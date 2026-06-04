"""Content loader/seed + read-endpoint tests against the real GIL lesson."""
from __future__ import annotations

from sqlalchemy import func, select

from app.content.seed import seed_from_dir
from app.models import Course, Question


async def test_seed_creates_course_and_questions(Session):
    async with Session() as s:
        n = await seed_from_dir(s)
    assert n >= 1
    async with Session() as s:
        courses = (await s.execute(select(func.count()).select_from(Course))).scalar()
        questions = (
            await s.execute(select(func.count()).select_from(Question))
        ).scalar()
    assert courses == 1
    assert questions == 5  # 5 concepts x 1 question in the GIL lesson


async def test_seed_is_idempotent(Session):
    async with Session() as s:
        await seed_from_dir(s)
    async with Session() as s:
        await seed_from_dir(s)  # second run must not duplicate
    async with Session() as s:
        courses = (await s.execute(select(func.count()).select_from(Course))).scalar()
        questions = (
            await s.execute(select(func.count()).select_from(Question))
        ).scalar()
    assert courses == 1
    assert questions == 5


async def test_list_courses(client):
    r = await client.get("/api/courses")
    assert r.status_code == 200
    data = r.json()
    py = next((c for c in data if c["slug"] == "python-core"), None)
    assert py is not None
    assert py["lesson_count"] == 1


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
