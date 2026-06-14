"""Lesson MCQ self-test service: serve a lesson's closed questions, record
results, roll up the per-lesson "test score", and aggregate a tests overview.

This is the no-LLM counterpart to ``quiz.py``. Serving is a pure DB read; unlike
the open quiz it deliberately includes the correct option + explanation so the
client can grade instantly (the options are visible anyway and there is no LLM
to protect).

Two kinds of user-state, kept separate by design:
- ``mcq_stats`` (per MCQ): seen/correct/last_correct — for per-question review.
- ``lesson_test_results`` (per lesson): best/last score over **full** runs — the
  source of the lesson badge and the dashboard "tests passed" indicator. A
  "review mistakes" run answers only a subset and must not inflate the best
  score, so only a run that covers every MCQ of the lesson updates it.

None of this touches SM-2 mastery: an MCQ guess never moves spaced repetition.
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import McqQuestion
from app.repositories import (
    LessonRepository,
    LessonTestResultRepository,
    McqRepository,
    McqStatsRepository,
)
from app.schemas import (
    LessonTestOut,
    LessonTestProgressOut,
    McqQuestionOut,
    TestsCourseOverviewOut,
    TestsOverviewOut,
)

#: A lesson test counts as "passed" once the best full run reaches this score.
TEST_PASS_THRESHOLD = 80


def _to_out(mcq: McqQuestion) -> McqQuestionOut:
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
    """Record a finished test. Always upserts per-MCQ ``mcq_stats``. If the run
    is **full** (every MCQ of the lesson answered), also records the run's score
    into ``lesson_test_results`` (drives the badge + dashboard). Unknown slugs
    are ignored. Commits once, then returns the refreshed progress."""
    await _ensure_lesson(session, course_slug, lesson_slug)
    mcq_repo = McqRepository(session)
    stats_repo = McqStatsRepository(session)

    lesson_slugs = {m.slug for m in await mcq_repo.list_for_lesson(course_slug, lesson_slug)}
    valid = await mcq_repo.all_slugs()

    posted: dict[str, bool] = {}
    for slug, correct in items:
        if slug not in valid:
            continue
        await stats_repo.record(user_id=user_id, mcq_slug=slug, correct=correct)
        posted[slug] = correct

    # Full run = answered every MCQ of this lesson → record the lesson score.
    answered_lesson = {s for s in posted if s in lesson_slugs}
    if lesson_slugs and answered_lesson >= lesson_slugs:
        correct_count = sum(1 for s in lesson_slugs if posted.get(s))
        score = round(100 * correct_count / len(lesson_slugs))
        await LessonTestResultRepository(session).record_full_run(
            user_id=user_id,
            course_slug=course_slug,
            lesson_slug=lesson_slug,
            score=score,
        )

    await session.commit()
    return await _build_progress(session, user_id, course_slug, lesson_slug)


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
