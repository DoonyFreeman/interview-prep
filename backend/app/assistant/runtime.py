"""Wire the graph to bounded lesson, progress and optional web tools."""
from __future__ import annotations

import asyncio
from functools import cached_property, lru_cache
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
from time import monotonic
from typing import Annotated, Any, Literal
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.response import ChatSource, ReplyMetadata
from app.assistant.streaming import AssistantEvent
from app.config import Settings, get_settings

_WEB_URL = "https://api.search.brave.com/res/v1/llm/context"
_TURN_WINDOW = 300
_TURNS_PER_WINDOW = 10
_REMEMBER = re.compile(r"^(?:запомни|remember)(?:\s*[:,]\s*|\s+)(.+)$", re.IGNORECASE | re.DOTALL)
_SHOW_MEMORY = {"что ты обо мне помнишь", "what do you remember about me"}
_FORGET_MEMORY = {"забудь всё обо мне", "забудь все обо мне", "forget everything about me"}
_MAX_PREFERENCE_LENGTH = 350
_REVIEW_REQUEST = re.compile(
    r"^(?:(?:подскажи|скажи)[,:]?\s+)?(?:что|какие темы)\s+(?:мне\s+)?(?:стоит\s+)?повторить\b"
    r"|^(?:покажи|открой)\s+(?:мне\s+)?(?:мою\s+)?очередь повторения\b"
    r"|^(?:посоветуй|подбери|составь)\b.{0,100}\b(?:для повторения|план повторения)\b"
    r"|^(?:what (?:should|do) i (?:need to )?(?:review|revise)|which topics should i (?:review|revise))\b"
    r"|^(?:show|open) (?:me )?my review queue\b",
    re.IGNORECASE,
)


class AssistantUnavailable(Exception):
    """The assistant could not complete the turn."""


class LessonSearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=350)]
    scope: Literal["current_lesson", "all_lessons"] = "current_lesson"


class ReadSectionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _lesson_url(course: str, lesson: str, anchor: str = "") -> str:
    url = f"/courses/{quote(course, safe='')}/lessons/{quote(lesson, safe='')}"
    return f"{url}#{quote(anchor, safe='')}" if anchor else url


def _safe_web_url(url: str) -> bool:
    if len(url) > 2000 or "\\" in url or any(ord(ch) < 33 for ch in url):
        return False
    try:
        parts = urlsplit(url)
        return parts.scheme == "https" and bool(parts.hostname) and parts.username is None
    except ValueError:
        return False


class AssistantRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Personal API concurrency and VPS inference are both kept to one turn.
        self.turn_lock = asyncio.Lock()
        self._turn_starts: dict[int, list[float]] = {}

    def reserve_turn(self, owner_id: int) -> int | None:
        """Count real attempts only. Return seconds until the next slot if full."""
        now = monotonic()
        cutoff = now - _TURN_WINDOW
        for account, starts in list(self._turn_starts.items()):
            if starts[-1] <= cutoff:
                del self._turn_starts[account]
        starts = [started for started in self._turn_starts.get(owner_id, ()) if started > cutoff]
        if len(starts) >= _TURNS_PER_WINDOW:
            return int(starts[0] - cutoff) + 1
        self._turn_starts[owner_id] = [*starts, now]
        return None

    @cached_property
    def retriever(self):
        from app.assistant.retrieval import LessonRetriever

        return LessonRetriever(
            Path(self.settings.assistant_index_path), Path(self.settings.assistant_model_dir),
            content_dir=Path(self.settings.content_dir),
        )

    @cached_property
    def model(self):
        from app.assistant.provider import GigaChatModel

        return GigaChatModel(
            credentials=self.settings.gigachat_credentials,
            scope=self.settings.gigachat_scope, model=self.settings.gigachat_model,
            ca_file=self.settings.gigachat_ca_file or None,
        )

    @property
    def persistence_path(self) -> Path:
        path = self.settings.assistant_persistence_path
        return Path(path) if path else Path(self.settings.assistant_index_path).with_name("langgraph.sqlite3")

    @cached_property
    def checkpointer(self):
        from app.assistant.persistence import SQLiteCheckpointSaver

        return SQLiteCheckpointSaver(self.persistence_path)

    @cached_property
    def store(self):
        from app.assistant.memory import AssistantStore

        return AssistantStore()

    @cached_property
    def graph(self):
        from app.assistant.graph import compile_assistant_graph

        return compile_assistant_graph(checkpointer=self.checkpointer, store=self.store)

    async def delete_checkpoints(self, account_key: str | None, thread_id: str) -> None:
        if account_key:
            try:
                await self.checkpointer.adelete_thread(f"{account_key}/{thread_id}")
            except (ImportError, OSError, sqlite3.Error) as exc:
                raise AssistantUnavailable from exc

    async def _memory(
        self, session: AsyncSession, owner_id: int, account_key: str, question: str,
    ) -> tuple[str, str | None]:
        from app.assistant.memory import AssistantStore

        store = AssistantStore(session)
        namespace = ("assistant", str(owner_id), account_key)
        normalized = question.strip().rstrip(".?!").casefold()
        if normalized in _FORGET_MEMORY:
            await store.adelete(namespace, "preference")
            return "", "Сохранённая заметка удалена."
        if match := _REMEMBER.fullmatch(question.strip()):
            preference = match[1].strip()
            if not preference or len(preference) > _MAX_PREFERENCE_LENGTH:
                return "", f"Напиши, что сохранить, в пределах {_MAX_PREFERENCE_LENGTH} символов."
            await store.aput(namespace, "preference", {"text": preference})
            return "", "Заметка сохранена. Она будет доступна в новых диалогах."
        item = await store.aget(namespace, "preference")
        preference = item.value["text"] if item is not None else ""
        await session.rollback()
        if normalized in _SHOW_MEMORY:
            return "", f"Сохранённая заметка\n\n{preference}" if preference else "Сохранённых заметок пока нет."
        return preference, None

    async def answer(
        self, messages: list[dict[str, str]], *, course_slug: str | None,
        lesson_slug: str | None, owner_id: int, session: AsyncSession | None, use_web: bool,
        on_event: AssistantEvent | None = None,
        account_key: str | None = None, thread_id: str | None = None,
    ) -> tuple[str, ReplyMetadata]:
        try:
            from app.assistant.graph import AssistantTool, ToolResult, run_assistant
            from app.assistant.provider import AssistantModelError
            from app.assistant.retrieval import RetrievalUnavailable
        except ImportError as exc:
            raise AssistantUnavailable from exc

        sources: dict[str, ChatSource] = {}
        aliases: dict[str, str] = {}
        lesson_chunks: dict[str, str] = {}
        search_error = False
        web_error = False

        def cite(key: str, source: ChatSource) -> str:
            source_id = aliases.get(key)
            if source_id is None:
                source_id = f"S{len(aliases) + 1}"
                aliases[key] = source_id
            sources[source_id] = source
            return source_id

        def lesson_hit(hit) -> dict[str, str]:
            source_id = cite(hit.chunk_id, ChatSource(
                title=hit.title, url=_lesson_url(hit.course_slug, hit.lesson_slug, hit.anchor), kind="lesson",
            ))
            lesson_chunks[source_id] = hit.chunk_id
            return {"source_id": source_id, "title": hit.title, "text": hit.text}

        async def search_lessons(args: dict[str, Any]) -> ToolResult:
            nonlocal search_error
            scoped = args["scope"] == "current_lesson" and lesson_slug is not None
            try:
                hits = await asyncio.to_thread(
                    self.retriever.search, args["query"], limit=5,
                    course_slug=course_slug if scoped else None, lesson_slug=lesson_slug if scoped else None,
                )
            except (RetrievalUnavailable, ImportError, OSError):
                search_error = True
                return ToolResult({"error": "Поиск по урокам временно недоступен"})
            sections = [lesson_hit(hit) for hit in hits]
            return ToolResult(
                {"sections": sections}, tuple(section["source_id"] for section in sections),
            )

        async def read_lesson_section(args: dict[str, Any]) -> ToolResult:
            source_id = args["chunk_id"]
            if source_id not in lesson_chunks:
                return ToolResult({"error": "Сначала найди этот раздел через поиск по урокам"})
            hit = await asyncio.to_thread(self.retriever.read_section, lesson_chunks[source_id])
            if hit is None:
                return ToolResult({"error": "Раздел недоступен"})
            return ToolResult({"section": lesson_hit(hit)}, (source_id,))

        async def get_review_queue(_: dict[str, Any]) -> ToolResult:
            from app.services import progress

            if session is None:
                raise RuntimeError("The review tool requires a database session")
            queue = await progress.get_review_queue(session, user_id=owner_id, limit=8)
            items = []
            for item in queue.items:
                sid = cite(f"review:{item.course_slug}:{item.lesson_slug}:{item.concept_slug}", ChatSource(
                    title=item.concept_title, url=_lesson_url(item.course_slug, item.lesson_slug, item.anchor),
                    kind="lesson",
                ))
                items.append({"source_id": sid, "topic": item.concept_title})
            # The read transaction must not span the next provider call.
            await session.rollback()
            if not items:
                sid = cite("review:queue", ChatSource(title="Очередь повторения", url="/review", kind="lesson"))
                return ToolResult({"due_for_review": [], "source_id": sid}, (sid,))
            return ToolResult({"due_for_review": items}, tuple(item["source_id"] for item in items))

        async def web_search(_: dict[str, Any]) -> ToolResult:
            # Consent applies to the current message only. Even a hostile tool
            # call cannot insert another turn or progress data in this request.
            nonlocal web_error
            results = await _web_passages(self.settings.brave_search_api_key, messages[-1]["content"])
            if results is None:
                web_error = True
                return ToolResult({"error": "Веб-поиск временно недоступен"})
            evidence = []
            for title, url, passage in results:
                sid = cite("web:" + sha256(url.encode()).hexdigest()[:24],
                           ChatSource(title=title, url=url, kind="web"))
                evidence.append({"source_id": sid, "title": title, "text": passage})
            return ToolResult({"passages": evidence}, tuple(item["source_id"] for item in evidence))

        scope_note = (
            f" Текущий урок чата: {course_slug}/{lesson_slug}."
            " Для сравнения с другими уроками используй scope=all_lessons."
            if lesson_slug else ""
        )
        tools = [
            AssistantTool("search_lessons", "Гибридный поиск по разделам уроков." + scope_note,
                          LessonSearchArgs, search_lessons),
            AssistantTool("read_lesson_section", "Прочитай раздел. Передай его source_id из поиска в chunk_id.",
                          ReadSectionArgs, read_lesson_section),
        ]
        if session is not None and _REVIEW_REQUEST.search(messages[-1]["content"]):
            tools.append(AssistantTool("get_review_queue", "Темы текущего пользователя, которым пора на повторение.",
                                       NoArgs, get_review_queue))
        if use_web and self.settings.brave_search_api_key:
            tools.append(AssistantTool(
                "web_search", "Найди свежие источники в интернете по текущему сообщению пользователя.",
                NoArgs, web_search,
            ))
        try:
            run_config = {}
            if session is not None and account_key and thread_id:
                preference, memory_reply = await self._memory(session, owner_id, account_key, messages[-1]["content"])
                if memory_reply is not None:
                    return memory_reply, ReplyMetadata()
                run_config = {
                    "graph": self.graph, "thread_id": f"{account_key}/{thread_id}", "memory_context": preference,
                }
            if not self.settings.gigachat_credentials:
                raise AssistantUnavailable
            reply = await run_assistant(
                self.model, messages, tools,
                lesson_context=f"{course_slug}/{lesson_slug}" if lesson_slug else None,
                on_event=on_event,
                fallback_lesson_search=True,
                **run_config,
            )
        except (AssistantModelError, TimeoutError, OSError, ImportError, sqlite3.Error) as exc:
            raise AssistantUnavailable from exc
        if (search_error or web_error) and not reply.source_ids:
            raise AssistantUnavailable
        citations: list[ChatSource] = []
        seen_urls: set[str] = set()
        for source_id in reply.source_ids:
            source = sources[source_id]
            if source.url not in seen_urls:
                citations.append(source)
                seen_urls.add(source.url)
        return reply.text, ReplyMetadata(sources=citations, tool_activity=list(reply.tools_used))


async def _web_passages(
    api_key: str, approved_message: str, *, transport: httpx.AsyncBaseTransport | None = None,
) -> list[tuple[str, str, str]] | None:
    query = " ".join(approved_message.split()[:75])[:600]
    try:
        async with httpx.AsyncClient(timeout=8, transport=transport) as client:
            response = await client.post(
                _WEB_URL, headers={"X-Subscription-Token": api_key},
                json={"q": query, "maximum_number_of_urls": 4,
                      "maximum_number_of_tokens": 2048, "safesearch": "moderate"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    grounding = data.get("grounding") if isinstance(data, dict) else None
    rows = grounding.get("generic") if isinstance(grounding, dict) else None
    if not isinstance(rows, list):
        return None
    passages = []
    for row in rows[:4]:
        if not isinstance(row, dict):
            continue
        url, title, snippets = row.get("url"), row.get("title"), row.get("snippets")
        if not isinstance(url, str) or not _safe_web_url(url) or not isinstance(snippets, list):
            continue
        text = "\n".join(part[:1500] for part in snippets[:3] if isinstance(part, str)).strip()[:2400]
        if text:
            passages.append((title.strip()[:200] if isinstance(title, str) and title.strip() else url, url, text))
    return passages


@lru_cache
def _shared_runtime() -> AssistantRuntime:
    return AssistantRuntime(get_settings())


async def get_assistant_runtime() -> AssistantRuntime:
    return _shared_runtime()
