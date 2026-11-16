"""GigaChat v1 transport for assistant messages and native function calls."""
from __future__ import annotations

import asyncio
import json
import socket
import ssl
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx


class AssistantModelError(Exception):
    """The assistant provider could not complete a request."""


def _connection_error(exc: BaseException, stage: str) -> AssistantModelError:
    if stage == "TLS setup":
        return AssistantModelError("GigaChat could not load CA certificates. Check GIGACHAT_CA_FILE or SSL_CERT_FILE")
    if isinstance(exc, httpx.TimeoutException):
        return AssistantModelError(f"GigaChat {stage} request timed out")
    if isinstance(exc, httpx.ProxyError):
        return AssistantModelError(f"GigaChat {stage} proxy connection failed")
    cause: BaseException | None = exc
    while cause is not None:
        if isinstance(cause, ssl.SSLCertVerificationError):
            return AssistantModelError(f"GigaChat {stage} TLS certificate verification failed. Check GIGACHAT_CA_FILE")
        if isinstance(cause, socket.gaierror):
            return AssistantModelError(f"GigaChat {stage} DNS lookup failed")
        cause = cause.__cause__
    return AssistantModelError(f"GigaChat {stage} connection failed")


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    state_id: str | None = None


@dataclass(frozen=True)
class ModelReply:
    text: str = ""
    tool_call: ToolCall | None = None
    finish_reason: str = "stop"


class AssistantModel(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: str = "auto",
    ) -> ModelReply: ...


@dataclass(frozen=True, repr=False)
class _AccessToken:
    value: str
    expires_at: float

    def usable(self, rejected: str | None) -> bool:
        return self.value != rejected and time.time() + 30 < self.expires_at


class GigaChatModel:
    """Obtain and reuse an OAuth token, refreshing once on an HTTP 401."""

    def __init__(
        self,
        *,
        credentials: str,
        scope: str = "GIGACHAT_API_PERS",
        base_url: str = "https://api.giga.chat/v1",
        oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        model: str = "GigaChat-2-Pro",
        ca_file: str | None = None,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._credentials = credentials.strip()
        self._scope = scope
        self._chat_url = f"{base_url.rstrip('/')}/chat/completions"
        self._oauth_url = oauth_url
        self._model = model
        self._ca_file = ca_file
        self._timeout = timeout
        self._transport = transport
        self._token: _AccessToken | None = None
        self._token_lock = asyncio.Lock()

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: str = "auto",
    ) -> ModelReply:
        return await self._complete(self._payload(messages, tools, tool_choice))

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        on_delta: Callable[[str], Awaitable[None]],
        tool_choice: str = "auto",
    ) -> ModelReply:
        if tools and tool_choice != "none":
            raise AssistantModelError("GigaChat streaming requires function calls to be disabled")
        payload = self._payload(messages, tools, tool_choice)
        payload["stream"] = True
        return await self._complete(payload, on_delta=on_delta)

    def _payload(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tool_choice: str
    ) -> dict[str, Any]:
        if not self._credentials or not self._model:
            raise AssistantModelError("GigaChat is not configured")
        if not self._credentials.isascii() or not self._credentials.isprintable() or " " in self._credentials:
            raise AssistantModelError("GigaChat credentials have an invalid format")
        if not all(self._valid_url(url) for url in (self._oauth_url, self._chat_url)):
            raise AssistantModelError("GigaChat requires HTTPS endpoints")

        function_call: str | dict[str, str] = "none"
        if tools and tool_choice != "none":
            function_call = "auto" if tool_choice == "auto" else {"name": tool_choice}
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "function_call": function_call,
            "max_tokens": 2400,
            "temperature": 0.2,
        }
        if tools:
            payload["functions"] = tools
        return payload

    async def _complete(
        self,
        payload: dict[str, Any],
        *,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelReply:
        stage = "TLS setup"
        accept = "text/event-stream" if on_delta is not None else "application/json"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._tls_context(),
                transport=self._transport,
            ) as client:
                token = None
                for _ in range(2):
                    stage = "OAuth"
                    token = await self._get_token(client, rejected=token)
                    stage = "API"
                    async with client.stream(
                        "POST",
                        self._chat_url,
                        headers={"Authorization": f"Bearer {token}", "Accept": accept},
                        json=payload,
                    ) as response:
                        if response.status_code == 200:
                            if on_delta is not None:
                                return await _parse_stream_reply(response, on_delta)
                            await response.aread()
                            return _parse_reply(response)
                    if response.status_code != 401:
                        break
                if response.status_code == 401 and self._token and self._token.value == token:
                    self._token = None
        except (httpx.DecodingError, httpx.TransportError, OSError, UnicodeError) as exc:
            raise _connection_error(exc, stage) from None

        raise AssistantModelError(f"GigaChat completion failed (HTTP {response.status_code})")

    @staticmethod
    def _valid_url(value: str) -> bool:
        try:
            url = httpx.URL(value)
        except httpx.InvalidURL:
            return False
        return url.scheme == "https" and bool(url.host) and not (url.userinfo or url.query or url.fragment)

    def _tls_context(self) -> bool | ssl.SSLContext:
        if not self._ca_file:
            return True
        context = httpx.create_ssl_context()
        context.load_verify_locations(cafile=self._ca_file)
        return context

    async def _get_token(self, client: httpx.AsyncClient, rejected: str | None = None) -> str:
        if self._token and self._token.usable(rejected):
            return self._token.value
        async with self._token_lock:
            if self._token and self._token.usable(rejected):
                return self._token.value
            response = await client.post(
                self._oauth_url,
                headers={
                    "Authorization": f"Basic {self._credentials}",
                    "Accept": "application/json",
                    "RqUID": str(uuid4()),
                },
                data={"scope": self._scope},
            )
            if response.status_code != 200:
                raise AssistantModelError(f"GigaChat authorization failed (HTTP {response.status_code})")
            try:
                payload = response.json()
                token = payload["access_token"]
                expires_at = payload["expires_at"]
                if not isinstance(token, str) or not token.isascii() or not token.isprintable() or " " in token:
                    raise ValueError
                if type(expires_at) not in (float, int) or not 0 < expires_at < 10**14:
                    raise ValueError
                # The REST response can use Unix seconds or milliseconds.
                if expires_at > 10**11:
                    expires_at /= 1000
                if expires_at <= time.time():
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise AssistantModelError("GigaChat returned an invalid access token") from None
            self._token = _AccessToken(token, expires_at)
            return token


async def _stream_lines(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    pending = b""
    skip_lf = False
    async with aclosing(response.aiter_bytes()) as chunks:
        async for chunk in chunks:
            if skip_lf:
                chunk = chunk.removeprefix(b"\n")
            skip_lf = chunk.endswith(b"\r")
            lines = (pending + chunk).splitlines(keepends=True)
            pending = b""
            for line in lines:
                if line.endswith((b"\r", b"\n")):
                    yield line.rstrip(b"\r\n")
                else:
                    pending = line


async def _stream_events(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    data_lines: list[bytes] = []
    first_line = True
    async with aclosing(_stream_lines(response)) as lines:
        async for line in lines:
            if first_line:
                line = line.removeprefix(b"\xef\xbb\xbf")
                first_line = False
            if not line:
                if data_lines:
                    yield b"\n".join(data_lines)
                    data_lines.clear()
                continue
            field, _, value = line.partition(b":")
            value = value.removeprefix(b" ")
            if field == b"event" and value == b"error":
                raise AssistantModelError("GigaChat returned a streaming error")
            if field == b"data":
                # GigaChat can end its [DONE] line with a single newline.
                if value == b"[DONE]" and not data_lines:
                    yield value
                    return
                data_lines.append(value)


async def _parse_stream_reply(
    response: httpx.Response, on_delta: Callable[[str], Awaitable[None]]
) -> ModelReply:
    content_type = response.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type != "text/event-stream":
        raise AssistantModelError("GigaChat returned an invalid response type for streaming")

    parts: list[str] = []
    finish_reason: str | None = None
    async with aclosing(_stream_events(response)) as events:
        async for event in events:
            if event == b"[DONE]":
                text = "".join(parts)
                if finish_reason is not None or text.strip():
                    return ModelReply(text=text, finish_reason=finish_reason or "stop")
                break
            content, reason = _parse_stream_event(event)
            if finish_reason is not None and (content or reason is not None):
                raise AssistantModelError("GigaChat sent data after the completion finished")
            if content:
                parts.append(content)
                await on_delta(content)
            if reason is not None:
                finish_reason = reason
    raise AssistantModelError("GigaChat stream ended before the completion finished")


def _parse_stream_event(event: bytes) -> tuple[str, str | None]:
    try:
        payload = json.loads(event.decode("utf-8"))
        choices = payload["choices"]
        if not isinstance(choices, list) or "error" in payload:
            raise ValueError
        if not choices:
            return "", None
        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")
        if finish_reason not in (None, "stop", "length"):
            raise ValueError
        if delta.get("role") not in (None, "assistant") or delta.get("function_call") is not None:
            raise ValueError
        content = delta.get("content")
        if content is not None:
            if not isinstance(content, str):
                raise ValueError
            # JSON escapes can introduce lone surrogates even in valid UTF-8 events.
            content.encode("utf-8")
    except (AttributeError, KeyError, TypeError, ValueError):
        raise AssistantModelError("GigaChat returned an invalid streaming completion") from None
    return content or "", finish_reason


def _parse_reply(response: httpx.Response) -> ModelReply:
    try:
        choice = response.json()["choices"][0]
        message = choice["message"]
        finish_reason = choice["finish_reason"]
        if message["role"] != "assistant" or not isinstance(finish_reason, str):
            raise ValueError
        text = message.get("content")
        if text is not None and not isinstance(text, str):
            raise ValueError
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        raise AssistantModelError("GigaChat returned an invalid completion") from None

    if finish_reason != "function_call":
        return ModelReply(text=text or "", finish_reason=finish_reason)

    call = message.get("function_call")
    state_id = message.get("functions_state_id")
    if (
        not isinstance(call, dict)
        or not isinstance(call.get("name"), str)
        or not isinstance(call.get("arguments"), dict)
        or (state_id is not None and not isinstance(state_id, str))
    ):
        return ModelReply(finish_reason="error")
    return ModelReply(text=text or "", tool_call=ToolCall(call["name"], call["arguments"], state_id))
