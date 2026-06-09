"""Repositories for the content mirror: courses, lessons, concepts, questions."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Concept, Course, Lesson, Question
from app.repositories.base import BaseRepository


class CourseRepository(BaseRepository[Course]):
    model = Course

    async def list_published_with_lesson_counts(self) -> list[tuple[Course, int]]:
        """Published courses + their lesson count, ordered for display."""
        lesson_count = (
            select(Lesson.course_id, func.count(Lesson.id).label("n"))
            .group_by(Lesson.course_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(Course, func.coalesce(lesson_count.c.n, 0))
                .outerjoin(lesson_count, lesson_count.c.course_id == Course.id)
                .where(Course.is_published.is_(True))
                .order_by(Course.order_index)
            )
        ).all()
        return [(course, n) for course, n in rows]

    async def get_by_slug(self, slug: str) -> Course | None:
        return await self.find_one_by(slug=slug)

    async def get_by_slug_with_lessons_concepts(self, slug: str) -> Course | None:
        return await self._one(
            select(Course)
            .where(Course.slug == slug)
            .options(selectinload(Course.lessons).selectinload(Lesson.concepts))
        )

    async def list_published_with_lessons_concepts(self) -> list[Course]:
        return await self._all(
            select(Course)
            .where(Course.is_published.is_(True))
            .options(selectinload(Course.lessons).selectinload(Lesson.concepts))
            .order_by(Course.order_index)
        )


class LessonRepository(BaseRepository[Lesson]):
    model = Lesson

    async def get_by_slugs(self, course_slug: str, lesson_slug: str) -> Lesson | None:
        """Plain lesson lookup by course+lesson slug (joins through Course)."""
        return await self._one(
            select(Lesson)
            .join(Course, Lesson.course_id == Course.id)
            .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
        )

    async def get_detail(self, course_id: int, lesson_slug: str) -> Lesson | None:
        """Lesson with concepts+questions eager-loaded (for the lesson detail view)."""
        return await self._one(
            select(Lesson)
            .where(Lesson.course_id == course_id, Lesson.slug == lesson_slug)
            .options(selectinload(Lesson.concepts).selectinload(Concept.questions))
        )

    async def get_for_serve(
        self, course_slug: str, lesson_slug: str
    ) -> Lesson | None:
        """Lesson with its course + concepts + questions, for question serving."""
        return (
            (
                await self.session.execute(
                    select(Lesson)
                    .join(Course, Lesson.course_id == Course.id)
                    .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
                    .options(
                        joinedload(Lesson.course),
                        selectinload(Lesson.concepts).selectinload(Concept.questions),
                    )
                )
            )
            .unique()
            .scalar_one_or_none()
        )


class ConceptRepository(BaseRepository[Concept]):
    model = Concept

    async def get_by_slug(self, slug: str) -> Concept | None:
        return await self.find_one_by(slug=slug)


class QuestionRepository(BaseRepository[Question]):
    model = Question

    async def get_with_context(self, question_id: int) -> Question | None:
        """Question with concept→lesson→course joined in (for grading/serving)."""
        return await self._one(
            select(Question)
            .where(Question.id == question_id)
            .options(
                joinedload(Question.concept)
                .joinedload(Concept.lesson)
                .joinedload(Lesson.course)
            )
        )

    async def min_id_for_concept(self, concept_id: int) -> int | None:
        """Lowest question id for a concept — a stable 'practice this' pick."""
        return (
            await self.session.execute(
                select(func.min(Question.id)).where(
                    Question.concept_id == concept_id
                )
            )
        ).scalar()

    async def count_by_lesson(self) -> dict[int, int]:
        """Per lesson: total number of questions (across all its concepts)."""
        rows = (
            await self.session.execute(
                select(Lesson.id, func.count(Question.id))
                .join(Concept, Question.concept_id == Concept.id)
                .join(Lesson, Concept.lesson_id == Lesson.id)
                .group_by(Lesson.id)
            )
        ).all()
        return {lesson_id: n for lesson_id, n in rows}
