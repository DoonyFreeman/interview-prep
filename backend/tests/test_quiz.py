"""Quiz flow tests with a fake LLM (no network).

The real Gemini client is replaced via a ``get_llm`` dependency override, so these
exercise serving / evaluating / hinting and the persistence + normalization logic
without any API key or HTTP call.
"""
from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

from app.content.seed import seed_from_dir
from app.database import get_session
from app.llm.client import get_llm
from app.main import create_app
from app.models import Attempt

CREDS = {"email": "quiz@example.com", "password": "secret123", "display_name": "Q"}


class FakeLLM:
    """Records calls and returns canned responses."""

    def __init__(self, json_payload: dict | None = None, text: str = "Подумай о подсчёте ссылок."):
        self.json_payload = json_payload if json_payload is not None else {
            "score": 75,
            "verdict": "частично",
            "summary": "Хороший ответ, но не полный.",
            "strengths": ["Верно про мьютекс"],
            "gaps": ["Не упомянут подсчёт ссылок"],
            "suggestion": "Добавьте про reference counting.",
        }
        self.text = text
        self.calls: list[tuple[str, str, str | None]] = []

    async def generate_json(self, prompt: str, *, system: str | None = None) -> dict:
        self.calls.append(("json", prompt, system))
        return self.json_payload

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        self.calls.append(("text", prompt, system))
        return self.text


@pytest.fixture
def fake_llm() -> FakeLLM:
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


async def _auth_header(client) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _first_question_id(client, headers) -> int:
    r = await client.get(
        "/api/quiz/courses/python-core/lessons/gil/next", headers=headers
    )
    assert r.status_code == 200
    return r.json()["id"]


# --------------------------------------------------------------------------- #
# Serve
# --------------------------------------------------------------------------- #
async def test_next_question_requires_auth(client):
    r = await client.get("/api/quiz/courses/python-core/lessons/gil/next")
    assert r.status_code in (401, 403)


async def test_next_question_shape_and_no_reference(client):
    headers = await _auth_header(client)
    r = await client.get(
        "/api/quiz/courses/python-core/lessons/gil/next", headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["text"]
    assert body["course_slug"] == "python-core"
    assert body["lesson_slug"] == "gil"
    assert body["concept_slug"]
    assert "anchor" in body
    # The reference answer must never reach the client.
    assert "reference_answer" not in body


async def test_next_question_unknown_lesson_404(client):
    headers = await _auth_header(client)
    r = await client.get(
        "/api/quiz/courses/python-core/lessons/nope/next", headers=headers
    )
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# Re-practice: question by id + lesson questions list with history
# --------------------------------------------------------------------------- #
async def test_get_question_by_id(client):
    headers = await _auth_header(client)
    qid = await _first_question_id(client, headers)

    r = await client.get(f"/api/quiz/questions/{qid}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == qid
    assert body["text"]
    assert "reference_answer" not in body


async def test_get_question_unknown_404(client):
    headers = await _auth_header(client)
    r = await client.get("/api/quiz/questions/999999", headers=headers)
    assert r.status_code == 404


async def test_lesson_questions_list_and_history(client):
    headers = await _auth_header(client)

    r = await client.get(
        "/api/quiz/courses/python-core/lessons/gil/questions", headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["course_slug"] == "python-core"
    assert len(body["questions"]) == 5  # GIL lesson has 5 concepts × 1 question
    first = body["questions"][0]
    assert first["attempts"] == 0
    assert first["last_score"] is None
    assert "reference_answer" not in first

    # Answer one question, then it shows up in history.
    qid = body["questions"][0]["id"]
    await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "ответ"},
        headers=headers,
    )
    r2 = await client.get(
        "/api/quiz/courses/python-core/lessons/gil/questions", headers=headers
    )
    answered = next(q for q in r2.json()["questions"] if q["id"] == qid)
    assert answered["attempts"] == 1
    assert answered["last_score"] == 75  # fake LLM default
    assert answered["last_verdict"] == "частично"
    assert answered["last_attempted_at"]


async def test_lesson_questions_requires_auth(client):
    r = await client.get("/api/quiz/courses/python-core/lessons/gil/questions")
    assert r.status_code in (401, 403)


async def test_question_attempts_history(client):
    headers = await _auth_header(client)
    qid = await _first_question_id(client, headers)

    # No attempts yet.
    r = await client.get(f"/api/quiz/questions/{qid}/attempts", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["question_id"] == qid
    assert body["text"]
    assert body["attempts"] == []
    assert "reference_answer" not in r.text

    # Two answers → two attempts, newest first, carrying answer + review.
    await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "первый ответ"},
        headers=headers,
    )
    await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "второй ответ", "hint_used": True},
        headers=headers,
    )
    r = await client.get(f"/api/quiz/questions/{qid}/attempts", headers=headers)
    attempts = r.json()["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["answer_text"] == "второй ответ"  # newest first
    assert attempts[1]["answer_text"] == "первый ответ"
    assert attempts[0]["hint_used"] is True
    # Stored review surfaces (fake LLM defaults).
    assert attempts[0]["score"] == 75
    assert attempts[0]["verdict"] == "частично"
    assert attempts[0]["gaps"]
    assert attempts[0]["created_at"]
    assert "reference_answer" not in r.text


async def test_question_attempts_requires_auth(client):
    r = await client.get("/api/quiz/questions/1/attempts")
    assert r.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Evaluate
# --------------------------------------------------------------------------- #
async def test_evaluate_returns_review_and_stores_attempt(client, Session, fake_llm):
    headers = await _auth_header(client)
    qid = await _first_question_id(client, headers)

    r = await client.post(
        f"/api/quiz/questions/{qid}/evaluate",
        json={"answer_text": "GIL — это мьютекс в CPython.", "hint_used": False},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 75
    assert body["verdict"] == "частично"
    assert body["strengths"] and body["gaps"]
    assert body["attempt_id"]

    # The grader was called with the eval system prompt and the reference answer.
    assert fake_llm.calls and fake_llm.calls[0][0] == "json"
    assert "ЭТАЛОННЫЙ ОТВЕТ" in fake_llm.calls[0][1]

    # An Attempt row was persisted with the score.
    async with Session() as session:
        attempts = (await session.execute(select(Attempt))).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].question_id == qid
    assert attempts[0].score == 75


async def test_evaluate_normalizes_bad_model_output(client, Session):
    """Off-contract score/verdict get clamped and a verdict derived from score."""
    bad = FakeLLM(json_payload={"score": 150, "verdict": "AMAZING", "summary": "ok"})
    app = create_app()

    async def _override_get_session():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_llm] = lambda: bad

    async with Session() as session:
        await seed_from_dir(session)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        headers = await _auth_header(c)
        qid = await _first_question_id(c, headers)
        r = await c.post(
            f"/api/quiz/questions/{qid}/evaluate",
            json={"answer_text": "x"},
            headers=headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 100  # clamped from 150
    assert body["verdict"] == "верно"  # derived from score (>=80)
    assert body["strengths"] == [] and body["gaps"] == []


async def test_evaluate_unknown_question_404(client):
    headers = await _auth_header(client)
    r = await client.post(
        "/api/quiz/questions/999999/evaluate",
        json={"answer_text": "x"},
        headers=headers,
    )
    assert r.status_code == 404


async def test_evaluate_requires_auth(client):
    r = await client.post(
        "/api/quiz/questions/1/evaluate", json={"answer_text": "x"}
    )
    assert r.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Hint
# --------------------------------------------------------------------------- #
async def test_hint_returns_text_without_reference(client, fake_llm):
    headers = await _auth_header(client)
    qid = await _first_question_id(client, headers)

    r = await client.post(
        f"/api/quiz/questions/{qid}/hint",
        json={"answer_text": ""},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["hint"] == fake_llm.text

    # Hint call used generate_text and the hint system prompt; the prompt builder
    # must NOT include the reference answer section.
    kind, prompt, _system = fake_llm.calls[-1]
    assert kind == "text"
    assert "ЭТАЛОННЫЙ ОТВЕТ" not in prompt


async def test_hint_requires_auth(client):
    r = await client.post("/api/quiz/questions/1/hint", json={"answer_text": ""})
    assert r.status_code in (401, 403)
