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

from agentdns_routing.namespace import NamespaceResolver
from agentdns_routing.stage_a_multi_intent import (
    StageAMultiIntentConfig,
    build_routing_run_trace,
    make_multi_intent_llm_client,
)
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage A multi-intent set routing on a frozen Stage R snapshot.")
    parser.add_argument("--input", required=True, help="Input sample jsonl path.")
    parser.add_argument("--snapshot", required=True, help="Frozen Stage R snapshot jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument("--provider", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--model", default=None, help="LLM model name.")
    parser.add_argument("--stage-a-version", default=StageAMultiIntentConfig().stage_a_version)
    parser.add_argument("--prompt-version", default=StageAMultiIntentConfig().prompt_version)
    parser.add_argument(
        "--gate-mode",
        choices=["default", "expanded"],
        default=StageAMultiIntentConfig().gate_mode,
        help="Stage A review gate calibration mode.",
    )
    parser.add_argument("--max-samples", type=int, default=None, help="Optional limit for smoke runs.")
    parser.add_argument("--no-resume", action="store_true", help="Do not reuse existing trace file.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N new samples.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = load_jsonl(args.input)
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    snapshots = {row["id"]: row for row in load_jsonl(args.snapshot)}
    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    config = StageAMultiIntentConfig(
        stage_a_version=args.stage_a_version,
        prompt_version=args.prompt_version,
        gate_mode=args.gate_mode,
    )
    client = make_multi_intent_llm_client(args.provider, args.model)

    split_name = Path(args.input).stem
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / f"{split_name}.{config.stage_a_version}.jsonl"
    summary_path = output_dir / f"{split_name}.{config.stage_a_version}.summary.json"

    trace_map: dict[str, dict[str, Any]] = {}
    if trace_path.exists() and not args.no_resume:
        trace_map = {row["sample_id"]: row for row in load_jsonl(trace_path)}

    completed_before = len(trace_map)
    for sample in samples:
        sample_id = sample["id"]
        if sample_id in trace_map:
            continue
        snapshot = snapshots.get(sample_id)
        if not snapshot:
            raise KeyError(f"Missing Stage R snapshot for sample_id={sample_id}")
        trace_map[sample_id] = build_routing_run_trace(
            sample=sample,
            snapshot=snapshot,
            resolver=resolver,
            client=client,
            config=config,
        )
        ordered_partial = [trace_map[sample["id"]] for sample in samples if sample["id"] in trace_map]
        dump_jsonl(trace_path, ordered_partial)
        newly_completed = len(trace_map) - completed_before
        if args.progress_every > 0 and newly_completed % args.progress_every == 0:
            print(
                json.dumps(
                    {"progress": {"completed": len(trace_map), "total": len(samples), "last_sample_id": sample_id}},
                    ensure_ascii=False,
                ),
                flush=True,
            )

    traces = [trace_map[sample["id"]] for sample in samples if sample["id"] in trace_map]
    summary = {
        "method": "stage_a_multi_intent",
        "samples": len(samples),
        "traces": len(traces),
        "stage_a_version": config.stage_a_version,
        "prompt_version": config.prompt_version,
        "stage_r_version": traces[0].get("stage_r_version") if traces else None,
        "input_path": args.input,
        "snapshot_path": args.snapshot,
        "provider": client.provider,
        "model": client.model,
        "gate_mode": config.gate_mode,
        "escalation_count": sum(1 for trace in traces if trace.get("stage_a", {}).get("escalate_to_stage_b")),
        "avg_selected_size": round(
            sum(len(trace.get("final_selected_fqdns", [])) for trace in traces) / len(traces),
            4,
        )
        if traces
        else 0.0,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"trace_path": str(trace_path), "summary_path": str(summary_path), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
