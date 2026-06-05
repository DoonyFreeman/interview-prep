"""Base class shared by all repositories."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Holds the active session. Subclasses add intent-revealing query methods.

    Repositories never commit — they ``add``/``flush`` and let the calling
    service own the transaction boundary.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, instance: object) -> None:
        self.session.add(instance)
