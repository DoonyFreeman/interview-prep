"""Auth endpoints: register, login, me — thin wrappers over the auth service."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    ChangePasswordIn,
    LoginIn,
    RegisterIn,
    TokenOut,
    UpdateProfileIn,
    UserOut,
)
from app.database import get_session
from app.models import User
from app.services import auth as auth_service

router = APIRouter()


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
    )


@router.post(
    "/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED
)
async def register(data: RegisterIn, session: AsyncSession = Depends(get_session)):
    return await auth_service.register(session, data)


@router.post("/auth/login", response_model=TokenOut)
async def login(data: LoginIn, session: AsyncSession = Depends(get_session)):
    return await auth_service.login(session, data)


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.patch("/auth/me", response_model=UserOut)
async def update_me(
    data: UpdateProfileIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    updated = await auth_service.update_profile(session, user, data)
    return _user_out(updated)


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await auth_service.change_password(session, user, data)
