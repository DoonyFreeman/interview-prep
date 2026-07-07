"""In-memory cache of static content (lesson markdown, roadmap).

This content is static per deploy, so we keep it in process memory rather than
reading files (or a DB blob) per request. Populated at startup by the seed step.
Lesson bodies are keyed by ``(course_slug, lesson_slug)``; the roadmap is the
raw parsed ``content/roadmap.json``.
"""
from __future__ import annotations

_LESSON_TEXT: dict[tuple[str, str], str] = {}
_ROADMAP: dict | None = None


def set_lesson_text(course_slug: str, lesson_slug: str, markdown: str) -> None:
    _LESSON_TEXT[(course_slug, lesson_slug)] = markdown


def get_lesson_text(course_slug: str, lesson_slug: str) -> str | None:
    return _LESSON_TEXT.get((course_slug, lesson_slug))


def set_roadmap(data: dict | None) -> None:
    global _ROADMAP
    _ROADMAP = data


def get_roadmap() -> dict | None:
    return _ROADMAP


def clear() -> None:
    global _ROADMAP
    _LESSON_TEXT.clear()
    _ROADMAP = None
