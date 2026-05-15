from __future__ import annotations

import shutil
import subprocess
from math import hypot
from pathlib import Path


SRC = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利高质量附图版_20260413")
OUT = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/doc/专利精修附图版_20260413")

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
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "  <defs>",
        "    <style>",
        "      .frame{fill:#fff;stroke:#000;stroke-width:4.8;vector-effect:non-scaling-stroke;}",
        "      .soft{fill:#fff;stroke:#000;stroke-width:4;vector-effect:non-scaling-stroke;}",
        "      .dash{fill:#fff;stroke:#000;stroke-width:4;stroke-dasharray:18 12;vector-effect:non-scaling-stroke;}",
        "      .line{fill:none;stroke:#000;stroke-width:4.2;stroke-linecap:square;stroke-linejoin:miter;vector-effect:non-scaling-stroke;}",
        f"      .title{{font-family:{FONT_TITLE};font-size:50px;font-weight:700;fill:#000;}}",
        f"      .group{{font-family:{FONT_TITLE};font-size:32px;font-weight:700;fill:#000;}}",
        f"      .label{{font-family:{FONT_TEXT};font-size:34px;font-weight:400;fill:#000;}}",
        f"      .small{{font-family:{FONT_TEXT};font-size:30px;font-weight:400;fill:#000;}}",
        f"      .tiny{{font-family:{FONT_TEXT};font-size:28px;font-weight:400;fill:#000;}}",
        f"      .micro{{font-family:{FONT_TEXT};font-size:24px;font-weight:400;fill:#000;}}",
        "    </style>",
        "  </defs>",
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
    ]


def svg_footer() -> list[str]:
    return ["</svg>"]


def title(label: str) -> list[str]:
    return [f'  <text x="{PAGE_W/2}" y="100" text-anchor="middle" class="title">{esc(label)}</text>']


def text_lines(x: float, y: float, lines: list[str], klass: str = "label", anchor: str = "middle", weight: str | None = None) -> list[str]:
    gap_map = {"label": 46, "small": 40, "tiny": 36, "micro": 30}
    line_gap = gap_map.get(klass, 40)
    start_y = y - ((len(lines) - 1) * line_gap) / 2
    extra = f' font-weight="{weight}"' if weight else ""
    return [
        f'  <text x="{x}" y="{start_y + i * line_gap}" text-anchor="{anchor}" class="{klass}"{extra}>{esc(line)}</text>'
        for i, line in enumerate(lines)
    ]


def rounded_box(x: float, y: float, w: float, h: float, lines: list[str], klass: str = "label", rx: int = 26, dashed: bool = False) -> list[str]:
    cls = "dash" if dashed else "soft"
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" class="{cls}"/>']
    out.extend(text_lines(x + w / 2, y + h / 2 + 4, lines, klass=klass))
    return out


def capsule(x: float, y: float, w: float, h: float, lines: list[str], klass: str = "label", dashed: bool = True) -> list[str]:
    rx = h / 2
    return rounded_box(x, y, w, h, lines, klass=klass, rx=int(rx), dashed=dashed)


def label_flag(x: float, y: float, text: str, w: float = 210) -> list[str]:
    out = [f'  <rect x="{x}" y="{y}" width="{w}" height="54" fill="#fff"/>']
    out.extend(text_lines(x + 18, y + 36, [text], klass="group", anchor="start"))
    return out


def line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="line"/>'


def arrow(x1: float, y1: float, x2: float, y2: float, head_len: int = 24, head_w: int = 16) -> list[str]:
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


def polyline(points: list[tuple[float, float]]) -> list[str]:
    if len(points) < 2:
        return []
    segs = [line(*points[i], *points[i + 1]) for i in range(len(points) - 1)]
    return segs


def poly_arrow(points: list[tuple[float, float]]) -> list[str]:
    if len(points) < 2:
        return []
    out = polyline(points[:-1])
    out.extend(arrow(*points[-2], *points[-1]))
    return out


def write_svg(name: str, lines: list[str]) -> None:
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def fig1() -> None:
    s = svg_header()
    s.extend(title("图1"))

    s.extend(label_flag(150, 185, "输入侧", w=120))
    s.extend(capsule(150, 245, 360, 120, ["用户请求"], klass="small"))
    s.extend(arrow(510, 305, 690, 305))

    s.extend(label_flag(740, 165, "核心路由层", w=180))
    s.extend(rounded_box(690, 210, 760, 190, ["受约束多阶段路由核心"], klass="label", rx=30))
    s.extend(capsule(800, 265, 240, 70, ["候选召回"], klass="tiny", dashed=False))
    s.extend(capsule(1060, 265, 250, 70, ["快路径裁决"], klass="tiny", dashed=False))
    s.extend(capsule(845, 345, 420, 70, ["慢路径共识与覆盖控制"], klass="tiny", dashed=False))

    s.extend(label_flag(1570, 185, "语义输出侧", w=180))
    s.extend(capsule(1520, 150, 380, 120, ["最终主能力地址"], klass="small"))
    s.extend(capsule(1520, 320, 380, 120, ["最终相关能力地址"], klass="small"))
    s.extend(arrow(1450, 255, 1520, 210))
    s.extend(arrow(1450, 355, 1520, 380))

    s.extend(label_flag(210, 650, "语义候选域", w=180))
    s.extend(capsule(150, 710, 500, 170, ["语义能力地址候选集合"], klass="small"))
    s.extend(arrow(980, 400, 500, 710))

    s.extend(label_flag(760, 610, "决策链路", w=150))
    s.extend(rounded_box(690, 680, 760, 1220, [" "], klass="small", rx=34))
    s.extend(rounded_box(810, 770, 520, 135, ["S101 接收用户请求"], klass="small"))
    s.extend(arrow(1070, 905, 1070, 1010))
    s.extend(rounded_box(650, 1010, 840, 160, ["S102 召回处理", "获得语义能力地址候选集合"], klass="small"))
    s.extend(arrow(1070, 1170, 1070, 1270))
    s.extend(rounded_box(760, 1270, 620, 135, ["S103 快路径裁决"], klass="small"))
    s.extend(arrow(1070, 1405, 1070, 1520))
    s.extend(capsule(760, 1520, 620, 150, ["S104 判断是否满足", "慢路径触发条件"], klass="small"))
    s.extend(text_lines(720, 1580, ["是"], klass="micro", weight="700"))
    s.extend(text_lines(1425, 1580, ["否"], klass="micro", weight="700"))
    s.extend(arrow(900, 1670, 900, 1780))
    s.extend(rounded_box(640, 1780, 520, 135, ["S105 异质共识处理"], klass="small"))
    s.extend(arrow(900, 1915, 900, 2020))
    s.extend(rounded_box(640, 2020, 520, 135, ["S106 覆盖控制步骤"], klass="small"))
    s.extend(poly_arrow([(1380, 1595), (1560, 1595), (1560, 2088), (1184, 2088)]))
    s.extend(arrow(1070, 2155, 1070, 2260))
    s.extend(rounded_box(560, 2260, 1020, 150, ["S107 筛选智能体实例地址候选集合"], klass="small"))
    s.extend(arrow(1070, 2410, 1070, 2520))
    s.extend(rounded_box(560, 2520, 1020, 135, ["S108 过滤和排序"], klass="small"))

    s.extend(label_flag(260, 2110, "实例执行层", w=180))
    s.extend(rounded_box(120, 2180, 350, 370, ["智能体注册快照", "", "地址精确匹配", "", "实例状态/端点/模式过滤"], klass="small", rx=26))
    s.extend(capsule(170, 2250, 250, 70, ["注册信息"], klass="tiny", dashed=False))
    s.extend(capsule(170, 2355, 250, 70, ["过滤条件"], klass="tiny", dashed=False))
    s.extend(capsule(170, 2460, 250, 70, ["排序依据"], klass="tiny", dashed=False))
    s.extend(arrow(470, 2365, 560, 2335))

    s.extend(label_flag(1640, 2185, "最终输出", w=150))
    s.extend(capsule(1600, 2245, 280, 320, ["目标智能体", "实例地址", "", "调用端点"], klass="small"))
    s.extend(arrow(1580, 2590, 1600, 2410))

    s.extend(svg_footer())
    write_svg("图1_总体流程示意图.svg", s)


def fig3() -> None:
    s = svg_header()
    s.extend(title("图3"))

    s.extend(label_flag(260, 210, "输入信息", w=150))
    s.extend(capsule(170, 280, 420, 130, ["快路径裁决结果"], klass="small"))
    s.extend(capsule(700, 280, 460, 130, ["语义交接信息"], klass="small"))
    s.extend(capsule(1290, 250, 520, 160, ["候选视图构造"], klass="small", dashed=False))
    s.extend(arrow(590, 345, 700, 345))
    s.extend(arrow(1160, 345, 1290, 330))

    s.extend(label_flag(170, 560, "职责角色层", w=180))
    s.extend(capsule(120, 670, 400, 170, ["领域专家角色"], klass="small"))
    s.extend(capsule(590, 670, 400, 170, ["治理风险角色"], klass="small"))
    s.extend(capsule(1060, 670, 400, 170, ["层级解析角色"], klass="small"))
    s.extend(capsule(1530, 670, 400, 170, ["用户偏好角色"], klass="small"))

    s.extend(poly_arrow([(1550, 410), (1550, 560), (320, 670)]))
    s.extend(poly_arrow([(1550, 410), (1550, 560), (790, 670)]))
    s.extend(poly_arrow([(1550, 410), (1550, 560), (1260, 670)]))
    s.extend(arrow(1550, 410, 1730, 670))

    s.extend(label_flag(720, 1130, "聚合与控制", w=180))
    s.extend(rounded_box(620, 1210, 760, 210, ["角色提案和角色信号聚合"], klass="label", rx=32))
    s.extend(capsule(770, 1275, 460, 70, ["聚合候选支持与阻断信号"], klass="tiny", dashed=False))

    s.extend(rounded_box(1535, 1220, 320, 190, ["覆盖控制单元"], klass="small", rx=28))
    s.extend(rounded_box(1580, 1275, 230, 80, ["覆盖授权判断"], klass="tiny", rx=18))
    s.extend(arrow(1380, 1315, 1535, 1315))

    s.extend(arrow(320, 840, 760, 1210))
    s.extend(arrow(790, 840, 980, 1210))
    s.extend(arrow(1260, 840, 1180, 1210))
    s.extend(arrow(1730, 840, 1220, 1210))

    s.extend(label_flag(450, 1760, "输出结果", w=150))
    s.extend(capsule(330, 1840, 460, 150, ["最终主能力地址"], klass="small", dashed=False))
    s.extend(capsule(980, 1840, 460, 150, ["最终相关能力地址"], klass="small", dashed=False))
    s.extend(arrow(1695, 1410, 560, 1840))
    s.extend(arrow(1695, 1410, 1210, 1840))

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
