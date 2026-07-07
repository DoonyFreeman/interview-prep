"""Pydantic response models for the read API.

Question reference answers ground the LLM evaluation server-side and are never
exposed pre-answer (serve / lesson list / attempts history). The one deliberate
exception is EvaluationOut: after the user submits an answer and it is graded,
the response reveals the authored reference answer for self-comparison.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator


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
    # The authored reference answer, revealed ONLY here — after the user has
    # submitted their own answer and it has been graded. Pre-answer endpoints
    # (serve / lesson list / attempts history) must keep omitting it.
    reference_answer: str
    concept_slug: str
    mastery: MasteryOut


class HintIn(BaseModel):
    answer_text: str = ""


class HintOut(BaseModel):
    hint: str


# --------------------------------------------------------------------------- #
# Lesson MCQ self-test (no LLM, graded client-side).
#
# Unlike the open quiz, the correct option index + explanation ARE sent to the
# client: the options are inherently visible and grading is a plain index compare
# (no LLM to protect), so instant client-side feedback is the deliberate design.
# This does NOT relax the reference_answer rule — open questions stay reference-
# free pre-answer.
# --------------------------------------------------------------------------- #
class McqQuestionOut(BaseModel):
    slug: str  # stable id (course:lesson:concept:i) — also the result key
    type: str  # "single" | "boolean"
    text: str
    options: list[str]
    correct_index: int
    explanation_md: str
    concept_slug: str
    concept_title: str
    anchor: str  # markdown heading anchor for the "back to theory" deep-link
    difficulty: int


class LessonTestOut(BaseModel):
    course_slug: str
    lesson_slug: str
    total: int
    questions: list[McqQuestionOut]


class TestResultItemIn(BaseModel):
    slug: str
    correct: bool


class TestResultIn(BaseModel):
    items: list[TestResultItemIn]


class LessonTestProgressOut(BaseModel):
    total: int  # MCQ in the lesson
    answered: int  # MCQ attempted at least once
    correct: int  # MCQ whose last answer was correct
    attempts: int  # number of full runs
    last_score: int  # 0..100, last full run
    best_score: int  # 0..100, best full run
    passed: bool  # best_score >= TEST_PASS_THRESHOLD


class TestsCourseOverviewOut(BaseModel):
    slug: str
    total: int  # lessons in this course that have MCQ
    passed: int  # of those, best_score >= threshold
    started: int  # of those, at least one full run


class TestsOverviewOut(BaseModel):
    total: int  # lessons with MCQ across all courses
    passed: int
    started: int
    courses: list[TestsCourseOverviewOut]


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


# --- Pet (corner cat) state ------------------------------------------------
class PetStateOut(BaseModel):
    name: str
    skin: str
    hat: str | None
    streak: int
    best_streak: int
    last_active_day: str | None
    hidden: bool


class PetStateUpdate(BaseModel):
    """Partial update — every field optional (PATCH semantics)."""

    name: str | None = None
    skin: str | None = None
    hat: str | None = None
    streak: int | None = None
    best_streak: int | None = None
    last_active_day: str | None = None
    hidden: bool | None = None


class PetVisit(BaseModel):
    """Mark the user active *today* (their local calendar day, "YYYY-MM-DD").

    The streak rollover is computed server-side from this single call so a
    daily visit can't be lost to a client-side optimistic-write rollback/race.
    """

    today: str

    @field_validator("today")
    @classmethod
    def _valid_day(cls, v: str) -> str:
        date.fromisoformat(v)  # raises (→ 422) on a malformed day
        return v


# --- Global lesson search ---------------------------------------------------
class SearchResultOut(BaseModel):
    """One search hit: a lesson (anchor "") or a specific H2 section of it.

    Built from titles + lesson markdown only — question data (and with it
    ``reference_answer``) is never loaded by the search path.
    """

    course_slug: str
    course_title: str
    lesson_slug: str
    lesson_title: str
    section_title: str | None  # H2 heading for section hits; None for lesson-top rows
    anchor: str  # "" => deep-link to the lesson top
    snippet: str
    match_field: str  # "lesson_title" | "section_title" | "body" | "course_title"


class SearchOut(BaseModel):
    query: str
    count: int
    results: list[SearchResultOut]


# --- Cat "thoughts" (corner cat) -------------------------------------------
class CatThoughtOut(BaseModel):
    """One studyable topic the corner cat can mention, from a completed lesson.

    ``definition`` is the first prose paragraph of the concept's H2 section
    (may be "" for a code-only section); the cat then shows the title alone.
    """

    key: str  # "{course_slug}/{lesson_slug}#{anchor}" — stable id for anti-repeat
    term: str  # concept title (the H2 heading)
    definition: str
    course_slug: str
    lesson_slug: str
    anchor: str


# --- Admin -------------------------------------------------------------------
class AdminUserOut(BaseModel):
    id: int
    email: str
    display_name: str
    created_at: datetime
    pet: PetStateOut
    total_concepts: int
    attempted_concepts: int
    mastered_concepts: int
    total_lessons: int
    completed_lessons: int
    tests_total: int  # lessons with MCQ
    tests_passed: int
    attempts_count: int
    avg_score: int  # rounded mean over all attempts, 0 if none


class AdminUsersOut(BaseModel):
    users: list[AdminUserOut]


class AdminUserDetailOut(BaseModel):
    user: AdminUserOut
    progress: ProgressOverviewOut
    tests: TestsOverviewOut


# --------------------------------------------------------------------------- #
# Roadmap (public /api/roadmap — stages -> courses -> lessons + resources)
# --------------------------------------------------------------------------- #
class RoadmapResourceOut(BaseModel):
    type: str  # video | article | docs
    lang: str  # ru | en
    title: str
    url: str
    source: str


class RoadmapLessonOut(BaseModel):
    slug: str
    title: str
    order: int
    duration_minutes: int
    # Lesson-specific curated links; [] => client falls back to course.resources.
    resources: list[RoadmapResourceOut]


class RoadmapCourseOut(BaseModel):
    slug: str
    title: str
    description: str
    summary: str
    resources: list[RoadmapResourceOut]
    lessons: list[RoadmapLessonOut]


class RoadmapExtraNodeOut(BaseModel):
    """A topic without an internal course — external resources only."""

    slug: str
    title: str
    summary: str
    resources: list[RoadmapResourceOut]


class RoadmapStageOut(BaseModel):
    slug: str
    title: str
    summary: str
    courses: list[RoadmapCourseOut]
    extra_nodes: list[RoadmapExtraNodeOut]


class RoadmapOut(BaseModel):
    stages: list[RoadmapStageOut]
