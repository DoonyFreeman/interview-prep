"""Quiz endpoints (auth-gated): serve a question, evaluate an answer, get a hint.

Serving is a pure DB read; evaluate and hint each make one grounded Gemini call.
All routes require a Bearer JWT. The reference answer never leaves the server.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
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
    LessonTestOut,
    LessonTestProgressOut,
    MixResultOut,
    QuestionAttemptsOut,
    QuestionOut,
    TestMixOut,
    TestResultIn,
    TestsOverviewOut,
    TestTopicsOut,
)
from app.services import lesson_test, quiz

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


# --------------------------------------------------------------------------- #
# Lesson MCQ self-test (no LLM, graded client-side).
# --------------------------------------------------------------------------- #
@router.get("/quiz/tests/overview", response_model=TestsOverviewOut)
async def tests_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Per-course + overall test status (lessons started/passed) for the dashboard."""
    return await lesson_test.tests_overview(session, user.id)


# --- Mixed test (/tests): pick topics + count, questions from any lesson ---- #
@router.get("/quiz/tests/topics", response_model=TestTopicsOut)
async def mix_topics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Selectable topics with question counts + this user's answered/weak tallies."""
    return await lesson_test.mix_topics(session, user.id)


@router.get("/quiz/tests/mix", response_model=TestMixOut)
async def tests_mix(
    courses: str = Query("", description="Comma-separated course slugs; empty = all"),
    banks: str = Query("lesson,exam", description="Comma-separated: lesson, exam"),
    mode: str = Query("smart", description="smart | random | weak | mistakes"),
    count: int = Query(20, ge=1, le=lesson_test.MAX_MIX_COUNT),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Generate one mixed test. Selection is server-side (the full bank is far
    too big to ship to the client just to keep a handful of questions)."""
    return await lesson_test.generate_mix(
        session,
        user.id,
        courses=[c for c in courses.split(",") if c],
        banks=[b for b in banks.split(",") if b],
        mode=mode,
        count=count,
    )


@router.post("/quiz/tests/mix/result", response_model=MixResultOut)
async def record_mix_result(
    data: TestResultIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record a finished mixed run; recomputes every lesson score it touched."""
    return await lesson_test.record_mix_results(
        session, user.id, [(i.slug, i.correct) for i in data.items]
    )


@router.get(
    "/quiz/courses/{course_slug}/lessons/{lesson_slug}/test",
    response_model=LessonTestOut,
)
async def lesson_test_questions(
    course_slug: str,
    lesson_slug: str,
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """All MCQ for the lesson (with correct index + explanation, for client grading)."""
    return await lesson_test.serve_test(session, course_slug, lesson_slug)


@router.get(
    "/quiz/courses/{course_slug}/lessons/{lesson_slug}/test/progress",
    response_model=LessonTestProgressOut,
)
async def lesson_test_progress(
    course_slug: str,
    lesson_slug: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """This user's lesson "test score": total / answered / last-correct counts."""
    return await lesson_test.get_lesson_progress(
        session, user.id, course_slug, lesson_slug
    )


@router.post(
    "/quiz/courses/{course_slug}/lessons/{lesson_slug}/test/result",
    response_model=LessonTestProgressOut,
)
async def record_lesson_test_result(
    course_slug: str,
    lesson_slug: str,
    data: TestResultIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record a finished test (one item per answered MCQ); returns fresh progress."""
    items = [(i.slug, i.correct) for i in data.items]
    return await lesson_test.record_results(
        session, user.id, course_slug, lesson_slug, items
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
