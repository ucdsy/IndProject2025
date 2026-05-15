from __future__ import annotations

import shutil
import subprocess
from math import hypot
from pathlib import Path


SRC = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利高质量附图版_20260413")
OUT = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利定稿附图版_20260413")
FONT = "PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif"


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_header(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "  <defs>",
        "    <style>",
        f"      .title{{font-family:{FONT};font-size:42px;font-weight:700;fill:#111;}}",
        f"      .group{{font-family:{FONT};font-size:24px;font-weight:700;fill:#222;}}",
        f"      .label{{font-family:{FONT};font-size:28px;font-weight:500;fill:#111;}}",
        f"      .small{{font-family:{FONT};font-size:24px;font-weight:500;fill:#111;}}",
        f"      .tiny{{font-family:{FONT};font-size:21px;font-weight:500;fill:#222;}}",
        "      .frame{fill:#fff;stroke:#111;stroke-width:3.2;vector-effect:non-scaling-stroke;}",
        "      .box{fill:#fff;stroke:#111;stroke-width:3.8;vector-effect:non-scaling-stroke;}",
        "      .line{fill:none;stroke:#111;stroke-width:3.4;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;}",
        "    </style>",
        "  </defs>",
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
    ]


def svg_footer() -> list[str]:
    return ["</svg>"]


def text_lines(x: float, y: float, lines: list[str], klass: str = "label", anchor: str = "middle") -> list[str]:
    gaps = {"label": 36, "small": 31, "tiny": 27, "group": 28, "title": 44}
    gap = gaps.get(klass, 32)
    start_y = y - ((len(lines) - 1) * gap) / 2
    return [
        f'  <text x="{x}" y="{start_y + i * gap}" text-anchor="{anchor}" class="{klass}">{esc(line)}</text>'
        for i, line in enumerate(lines)
    ]


def group_label(x: float, y: float, text: str) -> list[str]:
    return [f'  <text x="{x}" y="{y}" text-anchor="start" class="group">{esc(text)}</text>']


def frame(x: float, y: float, w: float, h: float) -> str:
    return f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" ry="18" class="frame"/>'


def box(x: float, y: float, w: float, h: float, lines: list[str], klass: str = "small", rx: int = 16) -> list[str]:
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" class="box"/>']
    out.extend(text_lines(x + w / 2, y + h / 2 + 2, lines, klass=klass))
    return out


def line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="line"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, head_len: int = 20, head_w: int = 13) -> list[str]:
    dx = x2 - x1
    dy = y2 - y1
    d = hypot(dx, dy)
    if not d:
        return []
    ux = dx / d
    uy = dy / d
    bx = x2 - ux * head_len
    by = y2 - uy * head_len
    px = -uy
    py = ux
    lx = bx + px * head_w
    ly = by + py * head_w
    rx = bx - px * head_w
    ry = by - py * head_w
    return [
        line(x1, y1, bx, by),
        f'  <polygon points="{x2},{y2} {lx},{ly} {rx},{ry}" fill="#111"/>',
    ]


def poly(points: list[tuple[float, float]], arrow_end: bool = False) -> list[str]:
    if len(points) < 2:
        return []
    out: list[str] = []
    limit = len(points) - 1 if not arrow_end else len(points) - 2
    for i in range(limit):
        out.append(line(*points[i], *points[i + 1]))
    if arrow_end:
        out.extend(arrow(*points[-2], *points[-1]))
    return out


def write_svg(name: str, lines: list[str]) -> None:
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def fig1() -> None:
    w, h = 2200, 1380
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 66, ["图1"], klass="title"))

    s.extend(group_label(120, 145, "输入与语义能力层"))
    s.append(frame(100, 170, 1460, 430))
    s.extend(box(150, 305, 260, 94, ["用户请求"], rx=22))
    s.extend(box(520, 235, 280, 86, ["预设命名空间"], klass="tiny", rx=18))
    s.extend(box(520, 375, 280, 86, ["候选召回"], klass="tiny", rx=18))
    s.extend(box(910, 235, 280, 86, ["快路径裁决"], klass="tiny", rx=18))
    s.extend(box(910, 375, 280, 86, ["慢路径共识"], klass="tiny", rx=18))
    s.extend(box(1300, 305, 180, 94, ["覆盖控制"], klass="tiny", rx=18))

    s.extend(arrow(410, 352, 520, 278))
    s.extend(arrow(410, 352, 520, 418))
    s.extend(arrow(800, 278, 910, 278))
    s.extend(arrow(800, 418, 910, 418))
    s.extend(arrow(1190, 278, 1300, 330))
    s.extend(arrow(1190, 418, 1300, 374))

    s.extend(group_label(1660, 145, "语义结果输出"))
    s.append(frame(1630, 170, 450, 430))
    s.extend(box(1710, 255, 290, 96, ["最终主能力地址"], rx=22))
    s.extend(box(1710, 415, 290, 96, ["最终相关能力地址"], rx=22))
    s.extend(arrow(1480, 330, 1710, 303))
    s.extend(arrow(1480, 374, 1710, 463))

    s.extend(group_label(120, 690, "实例执行层"))
    s.append(frame(100, 715, 1980, 430))
    s.extend(box(150, 882, 280, 96, ["智能体注册快照"], rx=22))
    s.extend(box(590, 882, 360, 96, ["精确匹配过滤"], rx=22))
    s.extend(box(1070, 812, 300, 86, ["实例匹配度"], klass="tiny", rx=18))
    s.extend(box(1070, 938, 300, 86, ["健康度"], klass="tiny", rx=18))
    s.extend(box(1450, 812, 320, 86, ["实例曝光公平度"], klass="tiny", rx=18))
    s.extend(box(1450, 938, 320, 86, ["提供方曝光公平度"], klass="tiny", rx=18))
    s.extend(box(1840, 882, 180, 96, ["实例排序"], klass="tiny", rx=18))

    s.extend(arrow(430, 930, 590, 930))
    s.extend(arrow(950, 930, 1070, 855))
    s.extend(arrow(950, 930, 1070, 981))
    s.extend(arrow(1370, 855, 1450, 855))
    s.extend(arrow(1370, 981, 1450, 981))
    s.extend(poly([(1770, 855), (1810, 855), (1810, 915), (1840, 915)], arrow_end=True))
    s.extend(poly([(1770, 981), (1810, 981), (1810, 945), (1840, 945)], arrow_end=True))

    s.extend(group_label(120, 1235, "最终输出与轨迹"))
    s.append(frame(100, 1260, 1980, 90))
    s.extend(box(260, 1276, 320, 58, ["目标智能体实例地址"], klass="tiny", rx=14))
    s.extend(box(760, 1276, 220, 58, ["调用端点"], klass="tiny", rx=14))
    s.extend(box(1250, 1276, 360, 58, ["结构化决策轨迹"], klass="tiny", rx=14))
    s.extend(arrow(1930, 978, 420, 1276))
    s.extend(arrow(1930, 930, 870, 1276))
    s.extend(poly([(1390, 600), (1390, 1230), (1430, 1230), (1430, 1276)], arrow_end=True))

    s.extend(svg_footer())
    write_svg("图1_系统总体结构示意图.svg", s)


def fig2() -> None:
    w, h = 2200, 1380
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 66, ["图2"], klass="title"))

    s.extend(group_label(120, 145, "语义能力地址层"))
    s.append(frame(100, 170, 1980, 470))
    s.extend(box(170, 355, 240, 92, ["用户请求"], rx=22))
    s.extend(box(530, 355, 280, 92, ["预设命名空间"], klass="tiny", rx=18))
    s.extend(box(930, 305, 360, 190, ["语义能力地址", "候选集合"], klass="small", rx=22))
    s.extend(box(1450, 270, 260, 86, ["最终主能力地址"], klass="tiny", rx=18))
    s.extend(box(1450, 444, 260, 86, ["最终相关能力地址"], klass="tiny", rx=18))
    s.extend(arrow(410, 401, 530, 401))
    s.extend(arrow(810, 401, 930, 401))
    s.extend(arrow(1290, 342, 1450, 313))
    s.extend(arrow(1290, 458, 1450, 487))

    s.extend(group_label(120, 740, "智能体实例地址层"))
    s.append(frame(100, 765, 1980, 470))
    s.extend(box(170, 950, 300, 92, ["智能体注册快照"], rx=22))
    s.extend(box(650, 900, 500, 192, ["与最终主能力地址", "精确对应的实例候选集合"], klass="small", rx=22))
    s.extend(box(1350, 950, 260, 92, ["目标智能体实例地址"], klass="tiny", rx=18))
    s.extend(box(1770, 950, 180, 92, ["调用端点"], klass="tiny", rx=18))
    s.extend(arrow(470, 996, 650, 996))
    s.extend(arrow(1150, 996, 1350, 996))
    s.extend(arrow(1610, 996, 1770, 996))
    s.extend(poly([(1580, 356), (1580, 820), (900, 820), (900, 900)], arrow_end=True))

    s.extend(svg_footer())
    write_svg("图2_两层地址关系示意图.svg", s)


def fig3() -> None:
    w, h = 2200, 1380
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 66, ["图3"], klass="title"))

    s.extend(group_label(120, 150, "输入与视图构造"))
    s.append(frame(100, 175, 1080, 260))
    s.extend(box(150, 275, 260, 86, ["快路径裁决结果"], klass="tiny", rx=18))
    s.extend(box(500, 275, 300, 86, ["语义交接信息"], klass="tiny", rx=18))
    s.extend(box(900, 245, 220, 146, ["候选视图", "构造"], klass="tiny", rx=18))
    s.extend(arrow(410, 318, 500, 318))
    s.extend(arrow(800, 318, 900, 318))

    s.extend(group_label(120, 520, "职责角色层"))
    s.append(frame(100, 545, 1980, 280))
    role_xs = [170, 660, 1150, 1640]
    role_titles = ["领域专家角色", "治理风险角色", "层级解析角色", "用户偏好角色"]
    role_tags = ["语义匹配", "风险约束", "层级冲突", "偏好恢复"]
    for x, title, tag in zip(role_xs, role_titles, role_tags):
        s.extend(box(x, 610, 320, 96, [title], klass="tiny", rx=18))
        s.extend(box(x + 70, 730, 180, 54, [tag], klass="tiny", rx=14))
    bus_y = 520
    s.extend(poly([(1010, 391), (1010, bus_y), (330, bus_y), (330, 610)], arrow_end=True))
    s.extend(poly([(1010, 391), (1010, bus_y), (820, bus_y), (820, 610)], arrow_end=True))
    s.extend(poly([(1010, 391), (1010, bus_y), (1310, bus_y), (1310, 610)], arrow_end=True))
    s.extend(poly([(1010, 391), (1010, bus_y), (1800, bus_y), (1800, 610)], arrow_end=True))

    s.extend(group_label(500, 910, "聚合与授权"))
    s.append(frame(480, 935, 1080, 250))
    s.extend(box(560, 1020, 640, 92, ["角色提案和角色信号聚合"], klass="small", rx=18))
    s.extend(box(1290, 1010, 210, 112, ["覆盖授权判断"], klass="tiny", rx=18))
    s.extend(arrow(1200, 1066, 1290, 1066))
    s.extend(arrow(330, 784, 760, 1020))
    s.extend(arrow(820, 784, 880, 1020))
    s.extend(arrow(1310, 784, 1000, 1020))
    s.extend(arrow(1800, 784, 1120, 1020))

    s.extend(group_label(1640, 910, "输出结果"))
    s.append(frame(1610, 935, 470, 250))
    s.extend(box(1660, 1000, 370, 74, ["最终主能力地址"], klass="tiny", rx=16))
    s.extend(box(1660, 1095, 370, 74, ["最终相关能力地址"], klass="tiny", rx=16))
    s.extend(arrow(1500, 1045, 1660, 1037))
    s.extend(arrow(1500, 1087, 1660, 1132))

    s.extend(svg_footer())
    write_svg("图3_协同决策结构示意图.svg", s)


def fig4() -> None:
    w, h = 2200, 1380
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 66, ["图4"], klass="title"))

    s.extend(group_label(120, 145, "过滤阶段"))
    s.append(frame(100, 170, 1980, 320))
    xs = [140, 530, 920, 1310, 1700]
    labels = [
        ["智能体注册快照"],
        ["精确地址匹配过滤"],
        ["实例状态过滤"],
        ["调用端点过滤"],
        ["模式兼容性过滤"],
    ]
    ws = [280, 300, 260, 260, 260]
    for i, (x, lines, wbox) in enumerate(zip(xs, labels, ws)):
        s.extend(box(x, 285, wbox, 92, lines, klass="tiny", rx=18))
        if i < len(xs) - 1:
            s.extend(arrow(x + wbox, 331, xs[i + 1], 331))

    s.extend(group_label(120, 600, "评分与排序阶段"))
    s.append(frame(100, 625, 1980, 420))
    s.extend(box(240, 745, 270, 80, ["实例匹配度"], klass="tiny", rx=16))
    s.extend(box(650, 745, 220, 80, ["健康度"], klass="tiny", rx=16))
    s.extend(box(1010, 745, 300, 80, ["实例曝光公平度"], klass="tiny", rx=16))
    s.extend(box(1450, 745, 320, 80, ["提供方曝光公平度"], klass="tiny", rx=16))
    s.extend(box(820, 915, 540, 90, ["排序得分生成"], klass="tiny", rx=18))
    s.extend(poly([(1830, 377), (1830, 690), (375, 690), (375, 745)], arrow_end=True))
    s.extend(poly([(1830, 377), (1830, 690), (760, 690), (760, 745)], arrow_end=True))
    s.extend(poly([(1830, 377), (1830, 690), (1160, 690), (1160, 745)], arrow_end=True))
    s.extend(poly([(1830, 377), (1830, 690), (1610, 690), (1610, 745)], arrow_end=True))
    s.extend(arrow(375, 825, 940, 915))
    s.extend(arrow(760, 825, 1040, 915))
    s.extend(arrow(1160, 825, 1140, 915))
    s.extend(arrow(1610, 825, 1240, 915))

    s.extend(group_label(760, 1130, "输出"))
    s.append(frame(740, 1155, 720, 130))
    s.extend(box(790, 1185, 620, 70, ["目标智能体实例地址及调用端点"], klass="tiny", rx=16))
    s.extend(arrow(1090, 1005, 1090, 1185))

    s.extend(svg_footer())
    write_svg("图4_实例过滤与排序过程示意图.svg", s)


def fig5() -> None:
    w, h = 2200, 1480
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 66, ["图5"], klass="title"))

    s.extend(group_label(120, 145, "结构化决策轨迹对象"))
    s.append(frame(100, 170, 1580, 1190))
    s.extend(box(220, 255, 1340, 120, ["召回阶段字段组", "语义能力地址候选集合、候选相关度、混淆源标记"], klass="tiny", rx=18))
    s.extend(box(220, 455, 1340, 150, ["快路径阶段字段组", "初始主能力地址、初始相关能力地址、裁决置信度、候选竞争差值、慢路径触发原因"], klass="tiny", rx=18))
    s.extend(box(220, 695, 1340, 150, ["慢路径阶段字段组", "语义交接信息、角色提案、角色信号、聚合结果、覆盖阻断原因"], klass="tiny", rx=18))
    s.extend(box(220, 935, 1340, 170, ["实例选择阶段字段组", "实例过滤原因、实例匹配度、健康度、实例曝光公平度、提供方曝光公平度、最终排序得分"], klass="tiny", rx=18))
    s.extend(box(220, 1185, 1340, 120, ["输出阶段字段组", "最终主能力地址、最终相关能力地址、目标智能体实例地址、调用端点"], klass="tiny", rx=18))
    s.extend(arrow(890, 375, 890, 455))
    s.extend(arrow(890, 605, 890, 695))
    s.extend(arrow(890, 845, 890, 935))
    s.extend(arrow(890, 1105, 890, 1185))

    s.extend(group_label(1780, 220, "可追溯能力"))
    s.append(frame(1750, 245, 330, 540))
    s.extend(box(1805, 315, 220, 70, ["可回放"], klass="tiny", rx=16))
    s.extend(box(1805, 455, 220, 70, ["可归因"], klass="tiny", rx=16))
    s.extend(box(1805, 595, 220, 70, ["可审计"], klass="tiny", rx=16))
    s.extend(arrow(1560, 315, 1805, 350))
    s.extend(arrow(1560, 770, 1805, 490))
    s.extend(arrow(1560, 1245, 1805, 630))

    s.extend(group_label(1780, 910, "错误定位"))
    s.append(frame(1750, 935, 330, 330))
    s.extend(box(1795, 995, 240, 60, ["召回阶段"], klass="tiny", rx=14))
    s.extend(box(1795, 1075, 240, 60, ["裁决阶段"], klass="tiny", rx=14))
    s.extend(box(1795, 1155, 240, 60, ["实例选择阶段"], klass="tiny", rx=14))
    s.extend(arrow(1560, 315, 1795, 1025))
    s.extend(arrow(1560, 530, 1795, 1105))
    s.extend(arrow(1560, 1015, 1795, 1185))

    s.extend(svg_footer())
    write_svg("图5_决策轨迹组织示意图.svg", s)


def build_pdfs() -> None:
    pdf_dir = OUT / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for svg in OUT.glob("*.svg"):
        subprocess.run(
            ["/usr/bin/sips", "-s", "format", "pdf", str(svg), "--out", str(pdf_dir / f"{svg.stem}.pdf")],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / "README.md", OUT / "README.md")
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    build_pdfs()


if __name__ == "__main__":
    main()
