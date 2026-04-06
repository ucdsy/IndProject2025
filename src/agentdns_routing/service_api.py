from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .namespace import NamespaceResolver
from .related_v2 import (
    RelatedV2Config,
    RelatedV2LLMClient,
    analyze_related_v2,
    attach_related_v2_final_fields,
    make_related_llm_client,
)
from .stage_a_clean import StageACleanConfig, build_routing_run_trace as build_stage_a_clean_trace
from .stage_a_llm import StageALLMConfig, build_routing_run_trace as build_stage_a_llm_trace, make_llm_client
from .stage_b_consensus import StageBConfig, build_stage_b_trace, make_stage_b_llm_client
from .stage_c_selector import StageCConfig, select_agents_for_subtasks
from .stage_r_clean import StageRCleanConfig, build_candidate_snapshot

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESCRIPTOR_PATH = ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"


class RoutingResolveRequest(BaseModel):
    query: str
    context: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    stage_a_mode: Literal["clean", "llm"] | None = None
    stage_b_mode: Literal["skip", "deterministic", "llm"] | None = None
    stage_a_provider: Literal["deepseek", "openai"] | None = None
    stage_b_provider: Literal["deepseek", "openai"] | None = None
    stage_a_model: str | None = None
    stage_b_model: str | None = None
    stage_r_top_k: int = 10
    sample_id: str | None = None


class RouteSelectionInput(BaseModel):
    routing_fqdn: str
    need: str | None = None


class StageCSelectRequest(BaseModel):
    routes: list[RouteSelectionInput]
    agent_registry_snapshot: dict[str, Any]
    top_k: int = 5


app = FastAPI(title="IndProj04 Routing Service")


@lru_cache(maxsize=1)
def _resolver() -> NamespaceResolver:
    descriptor_path = Path(os.getenv("INDPROJ_NAMESPACE_DESCRIPTORS", str(DEFAULT_DESCRIPTOR_PATH)))
    return NamespaceResolver.from_jsonl(descriptor_path)


@lru_cache(maxsize=1)
def _stage_r_version() -> str:
    return os.getenv("INDPROJ_STAGE_R_VERSION", "sr_clean_v2_20260314_related2")


@lru_cache(maxsize=1)
def _stage_r_config() -> StageRCleanConfig:
    return StageRCleanConfig()


@lru_cache(maxsize=1)
def _stage_a_clean_config() -> StageACleanConfig:
    return StageACleanConfig(stage_a_version=os.getenv("INDPROJ_STAGE_A_CLEAN_VERSION", StageACleanConfig().stage_a_version))


@lru_cache(maxsize=1)
def _stage_a_llm_config() -> StageALLMConfig:
    return StageALLMConfig(stage_a_version=os.getenv("INDPROJ_STAGE_A_LLM_VERSION", StageALLMConfig().stage_a_version))


@lru_cache(maxsize=1)
def _stage_b_config() -> StageBConfig:
    return StageBConfig(stage_b_version=os.getenv("INDPROJ_STAGE_B_VERSION", StageBConfig().stage_b_version))


@lru_cache(maxsize=1)
def _stage_c_config() -> StageCConfig:
    return StageCConfig(stage_c_version=os.getenv("INDPROJ_STAGE_C_VERSION", StageCConfig().stage_c_version))


@lru_cache(maxsize=1)
def _related_v2_config() -> RelatedV2Config:
    return RelatedV2Config(related_version=os.getenv("INDPROJ_RELATED_V2_VERSION", RelatedV2Config().related_version))


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "indproj04-routing-service"}


@app.post("/api/routing/resolve")
def resolve_routing(payload: RoutingResolveRequest) -> dict[str, Any]:
    resolver = _resolver()
    sample = {
        "id": payload.sample_id or f"service_{uuid.uuid4().hex[:10]}",
        "namespace_version": resolver.namespace_version,
        "query": payload.query,
        "context": payload.context,
        "constraints": payload.constraints,
    }
    snapshot = build_candidate_snapshot(
        sample=sample,
        resolver=resolver,
        top_k=payload.stage_r_top_k,
        stage_r_version=_stage_r_version(),
        config=_stage_r_config(),
    )

    trace = _build_routing_trace(sample=sample, snapshot=snapshot, payload=payload, resolver=resolver)
    routes = _ordered_routes(trace)

    return {
        "sample_id": sample["id"],
        "query": payload.query,
        "context": payload.context,
        "constraints": payload.constraints,
        "planner_projection": _planner_projection(routes=routes, resolver=resolver, extracted_entities=payload.context),
        "routing_result": {
            "selected_primary_fqdn": trace.get("final_primary_fqdn"),
            "selected_related_fqdns": trace.get("final_related_fqdns", []),
            "final_primary_fqdn": trace.get("final_primary_fqdn"),
            "final_related_fqdns": trace.get("final_related_fqdns", []),
            "final_decision_source": trace.get("final_decision_source"),
            "final_related_source": trace.get("final_related_source"),
            "entered_stage_b": bool(trace.get("entered_stage_b", False)),
            "stage_r_version": trace.get("stage_r_version"),
            "stage_a_version": trace.get("stage_a_version"),
            "stage_b_version": trace.get("stage_b_version"),
            "related_v2_version": trace.get("related_v2_version"),
            "related_candidate_options": _related_candidate_options(trace=trace, resolver=resolver),
        },
        "routing_trace": _routing_trace_lines(trace),
        "trace": trace,
    }


@app.post("/api/routing/select-agents")
def select_agents(payload: StageCSelectRequest) -> dict[str, Any]:
    resolver = _resolver()
    snapshot_agents = list(payload.agent_registry_snapshot.get("agents", []))
    selection = select_agents_for_subtasks(
        subtasks=[row.model_dump() for row in payload.routes],
        registry_snapshot={"agents": snapshot_agents},
        resolver=resolver,
        top_k=payload.top_k,
        config=_stage_c_config(),
    )
    selection["snapshot_id"] = payload.agent_registry_snapshot.get("snapshot_id")
    selection["generated_at"] = payload.agent_registry_snapshot.get("generated_at")
    return selection


def _build_routing_trace(
    sample: dict[str, Any],
    snapshot: dict[str, Any],
    payload: RoutingResolveRequest,
    resolver: NamespaceResolver,
) -> dict[str, Any]:
    stage_a_mode = _stage_a_mode(payload)
    stage_b_mode = _stage_b_mode(payload)
    related_config = _related_v2_config()
    related_client = _related_client(payload, stage_a_mode=stage_a_mode, stage_b_mode=stage_b_mode)

    if stage_a_mode == "llm":
        client = make_llm_client(provider=payload.stage_a_provider or os.getenv("INDPROJ_STAGE_A_PROVIDER", "deepseek"), model=payload.stage_a_model)
        trace = build_stage_a_llm_trace(
            sample=sample,
            snapshot=snapshot,
            resolver=resolver,
            client=client,
            config=_stage_a_llm_config(),
            related_config=related_config,
            related_client=related_client,
            with_related_v2=False,
        )
    else:
        trace = build_stage_a_clean_trace(
            sample=sample,
            snapshot=snapshot,
            resolver=resolver,
            config=_stage_a_clean_config(),
            related_config=related_config,
            related_client=related_client,
            with_related_v2=False,
        )

    provisional_primary = trace.get("final_primary_fqdn") or trace["stage_a"].get("selected_primary_fqdn")
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Related retrieval can speculatively start once Stage A has a provisional
        # primary; if Stage B keeps the same primary we reuse this work, otherwise
        # attach_related_v2_final_fields will rerun against the final primary.
        related_future = executor.submit(
            analyze_related_v2,
            sample=sample,
            trace=trace,
            resolver=resolver,
            primary_fqdn=provisional_primary,
            config=related_config,
            client=related_client,
        )

        if stage_b_mode == "skip":
            finalized_trace = trace
        else:
            stage_b_client = None
            if stage_b_mode == "llm":
                stage_b_client = make_stage_b_llm_client(
                    provider=payload.stage_b_provider or os.getenv("INDPROJ_STAGE_B_PROVIDER", "deepseek"),
                    model=payload.stage_b_model,
                )
            finalized_trace = build_stage_b_trace(
                sample=sample,
                trace=trace,
                resolver=resolver,
                config=_stage_b_config(),
                client=stage_b_client,
                related_config=related_config,
                related_client=related_client,
                with_related_v2=False,
            )

        prefetched_related = related_future.result()

    final_primary = finalized_trace.get("final_primary_fqdn") or provisional_primary
    if prefetched_related.get("primary_fqdn") == final_primary:
        return attach_related_v2_final_fields(
            sample=sample,
            trace=finalized_trace,
            resolver=resolver,
            config=related_config,
            precomputed=prefetched_related,
            client=related_client,
        )
    return attach_related_v2_final_fields(
        sample=sample,
        trace=finalized_trace,
        resolver=resolver,
        config=related_config,
        precomputed=prefetched_related,
        client=related_client,
    )


def _related_client(
    payload: RoutingResolveRequest,
    *,
    stage_a_mode: str,
    stage_b_mode: str,
) -> RelatedV2LLMClient | None:
    if stage_a_mode == "llm":
        provider = payload.stage_a_provider or os.getenv("INDPROJ_STAGE_A_PROVIDER", "deepseek")
        return make_related_llm_client(provider=provider, model=payload.stage_a_model)
    if stage_b_mode == "llm":
        provider = payload.stage_b_provider or os.getenv("INDPROJ_STAGE_B_PROVIDER", "deepseek")
        return make_related_llm_client(provider=provider, model=payload.stage_b_model)
    return None


def _stage_a_mode(payload: RoutingResolveRequest) -> str:
    if payload.stage_a_mode:
        return payload.stage_a_mode
    if os.getenv("INDPROJ_STAGE_A_MODE"):
        return os.getenv("INDPROJ_STAGE_A_MODE", "clean")
    return "llm" if (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")) else "clean"


def _stage_b_mode(payload: RoutingResolveRequest) -> str:
    if payload.stage_b_mode:
        return payload.stage_b_mode
    if os.getenv("INDPROJ_STAGE_B_MODE"):
        return os.getenv("INDPROJ_STAGE_B_MODE", "deterministic")
    return "llm" if (os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")) else "deterministic"


def _ordered_routes(trace: dict[str, Any]) -> list[str]:
    routes: list[str] = []
    final_primary = trace.get("final_primary_fqdn")
    if final_primary:
        routes.append(final_primary)
    for fqdn in trace.get("final_related_fqdns", []):
        if fqdn and fqdn not in routes:
            routes.append(fqdn)
    return routes


def _planner_projection(routes: list[str], resolver: NamespaceResolver, extracted_entities: dict[str, Any]) -> dict[str, Any]:
    intents: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fqdn in routes:
        node = resolver.get_node(fqdn)
        if not node:
            continue
        tags = [
            *(value for value in (node.l1, node.l2, node.segment) if value),
            *node.industry_tags,
            *node.risk_tags,
            *node.action_tags,
            *node.object_tags,
        ]
        intents[node.l1].append(
            {
                "need": node.l2 or node.l1,
                "fqdn_candidates": [fqdn],
                "tags": list(dict.fromkeys([tag for tag in tags if tag]))[:8],
            }
        )
    return {
        "country_root": "cn",
        "extracted_entities": extracted_entities,
        "intents": [{"category": category, "subtasks": subtasks} for category, subtasks in intents.items()],
    }


def _related_candidate_options(trace: dict[str, Any], resolver: NamespaceResolver) -> list[dict[str, Any]]:
    related_v2 = trace.get("related_v2") or {}
    candidate_rows = list(related_v2.get("related_candidates", []))
    llm_decision = ((related_v2.get("llm_trace") or {}).get("decision") or {})
    llm_selected = set(llm_decision.get("selected_related_fqdns", []))
    final_selected = set(trace.get("final_related_fqdns", []))
    candidate_notes = {
        row.get("fqdn"): row.get("reason") or row.get("note", "")
        for row in llm_decision.get("candidate_decisions", llm_decision.get("candidate_notes", []))
        if isinstance(row, dict) and row.get("fqdn")
    }
    blocked = {
        note.split(":")[1]
        for note in related_v2.get("review", {}).get("review_notes", [])
        if isinstance(note, str) and note.startswith("guard_drop:")
    }

    options: list[dict[str, Any]] = []
    for row in candidate_rows:
        fqdn = row.get("fqdn")
        if not fqdn:
            continue
        node = resolver.get_node(fqdn)
        status = "candidate"
        if fqdn in final_selected:
            status = "selected"
        elif fqdn in llm_selected and fqdn in blocked:
            status = "suggested_but_blocked"
        elif fqdn in llm_selected:
            status = "suggested"
        options.append(
            {
                "fqdn": fqdn,
                "status": status,
                "desc": node.desc if node else "",
                "l1": row.get("l1"),
                "l2": row.get("l2"),
                "segment": row.get("segment"),
                "score_related_v2": row.get("score_related_v2"),
                "builder_sources": list(row.get("builder_sources", [])),
                "stage_r_rank": row.get("stage_r_rank"),
                "cross_l1": bool(row.get("cross_l1", False)),
                "is_high_risk": bool(row.get("is_high_risk", False)),
                "cross_domain_secondary_ok": bool(row.get("cross_domain_secondary_ok", False)),
                "note": candidate_notes.get(fqdn, ""),
            }
        )
    return options


def _routing_trace_lines(trace: dict[str, Any]) -> list[str]:
    stage_r_candidates = [row["fqdn"] for row in trace.get("stage_r", {}).get("fqdn_candidates", [])[:5]]
    stage_a = trace.get("stage_a", {})
    lines = [
        f"Stage R: top candidates = {', '.join(stage_r_candidates)}" if stage_r_candidates else "Stage R: no candidates",
        (
            "Stage A: "
            f"primary={stage_a.get('selected_primary_fqdn')} | related={','.join(stage_a.get('selected_related_fqdns', [])) or '-'} | "
            f"confidence={stage_a.get('confidence')} | escalate={bool(stage_a.get('escalate_to_stage_b'))}"
        ),
    ]
    if trace.get("entered_stage_b"):
        stage_b = trace.get("stage_b", {})
        lines.append(
            "Stage B: "
            f"primary={stage_b.get('selected_primary_fqdn')} | related={','.join(stage_b.get('selected_related_fqdns', [])) or '-'} | "
            f"resolved={stage_b.get('resolved')}"
        )
    else:
        lines.append("Stage B: skipped")
    lines.append(
        "Final routing: "
        f"primary={trace.get('final_primary_fqdn')} | related={','.join(trace.get('final_related_fqdns', [])) or '-'} | "
        f"source={trace.get('final_decision_source')} | related_source={trace.get('final_related_source') or '-'}"
    )
    return lines
