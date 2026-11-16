from contextlib import closing
from pathlib import Path
import sqlite3
from typing import TypedDict

from langgraph.checkpoint.serde.types import ERROR
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.base import GetOp, PutOp, SearchOp
import pytest
import pytest_asyncio

from app.assistant import memory, persistence
from app.assistant.memory import AssistantStore
from app.assistant.persistence import SQLiteCheckpointSaver
from app.models import User

_ACCOUNT = ("assistant", "1", "owner-1")


@pytest_asyncio.fixture
async def preference_database(Session, monkeypatch):
    monkeypatch.setattr(memory, "SessionLocal", Session)
    async with Session.begin() as session:
        session.add(User(id=1, email="assistant-owner@example.com", password_hash="test"))
    return Session


class _State(TypedDict):
    question: str
    answer: str


def _graph(path: Path, *, interrupt_before=None):
    async def answer(state: _State, runtime: Runtime):
        preference = await runtime.store.aget(_ACCOUNT, "style")
        style = preference.value["format"] if preference else "default"
        return {"answer": f"{style}: {state['question']}"}

    graph = StateGraph(_State)
    graph.add_node("answer", answer)
    graph.add_edge(START, "answer")
    graph.add_edge("answer", END)
    return graph.compile(
        checkpointer=SQLiteCheckpointSaver(path), store=AssistantStore(),
        interrupt_before=interrupt_before,
    )


@pytest.mark.asyncio
async def test_langgraph_checkpoints_resume_with_preferences_after_reopening(tmp_path, preference_database):
    path = tmp_path / "assistant" / "langgraph.sqlite3"
    thread_id = "owner-1:thread-1"
    config = {"configurable": {"thread_id": thread_id}}
    store = AssistantStore()
    graph = _graph(path, interrupt_before=["answer"])
    assert not path.exists()
    await store.aput(_ACCOUNT, "style", {"format": "short"})
    await graph.ainvoke({"question": "AsyncIO?"}, config, durability="sync")
    before = await graph.aget_state(config)
    assert before.next == ("answer",)

    reopened = _graph(path)
    result = await reopened.ainvoke(None, config, durability="sync")
    assert result == {"question": "AsyncIO?", "answer": "short: AsyncIO?"}
    history = [checkpoint async for checkpoint in reopened.aget_state_history(config)]
    assert len(history) >= 2
    assert history[0].values == result
    assert history[0].parent_config

    other = {"configurable": {"thread_id": "owner-2:thread-1"}}
    saver = SQLiteCheckpointSaver(path)
    assert await saver.aget_tuple(other) is None
    assert await AssistantStore().aget(("assistant", "2", "owner-2"), "style") is None
    await saver.adelete_thread(thread_id)
    assert await SQLiteCheckpointSaver(path).aget_tuple(config) is None
    assert (await AssistantStore().aget(_ACCOUNT, "style")).value == {"format": "short"}


@pytest.mark.asyncio
async def test_checkpoint_snapshots_and_writes_are_idempotent(tmp_path):
    path = tmp_path / "langgraph.sqlite3"
    saver = SQLiteCheckpointSaver(path)
    config = {"configurable": {"thread_id": "owner:thread", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 4, "id": "checkpoint", "ts": "2026-11-15T00:00:00+00:00",
        "channel_values": {"answer": "saved"}, "channel_versions": {"answer": 1},
        "versions_seen": {}, "updated_channels": ["answer"],
    }
    stored = await saver.aput(config, checkpoint, {"source": "loop", "step": 1}, {"answer": 1})
    await saver.aput(config, {**checkpoint, "channel_values": {}}, {"step": 2}, {})
    await saver.aput_writes(stored, [("answer", "original")], "task-z", "one")
    await saver.aput_writes(stored, [("answer", "duplicate")], "task-z", "one")
    await saver.aput_writes(stored, [("answer", "first")], "task-a", "one")
    await saver.aput_writes(stored, [(ERROR, RuntimeError("private provider diagnostic"))], "task-error", "two")
    reopened = await SQLiteCheckpointSaver(path).aget_tuple(stored)
    assert reopened.checkpoint == checkpoint
    assert reopened.metadata["step"] == 1
    assert reopened.pending_writes == [
        ("task-a", "answer", "first"), ("task-z", "answer", "original"),
        ("task-error", ERROR, "Assistant graph step failed"),
    ]

    await saver.adelete_thread("owner:thread")
    await SQLiteCheckpointSaver(path).aput_writes(stored, [("answer", "late")], "task-late")
    await SQLiteCheckpointSaver(path).aput(config, checkpoint, {"step": 3}, {"answer": 1})
    assert await saver.aget_tuple(config) is None
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM checkpoint_writes").fetchone() == (0,)


@pytest.mark.asyncio
async def test_deleting_before_first_checkpoint_also_suppresses_late_writes(tmp_path, preference_database):
    path = tmp_path / "langgraph.sqlite3"
    config = {"configurable": {"thread_id": "owner:thread"}}
    saver = SQLiteCheckpointSaver(path)
    assert not path.exists()
    await saver.adelete_thread("owner:thread")
    await _graph(path).ainvoke({"question": "Already deleted"}, config, durability="sync")
    assert await saver.aget_tuple(config) is None
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM checkpoint_writes").fetchone() == (0,)


@pytest.mark.asyncio
async def test_checkpoint_history_is_bounded_and_expires(tmp_path, monkeypatch, preference_database):
    path = tmp_path / "langgraph.sqlite3"
    now = 100.0
    monkeypatch.setattr(persistence, "time", lambda: now)
    monkeypatch.setattr(persistence, "_CHECKPOINTS_PER_NAMESPACE", 2)
    graph = _graph(path)
    await AssistantStore().aput(_ACCOUNT, "style", {"format": "short"})
    config = {"configurable": {"thread_id": "owner:thread"}}
    for question in ("async", "threads"):
        await graph.ainvoke({"question": question}, config, durability="sync")
    saver = SQLiteCheckpointSaver(path)
    items = [item async for item in saver.alist(config)]
    assert len(items) == 2
    assert items[0].checkpoint["channel_values"] == {"question": "threads", "answer": "short: threads"}
    assert items[1].parent_config is None

    now += persistence._CHECKPOINT_MAX_AGE + 1
    assert await saver.aget_tuple(config) is None
    assert [item async for item in saver.alist(config)] == []
    await graph.ainvoke({"question": "after expiration"}, config, durability="sync")
    assert len([item async for item in saver.alist(config)]) == 2


@pytest.mark.asyncio
async def test_preferences_are_transactional_across_reopening(preference_database):
    store = AssistantStore()
    value = {"format": "short"}
    operations = [PutOp(_ACCOUNT, "style", value), GetOp(_ACCOUNT, "style")]
    created = (await store.abatch(operations))[1]
    value["format"] = "uncommitted"
    assert (await AssistantStore().aget(_ACCOUNT, "style")).value == {"format": "short"}
    assert await AssistantStore().aget(("assistant", "1", "another-generation"), "style") is None
    with pytest.raises(TypeError):
        await store.abatch([PutOp(_ACCOUNT, "style", value), PutOp(_ACCOUNT, "invalid", {"value": object()})])
    assert (await store.aget(_ACCOUNT, "style")).value == {"format": "short"}
    await store.aput(_ACCOUNT, "style", {"format": "detailed"})
    assert (await store.aget(_ACCOUNT, "style")).created_at == created.created_at
    with pytest.raises(NotImplementedError):
        await store.abatch([SearchOp(_ACCOUNT)])
    await store.adelete(_ACCOUNT, "style")
    assert await AssistantStore().aget(_ACCOUNT, "style") is None


@pytest.mark.asyncio
async def test_bound_preferences_follow_the_chat_transaction(preference_database):
    store = AssistantStore()
    original = {"format": "short"}
    await store.aput(_ACCOUNT, "style", original)

    async with preference_database() as session:
        bound = AssistantStore(session)
        await bound.aput(_ACCOUNT, "style", {"format": "detailed"})
        assert (await bound.aget(_ACCOUNT, "style")).value == {"format": "detailed"}
        await session.rollback()
    assert (await store.aget(_ACCOUNT, "style")).value == original

    async with preference_database() as session:
        await AssistantStore(session).adelete(_ACCOUNT, "style")
        await session.rollback()
    assert (await store.aget(_ACCOUNT, "style")).value == original

    async with preference_database.begin() as session:
        await AssistantStore(session).adelete(_ACCOUNT, "style")
    assert await store.aget(_ACCOUNT, "style") is None
