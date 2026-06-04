"""Quiz service: serve a question, evaluate an answer, produce a hint.

Serving a question is a pure DB read — no LLM. Evaluation and hints each make a
single Gemini call grounded in the lesson text + the question's reference answer.
The reference answer is used only server-side and never returned to the client.

Spaced-repetition-aware question selection is Phase 4; for now serving picks a
random question from the lesson.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.content import registry
from app.llm.client import LLMClient, LLMError
from app.llm.prompts import (
    EVAL_SYSTEM,
    HINT_SYSTEM,
    build_eval_prompt,
    build_hint_prompt,
)
from app.models import Attempt, Concept, Course, Lesson, Question
from app.schemas import EvaluationOut, QuestionOut

_VALID_VERDICTS = {"верно", "частично", "неверно"}


@dataclass
class _QContext:
    """A question with its concept / lesson / course joined in."""

    question: Question
    concept: Concept
    lesson: Lesson
    course: Course


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _load_options():
    return joinedload(Question.concept).joinedload(Concept.lesson).joinedload(
        Lesson.course
    )


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
    question = (
        await session.execute(
            select(Question)
            .where(Question.id == question_id)
            .options(_load_options())
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return _to_context(question)


# --------------------------------------------------------------------------- #
# Serve (pure DB read)
# --------------------------------------------------------------------------- #
async def serve_question(
    session: AsyncSession, course_slug: str, lesson_slug: str
) -> QuestionOut:
    """Return a random question from the given lesson (no reference answer)."""
    question = (
        await session.execute(
            select(Question)
            .join(Concept, Question.concept_id == Concept.id)
            .join(Lesson, Concept.lesson_id == Lesson.id)
            .join(Course, Lesson.course_id == Course.id)
            .where(Course.slug == course_slug, Lesson.slug == lesson_slug)
            .options(_load_options())
            .order_by(func.random())
            .limit(1)
        )
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=404, detail="No questions for this lesson"
        )
    return _to_out(_to_context(question))


# --------------------------------------------------------------------------- #
# Evaluate (one LLM call + persist an Attempt)
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

    attempt = Attempt(
        user_id=user_id,
        question_id=question_id,
        answer_text=answer_text,
        score=review["score"],
        review_json=json.dumps(review, ensure_ascii=False),
        hint_used=hint_used,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)

    return EvaluationOut(attempt_id=attempt.id, **review)


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
