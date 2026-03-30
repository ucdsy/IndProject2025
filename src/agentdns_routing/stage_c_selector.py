from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .namespace import NamespaceResolver


ONLINE_STATUSES = {"online", "ready", "available"}
DEFAULT_INPUT_REQUIRED_FIELDS = ("query", "entities", "need")


@dataclass(frozen=True)
class StageCConfig:
    stage_c_version: str = "stage_c_v1_20260326"
    top_k: int = 5
    w_match: float = 0.55
    w_schema: float = 0.25
    w_tag: float = 0.20
    heartbeat_half_life_seconds: float = 120.0
    tie_epsilon: float = 1e-6


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalize_tag(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _coerce_tag_set(*values: Any) -> set[str]:
    tags: set[str] = set()
    for value in values:
        if isinstance(value, str):
            normalized = _normalize_tag(value)
            if normalized:
                tags.add(normalized)
            continue
        if isinstance(value, list):
            for item in value:
                normalized = _normalize_tag(item)
                if normalized:
                    tags.add(normalized)
    return tags


def _parse_timestamp(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _normalize_schema(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def _schema_coverage(input_schema: dict[str, Any], output_schema: dict[str, Any]) -> float:
    required = set(DEFAULT_INPUT_REQUIRED_FIELDS)
    declared_required = {
        str(item).strip()
        for item in input_schema.get("required", [])
        if str(item).strip()
    }
    properties = {
        str(item).strip()
        for item in (input_schema.get("properties") or {}).keys()
        if str(item).strip()
    }
    covered = len(required & (declared_required | properties))
    input_score = covered / len(required)
    output_score = 1.0 if output_schema else 0.0
    return _clip(0.7 * input_score + 0.3 * output_score)


def _tag_score(agent_tags: set[str], request_tags: set[str]) -> float:
    if not request_tags:
        return 0.0
    return _clip(len(agent_tags & request_tags) / len(request_tags))


def _infer_request_tags(
    routing_fqdn: str,
    resolver: NamespaceResolver,
    semantic_parse: dict[str, Any] | None = None,
) -> set[str]:
    node = resolver.get_node(routing_fqdn)
    if not node:
        return set()
    tags = _coerce_tag_set(
        node.l1,
        node.l2,
        node.segment,
        list(node.action_tags),
        list(node.object_tags),
        list(node.risk_tags),
        list(node.industry_tags),
    )
    if semantic_parse:
        context_features = semantic_parse.get("context_features") or {}
        tags |= _coerce_tag_set(list(context_features.keys()), list(context_features.values()))
    return tags


def _provider_counts(agents: list[dict[str, Any]]) -> dict[str, int]:
    if all("exposure_count_provider" in row for row in agents):
        return {
            str(row.get("provider") or "unknown"): int(row.get("exposure_count_provider") or 0)
            for row in agents
        }
    counter: Counter[str] = Counter()
    for row in agents:
        counter[str(row.get("provider") or "unknown")] += int(row.get("exposure_count_agent") or 0)
    return dict(counter)


def select_execution_target(
    routing_fqdn: str,
    agent_registry_snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    semantic_parse: dict[str, Any] | None = None,
    config: StageCConfig | None = None,
) -> dict[str, Any]:
    config = config or StageCConfig()
    started_at = time.perf_counter()
    snapshot_agents = list(agent_registry_snapshot.get("agents", []))
    provider_counts = _provider_counts(snapshot_agents)
    request_tags = _infer_request_tags(routing_fqdn, resolver, semantic_parse)

    filtered_out: list[dict[str, Any]] = []
    ranked: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for row in snapshot_agents:
        candidate_fqdn = str(row.get("routing_fqdn") or row.get("fqdn") or "").strip().lower()
        reasons: list[str] = []
        if candidate_fqdn != routing_fqdn:
            reasons.append("routing_fqdn_mismatch")
        endpoint = str(row.get("endpoint") or row.get("api_base_url") or "").strip()
        if not endpoint:
            reasons.append("endpoint_missing")
        status = str(row.get("status") or "online").strip().lower()
        if status not in ONLINE_STATUSES:
            reasons.append("status_offline" if status == "offline" else "status_not_online")
        if reasons:
            filtered_out.append(
                {
                    "agent_fqdn": row.get("agent_fqdn"),
                    "routing_fqdn": candidate_fqdn,
                    "reasons": reasons,
                }
            )
            continue

        input_schema = _normalize_schema(row.get("input_schema"))
        output_schema = _normalize_schema(row.get("output_schema"))
        agent_tags = _coerce_tag_set(row.get("tags", []), row.get("skills", []))
        provider = str(row.get("provider") or "unknown")
        heartbeat = _parse_timestamp(row.get("last_heartbeat_at"))
        if heartbeat is None:
            age_seconds = 0.0
        else:
            age_seconds = max((now - heartbeat).total_seconds(), 0.0)
        schema_score = _schema_coverage(input_schema, output_schema)
        tag_score = _tag_score(agent_tags, request_tags)
        base = _clip(
            config.w_match * 1.0 + config.w_schema * schema_score + config.w_tag * tag_score
        )
        health = math.exp(-age_seconds / config.heartbeat_half_life_seconds)
        fair_agent = 1.0 / math.sqrt(1.0 + max(int(row.get("exposure_count_agent") or 0), 0))
        fair_provider = 1.0 / math.sqrt(1.0 + max(int(provider_counts.get(provider, 0)), 0))
        final = base * health * fair_agent * fair_provider
        ranked.append(
            {
                "agent_id": row.get("agent_id"),
                "agent_fqdn": row.get("agent_fqdn"),
                "name": row.get("name"),
                "display_name_cn": row.get("display_name_cn"),
                "mode": row.get("mode"),
                "provider": provider,
                "routing_fqdn": candidate_fqdn,
                "endpoint": endpoint,
                "tags": sorted(agent_tags),
                "base": round(base, 6),
                "health": round(health, 6),
                "fair_agent": round(fair_agent, 6),
                "fair_provider": round(fair_provider, 6),
                "fair_score": round(fair_agent * fair_provider, 6),
                "final": round(final, 6),
                "exposure_count_agent": int(row.get("exposure_count_agent") or 0),
                "exposure_count_provider": int(provider_counts.get(provider, 0)),
                "reason": (
                    f"final={final:.4f}=base{base:.4f}*health{health:.4f}"
                    f"*fair_agent{fair_agent:.4f}*fair_provider{fair_provider:.4f}"
                ),
            }
        )

    ranked.sort(
        key=lambda row: (
            -row["final"],
            -row["health"],
            -row["fair_provider"],
            row["agent_fqdn"] or "",
        )
    )
    top_k_agents = ranked[: config.top_k]

    tie_break_applied = False
    if len(top_k_agents) >= 2:
        first, second = top_k_agents[0], top_k_agents[1]
        tie_break_applied = abs(first["final"] - second["final"]) <= config.tie_epsilon

    chosen = top_k_agents[0] if top_k_agents else None
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    return {
        "stage_c_version": config.stage_c_version,
        "routing_fqdn": routing_fqdn,
        "top_k_agents": top_k_agents,
        "chosen_agent_fqdn": chosen["agent_fqdn"] if chosen else None,
        "chosen_agent_id": chosen.get("agent_id") if chosen else None,
        "endpoint": chosen["endpoint"] if chosen else None,
        "reason": chosen["reason"] if chosen else "no_exact_online_agent",
        "selection_trace": {
            "routing_fqdn": routing_fqdn,
            "request_tags": sorted(request_tags),
            "required_input_fields": list(DEFAULT_INPUT_REQUIRED_FIELDS),
            "candidate_count_before_filter": len(snapshot_agents),
            "candidate_count_after_filter": len(ranked),
            "filtered_out": filtered_out,
            "filtered_out_reasons": dict(
                sorted(
                    Counter(
                        reason
                        for row in filtered_out
                        for reason in row.get("reasons", [])
                    ).items()
                )
            ),
            "tie_break_applied": tie_break_applied,
            "chosen_agent_fqdn": chosen["agent_fqdn"] if chosen else None,
            "selection_latency_ms": latency_ms,
        },
    }


def select_agents_for_subtasks(
    subtasks: list[dict[str, Any]],
    registry_snapshot: dict[str, Any],
    resolver: NamespaceResolver,
    top_k: int | None = None,
    config: StageCConfig | None = None,
) -> dict[str, Any]:
    base_config = config or StageCConfig()
    effective_config = (
        base_config
        if top_k is None or top_k == base_config.top_k
        else StageCConfig(
            stage_c_version=base_config.stage_c_version,
            top_k=top_k,
            w_match=base_config.w_match,
            w_schema=base_config.w_schema,
            w_tag=base_config.w_tag,
            heartbeat_half_life_seconds=base_config.heartbeat_half_life_seconds,
            tie_epsilon=base_config.tie_epsilon,
        )
    )

    groups: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for subtask in subtasks:
        routing_fqdn = str(subtask.get("routing_fqdn") or "").strip()
        if not routing_fqdn:
            candidates = list(subtask.get("fqdn_candidates") or [])
            routing_fqdn = str(candidates[0]).strip() if candidates else ""
        if not routing_fqdn:
            continue
        selection = select_execution_target(
            routing_fqdn=routing_fqdn,
            agent_registry_snapshot=registry_snapshot,
            resolver=resolver,
            semantic_parse=subtask.get("semantic_parse"),
            config=effective_config,
        )
        groups.append(
            {
                "need": subtask.get("need"),
                "fqdn": routing_fqdn,
                "role": subtask.get("role", "related"),
                "chosen_agent_fqdn": selection.get("chosen_agent_fqdn"),
                "endpoint": selection.get("endpoint"),
                "agents": [
                    {
                        "agent_id": row.get("agent_id"),
                        "name": row.get("name"),
                        "display_name_cn": row.get("display_name_cn"),
                        "agent_code": (row.get("agent_fqdn") or "").split(".agent.", 1)[0] or None,
                        "agent_fqdn": row.get("agent_fqdn"),
                        "provider": row.get("provider"),
                        "endpoint": row.get("endpoint"),
                        "routing_fqdn": routing_fqdn,
                        "tags": row.get("tags", []),
                        "base": row.get("base"),
                        "health": row.get("health"),
                        "fair_agent": row.get("fair_agent"),
                        "fair_provider": row.get("fair_provider"),
                        "final": row.get("final"),
                        "score": row.get("base"),
                        "fair_score": row.get("final"),
                        "reason": row.get("reason"),
                        "fqdn": routing_fqdn,
                        "exposure_count": row.get("exposure_count_agent", 0),
                        "exposure_count_agent": row.get("exposure_count_agent", 0),
                        "exposure_count_provider": row.get("exposure_count_provider", 0),
                        "mode": row.get("mode"),
                        "score_breakdown": {
                            "base": row.get("base"),
                            "health": row.get("health"),
                            "fair_agent": row.get("fair_agent"),
                            "fair_provider": row.get("fair_provider"),
                            "final": row.get("final"),
                        },
                    }
                    for row in selection.get("top_k_agents", [])
                ],
            }
        )
        traces.append(
            {
                "routing_fqdn": routing_fqdn,
                **selection.get("selection_trace", {}),
            }
        )
    return {
        "stage_c_version": effective_config.stage_c_version,
        "groups": groups,
        "fairness_notes": [
            "base = w_match * S_match + w_schema * S_schema + w_tag * S_tag",
            "final = base * health * fair_agent * fair_provider",
            "严格按 routing_fqdn 过滤；Stage C 不改写路由",
        ],
        "selection_trace": {
            "snapshot_id": registry_snapshot.get("snapshot_id"),
            "generated_at": registry_snapshot.get("generated_at"),
            "groups": traces,
        },
    }
