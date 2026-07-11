"""Tests for SIP-0079 executor checkpoint, resume, and time budget.

Covers:
- Checkpoint saved after each successful task
- Checkpoint NOT saved after failed task
- Resume: skip completed tasks from checkpoint
- Resume: prior_outputs and artifact_refs restored
- CHECKPOINT_CREATED / CHECKPOINT_RESTORED events emitted
- Time budget enforcement
- RUN_RESUMED event emitted on resume
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
    WorkloadType,
)
from squadops.cycles.run_ledger import RunLedger
from squadops.events.types import EventType
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    mock.get_run.return_value = Run(
        run_id="run_impl",
        cycle_id="cyc_impl",
        run_number=1,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash",
        workload_type=WorkloadType.IMPLEMENTATION,
    )
    mock.update_run_status.side_effect = lambda run_id, status: Run(
        run_id=run_id,
        cycle_id="cyc_impl",
        run_number=1,
        status=status.value,
        initiated_by="api",
        resolved_config_hash="hash",
        workload_type=WorkloadType.IMPLEMENTATION,
    )
    mock.append_artifact_refs.return_value = mock.get_run.return_value
    mock.get_latest_checkpoint.return_value = None
    mock.save_checkpoint.return_value = None
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_queue(reply_router):
    mock = AsyncMock()
    mock.publish.return_value = None
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    # SIP-0094: the executor dispatches over {agent_id}_comms and awaits the
    # reply via the router instead of polling. bind() wires publish so each
    # dispatched comms.task auto-delivers the agent's reply.
    reply_router.bind(mock)
    return mock


@pytest.fixture
def mock_squad_profile():
    mock = AsyncMock()
    profile = SquadProfile(
        profile_id="full",
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
def impl_cycle():
    return Cycle(
        cycle_id="cyc_impl",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref="Build a CLI tool",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={},
        execution_overrides={},
    )


@pytest.fixture
def mock_event_bus():
    return MagicMock()


@pytest.fixture
def executor(mock_registry, mock_vault, mock_queue, mock_squad_profile, impl_cycle, mock_event_bus):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    mock_registry.get_cycle.return_value = impl_cycle
    return DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        event_bus=mock_event_bus,
        reply_router=mock_queue.reply_router,
    )


# ---------------------------------------------------------------------------
# Checkpoint on success
# ---------------------------------------------------------------------------


class TestCheckpointOnSuccess:
    """Checkpoint saved after each successful task."""

    async def test_checkpoint_saved_per_task(self, executor, mock_registry, mock_queue) -> None:
        """save_checkpoint called once per successful task (3 for implementation)."""
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        assert mock_registry.save_checkpoint.call_count == 3

    async def test_checkpoint_indices_increment(self, executor, mock_registry, mock_queue) -> None:
        """Each checkpoint has sequential checkpoint_index."""
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        calls = mock_registry.save_checkpoint.call_args_list
        indices = [c.args[0].checkpoint_index for c in calls]
        assert indices == [1, 2, 3]

    async def test_checkpoint_completed_task_ids_grow(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """Each checkpoint records all completed tasks so far."""
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        calls = mock_registry.save_checkpoint.call_args_list
        counts = [len(c.args[0].completed_task_ids) for c in calls]
        assert counts == [1, 2, 3]

    async def test_checkpoint_not_saved_after_failure(
        self, executor, mock_registry, mock_queue
    ) -> None:
        """No checkpoint saved when a task fails."""
        dispatch_count = 0

        def fail_second(env):
            nonlocal dispatch_count
            dispatch_count += 1
            # First task succeeds, every subsequent dispatch (including
            # retries of the failing task) fails.
            if dispatch_count == 1:
                return TaskResult(
                    task_id=env["task_id"],
                    status="SUCCEEDED",
                    outputs={"summary": "ok", "artifacts": []},
                )
            return TaskResult(
                task_id=env["task_id"],
                status="FAILED",
                error="build error",
            )

        mock_queue.reply_router.responder = fail_second

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Only 1 checkpoint (first task succeeded), none for the failure
        assert mock_registry.save_checkpoint.call_count == 1


# ---------------------------------------------------------------------------
# Checkpoint events
# ---------------------------------------------------------------------------


class TestCheckpointEvents:
    """CHECKPOINT_CREATED event emitted after each save."""

    async def test_checkpoint_created_event(self, executor, mock_event_bus, mock_queue) -> None:
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        checkpoint_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CHECKPOINT_CREATED
        ]
        assert len(checkpoint_events) == 3

    async def test_checkpoint_created_payload(self, executor, mock_event_bus, mock_queue) -> None:
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        checkpoint_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CHECKPOINT_CREATED
        ]
        first_payload = checkpoint_events[0].kwargs.get("payload") or checkpoint_events[0][1].get(
            "payload", {}
        )
        assert first_payload["checkpoint_index"] == 1


# ---------------------------------------------------------------------------
# Resume from checkpoint
# ---------------------------------------------------------------------------


class TestResumeFromCheckpoint:
    """Resume skips completed tasks from checkpoint."""

    async def test_skip_completed_tasks(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """When checkpoint has 1 completed task, only 2 are dispatched."""
        # Set up checkpoint with first task completed
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.define_done",),
            prior_outputs={"lead": {"summary": "contract established"}},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Only 2 tasks dispatched (skipped the first)
        assert mock_queue.publish.call_count == 2

    async def test_prior_outputs_restored(self, executor, mock_registry, mock_queue) -> None:
        """Prior outputs from checkpoint are available to subsequent tasks."""
        prior = {"lead": {"contract": "established"}}
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.define_done",),
            prior_outputs=prior,
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Verify the dispatched task includes prior_outputs from checkpoint
        first_publish = mock_queue.publish.call_args_list[0]
        msg_data = json.loads(first_publish.args[1])
        task_inputs = msg_data["payload"]["inputs"]
        assert task_inputs["prior_outputs"]["lead"]["contract"] == "established"

    async def test_artifact_refs_restored(
        self, executor, mock_registry, mock_vault, mock_queue
    ) -> None:
        """Artifact refs from checkpoint are restored."""
        art_ref = ArtifactRef(
            artifact_id="art_001",
            project_id="proj_001",
            filename="contract.md",
            media_type="text/markdown",
            artifact_type="document",
            content_hash="sha256:abc",
            size_bytes=100,
            created_at=NOW,
        )
        mock_vault.retrieve.return_value = (art_ref, b"# Contract")
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.define_done",),
            prior_outputs={},
            artifact_refs=("art_001",),
            plan_delta_refs=(),
            created_at=NOW,
        )
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Verify artifact_refs in dispatched task inputs include restored ref
        first_publish = mock_queue.publish.call_args_list[0]
        msg_data = json.loads(first_publish.args[1])
        task_inputs = msg_data["payload"]["inputs"]
        assert "art_001" in task_inputs["artifact_refs"]

    async def test_checkpoint_restored_event(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """CHECKPOINT_RESTORED event emitted on resume."""
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=2,
            completed_task_ids=(
                "task-run_impl-000-governance.define_done",
                "task-run_impl-001-development.develop",
            ),
            prior_outputs={},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        restored_events = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CHECKPOINT_RESTORED
        ]
        # Two emissions: one in execute_run, one in _execute_sequential
        assert len(restored_events) >= 1

    async def test_run_resumed_event_on_checkpoint_resume(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """RUN_RESUMED event (not RUN_STARTED) emitted when checkpoint exists."""
        mock_registry.get_latest_checkpoint.return_value = RunCheckpoint(
            run_id="run_impl",
            checkpoint_index=1,
            completed_task_ids=("task-run_impl-000-governance.define_done",),
            prior_outputs={},
            artifact_refs=(),
            plan_delta_refs=(),
            created_at=NOW,
        )
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_RESUMED in event_types
        assert EventType.RUN_STARTED not in event_types

    async def test_fresh_run_emits_started_not_resumed(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """Fresh run (no checkpoint) emits RUN_STARTED, not RUN_RESUMED."""
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_STARTED in event_types
        assert EventType.RUN_RESUMED not in event_types


# ---------------------------------------------------------------------------
# Time budget enforcement
# ---------------------------------------------------------------------------


class TestTimeBudget:
    """Time budget enforcement halts run when exhausted."""

    async def test_time_budget_exhausted(
        self, executor, mock_registry, mock_queue, impl_cycle, mock_event_bus
    ) -> None:
        """Run fails when time budget is exhausted."""
        import dataclasses

        budget_cycle = dataclasses.replace(impl_cycle, applied_defaults={"time_budget_seconds": 0})
        mock_registry.get_cycle.return_value = budget_cycle
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Run should fail due to time budget
        status_calls = mock_registry.update_run_status.call_args_list
        final_status = status_calls[-1].args[1]
        assert final_status == RunStatus.FAILED

    async def test_no_time_budget_no_enforcement(self, executor, mock_registry, mock_queue) -> None:
        """When time_budget_seconds is not set, no enforcement."""
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        status_calls = mock_registry.update_run_status.call_args_list
        final_status = status_calls[-1].args[1]
        assert final_status == RunStatus.COMPLETED

    async def test_time_budget_error_message(
        self, executor, mock_registry, mock_queue, impl_cycle, mock_event_bus
    ) -> None:
        """Error message includes time budget details."""
        import dataclasses

        budget_cycle = dataclasses.replace(impl_cycle, applied_defaults={"time_budget_seconds": 0})
        mock_registry.get_cycle.return_value = budget_cycle
        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        fail_events = [
            c for c in mock_event_bus.emit.call_args_list if c.args[0] == EventType.RUN_FAILED
        ]
        assert len(fail_events) == 1
        error_msg = fail_events[0].kwargs.get("payload", {}).get("error", "")
        assert "Time budget exhausted" in error_msg


# ---------------------------------------------------------------------------
# Paused state (BLOCKED outcome — Phase 3 full routing, Phase 2 tests _PausedError)
# ---------------------------------------------------------------------------


class TestPausedHandler:
    """_PausedError transitions run to PAUSED."""

    async def test_paused_error_transitions_to_paused(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """_PausedError in _execute_sequential → run PAUSED."""
        from adapters.cycles.dispatched_flow_executor import _PausedError

        with (
            patch.object(executor, "_execute_sequential", side_effect=_PausedError("blocked")),
            patch(
                "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Verify PAUSED status
        status_calls = mock_registry.update_run_status.call_args_list
        # First call: RUNNING, second call: safe_transition → PAUSED
        paused_calls = [c for c in status_calls if c.args[1] == RunStatus.PAUSED]
        assert len(paused_calls) >= 1

    async def test_paused_emits_run_paused_event(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        from adapters.cycles.dispatched_flow_executor import _PausedError

        with (
            patch.object(executor, "_execute_sequential", side_effect=_PausedError("blocked")),
            patch(
                "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_PAUSED in event_types


# ---------------------------------------------------------------------------
# Resume of an already-RUNNING run (#342)
# ---------------------------------------------------------------------------


class TestResumeOfAlreadyRunningRun:
    """#342: the resume/retry routes flip the run to RUNNING before enqueuing
    execution (#222/#256). execute_run must therefore skip its own RUNNING
    transition when the run already is — RUNNING → RUNNING is an illegal
    self-loop on every lifecycle-enforcing registry (postgres AND memory),
    so the unconditional call instantly failed every resumed run live."""

    def _wire_lifecycle_enforcement(self, mock_registry, initial_status: str) -> dict:
        """Make the mock registry enforce transitions exactly like the real ones."""
        from squadops.cycles.lifecycle import validate_run_transition

        state = {"status": initial_status}

        def _run(run_id: str = "run_impl") -> Run:
            return Run(
                run_id="run_impl",
                cycle_id="cyc_impl",
                run_number=1,
                status=state["status"],
                initiated_by="api",
                resolved_config_hash="hash",
                workload_type=WorkloadType.IMPLEMENTATION,
            )

        async def _update(run_id: str, status: RunStatus) -> Run:
            validate_run_transition(RunStatus(state["status"]), status)
            state["status"] = status.value
            return _run()

        mock_registry.get_run = AsyncMock(side_effect=_run)
        mock_registry.update_run_status = AsyncMock(side_effect=_update)
        mock_registry.append_artifact_refs.side_effect = lambda run_id, refs: _run()
        return state

    async def test_resumed_running_run_executes_and_completes(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """A run the resume route already flipped to RUNNING must execute to
        COMPLETED — not instantly FAIL on the RUNNING→RUNNING self-loop."""
        state = self._wire_lifecycle_enforcement(mock_registry, "running")

        with patch.object(executor, "_execute_sequential", new_callable=AsyncMock):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        assert state["status"] == "completed"
        event_types = [c.args[0] for c in mock_event_bus.emit.call_args_list]
        assert EventType.RUN_COMPLETED in event_types
        assert EventType.RUN_FAILED not in event_types

    async def test_queued_run_still_transitions_to_running_first(
        self, executor, mock_registry, mock_queue, mock_event_bus
    ) -> None:
        """The create path is unchanged: a QUEUED run still gets the executor's
        QUEUED→RUNNING transition before completing."""
        state = self._wire_lifecycle_enforcement(mock_registry, "queued")

        with patch.object(executor, "_execute_sequential", new_callable=AsyncMock):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        assert state["status"] == "completed"
        first_transition = mock_registry.update_run_status.call_args_list[0].args[1]
        assert first_transition == RunStatus.RUNNING


# ---------------------------------------------------------------------------
# SIP-0096 Phase 2 slice 1: verification-evidence recording to the ledger
# ---------------------------------------------------------------------------


class TestVerificationEvidenceRecording:
    """Each completed task's verification outputs are normalized into the run
    ledger at the dispatch seam and surface in the run_report integrity roll-up —
    the wiring that makes the Phase-1 aggregation non-inert."""

    def _run_report(self, mock_vault) -> str:
        for call in mock_vault.store.call_args_list:
            ref, content = call.args[0], call.args[1]
            if getattr(ref, "filename", "") == "run_report.md":
                return content.decode()
        raise AssertionError("run_report.md was not stored")

    async def test_passing_test_result_recorded_and_disclosed(
        self, executor, mock_registry, mock_queue, mock_vault
    ) -> None:
        """A passing test_result on each task makes the roll-up show real executed
        evidence — not the inert 'Executed: 0'."""

        def responder(env):
            return TaskResult(
                task_id=env["task_id"],
                status="SUCCEEDED",
                outputs={
                    "summary": "ok",
                    "artifacts": [],
                    "test_result": {"executed": True, "exit_code": 0, "tests_passed": True},
                },
            )

        mock_queue.reply_router.responder = responder

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        report = self._run_report(mock_vault)
        assert "## Verification Integrity" in report
        assert "Verdict: **accepted**" in report
        # 3 implementation tasks each carry a passing test_result → 3 tests_pass recorded.
        assert "Executed: 3 " in report

    async def test_not_executed_test_result_is_disclosed_not_dropped(
        self, executor, mock_registry, mock_queue, mock_vault
    ) -> None:
        """A not-executed test_result surfaces under 'Unverified (not executed)' —
        silence is disclosed through the choke point, never dropped (§6.6.3)."""

        def responder(env):
            return TaskResult(
                task_id=env["task_id"],
                status="SUCCEEDED",
                outputs={
                    "summary": "ok",
                    "artifacts": [],
                    "test_result": {"executed": False, "error": "ImportError: app"},
                },
            )

        mock_queue.reply_router.responder = responder

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        report = self._run_report(mock_vault)
        assert "### Unverified (not executed)" in report
        assert "tests_pass" in report
        assert "Executed: 0 " in report  # not-executed excluded from the executed count

    async def test_aborted_task_evidence_survives_the_abort(
        self, executor, mock_registry, mock_queue, mock_vault
    ) -> None:
        """A task that fails and aborts the run must still record its verification
        evidence. The abort path raises from inside dispatch_with_retry (before the
        normal recording line), so this is the #276-class failing evidence that
        would otherwise vanish — a failed run must read as honest red, not '0
        verified'."""

        def responder(env):
            return TaskResult(
                task_id=env["task_id"],
                status="FAILED",
                error="tests broke",
                outputs={"test_result": {"executed": True, "exit_code": 1, "tests_passed": False}},
            )

        mock_queue.reply_router.responder = responder

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Run failed, but the failing task's evidence reached the roll-up.
        status_calls = mock_registry.update_run_status.call_args_list
        assert status_calls[-1].args[1] == RunStatus.FAILED
        report = self._run_report(mock_vault)
        assert "## Verification Integrity" in report
        assert "Failed: tests_pass" in report
        assert "Executed: 1 " in report

    async def test_break_correction_records_failure_and_blocks_false_green(
        self, executor, mock_registry, mock_queue, mock_vault
    ) -> None:
        """The #376 leak: after a `patch` correction the executor advances
        (break_correction) with the ORIGINAL failed result. That failed evidence
        must still be recorded, and a COMPLETED run whose verdict is rejected must
        NOT print 'All tasks completed successfully' (§6.6.4 narrative override)."""
        failed = TaskResult(
            task_id="t",
            status="FAILED",
            error="build failed",
            outputs={"test_result": {"executed": True, "exit_code": 1, "tests_passed": False}},
        )
        with (
            patch.object(
                executor._task_dispatcher,
                "dispatch_with_retry",
                new_callable=AsyncMock,
                return_value=(False, failed),
            ),
            patch("adapters.cycles.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock),
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # Every task advanced on break_correction → run COMPLETED...
        assert mock_registry.update_run_status.call_args_list[-1].args[1] == RunStatus.COMPLETED
        report = self._run_report(mock_vault)
        # ...but the failed evidence was recorded and the narrative is honest.
        assert "Failed: tests_pass" in report
        assert "REJECTED" in report
        assert "All tasks completed successfully." not in report

    async def test_rerun_records_failed_attempt_then_supersedes_to_accepted(
        self, executor, mock_registry, mock_queue, mock_vault
    ) -> None:
        """#379 end-to-end at the recording seam: a task whose check FAILS then PASSES
        on re-dispatch (the ``continue`` path — a retry here, a #374 repair re-run in
        production) records BOTH attempts, stamped with the producing task id, and the
        verdict resolves to the FINAL state (accepted). Without recording the failed
        attempt the honest-history is lost; without subject-keyed supersession the run
        would be stuck ``rejected`` (the exact coupling #374 depends on).
        """
        dispatch_count = 0

        def fail_then_pass(env):
            nonlocal dispatch_count
            dispatch_count += 1
            # First dispatch of the first task fails its tests; the retry (2nd
            # dispatch) and every later task pass. env["task_id"] is stable across the
            # re-dispatch, so both records share the producing subject.
            failed = dispatch_count == 1
            return TaskResult(
                task_id=env["task_id"],
                status="FAILED" if failed else "SUCCEEDED",
                error="tests failed" if failed else None,
                outputs={
                    "summary": "x",
                    "artifacts": [],
                    "test_result": {
                        "executed": True,
                        "exit_code": 1 if failed else 0,
                        "tests_passed": not failed,
                    },
                },
            )

        mock_queue.reply_router.responder = fail_then_pass

        recorded: list = []
        real_record = RunLedger.record_check_result

        def _spy(self, result):
            recorded.append(result)
            real_record(self, result)

        with (
            patch.object(RunLedger, "record_check_result", _spy),
            patch("adapters.cycles.dispatched_flow_executor.asyncio.sleep", new_callable=AsyncMock),
        ):
            await executor.execute_run(cycle_id="cyc_impl", run_id="run_impl")

        # The failed attempt WAS recorded (my _route_outcome change fires on continue),
        # and it carries a producing subject so it can be superseded.
        tp = [r for r in recorded if r.check_id == "tests_pass"]
        failed_records = [r for r in tp if r.status == "failed"]
        passed_records = [r for r in tp if r.status == "passed"]
        assert failed_records, "the failed re-run attempt must be recorded, not dropped"
        assert all(r.subject for r in tp), "every recorded check must carry its subject"
        # The failed attempt and its passing re-run share one subject (same task).
        failed_subj = failed_records[0].subject
        assert any(r.subject == failed_subj for r in passed_records)

        # Final verdict reflects the recovered state — the superseded failure does not
        # pin it rejected.
        report = self._run_report(mock_vault)
        assert mock_registry.update_run_status.call_args_list[-1].args[1] == RunStatus.COMPLETED
        assert "Verdict: **accepted**" in report
        assert "Failed: tests_pass" not in report
