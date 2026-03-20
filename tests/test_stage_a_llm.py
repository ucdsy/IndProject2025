from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_a_eval import validate_traces
from src.agentdns_routing.stage_a_llm import (
    MockStageALLMClient,
    OpenAICompatibleStageALLMClient,
    StageALLMConfig,
    _minmax_norm,
    build_decision_packet,
    build_routing_run_trace,
)
from src.agentdns_routing.stage_a_clean import analyze_stage_a, StageACleanConfig

ROOT = Path(__file__).resolve().parents[1]


class _FixedClient:
    provider = "test"
    model = "fixed-json"

    def __init__(self, decision: dict):
        self._decision = decision

    def adjudicate(self, packet, config):
        return self._decision, json.dumps(self._decision, ensure_ascii=False)


class _FakeCompletions:
    def __init__(self, content: str, fail_on_json_mode: bool = False):
        self._content = content
        self._fail_on_json_mode = fail_on_json_mode
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail_on_json_mode and "response_format" in kwargs:
            raise TypeError("got an unexpected keyword argument 'response_format'")

        class _Message:
            def __init__(self, content: str) -> None:
                self.content = content

        class _Choice:
            def __init__(self, content: str) -> None:
                self.message = _Message(content)

        class _Response:
            def __init__(self, content: str) -> None:
                self.choices = [_Choice(content)]

        return _Response(self._content)


class _FakeOpenAIClient:
    def __init__(self, content: str, fail_on_json_mode: bool = False):
        self.chat = type(
            "_Chat",
            (),
            {"completions": _FakeCompletions(content, fail_on_json_mode=fail_on_json_mode)},
        )()


class StageALLMTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")
        cls.samples = {row["id"]: row for row in _load_jsonl(ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl")}
        cls.snapshots = {row["id"]: row for row in _load_jsonl(ROOT / "artifacts" / "stage_r_clean" / "dev.sr_clean_v1_20260307.jsonl")}
        cls.config = StageALLMConfig(stage_a_version="sa_llm_test")

    def test_decision_packet_contains_candidate_table_and_rules(self) -> None:
        sample = self.samples["formal_dev_000024"]
        snapshot = self.snapshots[sample["id"]]
        base_stage_a = analyze_stage_a(sample=sample, snapshot=snapshot, resolver=self.resolver, config=StageACleanConfig())
        packet = build_decision_packet(sample=sample, snapshot=snapshot, resolver=self.resolver, base_stage_a=base_stage_a, config=self.config)
        self.assertTrue(packet["hard_rules"])
        self.assertTrue(packet["candidates"])
        self.assertIn("selected_primary_fqdn", " ".join(packet["hard_rules"]))

    def test_invalid_llm_primary_does_not_escape_candidates(self) -> None:
        sample = self.samples["formal_dev_000024"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "selected_primary_fqdn": "not.allowed.cn",
                "selected_related_fqdns": ["action-items.meeting.productivity.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "summary.meeting.productivity.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.9,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["会议要点"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "action-items.meeting.productivity.cn",
                        "task_fit": 0.7,
                        "primary_fit": 0.2,
                        "related_fit": 0.9,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["待办"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.8,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        candidate_fqdns = {row["fqdn"] for row in snapshot["fqdn_candidates"]}
        self.assertIn(trace["stage_a"]["selected_primary_fqdn"], candidate_fqdns)
        self.assertIn("llm_primary_not_in_candidates", trace["stage_a"]["constraint_check"]["reasons"])

    def test_mock_client_trace_validates(self) -> None:
        sample = self.samples["formal_dev_000015"]
        snapshot = self.snapshots[sample["id"]]
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=MockStageALLMClient(), config=self.config)
        validation = validate_traces([trace], ROOT)
        self.assertTrue(validation["valid"])
        self.assertEqual(trace["stage_a"]["llm_provider"], "mock")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "verify.invoice.finance.cn")

    def test_llm_trace_records_fast_path_provenance_and_final_fields(self) -> None:
        sample = self.samples["formal_dev_000015"]
        snapshot = self.snapshots[sample["id"]]
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=MockStageALLMClient(), config=self.config)
        self.assertFalse(trace["entered_stage_b"])
        self.assertEqual(trace["final_decision_source"], "stage_a_llm")
        self.assertEqual(trace["final_primary_fqdn"], trace["stage_a"]["selected_primary_fqdn"])
        self.assertEqual(trace["stage_a"]["base_stage_a_version"], self.config.base_stage_a_version)
        self.assertEqual(trace["stage_a"]["prompt_version"], self.config.prompt_version)
        self.assertIn("query_packet", trace["stage_a"])

    def test_minmax_norm_uses_spread_floor(self) -> None:
        normed = _minmax_norm({"a": 0.05, "b": 0.15}, spread_floor=0.5)
        self.assertAlmostEqual(normed["a"], 0.0)
        self.assertAlmostEqual(normed["b"], 0.2)
        equal_normed = _minmax_norm({"a": 0.15, "b": 0.15}, spread_floor=0.5)
        self.assertEqual(equal_normed, {"a": 0.0, "b": 0.0})

    def test_openai_client_retries_without_json_mode_if_unsupported(self) -> None:
        client = OpenAICompatibleStageALLMClient.__new__(OpenAICompatibleStageALLMClient)
        client.provider = "openai"
        client.model = "gpt-5.4"
        client._client = _FakeOpenAIClient(
            content=json.dumps({"selected_primary_fqdn": "permit.gov.cn"}, ensure_ascii=False),
            fail_on_json_mode=True,
        )
        decision, _ = client.adjudicate({"query": "test", "candidates": []}, self.config)
        calls = client._client.chat.completions.calls
        self.assertEqual(decision["selected_primary_fqdn"], "permit.gov.cn")
        self.assertEqual(len(calls), 2)
        self.assertIn("response_format", calls[0])
        self.assertNotIn("response_format", calls[1])

    def test_dict_candidate_judgements_are_normalized(self) -> None:
        sample = self.samples["formal_dev_000001"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "企业短信验证码接口商用",
                "primary_intent": "梳理资质与备案",
                "secondary_intents": ["列出依据"],
                "selected_primary_fqdn": "permit.gov.cn",
                "selected_related_fqdns": [],
                "candidate_judgements": {
                    "permit.gov.cn": {
                        "task_fit": 0.9,
                        "primary_fit": 0.95,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "confidence": 0.9,
                        "evidence_for": "资质、备案",
                        "evidence_against": "",
                    }
                },
                "confidence": 0.9,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertNotIn("llm_judgements_not_list", trace["stage_a"]["constraint_check"]["reasons"])
        llm_rows = {row["fqdn"]: row for row in trace["stage_a"]["llm_decision"]["candidate_judgements"]}
        self.assertEqual(llm_rows["permit.gov.cn"]["task_fit"], 0.9)
        self.assertEqual(llm_rows["permit.gov.cn"]["evidence_for"], ["资质、备案"])

    def test_cross_domain_related_without_anchor_is_suppressed(self) -> None:
        sample = self.samples["formal_dev_000004"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "制造业背景下的数据接口规范要求",
                "primary_intent": "查找规范要求",
                "secondary_intents": ["列出检查提纲"],
                "selected_primary_fqdn": "policy.gov.cn",
                "selected_related_fqdns": ["compliance.security.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "policy.gov.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.9,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["规范要求"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "compliance.security.cn",
                        "task_fit": 0.6,
                        "primary_fit": 0.2,
                        "related_fit": 0.8,
                        "specificity_judgement": "too_coarse",
                        "risk_mismatch": False,
                        "evidence_for": [],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.9,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "policy.gov.cn")
        self.assertEqual(trace["stage_a"]["selected_related_fqdns"], [])

    def test_non_risk_cross_l1_secondary_related_can_be_kept(self) -> None:
        sample = self.samples["formal_dev_000037"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "去西安待四天",
                "primary_intent": "把西安这趟行程排出来",
                "secondary_intents": ["看看那几天的天气"],
                "selected_primary_fqdn": "xian.itinerary.travel.cn",
                "selected_related_fqdns": ["weather.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "xian.itinerary.travel.cn",
                        "task_fit": 0.95,
                        "primary_fit": 0.95,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["西安行程"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "weather.cn",
                        "task_fit": 0.8,
                        "primary_fit": 0.0,
                        "related_fit": 0.8,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["天气"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.9,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertIn("weather.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_same_l1_deterministic_secondary_anchor_can_rescue_related(self) -> None:
        sample = self.samples["formal_dev_000027"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "安排工业平台上线前的评审会",
                "primary_intent": "把会后的待办和责任项拉出来",
                "secondary_intents": ["补会议材料提纲"],
                "selected_primary_fqdn": "action-items.meeting.productivity.cn",
                "selected_related_fqdns": ["action-items.meeting.productivity.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "action-items.meeting.productivity.cn",
                        "task_fit": 0.95,
                        "primary_fit": 0.95,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["待办"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "docs.productivity.cn",
                        "task_fit": 0.2,
                        "primary_fit": 0.0,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": [],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.82,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertIn("docs.productivity.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_risk_cross_l1_secondary_related_remains_blocked(self) -> None:
        sample = self.samples["formal_dev_000004"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "工业互联网平台的数据接口要求",
                "primary_intent": "查清规范要求",
                "secondary_intents": ["列检查提纲"],
                "selected_primary_fqdn": "policy.gov.cn",
                "selected_related_fqdns": ["compliance.security.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "policy.gov.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.9,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["规范要求"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "compliance.security.cn",
                        "task_fit": 0.7,
                        "primary_fit": 0.3,
                        "related_fit": 0.8,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["检查提纲"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.9,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_related_fqdns"], [])

    def test_descendant_primary_without_primary_hits_falls_back_to_parent(self) -> None:
        sample = self.samples["formal_dev_000008"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "企业客户账号体系实名和权限治理",
                "primary_intent": "账号合规核对",
                "secondary_intents": [],
                "selected_primary_fqdn": "account.compliance.security.cn",
                "selected_related_fqdns": ["compliance.security.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "account.compliance.security.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.95,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": [],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "compliance.security.cn",
                        "task_fit": 0.8,
                        "primary_fit": 0.0,
                        "related_fit": 0.8,
                        "specificity_judgement": "too_coarse",
                        "risk_mismatch": False,
                        "evidence_for": [],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.9,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "compliance.security.cn")
        self.assertEqual(trace["stage_a"]["selected_related_fqdns"], [])

    def test_scene_only_city_segment_falls_back_to_generic_itinerary_parent(self) -> None:
        sample = self.samples["formal_dev_000036"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "去西安待四天",
                "primary_intent": "把路线和安排理出来",
                "secondary_intents": [],
                "selected_primary_fqdn": "xian.itinerary.travel.cn",
                "selected_related_fqdns": [],
                "candidate_judgements": [
                    {
                        "fqdn": "xian.itinerary.travel.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.9,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["西安场景"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "itinerary.travel.cn",
                        "task_fit": 0.7,
                        "primary_fit": 0.7,
                        "related_fit": 0.0,
                        "specificity_judgement": "too_coarse",
                        "risk_mismatch": False,
                        "evidence_for": ["路线安排"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.75,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "itinerary.travel.cn")

    def test_generic_meeting_schedule_child_falls_back_to_base_parent(self) -> None:
        sample = self.samples["formal_dev_000025"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "设备联调周会",
                "primary_intent": "把会议安排妥",
                "secondary_intents": [],
                "selected_primary_fqdn": "schedule.meeting.productivity.cn",
                "selected_related_fqdns": [],
                "candidate_judgements": [
                    {
                        "fqdn": "schedule.meeting.productivity.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.95,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["安排会议"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "meeting.productivity.cn",
                        "task_fit": 0.8,
                        "primary_fit": 0.85,
                        "related_fit": 0.0,
                        "specificity_judgement": "too_coarse",
                        "risk_mismatch": False,
                        "evidence_for": ["会议"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.86,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "meeting.productivity.cn")

    def test_explicit_meeting_schedule_request_is_not_demoted(self) -> None:
        sample = self.samples["formal_dev_000026"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "给企业客户准备项目例会",
                "primary_intent": "安排好会议时间和会场",
                "secondary_intents": [],
                "selected_primary_fqdn": "schedule.meeting.productivity.cn",
                "selected_related_fqdns": [],
                "candidate_judgements": [
                    {
                        "fqdn": "schedule.meeting.productivity.cn",
                        "task_fit": 0.9,
                        "primary_fit": 0.9,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["会议时间和会场"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "meeting.productivity.cn",
                        "task_fit": 0.8,
                        "primary_fit": 0.7,
                        "related_fit": 0.0,
                        "specificity_judgement": "too_coarse",
                        "risk_mismatch": False,
                        "evidence_for": ["会议"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.88,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "schedule.meeting.productivity.cn")

    def test_explicit_city_segment_with_primary_hits_is_not_demoted(self) -> None:
        sample = self.samples["formal_dev_000037"]
        snapshot = self.snapshots[sample["id"]]
        client = _FixedClient(
            {
                "scene_context": "去西安待四天",
                "primary_intent": "把西安这趟行程排出来",
                "secondary_intents": ["看看那几天的天气"],
                "selected_primary_fqdn": "xian.itinerary.travel.cn",
                "selected_related_fqdns": ["weather.cn"],
                "candidate_judgements": [
                    {
                        "fqdn": "xian.itinerary.travel.cn",
                        "task_fit": 0.95,
                        "primary_fit": 0.95,
                        "related_fit": 0.0,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["西安行程"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "itinerary.travel.cn",
                        "task_fit": 0.7,
                        "primary_fit": 0.7,
                        "related_fit": 0.0,
                        "specificity_judgement": "too_coarse",
                        "risk_mismatch": False,
                        "evidence_for": ["行程"],
                        "evidence_against": [],
                    },
                    {
                        "fqdn": "weather.cn",
                        "task_fit": 0.8,
                        "primary_fit": 0.0,
                        "related_fit": 0.8,
                        "specificity_judgement": "fit",
                        "risk_mismatch": False,
                        "evidence_for": ["天气"],
                        "evidence_against": [],
                    },
                ],
                "confidence": 0.9,
                "escalate_to_stage_b": False,
                "escalation_reasons": [],
                "notes": [],
            }
        )
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=self.resolver, client=client, config=self.config)
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "xian.itinerary.travel.cn")


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


if __name__ == "__main__":
    unittest.main()
