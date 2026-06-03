from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentdns_routing.stage_r_clean import build_candidate_snapshot
from src.agentdns_routing.namespace import NamespaceResolver, load_jsonl

FORMAL_DIR = ROOT / 'data' / 'agentdns_routing' / 'formal'
DESCRIPTOR_PATH = ROOT / 'data' / 'agentdns_routing' / 'namespace_descriptors.jsonl'
INPUT_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_input.jsonl'
LABEL_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_labels.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_coverage.csv'
RANK_PROBE_PATH = FORMAL_DIR / 'hard_routing_boundary_v1_rank_probe.csv'

DATASET_VERSION = 'hard_routing_boundary_v1_20260602'
NAMESPACE_VERSION = 'ns_v1_20260311'
STAGE_R_VERSION = 'sr_clean_v2_20260314_related2'
RANK_PROBE_TOP_K = 25
MAX_QUERY_VARIANTS_PER_CASE = 3

SLICE_TARGETS = {
    'low_rank_gold': 80,
    'parent_child_granularity': 90,
    'primary_secondary_conflict': 90,
    'cross_domain_overlap': 90,
    'high_risk_governance_tone': 80,
    'near_duplicate_descriptors': 70,
}

SURFACE_STYLES = ['colloquial', 'formal', 'enterprise', 'compressed', 'indirect', 'mixed']

HUMAN_TAILS = [
    '不用写太长，先给我能照着做的一版',
    '后面的细节我再补，先把这一步定下来',
    '别写成大而全的方案，先说眼前怎么处理',
    '越具体越好，最好能直接列步骤',
    '先按今天能推进的做法来',
    '如果有前提条件，也顺手标一下',
    '先别展开太多周边事项',
    '我主要想把这件事先弄清楚',
    '先给一个稳妥点的处理办法',
    '不用面面俱到，别漏关键点就行',
    '先把我现在该做什么说清楚',
    '按普通人能看懂的方式说',
    '先给一个简版，必要顺序也带上',
    '给我一个可操作清单',
    '先判断这件事该怎么处理',
    '不要写太虚，直接说该怎么做',
    '先从最紧要的开始',
    '先按保守做法来',
    '只要这件事本身的处理办法',
    '别把后续执行铺太开',
    '先帮我把方向定住',
    '有不确定的地方也标出来',
    '先给能落地的一版',
    '直接告诉我第一步做什么',
    '先按现实可办的来',
    '短一点，但重点别漏',
    '先把要点列清楚',
    '我晚点再补材料，先给初步结论',
    '能按优先级排一下更好',
    '先不用考虑很远的后续安排',
    '最好按一二三列出来',
    '我现在只需要能继续往下做的版本',
    '先按最常见的情况处理',
    '如果需要我补信息，也直接说',
    '先给我一个不容易出错的做法',
    '不要绕太远，先回答这个问题',
    '我只看这一步该怎么落',
    '先把结论放前面',
    '能给两个备选也可以，但先别发散',
    '先帮我收口到能执行的动作',
    '按工作里实际会用到的说',
    '先别写背景说明，直接给处理建议',
    '我主要是怕漏掉关键步骤',
    '先按普通流程来，不用设计复杂方案',
    '如果有顺序要求，请一起写清楚',
    '先给我能拿去沟通的一版',
    '不用追求完整报告，先解决眼前问题',
    '麻烦直接列关键动作',
    '先帮我把容易踩坑的地方点出来',
    '只要当前阶段需要做的事',
    '先给一个低风险的处理顺序',
    '能不能按清单方式给我',
    '先回答最该先做哪几步',
    '别把这事说复杂了',
    '我现在需要的是可执行建议',
    '先按已经给出的信息判断',
    '必要时提醒我还缺什么材料',
    '先别展开成长期方案',
    '给我一个能马上对外沟通的说法',
    '先把该确认的点列出来',
]

HIGH_RISK_BASES = {
    'permit.gov.cn',
    'policy.gov.cn',
    'compliance.security.cn',
    'risk.security.cn',
    'fraud.security.cn',
}

COMPETITOR_HINTS = {
    'budget.finance.cn': '预算拆分',
    'account.compliance.security.cn': '账号权限检查',
    'action-items.meeting.productivity.cn': '会后待办',
    'beijing.hotel.travel.cn': '北京住宿',
    'clinic.health.cn': '门诊检查',
    'compliance.security.cn': '合规检查',
    'coupon.commerce.cn': '优惠券',
    'data.compliance.security.cn': '数据外发检查',
    'docs.productivity.cn': '材料整理',
    'fitness.health.cn': '运动计划',
    'flight.travel.cn': '航班安排',
    'hotel.travel.cn': '住宿安排',
    'invoice.finance.cn': '发票处理',
    'issue.invoice.finance.cn': '开票处理',
    'itinerary.travel.cn': '完整路线',
    'meeting.productivity.cn': '会议安排',
    'nutrition.health.cn': '饮食建议',
    'policy.gov.cn': '政策依据',
    'price.commerce.cn': '比价',
    'reimburse.invoice.finance.cn': '报销判断',
    'restaurant.travel.cn': '餐饮安排',
    'risk.security.cn': '风险排查',
    'schedule.meeting.productivity.cn': '会议排期',
    'summary.meeting.productivity.cn': '会议纪要',
    'tax.finance.cn': '税务处理',
    'transaction.compliance.security.cn': '付款对象核验',
    'transport.travel.cn': '交通接驳',
    'tutoring.education.cn': '导师答疑',
    'verify.invoice.finance.cn': '票据验真',
    'weather.cn': '天气窗口',
    'xian.itinerary.travel.cn': '西安路线',
}


def pick(items: list[str], index: int, offset: int = 0) -> str:
    return items[(index + offset) % len(items)]


def stable_index(text: str) -> int:
    return sum((idx + 1) * ord(char) for idx, char in enumerate(text))


def normalize_base_fqdn(fqdn: str) -> str:
    parts = fqdn.split('.')
    return '.'.join(parts[1:]) if len(parts) == 4 else fqdn


def primary_granularity(fqdn: str) -> str:
    return 'segment' if len(fqdn.split('.')) == 4 else 'base'


def acceptable_fqdns(fqdn: str) -> list[str]:
    base = normalize_base_fqdn(fqdn)
    return [fqdn] if base == fqdn else [fqdn, base]


def family_id_for(stress_slice: str, sample_index: int) -> str:
    return f'hard_boundary_v1_{stress_slice}_{sample_index:06d}_f01'


def paraphrase_group_id_for(stress_slice: str, slug: str) -> str:
    return f'hard_boundary_v1_{stress_slice}_{slug}'


def competing_hint(spec_row: dict[str, Any], occurrence: int) -> str:
    competitors = [COMPETITOR_HINTS.get(fqdn, fqdn) for fqdn in spec_row['competitors']]
    if not competitors:
        return '旁边事项'
    first = pick(competitors, occurrence)
    second = pick(competitors, occurrence, 1)
    if first == second:
        return first
    return f'{first}、{second}'


def scene_text(scene: str, occurrence: int) -> str:
    variants = [
        scene,
        f'帮我看下，{scene}',
        f'我这边的情况是，{scene}',
        f'现在碰到的是，{scene}',
        f'临时碰到一个情况，{scene}',
        f'我想处理一下这个事：{scene}',
        f'麻烦看下，{scene}',
        f'刚好遇到个情况，{scene}',
        f'手上有个事：{scene}',
        f'先问个具体情况：{scene}',
    ]
    return pick(variants, occurrence)


def first_action(text: str) -> str:
    return text if text.startswith('先') else f'先{text}'


def plain_action(text: str) -> str:
    return text[1:] if text.startswith('先') else text


def render_from_templates(templates: list[str], occurrence: int, **values: str) -> str:
    return pick(templates, occurrence).format(**values)


def spec(
    slug: str,
    gt: str,
    scenes: list[str],
    primaries: list[str],
    competitors: list[str],
    failure: str,
    note: str,
    context: dict[str, Any],
    relevant: list[str] | None = None,
    secondary_texts: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'slug': slug,
        'gt': gt,
        'scenes': scenes,
        'primaries': primaries,
        'competitors': competitors,
        'failure': failure,
        'note': note,
        'context': context,
        'relevant': relevant or [],
        'secondary_texts': secondary_texts or [],
    }


def add_specs(target: list[dict[str, Any]], rows: list[tuple[Any, ...]]) -> None:
    for slug, gt, scenes, primaries, competitors, failure, note, context, *optional in rows:
        relevant = optional[0] if len(optional) >= 1 else None
        secondary_texts = optional[1] if len(optional) >= 2 else None
        target.append(spec(slug, gt, scenes, primaries, competitors, failure, note, context, relevant, secondary_texts))


LOW_RANK_SPECS = [
    spec('docs_from_meeting_noise', 'docs.productivity.cn', ['验收会后老板只要一页纸给客户看', '复盘会后需要一页能给外部看的结论'], ['把结论写成能发出去的材料', '整理成一页对外说法'], ['meeting.productivity.cn', 'risk.security.cn'], 'meeting_or_risk_over_primary', '主动作是形成对外材料，会议和风险只是内容来源。', {'industry': 'enterprise_service'}),
    spec('course_without_course_word', 'course.education.cn', ['新人要补采购流程，部门希望先有一个学习起点', '运营同事想系统补 SQL 实战，但还没找到起步入口'], ['推荐一个能开始学的路径', '给一个先学什么的安排'], ['tutoring.education.cn', 'docs.productivity.cn'], 'tutoring_or_docs_over_primary', '主动作是推荐学习课程/路径，不是找导师或写材料。', {'goal': 'training'}),
    spec('nutrition_with_clinic_noise', 'nutrition.health.cn', ['体检提示控糖，医生建议先从日常吃法调起', '减脂这件事现在主要卡在怎么吃'], ['给一版每天怎么吃的调整方案', '把吃饭这块排清楚'], ['clinic.health.cn', 'fitness.health.cn'], 'clinic_or_fitness_over_primary', '主动作是饮食调整，门诊/训练只是干扰背景。', {'goal': 'diet'}),
    spec('fitness_without_alias', 'fitness.health.cn', ['检查结果没大问题，想把身体状态慢慢拉回来', '久坐太久，想先找一个保守起步节奏'], ['排一个每天怎么动的起步计划', '给一个不会太猛的恢复安排'], ['clinic.health.cn', 'nutrition.health.cn'], 'clinic_or_nutrition_over_primary', '主动作是训练安排，检查和饮食不是 primary。', {'goal': 'recovery'}),
    spec('invest_with_tax_noise', 'invest.finance.cn', ['手上有笔一年内不用的钱，收益税务可以提醒但别展开', '闲钱想稳一点放着，税务影响只要点到'], ['给几个稳妥的放钱方向', '帮我想怎么配置更稳'], ['tax.finance.cn', 'budget.finance.cn'], 'tax_or_budget_over_primary', '主动作是稳健理财配置，税务只是干扰线索。', {'horizon': 'one_year'}),
    spec('permit_with_policy_noise', 'permit.gov.cn', ['合作方下载入口准备开放，政策依据可以顺带列', '园区服务小程序要对外开，规范依据只作支撑'], ['列清楚上线前要办哪些手续', '把准入和备案顺序排出来'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_or_compliance_over_primary', '主动作是许可/备案/准入手续，不是泛政策检索。', {'service': 'external_portal'}),
    spec('activity_with_itinerary_noise', 'activity.travel.cn', ['西安多出半天空档，完整路线不用重排', '杭州展会结束后临时多出两个小时'], ['找几个能塞进去的玩点', '筛一个不折腾的活动'], ['itinerary.travel.cn', 'transport.travel.cn'], 'itinerary_or_transport_over_primary', '主动作是活动/景点推荐，不是完整路线或交通。', {'city': '西安'}),
    spec('restaurant_with_coupon_noise', 'restaurant.travel.cn', ['客户中午来园区附近，优惠可以顺手看看', '看展中间只留一顿饭的时间'], ['找一个方便吃饭的地方', '筛个不耽误事的餐厅'], ['coupon.commerce.cn', 'price.commerce.cn'], 'commerce_over_restaurant', '主动作是餐饮地点安排，优惠和价格只是次要线索。', {'city': '苏州'}),
    spec('transport_with_weather_noise', 'transport.travel.cn', ['到杭州东站后要赶去会场，天气只影响备选', '落地后要从机场去客户现场'], ['把接驳路线看清楚', '安排最省事的过去方式'], ['weather.cn', 'itinerary.travel.cn'], 'weather_or_itinerary_over_primary', '主动作是接驳交通，天气/行程不是 primary。', {'city': '杭州'}),
    spec('policy_with_risk_noise', 'policy.gov.cn', ['工业数据接口上线前，风险可以之后再排', '对外报表下载要先找依据'], ['查清适用的规范和标准', '把相关政策依据找全'], ['risk.security.cn', 'compliance.security.cn'], 'risk_or_compliance_over_primary', '主动作是政策/标准依据检索，不是风险或合规裁决。', {'service': 'data_api'}),
]

PARENT_CHILD_SPECS = [
    spec('data_compliance', 'data.compliance.security.cn', ['设备遥测明细要同步到海外 BI 看板', '工业相机日志要发给海外供应商看板'], ['先看数据外发前要补哪些检查', '把数据留存和外发检查过一遍'], ['compliance.security.cn', 'risk.security.cn', 'policy.gov.cn'], 'parent_fallback', '证据落在 data compliance segment，不能只退回泛合规。', {'industry': 'manufacturing'}),
    spec('account_compliance', 'account.compliance.security.cn', ['经销商门户要开放给外部协作人员', '客户自助台要接统一账号体系'], ['先看账号实名和权限要补哪些动作', '把账号权限和实名检查过一遍'], ['compliance.security.cn', 'risk.security.cn'], 'parent_fallback', '账号实名/权限是 account compliance segment 证据。', {'industry': 'enterprise_service'}),
    spec('transaction_compliance', 'transaction.compliance.security.cn', ['要给外部培训供应商打首笔款项', '新供应商第一次结算前还没核过对象'], ['先把打款前的交易对象核验理清', '判断付款对象前置检查有哪些'], ['compliance.security.cn', 'risk.security.cn', 'invoice.finance.cn'], 'parent_fallback', '交易对象/付款对象核验应命中 transaction compliance segment。', {'industry': 'enterprise_service'}),
    spec('invoice_issue', 'issue.invoice.finance.cn', ['收了设备维保年费后需要补电子票', '客户付了培训费但开票字段还没理清'], ['先确认开票入口和必填字段', '把这张票怎么开理清楚'], ['invoice.finance.cn', 'tax.finance.cn'], 'parent_fallback', '开票/出具发票是 issue invoice segment 证据。', {'industry': 'enterprise_service'}),
    spec('invoice_verify', 'verify.invoice.finance.cn', ['线下展会回来收了一批住宿和搭建票据', '手里有一批培训费票据还没查真伪'], ['先把票据验真这一步做掉', '看看这些票据真不真、能不能用'], ['invoice.finance.cn', 'tax.finance.cn'], 'parent_fallback', '验真/查验是真伪 segment 证据。', {'industry': 'enterprise_service'}),
    spec('invoice_reimburse', 'reimburse.invoice.finance.cn', ['驻场工程师报回一组打车和住宿票', '活动结束后同事提交了一批报销票据'], ['先判断哪些票能直接报销入账', '把报销边界过一遍'], ['invoice.finance.cn', 'tax.finance.cn'], 'parent_fallback', '报销/入账是 reimburse invoice segment 证据。', {'industry': 'enterprise_service'}),
    spec('meeting_schedule', 'schedule.meeting.productivity.cn', ['跨团队回滚复盘会准备下周二开', '项目评审会人和时间还没对齐'], ['先把排期和参会时段敲定', '把会议时间和参会人约起来'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', '排期/时间/参会人是 schedule meeting segment 证据。', {'meeting_type': 'review'}),
    spec('meeting_summary', 'summary.meeting.productivity.cn', ['生产调度周会刚结束，录音和记录都在', '实施同步会结束后散落记录很多'], ['先把纪要主文整理出来', '把会上的结论整理成纪要'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', '纪要/总结是 summary meeting segment 证据。', {'meeting_type': 'sync'}),
    spec('meeting_action_items', 'action-items.meeting.productivity.cn', ['实施同步会里已经散落出一堆 owner 和待办', '复盘会上冒出很多后续任务'], ['先把行动项和 owner 抽出来', '把会后的待办整理清楚'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', 'owner/待办/行动项是 action-items segment 证据。', {'meeting_type': 'sync'}),
    spec('hotel_city', 'beijing.hotel.travel.cn', ['一早要去北京展馆布场，只住一晚', '北京转机过夜后第二天要进场'], ['筛北京这边住一晚最顺的酒店', '帮我挑北京不折腾的住处'], ['hotel.travel.cn', 'itinerary.travel.cn', 'transport.travel.cn'], 'parent_fallback', '明确城市与住宿场景构成北京酒店 l3 证据。', {'city': '北京'}),
    spec('itinerary_city', 'xian.itinerary.travel.cn', ['清明想去西安待三天看城墙和博物馆', '西安这段三天旅游还没排顺'], ['把西安这趟行程骨架排出来', '先把西安每天怎么走顺一下'], ['itinerary.travel.cn', 'activity.travel.cn', 'hotel.travel.cn'], 'parent_fallback', '明确城市与行程规划构成西安 itinerary l3 证据。', {'city': '西安'}),
]

PRIMARY_SECONDARY_SPECS = [
    spec('invoice_reimburse_tax', 'reimburse.invoice.finance.cn', ['这批培训费发票需要先分清哪些能报销', '同事报回来的住宿票要先判断能不能报'], ['先判断哪些能直接报销', '把报销边界分清楚'], ['tax.finance.cn', 'invoice.finance.cn'], 'secondary_steals_primary', '主任务是报销判断，税务只是顺带提醒。', {'expense_type': '培训费'}, ['tax.finance.cn'], ['顺手提醒税务口径', '税务影响看一眼就行']),
    spec('flight_weather', 'flight.travel.cn', ['下周去深圳做演示', '去杭州布场这趟窗口很紧'], ['先筛合适的航班', '把出发和返回航班挑出来'], ['weather.cn', 'itinerary.travel.cn'], 'secondary_steals_primary', '主任务是航班筛选，天气只是次要检查项。', {'city': '深圳'}, ['weather.cn'], ['天气也看一眼', '顺手确认天气窗口']),
    spec('docs_policy', 'docs.productivity.cn', ['客户说明书要压成一页', '对外说明要给合作伙伴看'], ['先把材料结构搭出来', '把一页说明写出来'], ['policy.gov.cn', 'compliance.security.cn'], 'secondary_steals_primary', '主任务是写材料，政策依据只是内容素材。', {'document': 'one_pager'}, ['policy.gov.cn'], ['顺手补相关政策依据', '把引用规范列在后面']),
    spec('budget_price', 'budget.finance.cn', ['设备巡检项目要控成本', '驻场培训周费用盘子没压住'], ['先拆预算和费用上限', '把成本盘子拆清楚'], ['price.commerce.cn', 'invoice.finance.cn'], 'secondary_steals_primary', '主任务是预算拆分，报价只是辅助输入。', {'project': '巡检'}, ['price.commerce.cn'], ['顺手给关键设备比价', '报价参考放后面']),
    spec('course_docs', 'course.education.cn', ['新人要补采购流程', 'SQL 实战学习要起步'], ['先推荐一门能开始的课', '给一个学习路径'], ['docs.productivity.cn', 'tutoring.education.cn'], 'secondary_steals_primary', '主任务是课程推荐，材料提纲只是配套。', {'goal': 'training'}, ['docs.productivity.cn'], ['顺手列个学习材料提纲', '材料清单放后面']),
    spec('nutrition_fitness', 'nutrition.health.cn', ['最近想减脂', '体检提示要控糖'], ['先给饮食调整方案', '把怎么吃排清楚'], ['fitness.health.cn', 'clinic.health.cn'], 'secondary_steals_primary', '主任务是饮食调整，训练只是配合。', {'goal': 'diet'}, ['fitness.health.cn'], ['顺手给一点运动配合', '训练建议简单带一下']),
    spec('permit_policy', 'permit.gov.cn', ['短信核验能力要对外开放', '合作方下载入口准备上线'], ['先列要补哪些备案和准入手续', '把办理顺序排出来'], ['policy.gov.cn', 'compliance.security.cn'], 'secondary_steals_primary', '主任务是手续/备案，政策依据只是支撑。', {'service': 'sms'}, ['policy.gov.cn'], ['顺手找相关依据', '政策条文列在后面']),
    spec('restaurant_coupon', 'restaurant.travel.cn', ['客户中午来工厂沟通', '展会中间只有一顿饭时间'], ['先找附近方便吃饭的地方', '筛一个不耽误事的餐厅'], ['coupon.commerce.cn', 'price.commerce.cn'], 'secondary_steals_primary', '主任务是餐饮地点，优惠只是附加。', {'city': '苏州'}, ['coupon.commerce.cn'], ['顺手看有没有优惠', '折扣信息简单带一下']),
    spec('risk_policy', 'risk.security.cn', ['外部报修入口准备开放', '供应商协作端口要上线'], ['先排主要风险点', '把容易出事的地方过一遍'], ['policy.gov.cn', 'compliance.security.cn'], 'secondary_steals_primary', '主任务是风险评估，政策只是参考。', {'service': 'portal'}, ['policy.gov.cn'], ['顺手列相关政策依据', '规范引用放后面']),
]

CROSS_DOMAIN_SPECS = [
    spec('travel_weather_hotel_primary_itinerary', 'itinerary.travel.cn', ['下周去云南玩，天气和酒店也要看', '云南五天出行还没排，住宿和降雨都悬着'], ['先把路线和每天安排排出来', '把行程骨架排顺'], ['weather.cn', 'hotel.travel.cn'], 'cross_domain_over_primary', '旅行、天气、住宿共现，但主动作是行程规划。', {'city': '云南'}, ['weather.cn', 'hotel.travel.cn'], ['天气窗口和住宿也带上', '顺手确认天气和住处']),
    spec('finance_tax_invoice_primary_budget', 'budget.finance.cn', ['客户培训活动要控成本，发票和税务也会牵出来', '设备采购要先压预算，后面还有票据和税务'], ['先把预算和费用上限拆出来', '把成本盘子排清楚'], ['invoice.finance.cn', 'tax.finance.cn'], 'cross_domain_over_primary', '财务多域共现，但主动作是预算拆分。', {'project': 'training'}, ['invoice.finance.cn', 'tax.finance.cn'], ['票据和税务也顺手提醒']),
    spec('docs_risk_policy', 'docs.productivity.cn', ['客户说明要带政策依据和风险提醒', '对外材料里要写规范和风险'], ['先把一页材料结构写出来', '把说明文档主干搭好'], ['policy.gov.cn', 'risk.security.cn'], 'cross_domain_over_primary', '政策/风险是内容素材，主动作是文档整理。', {'document': 'client_note'}, ['policy.gov.cn', 'risk.security.cn'], ['政策依据和风险点也补上']),
    spec('meeting_docs_compliance', 'meeting.productivity.cn', ['客户评审要约起来，材料和合规点也要准备', '下周上线评审要开，会前说明和合规检查都缺'], ['先把会议时间和参会人排好', '把评审会约起来'], ['docs.productivity.cn', 'compliance.security.cn'], 'cross_domain_over_primary', '文档/合规共现，但主动作是会议安排。', {'meeting_type': 'review'}, ['docs.productivity.cn', 'compliance.security.cn'], ['材料和合规点也一起准备']),
    spec('commerce_restaurant_coupon', 'restaurant.travel.cn', ['客户招待要订餐，优惠和价格也要看', '团建午餐要找门店，同时想控人均'], ['先筛附近合适餐厅', '找一个方便吃饭的地方'], ['coupon.commerce.cn', 'price.commerce.cn'], 'cross_domain_over_primary', 'commerce 词汇共现，但主动作是餐厅安排。', {'event': 'lunch'}, ['coupon.commerce.cn', 'price.commerce.cn'], ['优惠和人均价格也看']),
    spec('health_nutrition_clinic', 'nutrition.health.cn', ['控糖前要看门诊，但现在最想先把吃法调起来', '体检后要约检查，也想先有饮食方案'], ['先给一版饮食调整建议', '把日常吃法安排出来'], ['clinic.health.cn', 'fitness.health.cn'], 'cross_domain_over_primary', '门诊/运动共现，但主动作是营养饮食。', {'goal': 'health'}, ['clinic.health.cn', 'fitness.health.cn'], ['门诊和训练也简单提醒']),
    spec('weather_travel_overlap', 'weather.cn', ['杭州周末行程和住宿都还没最后定，但现在最怕天气窗口不稳', '西安看展那天路线可以晚点排，先担心会不会下雨'], ['先确认天气和降雨窗口', '把那几天天气看准'], ['itinerary.travel.cn', 'hotel.travel.cn'], 'cross_domain_over_primary', '旅行/住宿线索共现，但主动作是天气查询。', {'city': '杭州'}, ['itinerary.travel.cn'], ['行程安排之后再顺一下']),
    spec('education_docs_meeting', 'course.education.cn', ['新人培训要开答疑会，也要准备一页材料', '采购流程培训既要说明也要排会'], ['先定课程路径', '推荐能开始的课'], ['docs.productivity.cn', 'meeting.productivity.cn'], 'cross_domain_over_primary', '会议/文档是配套，主动作是课程选择。', {'training': 'new_hire'}, ['docs.productivity.cn', 'meeting.productivity.cn'], ['答疑会和材料也带上']),
    spec('governance_permit_risk', 'permit.gov.cn', ['合作方下载入口上线前，风险和政策都要注意', '对外通知接口要开放，合规风险也不少'], ['先列备案和准入手续', '把要办的前置动作排清楚'], ['risk.security.cn', 'policy.gov.cn'], 'cross_domain_over_primary', '风险/政策共现，但主动作是许可备案。', {'service': 'download'}, ['risk.security.cn', 'policy.gov.cn'], ['风险和政策依据也带上']),
]

HIGH_RISK_SPECS = [
    spec('permit_governance_tone', 'permit.gov.cn', ['合作方下载入口准备上线，别先做功能设计', '短信核验能力准备对外开放，风险先不展开'], ['先列备案、准入手续和顺序', '把要办哪些资质动作列清'], ['compliance.security.cn', 'risk.security.cn', 'policy.gov.cn'], 'generic_governance_over_primary', '治理口吻很强，但主动作是许可/备案。', {'service': 'download'}),
    spec('policy_governance_tone', 'policy.gov.cn', ['工业数据接口上线前大家都担心合规风险', '对外报表下载要上线，审计会追依据'], ['先查适用规范和标准', '把政策依据找全'], ['compliance.security.cn', 'risk.security.cn', 'permit.gov.cn'], 'generic_governance_over_primary', '高风险语气不能盖过政策检索主动作。', {'service': 'data_api'}),
    spec('compliance_governance_tone', 'compliance.security.cn', ['项目归档资料要外发到第三方系统，风险和留痕都要看', '合作方门户要开放下载，审计口径还没定'], ['先做合规检查项', '把审计留痕要求过一遍'], ['risk.security.cn', 'policy.gov.cn', 'permit.gov.cn'], 'risk_or_policy_over_primary', '主动作是合规/审计检查。', {'industry': 'enterprise_service'}),
    spec('risk_governance_tone', 'risk.security.cn', ['供应商协作端口准备开放，合规和策略都有人提', '外部报修入口上线前担心踩线'], ['先排主要风险点', '把容易出事的地方列出来'], ['compliance.security.cn', 'policy.gov.cn', 'fraud.security.cn'], 'compliance_or_policy_over_primary', '主动作是风险评估，不是泛合规或政策。', {'service': 'portal'}),
    spec('fraud_governance_tone', 'fraud.security.cn', ['返利订单怕被拆单薅补贴，审计也会追', '优惠券活动担心有人钻规则'], ['先列异常识别和拦截规则', '把最该防的作弊信号排出来'], ['risk.security.cn', 'compliance.security.cn'], 'risk_over_fraud', '异常套利/拦截规则是反欺诈证据。', {'campaign': 'rebate'}),
    spec('invoice_high_risk_tone', 'issue.invoice.finance.cn', ['这笔培训费开错票会影响后续审计', '服务费收款后补票，税务和合规都很敏感'], ['先把开票字段和入口确认好', '判断这张票该怎么开'], ['tax.finance.cn', 'compliance.security.cn'], 'tax_or_compliance_over_primary', '高风险口吻下主动作仍是开票。', {'expense_type': 'training'}),
    spec('tax_high_risk_tone', 'tax.finance.cn', ['服务费入账如果税务口径错了会很麻烦', '设备补贴收入涉及政策和合规'], ['先看税务上该怎么处理', '把适用税务口径确认好'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_or_compliance_over_primary', '主动作是税务处理。', {'revenue_type': 'service_fee'}),
    spec('transaction_high_risk_tone', 'transaction.compliance.security.cn', ['新供应商首笔付款一旦打错对象代价很高', '外部培训供应商打款前审计会查'], ['先核付款对象和前置检查', '把交易对象核验理一遍'], ['risk.security.cn', 'invoice.finance.cn'], 'risk_or_invoice_over_primary', '付款对象核验应命中 transaction compliance segment。', {'industry': 'enterprise_service'}),
]

NEAR_DUPLICATE_SPECS = [
    spec('risk_vs_fraud', 'fraud.security.cn', ['返利订单里担心有人拆单薅补贴', '积分换购担心被刷号套利'], ['先列异常识别和拦截规则', '把欺诈信号排出来'], ['risk.security.cn', 'compliance.security.cn'], 'near_duplicate_confusion', '欺诈/套利/拦截是 fraud，不是普通 risk。', {'campaign': 'rebate'}, ['risk.security.cn'], ['整体风险可以顺手看']),
    spec('policy_vs_permit', 'policy.gov.cn', ['对外通知接口上线前想知道依据', '工业数据共享接口上线前标准还没查'], ['先查适用规范和标准', '把政策依据找全'], ['permit.gov.cn', 'compliance.security.cn'], 'near_duplicate_confusion', '用户要查依据，不是办理许可。', {'service': 'notification'}),
    spec('permit_vs_policy', 'permit.gov.cn', ['合作方下载入口要开放，依据之后再看', '园区小程序上线前手续还不清楚'], ['先列要办哪些备案和准入手续', '把办理顺序列出来'], ['policy.gov.cn', 'compliance.security.cn'], 'near_duplicate_confusion', '用户要办手续，不是只查政策。', {'service': 'miniapp'}),
    spec('price_vs_coupon', 'price.commerce.cn', ['便携 SSD 不同平台差价很大', '会议麦克风报价看起来不一致'], ['先比不同渠道价格', '把报价按同一口径比一下'], ['coupon.commerce.cn', 'budget.finance.cn'], 'near_duplicate_confusion', '用户要比价，不是找优惠券。', {'product': 'ssd'}),
    spec('coupon_vs_price', 'coupon.commerce.cn', ['运动相机想买得便宜点，但重点是有没有券', '投影仪下单前想找可叠优惠'], ['先看有没有优惠券或折扣', '找最划算的优惠入口'], ['price.commerce.cn', 'budget.finance.cn'], 'near_duplicate_confusion', '用户要优惠/折扣，不是普通比价。', {'product': 'camera'}),
    spec('course_vs_tutoring', 'course.education.cn', ['想系统补 SQL 实战，先从课开始', '采购流程要学起来，先找课程入口'], ['推荐一门能开始的课', '给一个学习路径'], ['tutoring.education.cn', 'docs.productivity.cn'], 'near_duplicate_confusion', '课程路径不是导师辅导。', {'goal': 'sql'}),
    spec('tutoring_vs_course', 'tutoring.education.cn', ['采购流程总卡住，想找人带着答疑', 'SQL 实战学不下去，需要有人辅导'], ['找个合适的辅导方式', '帮我找能答疑的导师'], ['course.education.cn', 'meeting.productivity.cn'], 'near_duplicate_confusion', '导师/辅导是 tutoring，不是课程推荐。', {'goal': 'sql'}),
    spec('nutrition_vs_fitness', 'nutrition.health.cn', ['减脂先从吃法调整，不急着运动', '控糖重点是日常饮食怎么改'], ['给一版饮食调整建议', '把三餐怎么吃排出来'], ['fitness.health.cn', 'clinic.health.cn'], 'near_duplicate_confusion', '饮食/营养不是训练计划。', {'goal': 'diet'}),
    spec('fitness_vs_nutrition', 'fitness.health.cn', ['饮食先不展开，想先恢复运动节奏', '久坐后想从轻量运动开始'], ['排一个起步训练计划', '给一个每天怎么动的安排'], ['nutrition.health.cn', 'clinic.health.cn'], 'near_duplicate_confusion', '训练/运动是 fitness，不是营养。', {'goal': 'training'}),
    spec('clinic_vs_nutrition_fitness', 'clinic.health.cn', ['控糖前饮食和运动先不展开，想先知道普通门诊怎么约', '恢复训练前不急着排计划，先确认基础检查怎么走'], ['看看普通门诊或检查该怎么约', '先把基础检查入口看清楚'], ['nutrition.health.cn', 'fitness.health.cn'], 'near_duplicate_confusion', '门诊/检查是 clinic，不是营养或训练计划。', {'goal': 'checkup'}),
    spec('meeting_vs_docs', 'meeting.productivity.cn', ['材料之后再写，先把评审会约起来', '说明会要开，但文档还不急'], ['先排会议时间和参会人', '把会议安排敲定'], ['docs.productivity.cn', 'schedule.meeting.productivity.cn'], 'near_duplicate_confusion', '用户要会议安排，不是文档撰写。', {'meeting_type': 'review'}),
]


add_specs(
    LOW_RANK_SPECS,
    [
        ('docs_after_customer_call', 'docs.productivity.cn', ['客户电话里说了一堆验收口径', '售后沟通后只剩几条能写给客户的话'], ['整理成能发客户的说明', '把对外回复写成一页'], ['meeting.productivity.cn', 'risk.security.cn'], 'meeting_or_risk_over_primary', '用户要形成文档输出，通话/风险只是素材。', {'document': 'customer_reply'}),
        ('docs_acceptance_brief', 'docs.productivity.cn', ['验收材料散在聊天记录和会议截图里', '项目阶段结论还没形成可发版本'], ['把材料收成一版说明', '写一份能给领导看的摘要'], ['meeting.productivity.cn', 'summary.meeting.productivity.cn'], 'meeting_over_docs', '用户要文档成稿，不是安排会议或只做纪要。', {'document': 'acceptance_note'}),
        ('docs_partner_position', 'docs.productivity.cn', ['合作方追问我们对接口调整的口径', '外部伙伴要一段正式解释'], ['写一版对外说法', '把立场说明整理出来'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_over_docs', '政策/合规是背景，gold 是文档整理。', {'document': 'external_position'}),
        ('course_new_tool_path', 'course.education.cn', ['部门刚换了低代码工具，大家都没系统学过', '新来的运营要补一套数据看板基础'], ['给一个学习路径', '推荐能开始学的课'], ['tutoring.education.cn', 'docs.productivity.cn'], 'tutoring_or_docs_over_primary', '用户要课程/学习路径，不是找导师或写材料。', {'goal': 'tool_learning'}),
        ('course_procurement_refresh', 'course.education.cn', ['采购制度改过几次，新同事听不懂流程', '合规培训后还想系统补一遍采购知识'], ['安排先学什么', '找一门入门课程'], ['policy.gov.cn', 'tutoring.education.cn'], 'policy_or_tutoring_over_primary', '制度是背景，gold 是课程学习路径。', {'goal': 'procurement_training'}),
        ('course_ops_sql', 'course.education.cn', ['运营报表老出错，想从 SQL 基础补起', '活动分析要自己写查询，基础还不稳'], ['给一条从零开始的学习路线', '推荐适合入门的课程'], ['docs.productivity.cn', 'tutoring.education.cn'], 'docs_or_tutoring_over_primary', '用户要系统学习路径，不是文档或辅导。', {'goal': 'sql_training'}),
        ('nutrition_night_shift', 'nutrition.health.cn', ['夜班后胃口乱，体检又提示血脂偏高', '加班多了以后吃饭节奏全乱了'], ['安排一版日常吃法', '把三餐怎么调说清楚'], ['clinic.health.cn', 'fitness.health.cn'], 'clinic_or_fitness_over_primary', '检查/运动是背景，gold 是营养饮食。', {'goal': 'diet'}),
        ('nutrition_pressure_high', 'nutrition.health.cn', ['家里老人血压偏高，医生说先从吃饭改', '体检提醒少盐少油，但不知道怎么安排'], ['给一版低盐饮食安排', '把每天吃什么排一下'], ['clinic.health.cn', 'fitness.health.cn'], 'clinic_or_fitness_over_primary', '用户要饮食安排，不是门诊或训练。', {'goal': 'low_salt'}),
        ('nutrition_business_trip', 'nutrition.health.cn', ['出差一周都在外面吃，想尽量控糖', '酒店早餐和外卖为主，怕饮食失控'], ['给一版出差吃法建议', '安排不太难执行的饮食方案'], ['hotel.travel.cn', 'fitness.health.cn'], 'hotel_or_fitness_over_primary', '出差是场景，gold 是营养饮食。', {'goal': 'travel_diet'}),
        ('fitness_knee_recovery', 'fitness.health.cn', ['膝盖不太舒服但检查没大问题', '运动停了很久，担心一下子练猛了'], ['排一个轻量恢复计划', '安排每天怎么动'], ['clinic.health.cn', 'nutrition.health.cn'], 'clinic_or_nutrition_over_primary', '用户要运动恢复计划，不是看诊或饮食。', {'goal': 'recovery'}),
        ('fitness_office_mobility', 'fitness.health.cn', ['办公室久坐肩颈很紧', '每天开会太多，想插一点轻量活动'], ['给一套工位活动安排', '排一个不占时间的运动节奏'], ['meeting.productivity.cn', 'nutrition.health.cn'], 'meeting_or_nutrition_over_primary', '会议是背景，gold 是运动计划。', {'goal': 'mobility'}),
        ('fitness_hotel_room', 'fitness.health.cn', ['出差住酒店，没有器械也想保持运动', '外地培训几天，晚上只有房间里能动'], ['给一套无器械训练安排', '安排房间里能做的运动'], ['hotel.travel.cn', 'nutrition.health.cn'], 'hotel_or_nutrition_over_primary', '住宿是场景，gold 是运动训练。', {'goal': 'bodyweight'}),
        ('invest_bonus_idle', 'invest.finance.cn', ['年终奖暂时不用，想放得稳一点', '手里有一笔奖金，短期不想乱花'], ['想几个稳妥配置方向', '安排保守一点的放钱方案'], ['tax.finance.cn', 'budget.finance.cn'], 'tax_or_budget_over_primary', '用户要投资配置，不是税务或预算。', {'horizon': 'one_year'}),
        ('invest_parent_money', 'invest.finance.cn', ['父母有笔闲钱不想承担大波动', '家里存款想找个低风险去处'], ['给几个稳健选择', '帮忙想怎么配置更稳'], ['budget.finance.cn', 'tax.finance.cn'], 'budget_or_tax_over_primary', '用户要理财配置，预算/税务不是 primary。', {'risk_preference': 'low'}),
        ('invest_emergency_reserve', 'invest.finance.cn', ['应急金放卡里收益太低', '备用金想保持流动性又别太浪费'], ['给一个稳妥放置方案', '看看怎么放比较合适'], ['budget.finance.cn', 'tax.finance.cn'], 'budget_or_tax_over_primary', '用户要资金配置，不是预算拆账。', {'horizon': 'liquid'}),
        ('permit_api_partner', 'permit.gov.cn', ['合作接口要开放给外部厂商调用', '供应商自助查询入口准备上线'], ['列要补哪些手续', '把准入和备案步骤排一下'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_or_compliance_over_primary', '用户要办理/准入手续，不是只查政策。', {'service': 'partner_api'}),
        ('permit_campus_service', 'permit.gov.cn', ['园区预约服务准备给外部访客用', '访客登记小程序要从内测转公开'], ['看上线前要办什么', '列清楚备案和准入顺序'], ['policy.gov.cn', 'risk.security.cn'], 'policy_or_risk_over_primary', '用户要上线手续，风险/政策是背景。', {'service': 'visitor_service'}),
        ('permit_training_platform', 'permit.gov.cn', ['线上培训入口准备面向合作单位开放', '企业课程平台要接外部账号'], ['把上线前置手续列出来', '确认需要哪些准入动作'], ['policy.gov.cn', 'account.compliance.security.cn'], 'policy_or_account_over_primary', '用户要许可/准入，不是账号合规。', {'service': 'training_platform'}),
        ('activity_rainy_gap', 'activity.travel.cn', ['成都下午可能下雨，原计划空出两小时', '展馆附近临时多出一段空档'], ['找几个不折腾的活动', '筛一点能临时去的玩点'], ['weather.cn', 'itinerary.travel.cn'], 'weather_or_itinerary_over_primary', '天气/行程是背景，gold 是活动推荐。', {'city': '成都'}),
        ('activity_family_halfday', 'activity.travel.cn', ['带孩子去南京，半天时间不好安排', '老人小孩同行，下午只能轻松逛一下'], ['找几个轻松活动', '筛适合半天的玩点'], ['itinerary.travel.cn', 'restaurant.travel.cn'], 'itinerary_or_restaurant_over_primary', '用户要活动点，不是完整路线或餐厅。', {'city': '南京'}),
        ('activity_museum_gap', 'activity.travel.cn', ['博物馆闭馆后还剩两个小时', '西安晚上饭前有一小段空闲'], ['找点附近能去的地方', '筛几个短时间活动'], ['restaurant.travel.cn', 'itinerary.travel.cn'], 'restaurant_or_itinerary_over_primary', '用户要活动推荐。', {'city': '西安'}),
        ('restaurant_halal_client', 'restaurant.travel.cn', ['客户有清真饮食要求，下午还要赶会', '外宾中午来访，吃饭时间很紧'], ['找合适的吃饭地点', '筛一个方便的餐厅'], ['meeting.productivity.cn', 'coupon.commerce.cn'], 'meeting_or_coupon_over_primary', '用户要餐厅地点，会议/优惠是背景。', {'city': '北京'}),
        ('restaurant_vegetarian_team', 'restaurant.travel.cn', ['团队里有人吃素，晚上要聚一下', '培训结束后要找个大家都能吃的地方'], ['找一个合适餐厅', '筛个不踩雷的吃饭地方'], ['price.commerce.cn', 'coupon.commerce.cn'], 'commerce_over_restaurant', '用户要餐饮地点，不是比价或优惠。', {'city': '上海'}),
        ('restaurant_late_arrival', 'restaurant.travel.cn', ['航班落地很晚，还得找点能吃的', '到酒店附近已经九点多，想简单吃一顿'], ['找附近还开着的餐厅', '筛个方便吃饭的地方'], ['flight.travel.cn', 'hotel.travel.cn'], 'flight_or_hotel_over_primary', '航班/酒店是背景，gold 是餐厅。', {'city': '杭州'}),
        ('transport_hospital_transfer', 'transport.travel.cn', ['从医院出来要赶去高铁站', '陪诊结束后要尽快去机场'], ['安排怎么过去最省事', '把接驳路线看清楚'], ['clinic.health.cn', 'flight.travel.cn'], 'clinic_or_flight_over_primary', '用户要交通接驳，不是就医或航班。', {'city': '上海'}),
        ('transport_factory_station', 'transport.travel.cn', ['从工厂园区去火车站不熟路', '客户现场结束后要赶末班车'], ['安排过去方式', '看怎么走最稳'], ['meeting.productivity.cn', 'weather.cn'], 'meeting_or_weather_over_primary', '用户要交通路线。', {'city': '苏州'}),
        ('transport_campus_shuttle', 'transport.travel.cn', ['园区几个楼之间要接待参观团', '会场和酒店之间要来回接驳'], ['把接驳路线安排一下', '看怎么过去不折腾'], ['hotel.travel.cn', 'meeting.productivity.cn'], 'hotel_or_meeting_over_primary', '用户要交通接驳。', {'city': '北京'}),
        ('policy_ai_service_basis', 'policy.gov.cn', ['智能客服准备接入外部用户，先要找依据', 'AI 助手对客户开放前，领导问有没有规范'], ['查适用规范和标准', '把相关政策依据列出来'], ['permit.gov.cn', 'risk.security.cn'], 'permit_or_risk_over_primary', '用户要政策依据，不是手续或风险评估。', {'service': 'ai_assistant'}),
        ('policy_data_report_basis', 'policy.gov.cn', ['对外报表下载范围要定，先看依据', '数据共享口径没定，法务让先找标准'], ['找相关规范依据', '查清适用标准'], ['compliance.security.cn', 'permit.gov.cn'], 'compliance_or_permit_over_primary', '用户要政策/标准检索。', {'service': 'data_report'}),
        ('policy_cross_border_doc', 'policy.gov.cn', ['跨境合作材料要引用制度依据', '境外供应商要看我们适用哪些规则'], ['把政策依据找全', '列一版可引用的规范'], ['data.compliance.security.cn', 'risk.security.cn'], 'data_or_risk_over_primary', '用户要政策依据。', {'service': 'cross_border'}),
        ('weather_outdoor_setup', 'weather.cn', ['周末要在室外搭展台，路线之后再说', '团建在户外，最担心会不会下雨'], ['先看天气窗口', '确认降雨和温度情况'], ['itinerary.travel.cn', 'activity.travel.cn'], 'travel_or_activity_over_primary', '用户要天气查询。', {'city': '杭州'}),
        ('budget_team_offsite', 'budget.finance.cn', ['部门外出两天，住宿交通活动都要花钱', '团队培训要先估个费用上限'], ['拆一版预算', '把费用盘子算一下'], ['hotel.travel.cn', 'transport.travel.cn'], 'travel_over_budget', '用户要预算拆分。', {'project': 'offsite'}),
        ('tax_service_income', 'tax.finance.cn', ['服务费到账后财务问税务口径', '补贴收入要入账，但税务处理没定'], ['看税务上怎么处理', '确认适用税务口径'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_or_compliance_over_primary', '用户要税务处理。', {'revenue_type': 'service_fee'}),
        ('coupon_camera_sale', 'coupon.commerce.cn', ['运动相机快下单了，先想看看有没有券', '投影仪价格差不多，主要看能不能叠优惠'], ['找优惠券或折扣', '看看有什么可用优惠'], ['price.commerce.cn', 'budget.finance.cn'], 'price_or_budget_over_primary', '用户要优惠券。', {'product': 'camera'}),
        ('docs_escalation_reply', 'docs.productivity.cn', ['客户投诉升级后，会议记录和风险点都很多', '售后复盘里讲了很多背景，客户只等一段回复'], ['写一版能发客户的回复', '整理成正式对外说明'], ['meeting.productivity.cn', 'risk.security.cn'], 'meeting_or_risk_over_primary', '会议/风险是素材，gold 是文档输出。', {'document': 'escalation_reply'}),
        ('docs_vendor_notice', 'docs.productivity.cn', ['供应商变更通知要写给各区域团队', '接口调整后要给合作伙伴一段统一口径'], ['把通知文字整理出来', '写一版统一说明'], ['policy.gov.cn', 'meeting.productivity.cn'], 'policy_or_meeting_over_primary', '用户要文档成稿。', {'document': 'notice'}),
        ('nutrition_overtime_light', 'nutrition.health.cn', ['连续加班后胃不舒服，运动先不谈', '晚饭总是外卖，想先把吃法稳住'], ['安排一版清淡吃法', '把晚餐怎么吃说清楚'], ['fitness.health.cn', 'clinic.health.cn'], 'fitness_or_clinic_over_primary', '用户要饮食调整。', {'goal': 'light_diet'}),
        ('nutrition_parent_trip', 'nutrition.health.cn', ['带老人出门几天，血糖和吃饭都要稳', '旅行途中吃饭不规律，怕控糖乱掉'], ['给一版外出饮食安排', '把路上怎么吃排一下'], ['clinic.health.cn', 'itinerary.travel.cn'], 'clinic_or_itinerary_over_primary', '用户要营养饮食。', {'goal': 'travel_diet'}),
        ('fitness_stairs_start', 'fitness.health.cn', ['楼梯爬几层就喘，检查又没大问题', '最近体力下降，想先恢复一点活动量'], ['排一个轻量起步计划', '安排每天怎么动起来'], ['clinic.health.cn', 'nutrition.health.cn'], 'clinic_or_nutrition_over_primary', '用户要运动起步计划。', {'goal': 'stamina'}),
        ('fitness_lunch_break', 'fitness.health.cn', ['中午只有二十分钟，想插一点运动', '办公室没器械，但想改善久坐'], ['给一套短时间运动安排', '排一个午休活动计划'], ['nutrition.health.cn', 'meeting.productivity.cn'], 'nutrition_or_meeting_over_primary', '用户要训练安排。', {'goal': 'office_fitness'}),
        ('invest_cash_buffer', 'invest.finance.cn', ['公司发了一笔项目奖金，暂时不想动', '家里备用钱太多躺在卡里'], ['想几个稳妥放置方向', '给一个保守配置办法'], ['tax.finance.cn', 'budget.finance.cn'], 'tax_or_budget_over_primary', '用户要投资配置。', {'horizon': 'six_months'}),
        ('invest_short_term_goal', 'invest.finance.cn', ['半年后可能要用钱，现在想先放稳', '装修款暂时不用，但不敢买太波动的'], ['给几个低波动选择', '安排稳妥一点的配置'], ['budget.finance.cn', 'tax.finance.cn'], 'budget_or_tax_over_primary', '用户要稳健配置。', {'horizon': 'six_months'}),
        ('permit_partner_dashboard', 'permit.gov.cn', ['合作方看板准备开放外部访问', '供应商数据页面要从内部转对外'], ['列上线前要办的手续', '把准入和备案动作排一下'], ['compliance.security.cn', 'policy.gov.cn'], 'compliance_or_policy_over_primary', '用户要许可/准入手续。', {'service': 'partner_dashboard'}),
        ('permit_external_training', 'permit.gov.cn', ['外部培训报名页准备公开', '合作单位要访问课程报名入口'], ['确认需要哪些上线手续', '列清准入和备案顺序'], ['policy.gov.cn', 'risk.security.cn'], 'policy_or_risk_over_primary', '用户要手续办理。', {'service': 'training_signup'}),
        ('restaurant_early_client', 'restaurant.travel.cn', ['客户早上到园区，中午要找个省事的地方', '评审会结束后大家只剩半小时吃饭'], ['筛一个方便餐厅', '找附近能快速吃饭的地方'], ['meeting.productivity.cn', 'coupon.commerce.cn'], 'meeting_or_coupon_over_primary', '用户要餐厅地点。', {'city': '苏州'}),
        ('restaurant_budget_lunch', 'restaurant.travel.cn', ['团队午餐人均有限，但主要先定去哪吃', '培训中午要找地方，价格别太离谱'], ['先找合适餐厅', '筛不超预算的吃饭地方'], ['budget.finance.cn', 'price.commerce.cn'], 'budget_or_price_over_primary', '用户要餐饮地点。', {'city': '上海'}),
        ('transport_rain_client', 'transport.travel.cn', ['下雨天客户要从酒店去工厂', '天气不好，还得从会场赶到车站'], ['安排过去方式', '看怎么接驳最稳'], ['weather.cn', 'hotel.travel.cn'], 'weather_or_hotel_over_primary', '用户要交通接驳。', {'city': '杭州'}),
        ('transport_multi_stop', 'transport.travel.cn', ['上午客户现场，下午要赶到展馆', '一天里要从园区转去两个会场'], ['把路线顺一下', '安排怎么走不绕路'], ['meeting.productivity.cn', 'itinerary.travel.cn'], 'meeting_or_itinerary_over_primary', '用户要交通路线。', {'city': '上海'}),
    ],
)

add_specs(
    PARENT_CHILD_SPECS,
    [
        ('data_compliance_supplier_log', 'data.compliance.security.cn', ['供应商要接收设备运行明细做联调', '外协团队要看生产日志排查问题'], ['先看数据提供前要补哪些检查', '把日志外发的留存要求过一遍'], ['compliance.security.cn', 'risk.security.cn', 'policy.gov.cn'], 'parent_fallback', '数据明细外发落在 data compliance segment。', {'industry': 'manufacturing'}),
        ('data_compliance_training_export', 'data.compliance.security.cn', ['培训平台要导出学员行为数据给合作方', '外部讲师要拿到学员完成记录'], ['确认数据导出前的检查项', '把数据共享边界列清楚'], ['compliance.security.cn', 'policy.gov.cn'], 'parent_fallback', '学员数据共享是 data compliance segment。', {'industry': 'education'}),
        ('account_compliance_temp_staff', 'account.compliance.security.cn', ['临时外包人员要进协作系统', '项目结束前要给顾问开短期账号'], ['先看账号开通和权限怎么控', '把实名和权限边界过一遍'], ['compliance.security.cn', 'risk.security.cn'], 'parent_fallback', '账号实名/权限是 account compliance segment。', {'industry': 'enterprise_service'}),
        ('account_compliance_customer_portal', 'account.compliance.security.cn', ['客户门户要给代理商分配子账号', '售后系统要开放给区域服务商'], ['确认账号权限和实名要求', '把外部账号管理动作列清'], ['compliance.security.cn', 'risk.security.cn'], 'parent_fallback', '外部账号管理落在 account compliance segment。', {'industry': 'enterprise_service'}),
        ('transaction_compliance_refund', 'transaction.compliance.security.cn', ['大额退款要退给供应商指定账户', '合作方要求改收款账户后再付款'], ['核付款对象和账户变更检查', '把交易对象核验做清楚'], ['compliance.security.cn', 'fraud.security.cn', 'invoice.finance.cn'], 'parent_fallback', '付款对象核验落在 transaction compliance segment。', {'industry': 'enterprise_service'}),
        ('transaction_compliance_advance', 'transaction.compliance.security.cn', ['新渠道商要先付一笔预付款', '展会承办方要求提前打保证金'], ['列付款前置核验项', '先把交易对象检查过一遍'], ['compliance.security.cn', 'risk.security.cn'], 'parent_fallback', '预付款对象核验是 transaction compliance segment。', {'industry': 'enterprise_service'}),
        ('invoice_issue_license_fee', 'issue.invoice.finance.cn', ['客户付了软件授权费，要求当天开电子票', '服务订阅续费后财务要补票'], ['确认开票字段和入口', '把这张票怎么开说明白'], ['invoice.finance.cn', 'tax.finance.cn'], 'parent_fallback', '开具发票是 issue invoice segment。', {'expense_type': 'license_fee'}),
        ('invoice_verify_event_vendor', 'verify.invoice.finance.cn', ['活动供应商交来一批场地票据', '会务公司给的票据需要先查真伪'], ['先把票据验真', '查这些票能不能用'], ['invoice.finance.cn', 'tax.finance.cn'], 'parent_fallback', '票据真伪查验是 verify invoice segment。', {'expense_type': 'event'}),
        ('invoice_reimburse_remote_work', 'reimburse.invoice.finance.cn', ['远程驻场同事报回来住宿和餐补票', '外地实施结束后提交了交通票据'], ['判断哪些能报销入账', '把报销边界列清楚'], ['invoice.finance.cn', 'tax.finance.cn'], 'parent_fallback', '报销入账是 reimburse invoice segment。', {'expense_type': 'travel'}),
        ('meeting_schedule_vendor_review', 'schedule.meeting.productivity.cn', ['供应商复盘要约三方一起开', '客户验收前要协调几个部门碰时间'], ['把参会人和时间约起来', '先敲定会议排期'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', '会议排期是 schedule meeting segment。', {'meeting_type': 'vendor_review'}),
        ('meeting_schedule_release_gate', 'schedule.meeting.productivity.cn', ['上线评审会还没找到共同时间', '版本冻结前需要约一次决策会'], ['安排会议时间和参会人', '把会约起来'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', '约会排期落在 schedule meeting segment。', {'meeting_type': 'release_gate'}),
        ('meeting_summary_client_sync', 'summary.meeting.productivity.cn', ['客户同步会录音已经有了', '需求澄清会刚结束，记录比较散'], ['整理会议纪要', '把结论写成纪要'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', '会议纪要落在 summary meeting segment。', {'meeting_type': 'client_sync'}),
        ('meeting_summary_incident', 'summary.meeting.productivity.cn', ['故障复盘会讲了很多原因和改进项', '线上事故沟通会刚结束'], ['先整理复盘纪要', '把会议结论归成纪要'], ['meeting.productivity.cn', 'risk.security.cn'], 'parent_fallback', '会议总结是 summary meeting segment。', {'meeting_type': 'incident'}),
        ('meeting_action_followup', 'action-items.meeting.productivity.cn', ['上线评审会上分了很多后续任务', '客户沟通会后 owner 和期限散在记录里'], ['抽出待办和负责人', '把行动项列清楚'], ['meeting.productivity.cn', 'docs.productivity.cn'], 'parent_fallback', 'owner/期限/待办是 action-items segment。', {'meeting_type': 'release'}),
        ('meeting_action_incident', 'action-items.meeting.productivity.cn', ['事故复盘后大家认领了不少整改项', '周会上提到的风险整改没有台账'], ['列行动项和 owner', '把后续待办整理出来'], ['meeting.productivity.cn', 'risk.security.cn'], 'parent_fallback', '整改待办落在 action-items segment。', {'meeting_type': 'incident'}),
        ('hotel_beijing_training', 'beijing.hotel.travel.cn', ['北京培训第二天一早开课', '北京客户现场附近要住一晚'], ['挑北京这边合适的酒店', '筛北京不折腾的住处'], ['hotel.travel.cn', 'transport.travel.cn'], 'parent_fallback', '明确北京住宿落在 beijing.hotel l3。', {'city': '北京'}),
        ('hotel_beijing_family', 'beijing.hotel.travel.cn', ['带家人去北京看展，晚上只住一晚', '北京亲子行需要找离展馆近的住处'], ['筛北京附近酒店', '找北京住得方便的地方'], ['hotel.travel.cn', 'itinerary.travel.cn'], 'parent_fallback', '北京住宿是 l3 segment 证据。', {'city': '北京'}),
        ('itinerary_xian_family', 'xian.itinerary.travel.cn', ['带父母去西安三天，腿脚不能太累', '西安亲子游三天还没排路线'], ['把西安行程排顺', '安排西安每天怎么走'], ['itinerary.travel.cn', 'activity.travel.cn'], 'parent_fallback', '明确西安行程规划落在 xian itinerary l3。', {'city': '西安'}),
        ('itinerary_xian_museum', 'xian.itinerary.travel.cn', ['西安博物馆和城墙都想去，但时间只有两天', '西安周末行程想少走回头路'], ['排西安两天路线', '把西安行程骨架列出来'], ['itinerary.travel.cn', 'transport.travel.cn'], 'parent_fallback', '明确西安行程规划是 l3 segment。', {'city': '西安'}),
    ],
)

add_specs(
    PRIMARY_SECONDARY_SPECS,
    [
        ('invoice_issue_tax', 'issue.invoice.finance.cn', ['服务费收款后客户催开票', '软件授权费到账了但票还没开'], ['先确认这张票怎么开', '把开票字段和入口列清'], ['tax.finance.cn', 'invoice.finance.cn'], 'secondary_steals_primary', '主标签应是开票，税务只是附带提醒。', {'expense_type': 'service_fee'}, ['tax.finance.cn'], ['税务口径顺手提醒']),
        ('invoice_verify_reimburse', 'verify.invoice.finance.cn', ['报销前手里有一批住宿票据', '活动票据要入账前还没查真伪'], ['先查票据真伪', '看看这些票能不能用'], ['reimburse.invoice.finance.cn', 'tax.finance.cn'], 'secondary_steals_primary', '先验真，再谈报销。', {'expense_type': 'travel'}, ['reimburse.invoice.finance.cn'], ['后面再看能不能报销']),
        ('meeting_schedule_docs', 'schedule.meeting.productivity.cn', ['客户评审材料还没写，但会先得约上', '上线说明可以后补，评审会时间没定'], ['先把会议时间敲定', '把参会人约起来'], ['docs.productivity.cn', 'meeting.productivity.cn'], 'secondary_steals_primary', '主请求是排会，不是写材料。', {'meeting_type': 'review'}, ['docs.productivity.cn'], ['材料提纲后面再补']),
        ('meeting_summary_actions', 'summary.meeting.productivity.cn', ['复盘会后既要纪要也有待办', '同步会结束后 owner 很多但老板先要纪要'], ['先整理会议纪要', '把会上的结论写出来'], ['action-items.meeting.productivity.cn', 'docs.productivity.cn'], 'secondary_steals_primary', '主请求是纪要，行动项是次要。', {'meeting_type': 'sync'}, ['action-items.meeting.productivity.cn'], ['待办简单带一下']),
        ('meeting_actions_summary', 'action-items.meeting.productivity.cn', ['纪要可以简短，但整改任务要落人', '复盘会记录很多，最急的是后续谁做'], ['先列行动项和 owner', '把待办和期限抽出来'], ['summary.meeting.productivity.cn', 'docs.productivity.cn'], 'secondary_steals_primary', '主请求是行动项，不是纪要。', {'meeting_type': 'incident'}, ['summary.meeting.productivity.cn'], ['纪要可以简单带一下']),
        ('hotel_transport', 'hotel.travel.cn', ['明天到上海开会，接驳也要看但先找住处', '去深圳培训，交通之后再说'], ['先筛合适酒店', '找一个住得方便的地方'], ['transport.travel.cn', 'itinerary.travel.cn'], 'secondary_steals_primary', '主请求是住宿，交通是次要。', {'city': '上海'}, ['transport.travel.cn'], ['交通路线顺手看一下']),
        ('transport_hotel', 'transport.travel.cn', ['酒店订好了但去会场路线还没看', '客户现场和住处之间要来回跑'], ['先安排接驳路线', '看怎么过去最省事'], ['hotel.travel.cn', 'meeting.productivity.cn'], 'secondary_steals_primary', '主请求是交通接驳。', {'city': '上海'}, ['hotel.travel.cn'], ['住处信息可以作为参考']),
        ('weather_activity', 'weather.cn', ['户外团建活动可以改，但先看会不会下雨', '周末露营地点还没定，先担心天气'], ['先确认天气窗口', '看看降雨和温度'], ['activity.travel.cn', 'itinerary.travel.cn'], 'secondary_steals_primary', '主请求是天气，不是活动安排。', {'city': '杭州'}, ['activity.travel.cn'], ['活动备选后面再排']),
        ('activity_weather', 'activity.travel.cn', ['周末天气可能不好，但孩子还是想出去玩', '下午有雨的可能，想找不受影响的去处'], ['先找几个可去的活动', '筛不折腾的玩点'], ['weather.cn', 'itinerary.travel.cn'], 'secondary_steals_primary', '主请求是活动推荐。', {'city': '杭州'}, ['weather.cn'], ['天气简单看一下']),
        ('price_budget', 'price.commerce.cn', ['设备预算有上限，但先看不同渠道报价', '采购要控成本，先确认价格差多少'], ['先比不同渠道价格', '把报价按同一口径比一下'], ['budget.finance.cn', 'coupon.commerce.cn'], 'secondary_steals_primary', '主请求是比价，预算是约束。', {'product': 'device'}, ['budget.finance.cn'], ['预算上限也记一下']),
        ('coupon_price', 'coupon.commerce.cn', ['价格差不多，主要看哪里能叠券', '下单前想先找优惠，再看最终价格'], ['先找优惠券或折扣', '看看可用优惠入口'], ['price.commerce.cn', 'budget.finance.cn'], 'secondary_steals_primary', '主请求是优惠券。', {'product': 'projector'}, ['price.commerce.cn'], ['价格参考可以带一下']),
        ('invest_tax', 'invest.finance.cn', ['闲钱要配置，税务提醒可以后面看', '一年内不用的钱想稳妥放着'], ['先给配置方向', '想几个稳健放钱方案'], ['tax.finance.cn', 'budget.finance.cn'], 'secondary_steals_primary', '主请求是投资配置。', {'horizon': 'one_year'}, ['tax.finance.cn'], ['税务影响简单提醒']),
        ('tax_policy', 'tax.finance.cn', ['补贴收入涉及政策，但财务先问税怎么处理', '服务费入账要有依据，但先看税务口径'], ['先确认税务处理', '看适用税务口径'], ['policy.gov.cn', 'compliance.security.cn'], 'secondary_steals_primary', '主请求是税务处理。', {'revenue_type': 'subsidy'}, ['policy.gov.cn'], ['政策依据可以列后面']),
        ('compliance_policy', 'compliance.security.cn', ['材料要外发，政策依据可以查但先做检查', '合作方要接系统，规范后面再引用'], ['先列合规检查项', '把审计留痕要求过一遍'], ['policy.gov.cn', 'risk.security.cn'], 'secondary_steals_primary', '主请求是合规检查。', {'industry': 'enterprise_service'}, ['policy.gov.cn'], ['依据可以简单带一下']),
        ('fraud_risk', 'fraud.security.cn', ['优惠活动风险不少，但最怕有人套利', '返利订单整体有风险，先看作弊拦截'], ['先列异常识别规则', '把可疑套利信号排出来'], ['risk.security.cn', 'compliance.security.cn'], 'secondary_steals_primary', '主请求是反欺诈。', {'campaign': 'rebate'}, ['risk.security.cn'], ['整体风险顺手提醒']),
        ('risk_compliance', 'risk.security.cn', ['外部入口要开，合规会问但先排风险', '供应商端口上线前审计会看'], ['先排主要风险点', '把容易出事的地方列出来'], ['compliance.security.cn', 'policy.gov.cn'], 'secondary_steals_primary', '主请求是风险评估。', {'service': 'portal'}, ['compliance.security.cn'], ['合规检查后面再做']),
        ('clinic_nutrition', 'clinic.health.cn', ['饮食可以后面改，先想知道该约什么检查', '控糖前先确认门诊怎么走'], ['先看门诊或检查入口', '把基础检查怎么约说清'], ['nutrition.health.cn', 'fitness.health.cn'], 'secondary_steals_primary', '主请求是门诊/检查。', {'goal': 'checkup'}, ['nutrition.health.cn'], ['饮食建议简单提醒']),
        ('fitness_clinic', 'fitness.health.cn', ['检查结果没大问题，先恢复运动', '门诊之后医生说可以轻量活动'], ['先排起步训练计划', '安排每天怎么动'], ['clinic.health.cn', 'nutrition.health.cn'], 'secondary_steals_primary', '主请求是运动计划。', {'goal': 'recovery'}, ['clinic.health.cn'], ['检查注意事项简单带一下']),
        ('tutoring_course', 'tutoring.education.cn', ['课程看过了还是卡，想找人带着问', 'SQL 课学不下去，需要有人答疑'], ['先找合适辅导方式', '帮我找能答疑的导师'], ['course.education.cn', 'meeting.productivity.cn'], 'secondary_steals_primary', '主请求是辅导。', {'goal': 'sql'}, ['course.education.cn'], ['课程资料可以参考']),
        ('flight_transport', 'flight.travel.cn', ['去成都客户现场，落地后接驳也要看', '杭州出差要先定去回程'], ['先筛合适航班', '把出发返回航班挑出来'], ['transport.travel.cn', 'weather.cn'], 'secondary_steals_primary', '主请求是航班。', {'city': '成都'}, ['transport.travel.cn'], ['落地交通顺手看一下']),
        ('itinerary_flight', 'itinerary.travel.cn', ['机票之后再定，先把三天路线排顺', '去云南交通不急，先看每天怎么玩'], ['先排行程骨架', '把每天安排排出来'], ['flight.travel.cn', 'hotel.travel.cn'], 'secondary_steals_primary', '主请求是行程规划。', {'city': '云南'}, ['flight.travel.cn'], ['航班后面再看']),
    ],
)

add_specs(
    CROSS_DOMAIN_SPECS,
    [
        ('travel_flight_hotel_primary_itinerary', 'itinerary.travel.cn', ['去成都开会顺便玩两天，机票酒店都还没定', '青岛三天行程、航班和住处都悬着'], ['先把每天路线排出来', '把行程骨架搭好'], ['flight.travel.cn', 'hotel.travel.cn'], 'cross_domain_over_primary', '航班/住宿共现，但主请求是行程规划。', {'city': '成都'}, ['flight.travel.cn', 'hotel.travel.cn'], ['机票和酒店后面也带上']),
        ('travel_weather_primary_activity', 'activity.travel.cn', ['杭州周末可能下雨，但孩子想找地方玩', '下午天气不稳，还是想安排点室内活动'], ['先筛几个活动', '找不受天气影响的玩点'], ['weather.cn', 'itinerary.travel.cn'], 'cross_domain_over_primary', '天气共现，但主请求是活动推荐。', {'city': '杭州'}, ['weather.cn'], ['天气窗口也看一下']),
        ('hotel_transport_meeting', 'hotel.travel.cn', ['深圳评审会时间定了，住处和接驳都要看', '北京客户会前一晚要住下，交通也要顺'], ['先找合适酒店', '筛住得方便的地方'], ['transport.travel.cn', 'meeting.productivity.cn'], 'cross_domain_over_primary', '交通/会议共现，但主请求是住宿。', {'city': '深圳'}, ['transport.travel.cn'], ['接驳路线后面带一下']),
        ('transport_weather_meeting', 'transport.travel.cn', ['暴雨天要从机场赶到会场', '天气不好还要去客户现场开会'], ['先安排过去方式', '把接驳路线看稳'], ['weather.cn', 'meeting.productivity.cn'], 'cross_domain_over_primary', '天气/会议共现，但主请求是交通。', {'city': '广州'}, ['weather.cn', 'meeting.productivity.cn'], ['天气和会议时间也考虑']),
        ('finance_budget_invoice_tax', 'budget.finance.cn', ['外包项目要控成本，票据和税也会牵出来', '培训活动预算、发票和税务都要考虑'], ['先拆预算上限', '把费用盘子列清'], ['invoice.finance.cn', 'tax.finance.cn'], 'cross_domain_over_primary', '票据/税务共现，但主请求是预算。', {'project': 'outsourcing'}, ['invoice.finance.cn', 'tax.finance.cn'], ['发票和税务顺手提醒']),
        ('finance_invest_tax_budget', 'invest.finance.cn', ['奖金要配置，税和家庭预算也要考虑', '闲钱想放稳一点，后面还要算支出'], ['先给配置方向', '想几个稳健放钱方案'], ['tax.finance.cn', 'budget.finance.cn'], 'cross_domain_over_primary', '税务/预算共现，但主请求是投资配置。', {'horizon': 'one_year'}, ['tax.finance.cn', 'budget.finance.cn'], ['税和预算简单带一下']),
        ('invoice_reimburse_tax_compliance', 'reimburse.invoice.finance.cn', ['报销票据、税务口径和审计要求都在问', '活动费用要入账，合规和税务都敏感'], ['先判断哪些能报销', '把报销边界列清'], ['tax.finance.cn', 'compliance.security.cn'], 'cross_domain_over_primary', '税务/合规共现，但主请求是报销。', {'expense_type': 'event'}, ['tax.finance.cn', 'compliance.security.cn'], ['税务和审计也提醒']),
        ('docs_policy_compliance_meeting', 'docs.productivity.cn', ['评审会材料要带政策依据和合规点', '对外说明要同时回应规范和风险'], ['先把材料主干写出来', '整理一版对外说明'], ['policy.gov.cn', 'compliance.security.cn', 'meeting.productivity.cn'], 'cross_domain_over_primary', '政策/合规/会议共现，但主请求是文档。', {'document': 'review_note'}, ['policy.gov.cn', 'compliance.security.cn'], ['依据和合规点也带上']),
        ('meeting_schedule_docs_risk', 'schedule.meeting.productivity.cn', ['风险评审要开，材料和风险点也要准备', '上线会要约起来，同时要带说明材料'], ['先把会议时间约起来', '敲定参会人和时间'], ['docs.productivity.cn', 'risk.security.cn'], 'cross_domain_over_primary', '文档/风险共现，但主请求是排会。', {'meeting_type': 'risk_review'}, ['docs.productivity.cn', 'risk.security.cn'], ['材料和风险点后面准备']),
        ('meeting_action_compliance_docs', 'action-items.meeting.productivity.cn', ['合规复盘会后既有纪要也有整改项', '审计会结束后材料很多，但最急是任务落人'], ['先抽行动项和 owner', '把后续待办列清'], ['summary.meeting.productivity.cn', 'docs.productivity.cn', 'compliance.security.cn'], 'cross_domain_over_primary', '纪要/文档/合规共现，但主请求是行动项。', {'meeting_type': 'audit'}, ['summary.meeting.productivity.cn', 'docs.productivity.cn'], ['纪要和材料简单带一下']),
        ('commerce_price_coupon_budget', 'price.commerce.cn', ['采购预算有限，优惠券也想看，但先比报价', '会议设备要下单，价格、券和预算都要考虑'], ['先比不同渠道价格', '把报价按同口径比较'], ['coupon.commerce.cn', 'budget.finance.cn'], 'cross_domain_over_primary', '优惠/预算共现，但主请求是比价。', {'product': 'meeting_device'}, ['coupon.commerce.cn', 'budget.finance.cn'], ['优惠和预算也提醒']),
        ('commerce_coupon_restaurant_price', 'coupon.commerce.cn', ['团建餐厅定了，主要想看有没有团购券', '客户招待要控人均，先找可用优惠'], ['先找优惠券或折扣', '看看可叠优惠入口'], ['restaurant.travel.cn', 'price.commerce.cn'], 'cross_domain_over_primary', '餐厅/价格共现，但主请求是优惠。', {'event': 'lunch'}, ['restaurant.travel.cn', 'price.commerce.cn'], ['餐厅和价格也参考']),
        ('health_clinic_nutrition_fitness', 'clinic.health.cn', ['控糖、吃饭和运动都要改，但先想约检查', '恢复训练前饮食也要注意，先看门诊怎么走'], ['先看门诊或检查入口', '把基础检查怎么约说清'], ['nutrition.health.cn', 'fitness.health.cn'], 'cross_domain_over_primary', '营养/训练共现，但主请求是门诊。', {'goal': 'checkup'}, ['nutrition.health.cn', 'fitness.health.cn'], ['饮食和运动后面再安排']),
        ('health_fitness_nutrition_clinic', 'fitness.health.cn', ['体检没大问题，饮食也会调，但先想动起来', '医生说可以活动了，吃法后面再看'], ['先排起步训练计划', '安排每天怎么动'], ['nutrition.health.cn', 'clinic.health.cn'], 'cross_domain_over_primary', '营养/门诊共现，但主请求是训练。', {'goal': 'recovery'}, ['nutrition.health.cn', 'clinic.health.cn'], ['饮食和检查提醒也带上']),
        ('education_course_docs_meeting', 'course.education.cn', ['新人培训要有材料和答疑会，但先定课程', '采购流程培训既要说明也要排会'], ['先给学习路径', '推荐能开始的课程'], ['docs.productivity.cn', 'meeting.productivity.cn'], 'cross_domain_over_primary', '文档/会议共现，但主请求是课程。', {'training': 'new_hire'}, ['docs.productivity.cn', 'meeting.productivity.cn'], ['材料和答疑会后面带上']),
        ('education_tutoring_course_meeting', 'tutoring.education.cn', ['SQL 课看了还是不会，想找人答疑', '学习路径有了，但需要有人带着做题'], ['先找辅导方式', '帮我找能答疑的导师'], ['course.education.cn', 'meeting.productivity.cn'], 'cross_domain_over_primary', '课程/会议共现，但主请求是辅导。', {'goal': 'sql'}, ['course.education.cn', 'meeting.productivity.cn'], ['课程和约时间也参考']),
        ('governance_policy_permit_risk', 'policy.gov.cn', ['对外接口上线会涉及手续和风险，但先找依据', '数据下载开放前，备案和风控都要问'], ['先查适用规范', '把政策依据列出来'], ['permit.gov.cn', 'risk.security.cn'], 'cross_domain_over_primary', '许可/风险共现，但主请求是政策依据。', {'service': 'data_api'}, ['permit.gov.cn', 'risk.security.cn'], ['手续和风险后面再看']),
        ('governance_risk_compliance_policy', 'risk.security.cn', ['供应商入口上线，合规和政策都会被问', '外部报修入口要开，政策依据也要准备'], ['先排主要风险点', '把容易出事的地方列出来'], ['compliance.security.cn', 'policy.gov.cn'], 'cross_domain_over_primary', '合规/政策共现，但主请求是风险。', {'service': 'portal'}, ['compliance.security.cn', 'policy.gov.cn'], ['合规和政策也提示']),
        ('governance_compliance_data_policy', 'data.compliance.security.cn', ['数据看板要给外部供应商，政策和风险都要考虑', '海外协作方要看设备日志，合规和依据都敏感'], ['先看数据外发检查项', '把数据共享边界列清'], ['policy.gov.cn', 'risk.security.cn', 'compliance.security.cn'], 'cross_domain_over_primary', '政策/风险共现，但主请求是数据合规 segment。', {'industry': 'manufacturing'}, ['policy.gov.cn', 'risk.security.cn'], ['依据和风险也带上']),
        ('security_fraud_risk_compliance', 'fraud.security.cn', ['优惠活动怕作弊，风险和合规也要看', '返利订单异常，审计会问整体风险'], ['先列异常识别规则', '把套利信号和拦截点列出'], ['risk.security.cn', 'compliance.security.cn'], 'cross_domain_over_primary', '风险/合规共现，但主请求是反欺诈。', {'campaign': 'rebate'}, ['risk.security.cn', 'compliance.security.cn'], ['风险和合规简单带上']),
        ('weather_transport_hotel', 'weather.cn', ['周末去杭州，交通和酒店还没定，但先看天气', '露营路线和住处之后再说，先怕下雨'], ['先确认天气窗口', '看看降雨和温度'], ['transport.travel.cn', 'hotel.travel.cn'], 'cross_domain_over_primary', '交通/住宿共现，但主请求是天气。', {'city': '杭州'}, ['transport.travel.cn', 'hotel.travel.cn'], ['交通和住宿后面再排']),
    ],
)

add_specs(
    HIGH_RISK_SPECS,
    [
        ('permit_sms_vendor_risk', 'permit.gov.cn', ['短信通道要给外部供应商试用', '身份核验接口准备开放给合作方'], ['先列准入和备案手续', '把前置资质动作列清'], ['risk.security.cn', 'compliance.security.cn', 'policy.gov.cn'], 'generic_governance_over_primary', '高风险语气下主请求仍是许可/准入。', {'service': 'sms'}),
        ('permit_health_portal', 'permit.gov.cn', ['健康预约入口准备公开，审计也会盯', '在线问诊预约页要对外开放'], ['先确认上线前手续', '列清备案和准入顺序'], ['policy.gov.cn', 'compliance.security.cn'], 'generic_governance_over_primary', '主请求是许可备案。', {'service': 'health_portal'}),
        ('policy_ai_compliance', 'policy.gov.cn', ['AI 客服对外开放前大家担心合规', '智能助手上线前领导先问规则依据'], ['先查适用规范', '把政策依据找全'], ['compliance.security.cn', 'risk.security.cn', 'permit.gov.cn'], 'generic_governance_over_primary', '治理口吻不能盖过政策检索。', {'service': 'ai_assistant'}),
        ('policy_payment_risk', 'policy.gov.cn', ['外部支付说明要引用监管依据', '供应商结算流程变更前要找制度依据'], ['先找政策依据', '列适用规范和标准'], ['risk.security.cn', 'transaction.compliance.security.cn'], 'generic_governance_over_primary', '主请求是政策依据。', {'service': 'payment'}),
        ('compliance_data_export', 'data.compliance.security.cn', ['设备日志给海外供应商前审计会追责', '用户行为数据要同步第三方系统'], ['先列数据外发检查项', '把数据共享留痕要求过一遍'], ['risk.security.cn', 'policy.gov.cn'], 'risk_or_policy_over_primary', '主请求是数据合规 segment。', {'industry': 'manufacturing'}),
        ('compliance_account_vendor', 'account.compliance.security.cn', ['外包团队要进系统，权限错了责任很大', '代理商子账号开放前审计会看'], ['先核账号实名和权限', '把外部账号检查项列清'], ['risk.security.cn', 'policy.gov.cn'], 'risk_or_policy_over_primary', '主请求是账号合规 segment。', {'industry': 'enterprise_service'}),
        ('compliance_transaction_payment', 'transaction.compliance.security.cn', ['供应商首付款打错对象会很麻烦', '合作方临时改收款账户，审计会问'], ['先核交易对象和账户变更', '把付款前置检查列清'], ['risk.security.cn', 'fraud.security.cn'], 'risk_or_fraud_over_primary', '主请求是交易对象合规。', {'industry': 'enterprise_service'}),
        ('risk_external_download', 'risk.security.cn', ['外部下载入口一开就可能被滥用', '客户自助导出准备上线，大家担心风险'], ['先排主要风险点', '列容易出事的环节'], ['compliance.security.cn', 'policy.gov.cn'], 'compliance_or_policy_over_primary', '主请求是风险评估。', {'service': 'download'}),
        ('risk_model_output', 'risk.security.cn', ['AI 回复要直接给客户看，出错影响很大', '自动推荐结果准备上线，风控会追'], ['先排输出风险点', '把容易误导的地方列出来'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_or_compliance_over_primary', '主请求是风险识别。', {'service': 'ai_output'}),
        ('fraud_coupon_batch', 'fraud.security.cn', ['优惠券批量领取看起来异常', '新客补贴活动怕被脚本刷'], ['先列作弊识别规则', '把异常拦截点排出来'], ['risk.security.cn', 'compliance.security.cn'], 'risk_over_fraud', '套利/刷补贴是反欺诈。', {'campaign': 'coupon'}),
        ('fraud_refund_abuse', 'fraud.security.cn', ['退款申请里有人反复钻规则', '售后补贴可能被同一批账号套取'], ['先列异常识别和拦截规则', '把可疑退款信号排出来'], ['risk.security.cn', 'transaction.compliance.security.cn'], 'risk_over_fraud', '异常套利是 fraud。', {'campaign': 'refund'}),
        ('invoice_issue_audit', 'issue.invoice.finance.cn', ['开错票会影响审计和税务', '客户催票但字段不对后面会被追责'], ['先确认开票字段和入口', '把这张票怎么开说清'], ['tax.finance.cn', 'compliance.security.cn'], 'tax_or_compliance_over_primary', '主请求是开票。', {'expense_type': 'service'}),
        ('invoice_verify_audit', 'verify.invoice.finance.cn', ['票据真伪没查就入账风险很大', '供应商票据要报销前审计会看'], ['先查票据真伪', '确认这些票能不能用'], ['tax.finance.cn', 'compliance.security.cn'], 'tax_or_compliance_over_primary', '主请求是验真。', {'expense_type': 'vendor'}),
        ('tax_subsidy_risk', 'tax.finance.cn', ['补贴收入税务口径错了会被追', '服务费入账涉及监管和合规'], ['先确认税务处理', '把适用税务口径列清'], ['policy.gov.cn', 'compliance.security.cn'], 'policy_or_compliance_over_primary', '主请求是税务。', {'revenue_type': 'subsidy'}),
        ('tax_cross_region', 'tax.finance.cn', ['跨地区服务费结算，税务处理不敢随便定', '异地培训收入入账前财务要口径'], ['先看税务怎么处理', '确认适用税务口径'], ['policy.gov.cn', 'risk.security.cn'], 'policy_or_risk_over_primary', '主请求是税务处理。', {'revenue_type': 'training'}),
        ('transaction_vendor_bank', 'transaction.compliance.security.cn', ['供应商要求换银行卡再付款', '承办方临时改收款主体'], ['先核付款对象和账户变更', '把交易对象检查清楚'], ['risk.security.cn', 'fraud.security.cn'], 'risk_or_fraud_over_primary', '主请求是交易核验。', {'industry': 'enterprise_service'}),
        ('transaction_refund_target', 'transaction.compliance.security.cn', ['大额退款要退到新账户', '客户要求把退款打给关联公司'], ['先核退款对象', '列退款前置检查项'], ['risk.security.cn', 'invoice.finance.cn'], 'risk_or_invoice_over_primary', '主请求是交易对象核验。', {'industry': 'enterprise_service'}),
        ('data_policy_highrisk', 'policy.gov.cn', ['数据接口对外开放，合规和风险都很敏感', '客户下载范围扩大前领导要先看依据'], ['先找适用政策依据', '把规范标准列出来'], ['data.compliance.security.cn', 'risk.security.cn'], 'data_or_risk_over_primary', '主请求是政策依据。', {'service': 'data_api'}),
        ('compliance_archive_highrisk', 'compliance.security.cn', ['项目归档材料要给第三方查阅', '审计材料外发前怕留痕不够'], ['先列合规检查项', '把审计留痕要求过一遍'], ['risk.security.cn', 'policy.gov.cn'], 'risk_or_policy_over_primary', '主请求是合规检查。', {'industry': 'enterprise_service'}),
    ],
)

add_specs(
    NEAR_DUPLICATE_SPECS,
    [
        ('invoice_issue_vs_verify', 'issue.invoice.finance.cn', ['客户付了服务费，还没开票', '软件授权费到账后要补电子票'], ['先确认这张票怎么开', '把开票字段列清'], ['verify.invoice.finance.cn', 'tax.finance.cn'], 'near_duplicate_confusion', '开票不是票据验真。', {'expense_type': 'service_fee'}),
        ('invoice_verify_vs_issue', 'verify.invoice.finance.cn', ['供应商给的票据看着不太对', '活动发票入账前想先查真假'], ['先查票据真伪', '看看这些票能不能用'], ['issue.invoice.finance.cn', 'tax.finance.cn'], 'near_duplicate_confusion', '验真不是开新票。', {'expense_type': 'vendor'}),
        ('invoice_reimburse_vs_verify', 'reimburse.invoice.finance.cn', ['票据已经查过真伪，现在要看能不能报', '住宿票都是真的，但报销规则还没判'], ['先判断能不能报销', '把报销边界列清'], ['verify.invoice.finance.cn', 'tax.finance.cn'], 'near_duplicate_confusion', '报销判断不是验真。', {'expense_type': 'travel'}),
        ('schedule_vs_summary', 'schedule.meeting.productivity.cn', ['纪要之后再写，先把复盘会约起来', '材料不急，评审会时间还没定'], ['先排会议时间和参会人', '把会议约起来'], ['summary.meeting.productivity.cn', 'docs.productivity.cn'], 'near_duplicate_confusion', '排会不是写纪要。', {'meeting_type': 'review'}),
        ('summary_vs_actions', 'summary.meeting.productivity.cn', ['待办可以后面拆，老板先要会议纪要', 'owner 很多但现在先要一版复盘结论'], ['先整理会议纪要', '把会上结论写出来'], ['action-items.meeting.productivity.cn', 'docs.productivity.cn'], 'near_duplicate_confusion', '纪要不是行动项。', {'meeting_type': 'sync'}),
        ('actions_vs_schedule', 'action-items.meeting.productivity.cn', ['会已经开完了，不是再约时间', '复盘结束后要看谁负责后续'], ['先列行动项和 owner', '把后续待办抽出来'], ['schedule.meeting.productivity.cn', 'summary.meeting.productivity.cn'], 'near_duplicate_confusion', '行动项不是排会。', {'meeting_type': 'incident'}),
        ('hotel_vs_itinerary', 'hotel.travel.cn', ['路线可以后面排，今晚先找住处', '旅游计划没定，但先要定酒店'], ['先筛合适酒店', '找住得方便的地方'], ['itinerary.travel.cn', 'transport.travel.cn'], 'near_duplicate_confusion', '住宿不是完整行程。', {'city': '上海'}),
        ('flight_vs_transport', 'flight.travel.cn', ['机场到会场后面再看，先定去程航班', '接驳不急，先挑出发和返回时间'], ['先筛合适航班', '把航班挑出来'], ['transport.travel.cn', 'itinerary.travel.cn'], 'near_duplicate_confusion', '航班不是地面交通。', {'city': '深圳'}),
        ('transport_vs_flight', 'transport.travel.cn', ['机票已经定了，现在看机场怎么去酒店', '航班不用改，落地后路线没看'], ['先安排接驳路线', '看怎么过去最省事'], ['flight.travel.cn', 'hotel.travel.cn'], 'near_duplicate_confusion', '接驳交通不是航班。', {'city': '杭州'}),
        ('activity_vs_itinerary', 'activity.travel.cn', ['完整路线不用重排，只剩下午空档', '行程大致定了，想加一个轻松项目'], ['先找几个活动', '筛个能塞进去的玩点'], ['itinerary.travel.cn', 'restaurant.travel.cn'], 'near_duplicate_confusion', '活动推荐不是完整行程。', {'city': '南京'}),
        ('budget_vs_invest', 'budget.finance.cn', ['不是要理财，是项目费用先压住', '闲钱配置不谈，先看活动成本盘子'], ['先拆预算和费用上限', '把成本盘子列清'], ['invest.finance.cn', 'price.commerce.cn'], 'near_duplicate_confusion', '预算拆分不是投资配置。', {'project': 'event'}),
        ('compliance_vs_risk', 'compliance.security.cn', ['风险点可以后面排，先看审计检查项', '外发材料前不是做风险报告，先看合规留痕'], ['先列合规检查项', '把审计留痕要求过一遍'], ['risk.security.cn', 'policy.gov.cn'], 'near_duplicate_confusion', '合规检查不是风险评估。', {'industry': 'enterprise_service'}),
        ('risk_vs_compliance', 'risk.security.cn', ['合规条款后面查，先看哪里容易出事', '审计要求不急，先排上线风险'], ['先排主要风险点', '把容易出事的地方列出来'], ['compliance.security.cn', 'policy.gov.cn'], 'near_duplicate_confusion', '风险评估不是合规检查。', {'service': 'portal'}),
    ],
)


SLICE_SPECS = {
    'parent_child_granularity': PARENT_CHILD_SPECS,
    'primary_secondary_conflict': PRIMARY_SECONDARY_SPECS,
    'cross_domain_overlap': CROSS_DOMAIN_SPECS,
    'high_risk_governance_tone': HIGH_RISK_SPECS,
    'near_duplicate_descriptors': NEAR_DUPLICATE_SPECS,
}


def render_query(stress_slice: str, spec_row: dict[str, Any], occurrence: int, surface_style: str) -> str:
    scene = scene_text(pick(spec_row['scenes'], occurrence), occurrence)
    primary = pick(spec_row['primaries'], occurrence, 1)
    primary_first = first_action(primary)
    primary_plain = plain_action(primary)
    secondary = pick(spec_row['secondary_texts'], occurrence, 2) if spec_row['secondary_texts'] else ''

    if stress_slice == 'low_rank_gold':
        hint = competing_hint(spec_row, occurrence)
        return render_from_templates(
            [
                '{scene}，{hint}这些可以后面再说，{primary_first}。',
                '{scene}，别先绕到{hint}，我现在要{primary_plain}。',
                '{scene}。如果提到{hint}也只是背景，麻烦先{primary_plain}。',
                '{scene}，{hint}可以顺手记着，但{primary_first}。',
                '{scene}，我不是要马上处理{hint}，{primary_first}。',
                '{scene}，先不展开{hint}，我想先{primary_plain}。',
            ],
            occurrence,
            scene=scene,
            hint=hint,
            primary_first=primary_first,
            primary_plain=primary_plain,
        )
    if stress_slice == 'parent_child_granularity':
        return render_from_templates(
            [
                '{scene}，别只给泛泛提醒，{primary_first}。',
                '{scene}，这次要落到具体步骤，麻烦{primary_first}。',
                '{scene}，大方向我知道，{primary_first}。',
                '{scene}，我需要的是这一步：{primary_plain}。',
                '{scene}，先别只说注意事项，{primary_first}。',
                '{scene}，能不能直接{primary_plain}。',
            ],
            occurrence,
            scene=scene,
            primary_first=primary_first,
            primary_plain=primary_plain,
        )
    if stress_slice == 'primary_secondary_conflict':
        return render_from_templates(
            [
                '{scene}，{primary_first}，{secondary}。',
                '{scene}。{secondary}，但{primary_first}。',
                '{scene}，我主要想{primary_plain}，{secondary}。',
                '{scene}，先把这件事处理掉：{primary_plain}；{secondary}。',
                '{scene}，{secondary}可以带一下，先{primary_plain}。',
                '{scene}，别先展开旁支，先{primary_plain}，{secondary}。',
            ],
            occurrence,
            scene=scene,
            primary_first=primary_first,
            primary_plain=primary_plain,
            secondary=secondary,
        )
    if stress_slice == 'cross_domain_overlap':
        return render_from_templates(
            [
                '{scene}，{secondary}，但{primary_first}。',
                '{scene}。{secondary}，但{primary_first}。',
                '{scene}，其他先放后，先{primary_plain}，{secondary}。',
                '{scene}，我知道还会牵到别的事，{primary_first}，{secondary}。',
                '{scene}，先从这件事开始：{primary_plain}；{secondary}。',
                '{scene}，顺带的事项可以后面细化，{primary_first}，{secondary}。',
            ],
            occurrence,
            scene=scene,
            primary_first=primary_first,
            primary_plain=primary_plain,
            secondary=secondary,
        )
    if stress_slice == 'high_risk_governance_tone':
        return render_from_templates(
            [
                '{scene}，审计和合规后面肯定会问，{primary_first}。',
                '{scene}，这块先记着，麻烦{primary_first}。',
                '{scene}，先不写一大套原则，先把这件事说清楚：{primary_plain}。',
                '{scene}，监管和审计要点可以带一句，先{primary_plain}。',
                '{scene}，现在别先做长篇风险报告，{primary_first}。',
                '{scene}，我先要一个能过会讨论的说法：{primary_plain}。',
            ],
            occurrence,
            scene=scene,
            primary_first=primary_first,
            primary_plain=primary_plain,
        )
    return render_from_templates(
        [
            '{scene}，别给泛泛建议，{primary_first}。',
            '{scene}，我说的是{primary_plain}，不是旁边那些事。',
            '{scene}，不要转成别的处理，{primary_first}。',
            '{scene}，这一步先按字面需求来：{primary_plain}。',
            '{scene}，先别扩展，{primary_first}。',
            '{scene}，我只想先{primary_plain}。',
        ],
        occurrence,
        scene=scene,
        primary_first=primary_first,
        primary_plain=primary_plain,
    )


def build_candidate(stress_slice: str, spec_row: dict[str, Any], occurrence: int) -> dict[str, Any]:
    surface_style = pick(SURFACE_STYLES, occurrence)
    query = render_query(stress_slice, spec_row, occurrence, surface_style)
    tail = pick(HUMAN_TAILS, occurrence + stable_index(spec_row['slug']))
    query = f'{query.rstrip("。")}；{tail}。'
    relevant = list(spec_row['relevant'])
    return {
        'stress_slice': stress_slice,
        'slug': spec_row['slug'],
        'gt': spec_row['gt'],
        'query': query,
        'context': dict(spec_row['context']),
        'relevant': relevant,
        'competing': list(dict.fromkeys(spec_row['competitors'] + relevant)),
        'failure': spec_row['failure'],
        'note': spec_row['note'],
        'surface_style': surface_style,
        'variant_index': occurrence,
    }


def expand_slice(stress_slice: str, specs: list[dict[str, Any]], target: int, max_per_case: int = MAX_QUERY_VARIANTS_PER_CASE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    occurrence_by_slug: Counter[str] = Counter()
    for spec_row in specs:
        for _ in range(max_per_case):
            if len(rows) >= target:
                return rows
            occurrence_by_slug[spec_row['slug']] += 1
            rows.append(build_candidate(stress_slice, spec_row, occurrence_by_slug[spec_row['slug']]))
    if len(rows) < target:
        raise ValueError(
            f'{stress_slice} has only {len(specs)} base hard cases; '
            f'cap={max_per_case} yields {len(rows)} samples, below target={target}'
        )
    return rows


def rank_probe(resolver: NamespaceResolver, candidate: dict[str, Any], sample_id: str) -> dict[str, Any]:
    snapshot = build_candidate_snapshot(
        sample={
            'id': sample_id,
            'namespace_version': NAMESPACE_VERSION,
            'query': candidate['query'],
            'context': candidate['context'],
            'ground_truth_fqdn': candidate['gt'],
        },
        resolver=resolver,
        top_k=RANK_PROBE_TOP_K,
        stage_r_version=STAGE_R_VERSION,
    )
    fqdns = [row['fqdn'] for row in snapshot['fqdn_candidates']]
    gold_rank = fqdns.index(candidate['gt']) + 1 if candidate['gt'] in fqdns else None
    return {
        'stage_r_version': STAGE_R_VERSION,
        'top_k': RANK_PROBE_TOP_K,
        'gold_rank': gold_rank,
        'gold_in_top_k': gold_rank is not None,
        'head_fqdn': fqdns[0] if fqdns else '',
    }


def build_low_rank_rows(resolver: NamespaceResolver) -> list[dict[str, Any]]:
    pool = expand_slice('low_rank_gold', LOW_RANK_SPECS, len(LOW_RANK_SPECS) * MAX_QUERY_VARIANTS_PER_CASE)
    scored: list[tuple[int, dict[str, Any]]] = []
    for idx, candidate in enumerate(pool, start=1):
        probe = rank_probe(resolver, candidate, f'low_rank_probe_{idx:06d}')
        candidate['candidate_rank_probe'] = probe
        rank = probe['gold_rank']
        rank_key = 999 if rank is None else rank
        scored.append((rank_key, candidate))
    scored = [
        (rank_key, candidate)
        for rank_key, candidate in scored
        if candidate['candidate_rank_probe']['gold_rank'] is None or candidate['candidate_rank_probe']['gold_rank'] >= 4
    ]
    if len(scored) < SLICE_TARGETS['low_rank_gold']:
        raise ValueError(f'Only {len(scored)} low-rank eligible candidates available')
    scored.sort(key=lambda item: (item[0], item[1]['gt']), reverse=True)
    selected: list[dict[str, Any]] = []
    per_gt_count: Counter[str] = Counter()
    per_gt_cap = 8
    for _, candidate in scored:
        if per_gt_count[candidate['gt']] >= per_gt_cap:
            continue
        selected.append(candidate)
        per_gt_count[candidate['gt']] += 1
        if len(selected) == SLICE_TARGETS['low_rank_gold']:
            break
    if len(selected) < SLICE_TARGETS['low_rank_gold']:
        selected_ids = {id(candidate) for candidate in selected}
        for _, candidate in scored:
            if id(candidate) in selected_ids:
                continue
            selected.append(candidate)
            if len(selected) == SLICE_TARGETS['low_rank_gold']:
                break
    if any((row['candidate_rank_probe']['gold_rank'] or 999) < 4 for row in selected):
        raise ValueError('low_rank_gold selection did not produce rank>=4 or not-in-top-k examples')
    return selected


def build_bucket_tags(stress_slice: str, fqdn: str, relevant: list[str]) -> list[str]:
    tags = [stress_slice]
    if primary_granularity(fqdn) == 'segment':
        tags.extend(['segment_routing', 'parent_fallback'])
    if relevant:
        tags.append('primary_secondary')
    if normalize_base_fqdn(fqdn) in HIGH_RISK_BASES:
        tags.append('high_risk')
    return list(dict.fromkeys(tags))


def finalize_rows(resolver: NamespaceResolver, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    input_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    rank_rows: list[dict[str, str]] = []
    sample_index = 1
    seen_queries: set[str] = set()

    for candidate in candidates:
        sample_id = f'hard_boundary_v1_{sample_index:06d}'
        query = candidate['query']
        base_query = candidate['query'].rsplit('；', 1)[0]
        duplicate_attempt = 0
        while query in seen_queries:
            duplicate_attempt += 1
            tail = pick(HUMAN_TAILS, sample_index + duplicate_attempt)
            if tail in query and duplicate_attempt <= len(HUMAN_TAILS):
                continue
            query = f'{base_query.rstrip("。")}；{tail}。'
            if duplicate_attempt > len(HUMAN_TAILS):
                query = f'{base_query.rstrip("。")}；这是另一个实际场景，先单独看。'
                break
        candidate['query'] = query
        seen_queries.add(query)
        if not resolver.has_fqdn(candidate['gt']):
            raise ValueError(f'Unknown gt fqdn: {candidate["gt"]}')
        for fqdn in candidate['relevant'] + candidate['competing']:
            if not resolver.has_fqdn(fqdn):
                raise ValueError(f'Unknown related/competing fqdn: {fqdn}')

        probe = rank_probe(resolver, candidate, sample_id)
        high_risk_case = candidate['stress_slice'] == 'high_risk_governance_tone' or normalize_base_fqdn(candidate['gt']) in HIGH_RISK_BASES
        notes = candidate['note']
        if len(notes) < 8:
            notes = f'{notes} 旁支线索不应覆盖当前明确请求。'
        if candidate['stress_slice'] == 'low_rank_gold':
            rank_text = 'not_in_top_k' if probe['gold_rank'] is None else f'rank={probe["gold_rank"]}'
            notes = f'{notes} Stage R probe shows gold {rank_text}, head={probe["head_fqdn"]}.'

        input_rows.append(
            {
                'id': sample_id,
                'namespace_version': NAMESPACE_VERSION,
                'query': candidate['query'],
                'context': candidate['context'],
                'metadata': {
                    'dataset_version': DATASET_VERSION,
                    'stress_slice': candidate['stress_slice'],
                    'primary_granularity': primary_granularity(candidate['gt']),
                    'paraphrase_group_id': paraphrase_group_id_for(candidate['stress_slice'], candidate['slug']),
                    'variant_index': candidate['variant_index'],
                },
                'stress_slice': candidate['stress_slice'],
                'difficulty_tag': candidate['stress_slice'],
                'surface_style': candidate['surface_style'],
                'paraphrase_group_id': paraphrase_group_id_for(candidate['stress_slice'], candidate['slug']),
                'variant_index': candidate['variant_index'],
            }
        )
        label_rows.append(
            {
                'id': sample_id,
                'family_id': family_id_for(candidate['stress_slice'], sample_index),
                'paraphrase_group_id': paraphrase_group_id_for(candidate['stress_slice'], candidate['slug']),
                'variant_index': candidate['variant_index'],
                'ground_truth_fqdn': candidate['gt'],
                'acceptable_fqdns': acceptable_fqdns(candidate['gt']),
                'relevant_fqdns': candidate['relevant'],
                'stress_slice': candidate['stress_slice'],
                'expected_failure_mode': candidate['failure'],
                'competing_fqdns': list(dict.fromkeys(candidate['competing'])),
                'bucket_tags': build_bucket_tags(candidate['stress_slice'], candidate['gt'], candidate['relevant']),
                'primary_granularity': primary_granularity(candidate['gt']),
                'secondary_intent_present': bool(candidate['relevant']),
                'high_risk_case': high_risk_case,
                'candidate_rank_probe': probe,
                'notes_for_audit': notes,
            }
        )
        rank_rows.append(
            {
                'id': sample_id,
                'stress_slice': candidate['stress_slice'],
                'ground_truth_fqdn': candidate['gt'],
                'gold_rank': '' if probe['gold_rank'] is None else str(probe['gold_rank']),
                'gold_in_top_k': str(probe['gold_in_top_k']).lower(),
                'head_fqdn': probe['head_fqdn'],
            }
        )
        sample_index += 1

    coverage = coverage_rows(resolver, label_rows)
    stats = compute_stats(resolver, label_rows)
    return input_rows, label_rows, coverage, rank_rows, stats


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
    low_rank_rank_ge4 = sum(1 for rank in low_rank_ranks if rank is None or rank >= 4)
    low_rank_not_in_top_k = sum(1 for rank in low_rank_ranks if rank is None)
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
        'low_rank_gold_rank_ge4_or_missing_count': low_rank_rank_ge4,
        'low_rank_gold_not_in_top_k_count': low_rank_not_in_top_k,
        'ground_truth_fqdn_counts': dict(sorted(gt_counter.items())),
        'ground_truth_l1_counts': dict(sorted(l1_counter.items())),
    }


def coverage_rows(resolver: NamespaceResolver, label_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(stats: dict[str, Any]) -> None:
    manifest = {
        'dataset_name': 'hard_routing_boundary_v1',
        'dataset_version': DATASET_VERSION,
        'namespace_version': NAMESPACE_VERSION,
        'created_date': '2026-06-02',
        'purpose': 'Boundary stress set for single-primary routing, designed to test failure regions where collaboration should help.',
        'frozen_main_collection_unchanged': True,
        'stage_r_probe': {
            'stage_r_version': STAGE_R_VERSION,
            'top_k': RANK_PROBE_TOP_K,
        },
        'target_slice_counts': SLICE_TARGETS,
        'files': {
            'input': str(INPUT_PATH.relative_to(ROOT)),
            'labels': str(LABEL_PATH.relative_to(ROOT)),
            'coverage': str(COVERAGE_PATH.relative_to(ROOT)),
            'rank_probe': str(RANK_PROBE_PATH.relative_to(ROOT)),
        },
        'stats': stats,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    FORMAL_DIR.mkdir(parents=True, exist_ok=True)
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    candidates: list[dict[str, Any]] = []
    candidates.extend(build_low_rank_rows(resolver))
    for stress_slice, specs in SLICE_SPECS.items():
        candidates.extend(expand_slice(stress_slice, specs, SLICE_TARGETS[stress_slice]))
    input_rows, label_rows, coverage, rank_rows, stats = finalize_rows(resolver, candidates)
    if stats['stress_slice_counts'] != SLICE_TARGETS:
        raise ValueError(f'Slice counts mismatch: {stats["stress_slice_counts"]}')
    write_jsonl(INPUT_PATH, input_rows)
    write_jsonl(LABEL_PATH, label_rows)
    write_csv(
        COVERAGE_PATH,
        coverage,
        ['ground_truth_fqdn', 'base_fqdn', 'l1', 'l2', 'sample_count', 'segment_sample_count', 'secondary_intent_count', 'stress_slices'],
    )
    write_csv(RANK_PROBE_PATH, rank_rows, ['id', 'stress_slice', 'ground_truth_fqdn', 'gold_rank', 'gold_in_top_k', 'head_fqdn'])
    write_manifest(stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
