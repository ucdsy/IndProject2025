from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_a import StageAConfig, run_stage_a
from src.agentdns_routing.stage_r import build_candidate_snapshot, load_json, load_jsonl


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "agentdns_routing"


class StageATestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.descriptors = load_jsonl(DATA_DIR / "namespace_descriptors.jsonl")
        cls.lexicon = load_json(DATA_DIR / "evidence_lexicon.json")
        cls.resolver = NamespaceResolver(cls.descriptors)
        cls.dev_samples = {sample["id"]: sample for sample in load_jsonl(DATA_DIR / "dev.jsonl")}
        cls.config = StageAConfig()

    def _trace_for(self, sample_id: str) -> tuple[dict, dict]:
        sample = self.dev_samples[sample_id]
        snapshot = build_candidate_snapshot(sample, self.descriptors, self.lexicon, stage_r_version="sr_test")
        trace = run_stage_a(sample=sample, stage_r_trace=snapshot, resolver=self.resolver, config=self.config)
        return sample, trace

    def test_l3_exact_hit(self) -> None:
        sample, trace = self._trace_for("finance_000001")
        self.assertEqual(trace["selected_primary_fqdn"], sample["ground_truth_fqdn"])

    def test_multi_intent_related_retention(self) -> None:
        _, trace = self._trace_for("productivity_000001")
        self.assertIn("action-items.meeting.productivity.cn", trace["selected_related_fqdns"])

    def test_high_risk_escalates(self) -> None:
        _, trace = self._trace_for("security_000001")
        self.assertTrue(trace["escalate_to_stage_b"])
        self.assertIn("high_risk", trace["escalation_reasons"])

    def test_l3_missing_evidence_falls_back_to_l2(self) -> None:
        sample = {
            "id": "synthetic_fallback_001",
            "namespace_version": "ns_v1_20260311",
            "query": "帮我梳理一下企业发票处理流程，先给总体说明。",
            "context": {"industry": "enterprise_service"},
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "invoice.finance.cn",
            "relevant_fqdns": [],
            "acceptable_fqdns": ["invoice.finance.cn"],
        }
        snapshot = build_candidate_snapshot(sample, self.descriptors, self.lexicon, stage_r_version="sr_test")
        snapshot["fqdn_candidates"] = [
            {"fqdn": "verify.invoice.finance.cn", "score_r": 0.72, "source": ["synthetic"]},
            {"fqdn": "issue.invoice.finance.cn", "score_r": 0.70, "source": ["synthetic"]},
            {"fqdn": "invoice.finance.cn", "score_r": 0.69, "source": ["synthetic"]},
        ]
        trace = run_stage_a(sample=sample, stage_r_trace=snapshot, resolver=self.resolver, config=self.config)
        self.assertEqual(trace["selected_primary_fqdn"], "invoice.finance.cn")


if __name__ == "__main__":
    unittest.main()
