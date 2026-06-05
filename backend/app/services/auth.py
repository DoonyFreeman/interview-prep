"""Auth service: registration, login, and current-user lookup.

Wraps the password hashing (`auth/security.py`), token issuing (`auth/tokens.py`)
and the user repository so endpoints and the `get_current_user` dependency stay
thin and free of direct queries.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    ChangePasswordIn,
    LoginIn,
    RegisterIn,
    TokenOut,
    UpdateProfileIn,
)
from app.auth.security import hash_password, verify_password
from app.auth.tokens import create_access_token
from app.models import User
from app.repositories import UserRepository


async def register(session: AsyncSession, data: RegisterIn) -> TokenOut:
    repo = UserRepository(session)
    if await repo.get_by_email(data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    user = await repo.create(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    await session.commit()
    await session.refresh(user)
    return TokenOut(access_token=create_access_token(str(user.id)))


async def login(session: AsyncSession, data: LoginIn) -> TokenOut:
    user = await UserRepository(session).get_by_email(data.email)
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenOut(access_token=create_access_token(str(user.id)))


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await UserRepository(session).get_by_id(user_id)


async def update_profile(
    session: AsyncSession, user: User, data: UpdateProfileIn
) -> User:
    """Update the current user's editable profile fields (display name)."""
    user.display_name = data.display_name
    await session.commit()
    await session.refresh(user)
    return user


async def change_password(
    session: AsyncSession, user: User, data: ChangePasswordIn
) -> None:
    """Change the password after verifying the current one."""
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(data.new_password)
    await session.commit()
