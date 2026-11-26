#!/usr/bin/env python3
"""Render an owner-only resume PDF from its private sections JSON, offline."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from build_cheatsheets import INK, MUTED, register_fonts
from build_rag_cheatsheets import glyph_text

BLUE = HexColor("#235bc8")
TEAL = HexColor("#0b6d60")
BORDER = HexColor("#d6dfed")
WIDTH, HEIGHT = landscape(A4)
MARGIN = 30


def paragraph(page, value, x, top, width, *, font="Body", size=11, color=INK, align=0):
    style = ParagraphStyle(
        "resume", fontName=font, fontSize=size, leading=size * 1.18,
        textColor=color, alignment=align, splitLongWords=False,
    )
    part = Paragraph(glyph_text(value, font), style)
    _, height = part.wrap(width, HEIGHT)
    part.drawOn(page, x, top - height)
    return top - height


def arrow(page, x, end, y, color):
    page.setStrokeColor(color)
    page.setLineWidth(1.25)
    page.line(x, y, end, y)
    page.line(end - 4, y + 2.8, end, y)
    page.line(end - 4, y - 2.8, end, y)


def flow_row(page, flow, top, *, branch):
    color = TEAL if branch else BLUE
    wash = HexColor("#e9f5f1" if branch else "#eaf1ff")
    top = paragraph(page, flow["title"], MARGIN, top, WIDTH - 2*MARGIN,
                    font="BodyBold", size=11, color=color) - 7
    nodes = flow["nodes"]
    gap = 66 if len(nodes) < 5 else 49
    content_width = WIDTH - 2 * MARGIN
    node_width = (content_width - gap * (len(nodes) - 1)) / len(nodes)
    height = 74 if len(nodes) >= 5 else 59
    for index, node in enumerate(nodes):
        x = MARGIN + index * (node_width + gap)
        page.setFillColor(wash)
        page.setStrokeColor(BORDER)
        page.roundRect(x, top - height, node_width, height, 6, stroke=1, fill=1)
        bottom = paragraph(page, node["title"], x + 6, top - 8, node_width - 12,
                           font="BodyBold", size=10.4, color=color, align=1)
        bottom = paragraph(page, node["detail"], x + 5, bottom - 4, node_width - 10,
                           size=9.2, align=1)
        if bottom < top - height + 3:
            raise ValueError(f"Flow node overflows: {node['title']}")
        if index < len(nodes) - 1:
            start = x + node_width
            arrow(page, start + 4, start + gap - 4, top - 37, color)
            paragraph(page, flow["links"][index], start + 2, top - 7, gap - 4,
                      size=7.6, color=MUTED, align=1)
    return top - height - 13


def text_block(page, title, text, x, top, width, color):
    page.setFillColor(color)
    page.rect(x, top - 12, 2.5, 11, stroke=0, fill=1)
    y = paragraph(page, title, x + 8, top, width - 8, font="BodyBold", size=11.1)
    return paragraph(page, text, x + 8, y - 2, width - 8, size=9.7) - 7


def render_sheet(page, section, index, total):
    page.setFillColor(white)
    page.rect(0, 0, WIDTH, HEIGHT, fill=1, stroke=0)
    top = HEIGHT - 24
    paragraph(page, f"{index:02}", MARGIN, top, 46, font="Heading", size=29, color=BLUE)
    heading_x = MARGIN + 53
    available = WIDTH - MARGIN - heading_x
    top = paragraph(page, f"МОЁ РЕЗЮМЕ   /   PYTHON BACKEND   /   ЛИСТ {index} ИЗ {total}",
                    heading_x, top, available, font="BodyBold", size=9, color=MUTED) - 3
    top = paragraph(page, section["title"], heading_x, top, available, font="Heading", size=25) - 8
    page.setStrokeColor(BORDER)
    page.line(MARGIN, top, WIDTH - MARGIN, top)
    top = paragraph(page, section["takeaway"], MARGIN, top - 9, WIDTH - 2*MARGIN,
                    font="BodyBold", size=12, color=BLUE) - 12
    for number, flow in enumerate(section["flows"]):
        top = flow_row(page, flow, top, branch=number > 0)

    gap = 19
    column_width = (WIDTH - 2 * MARGIN - 2 * gap) / 3
    columns = [MARGIN + col * (column_width + gap) for col in range(3)]
    bottoms = []
    panels = section["panels"]
    weights = [70 + len(panel["text"]) for panel in panels]
    split = min(range(1, len(panels)), key=lambda i: abs(sum(weights[:i]) - sum(weights[i:])), default=1)
    page.setStrokeColor(BORDER)
    for x in columns[1:]:
        page.line(x - gap / 2, top, x - gap / 2, 40)
    for x, panels in zip(columns, [section["panels"][:split], section["panels"][split:]]):
        y = top
        for panel in panels:
            y = text_block(page, panel["title"], panel["text"], x, y, column_width, BLUE)
        bottoms.append(y)
    x = columns[-1]
    y = paragraph(page, "На собеседовании", x, top, column_width,
                  font="Heading", size=14, color=TEAL) - 6
    for pair in section["questions"]:
        y = text_block(page, pair["question"], pair["answer"], x, y, column_width, TEAL)
    bottoms.append(y)
    if min(bottoms) < 34:
        raise ValueError(f"Page overflow: {section['title']} ({bottoms})")

    page.setStrokeColor(BORDER)
    page.line(MARGIN, 33, WIDTH - MARGIN, 33)
    paragraph(page, "Подготовка к Python Backend • Личный материал", MARGIN, 27, WIDTH/2, size=9, color=MUTED)
    paragraph(page, "Схемы и адреса запросов — учебные примеры", WIDTH/2, 27,
              WIDTH/2-MARGIN, size=9, color=MUTED, align=2)
    page.showPage()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private JSON array of resume sections")
    parser.add_argument("output", type=Path)
    parser.add_argument("--font-dir", type=Path, default=Path("/System/Library/Fonts/Supplemental"))
    args = parser.parse_args()
    register_fonts(args.font_dir)
    sections = json.loads(args.source.read_text())
    if not sections or any(not section.get("takeaway") or not section.get("flows") for section in sections):
        parser.error("The PDF requires a takeaway and labeled flows for every section")
    fd, name = tempfile.mkstemp(dir=args.output.parent, suffix=".pdf")
    os.close(fd)
    temporary = Path(name)
    try:
        page = Canvas(str(temporary), pagesize=(WIDTH, HEIGHT), pageCompression=1)
        page.setTitle("Моё резюме — Python Backend")
        for index, section in enumerate(sections, 1):
            render_sheet(page, section, index, len(sections))
        page.save()
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
