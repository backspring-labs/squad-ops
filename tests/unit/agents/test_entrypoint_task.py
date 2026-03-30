"""Tests for AgentRunner._handle_task_envelope().

Verifies that the agent correctly deserializes incoming TaskEnvelopes,
submits them to the local orchestrator, and publishes results to the
reply queue.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_agents]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope_payload(envelope: TaskEnvelope, reply_queue: str = "cycle_results_run_001"):
    """Build the full message payload as the agent consumer would receive."""
    return {
        "action": "comms.task",
        "metadata": {
            "reply_queue": reply_queue,
            "correlation_id": envelope.correlation_id,
        },
        "payload": envelope.to_dict(),
    }


def _sample_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task_123",
        agent_id="neo",
        cycle_id="cyc_001",
        pulse_id="pulse_001",
        project_id="proj_001",
        task_type="development.design",
        correlation_id="corr_001",
        causation_id="cause_001",
        trace_id="trace_001",
        span_id="span_001",
        inputs={"prd": "Build something", "resolved_config": {}},
        metadata={"step_index": 1, "role": "dev"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandleTaskEnvelope:
    """AgentRunner._handle_task_envelope dispatches to orchestrator."""

    @pytest.fixture
    def runner(self):
        """Create a minimal AgentRunner with mocked internals."""
        from squadops.agents.entrypoint import AgentRunner

        with patch.object(AgentRunner, "__init__", lambda self, *a, **kw: None):
            r = AgentRunner.__new__(AgentRunner)
            r.agent_id = "neo"
            r.role = "dev"
            r._queue = AsyncMock()
            r._config = MagicMock()
            r._config.llm.timeout = 180.0

            # Mock orchestrator inside system
            mock_orchestrator = AsyncMock()
            mock_orchestrator.submit_task.return_value = TaskResult(
                task_id="task_123",
                status="SUCCEEDED",
                outputs={"summary": "implemented"},
            )
            r.system = MagicMock()
            r.system.orchestrator = mock_orchestrator

            return r

    async def test_dispatches_to_orchestrator(self, runner) -> None:
        """submit_task() is called with the deserialized TaskEnvelope."""
        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope)

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner.system.orchestrator.submit_task.assert_awaited_once()
        submitted = runner.system.orchestrator.submit_task.call_args.args[0]
        assert submitted.task_id == "task_123"
        assert submitted.task_type == "development.design"
        assert submitted.agent_id == "neo"

    async def test_publishes_result_to_reply_queue(self, runner) -> None:
        """TaskResult is published to the reply_queue from metadata."""
        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope, reply_queue="cycle_results_run_001")

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_awaited_once()
        call_args = runner._queue.publish.call_args
        assert call_args.args[0] == "cycle_results_run_001"

        published = json.loads(call_args.args[1])
        assert published["action"] == "comms.task.result"
        assert published["payload"]["task_id"] == "task_123"
        assert published["payload"]["status"] == "SUCCEEDED"

    async def test_error_returns_failed_result(self, runner) -> None:
        """If orchestrator raises, a FAILED TaskResult is published."""
        runner.system.orchestrator.submit_task.side_effect = RuntimeError("LLM timeout")

        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope)

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_awaited_once()
        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["payload"]["status"] == "FAILED"
        assert "LLM timeout" in published["payload"]["error"]

    async def test_no_reply_queue_logs_warning(self, runner) -> None:
        """If no reply_queue in metadata, result is not published."""
        envelope = _sample_envelope()
        payload = {
            "action": "comms.task",
            "metadata": {},  # no reply_queue
            "payload": envelope.to_dict(),
        }

        await runner._handle_task_envelope(payload, payload["metadata"])

        runner._queue.publish.assert_not_awaited()

    async def test_result_includes_correlation_id(self, runner) -> None:
        """Published result metadata includes the envelope's correlation_id."""
        envelope = _sample_envelope()
        payload = _make_envelope_payload(envelope)

        await runner._handle_task_envelope(payload, payload["metadata"])

        published = json.loads(runner._queue.publish.call_args.args[1])
        assert published["metadata"]["correlation_id"] == "corr_001"
