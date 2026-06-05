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


def _ok(text: str = "ok") -> httpx.Response:
    return httpx.Response(
        200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]}
    )


def _daily_quota_429() -> httpx.Response:
    return httpx.Response(
        429,
        json={
            "error": {
                "code": 429,
                "details": [
                    {
                        "violations": [
                            {"quotaId": "GenerateRequestsPerDayPerProjectPerModel"}
                        ]
                    }
                ],
            }
        },
    )


def _rpm_429(retry_seconds: str = "0s") -> httpx.Response:
    return httpx.Response(
        429,
        json={
            "error": {
                "code": 429,
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": retry_seconds,
                    }
                ],
            }
        },
    )


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Make retry backoff instant in tests."""
    async def _instant(_seconds):  # noqa: ANN001
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", _instant)


def _model_of(url: str) -> str:
    return url.split("/models/")[1].split(":")[0]


async def test_daily_quota_switches_model_immediately(monkeypatch):
    """A per-day 429 should jump straight to the next model (no retries)."""
    settings = Settings(
        gemini_api_key="k", gemini_model="model-a", gemini_fallback_models="model-b"
    )
    c = llm.GeminiClient(settings)
    seen: list[str] = []

    async def fake_post(self, url, *, params, json):
        seen.append(_model_of(url))
        return _daily_quota_429() if _model_of(url) == "model-a" else _ok()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await c.generate_text("hi") == "ok"
    assert seen == ["model-a", "model-b"]  # one shot each, switched on daily quota


async def test_rpm_limit_retries_same_model_then_succeeds(monkeypatch):
    """A minute-rate 429 retries the SAME model after the server delay."""
    settings = Settings(gemini_api_key="k", gemini_model="model-a")
    c = llm.GeminiClient(settings)
    calls: list[str] = []

    async def fake_post(self, url, *, params, json):
        calls.append(_model_of(url))
        return _rpm_429() if len(calls) == 1 else _ok("done")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await c.generate_text("hi") == "done"
    assert calls == ["model-a", "model-a"]  # retried same model, no fallback needed


async def test_long_rpm_cooldown_switches_model(monkeypatch):
    """A long RPM cooldown should switch models instead of stalling."""
    settings = Settings(
        gemini_api_key="k", gemini_model="model-a", gemini_fallback_models="model-b"
    )
    c = llm.GeminiClient(settings)
    seen: list[str] = []

    async def fake_post(self, url, *, params, json):
        m = _model_of(url)
        seen.append(m)
        return _rpm_429("45s") if m == "model-a" else _ok()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await c.generate_text("hi") == "ok"
    assert seen == ["model-a", "model-b"]  # switched without waiting out 45s


async def test_5xx_retries_then_falls_back(monkeypatch):
    """Persistent 503 on model-a exhausts its attempts, then model-b serves."""
    settings = Settings(
        gemini_api_key="k", gemini_model="model-a", gemini_fallback_models="model-b"
    )
    c = llm.GeminiClient(settings)
    seen: list[str] = []

    async def fake_post(self, url, *, params, json):
        m = _model_of(url)
        seen.append(m)
        return httpx.Response(503, text="overloaded") if m == "model-a" else _ok()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    assert await c.generate_text("hi") == "ok"
    assert seen.count("model-a") == llm._MAX_ATTEMPTS  # retried to the cap
    assert seen[-1] == "model-b"


async def test_all_models_fail_raises(monkeypatch):
    """When every model 4xx-fails, surface a single LLMError naming the chain."""
    settings = Settings(
        gemini_api_key="k", gemini_model="model-a", gemini_fallback_models="model-b"
    )
    c = llm.GeminiClient(settings)
    seen: list[str] = []

    async def fake_post(self, url, *, params, json):
        seen.append(_model_of(url))
        return httpx.Response(400, text="bad request")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(llm.LLMError, match="All models failed"):
        await c.generate_text("hi")
    # 4xx is not retried within a model, but each model is tried once.
    assert seen == ["model-a", "model-b"]


def test_is_daily_quota_detects_per_day():
    assert llm._is_daily_quota(_daily_quota_429().json()) is True
    assert llm._is_daily_quota(_rpm_429().json()) is False


def test_retry_delay_reads_retry_info():
    assert llm._retry_delay_seconds(_rpm_429("38s").json()) == 39.0
    assert llm._retry_delay_seconds({}) == 15.0


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
