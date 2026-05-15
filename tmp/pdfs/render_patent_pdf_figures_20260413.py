from pathlib import Path
import math

import fitz
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


ROOT = Path("/Users/xizhuxizhu/Desktop/IndProj04")
OUT_DIR = ROOT / "output/doc/专利PDF附图版_20260413"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 36
FONT = "STSong-Light"
pdfmetrics.registerFont(UnicodeCIDFont(FONT))


def set_font(c, size):
    c.setFont(FONT, size)


def center_text(c, x, y, w, h, text, size=10, leading=13):
    lines = text.split("\n")
    total = leading * (len(lines) - 1)
    cy = y + h / 2 + total / 2
    set_font(c, size)
    for i, line in enumerate(lines):
        ty = cy - i * leading
        tw = pdfmetrics.stringWidth(line, FONT, size)
        c.drawString(x + (w - tw) / 2, ty - size / 2, line)


def draw_box(c, x, y, w, h, text, size=10, linewidth=1.2, radius=0):
    c.setLineWidth(linewidth)
    if radius > 0:
        c.roundRect(x, y, w, h, radius, stroke=1, fill=0)
    else:
        c.rect(x, y, w, h, stroke=1, fill=0)
    center_text(c, x, y, w, h, text, size=size)


def draw_frame(c, x, y, w, h, label, label_size=10):
    c.setLineWidth(1.1)
    c.rect(x, y, w, h, stroke=1, fill=0)
    set_font(c, label_size)
    pad = 6
    label_w = pdfmetrics.stringWidth(label, FONT, label_size)
    c.setFillColorRGB(1, 1, 1)
    c.rect(x + 10, y + h - 7, label_w + pad * 2, 14, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(x + 10 + pad, y + h - 3, label)


def arrow(c, x1, y1, x2, y2, dashed=False, text=None, text_dx=0, text_dy=0):
    c.saveState()
    if dashed:
        c.setDash(4, 3)
    else:
        c.setDash()
    c.setLineWidth(1.1)
    c.line(x1, y1, x2, y2)
    c.restoreState()

    angle = math.atan2(y2 - y1, x2 - x1)
    head = 7
    a1 = angle + math.pi - math.pi / 8
    a2 = angle + math.pi + math.pi / 8
    c.line(x2, y2, x2 + head * math.cos(a1), y2 + head * math.sin(a1))
    c.line(x2, y2, x2 + head * math.cos(a2), y2 + head * math.sin(a2))

    if text:
        set_font(c, 8)
        mx = (x1 + x2) / 2 + text_dx
        my = (y1 + y2) / 2 + text_dy
        c.drawString(mx, my, text)


def poly_arrow(c, points, dashed=False, text=None, text_pos=None):
    c.saveState()
    if dashed:
        c.setDash(4, 3)
    else:
        c.setDash()
    c.setLineWidth(1.1)
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        c.line(x1, y1, x2, y2)
    c.restoreState()

    (x1, y1), (x2, y2) = points[-2], points[-1]
    angle = math.atan2(y2 - y1, x2 - x1)
    head = 7
    a1 = angle + math.pi - math.pi / 8
    a2 = angle + math.pi + math.pi / 8
    c.line(x2, y2, x2 + head * math.cos(a1), y2 + head * math.sin(a1))
    c.line(x2, y2, x2 + head * math.cos(a2), y2 + head * math.sin(a2))

    if text and text_pos:
        set_font(c, 8)
        c.drawString(text_pos[0], text_pos[1], text)


def fig1(path: Path):
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    set_font(c, 10)

    draw_box(c, 356, 532, 130, 28, "用户请求", size=11)

    draw_frame(c, 64, 402, 714, 92, "语义能力路由层")
    draw_box(c, 72, 424, 90, 40, "预设命名空间")
    draw_box(c, 182, 424, 90, 40, "候选召回")
    draw_box(c, 292, 424, 92, 40, "路由裁决\n快路径与协同决策")
    draw_box(c, 404, 424, 90, 40, "覆盖控制")
    draw_box(c, 514, 424, 92, 40, "主能力地址\n与相关能力地址")
    arrow(c, 162, 444, 182, 444)
    arrow(c, 272, 444, 292, 444)
    arrow(c, 384, 444, 404, 444)
    arrow(c, 494, 444, 514, 444)

    draw_frame(c, 262, 292, 318, 74, "语义地址输出层")
    draw_box(c, 318, 312, 206, 36, "最终主能力地址与最终相关能力地址")

    draw_frame(c, 64, 174, 714, 84, "实例执行层")
    draw_box(c, 96, 196, 100, 38, "注册快照")
    draw_box(c, 242, 188, 148, 54, "实例候选过滤\n按主能力地址、状态、端点和兼容性")
    draw_box(c, 436, 188, 146, 54, "综合评分与排序\n匹配度、健康度和公平度")
    draw_box(c, 628, 196, 118, 38, "目标实例地址\n与调用端点")
    arrow(c, 196, 215, 242, 215)
    arrow(c, 390, 215, 436, 215)
    arrow(c, 582, 215, 628, 215)

    draw_frame(c, 192, 74, 458, 66, "结构化轨迹层")
    draw_box(c, 286, 89, 270, 34, "结构化决策轨迹")

    poly_arrow(c, [(421, 424), (421, 348)])
    poly_arrow(c, [(421, 312), (421, 268), (316, 268), (316, 242)], dashed=True, text="约束实例候选过滤", text_pos=(430, 270))
    poly_arrow(c, [(338, 424), (338, 140), (338, 123)])
    poly_arrow(c, [(509, 188), (509, 140), (509, 123)])

    c.showPage()
    c.save()


def fig2(path: Path):
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    draw_frame(c, 70, 342, 700, 132, "语义能力地址层")
    draw_box(c, 94, 390, 100, 38, "用户请求")
    draw_box(c, 224, 380, 158, 56, "语义能力地址候选集合")
    draw_box(c, 430, 390, 110, 38, "最终主能力地址")
    draw_box(c, 586, 390, 116, 38, "最终相关能力地址")
    arrow(c, 194, 409, 224, 409)
    arrow(c, 382, 409, 430, 409)
    arrow(c, 382, 409, 586, 409)

    draw_frame(c, 70, 150, 700, 132, "智能体实例地址层")
    draw_box(c, 94, 198, 110, 38, "注册快照")
    draw_box(c, 238, 188, 172, 56, "精确对应的实例候选集合")
    draw_box(c, 456, 198, 120, 38, "目标实例地址")
    draw_box(c, 620, 198, 82, 38, "调用端点")
    arrow(c, 204, 217, 238, 217)
    arrow(c, 410, 217, 456, 217)
    arrow(c, 576, 217, 620, 217)

    arrow(c, 485, 390, 324, 244, dashed=True, text="作为实例筛选前提", text_dx=-10, text_dy=8)
    c.showPage()
    c.save()


def fig3(path: Path):
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    draw_box(c, 56, 272, 146, 56, "快路径裁决结果\n与语义交接信息")
    draw_box(c, 240, 278, 112, 44, "候选视图构造")

    draw_frame(c, 372, 148, 286, 284, "职责角色协同层")
    draw_box(c, 438, 378, 154, 34, "共享候选视图")
    draw_box(c, 394, 292, 86, 52, "领域专家角色\n语义匹配复核", size=9)
    draw_box(c, 522, 292, 86, 52, "治理风险角色\n风险约束复核", size=9)
    draw_box(c, 394, 214, 86, 52, "层级解析角色\n层级冲突复核", size=9)
    draw_box(c, 522, 214, 86, 52, "用户偏好角色\n偏好恢复复核", size=9)
    draw_box(c, 450, 166, 130, 36, "角色提案聚合")

    draw_box(c, 692, 278, 94, 44, "覆盖授权判断")

    draw_frame(c, 688, 166, 110, 76, "决策输出")
    draw_box(c, 702, 198, 82, 22, "最终主能力地址", size=8)
    draw_box(c, 702, 170, 82, 22, "最终相关能力地址", size=8)

    arrow(c, 202, 300, 240, 300)
    arrow(c, 352, 300, 438, 395)

    arrow(c, 476, 378, 437, 344)
    arrow(c, 502, 378, 565, 344)
    arrow(c, 528, 378, 437, 266)
    arrow(c, 554, 378, 565, 266)

    poly_arrow(c, [(437, 292), (437, 250), (432, 250), (432, 202), (490, 202)])
    poly_arrow(c, [(565, 292), (565, 250), (598, 250), (598, 202), (540, 202)])
    poly_arrow(c, [(437, 214), (437, 202), (490, 202)])
    poly_arrow(c, [(565, 214), (565, 202), (540, 202)])

    arrow(c, 580, 184, 692, 300)
    arrow(c, 739, 278, 743, 220)
    arrow(c, 739, 278, 743, 192)

    c.showPage()
    c.save()


def fig4(path: Path):
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    draw_frame(c, 72, 250, 320, 120, "过滤阶段")
    draw_box(c, 98, 290, 92, 40, "注册快照")
    draw_box(c, 218, 282, 148, 56, "实例候选过滤\n按主能力地址、状态、端点和兼容性")
    arrow(c, 190, 310, 218, 310)

    draw_frame(c, 444, 250, 220, 120, "评分与排序阶段")
    draw_box(c, 468, 282, 90, 56, "实例综合评分\n匹配度、健康度和公平度")
    draw_box(c, 582, 290, 58, 40, "实例排序")
    arrow(c, 558, 310, 582, 310)

    draw_box(c, 700, 286, 96, 48, "目标实例地址\n与调用端点")
    arrow(c, 366, 310, 468, 310)
    arrow(c, 640, 310, 700, 310)

    c.showPage()
    c.save()


def fig5(path: Path):
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    draw_frame(c, 82, 112, 430, 376, "结构化决策轨迹对象")
    draw_box(c, 124, 406, 346, 42, "召回字段组：候选集合、候选相关度、混淆源标记", size=9)
    draw_box(c, 124, 336, 346, 42, "快路径字段组：初始主能力地址、相关能力地址、触发原因", size=9)
    draw_box(c, 124, 266, 346, 42, "协同决策字段组：语义交接信息、角色提案、覆盖结果", size=9)
    draw_box(c, 124, 196, 346, 42, "实例选择字段组：过滤原因、综合评分、排序结果", size=9)
    draw_box(c, 124, 126, 346, 42, "输出字段组：最终主能力地址、相关能力地址、目标实例地址", size=9)
    arrow(c, 297, 406, 297, 378)
    arrow(c, 297, 336, 297, 308)
    arrow(c, 297, 266, 297, 238)
    arrow(c, 297, 196, 297, 168)

    draw_frame(c, 568, 188, 198, 180, "轨迹用途")
    draw_box(c, 596, 314, 142, 28, "支持回放")
    draw_box(c, 596, 276, 142, 28, "支持归因")
    draw_box(c, 596, 238, 142, 28, "支持审计")
    draw_box(c, 596, 200, 142, 28, "支持错误定位")
    arrow(c, 470, 286, 568, 286)

    c.showPage()
    c.save()


def render_png(pdf_path: Path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
    pix.save(str(pdf_path.with_suffix(".png")))


def main():
    figures = [
        ("图1_系统总体结构示意图.pdf", fig1),
        ("图2_两层地址关系示意图.pdf", fig2),
        ("图3_协同决策结构示意图.pdf", fig3),
        ("图4_实例过滤与排序过程示意图.pdf", fig4),
        ("图5_决策轨迹组织示意图.pdf", fig5),
    ]
    for name, fn in figures:
        path = OUT_DIR / name
        fn(path)
        render_png(path)


if __name__ == "__main__":
    main()
