from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path("/Users/xizhuxizhu/Desktop/IndProj04")
OUT_DIR = ROOT / "output/pptx/project_defense_20260426"
ASSET_DIR = OUT_DIR / "scratch/assets"
STRONG_ASSET_DIR = OUT_DIR / "scratch/strong_assets"
OUTPUT = OUT_DIR / "项目评审答辩PPT_成果汇编口径版_20260524.pptx"
PAPER_DIR = ROOT / "output/doc/gjtx_submission_20260413"
FIG_DIR = PAPER_DIR / "figures"

SLIDE_W, SLIDE_H = 13.333333, 7.5

C = {
    "navy": "061a46",
    "navy2": "082b6d",
    "blue": "0b63ce",
    "blue2": "1e83e6",
    "cyan": "26b6ff",
    "pale": "f2f7ff",
    "pale2": "e7f1ff",
    "line": "c8dbef",
    "ink": "102033",
    "muted": "53657a",
    "orange": "f4b000",
    "orange2": "e97132",
    "green": "0e8a57",
    "red": "b93232",
    "purple": "6b49c8",
    "white": "ffffff",
}


def rgb(hex_color: str) -> RGBColor:
    hex_color = hex_color.strip("#")
    return RGBColor(int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:], 16))


def pos(x, y, w, h):
    return Inches(x), Inches(y), Inches(w), Inches(h)


def add_bg(slide, name: str):
    slide.shapes.add_picture(str(ASSET_DIR / name), *pos(0, 0, SLIDE_W, SLIDE_H))


def add_text(
    slide,
    text,
    x,
    y,
    w,
    h,
    size=16,
    color="ink",
    bold=False,
    align="left",
    font="Microsoft YaHei",
    fill=None,
    line=None,
    radius=False,
    valign="top",
):
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if radius else MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        *pos(x, y, w, h),
    )
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
    if line:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(0.9)
    else:
        shape.line.fill.background()
    tf = shape.text_frame
    tf.clear()
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = {
        "top": MSO_ANCHOR.TOP,
        "middle": MSO_ANCHOR.MIDDLE,
        "bottom": MSO_ANCHOR.BOTTOM,
    }[valign]
    p = tf.paragraphs[0]
    p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
    r = p.add_run()
    r.text = text
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = rgb(C.get(color, color))
    return shape


def add_box(slide, x, y, w, h, fill="ffffff", line="c8dbef", radius=True, alpha=0):
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if radius else MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        *pos(x, y, w, h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.fill.transparency = alpha
    shape.line.color.rgb = rgb(line)
    shape.line.width = Pt(1)
    return shape


def add_line(slide, x, y, w, color="line", weight=1.2):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, *pos(x, y, w, 0.01))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(C.get(color, color))
    shape.line.fill.background()
    shape.height = Pt(weight)
    return shape


def add_circle(slide, x, y, d, fill):
    shape = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.OVAL, *pos(x, y, d, d))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(C.get(fill, fill))
    shape.line.fill.background()
    return shape


def add_picture(slide, file: Path, x, y, w, h):
    slide.shapes.add_picture(str(file), *pos(x, y, w, h))


def add_title(slide, title, subtitle="", sec=""):
    add_box(slide, 0, 0, SLIDE_W, 0.12, fill=C["navy2"], line=C["navy2"], radius=False)
    add_box(slide, 0, 0.12, SLIDE_W, 0.035, fill=C["blue2"], line=C["blue2"], radius=False)
    if sec:
        add_text(slide, sec, 0.52, 0.31, 0.74, 0.26, size=12, color="blue", bold=True, align="center", fill=C["pale2"], line=C["line"], radius=True, valign="middle")
        x0 = 1.42
    else:
        x0 = 0.52
    add_text(slide, title, x0, 0.26, 9.2, 0.42, size=22, color="ink", bold=True)
    if subtitle:
        add_text(slide, subtitle, x0, 0.68, 9.4, 0.26, size=10.8, color="muted")
    add_text(slide, "CNNIC", 11.7, 0.28, 1.1, 0.28, size=21, color="blue", bold=True, align="right", font="Arial")
    add_text(slide, "中国互联网络信息中心", 10.95, 0.58, 1.85, 0.18, size=8.5, color="muted", align="right")


def add_footer(slide, page):
    add_line(slide, 0.52, 7.08, 9.4, "line", 0.8)
    add_text(slide, "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究", 0.52, 7.15, 6.0, 0.18, size=7.5, color="muted")
    add_text(slide, f"{page:02d}", 12.2, 7.11, 0.42, 0.18, size=8, color="muted", align="right", font="Arial")


def add_bullet(slide, text, x, y, w, color="blue", size=12, text_color="ink"):
    add_circle(slide, x, y + 0.06, 0.075, color)
    add_text(slide, text, x + 0.18, y, w, 0.24, size=size, color=text_color)


def create_strong_assets():
    STRONG_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    # Evidence wall: paper pages + patent figures + report artefacts with shadows.
    sources = [
        ROOT / "output/doc/gjtx_submission_20260413/current_page_1.png",
        ROOT / "output/doc/gjtx_submission_20260413/page_preview_figs_03.png",
        ROOT / "output/doc/专利PDF附图版_20260413/图1_系统总体结构示意图.png",
        ROOT / "output/doc/专利PDF附图版_20260413/图3_协同决策结构示意图.png",
        ROOT / "output/doc/项目成果宣传稿_公众号版_架构图.png",
    ]
    canvas = Image.new("RGBA", (1500, 780), (246, 250, 255, 255))
    draw = ImageDraw.Draw(canvas)
    positions = [(70, 74, 330, 470), (380, 145, 330, 470), (730, 88, 330, 265), (1010, 215, 330, 265), (720, 430, 610, 110)]
    for src, (x, y, w, h) in zip(sources, positions):
        if not src.exists():
            continue
        im = Image.open(src).convert("RGBA")
        im.thumbnail((w, h), Image.LANCZOS)
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), fill=(0, 40, 80, 70))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        canvas.alpha_composite(shadow, (x + 12, y + 12))
        canvas.alpha_composite(im, (x, y))
    draw.text((72, 616), "论文稿 / 技术报告 / 专利附图 / 宣传图示 / 验收材料", fill=(13, 45, 92))
    canvas.save(STRONG_ASSET_DIR / "evidence_wall.png")

    # A simple dark semantic network background crop for section slides.
    base = Image.open(ASSET_DIR / "cover_bg.png").convert("RGBA")
    dark = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(dark)
    dd.rectangle((0, 0, base.size[0], base.size[1]), fill=(0, 5, 20, 48))
    Image.alpha_composite(base, dark).save(STRONG_ASSET_DIR / "cover_bg_deep.png")


def new_presentation():
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def slide_cover(prs):
    s = blank(prs)
    add_picture(s, STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "重点项目验收答辩｜成果汇编口径版", 0.72, 0.68, 3.55, 0.28, size=16, color="cyan", bold=True)
    add_line(s, 0.72, 1.06, 1.72, "cyan", 3)
    add_text(s, "面向互联网基础资源的大模型多智能体协作与可信认知标识技术研究", 0.72, 1.44, 8.4, 1.02, size=30, color="white", bold=True)
    add_text(s, "以智能体能力命名与语义路由为典型验证场景，形成协作复核、可信留痕和原型验证闭环", 0.75, 2.72, 8.9, 0.35, size=15.8, color="cfe4ff")
    metrics = [("563", "真实样本冻结集"), ("50/45", "节点/主标签"), ("44.25%", "默认协作触发率"), ("5/5/0", "改判/纠错/误改")]
    for i, (v, l) in enumerate(metrics):
        x = 0.78 + i * 2.18
        add_box(s, x, 4.25, 1.86, 0.76, fill="0b3c7c", line="4c96e8", alpha=16000)
        add_text(s, v, x + 0.08, 4.37, 1.7, 0.28, size=17.4 if len(v) > 6 else 20, color="white", bold=True, align="center", font="Arial")
        add_text(s, l, x + 0.08, 4.72, 1.7, 0.18, size=8.6, color="d2e6ff", align="center")
    add_text(s, "承研处所：技术发展所    项目负责人：邓斯宇    起止时间：2025年5月-2026年4月", 0.74, 6.62, 7.4, 0.25, size=11, color="d2e6ff")
    add_text(s, "CNNIC", 11.58, 0.38, 1.1, 0.3, size=23, color="white", bold=True, align="right", font="Arial")
    add_text(s, "中国互联网络信息中心", 10.9, 0.7, 1.78, 0.18, size=8.5, color="d2e6ff", align="right")


def slide_verdict(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "成果汇编主线：从研究目标到验收证据的闭环", "PPT 按成果汇编重排：研究背景、研究重点、研究成果、研究产出、考核对应和成果边界一线贯通。", "01")
    add_text(s, "答辩判断", 0.72, 1.18, 1.5, 0.3, size=18, color="blue", bold=True)
    add_text(s, "用成果汇编做母本，技术报告负责机制深度，论文负责实验硬证据，PPT 负责把“已完成什么、为什么有技术含量、凭什么可验收”讲清楚。", 0.72, 1.58, 10.85, 0.42, size=17.2, color="ink", bold=True)
    steps = [
        ("研究目标", "能力命名、语义路由、协作复核、可信记录", "G"),
        ("研究成果", "命名空间、算法、原型、实验资产", "R"),
        ("成果产出", "原型、报告、论文、专利、数据实验", "O"),
        ("考核对应", "任务书指标逐项落到证明材料", "A"),
    ]
    for i, (t, b, tag) in enumerate(steps):
        x = 0.78 + i * 3.05
        col = ["blue", "green", "orange2", "purple"][i]
        add_box(s, x, 2.42, 2.55, 1.26, fill="ffffff", line=C[col])
        add_text(s, tag, x + 0.18, 2.64, 0.88, 0.24, size=12.5 if len(tag) > 4 else 16, color=col, bold=True, font="Arial")
        add_text(s, t, x + 1.02, 2.62, 1.15, 0.22, size=13.2, color="ink", bold=True)
        add_text(s, b, x + 0.2, 3.1, 1.95, 0.26, size=9.5, color="muted")
        if i < 3:
            add_line(s, x + 2.62, 3.05, 0.34, "blue2", 2.0)
    cards = [
        ("原型系统", "自然语言请求、候选组织、结构化裁决、协作复核、过程记录和执行映射。", "blue"),
        ("数据实验", "563 样本、50 节点、45 主标签、冻结 train/test、配对消融和稳定性分析。", "green"),
        ("论文报告", "技术报告承接任务书，论文提供问题定义、方法机制和实验验证。", "orange2"),
        ("专利材料", "交底书、权利要求、说明书摘要和附图已形成，正式状态待补证明。", "purple"),
    ]
    for i, (t, b, col) in enumerate(cards):
        x = 0.82 + (i % 2) * 5.9
        y = 4.25 + (i // 2) * 0.92
        add_box(s, x, y, 5.1, 0.68, fill="f8fbff", line=C[col])
        add_text(s, t, x + 0.18, y + 0.18, 1.15, 0.18, size=12.2, color=col, bold=True)
        add_text(s, b, x + 1.45, y + 0.15, 3.25, 0.24, size=9.5, color="muted")
    add_footer(s, 2)


def slide_agenda(prs):
    s = blank(prs)
    add_picture(s, STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "答辩提纲", 0.72, 0.72, 2.2, 0.48, size=30, color="white", bold=True)
    add_line(s, 0.74, 1.32, 1.6, "cyan", 3)
    items = [
        ("一", "研究背景与目标", "互联网基础资源智能化演进下的能力组织与可信调用问题"),
        ("二", "研究重点与路线", "能力命名、结构化判别、职责化复核、过程留痕"),
        ("三", "研究成果与验证", "原型系统、数据资产、算法结果、协作过程和典型案例"),
        ("四", "成果产出与考核", "报告、论文、专利、实验资产、展示材料逐项对应任务书"),
        ("五", "成果边界与后续", "明确原型边界、待补证明和后续深化方向"),
    ]
    for i, (n, t, b) in enumerate(items):
        y = 1.75 + i * 0.88
        add_circle(s, 1.0, y, 0.34, ["cyan", "orange", "green", "purple", "blue2"][i])
        add_text(s, n, 1.0, y + 0.06, 0.34, 0.18, size=9, color="navy", bold=True, align="center", valign="middle")
        add_text(s, t, 1.58, y - 0.03, 2.1, 0.28, size=17, color="white", bold=True)
        add_text(s, b, 3.7, y, 5.8, 0.24, size=11.5, color="d2e6ff")
    add_text(s, "主线：成果汇编管总，技术报告讲机制，论文给指标，PPT 把验收证据链讲成一条线。", 0.78, 6.52, 8.8, 0.3, size=14, color="d2e6ff", bold=True)


def slide_background(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "攻关难点：不是做一次分类，而是把可控候选决策做成系统能力", "论文更新后，技术难点已经清晰收敛到固定能力集合内的主能力选择、相关能力识别和受控复核。", "02")
    add_text(s, "四个硬约束", 0.72, 1.22, 2.0, 0.3, size=18, color="blue", bold=True)
    blocks = [
        ("候选固定", "平台已经给出能力目录，算法不能自由生成候选外地址，必须在候选内稳定比较。", "blue"),
        ("语义复合", "请求包含主任务、次要诉求、场景线索和治理约束，单一关键词规则容易误判。", "orange2"),
        ("层级冲突", "父子节点、同层竞争和可接受回落并存，需要区分合理回落与粒度错误。", "green"),
        ("复核受控", "多智能体不能无边界讨论，必须有触发条件、职责视图和改判授权门槛。", "purple"),
    ]
    for i, (t, b, col) in enumerate(blocks):
        x = 0.78 + (i % 2) * 6.08
        y = 1.78 + (i // 2) * 1.48
        add_box(s, x, y, 5.25, 1.12, fill="ffffff", line=C[col])
        add_text(s, f"0{i+1}", x + 0.24, y + 0.2, 0.52, 0.28, size=17, color=col, bold=True, font="Arial")
        add_text(s, t, x + 0.88, y + 0.19, 2.1, 0.25, size=16, color="ink", bold=True)
        add_text(s, b, x + 0.88, y + 0.58, 3.78, 0.32, size=10.6, color="muted")
    add_box(s, 0.9, 5.0, 11.2, 1.08, fill="071a46", line="1e83e6")
    add_text(s, "攻关抓手", 1.25, 5.3, 1.4, 0.28, size=16, color="cyan", bold=True)
    add_text(s, "把“自然语言请求到能力地址”定义为受限能力命名空间下的语义路由问题。", 2.72, 5.2, 8.35, 0.36, size=17, color="white", bold=True)
    add_text(s, "项目难度在于同时保证候选边界、语义判别、协作纠错、执行落点和过程审计五件事成立。", 2.73, 5.68, 8.15, 0.24, size=11.3, color="d2e6ff")
    add_footer(s, 4)


def slide_task_mapping(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "任务书到攻关闭环：每个考核点都对应技术难题和突破证据", "重点项目验收不只看材料是否齐备，更要看任务书要求如何转化为可验证的攻关成果。", "03")
    headers = ["任务书要求", "攻关难点", "突破结果与评审证据"]
    widths = [2.8, 4.05, 4.65]
    x0, y0 = 0.72, 1.32
    for i, h in enumerate(headers):
        add_box(s, x0 + sum(widths[:i]), y0, widths[i], 0.46, fill=C["navy2"], line=C["navy2"], radius=False)
        add_text(s, h, x0 + sum(widths[:i]) + 0.08, y0 + 0.12, widths[i] - 0.16, 0.18, size=11.5, color="white", bold=True, align="center")
    rows = [
        ("多智能体协作原型", "多角色只有形成互补职责并受授权约束才有净收益", "Stage B 四职责复核、第二轮定向比较、override gate"),
        ("可信认知标识", "可信要落在过程对象，而不是只给最终标签", "candidate snapshot、decision packet、trust trace、selection trace"),
        ("真实标签反馈约束", "无现成 benchmark，需要冻结协议并防止后验调参", "563 条真实样本、train=450/test=113、累计稳定性分析"),
        ("报告或论文", "前沿题目要有问题定义、方法公式和实验边界", "新版投稿稿、主结果表、补充配置、消融、案例分析"),
        ("发明专利", "系统流程要凝练成可保护的技术特征", "交底书、权利要求书、说明书摘要、系统结构与协同决策附图"),
    ]
    for r, row in enumerate(rows):
        y = y0 + 0.46 + r * 0.73
        for c, val in enumerate(row):
            add_box(s, x0 + sum(widths[:c]), y, widths[c], 0.73, fill="ffffff", line="dbe8f5", radius=False)
            add_text(s, val, x0 + sum(widths[:c]) + 0.12, y + 0.19, widths[c] - 0.24, 0.28, size=10.8, color="ink", bold=(c == 0))
    add_text(s, "答辩讲法：把“任务书要求—技术难点—突破证据”串成一条链，突出重点项目攻关属性。", 0.82, 6.18, 9.2, 0.28, size=14, color="ink", bold=True)
    add_footer(s, 5)


def slide_object(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "问题定义：受限能力命名空间内的能力地址语义路由", "给定请求 x 和候选集合 N，系统输出主能力 ŷ、相关能力 R̂ 和执行实例 â；正文重点评估前两项。", "04")
    add_box(s, 0.8, 1.46, 4.9, 3.25, fill="ffffff", line=C["blue"])
    add_text(s, "能力地址 routing_fqdn", 1.12, 1.82, 2.9, 0.3, size=19, color="blue", bold=True, font="Arial")
    add_text(s, "回答“哪一类能力应处理请求”", 1.12, 2.22, 3.2, 0.26, size=13, color="ink", bold=True)
    for i, e in enumerate(["policy.gov.cn", "coupon.commerce.cn", "docs.productivity.cn", "activity.travel.cn"]):
        add_text(s, e, 1.15, 2.72 + i * 0.38, 2.6, 0.22, size=12, color="muted", font="Arial")
    add_box(s, 7.3, 1.46, 4.9, 3.25, fill="ffffff", line=C["green"])
    add_text(s, "实例地址 agent_fqdn", 7.62, 1.82, 2.7, 0.3, size=19, color="green", bold=True, font="Arial")
    add_text(s, "回答“由哪个具体智能体执行”", 7.62, 2.22, 3.2, 0.26, size=13, color="ink", bold=True)
    for i, e in enumerate(["agent-xxx.agent.policy.gov.cn", "endpoint / schema / health", "exact routing_fqdn match", "不在执行层改写能力地址"]):
        add_text(s, e, 7.65, 2.72 + i * 0.38, 3.1, 0.22, size=12, color="muted", font="Arial")
    add_line(s, 5.9, 3.06, 1.1, "blue2", 2.5)
    add_text(s, "分层解耦", 5.86, 2.66, 1.22, 0.24, size=12, color="blue", bold=True, align="center")
    add_box(s, 1.05, 5.22, 10.8, 0.96, fill="e7f1ff", line="7fb5ee")
    add_text(s, "形式化约束：ŷ(x)∈N，R̂(x)⊆N\\{ŷ(x)}，â(x) 只在 A(ŷ) 内选择。", 1.3, 5.48, 8.7, 0.22, size=14, color="ink", bold=True, font="Arial")
    add_text(s, "这使 Stage R miss、Stage A 语义误判、Stage B 授权改判和 Stage C 实例过滤可以分别归因。", 1.3, 5.82, 8.8, 0.18, size=10, color="muted")
    add_footer(s, 6)


def slide_architecture(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "总体架构：四阶段路由链路 + 全程可信轨迹", "一条链路同时覆盖自然语言请求、候选集合、结构化裁决、协作复核、执行落点和过程记录。", "05")
    add_box(s, 0.62, 1.25, 12.1, 4.05, fill="ffffff", line="b7d3ef")
    add_picture(s, FIG_DIR / "fig1_framework.png", 0.9, 1.55, 11.5, 3.35)
    labels = [("Stage R", "候选集合构造", "blue"), ("Stage A", "结构化语义路由", "green"), ("Stage B", "职责化复核", "orange2"), ("Stage C", "执行落点解析", "purple"), ("Trace", "统一过程记录", "blue2")]
    for i, (a, b, col) in enumerate(labels):
        x = 0.83 + i * 2.45
        add_text(s, a, x, 5.64, 0.78, 0.22, size=13, color=col, bold=True, font="Arial")
        add_text(s, b, x + 0.8, 5.65, 1.3, 0.18, size=9.8, color="muted")
        add_line(s, x, 5.95, 1.9, "line", 0.8)
    add_text(s, "架构价值：以能力组织、语义裁决、协作复核和执行落点构成可演示闭环。", 0.86, 6.35, 7.6, 0.28, size=14, color="ink", bold=True)
    add_footer(s, 7)


def slide_review_architecture(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "复核架构：职责化协作复核流程与授权改判门禁", "第二张论文架构图用于说明 Stage B 内部如何从升级样本走到多角色提案、定向复核和最终授权。", "06")
    add_box(s, 0.62, 1.2, 12.1, 4.35, fill="ffffff", line="b7d3ef")
    add_picture(s, FIG_DIR / "fig2_review_flow.png", 0.86, 1.48, 11.6, 3.85)
    highlights = [
        ("入口", "低置信 / 小 margin / 高风险 / 多意图冲突"),
        ("角色", "任务匹配、治理风险、层级解析、用户偏好"),
        ("门禁", "票数、共识增益、显式证据、敏感改判二轮确认"),
    ]
    for i, (t, b) in enumerate(highlights):
        x = 0.86 + i * 3.9
        col = ["orange2", "green", "blue"][i]
        add_box(s, x, 5.84, 3.2, 0.64, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.2, 6.03, 0.62, 0.18, size=12.5, color=col, bold=True)
        add_text(s, b, x + 0.86, 5.99, 2.0, 0.2, size=8.8, color="muted")
    add_text(s, "这页补足第二张论文架构图：证明协作复核不是“再问一遍模型”，而是有入口、有分工、有门禁的受控纠错机制。", 0.92, 6.78, 10.7, 0.18, size=10.4, color="ink", bold=True)
    add_footer(s, 8)


def slide_stage_r(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究成果一（2/2）：能力命名空间与候选边界", "成果汇编中的第一类研究成果：形成受控能力目录、候选召回和冻结快照，避免候选外发明。", "09")
    add_box(s, 0.75, 1.26, 5.45, 4.15, fill="071a46", line="1e83e6")
    add_text(s, "候选召回规则", 1.05, 1.55, 1.8, 0.24, size=17, color="white", bold=True)
    add_text(
        s,
        "for node in namespace:\n"
        "  score_r = alias + desc + context\n"
        "            + hierarchy_bonus\n"
        "            - overspecific_penalty\n"
        "            - weak_parent_penalty\n"
        "select diversified top-k candidates\n"
        "freeze candidate snapshot",
        1.06,
        1.98,
        4.55,
        1.72,
        size=12.2,
        color="d2e6ff",
        font="Menlo",
    )
    add_line(s, 1.06, 4.0, 4.6, "2f80d3", 1.0)
    for i, b in enumerate(["不读历史样例，避免 benchmark 泄漏", "召回来源保留 alias / desc_overlap / segment_node", "ground truth 未进入候选集可直接归因为 Stage R miss"]):
        add_bullet(s, b, 1.1, 4.25 + i * 0.3, 4.45, color="cyan", size=9.6, text_color="d2e6ff")

    add_box(s, 6.7, 1.26, 5.65, 2.05, fill="ffffff", line="c8dbef")
    add_text(s, "candidate_snapshot", 7.02, 1.56, 2.55, 0.22, size=14.5, color="blue", bold=True, font="Arial")
    add_text(s, "关键字段", 7.02, 1.82, 1.0, 0.16, size=9.8, color="muted")
    fields = ["fqdn", "score_r", "source[]", "matched_phrases", "components", "candidate_recall_hit"]
    for i, f in enumerate(fields):
        add_text(s, f, 7.06 + (i % 2) * 2.35, 2.14 + (i // 2) * 0.31, 1.9, 0.18, size=9.6, color="ink", font="Arial")

    add_box(s, 6.7, 3.62, 5.65, 1.78, fill="ffffff", line=C["green"])
    add_text(s, "样例: holdout3_000213", 7.02, 3.9, 2.65, 0.22, size=13.5, color="green", bold=True, font="Arial")
    rows = [("coupon.commerce.cn", "0.1885", "query:优惠"), ("price.commerce.cn", "0.1885", "query:价格"), ("meeting.productivity.cn", "0.1885", "query:会议")]
    for i, (fqdn, score, phrase) in enumerate(rows):
        y = 4.28 + i * 0.28
        add_text(s, fqdn, 7.02, y, 1.85, 0.15, size=8.7, color="ink", font="Arial")
        add_text(s, score, 8.98, y, 0.55, 0.15, size=8.7, color="muted", font="Arial")
        add_text(s, phrase, 9.68, y, 1.5, 0.15, size=8.7, color="muted")
    add_text(s, "技术价值：后续所有裁决都在冻结候选集合内进行，错误类型可以被精确拆分。", 0.92, 6.18, 9.5, 0.24, size=13.5, color="ink", bold=True)
    add_footer(s, 11)


def slide_stage_a(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究成果二：结构化语义路由算法", "成果汇编中的第二类研究成果：在固定候选集合内完成主能力、相关能力和竞争候选说明。", "10")
    add_box(s, 0.72, 1.22, 5.65, 2.05, fill="071a46", line="1e83e6")
    add_text(s, "主能力评分融合", 1.02, 1.5, 1.8, 0.24, size=16, color="white", bold=True)
    add_text(
        s,
        "score_a = 0.55*base_primary\n"
        "        + 0.15*stage_r\n"
        "        + 0.15*llm_task_fit\n"
        "        + 0.10*llm_primary_fit\n"
        "        + bonus - penalty",
        1.04,
        1.9,
        4.55,
        0.98,
        size=11.6,
        color="d2e6ff",
        font="Menlo",
    )
    add_box(s, 6.78, 1.22, 5.55, 2.05, fill="ffffff", line=C["orange2"])
    add_text(s, "Stage B 升级判据", 7.1, 1.5, 2.35, 0.24, size=15.2, color="orange2", bold=True)
    gates = ["confidence < 0.62", "margin < 0.08", "llm_requested", "high_risk 且 margin < 0.14", "multi_intent_conflict"]
    for i, g in enumerate(gates):
        add_text(s, g, 7.12 + (i % 2) * 2.35, 1.92 + (i // 2) * 0.34, 2.05, 0.18, size=10.0, color="ink", font="Arial")

    add_box(s, 0.72, 3.62, 5.65, 1.78, fill="ffffff", line=C["blue"])
    add_text(s, "decision packet", 1.02, 3.88, 2.1, 0.22, size=14.5, color="blue", bold=True, font="Arial")
    add_text(s, "关键字段", 1.02, 4.13, 1.0, 0.16, size=9.6, color="muted")
    packet_fields = ["selected_primary_fqdn", "selected_related_fqdns", "routing_top_k", "confidence / margin", "candidate_scores", "constraint_check"]
    for i, f in enumerate(packet_fields):
        add_text(s, f, 1.04 + (i % 2) * 2.35, 4.38 + (i // 2) * 0.26, 2.0, 0.16, size=8.9, color="ink", font="Arial")

    add_box(s, 6.78, 3.62, 5.55, 1.78, fill="ffffff", line=C["green"])
    add_text(s, "Stage B 语义卡", 7.1, 3.88, 2.4, 0.22, size=14.5, color="green", bold=True)
    add_text(s, "从 Stage A 下传", 7.1, 4.13, 1.55, 0.16, size=9.6, color="muted")
    cards = ["primary_rationale", "secondary_rationale", "challenger_notes", "uncertainty_summary", "confusion_points", "override_sensitivity"]
    for i, f in enumerate(cards):
        add_text(s, f, 7.12 + (i % 2) * 2.3, 4.38 + (i // 2) * 0.26, 2.0, 0.16, size=8.9, color="ink", font="Arial")
    add_text(s, "技术价值：模型输出不作为最终答案直出，而被转成可计算分数、升级理由和可审计证据包。", 0.92, 6.18, 10.0, 0.24, size=13.4, color="ink", bold=True)
    add_footer(s, 12)


def slide_stage_b(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究成果三：职责化协作复核与授权改判", "成果汇编中的第三类研究成果：低置信、高风险、多意图和层级竞争样本进入多角色复核。", "12")
    add_box(s, 0.7, 1.18, 3.55, 4.4, fill="071a46", line="1e83e6")
    add_text(s, "角色不是摆设", 1.0, 1.48, 1.65, 0.24, size=16, color="white", bold=True)
    roles = [("DomainExpert", "core_task_match"), ("GovernanceRisk", "risk_boundary_check"), ("HierarchyResolver", "hierarchy_granularity"), ("UserPreference", "primary_secondary_split")]
    for i, (r, d) in enumerate(roles):
        y = 1.92 + i * 0.56
        add_text(s, r, 1.0, y, 1.45, 0.17, size=9.5, color="cyan", bold=True, font="Arial")
        add_text(s, d, 2.38, y, 1.35, 0.17, size=8.4, color="d2e6ff", font="Arial")
    add_line(s, 1.0, 4.36, 2.75, "2f80d3", 1.0)
    add_text(s, "每个角色只看与职责相关的 packet 视图，避免四个 agent 重复同一种判断。", 1.0, 4.62, 2.75, 0.38, size=10.2, color="d2e6ff")

    add_box(s, 4.65, 1.18, 3.45, 4.4, fill="ffffff", line=C["orange2"])
    add_text(s, "改判授权门槛", 4.96, 1.48, 1.6, 0.24, size=16, color="orange2", bold=True)
    rules = [
        "override_vote_count >= 3",
        "consensus_score >= stage_a + 0.08",
        "explicit_support >= 0.55",
        "sensitive case 需要 round2 共识",
        "cross_l1 需额外 score gain",
    ]
    for i, r in enumerate(rules):
        add_bullet(s, r, 4.98, 1.95 + i * 0.43, 2.65, color="orange2", size=9.2)
    add_text(s, "未满足门槛：保留 Stage A 原判，并写入 override_block_reasons。", 4.98, 4.62, 2.55, 0.34, size=9.3, color="muted")

    add_box(s, 8.55, 1.18, 3.65, 4.4, fill="ffffff", line=C["green"])
    add_text(s, "共识得分与 trace", 8.86, 1.48, 1.85, 0.24, size=16, color="green", bold=True)
    add_text(
        s,
        "s_rev^(1) =\n"
        "  0.40*v(c)\n"
        "+ 0.25*rho(c)\n"
        "+ 0.15*s_sem\n"
        "+ 0.10*e(c)\n"
        "+ 0.10*r(c) + sigma",
        8.88,
        1.9,
        2.7,
        0.92,
        size=9.6,
        color="ink",
        font="Menlo",
    )
    trace_fields = ["stage_a_selected_primary", "escalation_reasons", "agent_votes", "override_allowed", "override_basis_histogram", "final_primary_fqdn"]
    for i, f in enumerate(trace_fields):
        add_text(s, f, 8.9, 3.02 + i * 0.28, 2.2, 0.15, size=8.8, color="muted", font="Arial")
    add_text(s, "技术价值：慢路径不是“再问一遍模型”，而是带门禁的候选内复核器。", 0.92, 6.18, 8.8, 0.24, size=13.5, color="ink", bold=True)
    add_footer(s, 14)


def slide_trace(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究成果四：可信过程轨迹可回放", "成果汇编中的第四类研究成果：候选快照、结构化裁决、角色提案、授权判断和最终落点均可追溯。", "16")

    add_box(s, 0.68, 1.2, 3.75, 5.28, fill="071a46", line="1e83e6")
    add_text(s, "用户请求", 0.98, 1.48, 1.1, 0.24, size=16, color="white", bold=True)
    add_text(
        s,
        "买会议麦克风这单如果不看优惠规则，明显会多花一笔。\n\n主问句：先看看有什么券或优惠能用\n顺带：比一眼价格",
        0.98,
        1.92,
        2.95,
        1.08,
        size=11,
        color="d2e6ff",
    )
    add_line(s, 0.98, 3.28, 2.95, "2f80d3", 1.0)
    add_text(s, "Stage R 候选快照", 0.98, 3.54, 1.85, 0.24, size=14, color="cyan", bold=True)
    candidates = [("coupon.commerce.cn", "优惠命中"), ("price.commerce.cn", "价格命中"), ("meeting.productivity.cn", "会议词面")]
    for i, (fqdn, reason) in enumerate(candidates):
        y = 3.92 + i * 0.42
        add_circle(s, 1.0, y + 0.05, 0.08, ["green", "orange2", "purple"][i])
        add_text(s, fqdn, 1.18, y, 1.75, 0.18, size=9.5, color="white", font="Arial")
        add_text(s, reason, 2.95, y, 0.8, 0.18, size=8.8, color="d2e6ff")
    add_text(s, "candidate_count = 10    primary_in_top_k = true", 0.98, 5.4, 2.75, 0.18, size=8.8, color="d2e6ff", font="Arial")

    stages = [
        ("Stage A 初判", "price.commerce.cn", "conf=0.519 / margin=0.064", "触发原因：low_confidence + small_margin", "orange2"),
        ("Stage B 复核", "3 票提议改判 / 1 票保守", "override_vote_count = 3", "证据集中在“优惠为主、价格为辅”", "blue"),
        ("授权改判", "override_allowed = true", "basis: explicit_primary_evidence", "主意图从“比价”校正为“优惠规则”", "green"),
    ]
    for i, (title, main, meta, note, col) in enumerate(stages):
        y = 1.34 + i * 1.55
        add_box(s, 5.0, y, 3.05, 1.08, fill="ffffff", line=C[col])
        add_circle(s, 5.22, y + 0.22, 0.26, col)
        add_text(s, str(i + 1), 5.22, y + 0.29, 0.26, 0.12, size=8.5, color="white", bold=True, align="center", valign="middle", font="Arial")
        add_text(s, title, 5.58, y + 0.18, 1.5, 0.2, size=13.5, color=col, bold=True)
        add_text(s, main, 5.58, y + 0.48, 1.95, 0.18, size=10.5, color="ink", bold=True, font="Arial")
        add_text(s, meta, 5.58, y + 0.72, 2.25, 0.16, size=8.6, color="muted", font="Arial")
        add_text(s, note, 5.58, y + 0.9, 2.15, 0.14, size=8.3, color="muted")
        if i < len(stages) - 1:
            add_line(s, 6.5, y + 1.17, 0.02, "line", 22)

    add_box(s, 8.72, 1.25, 3.55, 2.05, fill="fff1f1", line="f1c3c3")
    add_text(s, "最终路由", 9.02, 1.58, 1.1, 0.22, size=15, color="red", bold=True)
    add_text(s, "coupon.commerce.cn", 8.95, 1.98, 2.9, 0.26, size=15.2, color="red", bold=True, font="Arial")
    add_text(s, "final_decision_source = stage_b", 9.02, 2.36, 2.25, 0.18, size=9.6, color="muted", font="Arial")
    add_text(s, "可解释结论：优惠可用性是主任务，价格比较作为相关诉求保留。", 9.02, 2.67, 2.75, 0.28, size=10.1, color="ink")

    add_box(s, 8.72, 3.62, 3.55, 1.42, fill="e7f1ff", line="7fb5ee")
    add_text(s, "评审能看到什么", 9.02, 3.9, 1.7, 0.22, size=15, color="blue", bold=True)
    for i, b in enumerate(["错因：候选内主次意图误判", "修正：职责化角色给出证据", "边界：改判需通过授权检查"]):
        add_bullet(s, b, 9.02, 4.26 + i * 0.24, 2.8, color="blue", size=9.4)

    add_box(s, 0.82, 6.58, 11.25, 0.38, fill="ffffff", line="c8dbef", radius=True)
    add_text(
        s,
        "Trace contract 字段：stage_r.fqdn_candidates / stage_a.routing_top_k / stage_b.agent_votes / stage_b.trust_trace / final_primary_fqdn",
        1.04,
        6.68,
        10.65,
        0.12,
        size=9.1,
        color="muted",
        font="Arial",
    )
    add_footer(s, 18)


def slide_code(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "原型支撑：研究链路已经沉淀为可运行模块和测试用例", "成果汇编中的原型系统不是概念图，已经对应到模块、脚本、测试和实验资产。", "18")
    modules = [
        ("namespace.py", "能力节点 / FQDN / 层级", "blue"),
        ("stage_r_clean.py", "命名空间候选召回", "blue2"),
        ("stage_a_llm.py", "结构化语义裁决", "green"),
        ("stage_b_consensus.py", "职责化复核与授权", "orange2"),
        ("stage_c_selector.py", "实例过滤与排序", "purple"),
    ]
    for i, (m, d, col) in enumerate(modules):
        x = 0.75 + i * 2.48
        add_box(s, x, 1.55, 2.05, 1.18, fill="ffffff", line=C[col])
        add_text(s, m, x + 0.14, 1.83, 1.55, 0.18, size=10.5, color=col, bold=True, font="Arial")
        add_text(s, d, x + 0.14, 2.18, 1.45, 0.22, size=10.3, color="muted")
    add_box(s, 0.86, 3.45, 5.8, 1.7, fill="071a46", line="1e83e6")
    add_text(s, "运行入口", 1.15, 3.77, 1.4, 0.24, size=16, color="white", bold=True)
    for i, c in enumerate(["run_stage_r_clean_snapshot.py", "run_stage_a_llm.py", "run_stage_b.py", "run_routing_service.py"]):
        add_text(s, c, 1.16, 4.18 + i * 0.26, 3.9, 0.18, size=9.7, color="d2e6ff", font="Arial")
    add_box(s, 7.25, 3.45, 4.65, 1.7, fill="ffffff", line="c8dbef")
    add_text(s, "验证与规模", 7.55, 3.77, 1.6, 0.24, size=16, color="blue", bold=True)
    stats = [("12", "核心模块"), ("5", "运行脚本"), ("5", "测试文件"), ("9,787", "代码与测试行数")]
    for i, (v, l) in enumerate(stats):
        add_text(s, v, 7.55 + i * 1.0, 4.22, 0.8, 0.24, size=16, color=["blue", "green", "orange2", "red"][i], bold=True, font="Arial")
        add_text(s, l, 7.52 + i * 1.0, 4.55, 0.95, 0.18, size=7.8, color="muted", align="center")
    add_text(s, "代码证明项目已经从方案说明进入可运行、可测试、可复现实验状态。", 0.9, 6.35, 7.4, 0.28, size=14, color="ink", bold=True)
    add_footer(s, 20)


def slide_demo(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "原型系统：能力地址到执行实例的硬过滤与可解释排序", "成果汇编中的原型系统覆盖请求输入、候选组织、路由高亮、候选 Agent 排序和执行状态展示。", "17")
    add_box(s, 0.76, 1.28, 3.65, 4.1, fill="071a46", line="1e83e6")
    add_text(s, "硬过滤条件", 1.06, 1.58, 1.5, 0.24, size=16, color="white", bold=True)
    filters = ["routing_fqdn exact match", "endpoint exists", "status in online/ready/available", "input/output schema covered"]
    for i, f in enumerate(filters):
        add_bullet(s, f, 1.08, 2.05 + i * 0.46, 2.75, color="cyan", size=9.5, text_color="d2e6ff")
    add_text(s, "被过滤对象写入 filtered_out_reasons，避免执行层悄悄兜底。", 1.08, 4.28, 2.75, 0.34, size=9.5, color="d2e6ff")

    add_box(s, 4.78, 1.28, 3.45, 4.1, fill="ffffff", line=C["purple"])
    add_text(s, "排序评分", 5.08, 1.58, 1.35, 0.24, size=16, color="purple", bold=True)
    add_text(
        s,
        "base = 0.55*S_match\n"
        "     + 0.25*S_schema\n"
        "     + 0.20*S_tag\n\n"
        "final = base * health\n"
        "      * fair_agent\n"
        "      * fair_provider",
        5.08,
        2.02,
        2.75,
        1.55,
        size=11.5,
        color="ink",
        font="Menlo",
    )
    add_text(s, "health 按 heartbeat 半衰期衰减；fairness 抑制单 agent / provider 过度曝光。", 5.08, 4.08, 2.55, 0.42, size=9.2, color="muted")

    add_box(s, 8.78, 1.28, 3.25, 4.1, fill="ffffff", line=C["green"])
    add_text(s, "selection_trace", 9.08, 1.58, 1.75, 0.24, size=16, color="green", bold=True, font="Arial")
    trace = ["candidate_count_before_filter", "candidate_count_after_filter", "filtered_out_reasons", "chosen_agent_fqdn", "selection_latency_ms", "tie_break_applied"]
    for i, f in enumerate(trace):
        add_text(s, f, 9.08, 2.02 + i * 0.34, 2.25, 0.17, size=8.8, color="ink", font="Arial")
    add_text(s, "输出：chosen_agent_fqdn -> endpoint", 9.08, 4.36, 2.35, 0.2, size=10.2, color="green", bold=True, font="Arial")
    add_text(s, "技术价值：把“语义正确”推进到“可执行、可审计、可解释选择”。", 0.92, 6.18, 8.8, 0.24, size=13.5, color="ink", bold=True)
    add_footer(s, 19)


def slide_dataset(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究成果一（1/2）：建立统一评测样本集", "成果汇编优先呈现数据资产：563 条样本、50 个能力节点、45 类主标签和冻结 train/test 口径。", "07")
    for i, (v, l, col) in enumerate([("563", "总样本", "blue"), ("450", "train", "green"), ("113", "test", "orange2"), ("50", "命名空间节点", "purple"), ("45", "主标签", "red")]):
        x = 0.78 + i * 1.5
        add_text(s, v, x, 1.52, 1.0, 0.38, size=27, color=col, bold=True, font="Arial")
        add_text(s, l, x + 0.03, 2.02, 1.1, 0.18, size=10, color="ink", bold=True)
    domains = [("finance", 28), ("travel", 24), ("security", 16), ("productivity", 14), ("gov", 11), ("commerce", 7), ("health", 5), ("education", 5), ("weather", 3)]
    maxv = max(v for _, v in domains)
    add_box(s, 0.86, 2.75, 6.0, 2.75, fill="ffffff", line="c8dbef")
    add_text(s, "测试集领域分布", 1.15, 3.05, 1.8, 0.22, size=15, color="blue", bold=True)
    for i, (name, v) in enumerate(domains):
        y = 3.45 + i * 0.2
        add_text(s, name, 1.15, y, 1.0, 0.13, size=7.8, color="muted", font="Arial")
        add_box(s, 2.08, y + 0.03, 3.3 * v / maxv, 0.08, fill=C["blue2"], line=C["blue2"], radius=False)
        add_text(s, str(v), 5.55, y - 0.02, 0.28, 0.12, size=7.5, color="muted", font="Arial")
    add_box(s, 7.5, 2.75, 4.35, 2.75, fill="ffffff", line="c8dbef")
    add_text(s, "复杂样本标签", 7.78, 3.05, 1.8, 0.22, size=15, color="blue", bold=True)
    for i, (name, v, col) in enumerate([("multi_intent", 12, "orange2"), ("high_risk", 4, "red")]):
        add_text(s, name, 7.82, 3.55 + i * 0.62, 1.5, 0.2, size=12, color=col, bold=True, font="Arial")
        add_text(s, f"test={v}", 9.42, 3.56 + i * 0.62, 0.8, 0.18, size=11, color="muted", font="Arial")
    add_text(s, "最新报告口径：563 条样本、50 个命名空间节点、45 类主标签，测试集含 38 条相关能力标注、12 条多意图、4 条高风险样本。", 0.9, 6.25, 10.3, 0.28, size=12.3, color="ink", bold=True)
    add_footer(s, 9)


def slide_protocol(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "评测协议：冻结主口径，区分主结果、诊断结果与探索结果", "成果汇编把实验资产作为验收证据，必须说明 train/test、配置选择和复现边界。", "08")
    phases = [("统一样本池", "dev + blind + challenge + holdout2 + holdout3 = 563"), ("train=450", "方案开发 / 阈值选择 / 配置选择"), ("test=113", "一次性主结果报告"), ("配对消融", "train=320 / test=80，三类复核记录完整")]
    for i, (t, b) in enumerate(phases):
        x = 0.85 + i * 3.0
        add_box(s, x, 1.65, 2.3, 1.05, fill="ffffff", line="c8dbef")
        add_text(s, t, x + 0.18, 1.9, 1.5, 0.22, size=13.5, color=["blue", "green", "orange2", "purple"][i], bold=True)
        add_text(s, b, x + 0.18, 2.24, 1.75, 0.25, size=8.5, color="muted", font="Arial")
    add_box(s, 1.0, 3.45, 5.2, 1.55, fill="071a46", line="1e83e6")
    add_text(s, "防泄漏与可复现", 1.3, 3.78, 1.8, 0.24, size=16, color="white", bold=True)
    for i, b in enumerate(["候选快照与 gold 标签分离", "主结果只讲冻结 train/test", "历史 split 只作诊断材料"]):
        add_bullet(s, b, 1.3, 4.18 + i * 0.26, 3.8, color="cyan", size=10.3, text_color="d2e6ff")
    add_box(s, 7.0, 3.45, 4.55, 1.55, fill="ffffff", line="c8dbef")
    add_text(s, "指标", 7.3, 3.78, 1.0, 0.24, size=16, color="blue", bold=True)
    for i, m in enumerate(["PrimaryAcc@1", "Acceptable@1", "RelatedRecall", "RelatedPrecision", "Changed/Fix/Regress"]):
        add_text(s, m, 7.35 + (i % 2) * 1.8, 4.18 + (i // 2) * 0.28, 1.5, 0.16, size=8.8, color="muted", font="Arial")
    add_footer(s, 10)


def slide_results(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "实验验证：结构化判别是主台阶，协作复核提供边界修正", "统一 train/test 主协议下，测试集 PrimaryAcc@1 从 0.7876 提升到 0.8850；补充扩展配置达到 0.9292。", "11")
    add_box(s, 0.72, 1.22, 7.9, 4.65, fill="ffffff", line="c8dbef")
    add_picture(s, FIG_DIR / "01_pooled_test_waterfall.png", 1.0, 1.52, 7.28, 3.95)
    add_box(s, 8.95, 1.3, 3.1, 0.98, fill="e7f1ff", line="7fb5ee")
    add_text(s, "0.7876 → 0.8761", 9.18, 1.52, 2.6, 0.28, size=19, color="green", bold=True, align="center", font="Arial")
    add_text(s, "规则路由到结构化语义路由", 9.22, 1.88, 2.45, 0.16, size=9.2, color="ink", bold=True, align="center")
    add_box(s, 8.95, 2.55, 3.1, 0.98, fill="ffffff", line=C["orange2"])
    add_text(s, "0.8850", 9.55, 2.75, 1.7, 0.3, size=23, color="orange2", bold=True, align="center", font="Arial")
    add_text(s, "默认协作复核 / 零回归", 9.23, 3.12, 2.45, 0.16, size=9.2, color="muted", align="center")
    add_box(s, 8.95, 3.8, 3.1, 0.98, fill="fff1f1", line="f1c3c3")
    add_text(s, "0.9292", 9.55, 4.0, 1.7, 0.3, size=23, color="red", bold=True, align="center", font="Arial")
    add_text(s, "扩展配置 / 5 次改写全部修正", 9.12, 4.37, 2.7, 0.16, size=9.0, color="muted", align="center")
    add_text(s, "技术解释：先用结构化候选级证据解决大部分判别问题，再让协作复核只处理低置信、高风险和多意图冲突样本。", 0.92, 6.18, 10.0, 0.24, size=13.2, color="ink", bold=True)
    add_footer(s, 13)


def slide_stability(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "样本池稳定性：新增样本增加复杂度，但没有推翻方法排序", "成果汇编中的图表资产用于回答“样本是否太少、结论是否偶然”的评审追问。", "19")
    add_box(s, 0.66, 1.18, 8.25, 4.85, fill="ffffff", line="c8dbef")
    add_picture(s, FIG_DIR / "09_historical_cumulative_train_test.png", 0.94, 1.52, 7.7, 4.05)
    add_box(s, 9.25, 1.34, 2.78, 1.08, fill="ffffff", line=C["green"])
    add_text(s, "测试集 113 条", 9.55, 1.58, 1.65, 0.2, size=13.5, color="green", bold=True)
    add_text(s, "结构化语义路由 0.8761\n默认协作复核 0.8850\n扩展配置 0.9292", 9.55, 1.88, 1.95, 0.38, size=9.3, color="muted", font="Arial")
    add_box(s, 9.25, 2.78, 2.78, 1.08, fill="ffffff", line=C["orange2"])
    add_text(s, "稳定性含义", 9.55, 3.02, 1.45, 0.2, size=13.5, color="orange2", bold=True)
    add_text(s, "累计到 73、93、113 条时，三条方法曲线保持相对排序，没有因新增样本出现反转。", 9.55, 3.32, 1.95, 0.34, size=8.9, color="muted")
    add_box(s, 9.25, 4.14, 2.78, 1.3, fill="fff1f1", line="f1c3c3")
    add_text(s, "答辩话术", 9.55, 4.46, 1.25, 0.2, size=13.5, color="red", bold=True)
    add_text(s, "不声称覆盖全部未来命名空间；当前 563 样本用于排除“少量早期样本偶然支撑”的解释。", 9.55, 4.74, 1.95, 0.48, size=8.1, color="muted")
    add_text(s, "这一页是新版论文的关键补强：把“项目样本规模是否支撑结论”从口头解释变成可视化证据。", 0.92, 6.28, 10.2, 0.24, size=13.2, color="ink", bold=True)
    add_footer(s, 21)


def slide_ablation(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "配对消融：收益不是“多问几个智能体”，而是职责分工与授权控制", "成果汇编将配对消融作为多智能体协作增益的核心证据：训练侧 13/13/0，测试侧 5/5/0。", "13")
    add_box(s, 0.75, 1.28, 6.75, 4.55, fill="ffffff", line="c8dbef")
    add_text(s, "配对消融准确率", 1.05, 1.58, 1.8, 0.22, size=14, color="ink", bold=True)
    groups = [
        ("单角色复核", 0.8875, 0.8625),
        ("同质复核", 0.8844, 0.8625),
        ("职责化协作", 0.9187, 0.9250),
    ]
    base_y = 5.32
    for i, (name, train, test) in enumerate(groups):
        x = 1.35 + i * 1.75
        for j, (val, col, label) in enumerate([(train, "blue", "train"), (test, "orange2", "test")]):
            h = (val - 0.84) / (0.94 - 0.84) * 2.55
            bx = x + j * 0.46
            add_box(s, bx, base_y - h, 0.34, h, fill=C[col], line=C[col], radius=False)
            add_text(s, f"{val:.4f}", bx - 0.16, base_y - h - 0.22, 0.66, 0.14, size=6.8, color=col, bold=True, align="center", font="Arial")
            add_text(s, label, bx - 0.04, base_y + 0.08, 0.42, 0.12, size=6.5, color="muted", align="center", font="Arial")
        add_text(s, name, x - 0.22, 5.58, 1.28, 0.16, size=8.5, color="muted", align="center")
    add_box(s, 7.85, 1.42, 3.85, 1.05, fill="fff1f1", line="f1c3c3")
    add_text(s, "13/13/0", 8.15, 1.66, 1.7, 0.28, size=23, color="red", bold=True, font="Arial")
    add_text(s, "训练侧职责化协作改判/纠错/误改", 9.72, 1.72, 1.62, 0.18, size=8.5, color="muted")
    add_box(s, 7.85, 2.72, 3.85, 0.88, fill="ffffff", line="c8dbef")
    add_text(s, "0.8625 → 0.9250", 8.25, 2.92, 2.6, 0.24, size=18, color="red", bold=True, align="center", font="Arial")
    add_text(s, "测试侧职责化协作提升 +0.0625", 8.42, 3.26, 2.3, 0.16, size=8.8, color="muted", align="center")
    add_box(s, 7.85, 3.95, 3.85, 1.65, fill="e7f1ff", line="7fb5ee")
    add_text(s, "硬结论", 8.15, 4.25, 0.9, 0.22, size=15, color="blue", bold=True)
    for i, b in enumerate(["配对样本要求三类复核记录完整，口径更严谨", "单角色/同质复核测试侧没有超过基线", "职责化分工 + 结构化证据 + 授权门槛共同形成收益"]):
        add_bullet(s, b, 8.18, 4.62 + i * 0.32, 3.0, color="blue", size=8.0)
    add_footer(s, 15)


def slide_cases(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "典型案例：样本语义揭示具体冲突", "成果汇编中的典型案例负责把实验指标落到“能处理什么复杂语义问题”。", "14")
    cases = [
        {
            "tag": "holdout3_000038 / 跨域竞争",
            "quote": "请把驻场培训周内容压缩成一页领导评审材料，先搭材料骨架、梳理整体结构。",
            "wrong": "course.education.cn",
            "right": "docs.productivity.cn",
            "mode": "expanded 放行后修正",
            "basis": "表面词“培训”牵引到课程域；主动作是搭骨架、压材料、梳结构，应落文档处理。",
            "color": "blue",
        },
        {
            "tag": "holdout3_000173 / 主次意图拆分",
            "quote": "到西安后还要二次换乘，先看哪种接驳最省事；航班和活动顺手再核对。",
            "wrong": "flight.travel.cn",
            "right": "transport.travel.cn",
            "mode": "single_v2 / expanded 修正",
            "basis": "航班、活动是并列背景；主任务由“接驳最省事”“二次换乘”限定为交通接驳。",
            "color": "green",
        },
        {
            "tag": "holdout3_000303 / 跨域重叠",
            "quote": "杭州临时多出一个晚上，帮我挑一个不折腾的活动；住处是否需要调整也顺手看一下。",
            "wrong": "hotel.travel.cn",
            "right": "activity.travel.cn",
            "mode": "职责化复核稳定修正",
            "basis": "住处调整只是附带检查；主动作是挑活动，复核后把住宿从主标签降为干扰项。",
            "color": "orange2",
        },
    ]
    add_text(s, "样本表达（整理）", 1.02, 1.22, 1.42, 0.18, size=9.4, color="muted", bold=True)
    add_text(s, "误判路径", 5.68, 1.22, 0.9, 0.18, size=9.4, color="muted", bold=True, align="center")
    add_text(s, "复核抓住的主任务", 8.55, 1.22, 1.42, 0.18, size=9.4, color="muted", bold=True, align="center")
    x0, y0 = 0.72, 1.5
    for i, item in enumerate(cases):
        y = y0 + i * 1.34
        add_box(s, x0, y, 11.78, 1.14, fill="ffffff", line="dbe8f5")
        add_box(s, x0, y, 0.12, 1.14, fill=C[item["color"]], line=C[item["color"]], radius=False)
        add_text(s, item["tag"], x0 + 0.28, y + 0.16, 2.72, 0.18, size=9.6, color=item["color"], bold=True)
        add_text(s, item["quote"], x0 + 0.28, y + 0.42, 4.25, 0.38, size=9.0, color="ink", bold=True)
        add_text(s, "单智能体", x0 + 4.95, y + 0.20, 0.86, 0.16, size=7.8, color="muted", align="center")
        add_text(s, item["wrong"], x0 + 4.55, y + 0.48, 1.62, 0.18, size=9.2, color="red", bold=True, align="center", font="Arial")
        add_text(s, "→", x0 + 6.28, y + 0.45, 0.26, 0.18, size=12.5, color="muted", bold=True, align="center", font="Arial")
        add_text(s, item["mode"], x0 + 6.7, y + 0.20, 1.42, 0.16, size=7.8, color="muted", align="center")
        add_text(s, item["right"], x0 + 6.46, y + 0.48, 1.9, 0.18, size=9.2, color="green", bold=True, align="center", font="Arial")
        add_text(s, item["basis"], x0 + 8.72, y + 0.26, 3.0, 0.46, size=8.7, color="muted")
    add_box(s, 0.82, 5.72, 10.98, 0.58, fill="e7f1ff", line="7fb5ee")
    add_text(s, "案例价值：不是把样本堆满，而是用“样本语义 + trace 改判路径”证明系统能处理跨域竞争、主次拆分和重叠意图。", 1.08, 5.88, 9.85, 0.18, size=12.0, color="ink", bold=True)
    add_text(s, "注：页面话术为答辩可读化整理，原始样本与完整 trace 已在实验记录中留存。", 1.1, 6.12, 7.2, 0.14, size=7.5, color="muted")
    add_footer(s, 16)


def slide_collab_trace(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(
        s,
        "协作复核可视化：多角色讨论把改判变成可审计过程",
        "以 holdout3_000303 为例：Stage A 将主任务误判为住宿，Stage B 通过角色投票、证据归因和授权门槛完成改判。",
        "15",
    )
    add_box(s, 0.75, 1.16, 11.75, 0.58, fill="071a46", line="1e83e6")
    add_text(s, "样本语义", 1.05, 1.35, 0.8, 0.16, size=9.2, color="cyan", bold=True)
    add_text(s, "杭州临时多出一晚：先挑一个不折腾的活动；住处是否调整只是顺手检查。", 1.95, 1.32, 6.4, 0.18, size=12.6, color="white", bold=True)
    add_text(s, "trace fields: agent_votes / raw_response / trust_trace / feedback_scores", 8.35, 1.35, 3.4, 0.14, size=7.6, color="d2e6ff", font="Arial")

    # Top decision path.
    path = [
        ("Stage A 初判", "hotel.travel.cn", "表面词：住处", "red"),
        ("触发复核", "low confidence", "多意图 + close score", "orange2"),
        ("角色讨论", "4 agents", "主任务/风险/层级/偏好", "blue"),
        ("授权门槛", "3 : 1", "override allowed", "purple"),
        ("最终落点", "activity.travel.cn", "主任务：挑活动", "green"),
    ]
    for i, (t, v, b, col) in enumerate(path):
        x = 0.82 + i * 2.38
        add_box(s, x, 2.02, 1.82, 0.84, fill="ffffff", line=C[col])
        add_text(s, t, x + 0.12, 2.18, 0.9, 0.14, size=7.8, color="muted", bold=True)
        add_text(s, v, x + 0.12, 2.42, 1.3, 0.16, size=9.6, color=col, bold=True, font="Arial")
        add_text(s, b, x + 0.12, 2.64, 1.35, 0.12, size=6.9, color="muted")
        if i < len(path) - 1:
            add_text(s, "→", x + 1.96, 2.36, 0.22, 0.16, size=13, color="muted", bold=True, align="center", font="Arial")

    # Role lanes.
    roles = [
        ("DomainExpert", "主任务匹配", "activity.travel.cn", "“活动”直接命中主任务，住处是附带检查", "green"),
        ("GovernanceRisk", "风险边界", "hotel.travel.cn", "无高风险，保守支持 Stage A 原判", "red"),
        ("HierarchyResolver", "层级/粒度", "activity.travel.cn", "住宿节点更像 related，活动才是 primary", "green"),
        ("UserPreference", "用户偏好", "activity.travel.cn", "“重点/顺手”明确主次，活动优先", "green"),
    ]
    for i, (role, focus, vote, note, col) in enumerate(roles):
        x = 0.92 + (i % 2) * 5.05
        y = 3.25 + (i // 2) * 0.98
        add_box(s, x, y, 4.64, 0.76, fill="ffffff", line=C[col])
        add_circle(s, x + 0.22, y + 0.22, 0.24, col)
        add_text(s, str(i + 1), x + 0.22, y + 0.29, 0.24, 0.1, size=6.5, color="white", bold=True, align="center", valign="middle", font="Arial")
        add_text(s, role, x + 0.58, y + 0.15, 1.2, 0.16, size=9.2, color="ink", bold=True, font="Arial")
        add_text(s, focus, x + 1.78, y + 0.16, 0.9, 0.12, size=7.4, color="muted", align="center")
        add_text(s, vote, x + 2.76, y + 0.14, 1.35, 0.14, size=8.2, color=col, bold=True, font="Arial")
        add_text(s, note, x + 0.58, y + 0.43, 3.52, 0.14, size=7.6, color="muted")

    # Audit gate.
    add_box(s, 10.72, 3.25, 1.82, 1.74, fill="fff1f1", line="f1c3c3")
    add_text(s, "TRUST GATE", 10.99, 3.48, 1.18, 0.16, size=10.5, color="red", bold=True, align="center", font="Arial")
    add_text(s, "override votes", 11.02, 3.82, 0.95, 0.12, size=7.0, color="muted", align="center", font="Arial")
    add_text(s, "3", 10.86, 3.98, 0.42, 0.26, size=21, color="green", bold=True, align="center", font="Arial")
    add_text(s, ":", 11.29, 4.03, 0.12, 0.16, size=12, color="muted", bold=True, align="center", font="Arial")
    add_text(s, "1", 11.44, 3.98, 0.42, 0.26, size=21, color="red", bold=True, align="center", font="Arial")
    add_text(s, "support Stage A", 10.89, 4.36, 1.25, 0.12, size=7.0, color="muted", align="center", font="Arial")
    add_text(s, "allowed", 11.06, 4.65, 0.88, 0.16, size=10.4, color="green", bold=True, align="center", font="Arial")

    add_box(s, 0.9, 5.55, 10.96, 0.68, fill="e7f1ff", line="7fb5ee")
    add_text(s, "可审计证据", 1.18, 5.76, 0.95, 0.16, size=10.4, color="blue", bold=True)
    for i, txt in enumerate(["agent_votes 保存每个角色的投票", "raw_response 保存 LLM 原始结构化回复", "trust_trace 记录分歧、票数和授权结果", "feedback_scores 记录候选得分和共识增益"]):
        add_bullet(s, txt, 2.35 + (i % 2) * 4.35, 5.72 + (i // 2) * 0.25, 3.55, color="blue", size=7.6)
    add_footer(s, 17)


def slide_contribution(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "突破创新：把多智能体协作与可信认知标识压实到可验证链路", "最新报告口径强调项目不是单点算法，而是能力组织、协作共识、可信留痕和原型验证的组合突破。", "20")
    items = [
        ("能力命名突破", "构建能力逻辑地址与实例逻辑地址分层表达，支撑候选组织"),
        ("结构化判别突破", "将大模型判断压缩为 decision packet、score、margin 和冲突摘要"),
        ("职责化协作突破", "任务匹配、治理风险、层级解析、用户偏好形成异质证据视图"),
        ("显式授权突破", "复核触发与最终改判解耦，用票数、共识增益和证据门槛控制误改"),
        ("可信留痕突破", "候选、判断、复核、授权、执行落点全链路记录，支撑回放和审计"),
    ]
    for i, (t, b) in enumerate(items):
        x = 0.85 + (i % 3) * 4.0
        y = 1.55 + (i // 3) * 1.58
        add_box(s, x, y, 3.45, 1.15, fill="ffffff", line=C[["blue", "green", "orange2", "purple", "red"][i]])
        add_text(s, f"0{i+1}", x + 0.18, y + 0.22, 0.45, 0.2, size=14, color=["blue", "green", "orange2", "purple", "red"][i], bold=True, font="Arial")
        add_text(s, t, x + 0.72, y + 0.2, 1.75, 0.22, size=14.2, color="ink", bold=True)
        add_text(s, b, x + 0.72, y + 0.56, 2.25, 0.34, size=10.2, color="muted")
    add_box(s, 1.0, 5.42, 10.8, 0.78, fill="e7f1ff", line="7fb5ee")
    add_text(s, "攻关结果：形成“能力命名—结构化判别—职责化复核—可信过程记录—执行落点衔接”的可复用技术链条。", 1.3, 5.64, 9.4, 0.2, size=12.8, color="ink", bold=True)
    add_text(s, "实验层面用 563 冻结样本、累计稳定性、配对消融和典型案例证明该链条不是概念拼接。", 1.3, 5.93, 8.7, 0.16, size=9.8, color="muted")
    add_footer(s, 22)


def slide_evidence(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "研究产出：五类成果进入验收材料包", "按成果汇编口径组织，不把论文、报告、专利、原型和数据实验割裂展示。", "21")
    add_picture(s, STRONG_ASSET_DIR / "evidence_wall.png", 0.62, 1.22, 8.4, 4.4)
    add_box(s, 9.35, 1.5, 2.6, 3.7, fill="071a46", line="1e83e6")
    add_text(s, "成果清单", 9.65, 1.85, 1.3, 0.24, size=16, color="white", bold=True)
    for i, b in enumerate(["原型系统", "技术报告", "论文投稿稿", "发明专利材料", "数据与实验资产", "成果汇编/宣传稿"]):
        add_bullet(s, b, 9.68, 2.32 + i * 0.34, 1.8, color="cyan", size=9.6, text_color="d2e6ff")
    add_text(s, "成果汇编作为“证据总账”：原型、报告、论文、专利和实验资产均有对应材料，正式受理/展示证明按管理口径补齐。", 0.85, 6.25, 10.4, 0.28, size=12.8, color="ink", bold=True)
    add_footer(s, 23)


def slide_acceptance(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "考核指标对应：成果汇编已逐项落到证明材料", "把任务书指标转成验收表，而不是只列技术亮点。专利正式受理号、展示证明等以最终附件补充。", "22")
    rows = [
        ("原型系统", "已完成", "能力命名与语义路由控制台，覆盖请求输入、候选组织、协作复核、过程记录和执行映射"),
        ("算法方法", "已完成", "结构化语义路由、职责化协作复核、执行实例过滤和过程轨迹模型"),
        ("数据实验", "已完成", "563 样本、50 个能力节点、45 类主标签，完成冻结 train/test、配对消融和稳定性分析"),
        ("论文报告", "已完成", "技术报告、论文投稿稿、成果汇编和验收报告填写版已经形成"),
        ("知识产权", "状态待补", "专利申请材料、交底书、权利要求、说明书摘要和附图已形成，受理证明待正式补充"),
    ]
    x0, y0 = 0.82, 1.35
    widths = [2.55, 1.35, 7.2]
    for i, h in enumerate(["考核指标", "状态", "证据说明"]):
        add_box(s, x0 + sum(widths[:i]), y0, widths[i], 0.46, fill=C["navy2"], line=C["navy2"], radius=False)
        add_text(s, h, x0 + sum(widths[:i]) + 0.08, y0 + 0.12, widths[i] - 0.16, 0.16, size=9.8, color="white", bold=True, align="center")
    for r, row in enumerate(rows):
        y = y0 + 0.46 + r * 0.74
        for c, val in enumerate(row):
            add_box(s, x0 + sum(widths[:c]), y, widths[c], 0.74, fill="ffffff", line="dbe8f5", radius=False)
            color = "orange2" if val == "状态待补" else ("green" if c == 1 else "ink")
            add_text(s, val, x0 + sum(widths[:c]) + 0.12, y + 0.22, widths[c] - 0.24, 0.22, size=9.5, color=color, bold=(c <= 1))
    add_box(s, 1.0, 5.7, 10.5, 0.62, fill="e7f1ff", line="7fb5ee")
    add_text(s, "验收提交包建议按成果汇编目录组装：原型系统、算法方法、数据实验、论文报告、知识产权、展示证明。", 1.28, 5.92, 9.3, 0.2, size=12.2, color="ink", bold=True)
    add_footer(s, 24)


def slide_risks(prs):
    s = blank(prs)
    add_picture(s, ASSET_DIR / "light_texture.png", 0, 0, SLIDE_W, SLIDE_H)
    add_title(s, "问题边界与下一步：保留严谨表述，避免过度承诺", "评审往往会追问规模化、成本、外推性和端到端联调，这页提前回答。", "23")
    risks = [
        ("外推性", "现有结果建立在冻结样本与后验诊断池上，后续需扩展独立验证样本。"),
        ("运行成本", "已用慢路径率与修正收益做代理，真实 token、时延、稳定性仍需统一记录。"),
        ("系统联调", "Stage C 已有原型设计与测试，完整业务端到端联调需继续推进。"),
        ("可信强度", "当前是工程审计能力，后续可加入 hash-chain 与篡改检测。"),
    ]
    for i, (t, b) in enumerate(risks):
        x = 0.86 + (i % 2) * 5.75
        y = 1.55 + (i // 2) * 1.55
        add_box(s, x, y, 4.95, 1.1, fill="ffffff", line=C[["blue", "orange2", "green", "purple"][i]])
        add_text(s, t, x + 0.25, y + 0.24, 1.1, 0.22, size=15, color=["blue", "orange2", "green", "purple"][i], bold=True)
        add_text(s, b, x + 1.38, y + 0.2, 3.15, 0.36, size=10.5, color="muted")
    add_box(s, 1.0, 5.25, 10.8, 0.86, fill="071a46", line="1e83e6")
    add_text(s, "后续重点：扩大验证范围、完善质量/成本/时延日志、推动演示端联调、凝练标准化表达与业务试点。", 1.28, 5.55, 9.3, 0.24, size=13.5, color="white", bold=True)
    add_footer(s, 25)


def slide_close(prs):
    s = blank(prs)
    add_picture(s, STRONG_ASSET_DIR / "cover_bg_deep.png", 0, 0, SLIDE_W, SLIDE_H)
    add_text(s, "总结", 0.76, 0.92, 1.2, 0.4, size=30, color="white", bold=True)
    add_line(s, 0.78, 1.5, 1.5, "cyan", 3)
    points = [
        ("完成验收指标", "原型、报告/论文、专利材料、展示支撑均已形成。"),
        ("形成技术闭环", "能力命名、语义路由、职责化复核、执行落点和过程轨迹贯通。"),
        ("具备延展价值", "可继续支撑 AgentDNS、智能体标识、服务发现与治理审计方向。"),
    ]
    for i, (t, b) in enumerate(points):
        y = 2.15 + i * 1.0
        add_circle(s, 0.96, y, 0.38, ["cyan", "orange", "green"][i])
        add_text(s, str(i + 1), 0.96, y + 0.11, 0.38, 0.16, size=9, color="navy", bold=True, align="center", valign="middle", font="Arial")
        add_text(s, t, 1.55, y + 0.02, 2.2, 0.24, size=18, color="white", bold=True)
        add_text(s, b, 1.56, y + 0.42, 5.7, 0.22, size=12, color="d2e6ff")
    add_text(s, "谢谢，请各位专家批评指正", 0.78, 6.38, 3.8, 0.28, size=18, color="white", bold=True)
    add_text(s, "CNNIC", 11.58, 0.38, 1.1, 0.3, size=23, color="white", bold=True, align="right", font="Arial")
    add_text(s, "中国互联网络信息中心", 10.9, 0.7, 1.78, 0.18, size=8.5, color="d2e6ff", align="right")


def build():
    create_strong_assets()
    prs = new_presentation()
    for fn in [
        slide_cover,
        slide_verdict,
        slide_agenda,
        slide_background,
        slide_task_mapping,
        slide_object,
        slide_architecture,
        slide_review_architecture,
        slide_dataset,
        slide_protocol,
        slide_stage_r,
        slide_stage_a,
        slide_results,
        slide_stage_b,
        slide_ablation,
        slide_cases,
        slide_collab_trace,
        slide_trace,
        slide_demo,
        slide_code,
        slide_stability,
        slide_contribution,
        slide_evidence,
        slide_acceptance,
        slide_risks,
        slide_close,
    ]:
        fn(prs)
    prs.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
