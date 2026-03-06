from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
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

SPLIT_CONFIG = {
    'dev': {
        'path': FORMAL_DIR / 'dev.jsonl',
        'schema': SCHEMA_DIR / 'formal_dev_sample.schema.json',
        'split_name': 'dev',
        'kind': 'labeled',
    },
    'blind_input': {
        'path': FORMAL_DIR / 'blind_input.jsonl',
        'schema': SCHEMA_DIR / 'formal_blind_input_sample.schema.json',
        'split_name': 'blind',
        'kind': 'input',
    },
    'blind_labels': {
        'path': FORMAL_DIR / 'blind_labels.jsonl',
        'schema': SCHEMA_DIR / 'formal_blind_label_sample.schema.json',
        'split_name': 'blind',
        'kind': 'labels',
    },
    'challenge_input': {
        'path': FORMAL_DIR / 'challenge_input.jsonl',
        'schema': SCHEMA_DIR / 'formal_challenge_input_sample.schema.json',
        'split_name': 'challenge',
        'kind': 'input',
    },
    'challenge_labels': {
        'path': FORMAL_DIR / 'challenge_labels.jsonl',
        'schema': SCHEMA_DIR / 'formal_challenge_label_sample.schema.json',
        'split_name': 'challenge',
        'kind': 'labels',
    },
}

CITY_SEGMENT_NORMALIZERS = {
    'xian': 'xian',
    "xi'an": 'xian',
    'hangzhou': 'hangzhou',
    'yunnan': 'yunnan',
    'chengdu': 'chengdu',
    'shanghai': 'shanghai',
    'beijing': 'beijing',
    'guangzhou': 'guangzhou',
    'shenzhen': 'shenzhen',
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def load_schema(path: Path) -> Draft202012Validator:
    return Draft202012Validator(load_json(path))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def base_fqdn(resolver: NamespaceResolver, fqdn: str) -> str:
    node = resolver.get_node(fqdn)
    if node and node.parent_fqdn:
        return node.parent_fqdn
    return fqdn


def validate_rows(rows: list[dict[str, Any]], validator: Draft202012Validator, file_label: str, errors: list[str]) -> None:
    for idx, row in enumerate(rows, start=1):
        for err in validator.iter_errors(row):
            location = '.'.join(str(x) for x in err.path) or '<root>'
            errors.append(f'{file_label} 第 {idx} 行 schema 校验失败: {location}: {err.message}')


def collect_labeled_rows(all_rows: dict[str, list[dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    labeled: list[tuple[str, dict[str, Any]]] = []
    for key, cfg in SPLIT_CONFIG.items():
        if cfg['kind'] == 'labeled':
            labeled.extend((cfg['split_name'], row) for row in all_rows[key])
        elif cfg['kind'] == 'labels':
            labeled.extend((cfg['split_name'], row) for row in all_rows[key])
    return labeled


def almost_equal(left: float, right: float, tol: float = 1e-6) -> bool:
    return abs(left - right) <= tol


def leading_prefix_stats(rows: list[dict[str, Any]], prefix_len: int = 3) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        query = row.get('query', '')
        prefix = query[:prefix_len]
        if prefix:
            counts[prefix] += 1
    if not counts:
        return {'top_prefix': '', 'count': 0, 'ratio': 0.0}
    top_prefix, count = max(counts.items(), key=lambda item: item[1])
    return {
        'top_prefix': top_prefix,
        'count': count,
        'ratio': round(count / max(len(rows), 1), 4),
    }


def normalize_city_segment(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return CITY_SEGMENT_NORMALIZERS.get(normalized, normalized or None)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    base_nodes = [node for node in resolver.iter_nodes() if node.node_kind == 'base']
    base_node_count = len(base_nodes)

    validators = {name: load_schema(cfg['schema']) for name, cfg in SPLIT_CONFIG.items()}
    all_rows = {name: load_jsonl(cfg['path']) for name, cfg in SPLIT_CONFIG.items()}
    manifest = load_json(FORMAL_DIR / 'manifest.json')
    family_ledger = load_csv(FORMAL_DIR / 'family_ledger.csv')
    coverage_plan = load_csv(FORMAL_DIR / 'coverage_plan.csv')
    context_by_id = {
        row['id']: row.get('context') or {}
        for rows in (all_rows['dev'], all_rows['blind_input'], all_rows['challenge_input'])
        for row in rows
    }

    errors: list[str] = []
    warnings: list[str] = []

    for name, rows in all_rows.items():
        validate_rows(rows, validators[name], name, errors)

    # input/label id 对齐
    blind_input_ids = [row['id'] for row in all_rows['blind_input']]
    blind_label_ids = [row['id'] for row in all_rows['blind_labels']]
    challenge_input_ids = [row['id'] for row in all_rows['challenge_input']]
    challenge_label_ids = [row['id'] for row in all_rows['challenge_labels']]
    if blind_input_ids != blind_label_ids:
        errors.append('blind_input 与 blind_labels 的样本 id 顺序或集合不一致')
    if challenge_input_ids != challenge_label_ids:
        errors.append('challenge_input 与 challenge_labels 的样本 id 顺序或集合不一致')

    # split 间 id 不得重叠
    split_id_sets = {
        'dev': {row['id'] for row in all_rows['dev']},
        'blind': set(blind_input_ids),
        'challenge': set(challenge_input_ids),
    }
    split_names = list(split_id_sets)
    for i, left in enumerate(split_names):
        for right in split_names[i + 1 :]:
            overlap = split_id_sets[left].intersection(split_id_sets[right])
            if overlap:
                errors.append(f'{left} 与 {right} 存在重复样本 id: {sorted(overlap)}')

    # family 约束
    observed_family_split: dict[str, str] = {}
    observed_family_samples: dict[str, list[str]] = defaultdict(list)
    labeled_rows = collect_labeled_rows(all_rows)
    for split_name, row in labeled_rows:
        family_id = row['family_id']
        if family_id in observed_family_split and observed_family_split[family_id] != split_name:
            errors.append(f'family_id {family_id} 跨 split 出现: {observed_family_split[family_id]} / {split_name}')
        observed_family_split[family_id] = split_name
        observed_family_samples[family_id].append(row['id'])

    ledger_by_family = {row['family_id']: row for row in family_ledger}
    if set(ledger_by_family) != set(observed_family_split):
        missing_in_ledger = sorted(set(observed_family_split) - set(ledger_by_family))
        extra_in_ledger = sorted(set(ledger_by_family) - set(observed_family_split))
        if missing_in_ledger:
            errors.append(f'family_ledger 缺少 family_id: {missing_in_ledger}')
        if extra_in_ledger:
            warnings.append(f'family_ledger 存在当前 formal 数据未使用的 family_id: {extra_in_ledger}')

    for family_id, split_name in observed_family_split.items():
        if family_id not in ledger_by_family:
            continue
        ledger_row = ledger_by_family[family_id]
        if ledger_row['split'] != split_name:
            errors.append(f'family_ledger 中 {family_id} 的 split={ledger_row["split"]}，与数据实际 split={split_name} 不一致')
        ledger_sample_ids = [value for value in ledger_row['样本ID列表'].split(';') if value]
        if sorted(ledger_sample_ids) != sorted(observed_family_samples[family_id]):
            errors.append(f'family_ledger 中 {family_id} 的样本ID列表与 formal 数据不一致')

    # fqdn 合法性
    for split_name, row in labeled_rows:
        for field in ('ground_truth_fqdn',):
            fqdn = row[field]
            if not resolver.has_fqdn(fqdn):
                errors.append(f'{split_name} 样本 {row["id"]} 的 {field} 不在 namespace catalog 中: {fqdn}')
        for field in ('relevant_fqdns', 'acceptable_fqdns'):
            for fqdn in row.get(field, []):
                if not resolver.has_fqdn(fqdn):
                    errors.append(f'{split_name} 样本 {row["id"]} 的 {field} 包含未知 fqdn: {fqdn}')
        node = resolver.get_node(row['ground_truth_fqdn'])
        context = row.get('context') or context_by_id.get(row['id'], {})
        if node and node.segment and base_fqdn(resolver, row['ground_truth_fqdn']) in {'itinerary.travel.cn', 'hotel.travel.cn'}:
            context_city = normalize_city_segment((context or {}).get('city'))
            if context_city and context_city != node.segment:
                errors.append(
                    f'{split_name} 样本 {row["id"]} 的 city={context.get("city")} 与 l3 segment={node.segment} 不一致'
                )

    # namespace version / manifest 一致性
    manifest_ns = manifest['namespace_version']
    for file_name in ('dev', 'blind_input', 'challenge_input'):
        for row in all_rows[file_name]:
            if row['namespace_version'] != manifest_ns:
                errors.append(f'{file_name} 中样本 {row["id"]} 的 namespace_version 与 manifest 不一致')
    if 'namespace_version_note' not in manifest:
        warnings.append('manifest 缺少 namespace_version_note，日期语义仍不够清楚')

    # 统计
    split_sizes = {
        'dev': len(all_rows['dev']),
        'blind': len(all_rows['blind_labels']),
        'challenge': len(all_rows['challenge_labels']),
    }
    all_label_rows_only = all_rows['dev'] + all_rows['blind_labels'] + all_rows['challenge_labels']
    l3_hits = 0
    multi_intent_hits = 0
    miit_hits = 0
    unique_base = set()
    current_counts: dict[str, dict[str, int]] = defaultdict(lambda: {'dev': 0, 'blind': 0, 'challenge': 0})
    for split_name, row in labeled_rows:
        gt = row['ground_truth_fqdn']
        node = resolver.get_node(gt)
        if node and node.segment:
            l3_hits += 1
        if 'multi_intent' in row.get('difficulty_tags', []) or 'multi_intent' in row.get('intended_confusion_types', []):
            multi_intent_hits += 1
        family_row = ledger_by_family.get(row['family_id'])
        if family_row and family_row['场景桶'] == '工信':
            miit_hits += 1
        base = base_fqdn(resolver, gt)
        unique_base.add(base)
        current_counts[base][split_name] += 1

    total_labeled = len(all_label_rows_only) or 1
    stats = {
        'split_sizes': split_sizes,
        'total_labeled': len(all_label_rows_only),
        'miit_ratio': round(miit_hits / total_labeled, 4),
        'l3_ratio': round(l3_hits / total_labeled, 4),
        'multi_intent_ratio': round(multi_intent_hits / total_labeled, 4),
        'gt_base_coverage': {
            'covered': len(unique_base),
            'total_base_nodes': base_node_count,
            'ratio': round(len(unique_base) / max(base_node_count, 1), 4),
        },
    }

    blind_base = {
        base_fqdn(resolver, row['ground_truth_fqdn'])
        for row in all_rows['blind_labels']
    }
    stats['blind_base_coverage'] = {
        'covered': len(blind_base),
        'total_base_nodes': base_node_count,
        'ratio': round(len(blind_base) / max(base_node_count, 1), 4),
        'missing_bases': sorted({node.fqdn for node in base_nodes} - blind_base),
    }

    stats['split_prefix_bias'] = {
        'dev': leading_prefix_stats(all_rows['dev']),
        'blind_input': leading_prefix_stats(all_rows['blind_input']),
        'challenge_input': leading_prefix_stats(all_rows['challenge_input']),
    }

    targets = manifest.get('targets', {})
    if split_sizes['dev'] < targets.get('dev_min', 0):
        warnings.append(f"dev 样本数不足: {split_sizes['dev']} < {targets.get('dev_min')}")
    if split_sizes['blind'] < targets.get('blind_min', 0):
        warnings.append(f"blind 样本数不足: {split_sizes['blind']} < {targets.get('blind_min')}")
    if split_sizes['challenge'] < targets.get('challenge_min', 0):
        warnings.append(f"challenge 样本数不足: {split_sizes['challenge']} < {targets.get('challenge_min')}")
    if len(all_label_rows_only) < targets.get('total_min', 0):
        warnings.append(f"formal 总样本数不足: {len(all_label_rows_only)} < {targets.get('total_min')}")

    miit_range = targets.get('miit_ratio_range')
    if miit_range and not (miit_range[0] <= stats['miit_ratio'] <= miit_range[1]):
        warnings.append(f"工信场景占比越界: {stats['miit_ratio']} 不在 [{miit_range[0]}, {miit_range[1]}] 内")
    l3_range = targets.get('l3_ratio_range')
    if l3_range and not (l3_range[0] <= stats['l3_ratio'] <= l3_range[1]):
        warnings.append(f"l3 占比越界: {stats['l3_ratio']} 不在 [{l3_range[0]}, {l3_range[1]}] 内")
    multi_intent_range = targets.get('multi_intent_ratio_range')
    if multi_intent_range and not (multi_intent_range[0] <= stats['multi_intent_ratio'] <= multi_intent_range[1]):
        warnings.append(
            f"multi_intent 占比越界: {stats['multi_intent_ratio']} 不在 [{multi_intent_range[0]}, {multi_intent_range[1]}] 内"
        )

    # manifest 一致性
    for split_key, manifest_key in [('dev', 'dev'), ('blind', 'blind_labels'), ('challenge', 'challenge_labels')]:
        manifest_count = manifest['formal_splits'][manifest_key]['samples']
        if split_sizes[split_key] != manifest_count:
            errors.append(f'manifest 中 {manifest_key}.samples={manifest_count}，实际为 {split_sizes[split_key]}')

    input_counts = {
        'blind_input': len(all_rows['blind_input']),
        'challenge_input': len(all_rows['challenge_input']),
    }
    for manifest_key, actual_count in input_counts.items():
        manifest_count = manifest['formal_splits'][manifest_key]['samples']
        if actual_count != manifest_count:
            errors.append(f'manifest 中 {manifest_key}.samples={manifest_count}，实际为 {actual_count}')

    expected_split_miit = {
        'dev': round(
            sum(1 for row in all_rows['dev'] if (row.get('context') or {}).get('industry') in {'enterprise_service', 'manufacturing'})
            / max(len(all_rows['dev']), 1),
            4,
        ),
        'blind_input': round(
            sum(1 for row in all_rows['blind_input'] if (row.get('context') or {}).get('industry') in {'enterprise_service', 'manufacturing'})
            / max(len(all_rows['blind_input']), 1),
            4,
        ),
        'challenge_input': round(
            sum(1 for row in all_rows['challenge_input'] if (row.get('context') or {}).get('industry') in {'enterprise_service', 'manufacturing'})
            / max(len(all_rows['challenge_input']), 1),
            4,
        ),
    }
    for key, expected in expected_split_miit.items():
        manifest_value = manifest['formal_splits'][key].get('miit_ratio')
        if manifest_value is None or not almost_equal(float(manifest_value), expected):
            errors.append(f'manifest 中 {key}.miit_ratio={manifest_value}，实际应为 {expected}')

    manifest_total_samples = manifest.get('totals', {}).get('samples')
    if manifest_total_samples != len(all_label_rows_only):
        errors.append(f'manifest 中 totals.samples={manifest_total_samples}，实际应为 {len(all_label_rows_only)}')
    manifest_total_miit = manifest.get('totals', {}).get('miit_ratio')
    if manifest_total_miit is None or not almost_equal(float(manifest_total_miit), stats['miit_ratio']):
        errors.append(f'manifest 中 totals.miit_ratio={manifest_total_miit}，实际应为 {stats["miit_ratio"]}')

    manifest_current = manifest.get('current_stats', {})
    if manifest_current.get('split_sizes') != stats['split_sizes']:
        errors.append('manifest.current_stats.split_sizes 与当前重算结果不一致')
    if manifest_current.get('total_labeled') != stats['total_labeled']:
        errors.append(f'manifest.current_stats.total_labeled={manifest_current.get("total_labeled")}，实际应为 {stats["total_labeled"]}')
    for field in ('miit_ratio', 'l3_ratio', 'multi_intent_ratio'):
        manifest_value = manifest_current.get(field)
        if manifest_value is None or not almost_equal(float(manifest_value), stats[field]):
            errors.append(f'manifest.current_stats.{field}={manifest_value}，实际应为 {stats[field]}')
    manifest_cov = manifest_current.get('gt_base_coverage', {})
    if manifest_cov != stats['gt_base_coverage']:
        errors.append('manifest.current_stats.gt_base_coverage 与当前重算结果不一致')
    manifest_blind_cov = manifest_current.get('blind_base_coverage')
    expected_blind_cov = {
        'covered': stats['blind_base_coverage']['covered'],
        'total_base_nodes': stats['blind_base_coverage']['total_base_nodes'],
        'ratio': stats['blind_base_coverage']['ratio'],
    }
    if manifest_blind_cov is not None and manifest_blind_cov != expected_blind_cov:
        errors.append('manifest.current_stats.blind_base_coverage 与当前重算结果不一致')

    if stats['blind_base_coverage']['ratio'] < 1.0:
        warnings.append(
            f"blind 主表未覆盖全部 base taxonomy: {stats['blind_base_coverage']['covered']}/{stats['blind_base_coverage']['total_base_nodes']}，缺失 {stats['blind_base_coverage']['missing_bases']}"
        )

    for split_name, prefix_stats in stats['split_prefix_bias'].items():
        if prefix_stats['ratio'] >= 0.5:
            warnings.append(
                f"{split_name} 的 query 起始模板偏置较强: top_prefix={prefix_stats['top_prefix']}，占比 {prefix_stats['ratio']}"
            )

    # coverage plan 对比
    coverage_rows: list[dict[str, Any]] = []
    deficit_rows: list[dict[str, Any]] = []
    for row in coverage_plan:
        base = row['base_fqdn']
        current_dev = current_counts[base]['dev']
        current_blind = current_counts[base]['blind']
        current_challenge = current_counts[base]['challenge']
        target_dev = int(row['dev目标'])
        target_blind = int(row['blind目标'])
        target_challenge = int(row['challenge目标'])
        coverage_row = {
            **row,
            '当前dev': current_dev,
            '当前blind': current_blind,
            '当前challenge': current_challenge,
            'dev缺口': max(target_dev - current_dev, 0),
            'blind缺口': max(target_blind - current_blind, 0),
            'challenge缺口': max(target_challenge - current_challenge, 0),
        }
        coverage_rows.append(coverage_row)
        if coverage_row['dev缺口'] or coverage_row['blind缺口'] or coverage_row['challenge缺口']:
            deficit_rows.append(coverage_row)

    report = {
        'ok': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'stats': stats,
        'coverage_deficit_count': len(deficit_rows),
        'top_coverage_deficits': deficit_rows[:10],
    }

    with (ARTIFACT_DIR / 'formal_validation_report.json').open('w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    coverage_csv = ARTIFACT_DIR / 'formal_coverage_status.csv'
    with coverage_csv.open('w', encoding='utf-8', newline='') as fh:
        fieldnames = [
            'base_fqdn', '一级领域', '二级能力', '场景桶目标', '层级目标', '建议主要混淆',
            'dev目标', '当前dev', 'dev缺口', 'blind目标', '当前blind', 'blind缺口',
            'challenge目标', '当前challenge', 'challenge缺口'
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in coverage_rows:
            writer.writerow({key: row[key] for key in fieldnames})

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
