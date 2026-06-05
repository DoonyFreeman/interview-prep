"""Repository layer: the single place that talks SQLAlchemy to the DB.

Each repository wraps an :class:`~sqlalchemy.ext.asyncio.AsyncSession` and exposes
intent-revealing methods (``get_by_slug``, ``due_for_user`` …) so services and
endpoints never build queries by hand. Repositories ``flush``/``add`` but never
``commit`` — the caller (a service) owns the transaction, which lets a single
service method persist across several repositories atomically.
"""
from __future__ import annotations

from app.repositories.attempts import AttemptRepository
from app.repositories.content import (
    ConceptRepository,
    CourseRepository,
    LessonRepository,
    QuestionRepository,
)
from app.repositories.glossary import GlossaryRepository
from app.repositories.lesson_progress import LessonProgressRepository
from app.repositories.mastery import ConceptMasteryRepository
from app.repositories.users import UserRepository

__all__ = [
    "AttemptRepository",
    "ConceptMasteryRepository",
    "ConceptRepository",
    "CourseRepository",
    "GlossaryRepository",
    "LessonProgressRepository",
    "LessonRepository",
    "QuestionRepository",
    "UserRepository",
]
