"""Global lesson search: titles + full lesson markdown, whole-phrase matching.

The scan runs Python-side over the in-memory registry (not SQL LIKE) because
SQLite's LIKE is case-sensitive for Cyrillic while ``str.casefold()`` is not.
Structure (courses → lessons → concepts) comes from the repository; markdown
bodies come from the registry — same split as ``content.get_cat_thoughts``.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.content import registry
from app.content.excerpt import extract_h2_sections
from app.repositories import CourseRepository
from app.schemas import SearchOut, SearchResultOut

RESULT_CAP = 20
_SNIPPET_WIDTH = 160

# Lower is better; stable sort keeps document order within a rank.
_RANK = {"lesson_title": 0, "section_title": 1, "body": 2, "course_title": 3}


def _snippet(text: str, needle: str, width: int = _SNIPPET_WIDTH) -> str:
    """~``width`` chars around the first match, expanded to word boundaries.

    With no match (title hits) it degrades to the head of the text.
    """
    text = text.strip()
    if len(text) <= width:
        return text
    pos = text.casefold().find(needle)
    if pos < 0:
        pos = 0
    start = max(0, pos - (width - len(needle)) // 2)
    end = min(len(text), start + width)
    if start > 0:  # advance to the next word boundary
        cut = text.find(" ", start)
        if 0 <= cut < pos:
            start = cut + 1
    if end < len(text):  # retreat to the previous word boundary
        cut = text.rfind(" ", max(pos + len(needle), start), end)
        if cut > 0:
            end = cut
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


async def search_lessons(session: AsyncSession, q: str) -> SearchOut:
    query = q.strip()
    needle = query.casefold()
    if len(needle) < 2:
        return SearchOut(query=query, count=0, results=[])

    # ponytail: linear scan of ~2.5MB of markdown per request — milliseconds at
    # this content size; cache parsed sections beside the registry if it grows.
    courses = await CourseRepository(session).list_published_with_lessons_concepts()
    scored: list[tuple[int, SearchResultOut]] = []
    for course in courses:
        course_hit = needle in course.title.casefold()
        for lesson in sorted(course.lessons, key=lambda x: x.order_index):
            markdown = registry.get_lesson_text(course.slug, lesson.slug) or ""
            sections = extract_h2_sections(markdown)
            concept_titles = {c.anchor: c.title for c in lesson.concepts}
            first_text = next((text for _, _, text in sections if text), "")
            emitted: set[str] = set()  # anchors already emitted for this lesson

            def emit(field: str, anchor: str, title: str | None, text: str) -> None:
                if anchor in emitted:
                    return
                emitted.add(anchor)
                scored.append(
                    (
                        _RANK[field],
                        SearchResultOut(
                            course_slug=course.slug,
                            course_title=course.title,
                            lesson_slug=lesson.slug,
                            lesson_title=lesson.title,
                            section_title=title,
                            anchor=anchor,
                            snippet=_snippet(text, needle),
                            match_field=field,
                        ),
                    )
                )

            if needle in lesson.title.casefold():
                emit("lesson_title", "", None, first_text)
            for anchor, title, text in sections:
                if not anchor:  # intro before the first H2
                    if needle in text.casefold():
                        emit("body", "", None, text)
                    continue
                concept_title = concept_titles.get(anchor, "")
                if needle in title.casefold() or needle in concept_title.casefold():
                    emit("section_title", anchor, title, text)
                elif needle in text.casefold():
                    emit("body", anchor, title, text)
            if course_hit:
                emit("course_title", "", None, first_text)

    scored.sort(key=lambda pair: pair[0])
    results = [result for _, result in scored[:RESULT_CAP]]
    return SearchOut(query=query, count=len(results), results=results)
