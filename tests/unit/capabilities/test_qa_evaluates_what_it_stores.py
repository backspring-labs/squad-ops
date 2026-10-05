"""#1913 and #1727: a qa task evaluates exactly the set that will be stored, and a re-take proves it.

What bugs would these catch?
- **#1913:** a qa author's emission of another producer's file (#1912's run named a quoted
  ``backend/routes.py`` excerpt as a file) ran its suite and typed checks on a tree holding that
  file, while storage then dropped it as unauthorized. The agent's verdict and the stored one read
  different trees.
- **#1727:** the re-take path asserted nothing about SIP-0107 §20 (verified equals persisted), so a
  re-take whose stored set was not the set its suite read would be accepted silently. The
  transaction is the re-take plus the self-evaluation pass that completed it, each part named.

Entered at ``QATestHandler.handle`` with the real templates; the suite runner is faked at its seam.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.cycles.patch_verification import (
    RETAKE_EVALUATED_REVISION_KEY,
    candidate_revision_id,
    retake_identity_mismatch,
)
from squadops.llm.models import ChatMessage
from squadops.prompts.renderer import RequestTemplateRenderer

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "def create():\n    return {}\n"
_SUITE = "def test_create_run(client):\n    assert client.post('/api/runs').status_code == 200\n"
_EXCERPT = "```python:backend/routes.py\ndef create():\n    return {'id': 1}\n```\n"
_WHOLE_SUITE = "```python:backend/tests/test_runs.py\n" + _SUITE + "```\n"
_EDIT = (
    "```edit:backend/tests/test_runs.py\n<<<<<<< SEARCH\n    assert client.post('/api/runs')"
    ".status_code == 200\n=======\n    assert client.post('/api/runs').status_code == 201\n"
    ">>>>>>> REPLACE\n```\n"
)


async def _handle(answer: str | list[str], monkeypatch, **extra):
    runner = AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed"))
    monkeypatch.setattr("squadops.capabilities.handlers.test_runner.run_generated_tests", runner)

    answers = iter(answer if isinstance(answer, list) else [answer])

    async def _chat(messages, **kwargs):
        return ChatMessage(role="assistant", content=next(answers), completion_tokens=40)

    ctx = MagicMock()
    ctx.task_id = "task-run_1-m003-qa.test"
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
        "artifact_contents": {"backend/routes.py": _ROUTES},
        "acceptance_workspace_files": {"backend/routes.py": _ROUTES},
        "resolved_config": {"build_profile": "fullstack_fastapi_react"},
        "subtask_focus": "the runs suite",
        "expected_artifacts": ["backend/tests/test_runs.py"],
        **extra,
    }
    result = await QATestHandler().handle(ctx, inputs)
    return result, runner


async def test_a_file_another_producer_owns_is_dropped_before_the_suite_reads_it(monkeypatch):
    """#1913: the excerpt is the source under test, which qa may not write. Storage drops it,
    so the suite must not read it either, and the task's evidence names the drop."""
    result, runner = await _handle(_WHOLE_SUITE + _EXCERPT, monkeypatch)

    suite_tree = {f["path"] for f in runner.await_args.args[0] + runner.await_args.args[1]}
    stored = {a["name"] for a in result.outputs["artifacts"]}
    assert "backend/routes.py" not in stored
    assert "backend/tests/test_runs.py" in stored
    assert result._evidence.metadata["qa_unowned_dropped"] == ["backend/routes.py"]
    # The suite reads the source under test from the workspace it was handed, never the excerpt.
    assert all("{'id': 1}" not in f["content"] for f in runner.await_args.args[0])
    assert "backend/tests/test_runs.py" in suite_tree


async def test_a_new_file_outside_the_namespace_is_kept_as_storage_keeps_it(monkeypatch):
    """The control: only a file the workspace already holds is another producer's. A new path
    outside the namespace is a deliverable, which storage passes."""
    notes = "```markdown:docs/qa_notes.md\nfindings\n```\n"

    result, _ = await _handle(_WHOLE_SUITE + notes, monkeypatch)

    assert "docs/qa_notes.md" in {a["name"] for a in result.outputs["artifacts"]}
    assert "qa_unowned_dropped" not in (result._evidence.metadata or {})


async def test_a_re_take_records_the_identity_of_the_set_its_suite_read(monkeypatch):
    """#1727: storage proves the re-take stores this set (``retake_identity_mismatch``), so the
    identity must be of exactly the artifacts the result carries."""
    result, _ = await _handle(
        _EDIT, monkeypatch, retake_current_files={"backend/tests/test_runs.py": _SUITE}
    )

    evaluated = result.outputs[RETAKE_EVALUATED_REVISION_KEY]
    assert evaluated == candidate_revision_id(None, result.outputs["artifacts"])
    assert retake_identity_mismatch(result.outputs, result.outputs["artifacts"]) is None


async def test_a_first_attempt_records_no_re_take_identity(monkeypatch):
    result, _ = await _handle(_WHOLE_SUITE, monkeypatch)

    assert RETAKE_EVALUATED_REVISION_KEY not in result.outputs


def test_a_stored_set_that_is_not_the_evaluated_one_is_named():
    """#1913's shape at storage: the re-take evaluated a set holding the excerpt, and storage's
    grants dropped it. Bug caught: the mismatch passing, so the stored state is not the one the
    verdict was about."""
    evaluated = [
        {"name": "backend/tests/test_runs.py", "content": _SUITE},
        {"name": "backend/routes.py", "content": "x\n"},
    ]
    stored = evaluated[:1]
    outputs = {RETAKE_EVALUATED_REVISION_KEY: candidate_revision_id(None, evaluated)}

    assert retake_identity_mismatch(outputs, stored) == (
        candidate_revision_id(None, evaluated),
        candidate_revision_id(None, stored),
    )
    assert retake_identity_mismatch({}, stored) is None


async def test_the_transaction_is_the_re_take_plus_the_pass_each_part_named(monkeypatch):
    """#1727 (the owner's ruling): a re-take whose edit leaves a file missing is completed by a
    self-evaluation pass, and the record names both parts: the edit, and what the pass added.
    The identity storage proves is of the completed set."""
    participants = "def test_join(client):\n    assert client.post('/api/runs/r1/join').ok\n"
    pass_answer = "```python:backend/tests/test_participants.py\n" + participants + "```\n"

    result, _ = await _handle(
        [_EDIT, pass_answer],
        monkeypatch,
        retake_current_files={"backend/tests/test_runs.py": _SUITE},
        expected_artifacts=["backend/tests/test_runs.py", "backend/tests/test_participants.py"],
        resolved_config={
            "build_profile": "fullstack_fastapi_react",
            "output_validation": True,
            "max_self_eval_passes": 1,
        },
    )

    form = result.outputs["qa_retake_revision_form"]
    assert form["edited"] == ["backend/tests/test_runs.py"]
    assert form["completed_by_self_eval"] == ["backend/tests/test_participants.py"]
    assert result.outputs[RETAKE_EVALUATED_REVISION_KEY] == candidate_revision_id(
        None, result.outputs["artifacts"]
    )
