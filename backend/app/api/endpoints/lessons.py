"""Lesson detail endpoint: markdown body + concepts, via the content service."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import LessonDetail
from app.services import content

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
