"""Repositories for the lesson MCQ self-test + per-user stats."""
from __future__ import annotations

from datetime import datetime
from collections.abc import Iterable

from sqlalchemy import func, select
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


#: The per-lesson self-test bank (``tests.json``) — the only one a lesson's
#: badge and the tests overview score against.
BANK_LESSON = "lesson"
#: Extra applied/scenario questions (``exam.json``), served only in the mixed
#: ``/tests`` section so they never move a lesson's score.
BANK_EXAM = "exam"


class McqRepository(BaseRepository[McqQuestion]):
    model = McqQuestion

    async def list_for_lesson(
        self, course_slug: str, lesson_slug: str
    ) -> list[McqQuestion]:
        """The lesson-bank MCQ of a lesson with their concept joined in, ordered
        by concept then the authored order_index (stable test order). Exam-bank
        questions are excluded on purpose — the lesson test is the lesson's."""
        return await self._all(
            select(McqQuestion)
            .join(Concept, McqQuestion.concept_id == Concept.id)
            .join(Lesson, Concept.lesson_id == Lesson.id)
            .join(Course, Lesson.course_id == Course.id)
            .where(
                Course.slug == course_slug,
                Lesson.slug == lesson_slug,
                McqQuestion.bank == BANK_LESSON,
            )
            .options(joinedload(McqQuestion.concept))
            .order_by(Concept.order_index, McqQuestion.order_index)
        )

    async def all_slugs(self) -> set[str]:
        """Valid MCQ slugs (both banks) — used to ignore unknown slugs in posted
        results."""
        return set(
            (await self.session.execute(select(McqQuestion.slug))).scalars().all()
        )

    async def lessons_with_mcq(self) -> list[tuple[str, str]]:
        """Distinct (course_slug, lesson_slug) that have at least one lesson-bank
        MCQ — the universe of lessons the tests-overview counts against."""
        rows = (
            await self.session.execute(
                select(Course.slug, Lesson.slug)
                .join(Lesson, Lesson.course_id == Course.id)
                .join(Concept, Concept.lesson_id == Lesson.id)
                .join(McqQuestion, McqQuestion.concept_id == Concept.id)
                .where(McqQuestion.bank == BANK_LESSON)
                .distinct()
            )
        ).all()
        return [(c, l) for c, l in rows]

    # ------------------------------------------------------------------ mix --
    # The mixed /tests section draws from any course. Selection is two-step: pull
    # the cheap (id, slug, course) triples for the whole candidate pool, choose in
    # Python (see services/lesson_test.py:pick_mix), then hydrate only the chosen
    # rows. Loading ~700 full rows to keep 20 would be the wasteful way round.

    async def mix_candidates(
        self, *, course_slugs: Iterable[str] | None, banks: Iterable[str]
    ) -> list[tuple[int, str, str]]:
        """``(id, slug, course_slug)`` of every MCQ matching the filter."""
        stmt = (
            select(McqQuestion.id, McqQuestion.slug, Course.slug)
            .join(Concept, McqQuestion.concept_id == Concept.id)
            .join(Lesson, Concept.lesson_id == Lesson.id)
            .join(Course, Lesson.course_id == Course.id)
            .where(McqQuestion.bank.in_(list(banks)))
        )
        course_slugs = list(course_slugs or [])
        if course_slugs:
            stmt = stmt.where(Course.slug.in_(course_slugs))
        rows = (await self.session.execute(stmt)).all()
        return [(i, s, c) for i, s, c in rows]

    async def list_by_ids(
        self, ids: Iterable[int]
    ) -> list[tuple[McqQuestion, str, str, str, str]]:
        """Hydrate chosen MCQ with their course/lesson context, as
        ``(mcq, course_slug, course_title, lesson_slug, lesson_title)``. The
        mixed test spans lessons, so each question carries its own deep link."""
        ids = list(ids)
        if not ids:
            return []
        rows = (
            await self.session.execute(
                select(
                    McqQuestion, Course.slug, Course.title, Lesson.slug, Lesson.title
                )
                .join(Concept, McqQuestion.concept_id == Concept.id)
                .join(Lesson, Concept.lesson_id == Lesson.id)
                .join(Course, Lesson.course_id == Course.id)
                .where(McqQuestion.id.in_(ids))
                .options(joinedload(McqQuestion.concept))
            )
        ).all()
        return [tuple(r) for r in rows]  # type: ignore[misc]

    async def lessons_for_slugs(self, slugs: Iterable[str]) -> list[tuple[str, str]]:
        """Distinct ``(course_slug, lesson_slug)`` the given **lesson-bank** MCQ
        belong to. A mixed run answers questions from many lessons; this says
        whose standing score has to be recomputed. Exam-bank slugs are filtered
        out — they are not part of any lesson's test."""
        slugs = list(slugs)
        if not slugs:
            return []
        rows = (
            await self.session.execute(
                select(Course.slug, Lesson.slug)
                .join(Lesson, Lesson.course_id == Course.id)
                .join(Concept, Concept.lesson_id == Lesson.id)
                .join(McqQuestion, McqQuestion.concept_id == Concept.id)
                .where(
                    McqQuestion.slug.in_(slugs),
                    McqQuestion.bank == BANK_LESSON,
                )
                .distinct()
            )
        ).all()
        return [(c, l) for c, l in rows]

    async def counts_by_course(self) -> list[tuple[str, str, str, int]]:
        """``(course_slug, course_title, bank, count)`` — feeds the topic picker
        on the mixed-test setup screen."""
        rows = (
            await self.session.execute(
                select(
                    Course.slug,
                    Course.title,
                    McqQuestion.bank,
                    func.count(McqQuestion.id),
                )
                .join(Lesson, Lesson.course_id == Course.id)
                .join(Concept, Concept.lesson_id == Lesson.id)
                .join(McqQuestion, McqQuestion.concept_id == Concept.id)
                .group_by(Course.slug, Course.title, McqQuestion.bank)
                .order_by(Course.order_index)
            )
        ).all()
        return [(s, t, b, n) for s, t, b, n in rows]


class McqStatsRepository(BaseRepository[McqStat]):
    """Per-user MCQ stats. Flushes but never commits (the service owns the txn)."""

    model = McqStat

    async def list_for_user(self, user_id: int) -> list[McqStat]:
        """Every MCQ stat this user has — the weighting input for the mix."""
        return await self.list_by(user_id=user_id)

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
