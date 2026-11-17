from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest

from app.assistant.retrieval import (
    LessonHit,
    LessonRetriever,
    RetrievalUnavailable,
    build_index,
    reciprocal_rank_fusion,
)


class FakeEmbedder:
    def __init__(self) -> None:
        self.fingerprint = "fake-v1"
        self.passages: list[str] = []
        self.queries: list[str] = []

    def embed(self, texts: list[str], *, passage: bool):
        (self.passages if passage else self.queries).extend(texts)
        vectors = []
        for text in texts:
            if "asyncio.gather" in text or "несколько корутин" in text:
                vectors.append([1, 0, 0])
            elif "таймаут" in text:
                vectors.append([0, 1, 0])
            elif "unrelated" in text:
                vectors.append([-1, -1, -1])
            else:
                vectors.append([0, 0, 1])
        return np.asarray(vectors, dtype=np.float32)


def _write_course(root: Path, slug: str, lessons: dict[str, str]) -> Path:
    course = root / "courses" / slug
    course.mkdir(parents=True)
    (course / "metadata.json").write_text(json.dumps({
        "slug": slug,
        "title": slug,
        "lessons": [
            {"slug": lesson, "title": lesson, "file": f"{lesson}.md"}
            for lesson in lessons
        ],
    }))
    for lesson, markdown in lessons.items():
        (course / f"{lesson}.md").write_text(markdown, encoding="utf-8")
    # Broken JSON would fail if the Markdown-only path opened these banks.
    for name in ("questions.json", "tests.json", "exam.json", "draft.md"):
        (course / name).write_text("answerbanksecret")
    return course


@pytest.fixture
def corpus(tmp_path):
    _write_course(tmp_path, "python", {
        "tasks": """# Tasks introduction

## Запуск `asyncio.gather`

Запускает несколько корутин совместно.

````python
## This is Python, not a lesson heading
asyncio.gather(first(), second())
````

> ~~~~hr-answers
> privatehrsecret
> ~~~~

- ```solution
    exercisekeysecret
    ```

```solution
    ```
notactuallyclosingsecret
```

## Ожидание

Как работает таймаут.
""",
        "interop": """## Extension APIs

Связывает C++ и Python.

```answer-key
answerkeysecret
```
""",
    })
    _write_course(tmp_path, "service", {
        "tasks": "## Обработка событий\n\nКорутины: asyncio.gather.",
    })
    index = tmp_path / "lessons.sqlite3"
    model_dir = tmp_path / "model"
    embedder = FakeEmbedder()
    stats = build_index(tmp_path, model_dir, index, embedder=embedder)
    retriever = LessonRetriever(index, model_dir, content_dir=tmp_path, embedder=embedder)
    return index, model_dir, embedder, retriever, stats


def test_hybrid_uses_lexical_dense_and_preserves_anchored_code(corpus):
    index, _, embedder, retriever, stats = corpus
    assert stats == {"lessons": 3, "chunks": 5}
    assert index.stat().st_mode & 0o222 == 0
    assert not embedder.queries
    retriever.validate()
    assert not embedder.queries

    result = retriever.rank("asyncio.gather", course_slug="python", lesson_slug="tasks")
    hit, = result.hybrid
    assert result.lexical == result.dense == (hit,)
    assert (hit.course_slug, hit.lesson_slug, hit.anchor) == ("python", "tasks", "запуск-asynciogather")
    assert hit.title == "Запуск asyncio.gather"
    assert "````python\n## This is Python, not a lesson heading" in hit.text
    assert "asyncio.gather(first(), second())\n````" in hit.text
    assert retriever.read_section(hit.chunk_id) == hit

    paraphrase = retriever.rank("несколько корутин", course_slug="python")
    assert paraphrase.hybrid[0] == hit
    lexical = retriever.rank('C++ " OR ()*', dense_limit=0)
    assert [item.lesson_slug for item in lexical.lexical] == ["interop"]
    assert [item.course_slug for item in retriever.search("asyncio.gather", lesson_slug="tasks")] == [
        "python", "service",
    ]


def test_index_and_embeddings_exclude_private_slots_and_answer_keys(corpus):
    index, _, embedder, retriever, _ = corpus
    excluded = (
        "privatehrsecret", "exercisekeysecret", "notactuallyclosingsecret", "answerkeysecret", "answerbanksecret",
    )
    assert not any(token in text for token in excluded for text in embedder.passages)
    with closing(sqlite3.connect(index)) as connection:
        stored = [row[0] for row in connection.execute("SELECT text FROM chunks")]
    assert not any(token in text for token in excluded for text in stored)
    assert retriever.search("...", limit=5) == []
    assert retriever.search("unrelated") == []
    assert retriever.search("таймаут", course_slug="missing") == []
    assert retriever.read_section("missing") is None


@pytest.mark.parametrize("language", ["solution", "solution.md", r"hr-answers\.md", "solution&#x2e;md"])
def test_excluded_fence_after_implicit_quote_close_uses_rendered_language(tmp_path, language):
    markdown = (
        "> ```text\n> displayed-code\n\n"
        "## Heading\n\nPublic theory.\n\n"
        f"```{language}\nprotectedmarker\n```\n\n"
        "Public follow-up."
    )
    _write_course(tmp_path, "python", {"tasks": markdown})
    index = tmp_path / "lessons.sqlite3"
    embedder = FakeEmbedder()
    build_index(tmp_path, tmp_path, index, embedder=embedder)
    retriever = LessonRetriever(index, tmp_path, content_dir=tmp_path, embedder=embedder)

    assert not any("protectedmarker" in passage for passage in embedder.passages)
    assert retriever.rank("protectedmarker", dense_limit=0).lexical == ()
    heading, = retriever.rank("public", dense_limit=0).hybrid
    assert heading.anchor == "heading"
    assert "Public theory." in heading.text and "Public follow-up." in heading.text
    assert "displayed-code" in retriever.rank("displayed-code", dense_limit=0).hybrid[0].text


def test_index_rejects_non_markdown_and_out_of_course_sources(tmp_path):
    course = _write_course(tmp_path, "python", {"tasks": "# Tasks"})
    meta_path = course / "metadata.json"
    metadata = json.loads(meta_path.read_text())
    for path in ("questions.json", "../../../outside.md"):
        metadata["lessons"][0]["file"] = path
        meta_path.write_text(json.dumps(metadata))
        if path.endswith(".md"):
            (tmp_path.parent / "outside.md").write_text("outside-private-content")
        with pytest.raises(ValueError, match="Markdown in its course directory"):
            build_index(tmp_path, tmp_path, tmp_path / "lessons.sqlite3", embedder=FakeEmbedder())


def test_stale_index_fails_closed_and_atomic_rebuild_preserves_ids(tmp_path, corpus):
    index, model_dir, embedder, retriever, _ = corpus
    hit, = retriever.search("таймаут", course_slug="python")
    lesson_path = tmp_path / "courses" / "python" / "tasks.md"
    lesson_path.write_text(lesson_path.read_text() + "\nБолее свежая теория.", encoding="utf-8")
    with pytest.raises(RetrievalUnavailable, match="current lessons"):
        retriever.read_section(hit.chunk_id)

    build_index(tmp_path, model_dir, index, embedder=embedder)
    new_hit = retriever.read_section(hit.chunk_id)
    assert new_hit and "Более свежая теория." in new_hit.text
    embedder.fingerprint = "fake-v2"
    with pytest.raises(RetrievalUnavailable, match="embedding model"):
        retriever.search("таймаут")


def test_build_failure_preserves_existing_index(tmp_path, corpus):
    index, model_dir, _, retriever, _ = corpus
    old_bytes = index.read_bytes()
    embedder = FakeEmbedder()
    embedder.embed = lambda texts, passage: np.zeros((len(texts), 3), dtype=np.float32)
    with pytest.raises(RetrievalUnavailable, match="invalid vector"):
        build_index(tmp_path, model_dir, index, embedder=embedder)
    assert index.read_bytes() == old_bytes
    assert list(tmp_path.glob("lessons.sqlite3*")) == [index]
    retriever.validate()


def test_rrf_breaks_ties_by_chunk_id_and_deduplicates_rankings():
    a, b, c = [LessonHit(id_, "course", "lesson", "anchor", "Title", "text") for id_ in "abc"]
    assert reciprocal_rank_fusion([b, b, a], [c, a]) == (a, b, c)


def test_search_diversifies_sections_and_read_expands_around_the_matched_chunk(tmp_path):
    blocks = [
        f"```python\n# FOCUS-{i:02d}\n"
        + "asyncio.gather(first(), second(), timeout_override=True)\n" * 20
        + "```"
        for i in range(10)
    ]
    markdown = "## asyncio.gather\n\n" + "\n\n".join(blocks)
    markdown += "\n\n## Другой раздел\n\nБольше примеров: asyncio.gather."
    _write_course(tmp_path, "python", {"tasks": markdown})
    index = tmp_path / "lessons.sqlite3"
    embedder = FakeEmbedder()
    build_index(tmp_path, tmp_path, index, embedder=embedder)
    retriever = LessonRetriever(index, tmp_path, content_dir=tmp_path, embedder=embedder)

    run = retriever.rank("asyncio.gather")
    assert len(run.lexical) == 11
    assert [hit.anchor for hit in run.hybrid] == ["asynciogather", "другой-раздел"]
    focus = next(hit for hit in run.lexical if "FOCUS-04" in hit.text)
    expanded = retriever.read_section(focus.chunk_id)
    assert expanded and expanded.chunk_id == focus.chunk_id
    assert focus.text in expanded.text and "FOCUS-03" in expanded.text and "FOCUS-05" in expanded.text
    assert "Другой раздел" not in expanded.text
    assert expanded.text.count("\n```") - expanded.text.count("\n```python") == expanded.text.count("```python")
    assert len(expanded.text) <= 6500
    assert len(json.dumps(expanded.text, ensure_ascii=False).encode()) < 24_000


def test_missing_runtime_artifacts_fail_closed(tmp_path):
    index = tmp_path / "missing.sqlite3"
    retriever = LessonRetriever(index, tmp_path, content_dir=tmp_path)
    with pytest.raises(RetrievalUnavailable):
        retriever.validate()
    with pytest.raises(RetrievalUnavailable):
        retriever.search("a query")
    assert not index.exists()


def test_search_reads_langchain_and_langgraph_spoken_spellings(tmp_path):
    _write_course(tmp_path, "llm", {
        "langchain": "## LangChain\n\nИнтерфейс к моделям и готовые агенты.",
        "langgraph": "## LangGraph\n\nГраф исполнения со своим состоянием.",
    })
    embedder = FakeEmbedder()
    index = tmp_path / "index.sqlite3"
    model_dir = tmp_path / "model"
    build_index(tmp_path, model_dir, index, embedder=embedder)
    retriever = LessonRetriever(index, model_dir, content_dir=tmp_path, embedder=embedder)

    for query, slug in (("Lang chain", "langchain"), ("lang Graph", "langgraph")):
        result = retriever.rank(query, dense_limit=0)
        assert result.lexical[0].lesson_slug == slug
