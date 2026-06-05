"""Glossary service: public reference-term reads (no LLM, no auth).

Terms mirror ``content/glossary.json``; ``aliases``/``links`` are decoded from
their stored JSON here. The canonical category order is recovered from the
authored ``order_index`` (terms are seeded category-contiguous), so neither the
service nor the client has to hardcode the category list.
"""
from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlossaryTerm
from app.repositories import GlossaryRepository
from app.schemas import GlossaryLinkOut, GlossaryListOut, GlossaryTermOut


def _to_out(term: GlossaryTerm) -> GlossaryTermOut:
    return GlossaryTermOut(
        slug=term.slug,
        term=term.term,
        category=term.category,
        short_md=term.short_md,
        aliases=json.loads(term.aliases or "[]"),
        links=[GlossaryLinkOut(**ln) for ln in json.loads(term.links or "[]")],
    )


async def list_glossary(
    session: AsyncSession,
    category: str | None = None,
    q: str | None = None,
    kind: str = "reference",
) -> GlossaryListOut:
    terms = await GlossaryRepository(session).list_terms(
        category=category, q=q, kind=kind
    )

    # Canonical category order = order of first appearance by authored order_index.
    first_seen: dict[str, int] = {}
    for t in terms:
        if t.category not in first_seen:
            first_seen[t.category] = t.order_index
    categories = sorted(first_seen, key=lambda c: first_seen[c])
    rank = {c: i for i, c in enumerate(categories)}

    ordered = sorted(terms, key=lambda t: (rank[t.category], t.order_index))
    return GlossaryListOut(
        count=len(ordered),
        categories=categories,
        terms=[_to_out(t) for t in ordered],
    )


async def get_term(session: AsyncSession, slug: str) -> GlossaryTermOut:
    term = await GlossaryRepository(session).get_by_slug(slug)
    if term is None:
        raise HTTPException(status_code=404, detail="Term not found")
    return _to_out(term)
