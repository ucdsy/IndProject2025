from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from .namespace import NamespaceResolver, validate_fqdn
from .related_v2 import (
    RelatedV2Config,
    RelatedV2LLMClient,
    _clip,
    _coerce_short_label_list,
    _coerce_short_text,
    _dedupe_texts,
    _is_chain_duplicate,
    _load_json_object,
    _safe_float,
    _secondary_intent_bundle,
    _stage_a_semantic_handoff,
    _build_related_candidates,
)


@dataclass(frozen=True)
class RelatedV3SemanticConfig:
    related_version: str = "related_v3_semantic_20260411"
    base_config: RelatedV2Config = RelatedV2Config()
    llm_candidate_limit: int = 8
    max_related: int = 3
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1200
    llm_related_min_confidence: float = 0.22


def _semantic_system_prompt() -> str:
    return (
        "你是 AgentDNS related semantic adjudicator。"
        "你的任务是基于完整原始 query，在给定候选集合中找出除 finalized primary 之外、仍然作为独立次主题成立的能力。"
        "请优先依赖完整 query 的语义，不要过度依赖候选上的预评分。"
        "只有当某个 candidate 对应 query 中额外成立的意图/主题时，才能标记为 related。"
        "如果某候选只是 primary 的重复、同义变体、层级重复，或者更像 primary challenger，请 reject。"
        "你只能从 candidates 中选择，不能发明新的 fqdn。"
        "输出必须是单个 JSON 对象。"
    )


def _semantic_user_prompt(packet: dict[str, Any]) -> str:
    return (
        "请阅读下面的完整 query 与候选集合，直接判断哪些 candidate 是 related。\n"
        "要求：\n"
        "1. 不要先把 query 过度压缩成很多中间结构，直接在完整 query 语境下判断。\n"
        "2. related 必须是 finalized primary 之外，仍然作为独立次主题成立的能力。\n"
        "3. 如果候选只是 primary duplicate / primary challenger / scene-only association，请 reject。\n"
        "4. 输出字段：selected_related_fqdns, confidence, related_rationale, confusion_points, candidate_decisions。\n"
        "5. candidate_decisions 为对象列表，每项包含 fqdn / decision / reason / supporting_span；decision 只能是 related 或 reject。\n"
        "6. selected_related_fqdns 只能来自 candidates，且不能包含 finalized_primary_fqdn。\n\n"
        f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
    )


def _build_semantic_packet(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str,
    bundle: dict[str, Any],
    records: list[dict[str, Any]],
    config: RelatedV3SemanticConfig,
) -> dict[str, Any]:
    primary_node = resolver.get_node(primary_fqdn)
    candidates: list[dict[str, Any]] = []
    for row in records[: config.llm_candidate_limit]:
        node = resolver.get_node(row["fqdn"])
        candidates.append(
            {
                "fqdn": row["fqdn"],
                "desc": node.desc if node else "",
                "aliases": list(node.aliases[:5]) if node else [],
                "l1": row["l1"],
                "l2": row["l2"],
                "segment": row["segment"],
                "candidate_sources": row["builder_sources"],
                "cross_l1": row["cross_l1"],
                "likely_primary_challenger": row["likely_primary_challenger"],
                "stage_r_present": row["stage_r_present"],
                "is_high_risk": row["is_high_risk"],
            }
        )
    return {
        "sample_id": sample.get("id"),
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "finalized_primary_fqdn": primary_fqdn,
        "finalized_primary_desc": primary_node.desc if primary_node else "",
        "query_packet": bundle["query_packet"],
        "secondary_hints": bundle["secondary_intents"],
        "stage_a_semantic_handoff": _stage_a_semantic_handoff(trace),
        "hard_rules": [
            "selected_related_fqdns must come from candidates",
            "selected_related_fqdns must not contain finalized_primary_fqdn",
            "do not select obvious primary duplicates or primary challengers",
        ],
        "candidates": candidates,
    }


def _sanitize_semantic_decision(raw: dict[str, Any], candidate_fqdns: list[str]) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    candidate_set = set(candidate_fqdns)

    raw_selected = raw.get("selected_related_fqdns", [])
    if isinstance(raw_selected, str):
        raw_selected = [raw_selected]
    elif not isinstance(raw_selected, list):
        raw_selected = []
        issues.append("semantic_selection_not_list")

    selected: list[str] = []
    for fqdn in raw_selected:
        if fqdn in candidate_set and fqdn not in selected:
            selected.append(fqdn)
        elif fqdn not in candidate_set:
            issues.append("semantic_selection_not_in_candidates")

    raw_decisions = raw.get("candidate_decisions", [])
    if isinstance(raw_decisions, dict):
        raw_decisions = [{"fqdn": fqdn, **note} for fqdn, note in raw_decisions.items() if isinstance(note, dict)]
    elif not isinstance(raw_decisions, list):
        raw_decisions = []

    candidate_decisions: list[dict[str, str]] = []
    derived_selected: list[str] = []
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        fqdn = item.get("fqdn")
        decision = str(item.get("decision", "")).strip().lower()
        if fqdn not in candidate_set or decision not in {"related", "reject"}:
            continue
        reason = _coerce_short_text(item.get("reason", ""), limit=180)
        supporting_span = _coerce_short_text(item.get("supporting_span", ""), limit=80)
        row = {
            "fqdn": fqdn,
            "decision": decision,
            "reason": reason,
            "supporting_span": supporting_span,
        }
        candidate_decisions.append(row)
        if decision == "related" and fqdn not in derived_selected:
            derived_selected.append(fqdn)
        if len(candidate_decisions) >= 12:
            break

    if not selected and derived_selected:
        selected = derived_selected

    return (
        {
            "selected_related_fqdns": selected,
            "confidence": _safe_float(raw.get("confidence", 0.0)),
            "related_rationale": _coerce_short_text(raw.get("related_rationale", ""), limit=260),
            "confusion_points": _coerce_short_label_list(raw.get("confusion_points", []), limit=6),
            "candidate_decisions": candidate_decisions,
        },
        issues,
    )


def _apply_minimal_guardrails(
    records: list[dict[str, Any]],
    proposed: list[str],
    primary_fqdn: str,
    resolver: NamespaceResolver,
    config: RelatedV3SemanticConfig,
) -> tuple[list[str], list[str], list[str]]:
    record_map = {row["fqdn"]: row for row in records}
    kept: list[str] = []
    notes: list[str] = []
    confusion_points: list[str] = []
    for fqdn in proposed:
        row = record_map.get(fqdn)
        if not row:
            continue
        if _is_chain_duplicate(primary_fqdn, fqdn, resolver):
            notes.append(f"guard_drop:{fqdn}:chain_duplicate")
            confusion_points.append("chain_duplicate_related")
            continue
        if any(_is_chain_duplicate(existing, fqdn, resolver) for existing in kept):
            notes.append(f"guard_drop:{fqdn}:duplicate_related_chain")
            continue
        if row["likely_primary_challenger"] and not row["stage_a_related_prior"] and not row["stage_b_related_prior"]:
            notes.append(f"guard_drop:{fqdn}:primary_challenger")
            confusion_points.append("primary_challenger_overlap")
            continue
        kept.append(fqdn)
        if len(kept) >= config.max_related:
            break
    return kept, notes, sorted(set(confusion_points))


def analyze_related_v3_semantic(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str | None = None,
    config: RelatedV3SemanticConfig | None = None,
    client: RelatedV2LLMClient | None = None,
) -> dict[str, Any]:
    config = config or RelatedV3SemanticConfig()
    primary_fqdn = primary_fqdn or trace.get("final_primary_fqdn") or trace.get("stage_a", {}).get("selected_primary_fqdn")
    if not primary_fqdn or not validate_fqdn(primary_fqdn):
        return {
            "related_version": config.related_version,
            "selected_related_fqdns": [],
            "final_related_fqdns": [],
            "related_confidence": 0.0,
            "related_candidates": [],
            "decision_source": "related_v3_semantic",
            "review": {"triggered": False, "review_reasons": ["invalid_primary"], "review_notes": []},
            "execution": {"prefetch_reused": False, "reran_after_primary_override": False},
        }

    bundle = _secondary_intent_bundle(sample=sample, trace=trace, primary_fqdn=primary_fqdn, resolver=resolver)
    records = _build_related_candidates(
        sample=sample,
        trace=trace,
        resolver=resolver,
        primary_fqdn=primary_fqdn,
        bundle=bundle,
        config=config.base_config,
    )

    packet = _build_semantic_packet(
        sample=sample,
        trace=trace,
        resolver=resolver,
        primary_fqdn=primary_fqdn,
        bundle=bundle,
        records=records,
        config=config,
    )

    if client is None:
        raise ValueError("related_v3_semantic requires an LLM client")

    raw_decision, raw_text = client.adjudicate_related(packet, config.base_config)
    llm_decision, llm_issues = _sanitize_semantic_decision(raw_decision, [row["fqdn"] for row in records])
    selected, guard_notes, guard_confusion = _apply_minimal_guardrails(
        records=records,
        proposed=llm_decision["selected_related_fqdns"],
        primary_fqdn=primary_fqdn,
        resolver=resolver,
        config=config,
    )

    confidence = 0.0
    if selected:
        confidence = round(_clip(llm_decision["confidence"]), 6)

    return {
        "related_version": config.related_version,
        "primary_fqdn": primary_fqdn,
        "secondary_intents": bundle["secondary_intents"],
        "primary_secondary_split": bundle["primary_secondary_split"],
        "has_multi_intent_signal": bundle["has_multi_intent_signal"],
        "candidate_count": len(records),
        "related_candidates": records,
        "selected_related_fqdns": selected,
        "final_related_fqdns": selected,
        "related_confidence": confidence,
        "confusion_points": sorted(set(llm_decision["confusion_points"] + guard_confusion)),
        "selection_notes": [f"semantic_select:{fqdn}" for fqdn in llm_decision["selected_related_fqdns"]],
        "decision_source": "related_v3_semantic",
        "review": {
            "triggered": False,
            "review_reasons": sorted(set(llm_decision["confusion_points"] + guard_confusion + llm_issues)),
            "review_notes": guard_notes,
        },
        "llm_trace": {
            "provider": client.provider,
            "model": client.model,
            "packet": packet,
            "decision": llm_decision,
            "raw_response": raw_text,
            "issues": llm_issues,
        },
        "execution": {"prefetch_reused": False, "reran_after_primary_override": False},
    }


def attach_related_v3_semantic_final_fields(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: RelatedV3SemanticConfig | None = None,
    client: RelatedV2LLMClient | None = None,
) -> dict[str, Any]:
    config = config or RelatedV3SemanticConfig()
    final_primary = trace.get("final_primary_fqdn") or trace.get("stage_a", {}).get("selected_primary_fqdn")
    related_result = analyze_related_v3_semantic(
        sample=sample,
        trace=trace,
        resolver=resolver,
        primary_fqdn=final_primary,
        config=config,
        client=client,
    )
    updated = copy.deepcopy(trace)
    updated["related_v3_semantic_version"] = config.related_version
    updated["related_v3_semantic"] = related_result
    updated["legacy_final_related_fqdns"] = list(updated.get("final_related_fqdns", []))
    updated["final_related_fqdns"] = list(related_result.get("final_related_fqdns", []))
    updated["final_related_source"] = related_result.get("decision_source", "related_v3_semantic")
    return updated


def load_related_v3_semantic_response(text: str) -> dict[str, Any]:
    return _load_json_object(text)
