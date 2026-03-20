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
from agentdns_routing.stage_a_eval import evaluate_traces, validate_traces
from agentdns_routing.stage_a_llm import StageALLMConfig, build_routing_run_trace, make_llm_client
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run structured LLM Stage A on a frozen Stage R snapshot.")
    parser.add_argument("--input", required=True, help="Input sample jsonl path.")
    parser.add_argument("--snapshot", required=True, help="Frozen Stage R snapshot jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument("--provider", choices=["mock", "deepseek", "openai"], default="mock")
    parser.add_argument("--model", default=None, help="LLM model name.")
    parser.add_argument("--stage-a-version", default=StageALLMConfig().stage_a_version)
    parser.add_argument("--prompt-version", default=StageALLMConfig().prompt_version)
    parser.add_argument("--base-stage-a-version", default=StageALLMConfig().base_stage_a_version)
    parser.add_argument("--max-samples", type=int, default=None, help="Optional limit for smoke runs.")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not reuse existing trace file for the same stage_a_version.",
    )
    parser.add_argument(
        "--blind-mode",
        action="store_true",
        help="Force no-resume and record blind-run protocol metadata.",
    )
    parser.add_argument(
        "--exploratory",
        action="store_true",
        help="Tag this run as exploratory, e.g. after blind labels have been revealed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    samples = load_jsonl(args.input)
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    snapshots = {row["id"]: row for row in load_jsonl(args.snapshot)}
    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    no_resume = args.no_resume or args.blind_mode
    config = StageALLMConfig(
        stage_a_version=args.stage_a_version,
        prompt_version=args.prompt_version,
        base_stage_a_version=args.base_stage_a_version,
    )
    client = make_llm_client(provider=args.provider, model=args.model)

    split_name = Path(args.input).stem
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_path = output_dir / f"{split_name}.{config.stage_a_version}.jsonl"
    summary_path = output_dir / f"{split_name}.{config.stage_a_version}.summary.json"

    existing_trace_map: dict[str, dict[str, Any]] = {}
    if trace_path.exists() and not no_resume:
        existing_rows = load_jsonl(trace_path)
        existing_trace_map = {row["sample_id"]: row for row in existing_rows}

    for sample in samples:
        sample_id = sample["id"]
        if sample_id in existing_trace_map:
            continue
        snapshot = snapshots.get(sample_id)
        if not snapshot:
            raise KeyError(f"Missing Stage R snapshot for sample_id={sample_id}")
        trace = build_routing_run_trace(sample=sample, snapshot=snapshot, resolver=resolver, client=client, config=config)
        existing_trace_map[sample_id] = trace
        ordered_partial = [existing_trace_map[s["id"]] for s in samples if s["id"] in existing_trace_map]
        dump_jsonl(trace_path, ordered_partial)

    traces = [existing_trace_map[sample["id"]] for sample in samples if sample["id"] in existing_trace_map]
    summary = evaluate_traces(samples, traces)
    summary["method"] = "stage_a_llm"
    summary["stage_a_version"] = config.stage_a_version
    summary["prompt_version"] = config.prompt_version
    summary["base_stage_a_version"] = config.base_stage_a_version
    summary["stage_r_version"] = traces[0]["stage_r_version"] if traces else None
    summary["input_path"] = args.input
    summary["snapshot_path"] = args.snapshot
    summary["provider"] = client.provider
    summary["model"] = client.model
    summary["blind_mode"] = bool(args.blind_mode)
    summary["exploratory"] = bool(args.exploratory)
    summary["no_resume"] = bool(no_resume)
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
