"""Extract a short, plain-text excerpt for each H2 section of a lesson body.

Used by the corner-cat "thought" feature: every concept of a completed lesson
points at an H2 section (its ``anchor``), and the cat shows the first meaningful
paragraph of that section as a bite-sized definition. Lesson markdown is the
source of truth, so this reads it directly (via the in-memory registry) rather
than duplicating prose into the DB.
"""
from __future__ import annotations

import re

_INLINE_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BOLD = re.compile(r"\*\*([^*]*)\*\*")
_ITALIC = re.compile(r"\*([^*]*)\*")
_CODE = re.compile(r"`([^`]*)`")
_WS = re.compile(r"\s+")


def slugify(text: str) -> str:
    """Mirror of ``frontend/src/lib/slugify.ts`` and the content's anchors.

    lowercase -> drop punctuation (keep letters/digits/whitespace/dash, incl.
    Cyrillic; underscore is dropped) -> collapse whitespace to single dashes.
    """
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).replace("_", "")
    s = s.strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s


def _strip_markdown(text: str) -> str:
    """Strip the lightest inline markdown so a paragraph reads as plain text."""
    text = _INLINE_LINK.sub(r"\1", text)
    text = _BOLD.sub(r"\1", text)
    text = _ITALIC.sub(r"\1", text)
    text = _CODE.sub(r"\1", text)
    return _WS.sub(" ", text).strip()


_SENTENCE_END = re.compile(r"[.!?…](?=\s|$)")


def _truncate(text: str, max_chars: int) -> str:
    """Trim to whole sentences so the bubble never cuts off mid-thought.

    Keeps appending sentences while they fit; always keeps at least the first
    sentence (even if it's longer than ``max_chars`` — a complete sentence beats
    a clipped one). Falls back to a word-boundary cut + "…" only when the text
    has no sentence punctuation at all. A dangling ":" (it used to introduce a
    code block / list we dropped) is trimmed.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text.rstrip(" :")

    ends = [m.end() for m in _SENTENCE_END.finditer(text)]
    result = ""
    for e in ends:
        candidate = text[:e].strip()
        if len(candidate) <= max_chars:
            result = candidate
        else:
            break
    if result:
        return result.rstrip(" :")
    if ends:
        # First sentence alone exceeds the budget — keep it whole anyway.
        return text[: ends[0]].strip().rstrip(" :")
    # No sentence punctuation at all — last-resort word-boundary cut.
    return text[:max_chars].rsplit(" ", 1)[0].rstrip() + "…"


def _is_prose(line: str) -> bool:
    """True for a line that's a normal paragraph (not heading/list/table/quote)."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("#", ">", "|", "- ", "* ", "+ ")):
        return False
    # Ordered list item like "1. ".
    if re.match(r"^\d+\.\s", stripped):
        return False
    return True


def extract_h2_sections(markdown: str) -> list[tuple[str, str, str]]:
    """Return ordered ``(anchor, title, plain_text)`` for every H2 section.

    Used by the global search: ``plain_text`` is the whole section flattened to
    one plain-text line (inline markdown stripped). Code-fence *content* is kept
    — identifiers like ``asyncio.gather`` often appear only in code — while the
    fence markers themselves are dropped. Prose before the first H2 (and the H1
    line) comes back as a leading ``("", "", text)`` entry.
    """
    sections: list[tuple[str, str, str]] = []
    anchor, title = "", ""
    buf: list[str] = []

    def _flush() -> None:
        text = _strip_markdown(" ".join(buf))
        if anchor or text:
            sections.append((anchor, title, text))

    for line in markdown.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            _flush()
            title = line[3:].strip()
            anchor = slugify(title)
            buf = []
            continue
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        if stripped.startswith("#"):
            buf.append(stripped.lstrip("#").strip())
            continue
        if stripped:
            # Drop blockquote/list markers so snippets read as plain prose.
            buf.append(re.sub(r"^(?:>\s*|[-*+]\s+|\d+\.\s+)+", "", stripped))
    _flush()
    return sections


def extract_h2_excerpts(markdown: str, max_chars: int = 240, min_chars: int = 20) -> dict[str, str]:
    """Return ``{anchor: plain_text_excerpt}`` for every ``## `` H2 section.

    The excerpt is the first prose **paragraph** under the heading (skipping code
    fences, tables, lists and sub-headings). Markdown soft-wraps a paragraph
    across several lines, so consecutive prose lines are joined before
    truncating — otherwise the excerpt would end mid-sentence at the first wrap.
    Truncation keeps whole sentences. Sections with no usable prose map to ``""``
    so the caller can still surface the concept title alone.
    """
    excerpts: dict[str, str] = {}
    lines = markdown.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("## ") and not line.startswith("### "):
            anchor = slugify(line[3:].strip())
            i += 1
            in_code = False
            para_lines: list[str] = []
            while i < n:
                cur = lines[i]
                # Stop at the next H2/H1 boundary.
                if cur.startswith("## ") and not cur.startswith("### "):
                    break
                if cur.startswith("# ") and not cur.startswith("## "):
                    break
                if cur.lstrip().startswith("```"):
                    if para_lines:  # code right after prose ends the paragraph
                        break
                    in_code = not in_code
                    i += 1
                    continue
                if in_code:
                    i += 1
                    continue
                if not cur.strip():
                    if para_lines:  # a blank line ends the paragraph
                        break
                    i += 1
                    continue
                if _is_prose(cur):
                    para_lines.append(cur.strip())
                    i += 1
                    continue
                # A non-prose block (heading/list/table/quote).
                if para_lines:
                    break
                i += 1
            excerpt = ""
            if para_lines:
                para = _strip_markdown(" ".join(para_lines))
                if len(para) >= min_chars:
                    excerpt = _truncate(para, max_chars)
            if anchor and anchor not in excerpts:
                excerpts[anchor] = excerpt
            continue
        i += 1
    return excerpts
