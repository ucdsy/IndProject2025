from __future__ import annotations

import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_r_clean import build_candidate_snapshot


ROOT = Path(__file__).resolve().parents[1]


class StageRCleanTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")

    def test_context_only_city_prefers_base_node(self) -> None:
        sample = {
            "id": "synthetic_context_city_hotel",
            "namespace_version": "ns_v1_20260311",
            "query": "帮我找酒店，先给通用建议。",
            "context": {"city": "Chengdu"},
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "hotel.travel.cn",
            "relevant_fqdns": ["chengdu.hotel.travel.cn"],
        }
        snapshot = build_candidate_snapshot(sample, resolver=self.resolver, top_k=10, stage_r_version="sr_clean_test")
        candidates = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]]

        self.assertEqual(candidates[0], "hotel.travel.cn")
        self.assertNotEqual(candidates[0], "chengdu.hotel.travel.cn")

    def test_explicit_city_query_promotes_segment_node(self) -> None:
        sample = {
            "id": "synthetic_query_city_hotel",
            "namespace_version": "ns_v1_20260311",
            "query": "下周去成都出差，帮我找靠近会场的酒店。",
            "context": {"city": "Chengdu"},
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "chengdu.hotel.travel.cn",
            "relevant_fqdns": ["hotel.travel.cn"],
        }
        snapshot = build_candidate_snapshot(sample, resolver=self.resolver, top_k=10, stage_r_version="sr_clean_test")
        candidates = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]]

        self.assertEqual(candidates[0], "chengdu.hotel.travel.cn")
        self.assertIn("hotel.travel.cn", candidates[:3])

    def test_multi_intent_query_keeps_cross_domain_candidate(self) -> None:
        sample = {
            "id": "synthetic_multi_intent",
            "namespace_version": "ns_v1_20260311",
            "query": "安排下周评审会，并看看天气。",
            "context": {"time_window": "next_week", "city": "Suzhou", "industry": "enterprise_service"},
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "schedule.meeting.productivity.cn",
            "relevant_fqdns": ["weather.cn"],
        }
        snapshot = build_candidate_snapshot(sample, resolver=self.resolver, top_k=10, stage_r_version="sr_clean_test")
        candidates = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]]

        self.assertIn("meeting.productivity.cn", candidates[:2])
        self.assertIn("schedule.meeting.productivity.cn", candidates[:3])
        self.assertIn("weather.cn", candidates[:5])

    def test_low_signal_query_still_returns_non_empty_candidates(self) -> None:
        sample = {
            "id": "synthetic_low_signal",
            "namespace_version": "ns_v1_20260311",
            "query": "帮我梳理一下材料，先给个框架。",
            "context": {"industry": "enterprise_service"},
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "docs.productivity.cn",
            "relevant_fqdns": [],
        }
        snapshot = build_candidate_snapshot(sample, resolver=self.resolver, top_k=10, stage_r_version="sr_clean_test")
        candidates = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]]

        self.assertTrue(candidates)
        self.assertIn("docs.productivity.cn", candidates)

    def test_empty_query_does_not_crash_and_keeps_valid_candidates(self) -> None:
        sample = {
            "id": "synthetic_empty_query",
            "namespace_version": "ns_v1_20260311",
            "query": "",
            "context": {"industry": "enterprise_service"},
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "docs.productivity.cn",
            "relevant_fqdns": [],
        }
        snapshot = build_candidate_snapshot(sample, resolver=self.resolver, top_k=10, stage_r_version="sr_clean_test")
        candidates = snapshot["fqdn_candidates"]

        self.assertEqual(len(candidates), 10)
        self.assertTrue(all(candidate["fqdn"].endswith(".cn") for candidate in candidates))

    def test_long_context_with_mixed_types_still_returns_recall_trace(self) -> None:
        sample = {
            "id": "synthetic_long_context",
            "namespace_version": "ns_v1_20260311",
            "query": "帮我看一版风险评估。",
            "context": {
                "industry": "manufacturing",
                "time_window": "next_week",
                "notes": "设备上线前需要检查" * 20,
                "flags": ["external", "regulated_service"],
                "budget_rmb": 12000,
            },
            "constraints": ["fqdn_format_valid"],
            "ground_truth_fqdn": "risk.security.cn",
            "relevant_fqdns": ["data.compliance.security.cn"],
        }
        snapshot = build_candidate_snapshot(sample, resolver=self.resolver, top_k=10, stage_r_version="sr_clean_test")
        candidates = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]]

        self.assertIn("risk.security.cn", candidates)
        self.assertTrue(snapshot["confusion_sources"])
        self.assertIn("recall_sources", snapshot)


if __name__ == "__main__":
    unittest.main()
