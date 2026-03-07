#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentdns_routing.namespace import NamespaceResolver, load_jsonl as load_descriptor_jsonl, validate_fqdn
from agentdns_routing.stage_r_clean import (
    StageRCleanConfig,
    build_candidate_snapshot,
    dump_jsonl,
    load_jsonl,
)


GATE_THRESHOLDS = {
    "PrimaryRecall@10": 0.92,
    "UnionCoverage@10": 0.85,
    "L1Acc_top1cand": 0.90,
    "L2Acc_top1cand": 0.82,
    "L3PrimaryRecall@10": 0.90,
}

CONFUSION_MAP = {
    "C0_low_confusion": "low_confusion",
    "C1_multi_intent": "multi_intent",
    "C3_sibling_competition": "sibling_competition",
    "C4_governance_fallback": "governance_fallback",
    "C5_cross_domain_overlap": "cross_domain_overlap",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run gate evaluation for clean Stage R.")
    parser.add_argument("--input", required=True, help="Input jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--stage-r-version", default="sr_clean_v1_20260307")
    return parser.parse_args()


def build_snapshots(
    samples: list[dict[str, Any]],
    resolver: NamespaceResolver,
    top_k: int,
    stage_r_version: str,
    config: StageRCleanConfig,
) -> list[dict[str, Any]]:
    return [
        build_candidate_snapshot(
            sample=sample,
            resolver=resolver,
            top_k=top_k,
            stage_r_version=stage_r_version,
            config=config,
        )
        for sample in samples
    ]


def _rank_of(fqdn: str, candidates: list[dict[str, Any]]) -> int | None:
    for idx, candidate in enumerate(candidates, start=1):
        if candidate["fqdn"] == fqdn:
            return idx
    return None


def _union_coverage(sample: dict[str, Any], top_fqdns: list[str]) -> float:
    union = {sample["ground_truth_fqdn"], *sample.get("relevant_fqdns", [])}
    if not union:
        return 0.0
    return len(union & set(top_fqdns)) / len(union)


def _normalize_confusions(labels: list[str]) -> set[str]:
    normalized: set[str] = set()
    for label in labels:
        normalized.add(CONFUSION_MAP.get(label, label))
    return normalized


def classify_error_bucket(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    top_k: int,
) -> str:
    gt_node = resolver.get_node(sample["ground_truth_fqdn"])
    if not gt_node:
        return "E0_parse"
    candidate_nodes = [resolver.get_node(row["fqdn"]) for row in snapshot["fqdn_candidates"][:top_k]]
    gt_rank = _rank_of(sample["ground_truth_fqdn"], snapshot["fqdn_candidates"][:top_k])

    if gt_rank is None:
        same_l1 = any(node and node.l1 == gt_node.l1 for node in candidate_nodes)
        if not same_l1:
            return "E1_l1"

        same_l2 = any(node and node.l1 == gt_node.l1 and node.l2 == gt_node.l2 for node in candidate_nodes)
        if gt_node.l2 and not same_l2:
            return "E2_l2"

        if gt_node.depth == 3:
            same_parent = any(node and node.parent_fqdn == gt_node.parent_fqdn for node in candidate_nodes)
            if not same_parent:
                return "E3_l3"

        return "E4_candidate_miss"

    intended = set(sample.get("intended_confusion_types", []))
    predicted = _normalize_confusions(snapshot.get("confusion_sources", []))
    if intended and not (intended & predicted):
        return "E6_unjustified_confusion"
    if gt_rank > 1:
        return "E5_candidate_noise"
    return "OK"


def compute_core_metrics(
    samples: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    resolver: NamespaceResolver,
    top_k: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    primary_at_5 = 0
    primary_at_10 = 0
    related_total_5 = 0
    related_hits_5 = 0
    related_total_10 = 0
    related_hits_10 = 0
    union_sum = 0.0
    l1_hits = 0
    l2_hits = 0
    l2_total = 0
    l3_hits = 0
    l3_total = 0
    oracle_primary = 0
    reciprocal_rank = 0.0
    error_buckets: Counter[str] = Counter()
    per_sample: list[dict[str, Any]] = []

    for sample, snapshot in zip(samples, snapshots):
        top_fqdns = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"][:top_k]]
        top_5 = top_fqdns[:5]
        gt = sample["ground_truth_fqdn"]
        gt_node = resolver.get_node(gt)
        top1_node = resolver.get_node(top_fqdns[0]) if top_fqdns else None
        gt_rank = _rank_of(gt, snapshot["fqdn_candidates"][:top_k])
        related = sample.get("relevant_fqdns", [])
        acceptable = sample.get("acceptable_fqdns", [gt])

        if gt in top_5:
            primary_at_5 += 1
        if gt in top_fqdns:
            primary_at_10 += 1
        if any(fqdn in top_fqdns for fqdn in acceptable):
            oracle_primary += 1
        if gt_rank is not None:
            reciprocal_rank += 1.0 / gt_rank

        related_total_5 += len(related)
        related_hits_5 += sum(1 for fqdn in related if fqdn in top_5)
        related_total_10 += len(related)
        related_hits_10 += sum(1 for fqdn in related if fqdn in top_fqdns)
        union_cov = _union_coverage(sample, top_fqdns)
        union_sum += union_cov

        l1_hit = bool(top1_node and gt_node and top1_node.l1 == gt_node.l1)
        l1_hits += int(l1_hit)

        l2_hit = False
        if gt_node and gt_node.l2 is not None:
            l2_total += 1
            l2_hit = bool(top1_node and top1_node.l1 == gt_node.l1 and top1_node.l2 == gt_node.l2)
            l2_hits += int(l2_hit)

        l3_hit = False
        if gt_node and gt_node.depth == 3:
            l3_total += 1
            l3_hit = gt in top_fqdns
            l3_hits += int(l3_hit)

        bucket = classify_error_bucket(sample, snapshot, resolver, top_k)
        error_buckets[bucket] += 1
        per_sample.append(
            {
                "id": sample["id"],
                "ground_truth_fqdn": gt,
                "top1_fqdn": top_fqdns[0] if top_fqdns else None,
                "primary_rank": gt_rank,
                "l1_hit_top1": l1_hit,
                "l2_hit_top1": l2_hit if gt_node and gt_node.l2 is not None else None,
                "union_coverage_top10": round(union_cov, 4),
                "error_bucket": bucket,
                "confusion_sources": snapshot.get("confusion_sources", []),
                "intended_confusion_types": sample.get("intended_confusion_types", []),
                "head_score_delta": snapshot.get("semantic_parse", {}).get("selection_signals", {}).get("head_score_delta"),
            }
        )

    metrics = {
        "samples": len(samples),
        "PrimaryRecall@5": round(primary_at_5 / len(samples), 4) if samples else 0.0,
        "PrimaryRecall@10": round(primary_at_10 / len(samples), 4) if samples else 0.0,
        "RelatedCoverage@5": round(related_hits_5 / related_total_5, 4) if related_total_5 else 0.0,
        "RelatedCoverage@10": round(related_hits_10 / related_total_10, 4) if related_total_10 else 0.0,
        "UnionCoverage@10": round(union_sum / len(samples), 4) if samples else 0.0,
        "OraclePrimary@10": round(oracle_primary / len(samples), 4) if samples else 0.0,
        "MRR": round(reciprocal_rank / len(samples), 4) if samples else 0.0,
        "L1Acc_top1cand": round(l1_hits / len(samples), 4) if samples else 0.0,
        "L2Acc_top1cand": round(l2_hits / l2_total, 4) if l2_total else 0.0,
        "L3PrimaryRecall@10": round(l3_hits / l3_total, 4) if l3_total else 0.0,
        "error_buckets": dict(sorted(error_buckets.items())),
    }
    return metrics, per_sample


def validate_snapshot_contracts(
    snapshots: list[dict[str, Any]],
    schema_path: Path,
    top_k: int,
) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    schema_errors: list[dict[str, str]] = []
    valid_schema_count = 0
    valid_candidates_count = 0
    valid_trace_count = 0
    valid_confusion_count = 0

    required_trace_fields = {
        "semantic_parse",
        "descriptor_scores",
        "subtree_scores",
        "recall_sources",
        "fqdn_candidates",
        "confusion_sources",
        "candidate_generation_rules",
    }

    for snapshot in snapshots:
        errors = list(validator.iter_errors(snapshot))
        if not errors:
            valid_schema_count += 1
        else:
            schema_errors.append({"id": snapshot["id"], "error": errors[0].message})

        candidates = snapshot.get("fqdn_candidates", [])[:top_k]
        if candidates and all(validate_fqdn(candidate["fqdn"]) for candidate in candidates):
            valid_candidates_count += 1
        if required_trace_fields.issubset(snapshot.keys()):
            valid_trace_count += 1
        if snapshot.get("confusion_sources"):
            valid_confusion_count += 1

    total = len(snapshots) or 1
    return {
        "SnapshotSchemaPassRate": round(valid_schema_count / total, 4),
        "CandidateFormatPassRate": round(valid_candidates_count / total, 4),
        "TraceFieldPassRate": round(valid_trace_count / total, 4),
        "ConfusionSourcePassRate": round(valid_confusion_count / total, 4),
        "schema_errors": schema_errors[:10],
    }


def compute_confusion_breakdown(
    samples: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    top_k: int,
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for sample, snapshot in zip(samples, snapshots):
        for label in sample.get("intended_confusion_types", []):
            buckets[label].append((sample, snapshot))

    out: dict[str, dict[str, Any]] = {}
    for label, pairs in sorted(buckets.items()):
        primary_3 = 0
        primary_5 = 0
        primary_10 = 0
        related_hits = 0
        related_total = 0
        union_sum = 0.0
        reciprocal_rank = 0.0

        for sample, snapshot in pairs:
            top = [candidate["fqdn"] for candidate in snapshot["fqdn_candidates"][:top_k]]
            gt = sample["ground_truth_fqdn"]
            rank = _rank_of(gt, snapshot["fqdn_candidates"][:top_k])
            if gt in top[:3]:
                primary_3 += 1
            if gt in top[:5]:
                primary_5 += 1
            if gt in top:
                primary_10 += 1
            if rank is not None:
                reciprocal_rank += 1.0 / rank
            related = sample.get("relevant_fqdns", [])
            related_total += len(related)
            related_hits += sum(1 for fqdn in related if fqdn in top)
            union_sum += _union_coverage(sample, top)

        total = len(pairs)
        out[label] = {
            "samples": total,
            "PrimaryRecall@3": round(primary_3 / total, 4),
            "PrimaryRecall@5": round(primary_5 / total, 4),
            "PrimaryRecall@10": round(primary_10 / total, 4),
            "RelatedCoverage@10": round(related_hits / related_total, 4) if related_total else 0.0,
            "UnionCoverage@10": round(union_sum / total, 4),
            "MRR": round(reciprocal_rank / total, 4),
        }
    return out


def build_variant_summary(
    samples: list[dict[str, Any]],
    resolver: NamespaceResolver,
    top_k: int,
    stage_r_version: str,
    name: str,
    config: StageRCleanConfig,
) -> dict[str, Any]:
    snapshots = build_snapshots(samples, resolver, top_k, stage_r_version=f"{stage_r_version}.{name}", config=config)
    metrics, _ = compute_core_metrics(samples, snapshots, resolver, top_k)
    return {
        "variant": name,
        "config_overrides": {
            key: value
            for key, value in config.__dict__.items()
            if value != StageRCleanConfig().__dict__[key]
        },
        "PrimaryRecall@10": metrics["PrimaryRecall@10"],
        "UnionCoverage@10": metrics["UnionCoverage@10"],
        "MRR": metrics["MRR"],
        "L1Acc_top1cand": metrics["L1Acc_top1cand"],
        "L2Acc_top1cand": metrics["L2Acc_top1cand"],
    }


def run_ablations(
    samples: list[dict[str, Any]],
    resolver: NamespaceResolver,
    top_k: int,
    stage_r_version: str,
    baseline: StageRCleanConfig,
) -> list[dict[str, Any]]:
    variants = {
        "full": baseline,
        "minus_hierarchy": replace(baseline, enable_hierarchy_rerank=False),
        "minus_context_facets": replace(baseline, enable_context_facet_match=False),
        "minus_parent_fallback": replace(baseline, enable_parent_fallback=False),
    }
    return [
        build_variant_summary(samples, resolver, top_k, stage_r_version, name, config)
        for name, config in variants.items()
    ]


def run_sensitivity(
    samples: list[dict[str, Any]],
    resolver: NamespaceResolver,
    top_k: int,
    stage_r_version: str,
    baseline: StageRCleanConfig,
) -> list[dict[str, Any]]:
    variants = {
        "baseline": baseline,
        "alias_weight_minus15": replace(baseline, query_alias_weight=round(baseline.query_alias_weight * 0.85, 6)),
        "alias_weight_plus15": replace(baseline, query_alias_weight=round(baseline.query_alias_weight * 1.15, 6)),
        "context_weight_minus15": replace(baseline, context_match_weight=round(baseline.context_match_weight * 0.85, 6)),
        "context_weight_plus15": replace(baseline, context_match_weight=round(baseline.context_match_weight * 1.15, 6)),
    }
    return [
        build_variant_summary(samples, resolver, top_k, stage_r_version, name, config)
        for name, config in variants.items()
    ]


def compute_close_score_buckets(
    per_sample: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_sample:
        delta = row.get("head_score_delta")
        if delta is None:
            bucket = "singleton_or_no_delta"
        elif delta < 0.03:
            bucket = "delta_lt_0_03"
        elif delta < 0.08:
            bucket = "delta_0_03_to_0_08"
        else:
            bucket = "delta_ge_0_08"
        groups[bucket].append(row)

    out: dict[str, dict[str, Any]] = {}
    for bucket, rows in sorted(groups.items()):
        total = len(rows)
        primary_top1 = sum(1 for row in rows if row["primary_rank"] == 1)
        primary_top3 = sum(1 for row in rows if row["primary_rank"] is not None and row["primary_rank"] <= 3)
        out[bucket] = {
            "samples": total,
            "Top1PrimaryRate": round(primary_top1 / total, 4),
            "Top3PrimaryRate": round(primary_top3 / total, 4),
            "L1Acc_top1cand": round(sum(1 for row in rows if row["l1_hit_top1"]) / total, 4),
            "L2Acc_top1cand": round(
                sum(1 for row in rows if row["l2_hit_top1"] is True) / max(1, sum(1 for row in rows if row["l2_hit_top1"] is not None)),
                4,
            ),
        }
    return out


def run_robustness_checks(resolver: NamespaceResolver, stage_r_version: str) -> dict[str, Any]:
    cases = [
        {
            "name": "empty_query",
            "sample": {
                "id": "robust_empty_query",
                "namespace_version": resolver.namespace_version,
                "query": "",
                "context": {"industry": "enterprise_service"},
                "constraints": ["fqdn_format_valid"],
                "ground_truth_fqdn": "docs.productivity.cn",
                "relevant_fqdns": [],
            },
            "check": lambda snapshot: len(snapshot["fqdn_candidates"]) == 10 and all(
                validate_fqdn(candidate["fqdn"]) for candidate in snapshot["fqdn_candidates"]
            ),
        },
        {
            "name": "null_context",
            "sample": {
                "id": "robust_null_context",
                "namespace_version": resolver.namespace_version,
                "query": "帮我做一版训练计划。",
                "context": None,
                "constraints": ["fqdn_format_valid"],
                "ground_truth_fqdn": "fitness.health.cn",
                "relevant_fqdns": [],
            },
            "check": lambda snapshot: "fitness.health.cn" in {candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]},
        },
        {
            "name": "long_mixed_context",
            "sample": {
                "id": "robust_long_context",
                "namespace_version": resolver.namespace_version,
                "query": "上线前先做一版风险评估。",
                "context": {
                    "industry": "manufacturing",
                    "time_window": "next_week",
                    "notes": "设备上线前需要反复检查日志、权限和留痕。" * 15,
                    "flags": ["regulated_service", "external"],
                    "budget_rmb": 12000,
                },
                "constraints": ["fqdn_format_valid"],
                "ground_truth_fqdn": "risk.security.cn",
                "relevant_fqdns": ["data.compliance.security.cn"],
            },
            "check": lambda snapshot: "risk.security.cn" in {candidate["fqdn"] for candidate in snapshot["fqdn_candidates"]}
            and bool(snapshot["confusion_sources"]),
        },
    ]

    results = []
    for case in cases:
        snapshot = build_candidate_snapshot(
            sample=case["sample"],
            resolver=resolver,
            top_k=10,
            stage_r_version=stage_r_version,
            config=StageRCleanConfig(),
        )
        passed = bool(case["check"](snapshot))
        results.append({"name": case["name"], "passed": passed})
    return {"all_passed": all(item["passed"] for item in results), "cases": results}


def determine_gate_status(core: dict[str, Any], contract: dict[str, Any], robustness: dict[str, Any]) -> dict[str, Any]:
    gate_1_checks = {
        metric: core[metric] >= threshold for metric, threshold in GATE_THRESHOLDS.items()
    }
    gate_1_checks["SnapshotSchemaPassRate"] = contract["SnapshotSchemaPassRate"] == 1.0
    gate_1_checks["CandidateFormatPassRate"] = contract["CandidateFormatPassRate"] == 1.0
    gate_1_checks["TraceFieldPassRate"] = contract["TraceFieldPassRate"] == 1.0
    gate_1_checks["ConfusionSourcePassRate"] = contract["ConfusionSourcePassRate"] == 1.0
    gate_1_checks["Robustness"] = robustness["all_passed"]
    gate_1_passed = all(gate_1_checks.values())

    return {
        "gate_1_required": {
            "passed": gate_1_passed,
            "checks": gate_1_checks,
        },
        "gate_2_recommended": {
            "completed": True,
            "items": [
                "confusion_type_breakdown",
                "module_ablations",
                "weight_sensitivity",
                "close_score_buckets",
            ],
        },
        "advance_recommendation": "advance_to_stage_a" if gate_1_passed else "hold_stage_r",
    }


def build_markdown_report(
    stage_r_version: str,
    input_path: Path,
    snapshot_path: Path,
    summary: dict[str, Any],
) -> str:
    core = summary["core_metrics"]
    gate = summary["gate_status"]
    lines = [
        f"# Stage R Gate Report ({stage_r_version})",
        "",
        f"- Input: `{input_path}`",
        f"- Snapshot: `{snapshot_path}`",
        f"- Advance recommendation: `{gate['advance_recommendation']}`",
        "",
        "## Core Metrics",
        "",
        f"- PrimaryRecall@5: {core['PrimaryRecall@5']}",
        f"- PrimaryRecall@10: {core['PrimaryRecall@10']}",
        f"- RelatedCoverage@10: {core['RelatedCoverage@10']}",
        f"- UnionCoverage@10: {core['UnionCoverage@10']}",
        f"- MRR: {core['MRR']}",
        f"- L1Acc_top1cand: {core['L1Acc_top1cand']}",
        f"- L2Acc_top1cand: {core['L2Acc_top1cand']}",
        f"- L3PrimaryRecall@10: {core['L3PrimaryRecall@10']}",
        "",
        "## Gate 1",
        "",
    ]
    for name, passed in gate["gate_1_required"]["checks"].items():
        lines.append(f"- {name}: {'PASS' if passed else 'FAIL'}")

    lines.extend(
        [
            "",
            "## Error Buckets",
            "",
        ]
    )
    for bucket, count in core["error_buckets"].items():
        lines.append(f"- {bucket}: {count}")

    lines.extend(
        [
            "",
            "## Gate 2",
            "",
            "- confusion_type_breakdown: completed",
            "- module_ablations: completed",
            "- weight_sensitivity: completed",
            "- close_score_buckets: completed",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    resolver = NamespaceResolver(load_descriptor_jsonl(args.descriptors))
    samples = load_jsonl(input_path)
    config = StageRCleanConfig()
    base_name = f"{input_path.stem}.{args.stage_r_version}"
    snapshot_path = output_dir / f"{base_name}.jsonl"
    summary_path = output_dir / f"{base_name}.gate_summary.json"
    per_sample_path = output_dir / f"{base_name}.per_sample.json"
    report_path = output_dir / f"{base_name}.gate_report.md"

    snapshots = build_snapshots(samples, resolver, args.top_k, args.stage_r_version, config)
    dump_jsonl(snapshot_path, snapshots)

    core_metrics, per_sample = compute_core_metrics(samples, snapshots, resolver, args.top_k)
    contract_checks = validate_snapshot_contracts(
        snapshots,
        schema_path=ROOT / "schemas" / "candidate_snapshot.schema.json",
        top_k=args.top_k,
    )
    confusion_breakdown = compute_confusion_breakdown(samples, snapshots, args.top_k)
    ablations = run_ablations(samples, resolver, args.top_k, args.stage_r_version, config)
    sensitivity = run_sensitivity(samples, resolver, args.top_k, args.stage_r_version, config)
    close_score_buckets = compute_close_score_buckets(per_sample)
    robustness = run_robustness_checks(resolver, args.stage_r_version)
    gate_status = determine_gate_status(core_metrics, contract_checks, robustness)

    summary = {
        "input": str(input_path),
        "stage_r_version": args.stage_r_version,
        "top_k": args.top_k,
        "snapshot_path": str(snapshot_path),
        "core_metrics": core_metrics,
        "contract_checks": contract_checks,
        "robustness": robustness,
        "confusion_type_breakdown": confusion_breakdown,
        "ablations": ablations,
        "sensitivity": sensitivity,
        "close_score_buckets": close_score_buckets,
        "gate_status": gate_status,
    }

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    per_sample_path.write_text(json.dumps(per_sample, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(build_markdown_report(args.stage_r_version, input_path, snapshot_path, summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
