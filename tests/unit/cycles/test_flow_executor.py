"""Tests for InProcessFlowExecutor (adapters/cycles/in_process_flow_executor.py).

Covers sequential happy path, fail-fast, cancellation, artifact storage,
output chaining, gate pause/resume/rejection, port signature, and edge cases.

SIP-0066 Phases 2-7.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, call, patch

import pytest

from squadops.cycles.models import (
    AgentProfileEntry,
    ArtifactRef,
    Cycle,
    Gate,
    GateDecision,
    Run,
    RunStatus,
    SquadProfile,
    TaskFlowPolicy,
)
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    mock = AsyncMock()
    # Stub get_run to return a non-cancelled run by default
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
    return mock


@pytest.fixture
def mock_vault():
    mock = AsyncMock()
    # store returns the ref as-is (vault_uri would be populated in real impl)
    mock.store.side_effect = lambda ref, content: ref
    return mock


@pytest.fixture
def mock_orchestrator():
    mock = AsyncMock()
    # Default: all tasks succeed with artifacts
    mock.submit_task.return_value = TaskResult(
        task_id="task_001",
        status="SUCCEEDED",
        outputs={
            "summary": "stub output",
            "role": "strat",
            "artifacts": [
                {
                    "name": "output.md",
                    "content": "# Output",
                    "media_type": "text/markdown",
                    "type": "document",
                }
            ],
        },
    )
    return mock


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
            AgentProfileEntry(
                agent_id="data-agent", role="data", model="gpt-4", enabled=True
            ),
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
def executor(mock_registry, mock_vault, mock_orchestrator, mock_squad_profile, cycle, run):
    from adapters.cycles.in_process_flow_executor import InProcessFlowExecutor

    # Stub get_cycle and get_run
    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    return InProcessFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        orchestrator=mock_orchestrator,
        squad_profile=mock_squad_profile,
    )


# ===========================================================================
# Sequential happy path
# ===========================================================================


class TestSequentialHappyPath:
    """Sequential mode: 5 tasks execute in order, run completes."""

    async def test_sequential_happy_path(self, executor, mock_registry):
        """5 tasks execute; run transitions queued -> running -> completed."""
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        status_calls = mock_registry.update_run_status.call_args_list
        statuses = [c.args[1] for c in status_calls]
        assert statuses[0] == RunStatus.RUNNING
        assert statuses[-1] == RunStatus.COMPLETED

    async def test_sequential_submit_task_called_5_times(self, executor, mock_orchestrator):
        """Orchestrator.submit_task called once per pipeline step (5 total)."""
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        assert mock_orchestrator.submit_task.call_count == 5

    async def test_sequential_artifacts_stored(self, executor, mock_vault):
        """vault.store called for each task's artifacts (1 per task = 5 total)."""
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        assert mock_vault.store.call_count == 5

    async def test_sequential_artifact_refs_appended(self, executor, mock_registry):
        """registry.append_artifact_refs called once per step that produced artifacts."""
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        assert mock_registry.append_artifact_refs.call_count == 5


# ===========================================================================
# Fail-fast
# ===========================================================================


class TestFailFast:
    """Sequential mode fail-fast: first failure stops the pipeline."""

    async def test_sequential_fail_fast_on_first_failure(
        self, executor, mock_orchestrator, mock_registry
    ):
        """First task FAILED -> run transitions to failed, remaining skipped."""
        mock_orchestrator.submit_task.return_value = TaskResult(
            task_id="t1",
            status="FAILED",
            error="boom",
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # submit_task called only once (fail-fast)
        assert mock_orchestrator.submit_task.call_count == 1

        # Run transitioned to FAILED (via _safe_transition)
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses

    async def test_sequential_fail_fast_on_third_task(
        self, executor, mock_orchestrator, mock_registry
    ):
        """Tasks 1-2 succeed, task 3 fails -> submit_task called 3 times, run=failed."""
        call_num = 0

        async def submit_side_effect(envelope):
            nonlocal call_num
            call_num += 1
            if call_num == 3:
                return TaskResult(task_id="t3", status="FAILED", error="task 3 crash")
            return TaskResult(
                task_id=f"t{call_num}",
                status="SUCCEEDED",
                outputs={
                    "summary": "ok",
                    "role": "strat",
                    "artifacts": [
                        {
                            "name": "out.md",
                            "content": "# ok",
                            "media_type": "text/markdown",
                            "type": "document",
                        }
                    ],
                },
            )

        mock_orchestrator.submit_task.side_effect = submit_side_effect

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert mock_orchestrator.submit_task.call_count == 3
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ===========================================================================
# Cancellation
# ===========================================================================


class TestCancellation:
    """Run cancellation via local set and registry polling."""

    async def test_cancel_run_sets_local_and_registry(self, executor, mock_registry):
        """cancel_run() adds to local set and calls registry.cancel_run."""
        await executor.cancel_run("run_001")
        assert "run_001" in executor._cancelled
        mock_registry.cancel_run.assert_awaited_once_with("run_001")

    async def test_cancel_before_first_task(
        self, executor, mock_registry, mock_orchestrator
    ):
        """If get_run returns cancelled status, run transitions to cancelled, no tasks dispatched."""
        mock_registry.get_run.return_value = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="cancelled",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        mock_orchestrator.submit_task.assert_not_awaited()
        # Should attempt to transition to CANCELLED
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.CANCELLED in terminal_statuses

    async def test_cancel_mid_execution(
        self, executor, mock_registry, mock_orchestrator
    ):
        """After 2 successful tasks, registry returns cancelled -> remaining skipped."""
        # _is_cancelled is called before each task dispatch.
        # Each _is_cancelled call invokes get_run once.
        # Flow: get_cycle, get_run (initial load), update_run_status(RUNNING),
        #   then loop:  _is_cancelled->get_run, submit_task, ..., _is_cancelled->get_run
        # We need get_run to return non-cancelled for the first few calls,
        # then cancelled after 2 tasks have been dispatched.
        call_count = 0

        def get_run_side_effect(run_id):
            nonlocal call_count
            call_count += 1
            # First call: initial load in execute_run body
            # Calls 2-3: _is_cancelled checks before tasks 1 and 2 (non-cancelled)
            # Call 4+: _is_cancelled check before task 3 -> cancelled
            status = "cancelled" if call_count > 3 else "running"
            return Run(
                run_id=run_id,
                cycle_id="cyc_001",
                run_number=1,
                status=status,
                initiated_by="api",
                resolved_config_hash="hash",
            )

        mock_registry.get_run.side_effect = get_run_side_effect

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 2 tasks dispatched before cancellation detected
        assert mock_orchestrator.submit_task.call_count == 2

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.CANCELLED in terminal_statuses


# ===========================================================================
# Artifact storage
# ===========================================================================


class TestArtifactStorage:
    """Artifact ref creation and persistence."""

    async def test_no_duplicate_artifact_refs(self, executor, mock_registry):
        """Each append_artifact_refs call has only that step's new refs, not cumulative."""
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        for call_item in mock_registry.append_artifact_refs.call_args_list:
            refs_tuple = call_item.args[1]
            # Each call should have exactly 1 ref (one artifact per task in default mock)
            assert len(refs_tuple) == 1

    async def test_artifact_ref_has_metadata(self, executor, mock_vault):
        """ArtifactRef passed to vault.store has task_id and role in metadata."""
        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        for call_item in mock_vault.store.call_args_list:
            ref = call_item.args[0]
            assert isinstance(ref, ArtifactRef)
            assert "task_id" in ref.metadata
            assert "role" in ref.metadata
            assert ref.metadata["task_id"] is not None
            assert ref.metadata["role"] is not None


# ===========================================================================
# Chaining
# ===========================================================================


class TestOutputChaining:
    """Prior outputs are chained forward to downstream tasks.

    NOTE: The executor builds enriched envelopes via ``dataclasses.replace``
    whose ``inputs["prior_outputs"]`` value is the *same* mutable dict that is
    grown across loop iterations.  By the time we inspect call_args_list after
    execute_run returns, every captured envelope points at the fully-populated
    dict.  To observe the per-step snapshot we capture deep copies at call time
    via a ``side_effect`` wrapper.
    """

    @staticmethod
    def _capturing_side_effect(snapshots):
        """Return a side_effect that deep-copies each envelope's inputs."""
        import copy

        async def _capture(envelope):
            snapshots.append(copy.deepcopy(envelope.inputs))
            return TaskResult(
                task_id="task_001",
                status="SUCCEEDED",
                outputs={
                    "summary": "stub output",
                    "role": "strat",
                    "artifacts": [
                        {
                            "name": "output.md",
                            "content": "# Output",
                            "media_type": "text/markdown",
                            "type": "document",
                        }
                    ],
                },
            )

        return _capture

    async def test_prior_outputs_chained_to_downstream(
        self, executor, mock_orchestrator
    ):
        """Second task's envelope includes prior_outputs from the first task."""
        snapshots: list[dict] = []
        mock_orchestrator.submit_task.side_effect = self._capturing_side_effect(
            snapshots
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        assert len(snapshots) == 5

        # First task should have empty prior_outputs
        assert snapshots[0]["prior_outputs"] == {}

        # Second task should have prior_outputs from first task (strat only)
        assert len(snapshots[1]["prior_outputs"]) == 1
        assert "strat" in snapshots[1]["prior_outputs"]

    async def test_prior_outputs_keyed_by_role(self, executor, mock_orchestrator):
        """prior_outputs dict is keyed by role_id (strat, dev, qa, data, lead)."""
        snapshots: list[dict] = []
        mock_orchestrator.submit_task.side_effect = self._capturing_side_effect(
            snapshots
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # The last task (governance.review, role=lead) should have all 4 prior roles
        assert set(snapshots[4]["prior_outputs"].keys()) == {
            "strat",
            "dev",
            "qa",
            "data",
        }

        # The third task (qa.validate, role=qa) should have strat and dev
        assert set(snapshots[2]["prior_outputs"].keys()) == {"strat", "dev"}


# ===========================================================================
# Gate pause/resume
# ===========================================================================


class TestGatePauseResume:
    """Gate handling: pause, poll, resume/reject."""

    @pytest.fixture
    def gated_cycle(self):
        return Cycle(
            cycle_id="cyc_001",
            project_id="hello_squad",
            created_at=NOW,
            created_by="system",
            prd_ref="prd_ref_123",
            squad_profile_id="full-squad",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(
                mode="sequential",
                gates=(
                    Gate(
                        name="quality-review",
                        description="QA gate",
                        after_task_types=("strategy.analyze_prd",),
                    ),
                ),
            ),
            build_strategy="fresh",
        )

    @pytest.fixture
    def gated_executor(
        self,
        mock_registry,
        mock_vault,
        mock_orchestrator,
        mock_squad_profile,
        gated_cycle,
        run,
    ):
        from adapters.cycles.in_process_flow_executor import InProcessFlowExecutor

        mock_registry.get_cycle.return_value = gated_cycle
        mock_registry.get_run.return_value = run
        return InProcessFlowExecutor(
            cycle_registry=mock_registry,
            artifact_vault=mock_vault,
            orchestrator=mock_orchestrator,
            squad_profile=mock_squad_profile,
        )

    async def test_gate_pause_and_resume(
        self, gated_executor, mock_registry, mock_orchestrator
    ):
        """Gate after strategy.analyze_prd pauses run, approved decision resumes it."""
        # Track calls to get_run. The executor calls get_run:
        #   1. Initial load
        #   2-6. _is_cancelled checks (before each of 5 tasks)
        #   7. _handle_gate -> _is_cancelled -> get_run
        #   8+. _handle_gate poll loop -> get_run (returns gate decision)
        # We need the gate poll to eventually return an approved decision.
        poll_count = 0
        base_run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="running",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        def get_run_with_gate(run_id):
            nonlocal poll_count
            poll_count += 1
            # After enough calls, return a run with an approved gate decision
            # The gate poll loop: _is_cancelled calls get_run, then the loop body
            # calls get_run again. We approve after a couple of poll iterations.
            if poll_count >= 5:
                return Run(
                    run_id="run_001",
                    cycle_id="cyc_001",
                    run_number=1,
                    status="paused",
                    initiated_by="api",
                    resolved_config_hash="hash",
                    gate_decisions=(
                        GateDecision(
                            gate_name="quality-review",
                            decision="approved",
                            decided_by="op",
                            decided_at=NOW,
                        ),
                    ),
                )
            return base_run

        mock_registry.get_run.side_effect = get_run_with_gate

        with patch(
            "adapters.cycles.in_process_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await gated_executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # All 5 tasks should have been dispatched (gate didn't stop completion)
        assert mock_orchestrator.submit_task.call_count == 5

        # Run should end as completed
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses
        # Should have been paused at gate
        assert RunStatus.PAUSED in terminal_statuses

    async def test_gate_rejection_fails_run(
        self, gated_executor, mock_registry, mock_orchestrator
    ):
        """Gate with decision=rejected -> run transitions to failed."""
        poll_count = 0
        base_run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="running",
            initiated_by="api",
            resolved_config_hash="hash",
        )

        def get_run_with_rejection(run_id):
            nonlocal poll_count
            poll_count += 1
            if poll_count >= 5:
                return Run(
                    run_id="run_001",
                    cycle_id="cyc_001",
                    run_number=1,
                    status="paused",
                    initiated_by="api",
                    resolved_config_hash="hash",
                    gate_decisions=(
                        GateDecision(
                            gate_name="quality-review",
                            decision="rejected",
                            decided_by="op",
                            decided_at=NOW,
                            notes="Not ready",
                        ),
                    ),
                )
            return base_run

        mock_registry.get_run.side_effect = get_run_with_rejection

        with patch(
            "adapters.cycles.in_process_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await gated_executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Only 1 task dispatched (first step, then gate rejects)
        assert mock_orchestrator.submit_task.call_count == 1

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ===========================================================================
# Port signature
# ===========================================================================


class TestPortSignature:
    """Verify the execute_run signature matches SIP-0066 breaking change."""

    async def test_execute_run_accepts_new_signature(self, executor):
        """execute_run(cycle_id, run_id, profile_id) works without error."""
        await executor.execute_run(
            cycle_id="cyc_001", run_id="run_001", profile_id="full-squad"
        )


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases: empty artifacts, no outputs, etc."""

    async def test_empty_artifacts_no_vault_call(
        self, executor, mock_orchestrator, mock_vault
    ):
        """If task outputs have no 'artifacts' key, vault.store is not called."""
        mock_orchestrator.submit_task.return_value = TaskResult(
            task_id="task_001",
            status="SUCCEEDED",
            outputs={"summary": "done"},
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        mock_vault.store.assert_not_awaited()

    async def test_task_with_no_outputs(self, executor, mock_orchestrator, mock_vault):
        """TaskResult with outputs=None doesn't crash."""
        mock_orchestrator.submit_task.return_value = TaskResult(
            task_id="task_001",
            status="SUCCEEDED",
            outputs=None,
        )

        await executor.execute_run(cycle_id="cyc_001", run_id="run_001")
        mock_vault.store.assert_not_awaited()
        # Run should still complete successfully
