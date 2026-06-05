"""Glossary endpoints — a public reference section (pure DB reads, no auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import GlossaryListOut, GlossaryTermOut
from app.services import glossary

router = APIRouter()


@router.get("/glossary", response_model=GlossaryListOut)
async def list_glossary(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    return await glossary.list_glossary(session, category=category, q=q)


@router.get("/glossary/{slug}", response_model=GlossaryTermOut)
async def get_term(slug: str, session: AsyncSession = Depends(get_session)):
    return await glossary.get_term(session, slug)
