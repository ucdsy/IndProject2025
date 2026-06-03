#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


PUNCT_RE = re.compile(r"[，。！？；：、“”‘’（）()【】《》,.!?:;\"'`\-\[\]{}_/\\\s]+")
ASCII_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
FQDN_RE = re.compile(r"^(?:[a-z0-9-]+\.){1,3}cn$")


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def dump_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def validate_fqdn(value: str) -> bool:
    return bool(FQDN_RE.match((value or "").strip().lower()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run simple baselines for multi-intent set-valued AgentDNS routing.")
    parser.add_argument("--input", required=True, help="Multi-intent dataset jsonl.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument("--snapshot", default=None, help="Optional Stage R snapshot. Required for flat LLM baselines.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl.",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=["lexical_bm25", "flat_llm", "flat_llm_self_consistency", "embedding"],
        required=True,
    )
    parser.add_argument("--candidate-limit", type=int, default=10)
    parser.add_argument("--max-selected", type=int, default=5)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--provider", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--model", default=None, help="Chat model for flat LLM baselines.")
    parser.add_argument("--llm-temperature", type=float, default=0.0)
    parser.add_argument("--self-consistency-samples", type=int, default=3)
    parser.add_argument("--self-consistency-temperature", type=float, default=0.7)
    parser.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument(
        "--embedding-backend",
        choices=["sentence-transformers"],
        default="sentence-transformers",
    )
    parser.add_argument("--lexical-threshold-ratio", type=float, default=0.52)
    parser.add_argument("--embedding-threshold-ratio", type=float, default=0.90)
    parser.add_argument("--debug", action="store_true", help="Print startup progress to stderr.")
    return parser.parse_args()


def _debug(args: argparse.Namespace, message: str) -> None:
    if getattr(args, "debug", False):
        print(f"[debug] {message}", file=sys.stderr, flush=True)


def _normalize_text(value: str) -> str:
    return PUNCT_RE.sub("", (value or "").lower())


def _context_to_text(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    for value in context.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(item) for item in value if item is not None)
        else:
            parts.append(str(value))
    return " ".join(parts)


def _sample_query_text(sample: dict[str, Any]) -> str:
    return " ".join(part for part in [sample.get("query", ""), _context_to_text(sample.get("context"))] if part).strip()


def _char_ngrams(text: str, n: int) -> list[str]:
    cleaned = _normalize_text(text)
    if not cleaned:
        return []
    if len(cleaned) <= n:
        return [cleaned]
    return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]


def _tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    tokens: list[str] = []
    tokens.extend(ASCII_WORD_RE.findall(lowered))
    normalized = _normalize_text(lowered)
    if CJK_RE.search(normalized):
        tokens.extend(_char_ngrams(normalized, 1))
        tokens.extend(_char_ngrams(normalized, 2))
        tokens.extend(_char_ngrams(normalized, 3))
    elif normalized:
        tokens.append(normalized)
    return [token for token in tokens if token]


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _row_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("fqdn", ""),
        row.get("desc", ""),
        row.get("l1", ""),
        row.get("l2", ""),
        row.get("segment", ""),
        *list(row.get("aliases", [])),
        *list(row.get("examples", [])),
        *list(row.get("industry_tags", [])),
        *list(row.get("risk_tags", [])),
        *list(row.get("action_tags", [])),
        *list(row.get("object_tags", [])),
    ]
    return " ".join(part for part in parts if part)


def _materialize_catalog(descriptor_path: str | Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for descriptor in load_jsonl(descriptor_path):
        base_fqdn = str(descriptor["fqdn"]).strip().lower()
        base_row = {
            "fqdn": base_fqdn,
            "desc": descriptor.get("desc", ""),
            "aliases": list(descriptor.get("aliases", [])),
            "node_kind": "base",
            "l1": descriptor.get("l1"),
            "l2": descriptor.get("l2"),
            "segment": None,
            "parent_fqdn": None,
            "fallback_to": descriptor.get("fallback_to"),
            "examples": list(descriptor.get("examples", [])),
            "industry_tags": list(descriptor.get("industry_tags", [])),
            "risk_tags": list(descriptor.get("risk_tags", [])),
            "action_tags": list(descriptor.get("action_tags", [])),
            "object_tags": list(descriptor.get("object_tags", [])),
            "depth": 2 if descriptor.get("l2") else 1,
        }
        base_row["text"] = _row_text(base_row)
        rows.append(base_row)
        for segment, meta in descriptor.get("segments", {}).items():
            segment_fqdn = f"{segment}.{base_fqdn}"
            segment_row = {
                "fqdn": segment_fqdn,
                "desc": meta.get("desc", descriptor.get("desc", "")),
                "aliases": list(meta.get("aliases", [])),
                "node_kind": "segment",
                "l1": descriptor.get("l1"),
                "l2": descriptor.get("l2"),
                "segment": segment,
                "parent_fqdn": base_fqdn,
                "fallback_to": base_fqdn,
                "examples": list(descriptor.get("examples", [])),
                "industry_tags": list(descriptor.get("industry_tags", [])),
                "risk_tags": list(descriptor.get("risk_tags", [])),
                "action_tags": list(descriptor.get("action_tags", [])),
                "object_tags": list(descriptor.get("object_tags", [])),
                "depth": 3,
            }
            segment_row["text"] = _row_text(segment_row)
            rows.append(segment_row)
    rows.sort(key=lambda row: (row.get("depth", 0), row["fqdn"]))
    return rows, {row["fqdn"]: row for row in rows}


def _candidate_rows_from_catalog(catalog_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in catalog_rows:
        rows.append(
            {
                "fqdn": row["fqdn"],
                "desc": row.get("desc", ""),
                "aliases": list(row.get("aliases", []))[:8],
                "node_kind": row.get("node_kind"),
                "l1": row.get("l1"),
                "l2": row.get("l2"),
                "segment": row.get("segment"),
                "parent_fqdn": row.get("parent_fqdn"),
                "fallback_to": row.get("fallback_to"),
                "text": row.get("text", _row_text(row)),
            }
        )
    return rows


def _candidate_rows_from_snapshot(
    snapshot: dict[str, Any],
    catalog_by_fqdn: dict[str, dict[str, Any]],
    candidate_limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidates = sorted(snapshot.get("fqdn_candidates", []), key=lambda row: row.get("score_r", 0.0), reverse=True)
    for item in candidates[:candidate_limit]:
        fqdn = item.get("fqdn")
        if not isinstance(fqdn, str):
            continue
        catalog_row = catalog_by_fqdn.get(fqdn, {})
        rows.append(
            {
                "fqdn": fqdn,
                "desc": catalog_row.get("desc", ""),
                "aliases": list(catalog_row.get("aliases", []))[:8],
                "node_kind": item.get("node_kind"),
                "l1": item.get("l1"),
                "l2": item.get("l2"),
                "segment": item.get("segment"),
                "parent_fqdn": item.get("parent_fqdn"),
                "fallback_to": item.get("fallback_to"),
                "text": catalog_row.get("text", fqdn),
            }
        )
    return rows


class BM25Index:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.docs = [_tokens(row["text"]) for row in rows]
        self.doc_counters = [Counter(doc) for doc in self.docs]
        self.doc_lens = [len(doc) for doc in self.docs]
        self.avg_len = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 1.0
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc))
        total = len(self.docs)
        self.idf = {
            token: math.log(1.0 + (total - freq + 0.5) / (freq + 0.5))
            for token, freq in df.items()
        }

    def score(self, query: str) -> list[dict[str, Any]]:
        query_tokens = _tokens(query)
        query_counter = Counter(query_tokens)
        rows: list[dict[str, Any]] = []
        k1 = 1.4
        b = 0.72
        for row, doc_counter, doc_len in zip(self.rows, self.doc_counters, self.doc_lens):
            score = 0.0
            for token, query_tf in query_counter.items():
                tf = doc_counter.get(token, 0)
                if not tf:
                    continue
                idf = self.idf.get(token, 0.0)
                denom = tf + k1 * (1.0 - b + b * doc_len / max(self.avg_len, 1e-6))
                score += idf * (tf * (k1 + 1.0) / max(denom, 1e-6)) * min(query_tf, 3)
            if score > 0:
                output = {key: value for key, value in row.items() if key != "text"}
                output["score"] = round(score, 6)
                rows.append(output)
        return sorted(rows, key=lambda item: item["score"], reverse=True)


def _select_by_relative_threshold(
    ranked: list[dict[str, Any]],
    *,
    max_selected: int,
    ratio: float,
) -> list[str]:
    if not ranked:
        return []
    best = float(ranked[0].get("score", 0.0))
    if best <= 0:
        return [ranked[0]["fqdn"]]
    threshold = best * ratio
    selected = [row["fqdn"] for row in ranked if float(row.get("score", 0.0)) >= threshold]
    return _dedupe_keep_order(selected)[:max_selected] or [ranked[0]["fqdn"]]


def _build_baseline_trace(
    sample: dict[str, Any],
    method: str,
    selected: list[str],
    ranked: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = _dedupe_keep_order([fqdn for fqdn in selected if validate_fqdn(fqdn)])
    return {
        "run_id": f"run_{method}_{sample['id']}_{uuid.uuid4().hex[:8]}",
        "sample_id": sample["id"],
        "baseline_version": f"{method}_baseline_v1_20260602",
        "baseline_method": method,
        "entered_stage_b": False,
        "final_decision_source": method,
        "final_selected_fqdns": selected,
        "final_primary_fqdn": selected[0] if selected else None,
        "final_related_fqdns": selected[1:],
        "stage_baseline": {
            "method": method,
            "selected_fqdns": selected,
            "ranked_candidates": ranked,
            **(extra or {}),
        },
    }


def _make_chat_client(provider: str, model: str | None) -> tuple[dict[str, str], str, str]:
    provider = provider.lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set")
        return {"api_key": api_key, "base_url": "https://api.deepseek.com/v1"}, provider, model or "deepseek-chat"
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set")
        return {"api_key": api_key, "base_url": "https://api.openai.com/v1"}, provider, model or "gpt-5.4"
    raise ValueError(f"Unsupported provider: {provider}")


def _chat_completion_http(
    client: dict[str, str],
    payload: dict[str, Any],
    *,
    use_json_mode: bool = True,
    attempts: int = 3,
) -> str:
    body = dict(payload)
    if use_json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        client["base_url"].rstrip("/") + "/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {client['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                response_obj = json.loads(response.read().decode("utf-8"))
            return response_obj["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as exc:
            if use_json_mode:
                return _chat_completion_http(client, payload, use_json_mode=False, attempts=attempts)
            last_error = RuntimeError(exc.read().decode("utf-8", errors="replace"))
        except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            last_error = exc
        if attempt < attempts:
            continue
    if last_error:
        raise last_error
    raise RuntimeError("chat completion failed without an exception")


def _load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty LLM response")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _flat_llm_prompt(sample: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    exposed = [
        {
            "fqdn": row["fqdn"],
            "desc": row.get("desc", ""),
            "aliases": row.get("aliases", []),
        }
        for row in candidates
    ]
    packet = {
        "sample_id": sample["id"],
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "candidates": exposed,
        "rules": [
            "Select all and only candidates explicitly requested by the user query.",
            "Do not invent FQDNs outside candidates.",
            "Return a JSON object only.",
        ],
        "output_schema": {
            "selected_fqdns": ["fqdn"],
            "confidence": "0..1",
            "rationale": "short string",
        },
    }
    return json.dumps(packet, ensure_ascii=False, indent=2)


def _call_flat_llm(
    client: dict[str, str],
    model: str,
    sample: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    temperature: float,
    max_selected: int,
) -> tuple[list[str], dict[str, Any], str]:
    system = (
        "You are a flat AgentDNS candidate selector. "
        "You only see FQDN, description, and aliases. "
        "Do not use hidden structured routing fields. "
        "Return one JSON object."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _flat_llm_prompt(sample, candidates)},
        ],
        "temperature": temperature,
        "max_tokens": 1200,
    }
    raw = _chat_completion_http(client, payload)
    obj = _load_json_object(raw)
    candidate_set = {row["fqdn"] for row in candidates}
    selected = [
        fqdn
        for fqdn in obj.get("selected_fqdns", [])
        if isinstance(fqdn, str) and fqdn in candidate_set and validate_fqdn(fqdn)
    ]
    return _dedupe_keep_order(selected)[:max_selected], obj, raw


def _self_consistency_select(votes: list[list[str]], candidates: list[dict[str, Any]], max_selected: int) -> tuple[list[str], list[dict[str, Any]]]:
    candidate_order = [row["fqdn"] for row in candidates]
    counts = Counter(fqdn for vote in votes for fqdn in vote)
    rows: list[dict[str, Any]] = []
    sample_count = max(len(votes), 1)
    for fqdn in candidate_order:
        count = counts.get(fqdn, 0)
        rows.append({"fqdn": fqdn, "vote_count": count, "vote_ratio": round(count / sample_count, 6)})
    selected = [row["fqdn"] for row in rows if row["vote_count"] >= math.ceil(sample_count / 2)]
    if not selected and rows:
        rows.sort(key=lambda row: (row["vote_count"], -candidate_order.index(row["fqdn"])), reverse=True)
        selected = [rows[0]["fqdn"]]
    rows.sort(key=lambda row: (row["vote_count"], -candidate_order.index(row["fqdn"])), reverse=True)
    return _dedupe_keep_order(selected)[:max_selected], rows


def _load_sentence_transformer(model_name: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "sentence-transformers is not installed. Install it or run non-embedding baselines first."
        ) from exc
    return SentenceTransformer(model_name)


def _embedding_text(model_name: str, text: str, is_query: bool) -> str:
    lowered = model_name.lower()
    if "e5" in lowered:
        return ("query: " if is_query else "passage: ") + text
    return text


def _run_embedding_baseline(
    samples: list[dict[str, Any]],
    catalog_rows: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    import numpy as np

    model = _load_sentence_transformer(args.embedding_model)
    doc_texts = [_embedding_text(args.embedding_model, row["text"], is_query=False) for row in catalog_rows]
    doc_embeddings = np.asarray(model.encode(doc_texts, normalize_embeddings=True), dtype=np.float32)
    traces: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples, start=1):
        query = _embedding_text(args.embedding_model, _sample_query_text(sample), is_query=True)
        query_embedding = np.asarray(model.encode([query], normalize_embeddings=True), dtype=np.float32)[0]
        scores = doc_embeddings @ query_embedding
        ranked: list[dict[str, Any]] = []
        for row, score in zip(catalog_rows, scores):
            output = {key: value for key, value in row.items() if key != "text"}
            output["score"] = round(float(score), 6)
            ranked.append(output)
        ranked.sort(key=lambda row: row["score"], reverse=True)
        selected = _select_by_relative_threshold(
            ranked,
            max_selected=args.max_selected,
            ratio=args.embedding_threshold_ratio,
        )
        traces.append(
            _build_baseline_trace(
                sample,
                "embedding",
                selected,
                ranked[: args.candidate_limit],
                {"embedding_model": args.embedding_model, "embedding_backend": args.embedding_backend},
            )
        )
        if args.progress_every > 0 and idx % args.progress_every == 0:
            print(json.dumps({"progress": {"method": "embedding", "completed": idx, "total": len(samples)}}), flush=True)
    return traces


def _write_method_outputs(
    method: str,
    traces: list[dict[str, Any]],
    output_dir: Path,
    split_name: str,
    args: argparse.Namespace,
) -> tuple[Path, Path]:
    trace_path = output_dir / f"{split_name}.{method}_baseline_v1_20260602.jsonl"
    summary_path = output_dir / f"{split_name}.{method}_baseline_v1_20260602.summary.json"
    dump_jsonl(trace_path, traces)
    summary = {
        "method": method,
        "baseline_version": f"{method}_baseline_v1_20260602",
        "samples": len(traces),
        "input_path": args.input,
        "snapshot_path": args.snapshot,
        "candidate_limit": args.candidate_limit,
        "max_selected": args.max_selected,
        "provider": args.provider if "llm" in method else None,
        "model": args.model if "llm" in method else None,
        "embedding_model": args.embedding_model if method == "embedding" else None,
        "avg_selected_size": round(sum(len(row.get("final_selected_fqdns", [])) for row in traces) / len(traces), 4)
        if traces
        else 0.0,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return trace_path, summary_path


def main() -> int:
    args = parse_args()
    _debug(args, "parsed args")
    samples = load_jsonl(args.input)
    _debug(args, f"loaded samples={len(samples)}")
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    _debug(args, f"using samples={len(samples)}")
    raw_catalog_rows, catalog_by_fqdn = _materialize_catalog(args.descriptors)
    _debug(args, f"materialized catalog={len(raw_catalog_rows)}")
    catalog_rows = _candidate_rows_from_catalog(raw_catalog_rows)
    snapshot_by_id: dict[str, dict[str, Any]] = {}
    if args.snapshot:
        snapshot_by_id = {row["id"]: row for row in load_jsonl(args.snapshot)}
        _debug(args, f"loaded snapshots={len(snapshot_by_id)}")
    if any(method.startswith("flat_llm") for method in args.methods) and not snapshot_by_id:
        raise ValueError("--snapshot is required for flat LLM baselines")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_name = Path(args.input).stem
    outputs: dict[str, dict[str, str]] = {}

    bm25_index = BM25Index(catalog_rows)
    _debug(args, "built bm25")
    chat_client: dict[str, str] | None = None
    chat_provider = args.provider
    chat_model = args.model
    if any(method.startswith("flat_llm") for method in args.methods):
        chat_client, chat_provider, chat_model = _make_chat_client(args.provider, args.model)

    for method in args.methods:
        _debug(args, f"start method={method}")
        trace_path = output_dir / f"{split_name}.{method}_baseline_v1_20260602.jsonl"
        if trace_path.exists() and not args.no_resume:
            traces = load_jsonl(trace_path)
            trace_by_id = {row["sample_id"]: row for row in traces}
        else:
            traces = []
            trace_by_id = {}

        if method == "embedding":
            if trace_by_id and len(trace_by_id) == len(samples):
                traces = [trace_by_id[sample["id"]] for sample in samples]
            else:
                traces = _run_embedding_baseline(samples, catalog_rows, args)
        else:
            for idx, sample in enumerate(samples, start=1):
                sample_id = sample["id"]
                if sample_id in trace_by_id:
                    continue
                if method == "lexical_bm25":
                    ranked = bm25_index.score(_sample_query_text(sample))
                    selected = _select_by_relative_threshold(
                        ranked,
                        max_selected=args.max_selected,
                        ratio=args.lexical_threshold_ratio,
                    )
                    trace = _build_baseline_trace(
                        sample,
                        method,
                        selected,
                        ranked[: args.candidate_limit],
                        {"candidate_source": "namespace_catalog", "threshold_ratio": args.lexical_threshold_ratio},
                    )
                elif method == "flat_llm":
                    assert chat_client is not None and chat_model is not None
                    snapshot = snapshot_by_id.get(sample_id)
                    if not snapshot:
                        raise KeyError(f"Missing snapshot for sample_id={sample_id}")
                    candidates = _candidate_rows_from_snapshot(snapshot, catalog_by_fqdn, args.candidate_limit)
                    selected, obj, raw = _call_flat_llm(
                        chat_client,
                        chat_model,
                        sample,
                        candidates,
                        temperature=args.llm_temperature,
                        max_selected=args.max_selected,
                    )
                    trace = _build_baseline_trace(
                        sample,
                        method,
                        selected,
                        [{key: value for key, value in row.items() if key != "text"} for row in candidates],
                        {
                            "candidate_source": "stage_r_top_k_desc_alias_only",
                            "provider": chat_provider,
                            "model": chat_model,
                            "llm_decision": obj,
                            "llm_raw_response": raw,
                        },
                    )
                elif method == "flat_llm_self_consistency":
                    assert chat_client is not None and chat_model is not None
                    snapshot = snapshot_by_id.get(sample_id)
                    if not snapshot:
                        raise KeyError(f"Missing snapshot for sample_id={sample_id}")
                    candidates = _candidate_rows_from_snapshot(snapshot, catalog_by_fqdn, args.candidate_limit)
                    votes: list[list[str]] = []
                    raw_decisions: list[dict[str, Any]] = []
                    raw_texts: list[str] = []
                    for sample_index in range(args.self_consistency_samples):
                        selected, obj, raw = _call_flat_llm(
                            chat_client,
                            chat_model,
                            sample,
                            candidates,
                            temperature=args.self_consistency_temperature,
                            max_selected=args.max_selected,
                        )
                        votes.append(selected)
                        raw_decisions.append(obj)
                        raw_texts.append(raw)
                    selected, vote_rows = _self_consistency_select(votes, candidates, args.max_selected)
                    trace = _build_baseline_trace(
                        sample,
                        method,
                        selected,
                        vote_rows,
                        {
                            "candidate_source": "stage_r_top_k_desc_alias_only",
                            "provider": chat_provider,
                            "model": chat_model,
                            "self_consistency_samples": args.self_consistency_samples,
                            "self_consistency_temperature": args.self_consistency_temperature,
                            "votes": votes,
                            "llm_decisions": raw_decisions,
                            "llm_raw_responses": raw_texts,
                        },
                    )
                else:
                    raise ValueError(f"Unsupported method: {method}")
                trace_by_id[sample_id] = trace
                traces = [trace_by_id[item["id"]] for item in samples if item["id"] in trace_by_id]
                dump_jsonl(trace_path, traces)
                if args.progress_every > 0 and idx % args.progress_every == 0:
                    print(json.dumps({"progress": {"method": method, "completed": idx, "total": len(samples)}}), flush=True)
            traces = [trace_by_id[sample["id"]] for sample in samples if sample["id"] in trace_by_id]

        trace_path, summary_path = _write_method_outputs(method, traces, output_dir, split_name, args)
        outputs[method] = {"trace_path": str(trace_path), "summary_path": str(summary_path)}

    print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
