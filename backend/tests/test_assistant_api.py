"""API contract, ownership, failure recovery and third-party data boundaries."""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.api.endpoints.assistant import _stream_session_factory
from app.assistant.runtime import AssistantRuntime, AssistantUnavailable, _web_passages, get_assistant_runtime
from app.assistant.response import ChatSource, ReplyMetadata
from app.assistant.storage import ChatMessage, ChatRepository
from app.config import Settings
from app.content.seed import seed_from_dir
from app.database import get_session
from app.main import create_app
from app.models import User


class FakeAssistant(AssistantRuntime):
    def __init__(self, persistence_path):
        super().__init__(Settings(
            _env_file=None, assistant_enabled=True, brave_search_api_key="synthetic-key",
            assistant_persistence_path=str(persistence_path),
        ))
        self.calls = []
        self.fail = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    async def answer(
        self, messages, *, course_slug, lesson_slug, owner_id, session, use_web, on_event=None,
        account_key=None, thread_id=None,
    ):
        self.calls.append((messages, course_slug, lesson_slug, owner_id, use_web))
        self.started.set()
        if on_event is not None:
            for phase in ("thinking", "search_lessons", "generating"):
                await on_event("status", {"phase": phase})
            await on_event("delta", {"text": "Recall "})
        await self.release.wait()
        if self.fail:
            raise AssistantUnavailable
        return "Recall показывает, какую долю положительных примеров мы нашли.", ReplyMetadata(
            sources=[ChatSource(
                title="Precision и Recall",
                url="/courses/llm/lessons/ml-classification-metrics#precision-и-recall",
                kind="lesson",
            )],
            tool_activity=["search_lessons"],
        )


@pytest_asyncio.fixture
async def assistant_client(Session, tmp_path):
    async with Session() as session:
        await seed_from_dir(session)
    app = create_app()
    fake = FakeAssistant(tmp_path / "langgraph.sqlite3")

    async def session_override():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[_stream_session_factory] = lambda: Session
    app.dependency_overrides[get_assistant_runtime] = lambda: fake
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, fake


async def register(client, name):
    response = await client.post("/api/auth/register", json={
        "email": f"{name}@example.test", "password": "demo-only-123",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def thread_path(client, headers, **context):
    created = await client.post("/api/assistant/threads", json=context, headers=headers)
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "private, no-store"
    assert created.json()["preview"] is None
    return f"/api/assistant/threads/{created.json()['id']}"


@pytest.mark.parametrize("disconnect", (False, True))
async def test_stream_delivers_partial_text_before_commit_and_releases_lock(assistant_client, disconnect):
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers)
    payload = {"text": "Что такое Recall?", "request_id": str(uuid4())}
    fake.release.clear()
    frames = []
    received_delta = asyncio.Event()
    client_closed = asyncio.Event()
    request_pending = True

    async def receive():
        nonlocal request_pending
        if request_pending:
            request_pending = False
            return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}
        await client_closed.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        frames.append(message)
        if b"event: delta\n" in message.get("body", b""):
            received_delta.set()

    stream_path = f"{path}/messages/stream"
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1", "method": "POST", "scheme": "http", "path": stream_path,
        "query_string": b"", "server": ("test", 80), "client": ("test", 1),
        "headers": [(b"authorization", headers["Authorization"].encode()),
                    (b"content-type", b"application/json")],
    }
    task = asyncio.create_task(client._transport.app(scope, receive, send))
    try:
        await asyncio.wait_for(received_delta.wait(), timeout=4)
        assert not task.done()
        assert (await client.get(path, headers=headers)).json()["messages"] == []
        if disconnect:
            client_closed.set()
        else:
            fake.release.set()
        await asyncio.wait_for(task, timeout=4)
    finally:
        fake.release.set()
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert not fake.turn_lock.locked()
    transcript = b"".join(frame.get("body", b"") for frame in frames).decode()
    assert 'event: status\ndata: {"phase":"search_lessons"}' in transcript
    assert 'event: delta\ndata: {"text":"Recall "}' in transcript
    assert ("event: done\n" in transcript) == (not disconnect)
    messages = (await client.get(path, headers=headers)).json()["messages"]
    assert len(messages) == (0 if disconnect else 2)

    retry = await client.post(f"{path}/messages/stream", json=payload, headers=headers)
    assert retry.status_code == 200 and "event: done\n" in retry.text
    done = json.loads(retry.text.split("event: done\ndata: ", 1)[1].split("\n\n", 1)[0])
    assert done["preview"] == payload["text"]
    assert retry.headers["content-type"].startswith("text/event-stream")
    assert retry.headers["cache-control"] == "private, no-store"
    assert len(fake.calls) == (2 if disconnect else 1)


async def test_stream_checks_ownership_and_reports_generation_error(assistant_client):
    client, fake = assistant_client
    headers = await register(client, "owner")
    other = await register(client, "other")
    path = await thread_path(client, headers)
    stream = f"{path}/messages/stream"
    assert (await client.post(stream, json={"text": "Вопрос"}, headers=other)).status_code == 404
    assert not fake.calls

    fake.fail = True
    response = await client.post(stream, json={"text": "Вопрос"}, headers=headers)
    assert response.status_code == 200
    assert 'event: error\ndata: {"status":503,' in response.text
    assert "event: done" not in response.text
    assert (await client.get(path, headers=headers)).json()["messages"] == []


async def test_grounded_turn_history_and_idempotent_retry(assistant_client):
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers, course_slug="llm", lesson_slug="ml-classification-metrics")
    payload = {"text": "  Что такое Recall?  ", "request_id": str(uuid4())}
    result = await client.post(f"{path}/messages", json=payload, headers=headers)
    assert result.status_code == 200, result.text
    thread = result.json()
    assert thread["title"] == "Что такое Recall?"
    assert thread["preview"] == "Что такое Recall?"
    assert [m["role"] for m in thread["messages"]] == ["user", "assistant"]
    assert thread["messages"][1]["sources"][0]["url"].endswith("#precision-и-recall")
    assert thread["messages"][1]["tool_activity"] == ["search_lessons"]
    assert fake.calls[0][1:3] == ("llm", "ml-classification-metrics")

    retry = await client.post(f"{path}/messages", json=payload, headers=headers)
    assert retry.json() == thread
    assert len(fake.calls) == 1
    conflict = await client.post(f"{path}/messages", json={**payload, "use_web": True}, headers=headers)
    assert conflict.status_code == 409

    followup = await client.post(f"{path}/messages", json={"text": "А при смене порога?"}, headers=headers)
    assert followup.status_code == 200, followup.text
    assert len(followup.json()["messages"]) == 4
    assert [m["role"] for m in fake.calls[-1][0]] == ["user", "assistant", "user"]


async def test_threads_are_owned_and_deleting_removes_messages(assistant_client, Session):
    client, fake = assistant_client
    owner = await register(client, "owner")
    other = await register(client, "other")
    path = await thread_path(client, owner)
    await client.post(f"{path}/messages", json={"text": "Вопрос"}, headers=owner)
    assert (await client.get(path)).status_code in (401, 403)
    assert (await client.get(path, headers=other)).status_code == 404
    assert (await client.patch(path, json={"title": "Чужое"}, headers=other)).status_code == 404
    assert (await client.delete(path, headers=other)).status_code == 404
    assert (await client.post(f"{path}/messages", json={"text": "Чужое"}, headers=other)).status_code == 404
    assert (await client.get("/api/assistant/threads", headers=other)).json() == {"threads": []}
    assert len(fake.calls) == 1
    deleted = await client.delete(path, headers=owner)
    assert deleted.status_code == 204 and not deleted.content
    async with Session() as session:
        assert await session.scalar(select(func.count()).select_from(ChatMessage)) == 0


async def test_history_previews_and_renames_preserve_activity_order(assistant_client):
    client, _ = assistant_client
    headers = await register(client, "owner")
    older = await thread_path(client, headers)
    await client.post(f"{older}/messages", json={"text": "Первый вопрос"}, headers=headers)
    sent = await client.post(f"{older}/messages", json={"text": "  Новый\n\tвопрос " + "я" * 150}, headers=headers)
    assert sent.status_code == 200
    before = sent.json()
    newer = await thread_path(client, headers)
    expected_preview = ("Новый вопрос " + "я" * 150)[:120]
    assert before["preview"] == expected_preview

    renamed = await client.patch(older, json={"title": "  " + "я" * 100 + "  "}, headers=headers)
    assert renamed.status_code == 200 and renamed.headers["cache-control"] == "private, no-store"
    assert renamed.json() == {**before, "title": "я" * 100}
    assert (await client.get(older, headers=headers)).json() == renamed.json()

    history = await client.get("/api/assistant/threads", headers=headers)
    assert history.headers["cache-control"] == "private, no-store"
    newer_summary, older_summary = history.json()["threads"]
    assert newer_summary["id"] == newer.rsplit("/", 1)[-1]
    assert newer_summary["preview"] is None
    assert older_summary == {key: renamed.json()[key] for key in ("id", "title", "preview", "updated_at")}

    for invalid in ({"title": " \n "}, {"title": "я" * 101}, {"title": 3}, {"title": "Название", "extra": True}):
        rejected = await client.patch(older, json=invalid, headers=headers)
        assert rejected.status_code == 422 and rejected.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("title", ("Метрики", "Новый диалог"))
async def test_renaming_during_first_turn_keeps_title_and_reply(assistant_client, title):
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers)
    fake.release.clear()
    turn = asyncio.create_task(client.post(f"{path}/messages", json={"text": "Вопрос"}, headers=headers))
    try:
        await asyncio.wait_for(fake.started.wait(), timeout=2)
        renamed = await client.patch(path, json={"title": title}, headers=headers)
        assert renamed.status_code == 200 and renamed.json()["title"] == title
        assert renamed.json()["preview"] is None and renamed.json()["messages"] == []
    finally:
        fake.release.set()
        finished = await asyncio.wait_for(turn, timeout=2)
    assert finished.status_code == 200 and finished.json()["title"] == title
    assert finished.json()["preview"] == "Вопрос" and len(finished.json()["messages"]) == 2
    assert (await client.get(path, headers=headers)).json() == finished.json()


async def test_reissued_user_id_rejects_an_older_accounts_token(assistant_client, Session):
    client, _ = assistant_client
    previous = await register(client, "account")
    async with Session() as session:
        user = await session.scalar(select(User))
        await session.execute(update(User).where(User.id == user.id).values(
            created_at=user.created_at + timedelta(seconds=1),
        ))
        await session.commit()
    signed_in = await client.post("/api/auth/login", json={
        "email": "account@example.test", "password": "demo-only-123",
    })
    assert signed_in.status_code == 200
    current = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    path = await thread_path(client, current)
    assert (await client.get(path, headers=previous)).status_code == 401
    assert (await client.get("/api/assistant/threads", headers=previous)).status_code == 401
    assert (await client.get(path, headers=current)).status_code == 200


async def test_unavailable_and_overlapping_turns_leave_no_partial_messages(assistant_client):
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers)
    invalid = await client.post(
        f"{path}/messages", json={"text": "synthetic-private-content" * 200}, headers=headers,
    )
    assert invalid.status_code == 422 and invalid.headers["cache-control"] == "private, no-store"
    assert "synthetic-private-content" not in invalid.text
    fake.fail = True
    failed = await client.post(f"{path}/messages", json={"text": "Вопрос"}, headers=headers)
    assert failed.status_code == 503
    assert (await client.get(path, headers=headers)).json()["messages"] == []
    fake.started.clear()
    fake.release.clear()
    fake.fail = False
    turn = asyncio.create_task(client.post(f"{path}/messages", json={"text": "Вопрос"}, headers=headers))
    await asyncio.wait_for(fake.started.wait(), timeout=2)
    try:
        busy = await client.post(f"{path}/messages", json={"text": "Ещё"}, headers=headers)
        assert busy.status_code == 409
    finally:
        fake.release.set()
        finished = await asyncio.wait_for(turn, timeout=2)
    assert finished.status_code == 200 and len(finished.json()["messages"]) == 2


async def test_retry_observes_commit_between_busy_check_and_lock(assistant_client, monkeypatch):
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers)
    payload = {"text": "Вопрос", "request_id": str(uuid4())}
    stale_read = asyncio.Event()
    original_committed = asyncio.Event()
    find_request = ChatRepository.find_request

    async def pause_first_retry(repo, thread_id, request_id):
        found = await find_request(repo, thread_id, request_id)
        if found is None and fake.started.is_set() and not stale_read.is_set():
            stale_read.set()
            await original_committed.wait()
        return found

    monkeypatch.setattr(ChatRepository, "find_request", pause_first_retry)
    fake.release.clear()
    first = asyncio.create_task(client.post(f"{path}/messages", json=payload, headers=headers))
    await asyncio.wait_for(fake.started.wait(), timeout=2)
    retry = asyncio.create_task(client.post(f"{path}/messages", json=payload, headers=headers))
    try:
        await asyncio.wait_for(stale_read.wait(), timeout=2)
        fake.release.set()
        initial = await asyncio.wait_for(first, timeout=2)
    finally:
        fake.release.set()
        original_committed.set()
    replay = await asyncio.wait_for(retry, timeout=2)
    assert initial.status_code == replay.status_code == 200
    assert initial.json() == replay.json() and len(fake.calls) == 1


async def test_turn_budget_is_per_account_and_replay_does_not_spend_it(assistant_client, monkeypatch):
    monkeypatch.setattr("app.assistant.runtime._TURNS_PER_WINDOW", 1)
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers)
    request = {"text": "Вопрос", "request_id": str(uuid4())}
    assert (await client.post(f"{path}/messages", json=request, headers=headers)).status_code == 200
    assert (await client.post(f"{path}/messages", json=request, headers=headers)).status_code == 200
    capped = await client.post(f"{path}/messages", json={"text": "Другой вопрос"}, headers=headers)
    assert capped.status_code == 429 and int(capped.headers["retry-after"]) > 0
    other = await register(client, "other")
    other_path = await thread_path(client, other)
    assert (await client.post(f"{other_path}/messages", json={"text": "Вопрос"}, headers=other)).status_code == 200
    assert len(fake.calls) == 2


async def test_deleting_inflight_thread_discards_turn(assistant_client):
    client, fake = assistant_client
    headers = await register(client, "owner")
    path = await thread_path(client, headers)
    fake.release.clear()
    turn = asyncio.create_task(client.post(f"{path}/messages", json={"text": "Вопрос"}, headers=headers))
    await asyncio.wait_for(fake.started.wait(), timeout=2)
    try:
        assert (await client.delete(path, headers=headers)).status_code == 204
    finally:
        fake.release.set()
        finished = await asyncio.wait_for(turn, timeout=2)
    assert finished.status_code == 404
    assert (await client.get(path, headers=headers)).status_code == 404


async def test_web_api_sends_only_approved_text_and_filters_unsafe_links():
    async def handler(request):
        assert request.method == "POST"
        assert request.url.host == "api.search.brave.com"
        assert request.headers["X-Subscription-Token"] == "synthetic-key"
        assert json.loads(request.content)["q"] == "Что нового в Python 3.13?"
        return httpx.Response(200, json={"grounding": {"generic": [
            {"url": "https://docs.python.org/3/whatsnew/3.13.html", "title": "Python 3.13", "snippets": ["Free threading"]},
            {"url": "javascript:alert(1)", "title": "Unsafe", "snippets": ["bad link"]},
            {"url": "https://me:password@example.test", "title": "Unsafe", "snippets": ["bad link"]},
        ]}})

    passages = await _web_passages(
        "synthetic-key", "  Что нового в Python 3.13?  ", transport=httpx.MockTransport(handler),
    )
    assert passages == [("Python 3.13", "https://docs.python.org/3/whatsnew/3.13.html", "Free threading")]


async def test_chat_runs_langgraph_and_hybrid_tools_before_citing(assistant_client, tmp_path):
    import numpy as np

    from app.assistant.provider import GigaChatModel
    from app.assistant.retrieval import LessonRetriever, build_index

    class SmallEmbedder:
        fingerprint = "assistant-api-test"

        def embed(self, texts, *, passage):
            return np.array([[1.0, 0.0] if "recall" in text.casefold() else [0.1, 1.0] for text in texts])

    client, injected = assistant_client
    content = tmp_path / "content"
    course = content / "courses" / "llm"
    course.mkdir(parents=True)
    (course / "metadata.json").write_text(json.dumps({
        "slug": "llm", "title": "LLM",
        "lessons": [{"slug": "ml-classification-metrics", "title": "Метрики", "file": "metrics.md"}],
    }), encoding="utf-8")
    (course / "metrics.md").write_text(
        "# Метрики\n\n## Precision и Recall\nRecall = TP / (TP + FN).\n", encoding="utf-8",
    )
    index = tmp_path / "lessons.sqlite3"
    embedder = SmallEmbedder()
    build_index(content, tmp_path, index, embedder=embedder)
    injected.retriever = LessonRetriever(index, tmp_path, content_dir=content, embedder=embedder)
    injected.settings = injected.settings.model_copy(update={"gigachat_credentials": "test-credentials"})
    injected.answer = AssistantRuntime.answer.__get__(injected)
    provider_calls = []

    async def model_transport(request):
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "synthetic-token", "expires_at": 4102444800})
        body = json.loads(request.content)
        message = body["messages"][-1]
        provider_calls.append(message["role"])
        if message["role"] == "user":
            assert {tool["name"] for tool in body["functions"]} == {
                "search_lessons", "read_lesson_section",
            }
            reply = {"role": "assistant", "content": "", "function_call": {
                "name": "search_lessons", "arguments": {"query": "Что такое Recall"},
            }}
            return httpx.Response(200, json={"choices": [{"message": reply, "finish_reason": "function_call"}]})
        evidence = json.loads(message["content"])["data"]["sections"][0]
        assert "Recall = TP / (TP + FN)" in evidence["text"]
        response = (
            '{"ready":true}' if body["function_call"] == "auto"
            else json.dumps({"text": "Recall = TP / (TP + FN).", "source_ids": [evidence["source_id"]]})
        )
        return httpx.Response(200, json={"choices": [{
            "message": {"role": "assistant", "content": response}, "finish_reason": "stop",
        }]})

    injected.model = GigaChatModel(credentials="test-credentials", transport=httpx.MockTransport(model_transport))
    headers = await register(client, "owner")
    path = await thread_path(client, headers, course_slug="llm", lesson_slug="ml-classification-metrics")
    result = await client.post(f"{path}/messages", json={"text": "Что такое Recall?"}, headers=headers)
    assert result.status_code == 200, result.text
    reply = result.json()["messages"][-1]
    assert reply["text"] == "Recall = TP / (TP + FN)."
    assert reply["sources"][0]["url"].endswith("#precision-%D0%B8-recall")
    assert provider_calls == ["user", "function", "function"]


@pytest.mark.parametrize("scoped_search", (False, True))
async def test_langgraph_question_recovers_and_streams(assistant_client, scoped_search):
    from app.assistant.graph import FALLBACK_EVIDENCE_PREFIX
    from app.assistant.provider import GigaChatModel
    from app.assistant.retrieval import LessonHit

    class LangGraphRetriever:
        def search(self, query, *, limit, course_slug, lesson_slug):
            if lesson_slug:
                assert scoped_search and lesson_slug == "ml-classification-metrics"
                return [LessonHit(
                    "llm/ml-classification-metrics#recall:0", "llm", lesson_slug,
                    "recall", "Recall", "Recall — полнота классификации.",
                )]
            assert query == "Чем отличаются checkpoints и Store в LangGraph?"
            assert course_slug is lesson_slug is None
            return [LessonHit(
                "llm/langgraph-persistence#checkpointer-сохраняет-снимки:0",
                "llm", "langgraph-persistence", "checkpointer-сохраняет-снимки", "Checkpointer сохраняет снимки",
                "Checkpointer хранит снимки состояния диалога. Store хранит данные между диалогами.",
            )]

    async def transport(request):
        if request.url.path.endswith("/oauth"):
            return httpx.Response(200, json={"access_token": "synthetic-token", "expires_at": 4102444800})
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if not body.get("stream"):
            assert body["function_call"] == "auto"
            if scoped_search and body["messages"][-1]["role"] == "user":
                return httpx.Response(200, json={"choices": [{
                    "message": {"role": "assistant", "content": "", "function_call": {
                        "name": "search_lessons", "arguments": {"query": "LangGraph"},
                    }},
                    "finish_reason": "function_call",
                }]})
            return httpx.Response(200, json={"choices": [{
                "message": {"role": "assistant", "content": '{"ready":true}'},
                "finish_reason": "stop",
            }]})
        assert body["function_call"] == "none"
        _, marker, tail = system.partition(FALLBACK_EVIDENCE_PREFIX)
        if not marker:
            assert scoped_search
            chunks = ['{"source_ids":[],"text":"Не хватает материалов."}']
        else:
            fallback, _ = json.JSONDecoder().raw_decode(tail)
            source_id = "S2" if scoped_search else "S1"
            assert fallback["data"]["sections"][0]["source_id"] == source_id
            chunks = ['{"source_ids":["' + source_id + '"],"text":"Снимки', ' состояния и память между диалогами."}']
        frames = "".join(
            "data: " + json.dumps({"choices": [{"delta": {"content": chunk}}]}, ensure_ascii=False) + "\n\n"
            for chunk in chunks
        ) + "data: [DONE]\n\n"
        return httpx.Response(200, text=frames, headers={"Content-Type": "text/event-stream"})

    client, runtime = assistant_client
    runtime.settings = runtime.settings.model_copy(update={"gigachat_credentials": "test-key"})
    runtime.answer = AssistantRuntime.answer.__get__(runtime)
    runtime.retriever = LangGraphRetriever()
    runtime.model = GigaChatModel(credentials="test-key", transport=httpx.MockTransport(transport))
    owner = await register(client, "langgraph-owner")
    context = {"course_slug": "llm", "lesson_slug": "ml-classification-metrics"} if scoped_search else {}
    path = await thread_path(client, owner, **context)
    result = await client.post(f"{path}/messages/stream", json={
        "text": "Чем отличаются checkpoints и Store в LangGraph?",
    }, headers=owner)
    assert result.status_code == 200
    assert 'event: status\ndata: {"phase":"search_lessons"}' in result.text
    assert 'event: delta\ndata: {"text":"Снимки"}' in result.text
    assert "event: done" in result.text
    saved = (await client.get(path, headers=owner)).json()["messages"][-1]
    assert saved["text"] == "Снимки состояния и память между диалогами."
    assert "/lessons/langgraph-persistence#" in saved["sources"][0]["url"]
    checkpoints = [item async for item in runtime.checkpointer.alist(None)]
    assert checkpoints
    assert (await client.delete(path, headers=owner)).status_code == 204
    reopened = AssistantRuntime(runtime.settings)
    assert [item async for item in reopened.checkpointer.alist(None)] == []


async def test_explicit_memory_survives_reopen_and_is_scoped_to_account(assistant_client, monkeypatch):
    client, runtime = assistant_client
    runtime.answer = AssistantRuntime.answer.__get__(runtime)
    owner = await register(client, "memory-owner")
    other = await register(client, "other-account")

    async def send(path, headers, text):
        result = await client.post(f"{path}/messages", json={"text": text}, headers=headers)
        assert result.status_code == 200
        return result.json()["messages"][-1]["text"]

    first = await thread_path(client, owner)
    assert "Заметка сохранена" in await send(first, owner, "Запомни: отвечай с примерами")
    app = client._transport.app
    reopened = AssistantRuntime(runtime.settings)
    app.dependency_overrides[get_assistant_runtime] = lambda: reopened
    second = await thread_path(client, owner)
    other_thread = await thread_path(client, other)
    assert "отвечай с примерами" in await send(second, owner, "Что ты обо мне помнишь?")
    assert await send(other_thread, other, "Что ты обо мне помнишь?") == "Сохранённых заметок пока нет."

    async def reject_turn(*args, **kwargs):
        raise SQLAlchemyError("simulated commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(ChatRepository, "append_turn", reject_turn)
        rejected = await client.post(f"{second}/messages", json={"text": "Забудь всё обо мне"}, headers=owner)
        assert rejected.status_code == 503
    assert "отвечай с примерами" in await send(second, owner, "Что ты обо мне помнишь?")
    assert "удалена" in await send(second, owner, "Забудь всё обо мне")
    assert await send(first, owner, "Что ты обо мне помнишь?") == "Сохранённых заметок пока нет."
