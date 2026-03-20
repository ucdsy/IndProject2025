from __future__ import annotations

from collections import Counter
from typing import Any

from .routing_chain import evaluate_final_chain


def _has_labels(sample: dict[str, Any]) -> bool:
    return "ground_truth_fqdn" in sample and "acceptable_fqdns" in sample


def evaluate_stage_b(samples: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    labeled_pairs = [(sample, trace) for sample, trace in zip(samples, traces) if _has_labels(sample)]
    if not labeled_pairs:
        return {"labeled": False}

    chain_summary = evaluate_final_chain(samples, traces)

    total = len(labeled_pairs)
    applied = 0
    changed = 0
    fixed_primary = 0
    regressed_primary = 0
    primary_hits = 0
    acceptable_hits = 0
    related_total = 0
    related_hits = 0
    predicted_related_total = 0
    error_buckets: Counter[str] = Counter()
    per_sample: list[dict[str, Any]] = []

    for sample, trace in labeled_pairs:
        stage_a = trace["stage_a"]
        stage_b = trace.get("stage_b") or {}
        selected_primary = trace.get(
            "final_primary_fqdn",
            stage_b.get("selected_primary_fqdn", stage_a["selected_primary_fqdn"]),
        )
        selected_related = set(
            trace.get(
                "final_related_fqdns",
                stage_b.get("selected_related_fqdns", stage_a["selected_related_fqdns"]),
            )
        )
        gt = sample["ground_truth_fqdn"]
        acceptable = set(sample.get("acceptable_fqdns", [gt]))
        relevant = set(sample.get("relevant_fqdns", []))
        candidates = {row["fqdn"] for row in trace["stage_r"].get("fqdn_candidates", [])}

        stage_a_primary_hit = stage_a["selected_primary_fqdn"] == gt
        stage_b_primary_hit = selected_primary == gt

        applied += int(bool(trace.get("entered_stage_b", bool(stage_b))))
        changed += int(selected_primary != stage_a["selected_primary_fqdn"])
        fixed_primary += int((not stage_a_primary_hit) and stage_b_primary_hit)
        regressed_primary += int(stage_a_primary_hit and (not stage_b_primary_hit))

        primary_hits += int(stage_b_primary_hit)
        acceptable_hits += int(selected_primary in acceptable)
        related_total += len(relevant)
        related_hits += len(relevant & selected_related)
        predicted_related_total += len(selected_related)

        if gt not in candidates:
            bucket = "stage_r_primary_miss"
        elif selected_primary not in acceptable:
            bucket = "decision_primary_miss"
        elif relevant - selected_related:
            bucket = "decision_related_miss"
        elif selected_related - relevant:
            bucket = "decision_related_overpredict"
        else:
            bucket = "OK"
        error_buckets[bucket] += 1

        per_sample.append(
            {
                "id": sample["id"],
                "ground_truth_fqdn": gt,
                "stage_a_primary_fqdn": stage_a["selected_primary_fqdn"],
                "stage_b_primary_fqdn": selected_primary,
                "stage_b_related_fqdns": sorted(selected_related),
                "stage_b_applied": bool(trace.get("entered_stage_b", bool(stage_b))),
                "stage_b_changed_primary": selected_primary != stage_a["selected_primary_fqdn"],
                "final_decision_source": trace.get("final_decision_source"),
                "error_bucket": bucket,
            }
        )

    summary = {
        "labeled": True,
        "samples": total,
        "stage_b_applied": applied,
        "stage_b_changed_primary": changed,
        "stage_b_fixed_primary": fixed_primary,
        "stage_b_regressed_primary": regressed_primary,
        "StageBPrimaryAcc@1": round(primary_hits / total, 4),
        "StageBAcceptablePrimary@1": round(acceptable_hits / total, 4),
        "StageBRelatedRecall": round(related_hits / related_total, 4) if related_total else 0.0,
        "StageBRelatedPrecision": round(related_hits / predicted_related_total, 4) if predicted_related_total else 0.0,
        "error_buckets": dict(sorted(error_buckets.items())),
        "per_sample": per_sample,
    }
    summary.update(
        {
            "PrimaryAcc@1": chain_summary["PrimaryAcc@1"],
            "AcceptablePrimary@1": chain_summary["AcceptablePrimary@1"],
            "RelatedRecall": chain_summary["RelatedRecall"],
            "RelatedPrecision": chain_summary["RelatedPrecision"],
            "fast_path_rate": chain_summary["fast_path_rate"],
            "slow_path_rate": chain_summary["slow_path_rate"],
            "escalation_rate": chain_summary["escalation_rate"],
            "final_decision_source_counts": chain_summary["final_decision_source_counts"],
        }
    )
    return summary
