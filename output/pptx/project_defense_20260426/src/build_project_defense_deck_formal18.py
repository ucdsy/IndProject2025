from __future__ import annotations

from pathlib import Path

import build_project_defense_deck_acceptance15 as acc
import build_project_defense_deck_strong as base


ROOT = Path("/Users/xizhuxizhu/Desktop/IndProj04")
OUT_DIR = ROOT / "output/pptx/project_defense_20260426"
OUTPUT = OUT_DIR / "项目评审答辩PPT_正式验收18页版_20260524.pptx"
FIG_DIR = ROOT / "output/doc/gjtx_submission_20260413/figures"
DEMO_IMG = ROOT / "output/playwright/agentdnsdemo_risk_flow_adjusted.png"

C = base.C
SLIDE_W, SLIDE_H = base.SLIDE_W, base.SLIDE_H

blank = base.blank
add_picture = base.add_picture
add_box = base.add_box
add_text = base.add_text
add_title = base.add_title
add_footer = base.add_footer
add_line = base.add_line
add_circle = base.add_circle
add_bullet = base.add_bullet


def arrow(slide, x, y):
    add_text(slide, "→", x, y, 0.25, 0.18, size=15, color="muted", bold=True, align="center", font="Arial")


def correct_page(slide, page):
    add_text(slide, "", 12.02, 7.04, 0.76, 0.28, size=1, fill="edf6ff", line="edf6ff")
    add_text(slide, f"{page:02d}", 12.2, 7.11, 0.42, 0.18, size=8, color="muted", align="right", font="Arial")


def cover(prs):
    s = blank(prs)
    add_picture(s, base.STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "重点项目验收答辩", 0.72, 0.68, 2.45, 0.28, size=16, color="cyan", bold=True)
    add_line(s, 0.72, 1.06, 1.72, "cyan", 3)
    add_text(s, "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究", 0.72, 1.42, 8.7, 1.0, size=30, color="white", bold=True)
    add_text(s, "以智能体能力命名与语义路由为典型验证场景", 0.75, 2.73, 6.5, 0.35, size=15.8, color="cfe4ff")
    metrics = [("563", "冻结样本"), ("50/45", "能力节点/主标签"), ("88.50%", "默认协作准确率"), ("92.92%", "扩展配置准确率")]
    for i, (v, l) in enumerate(metrics):
        x = 0.78 + i * 2.18
        add_box(s, x, 4.25, 1.86, 0.76, fill="0b3c7c", line="4c96e8", alpha=16000)
        add_text(s, v, x + 0.08, 4.37, 1.7, 0.28, size=18.2 if len(v) > 5 else 20, color="white", bold=True, align="center", font="Arial")
        add_text(s, l, x + 0.08, 4.72, 1.7, 0.18, size=8.6, color="d2e6ff", align="center")
    add_text(s, "承研处所：技术发展所    项目负责人：邓斯宇    起止时间：2025年5月-2026年4月", 0.74, 6.62, 7.4, 0.25, size=11, color="d2e6ff")
    add_text(s, "CNNIC", 11.58, 0.38, 1.1, 0.3, size=23, color="white", bold=True, align="right", font="Arial")
    add_text(s, "中国互联网络信息中心", 10.9, 0.7, 1.78, 0.18, size=8.5, color="d2e6ff", align="right")


def task_completion_overview(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "任务书要求与完成总览：原型、算法、数据、论文报告和专利材料均已形成", "把任务书要求前置，让专家先看到验收闭环，再进入技术细节。", "03")
    rows = [
        ("多智能体协作原型", "已完成", "能力目录、候选组织、协作复核、过程回放和实例映射"),
        ("协作与共识算法", "已完成", "结构化语义判别、四角色复核、显式授权改判"),
        ("真实标签反馈验证", "已完成", "563 样本、450/113 冻结划分、主结果与消融实验"),
        ("论文报告与成果材料", "已完成", "技术报告、论文投稿稿、成果汇编、答辩材料"),
        ("发明专利", "材料已形成", "交底书、权利要求、说明书摘要和附图；受理证明按流程补充"),
    ]
    x0, y0 = 0.72, 1.24
    widths = [3.0, 1.45, 7.25]
    for i, h in enumerate(["任务书要求", "完成情况", "验收证明"]):
        add_box(s, x0 + sum(widths[:i]), y0, widths[i], 0.42, fill=C["navy2"], line=C["navy2"], radius=False)
        add_text(s, h, x0 + sum(widths[:i]) + 0.08, y0 + 0.11, widths[i] - 0.16, 0.14, size=9.3, color="white", bold=True, align="center")
    for r, row in enumerate(rows):
        y = y0 + 0.42 + r * 0.67
        for c, val in enumerate(row):
            add_box(s, x0 + sum(widths[:c]), y, widths[c], 0.67, fill="ffffff", line="dbe8f5", radius=False)
            col = "green" if c == 1 and val == "已完成" else ("orange2" if c == 1 else "ink")
            add_text(s, val, x0 + sum(widths[:c]) + 0.12, y + 0.2, widths[c] - 0.24, 0.18, size=9.4, color=col, bold=(c <= 1))
    add_box(s, 0.95, 5.42, 10.75, 0.68, fill="e7f1ff", line="7fb5ee")
    add_text(s, "验收判断", 1.25, 5.68, 1.0, 0.18, size=12.8, color="blue", bold=True)
    add_text(s, "任务完成不是只交材料，而是形成“技术路线—系统原型—冻结实验—成果材料”的可核验证据链。", 2.35, 5.68, 7.55, 0.18, size=11.2, color="ink", bold=True)
    add_footer(s, 3)


def positioning(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究定位：语义路由是典型验证场景，不是项目主题偏移", "主动回答“是不是只做分类任务”的质疑，说明项目主线如何落到可评测链路。", "04")
    steps = [
        ("能力命名", "能力对象如何组织"),
        ("候选选择", "请求如何进入固定候选"),
        ("结构化判别", "主能力和相关能力如何给出"),
        ("协作复核", "复杂边界样本如何受控改判"),
        ("过程留痕", "判断过程如何核验"),
        ("实例映射", "哪个 Agent 承接执行"),
    ]
    for i, (t, b) in enumerate(steps):
        x = 0.55 + i * 2.05
        col = ["blue", "green", "orange2", "purple", "red", "blue2"][i]
        add_box(s, x, 1.55, 1.58, 1.06, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.18, 1.82, 1.05, 0.18, size=10.2, color=col, bold=True, align="center")
        add_text(s, b, x + 0.18, 2.23, 1.05, 0.16, size=7.8, color="muted", align="center")
        if i < 5:
            arrow(s, x + 1.68, 1.98)
    add_box(s, 0.95, 3.42, 10.9, 0.9, fill="071a46", line="1e83e6")
    add_text(s, "主线", 1.25, 3.72, 0.7, 0.18, size=13, color="cyan", bold=True)
    add_text(s, "项目主线是“大模型多智能体协作与可信认知标识”；语义路由承担场景验证和原型评测作用。", 2.05, 3.69, 7.75, 0.22, size=12, color="white", bold=True)
    add_box(s, 0.95, 4.78, 10.9, 0.62, fill="fff8e8", line="f2d58b")
    add_text(s, "边界", 1.25, 5.0, 0.65, 0.16, size=11.6, color="orange2", bold=True)
    add_text(s, "“命名、地址、发现、路由”限定在智能体能力目录和实例映射范围内，不涉及现网域名注册、权威解析或递归解析。", 2.02, 4.99, 8.2, 0.16, size=9.6, color="ink", bold=True)
    add_footer(s, 4)


def hard_challenges(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "攻关难点：固定候选内的复杂语义决策必须可控、可复核、可追溯", "重点项目的技术难点不在“能不能调用模型”，而在复杂请求边界下如何稳定做出受控裁决。", "06")
    items = [
        ("候选固定", "不能生成候选外能力地址，必须在既有能力空间内稳定比较。", "blue"),
        ("语义复合", "一个请求常同时包含主任务、辅助诉求、约束条件和背景词。", "green"),
        ("层级冲突", "父子节点、相邻域和实例能力粒度容易互相竞争。", "orange2"),
        ("复核受控", "多智能体不能越讨论越乱，改判必须有门槛和记录。", "purple"),
    ]
    for i, (t, b, col) in enumerate(items):
        x = 0.88 + (i % 2) * 5.72
        y = 1.42 + (i // 2) * 1.38
        add_box(s, x, y, 4.75, 1.04, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.22, y + 0.25, 1.0, 0.18, size=12.8, color=col, bold=True)
        add_text(s, b, x + 1.35, y + 0.2, 2.75, 0.24, size=9.4, color="muted")
    add_box(s, 1.0, 4.78, 10.65, 0.76, fill="071a46", line="1e83e6")
    add_text(s, "攻关抓手", 1.3, 5.04, 1.1, 0.18, size=13.2, color="cyan", bold=True)
    add_text(s, "用能力命名空间约束边界，用结构化裁决压缩不确定性，用职责化复核处理冲突，用可信轨迹支撑回放核验。", 2.52, 5.02, 7.9, 0.2, size=11.2, color="white", bold=True)
    add_footer(s, 6)


def case_flow(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "典型案例：复核将“培训背景词”从主任务中剥离，完成受控纠错", "只保留一个强案例，用流程说明误判、触发、角色意见、授权门槛和最终改判。", "14")
    flow = [
        ("输入请求", "请把驻场培训周内容压缩成一页领导评审材料，先搭材料骨架。", "blue"),
        ("单智能体误判", "course.education.cn\n把“培训周”误当主任务", "red"),
        ("触发复核", "低置信 + 主动作冲突\n进入职责化复核", "orange2"),
        ("四角色意见", "任务匹配/层级解析支持文档处理\n风险角色未发现阻断项", "purple"),
        ("授权改判", "满足票数、证据强度和共识增益\n改为 docs.productivity.cn", "green"),
    ]
    for i, (t, b, col) in enumerate(flow):
        x = 0.52 + i * 2.45
        add_box(s, x, 1.62, 2.0, 1.54, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.18, 1.9, 1.2, 0.18, size=10.6, color=col, bold=True, align="center")
        add_text(s, b, x + 0.16, 2.32, 1.42, 0.32, size=8.2, color="muted", align="center")
        if i < 4:
            arrow(s, x + 2.07, 2.22)
    add_box(s, 0.95, 4.35, 10.9, 0.92, fill="e7f1ff", line="7fb5ee")
    add_text(s, "技术含义", 1.25, 4.66, 1.0, 0.18, size=13, color="blue", bold=True)
    add_text(s, "协作不是增加口径，而是拆分背景词、主动作、材料产出证据和候选竞争关系，再用授权门槛控制改判风险。", 2.35, 4.62, 8.4, 0.22, size=10.4, color="ink", bold=True)
    add_text(s, "测试侧改判/纠错/误改：5/5/0", 1.1, 5.78, 2.5, 0.18, size=12.6, color="green", bold=True)
    add_footer(s, 14)


def prototype_system(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "原型系统已覆盖请求输入、候选组织、协作复核、过程记录和执行映射", "验收现场重点展示系统能跑、能看、能回放，而不是展示代码模块清单。", "15")
    if DEMO_IMG.exists():
        add_picture(s, DEMO_IMG, 0.68, 1.24, 7.15, 4.16)
    else:
        add_box(s, 0.68, 1.24, 7.15, 4.16, fill="ffffff", line="c8dbef")
        add_text(s, "原型系统截图待补", 2.6, 3.1, 2.0, 0.22, size=14, color="muted", bold=True)
    add_box(s, 8.15, 1.24, 3.55, 4.16, fill="071a46", line="1e83e6")
    add_text(s, "演示证据", 8.48, 1.58, 1.2, 0.22, size=16, color="white", bold=True)
    for i, b in enumerate(["自然语言请求输入", "候选能力召回与高亮", "结构化裁决与协作复核", "主能力/相关能力输出", "候选 Agent 排序", "执行状态与过程记录回放"]):
        add_bullet(s, b, 8.5, 2.05 + i * 0.34, 2.4, color="cyan", size=8.5, text_color="d2e6ff")
    add_text(s, "原型价值：把方法链路固化为可演示系统，支撑专家现场核验技术路线是否真正落地。", 0.9, 6.0, 9.8, 0.22, size=12.2, color="ink", bold=True)
    add_footer(s, 15)


def outputs_package(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "成果产出与验收材料包：五类成果支撑项目结题", "材料表述统一为已形成、可提交、可核验；专利正式受理证明按流程补充。", "16")
    add_picture(s, base.STRONG_ASSET_DIR / "evidence_wall.png", 0.68, 1.18, 7.7, 4.0)
    add_box(s, 8.7, 1.18, 3.3, 4.0, fill="ffffff", line="c8dbef")
    for i, (t, b, col) in enumerate([
        ("原型系统", "能力命名与语义路由控制台", "blue"),
        ("报告/论文", "技术报告、论文投稿稿", "green"),
        ("专利材料", "申请材料已形成，受理证明待补", "orange2"),
        ("数据实验资产", "样本、脚本、图表、消融记录", "purple"),
        ("成果汇编/宣传", "成果汇编、宣传稿、答辩材料", "red"),
    ]):
        y = 1.52 + i * 0.66
        add_text(s, t, 9.02, y, 1.0, 0.16, size=9.4, color=col, bold=True)
        add_text(s, b, 10.05, y, 1.45, 0.16, size=7.7, color="muted")
    add_box(s, 0.95, 5.72, 10.8, 0.58, fill="e7f1ff", line="7fb5ee")
    add_text(s, "验收材料包建议按“原型系统、算法方法、数据实验、论文报告、知识产权、展示证明”六类归档。", 1.22, 5.94, 9.0, 0.16, size=11.2, color="ink", bold=True)
    add_footer(s, 16)


def boundary_next(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "成果边界清晰，具备后续工程化扩展基础", "提前回答外推性、运行成本、真实系统联调和可信强度追问，但不把边界写成弱项。", "17")
    items = [
        ("验证范围", "当前验证建立在冻结样本与诊断池上，后续扩展跨命名空间独立样本。", "blue"),
        ("在线指标", "已记录触发率与修正收益，后续补充 token、时延、成本和失败恢复。", "green"),
        ("业务联动", "当前为演示原型，后续推进与真实业务系统、服务发现接口联调。", "orange2"),
        ("可信机制", "当前实现工程审计与可回放，后续可加入 hash-chain 与篡改检测。", "purple"),
    ]
    for i, (t, b, col) in enumerate(items):
        x = 0.88 + (i % 2) * 5.72
        y = 1.35 + (i // 2) * 1.34
        add_box(s, x, y, 4.75, 1.0, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.22, y + 0.25, 0.92, 0.16, size=11.8, color=col, bold=True)
        add_text(s, b, x + 1.28, y + 0.19, 2.9, 0.24, size=8.8, color="muted")
    add_box(s, 1.0, 4.78, 10.65, 0.76, fill="071a46", line="1e83e6")
    add_text(s, "后续重点", 1.3, 5.04, 1.1, 0.18, size=13.2, color="cyan", bold=True)
    add_text(s, "扩大验证范围、完善质量/成本/时延日志、推动演示端联调、凝练标准化接口与业务试点。", 2.52, 5.02, 7.4, 0.2, size=11.4, color="white", bold=True)
    add_footer(s, 17)


def final_summary(prs):
    s = blank(prs)
    add_picture(s, base.STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "总结", 0.76, 0.92, 1.35, 0.4, size=30, color="white", bold=True)
    add_line(s, 0.78, 1.5, 1.5, "cyan", 3)
    points = [
        ("完成任务书验收指标", "原型、算法、数据实验、论文报告、专利申请材料和成果展示材料均已形成。"),
        ("形成技术闭环", "能力命名—语义路由—协作复核—可信留痕—执行映射贯通。"),
        ("支撑后续深化", "可面向 AgentDNS、智能体标识、服务发现与治理审计继续扩展。"),
    ]
    for i, (t, b) in enumerate(points):
        y = 2.1 + i * 0.86
        add_circle(s, 0.96, y, 0.34, ["cyan", "orange", "green"][i])
        add_text(s, str(i + 1), 0.96, y + 0.09, 0.34, 0.14, size=8, color="navy", bold=True, align="center", valign="middle", font="Arial")
        add_text(s, t, 1.5, y, 1.85, 0.22, size=15.8, color="white", bold=True)
        add_text(s, b, 3.55, y + 0.02, 6.4, 0.18, size=10.8, color="d2e6ff")
    add_box(s, 0.82, 5.42, 8.95, 0.62, fill="0b3c7c", line="4c96e8", alpha=15000)
    add_text(s, "答辩主线：任务完成有对照，技术攻关有机制，实验结果有数据，成果交付有材料。", 1.15, 5.64, 7.5, 0.18, size=11.6, color="white", bold=True)
    add_text(s, "谢谢，请各位专家批评指正", 0.78, 6.45, 3.8, 0.28, size=18, color="white", bold=True)
    add_text(s, "CNNIC", 11.58, 0.38, 1.1, 0.3, size=23, color="white", bold=True, align="right", font="Arial")
    add_text(s, "中国互联网络信息中心", 10.9, 0.7, 1.78, 0.18, size=8.5, color="d2e6ff", align="right")


def build():
    base.create_strong_assets()
    prs = base.new_presentation()
    cover(prs)
    acc.background(prs)
    task_completion_overview(prs)
    positioning(prs)
    acc.route_overview(prs)
    hard_challenges(prs)
    for fn, page in [
        (acc.namespace, 7),
        (acc.structured_routing, 8),
        (acc.multi_agent, 9),
        (acc.trusted_trace, 10),
        (acc.experiment_design, 11),
        (acc.core_results, 12),
        (acc.collaboration_case, 13),
    ]:
        fn(prs)
        correct_page(prs.slides[-1], page)
    case_flow(prs)
    prototype_system(prs)
    outputs_package(prs)
    boundary_next(prs)
    final_summary(prs)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
