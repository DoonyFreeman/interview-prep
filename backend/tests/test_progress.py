"""Phase 4: SM-2 units + progress/review/lesson endpoints with a fake LLM.

Evaluating an answer advances mastery, so the integration tests drive the real
``/evaluate`` route with a dependency-overridden fake grader (no network), then
read mastery back via the progress endpoints.
"""
from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

from app.content.seed import seed_from_dir
from app.database import get_session
from app.llm.client import get_llm
from app.main import create_app
from app.models import Concept, ConceptMastery, User, _utcnow
from app.services.sm2 import (
    DEFAULT_EASE,
    MIN_EASE,
    SM2State,
    score_to_quality,
    sm2_update,
)

CREDS = {"email": "p@example.com", "password": "secret123", "display_name": "P"}


# --------------------------------------------------------------------------- #
# Pure SM-2
# --------------------------------------------------------------------------- #
def test_score_to_quality_maps_full_range():
    assert score_to_quality(0) == 0
    assert score_to_quality(100) == 5
    assert score_to_quality(60) == 3
    assert score_to_quality(150) == 5  # clamped
    assert score_to_quality(-10) == 0  # clamped


def test_first_success_interval_one():
    s = sm2_update(SM2State(DEFAULT_EASE, 0.0, 0), quality=5)
    assert s.reps == 1
    assert s.interval_days == 1.0
    assert s.ease > DEFAULT_EASE  # quality 5 raises ease


def test_second_success_interval_six():
    s = sm2_update(SM2State(DEFAULT_EASE, 1.0, 1), quality=4)
    assert s.reps == 2
    assert s.interval_days == 6.0


def test_third_success_scales_by_ease():
    s2 = SM2State(ease=2.5, interval_days=6.0, reps=2)
    s3 = sm2_update(s2, quality=5)
    assert s3.reps == 3
    assert s3.interval_days == round(6.0 * s3.ease)


def test_lapse_resets_reps_and_lowers_ease():
    before = SM2State(ease=2.5, interval_days=6.0, reps=3)
    after = sm2_update(before, quality=1)
    assert after.reps == 0
    assert after.interval_days == 1.0
    assert after.ease < before.ease


def test_ease_never_below_floor():
    s = SM2State(ease=MIN_EASE, interval_days=10.0, reps=5)
    for _ in range(10):
        s = sm2_update(s, quality=0)
    assert s.ease >= MIN_EASE


# --------------------------------------------------------------------------- #
# Integration fixtures
# --------------------------------------------------------------------------- #
class FakeLLM:
    def __init__(self, score: int = 90):
        self.json_payload = {
            "score": score,
            "verdict": "верно",
            "summary": "Отличный ответ.",
            "strengths": ["Всё по делу"],
            "gaps": [],
            "suggestion": "Так держать.",
        }
        self.text = "Подсказка."

    async def generate_json(self, prompt, *, system=None):
        return self.json_payload

    async def generate_text(self, prompt, *, system=None):
        return self.text


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest_asyncio.fixture
async def client(Session, fake_llm):
    async with Session() as session:
        await seed_from_dir(session)
    app = create_app()

    async def _override_get_session():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_llm] = lambda: fake_llm
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth(client) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _user_id(Session) -> int:
    async with Session() as s:
        return (
            await s.execute(select(User.id).where(User.email == CREDS["email"]))
        ).scalar_one()


async def _serve_qid(client, headers) -> int:
    r = await client.get(
        "/api/quiz/courses/python-core/lessons/gil/next", headers=headers
    )
    assert r.status_code == 200
    return r.json()["id"]


# --------------------------------------------------------------------------- #
# Mastery via evaluate
# --------------------------------------------------------------------------- #
async def test_evaluate_creates_mastery(client):
    headers = await _auth(client)
    qid = await _serve_qid(client, headers)
    r = await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "хороший ответ"},
        headers=headers,
    )
    assert r.status_code == 200
    m = r.json()["mastery"]
    assert m["reps"] == 1
    assert m["interval_days"] == 1.0
    assert m["last_score"] == 90
    assert m["due"] is False  # due tomorrow, not now
    assert r.json()["concept_slug"]


async def test_overview_counts_attempted_and_mastered(client, Session):
    headers = await _auth(client)
    qid = await _serve_qid(client, headers)

    # First high-score attempt: attempted but not yet mastered (reps == 1).
    await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "a"},
        headers=headers,
    )
    ov = (await client.get("/api/progress", headers=headers)).json()
    assert ov["total_concepts"] == 5
    assert ov["attempted_concepts"] == 1
    assert ov["mastered_concepts"] == 0

    # Second high-score attempt on the same question -> reps 2, score 90 -> mastered.
    await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "a"},
        headers=headers,
    )
    ov = (await client.get("/api/progress", headers=headers)).json()
    assert ov["attempted_concepts"] == 1
    assert ov["mastered_concepts"] == 1
    # Nested structure is present.
    course = ov["courses"][0]
    assert course["slug"] == "python-core"
    assert course["lessons"][0]["slug"] == "gil"


async def test_review_queue_empty_then_due(client, Session):
    headers = await _auth(client)
    # Nothing attempted yet -> empty queue.
    q = (await client.get("/api/progress/review", headers=headers)).json()
    assert q["count"] == 0 and q["items"] == []

    # Insert a mastery row already due in the past.
    uid = await _user_id(Session)
    async with Session() as s:
        concept_id = (
            await s.execute(select(Concept.id).where(Concept.slug == "what-is-gil"))
        ).scalar_one()
        s.add(
            ConceptMastery(
                user_id=uid,
                concept_id=concept_id,
                ease=2.5,
                interval_days=1.0,
                reps=1,
                last_score=40,
                due_at=_utcnow() - timedelta(days=1),
            )
        )
        await s.commit()

    q = (await client.get("/api/progress/review", headers=headers)).json()
    assert q["count"] == 1
    item = q["items"][0]
    assert item["concept_slug"] == "what-is-gil"
    assert item["course_slug"] == "python-core"
    assert item["question_id"]  # a practice question is attached


async def test_mark_lesson_completed(client):
    headers = await _auth(client)
    r = await client.post(
        "/api/progress/courses/python-core/lessons/gil",
        json={"completed": True},
        headers=headers,
    )
    assert r.status_code == 204

    ov = (await client.get("/api/progress", headers=headers)).json()
    assert ov["courses"][0]["lessons"][0]["completed"] is True


async def test_mark_lesson_unknown_404(client):
    headers = await _auth(client)
    r = await client.post(
        "/api/progress/courses/python-core/lessons/nope",
        json={"completed": True},
        headers=headers,
    )
    assert r.status_code == 404


async def test_progress_requires_auth(client):
    assert (await client.get("/api/progress")).status_code in (401, 403)
    assert (await client.get("/api/progress/review")).status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Spaced-repetition-aware serving
# --------------------------------------------------------------------------- #
async def _concept_id(Session, slug: str) -> int:
    async with Session() as s:
        return (
            await s.execute(select(Concept.id).where(Concept.slug == slug))
        ).scalar_one()


async def _seed_mastery(Session, uid, slug, *, due_at):
    cid = await _concept_id(Session, slug)
    async with Session() as s:
        s.add(
            ConceptMastery(
                user_id=uid,
                concept_id=cid,
                ease=2.5,
                interval_days=6.0,
                reps=2,
                last_score=90,
                due_at=due_at,
            )
        )
        await s.commit()


ALL_GIL_CONCEPTS = [
    "what-is-gil",
    "gil-and-threads",
    "gil-release",
    "bypass-gil",
    "gil-future",
]


async def test_serve_prefers_never_attempted_concept(client, Session):
    headers = await _auth(client)
    uid = await _user_id(Session)
    far_future = _utcnow() + timedelta(days=30)
    # Give every concept mastery EXCEPT 'bypass-gil'.
    for slug in ALL_GIL_CONCEPTS:
        if slug != "bypass-gil":
            await _seed_mastery(Session, uid, slug, due_at=far_future)

    # The only un-attempted concept must be served (selection is deterministic here).
    for _ in range(5):
        r = await client.get(
            "/api/quiz/courses/python-core/lessons/gil/next", headers=headers
        )
        assert r.json()["concept_slug"] == "bypass-gil"


async def test_serve_prefers_due_concept(client, Session):
    headers = await _auth(client)
    uid = await _user_id(Session)
    far_future = _utcnow() + timedelta(days=30)
    overdue = _utcnow() - timedelta(days=2)
    for slug in ALL_GIL_CONCEPTS:
        due = overdue if slug == "gil-release" else far_future
        await _seed_mastery(Session, uid, slug, due_at=due)

    # All concepts attempted; only 'gil-release' is due -> it must be served.
    for _ in range(5):
        r = await client.get(
            "/api/quiz/courses/python-core/lessons/gil/next", headers=headers
        )
        assert r.json()["concept_slug"] == "gil-release"
