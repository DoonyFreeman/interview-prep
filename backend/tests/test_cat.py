"""Tests for the corner-cat thought pool: the H2-excerpt parser + the endpoint.

The cat shows topics from lessons the user marked complete. We assert the pool
spans completed lessons (not just glossary-matched concepts), excludes
unfinished lessons, and never yields an empty key/term.
"""
from __future__ import annotations

from app.content.excerpt import extract_h2_excerpts, slugify

CREDS = {"email": "cat@example.com", "password": "supersecret123"}


# --- extract_h2_excerpts ----------------------------------------------------


def test_extract_h2_excerpts_basic():
    md = (
        "# Lesson title\n\n"
        "Intro paragraph before any H2.\n\n"
        "## Что такое GIL\n\n"
        "GIL — это **глобальная** блокировка интерпретатора, "
        "которая защищает доступ к объектам.\n\n"
        "More detail here.\n\n"
        "## Второй раздел\n\n"
        "Короткий абзац про второй раздел и его особенности.\n"
    )
    out = extract_h2_excerpts(md)
    assert slugify("Что такое GIL") in out
    assert slugify("Второй раздел") in out
    # First prose paragraph, markdown stripped (** removed).
    first = out[slugify("Что такое GIL")]
    assert first.startswith("GIL — это глобальная блокировка")
    assert "**" not in first


def test_extract_h2_excerpts_skips_code_and_lists():
    md = (
        "## Только код\n\n"
        "```python\n"
        "x = 1  # this is not prose\n"
        "```\n\n"
        "## Со списком\n\n"
        "- bullet one\n"
        "- bullet two\n\n"
        "Настоящий абзац идёт после списка и достаточно длинный для excerpt.\n"
    )
    out = extract_h2_excerpts(md)
    # Code-only section → empty excerpt.
    assert out[slugify("Только код")] == ""
    # List skipped, real paragraph picked.
    assert out[slugify("Со списком")].startswith("Настоящий абзац")


def test_extract_h2_excerpts_truncates():
    long_para = "слово " * 100
    md = f"## Раздел\n\n{long_para}\n"
    out = extract_h2_excerpts(md, max_chars=50)
    excerpt = out[slugify("Раздел")]
    assert len(excerpt) <= 51  # 50 + the ellipsis char
    assert excerpt.endswith("…")


def test_extract_h2_excerpts_joins_wrapped_paragraph():
    # Markdown soft-wraps a paragraph across lines; the excerpt must join them
    # and end on a full sentence, not at the first line break.
    md = (
        "## int произвольной точности\n\n"
        "В Python `int` имеет **произвольную точность** — он ограничен только памятью, а не\n"
        "размером машинного слова (нет «64-битного предела», нет переполнения). Большие\n"
        "числа просто работают:\n\n"
        "```python\n"
        "x = 2 ** 1000\n"
        "```\n"
    )
    out = extract_h2_excerpts(md)
    excerpt = out[slugify("int произвольной точности")]
    # Joined across the wrapped lines (no truncation at "а не").
    assert "ограничен только памятью, а не размером машинного слова" in excerpt
    # Ends cleanly, never mid-word and never with a dangling colon.
    assert not excerpt.endswith("а не")
    assert not excerpt.endswith(":")


def test_truncate_keeps_whole_sentences():
    long = (
        "## Раздел\n\n"
        "Первое предложение про тему достаточно длинное и понятное. "
        "Второе предложение добавляет деталей и тоже немаленькое по длине. "
        "Третье предложение здесь уже лишнее для короткого пузыря кота.\n"
    )
    out = extract_h2_excerpts(long, max_chars=80)
    excerpt = out[slugify("Раздел")]
    # Cut on a sentence boundary — ends with '.', not mid-word.
    assert excerpt.endswith(".")
    assert "Первое предложение" in excerpt


def test_extract_h2_excerpts_ignores_h3():
    md = (
        "## Главный раздел\n\n"
        "Это вводный абзац главного раздела, он достаточно длинный.\n\n"
        "### Подраздел\n\n"
        "Текст подраздела.\n"
    )
    out = extract_h2_excerpts(md)
    assert slugify("Подраздел") not in out
    assert slugify("Главный раздел") in out


# --- endpoint ---------------------------------------------------------------


async def _auth(client) -> dict[str, str]:
    r = await client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_cat_thoughts_empty_without_completed(client):
    headers = await _auth(client)
    r = await client.get("/api/cat/thoughts", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


async def test_cat_thoughts_requires_auth(client):
    r = await client.get("/api/cat/thoughts")
    assert r.status_code in (401, 403)


async def test_cat_thoughts_covers_completed_lesson(client):
    headers = await _auth(client)
    # Mark python-core/gil complete.
    r = await client.post(
        "/api/progress/courses/python-core/lessons/gil",
        json={"completed": True},
        headers=headers,
    )
    assert r.status_code == 204

    r = await client.get("/api/cat/thoughts", headers=headers)
    assert r.status_code == 200
    thoughts = r.json()
    assert thoughts, "completed lesson should produce thoughts"
    # One entry per concept; all from the completed lesson.
    for t in thoughts:
        assert t["key"], "thought must have a stable key"
        assert t["term"], "thought must have a term/title"
        assert t["course_slug"] == "python-core"
        assert t["lesson_slug"] == "gil"
        assert t["key"] == f"python-core/gil#{t['anchor']}"
    # At least one concept carries a real definition from the markdown.
    assert any(t["definition"] for t in thoughts)


async def test_cat_thoughts_excludes_unfinished_lessons(client):
    headers = await _auth(client)
    # View (but do not complete) the lesson.
    r = await client.post(
        "/api/progress/courses/python-core/lessons/gil",
        json={"completed": False},
        headers=headers,
    )
    assert r.status_code == 204
    r = await client.get("/api/cat/thoughts", headers=headers)
    assert r.status_code == 200
    assert r.json() == []
