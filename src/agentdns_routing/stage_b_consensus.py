from __future__ import annotations

import copy
import json
import math
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from .namespace import NamespaceResolver, validate_fqdn
from .routing_chain import attach_stage_b_final_fields
from .stage_a_clean import _clip, _is_chain_duplicate, _safe_primary


@dataclass(frozen=True)
class StageBConfig:
    stage_b_version: str = "stage_b_v1_20260323_packetv2"
    prompt_version: str = "stage_b_prompt_v3_20260323"
    decision_mode: str = "llm_consensus_v1"
    deterministic_decision_mode: str = "consensus_minimal_v0"
    round2_margin_threshold: float = 0.10
    final_confidence_floor: float = 0.35
    related_min_score: float = 0.20
    max_rounds: int = 2
    allow_primary_override: bool = True
    override_vote_threshold: int = 3
    override_score_delta: float = 0.08
    override_min_explicit_support: float = 0.55
    cross_l1_stage_a_score_delta: float = 0.02
    related_vote_threshold: int = 2
    related_min_explicit_support: float = 0.55
    cross_l1_related_min_score: float = 0.55
    llm_temperature: float = 0.0
    collaboration_mode: str = "heterogeneous"
    include_semantic_handoff: bool = True
    general_reviewer_temperature: float | None = 0.35
    domain_expert_temperature: float | None = 0.50
    governance_risk_temperature: float | None = 0.2
    hierarchy_resolver_temperature: float | None = 0.35
    user_preference_temperature: float | None = 0.7
    llm_max_tokens: int = 3000
    parallel_role_calls: bool = True
    max_parallel_roles: int = 4


class StageBLLMClient(Protocol):
    provider: str
    model: str

    def adjudicate(self, role_name: str, packet: dict[str, Any], config: StageBConfig) -> tuple[dict[str, Any], str]:
        raise NotImplementedError


ROLE_NAMES = (
    "DomainExpert",
    "GovernanceRisk",
    "HierarchyResolver",
    "UserPreference",
)
BASE_ROLE_COUNT = len(ROLE_NAMES)

OVERRIDE_POSITIONS = ("support_stage_a", "propose_override")
OVERRIDE_BASIS_TAGS = (
    "explicit_primary_evidence",
    "specificity_gain",
    "risk_requirement",
    "multi_intent_separation",
    "hierarchy_disambiguation",
)


def _role_family(role_name: str) -> str:
    if role_name == "GeneralReviewer" or role_name.startswith("GeneralReviewer_"):
        return "GeneralReviewer"
    return role_name


def _role_names(config: StageBConfig) -> tuple[str, ...]:
    mode = str(config.collaboration_mode or "heterogeneous").lower()
    if mode == "single":
        return ("GeneralReviewer",)
    if mode == "homogeneous":
        return tuple(f"GeneralReviewer_{idx}" for idx in range(1, BASE_ROLE_COUNT + 1))
    return ROLE_NAMES


def _required_vote_count(base_threshold: int, role_count: int) -> int:
    scaled = math.ceil(base_threshold * role_count / BASE_ROLE_COUNT)
    return max(1, min(role_count, scaled))


def _role_temperature_map(config: StageBConfig) -> dict[str, float | None]:
    return {
        "GeneralReviewer": config.general_reviewer_temperature,
        "DomainExpert": config.domain_expert_temperature,
        "GovernanceRisk": config.governance_risk_temperature,
        "HierarchyResolver": config.hierarchy_resolver_temperature,
        "UserPreference": config.user_preference_temperature,
    }


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
        if item is None:
            continue
        text = str(item).strip()
        if text:
            items.append(text[:240])
        if len(items) >= limit:
            break
    return items


def _load_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty Stage B LLM response")
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


class OpenAICompatibleStageBLLMClient:
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

    def adjudicate(self, role_name: str, packet: dict[str, Any], config: StageBConfig) -> tuple[dict[str, Any], str]:
        messages = [
            {"role": "system", "content": _role_system_prompt(role_name)},
            {"role": "user", "content": _role_user_prompt(role_name, packet)},
        ]
        request_kwargs = {
            "model": self.model,
            "messages": messages,
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
        decision = _load_json_object(content)
        return decision, content


def make_stage_b_llm_client(provider: str, model: str | None = None) -> StageBLLMClient:
    provider = provider.lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise EnvironmentError("DEEPSEEK_API_KEY is not set")
        return OpenAICompatibleStageBLLMClient(
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
        return OpenAICompatibleStageBLLMClient(
            provider="openai",
            model=model or "gpt-5.4",
            api_key=api_key,
            timeout=60.0,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def _role_temperature(role_name: str, config: StageBConfig) -> float:
    override = _role_temperature_map(config).get(_role_family(role_name))
    return config.llm_temperature if override is None else float(override)


def _candidate_records(trace: dict[str, Any], resolver: NamespaceResolver) -> list[dict[str, Any]]:
    stage_a_llm_map = {
        row["fqdn"]: row
        for row in trace["stage_a"].get("llm_decision", {}).get("candidate_judgements", [])
        if isinstance(row, dict) and row.get("fqdn")
    }
    stage_r_by_fqdn = {
        row["fqdn"]: row
        for row in trace["stage_r"].get("fqdn_candidates", [])
    }
    routing_top_k_by_fqdn = {
        row["fqdn"]: row
        for row in trace["stage_a"].get("routing_top_k", [])
    }
    records: list[dict[str, Any]] = []
    for row in trace["stage_a"].get("candidate_scores", []):
        fqdn = row["fqdn"]
        breakdown = row.get("score_breakdown", {})
        evidence_for = row.get("evidence_for", {})
        evidence_against = row.get("evidence_against", [])
        stage_r_row = stage_r_by_fqdn.get(fqdn, {})
        top_k_row = routing_top_k_by_fqdn.get(fqdn, {})
        node = resolver.get_node(fqdn)
        llm_row = stage_a_llm_map.get(fqdn, {})
        penalty_total = sum(
            float(breakdown.get(key, 0.0))
            for key in (
                "coarse_parent_penalty",
                "secondary_only_penalty",
                "weak_segment_penalty",
                "scene_only_segment_penalty",
                "segment_parent_guard_penalty",
                "explicit_cue_guard_penalty",
                "fallback_penalty",
            )
        )
        if isinstance(evidence_for, dict):
            primary_hits = list(evidence_for.get("primary_hits", []))
            secondary_hits = list(evidence_for.get("secondary_hits", []))
            scene_hits = list(evidence_for.get("scene_hits", []))
            matched_phrases = evidence_for.get("matched_phrases", {})
            freeform_evidence = []
        else:
            primary_hits = []
            secondary_hits = []
            scene_hits = []
            matched_phrases = {}
            freeform_evidence = list(evidence_for)[:3] if isinstance(evidence_for, list) else []
        freeform_evidence_against = list(evidence_against)[:3] if isinstance(evidence_against, list) else []
        explicit_primary_support = 1.0 if primary_hits else 0.0
        explicit_secondary_support = 1.0 if secondary_hits else 0.0
        scene_support = 1.0 if scene_hits else 0.0
        explicit_support = max(
            explicit_primary_support,
            0.55 * explicit_secondary_support,
            0.20 * scene_support,
        )
        if freeform_evidence:
            explicit_support = max(explicit_support, 0.55)
        records.append(
            {
                "fqdn": fqdn,
                "score_a": float(row.get("score_a", 0.0)),
                "score_related": float(row.get("score_related", 0.0)),
                "score_r_norm": float(breakdown.get("score_r_norm", breakdown.get("stage_r_norm", 0.0))),
                "primary_fit": float(breakdown.get("primary_fit", breakdown.get("llm_primary_fit", breakdown.get("det_primary_norm", 0.0)))),
                "context_fit": float(breakdown.get("context_fit", breakdown.get("llm_task_fit", 0.0))),
                "hierarchy_fit": float(breakdown.get("hierarchy_fit", 0.0)),
                "specificity_fit": float(
                    breakdown.get(
                        "specificity_fit",
                        0.5 + breakdown.get("specificity_adjustment", 0.0),
                    )
                ),
                "evidence_diversity": float(breakdown.get("evidence_diversity", 0.0)),
                "node_type_fit": float(breakdown.get("node_type_fit", 0.0)),
                "relationship_bonus": float(breakdown.get("relationship_bonus", 0.0)),
                "penalty_total": penalty_total + float(breakdown.get("risk_penalty", 0.0)),
                "primary_hits": primary_hits,
                "secondary_hits": secondary_hits,
                "scene_hits": scene_hits,
                "explicit_support": explicit_support,
                "matched_phrases": matched_phrases,
                "node_kind": top_k_row.get("node_kind") or stage_r_row.get("node_kind"),
                "l1": top_k_row.get("l1") or stage_r_row.get("l1"),
                "l2": top_k_row.get("l2") or stage_r_row.get("l2"),
                "segment": top_k_row.get("segment") or stage_r_row.get("segment"),
                "parent_fqdn": stage_r_row.get("parent_fqdn"),
                "is_high_risk": bool(node.is_stage_a_high_risk) if node else False,
                "desc": node.desc if node else "",
                "aliases": list(node.aliases[:5]) if node else [],
                "freeform_evidence": freeform_evidence,
                "freeform_evidence_against": freeform_evidence_against,
                "stage_a_llm_task_fit": _safe_float(llm_row.get("task_fit", 0.0)),
                "stage_a_llm_primary_fit": _safe_float(llm_row.get("primary_fit", 0.0)),
                "stage_a_llm_related_fit": _safe_float(llm_row.get("related_fit", 0.0)),
                "stage_a_llm_specificity_judgement": str(llm_row.get("specificity_judgement", "fit"))[:32],
                "stage_a_llm_evidence_for": _coerce_text_list(llm_row.get("evidence_for", []), limit=3),
                "stage_a_llm_evidence_against": _coerce_text_list(llm_row.get("evidence_against", []), limit=3),
            }
        )
    return records


def _record_by_fqdn(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["fqdn"]: record for record in records}


def _competition_relation(
    fqdn: str,
    stage_a_primary: str | None,
    resolver: NamespaceResolver,
) -> str:
    if not stage_a_primary:
        return "no_incumbent"
    if fqdn == stage_a_primary:
        return "incumbent"
    if _is_chain_duplicate(fqdn, stage_a_primary, resolver):
        return "same_chain_competitor"
    left = resolver.get_node(fqdn)
    right = resolver.get_node(stage_a_primary)
    if left and right and left.l1 == right.l1:
        return "same_l1_competitor"
    return "cross_l1_competitor"


def _negative_evidence_card(record: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if record.get("secondary_hits") and not record.get("primary_hits"):
        reasons.append("secondary_only_signal")
    if record.get("scene_hits") and not record.get("primary_hits"):
        reasons.append("scene_only_support")
    if record.get("specificity_fit", 0.0) < 0.40:
        reasons.append("specificity_mismatch")
    if record.get("penalty_total", 0.0) >= 0.25:
        reasons.append("structure_penalties_present")
    for item in record.get("freeform_evidence_against", [])[:2]:
        if item not in reasons:
            reasons.append(item)
    return reasons[:4]


def _positive_evidence_card(record: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for bucket in ("primary_hits", "secondary_hits", "scene_hits", "freeform_evidence"):
        for value in record.get(bucket, [])[:2]:
            text = str(value).strip()
            if text and text not in items:
                items.append(text[:180])
            if len(items) >= 4:
                break
        if len(items) >= 4:
            break
    return items


def _stage_a_semantic_handoff(stage_a: dict[str, Any], *, enabled: bool = True) -> dict[str, Any]:
    if not enabled:
        return {
            "scene_context": "",
            "primary_intent": "",
            "secondary_intents": [],
            "primary_rationale": "",
            "secondary_rationale": "",
            "uncertainty_summary": "",
            "confusion_points": [],
            "override_sensitivity": "",
            "challenger_notes": [],
        }
    llm_decision = stage_a.get("llm_decision", {})
    challenger_notes = llm_decision.get("challenger_notes", [])
    if not isinstance(challenger_notes, list):
        challenger_notes = []
    return {
        "scene_context": llm_decision.get("scene_context", ""),
        "primary_intent": llm_decision.get("primary_intent", ""),
        "secondary_intents": list(llm_decision.get("secondary_intents", []))[:4],
        "primary_rationale": llm_decision.get("primary_rationale", ""),
        "secondary_rationale": llm_decision.get("secondary_rationale", ""),
        "uncertainty_summary": llm_decision.get("uncertainty_summary", ""),
        "confusion_points": list(llm_decision.get("confusion_points", []))[:5],
        "override_sensitivity": llm_decision.get("override_sensitivity", ""),
        "challenger_notes": [
            {
                "fqdn": item.get("fqdn"),
                "note": item.get("note"),
            }
            for item in challenger_notes[:4]
            if isinstance(item, dict) and item.get("fqdn") and item.get("note")
        ],
    }


def _histogram(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items()))


def _is_hierarchical_override(
    proposal_primary: str | None,
    stage_a_primary: str | None,
    resolver: NamespaceResolver | None,
) -> bool:
    if not resolver or not proposal_primary or not stage_a_primary or proposal_primary == stage_a_primary:
        return False
    return _is_chain_duplicate(stage_a_primary, proposal_primary, resolver)


def _infer_override_basis_tags(
    proposal_primary: str | None,
    stage_a_primary: str | None,
    record_by_fqdn: dict[str, dict[str, Any]],
    escalation_reasons: list[str],
    resolver: NamespaceResolver | None = None,
) -> list[str]:
    if not proposal_primary or not stage_a_primary or proposal_primary == stage_a_primary:
        return []
    proposal = record_by_fqdn.get(proposal_primary, {})
    stage_a_record = record_by_fqdn.get(stage_a_primary, {})
    tags: list[str] = []
    if proposal.get("primary_hits") and (
        not stage_a_record.get("primary_hits")
        or len(proposal.get("primary_hits", [])) > len(stage_a_record.get("primary_hits", []))
        or proposal.get("explicit_support", 0.0) > stage_a_record.get("explicit_support", 0.0)
    ):
        tags.append("explicit_primary_evidence")
    if proposal.get("specificity_fit", 0.0) > stage_a_record.get("specificity_fit", 0.0) + 0.10:
        tags.append("specificity_gain")
    if (
        "high_risk" in escalation_reasons
        or proposal.get("is_high_risk")
        or stage_a_record.get("is_high_risk")
    ):
        tags.append("risk_requirement")
    if "multi_intent_conflict" in escalation_reasons and (
        proposal.get("primary_hits") or proposal.get("secondary_hits")
    ):
        tags.append("multi_intent_separation")
    if _is_hierarchical_override(proposal_primary, stage_a_primary, resolver):
        tags.append("hierarchy_disambiguation")
    unique_tags: list[str] = []
    for tag in tags:
        if tag in OVERRIDE_BASIS_TAGS and tag not in unique_tags:
            unique_tags.append(tag)
    return unique_tags


def _coerce_override_position(
    raw_position: Any,
    proposal_primary: str | None,
    stage_a_primary: str | None,
) -> str:
    if raw_position in OVERRIDE_POSITIONS:
        return str(raw_position)
    if proposal_primary and stage_a_primary and proposal_primary != stage_a_primary:
        return "propose_override"
    return "support_stage_a"


def _coerce_override_basis_tags(
    raw_tags: Any,
    override_position: str,
    proposal_primary: str | None,
    stage_a_primary: str | None,
    record_by_fqdn: dict[str, dict[str, Any]],
    escalation_reasons: list[str],
    resolver: NamespaceResolver | None = None,
) -> list[str]:
    if override_position != "propose_override":
        return []
    tags = []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if tag in OVERRIDE_BASIS_TAGS and tag not in tags:
                tags.append(tag)
    inferred = _infer_override_basis_tags(
        proposal_primary=proposal_primary,
        stage_a_primary=stage_a_primary,
        record_by_fqdn=record_by_fqdn,
        escalation_reasons=escalation_reasons,
        resolver=resolver,
    )
    for tag in inferred:
        if tag not in tags:
            tags.append(tag)
    return tags[:3]


def _default_role_decision(role_name: str, packet: dict[str, Any], config: StageBConfig) -> dict[str, Any]:
    records = packet["candidates"]
    ranked = sorted(
        records,
        key=lambda item: (_role_score(role_name, item), item["score_a"], item["score_r_norm"]),
        reverse=True,
    )
    primary = ranked[0]["fqdn"] if ranked else None
    related: list[str] = []
    for record in ranked[1:]:
        if len(related) >= 2:
            break
        if record["score_related"] >= config.related_min_score and record["explicit_support"] > 0.0:
            related.append(record["fqdn"])
    override_position = _coerce_override_position(
        raw_position=None,
        proposal_primary=primary,
        stage_a_primary=packet["stage_a"]["selected_primary_fqdn"],
    )
    return {
        "proposal_primary_fqdn": primary,
        "proposal_related_fqdns": related,
        "confidence": _role_score(role_name, ranked[0]) if ranked else 0.0,
        "rationale": _role_rationale(role_name, ranked[0]) if ranked else f"{role_name}: no_candidates",
        "override_position": override_position,
        "override_basis_tags": [],
    }


def _role_score(role_name: str, record: dict[str, Any]) -> float:
    role_family = _role_family(role_name)
    score_r_norm = record["score_r_norm"]
    primary_fit = record["primary_fit"]
    context_fit = record["context_fit"]
    hierarchy_fit = record["hierarchy_fit"]
    specificity_fit = record["specificity_fit"]
    evidence_diversity = record["evidence_diversity"]
    node_type_fit = record["node_type_fit"]
    relationship_bonus = record["relationship_bonus"]
    explicit_support = record["explicit_support"]
    penalty_total = record["penalty_total"]
    is_segment = record.get("node_kind") == "segment"

    if role_family == "GeneralReviewer":
        value = (
            0.26 * primary_fit
            + 0.16 * context_fit
            + 0.12 * hierarchy_fit
            + 0.12 * specificity_fit
            + 0.10 * explicit_support
            + 0.08 * score_r_norm
            + 0.08 * relationship_bonus
            + 0.06 * evidence_diversity
            + 0.04 * node_type_fit
            - 0.18 * penalty_total
        )
    elif role_family == "DomainExpert":
        value = (
            0.34 * primary_fit
            + 0.16 * context_fit
            + 0.12 * specificity_fit
            + 0.10 * score_r_norm
            + 0.10 * evidence_diversity
            + 0.10 * explicit_support
            + 0.08 * relationship_bonus
            - 0.18 * penalty_total
        )
    elif role_family == "GovernanceRisk":
        value = (
            0.26 * primary_fit
            + 0.16 * context_fit
            + 0.14 * hierarchy_fit
            + 0.12 * score_r_norm
            + 0.10 * node_type_fit
            + 0.10 * explicit_support
            - 0.20 * penalty_total
        )
        if record["is_high_risk"] and explicit_support <= 0.0:
            value -= 0.12
        if record["is_high_risk"] and explicit_support > 0.0:
            value += 0.05
    elif role_family == "HierarchyResolver":
        value = (
            0.24 * hierarchy_fit
            + 0.20 * specificity_fit
            + 0.16 * relationship_bonus
            + 0.12 * primary_fit
            + 0.10 * context_fit
            + 0.08 * explicit_support
            + 0.06 * score_r_norm
            + 0.04 * evidence_diversity
            - 0.18 * penalty_total
        )
        value += 0.04 if is_segment else 0.0
        if hierarchy_fit >= 0.40:
            value += 0.03
    else:
        value = (
            0.30 * explicit_support
            + 0.22 * primary_fit
            + 0.16 * context_fit
            + 0.10 * score_r_norm
            + 0.10 * relationship_bonus
            + 0.06 * evidence_diversity
            + 0.06 * max(record["score_related"], 0.0)
            - 0.16 * penalty_total
        )
    return round(_clip(value), 6)


def _role_rationale(role_name: str, record: dict[str, Any]) -> str:
    role_family = _role_family(role_name)
    reasons: list[str] = []
    if record["primary_hits"]:
        reasons.append("explicit_primary_hits")
    elif record["secondary_hits"]:
        reasons.append("secondary_support")
    if record["context_fit"] >= 0.40:
        reasons.append("context_fit")
    if record["hierarchy_fit"] >= 0.40:
        reasons.append("hierarchy_fit")
    if record["specificity_fit"] >= 0.60:
        reasons.append("specificity_fit")
    if record["is_high_risk"]:
        reasons.append("high_risk")
    if not reasons:
        reasons.append("score_balance")
    return f"{role_family}: " + ", ".join(reasons[:3])


def _propose_related(
    selected_primary_fqdn: str,
    stage_a_related: list[str],
    resolver: NamespaceResolver,
) -> list[str]:
    related: list[str] = []
    for fqdn in stage_a_related:
        if fqdn == selected_primary_fqdn:
            continue
        if _is_chain_duplicate(selected_primary_fqdn, fqdn, resolver):
            continue
        if any(_is_chain_duplicate(existing, fqdn, resolver) for existing in related):
            continue
        if fqdn not in related:
            related.append(fqdn)
    return related


def _allow_new_related_candidate(
    *,
    fqdn: str,
    related_vote_count: int,
    role_count: int,
    record: dict[str, Any],
    selected_primary_fqdn: str,
    selected_related: list[str],
    selected_primary_record: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBConfig,
) -> bool:
    if fqdn == selected_primary_fqdn:
        return False
    if related_vote_count < _required_vote_count(config.related_vote_threshold, role_count):
        return False
    if _is_chain_duplicate(selected_primary_fqdn, fqdn, resolver):
        return False
    if any(_is_chain_duplicate(existing, fqdn, resolver) for existing in selected_related):
        return False
    if record.get("score_related", 0.0) < config.related_min_score:
        return False
    if record.get("explicit_support", 0.0) < config.related_min_explicit_support:
        return False
    if not record.get("secondary_hits"):
        return False
    if record.get("is_high_risk") and not record.get("secondary_hits"):
        return False

    selected_primary_l1 = selected_primary_record.get("l1")
    candidate_l1 = record.get("l1")
    if selected_primary_l1 and candidate_l1 and selected_primary_l1 != candidate_l1:
        if record.get("score_related", 0.0) < config.cross_l1_related_min_score:
            return False

    return True


def _propose_related_from_votes(
    selected_primary_fqdn: str,
    agent_votes: list[dict[str, Any]],
    stage_a_related: list[str],
    records: list[dict[str, Any]],
    resolver: NamespaceResolver,
    config: StageBConfig,
    role_count: int,
) -> list[str]:
    record_by_fqdn = {row["fqdn"]: row for row in records}
    selected_primary_record = record_by_fqdn.get(selected_primary_fqdn, {})
    related_vote_count: dict[str, int] = {}
    for vote in agent_votes:
        for fqdn in vote.get("proposal_related_fqdns", []):
            related_vote_count[fqdn] = related_vote_count.get(fqdn, 0) + 1

    related = _propose_related(
        selected_primary_fqdn=selected_primary_fqdn,
        stage_a_related=stage_a_related,
        resolver=resolver,
    )
    for fqdn, count in sorted(
        related_vote_count.items(),
        key=lambda item: (item[1], record_by_fqdn.get(item[0], {}).get("score_related", 0.0)),
        reverse=True,
    ):
        if fqdn in related:
            continue
        record = record_by_fqdn.get(fqdn, {})
        if _allow_new_related_candidate(
            fqdn=fqdn,
            related_vote_count=count,
            role_count=role_count,
            record=record,
            selected_primary_fqdn=selected_primary_fqdn,
            selected_related=related,
            selected_primary_record=selected_primary_record,
            resolver=resolver,
            config=config,
        ):
            related.append(fqdn)

    return related[:3]


def _role_focus(role_name: str) -> str:
    role_family = _role_family(role_name)
    if role_family == "GeneralReviewer":
        return "重点综合判断 incumbent 与 challenger 的主任务匹配度、粒度、约束和相关 secondary 线索。"
    if role_family == "DomainExpert":
        return "重点判断 query 核心任务与候选能力是否直接匹配。"
    if role_family == "GovernanceRisk":
        return "重点判断治理、高风险、跨域约束是否支持当前主路由。"
    if role_family == "HierarchyResolver":
        return "重点判断 parent-child、base-segment、sibling competition 与粒度是否匹配。"
    if role_family == "UserPreference":
        return "重点判断用户表述中的显式偏好、主次意图和 related 线索。"
    return ""


def _role_system_prompt(role_name: str) -> str:
    role_family = _role_family(role_name)
    return (
        "你是 AgentDNS Stage B 的慢路径共识角色。"
        "你仍然只能在给定候选集合内输出最终提案，不能发明新 fqdn。"
        f"你当前扮演的角色是 {role_family}。"
        f"{_role_focus(role_name)}"
        "请结合 query、Stage A 的语义交接、以及候选内证据卡，比较 incumbent 与主要 challenger。"
        "如果你认为 Stage A 原判存在明显弱点，可以建议 override；如果证据仍不足，也可以保留原判。"
        "请尽量说明 primary 为什么更像主任务，related 为什么更像次要诉求，以及当前最大的歧义点是什么。"
        "你必须显式声明自己是支持 Stage A 原判，还是建议 override。"
        "输出必须是单个 JSON 对象，不能附带散文解释。"
    )


def _role_user_prompt(role_name: str, packet: dict[str, Any]) -> str:
    return (
        "请作为固定角色参与 Stage B 共识。\n"
        "要求：\n"
        "1. 最终输出中的 proposal_primary_fqdn 与 proposal_related_fqdns 必须来自 candidates。\n"
        "2. proposal_primary_fqdn 必须唯一。\n"
        "3. proposal_related_fqdns 可以为空，但不能包含 proposal_primary_fqdn。\n"
        "4. rationale 请解释你为什么更支持当前 primary，以及 incumbent/ challenger 的关键差异。\n"
        "5. 若 packet.round_index=2，请优先在 round2_candidates 中比较，不要跳回其他候选。\n"
        "6. confidence 用 0 到 1。\n"
        "7. override_position 只能是 support_stage_a 或 propose_override。\n"
        "8. 若 override_position=propose_override，可用的 override_basis_tags 仅限："
        "explicit_primary_evidence, specificity_gain, risk_requirement, multi_intent_separation, hierarchy_disambiguation。\n"
        "9. 请优先利用 semantic_handoff、competition_view、positive_evidence_card、negative_evidence_card 做判断，不要只重复旧分数。\n"
        f"当前角色：{role_name}\n\n"
        f"{json.dumps(packet, ensure_ascii=False, indent=2)}"
    )


def _build_consensus_packet(
    sample: dict[str, Any],
    trace: dict[str, Any],
    records: list[dict[str, Any]],
    resolver: NamespaceResolver,
    config: StageBConfig,
    round_index: int,
    round2_candidates: list[str] | None = None,
) -> dict[str, Any]:
    stage_a = trace["stage_a"]
    stage_a_primary = stage_a.get("selected_primary_fqdn")
    enriched_records: list[dict[str, Any]] = []
    for record in records:
        enriched = dict(record)
        enriched["competition_view"] = {
            "relation_to_stage_a_primary": _competition_relation(record["fqdn"], stage_a_primary, resolver),
            "stage_a_selected_primary": record["fqdn"] == stage_a_primary,
            "same_chain_as_stage_a_primary": _is_chain_duplicate(record["fqdn"], stage_a_primary, resolver)
            if stage_a_primary
            else False,
        }
        enriched["positive_evidence_card"] = _positive_evidence_card(record)
        enriched["negative_evidence_card"] = _negative_evidence_card(record)
        enriched["secondary_recovery_card"] = {
            "secondary_anchor_strength": round(
                _clip(
                    0.65 * (1.0 if record.get("secondary_hits") else 0.0)
                    + 0.20 * min(len(record.get("stage_a_llm_evidence_for", [])), 2) / 2
                    + 0.15 * min(record.get("score_related", 0.0), 1.0)
                ),
                6,
            ),
            "cross_domain_secondary_ok": bool(
                record.get("secondary_hits")
                or record.get("stage_a_llm_related_fit", 0.0) >= 0.60
            ),
            "chain_duplicate_risk": bool(
                stage_a_primary and _is_chain_duplicate(stage_a_primary, record["fqdn"], resolver)
            ),
        }
        enriched_records.append(enriched)
    packet = {
        "sample_id": sample["id"],
        "namespace_version": trace["namespace_version"],
        "stage_r_version": trace["stage_r_version"],
        "stage_a_version": trace["stage_a_version"],
        "stage_b_version": config.stage_b_version,
        "prompt_version": config.prompt_version,
        "query": sample.get("query", ""),
        "context": sample.get("context", {}),
        "stage_a": {
            "selected_primary_fqdn": stage_a.get("selected_primary_fqdn"),
            "selected_related_fqdns": list(stage_a.get("selected_related_fqdns", [])),
            "confidence": stage_a.get("confidence"),
            "margin": stage_a.get("margin"),
            "escalation_reasons": list(stage_a.get("escalation_reasons", [])),
            "query_packet": stage_a.get("query_packet", {}),
            "decision_packet": stage_a.get("decision_packet", {}),
            "semantic_handoff": _stage_a_semantic_handoff(stage_a, enabled=config.include_semantic_handoff),
            "semantic_handoff_enabled": bool(config.include_semantic_handoff),
            "routing_top_k": list(stage_a.get("routing_top_k", []))[:5],
        },
        "round_index": round_index,
        "candidates": enriched_records,
    }
    if round2_candidates:
        packet["round2_candidates"] = round2_candidates
    return packet


def _sanitize_role_vote(
    role_name: str,
    raw: dict[str, Any],
    packet: dict[str, Any],
    resolver: NamespaceResolver | None = None,
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    candidate_fqdns = [row["fqdn"] for row in packet["candidates"]]
    candidate_set = set(candidate_fqdns)
    stage_a_primary = packet["stage_a"]["selected_primary_fqdn"]
    record_by_fqdn = _record_by_fqdn(packet["candidates"])
    escalation_reasons = list(packet["stage_a"].get("escalation_reasons", []))
    proposal_primary = raw.get("proposal_primary_fqdn")
    if proposal_primary not in candidate_set:
        issues.append(f"{role_name}:primary_not_in_candidates")
        proposal_primary = None

    raw_related = raw.get("proposal_related_fqdns", [])
    if not isinstance(raw_related, list):
        raw_related = []
        issues.append(f"{role_name}:related_not_list")
    proposal_related = [fqdn for fqdn in raw_related if fqdn in candidate_set and fqdn != proposal_primary]
    if len(proposal_related) != len(raw_related):
        issues.append(f"{role_name}:related_not_in_candidates")

    rationale = str(raw.get("rationale", "")).strip()[:280]
    if not rationale:
        rationale = f"{role_name}: score_balance"

    override_position = _coerce_override_position(
        raw_position=raw.get("override_position"),
        proposal_primary=proposal_primary,
        stage_a_primary=stage_a_primary,
    )
    override_basis_tags = _coerce_override_basis_tags(
        raw_tags=raw.get("override_basis_tags", []),
        override_position=override_position,
        proposal_primary=proposal_primary,
        stage_a_primary=stage_a_primary,
        record_by_fqdn=record_by_fqdn,
        escalation_reasons=escalation_reasons,
        resolver=resolver,
    )

    vote = {
        "agent": role_name,
        "proposal_primary_fqdn": proposal_primary,
        "proposal_related_fqdns": proposal_related,
        "confidence": _safe_float(raw.get("confidence", 0.0)),
        "rationale": rationale,
        "override_position": override_position,
        "override_basis_tags": override_basis_tags,
    }
    return vote, issues


def _collect_llm_votes(
    role_names: tuple[str, ...],
    packet: dict[str, Any],
    client: StageBLLMClient,
    config: StageBConfig,
    resolver: NamespaceResolver,
) -> tuple[list[dict[str, Any]], list[str]]:
    def collect_one(role_name: str) -> tuple[dict[str, Any], list[str]]:
        try:
            raw_vote, raw_response = client.adjudicate(role_name, packet, config)
            vote, vote_issues = _sanitize_role_vote(role_name, raw_vote, packet, resolver=resolver)
        except Exception as exc:  # pragma: no cover - integration/runtime behavior
            vote = {
                "agent": role_name,
                "proposal_primary_fqdn": packet["stage_a"]["selected_primary_fqdn"],
                "proposal_related_fqdns": [],
                "confidence": 0.0,
                "rationale": f"{role_name}: llm_error:{type(exc).__name__}",
                "override_position": "support_stage_a",
                "override_basis_tags": [],
            }
            vote_issues = [f"{role_name}:llm_error:{type(exc).__name__}"]
            raw_response = str(exc)
        vote["round"] = packet["round_index"]
        vote["raw_response"] = raw_response
        return vote, vote_issues

    votes: list[dict[str, Any]] = []
    issues: list[str] = []
    if config.parallel_role_calls and len(role_names) > 1:
        max_workers = max(1, min(config.max_parallel_roles, len(role_names)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_by_role = {
                role_name: executor.submit(collect_one, role_name)
                for role_name in role_names
            }
            results = {
                role_name: future.result()
                for role_name, future in future_by_role.items()
            }
        for role_name in role_names:
            vote, vote_issues = results[role_name]
            votes.append(vote)
            issues.extend(vote_issues)
        return votes, issues

    for role_name in role_names:
        vote, vote_issues = collect_one(role_name)
        votes.append(vote)
        issues.extend(vote_issues)
    return votes, issues


def _collect_deterministic_votes(
    role_names: tuple[str, ...],
    packet: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    votes: list[dict[str, Any]] = []
    issues: list[str] = []
    for role_name in role_names:
        raw_vote = _default_role_decision(role_name=role_name, packet=packet, config=config)
        vote, vote_issues = _sanitize_role_vote(role_name, raw_vote, packet, resolver=resolver)
        vote["round"] = packet["round_index"]
        votes.append(vote)
        issues.extend(vote_issues)
    return votes, issues


def _aggregate_feedback_scores(
    records: list[dict[str, Any]],
    agent_votes: list[dict[str, Any]],
    score_key: str,
    stage_a_primary: str | None,
    role_count: int,
) -> list[dict[str, Any]]:
    feedback_scores: list[dict[str, Any]] = []
    for record in records:
        primary_votes = [vote for vote in agent_votes if vote.get("proposal_primary_fqdn") == record["fqdn"]]
        related_votes = [vote for vote in agent_votes if record["fqdn"] in vote.get("proposal_related_fqdns", [])]
        support_votes = [vote for vote in primary_votes if vote.get("override_position") == "support_stage_a"]
        override_votes = [vote for vote in primary_votes if vote.get("override_position") == "propose_override"]
        vote_ratio = len(primary_votes) / max(role_count, 1)
        related_vote_ratio = len(related_votes) / max(role_count, 1)
        avg_role_score = sum(vote.get("confidence", 0.0) for vote in primary_votes) / len(primary_votes) if primary_votes else 0.0
        consensus_score = (
            0.40 * vote_ratio
            + 0.25 * avg_role_score
            + 0.15 * _clip(record["score_a"])
            + 0.10 * record["explicit_support"]
            + 0.10 * related_vote_ratio
        )
        feedback_scores.append(
            {
                "fqdn": record["fqdn"],
                "vote_count": len(primary_votes),
                "related_vote_count": len(related_votes),
                "avg_role_score": round(avg_role_score, 6),
                "stage_a_score": round(record["score_a"], 6),
                "explicit_support": round(record["explicit_support"], 6),
                "stage_a_support_vote_count": len(support_votes) if record["fqdn"] == stage_a_primary else 0,
                "override_vote_count": len(override_votes),
                "override_basis_histogram": _histogram(
                    [tag for vote in override_votes for tag in vote.get("override_basis_tags", [])]
                ),
                score_key: round(_clip(consensus_score), 6),
            }
        )
    return sorted(
        feedback_scores,
        key=lambda item: (item[score_key], item["vote_count"], item["stage_a_score"]),
        reverse=True,
    )


def _collect_sensitive_override_flags(
    stage_a_primary: str | None,
    proposal_primary: str | None,
    stage_a_reasons: list[str],
    record_by_fqdn: dict[str, dict[str, Any]],
    resolver: NamespaceResolver,
) -> dict[str, bool]:
    flags = {
        "high_risk_override": False,
        "hierarchical_override": False,
        "cross_l1_override": False,
    }
    if not stage_a_primary or not proposal_primary or proposal_primary == stage_a_primary:
        return flags
    stage_a_record = record_by_fqdn.get(stage_a_primary, {})
    proposal_record = record_by_fqdn.get(proposal_primary, {})
    flags["high_risk_override"] = bool(
        "high_risk" in stage_a_reasons
        or stage_a_record.get("is_high_risk")
        or proposal_record.get("is_high_risk")
    )
    flags["hierarchical_override"] = _is_hierarchical_override(proposal_primary, stage_a_primary, resolver)
    flags["cross_l1_override"] = bool(
        stage_a_record.get("l1")
        and proposal_record.get("l1")
        and stage_a_record["l1"] != proposal_record["l1"]
    )
    return flags


def _aggregate_override_histogram(agent_votes: list[dict[str, Any]], stage_a_primary: str | None) -> dict[str, int]:
    return _histogram(
        [
            tag
            for vote in agent_votes
            if vote.get("override_position") == "propose_override"
            and vote.get("proposal_primary_fqdn")
            and vote.get("proposal_primary_fqdn") != stage_a_primary
            for tag in vote.get("override_basis_tags", [])
        ]
    )


def _resolve_primary_decision(
    *,
    stage_a_primary: str | None,
    final_scores: list[dict[str, Any]],
    round2_score_map: dict[str, dict[str, Any]],
    stage_a_reasons: list[str],
    record_by_fqdn: dict[str, dict[str, Any]],
    resolver: NamespaceResolver,
    config: StageBConfig,
    role_count: int,
) -> tuple[str | None, dict[str, Any], list[str]]:
    notes: list[str] = []
    if not final_scores:
        return None, {
            "override_attempted": False,
            "override_allowed": False,
            "override_block_reasons": ["empty_stage_b_candidates"],
            "sensitive_override_flags": {
                "high_risk_override": False,
                "hierarchical_override": False,
                "cross_l1_override": False,
            },
        }, notes

    winner = final_scores[0]
    selected_primary = winner["fqdn"]
    sensitive_flags = _collect_sensitive_override_flags(
        stage_a_primary=stage_a_primary,
        proposal_primary=winner["fqdn"],
        stage_a_reasons=stage_a_reasons,
        record_by_fqdn=record_by_fqdn,
        resolver=resolver,
    )
    override_attempted = bool(stage_a_primary and winner["fqdn"] != stage_a_primary)
    block_reasons: list[str] = []
    override_allowed = False
    if override_attempted:
        stage_a_feedback = next((row for row in final_scores if row["fqdn"] == stage_a_primary), None)
        stage_a_consensus_score = stage_a_feedback["consensus_score_final"] if stage_a_feedback else 0.0
        winner_record = record_by_fqdn.get(winner["fqdn"], {})
        stage_a_record = record_by_fqdn.get(stage_a_primary, {})
        if not config.allow_primary_override:
            block_reasons.append("override_disabled")
        required_override_votes = _required_vote_count(config.override_vote_threshold, role_count)
        if winner["vote_count"] < required_override_votes:
            block_reasons.append("insufficient_round1_votes")
        if winner["consensus_score_final"] < stage_a_consensus_score + config.override_score_delta:
            block_reasons.append("insufficient_score_delta")
        if winner["explicit_support"] < config.override_min_explicit_support:
            block_reasons.append("insufficient_explicit_support")
        if any(sensitive_flags.values()):
            round2_vote_count = round2_score_map.get(winner["fqdn"], {}).get("vote_count", 0)
            if round2_vote_count < required_override_votes:
                block_reasons.append("sensitive_override_requires_round2_consensus")
            if not winner_record.get("primary_hits"):
                block_reasons.append("sensitive_override_requires_primary_hits")
            if winner_record.get("explicit_support", 0.0) <= stage_a_record.get("explicit_support", 0.0):
                block_reasons.append("sensitive_override_requires_stronger_explicit_support")
        if sensitive_flags.get("cross_l1_override"):
            if winner.get("stage_a_score", 0.0) < stage_a_record.get("score_a", 0.0) + config.cross_l1_stage_a_score_delta:
                block_reasons.append("cross_l1_override_requires_stage_a_score_gain")
        override_allowed = not block_reasons
        if override_allowed:
            notes.append("Stage B override was allowed after generic consensus checks passed.")
        else:
            notes.append("Stage B kept Stage A primary because generic override checks were not satisfied.")
            selected_primary = stage_a_primary
    return selected_primary, {
        "override_attempted": override_attempted,
        "override_allowed": override_allowed,
        "override_block_reasons": sorted(set(block_reasons)),
        "sensitive_override_flags": sensitive_flags,
    }, notes


def _selected_margin_and_confidence(
    final_scores: list[dict[str, Any]],
    selected_primary: str | None,
    config: StageBConfig,
) -> tuple[float, float]:
    if not final_scores or not selected_primary:
        return 0.0, 0.0
    selected_row = next((row for row in final_scores if row["fqdn"] == selected_primary), final_scores[0])
    runner_up_score = max(
        (row["consensus_score_final"] for row in final_scores if row["fqdn"] != selected_row["fqdn"]),
        default=0.0,
    )
    margin = max(selected_row["consensus_score_final"] - runner_up_score, 0.0)
    confidence = _clip(
        0.72 * selected_row["consensus_score_final"] + 0.28 * margin,
        low=config.final_confidence_floor,
    )
    return margin, confidence


def _analyze_stage_b_skipped(stage_a: dict[str, Any], config: StageBConfig) -> dict[str, Any]:
    selected_primary = stage_a.get("selected_primary_fqdn")
    selected_related = list(stage_a.get("selected_related_fqdns", []))
    return {
        "selected_primary_fqdn": selected_primary,
        "selected_related_fqdns": selected_related,
        "final_primary_fqdn": selected_primary,
        "final_related_fqdns": selected_related,
        "decision_mode": "skipped_not_escalated",
        "consensus_confidence": round(float(stage_a.get("confidence", 0.0)), 6),
        "consensus_margin": round(float(stage_a.get("margin", 0.0)), 6),
        "consensus_rounds": 0,
        "agent_votes": [],
        "agent_rationales": [],
        "feedback_scores": [],
        "trust_trace": {
            "stage_a_escalated": False,
            "stage_a_confidence": round(float(stage_a.get("confidence", 0.0)), 6),
            "stage_a_margin": round(float(stage_a.get("margin", 0.0)), 6),
            "escalation_reasons": [],
            "collaboration_mode": config.collaboration_mode,
            "semantic_handoff_enabled": bool(config.include_semantic_handoff),
            "notes": ["Stage B skipped because Stage A did not escalate."],
        },
        "constraint_check": {"pass": True, "reasons": []},
        "disagreement": False,
        "resolved": True,
    }


def _analyze_stage_b_deterministic(
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBConfig,
) -> dict[str, Any]:
    stage_a = trace["stage_a"]
    role_names = _role_names(config)
    role_count = len(role_names)
    records = _candidate_records(trace, resolver)
    if not records:
        return {
            "selected_primary_fqdn": None,
            "selected_related_fqdns": [],
            "final_primary_fqdn": None,
            "final_related_fqdns": [],
            "decision_mode": config.deterministic_decision_mode,
            "consensus_confidence": 0.0,
            "consensus_margin": 0.0,
            "consensus_rounds": 1,
            "agent_votes": [],
            "agent_rationales": [],
            "feedback_scores": [],
            "trust_trace": {
                "stage_a_escalated": True,
                "stage_a_confidence": round(float(stage_a.get("confidence", 0.0)), 6),
                "stage_a_margin": round(float(stage_a.get("margin", 0.0)), 6),
                "escalation_reasons": list(stage_a.get("escalation_reasons", [])),
                "collaboration_mode": config.collaboration_mode,
                "semantic_handoff_enabled": bool(config.include_semantic_handoff),
                "notes": ["No candidates available for Stage B consensus."],
            },
            "constraint_check": {"pass": False, "reasons": ["empty_stage_b_candidates"]},
            "disagreement": False,
            "resolved": False,
        }

    stage_a_primary = stage_a.get("selected_primary_fqdn")
    round1_packet = _build_consensus_packet(
        sample={"id": trace["sample_id"], "query": trace.get("query", ""), "context": trace.get("context", {})},
        trace=trace,
        records=records,
        resolver=resolver,
        config=config,
        round_index=1,
    )
    round1_votes, round1_issues = _collect_deterministic_votes(
        role_names,
        round1_packet,
        resolver=resolver,
        config=config,
    )
    feedback_scores = _aggregate_feedback_scores(
        records,
        round1_votes,
        score_key="consensus_score_round1",
        stage_a_primary=stage_a_primary,
        role_count=role_count,
    )

    agent_votes: list[dict[str, Any]] = list(round1_votes)
    rounds = 1
    notes = [
        "Stage B v0 only re-judges within the frozen Stage R candidate set.",
        f"Stage A escalation reasons: {', '.join(stage_a.get('escalation_reasons', [])) or 'none'}",
    ]
    final_scores = copy.deepcopy(feedback_scores)
    round2_score_map: dict[str, dict[str, Any]] = {}
    record_by_fqdn = _record_by_fqdn(records)
    if len(feedback_scores) > 1:
        round1_margin = feedback_scores[0]["consensus_score_round1"] - feedback_scores[1]["consensus_score_round1"]
        sensitive_flags = _collect_sensitive_override_flags(
            stage_a_primary=stage_a_primary,
            proposal_primary=feedback_scores[0]["fqdn"],
            stage_a_reasons=list(stage_a.get("escalation_reasons", [])),
            record_by_fqdn=record_by_fqdn,
            resolver=resolver,
        )
        sensitive_round2 = bool(stage_a_primary and feedback_scores[0]["fqdn"] != stage_a_primary and any(sensitive_flags.values()))
        if (round1_margin < config.round2_margin_threshold or sensitive_round2) and config.max_rounds > 1:
            rounds = 2
            round2_candidates = [feedback_scores[0]["fqdn"], feedback_scores[1]["fqdn"]]
            if sensitive_round2 and stage_a_primary:
                round2_candidates = [feedback_scores[0]["fqdn"], stage_a_primary]
            round2_candidates = list(dict.fromkeys(round2_candidates))
            top2_records = [row for row in records if row["fqdn"] in set(round2_candidates)]
            round2_packet = _build_consensus_packet(
                sample={"id": trace["sample_id"], "query": trace.get("query", ""), "context": trace.get("context", {})},
                trace=trace,
                records=top2_records,
                resolver=resolver,
                config=config,
                round_index=2,
                round2_candidates=round2_candidates,
            )
            round2_packet["round1_feedback"] = feedback_scores[:2]
            round2_votes, round2_issues = _collect_deterministic_votes(
                role_names,
                round2_packet,
                resolver=resolver,
                config=config,
            )
            agent_votes.extend(round2_votes)
            round1_issues.extend(round2_issues)
            round2_scores = _aggregate_feedback_scores(
                top2_records,
                round2_votes,
                score_key="consensus_score_round2",
                stage_a_primary=stage_a_primary,
                role_count=role_count,
            )
            round2_score_map = {row["fqdn"]: row for row in round2_scores}
            if sensitive_round2:
                notes.append("Round 2 was triggered because a sensitive override attempt requires re-adjudicating winner vs Stage A primary.")
            else:
                notes.append("Round 2 was triggered because round-1 top1/top2 margin was too small.")
        else:
            round2_score_map = {}
    for row in final_scores:
        round2_row = round2_score_map.get(row["fqdn"])
        row["round2_vote_count"] = round2_row["vote_count"] if round2_row else 0
        row["round2_override_vote_count"] = round2_row["override_vote_count"] if round2_row else 0
        row["round2_stage_a_support_vote_count"] = round2_row["stage_a_support_vote_count"] if round2_row else 0
        row["round2_override_basis_histogram"] = round2_row["override_basis_histogram"] if round2_row else {}
        round1_score = row["consensus_score_round1"]
        round2_score = round2_row["consensus_score_round2"] if round2_row else None
        if round2_score is None:
            row["consensus_score_final"] = round1_score
        else:
            row["consensus_score_final"] = round(_clip(0.45 * round1_score + 0.35 * round2_score + 0.20 * row["stage_a_score"]), 6)

    final_scores.sort(
        key=lambda item: (item["consensus_score_final"], item["vote_count"], item["stage_a_score"]),
        reverse=True,
    )
    selected_primary, override_trace, override_notes = _resolve_primary_decision(
        stage_a_primary=stage_a_primary,
        final_scores=final_scores,
        round2_score_map=round2_score_map,
        stage_a_reasons=list(stage_a.get("escalation_reasons", [])),
        record_by_fqdn=record_by_fqdn,
        resolver=resolver,
        config=config,
        role_count=role_count,
    )
    notes.extend(override_notes)

    selected_related = _propose_related(
        selected_primary_fqdn=selected_primary,
        stage_a_related=list(stage_a.get("selected_related_fqdns", [])),
        resolver=resolver,
    )
    margin, confidence = _selected_margin_and_confidence(final_scores, selected_primary, config)

    constraint_reasons: list[str] = []
    candidate_fqdns = {record["fqdn"] for record in records}
    if selected_primary not in candidate_fqdns:
        constraint_reasons.append("primary_not_in_candidates")
    if not _safe_primary({"fqdn": selected_primary}):
        constraint_reasons.append("invalid_primary_fqdn")
    invalid_related = [fqdn for fqdn in selected_related if fqdn not in candidate_fqdns]
    if invalid_related:
        constraint_reasons.append("related_not_in_candidates")
    constraint_reasons.extend(round1_issues)
    disagreement = len({vote["proposal_primary_fqdn"] for vote in round1_votes if vote.get("proposal_primary_fqdn")}) > 1

    return {
        "selected_primary_fqdn": selected_primary,
        "selected_related_fqdns": selected_related,
        "final_primary_fqdn": selected_primary,
        "final_related_fqdns": selected_related,
        "decision_mode": config.deterministic_decision_mode,
        "consensus_confidence": round(confidence, 6),
        "consensus_margin": round(margin, 6),
        "consensus_rounds": rounds,
        "agent_votes": agent_votes,
        "agent_rationales": [{"agent": vote["agent"], "rationale": vote["rationale"]} for vote in agent_votes],
        "feedback_scores": final_scores,
        "trust_trace": {
            "stage_a_escalated": True,
            "stage_a_selected_primary_fqdn": stage_a_primary,
            "stage_a_confidence": round(float(stage_a.get("confidence", 0.0)), 6),
            "stage_a_margin": round(float(stage_a.get("margin", 0.0)), 6),
            "escalation_reasons": list(stage_a.get("escalation_reasons", [])),
            "candidate_count": len(records),
            "collaboration_mode": config.collaboration_mode,
            "semantic_handoff_enabled": bool(config.include_semantic_handoff),
            "disagreement": disagreement,
            "override_attempted": override_trace["override_attempted"],
            "override_allowed": override_trace["override_allowed"],
            "override_block_reasons": override_trace["override_block_reasons"],
            "sensitive_override_flags": override_trace["sensitive_override_flags"],
            "stage_a_support_vote_count": sum(
                1
                for vote in agent_votes
                if vote.get("proposal_primary_fqdn") == stage_a_primary and vote.get("override_position") == "support_stage_a"
            ),
            "override_vote_count": sum(
                1
                for vote in agent_votes
                if vote.get("override_position") == "propose_override"
                and vote.get("proposal_primary_fqdn")
                and vote.get("proposal_primary_fqdn") != stage_a_primary
            ),
            "override_basis_histogram": _aggregate_override_histogram(agent_votes, stage_a_primary),
            "notes": notes,
            "backend": "deterministic_v0",
        },
        "constraint_check": {"pass": not constraint_reasons, "reasons": constraint_reasons},
        "disagreement": disagreement,
        "resolved": not constraint_reasons,
        "llm_provider": None,
        "llm_model": None,
        "prompt_version": config.prompt_version,
    }


def _analyze_stage_b_llm(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    client: StageBLLMClient,
    config: StageBConfig,
) -> dict[str, Any]:
    stage_a = trace["stage_a"]
    role_names = _role_names(config)
    role_count = len(role_names)
    records = _candidate_records(trace, resolver)
    if not records:
        return {
            "selected_primary_fqdn": None,
            "selected_related_fqdns": [],
            "final_primary_fqdn": None,
            "final_related_fqdns": [],
            "decision_mode": config.decision_mode,
            "consensus_confidence": 0.0,
            "consensus_margin": 0.0,
            "consensus_rounds": 1,
            "agent_votes": [],
            "agent_rationales": [],
            "feedback_scores": [],
            "trust_trace": {
                "stage_a_escalated": True,
                "stage_a_confidence": round(float(stage_a.get("confidence", 0.0)), 6),
                "stage_a_margin": round(float(stage_a.get("margin", 0.0)), 6),
                "escalation_reasons": list(stage_a.get("escalation_reasons", [])),
                "collaboration_mode": config.collaboration_mode,
                "semantic_handoff_enabled": bool(config.include_semantic_handoff),
                "notes": ["No candidates available for Stage B consensus."],
                "backend": config.decision_mode,
            },
            "constraint_check": {"pass": False, "reasons": ["empty_stage_b_candidates"]},
            "disagreement": False,
            "resolved": False,
            "llm_provider": client.provider,
            "llm_model": client.model,
            "prompt_version": config.prompt_version,
        }

    stage_a_primary = stage_a.get("selected_primary_fqdn")
    round1_packet = _build_consensus_packet(sample, trace, records, resolver, config, round_index=1)
    round1_votes, round1_issues = _collect_llm_votes(role_names, round1_packet, client, config, resolver=resolver)
    round1_scores = _aggregate_feedback_scores(
        records,
        round1_votes,
        score_key="consensus_score_round1",
        stage_a_primary=stage_a_primary,
        role_count=role_count,
    )

    all_votes = list(round1_votes)
    rounds = 1
    round2_scores: list[dict[str, Any]] | None = None
    notes = [
        "Stage B only re-judges within the frozen Stage R candidate set.",
        f"Stage A escalation reasons: {', '.join(stage_a.get('escalation_reasons', [])) or 'none'}",
    ]
    record_by_fqdn = _record_by_fqdn(records)

    if len(round1_scores) > 1:
        round1_margin = round1_scores[0]["consensus_score_round1"] - round1_scores[1]["consensus_score_round1"]
        sensitive_flags = _collect_sensitive_override_flags(
            stage_a_primary=stage_a_primary,
            proposal_primary=round1_scores[0]["fqdn"],
            stage_a_reasons=list(stage_a.get("escalation_reasons", [])),
            record_by_fqdn=record_by_fqdn,
            resolver=resolver,
        )
        sensitive_round2 = bool(stage_a_primary and round1_scores[0]["fqdn"] != stage_a_primary and any(sensitive_flags.values()))
        if (round1_margin < config.round2_margin_threshold or sensitive_round2) and config.max_rounds > 1:
            rounds = 2
            round2_candidates = [round1_scores[0]["fqdn"], round1_scores[1]["fqdn"]]
            if sensitive_round2 and stage_a_primary:
                round2_candidates = [round1_scores[0]["fqdn"], stage_a_primary]
            round2_candidates = list(dict.fromkeys(round2_candidates))
            top2_records = [row for row in records if row["fqdn"] in set(round2_candidates)]
            round2_packet = _build_consensus_packet(
                sample,
                trace,
                top2_records,
                resolver,
                config,
                round_index=2,
                round2_candidates=round2_candidates,
            )
            round2_packet["round1_feedback"] = round1_scores[:2]
            round2_votes, round2_issues = _collect_llm_votes(role_names, round2_packet, client, config, resolver=resolver)
            all_votes.extend(round2_votes)
            round1_issues.extend(round2_issues)
            round2_scores = _aggregate_feedback_scores(
                top2_records,
                round2_votes,
                score_key="consensus_score_round2",
                stage_a_primary=stage_a_primary,
                role_count=role_count,
            )
            if sensitive_round2:
                notes.append("Round 2 was triggered because a sensitive override attempt requires re-adjudicating winner vs Stage A primary.")
            else:
                notes.append("Round 2 was triggered because round-1 top1/top2 margin was too small.")

    final_scores = copy.deepcopy(round1_scores)
    round2_score_map = {row["fqdn"]: row for row in round2_scores or []}
    for row in final_scores:
        round1_score = row["consensus_score_round1"]
        round2_row = round2_score_map.get(row["fqdn"], {})
        row["round2_vote_count"] = round2_row.get("vote_count", 0)
        row["round2_override_vote_count"] = round2_row.get("override_vote_count", 0)
        row["round2_stage_a_support_vote_count"] = round2_row.get("stage_a_support_vote_count", 0)
        row["round2_override_basis_histogram"] = round2_row.get("override_basis_histogram", {})
        round2_score = round2_row.get("consensus_score_round2")
        if round2_score is None:
            row["consensus_score_final"] = round1_score
            continue
        row["consensus_score_final"] = round(
            _clip(0.45 * round1_score + 0.35 * round2_score + 0.20 * row["stage_a_score"]),
            6,
        )

    final_scores.sort(
        key=lambda item: (item["consensus_score_final"], item["vote_count"], item["stage_a_score"]),
        reverse=True,
    )
    selected_primary, override_trace, override_notes = _resolve_primary_decision(
        stage_a_primary=stage_a_primary,
        final_scores=final_scores,
        round2_score_map=round2_score_map,
        stage_a_reasons=list(stage_a.get("escalation_reasons", [])),
        record_by_fqdn=record_by_fqdn,
        resolver=resolver,
        config=config,
        role_count=role_count,
    )
    notes.extend(override_notes)

    selected_related = _propose_related_from_votes(
        selected_primary_fqdn=selected_primary,
        agent_votes=all_votes,
        stage_a_related=list(stage_a.get("selected_related_fqdns", [])),
        records=records,
        resolver=resolver,
        config=config,
        role_count=role_count,
    )

    margin, confidence = _selected_margin_and_confidence(final_scores, selected_primary, config)

    candidate_fqdns = {record["fqdn"] for record in records}
    constraint_reasons: list[str] = []
    if selected_primary not in candidate_fqdns:
        constraint_reasons.append("primary_not_in_candidates")
    if not selected_primary or not validate_fqdn(selected_primary):
        constraint_reasons.append("invalid_primary_fqdn")
    invalid_related = [fqdn for fqdn in selected_related if fqdn not in candidate_fqdns]
    if invalid_related:
        constraint_reasons.append("related_not_in_candidates")
    constraint_reasons.extend(round1_issues)

    disagreement = len({vote["proposal_primary_fqdn"] for vote in round1_votes if vote.get("proposal_primary_fqdn")}) > 1

    return {
        "selected_primary_fqdn": selected_primary,
        "selected_related_fqdns": selected_related,
        "final_primary_fqdn": selected_primary,
        "final_related_fqdns": selected_related,
        "decision_mode": config.decision_mode,
        "consensus_confidence": round(confidence, 6),
        "consensus_margin": round(margin, 6),
        "consensus_rounds": rounds,
        "agent_votes": all_votes,
        "agent_rationales": [{"agent": vote["agent"], "rationale": vote["rationale"], "round": vote["round"]} for vote in all_votes],
        "feedback_scores": final_scores,
        "trust_trace": {
            "stage_a_escalated": True,
            "stage_a_selected_primary_fqdn": stage_a_primary,
            "stage_a_confidence": round(float(stage_a.get("confidence", 0.0)), 6),
            "stage_a_margin": round(float(stage_a.get("margin", 0.0)), 6),
            "escalation_reasons": list(stage_a.get("escalation_reasons", [])),
            "candidate_count": len(records),
            "collaboration_mode": config.collaboration_mode,
            "semantic_handoff_enabled": bool(config.include_semantic_handoff),
            "disagreement": disagreement,
            "override_attempted": override_trace["override_attempted"],
            "override_allowed": override_trace["override_allowed"],
            "override_block_reasons": override_trace["override_block_reasons"],
            "sensitive_override_flags": override_trace["sensitive_override_flags"],
            "stage_a_support_vote_count": sum(
                1
                for vote in all_votes
                if vote.get("proposal_primary_fqdn") == stage_a_primary and vote.get("override_position") == "support_stage_a"
            ),
            "override_vote_count": sum(
                1
                for vote in all_votes
                if vote.get("override_position") == "propose_override"
                and vote.get("proposal_primary_fqdn")
                and vote.get("proposal_primary_fqdn") != stage_a_primary
            ),
            "override_basis_histogram": _aggregate_override_histogram(all_votes, stage_a_primary),
            "notes": notes,
            "backend": config.decision_mode,
        },
        "constraint_check": {"pass": not constraint_reasons, "reasons": sorted(set(constraint_reasons))},
        "disagreement": disagreement,
        "resolved": not constraint_reasons,
        "llm_provider": client.provider,
        "llm_model": client.model,
        "prompt_version": config.prompt_version,
    }


def analyze_stage_b(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBConfig | None = None,
    client: StageBLLMClient | None = None,
) -> dict[str, Any]:
    config = config or StageBConfig()
    stage_a = trace["stage_a"]
    if not stage_a.get("escalate_to_stage_b"):
        return _analyze_stage_b_skipped(stage_a, config)
    if client is None:
        return _analyze_stage_b_deterministic(trace=trace, resolver=resolver, config=config)
    return _analyze_stage_b_llm(sample=sample, trace=trace, resolver=resolver, client=client, config=config)


def build_stage_b_trace(
    sample: dict[str, Any],
    trace: dict[str, Any],
    resolver: NamespaceResolver,
    config: StageBConfig | None = None,
    client: StageBLLMClient | None = None,
) -> dict[str, Any]:
    config = config or StageBConfig()
    stage_b = analyze_stage_b(sample=sample, trace=trace, resolver=resolver, config=config, client=client)
    stage_b_trace = copy.deepcopy(trace)
    stage_b_trace["run_id"] = f"run_{config.stage_b_version}_{sample['id']}_{uuid.uuid4().hex[:8]}"
    stage_b_trace["stage_b_version"] = config.stage_b_version
    stage_b_trace["stage_b"] = stage_b
    return attach_stage_b_final_fields(stage_b_trace)
