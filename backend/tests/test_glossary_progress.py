"""Glossary quiz progress: auth-gated stats recording + per-category rollup."""
from __future__ import annotations

CREDS = {"email": "g@example.com", "password": "secret123", "display_name": "G"}


async def _auth(client) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code in (200, 201)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_progress_requires_auth(client):
    assert (await client.get("/api/glossary/progress")).status_code == 403
    assert (
        await client.post("/api/glossary/quiz/result", json={"items": []})
    ).status_code == 403


async def test_empty_progress(client):
    headers = await _auth(client)
    d = (await client.get("/api/glossary/progress", headers=headers)).json()
    assert d["total"] >= 100  # all seeded terms
    assert d["seen"] == 0
    assert d["mastered"] == 0
    assert d["terms"] == []
    # categories rolled up with totals even before any attempt
    assert any(c["category"] == "python" and c["total"] > 0 for c in d["categories"])


async def test_record_result_accumulates_and_marks_mastered(client):
    headers = await _auth(client)

    # First correct answer: seen=1, correct=1 — not mastered yet (needs >=2).
    r1 = await client.post(
        "/api/glossary/quiz/result",
        json={"items": [{"term_slug": "gil", "correct": True}]},
        headers=headers,
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["recorded"] == 1
    assert d1["seen"] == 1
    assert d1["mastered"] == 0
    gil = next(t for t in d1["terms"] if t["term_slug"] == "gil")
    assert gil["seen"] == 1 and gil["correct"] == 1 and gil["mastered"] is False

    # Second correct answer: correct=2 and last correct → mastered.
    d2 = (
        await client.post(
            "/api/glossary/quiz/result",
            json={"items": [{"term_slug": "gil", "correct": True}]},
            headers=headers,
        )
    ).json()
    assert d2["mastered"] == 1
    gil2 = next(t for t in d2["terms"] if t["term_slug"] == "gil")
    assert gil2["seen"] == 2 and gil2["correct"] == 2 and gil2["mastered"] is True

    # Category rollup reflects the mastered python term.
    py = next(c for c in d2["categories"] if c["category"] == "python")
    assert py["seen"] >= 1 and py["mastered"] == 1


async def test_wrong_answer_breaks_mastery(client):
    headers = await _auth(client)
    for correct in (True, True):  # reach mastered
        await client.post(
            "/api/glossary/quiz/result",
            json={"items": [{"term_slug": "gil", "correct": correct}]},
            headers=headers,
        )
    # A wrong answer flips last_correct, so it's no longer mastered.
    d = (
        await client.post(
            "/api/glossary/quiz/result",
            json={"items": [{"term_slug": "gil", "correct": False}]},
            headers=headers,
        )
    ).json()
    gil = next(t for t in d["terms"] if t["term_slug"] == "gil")
    assert gil["seen"] == 3 and gil["correct"] == 2
    assert gil["last_correct"] is False and gil["mastered"] is False
    assert d["mastered"] == 0


async def test_unknown_slug_ignored(client):
    headers = await _auth(client)
    d = (
        await client.post(
            "/api/glossary/quiz/result",
            json={
                "items": [
                    {"term_slug": "gil", "correct": True},
                    {"term_slug": "does-not-exist", "correct": True},
                ]
            },
            headers=headers,
        )
    ).json()
    assert d["recorded"] == 1  # only the valid slug counted
    assert {t["term_slug"] for t in d["terms"]} == {"gil"}


async def test_progress_is_per_user(client):
    headers = await _auth(client)
    await client.post(
        "/api/glossary/quiz/result",
        json={"items": [{"term_slug": "gil", "correct": True}]},
        headers=headers,
    )
    # A different user starts clean.
    other = await client.post(
        "/api/auth/register",
        json={"email": "g2@example.com", "password": "secret123", "display_name": "G2"},
    )
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    d = (await client.get("/api/glossary/progress", headers=h2)).json()
    assert d["seen"] == 0 and d["terms"] == []
