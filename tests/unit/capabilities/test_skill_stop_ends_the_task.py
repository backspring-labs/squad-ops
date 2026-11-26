"""A task whose model answers with its skill's declared stop ends there (SIP-0116 §17o; #3041).

What bug would these catch? A stop read as an empty emission: asked again, then sent to a
correction round, so the model is told to do what its skill told it to refuse and the reason
never reaches whoever reads the run. Every handler catches ``LLMError`` its own way and names
its own outcome, so none of them may decide this one. Entered where the agent enters, at
``HandlerExecutor.execute``, with the real handlers and prompt assets.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.agents.base import PortsBundle
from squadops.bootstrap.handlers import create_handler_registry
from squadops.llm.models import ChatMessage
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import SKILL_STOP_EVIDENCE, TaskEnvelope, TaskResultStatus
from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"
_ROUTES = "def create(payload):\n    return Run(**payload.dict())\n"
_LINE = "saved data: the profile's coins field would be renamed"
_SKILLS = [
    {
        "skillset": "fixture-dev",
        "version": 1,
        "skill": "gameplay",
        "digest": "0" * 64,
        "files": {
            "SKILL.md": (
                '---\nname: gameplay\ndescription: d\nstops: ["saved data:"]\n---\n'
                "Write the change. If it renames a saved field, stop and say in one line:\n"
                "`saved data: <field> would be renamed`.\n"
            )
        },
    }
]
_STOP = {
    "skillset": "fixture-dev",
    "skill": "gameplay",
    "opening": "saved data:",
    "line": _LINE,
}
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


def _executor(answer: str, calls: list) -> HandlerExecutor:
    llm = MagicMock()
    llm.default_model = "m"

    async def _answered(messages, **kwargs):
        calls.append(messages)
        return ChatMessage(role="assistant", content=answer)

    llm.chat_stream_with_usage = _answered
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
        cycle_id="cyc_stop",
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
async def test_a_stop_ends_the_task_once_naming_the_skill_and_its_line(task_type, inputs):
    calls: list = []

    result = await _executor(f"I can't make this change.\n\n`{_LINE}`\n", calls).execute(
        _envelope(task_type, {**inputs, "skills": _SKILLS})
    )

    assert len(calls) == 1, "a stopped task is never asked again"
    assert result.status == TaskResultStatus.FAILED
    assert result.error == f"stopped by the skill fixture-dev/gameplay: {_LINE}"
    assert result.execution_evidence[SKILL_STOP_EVIDENCE] == _STOP


@_CASES
async def test_the_same_words_from_a_task_handed_no_such_skill_are_no_stop(task_type, inputs):
    """The edge. Bug caught: a stop read from words alone, so any task whose answer opens a
    line that way ends its run whatever it was equipped with."""
    calls: list = []

    result = await _executor(f"`{_LINE}`\n", calls).execute(_envelope(task_type, inputs))

    assert SKILL_STOP_EVIDENCE not in (result.execution_evidence or {})
    assert "stopped by the skill" not in (result.error or "")


async def test_a_task_handed_the_skill_that_does_its_work_is_not_stopped():
    """Bug caught: a skill that declares a stop ending every task handed it."""
    calls: list = []
    answer = f"```python:backend/routes.py\n{_ROUTES}```\n"

    result = await _executor(answer, calls).execute(
        _envelope(TaskType.DEVELOPMENT_DEVELOP, {**_DEVELOP, "skills": _SKILLS})
    )

    assert SKILL_STOP_EVIDENCE not in (result.execution_evidence or {})
    assert "stopped by the skill" not in (result.error or "")
    assert any(
        a.get("name") == "backend/routes.py" for a in (result.outputs or {}).get("artifacts", [])
    )
