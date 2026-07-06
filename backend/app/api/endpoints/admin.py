"""Admin endpoints: per-user stats + manual pet override. Gated by ADMIN_EMAILS."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin
from app.database import get_session
from app.schemas import AdminUserDetailOut, AdminUsersOut, PetStateOut, PetStateUpdate
from app.services import admin as admin_service

router = APIRouter(dependencies=[Depends(get_current_admin)])


@router.get("/admin/users", response_model=AdminUsersOut)
async def list_users(session: AsyncSession = Depends(get_session)):
    return await admin_service.list_users(session)


@router.get("/admin/users/{user_id}", response_model=AdminUserDetailOut)
async def user_detail(user_id: int, session: AsyncSession = Depends(get_session)):
    return await admin_service.get_user_detail(session, user_id)


@router.patch("/admin/users/{user_id}/pet", response_model=PetStateOut)
async def update_user_pet(
    user_id: int,
    data: PetStateUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await admin_service.update_pet(session, user_id, data)
