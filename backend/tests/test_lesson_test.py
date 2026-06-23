"""Lesson MCQ self-test: serve closed questions + auth-gated client-side stats.

The serve endpoint deliberately ships the correct index + explanation (the
options are visible anyway and grading is a plain index compare). Stats are
per-user, keyed by the MCQ's stable slug.
"""
from __future__ import annotations

CREDS = {"email": "mcq@example.com", "password": "secret123", "display_name": "M"}
GIL = "/api/quiz/courses/python-core/lessons/gil"


async def _auth(client) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code in (200, 201)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_test_endpoints_require_auth(client):
    assert (await client.get(f"{GIL}/test")).status_code == 403
    assert (await client.get(f"{GIL}/test/progress")).status_code == 403
    assert (
        await client.post(f"{GIL}/test/result", json={"items": []})
    ).status_code == 403


async def test_serve_lesson_test_is_well_formed(client):
    headers = await _auth(client)
    d = (await client.get(f"{GIL}/test", headers=headers)).json()
    assert d["course_slug"] == "python-core" and d["lesson_slug"] == "gil"
    assert d["total"] == 10  # 5 concepts x 2 MCQ
    assert len(d["questions"]) == 10
    slugs = set()
    for q in d["questions"]:
        slugs.add(q["slug"])
        assert q["type"] in ("single", "boolean")
        assert len(q["options"]) >= 2
        assert 0 <= q["correct_index"] < len(q["options"])
        assert q["concept_slug"] and q["concept_title"] and q["anchor"]
        assert q["text"].strip()
    assert len(slugs) == 10  # unique stable slugs
    # The stable slug format encodes course:lesson:concept:index.
    assert all(s.startswith("python-core:gil:") for s in slugs)


async def test_other_course_lesson_serves_full_test(client):
    """Every course now has authored MCQ: a non-pilot course's lesson serves a
    well-formed test with 2 MCQ per concept (the serve path is course-agnostic).
    The empty-bank contract (200 + []) is still honoured by serve_test for any
    lesson that has none — there just aren't any in the seeded content anymore."""
    headers = await _auth(client)
    courses = (await client.get("/api/courses", headers=headers)).json()
    other = next(c for c in courses if c["slug"] != "python-core")
    detail = (await client.get(f"/api/courses/{other['slug']}", headers=headers)).json()
    lesson = detail["lessons"][0]
    d = (
        await client.get(
            f"/api/quiz/courses/{other['slug']}/lessons/{lesson['slug']}/test",
            headers=headers,
        )
    ).json()
    assert d["total"] == 2 * lesson["concept_count"]
    assert len(d["questions"]) == d["total"]
    assert all(0 <= q["correct_index"] < len(q["options"]) for q in d["questions"])


async def test_missing_lesson_is_404(client):
    headers = await _auth(client)
    r = await client.get(f"/api/quiz/courses/python-core/lessons/nope/test", headers=headers)
    assert r.status_code == 404


async def test_record_results_and_progress_rollup(client):
    headers = await _auth(client)
    served = (await client.get(f"{GIL}/test", headers=headers)).json()
    slugs = [q["slug"] for q in served["questions"]]

    # Answer the first three: two right, one wrong.
    items = [
        {"slug": slugs[0], "correct": True},
        {"slug": slugs[1], "correct": True},
        {"slug": slugs[2], "correct": False},
    ]
    r = await client.post(f"{GIL}/test/result", json={"items": items}, headers=headers)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 10
    assert d["answered"] == 3
    assert d["correct"] == 2  # last-correct count
    # A partial run (3 of 10) is NOT a full run — no lesson score recorded.
    assert d["attempts"] == 0 and d["best_score"] == 0 and d["passed"] is False

    # GET progress reflects the same standing.
    p = (await client.get(f"{GIL}/test/progress", headers=headers)).json()
    assert p["total"] == 10 and p["answered"] == 3 and p["correct"] == 2
    assert p["best_score"] == 0

    # Re-answering the wrong one correctly bumps the correct count.
    d2 = (
        await client.post(
            f"{GIL}/test/result",
            json={"items": [{"slug": slugs[2], "correct": True}]},
            headers=headers,
        )
    ).json()
    assert d2["answered"] == 3 and d2["correct"] == 3


def _full_run(slugs, correct_slugs):
    """Build a result payload answering every lesson MCQ; correct_slugs are right."""
    return {"items": [{"slug": s, "correct": s in correct_slugs} for s in slugs]}


async def test_full_run_records_score_and_passes(client):
    headers = await _auth(client)
    slugs = [q["slug"] for q in (await client.get(f"{GIL}/test", headers=headers)).json()["questions"]]

    # All 10 correct → score 100, passed, one attempt.
    d = (
        await client.post(f"{GIL}/test/result", json=_full_run(slugs, set(slugs)), headers=headers)
    ).json()
    assert d["attempts"] == 1
    assert d["best_score"] == 100 and d["last_score"] == 100 and d["passed"] is True

    # A weaker full run (6/10): last_score drops, best stays 100, attempts grows.
    d2 = (
        await client.post(f"{GIL}/test/result", json=_full_run(slugs, set(slugs[:6])), headers=headers)
    ).json()
    assert d2["attempts"] == 2
    assert d2["last_score"] == 60 and d2["best_score"] == 100 and d2["passed"] is True


async def test_below_threshold_is_not_passed(client):
    headers = await _auth(client)
    slugs = [q["slug"] for q in (await client.get(f"{GIL}/test", headers=headers)).json()["questions"]]
    # 7/10 = 70% < 80% → recorded but not passed.
    d = (
        await client.post(f"{GIL}/test/result", json=_full_run(slugs, set(slugs[:7])), headers=headers)
    ).json()
    assert d["best_score"] == 70 and d["passed"] is False


async def test_incomplete_union_never_sets_best_score(client):
    """A subset run that leaves some MCQ unseen records no lesson score: the
    standing score is only computed once every MCQ has been answered."""
    headers = await _auth(client)
    slugs = [q["slug"] for q in (await client.get(f"{GIL}/test", headers=headers)).json()["questions"]]
    d = (
        await client.post(
            f"{GIL}/test/result", json=_full_run(slugs[:3], set(slugs[:3])), headers=headers
        )
    ).json()
    assert d["attempts"] == 0 and d["best_score"] == 0 and d["passed"] is False


async def test_review_mistakes_lifts_lesson_to_passed(client):
    """Regression: a sub-80 full run, then re-answering the failed questions
    correctly via "review mistakes" (a subset), completes the union of latest
    answers and lifts the lesson to passed — and the overview reflects it."""
    headers = await _auth(client)
    slugs = [q["slug"] for q in (await client.get(f"{GIL}/test", headers=headers)).json()["questions"]]

    # Full run, 7/10 = 70% → recorded but not passed.
    wrong = set(slugs[7:])  # last 3 wrong
    d = (
        await client.post(f"{GIL}/test/result", json=_full_run(slugs, set(slugs[:7])), headers=headers)
    ).json()
    assert d["best_score"] == 70 and d["passed"] is False

    ov = (await client.get("/api/quiz/tests/overview", headers=headers)).json()
    assert ov["passed"] == 0

    # Review mistakes: re-answer just the 3 wrong ones correctly (a subset).
    d2 = (
        await client.post(
            f"{GIL}/test/result",
            json={"items": [{"slug": s, "correct": True} for s in wrong]},
            headers=headers,
        )
    ).json()
    # Union of latest answers is now all-correct → standing score 100, passed.
    assert d2["correct"] == 10 and d2["best_score"] == 100 and d2["passed"] is True

    ov2 = (await client.get("/api/quiz/tests/overview", headers=headers)).json()
    assert ov2["passed"] == 1


async def test_tests_overview(client):
    headers = await _auth(client)
    # Before any run: python-core has MCQ lessons, none passed/started.
    ov0 = (await client.get("/api/quiz/tests/overview", headers=headers)).json()
    assert ov0["total"] >= 10 and ov0["passed"] == 0 and ov0["started"] == 0
    pc0 = next(c for c in ov0["courses"] if c["slug"] == "python-core")
    assert pc0["total"] == 10 and pc0["passed"] == 0
    # Courses without authored MCQ are omitted from the overview.
    assert all(c["total"] > 0 for c in ov0["courses"])

    # Pass the GIL lesson test (full run, all correct).
    slugs = [q["slug"] for q in (await client.get(f"{GIL}/test", headers=headers)).json()["questions"]]
    await client.post(f"{GIL}/test/result", json=_full_run(slugs, set(slugs)), headers=headers)

    ov1 = (await client.get("/api/quiz/tests/overview", headers=headers)).json()
    assert ov1["passed"] == 1 and ov1["started"] == 1
    pc1 = next(c for c in ov1["courses"] if c["slug"] == "python-core")
    assert pc1["passed"] == 1 and pc1["started"] == 1


async def test_tests_overview_requires_auth(client):
    assert (await client.get("/api/quiz/tests/overview")).status_code == 403


async def test_unknown_slug_ignored(client):
    headers = await _auth(client)
    served = (await client.get(f"{GIL}/test", headers=headers)).json()
    good = served["questions"][0]["slug"]
    d = (
        await client.post(
            f"{GIL}/test/result",
            json={
                "items": [
                    {"slug": good, "correct": True},
                    {"slug": "python-core:gil:does-not-exist:9", "correct": True},
                ]
            },
            headers=headers,
        )
    ).json()
    assert d["answered"] == 1  # only the valid slug counted


async def test_progress_is_per_user(client):
    headers = await _auth(client)
    served = (await client.get(f"{GIL}/test", headers=headers)).json()
    await client.post(
        f"{GIL}/test/result",
        json={"items": [{"slug": served["questions"][0]["slug"], "correct": True}]},
        headers=headers,
    )
    other = await client.post(
        "/api/auth/register",
        json={"email": "mcq2@example.com", "password": "secret123", "display_name": "M2"},
    )
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    p = (await client.get(f"{GIL}/test/progress", headers=h2)).json()
    assert p["answered"] == 0 and p["correct"] == 0
