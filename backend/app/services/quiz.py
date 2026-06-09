"""Quiz service: serve a question, evaluate an answer, produce a hint.

Serving a question is a pure DB read — no LLM. Evaluation and hints each make a
single Gemini call grounded in the lesson text + the question's reference answer.
The reference answer is never sent pre-answer (serve / list / attempts); the one
deliberate exception is the evaluation response, which reveals it AFTER the
user's answer has been submitted and graded so they can compare.

All DB access goes through repositories; this module holds the orchestration
(LLM call, normalization, transaction boundary) and the spaced-repetition-aware
question selection.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.content import registry
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import (
    EVAL_SYSTEM,
    HINT_SYSTEM,
    build_eval_prompt,
    build_hint_prompt,
)
from app.models import Concept, ConceptMastery, Course, Lesson, Question, _utcnow
from app.repositories import (
    AttemptRepository,
    ConceptMasteryRepository,
    LessonRepository,
    QuestionRepository,
)
from app.schemas import (
    AttemptOut,
    EvaluationOut,
    LessonQuestionsOut,
    QuestionAttemptsOut,
    QuestionOut,
    QuestionStatusOut,
)
from app.services import progress

_VALID_VERDICTS = {"верно", "частично", "неверно"}


@dataclass
class _QContext:
    """A question with its concept / lesson / course joined in."""

    question: Question
    concept: Concept
    lesson: Lesson
    course: Course


# --------------------------------------------------------------------------- #
# Mapping helpers
# --------------------------------------------------------------------------- #
def _to_context(question: Question) -> _QContext:
    concept = question.concept
    lesson = concept.lesson
    return _QContext(
        question=question, concept=concept, lesson=lesson, course=lesson.course
    )


def _to_out(ctx: _QContext) -> QuestionOut:
    return QuestionOut(
        id=ctx.question.id,
        text=ctx.question.text,
        difficulty=ctx.question.difficulty,
        concept_slug=ctx.concept.slug,
        concept_title=ctx.concept.title,
        anchor=ctx.concept.anchor,
        course_slug=ctx.course.slug,
        lesson_slug=ctx.lesson.slug,
    )


async def _get_context(session: AsyncSession, question_id: int) -> _QContext:
    question = await QuestionRepository(session).get_with_context(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return _to_context(question)


# --------------------------------------------------------------------------- #
# Serve (pure DB read, spaced-repetition-aware selection)
# --------------------------------------------------------------------------- #
async def serve_question(
    session: AsyncSession, course_slug: str, lesson_slug: str, *, user_id: int
) -> QuestionOut:
    """Serve a question from the lesson, preferring concepts that need work.

    Selection order: a concept the user has never attempted, else the most
    overdue due concept, else a random concept (reviewing ahead). A random
    question from the chosen concept is returned (no reference answer).
    """
    lesson = await LessonRepository(session).get_for_serve(course_slug, lesson_slug)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    concepts = [c for c in lesson.concepts if c.questions]
    if not concepts:
        raise HTTPException(status_code=404, detail="No questions for this lesson")

    mastery_by_concept = {
        m.concept_id: m
        for m in await ConceptMasteryRepository(session).list_for_user_and_concepts(
            user_id, [c.id for c in concepts]
        )
    }
    now = _utcnow()

    concept = _pick_concept(concepts, mastery_by_concept, now)
    question = random.choice(concept.questions)

    ctx = _QContext(
        question=question, concept=concept, lesson=lesson, course=lesson.course
    )
    return _to_out(ctx)


def _pick_concept(
    concepts: list[Concept],
    mastery_by_concept: dict[int, ConceptMastery],
    now,
) -> Concept:
    new = [c for c in concepts if c.id not in mastery_by_concept]
    if new:
        return random.choice(new)

    due = [c for c in concepts if mastery_by_concept[c.id].due_at <= now]
    if due:
        # Most overdue first.
        return min(due, key=lambda c: mastery_by_concept[c.id].due_at)

    return random.choice(concepts)


async def get_question(session: AsyncSession, question_id: int) -> QuestionOut:
    """Serve one specific question by id (for re-practice). No reference answer."""
    ctx = await _get_context(session, question_id)
    return _to_out(ctx)


async def list_lesson_questions(
    session: AsyncSession, course_slug: str, lesson_slug: str, *, user_id: int
) -> LessonQuestionsOut:
    """All questions in a lesson + the user's attempt history with each one,
    so they can revisit and re-practice answered questions."""
    lesson = await LessonRepository(session).get_for_serve(course_slug, lesson_slug)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    pairs: list[tuple[Concept, Question]] = []
    for concept in sorted(lesson.concepts, key=lambda c: c.order_index):
        for question in sorted(concept.questions, key=lambda q: q.order_index):
            pairs.append((concept, question))

    attempts = await AttemptRepository(session).list_for_questions(
        user_id, [q.id for _, q in pairs]
    )
    last_by_q: dict[int, "object"] = {}
    count_by_q: dict[int, int] = {}
    for attempt in attempts:  # oldest-first → last write wins as the latest
        last_by_q[attempt.question_id] = attempt
        count_by_q[attempt.question_id] = count_by_q.get(attempt.question_id, 0) + 1

    items: list[QuestionStatusOut] = []
    for concept, question in pairs:
        attempt = last_by_q.get(question.id)
        verdict: str | None = None
        if attempt is not None:
            try:
                verdict = json.loads(attempt.review_json).get("verdict")
            except (ValueError, AttributeError):
                verdict = None
        items.append(
            QuestionStatusOut(
                id=question.id,
                text=question.text,
                difficulty=question.difficulty,
                concept_slug=concept.slug,
                concept_title=concept.title,
                anchor=concept.anchor,
                attempts=count_by_q.get(question.id, 0),
                last_score=attempt.score if attempt is not None else None,
                last_verdict=verdict,
                last_attempted_at=attempt.created_at if attempt is not None else None,
            )
        )

    return LessonQuestionsOut(
        course_slug=course_slug, lesson_slug=lesson_slug, questions=items
    )


async def get_question_attempts(
    session: AsyncSession, question_id: int, *, user_id: int
) -> QuestionAttemptsOut:
    """The user's past attempts at a question: their answer + the stored review,
    newest first. Lets the user revisit what they wrote and how it was graded."""
    ctx = await _get_context(session, question_id)
    attempts = await AttemptRepository(session).list_for_question(user_id, question_id)

    out: list[AttemptOut] = []
    for a in attempts:
        try:
            review = json.loads(a.review_json)
        except (ValueError, TypeError):
            review = {}
        out.append(
            AttemptOut(
                id=a.id,
                score=a.score,
                verdict=str(review.get("verdict", "")),
                summary=str(review.get("summary", "")),
                strengths=list(review.get("strengths") or []),
                gaps=list(review.get("gaps") or []),
                suggestion=str(review.get("suggestion", "")),
                answer_text=a.answer_text,
                hint_used=a.hint_used,
                created_at=a.created_at,
            )
        )

    return QuestionAttemptsOut(
        question_id=ctx.question.id,
        text=ctx.question.text,
        concept_title=ctx.concept.title,
        anchor=ctx.concept.anchor,
        course_slug=ctx.course.slug,
        lesson_slug=ctx.lesson.slug,
        attempts=out,
    )


# --------------------------------------------------------------------------- #
# Evaluate (one LLM call + persist an Attempt + advance mastery)
# --------------------------------------------------------------------------- #
async def evaluate_answer(
    session: AsyncSession,
    llm: LLMClient,
    *,
    user_id: int,
    question_id: int,
    answer_text: str,
    hint_used: bool,
) -> EvaluationOut:
    ctx = await _get_context(session, question_id)
    lesson_text = registry.get_lesson_text(ctx.course.slug, ctx.lesson.slug) or ""

    prompt = build_eval_prompt(
        lesson_text=lesson_text,
        question=ctx.question.text,
        reference_answer=ctx.question.reference_answer,
        user_answer=answer_text,
    )
    try:
        raw = await llm.generate_json(prompt, system=EVAL_SYSTEM)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Evaluation failed: {exc}",
        ) from exc

    review = _normalize_evaluation(raw)

    now = _utcnow()
    attempt = AttemptRepository(session).create(
        user_id=user_id,
        question_id=question_id,
        answer_text=answer_text,
        score=review["score"],
        review_json=json.dumps(review, ensure_ascii=False),
        hint_used=hint_used,
    )

    # Each scored attempt advances the SM-2 mastery of the question's concept,
    # in the same transaction as the attempt.
    mastery = await progress.update_mastery(
        session,
        user_id=user_id,
        concept_id=ctx.concept.id,
        score=review["score"],
        now=now,
    )

    await session.commit()
    await session.refresh(attempt)
    await session.refresh(mastery)

    return EvaluationOut(
        attempt_id=attempt.id,
        # Revealed post-answer only: the user has already committed their own
        # answer, so showing the authored reference is a learning aid, not a leak.
        reference_answer=ctx.question.reference_answer,
        concept_slug=ctx.concept.slug,
        mastery=progress.mastery_to_out(mastery, now),
        **review,
    )


def _normalize_evaluation(raw: dict) -> dict:
    """Coerce the model's JSON into our contract, clamping/defaulting as needed."""
    try:
        score = int(round(float(raw.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))

    verdict = str(raw.get("verdict", "")).strip().lower()
    if verdict not in _VALID_VERDICTS:
        # Derive a verdict from the score if the model gave something off-contract.
        verdict = "верно" if score >= 80 else "частично" if score >= 40 else "неверно"

    def _as_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return {
        "score": score,
        "verdict": verdict,
        "summary": str(raw.get("summary", "")).strip(),
        "strengths": _as_list(raw.get("strengths")),
        "gaps": _as_list(raw.get("gaps")),
        "suggestion": str(raw.get("suggestion", "")).strip(),
    }


# --------------------------------------------------------------------------- #
# Hint (one LLM call, reference answer withheld)
# --------------------------------------------------------------------------- #
async def generate_hint(
    session: AsyncSession,
    llm: LLMClient,
    *,
    question_id: int,
    answer_text: str = "",
) -> str:
    ctx = await _get_context(session, question_id)
    lesson_text = registry.get_lesson_text(ctx.course.slug, ctx.lesson.slug) or ""

    prompt = build_hint_prompt(
        lesson_text=lesson_text,
        question=ctx.question.text,
        user_answer=answer_text,
    )
    try:
        hint = await llm.generate_text(prompt, system=HINT_SYSTEM)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Hint failed: {exc}",
        ) from exc
    return hint.strip()
