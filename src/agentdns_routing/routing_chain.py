from __future__ import annotations

from collections import Counter
from typing import Any


def infer_stage_a_source(trace: dict[str, Any]) -> str:
    stage_a = trace.get("stage_a", {})
    if stage_a.get("llm_provider") or stage_a.get("llm_decision") or stage_a.get("decision_packet"):
        return "stage_a_llm"
    return "stage_a_clean"


def attach_stage_a_final_fields(trace: dict[str, Any], source: str | None = None) -> dict[str, Any]:
    stage_a = trace["stage_a"]
    trace["entered_stage_b"] = False
    trace["final_primary_fqdn"] = stage_a.get("selected_primary_fqdn")
    trace["final_related_fqdns"] = list(stage_a.get("selected_related_fqdns", []))
    trace["final_decision_source"] = source or infer_stage_a_source(trace)
    return trace


def attach_stage_b_final_fields(trace: dict[str, Any]) -> dict[str, Any]:
    stage_a = trace["stage_a"]
    stage_b = trace.get("stage_b") or {}
    entered_stage_b = bool(stage_a.get("escalate_to_stage_b"))
    trace["entered_stage_b"] = entered_stage_b
    if entered_stage_b and stage_b:
        trace["final_primary_fqdn"] = stage_b.get("final_primary_fqdn", stage_b.get("selected_primary_fqdn"))
        trace["final_related_fqdns"] = list(
            stage_b.get("final_related_fqdns", stage_b.get("selected_related_fqdns", []))
        )
        trace["final_decision_source"] = "stage_b"
        return trace
    return attach_stage_a_final_fields(trace)


def _has_labels(sample: dict[str, Any]) -> bool:
    return "ground_truth_fqdn" in sample and "acceptable_fqdns" in sample


def evaluate_final_chain(samples: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    labeled_pairs = [(sample, trace) for sample, trace in zip(samples, traces) if _has_labels(sample)]
    if not labeled_pairs:
        return {"labeled": False}

    total = len(labeled_pairs)
    primary_hits = 0
    acceptable_hits = 0
    related_total = 0
    related_hits = 0
    predicted_related_total = 0
    fast_path = 0
    slow_path = 0
    source_counts: Counter[str] = Counter()
    error_buckets: Counter[str] = Counter()
    per_sample: list[dict[str, Any]] = []

    for sample, trace in labeled_pairs:
        final_primary = trace.get("final_primary_fqdn", trace["stage_a"]["selected_primary_fqdn"])
        final_related = set(trace.get("final_related_fqdns", trace["stage_a"]["selected_related_fqdns"]))
        decision_source = trace.get("final_decision_source", infer_stage_a_source(trace))
        entered_stage_b = bool(trace.get("entered_stage_b", False))
        gt = sample["ground_truth_fqdn"]
        acceptable = set(sample.get("acceptable_fqdns", [gt]))
        relevant = set(sample.get("relevant_fqdns", []))
        candidates = {row["fqdn"] for row in trace["stage_r"].get("fqdn_candidates", [])}

        primary_hits += int(final_primary == gt)
        acceptable_hits += int(final_primary in acceptable)
        related_total += len(relevant)
        related_hits += len(relevant & final_related)
        predicted_related_total += len(final_related)
        fast_path += int(not entered_stage_b)
        slow_path += int(entered_stage_b)
        source_counts[decision_source] += 1

        if gt not in candidates:
            bucket = "stage_r_primary_miss"
        elif final_primary not in acceptable:
            bucket = "decision_primary_miss"
        elif relevant - final_related:
            bucket = "decision_related_miss"
        elif final_related - relevant:
            bucket = "decision_related_overpredict"
        else:
            bucket = "OK"
        error_buckets[bucket] += 1

        per_sample.append(
            {
                "id": sample["id"],
                "ground_truth_fqdn": gt,
                "final_primary_fqdn": final_primary,
                "final_related_fqdns": sorted(final_related),
                "final_decision_source": decision_source,
                "entered_stage_b": entered_stage_b,
                "error_bucket": bucket,
            }
        )

    return {
        "labeled": True,
        "samples": total,
        "PrimaryAcc@1": round(primary_hits / total, 4),
        "AcceptablePrimary@1": round(acceptable_hits / total, 4),
        "RelatedRecall": round(related_hits / related_total, 4) if related_total else 0.0,
        "RelatedPrecision": round(related_hits / predicted_related_total, 4) if predicted_related_total else 0.0,
        "fast_path_rate": round(fast_path / total, 4),
        "slow_path_rate": round(slow_path / total, 4),
        "escalation_rate": round(slow_path / total, 4),
        "final_decision_source_counts": dict(sorted(source_counts.items())),
        "error_buckets": dict(sorted(error_buckets.items())),
        "per_sample": per_sample,
    }
