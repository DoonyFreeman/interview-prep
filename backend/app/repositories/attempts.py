"""Attempt repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Attempt
from app.repositories.base import BaseRepository


class AttemptRepository(BaseRepository):
    async def list_for_questions(
        self, user_id: int, question_ids: list[int]
    ) -> list[Attempt]:
        """All of the user's attempts for the given questions, oldest first."""
        if not question_ids:
            return []
        return list(
            (
                await self.session.execute(
                    select(Attempt)
                    .where(
                        Attempt.user_id == user_id,
                        Attempt.question_id.in_(question_ids),
                    )
                    .order_by(Attempt.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

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
        self.session.add(attempt)
        return attempt
