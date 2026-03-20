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
from agentdns_routing.stage_a_clean import StageACleanConfig, build_routing_run_trace as build_a_clean_trace
from agentdns_routing.stage_a_eval import evaluate_traces, validate_traces
from agentdns_routing.stage_a_llm import (
    StageALLMConfig,
    build_routing_run_trace as build_a_llm_trace,
    make_llm_client,
)
from agentdns_routing.stage_b_consensus import (
    StageBConfig,
    build_stage_b_trace,
    make_stage_b_llm_client,
)
from agentdns_routing.stage_b_eval import evaluate_stage_b
from agentdns_routing.stage_r_clean import dump_jsonl, load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run formal R/A/B experiments across four routing chains.")
    parser.add_argument("--input", required=True, help="Input sample jsonl path.")
    parser.add_argument("--snapshot", required=True, help="Frozen Stage R snapshot jsonl path.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl path.",
    )
    parser.add_argument(
        "--chains",
        default="a_clean,a_llm,a_clean_b,a_llm_b",
        help="Comma-separated subset of: a_clean,a_llm,a_clean_b,a_llm_b",
    )
    parser.add_argument("--stage-a-clean-version", default=StageACleanConfig().stage_a_version)
    parser.add_argument("--stage-a-llm-version", default=StageALLMConfig().stage_a_version)
    parser.add_argument("--stage-a-llm-prompt-version", default=StageALLMConfig().prompt_version)
    parser.add_argument("--stage-a-llm-base-stage-a-version", default=None)
    parser.add_argument("--stage-b-version", default=StageBConfig().stage_b_version)
    parser.add_argument("--stage-b-prompt-version", default=StageBConfig().prompt_version)
    parser.add_argument("--a-llm-provider", choices=["mock", "deepseek", "openai"], default="mock")
    parser.add_argument("--a-llm-model", default=None)
    parser.add_argument("--b-provider", choices=["deterministic", "mock", "deepseek", "openai"], default="mock")
    parser.add_argument("--b-model", default=None)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--blind-mode", action="store_true")
    parser.add_argument("--exploratory", action="store_true")
    parser.add_argument("--eval-stage", choices=["hard13", "escalated_subset", "full_dev"], default=None)
    parser.add_argument("--depends-on", default=None, help="Optional prior stage summary json path for staged evaluation.")
    return parser.parse_args()


def _write_artifact(output_dir: Path, name: str, traces: list[dict], summary: dict) -> tuple[str, str]:
    trace_path = output_dir / f"{name}.jsonl"
    summary_path = output_dir / f"{name}.summary.json"
    dump_jsonl(trace_path, traces)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(trace_path), str(summary_path)


def _load_prereq_summary(path: str | None) -> dict | None:
    if not path:
        return None
    summary_path = Path(path)
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _assert_eval_stage_progression(eval_stage: str | None, prereq_summary: dict | None) -> None:
    if not eval_stage or eval_stage == "hard13":
        return
    if prereq_summary is None:
        raise ValueError(f"--eval-stage={eval_stage} requires --depends-on <prior summary.json>")
    expected_previous = {
        "escalated_subset": "hard13",
        "full_dev": "escalated_subset",
    }[eval_stage]
    if prereq_summary.get("eval_stage") != expected_previous:
        raise ValueError(
            f"--eval-stage={eval_stage} requires depends-on summary with eval_stage={expected_previous}"
        )
    if not prereq_summary.get("stage_gate_passed", False):
        raise ValueError(f"Depends-on summary did not pass stage gate: {Path(str(prereq_summary.get('summary_path', ''))).name}")


def _compute_stage_gate(eval_stage: str | None, chain_summary: dict, baseline_summary: dict | None) -> tuple[bool | None, dict | None]:
    if not eval_stage or baseline_summary is None:
        return None, None
    if eval_stage == "hard13":
        metrics = {
            "stage_b_regressed_primary": chain_summary.get("stage_b_regressed_primary"),
            "chain_primary_acc": chain_summary.get("PrimaryAcc@1"),
            "baseline_primary_acc": baseline_summary.get("PrimaryAcc@1"),
        }
        passed = (
            chain_summary.get("stage_b_regressed_primary") == 0
            and chain_summary.get("PrimaryAcc@1", 0.0) >= baseline_summary.get("PrimaryAcc@1", 0.0)
        )
        return passed, metrics
    if eval_stage == "escalated_subset":
        metrics = {
            "chain_primary_acc": chain_summary.get("PrimaryAcc@1"),
            "baseline_primary_acc": baseline_summary.get("PrimaryAcc@1"),
            "chain_acceptable_primary_acc": chain_summary.get("AcceptablePrimary@1"),
            "baseline_acceptable_primary_acc": baseline_summary.get("AcceptablePrimary@1"),
            "chain_related_precision": chain_summary.get("RelatedPrecision"),
            "baseline_related_precision": baseline_summary.get("RelatedPrecision"),
        }
        passed = (
            chain_summary.get("PrimaryAcc@1", 0.0) >= baseline_summary.get("PrimaryAcc@1", 0.0)
            and chain_summary.get("AcceptablePrimary@1", 0.0) >= baseline_summary.get("AcceptablePrimary@1", 0.0)
            and chain_summary.get("RelatedPrecision", 0.0) >= baseline_summary.get("RelatedPrecision", 0.0)
        )
        return passed, metrics
    return None, None


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prereq_summary = _load_prereq_summary(args.depends_on)
    _assert_eval_stage_progression(args.eval_stage, prereq_summary)

    requested = {item.strip() for item in args.chains.split(",") if item.strip()}
    valid = {"a_clean", "a_llm", "a_clean_b", "a_llm_b"}
    unknown = requested - valid
    if unknown:
        raise ValueError(f"Unsupported chains: {sorted(unknown)}")

    samples = load_jsonl(args.input)
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    snapshots = {row["id"]: row for row in load_jsonl(args.snapshot)}
    resolver = NamespaceResolver.from_jsonl(args.descriptors)

    results: dict[str, dict[str, str | dict]] = {}
    split_name = Path(args.input).stem

    a_clean_traces: list[dict] = []
    if {"a_clean", "a_clean_b"} & requested:
        a_clean_config = StageACleanConfig(stage_a_version=args.stage_a_clean_version)
        for sample in samples:
            snapshot = snapshots.get(sample["id"])
            if not snapshot:
                raise KeyError(f"Missing Stage R snapshot for sample_id={sample['id']}")
            a_clean_traces.append(
                build_a_clean_trace(sample=sample, snapshot=snapshot, resolver=resolver, config=a_clean_config)
            )
        a_clean_summary = evaluate_traces(samples, a_clean_traces)
        a_clean_summary["method"] = "stage_a_clean"
        a_clean_summary["stage_a_version"] = a_clean_config.stage_a_version
        a_clean_summary["stage_r_version"] = a_clean_traces[0]["stage_r_version"] if a_clean_traces else None
        a_clean_summary["input_path"] = args.input
        a_clean_summary["snapshot_path"] = args.snapshot
        a_clean_summary["trace_validation"] = validate_traces(a_clean_traces, ROOT)
        a_clean_summary["eval_stage"] = args.eval_stage
        a_clean_summary["prereq_summary_path"] = args.depends_on
        name = f"{split_name}.{a_clean_config.stage_a_version}"
        trace_path, summary_path = _write_artifact(output_dir, name, a_clean_traces, a_clean_summary)
        a_clean_summary["summary_path"] = summary_path
        results["a_clean"] = {"trace_path": trace_path, "summary_path": summary_path, "summary": a_clean_summary}

    a_llm_traces: list[dict] = []
    if {"a_llm", "a_llm_b"} & requested:
        a_llm_config = StageALLMConfig(
            stage_a_version=args.stage_a_llm_version,
            prompt_version=args.stage_a_llm_prompt_version,
            base_stage_a_version=args.stage_a_llm_base_stage_a_version or args.stage_a_clean_version,
        )
        a_llm_client = make_llm_client(provider=args.a_llm_provider, model=args.a_llm_model)
        for sample in samples:
            snapshot = snapshots.get(sample["id"])
            if not snapshot:
                raise KeyError(f"Missing Stage R snapshot for sample_id={sample['id']}")
            a_llm_traces.append(
                build_a_llm_trace(
                    sample=sample,
                    snapshot=snapshot,
                    resolver=resolver,
                    client=a_llm_client,
                    config=a_llm_config,
                )
            )
        a_llm_summary = evaluate_traces(samples, a_llm_traces)
        a_llm_summary["method"] = "stage_a_llm"
        a_llm_summary["stage_a_version"] = a_llm_config.stage_a_version
        a_llm_summary["prompt_version"] = a_llm_config.prompt_version
        a_llm_summary["base_stage_a_version"] = a_llm_config.base_stage_a_version
        a_llm_summary["stage_r_version"] = a_llm_traces[0]["stage_r_version"] if a_llm_traces else None
        a_llm_summary["input_path"] = args.input
        a_llm_summary["snapshot_path"] = args.snapshot
        a_llm_summary["provider"] = a_llm_client.provider
        a_llm_summary["model"] = a_llm_client.model
        a_llm_summary["blind_mode"] = bool(args.blind_mode)
        a_llm_summary["exploratory"] = bool(args.exploratory)
        a_llm_summary["trace_validation"] = validate_traces(a_llm_traces, ROOT)
        a_llm_summary["eval_stage"] = args.eval_stage
        a_llm_summary["prereq_summary_path"] = args.depends_on
        name = f"{split_name}.{a_llm_config.stage_a_version}"
        trace_path, summary_path = _write_artifact(output_dir, name, a_llm_traces, a_llm_summary)
        a_llm_summary["summary_path"] = summary_path
        results["a_llm"] = {"trace_path": trace_path, "summary_path": summary_path, "summary": a_llm_summary}

    b_client = None if args.b_provider == "deterministic" else make_stage_b_llm_client(args.b_provider, args.b_model)
    b_config = StageBConfig(stage_b_version=args.stage_b_version, prompt_version=args.stage_b_prompt_version)

    if "a_clean_b" in requested:
        if not a_clean_traces:
            raise RuntimeError("a_clean traces are required for a_clean_b chain")
        a_clean_b_traces = [
            build_stage_b_trace(sample=sample, trace=trace, resolver=resolver, config=b_config, client=b_client)
            for sample, trace in zip(samples, a_clean_traces)
        ]
        a_clean_b_summary = evaluate_stage_b(samples, a_clean_b_traces)
        a_clean_b_summary["method"] = "stage_a_clean_to_stage_b"
        a_clean_b_summary["stage_a_version"] = a_clean_traces[0]["stage_a_version"] if a_clean_traces else None
        a_clean_b_summary["stage_b_version"] = b_config.stage_b_version
        a_clean_b_summary["prompt_version"] = b_config.prompt_version
        a_clean_b_summary["stage_r_version"] = a_clean_b_traces[0]["stage_r_version"] if a_clean_b_traces else None
        a_clean_b_summary["provider"] = b_client.provider if b_client else "deterministic"
        a_clean_b_summary["model"] = b_client.model if b_client else b_config.deterministic_decision_mode
        a_clean_b_summary["input_path"] = args.input
        a_clean_b_summary["snapshot_path"] = args.snapshot
        a_clean_b_summary["blind_mode"] = bool(args.blind_mode)
        a_clean_b_summary["exploratory"] = bool(args.exploratory)
        a_clean_b_summary["trace_validation"] = validate_traces(a_clean_b_traces, ROOT)
        gate_passed, gate_metrics = _compute_stage_gate(
            args.eval_stage,
            a_clean_b_summary,
            results.get("a_clean", {}).get("summary"),
        )
        a_clean_b_summary["eval_stage"] = args.eval_stage
        a_clean_b_summary["prereq_summary_path"] = args.depends_on
        a_clean_b_summary["stage_gate_passed"] = gate_passed
        a_clean_b_summary["stage_gate_metrics"] = gate_metrics
        name = f"{split_name}.{args.stage_a_clean_version}__{b_config.stage_b_version}"
        trace_path, summary_path = _write_artifact(output_dir, name, a_clean_b_traces, a_clean_b_summary)
        a_clean_b_summary["summary_path"] = summary_path
        results["a_clean_b"] = {"trace_path": trace_path, "summary_path": summary_path, "summary": a_clean_b_summary}

    if "a_llm_b" in requested:
        if not a_llm_traces:
            raise RuntimeError("a_llm traces are required for a_llm_b chain")
        a_llm_b_traces = [
            build_stage_b_trace(sample=sample, trace=trace, resolver=resolver, config=b_config, client=b_client)
            for sample, trace in zip(samples, a_llm_traces)
        ]
        a_llm_b_summary = evaluate_stage_b(samples, a_llm_b_traces)
        a_llm_b_summary["method"] = "stage_a_llm_to_stage_b"
        a_llm_b_summary["stage_a_version"] = a_llm_traces[0]["stage_a_version"] if a_llm_traces else None
        a_llm_b_summary["stage_b_version"] = b_config.stage_b_version
        a_llm_b_summary["prompt_version"] = b_config.prompt_version
        a_llm_b_summary["stage_r_version"] = a_llm_b_traces[0]["stage_r_version"] if a_llm_b_traces else None
        a_llm_b_summary["provider"] = b_client.provider if b_client else "deterministic"
        a_llm_b_summary["model"] = b_client.model if b_client else b_config.deterministic_decision_mode
        a_llm_b_summary["input_path"] = args.input
        a_llm_b_summary["snapshot_path"] = args.snapshot
        a_llm_b_summary["blind_mode"] = bool(args.blind_mode)
        a_llm_b_summary["exploratory"] = bool(args.exploratory)
        a_llm_b_summary["trace_validation"] = validate_traces(a_llm_b_traces, ROOT)
        gate_passed, gate_metrics = _compute_stage_gate(
            args.eval_stage,
            a_llm_b_summary,
            results.get("a_llm", {}).get("summary"),
        )
        a_llm_b_summary["eval_stage"] = args.eval_stage
        a_llm_b_summary["prereq_summary_path"] = args.depends_on
        a_llm_b_summary["stage_gate_passed"] = gate_passed
        a_llm_b_summary["stage_gate_metrics"] = gate_metrics
        name = f"{split_name}.{args.stage_a_llm_version}__{b_config.stage_b_version}"
        trace_path, summary_path = _write_artifact(output_dir, name, a_llm_b_traces, a_llm_b_summary)
        a_llm_b_summary["summary_path"] = summary_path
        results["a_llm_b"] = {"trace_path": trace_path, "summary_path": summary_path, "summary": a_llm_b_summary}

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
