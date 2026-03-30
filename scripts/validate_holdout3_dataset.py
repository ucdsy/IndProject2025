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

INPUT_PATH = FORMAL_DIR / 'holdout3_input.jsonl'
LABEL_PATH = FORMAL_DIR / 'holdout3_labels.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'holdout3_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'holdout3_coverage_status.csv'
SKELETON_AUDIT_PATH = FORMAL_DIR / 'holdout3_skeleton_audit.csv'
REPORT_PATH = ARTIFACT_DIR / 'holdout3_validation_report.json'

OLD_LABEL_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_labels.jsonl',
    FORMAL_DIR / 'challenge_labels.jsonl',
    FORMAL_DIR / 'holdout2_labels.jsonl',
]
OLD_INPUT_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_input.jsonl',
    FORMAL_DIR / 'challenge_input.jsonl',
    FORMAL_DIR / 'holdout2_input.jsonl',
]
BANNED_OLD_MARKERS = (
    '我们正在推进',
    '接下来要推进',
    '如果接下来要推进',
    '场景是“',
    '我手上这个请求是',
    '把问题说直白一点',
    '先看这个场景',
    '先围绕“',
    '这件事的主线还是',
    '先别发散',
    '围绕“',
    '准备落地，但我更担心风险边界',
    '别先谈实现',
    '如果现在只落一个入口',
    '顺手也把',
)
CITY_NORMALIZERS = {
    '北京': 'beijing',
    'beijing': 'beijing',
    '上海': 'shanghai',
    'shanghai': 'shanghai',
    '成都': 'chengdu',
    'chengdu': 'chengdu',
    '西安': 'xian',
    'xian': 'xian',
    "xi'an": 'xian',
    '杭州': 'hangzhou',
    'hangzhou': 'hangzhou',
    '广州': 'guangzhou',
    'guangzhou': 'guangzhou',
    '深圳': 'shenzhen',
    'shenzhen': 'shenzhen',
    '云南': 'yunnan',
    'yunnan': 'yunnan',
}


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


def normalize_city(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return CITY_NORMALIZERS.get(normalized, normalized or None)


def recompute_stats(
    resolver: NamespaceResolver,
    input_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    skeleton_rows: list[dict[str, str]],
) -> dict[str, Any]:
    eval_bucket_counts = Counter(row['eval_bucket'] for row in label_rows)
    intent_form_counts = Counter(row['intent_form'] for row in input_rows)
    surface_style_counts = Counter(row['surface_style'] for row in input_rows)
    l1_counts: Counter[str] = Counter()
    distinct_base = set()
    l3_hits = 0
    high_risk_hits = 0
    multi_intent_hits = 0
    skeleton_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)

    label_by_id = {row['id']: row for row in label_rows}
    for row in label_rows:
        gt = row['ground_truth_fqdn']
        node = resolver.get_node(gt)
        base = normalize_base_fqdn(gt)
        distinct_base.add(base)
        if node and node.segment:
            l3_hits += 1
        if row.get('high_risk_case'):
            high_risk_hits += 1
        if row.get('secondary_intent_present'):
            multi_intent_hits += 1
        base_node = resolver.get_node(base)
        if base_node:
            l1_counts[base_node.l1] += 1

    for row in skeleton_rows:
        label = label_by_id.get(row['id'])
        if label:
            skeleton_by_bucket[label['eval_bucket']][row['query_skeleton_id']] += 1

    total = len(label_rows)
    max_bucket_skeleton_share = max(
        (max(counter.values()) / max(sum(counter.values()), 1)) for counter in skeleton_by_bucket.values()
    )
    overlap_count = sum(1 for row in skeleton_rows if str(row.get('skeleton_overlap_flag', '')).strip().lower() == 'true')

    return {
        'total_samples': total,
        'distinct_base_fqdn': len(distinct_base),
        'l3_ratio': round(l3_hits / max(total, 1), 4),
        'multi_intent_ratio': round(multi_intent_hits / max(total, 1), 4),
        'high_risk_case_count': high_risk_hits,
        'eval_bucket_counts': dict(eval_bucket_counts),
        'intent_form_counts': dict(intent_form_counts),
        'surface_style_counts': dict(surface_style_counts),
        'l1_counts': dict(l1_counts),
        'max_l1_ratio': round(max(l1_counts.values()) / max(total, 1), 4),
        'max_bucket_skeleton_share': round(max_bucket_skeleton_share, 4),
        'skeleton_overlap_flag_count': overlap_count,
        'ood_like_count': 0,
    }


def recompute_coverage(resolver: NamespaceResolver, input_rows: list[dict[str, Any]], label_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    bucket_by_base: dict[str, set[str]] = defaultdict(set)
    intent_by_base: dict[str, set[str]] = defaultdict(set)
    style_by_base: dict[str, set[str]] = defaultdict(set)
    sample_count_by_base: Counter[str] = Counter()
    l3_count_by_base: Counter[str] = Counter()

    input_by_id = {row['id']: row for row in input_rows}
    for row in label_rows:
        gt = row['ground_truth_fqdn']
        base = normalize_base_fqdn(gt)
        sample_count_by_base[base] += 1
        input_row = input_by_id[row['id']]
        bucket_by_base[base].add(input_row['source_bucket'])
        intent_by_base[base].add(input_row['intent_form'])
        style_by_base[base].add(input_row['surface_style'])
        node = resolver.get_node(gt)
        if node and node.segment:
            l3_count_by_base[base] += 1

    rows: list[dict[str, str]] = []
    for base in sorted(sample_count_by_base):
        node = resolver.get_node(base)
        rows.append(
            {
                'base_fqdn': base,
                'l1': node.l1 if node else '',
                'l2': node.l2 or '' if node else '',
                'sample_count': str(sample_count_by_base[base]),
                'l3_sample_count': str(l3_count_by_base[base]),
                'eval_bucket_summary': ';'.join(sorted(bucket_by_base[base])),
                'intent_form_summary': ';'.join(sorted(intent_by_base[base])),
                'surface_style_summary': ';'.join(sorted(style_by_base[base])),
            }
        )
    return rows


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    input_rows = load_jsonl(INPUT_PATH)
    label_rows = load_jsonl(LABEL_PATH)
    manifest = load_json(MANIFEST_PATH)
    coverage_rows = load_csv(COVERAGE_PATH)
    skeleton_rows = load_csv(SKELETON_AUDIT_PATH)

    input_validator = load_schema(SCHEMA_DIR / 'holdout3_input_sample.schema.json')
    label_validator = load_schema(SCHEMA_DIR / 'holdout3_label_sample.schema.json')

    errors: list[str] = []
    warnings: list[str] = []

    validate_rows(input_rows, input_validator, 'holdout3_input', errors)
    validate_rows(label_rows, label_validator, 'holdout3_labels', errors)

    input_ids = [row['id'] for row in input_rows]
    label_ids = [row['id'] for row in label_rows]
    audit_ids = [row['id'] for row in skeleton_rows]
    if input_ids != label_ids:
        errors.append('holdout3_input 与 holdout3_labels 的样本 id 顺序或集合不一致')
    if input_ids != audit_ids:
        errors.append('holdout3_input 与 holdout3_skeleton_audit 的样本 id 顺序或集合不一致')
    if len(set(input_ids)) != len(input_ids):
        errors.append('holdout3_input 存在重复样本 id')
    if len({row['query'] for row in input_rows}) != len(input_rows):
        errors.append('holdout3_input 存在重复 query 文本')

    old_families: set[str] = set()
    for path in OLD_LABEL_FILES:
        for row in load_jsonl(path):
            family_id = row.get('family_id')
            if family_id:
                old_families.add(family_id)
    overlap_families = sorted(old_families.intersection({row['family_id'] for row in label_rows}))
    if overlap_families:
        errors.append(f'holdout3 family_id 与已揭盲 split 重叠: {overlap_families}')

    old_queries: set[str] = set()
    for path in OLD_INPUT_FILES:
        for row in load_jsonl(path):
            old_queries.add(row['query'])
    overlap_queries = sorted(old_queries.intersection({row['query'] for row in input_rows}))
    if overlap_queries:
        errors.append('holdout3 query 与旧 split 存在完全重复文本')

    input_by_id = {row['id']: row for row in input_rows}
    label_by_id = {row['id']: row for row in label_rows}
    audit_by_id = {row['id']: row for row in skeleton_rows}

    required_audit_columns = {
        'id',
        'family_id',
        'eval_bucket',
        'intent_form',
        'surface_style',
        'query_skeleton_id',
        'suspected_nearby_old_family',
        'skeleton_overlap_flag',
        'auditor_note',
    }
    if skeleton_rows:
        missing_columns = required_audit_columns.difference(skeleton_rows[0].keys())
        if missing_columns:
            errors.append(f'holdout3_skeleton_audit.csv 缺少列: {sorted(missing_columns)}')

    for row in input_rows:
        if any(marker in row['query'] for marker in BANNED_OLD_MARKERS):
            errors.append(f'样本 {row["id"]} 仍命中旧 skeleton marker')

    for row in label_rows:
        sample_id = row['id']
        input_row = input_by_id.get(sample_id)
        audit_row = audit_by_id.get(sample_id)
        gt = row['ground_truth_fqdn']
        if not resolver.has_fqdn(gt):
            errors.append(f'样本 {sample_id} 的 ground_truth_fqdn 不在 namespace catalog 中: {gt}')
            continue

        node = resolver.get_node(gt)
        base = normalize_base_fqdn(gt)
        expected_granularity = 'segment' if node and node.segment else 'base'
        if row['primary_granularity'] != expected_granularity:
            errors.append(f'样本 {sample_id} 的 primary_granularity 与 ground truth 深度不一致')

        if input_row is None:
            continue
        metadata = input_row.get('metadata') or {}
        if metadata.get('base_fqdn') != base:
            errors.append(f'样本 {sample_id} 的 metadata.base_fqdn={metadata.get("base_fqdn")}，期望为 {base}')
        if metadata.get('primary_granularity') != row['primary_granularity']:
            errors.append(f'样本 {sample_id} 的 metadata.primary_granularity 与 labels 不一致')
        if input_row['namespace_version'] != manifest['namespace_version']:
            errors.append(f'样本 {sample_id} 的 namespace_version 与 manifest 不一致')
        if input_row['source_bucket'] != row['eval_bucket']:
            errors.append(f'样本 {sample_id} 的 source_bucket 与 eval_bucket 不一致')
        if input_row['difficulty_tag'] != row['eval_bucket']:
            warnings.append(f'样本 {sample_id} 的 difficulty_tag 与 eval_bucket 不一致')
        if input_row['intent_form'] != row['intent_form']:
            errors.append(f'样本 {sample_id} 的 intent_form input/label 不一致')
        if input_row['surface_style'] != row['surface_style']:
            errors.append(f'样本 {sample_id} 的 surface_style input/label 不一致')

        acceptable = row.get('acceptable_fqdns', [])
        relevant = row.get('relevant_fqdns', [])
        if gt not in acceptable:
            errors.append(f'样本 {sample_id} 的 acceptable_fqdns 未包含 ground_truth_fqdn')
        if row['primary_granularity'] == 'segment' and base not in acceptable:
            errors.append(f'样本 {sample_id} 的 acceptable_fqdns 未包含 base fallback')
        for fqdn in acceptable + relevant:
            if not resolver.has_fqdn(fqdn):
                errors.append(f'样本 {sample_id} 的标签字段包含未知 fqdn: {fqdn}')
        if gt in relevant:
            errors.append(f'样本 {sample_id} 的 relevant_fqdns 不应包含 ground_truth_fqdn')
        if row['secondary_intent_present'] != bool(relevant):
            errors.append(f'样本 {sample_id} 的 secondary_intent_present 与 relevant_fqdns 不一致')
        if bool(relevant) != ('multi_intent' in row['bucket_tags']):
            errors.append(f'样本 {sample_id} 的 bucket_tags 与 secondary intent 标记不一致')
        if not row['bucket_tags']:
            errors.append(f'样本 {sample_id} 的 bucket_tags 为空')

        if node and node.segment and base in {'hotel.travel.cn', 'itinerary.travel.cn'}:
            context_city = normalize_city((input_row.get('context') or {}).get('city'))
            if context_city and context_city != node.segment:
                errors.append(f'样本 {sample_id} 的 city={input_row.get("context", {}).get("city")} 与 l3 segment={node.segment} 不一致')

        if audit_row is None:
            errors.append(f'样本 {sample_id} 缺少 skeleton audit 记录')
            continue
        if audit_row['family_id'] != row['family_id']:
            errors.append(f'样本 {sample_id} 的 skeleton audit family_id 不一致')
        if audit_row['eval_bucket'] != row['eval_bucket']:
            errors.append(f'样本 {sample_id} 的 skeleton audit eval_bucket 不一致')
        if audit_row['intent_form'] != row['intent_form']:
            errors.append(f'样本 {sample_id} 的 skeleton audit intent_form 不一致')
        if audit_row['surface_style'] != row['surface_style']:
            errors.append(f'样本 {sample_id} 的 skeleton audit surface_style 不一致')
        if audit_row['query_skeleton_id'] != metadata.get('query_skeleton_id'):
            errors.append(f'样本 {sample_id} 的 skeleton audit query_skeleton_id 与 input metadata 不一致')
        if str(audit_row['skeleton_overlap_flag']).strip().lower() != 'false':
            errors.append(f'样本 {sample_id} 的 skeleton_overlap_flag 不为 false')

    stats = recompute_stats(resolver, input_rows, label_rows, skeleton_rows)
    if stats['total_samples'] != manifest['targets']['total_samples']:
        errors.append(f'holdout3 总量异常: {stats["total_samples"]}')
    if stats['distinct_base_fqdn'] < manifest['targets']['min_distinct_base_fqdn']:
        errors.append(
            f'holdout3 base_fqdn 覆盖不足: {stats["distinct_base_fqdn"]} < {manifest["targets"]["min_distinct_base_fqdn"]}'
        )
    if stats['l3_ratio'] < manifest['targets']['l3_ratio_min']:
        errors.append(f'holdout3 l3_ratio 过低: {stats["l3_ratio"]}')
    lower, upper = manifest['targets']['multi_intent_ratio_range']
    if not (lower <= stats['multi_intent_ratio'] <= upper):
        errors.append(f'holdout3 multi_intent_ratio 越界: {stats["multi_intent_ratio"]}')
    if stats['max_l1_ratio'] > manifest['targets']['max_l1_ratio']:
        errors.append(f'holdout3 max_l1_ratio 越界: {stats["max_l1_ratio"]}')
    if stats['max_bucket_skeleton_share'] > manifest['targets']['max_bucket_skeleton_share']:
        errors.append(f'holdout3 max_bucket_skeleton_share 越界: {stats["max_bucket_skeleton_share"]}')
    if stats['skeleton_overlap_flag_count'] > manifest['targets']['skeleton_overlap_flag_count_max']:
        errors.append(f'holdout3 skeleton_overlap_flag_count 不为 0: {stats["skeleton_overlap_flag_count"]}')

    for bucket, target in manifest['targets']['eval_bucket_counts'].items():
        observed = stats['eval_bucket_counts'].get(bucket, 0)
        if observed != target:
            errors.append(f'eval_bucket {bucket} 样本数不符: {observed} != {target}')
        bucket_forms = {row['intent_form'] for row in label_rows if row['eval_bucket'] == bucket}
        bucket_styles = {row['surface_style'] for row in label_rows if row['eval_bucket'] == bucket}
        if len(bucket_forms) < manifest['targets']['min_intent_forms_per_bucket']:
            errors.append(f'eval_bucket {bucket} 的 intent_form 覆盖不足: {len(bucket_forms)}')
        if len(bucket_styles) < manifest['targets']['min_surface_styles_per_bucket']:
            errors.append(f'eval_bucket {bucket} 的 surface_style 覆盖不足: {len(bucket_styles)}')

    for intent_form, target in manifest['targets']['intent_form_counts'].items():
        observed = stats['intent_form_counts'].get(intent_form, 0)
        if observed != target:
            errors.append(f'intent_form {intent_form} 全局样本数不符: {observed} != {target}')

    manifest_stats = manifest.get('current_stats', {})
    for field in (
        'total_samples',
        'distinct_base_fqdn',
        'l3_ratio',
        'multi_intent_ratio',
        'high_risk_case_count',
        'max_l1_ratio',
        'max_bucket_skeleton_share',
        'skeleton_overlap_flag_count',
        'ood_like_count',
    ):
        expected = stats[field]
        actual = manifest_stats.get(field)
        if isinstance(expected, float):
            if actual is None or not almost_equal(float(actual), expected):
                errors.append(f'manifest.current_stats.{field}={actual}，回算应为 {expected}')
        else:
            if actual != expected:
                errors.append(f'manifest.current_stats.{field}={actual}，回算应为 {expected}')
    for field in ('eval_bucket_counts', 'intent_form_counts', 'surface_style_counts', 'l1_counts'):
        if manifest_stats.get(field) != stats[field]:
            errors.append(f'manifest.current_stats.{field} 与回算结果不一致')

    recomputed_coverage = recompute_coverage(resolver, input_rows, label_rows)
    if coverage_rows != recomputed_coverage:
        errors.append('holdout3_coverage_status.csv 与回算覆盖统计不一致')

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
            'skeleton_audit_clean': stats['skeleton_overlap_flag_count'] == 0,
            'coverage_csv_matches': coverage_rows == recomputed_coverage,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
