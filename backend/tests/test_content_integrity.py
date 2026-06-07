"""Content-integrity tests over the whole curriculum (Phase 6: 20 courses).

These guard the on-disk content as it grows: every course parses, every concept
anchor matches a real H2 heading (so "back to theory" deep-links land), every
concept is backed by a question, questions.json has no orphan keys, every
reference answer is present server-side, and none of them leak to the client.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.config import get_settings
from app.content.loader import load_content


def slugify(text: str) -> str:
    """Mirror of ``frontend/src/lib/slugify.ts`` (and the content's anchors):

    lowercase -> drop punctuation (keep letters/digits/whitespace/dash, incl.
    Cyrillic; underscore is dropped) -> collapse whitespace to single dashes.
    """
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).replace("_", "")
    s = s.strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s


def _h2_anchors(markdown: str) -> set[str]:
    """Slugified anchors of every ``## `` heading in a lesson body."""
    anchors = set()
    for line in markdown.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            anchors.add(slugify(line[3:].strip()))
    return anchors


@pytest.fixture(scope="module")
def bundle():
    return load_content(get_settings().content_dir)


@pytest.fixture(scope="module")
def content_root() -> Path:
    return Path(get_settings().content_dir)


# --------------------------------------------------------------------------- #
# Structure
# --------------------------------------------------------------------------- #
def test_all_courses_load(bundle):
    assert len(bundle.courses) >= 20
    slugs = [c.slug for c in bundle.courses]
    assert len(slugs) == len(set(slugs))  # unique course slugs
    for course in bundle.courses:
        assert course.slug and course.title
        assert course.lessons, f"course {course.slug} has no lessons"
        for lesson in course.lessons:
            assert lesson.slug and lesson.title
            assert lesson.markdown.strip(), f"{course.slug}/{lesson.slug} empty md"
            assert lesson.concepts, f"{course.slug}/{lesson.slug} has no concepts"


# --------------------------------------------------------------------------- #
# Anchors match real H2 headings
# --------------------------------------------------------------------------- #
def test_concept_anchors_match_h2_headings(bundle):
    mismatches: list[str] = []
    for course in bundle.courses:
        for lesson in course.lessons:
            h2 = _h2_anchors(lesson.markdown)
            for concept in lesson.concepts:
                assert concept.anchor, f"{course.slug}/{lesson.slug}/{concept.slug}"
                if concept.anchor not in h2:
                    mismatches.append(
                        f"{course.slug}/{lesson.slug}/{concept.slug}: "
                        f"anchor={concept.anchor!r} not in H2 {sorted(h2)}"
                    )
    assert not mismatches, "anchor/H2 mismatch:\n" + "\n".join(mismatches)


# --------------------------------------------------------------------------- #
# Questions: every concept backed, no orphans, reference answers present
# --------------------------------------------------------------------------- #
def test_every_concept_has_a_question(bundle):
    empty = [
        f"{c.slug}/{l.slug}/{con.slug}"
        for c in bundle.courses
        for l in c.lessons
        for con in l.concepts
        if not con.questions
    ]
    assert not empty, "concepts without questions: " + ", ".join(empty)


def test_reference_answers_present(bundle):
    empty = [
        f"{c.slug}/{l.slug}/{con.slug}"
        for c in bundle.courses
        for l in c.lessons
        for con in l.concepts
        for q in con.questions
        if not q.reference_answer.strip()
    ]
    assert not empty, "questions with empty reference_answer: " + ", ".join(empty)


def test_questions_json_has_no_orphan_keys(content_root):
    """Every lesson/concept key in questions.json must exist in metadata.json."""
    orphans: list[str] = []
    courses_dir = content_root / "courses"
    for course_path in sorted(p for p in courses_dir.iterdir() if p.is_dir()):
        meta_file = course_path / "metadata.json"
        questions_file = course_path / "questions.json"
        if not meta_file.is_file() or not questions_file.is_file():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        questions = json.loads(questions_file.read_text(encoding="utf-8"))

        lessons = {l["slug"]: l for l in meta.get("lessons", [])}
        for lesson_slug, concept_map in questions.items():
            if lesson_slug not in lessons:
                orphans.append(f"{course_path.name}: lesson {lesson_slug!r}")
                continue
            valid_concepts = {c["slug"] for c in lessons[lesson_slug].get("concepts", [])}
            for concept_slug in concept_map:
                if concept_slug not in valid_concepts:
                    orphans.append(
                        f"{course_path.name}/{lesson_slug}: concept {concept_slug!r}"
                    )
    assert not orphans, "orphan questions.json keys:\n" + "\n".join(orphans)


# --------------------------------------------------------------------------- #
# Reference answers never leak through the lesson endpoint (all courses)
# --------------------------------------------------------------------------- #
async def test_reference_answers_never_leak_any_lesson(client):
    courses = (await client.get("/api/courses")).json()
    checked = 0
    for course in courses:
        detail = (await client.get(f"/api/courses/{course['slug']}")).json()
        for lesson in detail["lessons"]:
            r = await client.get(
                f"/api/courses/{course['slug']}/lessons/{lesson['slug']}"
            )
            assert r.status_code == 200
            assert "reference_answer" not in r.text
            checked += 1
    assert checked >= 90  # ~97 lessons in the full curriculum
