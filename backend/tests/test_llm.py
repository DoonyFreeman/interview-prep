"""Unit tests for the Gemini client's pure helpers + the evaluation normalizer.

These need no network: they cover JSON-fence tolerance, candidate extraction,
the no-key guard, and the model-chain fallback (via a stubbed httpx call).
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.llm import client as llm
from app.services.quiz import _normalize_evaluation


def test_parse_json_object_plain():
    assert llm._parse_json_object('{"score": 90}') == {"score": 90}


def test_parse_json_object_strips_code_fence():
    raw = '```json\n{"score": 10, "verdict": "неверно"}\n```'
    assert llm._parse_json_object(raw)["verdict"] == "неверно"


def test_parse_json_object_rejects_non_object():
    with pytest.raises(llm.LLMError):
        llm._parse_json_object("[1, 2, 3]")


def test_parse_json_object_rejects_garbage():
    with pytest.raises(llm.LLMError):
        llm._parse_json_object("not json at all")


def test_extract_text_concatenates_parts():
    data = {"candidates": [{"content": {"parts": [{"text": "a"}, {"text": "b"}]}}]}
    assert llm._extract_text(data) == "ab"


def test_extract_text_no_candidates_raises():
    with pytest.raises(llm.LLMError):
        llm._extract_text({"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})


async def test_generate_requires_api_key():
    c = llm.GeminiClient(Settings(gemini_api_key=""))
    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY"):
        await c.generate_text("hi")


async def test_model_chain_falls_back_on_429(monkeypatch):
    """First model returns 429, second succeeds — client should walk the chain."""
    settings = Settings(
        gemini_api_key="test-key",
        gemini_model="model-a",
        gemini_fallback_models="model-b",
    )
    c = llm.GeminiClient(settings)
    seen: list[str] = []

    async def fake_post(self, url, *, params, json):  # noqa: A002 - mirrors httpx
        model = url.split("/models/")[1].split(":")[0]
        seen.append(model)
        if model == "model-a":
            return httpx.Response(429, text="quota exceeded")
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await c.generate_text("hi") == "ok"
    assert seen == ["model-a", "model-b"]


async def test_client_error_not_retried(monkeypatch):
    """A 400 is a real error — surface it, don't walk the whole chain."""
    settings = Settings(
        gemini_api_key="test-key",
        gemini_model="model-a",
        gemini_fallback_models="model-b",
    )
    c = llm.GeminiClient(settings)
    calls: list[str] = []

    async def fake_post(self, url, *, params, json):
        calls.append(url)
        return httpx.Response(400, text="bad request")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(llm.LLMError, match="400"):
        await c.generate_text("hi")
    assert len(calls) == 1  # stopped at the first model


def test_normalize_clamps_score_and_derives_verdict():
    out = _normalize_evaluation({"score": 250, "verdict": "weird"})
    assert out["score"] == 100
    assert out["verdict"] == "верно"


def test_normalize_low_score_verdict():
    out = _normalize_evaluation({"score": 10})
    assert out["verdict"] == "неверно"


def test_normalize_coerces_scalar_lists():
    out = _normalize_evaluation(
        {"score": 50, "strengths": "только одно", "gaps": None}
    )
    assert out["strengths"] == ["только одно"]
    assert out["gaps"] == []
