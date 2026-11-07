"""Keep the five-day agent path connected, compact and runnable in the reader."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from app.config import get_settings
from app.content.loader import load_content

SLUGS = (
    "langchain-components", "langchain-contracts", "agent-decisions",
    "langgraph-state", "langgraph-persistence",
)


def _lessons():
    bundle = load_content(get_settings().content_dir)
    return {(c.slug, l.slug): l for c in bundle.courses for l in c.lessons}


def _anchor(text):
    text = re.sub(r"[^\w\s-]", "", text.lower()).replace("_", "")
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", text.strip()))


def test_agent_path_has_five_short_registered_lessons():
    lessons = _lessons()
    for order, slug in enumerate(SLUGS, 8):
        assert ("llm", slug) in lessons, f"Missing study day: {slug}"
        lesson = lessons["llm", slug]
        assert lesson.order_index == order
        assert 25 <= lesson.duration_minutes <= 35
        assert 4 <= len(lesson.concepts) <= 5
        assert len(re.findall(r"\S+", lesson.markdown)) <= 1600, f"{slug}: split this long lesson"
        assert "```solution\n" in lesson.markdown


def test_agent_links_and_diagrams_reach_real_targets():
    lessons = _lessons()
    public = Path(__file__).resolve().parents[2] / "frontend/public"
    seen = set()
    for slug in SLUGS:
        text = lessons["llm", slug].markdown
        links = re.findall(r'\[[^\]]+\]\(/courses/([^/]+)/lessons/([^#\s)]+)(?:#([^\s)]+))?(?:\s+"([^"]+)")?\)', text)
        assert any(anchor and preview for _, _, anchor, preview in links), f"{slug}: needs concept preview"
        for course, target, anchor, _ in links:
            assert (course, target) in lessons, f"{slug}: broken {course}/{target}"
            if anchor:
                headings = re.findall(r"^#{1,3} (.+)$", lessons[course, target].markdown, re.M)
                assert unquote(anchor) in {_anchor(h) for h in headings}, f"{slug}: broken #{anchor}"
        images = re.findall(r'!\[([^\]]+)\]\((/lesson-media/[^\s)]+)', text)
        assert images, f"{slug}: missing diagram"
        for alt, source in images:
            name, _, size = source.partition("#")
            assert alt.strip() and size == "1200x720"
            root = ET.parse(public / name.lstrip("/")).getroot()
            assert root.attrib["viewBox"] == "0 0 1200 720"
            assert root.find("{http://www.w3.org/2000/svg}title") is not None
            assert root.find("{http://www.w3.org/2000/svg}desc") is not None
            assert not root.findall(".//{http://www.w3.org/2000/svg}script")
            seen.add(name)
    assert len(seen) == 8


def test_graph_walkthrough_has_concrete_states_and_finite_steps():
    text = _lessons()["llm", "langgraph-state"].markdown
    blocks = re.findall(r"```execution\n(.*?)\n```", text, re.S)
    assert blocks
    for block in blocks:
        trace = json.loads(block)
        assert trace["title"] and 3 <= len(trace["nodes"]) <= 12
        assert 4 <= len(trace["steps"]) <= 40
        for step in trace["steps"]:
            assert step["node"] in trace["nodes"]
            assert step["explanation"] and isinstance(step["state"], dict)
        assert trace["steps"][0]["state"] != trace["steps"][-1]["state"]
