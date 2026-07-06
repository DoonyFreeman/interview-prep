"""Admin service: cross-user stats rollup + manual pet override.

Reads reuse the existing per-user services (progress overview, tests overview)
in a loop — plenty for a private app with a handful of users.
The pet write deliberately skips the unlock clamps of ``pet.update``: the admin
is the source of truth (e.g. restoring a lost streak).
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import AttemptRepository, PetStateRepository, UserRepository
from app.schemas import (
    AdminUserDetailOut,
    AdminUserOut,
    AdminUsersOut,
    PetStateOut,
    PetStateUpdate,
    ProgressOverviewOut,
    TestsOverviewOut,
)
from app.services import lesson_test, progress
from app.services.pet import _pet_out

_DEFAULT_PET = PetStateOut(
    name="",
    skin="classic",
    hat=None,
    streak=0,
    best_streak=0,
    last_active_day=None,
    hidden=False,
)


async def _user_summary(
    session: AsyncSession, user: User
) -> tuple[AdminUserOut, ProgressOverviewOut, TestsOverviewOut]:
    pet = await PetStateRepository(session).get(user.id)
    overview = await progress.get_overview(session, user_id=user.id)
    tests = await lesson_test.tests_overview(session, user.id)
    attempts_count, avg_score = await AttemptRepository(session).count_and_avg_for_user(
        user.id
    )
    lessons = [lesson for course in overview.courses for lesson in course.lessons]
    out = AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        pet=_pet_out(pet) if pet else _DEFAULT_PET,
        total_concepts=overview.total_concepts,
        attempted_concepts=overview.attempted_concepts,
        mastered_concepts=overview.mastered_concepts,
        total_lessons=len(lessons),
        completed_lessons=sum(lesson.completed for lesson in lessons),
        tests_total=tests.total,
        tests_passed=tests.passed,
        attempts_count=attempts_count,
        avg_score=avg_score,
    )
    return out, overview, tests


async def list_users(session: AsyncSession) -> AdminUsersOut:
    # ponytail: N+1 rollup per user — fine for <10 users, paginate if that grows
    users = await UserRepository(session).list_all()
    return AdminUsersOut(users=[(await _user_summary(session, u))[0] for u in users])


async def get_user_detail(session: AsyncSession, user_id: int) -> AdminUserDetailOut:
    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    out, overview, tests = await _user_summary(session, user)
    return AdminUserDetailOut(user=out, progress=overview, tests=tests)


async def update_pet(
    session: AsyncSession, user_id: int, data: PetStateUpdate
) -> PetStateOut:
    if await UserRepository(session).get_by_id(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    repo = PetStateRepository(session)
    pet = await repo.get(user_id)
    if pet is None:
        pet = repo.create(user_id=user_id)
        await session.flush()

    fields = data.model_dump(exclude_unset=True)
    for field, value in fields.items():
        # hat / last_active_day are nullable — an explicit null clears them
        if value is None and field not in ("hat", "last_active_day"):
            continue
        if field in ("streak", "best_streak"):
            value = max(0, value)
        setattr(pet, field, value)

    # The one invariant kept even for admins: best_streak >= streak.
    pet.best_streak = max(pet.best_streak, pet.streak)
    await session.commit()
    await session.refresh(pet)
    return _pet_out(pet)
