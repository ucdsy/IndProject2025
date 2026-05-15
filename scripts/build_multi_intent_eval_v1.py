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
DATA_PATH = FORMAL_DIR / 'multi_intent_eval_v1.jsonl'
MANIFEST_PATH = FORMAL_DIR / 'multi_intent_eval_v1_manifest.json'
COVERAGE_PATH = FORMAL_DIR / 'multi_intent_eval_v1_coverage.csv'

DATASET_VERSION = 'multi_intent_eval_v1_20260426'
NAMESPACE_VERSION = 'ns_v1_20260311'

TASK_NOTES = {
    'activity.travel.cn': '活动/景点安排被明确提出。',
    'budget.finance.cn': '预算、费用拆分或成本上限被明确提出。',
    'clinic.health.cn': '门诊、挂号或基础检查被明确提出。',
    'compliance.security.cn': '合规检查、审计或留痕要求被明确提出。',
    'coupon.commerce.cn': '优惠、折扣或优惠券查询被明确提出。',
    'course.education.cn': '课程、培训或学习路径被明确提出。',
    'docs.productivity.cn': '文档、材料、提纲或说明撰写被明确提出。',
    'fitness.health.cn': '训练、运动或健身计划被明确提出。',
    'flight.travel.cn': '航班或机票筛选被明确提出。',
    'fraud.security.cn': '反欺诈、异常识别或拦截规则被明确提出。',
    'hotel.travel.cn': '酒店、住宿或住处筛选被明确提出。',
    'invest.finance.cn': '理财、投资或资金配置被明确提出。',
    'invoice.finance.cn': '发票、票据、开票、验真或报销被明确提出。',
    'itinerary.travel.cn': '路线、行程或每日安排被明确提出。',
    'meeting.productivity.cn': '会议安排、纪要或行动项被明确提出。',
    'nutrition.health.cn': '饮食、营养或食谱调整被明确提出。',
    'permit.gov.cn': '许可、备案、审批或资质清单被明确提出。',
    'policy.gov.cn': '政策、规范、标准或依据检索被明确提出。',
    'price.commerce.cn': '价格、报价或比价被明确提出。',
    'restaurant.travel.cn': '餐厅、吃饭地点或餐饮安排被明确提出。',
    'risk.security.cn': '风险、风控或安全评估被明确提出。',
    'tax.finance.cn': '税务、税率或纳税处理被明确提出。',
    'transport.travel.cn': '交通、接驳或通勤方案被明确提出。',
    'tutoring.education.cn': '导师、辅导或答疑服务被明确提出。',
    'weather.cn': '天气、气温或降雨查询被明确提出。',
}


def spec(
    slug: str,
    golds: list[str],
    queries: list[str],
    domain_mix: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        'slug': slug,
        'golds': golds,
        'queries': queries,
        'domain_mix': domain_mix,
        'context': context,
    }


SINGLE_SPECS = [
    spec('weather_shanghai_rain', ['weather.cn'], ['明天上海会不会下雨，帮我看下气温和降雨窗口。'], 'travel_life', {'city': '上海'}),
    spec('meeting_review_schedule', ['meeting.productivity.cn'], ['帮我把下周项目评审会的时间和参会人约起来。'], 'enterprise_ops', {'meeting_type': '项目评审会'}),
    spec('docs_client_onepager', ['docs.productivity.cn'], ['把客户沟通会的材料压成一页说明，先给我一个结构。'], 'enterprise_ops', {'audience': '客户'}),
    spec('budget_onboarding', ['budget.finance.cn'], ['渠道 onboarding 活动先帮我拆一下预算和费用上限。'], 'finance_commerce', {'project': '渠道 onboarding'}),
    spec('invoice_verify_batch', ['invoice.finance.cn'], ['这批培训费票据先帮我验一下真伪和能不能用。'], 'finance_commerce', {'expense_type': '培训费'}),
    spec('tax_service_income', ['tax.finance.cn'], ['软件服务费进账前，先帮我看税务上该怎么处理。'], 'finance_commerce', {'revenue_type': '软件服务费'}),
    spec('price_ssd', ['price.commerce.cn'], ['便携 SSD 不同平台报价差很多，帮我先比个价。'], 'finance_commerce', {'product': '便携 SSD'}),
    spec('coupon_camera', ['coupon.commerce.cn'], ['想买运动相机，先帮我看看有没有券或折扣。'], 'finance_commerce', {'product': '运动相机'}),
    spec('nutrition_sugar', ['nutrition.health.cn'], ['最近想控糖，先给我一版饮食调整建议。'], 'health_education', {'goal': '控糖'}),
    spec('fitness_recovery', ['fitness.health.cn'], ['我想恢复运动，帮我排个起步训练计划。'], 'health_education', {'goal': '恢复运动'}),
    spec('clinic_checkup', ['clinic.health.cn'], ['想做一次基础检查，帮我看看普通门诊怎么约。'], 'health_education', {'goal': '基础检查'}),
    spec('course_sql', ['course.education.cn'], ['我想系统学 SQL 实战，先推荐一门能开始的课。'], 'health_education', {'goal': 'SQL 实战'}),
    spec('tutoring_purchase', ['tutoring.education.cn'], ['采购流程我总是卡住，帮我找个合适的辅导方式。'], 'health_education', {'goal': '采购流程'}),
    spec('itinerary_xian', ['itinerary.travel.cn'], ['清明想去西安三天，帮我把路线和每天安排排出来。'], 'travel_life', {'city': '西安'}),
    spec('hotel_beijing', ['hotel.travel.cn'], ['下周在北京只住一晚，帮我筛个离会场近的酒店。'], 'travel_life', {'city': '北京'}),
    spec('flight_shenzhen', ['flight.travel.cn'], ['下周要飞深圳做演示，帮我筛合适的航班。'], 'travel_life', {'city': '深圳'}),
    spec('restaurant_factory_visit', ['restaurant.travel.cn'], ['客户中午来工厂附近，帮我找个方便吃饭的地方。'], 'travel_life', {'city': '苏州'}),
    spec('transport_station', ['transport.travel.cn'], ['杭州东站到会场怎么接驳最省事，帮我看一下。'], 'travel_life', {'city': '杭州'}),
    spec('policy_data_api', ['policy.gov.cn'], ['工业数据接口上线前，帮我查一下适用的政策和标准。'], 'governance', {'service': '工业数据接口'}),
    spec('risk_external_portal', ['risk.security.cn'], ['外部报修入口准备开放，先帮我排一下主要风险点。'], 'governance', {'service': '外部报修入口'}),
]

DOUBLE_SPECS = [
    spec('yunnan_route_weather', ['itinerary.travel.cn', 'weather.cn'], ['下周去云南玩，帮我安排路线，再看看天气。', '云南五天行程还没定，先排路线，也帮我确认降雨情况。'], 'travel_life', {'city': '云南'}),
    spec('hotel_transport', ['hotel.travel.cn', 'transport.travel.cn'], ['北京开会只住一晚，帮我找酒店，也看看从酒店到会场怎么走。', '我下周到北京参会，住宿和接驳路线都帮我一起看。'], 'travel_life', {'city': '北京'}),
    spec('flight_weather', ['flight.travel.cn', 'weather.cn'], ['去深圳的航班帮我筛一下，顺便看下那几天天气会不会影响出行。', '下周飞深圳做演示，机票和天气窗口都帮我确认一下。'], 'travel_life', {'city': '深圳'}),
    spec('activity_restaurant', ['activity.travel.cn', 'restaurant.travel.cn'], ['西安多出半天时间，帮我找个活动，再安排一顿附近吃饭。', '周末在西安有空档，想看看玩什么，也找个不折腾的餐厅。'], 'travel_life', {'city': '西安'}),
    spec('restaurant_coupon', ['restaurant.travel.cn', 'coupon.commerce.cn'], ['客户中午要吃饭，帮我找餐厅，也看看有没有可用优惠。', '园区附近订餐先筛门店，再帮我找一下折扣或券。'], 'travel_life', {'city': '苏州'}),
    spec('budget_price', ['budget.finance.cn', 'price.commerce.cn'], ['设备巡检项目先做预算，也帮我比一下采购价格。', '驻场培训周要控成本，预算和关键物料报价都帮我拆出来。'], 'finance_commerce', {'project': '设备巡检'}),
    spec('invoice_tax', ['invoice.finance.cn', 'tax.finance.cn'], ['这批服务费票据要处理，也帮我看税务口径。', '年度支持服务既要补票，也要确认税务上怎么入账。'], 'finance_commerce', {'expense_type': '服务费'}),
    spec('price_coupon', ['price.commerce.cn', 'coupon.commerce.cn'], ['会议麦克风先帮我比价，再看看哪个平台有券。', '便携 SSD 想买得划算点，价格和优惠都查一下。'], 'finance_commerce', {'product': '会议麦克风'}),
    spec('invest_tax', ['invest.finance.cn', 'tax.finance.cn'], ['这笔闲钱想稳一点理财，也帮我看下收益相关税务影响。', '一年内不用的钱帮我做稳健配置，同时提醒税务上要注意什么。'], 'finance_commerce', {'horizon': '一年'}),
    spec('budget_invoice', ['budget.finance.cn', 'invoice.finance.cn'], ['客户培训活动先拆预算，再把后续票据处理路径列一下。', '这次巡检项目要先做费用上限，也把发票流转一起梳顺。'], 'finance_commerce', {'project': '客户培训'}),
    spec('meeting_docs', ['meeting.productivity.cn', 'docs.productivity.cn'], ['评审会时间帮我排一下，会前材料也给我列个提纲。', '下周同步会要约起来，同时准备一页会前说明。'], 'enterprise_ops', {'meeting_type': '评审会'}),
    spec('meeting_risk', ['meeting.productivity.cn', 'risk.security.cn'], ['上线评审会帮我安排，同时把会上需要先看的风险点列出来。', '我要约一次发布前评审，也请提前整理主要风险清单。'], 'enterprise_ops', {'meeting_type': '上线评审'}),
    spec('docs_policy', ['docs.productivity.cn', 'policy.gov.cn'], ['客户说明书先帮我搭结构，也补上相关政策依据。', '这份对外说明要写出来，同时把引用的规范标准查全。'], 'enterprise_ops', {'document': '客户说明书'}),
    spec('compliance_policy', ['compliance.security.cn', 'policy.gov.cn'], ['数据报表外发前先做合规检查，也查一下对应政策依据。', '合作方要看运营日志，合规点和相关标准都帮我过一遍。'], 'governance', {'service': '报表外发'}),
    spec('permit_policy', ['permit.gov.cn', 'policy.gov.cn'], ['园区服务小程序上线前，帮我列备案手续，也把政策依据找出来。', '短信核验能力要对外开，前置许可和相关规范都帮我确认。'], 'governance', {'service': '园区服务小程序'}),
    spec('risk_fraud', ['risk.security.cn', 'fraud.security.cn'], ['补贴活动上线前先看风险，也帮我列异常套利拦截点。', '返利订单担心被钻规则，整体风险和反欺诈规则都看一下。'], 'governance', {'campaign': '补贴活动'}),
    spec('compliance_risk', ['compliance.security.cn', 'risk.security.cn'], ['客户自助台开放前，合规留痕和风险点都帮我检查。', '外部下载口要开，先看合规要求，也排一遍高风险点。'], 'governance', {'service': '客户自助台'}),
    spec('fraud_compliance', ['fraud.security.cn', 'compliance.security.cn'], ['优惠券活动要防刷，也帮我确认拦截规则是否满足合规留痕。', '积分换购担心作弊，反欺诈和审计记录都帮我看一下。'], 'governance', {'campaign': '优惠券活动'}),
    spec('course_tutoring', ['course.education.cn', 'tutoring.education.cn'], ['想补采购流程，先推荐课程，也帮我找个能答疑的辅导方式。', 'SQL 实战我想系统学，课程和导师答疑都帮我看看。'], 'health_education', {'goal': '采购流程'}),
    spec('nutrition_fitness', ['nutrition.health.cn', 'fitness.health.cn'], ['最近想减脂，饮食方案和起步训练都帮我排一下。', '控糖这件事先从吃和运动两块给我一个计划。'], 'health_education', {'goal': '减脂'}),
    spec('clinic_nutrition', ['clinic.health.cn', 'nutrition.health.cn'], ['想做基础检查，也请顺手给一版饮食调整建议。', '控糖前我想先约门诊，再看看饮食怎么改。'], 'health_education', {'goal': '控糖'}),
    spec('clinic_fitness', ['clinic.health.cn', 'fitness.health.cn'], ['恢复运动前想先做检查，再帮我排个训练起步计划。', '膝盖不太舒服，先看门诊怎么约，也给我一个保守训练安排。'], 'health_education', {'goal': '恢复运动'}),
    spec('activity_transport', ['activity.travel.cn', 'transport.travel.cn'], ['杭州多出半天空档，帮我找活动，也看看怎么过去最省事。', '展会结束后想临时加个景点，活动和接驳一起帮我看。'], 'travel_life', {'city': '杭州'}),
    spec('hotel_weather', ['hotel.travel.cn', 'weather.cn'], ['周末去上海住一晚，酒店和天气都帮我看一下。', '成都出差想订住处，也确认那几天会不会下雨。'], 'travel_life', {'city': '上海'}),
    spec('flight_transport', ['flight.travel.cn', 'transport.travel.cn'], ['去广州的航班先筛一下，落地后到园区的接驳也帮我看。', '我下周飞杭州，机票和高铁站到酒店的交通都帮我安排。'], 'travel_life', {'city': '广州'}),
    spec('tax_policy', ['tax.finance.cn', 'policy.gov.cn'], ['设备补贴收入要入账，帮我看税务处理，也查一下政策依据。', '服务费税务口径不确定，税务和对应规范都帮我确认。'], 'governance', {'topic': '税务政策'}),
    spec('permit_risk', ['permit.gov.cn', 'risk.security.cn'], ['对外通知接口要上线，先列备案手续，再排一遍风险点。', '合作方下载入口准备开放，许可动作和风险边界都帮我看。'], 'governance', {'service': '对外通知接口'}),
    spec('course_docs', ['course.education.cn', 'docs.productivity.cn'], ['给新人做采购培训，课程路径和一页学习材料都帮我准备。', 'SQL 入门培训要开始，先推荐课程，也整理一份学习说明。'], 'enterprise_ops', {'training': '新人培训'}),
    spec('tutoring_meeting', ['tutoring.education.cn', 'meeting.productivity.cn'], ['导师答疑要约起来，顺便帮我安排一次小组辅导会。', '采购流程带练想找老师，也帮我把答疑会时间排好。'], 'health_education', {'goal': '答疑'}),
    spec('docs_invoice', ['docs.productivity.cn', 'invoice.finance.cn'], ['报销规则要写成一页说明，也把票据处理步骤梳一下。', '给销售同事的开票说明先写出来，再列出发票流转流程。'], 'enterprise_ops', {'document': '报销说明'}),
]

TRIPLE_SPECS = [
    spec('travel_plan_hotel_weather', ['itinerary.travel.cn', 'hotel.travel.cn', 'weather.cn'], ['下周去云南玩，路线、天气和合适酒店都帮我看一下。', '云南五天行程帮我排好，同时确认天气并筛住宿。'], 'travel_life', {'city': '云南'}),
    spec('travel_flight_hotel_itinerary', ['flight.travel.cn', 'hotel.travel.cn', 'itinerary.travel.cn'], ['去成都培训，机票、酒店和两天路线都帮我安排。', '成都这趟先筛航班，再找住处，并把每天安排排出来。'], 'travel_life', {'city': '成都'}),
    spec('travel_activity_restaurant_transport', ['activity.travel.cn', 'restaurant.travel.cn', 'transport.travel.cn'], ['西安半天空档想安排活动、吃饭和接驳路线。', '展会结束后想去逛一下，景点、餐厅和交通都帮我看。'], 'travel_life', {'city': '西安'}),
    spec('travel_flight_weather_transport', ['flight.travel.cn', 'weather.cn', 'transport.travel.cn'], ['下周飞深圳，航班、天气和落地接驳都帮我确认。', '深圳演示这趟先看机票，再看天气，最后安排到客户现场的交通。'], 'travel_life', {'city': '深圳'}),
    spec('finance_budget_price_invoice', ['budget.finance.cn', 'price.commerce.cn', 'invoice.finance.cn'], ['设备采购要控成本，预算、报价和后续发票处理都帮我梳理。', '巡检项目先拆预算，比一遍关键设备价格，再列票据流程。'], 'finance_commerce', {'project': '设备采购'}),
    spec('finance_invoice_tax_compliance', ['invoice.finance.cn', 'tax.finance.cn', 'compliance.security.cn'], ['年度服务费要补票、确认税务口径，并检查合规留痕。', '这批企业服务收入先看发票，再看税务，同时补审计检查。'], 'governance', {'revenue_type': '服务费'}),
    spec('gov_permit_policy_compliance', ['permit.gov.cn', 'policy.gov.cn', 'compliance.security.cn'], ['短信核验能力上线前，备案手续、政策依据和合规检查都要列清。', '园区服务小程序对外开，许可、规范和审计留痕都帮我过一遍。'], 'governance', {'service': '短信核验'}),
    spec('security_risk_fraud_compliance', ['risk.security.cn', 'fraud.security.cn', 'compliance.security.cn'], ['返利活动上线前，整体风险、反欺诈拦截和合规留痕都帮我看。', '积分换购担心被刷，风控、异常识别和审计要求都列一下。'], 'governance', {'campaign': '返利活动'}),
    spec('work_meeting_docs_compliance', ['meeting.productivity.cn', 'docs.productivity.cn', 'compliance.security.cn'], ['外部合作评审会要约起来，材料要准备，合规检查也要补上。', '下周客户评审先排会议，再写一页说明，并列出合规注意点。'], 'enterprise_ops', {'meeting_type': '客户评审'}),
    spec('work_meeting_docs_policy', ['meeting.productivity.cn', 'docs.productivity.cn', 'policy.gov.cn'], ['政策解读会帮我安排，同时准备材料，并把相关规范找全。', '我要开一次标准宣贯会，会议、讲义和政策依据一起准备。'], 'enterprise_ops', {'meeting_type': '政策解读会'}),
    spec('health_nutrition_fitness_clinic', ['nutrition.health.cn', 'fitness.health.cn', 'clinic.health.cn'], ['我想控糖，饮食、训练和门诊检查怎么安排都帮我看。', '减脂前先看门诊怎么约，再给饮食和训练计划。'], 'health_education', {'goal': '控糖'}),
    spec('education_course_tutoring_docs', ['course.education.cn', 'tutoring.education.cn', 'docs.productivity.cn'], ['新人采购培训需要课程、导师答疑和一页学习材料。', 'SQL 实战训练营先定课程，再找辅导方式，并整理学习说明。'], 'health_education', {'training': '新人培训'}),
    spec('invest_tax_risk', ['invest.finance.cn', 'tax.finance.cn', 'risk.security.cn'], ['这笔钱想做稳健理财，也看税务影响和风险点。', '半年不用的闲钱帮我配置一下，同时提醒收益税务和风险。'], 'finance_commerce', {'horizon': '半年'}),
    spec('commerce_restaurant_coupon_price', ['restaurant.travel.cn', 'coupon.commerce.cn', 'price.commerce.cn'], ['团建午餐先找餐厅，再看优惠券和人均价格。', '客户招待想订餐，门店、折扣和报价都帮我比一下。'], 'finance_commerce', {'event': '团建午餐'}),
    spec('travel_hotel_weather_transport', ['hotel.travel.cn', 'weather.cn', 'transport.travel.cn'], ['上海出差住处、天气和到会场交通都帮我确认。', '成都培训那几天酒店、降雨和接驳路线一起看。'], 'travel_life', {'city': '上海'}),
    spec('ops_budget_meeting_docs', ['budget.finance.cn', 'meeting.productivity.cn', 'docs.productivity.cn'], ['项目复盘会要排期，预算差异和复盘材料也一起准备。', '下周要开成本复盘，会议、预算拆解和一页材料都帮我弄好。'], 'enterprise_ops', {'meeting_type': '成本复盘'}),
]

FOUR_PLUS_SPECS = [
    spec('full_travel_bundle', ['itinerary.travel.cn', 'flight.travel.cn', 'hotel.travel.cn', 'weather.cn'], ['下周去云南玩，帮我看航班、排路线、找酒店，再确认天气。'], 'travel_life', {'city': '云南'}),
    spec('travel_day_bundle', ['itinerary.travel.cn', 'activity.travel.cn', 'restaurant.travel.cn', 'transport.travel.cn'], ['杭州一天空档帮我安排路线、景点、吃饭地点和接驳交通。'], 'travel_life', {'city': '杭州'}),
    spec('launch_governance_bundle', ['permit.gov.cn', 'policy.gov.cn', 'compliance.security.cn', 'risk.security.cn'], ['合作方下载入口要上线，备案手续、政策依据、合规留痕和风险点都帮我列清。'], 'governance', {'service': '合作方下载入口'}),
    spec('procurement_bundle', ['budget.finance.cn', 'price.commerce.cn', 'coupon.commerce.cn', 'invoice.finance.cn'], ['会议设备采购先拆预算、比价格、找优惠，再列发票处理步骤。'], 'finance_commerce', {'project': '会议设备采购'}),
    spec('finance_governance_bundle', ['invoice.finance.cn', 'tax.finance.cn', 'compliance.security.cn', 'policy.gov.cn'], ['企业服务收入要补票、确认税务、做合规检查，并查相关政策依据。'], 'governance', {'revenue_type': '企业服务收入'}),
    spec('review_packet_bundle', ['meeting.productivity.cn', 'docs.productivity.cn', 'risk.security.cn', 'compliance.security.cn'], ['上线评审会帮我排期，准备材料，同时列风险点和合规检查项。'], 'enterprise_ops', {'meeting_type': '上线评审'}),
    spec('health_program_bundle', ['nutrition.health.cn', 'fitness.health.cn', 'clinic.health.cn', 'course.education.cn'], ['控糖这件事帮我安排门诊、饮食、训练，再推荐一门入门课程。'], 'health_education', {'goal': '控糖'}),
    spec('training_bundle', ['course.education.cn', 'tutoring.education.cn', 'meeting.productivity.cn', 'docs.productivity.cn'], ['新人培训要选课程、找辅导老师、安排答疑会，并准备一页学习材料。'], 'enterprise_ops', {'training': '新人培训'}),
]


def intent_bucket(intent_count: int) -> str:
    if intent_count == 1:
        return 'single'
    if intent_count == 2:
        return 'double'
    if intent_count == 3:
        return 'triple'
    return 'four_plus'


def intent_notes(golds: list[str]) -> str:
    return ' '.join(TASK_NOTES[fqdn] for fqdn in golds)


def iter_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    specs.extend(SINGLE_SPECS)
    specs.extend(DOUBLE_SPECS)
    specs.extend(TRIPLE_SPECS)
    specs.extend(FOUR_PLUS_SPECS)
    return specs


def build_rows(resolver: NamespaceResolver) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample_index = 1
    for item in iter_specs():
        for query_index, query in enumerate(item['queries'], start=1):
            golds = item['golds']
            for fqdn in golds:
                if not resolver.has_fqdn(fqdn):
                    raise ValueError(f'Unknown gold fqdn: {fqdn}')
            if len(set(golds)) != len(golds):
                raise ValueError(f'Duplicate gold fqdn in {item["slug"]}: {golds}')
            sample_id = f'multi_intent_eval_v1_{sample_index:06d}'
            family_id = f'multi_intent_eval_v1_{item["slug"]}_{query_index:06d}_f01'
            rows.append(
                {
                    'id': sample_id,
                    'family_id': family_id,
                    'dataset_version': DATASET_VERSION,
                    'namespace_version': NAMESPACE_VERSION,
                    'query': query,
                    'gold_intent_fqdns': golds,
                    'intent_count': len(golds),
                    'intent_count_bucket': intent_bucket(len(golds)),
                    'domain_mix': item['domain_mix'],
                    'context': item['context'],
                    'intent_notes': intent_notes(golds),
                }
            )
            sample_index += 1

    if len(rows) != 120:
        raise ValueError(f'Expected 120 samples, got {len(rows)}')
    if len({row['query'] for row in rows}) != len(rows):
        raise ValueError('Duplicate query text in multi-intent eval v1')
    if len({row['family_id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate family_id in multi-intent eval v1')
    return rows


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


def coverage_rows(resolver: NamespaceResolver, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ['fqdn', 'l1', 'l2', 'gold_mention_count', 'intent_count_buckets', 'domain_mixes']
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(path: Path, stats: dict[str, Any]) -> None:
    manifest = {
        'dataset_name': 'multi_intent_eval_v1',
        'dataset_version': DATASET_VERSION,
        'namespace_version': NAMESPACE_VERSION,
        'created_date': '2026-04-26',
        'purpose': 'Independent set-valued routing evaluation for queries containing one or more explicit executable intents.',
        'frozen_main_collection_unchanged': True,
        'files': {
            'data': str(DATA_PATH.relative_to(ROOT)),
            'schema': 'schemas/multi_intent_eval_sample.schema.json',
            'coverage': str(COVERAGE_PATH.relative_to(ROOT)),
        },
        'evaluation_metrics': ['Exact Set Accuracy', 'Set Precision', 'Set Recall', 'Set F1'],
        'labeling_principles': [
            'gold_intent_fqdns contains all explicitly requested executable capability FQDNs.',
            'No primary/related distinction is imposed in this dataset.',
            'Only explicit or strongly required intents are labeled.',
            'Every gold FQDN must exist in the current namespace catalog.',
        ],
        'stats': stats,
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    FORMAL_DIR.mkdir(parents=True, exist_ok=True)
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    rows = build_rows(resolver)
    stats = compute_stats(resolver, rows)
    write_jsonl(DATA_PATH, rows)
    write_csv(COVERAGE_PATH, coverage_rows(resolver, rows))
    write_manifest(MANIFEST_PATH, stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
