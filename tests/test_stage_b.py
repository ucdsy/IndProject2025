from __future__ import annotations

import copy
import json
import time
import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.stage_a_clean import StageACleanConfig, build_routing_run_trace
from src.agentdns_routing.stage_a_eval import validate_traces
from src.agentdns_routing.stage_b_consensus import (
    StageBConfig,
    _role_temperature,
    build_stage_b_trace,
)
from src.agentdns_routing.stage_a_llm import (
    StageALLMConfig,
    build_routing_run_trace as build_stage_a_llm_trace,
)

ROOT = Path(__file__).resolve().parents[1]


class StageBTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")
        cls.samples = {row["id"]: row for row in _load_jsonl(ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl")}
        cls.snapshots = {row["id"]: row for row in _load_jsonl(ROOT / "artifacts" / "stage_r_clean" / "dev.sr_clean_v1_20260307.jsonl")}
        cls.stage_a_config = StageACleanConfig(stage_a_version="sa_clean_test")
        cls.stage_b_config = StageBConfig(stage_b_version="stage_b_test")

    def _stage_b_trace(self, sample_id: str) -> dict:
        stage_a_trace = build_routing_run_trace(
            sample=self.samples[sample_id],
            snapshot=self.snapshots[sample_id],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        return build_stage_b_trace(
            sample=self.samples[sample_id],
            trace=stage_a_trace,
            resolver=self.resolver,
            config=self.stage_b_config,
        )

    def _force_stage_a_escalation(self, trace: dict, reasons: list[str] | None = None) -> dict:
        forced = copy.deepcopy(trace)
        forced["stage_a"]["escalate_to_stage_b"] = True
        forced["stage_a"]["escalation_reasons"] = list(reasons or ["low_confidence"])
        return forced

    def _mutate_candidate(
        self,
        trace: dict,
        fqdn: str,
        *,
        score_a: float | None = None,
        score_related: float | None = None,
        primary_hits: list[str] | None = None,
        secondary_hits: list[str] | None = None,
        scene_hits: list[str] | None = None,
        specificity_fit: float | None = None,
    ) -> dict:
        updated = copy.deepcopy(trace)
        for row in updated["stage_a"]["candidate_scores"]:
            if row["fqdn"] != fqdn:
                continue
            if score_a is not None:
                row["score_a"] = score_a
            if score_related is not None:
                row["score_related"] = score_related
            evidence_for = row.setdefault("evidence_for", {})
            if primary_hits is not None:
                evidence_for["primary_hits"] = list(primary_hits)
            if secondary_hits is not None:
                evidence_for["secondary_hits"] = list(secondary_hits)
            if scene_hits is not None:
                evidence_for["scene_hits"] = list(scene_hits)
            breakdown = row.setdefault("score_breakdown", {})
            if specificity_fit is not None:
                breakdown["specificity_fit"] = specificity_fit
            break
        return updated

    def test_non_escalated_trace_is_skipped(self) -> None:
        trace = self._stage_b_trace("formal_dev_000016")
        self.assertEqual(trace["stage_b"]["decision_mode"], "skipped_not_escalated")
        self.assertEqual(
            trace["stage_b"]["selected_primary_fqdn"],
            trace["stage_a"]["selected_primary_fqdn"],
        )

    def test_escalated_trace_keeps_primary_inside_candidates(self) -> None:
        trace = self._stage_b_trace("formal_dev_000007")
        candidate_fqdns = {row["fqdn"] for row in trace["stage_r"]["fqdn_candidates"]}
        self.assertIn(trace["stage_b"]["selected_primary_fqdn"], candidate_fqdns)
        self.assertTrue(trace["stage_b"]["trust_trace"]["stage_a_escalated"])

    def test_stage_b_emits_four_role_votes(self) -> None:
        trace = self._stage_b_trace("formal_dev_000025")
        self.assertEqual(len([vote for vote in trace["stage_b"]["agent_votes"] if vote["round"] == 1]), 4)
        self.assertIn(len(trace["stage_b"]["agent_votes"]), {4, 8})
        self.assertIn(trace["stage_b"]["consensus_rounds"], {1, 2})

    def test_stage_b_trace_still_validates_against_base_schema(self) -> None:
        trace = self._stage_b_trace("formal_dev_000036")
        validation = validate_traces([trace], ROOT)
        self.assertTrue(validation["valid"], validation["errors"])

    def test_stage_b_llm_path_marks_final_output_as_stage_b(self) -> None:
        stage_a_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000007"],
            snapshot=self.snapshots["formal_dev_000007"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": stage_a_trace["stage_a"]["selected_primary_fqdn"],
                    "proposal_related_fqdns": [],
                    "confidence": 0.9,
                    "rationale": f"{role}: keep",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000007"],
            trace=stage_a_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_llm_test"),
            client=client,
        )
        self.assertTrue(trace["entered_stage_b"])
        self.assertEqual(trace["final_decision_source"], "stage_b")
        self.assertEqual(trace["stage_b"]["decision_mode"], "llm_consensus_v1")
        self.assertEqual(len([row for row in trace["stage_b"]["agent_votes"] if row["round"] == 1]), 4)
        self.assertEqual(trace["final_primary_fqdn"], trace["stage_b"]["selected_primary_fqdn"])

    def test_sensitive_override_is_blocked_without_stronger_explicit_support(self) -> None:
        stage_a_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000007"],
            snapshot=self.snapshots["formal_dev_000007"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "compliance.security.cn",
                    "proposal_related_fqdns": [],
                    "confidence": 0.95,
                    "rationale": f"{role}: override_to_base",
                    "override_position": "propose_override",
                    "override_basis_tags": ["risk_requirement", "hierarchy_disambiguation"],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            },
            round2={
                role: {
                    "proposal_primary_fqdn": "compliance.security.cn",
                    "proposal_related_fqdns": [],
                    "confidence": 0.97,
                    "rationale": f"{role}: override_to_base_round2",
                    "override_position": "propose_override",
                    "override_basis_tags": ["risk_requirement", "hierarchy_disambiguation"],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            },
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000007"],
            trace=stage_a_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_sensitive_block_test"),
            client=client,
        )
        self.assertEqual(trace["stage_b"]["consensus_rounds"], 2)
        self.assertEqual(trace["stage_b"]["selected_primary_fqdn"], stage_a_trace["stage_a"]["selected_primary_fqdn"])
        self.assertTrue(trace["stage_b"]["trust_trace"]["override_attempted"])
        self.assertFalse(trace["stage_b"]["trust_trace"]["override_allowed"])
        self.assertIn(
            "sensitive_override_requires_stronger_explicit_support",
            trace["stage_b"]["trust_trace"]["override_block_reasons"],
        )
        self.assertTrue(trace["stage_b"]["trust_trace"]["sensitive_override_flags"]["high_risk_override"])
        self.assertTrue(trace["stage_b"]["trust_trace"]["sensitive_override_flags"]["hierarchical_override"])

    def test_non_sensitive_override_is_allowed_with_generic_thresholds(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000016"],
            snapshot=self.snapshots["formal_dev_000016"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["low_confidence"])
        base_trace = self._mutate_candidate(
            base_trace,
            "budget.finance.cn",
            score_a=0.92,
            primary_hits=["预算"],
            secondary_hits=[],
            scene_hits=[],
            specificity_fit=0.9,
        )
        base_trace["stage_a"]["selected_primary_fqdn"] = "invoice.finance.cn"
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "budget.finance.cn",
                    "proposal_related_fqdns": [],
                    "confidence": 0.94,
                    "rationale": f"{role}: budget_override",
                    "override_position": "propose_override",
                    "override_basis_tags": ["explicit_primary_evidence", "specificity_gain"],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000016"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_nonsensitive_allow_test"),
            client=client,
        )
        self.assertEqual(trace["stage_b"]["selected_primary_fqdn"], "budget.finance.cn")
        self.assertTrue(trace["stage_b"]["trust_trace"]["override_attempted"])
        self.assertTrue(trace["stage_b"]["trust_trace"]["override_allowed"])
        self.assertEqual(trace["final_primary_fqdn"], "budget.finance.cn")
        self.assertEqual(trace["final_decision_source"], "stage_b")

    def test_related_can_update_without_primary_flip(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000016"],
            snapshot=self.snapshots["formal_dev_000016"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["low_confidence"])
        base_trace = self._mutate_candidate(
            base_trace,
            "budget.finance.cn",
            score_related=0.42,
            secondary_hits=["预算"],
            scene_hits=[],
        )
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "invoice.finance.cn",
                    "proposal_related_fqdns": ["budget.finance.cn"],
                    "confidence": 0.86,
                    "rationale": f"{role}: keep_invoice_add_budget",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000016"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_related_update_test"),
            client=client,
        )
        self.assertEqual(trace["stage_b"]["selected_primary_fqdn"], "invoice.finance.cn")
        self.assertIn("budget.finance.cn", trace["stage_b"]["selected_related_fqdns"])
        self.assertEqual(trace["final_primary_fqdn"], "invoice.finance.cn")
        self.assertIn("budget.finance.cn", trace["final_related_fqdns"])

    def test_scene_only_related_addition_is_blocked(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000036"],
            snapshot=self.snapshots["formal_dev_000036"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["low_confidence"])
        base_trace["stage_a"]["selected_related_fqdns"] = []
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "itinerary.travel.cn",
                    "proposal_related_fqdns": ["xian.hotel.travel.cn"],
                    "confidence": 0.82,
                    "rationale": f"{role}: keep_itinerary_add_city_scene_only",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000036"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_scene_only_related_block_test"),
            client=client,
        )
        self.assertNotIn("xian.hotel.travel.cn", trace["stage_b"]["selected_related_fqdns"])

    def test_chain_duplicate_related_addition_is_blocked(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000011"],
            snapshot=self.snapshots["formal_dev_000011"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["high_risk", "low_confidence"])
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "risk.security.cn",
                    "proposal_related_fqdns": ["data.compliance.security.cn", "compliance.security.cn"],
                    "confidence": 0.91,
                    "rationale": f"{role}: keep_risk_expand_compliance_chain",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000011"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_related_chain_block_test"),
            client=client,
        )
        self.assertIn("data.compliance.security.cn", trace["stage_b"]["selected_related_fqdns"])
        self.assertNotIn("compliance.security.cn", trace["stage_b"]["selected_related_fqdns"])

    def test_cross_l1_new_related_requires_stronger_related_score(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000010"],
            snapshot=self.snapshots["formal_dev_000010"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["high_risk", "multi_intent_conflict"])
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "account.compliance.security.cn",
                    "proposal_related_fqdns": ["summary.meeting.productivity.cn"],
                    "confidence": 0.84,
                    "rationale": f"{role}: keep_primary_add_cross_l1_related",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000010"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_related_cross_l1_block_test"),
            client=client,
        )
        self.assertNotIn("summary.meeting.productivity.cn", trace["stage_b"]["selected_related_fqdns"])

    def test_primary_only_new_related_addition_is_blocked(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000039"],
            snapshot=self.snapshots["formal_dev_000039"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["low_confidence"])
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "chengdu.hotel.travel.cn",
                    "proposal_related_fqdns": ["transport.travel.cn", "chengdu.itinerary.travel.cn"],
                    "confidence": 0.83,
                    "rationale": f"{role}: keep_hotel_add_city_itinerary",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000039"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_related_primary_only_block_test"),
            client=client,
        )
        self.assertIn("transport.travel.cn", trace["stage_b"]["selected_related_fqdns"])
        self.assertNotIn("chengdu.itinerary.travel.cn", trace["stage_b"]["selected_related_fqdns"])

    def test_cross_l1_sensitive_override_requires_stage_a_score_gain(self) -> None:
        base_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000016"],
            snapshot=self.snapshots["formal_dev_000016"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        base_trace = self._force_stage_a_escalation(base_trace, reasons=["low_confidence"])
        base_trace = self._mutate_candidate(
            base_trace,
            "tutoring.education.cn",
            score_a=0.60,
            primary_hits=["辅导"],
            secondary_hits=[],
            scene_hits=[],
        )
        client = _ScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": "tutoring.education.cn",
                    "proposal_related_fqdns": [],
                    "confidence": 0.95,
                    "rationale": f"{role}: tutoring_override",
                    "override_position": "propose_override",
                    "override_basis_tags": ["explicit_primary_evidence"],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            },
            round2={
                role: {
                    "proposal_primary_fqdn": "tutoring.education.cn",
                    "proposal_related_fqdns": [],
                    "confidence": 0.96,
                    "rationale": f"{role}: tutoring_override_round2",
                    "override_position": "propose_override",
                    "override_basis_tags": ["explicit_primary_evidence"],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            },
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000016"],
            trace=base_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_cross_l1_block_test"),
            client=client,
        )
        self.assertEqual(trace["stage_b"]["selected_primary_fqdn"], "invoice.finance.cn")
        self.assertIn(
            "cross_l1_override_requires_stage_a_score_gain",
            trace["stage_b"]["trust_trace"]["override_block_reasons"],
        )

    def test_stage_b_accepts_upstream_stage_a_llm_trace(self) -> None:
        trace = build_stage_a_llm_trace(
            sample=self.samples["formal_dev_000007"],
            snapshot=self.snapshots["formal_dev_000007"],
            resolver=self.resolver,
            client=_HeuristicStageATestClient(),
            config=StageALLMConfig(stage_a_version="sa_llm_stage_b_test"),
        )
        if not trace["stage_a"]["escalate_to_stage_b"]:
            trace["stage_a"]["escalate_to_stage_b"] = True
            trace["stage_a"]["escalation_reasons"] = ["low_confidence"]
        stage_b_trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000007"],
            trace=trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_on_a_llm_test"),
            client=_ScriptedStageBLLMClient(
                round1={
                    role: {
                        "proposal_primary_fqdn": trace["stage_a"]["selected_primary_fqdn"],
                        "proposal_related_fqdns": [],
                        "confidence": 0.86,
                        "rationale": f"{role}: keep",
                        "override_position": "support_stage_a",
                        "override_basis_tags": [],
                    }
                    for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
                }
            ),
        )
        self.assertTrue(stage_b_trace["entered_stage_b"])
        self.assertIn(stage_b_trace["final_decision_source"], {"stage_b"})
        self.assertIn("override_attempted", stage_b_trace["stage_b"]["trust_trace"])
        self.assertIn("sensitive_override_flags", stage_b_trace["stage_b"]["trust_trace"])

    def test_stage_b_packet_includes_stage_a_uncertainty_handoff_and_cards(self) -> None:
        trace = build_stage_a_llm_trace(
            sample=self.samples["formal_dev_000007"],
            snapshot=self.snapshots["formal_dev_000007"],
            resolver=self.resolver,
            client=_HeuristicStageATestClient(),
            config=StageALLMConfig(stage_a_version="sa_llm_stage_b_packet_test"),
        )
        trace["stage_a"]["escalate_to_stage_b"] = True
        trace["stage_a"]["escalation_reasons"] = ["low_confidence", "sibling_granularity_conflict"]
        client = _CapturingScriptedStageBLLMClient(
            round1={
                role: {
                    "proposal_primary_fqdn": trace["stage_a"]["selected_primary_fqdn"],
                    "proposal_related_fqdns": [],
                    "confidence": 0.82,
                    "rationale": f"{role}: keep",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                }
                for role in ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")
            }
        )
        build_stage_b_trace(
            sample=self.samples["formal_dev_000007"],
            trace=trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_packet_capture_test"),
            client=client,
        )
        packet = client.packets[0]
        self.assertIn("semantic_handoff", packet["stage_a"])
        self.assertTrue(packet["stage_a"]["semantic_handoff"]["uncertainty_summary"])
        self.assertIn("competition_view", packet["candidates"][0])
        self.assertIn("positive_evidence_card", packet["candidates"][0])
        self.assertIn("negative_evidence_card", packet["candidates"][0])
        self.assertIn("secondary_recovery_card", packet["candidates"][0])

    def test_role_temperature_can_be_overridden_per_agent(self) -> None:
        config = StageBConfig(
            llm_temperature=0.0,
            domain_expert_temperature=0.2,
            governance_risk_temperature=0.0,
            user_preference_temperature=0.15,
            hierarchy_resolver_temperature=0.25,
        )
        self.assertEqual(_role_temperature("GovernanceRisk", config), 0.0)
        self.assertEqual(_role_temperature("DomainExpert", config), 0.2)
        self.assertEqual(_role_temperature("UserPreference", config), 0.15)
        self.assertEqual(_role_temperature("HierarchyResolver", config), 0.25)

    def test_parallel_vote_collection_preserves_role_order(self) -> None:
        stage_a_trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000007"],
            snapshot=self.snapshots["formal_dev_000007"],
            resolver=self.resolver,
            config=self.stage_a_config,
        )
        client = _DelayedScriptedStageBLLMClient(
            round1={
                "DomainExpert": {
                    "proposal_primary_fqdn": stage_a_trace["stage_a"]["selected_primary_fqdn"],
                    "proposal_related_fqdns": [],
                    "confidence": 0.9,
                    "rationale": "DomainExpert: keep",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                },
                "GovernanceRisk": {
                    "proposal_primary_fqdn": stage_a_trace["stage_a"]["selected_primary_fqdn"],
                    "proposal_related_fqdns": [],
                    "confidence": 0.88,
                    "rationale": "GovernanceRisk: keep",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                },
                "HierarchyResolver": {
                    "proposal_primary_fqdn": stage_a_trace["stage_a"]["selected_primary_fqdn"],
                    "proposal_related_fqdns": [],
                    "confidence": 0.81,
                    "rationale": "HierarchyResolver: keep",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                },
                "UserPreference": {
                    "proposal_primary_fqdn": stage_a_trace["stage_a"]["selected_primary_fqdn"],
                    "proposal_related_fqdns": [],
                    "confidence": 0.8,
                    "rationale": "UserPreference: keep",
                    "override_position": "support_stage_a",
                    "override_basis_tags": [],
                },
            }
        )
        trace = build_stage_b_trace(
            sample=self.samples["formal_dev_000007"],
            trace=stage_a_trace,
            resolver=self.resolver,
            config=StageBConfig(stage_b_version="stage_b_parallel_order_test", parallel_role_calls=True),
            client=client,
        )
        round1_agents = [vote["agent"] for vote in trace["stage_b"]["agent_votes"] if vote["round"] == 1]
        self.assertEqual(round1_agents, ["DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference"])


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class _ScriptedStageBLLMClient:
    provider = "test"
    model = "scripted-stage-b"

    def __init__(self, round1: dict[str, dict], round2: dict[str, dict] | None = None) -> None:
        self._round1 = round1
        self._round2 = round2 or round1

    def adjudicate(self, role_name: str, packet: dict, config: StageBConfig) -> tuple[dict, str]:
        payload = self._round1 if packet["round_index"] == 1 else self._round2
        decision = copy.deepcopy(payload[role_name])
        return decision, json.dumps(decision, ensure_ascii=False)


class _DelayedScriptedStageBLLMClient(_ScriptedStageBLLMClient):
    provider = "test-parallel"
    model = "delayed-scripted-stage-b"

    def adjudicate(self, role_name: str, packet: dict, config: StageBConfig) -> tuple[dict, str]:
        delays = {
            "DomainExpert": 0.04,
            "GovernanceRisk": 0.01,
            "HierarchyResolver": 0.03,
            "UserPreference": 0.02,
        }
        time.sleep(delays[role_name])
        return super().adjudicate(role_name, packet, config)


class _HeuristicStageATestClient:
    provider = "test"
    model = "heuristic-stage-a"

    def adjudicate(self, packet, config):
        ranked = sorted(
            packet["candidates"],
            key=lambda row: (
                1 if row.get("primary_hits") else 0,
                row.get("score_r", 0.0),
                1 if row.get("node_kind") == "base" else 0,
                1 if row.get("node_kind") == "segment" and row.get("scene_hits") else 0,
            ),
            reverse=True,
        )
        primary = ranked[0]["fqdn"] if ranked else None
        related = [
            row["fqdn"]
            for row in ranked
            if row["fqdn"] != primary and row.get("secondary_hits")
        ][: config.max_related]
        judgements = []
        for candidate in packet["candidates"]:
            judgements.append(
                {
                    "fqdn": candidate["fqdn"],
                    "task_fit": 0.9 if candidate.get("primary_hits") else 0.7 if candidate.get("secondary_hits") else 0.2,
                    "primary_fit": 0.95 if candidate["fqdn"] == primary else 0.15,
                    "related_fit": 0.8 if candidate["fqdn"] in related else 0.0,
                    "specificity_judgement": "fit",
                    "risk_mismatch": False,
                    "evidence_for": candidate.get("primary_hits", [])[:2] or candidate.get("secondary_hits", [])[:2],
                    "evidence_against": [],
                }
            )
        decision = {
            "scene_context": " / ".join(packet.get("query_view", {}).get("quoted_segments", [])[:2]),
            "primary_intent": packet.get("query", ""),
            "secondary_intents": list(packet.get("query_view", {}).get("clauses", [])[1:3]),
            "selected_primary_fqdn": primary,
            "selected_related_fqdns": related,
            "candidate_judgements": judgements,
            "confidence": 0.72,
            "escalate_to_stage_b": False,
            "escalation_reasons": [],
            "notes": ["heuristic_test_decision"],
            "primary_rationale": "selected primary best matches the main task",
            "secondary_rationale": "related nodes are reserved for explicit secondary support",
            "uncertainty_summary": "nearest challenger shares partial surface cues",
            "confusion_points": ["sibling_granularity_conflict"],
            "override_sensitivity": "needs_strong_evidence",
            "challenger_notes": [
                {
                    "fqdn": ranked[1]["fqdn"],
                    "note": "nearest challenger is competitive but less directly grounded",
                }
            ] if len(ranked) > 1 else [],
        }
        return decision, json.dumps(decision, ensure_ascii=False)


class _CapturingScriptedStageBLLMClient(_ScriptedStageBLLMClient):
    def __init__(self, round1: dict[str, dict], round2: dict[str, dict] | None = None) -> None:
        super().__init__(round1=round1, round2=round2)
        self.packets: list[dict] = []

    def adjudicate(self, role_name: str, packet: dict, config: StageBConfig) -> tuple[dict, str]:
        self.packets.append(copy.deepcopy(packet))
        return super().adjudicate(role_name, packet, config)


if __name__ == "__main__":
    unittest.main()
