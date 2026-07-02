"""Global lesson search: public GET /api/search?q= over titles + lesson markdown."""
from __future__ import annotations


async def test_search_is_public_and_finds_gather(client):
    """"gather" must surface the asyncio tasks-gather lesson with a deep-link."""
    r = await client.get("/api/search", params={"q": "gather"})
    assert r.status_code == 200
    d = r.json()
    assert d["query"] == "gather"
    assert d["count"] == len(d["results"]) > 0

    hits = [x for x in d["results"] if x["lesson_slug"] == "tasks-gather"]
    assert hits, "tasks-gather lesson not found for 'gather'"
    top = hits[0]
    assert top["course_slug"] == "python-asyncio"
    assert top["course_title"]
    assert top["lesson_title"] == "Задачи, gather и отмена"
    assert "gather" in top["snippet"].lower()


async def test_search_title_match_ranks_above_body(client):
    """A lesson whose title contains the query outranks body-only matches."""
    d = (await client.get("/api/search", params={"q": "gather"})).json()
    first = d["results"][0]
    assert first["match_field"] == "lesson_title"
    assert first["lesson_slug"] == "tasks-gather"
    assert first["anchor"] == ""  # lesson-title match links to the lesson top


async def test_search_section_match_carries_anchor(client):
    """A section-heading match deep-links to that H2 anchor."""
    d = (await client.get("/api/search", params={"q": "as_completed"})).json()
    hit = next(
        x
        for x in d["results"]
        if x["lesson_slug"] == "tasks-gather" and x["match_field"] == "section_title"
    )
    assert hit["anchor"] == "gather-wait-ascompleted"
    assert hit["section_title"] == "gather, wait, as_completed"


async def test_search_short_query_rejected(client):
    r = await client.get("/api/search", params={"q": "a"})
    assert r.status_code == 422
    r = await client.get("/api/search")  # q is required
    assert r.status_code == 422


async def test_search_no_results_shape(client):
    d = (await client.get("/api/search", params={"q": "zzzqqqxxywy"})).json()
    assert d == {"query": "zzzqqqxxywy", "count": 0, "results": []}


async def test_search_results_are_capped(client):
    """A very common word must not dump the whole curriculum."""
    d = (await client.get("/api/search", params={"q": "python"})).json()
    assert 0 < d["count"] <= 20


async def test_search_cyrillic_is_case_insensitive(client):
    lower = (await client.get("/api/search", params={"q": "декоратор"})).json()
    upper = (await client.get("/api/search", params={"q": "ДЕКОРАТОР"})).json()
    assert lower["count"] > 0
    assert upper["count"] == lower["count"]
    assert {(x["lesson_slug"], x["anchor"]) for x in upper["results"]} == {
        (x["lesson_slug"], x["anchor"]) for x in lower["results"]
    }


async def test_search_never_leaks_reference_answers(client):
    """Search reads titles + lesson markdown only — no question data at all."""
    r = await client.get("/api/search", params={"q": "gather"})
    assert "reference_answer" not in r.text


async def test_search_dedupes_by_lesson_and_anchor(client):
    """One row per (lesson, anchor): a title hit absorbs body hits of the same
    lesson top, a section hit absorbs body hits of the same section."""
    d = (await client.get("/api/search", params={"q": "gather"})).json()
    keys = [(x["lesson_slug"], x["anchor"]) for x in d["results"]]
    assert len(keys) == len(set(keys))
