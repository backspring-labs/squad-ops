"""Tests for the SIP-0079 correction protocol, owned by ``CorrectionRunner``
since SIP-0097 slice 3 (renamed from test_correction_protocol.py).

Covers all 4 correction paths (continue, patch, rewind, abort),
plan delta storage, max_correction_attempts, correction task checkpointing,
and CORRECTION_INITIATED/DECIDED/COMPLETED event emission. Most tests drive
the protocol end-to-end through the executor (which composes the default
runner); ``TestCorrectionRunnerStandalone`` constructs the collaborator
directly, without a ``DispatchedFlowExecutor`` instance (SIP-0097 §9).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
from squadops.events.types import EventType
from squadops.tasks.models import TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    mock = AsyncMock()
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    mock.consume.return_value = []
    # SIP-0094: publishing a comms.task auto-delivers the agent reply via the
    # reply router (the executor no longer polls a reply queue).
    return reply_router.bind(mock)


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
            AgentProfileEntry(
                agent_id="data-agent",
                role="data",
                model="gpt-4",
                enabled=True,
            ),
            AgentProfileEntry(agent_id="max", role="lead", model="gpt-4", enabled=True),
        ),
        created_at=NOW,
    )
    mock.resolve_snapshot.return_value = (profile, "sha256:abc")
    return mock


@pytest.fixture
def mock_event_bus():
    return MagicMock()


@pytest.fixture
def cycle():
    return Cycle(
        cycle_id="cyc_001",
        project_id="hello_squad",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full",
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
def executor(
    mock_registry,
    mock_vault,
    mock_queue,
    mock_squad_profile,
    mock_event_bus,
    cycle,
    run,
):
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    # SIP-0097 slice 3: the event bus must be passed at construction — the
    # default CorrectionRunner captures it in __init__, so a post-hoc
    # `ex._cycle_event_bus = ...` assignment would not reach correction events.
    ex = DispatchedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
        reply_router=mock_queue.reply_router,
        event_bus=mock_event_bus,
    )
    return ex


def _script_replies(reply_router, script):
    """Drive the reply router from a list of (status, outputs, error) tuples.

    Each dispatch (in order) gets the next scripted reply, exactly as the old
    scripted consume side_effect did. After the script is exhausted, replies
    default to SUCCEEDED — same fallback as before.
    """
    idx = {"n": 0}

    def responder(env):
        i = idx["n"]
        idx["n"] += 1
        if i < len(script):
            status, outputs, error = script[i]
        else:
            status, outputs, error = ("SUCCEEDED", {"summary": "ok", "role": "strat"}, None)
        return TaskResult(
            task_id=env["task_id"],
            status=status,
            outputs=outputs,
            error=error,
        )

    reply_router.responder = responder


# ---------------------------------------------------------------------------
# Correction protocol: continue path
# ---------------------------------------------------------------------------


class TestCorrectionContinue:
    """Correction path 'continue': reset failures, proceed to next task."""

    async def test_continue_path_allows_remaining_tasks(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Semantic failure -> correction decides 'continue' -> remaining tasks run."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "continue",
            "role": "lead",
            "correction_path": "continue",
            "decision_rationale": "Non-critical failure",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Transient issue",
        }
        script = [
            # Task 1: semantic failure
            ("FAILED", semantic_outputs, "bad output"),
            # Correction: analyze_failure succeeds
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            # Correction: correction_decision succeeds with "continue"
            ("SUCCEEDED", correction_decision, None),
            # Tasks 2-5: succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (failed) + 2 (correction) + 4 (remaining) = 7
        assert mock_queue.publish.call_count == 7

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses


# ---------------------------------------------------------------------------
# Correction protocol: patch path
# ---------------------------------------------------------------------------


class TestCorrectionPatch:
    """Correction path 'patch': dispatch repair tasks, then proceed."""

    async def test_patch_dispatches_repair_tasks(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Patch path -> repair tasks dispatched, then remaining tasks proceed."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "Fix is localized",
            "affected_task_types": ["development.develop"],
            "classification": "work_product",
            "analysis_summary": "Output quality issue",
        }
        script = [
            # Task 1: semantic failure
            ("FAILED", semantic_outputs, "bad output"),
            # Correction: analyze_failure
            (
                "SUCCEEDED",
                {
                    "classification": "work_product",
                    "analysis_summary": "quality",
                    "role": "data",
                },
                None,
            ),
            # Correction: correction_decision -> patch
            ("SUCCEEDED", correction_decision, None),
            # Repair: development.repair
            ("SUCCEEDED", {"summary": "repaired", "role": "dev"}, None),
            # Repair: qa.validate_repair
            ("SUCCEEDED", {"summary": "validated", "role": "qa"}, None),
            # #374: a patch re-runs the ORIGINAL failed check (Task 1) — now passes
            ("SUCCEEDED", {"summary": "task1 re-run ok", "role": "dev"}, None),
            # Tasks 2-5: succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (failed) + 2 (correction) + 2 (repair) + 1 (#374 re-run of Task 1) + 4 (remaining) = 10
        assert mock_queue.publish.call_count == 10

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses

    async def test_patch_rerun_never_converges_fails_run(self, executor, mock_queue, mock_registry):
        """#374: a patch whose re-run never passes must FAIL the run, not false-complete.

        Catches the pre-#374 false-green (#276 class): a ``patch`` advanced
        unconditionally, so a task whose repair never actually fixed the check still
        reached COMPLETED. Now a ``patch`` re-runs the original check; a persistent
        failure re-enters correction until ``max_correction_attempts`` exhausts,
        raising ``_ExecutionError`` → the run is FAILED, never COMPLETED.
        """
        import dataclasses

        cycle_2 = dataclasses.replace(
            mock_registry.get_cycle.return_value,
            applied_defaults={"max_correction_attempts": 2},
        )
        mock_registry.get_cycle.return_value = cycle_2

        patch_decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "Fix is localized",
            "affected_task_types": ["development.develop"],
            "classification": "work_product",
            "analysis_summary": "Output quality issue",
        }

        def responder(env):
            tid = env["task_id"]
            if "correction_decision" in tid:
                return TaskResult(
                    task_id=tid, status="SUCCEEDED", outputs=patch_decision, error=None
                )
            if tid.startswith("corr-") or tid.startswith("repair-"):
                # analyze_failure / repair / validate_repair all succeed
                return TaskResult(
                    task_id=tid,
                    status="SUCCEEDED",
                    outputs={
                        "summary": "ok",
                        "role": "data",
                        "classification": "work_product",
                        "analysis_summary": "quality",
                    },
                    error=None,
                )
            # An original plan task: its check keeps failing on every re-run.
            return TaskResult(
                task_id=tid,
                status="FAILED",
                outputs={"outcome_class": TaskOutcome.SEMANTIC_FAILURE, "role": "dev"},
                error="check still failing",
            )

        mock_queue.reply_router.responder = responder

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        terminal_statuses = [c.args[1] for c in mock_registry.update_run_status.call_args_list]
        # The #374 guarantee: a non-converging repair fails honestly, never false-green.
        assert RunStatus.FAILED in terminal_statuses
        assert RunStatus.COMPLETED not in terminal_statuses
        # Proof the check was actually re-run (not advanced-on-first-patch): the old
        # behavior was exactly 5 publishes (1 fail + 2 correction + 2 repair) then a
        # false-advance; re-running past the first patch exceeds that.
        assert mock_queue.publish.call_count > 5


# ---------------------------------------------------------------------------
# Correction/repair task artifact persistence (silent-drop fix)
# ---------------------------------------------------------------------------


class TestCorrectionTaskArtifactStorage:
    """Until this fix landed, the correction-task and repair-task success
    branches called `_checkpoint_correction_task` directly — which only
    snapshots existing `all_artifact_refs` into a checkpoint and does NOT
    persist new artifacts from the task's outputs. Cycles 4b and 6 both
    showed the symptom: builder.assemble_repair runs, produces a
    qa_handoff.md in its outputs, the executor checkpoints completion,
    and the qa_handoff.md never reaches the artifact registry — the run
    marks 'completed' while violating its own contract."""

    async def test_helper_stores_each_artifact_via_vault(self, executor, mock_vault):
        """Unit-level: the helper iterates outputs.artifacts and stores each."""
        from squadops.cycles.models import Cycle, TaskFlowPolicy
        from squadops.tasks.models import TaskEnvelope, TaskResult

        cycle = Cycle(
            cycle_id="cyc_x",
            project_id="proj",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
            squad_profile_snapshot_ref="ref",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
        envelope = TaskEnvelope(
            task_id="repair-1",
            agent_id="bob",
            cycle_id="cyc_x",
            pulse_id="p",
            project_id="proj",
            task_type="builder.assemble_repair",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={},
            metadata={"role": "builder"},
        )
        result = TaskResult(
            task_id="repair-1",
            status="SUCCEEDED",
            outputs={
                "artifacts": [
                    {
                        "name": "qa_handoff.md",
                        "content": "## How to Run Backend\n...",
                        "media_type": "text/markdown",
                        "type": "document",
                    },
                    {
                        "name": "requirements.txt",
                        "content": "fastapi\nuvicorn\n",
                        "media_type": "text/plain",
                        "type": "config",
                    },
                ],
            },
        )

        all_refs: list[str] = []
        stored: list = []
        await executor._correction_runner._store_correction_task_artifacts(
            result, envelope, cycle, "run_x", all_refs, stored
        )

        # Both artifacts hit the vault.
        assert mock_vault.store.call_count == 2
        stored_filenames = {call.args[0].filename for call in mock_vault.store.call_args_list}
        assert stored_filenames == {"qa_handoff.md", "requirements.txt"}

        # all_artifact_refs and stored_artifacts both got the new refs.
        assert len(all_refs) == 2
        assert len(stored) == 2
        # producing_task_type metadata pinned so triage can attribute the
        # artifact to the repair pass, not the original failed task.
        first_ref = mock_vault.store.call_args_list[0].args[0]
        assert first_ref.metadata.get("producing_task_type") == "builder.assemble_repair"

    async def test_helper_no_op_when_no_artifacts(self, executor, mock_vault):
        """Repair tasks that fail or produce no artifacts must not crash
        and must not call the vault. Defensive check on the absence
        path."""
        from squadops.cycles.models import Cycle, TaskFlowPolicy
        from squadops.tasks.models import TaskEnvelope, TaskResult

        cycle = Cycle(
            cycle_id="cyc_x",
            project_id="proj",
            created_at=NOW,
            created_by="system",
            prd_ref="prd",
            squad_profile_id="full",
            squad_profile_snapshot_ref="ref",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )
        envelope = TaskEnvelope(
            task_id="corr-1",
            agent_id="data-agent",
            cycle_id="cyc_x",
            pulse_id="p",
            project_id="proj",
            task_type="data.analyze_failure",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={},
            metadata={"role": "data"},
        )
        result = TaskResult(
            task_id="corr-1",
            status="SUCCEEDED",
            outputs={"summary": "no artifacts"},  # no "artifacts" key
        )

        all_refs: list[str] = []
        stored: list = []
        await executor._correction_runner._store_correction_task_artifacts(
            result, envelope, cycle, "run_x", all_refs, stored
        )

        assert mock_vault.store.call_count == 0
        assert all_refs == []
        assert stored == []

    async def test_repair_artifacts_reach_vault_in_patch_flow(
        self, executor, mock_queue, mock_registry, mock_vault, mock_event_bus
    ):
        """End-to-end through the patch path: a builder.assemble failure
        triggers the correction protocol; the repair task's qa_handoff.md
        artifact MUST land in the vault. Direct regression guard for the
        cycle-4b / cycle-6 silent-drop pattern."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "builder",
        }
        correction_decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "Missing section",
            "affected_task_types": ["builder.assemble"],
            "classification": "work_product",
            "analysis_summary": "qa_handoff.md missing required sections",
        }
        # The repair output that previously got dropped.
        repaired_qa_handoff = {
            "summary": "repaired",
            "role": "builder",
            "artifacts": [
                {
                    "name": "qa_handoff.md",
                    "content": "## How to Test\n...\n## Expected Behavior\n...\n",
                    "media_type": "text/markdown",
                    "type": "document",
                },
            ],
        }
        script = [
            ("FAILED", semantic_outputs, "missing sections"),
            (
                "SUCCEEDED",
                {
                    "classification": "work_product",
                    "analysis_summary": "qa_handoff incomplete",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
            ("SUCCEEDED", repaired_qa_handoff, None),
            ("SUCCEEDED", {"summary": "validated", "role": "qa"}, None),
            # remaining tasks just succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Look for qa_handoff.md among the stored artifacts. Plan_deltas
        # also hit the vault (correctly) — filter to the artifact under test.
        stored_filenames = [call.args[0].filename for call in mock_vault.store.call_args_list]
        assert "qa_handoff.md" in stored_filenames, (
            f"qa_handoff.md missing from vault stores; got: {stored_filenames}"
        )

        # And the run completed successfully (the storage doesn't break
        # the existing checkpoint flow).
        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses

    async def test_validate_repair_envelope_carries_repair_artifacts_in_prior_outputs(
        self, executor, mock_queue, mock_registry, mock_vault, mock_event_bus
    ):
        """qa.validate_repair must see the upstream repair task's artifacts.

        Cycle 8 regression: the executor previously stripped `artifacts`
        from the repair task's outputs when collecting prior_outputs, so
        Eve only saw the role-keyed one-line summary and rendered
        Verdict: FAIL even when the repaired file was already in the
        registry. This pins the executor side of the fix — the
        downstream prompt formatting is covered by repair handler tests."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "Localized fix",
            "affected_task_types": ["development.develop"],
            "classification": "work_product",
            "analysis_summary": "Output quality issue",
        }
        repair_with_artifacts = {
            "summary": "[dev] repaired",
            "role": "dev",
            "artifacts": [
                {
                    "name": "frontend/src/components/RunDetail.jsx",
                    "content": "import React from 'react';\nexport default function RunDetail() {}\n",
                    "media_type": "text/javascript",
                    "type": "source",
                },
            ],
        }
        script = [
            ("FAILED", semantic_outputs, "missing component"),
            (
                "SUCCEEDED",
                {
                    "classification": "work_product",
                    "analysis_summary": "missing RunDetail.jsx",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
            ("SUCCEEDED", repair_with_artifacts, None),
            ("SUCCEEDED", {"summary": "validated", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        publishes = [_published_envelope(c) for c in mock_queue.publish.call_args_list]
        validate = next(p for p in publishes if p["task_type"] == "qa.validate_repair")

        prior = validate["inputs"]["prior_outputs"]
        dev_block = prior.get("dev")
        assert dev_block is not None, (
            f"dev repair output missing from prior_outputs; got keys: {list(prior.keys())}"
        )
        artifacts = dev_block.get("artifacts")
        assert artifacts, (
            "validate_repair envelope must carry repair artifacts; "
            "without this Eve cannot verify the repair against acceptance criteria"
        )
        names = [a.get("name") for a in artifacts]
        assert "frontend/src/components/RunDetail.jsx" in names
        # Content travels too — Eve needs to read it, not just see the filename.
        assert any(
            "export default function RunDetail" in (a.get("content") or "") for a in artifacts
        )


# ---------------------------------------------------------------------------
# Correction protocol: abort and rewind paths
# ---------------------------------------------------------------------------


class TestCorrectionTerminalPaths:
    """Abort and rewind paths both terminate the run as FAILED."""

    @pytest.mark.parametrize(
        "correction_path,rationale",
        [
            ("abort", "Unrecoverable"),
            ("rewind", "Need to go back"),
        ],
    )
    async def test_terminal_path_fails_run(
        self,
        executor,
        mock_queue,
        mock_registry,
        mock_event_bus,
        correction_path,
        rationale,
    ):
        """Both abort and rewind -> run transitions to FAILED."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": correction_path,
            "role": "lead",
            "correction_path": correction_path,
            "decision_rationale": rationale,
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Issue found",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "issue",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (task) + 2 (correction) = 3
        assert mock_queue.publish.call_count == 3

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ---------------------------------------------------------------------------
# max_correction_attempts
# ---------------------------------------------------------------------------


class TestMaxCorrectionAttempts:
    """max_correction_attempts enforced.

    SIP-0100 Task 0.4 baseline: this class is the characterization of the CURRENT correction
    counting — there is ONE shared ``correction_counter`` and every correction attempt consumes
    it (exhaustion raises at ``max_correction_attempts``). SIP-0100 Task 3.4 adds a *separate*
    bounded contract-compliance counter (plan D6); it MUST keep this behavior green for
    implementation-caused corrections while routing compliance violations to the new counter.
    """

    async def test_max_corrections_exhausted(self, executor, mock_queue, mock_registry, cycle):
        import dataclasses

        cycle_1 = dataclasses.replace(cycle, applied_defaults={"max_correction_attempts": 1})
        mock_registry.get_cycle.return_value = cycle_1

        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "continue",
            "role": "lead",
            "correction_path": "continue",
            "decision_rationale": "Try again",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "transient",
        }
        semantic_outputs_2 = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "dev",
        }
        script = [
            # Task 1: semantic failure
            ("FAILED", semantic_outputs, "bad"),
            # Correction 1: analyze + decide -> continue
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
            # Task 2: also semantic failure
            ("FAILED", semantic_outputs_2, "bad again"),
            # max_correction_attempts=1 exhausted -> abort
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (fail) + 2 (correction) + 1 (task 2 fail) = 4
        assert mock_queue.publish.call_count == 4

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.FAILED in terminal_statuses


# ---------------------------------------------------------------------------
# Plan delta stored as artifact
# ---------------------------------------------------------------------------


class TestPlanDelta:
    """Plan delta stored as artifact after correction."""

    async def test_plan_delta_stored(
        self, executor, mock_queue, mock_registry, mock_vault, mock_event_bus
    ):
        """Correction protocol stores a plan_delta artifact whose
        classification/analysis_summary come from data.analyze_failure
        and decision_rationale comes from governance.correction_decision.

        Regression for issue #95: the lead's correction_decision handler does
        not echo back classification/analysis_summary, so previously the
        executor's reused `correction_outputs` variable lost those fields by
        the time the PlanDelta was constructed. Each handler's outputs must be
        sourced from the right step.
        """
        import json

        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        # Mirrors GovernanceCorrectionDecisionHandler outputs in prod:
        # NO classification or analysis_summary keys.
        correction_decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "Cannot fix",
            "affected_task_types": [],
        }
        analyze_failure = {
            "classification": "work_product",
            "analysis_summary": "Bob produced output without qa_handoff.md",
            "contributing_factors": ["missing required deployment file"],
            "role": "data",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            ("SUCCEEDED", analyze_failure, None),
            ("SUCCEEDED", correction_decision, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        store_calls = mock_vault.store.call_args_list
        delta_stores = [c for c in store_calls if c.args[0].artifact_type == "plan_delta"]
        assert len(delta_stores) == 1

        delta_ref, delta_content = delta_stores[0].args
        assert "plan_delta" in delta_ref.filename

        delta = json.loads(delta_content.decode())
        assert delta["failure_classification"] == "work_product"
        assert delta["analysis_summary"] == "Bob produced output without qa_handoff.md"
        assert delta["decision_rationale"] == "Cannot fix"
        assert delta["correction_path"] == "abort"
        # SIP-0092 M2 → M3 gate diagnostic — must default to "none" when
        # the correction-decision handler doesn't surface a candidate.
        assert delta["structural_plan_change_candidate"] == "none"
        assert delta["structural_plan_change_rationale"] == ""

    async def test_plan_delta_carries_structural_change_candidate(
        self, executor, mock_queue, mock_registry, mock_vault, mock_event_bus
    ):
        """SIP-0092 M2 → M3 gate diagnostic: when the correction-decision
        handler emits `structural_plan_change_candidate`, the field
        must travel into the persisted plan_delta artifact so gate-evidence
        aggregation can count cycles where the lead would have wanted a
        plan change if M3 were available."""
        import json

        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "Localized fix",
            "affected_task_types": ["development.develop"],
            "structural_plan_change_candidate": "add_task",
            "structural_plan_change_rationale": "Need a separate join/leave test task",
        }
        analyze_failure = {
            "classification": "work_product",
            "analysis_summary": "Coverage gap on join/leave endpoints",
            "role": "data",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            ("SUCCEEDED", analyze_failure, None),
            ("SUCCEEDED", correction_decision, None),
            # repair tasks (development.correction_repair, qa.validate_repair)
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            # remaining tasks
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        delta_stores = [
            c for c in mock_vault.store.call_args_list if c.args[0].artifact_type == "plan_delta"
        ]
        assert len(delta_stores) == 1
        delta = json.loads(delta_stores[0].args[1].decode())
        assert delta["structural_plan_change_candidate"] == "add_task"
        assert "join/leave" in delta["structural_plan_change_rationale"]


# ---------------------------------------------------------------------------
# Correction tasks checkpoint on success
# ---------------------------------------------------------------------------


class TestCorrectionCheckpoints:
    """Correction tasks checkpoint on success."""

    async def test_successful_correction_tasks_checkpointed(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Successful correction tasks trigger checkpoint saves."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "Done",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "N/A",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            # analyze_failure succeeds -> checkpoint
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            # correction_decision succeeds -> checkpoint
            ("SUCCEEDED", correction_decision, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 2 successful correction tasks -> 2 checkpoint saves
        assert mock_registry.save_checkpoint.call_count == 2

    async def test_failed_correction_task_not_checkpointed(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """Failed correction tasks do NOT trigger checkpoint saves."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            # analyze_failure fails
            ("FAILED", None, "corr fail"),
            # correction_decision fails
            ("FAILED", None, "corr fail"),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 0 successful tasks -> 0 checkpoints
        assert mock_registry.save_checkpoint.call_count == 0


# ---------------------------------------------------------------------------
# Correction events
# ---------------------------------------------------------------------------


class TestCorrectionEvents:
    """CORRECTION_INITIATED/DECIDED/COMPLETED events emitted."""

    async def test_correction_events_emitted_in_order(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """All 3 correction events emitted in INITIATED < DECIDED < COMPLETED order."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "Done",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "N/A",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        emit_calls = mock_event_bus.emit.call_args_list
        event_types = [c.args[0] for c in emit_calls]

        assert EventType.CORRECTION_INITIATED in event_types
        assert EventType.CORRECTION_DECIDED in event_types
        assert EventType.CORRECTION_COMPLETED in event_types

        # Verify order: INITIATED before DECIDED before COMPLETED
        init_idx = event_types.index(EventType.CORRECTION_INITIATED)
        decided_idx = event_types.index(EventType.CORRECTION_DECIDED)
        completed_idx = event_types.index(EventType.CORRECTION_COMPLETED)
        assert init_idx < decided_idx < completed_idx

    async def test_correction_decided_carries_path(
        self, executor, mock_queue, mock_registry, mock_event_bus
    ):
        """CORRECTION_DECIDED event payload contains correction_path."""
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        correction_decision = {
            "summary": "continue",
            "role": "lead",
            "correction_path": "continue",
            "decision_rationale": "OK",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "Fine",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {
                    "classification": "execution",
                    "analysis_summary": "ok",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", correction_decision, None),
            # Remaining 4 tasks succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # Find CORRECTION_DECIDED emit
        decided_calls = [
            c
            for c in mock_event_bus.emit.call_args_list
            if c.args[0] == EventType.CORRECTION_DECIDED
        ]
        assert len(decided_calls) == 1
        payload = decided_calls[0].kwargs.get("payload", {})
        assert payload["correction_path"] == "continue"


# ---------------------------------------------------------------------------
# Issue #110: correction & repair tasks must propagate squad-profile model
# ---------------------------------------------------------------------------


def _published_envelope(call) -> dict:
    """Decode a mock_queue.publish call into the inner TaskEnvelope dict."""
    return json.loads(call.args[1])["payload"]


class TestCorrectionModelResolution:
    """Issue #110: correction-loop envelopes carry profile-resolved model.

    Without this, ``inputs["agent_model"]`` is absent and the agent falls
    back to the container's instance default — silently bypassing the cycle's
    squad profile. Observed in cyc_d1c1a259c983 where data.analyze_failure
    ran on qwen2.5:3b-instruct under a profile that pinned all roles to
    qwen3.6:27b.
    """

    @pytest.fixture
    def model_diverse_profile(self):
        """Profile where each role has a distinctive model string."""
        from squadops.cycles.models import SquadProfile

        return SquadProfile(
            profile_id="diverse",
            name="Diverse",
            description="distinct per-role models",
            version=1,
            agents=(
                AgentProfileEntry(
                    agent_id="strat-a", role="strat", model="model-strat", enabled=True
                ),
                AgentProfileEntry(
                    agent_id="dev-a",
                    role="dev",
                    model="model-dev",
                    enabled=True,
                    config_overrides={"temperature": 0.42},
                ),
                AgentProfileEntry(agent_id="qa-a", role="qa", model="model-qa", enabled=True),
                AgentProfileEntry(agent_id="data-a", role="data", model="model-data", enabled=True),
                AgentProfileEntry(agent_id="lead-a", role="lead", model="model-lead", enabled=True),
            ),
            created_at=NOW,
        )

    async def test_correction_envelopes_carry_profile_model(
        self,
        executor,
        mock_queue,
        mock_squad_profile,
        model_diverse_profile,
    ):
        """data.analyze_failure + governance.correction_decision get role-specific model."""
        mock_squad_profile.resolve_snapshot.return_value = (
            model_diverse_profile,
            "sha256:diverse",
        )
        semantic_outputs = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "strat",
        }
        decision = {
            "summary": "abort",
            "role": "lead",
            "correction_path": "abort",
            "decision_rationale": "halt",
            "affected_task_types": [],
            "classification": "execution",
            "analysis_summary": "halt",
        }
        script = [
            ("FAILED", semantic_outputs, "bad"),
            (
                "SUCCEEDED",
                {"classification": "execution", "analysis_summary": "x", "role": "data"},
                None,
            ),
            ("SUCCEEDED", decision, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        publishes = [_published_envelope(c) for c in mock_queue.publish.call_args_list]
        analyze = next(p for p in publishes if p["task_type"] == "data.analyze_failure")
        decide = next(p for p in publishes if p["task_type"] == "governance.correction_decision")

        assert analyze["agent_id"] == "data-a"
        assert analyze["inputs"]["agent_model"] == "model-data"
        assert decide["agent_id"] == "lead-a"
        assert decide["inputs"]["agent_model"] == "model-lead"

    async def test_repair_envelopes_carry_profile_model_and_overrides(
        self,
        executor,
        mock_queue,
        mock_squad_profile,
        model_diverse_profile,
    ):
        """Patch-path repair tasks get the repaired role's model + config_overrides."""
        mock_squad_profile.resolve_snapshot.return_value = (
            model_diverse_profile,
            "sha256:diverse",
        )
        # Trigger correction on a development.develop task so the patch path
        # routes repair to the dev role (which has config_overrides set).
        dev_failure = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "dev",
        }
        decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "localized fix",
            "affected_task_types": ["development.develop"],
            "classification": "work_product",
            "analysis_summary": "code issue",
        }
        script = [
            # Task 0 (strat) succeeds, task 1 (dev) fails.
            ("SUCCEEDED", {"summary": "framed", "role": "strat"}, None),
            ("FAILED", dev_failure, "bad code"),
            (
                "SUCCEEDED",
                {"classification": "work_product", "analysis_summary": "x", "role": "data"},
                None,
            ),
            ("SUCCEEDED", decision, None),
            # Repair tasks + remaining task plan succeed.
            ("SUCCEEDED", {"summary": "repaired", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "validated", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with patch(
            "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        publishes = [_published_envelope(c) for c in mock_queue.publish.call_args_list]
        repair = next(
            p for p in publishes if p["task_id"].startswith("repair-") and p["agent_id"] == "dev-a"
        )

        assert repair["inputs"]["agent_model"] == "model-dev"
        assert repair["inputs"]["agent_config_overrides"] == {"temperature": 0.42}

    async def test_repair_envelopes_carry_failed_task_contract(
        self,
        executor,
        mock_queue,
        mock_squad_profile,
        model_diverse_profile,
    ):
        """Patch-path repair envelopes plumb the failed task's contract.

        Cycle 7 (run_8b0805798d71) showed corrections firing but the repair
        agents producing a generic ``repair_output.md`` instead of the
        ``qa_handoff.md`` the original task was specced to produce. Root
        cause: the repair envelope only carried PRD + failure_evidence,
        not ``expected_artifacts`` or ``acceptance_criteria``. With those
        plumbed through, downstream prompt-building can ground the LLM in
        what to actually emit.
        """
        from squadops.tasks.models import TaskEnvelope

        mock_squad_profile.resolve_snapshot.return_value = (
            model_diverse_profile,
            "sha256:diverse",
        )

        # Wrap generate_task_plan so the failed task carries a real plan
        # contract. (The static plan generator only sets these when an
        # ImplementationPlan is supplied — the path under test here.)
        import adapters.cycles.dispatched_flow_executor as exec_mod
        from squadops.cycles.task_plan import generate_task_plan as real_gen

        def _gen_with_contract(*args, **kwargs):
            envelopes = real_gen(*args, **kwargs)
            tagged = []
            for env in envelopes:
                # The default cycle plan uses development.design as the
                # dev step (not development.develop, which is plan-driven).
                if env.task_type == "development.design":
                    new_inputs = {
                        **env.inputs,
                        "subtask_focus": "QA handoff packaging",
                        "subtask_description": "Assemble qa_handoff.md",
                        "expected_artifacts": ["qa_handoff.md", "backend/requirements.txt"],
                        "acceptance_criteria": [
                            "qa_handoff.md must contain '## How to Test'",
                            "qa_handoff.md must contain '## Expected Behavior'",
                        ],
                    }
                    tagged.append(
                        TaskEnvelope(
                            task_id=env.task_id,
                            agent_id=env.agent_id,
                            cycle_id=env.cycle_id,
                            pulse_id=env.pulse_id,
                            project_id=env.project_id,
                            task_type=env.task_type,
                            correlation_id=env.correlation_id,
                            causation_id=env.causation_id,
                            trace_id=env.trace_id,
                            span_id=env.span_id,
                            inputs=new_inputs,
                            metadata=env.metadata,
                        )
                    )
                else:
                    tagged.append(env)
            return tagged

        dev_failure = {
            "outcome_class": TaskOutcome.SEMANTIC_FAILURE,
            "role": "dev",
        }
        decision = {
            "summary": "patch",
            "role": "lead",
            "correction_path": "patch",
            "decision_rationale": "localized fix",
            "affected_task_types": ["development.design"],
            "classification": "work_product",
            "analysis_summary": "Missing required headings",
        }
        script = [
            ("SUCCEEDED", {"summary": "framed", "role": "strat"}, None),
            ("FAILED", dev_failure, "missing headings"),
            (
                "SUCCEEDED",
                {
                    "classification": "work_product",
                    "analysis_summary": "Missing '## How to Test'",
                    "role": "data",
                },
                None,
            ),
            ("SUCCEEDED", decision, None),
            ("SUCCEEDED", {"summary": "repaired", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "validated", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        _script_replies(mock_queue.reply_router, script)

        with (
            patch.object(exec_mod, "generate_task_plan", _gen_with_contract),
            patch(
                "adapters.cycles.dispatched_flow_executor.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        publishes = [_published_envelope(c) for c in mock_queue.publish.call_args_list]
        repair = next(p for p in publishes if p["task_id"].startswith("repair-"))

        inputs = repair["inputs"]
        assert inputs["failed_task_type"] == "development.design"
        assert inputs["expected_artifacts"] == [
            "qa_handoff.md",
            "backend/requirements.txt",
        ]
        assert any("How to Test" in c for c in inputs["acceptance_criteria"])
        assert inputs["subtask_focus"] == "QA handoff packaging"
        assert inputs["failure_analysis"]["analysis_summary"] == "Missing '## How to Test'"
        assert inputs["correction_decision"]["correction_path"] == "patch"


# ---------------------------------------------------------------------------
# Standalone construction (SIP-0097 §9): the collaborator is instantiable and
# testable without a DispatchedFlowExecutor instance
# ---------------------------------------------------------------------------


class TestCorrectionRunnerStandalone:
    """Drive run_correction_protocol on a directly-constructed CorrectionRunner
    with scripted callables — no executor anywhere."""

    def _make_runner(self, responder, vault=None, registry=None, bus=None):
        """Build a CorrectionRunner whose dispatch callable answers via
        ``responder(envelope) -> TaskResult`` and whose store_artifact
        callable records what would be persisted."""
        from adapters.cycles.correction_runner import CorrectionRunner
        from squadops.cycles.models import ArtifactRef

        registry = registry or AsyncMock()
        vault = vault or AsyncMock()
        vault.store.side_effect = lambda ref, _content: ref
        bus = bus or MagicMock()

        class _PassthroughDispatcher:
            """Minimal TaskDispatcher stand-in: routes dispatch_task through
            the test's responder, never creates Prefect task_runs (SIP-0097
            slice 5 — the runner takes the dispatcher itself, not callables)."""

            async def dispatch_task(self, envelope, run_id, **_kwargs):
                return responder(envelope)

            async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
                return None

        async def store_artifact(art, cycle, run_id, envelope, producing_task_type=None):
            content = art.get("content", "").encode()
            ref = ArtifactRef(
                artifact_id=f"art_{envelope.task_id}",
                project_id=cycle.project_id,
                artifact_type=art.get("type", "document"),
                filename=art["name"],
                content_hash="h",
                size_bytes=len(content),
                media_type=art.get("media_type", "text/markdown"),
                created_at=NOW,
                cycle_id=cycle.cycle_id,
                run_id=run_id,
            )
            return await vault.store(ref, content)

        runner = CorrectionRunner(
            cycle_registry=registry,
            artifact_vault=vault,
            event_bus=bus,
            task_dispatcher=_PassthroughDispatcher(),
            store_artifact=store_artifact,
        )
        return runner, registry, vault, bus

    def _failed_envelope(self):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task_failed",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="development.implement",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={},
            metadata={"role": "dev"},
        )

    async def test_analysis_fields_survive_to_plan_delta(self, cycle):
        """Issue #95 regression, executor-free: the analyzer's classification
        and analysis_summary must reach the PlanDelta even though the
        subsequent governance.correction_decision step doesn't carry them."""

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "classification": "work_product",
                        "analysis_summary": "missing acceptance section",
                    },
                )
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "retry remaining",
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, vault, _bus = self._make_runner(responder)
        plan_delta_refs: list[str] = []

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=plan_delta_refs,
        )

        assert protocol_result.correction_path == "continue"
        assert len(plan_delta_refs) == 1
        delta_calls = [
            c for c in vault.store.call_args_list if c.args[0].artifact_type == "plan_delta"
        ]
        assert len(delta_calls) == 1
        delta = json.loads(delta_calls[0].args[1])
        assert delta["failure_classification"] == "work_product"
        assert delta["analysis_summary"] == "missing acceptance section"
        assert delta["correction_path"] == "continue"

    async def test_missing_decision_defaults_to_abort(self, cycle):
        """Edge case: a decision step that returns no correction_path must
        yield "abort" (never a silent continue) — and still emit the full
        CORRECTION_INITIATED → DECIDED → COMPLETED lifecycle."""

        def responder(envelope):
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, bus = self._make_runner(responder)

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert protocol_result.correction_path == "abort"
        emitted = [c.args[0] for c in bus.emit.call_args_list]
        assert EventType.CORRECTION_INITIATED in emitted
        assert EventType.CORRECTION_DECIDED in emitted
        assert EventType.CORRECTION_COMPLETED in emitted

    async def test_failed_step_emits_task_failed_and_skips_checkpoint(self, cycle):
        """Error path: a correction step that FAILs must emit TASK_FAILED and
        must NOT be checkpointed as completed (only succeeded steps are)."""

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                return TaskResult(
                    task_id=envelope.task_id, status="FAILED", error="analyzer crashed"
                )
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"correction_path": "continue"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, registry, _vault, bus = self._make_runner(responder)
        completed: list[str] = []

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=completed,
            plan_delta_refs=[],
        )

        failed_events = [
            c for c in bus.emit.call_args_list if c.args and c.args[0] == EventType.TASK_FAILED
        ]
        assert len(failed_events) == 1
        assert failed_events[0].kwargs["payload"]["error"] == "analyzer crashed"
        # The failed analyzer step is not in completed_task_ids; the
        # succeeding decision step is.
        assert not any("data.analyze_failure" in t for t in completed)
        assert any("governance.correction_decision" in t for t in completed)
        # One checkpoint saved (decision step only).
        assert registry.save_checkpoint.await_count == 1

    async def test_patch_path_returns_repair_artifacts_excluding_validate_step(self, cycle):
        """#389 regression: the executor verifies patches against the repair
        steps' emitted files — if the protocol doesn't surface them (or lets
        the validate step's judgment doc shadow a product file), patch
        verification silently never engages and every repair is re-rolled."""
        import dataclasses as _dc

        repaired = {"name": "qa_handoff.md", "content": "## How to Test\n", "type": "document"}

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "repairable",
                        "affected_task_types": ["builder.assemble"],
                    },
                )
            if envelope.task_type == "builder.assemble_repair":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [repaired], "summary": "repaired"},
                )
            if envelope.task_type == "qa.validate_repair":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "artifacts": [{"name": "repair_validation.md", "content": "PASS"}],
                        "verdict": "PASS",
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        failed_envelope = _dc.replace(
            self._failed_envelope(), task_type="builder.assemble", metadata={"role": "builder"}
        )

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed_envelope,
            result=TaskResult(task_id="task_failed", status="FAILED", error="missing sections"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert protocol_result.correction_path == "patch"
        assert protocol_result.repair_artifacts == [repaired]

    async def test_non_patch_path_returns_no_repair_artifacts(self, cycle):
        """#389: a 'continue' decision dispatches no repair steps — surfacing
        stale/empty artifacts here would make the executor 'verify' nothing
        and could accept an unrepaired task."""

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"correction_path": "continue"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert protocol_result.correction_path == "continue"
        assert protocol_result.repair_artifacts == []


class TestReexecuteRepairedSuite:
    """#456: the repaired-suite retest — the correction loop's source of fresh
    behavioral evidence. Wrong routing, a polluted file set, or a missing
    workspace makes the retest execute something other than 'the repaired
    suite against the original workspace', which is worse than not retesting."""

    def _make_runner(self, responder):
        from adapters.cycles.correction_runner import CorrectionRunner

        class _PassthroughDispatcher:
            def __init__(self):
                self.dispatched = []

            async def dispatch_task(self, envelope, run_id, **_kwargs):
                self.dispatched.append(envelope)
                return responder(envelope)

            async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
                return None

        dispatcher = _PassthroughDispatcher()
        runner = CorrectionRunner(
            cycle_registry=AsyncMock(),
            artifact_vault=AsyncMock(),
            event_bus=MagicMock(),
            task_dispatcher=dispatcher,
            store_artifact=AsyncMock(),
        )
        return runner, dispatcher

    def _failed_qa_envelope(self):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-run_001-m004-qa.test",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="qa.test",
            correlation_id="corr",
            causation_id=None,
            trace_id="t",
            span_id="s",
            inputs={
                "resolved_config": {"dev_capability": "fullstack_fastapi_react"},
                "artifact_contents": {"backend/main.py": "app = None\n"},
                "subtask_focus": "Backend API Tests",
                "expected_artifacts": ["tests/test_api.py"],
                "acceptance_criteria": ["tests pass"],
            },
            metadata={"role": "qa"},
        )

    def _profile(self):
        return SquadProfile(
            profile_id="full",
            name="Full",
            description="d",
            version=1,
            agents=(AgentProfileEntry(agent_id="eve", role="qa", model="qwen", enabled=True),),
            created_at=NOW,
        )

    def _cycle(self):
        return Cycle(
            cycle_id="cyc_001",
            project_id="hello_squad",
            created_at=NOW,
            created_by="system",
            prd_ref="prd_123",
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
        )

    def _state_kwargs(self):
        return {
            "prior_outputs": {},
            "all_artifact_refs": [],
            "stored_artifacts": [],
            "completed_task_ids": [],
            "plan_delta_refs": [],
        }

    async def test_retest_envelope_reruns_failed_task_in_qa_environment(self):
        """Bug caught: retest routed to the wrong agent/task_type would produce
        evidence from a different environment than the original run's."""
        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        patched = [
            {"name": "tests/test_api.py", "content": "def test_x():\n    assert 1\n"},
            {"name": "test_report.md", "content": "old report", "type": "test_report"},
            {
                "name": "typed_check_evaluation.json",
                "content": "{}",
                "type": "typed_check_evaluation",
            },
        ]

        result = await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            self._failed_qa_envelope(),
            patched,
            1,
            profile=self._profile(),
            **self._state_kwargs(),
        )

        assert result is not None and result.status == "SUCCEEDED"
        (env,) = dispatcher.dispatched
        assert env.task_type == "qa.test"
        assert env.agent_id == "eve"
        assert env.task_id == "retest-run_001-01-qa.test"
        assert env.causation_id == "task-run_001-m004-qa.test"
        assert env.metadata["retest"] is True

    async def test_retest_inputs_carry_suite_and_original_workspace(self):
        """Bug caught: report/evaluation artifacts leaking into the suite, or
        the workspace missing — the retest would run the wrong thing."""
        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        patched = [
            {"name": "tests/test_api.py", "content": "repaired", "type": "test"},
            {"name": "test_report.md", "content": "old report", "type": "test_report"},
            {
                "name": "typed_check_evaluation.json",
                "content": "{}",
                "type": "typed_check_evaluation",
            },
        ]

        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            self._failed_qa_envelope(),
            patched,
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )

        (env,) = dispatcher.dispatched
        names = [f["filename"] for f in env.inputs["retest_files"]]
        assert names == ["tests/test_api.py"]
        assert env.inputs["retest_files"][0]["content"] == "repaired"
        # Original workspace travels with the retest.
        assert env.inputs["artifact_contents"] == {"backend/main.py": "app = None\n"}
        assert env.inputs["resolved_config"]["dev_capability"] == "fullstack_fastapi_react"

    async def test_no_usable_suite_returns_none_without_dispatch(self):
        """Bug caught: dispatching a retest with zero files — it would 'pass'
        vacuously (pytest collects nothing) and false-green the patch."""
        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        patched = [{"name": "test_report.md", "content": "r", "type": "test_report"}]

        result = await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            self._failed_qa_envelope(),
            patched,
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )

        assert result is None
        assert dispatcher.dispatched == []

    async def test_workspaceless_envelope_never_dispatches(self):
        """3.11 reproduction: a retest built without artifact_contents fails
        eve's input validation in 300ms and burns a fallback re-roll — the
        runner must refuse the doomed dispatch and return None instead."""
        import dataclasses

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        bare = dataclasses.replace(
            self._failed_qa_envelope(),
            inputs={"resolved_config": {}, "acceptance_criteria": []},
        )

        result = await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            bare,
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )

        assert result is None
        assert dispatcher.dispatched == []


class TestResolveRepairTarget:
    """#531/#532: a patch-path repair must include the DRIFTED SOURCE (from the
    deterministic interface-drift evidence) so a tests_pass failure caused by
    drifted models.py isn't 'repaired' by regenerating the tests. pf-21 refined
    this to a UNION: the failing check's own artifact can carry an independent bug
    (a broken pytest fixture) alongside drift, so it must be targeted too — else
    the loop re-patches already-fixed source forever and never converges."""

    def test_drift_unions_drifted_source_with_the_failing_artifacts(self):
        """Replay of pf-19 (cyc_3632da190fd2) + pf-21 (cyc_2aac58b9f03d):
        tests_pass failed with backend/models.py drifted (notes/pace vs
        route_notes/pace_target) and main.py adding GET /. The drifted source
        MUST be in the target (the #531/#532 win), AND — because the failing test
        file can have its own bug (pf-21's client fixture) — the failed task's
        artifacts are unioned in, drift first."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        failure_evidence = {
            "interface_drift": [
                {
                    "kind": "field_drift",
                    "file": "backend/models.py",
                    "extra": ["notes", "pace"],
                    "missing": ["route_notes", "pace_target"],
                    "instruction": "rename notes->route_notes, pace->pace_target",
                },
                {
                    "kind": "route_drift",
                    "file": "backend/main.py",
                    "extra": ["GET /"],
                    "missing": [],
                    "instruction": "remove the unauthorized GET / route",
                },
            ],
            "validation_result": {"summary": "tests_pass exit 1"},
        }
        failed_inputs = {
            "expected_artifacts": ["tests/test_runs.py", "tests/test_participants.py"],
            "subtask_focus": "Backend run CRUD and validation pytest suite",
            "subtask_description": "Write and run the backend pytest suite",
        }
        artifacts, focus, description = _resolve_repair_target(failure_evidence, failed_inputs)

        # Drift files first (the cause, #531/#532 win — always fixable, no masking),
        # then the failing task's own artifacts (pf-21: their own bug is fixable too).
        assert artifacts == [
            "backend/main.py",
            "backend/models.py",
            "tests/test_runs.py",
            "tests/test_participants.py",
        ]
        assert "backend/models.py" in artifacts  # drifted source is targeted
        assert "tests/test_runs.py" in artifacts  # failing artifact's own bug is fixable
        assert artifacts.index("backend/models.py") < artifacts.index("tests/test_runs.py")
        # No inline prompt content is authored here (#448): the "how" is the managed
        # drift instruction + failure summary, so focus/description stay unset.
        assert focus is None
        assert description is None

    def test_drift_dedups_when_failing_artifact_is_also_drifted(self):
        """If the failing check's artifact IS one of the drifted files, it appears
        once — no duplicate target entry."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {
            "interface_drift": [
                {"file": "backend/models.py", "instruction": "fix fields"},
            ],
        }
        failed_inputs = {"expected_artifacts": ["backend/models.py"]}
        artifacts, _, _ = _resolve_repair_target(evidence, failed_inputs)
        assert artifacts == ["backend/models.py"]

    def test_drift_qa_test_also_unions_package_scoped_source(self):
        """pf-27 (cyc_d01810b2922f): a tests_pass failure that CO-OCCURS with interface
        drift on a frozen file (backend/main.py) must STILL reach the fill-slot source
        under test (backend/routes.py). The drift branch unions the same package-scoped
        implementation surface as the no-drift RC2 branch — else the repair edits only
        the drifted file + the failing test and the real validation bug in routes.py is
        never fixed (the pf-27 non-convergence wall)."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {
            "interface_drift": [
                {"file": "backend/main.py", "instruction": "remove undeclared GET /health"},
            ],
        }
        failed_inputs = {
            "expected_artifacts": ["backend/tests/test_runs_crud.py"],
            "implementation_artifacts": [
                "backend/models.py",
                "backend/routes.py",
                "backend/main.py",
                "frontend/src/views/RunsListView.jsx",
            ],
        }
        artifacts, focus, description = _resolve_repair_target(evidence, failed_inputs)

        assert "backend/routes.py" in artifacts  # fill-slot validation fix now reachable
        assert "backend/tests/test_runs_crud.py" in artifacts  # failing artifact still targeted
        assert "backend/main.py" in artifacts  # drifted file still targeted
        assert artifacts.count("backend/main.py") == 1  # deduped across drift + scoped source
        assert "frontend/src/views/RunsListView.jsx" not in artifacts  # package-scoped
        # drift branch: the "how" is the interface-drift instruction + failure summary.
        assert focus is None and description is None

    def test_drift_without_implementation_surface_is_byte_identical(self):
        """Backward-compat: drift present but no implementation_artifacts key (author
        mode / non-build corrections) → the target is exactly drift ∪ failed artifacts,
        the pre-pf-27 union (empty scoped surface adds nothing)."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {"interface_drift": [{"file": "backend/models.py", "instruction": "fix"}]}
        failed_inputs = {"expected_artifacts": ["backend/tests/test_runs.py"]}
        artifacts, _, _ = _resolve_repair_target(evidence, failed_inputs)
        assert artifacts == ["backend/models.py", "backend/tests/test_runs.py"]

    def test_no_drift_falls_back_to_failed_task_artifacts(self):
        """Absent interface drift, the target is byte-identical to today —
        the failed task's own artifacts/focus/description."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        failed_inputs = {
            "expected_artifacts": ["qa_handoff.md"],
            "subtask_focus": "QA handoff",
            "subtask_description": "Assemble the handoff doc",
        }
        artifacts, focus, description = _resolve_repair_target(
            {"validation_result": {"summary": "missing sections"}}, failed_inputs
        )
        assert artifacts == ["qa_handoff.md"]
        assert focus == "QA handoff"
        assert description == "Assemble the handoff doc"

    def test_no_drift_qa_test_retargets_package_scoped_source(self):
        """RC2 (pf-24): a no-drift qa.test failure (a behavioral bug whose fix lives
        in the source under test, not the test file) unions the failing test artifact
        with the plan's implementation source that shares its top-level package —
        reaching backend/main.py (the /api-prefix fix) while excluding frontend."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        failed_inputs = {
            "expected_artifacts": ["backend/tests/test_runs.py"],
            "implementation_artifacts": [
                "backend/models.py",
                "backend/routes.py",
                "backend/main.py",
                "frontend/src/App.jsx",
            ],
            "subtask_focus": "Backend pytest suite",
            "subtask_description": "Run the backend suite",
        }
        # No interface drift → the RC2 branch.
        artifacts, focus, description = _resolve_repair_target(
            {"validation_result": {"summary": "tests_pass exit 1; /api/runs 404"}},
            failed_inputs,
        )

        assert artifacts == [
            "backend/tests/test_runs.py",
            "backend/models.py",
            "backend/routes.py",
            "backend/main.py",
        ]
        assert "backend/main.py" in artifacts  # the /api-prefix fix is now reachable
        assert "frontend/src/App.jsx" not in artifacts  # package-scoped: no cross-package regen
        assert focus == "Backend pytest suite"
        assert description == "Run the backend suite"

    def test_no_drift_without_surface_is_byte_identical(self):
        """Backward-compat: no implementation_artifacts key → target is exactly the
        failed task's own artifacts (the pre-RC2 #531 behavior)."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        failed_inputs = {
            "expected_artifacts": ["backend/tests/test_runs.py"],
            "subtask_focus": "suite",
            "subtask_description": "run suite",
        }
        artifacts, focus, description = _resolve_repair_target(
            {"validation_result": {"summary": "tests_pass exit 1"}}, failed_inputs
        )
        assert artifacts == ["backend/tests/test_runs.py"]
        assert focus == "suite"
        assert description == "run suite"

    def test_no_drift_frontend_failure_scopes_to_frontend_only(self):
        """Package-scoping is symmetric: a frontend test failure retargets frontend
        source and leaves backend untouched (blast-radius containment both ways)."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        failed_inputs = {
            "expected_artifacts": ["frontend/src/tests/flows.test.jsx"],
            "implementation_artifacts": [
                "backend/main.py",
                "frontend/src/App.jsx",
                "frontend/src/api.js",
            ],
        }
        artifacts, _, _ = _resolve_repair_target({}, failed_inputs)
        assert artifacts == [
            "frontend/src/tests/flows.test.jsx",
            "frontend/src/App.jsx",
            "frontend/src/api.js",
        ]
        assert "backend/main.py" not in artifacts

    def test_drift_present_also_unions_implementation_surface(self):
        """pf-27 (cyc_d01810b2922f) SUPERSEDED the earlier 'drift path stays
        byte-identical' boundary: RC2's package-scoped implementation surface is now
        unioned on the drift branch too. The old boundary assumed drift_files always
        capture the fixable source cause — false when the drift is on a scaffold-FROZEN
        file (main.py) while the behavioral bug lives in a non-drift fill slot
        (routes.py), which then never enters the target → non-convergence. Ordering:
        drifted source first, failed artifact, then scoped source; frontend stays out
        (package-scoped); focus/description unset (#448)."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {"interface_drift": [{"file": "backend/models.py", "instruction": "fix fields"}]}
        failed_inputs = {
            "expected_artifacts": ["backend/tests/test_runs.py"],
            "implementation_artifacts": ["backend/routes.py", "frontend/src/App.jsx"],
        }
        artifacts, focus, _ = _resolve_repair_target(evidence, failed_inputs)
        assert artifacts == ["backend/models.py", "backend/tests/test_runs.py", "backend/routes.py"]
        assert "frontend/src/App.jsx" not in artifacts  # package-scoped: no cross-package regen
        assert focus is None  # drift path leaves focus/description unset (#448)

    def test_no_drift_scoped_source_dedups_against_failed_artifact(self):
        """If a surface file is also a failed artifact it appears once, failed
        artifact first (order preserved)."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        failed_inputs = {
            "expected_artifacts": ["backend/main.py"],
            "implementation_artifacts": ["backend/main.py", "backend/routes.py"],
        }
        artifacts, _, _ = _resolve_repair_target({}, failed_inputs)
        assert artifacts == ["backend/main.py", "backend/routes.py"]

    @pytest.mark.parametrize(
        "evidence",
        [
            None,
            {},
            {"interface_drift": []},
            {"interface_drift": [{"kind": "field_drift"}]},  # finding with no 'file'
            "not-a-dict",
        ],
    )
    def test_missing_or_fileless_drift_falls_back(self, evidence):
        """Robustness: no usable drift evidence → fall back to the failed task's
        artifacts, never crash or return an empty retarget."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        artifacts, focus, _ = _resolve_repair_target(evidence, {"expected_artifacts": ["a.py"]})
        assert artifacts == ["a.py"]
        assert focus is None
