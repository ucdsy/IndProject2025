from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agentdns_routing.namespace import NamespaceResolver, load_jsonl

FORMAL_DIR = ROOT / 'data' / 'agentdns_routing' / 'formal'
DESCRIPTOR_PATH = ROOT / 'data' / 'agentdns_routing' / 'namespace_descriptors.jsonl'
COVERAGE_PLAN_PATH = FORMAL_DIR / 'coverage_plan.csv'
MANIFEST_PATH = FORMAL_DIR / 'manifest.json'


def s(scene: str, **context: Any) -> dict[str, Any]:
    return {"scene": scene, "context": context}


CONFUSION_CN = {
    'multi_intent': '多意图',
    'lexical_overlap': '词面重叠',
    'sibling_competition': '兄弟竞争',
    'governance_fallback': '治理回落',
    'cross_domain_overlap': '跨域重叠',
    'fallback': '粒度回落',
}

SCENE_SENTENCE_PATTERNS = {
    'dev': [
        '我们正在推进“{scene}”。',
        '现在要处理的事情是“{scene}”。',
        '当前这件事是“{scene}”。',
        '这次先落到“{scene}”上。',
        '眼下在处理“{scene}”。',
        '手头先推进“{scene}”。',
    ],
    'blind': [
        '“{scene}”准备落地。',
        '接下来要推进“{scene}”。',
        '围绕“{scene}”，先做前置梳理。',
        '先把“{scene}”这件事往前推。',
        '现在先处理“{scene}”。',
        '这一步先落到“{scene}”上。',
    ],
    'challenge': [
        '如果接下来要推进“{scene}”，我最想先弄清楚的是：{main}。',
        '围绕“{scene}”，当前最想先确认的是：{main}。',
        '真要把“{scene}”往下推，先得回答这个问题：{main}。',
        '“{scene}”如果真要继续，最先得想清楚的是：{main}。',
        '要把“{scene}”真正做下去，第一步得先搞清：{main}。',
        '围绕“{scene}”这件事，我会先追问一句：{main}。',
    ],
}

MAIN_SENTENCE_PATTERNS = {
    'dev': [
        '请先{main}。',
        '麻烦先{main}。',
        '想先请你{main}。',
    ],
    'blind': [
        '先{main}。',
        '优先{main}。',
        '先处理这一步：{main}。',
    ],
}

SCENE_STRIP_PREFIXES = (
    '梳理', '排查', '看清', '整理', '核对', '压缩', '压一遍', '比较',
)

MAIN_STRIP_PREFIXES = (
    '先帮我', '请先', '先请你', '先让我', '麻烦先', '最该先补的', '最先该', '真正要', '真要', '围绕', '先',
)

SECONDARY_STRIP_PREFIXES = (
    '另外', '再', '顺便', '顺手', '同时', '也',
)

BLUEPRINTS: dict[str, dict[str, Any]] = {
    'permit.gov.cn': {
        '对象': '准入手续',
        '主动作': '许可备案',
        '高风险': False,
        'subjects_miit': [
            s('把企业短信验证码接口正式商用', industry='enterprise_service', service='sms-api'),
            s('上线工业互联网平台的短信告警能力', industry='manufacturing', service='sms-alert'),
            s('开放面向企业客户的云通信通知接口', industry='enterprise_service', service='cloud-message'),
            s('把设备远程运维通知服务投入商用', industry='manufacturing', service='device-notify'),
            s('让园区企业服务平台支持短信核验', industry='enterprise_service', service='verification-message'),
            s('把工业设备状态告警接口对外开放', industry='manufacturing', service='device-alert-api'),
        ],
        'subjects_non': [],
        'main_dev': ['梳理需要补哪些资质和备案', '列清前置许可和报备事项'],
        'main_blind': ['把前置手续和办理顺序理一遍', '看清商用前还缺哪些准入动作'],
        'main_challenge': ['跟准入手续有关的前置动作还有哪些没补齐', '正式上线前必须先过的许可事项还差什么'],
        'secondary_options': [
            {'text': '再把对应依据列一下', 'relevant': 'policy.gov.cn', 'confusions': ['lexical_overlap']},
            {'text': '顺便整理成办理清单', 'relevant': None, 'confusions': ['governance_fallback']},
        ],
        'single_confusions': ['lexical_overlap', 'governance_fallback'],
    },
    'policy.gov.cn': {
        '对象': '政策规范',
        '主动作': '政策检索',
        '高风险': False,
        'subjects_miit': [
            s('梳理工业互联网平台的数据接口要求', industry='manufacturing'),
            s('排查企业短信服务的工信相关规范', industry='enterprise_service'),
            s('看清设备远程运维接口的行业标准', industry='manufacturing'),
            s('整理云通信平台适用的标准条线', industry='enterprise_service'),
            s('核对工业软件服务上线前的规范要求', industry='manufacturing'),
            s('查一遍企业通知接口的政策边界', industry='enterprise_service'),
        ],
        'subjects_non': [],
        'main_dev': ['梳理适用的政策、标准和条款', '先把相关规范要求查清楚'],
        'main_blind': ['先把政策条线和标准要求过一遍', '先看清适用的规范边界'],
        'main_challenge': ['围绕它真正卡人的规范要求到底有哪些', '真正要落地时先得看清哪些条线'],
        'secondary_options': [
            {'text': '再看看是否会牵出备案动作', 'relevant': 'permit.gov.cn', 'confusions': ['lexical_overlap']},
            {'text': '顺便列个检查提纲', 'relevant': None, 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['lexical_overlap'],
    },
    'compliance.security.cn': {
        '对象': '合规检查',
        '主动作': '合规审查',
        '高风险': True,
        'subjects_miit': [
            s('处理工业设备运行日志并接入外部分析平台', industry='manufacturing', destination='overseas_cloud'),
            s('对企业客户账号体系做实名和权限治理', industry='enterprise_service'),
            s('给供应商付款前做对象合规核验', industry='enterprise_service'),
            s('把设备侧采集数据汇总到外部云分析', industry='manufacturing', destination='overseas_cloud'),
            s('升级企业账号权限和实名流程', industry='enterprise_service'),
            s('做一轮供应商名单筛查和留档', industry='enterprise_service'),
        ],
        'subjects_non': [
            s('整理用户账号和隐私设置', industry='consumer_service'),
            s('核对交易对象名单', industry='consumer_service'),
        ],
        'main_dev': ['先把合规检查项过一遍', '先做一轮合规梳理'],
        'main_blind': ['先把合规边界和留痕要求理清', '先过一遍合规项和审计点'],
        'main_challenge': ['哪些前置检查和留痕动作不能省', '真要推进前最容易漏掉的合规动作是什么'],
        'secondary_options': [
            {'text': '再补风险关注点', 'relevant': 'risk.security.cn', 'confusions': ['governance_fallback']},
            {'text': '顺便整理留档要点', 'relevant': None, 'confusions': ['governance_fallback']},
        ],
        'single_confusions': ['governance_fallback'],
        'segments': {
            'data': {
                '对象': '数据出境与留存',
                '主动作': '数据合规检查',
                'main_dev': ['先做一轮数据出境合规检查', '先核对数据留存和出境要求'],
                'main_blind': ['先把数据合规这块过一遍', '先理清数据出境前的检查项'],
                'main_challenge': ['哪些和数据出境直接相关的动作最不能漏', '数据真正要流出去前先得补哪些检查'],
            },
            'account': {
                '对象': '账号实名与权限',
                '主动作': '账号合规检查',
                'main_dev': ['先把账号实名、权限和留痕要求过一遍', '先核对账号合规项'],
                'main_blind': ['先把账号这块的合规要求理清', '先过一遍实名和权限方面的检查项'],
                'main_challenge': ['围绕账号这块最容易漏掉的治理动作是什么', '真正上线前账号合规先从哪块补起'],
            },
            'transaction': {
                '对象': '交易对象核验',
                '主动作': '交易对象合规检查',
                'main_dev': ['先把交易对象合规风险过一遍', '先做一轮付款对象合规核验'],
                'main_blind': ['先理清交易对象这块的合规要求', '先过一遍对象核验和留档动作'],
                'main_challenge': ['围绕付款对象最该先补的审查动作是什么', '真要付款前对象核验先得查哪几项'],
            },
        },
    },
    'risk.security.cn': {
        '对象': '风险检查',
        '主动作': '风险评估',
        '高风险': True,
        'subjects_miit': [
            s('工业设备远程运维接口准备上线', industry='manufacturing'),
            s('企业短信通知服务准备开放给客户', industry='enterprise_service'),
            s('把设备日志接入外部分析系统', industry='manufacturing'),
            s('供应商付款流程准备接到平台里', industry='enterprise_service'),
            s('工业软件订阅服务准备商用', industry='manufacturing'),
            s('园区企业服务平台要接实名校验', industry='enterprise_service'),
        ],
        'subjects_non': [
            s('做一轮账号安全检查', industry='consumer_service'),
            s('评估线上支付环节风险', industry='consumer_service'),
        ],
        'main_dev': ['先做一版风险评估', '先把风控检查项过一遍'],
        'main_blind': ['先把风险点理一遍', '先看清上线前的风控项'],
        'main_challenge': ['最该先补的风险检查动作是什么', '真正动起来前，风险这块先卡哪几项'],
        'secondary_options': [
            {'text': '再看看是否会牵出数据合规问题', 'relevant': 'data.compliance.security.cn', 'confusions': ['governance_fallback']},
            {'text': '顺便给出留档清单', 'relevant': None, 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['governance_fallback'],
    },
    'fraud.security.cn': {
        '对象': '反欺诈',
        '主动作': '异常识别',
        '高风险': True,
        'subjects_miit': [
            s('企业采购支付流程接入新供应商', industry='enterprise_service'),
            s('工业配件线上下单流程准备开放', industry='manufacturing'),
        ],
        'subjects_non': [
            s('核对线上付款订单里的异常行为', industry='consumer_service'),
            s('检查促销订单里有没有异常交易', industry='consumer_service'),
            s('看一遍支付环节的欺诈迹象', industry='consumer_service'),
        ],
        'main_dev': ['先做一轮反欺诈检查', '先识别一下异常交易迹象'],
        'main_blind': ['先把反欺诈这块过一遍', '先看一遍异常风险点'],
        'main_challenge': ['哪些异常迹象最该优先拦住', '真要放量前最容易漏掉的欺诈风险是什么'],
        'secondary_options': [
            {'text': '再补一份风险关注点', 'relevant': 'risk.security.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'invoice.finance.cn': {
        '对象': '发票处理',
        '主动作': '发票处理',
        '高风险': False,
        'subjects_miit': [
            s('整理企业服务费票据', industry='enterprise_service', channel='erp'),
            s('处理工业软件订阅服务的发票', industry='manufacturing'),
            s('核对差旅和住宿票据', industry='enterprise_service'),
            s('整理客户预付款对应的票据', industry='enterprise_service'),
            s('核对设备采购相关票据', industry='manufacturing'),
            s('处理 SaaS 合同后的发票流转', industry='enterprise_service'),
        ],
        'subjects_non': [
            s('整理日常消费票据', channel='app'),
            s('看看几张电子票据', channel='app'),
        ],
        'main_dev': ['先把发票处理流程过一遍', '先看一遍票据处理口径'],
        'main_blind': ['先把票据处理这块理清', '先看清发票相关动作该怎么走'],
        'main_challenge': ['跟票据处理直接相关的动作先该补哪块', '真要往下走前，发票这块最容易漏掉什么'],
        'secondary_options': [
            {'text': '再补税务字段提醒', 'relevant': 'tax.finance.cn', 'confusions': ['cross_domain_overlap']},
            {'text': '顺便整理入账口径', 'relevant': None, 'confusions': ['fallback']},
        ],
        'single_confusions': ['sibling_competition', 'fallback'],
        'segments': {
            'issue': {
                '对象': '开票动作',
                '主动作': '发票开具',
                'main_dev': ['先把开电子发票这件事做对', '先列清开票所需字段和动作'],
                'main_blind': ['先确认开票动作本身怎么走', '先把开票这块理清'],
                'main_challenge': ['真正要把票开出来，先得把哪几件事捋顺', '开票前最容易漏掉的字段和动作是什么'],
            },
            'verify': {
                '对象': '发票验真',
                '主动作': '验真查验',
                'main_dev': ['先把这批发票验真', '先核对票据真伪和有效性'],
                'main_blind': ['先确认这批票据靠不靠谱', '先把验真这块做一遍'],
                'main_challenge': ['真要往下入账前，票据真伪这关先怎么卡', '和票据真伪直接相关的动作最该先补哪块'],
            },
            'reimburse': {
                '对象': '报销入账',
                '主动作': '报销判断',
                'main_dev': ['先判断哪些票据能直接走报销', '先按报销口径把票据分出来'],
                'main_blind': ['先理清这批票据怎么按报销口径走', '先看哪些能直接入账报销'],
                'main_challenge': ['真要往报销流程里放，哪类票最容易卡住', '和报销入账直接相关的判断先得做哪步'],
            },
        },
    },
    'tax.finance.cn': {
        '对象': '税务处理',
        '主动作': '税务判断',
        '高风险': False,
        'subjects_miit': [
            s('工业软件订阅服务签约后准备计费', industry='enterprise_service'),
            s('企业客户续费后要补票和入账', industry='enterprise_service'),
            s('设备采购服务要走税务处理', industry='manufacturing'),
            s('云通信接口对外收费后要补票据', industry='enterprise_service'),
            s('工业平台服务费准备结算', industry='manufacturing'),
            s('企业 SaaS 服务准备做收入确认', industry='enterprise_service'),
        ],
        'subjects_non': [
            s('整理一笔消费类服务费', industry='consumer_service')],
        'main_dev': ['先看税率和税务口径怎么处理', '先把税务处理规则理一遍'],
        'main_blind': ['先把税务口径过一遍', '先确认税率和税务处理怎么走'],
        'main_challenge': ['真正要入账前，税务这块先该看清什么', '跟税务处理直接相关的关键口径有哪些'],
        'secondary_options': [
            {'text': '再把开票字段列一下', 'relevant': 'issue.invoice.finance.cn', 'confusions': ['cross_domain_overlap']},
            {'text': '顺便整理入账提醒', 'relevant': None, 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'budget.finance.cn': {
        '对象': '预算测算',
        '主动作': '预算规划',
        '高风险': False,
        'subjects_miit': [
            s('给企业短信接口做年度费用规划', industry='enterprise_service'),
            s('测算工业设备运维平台的预算', industry='manufacturing'),
        ],
        'subjects_non': [],
        'main_dev': ['先做一版预算测算', '先把成本预算拆开'],
        'main_blind': ['先把预算口径理清', '先看费用规划该怎么拆'],
        'main_challenge': ['真要推进前，预算这块先得补哪几项', '跟费用规划直接相关的口径先该看清什么'],
        'secondary_options': [
            {'text': '再补采购价格参考', 'relevant': 'price.commerce.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'invest.finance.cn': {
        '对象': '投资理财',
        '主动作': '投资判断',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('梳理一笔闲钱的理财方向', industry='consumer_service')
        ],
        'main_dev': ['先看下投资组合怎么配', '先做一版理财方向判断'],
        'main_blind': ['先把投资方向理一遍', '先看看这笔钱怎么放更合适'],
        'main_challenge': ['真正要配资产前，先该把哪些判断做清楚', '围绕这笔钱最该先想清楚的理财问题是什么'],
        'secondary_options': [
            {'text': '再补一份风险提示', 'relevant': 'risk.security.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'meeting.productivity.cn': {
        '对象': '会议处理',
        '主动作': '会议协同',
        '高风险': False,
        'subjects_miit': [
            s('安排和集成商的接口评审会', industry='manufacturing', time_window='next_week'),
            s('整理设备联调周会', industry='manufacturing'),
            s('给企业客户准备项目例会', industry='enterprise_service', time_window='tomorrow'),
            s('安排工业平台上线前的评审会', industry='manufacturing', time_window='this_week'),
            s('整理和供应商的周例会', industry='enterprise_service'),
            s('筹备一次实施复盘会', industry='enterprise_service', time_window='next_week'),
        ],
        'subjects_non': [
            s('安排一次朋友聚会讨论', time_window='weekend')
        ],
        'main_dev': ['先把会议这件事安排妥', '先把会务和会后输出理清'],
        'main_blind': ['先把会议协同这块过一遍', '先看会议相关动作怎么落'],
        'main_challenge': ['真正要把会开起来，最该先补的动作是什么', '围绕这场会先该理清哪些具体动作'],
        'secondary_options': [
            {'text': '再补会议材料提纲', 'relevant': 'docs.productivity.cn', 'confusions': ['cross_domain_overlap']},
            {'text': '顺手列个后续待办', 'relevant': 'action-items.meeting.productivity.cn', 'confusions': ['sibling_competition']},
        ],
        'single_confusions': ['sibling_competition'],
        'segments': {
            'schedule': {
                '对象': '会议安排',
                '主动作': '会议排期',
                'main_dev': ['先把会议排期和时间敲定', '先安排好会议时间和会场'],
                'main_blind': ['先把会议怎么约起来理清', '先把排期这件事办妥'],
                'main_challenge': ['真要把会约起来，先得补哪几个动作', '围绕排期这件事最先该确定什么'],
            },
            'summary': {
                '对象': '会议纪要',
                '主动作': '纪要总结',
                'main_dev': ['先把会议纪要和要点整理出来', '先压出三条会议要点'],
                'main_blind': ['先把会后重点梳理出来', '先把这场会的纪要做出来'],
                'main_challenge': ['真要给别人快速看懂，这场会先该怎么压缩重点', '会后最该先沉淀出来的要点是什么'],
            },
            'action-items': {
                '对象': '行动项',
                '主动作': '待办提取',
                'main_dev': ['先把会后的待办和责任项拉出来', '先整理后续行动项'],
                'main_blind': ['先把会后要跟的任务列出来', '先看清后续谁做什么'],
                'main_challenge': ['真要让事情往前走，先得把哪些行动项钉住', '会后最该先落下来的任务清单是什么'],
            },
        },
    },
    'docs.productivity.cn': {
        '对象': '文档整理',
        '主动作': '方案提炼',
        '高风险': False,
        'subjects_miit': [
            s('整理工业设备接入方案', industry='manufacturing'),
            s('压缩企业短信平台技术方案', industry='enterprise_service'),
            s('梳理工业软件实施说明', industry='manufacturing'),
            s('整理园区企业服务平台材料', industry='enterprise_service'),
            s('压一遍设备远程运维方案', industry='manufacturing'),
            s('把供应商交付说明整理成提纲', industry='enterprise_service'),
            s('梳理平台对外接口说明', industry='manufacturing'),
        ],
        'subjects_non': [
            s('把一份旅游攻略整理成提纲', industry='consumer_service')
        ],
        'main_dev': ['先把文档提纲和摘要整理出来', '先压成一页可看的材料'],
        'main_blind': ['先把材料结构和重点梳理一遍', '先把这份方案压缩成提纲'],
        'main_challenge': ['真要让别人快速看懂，先该把哪些结构压出来', '围绕这份材料最先该沉淀的提纲是什么'],
        'secondary_options': [
            {'text': '再补三条主要风险', 'relevant': 'risk.security.cn', 'confusions': ['cross_domain_overlap']},
            {'text': '顺手列个执行清单', 'relevant': None, 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'price.commerce.cn': {
        '对象': '价格比较',
        '主动作': '比价',
        '高风险': False,
        'subjects_miit': [
            s('给企业采购一批 27 寸显示器', industry='enterprise_service'),
            s('比较工业采集网关的采购报价', industry='manufacturing'),
        ],
        'subjects_non': [
            s('买个 27 寸显示器', channel='ecommerce'),
            s('挑一台家用空气炸锅', channel='ecommerce'),
            s('选一副降噪耳机', channel='ecommerce'),
            s('看看几家平台的手机报价', channel='ecommerce'),
        ],
        'main_dev': ['先帮我比一下不同渠道的价格', '先把报价差异拉出来看看'],
        'main_blind': ['先把价格区间和渠道差异理一遍', '先看清哪边更划算'],
        'main_challenge': ['真正下单前，价格这块最该先摸清什么', '围绕采购成本先该看明白哪些差异'],
        'secondary_options': [
            {'text': '再顺手看看有没有能用的优惠', 'relevant': 'coupon.commerce.cn', 'confusions': ['sibling_competition']},
        ],
        'single_confusions': ['sibling_competition'],
    },
    'coupon.commerce.cn': {
        '对象': '优惠信息',
        '主动作': '找优惠',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('点一份汉堡王外卖', channel='food_delivery'),
            s('下单一台扫地机器人', channel='ecommerce'),
            s('买一副运动耳机', channel='ecommerce'),
        ],
        'main_dev': ['先看看有没有可用优惠券', '先把能领的折扣找出来'],
        'main_blind': ['先看能不能拿到优惠', '先把折扣这块摸清'],
        'main_challenge': ['真要下单前，最值得先翻的优惠在哪儿', '围绕这次购买，优惠这块最先该看什么'],
        'secondary_options': [
            {'text': '再看看不同渠道差价', 'relevant': 'price.commerce.cn', 'confusions': ['sibling_competition']},
            {'text': '顺便看附近门店能不能送', 'relevant': 'restaurant.travel.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['sibling_competition'],
    },
    'itinerary.travel.cn': {
        '对象': '行程规划',
        '主动作': '行程安排',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('去西安待四天', city='Xian', budget_rmb=5000),
            s('去杭州出差两天', city='Hangzhou'),
            s('去云南玩七天', city='Yunnan', budget_rmb=6000),
            s('去上海看展顺便逛两天', city='Shanghai'),
            s('去成都看演出顺便待两天', city='Chengdu'),
            s('去北京开会前留一天空档', city='Beijing'),
        ],
        'main_dev': ['先排个行程', '先把路线和安排理出来'],
        'main_blind': ['先把行程骨架搭起来', '先看这趟行程怎么排更顺'],
        'main_challenge': ['真要出发前，这趟安排最该先怎么捋', '围绕这次出行，先该把哪部分行程想清楚'],
        'secondary_options': [
            {'text': '再看看那几天的天气', 'relevant': 'weather.cn', 'confusions': ['cross_domain_overlap']},
            {'text': '顺便补几个可去的活动点', 'relevant': 'activity.travel.cn', 'confusions': ['sibling_competition']},
        ],
        'single_confusions': ['sibling_competition'],
        'segments': {
            'beijing': {'对象': '北京行程', '主动作': '北京行程安排', 'main_dev': ['先把北京这趟行程排出来'], 'main_blind': ['先理一遍北京这趟怎么走'], 'main_challenge': ['真去北京前，这几天最该先怎么排']},
            'shanghai': {'对象': '上海行程', '主动作': '上海行程安排', 'main_dev': ['先把上海这趟行程排出来'], 'main_blind': ['先理一遍上海这趟怎么走'], 'main_challenge': ['真去上海前，这几天最该先怎么排']},
            'chengdu': {'对象': '成都行程', '主动作': '成都行程安排', 'main_dev': ['先把成都这趟行程排出来'], 'main_blind': ['先理一遍成都这趟怎么走'], 'main_challenge': ['真去成都前，这几天最该先怎么排']},
            'xian': {'对象': '西安行程', '主动作': '西安行程安排', 'main_dev': ['先把西安这趟行程排出来'], 'main_blind': ['先理一遍西安这趟怎么走'], 'main_challenge': ['真去西安前，这几天最该先怎么排']},
            'hangzhou': {'对象': '杭州行程', '主动作': '杭州行程安排', 'main_dev': ['先把杭州这趟行程排出来'], 'main_blind': ['先理一遍杭州这趟怎么走'], 'main_challenge': ['真去杭州前，这几天最该先怎么排']},
            'guangzhou': {'对象': '广州行程', '主动作': '广州行程安排', 'main_dev': ['先把广州这趟行程排出来'], 'main_blind': ['先理一遍广州这趟怎么走'], 'main_challenge': ['真去广州前，这几天最该先怎么排']},
            'shenzhen': {'对象': '深圳行程', '主动作': '深圳行程安排', 'main_dev': ['先把深圳这趟行程排出来'], 'main_blind': ['先理一遍深圳这趟怎么走'], 'main_challenge': ['真去深圳前，这几天最该先怎么排']},
            'yunnan': {'对象': '云南行程', '主动作': '云南行程安排', 'main_dev': ['先把云南这趟行程排出来'], 'main_blind': ['先理一遍云南这趟怎么走'], 'main_challenge': ['真去云南前，这几天最该先怎么排']},
        },
    },
    'hotel.travel.cn': {
        '对象': '酒店筛选',
        '主动作': '找酒店',
        '高风险': False,
        'subjects_miit': [
            s('去外地参加设备评审会', city='Beijing'),
        ],
        'subjects_non': [
            s('去成都看演出', city='Chengdu'),
            s('去北京开会', city='Beijing'),
            s('去上海出差', city='Shanghai'),
            s('去杭州玩两天', city='Hangzhou'),
        ],
        'main_dev': ['先找个住起来方便的酒店', '先把住宿这块筛一遍'],
        'main_blind': ['先把住哪里这件事理顺', '先看什么样的酒店更合适'],
        'main_challenge': ['真要定住处前，最该先卡哪几个条件', '围绕这次住宿，先该把什么筛选清楚'],
        'secondary_options': [
            {'text': '再看看通勤和接驳', 'relevant': 'transport.travel.cn', 'confusions': ['sibling_competition']},
        ],
        'single_confusions': ['sibling_competition'],
        'segments': {
            'beijing': {'对象': '北京酒店', '主动作': '北京住宿筛选', 'main_dev': ['先筛北京这边住起来方便的酒店'], 'main_blind': ['先看北京这趟住哪里更顺'], 'main_challenge': ['真到北京前，住处先该怎么筛']},
            'shanghai': {'对象': '上海酒店', '主动作': '上海住宿筛选', 'main_dev': ['先筛上海这边住起来方便的酒店'], 'main_blind': ['先看上海这趟住哪里更顺'], 'main_challenge': ['真到上海前，住处先该怎么筛']},
            'chengdu': {'对象': '成都酒店', '主动作': '成都住宿筛选', 'main_dev': ['先筛成都这边住起来方便的酒店'], 'main_blind': ['先看成都这趟住哪里更顺'], 'main_challenge': ['真到成都前，住处先该怎么筛']},
            'xian': {'对象': '西安酒店', '主动作': '西安住宿筛选', 'main_dev': ['先筛西安这边住起来方便的酒店'], 'main_blind': ['先看西安这趟住哪里更顺'], 'main_challenge': ['真到西安前，住处先该怎么筛']},
            'hangzhou': {'对象': '杭州酒店', '主动作': '杭州住宿筛选', 'main_dev': ['先筛杭州这边住起来方便的酒店'], 'main_blind': ['先看杭州这趟住哪里更顺'], 'main_challenge': ['真到杭州前，住处先该怎么筛']},
            'guangzhou': {'对象': '广州酒店', '主动作': '广州住宿筛选', 'main_dev': ['先筛广州这边住起来方便的酒店'], 'main_blind': ['先看广州这趟住哪里更顺'], 'main_challenge': ['真到广州前，住处先该怎么筛']},
            'shenzhen': {'对象': '深圳酒店', '主动作': '深圳住宿筛选', 'main_dev': ['先筛深圳这边住起来方便的酒店'], 'main_blind': ['先看深圳这趟住哪里更顺'], 'main_challenge': ['真到深圳前，住处先该怎么筛']},
            'yunnan': {'对象': '云南酒店', '主动作': '云南住宿筛选', 'main_dev': ['先筛云南这边住起来方便的酒店'], 'main_blind': ['先看云南这趟住哪里更顺'], 'main_challenge': ['真到云南前，住处先该怎么筛']},
        },
    },
    'flight.travel.cn': {
        '对象': '航班选择',
        '主动作': '查航班',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('去广州出差', city='Guangzhou'),
            s('去成都看比赛', city='Chengdu'),
            s('去深圳见客户', city='Shenzhen'),
        ],
        'main_dev': ['先看一下机票和航班选择', '先把合适的航班筛出来'],
        'main_blind': ['先把航班这块理一遍', '先看什么时间和班次更顺'],
        'main_challenge': ['真要订票前，航班这块先该卡哪几个条件', '围绕这次出行，机票先该怎么筛'],
        'secondary_options': [
            {'text': '再顺手看行程怎么接', 'relevant': 'itinerary.travel.cn', 'confusions': ['sibling_competition']},
            {'text': '顺便看看天气', 'relevant': 'weather.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['sibling_competition'],
    },
    'restaurant.travel.cn': {
        '对象': '餐厅门店',
        '主动作': '找吃饭的地方',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('在外地出差时找晚饭', city='Beijing'),
            s('周末想在杭州找家餐厅', city='Hangzhou'),
        ],
        'main_dev': ['先找个方便吃饭的地方', '先筛一遍附近能去的餐厅'],
        'main_blind': ['先看去哪儿吃更合适', '先把门店这块摸一遍'],
        'main_challenge': ['真要过去吃前，先该把哪几个条件想清楚', '围绕这顿饭，门店这块最先看什么'],
        'secondary_options': [
            {'text': '再看看有没有可用优惠', 'relevant': 'coupon.commerce.cn', 'confusions': ['cross_domain_overlap']},
            {'text': '顺便看过去方不方便', 'relevant': 'transport.travel.cn', 'confusions': ['sibling_competition']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'activity.travel.cn': {
        '对象': '活动景点',
        '主动作': '找活动',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('去上海玩两天', city='Shanghai'),
            s('去成都逛周末', city='Chengdu'),
            s('去广州待三天', city='Guangzhou'),
        ],
        'main_dev': ['先看看能安排哪些活动', '先把可去的点位和活动捋一下'],
        'main_blind': ['先把玩什么这件事理一遍', '先看哪些活动更值得排进去'],
        'main_challenge': ['真要排进去，活动这块最该先筛什么', '围绕这次出行，玩什么最先该定'],
        'secondary_options': [
            {'text': '再看看交通怎么接', 'relevant': 'transport.travel.cn', 'confusions': ['sibling_competition']},
            {'text': '顺便看看天气', 'relevant': 'weather.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['sibling_competition'],
    },
    'transport.travel.cn': {
        '对象': '交通接驳',
        '主动作': '交通安排',
        '高风险': False,
        'subjects_miit': [
            s('去会场参加设备评审', city='Beijing', industry='manufacturing'),
        ],
        'subjects_non': [
            s('从酒店去演出场馆', city='Chengdu'),
            s('从机场去市区住处', city='Shanghai'),
            s('去景点之间换乘', city='Hangzhou'),
        ],
        'main_dev': ['先把交通和接驳方式安排一下', '先看怎么走更省事'],
        'main_blind': ['先把通勤接驳理一遍', '先看这段路怎么接更顺'],
        'main_challenge': ['真要动身前，交通这块先该补哪几个判断', '围绕这段通勤，最该先看清什么'],
        'secondary_options': [
            {'text': '再看看住处选得合不合适', 'relevant': 'hotel.travel.cn', 'confusions': ['sibling_competition']},
            {'text': '顺便补一版行程', 'relevant': 'itinerary.travel.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['sibling_competition'],
    },
    'weather.cn': {
        '对象': '天气情况',
        '主动作': '天气查询',
        '高风险': False,
        'subjects_miit': [
            s('下周去外地参加客户交流', city='Suzhou', time_window='next_week', industry='enterprise_service')
        ],
        'subjects_non': [
            s('周末在杭州安排外出', city='Hangzhou', time_window='weekend'),
            s('下周准备去成都玩', city='Chengdu', time_window='next_week'),
            s('明天想去上海办点事', city='Shanghai', time_window='tomorrow'),
            s('五一准备去西安', city='Xian', time_window='holiday'),
        ],
        'main_dev': ['先看看天气和温度', '先查一下会不会下雨'],
        'main_blind': ['先把天气这块看清', '先摸一下气温和降雨情况'],
        'main_challenge': ['真要出门前，天气这块最该先确认什么', '围绕这次外出，气象上最先该看哪项'],
        'secondary_options': [
            {'text': '再把行程顺一下', 'relevant': 'itinerary.travel.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'nutrition.health.cn': {
        '对象': '饮食调整',
        '主动作': '营养规划',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('最近总是晚睡', goal='diet_adjustment'),
            s('想把饮食先调得清淡一点', goal='diet_adjustment'),
            s('想控制油和糖的摄入', goal='diet_adjustment'),
        ],
        'main_dev': ['先给我一套低油低糖的吃法', '先做一版饮食调整方案'],
        'main_blind': ['先把吃饭这件事调一调', '先理一版饮食安排'],
        'main_challenge': ['真要把状态往回拉，饮食这块最该先改哪几件事', '围绕日常吃饭，最该先调整什么'],
        'secondary_options': [
            {'text': '再补一点运动建议', 'relevant': 'fitness.health.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'fitness.health.cn': {
        '对象': '训练安排',
        '主动作': '健身规划',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('想恢复一点运动习惯', goal='fitness'),
            s('准备开始规律锻炼', goal='fitness'),
        ],
        'main_dev': ['先做一版训练计划', '先把锻炼安排排起来'],
        'main_blind': ['先理一版训练节奏', '先看怎么开始锻炼更稳'],
        'main_challenge': ['真要把运动捡起来，最该先定哪几件事', '围绕训练这件事，起步先该怎么排'],
        'secondary_options': [
            {'text': '再补饮食配合建议', 'relevant': 'nutrition.health.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'clinic.health.cn': {
        '对象': '门诊就医',
        '主动作': '门诊信息查询',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('最近总想去门诊看看', goal='clinic'),
            s('准备做一次普通门诊检查', goal='clinic'),
        ],
        'main_dev': ['先看看该去哪里挂号', '先查一下门诊怎么走'],
        'main_blind': ['先把就医这步理一理', '先看门诊这块怎么安排'],
        'main_challenge': ['真要去看之前，门诊这块最该先搞清什么', '围绕这次就医，先该确认哪步'],
        'secondary_options': [
            {'text': '再顺手看下相关课程科普', 'relevant': 'course.education.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'course.education.cn': {
        '对象': '课程学习',
        '主动作': '课程选择',
        '高风险': False,
        'subjects_miit': [
            s('系统学一下工控安全基础', goal='self_learning', industry='manufacturing')
        ],
        'subjects_non': [
            s('补一门数据分析入门课', goal='self_learning'),
            s('找一门项目管理基础课', goal='self_learning'),
        ],
        'main_dev': ['先推荐一门适合入门的课程', '先给我一条学习路径'],
        'main_blind': ['先看什么课程适合起步', '先把入门学习路线理一遍'],
        'main_challenge': ['真要开始学，最先该报哪类课', '围绕入门这件事，先该怎么选课'],
        'secondary_options': [
            {'text': '再看看要不要找人辅导', 'relevant': 'tutoring.education.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
    'tutoring.education.cn': {
        '对象': '辅导答疑',
        '主动作': '找辅导',
        '高风险': False,
        'subjects_miit': [],
        'subjects_non': [
            s('学一门新课时想找人带一带', goal='self_learning'),
            s('准备找个导师答疑', goal='self_learning'),
        ],
        'main_dev': ['先帮我找个能答疑的辅导方式', '先看有没有合适的导师或辅导'],
        'main_blind': ['先把辅导这件事理一理', '先看怎么找人带更合适'],
        'main_challenge': ['真要有人带着学，先该把哪几个条件想清楚', '围绕辅导这件事，先该从哪步定下来'],
        'secondary_options': [
            {'text': '再配一门适合的课程', 'relevant': 'course.education.cn', 'confusions': ['cross_domain_overlap']},
        ],
        'single_confusions': ['cross_domain_overlap'],
    },
}

MULTI_TOTALS = {
    'permit.gov.cn': 4,
    'policy.gov.cn': 3,
    'compliance.security.cn': 6,
    'risk.security.cn': 3,
    'fraud.security.cn': 1,
    'invoice.finance.cn': 6,
    'tax.finance.cn': 4,
    'budget.finance.cn': 1,
    'invest.finance.cn': 0,
    'meeting.productivity.cn': 4,
    'docs.productivity.cn': 4,
    'price.commerce.cn': 3,
    'coupon.commerce.cn': 1,
    'itinerary.travel.cn': 2,
    'hotel.travel.cn': 2,
    'flight.travel.cn': 1,
    'restaurant.travel.cn': 1,
    'activity.travel.cn': 1,
    'transport.travel.cn': 2,
    'weather.cn': 1,
    'nutrition.health.cn': 1,
    'fitness.health.cn': 0,
    'clinic.health.cn': 1,
    'course.education.cn': 1,
    'tutoring.education.cn': 1,
}

L3_TOTALS = {
    'compliance.security.cn': 6,
    'invoice.finance.cn': 7,
    'meeting.productivity.cn': 5,
    'itinerary.travel.cn': 2,
    'hotel.travel.cn': 2,
}

MIXED_MIIT_TOTALS = {
    'price.commerce.cn': 2,
    'transport.travel.cn': 1,
    'weather.cn': 1,
    'course.education.cn': 1,
    'fraud.security.cn': 0,
    'coupon.commerce.cn': 0,
}

SEGMENT_ORDERS = {
    'compliance.security.cn': ['data', 'transaction', 'account'],
    'invoice.finance.cn': ['verify', 'issue', 'reimburse'],
    'meeting.productivity.cn': ['summary', 'schedule', 'action-items'],
    'itinerary.travel.cn': ['xian', 'hangzhou', 'yunnan', 'chengdu', 'shanghai', 'beijing'],
    'hotel.travel.cn': ['chengdu', 'beijing', 'hangzhou', 'shanghai'],
}

SEGMENT_CONTEXT_FIELDS = {
    'itinerary.travel.cn': 'city',
    'hotel.travel.cn': 'city',
}

SEGMENT_CONTEXT_NORMALIZERS = {
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


def load_coverage_plan() -> list[dict[str, str]]:
    with COVERAGE_PLAN_PATH.open('r', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def allocate_total_by_split(split_counts: dict[str, int], total_positive: int) -> dict[str, int]:
    total = sum(split_counts.values())
    if total_positive <= 0:
        return {k: 0 for k in split_counts}
    raw = {k: total_positive * v / total for k, v in split_counts.items()}
    allocated = {k: int(raw[k]) for k in split_counts}
    remaining = total_positive - sum(allocated.values())
    order = sorted(split_counts, key=lambda k: (raw[k] - allocated[k], split_counts[k]), reverse=True)
    for key in order:
        if remaining <= 0:
            break
        allocated[key] += 1
        remaining -= 1
    return allocated


def spread_flags(size: int, positives: int) -> list[bool]:
    if size <= 0:
        return []
    if positives <= 0:
        return [False] * size
    if positives >= size:
        return [True] * size
    marks = [False] * size
    if positives == 1:
        marks[size // 2] = True
        return marks
    positions = []
    for i in range(positives):
        pos = round(i * (size - 1) / (positives - 1))
        positions.append(pos)
    seen = set()
    for pos in positions:
        while pos in seen and pos + 1 < size:
            pos += 1
        seen.add(pos)
        marks[pos] = True
    return marks


def choose_subject(blueprint: dict[str, Any], miit: bool, index: int, split: str) -> dict[str, Any]:
    subjects = blueprint['subjects_miit'] if miit else blueprint['subjects_non'] or blueprint['subjects_miit']
    offset = {'dev': 0, 'blind': 1, 'challenge': 2}[split]
    return subjects[(index + offset) % len(subjects)]


def choose_text(options: list[str], index: int, split: str) -> str:
    return options[index % len(options)]


def choose_secondary(blueprint: dict[str, Any], index: int, split: str) -> dict[str, Any]:
    options = blueprint.get('secondary_options', [])
    if not options:
        return {'text': '', 'relevant': None, 'confusions': []}
    return options[index % len(options)]


def normalize_segment_context(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return SEGMENT_CONTEXT_NORMALIZERS.get(normalized, normalized or None)


def choose_aligned_subject(
    base_fqdn: str,
    blueprint: dict[str, Any],
    miit: bool,
    index: int,
    split: str,
    segment: str | None,
) -> dict[str, Any]:
    subject = choose_subject(blueprint, miit, index, split)
    if not segment or base_fqdn not in SEGMENT_CONTEXT_FIELDS:
        return subject

    context_key = SEGMENT_CONTEXT_FIELDS[base_fqdn]
    subjects = blueprint['subjects_miit'] if miit else blueprint['subjects_non'] or blueprint['subjects_miit']
    matching = [
        item for item in subjects
        if normalize_segment_context((item.get('context') or {}).get(context_key)) == segment
    ]
    if not matching:
        return subject
    return matching[index % len(matching)]


def strip_trailing_punctuation(text: str) -> str:
    return text.rstrip('。！？；，,;!? ')


def strip_prefixes(text: str, prefixes: tuple[str, ...]) -> str:
    value = text.strip()
    changed = True
    while changed and value:
        changed = False
        for prefix in prefixes:
            if value.startswith(prefix):
                value = value[len(prefix):].lstrip('，,：: ')
                changed = True
                break
    return value


def normalize_scene(text: str) -> str:
    value = strip_trailing_punctuation(text.strip())
    stripped = strip_prefixes(value, SCENE_STRIP_PREFIXES)
    return stripped or value


def normalize_main(text: str) -> str:
    value = strip_trailing_punctuation(text.strip())
    stripped = strip_prefixes(value, MAIN_STRIP_PREFIXES)
    return stripped or value


def normalize_secondary(text: str) -> str:
    value = strip_trailing_punctuation(text.strip())
    stripped = strip_prefixes(value, SECONDARY_STRIP_PREFIXES)
    return stripped or value


def compose_query(split: str, scene: str, main: str, secondary: str, index: int) -> str:
    scene_text = normalize_scene(scene)
    main_text = normalize_main(main)
    secondary_text = normalize_secondary(secondary) if secondary else ''

    if split == 'challenge':
        sentences = [
            choose_text(SCENE_SENTENCE_PATTERNS[split], index, split).format(
                scene=scene_text,
                main=main_text,
            )
        ]
    else:
        sentences = [
            choose_text(SCENE_SENTENCE_PATTERNS[split], index, split).format(scene=scene_text),
            choose_text(MAIN_SENTENCE_PATTERNS[split], index, split).format(main=main_text),
        ]

    if secondary_text:
        sentences.append(f'另外，再{secondary_text}。')

    return ''.join(sentences)


def ledger_confusions(values: list[str]) -> str:
    return '；'.join(CONFUSION_CN.get(value, value) for value in values)


def make_id(split: str, idx: int) -> str:
    return f'formal_{split}_{idx:06d}'


def make_family_id(split: str, base_fqdn: str, local_index: int) -> str:
    slug = base_fqdn.replace('.', '_').replace('-', '_')
    return f'{split}_{slug}_f{local_index:02d}'


def build_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    coverage_rows = load_coverage_plan()

    outputs = {
        'dev': [],
        'blind_input': [],
        'blind_labels': [],
        'challenge_input': [],
        'challenge_labels': [],
    }
    ledger_rows: list[dict[str, str]] = []
    split_global_counter = {'dev': 1, 'blind': 1, 'challenge': 1}

    for row in coverage_rows:
        base_fqdn = row['base_fqdn']
        blueprint = BLUEPRINTS[base_fqdn]
        split_counts = {
            'dev': int(row['dev目标']),
            'blind': int(row['blind目标']),
            'challenge': int(row['challenge目标']),
        }
        total_count = sum(split_counts.values())
        multi_split = allocate_total_by_split(split_counts, MULTI_TOTALS.get(base_fqdn, 0))
        l3_split = allocate_total_by_split(split_counts, L3_TOTALS.get(base_fqdn, 0))
        if row['场景桶目标'] == '工信优先':
            miit_split = {k: split_counts[k] for k in split_counts}
        elif row['场景桶目标'] == '非工信优先':
            miit_split = {k: 0 for k in split_counts}
        else:
            miit_split = allocate_total_by_split(split_counts, MIXED_MIIT_TOTALS.get(base_fqdn, 0))

        for split in ('dev', 'blind', 'challenge'):
            count = split_counts[split]
            if count == 0:
                continue
            multi_flags = spread_flags(count, multi_split[split])
            l3_flags = spread_flags(count, l3_split[split])
            miit_flags = spread_flags(count, miit_split[split])
            segment_order = SEGMENT_ORDERS.get(base_fqdn, [])
            segment_index = 0
            for local_index in range(count):
                variant_index = split_global_counter[split] - 1
                use_multi = multi_flags[local_index]
                use_l3 = l3_flags[local_index]
                miit = miit_flags[local_index]
                gt_fqdn = base_fqdn
                acceptable = [base_fqdn]
                object_name = blueprint['对象']
                action_name = blueprint['主动作']
                main_options = blueprint[f'main_{split}']

                if use_l3:
                    segment = segment_order[segment_index % len(segment_order)]
                    segment_index += 1
                    segment_spec = blueprint['segments'][segment]
                    gt_fqdn = resolver.canonicalize_segment(base_fqdn, segment)
                    acceptable = [gt_fqdn, base_fqdn]
                    object_name = segment_spec['对象']
                    action_name = segment_spec['主动作']
                    main_options = segment_spec[f'main_{split}']
                else:
                    segment = None

                subject = choose_aligned_subject(
                    base_fqdn=base_fqdn,
                    blueprint=blueprint,
                    miit=miit,
                    index=local_index,
                    split=split,
                    segment=segment,
                )

                secondary = choose_secondary(blueprint, variant_index, split) if use_multi else {'text': '', 'relevant': None, 'confusions': []}
                query = compose_query(
                    split=split,
                    scene=subject['scene'],
                    main=choose_text(main_options, variant_index, split),
                    secondary=secondary['text'],
                    index=variant_index,
                )
                relevant = [secondary['relevant']] if secondary.get('relevant') and secondary['relevant'] != gt_fqdn else []
                confusions = list(blueprint.get('single_confusions', []))
                confusions.extend(secondary.get('confusions', []))
                if use_multi:
                    confusions.append('multi_intent')
                if use_l3:
                    if base_fqdn in {'invoice.finance.cn', 'meeting.productivity.cn', 'hotel.travel.cn', 'itinerary.travel.cn'}:
                        confusions.append('sibling_competition')
                    if base_fqdn in {'compliance.security.cn', 'invoice.finance.cn'}:
                        confusions.append('fallback')
                confusions = list(dict.fromkeys(confusions))
                difficulty_tags = []
                if blueprint['高风险']:
                    difficulty_tags.append('high_risk')
                if use_multi:
                    difficulty_tags.append('multi_intent')

                family_id = make_family_id(split, gt_fqdn if not use_l3 else base_fqdn, local_index + 1)
                sample_id = make_id(split, split_global_counter[split])
                split_global_counter[split] += 1

                labeled_row = {
                    'id': sample_id,
                    'family_id': family_id,
                    'namespace_version': 'ns_v1_20260311',
                    'query': query,
                    'context': subject['context'],
                    'constraints': ['fqdn_format_valid'],
                    'ground_truth_fqdn': gt_fqdn,
                    'relevant_fqdns': relevant,
                    'acceptable_fqdns': acceptable,
                    'difficulty_tags': difficulty_tags,
                    'intended_confusion_types': confusions,
                }

                if split == 'dev':
                    outputs['dev'].append(labeled_row)
                elif split == 'blind':
                    outputs['blind_input'].append({
                        'id': sample_id,
                        'namespace_version': 'ns_v1_20260311',
                        'query': query,
                        'context': subject['context'],
                        'constraints': ['fqdn_format_valid'],
                    })
                    outputs['blind_labels'].append({
                        'id': sample_id,
                        'family_id': family_id,
                        'ground_truth_fqdn': gt_fqdn,
                        'relevant_fqdns': relevant,
                        'acceptable_fqdns': acceptable,
                        'difficulty_tags': difficulty_tags,
                        'intended_confusion_types': confusions,
                    })
                else:
                    outputs['challenge_input'].append({
                        'id': sample_id,
                        'namespace_version': 'ns_v1_20260311',
                        'query': query,
                        'context': subject['context'],
                        'constraints': ['fqdn_format_valid'],
                    })
                    outputs['challenge_labels'].append({
                        'id': sample_id,
                        'family_id': family_id,
                        'ground_truth_fqdn': gt_fqdn,
                        'relevant_fqdns': relevant,
                        'acceptable_fqdns': acceptable,
                        'difficulty_tags': difficulty_tags,
                        'intended_confusion_types': confusions,
                    })

                ledger_rows.append({
                    'family_id': family_id,
                    'split': split,
                    '样本ID列表': sample_id,
                    '主路由fqdn': gt_fqdn,
                    '主能力base_fqdn': base_fqdn,
                    '一级领域': row['一级领域'],
                    '二级能力': row['二级能力'],
                    '是否l3': '是' if use_l3 else '否',
                    '场景桶': '工信' if miit else '非工信',
                    '主对象': object_name,
                    '主动作': action_name,
                    '次要意图模式': secondary['text'] or '无',
                    '主要混淆类型': ledger_confusions(confusions),
                    '备注': '',
                })

    return (
        outputs['dev'],
        outputs['blind_input'],
        outputs['blind_labels'],
        outputs['challenge_input'],
        outputs['challenge_labels'],
        ledger_rows,
    )


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def dump_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        'family_id', 'split', '样本ID列表', '主路由fqdn', '主能力base_fqdn', '一级领域', '二级能力', '是否l3', '场景桶', '主对象', '主动作', '次要意图模式', '主要混淆类型', '备注'
    ]
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def update_manifest(
    dev_rows: list[dict[str, Any]],
    blind_input: list[dict[str, Any]],
    blind_labels: list[dict[str, Any]],
    challenge_input: list[dict[str, Any]],
    challenge_labels: list[dict[str, Any]],
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    dataset_version = 'formal_v1_1_20260306'

    def miit_ratio(rows: list[dict[str, Any]]) -> float:
        count = 0
        for row in rows:
            ctx = row.get('context') or {}
            if ctx.get('industry') in {'enterprise_service', 'manufacturing'}:
                count += 1
        return round(count / max(len(rows), 1), 4)

    all_labeled = dev_rows + blind_labels + challenge_labels
    all_context_rows = dev_rows + blind_input + challenge_input
    context_by_id = {row['id']: row.get('context') or {} for row in all_context_rows}
    miit_labeled = 0
    l3_count = 0
    multi_count = 0
    resolver = NamespaceResolver(load_jsonl(DESCRIPTOR_PATH))
    covered_bases = set()
    blind_covered_bases = set()
    for row in all_labeled:
        if context_by_id.get(row['id'], {}).get('industry') in {'enterprise_service', 'manufacturing'}:
            miit_labeled += 1
        if 'multi_intent' in row.get('difficulty_tags', []) or 'multi_intent' in row.get('intended_confusion_types', []):
            multi_count += 1
        node = resolver.get_node(row['ground_truth_fqdn'])
        if node and node.segment:
            l3_count += 1
            covered_bases.add(node.parent_fqdn)
        else:
            covered_bases.add(row['ground_truth_fqdn'])
        if row['id'].startswith('formal_blind_'):
            if node and node.segment:
                blind_covered_bases.add(node.parent_fqdn)
            else:
                blind_covered_bases.add(row['ground_truth_fqdn'])

    manifest['dataset_version'] = dataset_version
    manifest['status'] = 'formal_v1_1_seeded'
    manifest['namespace_version_note'] = (
        f'ns_v1_20260311 表示命名空间计划冻结日期（2026-03-11），不是 {dataset_version} 的数据构建日期；'
        'formal 数据可在该冻结日前后扩表，但 canonical contract 不应回改。'
    )
    manifest['formal_splits']['dev']['samples'] = len(dev_rows)
    manifest['formal_splits']['blind_input']['samples'] = len(blind_input)
    manifest['formal_splits']['blind_labels']['samples'] = len(blind_labels)
    manifest['formal_splits']['challenge_input']['samples'] = len(challenge_input)
    manifest['formal_splits']['challenge_labels']['samples'] = len(challenge_labels)
    manifest['formal_splits']['dev']['miit_ratio'] = miit_ratio(dev_rows)
    manifest['formal_splits']['blind_input']['miit_ratio'] = round(
        sum(1 for row in blind_input if (row.get('context') or {}).get('industry') in {'enterprise_service', 'manufacturing'}) / max(len(blind_input), 1),
        4,
    )
    manifest['formal_splits']['challenge_input']['miit_ratio'] = round(
        sum(1 for row in challenge_input if (row.get('context') or {}).get('industry') in {'enterprise_service', 'manufacturing'}) / max(len(challenge_input), 1),
        4,
    )
    manifest['totals'] = {
        'samples': len(all_labeled),
        'miit_ratio': round(miit_labeled / max(len(all_labeled), 1), 4),
    }
    manifest['current_stats'] = {
        'split_sizes': {
            'dev': len(dev_rows),
            'blind': len(blind_labels),
            'challenge': len(challenge_labels),
        },
        'total_labeled': len(all_labeled),
        'miit_ratio': round(miit_labeled / max(len(all_labeled), 1), 4),
        'l3_ratio': round(l3_count / max(len(all_labeled), 1), 4),
        'multi_intent_ratio': round(multi_count / max(len(all_labeled), 1), 4),
        'gt_base_coverage': {
            'covered': len(covered_bases),
            'total_base_nodes': len([node for node in resolver.iter_nodes() if node.node_kind == 'base']),
            'ratio': round(len(covered_bases) / max(len([node for node in resolver.iter_nodes() if node.node_kind == 'base']), 1), 4),
        },
        'blind_base_coverage': {
            'covered': len(blind_covered_bases),
            'total_base_nodes': len([node for node in resolver.iter_nodes() if node.node_kind == 'base']),
            'ratio': round(
                len(blind_covered_bases) / max(len([node for node in resolver.iter_nodes() if node.node_kind == 'base']), 1),
                4,
            ),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    FORMAL_DIR.mkdir(parents=True, exist_ok=True)
    dev_rows, blind_input, blind_labels, challenge_input, challenge_labels, ledger_rows = build_rows()
    dump_jsonl(FORMAL_DIR / 'dev.jsonl', dev_rows)
    dump_jsonl(FORMAL_DIR / 'blind_input.jsonl', blind_input)
    dump_jsonl(FORMAL_DIR / 'blind_labels.jsonl', blind_labels)
    dump_jsonl(FORMAL_DIR / 'challenge_input.jsonl', challenge_input)
    dump_jsonl(FORMAL_DIR / 'challenge_labels.jsonl', challenge_labels)
    dump_ledger(FORMAL_DIR / 'family_ledger.csv', ledger_rows)
    update_manifest(dev_rows, blind_input, blind_labels, challenge_input, challenge_labels)
    print(json.dumps({
        'dev': len(dev_rows),
        'blind': len(blind_labels),
        'challenge': len(challenge_labels),
        'total': len(dev_rows) + len(blind_labels) + len(challenge_labels),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
