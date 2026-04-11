from __future__ import annotations

from math import hypot
from pathlib import Path


OUT = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利正式附图版_20260410")
FONT = "PingFang SC, Heiti SC, Microsoft YaHei, sans-serif"


def svg_header(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
    ]


def svg_footer() -> list[str]:
    return ["</svg>"]


def text_center(x: float, y: float, lines: list[str], size: int = 32, bold: bool = False) -> list[str]:
    weight = "700" if bold else "400"
    line_gap = int(size * 1.35)
    start_y = y - ((len(lines) - 1) * line_gap) / 2
    out = []
    for idx, line in enumerate(lines):
        cy = start_y + idx * line_gap
        out.append(
            f'  <text x="{x}" y="{cy}" text-anchor="middle" '
            f'font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="#000000">{line}</text>'
        )
    return out


def text_left(x: float, y: float, text: str, size: int = 30, bold: bool = False) -> str:
    weight = "700" if bold else "400"
    return (
        f'  <text x="{x}" y="{y}" text-anchor="start" font-family="{FONT}" '
        f'font-size="{size}" font-weight="{weight}" fill="#000000">{text}</text>'
    )


def rect_box(x: float, y: float, w: float, h: float, lines: list[str], size: int = 30) -> list[str]:
    out = [
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="#000000" stroke-width="4"/>'
    ]
    out.extend(text_center(x + w / 2, y + h / 2 + 4, lines, size=size))
    return out


def frame_box(x: float, y: float, w: float, h: float, title: str, title_x: float | None = None) -> list[str]:
    tx = title_x if title_x is not None else x + 40
    return [
        f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="#000000" stroke-width="4"/>',
        text_left(tx, y + 48, title, size=30, bold=True),
    ]


def diamond(cx: float, cy: float, hw: float, hh: float, lines: list[str], size: int = 30) -> list[str]:
    pts = f"{cx},{cy-hh} {cx+hw},{cy} {cx},{cy+hh} {cx-hw},{cy}"
    out = [f'  <polygon points="{pts}" fill="#ffffff" stroke="#000000" stroke-width="4"/>']
    out.extend(text_center(cx, cy + 6, lines, size=size))
    return out


def arrow_line(x1: float, y1: float, x2: float, y2: float, stroke: int = 4, head_len: int = 24, head_w: int = 16) -> list[str]:
    dx = x2 - x1
    dy = y2 - y1
    length = hypot(dx, dy)
    if length == 0:
        return []
    ux = dx / length
    uy = dy / length
    lx = x2 - ux * head_len
    ly = y2 - uy * head_len
    px = -uy
    py = ux
    left_x = lx + px * head_w
    left_y = ly + py * head_w
    right_x = lx - px * head_w
    right_y = ly - py * head_w
    return [
        f'  <line x1="{x1}" y1="{y1}" x2="{lx}" y2="{ly}" stroke="#000000" stroke-width="{stroke}" fill="none"/>',
        f'  <polygon points="{x2},{y2} {left_x},{left_y} {right_x},{right_y}" fill="#000000"/>',
    ]


def plain_line(x1: float, y1: float, x2: float, y2: float, stroke: int = 4) -> str:
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#000000" stroke-width="{stroke}" fill="none"/>'


def write_svg(name: str, lines: list[str]) -> None:
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def fig1() -> None:
    w, h = 1700, 2200
    s = svg_header(w, h)
    s.extend(text_center(w / 2, 58, ["图1"], size=42, bold=True))
    s.extend(rect_box(440, 120, 820, 120, ["S101 接收用户请求"], size=32))
    s.extend(arrow_line(850, 240, 850, 340))
    s.extend(rect_box(360, 340, 980, 130, ["S102 召回处理，获得语义能力地址候选集合"], size=30))
    s.extend(arrow_line(850, 470, 850, 590))
    s.extend(rect_box(360, 590, 980, 130, ["S103 快路径裁决"], size=32))
    s.extend(arrow_line(850, 720, 850, 820))
    s.extend(diamond(850, 1010, 260, 150, ["S104 是否满足", "慢路径触发条件"], size=30))

    s.extend(text_center(500, 968, ["是"], size=28, bold=True))
    s.extend(arrow_line(710, 1125, 710, 1260))
    s.extend(rect_box(400, 1260, 620, 120, ["S105 异质共识处理"], size=32))
    s.extend(arrow_line(710, 1380, 710, 1500))
    s.extend(rect_box(470, 1500, 760, 120, ["S106 覆盖控制步骤"], size=32))

    s.extend(text_center(1190, 968, ["否"], size=28, bold=True))
    s.extend(arrow_line(1110, 1010, 1460, 1010))
    s.append(plain_line(1460, 1010, 1460, 1560))
    s.extend(arrow_line(1460, 1560, 1230, 1560))

    s.extend(arrow_line(850, 1620, 850, 1740))
    s.extend(rect_box(300, 1740, 1100, 120, ["S107 筛选智能体实例地址候选集合"], size=30))
    s.extend(arrow_line(850, 1860, 850, 1980))
    s.extend(rect_box(300, 1980, 1100, 120, ["S108 过滤和排序"], size=32))
    s.extend(arrow_line(850, 2100, 850, 2180))
    s.extend(rect_box(170, 2140, 1360, 140, ["S109 输出最终主能力地址、最终相关能力地址、", "目标智能体实例地址、调用端点及结构化决策轨迹"], size=28))
    s.extend(svg_footer())
    write_svg("图1_总体流程示意图.svg", s)


def fig2() -> None:
    w, h = 2100, 1450
    s = svg_header(w, h)
    s.extend(text_center(w / 2, 58, ["图2"], size=42, bold=True))
    s.extend(frame_box(110, 120, 1880, 480, "语义能力地址层", title_x=250))
    s.extend(rect_box(190, 260, 260, 110, ["用户请求"], size=32))
    s.extend(rect_box(600, 260, 360, 110, ["预设命名空间"], size=32))
    s.extend(rect_box(1110, 225, 380, 180, ["语义能力地址", "候选集合"], size=32))
    s.extend(rect_box(1610, 210, 280, 110, ["最终主能力地址"], size=30))
    s.extend(rect_box(1610, 355, 280, 110, ["最终相关能力地址"], size=30))
    s.extend(arrow_line(450, 315, 600, 315))
    s.extend(arrow_line(960, 315, 1110, 315))
    s.extend(arrow_line(1490, 280, 1610, 265))
    s.extend(arrow_line(1490, 350, 1610, 410))

    s.extend(frame_box(110, 730, 1880, 560, "智能体实例地址层", title_x=250))
    s.extend(rect_box(200, 910, 360, 130, ["智能体注册快照"], size=30))
    s.extend(rect_box(770, 860, 500, 220, ["与最终主能力地址", "精确对应的实例候选集合"], size=30))
    s.extend(rect_box(1450, 910, 340, 130, ["目标智能体实例地址"], size=30))
    s.extend(rect_box(1840, 910, 120, 130, ["调用端点"], size=30))
    s.extend(arrow_line(560, 975, 770, 975))
    s.extend(arrow_line(1270, 975, 1450, 975))
    s.extend(arrow_line(1790, 975, 1840, 975))
    s.append(plain_line(1750, 465, 1750, 690))
    s.append(plain_line(1750, 690, 1020, 690))
    s.extend(arrow_line(1020, 690, 1020, 860))
    s.extend(svg_footer())
    write_svg("图2_两层地址关系示意图.svg", s)


def fig3() -> None:
    w, h = 2000, 1400
    s = svg_header(w, h)
    s.extend(text_center(w / 2, 58, ["图3"], size=42, bold=True))
    s.extend(rect_box(120, 140, 340, 110, ["快路径裁决结果"], size=30))
    s.extend(rect_box(580, 140, 380, 110, ["语义交接信息"], size=30))
    s.extend(rect_box(1120, 140, 420, 110, ["候选视图构造"], size=30))
    s.extend(arrow_line(460, 195, 580, 195))
    s.extend(arrow_line(960, 195, 1120, 195))

    role_y = 500
    s.extend(rect_box(120, role_y, 280, 110, ["领域专家角色"], size=30))
    s.extend(rect_box(490, role_y, 280, 110, ["治理风险角色"], size=30))
    s.extend(rect_box(860, role_y, 280, 110, ["层级解析角色"], size=30))
    s.extend(rect_box(1230, role_y, 280, 110, ["用户偏好角色"], size=30))

    s.extend(arrow_line(1330, 250, 260, role_y))
    s.extend(arrow_line(1330, 250, 630, role_y))
    s.extend(arrow_line(1330, 250, 1000, role_y))
    s.extend(arrow_line(1330, 250, 1370, role_y))

    s.extend(rect_box(430, 820, 780, 130, ["角色提案和角色信号聚合"], size=32))
    s.extend(rect_box(1390, 820, 340, 130, ["覆盖控制单元"], size=30))
    s.extend(arrow_line(260, 610, 580, 820))
    s.extend(arrow_line(630, 610, 740, 820))
    s.extend(arrow_line(1000, 610, 900, 820))
    s.extend(arrow_line(1370, 610, 1060, 820))
    s.extend(arrow_line(1210, 885, 1390, 885))

    s.extend(rect_box(380, 1140, 360, 120, ["最终主能力地址"], size=30))
    s.extend(rect_box(920, 1140, 360, 120, ["最终相关能力地址"], size=30))
    s.extend(arrow_line(1560, 950, 560, 1140))
    s.extend(arrow_line(1560, 950, 1100, 1140))
    s.extend(svg_footer())
    write_svg("图3_异质共识与覆盖控制结构示意图.svg", s)


def fig4() -> None:
    w, h = 2100, 1500
    s = svg_header(w, h)
    s.extend(text_center(w / 2, 58, ["图4"], size=42, bold=True))
    top_y = 160
    s.extend(rect_box(100, top_y, 290, 110, ["智能体注册快照"], size=30))
    s.extend(rect_box(470, top_y, 310, 110, ["精确地址匹配过滤"], size=30))
    s.extend(rect_box(860, top_y, 290, 110, ["实例状态过滤"], size=30))
    s.extend(rect_box(1230, top_y, 290, 110, ["调用端点过滤"], size=30))
    s.extend(rect_box(1600, top_y, 220, 110, ["模式过滤"], size=30))
    s.extend(arrow_line(390, 215, 470, 215))
    s.extend(arrow_line(780, 215, 860, 215))
    s.extend(arrow_line(1150, 215, 1230, 215))
    s.extend(arrow_line(1520, 215, 1600, 215))

    s.append(plain_line(1710, 270, 1710, 470))
    s.append(plain_line(1710, 470, 1030, 470))

    s.extend(rect_box(220, 620, 330, 110, ["实例匹配度计算"], size=30))
    s.extend(rect_box(660, 620, 280, 110, ["健康度计算"], size=30))
    s.extend(rect_box(1050, 620, 360, 110, ["实例曝光公平度计算"], size=28))
    s.extend(rect_box(1520, 620, 380, 110, ["提供方曝光公平度计算"], size=28))
    s.extend(arrow_line(1030, 470, 385, 620))
    s.extend(arrow_line(1030, 470, 800, 620))
    s.extend(arrow_line(1030, 470, 1230, 620))
    s.extend(arrow_line(1030, 470, 1710, 620))

    s.extend(rect_box(650, 1010, 800, 130, ["排序得分生成"], size=34))
    s.extend(arrow_line(385, 730, 830, 1010))
    s.extend(arrow_line(800, 730, 930, 1010))
    s.extend(arrow_line(1230, 730, 1170, 1010))
    s.extend(arrow_line(1710, 730, 1270, 1010))

    s.extend(rect_box(760, 1280, 580, 130, ["目标智能体实例地址及调用端点"], size=30))
    s.extend(arrow_line(1050, 1140, 1050, 1280))
    s.extend(svg_footer())
    write_svg("图4_实例过滤与排序过程示意图.svg", s)


def fig5() -> None:
    w, h = 1800, 2100
    s = svg_header(w, h)
    s.extend(text_center(w / 2, 58, ["图5"], size=42, bold=True))
    s.extend(frame_box(130, 110, 1540, 1860, "结构化决策轨迹", title_x=780))

    s.extend(rect_box(280, 240, 1240, 200, ["召回阶段字段组", "语义能力地址候选集合、候选相关度、混淆源标记"], size=30))
    s.extend(rect_box(280, 560, 1240, 240, ["快路径阶段字段组", "初始主能力地址、初始相关能力地址、裁决置信度、", "候选竞争差值、慢路径触发原因"], size=28))
    s.extend(rect_box(280, 920, 1240, 240, ["慢路径阶段字段组", "语义交接信息、角色提案、角色信号、", "聚合结果、覆盖阻断原因"], size=28))
    s.extend(rect_box(280, 1280, 1240, 260, ["实例选择阶段字段组", "实例过滤原因、实例匹配度、健康度、实例曝光公平度、", "提供方曝光公平度、最终排序得分"], size=28))
    s.extend(rect_box(280, 1660, 1240, 190, ["输出阶段字段组", "最终主能力地址、最终相关能力地址、", "目标智能体实例地址、调用端点"], size=28))

    s.extend(arrow_line(900, 440, 900, 560))
    s.extend(arrow_line(900, 800, 900, 920))
    s.extend(arrow_line(900, 1160, 900, 1280))
    s.extend(arrow_line(900, 1540, 900, 1660))
    s.extend(svg_footer())
    write_svg("图5_结构化决策轨迹数据组织示意图.svg", s)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()


if __name__ == "__main__":
    main()
