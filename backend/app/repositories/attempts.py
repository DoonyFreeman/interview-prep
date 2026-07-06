"""Attempt repository."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import Attempt, Concept, Lesson, Question
from app.repositories.base import BaseRepository


class AttemptRepository(BaseRepository[Attempt]):
    model = Attempt

    async def list_for_questions(
        self, user_id: int, question_ids: list[int]
    ) -> list[Attempt]:
        """All of the user's attempts for the given questions, oldest first."""
        if not question_ids:
            return []
        return await self._all(
            select(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.question_id.in_(question_ids),
            )
            .order_by(Attempt.created_at.asc())
        )

    async def list_for_question(
        self, user_id: int, question_id: int
    ) -> list[Attempt]:
        """The user's attempts for one question, newest first (history view)."""
        return await self._all(
            select(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.question_id == question_id,
            )
            .order_by(Attempt.created_at.desc())
        )

    async def answered_counts_by_lesson(self, user_id: int) -> dict[int, int]:
        """Per lesson: how many distinct questions the user has attempted."""
        rows = (
            await self.session.execute(
                select(
                    Lesson.id,
                    func.count(func.distinct(Question.id)),
                )
                .select_from(Attempt)
                .join(Question, Attempt.question_id == Question.id)
                .join(Concept, Question.concept_id == Concept.id)
                .join(Lesson, Concept.lesson_id == Lesson.id)
                .where(Attempt.user_id == user_id)
                .group_by(Lesson.id)
            )
        ).all()
        return {lesson_id: n for lesson_id, n in rows}

    async def count_and_avg_for_user(self, user_id: int) -> tuple[int, int]:
        """(attempt count, rounded average score) for a user — (0, 0) if none."""
        count, avg = (
            await self.session.execute(
                select(func.count(Attempt.id), func.avg(Attempt.score)).where(
                    Attempt.user_id == user_id
                )
            )
        ).one()
        return count, round(avg) if avg is not None else 0

    def create(
        self,
        *,
        user_id: int,
        question_id: int,
        answer_text: str,
        score: int,
        review_json: str,
        hint_used: bool,
    ) -> Attempt:
        """Build + stage an Attempt. The caller commits."""
        attempt = Attempt(
            user_id=user_id,
            question_id=question_id,
            answer_text=answer_text,
            score=score,
            review_json=review_json,
            hint_used=hint_used,
        )
        self.add(attempt)
        return attempt
