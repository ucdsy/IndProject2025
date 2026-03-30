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
INPUT_PATH = FORMAL_DIR / 'holdout3_input.jsonl'
LABEL_PATH = FORMAL_DIR / 'holdout3_labels.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'holdout3_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'holdout3_coverage_status.csv'
SKELETON_AUDIT_PATH = FORMAL_DIR / 'holdout3_skeleton_audit.csv'

NAMESPACE_VERSION = 'ns_v1_20260311'
DATASET_VERSION = 'holdout3_v0_20260330'

EVAL_BUCKETS = [
    'ordinary_fast_path',
    'sibling_hierarchy',
    'primary_secondary_disentanglement',
    'cross_domain_overlap',
    'high_risk_governance',
]
INTENT_FORMS = [
    'direct_request',
    'scene_description',
    'stepwise_instruction',
    'constraint_first',
    'goal_then_support',
]
SURFACE_STYLES = [
    'colloquial',
    'formal',
    'enterprise',
    'compressed',
    'indirect',
    'mixed',
]

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
    '这事我最关心的还是',
    '先别发散',
    '围绕“',
    '准备落地，但我更担心会不会出事',
    '别先谈实现',
    '如果现在只落一个入口',
    '顺手也把',
)

HIGH_RISK_BASES = {
    'permit.gov.cn',
    'policy.gov.cn',
    'compliance.security.cn',
    'risk.security.cn',
    'fraud.security.cn',
}

SHOWCASE_BUCKET_LIMITS = {
    'sibling_hierarchy': 10,
    'primary_secondary_disentanglement': 10,
    'cross_domain_overlap': 10,
    'high_risk_governance': 10,
}

CITY_LABELS = {
    'beijing': '北京',
    'shanghai': '上海',
    'chengdu': '成都',
    'xian': '西安',
    'hangzhou': '杭州',
    'guangzhou': '广州',
    'shenzhen': '深圳',
    'yunnan': '云南',
}

ORDINARY_COUNTS = {
    'activity.travel.cn': 4,
    'flight.travel.cn': 4,
    'restaurant.travel.cn': 4,
    'transport.travel.cn': 4,
    'weather.cn': 4,
    'beijing.hotel.travel.cn': 2,
    'shenzhen.hotel.travel.cn': 2,
    'hangzhou.itinerary.travel.cn': 2,
    'guangzhou.itinerary.travel.cn': 2,
    'budget.finance.cn': 4,
    'invest.finance.cn': 4,
    'tax.finance.cn': 4,
    'clinic.health.cn': 4,
    'fitness.health.cn': 4,
    'nutrition.health.cn': 4,
    'docs.productivity.cn': 6,
    'schedule.meeting.productivity.cn': 2,
    'summary.meeting.productivity.cn': 2,
    'course.education.cn': 4,
    'tutoring.education.cn': 4,
    'coupon.commerce.cn': 4,
    'price.commerce.cn': 6,
}

SIBLING_COUNTS = {
    'data.compliance.security.cn': 8,
    'account.compliance.security.cn': 8,
    'transaction.compliance.security.cn': 8,
    'issue.invoice.finance.cn': 8,
    'verify.invoice.finance.cn': 8,
    'reimburse.invoice.finance.cn': 8,
    'schedule.meeting.productivity.cn': 6,
    'summary.meeting.productivity.cn': 5,
    'action-items.meeting.productivity.cn': 5,
    'beijing.hotel.travel.cn': 2,
    'shanghai.hotel.travel.cn': 2,
    'chengdu.hotel.travel.cn': 2,
    'hangzhou.hotel.travel.cn': 2,
    'xian.itinerary.travel.cn': 2,
    'shenzhen.itinerary.travel.cn': 2,
    'yunnan.itinerary.travel.cn': 2,
    'beijing.itinerary.travel.cn': 2,
}

PRIMARY_SECONDARY_COUNTS = {
    'docs.productivity.cn': 5,
    'meeting.productivity.cn': 5,
    'budget.finance.cn': 6,
    'invoice.finance.cn': 6,
    'tax.finance.cn': 4,
    'price.commerce.cn': 4,
    'coupon.commerce.cn': 4,
    'course.education.cn': 4,
    'tutoring.education.cn': 4,
    'nutrition.health.cn': 4,
    'clinic.health.cn': 4,
    'fitness.health.cn': 4,
    'transport.travel.cn': 4,
    'flight.travel.cn': 3,
    'activity.travel.cn': 2,
    'restaurant.travel.cn': 2,
    'beijing.hotel.travel.cn': 2,
    'shanghai.hotel.travel.cn': 2,
    'hangzhou.itinerary.travel.cn': 2,
    'xian.itinerary.travel.cn': 2,
    'permit.gov.cn': 2,
    'policy.gov.cn': 2,
    'weather.cn': 3,
}

CROSS_DOMAIN_COUNTS = {
    'activity.travel.cn': 4,
    'flight.travel.cn': 4,
    'restaurant.travel.cn': 4,
    'transport.travel.cn': 4,
    'weather.cn': 4,
    'beijing.hotel.travel.cn': 2,
    'shanghai.hotel.travel.cn': 2,
    'hangzhou.itinerary.travel.cn': 2,
    'xian.itinerary.travel.cn': 2,
    'budget.finance.cn': 4,
    'invest.finance.cn': 4,
    'invoice.finance.cn': 4,
    'tax.finance.cn': 4,
    'clinic.health.cn': 4,
    'fitness.health.cn': 4,
    'nutrition.health.cn': 4,
    'docs.productivity.cn': 5,
    'meeting.productivity.cn': 5,
    'coupon.commerce.cn': 4,
    'price.commerce.cn': 4,
    'course.education.cn': 2,
    'tutoring.education.cn': 2,
    'permit.gov.cn': 1,
    'policy.gov.cn': 1,
}

HIGH_RISK_COUNTS = {
    'compliance.security.cn': 8,
    'risk.security.cn': 8,
    'fraud.security.cn': 8,
    'data.compliance.security.cn': 8,
    'account.compliance.security.cn': 8,
    'transaction.compliance.security.cn': 8,
    'permit.gov.cn': 10,
    'policy.gov.cn': 10,
    'issue.invoice.finance.cn': 4,
    'tax.finance.cn': 4,
    'invoice.finance.cn': 4,
}

SECONDARY_MAP = {
    'docs.productivity.cn': ['risk.security.cn', 'meeting.productivity.cn', 'budget.finance.cn'],
    'meeting.productivity.cn': ['docs.productivity.cn', 'risk.security.cn'],
    'schedule.meeting.productivity.cn': ['docs.productivity.cn', 'summary.meeting.productivity.cn'],
    'summary.meeting.productivity.cn': ['docs.productivity.cn', 'action-items.meeting.productivity.cn'],
    'action-items.meeting.productivity.cn': ['docs.productivity.cn', 'summary.meeting.productivity.cn'],
    'budget.finance.cn': ['price.commerce.cn', 'docs.productivity.cn'],
    'invoice.finance.cn': ['tax.finance.cn', 'budget.finance.cn'],
    'issue.invoice.finance.cn': ['tax.finance.cn', 'budget.finance.cn'],
    'verify.invoice.finance.cn': ['tax.finance.cn', 'reimburse.invoice.finance.cn'],
    'reimburse.invoice.finance.cn': ['budget.finance.cn', 'tax.finance.cn'],
    'tax.finance.cn': ['issue.invoice.finance.cn', 'invoice.finance.cn'],
    'price.commerce.cn': ['coupon.commerce.cn', 'budget.finance.cn'],
    'coupon.commerce.cn': ['price.commerce.cn', 'budget.finance.cn'],
    'course.education.cn': ['tutoring.education.cn', 'docs.productivity.cn'],
    'tutoring.education.cn': ['course.education.cn', 'docs.productivity.cn'],
    'nutrition.health.cn': ['fitness.health.cn', 'clinic.health.cn'],
    'clinic.health.cn': ['nutrition.health.cn', 'course.education.cn'],
    'fitness.health.cn': ['nutrition.health.cn', 'clinic.health.cn'],
    'activity.travel.cn': ['transport.travel.cn', 'weather.cn'],
    'transport.travel.cn': ['hotel.travel.cn', 'weather.cn'],
    'flight.travel.cn': ['weather.cn', 'transport.travel.cn'],
    'restaurant.travel.cn': ['transport.travel.cn', 'coupon.commerce.cn'],
    'hotel.travel.cn': ['transport.travel.cn', 'restaurant.travel.cn'],
    'itinerary.travel.cn': ['weather.cn', 'activity.travel.cn'],
    'beijing.hotel.travel.cn': ['transport.travel.cn', 'restaurant.travel.cn'],
    'shanghai.hotel.travel.cn': ['transport.travel.cn', 'restaurant.travel.cn'],
    'hangzhou.itinerary.travel.cn': ['weather.cn', 'activity.travel.cn'],
    'xian.itinerary.travel.cn': ['weather.cn', 'activity.travel.cn'],
    'weather.cn': ['itinerary.travel.cn', 'flight.travel.cn'],
    'permit.gov.cn': ['policy.gov.cn', 'compliance.security.cn'],
    'policy.gov.cn': ['permit.gov.cn', 'risk.security.cn'],
    'compliance.security.cn': ['risk.security.cn', 'policy.gov.cn'],
    'data.compliance.security.cn': ['risk.security.cn', 'policy.gov.cn'],
    'account.compliance.security.cn': ['risk.security.cn', 'permit.gov.cn'],
    'transaction.compliance.security.cn': ['risk.security.cn', 'policy.gov.cn'],
    'risk.security.cn': ['compliance.security.cn', 'data.compliance.security.cn'],
    'fraud.security.cn': ['risk.security.cn', 'transaction.compliance.security.cn'],
    'invest.finance.cn': ['tax.finance.cn', 'budget.finance.cn'],
}

PROJECTS = ['渠道招募会', '客户 workshop', '展会布场', '驻场培训周', '设备巡检项目', '售后交付周', '园区开放日', '复盘准备会']
AUDIENCES = ['领导评审', '客户决策会', '合作方周报', '财务共享组', '法务窗口', '项目群']
PRODUCTS = ['便携 SSD', '工业相机', '手持噪声仪', '会议麦克风', '演示平板', '工控网关']
DATA_ASSETS = ['工业相机日志', '售后工单附件', '合作方报表', '设备遥测明细', '经销商结算单', '项目归档资料']
ACCOUNT_SCENES = ['经销商门户', '外包协作入口', '服务商控制台', '客户自助台', '伙伴运营后台']
PAYMENT_TARGETS = ['清分服务商', '区域分销商', '渠道代理商', '外部培训供应商', '驻场实施商']
EXPENSE_TYPES = ['住宿票', '交通票', '搭建费', '培训费', '设备租赁费', '年费账单']
MEETING_TYPES = ['回滚复盘会', '采购评审会', '产线周会', '实施同步会', '客户周例会', '风险评审会']
TRAVEL_PURPOSES = ['看展', '布场', '驻场培训', '路演串场', '客户 workshop', '实地调研', '转机过夜', '复盘会']
HEALTH_GOALS = ['控糖', '恢复运动习惯', '做基础检查', '减脂', '调作息', '缓解久坐后的僵硬']
LEARNING_TOPICS = ['SQL 实战', '项目管理', '数据治理', '采购流程', '财务分析', '供应商协同']
CONSUMER_SCENES = ['周末安排', '月底要交的事项', '预算刚批下来的计划', '下周要开的会', '临近上线的窗口']


def pick(options: list[str], index: int, salt: int = 0) -> str:
    return options[(index * 3 + salt * 5) % len(options)]


def expand_round_robin(counts: dict[str, int]) -> list[str]:
    remaining = dict(counts)
    ordered_keys = list(counts)
    out: list[str] = []
    while len(out) < sum(counts.values()):
        progressed = False
        for key in ordered_keys:
            if remaining.get(key, 0) > 0:
                out.append(key)
                remaining[key] -= 1
                progressed = True
        if not progressed:
            break
    return out


def rotate(values: list[str], offset: int) -> list[str]:
    offset = offset % len(values)
    return values[offset:] + values[:offset]


def normalize_base_fqdn(fqdn: str) -> str:
    parts = fqdn.split('.')
    return '.'.join(parts[1:]) if len(parts) == 4 else fqdn


def primary_granularity(fqdn: str) -> str:
    return 'segment' if len(fqdn.split('.')) == 4 else 'base'


def acceptable_fqdns(fqdn: str) -> list[str]:
    base = normalize_base_fqdn(fqdn)
    if base == fqdn:
        return [fqdn]
    return [fqdn, base]


def family_id_for(sample_index: int, eval_bucket: str) -> str:
    return f'holdout3_{eval_bucket}_{sample_index:06d}_f01'


def city_name(segment: str) -> str:
    return CITY_LABELS[segment]


def support_phrase(fqdn: str, index: int) -> str:
    base = normalize_base_fqdn(fqdn)
    segment = fqdn.split('.')[0] if len(fqdn.split('.')) == 4 else ''
    if base == 'docs.productivity.cn':
        return pick(['补一版材料提纲', '把一页式结构顺手列齐', '把对外文档主干补出来'], index)
    if base == 'meeting.productivity.cn':
        if segment == 'schedule':
            return pick(['把参会时段顺手排好', '把会前窗口一并定掉'], index)
        if segment == 'summary':
            return pick(['把纪要主文一并整理出来', '把关键结论顺手收住'], index)
        if segment == 'action-items':
            return pick(['把 owner 和待办顺手抽出来', '把行动项一并挂清'], index)
        return pick(['把会议材料顺手理一下', '把会务相关动作补齐'], index)
    if base == 'budget.finance.cn':
        return pick(['顺手比一眼价格', '把预算拆分再过一下', '再看看费用边界'], index)
    if base == 'invoice.finance.cn':
        if segment == 'issue':
            return pick(['把税务字段顺手列一下', '把入账口径补齐'], index)
        if segment == 'verify':
            return pick(['把税务口径顺手看一下', '把可入账边界补一句'], index)
        if segment == 'reimburse':
            return pick(['把验真提醒顺手记上', '顺手看看预算够不够'], index)
        return pick(['补税务口径', '把票据流转顺手记一下'], index)
    if base == 'tax.finance.cn':
        return pick(['把开票动作顺手记上', '把入账处理一起补齐'], index)
    if base == 'price.commerce.cn':
        return pick(['看看优惠能不能叠', '把折扣信息顺手带上'], index)
    if base == 'coupon.commerce.cn':
        return pick(['把价格对照顺手补上', '补不同平台的价差参考'], index)
    if base == 'course.education.cn':
        return pick(['看看要不要找人辅导', '把配套材料顺手列一下'], index)
    if base == 'tutoring.education.cn':
        return pick(['顺手挑一门对应课程', '把学习材料入口一起记上'], index)
    if base == 'nutrition.health.cn':
        return pick(['补一点运动安排', '把门诊检查一起记上'], index)
    if base == 'clinic.health.cn':
        return pick(['补一点饮食建议', '顺手看下后续训练安排'], index)
    if base == 'fitness.health.cn':
        return pick(['补一版饮食调整', '顺手看看恢复节奏'], index)
    if base == 'activity.travel.cn':
        return pick(['把接驳方式顺手记上', '把天气窗口一并看一下'], index)
    if base == 'transport.travel.cn':
        return pick(['顺手看住处是否也该调整', '把天气窗口顺带看掉'], index)
    if base == 'flight.travel.cn':
        return pick(['把天气窗口顺手补上', '把到达后的接驳一并记住'], index)
    if base == 'restaurant.travel.cn':
        return pick(['把接驳时间一起看下', '顺手查下有没有优惠'], index)
    if base == 'hotel.travel.cn':
        city = city_name(segment) if segment else '这段'
        return pick([f'把{city}这边的接驳也记上', f'顺手看下{city}附近餐食'], index)
    if base == 'itinerary.travel.cn':
        city = city_name(segment) if segment else '这段'
        return pick([f'把{city}的天气窗口一并带上', f'顺手把{city}活动顺序标一下'], index)
    if base == 'weather.cn':
        return pick(['把行程顺手再看一眼', '把航班或活动再对一遍'], index)
    if base == 'permit.gov.cn':
        return pick(['顺手把相关依据也找出来', '把办理顺序一并理清'], index)
    if base == 'policy.gov.cn':
        return pick(['把可能要补的动作顺手记下', '顺手把相关依据找齐'], index)
    if base == 'compliance.security.cn':
        return pick(['顺手把风险点也记一下', '把要留痕的地方顺手列一下'], index)
    if base == 'risk.security.cn':
        return pick(['顺手看看合规要求', '把哪些地方容易踩线顺手记一下'], index)
    if base == 'fraud.security.cn':
        return pick(['补一眼风控规则', '把异常阈值顺手带上'], index)
    if base == 'invest.finance.cn':
        return pick(['把税费影响顺手看一眼', '顺手看看期限怎么选更稳'], index)
    return pick(['补一个配套动作', '顺手带一条辅助信息'], index)


def hint_phrase(fqdn: str, index: int) -> str:
    base = normalize_base_fqdn(fqdn)
    if base == 'risk.security.cn':
        return pick(['几个容易出事的点', '一些风控条件', '几处不能踩的红线'], index)
    if base == 'policy.gov.cn':
        return pick(['几条相关依据', '一些标准边界', '几项政策口径'], index)
    if base == 'permit.gov.cn':
        return pick(['一些前置手续信息', '办理顺序的碎片信息', '准入动作相关的提示'], index)
    if base == 'price.commerce.cn':
        return pick(['价格对照信息', '渠道价差信息', '报价相关碎片'], index)
    if base == 'coupon.commerce.cn':
        return pick(['优惠规则信息', '券和折扣的提示', '促销相关碎片'], index)
    if base == 'tax.finance.cn':
        return pick(['税务口径信息', '入账边界的提示', '税费处理相关说明'], index)
    if base == 'weather.cn':
        return pick(['天气窗口信息', '降雨和温差提示', '天气相关碎片'], index)
    if base == 'transport.travel.cn':
        return pick(['接驳安排信息', '换乘相关提示', '通勤约束'], index)
    if base == 'itinerary.travel.cn':
        return pick(['行程顺序信息', '每日安排的提示', '行程骨架相关说明'], index)
    if base == 'hotel.travel.cn':
        return pick(['住处选择信息', '落脚点相关提示', '住宿约束'], index)
    if base == 'course.education.cn':
        return pick(['课程材料信息', '学习路径相关提示', '入门资料碎片'], index)
    if base == 'tutoring.education.cn':
        return pick(['辅导方式信息', '带练相关提示', '辅导安排碎片'], index)
    if base == 'nutrition.health.cn':
        return pick(['饮食调整信息', '饮食边界提示', '控糖相关说明'], index)
    if base == 'fitness.health.cn':
        return pick(['训练安排信息', '运动节奏提示', '恢复计划碎片'], index)
    return pick(['一些顺带信息', '几条辅助线索', '一些先不用放在最前面的提示'], index)


def bucket_constraint(eval_bucket: str, fqdn: str, index: int) -> str:
    if eval_bucket == 'ordinary_fast_path':
        return pick(['我这次只想先解决最直接的那一步', '先别扩成别的问题', '我想先把最核心的事办掉'], index)
    if eval_bucket == 'sibling_hierarchy':
        return pick(['别把相近但不是一回事的内容混在一起', '我不想在相近的问题里来回绕', '先弄清最贴近我这件事的那个就行'], index)
    if eval_bucket == 'primary_secondary_disentanglement':
        return pick(['我主要想问的和顺带那件事得分开', '补充那件事可以记一下，但别盖过我现在最想问的', '顺带需求先别抢我现在这件事'], index)
    if eval_bucket == 'cross_domain_overlap':
        return pick(['旁边信息很多，但我最在意的问题只有一个', '跨域信息会干扰判断，但我现在想问的不能跑偏', '辅助信息很多，但别把我真正的问题带偏'], index)
    return pick(['这事一旦弄错代价会很高', '我更担心风险和合规别踩线', '得先把合规、身份或资金边界看清'], index)


def node_payload(fqdn: str, index: int) -> dict[str, Any]:
    parts = fqdn.split('.')
    segment = parts[0] if len(parts) == 4 else ''
    base = normalize_base_fqdn(fqdn)

    if base == 'activity.travel.cn':
        city = pick(list(CITY_LABELS.values()), index)
        gap = pick(['半天空档', '一个晚上', '一整个下午', '两小时窗口'], index, 1)
        scene = f'在{city}临时多出{gap}，想塞进一个不折腾的活动'
        primary = pick(['帮我挑几个能塞进去的活动', '先看看这段能安排什么活动', '把这点空档能去的活动筛一遍'], index)
        context = {'city': city, 'time_window': gap}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'budget.finance.cn':
        project = pick(PROJECTS, index)
        scene = f'{project}的费用盘子还没压住，分项和上限都没收口'
        primary = pick(['先把预算和上限拆清楚', '帮我把费用边界和科目理一遍', '先把这笔预算怎么拆分顺一遍'], index)
        context = {'project': project, 'industry': 'enterprise_service'}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'clinic.health.cn':
        goal = pick(HEALTH_GOALS, index)
        scene = f'关于“{goal}”这件事，当前想走一次普通门诊或基础检查'
        primary = pick(['看看普通门诊或检查该怎么约', '先给我理一下门诊检查怎么安排', '帮我判断先做哪类基础检查'], index)
        context = {'goal': goal}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'compliance.security.cn':
        if segment == 'data':
            asset = pick(DATA_ASSETS, index)
            dest = pick(['海外 BI 看板', '合作方排障台', '外部分析仓', '跨区质检看板'], index, 1)
            scene = f'{asset}准备同步到{dest}，但外发边界和留痕口径还没定'
            primary = pick(['先看这类数据外发要补什么检查', '帮我把数据共享前要过的检查理一遍', '先判断这类数据同步有哪些合规前置'], index)
            context = {'industry': 'manufacturing', 'destination': dest}
            note = ''
        elif segment == 'account':
            portal = pick(ACCOUNT_SCENES, index)
            scene = f'{portal}要接统一账号，外部协作人员也会进来，实名和权限还没收口'
            primary = pick(['先看账号实名和权限要补哪些动作', '帮我把账号治理这块先理顺', '先判断外部协作账号要过哪些检查'], index)
            context = {'industry': 'enterprise_service', 'service': portal}
            note = ''
        elif segment == 'transaction':
            target = pick(PAYMENT_TARGETS, index)
            scene = f'要给{target}打首笔款项，但交易对象核验和留痕动作还没理清'
            primary = pick(['先把打款前的对象核验理一遍', '先看首笔打款前要核什么', '帮我判断这笔付款前置检查有哪些'], index)
            context = {'industry': 'enterprise_service', 'counterparty': target}
            note = ''
        else:
            asset = pick(['企业档案', '合作方报表', '运维日志包', '项目归档资料'], index)
            scene = f'{asset}要外发或归档到第三方系统，当前只知道需要先过一轮合规检查'
            primary = pick(['先过一遍合规检查', '帮我看看这事先查哪些合规点', '先判断外发或归档前要补哪些检查'], index)
            context = {'industry': 'enterprise_service'}
            note = ''
        return {'scene': scene, 'primary': primary, 'context': context, 'note': note}

    if base == 'coupon.commerce.cn':
        product = pick(PRODUCTS, index)
        scene = f'买{product}这单如果不看优惠规则，明显会多花一笔'
        primary = pick(['先看看有什么券或优惠能用', '帮我找最划算的优惠入口', '先把折扣规则看清'], index)
        context = {'channel': 'ecommerce', 'product': product}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'course.education.cn':
        topic = pick(LEARNING_TOPICS, index)
        scene = f'想系统补一下{topic}，但还没决定先从哪门课开始'
        primary = pick(['先帮我挑合适的入门课', '看看先上哪门课更合适', '先给我推荐一门能开始学的课'], index)
        context = {'goal': topic}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'docs.productivity.cn':
        audience = pick(AUDIENCES, index)
        project = pick(PROJECTS, index, 1)
        scene = f'要把{project}相关内容压成一页给{audience}看，但材料结构还没落稳'
        primary = pick(['先把这一页材料的骨架搭出来', '帮我把文档主干先列出来', '先把给对方看的材料结构理顺'], index)
        context = {'audience': audience, 'project': project}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'fitness.health.cn':
        goal = pick(HEALTH_GOALS, index)
        scene = f'想把“{goal}”重新捡起来，但训练起步还没落成具体动作'
        primary = pick(['先给我一版能开始做的训练安排', '帮我排个起步训练计划', '先看看怎么恢复运动更稳'], index)
        context = {'goal': goal}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'flight.travel.cn':
        city = pick(list(CITY_LABELS.values()), index)
        purpose = pick(TRAVEL_PURPOSES, index, 1)
        scene = f'去{city}{purpose}这趟，出发和返回窗口都卡得很紧，航班还没定'
        primary = pick(['先帮我筛合适的航班', '看看这一趟怎么飞更合适', '先把出发和返回航班挑出来'], index)
        context = {'city': city, 'travel_purpose': purpose}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'fraud.security.cn':
        campaign = pick(['返利订单', '积分换购', '优惠券活动', '设备补贴申请'], index)
        scene = f'{campaign}里担心有人钻规则，异常迹象和拦截重点还没排清'
        primary = pick(['先帮我看看最该防的异常点', '先排一遍容易出问题的地方', '先看哪些风险信号最值得拦'], index)
        context = {'industry': 'consumer_service', 'campaign': campaign}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'hotel.travel.cn':
        city = city_name(segment)
        purpose = pick(TRAVEL_PURPOSES, index)
        stay = pick(['只住一晚', '要连住两晚', '红眼到达后过夜', '第二天一早就要进场'], index, 1)
        scene = f'{city}这趟是为了{purpose}，{stay}，但落脚点还没筛到合适方案'
        primary = pick([f'帮我挑个{city}这边合适的住处', f'先看看{city}这趟住哪里更顺', f'先筛一轮{city}这边不折腾的酒店'], index)
        context = {'city': city, 'travel_purpose': purpose}
        note = 'l3 evidence 来自明确城市与住宿场景。'
        return {'scene': scene, 'primary': primary, 'context': context, 'note': note}

    if base == 'invest.finance.cn':
        horizon = pick(['三个月', '半年', '九个月', '一年'], index)
        scene = f'手上有一笔{horizon}内不用的闲钱，目标偏稳，不想走激进方向'
        primary = pick(['看看更稳妥的理财安排', '先给我几个偏稳的资金去向', '帮我想想这笔钱怎么放更稳'], index)
        context = {'horizon': horizon}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'invoice.finance.cn':
        if segment == 'issue':
            expense = pick(EXPENSE_TYPES, index)
            scene = f'收了{expense}对应的费用后需要补电子票，但开票动作和字段还没理清'
            primary = pick(['先把开票这一步理清', '看看补票要准备什么', '先判断怎么开这张票'], index)
            context = {'industry': 'enterprise_service', 'expense_type': expense}
            note = ''
        elif segment == 'verify':
            expense = pick(EXPENSE_TYPES, index)
            scene = f'手里收了一批{expense}相关票据，真伪和可用性还没过一遍'
            primary = pick(['先帮我过一遍这些票真不真', '看看这些票据能不能用', '先验一下这批票'], index)
            context = {'industry': 'enterprise_service', 'expense_type': expense}
            note = ''
        elif segment == 'reimburse':
            expense = pick(EXPENSE_TYPES, index)
            scene = f'报回来的{expense}需要分清哪些能直接进报销，当前还没做第一轮判断'
            primary = pick(['先判断哪些能直接报销', '帮我分一下哪些票能报', '先把报销边界过一遍'], index)
            context = {'industry': 'enterprise_service', 'expense_type': expense}
            note = ''
        else:
            project = pick(PROJECTS, index)
            scene = f'{project}相关票据要一次梳顺，流转步骤和处理顺序还没收住'
            primary = pick(['先把整条票据处理顺一遍', '看看这批发票该怎么流转', '先把票据处理流程理清'], index)
            context = {'industry': 'enterprise_service', 'project': project}
            note = ''
        return {'scene': scene, 'primary': primary, 'context': context, 'note': note}

    if base == 'itinerary.travel.cn':
        city = city_name(segment)
        purpose = pick(TRAVEL_PURPOSES, index)
        days = pick(['两天', '三天', '四天', '一个周末'], index, 1)
        scene = f'{city}这段{days}安排是为了{purpose}，地点和顺序大致有了，但每天怎么排还没顺'
        primary = pick([f'帮我把{city}这段行程排出来', f'先把{city}每天怎么走顺一下', f'先给我排个{city}这趟不折腾的行程'], index)
        context = {'city': city, 'travel_purpose': purpose, 'time_window': days}
        note = 'l3 evidence 来自明确城市与行程场景。'
        return {'scene': scene, 'primary': primary, 'context': context, 'note': note}

    if base == 'meeting.productivity.cn':
        meeting = pick(MEETING_TYPES, index)
        if segment == 'schedule':
            scene = f'{meeting}的人和时间还没对齐，会期窗口也没完全锁住'
            primary = pick(['先把时间和参会人排开', '帮我把会议时间敲定', '先把会期窗口排出来'], index)
            context = {'meeting_type': meeting}
            note = ''
        elif segment == 'summary':
            scene = f'{meeting}刚结束，录音和散落记录都有，但纪要还没写出来'
            primary = pick(['先帮我把纪要写出来', '把会上的结论先整理一下', '先出一版会议纪要'], index)
            context = {'meeting_type': meeting}
            note = ''
        elif segment == 'action-items':
            scene = f'{meeting}里冒出一串 owner 和待办，当前还没把行动项抽干净'
            primary = pick(['先把 owner 和待办拎出来', '帮我把行动项整理清楚', '先抽出会后的待办'], index)
            context = {'meeting_type': meeting}
            note = ''
        else:
            scene = f'{meeting}相关动作要整体理顺，但会务和材料暂时混在一起'
            primary = pick(['先把会务相关的事理顺', '帮我把会议这摊事先收住', '先把会议安排整体顺一下'], index)
            context = {'meeting_type': meeting}
            note = ''
        return {'scene': scene, 'primary': primary, 'context': context, 'note': note}

    if base == 'nutrition.health.cn':
        goal = pick(HEALTH_GOALS, index)
        scene = f'最近针对“{goal}”想从饮食下手，但具体怎么调还没成方案'
        primary = pick(['先给我一版饮食调整建议', '看看吃这块该怎么改', '先帮我把饮食方案理一下'], index)
        context = {'goal': goal}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'permit.gov.cn':
        service = pick(['短信核验能力', '设备告警接口', '合作方下载入口', '园区服务小程序', '对外通知接口'], index)
        scene = f'{service}准备对外开放，但准入动作和办理顺序还没补齐'
        primary = pick(['先看看要补哪些手续或备案', '帮我理一下前置手续和顺序', '先判断这项能力上线前要办什么'], index)
        context = {'industry': 'enterprise_service', 'service': service}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'policy.gov.cn':
        service = pick(['设备遥测接口', '工业数据共享接口', '企业通知服务', '对外报表下载', '外部合作方接入'], index)
        scene = f'{service}要上线，但相关依据和标准边界还没有核完'
        primary = pick(['先看看适用的规则和边界', '帮我把相关依据理一遍', '先判断有哪些标准不能碰'], index)
        context = {'industry': 'manufacturing', 'service': service}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'price.commerce.cn':
        product = pick(PRODUCTS, index)
        scene = f'要买{product}，不同渠道的报价看起来差不少，但还没比到同一口径'
        primary = pick(['先比一下各渠道价格', '帮我看看哪里买更合适', '先把报价拉平对一下'], index)
        context = {'channel': 'ecommerce', 'product': product}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'restaurant.travel.cn':
        city = pick(list(CITY_LABELS.values()), index)
        purpose = pick(TRAVEL_PURPOSES, index, 1)
        scene = f'去{city}{purpose}中间只留出一顿饭的空档，想找个不折腾的餐食点'
        primary = pick(['先找个不折腾的吃饭地方', '帮我筛下附近合适的餐厅', '先看看哪家最顺路'], index)
        context = {'city': city, 'travel_purpose': purpose}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'risk.security.cn':
        channel = pick(['远程升级通道', '外部下载入口', '客户自助报修口', '供应商协作端口', '对外查询接口'], index)
        scene = f'{channel}要开放，但高风险点、留痕和策略边界还没排清'
        primary = pick(['先把最该防的风险点排出来', '帮我看看这事容易踩哪些线', '先过一遍容易出事的地方'], index)
        context = {'industry': 'manufacturing', 'service': channel}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'tax.finance.cn':
        matter = pick(['服务续费', '设备采购', '渠道返点', '搭建费用', '培训费用'], index)
        scene = f'{matter}要进账，但税务口径和适用边界目前还没讲清'
        primary = pick(['先看看税务上该怎么处理', '帮我把税务口径理一下', '先判断这笔在税务上怎么走'], index)
        context = {'industry': 'enterprise_service', 'matter': matter}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'transport.travel.cn':
        city = pick(list(CITY_LABELS.values()), index)
        arrival = pick(['到站后还要二次换乘', '落地后马上要赶去会场', '深夜到站后还要转去住处', '高铁下来还要进园区'], index, 1)
        scene = f'{city}这一段{arrival}，但接驳路线还没收住'
        primary = pick(['先看看怎么接驳最省事', '帮我排个顺一点的接驳方案', '先把换乘路线理一遍'], index)
        context = {'city': city}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'tutoring.education.cn':
        topic = pick(LEARNING_TOPICS, index)
        scene = f'学{topic}的时候卡在没人带着练，想找更合适的辅导方式'
        primary = pick(['先找个合适的辅导方式', '帮我看看哪种带练更适合', '先想想怎么找人带着学'], index)
        context = {'goal': topic}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    if base == 'weather.cn':
        city = pick(list(CITY_LABELS.values()), index)
        window = pick(['明天', '本周末', '下周', '这两天'], index, 1)
        scene = f'{city}{window}这段安排特别吃天气窗口，但天气到底怎么样还没看准'
        primary = pick(['先看看天气到底怎么样', '帮我查下天气窗口', '先判断这几天的天气情况'], index)
        context = {'city': city, 'time_window': window}
        return {'scene': scene, 'primary': primary, 'context': context, 'note': ''}

    raise ValueError(f'Unsupported node for holdout3 generation: {fqdn}')


def secondary_for(primary_fqdn: str, occurrence: int) -> str:
    exact = SECONDARY_MAP.get(primary_fqdn)
    if exact:
        return pick(exact, occurrence)
    base = normalize_base_fqdn(primary_fqdn)
    options = SECONDARY_MAP.get(base)
    if options:
        return pick(options, occurrence)
    return 'docs.productivity.cn'


def render_secondary_clause(style: str, secondary_text: str) -> str:
    if style == 'colloquial':
        return f'；另外，{secondary_text}'
    if style == 'formal':
        return f'；另外，{secondary_text}'
    if style == 'enterprise':
        return f'；另外，{secondary_text}'
    if style == 'compressed':
        return f' / 另外:{secondary_text}'
    if style == 'indirect':
        return f'；另外，{secondary_text}'
    return f'；另外，{secondary_text}'


def render_query(
    intent_form: str,
    surface_style: str,
    scene: str,
    primary: str,
    secondary_text: str,
    constraint: str,
    has_secondary: bool,
) -> str:
    secondary_clause = render_secondary_clause(surface_style, secondary_text) if has_secondary else ''

    if intent_form == 'direct_request':
        if surface_style == 'colloquial':
            return f'是这样，{scene}。我现在主要想问：{primary}{secondary_clause}。'
        if surface_style == 'formal':
            return f'关于“{scene}”，我目前最需要的是：{primary}{secondary_clause}。'
        if surface_style == 'enterprise':
            return f'目前的情况是：{scene}。我这边优先想看的是：{primary}{secondary_clause}。'
        if surface_style == 'compressed':
            return f'{scene}；需求:{primary}{secondary_clause}'
        if surface_style == 'indirect':
            return f'{scene}。要是现在只抓一件事，我最想搞清楚的是：{primary}{secondary_clause}。'
        return f'先说下情况：{scene}。我更想问的是：{primary}{secondary_clause}。'

    if intent_form == 'scene_description':
        if surface_style == 'colloquial':
            return f'现在的情况有点杂：{scene}。不过我最想问的是：{primary}{secondary_clause}。'
        if surface_style == 'formal':
            return f'当前情况如下：{scene}。其中我最需要的是：{primary}{secondary_clause}。'
        if surface_style == 'enterprise':
            return f'现状是：{scene}。在这些事里，我这边更关心的是：{primary}{secondary_clause}。'
        if surface_style == 'compressed':
            return f'情况:{scene}；想问:{primary}{secondary_clause}'
        if surface_style == 'indirect':
            return f'{scene}。如果先只抓重点，我最想确认的是：{primary}{secondary_clause}。'
        return f'背景大概是这样：{scene}。真要先问的话，我会先问：{primary}{secondary_clause}。'

    if intent_form == 'stepwise_instruction':
        if surface_style == 'colloquial':
            return f'我想先把重点拎出来：{primary}{secondary_clause}。其他情况是“{scene}”。'
        if surface_style == 'formal':
            return f'如果分开来看，我最先想确认的是：{primary}{secondary_clause}。相关情况是“{scene}”。'
        if surface_style == 'enterprise':
            return f'这边先说重点：{primary}{secondary_clause}。相关背景是：{scene}。'
        if surface_style == 'compressed':
            return f'重点:{primary}{secondary_clause}；背景:{scene}'
        if surface_style == 'indirect':
            return f'{scene}。这些先放一边的话，我最想确认的是：{primary}{secondary_clause}。'
        return f'我先说重点：{primary}{secondary_clause}。背景和其他信息是“{scene}”。'

    if intent_form == 'constraint_first':
        if surface_style == 'colloquial':
            return f'我先把前提说清：{constraint}。在这个前提下，我最想问的是：{primary}{secondary_clause}。相关情况是“{scene}”。'
        if surface_style == 'formal':
            return f'前提是：{constraint}。在此基础上，我目前最需要的是：{primary}{secondary_clause}。相关情况是“{scene}”。'
        if surface_style == 'enterprise':
            return f'约束是：{constraint}。在这个范围内，我这边更关心的是：{primary}{secondary_clause}。背景是：{scene}。'
        if surface_style == 'compressed':
            return f'前提:{constraint}；需求:{primary}{secondary_clause}；情况:{scene}'
        if surface_style == 'indirect':
            return f'前提先放这：{constraint}。基于这个情况，我最想确认的是：{primary}{secondary_clause}。'
        return f'先说前提：{constraint}。再看“{scene}”，我现在最想问的是：{primary}{secondary_clause}。'

    if surface_style == 'colloquial':
        return f'我最想办的就一件事：{primary}。其他情况是“{scene}”{secondary_clause}。'
    if surface_style == 'formal':
        return f'我当前最明确的需求是：{primary}。补充情况为：“{scene}”{secondary_clause}。'
    if surface_style == 'enterprise':
        return f'当前主需求是：{primary}。补充情况：{scene}{secondary_clause}。'
    if surface_style == 'compressed':
        return f'需求:{primary}；补充:{scene}{secondary_clause}'
    if surface_style == 'indirect':
        return f'如果先只说我最关心的，就是：{primary}。至于背景，则是“{scene}”{secondary_clause}。'
    return f'我最关心的还是：{primary}。其余背景是“{scene}”{secondary_clause}。'


def uniquify_query(query: str, eval_bucket: str, duplicate_index: int) -> str:
    if duplicate_index == 0:
        return query
    suffix_map = {
        'ordinary_fast_path': ['先把这件事办了就行', '别一下子扯到别处去'],
        'sibling_hierarchy': ['我问的就是最贴近这层', '别把相关但不同的事混在一起'],
        'primary_secondary_disentanglement': ['顺带那件事先往后放', '主次我想分清一点'],
        'cross_domain_overlap': ['旁边的信息别把重点带偏', '我还是想先把主问题说清'],
        'high_risk_governance': ['这事我会先看有没有风险', '宁可先把边界问明白'],
    }
    tail = suffix_map[eval_bucket][(duplicate_index - 1) % len(suffix_map[eval_bucket])]
    trimmed = query.rstrip('。')
    if trimmed.endswith('|') or trimmed.endswith('/'):
        trimmed = trimmed.rstrip('|/ ').rstrip()
    return f'{trimmed}；{tail}。'


def build_bucket_tags(eval_bucket: str, fqdn: str, has_secondary: bool) -> list[str]:
    tags: list[str] = []
    if eval_bucket == 'ordinary_fast_path':
        tags.extend(['fast_path', 'low_competition'])
    elif eval_bucket == 'sibling_hierarchy':
        tags.extend(['sibling_competition', 'hierarchy_resolution'])
    elif eval_bucket == 'primary_secondary_disentanglement':
        tags.extend(['primary_secondary', 'multi_intent'])
    elif eval_bucket == 'cross_domain_overlap':
        tags.extend(['cross_domain_boundary'])
    else:
        tags.extend(['governance_boundary', 'risk_gate'])
    if primary_granularity(fqdn) == 'segment':
        tags.extend(['segment_routing', 'parent_fallback'])
    if has_secondary and 'multi_intent' not in tags:
        tags.append('multi_intent')
    return list(dict.fromkeys(tags))


def compose_audit_note(
    seed_note: str,
    eval_bucket: str,
    primary_fqdn: str,
    secondary_fqdn: str,
    secondary_text: str,
    has_secondary: bool,
    high_risk_case: bool,
    scene: str,
    primary_text: str,
    showcase_case: bool,
) -> str:
    notes: list[str] = []
    if seed_note:
        notes.append(seed_note)

    base = normalize_base_fqdn(primary_fqdn)
    granularity = primary_granularity(primary_fqdn)

    if showcase_case:
        if eval_bucket == 'sibling_hierarchy':
            if granularity == 'segment':
                notes.append(
                    f'样本核心场景是“{scene}”，主问句是“{primary_text}”。证据落在具体子类 {primary_fqdn}，不能只退回父节点 {base}。'
                )
            else:
                notes.append(
                    f'样本主问句是“{primary_text}”。虽然同层兄弟节点容易混淆，但 scene 仍把需求锁在 {primary_fqdn}。'
                )
            return ' '.join(notes)
        if eval_bucket == 'primary_secondary_disentanglement' and has_secondary and secondary_fqdn:
            notes.append(
                f'主问句是“{primary_text}”，而“{secondary_text}”只是顺带诉求，对应 {secondary_fqdn}。因此主标签保留为 {primary_fqdn}，secondary 只进 relevant。'
            )
            return ' '.join(notes)
        if eval_bucket == 'cross_domain_overlap':
            if has_secondary and secondary_fqdn:
                notes.append(
                    f'场景里混入了别域线索，但 query 真正要解决的是“{primary_text}”；“{secondary_text}”只对应 {secondary_fqdn}，不能盖过 {primary_fqdn}。'
                )
            else:
                notes.append(
                    f'场景里混入了邻域提示，但主问句仍是“{primary_text}”。这些干扰不构成独立次任务，所以只保留 {primary_fqdn}，不把 {secondary_fqdn} 记进 relevant。'
                )
            return ' '.join(notes)
        if eval_bucket == 'high_risk_governance':
            if has_secondary and secondary_fqdn:
                notes.append(
                    f'这条样本难在风险口吻很强，但真正动作仍是“{primary_text}”；“{secondary_text}”只给 {secondary_fqdn} 提供辅助线索，主标签仍为 {primary_fqdn}。'
                )
            else:
                notes.append(
                    f'这条样本把风险、边界、留痕说得很重，但真正动作仍是“{primary_text}”。因此主标签命中 {primary_fqdn}，而不是被更泛的治理类邻居带偏。'
                )
            return ' '.join(notes)

    if eval_bucket == 'high_risk_governance':
        if has_secondary and secondary_fqdn:
            notes.append(f'高风险治理样本：主标签是 {primary_fqdn}，{secondary_fqdn} 仅作相关次要线索。')
        else:
            notes.append(f'高风险治理样本：即使 query 带规则、风控或留痕口吻，主标签仍应命中 {primary_fqdn}。')
    elif eval_bucket == 'sibling_hierarchy':
        if granularity == 'segment':
            notes.append(f'层级近邻难例：需要命中具体 segment {primary_fqdn}，不能只回到父节点 {base}。')
        else:
            notes.append(f'层级近邻难例：相邻节点容易混淆，但主标签仍应保持为 {primary_fqdn}。')
    elif eval_bucket == 'primary_secondary_disentanglement' and has_secondary and secondary_fqdn:
        notes.append(f'主次分离难例：{secondary_fqdn} 是相关但非主标签，主标签仍为 {primary_fqdn}。')
    elif eval_bucket == 'cross_domain_overlap':
        if has_secondary and secondary_fqdn:
            notes.append(f'跨域重叠难例：{secondary_fqdn} 与主任务共现，但主标签仍为 {primary_fqdn}。')
        else:
            notes.append(f'跨域干扰难例：query 混入邻域线索，但无 secondary ground truth，主标签仍为 {primary_fqdn}。')
    elif high_risk_case:
        notes.append(f'高风险 base 样本：虽然不在高风险 bucket，主标签仍为 {primary_fqdn}。')

    return ' '.join(notes)


def load_old_family_index(resolver: NamespaceResolver) -> dict[str, list[str]]:
    old_by_base: dict[str, list[str]] = defaultdict(list)
    for path in OLD_LABEL_FILES:
        for row in load_jsonl(path):
            gt = row.get('ground_truth_fqdn')
            family_id = row.get('family_id')
            if gt and family_id:
                old_by_base[normalize_base_fqdn(gt)].append(family_id)
    return old_by_base


def build_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    old_family_index = load_old_family_index(resolver)

    bucket_to_nodes = {
        'ordinary_fast_path': expand_round_robin(ORDINARY_COUNTS),
        'sibling_hierarchy': expand_round_robin(SIBLING_COUNTS),
        'primary_secondary_disentanglement': expand_round_robin(PRIMARY_SECONDARY_COUNTS),
        'cross_domain_overlap': expand_round_robin(CROSS_DOMAIN_COUNTS),
        'high_risk_governance': expand_round_robin(HIGH_RISK_COUNTS),
    }

    input_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, str]] = []
    skeleton_rows: list[dict[str, str]] = []

    base_counter: Counter[str] = Counter()
    l3_counter: Counter[str] = Counter()
    l1_counter: Counter[str] = Counter()
    bucket_counter: Counter[str] = Counter()
    intent_counter: Counter[str] = Counter()
    style_counter: Counter[str] = Counter()
    skeleton_counter_by_bucket: dict[str, Counter[str]] = defaultdict(Counter)
    showcase_signatures_by_bucket: dict[str, set[tuple[str, str, bool]]] = defaultdict(set)
    multi_intent_hits = 0
    high_risk_hits = 0
    seen_queries: Counter[str] = Counter()

    sample_index = 1

    for bucket_index, eval_bucket in enumerate(EVAL_BUCKETS):
        forms = [INTENT_FORMS[i % len(INTENT_FORMS)] for i in range(80)]
        styles = [rotate(SURFACE_STYLES, bucket_index)[i % len(SURFACE_STYLES)] for i in range(80)]
        node_occurrence: Counter[str] = Counter()

        for bucket_pos, primary_fqdn in enumerate(bucket_to_nodes[eval_bucket]):
            sample_id = f'holdout3_{sample_index:06d}'
            family_id = family_id_for(sample_index, eval_bucket)
            intent_form = forms[bucket_pos]
            surface_style = styles[bucket_pos]
            node_occurrence[primary_fqdn] += 1
            local_index = node_occurrence[primary_fqdn]

            payload = node_payload(primary_fqdn, local_index)
            scene = payload['scene']
            primary_text = payload['primary']
            context = dict(payload['context'])
            note = payload['note']

            has_secondary = (
                eval_bucket == 'primary_secondary_disentanglement'
                or (eval_bucket == 'cross_domain_overlap' and bucket_pos % 2 == 0)
                or (eval_bucket == 'high_risk_governance' and bucket_pos % 5 == 0)
            )
            secondary_fqdn = secondary_for(primary_fqdn, local_index) if has_secondary or eval_bucket == 'cross_domain_overlap' else ''
            if eval_bucket == 'cross_domain_overlap' and not has_secondary and secondary_fqdn:
                scene = f'{scene}，另外还混着{hint_phrase(secondary_fqdn, local_index)}'

            secondary_text = support_phrase(secondary_fqdn, local_index) if has_secondary else ''
            query_skeleton_id = f'{intent_form}.{surface_style}'
            query = render_query(
                intent_form=intent_form,
                surface_style=surface_style,
                scene=scene,
                primary=primary_text,
                secondary_text=secondary_text,
                constraint=bucket_constraint(eval_bucket, primary_fqdn, bucket_pos + 1),
                has_secondary=has_secondary,
            )
            query = uniquify_query(query, eval_bucket, seen_queries[query])
            seen_queries[query] += 1

            if any(marker in query for marker in BANNED_OLD_MARKERS):
                raise ValueError(f'holdout3 query 命中旧 skeleton marker: {sample_id} -> {query}')

            if not resolver.has_fqdn(primary_fqdn):
                raise ValueError(f'Unknown primary fqdn: {primary_fqdn}')
            if has_secondary and secondary_fqdn and not resolver.has_fqdn(secondary_fqdn):
                raise ValueError(f'Unknown secondary fqdn: {secondary_fqdn}')

            relevant = [secondary_fqdn] if has_secondary and secondary_fqdn else []
            bucket_tags = build_bucket_tags(eval_bucket, primary_fqdn, has_secondary)
            base = normalize_base_fqdn(primary_fqdn)
            base_node = resolver.get_node(base)
            suspected_old = pick(old_family_index.get(base, ['']), local_index) if old_family_index.get(base) else ''
            high_risk_case = eval_bucket == 'high_risk_governance' or base in HIGH_RISK_BASES
            showcase_signature = (primary_fqdn, secondary_fqdn if relevant else '', bool(relevant))
            showcase_case = False
            showcase_limit = SHOWCASE_BUCKET_LIMITS.get(eval_bucket)
            if showcase_limit is not None:
                signatures = showcase_signatures_by_bucket[eval_bucket]
                if showcase_signature not in signatures and len(signatures) < showcase_limit:
                    signatures.add(showcase_signature)
                    showcase_case = True
            note = compose_audit_note(
                seed_note=note,
                eval_bucket=eval_bucket,
                primary_fqdn=primary_fqdn,
                secondary_fqdn=secondary_fqdn,
                secondary_text=secondary_text,
                has_secondary=bool(relevant),
                high_risk_case=high_risk_case,
                scene=scene,
                primary_text=primary_text,
                showcase_case=showcase_case,
            )

            input_rows.append(
                {
                    'id': sample_id,
                    'namespace_version': NAMESPACE_VERSION,
                    'query': query,
                    'context': context,
                    'metadata': {
                        'base_fqdn': base,
                        'primary_granularity': primary_granularity(primary_fqdn),
                        'query_skeleton_id': query_skeleton_id,
                    },
                    'source_bucket': eval_bucket,
                    'difficulty_tag': eval_bucket,
                    'intent_form': intent_form,
                    'surface_style': surface_style,
                }
            )
            label_rows.append(
                {
                    'id': sample_id,
                    'family_id': family_id,
                    'ground_truth_fqdn': primary_fqdn,
                    'acceptable_fqdns': acceptable_fqdns(primary_fqdn),
                    'relevant_fqdns': relevant,
                    'eval_bucket': eval_bucket,
                    'bucket_tags': bucket_tags,
                    'intent_form': intent_form,
                    'surface_style': surface_style,
                    'primary_granularity': primary_granularity(primary_fqdn),
                    'secondary_intent_present': bool(relevant),
                    'high_risk_case': high_risk_case,
                    'notes_for_audit': note,
                }
            )
            skeleton_rows.append(
                {
                    'id': sample_id,
                    'family_id': family_id,
                    'eval_bucket': eval_bucket,
                    'intent_form': intent_form,
                    'surface_style': surface_style,
                    'query_skeleton_id': query_skeleton_id,
                    'suspected_nearby_old_family': suspected_old,
                    'skeleton_overlap_flag': 'false',
                    'auditor_note': f'new template bank {query_skeleton_id}',
                }
            )

            base_counter[base] += 1
            bucket_counter[eval_bucket] += 1
            intent_counter[intent_form] += 1
            style_counter[surface_style] += 1
            skeleton_counter_by_bucket[eval_bucket][query_skeleton_id] += 1
            if primary_granularity(primary_fqdn) == 'segment':
                l3_counter[base] += 1
            if relevant:
                multi_intent_hits += 1
            if high_risk_case:
                high_risk_hits += 1
            if base_node:
                l1_counter[base_node.l1] += 1

            sample_index += 1

    for base in sorted(base_counter):
        node = resolver.get_node(base)
        bucket_summary = ';'.join(
            sorted({row['source_bucket'] for row in input_rows if row['metadata']['base_fqdn'] == base})
        )
        intent_summary = ';'.join(
            sorted({row['intent_form'] for row in input_rows if row['metadata']['base_fqdn'] == base})
        )
        style_summary = ';'.join(
            sorted({row['surface_style'] for row in input_rows if row['metadata']['base_fqdn'] == base})
        )
        coverage_rows.append(
            {
                'base_fqdn': base,
                'l1': node.l1 if node else '',
                'l2': node.l2 or '' if node else '',
                'sample_count': str(base_counter[base]),
                'l3_sample_count': str(l3_counter[base]),
                'eval_bucket_summary': bucket_summary,
                'intent_form_summary': intent_summary,
                'surface_style_summary': style_summary,
            }
        )

    total = len(label_rows)
    max_bucket_skeleton_share = max(
        max(counter.values()) / 80.0 for counter in skeleton_counter_by_bucket.values()
    )
    manifest = {
        'dataset_version': DATASET_VERSION,
        'namespace_version': NAMESPACE_VERSION,
        'status': 'unrevealed_seeded',
        'paths': {
            'input': str(INPUT_PATH.relative_to(ROOT)),
            'labels': str(LABEL_PATH.relative_to(ROOT)),
            'coverage_status': str(COVERAGE_PATH.relative_to(ROOT)),
            'skeleton_audit': str(SKELETON_AUDIT_PATH.relative_to(ROOT)),
        },
        'reveal_protocol': {
            'single_join': True,
            'development_may_read_input_only': True,
            'post_reveal_requires_version_bump': True,
        },
        'targets': {
            'total_samples': 400,
            'eval_bucket_counts': {bucket: 80 for bucket in EVAL_BUCKETS},
            'intent_form_counts': {form: 80 for form in INTENT_FORMS},
            'min_intent_forms_per_bucket': 4,
            'min_surface_styles_per_bucket': 4,
            'max_bucket_skeleton_share': 0.2,
            'min_distinct_base_fqdn': 25,
            'max_l1_ratio': 0.35,
            'multi_intent_ratio_range': [0.3, 0.45],
            'l3_ratio_min': 0.25,
            'skeleton_overlap_flag_count_max': 0,
        },
        'current_stats': {
            'total_samples': total,
            'distinct_base_fqdn': len(base_counter),
            'l3_ratio': round(sum(l3_counter.values()) / max(total, 1), 4),
            'multi_intent_ratio': round(multi_intent_hits / max(total, 1), 4),
            'high_risk_case_count': high_risk_hits,
            'eval_bucket_counts': dict(bucket_counter),
            'intent_form_counts': dict(intent_counter),
            'surface_style_counts': dict(style_counter),
            'l1_counts': dict(l1_counter),
            'max_l1_ratio': round(max(l1_counter.values()) / max(total, 1), 4),
            'max_bucket_skeleton_share': round(max_bucket_skeleton_share, 4),
            'skeleton_overlap_flag_count': 0,
            'ood_like_count': 0,
        },
        'family_disjoint_against': [
            'data/agentdns_routing/formal/dev.jsonl',
            'data/agentdns_routing/formal/blind_input.jsonl',
            'data/agentdns_routing/formal/challenge_input.jsonl',
            'data/agentdns_routing/formal/holdout2_input.jsonl',
        ],
        'provenance': {
            'spec': 'closure/27_holdout3_data_spec.md',
            'built_on': '2026-03-30',
        },
        'last_validation_report': 'artifacts/dataset/holdout3_validation_report.json',
    }
    return input_rows, label_rows, coverage_rows, skeleton_rows, manifest


def ensure_family_disjoint(label_rows: list[dict[str, Any]]) -> None:
    existing: set[str] = set()
    for path in OLD_LABEL_FILES:
        for row in load_jsonl(path):
            family_id = row.get('family_id')
            if family_id:
                existing.add(family_id)
    overlap = existing.intersection({row['family_id'] for row in label_rows})
    if overlap:
        raise ValueError(f'holdout3 family_id 与已揭盲 split 重叠: {sorted(overlap)}')


def ensure_query_disjoint(input_rows: list[dict[str, Any]]) -> None:
    existing_queries: set[str] = set()
    for path in OLD_INPUT_FILES:
        for row in load_jsonl(path):
            existing_queries.add(row['query'])
    overlap = existing_queries.intersection({row['query'] for row in input_rows})
    if overlap:
        raise ValueError('holdout3 query 与旧 split 存在完全重复文本')


def validate_targets(manifest: dict[str, Any], input_rows: list[dict[str, Any]], label_rows: list[dict[str, Any]], skeleton_rows: list[dict[str, str]]) -> None:
    stats = manifest['current_stats']
    if len(input_rows) != 400 or len(label_rows) != 400 or len(skeleton_rows) != 400:
        raise ValueError('holdout3 总量不为 400')
    if stats['distinct_base_fqdn'] < 25:
        raise ValueError(f'holdout3 base_fqdn 覆盖不足: {stats["distinct_base_fqdn"]} < 25')
    if stats['l3_ratio'] < 0.25:
        raise ValueError(f'holdout3 l3_ratio 过低: {stats["l3_ratio"]}')
    if not (0.3 <= stats['multi_intent_ratio'] <= 0.45):
        raise ValueError(f'holdout3 multi_intent_ratio 越界: {stats["multi_intent_ratio"]}')
    if stats['max_l1_ratio'] > 0.35:
        raise ValueError(f'holdout3 max_l1_ratio 越界: {stats["max_l1_ratio"]}')
    if stats['max_bucket_skeleton_share'] > 0.2:
        raise ValueError(f'holdout3 max_bucket_skeleton_share 越界: {stats["max_bucket_skeleton_share"]}')
    if any(value != 80 for value in stats['eval_bucket_counts'].values()):
        raise ValueError('holdout3 eval_bucket 配额未达到 80')
    if any(value != 80 for value in stats['intent_form_counts'].values()):
        raise ValueError('holdout3 intent_form 全局配额未达到 80')


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def dump_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    FORMAL_DIR.mkdir(parents=True, exist_ok=True)
    input_rows, label_rows, coverage_rows, skeleton_rows, manifest = build_rows()
    ensure_family_disjoint(label_rows)
    ensure_query_disjoint(input_rows)
    validate_targets(manifest, input_rows, label_rows, skeleton_rows)

    dump_jsonl(INPUT_PATH, input_rows)
    dump_jsonl(LABEL_PATH, label_rows)
    dump_csv(
        COVERAGE_PATH,
        coverage_rows,
        ['base_fqdn', 'l1', 'l2', 'sample_count', 'l3_sample_count', 'eval_bucket_summary', 'intent_form_summary', 'surface_style_summary'],
    )
    dump_csv(
        SKELETON_AUDIT_PATH,
        skeleton_rows,
        ['id', 'family_id', 'eval_bucket', 'intent_form', 'surface_style', 'query_skeleton_id', 'suspected_nearby_old_family', 'skeleton_overlap_flag', 'auditor_note'],
    )
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest['current_stats'], ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
