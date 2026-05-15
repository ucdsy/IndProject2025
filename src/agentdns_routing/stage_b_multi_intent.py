from __future__ import annotations

import copy
import json
import os
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from .namespace import NamespaceResolver, validate_fqdn


ROLE_NAMES = ("DomainExpert", "GovernanceRisk", "HierarchyResolver", "UserPreference")


@dataclass(frozen=True)
class StageBMultiIntentConfig:
    stage_b_version: str = "stage_b_multi_intent_v2_20260426_hetero"
    prompt_version: str = "stage_b_multi_intent_prompt_v2_20260426"
    collaboration_mode: str = "heterogeneous"
    gate_mode: str = "expanded"
    prompt_candidate_limit: int = 10
    max_selected: int = 5
    support_vote_threshold: int = 2
    stage_a_keep_vote_threshold: int = 1
    confidence_threshold: float = 0.62
    boundary_margin_threshold: float = 0.08
    expanded_boundary_margin_threshold: float = 0.14
    keep_score_floor: float = 0.34
    add_score_threshold: float = 0.48
    round2_margin_threshold: float = 0.08
    max_rounds: int = 2
    llm_max_tokens: int = 2200
    general_reviewer_temperature: float | None = 0.35
    domain_expert_temperature: float | None = 0.50
    governance_risk_temperature: float | None = 0.20
    hierarchy_resolver_temperature: float | None = 0.35
    user_preference_temperature: float | None = 0.70
    parallel_role_calls: bool = True
    max_parallel_roles: int = 4

    @property
    def stage_a_prior_weight(self) -> float:
        return 0.34

    @property
    def support_vote_weight(self) -> float:
        return 0.30

    @property
    def support_confidence_weight(self) -> float:
        return 0.12

    @property
    def stage_a_selected_bonus(self) -> float:
        return 0.10

    @property
    def stage_r_weight(self) -> float:
        return 0.08

    @property
    def remove_vote_penalty(self) -> float:
        return 0.24


class StageBMultiIntentClient(Protocol):
    provider: str
    model: str

    def review_set(
        self,
        role_name: str,
        packet: dict[str, Any],
        config: StageBMultiIntentConfig,
    ) -> tuple[dict[str, Any], str]:
        raise NotImplementedError


class OpenAICompatibleStageBMultiIntentClient:
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

    def review_set(
        self,
        role_name: str,
        packet: dict[str, Any],
        config: StageBMultiIntentConfig,
    ) -> tuple[dict[str, Any], str]:
        request_kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _system_prompt(role_name)},
                {"role": "user", "content": _user_prompt(packet)},
            ],
            "temperature": _role_temperature(role_name, config),
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


def make_stage_b_multi_intent_llm_client(provider: str, model: str | None = None) -> StageBMultiIntentClient:
    provider = provider.lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set")
        return OpenAICompatibleStageBMultiIntentClient(
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
        return OpenAICompatibleStageBMultiIntentClient(
            provider="openai",
            model=model or "gpt-5.4",
            api_key=api_key,
            timeout=60.0,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _role_temperature(role_name: str, config: StageBMultiIntentConfig) -> float | None:
    if config.collaboration_mode in {"single", "homogeneous"}:
        return config.general_reviewer_temperature
    return {
        "DomainExpert": config.domain_expert_temperature,
        "GovernanceRisk": config.governance_risk_temperature,
        "HierarchyResolver": config.hierarchy_resolver_temperature,
        "UserPreference": config.user_preference_temperature,
    }.get(role_name, config.general_reviewer_temperature)


def _role_names(config: StageBMultiIntentConfig) -> tuple[str, ...]:
    if config.collaboration_mode == "single":
        return ("GeneralReviewer",)
    if config.collaboration_mode == "homogeneous":
        return ("GeneralReviewer", "GeneralReviewer", "GeneralReviewer", "GeneralReviewer")
    return ROLE_NAMES


def _system_prompt(role_name: str) -> str:
    role_desc = {
        "DomainExpert": "关注候选是否直接匹配用户表达的任务语义。",
        "GovernanceRisk": "关注高风险、治理、安全、合规场景中是否过选或漏选。",
        "HierarchyResolver": "关注父子层级、同链路重复和粒度是否合适。",
        "UserPreference": "关注用户原始 query 中所有明确需求是否被覆盖。",
        "GeneralReviewer": "综合判断候选集合是否完整且不过选。",
    }.get(role_name, "综合判断候选集合是否完整且不过选。")
    return (
        f"你是 AgentDNS 多意图集合路由的 {role_name} reviewer。{role_desc}"
        "你沿用 Stage B 共识评审职责，但目标是审查 selected_fqdns 集合，而不是只审查单个 primary。"
        "你只能选择 candidates 中的 fqdn，不能发明新 fqdn。"
        "输出必须是单个 JSON 对象。"
    )


def _user_prompt(packet: dict[str, Any]) -> str:
    return (
        "请审查 Stage A 的多意图集合路由结果，并给出你的集合建议。"
        "Stage A 已经给出校准后的 stage_a_score_set、逐候选裁决和边界信息；你需要在这些信息基础上做独立复核。\n"
        "要求：\n"
        "1. proposed_selected_fqdns 必须全部来自 candidates。\n"
        "2. proposed_selected_fqdns 表示你认为 query 明确请求的完整 FQDN 集合，不区分 primary/related。\n"
        "3. keep_fqdns 只能来自 stage_a_selected_fqdns；add_fqdns 是你认为应补充的候选；remove_fqdns 是你认为应移除的 Stage A 候选。\n"
        "4. candidate_decisions 必须覆盖所有 candidates，每项包含 fqdn, action, confidence, evidence。\n"
        "5. action 只能取 keep/add/remove/drop。\n"
        "6. 不要因为泛相关而 add；必须有 query 原文支持短语或明确上下文支持。\n"
        "7. 如果候选与已选候选属于父子或同链路重复，保留最能直接承接用户需求的粒度。\n"
        "8. 输出字段：proposed_selected_fqdns, keep_fqdns, add_fqdns, remove_fqdns, confidence, rationale, candidate_decisions。\n\n"
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


def _safe_unbounded_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def _prune_chain_duplicates(selected: list[str], score_map: dict[str, float], resolver: NamespaceResolver) -> list[str]:
    ordered = sorted(_dedupe_keep_order(selected), key=lambda fqdn: score_map.get(fqdn, 0.0), reverse=True)
    pruned: list[str] = []
    for fqdn in ordered:
        if any(_is_chain_duplicate(fqdn, existing, resolver) for existing in pruned):
            continue
        pruned.append(fqdn)
    return pruned


def _candidate_rows(trace: dict[str, Any], resolver: NamespaceResolver, config: StageBMultiIntentConfig) -> list[dict[str, Any]]:
    candidates = sorted(
        trace.get("stage_r", {}).get("fqdn_candidates", []),
        key=lambda row: row.get("score_r", 0.0),
        reverse=True,
    )
    stage_a = trace.get("stage_a") or {}
    stage_a_scores = {row.get("fqdn"): row for row in stage_a.get("candidate_scores", []) if isinstance(row, dict)}
    stage_a_decisions = {row.get("fqdn"): row for row in stage_a.get("candidate_decisions", []) if isinstance(row, dict)}
    stage_a_roles = {row.get("fqdn"): row.get("role") for row in stage_a.get("routing_top_k", []) if isinstance(row, dict)}
    stage_a_selected = set(_stage_a_selected(trace))
    rows: list[dict[str, Any]] = []
    for row in candidates[: config.prompt_candidate_limit]:
        node = resolver.get_node(row["fqdn"])
        score_row = stage_a_scores.get(row["fqdn"], {})
        decision_row = stage_a_decisions.get(row["fqdn"], {})
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
                "desc": node.desc if node else "",
                "aliases": list(node.aliases[:6]) if node else [],
                "matched_phrases": row.get("matched_phrases", {}),
                "stage_a_selected": row["fqdn"] in stage_a_selected,
                "stage_a_score_set": round(_safe_unbounded_float(score_row.get("score_set")), 6),
                "stage_a_role": stage_a_roles.get(row["fqdn"]),
                "stage_a_decision": decision_row.get("decision"),
                "stage_a_task_fit": round(_safe_float(decision_row.get("task_fit")), 6),
                "stage_a_select_fit": round(_safe_float(decision_row.get("select_fit")), 6),
                "stage_a_evidence_for": list(decision_row.get("evidence_for", []))[:4],
                "stage_a_evidence_against": list(decision_row.get("evidence_against", []))[:4],
                "stage_a_score_breakdown": score_row.get("score_breakdown", {}),
            }
        )
    return rows


def _stage_a_selected(trace: dict[str, Any]) -> list[str]:
    stage_a = trace.get("stage_a") or {}
    selected = stage_a.get("selected_fqdns")
    if isinstance(selected, list):
        return _dedupe_keep_order([fqdn for fqdn in selected if isinstance(fqdn, str)])
    final_selected = trace.get("final_selected_fqdns")
    if isinstance(final_selected, list):
        return _dedupe_keep_order([fqdn for fqdn in final_selected if isinstance(fqdn, str)])
    return _dedupe_keep_order([trace.get("final_primary_fqdn"), *list(trace.get("final_related_fqdns") or [])])


def build_review_packet(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBMultiIntentConfig | None = None,
) -> dict[str, Any]:
    config = config or StageBMultiIntentConfig()
    candidates = _candidate_rows(trace, resolver, config)
    return {
        "sample_id": sample["id"],
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "stage_a_version": trace.get("stage_a_version"),
        "stage_a_selected_fqdns": _stage_a_selected(trace),
        "stage_a_confidence": trace.get("stage_a", {}).get("confidence"),
        "stage_a_boundary_margin": trace.get("stage_a", {}).get("boundary_margin"),
        "stage_a_review_boundary_threshold": trace.get("stage_a", {}).get("review_boundary_threshold"),
        "stage_a_decision_mode": trace.get("stage_a", {}).get("decision_mode"),
        "stage_a_score_breakdown": trace.get("stage_a", {}).get("score_breakdown", {}),
        "stage_a_escalation_reasons": trace.get("stage_a", {}).get("escalation_reasons", []),
        "stage_a_intent_summary": trace.get("stage_a", {}).get("intent_summary"),
        "stage_a_candidate_decisions": trace.get("stage_a", {}).get("candidate_decisions", []),
        "review_rules": [
            "review the set-valued Stage A output, not a single primary",
            "use stage_a_score_set as calibrated algorithmic prior, not as a label",
            "keep Stage A selections unless there is clear semantic or hierarchy evidence to remove",
            "add a candidate only when the original query explicitly supports that independent intent",
            "avoid parent-child duplicates and same-chain duplicates in the final set",
        ],
        "gate_mode": config.gate_mode,
        "candidates": candidates,
    }


def _sanitize_vote(
    role_name: str,
    raw: dict[str, Any],
    candidate_fqdns: list[str],
    stage_a_selected: list[str],
) -> tuple[dict[str, Any], list[str]]:
    candidate_set = set(candidate_fqdns)
    stage_a_set = set(stage_a_selected)
    issues: list[str] = []

    def clean(values: Any, *, require_stage_a: bool = False) -> list[str]:
        cleaned: list[str] = []
        for fqdn in _as_list(values):
            if fqdn not in candidate_set or not validate_fqdn(fqdn):
                issues.append("vote_fqdn_not_in_candidates")
                continue
            if require_stage_a and fqdn not in stage_a_set:
                issues.append("keep_or_remove_not_in_stage_a_selection")
                continue
            cleaned.append(fqdn)
        return _dedupe_keep_order(cleaned)

    proposed = clean(raw.get("proposed_selected_fqdns"))
    keep = clean(raw.get("keep_fqdns"), require_stage_a=True)
    add = clean(raw.get("add_fqdns"))
    remove = clean(raw.get("remove_fqdns"), require_stage_a=True)
    if not proposed:
        proposed = _dedupe_keep_order([*keep, *add, *[fqdn for fqdn in stage_a_selected if fqdn not in remove]])
    decisions = []
    seen: set[str] = set()
    for item in _as_list(raw.get("candidate_decisions")):
        if not isinstance(item, dict):
            continue
        fqdn = item.get("fqdn")
        if fqdn not in candidate_set or fqdn in seen:
            continue
        action = str(item.get("action", "drop")).strip().lower()
        if action not in {"keep", "add", "remove", "drop"}:
            action = "drop"
        seen.add(fqdn)
        decisions.append(
            {
                "fqdn": fqdn,
                "action": action,
                "confidence": round(_safe_float(item.get("confidence")), 6),
                "evidence": [str(value)[:160] for value in _as_list(item.get("evidence"))[:4]],
            }
        )
    return (
        {
            "agent": role_name,
            "proposed_selected_fqdns": proposed,
            "keep_fqdns": keep,
            "add_fqdns": add,
            "remove_fqdns": remove,
            "confidence": round(_safe_float(raw.get("confidence")), 6),
            "rationale": str(raw.get("rationale", ""))[:500],
            "candidate_decisions": decisions,
        },
        sorted(set(issues)),
    )


def _collect_votes(
    role_names: tuple[str, ...],
    packet: dict[str, Any],
    client: StageBMultiIntentClient,
    config: StageBMultiIntentConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidate_fqdns = [row["fqdn"] for row in packet["candidates"]]
    stage_a_selected = list(packet.get("stage_a_selected_fqdns", []))

    def call_role(index_and_role: tuple[int, str]) -> tuple[int, dict[str, Any], list[str]]:
        index, role_name = index_and_role
        raw, raw_text = client.review_set(role_name, packet, config)
        vote, issues = _sanitize_vote(f"{role_name}_{index}" if role_name == "GeneralReviewer" else role_name, raw, candidate_fqdns, stage_a_selected)
        vote["raw_response"] = raw_text
        return index, vote, issues

    votes: list[dict[str, Any]] = []
    issues: list[str] = []
    indexed_roles = tuple(enumerate(role_names, start=1))
    if config.parallel_role_calls and len(indexed_roles) > 1:
        max_workers = max(1, min(config.max_parallel_roles, len(indexed_roles)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for _, vote, role_issues in sorted(executor.map(call_role, indexed_roles), key=lambda row: row[0]):
                votes.append(vote)
                issues.extend(role_issues)
    else:
        for item in indexed_roles:
            _, vote, role_issues = call_role(item)
            votes.append(vote)
            issues.extend(role_issues)
    return votes, sorted(set(issues))


def _candidate_action(vote: dict[str, Any], fqdn: str) -> str | None:
    for item in vote.get("candidate_decisions", []):
        if item.get("fqdn") == fqdn:
            return item.get("action")
    return None


def _aggregate_votes(
    packet: dict[str, Any],
    votes: list[dict[str, Any]],
    resolver: NamespaceResolver,
    config: StageBMultiIntentConfig,
) -> tuple[list[str], list[dict[str, Any]]]:
    candidate_order = [row["fqdn"] for row in packet["candidates"]]
    score_r = {row["fqdn"]: float(row.get("score_r", 0.0)) for row in packet["candidates"]}
    max_score_r = max(score_r.values() or [1.0])
    stage_a_score = {row["fqdn"]: _safe_unbounded_float(row.get("stage_a_score_set")) for row in packet["candidates"]}
    max_stage_a_score = max(stage_a_score.values() or [1.0])
    stage_a_selected = set(packet.get("stage_a_selected_fqdns", []))
    role_count = max(len(votes), 1)
    rows: list[dict[str, Any]] = []
    for fqdn in candidate_order:
        support_votes = []
        remove_votes = []
        action_histogram: Counter[str] = Counter()
        for vote in votes:
            action = _candidate_action(vote, fqdn)
            if action:
                action_histogram[action] += 1
            supports_candidate = (
                fqdn in set(vote.get("proposed_selected_fqdns", []))
                or fqdn in set(vote.get("keep_fqdns", []))
                or fqdn in set(vote.get("add_fqdns", []))
                or action in {"keep", "add"}
            )
            removes_candidate = fqdn in set(vote.get("remove_fqdns", [])) or action == "remove"
            if supports_candidate:
                support_votes.append(vote)
            if removes_candidate:
                remove_votes.append(vote)
        avg_conf = sum(float(vote.get("confidence", 0.0)) for vote in support_votes) / len(support_votes) if support_votes else 0.0
        support_count = len(support_votes)
        remove_count = len(remove_votes)
        stage_a_prior = fqdn in stage_a_selected
        support_ratio = support_count / role_count
        remove_ratio = remove_count / role_count
        stage_a_score_norm = _clip(stage_a_score.get(fqdn, 0.0) / max(max_stage_a_score, 1e-6))
        stage_r_norm = _clip(score_r.get(fqdn, 0.0) / max(max_score_r, 1e-6))
        score = (
            config.stage_a_prior_weight * stage_a_score_norm
            + config.support_vote_weight * support_ratio
            + config.support_confidence_weight * avg_conf
            + (config.stage_a_selected_bonus if stage_a_prior else 0.0)
            + config.stage_r_weight * stage_r_norm
            - config.remove_vote_penalty * remove_ratio
        )
        aggregate_score = _clip(score)
        selected = (
            stage_a_prior
            and remove_count < config.support_vote_threshold
            and (support_count >= config.stage_a_keep_vote_threshold or aggregate_score >= config.keep_score_floor)
        ) or (
            not stage_a_prior
            and support_count >= config.support_vote_threshold
            and aggregate_score >= config.add_score_threshold
        )
        rows.append(
            {
                "fqdn": fqdn,
                "selected": selected,
                "support_vote_count": support_count,
                "remove_vote_count": remove_count,
                "stage_a_selected": stage_a_prior,
                "stage_a_score_set": round(stage_a_score.get(fqdn, 0.0), 6),
                "stage_a_score_norm": round(stage_a_score_norm, 6),
                "avg_support_confidence": round(avg_conf, 6),
                "stage_r_score": round(score_r.get(fqdn, 0.0), 6),
                "stage_r_score_norm": round(stage_r_norm, 6),
                "aggregate_score": round(aggregate_score, 6),
                "action_histogram": dict(action_histogram),
                "supporting_agents": [vote["agent"] for vote in support_votes],
                "removing_agents": [vote["agent"] for vote in remove_votes],
            }
        )
    rows.sort(key=lambda row: (row["selected"], row["aggregate_score"], row["stage_r_score"]), reverse=True)
    selected = [row["fqdn"] for row in rows if row["selected"]][: config.max_selected]
    if not selected:
        selected = list(packet.get("stage_a_selected_fqdns", []))[: config.max_selected] or candidate_order[:1]
    score_map = {row["fqdn"]: row["aggregate_score"] for row in rows}
    selected = _prune_chain_duplicates(selected, score_map, resolver)[: config.max_selected]
    selected_set = set(selected)
    for row in rows:
        row["selected"] = row["fqdn"] in selected_set
    rows.sort(key=lambda row: (row["selected"], row["aggregate_score"], row["stage_r_score"]), reverse=True)
    return _dedupe_keep_order(selected), rows


def _stage_b_gate(
    trace: dict[str, Any],
    config: StageBMultiIntentConfig,
    force_stage_b: bool = False,
) -> tuple[bool, list[str]]:
    if force_stage_b:
        return True, ["force_stage_b"]
    stage_a = trace.get("stage_a") or {}
    reasons: list[str] = []
    if stage_a.get("escalate_to_stage_b"):
        reasons.append("stage_a_escalated")
    if config.gate_mode == "expanded":
        if stage_a.get("multi_intent_review_recommended"):
            reasons.append("stage_a_multi_intent_review_recommended")
        confidence = _safe_float(stage_a.get("confidence"), default=1.0)
        if confidence < config.confidence_threshold:
            reasons.append("low_stage_a_confidence")
        boundary_threshold = _safe_unbounded_float(
            stage_a.get("review_boundary_threshold"),
            config.expanded_boundary_margin_threshold,
        )
        boundary_margin = _safe_unbounded_float(stage_a.get("boundary_margin"), boundary_threshold)
        if boundary_margin < boundary_threshold:
            reasons.append("small_stage_a_set_boundary")
        selection_signals = trace.get("stage_r", {}).get("semantic_parse", {}).get("selection_signals", {})
        if selection_signals.get("has_multi_intent_signal") and len(_stage_a_selected(trace)) < 2:
            reasons.append("multi_intent_signal_underselected")
    return bool(reasons), sorted(set(reasons))


def _analyze_skipped(stage_a_selected: list[str], config: StageBMultiIntentConfig, gate_reasons: list[str]) -> dict[str, Any]:
    return {
        "selected_fqdns": stage_a_selected,
        "final_selected_fqdns": stage_a_selected,
        "decision_mode": "skipped_not_escalated",
        "consensus_confidence": None,
        "agent_votes": [],
        "feedback_scores": [],
        "constraint_check": {"pass": True, "reasons": []},
        "trust_trace": {
            "stage_a_escalated": False,
            "collaboration_mode": config.collaboration_mode,
            "gate_mode": config.gate_mode,
            "gate_reasons": gate_reasons,
        },
    }


def _analyze_deterministic(stage_a_selected: list[str], config: StageBMultiIntentConfig, gate_reasons: list[str]) -> dict[str, Any]:
    return {
        "selected_fqdns": stage_a_selected,
        "final_selected_fqdns": stage_a_selected,
        "decision_mode": "multi_intent_deterministic_passthrough",
        "consensus_confidence": None,
        "agent_votes": [],
        "feedback_scores": [],
        "constraint_check": {"pass": True, "reasons": []},
        "trust_trace": {
            "stage_a_escalated": True,
            "collaboration_mode": config.collaboration_mode,
            "gate_mode": config.gate_mode,
            "gate_reasons": gate_reasons,
        },
    }


def _set_boundary_margin(feedback_scores: list[dict[str, Any]]) -> float:
    selected_scores = [row["aggregate_score"] for row in feedback_scores if row.get("selected")]
    unselected_scores = [row["aggregate_score"] for row in feedback_scores if not row.get("selected")]
    if not selected_scores:
        return -max(unselected_scores or [0.0])
    return min(selected_scores) - max(unselected_scores or [0.0])


def _round2_candidate_fqdns(feedback_scores: list[dict[str, Any]], config: StageBMultiIntentConfig) -> list[str]:
    selected_rows = sorted(
        [row for row in feedback_scores if row.get("selected")],
        key=lambda row: row["aggregate_score"],
    )
    unselected_rows = sorted(
        [row for row in feedback_scores if not row.get("selected")],
        key=lambda row: row["aggregate_score"],
        reverse=True,
    )
    if not selected_rows or not unselected_rows:
        return []
    if _set_boundary_margin(feedback_scores) >= config.round2_margin_threshold:
        return []
    return _dedupe_keep_order(
        [row["fqdn"] for row in selected_rows[:2]]
        + [row["fqdn"] for row in unselected_rows[:2]]
    )


def _build_round2_packet(packet: dict[str, Any], round2_fqdns: list[str], feedback_scores: list[dict[str, Any]]) -> dict[str, Any]:
    selected_set = set(round2_fqdns)
    round2_packet = copy.deepcopy(packet)
    round2_packet["candidates"] = [row for row in packet["candidates"] if row["fqdn"] in selected_set]
    round2_packet["stage_a_selected_fqdns"] = [
        fqdn for fqdn in packet.get("stage_a_selected_fqdns", []) if fqdn in selected_set
    ]
    round2_packet["round_index"] = 2
    round2_packet["review_focus"] = "Only adjudicate the close set-boundary candidates listed in candidates."
    round2_packet["round1_feedback"] = [
        row for row in feedback_scores if row["fqdn"] in selected_set
    ]
    return round2_packet


def _merge_round2_feedback(
    round1_scores: list[dict[str, Any]],
    round2_scores: list[dict[str, Any]],
    resolver: NamespaceResolver,
    config: StageBMultiIntentConfig,
) -> tuple[list[str], list[dict[str, Any]]]:
    round2_map = {row["fqdn"]: row for row in round2_scores}
    merged = copy.deepcopy(round1_scores)
    selected_set = {row["fqdn"] for row in round1_scores if row.get("selected")}
    for row in merged:
        round2_row = round2_map.get(row["fqdn"])
        row["aggregate_score_round1"] = row["aggregate_score"]
        if not round2_row:
            row["aggregate_score_round2"] = None
            row["round2_support_vote_count"] = 0
            row["round2_remove_vote_count"] = 0
            continue
        row["aggregate_score_round2"] = round2_row["aggregate_score"]
        row["round2_support_vote_count"] = round2_row["support_vote_count"]
        row["round2_remove_vote_count"] = round2_row["remove_vote_count"]
        row["aggregate_score"] = round(_clip(0.55 * row["aggregate_score"] + 0.45 * round2_row["aggregate_score"]), 6)
        if round2_row.get("selected"):
            selected_set.add(row["fqdn"])
        else:
            selected_set.discard(row["fqdn"])
    score_map = {row["fqdn"]: row["aggregate_score"] for row in merged}
    selected = _prune_chain_duplicates(list(selected_set), score_map, resolver)[: config.max_selected]
    final_selected = set(selected)
    for row in merged:
        row["selected"] = row["fqdn"] in final_selected
    merged.sort(key=lambda row: (row["selected"], row["aggregate_score"], row["stage_r_score"]), reverse=True)
    return selected, merged


def analyze_stage_b_multi_intent(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBMultiIntentConfig | None = None,
    client: StageBMultiIntentClient | None = None,
    force_stage_b: bool = False,
) -> dict[str, Any]:
    config = config or StageBMultiIntentConfig()
    stage_a_selected = _stage_a_selected(trace)
    should_enter, gate_reasons = _stage_b_gate(trace, config, force_stage_b=force_stage_b)
    stage_a_escalated = "stage_a_escalated" in gate_reasons or bool(trace.get("stage_a", {}).get("escalate_to_stage_b"))
    if not should_enter:
        return _analyze_skipped(stage_a_selected, config, gate_reasons)
    if client is None:
        return _analyze_deterministic(stage_a_selected, config, gate_reasons)

    packet = build_review_packet(sample=sample, trace=trace, resolver=resolver, config=config)
    role_names = _role_names(config)
    votes, issues = _collect_votes(role_names, packet, client, config)
    selected, feedback_scores = _aggregate_votes(packet, votes, resolver, config)
    rounds = 1
    round2_fqdns: list[str] = []
    if config.max_rounds > 1:
        round2_fqdns = _round2_candidate_fqdns(feedback_scores, config)
    if round2_fqdns:
        rounds = 2
        round2_packet = _build_round2_packet(packet, round2_fqdns, feedback_scores)
        round2_votes, round2_issues = _collect_votes(role_names, round2_packet, client, config)
        for vote in round2_votes:
            vote["round_index"] = 2
        for vote in votes:
            vote["round_index"] = 1
        issues.extend(round2_issues)
        round2_selected, round2_scores = _aggregate_votes(round2_packet, round2_votes, resolver, config)
        selected, feedback_scores = _merge_round2_feedback(feedback_scores, round2_scores, resolver, config)
        votes.extend(round2_votes)
    else:
        for vote in votes:
            vote["round_index"] = 1
    invalid = [fqdn for fqdn in selected if fqdn not in {row["fqdn"] for row in packet["candidates"]}]
    if invalid:
        issues.append("final_selected_not_in_candidates")
    confidence = sum(float(vote.get("confidence", 0.0)) for vote in votes) / len(votes) if votes else 0.0
    return {
        "selected_fqdns": selected,
        "final_selected_fqdns": selected,
        "decision_mode": "multi_intent_llm_consensus_v2",
        "consensus_confidence": round(confidence, 6),
        "agent_votes": votes,
        "agent_rationales": [{"agent": vote["agent"], "rationale": vote["rationale"]} for vote in votes],
        "feedback_scores": feedback_scores,
        "constraint_check": {"pass": not issues, "reasons": sorted(set(issues))},
        "trust_trace": {
            "stage_a_escalated": stage_a_escalated,
            "force_stage_b": force_stage_b,
            "stage_a_selected_fqdns": stage_a_selected,
            "collaboration_mode": config.collaboration_mode,
            "gate_mode": config.gate_mode,
            "gate_reasons": gate_reasons,
            "role_count": len(role_names),
            "consensus_rounds": rounds,
            "round2_candidate_fqdns": round2_fqdns,
            "support_vote_histogram": dict(Counter(row["support_vote_count"] for row in feedback_scores)),
            "remove_vote_histogram": dict(Counter(row["remove_vote_count"] for row in feedback_scores)),
            "set_boundary_margin": round(_set_boundary_margin(feedback_scores), 6),
        },
        "review_packet": packet,
    }


def attach_stage_b_multi_final_fields(trace: dict[str, Any]) -> dict[str, Any]:
    stage_b = trace.get("stage_b") or {}
    selected = list(stage_b.get("final_selected_fqdns") or stage_b.get("selected_fqdns") or [])
    entered_stage_b = stage_b.get("decision_mode") != "skipped_not_escalated"
    trace["entered_stage_b"] = bool(entered_stage_b)
    trace["final_selected_fqdns"] = selected
    trace["final_decision_source"] = "stage_b_multi_intent" if entered_stage_b else "stage_a_multi_intent"
    trace["final_primary_fqdn"] = selected[0] if selected else None
    trace["final_related_fqdns"] = selected[1:]
    return trace


def build_stage_b_multi_intent_trace(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBMultiIntentConfig | None = None,
    client: StageBMultiIntentClient | None = None,
    force_stage_b: bool = False,
) -> dict[str, Any]:
    config = config or StageBMultiIntentConfig()
    stage_b = analyze_stage_b_multi_intent(
        sample=sample,
        trace=trace,
        resolver=resolver,
        config=config,
        client=client,
        force_stage_b=force_stage_b,
    )
    output = copy.deepcopy(trace)
    output["run_id"] = f"run_{config.stage_b_version}_{sample['id']}_{uuid.uuid4().hex[:8]}"
    output["stage_b_version"] = config.stage_b_version
    output["stage_b"] = stage_b
    return attach_stage_b_multi_final_fields(output)
