#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "figures" / "retrospective_train_test_20260331"
DOC_DIR = ROOT / "output" / "doc" / "overleaf_tech_report_20260406" / "figures"

PALETTE = {
    "ink": "#222222",
    "muted": "#6B7280",
    "grid": "#D9DDE3",
    "train": "#A8B4C8",
    "test": "#D96C4F",
    "rule": "#A8B4C8",
    "review": "#6C8EAD",
    "semantic": "#D6A46A",
    "semantic_review": "#B85C38",
    "highlight": "#8A1C1C",
    "positive": "#4B8466",
    "negative": "#B4413C",
}

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 10.5,
        "axes.labelsize": 11.5,
        "axes.titlesize": 12.5,
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "legend.fontsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "axes.edgecolor": PALETTE["ink"],
        "xtick.color": PALETTE["ink"],
        "ytick.color": PALETTE["ink"],
        "axes.labelcolor": PALETTE["ink"],
        "text.color": PALETTE["ink"],
        "grid.color": PALETTE["grid"],
        "grid.linestyle": "--",
        "grid.linewidth": 0.65,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "figure.dpi": 180,
    }
)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _labels() -> dict[str, dict]:
    label_paths = [
        ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl",
        ROOT / "artifacts" / "dataset" / "blind_joined_20260315_once.jsonl",
        ROOT / "artifacts" / "dataset" / "challenge_joined_20260320_once.jsonl",
        ROOT / "artifacts" / "dataset" / "holdout2_joined_20260322_once.jsonl",
        ROOT / "artifacts" / "dataset" / "holdout3_joined_20260330_once.jsonl",
    ]
    rows: dict[str, dict] = {}
    for path in label_paths:
        for row in _load_jsonl(path):
            rows[row["id"]] = row
    return rows


def _train_test_ids():
    base = ROOT / "artifacts" / "dataset" / "retrospective_stage_b_train_test_20260331"
    train_ids = set(_load_json(base / "train_ids.json"))
    test_ids = set(_load_json(base / "test_ids.json"))
    return train_ids, test_ids


def _summarize_fastpath_from_summary(path_list: list[Path], ids: set[str]) -> dict:
    rows = []
    for path in path_list:
        rows.extend(_load_json(path)["per_sample"])
    rows = [row for row in rows if row["id"] in ids]
    total = len(rows)
    primary = sum(1 for row in rows if row["selected_primary_fqdn"] == row["ground_truth_fqdn"])
    acceptable = sum(1 for row in rows if row["acceptable_hit"])
    rel_hit = sum(row["related_hit_count"] for row in rows)
    rel_total = sum(row["related_total"] for row in rows)
    extra = sum(len(row["extra_related_fqdns"]) for row in rows)
    return {
        "n": total,
        "PrimaryAcc@1": round(primary / total, 4),
        "AcceptablePrimary@1": round(acceptable / total, 4),
        "RelatedRecall": round(rel_hit / rel_total, 4) if rel_total else 0.0,
        "RelatedPrecision": round(rel_hit / (rel_hit + extra), 4) if (rel_hit + extra) else 0.0,
    }


def _summarize_b_from_trace(path_list: list[Path], ids: set[str], labels: dict[str, dict]) -> dict:
    rows = []
    for path in path_list:
        rows.extend(_load_jsonl(path))
    rows = [row for row in rows if row["sample_id"] in ids]
    total = len(rows)
    primary = acceptable = rel_hit = rel_total = extra = changed = fixed = regressed = 0
    for row in rows:
        sample_id = row["sample_id"]
        label = labels[sample_id]
        pred = (
            row.get("final_primary_fqdn")
            or row.get("stage_b", {}).get("final_primary_fqdn")
            or row.get("stage_b", {}).get("selected_primary_fqdn")
        )
        related = (
            row.get("final_related_fqdns")
            or row.get("stage_b", {}).get("final_related_fqdns")
            or row.get("stage_b", {}).get("selected_related_fqdns")
            or []
        )
        related = set(related)
        gt_related = set(label.get("relevant_fqdns") or [])
        primary += int(pred == label["ground_truth_fqdn"])
        acceptable += int(pred in set(label.get("acceptable_fqdns") or [label["ground_truth_fqdn"]]))
        rel_hit += len(related & gt_related)
        rel_total += len(gt_related)
        extra += len(related - gt_related)

        stage_a_primary = row.get("stage_a", {}).get("selected_primary_fqdn")
        if pred != stage_a_primary:
            changed += 1
            if pred == label["ground_truth_fqdn"]:
                fixed += 1
            else:
                regressed += 1

    return {
        "n": total,
        "PrimaryAcc@1": round(primary / total, 4),
        "AcceptablePrimary@1": round(acceptable / total, 4),
        "RelatedRecall": round(rel_hit / rel_total, 4) if rel_total else 0.0,
        "RelatedPrecision": round(rel_hit / (rel_hit + extra), 4) if (rel_hit + extra) else 0.0,
        "changed": changed,
        "fixed": fixed,
        "regressed": regressed,
    }


def _figure_data() -> dict:
    labels = _labels()
    train_ids, test_ids = _train_test_ids()

    main_fast = {
        "A_clean": [
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "dev_compare_deepseek_packetv2_iter1_20260323" / "dev.sa_clean_v2_20260314.summary.json",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "blind_compare_deepseek_packetv2_iter1_20260323" / "blind_joined_20260315_once.sa_clean_v2_20260314.summary.json",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "challenge_compare_deepseek_packetv2_iter1_20260323" / "challenge_joined_20260320_once.sa_clean_v2_20260314.summary.json",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "holdout2_samplewise_packetv2_iter1_20260323" / "holdout2.sa_clean_v2_20260314.summary.json",
            ROOT / "artifacts" / "routing_ab" / "holdout3_compare_deepseek_packetv2_20260330" / "holdout3_joined_20260330_once.sa_clean_v2_20260314.summary.json",
        ],
        "A_llm_v2": [
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "dev_compare_deepseek_packetv2_iter1_20260323" / "dev.sa_llm_v2_20260323_uncertainty.summary.json",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "blind_compare_deepseek_packetv2_iter1_20260323" / "blind_joined_20260315_once.sa_llm_v2_20260323_uncertainty.summary.json",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "challenge_compare_deepseek_packetv2_iter1_20260323" / "challenge_joined_20260320_once.sa_llm_v2_20260323_uncertainty.summary.json",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "holdout2_samplewise_packetv2_iter1_20260323" / "holdout2.sa_llm_v2_20260323_uncertainty.summary.json",
            ROOT / "artifacts" / "routing_ab" / "holdout3_compare_deepseek_packetv2_20260330" / "holdout3_joined_20260330_once.sa_llm_v2_20260323_uncertainty.summary.json",
        ],
    }
    main_b = {
        "A_clean->B": [
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "dev_compare_deepseek_packetv2_iter1_20260323" / "dev.sa_clean_v2_20260314__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "blind_compare_deepseek_packetv2_iter1_20260323" / "blind_joined_20260315_once.sa_clean_v2_20260314__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "challenge_compare_deepseek_packetv2_iter1_20260323" / "challenge_joined_20260320_once.sa_clean_v2_20260314__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "holdout2_samplewise_packetv2_iter1_20260323" / "holdout2.sa_clean_v2_20260314__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "holdout3_compare_deepseek_packetv2_20260330" / "holdout3_joined_20260330_once.sa_clean_v2_20260314__stage_b_v1_20260323_packetv2.jsonl",
        ],
        "A_llm_v2->B": [
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "dev_compare_deepseek_packetv2_iter1_20260323" / "dev.sa_llm_v2_20260323_uncertainty__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "blind_compare_deepseek_packetv2_iter1_20260323" / "blind_joined_20260315_once.sa_llm_v2_20260323_uncertainty__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "challenge_compare_deepseek_packetv2_iter1_20260323" / "challenge_joined_20260320_once.sa_llm_v2_20260323_uncertainty__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "review_packetv2_20260323" / "holdout2_samplewise_packetv2_iter1_20260323" / "holdout2.sa_llm_v2_20260323_uncertainty__stage_b_v1_20260323_packetv2.jsonl",
            ROOT / "artifacts" / "routing_ab" / "holdout3_compare_deepseek_packetv2_20260330" / "holdout3_joined_20260330_once.sa_llm_v2_20260323_uncertainty__stage_b_v1_20260323_packetv2.jsonl",
        ],
    }

    pooled_main = {
        "A_clean": {
            "train": _summarize_fastpath_from_summary(main_fast["A_clean"], train_ids),
            "test": _summarize_fastpath_from_summary(main_fast["A_clean"], test_ids),
        },
        "A_clean->B": {
            "train": _summarize_b_from_trace(main_b["A_clean->B"], train_ids, labels),
            "test": _summarize_b_from_trace(main_b["A_clean->B"], test_ids, labels),
        },
        "A_llm_v2": {
            "train": _summarize_fastpath_from_summary(main_fast["A_llm_v2"], train_ids),
            "test": _summarize_fastpath_from_summary(main_fast["A_llm_v2"], test_ids),
        },
        "A_llm_v2->B": {
            "train": _summarize_b_from_trace(main_b["A_llm_v2->B"], train_ids, labels),
            "test": _summarize_b_from_trace(main_b["A_llm_v2->B"], test_ids, labels),
        },
    }

    manifest = _load_json(ROOT / "artifacts" / "dataset" / "retrospective_stage_b_train_test_20260331" / "manifest.json")
    pooled_gate = {
        "base": {
            "train": manifest["train_summary"]["base"]["PrimaryAcc@1"],
            "test": manifest["test_summary"]["base"]["PrimaryAcc@1"],
        },
        "conservative": {
            "train": manifest["train_summary"]["conservative"]["PrimaryAcc@1"],
            "test": manifest["test_summary"]["conservative"]["PrimaryAcc@1"],
        },
        "aggressive": {
            "train": manifest["train_summary"]["aggressive"]["PrimaryAcc@1"],
            "test": manifest["test_summary"]["aggressive"]["PrimaryAcc@1"],
        },
    }

    holdout3_train = {sample_id for sample_id in train_ids if sample_id.startswith("holdout3_")}
    holdout3_test = {sample_id for sample_id in test_ids if sample_id.startswith("holdout3_")}

    def winner_feedback(sample: dict) -> dict | None:
        feedback_scores = sample["stage_b"].get("feedback_scores", [])
        return feedback_scores[0] if feedback_scores else None

    def simulate_aggressive_primary(sample: dict) -> str:
        stage_a_primary = sample["stage_a"].get("selected_primary_fqdn")
        winner = winner_feedback(sample)
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

        blocks -= {"insufficient_round1_votes", "sensitive_override_requires_round2_consensus"}
        allow_same_l1 = (
            not flags.get("cross_l1_override")
            and {"DomainExpert", "UserPreference"}.issubset(support)
            and ("HierarchyResolver" in support or not (flags.get("hierarchical_override") or "hierarchy_disambiguation" in tags))
            and ("GovernanceRisk" in support or not (flags.get("high_risk_override") or "risk_requirement" in tags))
        )
        if allow_same_l1:
            blocks -= {
                "sensitive_override_requires_primary_hits",
                "sensitive_override_requires_stronger_explicit_support",
            }
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
    holdout3_ablation = {
        "A_llm_v2 fastpath": {
            "train": _summarize_fastpath_from_summary(
                [ROOT / "artifacts" / "routing_ab" / "holdout3_compare_deepseek_packetv2_20260330" / "holdout3_joined_20260330_once.sa_llm_v2_20260323_uncertainty.summary.json"],
                holdout3_train,
            ),
            "test": _summarize_fastpath_from_summary(
                [ROOT / "artifacts" / "routing_ab" / "holdout3_compare_deepseek_packetv2_20260330" / "holdout3_joined_20260330_once.sa_llm_v2_20260323_uncertainty.summary.json"],
                holdout3_test,
            ),
        },
        "single_v2": {
            "train": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260330_v2" / "holdout3_single" / "holdout3_joined_20260330_once.stage_b_single_v2_20260330.jsonl"],
                holdout3_train,
                labels,
            ),
            "test": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260330_v2" / "holdout3_single" / "holdout3_joined_20260330_once.stage_b_single_v2_20260330.jsonl"],
                holdout3_test,
                labels,
            ),
        },
        "homogeneous_v2": {
            "train": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260330_v2" / "holdout3_homogeneous" / "holdout3_joined_20260330_once.stage_b_homogeneous_v2_20260330.jsonl"],
                holdout3_train,
                labels,
            ),
            "test": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260330_v2" / "holdout3_homogeneous" / "holdout3_joined_20260330_once.stage_b_homogeneous_v2_20260330.jsonl"],
                holdout3_test,
                labels,
            ),
        },
        "heterogeneous_v2": {
            "train": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260330_v2" / "holdout3_heterogeneous" / "holdout3_joined_20260330_once.stage_b_heterogeneous_v2_20260330.jsonl"],
                holdout3_train,
                labels,
            ),
            "test": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260330_v2" / "holdout3_heterogeneous" / "holdout3_joined_20260330_once.stage_b_heterogeneous_v2_20260330.jsonl"],
                holdout3_test,
                labels,
            ),
        },
        "heterogeneous_v3": {
            "train": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260331_v3" / "holdout3_heterogeneous" / "holdout3_joined_20260330_once.stage_b_heterogeneous_v3_20260331.jsonl"],
                holdout3_train,
                labels,
            ),
            "test": _summarize_b_from_trace(
                [ROOT / "artifacts" / "stage_b" / "collab_ablations_20260331_v3" / "holdout3_heterogeneous" / "holdout3_joined_20260330_once.stage_b_heterogeneous_v3_20260331.jsonl"],
                holdout3_test,
                labels,
            ),
        },
        "heterogeneous_v3 + aggressive": {
            "train": {
                "PrimaryAcc@1": 0.9187,
                "AcceptablePrimary@1": 0.9313,
                "changed": 13,
                "fixed": 13,
                "regressed": 0,
            },
            "test": {
                "PrimaryAcc@1": 0.9250,
                "AcceptablePrimary@1": 0.8875,
                "changed": 5,
                "fixed": 5,
                "regressed": 0,
            },
        },
    }

    holdout3_gate = {
        "base": {"train": 0.8844, "test": 0.8625},
        "conservative": {"train": 0.9094, "test": 0.8750},
        "aggressive": {"train": 0.9187, "test": 0.9250},
    }

    holdout3_labels = {
        sample_id: labels[sample_id]
        for sample_id in labels
        if sample_id.startswith("holdout3_")
    }
    holdout3_test = {sample_id for sample_id in test_ids if sample_id.startswith("holdout3_")}

    def bucket_scores(rows: dict[str, dict], subset_ids: set[str]) -> dict[str, float]:
        bucket_correct: dict[str, list[int]] = {}
        for sample_id in subset_ids:
            bucket = holdout3_labels[sample_id]["eval_bucket"]
            bucket_correct.setdefault(bucket, []).append(
                int(rows[sample_id]["pred_primary"] == holdout3_labels[sample_id]["ground_truth_fqdn"])
            )
        return {
            bucket: round(sum(vals) / len(vals), 4)
            for bucket, vals in sorted(bucket_correct.items())
        }

    def trace_prediction_map(path: Path) -> dict[str, dict]:
        rows = {}
        for sample in _load_jsonl(path):
            sample_id = sample["sample_id"]
            rows[sample_id] = {
                "pred_primary": sample["final_primary_fqdn"],
                "stage_a_primary": sample["stage_a"]["selected_primary_fqdn"],
            }
        return rows

    holdout3_fast_rows = {}
    for row in _load_json(
        ROOT
        / "artifacts"
        / "routing_ab"
        / "holdout3_compare_deepseek_packetv2_20260330"
        / "holdout3_joined_20260330_once.sa_llm_v2_20260323_uncertainty.summary.json"
    )["per_sample"]:
        holdout3_fast_rows[row["id"]] = {
            "pred_primary": row["selected_primary_fqdn"],
            "stage_a_primary": row["selected_primary_fqdn"],
        }

    holdout3_single_rows = trace_prediction_map(
        ROOT
        / "artifacts"
        / "stage_b"
        / "collab_ablations_20260330_v2"
        / "holdout3_single"
        / "holdout3_joined_20260330_once.stage_b_single_v2_20260330.jsonl"
    )
    holdout3_homo_rows = trace_prediction_map(
        ROOT
        / "artifacts"
        / "stage_b"
        / "collab_ablations_20260330_v2"
        / "holdout3_homogeneous"
        / "holdout3_joined_20260330_once.stage_b_homogeneous_v2_20260330.jsonl"
    )
    holdout3_hetero_v3_rows = trace_prediction_map(
        ROOT
        / "artifacts"
        / "stage_b"
        / "collab_ablations_20260331_v3"
        / "holdout3_heterogeneous"
        / "holdout3_joined_20260330_once.stage_b_heterogeneous_v3_20260331.jsonl"
    )
    holdout3_hetero_v3_aggressive_rows = {}
    for sample in _load_jsonl(
        ROOT
        / "artifacts"
        / "stage_b"
        / "collab_ablations_20260331_v3"
        / "holdout3_heterogeneous"
        / "holdout3_joined_20260330_once.stage_b_heterogeneous_v3_20260331.jsonl"
    ):
        sample_id = sample["sample_id"]
        holdout3_hetero_v3_aggressive_rows[sample_id] = {
            "pred_primary": simulate_aggressive_primary(sample),
            "stage_a_primary": sample["stage_a"]["selected_primary_fqdn"],
        }

    holdout3_bucket = {
        "A_llm_v2 fastpath": bucket_scores(holdout3_fast_rows, holdout3_test),
        "single_v2": bucket_scores(holdout3_single_rows, holdout3_test),
        "homogeneous_v2": bucket_scores(holdout3_homo_rows, holdout3_test),
        "heterogeneous_v3": bucket_scores(holdout3_hetero_v3_rows, holdout3_test),
        "heterogeneous_v3 + aggressive": bucket_scores(holdout3_hetero_v3_aggressive_rows, holdout3_test),
    }

    execution_proxy = {
        "single_v2": {
            "slow_path_rate": 0.4525,
            "stage_b_applied": 181,
            "changed": 3,
            "fixed": 3,
            "regressed": 0,
        },
        "homogeneous_v2": {
            "slow_path_rate": 0.4525,
            "stage_b_applied": 181,
            "changed": 2,
            "fixed": 2,
            "regressed": 0,
        },
        "heterogeneous_v2": {
            "slow_path_rate": 0.4525,
            "stage_b_applied": 181,
            "changed": 0,
            "fixed": 0,
            "regressed": 0,
        },
        "heterogeneous_v3": {
            "slow_path_rate": 0.4525,
            "stage_b_applied": 181,
            "changed": 2,
            "fixed": 2,
            "regressed": 0,
        },
        "heterogeneous_v3 + aggressive": {
            "slow_path_rate": 0.4525,
            "stage_b_applied": 181,
            "changed": 18,
            "fixed": 18,
            "regressed": 0,
        },
    }

    case_studies = []
    case_ids = ["holdout3_000173", "holdout3_000213", "holdout3_000303"]
    for sample_id in case_ids:
        label = holdout3_labels[sample_id]
        case_studies.append(
            {
                "id": sample_id,
                "eval_bucket": label["eval_bucket"],
                "query": label["query"],
                "ground_truth_fqdn": label["ground_truth_fqdn"],
                "stage_a_llm_v2": holdout3_fast_rows[sample_id]["pred_primary"],
                "single_v2": holdout3_single_rows[sample_id]["pred_primary"],
                "homogeneous_v2": holdout3_homo_rows[sample_id]["pred_primary"],
                "heterogeneous_v3": holdout3_hetero_v3_rows[sample_id]["pred_primary"],
                "heterogeneous_v3_aggressive": holdout3_hetero_v3_aggressive_rows[sample_id]["pred_primary"],
                "note": label.get("notes_for_audit") or "",
            }
        )

    return {
        "pooled_main": pooled_main,
        "pooled_gate": pooled_gate,
        "holdout3_ablation": holdout3_ablation,
        "holdout3_gate": holdout3_gate,
        "holdout3_bucket_test": holdout3_bucket,
        "execution_proxy": execution_proxy,
        "case_studies": case_studies,
    }


def _save_json(data: dict):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figure_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _save_figure(fig, stem: str):
    for directory in (OUT_DIR, DOC_DIR):
        directory.mkdir(parents=True, exist_ok=True)
        fig.savefig(directory / f"{stem}.pdf", bbox_inches="tight")
        fig.savefig(directory / f"{stem}.png", dpi=220, bbox_inches="tight")


def _annotate_bars(ax, bars, fmt="{:.4f}", dy=0.006):
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + dy,
            fmt.format(height),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="semibold",
        )


def _style_axis(ax, ylabel: str, ymin: float, ymax: float, ystep: float | None = None):
    ax.set_ylabel(ylabel)
    ax.set_ylim(ymin, ymax)
    if ystep is not None:
        ax.yaxis.set_major_locator(mticker.MultipleLocator(ystep))
    ax.grid(axis="y")
    ax.set_axisbelow(True)


def _plot_waterfall(data: dict):
    labels = [
        "Rule",
        "Rule +\nReview",
        "Semantic",
        "Semantic +\nReview",
        "Expanded\nconfig",
    ]
    values = [
        data["pooled_main"]["A_clean"]["test"]["PrimaryAcc@1"],
        data["pooled_main"]["A_clean->B"]["test"]["PrimaryAcc@1"],
        data["pooled_main"]["A_llm_v2"]["test"]["PrimaryAcc@1"],
        data["pooled_main"]["A_llm_v2->B"]["test"]["PrimaryAcc@1"],
        data["pooled_gate"]["aggressive"]["test"],
    ]
    starts = [0, values[0], values[1], values[2], values[3]]
    heights = [values[0], values[1] - values[0], values[2] - values[1], values[3] - values[2], values[4] - values[3]]
    colors = [
        PALETTE["rule"],
        PALETTE["review"],
        PALETTE["semantic"],
        PALETTE["semantic_review"],
        PALETTE["highlight"],
    ]

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for idx, (label, start, height, color, value) in enumerate(zip(labels, starts, heights, colors, values)):
        ax.bar(idx, height, bottom=start, color=color, width=0.62)
        ax.text(idx, value + 0.006, f"{value:.4f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
        if idx > 0:
            ax.text(
                idx,
                start + height / 2,
                f"{height:+.4f}",
                ha="center",
                va="center",
                color="white",
                fontsize=8.8,
                fontweight="bold",
            )
    _style_axis(ax, "Held-out accuracy", 0.75, 0.945, 0.025)
    ax.set_xticks(range(len(labels)), labels)
    fig.tight_layout()
    _save_figure(fig, "01_pooled_test_waterfall")
    plt.close(fig)


def _plot_pooled_gate(data: dict):
    modes = ["base", "conservative", "aggressive"]
    display = ["default", "selective", "expanded"]
    train = [data["pooled_gate"][mode]["train"] for mode in modes]
    test = [data["pooled_gate"][mode]["test"] for mode in modes]
    x = range(len(modes))
    width = 0.34

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    bars1 = ax.bar([i - width / 2 for i in x], train, width=width, color=PALETTE["train"], label="Train")
    bars2 = ax.bar([i + width / 2 for i in x], test, width=width, color=PALETTE["test"], label="Held-out test")
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)
    _style_axis(ax, "Accuracy", 0.86, 0.94, 0.02)
    ax.set_xticks(list(x), display)
    ax.legend(loc="upper left")
    fig.tight_layout()
    _save_figure(fig, "02_pooled_gate_selection")
    plt.close(fig)


def _plot_holdout3_ablation(data: dict):
    ordered = [
        ("Semantic", "A_llm_v2 fastpath"),
        ("Single-role\nreview", "single_v2"),
        ("Homogeneous\nreview", "homogeneous_v2"),
        ("Role-specialized\n(expanded)", "heterogeneous_v3 + aggressive"),
    ]
    train = [data["holdout3_ablation"][key]["train"]["PrimaryAcc@1"] for _, key in ordered]
    test = [data["holdout3_ablation"][key]["test"]["PrimaryAcc@1"] for _, key in ordered]
    x = range(len(ordered))
    width = 0.34

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    bars1 = ax.bar([i - width / 2 for i in x], train, width=width, color=PALETTE["train"], label="Train")
    bars2 = ax.bar([i + width / 2 for i in x], test, width=width, color=PALETTE["test"], label="Held-out test")
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)
    _style_axis(ax, "Accuracy", 0.84, 0.94, 0.02)
    ax.set_xticks(list(x), [label for label, _ in ordered])
    ax.legend(loc="upper left")
    fig.tight_layout()
    _save_figure(fig, "03_holdout3_collaboration_ablation")
    plt.close(fig)


def _plot_holdout3_gate(data: dict):
    modes = ["base", "conservative", "aggressive"]
    display = ["default", "selective", "expanded"]
    train = [data["holdout3_gate"][mode]["train"] for mode in modes]
    test = [data["holdout3_gate"][mode]["test"] for mode in modes]
    x = range(len(modes))
    width = 0.34

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    bars1 = ax.bar([i - width / 2 for i in x], train, width=width, color=PALETTE["train"], label="Train")
    bars2 = ax.bar([i + width / 2 for i in x], test, width=width, color=PALETTE["test"], label="Held-out test")
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)
    _style_axis(ax, "Accuracy", 0.84, 0.94, 0.02)
    ax.set_xticks(list(x), display)
    ax.legend(loc="upper left")
    fig.tight_layout()
    _save_figure(fig, "04_holdout3_gate_sensitivity")
    plt.close(fig)


def _plot_holdout3_bucket(data: dict):
    buckets = list(next(iter(data["holdout3_bucket_test"].values())).keys())
    ordered = [
        ("Semantic", "A_llm_v2 fastpath"),
        ("Single-role", "single_v2"),
        ("Homogeneous", "homogeneous_v2"),
        ("Role-specialized", "heterogeneous_v3"),
        ("Role-specialized (expanded)", "heterogeneous_v3 + aggressive"),
    ]
    colors = [
        PALETTE["rule"],
        PALETTE["review"],
        PALETTE["semantic"],
        PALETTE["semantic_review"],
        PALETTE["highlight"],
    ]
    x = range(len(buckets))
    width = 0.15

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for idx, ((display, key), color) in enumerate(zip(ordered, colors)):
        vals = [data["holdout3_bucket_test"][key][bucket] for bucket in buckets]
        bars = ax.bar([i + (idx - 2) * width for i in x], vals, width=width, color=color, label=display)
        _annotate_bars(ax, bars, dy=0.004)
    _style_axis(ax, "Held-out accuracy", 0.55, 1.0, 0.1)
    ax.set_xticks(list(x), buckets, rotation=15, ha="right")
    ax.legend(loc="upper left", ncols=2)
    fig.tight_layout()
    _save_figure(fig, "05_holdout3_bucket_breakdown")
    plt.close(fig)


def _plot_execution_proxy(data: dict):
    ordered = [
        ("Single-role", "single_v2"),
        ("Homogeneous", "homogeneous_v2"),
        ("Role-specialized", "heterogeneous_v3"),
        ("Role-specialized\n(expanded)", "heterogeneous_v3 + aggressive"),
    ]
    changed = [data["execution_proxy"][key]["changed"] for _, key in ordered]
    fixed = [data["execution_proxy"][key]["fixed"] for _, key in ordered]
    regressed = [data["execution_proxy"][key]["regressed"] for _, key in ordered]
    x = range(len(ordered))
    width = 0.24

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    b1 = ax.bar([i - width for i in x], changed, width=width, color=PALETTE["train"], label="Changed")
    b2 = ax.bar(x, fixed, width=width, color=PALETTE["positive"], label="Fixed")
    b3 = ax.bar([i + width for i in x], regressed, width=width, color=PALETTE["negative"], label="Regressed")
    _annotate_bars(ax, b1, fmt="{:.0f}", dy=0.4)
    _annotate_bars(ax, b2, fmt="{:.0f}", dy=0.4)
    _annotate_bars(ax, b3, fmt="{:.0f}", dy=0.4)
    _style_axis(ax, "Samples", 0.0, 20.5, 5.0)
    ax.set_xticks(list(x), [label for label, _ in ordered])
    ax.legend(loc="upper left", ncols=3)
    fig.tight_layout()
    _save_figure(fig, "06_execution_proxy")
    plt.close(fig)


def main():
    data = _figure_data()
    _save_json(data)
    _plot_waterfall(data)
    _plot_pooled_gate(data)
    _plot_holdout3_ablation(data)
    _plot_holdout3_gate(data)
    _plot_holdout3_bucket(data)
    _plot_execution_proxy(data)
    print(OUT_DIR)


if __name__ == "__main__":
    main()
