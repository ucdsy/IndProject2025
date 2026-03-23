from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
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
CJK_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class StageRCleanConfig:
    lexical_signal_scale: float = 1.0
    desc_signal_scale: float = 1.0
    context_signal_scale: float = 1.0
    segment_penalty_scale: float = 1.0
    hierarchy_bonus_scale: float = 1.0
    strict_parent_segment_limit: int = 1
    relaxed_parent_segment_limit: int = 3
    multi_intent_head_budget: int = 5
    default_head_budget: int = 7
    signal_window: int = 6
    close_score_delta: float = 0.08
    enable_context_facet_match: bool = True
    enable_hierarchy_rerank: bool = True
    enable_parent_fallback: bool = True
    enable_diversified_selection: bool = True
    enable_low_signal_fallback: bool = True

    @property
    def query_alias_weight(self) -> float:
        return 0.58 * self.lexical_signal_scale

    @property
    def context_alias_weight(self) -> float:
        return 0.09 * self.lexical_signal_scale

    @property
    def desc_similarity_weight(self) -> float:
        return 0.20 * self.desc_signal_scale

    @property
    def context_match_weight(self) -> float:
        return 0.13 * self.context_signal_scale

    @property
    def desc_similarity_threshold(self) -> float:
        return 0.01

    @property
    def desc_bigram_backoff_scale(self) -> float:
        return 0.6

    @property
    def metadata_exact_match(self) -> float:
        return 0.9

    @property
    def segment_exact_match(self) -> float:
        return 0.7

    @property
    def segment_query_bonus(self) -> float:
        return 0.10

    @property
    def segment_context_bonus(self) -> float:
        return 0.03

    @property
    def short_segment_alias_discount(self) -> float:
        return 0.55

    @property
    def segment_context_only_penalty(self) -> float:
        return 0.10 * self.segment_penalty_scale

    @property
    def segment_missing_segment_hit_penalty(self) -> float:
        return 0.06 * self.segment_penalty_scale

    @property
    def segment_low_desc_penalty(self) -> float:
        return 0.06 * self.segment_penalty_scale

    @property
    def segment_desc_penalty_threshold(self) -> float:
        return 0.08

    @property
    def base_child_support_cap(self) -> float:
        return 0.30

    @property
    def base_child_support_weight(self) -> float:
        return 0.25 * self.hierarchy_bonus_scale

    @property
    def segment_parent_bonus_cap(self) -> float:
        return 0.40

    @property
    def segment_parent_bonus_weight(self) -> float:
        return 0.18 * self.hierarchy_bonus_scale

    @property
    def segment_weak_parent_threshold(self) -> float:
        return 0.12

    @property
    def segment_weak_parent_penalty(self) -> float:
        return 0.08 * self.segment_penalty_scale


def normalize_text(value: str) -> str:
    return PUNCT_RE.sub("", value.lower())


def contains_cjk(value: str) -> bool:
    return bool(CJK_RE.search(value))


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


def _context_items(context: dict[str, Any] | None) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if not context:
        return items
    for key, value in context.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                normalized = normalize_text(str(item))
                if normalized:
                    items.append((str(key), normalized))
            continue
        normalized = normalize_text(str(value))
        if normalized:
            items.append((str(key), normalized))
    return items


def _node_search_text(node: RoutingNode) -> str:
    parts = list(node.aliases)
    if node.desc:
        parts.append(node.desc)
    parts.append(node.l1)
    if node.l2:
        parts.append(node.l2)
    if node.segment:
        parts.append(node.segment)
    parts.extend(node.industry_tags)
    parts.extend(node.risk_tags)
    parts.extend(node.action_tags)
    parts.extend(node.object_tags)
    return " ".join(parts)


def _node_metadata_values(node: RoutingNode) -> set[str]:
    values = {
        normalize_text(value)
        for value in (
            node.l1,
            node.l2,
            *node.industry_tags,
            *node.risk_tags,
            *node.action_tags,
            *node.object_tags,
        )
        if value and normalize_text(value)
    }
    return values


def _context_score(
    node: RoutingNode,
    context: dict[str, Any] | None,
    config: StageRCleanConfig,
) -> tuple[float, list[str]]:
    if not context or not config.enable_context_facet_match:
        return 0.0, []
    score = 0.0
    hits: list[str] = []
    seen_signals: set[tuple[str, str]] = set()
    metadata_values = _node_metadata_values(node)
    segment_value = normalize_text(node.segment) if node.segment else ""
    for field_name, value_norm in _context_items(context):
        if value_norm in metadata_values and ("metadata", value_norm) not in seen_signals:
            seen_signals.add(("metadata", value_norm))
            score += config.metadata_exact_match
            hits.append(f"{field_name}:metadata:{value_norm}")
        if segment_value and value_norm == segment_value and ("segment", value_norm) not in seen_signals:
            seen_signals.add(("segment", value_norm))
            score += config.segment_exact_match
            hits.append(f"{field_name}:segment:{value_norm}")
    return score, hits


def _alias_score(
    node: RoutingNode,
    query_text: str,
    context_text: str,
    config: StageRCleanConfig,
) -> tuple[float, float, list[str]]:
    query_score = 0.0
    context_score = 0.0
    hits: list[str] = []
    query_norm = normalize_text(query_text)
    context_norm = normalize_text(context_text)
    for alias in node.aliases:
        if not alias:
            continue
        alias_norm = normalize_text(alias)
        if not alias_norm:
            continue
        base = min(len(alias_norm), 4) / 4.0
        if len(alias_norm) <= 2:
            base *= 0.65 if contains_cjk(alias_norm) else 0.45
        if node.node_kind == "segment" and len(alias_norm) <= 2:
            base *= config.short_segment_alias_discount

        query_hit = alias_norm in query_norm
        context_hit = alias_norm in context_norm
        if not query_hit and not context_hit:
            continue

        if query_hit:
            query_bonus = config.segment_query_bonus if node.segment else 0.0
            query_score += base + query_bonus
            hits.append(f"query:{alias}")
        elif context_hit:
            context_bonus = config.segment_context_bonus if node.segment else 0.0
            context_score += base * 0.35 + context_bonus
            hits.append(f"context:{alias}")
    return query_score, context_score, hits


def _desc_similarity_score(
    node: RoutingNode,
    query_text: str,
    config: StageRCleanConfig,
) -> tuple[float, list[str]]:
    node_text = _node_search_text(node)
    tri_sim = jaccard(char_ngrams(query_text, n=3), char_ngrams(node_text, n=3))
    bi_sim = 0.0
    if contains_cjk(query_text) or contains_cjk(node_text):
        bi_sim = jaccard(char_ngrams(query_text, n=2), char_ngrams(node_text, n=2))
    sim = tri_sim
    hits: list[str] = []
    if tri_sim > 0:
        hits.append("char_trigram")
    if bi_sim > 0 and bi_sim * config.desc_bigram_backoff_scale > sim:
        sim = bi_sim * config.desc_bigram_backoff_scale
        hits.append("char_bigram_backoff")
    return sim, hits


def score_node(
    node: RoutingNode,
    query: str,
    context: dict[str, Any] | None,
    config: StageRCleanConfig,
) -> dict[str, Any]:
    context_text = _context_to_text(context)
    query_alias_score, context_alias_score, alias_hits = _alias_score(node, query, context_text, config)
    desc_sim, desc_hits = _desc_similarity_score(node, query, config)
    context_score, context_hits = _context_score(node, context, config)
    desc_sim_effective = desc_sim if desc_sim >= config.desc_similarity_threshold else 0.0
    context_score_effective = context_score if (query_alias_score > 0.0 or desc_sim_effective > 0.0 or context_alias_score > 0.0) else 0.0

    overspecific_penalty = 0.0
    if node.node_kind == "segment":
        if query_alias_score == 0.0 and context_alias_score > 0.0:
            overspecific_penalty += config.segment_context_only_penalty
        if query_alias_score == 0.0 and not any(":segment:" in hit for hit in context_hits):
            overspecific_penalty += config.segment_missing_segment_hit_penalty
        if query_alias_score == 0.0 and desc_sim_effective < config.segment_desc_penalty_threshold:
            overspecific_penalty += config.segment_low_desc_penalty

    raw = (
        config.query_alias_weight * min(query_alias_score, 1.8)
        + config.context_alias_weight * min(context_alias_score, 0.9)
        + config.desc_similarity_weight * desc_sim_effective
        + config.context_match_weight * min(context_score_effective, 1.0)
        - overspecific_penalty
    )
    score = max(raw, 0.0)
    sources: list[str] = []
    if query_alias_score > 0.0 or context_alias_score > 0.0:
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
            "query_alias_score": round(min(query_alias_score, 1.8), 6),
            "context_alias_score": round(min(context_alias_score, 0.9), 6),
            "raw_desc_similarity": round(desc_sim, 6),
            "desc_similarity": round(desc_sim_effective, 6),
            "context_score": round(min(context_score_effective, 1.0), 6),
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


def _rank_sort_key(row: dict[str, Any]) -> tuple[float, int, str]:
    return (-row["score_r"], 0 if row["node_kind"] == "base" else 1, row["fqdn"])


def _aggregate_subtree_scores(rows: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    base_scores: dict[str, float] = {}
    l1_scores: dict[str, float] = defaultdict(float)
    l2_scores: dict[str, float] = defaultdict(float)
    for row in rows:
        l1_scores[row["l1"]] = max(l1_scores[row["l1"]], row["score_r"])
        if row.get("l2"):
            l2_key = f"{row['l2']}.{row['l1']}.cn"
            l2_scores[l2_key] = max(l2_scores[l2_key], row["score_r"])
        if row["node_kind"] == "base":
            base_scores[row["fqdn"]] = row["score_r"]
    return base_scores, dict(l1_scores), dict(l2_scores)


def _rerank_with_hierarchy(
    rows: list[dict[str, Any]],
    config: StageRCleanConfig,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    base_scores, l1_scores, l2_scores = _aggregate_subtree_scores(rows)
    child_max: dict[str, float] = defaultdict(float)
    for row in rows:
        if row["node_kind"] == "segment" and row.get("parent_fqdn"):
            child_max[row["parent_fqdn"]] = max(child_max[row["parent_fqdn"]], row["score_r"])

    reranked: list[dict[str, Any]] = []
    for row in rows:
        local_score = row["score_r"]
        updated = dict(row)
        components = dict(row.get("components", {}))
        hierarchy_bonus = 0.0
        context_only_penalty = 0.0
        weak_parent_penalty = 0.0

        if row["node_kind"] == "base":
            child_support = max(child_max.get(row["fqdn"], 0.0) - local_score, 0.0)
            hierarchy_bonus = min(child_support, config.base_child_support_cap) * config.base_child_support_weight
            components["child_support"] = round(child_support, 6)
        else:
            parent_score = base_scores.get(row.get("parent_fqdn"), 0.0)
            query_alias_score = components.get("query_alias_score", 0.0)
            context_alias_score = components.get("context_alias_score", 0.0)
            hierarchy_bonus = min(parent_score, config.segment_parent_bonus_cap) * config.segment_parent_bonus_weight
            if query_alias_score == 0.0 and context_alias_score > 0.0:
                context_only_penalty = config.segment_context_only_penalty
            if parent_score < config.segment_weak_parent_threshold:
                weak_parent_penalty = config.segment_weak_parent_penalty
            components["parent_score"] = round(parent_score, 6)

        final_score = max(local_score + hierarchy_bonus - context_only_penalty - weak_parent_penalty, 0.0)
        components["hierarchy_bonus"] = round(hierarchy_bonus, 6)
        components["context_only_penalty"] = round(context_only_penalty, 6)
        components["weak_parent_penalty"] = round(weak_parent_penalty, 6)
        updated["score_r"] = round(final_score, 6)
        updated["components"] = components
        if hierarchy_bonus > 0.0 and "hierarchy_rerank" not in updated["source"]:
            updated["source"] = list(updated["source"]) + ["hierarchy_rerank"]
        reranked.append(updated)

    reranked = sorted(reranked, key=_rank_sort_key)
    subtree_scores = {
        "l1": dict(sorted(l1_scores.items(), key=lambda item: (-item[1], item[0]))),
        "l2": dict(sorted(l2_scores.items(), key=lambda item: (-item[1], item[0]))),
    }
    return reranked, subtree_scores


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
    return _dedupe_candidates(sorted(augmented, key=_rank_sort_key))


def _select_candidates(
    ranked: list[dict[str, Any]],
    top_k: int,
    selection_signals: dict[str, Any],
    config: StageRCleanConfig,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    segment_by_parent: Counter[str] = Counter()
    seen_l1: set[str] = set()
    multi_intent = selection_signals.get("has_multi_intent_signal", False)
    head_budget = min(top_k, config.multi_intent_head_budget if multi_intent else config.default_head_budget)

    def can_take(row: dict[str, Any], *, strict_parent_limit: bool) -> bool:
        if row["fqdn"] in seen:
            return False
        if row["node_kind"] == "segment" and row.get("parent_fqdn"):
            limit = config.strict_parent_segment_limit if strict_parent_limit else config.relaxed_parent_segment_limit
            if segment_by_parent[row["parent_fqdn"]] >= limit:
                return False
        return True

    def take(row: dict[str, Any]) -> None:
        selected.append(row)
        seen.add(row["fqdn"])
        seen_l1.add(row["l1"])
        if row["node_kind"] == "segment" and row.get("parent_fqdn"):
            segment_by_parent[row["parent_fqdn"]] += 1

    for row in ranked:
        if len(selected) >= head_budget:
            break
        if can_take(row, strict_parent_limit=True):
            take(row)

    if multi_intent and config.enable_diversified_selection:
        for row in ranked:
            if len(selected) >= top_k:
                break
            if row["l1"] in seen_l1:
                continue
            if can_take(row, strict_parent_limit=False):
                take(row)

    for row in ranked:
        if len(selected) >= top_k:
            break
        if can_take(row, strict_parent_limit=False):
            take(row)

    return selected


def _fallback_ranked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -row["components"].get("query_alias_score", 0.0),
            -row["components"].get("raw_desc_similarity", 0.0),
            -row["components"].get("context_score", 0.0),
            row["node_kind"] != "base",
            row["fqdn"],
        ),
    )


def _selection_signals(
    ranked: list[dict[str, Any]],
    config: StageRCleanConfig,
) -> dict[str, Any]:
    if not ranked:
        return {
            "has_multi_intent_signal": False,
            "has_cross_domain_competition": False,
            "has_sibling_competition": False,
            "head_score_delta": None,
        }

    head = ranked[: config.signal_window]
    top_score = head[0]["score_r"]
    competitive = [row for row in head if row["score_r"] >= top_score - config.close_score_delta]
    competitive_domains = {row["l1"] for row in competitive}
    parent_counter: Counter[str] = Counter()
    for row in competitive:
        parent_key = row.get("parent_fqdn") or row["fqdn"]
        parent_counter[parent_key] += 1

    return {
        "has_multi_intent_signal": len(competitive_domains) >= 2,
        "has_cross_domain_competition": len(competitive_domains) >= 2,
        "has_sibling_competition": any(count >= 2 for count in parent_counter.values()),
        "head_score_delta": round(top_score - head[1]["score_r"], 6) if len(head) >= 2 else None,
    }


def _confusion_sources(candidates: list[dict[str, Any]], selection_signals: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    if selection_signals.get("has_multi_intent_signal"):
        sources.append("C1_multi_intent")
    if selection_signals.get("has_cross_domain_competition"):
        sources.append("C5_cross_domain_overlap")
    if selection_signals.get("has_sibling_competition"):
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
    config: StageRCleanConfig | None = None,
) -> dict[str, Any]:
    config = config or StageRCleanConfig()
    query = sample["query"]
    context = sample.get("context") or {}
    scored = [score_node(node, query, context, config) for node in resolver.iter_nodes()]
    ranked_all = sorted(scored, key=lambda x: (-x["score_r"], x["fqdn"]))
    ranked = [row for row in ranked_all if row["score_r"] > 0]
    if config.enable_hierarchy_rerank:
        ranked, subtree_scores = _rerank_with_hierarchy(ranked, config)
    else:
        _, l1_scores, l2_scores = _aggregate_subtree_scores(ranked)
        subtree_scores = {
            "l1": dict(sorted(l1_scores.items(), key=lambda item: (-item[1], item[0]))),
            "l2": dict(sorted(l2_scores.items(), key=lambda item: (-item[1], item[0]))),
        }
    if config.enable_parent_fallback:
        ranked = _add_parent_fallbacks(resolver, ranked)
    selection_signals = _selection_signals(ranked, config)
    candidates = _select_candidates(ranked, top_k=top_k, selection_signals=selection_signals, config=config)
    if len(candidates) < top_k and config.enable_low_signal_fallback:
        fallback_rows = _fallback_ranked_rows(ranked_all)
        existing = {row["fqdn"] for row in candidates}
        for row in fallback_rows:
            if row["fqdn"] in existing:
                continue
            candidates.append(row)
            existing.add(row["fqdn"])
            if len(candidates) >= top_k:
                break

    semantic_parse = {
        "selection_signals": selection_signals,
        "context_features": context,
        "matched_candidate_fqdns": [row["fqdn"] for row in candidates[:8]],
    }
    recall_sources = sorted({source for row in candidates for source in row.get("source", [])})

    snapshot: dict[str, Any] = {
        "id": sample["id"],
        "namespace_version": sample["namespace_version"],
        "stage_r_version": stage_r_version,
        "semantic_parse": semantic_parse,
        "descriptor_scores": ranked[: min(20, len(ranked))],
        "subtree_scores": subtree_scores,
        "recall_sources": recall_sources,
        "fqdn_candidates": candidates,
        "confusion_sources": _confusion_sources(candidates, selection_signals),
        "candidate_generation_rules": [
            "descriptor_only_recall",
            "no_examples_in_index",
            "no_bootstrap_lexicon",
            "query_context_separated_scoring",
            "generic_metadata_facet_alignment",
            "hierarchy_rerank" if config.enable_hierarchy_rerank else "hierarchy_rerank_disabled",
            "structure_signal_diversified_selection" if config.enable_diversified_selection else "rank_only_selection",
            "parent_fallback_for_segment_nodes" if config.enable_parent_fallback else "parent_fallback_disabled",
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
