"""Idempotent seeding of parsed content into the DB + markdown registry.

Markdown/JSON under ``content/`` is the source of truth; the DB tables are a
queryable mirror. Re-running ``seed_content`` upserts courses/lessons/concepts by
slug and fully replaces each concept's question set (content is authoritative),
so it is safe to run on every startup.
"""
from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.content import registry
from app.content.loader import ContentBundle, CourseData, LessonData, load_content
from app.models import Concept, Course, GlossaryTerm, Lesson, McqQuestion, Question


async def seed_from_dir(session: AsyncSession, content_dir: str | None = None) -> int:
    """Load content from disk and seed it. Returns the number of courses seeded."""
    settings = get_settings()
    bundle = load_content(content_dir or settings.content_dir)
    await seed_content(session, bundle)
    return len(bundle.courses)


async def seed_content(session: AsyncSession, bundle: ContentBundle) -> None:
    registry.clear()
    for course_data in bundle.courses:
        course = await _upsert_course(session, course_data)
        for lesson_data in course_data.lessons:
            await _upsert_lesson(session, course, course_data, lesson_data)
    await _seed_glossary(session, bundle)
    # In-memory only (no user state, no search) — served by GET /api/roadmap.
    registry.set_roadmap(bundle.roadmap)
    await session.commit()


async def _seed_glossary(session: AsyncSession, bundle: ContentBundle) -> None:
    """Replace the glossary wholesale — content is authoritative, no user state
    references these rows, so a clean re-insert keeps it simple and idempotent."""
    await session.execute(delete(GlossaryTerm))
    for term in bundle.glossary_terms:
        session.add(
            GlossaryTerm(
                slug=term.slug,
                term=term.term,
                category=term.category,
                short_md=term.short_md,
                kind=term.kind,
                order_index=term.order_index,
                aliases=json.dumps(term.aliases, ensure_ascii=False),
                links=json.dumps(
                    [
                        {
                            "course_slug": ln.course_slug,
                            "lesson_slug": ln.lesson_slug,
                            "anchor": ln.anchor,
                        }
                        for ln in term.links
                    ],
                    ensure_ascii=False,
                ),
            )
        )
    await session.flush()


async def _upsert_course(session: AsyncSession, data: CourseData) -> Course:
    course = (
        await session.execute(select(Course).where(Course.slug == data.slug))
    ).scalar_one_or_none()
    if course is None:
        course = Course(slug=data.slug)
        session.add(course)
    course.title = data.title
    course.description = data.description
    course.order_index = data.order_index
    course.is_published = True
    await session.flush()
    return course


async def _upsert_lesson(
    session: AsyncSession,
    course: Course,
    course_data: CourseData,
    data: LessonData,
) -> None:
    lesson = (
        await session.execute(
            select(Lesson).where(
                Lesson.course_id == course.id, Lesson.slug == data.slug
            )
        )
    ).scalar_one_or_none()
    if lesson is None:
        lesson = Lesson(course_id=course.id, slug=data.slug)
        session.add(lesson)
    lesson.title = data.title
    lesson.content_path = data.content_path
    lesson.order_index = data.order_index
    lesson.duration_minutes = data.duration_minutes
    await session.flush()

    # Cache markdown for fast serving + LLM grounding.
    registry.set_lesson_text(course_data.slug, data.slug, data.markdown)

    for concept_data in data.concepts:
        concept = (
            await session.execute(
                select(Concept).where(
                    Concept.lesson_id == lesson.id, Concept.slug == concept_data.slug
                )
            )
        ).scalar_one_or_none()
        if concept is None:
            concept = Concept(lesson_id=lesson.id, slug=concept_data.slug)
            session.add(concept)
        concept.title = concept_data.title
        concept.anchor = concept_data.anchor
        concept.order_index = concept_data.order_index
        await session.flush()

        # Questions: content is authoritative — replace the concept's set.
        await session.execute(
            delete(Question).where(Question.concept_id == concept.id)
        )
        for q in concept_data.questions:
            session.add(
                Question(
                    concept_id=concept.id,
                    text=q.text,
                    reference_answer=q.reference_answer,
                    difficulty=q.difficulty,
                    order_index=q.order_index,
                )
            )
        await session.flush()

        # MCQ self-test bank: content is authoritative — replace the set.
        await session.execute(
            delete(McqQuestion).where(McqQuestion.concept_id == concept.id)
        )
        for m in concept_data.mcqs:
            session.add(
                McqQuestion(
                    slug=m.slug,
                    concept_id=concept.id,
                    type=m.type,
                    text=m.text,
                    options=json.dumps(m.options, ensure_ascii=False),
                    correct_index=m.correct_index,
                    explanation_md=m.explanation_md,
                    difficulty=m.difficulty,
                    order_index=m.order_index,
                )
            )
        await session.flush()
