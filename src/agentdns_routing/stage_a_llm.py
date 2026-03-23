from __future__ import annotations

import json
import math
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from .namespace import NamespaceResolver, RoutingNode, validate_fqdn
from .routing_chain import attach_stage_a_final_fields
from .stage_a_clean import (
    StageACleanConfig,
    _chain_members,
    _clip,
    _has_required_cues,
    analyze_stage_a,
)

CLAUSE_RE = re.compile(r"[。！？!?；;]")
QUOTE_RE = re.compile(r"[“\"「『](.*?)[”\"」』]")


@dataclass(frozen=True)
class StageALLMConfig:
    stage_a_version: str = "sa_llm_v1_20260314"
    prompt_version: str = "stage_a_prompt_v1_20260317"
    base_stage_a_version: str = StageACleanConfig().stage_a_version
    prompt_candidate_limit: int = 8
    routing_top_k: int = 5
    max_related: int = 3
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1400
    score_temperature: float = 0.45
    confidence_threshold: float = 0.62
    llm_confidence_relief_threshold: float = 0.82
    margin_threshold: float = 0.08
    high_risk_margin_threshold: float = 0.14
    minmax_spread_floor: float = 0.5
    primary_blend_scale: float = 1.0
    related_blend_scale: float = 1.0
    llm_bias_scale: float = 1.0
    related_min_score: float = 0.42
    deterministic_related_anchor_threshold: float = 0.80
    same_l1_secondary_related_anchor_threshold: float = 0.55
    same_l1_secondary_related_min_score: float = 0.30
    cross_l1_secondary_related_min_score: float = 0.68
    scene_only_descendant_margin_threshold: float = 0.20

    @property
    def base_primary_weight(self) -> float:
        return 0.55 * self.primary_blend_scale

    @property
    def stage_r_weight(self) -> float:
        return 0.15 * self.primary_blend_scale

    @property
    def llm_task_weight(self) -> float:
        return 0.15 * self.primary_blend_scale

    @property
    def llm_primary_weight(self) -> float:
        return 0.10 * self.primary_blend_scale

    @property
    def llm_primary_bonus(self) -> float:
        return 0.05 * self.llm_bias_scale

    @property
    def llm_specificity_fit_bonus(self) -> float:
        return 0.05 * self.llm_bias_scale

    @property
    def llm_specificity_coarse_penalty(self) -> float:
        return 0.05 * self.llm_bias_scale

    @property
    def llm_specificity_specific_penalty(self) -> float:
        return 0.07 * self.llm_bias_scale

    @property
    def llm_risk_penalty(self) -> float:
        return 0.08 * self.llm_bias_scale

    @property
    def base_related_weight(self) -> float:
        return 0.50 * self.related_blend_scale

    @property
    def llm_related_weight(self) -> float:
        return 0.30 * self.related_blend_scale

    @property
    def llm_related_selected_bonus(self) -> float:
        return 0.08 * self.llm_bias_scale

    @property
    def llm_task_related_weight(self) -> float:
        return 0.08 * self.related_blend_scale


class StageALLMClient(Protocol):
    provider: str
    model: str

    def adjudicate(self, packet: dict[str, Any], config: StageALLMConfig) -> tuple[dict[str, Any], str]:
        raise NotImplementedError


class OpenAICompatibleStageALLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 45.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1)

    def adjudicate(self, packet: dict[str, Any], config: StageALLMConfig) -> tuple[dict[str, Any], str]:
        messages = [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(packet)},
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


def make_llm_client(provider: str, model: str | None = None) -> StageALLMClient:
    provider = provider.lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set")
        return OpenAICompatibleStageALLMClient(
            provider="deepseek",
            model=model or "deepseek-chat",
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=45.0,
        )
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set")
        return OpenAICompatibleStageALLMClient(
            provider="openai",
            model=model or "gpt-5.4",
            api_key=api_key,
            timeout=45.0,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _system_prompt() -> str:
    return (
        "你是 AgentDNS Stage A 的单智能体裁决器。"
        "你只能在给定候选集合内做结构化裁决，不能发明新 fqdn。"
        "先理解 query 的 scene_context、primary_intent、secondary_intents，再在 candidates 内判断 primary/related。"
        "你必须区分 primary 和 related；若不确定，应请求升级到 Stage B。"
        "confusion_sources 只是软提示，不是既定事实。"
        "输出必须是单个 JSON 对象，不能附带散文解释。"
    )


def _user_prompt(packet: dict[str, Any]) -> str:
    return (
        "请基于下面的 decision packet 进行候选内裁决。\n"
        "要求：\n"
        "1. 只能从 candidates 中选 selected_primary_fqdn 和 selected_related_fqdns。\n"
        "2. 先输出 scene_context、primary_intent、secondary_intents。\n"
        "3. related 只在存在明确 secondary_intent 且候选直接承接该 secondary_intent 时才可填写；若无明确 secondary_intent，一般返回空列表。\n"
        "4. 对每个 selected_related_fqdn，candidate_judgements.evidence_for 必须给出支持它的具体短语；不要因为“泛相关”就挂 related。\n"
        "5. 在 governance/security 场景，不要把 sibling 节点默认当 related，除非 query 里存在独立次要诉求。\n"
        "6. candidate_judgements 里至少覆盖所有 candidates。\n"
        "7. task_fit / primary_fit / related_fit 都用 0 到 1 的数值。\n"
        "8. specificity_judgement 只能取 too_coarse / fit / too_specific。\n"
        "9. confidence 用 0 到 1，但这是模型自评，不会直接决定最终系统置信度。\n"
        "10. 若低置信、样本高风险或 primary/related 拿不准，设置 escalate_to_stage_b=true。\n\n"
        f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
    )


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


def _candidate_desc(node: RoutingNode | None) -> str:
    if not node:
        return ""
    return node.desc


def _truncate_aliases(node: RoutingNode | None, limit: int = 5) -> list[str]:
    if not node:
        return []
    return list(node.aliases[:limit])


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


def _minmax_norm(values: dict[str, float], spread_floor: float = 0.5) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    spread = high - low
    if math.isclose(spread, 0.0):
        return {key: 0.0 for key in values}
    denom = max(spread, spread_floor)
    return {key: _clip((value - low) / denom) for key, value in values.items()}


def _specificity_adjustment(label: str, config: StageALLMConfig) -> float:
    if label == "fit":
        return config.llm_specificity_fit_bonus
    if label == "too_coarse":
        return -config.llm_specificity_coarse_penalty
    if label == "too_specific":
        return -config.llm_specificity_specific_penalty
    return 0.0


def _normalize_specificity_judgement(raw: Any) -> tuple[str, str | None]:
    text = str(raw or "").strip().lower()
    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in {"fit", "too_coarse", "too_specific"}:
        return normalized, None
    if normalized in {"coarse", "too_coarsed", "toocoarse"}:
        return "too_coarse", "llm_specificity_judgement_normalized"
    if normalized in {"specific", "toospecific"}:
        return "too_specific", "llm_specificity_judgement_normalized"
    return "fit", "llm_specificity_judgement_unknown"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return _clip(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_text_list(value: Any, limit: int = 3) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text[:240]] if text else []
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if not item:
            continue
        text = str(item).strip()
        if text:
            items.append(text[:240])
        if len(items) >= limit:
            break
    return items


def _build_prompt_query_view(query: str) -> dict[str, Any]:
    text = (query or "").strip()
    clauses = [part.strip("，。；; ") for part in CLAUSE_RE.split(text) if part.strip("，。；; ")]
    quoted_segments = [match.strip() for match in QUOTE_RE.findall(text) if match.strip()]
    return {
        "full_text": text,
        "clauses": clauses[:6],
        "quoted_segments": quoted_segments[:3],
    }


def _sanitize_llm_decision(raw: dict[str, Any], candidate_fqdns: list[str]) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    candidate_set = set(candidate_fqdns)
    selected_primary = raw.get("selected_primary_fqdn")
    if selected_primary not in candidate_set:
        issues.append("llm_primary_not_in_candidates")
        selected_primary = None

    raw_selected_related = raw.get("selected_related_fqdns", [])
    if not isinstance(raw_selected_related, list):
        raw_selected_related = []
        issues.append("llm_related_not_list")
    selected_related = [fqdn for fqdn in raw_selected_related if fqdn in candidate_set]
    if len(selected_related) != len(raw_selected_related):
        issues.append("llm_related_not_in_candidates")

    raw_judgements = raw.get("candidate_judgements", [])
    if isinstance(raw_judgements, dict):
        raw_judgements = [
            {"fqdn": fqdn, **row}
            for fqdn, row in raw_judgements.items()
            if isinstance(row, dict)
        ]
    elif not isinstance(raw_judgements, list):
        raw_judgements = []
        issues.append("llm_judgements_not_list")
    judgements_by_fqdn = {}
    for row in raw_judgements:
        if not isinstance(row, dict):
            issues.append("llm_judgement_not_object")
            continue
        fqdn = row.get("fqdn")
        if fqdn in candidate_set:
            judgements_by_fqdn[fqdn] = row
    candidate_judgements: list[dict[str, Any]] = []
    for fqdn in candidate_fqdns:
        row = judgements_by_fqdn.get(fqdn, {})
        specificity_judgement, specificity_issue = _normalize_specificity_judgement(
            row.get("specificity_judgement", "fit")
        )
        if specificity_issue:
            issues.append(specificity_issue)
        candidate_judgements.append(
            {
                "fqdn": fqdn,
                "task_fit": _safe_float(row.get("task_fit", 0.0)),
                "primary_fit": _safe_float(row.get("primary_fit", 0.0)),
                "related_fit": _safe_float(row.get("related_fit", 0.0)),
                "specificity_judgement": specificity_judgement,
                "risk_mismatch": bool(row.get("risk_mismatch", False)),
                "confidence": _safe_float(row.get("confidence", 0.0)),
                "evidence_for": _coerce_text_list(row.get("evidence_for", []), limit=3),
                "evidence_against": _coerce_text_list(row.get("evidence_against", []), limit=3),
            }
        )

    top_confidence = _safe_float(raw.get("confidence", 0.0))
    if top_confidence == 0.0 and selected_primary:
        primary_row = next((row for row in candidate_judgements if row["fqdn"] == selected_primary), None)
        if primary_row:
            top_confidence = max(
                primary_row.get("confidence", 0.0),
                0.6 * primary_row.get("task_fit", 0.0) + 0.4 * primary_row.get("primary_fit", 0.0),
            )

    raw_escalation_reasons = raw.get("escalation_reasons", [])
    if isinstance(raw_escalation_reasons, str):
        raw_escalation_reasons = [raw_escalation_reasons]
    elif not isinstance(raw_escalation_reasons, list):
        raw_escalation_reasons = []

    raw_notes = raw.get("notes", [])
    if isinstance(raw_notes, str):
        raw_notes = [raw_notes]
    elif not isinstance(raw_notes, list):
        raw_notes = []

    return (
        {
            "scene_context": str(raw.get("scene_context", ""))[:200],
            "primary_intent": str(raw.get("primary_intent", ""))[:200],
            "secondary_intents": [str(item)[:120] for item in raw.get("secondary_intents", []) if item][:5]
            if isinstance(raw.get("secondary_intents", []), list)
            else [],
            "selected_primary_fqdn": selected_primary,
            "selected_related_fqdns": selected_related,
            "candidate_judgements": candidate_judgements,
            "confidence": top_confidence,
            "escalate_to_stage_b": bool(raw.get("escalate_to_stage_b", False)),
            "escalation_reasons": list(raw_escalation_reasons),
            "notes": list(raw_notes)[:5],
        },
        issues,
    )


def build_decision_packet(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    base_stage_a: dict[str, Any],
    config: StageALLMConfig | None = None,
) -> dict[str, Any]:
    config = config or StageALLMConfig()
    base_map = {row["fqdn"]: row for row in base_stage_a.get("candidate_scores", [])}
    candidates_sorted = sorted(snapshot.get("fqdn_candidates", []), key=lambda row: row.get("score_r", 0.0), reverse=True)
    top_candidates = candidates_sorted[: config.prompt_candidate_limit]
    top1 = top_candidates[0]["fqdn"] if top_candidates else None
    top2 = top_candidates[1]["fqdn"] if len(top_candidates) > 1 else None
    top_gap = 0.0
    if len(top_candidates) > 1:
        top_gap = round(float(top_candidates[0].get("score_r", 0.0)) - float(top_candidates[1].get("score_r", 0.0)), 6)

    packet_candidates: list[dict[str, Any]] = []
    for row in top_candidates:
        node = resolver.get_node(row["fqdn"])
        base_row = base_map.get(row["fqdn"], {})
        evidence = base_row.get("evidence_for", {})
        packet_candidates.append(
            {
                "fqdn": row["fqdn"],
                "score_r": round(float(row.get("score_r", 0.0)), 6),
                "node_kind": row.get("node_kind"),
                "l1": row.get("l1"),
                "l2": row.get("l2"),
                "segment": row.get("segment"),
                "parent_fqdn": row.get("parent_fqdn"),
                "fallback_to": row.get("fallback_to"),
                "desc": _candidate_desc(node),
                "aliases": _truncate_aliases(node),
                "source": list(row.get("source", [])),
                "matched_phrases": row.get("matched_phrases", {}),
                "components": {
                    key: round(float(value), 6) if isinstance(value, (int, float)) else value
                    for key, value in row.get("components", {}).items()
                },
                "primary_hits": evidence.get("primary_hits", []),
                "secondary_hits": evidence.get("secondary_hits", []),
                "scene_hits": evidence.get("scene_hits", []),
            }
        )

    return {
        "sample_id": sample["id"],
        "namespace_version": snapshot["namespace_version"],
        "stage_r_version": snapshot["stage_r_version"],
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "query_view": _build_prompt_query_view(sample.get("query", "")),
        "hard_rules": [
            "只能从 candidates 中选 selected_primary_fqdn 和 selected_related_fqdns",
            "primary 必须唯一",
            "related 可以为空，但不能包含 primary",
            "若不确定，可设置 escalate_to_stage_b=true",
        ],
        "soft_hints": {
            "confusion_sources": snapshot.get("confusion_sources", []),
            "selection_signals": snapshot.get("semantic_parse", {}).get("selection_signals", {}),
            "top1_candidate_by_stage_r": top1,
            "top2_candidate_by_stage_r": top2,
            "top1_top2_gap": top_gap,
        },
        "candidates": packet_candidates,
    }


def _is_chain_duplicate(primary_fqdn: str, other_fqdn: str, resolver: NamespaceResolver) -> bool:
    if primary_fqdn == other_fqdn:
        return True
    return other_fqdn in _chain_members(primary_fqdn, resolver) or primary_fqdn in _chain_members(other_fqdn, resolver)


def _is_descendant(descendant_fqdn: str, ancestor_fqdn: str, resolver: NamespaceResolver) -> bool:
    if descendant_fqdn == ancestor_fqdn:
        return False
    return ancestor_fqdn in _chain_members(descendant_fqdn, resolver)


def _same_l1(left_fqdn: str | None, right_fqdn: str | None, resolver: NamespaceResolver) -> bool:
    if not left_fqdn or not right_fqdn:
        return False
    left = resolver.get_node(left_fqdn)
    right = resolver.get_node(right_fqdn)
    if not left or not right:
        return False
    return left.l1 == right.l1


def _is_high_risk_route(fqdn: str | None, resolver: NamespaceResolver) -> bool:
    if not fqdn:
        return False
    node = resolver.get_node(fqdn)
    if not node:
        return False
    return bool(node.is_stage_a_high_risk)


def _softmax_scores(scores: dict[str, float], temperature: float) -> dict[str, float]:
    if not scores:
        return {}
    safe_temp = max(temperature, 1e-6)
    shift = max(scores.values())
    exps = {key: math.exp((value - shift) / safe_temp) for key, value in scores.items()}
    total = sum(exps.values()) or 1.0
    return {key: value / total for key, value in exps.items()}


def _agreement_score(selected_primary: str | None, deterministic_primary: str | None, resolver: NamespaceResolver) -> float:
    if not selected_primary or not deterministic_primary:
        return 0.0
    if selected_primary == deterministic_primary:
        return 1.0
    if _is_chain_duplicate(selected_primary, deterministic_primary, resolver):
        return 0.6
    return 0.0


def _llm_evidence_support(llm_row: dict[str, Any]) -> float:
    specificity, _ = _normalize_specificity_judgement(llm_row.get("specificity_judgement", "fit"))
    specificity_support = 1.0 if specificity == "fit" else 0.6 if specificity == "too_coarse" else 0.4
    return _clip(
        0.55 * _safe_float(llm_row.get("task_fit", 0.0))
        + 0.35 * _safe_float(llm_row.get("primary_fit", 0.0))
        + 0.10 * specificity_support
    )


def calibrate_llm_decision(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    base_stage_a: dict[str, Any],
    llm_decision: dict[str, Any],
    llm_issues: list[str],
    raw_response: str,
    client: StageALLMClient,
    config: StageALLMConfig | None = None,
) -> dict[str, Any]:
    config = config or StageALLMConfig()
    candidate_rows = snapshot.get("fqdn_candidates", [])
    candidate_fqdns = [row["fqdn"] for row in candidate_rows]
    candidate_set = set(candidate_fqdns)
    base_map = {row["fqdn"]: row for row in base_stage_a.get("candidate_scores", [])}
    llm_map = {row["fqdn"]: row for row in llm_decision.get("candidate_judgements", [])}

    det_primary_scores = {fqdn: float(base_map[fqdn]["score_a"]) for fqdn in candidate_fqdns if fqdn in base_map}
    det_related_scores = {fqdn: float(base_map[fqdn]["score_related"]) for fqdn in candidate_fqdns if fqdn in base_map}
    det_primary_norm = _minmax_norm(det_primary_scores, spread_floor=config.minmax_spread_floor)
    det_related_norm = _minmax_norm(det_related_scores, spread_floor=config.minmax_spread_floor)
    stage_r_norm = {fqdn: float(base_map[fqdn]["score_breakdown"].get("score_r_norm", 0.0)) for fqdn in candidate_fqdns if fqdn in base_map}

    primary_scores: dict[str, float] = {}
    related_scores: dict[str, float] = {}
    candidate_scores: list[dict[str, Any]] = []

    llm_selected_primary = llm_decision.get("selected_primary_fqdn")
    llm_selected_related = set(llm_decision.get("selected_related_fqdns", []))

    for row in candidate_rows:
        fqdn = row["fqdn"]
        llm_row = llm_map.get(
            fqdn,
            {
                "task_fit": 0.0,
                "primary_fit": 0.0,
                "related_fit": 0.0,
                "specificity_judgement": "fit",
                "risk_mismatch": False,
                "evidence_for": [],
                "evidence_against": [],
            },
        )
        specificity_judgement, specificity_issue = _normalize_specificity_judgement(
            llm_row.get("specificity_judgement", "fit")
        )
        if specificity_issue:
            llm_issues.append(specificity_issue)
        specificity_adjustment = _specificity_adjustment(specificity_judgement, config)
        risk_penalty = config.llm_risk_penalty if llm_row.get("risk_mismatch") else 0.0
        selected_primary_bonus = config.llm_primary_bonus if fqdn == llm_selected_primary else 0.0
        selected_related_bonus = config.llm_related_selected_bonus if fqdn in llm_selected_related else 0.0

        score_primary = (
            config.base_primary_weight * det_primary_norm.get(fqdn, 0.0)
            + config.stage_r_weight * stage_r_norm.get(fqdn, 0.0)
            + config.llm_task_weight * _safe_float(llm_row.get("task_fit", 0.0))
            + config.llm_primary_weight * _safe_float(llm_row.get("primary_fit", 0.0))
            + selected_primary_bonus
            + specificity_adjustment
            - risk_penalty
        )
        score_related = (
            config.base_related_weight * det_related_norm.get(fqdn, 0.0)
            + config.llm_related_weight * _safe_float(llm_row.get("related_fit", 0.0))
            + config.llm_task_related_weight * _safe_float(llm_row.get("task_fit", 0.0))
            + selected_related_bonus
        )
        primary_scores[fqdn] = round(score_primary, 6)
        related_scores[fqdn] = round(score_related, 6)
        candidate_scores.append(
            {
                "fqdn": fqdn,
                "score_a": round(score_primary, 6),
                "score_related": round(score_related, 6),
                "score_breakdown": {
                    "det_primary_norm": round(det_primary_norm.get(fqdn, 0.0), 6),
                    "det_related_norm": round(det_related_norm.get(fqdn, 0.0), 6),
                    "stage_r_norm": round(stage_r_norm.get(fqdn, 0.0), 6),
                    "llm_task_fit": round(_safe_float(llm_row.get("task_fit", 0.0)), 6),
                    "llm_primary_fit": round(_safe_float(llm_row.get("primary_fit", 0.0)), 6),
                    "llm_related_fit": round(_safe_float(llm_row.get("related_fit", 0.0)), 6),
                    "llm_specificity_judgement": specificity_judgement,
                    "llm_selected_primary_bonus": round(selected_primary_bonus, 6),
                    "llm_selected_related_bonus": round(selected_related_bonus, 6),
                    "specificity_adjustment": round(specificity_adjustment, 6),
                    "risk_penalty": round(risk_penalty, 6),
                },
                "evidence_for": list(llm_row.get("evidence_for", []))[:3],
                "evidence_against": list(llm_row.get("evidence_against", []))[:3],
            }
        )

    ranked_primary = sorted(candidate_fqdns, key=lambda fqdn: (primary_scores[fqdn], related_scores[fqdn]), reverse=True)
    selected_primary = ranked_primary[0] if ranked_primary else None
    deterministic_primary = base_stage_a.get("selected_primary_fqdn")
    if (
        selected_primary
        and deterministic_primary
        and selected_primary != deterministic_primary
        and _is_descendant(selected_primary, deterministic_primary, resolver)
    ):
        primary_gap = primary_scores[selected_primary] - primary_scores.get(deterministic_primary, 0.0)
        selected_base_evidence = base_map.get(selected_primary, {}).get("evidence_for", {})
        selected_primary_hits = selected_base_evidence.get("primary_hits", [])
        selected_scene_hits = selected_base_evidence.get("scene_hits", [])
        deterministic_llm_row = llm_map.get(deterministic_primary, {})
        selected_node = resolver.get_node(selected_primary)
        if (
            det_primary_norm.get(deterministic_primary, 0.0) >= 0.85
            and primary_gap <= config.margin_threshold
            and not selected_primary_hits
        ):
            selected_primary = deterministic_primary
        elif (
            selected_node
            and selected_node.node_kind == "segment"
            and det_primary_norm.get(deterministic_primary, 0.0) >= 0.85
            and primary_gap <= config.scene_only_descendant_margin_threshold
            and not selected_primary_hits
            and bool(selected_scene_hits)
            and _safe_float(deterministic_llm_row.get("task_fit", 0.0)) >= 0.6
        ):
            selected_primary = deterministic_primary
        elif (
            selected_node
            and selected_node.routing_constraints.get("requires_explicit_primary_cues")
            and selected_node.routing_constraints.get("generic_trigger_aliases")
            and bool(selected_primary_hits)
            and set(selected_primary_hits) <= set(selected_node.routing_constraints.get("generic_trigger_aliases", []))
            and not _has_required_cues(
                sample.get("query", ""),
                tuple(selected_node.routing_constraints.get("requires_explicit_primary_cues", [])),
            )
            and det_primary_norm.get(deterministic_primary, 0.0) >= 0.9
        ):
            selected_primary = deterministic_primary
    if (
        selected_primary
        and deterministic_primary
        and selected_primary != deterministic_primary
        and _is_descendant(deterministic_primary, selected_primary, resolver)
    ):
        det_row = llm_map.get(deterministic_primary, {})
        if det_primary_norm.get(deterministic_primary, 0.0) >= 0.85 and _safe_float(det_row.get("task_fit", 0.0)) >= 0.55:
            selected_primary = deterministic_primary

    ranked_related_candidates = sorted(
        [fqdn for fqdn in candidate_fqdns if fqdn != selected_primary],
        key=lambda fqdn: (related_scores[fqdn], primary_scores[fqdn], 1 if resolver.get_node(fqdn) and resolver.get_node(fqdn).node_kind == "segment" else 0),
        reverse=True,
    )
    selected_related: list[str] = []
    deterministic_related = set(base_stage_a.get("selected_related_fqdns", []))
    selection_signals = snapshot.get("semantic_parse", {}).get("selection_signals", {})
    has_secondary_context = bool(selection_signals.get("has_multi_intent_signal") or llm_decision.get("secondary_intents"))
    for fqdn in ranked_related_candidates:
        if _is_chain_duplicate(selected_primary, fqdn, resolver):
            continue
        llm_row = llm_map.get(fqdn, {})
        llm_evidence_for = [item for item in llm_row.get("evidence_for", []) if item]
        base_evidence = base_map.get(fqdn, {}).get("evidence_for", {})
        has_secondary_hits = bool(base_evidence.get("secondary_hits", []))
        has_related_signal = fqdn in llm_selected_related
        has_deterministic_anchor = (
            fqdn in deterministic_related and det_related_norm.get(fqdn, 0.0) >= config.deterministic_related_anchor_threshold
        )
        has_same_l1_secondary_anchor = (
            _same_l1(selected_primary, fqdn, resolver)
            and not _is_high_risk_route(fqdn, resolver)
            and fqdn in deterministic_related
            and det_related_norm.get(fqdn, 0.0) >= config.same_l1_secondary_related_anchor_threshold
            and has_secondary_hits
        )
        if not has_related_signal and (has_deterministic_anchor or has_same_l1_secondary_anchor):
            has_related_signal = True
        if not has_related_signal:
            continue
        if not has_deterministic_anchor and not has_secondary_context:
            continue
        if not has_deterministic_anchor and not (llm_evidence_for or has_secondary_hits):
            continue
        allow_cross_l1_secondary = (
            not _is_high_risk_route(selected_primary, resolver)
            and not _is_high_risk_route(fqdn, resolver)
            and fqdn in llm_selected_related
            and has_secondary_context
            and (llm_evidence_for or has_secondary_hits)
            and related_scores[fqdn] >= config.cross_l1_secondary_related_min_score
        )
        if not _same_l1(selected_primary, fqdn, resolver) and not has_deterministic_anchor and not allow_cross_l1_secondary:
            continue
        min_related_score = (
            config.same_l1_secondary_related_min_score
            if has_same_l1_secondary_anchor
            else config.related_min_score
        )
        if related_scores[fqdn] < min_related_score:
            continue
        if any(_is_chain_duplicate(existing, fqdn, resolver) for existing in selected_related):
            continue
        selected_related.append(fqdn)
        if len(selected_related) >= config.max_related:
            break

    probability_scores = _softmax_scores(primary_scores, temperature=config.score_temperature)
    top1_prob = probability_scores.get(selected_primary, 0.0) if selected_primary else 0.0
    second_prob = sorted(probability_scores.values(), reverse=True)[1] if len(probability_scores) > 1 else 0.0
    llm_confidence = _safe_float(llm_decision.get("confidence", 0.0))
    margin = _clip(top1_prob - second_prob)
    margin_support = _clip(margin / max(config.margin_threshold, 1e-6))
    primary_llm_row = llm_map.get(selected_primary, {}) if selected_primary else {}
    evidence_support = _llm_evidence_support(primary_llm_row)
    agreement_support = _agreement_score(selected_primary, deterministic_primary, resolver)
    confidence = _clip(
        0.55 * top1_prob
        + 0.20 * margin_support
        + 0.15 * evidence_support
        + 0.10 * agreement_support
    )

    routing_top_k: list[dict[str, Any]] = []
    for fqdn in ranked_primary[: config.routing_top_k]:
        row = next(item for item in candidate_rows if item["fqdn"] == fqdn)
        if fqdn == selected_primary:
            role = "primary"
        elif fqdn in selected_related:
            role = "related"
        elif _is_chain_duplicate(selected_primary, fqdn, resolver):
            role = "fallback"
        else:
            role = "distractor"
        routing_top_k.append(
            {
                "fqdn": fqdn,
                "score_a": primary_scores[fqdn],
                "score_related": related_scores[fqdn],
                "role": role,
                "node_kind": row.get("node_kind"),
                "l1": row.get("l1"),
                "l2": row.get("l2"),
                "segment": row.get("segment"),
            }
        )

    constraint_reasons: list[str] = []
    if not selected_primary or selected_primary not in candidate_set:
        constraint_reasons.append("invalid_primary_after_calibration")
    elif not validate_fqdn(selected_primary):
        constraint_reasons.append("invalid_primary_fqdn")
    invalid_related = [fqdn for fqdn in selected_related if fqdn not in candidate_set]
    if invalid_related:
        constraint_reasons.append("related_not_in_candidates")
    constraint_reasons.extend(llm_issues)

    confusion_sources = set(snapshot.get("confusion_sources", []))
    escalation_reasons: list[str] = []
    has_llm_relief = (
        llm_confidence >= config.llm_confidence_relief_threshold
        and evidence_support >= 0.75
        and agreement_support >= 0.6
    )
    if confidence < config.confidence_threshold and not has_llm_relief:
        escalation_reasons.append("low_confidence")
    if margin < config.margin_threshold:
        escalation_reasons.append("small_margin")
    if llm_decision.get("escalate_to_stage_b"):
        escalation_reasons.append("llm_requested")
    escalation_reasons.extend(llm_decision.get("escalation_reasons", []))
    if _is_high_risk_route(selected_primary, resolver):
        if margin < config.high_risk_margin_threshold or "C4_governance_fallback" in confusion_sources:
            escalation_reasons.append("high_risk")
    if (selection_signals.get("has_multi_intent_signal") or llm_decision.get("secondary_intents")) and not selected_related:
        escalation_reasons.append("multi_intent_conflict")
    escalation_reasons.extend(constraint_reasons)

    return {
        "selected_primary_fqdn": selected_primary,
        "selected_related_fqdns": selected_related,
        "confidence": round(confidence, 6),
        "margin": round(margin, 6),
        "routing_top_k": routing_top_k,
        "constraint_check": {"pass": not constraint_reasons, "reasons": sorted(set(constraint_reasons))},
        "escalate_to_stage_b": bool(escalation_reasons),
        "escalation_reasons": sorted(set(escalation_reasons)),
        "candidate_scores": candidate_scores,
        "score_breakdown": {
            "primary_fqdn": selected_primary,
            "primary_probability": round(top1_prob, 6),
            "primary_margin_probability": round(margin, 6),
            "llm_confidence": round(llm_confidence, 6),
            "llm_evidence_support": round(evidence_support, 6),
            "agreement_support": round(agreement_support, 6),
            "base_stage_a_primary": base_stage_a.get("selected_primary_fqdn"),
        },
        "llm_provider": client.provider,
        "llm_model": client.model,
        "llm_decision": llm_decision,
        "llm_raw_response": raw_response,
    }


def analyze_stage_a_llm(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    client: StageALLMClient,
    config: StageALLMConfig | None = None,
) -> dict[str, Any]:
    config = config or StageALLMConfig()
    base_stage_a = analyze_stage_a(
        sample=sample,
        snapshot=snapshot,
        resolver=resolver,
        config=StageACleanConfig(stage_a_version=config.base_stage_a_version),
    )
    packet = build_decision_packet(sample=sample, snapshot=snapshot, resolver=resolver, base_stage_a=base_stage_a, config=config)
    llm_raw = ""
    llm_issues: list[str] = []
    try:
        llm_raw_decision, llm_raw = client.adjudicate(packet, config)
        llm_decision, llm_issues = _sanitize_llm_decision(
            llm_raw_decision,
            [row["fqdn"] for row in snapshot.get("fqdn_candidates", [])],
        )
    except Exception as exc:  # pragma: no cover - exercised in integration/dry runs
        llm_issues = [f"llm_error:{type(exc).__name__}"]
        llm_decision = {
            "selected_primary_fqdn": None,
            "selected_related_fqdns": [],
            "candidate_judgements": [],
            "confidence": 0.0,
            "escalate_to_stage_b": True,
            "escalation_reasons": ["llm_error"],
            "notes": [str(exc)],
        }
        llm_raw = str(exc)

    stage_a = calibrate_llm_decision(
        sample=sample,
        snapshot=snapshot,
        resolver=resolver,
        base_stage_a=base_stage_a,
        llm_decision=llm_decision,
        llm_issues=llm_issues,
        raw_response=llm_raw,
        client=client,
        config=config,
    )
    stage_a["decision_packet"] = packet
    stage_a["query_packet"] = base_stage_a.get("query_packet", {})
    stage_a["base_stage_a_version"] = config.base_stage_a_version
    stage_a["prompt_version"] = config.prompt_version
    stage_a["decision_mode"] = "single_agent_llm_v1"
    return stage_a


def build_routing_run_trace(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    client: StageALLMClient,
    config: StageALLMConfig | None = None,
) -> dict[str, Any]:
    config = config or StageALLMConfig()
    stage_a = analyze_stage_a_llm(sample=sample, snapshot=snapshot, resolver=resolver, client=client, config=config)
    trace = {
        "run_id": f"run_{config.stage_a_version}_{sample['id']}_{uuid.uuid4().hex[:8]}",
        "sample_id": sample["id"],
        "namespace_version": snapshot["namespace_version"],
        "stage_r_version": snapshot["stage_r_version"],
        "stage_a_version": config.stage_a_version,
        "stage_r": snapshot,
        "stage_a": stage_a,
    }
    return attach_stage_a_final_fields(trace, source="stage_a_llm")
