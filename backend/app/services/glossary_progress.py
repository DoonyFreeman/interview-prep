"""Glossary quiz progress: record results + aggregate per-term/category stats.

Stats are user-state (per user, per term slug). A term is "mastered" when it's
been answered correctly at least twice and the last answer was correct. The
client builds quizzes and weights term selection from this data; the server only
stores counts and rolls them up.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlossaryTermStat
from app.repositories import GlossaryRepository, GlossaryStatsRepository
from app.schemas import (
    GlossaryCategoryProgressOut,
    GlossaryProgressOut,
    GlossaryTermStatOut,
)


def _is_mastered(stat: GlossaryTermStat) -> bool:
    return stat.correct >= 2 and stat.last_correct


def _stat_out(stat: GlossaryTermStat) -> GlossaryTermStatOut:
    return GlossaryTermStatOut(
        term_slug=stat.term_slug,
        seen=stat.seen,
        correct=stat.correct,
        last_correct=stat.last_correct,
        mastered=_is_mastered(stat),
        last_seen_at=stat.last_seen_at,
    )


async def _build_progress(
    session: AsyncSession, user_id: int, recorded: int = 0
) -> GlossaryProgressOut:
    terms = await GlossaryRepository(session).list_terms()
    stats = await GlossaryStatsRepository(session).list_for_user(user_id)

    slug_category = {t.slug: t.category for t in terms}

    # Canonical category order = first appearance by authored order_index.
    first_seen: dict[str, int] = {}
    cat_total: dict[str, int] = {}
    for t in terms:
        cat_total[t.category] = cat_total.get(t.category, 0) + 1
        if t.category not in first_seen:
            first_seen[t.category] = t.order_index
    ordered_categories = sorted(first_seen, key=lambda c: first_seen[c])

    cat_seen: dict[str, int] = {c: 0 for c in cat_total}
    cat_mastered: dict[str, int] = {c: 0 for c in cat_total}
    seen_total = 0
    mastered_total = 0
    for stat in stats:
        category = slug_category.get(stat.term_slug)
        if category is None:  # stale slug (term removed) — ignore in rollups
            continue
        if stat.seen > 0:
            cat_seen[category] += 1
            seen_total += 1
        if _is_mastered(stat):
            cat_mastered[category] += 1
            mastered_total += 1

    categories = [
        GlossaryCategoryProgressOut(
            category=c,
            total=cat_total[c],
            seen=cat_seen[c],
            mastered=cat_mastered[c],
        )
        for c in ordered_categories
    ]
    return GlossaryProgressOut(
        total=len(terms),
        seen=seen_total,
        mastered=mastered_total,
        recorded=recorded,
        categories=categories,
        terms=[_stat_out(s) for s in stats],
    )


async def get_progress(session: AsyncSession, user_id: int) -> GlossaryProgressOut:
    return await _build_progress(session, user_id)


async def record_results(
    session: AsyncSession,
    user_id: int,
    items: list[tuple[str, bool]],
) -> GlossaryProgressOut:
    """Record a finished quiz: one upsert per (term, correct). Unknown slugs are
    ignored. Commits once, then returns the refreshed progress."""
    repo = GlossaryRepository(session)
    stats_repo = GlossaryStatsRepository(session)
    valid = await repo.all_slugs()

    recorded = 0
    for term_slug, correct in items:
        if term_slug not in valid:
            continue
        await stats_repo.record(user_id=user_id, term_slug=term_slug, correct=correct)
        recorded += 1
    await session.commit()
    return await _build_progress(session, user_id, recorded=recorded)
