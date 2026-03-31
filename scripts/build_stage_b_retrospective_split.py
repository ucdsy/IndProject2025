#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SPLITS = {
    "dev": {
        "labels": ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl",
        "trace": ROOT / "artifacts" / "stage_b" / "gate_replay_20260331_v3" / "dev" / "dev.stage_b_heterogeneous_v3_20260331.jsonl",
    },
    "blind": {
        "labels": ROOT / "artifacts" / "dataset" / "blind_joined_20260315_once.jsonl",
        "trace": ROOT / "artifacts" / "stage_b" / "gate_replay_20260331_v3" / "blind" / "blind_joined_20260315_once.stage_b_heterogeneous_v3_20260331.jsonl",
    },
    "challenge": {
        "labels": ROOT / "artifacts" / "dataset" / "challenge_joined_20260320_once.jsonl",
        "trace": ROOT / "artifacts" / "stage_b" / "gate_replay_20260331_v3" / "challenge" / "challenge_joined_20260320_once.stage_b_heterogeneous_v3_20260331.jsonl",
    },
    "holdout2": {
        "labels": ROOT / "artifacts" / "dataset" / "holdout2_joined_20260322_once.jsonl",
        "trace": ROOT / "artifacts" / "stage_b" / "gate_replay_20260331_v3" / "holdout2" / "holdout2_joined_20260322_once.stage_b_heterogeneous_v3_20260331.jsonl",
    },
    "holdout3": {
        "labels": ROOT / "artifacts" / "dataset" / "holdout3_joined_20260330_once.jsonl",
        "trace": ROOT / "artifacts" / "stage_b" / "collab_ablations_20260331_v3" / "holdout3_heterogeneous" / "holdout3_joined_20260330_once.stage_b_heterogeneous_v3_20260331.jsonl",
    },
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _winner_feedback(sample: dict[str, Any]) -> dict[str, Any] | None:
    feedback_scores = sample["stage_b"].get("feedback_scores", [])
    if not feedback_scores:
        return None
    return feedback_scores[0]


def _simulate_primary(sample: dict[str, Any], mode: str) -> str | None:
    stage_a_primary = sample["stage_a"].get("selected_primary_fqdn")
    winner = _winner_feedback(sample)
    if not winner:
        return stage_a_primary
    winner_fqdn = winner["fqdn"]
    if winner_fqdn == stage_a_primary:
        return stage_a_primary

    blocks = set(sample["stage_b"]["trust_trace"].get("override_block_reasons") or [])
    support = set(winner.get("role_signal_support_families") or [])
    signal_block = set(winner.get("role_signal_block_families") or [])
    tags = set((winner.get("override_basis_histogram") or {}).keys())
    flags = sample["stage_b"]["trust_trace"].get("sensitive_override_flags") or {}

    if mode in {"conservative", "aggressive"}:
        blocks -= {"insufficient_round1_votes", "sensitive_override_requires_round2_consensus"}
        allow_same_l1 = (
            not flags.get("cross_l1_override")
            and {"DomainExpert", "UserPreference"}.issubset(support)
            and (
                "HierarchyResolver" in support
                or not (flags.get("hierarchical_override") or "hierarchy_disambiguation" in tags)
            )
            and (
                "GovernanceRisk" in support
                or not (flags.get("high_risk_override") or "risk_requirement" in tags)
            )
        )
        if allow_same_l1:
            blocks -= {
                "sensitive_override_requires_primary_hits",
                "sensitive_override_requires_stronger_explicit_support",
            }

    if mode == "aggressive":
        allow_cross_l1 = (
            flags.get("cross_l1_override")
            and {"DomainExpert", "UserPreference"}.issubset(support)
            and "GovernanceRisk" not in signal_block
        )
        if allow_cross_l1:
            blocks -= {
                "cross_l1_override_requires_stage_a_score_gain",
                "missing_governance_clearance",
                "sensitive_override_requires_primary_hits",
                "sensitive_override_requires_stronger_explicit_support",
            }

    return stage_a_primary if blocks else winner_fqdn


def _accuracy(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


def build_records() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    labels_by_id: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for split, paths in DEFAULT_SPLITS.items():
        for row in _load_jsonl(paths["labels"]):
            labels_by_id[row["id"]] = row
        for sample in _load_jsonl(paths["trace"]):
            sample_id = sample["sample_id"]
            label = labels_by_id[sample_id]
            ground_truth = label["ground_truth_fqdn"]
            entry = {
                "id": sample_id,
                "split": split,
                "base_correct": int(sample["stage_b"]["selected_primary_fqdn"] == ground_truth),
                "conservative_correct": int(_simulate_primary(sample, "conservative") == ground_truth),
                "aggressive_correct": int(_simulate_primary(sample, "aggressive") == ground_truth),
            }
            records.append(entry)
    return records, labels_by_id


def _subset_summary(records: list[dict[str, Any]], selected_ids: set[str]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for mode_key in ("base", "conservative", "aggressive"):
        values = [row[f"{mode_key}_correct"] for row in records if row["id"] in selected_ids]
        correct = sum(values)
        total = len(values)
        summary[mode_key] = {
            "correct": correct,
            "total": total,
            "PrimaryAcc@1": _accuracy(correct, total),
        }
    return summary


def _select_best_mode(train_summary: dict[str, dict[str, Any]]) -> str:
    order = ("base", "conservative", "aggressive")
    return max(order, key=lambda mode: (train_summary[mode]["PrimaryAcc@1"], -order.index(mode)))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build retrospective Stage B train/test split and summaries.")
    parser.add_argument("--seed", type=int, default=20260331)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "artifacts" / "dataset" / "retrospective_stage_b_train_test_20260331"),
    )
    args = parser.parse_args()

    records, labels_by_id = build_records()
    rng = random.Random(args.seed)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[row["split"]].append(row)

    train_ids: set[str] = set()
    test_ids: set[str] = set()
    split_manifest: dict[str, Any] = {}
    for split, items in grouped.items():
        shuffled = items[:]
        rng.shuffle(shuffled)
        test_count = max(1, round(len(shuffled) * args.test_ratio))
        test_subset = shuffled[:test_count]
        train_subset = shuffled[test_count:]
        split_manifest[split] = {
            "samples": len(shuffled),
            "train": len(train_subset),
            "test": len(test_subset),
            "test_ratio": round(len(test_subset) / len(shuffled), 4),
        }
        train_ids.update(row["id"] for row in train_subset)
        test_ids.update(row["id"] for row in test_subset)

    train_summary = _subset_summary(records, train_ids)
    test_summary = _subset_summary(records, test_ids)
    selected_mode = _select_best_mode(train_summary)

    output_dir = Path(args.output_dir)
    train_rows = [labels_by_id[sample_id] for sample_id in sorted(train_ids)]
    test_rows = [labels_by_id[sample_id] for sample_id in sorted(test_ids)]
    test_breakdown: dict[str, Any] = {}
    for split in grouped:
        subset = {row["id"] for row in records if row["split"] == split and row["id"] in test_ids}
        test_breakdown[split] = _subset_summary(records, subset)

    _write_json(output_dir / "manifest.json", {
        "protocol": "retrospective_stratified_split",
        "seed": args.seed,
        "test_ratio": args.test_ratio,
        "split_sources": {
            split: {
                "labels": _repo_rel(paths["labels"]),
                "trace": _repo_rel(paths["trace"]),
            }
            for split, paths in DEFAULT_SPLITS.items()
        },
        "split_manifest": split_manifest,
        "train_samples": len(train_ids),
        "test_samples": len(test_ids),
        "selected_mode_on_train": selected_mode,
        "train_summary": train_summary,
        "test_summary": test_summary,
        "test_breakdown": test_breakdown,
    })
    _write_json(output_dir / "train_ids.json", sorted(train_ids))
    _write_json(output_dir / "test_ids.json", sorted(test_ids))
    _write_jsonl(output_dir / "train_joined.jsonl", train_rows)
    _write_jsonl(output_dir / "test_joined.jsonl", test_rows)
    _write_json(output_dir / "per_sample_correctness.json", records)

    print(json.dumps({
        "output_dir": str(output_dir),
        "selected_mode_on_train": selected_mode,
        "train_summary": train_summary,
        "test_summary": test_summary,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
