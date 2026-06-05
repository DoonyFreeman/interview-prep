"""Gemini client over the REST ``generateContent`` API.

Runtime-only and narrow: the app calls Gemini to grade an answer and to produce
a hint, nothing else. Resilience mirrors the author's telegram-bot ``gemini.py``:

* **per-model retries with backoff** for transient failures, then
* **model fallback** down :pyattr:`Settings.model_chain` (primary + fallbacks).

Failure handling per HTTP status:
  - 200            → return the text.
  - 429 daily quota (``quotaId`` contains ``PerDay``) → switch model immediately
    (waiting is pointless — the day's budget is gone).
  - 429 rpm limit  → retry the **same** model after the server's ``RetryInfo``
    delay, up to a cap.
  - 5xx / network  → retry the same model with exponential backoff, then switch.
  - other 4xx      → give up on this model, try the next.

The :class:`LLMClient` protocol is the seam tests override (``get_llm``), so the
quiz service runs without network/key.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_RETRY_STATUS = {500, 502, 503, 504}  # transient server errors — retry same model
_MAX_ATTEMPTS = 4  # attempts per model before falling back
_MAX_DELAY = 15.0  # cap on wait between attempts, seconds
# If a minute-rate cooldown is longer than this, switching models beats waiting
# (these calls are interactive — a hint/grade shouldn't stall on one model).
_RPM_SWITCH_THRESHOLD = 8.0


class LLMError(Exception):
    """Raised when no model in the chain could produce a response."""


class _ModelUnavailable(Exception):
    """Internal: this model is exhausted (limit/error) — switch to the next."""


@runtime_checkable
class LLMClient(Protocol):
    """The narrow surface the quiz service needs. Mockable in tests."""

    async def generate_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        ...

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        ...


class GeminiClient:
    """Async Gemini client: retries per model, then walks the model chain."""

    def __init__(self, settings: Settings, *, timeout: float = 60.0) -> None:
        self._api_key = settings.gemini_api_key
        self._base_url = settings.gemini_base_url.rstrip("/")
        self._models = settings.model_chain
        self._timeout = timeout

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        """Return the model's plain-text response."""
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

        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                # Real budget so graded JSON isn't truncated (a bare response
                # defaults low and gets cut → MAX_TOKENS).
                "maxOutputTokens": 2048,
                # 2.5-family models spend output tokens on internal "thinking";
                # we don't need a chain of thought (reference answer is supplied),
                # so disable it for compact, fast, cheap responses.
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if as_json:
            body["generationConfig"]["responseMimeType"] = "application/json"

        last_err = "?"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for idx, model in enumerate(self._models):
                try:
                    return await self._generate_one(client, model, body)
                except _ModelUnavailable as exc:
                    last_err = str(exc)
                    nxt = self._models[idx + 1] if idx + 1 < len(self._models) else None
                    if nxt:
                        logger.warning("Model %s unavailable (%s) → %s", model, exc, nxt)
                    else:
                        logger.error("All models exhausted. Last: %s (%s)", model, exc)
        raise LLMError(
            f"All models failed ({', '.join(self._models)}): {last_err}"
        )

    async def _generate_one(
        self, client: httpx.AsyncClient, model: str, body: dict[str, Any]
    ) -> str:
        url = f"{self._base_url}/v1beta/models/{model}:generateContent"
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = await client.post(url, params={"key": self._api_key}, json=body)
            except httpx.TransportError as exc:  # network blip
                if attempt == _MAX_ATTEMPTS:
                    raise _ModelUnavailable(f"{model}: network: {exc}") from exc
                await self._sleep(2 ** (attempt - 1), model, attempt, str(exc))
                continue

            if resp.status_code == 200:
                return _extract_text(resp.json())

            data = _safe_json(resp)

            if resp.status_code == 429:
                if _is_daily_quota(data):
                    # Daily free-tier budget gone — waiting won't help, switch model.
                    raise _ModelUnavailable(f"{model}: daily quota exhausted")
                delay = _retry_delay_seconds(data)
                # A long cooldown → switch model now instead of stalling the request.
                if delay > _RPM_SWITCH_THRESHOLD or attempt == _MAX_ATTEMPTS:
                    raise _ModelUnavailable(f"{model}: rpm limit ({delay:.0f}s)")
                await self._sleep(delay, model, attempt, "429 rpm")
                continue

            if resp.status_code in _RETRY_STATUS:
                if attempt == _MAX_ATTEMPTS:
                    raise _ModelUnavailable(f"{model}: HTTP {resp.status_code}")
                await self._sleep(2 ** (attempt - 1), model, attempt, str(resp.status_code))
                continue

            # Other 4xx — pointless to retry this model; try the next one.
            msg = data.get("error", {}).get("message", "")[:120]
            raise _ModelUnavailable(f"{model}: HTTP {resp.status_code} {msg}")

        raise _ModelUnavailable(f"{model}: attempts exhausted")

    async def _sleep(self, delay: float, model: str, attempt: int, info: str) -> None:
        delay = min(max(delay, 1.0), _MAX_DELAY)
        logger.warning(
            "Gemini[%s] %s — retry in %.0fs (attempt %d/%d)",
            model, info, delay, attempt, _MAX_ATTEMPTS,
        )
        await asyncio.sleep(delay)


# --------------------------------------------------------------------------- #
# Pure helpers (testable without network)
# --------------------------------------------------------------------------- #
def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        return resp.json()
    except ValueError:
        return {}


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


def _quota_id(data: dict[str, Any]) -> str:
    for det in data.get("error", {}).get("details", []):
        for v in det.get("violations", []):
            if v.get("quotaId"):
                return v["quotaId"]
    return ""


def _is_daily_quota(data: dict[str, Any]) -> bool:
    return "PerDay" in _quota_id(data)


def _retry_delay_seconds(data: dict[str, Any]) -> float:
    """Seconds from the server's RetryInfo (e.g. '38s'); default if absent."""
    for det in data.get("error", {}).get("details", []):
        if "RetryInfo" in det.get("@type", ""):
            m = re.search(r"([\d.]+)s", det.get("retryDelay", ""))
            if m:
                return float(m.group(1)) + 1.0
    return 15.0


def _parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating ```json fences the model may add."""
    text = raw.strip()
    if text.startswith("```"):
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
