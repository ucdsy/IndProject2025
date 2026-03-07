from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FORMAL_INPUTS = [
    ROOT / "data" / "agentdns_routing" / "formal" / "dev.jsonl",
    ROOT / "data" / "agentdns_routing" / "formal" / "blind_input.jsonl",
    ROOT / "data" / "agentdns_routing" / "formal" / "challenge_input.jsonl",
]
DESCRIPTORS = ROOT / "data" / "agentdns_routing" / "namespace_descriptors.jsonl"
LEXICON = ROOT / "data" / "agentdns_routing" / "evidence_lexicon.json"
ARTIFACT_DIR = ROOT / "artifacts" / "dataset"
JSON_OUT = ARTIFACT_DIR / "knowledge_source_audit.json"
MD_OUT = ARTIFACT_DIR / "knowledge_source_audit.md"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def hit_ids(phrase: str, queries: list[dict[str, str]]) -> list[str]:
    return [row["id"] for row in queries if phrase and phrase in row["query"]]


def main() -> None:
    queries: list[dict[str, str]] = []
    for path in FORMAL_INPUTS:
        for row in load_jsonl(path):
            queries.append({"id": row["id"], "query": row["query"], "split": path.stem})

    descriptors = load_jsonl(DESCRIPTORS)
    lexicon = json.loads(LEXICON.read_text(encoding="utf-8")) if LEXICON.exists() else {}

    descriptor_phrase_bank: set[str] = set()
    descriptor_alias_hits: list[dict[str, Any]] = []
    descriptor_example_hits: list[dict[str, Any]] = []
    segment_alias_hits: list[dict[str, Any]] = []

    for row in descriptors:
        fqdn = row["fqdn"]
        for alias in row.get("aliases", []):
            descriptor_phrase_bank.add(alias)
            ids = hit_ids(alias, queries)
            if ids:
                descriptor_alias_hits.append(
                    {"fqdn": fqdn, "phrase": alias, "hits": len(ids), "sample_ids": ids[:5]}
                )
        for example in row.get("examples", []):
            descriptor_phrase_bank.add(example)
            ids = hit_ids(example, queries)
            if ids:
                descriptor_example_hits.append(
                    {"fqdn": fqdn, "phrase": example, "hits": len(ids), "sample_ids": ids[:5]}
                )
        for segment, spec in row.get("segments", {}).items():
            for alias in spec.get("aliases", []):
                descriptor_phrase_bank.add(alias)
                ids = hit_ids(alias, queries)
                if ids:
                    segment_alias_hits.append(
                        {
                            "fqdn": fqdn,
                            "segment": segment,
                            "phrase": alias,
                            "hits": len(ids),
                            "sample_ids": ids[:5],
                        }
                    )

    lexicon_hits: list[dict[str, Any]] = []
    lexicon_hits_outside_descriptors: list[dict[str, Any]] = []
    all_lexicon_phrases: set[str] = set()
    for section, items in lexicon.items():
        for item in items:
            label = item["label"]
            for phrase in item.get("phrases", []):
                all_lexicon_phrases.add(phrase)
                ids = hit_ids(phrase, queries)
                if not ids:
                    continue
                row = {
                    "section": section,
                    "label": label,
                    "phrase": phrase,
                    "hits": len(ids),
                    "sample_ids": ids[:5],
                    "in_descriptors": phrase in descriptor_phrase_bank,
                }
                lexicon_hits.append(row)
                if phrase not in descriptor_phrase_bank:
                    lexicon_hits_outside_descriptors.append(row)

    review_required_aliases = [
        row
        for row in sorted(
            descriptor_alias_hits + [
                {
                    "fqdn": item["fqdn"],
                    "phrase": item["phrase"],
                    "hits": item["hits"],
                    "sample_ids": item["sample_ids"],
                }
                for item in segment_alias_hits
            ],
            key=lambda x: (-x["hits"], -len(x["phrase"]), x["fqdn"], x["phrase"]),
        )
        if len(row["phrase"]) <= 2 and row["hits"] >= 2
    ]

    report = {
        "query_count": len(queries),
        "descriptor_count": len(descriptors),
        "descriptor_phrase_count": len(descriptor_phrase_bank),
        "lexicon_phrase_count": len(all_lexicon_phrases),
        "summary": {
            "descriptor_alias_hit_count": len(descriptor_alias_hits),
            "descriptor_example_hit_count": len(descriptor_example_hits),
            "segment_alias_hit_count": len(segment_alias_hits),
            "lexicon_hit_count": len(lexicon_hits),
            "lexicon_hit_outside_descriptor_count": len(lexicon_hits_outside_descriptors),
        },
        "findings": {
            "descriptor_example_hits": sorted(
                descriptor_example_hits,
                key=lambda x: (-x["hits"], -len(x["phrase"]), x["fqdn"], x["phrase"]),
            ),
            "review_required_short_aliases": review_required_aliases[:20],
            "lexicon_hits_outside_descriptors": sorted(
                lexicon_hits_outside_descriptors,
                key=lambda x: (-x["hits"], -len(x["phrase"]), x["section"], x["label"], x["phrase"]),
            ),
        },
        "decisions": {
            "keep": [
                "namespace/canonical contract",
                "descriptor 中与 l1/l2/l3 命名直接对应的节点别名",
                "fallback chain 与 segment canonical 规则",
            ],
            "downgrade_to_sidecar": [
                "descriptor 里的短且高频的通用词，只能低权重使用",
                "industry/context 类 broad phrase，不得主导 Stage R 主召回",
            ],
            "exclude_from_clean_stage_r": [
                "descriptor examples 不进入 clean Stage R 主索引",
                "旧 bootstrap 词典已从主干清理，不直接进入 clean Stage R",
            ],
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    top_lexicon = report["findings"]["lexicon_hits_outside_descriptors"][:12]
    top_short = report["findings"]["review_required_short_aliases"][:8]
    top_examples = report["findings"]["descriptor_example_hits"][:8]
    lines = [
        "# 知识源泄漏审计",
        "",
        "## 1. 审计范围",
        f"- formal 输入 query 总数: `{len(queries)}`",
        f"- namespace descriptor 数量: `{len(descriptors)}`",
        f"- descriptor 短语总量: `{len(descriptor_phrase_bank)}`",
        f"- lexicon 短语总量: `{len(all_lexicon_phrases)}`",
        "",
        "## 2. 结论",
        "- `namespace/canonical contract` 可以保留。",
        "- `descriptor examples` 已出现与 formal query 的直接重叠，不应进入 clean `Stage R` 主索引。",
        "- 旧 bootstrap 词典已从主干清理；如果未来重新引入词典，必须来自独立术语表并重跑本审计。",
        "- descriptor 中部分短且高频的 alias/segment alias 不构成直接泄漏，但只能做低权重 sidecar，不能作为主召回锚点。",
        "",
        "## 3. 核心统计",
        f"- descriptor alias 命中数: `{report['summary']['descriptor_alias_hit_count']}`",
        f"- descriptor example 命中数: `{report['summary']['descriptor_example_hit_count']}`",
        f"- segment alias 命中数: `{report['summary']['segment_alias_hit_count']}`",
        f"- lexicon 命中数: `{report['summary']['lexicon_hit_count']}`",
        f"- lexicon 中“不在 descriptor 内但命中 formal query”的条目数: `{report['summary']['lexicon_hit_outside_descriptor_count']}`",
        "",
        "## 4. descriptor example 直接重叠",
    ]
    if top_examples:
        for item in top_examples:
            lines.append(
                f"- `{item['fqdn']}`: `{item['phrase']}`，命中 `{item['hits']}` 条，样本示例 `{', '.join(item['sample_ids'])}`"
            )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "## 5. 需降权审查的短高频 alias",
        ]
    )
    for item in top_short:
        lines.append(
            f"- `{item['fqdn']}`: `{item['phrase']}`，命中 `{item['hits']}` 条，样本示例 `{', '.join(item['sample_ids'])}`"
        )

    lines.extend(
        [
            "",
            "## 6. 必须移出 clean Stage R 的 lexicon 条目（节选）",
        ]
    )
    if top_lexicon:
        for item in top_lexicon:
            lines.append(
                f"- `{item['section']}/{item['label']}`: `{item['phrase']}`，命中 `{item['hits']}` 条，样本示例 `{', '.join(item['sample_ids'])}`"
            )
    else:
        lines.append("- 当前仓库已无 bootstrap 词典文件，本节保留作审计占位。")

    lines.extend(
        [
            "",
            "## 7. clean Stage R 输入边界（冻结建议）",
            "- 保留: namespace/canonical contract、descriptor 中与节点命名直接绑定的 aliases、segment canonical 规则、fallback chain。",
            "- 低权重 sidecar: descriptor 中短且泛化强的 alias，例如 `安排`、`日志`、`要点`、`北京/成都/杭州` 之外的通用短词。",
            "- 排除: descriptor examples、任何直接由 gold query 反推出来的 bootstrap 词典。",
            "- 若后续需要恢复词典，必须从独立术语表重新生成，并重新跑本审计脚本。",
        ]
    )
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(JSON_OUT), "markdown": str(MD_OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
