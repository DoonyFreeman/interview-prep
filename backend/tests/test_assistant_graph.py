"""Assistant graph and GigaChat protocol checks without live credentials."""
from __future__ import annotations

import asyncio
import json
import socket
import ssl
import time
from uuid import UUID

import httpx
from pydantic import BaseModel, Field
import pytest

from app.assistant.graph import AssistantTool, ToolResult, run_assistant
from app.assistant.provider import AssistantModelError, GigaChatModel, ModelReply, ToolCall


_HISTORY = [
    {"role": "user", "content": "Разбираю SQL"},
    {"role": "assistant", "content": "Какую тему?"},
    {"role": "user", "content": "Как работает INNER JOIN?"},
]
_SOURCE = "sql:joins:inner-join"
_ANSWER = "INNER JOIN возвращает строки, для которых выполняется условие соединения."


class _Query(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class _Model:
    def __init__(self, *replies: ModelReply) -> None:
        self.replies = iter(replies)
        self.requests = []

    async def complete(self, messages, tools, *, tool_choice="auto") -> ModelReply:
        self.requests.append((messages, tools, tool_choice))
        return next(self.replies)


def _final(*ids: str, text: str = _ANSWER) -> ModelReply:
    return ModelReply(text=json.dumps({"text": text, "source_ids": list(ids)}))


def _search(run) -> AssistantTool:
    return AssistantTool("search_lessons", "Найти материалы в уроках", _Query, run)


async def _matching_lesson(arguments):
    assert arguments == {"query": "inner join"}
    return ToolResult({"excerpt": _ANSWER}, (_SOURCE,))


@pytest.mark.asyncio
async def test_native_gigachat_function_round_trip_preserves_history_and_citations():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/oauth"):
            assert request.headers["authorization"] == "Basic fake-credentials"
            assert UUID(request.headers["rquid"]).version == 4
            assert request.content == b"scope=GIGACHAT_API_PERS"
            return httpx.Response(200, json={"access_token": "fake-token", "expires_at": (time.time() + 120) * 1000})

        assert request.url == httpx.URL("https://api.giga.chat/v1/chat/completions")
        assert request.headers["authorization"] == "Bearer fake-token"
        body = json.loads(request.content)
        assert body["model"] == "GigaChat-2-Pro"
        assert body["function_call"] == "auto"
        assert [tool["name"] for tool in body["functions"]] == ["search_lessons"]
        assert body["functions"][0]["parameters"]["required"] == ["query"]
        assert body["messages"][0]["role"] == "system"
        assert "SQL / JOIN" in body["messages"][0]["content"]
        assert body["messages"][1:4] == _HISTORY

        call_message = {
            "role": "assistant",
            "content": "",
            "function_call": {"name": "search_lessons", "arguments": {"query": "inner join"}},
            "functions_state_id": "de745097-644b-4e3e-abe0-9c55931d17bf",
        }
        if len(requests) == 2:
            return httpx.Response(200, json={"choices": [{"message": call_message, "finish_reason": "function_call"}]})

        assistant_message, function_message = body["messages"][-2:]
        assert assistant_message == call_message
        assert function_message["role"] == "function"
        assert function_message["name"] == "search_lessons"
        assert json.loads(function_message["content"]) == {
            "data": {"excerpt": _ANSWER},
            "source_ids": [_SOURCE],
        }
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": _final(_SOURCE).text}, "finish_reason": "stop"}
        ]})

    model = GigaChatModel(credentials="fake-credentials", transport=httpx.MockTransport(handler))
    reply = await run_assistant(model, _HISTORY, [_search(_matching_lesson)], lesson_context="SQL / JOIN")

    assert len(requests) == 3
    assert reply.text == _ANSWER
    assert reply.source_ids == (_SOURCE,)
    assert reply.tools_used == ("search_lessons",)


@pytest.mark.asyncio
async def test_oauth_refresh_is_shared_by_parallel_requests_and_retries_once():
    token_requests = 0
    attempted_tokens = []

    async def handler(request):
        nonlocal token_requests
        if request.url.path.endswith("/oauth"):
            token_requests += 1
            count = token_requests
            await asyncio.sleep(0)
            return httpx.Response(200, json={"access_token": f"token-{count}", "expires_at": time.time() + 120})
        assert json.loads(request.content)["function_call"] == "none"
        token = request.headers["authorization"]
        attempted_tokens.append(token)
        if token == "Bearer token-1":
            await asyncio.sleep(0)
            return httpx.Response(401, text="sensitive vendor detail")
        return httpx.Response(200, json={"choices": [
            {"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ]})

    model = GigaChatModel(credentials="fake-credentials", transport=httpx.MockTransport(handler))
    replies = await asyncio.gather(*(model.complete(_HISTORY, []) for _ in range(3)))

    assert [reply.text for reply in replies] == ["ok"] * 3
    assert token_requests == 2
    assert attempted_tokens == ["Bearer token-1"] * 3 + ["Bearer token-2"] * 3


@pytest.mark.asyncio
async def test_provider_error_only_exposes_status():
    def handler(request):
        return httpx.Response(403, text="fake-credentials and vendor request dump")

    model = GigaChatModel(credentials="fake-credentials", transport=httpx.MockTransport(handler))
    with pytest.raises(AssistantModelError, match=r"^GigaChat authorization failed \(HTTP 403\)$"):
        await model.complete(_HISTORY, [])


@pytest.mark.parametrize(("cause", "message"), [
    (ssl.SSLCertVerificationError("sensitive TLS details"),
     "GigaChat OAuth TLS certificate verification failed. Check GIGACHAT_CA_FILE"),
    (socket.gaierror("sensitive DNS details"), "GigaChat OAuth DNS lookup failed"),
])
async def test_transport_diagnostics_are_specific_and_redacted(cause, message):
    def handler(request):
        raise httpx.ConnectError("sensitive transport details", request=request) from cause

    model = GigaChatModel(credentials="fake-credentials", transport=httpx.MockTransport(handler))
    with pytest.raises(AssistantModelError) as caught:
        await model.complete(_HISTORY, [])

    assert str(caught.value) == message
    assert caught.value.__suppress_context__


def test_custom_ca_extends_httpx_trust_store(monkeypatch):
    class TrustStore:
        def load_verify_locations(self, *, cafile):
            self.loaded = cafile

    context = TrustStore()
    monkeypatch.setattr(httpx, "create_ssl_context", lambda: context)

    model = GigaChatModel(credentials="fake-credentials", ca_file="custom-ca.crt")

    assert model._tls_context() is context
    assert context.loaded == "custom-ca.crt"


@pytest.mark.asyncio
async def test_forged_citations_receive_one_grounded_repair():
    call = ModelReply(tool_call=ToolCall("search_lessons", {"query": "inner join"}))
    model = _Model(call, _final(_SOURCE, "forged-id", text="Unverified claim"), _final(_SOURCE, _SOURCE))

    reply = await run_assistant(model, _HISTORY, [_search(_matching_lesson)])

    assert reply.text == _ANSWER
    assert reply.source_ids == (_SOURCE,)
    messages, _, mode = model.requests[-1]
    assert mode == "none"
    assert _SOURCE in messages[0]["content"]
    assert "forged-id" not in messages[0]["content"]


@pytest.mark.asyncio
async def test_missing_evidence_forces_search_and_rejects_unverified_answer():
    searched = []

    async def search(arguments):
        searched.append(arguments)
        return ToolResult({"matches": []})

    call = ModelReply(tool_call=ToolCall("search_lessons", {"query": "inner join"}))
    model = _Model(_final(_SOURCE, text="Unverified claim"), call, _final(_SOURCE, text="Unverified claim"))

    reply = await run_assistant(model, _HISTORY, [_search(search)])

    assert searched == [{"query": "inner join"}]
    assert [mode for _, _, mode in model.requests] == ["auto", "search_lessons", "auto"]
    assert "Уточни тему" in reply.text
    assert reply.source_ids == ()


@pytest.mark.asyncio
async def test_disallowed_invalid_and_duplicate_calls_are_bounded():
    invoked = []

    async def search(arguments):
        invoked.append(arguments)
        return await _matching_lesson(arguments)

    search_call = ModelReply(tool_call=ToolCall("search_lessons", {"query": "inner join"}))
    model = _Model(
        ModelReply(tool_call=ToolCall("web_search", {"query": "private text"})),
        ModelReply(tool_call=ToolCall("search_lessons", {"query": 42})),
        search_call,
        search_call,
        _final(_SOURCE),
    )

    reply = await run_assistant(model, _HISTORY, [_search(search)])

    assert invoked == [{"query": "inner join"}]
    assert reply.tools_used == ("search_lessons",)
    assert reply.source_ids == (_SOURCE,)
    messages, definitions, mode = model.requests[-1]
    assert mode == "none"
    assert [item["name"] for item in definitions] == ["search_lessons"]
    assert "вызов уже выполнен" in json.loads(messages[-1]["content"])["error"]
    assert "private text" not in json.dumps(messages)


@pytest.mark.asyncio
async def test_invalid_final_after_repair_returns_fallback():
    call = ModelReply(tool_call=ToolCall("search_lessons", {"query": "inner join"}))
    model = _Model(call, ModelReply(text="not JSON"), _final("forged-id"))

    reply = await run_assistant(model, _HISTORY, [_search(_matching_lesson)])

    assert "Уточни тему" in reply.text
    assert reply.source_ids == ()
    assert len(model.requests) == 3


@pytest.mark.asyncio
async def test_turn_timeout_cancels_model():
    stopped = asyncio.Event()

    class SlowModel:
        async def complete(self, messages, tools, *, tool_choice="auto") -> ModelReply:
            try:
                await asyncio.sleep(30)
            finally:
                stopped.set()

    with pytest.raises(AssistantModelError, match="timed out"):
        await run_assistant(SlowModel(), _HISTORY, [], timeout=0.05)
    assert stopped.is_set()
