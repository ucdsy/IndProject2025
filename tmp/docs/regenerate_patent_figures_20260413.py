from __future__ import annotations

from math import hypot
from pathlib import Path


OUT = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利高质量附图版_20260413")

PAGE_W = 2100
PAGE_H = 2970

FONT_TEXT = "Songti SC, STSong, SimSun, serif"
FONT_TITLE = "Heiti SC, PingFang SC, Microsoft YaHei, sans-serif"


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_header(width: int = PAGE_W, height: int = PAGE_H) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "  <defs>",
        "    <style>",
        "      .frame{fill:#fff;stroke:#000;stroke-width:5;vector-effect:non-scaling-stroke;}",
        "      .box{fill:#fff;stroke:#000;stroke-width:4.5;vector-effect:non-scaling-stroke;}",
        "      .line{fill:none;stroke:#000;stroke-width:4.5;stroke-linecap:square;stroke-linejoin:miter;vector-effect:non-scaling-stroke;}",
        f"      .title{{font-family:{FONT_TITLE};font-size:48px;font-weight:700;fill:#000;}}",
        f"      .label{{font-family:{FONT_TEXT};font-size:34px;font-weight:400;fill:#000;}}",
        f"      .small{{font-family:{FONT_TEXT};font-size:30px;font-weight:400;fill:#000;}}",
        f"      .tiny{{font-family:{FONT_TEXT};font-size:28px;font-weight:400;fill:#000;}}",
        f"      .group{{font-family:{FONT_TITLE};font-size:32px;font-weight:700;fill:#000;}}",
        "    </style>",
        "  </defs>",
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
    ]


def svg_footer() -> list[str]:
    return ["</svg>"]


def title(label: str) -> list[str]:
    return [f'  <text x="{PAGE_W/2}" y="96" text-anchor="middle" class="title">{esc(label)}</text>']


def text_lines(
    x: float,
    y: float,
    lines: list[str],
    klass: str = "label",
    anchor: str = "middle",
    weight: str | None = None,
) -> list[str]:
    line_gap = 46 if klass == "label" else 40
    start_y = y - ((len(lines) - 1) * line_gap) / 2
    out: list[str] = []
    extra = f' font-weight="{weight}"' if weight else ""
    for i, line in enumerate(lines):
        out.append(
            f'  <text x="{x}" y="{start_y + i * line_gap}" text-anchor="{anchor}" class="{klass}"{extra}>{esc(line)}</text>'
        )
    return out


def rect_box(x: float, y: float, w: float, h: float, lines: list[str], klass: str = "label") -> list[str]:
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" class="box"/>']
    out.extend(text_lines(x + w / 2, y + h / 2 + 4, lines, klass=klass))
    return out


def frame_box(x: float, y: float, w: float, h: float, label_text: str) -> list[str]:
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" class="frame"/>']
    out.append(f'  <rect x="{x + 38}" y="{y - 28}" width="220" height="54" fill="#ffffff"/>')
    out.extend(text_lines(x + 148, y - 2, [label_text], klass="group"))
    return out


def diamond(cx: float, cy: float, hw: float, hh: float, lines: list[str]) -> list[str]:
    pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
    out = [f'  <polygon points="{pts}" class="box"/>']
    out.extend(text_lines(cx, cy + 4, lines, klass="label"))
    return out


def line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="line"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, head_len: int = 26, head_w: int = 18) -> list[str]:
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
        f'  <polygon points="{x2},{y2} {lx},{ly} {rx},{ry}" fill="#000"/>',
    ]


def elbow_arrow(x1: float, y1: float, mx: float, my: float, x2: float, y2: float) -> list[str]:
    return [
        line(x1, y1, mx, my),
        *arrow(mx, my, x2, y2),
    ]


def write_svg(filename: str, lines: list[str]) -> None:
    (OUT / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def fig1() -> None:
    s = svg_header()
    s.extend(title("图1"))

    s.extend(rect_box(520, 180, 1060, 150, ["S101 接收用户请求"]))
    s.extend(arrow(1050, 330, 1050, 430))
    s.extend(rect_box(360, 430, 1380, 170, ["S102 召回处理", "获得语义能力地址候选集合"]))
    s.extend(arrow(1050, 600, 1050, 720))
    s.extend(rect_box(470, 720, 1160, 150, ["S103 快路径裁决"]))
    s.extend(arrow(1050, 870, 1050, 990))
    s.extend(diamond(1050, 1200, 310, 180, ["S104 是否满足", "慢路径触发条件"]))

    s.extend(text_lines(675, 1150, ["是"], klass="small", weight="700"))
    s.extend(arrow(820, 1320, 820, 1450))
    s.extend(rect_box(430, 1450, 780, 150, ["S105 异质共识处理"]))
    s.extend(arrow(820, 1600, 820, 1730))
    s.extend(rect_box(430, 1730, 780, 150, ["S106 覆盖控制步骤"]))

    s.extend(text_lines(1410, 1150, ["否"], klass="small", weight="700"))
    s.extend(arrow(1360, 1200, 1760, 1200))
    s.append(line(1760, 1200, 1760, 1805))
    s.extend(arrow(1760, 1805, 1260, 1805))

    s.extend(arrow(1050, 1880, 1050, 2010))
    s.extend(rect_box(300, 2010, 1500, 150, ["S107 筛选智能体实例地址候选集合"]))
    s.extend(arrow(1050, 2160, 1050, 2290))
    s.extend(rect_box(300, 2290, 1500, 150, ["S108 过滤和排序"]))
    s.extend(arrow(1050, 2440, 1050, 2570))
    s.extend(rect_box(180, 2570, 1740, 180, ["S109 输出最终主能力地址、最终相关能力地址、", "目标智能体实例地址、调用端点及结构化决策轨迹"], klass="small"))

    s.extend(svg_footer())
    write_svg("图1_总体流程示意图.svg", s)


def fig2() -> None:
    s = svg_header()
    s.extend(title("图2"))

    s.extend(frame_box(120, 190, 1860, 950, "语义能力地址层"))
    s.extend(rect_box(210, 420, 290, 140, ["用户请求"]))
    s.extend(rect_box(650, 420, 360, 140, ["预设命名空间"]))
    s.extend(rect_box(1160, 360, 410, 260, ["语义能力地址", "候选集合"]))
    s.extend(rect_box(1710, 320, 190, 130, ["最终主", "能力地址"], klass="small"))
    s.extend(rect_box(1710, 500, 190, 130, ["最终相关", "能力地址"], klass="small"))
    s.extend(arrow(500, 490, 650, 490))
    s.extend(arrow(1010, 490, 1160, 490))
    s.extend(arrow(1570, 430, 1710, 385))
    s.extend(arrow(1570, 550, 1710, 565))
    s.extend(rect_box(670, 760, 880, 180, ["在候选集合内部执行快路径裁决", "以及必要时的慢路径共识处理"]))
    s.extend(arrow(1365, 620, 1180, 760))

    s.extend(frame_box(120, 1340, 1860, 1250, "智能体实例地址层"))
    s.extend(rect_box(220, 1700, 420, 160, ["智能体注册快照"]))
    s.extend(rect_box(770, 1620, 620, 320, ["与最终主能力地址", "精确对应的实例候选集合"]))
    s.extend(rect_box(1530, 1700, 250, 160, ["目标智能体", "实例地址"], klass="small"))
    s.extend(rect_box(1810, 1700, 120, 160, ["调用", "端点"], klass="small"))
    s.extend(arrow(640, 1780, 770, 1780))
    s.extend(arrow(1390, 1780, 1530, 1780))
    s.extend(arrow(1780, 1780, 1810, 1780))

    s.append(line(1805, 630, 1805, 1470))
    s.append(line(1805, 1470, 1080, 1470))
    s.extend(arrow(1080, 1470, 1080, 1620))

    s.extend(rect_box(790, 2120, 580, 180, ["过滤离线、缺失端点、", "模式不兼容等实例"]))
    s.extend(arrow(1080, 1940, 1080, 2120))
    s.extend(rect_box(790, 2360, 580, 180, ["基于匹配度、健康度和", "公平因子进行排序"]))
    s.extend(arrow(1080, 2300, 1080, 2360))

    s.extend(svg_footer())
    write_svg("图2_两层地址关系示意图.svg", s)


def fig3() -> None:
    s = svg_header()
    s.extend(title("图3"))

    s.extend(rect_box(150, 220, 380, 140, ["快路径裁决结果"]))
    s.extend(rect_box(680, 220, 410, 140, ["语义交接信息"]))
    s.extend(rect_box(1240, 220, 480, 140, ["候选视图构造"]))
    s.extend(arrow(530, 290, 680, 290))
    s.extend(arrow(1090, 290, 1240, 290))

    s.extend(frame_box(120, 540, 1760, 610, "职责角色层"))
    s.extend(rect_box(170, 720, 330, 150, ["领域专家角色"]))
    s.extend(rect_box(590, 720, 330, 150, ["治理风险角色"]))
    s.extend(rect_box(1010, 720, 330, 150, ["层级解析角色"]))
    s.extend(rect_box(1430, 720, 330, 150, ["用户偏好角色"]))

    s.extend(elbow_arrow(1480, 360, 335, 540, 335, 720))
    s.extend(elbow_arrow(1480, 360, 755, 540, 755, 720))
    s.extend(elbow_arrow(1480, 360, 1175, 540, 1175, 720))
    s.extend(elbow_arrow(1480, 360, 1595, 540, 1595, 720))

    s.extend(rect_box(390, 1330, 920, 170, ["角色提案和角色信号聚合"]))
    s.extend(rect_box(1440, 1330, 340, 170, ["覆盖控制单元"]))
    s.extend(arrow(335, 870, 620, 1330))
    s.extend(arrow(755, 870, 840, 1330))
    s.extend(arrow(1175, 870, 1060, 1330))
    s.extend(arrow(1595, 870, 1280, 1330))
    s.extend(arrow(1310, 1415, 1440, 1415))

    s.extend(rect_box(330, 1820, 420, 160, ["最终主能力地址"]))
    s.extend(rect_box(930, 1820, 420, 160, ["最终相关能力地址"]))
    s.extend(arrow(1610, 1500, 540, 1820))
    s.extend(arrow(1610, 1500, 1140, 1820))

    s.extend(svg_footer())
    write_svg("图3_异质共识与覆盖控制结构示意图.svg", s)


def fig4() -> None:
    s = svg_header()
    s.extend(title("图4"))

    s.extend(frame_box(140, 220, 1820, 520, "过滤阶段"))
    s.extend(rect_box(210, 420, 300, 150, ["智能体注册快照"]))
    s.extend(rect_box(580, 420, 320, 150, ["精确地址匹配过滤"]))
    s.extend(rect_box(970, 420, 300, 150, ["实例状态过滤"]))
    s.extend(rect_box(1340, 420, 300, 150, ["调用端点过滤"]))
    s.extend(rect_box(1710, 420, 180, 150, ["模式过滤"]))
    s.extend(arrow(510, 495, 580, 495))
    s.extend(arrow(900, 495, 970, 495))
    s.extend(arrow(1270, 495, 1340, 495))
    s.extend(arrow(1640, 495, 1710, 495))

    s.extend(frame_box(140, 930, 1820, 760, "评分与排序阶段"))
    s.extend(rect_box(210, 1160, 320, 150, ["实例匹配度计算"]))
    s.extend(rect_box(610, 1160, 280, 150, ["健康度计算"]))
    s.extend(rect_box(970, 1160, 380, 150, ["实例曝光公平度计算"], klass="small"))
    s.extend(rect_box(1430, 1160, 390, 150, ["提供方曝光公平度计算"], klass="small"))

    s.append(line(1800, 570, 1800, 880))
    s.append(line(1800, 880, 1060, 880))
    s.extend(arrow(1060, 880, 1060, 1040))
    s.extend(arrow(1060, 1040, 370, 1160))
    s.extend(arrow(1060, 1040, 750, 1160))
    s.extend(arrow(1060, 1040, 1160, 1160))
    s.extend(arrow(1060, 1040, 1625, 1160))

    s.extend(rect_box(650, 1500, 800, 170, ["组合生成最终排序得分"]))
    s.extend(arrow(370, 1310, 850, 1500))
    s.extend(arrow(750, 1310, 980, 1500))
    s.extend(arrow(1160, 1310, 1120, 1500))
    s.extend(arrow(1625, 1310, 1250, 1500))

    s.extend(rect_box(700, 1880, 700, 180, ["目标智能体实例地址及调用端点"]))
    s.extend(arrow(1050, 1670, 1050, 1880))

    s.extend(svg_footer())
    write_svg("图4_实例过滤与排序过程示意图.svg", s)


def fig5() -> None:
    s = svg_header()
    s.extend(title("图5"))

    s.extend(frame_box(140, 180, 1820, 2550, "结构化决策轨迹"))

    s.extend(rect_box(260, 420, 1580, 210, ["召回阶段字段组", "语义能力地址候选集合、候选相关度、混淆源标记"]))
    s.extend(rect_box(260, 830, 1580, 260, ["快路径阶段字段组", "初始主能力地址、初始相关能力地址、裁决置信度、", "候选竞争差值、慢路径触发原因"], klass="small"))
    s.extend(rect_box(260, 1290, 1580, 260, ["慢路径阶段字段组", "语义交接信息、角色提案、角色信号、", "聚合结果、覆盖阻断原因"], klass="small"))
    s.extend(rect_box(260, 1750, 1580, 300, ["实例选择阶段字段组", "实例过滤原因、实例匹配度、健康度、实例曝光公平度、", "提供方曝光公平度、最终排序得分"], klass="small"))
    s.extend(rect_box(260, 2250, 1580, 220, ["输出阶段字段组", "最终主能力地址、最终相关能力地址、", "目标智能体实例地址、调用端点"], klass="small"))

    s.extend(arrow(1050, 630, 1050, 830))
    s.extend(arrow(1050, 1090, 1050, 1290))
    s.extend(arrow(1050, 1550, 1050, 1750))
    s.extend(arrow(1050, 2050, 1050, 2250))

    s.extend(svg_footer())
    write_svg("图5_结构化决策轨迹数据组织示意图.svg", s)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    (OUT / "README.md").write_text(
        "\n".join(
            [
                "# 专利高质量附图版 20260413",
                "",
                "本目录为独立矢量附图，不考虑嵌入 docx 的缩放限制。",
                "建议优先使用 SVG 原图；如需插入 Word 或发代理人，可由你自行选择合适缩放比例。",
                "",
                "- 图1_总体流程示意图.svg",
                "- 图2_两层地址关系示意图.svg",
                "- 图3_异质共识与覆盖控制结构示意图.svg",
                "- 图4_实例过滤与排序过程示意图.svg",
                "- 图5_结构化决策轨迹数据组织示意图.svg",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
