"""Corner-cat endpoints (auth-gated).

The cat shows a random "thought" about a topic the user has actually finished.
This serves the full pool — one entry per concept of every completed lesson —
so the client can pick + de-dupe without re-deriving definitions from the
glossary.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.models import User
from app.schemas import CatThoughtOut
from app.services import content as content_service

router = APIRouter()


@router.get("/cat/thoughts", response_model=list[CatThoughtOut])
async def cat_thoughts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Topics from the user's completed lessons (one per concept)."""
    return await content_service.get_cat_thoughts(session, user_id=user.id)
