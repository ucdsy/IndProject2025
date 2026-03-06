#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentdns_routing.namespace import NamespaceResolver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export canonical routing catalog materialized from namespace descriptors.")
    parser.add_argument(
        "--descriptors",
        default=str(ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "artifacts" / "namespace" / "routing_catalog.ns_v1_20260311.jsonl"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolver = NamespaceResolver.from_jsonl(args.descriptors)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = resolver.export_catalog_rows()
    with output.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                "namespace_version": resolver.namespace_version,
                "nodes": len(rows),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

