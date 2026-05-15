from __future__ import annotations

import shutil
import subprocess
from math import hypot
from pathlib import Path


SRC = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利高质量附图版_20260413")
OUT = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利二次精修附图版_20260413")

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
        f"      .title{{font-family:{FONT};font-size:44px;font-weight:700;fill:#111;}}",
        f"      .group{{font-family:{FONT};font-size:24px;font-weight:700;fill:#222;}}",
        f"      .label{{font-family:{FONT};font-size:30px;font-weight:500;fill:#111;}}",
        f"      .small{{font-family:{FONT};font-size:25px;font-weight:500;fill:#111;}}",
        f"      .tiny{{font-family:{FONT};font-size:22px;font-weight:500;fill:#222;}}",
        "      .solid{fill:#fff;stroke:#111;stroke-width:4;vector-effect:non-scaling-stroke;}",
        "      .dash{fill:#fff;stroke:#111;stroke-width:3.5;stroke-dasharray:14 10;vector-effect:non-scaling-stroke;}",
        "      .line{fill:none;stroke:#111;stroke-width:3.8;stroke-linecap:round;stroke-linejoin:round;vector-effect:non-scaling-stroke;}",
        "    </style>",
        "  </defs>",
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/>',
    ]


def svg_footer() -> list[str]:
    return ["</svg>"]


def text_lines(x: float, y: float, lines: list[str], klass: str = "label", anchor: str = "middle") -> list[str]:
    gap = {"label": 38, "small": 31, "tiny": 27, "group": 28}.get(klass, 32)
    start_y = y - ((len(lines) - 1) * gap) / 2
    return [
        f'  <text x="{x}" y="{start_y + i * gap}" text-anchor="{anchor}" class="{klass}">{esc(line)}</text>'
        for i, line in enumerate(lines)
    ]


def rounded_box(x: float, y: float, w: float, h: float, lines: list[str], klass: str = "label", rx: int = 24, dashed: bool = False) -> list[str]:
    cls = "dash" if dashed else "solid"
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" class="{cls}"/>']
    out.extend(text_lines(x + w / 2, y + h / 2 + 3, lines, klass=klass))
    return out


def group_label(x: float, y: float, text: str) -> list[str]:
    return [f'  <text x="{x}" y="{y}" text-anchor="start" class="group">{esc(text)}</text>']


def line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="line"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, head_len: int = 22, head_w: int = 15) -> list[str]:
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


def polyline(points: list[tuple[float, float]], arrow_end: bool = False) -> list[str]:
    if len(points) < 2:
        return []
    out = [line(*points[i], *points[i + 1]) for i in range(len(points) - 1 - (1 if arrow_end else 0))]
    if arrow_end:
        out.extend(arrow(*points[-2], *points[-1]))
    else:
        out.append(line(*points[-2], *points[-1]))
    return out


def write_svg(name: str, lines: list[str]) -> None:
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def fig1() -> None:
    w, h = 2200, 1400
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 70, ["图1"], klass="title"))

    s.extend(group_label(120, 190, "输入"))
    s.extend(rounded_box(120, 225, 280, 110, ["用户请求"], klass="small", dashed=True, rx=55))

    s.extend(group_label(1260, 130, "语义输出"))
    s.extend(rounded_box(1760, 150, 290, 110, ["最终主能力地址"], klass="small", dashed=True, rx=55))
    s.extend(rounded_box(1760, 300, 290, 110, ["最终相关能力地址"], klass="small", dashed=True, rx=55))

    s.extend(group_label(135, 435, "语义候选"))
    s.extend(rounded_box(120, 470, 360, 130, ["语义能力地址候选集合"], klass="small", dashed=True, rx=65))

    s.extend(group_label(650, 120, "核心路由层"))
    s.extend(rounded_box(560, 150, 1030, 300, [], klass="label", rx=28))
    s.extend(rounded_box(660, 235, 250, 72, ["候选召回"], klass="tiny", rx=36))
    s.extend(rounded_box(940, 235, 250, 72, ["快路径裁决"], klass="tiny", rx=36))
    s.extend(rounded_box(765, 330, 500, 72, ["慢路径共识与覆盖控制"], klass="tiny", rx=36))

    s.extend(arrow(400, 280, 560, 280))
    s.extend(arrow(480, 535, 760, 395))
    s.extend(arrow(1590, 235, 1760, 205))
    s.extend(arrow(1590, 345, 1760, 355))

    s.extend(group_label(120, 665, "实例执行层"))
    s.extend(rounded_box(120, 700, 310, 250, ["智能体注册快照"], klass="small", rx=24))
    s.extend(rounded_box(165, 770, 220, 54, ["注册信息"], klass="tiny", rx=16))
    s.extend(rounded_box(165, 846, 220, 54, ["过滤条件"], klass="tiny", rx=16))
    s.extend(rounded_box(165, 922, 220, 54, ["排序依据"], klass="tiny", rx=16))

    s.extend(group_label(770, 665, "执行实例确定"))
    s.extend(rounded_box(700, 700, 760, 250, [], klass="small", rx=26))
    s.extend(rounded_box(790, 780, 260, 66, ["精确匹配过滤"], klass="tiny", rx=18))
    s.extend(rounded_box(1100, 780, 260, 66, ["实例排序"], klass="tiny", rx=18))
    s.extend(rounded_box(860, 875, 440, 62, ["依据匹配度、健康度与公平因子"], klass="tiny", rx=16))
    s.extend(arrow(430, 825, 700, 825))
    s.extend(arrow(1200, 450, 1200, 700))

    s.extend(group_label(1770, 665, "最终输出"))
    s.extend(rounded_box(1760, 720, 290, 170, ["目标智能体实例地址", "调用端点"], klass="small", dashed=True, rx=70))
    s.extend(arrow(1460, 825, 1760, 805))

    s.extend(group_label(560, 1060, "总体处理链"))
    flow_y = 1100
    xs = [120, 470, 820, 1170, 1520, 1870]
    labels = [
        ["S101", "接收请求"],
        ["S102", "候选召回"],
        ["S103", "快路径裁决"],
        ["S104", "慢路径共识", "与覆盖控制"],
        ["S105", "实例确定"],
        ["S106", "输出结果"],
    ]
    widths = [260, 260, 260, 300, 260, 210]
    for i, (x, lines, width) in enumerate(zip(xs, labels, widths)):
        s.extend(rounded_box(x, flow_y, width, 120, lines, klass="tiny", rx=22))
        if i < len(xs) - 1:
            s.extend(arrow(x + width, flow_y + 60, xs[i + 1], flow_y + 60))

    s.extend(svg_footer())
    write_svg("图1_总体流程示意图.svg", s)


def fig3() -> None:
    w, h = 2200, 1400
    s = svg_header(w, h)
    s.extend(text_lines(w / 2, 70, ["图3"], klass="title"))

    s.extend(group_label(130, 185, "输入链路"))
    s.extend(rounded_box(120, 220, 280, 96, ["快路径裁决结果"], klass="tiny", dashed=True, rx=48))
    s.extend(arrow(400, 268, 520, 268))
    s.extend(rounded_box(520, 220, 310, 96, ["语义交接信息"], klass="tiny", dashed=True, rx=48))
    s.extend(arrow(830, 268, 970, 268))
    s.extend(rounded_box(970, 190, 430, 132, ["候选视图构造"], klass="small", rx=66))

    s.extend(group_label(120, 460, "职责角色层"))
    s.extend(rounded_box(120, 500, 420, 132, ["领域专家角色"], klass="small", dashed=True, rx=66))
    s.extend(rounded_box(620, 500, 420, 132, ["治理风险角色"], klass="small", dashed=True, rx=66))
    s.extend(rounded_box(1120, 500, 420, 132, ["层级解析角色"], klass="small", dashed=True, rx=66))
    s.extend(rounded_box(1620, 500, 420, 132, ["用户偏好角色"], klass="small", dashed=True, rx=66))

    s.extend(rounded_box(240, 535, 180, 58, ["语义匹配"], klass="tiny", rx=14))
    s.extend(rounded_box(740, 535, 180, 58, ["风险约束"], klass="tiny", rx=14))
    s.extend(rounded_box(1240, 535, 180, 58, ["层级冲突"], klass="tiny", rx=14))
    s.extend(rounded_box(1740, 535, 180, 58, ["偏好恢复"], klass="tiny", rx=14))

    s.extend(polyline([(1185, 322), (1185, 420), (330, 420), (330, 500)], arrow_end=True))
    s.extend(polyline([(1185, 322), (1185, 440), (830, 440), (830, 500)], arrow_end=True))
    s.extend(polyline([(1185, 322), (1185, 500), (1330, 500)], arrow_end=True))
    s.extend(polyline([(1185, 322), (1185, 440), (1830, 440), (1830, 500)], arrow_end=True))

    s.extend(group_label(790, 740, "聚合与控制"))
    s.extend(rounded_box(700, 780, 820, 180, ["角色提案和角色信号聚合"], klass="label", rx=24))
    s.extend(rounded_box(870, 835, 480, 62, ["聚合候选支持与阻断信号"], klass="tiny", rx=16))
    s.extend(rounded_box(1670, 805, 240, 130, ["覆盖控制"], klass="small", rx=20))
    s.extend(rounded_box(1700, 848, 180, 52, ["覆盖授权判断"], klass="tiny", rx=14))
    s.extend(arrow(1520, 870, 1670, 870))

    s.extend(arrow(330, 632, 880, 780))
    s.extend(arrow(830, 632, 1040, 780))
    s.extend(arrow(1330, 632, 1180, 780))
    s.extend(arrow(1830, 632, 1340, 780))

    s.extend(group_label(360, 1120, "输出结果"))
    s.extend(rounded_box(340, 1160, 420, 110, ["最终主能力地址"], klass="small", rx=55))
    s.extend(rounded_box(940, 1160, 420, 110, ["最终相关能力地址"], klass="small", rx=55))
    s.extend(arrow(1790, 935, 560, 1160))
    s.extend(arrow(1790, 935, 1160, 1160))

    s.extend(svg_footer())
    write_svg("图3_异质共识与覆盖控制结构示意图.svg", s)


def copy_remaining() -> None:
    for name in [
        "图2_两层地址关系示意图.svg",
        "图4_实例过滤与排序过程示意图.svg",
        "图5_结构化决策轨迹数据组织示意图.svg",
        "README.md",
    ]:
        shutil.copy2(SRC / name, OUT / name)


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
    copy_remaining()
    fig1()
    fig3()
    build_pdfs()


if __name__ == "__main__":
    main()
