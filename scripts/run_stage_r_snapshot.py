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

from agentdns_routing.stage_r import build_candidate_snapshot, dump_jsonl, load_json, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Stage R candidate snapshots for a split.")
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
    )
    parser.add_argument(
        "--lexicon",
        default=str(ROOT / "data" / "agentdns_routing" / "evidence_lexicon.json"),
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=None,
        help="Optional explicit gold dataset path. Defaults to data/agentdns_routing/{split}.jsonl",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to artifacts/stage_r/{split}.sr_v0_20260306.jsonl",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--stage-r-version", default="sr_v0_20260306")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_path or ROOT / "data" / "agentdns_routing" / f"{args.split}.jsonl")
    output_path = Path(
        args.output or ROOT / "artifacts" / "stage_r" / f"{args.split}.{args.stage_r_version}.jsonl"
    )

    descriptors = load_jsonl(args.descriptors)
    lexicon = load_json(args.lexicon)
    samples = load_jsonl(input_path)

    snapshots = [
        build_candidate_snapshot(
            sample=sample,
            descriptors=descriptors,
            lexicon=lexicon,
            top_k=args.top_k,
            stage_r_version=args.stage_r_version,
        )
        for sample in samples
    ]
    dump_jsonl(output_path, snapshots)

    summary = {
        "split": args.split,
        "samples": len(samples),
        "descriptors": len(descriptors),
        "top_k": args.top_k,
        "stage_r_version": args.stage_r_version,
        "output": str(output_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

