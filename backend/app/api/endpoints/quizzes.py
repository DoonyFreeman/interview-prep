"""Quiz endpoints (auth-gated): serve a question, evaluate an answer, get a hint.

Serving is a pure DB read; evaluate and hint each make one grounded Gemini call.
All routes require a Bearer JWT. The reference answer never leaves the server.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.llm.client import LLMClient, get_llm
from app.models import User
from app.schemas import (
    EvaluateIn,
    EvaluationOut,
    HintIn,
    HintOut,
    LessonQuestionsOut,
    QuestionAttemptsOut,
    QuestionOut,
)
from app.services import quiz

router = APIRouter()


@router.get(
    "/quiz/courses/{course_slug}/lessons/{lesson_slug}/next",
    response_model=QuestionOut,
)
async def next_question(
    course_slug: str,
    lesson_slug: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve a question from the lesson (pure DB read, no reference answer)."""
    return await quiz.serve_question(
        session, course_slug, lesson_slug, user_id=user.id
    )


@router.get(
    "/quiz/courses/{course_slug}/lessons/{lesson_slug}/questions",
    response_model=LessonQuestionsOut,
)
async def lesson_questions(
    course_slug: str,
    lesson_slug: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all lesson questions + the user's attempt history (for re-practice)."""
    return await quiz.list_lesson_questions(
        session, course_slug, lesson_slug, user_id=user.id
    )


@router.get("/quiz/questions/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: int,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Serve one specific question by id (re-practice). No reference answer."""
    return await quiz.get_question(session, question_id)


@router.get(
    "/quiz/questions/{question_id}/attempts",
    response_model=QuestionAttemptsOut,
)
async def question_attempts(
    question_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """The user's past attempts at a question (their answers + stored reviews)."""
    return await quiz.get_question_attempts(session, question_id, user_id=user.id)


@router.post(
    "/quiz/questions/{question_id}/evaluate",
    response_model=EvaluationOut,
)
async def evaluate(
    question_id: int,
    data: EvaluateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
):
    """Grade the answer against the lesson + reference answer; store the attempt."""
    return await quiz.evaluate_answer(
        session,
        llm,
        user_id=user.id,
        question_id=question_id,
        answer_text=data.answer_text,
        hint_used=data.hint_used,
    )


@router.post(
    "/quiz/questions/{question_id}/hint",
    response_model=HintOut,
)
async def hint(
    question_id: int,
    data: HintIn,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
):
    """Return a leading nudge that must not reveal the reference answer."""
    text = await quiz.generate_hint(
        session, llm, question_id=question_id, answer_text=data.answer_text
    )
    return HintOut(hint=text)
