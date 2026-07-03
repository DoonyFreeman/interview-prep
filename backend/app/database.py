"""Async SQLAlchemy engine + session factory for SQLite.

SQLite is run in WAL mode with a busy timeout so concurrent reads don't block
on the single writer — plenty for a small private app, and it keeps the
backend light (no separate DB server).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Enable WAL + sane durability/concurrency pragmas on every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a transactional session."""
    async with SessionLocal() as session:
        yield session


def ensure_schema_upgrades(connection) -> None:
    """Apply additive, idempotent schema upgrades to an existing DB.

    We have no Alembic; ``create_all`` only creates *missing tables*, never new
    columns on tables that already exist. This adds columns introduced after a
    table shipped, so a live ``data/app.db`` (or the docker volume) picks them
    up without a rebuild and without touching existing rows. Only ever ADD a
    nullable column here — never drop or alter — so it's safe to re-run.

    Takes the sync SQLAlchemy ``Connection`` handed in by ``run_sync``.
    """
    existing = {
        row[1]
        for row in connection.exec_driver_sql("PRAGMA table_info(pet_state)").fetchall()
    }
    if existing and "hat" not in existing:
        connection.exec_driver_sql("ALTER TABLE pet_state ADD COLUMN hat VARCHAR(20)")


async def init_db() -> None:
    """Create all tables. Called from the app lifespan on startup."""
    # Import models so they register on Base.metadata before create_all.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_schema_upgrades)
