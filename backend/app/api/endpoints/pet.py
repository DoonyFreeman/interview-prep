"""Pet (corner cat) endpoints (auth-gated): read + partial update.

The streak rollover is done client-side (local day); these routes just persist
the per-user pet state so name/skin/streak survive across devices.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_session
from app.models import User
from app.schemas import PetStateOut, PetStateUpdate
from app.services import pet as pet_service

router = APIRouter()


@router.get("/pet", response_model=PetStateOut)
async def get_pet(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """The current user's pet state (lazily created with defaults)."""
    return await pet_service.get_or_create(session, user_id=user.id)


@router.patch("/pet", response_model=PetStateOut)
async def update_pet(
    data: PetStateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update name / skin / streak / visibility (skin clamped to unlocked)."""
    return await pet_service.update(session, user_id=user.id, data=data)
