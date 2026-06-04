"""Progress + spaced-repetition state (DB-facing side of SM-2).

Each scored attempt updates the mastery of the question's concept
(:func:`update_mastery`); the review queue surfaces concepts whose ``due_at`` has
passed (:func:`get_review_queue`); the overview rolls mastery up per course /
lesson (:func:`get_overview`). Lesson view/completion is tracked separately
(:func:`touch_lesson_progress`).

All timestamps are timezone-aware UTC (matching ``models._utcnow``) so the ISO
strings SQLite stores stay lexically comparable in ``due_at`` filters.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Concept,
    ConceptMastery,
    Course,
    Lesson,
    LessonProgress,
    Question,
    _utcnow,
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
    mastery = (
        await session.execute(
            select(ConceptMastery).where(
                ConceptMastery.user_id == user_id,
                ConceptMastery.concept_id == concept_id,
            )
        )
    ).scalar_one_or_none()
    if mastery is None:
        mastery = ConceptMastery(
            user_id=user_id,
            concept_id=concept_id,
            ease=DEFAULT_EASE,
            interval_days=0.0,
            reps=0,
        )
        session.add(mastery)

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
    rows = (
        await session.execute(
            select(ConceptMastery, Concept, Lesson, Course)
            .join(Concept, ConceptMastery.concept_id == Concept.id)
            .join(Lesson, Concept.lesson_id == Lesson.id)
            .join(Course, Lesson.course_id == Course.id)
            .where(
                ConceptMastery.user_id == user_id,
                ConceptMastery.due_at <= now,
            )
            .order_by(ConceptMastery.due_at.asc())
            .limit(limit)
        )
    ).all()

    items: list[ReviewItem] = []
    for mastery, concept, lesson, course in rows:
        question_id = (
            await session.execute(
                select(func.min(Question.id)).where(Question.concept_id == concept.id)
            )
        ).scalar()
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

    courses = (
        (
            await session.execute(
                select(Course)
                .where(Course.is_published.is_(True))
                .options(
                    selectinload(Course.lessons).selectinload(Lesson.concepts)
                )
                .order_by(Course.order_index)
            )
        )
        .scalars()
        .all()
    )

    mastery_by_concept = {
        m.concept_id: m
        for m in (
            await session.execute(
                select(ConceptMastery).where(ConceptMastery.user_id == user_id)
            )
        )
        .scalars()
        .all()
    }
    completed_lessons = {
        lp.lesson_id
        for lp in (
            await session.execute(
                select(LessonProgress).where(
                    LessonProgress.user_id == user_id,
                    LessonProgress.completed.is_(True),
                )
            )
        )
        .scalars()
        .all()
    }

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
    lesson = (
        await session.execute(
            select(Lesson)
            .join(Course, Lesson.course_id == Course.id)
            .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
        )
    ).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    progress = (
        await session.execute(
            select(LessonProgress).where(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id == lesson.id,
            )
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = LessonProgress(user_id=user_id, lesson_id=lesson.id)
        session.add(progress)
    progress.last_viewed_at = now
    if completed:
        progress.completed = True
    await session.commit()
    await session.refresh(progress)
    return progress
