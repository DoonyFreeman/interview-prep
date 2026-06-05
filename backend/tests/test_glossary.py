"""Glossary seed + public read-endpoint tests against content/glossary.json."""
from __future__ import annotations

from sqlalchemy import func, select

from app.content.seed import seed_from_dir
from app.models import GlossaryTerm


async def test_seed_creates_glossary_terms(Session):
    async with Session() as s:
        await seed_from_dir(s)
    async with Session() as s:
        n = (
            await s.execute(select(func.count()).select_from(GlossaryTerm))
        ).scalar()
        gil = (
            await s.execute(select(GlossaryTerm).where(GlossaryTerm.slug == "gil"))
        ).scalar_one()
    assert n >= 100  # a substantial P0 glossary is seeded
    assert gil.category == "python"
    assert "GIL" in gil.term


async def test_seed_glossary_is_idempotent(Session):
    async with Session() as s:
        await seed_from_dir(s)
    async with Session() as s:
        first = (
            await s.execute(select(func.count()).select_from(GlossaryTerm))
        ).scalar()
    async with Session() as s:
        await seed_from_dir(s)  # re-seed must not duplicate
    async with Session() as s:
        second = (
            await s.execute(select(func.count()).select_from(GlossaryTerm))
        ).scalar()
    assert first == second


async def test_list_glossary_is_public(client):
    """No auth header is sent by the fixture client — the section is public."""
    r = await client.get("/api/glossary")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 100
    assert d["count"] == len(d["terms"])
    assert "python" in d["categories"]
    # Categories come back in canonical (authored) order, python first.
    assert d["categories"][0] == "python"


async def test_glossary_filter_by_category(client):
    r = await client.get("/api/glossary", params={"category": "databases"})
    assert r.status_code == 200
    d = r.json()
    assert d["count"] > 0
    assert all(t["category"] == "databases" for t in d["terms"])
    assert d["categories"] == ["databases"]


async def test_glossary_search_matches_term_and_aliases(client):
    by_term = await client.get("/api/glossary", params={"q": "GIL"})
    assert by_term.status_code == 200
    slugs = {t["slug"] for t in by_term.json()["terms"]}
    assert "gil" in slugs

    # "typing" is only an alias of the type-hints term, not in its title.
    by_alias = await client.get("/api/glossary", params={"q": "typing"})
    assert "type-hints" in {t["slug"] for t in by_alias.json()["terms"]}


async def test_get_term_with_links(client):
    r = await client.get("/api/glossary/gil")
    assert r.status_code == 200
    d = r.json()
    assert d["slug"] == "gil"
    assert d["short_md"]
    assert d["links"][0]["lesson_slug"] == "gil"
    assert d["links"][0]["anchor"]  # deep-link anchor present


async def test_get_unknown_term_404(client):
    r = await client.get("/api/glossary/does-not-exist")
    assert r.status_code == 404
