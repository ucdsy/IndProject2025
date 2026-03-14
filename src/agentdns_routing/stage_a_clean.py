from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

from .namespace import NamespaceResolver, RoutingNode, validate_fqdn

PUNCT_RE = re.compile(r"[，。！？；：、“”‘’（）()【】《》,.!?:;\"'`\-\[\]{}_/\\\s]+")
CLAUSE_RE = re.compile(r"[。！？!?；;]")
QUOTE_RE = re.compile(r"[“\"「『](.*?)[”\"」』]")
RISK_L1 = {"gov", "security"}


@dataclass(frozen=True)
class StageACleanConfig:
    stage_a_version: str = "sa_clean_v2_20260314"
    routing_top_k: int = 5
    stage_r_weight: float = 0.40
    primary_fit_weight: float = 0.26
    context_fit_weight: float = 0.10
    hierarchy_fit_weight: float = 0.10
    specificity_weight: float = 0.08
    evidence_diversity_weight: float = 0.06
    node_type_weight: float = 0.05
    coarse_parent_penalty_weight: float = 0.26
    secondary_only_penalty: float = 0.10
    weak_segment_penalty: float = 0.12
    scene_only_segment_penalty: float = 0.14
    segment_parent_guard_penalty: float = 0.22
    explicit_cue_guard_penalty: float = 0.26
    segment_secondary_only_multiplier: float = 1.6
    fallback_penalty: float = 0.16
    fallback_relief_child_primary_threshold: float = 0.20
    related_min_score: float = 0.30
    related_gap: float = 0.12
    confidence_threshold: float = 0.62
    margin_threshold: float = 0.08
    high_risk_margin_threshold: float = 0.14
    head_delta_threshold: float = 0.03


def normalize_text(value: str) -> str:
    return PUNCT_RE.sub("", (value or "").lower())


def char_ngrams(text: str, n: int = 3) -> set[str]:
    cleaned = normalize_text(text)
    if len(cleaned) < n:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _exp_norm(value: float, scale: float = 2.0) -> float:
    if value <= 0:
        return 0.0
    return _clip(1.0 - math.exp(-scale * value))


def _context_to_text(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    return " ".join(str(value) for value in context.values() if value is not None)


def _dedupe_texts(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip("，。；; ")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _has_required_cues(text: str, required_cues: tuple[str, ...] | list[str]) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return any(normalize_text(cue) in normalized for cue in required_cues if normalize_text(cue))


def build_query_packet(query: str) -> dict[str, Any]:
    text = query.strip()
    clauses = [part.strip("，。；; ") for part in CLAUSE_RE.split(text) if part.strip("，。；; ")]
    quoted_segments = _dedupe_texts([match.strip() for match in QUOTE_RE.findall(text) if match.strip()])

    scene_parts: list[str] = []
    if len(clauses) >= 2:
        scene_parts.append(clauses[0])
    if quoted_segments:
        scene_parts.append(quoted_segments[0])
    scene_text = " ".join(_dedupe_texts(scene_parts)).strip()

    if len(clauses) >= 2:
        primary_request_text = clauses[1]
    elif clauses:
        primary_request_text = clauses[0]
    else:
        primary_request_text = text

    supplemental_parts = _dedupe_texts(clauses[2:] + quoted_segments[1:])
    return {
        "full_text": text,
        "scene_text": scene_text,
        "primary_request_text": primary_request_text,
        "supplemental_texts": supplemental_parts,
        "clauses": clauses,
        "quoted_segments": quoted_segments,
        "has_structural_multi_intent": len(clauses) >= 3 or len(quoted_segments) >= 2,
    }


def _alias_match_score(text: str, aliases: tuple[str, ...]) -> tuple[float, list[str]]:
    text_norm = normalize_text(text)
    if not text_norm:
        return 0.0, []
    score = 0.0
    hits: list[str] = []
    for alias in aliases:
        alias_norm = normalize_text(alias)
        if not alias_norm or alias_norm not in text_norm:
            continue
        base = min(len(alias_norm), 4) / 4.0
        if len(alias_norm) <= 2:
            base *= 0.85
        score += base
        hits.append(alias)
    return min(score, 1.5), hits


def _desc_match_score(text: str, node: RoutingNode) -> float:
    if not text:
        return 0.0
    desc_text = " ".join([node.desc, *node.aliases])
    return _clip(jaccard(char_ngrams(text, 2), char_ngrams(desc_text, 2)) / 0.05)


def _primary_fit_proxy(record: dict[str, Any]) -> float:
    return _clip(
        0.60 * record["primary_alias_norm"]
        + 0.20 * record["query_alias_stage_r"]
        + 0.15 * record["desc_norm"]
        + 0.05 * record["scene_alias_norm"]
    )


def _evidence_diversity(candidate: dict[str, Any]) -> float:
    sources = [item for item in candidate.get("source", []) if item != "parent_fallback"]
    return _clip(len(set(sources)) / 4.0)


def _chain_members(fqdn: str, resolver: NamespaceResolver) -> set[str]:
    members = {fqdn}
    members.update(resolver.fallback_chain(fqdn))
    node = resolver.get_node(fqdn)
    if node and node.parent_fqdn:
        members.add(node.parent_fqdn)
    return members


def _is_chain_duplicate(primary_fqdn: str, other_fqdn: str, resolver: NamespaceResolver) -> bool:
    if primary_fqdn == other_fqdn:
        return True
    return other_fqdn in _chain_members(primary_fqdn, resolver) or primary_fqdn in _chain_members(other_fqdn, resolver)


def _relationship_bonus(record: dict[str, Any], primary_record: dict[str, Any], selection_signals: dict[str, Any], confusion_sources: set[str]) -> float:
    if record["fqdn"] == primary_record["fqdn"]:
        return 0.0
    if record.get("parent_fqdn") and record.get("parent_fqdn") == primary_record.get("parent_fqdn"):
        return 0.9
    if "C4_governance_fallback" in confusion_sources and record.get("l1") in RISK_L1:
        return 0.55
    return 0.0


def _safe_primary(record: dict[str, Any]) -> bool:
    return validate_fqdn(record["fqdn"])


def analyze_stage_a(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageACleanConfig | None = None,
) -> dict[str, Any]:
    config = config or StageACleanConfig()
    query_packet = build_query_packet(sample.get("query", ""))
    candidates = snapshot.get("fqdn_candidates", [])
    if not candidates:
        return {
            "selected_primary_fqdn": None,
            "selected_related_fqdns": [],
            "confidence": 0.0,
            "margin": 0.0,
            "routing_top_k": [],
            "constraint_check": {"pass": False, "reasons": ["empty_candidates"]},
            "escalate_to_stage_b": True,
            "escalation_reasons": ["empty_candidates"],
            "candidate_scores": [],
            "score_breakdown": {},
            "query_packet": query_packet,
        }

    top_stage_r = max(candidate.get("score_r", 0.0) for candidate in candidates) or 1.0
    context_text = _context_to_text(sample.get("context"))
    selection_signals = snapshot.get("semantic_parse", {}).get("selection_signals", {})
    structural_multi_intent_signal = bool(
        selection_signals.get("has_multi_intent_signal") or query_packet.get("has_structural_multi_intent")
    )
    confusion_sources = set(snapshot.get("confusion_sources", []))
    selection_signals = {
        **selection_signals,
        "has_multi_intent_signal": structural_multi_intent_signal,
    }

    records: list[dict[str, Any]] = []
    by_parent: dict[str, list[dict[str, Any]]] = {}

    for candidate in candidates:
        node = resolver.get_node(candidate["fqdn"])
        if not node:
            continue
        components = candidate.get("components", {})
        primary_alias_raw, primary_hits = _alias_match_score(query_packet["primary_request_text"], node.aliases)
        secondary_alias_raw = 0.0
        supplemental_desc_norm = 0.0
        secondary_hits: list[str] = []
        for text in query_packet["supplemental_texts"]:
            score, hits = _alias_match_score(text, node.aliases)
            secondary_alias_raw = max(secondary_alias_raw, score)
            supplemental_desc_norm = max(supplemental_desc_norm, _desc_match_score(text, node))
            for hit in hits:
                if hit not in secondary_hits:
                    secondary_hits.append(hit)
        scene_alias_raw, scene_hits = _alias_match_score(query_packet["scene_text"], node.aliases)

        primary_alias_norm = _exp_norm(primary_alias_raw)
        secondary_alias_norm = _exp_norm(secondary_alias_raw)
        supplemental_desc_norm = _clip(supplemental_desc_norm / 0.9)
        secondary_support_norm = max(secondary_alias_norm, 0.85 * supplemental_desc_norm)
        scene_alias_norm = _exp_norm(scene_alias_raw)
        stage_r_alias_norm = _exp_norm(float(components.get("query_alias_score", 0.0)), scale=1.5)
        desc_norm = _clip(max(float(components.get("desc_similarity", 0.0)), _desc_match_score(query_packet["primary_request_text"], node)) / 0.05)
        context_norm = _clip(float(components.get("context_score", 0.0)) / 0.9)
        score_r_norm = _clip(float(candidate.get("score_r", 0.0)) / top_stage_r)
        record = {
            "fqdn": candidate["fqdn"],
            "node_kind": candidate.get("node_kind"),
            "l1": candidate.get("l1"),
            "l2": candidate.get("l2"),
            "segment": candidate.get("segment"),
            "parent_fqdn": candidate.get("parent_fqdn"),
            "fallback_to": candidate.get("fallback_to"),
            "score_r": float(candidate.get("score_r", 0.0)),
            "score_r_norm": score_r_norm,
            "query_alias_stage_r": stage_r_alias_norm,
            "primary_alias_norm": primary_alias_norm,
            "secondary_alias_norm": secondary_alias_norm,
            "supplemental_desc_norm": supplemental_desc_norm,
            "secondary_support_norm": secondary_support_norm,
            "scene_alias_norm": scene_alias_norm,
            "desc_norm": desc_norm,
            "context_norm": context_norm,
            "evidence_diversity": _evidence_diversity(candidate),
            "source": list(candidate.get("source", [])),
            "components": components,
            "matched_phrases": candidate.get("matched_phrases", {}),
            "primary_hits": primary_hits,
            "secondary_hits": secondary_hits,
            "scene_hits": scene_hits,
            "routing_constraints": dict(node.routing_constraints),
        }
        records.append(record)
        if record["parent_fqdn"]:
            by_parent.setdefault(record["parent_fqdn"], []).append(record)

    for record in records:
        primary_alias_norm = record["primary_alias_norm"]
        secondary_alias_norm = record["secondary_alias_norm"]
        secondary_support_norm = record["secondary_support_norm"]
        scene_alias_norm = record["scene_alias_norm"]
        desc_norm = record["desc_norm"]
        if record["node_kind"] == "segment":
            parent_score = 0.0
            parent_primary_proxy = 0.0
            if record["parent_fqdn"]:
                parent = next((item for item in records if item["fqdn"] == record["parent_fqdn"]), None)
                if parent:
                    parent_score = parent["score_r_norm"]
                    parent_primary_proxy = _primary_fit_proxy(parent)
            hierarchy_fit = parent_score
            specificity_fit = _clip(
                0.65 * primary_alias_norm
                + 0.30 * secondary_support_norm
                + 0.20 * scene_alias_norm
                + 0.35 * parent_score
            )
            node_type_fit = 1.0 if primary_alias_norm > 0 else 0.7 if secondary_alias_norm > 0 else 0.35
            coarse_parent_penalty = 0.0
            weak_segment_penalty = (
                config.weak_segment_penalty
                if primary_alias_norm == 0.0 and secondary_support_norm == 0.0 and desc_norm < 0.35
                else 0.0
            )
            scene_only_segment_penalty = (
                config.scene_only_segment_penalty
                if primary_alias_norm == 0.0 and secondary_support_norm == 0.0 and scene_alias_norm > 0.0
                else 0.0
            )
            segment_parent_guard_penalty = (
                config.segment_parent_guard_penalty
                if primary_alias_norm == 0.0
                and secondary_support_norm < 0.15
                and scene_alias_norm > 0.0
                and parent_primary_proxy >= 0.35
                else 0.0
            )
            routing_constraints = record.get("routing_constraints", {})
            required_cues = tuple(routing_constraints.get("requires_explicit_primary_cues", []))
            generic_trigger_aliases = set(routing_constraints.get("generic_trigger_aliases", []))
            explicit_cue_guard_penalty = (
                config.explicit_cue_guard_penalty
                if required_cues
                and generic_trigger_aliases
                and primary_alias_norm > 0.0
                and bool(record.get("primary_hits"))
                and set(record.get("primary_hits", [])) <= generic_trigger_aliases
                and not _has_required_cues(query_packet["primary_request_text"], required_cues)
                and parent_primary_proxy >= 0.35
                else 0.0
            )
        else:
            children = by_parent.get(record["fqdn"], [])
            child_primary_support = max((child["primary_alias_norm"] for child in children), default=0.0)
            child_secondary_support = max((child["secondary_alias_norm"] for child in children), default=0.0)
            hierarchy_fit = _clip(child_primary_support + 0.5 * child_secondary_support)
            specificity_fit = 0.85 if child_primary_support < 0.20 else 0.25
            node_type_fit = 0.85 if record["node_kind"] == "base" else 0.5
            coarse_parent_penalty = config.coarse_parent_penalty_weight * (0.8 * child_primary_support + 0.5 * child_secondary_support)
            weak_segment_penalty = 0.0
            scene_only_segment_penalty = 0.0
            segment_parent_guard_penalty = 0.0
            explicit_cue_guard_penalty = 0.0
            record["child_primary_support"] = child_primary_support
            record["child_secondary_support"] = child_secondary_support

        primary_fit = _clip(
            0.60 * primary_alias_norm
            + 0.20 * stage_r_alias_norm
            + 0.15 * desc_norm
            + 0.05 * scene_alias_norm
        )
        fallback_penalty = config.fallback_penalty if record["source"] == ["parent_fallback"] else 0.0
        if record["source"] == ["parent_fallback"]:
            child_primary_support = record.get("child_primary_support", 0.0)
            if child_primary_support < config.fallback_relief_child_primary_threshold or primary_fit >= 0.35:
                fallback_penalty = 0.0
        secondary_only_penalty = (
            config.secondary_only_penalty * (config.segment_secondary_only_multiplier if record["node_kind"] == "segment" else 1.0)
            if primary_alias_norm == 0.0 and secondary_support_norm > 0.0
            else 0.0
        )

        score_a = (
            config.stage_r_weight * record["score_r_norm"]
            + config.primary_fit_weight * primary_fit
            + config.context_fit_weight * record["context_norm"]
            + config.hierarchy_fit_weight * hierarchy_fit
            + config.specificity_weight * specificity_fit
            + config.evidence_diversity_weight * record["evidence_diversity"]
            + config.node_type_weight * node_type_fit
            - coarse_parent_penalty
            - secondary_only_penalty
            - weak_segment_penalty
            - scene_only_segment_penalty
            - segment_parent_guard_penalty
            - explicit_cue_guard_penalty
            - fallback_penalty
        )

        record.update(
            {
                "primary_fit": primary_fit,
                "hierarchy_fit": hierarchy_fit,
                "specificity_fit": specificity_fit,
                "node_type_fit": node_type_fit,
                "coarse_parent_penalty": coarse_parent_penalty,
                "secondary_only_penalty": secondary_only_penalty,
                "weak_segment_penalty": weak_segment_penalty,
                "scene_only_segment_penalty": scene_only_segment_penalty,
                "segment_parent_guard_penalty": segment_parent_guard_penalty,
                "explicit_cue_guard_penalty": explicit_cue_guard_penalty,
                "fallback_penalty": fallback_penalty,
                "score_a": round(score_a, 6),
            }
        )

    records.sort(key=lambda item: (item["score_a"], item["score_r"]), reverse=True)
    primary = records[0]

    for record in records:
        record["relationship_bonus"] = _relationship_bonus(record, primary, selection_signals, confusion_sources)
        record["score_related"] = round(
            0.35 * record["score_r_norm"]
            + 0.18 * max(record["secondary_alias_norm"], 0.60 * record["primary_alias_norm"])
            + 0.14 * record["supplemental_desc_norm"]
            + 0.08 * record["context_norm"]
            + 0.10 * record["evidence_diversity"]
            + 0.15 * record["relationship_bonus"]
            - (0.18 if _is_chain_duplicate(primary["fqdn"], record["fqdn"], resolver) and record["fqdn"] != primary["fqdn"] else 0.0),
            6,
        )

    related_candidates: list[dict[str, Any]] = []
    for record in records[1:]:
        if _is_chain_duplicate(primary["fqdn"], record["fqdn"], resolver):
            continue
        parent_related_support_ok = True
        if record["node_kind"] == "segment" and record.get("parent_fqdn"):
            parent_record = next((item for item in records if item["fqdn"] == record["parent_fqdn"]), None)
            if parent_record and parent_record["score_r_norm"] < 0.25 and parent_record["score_a"] < 0.25:
                parent_related_support_ok = False
        has_explicit_secondary_signal = bool(record["secondary_hits"]) or (
            structural_multi_intent_signal
            and record["supplemental_desc_norm"] >= 0.55
            and (
                (
                    record.get("l1") == primary.get("l1")
                    and record.get("l2") != primary.get("l2")
                )
                or selection_signals.get("has_cross_domain_competition")
            )
        )
        if not has_explicit_secondary_signal or not parent_related_support_ok:
            continue
        if record["score_related"] < config.related_min_score and record["score_a"] < primary["score_a"] - config.related_gap:
            continue
        related_candidates.append(record)

    related: list[str] = []
    related_candidates.sort(
        key=lambda item: (
            item["score_related"],
            1 if item.get("node_kind") == "segment" else 0,
            item["score_a"],
        ),
        reverse=True,
    )
    for record in related_candidates:
        if any(_is_chain_duplicate(existing, record["fqdn"], resolver) for existing in related):
            continue
        related.append(record["fqdn"])

    competitive_records = [record for record in records if not _is_chain_duplicate(primary["fqdn"], record["fqdn"], resolver) or record["fqdn"] == primary["fqdn"]]
    best_competitor = competitive_records[1] if len(competitive_records) > 1 else None
    margin = primary["score_a"] - best_competitor["score_a"] if best_competitor else primary["score_a"]
    confidence = _clip(0.72 * primary["score_a"] + 0.28 * margin)

    escalation_reasons: list[str] = []
    if confidence < config.confidence_threshold:
        escalation_reasons.append("low_confidence")
    if margin < config.margin_threshold:
        escalation_reasons.append("small_margin")
    if selection_signals.get("head_score_delta") is not None and selection_signals["head_score_delta"] < config.head_delta_threshold:
        escalation_reasons.append("close_score_delta")
    if primary.get("l1") in RISK_L1 and (margin < config.high_risk_margin_threshold or "C4_governance_fallback" in confusion_sources):
        escalation_reasons.append("high_risk")
    if structural_multi_intent_signal and not related:
        escalation_reasons.append("multi_intent_conflict")

    routing_top_k: list[dict[str, Any]] = []
    for record in records[: config.routing_top_k]:
        if record["fqdn"] == primary["fqdn"]:
            role = "primary"
        elif record["fqdn"] in related:
            role = "related"
        elif _is_chain_duplicate(primary["fqdn"], record["fqdn"], resolver):
            role = "fallback"
        else:
            role = "distractor"
        routing_top_k.append(
            {
                "fqdn": record["fqdn"],
                "score_a": round(record["score_a"], 6),
                "score_related": round(record["score_related"], 6),
                "role": role,
                "node_kind": record.get("node_kind"),
                "l1": record.get("l1"),
                "l2": record.get("l2"),
                "segment": record.get("segment"),
            }
        )

    constraint_reasons: list[str] = []
    if not _safe_primary(primary):
        constraint_reasons.append("invalid_primary_fqdn")
    candidate_fqdns = {record["fqdn"] for record in records}
    if primary["fqdn"] not in candidate_fqdns:
        constraint_reasons.append("primary_not_in_candidates")
    invalid_related = [fqdn for fqdn in related if fqdn not in candidate_fqdns]
    if invalid_related:
        constraint_reasons.append("related_not_in_candidates")

    return {
        "selected_primary_fqdn": primary["fqdn"],
        "selected_related_fqdns": related,
        "confidence": round(confidence, 6),
        "margin": round(margin, 6),
        "routing_top_k": routing_top_k,
        "constraint_check": {
            "pass": not constraint_reasons,
            "reasons": constraint_reasons,
        },
        "escalate_to_stage_b": bool(escalation_reasons or constraint_reasons),
        "escalation_reasons": sorted(set(escalation_reasons + constraint_reasons)),
        "candidate_scores": [
            {
                "fqdn": record["fqdn"],
                "score_a": round(record["score_a"], 6),
                "score_related": round(record["score_related"], 6),
                "score_breakdown": {
                    "score_r_norm": round(record["score_r_norm"], 6),
                    "primary_fit": round(record["primary_fit"], 6),
                    "context_fit": round(record["context_norm"], 6),
                    "hierarchy_fit": round(record["hierarchy_fit"], 6),
                    "specificity_fit": round(record["specificity_fit"], 6),
                    "evidence_diversity": round(record["evidence_diversity"], 6),
                    "node_type_fit": round(record["node_type_fit"], 6),
                    "coarse_parent_penalty": round(record["coarse_parent_penalty"], 6),
                    "secondary_only_penalty": round(record["secondary_only_penalty"], 6),
                    "weak_segment_penalty": round(record["weak_segment_penalty"], 6),
                    "scene_only_segment_penalty": round(record["scene_only_segment_penalty"], 6),
                    "segment_parent_guard_penalty": round(record["segment_parent_guard_penalty"], 6),
                    "explicit_cue_guard_penalty": round(record["explicit_cue_guard_penalty"], 6),
                    "fallback_penalty": round(record["fallback_penalty"], 6),
                    "relationship_bonus": round(record["relationship_bonus"], 6),
                },
                "evidence_for": {
                    "primary_hits": record["primary_hits"],
                    "secondary_hits": record["secondary_hits"],
                    "scene_hits": record["scene_hits"],
                    "matched_phrases": record["matched_phrases"],
                },
            }
            for record in records
        ],
        "score_breakdown": {
            "primary_fqdn": primary["fqdn"],
            "primary_score": round(primary["score_a"], 6),
            "best_competitor_fqdn": best_competitor["fqdn"] if best_competitor else None,
            "best_competitor_score": round(best_competitor["score_a"], 6) if best_competitor else None,
        },
        "query_packet": query_packet,
    }


def build_routing_run_trace(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageACleanConfig | None = None,
) -> dict[str, Any]:
    config = config or StageACleanConfig()
    stage_a = analyze_stage_a(sample=sample, snapshot=snapshot, resolver=resolver, config=config)
    return {
        "run_id": f"run_{config.stage_a_version}_{sample['id']}_{uuid.uuid4().hex[:8]}",
        "sample_id": sample["id"],
        "namespace_version": snapshot["namespace_version"],
        "stage_r_version": snapshot["stage_r_version"],
        "stage_a_version": config.stage_a_version,
        "stage_r": snapshot,
        "stage_a": stage_a,
    }
