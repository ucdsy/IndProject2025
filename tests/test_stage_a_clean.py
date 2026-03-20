from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_a_clean import StageACleanConfig, build_routing_run_trace

ROOT = Path(__file__).resolve().parents[1]


class StageACleanTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")
        cls.samples = {row["id"]: row for row in _load_jsonl(ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl")}
        cls.snapshots = {row["id"]: row for row in _load_jsonl(ROOT / "artifacts" / "stage_r_clean" / "dev.sr_clean_v1_20260307.jsonl")}
        cls.config = StageACleanConfig(stage_a_version="sa_clean_test")

    def _trace(self, sample_id: str) -> dict:
        return build_routing_run_trace(
            sample=self.samples[sample_id],
            snapshot=self.snapshots[sample_id],
            resolver=self.resolver,
            config=self.config,
        )

    def test_segment_invoice_can_beat_base_when_query_is_specific(self) -> None:
        trace = self._trace("formal_dev_000015")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "verify.invoice.finance.cn")
        self.assertIn("tax.finance.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_base_invoice_remains_primary_when_query_is_generic(self) -> None:
        trace = self._trace("formal_dev_000016")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "invoice.finance.cn")

    def test_meeting_multi_intent_distinguishes_primary_and_related(self) -> None:
        trace = self._trace("formal_dev_000024")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "summary.meeting.productivity.cn")
        self.assertIn("action-items.meeting.productivity.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_meeting_materials_secondary_can_recover_docs_related(self) -> None:
        trace = self._trace("formal_dev_000027")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "action-items.meeting.productivity.cn")
        self.assertIn("docs.productivity.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_fitness_secondary_can_recover_exercise_related(self) -> None:
        trace = self._trace("formal_dev_000046")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "nutrition.health.cn")
        self.assertIn("fitness.health.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_high_risk_related_does_not_expand_without_explicit_secondary_hit(self) -> None:
        trace = self._trace("formal_dev_000009")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "transaction.compliance.security.cn")
        self.assertIn("risk.security.cn", trace["stage_a"]["selected_related_fqdns"])
        self.assertNotIn("fraud.security.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_high_risk_flag_is_schema_driven_and_inherited_to_segments(self) -> None:
        self.assertTrue(self.resolver.get_node("policy.gov.cn").is_stage_a_high_risk)
        self.assertTrue(self.resolver.get_node("account.compliance.security.cn").is_stage_a_high_risk)
        self.assertTrue(self.resolver.get_node("fraud.security.cn").is_stage_a_high_risk)
        self.assertFalse(self.resolver.get_node("tax.finance.cn").is_stage_a_high_risk)

    def test_generic_meeting_request_prefers_base_over_schedule_child(self) -> None:
        trace = self._trace("formal_dev_000025")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "meeting.productivity.cn")

    def test_explicit_meeting_schedule_request_keeps_schedule_child(self) -> None:
        trace = self._trace("formal_dev_000026")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "schedule.meeting.productivity.cn")

    def test_generic_compliance_prefers_base_over_scene_only_segment(self) -> None:
        trace = self._trace("formal_dev_000008")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "compliance.security.cn")

    def test_city_in_scene_does_not_force_segment_for_generic_itinerary(self) -> None:
        trace = self._trace("formal_dev_000036")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "itinerary.travel.cn")

    def test_cross_domain_related_requires_secondary_evidence(self) -> None:
        trace = self._trace("formal_dev_000010")
        self.assertNotIn("summary.meeting.productivity.cn", trace["stage_a"]["selected_related_fqdns"])

    def test_high_risk_case_escalates(self) -> None:
        trace = self._trace("formal_dev_000007")
        self.assertEqual(trace["stage_a"]["selected_primary_fqdn"], "data.compliance.security.cn")
        self.assertTrue(trace["stage_a"]["escalate_to_stage_b"])

    def test_clean_trace_exposes_fast_path_final_fields(self) -> None:
        trace = self._trace("formal_dev_000016")
        self.assertFalse(trace["entered_stage_b"])
        self.assertEqual(trace["final_decision_source"], "stage_a_clean")
        self.assertEqual(trace["final_primary_fqdn"], trace["stage_a"]["selected_primary_fqdn"])
        self.assertEqual(trace["final_related_fqdns"], trace["stage_a"]["selected_related_fqdns"])



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
