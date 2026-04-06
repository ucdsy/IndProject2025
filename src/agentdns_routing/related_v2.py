from __future__ import annotations

import copy
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import OpenAI

from .namespace import NamespaceResolver, RoutingNode, validate_fqdn
from .stage_r_clean import StageRCleanConfig, score_node

PUNCT_RE = re.compile(r"[，。！？；：、“”‘’（）()【】《》,.!?:;\"'`\-\[\]{}_/\\\s]+")
CLAUSE_RE = re.compile(r"[。！？!?；;]")
QUOTE_RE = re.compile(r"[“\"「『](.*?)[”\"」』]")
COMMA_SPLIT_RE = re.compile(r"[，,、]")
SECONDARY_CUE_WORDS = ("顺手", "顺便", "另外", "同时", "也", "还", "再", "以及", "并且", "外加")


@dataclass(frozen=True)
class RelatedV2Config:
    related_version: str = "related_v2_20260401"
    candidate_pool_limit: int = 12
    llm_candidate_limit: int = 8
    stage_r_seed_limit: int = 10
    query_theme_seed_limit: int = 6
    max_related: int = 3
    min_candidate_score: float = 0.16
    select_min_score: float = 0.28
    cross_l1_select_min_score: float = 0.42
    prior_rescue_min_score: float = 0.22
    same_l1_bonus: float = 0.08
    same_l2_bonus: float = 0.04
    stage_r_seed_bonus: float = 0.06
    primary_neighbor_bonus: float = 0.06
    query_theme_seed_bonus: float = 0.08
    stage_a_related_prior_bonus: float = 0.14
    stage_b_related_prior_bonus: float = 0.18
    explicit_secondary_bonus: float = 0.12
    llm_secondary_bonus: float = 0.10
    cross_l1_penalty: float = 0.08
    high_risk_penalty: float = 0.12
    primary_competitor_penalty: float = 0.16
    review_confidence_threshold: float = 0.55
    review_gap_threshold: float = 0.05
    review_add_min_score: float = 0.36
    review_cross_l1_add_min_score: float = 0.48
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1200
    llm_related_min_confidence: float = 0.32
    llm_relaxed_cross_l1_min_score: float = 0.28
    llm_relaxed_primary_neighbor_min_score: float = 0.22
    stage_r_config: StageRCleanConfig = field(default_factory=StageRCleanConfig)


class RelatedV2LLMClient(Protocol):
    provider: str
    model: str

    def adjudicate_related(self, packet: dict[str, Any], config: RelatedV2Config) -> tuple[dict[str, Any], str]:
        raise NotImplementedError


class OpenAICompatibleRelatedV2LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1)

    def adjudicate_related(self, packet: dict[str, Any], config: RelatedV2Config) -> tuple[dict[str, Any], str]:
        messages = [
            {"role": "system", "content": _related_llm_system_prompt()},
            {"role": "user", "content": _related_llm_user_prompt(packet)},
        ]
        request_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": config.llm_temperature,
            "max_tokens": config.llm_max_tokens,
        }
        try:
            response = self._client.chat.completions.create(
                **request_kwargs,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            if not _should_retry_without_json_mode(exc):
                raise
            response = self._client.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content or ""
        decision = _load_json_object(content)
        return decision, content


def make_related_llm_client(provider: str, model: str | None = None) -> RelatedV2LLMClient:
    provider = provider.lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set")
        return OpenAICompatibleRelatedV2LLMClient(
            provider="deepseek",
            model=model or "deepseek-chat",
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=60.0,
        )
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set")
        return OpenAICompatibleRelatedV2LLMClient(
            provider="openai",
            model=model or "gpt-5.4",
            api_key=api_key,
            timeout=60.0,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalize_text(value: str) -> str:
    return PUNCT_RE.sub("", (value or "").lower())


def _dedupe_texts(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip("，。；; ")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty related_v2 LLM response")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _should_retry_without_json_mode(exc: Exception) -> bool:
    message = str(exc).lower()
    return isinstance(exc, TypeError) or any(
        token in message
        for token in (
            "response_format",
            "json_object",
            "unexpected keyword",
            "unknown parameter",
            "not supported",
            "unsupported",
            "extra inputs are not permitted",
        )
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return _clip(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_short_text(value: Any, limit: int = 220) -> str:
    text = str(value or "").strip()
    return text[:limit] if text else ""


def _coerce_short_label_list(value: Any, limit: int = 6) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        normalized = text.replace(" ", "_")[:64]
        if normalized not in labels:
            labels.append(normalized)
        if len(labels) >= limit:
            break
    return labels


def _build_query_packet(query: str) -> dict[str, Any]:
    text = (query or "").strip()
    clauses = [part.strip("，。；; ") for part in CLAUSE_RE.split(text) if part.strip("，。；; ")]
    quoted_segments = _dedupe_texts([match.strip() for match in QUOTE_RE.findall(text) if match.strip()])

    scene_parts: list[str] = []
    if len(clauses) >= 2:
        scene_parts.append(clauses[0])
    if quoted_segments:
        scene_parts.append(quoted_segments[0])
    scene_text = " ".join(_dedupe_texts(scene_parts)).strip()

    if len(clauses) >= 2:
        primary_request_text = clauses[1]
    elif clauses:
        primary_request_text = clauses[0]
    else:
        primary_request_text = text

    supplemental_parts = _dedupe_texts(clauses[2:] + quoted_segments[1:])
    return {
        "full_text": text,
        "scene_text": scene_text,
        "primary_request_text": primary_request_text,
        "supplemental_texts": supplemental_parts,
        "clauses": clauses,
        "quoted_segments": quoted_segments,
        "has_structural_multi_intent": len(clauses) >= 3 or len(quoted_segments) >= 2,
    }


def _chain_members(fqdn: str, resolver: NamespaceResolver) -> set[str]:
    members = {fqdn}
    members.update(resolver.fallback_chain(fqdn))
    node = resolver.get_node(fqdn)
    if node and node.parent_fqdn:
        members.add(node.parent_fqdn)
    return members


def _is_chain_duplicate(primary_fqdn: str, other_fqdn: str, resolver: NamespaceResolver) -> bool:
    if primary_fqdn == other_fqdn:
        return True
    return other_fqdn in _chain_members(primary_fqdn, resolver) or primary_fqdn in _chain_members(other_fqdn, resolver)


def _context_to_text(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    return " ".join(str(value) for value in context.values() if value is not None)


def _node_text(node: RoutingNode | None) -> str:
    if not node:
        return ""
    parts = [node.fqdn, node.l1, node.l2 or "", node.segment or "", node.desc, *node.aliases]
    return " ".join([part for part in parts if part])


def _llm_secondary_intents(trace: dict[str, Any]) -> list[str]:
    stage_a = trace.get("stage_a", {})
    llm_decision = stage_a.get("llm_decision", {})
    raw = llm_decision.get("secondary_intents", [])
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _secondary_intents_from_query_packet(query_packet: dict[str, Any]) -> list[str]:
    primary_text = str(query_packet.get("primary_request_text", "")).strip()
    primary_norm = _normalize_text(primary_text)
    candidates: list[str] = []

    candidates.extend(str(item).strip() for item in query_packet.get("supplemental_texts", []) if str(item).strip())

    full_text = str(query_packet.get("full_text", "")).strip()
    comma_parts = [part.strip("，,、。；; ") for part in COMMA_SPLIT_RE.split(full_text) if part.strip("，,、。；; ")]
    if len(comma_parts) >= 2:
        candidates.extend(comma_parts[1:])

    for cue in SECONDARY_CUE_WORDS:
        if cue not in full_text:
            continue
        suffix = full_text.split(cue, 1)[1].strip("：:，,、。；; ")
        if suffix:
            candidates.append(suffix)

    cleaned: list[str] = []
    for item in _dedupe_texts(candidates):
        norm = _normalize_text(item)
        if not norm:
            continue
        if primary_norm and norm == primary_norm:
            continue
        cleaned.append(item)
    return cleaned[:5]


def _secondary_intent_bundle(sample: dict[str, Any], trace: dict[str, Any], primary_fqdn: str, resolver: NamespaceResolver) -> dict[str, Any]:
    stage_a = trace.get("stage_a", {})
    query_packet = copy.deepcopy(stage_a.get("query_packet") or _build_query_packet(sample.get("query", "")))
    llm_secondary = _llm_secondary_intents(trace)
    query_secondary = _secondary_intents_from_query_packet(query_packet)
    secondary_texts = _dedupe_texts(query_secondary + llm_secondary)

    primary_node = resolver.get_node(primary_fqdn)
    stage_a_selected_related = list(stage_a.get("selected_related_fqdns", []))
    stage_b_selected_related = list((trace.get("stage_b") or {}).get("selected_related_fqdns", []))

    return {
        "query_packet": query_packet,
        "secondary_intents": secondary_texts,
        "primary_secondary_split": {
            "primary_request_text": query_packet.get("primary_request_text", ""),
            "secondary_texts": secondary_texts,
            "scene_text": query_packet.get("scene_text", ""),
        },
        "has_multi_intent_signal": bool(
            query_packet.get("has_structural_multi_intent")
            or secondary_texts
            or stage_a_selected_related
            or stage_b_selected_related
        ),
        "stage_a_related_prior": stage_a_selected_related,
        "stage_b_related_prior": stage_b_selected_related,
        "primary_node_text": _node_text(primary_node),
    }


def _stage_a_semantic_handoff(trace: dict[str, Any]) -> dict[str, Any]:
    stage_a = trace.get("stage_a", {})
    llm_decision = stage_a.get("llm_decision", {})
    return {
        "scene_context": llm_decision.get("scene_context", ""),
        "primary_intent": llm_decision.get("primary_intent", ""),
        "secondary_intents": list(llm_decision.get("secondary_intents", [])),
        "primary_rationale": llm_decision.get("primary_rationale", ""),
        "secondary_rationale": llm_decision.get("secondary_rationale", ""),
        "uncertainty_summary": llm_decision.get("uncertainty_summary", ""),
        "confusion_points": list(llm_decision.get("confusion_points", [])),
        "challenger_notes": list(llm_decision.get("challenger_notes", [])),
    }


def _best_secondary_match(
    node: RoutingNode,
    secondary_intents: list[str],
    context: dict[str, Any] | None,
    config: RelatedV2Config,
) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    if not secondary_intents:
        return {
            "intent_text": "",
            "score_r": 0.0,
            "matched_aliases": [],
            "components": {},
        }
    for intent in secondary_intents:
        row = score_node(node=node, query=intent, context=context, config=config.stage_r_config)
        row["intent_text"] = intent
        matched_aliases = list(row.get("matched_phrases", {}).get("aliases", []))
        row["matched_aliases"] = matched_aliases
        if best is None or row["score_r"] > best["score_r"]:
            best = row
    return best or {
        "intent_text": "",
        "score_r": 0.0,
        "matched_aliases": [],
        "components": {},
    }


def _primary_competitor_gap(trace: dict[str, Any], fqdn: str, primary_fqdn: str) -> float | None:
    candidate_scores = trace.get("stage_a", {}).get("candidate_scores", [])
    if not candidate_scores:
        return None
    scores = {row["fqdn"]: float(row.get("score_a", 0.0)) for row in candidate_scores}
    if fqdn not in scores or primary_fqdn not in scores:
        return None
    return round(scores[primary_fqdn] - scores[fqdn], 6)


def _stage_r_seed_rows(trace: dict[str, Any], config: RelatedV2Config) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for rank, row in enumerate(trace.get("stage_r", {}).get("fqdn_candidates", [])[: config.stage_r_seed_limit], start=1):
        fqdn = str(row.get("fqdn", "")).strip()
        if fqdn and fqdn not in rows:
            rows[fqdn] = {"rank": rank, **row}
    return rows


def _primary_neighbor_seed_fqdns(primary_fqdn: str, resolver: NamespaceResolver) -> set[str]:
    node = resolver.get_node(primary_fqdn)
    if not node:
        return set()

    base_fqdn = node.parent_fqdn or node.fqdn
    seeds: set[str] = set()
    seeds.update(resolver.segments_for_base(base_fqdn))

    for other in resolver.iter_nodes():
        if other.fqdn == primary_fqdn:
            continue
        if other.node_kind == "base" and other.l1 == node.l1:
            seeds.add(other.fqdn)

    return seeds


def _query_theme_seed_fqdns(
    sample: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str,
    bundle: dict[str, Any],
    config: RelatedV2Config,
) -> set[str]:
    if not bundle.get("secondary_intents"):
        return set()

    ranked: list[tuple[float, int, str]] = []
    for node in resolver.iter_nodes():
        if _is_chain_duplicate(primary_fqdn, node.fqdn, resolver):
            continue
        best = _best_secondary_match(
            node=node,
            secondary_intents=bundle["secondary_intents"],
            context=sample.get("context"),
            config=config,
        )
        score = float(best.get("score_r", 0.0))
        explicit_hits = bool(best.get("matched_aliases"))
        if not explicit_hits and score < config.min_candidate_score:
            continue
        ranked.append((score, 1 if explicit_hits else 0, node.fqdn))

    ranked.sort(reverse=True)
    return {fqdn for _, _, fqdn in ranked[: config.query_theme_seed_limit]}


def _candidate_record(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str,
    node: RoutingNode,
    bundle: dict[str, Any],
    config: RelatedV2Config,
    builder_sources: set[str] | None = None,
    stage_r_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    builder_sources = builder_sources or set()
    best = _best_secondary_match(node=node, secondary_intents=bundle["secondary_intents"], context=sample.get("context"), config=config)
    primary_node = resolver.get_node(primary_fqdn)
    same_l1 = bool(primary_node and node.l1 == primary_node.l1)
    same_l2 = bool(primary_node and node.l2 and primary_node.l2 and node.l2 == primary_node.l2)
    cross_l1 = bool(primary_node and node.l1 != primary_node.l1)
    stage_a_prior = node.fqdn in set(bundle["stage_a_related_prior"])
    stage_b_prior = node.fqdn in set(bundle["stage_b_related_prior"])
    explicit_secondary_hits = bool(best.get("matched_aliases"))
    primary_gap = _primary_competitor_gap(trace, node.fqdn, primary_fqdn)
    likely_primary_challenger = primary_gap is not None and primary_gap <= 0.08
    stage_r_present = "stage_r" in builder_sources
    is_primary_neighbor = "primary_neighbor" in builder_sources
    is_query_theme_seed = "query_theme_seed" in builder_sources

    score = (
        0.62 * float(best.get("score_r", 0.0))
        + (config.same_l1_bonus if same_l1 and not same_l2 else 0.0)
        + (config.same_l2_bonus if same_l2 else 0.0)
        + (config.stage_r_seed_bonus if stage_r_present else 0.0)
        + (config.primary_neighbor_bonus if is_primary_neighbor else 0.0)
        + (config.query_theme_seed_bonus if is_query_theme_seed else 0.0)
        + (config.stage_a_related_prior_bonus if stage_a_prior else 0.0)
        + (config.stage_b_related_prior_bonus if stage_b_prior else 0.0)
        + (config.explicit_secondary_bonus if explicit_secondary_hits else 0.0)
        + (config.llm_secondary_bonus if bundle["secondary_intents"] and best.get("intent_text") in bundle["secondary_intents"] else 0.0)
        - (config.cross_l1_penalty if cross_l1 else 0.0)
        - (config.high_risk_penalty if node.is_stage_a_high_risk and not explicit_secondary_hits else 0.0)
        - (config.primary_competitor_penalty if likely_primary_challenger and not (stage_a_prior or stage_b_prior) else 0.0)
    )

    cross_domain_secondary_ok = bool(
        cross_l1
        and not node.is_stage_a_high_risk
        and (explicit_secondary_hits or stage_a_prior or stage_b_prior or is_query_theme_seed)
        and (
            float(best.get("score_r", 0.0)) >= config.cross_l1_select_min_score
            or stage_a_prior
            or stage_b_prior
        )
    )

    return {
        "fqdn": node.fqdn,
        "score_related_v2": round(_clip(score), 6),
        "best_intent_text": best.get("intent_text", ""),
        "best_secondary_score": round(float(best.get("score_r", 0.0)), 6),
        "matched_aliases": list(best.get("matched_aliases", [])),
        "same_l1": same_l1,
        "same_l2": same_l2,
        "cross_l1": cross_l1,
        "builder_sources": sorted(builder_sources),
        "stage_r_present": stage_r_present,
        "stage_r_rank": stage_r_row.get("rank") if stage_r_row else None,
        "stage_r_score": round(float(stage_r_row.get("score_r", 0.0)), 6) if stage_r_row else None,
        "is_primary_neighbor": is_primary_neighbor,
        "is_query_theme_seed": is_query_theme_seed,
        "is_high_risk": bool(node.is_stage_a_high_risk),
        "stage_a_related_prior": stage_a_prior,
        "stage_b_related_prior": stage_b_prior,
        "explicit_secondary_hits": explicit_secondary_hits,
        "cross_domain_secondary_ok": cross_domain_secondary_ok,
        "likely_primary_challenger": likely_primary_challenger,
        "primary_competitor_gap": primary_gap,
        "node_kind": node.node_kind,
        "l1": node.l1,
        "l2": node.l2,
        "segment": node.segment,
        "parent_fqdn": node.parent_fqdn,
        "fallback_to": node.fallback_to,
        "components": best.get("components", {}),
        "source": list(best.get("source", [])),
    }


def _build_related_candidates(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str,
    bundle: dict[str, Any],
    config: RelatedV2Config,
) -> list[dict[str, Any]]:
    stage_r_rows = _stage_r_seed_rows(trace=trace, config=config)
    seed_sources: dict[str, set[str]] = defaultdict(set)

    for fqdn in stage_r_rows:
        seed_sources[fqdn].add("stage_r")
    for fqdn in bundle["stage_a_related_prior"]:
        seed_sources[fqdn].add("stage_a_prior")
    for fqdn in bundle["stage_b_related_prior"]:
        seed_sources[fqdn].add("stage_b_prior")
    for fqdn in _primary_neighbor_seed_fqdns(primary_fqdn=primary_fqdn, resolver=resolver):
        seed_sources[fqdn].add("primary_neighbor")
    for fqdn in _query_theme_seed_fqdns(
        sample=sample,
        resolver=resolver,
        primary_fqdn=primary_fqdn,
        bundle=bundle,
        config=config,
    ):
        seed_sources[fqdn].add("query_theme_seed")

    records: list[dict[str, Any]] = []
    for fqdn, builder_sources in seed_sources.items():
        if _is_chain_duplicate(primary_fqdn, fqdn, resolver):
            continue
        node = resolver.get_node(fqdn)
        if not node:
            continue
        record = _candidate_record(
            sample=sample,
            trace=trace,
            resolver=resolver,
            primary_fqdn=primary_fqdn,
            node=node,
            bundle=bundle,
            config=config,
            builder_sources=builder_sources,
            stage_r_row=stage_r_rows.get(fqdn),
        )
        should_keep = (
            record["score_related_v2"] >= config.min_candidate_score
            or record["stage_a_related_prior"]
            or record["stage_b_related_prior"]
            or record["stage_r_present"]
            or record["is_primary_neighbor"]
            or record["is_query_theme_seed"]
        )
        if should_keep:
            records.append(record)

    records.sort(
        key=lambda row: (
            row["score_related_v2"],
            1 if row["stage_b_related_prior"] else 0,
            1 if row["stage_a_related_prior"] else 0,
            1 if row["stage_r_present"] else 0,
            1 if row["is_primary_neighbor"] else 0,
            1 if row["is_query_theme_seed"] else 0,
            row["best_secondary_score"],
        ),
        reverse=True,
    )
    return records[: config.candidate_pool_limit]


def _related_llm_system_prompt() -> str:
    return (
        "你是 AgentDNS related adjudicator。"
        "你的任务不是改 primary，而是从候选集合中识别 query 里额外成立的 secondary intents。"
        "related 的判断标准很简单：某个候选必须能够对上 query 里的一个非主意图。"
        "如果某候选只是 primary 的重复、同义层级、或者更像 primary challenger，就不要选。"
        "你只能从给定 candidates 中选择 related，不能发明新 fqdn。"
        "如果 query 没有独立 secondary intent，可以返回空列表。"
        "输出必须是单个 JSON 对象。"
    )


def _related_llm_user_prompt(packet: dict[str, Any]) -> str:
    return (
        "请基于下面的 decision packet 做 query-anchored 的 related 判定。\n"
        "要求：\n"
        "1. 先根据原 query 提炼 secondary_intents，且每个 intent 都必须是非主意图。\n"
        "2. 然后逐个 candidate 判断：它是否能明确对上某个 secondary_intent。\n"
        "3. 只有能对上某个 secondary_intent 的 candidate 才能标成 related。\n"
        "4. 如果某候选更像 primary challenger、primary 重复、或者只是场景共现项，请 reject。\n"
        "5. selected_related_fqdns 只能来自 candidates，且不能包含 finalized_primary_fqdn。\n"
        "6. 输出字段：secondary_intents, selected_related_fqdns, confidence, related_rationale, confusion_points, candidate_decisions。\n"
        "7. candidate_decisions 是对象列表，每项包含 fqdn / matched_intent / decision / reason；decision 只能是 related 或 reject。\n"
        "8. matched_intent 只在 decision=related 时填写，且必须来自 secondary_intents 或其等价短语。\n\n"
        f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
    )


def _build_related_decision_packet(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str,
    bundle: dict[str, Any],
    records: list[dict[str, Any]],
    config: RelatedV2Config,
) -> dict[str, Any]:
    primary_node = resolver.get_node(primary_fqdn)
    candidate_rows: list[dict[str, Any]] = []
    for record in records[: config.llm_candidate_limit]:
        node = resolver.get_node(record["fqdn"])
        candidate_rows.append(
            {
                "fqdn": record["fqdn"],
                "score_related_v2": record["score_related_v2"],
                "best_intent_text": record["best_intent_text"],
                "best_secondary_score": record["best_secondary_score"],
                "matched_aliases": record["matched_aliases"],
                "same_l1": record["same_l1"],
                "same_l2": record["same_l2"],
                "cross_l1": record["cross_l1"],
                "is_high_risk": record["is_high_risk"],
                "candidate_builder_sources": record["builder_sources"],
                "stage_r_present": record["stage_r_present"],
                "stage_r_rank": record["stage_r_rank"],
                "explicit_secondary_hits": record["explicit_secondary_hits"],
                "cross_domain_secondary_ok": record["cross_domain_secondary_ok"],
                "likely_primary_challenger": record["likely_primary_challenger"],
                "primary_competitor_gap": record["primary_competitor_gap"],
                "node_kind": record["node_kind"],
                "l1": record["l1"],
                "l2": record["l2"],
                "segment": record["segment"],
                "parent_fqdn": record["parent_fqdn"],
                "fallback_to": record["fallback_to"],
                "desc": node.desc if node else "",
                "aliases": list(node.aliases[:5]) if node else [],
            }
        )
    return {
        "sample_id": sample.get("id"),
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "finalized_primary_fqdn": primary_fqdn,
        "finalized_primary_desc": primary_node.desc if primary_node else "",
        "query_packet": bundle["query_packet"],
        "secondary_intents": bundle["secondary_intents"],
        "primary_secondary_split": bundle["primary_secondary_split"],
        "has_multi_intent_signal": bundle["has_multi_intent_signal"],
        "stage_a_semantic_handoff": _stage_a_semantic_handoff(trace),
        "hard_rules": [
            "selected_related_fqdns must come from candidates",
            "selected_related_fqdns must not contain finalized_primary_fqdn",
            "do not choose primary challengers as related",
            "return [] when no independent secondary theme is supported",
        ],
        "candidate_builder_note": "candidates are built from Stage R top-k, primary neighborhood, priors, and query-theme seeds; query is the semantic anchor, primary is a constraint.",
        "candidates": candidate_rows,
    }


def _sanitize_related_llm_decision(raw: dict[str, Any], candidate_fqdns: list[str]) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    candidate_set = set(candidate_fqdns)
    raw_selected = raw.get("selected_related_fqdns", [])
    if isinstance(raw_selected, str):
        raw_selected = [raw_selected]
    elif not isinstance(raw_selected, list):
        raw_selected = []
        issues.append("related_llm_selection_not_list")
    selected_related: list[str] = []
    for fqdn in raw_selected:
        if fqdn in candidate_set and fqdn not in selected_related:
            selected_related.append(fqdn)
        elif fqdn not in candidate_set:
            issues.append("related_llm_selection_not_in_candidates")

    raw_decisions = raw.get("candidate_decisions")
    if raw_decisions is None:
        raw_decisions = raw.get("candidate_notes", [])
    if isinstance(raw_decisions, dict):
        raw_decisions = [{"fqdn": fqdn, **note} for fqdn, note in raw_decisions.items() if isinstance(note, dict)]
    elif not isinstance(raw_decisions, list):
        raw_decisions = []
    candidate_decisions: list[dict[str, str]] = []
    derived_selected: list[str] = []
    for item in raw_decisions:
        if not isinstance(item, dict):
            continue
        fqdn = item.get("fqdn")
        decision = str(item.get("decision", "")).strip().lower()
        if fqdn not in candidate_set or decision not in {"related", "reject"}:
            continue
        matched_intent = _coerce_short_text(item.get("matched_intent", ""), limit=80)
        reason = _coerce_short_text(item.get("reason", item.get("note", "")), limit=180)
        row = {
            "fqdn": fqdn,
            "decision": decision,
            "matched_intent": matched_intent,
            "reason": reason,
        }
        candidate_decisions.append(row)
        if decision == "related" and matched_intent and fqdn not in derived_selected:
            derived_selected.append(fqdn)
        if len(candidate_decisions) >= 12:
            break
    if not selected_related and derived_selected:
        selected_related = derived_selected

    secondary_intents = []
    raw_secondary = raw.get("secondary_intents", [])
    if isinstance(raw_secondary, list):
        secondary_intents = [str(item)[:120] for item in raw_secondary if str(item).strip()][:5]

    return (
        {
            "secondary_intents": secondary_intents,
            "selected_related_fqdns": selected_related,
            "confidence": _safe_float(raw.get("confidence", 0.0)),
            "related_rationale": _coerce_short_text(raw.get("related_rationale", ""), limit=260),
            "confusion_points": _coerce_short_label_list(raw.get("confusion_points", []), limit=6),
            "candidate_decisions": candidate_decisions,
        },
        issues,
    )


def _apply_related_guardrails(
    records: list[dict[str, Any]],
    proposed: list[str],
    primary_fqdn: str,
    resolver: NamespaceResolver,
    config: RelatedV2Config,
) -> tuple[list[str], list[str], list[str]]:
    record_map = {row["fqdn"]: row for row in records}
    kept: list[str] = []
    notes: list[str] = []
    confusion_points: list[str] = []
    for fqdn in proposed:
        row = record_map.get(fqdn)
        if not row:
            continue
        if _is_chain_duplicate(primary_fqdn, fqdn, resolver):
            notes.append(f"guard_drop:{fqdn}:chain_duplicate")
            confusion_points.append("chain_duplicate_related")
            continue
        if any(_is_chain_duplicate(existing, fqdn, resolver) for existing in kept):
            notes.append(f"guard_drop:{fqdn}:duplicate_related_chain")
            continue
        if row["likely_primary_challenger"] and not row["explicit_secondary_hits"]:
            notes.append(f"guard_drop:{fqdn}:primary_challenger")
            confusion_points.append("primary_challenger_overlap")
            continue

        allow_cross_l1_by_llm_signal = bool(
            row["cross_l1"]
            and row["is_query_theme_seed"]
            and row["stage_r_present"]
            and row["score_related_v2"] >= config.llm_relaxed_cross_l1_min_score
            and not row["likely_primary_challenger"]
        )
        allow_high_risk_by_llm_signal = bool(
            row["is_high_risk"]
            and row["is_query_theme_seed"]
            and row["stage_r_present"]
            and row["score_related_v2"] >= config.cross_l1_select_min_score
            and not row["likely_primary_challenger"]
        )

        if row["cross_l1"] and not row["cross_domain_secondary_ok"] and not allow_cross_l1_by_llm_signal:
            notes.append(f"guard_drop:{fqdn}:cross_domain_secondary_uncertain")
            confusion_points.append("cross_domain_secondary_uncertain")
            continue
        if row["is_high_risk"] and not row["explicit_secondary_hits"] and not row["stage_b_related_prior"] and not allow_high_risk_by_llm_signal:
            notes.append(f"guard_drop:{fqdn}:high_risk_without_explicit_support")
            confusion_points.append("high_risk_secondary_uncertain")
            continue
        threshold = config.cross_l1_select_min_score if row["cross_l1"] else config.select_min_score
        if row["is_primary_neighbor"] and not row["cross_l1"]:
            threshold = min(threshold, config.llm_relaxed_primary_neighbor_min_score)
        elif allow_cross_l1_by_llm_signal:
            threshold = min(threshold, config.llm_relaxed_cross_l1_min_score)
        if row["score_related_v2"] < threshold and not (row["stage_a_related_prior"] or row["stage_b_related_prior"]):
            notes.append(f"guard_drop:{fqdn}:below_score_threshold")
            continue
        if allow_cross_l1_by_llm_signal:
            notes.append(f"guard_keep:{fqdn}:cross_l1_llm_supported")
        if allow_high_risk_by_llm_signal:
            notes.append(f"guard_keep:{fqdn}:high_risk_llm_supported")
        kept.append(fqdn)
        if len(kept) >= config.max_related:
            break
    return kept, notes, sorted(set(confusion_points))


def _select_related_candidates(
    records: list[dict[str, Any]],
    primary_fqdn: str,
    resolver: NamespaceResolver,
    config: RelatedV2Config,
) -> tuple[list[str], list[str], list[str]]:
    selected: list[str] = []
    notes: list[str] = []
    confusion_points: list[str] = []
    for record in records:
        fqdn = record["fqdn"]
        score = record["score_related_v2"]
        if any(_is_chain_duplicate(existing, fqdn, resolver) for existing in selected):
            continue
        if record["likely_primary_challenger"] and not (record["stage_a_related_prior"] or record["stage_b_related_prior"]):
            confusion_points.append("primary_challenger_overlap")
            continue
        threshold = config.cross_l1_select_min_score if record["cross_l1"] else config.select_min_score
        if record["stage_a_related_prior"] or record["stage_b_related_prior"]:
            threshold = min(threshold, config.prior_rescue_min_score)
        if score < threshold:
            continue
        if record["cross_l1"] and not record["cross_domain_secondary_ok"] and not (record["stage_a_related_prior"] or record["stage_b_related_prior"]):
            confusion_points.append("cross_domain_secondary_uncertain")
            continue
        if record["is_high_risk"] and not record["explicit_secondary_hits"] and not record["stage_b_related_prior"]:
            confusion_points.append("high_risk_secondary_uncertain")
            continue
        selected.append(fqdn)
        notes.append(f"select:{fqdn}:score={score}")
        if len(selected) >= config.max_related:
            break
    return selected, notes, sorted(set(confusion_points))


def _review_related_selection(
    records: list[dict[str, Any]],
    selected: list[str],
    confusion_points: list[str],
    config: RelatedV2Config,
) -> dict[str, Any]:
    if not records:
        return {
            "triggered": False,
            "review_reasons": [],
            "review_notes": [],
            "final_related_fqdns": selected,
            "final_confidence": 0.0,
        }

    score_map = {row["fqdn"]: row["score_related_v2"] for row in records}
    selected_scores = [score_map[fqdn] for fqdn in selected if fqdn in score_map]
    confidence = round(sum(selected_scores) / len(selected_scores), 6) if selected_scores else 0.0

    top_rejected = next((row for row in records if row["fqdn"] not in selected), None)
    top_rejected_gap = None
    if selected and top_rejected:
        top_rejected_gap = round(selected_scores[-1] - top_rejected["score_related_v2"], 6)

    review_reasons: list[str] = []
    if confidence < config.review_confidence_threshold:
        review_reasons.append("low_related_confidence")
    if any(row["cross_l1"] for row in records if row["fqdn"] in selected):
        review_reasons.append("cross_l1_secondary")
    if any(row["is_high_risk"] for row in records if row["fqdn"] in selected):
        review_reasons.append("high_risk_secondary")
    if top_rejected_gap is not None and top_rejected_gap <= config.review_gap_threshold:
        review_reasons.append("close_related_margin")
    review_reasons.extend(confusion_points)
    review_reasons = sorted(set(review_reasons))

    final_related = list(selected)
    review_notes: list[str] = []
    if not review_reasons:
        return {
            "triggered": False,
            "review_reasons": [],
            "review_notes": [],
            "final_related_fqdns": final_related,
            "final_confidence": confidence,
        }

    for row in records:
        if row["fqdn"] in final_related:
            continue
        if len(final_related) >= config.max_related:
            break
        if row["cross_l1"]:
            if row["score_related_v2"] < config.review_cross_l1_add_min_score or not row["cross_domain_secondary_ok"]:
                continue
        elif row["score_related_v2"] < config.review_add_min_score:
            continue
        if row["likely_primary_challenger"]:
            continue
        final_related.append(row["fqdn"])
        review_notes.append(f"review_add:{row['fqdn']}")

    filtered: list[str] = []
    for fqdn in final_related:
        row = next(item for item in records if item["fqdn"] == fqdn)
        if row["is_high_risk"] and not row["explicit_secondary_hits"] and not row["stage_b_related_prior"]:
            review_notes.append(f"review_drop:{fqdn}:high_risk_without_explicit_support")
            continue
        filtered.append(fqdn)

    final_scores = [score_map[fqdn] for fqdn in filtered if fqdn in score_map]
    final_confidence = round(sum(final_scores) / len(final_scores), 6) if final_scores else 0.0
    return {
        "triggered": True,
        "review_reasons": review_reasons,
        "review_notes": review_notes,
        "final_related_fqdns": filtered[: config.max_related],
        "final_confidence": final_confidence,
    }


def analyze_related_v2(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    primary_fqdn: str | None = None,
    config: RelatedV2Config | None = None,
    client: RelatedV2LLMClient | None = None,
) -> dict[str, Any]:
    config = config or RelatedV2Config()
    primary_fqdn = primary_fqdn or trace.get("final_primary_fqdn") or trace.get("stage_a", {}).get("selected_primary_fqdn")
    if not primary_fqdn or not validate_fqdn(primary_fqdn):
        return {
            "related_version": config.related_version,
            "selected_related_fqdns": [],
            "final_related_fqdns": [],
            "related_confidence": 0.0,
            "secondary_intents": [],
            "primary_secondary_split": {},
            "related_candidates": [],
            "decision_source": "related_v2",
            "review": {"triggered": False, "review_reasons": ["invalid_primary"], "review_notes": []},
            "execution": {"prefetch_reused": False, "reran_after_primary_override": False},
        }

    bundle = _secondary_intent_bundle(sample=sample, trace=trace, primary_fqdn=primary_fqdn, resolver=resolver)
    records = _build_related_candidates(
        sample=sample,
        trace=trace,
        resolver=resolver,
        primary_fqdn=primary_fqdn,
        bundle=bundle,
        config=config,
    )
    if client is None:
        selected, selection_notes, confusion_points = _select_related_candidates(
            records=records,
            primary_fqdn=primary_fqdn,
            resolver=resolver,
            config=config,
        )
        review = _review_related_selection(records=records, selected=selected, confusion_points=confusion_points, config=config)
        secondary_intents = bundle["secondary_intents"]
        decision_source = "related_v2_det"
        llm_trace: dict[str, Any] | None = None
    else:
        packet = _build_related_decision_packet(
            sample=sample,
            trace=trace,
            resolver=resolver,
            primary_fqdn=primary_fqdn,
            bundle=bundle,
            records=records,
            config=config,
        )
        raw_decision, raw_text = client.adjudicate_related(packet, config)
        llm_decision, llm_issues = _sanitize_related_llm_decision(raw_decision, [row["fqdn"] for row in records])
        selected, guard_notes, guard_confusion = _apply_related_guardrails(
            records=records,
            proposed=llm_decision["selected_related_fqdns"],
            primary_fqdn=primary_fqdn,
            resolver=resolver,
            config=config,
        )
        confidence = 0.0
        if selected:
            score_map = {row["fqdn"]: row["score_related_v2"] for row in records}
            confidence = round(
                _clip(
                    0.55 * llm_decision["confidence"]
                    + 0.45 * (sum(score_map[fqdn] for fqdn in selected) / len(selected))
                ),
                6,
            )
        review = {
            "triggered": False,
            "review_reasons": sorted(set(llm_decision["confusion_points"] + guard_confusion + llm_issues)),
            "review_notes": guard_notes,
            "final_related_fqdns": selected,
            "final_confidence": confidence,
        }
        selection_notes = [f"llm_select:{fqdn}" for fqdn in llm_decision["selected_related_fqdns"]]
        confusion_points = sorted(set(llm_decision["confusion_points"] + guard_confusion))
        secondary_intents = _dedupe_texts(llm_decision["secondary_intents"] + bundle["secondary_intents"])
        decision_source = "related_v2_llm"
        llm_trace = {
            "provider": client.provider,
            "model": client.model,
            "packet": packet,
            "decision": llm_decision,
            "raw_response": raw_text,
            "issues": llm_issues,
        }

    return {
        "related_version": config.related_version,
        "primary_fqdn": primary_fqdn,
        "secondary_intents": secondary_intents,
        "primary_secondary_split": bundle["primary_secondary_split"],
        "has_multi_intent_signal": bundle["has_multi_intent_signal"],
        "candidate_count": len(records),
        "related_candidates": records,
        "selected_related_fqdns": selected,
        "final_related_fqdns": list(review["final_related_fqdns"]),
        "related_confidence": review["final_confidence"],
        "confusion_points": confusion_points,
        "selection_notes": selection_notes,
        "decision_source": decision_source,
        "review": {
            "triggered": review["triggered"],
            "review_reasons": list(review["review_reasons"]),
            "review_notes": list(review["review_notes"]),
        },
        "llm_trace": llm_trace,
        "execution": {"prefetch_reused": False, "reran_after_primary_override": False},
    }


def attach_related_v2_final_fields(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: RelatedV2Config | None = None,
    precomputed: dict[str, Any] | None = None,
    client: RelatedV2LLMClient | None = None,
) -> dict[str, Any]:
    config = config or RelatedV2Config()
    final_primary = trace.get("final_primary_fqdn") or trace.get("stage_a", {}).get("selected_primary_fqdn")
    related_result = None
    if precomputed and precomputed.get("primary_fqdn") == final_primary:
        related_result = copy.deepcopy(precomputed)
        related_result.setdefault("execution", {})
        related_result["execution"]["prefetch_reused"] = True
    else:
        related_result = analyze_related_v2(
            sample=sample,
            trace=trace,
            resolver=resolver,
            primary_fqdn=final_primary,
            config=config,
            client=client,
        )
        related_result.setdefault("execution", {})
        if precomputed and precomputed.get("primary_fqdn") != final_primary:
            related_result["execution"]["reran_after_primary_override"] = True

    updated = copy.deepcopy(trace)
    updated["related_v2_version"] = config.related_version
    updated["related_v2"] = related_result
    updated["legacy_final_related_fqdns"] = list(updated.get("final_related_fqdns", []))
    updated["final_related_fqdns"] = list(related_result.get("final_related_fqdns", []))
    updated["final_related_source"] = related_result.get("decision_source", "related_v2")
    return updated
