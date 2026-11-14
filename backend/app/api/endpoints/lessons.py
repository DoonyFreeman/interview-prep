"""Lesson detail endpoint: markdown body + concepts, via the content service."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, has_account_bound_token
from app.database import get_session
from app.models import User
from app.schemas import LessonDetail
from app.services import content, private_hr

router = APIRouter()


@router.get(
    "/courses/{course_slug}/lessons/{lesson_slug}",
    response_model=LessonDetail,
)
async def get_lesson(
    course_slug: str,
    lesson_slug: str,
    session: AsyncSession = Depends(get_session),
):
    return await content.get_lesson(session, course_slug, lesson_slug)


@router.get("/hr-screening/answers/{lesson_slug}", response_model=private_hr.AnswerGroups)
def get_private_hr_answers(
    lesson_slug: str,
    response: Response,
    user: User = Depends(get_current_user),
    account_bound: bool = Depends(has_account_bound_token),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    if not account_bound:
        return {}
    return private_hr.get_answers(user.id, user.email, user.created_at, lesson_slug)
