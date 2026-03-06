from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .namespace import NamespaceResolver, RoutingNode


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dump_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


PUNCT_RE = re.compile(r"[，。！？；：、“”‘’（）()【】《》,.!?:;\"'`\-\[\]{}_/\\\s]+")


def normalize_text(value: str) -> str:
    return PUNCT_RE.sub("", value.lower())


def char_ngrams(text: str, n: int = 3) -> set[str]:
    cleaned = normalize_text(text)
    if len(cleaned) < n:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _context_to_text(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    values: list[str] = []
    for value in context.values():
        if value is None:
            continue
        values.append(str(value))
    return " ".join(values)


def _query_markers(query: str) -> dict[str, bool]:
    return {
        "has_multi_intent_marker": any(marker in query for marker in ("并", "同时", "顺便", "顺手", "以及", "并且", "另外")),
        "has_question_marker": any(marker in query for marker in ("哪些", "怎么", "如何", "是否", "吗")),
    }


def _node_search_text(node: RoutingNode) -> str:
    parts = list(node.aliases)
    if node.desc:
        parts.append(node.desc)
    if node.segment:
        parts.append(node.segment)
    parts.extend(node.industry_tags)
    return " ".join(parts)


def _context_score(node: RoutingNode, context: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not context:
        return 0.0, []
    score = 0.0
    hits: list[str] = []
    industry = context.get("industry")
    if industry and industry in node.industry_tags:
        score += 1.0
        hits.append(f"industry:{industry}")
    city = context.get("city")
    if node.segment and city and str(city).lower() == node.segment:
        score += 1.2
        hits.append(f"segment:{node.segment}")
    return score, hits


def _alias_score(node: RoutingNode, query_text: str, context_text: str) -> tuple[float, list[str]]:
    score = 0.0
    hits: list[str] = []
    full_text = f"{query_text} {context_text}"
    for alias in node.aliases:
        if not alias:
            continue
        alias_norm = normalize_text(alias)
        if not alias_norm:
            continue
        if alias_norm in normalize_text(full_text):
            base = min(len(alias_norm), 4) / 4.0
            if len(alias_norm) <= 2:
                base *= 0.45
            if node.segment and alias_norm in normalize_text(query_text):
                base += 0.25
            score += base
            hits.append(alias)
    return score, hits


def _desc_similarity_score(node: RoutingNode, query_text: str, context_text: str) -> tuple[float, list[str]]:
    node_text = _node_search_text(node)
    sim = jaccard(char_ngrams(query_text + " " + context_text), char_ngrams(node_text))
    hits: list[str] = []
    if sim > 0:
        hits.append("char_trigram")
    return sim, hits


def score_node(node: RoutingNode, query: str, context: dict[str, Any] | None) -> dict[str, Any]:
    context_text = _context_to_text(context)
    alias_score, alias_hits = _alias_score(node, query, context_text)
    desc_sim, desc_hits = _desc_similarity_score(node, query, context_text)
    context_score, context_hits = _context_score(node, context)
    desc_sim_effective = desc_sim if desc_sim >= 0.10 else 0.0
    context_score_effective = context_score if (alias_hits or desc_sim_effective > 0.0) else 0.0

    overspecific_penalty = 0.0
    if node.node_kind == "segment" and not any(hit.startswith("segment:") for hit in context_hits) and not alias_hits:
        overspecific_penalty = 0.18

    raw = (
        0.60 * min(alias_score, 1.8)
        + 0.25 * desc_sim_effective
        + 0.15 * min(context_score_effective, 1.2)
        - overspecific_penalty
    )
    score = max(raw, 0.0)
    sources: list[str] = []
    if alias_hits:
        sources.append("alias")
    if desc_hits:
        sources.append("desc_overlap")
    if context_hits:
        sources.append("context")
    if node.node_kind == "segment":
        sources.append("segment_node")

    return {
        "fqdn": node.fqdn,
        "node_kind": node.node_kind,
        "l1": node.l1,
        "l2": node.l2,
        "segment": node.segment,
        "parent_fqdn": node.parent_fqdn,
        "fallback_to": node.fallback_to,
        "score_r": round(score, 6),
        "source": sources,
        "components": {
            "alias_score": round(min(alias_score, 1.8), 6),
            "desc_similarity": round(desc_sim_effective, 6),
            "context_score": round(min(context_score_effective, 1.2), 6),
            "overspecific_penalty": round(overspecific_penalty, 6),
        },
        "matched_phrases": {
            "aliases": alias_hits,
            "context": context_hits,
        },
    }


def _dedupe_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        fqdn = row["fqdn"]
        if fqdn in seen:
            continue
        seen.add(fqdn)
        out.append(row)
    return out


def _add_parent_fallbacks(
    resolver: NamespaceResolver,
    ranked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    augmented = list(ranked)
    for row in list(ranked):
        parent = row.get("parent_fqdn")
        if not parent:
            continue
        parent_node = resolver.get_node(parent)
        if not parent_node:
            continue
        augmented.append(
            {
                "fqdn": parent_node.fqdn,
                "node_kind": parent_node.node_kind,
                "l1": parent_node.l1,
                "l2": parent_node.l2,
                "segment": parent_node.segment,
                "parent_fqdn": parent_node.parent_fqdn,
                "fallback_to": parent_node.fallback_to,
                "score_r": round(max(row["score_r"] - 0.03, 0.0), 6),
                "source": ["parent_fallback"],
            }
        )
    return _dedupe_candidates(sorted(augmented, key=lambda x: (-x["score_r"], x["fqdn"])))


def _confusion_sources(candidates: list[dict[str, Any]], query: str) -> list[str]:
    sources: list[str] = []
    if any(marker in query for marker in ("并", "同时", "顺便", "另外", "再")):
        sources.append("C1_multi_intent")
    if len(candidates) >= 2 and candidates[0]["l1"] != candidates[1]["l1"]:
        sources.append("C5_cross_domain_overlap")
    if len(candidates) >= 2 and candidates[0].get("l2") == candidates[1].get("l2") and candidates[0]["fqdn"] != candidates[1]["fqdn"]:
        sources.append("C3_sibling_competition")
    if any(row.get("parent_fqdn") for row in candidates[:5]) and any(row["source"] == ["parent_fallback"] for row in candidates[:8]):
        sources.append("C4_governance_fallback")
    if not sources:
        sources.append("C0_low_confusion")
    return sources


def build_candidate_snapshot(
    sample: dict[str, Any],
    resolver: NamespaceResolver,
    top_k: int,
    stage_r_version: str,
) -> dict[str, Any]:
    query = sample["query"]
    context = sample.get("context") or {}
    scored = [score_node(node, query, context) for node in resolver.iter_nodes()]
    ranked = [row for row in sorted(scored, key=lambda x: (-x["score_r"], x["fqdn"])) if row["score_r"] > 0]
    ranked = _add_parent_fallbacks(resolver, ranked)
    candidates = ranked[:top_k]

    semantic_parse = {
        "query_markers": _query_markers(query),
        "context_features": context,
        "matched_candidate_fqdns": [row["fqdn"] for row in candidates[:8]],
    }

    snapshot: dict[str, Any] = {
        "id": sample["id"],
        "namespace_version": sample["namespace_version"],
        "stage_r_version": stage_r_version,
        "semantic_parse": semantic_parse,
        "descriptor_scores": ranked[: min(20, len(ranked))],
        "subtree_scores": {},
        "fqdn_candidates": candidates,
        "confusion_sources": _confusion_sources(candidates, query),
        "candidate_generation_rules": [
            "descriptor_only_recall",
            "no_examples_in_index",
            "no_bootstrap_lexicon",
            "parent_fallback_for_segment_nodes",
        ],
    }

    if "ground_truth_fqdn" in sample:
        top_fqdns = [row["fqdn"] for row in candidates]
        relevant = sample.get("relevant_fqdns", [])
        snapshot["candidate_recall_hit"] = {
            "primary_in_top_k": sample["ground_truth_fqdn"] in top_fqdns,
            "related_hits": [fqdn for fqdn in relevant if fqdn in top_fqdns],
        }
    return snapshot
