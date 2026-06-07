"""Repository-layer unit tests against the in-memory seeded DB.

These exercise the data layer directly (no HTTP), covering the methods services
rely on: user lookup/creation, question context loading, due mastery selection,
completed-lesson lookup, and the course listing rollup.
"""
from __future__ import annotations

from datetime import timedelta

import pytest_asyncio

from app.content.seed import seed_from_dir
from app.models import ConceptMastery, _utcnow
from app.repositories import (
    ConceptMasteryRepository,
    ConceptRepository,
    CourseRepository,
    LessonProgressRepository,
    QuestionRepository,
    UserRepository,
)


@pytest_asyncio.fixture
async def session(Session):
    async with Session() as s:
        await seed_from_dir(s)
    async with Session() as s:
        yield s


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
async def test_user_create_and_lookup(session):
    repo = UserRepository(session)
    user = await repo.create(email="r@e.com", password_hash="h", display_name="R")
    await session.commit()

    assert (await repo.get_by_email("r@e.com")).id == user.id
    assert (await repo.get_by_id(user.id)).email == "r@e.com"
    assert await repo.get_by_email("missing@e.com") is None


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #
async def test_question_get_with_context_loads_relations(session):
    concept = await ConceptRepository(session).get_by_slug("gil-release")
    qid = await QuestionRepository(session).min_id_for_concept(concept.id)

    question = await QuestionRepository(session).get_with_context(qid)
    # concept -> lesson -> course are eagerly available without extra queries.
    assert question.concept.slug == "gil-release"
    assert question.concept.lesson.slug == "gil"
    assert question.concept.lesson.course.slug == "python-core"
    # The reference answer lives here (server-side only).
    assert question.reference_answer


async def test_question_get_with_context_missing_returns_none(session):
    assert await QuestionRepository(session).get_with_context(999999) is None


async def test_course_listing_counts_lessons(session):
    rows = await CourseRepository(session).list_published_with_lesson_counts()
    assert len(rows) >= 20  # full Phase 6 curriculum
    py = next((row for row in rows if row[0].slug == "python-core"), None)
    assert py is not None
    course, lesson_count = py
    assert lesson_count >= 1


# --------------------------------------------------------------------------- #
# Mastery / progress
# --------------------------------------------------------------------------- #
async def test_due_for_user_returns_only_overdue(session):
    user = await UserRepository(session).create(
        email="d@e.com", password_hash="h", display_name="D"
    )
    await session.commit()

    overdue_cid = (await ConceptRepository(session).get_by_slug("what-is-gil")).id
    future_cid = (await ConceptRepository(session).get_by_slug("gil-release")).id
    now = _utcnow()
    session.add(
        ConceptMastery(
            user_id=user.id,
            concept_id=overdue_cid,
            ease=2.5,
            interval_days=1.0,
            reps=1,
            last_score=40,
            due_at=now - timedelta(days=1),
        )
    )
    session.add(
        ConceptMastery(
            user_id=user.id,
            concept_id=future_cid,
            ease=2.5,
            interval_days=6.0,
            reps=2,
            last_score=90,
            due_at=now + timedelta(days=6),
        )
    )
    await session.commit()

    rows = await ConceptMasteryRepository(session).due_for_user(user.id, now, limit=50)
    assert len(rows) == 1
    mastery, concept, lesson, course = rows[0]
    assert concept.id == overdue_cid
    assert course.slug == "python-core"


async def test_completed_lesson_ids(session):
    from app.models import Lesson
    from sqlalchemy import select

    user = await UserRepository(session).create(
        email="c@e.com", password_hash="h", display_name="C"
    )
    await session.commit()
    # Pick a specific lesson by slug — the seed now holds many lessons, so a bare
    # select(Lesson.id) would raise MultipleResultsFound.
    lesson_id = (
        await session.execute(select(Lesson.id).where(Lesson.slug == "gil"))
    ).scalar_one()

    repo = LessonProgressRepository(session)
    assert await repo.completed_lesson_ids(user.id) == set()

    progress = repo.create(user_id=user.id, lesson_id=lesson_id)
    progress.completed = True
    await session.commit()

    assert await repo.completed_lesson_ids(user.id) == {lesson_id}
