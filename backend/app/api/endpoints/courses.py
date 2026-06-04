"""Course listing endpoints (pure DB reads, no LLM)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Course, Lesson
from app.schemas import CourseDetail, CourseSummary, LessonSummary

router = APIRouter()


@router.get("/courses", response_model=list[CourseSummary])
async def list_courses(session: AsyncSession = Depends(get_session)):
    lesson_count = (
        select(Lesson.course_id, func.count(Lesson.id).label("n"))
        .group_by(Lesson.course_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Course, func.coalesce(lesson_count.c.n, 0))
            .outerjoin(lesson_count, lesson_count.c.course_id == Course.id)
            .where(Course.is_published.is_(True))
            .order_by(Course.order_index)
        )
    ).all()
    return [
        CourseSummary(
            slug=c.slug,
            title=c.title,
            description=c.description,
            order=c.order_index,
            lesson_count=n,
        )
        for c, n in rows
    ]


@router.get("/courses/{course_slug}", response_model=CourseDetail)
async def get_course(course_slug: str, session: AsyncSession = Depends(get_session)):
    course = (
        await session.execute(
            select(Course)
            .where(Course.slug == course_slug)
            .options(selectinload(Course.lessons).selectinload(Lesson.concepts))
        )
    ).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = [
        LessonSummary(
            slug=lesson.slug,
            title=lesson.title,
            order=lesson.order_index,
            duration_minutes=lesson.duration_minutes,
            concept_count=len(lesson.concepts),
        )
        for lesson in sorted(course.lessons, key=lambda x: x.order_index)
    ]
    return CourseDetail(
        slug=course.slug,
        title=course.title,
        description=course.description,
        order=course.order_index,
        lessons=lessons,
    )
