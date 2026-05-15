from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from .namespace import NamespaceResolver, RoutingNode, validate_fqdn
from .stage_a_clean import StageACleanConfig, analyze_stage_a
from .stage_a_llm import _minmax_norm, _normalize_specificity_judgement


@dataclass(frozen=True)
class StageAMultiIntentConfig:
    stage_a_version: str = "stage_a_multi_intent_v2_20260426"
    prompt_version: str = "stage_a_multi_intent_prompt_v2_20260426"
    base_stage_a_version: str = StageACleanConfig().stage_a_version
    prompt_candidate_limit: int = 10
    max_selected: int = 5
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2200
    confidence_threshold: float = 0.62
    boundary_margin_threshold: float = 0.08
    expanded_boundary_margin_threshold: float = 0.14
    minmax_spread_floor: float = 0.5
    selection_score_threshold: float = 0.52
    llm_selected_rescue_threshold: float = 0.45
    deterministic_rescue_threshold: float = 0.70
    high_risk_confidence_threshold: float = 0.70
    gate_mode: str = "expanded"

    @property
    def base_set_weight(self) -> float:
        return 0.45

    @property
    def stage_r_weight(self) -> float:
        return 0.15

    @property
    def llm_task_weight(self) -> float:
        return 0.18

    @property
    def llm_select_weight(self) -> float:
        return 0.17

    @property
    def llm_selected_bonus(self) -> float:
        return 0.05


class StageAMultiIntentClient(Protocol):
    provider: str
    model: str

    def select_intents(self, packet: dict[str, Any], config: StageAMultiIntentConfig) -> tuple[dict[str, Any], str]:
        raise NotImplementedError


class OpenAICompatibleStageAMultiIntentClient:
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

    def select_intents(self, packet: dict[str, Any], config: StageAMultiIntentConfig) -> tuple[dict[str, Any], str]:
        request_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(packet)},
            ],
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
        return _load_json_object(content), content


def make_multi_intent_llm_client(provider: str, model: str | None = None) -> StageAMultiIntentClient:
    provider = provider.lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set")
        return OpenAICompatibleStageAMultiIntentClient(
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
        return OpenAICompatibleStageAMultiIntentClient(
            provider="openai",
            model=model or "gpt-5.4",
            api_key=api_key,
            timeout=60.0,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _system_prompt() -> str:
    return (
        "你是 AgentDNS 多意图集合路由器。"
        "你的任务不是选一个 primary，也不是区分 primary/related，而是从候选集合中选出 query 明确请求的所有目标 FQDN。"
        "你只能选择 candidates 中的 fqdn，不能发明新 fqdn。"
        "输出必须是单个 JSON 对象，不能附带散文解释。"
    )


def _user_prompt(packet: dict[str, Any]) -> str:
    return (
        "请基于下面的 multi-intent decision packet 进行集合路由。\n"
        "要求：\n"
        "1. selected_fqdns 是最终集合，必须全部来自 candidates。\n"
        "2. 这里不要求区分 primary/related，但必须像原 Stage A 一样逐候选裁决，并给出可校准的打分。\n"
        "3. 单意图 query 应返回长度为 1 的 selected_fqdns；多意图 query 应覆盖所有明确独立意图。\n"
        "4. 不要因为同一场景泛相关就多选；每个 select 必须能在 query 中找到支持短语。\n"
        "5. 父子或同链路候选重复时，优先选择能直接承接用户需求的更合适粒度。\n"
        "6. candidate_decisions 必须覆盖所有 candidates，每项包含 fqdn, decision, task_fit, select_fit, "
        "specificity_judgement, risk_mismatch, confidence, evidence_for, evidence_against。\n"
        "7. decision 只能取 select/drop；task_fit/select_fit/confidence 使用 0 到 1。\n"
        "8. specificity_judgement 只能取 too_coarse/fit/too_specific。\n"
        "9. 如果候选不足、语义不确定或集合边界不确定，设置 escalate_to_stage_b=true。\n"
        "10. 输出字段：intent_summary, selected_fqdns, candidate_decisions, confidence, "
        "escalate_to_stage_b, escalation_reasons, uncertainty_points。\n\n"
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
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _candidate_desc(node: RoutingNode | None) -> str:
    return node.desc if node else ""


def _candidate_aliases(node: RoutingNode | None, limit: int = 6) -> list[str]:
    return list(node.aliases[:limit]) if node else []


def _candidate_rows(
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageAMultiIntentConfig,
    base_stage_a: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates = sorted(snapshot.get("fqdn_candidates", []), key=lambda row: row.get("score_r", 0.0), reverse=True)
    base_map = {row["fqdn"]: row for row in base_stage_a.get("candidate_scores", [])}
    rows: list[dict[str, Any]] = []
    for row in candidates[: config.prompt_candidate_limit]:
        node = resolver.get_node(row["fqdn"])
        base_row = base_map.get(row["fqdn"], {})
        evidence = base_row.get("evidence_for", {})
        rows.append(
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
                "aliases": _candidate_aliases(node),
                "source": list(row.get("source", [])),
                "matched_phrases": row.get("matched_phrases", {}),
                "base_score_a": round(float(base_row.get("score_a", 0.0)), 6),
                "base_score_related": round(float(base_row.get("score_related", 0.0)), 6),
                "base_role": next(
                    (
                        item.get("role")
                        for item in base_stage_a.get("routing_top_k", [])
                        if item.get("fqdn") == row["fqdn"]
                    ),
                    None,
                ),
                "base_evidence": {
                    "primary_hits": evidence.get("primary_hits", []),
                    "secondary_hits": evidence.get("secondary_hits", []),
                    "scene_hits": evidence.get("scene_hits", []),
                    "matched_phrases": evidence.get("matched_phrases", []),
                },
            }
        )
    return rows


def build_decision_packet(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    base_stage_a: dict[str, Any],
    config: StageAMultiIntentConfig | None = None,
) -> dict[str, Any]:
    config = config or StageAMultiIntentConfig()
    candidates = _candidate_rows(snapshot, resolver, config, base_stage_a)
    return {
        "sample_id": sample["id"],
        "namespace_version": snapshot.get("namespace_version"),
        "stage_r_version": snapshot.get("stage_r_version"),
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "rules": [
            "selected_fqdns must be a set-valued prediction over candidates",
            "do not force a primary/related split in the final output",
            "select all explicitly requested intents and only explicitly requested intents",
            "single-intent queries should normally have exactly one selected fqdn",
            "use base_score_a/base_score_related as algorithmic evidence, not as labels",
        ],
        "soft_hints": {
            "selection_signals": snapshot.get("semantic_parse", {}).get("selection_signals", {}),
            "recall_sources": snapshot.get("recall_sources", []),
            "base_stage_a_selected_primary": base_stage_a.get("selected_primary_fqdn"),
            "base_stage_a_selected_related": base_stage_a.get("selected_related_fqdns", []),
            "base_stage_a_confidence": base_stage_a.get("confidence"),
            "base_stage_a_margin": base_stage_a.get("margin"),
            "base_stage_a_escalation_reasons": base_stage_a.get("escalation_reasons", []),
        },
        "candidates": candidates,
    }


def _sanitize_candidate_decisions(raw: Any, candidate_set: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _as_list(raw):
        if not isinstance(item, dict):
            continue
        fqdn = item.get("fqdn")
        if fqdn not in candidate_set or fqdn in seen:
            continue
        decision = str(item.get("decision", "drop")).strip().lower()
        if decision not in {"select", "drop"}:
            decision = "select" if decision in {"keep", "add"} else "drop"
        specificity_judgement, _specificity_issue = _normalize_specificity_judgement(
            item.get("specificity_judgement", "fit")
        )
        seen.add(fqdn)
        rows.append(
            {
                "fqdn": fqdn,
                "decision": decision,
                "task_fit": _safe_float(item.get("task_fit", 0.0)),
                "select_fit": _safe_float(item.get("select_fit", item.get("related_fit", 0.0))),
                "specificity_judgement": specificity_judgement,
                "risk_mismatch": bool(item.get("risk_mismatch", False)),
                "confidence": _safe_float(item.get("confidence", 0.0)),
                "evidence_for": [str(value)[:160] for value in _as_list(item.get("evidence_for"))[:4]],
                "evidence_against": [str(value)[:160] for value in _as_list(item.get("evidence_against"))[:4]],
            }
        )
    for fqdn in sorted(candidate_set - seen):
        rows.append(
            {
                "fqdn": fqdn,
                "decision": "drop",
                "task_fit": 0.0,
                "select_fit": 0.0,
                "specificity_judgement": "fit",
                "risk_mismatch": False,
                "confidence": 0.0,
                "evidence_for": [],
                "evidence_against": [],
            }
        )
    return rows


def _sanitize_llm_decision(
    raw: dict[str, Any],
    candidate_fqdns: list[str],
    config: StageAMultiIntentConfig,
) -> tuple[dict[str, Any], list[str]]:
    candidate_set = set(candidate_fqdns)
    issues: list[str] = []
    selected: list[str] = []
    for fqdn in _as_list(raw.get("selected_fqdns")):
        if fqdn in candidate_set and validate_fqdn(fqdn):
            selected.append(fqdn)
        else:
            issues.append("selected_fqdn_not_in_candidates")
    selected = _dedupe_keep_order(selected)[: config.max_selected]
    if not selected and candidate_fqdns:
        selected = [candidate_fqdns[0]]
        issues.append("empty_selection_fallback_to_stage_r_top1")

    candidate_decisions = _sanitize_candidate_decisions(raw.get("candidate_decisions"), candidate_set)
    confidence = _safe_float(raw.get("confidence"), default=0.0)
    escalation_reasons = [str(value)[:80] for value in _as_list(raw.get("escalation_reasons"))]
    if confidence < config.confidence_threshold:
        escalation_reasons.append("low_confidence")
    escalation_reasons.extend(issues)
    return (
        {
            "intent_summary": str(raw.get("intent_summary", ""))[:500],
            "selected_fqdns": selected,
            "candidate_decisions": candidate_decisions,
            "confidence": round(confidence, 6),
            "escalate_to_stage_b": bool(raw.get("escalate_to_stage_b")) or bool(escalation_reasons),
            "escalation_reasons": sorted(set(escalation_reasons)),
            "uncertainty_points": [str(value)[:120] for value in _as_list(raw.get("uncertainty_points"))[:8]],
        },
        sorted(set(issues)),
    )


def _base_selected_set(base_stage_a: dict[str, Any]) -> list[str]:
    return _dedupe_keep_order(
        [
            base_stage_a.get("selected_primary_fqdn"),
            *list(base_stage_a.get("selected_related_fqdns", [])),
        ]
    )


def _chain_members(fqdn: str, resolver: NamespaceResolver) -> set[str]:
    members = {fqdn}
    members.update(resolver.fallback_chain(fqdn))
    node = resolver.get_node(fqdn)
    if node and node.parent_fqdn:
        members.add(node.parent_fqdn)
    return members


def _is_chain_duplicate(left: str, right: str, resolver: NamespaceResolver) -> bool:
    if left == right:
        return True
    return right in _chain_members(left, resolver) or left in _chain_members(right, resolver)


def _same_l1(left: str, right: str, resolver: NamespaceResolver) -> bool:
    left_node = resolver.get_node(left)
    right_node = resolver.get_node(right)
    return bool(left_node and right_node and left_node.l1 == right_node.l1)


def _specificity_adjustment(judgement: str) -> float:
    if judgement == "too_coarse":
        return -0.04
    if judgement == "too_specific":
        return -0.06
    return 0.03


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _prune_chain_duplicates(selected: list[str], scores: dict[str, float], resolver: NamespaceResolver) -> list[str]:
    ordered = sorted(_dedupe_keep_order(selected), key=lambda fqdn: scores.get(fqdn, 0.0), reverse=True)
    pruned: list[str] = []
    for fqdn in ordered:
        if any(_is_chain_duplicate(fqdn, existing, resolver) for existing in pruned):
            continue
        pruned.append(fqdn)
    return pruned


def calibrate_multi_intent_decision(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    base_stage_a: dict[str, Any],
    llm_decision: dict[str, Any],
    llm_issues: list[str],
    raw_response: str,
    client: StageAMultiIntentClient,
    config: StageAMultiIntentConfig | None = None,
) -> dict[str, Any]:
    config = config or StageAMultiIntentConfig()
    packet = build_decision_packet(sample=sample, snapshot=snapshot, resolver=resolver, base_stage_a=base_stage_a, config=config)
    candidate_rows = packet["candidates"]
    candidate_fqdns = [row["fqdn"] for row in candidate_rows]
    candidate_set = set(candidate_fqdns)
    base_map = {row["fqdn"]: row for row in base_stage_a.get("candidate_scores", [])}
    decision_map = {row["fqdn"]: row for row in llm_decision.get("candidate_decisions", [])}
    llm_selected = set(llm_decision.get("selected_fqdns", []))

    det_primary_scores = {fqdn: float(base_map.get(fqdn, {}).get("score_a", 0.0)) for fqdn in candidate_fqdns}
    det_related_scores = {fqdn: float(base_map.get(fqdn, {}).get("score_related", 0.0)) for fqdn in candidate_fqdns}
    det_primary_norm = _minmax_norm(det_primary_scores, spread_floor=config.minmax_spread_floor)
    det_related_norm = _minmax_norm(det_related_scores, spread_floor=config.minmax_spread_floor)

    max_stage_r = max([float(row.get("score_r", 0.0)) for row in candidate_rows] or [1.0])
    set_scores: dict[str, float] = {}
    candidate_scores: list[dict[str, Any]] = []
    for row in candidate_rows:
        fqdn = row["fqdn"]
        decision = decision_map.get(fqdn, {})
        specificity = decision.get("specificity_judgement", "fit")
        det_set_norm = max(det_primary_norm.get(fqdn, 0.0), det_related_norm.get(fqdn, 0.0))
        stage_r_norm = _clip(float(row.get("score_r", 0.0)) / max(max_stage_r, 1e-6))
        task_fit = _safe_float(decision.get("task_fit", 0.0))
        select_fit = _safe_float(decision.get("select_fit", 0.0))
        selected_bonus = config.llm_selected_bonus if fqdn in llm_selected or decision.get("decision") == "select" else 0.0
        risk_penalty = 0.08 if decision.get("risk_mismatch") else 0.0
        score = (
            config.base_set_weight * det_set_norm
            + config.stage_r_weight * stage_r_norm
            + config.llm_task_weight * task_fit
            + config.llm_select_weight * select_fit
            + selected_bonus
            + _specificity_adjustment(specificity)
            - risk_penalty
        )
        set_scores[fqdn] = round(score, 6)
        candidate_scores.append(
            {
                "fqdn": fqdn,
                "score_set": round(score, 6),
                "decision": decision.get("decision", "drop"),
                "node_kind": row.get("node_kind"),
                "l1": row.get("l1"),
                "l2": row.get("l2"),
                "segment": row.get("segment"),
                "score_breakdown": {
                    "det_primary_norm": round(det_primary_norm.get(fqdn, 0.0), 6),
                    "det_related_norm": round(det_related_norm.get(fqdn, 0.0), 6),
                    "det_set_norm": round(det_set_norm, 6),
                    "stage_r_norm": round(stage_r_norm, 6),
                    "llm_task_fit": round(task_fit, 6),
                    "llm_select_fit": round(select_fit, 6),
                    "llm_selected_bonus": round(selected_bonus, 6),
                    "specificity_adjustment": round(_specificity_adjustment(specificity), 6),
                    "risk_penalty": round(risk_penalty, 6),
                },
                "evidence_for": list(decision.get("evidence_for", []))[:4],
                "evidence_against": list(decision.get("evidence_against", []))[:4],
            }
        )

    selected: list[str] = []
    for fqdn in candidate_fqdns:
        decision = decision_map.get(fqdn, {})
        score = set_scores.get(fqdn, 0.0)
        det_set_norm = max(det_primary_norm.get(fqdn, 0.0), det_related_norm.get(fqdn, 0.0))
        if fqdn in llm_selected and score >= config.llm_selected_rescue_threshold:
            selected.append(fqdn)
        elif decision.get("decision") == "select" and score >= config.selection_score_threshold:
            selected.append(fqdn)
        elif det_set_norm >= config.deterministic_rescue_threshold and _safe_float(decision.get("task_fit", 0.0)) >= 0.55:
            selected.append(fqdn)

    if not selected and candidate_fqdns:
        selected = [max(candidate_fqdns, key=lambda fqdn: set_scores.get(fqdn, 0.0))]
    selected = _prune_chain_duplicates(selected, set_scores, resolver)[: config.max_selected]

    selected_scores = [set_scores[fqdn] for fqdn in selected]
    unselected = [fqdn for fqdn in candidate_fqdns if fqdn not in set(selected)]
    best_unselected = max((set_scores[fqdn] for fqdn in unselected), default=0.0)
    min_selected = min(selected_scores) if selected_scores else 0.0
    boundary_margin = round(min_selected - best_unselected, 6)
    boundary_threshold = (
        config.expanded_boundary_margin_threshold
        if config.gate_mode == "expanded"
        else config.boundary_margin_threshold
    )

    selected_decisions = [decision_map.get(fqdn, {}) for fqdn in selected]
    evidence_support = (
        sum(
            _clip(
                0.50 * _safe_float(row.get("task_fit", 0.0))
                + 0.35 * _safe_float(row.get("select_fit", 0.0))
                + 0.15 * _safe_float(row.get("confidence", 0.0))
            )
            for row in selected_decisions
        )
        / len(selected_decisions)
        if selected_decisions
        else 0.0
    )
    agreement_support = _jaccard(set(selected), set(_base_selected_set(base_stage_a)))
    boundary_support = _clip(boundary_margin / max(boundary_threshold, 1e-6))
    mean_selected_score = sum(selected_scores) / len(selected_scores) if selected_scores else 0.0
    confidence = _clip(
        0.35 * mean_selected_score
        + 0.25 * boundary_support
        + 0.25 * evidence_support
        + 0.15 * agreement_support
    )

    escalation_reasons: list[str] = []
    selection_signals = snapshot.get("semantic_parse", {}).get("selection_signals", {})
    if confidence < config.confidence_threshold:
        escalation_reasons.append("low_confidence")
    if boundary_margin < boundary_threshold:
        escalation_reasons.append("small_set_boundary_margin")
    if llm_decision.get("escalate_to_stage_b"):
        escalation_reasons.append("llm_requested")
    if selection_signals.get("has_multi_intent_signal") and len(selected) < 2:
        escalation_reasons.append("multi_intent_underselected")
    if any((resolver.get_node(fqdn) and resolver.get_node(fqdn).is_stage_a_high_risk) for fqdn in selected) and confidence < config.high_risk_confidence_threshold:
        escalation_reasons.append("high_risk_low_confidence")
    if len(selected) >= config.max_selected and unselected and best_unselected >= min_selected - 0.02:
        escalation_reasons.append("selection_at_cap_with_close_candidate")
    for reason in base_stage_a.get("escalation_reasons", []):
        escalation_reasons.append(f"base_stage_a:{reason}")
    escalation_reasons.extend(llm_decision.get("escalation_reasons", []))
    escalation_reasons.extend(llm_issues)

    routing_top_k = []
    for fqdn in sorted(candidate_fqdns, key=lambda item: set_scores.get(item, 0.0), reverse=True):
        row = next(item for item in candidate_rows if item["fqdn"] == fqdn)
        routing_top_k.append(
            {
                "fqdn": fqdn,
                "score_set": set_scores[fqdn],
                "role": "selected" if fqdn in selected else "distractor",
                "node_kind": row.get("node_kind"),
                "l1": row.get("l1"),
                "l2": row.get("l2"),
                "segment": row.get("segment"),
            }
        )

    return {
        "selected_fqdns": selected,
        "confidence": round(confidence, 6),
        "margin": boundary_margin,
        "boundary_margin": boundary_margin,
        "review_boundary_threshold": boundary_threshold,
        "multi_intent_review_recommended": bool(escalation_reasons),
        "escalate_to_stage_b": bool(escalation_reasons),
        "escalation_reasons": sorted(set(str(reason)[:120] for reason in escalation_reasons if reason)),
        "constraint_check": {"pass": not llm_issues, "reasons": sorted(set(llm_issues))},
        "decision_packet": packet,
        "candidate_decisions": llm_decision["candidate_decisions"],
        "candidate_scores": candidate_scores,
        "routing_top_k": routing_top_k,
        "score_breakdown": {
            "mean_selected_score": round(mean_selected_score, 6),
            "min_selected_score": round(min_selected, 6),
            "best_unselected_score": round(best_unselected, 6),
            "boundary_support": round(boundary_support, 6),
            "llm_confidence": llm_decision.get("confidence"),
            "evidence_support": round(evidence_support, 6),
            "agreement_support": round(agreement_support, 6),
            "base_stage_a_selected": _base_selected_set(base_stage_a),
        },
        "intent_summary": llm_decision["intent_summary"],
        "uncertainty_points": llm_decision["uncertainty_points"],
        "llm_provider": client.provider,
        "llm_model": client.model,
        "llm_decision": llm_decision,
        "llm_raw_response": raw_response,
        "prompt_version": config.prompt_version,
        "base_stage_a_version": config.base_stage_a_version,
        "decision_mode": "multi_intent_set_llm_calibrated_v2",
    }


def analyze_stage_a_multi_intent(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    client: StageAMultiIntentClient,
    config: StageAMultiIntentConfig | None = None,
) -> dict[str, Any]:
    config = config or StageAMultiIntentConfig()
    base_stage_a = analyze_stage_a(
        sample=sample,
        snapshot=snapshot,
        resolver=resolver,
        config=StageACleanConfig(stage_a_version=config.base_stage_a_version),
    )
    packet = build_decision_packet(
        sample=sample,
        snapshot=snapshot,
        resolver=resolver,
        base_stage_a=base_stage_a,
        config=config,
    )
    candidate_fqdns = [row["fqdn"] for row in packet["candidates"]]
    raw_response = ""
    try:
        raw_decision, raw_response = client.select_intents(packet, config)
        decision, issues = _sanitize_llm_decision(raw_decision, candidate_fqdns, config)
    except Exception as exc:  # pragma: no cover - exercised in integration runs
        fallback = candidate_fqdns[:1]
        decision = {
            "intent_summary": "",
            "selected_fqdns": fallback,
            "candidate_decisions": _sanitize_candidate_decisions([], set(candidate_fqdns)),
            "confidence": 0.0,
            "escalate_to_stage_b": True,
            "escalation_reasons": [f"llm_error:{type(exc).__name__}"],
            "uncertainty_points": ["stage_a_multi_intent_llm_error"],
        }
        issues = [f"llm_error:{type(exc).__name__}"]
        raw_response = str(exc)

    return calibrate_multi_intent_decision(
        sample=sample,
        snapshot=snapshot,
        resolver=resolver,
        base_stage_a=base_stage_a,
        llm_decision=decision,
        llm_issues=issues,
        raw_response=raw_response,
        client=client,
        config=config,
    )


def attach_stage_a_multi_final_fields(trace: dict[str, Any]) -> dict[str, Any]:
    selected = list(trace["stage_a"].get("selected_fqdns", []))
    trace["entered_stage_b"] = False
    trace["final_selected_fqdns"] = selected
    trace["final_decision_source"] = "stage_a_multi_intent"
    # Compatibility fields keep older table code from failing, but the multi-intent metric uses final_selected_fqdns.
    trace["final_primary_fqdn"] = selected[0] if selected else None
    trace["final_related_fqdns"] = selected[1:]
    return trace


def build_routing_run_trace(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    client: StageAMultiIntentClient,
    config: StageAMultiIntentConfig | None = None,
) -> dict[str, Any]:
    config = config or StageAMultiIntentConfig()
    stage_a = analyze_stage_a_multi_intent(sample=sample, snapshot=snapshot, resolver=resolver, client=client, config=config)
    trace = {
        "run_id": f"run_{config.stage_a_version}_{sample['id']}_{uuid.uuid4().hex[:8]}",
        "sample_id": sample["id"],
        "namespace_version": snapshot["namespace_version"],
        "stage_r_version": snapshot["stage_r_version"],
        "stage_a_version": config.stage_a_version,
        "stage_r": snapshot,
        "stage_a": stage_a,
    }
    return attach_stage_a_multi_final_fields(trace)
