from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def has_labels(sample: dict[str, Any]) -> bool:
    return "ground_truth_fqdn" in sample and "acceptable_fqdns" in sample


def evaluate_traces(samples: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    labeled_pairs = [(sample, trace) for sample, trace in zip(samples, traces) if has_labels(sample)]
    if not labeled_pairs:
        return {"labeled": False}

    total = len(labeled_pairs)
    primary_hits = 0
    acceptable_hits = 0
    related_total = 0
    related_hits = 0
    related_covered_total = 0
    related_stage_a_hits = 0
    predicted_related_total = 0
    extra_related_total = 0
    overpredict_samples = 0
    escalation_count = 0
    error_buckets: Counter[str] = Counter()
    per_sample: list[dict[str, Any]] = []

    for sample, trace in labeled_pairs:
        stage_a = trace["stage_a"]
        selected_primary = stage_a["selected_primary_fqdn"]
        selected_related = set(stage_a["selected_related_fqdns"])
        candidates = [row["fqdn"] for row in trace["stage_r"].get("fqdn_candidates", [])]
        candidate_set = set(candidates)
        gt = sample["ground_truth_fqdn"]
        acceptable = set(sample.get("acceptable_fqdns", [gt]))
        relevant = set(sample.get("relevant_fqdns", []))
        relevant_covered = relevant & candidate_set
        relevant_missing_stage_r = relevant - candidate_set
        relevant_missing_stage_a = relevant_covered - selected_related
        extra_related = selected_related - relevant

        primary_hit = selected_primary == gt
        acceptable_hit = selected_primary in acceptable
        related_hit_count = len(relevant & selected_related)

        primary_hits += int(primary_hit)
        acceptable_hits += int(acceptable_hit)
        related_total += len(relevant)
        related_hits += related_hit_count
        related_covered_total += len(relevant_covered)
        related_stage_a_hits += len(relevant_covered & selected_related)
        predicted_related_total += len(selected_related)
        extra_related_total += len(extra_related)
        overpredict_samples += int(bool(extra_related))
        escalation_count += int(stage_a["escalate_to_stage_b"])

        if gt not in candidates:
            bucket = "stage_r_primary_miss"
        elif relevant_missing_stage_r:
            bucket = "stage_r_related_miss"
        elif not acceptable_hit:
            bucket = "decision_primary_miss"
        elif relevant and relevant_missing_stage_a:
            bucket = "decision_related_miss"
        elif extra_related:
            bucket = "decision_related_overpredict"
        else:
            bucket = "OK"
        error_buckets[bucket] += 1

        per_sample.append(
            {
                "id": sample["id"],
                "ground_truth_fqdn": gt,
                "selected_primary_fqdn": selected_primary,
                "selected_related_fqdns": sorted(selected_related),
                "acceptable_hit": acceptable_hit,
                "related_hit_count": related_hit_count,
                "related_total": len(relevant),
                "related_covered_by_stage_r": len(relevant_covered),
                "related_missing_stage_r": sorted(relevant_missing_stage_r),
                "related_missing_stage_a": sorted(relevant_missing_stage_a),
                "extra_related_fqdns": sorted(extra_related),
                "confidence": stage_a["confidence"],
                "margin": stage_a["margin"],
                "escalate_to_stage_b": stage_a["escalate_to_stage_b"],
                "escalation_reasons": stage_a["escalation_reasons"],
                "error_bucket": bucket,
            }
        )

    return {
        "labeled": True,
        "samples": total,
        "PrimaryAcc@1": round(primary_hits / total, 4),
        "AcceptablePrimary@1": round(acceptable_hits / total, 4),
        "RelatedRecall": round(related_hits / related_total, 4) if related_total else 0.0,
        "RelatedRecall@Covered": round(related_stage_a_hits / related_covered_total, 4) if related_covered_total else 0.0,
        "RelatedPrecision": round(related_hits / predicted_related_total, 4) if predicted_related_total else 0.0,
        "avg_extra_related": round(extra_related_total / total, 4),
        "related_overpredict_rate": round(overpredict_samples / total, 4),
        "escalation_rate": round(escalation_count / total, 4),
        "error_buckets": dict(sorted(error_buckets.items())),
        "per_sample": per_sample,
    }


def validate_traces(traces: list[dict[str, Any]], root: str | Path) -> dict[str, Any]:
    root = Path(root)
    schema = json.loads((root / "schemas" / "routing_run_trace.schema.json").read_text(encoding="utf-8"))
    candidate_schema = json.loads((root / "schemas" / "candidate_snapshot.schema.json").read_text(encoding="utf-8"))
    if schema.get("properties", {}).get("stage_r", {}).get("$ref") == "candidate_snapshot.schema.json":
        schema["properties"]["stage_r"] = candidate_schema
    validator = Draft202012Validator(schema)
    errors: list[dict[str, Any]] = []
    for trace in traces:
        trace_errors = list(validator.iter_errors(trace))
        if trace_errors:
            errors.append(
                {
                    "sample_id": trace.get("sample_id"),
                    "errors": [error.message for error in trace_errors],
                }
            )
    return {"valid": not errors, "errors": errors}
