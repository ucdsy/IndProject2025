from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.related_v2 import (
    RelatedV2Config,
    _apply_related_guardrails,
    analyze_related_v2,
    attach_related_v2_final_fields,
)
from src.agentdns_routing.service_api import RoutingResolveRequest, resolve_routing
from src.agentdns_routing.stage_a_eval import evaluate_traces
from src.agentdns_routing.stage_a_clean import StageACleanConfig, build_routing_run_trace

ROOT = Path(__file__).resolve().parents[1]


class RelatedV2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")
        cls.samples = {row["id"]: row for row in _load_jsonl(ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl")}
        cls.snapshots = {row["id"]: row for row in _load_jsonl(ROOT / "artifacts" / "stage_r_clean" / "dev.sr_clean_v1_20260307.jsonl")}
        cls.stage_a_config = StageACleanConfig(stage_a_version="sa_clean_related_v2_test")
        cls.related_config = RelatedV2Config(related_version="related_v2_test")

    def test_prefetch_is_reused_when_primary_is_stable(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            related_config=self.related_config,
            with_related_v2=False,
        )
        precomputed = analyze_related_v2(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            primary_fqdn=trace["final_primary_fqdn"],
            config=self.related_config,
        )
        finalized = attach_related_v2_final_fields(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            config=self.related_config,
            precomputed=precomputed,
        )
        self.assertEqual(finalized["final_related_fqdns"], ["action-items.meeting.productivity.cn"])
        self.assertTrue(finalized["related_v2"]["execution"]["prefetch_reused"])
        self.assertFalse(finalized["related_v2"]["execution"]["reran_after_primary_override"])

    def test_related_v2_reruns_when_primary_changes(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            related_config=self.related_config,
            with_related_v2=False,
        )
        precomputed = analyze_related_v2(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            primary_fqdn=trace["final_primary_fqdn"],
            config=self.related_config,
        )
        overridden = copy.deepcopy(trace)
        overridden["final_primary_fqdn"] = "action-items.meeting.productivity.cn"
        finalized = attach_related_v2_final_fields(
            sample=self.samples["formal_dev_000024"],
            trace=overridden,
            resolver=self.resolver,
            config=self.related_config,
            precomputed=precomputed,
        )
        self.assertNotEqual(precomputed["primary_fqdn"], finalized["related_v2"]["primary_fqdn"])
        self.assertTrue(finalized["related_v2"]["execution"]["reran_after_primary_override"])
        self.assertEqual(finalized["final_related_fqdns"], [])

    def test_service_returns_related_v2_result_fields(self) -> None:
        response = resolve_routing(
            RoutingResolveRequest(
                query="现在要处理的事情是“会议纪要先整理，顺手把待办项也列出来”。",
                context={},
                constraints=[],
                stage_a_mode="clean",
                stage_b_mode="skip",
                sample_id="service_related_v2_test",
            )
        )
        routing_result = response["routing_result"]
        self.assertIn("final_related_source", routing_result)
        self.assertIn("related_v2_version", routing_result)
        self.assertIn("related_candidate_options", routing_result)
        self.assertEqual(routing_result["final_related_source"], "related_v2_det")
        self.assertIsInstance(routing_result["final_related_fqdns"], list)
        self.assertIsInstance(routing_result["related_candidate_options"], list)

    def test_service_extracts_related_from_natural_multi_intent_query(self) -> None:
        response = resolve_routing(
            RoutingResolveRequest(
                query="这次去云南主要先把行程排清楚，顺手看一下住处和接驳。",
                context={},
                constraints=[],
                stage_a_mode="clean",
                stage_b_mode="skip",
                sample_id="service_related_v2_travel_test",
            )
        )
        routing_result = response["routing_result"]
        self.assertEqual(routing_result["final_primary_fqdn"], "yunnan.itinerary.travel.cn")
        self.assertEqual(
            routing_result["final_related_fqdns"],
            ["transport.travel.cn", "hotel.travel.cn"],
        )
        self.assertEqual(routing_result["final_related_source"], "related_v2_det")
        related_trace = response["trace"]["related_v2"]
        self.assertTrue(related_trace["has_multi_intent_signal"])
        self.assertIn("看一下住处和接驳", related_trace["secondary_intents"])
        candidate_map = {row["fqdn"]: row for row in related_trace["related_candidates"]}
        self.assertIn("hotel.travel.cn", candidate_map)
        self.assertIn("transport.travel.cn", candidate_map)
        self.assertIn("primary_neighbor", candidate_map["hotel.travel.cn"]["builder_sources"])
        self.assertIn("primary_neighbor", candidate_map["transport.travel.cn"]["builder_sources"])
        option_map = {row["fqdn"]: row for row in routing_result["related_candidate_options"]}
        self.assertEqual(option_map["hotel.travel.cn"]["status"], "selected")
        self.assertEqual(option_map["transport.travel.cn"]["status"], "selected")

    def test_stage_a_eval_prefers_final_related_fields(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            related_config=self.related_config,
            with_related_v2=False,
        )
        trace["final_primary_fqdn"] = trace["stage_a"]["selected_primary_fqdn"]
        trace["final_related_fqdns"] = ["action-items.meeting.productivity.cn"]
        trace["final_decision_source"] = "related_v2_test"
        trace["final_related_source"] = "related_v2_test"
        summary = evaluate_traces([self.samples["formal_dev_000024"]], [trace])
        self.assertEqual(summary["RelatedRecall"], 1.0)
        self.assertEqual(summary["RelatedPrecision"], 1.0)
        self.assertEqual(summary["per_sample"][0]["selected_related_fqdns"], ["action-items.meeting.productivity.cn"])
        self.assertEqual(summary["per_sample"][0]["final_related_source"], "related_v2_test")

    def test_llm_related_adjudication_uses_query_themes_then_applies_guardrails(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            related_config=self.related_config,
            with_related_v2=False,
        )
        result = analyze_related_v2(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            primary_fqdn=trace["final_primary_fqdn"],
            config=self.related_config,
            client=_ScriptedRelatedV2LLMClient(
                {
                    "secondary_intents": ["后续待办"],
                    "confidence": 0.82,
                    "related_rationale": "待办是 query 里的独立次主题。",
                    "confusion_points": ["primary_vs_secondary_ambiguous"],
                    "candidate_decisions": [
                        {
                            "fqdn": "action-items.meeting.productivity.cn",
                            "matched_intent": "后续待办",
                            "decision": "related",
                            "reason": "后续待办是独立次主题。",
                        },
                        {
                            "fqdn": "summary.meeting.productivity.cn",
                            "matched_intent": "",
                            "decision": "reject",
                            "reason": "这更像 primary 的同链路补充，不是独立次意图。",
                        }
                    ],
                }
            ),
        )
        self.assertEqual(result["decision_source"], "related_v2_llm")
        self.assertEqual(result["final_related_fqdns"], ["action-items.meeting.productivity.cn"])
        self.assertIn("primary_vs_secondary_ambiguous", result["confusion_points"])
        self.assertIsNotNone(result["llm_trace"])
        self.assertEqual(
            result["llm_trace"]["decision"]["candidate_decisions"][0]["matched_intent"],
            "后续待办",
        )

    def test_candidate_builder_survives_natural_language_secondary_intents(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            related_config=self.related_config,
            with_related_v2=False,
        )
        trace["stage_a"]["llm_decision"] = {
            "secondary_intents": [
                "先把会议纪要整理出来",
                "顺手把后续待办再列清楚",
            ]
        }
        result = analyze_related_v2(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            primary_fqdn=trace["final_primary_fqdn"],
            config=self.related_config,
            client=_ScriptedRelatedV2LLMClient(
                {
                    "secondary_intents": ["后续待办"],
                    "confidence": 0.8,
                    "related_rationale": "待办是 query 里的次主题。",
                    "confusion_points": [],
                    "candidate_decisions": [
                        {
                            "fqdn": "action-items.meeting.productivity.cn",
                            "matched_intent": "后续待办",
                            "decision": "related",
                            "reason": "来自 query 的后续待办意图，并与 primary 非重复。",
                        }
                    ],
                }
            ),
        )
        candidate_map = {row["fqdn"]: row for row in result["related_candidates"]}
        self.assertIn("action-items.meeting.productivity.cn", candidate_map)
        self.assertTrue(result["candidate_count"] > 0)
        self.assertIn("primary_neighbor", candidate_map["action-items.meeting.productivity.cn"]["builder_sources"])
        self.assertEqual(result["final_related_fqdns"], ["action-items.meeting.productivity.cn"])

    def test_llm_related_can_derive_selection_from_candidate_decisions(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            related_config=self.related_config,
            with_related_v2=False,
        )
        result = analyze_related_v2(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            primary_fqdn=trace["final_primary_fqdn"],
            config=self.related_config,
            client=_ScriptedRelatedV2LLMClient(
                {
                    "secondary_intents": ["后续待办"],
                    "confidence": 0.76,
                    "related_rationale": "query 明确包含后续待办这个次意图。",
                    "confusion_points": [],
                    "candidate_decisions": [
                        {
                            "fqdn": "action-items.meeting.productivity.cn",
                            "matched_intent": "后续待办",
                            "decision": "related",
                            "reason": "与 query 的非主意图一一对应。",
                        }
                    ],
                }
            ),
        )
        self.assertEqual(result["final_related_fqdns"], ["action-items.meeting.productivity.cn"])

    def test_guardrails_allow_llm_selected_cross_l1_when_supported_by_builder(self) -> None:
        kept, notes, confusion = _apply_related_guardrails(
            records=[
                {
                    "fqdn": "restaurant.travel.cn",
                    "cross_l1": True,
                    "cross_domain_secondary_ok": False,
                    "is_query_theme_seed": True,
                    "stage_r_present": True,
                    "score_related_v2": 0.39687,
                    "likely_primary_challenger": False,
                    "is_high_risk": False,
                    "explicit_secondary_hits": False,
                    "stage_b_related_prior": False,
                    "stage_a_related_prior": False,
                    "is_primary_neighbor": False,
                }
            ],
            proposed=["restaurant.travel.cn"],
            primary_fqdn="coupon.commerce.cn",
            resolver=self.resolver,
            config=self.related_config,
        )
        self.assertEqual(kept, ["restaurant.travel.cn"])
        self.assertIn("guard_keep:restaurant.travel.cn:cross_l1_llm_supported", notes)
        self.assertEqual(confusion, [])


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

class _ScriptedRelatedV2LLMClient:
    provider = "scripted"
    model = "scripted-related"

    def __init__(self, decision: dict) -> None:
        self._decision = decision

    def adjudicate_related(self, packet: dict, config: RelatedV2Config) -> tuple[dict, str]:
        return self._decision, json.dumps(self._decision, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
