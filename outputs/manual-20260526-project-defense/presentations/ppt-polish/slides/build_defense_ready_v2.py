from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image


ROOT = Path("/Users/xizhuxizhu/Desktop/IndProj04")
SRC_DIR = ROOT / "output/pptx/project_defense_20260426/src"
sys.path.insert(0, str(SRC_DIR))

import build_project_defense_deck_acceptance15 as acc  # noqa: E402
import build_project_defense_deck_formal18 as f18  # noqa: E402
import build_project_defense_deck_strong as base  # noqa: E402


OUTPUT = Path("/Users/xizhuxizhu/Downloads/重点项目验收答辩PPT_正式答辩版_v2_20260526.pptx")
WORKSPACE = Path("/Users/xizhuxizhu/Desktop/IndProj04/outputs/manual-20260526-project-defense/presentations/ppt-polish")
FIG_DIR = ROOT / "output/doc/gjtx_submission_20260413/figures"
PATENT_DIR = ROOT / "output/doc/574_patent_reply_figures_clean"
PDF_PATENT_DIR = ROOT / "output/doc/专利PDF附图版_20260413"

C = base.C
SLIDE_W, SLIDE_H = base.SLIDE_W, base.SLIDE_H

blank = base.blank
add_picture = base.add_picture
add_box = base.add_box
add_text = base.add_text
add_title = base.add_title
add_footer = base.add_footer
add_line = base.add_line
add_bullet = base.add_bullet


def fit_image(slide, file: Path, x, y, w, h):
    if file.exists():
        with Image.open(file) as im:
            iw, ih = im.size
        scale = min(w / iw, h / ih)
        ww = iw * scale
        hh = ih * scale
        add_picture(slide, file, x + (w - ww) / 2, y + (h - hh) / 2, ww, hh)
    else:
        add_box(slide, x, y, w, h, fill="ffffff", line="c8dbef")
        add_text(slide, f"图片待补：{file.name}", x + 0.25, y + h / 2 - 0.1, w - 0.5, 0.2, size=11, color="muted", align="center")


def correct_marker(slide, page):
    add_text(slide, f"{page:02d}", 0.52, 0.31, 0.74, 0.26, size=12, color="blue", bold=True, align="center", fill=C["pale2"], line=C["line"], radius=True, valign="middle")
    f18.correct_page(slide, page)


def agenda(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "答辩提纲：围绕任务完成、技术攻关、实验证据和成果交付展开", "主讲 18 页，备份 4 页；现场优先讲清任务书闭环和核心技术证据。", "02")
    items = [
        ("一", "研究背景与定位", "智能体服务接入后，能力发现与可信调用成为基础资源新问题"),
        ("二", "任务书完成闭环", "原型、算法、数据、论文报告、专利材料逐项落到证明材料"),
        ("三", "技术路线与攻关", "能力命名、结构化判别、职责化复核、可信留痕和执行映射"),
        ("四", "实验验证与案例", "冻结样本、核心结果、配对消融和典型纠错过程"),
        ("五", "成果交付与后续", "验收材料包、边界说明和工程化扩展方向"),
    ]
    for i, (idx, title, desc) in enumerate(items):
        x = 0.76 + i * 2.42
        add_box(s, x, 1.62, 1.9, 3.7, fill="ffffff", line=C[["blue", "green", "orange2", "purple", "red"][i]])
        add_text(s, idx, x + 0.68, 1.98, 0.5, 0.3, size=24, color=["blue", "green", "orange2", "purple", "red"][i], bold=True, align="center")
        add_text(s, title, x + 0.2, 2.72, 1.28, 0.26, size=12.2, color="ink", bold=True, align="center")
        add_text(s, desc, x + 0.22, 3.42, 1.25, 0.6, size=8.2, color="muted", align="center")
    add_box(s, 1.05, 5.92, 10.7, 0.54, fill="e7f1ff", line="7fb5ee")
    add_text(s, "答辩主线：先证明任务书完成，再证明技术上有攻关，最后用实验和原型证据支撑验收。", 1.35, 6.12, 8.9, 0.16, size=11.5, color="ink", bold=True)
    add_footer(s, 2)


def background(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "背景：智能体服务进入能力发现与可信调用阶段", "大模型应用从回答问题扩展到触发服务、调用工具和执行任务，基础资源支撑对象随之变化。", "02")
    left = [
        ("传统支撑对象", "域名 / 地址\n接口 / 平台\n资源 / 服务", "blue"),
        ("智能体时代扩展", "智能体能力\n候选实例\n任务入口\n过程证据", "green"),
    ]
    for i, (t, b, col) in enumerate(left):
        x = 0.82 + i * 2.48
        add_box(s, x, 1.48, 2.08, 2.2, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.26, 1.82, 1.2, 0.2, size=12.4, color=col, bold=True, align="center")
        add_text(s, b, x + 0.32, 2.34, 1.1, 0.76, size=10.5, color="ink", bold=True, align="center")
    rows = [
        ("能力对象如何组织", "不同来源、职责和执行边界需要统一描述"),
        ("请求如何指向能力", "主能力、相关能力和执行实例需要区分"),
        ("协作复核如何受控", "复杂语义、风险约束和层级冲突需要多视角判断"),
        ("过程如何审计核验", "候选、判断、复核、授权和执行需留痕"),
    ]
    add_box(s, 6.05, 1.24, 5.65, 3.22, fill="ffffff", line="c8dbef")
    add_text(s, "带来的关键问题", 6.36, 1.58, 1.55, 0.2, size=14.5, color="orange2", bold=True)
    for i, (t, b) in enumerate(rows):
        y = 2.02 + i * 0.54
        add_text(s, t, 6.38, y, 1.5, 0.15, size=9.2, color="ink", bold=True)
        add_text(s, b, 8.05, y, 2.75, 0.15, size=8.2, color="muted")
    add_box(s, 0.95, 5.35, 10.9, 0.66, fill="071a46", line="1e83e6")
    add_text(s, "本项目聚焦：能力组织、语义决策、协作复核与可信过程记录。", 1.3, 5.6, 7.9, 0.18, size=12.6, color="white", bold=True)
    add_footer(s, 2)


def data_protocol(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "数据资产与评测协议：冻结主口径，区分主结果、诊断结果与探索结果", "训练集用于配置选择，测试集用于一次性报告，避免后验调参。", "12")
    metrics = [("563", "总样本", "blue"), ("450", "train", "green"), ("113", "test", "orange2"), ("50", "能力节点", "purple"), ("45", "主标签", "red"), ("97.35%", "top-8 gold 覆盖", "blue2")]
    for i, (v, l, col) in enumerate(metrics):
        x = 0.72 + i * 1.82
        add_box(s, x, 1.22, 1.42, 0.76, fill="ffffff", line=C[col])
        add_text(s, v, x + 0.08, 1.4, 1.18, 0.22, size=16.2 if len(v) > 4 else 18.5, color=col, bold=True, align="center", font="Arial")
        add_text(s, l, x + 0.08, 1.72, 1.18, 0.12, size=7.5, color="muted", align="center")
    fit_image(s, FIG_DIR / "07_eval_scale_stability.png", 0.82, 2.4, 6.65, 3.05)
    add_box(s, 7.78, 2.42, 3.95, 2.92, fill="ffffff", line="c8dbef")
    for i, (t, b, col) in enumerate([
        ("主结果", "只报告冻结 test=113", "blue"),
        ("诊断结果", "用于解释样本复杂度和稳定性", "green"),
        ("探索结果", "不混入主指标口径", "orange2"),
    ]):
        y = 2.78 + i * 0.72
        add_text(s, t, 8.1, y, 0.8, 0.16, size=9.8, color=col, bold=True)
        add_text(s, b, 9.05, y, 1.85, 0.16, size=8.1, color="muted")
    add_box(s, 0.95, 6.05, 10.8, 0.46, fill="e7f1ff", line="7fb5ee")
    add_text(s, "结论稳定性：样本池扩展后，规则路由、结构化判别、默认协作、扩展配置的相对排序没有被推翻。", 1.25, 6.22, 9.0, 0.12, size=10.2, color="ink", bold=True)
    add_footer(s, 12)


def ablation(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "配对消融：协作收益来自职责分工与授权控制", "不是简单“多问几个智能体”，职责化协作在完整配对消融中形成明显净收益。", "14")
    fit_image(s, FIG_DIR / "03_holdout3_collaboration_ablation.png", 0.75, 1.32, 6.95, 3.9)
    add_box(s, 8.05, 1.42, 3.75, 3.75, fill="ffffff", line="c8dbef")
    points = [
        ("不是多问一次", "单角色/同质复核测试侧没有明显超过基线", "blue"),
        ("异质证据有效", "四类职责分别处理不同冲突来源", "green"),
        ("授权控制误改", "职责化协作测试侧 92.50%，改判/纠错/误改为 5/5/0", "orange2"),
    ]
    for i, (t, b, col) in enumerate(points):
        y = 1.82 + i * 0.94
        add_text(s, f"0{i+1}", 8.38, y, 0.34, 0.16, size=9.5, color=col, bold=True, font="Arial")
        add_text(s, t, 8.82, y, 1.08, 0.16, size=9.5, color="ink", bold=True)
        add_text(s, b, 8.82, y + 0.3, 2.2, 0.24, size=7.8, color="muted")
    add_box(s, 0.95, 5.92, 10.8, 0.54, fill="e7f1ff", line="7fb5ee")
    add_text(s, "核心结论：协作收益来自“角色差异 + 授权控制”，而不是单纯增加模型调用次数。", 1.25, 6.12, 8.4, 0.16, size=11.1, color="ink", bold=True)
    add_footer(s, 14)


def acceptance_table(prs):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "考核指标完成情况：任务书要求逐项落到证明材料", "把验收指标转成完成情况和证明材料，而不是只列技术亮点。", "17")
    rows = [
        ("多智能体协作原型框架", "已完成", "能力命名、语义判别、职责化复核、授权改判、执行映射和过程记录链路"),
        ("至少 1 项发明专利", "材料已形成，流程推进中", "交底书、权利要求书、说明书摘要、附图；正式状态以管理记录为准"),
        ("技术研究报告或论文", "已完成", "技术报告、论文投稿稿、实验图表和方法说明"),
        ("成果展示或汇报演示", "已形成", "成果汇编、宣传稿、PPT、原型演示支撑材料"),
    ]
    x0, y0 = 0.72, 1.34
    widths = [3.05, 2.05, 6.55]
    for i, h in enumerate(["考核要求", "完成情况", "证明材料 / 答辩口径"]):
        add_box(s, x0 + sum(widths[:i]), y0, widths[i], 0.46, fill=C["navy2"], line=C["navy2"], radius=False)
        add_text(s, h, x0 + sum(widths[:i]) + 0.08, y0 + 0.12, widths[i] - 0.16, 0.16, size=9.8, color="white", bold=True, align="center")
    for r, row in enumerate(rows):
        y = y0 + 0.46 + r * 0.82
        for c, val in enumerate(row):
            add_box(s, x0 + sum(widths[:c]), y, widths[c], 0.82, fill="ffffff", line="dbe8f5", radius=False)
            col = "green" if c == 1 and val in {"已完成", "已形成"} else ("orange2" if c == 1 else "ink")
            add_text(s, val, x0 + sum(widths[:c]) + 0.12, y + 0.25, widths[c] - 0.24, 0.2, size=9.4, color=col, bold=(c <= 1))
    add_box(s, 0.95, 5.55, 10.8, 0.64, fill="fff8e8", line="f2d58b")
    add_text(s, "边界说明：本期成果定位为研究原型和方法验证；生产级 DNS 解析、端到端业务联调、强密码学可信审计链属于后续工程化方向。", 1.22, 5.78, 9.45, 0.18, size=10.8, color="ink", bold=True)
    add_footer(s, 17)


def backup_slide(prs, page, title, subtitle, image, caption):
    s = blank(prs)
    add_picture(s, base.ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, title, subtitle, f"备份 {page - 18}")
    add_box(s, 0.82, 1.06, 11.0, 5.05, fill="ffffff", line="c8dbef")
    fit_image(s, image, 1.02, 1.28, 10.6, 4.58)
    add_box(s, 1.0, 6.24, 10.65, 0.44, fill="e7f1ff", line="7fb5ee")
    add_text(s, caption, 1.3, 6.4, 9.1, 0.12, size=9.8, color="ink", bold=True)
    add_footer(s, page)


def build():
    base.create_strong_assets()
    prs = base.new_presentation()
    f18.cover(prs)
    background(prs)
    f18.task_completion_overview(prs)
    correct_marker(prs.slides[-1], 3)
    f18.positioning(prs)
    correct_marker(prs.slides[-1], 4)
    acc.route_overview(prs)
    correct_marker(prs.slides[-1], 5)
    f18.hard_challenges(prs)
    correct_marker(prs.slides[-1], 6)
    acc.namespace(prs)
    correct_marker(prs.slides[-1], 7)
    acc.structured_routing(prs)
    correct_marker(prs.slides[-1], 8)
    acc.multi_agent(prs)
    correct_marker(prs.slides[-1], 9)
    acc.trusted_trace(prs)
    correct_marker(prs.slides[-1], 10)
    f18.prototype_system(prs)
    correct_marker(prs.slides[-1], 11)
    data_protocol(prs)
    acc.core_results(prs)
    correct_marker(prs.slides[-1], 13)
    ablation(prs)
    f18.case_flow(prs)
    correct_marker(prs.slides[-1], 15)
    f18.outputs_package(prs)
    correct_marker(prs.slides[-1], 16)
    acceptance_table(prs)
    f18.final_summary(prs)
    backup_slide(
        prs,
        19,
        "备份图 A：不同协作配置下的训练集 / 测试集表现",
        "用于回答“为什么有默认、选择性、扩展配置”的追问。",
        FIG_DIR / "03_holdout3_collaboration_ablation.png",
        "可说明职责化协作在训练侧和测试侧均优于单角色/同质复核。",
    )
    backup_slide(
        prs,
        20,
        "备份图 B：执行实例过滤与排序流程",
        "用于回答 Stage C 如何从能力地址落到具体 Agent。",
        PATENT_DIR / "图4_实例过滤与排序过程示意图.png",
        "先按能力地址硬过滤，再结合端点、schema、健康状态和可用状态排序。",
    )
    backup_slide(
        prs,
        21,
        "备份图 C：结构化决策轨迹字段组",
        "用于回答可信留痕记录哪些对象。",
        PATENT_DIR / "图5_结构化决策轨迹数据组织示意图.png",
        "候选快照、裁决包、角色提案、授权判断和执行映射共同构成可回放轨迹。",
    )
    backup_slide(
        prs,
        22,
        "备份图 D：语义能力地址与实例地址两层关系",
        "用于回答“地址、发现、命名”的边界。",
        PATENT_DIR / "图2_两层地址关系示意图.png",
        "能力地址回答哪类能力处理，实例地址回答哪个智能体执行，两者限定在原型逻辑地址层。",
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
