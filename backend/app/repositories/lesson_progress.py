"""LessonProgress repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models import LessonProgress
from app.repositories.base import BaseRepository


class LessonProgressRepository(BaseRepository[LessonProgress]):
    model = LessonProgress

    async def get(self, user_id: int, lesson_id: int) -> LessonProgress | None:
        """One user's progress row for a lesson (composite key, not the PK)."""
        return await self.find_one_by(user_id=user_id, lesson_id=lesson_id)

    async def completed_lesson_ids(self, user_id: int) -> set[int]:
        rows = (
            await self.session.execute(
                select(LessonProgress.lesson_id).where(
                    LessonProgress.user_id == user_id,
                    LessonProgress.completed.is_(True),
                )
            )
        ).all()
        return {lesson_id for (lesson_id,) in rows}

    def create(self, *, user_id: int, lesson_id: int) -> LessonProgress:
        progress = LessonProgress(user_id=user_id, lesson_id=lesson_id)
        self.add(progress)
        return progress
