"""Durable LangGraph checkpoints for the study assistant."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from time import time
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver, ChannelVersions, Checkpoint, CheckpointMetadata, CheckpointTuple,
    WRITES_IDX_MAP, get_checkpoint_id, get_serializable_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.serde.types import ERROR

_CHECKPOINT_MAX_AGE = 7 * 24 * 60 * 60
_CHECKPOINTS_PER_NAMESPACE = 32

_CHECKPOINT_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL, namespace TEXT NOT NULL, checkpoint_id TEXT NOT NULL,
    parent_id TEXT, saved_at REAL NOT NULL,
    checkpoint_type TEXT NOT NULL, checkpoint BLOB NOT NULL,
    metadata_type TEXT NOT NULL, metadata BLOB NOT NULL,
    PRIMARY KEY (thread_id, namespace, checkpoint_id)
);
CREATE INDEX IF NOT EXISTS checkpoints_saved_at ON checkpoints (saved_at);
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL, namespace TEXT NOT NULL, checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL, idx INTEGER NOT NULL, task_path TEXT NOT NULL, channel TEXT NOT NULL,
    value_type TEXT NOT NULL, value BLOB NOT NULL, saved_at REAL NOT NULL,
    PRIMARY KEY (thread_id, namespace, checkpoint_id, task_id, idx)
);
CREATE INDEX IF NOT EXISTS checkpoint_writes_saved_at ON checkpoint_writes (saved_at);
CREATE TABLE IF NOT EXISTS checkpoint_thread_deletions (
    thread_id TEXT PRIMARY KEY, deleted_at REAL NOT NULL
);
"""

@contextmanager
def _connect(path: Path, *, write: bool = False) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)

    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA secure_delete = ON")
        db.executescript(_CHECKPOINT_SCHEMA)
        with db:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
    finally:
        db.close()


def _scope(config: RunnableConfig) -> tuple[str, str]:
    values = config["configurable"]
    return values["thread_id"], values.get("checkpoint_ns", "")


def _config(thread_id: str, namespace: str, checkpoint_id: str) -> RunnableConfig:
    return {
        "configurable": {"thread_id": thread_id, "checkpoint_ns": namespace, "checkpoint_id": checkpoint_id},
    }


def _thread_deleted(db: sqlite3.Connection, thread_id: str) -> bool:
    return db.execute(
        "SELECT 1 FROM checkpoint_thread_deletions WHERE thread_id = ?", (thread_id,),
    ).fetchone() is not None


class SQLiteCheckpointSaver(BaseCheckpointSaver[int]):
    """Save full snapshots for the assistant's non-delta channels and pending writes."""

    def __init__(self, path: str | Path) -> None:
        super().__init__(serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        self.path = Path(path)

    def _tuple(self, db: sqlite3.Connection, row: sqlite3.Row, cutoff: float) -> CheckpointTuple:
        thread, namespace, checkpoint_id = row["thread_id"], row["namespace"], row["checkpoint_id"]
        pending = db.execute(
            """SELECT task_id, channel, value_type, value FROM checkpoint_writes
            WHERE thread_id = ? AND namespace = ? AND checkpoint_id = ?
            ORDER BY task_path, task_id, idx""",
            (thread, namespace, checkpoint_id),
        )
        parent = row["parent_id"]
        parent_exists = parent and db.execute(
            """SELECT 1 FROM checkpoints
            WHERE thread_id = ? AND namespace = ? AND checkpoint_id = ? AND saved_at > ?""",
            (thread, namespace, parent, cutoff),
        ).fetchone()
        return CheckpointTuple(
            config=_config(thread, namespace, checkpoint_id),
            checkpoint=self.serde.loads_typed((row["checkpoint_type"], row["checkpoint"])),
            metadata=self.serde.loads_typed((row["metadata_type"], row["metadata"])),
            parent_config=_config(thread, namespace, parent) if parent_exists else None,
            pending_writes=[
                (task, channel, self.serde.loads_typed((kind, value)))
                for task, channel, kind, value in pending
            ],
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread, namespace = _scope(config)
        checkpoint_id = get_checkpoint_id(config)
        cutoff = time() - _CHECKPOINT_MAX_AGE
        query = "SELECT * FROM checkpoints WHERE thread_id = ? AND namespace = ? AND saved_at > ?"
        args = (thread, namespace, cutoff)
        if checkpoint_id is not None:
            query += " AND checkpoint_id = ?"
            args += (checkpoint_id,)
        with _connect(self.path) as db:
            row = db.execute(query + " ORDER BY checkpoint_id DESC LIMIT 1", args).fetchone()
            return self._tuple(db, row, cutoff) if row else None

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return await asyncio.to_thread(self.get_tuple, config)

    def list(
        self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None, limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        cutoff = time() - _CHECKPOINT_MAX_AGE
        query = "SELECT * FROM checkpoints WHERE saved_at > ?"
        args: list[Any] = [cutoff]
        if config is not None:
            values = config["configurable"]
            query += " AND thread_id = ?"
            args.append(values["thread_id"])
            if (namespace := values.get("checkpoint_ns")) is not None:
                query += " AND namespace = ?"
                args.append(namespace)
            if (checkpoint_id := get_checkpoint_id(config)) is not None:
                query += " AND checkpoint_id = ?"
                args.append(checkpoint_id)
        if before is not None and (checkpoint_id := get_checkpoint_id(before)) is not None:
            query += " AND checkpoint_id < ?"
            args.append(checkpoint_id)
        with _connect(self.path) as db:
            for row in db.execute(query + " ORDER BY checkpoint_id DESC", args):
                if limit is not None and limit <= 0:
                    break
                item = self._tuple(db, row, cutoff)
                if filter and not all(item.metadata.get(key) == value for key, value in filter.items()):
                    continue
                yield item
                if limit is not None:
                    limit -= 1

    async def alist(
        self, config: RunnableConfig | None, *, filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None, limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        items = await asyncio.to_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for item in items:
            yield item

    def put(
        self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread, namespace = _scope(config)
        checkpoint_id = checkpoint["id"]
        saved_config = _config(thread, namespace, checkpoint_id)
        now = time()
        serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        serialized_metadata = self.serde.dumps_typed(get_serializable_checkpoint_metadata(config, metadata))
        with _connect(self.path, write=True) as db:
            if _thread_deleted(db, thread):
                return saved_config
            db.execute(
                """INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (thread_id, namespace, checkpoint_id) DO NOTHING""",
                (thread, namespace, checkpoint_id, get_checkpoint_id(config), now,
                 *serialized_checkpoint, *serialized_metadata),
            )
            cutoff = now - _CHECKPOINT_MAX_AGE
            db.execute("DELETE FROM checkpoint_writes WHERE saved_at <= ?", (cutoff,))
            db.execute("DELETE FROM checkpoints WHERE saved_at <= ?", (cutoff,))
            db.execute("DELETE FROM checkpoint_thread_deletions WHERE deleted_at <= ?", (cutoff,))
            # Cap each thread namespace while allowing writes to arrive before their checkpoint.
            rows = db.execute(
                """SELECT checkpoint_id FROM checkpoints WHERE thread_id = ? AND namespace = ?
                ORDER BY checkpoint_id DESC LIMIT -1 OFFSET ?""",
                (thread, namespace, _CHECKPOINTS_PER_NAMESPACE),
            ).fetchall()
            for row in rows:
                key = (thread, namespace, row["checkpoint_id"])
                db.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = ? AND namespace = ? AND checkpoint_id = ?", key,
                )
                db.execute("DELETE FROM checkpoints WHERE thread_id = ? AND namespace = ? AND checkpoint_id = ?", key)
        return saved_config

    async def aput(
        self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    def put_writes(
        self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "",
    ) -> None:
        if not writes:
            return
        thread, namespace = _scope(config)
        checkpoint_id = config["configurable"]["checkpoint_id"]
        now = time()
        # LangGraph needs to know the step failed. Exception messages may contain private diagnostics.
        values = [
            (thread, namespace, checkpoint_id, task_id, WRITES_IDX_MAP.get(channel, idx), task_path,
             channel, *self.serde.dumps_typed("Assistant graph step failed" if channel == ERROR else value), now)
            for idx, (channel, value) in enumerate(writes)
        ]
        with _connect(self.path, write=True) as db:
            if _thread_deleted(db, thread):
                return
            db.executemany(
                """INSERT INTO checkpoint_writes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (thread_id, namespace, checkpoint_id, task_id, idx) DO UPDATE SET
                    task_path=excluded.task_path, channel=excluded.channel,
                    value_type=excluded.value_type, value=excluded.value, saved_at=excluded.saved_at
                WHERE excluded.idx < 0""",
                values,
            )

    async def aput_writes(
        self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "",
    ) -> None:
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    def delete_thread(self, thread_id: str) -> None:
        with _connect(self.path, write=True) as db:
            now = time()
            db.execute("DELETE FROM checkpoint_thread_deletions WHERE deleted_at <= ?", (now - _CHECKPOINT_MAX_AGE,))
            # Graph steps already in flight may attempt writes after the chat is deleted.
            db.execute(
                """INSERT INTO checkpoint_thread_deletions VALUES (?, ?)
                ON CONFLICT (thread_id) DO UPDATE SET deleted_at=excluded.deleted_at""",
                (thread_id, now),
            )
            db.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))
            db.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.to_thread(self.delete_thread, thread_id)
