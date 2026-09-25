"""SIP-0096 §17a change 1 — a producer's dispute of a check, captured as a typed output.

A build or repair task may end its response with one ``disputed_checks`` block. The block is
stripped before anything extracts files from it and its entries ride the task's outputs.
These tests name what each would catch: a block stored as the task's expected file, a dispute
lost on the failed result it is most often attached to, or an instruction the template
declares and the handler never passes (the #1289 shape).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.capabilities.disputed_checks import (
    DISPUTED_CHECKS,
    criterion_identities,
    failing_row_identities,
    split_disputed_checks,
)
from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.capabilities.handlers.impl.repair_handlers import DevelopmentCorrectionRepairHandler
from squadops.capabilities.handlers.test_runner import RunTestsResult
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskEnvelope, TaskResultStatus
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "def create(payload):\n    return Run(**payload.dict())\n"
_FILE = "```python:backend/routes.py\nx = 1\n```\n"
_DISPUTE = (
    "```disputed_checks\n"
    "- check: acceptance:declared_imports\n"
    "  file: frontend/src/views/RunList.jsx\n"
    "  criterion_id: vc-view-compiles-run-list\n"
    "  reason: the @/lib alias is declared in the tsconfig paths\n"
    "```\n"
)
_DISPUTED = {
    "check": "acceptance:declared_imports",
    "file": "frontend/src/views/RunList.jsx",
    "criterion_id": "vc-view-compiles-run-list",
    "reason": "the @/lib alias is declared in the tsconfig paths",
}
_NAMED_FILE = "```yaml:disputed_checks.yaml\n- check: a\n  reason: b\n```\n"


@pytest.mark.parametrize(
    ("response", "kept", "disputes"),
    [
        (_FILE + "\n" + _DISPUTE, _FILE + "\n", [_DISPUTED]),
        (_NAMED_FILE, _NAMED_FILE, []),
        ("```disputed_checks\n- check: [unclosed\n```\n", "", []),
        (
            "```disputed_checks\n- check: a\n- check: b\n  reason: r\n```\n",
            "",
            [{"check": "b", "reason": "r"}],
        ),
        ("no block at all", "no block at all", []),
    ],
    ids=["after a file", "a file named for it", "unparseable", "no reason", "absent"],
)
def test_the_block_is_taken_out_whole_and_only_a_well_formed_entry_disputes(
    response, kept, disputes
):
    """Bug caught: a file whose path mentions the word read as a dispute; a block that does
    not parse left in the response for the extractor; an entry with no reason counted."""
    assert split_disputed_checks(response) == (kept, disputes)


#: The typed criterion the build tasks here are judged by, in the resolved form a plan hands them,
#: and the failing row its evaluation produced — the shape a repair's evidence carries.
_CRITERION = {
    "check": "declared_imports",
    "params": {"file": "frontend/src/views/RunList.jsx"},
    "id": "vc-view-compiles-run-list",
}
_FAILING_ROW = {
    "check": "acceptance:declared_imports",
    "severity": "error",
    "params": {"file": "frontend/src/views/RunList.jsx"},
    "status": "failed",
    "passed": False,
    "reason": "unresolved import '@/lib/api'",
    "criterion_id": "vc-view-compiles-run-list",
}
_IDENTITY = (
    "- check: `acceptance:declared_imports`, file: `frontend/src/views/RunList.jsx`, "
    "criterion_id: `vc-view-compiles-run-list`"
)


@pytest.mark.parametrize(
    ("reader", "entries", "lines"),
    [
        (criterion_identities, [_CRITERION, "the list shows every run"], [_IDENTITY]),
        (
            criterion_identities,
            [{"check": "command_exit_zero", "argv": ["npm", "test"]}],
            ["- check: `acceptance:command_exit_zero`"],
        ),
        (
            failing_row_identities,
            [_FAILING_ROW],
            [_IDENTITY + " — failed: unresolved import '@/lib/api'"],
        ),
        (
            failing_row_identities,
            [
                {**_FAILING_ROW, "status": "passed", "passed": True},
                # A warning-severity failure: advice, which the loop never acts on (#598).
                {**_FAILING_ROW, "severity": "warning", "passed": True},
                {"check": "tests_pass", "passed": False, "file": "tests/test_runs.py"},
            ],
            ["- check: `tests_pass`, file: `tests/test_runs.py`"],
        ),
    ],
    ids=["criterion", "flat criterion, no file", "failing row", "only blocking failures"],
)
def test_each_check_is_named_as_its_row_will_be(reader, entries, lines):
    """Bug caught: a criterion listed under its bare name while its row says ``acceptance:``,
    so the quoted name matches nothing; prose listed as a check; a passing or advisory row
    offered for dispute."""
    assert reader(entries) == lines


def _renderer() -> RequestTemplateRenderer:
    return RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )


def _repair_inputs() -> dict:
    return {
        "prd": "Runs API",
        "failed_task_type": "development.develop",
        "failure_evidence": {"validation_result": {"checks": [_FAILING_ROW]}},
        "correction_decision": {},
        "expected_artifacts": ["backend/routes.py"],
        "acceptance_workspace_files": {"backend/routes.py": _ROUTES},
    }


def _executor(response: str, sent: list) -> HandlerExecutor:
    llm = MagicMock()
    llm.default_model = "qwen3.8:27b"

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content=response, completion_tokens=40)

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
        request_renderer=_renderer(),
    )
    return HandlerExecutor("dev-agent", create_handler_registry(roles=["dev"]), ports, role="dev")


def _envelope(task_type: str, inputs: dict) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=f"task-{task_type}",
        agent_id="dev-agent",
        cycle_id="cyc_disputes",
        pulse_id="pulse-1",
        project_id="group_run",
        task_type=task_type,
        inputs=inputs,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
    )


_DEVELOP_INPUTS = {
    "prd": "Runs API",
    "acceptance_criteria": [_CRITERION],
    "artifact_contents": {"implementation_plan.md": "1. The runs routes"},
    "subtask_focus": "the runs routes",
    "expected_artifacts": ["backend/routes.py"],
}


@pytest.mark.parametrize(
    ("task_type", "inputs", "status"),
    [
        # A repair's prose is kept as its note, and the task succeeds.
        (TaskType.DEVELOPMENT_CORRECTION_REPAIR, _repair_inputs(), TaskResultStatus.SUCCEEDED),
        # A build task with no file fails — the result a dispute is most often attached to.
        (TaskType.DEVELOPMENT_DEVELOP, _DEVELOP_INPUTS, TaskResultStatus.FAILED),
    ],
    ids=["dev repair", "develop"],
)
async def test_an_answer_that_is_only_a_dispute_carries_it_and_stores_no_file(
    task_type, inputs, status
):
    """#1581's shape, entered where the agent enters: the producer answers that the file is
    right and the check is wrong. Bug caught: the block, the response's only fence, stored AS
    ``backend/routes.py`` by the single-expected-file fallback; or the dispute dropped from a
    result, the failed one above all."""
    sent: list = []
    response = "The routes module is correct; the check reads the wrong config.\n\n" + _DISPUTE

    result = await _executor(response, sent).execute(_envelope(task_type, inputs))

    assert result.status == status, result.error
    assert result.outputs[DISPUTED_CHECKS] == [_DISPUTED]
    stored = result.outputs.get("artifacts") or []
    assert "backend/routes.py" not in {a["name"] for a in stored}
    assert not any("disputed_checks" in str(a.get("content")) for a in stored), stored
    assert "```disputed_checks" in sent[0][-1].content, "the task was told how to dispute"


async def test_a_response_without_the_block_carries_no_disputes_key():
    """The control: a task that disputes nothing reports nothing, not an empty list."""
    result = await _executor("```python:backend/routes.py\n" + _ROUTES + "```\n", []).execute(
        _envelope(TaskType.DEVELOPMENT_CORRECTION_REPAIR, _repair_inputs())
    )

    assert result.status == TaskResultStatus.SUCCEEDED, result.error
    assert DISPUTED_CHECKS not in result.outputs


def _context(sent: list) -> MagicMock:
    ctx = MagicMock()

    async def _chat(messages, **kwargs):
        sent.append(messages)
        return ChatMessage(role="assistant", content=_FILE, completion_tokens=40)

    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = _renderer()
    ctx.correlation_context = None
    ctx.disputed_checks = []
    ctx.task_id = "task-1"
    return ctx


_SOURCES = {"my_app/main.py": "def main():\n    print('hello')\n"}


@pytest.mark.parametrize(
    ("handler", "inputs"),
    [
        (DevelopmentCorrectionRepairHandler, _repair_inputs()),
        (DevelopmentDevelopHandler, _DEVELOP_INPUTS),
        (
            QATestHandler,
            {
                "prd": "Runs API",
                "artifact_contents": _SOURCES,
                "subtask_focus": "the runs suite",
                "expected_artifacts": ["tests/test_runs.py"],
                "acceptance_criteria": [_CRITERION],
            },
        ),
        (
            BuilderAssembleHandler,
            {
                "prd": "Runs API",
                "resolved_config": {"build_profile": "python_cli_builder"},
                "artifact_contents": _SOURCES,
                "acceptance_criteria": [_CRITERION],
            },
        ),
    ],
    ids=["dev repair", "develop", "qa test", "builder assemble"],
)
async def test_every_build_and_repair_prompt_says_how_to_dispute_a_check(
    handler, inputs, monkeypatch
):
    """Through each handler's own render, on the real templates, on the path a plan-driven task
    takes. Bug caught: the section declared by a template and never passed by its handler — it
    renders empty (#1289 is the same gap) — or passed without the checks, so the task is told it
    may dispute and never told what it is judged by."""
    monkeypatch.setattr(
        "squadops.capabilities.handlers.test_runner.run_generated_tests",
        AsyncMock(return_value=RunTestsResult(executed=True, exit_code=0, stdout="1 passed")),
    )
    sent: list = []

    await handler().handle(_context(sent), inputs)

    prompt = "\n".join(str(m.content) for m in sent[0])
    assert "If a check you are judged by is wrong" in prompt
    assert _IDENTITY in prompt


async def test_a_task_judged_by_no_named_check_is_not_offered_a_dispute():
    """The control: a build task whose criteria are all prose has nothing a dispute could name,
    and is not told how to dispute."""
    sent: list = []
    inputs = {**_DEVELOP_INPUTS, "acceptance_criteria": ["the list shows every run"]}

    await DevelopmentDevelopHandler().handle(_context(sent), inputs)

    assert "disputed_checks" not in "\n".join(str(m.content) for m in sent[0])
