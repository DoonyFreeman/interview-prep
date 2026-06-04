"""Lesson detail endpoint: markdown body (from the in-memory registry) + concepts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.content import registry
from app.database import get_session
from app.models import Concept, Course, Lesson
from app.schemas import ConceptOut, LessonDetail

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
    course = (
        await session.execute(select(Course).where(Course.slug == course_slug))
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lesson = (
        await session.execute(
            select(Lesson)
            .where(Lesson.course_id == course.id, Lesson.slug == lesson_slug)
            .options(selectinload(Lesson.concepts).selectinload(Concept.questions))
        )
    ).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    markdown = registry.get_lesson_text(course_slug, lesson_slug) or ""
    concepts = [
        ConceptOut(
            slug=c.slug,
            title=c.title,
            anchor=c.anchor,
            order=c.order_index,
            question_count=len(c.questions),
        )
        for c in sorted(lesson.concepts, key=lambda x: x.order_index)
    ]
    return LessonDetail(
        slug=lesson.slug,
        title=lesson.title,
        course_slug=course_slug,
        duration_minutes=lesson.duration_minutes,
        markdown=markdown,
        concepts=concepts,
    )
