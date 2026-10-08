"""Capturing each authoring seam before it authors (SIP-0110 §0.9, §0.11; #2105).

The capture lives in ``_llm_call``, the one sequence every model call goes through, and the
handler executor hands it the task's inputs. These enter at ``HandlerExecutor.execute``, the
caller the live agent uses, with the real proposal handler, renderer and assembler.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.capabilities.context_assembly import (
    CONTEXT_CONTRACTS,
    authoring_seam_of,
)
from squadops.capabilities.handlers.planning.proposal import StrategyProposeIncrementHandler
from squadops.llm.models import ChatMessage
from squadops.memory.authoring_envelope import AuthoringReplayEnvelope, AuthoringSeam
from squadops.orchestration.handler_executor import HandlerExecutor
from squadops.orchestration.handler_registry import HandlerRegistry
from squadops.tasks.models import TaskEnvelope
from squadops.tasks.task_types import TaskType
from tests.unit.agent_foundation.orchestration.test_handler_executor import MockHandler
from tests.unit.capabilities.test_strategy_propose_increment import (
    _REFERENCE,
    _ctx,
    _fenced,
    _inputs,
)

pytestmark = [pytest.mark.domain_capabilities]

_SEAMS = {
    TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF: AuthoringSeam.PLAN_WRITING,
    TaskType.DEVELOPMENT_DESIGN_PLAN: AuthoringSeam.PLAN_WRITING,
    TaskType.DEVELOPMENT_AUTHOR_MANIFEST: AuthoringSeam.PLAN_WRITING,
    TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: AuthoringSeam.PLAN_WRITING,
    TaskType.QA_PROPOSE_PLAN_TASKS: AuthoringSeam.PLAN_WRITING,
    TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: AuthoringSeam.PLAN_WRITING,
    TaskType.DEVELOPMENT_DEVELOP: AuthoringSeam.BUILD_AUTHORING,
    TaskType.QA_TEST: AuthoringSeam.BUILD_AUTHORING,
    TaskType.BUILDER_ASSEMBLE: AuthoringSeam.BUILD_AUTHORING,
    TaskType.DEVELOPMENT_REPAIR: AuthoringSeam.REPAIR,
    TaskType.DEVELOPMENT_CORRECTION_REPAIR: AuthoringSeam.REPAIR,
    TaskType.QA_TEST_REPAIR: AuthoringSeam.REPAIR,
    TaskType.BUILDER_ASSEMBLE_REPAIR: AuthoringSeam.REPAIR,
    TaskType.STRATEGY_PROPOSE_INCREMENT: AuthoringSeam.PROPOSAL_WRITING,
}


def test_the_seams_are_exactly_the_fourteen_task_types_section_0_9_names():
    """Bug caught: a seam whose authoring is never captured (so no replay case exists for it),
    or a task type captured that is not a seam (a prompt stored that nothing will replay)."""
    found = {t: authoring_seam_of(t) for t in TaskType if authoring_seam_of(t) is not None}

    assert found == _SEAMS


def test_plan_writing_is_read_from_the_plan_rejection_declaration_not_declared_twice():
    """Bug caught: a seventh plan-authoring type given #2058's context but never captured, the
    two declarations drifting apart."""
    plan_writers = {t for t, c in CONTEXT_CONTRACTS.items() if c.plan_rejection_context}

    assert {t for t, s in _SEAMS.items() if s is AuthoringSeam.PLAN_WRITING} == plan_writers


def _executor(handler, ctx_ports) -> HandlerExecutor:
    registry = HandlerRegistry()
    registry.register(handler)
    return HandlerExecutor("exec-1", registry, ctx_ports, role="strat")


def _dispatched(task_type: str, inputs: dict) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task-run_1-m000-x",
        agent_id="nat",
        cycle_id="cyc_1",
        pulse_id="p",
        project_id="group_run",
        task_type=task_type,
        correlation_id="c",
        causation_id="c",
        trace_id="t",
        span_id="s",
        inputs=inputs,
    )


async def test_a_proposal_is_captured_once_before_its_first_call_with_what_it_was_given():
    """Wiring, entered at ``HandlerExecutor.execute``. The first answer is refused and re-asked,
    so the model is called twice. Bugs caught: the envelope taken at the re-ask (whose prompt
    carries the refusal, not what the author was given), taken twice, or holding inputs other
    than the dispatched ones."""
    ports = _ctx("No proposal here.", _fenced(_REFERENCE)).ports
    inputs = _inputs()

    result = await _executor(StrategyProposeIncrementHandler(), ports).execute(
        _dispatched(TaskType.STRATEGY_PROPOSE_INCREMENT, inputs)
    )

    assert result.status == "SUCCEEDED", result.error
    calls = ports.llm.chat_stream_with_usage.call_args_list
    assert len(calls) == 2
    envelope = AuthoringReplayEnvelope.from_dict(result.authoring_envelope)
    assert envelope.seam is AuthoringSeam.PROPOSAL_WRITING
    assert [(m["role"], m["content"]) for m in envelope.messages] == [
        (m.role, m.content) for m in calls[0].args[0]
    ]
    assert envelope.inputs == inputs
    assert envelope.task_id == "task-run_1-m000-x" and envelope.role == "strat"
    assert envelope.memory == {"snapshot": None, "intervention": None}


async def test_a_task_that_is_not_a_seam_carries_no_envelope():
    """Bug caught: every task's prompt stored, which nothing replays and which costs the store."""
    handler = MockHandler(task_type=TaskType.DATA_REPORT, outputs={"summary": "s"})

    result = await _executor(handler, MagicMock()).execute(_dispatched(TaskType.DATA_REPORT, {}))

    assert result.status == "SUCCEEDED"
    assert result.authoring_envelope is None


async def test_a_capture_that_fails_never_fails_the_authoring():
    """Bug caught: the instrument changing the run it measures: a proposal refused because its
    envelope could not be built."""
    ports = _ctx(_fenced(_REFERENCE)).ports

    with patch(
        "squadops.memory.authoring_envelope.capture_envelope", side_effect=RuntimeError("boom")
    ):
        result = await _executor(StrategyProposeIncrementHandler(), ports).execute(
            _dispatched(TaskType.STRATEGY_PROPOSE_INCREMENT, _inputs())
        )

    assert result.status == "SUCCEEDED", result.error
    assert result.authoring_envelope is None


async def test_a_seam_task_that_raises_after_its_call_still_reports_its_envelope():
    """Bug caught: the envelope of a task that failed lost with it. A failed authoring is still
    a case the replay can read."""
    ports = _ctx(_fenced(_REFERENCE)).ports
    handler = StrategyProposeIncrementHandler()
    original = handler._success

    def explode(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after the call")

    handler._success = explode  # type: ignore[method-assign]
    result = await _executor(handler, ports).execute(
        _dispatched(TaskType.STRATEGY_PROPOSE_INCREMENT, _inputs())
    )

    assert result.status == "FAILED"
    assert result.authoring_envelope["seam"] == AuthoringSeam.PROPOSAL_WRITING.value


async def test_the_capture_is_not_fooled_by_a_mock_context():
    """Bug caught: a test double's auto-attribute read as captured inputs, so the capture runs on
    mock values and breaks the call under test (what broke twelve suites while building this)."""
    ctx = MagicMock()
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        return_value=ChatMessage(role="assistant", content="x")
    )
    ctx.authoring_envelope = None

    handler = StrategyProposeIncrementHandler()
    await handler._llm_call(
        ctx, [ChatMessage(role="user", content="u")], {}, inputs={}, started=0.0, record=False
    )

    assert ctx.authoring_envelope is None
