"""PetState repository — one row per user for the corner cat."""
from __future__ import annotations

from app.models import PetState
from app.repositories.base import BaseRepository


class PetStateRepository(BaseRepository[PetState]):
    model = PetState

    async def get(self, user_id: int) -> PetState | None:
        """The user's pet row (one per user, by ``user_id`` — not the PK)."""
        return await self.find_one_by(user_id=user_id)

    def create(self, *, user_id: int) -> PetState:
        pet = PetState(user_id=user_id)
        self.add(pet)
        return pet
