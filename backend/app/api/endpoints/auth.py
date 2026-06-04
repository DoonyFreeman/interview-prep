"""Auth endpoints: register, login, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.auth.security import hash_password, verify_password
from app.auth.tokens import create_access_token
from app.database import get_session
from app.models import User

router = APIRouter()


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, session: AsyncSession = Depends(get_session)):
    exists = (
        await session.execute(select(User).where(User.email == data.email))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/auth/login", response_model=TokenOut)
async def login(data: LoginIn, session: AsyncSession = Depends(get_session)):
    user = (
        await session.execute(select(User).where(User.email == data.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, display_name=user.display_name)
