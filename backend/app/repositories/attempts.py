"""Attempt repository."""
from __future__ import annotations

from app.models import Attempt
from app.repositories.base import BaseRepository


class AttemptRepository(BaseRepository):
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
