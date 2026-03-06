from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FQDN_RE = re.compile(r"^(?:[a-z0-9-]+\.){1,3}cn$")


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def normalize_fqdn(value: str) -> str:
    return value.strip().lower()


def validate_fqdn(value: str) -> bool:
    return bool(FQDN_RE.match(normalize_fqdn(value)))


@dataclass(frozen=True)
class RoutingNode:
    namespace_version: str
    fqdn: str
    node_kind: str
    l1: str
    l2: str | None
    segment: str | None
    parent_fqdn: str | None
    fallback_to: str | None
    aliases: tuple[str, ...]
    desc: str
    examples: tuple[str, ...]
    industry_tags: tuple[str, ...]
    risk_tags: tuple[str, ...]
    action_tags: tuple[str, ...]
    object_tags: tuple[str, ...]
    allowed_l3: tuple[str, ...]

    @property
    def depth(self) -> int:
        if self.segment:
            return 3
        if self.l2:
            return 2
        return 1

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["depth"] = self.depth
        return row


class NamespaceResolver:
    """Canonicalizes routing_fqdn and materializes l3 nodes from descriptor segments."""

    def __init__(self, descriptors: list[dict[str, Any]]):
        self._descriptors = descriptors
        self._nodes: dict[str, RoutingNode] = {}
        self._base_to_segments: dict[str, list[str]] = {}
        self.namespace_version = descriptors[0]["namespace_version"] if descriptors else "unknown"
        self._materialize_catalog()

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "NamespaceResolver":
        return cls(load_jsonl(path))

    def _materialize_catalog(self) -> None:
        for descriptor in self._descriptors:
            base_fqdn = normalize_fqdn(descriptor["fqdn"])
            base_node = RoutingNode(
                namespace_version=descriptor["namespace_version"],
                fqdn=base_fqdn,
                node_kind="base",
                l1=descriptor["l1"],
                l2=descriptor.get("l2"),
                segment=None,
                parent_fqdn=None,
                fallback_to=descriptor.get("fallback_to"),
                aliases=tuple(descriptor.get("aliases", [])),
                desc=descriptor.get("desc", ""),
                examples=tuple(descriptor.get("examples", [])),
                industry_tags=tuple(descriptor.get("industry_tags", [])),
                risk_tags=tuple(descriptor.get("risk_tags", [])),
                action_tags=tuple(descriptor.get("action_tags", [])),
                object_tags=tuple(descriptor.get("object_tags", [])),
                allowed_l3=tuple(descriptor.get("allowed_l3", [])),
            )
            self._nodes[base_fqdn] = base_node

            segment_fqdns: list[str] = []
            for segment, meta in descriptor.get("segments", {}).items():
                segment_fqdn = self.canonicalize_segment(base_fqdn, segment)
                segment_fqdns.append(segment_fqdn)
                self._nodes[segment_fqdn] = RoutingNode(
                    namespace_version=descriptor["namespace_version"],
                    fqdn=segment_fqdn,
                    node_kind="segment",
                    l1=descriptor["l1"],
                    l2=descriptor.get("l2"),
                    segment=segment,
                    parent_fqdn=base_fqdn,
                    fallback_to=base_fqdn,
                    aliases=tuple(_dedupe_keep_order(list(meta.get("aliases", [])))),
                    desc=meta.get("desc", descriptor.get("desc", "")),
                    examples=tuple(descriptor.get("examples", [])),
                    industry_tags=tuple(descriptor.get("industry_tags", [])),
                    risk_tags=tuple(descriptor.get("risk_tags", [])),
                    action_tags=tuple(descriptor.get("action_tags", [])),
                    object_tags=tuple(descriptor.get("object_tags", [])),
                    allowed_l3=tuple(),
                )
            self._base_to_segments[base_fqdn] = segment_fqdns

    def iter_nodes(self) -> list[RoutingNode]:
        return list(self._nodes.values())

    def export_catalog_rows(self) -> list[dict[str, Any]]:
        return [node.to_dict() for node in sorted(self._nodes.values(), key=lambda node: (node.depth, node.fqdn))]

    def has_fqdn(self, fqdn: str) -> bool:
        return normalize_fqdn(fqdn) in self._nodes

    def get_node(self, fqdn: str) -> RoutingNode | None:
        return self._nodes.get(normalize_fqdn(fqdn))

    def canonicalize_fqdn(self, fqdn: str) -> str:
        normalized = normalize_fqdn(fqdn)
        if normalized not in self._nodes:
            raise KeyError(f"Unknown routing_fqdn: {fqdn}")
        return normalized

    def canonicalize_segment(self, base_fqdn: str, segment: str) -> str:
        return f"{normalize_fqdn(segment)}.{normalize_fqdn(base_fqdn)}"

    def parent_fallback(self, fqdn: str) -> str | None:
        node = self.get_node(fqdn)
        if not node:
            return None
        if node.parent_fqdn:
            return node.parent_fqdn
        return node.fallback_to

    def fallback_chain(self, fqdn: str) -> list[str]:
        chain: list[str] = []
        current = self.parent_fallback(fqdn)
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            chain.append(current)
            current = self.parent_fallback(current)
        return chain

    def segments_for_base(self, base_fqdn: str) -> list[str]:
        return list(self._base_to_segments.get(normalize_fqdn(base_fqdn), []))
