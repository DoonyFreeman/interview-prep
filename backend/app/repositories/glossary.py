"""Repository for the glossary reference section."""
from __future__ import annotations

from sqlalchemy import or_, select

from app.models import GlossaryTerm
from app.repositories.base import BaseRepository


class GlossaryRepository(BaseRepository):
    async def list_terms(
        self, category: str | None = None, q: str | None = None
    ) -> list[GlossaryTerm]:
        """All terms, optionally filtered by category and/or a search string.

        Search matches term/slug/aliases/body (aliases are stored as JSON text, so
        a LIKE over it works for the common case). Ordered by category then the
        authored order_index for stable grouping on the client.
        """
        stmt = select(GlossaryTerm)
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
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_slug(self, slug: str) -> GlossaryTerm | None:
        return (
            await self.session.execute(
                select(GlossaryTerm).where(GlossaryTerm.slug == slug)
            )
        ).scalar_one_or_none()
