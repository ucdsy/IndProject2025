#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "figures" / "retrospective_train_test_20260331"
GJTX_DOC_DIR = ROOT / "output" / "doc" / "gjtx_submission_20260413" / "figures"
SPLIT_DIR = ROOT / "artifacts" / "dataset" / "retrospective_stage_b_train_test_20260331"

PALETTE = {
    "ink": "#222222",
    "muted": "#6B7280",
    "grid": "#D9DDE3",
    "rule": "#8C98A8",
    "semantic": "#D6A46A",
    "review": "#B85C38",
    "expanded": "#8A1C1C",
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [
            "PingFang SC",
            "Songti SC",
            "Heiti SC",
            "STHeiti",
            "Arial Unicode MS",
            "DejaVu Sans",
        ],
        "font.size": 10.5,
        "axes.labelsize": 11.5,
        "axes.titlesize": 12.5,
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "legend.fontsize": 9.8,
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
        "axes.unicode_minus": False,
    }
)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _test_ids() -> list[str]:
    return list(_load_json(SPLIT_DIR / "test_ids.json"))


def _summary_paths(stage_a_name: str) -> list[Path]:
    base = ROOT / "artifacts" / "routing_ab"
    return [
        base
        / "review_packetv2_20260323"
        / "dev_compare_deepseek_packetv2_iter1_20260323"
        / f"dev.{stage_a_name}.summary.json",
        base
        / "review_packetv2_20260323"
        / "blind_compare_deepseek_packetv2_iter1_20260323"
        / f"blind_joined_20260315_once.{stage_a_name}.summary.json",
        base
        / "review_packetv2_20260323"
        / "challenge_compare_deepseek_packetv2_iter1_20260323"
        / f"challenge_joined_20260320_once.{stage_a_name}.summary.json",
        base
        / "review_packetv2_20260323"
        / "holdout2_samplewise_packetv2_iter1_20260323"
        / f"holdout2.{stage_a_name}.summary.json",
        base
        / "holdout3_compare_deepseek_packetv2_20260330"
        / f"holdout3_joined_20260330_once.{stage_a_name}.summary.json",
    ]


def _correctness_from_summaries(stage_a_name: str, test_ids: list[str]) -> np.ndarray:
    rows = []
    for path in _summary_paths(stage_a_name):
        rows.extend(_load_json(path)["per_sample"])
    by_id = {
        row["id"]: int(row["selected_primary_fqdn"] == row["ground_truth_fqdn"])
        for row in rows
    }
    missing = [sample_id for sample_id in test_ids if sample_id not in by_id]
    if missing:
        raise ValueError(f"missing summary rows for {stage_a_name}: {missing[:5]}")
    return np.array([by_id[sample_id] for sample_id in test_ids], dtype=float)


def _correctness_from_gate(field: str, test_ids: list[str]) -> np.ndarray:
    rows = _load_json(SPLIT_DIR / "per_sample_correctness.json")
    by_id = {row["id"]: float(row[field]) for row in rows}
    missing = [sample_id for sample_id in test_ids if sample_id not in by_id]
    if missing:
        raise ValueError(f"missing gate rows for {field}: {missing[:5]}")
    return np.array([by_id[sample_id] for sample_id in test_ids], dtype=float)


def _stability_records(methods: dict[str, np.ndarray]) -> list[dict]:
    n = len(next(iter(methods.values())))
    sizes = [20, 40, 60, 80, 100, n]
    repeats = 2000
    rng = np.random.default_rng(20260429)
    records: list[dict] = []

    for size in sizes:
        if size == n:
            sampled = [np.arange(n)]
        else:
            sampled = [rng.choice(n, size=size, replace=False) for _ in range(repeats)]

        for name, values in methods.items():
            scores = np.array([values[idx].mean() for idx in sampled])
            records.append(
                {
                    "method": name,
                    "sample_size": size,
                    "mean": float(scores.mean()),
                    "ci_low": float(np.quantile(scores, 0.025)),
                    "ci_high": float(np.quantile(scores, 0.975)),
                    "full_test_accuracy": float(values.mean()),
                }
            )
    return records


def _write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["method", "sample_size", "mean", "ci_low", "ci_high", "full_test_accuracy"],
        )
        writer.writeheader()
        writer.writerows(records)


def _plot(records: list[dict], path_base: Path) -> None:
    order = [
        ("规则路由", PALETTE["rule"], "-", "o"),
        ("结构化语义路由", PALETTE["semantic"], "-", "s"),
        ("默认协作复核", PALETTE["review"], "-", "^"),
        ("扩展配置（补充）", PALETTE["expanded"], "--", "D"),
    ]
    offsets = [-1.5, -0.5, 0.5, 1.5]

    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    for (method, color, linestyle, marker), offset in zip(order, offsets):
        rows = [row for row in records if row["method"] == method]
        xs = np.array([row["sample_size"] for row in rows])
        xs_plot = xs + offset
        mean = np.array([row["mean"] for row in rows])
        low = np.array([row["ci_low"] for row in rows])
        high = np.array([row["ci_high"] for row in rows])
        yerr = np.vstack([mean - low, high - mean])
        ax.errorbar(
            xs_plot,
            mean,
            yerr=yerr,
            color=color,
            linestyle=linestyle,
            marker=marker,
            markersize=5.2,
            linewidth=2.0,
            elinewidth=1.0,
            capsize=2.8,
            capthick=1.0,
            label=method,
        )

    ax.set_title("不同评测样本规模下准确率估计的稳定性")
    ax.set_xlabel("评测样本数")
    ax.set_ylabel("主标签准确率")
    ax.set_xlim(18, 115)
    ax.set_ylim(0.55, 1.02)
    ax.set_xticks([20, 40, 60, 80, 100, 113])
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    ax.grid(axis="y")
    ax.legend(loc="lower right", ncols=2)
    ax.text(
        20,
        0.565,
        "误差棒为固定测试集随机子采样的95%区间；虚线为补充配置结果。",
        fontsize=9.2,
        color=PALETTE["muted"],
    )
    fig.tight_layout()
    path_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(path_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    test_ids = _test_ids()
    methods = {
        "规则路由": _correctness_from_summaries("sa_clean_v2_20260314", test_ids),
        "结构化语义路由": _correctness_from_summaries(
            "sa_llm_v2_20260323_uncertainty", test_ids
        ),
        "默认协作复核": _correctness_from_gate("base_correct", test_ids),
        "扩展配置（补充）": _correctness_from_gate("aggressive_correct", test_ids),
    }
    records = _stability_records(methods)
    csv_path = OUT_DIR / "07_eval_scale_stability.csv"
    figure_base = OUT_DIR / "07_eval_scale_stability"
    _write_csv(records, csv_path)
    _plot(records, figure_base)

    GJTX_DOC_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in [".png", ".pdf"]:
        shutil.copy2(figure_base.with_suffix(suffix), GJTX_DOC_DIR / f"07_eval_scale_stability{suffix}")

    print(figure_base.with_suffix(".png"))
    print(csv_path)


if __name__ == "__main__":
    main()
