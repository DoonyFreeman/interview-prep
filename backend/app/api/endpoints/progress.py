"""Progress endpoints (auth-gated): overview, spaced-repetition review queue,
lesson view/completion.

Mastery itself is advanced as a side effect of evaluating answers
(``quiz.evaluate_answer``); these routes read that state back and let the client
mark lessons as viewed/completed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.models import User
from app.schemas import (
    LessonProgressIn,
    ProgressOverviewOut,
    QuestionsProgressOut,
    ReviewQueueOut,
)
from app.services import progress

router = APIRouter()


@router.get("/progress", response_model=ProgressOverviewOut)
async def overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Per-course / lesson / concept mastery rollup for the current user."""
    return await progress.get_overview(session, user_id=user.id)


@router.get("/progress/questions", response_model=QuestionsProgressOut)
async def questions_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Per-course / lesson: questions answered vs. total ('what's left')."""
    return await progress.get_questions_overview(session, user_id=user.id)


@router.get("/progress/review", response_model=ReviewQueueOut)
async def review_queue(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Concepts due for review now (SM-2 ``due_at`` has passed), soonest first."""
    return await progress.get_review_queue(session, user_id=user.id)


@router.post(
    "/progress/courses/{course_slug}/lessons/{lesson_slug}",
    status_code=204,
)
async def mark_lesson(
    course_slug: str,
    lesson_slug: str,
    data: LessonProgressIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record that the user viewed (and optionally completed) a lesson."""
    await progress.touch_lesson_progress(
        session,
        user_id=user.id,
        course_slug=course_slug,
        lesson_slug=lesson_slug,
        completed=data.completed,
    )
