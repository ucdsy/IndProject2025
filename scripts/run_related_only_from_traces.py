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
from agentdns_routing.related_v2 import RelatedV2Config, attach_related_v2_final_fields, make_related_llm_client
from agentdns_routing.stage_a_eval import evaluate_traces
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach related_v2 onto frozen traces without rerunning primary.")
    parser.add_argument("--input", required=True, help="Joined labeled input jsonl path.")
    parser.add_argument(
        "--trace-files",
        required=True,
        nargs="+",
        help="One or more frozen trace jsonl files that provide primary decisions.",
    )
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument("--provider", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--model", default=None)
    parser.add_argument("--related-version", default=RelatedV2Config().related_version)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--sample-ids", default=None, help="Optional json file listing sample ids to keep.")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
        help="Write checkpoint files every N successful samples.",
    )
    return parser.parse_args()


def _load_trace_map(paths: list[str]) -> dict[str, dict]:
    traces: dict[str, dict] = {}
    for path in paths:
        for row in load_jsonl(path):
            traces[row["sample_id"]] = row
    return traces


def _load_sample_id_filter(path: str | None) -> set[str] | None:
    if not path:
        return None
    values = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(item) for item in values}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    samples = load_jsonl(args.input)
    sample_filter = _load_sample_id_filter(args.sample_ids)
    if sample_filter is not None:
        samples = [row for row in samples if row["id"] in sample_filter]
    if args.max_samples is not None:
        samples = samples[: args.max_samples]

    trace_map = _load_trace_map(args.trace_files)
    client = make_related_llm_client(provider=args.provider, model=args.model)
    config = RelatedV2Config(related_version=args.related_version)

    split_name = Path(args.input).stem
    trace_path = output_dir / f"{split_name}.{config.related_version}.jsonl"
    summary_path = output_dir / f"{split_name}.{config.related_version}.summary.json"
    failures_path = output_dir / f"{split_name}.{config.related_version}.failures.json"
    progress_path = output_dir / f"{split_name}.{config.related_version}.progress.json"

    updated_traces: list[dict] = load_jsonl(trace_path) if trace_path.exists() else []
    completed_ids = {row["sample_id"] for row in updated_traces}
    failures: dict[str, str] = {}
    if failures_path.exists():
        payload = json.loads(failures_path.read_text(encoding="utf-8"))
        failures = {str(key): str(value) for key, value in payload.get("failures", {}).items()}

    def flush_progress() -> None:
        dump_jsonl(trace_path, updated_traces)
        _write_json(
            failures_path,
            {
                "failures": failures,
                "failure_count": len(failures),
            },
        )
        _write_json(
            progress_path,
            {
                "method": "related_only_from_frozen_traces",
                "related_version": config.related_version,
                "provider": client.provider,
                "model": client.model,
                "input_path": args.input,
                "trace_files": list(args.trace_files),
                "sample_filter": args.sample_ids,
                "total_samples": len(samples),
                "completed_samples": len(updated_traces),
                "remaining_samples": max(len(samples) - len(updated_traces), 0),
                "failure_count": len(failures),
            },
        )

    processed_since_checkpoint = 0
    for sample in samples:
        if sample["id"] in completed_ids:
            continue
        trace = trace_map.get(sample["id"])
        if trace is None:
            raise KeyError(f"Missing frozen trace for sample_id={sample['id']}")
        try:
            updated_trace = attach_related_v2_final_fields(
                sample=sample,
                trace=trace,
                resolver=resolver,
                config=config,
                client=client,
            )
        except Exception as exc:  # noqa: BLE001
            failures[sample["id"]] = f"{type(exc).__name__}: {exc}"
            flush_progress()
            print(
                json.dumps(
                    {
                        "event": "sample_failed",
                        "sample_id": sample["id"],
                        "error": failures[sample["id"]],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            continue

        updated_traces.append(updated_trace)
        completed_ids.add(sample["id"])
        failures.pop(sample["id"], None)
        processed_since_checkpoint += 1

        if processed_since_checkpoint >= args.checkpoint_every:
            flush_progress()
            processed_since_checkpoint = 0

    flush_progress()

    if failures:
        print(
            json.dumps(
                {
                    "event": "incomplete_run",
                    "completed_samples": len(updated_traces),
                    "failure_count": len(failures),
                    "trace_path": str(trace_path),
                    "failures_path": str(failures_path),
                    "progress_path": str(progress_path),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        raise SystemExit(2)

    summary = evaluate_traces(samples, updated_traces)
    summary["method"] = "related_only_from_frozen_traces"
    summary["related_version"] = config.related_version
    summary["provider"] = client.provider
    summary["model"] = client.model
    summary["input_path"] = args.input
    summary["trace_files"] = list(args.trace_files)
    summary["sample_filter"] = args.sample_ids

    dump_jsonl(trace_path, updated_traces)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if failures_path.exists():
        failures_path.unlink()
    if progress_path.exists():
        progress_path.unlink()
    print(json.dumps({"trace_path": str(trace_path), "summary_path": str(summary_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
