"""Auth endpoints: register, login, me — thin wrappers over the auth service."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.database import get_session
from app.models import User
from app.services import auth as auth_service

router = APIRouter()


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
    return UserOut(id=user.id, email=user.email, display_name=user.display_name)
