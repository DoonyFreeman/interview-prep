"""Pet (corner cat) service: get-or-create the user's pet row + partial update.

Pure user-state, like the glossary stats. The daily-streak rollover is computed
client-side (it needs the user's *local* day); the server just stores the values
and enforces two invariants on write: ``skin`` must be one the user's
``best_streak`` has unlocked, and ``best_streak >= streak``.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PetState
from app.repositories import PetStateRepository
from app.schemas import PetStateOut, PetStateUpdate

# Skin → best-streak day it unlocks at. Mirrors the frontend SKIN_MILESTONES in
# lib/cat.ts (no shared code across the stack — keep the two in sync).
SKIN_MILESTONES: dict[str, int] = {
    "classic": 0,
    "tabby": 3,
    "tuxedo": 7,
    "calico": 14,
    "void": 30,
}


def skins_unlocked(best_streak: int) -> list[str]:
    return [s for s, at in SKIN_MILESTONES.items() if best_streak >= at]


def _pet_out(pet: PetState) -> PetStateOut:
    return PetStateOut(
        name=pet.name,
        skin=pet.skin,
        streak=pet.streak,
        best_streak=pet.best_streak,
        last_active_day=pet.last_active_day,
        hidden=pet.hidden,
    )


async def get_or_create(session: AsyncSession, user_id: int) -> PetStateOut:
    repo = PetStateRepository(session)
    pet = await repo.get(user_id)
    if pet is None:
        pet = repo.create(user_id=user_id)
        await session.commit()
        await session.refresh(pet)
    return _pet_out(pet)


async def visit(session: AsyncSession, user_id: int, today: str) -> PetStateOut:
    """Roll the daily streak for "the app was opened today" — atomically.

    Mirrors the client ``rolloverStreak`` (kept in sync, like SKIN_MILESTONES):
    same day → unchanged, next day → +1, gap ≥ 2 or clock-backwards → reset to 1
    (today still counts). Done in one server call so a daily visit can't be lost
    to an optimistic-write rollback or a race with other pet PATCHes.
    """
    repo = PetStateRepository(session)
    pet = await repo.get(user_id)
    if pet is None:
        pet = repo.create(user_id=user_id)
        await session.flush()

    if pet.last_active_day != today:
        if pet.last_active_day is None:
            pet.streak = 1
        else:
            gap = (date.fromisoformat(today) - date.fromisoformat(pet.last_active_day)).days
            pet.streak = pet.streak + 1 if gap == 1 else 1
        pet.last_active_day = today
        pet.best_streak = max(pet.best_streak, pet.streak)

    await session.commit()
    await session.refresh(pet)
    return _pet_out(pet)


async def update(
    session: AsyncSession, user_id: int, data: PetStateUpdate
) -> PetStateOut:
    repo = PetStateRepository(session)
    pet = await repo.get(user_id)
    if pet is None:
        pet = repo.create(user_id=user_id)
        await session.flush()

    fields = data.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        pet.name = fields["name"].strip()[:40]
    if "streak" in fields and fields["streak"] is not None:
        pet.streak = max(0, fields["streak"])
    if "best_streak" in fields and fields["best_streak"] is not None:
        pet.best_streak = max(0, fields["best_streak"])
    if "last_active_day" in fields:
        pet.last_active_day = fields["last_active_day"]
    if "hidden" in fields and fields["hidden"] is not None:
        pet.hidden = fields["hidden"]

    # Invariants: best_streak never below the current streak, then clamp the
    # chosen skin to what that best_streak has unlocked.
    pet.best_streak = max(pet.best_streak, pet.streak)
    if "skin" in fields and fields["skin"] is not None:
        wanted = fields["skin"]
        if wanted in skins_unlocked(pet.best_streak):
            pet.skin = wanted
    if pet.skin not in skins_unlocked(pet.best_streak):
        pet.skin = "classic"

    await session.commit()
    await session.refresh(pet)
    return _pet_out(pet)
