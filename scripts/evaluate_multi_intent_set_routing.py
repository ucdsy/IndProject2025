#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL row {line_no} in {path}") from exc
    return rows


def _dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _as_ordered_unique(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        path = Path(value)
        return path.stem, path
    name, raw_path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"Empty artifact name in --trace {value!r}")
    return name, Path(raw_path)


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return _safe_div(2 * precision * recall, precision + recall)


def _extract_prediction(trace: dict[str, Any], mode: str) -> list[str]:
    if mode == "stage_a":
        stage_a = trace.get("stage_a") or {}
        if isinstance(stage_a.get("selected_fqdns"), list):
            return _as_ordered_unique(stage_a.get("selected_fqdns"))
        return _as_ordered_unique([stage_a.get("selected_primary_fqdn"), *_as_ordered_unique(stage_a.get("selected_related_fqdns"))])

    if mode == "stage_b":
        stage_b = trace.get("stage_b") or {}
        if stage_b:
            if isinstance(stage_b.get("final_selected_fqdns"), list) or isinstance(stage_b.get("selected_fqdns"), list):
                return _as_ordered_unique(stage_b.get("final_selected_fqdns") or stage_b.get("selected_fqdns"))
            primary = stage_b.get("final_primary_fqdn") or stage_b.get("selected_primary_fqdn")
            related = stage_b.get("final_related_fqdns") or stage_b.get("selected_related_fqdns")
            return _as_ordered_unique([primary, *_as_ordered_unique(related)])
        return _extract_prediction(trace, "stage_a")

    if isinstance(trace.get("final_selected_fqdns"), list):
        return _as_ordered_unique(trace.get("final_selected_fqdns"))
    primary = trace.get("final_primary_fqdn")
    related = trace.get("final_related_fqdns")
    if not primary:
        stage_b = trace.get("stage_b") or {}
        primary = stage_b.get("final_primary_fqdn") or stage_b.get("selected_primary_fqdn")
    if related is None:
        stage_b = trace.get("stage_b") or {}
        related = stage_b.get("final_related_fqdns") or stage_b.get("selected_related_fqdns")
    if not primary:
        stage_a = trace.get("stage_a") or {}
        primary = stage_a.get("selected_primary_fqdn")
    if related is None:
        stage_a = trace.get("stage_a") or {}
        related = stage_a.get("selected_related_fqdns")
    return _as_ordered_unique([primary, *_as_ordered_unique(related)])


def _bucket_summary(rows: list[dict[str, Any]], group_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(group_key, "unknown"))].append(row)
    return {key: _aggregate_per_sample(value) for key, value in sorted(groups.items())}


def _aggregate_per_sample(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "samples": 0,
            "ExactSetAcc": 0.0,
            "SetPrecision_micro": 0.0,
            "SetRecall_micro": 0.0,
            "SetF1_micro": 0.0,
            "SetPrecision_macro": 0.0,
            "SetRecall_macro": 0.0,
            "SetF1_macro": 0.0,
            "Jaccard_macro": 0.0,
            "AllGoldCoveredRate": 0.0,
            "AnyHitRate": 0.0,
            "EmptyPredictionRate": 0.0,
            "OverPredictionRate": 0.0,
            "UnderPredictionRate": 0.0,
            "AvgGoldSetSize": 0.0,
            "AvgPredSetSize": 0.0,
        }

    total = len(rows)
    total_hits = sum(row["hit_count"] for row in rows)
    total_gold = sum(row["gold_count"] for row in rows)
    total_pred = sum(row["pred_count"] for row in rows)
    micro_p = _safe_div(total_hits, total_pred)
    micro_r = _safe_div(total_hits, total_gold)
    exact = sum(1 for row in rows if row["exact_set_match"]) / total
    all_covered = sum(1 for row in rows if row["all_gold_covered"]) / total
    any_hit = sum(1 for row in rows if row["hit_count"] > 0) / total
    empty_pred = sum(1 for row in rows if row["pred_count"] == 0) / total
    over_pred = sum(1 for row in rows if row["extra_count"] > 0) / total
    under_pred = sum(1 for row in rows if row["miss_count"] > 0) / total

    return {
        "samples": total,
        "ExactSetAcc": round(exact, 4),
        "SetPrecision_micro": round(micro_p, 4),
        "SetRecall_micro": round(micro_r, 4),
        "SetF1_micro": round(_f1(micro_p, micro_r), 4),
        "SetPrecision_macro": round(sum(row["precision"] for row in rows) / total, 4),
        "SetRecall_macro": round(sum(row["recall"] for row in rows) / total, 4),
        "SetF1_macro": round(sum(row["f1"] for row in rows) / total, 4),
        "Jaccard_macro": round(sum(row["jaccard"] for row in rows) / total, 4),
        "AllGoldCoveredRate": round(all_covered, 4),
        "AnyHitRate": round(any_hit, 4),
        "EmptyPredictionRate": round(empty_pred, 4),
        "OverPredictionRate": round(over_pred, 4),
        "UnderPredictionRate": round(under_pred, 4),
        "AvgGoldSetSize": round(sum(row["gold_count"] for row in rows) / total, 4),
        "AvgPredSetSize": round(sum(row["pred_count"] for row in rows) / total, 4),
    }


def evaluate_trace(samples: list[dict[str, Any]], traces: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    trace_by_id = {row.get("sample_id"): row for row in traces}
    per_sample: list[dict[str, Any]] = []
    missing: list[str] = []

    for sample in samples:
        sample_id = sample["id"]
        trace = trace_by_id.get(sample_id)
        if not trace:
            missing.append(sample_id)
            continue
        gold = _as_ordered_unique(sample.get("gold_intent_fqdns"))
        pred = _extract_prediction(trace, mode)
        gold_set = set(gold)
        pred_set = set(pred)
        hits = sorted(gold_set & pred_set)
        missing_gold = sorted(gold_set - pred_set)
        extra = sorted(pred_set - gold_set)
        precision = _safe_div(len(hits), len(pred_set))
        recall = _safe_div(len(hits), len(gold_set))
        union_count = len(gold_set | pred_set)
        row = {
            "id": sample_id,
            "intent_count_bucket": sample.get("intent_count_bucket"),
            "domain_mix": sample.get("domain_mix"),
            "gold_intent_fqdns": gold,
            "predicted_fqdns": pred,
            "hits": hits,
            "missing_gold": missing_gold,
            "extra_predicted": extra,
            "gold_count": len(gold_set),
            "pred_count": len(pred_set),
            "hit_count": len(hits),
            "miss_count": len(missing_gold),
            "extra_count": len(extra),
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(_f1(precision, recall), 6),
            "jaccard": round(_safe_div(len(hits), union_count), 6),
            "exact_set_match": gold_set == pred_set,
            "all_gold_covered": gold_set <= pred_set,
            "entered_stage_b": bool(trace.get("entered_stage_b")),
            "final_decision_source": trace.get("final_decision_source"),
            "final_related_source": trace.get("final_related_source"),
        }
        per_sample.append(row)

    if missing:
        raise KeyError(f"Missing traces for {len(missing)} samples; first missing ids: {missing[:5]}")

    summary = _aggregate_per_sample(per_sample)
    summary.update(
        {
            "prediction_mode": mode,
            "samples_total": len(samples),
            "samples_evaluated": len(per_sample),
            "intent_count_buckets": _bucket_summary(per_sample, "intent_count_bucket"),
            "domain_mix_buckets": _bucket_summary(per_sample, "domain_mix"),
            "entered_stage_b_rate": round(sum(1 for row in per_sample if row["entered_stage_b"]) / len(per_sample), 4)
            if per_sample
            else 0.0,
            "final_decision_source_counts": dict(
                sorted(Counter(str(row["final_decision_source"]) for row in per_sample).items())
            ),
            "final_related_source_counts": dict(
                sorted(Counter(str(row["final_related_source"]) for row in per_sample).items())
            ),
            "per_sample": per_sample,
        }
    )
    return summary


def evaluate_snapshot(samples: list[dict[str, Any]], snapshots: list[dict[str, Any]], top_k: int | None) -> dict[str, Any]:
    snapshot_by_id = {row.get("id"): row for row in snapshots}
    per_sample: list[dict[str, Any]] = []
    missing: list[str] = []

    for sample in samples:
        sample_id = sample["id"]
        snapshot = snapshot_by_id.get(sample_id)
        if not snapshot:
            missing.append(sample_id)
            continue
        candidates = [row.get("fqdn") for row in snapshot.get("fqdn_candidates", [])]
        candidates = [fqdn for fqdn in candidates if isinstance(fqdn, str)]
        if top_k is not None:
            candidates = candidates[:top_k]
        gold = _as_ordered_unique(sample.get("gold_intent_fqdns"))
        gold_set = set(gold)
        candidate_set = set(candidates)
        hits = sorted(gold_set & candidate_set)
        row = {
            "id": sample_id,
            "intent_count_bucket": sample.get("intent_count_bucket"),
            "domain_mix": sample.get("domain_mix"),
            "gold_intent_fqdns": gold,
            "candidate_fqdns": candidates,
            "hits": hits,
            "missing_gold": sorted(gold_set - candidate_set),
            "candidate_count": len(candidate_set),
            "gold_count": len(gold_set),
            "hit_count": len(hits),
            "miss_count": len(gold_set - candidate_set),
            "all_gold_covered": gold_set <= candidate_set,
            "any_hit": bool(gold_set & candidate_set),
        }
        per_sample.append(row)

    if missing:
        raise KeyError(f"Missing snapshots for {len(missing)} samples; first missing ids: {missing[:5]}")

    total = len(per_sample)
    total_hits = sum(row["hit_count"] for row in per_sample)
    total_gold = sum(row["gold_count"] for row in per_sample)
    all_covered = sum(1 for row in per_sample if row["all_gold_covered"])
    any_hit = sum(1 for row in per_sample if row["any_hit"])
    return {
        "samples": total,
        "candidate_top_k": top_k,
        "GoldCoverageRecall": round(_safe_div(total_hits, total_gold), 4),
        "AllGoldCoveredRate": round(_safe_div(all_covered, total), 4),
        "AnyHitRate": round(_safe_div(any_hit, total), 4),
        "AvgGoldSetSize": round(_safe_div(total_gold, total), 4),
        "AvgCandidateSetSize": round(_safe_div(sum(row["candidate_count"] for row in per_sample), total), 4),
        "intent_count_buckets": _snapshot_bucket_summary(per_sample, "intent_count_bucket"),
        "domain_mix_buckets": _snapshot_bucket_summary(per_sample, "domain_mix"),
        "per_sample": per_sample,
    }


def _snapshot_bucket_summary(rows: list[dict[str, Any]], group_key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(group_key, "unknown"))].append(row)
    output: dict[str, dict[str, Any]] = {}
    for key, group_rows in sorted(groups.items()):
        total = len(group_rows)
        total_hits = sum(row["hit_count"] for row in group_rows)
        total_gold = sum(row["gold_count"] for row in group_rows)
        output[key] = {
            "samples": total,
            "GoldCoverageRecall": round(_safe_div(total_hits, total_gold), 4),
            "AllGoldCoveredRate": round(_safe_div(sum(1 for row in group_rows if row["all_gold_covered"]), total), 4),
            "AnyHitRate": round(_safe_div(sum(1 for row in group_rows if row["any_hit"]), total), 4),
            "AvgGoldSetSize": round(_safe_div(total_gold, total), 4),
            "AvgCandidateSetSize": round(_safe_div(sum(row["candidate_count"] for row in group_rows), total), 4),
        }
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate set-valued routing on multi-intent AgentDNS samples.")
    parser.add_argument("--input", required=True, help="Multi-intent dataset jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Directory for summary and per-sample artifacts.")
    parser.add_argument("--snapshot", default=None, help="Optional Stage R snapshot jsonl path.")
    parser.add_argument("--snapshot-top-k", type=int, default=None, help="Optional top-k cutoff for snapshot coverage.")
    parser.add_argument(
        "--trace",
        action="append",
        default=[],
        help="Named trace as name=path. Can be repeated.",
    )
    parser.add_argument(
        "--prediction-mode",
        choices=["final", "stage_a", "stage_b"],
        default="final",
        help="Which trace fields should define the predicted set.",
    )
    parser.add_argument("--summary-name", default="multi_intent_set_eval.summary.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = _load_jsonl(input_path)

    result: dict[str, Any] = {
        "input_path": str(input_path),
        "samples": len(samples),
        "gold_total_mentions": sum(len(_as_ordered_unique(row.get("gold_intent_fqdns"))) for row in samples),
        "artifacts": {},
    }

    if args.snapshot:
        snapshot_path = Path(args.snapshot)
        snapshot_summary = evaluate_snapshot(samples, _load_jsonl(snapshot_path), args.snapshot_top_k)
        result["stage_r_snapshot"] = {key: value for key, value in snapshot_summary.items() if key != "per_sample"}
        per_sample_path = output_dir / "stage_r_snapshot.per_sample.jsonl"
        _dump_jsonl(per_sample_path, snapshot_summary["per_sample"])
        result["artifacts"]["stage_r_snapshot_per_sample"] = str(per_sample_path)

    trace_summaries: dict[str, Any] = {}
    for trace_arg in args.trace:
        name, trace_path = _parse_named_path(trace_arg)
        summary = evaluate_trace(samples, _load_jsonl(trace_path), args.prediction_mode)
        trace_summaries[name] = {key: value for key, value in summary.items() if key != "per_sample"}
        per_sample_path = output_dir / f"{name}.per_sample.jsonl"
        _dump_jsonl(per_sample_path, summary["per_sample"])
        result["artifacts"][f"{name}_per_sample"] = str(per_sample_path)
    if trace_summaries:
        result["traces"] = trace_summaries

    summary_path = output_dir / args.summary_name
    result["artifacts"]["summary"] = str(summary_path)
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
