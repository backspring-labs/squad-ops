"""SIP-0086 §12a change 3, 1.8.2 plan §3.3 — a qa re-take after a refunded repair edits its suite.

The executor carries the suite the failed qa task wrote onto its re-dispatch. These tests name
what each would catch: the suite not shown (so the re-take re-authors blind), its edits dropped
or refused silently, and a whole-suite re-emission — deploy A's shape on every such re-take —
unrecorded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.llm.models import ChatMessage
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_SUITE = "def test_create_run(client):\n    assert client.post('/api/runs').status_code == 200\n"
_EDIT = (
    "```edit:tests/test_runs.py\n<<<<<<< SEARCH\n    assert client.post('/api/runs').status_code "
    "== 200\n=======\n    assert client.post('/api/runs').status_code == 201\n>>>>>>> REPLACE\n```\n"
)
_WHOLE = "```python:tests/test_runs.py\n" + _SUITE.replace("200", "201") + "```\n"
_PARTICIPANTS = (
    "def test_join_run(client):\n"
    "    assert client.post('/api/runs/r1/join', json={'name': 'ann'}).status_code == 200\n"
)
_ONE_SUITE = {"tests/test_runs.py": _SUITE}
_TWO_FILE_SUITE = {"tests/test_runs.py": _SUITE, "tests/test_participants.py": _PARTICIPANTS}


async def _retake(
    answer: str, caplog, monkeypatch, *, carried: bool = True, suite: dict | None = None
):
    suite = _ONE_SUITE if suite is None else suite
    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_generated_tests",
        AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed")),
    )
    sent: list = []

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content=answer, completion_tokens=40)

    ctx = MagicMock()
    ctx.task_id = "task-run_1-m005-qa.test"
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx.correlation_context = None
    ctx.disputed_checks = []
    inputs = {
        "prd": "Runs API",
        "artifact_contents": {"backend/routes.py": "def create():\n    return {}\n"},
        "subtask_focus": "the runs suite",
        "expected_artifacts": sorted(suite),
    }
    if carried:
        inputs["retake_current_files"] = dict(suite)
    with caplog.at_level(logging.INFO):
        result = await QATestHandler().handle(ctx, inputs)
    forms = [
        json.loads(r.getMessage().split("qa_retake_revision_form ", 1)[1])
        for r in caplog.records
        if "qa_retake_revision_form " in r.getMessage()
    ]
    stored = {a["name"]: a["content"] for a in (result.outputs or {}).get("artifacts", [])}
    return result, sent[0][-1].content, forms, stored


async def test_a_re_take_is_shown_its_suite_and_edits_it(caplog, monkeypatch):
    """Entered at ``QATestHandler.handle`` on the plan-driven path and the real templates. Bug
    caught: the suite not shown, so the re-take re-authors it blind — or the edit fence dropped,
    leaving an empty emission that fails the task."""
    result, prompt, forms, stored = await _retake(_EDIT, caplog, monkeypatch)

    assert "A Re-take: Revise the Suite You Wrote" in prompt
    assert f"`tests/test_runs.py`:\n```\n{_SUITE}```" in prompt, "the suite, verbatim"
    assert result.success, result.error
    assert "status_code == 201" in stored["tests/test_runs.py"]
    (form,) = forms
    assert (form["form"], form["edited"]) == ("edits", ["tests/test_runs.py"])


async def test_a_re_take_that_re_emits_the_suite_whole_is_recorded_as_such(caplog, monkeypatch):
    """Deploy A's shape on every such re-take. Bug caught: the re-emission unread, so the
    readout cannot tell a re-take that edited from one that re-authored."""
    result, _prompt, forms, stored = await _retake(_WHOLE, caplog, monkeypatch)

    assert result.success, result.error
    assert "status_code == 201" in stored["tests/test_runs.py"]
    (form,) = forms
    assert form["whole_file_offered"] == ["tests/test_runs.py"]


async def test_a_first_attempt_is_offered_no_edit_form(caplog, monkeypatch):
    """The control: only the re-take after a refunded round carries the suite."""
    result, prompt, forms, _stored = await _retake(_WHOLE, caplog, monkeypatch, carried=False)

    assert "A Re-take" not in prompt
    assert forms == []
    assert result.success, result.error


@pytest.mark.parametrize(
    "answer", [_EDIT, _WHOLE], ids=["edits one file", "re-emits one file whole"]
)
async def test_a_re_take_keeps_the_suite_files_it_leaves_alone(caplog, monkeypatch, answer):
    """#1755, read on 1.8.2 deploy A′ (``cyc_96656c0e48be``): offered two suite files, the
    re-take edited one, and the other vanished from the tree the checks read; self-evaluation
    then regenerated it whole, unverified against the file it replaced. Bug caught: the task's
    output is only the files the response touched, not the transaction's candidate."""
    result, _prompt, forms, stored = await _retake(
        answer, caplog, monkeypatch, suite=_TWO_FILE_SUITE
    )

    assert result.success, result.error
    assert "status_code == 201" in stored["tests/test_runs.py"]
    assert stored["tests/test_participants.py"] == _PARTICIPANTS, "byte for byte"
    (form,) = forms
    assert form["carried"] == ["tests/test_participants.py"]


async def test_the_carried_suite_never_stands_in_for_an_empty_re_take(caplog, monkeypatch):
    """The edge: a re-take that answers with no edit and no file still fails as having emitted
    nothing. Bug caught: the carried suite filling the output, so an empty answer passes as the
    suite it was shown."""
    result, _prompt, forms, stored = await _retake(
        "I could not find anything to change.", caplog, monkeypatch, suite=_TWO_FILE_SUITE
    )

    assert not result.success
    assert not set(stored) & set(_TWO_FILE_SUITE), "no suite file in the failed output"
    (form,) = forms
    assert form["carried"] == []
