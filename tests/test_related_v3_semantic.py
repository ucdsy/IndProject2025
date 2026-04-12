from __future__ import annotations

import unittest
from pathlib import Path

from src.agentdns_routing.namespace import NamespaceResolver
from src.agentdns_routing.related_v3_semantic import (
    RelatedV3SemanticConfig,
    analyze_related_v3_semantic,
    attach_related_v3_semantic_final_fields,
)
from src.agentdns_routing.stage_a_clean import StageACleanConfig, build_routing_run_trace
from src.agentdns_routing.stage_a_eval import evaluate_traces

ROOT = Path(__file__).resolve().parents[1]


class RelatedV3SemanticTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.resolver = NamespaceResolver.from_jsonl(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl")
        cls.samples = {row["id"]: row for row in _load_jsonl(ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl")}
        cls.snapshots = {row["id"]: row for row in _load_jsonl(ROOT / "artifacts" / "stage_r_clean" / "dev.sr_clean_v1_20260307.jsonl")}
        cls.stage_a_config = StageACleanConfig(stage_a_version="sa_clean_related_v3_semantic_test")
        cls.semantic_config = RelatedV3SemanticConfig(related_version="related_v3_semantic_test")

    def test_semantic_adjudication_uses_candidate_decisions(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            with_related_v2=False,
        )
        result = analyze_related_v3_semantic(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            config=self.semantic_config,
            client=_ScriptedSemanticClient(
                {
                    "selected_related_fqdns": [],
                    "confidence": 0.78,
                    "related_rationale": "完整 query 明确包含待办这个次主题。",
                    "confusion_points": [],
                    "candidate_decisions": [
                        {
                            "fqdn": "action-items.meeting.productivity.cn",
                            "decision": "related",
                            "reason": "待办项是 query 中额外成立的主题。",
                            "supporting_span": "把待办项也列出来",
                        },
                        {
                            "fqdn": "summary.meeting.productivity.cn",
                            "decision": "reject",
                            "reason": "这更像主意图的同链路补充。",
                            "supporting_span": "",
                        },
                    ],
                }
            ),
        )
        self.assertEqual(result["decision_source"], "related_v3_semantic")
        self.assertEqual(result["final_related_fqdns"], ["action-items.meeting.productivity.cn"])
        self.assertEqual(result["llm_trace"]["decision"]["candidate_decisions"][0]["decision"], "related")

    def test_semantic_attach_updates_final_related_fields(self) -> None:
        trace = build_routing_run_trace(
            sample=self.samples["formal_dev_000024"],
            snapshot=self.snapshots["formal_dev_000024"],
            resolver=self.resolver,
            config=self.stage_a_config,
            with_related_v2=False,
        )
        finalized = attach_related_v3_semantic_final_fields(
            sample=self.samples["formal_dev_000024"],
            trace=trace,
            resolver=self.resolver,
            config=self.semantic_config,
            client=_ScriptedSemanticClient(
                {
                    "selected_related_fqdns": ["action-items.meeting.productivity.cn"],
                    "confidence": 0.72,
                    "related_rationale": "待办项是 query 中的独立次主题。",
                    "confusion_points": [],
                    "candidate_decisions": [
                        {
                            "fqdn": "action-items.meeting.productivity.cn",
                            "decision": "related",
                            "reason": "直接对上 query 的次主题。",
                            "supporting_span": "把待办项也列出来",
                        }
                    ],
                }
            ),
        )
        self.assertEqual(finalized["final_related_source"], "related_v3_semantic")
        self.assertEqual(finalized["final_related_fqdns"], ["action-items.meeting.productivity.cn"])
        summary = evaluate_traces([self.samples["formal_dev_000024"]], [finalized])
        self.assertEqual(summary["RelatedRecall"], 1.0)
        self.assertEqual(summary["RelatedPrecision"], 1.0)


class _ScriptedSemanticClient:
    provider = "scripted"
    model = "scripted-semantic"

    def __init__(self, response: dict) -> None:
        self._response = response

    def adjudicate_related(self, packet: dict, config) -> tuple[dict, str]:
        return self._response, ""


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(__import__("json").loads(line))
    return rows
