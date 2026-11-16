"""Build and query the local hybrid index of published lesson Markdown."""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
import hashlib
from html import unescape
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import TYPE_CHECKING
from uuid import uuid4

from app.assistant.embeddings import E5Embedder, Embedder, EmbeddingError
from app.content.excerpt import slugify
from app.content.loader import load_lesson_markdown

if TYPE_CHECKING:
    from numpy.typing import NDArray

INDEX_VERSION = "2"
DEFAULT_LEXICAL_CANDIDATES = 40
DEFAULT_DENSE_CANDIDATES = 20
DEFAULT_RRF_CONSTANT = 10
DEFAULT_LIMIT = 5
DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"
_TARGET_CHARS = 1000
_SECTION_MAX_CHARS = 6500
# Keep room for the surrounding tool-result envelope and metadata.
_SECTION_MAX_JSON_BYTES = 20_000
_RENDERED_FENCE_LANGUAGE = re.compile(r"language-([\w-]+)", re.ASCII)
_INLINE_LINK = re.compile(r"!?\[([^\]]+)\]\([^)]*\)")
_TERM = re.compile(r"[^\W_]+(?:[._:-][^\W_]+)*(?:\+\+|#)?", re.UNICODE)
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_EXCLUDED_FENCES = frozenset({
    "hr-answers", "private-hr", "solution", "answer-key", "answer-keys", "answers",
})


class RetrievalUnavailable(RuntimeError):
    """The configured lesson corpus, index or embedding model is unavailable."""


@dataclass(frozen=True)
class LessonHit:
    chunk_id: str
    course_slug: str
    lesson_slug: str
    anchor: str
    title: str
    text: str

    @property
    def section_key(self) -> tuple[str, str, str]:
        return self.course_slug, self.lesson_slug, self.anchor


@dataclass(frozen=True)
class RetrievalRun:
    lexical: tuple[LessonHit, ...] = ()
    dense: tuple[LessonHit, ...] = ()
    hybrid: tuple[LessonHit, ...] = ()


@dataclass(frozen=True)
class _Lesson:
    course_slug: str
    course_title: str
    lesson_slug: str
    lesson_title: str
    markdown: str


@dataclass(frozen=True)
class _Corpus:
    lessons: tuple[_Lesson, ...]
    fingerprint: str
    paths: tuple[Path, ...]


def _load_corpus(content_dir: Path) -> _Corpus:
    courses_dir = content_dir / "courses"
    course_dirs = sorted(path for path in courses_dir.iterdir() if path.is_dir())
    paths = {courses_dir, *course_dirs}
    paths.update(path / "metadata.json" for path in course_dirs if (path / "metadata.json").is_file())
    lessons = []
    keys: set[tuple[str, str]] = set()
    for course_slug, course_title, lesson in load_lesson_markdown(content_dir):
        key = (course_slug, lesson.slug)
        if key in keys:
            raise ValueError(f"Duplicate lesson in assistant corpus: {course_slug}/{lesson.slug}")
        keys.add(key)
        paths.add(Path(lesson.content_path))
        lessons.append(_Lesson(course_slug, course_title, lesson.slug, lesson.title, lesson.markdown))
    if not lessons:
        raise ValueError("The published lesson corpus is empty")

    digest = hashlib.sha256()
    lessons.sort(key=lambda lesson: (lesson.course_slug, lesson.lesson_slug))
    for lesson in lessons:
        fields = (lesson.course_slug, lesson.course_title, lesson.lesson_slug, lesson.lesson_title, lesson.markdown)
        digest.update(json.dumps(fields, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return _Corpus(tuple(lessons), digest.hexdigest(), tuple(sorted(paths)))


def _file_signatures(paths: tuple[Path, ...]) -> tuple[tuple[int, int, int, int, int], ...]:
    signatures = []
    for path in paths:
        info = path.stat()
        signatures.append((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns))
    return tuple(signatures)


def _sections(markdown: str) -> Iterable[tuple[str, list[str]]]:
    """Separate H2 sections and Markdown blocks, keeping complete code fences."""
    from markdown_it import MarkdownIt
    from markdown_it.common.utils import unescapeAll

    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    source_lines = markdown.split("\n")
    tokens = MarkdownIt("commonmark", {"maxNesting": 1000}).parse(markdown)
    code_ranges: dict[int, tuple[int, bool]] = {}
    headings: dict[int, tuple[int, str]] = {}
    for i, token in enumerate(tokens):
        if token.map is None:
            continue
        start, end = token.map
        if token.type == "fence":
            # Match the class and first language capture used by Markdown.tsx.
            info = unescapeAll(token.info.strip()).split(maxsplit=1)
            language = _RENDERED_FENCE_LANGUAGE.search("language-" + info[0]) if info else None
            excluded = language is not None and language[1].casefold() in _EXCLUDED_FENCES
            code_ranges[start] = (end, excluded)
        elif token.type == "code_block":
            code_ranges[start] = (end, False)
        elif token.type == "heading_open" and token.tag == "h2" and token.level == 0:
            # Keep identifiers such as __repr__ in titles and passage embeddings.
            text = unescape(_INLINE_LINK.sub(r"\1", tokens[i + 1].content)).replace("`", "")
            headings[start] = (end, text.strip())

    title = ""
    blocks: list[str] = []
    lines: list[str] = []

    def finish_block() -> None:
        block = "\n".join(lines).strip("\n")
        if block.strip():
            blocks.append(block)
        lines.clear()

    line_index = 0
    while line_index < len(source_lines):
        if line_index in code_ranges:
            finish_block()
            end, excluded = code_ranges[line_index]
            if not excluded:
                blocks.append("\n".join(source_lines[line_index:end]))
            line_index = end
            continue
        if line_index in headings:
            finish_block()
            yield title, blocks
            line_index, title = headings[line_index]
            blocks = []
            continue
        line = source_lines[line_index]
        if line.strip():
            lines.append(line)
        else:
            finish_block()
        line_index += 1

    finish_block()
    yield title, blocks


def _parts(blocks: list[str]) -> Iterable[str]:
    group: list[str] = []
    size = 0
    for block in blocks:
        if group and size + 2 + len(block) > _TARGET_CHARS:
            yield "\n\n".join(group)
            group, size = [], 0
        size += len(block) + (2 if group else 0)
        group.append(block)
    if group:
        yield "\n\n".join(group)


def _lesson_chunks(lesson: _Lesson) -> Iterable[LessonHit]:
    parts_by_anchor: Counter[str] = Counter()
    for heading, blocks in _sections(lesson.markdown):
        anchor = slugify(heading)
        title = heading or lesson.lesson_title
        for text in _parts(blocks):
            part_number = parts_by_anchor[anchor]
            parts_by_anchor[anchor] += 1
            yield LessonHit(
                f"{lesson.course_slug}/{lesson.lesson_slug}#{anchor}:{part_number}",
                lesson.course_slug, lesson.lesson_slug, anchor, title, text,
            )


def _identifier(term: str) -> str:
    # Use the same unicode61 tokenizer for natural text and exact code identifiers.
    return "x" + term.encode("utf-8").hex()


def _identifiers(text: str) -> str:
    return " ".join(
        _identifier(term) for term in dict.fromkeys(_TERM.findall(text.casefold()))
        if not _WORD.fullmatch(term)
    )


def _fts_expression(query: str) -> str:
    tokens: dict[str, None] = {}
    for term in _TERM.findall(query.casefold()):
        if _WORD.fullmatch(term):
            tokens[f'"{term}"'] = None
        else:
            tokens[f'identifiers:"{_identifier(term)}"'] = None
            words = _WORD.findall(term)
            if len(words) > 1:
                tokens.update((f'"{word}"', None) for word in words)
    return " OR ".join(list(tokens)[:64])


_SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    chunk_id TEXT UNIQUE NOT NULL,
    course_slug TEXT NOT NULL,
    lesson_slug TEXT NOT NULL,
    anchor TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX chunks_lesson ON chunks(course_slug, lesson_slug);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    title, body, identifiers, tokenize='unicode61 remove_diacritics 2'
);
"""


def _unit_vectors(vectors, count: int) -> NDArray:
    import numpy as np

    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != count or matrix.shape[1] < 1:
        raise RetrievalUnavailable("The embedding model returned an unexpected matrix")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or not (norms > 0).all():
        raise RetrievalUnavailable("The embedding model returned an invalid vector")
    return matrix / norms


def build_index(
    content_dir: Path, model_dir: Path, index_path: Path, *, embedder: Embedder | None = None,
) -> dict[str, int]:
    """Embed the corpus offline and atomically replace the SQLite artifact."""
    if embedder is None:
        embedder = E5Embedder(model_dir)
    corpus = _load_corpus(content_dir)
    passages: list[tuple[LessonHit, str]] = []
    for lesson in corpus.lessons:
        for hit in _lesson_chunks(lesson):
            title = "\n".join(dict.fromkeys((lesson.course_title, lesson.lesson_title, hit.title)))
            passages.append((hit, title))
    if not passages:
        raise RetrievalUnavailable("The published lesson corpus has no indexable sections")

    artifact_fingerprint = embedder.fingerprint
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(prefix=index_path.name + ".", dir=index_path.parent, delete=False) as file:
        pending = Path(file.name)

    try:
        with closing(sqlite3.connect(pending)) as connection, connection:
            connection.executescript(_SCHEMA)
            dimension = None
            for offset in range(0, len(passages), 16):
                batch = passages[offset:offset + 16]
                embeddings = _unit_vectors(
                    embedder.embed([title + "\n\n" + hit.text for hit, title in batch], passage=True),
                    len(batch),
                )
                if dimension is not None and embeddings.shape[1] != dimension:
                    raise RetrievalUnavailable("The embedding dimension changed during indexing")
                dimension = embeddings.shape[1]
                for row_id, ((hit, title), vector) in enumerate(zip(batch, embeddings), start=offset + 1):
                    connection.execute(
                        "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            row_id, hit.chunk_id, hit.course_slug, hit.lesson_slug, hit.anchor,
                            hit.title, hit.text, vector.astype("<f4", copy=False).tobytes(),
                        ),
                    )
                    connection.execute(
                        "INSERT INTO chunks_fts(rowid, title, body, identifiers) VALUES (?, ?, ?, ?)",
                        (row_id, title, hit.text, _identifiers(title + "\n" + hit.text)),
                    )
            connection.executemany(
                "INSERT INTO metadata VALUES (?, ?)",
                {
                    "version": INDEX_VERSION,
                    "source_fingerprint": corpus.fingerprint,
                    "model_fingerprint": artifact_fingerprint,
                    "dimension": str(dimension),
                    "generation": uuid4().hex,
                    "chunks": str(len(passages)),
                }.items(),
            )

        if embedder.fingerprint != artifact_fingerprint:
            raise RetrievalUnavailable("The embedding model changed during indexing")
        pending.chmod(0o444)
        pending.replace(index_path)
    finally:
        pending.unlink(missing_ok=True)
    return {"lessons": len(corpus.lessons), "chunks": len(passages)}


def reciprocal_rank_fusion(
    lexical: Iterable[LessonHit], dense: Iterable[LessonHit], *, constant: int = DEFAULT_RRF_CONSTANT,
) -> tuple[LessonHit, ...]:
    if constant < 0:
        raise ValueError("The RRF constant must be nonnegative")
    scores: dict[str, float] = {}
    hits: dict[str, LessonHit] = {}
    for ranking in (lexical, dense):
        distinct = {hit.chunk_id: hit for hit in ranking}
        for rank, (chunk_id, hit) in enumerate(distinct.items(), start=1):
            hits.setdefault(chunk_id, hit)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (constant + rank)
    return tuple(hits[chunk_id] for chunk_id in sorted(scores, key=lambda key: (-scores[key], key)))


def distinct_sections(ranking: Iterable[LessonHit], limit: int) -> tuple[LessonHit, ...]:
    """Select the highest ranked chunk for each cited lesson section."""
    hits = []
    seen: set[tuple[str, str, str]] = set()
    for hit in ranking:
        if len(hits) == limit:
            break
        if hit.section_key not in seen:
            hits.append(hit)
            seen.add(hit.section_key)
    return tuple(hits)


def _fits_section(text: str) -> bool:
    return (
        len(text) <= _SECTION_MAX_CHARS
        and len(json.dumps(text, ensure_ascii=False).encode("utf-8")) <= _SECTION_MAX_JSON_BYTES
    )


def _expand_section(hit: LessonHit, chunks: tuple[LessonHit, ...]) -> LessonHit:
    text = hit.text
    if not _fits_section(text):
        # An individually oversized block is the only case where we cut within a chunk.
        low, high = 0, _SECTION_MAX_CHARS - 2
        while low < high:
            middle = (low + high + 1) // 2
            if _fits_section(text[:middle] + "\n…"):
                low = middle
            else:
                high = middle - 1
        return replace(hit, text=text[:low].rstrip() + "\n…")

    center = chunks.index(hit)
    left, right = center - 1, center + 1
    while left >= 0 or right < len(chunks):
        if left >= 0:
            next_text = chunks[left].text + "\n\n" + text
            if _fits_section(next_text):
                text = next_text
                left -= 1
            else:
                left = -1
        if right < len(chunks):
            next_text = text + "\n\n" + chunks[right].text
            if _fits_section(next_text):
                text = next_text
                right += 1
            else:
                right = len(chunks)
    return replace(hit, text=text)


@dataclass(frozen=True)
class _IndexState:
    generation: str
    hits: tuple[LessonHit, ...]
    hits_by_id: dict[str, LessonHit]
    hits_by_section: dict[tuple[str, str, str], tuple[LessonHit, ...]]
    row_ids: dict[int, LessonHit]
    embeddings: NDArray


class LessonRetriever:
    def __init__(
        self, index_path: Path, model_dir: Path, *, content_dir: Path | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._index_path = index_path
        self._content_dir = content_dir if content_dir is not None else DEFAULT_CONTENT_DIR
        self._embedder = embedder if embedder is not None else E5Embedder(model_dir)
        self._lock = Lock()
        self._source_paths: tuple[Path, ...] = ()
        self._source_signatures: tuple[tuple[int, int, int, int, int], ...] = ()
        self._source_fingerprint = ""
        self._state: _IndexState | None = None

    def _current_source_fingerprint(self) -> str:
        if self._source_paths:
            try:
                if _file_signatures(self._source_paths) == self._source_signatures:
                    return self._source_fingerprint
            except FileNotFoundError:
                pass  # Re-read the manifest to account for removed lessons or courses.

        corpus = _load_corpus(self._content_dir)
        self._source_paths = corpus.paths
        self._source_signatures = _file_signatures(corpus.paths)
        self._source_fingerprint = corpus.fingerprint
        return self._source_fingerprint

    @contextmanager
    def _open_index(self):
        try:
            uri = self._index_path.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                connection.execute("BEGIN")
                yield connection
        except (ImportError, OSError, sqlite3.Error, EmbeddingError, KeyError, ValueError) as exc:
            raise RetrievalUnavailable("The local assistant retrieval index or model is unavailable") from exc

    def _read_state(self, connection: sqlite3.Connection) -> _IndexState:
        import numpy as np

        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        if metadata.get("version") != INDEX_VERSION:
            raise RetrievalUnavailable("The assistant index needs to be rebuilt for this version")
        if metadata["source_fingerprint"] != self._current_source_fingerprint():
            raise RetrievalUnavailable("The assistant index needs to be rebuilt for the current lessons")
        if metadata["model_fingerprint"] != self._embedder.fingerprint:
            raise RetrievalUnavailable("The assistant index needs to be rebuilt for the configured embedding model")
        if self._state is not None and self._state.generation == metadata["generation"]:
            return self._state

        rows = connection.execute(
            "SELECT id, chunk_id, course_slug, lesson_slug, anchor, title, text, embedding "
            "FROM chunks ORDER BY chunk_id"
        ).fetchall()
        fts_count = connection.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
        if not rows or len(rows) != int(metadata["chunks"]) or len(rows) != fts_count:
            raise RetrievalUnavailable("The assistant index has inconsistent chunk counts")
        hits = tuple(LessonHit(*row[1:-1]) for row in rows)
        embeddings = np.stack([np.frombuffer(row[-1], dtype="<f4") for row in rows])
        if embeddings.shape[1] != int(metadata["dimension"]):
            raise RetrievalUnavailable("The assistant index has an invalid embedding dimension")
        embeddings = _unit_vectors(embeddings, len(rows))
        sections: dict[tuple[str, str, str], list[LessonHit]] = {}
        for hit in hits:
            sections.setdefault(hit.section_key, []).append(hit)
        self._state = _IndexState(
            metadata["generation"], hits,
            {hit.chunk_id: hit for hit in hits},
            {
                section: tuple(sorted(parts, key=lambda part: int(part.chunk_id.rsplit(":", 1)[1])))
                for section, parts in sections.items()
            },
            {row[0]: hit for row, hit in zip(rows, hits)},
            embeddings,
        )
        return self._state

    def validate(self) -> None:
        """Check local artifact compatibility without running model inference."""
        with self._lock, self._open_index() as connection:
            self._read_state(connection)

    def read_section(self, chunk_id: str) -> LessonHit | None:
        with self._lock, self._open_index() as connection:
            state = self._read_state(connection)
            hit = state.hits_by_id.get(chunk_id)
            return _expand_section(hit, state.hits_by_section[hit.section_key]) if hit else None

    def search(
        self, query: str, *, limit: int = DEFAULT_LIMIT,
        course_slug: str | None = None, lesson_slug: str | None = None,
    ) -> list[LessonHit]:
        return list(self.rank(query, limit=limit, course_slug=course_slug, lesson_slug=lesson_slug).hybrid)

    def rank(
        self, query: str, *, limit: int = DEFAULT_LIMIT,
        course_slug: str | None = None, lesson_slug: str | None = None,
        lexical_limit: int = DEFAULT_LEXICAL_CANDIDATES, dense_limit: int = DEFAULT_DENSE_CANDIDATES,
        rrf_constant: int = DEFAULT_RRF_CONSTANT,
    ) -> RetrievalRun:
        """Return the lexical, dense, and fused ranks for one query and optional lesson scope."""
        if min(limit, lexical_limit, dense_limit, rrf_constant) < 0:
            raise ValueError("Ranking limits and the RRF constant must be nonnegative")
        query = query.strip()
        expression = _fts_expression(query)
        if not expression or not limit:
            return RetrievalRun()

        with self._lock, self._open_index() as connection:
            state = self._read_state(connection)
            scopes = tuple((column, value) for column, value in (
                ("course_slug", course_slug), ("lesson_slug", lesson_slug),
            ) if value is not None)
            positions = range(len(state.hits))
            if scopes:
                positions = [
                    i for i, hit in enumerate(state.hits)
                    if all(getattr(hit, column) == value for column, value in scopes)
                ]
            if not positions:
                return RetrievalRun()
            lexical = self._lexical(connection, state, expression, scopes, lexical_limit)
            dense = self._dense(state, query, positions, dense_limit)
            fused = reciprocal_rank_fusion(lexical, dense, constant=rrf_constant)
            hybrid = distinct_sections(fused, limit)
            return RetrievalRun(lexical, dense, hybrid)

    @staticmethod
    def _lexical(connection, state, expression, scopes, limit) -> tuple[LessonHit, ...]:
        where_scope = "".join(f" AND chunks.{column} = ?" for column, _ in scopes)
        rows = connection.execute(
            "SELECT chunks.id FROM chunks_fts JOIN chunks ON chunks.id = chunks_fts.rowid "
            f"WHERE chunks_fts MATCH ?{where_scope} "
            "ORDER BY bm25(chunks_fts, 4.0, 1.0, 8.0), chunks.chunk_id LIMIT ?",
            (expression, *(value for _, value in scopes), limit),
        )
        return tuple(state.row_ids[row_id] for (row_id,) in rows)

    def _dense(self, state, query, positions, limit) -> tuple[LessonHit, ...]:
        import numpy as np

        if not limit:
            return ()
        vector = _unit_vectors(self._embedder.embed([query], passage=False), 1)[0]
        if vector.shape[0] != state.embeddings.shape[1]:
            raise RetrievalUnavailable("The query and lesson embedding dimensions differ")
        matrix = state.embeddings if isinstance(positions, range) else state.embeddings[positions]
        # Avoid spawning BLAS threads for a small matrix on a one-core host.
        scores = np.einsum("ij,j->i", matrix, vector, optimize=False)
        ranked = np.argsort(-scores, kind="stable")[:limit]
        return tuple(state.hits[positions[i]] for i in ranked if scores[i] > 0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build a new lesson index on this machine")
    build.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    build.add_argument("--model-dir", type=Path, required=True)
    build.add_argument("--index", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_index(args.content_dir, args.model_dir, args.index)
    except (RetrievalUnavailable, EmbeddingError, ImportError, OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Index build failed: {exc}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
