#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentdns_routing.namespace import NamespaceResolver
from agentdns_routing.stage_a import StageAConfig, evaluate_stage_a_run, save_stage_a_outputs
from agentdns_routing.stage_r import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic Stage A evaluation on a fixed Stage R snapshot.")
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
    )
    parser.add_argument(
        "--gold",
        default=None,
        help="Optional explicit gold path. Defaults to data/agentdns_routing/{split}.jsonl",
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Optional explicit Stage R snapshot path. Defaults to artifacts/stage_r/{split}.sr_v0_20260306.jsonl",
    )
    parser.add_argument("--stage-a-version", default="sa_v0_20260306")
    parser.add_argument("--confidence-temperature", type=float, default=0.25)
    parser.add_argument("--tau", type=float, default=0.30)
    parser.add_argument("--delta", type=float, default=0.08)
    parser.add_argument("--tau-rel", type=float, default=0.12)
    parser.add_argument("--tau-cov", type=float, default=0.50)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "artifacts" / "stage_a"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gold_path = Path(args.gold or ROOT / "data" / "agentdns_routing" / f"{args.split}.jsonl")
    snapshot_path = Path(
        args.snapshot or ROOT / "artifacts" / "stage_r" / f"{args.split}.sr_v0_20260306.jsonl"
    )
    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    gold_samples = load_jsonl(gold_path)
    snapshots = load_jsonl(snapshot_path)
    config = StageAConfig(
        stage_a_version=args.stage_a_version,
        confidence_temperature=args.confidence_temperature,
        tau=args.tau,
        delta=args.delta,
        tau_rel=args.tau_rel,
        tau_cov=args.tau_cov,
        top_k=args.top_k,
    )
    traces, summary = evaluate_stage_a_run(
        gold_samples=gold_samples,
        snapshots=snapshots,
        resolver=resolver,
        config=config,
        run_id_prefix=f"{args.split}_{config.stage_a_version}",
    )

    output_dir = Path(args.output_dir)
    traces_path = output_dir / f"{args.split}.{config.stage_a_version}.jsonl"
    summary_path = output_dir / f"{args.split}.{config.stage_a_version}.summary.json"
    save_stage_a_outputs(traces=traces, summary=summary, traces_path=traces_path, summary_path=summary_path)
    print(
        json.dumps(
            {
                "split": args.split,
                "summary_path": str(summary_path),
                "traces_path": str(traces_path),
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
