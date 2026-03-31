#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _winner_feedback(sample: dict[str, Any]) -> dict[str, Any] | None:
    feedback_scores = sample["stage_b"].get("feedback_scores", [])
    if not feedback_scores:
        return None
    return feedback_scores[0]


def _support_context(sample: dict[str, Any]) -> tuple[set[str], set[str], set[str], dict[str, Any]]:
    winner = _winner_feedback(sample)
    if not winner:
        return set(), set(), set(), {}
    support = set(winner.get("role_signal_support_families") or [])
    block = set(winner.get("role_signal_block_families") or [])
    tags = set((winner.get("override_basis_histogram") or {}).keys())
    flags = sample["stage_b"]["trust_trace"].get("sensitive_override_flags") or {}
    return support, block, tags, flags


def _simulate_primary(sample: dict[str, Any], mode: str) -> tuple[str | None, str]:
    stage_a_primary = sample["stage_a"].get("selected_primary_fqdn")
    winner = _winner_feedback(sample)
    if not winner:
        return stage_a_primary, "no_stage_b"
    winner_fqdn = winner["fqdn"]
    if winner_fqdn == stage_a_primary:
        return stage_a_primary, "keep_stage_a_top"

    blocks = set(sample["stage_b"]["trust_trace"].get("override_block_reasons") or [])
    support, signal_block, tags, flags = _support_context(sample)

    # Old vote-count style gates do not apply under responsibility-aware replay.
    blocks -= {"insufficient_round1_votes", "sensitive_override_requires_round2_consensus"}

    if mode in {"conservative", "aggressive"}:
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

    if blocks:
        return stage_a_primary, "|".join(sorted(blocks))
    return winner_fqdn, "override"


def _build_summary(
    traces: list[dict[str, Any]],
    labels_by_id: dict[str, dict[str, Any]],
    mode: str,
    trace_path: Path,
) -> dict[str, Any]:
    samples = 0
    primary_acc = 0
    acceptable_acc = 0
    changed = 0
    fixed = 0
    regressed = 0
    reasons = Counter()
    changes: list[dict[str, Any]] = []

    for sample in traces:
        sample_id = sample["sample_id"]
        label = labels_by_id[sample_id]
        stage_a_primary = sample["stage_a"].get("selected_primary_fqdn")
        simulated_primary, reason = _simulate_primary(sample, mode)
        reasons[reason] += 1
        samples += 1

        ground_truth = label["ground_truth_fqdn"]
        acceptable_fqdns = set(label.get("acceptable_fqdns") or [])
        if simulated_primary == ground_truth:
            primary_acc += 1
        if simulated_primary == ground_truth or simulated_primary in acceptable_fqdns:
            acceptable_acc += 1

        if simulated_primary != stage_a_primary:
            changed += 1
            if stage_a_primary != ground_truth and simulated_primary == ground_truth:
                fixed += 1
            if stage_a_primary == ground_truth and simulated_primary != ground_truth:
                regressed += 1
            changes.append(
                {
                    "sample_id": sample_id,
                    "stage_a_primary_fqdn": stage_a_primary,
                    "stage_b_trace_primary_fqdn": sample["stage_b"].get("selected_primary_fqdn"),
                    "simulated_primary_fqdn": simulated_primary,
                    "ground_truth_fqdn": ground_truth,
                    "reason": reason,
                    "sensitive_override_flags": sample["stage_b"]["trust_trace"].get("sensitive_override_flags"),
                }
            )

    return {
        "replay_mode": mode,
        "trace_path": str(trace_path),
        "samples": samples,
        "PrimaryAcc@1": round(primary_acc / samples, 4) if samples else 0.0,
        "AcceptablePrimary@1": round(acceptable_acc / samples, 4) if samples else 0.0,
        "stage_b_changed_primary": changed,
        "stage_b_fixed_primary": fixed,
        "stage_b_regressed_primary": regressed,
        "reason_histogram": dict(reasons),
        "changed_samples": changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay Stage B gate variants from an existing hetero-v3 trace.")
    parser.add_argument("--trace", required=True, help="Path to Stage B trace JSONL.")
    parser.add_argument("--labels", required=True, help="Path to joined dataset JSONL with labels.")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("responsibility_only", "conservative", "aggressive"),
        help=(
            "Gate replay mode: responsibility_only drops old vote-count gates; "
            "conservative also relaxes same-l1/hierarchy/high-risk internal fixes; "
            "aggressive also relaxes cross-l1 overrides."
        ),
    )
    parser.add_argument("--output", help="Optional path to write summary JSON.")
    args = parser.parse_args()

    trace_path = Path(args.trace)
    label_path = Path(args.labels)
    traces = _load_jsonl(trace_path)
    labels = _load_jsonl(label_path)
    labels_by_id = {row["id"]: row for row in labels}

    summary = _build_summary(traces, labels_by_id, args.mode, trace_path)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
