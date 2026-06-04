"""Pydantic response models for the read API.

Question reference answers are intentionally NOT exposed here — they ground the
LLM evaluation server-side and must never be sent to the client.
"""
from __future__ import annotations

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


class EvaluateIn(BaseModel):
    answer_text: str
    hint_used: bool = False


class EvaluationOut(BaseModel):
    attempt_id: int
    score: int  # 0..100
    verdict: str  # "верно" | "частично" | "неверно"
    summary: str
    strengths: list[str]
    gaps: list[str]
    suggestion: str


class HintIn(BaseModel):
    answer_text: str = ""


class HintOut(BaseModel):
    hint: str
