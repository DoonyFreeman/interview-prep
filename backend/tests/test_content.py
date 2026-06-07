"""Content loader/seed + read-endpoint tests.

Assertions are derived from the on-disk content via the loader rather than
hardcoded counts, so they survive content growth (Phase 6: 20 courses).
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.config import get_settings
from app.content.loader import load_content
from app.content.seed import seed_from_dir
from app.models import Concept, Course, Question


def _expected_counts():
    """Course / concept / question totals from the real content on disk."""
    bundle = load_content(get_settings().content_dir)
    courses = len(bundle.courses)
    concepts = sum(len(l.concepts) for c in bundle.courses for l in c.lessons)
    questions = sum(
        len(con.questions) for c in bundle.courses for l in c.lessons for con in l.concepts
    )
    return courses, concepts, questions


def _course_lesson_count(slug: str) -> int:
    bundle = load_content(get_settings().content_dir)
    course = next(c for c in bundle.courses if c.slug == slug)
    return len(course.lessons)


async def test_seed_creates_course_and_questions(Session):
    exp_courses, exp_concepts, exp_questions = _expected_counts()
    async with Session() as s:
        n = await seed_from_dir(s)
    assert n == exp_courses
    assert n >= 20  # full Phase 6 curriculum
    async with Session() as s:
        courses = (await s.execute(select(func.count()).select_from(Course))).scalar()
        concepts = (await s.execute(select(func.count()).select_from(Concept))).scalar()
        questions = (
            await s.execute(select(func.count()).select_from(Question))
        ).scalar()
    assert courses == exp_courses
    assert questions == exp_questions
    assert questions >= concepts  # every concept is backed by >=1 question


async def test_seed_is_idempotent(Session):
    async with Session() as s:
        await seed_from_dir(s)
    async with Session() as s:
        courses_1 = (await s.execute(select(func.count()).select_from(Course))).scalar()
        questions_1 = (
            await s.execute(select(func.count()).select_from(Question))
        ).scalar()
    async with Session() as s:
        await seed_from_dir(s)  # second run must not duplicate
    async with Session() as s:
        courses_2 = (await s.execute(select(func.count()).select_from(Course))).scalar()
        questions_2 = (
            await s.execute(select(func.count()).select_from(Question))
        ).scalar()
    assert courses_2 == courses_1
    assert questions_2 == questions_1


async def test_list_courses(client):
    r = await client.get("/api/courses")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 1  # multi-course curriculum
    py = next((c for c in data if c["slug"] == "python-core"), None)
    assert py is not None
    assert py["lesson_count"] == _course_lesson_count("python-core")


async def test_get_course_detail(client):
    r = await client.get("/api/courses/python-core")
    assert r.status_code == 200
    d = r.json()
    assert d["lessons"][0]["slug"] == "gil"
    assert d["lessons"][0]["concept_count"] == 5


async def test_get_lesson_serves_markdown_and_concepts(client):
    r = await client.get("/api/courses/python-core/lessons/gil")
    assert r.status_code == 200
    d = r.json()
    assert "GIL" in d["markdown"]
    assert len(d["concepts"]) == 5
    assert d["concepts"][0]["anchor"]  # anchor present for "back to theory"


async def test_reference_answers_never_leak(client):
    """Reference answers ground server-side grading and must not reach the client."""
    r = await client.get("/api/courses/python-core/lessons/gil")
    assert "reference_answer" not in r.text


async def test_unknown_course_404(client):
    r = await client.get("/api/courses/does-not-exist")
    assert r.status_code == 404
