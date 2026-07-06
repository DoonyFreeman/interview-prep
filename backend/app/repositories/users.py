"""User repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.get(user_id)

    async def list_all(self) -> list[User]:
        return await self._all(select(User).order_by(User.id))

    async def get_by_email(self, email: str) -> User | None:
        return await self.find_one_by(email=email)

    async def create(self, *, email: str, password_hash: str, display_name: str) -> User:
        user = User(
            email=email, password_hash=password_hash, display_name=display_name
        )
        self.add(user)
        return user
