from __future__ import annotations

from pathlib import Path

from pptx.util import Inches

import build_project_defense_deck_strong as base


ROOT = Path("/Users/xizhuxizhu/Desktop/IndProj04")
OUT_DIR = ROOT / "output/pptx/project_defense_20260426"
OUTPUT = OUT_DIR / "项目评审答辩PPT_验收答辩15页版_20260524.pptx"
FIG_DIR = ROOT / "output/doc/gjtx_submission_20260413/figures"
DEMO_IMG = ROOT / "output/playwright/agentdnsdemo_risk_flow_adjusted.png"

C = base.C
SLIDE_W, SLIDE_H = base.SLIDE_W, base.SLIDE_H


def blank(prs):
    return base.blank(prs)


def add_picture(slide, file: Path, x, y, w, h):
    return base.add_picture(slide, file, x, y, w, h)


def add_box(slide, x, y, w, h, fill="ffffff", line="c8dbef", radius=True, alpha=0):
    return base.add_box(slide, x, y, w, h, fill=fill, line=line, radius=radius, alpha=alpha)


def add_text(slide, *args, **kwargs):
    return base.add_text(slide, *args, **kwargs)


def add_title(slide, title, subtitle="", sec=""):
    return base.add_title(slide, title, subtitle, sec)


def add_footer(slide, page):
    return base.add_footer(slide, page)


def add_line(slide, x, y, w, color="line", weight=1.2):
    return base.add_line(slide, x, y, w, color=color, weight=weight)


def add_circle(slide, x, y, d, fill):
    return base.add_circle(slide, x, y, d, fill)


def add_bullet(slide, text, x, y, w, color="blue", size=12, text_color="ink"):
    return base.add_bullet(slide, text, x, y, w, color=color, size=size, text_color=text_color)


def arrow(slide, x, y):
    add_text(slide, "→", x, y, 0.25, 0.18, size=15, color="muted", bold=True, align="center", font="Arial")


def cover(prs):
    s = blank(prs)
    add_picture(s, base.STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "重点项目验收答辩｜15页精简版", 0.72, 0.68, 3.55, 0.28, size=16, color="cyan", bold=True)
    add_line(s, 0.72, 1.06, 1.72, "cyan", 3)
    add_text(s, "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究", 0.72, 1.42, 8.7, 1.0, size=30, color="white", bold=True)
    add_text(s, "以智能体能力命名与语义路由为典型验证载体，完成协作复核、显式授权、可信留痕和原型验证闭环", 0.75, 2.73, 9.1, 0.35, size=15.4, color="cfe4ff")
    for i, (v, l) in enumerate([("563", "冻结样本"), ("50/45", "能力节点/主标签"), ("0.9292", "扩展配置准确率"), ("5/5/0", "改判/纠错/误改")]):
        x = 0.78 + i * 2.18
        add_box(s, x, 4.25, 1.86, 0.76, fill="0b3c7c", line="4c96e8", alpha=16000)
        add_text(s, v, x + 0.08, 4.37, 1.7, 0.28, size=20, color="white", bold=True, align="center", font="Arial")
        add_text(s, l, x + 0.08, 4.72, 1.7, 0.18, size=8.6, color="d2e6ff", align="center")
    add_text(s, "承研处所：技术发展所    项目负责人：邓斯宇    起止时间：2025年5月-2026年4月", 0.74, 6.62, 7.4, 0.25, size=11, color="d2e6ff")
    add_text(s, "CNNIC", 11.58, 0.38, 1.1, 0.3, size=23, color="white", bold=True, align="right", font="Arial")
    add_text(s, "中国互联网络信息中心", 10.9, 0.7, 1.78, 0.18, size=8.5, color="d2e6ff", align="right")


def background(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "项目背景：智能体服务规模化接入后，能力调用需要可信基础支撑", "不是做泛泛 Agent 应用，而是解决能力如何组织、如何选择、如何复核、如何留痕的问题。", "02")
    chain = [
        ("智能体服务增多", "工具调用和服务发现对象变复杂"),
        ("用户请求自然语言化", "主任务、次要任务和风险线索混在一起"),
        ("能力错选风险上升", "主能力错派、相关能力遗漏、风险任务误派发"),
        ("过程需要核验", "候选、判断、复核和执行落点必须可追溯"),
    ]
    for i, (t, b) in enumerate(chain):
        x = 0.78 + i * 3.02
        col = ["blue", "green", "orange2", "purple"][i]
        add_box(s, x, 1.55, 2.32, 1.22, fill="ffffff", line=C[col])
        add_text(s, f"0{i+1}", x + 0.18, 1.78, 0.42, 0.2, size=13, color=col, bold=True, font="Arial")
        add_text(s, t, x + 0.68, 1.76, 1.25, 0.2, size=12.4, color="ink", bold=True)
        add_text(s, b, x + 0.22, 2.22, 1.78, 0.26, size=8.8, color="muted")
        if i < 3:
            arrow(s, x + 2.44, 2.02)
    add_box(s, 0.92, 3.55, 4.9, 1.64, fill="071a46", line="1e83e6")
    add_text(s, "问题与风险", 1.22, 3.88, 1.3, 0.24, size=16, color="white", bold=True)
    for i, b in enumerate(["主能力错选：词面命中但任务中心偏移", "相关能力遗漏：次要诉求没有被识别", "风险任务误派发：治理边界缺少复核", "过程不可追溯：无法解释为何选这个 Agent"]):
        add_bullet(s, b, 1.25, 4.28 + i * 0.28, 3.7, color="cyan", size=8.4, text_color="d2e6ff")
    add_box(s, 6.35, 3.55, 4.9, 1.64, fill="ffffff", line="7fb5ee")
    add_text(s, "项目切入点", 6.68, 3.88, 1.2, 0.24, size=16, color="blue", bold=True)
    add_text(s, "围绕互联网基础资源场景中的智能体能力组织与可信调用入口，构建“多智能体协作 + 可信认知标识”的验证框架。", 6.72, 4.32, 3.72, 0.42, size=12.0, color="ink", bold=True)
    add_footer(s, 2)


def task_focus(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "任务书目标与本项目聚焦：没有偏题，语义路由只是验证载体", "把任务书要求转成四类可验证技术对象：角色、共识、可信记录和真实标签反馈。", "03")
    items = [
        ("多视角认知风格生成", "任务匹配、治理风险、层级解析、用户偏好四类职责角色", "blue"),
        ("多智能体交互与共识算法", "角色并行复核、候选级证据聚合、二轮复核、显式授权改判", "green"),
        ("智能体行为可信标识", "候选快照、角色标识、结构化判断、授权结果、执行接口记录", "orange2"),
        ("真实标签反馈验证", "563 条样本、冻结 train/test、主结果、消融和诊断分析", "purple"),
    ]
    for i, (t, b, col) in enumerate(items):
        x = 0.86 + (i % 2) * 5.85
        y = 1.55 + (i // 2) * 1.42
        add_box(s, x, y, 5.0, 1.05, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.24, y + 0.22, 1.8, 0.2, size=13.4, color=col, bold=True)
        add_text(s, b, x + 2.12, y + 0.18, 2.35, 0.28, size=9.4, color="muted")
    add_box(s, 1.0, 5.2, 10.7, 0.82, fill="e7f1ff", line="7fb5ee")
    add_text(s, "答辩防守点", 1.3, 5.44, 1.2, 0.18, size=13, color="blue", bold=True)
    add_text(s, "项目主题是“大模型多智能体协作与可信认知标识”；语义路由承担场景验证和原型评测作用，不替代项目主题。", 2.55, 5.43, 7.85, 0.2, size=12.0, color="ink", bold=True)
    add_footer(s, 3)


def scenario_mapping(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "典型验证场景：语义路由把项目主题落到可评测链路", "能力命名、候选选择、协作复核、过程记录和执行映射在同一个受控样本空间内被验证。", "04")
    steps = [
        ("自然语言请求", "用户提出复杂任务"),
        ("能力命名空间", "能力对象如何组织"),
        ("结构化语义路由", "请求如何指向主能力和相关能力"),
        ("多智能体复核", "复杂边界样本如何受控改判"),
        ("可信过程记录", "判断过程如何核验"),
        ("执行实例映射", "最终由哪个 Agent 承接"),
    ]
    for i, (t, b) in enumerate(steps):
        x = 0.55 + i * 2.06
        col = ["blue", "green", "orange2", "purple", "red", "blue2"][i]
        add_box(s, x, 1.78, 1.62, 1.12, fill="ffffff", line=C[col])
        add_text(s, str(i + 1), x + 0.14, 2.02, 0.26, 0.14, size=9.2, color=col, bold=True, font="Arial")
        add_text(s, t, x + 0.43, 2.0, 0.9, 0.18, size=10.1, color="ink", bold=True, align="center")
        add_text(s, b, x + 0.18, 2.42, 1.16, 0.2, size=7.7, color="muted", align="center")
        if i < 5:
            arrow(s, x + 1.7, 2.2)
    add_box(s, 0.9, 3.82, 10.95, 0.9, fill="071a46", line="1e83e6")
    add_text(s, "边界说明", 1.2, 4.12, 1.05, 0.18, size=13.2, color="cyan", bold=True)
    add_text(s, "本项目中的“命名、地址、发现、路由”均限定在智能体能力目录、候选选择和实例映射范围内，不涉及现网域名注册、权威解析或递归解析。", 2.35, 4.08, 8.45, 0.25, size=11.2, color="white", bold=True)
    add_box(s, 1.1, 5.18, 10.4, 0.54, fill="fff8e8", line="f2d58b")
    add_text(s, "一句话：语义路由是项目主题的典型验证载体，不是把项目建设成生产级 DNS 解析系统。", 1.42, 5.36, 8.8, 0.18, size=12.5, color="ink", bold=True)
    add_footer(s, 4)


def route_overview(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "总体技术路线：能力组织、结构化判断、协作复核、可信留痕形成闭环", "一张图说明从请求输入到执行衔接的完整链路，也是整套答辩的核心图。", "05")
    parts = [
        ("请求输入", "query / context", "blue"),
        ("能力命名与候选组织", "N, C(x)", "green"),
        ("单智能体结构化判别", "ŷ, R̂, score", "orange2"),
        ("协作触发判断", "low confidence / risk", "purple"),
        ("职责化复核 + 授权", "votes / gate", "red"),
        ("地址输出与执行衔接", "ability / instance", "blue2"),
    ]
    for i, (t, b, col) in enumerate(parts):
        x = 0.5 + i * 2.05
        add_box(s, x, 1.25, 1.65, 0.78, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.14, 1.42, 1.1, 0.16, size=8.8, color=col, bold=True, align="center")
        add_text(s, b, x + 0.15, 1.72, 1.08, 0.12, size=6.8, color="muted", align="center", font="Arial")
        if i < 5:
            arrow(s, x + 1.72, 1.55)
    add_box(s, 0.85, 2.34, 10.9, 0.42, fill="e7f1ff", line="7fb5ee")
    add_text(s, "可信轨迹", 1.16, 2.48, 1.0, 0.12, size=10, color="blue", bold=True)
    for i, t in enumerate(["候选快照", "规则分数", "结构化裁决", "角色提案", "授权判断", "最终输出"]):
        add_text(s, t, 2.35 + i * 1.35, 2.49, 0.88, 0.1, size=7.2, color="ink", bold=True, align="center")
    add_picture(s, FIG_DIR / "fig1_framework.png", 1.05, 2.86, 10.5, 3.78)
    add_footer(s, 5)


def namespace(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "关键技术一：能力命名空间与候选边界是可评测基础", "不是简单调 API，而是构建受限、可复核、可评测的能力空间。", "06")
    for i, (v, l, col) in enumerate([("50", "能力节点", "blue"), ("45", "主标签", "green"), ("563", "评测样本", "orange2")]):
        x = 0.9 + i * 1.6
        add_text(s, v, x, 1.42, 1.05, 0.38, size=28, color=col, bold=True, font="Arial")
        add_text(s, l, x + 0.05, 1.9, 1.1, 0.16, size=10.2, color="ink", bold=True)
    x0, y0 = 6.0, 1.28
    nodes = [("一级能力域", "travel / security / productivity"), ("二级能力域", "hotel / activity / docs"), ("能力逻辑地址", "activity.travel.cn"), ("实例逻辑地址", "agent endpoint")]
    for i, (t, b) in enumerate(nodes):
        y = y0 + i * 0.72
        add_box(s, x0, y, 4.4, 0.46, fill="ffffff", line=C[["blue", "green", "orange2", "purple"][i]])
        add_text(s, t, x0 + 0.18, y + 0.13, 1.25, 0.14, size=8.8, color=["blue", "green", "orange2", "purple"][i], bold=True)
        add_text(s, b, x0 + 1.56, y + 0.13, 2.28, 0.14, size=8.4, color="muted", font="Arial")
    add_box(s, 0.95, 3.25, 4.4, 1.55, fill="071a46", line="1e83e6")
    add_text(s, "技术约束", 1.25, 3.55, 1.2, 0.2, size=15, color="white", bold=True)
    for i, b in enumerate(["候选集合冻结，后续裁决不得发明候选外标签", "能力地址表示哪类能力承接请求", "实例地址表示最终哪个具体 Agent 执行"]):
        add_bullet(s, b, 1.28, 3.94 + i * 0.32, 3.2, color="cyan", size=8.6, text_color="d2e6ff")
    add_box(s, 6.0, 4.55, 4.45, 0.8, fill="fff8e8", line="f2d58b")
    add_text(s, "边界", 6.28, 4.82, 0.55, 0.16, size=11.8, color="orange2", bold=True)
    add_text(s, "能力目录和逻辑地址是原型内部实验对象，不是现网 DNS 资源。", 6.95, 4.82, 2.88, 0.16, size=9.2, color="ink", bold=True)
    add_footer(s, 6)


def structured_routing(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "关键技术二：结构化语义路由把模型判断约束在候选集合内", "核心不是让模型自由生成，而是让模型输出可比较、可升级、可复核的候选级裁决。", "07")
    add_box(s, 0.82, 1.38, 4.65, 2.65, fill="fff1f1", line="f1c3c3")
    add_text(s, "规则路由", 1.15, 1.72, 1.0, 0.24, size=16, color="red", bold=True)
    for i, b in enumerate(["关键词 / 别名 / 描述相似度", "层级信号和上下文命中", "问题：容易被表面词误拉偏"]):
        add_bullet(s, b, 1.18, 2.14 + i * 0.36, 3.3, color="red", size=10.0)
    add_box(s, 6.18, 1.38, 4.65, 2.65, fill="e7f1ff", line="7fb5ee")
    add_text(s, "结构化语义路由", 6.52, 1.72, 1.8, 0.24, size=16, color="blue", bold=True)
    for i, b in enumerate(["主任务摘要 / 相关能力", "置信度 / 风险提示 / 竞争候选说明", "约束：只能从候选集合中选择"]):
        add_bullet(s, b, 6.55, 2.14 + i * 0.36, 3.5, color="blue", size=10.0)
    add_box(s, 1.0, 4.85, 9.95, 0.72, fill="071a46", line="1e83e6")
    add_text(s, "结果", 1.3, 5.08, 0.6, 0.18, size=13, color="cyan", bold=True)
    add_text(s, "规则路由主准确率 78.76%，结构化语义路由提升至 87.61%；主要收益来自候选内主任务比较能力。", 2.05, 5.07, 7.7, 0.18, size=12.1, color="white", bold=True)
    add_footer(s, 7)


def multi_agent(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "关键技术三：职责化多智能体复核把“讨论”变成受控改判", "协作触发和最终改判分开；只有满足票数、证据强度、共识增益和风险确认条件才允许改判。", "08")
    roles = [
        ("任务匹配", "谁最能承接主任务", "blue"),
        ("治理风险", "审查高风险、跨域、敏感改判", "red"),
        ("层级解析", "处理父子节点和粒度冲突", "green"),
        ("用户偏好", "区分主次意图和辅助诉求", "orange2"),
    ]
    for i, (t, b, col) in enumerate(roles):
        x = 0.86 + (i % 2) * 4.1
        y = 1.38 + (i // 2) * 1.12
        add_box(s, x, y, 3.45, 0.86, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.22, y + 0.2, 0.95, 0.18, size=12.6, color=col, bold=True)
        add_text(s, b, x + 1.32, y + 0.2, 1.72, 0.18, size=9.0, color="muted")
    add_box(s, 8.95, 1.55, 2.45, 2.05, fill="071a46", line="1e83e6")
    add_text(s, "显式授权改判", 9.25, 1.86, 1.5, 0.22, size=15, color="white", bold=True)
    for i, b in enumerate(["≥3 票支持", "共识分数增益 ≥0.08", "显式主任务证据 ≥0.55", "高风险/跨域需额外确认"]):
        add_bullet(s, b, 9.28, 2.28 + i * 0.26, 1.55, color="cyan", size=7.7, text_color="d2e6ff")
    add_picture(s, FIG_DIR / "fig2_review_flow.png", 1.0, 4.25, 10.55, 1.58)
    add_footer(s, 8)


def trusted_trace(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "关键技术四：可信认知标识落到过程记录对象", "可信不是空泛概念，而是可记录、可回放、可解释、可核验。", "09")
    fields = [("输入请求", "query"), ("候选集合", "C(x)"), ("规则初判", "rule score"), ("结构化裁决", "decision packet"), ("角色提案", "agent votes"), ("授权判断", "trust gate"), ("最终能力地址", "ability addr"), ("实例映射", "agent endpoint")]
    for i, (t, b) in enumerate(fields):
        x = 0.72 + (i % 4) * 2.95
        y = 1.35 + (i // 4) * 1.08
        add_box(s, x, y, 2.25, 0.72, fill="ffffff", line=C[["blue", "green", "orange2", "purple"][i % 4]])
        add_text(s, t, x + 0.16, y + 0.18, 1.0, 0.16, size=10.2, color="ink", bold=True)
        add_text(s, b, x + 1.1, y + 0.2, 0.82, 0.12, size=7.8, color="muted", align="center", font="Arial")
    add_box(s, 0.92, 4.18, 10.8, 1.05, fill="071a46", line="1e83e6")
    add_text(s, "复盘能力", 1.22, 4.52, 1.2, 0.22, size=15, color="cyan", bold=True)
    add_text(s, "每条请求可还原：候选集合如何形成、初判为何选择、协作角色提出哪些支持或阻止信号、控制器为何允许或拒绝改判。", 2.52, 4.5, 8.05, 0.22, size=11.4, color="white", bold=True)
    add_footer(s, 9)


def experiment_design(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "实验设计与数据资产：冻结协议支撑项目验收与论文复现", "评委需要看到不是演示几个样例，而是有稳定样本、固定配置和可复现实验口径。", "10")
    cards = [("563", "样本总量", "blue"), ("450", "train", "green"), ("113", "test", "orange2"), ("97.35%", "top-8 gold 覆盖", "purple")]
    for i, (v, l, col) in enumerate(cards):
        x = 0.9 + i * 2.3
        add_box(s, x, 1.52, 1.75, 0.9, fill="ffffff", line=C[col])
        add_text(s, v, x + 0.12, 1.72, 1.45, 0.28, size=21, color=col, bold=True, align="center", font="Arial")
        add_text(s, l, x + 0.12, 2.1, 1.45, 0.14, size=8.4, color="muted", align="center")
    add_box(s, 0.9, 3.05, 4.95, 1.55, fill="ffffff", line="c8dbef")
    add_text(s, "评价指标", 1.22, 3.36, 1.0, 0.2, size=15, color="blue", bold=True)
    for i, b in enumerate(["主标签准确率", "可接受准确率", "相关能力召回/精确率", "改判 / 纠错 / 误改"]):
        add_bullet(s, b, 1.25, 3.76 + i * 0.28, 3.2, color="blue", size=8.8)
    add_box(s, 6.28, 3.05, 4.95, 1.55, fill="ffffff", line="c8dbef")
    add_text(s, "困难样本", 6.6, 3.36, 1.0, 0.2, size=15, color="orange2", bold=True)
    for i, b in enumerate(["层级竞争", "跨域重叠", "主次意图拆分", "高风险治理"]):
        add_bullet(s, b, 6.63 + (i % 2) * 1.75, 3.78 + (i // 2) * 0.32, 1.3, color="orange2", size=8.8)
    add_footer(s, 10)


def core_results(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "核心实验结果：结构化语义路由与协作复核显著提升复杂请求匹配准确率", "一页讲清 78.76% → 87.61% → 88.50% → 92.92%。", "11")
    add_box(s, 0.72, 1.22, 7.9, 4.65, fill="ffffff", line="c8dbef")
    add_picture(s, FIG_DIR / "01_pooled_test_waterfall.png", 1.0, 1.52, 7.28, 3.95)
    metrics = [("78.76%", "规则路由基线", "muted"), ("87.61%", "结构化语义路由", "blue"), ("88.50%", "默认协作复核", "orange2"), ("92.92%", "扩展协作配置", "red")]
    for i, (v, l, col) in enumerate(metrics):
        add_box(s, 8.95, 1.28 + i * 1.0, 2.8, 0.72, fill="ffffff" if i != 3 else "fff1f1", line="c8dbef" if i != 3 else "f1c3c3")
        add_text(s, v, 9.2, 1.45 + i * 1.0, 1.2, 0.22, size=17.5, color=col, bold=True, font="Arial")
        add_text(s, l, 10.42, 1.48 + i * 1.0, 1.05, 0.14, size=7.8, color="muted")
    add_text(s, "结论：结构化语义判别提供主要增益；职责化协作复核集中处理边界冲突，扩展配置 5 次改写全部有效修正、0 次误改。", 0.92, 6.18, 10.2, 0.24, size=12.8, color="ink", bold=True)
    add_footer(s, 11)


def collaboration_case(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "协作复核有效性：角色分工带来复杂样本受控净修正", "不重复主结果，用消融和案例证明多智能体不是堆角色。", "12")
    add_box(s, 0.72, 1.26, 5.55, 3.45, fill="ffffff", line="c8dbef")
    add_text(s, "配对消融测试准确率", 1.05, 1.55, 1.8, 0.2, size=14.5, color="ink", bold=True)
    groups = [("单角色", 0.8625, "blue"), ("同质复核", 0.8625, "purple"), ("职责化协作", 0.9250, "orange2")]
    base_y = 4.35
    for i, (name, val, col) in enumerate(groups):
        x = 1.4 + i * 1.35
        h = (val - 0.84) / 0.10 * 1.9
        add_box(s, x, base_y - h, 0.54, h, fill=C[col], line=C[col], radius=False)
        add_text(s, f"{val:.4f}", x - 0.15, base_y - h - 0.22, 0.85, 0.14, size=7.6, color=col, bold=True, align="center", font="Arial")
        add_text(s, name, x - 0.32, 4.52, 1.1, 0.14, size=8.4, color="muted", align="center")
    add_box(s, 6.72, 1.26, 4.95, 3.45, fill="ffffff", line="c8dbef")
    add_text(s, "典型案例", 7.05, 1.55, 1.0, 0.2, size=14.5, color="green", bold=True)
    add_text(s, "请求语义：请把驻场培训周内容压缩成一页领导评审材料，先搭材料骨架。", 7.05, 1.95, 3.55, 0.28, size=10.5, color="ink", bold=True)
    add_text(s, "单智能体误判", 7.05, 2.62, 1.05, 0.14, size=8.5, color="muted")
    add_text(s, "course.education.cn", 8.08, 2.6, 1.5, 0.14, size=9.4, color="red", bold=True, font="Arial")
    add_text(s, "协作修正", 7.05, 3.02, 0.82, 0.14, size=8.5, color="muted")
    add_text(s, "docs.productivity.cn", 8.08, 3.0, 1.5, 0.14, size=9.4, color="green", bold=True, font="Arial")
    add_text(s, "修正依据：培训是背景词，主动作是搭骨架、压材料、梳结构。", 7.05, 3.48, 3.58, 0.22, size=9.0, color="muted")
    add_box(s, 1.0, 5.25, 10.4, 0.62, fill="e7f1ff", line="7fb5ee")
    add_text(s, "结论：单角色/同质复核测试侧没有超过基线；职责化协作复核提升 6.25 个百分点，测试侧改判/纠错/误改为 5/5/0。", 1.28, 5.48, 9.25, 0.18, size=11.8, color="ink", bold=True)
    add_footer(s, 12)


def prototype_outputs(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "原型系统与成果产出：形成可演示、可归档、可提交的成果包", "让评委看到“做出来了”，同时看到论文、技术报告、专利材料和成果汇编已经成套。", "13")
    if DEMO_IMG.exists():
        add_picture(s, DEMO_IMG, 0.72, 1.28, 6.7, 3.85)
    else:
        add_box(s, 0.72, 1.28, 6.7, 3.85, fill="ffffff", line="c8dbef")
        add_text(s, "原型系统截图待补", 2.4, 3.0, 2.0, 0.2, size=14, color="muted", bold=True)
    add_box(s, 7.78, 1.28, 3.85, 3.85, fill="071a46", line="1e83e6")
    add_text(s, "成果包", 8.1, 1.6, 1.0, 0.22, size=16, color="white", bold=True)
    for i, b in enumerate(["智能体能力命名与语义路由原型系统", "技术报告 v1.3", "论文投稿稿", "发明专利申请相关材料", "563 样本与实验图表资产", "成果汇编、宣传稿、验收报告"]):
        add_bullet(s, b, 8.12, 2.04 + i * 0.32, 2.7, color="cyan", size=8.6, text_color="d2e6ff")
    add_text(s, "原型覆盖：请求输入、候选能力召回、结构化裁决、协作复核、主能力/相关能力输出、候选 Agent 排序、执行状态和过程记录回放。", 0.86, 5.65, 10.4, 0.24, size=11.8, color="ink", bold=True)
    add_footer(s, 13)


def acceptance_table(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "考核指标完成情况：任务书要求均已落到证明材料", "少写形容词，多写完成情况和证明材料；专利正式受理号、展示证明按最终附件补充。", "14")
    rows = [
        ("多智能体协作原型框架", "已完成", "能力命名与语义路由控制台、原型截图/演示记录"),
        ("技术研究报告或论文", "已完成", "技术报告、论文投稿稿、成果汇编、验收报告填写版"),
        ("发明专利", "材料已形成", "交底书、权利要求、说明书摘要、附图；受理证明待补"),
        ("对内成果展示或汇报演示", "已形成支撑", "答辩 PPT、成果汇编、宣传稿、图表材料、演示截图"),
    ]
    x0, y0 = 0.78, 1.34
    widths = [3.0, 1.55, 6.95]
    for i, h in enumerate(["考核要求", "完成情况", "证明材料"]):
        add_box(s, x0 + sum(widths[:i]), y0, widths[i], 0.46, fill=C["navy2"], line=C["navy2"], radius=False)
        add_text(s, h, x0 + sum(widths[:i]) + 0.08, y0 + 0.12, widths[i] - 0.16, 0.16, size=9.8, color="white", bold=True, align="center")
    for r, row in enumerate(rows):
        y = y0 + 0.46 + r * 0.84
        for c, val in enumerate(row):
            add_box(s, x0 + sum(widths[:c]), y, widths[c], 0.84, fill="ffffff", line="dbe8f5", radius=False)
            col = "green" if c == 1 and val == "已完成" else ("orange2" if c == 1 else "ink")
            add_text(s, val, x0 + sum(widths[:c]) + 0.12, y + 0.27, widths[c] - 0.24, 0.2, size=10.0, color=col, bold=(c <= 1))
    add_box(s, 0.95, 5.48, 10.75, 0.62, fill="e7f1ff", line="7fb5ee")
    add_text(s, "验收材料包：原型系统、算法方法、数据实验、论文报告、知识产权、成果展示证明。", 1.22, 5.72, 8.8, 0.18, size=12.4, color="ink", bold=True)
    add_footer(s, 14)


def summary_next(prs):
    s = blank(prs)
    add_picture(s, base.STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "总结与后续工作", 0.76, 0.92, 2.8, 0.4, size=29, color="white", bold=True)
    add_line(s, 0.78, 1.5, 1.5, "cyan", 3)
    summary = [
        ("完成闭环", "构建面向互联网基础资源场景的能力命名、语义路由、协作复核和可信留痕原型链路。"),
        ("形成方法", "结构化语义判别与职责化协作复核结合，实现复杂样本受控净修正。"),
        ("沉淀成果", "形成原型系统、实验数据、论文报告、专利申请材料和成果汇编。"),
    ]
    for i, (t, b) in enumerate(summary):
        y = 2.05 + i * 0.78
        add_circle(s, 0.96, y, 0.34, ["cyan", "orange", "green"][i])
        add_text(s, str(i + 1), 0.96, y + 0.09, 0.34, 0.14, size=8, color="navy", bold=True, align="center", valign="middle", font="Arial")
        add_text(s, t, 1.48, y, 1.1, 0.2, size=15, color="white", bold=True)
        add_text(s, b, 2.7, y + 0.02, 6.4, 0.18, size=10.6, color="d2e6ff")
    add_box(s, 0.82, 5.0, 9.25, 0.86, fill="0b3c7c", line="4c96e8", alpha=15000)
    add_text(s, "后续方向", 1.15, 5.28, 1.1, 0.2, size=15, color="cyan", bold=True)
    add_text(s, "扩展跨命名空间样本；补充时延、成本、失败恢复等在线指标；推进真实业务系统、可信审计机制和标准化接口联动。", 2.35, 5.28, 6.55, 0.2, size=10.8, color="white", bold=True)
    add_text(s, "谢谢，请各位专家批评指正", 0.78, 6.45, 3.8, 0.28, size=18, color="white", bold=True)
    add_text(s, "CNNIC", 11.58, 0.38, 1.1, 0.3, size=23, color="white", bold=True, align="right", font="Arial")
    add_text(s, "中国互联网络信息中心", 10.9, 0.7, 1.78, 0.18, size=8.5, color="d2e6ff", align="right")


def build():
    base.create_strong_assets()
    prs = base.new_presentation()
    for fn in [
        cover,
        background,
        task_focus,
        scenario_mapping,
        route_overview,
        namespace,
        structured_routing,
        multi_agent,
        trusted_trace,
        experiment_design,
        core_results,
        collaboration_case,
        prototype_outputs,
        acceptance_table,
        summary_next,
    ]:
        fn(prs)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
