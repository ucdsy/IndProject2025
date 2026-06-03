from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agentdns_routing.namespace import NamespaceResolver, load_jsonl

FORMAL_DIR = ROOT / 'data' / 'agentdns_routing' / 'formal'
SCHEMA_DIR = ROOT / 'schemas'
ARTIFACT_DIR = ROOT / 'artifacts' / 'dataset'
DESCRIPTOR_PATH = ROOT / 'data' / 'agentdns_routing' / 'namespace_descriptors.jsonl'

INPUT_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_input.jsonl'
LABEL_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_labels.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_coverage.csv'
RANK_PROBE_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_rank_probe.csv'
REPORT_PATH = ARTIFACT_DIR / 'hard_routing_boundary_v1_validation_report.json'

SLICE_TARGETS = {
    'low_rank_gold': 80,
    'parent_child_granularity': 90,
    'primary_secondary_conflict': 90,
    'cross_domain_overlap': 90,
    'high_risk_governance_tone': 80,
    'near_duplicate_descriptors': 70,
}
HIGH_RISK_BASES = {
    'permit.gov.cn',
    'policy.gov.cn',
    'compliance.security.cn',
    'risk.security.cn',
    'fraud.security.cn',
}
INPUT_REQUIRED = {
    'id',
    'namespace_version',
    'query',
    'context',
    'metadata',
    'stress_slice',
    'difficulty_tag',
    'surface_style',
    'paraphrase_group_id',
    'variant_index',
}
LABEL_REQUIRED = {
    'id',
    'family_id',
    'paraphrase_group_id',
    'variant_index',
    'ground_truth_fqdn',
    'acceptable_fqdns',
    'relevant_fqdns',
    'stress_slice',
    'expected_failure_mode',
    'competing_fqdns',
    'bucket_tags',
    'primary_granularity',
    'secondary_intent_present',
    'high_risk_case',
    'candidate_rank_probe',
    'notes_for_audit',
}
SURFACE_STYLES = {'colloquial', 'formal', 'enterprise', 'compressed', 'indirect', 'mixed'}
BANNED_QUERY_TERMS = [
    '路由',
    '主能力',
    '主标签',
    '竞争候选',
    '相邻能力',
    '能力命中',
    '泛化能力',
    '能力边界',
    '边界判断',
    '边界稳定性',
    'hard_boundary',
    'stress_slice',
    'candidate',
    'gold',
    'Stage R',
    'FQDN',
    'namespace',
    '评测',
    '样本',
    '主任务是',
    '主动作',
]
OLD_TEMPLATE_FRAGMENTS = [
    '这里不要只按大类处理，我要的是更具体的这一步',
    '虽然这里还牵到别的域，但我现在最先要的是',
    '这个说法很容易和相邻能力混在一起',
    '风控、合规和政策都会被问到，但当前第一步是',
    '这些线索容易带偏，但现在真正要先做的是',
    '旁边可能会提到',
    '当前只做路由判断',
    '这条先用于边界判断',
    '先检查主能力是否命中',
    '这条先看边界稳定性',
    '先把竞争候选压住',
    '别让相关词抢主标签',
]
UNNATURAL_QUERY_FRAGMENTS = [
    '帮我给',
    '处理排',
    '先把把',
    '先从把',
    '先从列',
    '可以一起带一下',
    '风险先不展开，风险先记着',
    '帮我帮我',
    '先帮我帮',
    '麻烦先帮我帮',
]
MAX_REPEATED_QUERY_HEAD = 12
MAX_REPEATED_QUERY_TAIL = 25
MAX_VARIANTS_PER_PARAPHRASE_GROUP = 3
DOMAIN_LIKE_PATTERN = re.compile(r'\b[a-z0-9-]+(?:\.[a-z0-9-]+)+\.cn\b')
OLD_INPUT_FILES = [
    ROOT / 'data' / 'agentdns_routing' / 'dev.jsonl',
    ROOT / 'data' / 'agentdns_routing' / 'test.jsonl',
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_input.jsonl',
    FORMAL_DIR / 'challenge_input.jsonl',
    FORMAL_DIR / 'holdout2_input.jsonl',
    FORMAL_DIR / 'holdout3_input.jsonl',
    FORMAL_DIR / 'multi_intent_eval_v1.jsonl',
]
OLD_LABEL_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_labels.jsonl',
    FORMAL_DIR / 'challenge_labels.jsonl',
    FORMAL_DIR / 'holdout2_labels.jsonl',
    FORMAL_DIR / 'holdout3_labels.jsonl',
    FORMAL_DIR / 'multi_intent_eval_v1.jsonl',
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def validate_input_rows(rows: list[dict[str, Any]], errors: list[str]) -> None:
    for idx, row in enumerate(rows, start=1):
        missing = INPUT_REQUIRED.difference(row)
        if missing:
            errors.append(f'hard_routing_boundary_v1_input 第 {idx} 行结构校验失败: 缺少字段 {sorted(missing)}')
            continue
        if row['namespace_version'] != 'ns_v1_20260311':
            errors.append(f'{row["id"]} namespace_version 不正确')
        if row['stress_slice'] not in SLICE_TARGETS:
            errors.append(f'{row["id"]} stress_slice 不合法: {row["stress_slice"]}')
        if row['difficulty_tag'] != row['stress_slice']:
            errors.append(f'{row["id"]} difficulty_tag 应与 stress_slice 一致')
        if row['surface_style'] not in SURFACE_STYLES:
            errors.append(f'{row["id"]} surface_style 不合法: {row["surface_style"]}')
        if not isinstance(row['paraphrase_group_id'], str) or not row['paraphrase_group_id'].startswith(f'hard_boundary_v1_{row["stress_slice"]}_'):
            errors.append(f'{row["id"]} paraphrase_group_id 不合法')
        if not isinstance(row['variant_index'], int) or row['variant_index'] < 1 or row['variant_index'] > MAX_VARIANTS_PER_PARAPHRASE_GROUP:
            errors.append(f'{row["id"]} variant_index 不合法: {row.get("variant_index")}')
        if not isinstance(row['query'], str) or len(row['query']) < 8:
            errors.append(f'{row["id"]} query 为空或过短')
        if not isinstance(row['context'], dict):
            errors.append(f'{row["id"]} context 不是 object')
        metadata = row['metadata']
        if not isinstance(metadata, dict):
            errors.append(f'{row["id"]} metadata 不是 object')
        else:
            if metadata.get('dataset_version') != 'hard_routing_boundary_v1_20260602':
                errors.append(f'{row["id"]} metadata.dataset_version 不正确')
            if metadata.get('stress_slice') != row['stress_slice']:
                errors.append(f'{row["id"]} metadata.stress_slice 与 input stress_slice 不一致')
            if metadata.get('primary_granularity') not in {'base', 'segment'}:
                errors.append(f'{row["id"]} metadata.primary_granularity 不合法')
            if metadata.get('paraphrase_group_id') != row['paraphrase_group_id']:
                errors.append(f'{row["id"]} metadata.paraphrase_group_id 与 input 不一致')
            if metadata.get('variant_index') != row['variant_index']:
                errors.append(f'{row["id"]} metadata.variant_index 与 input 不一致')


def query_head_signature(query: str) -> str:
    normalized = re.sub(r'\s+', '', query)
    return normalized[:18]


def query_tail_signature(query: str) -> str:
    parts = [part for part in re.split(r'[；。]', query) if part]
    return parts[-1] if parts else query


def validate_query_naturalness(rows: list[dict[str, Any]], errors: list[str], warnings: list[str]) -> dict[str, Any]:
    banned_hits: list[dict[str, str]] = []
    old_template_hits: list[dict[str, str]] = []
    unnatural_hits: list[dict[str, str]] = []
    domain_like_hits: list[dict[str, str]] = []
    head_counter = Counter()
    tail_counter = Counter()
    for row in rows:
        query = row['query']
        for term in BANNED_QUERY_TERMS:
            if term in query:
                banned_hits.append({'id': row['id'], 'term': term})
        for fragment in OLD_TEMPLATE_FRAGMENTS:
            if fragment in query:
                old_template_hits.append({'id': row['id'], 'fragment': fragment})
        for fragment in UNNATURAL_QUERY_FRAGMENTS:
            if fragment in query:
                unnatural_hits.append({'id': row['id'], 'fragment': fragment})
        match = DOMAIN_LIKE_PATTERN.search(query)
        if match:
            domain_like_hits.append({'id': row['id'], 'domain_like': match.group(0)})
        head_counter[query_head_signature(query)] += 1
        tail_counter[query_tail_signature(query)] += 1

    repeated_heads = {head: count for head, count in head_counter.items() if count > MAX_REPEATED_QUERY_HEAD}
    repeated_tails = {tail: count for tail, count in tail_counter.items() if count > MAX_REPEATED_QUERY_TAIL}
    if banned_hits:
        errors.append(f'query 含评测/算法术语: {banned_hits[:10]}')
    if old_template_hits:
        errors.append(f'query 含旧模板残留: {old_template_hits[:10]}')
    if unnatural_hits:
        errors.append(f'query 含不自然拼接片段: {unnatural_hits[:10]}')
    if domain_like_hits:
        errors.append(f'query 含域名形态字符串: {domain_like_hits[:10]}')
    if repeated_heads:
        errors.append(f'query 开头重复过高: {dict(list(repeated_heads.items())[:10])}')
    if repeated_tails:
        errors.append(f'query 尾句重复过高: {dict(list(repeated_tails.items())[:10])}')
    if max(tail_counter.values() or [0]) > 20:
        warnings.append(f'query 尾句最高重复 {max(tail_counter.values())} 次，低于硬阈值但仍建议人工抽看')
    return {
        'banned_query_term_hits': len(banned_hits),
        'old_template_fragment_hits': len(old_template_hits),
        'unnatural_fragment_hits': len(unnatural_hits),
        'domain_like_query_hits': len(domain_like_hits),
        'max_query_head_repeat': max(head_counter.values() or [0]),
        'max_query_tail_repeat': max(tail_counter.values() or [0]),
    }


def validate_label_rows(rows: list[dict[str, Any]], errors: list[str]) -> None:
    for idx, row in enumerate(rows, start=1):
        missing = LABEL_REQUIRED.difference(row)
        if missing:
            errors.append(f'hard_routing_boundary_v1_labels 第 {idx} 行结构校验失败: 缺少字段 {sorted(missing)}')
            continue
        if row['stress_slice'] not in SLICE_TARGETS:
            errors.append(f'{row["id"]} stress_slice 不合法: {row["stress_slice"]}')
        if not isinstance(row['paraphrase_group_id'], str) or not row['paraphrase_group_id'].startswith(f'hard_boundary_v1_{row["stress_slice"]}_'):
            errors.append(f'{row["id"]} paraphrase_group_id 不合法')
        if not isinstance(row['variant_index'], int) or row['variant_index'] < 1 or row['variant_index'] > MAX_VARIANTS_PER_PARAPHRASE_GROUP:
            errors.append(f'{row["id"]} variant_index 不合法: {row.get("variant_index")}')
        if row['primary_granularity'] not in {'base', 'segment'}:
            errors.append(f'{row["id"]} primary_granularity 不合法')
        for field in ('acceptable_fqdns', 'relevant_fqdns', 'competing_fqdns', 'bucket_tags'):
            if not isinstance(row[field], list):
                errors.append(f'{row["id"]} {field} 不是 array')
        if not isinstance(row['secondary_intent_present'], bool):
            errors.append(f'{row["id"]} secondary_intent_present 不是 boolean')
        if not isinstance(row['high_risk_case'], bool):
            errors.append(f'{row["id"]} high_risk_case 不是 boolean')
        if not isinstance(row['notes_for_audit'], str) or len(row['notes_for_audit']) < 8:
            errors.append(f'{row["id"]} notes_for_audit 为空或过短')
        probe = row['candidate_rank_probe']
        if not isinstance(probe, dict):
            errors.append(f'{row["id"]} candidate_rank_probe 不是 object')
            continue
        for field in ('stage_r_version', 'top_k', 'gold_rank', 'gold_in_top_k', 'head_fqdn'):
            if field not in probe:
                errors.append(f'{row["id"]} candidate_rank_probe 缺少 {field}')


def normalize_base_fqdn(fqdn: str) -> str:
    parts = fqdn.split('.')
    return '.'.join(parts[1:]) if len(parts) == 4 else fqdn


def primary_granularity(fqdn: str) -> str:
    return 'segment' if len(fqdn.split('.')) == 4 else 'base'


def acceptable_fqdns(fqdn: str) -> list[str]:
    base = normalize_base_fqdn(fqdn)
    return [fqdn] if base == fqdn else [fqdn, base]


def compute_stats(resolver: NamespaceResolver, label_rows: list[dict[str, Any]]) -> dict[str, Any]:
    slice_counts = Counter(row['stress_slice'] for row in label_rows)
    gt_counter = Counter(row['ground_truth_fqdn'] for row in label_rows)
    base_counter = Counter(normalize_base_fqdn(row['ground_truth_fqdn']) for row in label_rows)
    l1_counter: Counter[str] = Counter()
    segment_count = 0
    high_risk_count = 0
    secondary_count = 0
    group_counter = Counter(row['paraphrase_group_id'] for row in label_rows)
    low_rank_ranks: list[int | None] = []
    for row in label_rows:
        node = resolver.get_node(row['ground_truth_fqdn'])
        if node:
            l1_counter[node.l1] += 1
        if row['primary_granularity'] == 'segment':
            segment_count += 1
        if row['high_risk_case']:
            high_risk_count += 1
        if row['secondary_intent_present']:
            secondary_count += 1
        if row['stress_slice'] == 'low_rank_gold':
            low_rank_ranks.append(row['candidate_rank_probe']['gold_rank'])
    return {
        'total_samples': len(label_rows),
        'stress_slice_counts': dict(slice_counts),
        'distinct_ground_truth_fqdn': len(gt_counter),
        'distinct_ground_truth_base_fqdn': len(base_counter),
        'segment_primary_count': segment_count,
        'secondary_intent_count': secondary_count,
        'high_risk_case_count': high_risk_count,
        'distinct_paraphrase_group_count': len(group_counter),
        'max_variants_per_paraphrase_group': max(group_counter.values() or [0]),
        'low_rank_gold_rank_ge4_or_missing_count': sum(1 for rank in low_rank_ranks if rank is None or rank >= 4),
        'low_rank_gold_not_in_top_k_count': sum(1 for rank in low_rank_ranks if rank is None),
        'ground_truth_fqdn_counts': dict(sorted(gt_counter.items())),
        'ground_truth_l1_counts': dict(sorted(l1_counter.items())),
    }


def compute_coverage(resolver: NamespaceResolver, label_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    slice_by_fqdn: dict[str, set[str]] = defaultdict(set)
    count_by_fqdn: Counter[str] = Counter()
    segment_count_by_fqdn: Counter[str] = Counter()
    secondary_count_by_fqdn: Counter[str] = Counter()
    for row in label_rows:
        fqdn = row['ground_truth_fqdn']
        count_by_fqdn[fqdn] += 1
        slice_by_fqdn[fqdn].add(row['stress_slice'])
        if row['primary_granularity'] == 'segment':
            segment_count_by_fqdn[fqdn] += 1
        if row['secondary_intent_present']:
            secondary_count_by_fqdn[fqdn] += 1
    rows: list[dict[str, str]] = []
    for fqdn in sorted(count_by_fqdn):
        node = resolver.get_node(fqdn)
        rows.append(
            {
                'ground_truth_fqdn': fqdn,
                'base_fqdn': normalize_base_fqdn(fqdn),
                'l1': node.l1 if node else '',
                'l2': node.l2 or '' if node else '',
                'sample_count': str(count_by_fqdn[fqdn]),
                'segment_sample_count': str(segment_count_by_fqdn[fqdn]),
                'secondary_intent_count': str(secondary_count_by_fqdn[fqdn]),
                'stress_slices': ';'.join(sorted(slice_by_fqdn[fqdn])),
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
    rank_probe_rows = load_csv(RANK_PROBE_PATH)

    errors: list[str] = []
    warnings: list[str] = []

    validate_input_rows(input_rows, errors)
    validate_label_rows(label_rows, errors)
    naturalness_stats = validate_query_naturalness(input_rows, errors, warnings)

    input_ids = [row['id'] for row in input_rows]
    label_ids = [row['id'] for row in label_rows]
    rank_ids = [row['id'] for row in rank_probe_rows]
    if input_ids != label_ids:
        errors.append('hard boundary input/label id 顺序或集合不一致')
    if input_ids != rank_ids:
        errors.append('hard boundary rank_probe id 顺序或集合不一致')
    if len(set(input_ids)) != len(input_ids):
        errors.append('hard boundary input 存在重复 id')
    if len({row['query'] for row in input_rows}) != len(input_rows):
        errors.append('hard boundary input 存在重复 query')
    if len({row['family_id'] for row in label_rows}) != len(label_rows):
        errors.append('hard boundary labels 存在重复 family_id')

    old_queries: set[str] = set()
    for path in OLD_INPUT_FILES:
        if path.exists():
            for row in load_jsonl(path):
                query = row.get('query')
                if query:
                    old_queries.add(query)
    overlap_queries = sorted(old_queries.intersection({row['query'] for row in input_rows}))
    if overlap_queries:
        errors.append(f'hard boundary query 与已有集合重复: {overlap_queries[:5]}')

    old_families: set[str] = set()
    for path in OLD_LABEL_FILES:
        if path.exists():
            for row in load_jsonl(path):
                family_id = row.get('family_id')
                if family_id:
                    old_families.add(family_id)
    overlap_families = sorted(old_families.intersection({row['family_id'] for row in label_rows}))
    if overlap_families:
        errors.append(f'hard boundary family_id 与已有集合重复: {overlap_families[:5]}')

    rank_by_id = {row['id']: row for row in rank_probe_rows}
    for input_row, label_row in zip(input_rows, label_rows):
        sample_id = label_row['id']
        gt = label_row['ground_truth_fqdn']
        if input_row['stress_slice'] != label_row['stress_slice']:
            errors.append(f'{sample_id} input/label stress_slice 不一致')
        if input_row['paraphrase_group_id'] != label_row['paraphrase_group_id']:
            errors.append(f'{sample_id} input/label paraphrase_group_id 不一致')
        if input_row['variant_index'] != label_row['variant_index']:
            errors.append(f'{sample_id} input/label variant_index 不一致')
        if input_row['metadata']['primary_granularity'] != label_row['primary_granularity']:
            errors.append(f'{sample_id} input/label primary_granularity 不一致')
        if not resolver.has_fqdn(gt):
            errors.append(f'{sample_id} ground_truth_fqdn 不在 namespace: {gt}')
        if label_row['primary_granularity'] != primary_granularity(gt):
            errors.append(f'{sample_id} primary_granularity 与 gt 不一致')
        if label_row['acceptable_fqdns'] != acceptable_fqdns(gt):
            errors.append(f'{sample_id} acceptable_fqdns 与 gt 层级不一致')
        for field in ('relevant_fqdns', 'competing_fqdns'):
            for fqdn in label_row[field]:
                if not resolver.has_fqdn(fqdn):
                    errors.append(f'{sample_id} {field} 包含未知 fqdn: {fqdn}')
        if gt in label_row['relevant_fqdns']:
            errors.append(f'{sample_id} relevant_fqdns 包含 ground truth')
        if gt in label_row['competing_fqdns']:
            errors.append(f'{sample_id} competing_fqdns 包含 ground truth')
        if label_row['secondary_intent_present'] != bool(label_row['relevant_fqdns']):
            errors.append(f'{sample_id} secondary_intent_present 与 relevant_fqdns 不一致')
        expected_high_risk = label_row['stress_slice'] == 'high_risk_governance_tone' or normalize_base_fqdn(gt) in HIGH_RISK_BASES
        if label_row['high_risk_case'] != expected_high_risk:
            errors.append(f'{sample_id} high_risk_case 与 slice/base 不一致')

        probe = label_row['candidate_rank_probe']
        rank_row = rank_by_id.get(sample_id)
        if rank_row:
            rank_from_csv = None if rank_row['gold_rank'] == '' else int(rank_row['gold_rank'])
            if rank_from_csv != probe['gold_rank']:
                errors.append(f'{sample_id} rank_probe csv 与 label gold_rank 不一致')
            if rank_row['head_fqdn'] != probe['head_fqdn']:
                errors.append(f'{sample_id} rank_probe csv 与 label head_fqdn 不一致')
        if label_row['stress_slice'] == 'low_rank_gold':
            rank = probe['gold_rank']
            if rank is not None and rank < 4:
                errors.append(f'{sample_id} low_rank_gold 的 gold_rank 过高: {rank}')

    stats = compute_stats(resolver, label_rows)
    recomputed_coverage = compute_coverage(resolver, label_rows)
    if stats != manifest.get('stats'):
        errors.append('hard boundary manifest stats 与回算结果不一致')
    if recomputed_coverage != coverage_rows:
        errors.append('hard boundary coverage csv 与回算结果不一致')
    if stats['stress_slice_counts'] != SLICE_TARGETS:
        errors.append(f'hard boundary stress_slice_counts 不符合目标: {stats["stress_slice_counts"]}')
    if stats['total_samples'] != 500:
        errors.append(f'hard boundary 样本数不是 500: {stats["total_samples"]}')
    if stats['distinct_ground_truth_base_fqdn'] != 25:
        errors.append(f'hard boundary ground-truth base coverage 不是 25/25: {stats["distinct_ground_truth_base_fqdn"]}')
    if stats['max_variants_per_paraphrase_group'] > MAX_VARIANTS_PER_PARAPHRASE_GROUP:
        errors.append(
            f'hard boundary paraphrase group 变体数超过 {MAX_VARIANTS_PER_PARAPHRASE_GROUP}: '
            f'{stats["max_variants_per_paraphrase_group"]}'
        )
    if stats['low_rank_gold_rank_ge4_or_missing_count'] != SLICE_TARGETS['low_rank_gold']:
        errors.append('hard boundary low_rank_gold 未全部满足 rank>=4 或 top-k 未命中')

    report = {
        'ok': not errors,
        'errors': errors,
        'warnings': warnings,
        'dataset_version': manifest.get('dataset_version'),
        'namespace_version': manifest.get('namespace_version'),
        'stats': stats,
        'naturalness_stats': naturalness_stats,
        'checks': {
            'schema_valid': not any('结构校验失败' in error for error in errors),
            'query_naturalness': naturalness_stats['banned_query_term_hits'] == 0
            and naturalness_stats['old_template_fragment_hits'] == 0
            and naturalness_stats['unnatural_fragment_hits'] == 0
            and naturalness_stats['domain_like_query_hits'] == 0
            and naturalness_stats['max_query_head_repeat'] <= MAX_REPEATED_QUERY_HEAD
            and naturalness_stats['max_query_tail_repeat'] <= MAX_REPEATED_QUERY_TAIL,
            'query_text_disjoint': not overlap_queries,
            'family_disjoint': not overlap_families,
            'coverage_csv_matches': recomputed_coverage == coverage_rows,
            'manifest_stats_match': stats == manifest.get('stats'),
            'slice_counts_match': stats['stress_slice_counts'] == SLICE_TARGETS,
            'paraphrase_cap_respected': stats['max_variants_per_paraphrase_group'] <= MAX_VARIANTS_PER_PARAPHRASE_GROUP,
            'low_rank_gold_rank_ge4_or_missing': stats['low_rank_gold_rank_ge4_or_missing_count'] == SLICE_TARGETS['low_rank_gold'],
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
