"""Lesson MCQ self-test service: serve a lesson's closed questions, record
results, roll up the per-lesson "test score", and aggregate a tests overview.

This is the no-LLM counterpart to ``quiz.py``. Serving is a pure DB read; unlike
the open quiz it deliberately includes the correct option + explanation so the
client can grade instantly (the options are visible anyway and there is no LLM
to protect).

Two kinds of user-state, kept separate by design:
- ``mcq_stats`` (per MCQ): seen/correct/last_correct — for per-question review.
- ``lesson_test_results`` (per lesson): best/last **standing** score — the source
  of the lesson badge and the dashboard "tests passed" indicator. The score is
  computed from the user's *latest* answer to each MCQ (the ``mcq_stats`` union),
  recorded once every MCQ of the lesson has been answered at least once. So a
  "review mistakes" run (a subset) can complete the union and lift the lesson to
  passed; ``best_score`` is kept as ``max`` and never drops. No inflation: the
  score is always over the full lesson MCQ set, never a lone subset.

None of this touches SM-2 mastery: an MCQ guess never moves spaced repetition.

The bottom half of this module serves the **mixed** test (the ``/tests``
section): the same question banks, but drawn across courses in any quantity.
"""
from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import McqQuestion, McqStat, _utcnow
from app.repositories import (
    LessonRepository,
    LessonTestResultRepository,
    McqRepository,
    McqStatsRepository,
)
from app.repositories.mcq import BANK_EXAM, BANK_LESSON
from app.schemas import (
    LessonTestOut,
    LessonTestProgressOut,
    McqQuestionOut,
    MixResultOut,
    TestMixOut,
    TestsCourseOverviewOut,
    TestsOverviewOut,
    TestTopicOut,
    TestTopicsOut,
)

#: A lesson test counts as "passed" once the best full run reaches this score.
TEST_PASS_THRESHOLD = 80


def _to_out(mcq: McqQuestion, **context: str) -> McqQuestionOut:
    """Map an MCQ to its read schema. ``context`` carries course/lesson slugs +
    titles for the mixed test, where every question comes from a different
    lesson; the per-lesson test already knows them from the URL and omits them."""
    try:
        options = json.loads(mcq.options)
    except (ValueError, TypeError):
        options = []
    concept = mcq.concept
    return McqQuestionOut(
        slug=mcq.slug,
        type=mcq.type,
        text=mcq.text,
        options=list(options),
        correct_index=mcq.correct_index,
        explanation_md=mcq.explanation_md,
        concept_slug=concept.slug,
        concept_title=concept.title,
        anchor=concept.anchor,
        difficulty=mcq.difficulty,
        bank=mcq.bank,
        **context,
    )


async def _ensure_lesson(session: AsyncSession, course_slug: str, lesson_slug: str):
    lesson = await LessonRepository(session).get_by_slugs(course_slug, lesson_slug)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


async def serve_test(
    session: AsyncSession, course_slug: str, lesson_slug: str
) -> LessonTestOut:
    """All MCQ for a lesson (with correct index + explanation, for client grading).
    404 if the lesson doesn't exist; an empty list if it has no authored MCQ yet."""
    await _ensure_lesson(session, course_slug, lesson_slug)
    mcqs = await McqRepository(session).list_for_lesson(course_slug, lesson_slug)
    questions = [_to_out(m) for m in mcqs]
    return LessonTestOut(
        course_slug=course_slug,
        lesson_slug=lesson_slug,
        total=len(questions),
        questions=questions,
    )


async def _build_progress(
    session: AsyncSession, user_id: int, course_slug: str, lesson_slug: str
) -> LessonTestProgressOut:
    mcqs = await McqRepository(session).list_for_lesson(course_slug, lesson_slug)
    slugs = [m.slug for m in mcqs]
    stats = await McqStatsRepository(session).list_for_slugs(user_id, slugs)
    by_slug = {s.mcq_slug: s for s in stats}

    answered = 0
    correct = 0
    for slug in slugs:
        stat = by_slug.get(slug)
        if stat is None or stat.seen == 0:
            continue
        answered += 1
        if stat.last_correct:
            correct += 1

    result = await LessonTestResultRepository(session).get(
        user_id, course_slug, lesson_slug
    )
    best = result.best_score if result else 0
    return LessonTestProgressOut(
        total=len(slugs),
        answered=answered,
        correct=correct,
        attempts=result.attempts if result else 0,
        last_score=result.last_score if result else 0,
        best_score=best,
        passed=best >= TEST_PASS_THRESHOLD,
    )


async def get_lesson_progress(
    session: AsyncSession, user_id: int, course_slug: str, lesson_slug: str
) -> LessonTestProgressOut:
    await _ensure_lesson(session, course_slug, lesson_slug)
    return await _build_progress(session, user_id, course_slug, lesson_slug)


async def record_results(
    session: AsyncSession,
    user_id: int,
    course_slug: str,
    lesson_slug: str,
    items: list[tuple[str, bool]],
) -> LessonTestProgressOut:
    """Record a finished test. Always upserts per-MCQ ``mcq_stats``. Once every
    MCQ of the lesson has been answered at least once, records the lesson's
    **standing** score — computed from the user's *latest* answer to each MCQ
    (the ``mcq_stats`` union, not just this submission) — into
    ``lesson_test_results`` (drives the badge + dashboard). This means fixing a
    failed question in "review mistakes" mode (a subset submission) can complete
    the union and lift the lesson to passed. There is no inflation risk: the
    score is always over the **full** lesson MCQ set, so a subset can only raise
    it when the remaining questions were already correct. Unknown slugs are
    ignored. Commits once, then returns the refreshed progress."""
    await _ensure_lesson(session, course_slug, lesson_slug)
    mcq_repo = McqRepository(session)
    stats_repo = McqStatsRepository(session)

    valid = await mcq_repo.all_slugs()

    for slug, correct in items:
        if slug not in valid:
            continue
        await stats_repo.record(user_id=user_id, mcq_slug=slug, correct=correct)
    await session.flush()

    await _record_standing_score(session, user_id, course_slug, lesson_slug)

    await session.commit()
    return await _build_progress(session, user_id, course_slug, lesson_slug)


async def _record_standing_score(
    session: AsyncSession, user_id: int, course_slug: str, lesson_slug: str
) -> None:
    """Once every MCQ of the lesson has been answered at least once, record the
    standing score from the user's latest answer to each (the ``mcq_stats``
    union). No-op while any question of the lesson is still untouched. Flushes
    but does not commit — the caller owns the transaction."""
    mcq_repo = McqRepository(session)
    lesson_slugs = [
        m.slug for m in await mcq_repo.list_for_lesson(course_slug, lesson_slug)
    ]
    if not lesson_slugs:
        return
    stats = await McqStatsRepository(session).list_for_slugs(user_id, lesson_slugs)
    by_slug = {s.mcq_slug: s for s in stats}
    seen = [by_slug.get(s) for s in lesson_slugs]
    if not all(st is not None and st.seen > 0 for st in seen):
        return
    correct_count = sum(1 for st in seen if st.last_correct)
    score = round(100 * correct_count / len(lesson_slugs))
    await LessonTestResultRepository(session).record_full_run(
        user_id=user_id,
        course_slug=course_slug,
        lesson_slug=lesson_slug,
        score=score,
    )


async def tests_overview(session: AsyncSession, user_id: int) -> TestsOverviewOut:
    """Per-course + overall test status for the dashboard: of the lessons that
    have MCQ, how many this user has started / passed. Courses without any MCQ
    are omitted, so the overview grows naturally as more content is authored."""
    lessons = await McqRepository(session).lessons_with_mcq()
    results = await LessonTestResultRepository(session).list_for_user(user_id)
    by_key = {(r.course_slug, r.lesson_slug): r for r in results}

    # course_slug -> [total, passed, started]
    per_course: dict[str, list[int]] = {}
    order: list[str] = []
    for course_slug, lesson_slug in lessons:
        if course_slug not in per_course:
            per_course[course_slug] = [0, 0, 0]
            order.append(course_slug)
        agg = per_course[course_slug]
        agg[0] += 1  # total
        r = by_key.get((course_slug, lesson_slug))
        if r and r.attempts > 0:
            agg[2] += 1  # started
            if r.best_score >= TEST_PASS_THRESHOLD:
                agg[1] += 1  # passed

    courses = [
        TestsCourseOverviewOut(
            slug=slug,
            total=per_course[slug][0],
            passed=per_course[slug][1],
            started=per_course[slug][2],
        )
        for slug in order
    ]
    return TestsOverviewOut(
        total=sum(c.total for c in courses),
        passed=sum(c.passed for c in courses),
        started=sum(c.started for c in courses),
        courses=courses,
    )


# --------------------------------------------------------------------------- #
# Mixed test (the /tests section): any course, any count, really random.
# --------------------------------------------------------------------------- #
#: Selection strategies offered on the setup screen. `smart` weights by what the
#: user is weak at; `random` is deliberately *uniform* — when someone asks for a
#: random test they mean random, not "randomly what the algorithm thinks".
MIX_MODES = ("smart", "random", "weak", "mistakes")

#: Cap on one run — enough for a long session, small enough to stay one request.
MAX_MIX_COUNT = 100

#: Questions seen within this window are demoted in `smart` mode, so finishing a
#: test and immediately starting another doesn't replay the same ones.
RECENT_MINUTES = 30


def filter_pool(
    candidates: Sequence[tuple[int, str, str]],
    stats: Mapping[str, "McqStat"],
    mode: str,
) -> list[tuple[int, str, str]]:
    """The candidates a mode is allowed to draw from. `smart` and `random` use
    everything (they differ only in weighting); `weak` and `mistakes` narrow it.
    Split out from `pick_mix` so the caller can report the *real* pool size."""
    if mode == "mistakes":
        return [
            c for c in candidates
            if (s := stats.get(c[1])) is not None and s.seen > 0 and not s.last_correct
        ]
    if mode == "weak":
        return [
            c for c in candidates
            if (s := stats.get(c[1])) is None or s.seen == 0 or not s.last_correct
        ]
    return list(candidates)


def pick_mix(
    candidates: Sequence[tuple[int, str, str]],
    stats: Mapping[str, "McqStat"],
    *,
    mode: str,
    count: int,
    rng: random.Random,
    now: datetime | None = None,
) -> list[int]:
    """Choose which MCQ ids make up one run. Pure apart from ``rng``, so the
    weighting is unit-testable with a seeded Random.

    ``candidates`` is ``(id, slug, course_slug)``; ``stats`` maps slug -> the
    user's :class:`McqStat`. Returns at most ``count`` ids.

    - ``random``   — uniform sample. No weighting at all.
    - ``mistakes`` — only questions whose last answer was wrong.
    - ``weak``     — never-seen + last-wrong (what you don't know yet).
    - ``smart``    — weighted draw over everything: unseen highest, then wrong,
      then shaky, mastered lowest; recently-seen demoted.

    Every mode spreads the result across courses (round-robin over the shuffled
    per-course buckets) so a 20-question mix over 5 topics isn't 18 from one.
    """
    now = now or _utcnow()
    count = max(1, min(count, MAX_MIX_COUNT))

    def weight(slug: str) -> float:
        stat = stats.get(slug)
        if stat is None or stat.seen == 0:
            w = 6.0  # never answered — the most useful thing to ask
        elif not stat.last_correct:
            w = 5.0  # got it wrong last time
        elif stat.correct < 2:
            w = 2.0  # right once; not proven yet
        else:
            w = 0.6  # mastered — keep a trickle for retention
        if stat is not None and (now - stat.last_seen_at) < timedelta(
            minutes=RECENT_MINUTES
        ):
            w *= 0.25  # just saw it — don't repeat within a session
        return w

    pool = filter_pool(candidates, stats, mode)
    if not pool:
        return []

    if mode == "smart":
        chosen = _weighted_sample(pool, [weight(c[1]) for c in pool], count, rng)
    else:
        chosen = rng.sample(pool, min(count, len(pool)))

    return _round_robin_by_course(chosen, rng)


def _weighted_sample(
    pool: Sequence[tuple[int, str, str]],
    weights: Sequence[float],
    count: int,
    rng: random.Random,
) -> list[tuple[int, str, str]]:
    """Weighted sampling *without replacement* (Efraimidis–Spirakis): give each
    item the key ``random ** (1/weight)`` and keep the largest ``count``. One
    pass, no re-normalising after each draw."""
    keyed = [
        (rng.random() ** (1.0 / max(w, 1e-6)), item) for item, w in zip(pool, weights)
    ]
    keyed.sort(key=lambda kv: kv[0], reverse=True)
    return [item for _, item in keyed[:count]]


def _round_robin_by_course(
    chosen: Sequence[tuple[int, str, str]], rng: random.Random
) -> list[int]:
    """Interleave the chosen questions across courses so consecutive questions
    tend to jump topic — a mixed test should *feel* mixed."""
    buckets: dict[str, list[tuple[int, str, str]]] = {}
    for item in chosen:
        buckets.setdefault(item[2], []).append(item)
    for items in buckets.values():
        rng.shuffle(items)

    order = list(buckets)
    rng.shuffle(order)
    out: list[int] = []
    while order:
        for course in list(order):
            items = buckets[course]
            out.append(items.pop()[0])
            if not items:
                order.remove(course)
    return out


async def mix_topics(session: AsyncSession, user_id: int) -> TestTopicsOut:
    """Selectable topics (= courses) with their question counts and this user's
    answered/weak tallies — everything the setup screen needs in one request."""
    counts = await McqRepository(session).counts_by_course()
    stats = await McqStatsRepository(session).list_for_user(user_id)
    by_slug = {s.mcq_slug: s for s in stats}

    # course_slug -> per-course tallies, in catalog order (counts_by_course).
    titles: dict[str, str] = {}
    per_bank: dict[str, dict[str, int]] = {}
    order: list[str] = []
    for course_slug, title, bank, n in counts:
        if course_slug not in per_bank:
            per_bank[course_slug] = {}
            titles[course_slug] = title
            order.append(course_slug)
        per_bank[course_slug][bank] = n

    # answered/weak need the slugs themselves, not just counts.
    candidates = await McqRepository(session).mix_candidates(
        course_slugs=None, banks=(BANK_LESSON, BANK_EXAM)
    )
    answered: dict[str, int] = {}
    weak: dict[str, int] = {}
    for _id, slug, course_slug in candidates:
        stat = by_slug.get(slug)
        if stat is None or stat.seen == 0:
            continue
        answered[course_slug] = answered.get(course_slug, 0) + 1
        if not stat.last_correct:
            weak[course_slug] = weak.get(course_slug, 0) + 1

    topics = [
        TestTopicOut(
            slug=slug,
            title=titles[slug],
            lesson_total=per_bank[slug].get(BANK_LESSON, 0),
            exam_total=per_bank[slug].get(BANK_EXAM, 0),
            total=sum(per_bank[slug].values()),
            answered=answered.get(slug, 0),
            weak=weak.get(slug, 0),
        )
        for slug in order
    ]
    return TestTopicsOut(
        topics=topics,
        total=sum(t.total for t in topics),
        lesson_total=sum(t.lesson_total for t in topics),
        exam_total=sum(t.exam_total for t in topics),
        answered=sum(t.answered for t in topics),
        weak=sum(t.weak for t in topics),
    )


async def generate_mix(
    session: AsyncSession,
    user_id: int,
    *,
    courses: Sequence[str] | None = None,
    banks: Sequence[str] = (BANK_LESSON, BANK_EXAM),
    mode: str = "smart",
    count: int = 20,
) -> TestMixOut:
    """Build one mixed test. Selection happens server-side (unlike the glossary
    quiz, which generates on the client) because the full MCQ bank is ~800 KB of
    JSON — far too much to ship just to keep 20 questions."""
    if mode not in MIX_MODES:
        raise HTTPException(status_code=422, detail="Unknown mode")
    banks = [b for b in banks if b in (BANK_LESSON, BANK_EXAM)] or [BANK_LESSON]

    repo = McqRepository(session)
    candidates = await repo.mix_candidates(course_slugs=courses, banks=banks)
    stats = await McqStatsRepository(session).list_for_user(user_id)
    by_slug = {s.mcq_slug: s for s in stats}

    # `pool` is what the *mode* can actually draw from, not the raw filter match —
    # for "mistakes" those are very different numbers, and the UI shows it.
    pool = len(filter_pool(candidates, by_slug, mode))
    ids = pick_mix(
        candidates,
        by_slug,
        mode=mode,
        count=count,
        rng=random.Random(),
    )
    rows = await repo.list_by_ids(ids)
    by_id = {row[0].id: row for row in rows}

    questions = [
        _to_out(
            mcq,
            course_slug=course_slug,
            course_title=course_title,
            lesson_slug=lesson_slug,
            lesson_title=lesson_title,
        )
        for mcq_id in ids
        if (row := by_id.get(mcq_id)) is not None
        for mcq, course_slug, course_title, lesson_slug, lesson_title in [row]
    ]
    return TestMixOut(count=len(questions), pool=pool, questions=questions)


async def record_mix_results(
    session: AsyncSession, user_id: int, items: list[tuple[str, bool]]
) -> MixResultOut:
    """Record a finished mixed run. Per-MCQ stats are written exactly as for a
    lesson test, then every lesson the run touched has its standing score
    recomputed — so answering a lesson's last unseen question here can complete
    that lesson's test. Exam-bank answers never reach a lesson score (they aren't
    part of any lesson's set). Unknown slugs are ignored."""
    stats_repo = McqStatsRepository(session)
    valid = await McqRepository(session).all_slugs()

    recorded = 0
    correct_count = 0
    touched: list[str] = []
    for slug, correct in items:
        if slug not in valid:
            continue
        await stats_repo.record(user_id=user_id, mcq_slug=slug, correct=correct)
        recorded += 1
        correct_count += 1 if correct else 0
        touched.append(slug)
    await session.flush()

    for course_slug, lesson_slug in await McqRepository(session).lessons_for_slugs(
        touched
    ):
        await _record_standing_score(session, user_id, course_slug, lesson_slug)

    await session.commit()
    return MixResultOut(recorded=recorded, correct=correct_count)
