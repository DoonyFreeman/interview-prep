"""ConceptMastery repository (SM-2 spaced-repetition state)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models import Concept, ConceptMastery, Course, Lesson
from app.repositories.base import BaseRepository


class ConceptMasteryRepository(BaseRepository[ConceptMastery]):
    model = ConceptMastery

    async def get(self, user_id: int, concept_id: int) -> ConceptMastery | None:
        """One user's mastery row for a concept (composite key, not the PK)."""
        return await self.find_one_by(user_id=user_id, concept_id=concept_id)

    async def list_for_user(self, user_id: int) -> list[ConceptMastery]:
        return await self.list_by(user_id=user_id)

    async def list_for_user_and_concepts(
        self, user_id: int, concept_ids: list[int]
    ) -> list[ConceptMastery]:
        if not concept_ids:
            return []
        return await self._all(
            select(ConceptMastery).where(
                ConceptMastery.user_id == user_id,
                ConceptMastery.concept_id.in_(concept_ids),
            )
        )

    async def due_for_user(
        self, user_id: int, now: datetime, limit: int
    ) -> list[tuple[ConceptMastery, Concept, Lesson, Course]]:
        """Mastery rows due now, joined with concept/lesson/course, soonest first."""
        rows = (
            await self.session.execute(
                select(ConceptMastery, Concept, Lesson, Course)
                .join(Concept, ConceptMastery.concept_id == Concept.id)
                .join(Lesson, Concept.lesson_id == Lesson.id)
                .join(Course, Lesson.course_id == Course.id)
                .where(
                    ConceptMastery.user_id == user_id,
                    ConceptMastery.due_at <= now,
                )
                .order_by(ConceptMastery.due_at.asc())
                .limit(limit)
            )
        ).all()
        return [tuple(row) for row in rows]

    def create(
        self,
        *,
        user_id: int,
        concept_id: int,
        ease: float,
        interval_days: float,
        reps: int,
    ) -> ConceptMastery:
        mastery = ConceptMastery(
            user_id=user_id,
            concept_id=concept_id,
            ease=ease,
            interval_days=interval_days,
            reps=reps,
        )
        self.add(mastery)
        return mastery
