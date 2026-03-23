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

INPUT_PATH = FORMAL_DIR / 'holdout2_input.jsonl'
LABEL_PATH = FORMAL_DIR / 'holdout2_labels.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'holdout2_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'holdout2_coverage_status.csv'
REPORT_PATH = ARTIFACT_DIR / 'holdout2_validation_report.json'

FORMAL_INPUT_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_input.jsonl',
    FORMAL_DIR / 'challenge_input.jsonl',
]
FORMAL_LABEL_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_labels.jsonl',
    FORMAL_DIR / 'challenge_labels.jsonl',
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def load_schema(path: Path) -> Draft202012Validator:
    return Draft202012Validator(load_json(path))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def validate_rows(rows: list[dict[str, Any]], validator: Draft202012Validator, file_label: str, errors: list[str]) -> None:
    for idx, row in enumerate(rows, start=1):
        for err in validator.iter_errors(row):
            location = '.'.join(str(x) for x in err.path) or '<root>'
            errors.append(f'{file_label} 第 {idx} 行 schema 校验失败: {location}: {err.message}')


def normalize_base_fqdn(fqdn: str) -> str:
    parts = fqdn.split('.')
    return '.'.join(parts[1:]) if len(parts) == 4 else fqdn


def almost_equal(left: float, right: float, tol: float = 1e-6) -> bool:
    return abs(left - right) <= tol


def recompute_stats(
    resolver: NamespaceResolver,
    input_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    bucket_counts = Counter(row['source_bucket'] for row in input_rows)
    distinct_base = {normalize_base_fqdn(row['ground_truth_fqdn']) for row in label_rows}
    l3_hits = 0
    note_hits = 0
    high_risk_hits = 0
    multi_intent_hits = 0
    for row in label_rows:
        node = resolver.get_node(row['ground_truth_fqdn'])
        if node and node.segment:
            l3_hits += 1
        if row.get('notes_for_audit', '').strip():
            note_hits += 1
        if row.get('high_risk_case'):
            high_risk_hits += 1
        if row.get('secondary_intent_present'):
            multi_intent_hits += 1

    total = len(label_rows)
    return {
        'total_samples': total,
        'distinct_base_fqdn': len(distinct_base),
        'l3_ratio': round(l3_hits / max(total, 1), 4),
        'multi_intent_ratio': round(multi_intent_hits / max(total, 1), 4),
        'source_bucket_counts': dict(bucket_counts),
        'high_risk_case_count': high_risk_hits,
        'notes_for_audit_nonempty_ratio': round(note_hits / max(total, 1), 4),
        'ood_like_count': 0,
    }


def recompute_coverage(
    resolver: NamespaceResolver,
    input_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    bucket_by_base: dict[str, set[str]] = defaultdict(set)
    sample_count_by_base: Counter[str] = Counter()
    l3_count_by_base: Counter[str] = Counter()

    input_by_id = {row['id']: row for row in input_rows}
    for row in label_rows:
        gt = row['ground_truth_fqdn']
        base = normalize_base_fqdn(gt)
        sample_count_by_base[base] += 1
        input_row = input_by_id[row['id']]
        bucket_by_base[base].add(input_row['source_bucket'])
        node = resolver.get_node(gt)
        if node and node.segment:
            l3_count_by_base[base] += 1

    coverage_rows: list[dict[str, str]] = []
    for base in sorted(sample_count_by_base):
        node = resolver.get_node(base)
        coverage_rows.append(
            {
                'base_fqdn': base,
                'l1': node.l1 if node else '',
                'l2': node.l2 or '' if node else '',
                'sample_count': str(sample_count_by_base[base]),
                'l3_sample_count': str(l3_count_by_base[base]),
                'bucket_summary': ';'.join(sorted(bucket_by_base[base])),
            }
        )
    return coverage_rows


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    input_rows = load_jsonl(INPUT_PATH)
    label_rows = load_jsonl(LABEL_PATH)
    manifest = load_json(MANIFEST_PATH)
    coverage_rows = load_csv(COVERAGE_PATH)

    input_validator = load_schema(SCHEMA_DIR / 'holdout2_input_sample.schema.json')
    label_validator = load_schema(SCHEMA_DIR / 'holdout2_label_sample.schema.json')

    errors: list[str] = []
    warnings: list[str] = []

    validate_rows(input_rows, input_validator, 'holdout2_input', errors)
    validate_rows(label_rows, label_validator, 'holdout2_labels', errors)

    input_ids = [row['id'] for row in input_rows]
    label_ids = [row['id'] for row in label_rows]
    if input_ids != label_ids:
        errors.append('holdout2_input 与 holdout2_labels 的样本 id 顺序或集合不一致')
    if len(set(input_ids)) != len(input_ids):
        errors.append('holdout2_input 存在重复样本 id')
    if len({row['query'] for row in input_rows}) != len(input_rows):
        errors.append('holdout2_input 存在重复 query 文本')

    formal_families: set[str] = set()
    for path in FORMAL_LABEL_FILES:
        for row in load_jsonl(path):
            family_id = row.get('family_id')
            if family_id:
                formal_families.add(family_id)
    holdout_families = [row['family_id'] for row in label_rows]
    overlap_families = sorted(formal_families.intersection(holdout_families))
    if overlap_families:
        errors.append(f'holdout2 family_id 与 formal 已有 split 重叠: {overlap_families}')

    formal_queries: set[str] = set()
    for path in FORMAL_INPUT_FILES:
        for row in load_jsonl(path):
            formal_queries.add(row['query'])
    overlap_queries = sorted(formal_queries.intersection({row['query'] for row in input_rows}))
    if overlap_queries:
        errors.append('holdout2 query 与 formal 现有 split 存在完全重复文本')

    input_by_id = {row['id']: row for row in input_rows}
    for row in label_rows:
        sample_id = row['id']
        gt = row['ground_truth_fqdn']
        if not resolver.has_fqdn(gt):
            errors.append(f'样本 {sample_id} 的 ground_truth_fqdn 不在 namespace catalog 中: {gt}')
            continue
        node = resolver.get_node(gt)
        expected_granularity = 'segment' if node and node.segment else 'base'
        if row['primary_granularity'] != expected_granularity:
            errors.append(f'样本 {sample_id} 的 primary_granularity 与 ground truth 深度不一致')

        base = normalize_base_fqdn(gt)
        input_row = input_by_id.get(sample_id)
        if input_row is None:
            continue
        metadata = input_row.get('metadata') or {}
        if metadata.get('base_fqdn') != base:
            errors.append(f'样本 {sample_id} 的 metadata.base_fqdn={metadata.get("base_fqdn")}，期望为 {base}')
        if metadata.get('primary_granularity') != row['primary_granularity']:
            errors.append(f'样本 {sample_id} 的 metadata.primary_granularity 与 labels 不一致')
        if input_row.get('namespace_version') != manifest['namespace_version']:
            errors.append(f'样本 {sample_id} 的 namespace_version 与 manifest 不一致')

        acceptable = row.get('acceptable_fqdns', [])
        relevant = row.get('relevant_fqdns', [])
        if gt not in acceptable:
            errors.append(f'样本 {sample_id} 的 acceptable_fqdns 未包含 ground_truth_fqdn')
        for fqdn in acceptable + relevant:
            if not resolver.has_fqdn(fqdn):
                errors.append(f'样本 {sample_id} 的标签字段包含未知 fqdn: {fqdn}')
        if gt in relevant:
            errors.append(f'样本 {sample_id} 的 relevant_fqdns 不应包含 ground_truth_fqdn')
        if row['secondary_intent_present'] != bool(relevant):
            errors.append(f'样本 {sample_id} 的 secondary_intent_present 与 relevant_fqdns 不一致')
        if bool(relevant) != ('multi_intent' in row.get('intended_confusion_types', [])):
            errors.append(f'样本 {sample_id} 的 intended_confusion_types 与 secondary intent 标记不一致')
        if row['primary_granularity'] == 'segment' and base not in acceptable:
            errors.append(f'样本 {sample_id} 的 acceptable_fqdns 未包含 base fallback')
        if input_row.get('difficulty_tag') != input_row.get('source_bucket'):
            warnings.append(f'样本 {sample_id} 的 difficulty_tag 与 source_bucket 不一致')

    stats = recompute_stats(resolver, input_rows, label_rows)
    target_total_range = manifest['targets']['total_range']
    if not (target_total_range[0] <= stats['total_samples'] <= target_total_range[1]):
        errors.append(f'holdout2 总量越界: {stats["total_samples"]}')
    if stats['distinct_base_fqdn'] < manifest['targets']['min_distinct_base_fqdn']:
        errors.append(
            f'holdout2 base_fqdn 覆盖不足: {stats["distinct_base_fqdn"]} < {manifest["targets"]["min_distinct_base_fqdn"]}'
        )
    if stats['l3_ratio'] < manifest['targets']['l3_ratio_min']:
        errors.append(f'holdout2 l3_ratio 过低: {stats["l3_ratio"]}')
    lower, upper = manifest['targets']['multi_intent_ratio_range']
    if not (lower <= stats['multi_intent_ratio'] <= upper):
        errors.append(f'holdout2 multi_intent_ratio 越界: {stats["multi_intent_ratio"]}')
    if stats['notes_for_audit_nonempty_ratio'] >= manifest['targets']['notes_for_audit_nonempty_ratio_max']:
        errors.append(
            'holdout2 notes_for_audit 非空比例过高: '
            f'{stats["notes_for_audit_nonempty_ratio"]} >= {manifest["targets"]["notes_for_audit_nonempty_ratio_max"]}'
        )

    target_buckets = manifest['targets']['bucket_targets']
    for bucket, target in target_buckets.items():
        observed = stats['source_bucket_counts'].get(bucket, 0)
        if observed < target:
            errors.append(f'bucket {bucket} 未达到最小配额: {observed} < {target}')

    manifest_stats = manifest.get('current_stats', {})
    for field in (
        'total_samples',
        'distinct_base_fqdn',
        'high_risk_case_count',
        'ood_like_count',
        'notes_for_audit_nonempty_ratio',
        'l3_ratio',
        'multi_intent_ratio',
    ):
        expected = stats[field]
        actual = manifest_stats.get(field)
        if isinstance(expected, float):
            if actual is None or not almost_equal(float(actual), expected):
                errors.append(f'manifest.current_stats.{field}={actual}，回算应为 {expected}')
        else:
            if actual != expected:
                errors.append(f'manifest.current_stats.{field}={actual}，回算应为 {expected}')
    if manifest_stats.get('source_bucket_counts') != stats['source_bucket_counts']:
        errors.append('manifest.current_stats.source_bucket_counts 与回算结果不一致')

    recomputed_coverage = recompute_coverage(resolver, input_rows, label_rows)
    if coverage_rows != recomputed_coverage:
        errors.append('holdout2_coverage_status.csv 与回算覆盖统计不一致')

    report = {
        'ok': not errors,
        'errors': errors,
        'warnings': warnings,
        'dataset_version': manifest.get('dataset_version'),
        'namespace_version': manifest.get('namespace_version'),
        'stats': stats,
        'checks': {
            'family_disjoint': not overlap_families,
            'query_text_disjoint': not overlap_queries,
            'schema_valid': not any('schema 校验失败' in item for item in errors),
            'coverage_csv_matches': coverage_rows == recomputed_coverage,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
