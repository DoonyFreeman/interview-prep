"""Progress and grounded partial replies from the assistant graph."""
import json

import pytest
from pydantic import BaseModel

from app.assistant.graph import FALLBACK_EVIDENCE_PREFIX, AssistantTool, ToolResult, compile_assistant_graph, run_assistant
from app.assistant.memory import AssistantStore
from app.assistant.persistence import SQLiteCheckpointSaver
from app.assistant.provider import AssistantModelError, ModelReply, ToolCall
from app.assistant.streaming import AnswerPreview

_HISTORY = [{"role": "user", "content": "Как работает INNER JOIN?"}]
_SOURCE = "sql:joins:inner"
_ANSWER = 'INNER JOIN оставляет совпадающие строки.\n"JOIN" — пример. 🙂'
_STATUS = "status"
_READY = ModelReply(text='{"ready":true}')


class _Query(BaseModel):
    query: str


class _Model:
    def __init__(self, replies, streams):
        self.replies = iter(replies)
        self.streams = iter(streams)
        self.requests = []

    async def complete(self, messages, tools, *, tool_choice="auto"):
        self.requests.append(("complete", tool_choice, messages))
        return next(self.replies)

    async def complete_stream(self, messages, tools, *, on_delta, tool_choice="none"):
        self.requests.append(("stream", tool_choice, messages))
        operation = next(self.streams)
        return await operation(on_delta)


def _call(name):
    return ModelReply(tool_call=ToolCall(name, {"query": "inner join"}))


def _tool(name, run):
    return AssistantTool(name, "Назначение функции", _Query, run)


async def _matching_lesson(_):
    return ToolResult({"excerpt": _ANSWER}, (_SOURCE,))


def _answer_json(answer=_ANSWER, *, source_ids=(_SOURCE,)):
    return json.dumps({"source_ids": source_ids, "text": answer})


def _one_chunk(text, *, finish_reason="stop"):
    async def stream(on_delta):
        await on_delta(text)
        return ModelReply(text=text, finish_reason=finish_reason)

    return stream


def _collect(events):
    async def collect(event, data):
        events.append((event, data))

    return collect


def test_preview_decodes_only_answer_text_across_json_escape_boundaries():
    for output in (_answer_json(), f"```json\n{_answer_json()}\n```"):
        preview = AnswerPreview((_SOURCE,))
        parts = [preview.append(char) for char in output]

        assert "".join(parts) == _ANSWER
        assert " 🙂" in parts
        assert preview.source_ids == (_SOURCE,)


@pytest.mark.parametrize("output", [
    _answer_json(source_ids=("forged",)),
    _answer_json(source_ids=()),
    _answer_json(source_ids=(_SOURCE, {})),
    _answer_json(source_ids=(_SOURCE,) * 9),
    'private analysis\n' + _answer_json(),
    json.dumps({"text": _ANSWER, "source_ids": [_SOURCE]}),
    json.dumps({"source_ids": [_SOURCE], "reasoning": "private analysis", "text": _ANSWER}),
])
def test_preview_waits_for_the_requested_envelope_and_known_sources(output):
    preview = AnswerPreview((_SOURCE,))
    assert "".join(preview.append(char) for char in output) == ""


@pytest.mark.asyncio
async def test_multiple_tool_steps_precede_the_single_streaming_writer():
    events = []

    async def search(args):
        assert events[-1] == (_STATUS, {"phase": "search_lessons"})
        return await _matching_lesson(args)

    async def read(args):
        assert events[-1] == (_STATUS, {"phase": "read_lesson_section"})
        return await _matching_lesson(args)

    async def stream(on_delta):
        content = _answer_json()
        prefix, text = content.split('"text": ', 1)
        await on_delta(prefix)
        assert events[-1] == (_STATUS, {"phase": "generating"})
        await on_delta('"text": ' + text[:6])
        assert events[-1] == ("delta", {"text": "INNER"})
        await on_delta(text[6:])
        return ModelReply(text=content)

    model = _Model([_call("search_lessons"), _call("read_lesson_section"), ModelReply(text="Готово")], [stream])
    reply = await run_assistant(
        model, _HISTORY, [_tool("search_lessons", search), _tool("read_lesson_section", read)],
        on_event=_collect(events),
    )

    assert [data["phase"] for event, data in events if event == _STATUS] == [
        "thinking", "search_lessons", "thinking", "read_lesson_section", "thinking", "generating",
    ]
    assert "".join(data["text"] for event, data in events if event == "delta") == reply.text == _ANSWER
    assert reply.source_ids == (_SOURCE,)
    assert [request[:2] for request in model.requests] == [("complete", "auto")] * 3 + [("stream", "none")]
    assert '{"ready":true}' in model.requests[0][2][0]["content"]
    assert 'Сначала запиши source_ids, затем text.' in model.requests[-1][2][0]["content"]


@pytest.mark.asyncio
async def test_stream_with_invalid_finish_resets_before_repair():
    events = []
    suspect = _answer_json("Незаконченный черновик")
    model = _Model(
        [_call("search_lessons"), _READY],
        [_one_chunk(suspect, finish_reason="length"), _one_chunk(_answer_json())],
    )

    reply = await run_assistant(model, _HISTORY, [_tool("search_lessons", _matching_lesson)], on_event=_collect(events))

    assert events[-5:] == [
        (_STATUS, {"phase": "generating"}), ("delta", {"text": "Незаконченный черновик"}),
        ("reset", {}), (_STATUS, {"phase": "generating"}), ("delta", {"text": _ANSWER}),
    ]
    assert reply.text == _ANSWER


@pytest.mark.asyncio
async def test_stream_transport_failure_uses_a_validated_completion_without_fake_deltas():
    events = []

    async def broken_stream(on_delta):
        await on_delta(_answer_json("Черновик"))
        raise AssistantModelError("Test stream interruption")

    model = _Model([_call("search_lessons"), _READY, ModelReply(text=_answer_json())], [broken_stream])

    reply = await run_assistant(model, _HISTORY, [_tool("search_lessons", _matching_lesson)], on_event=_collect(events))

    assert events[-2:] == [("delta", {"text": "Черновик"}), ("reset", {})]
    assert model.requests[-1][:2] == ("complete", "none")
    assert reply.text == _ANSWER


@pytest.mark.asyncio
async def test_untrusted_citations_emit_no_text_while_the_answer_is_repaired():
    events = []
    model = _Model(
        [_call("search_lessons"), _READY],
        [_one_chunk(_answer_json("Неизвестный источник", source_ids=("forged",))), _one_chunk(_answer_json())],
    )

    reply = await run_assistant(model, _HISTORY, [_tool("search_lessons", _matching_lesson)], on_event=_collect(events))

    assert [(event, data) for event, data in events if event != _STATUS] == [("delta", {"text": _ANSWER})]
    assert reply.source_ids == (_SOURCE,)


@pytest.mark.asyncio
async def test_course_search_fallback_uses_original_question_and_retries_omitted_citations():
    events = []
    question = "Что в LangGraph сохраняет снимки графа? " + "контекст " * 45

    async def search(args):
        assert events[-1] == (_STATUS, {"phase": "search_lessons"})
        assert args == {"query": question[:350], "scope": "all_lessons"}
        return ToolResult({"sections": [{"source_id": _SOURCE, "text": _ANSWER}]}, (_SOURCE,))

    model = _Model(
        [ModelReply(text=_answer_json(source_ids=()))],
        [_one_chunk(_answer_json(source_ids=())), _one_chunk(_answer_json())],
    )
    history = [{"role": "user", "content": question}]

    reply = await run_assistant(
        model, history, [_tool("search_lessons", search)], fallback_lesson_search=True, on_event=_collect(events),
    )

    writer_messages = model.requests[-1][2]
    assert writer_messages[1:] == history
    evidence = writer_messages[0]["content"].split(FALLBACK_EVIDENCE_PREFIX, 1)[1].split("\n", 1)[0]
    assert json.loads(evidence)["source_ids"] == [_SOURCE]
    assert reply.source_ids == (_SOURCE,)
    assert reply.tools_used == ("search_lessons",)
    assert [(event, data) for event, data in events if event != _STATUS] == [("delta", {"text": _ANSWER})]


@pytest.mark.asyncio
async def test_checkpointed_turns_reopen_with_fresh_context_and_evidence(tmp_path):
    path = tmp_path / "assistant-state.sqlite3"
    config = {"configurable": {"thread_id": "user-123:thread-456"}}
    store = AssistantStore()
    graph = compile_assistant_graph(checkpointer=SQLiteCheckpointSaver(path), store=store)
    events = []
    model = _Model([_call("search_lessons"), _READY], [_one_chunk(_answer_json())])

    first = await run_assistant(
        model, _HISTORY, [_tool("search_lessons", _matching_lesson)], graph=graph,
        thread_id="user-123:thread-456", on_event=_collect(events), memory_context="Предпочитаю примеры",
    )

    assert first.text == _ANSWER
    assert graph.store is store
    assert "Предпочитаю примеры" in model.requests[-1][2][0]["content"]
    assert events[-1] == ("delta", {"text": _ANSWER})

    async def missing_lesson(args):
        assert args == {"query": "inner join"}
        return ToolResult({"sections": []})

    reopened = compile_assistant_graph(checkpointer=SQLiteCheckpointSaver(path), store=AssistantStore())
    model = _Model([_call("search_lessons"), ModelReply(text=_answer_json())], [])
    second = await run_assistant(
        model, [{"role": "user", "content": "Новый вопрос"}], [_tool("search_lessons", missing_lesson)],
        graph=reopened, thread_id="user-123:thread-456",
    )

    assert second.source_ids == ()
    assert "Уточни тему" in second.text
    assert "Предпочитаю примеры" not in model.requests[-1][2][0]["content"]
    snapshots = [snapshot async for snapshot in reopened.aget_state_history(config)]
    assert snapshots[0].values["source_ids"] == []
    assert snapshots[0].values["reply"]["text"] == second.text
    assert any(snapshot.values.get("reply", {}).get("text") == first.text
               for snapshot in snapshots if snapshot.values.get("reply"))
    assert snapshots[0].values.keys().isdisjoint({"model", "tools", "on_event", "memory_context"})
