"""SIP-0086 §12a change 3 — a self-evaluation pass sees what it edits.

The pass used to be told "Your previous response was incomplete" with a summary that named no
check ("Typed checks failed: N of M") and no file content, and was asked to re-emit files whole.
These tests name what each would catch: a failing check or its errors not shown; the file the
pass must fix not shown verbatim, so an edit's anchor is copied from memory; an edit fence
dropped or stored as a file; a refused transaction half-applied; a whole-file re-emission of a
shown file unrecorded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.capabilities.handlers.cycle.base import failing_check_lines
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "from typing import Any\n\n\ndef list_runs() -> list[Any]:\n    return []\n"
_FIRST = f"```python:backend/routes.py\n{_ROUTES}```\n"
_EDIT = (
    "```edit:backend/routes.py\n<<<<<<< SEARCH\nfrom typing import Any\n=======\n"
    "import fastapi\nfrom typing import Any\n>>>>>>> REPLACE\n```\n"
)
_WHOLE = f"```python:backend/routes.py\nimport fastapi\n{_ROUTES}```\n"
_REFUSED = (
    "```edit:backend/routes.py\n<<<<<<< SEARCH\nfrom typing import Nothing\n=======\n"
    "import fastapi\n>>>>>>> REPLACE\n```\n\n```python:backend/extra.py\nx = 1\n```\n"
)


async def _develop(pass_answer: str, caplog):
    sent: list = []
    answers = iter([_FIRST, pass_answer])

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content=next(answers), completion_tokens=40)

    llm = MagicMock()
    llm.default_model = "qwen3.8:27b"
    llm.chat_stream_with_usage = _chat
    prompt_service = MagicMock()
    prompt_service.assemble.return_value = MagicMock(content="system", assembly_hash="h")
    ports = PortsBundle(
        llm=llm,
        memory=MagicMock(),
        prompt_service=prompt_service,
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
        request_renderer=RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
        ),
    )
    envelope = TaskEnvelope(
        task_id="task-run_1-m000-development.develop",
        agent_id="neo",
        cycle_id="cyc",
        pulse_id="p",
        project_id="group_run",
        task_type="development.develop",
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs={
            "prd": "Runs API",
            "artifact_contents": {"implementation_plan.md": "1. routes"},
            "subtask_focus": "the runs routes",
            "expected_artifacts": ["backend/routes.py"],
            "acceptance_criteria": [
                {
                    "check": "import_present",
                    "params": {"file": "backend/routes.py", "module": "fastapi"},
                    "id": "vc-routes-import-fastapi",
                }
            ],
            "resolved_config": {"output_validation": True, "max_self_eval_passes": 1},
        },
    )
    executor = HandlerExecutor("neo", create_handler_registry(roles=["dev"]), ports, role="dev")
    with caplog.at_level(logging.INFO):
        result = await executor.execute(envelope)
    forms = [
        json.loads(r.getMessage().split("self_eval_revision_form ", 1)[1])
        for r in caplog.records
        if "self_eval_revision_form " in r.getMessage()
    ]
    stored = {a["name"]: a["content"] for a in (result.outputs or {}).get("artifacts", [])}
    return result, sent, forms, stored


async def test_a_pass_sees_the_failing_check_and_the_file_and_fixes_it_with_an_edit(caplog):
    """Entered at ``HandlerExecutor.execute`` on the real develop handler and templates. Bug
    caught: the pass told only "Typed checks failed: 1 of 3" — no check, no file — and asked
    to re-emit it whole; or its edit fence dropped, or stored as a file named by its path."""
    result, sent, forms, stored = await _develop(_EDIT, caplog)

    followup = sent[1][-1].content
    failing = followup.split("Every check that failed")[1].split("Files you already produced")[0]
    assert (
        "- check: `acceptance:import_present`, file: `backend/routes.py`, "
        "criterion_id: `vc-routes-import-fastapi` — failed: module_not_imported"
    ) in failing
    assert f"`backend/routes.py`:\n```\n{_ROUTES}```" in followup, "the file, verbatim"
    assert "How to Write an Edit Fence" in followup
    assert result.status == "SUCCEEDED", result.error
    # Stored as the extractor stores every file: without its final newline.
    assert stored["backend/routes.py"] == "import fastapi\n" + _ROUTES.rstrip("\n")
    (form,) = forms
    assert (form["pass"], form["form"], form["edited"]) == (1, "edits", ["backend/routes.py"])


async def test_a_pass_that_re_emits_a_shown_file_whole_is_recorded_as_such(caplog):
    """Recorded like a repair's (SIP-0107 §46a, §46o). Bug caught: a shown file re-emitted
    whole read as an edit, or not read at all — the pass's form invisible to the count."""
    result, _sent, forms, stored = await _develop(_WHOLE, caplog)

    assert result.status == "SUCCEEDED", result.error
    assert stored["backend/routes.py"] == "import fastapi\n" + _ROUTES.rstrip("\n")
    (form,) = forms
    assert form["form"] == "whole_file"
    assert form["whole_file_offered"] == ["backend/routes.py"]


async def test_a_refused_edit_applies_nothing(caplog):
    """SIP-0107 §14: one transaction, all or none. Bug caught: a refused edit's whole-file
    remainder applied, or the refused fence stored as a file."""
    result, _sent, forms, stored = await _develop(_REFUSED, caplog)

    assert stored["backend/routes.py"] == _ROUTES.rstrip("\n"), "the pass changed nothing"
    assert "backend/extra.py" not in stored, "nor added the whole file it emitted beside it"
    assert result.status == "FAILED"
    (form,) = forms
    assert form["refusals"] >= 1


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {
                "check": "acceptance:frontend_compiles",
                "params": {"file": "app/page.tsx"},
                "passed": False,
                "reason": "frontend_build_failed",
                "actual": {
                    "diagnostics": ["app/page.tsx(3,1): error TS2304: Cannot find name 'x'."],
                    "diagnostic_count": 4,
                },
            },
            [
                "- check: `acceptance:frontend_compiles`, file: `app/page.tsx` — failed: "
                "frontend_build_failed",
                "  - app/page.tsx(3,1): error TS2304: Cannot find name 'x'.",
                "  - (+3 more)",
            ],
        ),
        (
            {
                "check": "acceptance:frontend_compiles",
                "params": {"file": "src/App.jsx"},
                "passed": False,
                "reason": "frontend_build_failed",
                "actual": {"stderr_tail": "RollupError: 'runId' is not defined"},
            },
            [
                "- check: `acceptance:frontend_compiles`, file: `src/App.jsx` — failed: "
                "frontend_build_failed",
                "`build output`:\n```\nRollupError: 'runId' is not defined\n```",
            ],
        ),
        ({"check": "acceptance:import_present", "passed": True, "status": "passed"}, []),
    ],
    ids=["every type error, and how many more", "the build's tail when no list", "a pass"],
)
def test_every_failing_row_is_shown_with_what_it_reported(row, expected):
    """Bug caught: change 2's diagnostic list carried to the evidence and never shown to the
    pass that could act on it, or a row that passed shown as a failure."""
    assert failing_check_lines([row]) == expected


async def test_a_shape_that_declines_edits_is_shown_no_file_and_no_edit_form():
    """The qa scaffold fill declines (its shells are filled by slot, never edited). Bug
    caught: the loop offering the edit form whatever the shape says, so a pass edits a frozen
    shell's text around its slots."""
    from squadops.capabilities.handlers.cycle.base import SelfEvalFollowup
    from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
    from squadops.capabilities.handlers.cycle.validation import ValidationResult

    class _Declines(SelfEvalFollowup):
        edits_offered = False

    failing = ValidationResult(
        passed=False,
        checks=[
            {
                "check": "acceptance:import_present",
                "params": {"file": "backend/routes.py"},
                "passed": False,
                "reason": "module_not_imported",
            }
        ],
        summary="Typed checks failed: 1 of 1",
    )
    sent: list = []

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content="", completion_tokens=5)

    ctx = MagicMock()
    ctx.task_id = "task-1"
    ctx.ports.llm.chat_stream_with_usage = _chat
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx.correlation_context = None
    handler = DevelopmentDevelopHandler()

    async def _still_failing(*_a, **_k):
        return failing

    handler._validate_output = _still_failing
    for shape, offered in ((_Declines(), False), (SelfEvalFollowup(), True)):
        sent.clear()
        await handler._self_evaluate(
            ctx,
            {"resolved_config": {"max_self_eval_passes": 1}},
            validation=failing,
            artifacts=[{"name": "backend/routes.py", "content": _ROUTES}],
            evidence_extra={},
            typed_error_counts={},
            transcript=("system", "build it", _FIRST),
            chat_kwargs={},
            started=0.0,
            rendered=None,
            followup=shape,
        )
        followup = sent[0][-1].content
        assert ("How to Write an Edit Fence" in followup) is offered, type(shape).__name__
        assert ("`backend/routes.py`:\n```" in followup) is offered
