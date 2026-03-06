from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .namespace import NamespaceResolver, validate_fqdn


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


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


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _unique_phrases(values: list[str]) -> list[str]:
    cleaned = [value.strip().lower() for value in values if isinstance(value, str) and value.strip()]
    return _dedupe_keep_order(cleaned)


def _match_spec_list(text: str, specs: list[dict[str, Any]], field_name: str) -> tuple[list[str], list[dict[str, str]]]:
    labels: list[str] = []
    spans: list[dict[str, str]] = []
    for spec in specs:
        label = spec["label"]
        for phrase in spec.get("phrases", []):
            if phrase and phrase.lower() in text:
                labels.append(label)
                spans.append({"field": field_name, "label": label, "phrase": phrase})
    return _dedupe_keep_order(labels), spans


def _match_first_label(text: str, specs: list[dict[str, Any]], field_name: str) -> tuple[str | None, list[dict[str, str]]]:
    earliest_label: str | None = None
    earliest_index: int | None = None
    spans: list[dict[str, str]] = []
    for spec in specs:
        label = spec["label"]
        for phrase in spec.get("phrases", []):
            if not phrase:
                continue
            index = text.find(phrase.lower())
            if index >= 0:
                spans.append({"field": field_name, "label": label, "phrase": phrase})
                if earliest_index is None or index < earliest_index:
                    earliest_index = index
                    earliest_label = label
    return earliest_label, spans


def parse_semantic_evidence(
    query: str,
    context: dict[str, Any] | None,
    lexicon: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    text = query.lower()
    if context:
        context_text = json.dumps(context, ensure_ascii=False).lower()
        text = f"{text}\n{context_text}"

    evidence_spans: list[dict[str, str]] = []
    parsed: dict[str, Any] = {}
    for field_name in (
        "primary_action",
        "target_object",
        "industry_context",
    ):
        label, spans = _match_first_label(text, lexicon.get(field_name, []), field_name)
        evidence_spans.extend(spans)
        parsed[field_name] = label

    for field_name in (
        "domain_hints",
        "capability_hints",
        "segment_hints",
        "secondary_intents",
        "risk_flags",
    ):
        labels, spans = _match_spec_list(text, lexicon.get(field_name, []), field_name)
        evidence_spans.extend(spans)
        parsed[field_name] = labels

    parsed["evidence_spans"] = evidence_spans
    parsed["query_markers"] = {
        "has_multi_intent_marker": any(marker in text for marker in ("并", "同时", "顺便", "顺手", "以及", "并且", "再看", "再看看")),
        "has_question_marker": any(marker in text for marker in ("哪些", "需要", "怎么", "如何", "帮我")),
    }
    return parsed


def _descriptor_surface_phrases(descriptor: dict[str, Any]) -> list[str]:
    phrases: list[str] = []
    phrases.extend(descriptor.get("aliases", []))
    phrases.extend(descriptor.get("examples", []))
    phrases.extend(descriptor.get("industry_tags", []))
    phrases.extend(descriptor.get("risk_tags", []))
    phrases.extend(descriptor.get("action_tags", []))
    phrases.extend(descriptor.get("object_tags", []))
    desc = descriptor.get("desc")
    if desc:
        phrases.append(desc)
    return _unique_phrases(phrases)


def _ratio(num: float, denom: float) -> float:
    return num / denom if denom else 0.0


def _count_phrase_hits(text: str, phrases: list[str]) -> tuple[int, list[str]]:
    hits: list[str] = []
    for phrase in phrases:
        if phrase and phrase in text:
            hits.append(phrase)
    return len(hits), hits


def _safe_sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def score_descriptor(
    query: str,
    semantic_parse: dict[str, Any],
    descriptor: dict[str, Any],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    weights = weights or {
        "lex": 0.28,
        "slot": 0.27,
        "meta": 0.20,
        "risk": 0.10,
        "industry": 0.10,
        "dense": 0.00,
        "over": 0.05,
    }
    text = query.lower()

    surface = _descriptor_surface_phrases(descriptor)
    hit_count, hit_phrases = _count_phrase_hits(text, surface)
    lexical_match = _ratio(hit_count, max(4, len(surface)))

    slot_terms = 0.0
    slot_hits: list[str] = []
    if descriptor["l1"] in semantic_parse.get("domain_hints", []):
        slot_terms += 1.0
        slot_hits.append(f"domain:{descriptor['l1']}")
    if descriptor.get("l2") and descriptor["l2"] in semantic_parse.get("capability_hints", []):
        slot_terms += 1.2
        slot_hits.append(f"capability:{descriptor['l2']}")
    primary_action = semantic_parse.get("primary_action")
    if primary_action and primary_action in descriptor.get("action_tags", []):
        slot_terms += 1.0
        slot_hits.append(f"action:{primary_action}")
    target_object = semantic_parse.get("target_object")
    if target_object and target_object in descriptor.get("object_tags", []):
        slot_terms += 1.2
        slot_hits.append(f"object:{target_object}")
    slot_match = min(slot_terms / 4.4, 1.0)

    meta_terms = 0.0
    meta_hits: list[str] = []
    for phrase in descriptor.get("aliases", []):
        if phrase.lower() in text:
            meta_terms += 1.0
            meta_hits.append(f"alias:{phrase}")
    for phrase in descriptor.get("examples", []):
        if phrase.lower() in text:
            meta_terms += 0.7
            meta_hits.append(f"example:{phrase}")
    for phrase in descriptor.get("industry_tags", []):
        if phrase.lower() in text:
            meta_terms += 0.6
            meta_hits.append(f"industry_tag:{phrase}")
    metadata_match = min(meta_terms / 3.0, 1.0)

    risk_terms = 0.0
    risk_hits: list[str] = []
    risk_flags = semantic_parse.get("risk_flags", [])
    for risk_flag in risk_flags:
        if risk_flag in descriptor.get("risk_tags", []):
            risk_terms += 1.0
            risk_hits.append(risk_flag)
    if risk_flags and descriptor["l1"] in {"security", "gov"}:
        risk_terms += 0.5
        risk_hits.append(f"domain:{descriptor['l1']}")
    risk_alignment = min(risk_terms / 2.0, 1.0)

    industry_fit = 0.0
    industry_label = semantic_parse.get("industry_context")
    if industry_label and industry_label in descriptor.get("industry_tags", []):
        industry_fit = 1.0
    elif industry_label and descriptor["l1"] in {"gov", "security", "finance", "productivity"} and industry_label == "enterprise_service":
        industry_fit = 0.6

    overspecific_penalty = 0.0
    if descriptor.get("segments") and not semantic_parse.get("segment_hints"):
        overspecific_penalty = 0.0

    score = (
        weights["lex"] * lexical_match
        + weights["slot"] * slot_match
        + weights["meta"] * metadata_match
        + weights["risk"] * risk_alignment
        + weights["industry"] * industry_fit
        + weights["dense"] * 0.0
        - weights["over"] * overspecific_penalty
    )

    return {
        "fqdn": descriptor["fqdn"],
        "l1": descriptor["l1"],
        "l2": descriptor.get("l2"),
        "score_r": round(max(score, 0.0), 6),
        "components": {
            "lexical_match": round(lexical_match, 6),
            "slot_match": round(slot_match, 6),
            "metadata_match": round(metadata_match, 6),
            "risk_alignment": round(risk_alignment, 6),
            "industry_fit": round(industry_fit, 6),
            "overspecific_penalty": round(overspecific_penalty, 6),
        },
        "matched_phrases": {
            "lexical": hit_phrases,
            "slot": slot_hits,
            "meta": meta_hits,
            "risk": risk_hits,
        },
    }


def _score_segment_candidate(
    query: str,
    semantic_parse: dict[str, Any],
    descriptor: dict[str, Any],
    base_score: float,
    resolver: NamespaceResolver,
) -> list[dict[str, Any]]:
    text = query.lower()
    candidates: list[dict[str, Any]] = []
    segment_hints = set(semantic_parse.get("segment_hints", []))
    for segment, meta in descriptor.get("segments", {}).items():
        aliases = [value.lower() for value in meta.get("aliases", [])]
        hit_count, hit_phrases = _count_phrase_hits(text, aliases)
        matched_by_hint = segment in segment_hints
        if hit_count == 0 and not matched_by_hint:
            continue

        specificity_boost = 0.10 + min(hit_count, 2) * 0.05 + (0.05 if matched_by_hint else 0.0)
        fqdn = resolver.canonicalize_segment(descriptor["fqdn"], segment)
        node = resolver.get_node(fqdn)
        candidates.append(
            {
                "fqdn": fqdn,
                "score_r": round(base_score + specificity_boost, 6),
                "node_kind": node.node_kind if node else "segment",
                "l1": node.l1 if node else descriptor["l1"],
                "l2": node.l2 if node else descriptor.get("l2"),
                "segment": node.segment if node else segment,
                "parent_fqdn": node.parent_fqdn if node else descriptor["fqdn"],
                "fallback_to": node.fallback_to if node else descriptor["fqdn"],
                "components": {
                    "segment_match": round(_safe_sigmoid(hit_count + (1 if matched_by_hint else 0)) - 0.5, 6),
                    "specificity_boost": round(specificity_boost, 6),
                },
                "matched_phrases": {
                    "segment": hit_phrases,
                },
                "source": ["segment_expand"],
            }
        )
    return candidates


def _derive_confusion_sources(semantic_parse: dict[str, Any], fqdn_candidates: list[dict[str, Any]]) -> list[str]:
    confusion: list[str] = []
    if semantic_parse.get("secondary_intents") or semantic_parse.get("query_markers", {}).get("has_multi_intent_marker"):
        confusion.append("C1_multi_intent")

    domains = [candidate["fqdn"].split(".")[-2] if candidate["fqdn"].count(".") >= 2 else candidate["fqdn"].split(".")[0] for candidate in fqdn_candidates[:5]]
    if len(set(domains)) > 1:
        confusion.append("C5_cross_domain_overlap")

    family_counts: defaultdict[str, int] = defaultdict(int)
    for candidate in fqdn_candidates[:8]:
        parts = candidate["fqdn"].split(".")
        family = ".".join(parts[-3:]) if len(parts) >= 4 else ".".join(parts[-2:]) if len(parts) >= 3 else candidate["fqdn"]
        family_counts[family] += 1
    if any(count >= 2 for count in family_counts.values()):
        confusion.append("C3_sibling_competition")

    if semantic_parse.get("risk_flags") and any(
        candidate["fqdn"].endswith("security.cn") or candidate["fqdn"].endswith("gov.cn") for candidate in fqdn_candidates[:5]
    ):
        confusion.append("C4_governance_fallback")

    if any("lexical" in candidate.get("source", []) for candidate in fqdn_candidates[:5]):
        confusion.append("C2_lexical_overlap")

    return _dedupe_keep_order(confusion)


def build_candidate_snapshot(
    sample: dict[str, Any],
    descriptors: list[dict[str, Any]],
    lexicon: dict[str, Any],
    top_k: int = 10,
    stage_r_version: str = "sr_v0_20260306",
) -> dict[str, Any]:
    query = sample["query"]
    semantic_parse = parse_semantic_evidence(query, sample.get("context"), lexicon)
    resolver = NamespaceResolver(descriptors)

    scored_descriptors = [score_descriptor(query, semantic_parse, descriptor) for descriptor in descriptors]
    descriptor_by_fqdn = {descriptor["fqdn"]: descriptor for descriptor in descriptors}

    expanded_candidates: list[dict[str, Any]] = []
    for scored in scored_descriptors:
        descriptor = descriptor_by_fqdn[scored["fqdn"]]
        sources = []
        if scored["components"]["lexical_match"] > 0:
            sources.append("lexical")
        if scored["components"]["slot_match"] > 0:
            sources.append("slot")
        if scored["components"]["metadata_match"] > 0:
            sources.append("metadata")
        if scored["components"]["risk_alignment"] > 0:
            sources.append("risk")
        if scored["components"]["industry_fit"] > 0:
            sources.append("industry")

        expanded_candidates.append(
            {
                "fqdn": scored["fqdn"],
                "score_r": scored["score_r"],
                "node_kind": "base",
                "l1": descriptor["l1"],
                "l2": descriptor.get("l2"),
                "segment": None,
                "parent_fqdn": None,
                "fallback_to": descriptor.get("fallback_to"),
                "source": sources or ["baseline"],
            }
        )
        expanded_candidates.extend(
            _score_segment_candidate(
                query=query,
                semantic_parse=semantic_parse,
                descriptor=descriptor,
                base_score=scored["score_r"],
                resolver=resolver,
            )
        )

    # Prefer candidates with real evidence and keep deterministic ordering.
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in sorted(expanded_candidates, key=lambda item: (-item["score_r"], item["fqdn"])):
        if candidate["fqdn"] not in deduped:
            deduped[candidate["fqdn"]] = candidate

    fqdn_candidates = list(deduped.values())[:top_k]
    confusion_sources = _derive_confusion_sources(semantic_parse, fqdn_candidates)

    l1_scores: dict[str, float] = defaultdict(float)
    l2_scores: dict[str, float] = defaultdict(float)
    for scored in scored_descriptors:
        l1_scores[scored["l1"]] = max(l1_scores[scored["l1"]], scored["score_r"])
        if scored.get("l2"):
            l2_key = f"{scored['l2']}.{scored['l1']}.cn"
            l2_scores[l2_key] = max(l2_scores[l2_key], scored["score_r"])

    return {
        "id": sample["id"],
        "namespace_version": sample["namespace_version"],
        "stage_r_version": stage_r_version,
        "semantic_parse": semantic_parse,
        "descriptor_scores": sorted(
            [
                {
                    "fqdn": scored["fqdn"],
                    "score_r": scored["score_r"],
                    "components": scored["components"],
                }
                for scored in scored_descriptors
            ],
            key=lambda item: (-item["score_r"], item["fqdn"]),
        )[:12],
        "subtree_scores": {
            "l1": dict(sorted(l1_scores.items(), key=lambda item: (-item[1], item[0]))),
            "l2": dict(sorted(l2_scores.items(), key=lambda item: (-item[1], item[0]))),
        },
        "fqdn_candidates": fqdn_candidates,
        "confusion_sources": confusion_sources,
        "candidate_generation_rules": [
            "namespace_descriptor_recall",
            "l3_segment_expand_when_evidence_exists",
            "query_induced_confusion_only",
        ],
        "candidate_recall_hit": {
            "primary_in_top_k": sample["ground_truth_fqdn"] in {candidate["fqdn"] for candidate in fqdn_candidates},
            "related_hits": [
                fqdn for fqdn in sample.get("relevant_fqdns", []) if fqdn in {candidate["fqdn"] for candidate in fqdn_candidates}
            ],
        },
    }
