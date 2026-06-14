"""Repositories for the lesson MCQ self-test + per-user stats."""
from __future__ import annotations

from datetime import datetime
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import (
    Concept,
    Course,
    Lesson,
    LessonTestResult,
    McqQuestion,
    McqStat,
    _utcnow,
)
from app.repositories.base import BaseRepository


class McqRepository(BaseRepository[McqQuestion]):
    model = McqQuestion

    async def list_for_lesson(
        self, course_slug: str, lesson_slug: str
    ) -> list[McqQuestion]:
        """All MCQ of a lesson with their concept joined in, ordered by concept
        then the authored order_index (stable test order)."""
        return await self._all(
            select(McqQuestion)
            .join(Concept, McqQuestion.concept_id == Concept.id)
            .join(Lesson, Concept.lesson_id == Lesson.id)
            .join(Course, Lesson.course_id == Course.id)
            .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
            .options(joinedload(McqQuestion.concept))
            .order_by(Concept.order_index, McqQuestion.order_index)
        )

    async def all_slugs(self) -> set[str]:
        """Valid MCQ slugs — used to ignore unknown slugs in posted results."""
        return set(
            (await self.session.execute(select(McqQuestion.slug))).scalars().all()
        )

    async def lessons_with_mcq(self) -> list[tuple[str, str]]:
        """Distinct (course_slug, lesson_slug) that have at least one MCQ —
        the universe of lessons the tests-overview counts against."""
        rows = (
            await self.session.execute(
                select(Course.slug, Lesson.slug)
                .join(Lesson, Lesson.course_id == Course.id)
                .join(Concept, Concept.lesson_id == Lesson.id)
                .join(McqQuestion, McqQuestion.concept_id == Concept.id)
                .distinct()
            )
        ).all()
        return [(c, l) for c, l in rows]


class McqStatsRepository(BaseRepository[McqStat]):
    """Per-user MCQ stats. Flushes but never commits (the service owns the txn)."""

    model = McqStat

    async def list_for_slugs(
        self, user_id: int, slugs: Iterable[str]
    ) -> list[McqStat]:
        slugs = list(slugs)
        if not slugs:
            return []
        return await self._all(
            select(McqStat).where(
                McqStat.user_id == user_id, McqStat.mcq_slug.in_(slugs)
            )
        )

    async def record(
        self,
        *,
        user_id: int,
        mcq_slug: str,
        correct: bool,
        now: datetime | None = None,
    ) -> McqStat:
        """Upsert one MCQ result: bump seen/correct, set last_correct/last_seen."""
        now = now or _utcnow()
        stat = await self.find_one_by(user_id=user_id, mcq_slug=mcq_slug)
        if stat is None:
            stat = McqStat(user_id=user_id, mcq_slug=mcq_slug, seen=0, correct=0)
            self.add(stat)
        stat.seen += 1
        stat.correct += 1 if correct else 0
        stat.last_correct = correct
        stat.last_seen_at = now
        await self.session.flush()
        return stat


class LessonTestResultRepository(BaseRepository[LessonTestResult]):
    """Per-(user, lesson) test score. Flushes but never commits."""

    model = LessonTestResult

    async def get(
        self, user_id: int, course_slug: str, lesson_slug: str
    ) -> LessonTestResult | None:
        return await self.find_one_by(
            user_id=user_id, course_slug=course_slug, lesson_slug=lesson_slug
        )

    async def list_for_user(self, user_id: int) -> list[LessonTestResult]:
        return await self.list_by(user_id=user_id)

    async def record_full_run(
        self,
        *,
        user_id: int,
        course_slug: str,
        lesson_slug: str,
        score: int,
        now: datetime | None = None,
    ) -> LessonTestResult:
        """Upsert a completed full run: bump attempts, set last/best score."""
        now = now or _utcnow()
        row = await self.get(user_id, course_slug, lesson_slug)
        if row is None:
            row = LessonTestResult(
                user_id=user_id,
                course_slug=course_slug,
                lesson_slug=lesson_slug,
                attempts=0,
                last_score=0,
                best_score=0,
            )
            self.add(row)
        row.attempts += 1
        row.last_score = score
        row.best_score = max(row.best_score, score)
        row.last_at = now
        await self.session.flush()
        return row
