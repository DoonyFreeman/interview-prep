import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx
import pytest

from app.assistant.provider import AssistantModelError, GigaChatModel, ModelReply


_MESSAGES = [{"role": "user", "content": "Объясни JOIN"}]
_STREAM_HEADERS = {"Content-Type": "text/event-stream; charset=utf-8"}
_DONE = b"data: [DONE]\n"


def _event(delta: dict, reason: str | None = None) -> bytes:
    choice = {"delta": delta, "index": 0, "finish_reason": reason}
    data = json.dumps({"choices": [choice]}, ensure_ascii=False).encode()
    return b"data: " + data + b"\n\n"


def _token(value: str = "test-token") -> httpx.Response:
    return httpx.Response(200, json={"access_token": value, "expires_at": time.time() + 90})


class _Stream(httpx.AsyncByteStream):
    def __init__(self, *chunks: bytes | Exception) -> None:
        self.chunks = chunks
        self.read = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            self.read += 1
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def run_async():
    # Runner finalizes HTTPX's internal async iterators even on early exit.
    with asyncio.Runner() as runner:
        yield runner.run


@pytest.mark.parametrize("finish", [b"", _event({"content": ""}, "stop")])
def test_stream_emits_content_before_the_next_chunk_and_handles_sse_framing(finish, run_async):
    first = _event({"role": "assistant", "content": "связь\u2028таблиц", "reasoning_content": "hidden"})
    split = first.index("с".encode()) + 1
    stream = _Stream(
        b"\xef\xbb\xbf: keep alive\r",
        b"\n\r\n" + first[:split],
        first[split:],
        'data: {"choices":\r\ndata: [{"delta": {"content": " через JOIN"}}]}\r'.encode(),
        b"\n\r\n" + _event({"reasoning_content": "also hidden"}),
        finish + b'data: {"choices":[],"usage":{}}\n\n' + _DONE,
    )
    received = []

    def handler(request):
        if request.url.path.endswith("/oauth"):
            return _token()
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.headers["accept"] == "text/event-stream"
        payload = json.loads(request.content)
        assert payload["messages"] == _MESSAGES
        assert payload["stream"] is True
        assert payload["function_call"] == "none"
        assert "functions" not in payload
        return httpx.Response(200, headers=_STREAM_HEADERS, stream=stream)

    async def on_delta(text: str) -> None:
        received.append((text, stream.read))

    model = GigaChatModel(credentials="test-credentials", transport=httpx.MockTransport(handler))
    reply = run_async(model.complete_stream(_MESSAGES, [], on_delta=on_delta))

    assert received == [("связь\u2028таблиц", 3), (" через JOIN", 5)]
    assert reply == ModelReply(text="связь\u2028таблиц через JOIN")
    assert stream.closed


@pytest.mark.parametrize("continues_unauthorized", [False, True])
def test_stream_refreshes_rejected_oauth_token_only_once(continues_unauthorized, run_async):
    tokens = []
    rejected_streams = []
    attempted_tokens = []
    received = []
    tools = [{"name": "search_lessons", "parameters": {"type": "object"}}]

    def handler(request):
        if request.url.path.endswith("/oauth"):
            tokens.append(f"test-token-{len(tokens) + 1}")
            return _token(tokens[-1])
        attempted_tokens.append(request.headers["authorization"])
        payload = json.loads(request.content)
        assert payload["function_call"] == "none"
        assert payload["functions"] == tools
        if len(attempted_tokens) == 1 or continues_unauthorized:
            rejected = _Stream(b"private provider error details")
            rejected_streams.append(rejected)
            return httpx.Response(401, stream=rejected)
        return httpx.Response(200, headers=_STREAM_HEADERS, stream=_Stream(
            _event({"content": "Ответ"}, "length"), _DONE,
        ))

    async def on_delta(text: str) -> None:
        received.append(text)

    model = GigaChatModel(credentials="test-credentials", transport=httpx.MockTransport(handler))
    if continues_unauthorized:
        with pytest.raises(AssistantModelError, match=r"^GigaChat completion failed \(HTTP 401\)$"):
            run_async(model.complete_stream(_MESSAGES, tools, on_delta=on_delta, tool_choice="none"))
        assert received == []
    else:
        reply = run_async(model.complete_stream(_MESSAGES, tools, on_delta=on_delta, tool_choice="none"))
        assert reply == ModelReply(text="Ответ", finish_reason="length")
        assert received == ["Ответ"]
    assert attempted_tokens == ["Bearer test-token-1", "Bearer test-token-2"]
    assert all(stream.closed and stream.read == 0 for stream in rejected_streams)


@pytest.mark.parametrize(("tail", "message"), [
    ((_event({}, "stop"),), "GigaChat stream ended before the completion finished"),
    ((_event({}, "stop"), b"data: [DON"), "GigaChat stream ended before the completion finished"),
    ((b'data: {"error":"private provider details"}\n\n',), "GigaChat returned an invalid streaming completion"),
    ((b"data: \xff\n\n",), "GigaChat returned an invalid streaming completion"),
    ((b'data: {"choices":[{"delta":{"content":"\\ud800"}}]}\n\n',), "GigaChat returned an invalid streaming completion"),
    ((_event({}, "function_call"), _DONE), "GigaChat returned an invalid streaming completion"),
    ((httpx.ReadError("private provider details"),), "GigaChat API connection failed"),
])
def test_stream_failures_close_without_retrying_after_a_delta(tail, message, run_async):
    requests = []
    stream = _Stream(_event({"content": "Начало"}), *tail)
    received = []

    def handler(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/oauth"):
            return _token()
        return httpx.Response(200, headers=_STREAM_HEADERS, stream=stream)

    async def on_delta(text: str) -> None:
        received.append(text)

    model = GigaChatModel(credentials="test-credentials", transport=httpx.MockTransport(handler))
    with pytest.raises(AssistantModelError) as caught:
        run_async(model.complete_stream(_MESSAGES, [], on_delta=on_delta))

    assert str(caught.value) == message
    assert received == ["Начало"]
    assert requests == ["/api/v2/oauth", "/v1/chat/completions"]
    assert stream.closed


def test_stream_cancellation_closes_provider_response(run_async):
    received_delta = asyncio.Event()
    stream = _Stream(_event({"content": "Начало"}), _event({}, "stop"), _DONE)

    def handler(request):
        if request.url.path.endswith("/oauth"):
            return _token()
        return httpx.Response(200, headers=_STREAM_HEADERS, stream=stream)

    async def on_delta(text: str) -> None:
        received_delta.set()
        await asyncio.Future()

    model = GigaChatModel(credentials="test-credentials", transport=httpx.MockTransport(handler))

    async def cancel_after_delta():
        task = asyncio.create_task(model.complete_stream(_MESSAGES, [], on_delta=on_delta))
        try:
            await asyncio.wait_for(received_delta.wait(), timeout=1)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    run_async(cancel_after_delta())

    assert stream.read == 1
    assert stream.closed
