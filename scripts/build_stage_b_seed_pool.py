#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentdns_routing.stage_a_eval import evaluate_traces
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Stage B seed pool from labeled Stage A traces.")
    parser.add_argument("--input", required=True, help="Labeled sample jsonl path.")
    parser.add_argument("--traces", required=True, help="Stage A trace jsonl path.")
    parser.add_argument("--output", required=True, help="Output stage_b_seed_pool jsonl path.")
    return parser.parse_args()


def _build_pool_rows(samples: list[dict[str, Any]], traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    per_sample = {
        row["id"]: row
        for row in evaluate_traces(samples, traces).get("per_sample", [])
    }
    trace_by_id = {trace["sample_id"]: trace for trace in traces}
    rows: list[dict[str, Any]] = []
    for sample in samples:
        trace = trace_by_id.get(sample["id"])
        if not trace:
            continue
        stage_a = trace["stage_a"]
        if not stage_a.get("escalate_to_stage_b"):
            continue
        sample_eval = per_sample.get(sample["id"], {})
        error_bucket = sample_eval.get("error_bucket", "UNLABELED")
        hard_case_family = error_bucket if error_bucket != "OK" else None
        rows.append(
            {
                "id": sample["id"],
                "query": sample.get("query"),
                "context": sample.get("context", {}),
                "ground_truth_fqdn": sample.get("ground_truth_fqdn"),
                "acceptable_fqdns": sample.get("acceptable_fqdns", []),
                "relevant_fqdns": sample.get("relevant_fqdns", []),
                "stage_r_version": trace.get("stage_r_version"),
                "stage_a_version": trace.get("stage_a_version"),
                "stage_a_selected_primary_fqdn": stage_a.get("selected_primary_fqdn"),
                "stage_a_selected_related_fqdns": stage_a.get("selected_related_fqdns", []),
                "stage_a_confidence": stage_a.get("confidence"),
                "stage_a_margin": stage_a.get("margin"),
                "stage_a_escalation_reasons": stage_a.get("escalation_reasons", []),
                "candidate_fqdns": [row["fqdn"] for row in trace["stage_r"].get("fqdn_candidates", [])],
                "hard_case": error_bucket != "OK",
                "hard_case_family": hard_case_family,
                "error_bucket": error_bucket,
                "note": (
                    "blind hard error"
                    if error_bucket != "OK"
                    else "blind escalated but currently correct under Stage A"
                ),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    samples = load_jsonl(args.input)
    traces = load_jsonl(args.traces)
    rows = _build_pool_rows(samples, traces)
    dump_jsonl(args.output, rows)
    hard_cases = [row["id"] for row in rows if row["hard_case"]]
    print(
        json.dumps(
            {
                "output_path": args.output,
                "samples": len(rows),
                "hard_cases": hard_cases,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
