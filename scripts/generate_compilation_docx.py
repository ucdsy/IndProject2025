from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


INPUT_MD = Path("output/doc/项目成果汇编_20260416.md")
OUTPUT_DOCX = Path("output/doc/项目成果汇编_20260416.docx")


def apply_font(run, size: int, east_asia: str, bold: bool = False) -> None:
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.bold = bold
    run._element.rPr.rFonts.set(qn("w:eastAsia"), east_asia)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.6)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def add_title(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(text)
    apply_font(run, 16, "黑体", bold=True)


def add_heading(doc: Document, text: str, level: int) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8 if level == 2 else 6)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    if level == 2:
        apply_font(run, 14, "黑体", bold=True)
    elif level == 3:
        apply_font(run, 12, "黑体", bold=True)
    else:
        apply_font(run, 12, "楷体_GB2312", bold=True)


def add_body_paragraph(doc: Document, text: str, indent: bool = True) -> None:
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.84)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    apply_font(run, 12, "宋体")


def add_tag_paragraph(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5
    run = p.add_run(text)
    apply_font(run, 12, "宋体")


def build_doc(lines: list[str]) -> Document:
    doc = Document()
    configure_document(doc)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            add_title(doc, line[2:].strip())
            continue
        if line.startswith("## "):
            add_heading(doc, line[3:].strip(), level=2)
            continue
        if line.startswith("### "):
            add_heading(doc, line[4:].strip(), level=3)
            continue
        if line.startswith("#### "):
            add_heading(doc, line[5:].strip(), level=4)
            continue
        if line.startswith("项目编号：") or line.startswith("研究处所：") or line.startswith("项目负责人：") or line.startswith("项目参与人："):
            add_tag_paragraph(doc, line)
            continue
        add_body_paragraph(doc, line, indent=True)

    return doc


def main() -> None:
    text = INPUT_MD.read_text(encoding="utf-8")
    doc = build_doc(text.splitlines())
    OUTPUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT_DOCX)
    print(OUTPUT_DOCX)


if __name__ == "__main__":
    main()
