"""Test fixtures: isolated in-memory SQLite + seeded content + ASGI client.

Uses a StaticPool so the in-memory DB persists across connections within a test.
The app's lifespan (which would seed the real file DB) is intentionally NOT run —
ASGITransport skips it — so content is seeded into the test engine via fixtures.
"""
from __future__ import annotations

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.content.seed import seed_from_dir
from app.database import Base, get_session
from app.main import create_app


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def Session(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(Session):
    async with Session() as session:
        await seed_from_dir(session)

    app = create_app()

    async def _override_get_session():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
