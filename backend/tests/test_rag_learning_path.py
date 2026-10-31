"""Keep the RAG reading path's cross-lesson references and diagrams usable."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from app.config import get_settings
from app.content.loader import load_content


LESSONS = (
    "rag-documents-embeddings",
    "rag-search-indexes",
    "rag-evaluation",
)


def _lessons():
    bundle = load_content(get_settings().content_dir)
    return {(c.slug, l.slug): l for c in bundle.courses for l in c.lessons}


def _anchor(title: str) -> str:
    title = re.sub(r"[^\w\s-]", "", title.lower()).replace("_", "")
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", title.strip()))


def test_rag_concept_links_reach_real_lesson_sections():
    lessons = _lessons()
    for slug in LESSONS:
        lesson = lessons["llm", slug]
        links = re.findall(
            r'\[[^\]]+\]\(/courses/([^/]+)/lessons/([^#\s)]+)#([^\s)]+)(?:\s+"([^"]+)")?\)',
            lesson.markdown,
        )
        assert links, f"{slug}: missing cross-lesson references"
        assert any(definition for *_, definition in links), f"{slug}: no concept previews"
        for course, target, anchor, definition in links:
            assert (course, target) in lessons, f"{slug}: missing {course}/{target}"
            headings = re.findall(r"^#{1,3} (.+)$", lessons[course, target].markdown, re.M)
            assert unquote(anchor) in {_anchor(h) for h in headings}, f"{slug}: broken #{anchor}"
            if definition:
                assert len(definition) <= 600, f"{slug}: preview should stay concise"


def test_rag_diagrams_are_local_accessible_svg_assets():
    lessons = _lessons()
    public = Path(__file__).resolve().parents[2] / "frontend" / "public"
    seen = set()
    for slug in LESSONS:
        images = re.findall(r'!\[([^\]]+)\]\((/lesson-media/[^\s)]+)', lessons["llm", slug].markdown)
        assert images, f"{slug}: no diagrams"
        for alt, source in images:
            assert alt.strip()
            filename, _, dimensions = source.partition("#")
            path = public / filename.lstrip("/")
            assert path.is_file(), f"{slug}: missing {filename}"
            if path.suffix == ".svg":
                svg = ET.parse(path).getroot()
                assert svg.attrib["viewBox"] == "0 0 1200 720"
                assert dimensions == "1200x720"
                assert svg.find("{http://www.w3.org/2000/svg}title") is not None
                assert not svg.findall(".//{http://www.w3.org/2000/svg}script")
                seen.add(path.name)
    assert len(seen) == 6
