from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_a_multi_intent import (
    StageAMultiIntentConfig,
    build_routing_run_trace,
)
from src.agentdns_routing.stage_b_multi_intent import (
    StageBMultiIntentConfig,
    build_stage_b_multi_intent_trace,
)

ROOT = Path(__file__).resolve().parents[1]


class _StageASetClient:
    provider = "test"
    model = "set-client"

    def __init__(self, selected: list[str], confidence: float = 0.9, escalate: bool = False) -> None:
        self.selected = selected
        self.confidence = confidence
        self.escalate = escalate

    def select_intents(self, packet, config):
        decision = {
            "intent_summary": "test set selection",
            "selected_fqdns": self.selected,
            "candidate_decisions": [
                {
                    "fqdn": row["fqdn"],
                    "decision": "select" if row["fqdn"] in self.selected else "drop",
                    "task_fit": 0.95 if row["fqdn"] in self.selected else 0.05,
                    "select_fit": 0.95 if row["fqdn"] in self.selected else 0.05,
                    "specificity_judgement": "fit",
                    "risk_mismatch": False,
                    "confidence": self.confidence if row["fqdn"] in self.selected else 0.5,
                    "evidence_for": ["hit"] if row["fqdn"] in self.selected else [],
                    "evidence_against": [],
                }
                for row in packet["candidates"]
            ],
            "confidence": self.confidence,
            "escalate_to_stage_b": self.escalate,
            "escalation_reasons": [],
            "uncertainty_points": [],
        }
        return decision, json.dumps(decision, ensure_ascii=False)


class _StageBSetClient:
    provider = "test"
    model = "set-reviewer"

    def __init__(self, proposed_by_role: dict[str, list[str]]) -> None:
        self.proposed_by_role = proposed_by_role

    def review_set(self, role_name, packet, config):
        proposed = self.proposed_by_role.get(role_name, packet["stage_a_selected_fqdns"])
        stage_a_selected = set(packet["stage_a_selected_fqdns"])
        decision = {
            "proposed_selected_fqdns": proposed,
            "keep_fqdns": [fqdn for fqdn in proposed if fqdn in stage_a_selected],
            "add_fqdns": [fqdn for fqdn in proposed if fqdn not in stage_a_selected],
            "remove_fqdns": [fqdn for fqdn in stage_a_selected if fqdn not in proposed],
            "confidence": 0.9,
            "rationale": "scripted",
            "candidate_decisions": [
                {
                    "fqdn": row["fqdn"],
                    "action": "keep" if row["fqdn"] in proposed and row["fqdn"] in stage_a_selected else "add" if row["fqdn"] in proposed else "drop",
                    "confidence": 0.9 if row["fqdn"] in proposed else 0.5,
                    "evidence": ["hit"] if row["fqdn"] in proposed else [],
                }
                for row in packet["candidates"]
            ],
        }
        return decision, json.dumps(decision, ensure_ascii=False)


class MultiIntentRoutingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")
        cls.samples = {
            row["id"]: row
            for row in _load_jsonl(ROOT / "data" / "agentdns_routing" / "formal" / "multi_intent_eval_v1.jsonl")
        }
        cls.snapshots = {
            row["id"]: row
            for row in _load_jsonl(
                ROOT
                / "artifacts"
                / "stage_r_clean"
                / "multi_intent_eval_v1_deepseek_chat_v3_20260426"
                / "multi_intent_eval_v1.sr_clean_v0_20260306.jsonl"
            )
        }

    def test_stage_a_multi_keeps_set_field_and_compat_fields(self) -> None:
        sample = self.samples["multi_intent_eval_v1_000001"]
        snapshot = self.snapshots[sample["id"]]
        trace = build_routing_run_trace(
            sample=sample,
            snapshot=snapshot,
            resolver=self.resolver,
            client=_StageASetClient(["weather.cn"]),
            config=StageAMultiIntentConfig(stage_a_version="stage_a_multi_test"),
        )
        self.assertEqual(trace["final_selected_fqdns"], ["weather.cn"])
        self.assertEqual(trace["final_primary_fqdn"], "weather.cn")
        self.assertEqual(trace["final_related_fqdns"], [])
        self.assertEqual(trace["final_decision_source"], "stage_a_multi_intent")

    def test_stage_b_multi_adds_candidate_by_consensus(self) -> None:
        sample = self.samples["multi_intent_eval_v1_000004"]
        snapshot = self.snapshots[sample["id"]]
        candidate_fqdns = [row["fqdn"] for row in snapshot["fqdn_candidates"]]
        base_fqdn = candidate_fqdns[0]
        add_fqdn = candidate_fqdns[1]
        stage_a_trace = build_routing_run_trace(
            sample=sample,
            snapshot=snapshot,
            resolver=self.resolver,
            client=_StageASetClient([base_fqdn], confidence=0.2, escalate=True),
            config=StageAMultiIntentConfig(stage_a_version="stage_a_multi_test"),
        )
        client = _StageBSetClient(
            {
                "DomainExpert": [base_fqdn, add_fqdn],
                "GovernanceRisk": [base_fqdn],
                "HierarchyResolver": [base_fqdn, add_fqdn],
                "UserPreference": [base_fqdn, add_fqdn],
            }
        )
        trace = build_stage_b_multi_intent_trace(
            sample=sample,
            trace=stage_a_trace,
            resolver=self.resolver,
            config=StageBMultiIntentConfig(stage_b_version="stage_b_multi_test", max_rounds=1),
            client=client,
        )
        self.assertTrue(trace["entered_stage_b"])
        self.assertIn(base_fqdn, trace["final_selected_fqdns"])
        self.assertIn(add_fqdn, trace["final_selected_fqdns"])
        self.assertEqual(trace["final_decision_source"], "stage_b_multi_intent")


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
