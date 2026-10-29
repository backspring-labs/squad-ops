"""The correction repairs' ``handle()``, characterized whole before #2810 moves what they show.

#2810 moves what a repair's prompt shows of the tree it repairs (``acceptance_workspace_files``
with the failed task's own files over it) out of ``_RepairPromptMixin`` into
``squadops.capabilities.repair_prompt_contents``, so the composer counts it through the same
functions. That is an extraction: no byte of what reaches the model, what the repair returns, or
what it logs may change.

These cases drive the real ``handle()`` of the dev and qa repairs through each shape the moved
code decides: a named file in the workspace, one from the failed task's own files, a new file
beside them, none existing (the whole-file form), a qa repair's failing-case frames, a file whose
backticks lengthen its fence, and a refused whole-file re-emission retried once. Each is compared
against a golden captured from the code before the extraction (``origin/main`` at ``cf1fbe23``).

The renderer records each template it is asked for with its variables and renders a hash of them,
so a section the moved code renders with different variables, or renders where it didn't before,
changes the golden, and an edit to a template's own text elsewhere doesn't.

Bug caught: the extraction changing which files the repair shows or offers for editing, their
order or fences, the files its failing-case frames are cut from, the edit form's entity list, or
what its edits are applied to.

Regenerate (only for a DELIBERATE behaviour change, in the PR that makes it):
    UPDATE_REPAIR_GOLDENS=1 pytest tests/unit/capabilities/handlers/test_repair_prompt_characterization.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from squadops.capabilities.handlers.impl.repair_handlers import (
    DevelopmentCorrectionRepairHandler,
    QATestRepairHandler,
)
from squadops.llm.models import ChatMessage

pytestmark = [pytest.mark.domain_capabilities]

_GOLDEN_PATH = Path(__file__).parent / "goldens" / "repair_prompt_characterization.json"
_LOGGER = "squadops.capabilities.handlers.impl.repair_handlers"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class _Renderer:
    """Records each render with its variables, and renders a hash of exactly those variables."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def render(self, template_id: str, variables: dict[str, Any], environment: str = "x"):
        self.calls.append({"template": template_id, "variables": dict(variables)})
        payload = json.dumps(variables, sort_keys=True, default=str)
        rendered = MagicMock()
        rendered.content = f"[{template_id} {_sha(payload)}]"
        rendered.template_id = template_id
        rendered.template_version = "1"
        rendered.render_hash = _sha(template_id + payload)
        return rendered


def _context(*responses: str) -> tuple[MagicMock, list, _Renderer]:
    calls: list[list[ChatMessage]] = []
    queued = list(responses)
    renderer = _Renderer()

    ctx = MagicMock()
    assembled = MagicMock()
    assembled.content = "System prompt"
    assembled.assembly_hash = "sha256:test"
    ctx.ports.prompt_service.get_system_prompt.return_value = assembled
    ctx.ports.request_renderer = renderer
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.llm_observability = None

    async def _capture(messages, **kwargs):
        calls.append(list(messages))
        if not queued:
            raise AssertionError(f"handler made {len(calls)} LLM calls; fewer were seeded")
        return ChatMessage(
            role="assistant", content=queued.pop(0), prompt_tokens=11, completion_tokens=7
        )

    ctx.ports.llm.chat_stream_with_usage = _capture
    ctx.correlation_context = None
    return ctx, calls, renderer


def _normalize(value: Any) -> Any:
    """Artifact contents become their hash and length, so the golden stays readable while
    still pinning every byte."""
    if isinstance(value, dict):
        return {
            k: {"sha": _sha(v), "len": len(v)} if k == "content" and isinstance(v, str)
            else _normalize(v)
            for k, v in value.items()
        }  # fmt: skip
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# --- an invented product: an orbit tracker's backend, its console and its suite ----------------

_ROUTES = (
    "from orbit.store import moons\n\n\n"
    "def list_moons():\n    return [m.name for m in moons()]\n\n\n"
    "def moon_period(name):\n    return next(m.period for m in moons() if m.name == name)\n"
)
_STORE = "MOONS = []\n\n\ndef moons():\n    return list(MOONS)\n"
_PANEL = "export function Panel({ moons }) {\n  return moons.map((m) => m.name).join(', ');\n}\n"
_SUITE = "".join(
    f"def test_moon_{i}():\n    assert moon_period('io') == {i}\n\n\n" for i in range(1, 6)
)
#: A module whose docstring quotes a fence, so its own fence must be longer, and names a moon
#: outside ASCII.
_FENCED = '"""Shown as:\n\n````\n```python\nx = 1\n```\n````\n\nAlso Mimas and Encélade."""\n\n\ndef label():\n    return "Encélade"\n'
_WORKSPACE = {
    "orbit/routes.py": _ROUTES,
    "orbit/store.py": _STORE,
    "orbit/docs.py": _FENCED,
    "console/src/Panel.jsx": _PANEL,
    "tests/test_orbit.py": _SUITE,
}
_EVIDENCE = {
    "failed_task_id": "task-run_orbit-m000-development.develop",
    "validation_result": {
        "summary": "moon_period raises StopIteration for an unknown moon",
        "checks": [{"check": "acceptance:endpoint_defined", "passed": False}],
    },
}
_DECISION = {"correction_path": "patch", "decision_rationale": "moon_period needs a default"}


def _inputs(expected: list[str], **extra) -> dict:
    return {
        "prd": "Orbit lists each moon and its period.",
        "failed_task_type": "development.develop",
        "failure_evidence": _EVIDENCE,
        "failure_analysis": {"analysis_summary": "no default for an unknown moon"},
        "correction_decision": _DECISION,
        "subtask_focus": "the moon period",
        "subtask_description": "Return 0 for a moon the store doesn't hold.",
        "expected_artifacts": expected,
        "acceptance_criteria": ["An unknown moon's period is 0."],
        "acceptance_workspace_files": dict(_WORKSPACE),
        "correction_attempt": 1,
        "max_correction_attempts": 3,
        **extra,
    }


def _edit(path: str, search: str, replace: str) -> str:
    return f"```edit:{path}\n<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n```\n"


_ROUTES_EDIT = _edit(
    "orbit/routes.py",
    "    return next(m.period for m in moons() if m.name == name)",
    "    return next((m.period for m in moons() if m.name == name), 0)",
)
_FAILING_CASES = {
    **_EVIDENCE,
    "validation_result": {
        "summary": "2 failed",
        "checks": [
            {
                "check": "tests_pass",
                "passed": False,
                "failing_cases": [
                    {
                        "file": "tests/test_orbit.py",
                        "title": "test_moon_3",
                        "failing_line": 10,
                        "message": "assert 0 == 3",
                    },
                    {
                        "file": "tests/test_missing.py",
                        "title": "test_absent",
                        "line": 4,
                        "message": "file not in the tree",
                    },
                ],
            }
        ],
    },
}

_CASES: dict[str, tuple[type, tuple[str, ...], dict]] = {
    # The named file is in the workspace: shown, offered for editing, edited.
    "dev_named_file_in_the_workspace": (
        DevelopmentCorrectionRepairHandler,
        (_ROUTES_EDIT,),
        _inputs(["orbit/routes.py"]),
    ),
    # One named file only the failed task wrote, over the workspace, and one new file.
    "dev_failed_tasks_own_file_and_a_new_file": (
        DevelopmentCorrectionRepairHandler,
        (
            _edit("orbit/ledger.py", "LEDGER = {}", "LEDGER = {'io': 2}")
            + "```python:orbit/defaults.py\nDEFAULT_PERIOD = 0\n```\n",
        ),
        _inputs(
            ["orbit/ledger.py", "orbit/defaults.py"],
            failed_task_artifacts=[
                {"name": "orbit/ledger.py", "content": "LEDGER = {}\n"},
                {"name": "orbit/routes.py", "content": _ROUTES.replace("name)", "name)  # v2")},
            ],
        ),
    ),
    # Nothing named exists yet: no current files, no edit form, the whole-file form.
    "dev_no_named_file_exists": (
        DevelopmentCorrectionRepairHandler,
        ("```python:orbit/fresh.py\nFRESH = True\n```\n",),
        _inputs(["orbit/fresh.py"]),
    ),
    # A file whose own backticks lengthen its fence, with a moon outside ASCII.
    "dev_a_file_with_fences_and_unicode": (
        DevelopmentCorrectionRepairHandler,
        (_edit("orbit/docs.py", '    return "Encélade"', '    return "Enceladus"'),),
        _inputs(["orbit/docs.py", "console/src/Panel.jsx"]),
    ),
    # An existing file re-emitted whole is refused, and the repair is asked once more.
    "dev_whole_file_refused_then_retried": (
        DevelopmentCorrectionRepairHandler,
        (f"```python:orbit/routes.py\n{_ROUTES}```\n", _ROUTES_EDIT),
        _inputs(["orbit/routes.py"], correction_decision={}),
    ),
    # A qa repair: its failing cases' frames, cut from the tree it repairs.
    "qa_failing_cases_with_frames": (
        QATestRepairHandler,
        (
            _edit(
                "tests/test_orbit.py",
                "    assert moon_period('io') == 3",
                "    assert moon_period('io') == 0",
            ),
        ),
        _inputs(
            ["tests/test_orbit.py"],
            failed_task_type="qa.test",
            failure_evidence=_FAILING_CASES,
        ),
    ),
}


async def _run(case: str, caplog) -> dict:
    handler_class, responses, inputs = _CASES[case]
    ctx, calls, renderer = _context(*responses)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        result = await handler_class().handle(ctx, dict(inputs))
    return _normalize(
        {
            "success": result.success,
            "error": result.error,
            "renders": renderer.calls,
            "transcripts": [[[m.role, m.content] for m in msgs] for msgs in calls],
            "outputs": {k: v for k, v in result.outputs.items() if k != "prompt_provenance"},
            "log": [r.getMessage() for r in caplog.records if r.name == _LOGGER],
        }
    )


@pytest.mark.parametrize("case", list(_CASES))
async def test_a_repairs_handle_is_what_it_was_before_the_extraction(case, caplog):
    """Entered at each repair handler's ``handle()``. Bug caught: the move of what a repair shows
    of its tree changing any byte of its prompt, its outputs or its log lines."""
    observed = await _run(case, caplog)

    golden = json.loads(_GOLDEN_PATH.read_text()) if _GOLDEN_PATH.exists() else {}
    if os.environ.get("UPDATE_REPAIR_GOLDENS") == "1":
        golden[case] = observed
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(json.dumps(golden, indent=1, sort_keys=True) + "\n")
        return

    assert case in golden, f"no golden for {case}; capture it from the pre-extraction code"
    assert observed == golden[case], (
        f"{case}: handle() changed what it sends, returns or logs. If the change is DELIBERATE, "
        "regenerate the golden in the same PR so it reads as a behaviour change."
    )


def test_the_cases_exercise_what_the_extraction_moves():
    """Guards the golden against going vacuous: a case that stopped showing current files,
    offering the edit form, cutting a frame or retrying would still match its own regenerated
    golden and prove nothing."""
    golden = json.loads(_GOLDEN_PATH.read_text())

    def rendered(case: str, template: str) -> list[dict]:
        return [c["variables"] for c in golden[case]["renders"] if c["template"] == template]

    [shown] = rendered("dev_named_file_in_the_workspace", "request.cycle_repair_current_files")
    assert "`orbit/routes.py`:\n```\nfrom orbit.store" in shown["current_files"]
    [own] = rendered(
        "dev_failed_tasks_own_file_and_a_new_file", "request.cycle_repair_current_files"
    )
    assert own["current_files"] == "`orbit/ledger.py`:\n```\nLEDGER = {}\n```"
    [form] = rendered(
        "dev_failed_tasks_own_file_and_a_new_file", "request.cycle_repair_output_scoped"
    )
    assert form["new_files"] == "- `orbit/defaults.py`"
    assert rendered("dev_no_named_file_exists", "request.cycle_repair_current_files") == []
    [fenced] = rendered("dev_a_file_with_fences_and_unicode", "request.cycle_repair_current_files")
    assert "`orbit/docs.py`:\n`````\n" in fenced["current_files"]
    assert "Encélade" in fenced["current_files"]
    assert rendered(
        "dev_whole_file_refused_then_retried", "request.cycle_repair_anchored_edit_retry"
    )
    [frames] = rendered(
        "qa_failing_cases_with_frames", "request.qa_test_repair_failing_cases_appendix"
    )
    assert "`tests/test_orbit.py:10` › test_moon_3" in frames["case_frames"]
    assert "test_missing.py" not in frames["case_frames"]
