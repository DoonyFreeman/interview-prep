"""Generic Data-Mapper base for the repository layer.

SQLAlchemy's ORM is itself an implementation of the **Data Mapper** pattern: it
maps plain mapped classes (``app.models``) to/from rows without those classes
carrying any persistence logic (unlike Active Record). This ``BaseRepository`` is
the thin, reusable access layer sitting on that mapper — parameterised by the
mapped class (``BaseRepository[User]``) so every concrete repository inherits the
common primitives:

* :meth:`get` — fetch by primary key via the session identity map,
* :meth:`find_one_by` / :meth:`list_by` — equality filtering by mapped attribute,
* :meth:`add` — stage a new instance,

and only writes the queries that are genuinely bespoke (joins, eager loads,
search, aggregates).

Repositories ``add``/``flush`` but never ``commit`` — the calling service owns the
transaction boundary, so one service method can persist across several
repositories atomically.
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Holds the active session and the common mapper primitives.

    Concrete subclasses bind a mapped class via the :attr:`model` class attribute
    and add intent-revealing query methods on top.
    """

    #: The mapped class this repository maps. Set by every concrete subclass.
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- staging ---------------------------------------------------------- #
    def add(self, instance: object) -> None:
        """Stage a new/owned instance. The calling service commits."""
        self.session.add(instance)

    # -- execution helpers (cut the execute/scalars boilerplate) ---------- #
    async def _one(self, stmt: Select) -> ModelT | None:
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _all(self, stmt: Select) -> list[ModelT]:
        return list((await self.session.execute(stmt)).scalars().all())

    # -- generic mapper primitives ---------------------------------------- #
    async def get(self, id_: Any) -> ModelT | None:
        """Fetch by primary key (consults the session identity map first)."""
        return await self.session.get(self.model, id_)

    async def find_one_by(self, **filters: Any) -> ModelT | None:
        """First row whose mapped attributes equal ``filters`` (or ``None``)."""
        return await self._one(self._select_where(**filters))

    async def list_by(self, *, order_by: Any = None, **filters: Any) -> list[ModelT]:
        """All rows whose mapped attributes equal ``filters``, optionally ordered."""
        stmt = self._select_where(**filters)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return await self._all(stmt)

    def _select_where(self, **filters: Any) -> Select:
        stmt = select(self.model)
        for attr, value in filters.items():
            stmt = stmt.where(getattr(self.model, attr) == value)
        return stmt
