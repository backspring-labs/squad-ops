"""Tests for SIP-0079 outcome routing in DispatchedFlowExecutor.

Covers TaskOutcome-based routing: RETRYABLE_FAILURE retries, SEMANTIC_FAILURE
triggers correction, BLOCKED pauses, SUCCESS resets and checkpoints,
NEEDS_REPLAN from contract aborts immediately, and the D5 fallback table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.cycles.task_outcome import TaskOutcome
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_run.return_value = Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.update_run_status.side_effect = lambda run_id, status: Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=1,
        status=status.value,
        initiated_by="api",
        resolved_config_hash="hash",
    )
    mock.append_artifact_refs.return_value = mock.get_run.return_value
    mock.get_latest_checkpoint.return_value = None
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_queue(reply_router):
    """Mock QueuePort bound to the reply router: publishing a ``comms.task``
    auto-delivers the agent's reply (SIP-0094)."""
    mock = AsyncMock()
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    return reply_router.bind(mock)


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    profile = SquadProfile(
        profile_id="full-squad",
        name="Full Squad",
        description="All",
        version=1,
        agents=(
            AgentProfileEntry(agent_id="nat", role="strat", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="neo", role="dev", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="eve", role="qa", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="data-agent", role="data", model="gpt-4", enabled=True),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


@pytest.fixture
def run():
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
    )


@pytest.fixture
def executor(mock_registry, mock_vault, mock_queue, mock_squad_profile, cycle, run):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    return DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        reply_router=mock_queue.reply_router,
    )


# ---------------------------------------------------------------------------
# Helpers for scripted agent replies
# ---------------------------------------------------------------------------


def _scripted_responder(responses):
    """Build a reply-router responder that returns a different result per
    dispatch (SIP-0094 equivalent of the old per-publish consume side_effect).

    ``responses`` maps dispatch index (0-based, in publish order) to
    (status, outputs, error). Missing indices get status="SUCCEEDED". The
    responder is invoked once per ``comms.task`` publish, so the index advances
    in lockstep with the executor's dispatch sequence — exactly as the old
    consume side_effect's call counter did.
    """
    call_idx = {"n": 0}

    def responder(env):
        idx = call_idx["n"]
        call_idx["n"] += 1
        status, outputs, error = responses.get(
            idx, ("SUCCEEDED", {"summary": "ok", "role": "strat"}, None)
        )
        return TaskResult(
            task_id=env["task_id"],
            status=status,
            outputs=outputs,
            error=error,
        )

    return responder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRetryableFailure:
    """RETRYABLE_FAILURE outcome → retry the same task."""

    async def test_retryable_retries_same_task(self, executor, mock_queue, mock_registry):
        """First dispatch fails, retried, succeeds on second attempt."""
        # Publish call 0: first task → FAILED (no outcome_class → RETRYABLE)
        # Publish call 1: retry same task → SUCCEEDED
        # Publish calls 2-6: remaining 4 tasks → SUCCEEDED
        responses = {
            0: ("FAILED", None, "transient"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (fail) + 1 (retry) + 4 (remaining) = 6 publishes
        assert mock_queue.publish.call_count == 6

        # Run should complete successfully
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses

    async def test_retryable_uses_max_task_retries(
        self, executor, mock_queue, mock_registry, cycle
    ):
        """With max_task_retries=3, task gets 3 attempts before SEMANTIC."""
        import dataclasses

        cycle_3 = dataclasses.replace(cycle, applied_defaults={"max_task_retries": 3})
        mock_registry.get_cycle.return_value = cycle_3

        # All dispatches fail → attempt 1,2 = RETRYABLE, attempt 3 = SEMANTIC
        responses = {i: ("FAILED", None, "boom") for i in range(10)}
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 3 (retries) + 2 (correction tasks) = 5 publishes
        assert mock_queue.publish.call_count == 5

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestSemanticFailure:
    """SEMANTIC_FAILURE → triggers correction protocol."""

    async def test_explicit_semantic_failure_triggers_correction(
        self, executor, mock_queue, mock_registry
    ):
        """Task returns explicit SEMANTIC_FAILURE → correction protocol runs."""
        outputs_with_semantic = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "summary": "bad output",
            "role": "strat",
        }
        # Dispatch 0: FAILED with SEMANTIC_FAILURE outcome
        # Dispatches 1-2: correction tasks (analyze_failure + correction_decision)
        responses = {
            0: ("FAILED", outputs_with_semantic, "semantic error"),
            1: ("FAILED", None, "correction failed"),
            2: ("FAILED", None, "correction failed"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (task) + 2 (correction) = 3 publishes (no retry for explicit outcome)
        assert mock_queue.publish.call_count == 3

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestBlockedOutcome:
    """BLOCKED outcome → run transitions to PAUSED."""

    async def test_blocked_pauses_run(self, executor, mock_queue, mock_registry):
        """Task returns BLOCKED outcome → run transitions to PAUSED."""
        outputs_blocked = {
            "outcome_class": TaskOutcome.BLOCKED,
            "summary": "waiting for approval",
            "role": "strat",
        }
        responses = {
            0: ("FAILED", outputs_blocked, "blocked"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 1 publish (blocked on first task)
        assert mock_queue.publish.call_count == 1

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.PAUSED in terminal_statuses


class TestSuccessOutcome:
    """SUCCESS → checkpoint saved, consecutive_failures reset."""

    async def test_success_checkpoints(self, executor, mock_queue, mock_registry):
        """Each successful task triggers a checkpoint save."""
        # All 5 tasks succeed
        mock_queue.reply_router.responder = _scripted_responder({})

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 tasks → 5 checkpoint saves
        assert mock_registry.save_checkpoint.call_count == 5

    async def test_success_after_retry_still_checkpoints(self, executor, mock_queue, mock_registry):
        """Task fails once (retried), then succeeds → checkpoint saved."""
        responses = {
            0: ("FAILED", None, "transient"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 5 successful tasks → 5 checkpoints (retry failure doesn't checkpoint)
        assert mock_registry.save_checkpoint.call_count == 5


class TestNeedReplanFromContract:
    """NEEDS_REPLAN from governance.define_done → immediate abort (D9)."""

    async def test_contract_failure_aborts_immediately(
        self, executor, mock_queue, mock_registry, run
    ):
        """Contract task failure → no correction protocol, immediate abort."""
        import dataclasses

        run_impl = dataclasses.replace(run, workload_type="implementation")
        mock_registry.get_run.return_value = run_impl

        outputs_replan = {
            "outcome_class": TaskOutcome.NEEDS_REPLAN,
            "summary": "contract parse failed",
            "role": "lead",
        }
        responses = {
            0: ("FAILED", outputs_replan, "parse error"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 1 publish — contract failure is immediate abort
        assert mock_queue.publish.call_count == 1

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestFallbackTable:
    """D5 fallback table: None outcome_class → RETRYABLE first, SEMANTIC after."""

    async def test_none_outcome_first_failure_retries(self, executor, mock_queue, mock_registry):
        """First unclassified failure → RETRYABLE → retry."""
        # First dispatch fails (no outcome), second succeeds, rest succeed
        responses = {
            0: ("FAILED", None, "transient"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (fail) + 1 (retry succeeds) + 4 (remaining) = 6
        assert mock_queue.publish.call_count == 6
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses

    async def test_exhausted_retries_becomes_semantic(self, executor, mock_queue, mock_registry):
        """All retries exhausted → SEMANTIC_FAILURE → correction → abort."""
        responses = {i: ("FAILED", None, "boom") for i in range(10)}
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 (retries) + 2 (correction) = 4
        assert mock_queue.publish.call_count == 4

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


class TestNeedsRepairOutcome:
    """NEEDS_REPAIR outcome → triggers correction protocol."""

    async def test_needs_repair_triggers_correction(self, executor, mock_queue, mock_registry):
        """Explicit NEEDS_REPAIR → correction protocol."""
        outputs_repair = {
            "outcome_class": TaskOutcome.NEEDS_REPAIR,
            "summary": "needs fix",
            "role": "strat",
        }
        responses = {
            0: ("FAILED", outputs_repair, "repair needed"),
            1: ("FAILED", None, "corr"),
            2: ("FAILED", None, "corr"),
        }
        mock_queue.reply_router.responder = _scripted_responder(responses)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (task) + 2 (correction tasks) = 3
        assert mock_queue.publish.call_count == 3

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses
