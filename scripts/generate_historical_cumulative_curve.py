#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / "tmp" / "matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


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


def _fastpath_correct(stage_a_name: str) -> dict[str, int]:
    rows = []
    for path in _summary_paths(stage_a_name):
        rows.extend(_load_json(path)["per_sample"])
    return {
        row["id"]: int(row["selected_primary_fqdn"] == row["ground_truth_fqdn"])
        for row in rows
    }


def _gate_correct(field: str) -> dict[str, int]:
    rows = _load_json(SPLIT_DIR / "per_sample_correctness.json")
    return {row["id"]: int(row[field]) for row in rows}


def _historical_batches(chunk_size: int) -> list[tuple[str, str, int | None]]:
    return [
        ("样本池一", "formal_dev_", None),
        ("样本池二", "formal_blind_", None),
        ("样本池三", "formal_challenge_", None),
        ("样本池四", "holdout2_", None),
        ("样本池五", "holdout3_", chunk_size),
    ]


def _method_correctness() -> dict[str, dict[str, int]]:
    return {
        "规则路由": _fastpath_correct("sa_clean_v2_20260314"),
        "结构化语义路由": _fastpath_correct("sa_llm_v2_20260323_uncertainty"),
        "默认协作复核": _gate_correct("base_correct"),
        "扩展配置（补充）": _gate_correct("aggressive_correct"),
    }


def _records_for_split(split_name: str, split_ids: set[str], chunk_size: int) -> list[dict]:
    methods = {
        "规则路由": _fastpath_correct("sa_clean_v2_20260314"),
        "结构化语义路由": _fastpath_correct("sa_llm_v2_20260323_uncertainty"),
        "默认协作复核": _gate_correct("base_correct"),
        "扩展配置（补充）": _gate_correct("aggressive_correct"),
    }
    all_ids = sorted(set().union(*[set(v) for v in methods.values()]))

    cumulative: list[str] = []
    records: list[dict] = []
    for batch_name, prefix, batch_chunk_size in _historical_batches(chunk_size):
        batch_ids = [sample_id for sample_id in all_ids if sample_id.startswith(prefix) and sample_id in split_ids]
        chunks = [batch_ids]
        if batch_chunk_size:
            chunks = [batch_ids[:idx] for idx in range(batch_chunk_size, len(batch_ids) + 1, batch_chunk_size)]
            if chunks[-1] != batch_ids:
                chunks.append(batch_ids)

        base = list(cumulative)
        for chunk in chunks:
            cumulative = sorted(set(base + chunk))
            suffix = ""
            if batch_chunk_size and len(chunk) < len(batch_ids):
                suffix = f"（前{len(chunk)}条）"
            for method, correctness in methods.items():
                vals = [correctness[sample_id] for sample_id in cumulative if sample_id in correctness]
                records.append(
                    {
                        "split": split_name,
                        "batch": f"{batch_name}{suffix}",
                        "sample_size": len(vals),
                        "method": method,
                        "correct": sum(vals),
                        "accuracy": sum(vals) / len(vals),
                    }
                )
    return records


def _test_records() -> list[dict]:
    test_ids = set(_load_json(SPLIT_DIR / "test_ids.json"))
    return _records_for_split("测试划分", test_ids, chunk_size=20)


def _train_test_records() -> list[dict]:
    train_ids = set(_load_json(SPLIT_DIR / "train_ids.json"))
    test_ids = set(_load_json(SPLIT_DIR / "test_ids.json"))
    return _records_for_split("训练划分", train_ids, chunk_size=80) + _records_for_split(
        "测试划分", test_ids, chunk_size=20
    )


def _write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["batch", "sample_size", "method", "correct", "accuracy"]
        if records and "split" in records[0]:
            fieldnames = ["split"] + fieldnames
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def _plot(records: list[dict], path_base: Path) -> None:
    order = [
        ("规则路由", PALETTE["rule"], "-", "o"),
        ("结构化语义路由", PALETTE["semantic"], "-", "s"),
        ("默认协作复核", PALETTE["review"], "-", "^"),
        ("扩展配置（补充）", PALETTE["expanded"], "--", "D"),
    ]
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    for method, color, linestyle, marker in order:
        rows = [row for row in records if row["method"] == method]
        xs = [row["sample_size"] for row in rows]
        ys = [row["accuracy"] for row in rows]
        ax.plot(
            xs,
            ys,
            color=color,
            linestyle=linestyle,
            marker=marker,
            markersize=5.4,
            linewidth=2.0,
            label=method,
        )
        for x, y in zip(xs, ys):
            if x == xs[-1]:
                ax.text(x + 1.2, y, f"{y:.3f}", fontsize=9.0, color=color, va="center")

    ax.set_title("样本池累计扩展下的测试侧准确率变化")
    ax.set_xlabel("累计测试样本数")
    ax.set_ylabel("主标签准确率")
    ax.set_xlim(8, 121)
    ax.set_ylim(0.72, 1.02)
    ax.set_xticks([10, 17, 22, 33, 53, 73, 93, 113])
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    ax.grid(axis="y")
    ax.legend(loc="lower right", ncols=2)
    ax.text(
        10,
        0.733,
        "按固定样本池顺序累计统计；虚线为补充配置结果。",
        fontsize=9.2,
        color=PALETTE["muted"],
    )
    fig.tight_layout()
    path_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(path_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _plot_train_test(records: list[dict], path_base: Path) -> None:
    order = [
        ("规则路由", PALETTE["rule"], "-", "o"),
        ("结构化语义路由", PALETTE["semantic"], "-", "s"),
        ("默认协作复核", PALETTE["review"], "-", "^"),
        ("扩展配置（补充）", PALETTE["expanded"], "--", "D"),
    ]
    splits = [
        ("训练划分", "训练划分累计结果", [40, 68, 87, 130, 210, 290, 370, 450], (35, 470)),
        ("测试划分", "测试划分累计结果", [10, 17, 22, 33, 53, 73, 93, 113], (8, 121)),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.9), sharey=True)
    handles = []
    labels = []

    for ax, (split_name, title, xticks, xlim) in zip(axes, splits):
        split_records = [row for row in records if row["split"] == split_name]
        for method, color, linestyle, marker in order:
            rows = [row for row in split_records if row["method"] == method]
            xs = [row["sample_size"] for row in rows]
            ys = [row["accuracy"] for row in rows]
            line = ax.plot(
                xs,
                ys,
                color=color,
                linestyle=linestyle,
                marker=marker,
                markersize=5.2,
                linewidth=2.0,
                label=method,
            )[0]
            if split_name == "训练划分":
                handles.append(line)
                labels.append(method)
            for x, y in zip(xs, ys):
                if x == xs[-1]:
                    ax.text(x + (4 if split_name == "训练划分" else 1.2), y, f"{y:.3f}", fontsize=8.8, color=color, va="center")

        ax.set_title(title)
        ax.set_xlabel("累计样本数")
        ax.set_xlim(*xlim)
        ax.set_ylim(0.72, 1.02)
        ax.set_xticks(xticks)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
        ax.grid(axis="y")

    axes[0].set_ylabel("主标签准确率")
    fig.suptitle("样本池累计扩展下的训练划分与测试划分准确率变化", y=0.99, fontsize=13.0, fontweight="bold")
    fig.legend(handles, labels, loc="lower center", ncols=4, bbox_to_anchor=(0.5, -0.015))
    fig.text(
        0.105,
        0.08,
        "按固定样本池顺序累计统计；训练划分与测试划分分别计算，虚线为补充配置结果。",
        fontsize=9.2,
        color=PALETTE["muted"],
    )
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    path_base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path_base.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(path_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    records = _test_records()
    csv_path = OUT_DIR / "08_historical_cumulative_test.csv"
    figure_base = OUT_DIR / "08_historical_cumulative_test"
    _write_csv(records, csv_path)
    _plot(records, figure_base)

    GJTX_DOC_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in [".png", ".pdf"]:
        shutil.copy2(figure_base.with_suffix(suffix), GJTX_DOC_DIR / f"08_historical_cumulative_test{suffix}")

    train_test_records = _train_test_records()
    train_test_csv_path = OUT_DIR / "09_historical_cumulative_train_test.csv"
    train_test_figure_base = OUT_DIR / "09_historical_cumulative_train_test"
    _write_csv(train_test_records, train_test_csv_path)
    _plot_train_test(train_test_records, train_test_figure_base)
    for suffix in [".png", ".pdf"]:
        shutil.copy2(
            train_test_figure_base.with_suffix(suffix),
            GJTX_DOC_DIR / f"09_historical_cumulative_train_test{suffix}",
        )

    print(figure_base.with_suffix(".png"))
    print(csv_path)
    print(train_test_figure_base.with_suffix(".png"))
    print(train_test_csv_path)


if __name__ == "__main__":
    main()
