"""SQLAlchemy ORM models.

Content tables (Course/Lesson/Concept/Question) mirror the markdown + JSON seed
and are upserted at startup — markdown stays the source of truth. User tables
(User/Attempt/ConceptMastery/LessonProgress) hold per-user state.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    # Naive UTC: the DateTime columns are timezone-naive, and SQLite returns
    # naive values on read, so we keep everything naive-UTC to stay comparable
    # (mixing aware/naive datetimes raises, and offset suffixes break the
    # lexical ordering SQLite relies on for due_at filters).
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Content (mirrors the seed; source of truth is markdown/JSON)
# --------------------------------------------------------------------------- #
class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index",
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("course_id", "slug", name="uq_lesson_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content_path: Mapped[str] = mapped_column(String(300))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped["Course"] = relationship(back_populates="lessons")
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="Concept.order_index",
    )


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("lesson_id", "slug", name="uq_concept_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Markdown heading anchor used by the "Back to theory" deep-link.
    anchor: Mapped[str] = mapped_column(String(200), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    lesson: Mapped["Lesson"] = relationship(back_populates="concepts")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
    )
    mcqs: Mapped[list["McqQuestion"]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
        order_by="McqQuestion.order_index",
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    # Authored reference answer — grounds the AI evaluation.
    reference_answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    concept: Mapped["Concept"] = relationship(back_populates="questions")


class McqQuestion(Base):
    """A closed multiple-choice question for the lesson self-test (no LLM).

    Mirrors ``content/courses/<slug>/tests.json``. Unlike the open ``Question``
    (graded by the LLM against a *hidden* ``reference_answer``), an MCQ is graded
    by comparing the chosen option index — so the correct index + explanation are
    sent to the client and graded there for instant feedback. ``slug`` is a stable
    id (``course:lesson:concept:i``, derived by the loader) that survives the
    wholesale re-seed and keys the per-user :class:`McqStat`.
    """

    __tablename__ = "mcq_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20), default="single")  # single|boolean
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str]
    correct_index: Mapped[int] = mapped_column(Integer, default=0)
    explanation_md: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    concept: Mapped["Concept"] = relationship(back_populates="mcqs")


class GlossaryTerm(Base):
    """A standalone reference term (the glossary section).

    Mirrors ``content/glossary.json`` and is independent of courses/lessons so it
    can be complete even before lessons exist. ``aliases`` and ``links`` are stored
    as JSON text (decoded in the service). No user-state references it.
    """

    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    term: Mapped[str] = mapped_column(String(200))
    # "reference" (the technical glossary) or "slang" (the plain-language slang
    # dictionary). The two share this table but are served/grouped separately.
    kind: Mapped[str] = mapped_column(String(20), default="reference", index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    short_md: Mapped[str] = mapped_column(Text)
    aliases: Mapped[str] = mapped_column(Text, default="[]")  # JSON list[str]
    # JSON list[{course_slug, lesson_slug, anchor}] — deep-links "back to theory".
    links: Mapped[str] = mapped_column(Text, default="[]")
    order_index: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- #
# Users & per-user state
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    answer_text: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    # Full evaluation payload (strengths/gaps/suggestion/reasoning) as JSON text.
    review_json: Mapped[str] = mapped_column(Text, default="{}")
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ConceptMastery(Base):
    """SM-2 spaced-repetition state per (user, concept)."""

    __tablename__ = "concept_mastery"
    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", name="uq_mastery_user_concept"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), index=True
    )
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    last_score: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class GlossaryTermStat(Base):
    """Per-(user, glossary term) quiz stats — drives the smart term selection.

    References a term by its ``slug`` (not an FK) so the glossary can be
    re-seeded wholesale without touching user data. A term is "mastered" when
    ``correct >= 2`` and the last answer was correct.
    """

    __tablename__ = "glossary_term_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "term_slug", name="uq_glossary_stat_user_term"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    term_slug: Mapped[str] = mapped_column(String(80), index=True)
    seen: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    last_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class McqStat(Base):
    """Per-(user, MCQ) self-test stats — drives the lesson "test score" badge and
    the "review mistakes" mode.

    References an MCQ by its stable ``slug`` (not an FK) so the test bank can be
    re-seeded wholesale without touching user data, mirroring
    :class:`GlossaryTermStat`. An MCQ is "mastered" when answered correctly at
    least twice and the last answer was correct.
    """

    __tablename__ = "mcq_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "mcq_slug", name="uq_mcq_stat_user_mcq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mcq_slug: Mapped[str] = mapped_column(String(160), index=True)
    seen: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    last_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class LessonTestResult(Base):
    """Per-(user, lesson) MCQ test score — drives the lesson badge and the
    dashboard "tests passed" indicator.

    Only **full** runs (every MCQ of the lesson answered) update this; the
    "review mistakes" mode posts a subset and must not inflate ``best_score``.
    Keyed by ``course_slug``/``lesson_slug`` (not an FK) so it survives the
    wholesale content re-seed, mirroring :class:`McqStat`. "Passed" is derived
    on read (``best_score >= TEST_PASS_THRESHOLD``), not stored.
    """

    __tablename__ = "lesson_test_results"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "course_slug", "lesson_slug", name="uq_test_result_user_lesson"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_slug: Mapped[str] = mapped_column(String(64), index=True)
    lesson_slug: Mapped[str] = mapped_column(String(64), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # full runs
    last_score: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    best_score: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    last_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
