"""Glossary endpoints.

Reference reads (`GET /glossary`, `/glossary/{slug}`) are public. Quiz progress
(`/glossary/progress`, `/glossary/quiz/result`) is per-user and auth-gated.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.models import User
from app.schemas import (
    GlossaryListOut,
    GlossaryProgressOut,
    GlossaryQuizResultIn,
    GlossaryTermOut,
)
from app.services import glossary, glossary_progress

router = APIRouter()


@router.get("/glossary", response_model=GlossaryListOut)
async def list_glossary(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    kind: str = Query(default="reference", pattern="^(reference|slang)$"),
    session: AsyncSession = Depends(get_session),
):
    return await glossary.list_glossary(session, category=category, q=q, kind=kind)


@router.get("/glossary/progress", response_model=GlossaryProgressOut)
async def glossary_progress_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Per-term quiz stats + per-category rollup for the current user."""
    return await glossary_progress.get_progress(session, user_id=user.id)


@router.post("/glossary/quiz/result", response_model=GlossaryProgressOut)
async def record_quiz_result(
    data: GlossaryQuizResultIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record a finished quiz (one item per answered term); returns fresh progress."""
    items = [(i.term_slug, i.correct) for i in data.items]
    return await glossary_progress.record_results(session, user_id=user.id, items=items)


@router.get("/glossary/{slug}", response_model=GlossaryTermOut)
async def get_term(slug: str, session: AsyncSession = Depends(get_session)):
    return await glossary.get_term(session, slug)
