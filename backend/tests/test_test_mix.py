"""Mixed test (the /tests section): topics, generation, and result recording.

The mix draws from any course, so unlike the per-lesson test it selects
server-side and every question carries its own course/lesson deep link. Answers
still flow into the same ``mcq_stats``, and any lesson the run completes gets its
standing score recomputed.
"""
from __future__ import annotations

import random

from app.services.lesson_test import pick_mix

CREDS = {"email": "mix@example.com", "password": "secret123", "display_name": "X"}
TOPICS = "/api/quiz/tests/topics"
MIX = "/api/quiz/tests/mix"


async def _auth(client) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code in (200, 201)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class _Stat:
    """Stand-in for an McqStat row — pick_mix only reads these four fields."""

    def __init__(self, seen=0, correct=0, last_correct=False, last_seen_at=None):
        from app.models import _utcnow
        from datetime import timedelta

        self.seen = seen
        self.correct = correct
        self.last_correct = last_correct
        self.last_seen_at = last_seen_at or (_utcnow() - timedelta(days=1))


def _pool(n: int, courses: int = 2):
    return [(i, f"slug-{i}", f"course-{i % courses}") for i in range(n)]


# --------------------------------------------------------------- selection ---
def test_pick_mix_respects_count_and_returns_unique_ids():
    ids = pick_mix(_pool(50), {}, mode="random", count=12, rng=random.Random(1))
    assert len(ids) == 12
    assert len(set(ids)) == 12


def test_pick_mix_caps_at_pool_size():
    ids = pick_mix(_pool(5), {}, mode="random", count=40, rng=random.Random(1))
    assert len(ids) == 5


def test_random_mode_is_actually_uniform():
    """'Random' must not be smart-in-disguise: over many draws from a pool where
    one item is 'mastered', every item should come up about equally often."""
    pool = _pool(20, courses=1)
    stats = {f"slug-{i}": _Stat(seen=9, correct=9, last_correct=True) for i in range(10)}
    rng = random.Random(7)
    hits = {i: 0 for i in range(20)}
    for _ in range(400):
        for mcq_id in pick_mix(pool, stats, mode="random", count=5, rng=rng):
            hits[mcq_id] += 1
    mastered = sum(hits[i] for i in range(10))
    fresh = sum(hits[i] for i in range(10, 20))
    assert abs(mastered - fresh) < 0.2 * (mastered + fresh)


def test_smart_mode_prefers_unseen_and_wrong():
    """Same pool, smart mode: the never-seen and last-wrong half should dominate."""
    pool = _pool(20, courses=1)
    stats = {f"slug-{i}": _Stat(seen=9, correct=9, last_correct=True) for i in range(10)}
    rng = random.Random(7)
    mastered = fresh = 0
    for _ in range(200):
        for mcq_id in pick_mix(pool, stats, mode="smart", count=5, rng=rng):
            if mcq_id < 10:
                mastered += 1
            else:
                fresh += 1
    assert fresh > mastered * 3


def test_mistakes_mode_only_returns_last_wrong():
    pool = _pool(20, courses=1)
    stats = {
        "slug-3": _Stat(seen=2, correct=1, last_correct=False),
        "slug-8": _Stat(seen=1, correct=0, last_correct=False),
        "slug-5": _Stat(seen=2, correct=2, last_correct=True),
    }
    ids = pick_mix(pool, stats, mode="mistakes", count=20, rng=random.Random(3))
    assert sorted(ids) == [3, 8]


def test_weak_mode_includes_unseen_but_not_mastered():
    pool = _pool(6, courses=1)
    stats = {f"slug-{i}": _Stat(seen=3, correct=3, last_correct=True) for i in range(4)}
    stats["slug-2"] = _Stat(seen=1, correct=0, last_correct=False)
    ids = pick_mix(pool, stats, mode="weak", count=10, rng=random.Random(3))
    assert sorted(ids) == [2, 4, 5]  # the wrong one + the two never seen


def test_mix_interleaves_courses():
    """A mixed test should feel mixed: consecutive questions mostly change topic."""
    pool = [(i, f"slug-{i}", f"course-{i // 20}") for i in range(60)]  # 3 courses
    ids = pick_mix(pool, {}, mode="random", count=30, rng=random.Random(11))
    courses = [f"course-{i // 20}" for i in ids]
    same_as_previous = sum(1 for a, b in zip(courses, courses[1:]) if a == b)
    assert same_as_previous <= 3


def test_empty_pool_yields_nothing():
    assert pick_mix([], {}, mode="smart", count=10, rng=random.Random(1)) == []


# ---------------------------------------------------------------- API ---
async def test_mix_endpoints_require_auth(client):
    assert (await client.get(TOPICS)).status_code == 403
    assert (await client.get(MIX)).status_code == 403
    assert (await client.post(f"{MIX}/result", json={"items": []})).status_code == 403


async def test_topics_list_every_course_with_questions(client):
    headers = await _auth(client)
    d = (await client.get(TOPICS, headers=headers)).json()
    assert d["total"] > 0
    assert d["total"] == sum(t["total"] for t in d["topics"])
    assert d["lesson_total"] + d["exam_total"] == d["total"]
    assert d["answered"] == 0 and d["weak"] == 0  # fresh user
    core = next(t for t in d["topics"] if t["slug"] == "python-core")
    assert core["title"] and core["lesson_total"] > 0


async def test_mix_is_well_formed_and_carries_deep_links(client):
    headers = await _auth(client)
    d = (await client.get(f"{MIX}?count=15&mode=random", headers=headers)).json()
    assert d["count"] == 15 and d["pool"] >= 15
    assert len({q["slug"] for q in d["questions"]}) == 15  # no repeats in a run
    for q in d["questions"]:
        assert 0 <= q["correct_index"] < len(q["options"])
        # Unlike the lesson test, each question must say where it came from.
        assert q["course_slug"] and q["lesson_slug"]
        assert q["course_title"] and q["lesson_title"]
        assert q["anchor"] and q["concept_title"]
        assert q["bank"] in ("lesson", "exam")


async def test_mix_honours_the_course_filter(client):
    headers = await _auth(client)
    d = (
        await client.get(
            f"{MIX}?courses=python-core&count=25&mode=random", headers=headers
        )
    ).json()
    assert d["questions"]
    assert {q["course_slug"] for q in d["questions"]} == {"python-core"}


async def test_mix_rejects_an_unknown_mode(client):
    headers = await _auth(client)
    assert (await client.get(f"{MIX}?mode=nonsense", headers=headers)).status_code == 422


async def test_mix_count_is_bounded(client):
    headers = await _auth(client)
    assert (await client.get(f"{MIX}?count=0", headers=headers)).status_code == 422
    assert (await client.get(f"{MIX}?count=9999", headers=headers)).status_code == 422


async def test_mix_result_feeds_the_same_stats_and_lesson_scores(client):
    """A mixed run is not a parallel universe: its answers land in mcq_stats, so
    the topic tallies move and a lesson finished this way gets its score."""
    headers = await _auth(client)
    served = (
        await client.get(
            "/api/quiz/courses/python-core/lessons/gil/test", headers=headers
        )
    ).json()
    items = [{"slug": q["slug"], "correct": True} for q in served["questions"]]

    r = await client.post(f"{MIX}/result", json={"items": items}, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"recorded": len(items), "correct": len(items)}

    # The lesson's standing score was recomputed even though we posted via /mix.
    prog = (
        await client.get(
            "/api/quiz/courses/python-core/lessons/gil/test/progress", headers=headers
        )
    ).json()
    assert prog["best_score"] == 100 and prog["passed"] is True

    topics = (await client.get(TOPICS, headers=headers)).json()
    core = next(t for t in topics["topics"] if t["slug"] == "python-core")
    assert core["answered"] == len(items) and core["weak"] == 0


async def test_exam_bank_never_touches_a_lesson_score(client):
    """The exam bank is extra practice, not part of any lesson's test. Answering
    exam questions — even every one of them — must leave lesson progress alone."""
    headers = await _auth(client)
    exam = (
        await client.get(f"{MIX}?banks=exam&courses=python-core&count=50", headers=headers)
    ).json()
    assert exam["questions"], "python-core should have an authored exam bank"
    assert {q["bank"] for q in exam["questions"]} == {"exam"}

    await client.post(
        f"{MIX}/result",
        json={"items": [{"slug": q["slug"], "correct": True} for q in exam["questions"]]},
        headers=headers,
    )
    for lesson in {q["lesson_slug"] for q in exam["questions"]}:
        prog = (
            await client.get(
                f"/api/quiz/courses/python-core/lessons/{lesson}/test/progress",
                headers=headers,
            )
        ).json()
        assert prog["answered"] == 0, f"{lesson}: exam answers leaked into the lesson"
        assert prog["attempts"] == 0 and prog["best_score"] == 0


async def test_lesson_test_never_serves_exam_questions(client):
    headers = await _auth(client)
    served = (
        await client.get(
            "/api/quiz/courses/python-core/lessons/gil/test", headers=headers
        )
    ).json()
    assert served["questions"]
    assert all(q["bank"] == "lesson" for q in served["questions"])
    assert not any(q["slug"].startswith("exam:") for q in served["questions"])


async def test_mix_result_ignores_unknown_slugs(client):
    headers = await _auth(client)
    r = await client.post(
        f"{MIX}/result",
        json={"items": [{"slug": "does:not:exist:0", "correct": True}]},
        headers=headers,
    )
    assert r.json() == {"recorded": 0, "correct": 0}


async def test_mistakes_mode_returns_what_was_missed(client):
    headers = await _auth(client)
    served = (
        await client.get(
            "/api/quiz/courses/python-core/lessons/gil/test", headers=headers
        )
    ).json()
    wrong = [q["slug"] for q in served["questions"][:3]]
    await client.post(
        f"{MIX}/result",
        json={"items": [{"slug": s, "correct": False} for s in wrong]},
        headers=headers,
    )
    d = (await client.get(f"{MIX}?mode=mistakes&count=50", headers=headers)).json()
    assert sorted(q["slug"] for q in d["questions"]) == sorted(wrong)
    # `pool` must report what this mode can draw from, not the raw filter match.
    assert d["pool"] == len(wrong)
