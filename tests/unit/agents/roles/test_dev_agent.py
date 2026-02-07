"""Unit tests for DevAgent SIP-0061 instrumentation.

Tests task event taxonomy (success + failure paths), paired instrumentation,
and call-site boundary enforcement.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadops.execution.agent import AgentRequest
from squadops.execution.squad.dev import DevAgent
from squadops.llm.models import LLMResponse
from squadops.tasks.models import TaskEnvelope
from squadops.telemetry.models import CorrelationContext


def _make_agent(mock_obs=None) -> DevAgent:
    """Create a DevAgent with mocked dependencies."""
    return DevAgent(
        secret_manager=MagicMock(),
        db_runtime=MagicMock(),
        heartbeat_reporter=MagicMock(),
        agent_id="dev-001",
        llm_observability=mock_obs,
    )


def _make_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task-100",
        agent_id="dev-001",
        cycle_id="CYCLE-100",
        pulse_id="pulse-100",
        project_id="project-100",
        task_type="development.code_generate",
        inputs={"action": "build"},
        correlation_id="corr-CYCLE-100",
        causation_id="cause-root",
        trace_id="trace-task-100",
        span_id="span-task-100",
    )


def _make_request(envelope=None, llm_response=None, **extras) -> AgentRequest:
    payload = {"envelope": envelope or _make_envelope()}
    if llm_response is not None:
        payload["llm_response"] = llm_response
        payload.setdefault("model", "test-model")
        payload.setdefault("prompt_text", "write code")
    payload.update(extras)
    return AgentRequest(action="execute", payload=payload)


class TestTaskEventTaxonomy:
    """Verify all 4 SIP-0061 event taxonomy events are emitted."""

    def test_agent_emits_task_events_on_success(self):
        """Success path emits: task.assigned, task.started, task.completed (in order)."""
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)

        result = agent.on_execute(_make_request())
        assert result == {"status": "ok"}

        event_calls = [c for c in mock_obs.record_event.call_args_list]
        event_names = [c.args[1].name for c in event_calls]
        assert event_names == ["task.assigned", "task.started", "task.completed"]

    def test_agent_emits_task_events_on_failure(self):
        """Failure path emits: task.assigned, task.started, task.failed (in order)."""
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)

        # Make the llm_response trigger an error by patching build_generation_record
        request = _make_request(llm_response=MagicMock(spec=[]))  # Missing .text

        with pytest.raises(Exception):
            agent.on_execute(request)

        event_calls = [c for c in mock_obs.record_event.call_args_list]
        event_names = [c.args[1].name for c in event_calls]
        assert "task.assigned" in event_names
        assert "task.started" in event_names
        assert "task.failed" in event_names

    def test_end_task_span_called_on_success(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)
        agent.on_execute(_make_request())
        mock_obs.end_task_span.assert_called_once()

    def test_end_task_span_called_on_failure(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)

        request = _make_request(llm_response=MagicMock(spec=[]))
        with pytest.raises(Exception):
            agent.on_execute(request)

        # end_task_span must be called even on failure (finally block)
        mock_obs.end_task_span.assert_called_once()


class TestPairedInstrumentation:
    """record_generation() called when LLM response is present."""

    def test_record_generation_called_with_llm_response(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)

        llm_response = LLMResponse(
            text="generated code",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        request = _make_request(llm_response=llm_response)
        agent.on_execute(request)

        mock_obs.record_generation.assert_called_once()
        call_args = mock_obs.record_generation.call_args
        ctx = call_args.args[0]
        record = call_args.args[1]
        layers = call_args.args[2]

        assert isinstance(ctx, CorrelationContext)
        assert ctx.cycle_id == "CYCLE-100"
        assert ctx.task_id == "task-100"
        assert record.model == "test-model"
        assert record.response_text == "generated code"
        assert layers.prompt_layer_set_id is not None

    def test_no_generation_when_no_llm_response(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)
        agent.on_execute(_make_request())
        mock_obs.record_generation.assert_not_called()


class TestCallSiteBoundary:
    """Agent MUST NOT call orchestrator-owned lifecycle methods."""

    def test_agent_does_not_call_flush_or_close(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)
        agent.on_execute(_make_request())

        mock_obs.flush.assert_not_called()
        mock_obs.close.assert_not_called()

    def test_agent_does_not_call_cycle_or_pulse_methods(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)
        agent.on_execute(_make_request())

        mock_obs.start_cycle_trace.assert_not_called()
        mock_obs.end_cycle_trace.assert_not_called()
        mock_obs.start_pulse_span.assert_not_called()
        mock_obs.end_pulse_span.assert_not_called()


class TestCorrelationContext:
    """Verify context is built correctly from envelope."""

    def test_context_from_envelope(self):
        mock_obs = MagicMock()
        agent = _make_agent(mock_obs)
        agent.on_execute(_make_request())

        # Check the ctx passed to start_task_span
        ctx = mock_obs.start_task_span.call_args.args[0]
        assert ctx.cycle_id == "CYCLE-100"
        assert ctx.pulse_id == "pulse-100"
        assert ctx.task_id == "task-100"
        assert ctx.correlation_id == "corr-CYCLE-100"
        assert ctx.agent_id == "dev-001"
        assert ctx.agent_role == "dev"


class TestNoEnvelope:
    """Edge case: missing envelope in payload."""

    def test_returns_error_when_no_envelope(self):
        agent = _make_agent(MagicMock())
        request = AgentRequest(action="execute", payload={})
        result = agent.on_execute(request)
        assert result["status"] == "error"
