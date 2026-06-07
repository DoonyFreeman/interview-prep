"""Repositories for the glossary reference section + per-user quiz stats."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select

from app.models import GlossaryTerm, GlossaryTermStat, _utcnow
from app.repositories.base import BaseRepository


class GlossaryRepository(BaseRepository[GlossaryTerm]):
    model = GlossaryTerm

    async def list_terms(
        self,
        category: str | None = None,
        q: str | None = None,
        kind: str = "reference",
    ) -> list[GlossaryTerm]:
        """Terms of one kind ("reference" or "slang"), optionally filtered by
        category and/or a search string.

        Search matches term/slug/aliases/body (aliases are stored as JSON text, so
        a LIKE over it works for the common case). Ordered by category then the
        authored order_index for stable grouping on the client.
        """
        stmt = select(GlossaryTerm).where(GlossaryTerm.kind == kind)
        if category:
            stmt = stmt.where(GlossaryTerm.category == category)
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    GlossaryTerm.term.ilike(like),
                    GlossaryTerm.slug.ilike(like),
                    GlossaryTerm.aliases.ilike(like),
                    GlossaryTerm.short_md.ilike(like),
                )
            )
        stmt = stmt.order_by(GlossaryTerm.category, GlossaryTerm.order_index)
        return await self._all(stmt)

    async def get_by_slug(self, slug: str) -> GlossaryTerm | None:
        return await self.find_one_by(slug=slug)

    async def all_slugs(self) -> set[str]:
        """Valid term slugs — used to ignore unknown slugs in posted results."""
        return set(
            (await self.session.execute(select(GlossaryTerm.slug))).scalars().all()
        )


class GlossaryStatsRepository(BaseRepository[GlossaryTermStat]):
    """Per-user quiz stats for glossary terms. Flushes but never commits."""

    model = GlossaryTermStat

    async def list_for_user(self, user_id: int) -> list[GlossaryTermStat]:
        return await self.list_by(user_id=user_id)

    async def record(
        self,
        *,
        user_id: int,
        term_slug: str,
        correct: bool,
        now: datetime | None = None,
    ) -> GlossaryTermStat:
        """Upsert one term result: bump seen/correct, set last_correct/last_seen."""
        now = now or _utcnow()
        stat = await self.find_one_by(user_id=user_id, term_slug=term_slug)
        if stat is None:
            stat = GlossaryTermStat(
                user_id=user_id, term_slug=term_slug, seen=0, correct=0
            )
            self.add(stat)
        stat.seen += 1
        stat.correct += 1 if correct else 0
        stat.last_correct = correct
        stat.last_seen_at = now
        await self.session.flush()
        return stat
