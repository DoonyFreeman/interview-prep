"""Owner-scoped chat history and atomic persistence of complete turns."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import (
    ForeignKey, Index, String, Text, UniqueConstraint, case, delete, func, insert, literal, select, update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.assistant.response import ReplyMetadata
from app.database import Base
from app.models import _utcnow

MAX_THREADS = 50
MAX_TURNS = 100
_HISTORY_MESSAGES = 12
_HISTORY_CHARACTERS = 12_000
_PREVIEW_CHARACTERS = 120
_DEFAULT_TITLE = "Новый диалог"
# Leading whitespace distinguishes an explicit rename to the default title.
# User-entered and generated titles are trimmed before storage.
_RENAMED_DEFAULT_TITLE = f" {_DEFAULT_TITLE}"


class ChatThread(Base):
    __tablename__ = "assistant_threads"
    __table_args__ = (Index("ix_assistant_threads_owner_updated", "owner_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(100), default=_DEFAULT_TITLE)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow)
    course_slug: Mapped[str | None] = mapped_column(String(64))
    lesson_slug: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(default=0)


class ChatMessage(Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "position"),
        UniqueConstraint("thread_id", "request_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(ForeignKey("assistant_threads.id", ondelete="CASCADE"))
    position: Mapped[int]
    role: Mapped[str] = mapped_column(String(9))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime]
    request_id: Mapped[str | None] = mapped_column(String(36))
    web_requested: Mapped[bool] = mapped_column(default=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class AssistantPreference(Base):
    __tablename__ = "assistant_preferences"

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    account_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class MessageOut(ReplyMetadata):
    id: str
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class ThreadSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime
    preview: str | None


class ThreadOut(ThreadSummary):
    course_slug: str | None
    lesson_slug: str | None
    messages: list[MessageOut]


class ThreadList(BaseModel):
    threads: list[ThreadSummary]


Slug = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")]


class CreateThread(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_slug: Slug | None = None
    lesson_slug: Slug | None = None

    @model_validator(mode="after")
    def validate_lesson_context(self) -> CreateThread:
        if (self.course_slug is None) != (self.lesson_slug is None):
            raise ValueError("Для контекста нужны курс и урок")
        return self


class RenameThread(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SendMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]
    use_web: bool = False
    request_id: UUID = Field(default_factory=uuid4)


def summary(thread: ChatThread, latest_user_text: str | None) -> ThreadSummary:
    preview = " ".join((latest_user_text or "").split())[:_PREVIEW_CHARACTERS].rstrip()
    title = _DEFAULT_TITLE if thread.title == _RENAMED_DEFAULT_TITLE else thread.title
    return ThreadSummary(
        id=thread.id, title=title, updated_at=thread.updated_at.replace(tzinfo=timezone.utc),
        preview=preview or None,
    )


class ChatRepository:
    def __init__(self, session: AsyncSession, owner_id: int, account_key: str | None = None) -> None:
        self.session = session
        self.owner_id = owner_id
        self.account_key = account_key

    def _owned(self, thread_id: str):
        return (ChatThread.id == thread_id, ChatThread.owner_id == self.owner_id)

    async def list_threads(self) -> list[ThreadSummary]:
        latest_user_text = (
            select(ChatMessage.text)
            .where(ChatMessage.thread_id == ChatThread.id, ChatMessage.role == "user")
            .order_by(ChatMessage.position.desc()).limit(1).scalar_subquery()
        )
        result = await self.session.execute(
            select(ChatThread, latest_user_text).where(ChatThread.owner_id == self.owner_id)
            .order_by(ChatThread.updated_at.desc(), ChatThread.id).limit(MAX_THREADS)
        )
        return [summary(thread, text) for thread, text in result]

    async def create_thread(self, data: CreateThread) -> ChatThread | None:
        # A single INSERT-SELECT checks the limit under SQLite's writer lock.
        thread_id = str(uuid4())
        owned_count = (
            select(func.count()).select_from(ChatThread)
            .where(ChatThread.owner_id == self.owner_id).scalar_subquery()
        )
        values = select(
            literal(thread_id), literal(self.owner_id), literal(_DEFAULT_TITLE),
            literal(_utcnow()), literal(data.course_slug), literal(data.lesson_slug), literal(0),
        ).where(owned_count < MAX_THREADS)
        created = await self.session.scalar(
            insert(ChatThread).from_select(
                ["id", "owner_id", "title", "updated_at", "course_slug", "lesson_slug", "revision"],
                values,
            ).returning(ChatThread)
        )
        await self.session.commit()
        return created

    async def get_thread(self, thread_id: str) -> ChatThread | None:
        return await self.session.scalar(
            select(ChatThread).where(*self._owned(thread_id)).execution_options(populate_existing=True)
        )

    async def rename_thread(self, thread_id: str, title: str) -> ThreadOut | None:
        stored_title = _RENAMED_DEFAULT_TITLE if title == _DEFAULT_TITLE else title
        thread = await self.session.scalar(
            update(ChatThread).where(*self._owned(thread_id)).values(title=stored_title)
            .returning(ChatThread).execution_options(populate_existing=True)
        )
        result = await self.detail(thread) if thread is not None else None
        await self.session.commit()
        return result

    async def delete_thread(self, thread_id: str) -> bool:
        # Keep the explicit delete so cleanup also works on test connections
        # that do not install the production SQLite foreign-key pragma.
        removed = await self.session.scalar(
            delete(ChatThread).where(*self._owned(thread_id)).returning(ChatThread.id)
        )
        if removed is not None:
            await self.session.execute(delete(ChatMessage).where(ChatMessage.thread_id == removed))
        await self.session.commit()
        return removed is not None

    async def _messages(self, thread_id: str, *, recent: bool = False) -> list[ChatMessage]:
        statement = (
            select(ChatMessage).join(ChatThread, ChatThread.id == ChatMessage.thread_id)
            .where(*self._owned(thread_id))
        )
        if recent:
            result = await self.session.scalars(
                statement.order_by(ChatMessage.position.desc()).limit(_HISTORY_MESSAGES)
            )
            return list(reversed(result.all()))
        result = await self.session.scalars(statement.order_by(ChatMessage.position))
        return list(result)

    async def detail(self, thread: ChatThread) -> ThreadOut:
        rows = await self._messages(thread.id)
        latest_user_text = next((row.text for row in reversed(rows) if row.role == "user"), None)
        messages = [
            MessageOut(
                id=row.id, role=row.role, text=row.text,
                created_at=row.created_at.replace(tzinfo=timezone.utc),
                **ReplyMetadata.model_validate_json(row.metadata_json).model_dump(),
            )
            for row in rows
        ]
        return ThreadOut(
            **summary(thread, latest_user_text).model_dump(), course_slug=thread.course_slug,
            lesson_slug=thread.lesson_slug, messages=messages,
        )

    async def find_request(self, thread_id: str, request_id: UUID) -> ChatMessage | None:
        return await self.session.scalar(
            select(ChatMessage).join(ChatThread, ChatThread.id == ChatMessage.thread_id)
            .where(*self._owned(thread_id), ChatMessage.request_id == str(request_id))
        )

    async def history(self, thread_id: str) -> list[dict[str, str]]:
        rows = await self._messages(thread_id, recent=True)
        history: list[dict[str, str]] = []
        remaining = _HISTORY_CHARACTERS
        # Only include complete pairs, so the model never gets an orphan reply.
        for index in range(len(rows) - 2, -1, -2):
            turn = rows[index:index + 2]
            if sum(len(row.text) for row in turn) > remaining:
                break
            for row in reversed(turn):
                history.append({"role": row.role, "content": row.text})
                remaining -= len(row.text)
        return list(reversed(history))

    async def append_turn(
        self, thread_id: str, revision: int, request: SendMessage, reply: str, metadata: ReplyMetadata,
    ) -> ChatThread | None:
        now = _utcnow()
        changes: dict = {"revision": revision + 1, "updated_at": now}
        if revision == 0:
            generated_title = " ".join(request.text.split())[:90]
            changes["title"] = case(
                (ChatThread.title == _DEFAULT_TITLE, generated_title), else_=ChatThread.title,
            )
        thread = await self.session.scalar(
            update(ChatThread).where(*self._owned(thread_id), ChatThread.revision == revision)
            .values(**changes).returning(ChatThread).execution_options(populate_existing=True)
        )
        if thread is None:
            await self.session.rollback()
            return None
        self.session.add_all([
            ChatMessage(
                thread_id=thread_id, role="user", text=request.text, position=2 * revision,
                created_at=now, request_id=str(request.request_id), web_requested=request.use_web,
            ),
            ChatMessage(
                thread_id=thread_id, role="assistant", text=reply, position=2 * revision + 1,
                created_at=now, metadata_json=metadata.model_dump_json(),
            ),
        ])
        await self.session.commit()
        return thread
