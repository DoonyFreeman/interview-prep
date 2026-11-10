#!/usr/bin/env python3
"""Bundle the non-Python sheets in catalog order without duplicating RAG pages."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from build_rag_cheatsheets import ASSET_DIR, SHEETS as RAG_SHEETS, bundle_pdf

SHEETS = (
    ('team-processes', 'Процессы в команде', 1),
    ('llm-basics', 'Основы LLM', 1),
    ('agents', 'LLM-агенты', 1),
    ('langchain-tools', 'LangChain и tool calling', 2),
    ('langgraph-agents', 'Агенты и LangGraph', 2),
    ('ml-metrics', 'Метрики ML, кривые и регрессия', 3),
    ('rag', 'RAG: поиск и контекст', 1),
    *((slug, title, 2) for slug, title in RAG_SHEETS),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    filename = 'cheatsheets-all.pdf'
    with tempfile.TemporaryDirectory(dir=args.output_dir) as folder:
        staged = Path(folder) / filename
        bundle_pdf(
            [(ASSET_DIR / f'{slug}.pdf', title, pages) for slug, title, pages in SHEETS],
            staged,
            title='Шпаргалки InterviewPrep',
        )
        staged.replace(args.output_dir / filename)
    print(f'{filename}: {len(SHEETS)} sheets, {sum(pages for _, _, pages in SHEETS)} pages')


if __name__ == '__main__':
    main()
