from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agentdns_routing.namespace import NamespaceResolver, load_jsonl

FORMAL_DIR = ROOT / 'data' / 'agentdns_routing' / 'formal'
SCHEMA_DIR = ROOT / 'schemas'
ARTIFACT_DIR = ROOT / 'artifacts' / 'dataset'
DESCRIPTOR_PATH = ROOT / 'data' / 'agentdns_routing' / 'namespace_descriptors.jsonl'

DATA_PATH = FORMAL_DIR / 'multi_intent_eval_v1.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'multi_intent_eval_v1_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'multi_intent_eval_v1_coverage.csv'
REPORT_PATH = ARTIFACT_DIR / 'multi_intent_eval_v1_validation_report.json'

OLD_INPUT_FILES = [
    ROOT / 'data' / 'agentdns_routing' / 'dev.jsonl',
    ROOT / 'data' / 'agentdns_routing' / 'test.jsonl',
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_input.jsonl',
    FORMAL_DIR / 'challenge_input.jsonl',
    FORMAL_DIR / 'holdout2_input.jsonl',
    FORMAL_DIR / 'holdout3_input.jsonl',
]
OLD_LABEL_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_labels.jsonl',
    FORMAL_DIR / 'challenge_labels.jsonl',
    FORMAL_DIR / 'holdout2_labels.jsonl',
    FORMAL_DIR / 'holdout3_labels.jsonl',
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def load_schema(path: Path) -> Draft202012Validator:
    return Draft202012Validator(load_json(path))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def validate_rows(rows: list[dict[str, Any]], validator: Draft202012Validator, errors: list[str]) -> None:
    for idx, row in enumerate(rows, start=1):
        for err in validator.iter_errors(row):
            location = '.'.join(str(x) for x in err.path) or '<root>'
            errors.append(f'multi_intent_eval_v1 第 {idx} 行 schema 校验失败: {location}: {err.message}')


def intent_bucket(intent_count: int) -> str:
    if intent_count == 1:
        return 'single'
    if intent_count == 2:
        return 'double'
    if intent_count == 3:
        return 'triple'
    return 'four_plus'


def compute_stats(resolver: NamespaceResolver, rows: list[dict[str, Any]]) -> dict[str, Any]:
    intent_count_counts = Counter(row['intent_count_bucket'] for row in rows)
    domain_mix_counts = Counter(row['domain_mix'] for row in rows)
    gold_counter: Counter[str] = Counter()
    l1_counter: Counter[str] = Counter()
    multi_intent_rows = 0
    for row in rows:
        if row['intent_count'] > 1:
            multi_intent_rows += 1
        for fqdn in row['gold_intent_fqdns']:
            gold_counter[fqdn] += 1
            node = resolver.get_node(fqdn)
            if node:
                l1_counter[node.l1] += 1
    return {
        'total_samples': len(rows),
        'single_intent_samples': intent_count_counts['single'],
        'multi_intent_samples': multi_intent_rows,
        'intent_count_counts': dict(intent_count_counts),
        'domain_mix_counts': dict(domain_mix_counts),
        'total_gold_mentions': sum(gold_counter.values()),
        'distinct_gold_fqdn': len(gold_counter),
        'max_gold_intents_per_sample': max(row['intent_count'] for row in rows),
        'gold_fqdn_counts': dict(sorted(gold_counter.items())),
        'gold_l1_counts': dict(sorted(l1_counter.items())),
    }


def compute_coverage(resolver: NamespaceResolver, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    gold_counter: Counter[str] = Counter()
    bucket_by_fqdn: dict[str, set[str]] = defaultdict(set)
    domain_by_fqdn: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for fqdn in row['gold_intent_fqdns']:
            gold_counter[fqdn] += 1
            bucket_by_fqdn[fqdn].add(row['intent_count_bucket'])
            domain_by_fqdn[fqdn].add(row['domain_mix'])

    output: list[dict[str, str]] = []
    for fqdn in sorted(gold_counter):
        node = resolver.get_node(fqdn)
        output.append(
            {
                'fqdn': fqdn,
                'l1': node.l1 if node else '',
                'l2': node.l2 or '' if node else '',
                'gold_mention_count': str(gold_counter[fqdn]),
                'intent_count_buckets': ';'.join(sorted(bucket_by_fqdn[fqdn])),
                'domain_mixes': ';'.join(sorted(domain_by_fqdn[fqdn])),
            }
        )
    return output


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    rows = load_jsonl(DATA_PATH)
    manifest = load_json(MANIFEST_PATH)
    coverage_rows = load_csv(COVERAGE_PATH)
    schema = load_schema(SCHEMA_DIR / 'multi_intent_eval_sample.schema.json')

    errors: list[str] = []
    warnings: list[str] = []

    validate_rows(rows, schema, errors)

    ids = [row['id'] for row in rows]
    if len(ids) != len(set(ids)):
        errors.append('multi_intent_eval_v1 存在重复 id')
    if len({row['query'] for row in rows}) != len(rows):
        errors.append('multi_intent_eval_v1 存在重复 query')
    if len({row['family_id'] for row in rows}) != len(rows):
        errors.append('multi_intent_eval_v1 存在重复 family_id')

    old_queries: set[str] = set()
    for path in OLD_INPUT_FILES:
        if path.exists():
            for row in load_jsonl(path):
                query = row.get('query')
                if query:
                    old_queries.add(query)
    overlap_queries = sorted(old_queries.intersection({row['query'] for row in rows}))
    if overlap_queries:
        errors.append(f'multi_intent_eval_v1 query 与已有主/holdout 集合重复: {overlap_queries[:5]}')

    old_families: set[str] = set()
    for path in OLD_LABEL_FILES:
        if path.exists():
            for row in load_jsonl(path):
                family_id = row.get('family_id')
                if family_id:
                    old_families.add(family_id)
    overlap_families = sorted(old_families.intersection({row['family_id'] for row in rows}))
    if overlap_families:
        errors.append(f'multi_intent_eval_v1 family_id 与已有集合重复: {overlap_families[:5]}')

    for row in rows:
        golds = row['gold_intent_fqdns']
        if row['intent_count'] != len(golds):
            errors.append(f'{row["id"]} intent_count 与 gold_intent_fqdns 长度不一致')
        if row['intent_count_bucket'] != intent_bucket(len(golds)):
            errors.append(f'{row["id"]} intent_count_bucket 与 gold 数量不一致')
        if len(golds) != len(set(golds)):
            errors.append(f'{row["id"]} gold_intent_fqdns 存在重复项')
        for fqdn in golds:
            if not resolver.has_fqdn(fqdn):
                errors.append(f'{row["id"]} gold fqdn 不在 namespace catalog: {fqdn}')

    stats = compute_stats(resolver, rows)
    if stats != manifest.get('stats'):
        errors.append('multi_intent_eval_v1 manifest stats 与回算结果不一致')

    recomputed_coverage = compute_coverage(resolver, rows)
    if recomputed_coverage != coverage_rows:
        errors.append('multi_intent_eval_v1 coverage csv 与回算结果不一致')

    expected_counts = {'single': 20, 'double': 60, 'triple': 32, 'four_plus': 8}
    if stats['intent_count_counts'] != expected_counts:
        errors.append(f'multi_intent_eval_v1 intent_count_counts 不符合 v1 目标: {stats["intent_count_counts"]}')
    if stats['distinct_gold_fqdn'] != 25:
        errors.append(f'multi_intent_eval_v1 未覆盖全部 25 个 base fqdn: {stats["distinct_gold_fqdn"]}')
    if stats['multi_intent_samples'] != 100:
        errors.append(f'multi_intent_eval_v1 multi-intent 样本数应为 100，实际 {stats["multi_intent_samples"]}')

    report = {
        'ok': not errors,
        'errors': errors,
        'warnings': warnings,
        'dataset_version': manifest.get('dataset_version'),
        'namespace_version': manifest.get('namespace_version'),
        'stats': stats,
        'checks': {
            'schema_valid': not any('schema 校验失败' in error for error in errors),
            'query_text_disjoint': not overlap_queries,
            'family_disjoint': not overlap_families,
            'coverage_csv_matches': recomputed_coverage == coverage_rows,
            'manifest_stats_match': stats == manifest.get('stats'),
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
