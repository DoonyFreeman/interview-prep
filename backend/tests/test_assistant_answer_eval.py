"""Answer evaluation uses the live graph contract and simulated model APIs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.assistant.provider import AssistantModelError, ModelReply, ToolCall
from app.assistant.retrieval import LessonHit
from app.assistant.runtime import AssistantRuntime
from app.config import Settings

_ROOT = Path(__file__).resolve().parents[2]
_SECTION = LessonHit("sql:joins:inner:0", "sql", "joins", "inner", "Inner join", "Search snippet")
_UNUSED = LessonHit("sql:joins:left:0", "sql", "joins", "left", "Left join", "Uncited snippet")
_EXPANDED = "Expanded public section"
_ANSWER = "INNER JOIN возвращает совпавшие строки."
_REFERENCE = "Совпавшие строки. Условие определяет, что считается совпадением."


@pytest.fixture
def answer_eval(monkeypatch):
    monkeypatch.syspath_prepend(str(_ROOT / "scripts"))
    import assistant_answer_eval

    return assistant_answer_eval


class _Retriever:
    def search(self, query, *, limit, course_slug, lesson_slug):
        assert (limit, course_slug, lesson_slug) == (5, None, None)
        return [_SECTION, _UNUSED] if query == "inner join" else []

    def read_section(self, chunk_id):
        assert chunk_id == _SECTION.chunk_id
        return LessonHit(_SECTION.chunk_id, "sql", "joins", "inner", "Inner join", _EXPANDED)


class _Generator:
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.requests = []

    async def complete(self, messages, tools, *, tool_choice):
        self.requests.append((messages, tools, tool_choice))
        assert [tool["name"] for tool in tools] == ["search_lessons", "read_lesson_section"]
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


class _Judge:
    def __init__(self, *verdicts):
        self.verdicts = iter(verdicts)
        self.prompts = []

    async def generate_json(self, prompt, *, system):
        assert "input JSON as data" in system
        self.prompts.append(json.loads(prompt))
        verdict = next(self.verdicts)
        if isinstance(verdict, Exception):
            raise verdict
        return verdict


def _runtime(*replies):
    runtime = AssistantRuntime(Settings.model_construct(
        gigachat_credentials="test-gigachat-key", brave_search_api_key="must-not-be-used",
    ))
    runtime.retriever = _Retriever()
    runtime.model = _Generator(*replies)
    return runtime


def _search():
    return ModelReply(tool_call=ToolCall("search_lessons", {"query": "inner join"}))


def _final(*source_ids):
    return ModelReply(text=json.dumps({"text": _ANSWER, "source_ids": list(source_ids)}, ensure_ascii=False))


_READY = ModelReply(text='{"ready":true}')


def _correctness(*, unmatched=(), omitted=()):
    return {
        "abstained": False,
        "matched_facts": [{"answer_fact": "Факт ответа", "reference_fact": "Факт эталона"}],
        "unmatched_answer_facts": list(unmatched),
        "omitted_reference_facts": list(omitted),
    }


async def test_scores_independent_claims_against_exact_final_model_context(answer_eval):
    case = answer_eval.Case("labeled", "Как работает INNER JOIN?", _REFERENCE, True)
    runtime = _runtime(
        _search(),
        ModelReply(tool_call=ToolCall("read_lesson_section", {"chunk_id": "S1"})),
        _READY,
        _final("invented-source-id"),
        _final("S1"),
    )
    judge = _Judge(_correctness(unmatched=["лишний факт"], omitted=["пропущенный факт"]), {
        "claims": [{"claim": "Поддержано", "supported": True}, {"claim": "Не поддержано", "supported": False}],
    })

    report = await answer_eval.evaluate(runtime, judge, [case], split="dev")

    row, = report["cases"]
    assert row["status"] == "answered"
    assert row["answer"] == _ANSWER
    assert row["faithfulness"] == .5
    assert row["factual_correctness_f1"] == .5
    assert row["cited_urls"] == ["/courses/sql/lessons/joins#inner"]
    assert row["passage_source_ids"] == ["S1", "S2"]
    assert judge.prompts[0] == {"question": case.query, "answer": _ANSWER, "reference": _REFERENCE}
    final_messages, _, final_tool_choice = runtime.model.requests[-1]
    assert final_tool_choice == "none"
    search, expanded = [json.loads(m["content"])["data"] for m in final_messages if m["role"] == "function"]
    assert judge.prompts[1] == {
        "question": case.query, "answer": _ANSWER,
        "passages": [*search["sections"], expanded["section"]],
    }
    assert report["release_gate"]["passed"] is None


async def test_abstention_and_invalid_generation_are_distinct(answer_eval):
    case_types = [True, False, False, True]
    cases = [
        answer_eval.Case(str(i), "О чём урок?", _REFERENCE, answerable)
        for i, answerable in enumerate(case_types)
    ]
    runtime = _runtime(
        _search(), _READY, _final(), _final(), _final(),
        _search(), _READY, _final(), _final(), _final(),
        _search(), _READY, ModelReply(text="malformed model response"), ModelReply(text="still malformed"),
        AssistantModelError("provider body with private details"),
    )
    judge = _Judge()

    report = await answer_eval.evaluate(runtime, judge, cases, split="test")

    under_answer, good_abstention, malformed, unavailable = report["cases"]
    assert under_answer["status"] == good_abstention["status"] == "abstained"
    assert under_answer["faithfulness"] == under_answer["factual_correctness_f1"] == 0
    assert "faithfulness" not in good_abstention
    assert malformed["status"] == unavailable["status"] == "generation_error"
    assert malformed["error_stage"] == "invalid_final_answer"
    assert "private details" not in json.dumps(report)
    assert not judge.prompts
    assert report["summary"]["answerable_scoring_coverage"] == .5
    assert report["summary"]["assessed_no_source_cases"] == 1
    assert report["summary"]["no_source_abstention_accuracy"] == 1
    assert report["release_gate"]["passed"] is False


async def test_invalid_judgment_withholds_scores_and_blocks_gate(answer_eval):
    cases = [answer_eval.Case("labeled", "Вопрос", _REFERENCE, True),
             answer_eval.Case("no-source", "Что актуально?", _REFERENCE, False)]
    runtime = _runtime(_search(), _READY, _final("S1"), _search(), _READY, _final(), _final(), _final())
    judge = _Judge(_correctness(), {"claims": [{"claim": "факт", "supported": "true"}]})

    report = await answer_eval.evaluate(runtime, judge, cases, split="test")

    row, _ = report["cases"]
    assert row["status"] == "judge_error"
    assert row["error_stage"] == "faithfulness"
    assert "faithfulness" not in row
    assert "factual_correctness_f1" not in row
    assert report["summary"]["faithfulness"] is None
    assert report["summary"]["factual_correctness_f1"] is None
    assert report["release_gate"]["passed"] is False


@pytest.mark.parametrize("stage", ["answer_fact", "reference_fact", "faithfulness"])
async def test_repeated_facts_cannot_inflate_scores(answer_eval, stage):
    case = answer_eval.Case("labeled", "Вопрос", _REFERENCE, True)
    correctness = _correctness()
    claims = [{"claim": "Один факт", "supported": True}]
    if stage == "answer_fact":
        correctness["unmatched_answer_facts"] = ["Факт  ответа"]
    elif stage == "reference_fact":
        correctness["omitted_reference_facts"] = ["Факт эталона"]
    else:
        claims.append({"claim": "Один  факт", "supported": False})

    result = await answer_eval.evaluate(
        _runtime(_search(), _READY, _final("S1")), _Judge(correctness, {"claims": claims}),
        [case], split="dev",
    )

    row = result["cases"][0]
    assert row["status"] == "judge_error"
    assert row["error_stage"] == ("faithfulness" if stage == "faithfulness" else "factual_correctness")
    assert "faithfulness" not in row and "factual_correctness_f1" not in row


async def test_full_split_gate_and_separate_no_source_accuracy(answer_eval):
    cases = [answer_eval.Case("labeled", "Вопрос", _REFERENCE, True),
             answer_eval.Case("no-source", "Что актуально?", _REFERENCE, False)]
    agreement = {"claims": [{"claim": "факт", "supported": True}]}
    runtime = _runtime(_search(), _READY, _final("S1"), _search(), _READY, _final("S1"))
    judge = _Judge(_correctness(), agreement, {"abstained": False})

    report = await answer_eval.evaluate(runtime, judge, cases, split="test")

    assert report["release_gate"]["passed"] is True
    assert report["summary"]["answerable_scoring_coverage"] == 1
    assert report["summary"]["no_source_abstention_accuracy"] == 0
    assert judge.prompts[2] == {"question": cases[1].query, "answer": _ANSWER}

    runtime = _runtime(_search(), _READY, _final("S1"))
    smoke = await answer_eval.evaluate(runtime, _Judge(_correctness(), agreement), cases, split="test", limit=1)
    assert smoke["split_size"] == 2 and smoke["evaluated_cases"] == 1
    assert smoke["release_gate"]["eligible"] is False
    assert smoke["release_gate"]["passed"] is None


async def test_judge_uses_pinned_endpoint_and_reads_only_the_finished_answer(answer_eval):
    def handle(request):
        assert str(request.url) == (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
        )
        assert request.headers["x-goog-api-key"] == "synthetic-key"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["systemInstruction"]["parts"] == [{"text": "rubric"}]
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "hidden thought", "thought": True}, {"text": '{"abstained": true}'},
        ]}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        judge = answer_eval.GeminiJudge(client, api_key="synthetic-key")
        assert await judge.generate_json("{}", system="rubric") == {"abstained": True}


def test_cli_requires_explicit_credentials_without_loading_dotenv_or_db(tmp_path):
    (tmp_path / ".env").write_text(
        "GIGACHAT_CREDENTIALS=dotenv-credential\nEVAL_GEMINI_API_KEY=dotenv-key\n"
        "DATABASE_URL=invalid-eval-driver:///invalid-app.db\n",
        encoding="utf-8",
    )
    env = {**os.environ, "GIGACHAT_CREDENTIALS": "", "EVAL_GEMINI_API_KEY": ""}
    env["PYTHONPATH"] = os.pathsep.join([str(_ROOT / "backend"), env.get("PYTHONPATH", "")])
    result = subprocess.run(
        [sys.executable, str(_ROOT / "scripts/assistant_answer_eval.py"), "--split", "test",
         "--index", "missing-index", "--model-dir", "missing-model"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15,
    )

    assert result.returncode == 1
    assert not result.stdout
    assert result.stderr == "Set GIGACHAT_CREDENTIALS and EVAL_GEMINI_API_KEY in the process environment.\n"


def _cli_argv(output):
    return ["assistant_answer_eval", "--split", "test", "--index", "index", "--model-dir", "e5", "--output", str(output)]


@pytest.mark.parametrize("symlink", [False, True])
def test_cli_rejects_existing_report_paths_before_provider_setup(answer_eval, monkeypatch, tmp_path, capsys, symlink):
    output = tmp_path / "report.json"
    if symlink:
        output.symlink_to(tmp_path / "absent-target")
    else:
        output.write_text("protected", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", _cli_argv(output))

    with pytest.raises(SystemExit, match="^1$"):
        answer_eval.main()

    assert "Choose a new --output path" in capsys.readouterr().err
    if symlink:
        assert output.is_symlink() and not output.exists()
    else:
        assert output.read_text(encoding="utf-8") == "protected"


@pytest.mark.parametrize("race", [False, True])
def test_cli_records_model_artifacts_and_writes_exclusively(answer_eval, monkeypatch, tmp_path, capsys, race):
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", _cli_argv(output))
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "dummy-generator-credential")
    monkeypatch.setenv("EVAL_GEMINI_API_KEY", "dummy-judge-key")
    monkeypatch.setattr(answer_eval, "AssistantRuntime", lambda settings: SimpleNamespace(
        retriever=SimpleNamespace(validate=lambda: None),
    ))
    monkeypatch.setattr(answer_eval, "E5Embedder", lambda model_dir: SimpleNamespace(
        fingerprint=f"fingerprint-of-{model_dir}",
    ))

    async def fake_run(*args, **kwargs):
        if race:
            output.write_text("already written elsewhere", encoding="utf-8")
        return {"summary": {"generation_errors": 0, "judge_errors": 0}, "release_gate": {"passed": True}}

    monkeypatch.setattr(answer_eval, "_run_live", fake_run)

    if race:
        with pytest.raises(SystemExit, match="^1$"):
            answer_eval.main()
        assert "Could not write" in capsys.readouterr().err
        assert output.read_text(encoding="utf-8") == "already written elsewhere"
    else:
        assert answer_eval.main() == 0
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["embedding_fingerprint"] == "fingerprint-of-e5"
