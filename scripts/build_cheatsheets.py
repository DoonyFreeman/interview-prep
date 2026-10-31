#!/usr/bin/env python3
"""Optional local PDF authoring; application builds use the checked-in PDFs.

Requires reportlab and pypdf. Pass original PDF paths explicitly to regenerate
standalone sheets; without them only ml-metrics.pdf is generated from Markdown.
Fonts default to macOS Supplemental; use --font-dir on another authoring host.
No source PDFs or system fonts are copied into the repository.
"""
from __future__ import annotations

import argparse
import html
import io
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ByteStringObject, NameObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
TITLES = {
    'concurrency': 'Конкурентность, потоки и asyncio',
    'team-processes': 'Процессы в IT-команде',
    'llm-basics': 'LLM: как устроены и как с ними работать',
    'rag': 'RAG: поиск по своим документам',
    'agents': 'Tool calling и агенты',
    'ml-metrics': 'Метрики ML: классификация и регрессия',
}
INK = colors.HexColor('#191d29')
MUTED = colors.HexColor('#626a7d')
PURPLE = colors.HexColor('#6a4bd6')
BORDER = colors.HexColor('#d3d7e0')


def register_fonts(folder: Path) -> None:
    for name, filename, index in [
        ('Body', 'PTSans.ttc', 0), ('Heading', 'PTSerif.ttc', 3),
        ('RegularSerif', 'PTSerif.ttc', 0), ('Mono', 'PTMono.ttc', 1),
        ('Math', 'Arial.ttf', 0), ('MathExtra', 'Arial Unicode.ttf', 0),
    ]:
        path = folder / filename
        if not path.is_file():
            raise ValueError(f'Authoring font missing: {path}; supply --font-dir')
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=index))
    # Use the genuine bold face rather than synthesizing bold text.
    pdfmetrics.registerFont(TTFont('BodyBold', str(folder / 'PTSans.ttc'), subfontIndex=4))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyBold', italic='Body', boldItalic='BodyBold')


def write_page(page, destination: Path, title: str) -> None:
    # Source annotations are unnecessary for printable standalone sheets. Drop
    # them all so private local URI links cannot survive the split.
    page.pop(NameObject('/Annots'), None)
    writer = PdfWriter()
    writer.add_page(page)
    writer.add_metadata({'/Title': title, '/Creator': 'InterviewPrep', '/Producer': 'InterviewPrep'})
    with destination.open('wb') as stream:
        writer.write(stream)


def unicode_map(font) -> dict[int, str]:
    """Read the simple two-byte ToUnicode maps used by the supplied originals."""
    stream = font.get_object().get('/ToUnicode')
    if stream is None:
        return {}
    source = stream.get_object().get_data().decode('ascii')
    mapping = {}
    for section in re.findall(r'beginbfchar(.*?)endbfchar', source, re.S):
        for code, value in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', section):
            mapping[int(code, 16)] = bytes.fromhex(value).decode('utf-16-be')
    for section in re.findall(r'beginbfrange(.*?)endbfrange', source, re.S):
        for first, last, target in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', section):
            for code in range(int(first, 16), int(last, 16) + 1):
                mapping[code] = chr(int(target, 16) + code - int(first, 16))
    return mapping


def remove_unverified_delivery(block, maps):
    """Delete unsupported delivery text and its glyph advances, never paint over it."""
    font, glyphs = None, []
    for index, (operands, operator) in enumerate(block):
        if operator == b'Tf':
            font = operands[0]
        elif operator == b'Tj' and font in maps:
            value = operands[0]
            raw = value if isinstance(value, bytes) else value.original_bytes
            decoded = ''.join(maps[font].get(int.from_bytes(raw[i:i + 2], 'big'), '?') for i in range(0, len(raw), 2))
            glyphs.append((index, raw, decoded))
    text = ''.join(decoded for _, _, decoded in glyphs)
    phrase = ', будет завтра'
    start = text.find(phrase)
    if start < 0:
        return block, 0
    end, offset, result = start + len(phrase), 0, list(block)
    for index, raw, decoded in glyphs:
        lo, hi = max(0, start - offset), min(len(decoded), end - offset)
        if lo < hi:
            # Original fonts encode every character with one two-byte CID.
            if len(raw) != 2 * len(decoded):
                raise ValueError('Delivery correction: unsupported multi-character glyph')
            kept = raw[:lo * 2] + raw[hi * 2:]
            result[index] = ([ByteStringObject(kept)], b'Tj') if kept else None
            # Each original glyph has an explicit advance after it. Remove the
            # deleted glyph's advance too, closing the gap before punctuation.
            if not kept and index + 1 < len(block) and block[index + 1][1] == b'Td':
                result[index + 1] = None
        offset += len(decoded)
    return [operation for operation in result if operation is not None], 1


def standalone(source: Path, output: Path, slugs: list[str]) -> None:
    reader = PdfReader(source)
    if len(reader.pages) != len(slugs):
        raise ValueError(f'{source.name}: expected {len(slugs)} pages, got {len(reader.pages)}')
    for index, slug in enumerate(slugs):
        holder = PdfWriter()
        page = holder.add_page(reader.pages[index])
        if float(page.mediabox.width) < float(page.mediabox.height):
            raise ValueError(f'{source.name}: expected landscape page {index + 1}')
        if slug == 'concurrency':
            write_page(page, output / f'{slug}.pdf', TITLES[slug])
            continue
        # Chromium's source pages retain document-space text matrices. Remove
        # complete text objects for the header/folio; all body paths and text
        # objects remain vector content. Replace the LLM cross-reference footer.
        stream = page.get_contents()
        result, block = [], None
        removed = 0
        corrections = 0
        maps = {name: unicode_map(font) for name, font in page['/Resources']['/Font'].items()}
        for operands, operator in stream.operations:
            if operator == b'BT':
                block = []
            if block is not None:
                block.append((operands, operator))
                if operator == b'ET':
                    matrices = [o for o, op in block if op == b'Tm']
                    remove = any(
                        (abs(float(m[5]) - (27 + 794 * index)) < .1)
                        or (abs(float(m[4]) - 26.453125) < .1 and abs(float(m[5]) - (52 + 794 * index)) < .1)
                        or (slug == 'llm-basics' and float(m[5]) >= 1550)
                        for m in matrices
                    )
                    if remove:
                        removed += 1
                    else:
                        corrected, count = remove_unverified_delivery(block, maps)
                        corrections += count
                        result.extend(corrected)
                    block = None
            else:
                result.append((operands, operator))
        if slug in ('llm-basics', 'agents') and corrections != 1:
            raise ValueError(f'{source.name}: expected one delivery correction on page {index + 1}, got {corrections}')
        if removed < 2:
            raise ValueError(f'{source.name}: header structure changed on page {index + 1}')
        stream.operations = result
        page.replace_contents(stream)
        overlay = io.BytesIO()
        c = canvas.Canvas(overlay, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
        c.setFillColor(MUTED)
        c.setFont('Mono', 5.7)
        c.drawString(44.17, 574.71, 'ШПАРГАЛКА К СОБЕСЕДОВАНИЮ · ЛИСТ 1 ИЗ 1')
        if slug == 'llm-basics':
            c.setFillColor(colors.white)
            c.rect(19, 10, 806, 14, fill=1, stroke=0)
            c.setFillColor(PURPLE)
            c.setFont('BodyBold', 5.9)
            c.drawString(19.84, 15.2, 'ВОПРОСЫ МЕНТОРА >')
            c.setFillColor(INK)
            c.setFont('Body', 6.2)
            c.drawString(101.8, 15.2, 'Токен и окно 01 · Галлюцинации 02 · temperature 03 · Роли 04 · Few-shot 05 · JSON 07 · Стоимость 08 · Ассистент: «Tool calling и агенты», §04')
        c.save()
        overlay.seek(0)
        page.merge_page(PdfReader(overlay).pages[0])
        write_page(page, output / f'{slug}.pdf', TITLES[slug])


def markup(text: str) -> str:
    text = html.escape(text.replace('—', '-').replace('–', '-').replace('\u2011', '-'))
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # PT Sans lacks Greek sigma and combining/subscript Latin math glyphs.
    # Embed a Unicode fallback for these individual glyphs, retaining real text.
    for char in 'Σᵢŷȳ→↓':
        text = text.replace(char, f'<font name="Math">{char}</font>')
    for char in '₋₁':
        text = text.replace(char, f'<font name="MathExtra">{char}</font>')
    return text


def markdown_blocks(body: str, width: float):
    style = ParagraphStyle('body', fontName='Body', fontSize=8.5, leading=10.6, textColor=INK, spaceAfter=3)
    cellstyle = ParagraphStyle('cell', parent=style, fontSize=8.0, leading=9.5)
    chunks = re.split(r'\n\s*\n', body.strip())
    for chunk in chunks:
        if chunk.startswith('|'):
            rows = [[cell.strip() for cell in line.strip().strip('|').split('|')] for line in chunk.splitlines()]
            rows = [row for row in rows if not all(re.fullmatch(r'[:\- ]+', cell) for cell in row)]
            # Compact, semantic table widths avoid narrow formula columns.
            fractions = {2: [.56, .44], 3: [.22, .39, .39], 4: [.22, .35, .16, .27], 5: [.19, .25, .20, .19, .17]}[len(rows[0])]
            table = Table([[Paragraph(markup(cell), cellstyle) for cell in row] for row in rows], colWidths=[width * f for f in fractions], hAlign='LEFT')
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0edf9')),
                ('LINEBELOW', (0, 0), (-1, -1), .3, BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            yield table
        else:
            yield Paragraph(markup(chunk.replace('\n', ' ')), style)


def ml_pdf(markdown: Path, destination: Path) -> None:
    text = markdown.read_text(encoding='utf-8')
    sections = re.findall(r'^## ([^\n]+)\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if len(sections) != 9:
        raise ValueError(f'{markdown}: expected exactly nine H2 sections, got {len(sections)}')
    w, h = landscape(A4)
    c = canvas.Canvas(str(destination), pagesize=(w, h), invariant=1)
    c.setTitle(TITLES['ml-metrics'])
    c.setAuthor('')
    c.setCreator('InterviewPrep')
    gap, margin, top, bottom = 10, 20, h - 60, 34
    cw = (w - margin * 2 - gap * 2) / 3
    ch = top - bottom
    accents = ['#eee9fb', '#e2f2ec', '#fff2cd']
    for page in range(3):
        c.setFillColor(MUTED)
        c.setFont('Mono', 7)
        c.drawString(20, h - 20, f'ШПАРГАЛКА К СОБЕСЕДОВАНИЮ · ЛИСТ {page + 1} ИЗ 3')
        c.setFillColor(INK)
        c.setFont('Heading', 20)
        c.drawString(20, h - 43, 'Метрики ML: смысл, формулы и расчёт')
        for col in range(3):
            i = page * 3 + col
            title, body = sections[i]
            x, y = margin + col * (cw + gap), bottom
            c.setStrokeColor(BORDER)
            c.setLineWidth(.65)
            c.roundRect(x, y, cw, ch, 5, stroke=1, fill=0)
            c.setFillColor(colors.HexColor(accents[col]))
            c.roundRect(x + 1, y + ch - 29, cw - 2, 28, 4, stroke=0, fill=1)
            c.setFillColor(PURPLE)
            c.setFont('Mono', 7)
            c.drawString(x + 7, y + ch - 18, f'{i + 1:02}')
            c.setFillColor(INK)
            c.setFont('Heading', 10.4)
            c.drawString(x + 24, y + ch - 18, title)
            cursor = y + ch - 37
            for flowable in markdown_blocks(body, cw - 14):
                _, height = flowable.wrap(cw - 14, ch)
                if cursor - height < y + 6:
                    raise ValueError(f'ML section {i + 1} overflows by {y + 6 - cursor + height:.1f}pt; revise layout, not content')
                flowable.drawOn(c, x + 7, cursor - height)
                cursor -= height + 5
        c.setFillColor(MUTED)
        c.setFont('Body', 7)
        c.drawString(20, 17, 'Сначала смысл метрики, затем формула, подстановка чисел и вывод.')
        c.drawRightString(w - 20, 17, 'Подбор: validation · Финальная проверка: test')
        c.showPage()
    c.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concurrency-source', type=Path)
    parser.add_argument('--bundle-source', type=Path)
    parser.add_argument('--font-dir', type=Path, default=Path('/System/Library/Fonts/Supplemental'))
    parser.add_argument('--ml-source', type=Path, default=ROOT / 'frontend/src/content/cheatsheets/ml-metrics.md')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'frontend/public/cheatsheets')
    args = parser.parse_args()
    try:
        register_fonts(args.font_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for source in (args.concurrency_source, args.bundle_source, args.ml_source):
            if source is not None and not source.is_file():
                raise ValueError(f'Source file missing: {source}')
        if args.concurrency_source:
            standalone(args.concurrency_source, args.output_dir, ['concurrency'])
        if args.bundle_source:
            standalone(args.bundle_source, args.output_dir, ['team-processes', 'llm-basics', 'rag', 'agents'])
        ml_pdf(args.ml_source, args.output_dir / 'ml-metrics.pdf')
    except (ValueError, OSError) as error:
        parser.exit(1, f'cheatsheets: {error}\n')


if __name__ == '__main__':
    main()
