from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agentdns_routing.namespace import NamespaceResolver, load_jsonl

FORMAL_DIR = ROOT / 'data' / 'agentdns_routing' / 'formal'
DESCRIPTOR_PATH = ROOT / 'data' / 'agentdns_routing' / 'namespace_descriptors.jsonl'
INPUT_PATH = FORMAL_DIR / 'holdout2_input.jsonl'
LABEL_PATH = FORMAL_DIR / 'holdout2_labels.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'holdout2_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'holdout2_coverage_status.csv'

NAMESPACE_VERSION = 'ns_v1_20260311'
DATASET_VERSION = 'holdout2_v0_20260322'

BUCKET_TARGETS = {
    'hierarchy_sibling': 12,
    'cross_domain': 10,
    'multi_intent': 10,
    'high_risk': 8,
    'fast_path': 8,
    'long_tail': 6,
}

FORMAL_FAMILY_FILES = [
    FORMAL_DIR / 'dev.jsonl',
    FORMAL_DIR / 'blind_labels.jsonl',
    FORMAL_DIR / 'challenge_labels.jsonl',
]

QUERY_PATTERNS = {
    'hierarchy_sibling': [
        '场景是“{scene}”。如果现在只落一个入口，就先做这件事：{main}。',
        '我手上这个请求是“{scene}”。先别发散，当前最该落的动作是：{main}。',
        '把问题说直白一点，“{scene}”这件事最先该落的能力是：{main}。',
        '先看这个场景：“{scene}”。如果不想走错层级，第一步应该是：{main}。',
    ],
    'cross_domain': [
        '“{scene}”里我优先想解决的是{main}。另外，{secondary}。',
        '先围绕“{scene}”把主问题处理掉：{main}。同时，{secondary}。',
        '这件事的主线还是“{scene}”。{main}；另外，{secondary}。',
        '先别发散，就按“{scene}”来。{main}；另外，{secondary}。',
    ],
    'multi_intent': [
        '围绕“{scene}”，先做主线：{main}。随后，{secondary}。',
        '“{scene}”这件事先处理主线：{main}。然后，{secondary}。',
        '我想先把“{scene}”做起来：{main}。再补一步：{secondary}。',
        '先帮我把“{scene}”的主线落下去：{main}。接着，{secondary}。',
    ],
    'high_risk': [
        '“{scene}”准备落地，但我更担心风险边界。当前最先该做的是：{main}。',
        '别先谈实现，我想先卡住合规与风控。“{scene}”这件事里优先动作是：{main}。',
        '对“{scene}”来说，最不能跳过的是高风险检查。先做这步：{main}。',
        '这件事一旦做错代价会很高：“{scene}”。先卡住这一步：{main}。',
    ],
    'fast_path': [
        '“{scene}”。直接处理：{main}。',
        '就这个场景：“{scene}”。当前动作是：{main}。',
        '我现在只想解决一件事，“{scene}”。请直接：{main}。',
        '场景很直接：“{scene}”。把这步做掉：{main}。',
    ],
    'long_tail': [
        '这个需求不算主流，但还在当前能力边界里：“{scene}”。先处理：{main}。',
        '换个偏一点的场景来看，“{scene}”这件事先落这步：{main}。',
        '这类需求不常见，但仍然是有效路由范围：“{scene}”。当前先做：{main}。',
        '我有个偏门但合理的请求：“{scene}”。先从这一步开始：{main}。',
    ],
}

BUCKETS_WITH_EXPLICIT_SECONDARY = {'cross_domain', 'multi_intent'}


def spec(
    slug: str,
    gt: str,
    bucket: str,
    scene: str,
    context: dict[str, Any],
    main: str,
    secondary: str = '',
    relevant: list[str] | None = None,
    confusions: list[str] | None = None,
    note: str = '',
) -> dict[str, Any]:
    return {
        'slug': slug,
        'gt': gt,
        'bucket': bucket,
        'scene': scene,
        'context': context,
        'main': main,
        'secondary': secondary,
        'relevant': relevant or [],
        'confusions': confusions or [],
        'note': note,
    }


RECIPES = [
    spec('data_export_camera_vendor', 'data.compliance.security.cn', 'hierarchy_sibling', '把工业相机日志发到海外供应商看板', {'industry': 'manufacturing', 'destination': 'overseas_saas'}, '把数据出境前的检查路径厘清', '补一版留痕动作', ['risk.security.cn'], ['governance_fallback', 'fallback']),
    spec('vendor_bank_account_check', 'transaction.compliance.security.cn', 'hierarchy_sibling', '给新供应商打首笔结算款', {'industry': 'enterprise_service'}, '先把交易对象核验该走的入口定清', '整理留档点', ['risk.security.cn'], ['governance_fallback', 'fallback']),
    spec('dealer_portal_account_realname', 'account.compliance.security.cn', 'hierarchy_sibling', '经销商门户准备开放多账号协作', {'industry': 'enterprise_service'}, '先把账号实名和权限治理的入口定下来', '补审计留痕要求', ['risk.security.cn'], ['governance_fallback', 'fallback']),
    spec('expo_invoice_verify', 'verify.invoice.finance.cn', 'hierarchy_sibling', '线下展会回来收了一批住宿和搭建票据', {'industry': 'enterprise_service'}, '先把票据验真这一步做掉', '提醒税务字段', ['tax.finance.cn'], ['sibling_competition', 'fallback']),
    spec('maintenance_fee_issue', 'issue.invoice.finance.cn', 'hierarchy_sibling', '收了设备维保年费后需要补电子票', {'industry': 'manufacturing'}, '先确认开票入口和必填字段', '补入账口径', ['tax.finance.cn'], ['sibling_competition', 'fallback']),
    spec('field_service_reimburse', 'reimburse.invoice.finance.cn', 'hierarchy_sibling', '驻场工程师报回了一组打车和住宿票', {'industry': 'enterprise_service'}, '先判断哪些票能直接报销入账', '补验真提醒', ['verify.invoice.finance.cn'], ['sibling_competition', 'fallback']),
    spec('weekly_dispatch_summary', 'summary.meeting.productivity.cn', 'hierarchy_sibling', '生产调度周会刚结束，录音和记录都在', {'industry': 'manufacturing', 'time_window': 'this_week'}, '先把纪要主文整理出来', '顺手提炼材料提纲', ['docs.productivity.cn'], ['sibling_competition', 'fallback']),
    spec('rollback_review_schedule', 'schedule.meeting.productivity.cn', 'hierarchy_sibling', '跨团队回滚复盘会准备下周二开', {'industry': 'enterprise_service', 'time_window': 'next_week'}, '先把排期和参会时段敲定', '提醒会前材料', ['docs.productivity.cn'], ['sibling_competition', 'fallback']),
    spec('implementation_sync_actions', 'action-items.meeting.productivity.cn', 'hierarchy_sibling', '实施同步会里已经散落出一堆 owner 和待办', {'industry': 'enterprise_service'}, '先把行动项和 owner 抽出来', '补一页纪要', ['summary.meeting.productivity.cn'], ['sibling_competition', 'fallback']),
    spec('xian_holiday_itinerary', 'xian.itinerary.travel.cn', 'hierarchy_sibling', '清明想去西安待三天看城墙和博物馆', {'city': 'Xian', 'budget_rmb': 4500}, '把西安这趟行程骨架排出来', '顺手看天气窗口', ['weather.cn'], ['sibling_competition', 'fallback'], 'l3 evidence 来自明确城市与出行时长。'),
    spec('beijing_expo_hotel', 'beijing.hotel.travel.cn', 'hierarchy_sibling', '一早要去北京展馆布场，只住一晚', {'city': 'Beijing'}, '筛北京这边住一晚最顺的酒店', '补通勤判断', ['transport.travel.cn'], ['sibling_competition', 'fallback']),
    spec('chengdu_training_hotel', 'chengdu.hotel.travel.cn', 'hierarchy_sibling', '去成都做两天客户培训，晚上才结束', {'city': 'Chengdu'}, '先筛成都这边回酒店不折腾的住处', '补地铁接驳判断', ['transport.travel.cn'], ['sibling_competition', 'fallback']),

    spec('industrial_api_policy_then_permit', 'policy.gov.cn', 'cross_domain', '工业数据接口准备对外开放给合作方', {'industry': 'manufacturing'}, '把适用规范和条线找全', '提醒是否还牵出备案动作', ['permit.gov.cn'], ['cross_domain_overlap']),
    spec('renewal_tax_then_issue', 'tax.finance.cn', 'cross_domain', '平台服务续费后需要补票并确认入账', {'industry': 'enterprise_service'}, '先厘清税务口径', '再把开票字段列一下', ['issue.invoice.finance.cn'], ['cross_domain_overlap']),
    spec('onepager_with_risk', 'docs.productivity.cn', 'cross_domain', '要把客户看的实施说明压成一页', {'industry': 'manufacturing'}, '先把文档结构压出来', '再补三条主要风险', ['risk.security.cn'], ['cross_domain_overlap']),
    spec('factory_meter_price', 'price.commerce.cn', 'cross_domain', '给产线买手持噪声仪', {'industry': 'manufacturing', 'channel': 'ecommerce'}, '先比一下不同渠道的价格', '看看有没有可叠的优惠', ['coupon.commerce.cn'], ['cross_domain_overlap']),
    spec('sports_cam_coupon', 'coupon.commerce.cn', 'cross_domain', '想买一台运动相机', {'channel': 'ecommerce'}, '先找最值的优惠入口', '顺手看不同平台差价', ['price.commerce.cn'], ['cross_domain_overlap']),
    spec('shenzhen_flight_with_weather', 'flight.travel.cn', 'cross_domain', '下周要飞深圳给客户做演示', {'city': 'Shenzhen', 'time_window': 'next_week'}, '先筛更合适的航班', '顺手看一下天气', ['weather.cn'], ['cross_domain_overlap']),
    spec('plant_gate_restaurant', 'restaurant.travel.cn', 'cross_domain', '外部访客来工厂沟通，中午要在园区附近吃饭', {'city': 'Suzhou'}, '先找附近方便吃饭的地方', '再看看有没有可用优惠', ['coupon.commerce.cn'], ['cross_domain_overlap']),
    spec('hangzhou_weather_then_itinerary', 'weather.cn', 'cross_domain', '周末去杭州看展，行程还没完全定', {'city': 'Hangzhou', 'time_window': 'weekend'}, '先确认天气窗口', '把行程顺一遍', ['itinerary.travel.cn'], ['cross_domain_overlap']),
    spec('sugar_control_nutrition', 'nutrition.health.cn', 'cross_domain', '最近体检提示控糖，想先从饮食改起', {'goal': 'diet_adjustment'}, '先给一版饮食调整方案', '补一点运动配合建议', ['fitness.health.cn'], ['cross_domain_overlap']),
    spec('clinic_with_course_tip', 'clinic.health.cn', 'cross_domain', '想先做一次基础门诊检查', {'goal': 'clinic'}, '先确定门诊怎么挂和怎么去', '顺手给点相关科普', ['course.education.cn'], ['cross_domain_overlap']),

    spec('campus_app_permit_plus_policy', 'permit.gov.cn', 'multi_intent', '园区服务小程序准备接短信核验', {'industry': 'enterprise_service', 'service': 'miniapp-sms'}, '把要补的准入动作列清', '给我排个办理顺序并附上依据', ['policy.gov.cn'], ['governance_fallback']),
    spec('partner_portal_compliance_plus_audit', 'compliance.security.cn', 'multi_intent', '合作伙伴门户准备开放报表下载', {'industry': 'enterprise_service'}, '先把合规检查项过一遍', '补审计留痕点', ['risk.security.cn'], ['governance_fallback']),
    spec('repair_portal_risk_plus_data', 'risk.security.cn', 'multi_intent', '设备自助报修入口准备开放给外部客户', {'industry': 'manufacturing'}, '先做风控检查', '看看是否连到数据合规问题', ['data.compliance.security.cn'], ['governance_fallback']),
    spec('invoice_flow_plus_tax', 'invoice.finance.cn', 'multi_intent', '年度支持服务的票据流转要一次梳顺', {'industry': 'enterprise_service'}, '先梳理发票处理路径', '补税务提醒', ['tax.finance.cn'], ['cross_domain_overlap']),
    spec('distributor_budget_plus_price', 'budget.finance.cn', 'multi_intent', '给渠道 onboarding 活动做一版预算', {'industry': 'enterprise_service'}, '先把预算拆出来', '补采购价格参考', ['price.commerce.cn'], ['cross_domain_overlap']),
    spec('meeting_plus_materials', 'meeting.productivity.cn', 'multi_intent', 'PMO 周会要把会务和材料一起理顺', {'industry': 'enterprise_service'}, '先把会议相关动作理顺', '补材料提纲', ['docs.productivity.cn'], ['cross_domain_overlap']),
    spec('suzhou_activity_plus_transport', 'activity.travel.cn', 'multi_intent', '在苏州多出半天空档，想临时加个活动', {'city': 'Suzhou'}, '先筛能排进去的活动', '看看交通怎么接', ['transport.travel.cn'], ['sibling_competition']),
    spec('airport_transport_plus_hotel', 'transport.travel.cn', 'multi_intent', '深夜到站后还要转去酒店', {'city': 'Shanghai'}, '先把接驳路线安排好', '再看住处是不是也该调整', ['hotel.travel.cn'], ['sibling_competition']),
    spec('data_gov_course_plus_tutor', 'course.education.cn', 'multi_intent', '想系统补一下数据治理基础', {'goal': 'self_learning'}, '先选一门入门课程', '再看看要不要找人辅导', ['tutoring.education.cn'], ['cross_domain_overlap']),
    spec('shanghai_hotel_plus_transport', 'shanghai.hotel.travel.cn', 'multi_intent', '下周去上海开客户 workshop，两天都很满', {'city': 'Shanghai'}, '先筛上海这边住处', '再把地铁通勤一并看掉', ['transport.travel.cn'], ['sibling_competition'], 'l3 evidence 来自明确城市和会议型场景。'),

    spec('supplier_alert_permit', 'permit.gov.cn', 'high_risk', '工业告警能力准备开放给外部供应商', {'industry': 'manufacturing', 'service': 'supplier-alert'}, '把上线前绝不能漏的许可动作列出来', '', [], ['governance_fallback']),
    spec('telemetry_policy_guard', 'policy.gov.cn', 'high_risk', '设备遥测接口准备给海外客户使用', {'industry': 'manufacturing'}, '先看政策边界和标准约束', '', [], ['governance_fallback']),
    spec('rebate_order_fraud', 'fraud.security.cn', 'high_risk', '营销返利订单里担心有人薅规则', {'industry': 'consumer_service'}, '先识别最该优先拦住的欺诈迹象', '', [], ['cross_domain_overlap']),
    spec('telemetry_export_check', 'data.compliance.security.cn', 'high_risk', '设备遥测数据准备同步到海外 BI', {'industry': 'manufacturing', 'destination': 'overseas_bi'}, '先看数据出境这条检查线', '', [], ['governance_fallback', 'fallback'], '涉及出境语义，保留 audit note 以便核对标签边界。'),
    spec('new_vendor_transaction_check', 'transaction.compliance.security.cn', 'high_risk', '首次给新清分服务商打款', {'industry': 'enterprise_service'}, '先做交易对象合规核验', '', [], ['governance_fallback', 'fallback']),
    spec('upgrade_channel_risk', 'risk.security.cn', 'high_risk', '远程升级通道准备对客户开放', {'industry': 'manufacturing'}, '先把高风险点排出来', '', [], ['governance_fallback']),
    spec('contractor_sso_account', 'account.compliance.security.cn', 'high_risk', '外包人员 SSO 入口准备并到统一账号体系', {'industry': 'enterprise_service'}, '先核对账号实名和权限治理项', '', [], ['governance_fallback', 'fallback']),
    spec('archive_export_compliance', 'compliance.security.cn', 'high_risk', '企业档案准备导到第三方系统做归档', {'industry': 'enterprise_service'}, '先做一轮合规审查', '', [], ['governance_fallback']),

    spec('cash_treasury_invest', 'invest.finance.cn', 'fast_path', '手上有一笔半年内不用的闲钱', {'industry': 'consumer_service'}, '给个更稳妥的理财方向'),
    spec('procurement_onepager_docs', 'docs.productivity.cn', 'fast_path', '把采购方案压成一页给领导看', {'industry': 'enterprise_service'}, '把文档提纲压出来'),
    spec('portable_ssd_price', 'price.commerce.cn', 'fast_path', '想买一块便携 SSD', {'channel': 'ecommerce'}, '比一下哪里更便宜'),
    spec('hangzhou_short_itinerary', 'hangzhou.itinerary.travel.cn', 'fast_path', '想去杭州安静待两天', {'city': 'Hangzhou'}, '排个杭州两天行程', '', [], ['sibling_competition', 'fallback'], 'l3 evidence 来自明确城市。'),
    spec('guangzhou_indoor_activity', 'activity.travel.cn', 'fast_path', '广州下雨天想找室内活动', {'city': 'Guangzhou'}, '推荐几个能安排进去的活动'),
    spec('restart_fitness_plan', 'fitness.health.cn', 'fast_path', '想把运动习惯重新捡起来', {'goal': 'fitness'}, '给个训练起步计划'),
    spec('pm_course_fast', 'course.education.cn', 'fast_path', '想补一门项目管理基础课', {'goal': 'self_learning'}, '推荐适合入门的课程'),
    spec('suzhou_weather_fast', 'weather.cn', 'fast_path', '明天去苏州办事', {'city': 'Suzhou', 'time_window': 'tomorrow'}, '查下天气和降雨'),

    spec('booth_budget_cap', 'budget.finance.cn', 'long_tail', '要给展台周边物料卡一个预算上限', {'industry': 'enterprise_service'}, '先把预算上限拆出来'),
    spec('sql_tutor_longtail', 'tutoring.education.cn', 'long_tail', '学 SQL 时想找个能带着做题的人', {'goal': 'self_learning'}, '先找种合适的辅导方式', '', [], ['lexical_overlap'], 'long-tail 场景，保留 note 方便后续抽检。'),
    spec('precheck_clinic_longtail', 'clinic.health.cn', 'long_tail', '体检前想先做个普通门诊咨询', {'goal': 'clinic'}, '看看门诊怎么安排'),
    spec('points_coupon_longtail', 'coupon.commerce.cn', 'long_tail', '想用积分换购一台咖啡机', {'channel': 'ecommerce'}, '先找能用的优惠或兑换入口'),
    spec('late_train_transport_longtail', 'transport.travel.cn', 'long_tail', '晚点到站后还要去城郊住处', {'city': 'Hangzhou'}, '看看怎么接驳最省事'),
    spec('airport_meal_restaurant_longtail', 'restaurant.travel.cn', 'long_tail', '转机只有两个小时，想先找个不折腾的饭点', {'city': 'Shanghai'}, '找家好到达的餐厅'),
]


def normalize_base_fqdn(fqdn: str) -> str:
    parts = fqdn.split('.')
    return '.'.join(parts[1:]) if len(parts) == 4 else fqdn


def compose_query(recipe: dict[str, Any], index: int) -> str:
    pattern = QUERY_PATTERNS[recipe['bucket']][index % len(QUERY_PATTERNS[recipe['bucket']])]
    query = pattern.format(scene=recipe['scene'], main=recipe['main'], secondary=recipe['secondary'])
    return query


def is_high_risk(base_fqdn: str, bucket: str) -> bool:
    return bucket == 'high_risk' or base_fqdn in {
        'permit.gov.cn',
        'policy.gov.cn',
        'compliance.security.cn',
        'risk.security.cn',
        'fraud.security.cn',
    }


def acceptable_fqdns(gt: str) -> list[str]:
    parts = gt.split('.')
    if len(parts) == 4:
        return [gt, '.'.join(parts[1:])]
    return [gt]


def primary_granularity(gt: str) -> str:
    return 'segment' if len(gt.split('.')) == 4 else 'base'


def build_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))

    input_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []

    base_counter: Counter[str] = Counter()
    l3_counter: Counter[str] = Counter()
    bucket_counter: Counter[str] = Counter()
    multi_counter = 0
    audit_note_nonempty = 0

    for index, recipe in enumerate(RECIPES, start=1):
        sample_id = f'holdout2_{index:06d}'
        family_id = f'holdout2_{recipe["slug"]}_f01'
        gt = recipe['gt']
        base = normalize_base_fqdn(gt)
        query = compose_query(recipe, index - 1)
        relevant = recipe['relevant'] if recipe['bucket'] in BUCKETS_WITH_EXPLICIT_SECONDARY else []
        confusions = list(dict.fromkeys(recipe['confusions'] + (['multi_intent'] if relevant else [])))
        if not resolver.has_fqdn(gt):
            raise ValueError(f'Unknown gt fqdn: {gt}')
        for fqdn in relevant + acceptable_fqdns(gt):
            if not resolver.has_fqdn(fqdn):
                raise ValueError(f'Unknown related/acceptable fqdn: {fqdn}')
        if recipe['note']:
            audit_note_nonempty += 1
        if relevant:
            multi_counter += 1

        input_rows.append({
            'id': sample_id,
            'namespace_version': NAMESPACE_VERSION,
            'query': query,
            'context': recipe['context'],
            'metadata': {
                'base_fqdn': base,
                'primary_granularity': primary_granularity(gt),
            },
            'source_bucket': recipe['bucket'],
            'difficulty_tag': recipe['bucket'],
        })
        label_rows.append({
            'id': sample_id,
            'family_id': family_id,
            'ground_truth_fqdn': gt,
            'acceptable_fqdns': acceptable_fqdns(gt),
            'relevant_fqdns': relevant,
            'intended_confusion_types': confusions,
            'primary_granularity': primary_granularity(gt),
            'secondary_intent_present': bool(relevant),
            'high_risk_case': is_high_risk(base, recipe['bucket']),
            'notes_for_audit': recipe['note'],
        })

        base_counter[base] += 1
        if primary_granularity(gt) == 'segment':
            l3_counter[base] += 1
        bucket_counter[recipe['bucket']] += 1

    for base, count in sorted(base_counter.items()):
        parts = base.split('.')
        coverage_rows.append({
            'base_fqdn': base,
            'l1': parts[-2],
            'l2': parts[-3] if len(parts) == 3 else '',
            'sample_count': count,
            'l3_sample_count': l3_counter[base],
            'bucket_summary': ';'.join(sorted({row['source_bucket'] for row in input_rows if row['metadata']['base_fqdn'] == base})),
        })

    total = len(label_rows)
    manifest = {
        'dataset_version': DATASET_VERSION,
        'namespace_version': NAMESPACE_VERSION,
        'status': 'unrevealed_seeded',
        'paths': {
            'input': str(INPUT_PATH.relative_to(ROOT)),
            'labels': str(LABEL_PATH.relative_to(ROOT)),
            'coverage_status': str(COVERAGE_PATH.relative_to(ROOT)),
        },
        'reveal_protocol': {
            'single_join': True,
            'development_may_read_input_only': True,
            'post_reveal_requires_version_bump': True,
        },
        'targets': {
            'total_range': [48, 60],
            'target_total': 54,
            'bucket_targets': BUCKET_TARGETS,
            'min_distinct_base_fqdn': 20,
            'multi_intent_ratio_range': [0.35, 0.5],
            'l3_ratio_min': 0.25,
            'notes_for_audit_nonempty_ratio_max': 0.1,
        },
        'current_stats': {
            'total_samples': total,
            'distinct_base_fqdn': len(base_counter),
            'l3_ratio': round(sum(l3_counter.values()) / max(total, 1), 4),
            'multi_intent_ratio': round(multi_counter / max(total, 1), 4),
            'source_bucket_counts': dict(bucket_counter),
            'high_risk_case_count': sum(1 for row in label_rows if row['high_risk_case']),
            'notes_for_audit_nonempty_ratio': round(audit_note_nonempty / max(total, 1), 4),
            'ood_like_count': 0,
        },
        'family_disjoint_against': [
            'data/agentdns_routing/formal/dev.jsonl',
            'data/agentdns_routing/formal/blind_input.jsonl',
            'data/agentdns_routing/formal/challenge_input.jsonl',
        ],
        'provenance': {
            'spec': 'closure/23_holdout2_data_spec.md',
            'built_on': '2026-03-22',
        },
        'last_validation_report': 'artifacts/dataset/holdout2_validation_report.json',
    }

    return input_rows, label_rows, manifest, coverage_rows


def ensure_formal_family_disjoint(label_rows: list[dict[str, Any]]) -> None:
    existing_families: set[str] = set()
    for path in FORMAL_FAMILY_FILES:
        rows = load_jsonl(path)
        for row in rows:
            family_id = row.get('family_id')
            if family_id:
                existing_families.add(family_id)
    overlap = existing_families.intersection({row['family_id'] for row in label_rows})
    if overlap:
        raise ValueError(f'holdout2 family_id 与 formal 已有 split 重叠: {sorted(overlap)}')


def ensure_query_disjoint(input_rows: list[dict[str, Any]]) -> None:
    existing_queries: set[str] = set()
    for path in [FORMAL_DIR / 'dev.jsonl', FORMAL_DIR / 'blind_input.jsonl', FORMAL_DIR / 'challenge_input.jsonl']:
        for row in load_jsonl(path):
            existing_queries.add(row['query'])
    overlap = existing_queries.intersection({row['query'] for row in input_rows})
    if overlap:
        raise ValueError('holdout2 query 与 formal 现有 split 存在完全重复文本')


def validate_recipe_targets(manifest: dict[str, Any], label_rows: list[dict[str, Any]]) -> None:
    total = len(label_rows)
    if not (48 <= total <= 60):
        raise ValueError(f'holdout2 总量越界: {total}')
    base_count = len({normalize_base_fqdn(row['ground_truth_fqdn']) for row in label_rows})
    if base_count < 20:
        raise ValueError(f'holdout2 base_fqdn 覆盖不足: {base_count} < 20')
    l3_ratio = manifest['current_stats']['l3_ratio']
    if l3_ratio < 0.25:
        raise ValueError(f'holdout2 l3_ratio 过低: {l3_ratio}')
    multi_ratio = manifest['current_stats']['multi_intent_ratio']
    if not (0.35 <= multi_ratio <= 0.5):
        raise ValueError(f'holdout2 multi_intent_ratio 越界: {multi_ratio}')
    if manifest['current_stats']['notes_for_audit_nonempty_ratio'] >= 0.1:
        raise ValueError('notes_for_audit 非空比例过高')


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def dump_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ['base_fqdn', 'l1', 'l2', 'sample_count', 'l3_sample_count', 'bucket_summary']
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    FORMAL_DIR.mkdir(parents=True, exist_ok=True)
    input_rows, label_rows, manifest, coverage_rows = build_rows()
    ensure_formal_family_disjoint(label_rows)
    ensure_query_disjoint(input_rows)
    validate_recipe_targets(manifest, label_rows)

    dump_jsonl(INPUT_PATH, input_rows)
    dump_jsonl(LABEL_PATH, label_rows)
    dump_csv(COVERAGE_PATH, coverage_rows)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest['current_stats'], ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
