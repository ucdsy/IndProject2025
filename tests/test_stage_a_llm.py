from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_a_eval import validate_traces
from src.agentdns_routing.stage_a_llm import (
    MockStageALLMClient,
    StageALLMConfig,
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
