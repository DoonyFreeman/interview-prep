"""Gemini client over the REST ``generateContent`` API.

Runtime-only and narrow: the app calls Gemini to grade an answer and to produce
a hint, nothing else. The client walks :pyattr:`Settings.model_chain` (primary
model + fallbacks) on per-day quota / transient errors, mirroring the fallback
pattern used in the author's telegram-bot ``gemini.py``.

The :class:`LLMClient` protocol is the seam the quiz service depends on, so tests
can inject a fake without touching the network (see ``tests/test_quiz.py``).
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import Settings, get_settings

# HTTP statuses that mean "this model is unavailable right now, try the next one"
# rather than "the request itself is bad" (which we surface immediately).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMError(Exception):
    """Raised when no model in the chain could produce a response."""


@runtime_checkable
class LLMClient(Protocol):
    """The narrow surface the quiz service needs. Mockable in tests."""

    async def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        ...

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        ...


class GeminiClient:
    """Async Gemini client that walks the configured model chain on failure."""

    def __init__(self, settings: Settings, *, timeout: float = 30.0) -> None:
        self._api_key = settings.gemini_api_key
        self._base_url = settings.gemini_base_url.rstrip("/")
        self._models = settings.model_chain
        self._timeout = timeout

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's plain-text response, walking the model chain."""
        return await self._generate(prompt, system=system, as_json=False)

    async def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        """Return the model's response parsed as a JSON object."""
        raw = await self._generate(prompt, system=system, as_json=True)
        return _parse_json_object(raw)

    # ------------------------------------------------------------------ #
    async def _generate(self, prompt: str, *, system: str | None, as_json: bool) -> str:
        if not self._api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        if not self._models:
            raise LLMError("No Gemini model configured")

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                # Grading/hints are short; give a real budget so the JSON isn't
                # truncated (a bare response defaults low and gets cut → MAX_TOKENS).
                "maxOutputTokens": 2048,
                # 2.5-family models spend output tokens on internal "thinking" by
                # default, which can starve the visible answer. We don't need a
                # chain of thought — the reference answer is already supplied — so
                # disable it for compact, fast, cheap responses. (All models in
                # the configured chain are 2.5-family and accept this.)
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if as_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as http:
            for model in self._models:
                try:
                    return await self._call_model(http, model, payload)
                except _RetryNextModel as exc:
                    last_error = exc
                    continue
        raise LLMError(
            f"All models failed ({', '.join(self._models)}): {last_error}"
        ) from last_error

    async def _call_model(
        self, http: httpx.AsyncClient, model: str, payload: dict[str, Any]
    ) -> str:
        url = f"{self._base_url}/v1beta/models/{model}:generateContent"
        try:
            resp = await http.post(
                url, params={"key": self._api_key}, json=payload
            )
        except httpx.HTTPError as exc:  # network/timeout — try the next model
            raise _RetryNextModel(f"{model}: {exc}") from exc

        if resp.status_code in _RETRYABLE_STATUS:
            raise _RetryNextModel(f"{model}: HTTP {resp.status_code}")
        if resp.status_code >= 400:
            # A genuine client error (bad key, malformed request) — don't mask it
            # by walking the chain; every model would fail the same way.
            raise LLMError(f"Gemini error {resp.status_code}: {resp.text[:300]}")

        return _extract_text(resp.json())


class _RetryNextModel(Exception):
    """Internal signal: this model failed transiently, try the next in the chain."""


def _extract_text(data: dict[str, Any]) -> str:
    """Pull the first candidate's concatenated text out of a generateContent body."""
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback", {})
        raise LLMError(f"No candidates returned (feedback: {feedback})")
    parts = candidates[0].get("content", {}).get("parts", []) or []
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise LLMError("Empty response text from model")
    return text


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating ```json fences the model may add."""
    text = raw.strip()
    if text.startswith("```"):
        # strip a leading ```json / ``` fence and the trailing ```
        text = text.split("\n", 1)[-1] if "\n" in text else text
        text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {raw[:300]}") from exc
    if not isinstance(data, dict):
        raise LLMError(f"Expected a JSON object, got {type(data).__name__}")
    return data


@lru_cache
def get_llm_client() -> GeminiClient:
    """Cached real client. Construction is cheap; the HTTP client is per-call."""
    return GeminiClient(get_settings())


def get_llm() -> LLMClient:
    """FastAPI dependency. Overridden in tests with a fake client."""
    return get_llm_client()
