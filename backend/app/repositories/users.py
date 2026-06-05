"""User repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get_by_id(self, user_id: int) -> User | None:
        return (
            await self.session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        return (
            await self.session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    async def create(self, *, email: str, password_hash: str, display_name: str) -> User:
        user = User(
            email=email, password_hash=password_hash, display_name=display_name
        )
        self.session.add(user)
        return user
