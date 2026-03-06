from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .namespace import NamespaceResolver, RoutingNode, validate_fqdn
from .stage_r import dump_jsonl, load_jsonl


@dataclass
class StageAConfig:
    stage_a_version: str = "sa_v0_20260306"
    temperature: float = 1.0
    confidence_temperature: float = 0.25
    tau: float = 0.30
    delta: float = 0.08
    tau_rel: float = 0.12
    tau_cov: float = 0.50
    m_rel: int = 3
    top_k: int = 5
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "stage_r": 0.30,
            "slot": 0.30,
            "context": 0.15,
            "specificity": 0.10,
            "risk_penalty": 0.10,
            "constraint_penalty": 0.05,
        }
    )


def _softmax(values: list[float], temperature: float) -> list[float]:
    if not values:
        return []
    scaled = [value / max(temperature, 1e-6) for value in values]
    pivot = max(scaled)
    exps = [math.exp(value - pivot) for value in scaled]
    denom = sum(exps)
    return [value / denom for value in exps]


def _context_blob(query: str, context: dict[str, Any] | None) -> str:
    context_text = json.dumps(context or {}, ensure_ascii=False).lower()
    return f"{query.lower()}\n{context_text}"


def _slot_match(node: RoutingNode, semantic_parse: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if node.l1 in semantic_parse.get("domain_hints", []):
        score += 1.0
        reasons.append(f"domain:{node.l1}")
    if node.l2 and node.l2 in semantic_parse.get("capability_hints", []):
        score += 1.2
        reasons.append(f"capability:{node.l2}")
    primary_action = semantic_parse.get("primary_action")
    if primary_action:
        if node.segment is None and primary_action in node.action_tags:
            score += 1.0
            reasons.append(f"action:{primary_action}")
        if node.segment == primary_action:
            score += 1.0
            reasons.append(f"segment_action:{primary_action}")
    target_object = semantic_parse.get("target_object")
    if target_object and target_object in node.object_tags:
        score += 1.2
        reasons.append(f"object:{target_object}")
    if node.segment and node.segment in semantic_parse.get("segment_hints", []):
        score += 1.2
        reasons.append(f"segment:{node.segment}")
    return min(score / 5.6, 1.0), reasons


def _context_fit(node: RoutingNode, query: str, context: dict[str, Any] | None, semantic_parse: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    blob = _context_blob(query, context)
    industry_context = semantic_parse.get("industry_context")
    if industry_context and industry_context in node.industry_tags:
        score += 0.8
        reasons.append(f"industry:{industry_context}")
    elif industry_context == "enterprise_service" and node.l1 in {"gov", "security", "finance", "productivity"}:
        score += 0.5
        reasons.append("industry:enterprise_service_backoff")

    parent_aligned = bool(
        node.l1 in semantic_parse.get("domain_hints", [])
        or (node.l2 and node.l2 in semantic_parse.get("capability_hints", []))
        or (semantic_parse.get("target_object") and semantic_parse.get("target_object") in node.object_tags)
    )
    if node.segment and node.segment in blob and parent_aligned:
        score += 0.8
        reasons.append(f"context_segment:{node.segment}")
    if node.segment == "schedule" and context and context.get("time_window"):
        score += 0.7
        reasons.append("context:time_window")
    if node.l2 == "meeting" and context and context.get("time_window"):
        score += 0.3
        reasons.append("context:meeting_time_window")
    if node.l2 == "hotel" and ("会场" in query or "场馆" in query):
        score += 0.2
        reasons.append("context:venue_nearby")
    return min(score, 1.0), reasons


def _specificity_score(node: RoutingNode, semantic_parse: dict[str, Any]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    segment_hints = set(semantic_parse.get("segment_hints", []))
    has_parent_alignment = bool(
        node.l1 in semantic_parse.get("domain_hints", [])
        or (node.l2 and node.l2 in semantic_parse.get("capability_hints", []))
        or (semantic_parse.get("target_object") and semantic_parse.get("target_object") in node.object_tags)
    )
    if node.segment:
        if node.segment in segment_hints and has_parent_alignment:
            reasons.append("segment_exact")
            return 1.0, reasons
        if node.segment in segment_hints:
            reasons.append("segment_without_parent_alignment")
            return 0.15, reasons
        if node.segment == "schedule" and semantic_parse.get("primary_action") in {"plan", "schedule"}:
            reasons.append("schedule_inferred_from_action")
            return 0.75, reasons
        reasons.append("segment_without_evidence")
        return -0.6, reasons

    if segment_hints and node.allowed_l3 and segment_hints.intersection(set(node.allowed_l3)):
        reasons.append("base_when_segment_available")
        return 0.15, reasons

    if node.l2:
        reasons.append("balanced_l2")
        return 0.60, reasons

    reasons.append("coarse_l1")
    return 0.25, reasons


def _risk_mismatch_penalty(node: RoutingNode, semantic_parse: dict[str, Any]) -> tuple[float, list[str]]:
    risk_flags = semantic_parse.get("risk_flags", [])
    if not risk_flags:
        return 0.0, []

    penalty = 0.0
    reasons: list[str] = []
    if "high_risk_data" in risk_flags and not (node.l1 == "security" and node.l2 in {"compliance", "risk"}):
        penalty = max(penalty, 0.9)
        reasons.append("high_risk_data_mismatch")
    if "regulated_service" in risk_flags and node.l1 not in {"gov", "security"}:
        penalty = max(penalty, 0.7)
        reasons.append("regulated_service_mismatch")
    if "money_related" in risk_flags and node.l1 not in {"finance", "security", "gov"}:
        penalty = max(penalty, 0.45)
        reasons.append("money_domain_mismatch")
    if "identity_related" in risk_flags and node.l1 not in {"security", "gov"}:
        penalty = max(penalty, 0.55)
        reasons.append("identity_domain_mismatch")
    return penalty, reasons


def _constraint_penalty(node: RoutingNode | None, candidate_fqdn: str, candidate_set: set[str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    penalty = 0.0
    if candidate_fqdn not in candidate_set:
        penalty = max(penalty, 1.0)
        reasons.append("not_in_stage_r_candidates")
    if not validate_fqdn(candidate_fqdn):
        penalty = max(penalty, 1.0)
        reasons.append("fqdn_format_invalid")
    if node is None:
        penalty = max(penalty, 1.0)
        reasons.append("unknown_fqdn")
    return penalty, reasons


def _coverage_score(
    node: RoutingNode,
    semantic_parse: dict[str, Any],
    probability: float,
    primary_fqdn: str,
    resolver: NamespaceResolver,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    secondary_intents = set(semantic_parse.get("secondary_intents", []))
    if node.fqdn in secondary_intents:
        reasons.append("secondary_intent_exact")
        return 1.0, reasons
    if node.parent_fqdn and node.parent_fqdn in secondary_intents:
        reasons.append("secondary_intent_parent_match")
        return 0.85, reasons

    primary_parent = resolver.parent_fallback(primary_fqdn)
    if primary_parent and node.fqdn == primary_parent:
        reasons.append("primary_parent_fallback")
        return 0.70, reasons

    if semantic_parse.get("query_markers", {}).get("has_multi_intent_marker") and probability >= 0.20:
        reasons.append("multi_intent_prob")
        return 0.60, reasons

    return 0.0, reasons


def score_stage_a_candidate(
    node: RoutingNode | None,
    candidate: dict[str, Any],
    query: str,
    context: dict[str, Any] | None,
    semantic_parse: dict[str, Any],
    candidate_set: set[str],
    max_stage_r_score: float,
    config: StageAConfig,
) -> dict[str, Any]:
    stage_r_score = candidate["score_r"] / max_stage_r_score if max_stage_r_score else 0.0
    if node is None:
        slot_match = 0.0
        slot_reasons: list[str] = []
        context_fit = 0.0
        context_reasons: list[str] = []
        specificity = -1.0
        specificity_reasons = ["unknown_node"]
        risk_penalty = 1.0
        risk_reasons = ["unknown_node"]
    else:
        slot_match, slot_reasons = _slot_match(node, semantic_parse)
        context_fit, context_reasons = _context_fit(node, query, context, semantic_parse)
        specificity, specificity_reasons = _specificity_score(node, semantic_parse)
        risk_penalty, risk_reasons = _risk_mismatch_penalty(node, semantic_parse)

    constraint_penalty, constraint_reasons = _constraint_penalty(node, candidate["fqdn"], candidate_set)

    score_a = (
        config.weights["stage_r"] * stage_r_score
        + config.weights["slot"] * slot_match
        + config.weights["context"] * context_fit
        + config.weights["specificity"] * specificity
        - config.weights["risk_penalty"] * risk_penalty
        - config.weights["constraint_penalty"] * constraint_penalty
    )

    return {
        "fqdn": candidate["fqdn"],
        "node_kind": node.node_kind if node else "unknown",
        "l1": node.l1 if node else None,
        "l2": node.l2 if node else None,
        "segment": node.segment if node else None,
        "parent_fqdn": node.parent_fqdn if node else None,
        "fallback_to": node.fallback_to if node else None,
        "score_a": round(score_a, 6),
        "components": {
            "S_stage_r": round(stage_r_score, 6),
            "S_slot_match": round(slot_match, 6),
            "S_context_fit": round(context_fit, 6),
            "S_specificity": round(specificity, 6),
            "P_risk_mismatch": round(risk_penalty, 6),
            "P_constraint": round(constraint_penalty, 6),
        },
        "reasons": {
            "slot": slot_reasons,
            "context": context_reasons,
            "specificity": specificity_reasons,
            "risk": risk_reasons,
            "constraint": constraint_reasons,
        },
    }


def run_stage_a(
    sample: dict[str, Any],
    stage_r_trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageAConfig | None = None,
) -> dict[str, Any]:
    config = config or StageAConfig()
    candidate_set = {candidate["fqdn"] for candidate in stage_r_trace.get("fqdn_candidates", [])}
    max_stage_r_score = max((candidate["score_r"] for candidate in stage_r_trace.get("fqdn_candidates", [])), default=1.0)

    scored_candidates = [
        score_stage_a_candidate(
            node=resolver.get_node(candidate["fqdn"]),
            candidate=candidate,
            query=sample["query"],
            context=sample.get("context"),
            semantic_parse=stage_r_trace["semantic_parse"],
            candidate_set=candidate_set,
            max_stage_r_score=max_stage_r_score,
            config=config,
        )
        for candidate in stage_r_trace.get("fqdn_candidates", [])
    ]
    scored_candidates.sort(key=lambda item: (-item["score_a"], item["fqdn"]))

    probabilities = _softmax([item["score_a"] for item in scored_candidates], config.temperature)
    confidence_probs = _softmax([item["score_a"] for item in scored_candidates], config.confidence_temperature)
    for item, probability in zip(scored_candidates, probabilities):
        item["probability"] = round(probability, 6)
    for item, probability in zip(scored_candidates, confidence_probs):
        item["confidence_probability"] = round(probability, 6)

    selected_primary = scored_candidates[0]["fqdn"] if scored_candidates else None
    confidence = confidence_probs[0] if confidence_probs else 0.0
    margin = (confidence_probs[0] - confidence_probs[1]) if len(confidence_probs) >= 2 else confidence

    selected_related: list[str] = []
    top1_node = resolver.get_node(selected_primary) if selected_primary else None
    top1_parent = resolver.parent_fallback(selected_primary) if selected_primary else None
    related_pool: list[tuple[float, float, str]] = []
    for item in scored_candidates[1:]:
        node = resolver.get_node(item["fqdn"])
        coverage_score, coverage_reasons = _coverage_score(
            node=node,
            semantic_parse=stage_r_trace["semantic_parse"],
            probability=item["probability"],
            primary_fqdn=selected_primary,
            resolver=resolver,
        ) if node else (0.0, [])
        item["components"]["S_coverage"] = round(coverage_score, 6)
        item["reasons"]["coverage"] = coverage_reasons
        if item["fqdn"] == selected_primary:
            continue
        effective_tau_rel = config.tau_rel if coverage_score < 0.90 else 0.08
        if item["probability"] < effective_tau_rel:
            continue
        if coverage_score < config.tau_cov:
            continue
        related_pool.append((coverage_score, item["probability"], item["fqdn"]))

    related_pool.sort(key=lambda item: (-item[0], -item[1], item[2]))
    for _, _, fqdn in related_pool[: config.m_rel]:
        selected_related.append(fqdn)

    routing_top_k: list[dict[str, Any]] = []
    for item in scored_candidates[: config.top_k]:
        role = "candidate"
        if item["fqdn"] == selected_primary:
            role = "primary"
        elif item["fqdn"] in selected_related:
            role = "related"
        elif top1_parent and item["fqdn"] == top1_parent:
            role = "fallback"
        elif top1_node and item["fqdn"] in resolver.fallback_chain(top1_node.fqdn):
            role = "fallback"

        routing_top_k.append(
            {
                "fqdn": item["fqdn"],
                "score": item["score_a"],
                "probability": item["probability"],
                "role": role,
            }
        )

    constraint_reasons = []
    if not selected_primary:
        constraint_reasons.append("no_candidate")
    elif selected_primary not in candidate_set:
        constraint_reasons.append("primary_not_in_candidates")
    if selected_primary and not validate_fqdn(selected_primary):
        constraint_reasons.append("primary_fqdn_invalid")
    if selected_primary and not resolver.has_fqdn(selected_primary):
        constraint_reasons.append("primary_unknown")
    constraint_check = {
        "pass": len(constraint_reasons) == 0,
        "reasons": constraint_reasons,
    }

    escalation_reasons: list[str] = []
    if confidence < config.tau:
        escalation_reasons.append("low_confidence")
    if margin < config.delta:
        escalation_reasons.append("small_margin")
    if not constraint_check["pass"]:
        escalation_reasons.append("constraint_failed")
    high_risk_flags = {"regulated_service", "high_risk_data", "identity_related"}
    top1_is_governance = bool(top1_node and top1_node.l1 in {"security", "gov"})
    if high_risk_flags.intersection(set(stage_r_trace["semantic_parse"].get("risk_flags", []))) or top1_is_governance:
        escalation_reasons.append("high_risk")
    if stage_r_trace["semantic_parse"].get("secondary_intents") and not selected_related:
        escalation_reasons.append("multi_intent_conflict")

    return {
        "stage_a_version": config.stage_a_version,
        "temperature": config.temperature,
        "confidence_temperature": config.confidence_temperature,
        "routing_top_k": routing_top_k,
        "candidate_scores": scored_candidates,
        "selected_primary_fqdn": selected_primary,
        "selected_related_fqdns": selected_related,
        "confidence": round(confidence, 6),
        "margin": round(margin, 6),
        "constraint_check": constraint_check,
        "escalate_to_stage_b": bool(escalation_reasons),
        "escalation_reasons": escalation_reasons,
    }


def classify_stage_a_error(
    sample: dict[str, Any],
    stage_r_trace: dict[str, Any],
    stage_a_trace: dict[str, Any],
    resolver: NamespaceResolver,
) -> list[str]:
    buckets: list[str] = []
    gt = sample["ground_truth_fqdn"]
    pred = stage_a_trace["selected_primary_fqdn"]
    candidates = {candidate["fqdn"] for candidate in stage_r_trace.get("fqdn_candidates", [])}
    if gt not in candidates:
        buckets.append("stage_r_miss")
        return buckets

    gt_node = resolver.get_node(gt)
    pred_node = resolver.get_node(pred) if pred else None

    if pred != gt:
        if gt_node and gt_node.segment and resolver.parent_fallback(gt) == pred:
            buckets.append("D1_under_specific")
        elif pred_node and pred_node.segment and resolver.parent_fallback(pred) == gt:
            buckets.append("D0_over_specific")
        elif pred in sample.get("relevant_fqdns", []):
            buckets.append("D2_secondary_bias")
        else:
            buckets.append("D_primary_other")

    relevant = set(sample.get("relevant_fqdns", []))
    if relevant and not relevant.intersection(set(stage_a_trace.get("selected_related_fqdns", []))):
        buckets.append("D2b_related_miss")

    if "high_risk" in sample.get("difficulty_tags", []) and not stage_a_trace.get("escalate_to_stage_b"):
        buckets.append("D3_high_risk_not_escalated")

    return buckets


def evaluate_stage_a_run(
    gold_samples: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    resolver: NamespaceResolver,
    config: StageAConfig | None = None,
    run_id_prefix: str = "stagea",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = config or StageAConfig()
    snapshot_by_id = {snapshot["id"]: snapshot for snapshot in snapshots}
    traces: list[dict[str, Any]] = []

    metrics = {
        "samples": 0,
        "primary_hits": 0,
        "acceptable_hits": 0,
        "related_hits": 0,
        "related_total": 0,
        "escalations": 0,
        "error_buckets": {},
    }

    for sample in gold_samples:
        stage_r_trace = snapshot_by_id[sample["id"]]
        stage_a_trace = run_stage_a(sample=sample, stage_r_trace=stage_r_trace, resolver=resolver, config=config)
        run_id = f"{run_id_prefix}_{sample['id']}"
        trace = {
            "run_id": run_id,
            "sample_id": sample["id"],
            "namespace_version": sample["namespace_version"],
            "stage_r_version": stage_r_trace["stage_r_version"],
            "stage_a_version": config.stage_a_version,
            "stage_r": stage_r_trace,
            "stage_a": stage_a_trace,
        }
        traces.append(trace)

        metrics["samples"] += 1
        if stage_a_trace["selected_primary_fqdn"] == sample["ground_truth_fqdn"]:
            metrics["primary_hits"] += 1
        acceptable = set(sample.get("acceptable_fqdns", [])) or {sample["ground_truth_fqdn"]}
        if stage_a_trace["selected_primary_fqdn"] in acceptable:
            metrics["acceptable_hits"] += 1
        relevant = set(sample.get("relevant_fqdns", []))
        metrics["related_total"] += len(relevant)
        metrics["related_hits"] += len(relevant.intersection(set(stage_a_trace["selected_related_fqdns"])))
        if stage_a_trace["escalate_to_stage_b"]:
            metrics["escalations"] += 1
        for bucket in classify_stage_a_error(sample, stage_r_trace, stage_a_trace, resolver):
            metrics["error_buckets"][bucket] = metrics["error_buckets"].get(bucket, 0) + 1

    sample_count = max(metrics["samples"], 1)
    related_total = max(metrics["related_total"], 1)
    summary = {
        "stage_a_version": config.stage_a_version,
        "samples": metrics["samples"],
        "PrimaryAcc@1": round(metrics["primary_hits"] / sample_count, 4),
        "AcceptablePrimary@1": round(metrics["acceptable_hits"] / sample_count, 4),
        "RelatedRecall": round(metrics["related_hits"] / related_total, 4) if metrics["related_total"] else None,
        "escalation_rate": round(metrics["escalations"] / sample_count, 4),
        "error_buckets": metrics["error_buckets"],
    }
    return traces, summary


def save_stage_a_outputs(
    traces: list[dict[str, Any]],
    summary: dict[str, Any],
    traces_path: str | Path,
    summary_path: str | Path,
) -> None:
    dump_jsonl(traces_path, traces)
    target = Path(summary_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
