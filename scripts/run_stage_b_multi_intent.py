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
from agentdns_routing.stage_b_multi_intent import (
    StageBMultiIntentConfig,
    build_stage_b_multi_intent_trace,
    make_stage_b_multi_intent_llm_client,
)
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage B multi-intent set consensus on Stage A multi-intent traces.")
    parser.add_argument("--input", required=True, help="Input sample jsonl path.")
    parser.add_argument("--traces", required=True, help="Stage A multi-intent trace jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument("--provider", choices=["deterministic", "deepseek", "openai"], default="deepseek")
    parser.add_argument("--model", default=None, help="Stage B LLM model name.")
    parser.add_argument("--stage-b-version", default=StageBMultiIntentConfig().stage_b_version)
    parser.add_argument("--prompt-version", default=StageBMultiIntentConfig().prompt_version)
    parser.add_argument(
        "--gate-mode",
        choices=["default", "expanded"],
        default=StageBMultiIntentConfig().gate_mode,
        help="Stage B entry gate. expanded mirrors the primary-chain expanded gate.",
    )
    parser.add_argument("--max-rounds", type=int, default=StageBMultiIntentConfig().max_rounds)
    parser.add_argument(
        "--max-parallel-roles",
        type=int,
        default=StageBMultiIntentConfig().max_parallel_roles,
        help="Maximum parallel reviewer calls within one Stage B sample.",
    )
    parser.add_argument(
        "--collaboration-mode",
        choices=["single", "homogeneous", "heterogeneous"],
        default=StageBMultiIntentConfig().collaboration_mode,
    )
    parser.add_argument("--force-stage-b", action="store_true", help="Run Stage B for every sample instead of gated escalation only.")
    parser.add_argument("--max-samples", type=int, default=None, help="Optional limit for smoke runs.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N samples.")
    parser.add_argument("--checkpoint-every", type=int, default=25, help="Write a checkpoint trace every N samples.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = load_jsonl(args.input)
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    trace_by_sample_id = {row["sample_id"]: row for row in load_jsonl(args.traces)}
    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    config = StageBMultiIntentConfig(
        stage_b_version=args.stage_b_version,
        prompt_version=args.prompt_version,
        collaboration_mode=args.collaboration_mode,
        gate_mode=args.gate_mode,
        max_rounds=args.max_rounds,
        max_parallel_roles=args.max_parallel_roles,
    )
    client = None if args.provider == "deterministic" else make_stage_b_multi_intent_llm_client(args.provider, args.model)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_name = Path(args.input).stem
    checkpoint_path = output_dir / f"{split_name}.{config.stage_b_version}.checkpoint.jsonl"
    traces: list[dict] = []
    for idx, sample in enumerate(samples, start=1):
        stage_a_trace = trace_by_sample_id.get(sample["id"])
        if not stage_a_trace:
            raise KeyError(f"Missing Stage A trace for sample_id={sample['id']}")
        traces.append(
            build_stage_b_multi_intent_trace(
                sample=sample,
                trace=stage_a_trace,
                resolver=resolver,
                config=config,
                client=client,
                force_stage_b=args.force_stage_b,
            )
        )
        if args.progress_every > 0 and idx % args.progress_every == 0:
            print(
                json.dumps(
                    {
                        "progress": {
                            "completed": idx,
                            "total": len(samples),
                            "last_sample_id": sample["id"],
                            "force_stage_b": bool(args.force_stage_b),
                        }
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        if args.checkpoint_every > 0 and idx % args.checkpoint_every == 0:
            dump_jsonl(checkpoint_path, traces)

    trace_path = output_dir / f"{split_name}.{config.stage_b_version}.jsonl"
    summary_path = output_dir / f"{split_name}.{config.stage_b_version}.summary.json"
    dump_jsonl(trace_path, traces)
    summary = {
        "method": "stage_b_multi_intent",
        "samples": len(samples),
        "traces": len(traces),
        "stage_b_version": config.stage_b_version,
        "prompt_version": config.prompt_version,
        "stage_a_version": traces[0].get("stage_a_version") if traces else None,
        "stage_r_version": traces[0].get("stage_r_version") if traces else None,
        "input_path": args.input,
        "trace_input_path": args.traces,
        "provider": client.provider if client else "deterministic",
        "model": client.model if client else "multi_intent_deterministic_passthrough",
        "collaboration_mode": config.collaboration_mode,
        "gate_mode": config.gate_mode,
        "max_rounds": config.max_rounds,
        "max_parallel_roles": config.max_parallel_roles,
        "force_stage_b": bool(args.force_stage_b),
        "entered_stage_b_count": sum(1 for trace in traces if trace.get("entered_stage_b")),
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
