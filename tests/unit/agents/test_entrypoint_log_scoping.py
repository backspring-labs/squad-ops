"""SIP-0087 B1 contract test: end-to-end log scoping in the agent process.

Pins the contract that gives the SIP its value: when the agent receives a
TaskEnvelope carrying flow_run_id / task_run_id, log records emitted *while
submit_task is running* reach the Prefect forwarder tagged with those IDs.

Without this contract, handler events (executing_capability,
handler_succeeded, t/s=… throughput lines) never appear in the Prefect
task pane — which is the entire point of the SIP.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.prefect_log_forwarder import LogHandlerFilters, PrefectLogHandler
from squadops.tasks.models import TaskEnvelope, TaskResult

pytestmark = [pytest.mark.domain_agents]


def _envelope_with_run_ids(*, flow_run_id: str, task_run_id: str) -> TaskEnvelope:
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
        metadata={"role": "dev"},
        flow_run_id=flow_run_id,
        task_run_id=task_run_id,
    )


def _payload_for(envelope: TaskEnvelope) -> dict:
    return {
        "action": "comms.task",
        "metadata": {
            "reply_queue": "cycle_results_run_001",
            "correlation_id": envelope.correlation_id,
        },
        "payload": envelope.to_dict(),
    }


def _make_runner(submit_impl=None):
    """Bare AgentRunner — bypass __init__ to avoid loading instances.yaml."""
    from squadops.agents.entrypoint import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_id = "neo"
    runner.role = "dev"
    runner._queue = AsyncMock()
    runner._config = MagicMock()
    runner._config.llm.timeout = 180.0

    async def default_submit(envelope, timeout_seconds=None):
        # Emit a handler-style log inside submit_task so the test can assert
        # what reaches the forwarder. ``adapters.test`` matches the default
        # allowed_prefixes so the record is not filtered by name.
        logging.getLogger("adapters.test").info("handler heartbeat tokens=42")
        return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={"summary": "ok"})

    # Use a real async function so the awaited call runs the body. AsyncMock's
    # side_effect handling for async callables is brittle in nested awaits; a
    # plain function avoids that ambiguity.
    runner.system = MagicMock()
    runner.system.orchestrator = MagicMock()
    runner.system.orchestrator.submit_task = submit_impl or default_submit
    runner.system.ports.llm_observability = None
    return runner


@pytest.fixture
def installed_handler():
    """Install a real PrefectLogHandler against a mock forwarder on root.

    Also forces INFO level on the loggers we drive in these tests, so the
    record actually reaches the handler — without this, source loggers
    inherit WARNING and silently drop INFO records before any handler runs.
    """
    forwarder = MagicMock(enqueue=MagicMock())
    handler = PrefectLogHandler(forwarder, filters=LogHandlerFilters(min_level=logging.INFO))
    logging.getLogger().addHandler(handler)

    prior_levels = {
        name: logging.getLogger(name).level for name in ("adapters", "squadops")
    }
    logging.getLogger("adapters").setLevel(logging.INFO)
    logging.getLogger("squadops").setLevel(logging.INFO)

    yield forwarder, handler

    logging.getLogger().removeHandler(handler)
    for name, level in prior_levels.items():
        logging.getLogger(name).setLevel(level)


# ---------------------------------------------------------------------------
# B1 contract: handler logs during submit_task carry the envelope's run IDs
# ---------------------------------------------------------------------------


async def test_handler_log_during_submit_task_carries_run_ids(installed_handler):
    """A log emitted inside submit_task is forwarded with flow_run_id /
    task_run_id from the envelope."""
    forwarder, _handler = installed_handler
    runner = _make_runner()
    envelope = _envelope_with_run_ids(flow_run_id="fr-abc", task_run_id="tr-xyz")

    await runner._handle_task_envelope(_payload_for(envelope), {})

    forwarder.enqueue.assert_called_once()
    payload = forwarder.enqueue.call_args.args[0]
    assert payload["flow_run_id"] == "fr-abc"
    assert payload["task_run_id"] == "tr-xyz"
    assert "handler heartbeat tokens=42" in payload["message"]


async def test_logs_emitted_after_submit_task_returns_are_not_scoped(installed_handler):
    """Once submit_task returns, the contextvar exits. A subsequent log
    emitted *outside* the scope must not carry run IDs (otherwise we'd
    leak task IDs onto orchestrator-level logs)."""
    forwarder, _handler = installed_handler
    runner = _make_runner()
    envelope = _envelope_with_run_ids(flow_run_id="fr-abc", task_run_id="tr-xyz")

    await runner._handle_task_envelope(_payload_for(envelope), {})
    forwarder.enqueue.reset_mock()

    # Emit *after* dispatch returns — outside any correlation context.
    logging.getLogger("adapters.test").info("post-dispatch noise")

    forwarder.enqueue.assert_not_called()


async def test_envelope_without_run_ids_does_not_enter_run_ids_scope(installed_handler):
    """Envelope with empty run IDs (Prefect disabled at runtime-api) →
    handler logs are dropped (no flow_run_id/task_run_id in payload).
    Acceptance criterion §7.7: pre-correlation logs stay out of task panes."""
    forwarder, _handler = installed_handler
    runner = _make_runner()
    envelope = _envelope_with_run_ids(flow_run_id="", task_run_id="")

    await runner._handle_task_envelope(_payload_for(envelope), {})

    # The log inside submit_task entered use_correlation_context but NOT
    # use_run_ids (since there are no IDs). PrefectLogHandler drops records
    # without flow_run_id or task_run_id.
    forwarder.enqueue.assert_not_called()


async def test_run_ids_cleared_when_submit_task_raises(installed_handler):
    """Failure inside submit_task must still exit the contextvar scope.
    Otherwise leaked IDs would tag every subsequent log on the same task."""
    forwarder, _handler = installed_handler

    async def raising_submit(envelope, timeout_seconds=None):
        logging.getLogger("adapters.test").info("about to fail")
        raise RuntimeError("boom")

    runner = _make_runner(submit_impl=raising_submit)
    envelope = _envelope_with_run_ids(flow_run_id="fr-abc", task_run_id="tr-xyz")

    await runner._handle_task_envelope(_payload_for(envelope), {})

    # The pre-failure log was forwarded with the IDs.
    payload = forwarder.enqueue.call_args.args[0]
    assert payload["flow_run_id"] == "fr-abc"
    assert payload["task_run_id"] == "tr-xyz"
    forwarder.enqueue.reset_mock()

    # Logs after the failure are not scoped.
    logging.getLogger("adapters.test").info("post-failure")
    forwarder.enqueue.assert_not_called()
