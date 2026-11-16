"""Decode answer text from a provider stream once it identifies retrieved sources."""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_core import from_json

AssistantEvent = Callable[[str, dict[str, Any]], Awaitable[None]]

MAX_ANSWER_LENGTH = 7000
MAX_ANSWER_SOURCES = 8
_MAX_PREVIEW_JSON_LENGTH = 100_000
_SOURCE_FIELD = re.compile(r'\s*(?:```(?:json)?\n\s*)?\{[ \t\r\n]*"source_ids"[ \t\r\n]*:[ \t\r\n]*(?=\[)')
_TEXT_FIELD = re.compile(r'[ \t\r\n]*,[ \t\r\n]*"text"[ \t\r\n]*:[ \t\r\n]*"')
_DECODER = json.JSONDecoder()


class AnswerPreview:
    def __init__(self, allowed_sources: tuple[str, ...]) -> None:
        self._allowed_sources = frozenset(allowed_sources)
        self._raw = ""
        self._disabled = False
        self._source_end = 0
        self._text_start: int | None = None
        self.source_ids: tuple[str, ...] = ()
        self.text = ""

    def append(self, chunk: str) -> str:
        if self._disabled:
            return ""
        if len(self._raw) + len(chunk) > _MAX_PREVIEW_JSON_LENGTH:
            self._disabled = True
            return ""
        self._raw += chunk
        if self._text_start is None:
            if not self.source_ids and not self._read_sources():
                return ""
            field = _TEXT_FIELD.match(self._raw, self._source_end)
            if field is None:
                return ""
            self._text_start = field.end() - 1

        try:
            # A split escape, including a split surrogate pair, waits for the next chunk.
            text: str = from_json(self._raw[self._text_start:], allow_partial="trailing-strings")
        except ValueError:
            return ""
        text = text.strip()
        if len(text) > MAX_ANSWER_LENGTH or not text.startswith(self.text):
            self._disabled = True
            return ""
        delta = text[len(self.text):]
        self.text = text
        return delta

    def _read_sources(self) -> bool:
        field = _SOURCE_FIELD.match(self._raw)
        if field is None:
            return False
        try:
            source_ids, end = _DECODER.raw_decode(self._raw, field.end())
        except (ValueError, RecursionError):
            return False
        if not 1 <= len(source_ids) <= MAX_ANSWER_SOURCES or any(
            not isinstance(source, str) or source not in self._allowed_sources for source in source_ids
        ):
            self._disabled = True
            return False
        self.source_ids = tuple(dict.fromkeys(source_ids))
        self._source_end = end
        return True
