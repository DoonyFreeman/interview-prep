"""Progress + spaced-repetition state (DB-facing side of SM-2).

Each scored attempt updates the mastery of the question's concept
(:func:`update_mastery`); the review queue surfaces concepts whose ``due_at`` has
passed (:func:`get_review_queue`); the overview rolls mastery up per course /
lesson (:func:`get_overview`). Lesson view/completion is tracked separately
(:func:`touch_lesson_progress`).

All DB access goes through repositories; this module holds the business rules
(SM-2 step, mastered threshold) and the ORM→schema mapping. All timestamps are
timezone-aware-free UTC (``models._utcnow``) so SQLite's lexical ``due_at``
filters stay correct.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConceptMastery, LessonProgress, _utcnow
from app.repositories import (
    ConceptMasteryRepository,
    CourseRepository,
    LessonProgressRepository,
    LessonRepository,
    QuestionRepository,
)
from app.schemas import (
    ConceptProgressOut,
    CourseProgressOut,
    LessonProgressOut,
    MasteryOut,
    ProgressOverviewOut,
    ReviewItem,
    ReviewQueueOut,
)
from app.services.sm2 import DEFAULT_EASE, SM2State, score_to_quality, sm2_update

# A concept counts as "mastered" once it has survived a couple of successful
# reviews at a high score — enough that SM-2 has pushed its interval out.
MASTERED_MIN_REPS = 2
MASTERED_MIN_SCORE = 80


def _is_mastered(reps: int, last_score: int) -> bool:
    return reps >= MASTERED_MIN_REPS and last_score >= MASTERED_MIN_SCORE


# --------------------------------------------------------------------------- #
# Mastery update (called from quiz.evaluate_answer, same transaction)
# --------------------------------------------------------------------------- #
async def update_mastery(
    session: AsyncSession,
    *,
    user_id: int,
    concept_id: int,
    score: int,
    now: datetime | None = None,
) -> ConceptMastery:
    """Apply one SM-2 step to the (user, concept) mastery row, creating it if new.

    Flushes but does not commit — the caller owns the transaction.
    """
    now = now or _utcnow()
    repo = ConceptMasteryRepository(session)
    mastery = await repo.get(user_id, concept_id)
    if mastery is None:
        mastery = repo.create(
            user_id=user_id,
            concept_id=concept_id,
            ease=DEFAULT_EASE,
            interval_days=0.0,
            reps=0,
        )

    new = sm2_update(
        SM2State(mastery.ease, mastery.interval_days, mastery.reps),
        score_to_quality(score),
    )
    mastery.ease = new.ease
    mastery.interval_days = new.interval_days
    mastery.reps = new.reps
    mastery.last_score = score
    mastery.due_at = now + timedelta(days=new.interval_days)
    mastery.updated_at = now
    await session.flush()
    return mastery


def mastery_to_out(mastery: ConceptMastery, now: datetime | None = None) -> MasteryOut:
    now = now or _utcnow()
    return MasteryOut(
        reps=mastery.reps,
        ease=round(mastery.ease, 3),
        interval_days=mastery.interval_days,
        last_score=mastery.last_score,
        due_at=mastery.due_at,
        due=mastery.due_at <= now,
    )


# --------------------------------------------------------------------------- #
# Review queue
# --------------------------------------------------------------------------- #
async def get_review_queue(
    session: AsyncSession,
    *,
    user_id: int,
    now: datetime | None = None,
    limit: int = 50,
) -> ReviewQueueOut:
    """Concepts whose ``due_at`` has passed, soonest-due first, with a question."""
    now = now or _utcnow()
    mastery_repo = ConceptMasteryRepository(session)
    question_repo = QuestionRepository(session)

    rows = await mastery_repo.due_for_user(user_id, now, limit)
    items: list[ReviewItem] = []
    for mastery, concept, lesson, course in rows:
        question_id = await question_repo.min_id_for_concept(concept.id)
        items.append(
            ReviewItem(
                concept_slug=concept.slug,
                concept_title=concept.title,
                course_slug=course.slug,
                lesson_slug=lesson.slug,
                anchor=concept.anchor,
                last_score=mastery.last_score,
                reps=mastery.reps,
                due_at=mastery.due_at,
                question_id=question_id,
            )
        )
    return ReviewQueueOut(count=len(items), items=items)


# --------------------------------------------------------------------------- #
# Overview (per course / lesson / concept rollup)
# --------------------------------------------------------------------------- #
async def get_overview(
    session: AsyncSession, *, user_id: int, now: datetime | None = None
) -> ProgressOverviewOut:
    now = now or _utcnow()

    courses = await CourseRepository(session).list_published_with_lessons_concepts()
    mastery_by_concept = {
        m.concept_id: m
        for m in await ConceptMasteryRepository(session).list_for_user(user_id)
    }
    completed_lessons = await LessonProgressRepository(session).completed_lesson_ids(
        user_id
    )

    course_outs: list[CourseProgressOut] = []
    g_total = g_attempted = g_mastered = g_due = 0

    for course in courses:
        c_total = c_attempted = c_mastered = c_due = 0
        lesson_outs: list[LessonProgressOut] = []

        for lesson in sorted(course.lessons, key=lambda x: x.order_index):
            concept_outs: list[ConceptProgressOut] = []
            l_attempted = l_mastered = l_due = 0

            for concept in sorted(lesson.concepts, key=lambda x: x.order_index):
                m = mastery_by_concept.get(concept.id)
                attempted = m is not None
                reps = m.reps if m else 0
                last_score = m.last_score if m else 0
                due_at = m.due_at if m else None
                is_due = bool(m and m.due_at <= now)
                mastered = _is_mastered(reps, last_score)

                l_attempted += int(attempted)
                l_mastered += int(mastered)
                l_due += int(is_due)

                concept_outs.append(
                    ConceptProgressOut(
                        slug=concept.slug,
                        title=concept.title,
                        anchor=concept.anchor,
                        attempted=attempted,
                        mastered=mastered,
                        reps=reps,
                        last_score=last_score,
                        due_at=due_at,
                        due=is_due,
                    )
                )

            l_total = len(concept_outs)
            lesson_outs.append(
                LessonProgressOut(
                    slug=lesson.slug,
                    title=lesson.title,
                    completed=lesson.id in completed_lessons,
                    total_concepts=l_total,
                    attempted_concepts=l_attempted,
                    mastered_concepts=l_mastered,
                    due_concepts=l_due,
                    concepts=concept_outs,
                )
            )
            c_total += l_total
            c_attempted += l_attempted
            c_mastered += l_mastered
            c_due += l_due

        course_outs.append(
            CourseProgressOut(
                slug=course.slug,
                title=course.title,
                total_concepts=c_total,
                attempted_concepts=c_attempted,
                mastered_concepts=c_mastered,
                due_concepts=c_due,
                lessons=lesson_outs,
            )
        )
        g_total += c_total
        g_attempted += c_attempted
        g_mastered += c_mastered
        g_due += c_due

    return ProgressOverviewOut(
        total_concepts=g_total,
        attempted_concepts=g_attempted,
        mastered_concepts=g_mastered,
        due_concepts=g_due,
        courses=course_outs,
    )


# --------------------------------------------------------------------------- #
# Lesson view / completion
# --------------------------------------------------------------------------- #
async def touch_lesson_progress(
    session: AsyncSession,
    *,
    user_id: int,
    course_slug: str,
    lesson_slug: str,
    completed: bool,
    now: datetime | None = None,
) -> LessonProgress:
    """Upsert the (user, lesson) progress row: bump last-viewed, set completed."""
    now = now or _utcnow()
    lesson = await LessonRepository(session).get_by_slugs(course_slug, lesson_slug)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    repo = LessonProgressRepository(session)
    progress = await repo.get(user_id, lesson.id)
    if progress is None:
        progress = repo.create(user_id=user_id, lesson_id=lesson.id)
    progress.last_viewed_at = now
    if completed:
        progress.completed = True
    await session.commit()
    await session.refresh(progress)
    return progress
