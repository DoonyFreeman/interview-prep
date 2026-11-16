"""Authenticated assistant conversations and complete question/answer turns."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from hashlib import sha256
from typing import Any
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Send

from app.assistant.runtime import AssistantRuntime, AssistantUnavailable, get_assistant_runtime
from app.assistant.storage import (
    MAX_TURNS, ChatRepository, ChatThread, CreateThread, RenameThread, SendMessage, ThreadList, ThreadOut,
)
from app.auth.dependencies import get_current_user, has_account_bound_token
from app.database import SessionLocal, get_session
from app.models import User
from app.repositories import CourseRepository, LessonRepository


_PRIVATE = {"Cache-Control": "private, no-store"}
_EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]
_logger = logging.getLogger(__name__)


class _PrivateChatRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def respond(request: Request) -> Response:
            try:
                response = await handler(request)
            except RequestValidationError:
                return JSONResponse({"detail": "Проверь параметры запроса"}, status_code=422, headers=_PRIVATE)
            except StarletteHTTPException as exc:
                exc.headers = {**(exc.headers or {}), **_PRIVATE}
                raise
            response.headers.update(_PRIVATE)
            return response

        return respond


class _AssistantStream(StreamingResponse):
    async def stream_response(self, send: Send) -> None:
        try:
            await super().stream_response(send)
        finally:
            # A disconnect can cancel ASGI send while the generator is suspended at yield.
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()


router = APIRouter(prefix="/assistant", route_class=_PrivateChatRoute)


class AssistantConfig(BaseModel):
    enabled: bool
    web_search_available: bool


def _repository(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session),
    account_bound: bool = Depends(has_account_bound_token),
) -> ChatRepository:
    if not account_bound:
        raise HTTPException(401, "Войди заново, чтобы открыть историю диалогов")
    account_key = sha256(f"{user.id}:{user.created_at.isoformat()}".encode()).hexdigest()
    return ChatRepository(session, user.id, account_key)


def _feature_enabled(runtime: AssistantRuntime) -> None:
    if not runtime.settings.assistant_enabled:
        raise HTTPException(503, "Учебный помощник пока недоступен")


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(409, {"code": code, "message": message})


async def _owned_thread(repo: ChatRepository, thread_id: str) -> ChatThread:
    thread = await repo.get_thread(thread_id)
    if thread is None:
        raise HTTPException(404, "Диалог не найден")
    return thread


async def _replayed_turn(repo: ChatRepository, thread: ChatThread, data: SendMessage) -> ThreadOut | None:
    previous = await repo.find_request(thread.id, data.request_id)
    if previous is None:
        return None
    if previous.text != data.text or previous.web_requested != data.use_web:
        raise _conflict("assistant_thread_changed", "Этот идентификатор уже использован для другого сообщения")
    return await repo.detail(thread)


@router.get("/config", response_model=AssistantConfig)
async def config(
    _user: User = Depends(get_current_user), runtime: AssistantRuntime = Depends(get_assistant_runtime),
) -> AssistantConfig:
    enabled = runtime.settings.assistant_enabled
    return AssistantConfig(enabled=enabled, web_search_available=enabled and bool(runtime.settings.brave_search_api_key))


@router.get("/threads", response_model=ThreadList)
async def list_threads(repo: ChatRepository = Depends(_repository)) -> ThreadList:
    return ThreadList(threads=await repo.list_threads())


@router.post("/threads", response_model=ThreadOut, status_code=201)
async def create_thread(
    data: CreateThread, repo: ChatRepository = Depends(_repository),
    runtime: AssistantRuntime = Depends(get_assistant_runtime),
) -> ThreadOut:
    _feature_enabled(runtime)
    if data.course_slug is not None and data.lesson_slug is not None:
        course = await CourseRepository(repo.session).get_by_slug(data.course_slug)
        lesson = await LessonRepository(repo.session).get_by_slugs(data.course_slug, data.lesson_slug)
        if course is None or not course.is_published or lesson is None:
            raise HTTPException(404, "Урок не найден")
    thread = await repo.create_thread(data)
    if thread is None:
        raise _conflict("assistant_thread_limit", "Достигнут лимит диалогов. Удали один из старых диалогов.")
    return await repo.detail(thread)


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def thread_detail(thread_id: UUID, repo: ChatRepository = Depends(_repository)) -> ThreadOut:
    return await repo.detail(await _owned_thread(repo, str(thread_id)))


@router.patch("/threads/{thread_id}", response_model=ThreadOut)
async def rename_thread(
    thread_id: UUID, data: RenameThread, repo: ChatRepository = Depends(_repository),
) -> ThreadOut:
    try:
        renamed = await repo.rename_thread(str(thread_id), data.title)
    except SQLAlchemyError:
        await repo.session.rollback()
        raise HTTPException(503, "Не удалось переименовать диалог. Попробуй ещё раз.") from None
    if renamed is None:
        raise HTTPException(404, "Диалог не найден")
    return renamed


@router.delete("/threads/{thread_id}", status_code=204, response_class=Response)
async def delete_thread(
    thread_id: UUID, repo: ChatRepository = Depends(_repository),
    runtime: AssistantRuntime = Depends(get_assistant_runtime),
) -> Response:
    thread_key = str(thread_id)
    await _owned_thread(repo, thread_key)
    await repo.session.rollback()
    try:
        await runtime.delete_checkpoints(repo.account_key, thread_key)
        if not await repo.delete_thread(thread_key):
            raise HTTPException(404, "Диалог не найден")
    except AssistantUnavailable:
        raise HTTPException(503, "Не удалось удалить диалог. Попробуй ещё раз.") from None
    return Response(status_code=204)


@router.post("/threads/{thread_id}/messages", response_model=ThreadOut)
async def send_message(
    thread_id: UUID, data: SendMessage, repo: ChatRepository = Depends(_repository),
    runtime: AssistantRuntime = Depends(get_assistant_runtime),
) -> ThreadOut:
    return await _run_turn(str(thread_id), data, repo, runtime)


def _stream_session_factory() -> async_sessionmaker[AsyncSession]:
    return SessionLocal


@router.post("/threads/{thread_id}/messages/stream", response_class=StreamingResponse)
async def stream_message(
    thread_id: UUID, data: SendMessage, repo: ChatRepository = Depends(_repository),
    runtime: AssistantRuntime = Depends(get_assistant_runtime),
    sessions: async_sessionmaker[AsyncSession] = Depends(_stream_session_factory),
) -> StreamingResponse:
    thread_key = str(thread_id)
    await _owned_thread(repo, thread_key)
    return _AssistantStream(
        _stream_turn(thread_key, data, repo.owner_id, repo.account_key, runtime, sessions),
        media_type="text/event-stream", headers={"X-Accel-Buffering": "no"},
    )


async def _stream_turn(
    thread_key: str, data: SendMessage, owner_id: int, account_key: str | None, runtime: AssistantRuntime,
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[str]:
    events: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=32)

    async def emit(event: str, payload: dict[str, Any]) -> None:
        await events.put((event, payload))

    async def produce() -> None:
        try:
            # FastAPI closes yield dependencies before streaming on the pinned version.
            async with sessions() as session:
                repo = ChatRepository(session, owner_id, account_key)
                result = await _run_turn(thread_key, data, repo, runtime, emit)
            await emit("done", result.model_dump(mode="json"))
        except HTTPException as exc:
            await emit("error", {"status": exc.status_code, "detail": exc.detail})
        except Exception as exc:
            _logger.error("Assistant stream failed (%s)", type(exc).__name__)
            await emit("error", {"status": 500, "detail": "Поток ответа прервался"})

    task = asyncio.create_task(produce())
    try:
        while True:
            try:
                event, payload = await asyncio.wait_for(events.get(), timeout=10)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
            if event in ("done", "error"):
                break
    finally:
        task.cancel()
        with anyio.CancelScope(shield=True), suppress(asyncio.CancelledError):
            await task


async def _run_turn(
    thread_key: str, data: SendMessage, repo: ChatRepository, runtime: AssistantRuntime,
    emit: _EventSink | None = None,
) -> ThreadOut:
    if runtime.turn_lock.locked():
        thread = await _owned_thread(repo, thread_key)
        if (replayed := await _replayed_turn(repo, thread, data)) is not None:
            return replayed
        if runtime.turn_lock.locked():
            raise _conflict("assistant_busy", "Помощник уже отвечает. Повтори отправку через несколько секунд.")
        await repo.session.rollback()

    async with runtime.turn_lock:
        thread = await _owned_thread(repo, thread_key)
        if (replayed := await _replayed_turn(repo, thread, data)) is not None:
            return replayed
        _feature_enabled(runtime)
        if data.use_web and not runtime.settings.brave_search_api_key:
            raise HTTPException(503, "Поиск в интернете недоступен")
        if thread.revision >= MAX_TURNS:
            raise _conflict("assistant_turn_limit", "Диалог достиг лимита сообщений. Создай новый диалог.")
        wait = runtime.reserve_turn(repo.owner_id)
        if wait is not None:
            raise HTTPException(
                429, {"code": "assistant_rate_limit", "message": "Попробуй через несколько минут"},
                headers={"Retry-After": str(wait)},
            )
        revision, course_slug, lesson_slug = thread.revision, thread.course_slug, thread.lesson_slug
        history = await repo.history(thread_key)
        history.append({"role": "user", "content": data.text})
        await repo.session.rollback()
        try:
            streaming = {"on_event": emit} if emit is not None else {}
            reply, metadata = await runtime.answer(
                history, course_slug=course_slug, lesson_slug=lesson_slug,
                owner_id=repo.owner_id, session=repo.session, use_web=data.use_web, **streaming,
                account_key=repo.account_key, thread_id=thread_key,
            )
            if emit is not None:
                await emit("status", {"phase": "saving"})
            updated = await repo.append_turn(thread_key, revision, data, reply, metadata)
        except AssistantUnavailable:
            raise HTTPException(503, "Помощник не смог ответить. Попробуй отправить ещё раз.") from None
        except SQLAlchemyError:
            await repo.session.rollback()
            raise HTTPException(503, "Не удалось сохранить ответ. Попробуй отправить ещё раз.") from None

    if updated is None:
        current = await _owned_thread(repo, thread_key)
        if (replayed := await _replayed_turn(repo, current, data)) is not None:
            return replayed
        raise _conflict("assistant_thread_changed", "Диалог изменился. Открой его заново и повтори отправку.")
    return await repo.detail(updated)
