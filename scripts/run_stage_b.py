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
from agentdns_routing.stage_a_eval import validate_traces
from agentdns_routing.stage_b_consensus import (
    StageBConfig,
    build_stage_b_trace,
    make_stage_b_llm_client,
)
from agentdns_routing.stage_b_eval import evaluate_stage_b
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run minimal Stage B on Stage A traces.")
    parser.add_argument("--input", required=True, help="Input sample jsonl path.")
    parser.add_argument("--traces", required=True, help="Stage A trace jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument("--stage-b-version", default=StageBConfig().stage_b_version)
    parser.add_argument("--prompt-version", default=StageBConfig().prompt_version)
    parser.add_argument("--provider", choices=["deterministic", "mock", "deepseek", "openai"], default="mock")
    parser.add_argument("--model", default=None, help="Stage B LLM model name.")
    parser.add_argument("--max-samples", type=int, default=None, help="Optional limit for smoke runs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = load_jsonl(args.input)
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    trace_by_sample_id = {row["sample_id"]: row for row in load_jsonl(args.traces)}
    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    config = StageBConfig(stage_b_version=args.stage_b_version, prompt_version=args.prompt_version)
    client = None if args.provider == "deterministic" else make_stage_b_llm_client(args.provider, args.model)

    traces: list[dict] = []
    for sample in samples:
        trace = trace_by_sample_id.get(sample["id"])
        if not trace:
            raise KeyError(f"Missing Stage A trace for sample_id={sample['id']}")
        traces.append(build_stage_b_trace(sample=sample, trace=trace, resolver=resolver, config=config, client=client))

    split_name = Path(args.input).stem
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / f"{split_name}.{config.stage_b_version}.jsonl"
    summary_path = output_dir / f"{split_name}.{config.stage_b_version}.summary.json"

    dump_jsonl(trace_path, traces)
    summary = evaluate_stage_b(samples, traces)
    summary["stage_b_version"] = config.stage_b_version
    summary["prompt_version"] = config.prompt_version
    summary["stage_a_version"] = traces[0].get("stage_a_version") if traces else None
    summary["stage_r_version"] = traces[0].get("stage_r_version") if traces else None
    summary["input_path"] = args.input
    summary["trace_input_path"] = args.traces
    summary["provider"] = client.provider if client else "deterministic"
    summary["model"] = client.model if client else config.deterministic_decision_mode
    summary["trace_validation"] = validate_traces(traces, ROOT)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "trace_path": str(trace_path),
                "summary_path": str(summary_path),
                "summary": {key: value for key, value in summary.items() if key != "per_sample"},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
