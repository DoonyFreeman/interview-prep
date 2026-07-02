"""Global lesson search endpoint (public, like the glossary reads)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import SearchOut
from app.services import search as search_service

router = APIRouter()


@router.get("/search", response_model=SearchOut)
async def search_lessons(
    q: str = Query(min_length=2, max_length=200),
    session: AsyncSession = Depends(get_session),
):
    return await search_service.search_lessons(session, q)
