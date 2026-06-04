"""In-memory cache of lesson markdown text.

Lesson bodies are static, so we keep them in process memory rather than reading
files (or a DB blob) per request. Populated at startup by the seed step and read
by the lessons endpoint and, later, by the LLM grounding step. Keyed by
``(course_slug, lesson_slug)``.
"""
from __future__ import annotations

_LESSON_TEXT: dict[tuple[str, str], str] = {}


def set_lesson_text(course_slug: str, lesson_slug: str, markdown: str) -> None:
    _LESSON_TEXT[(course_slug, lesson_slug)] = markdown


def get_lesson_text(course_slug: str, lesson_slug: str) -> str | None:
    return _LESSON_TEXT.get((course_slug, lesson_slug))


def clear() -> None:
    _LESSON_TEXT.clear()
