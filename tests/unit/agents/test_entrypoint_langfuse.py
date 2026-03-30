"""Tests for LangFuse lifecycle wrapping in AgentRunner._handle_task_envelope.

Verifies that start_cycle_trace, start_task_span, end_task_span,
end_cycle_trace, and flush are called around submit_task, including
on failure paths.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_agents]


def _make_envelope_payload() -> dict:
    """Build a payload dict as would arrive from the queue."""
    envelope = TaskEnvelope(
        task_id="task_abc",
        agent_id="neo",
        cycle_id="cyc_001",
        pulse_id="p1",
        project_id="proj_001",
        task_type="development.design",
        correlation_id="corr-1",
        causation_id="cause-1",
        trace_id="shared-trace-id",
        span_id="span-1",
        metadata={"role": "dev"},
    )
    return {
        "action": "comms.task",
        "metadata": {"reply_queue": "cycle_results_run_001"},
        "payload": envelope.to_dict(),
    }


def _make_runner():
    """Build a minimal AgentRunner-like object for testing _handle_task_envelope."""
    # We test the method directly, not via the full AgentRunner constructor
    # (which requires instances.yaml). Instead, patch what we need.
    from squadops.agents.entrypoint import AgentRunner

    with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
        runner = AgentRunner.__new__(AgentRunner)

    runner.role = "dev"
    runner.agent_id = "neo"
    runner._config = MagicMock()
    runner._config.llm.timeout = 180.0

    # Mock system with ports
    runner.system = MagicMock()
    runner.system.orchestrator.submit_task = AsyncMock(
        return_value=TaskResult(task_id="task_abc", status="SUCCEEDED", outputs={"summary": "ok"})
    )

    # Mock LLM observability
    mock_obs = MagicMock()
    runner.system.ports.llm_observability = mock_obs

    # Mock queue
    runner._queue = AsyncMock()
    runner._queue.publish = AsyncMock()

    return runner, mock_obs


class TestTaskEnvelopeWrapsWithLangfuseLifecycle:
    """Verify LangFuse lifecycle calls around submit_task."""

    async def test_lifecycle_calls_on_success(self):
        runner, mock_obs = _make_runner()
        payload = _make_envelope_payload()

        await runner._handle_task_envelope(payload, payload["metadata"])

        mock_obs.start_cycle_trace.assert_called_once()
        mock_obs.start_task_span.assert_called_once()
        mock_obs.end_task_span.assert_called_once()
        mock_obs.end_cycle_trace.assert_called_once()
        mock_obs.flush.assert_called_once()

    async def test_correlation_context_has_trace_id(self):
        runner, mock_obs = _make_runner()
        payload = _make_envelope_payload()

        await runner._handle_task_envelope(payload, payload["metadata"])

        ctx = mock_obs.start_cycle_trace.call_args[0][0]
        assert ctx.trace_id == "shared-trace-id"
        assert ctx.cycle_id == "cyc_001"
        assert ctx.task_id == "task_abc"
        assert ctx.agent_id == "neo"
        assert ctx.agent_role == "dev"

    async def test_result_published_to_reply_queue(self):
        runner, mock_obs = _make_runner()
        payload = _make_envelope_payload()

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_awaited_once()
        pub_args = runner._queue.publish.call_args
        assert pub_args.args[0] == "cycle_results_run_001"
        published = json.loads(pub_args.args[1])
        assert published["payload"]["task_id"] == "task_abc"
        assert published["payload"]["status"] == "SUCCEEDED"


class TestTaskEnvelopeLangfuseOnFailure:
    """Verify lifecycle calls happen even on submit_task failure."""

    async def test_lifecycle_calls_on_failure(self):
        runner, mock_obs = _make_runner()
        runner.system.orchestrator.submit_task = AsyncMock(side_effect=RuntimeError("boom"))
        payload = _make_envelope_payload()

        await runner._handle_task_envelope(payload, payload["metadata"])

        # Lifecycle still called in finally block
        mock_obs.start_cycle_trace.assert_called_once()
        mock_obs.start_task_span.assert_called_once()
        mock_obs.end_task_span.assert_called_once()
        mock_obs.end_cycle_trace.assert_called_once()
        mock_obs.flush.assert_called_once()

    async def test_failure_result_published(self):
        runner, mock_obs = _make_runner()
        runner.system.orchestrator.submit_task = AsyncMock(side_effect=RuntimeError("boom"))
        payload = _make_envelope_payload()

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_awaited_once()
        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["payload"]["status"] == "FAILED"
        assert "boom" in published["payload"]["error"]


class TestTaskEnvelopeNoObservability:
    """When llm_observability is None (NoOp not assigned), no errors."""

    async def test_no_observability_no_error(self):
        runner, _ = _make_runner()
        runner.system.ports.llm_observability = None
        payload = _make_envelope_payload()

        # Should not raise
        await runner._handle_task_envelope(payload, payload["metadata"])

        runner.system.orchestrator.submit_task.assert_awaited_once()
