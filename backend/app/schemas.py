"""Pydantic response models for the read API.

Question reference answers are intentionally NOT exposed here — they ground the
LLM evaluation server-side and must never be sent to the client.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CourseSummary(BaseModel):
    slug: str
    title: str
    description: str
    order: int
    lesson_count: int


class ConceptOut(BaseModel):
    slug: str
    title: str
    anchor: str
    order: int
    question_count: int


class LessonSummary(BaseModel):
    slug: str
    title: str
    order: int
    duration_minutes: int
    concept_count: int


class CourseDetail(BaseModel):
    slug: str
    title: str
    description: str
    order: int
    lessons: list[LessonSummary]


class LessonDetail(BaseModel):
    slug: str
    title: str
    course_slug: str
    duration_minutes: int
    markdown: str
    concepts: list[ConceptOut]


# --------------------------------------------------------------------------- #
# Quiz (serve / evaluate / hint). reference_answer is never present here.
# --------------------------------------------------------------------------- #
class QuestionOut(BaseModel):
    id: int
    text: str
    difficulty: int
    concept_slug: str
    concept_title: str
    anchor: str  # markdown heading anchor for the "Back to theory" deep-link
    course_slug: str
    lesson_slug: str


class QuestionStatusOut(BaseModel):
    """A lesson question plus the current user's attempt history with it."""

    id: int
    text: str
    difficulty: int
    concept_slug: str
    concept_title: str
    anchor: str
    attempts: int
    last_score: int | None
    last_verdict: str | None
    last_attempted_at: datetime | None


class LessonQuestionsOut(BaseModel):
    course_slug: str
    lesson_slug: str
    questions: list[QuestionStatusOut]


class AttemptOut(BaseModel):
    """One past attempt at a question: the user's answer + the stored review."""

    id: int
    score: int
    verdict: str
    summary: str
    strengths: list[str]
    gaps: list[str]
    suggestion: str
    answer_text: str
    hint_used: bool
    created_at: datetime


class QuestionAttemptsOut(BaseModel):
    """A question's context + the current user's attempt history, newest first."""

    question_id: int
    text: str
    concept_title: str
    anchor: str
    course_slug: str
    lesson_slug: str
    attempts: list[AttemptOut]


class EvaluateIn(BaseModel):
    answer_text: str
    hint_used: bool = False


class MasteryOut(BaseModel):
    """SM-2 state for a concept after a scored attempt."""

    reps: int
    ease: float
    interval_days: float
    last_score: int
    due_at: datetime
    due: bool  # due_at has already passed (ready for review now)


class EvaluationOut(BaseModel):
    attempt_id: int
    score: int  # 0..100
    verdict: str  # "верно" | "частично" | "неверно"
    summary: str
    strengths: list[str]
    gaps: list[str]
    suggestion: str
    concept_slug: str
    mastery: MasteryOut


class HintIn(BaseModel):
    answer_text: str = ""


class HintOut(BaseModel):
    hint: str


# --------------------------------------------------------------------------- #
# Progress + spaced-repetition review queue
# --------------------------------------------------------------------------- #
class ReviewItem(BaseModel):
    concept_slug: str
    concept_title: str
    course_slug: str
    lesson_slug: str
    anchor: str
    last_score: int
    reps: int
    due_at: datetime
    question_id: int | None  # a question to practice this concept, if any


class ReviewQueueOut(BaseModel):
    count: int
    items: list[ReviewItem]


class ConceptProgressOut(BaseModel):
    slug: str
    title: str
    anchor: str
    attempted: bool
    mastered: bool
    reps: int
    last_score: int
    due_at: datetime | None
    due: bool


class LessonProgressOut(BaseModel):
    slug: str
    title: str
    completed: bool
    total_concepts: int
    attempted_concepts: int
    mastered_concepts: int
    due_concepts: int
    concepts: list[ConceptProgressOut]


class CourseProgressOut(BaseModel):
    slug: str
    title: str
    total_concepts: int
    attempted_concepts: int
    mastered_concepts: int
    due_concepts: int
    lessons: list[LessonProgressOut]


class ProgressOverviewOut(BaseModel):
    total_concepts: int
    attempted_concepts: int
    mastered_concepts: int
    due_concepts: int
    courses: list[CourseProgressOut]


# --------------------------------------------------------------------------- #
# Questions-answered progress ("what's left" overview)
# --------------------------------------------------------------------------- #
class LessonQuestionsProgressOut(BaseModel):
    slug: str
    title: str
    total: int
    answered: int


class CourseQuestionsProgressOut(BaseModel):
    slug: str
    title: str
    total: int
    answered: int
    lessons: list[LessonQuestionsProgressOut]


class QuestionsProgressOut(BaseModel):
    total: int
    answered: int
    courses: list[CourseQuestionsProgressOut]


class LessonProgressIn(BaseModel):
    completed: bool = False


# --------------------------------------------------------------------------- #
# Glossary (public reference section)
# --------------------------------------------------------------------------- #
class GlossaryLinkOut(BaseModel):
    course_slug: str
    lesson_slug: str
    anchor: str  # markdown heading anchor for the "back to theory" deep-link


class GlossaryTermOut(BaseModel):
    slug: str
    term: str
    category: str
    short_md: str
    aliases: list[str]
    links: list[GlossaryLinkOut]


class GlossaryListOut(BaseModel):
    count: int
    categories: list[str]  # category slugs in canonical display order
    terms: list[GlossaryTermOut]


# --- Glossary quiz progress (auth) ----------------------------------------- #
class GlossaryQuizResultItemIn(BaseModel):
    term_slug: str
    correct: bool


class GlossaryQuizResultIn(BaseModel):
    items: list[GlossaryQuizResultItemIn]


class GlossaryTermStatOut(BaseModel):
    term_slug: str
    seen: int
    correct: int
    last_correct: bool
    mastered: bool  # correct >= 2 and last answer correct
    last_seen_at: datetime


class GlossaryCategoryProgressOut(BaseModel):
    category: str
    total: int  # terms in this category
    seen: int  # terms attempted at least once
    mastered: int


class GlossaryProgressOut(BaseModel):
    total: int  # total glossary terms
    seen: int
    mastered: int
    recorded: int  # number of stat rows posted (returned by /result)
    categories: list[GlossaryCategoryProgressOut]
    terms: list[GlossaryTermStatOut]
