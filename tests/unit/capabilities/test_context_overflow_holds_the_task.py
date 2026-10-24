"""A prompt that overflows the served window holds its task (SIP-0111 §5.2).

What bug would these catch? A context overflow read as the work product's failure: retried with
the same prompt, which fails the same way, then sent to a correction round whose repair is
blamed for a deploy defect (the registry's window and the server's disagree). Every handler
catches ``LLMError`` its own way, so a handler that names its own outcome (or none) must not
decide this one.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.cycles.task_outcome import TaskOutcome
from squadops.llm.exceptions import LLMContextOverflowError, LLMTimeoutError
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskEnvelope, TaskResultStatus
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "def create(payload):\n    return Run(**payload.dict())\n"
_DEVELOP = {
    "prd": "Runs API",
    "artifact_contents": {"implementation_plan.md": "1. The runs routes"},
    "subtask_focus": "the runs routes",
    "expected_artifacts": ["backend/routes.py"],
}
_REPAIR = {
    "prd": "Runs API",
    "failed_task_type": "development.develop",
    "failure_evidence": {},
    "correction_decision": {},
    "expected_artifacts": ["backend/routes.py"],
    "acceptance_workspace_files": {"backend/routes.py": _ROUTES},
}


def _executor(error: Exception, calls: list) -> HandlerExecutor:
    llm = MagicMock()
    llm.default_model = "qwen3.8-27b-tf-nvfp4"

    async def _refused(messages, **kwargs):
        calls.append(messages)
        raise error

    llm.chat_stream_with_usage = _refused
    prompt_service = MagicMock()
    prompt_service.assemble.return_value = MagicMock(content="system", assembly_hash="h")
    ports = PortsBundle(
        llm=llm,
        prompt_service=prompt_service,
        queue=MagicMock(),
        metrics=MagicMock(),
        events=MagicMock(),
        filesystem=MagicMock(),
        request_renderer=RequestTemplateRenderer(
            FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
        ),
    )
    return HandlerExecutor("dev-agent", create_handler_registry(roles=["dev"]), ports, role="dev")


def _envelope(task_type: str, inputs: dict) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=f"task-{task_type}",
        agent_id="dev-agent",
        cycle_id="cyc_overflow",
        pulse_id="pulse-1",
        project_id="group_run",
        task_type=task_type,
        inputs=inputs,
        correlation_id="corr",
        causation_id="cause",
        trace_id="trace",
        span_id="span",
    )


_CASES = pytest.mark.parametrize(
    ("task_type", "inputs"),
    [
        (TaskType.DEVELOPMENT_DEVELOP, _DEVELOP),
        (TaskType.DEVELOPMENT_CORRECTION_REPAIR, _REPAIR),
    ],
    ids=["develop", "dev repair"],
)


@_CASES
async def test_an_overflow_holds_the_task_with_the_windows_it_names(task_type, inputs):
    """Entered where the agent enters, through each handler's own ``except LLMError``."""
    calls: list = []
    overflow = LLMContextOverflowError(
        "prompt of 70,112 tokens exceeds the served window",
        served_window=65536,
        prompt_tokens=70112,
    )

    result = await _executor(overflow, calls).execute(_envelope(task_type, inputs))

    assert len(calls) == 1, "the same prompt is never sent again"
    assert result.status == TaskResultStatus.FAILED
    assert result.outputs["outcome_class"] == TaskOutcome.BLOCKED
    assert result.outputs["infrastructure_block"] == {
        "reason": "context_overflow",
        "served_window": 65536,
        "prompt_tokens": 70112,
        "message": "prompt of 70,112 tokens exceeds the served window",
    }


@_CASES
async def test_any_other_model_failure_is_left_to_the_retry_and_correction_path(task_type, inputs):
    calls: list = []

    result = await _executor(LLMTimeoutError("timed out"), calls).execute(
        _envelope(task_type, inputs)
    )

    assert result.status == TaskResultStatus.FAILED
    assert (result.outputs or {}).get("outcome_class") != TaskOutcome.BLOCKED
    assert "infrastructure_block" not in (result.outputs or {})
