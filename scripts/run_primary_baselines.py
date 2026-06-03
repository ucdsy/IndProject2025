#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import socket
import sys
import urllib.error
import urllib.request
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PUNCT_RE = re.compile(r"[，。！？；：、“”‘’（）()【】《》,.!?:;\"'`\-\[\]{}_/\\\s]+")
ASCII_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
FQDN_RE = re.compile(r"^(?:[a-z0-9-]+\.){1,3}cn$")
RAW_FQDN_RE = re.compile(r"\b(?:[a-z0-9-]+\.){1,3}cn\b")


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


def validate_fqdn(value: str | None) -> bool:
    return bool(FQDN_RE.match((value or "").strip().lower()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run primary-label baselines for the retrospective train/test protocol.")
    parser.add_argument("--input", required=True, help="Labeled input jsonl, e.g. retrospective test_joined.jsonl.")
    parser.add_argument("--snapshot", required=True, help="Stage R snapshot jsonl aligned to --input.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
        help="Namespace descriptor jsonl.",
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=["lexical_bm25", "embedding", "flat_llm", "flat_llm_self_consistency"],
        required=True,
    )
    parser.add_argument("--candidate-limit", type=int, default=10)
    parser.add_argument(
        "--candidate-order",
        choices=["stage_r", "alphabetical", "shuffle"],
        default="stage_r",
        help="Display order for flat LLM candidates. Non-LLM baselines keep their native ranking.",
    )
    parser.add_argument("--candidate-shuffle-seed", type=int, default=0)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--progress-every", type=int, default=10)
    parser.add_argument("--provider", choices=["deepseek", "openai"], default="deepseek")
    parser.add_argument("--model", default=None)
    parser.add_argument("--llm-temperature", type=float, default=0.0)
    parser.add_argument("--self-consistency-samples", type=int, default=3)
    parser.add_argument("--self-consistency-temperature", type=float, default=0.7)
    parser.add_argument("--embedding-model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--lexical-top1", action="store_true", default=True)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def debug(args: argparse.Namespace, message: str) -> None:
    if args.debug:
        print(f"[debug] {message}", file=sys.stderr, flush=True)


def normalize_text(value: str) -> str:
    return PUNCT_RE.sub("", (value or "").lower())


def context_to_text(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    for value in context.values():
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(item) for item in value if item is not None)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts)


def sample_query_text(sample: dict[str, Any]) -> str:
    return " ".join(part for part in [sample.get("query", ""), context_to_text(sample.get("context"))] if part).strip()


def char_ngrams(text: str, n: int) -> list[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    if len(cleaned) <= n:
        return [cleaned]
    return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]


def tokens(text: str) -> list[str]:
    lowered = (text or "").lower()
    out: list[str] = []
    out.extend(ASCII_WORD_RE.findall(lowered))
    normalized = normalize_text(lowered)
    if CJK_RE.search(normalized):
        out.extend(char_ngrams(normalized, 1))
        out.extend(char_ngrams(normalized, 2))
        out.extend(char_ngrams(normalized, 3))
    elif normalized:
        out.append(normalized)
    return [token for token in out if token]


def row_text(row: dict[str, Any]) -> str:
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
    return " ".join(str(part) for part in parts if part)


def materialize_catalog(descriptor_path: str | Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
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
        base_row["text"] = row_text(base_row)
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
            segment_row["text"] = row_text(segment_row)
            rows.append(segment_row)
    rows.sort(key=lambda row: (row.get("depth", 0), row["fqdn"]))
    return rows, {row["fqdn"]: row for row in rows}


class BM25Index:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.docs = [tokens(row["text"]) for row in rows]
        self.counters = [Counter(doc) for doc in self.docs]
        self.lengths = [len(doc) for doc in self.docs]
        self.avg_len = sum(self.lengths) / len(self.lengths) if self.lengths else 1.0
        df: Counter[str] = Counter()
        for doc in self.docs:
            df.update(set(doc))
        total = len(self.docs)
        self.idf = {
            token: math.log(1.0 + (total - freq + 0.5) / (freq + 0.5))
            for token, freq in df.items()
        }

    def score(self, query: str) -> list[dict[str, Any]]:
        query_counter = Counter(tokens(query))
        k1 = 1.4
        b = 0.72
        ranked: list[dict[str, Any]] = []
        for row, counter, doc_len in zip(self.rows, self.counters, self.lengths):
            score = 0.0
            for token, query_tf in query_counter.items():
                tf = counter.get(token, 0)
                if not tf:
                    continue
                denom = tf + k1 * (1.0 - b + b * doc_len / max(self.avg_len, 1e-6))
                score += self.idf.get(token, 0.0) * (tf * (k1 + 1.0) / max(denom, 1e-6)) * min(query_tf, 3)
            if score > 0:
                output = {key: value for key, value in row.items() if key != "text"}
                output["score"] = round(score, 6)
                ranked.append(output)
        return sorted(ranked, key=lambda item: item["score"], reverse=True)


def make_chat_client(provider: str, model: str | None) -> tuple[dict[str, str], str, str]:
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


def chat_completion_http(client: dict[str, str], payload: dict[str, Any], *, use_json_mode: bool = True, attempts: int = 3) -> str:
    body = dict(payload)
    if use_json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        client["base_url"].rstrip("/") + "/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {client['api_key']}", "Content-Type": "application/json"},
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
                return chat_completion_http(client, payload, use_json_mode=False, attempts=attempts)
            last_error = RuntimeError(exc.read().decode("utf-8", errors="replace"))
        except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            last_error = exc
        if attempt < attempts:
            continue
    if last_error:
        raise last_error
    raise RuntimeError("chat completion failed")


def load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def snapshot_candidates(snapshot: dict[str, Any], catalog_by_fqdn: dict[str, dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    candidates = sorted(snapshot.get("fqdn_candidates", []), key=lambda row: row.get("score_r", 0.0), reverse=True)
    rows: list[dict[str, Any]] = []
    for item in candidates[:limit]:
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
                "score_r": item.get("score_r"),
            }
        )
    return rows


def flat_llm_prompt(sample: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    exposed = [
        {"fqdn": row["fqdn"], "desc": row.get("desc", ""), "aliases": row.get("aliases", [])}
        for row in candidates
    ]
    packet = {
        "sample_id": sample["id"],
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "candidates": exposed,
        "task": "Select exactly one primary FQDN that best handles the user's main intent.",
        "rules": [
            "Use only FQDNs from candidates.",
            "If the query includes multiple requests, choose the main capability that should receive the request first.",
            "Do not output related or auxiliary FQDNs.",
            "Return one JSON object only.",
        ],
        "output_schema": {
            "primary_fqdn": "one fqdn from candidates",
            "confidence": "0..1",
            "rationale": "short string",
        },
    }
    return json.dumps(packet, ensure_ascii=False, indent=2)


def call_flat_llm(
    client: dict[str, str],
    model: str,
    sample: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    temperature: float,
) -> tuple[str | None, dict[str, Any], str]:
    system = (
        "You are a flat AgentDNS primary-label selector. "
        "You only see FQDN, description, and aliases for candidates. "
        "Do not use hidden structured routing fields or scores. "
        "Return one JSON object."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": flat_llm_prompt(sample, candidates)},
        ],
        "temperature": temperature,
        "max_tokens": 900,
    }
    raw = chat_completion_http(client, payload)
    candidate_set = {row["fqdn"] for row in candidates}
    try:
        obj = load_json_object(raw)
    except Exception as exc:
        obj = {"parse_error": str(exc), "raw_response": raw}
    primary = obj.get("primary_fqdn") or obj.get("selected_primary_fqdn") or obj.get("selected_fqdn")
    if not isinstance(primary, str):
        for fqdn in RAW_FQDN_RE.findall(raw.lower()):
            if fqdn in candidate_set:
                primary = fqdn
                break
    if not isinstance(primary, str) or primary not in candidate_set or not validate_fqdn(primary):
        primary = candidates[0]["fqdn"] if candidates else None
    return primary, obj, raw


def vote_primary(votes: list[str | None], candidates: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    order = [row["fqdn"] for row in candidates]
    counts = Counter(fqdn for fqdn in votes if fqdn)
    vote_rows = [
        {"fqdn": fqdn, "vote_count": counts.get(fqdn, 0), "vote_ratio": round(counts.get(fqdn, 0) / max(len(votes), 1), 6)}
        for fqdn in order
    ]
    vote_rows.sort(key=lambda row: (row["vote_count"], -order.index(row["fqdn"])), reverse=True)
    return (vote_rows[0]["fqdn"] if vote_rows else None), vote_rows


def order_flat_llm_candidates(
    candidates: list[dict[str, Any]],
    *,
    order: str,
    seed: int,
    sample_id: str,
) -> list[dict[str, Any]]:
    if order == "stage_r":
        return list(candidates)
    if order == "alphabetical":
        return sorted(candidates, key=lambda row: row["fqdn"])
    if order == "shuffle":
        shuffled = list(candidates)
        rng = random.Random(f"{seed}:{sample_id}")
        rng.shuffle(shuffled)
        return shuffled
    raise ValueError(f"Unsupported candidate order: {order}")


def load_sentence_transformer(model_name: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:
        raise RuntimeError("sentence-transformers is not installed") from exc
    return SentenceTransformer(model_name)


def embedding_text(model_name: str, text: str, is_query: bool) -> str:
    if "e5" in model_name.lower():
        return ("query: " if is_query else "passage: ") + text
    return text


def minimal_stage_r(ranked: list[dict[str, Any]], stage_r_version: str) -> dict[str, Any]:
    return {
        "stage_r_version": stage_r_version,
        "fqdn_candidates": ranked,
    }


def build_trace(
    sample: dict[str, Any],
    method: str,
    primary: str | None,
    ranked: list[dict[str, Any]],
    stage_r: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    confidence = float((ranked[0].get("score") or ranked[0].get("score_r") or 0.0)) if ranked else 0.0
    margin = 0.0
    if len(ranked) >= 2:
        first = float(ranked[0].get("score") or ranked[0].get("score_r") or 0.0)
        second = float(ranked[1].get("score") or ranked[1].get("score_r") or 0.0)
        margin = first - second
    primary = primary if validate_fqdn(primary) else None
    return {
        "run_id": f"run_{method}_{sample['id']}_{uuid.uuid4().hex[:8]}",
        "sample_id": sample["id"],
        "baseline_version": f"{method}_primary_baseline_v1_20260602",
        "baseline_method": method,
        "stage_r_version": stage_r.get("stage_r_version", "primary_baseline_candidates_v1"),
        "stage_r": stage_r,
        "stage_a": {
            "stage_a_version": f"{method}_primary_baseline_v1_20260602",
            "selected_primary_fqdn": primary,
            "selected_related_fqdns": [],
            "confidence": round(confidence, 6),
            "margin": round(margin, 6),
            "escalate_to_stage_b": False,
            "escalation_reasons": [],
        },
        "entered_stage_b": False,
        "final_primary_fqdn": primary,
        "final_related_fqdns": [],
        "final_decision_source": method,
        "final_related_source": method,
        "stage_baseline": {"method": method, "ranked_candidates": ranked, **(extra or {})},
    }


def evaluate_primary(samples: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    trace_by_id = {row["sample_id"]: row for row in traces}
    per_sample: list[dict[str, Any]] = []
    for sample in samples:
        trace = trace_by_id[sample["id"]]
        pred = trace.get("final_primary_fqdn")
        gt = sample["ground_truth_fqdn"]
        acceptable = set(sample.get("acceptable_fqdns") or [gt])
        row = {
            "id": sample["id"],
            "ground_truth_fqdn": gt,
            "acceptable_fqdns": sorted(acceptable),
            "final_primary_fqdn": pred,
            "primary_hit": pred == gt,
            "acceptable_hit": pred in acceptable,
            "source": trace.get("final_decision_source"),
        }
        per_sample.append(row)
    total = len(per_sample)
    primary = sum(1 for row in per_sample if row["primary_hit"])
    acceptable = sum(1 for row in per_sample if row["acceptable_hit"])
    return {
        "samples": total,
        "primary_correct": primary,
        "acceptable_correct": acceptable,
        "PrimaryAcc@1": round(primary / total, 4) if total else 0.0,
        "AcceptablePrimary@1": round(acceptable / total, 4) if total else 0.0,
        "per_sample": per_sample,
    }


def write_outputs(method: str, traces: list[dict[str, Any]], output_dir: Path, split_name: str, args: argparse.Namespace) -> dict[str, str]:
    trace_path = output_dir / f"{split_name}.{method}_primary_baseline_v1_20260602.jsonl"
    summary_path = output_dir / f"{split_name}.{method}_primary_baseline_v1_20260602.summary.json"
    dump_jsonl(trace_path, traces)
    summary = evaluate_primary(load_jsonl(args.input), traces)
    summary.update(
        {
            "method": method,
            "baseline_version": f"{method}_primary_baseline_v1_20260602",
            "input_path": args.input,
            "snapshot_path": args.snapshot,
            "candidate_limit": args.candidate_limit,
            "candidate_order": args.candidate_order if "llm" in method else None,
            "candidate_shuffle_seed": args.candidate_shuffle_seed
            if "llm" in method and args.candidate_order == "shuffle"
            else None,
            "provider": args.provider if "llm" in method else None,
            "model": args.model if "llm" in method else None,
            "embedding_model": args.embedding_model if method == "embedding" else None,
        }
    )
    per_sample = summary.pop("per_sample")
    per_sample_path = output_dir / f"{split_name}.{method}_primary_baseline_v1_20260602.per_sample.jsonl"
    dump_jsonl(per_sample_path, per_sample)
    summary["per_sample_path"] = str(per_sample_path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"trace_path": str(trace_path), "summary_path": str(summary_path), "per_sample_path": str(per_sample_path)}


def main() -> int:
    args = parse_args()
    samples = load_jsonl(args.input)
    snapshots = {row["id"]: row for row in load_jsonl(args.snapshot)}
    catalog_rows, catalog_by_fqdn = materialize_catalog(args.descriptors)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    split_name = Path(args.input).stem
    outputs: dict[str, dict[str, str]] = {}

    bm25_index = BM25Index(catalog_rows)
    chat_client: dict[str, str] | None = None
    chat_provider = args.provider
    chat_model = args.model
    if any(method.startswith("flat_llm") for method in args.methods):
        chat_client, chat_provider, chat_model = make_chat_client(args.provider, args.model)

    embedding_model: Any | None = None
    doc_embeddings: Any | None = None
    np: Any | None = None
    if "embedding" in args.methods:
        import numpy as _np

        np = _np
        embedding_model = load_sentence_transformer(args.embedding_model)
        doc_texts = [embedding_text(args.embedding_model, row["text"], is_query=False) for row in catalog_rows]
        doc_embeddings = np.asarray(embedding_model.encode(doc_texts, normalize_embeddings=True), dtype=np.float32)

    for method in args.methods:
        trace_path = output_dir / f"{split_name}.{method}_primary_baseline_v1_20260602.jsonl"
        if trace_path.exists() and not args.no_resume:
            traces = load_jsonl(trace_path)
            trace_by_id = {row["sample_id"]: row for row in traces}
        else:
            traces = []
            trace_by_id = {}

        for idx, sample in enumerate(samples, start=1):
            if sample["id"] in trace_by_id:
                continue
            if method == "lexical_bm25":
                ranked = bm25_index.score(sample_query_text(sample))[: args.candidate_limit]
                primary = ranked[0]["fqdn"] if ranked else None
                stage_r = minimal_stage_r(ranked, "lexical_bm25_primary_baseline_v1")
                trace = build_trace(sample, method, primary, ranked, stage_r, {"candidate_source": "namespace_catalog"})
            elif method == "embedding":
                assert embedding_model is not None and doc_embeddings is not None and np is not None
                query = embedding_text(args.embedding_model, sample_query_text(sample), is_query=True)
                query_embedding = np.asarray(embedding_model.encode([query], normalize_embeddings=True), dtype=np.float32)[0]
                scores = doc_embeddings @ query_embedding
                ranked = []
                for row, score in zip(catalog_rows, scores):
                    output = {key: value for key, value in row.items() if key != "text"}
                    output["score"] = round(float(score), 6)
                    ranked.append(output)
                ranked.sort(key=lambda row: row["score"], reverse=True)
                ranked = ranked[: args.candidate_limit]
                primary = ranked[0]["fqdn"] if ranked else None
                stage_r = minimal_stage_r(ranked, "embedding_primary_baseline_v1")
                trace = build_trace(
                    sample,
                    method,
                    primary,
                    ranked,
                    stage_r,
                    {"candidate_source": "namespace_catalog", "embedding_model": args.embedding_model},
                )
            elif method in {"flat_llm", "flat_llm_self_consistency"}:
                assert chat_client is not None and chat_model is not None
                snapshot = snapshots.get(sample["id"])
                if not snapshot:
                    raise KeyError(f"Missing Stage R snapshot for sample_id={sample['id']}")
                stage_r_candidates = snapshot_candidates(snapshot, catalog_by_fqdn, args.candidate_limit)
                candidates = order_flat_llm_candidates(
                    stage_r_candidates,
                    order=args.candidate_order,
                    seed=args.candidate_shuffle_seed,
                    sample_id=sample["id"],
                )
                if method == "flat_llm":
                    primary, obj, raw = call_flat_llm(
                        chat_client,
                        chat_model,
                        sample,
                        candidates,
                        temperature=args.llm_temperature,
                    )
                    trace = build_trace(
                        sample,
                        method,
                        primary,
                        candidates,
                        snapshot,
                        {
                            "candidate_source": "stage_r_top_k_desc_alias_only",
                            "candidate_order": args.candidate_order,
                            "candidate_shuffle_seed": args.candidate_shuffle_seed
                            if args.candidate_order == "shuffle"
                            else None,
                            "provider": chat_provider,
                            "model": chat_model,
                            "llm_decision": obj,
                            "llm_raw_response": raw,
                        },
                    )
                else:
                    votes: list[str | None] = []
                    decisions: list[dict[str, Any]] = []
                    raws: list[str] = []
                    for _ in range(args.self_consistency_samples):
                        primary, obj, raw = call_flat_llm(
                            chat_client,
                            chat_model,
                            sample,
                            candidates,
                            temperature=args.self_consistency_temperature,
                        )
                        votes.append(primary)
                        decisions.append(obj)
                        raws.append(raw)
                    primary, vote_rows = vote_primary(votes, candidates)
                    trace = build_trace(
                        sample,
                        method,
                        primary,
                        candidates,
                        snapshot,
                        {
                            "candidate_source": "stage_r_top_k_desc_alias_only",
                            "candidate_order": args.candidate_order,
                            "candidate_shuffle_seed": args.candidate_shuffle_seed
                            if args.candidate_order == "shuffle"
                            else None,
                            "provider": chat_provider,
                            "model": chat_model,
                            "self_consistency_samples": args.self_consistency_samples,
                            "self_consistency_temperature": args.self_consistency_temperature,
                            "votes": votes,
                            "vote_rows": vote_rows,
                            "llm_decisions": decisions,
                            "llm_raw_responses": raws,
                        },
                    )
            else:
                raise ValueError(f"Unsupported method: {method}")

            trace_by_id[sample["id"]] = trace
            traces = [trace_by_id[row["id"]] for row in samples if row["id"] in trace_by_id]
            dump_jsonl(trace_path, traces)
            if args.progress_every > 0 and idx % args.progress_every == 0:
                print(json.dumps({"progress": {"method": method, "completed": idx, "total": len(samples)}}), flush=True)

        traces = [trace_by_id[row["id"]] for row in samples if row["id"] in trace_by_id]
        outputs[method] = write_outputs(method, traces, output_dir, split_name, args)

    print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
