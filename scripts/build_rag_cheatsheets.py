#!/usr/bin/env python3
"""Offline RAG PDF authoring; normal app builds use the checked-in assets.

Requires reportlab, pypdf and the same local fonts as build_cheatsheets.py.
Each Markdown sheet must contain six H2 sections; overflow is an error.
"""
from __future__ import annotations

import argparse
import html
import re
import tempfile
import unicodedata
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from build_cheatsheets import BORDER, INK, MUTED, PURPLE, ROOT, register_fonts

SHEETS = (
    ('rag-documents-embeddings', 'RAG: документы и эмбеддинги'),
    ('rag-search-indexes', 'RAG: поиск и индексы'),
    ('rag-evaluation', 'RAG: оценка и диагностика'),
)
SOURCE_DIR = ROOT / 'frontend/src/content/cheatsheets'
ASSET_DIR = ROOT / 'frontend/public/cheatsheets'


def glyph_text(text: str, font: str = 'Body') -> str:
    """Keep selectable Unicode, choosing a font that actually has every glyph."""
    text = unicodedata.normalize('NFC', text)
    text = text.replace('—', '-').replace('–', '-').replace('\u2011', '-')
    runs: list[tuple[str, str]] = []
    for char in text:
        selected = next((name for name in (font, 'Math', 'MathExtra')
                         if ord(char) in pdfmetrics.getFont(name).face.charToGlyph), None)
        if selected is None:
            raise ValueError(f'No authoring font supports U+{ord(char):04X} {char!r}')
        if runs and runs[-1][0] == selected:
            runs[-1] = (selected, runs[-1][1] + char)
        else:
            runs.append((selected, char))
    return ''.join(f'<font name="{name}">{html.escape(value)}</font>' for name, value in runs)


def markup(text: str, font: str = 'Body') -> str:
    # Links retain their readable label; printable sheets contain no annotations.
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    parts = re.split(r'(\*\*.+?\*\*|`[^`]+`)', text)
    return ''.join(glyph_text(part[2:-2], 'BodyBold') if part.startswith('**')
                   else glyph_text(part[1:-1], 'Mono') if part.startswith('`')
                   else glyph_text(part, font) for part in parts)


def markdown_blocks(body: str, width: float):
    style = ParagraphStyle('rag-body', fontName='Body', fontSize=8.5,
                           leading=10.6, textColor=INK)
    cellstyle = ParagraphStyle('rag-cell', parent=style, leading=10.2)
    for chunk in re.split(r'\n\s*\n', body.strip()):
        if chunk.startswith('|'):
            rows = [[cell.strip() for cell in line.strip().strip('|').split('|')]
                    for line in chunk.splitlines()]
            rows = [row for row in rows if not all(re.fullmatch(r'[:\- ]+', cell) for cell in row)]
            count = len(rows[0])
            if count < 2 or any(len(row) != count for row in rows):
                raise ValueError('Invalid Markdown table')
            fractions = {2: [.43, .57], 3: [.25, .36, .39], 4: [.25] * 4}.get(count)
            if fractions is None:
                raise ValueError('RAG tables support two to four columns')
            table = Table([[Paragraph(markup(cell), cellstyle) for cell in row] for row in rows],
                          colWidths=[width * fraction for fraction in fractions], hAlign='LEFT')
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0edf9')),
                ('LINEBELOW', (0, 0), (-1, -1), .3, BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            yield table
        else:
            yield Paragraph(markup(chunk.replace('\n', ' ')), style)


def sheet_pdf(source: Path, destination: Path, title: str) -> None:
    text = source.read_text(encoding='utf-8')
    sections = re.findall(r'^## ([^\n]+)\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if len(sections) != 6:
        raise ValueError(f'{source.name}: expected six H2 sections, got {len(sections)}')
    w, h = landscape(A4)
    c = canvas.Canvas(str(destination), pagesize=(w, h), invariant=1)
    c.setTitle(title)
    c.setAuthor('')
    c.setCreator('InterviewPrep')
    margin, gap, bottom, top = 20, 10, 34, h - 60
    cw = (w - 2 * margin - 2 * gap) / 3
    ch = top - bottom
    heading_style = ParagraphStyle('rag-heading', fontName='Heading', fontSize=10.4,
                                   leading=12.2, textColor=INK)
    for page in range(2):
        c.setFillColor(MUTED)
        c.setFont('Mono', 7)
        c.drawString(margin, h - 20, f'ШПАРГАЛКА К СОБЕСЕДОВАНИЮ · ЛИСТ {page + 1} ИЗ 2')
        c.setFillColor(INK)
        c.setFont('Heading', 20)
        c.drawString(margin, h - 43, title)
        for col, accent in enumerate(('#eee9fb', '#e2f2ec', '#fff2cd')):
            i = page * 3 + col
            heading, body = sections[i]
            x = margin + col * (cw + gap)
            heading_p = Paragraph(markup(heading, 'Heading'), heading_style)
            _, heading_h = heading_p.wrap(cw - 32, ch)
            banner_h = max(29, heading_h + 14)
            c.setStrokeColor(BORDER)
            c.setLineWidth(.65)
            c.roundRect(x, bottom, cw, ch, 5, stroke=1, fill=0)
            c.setFillColor(colors.HexColor(accent))
            c.roundRect(x + 1, top - banner_h, cw - 2, banner_h - 1, 4, stroke=0, fill=1)
            c.setFillColor(PURPLE)
            c.setFont('Mono', 7)
            c.drawString(x + 7, top - 18, f'{i + 1:02}')
            heading_p.drawOn(c, x + 24, top - 7 - heading_h)
            cursor = top - banner_h - 8
            for flowable in markdown_blocks(body, cw - 14):
                _, height = flowable.wrap(cw - 14, ch)
                if cursor - height < bottom + 6:
                    raise ValueError(f'{source.name} section {i + 1} overflows by '
                                     f'{bottom + 6 - cursor + height:.1f}pt; revise content')
                flowable.drawOn(c, x + 7, cursor - height)
                cursor -= height + 5
        c.setFillColor(MUTED)
        c.setFont('Body', 7)
        c.drawString(margin, 17, 'RAG: от исходного документа до проверяемого ответа.')
        c.drawRightString(w - margin, 17, f'Лист {page + 1} из 2 · InterviewPrep')
        c.showPage()
    c.save()


def bundle_pdf(paths: list[tuple[Path, str]], destination: Path) -> None:
    writer = PdfWriter()
    for path, title in paths:
        reader = PdfReader(path)
        expected = 1 if path.name == 'rag.pdf' else 2
        if len(reader.pages) != expected:
            raise ValueError(f'{path.name}: expected {expected} pages, got {len(reader.pages)}')
        first = len(writer.pages)
        for page in reader.pages:
            added = writer.add_page(page)
            # No source document actions, scripts or URI annotations survive.
            for key in ('/Annots', '/AA', '/A'):
                added.pop(NameObject(key), None)
        writer.add_outline_item(title, first)
    writer.add_metadata({'/Title': 'RAG: полный комплект шпаргалок', '/Author': '',
                         '/Creator': 'InterviewPrep', '/Producer': 'InterviewPrep'})
    with destination.open('wb') as stream:
        writer.write(stream)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir', type=Path, default=Path('/System/Library/Fonts/Supplemental'))
    parser.add_argument('--output-dir', type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    try:
        register_fonts(args.font_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='interview-prep-rag-') as folder:
            staging = Path(folder)
            for slug, title in SHEETS:
                sheet_pdf(SOURCE_DIR / f'{slug}.md', staging / f'{slug}.pdf', title)
            bundle_pdf([(ASSET_DIR / 'rag.pdf', 'RAG: обзор'),
                        *((staging / f'{slug}.pdf', title) for slug, title in SHEETS)],
                       staging / 'rag-all.pdf')
            for path in sorted(staging.glob('*.pdf')):
                (args.output_dir / path.name).write_bytes(path.read_bytes())
                print(f'{path.name}: {len(PdfReader(path).pages)} pages')
    except (ValueError, OSError) as error:
        parser.exit(1, f'rag-cheatsheets: {error}\n')


if __name__ == '__main__':
    main()
