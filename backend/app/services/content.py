"""Content service: course listing + course/lesson detail.

Pure DB reads (no LLM). Metadata comes from the content-mirror tables via
repositories; lesson markdown bodies come from the in-memory registry. Endpoints
stay thin — they just call these and return the schema.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import registry
from app.repositories import CourseRepository, LessonRepository
from app.schemas import (
    ConceptOut,
    CourseDetail,
    CourseSummary,
    LessonDetail,
    LessonSummary,
)


async def list_courses(session: AsyncSession) -> list[CourseSummary]:
    rows = await CourseRepository(session).list_published_with_lesson_counts()
    return [
        CourseSummary(
            slug=course.slug,
            title=course.title,
            description=course.description,
            order=course.order_index,
            lesson_count=n,
        )
        for course, n in rows
    ]


async def get_course(session: AsyncSession, course_slug: str) -> CourseDetail:
    course = await CourseRepository(session).get_by_slug_with_lessons_concepts(
        course_slug
    )
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


async def get_lesson(
    session: AsyncSession, course_slug: str, lesson_slug: str
) -> LessonDetail:
    course = await CourseRepository(session).get_by_slug(course_slug)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    lesson = await LessonRepository(session).get_detail(course.id, lesson_slug)
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
