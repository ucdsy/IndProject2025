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

from agentdns_routing.namespace import NamespaceResolver, load_jsonl as load_descriptor_jsonl
from agentdns_routing.stage_r_clean import build_candidate_snapshot, dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate clean Stage R candidate snapshots.")
    parser.add_argument("--input", required=True, help="Input jsonl path.")
    parser.add_argument("--output", required=True, help="Output snapshot jsonl path.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--stage-r-version", default="sr_clean_v0_20260306")
    parser.add_argument("--summary", default=None, help="Optional summary json path.")
    return parser.parse_args()


def build_summary(samples: list[dict], snapshots: list[dict], top_k: int, input_path: Path) -> dict:
    if not samples or "ground_truth_fqdn" not in samples[0]:
        return {
            "input": str(input_path),
            "samples": len(samples),
            "top_k": top_k,
            "stage": "stage_r_clean",
            "labels_available": False,
        }

    primary_hits = 0
    related_total = 0
    related_hit_total = 0
    for sample, snapshot in zip(samples, snapshots):
        top_fqdns = [row["fqdn"] for row in snapshot["fqdn_candidates"][:top_k]]
        if sample["ground_truth_fqdn"] in top_fqdns:
            primary_hits += 1
        related = sample.get("relevant_fqdns", [])
        related_total += len(related)
        related_hit_total += sum(1 for fqdn in related if fqdn in top_fqdns)

    return {
        "input": str(input_path),
        "samples": len(samples),
        "top_k": top_k,
        "stage": "stage_r_clean",
        "labels_available": True,
        "PrimaryRecall@K": round(primary_hits / len(samples), 4) if samples else 0.0,
        "RelatedCoverage@K": round(related_hit_total / related_total, 4) if related_total else 0.0,
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    summary_path = Path(args.summary) if args.summary else None

    resolver = NamespaceResolver(load_descriptor_jsonl(args.descriptors))
    samples = load_jsonl(input_path)
    snapshots = [
        build_candidate_snapshot(
            sample=sample,
            resolver=resolver,
            top_k=args.top_k,
            stage_r_version=args.stage_r_version,
        )
        for sample in samples
    ]
    dump_jsonl(output_path, snapshots)
    summary = build_summary(samples, snapshots, args.top_k, input_path)
    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
