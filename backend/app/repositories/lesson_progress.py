"""LessonProgress repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models import LessonProgress
from app.repositories.base import BaseRepository


class LessonProgressRepository(BaseRepository):
    async def get(self, user_id: int, lesson_id: int) -> LessonProgress | None:
        return (
            await self.session.execute(
                select(LessonProgress).where(
                    LessonProgress.user_id == user_id,
                    LessonProgress.lesson_id == lesson_id,
                )
            )
        ).scalar_one_or_none()

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
        self.session.add(progress)
        return progress
