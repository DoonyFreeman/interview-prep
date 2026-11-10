#!/usr/bin/env python3
"""Rebuild the two LangChain and LangGraph PDF sheets from their Markdown."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from build_cheatsheets import register_fonts
from build_rag_cheatsheets import ASSET_DIR, SOURCE_DIR, sheet_pdf

SHEETS = (
    ('langchain-tools', 'LangChain и tool calling', 'Дни 1–2 · От промпта до результата инструмента'),
    ('langgraph-agents', 'Агенты и LangGraph', 'Дни 3–5 · От первого шага до возобновления графа'),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir', type=Path, default=Path('/System/Library/Fonts/Supplemental'))
    parser.add_argument('--output-dir', type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    register_fonts(args.font_dir)
    with tempfile.TemporaryDirectory(prefix='interview-prep-agent-sheets-') as folder:
        staging = Path(folder)
        for slug, title, footer in SHEETS:
            sheet_pdf(SOURCE_DIR / f'{slug}.md', staging / f'{slug}.pdf', title,
                      footer=footer, font_size=10.5)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(staging.glob('*.pdf')):
            (args.output_dir / path.name).write_bytes(path.read_bytes())
            print(f'{path.name}: 2 pages')


if __name__ == '__main__':
    main()
