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
            # Repair: development.correction_repair
            ("SUCCEEDED", {"summary": "repaired", "role": "dev"}, None),
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

        # 1 (failed) + 2 (correction) + 1 (repair, #556: dev only) +
        # 1 (#374 re-run of Task 1) + 4 (remaining) = 9
        assert mock_queue.publish.call_count == 9

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
                # analyze_failure / repair all succeed
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

    async def test_only_types_filter_stores_report_and_drops_workspace_files(
        self, executor, mock_vault
    ):
        """#1017 unit half: with ``only_types=("test_report",)`` the helper stores
        the report and drops everything else. The bug the drop-half catches: a
        failed retest re-emits its whole patched tree as ``test``-typed artifacts,
        and storing those under the failed task's own producing_task_type would
        make them read as legitimate qa output to every workspace view —
        quietly defeating the rejected-candidate exclusion (pf-31 Fix E)."""
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
            task_id="retest-run_x-00-qa.test",
            agent_id="eve",
            cycle_id="cyc_x",
            pulse_id="p",
            project_id="proj",
            task_type="qa.test",
            correlation_id="corr",
            causation_id="task-qa",
            trace_id="t",
            span_id="s",
            inputs={},
            metadata={"role": "qa", "retest": True},
        )
        result = TaskResult(
            task_id="retest-run_x-00-qa.test",
            status="FAILED",
            outputs={
                "artifacts": [
                    {
                        "name": "__tests__/api.test.ts",
                        "content": "test body",
                        "media_type": "text/typescript",
                        "type": "test",
                    },
                    {
                        "name": "app/api/runs/route.ts",
                        "content": "repaired route",
                        "media_type": "text/typescript",
                        "type": "test",
                    },
                    {
                        "name": "test_report.md",
                        "content": "# Test Execution Report\n\nFAIL api.test.ts > join 201",
                        "media_type": "text/markdown",
                        "type": "test_report",
                    },
                ],
            },
        )

        all_refs: list[str] = []
        stored: list = []
        await executor._correction_runner._store_correction_task_artifacts(
            result, envelope, cycle, "run_x", all_refs, stored, only_types=("test_report",)
        )

        assert mock_vault.store.call_count == 1
        stored_ref = mock_vault.store.call_args_list[0].args[0]
        assert stored_ref.filename == "test_report.md"
        # The failing-test line — the evidence #1012's adjudication needed — survives.
        assert b"FAIL api.test.ts > join 201" in mock_vault.store.call_args_list[0].args[1]
        assert len(all_refs) == 1

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

    async def test_repair_sequence_dispatches_no_validate_step(
        self, executor, mock_queue, mock_registry, mock_vault, mock_event_bus
    ):
        """#556: the repair sequence dispatches NO qa.validate_repair task,
        and the repair's outputs land in prior_outputs WITHOUT `artifacts`
        (fan-in convention) — the repaired files reach the overlay via
        `repair_artifacts`, not prompt context. A validate dispatch
        reappearing here means an unconsumed LLM turn re-entered the loop;
        artifacts reappearing in prior_outputs means full file contents
        are bloating every downstream prompt again."""
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
        assert not any(p["task_type"] == "qa.validate_repair" for p in publishes), (
            "no qa.validate_repair task may be dispatched (#556)"
        )
        # The dev repair DID run, and later envelopes see its summary but
        # not its file contents.
        assert any(p["task_id"].startswith("repair-") for p in publishes)
        later_with_dev = [
            p["inputs"]["prior_outputs"]["dev"]
            for p in publishes
            if "dev" in (p.get("inputs", {}).get("prior_outputs") or {})
            and p["inputs"]["prior_outputs"]["dev"].get("summary") == "[dev] repaired"
        ]
        assert later_with_dev, "repair summary should reach downstream prior_outputs"
        assert all("artifacts" not in block for block in later_with_dev)


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


class TestEmptyEmissionRefund:
    """#1053, executor side: the refund, and the bound on it.

    The runner flags an emission containing nothing; this is where the attempt is
    handed back. Both halves matter — refunding lets a correct diagnosis have another
    go, and bounding it stops a producer that never emits from looping forever.
    """

    @staticmethod
    def _refund(counter: dict, *, empty: bool, max_corrections: int, attempt: int) -> dict:
        """Drive the EXECUTOR's rule, not a copy of it.

        The first version of this helper re-implemented the arithmetic, which would have
        kept passing while the real rule drifted. `refund_empty_emission_attempt` is
        module-level for exactly this reason.
        """
        from adapters.cycles.dispatched_flow_executor import refund_empty_emission_attempt

        if empty:
            refund_empty_emission_attempt(counter, max_corrections, attempt)
        return counter

    def test_an_empty_emission_hands_the_attempt_back(self):
        """Arm B's shape: the pre-incremented attempt is returned, so the round is
        re-taken instead of billed. Without this, two empty files spent a budget of
        three against a diagnosis that never drifted."""
        counter = {"n": 1}
        self._refund(counter, empty=True, max_corrections=3, attempt=0)
        assert counter["n"] == 0
        assert counter["empty_refunds"] == 1

    def test_a_real_emission_keeps_its_attempt(self):
        """The control. Refunding a genuine repair would make the budget bound nothing
        and a non-converging loop would run until the time budget killed it."""
        counter = {"n": 1}
        self._refund(counter, empty=False, max_corrections=3, attempt=0)
        assert counter["n"] == 1
        assert "empty_refunds" not in counter

    def test_the_refund_allowance_is_finite(self):
        """A producer that emits nothing EVERY time must still terminate. Once the
        allowance is spent the empty round is counted, so exhaustion is reachable."""
        counter = {"n": 0}
        for i in range(5):
            counter["n"] += 1
            self._refund(counter, empty=True, max_corrections=2, attempt=counter["n"] - 1)
        assert counter["empty_refunds"] == 2
        # Three of five rounds were billed, so the budget still advances.
        assert counter["n"] == 3

    def test_refunds_are_counted_separately_from_the_correction_budget(self):
        """The allowance cannot come out of the pool it is failing to consume — that is
        unbounded by construction. `empty_refunds` is its own key."""
        counter = {"n": 1}
        self._refund(counter, empty=True, max_corrections=3, attempt=0)
        assert counter["empty_refunds"] == 1
        assert counter["n"] == 0


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
            # repair task (development.correction_repair)
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
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
            # Repair task + remaining task plan succeed.
            ("SUCCEEDED", {"summary": "repaired", "role": "dev"}, None),
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

    async def test_failed_step_stores_report_evidence_only(self, cycle):
        """#1017 flow half, executor-free: a FAILED protocol step's report-typed
        evidence reaches the vault; its workspace files and checkpoint do not.

        The bug this catches: the FAILED branch previously stored nothing, so a
        red retest's test_report.md — the runner stdout naming which tests
        rejected the repair — was built by the handler and dropped, leaving the
        #1012 signature unadjudicable from banked state (V38 slot 6 required a
        full offline replay to recover what this artifact says)."""
        from squadops.tasks.models import TaskEnvelope, TaskResult

        def responder(envelope):
            return TaskResult(
                task_id=envelope.task_id,
                status="FAILED",
                outputs={
                    "artifacts": [
                        {"name": "__tests__/api.test.ts", "content": "t", "type": "test"},
                        {"name": "app/api/runs/route.ts", "content": "r", "type": "test"},
                        {
                            "name": "test_report.md",
                            "content": "FAIL join expects 201",
                            "media_type": "text/markdown",
                            "type": "test_report",
                        },
                    ]
                },
                error="Repaired suite still fails (exit 1)",
            )

        runner, registry, vault, _bus = self._make_runner(responder)

        retest_envelope = TaskEnvelope(
            task_id="retest-run_001-00-qa.test",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p",
            project_id="hello_squad",
            task_type="qa.test",
            correlation_id="corr",
            causation_id="task_failed",
            trace_id="t",
            span_id="s",
            inputs={},
            metadata={"role": "qa", "retest": True},
        )

        all_refs: list[str] = []
        stored: list = []
        result = await runner._dispatch_protocol_step(
            retest_envelope,
            "run_001",
            cycle,
            None,
            prior_outputs={},
            all_artifact_refs=all_refs,
            stored_artifacts=stored,
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert result.status == "FAILED"
        # Exactly the report is persisted — never the step's workspace files.
        assert vault.store.call_count == 1
        assert vault.store.call_args_list[0].args[0].filename == "test_report.md"
        assert all_refs == [vault.store.call_args_list[0].args[0].artifact_id]
        # A failed step still never checkpoints.
        assert registry.save_checkpoint.call_count == 0

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

    async def test_patch_path_returns_repair_artifacts(self, cycle):
        """#389 regression: the executor verifies patches against the repair
        steps' emitted files — if the protocol doesn't surface them, patch
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

    async def test_repair_envelope_threads_resolved_config_from_failed_task(self, cycle):
        """pf-30 regression: the repair handler's scaffold fill-only appendix
        gates on ``inputs["resolved_config"]["build_profile"]``
        (``is_scaffoldable_stack``). The repair envelope previously omitted
        ``resolved_config``, so the gate saw an empty profile and silently
        no-opped — repairs freely rewrote scaffold-owned interface (pf-30
        attempts 1-3 re-emitted routes.py with relative decorator paths
        against a correct diagnosis, never converging). The retest path
        already threaded the field; this pins the repair path too."""
        import dataclasses as _dc

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                captured.append(envelope)
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [], "summary": "repaired"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        resolved_config = {"build_profile": "fullstack_fastapi_react"}
        failed = _dc.replace(
            self._failed_envelope(),
            task_type="development.develop",
            inputs={
                "resolved_config": resolved_config,
                "expected_artifacts": ["backend/routes.py"],
            },
        )

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="typed check failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert len(captured) == 1
        assert captured[0].inputs["resolved_config"] == resolved_config

    async def test_repair_envelope_resolved_config_defaults_empty(self, cycle):
        """A failed envelope with no resolved_config threads {} — the
        fill-only gate no-ops cleanly instead of the handler KeyErroring."""
        import dataclasses as _dc

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                captured.append(envelope)
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [], "summary": "repaired"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        failed = _dc.replace(self._failed_envelope(), task_type="development.develop")

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert len(captured) == 1
        assert captured[0].inputs["resolved_config"] == {}

    async def test_repair_envelope_carries_the_anchor_surface_from_the_manifest(self, cycle):
        """#667 / fay-14 (cyc_42eed09efbec): neo's FIRST fill of RunDetailView
        honored the manifest anchor convention (art_5ece1244ce22); four repair
        rounds later the accepted view (art_b5890e085e63) carried none of it —
        every repair envelope lacked the anchor surface. The fay-14 shape is
        cross-chain: the FAILED task is qa.test (suite failed → SUBJECT locus →
        dev repair), whose envelope carries only the qa-keyed variant — so the
        surface must be re-derived from the manifest, not copied by key. Both
        keys ride the repair envelope; each handler reads its own."""
        import dataclasses as _dc
        from pathlib import Path

        from squadops.capabilities.scaffold import (
            InterfaceManifest,
            testid_surface_instructions,
        )

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                captured.append(envelope)
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [], "summary": "repaired"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        manifest = InterfaceManifest.from_yaml(
            (
                Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
            ).read_text()
        )
        expected_lines = testid_surface_instructions(manifest)
        assert expected_lines, "fixture manifest must declare testids"

        runner, _registry, _vault, _bus = self._make_runner(responder)
        failed = _dc.replace(
            self._failed_envelope(),
            task_type="qa.test",
            inputs={"dom_testid_surface": expected_lines},
        )

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="suite failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            interface_manifest=manifest,
        )

        assert len(captured) == 1
        assert captured[0].inputs["testid_surface"] == expected_lines
        assert captured[0].inputs["dom_testid_surface"] == expected_lines
        assert any("run-detail" in line for line in captured[0].inputs["testid_surface"])

    async def test_repair_envelope_carries_the_loop_position(self, cycle):
        """#1015 part C: `correction_attempts` and `max_correction_attempts` both
        existed at this dispatch site and neither crossed into the repair envelope, so
        the prompt could not tell round 1 from round 3 or say the budget is finite.

        Bug caught: the same transport gap that #1040 closed for the dev surfaces —
        a value computed one line away from the envelope and never put on it. The
        handler-side render test passes without this, which is exactly how the fact
        goes missing while every step looks covered.
        """
        import dataclasses as _dc

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                captured.append(envelope)
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [], "summary": "repaired"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=_dc.replace(self._failed_envelope(), task_type="qa.test"),
            result=TaskResult(task_id="task_failed", status="FAILED", error="suite failed"),
            correction_attempts=1,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert len(captured) == 1
        # attempts=1 already spent, so the repair being dispatched is attempt 2.
        assert captured[0].inputs["correction_attempt"] == 2
        assert isinstance(captured[0].inputs["max_correction_attempts"], int)

    async def test_no_manifest_threads_no_anchor_keys(self, cycle):
        """Boundary: a manifest-less correction (author mode, non-scaffold
        stacks) must not grow anchor keys — the deriver returns [] and the
        presence-keyed threading stays silent."""
        import dataclasses as _dc

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                captured.append(envelope)
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [], "summary": "repaired"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        failed = _dc.replace(self._failed_envelope(), task_type="development.develop")

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert len(captured) == 1
        assert "testid_surface" not in captured[0].inputs
        assert "dom_testid_surface" not in captured[0].inputs

    async def test_repair_frozen_emission_dropped_and_signaled(self, cycle):
        """SIP-0100 3.4b (pf-27/pf-30 regression), #691: a repair emitting a
        scaffold-frozen path has that artifact DROPPED before any landing point —
        neither the registry store nor the repair_artifacts overlay ever carries it —
        the enforcement is evidenced, and the instruction lands on the carry for the
        next attempt. Un-enforced repair emissions were how pf-27's drift signal got
        polluted and pf-30's repairs fought the scaffold; storing the enforced copy
        under the producer's own task type was how shk-2's phantom drift was fed."""
        from pathlib import Path

        from squadops.capabilities.scaffold import InterfaceManifest
        from squadops.events.types import EventType as _ET

        manifest = InterfaceManifest.from_yaml(
            (
                Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
            ).read_text()
        )

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "artifacts": [
                            {"name": "backend/main.py", "content": "TAMPERED = 1\n"},
                            {"name": "backend/routes.py", "content": "def fill(): return 1\n"},
                        ],
                        "summary": "repaired",
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, vault, bus = self._make_runner(responder)
        carry: list[str] = []

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="tests failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            interface_manifest=manifest,
            scaffold_enforcement_carry=carry,
        )

        # Overlay landing point: the frozen path is gone, the fill slot untouched.
        by_name = {a["name"]: a["content"] for a in protocol_result.repair_artifacts}
        assert "backend/main.py" not in by_name
        assert by_name["backend/routes.py"] == "def fill(): return 1\n"

        # Registry landing point: nothing was stored for the frozen path — not the
        # tamper, and not a scaffold-byte copy under the repair's task type either
        # (that copy is what fed shk-2's phantom drift, #691).
        stored = {
            call.args[0].filename: call.args[1]
            for call in vault.store.call_args_list
            if call.args[0].filename in ("backend/main.py", "backend/routes.py")
        }
        assert "backend/main.py" not in stored
        assert stored["backend/routes.py"] == b"def fill(): return 1\n"

        # Signal: exactly one instruction carried, naming the frozen path.
        assert len(carry) == 1
        assert "backend/main.py" in carry[0]
        assert "fill slots" in carry[0]

        # Evidence: the enforcement was surfaced as an event, not silent.
        enforce_events = [
            c
            for c in bus.emit.call_args_list
            if c.args and c.args[0] == _ET.ARTIFACT_OWNERSHIP_ENFORCED
        ]
        assert len(enforce_events) == 1

    async def test_carry_instructions_reach_next_attempt_failure_evidence(self, cycle):
        """3.4b restore+signal, second half: instructions already on the carry are
        injected into this attempt's failure_evidence (scaffold_enforcement key), so
        the analyze/decision/repair prompts are TOLD about prior frozen restores
        instead of rediscovering the fight."""
        captured: list = []

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                captured.append(envelope)
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "keep going",
                        "affected_task_types": [],
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        carry = ["`backend/main.py` is scaffold-frozen and canonical; do not re-emit it."]

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=1,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            scaffold_enforcement_carry=carry,
        )

        assert len(captured) == 1
        evidence = captured[0].inputs["failure_evidence"]
        assert evidence["scaffold_enforcement"] == carry

    async def test_frozen_file_never_becomes_interface_drift_evidence(self, cycle):
        """#691 wiring seam: the correction protocol must pass the bound record's frozen
        paths into drift detection. Without this the exclusion exists but is never
        reached — a silent no-op — and the analyzer is handed the scaffold's own
        ``GET /health`` probe as producer drift, which is what pinned shk-2's repair
        target to a file no producer may write."""
        from pathlib import Path

        from squadops.capabilities.scaffold import InterfaceManifest

        manifest = InterfaceManifest.from_yaml(
            (
                Path(__file__).parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
            ).read_text()
        )
        # The scaffold's frozen main.py: declares the readiness probe the manifest does
        # not (and cannot) describe, plus a business route so the file is route-bearing.
        frozen_main = (
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            '@router.get("/health")\n'
            "def health(): ...\n"
        )
        drifted_slot = (
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            '@router.post("/run")\n'
            "def create(): ...\n"
        )
        captured: list = []

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                captured.append(envelope)
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "keep going",
                        "affected_task_types": [],
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        await runner.run_correction_protocol(
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
            interface_manifest=manifest,
            artifact_contents={
                "backend/main.py": frozen_main,
                "backend/routes.py": drifted_slot,
            },
            scaffold_enforcement_carry=[],
        )

        drift = captured[0].inputs["failure_evidence"].get("interface_drift", [])
        # The frozen file is silent; the writable slot's real drift still reported.
        assert [d["file"] for d in drift] == ["backend/routes.py"]
        assert "POST /run" in drift[0]["extra"]

    async def test_failure_evidence_carries_contract_expectations(self, cycle):
        """pf-31 Fix A: the failed task's typed criteria reach the analyzer as
        exact expectation lines — without this the analyzer/decision reason from
        prose while the contract's letter ({id} vs {run_id}) stays invisible."""
        import dataclasses as _dc

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                captured.append(envelope)
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "x",
                        "affected_task_types": [],
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        failed = _dc.replace(
            self._failed_envelope(),
            task_type="development.develop",
            inputs={
                "acceptance_criteria": [
                    "GET /runs/{run_id} returns run detail",
                    {
                        "check": "endpoint_defined",
                        "params": {
                            "file": "backend/routes.py",
                            "methods_paths": ["GET /runs/{id}"],
                        },
                        "id": "vc-routes-endpoints",
                    },
                ],
            },
        )

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="typed check failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert len(captured) == 1
        lines = captured[0].inputs["failure_evidence"]["contract_expectations"]
        assert len(lines) == 1
        assert "`GET /runs/{id}`" in lines[0]

    async def test_repair_truncated_python_emission_dropped_and_signaled(self, cycle):
        """pf-31 Fix D: a syntactically invalid .py repair emission is DROPPED
        before any landing point — the overlay and registry never see it (the
        prior stored version stays current) — and the next attempt is told via
        the carry. pf-31 repair-03's truncated test file re-imported the
        collection crash it was dispatched to fix."""
        import dataclasses as _dc

        truncated = "def test_join(client):\n    resp = client.post(\n"

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "artifacts": [
                            {"name": "backend/tests/test_runs.py", "content": truncated},
                            {"name": "backend/routes.py", "content": "ROUTES = []\n"},
                        ],
                        "summary": "repaired",
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, vault, bus = self._make_runner(responder)
        carry: list[str] = []
        failed = _dc.replace(self._failed_envelope(), task_type="development.develop")

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="tests failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            scaffold_enforcement_carry=carry,
        )

        # Overlay: only the valid file survives.
        names = [a["name"] for a in protocol_result.repair_artifacts]
        assert names == ["backend/routes.py"]
        # Registry: the truncated file was never stored.
        stored_names = [c.args[0].filename for c in vault.store.call_args_list]
        assert "backend/tests/test_runs.py" not in stored_names
        assert "backend/routes.py" in stored_names
        # Signal: carried instruction names the file and demands completeness.
        assert len(carry) == 1
        assert "backend/tests/test_runs.py" in carry[0] and "DISCARDED" in carry[0]
        # Evidence: surfaced as an event, not silent.
        from squadops.events.types import EventType as _ET

        rejected_events = [
            c
            for c in bus.emit.call_args_list
            if c.args and c.args[0] == _ET.ARTIFACT_EMISSION_REJECTED
        ]
        assert len(rejected_events) == 1

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


class TestProbeOwnedRepairTarget:
    """#688: a failing behavioral probe aims the repair at the fill slot that owns
    its endpoint, resolved from contract data.

    shk-2 (cyc_88162ecfd895) is the loss this closes: ``backend/routes.py`` used
    ``RunEvent`` without importing it, so ``vc-probe-runs`` answered 500. Both
    repairs emitted ``backend/main.py`` (named by drift evidence) + the failing
    suite, never ``routes.py`` — nothing in the target could name the defect site.
    """

    # Contract v9 (art_4f368ea08799) endpoint→slot map, and the probes that failed
    # per run_verification_summaries for run_da25453895e3.
    OWNERS = {
        "GET /runs": "backend/routes.py",
        "POST /runs": "backend/routes.py",
        "GET /runs/{run_id}": "backend/routes.py",
        "POST /runs/{run_id}/join": "backend/routes.py",
        "POST /runs/{run_id}/leave": "backend/routes.py",
    }
    PROBES = [
        {
            "id": "vc-probe-runs",
            "subject": "backend",
            "request": {"method": "POST", "path": "/runs", "json": {"title": "sample"}},
            "expect": {"status": 201},
            "capture": {"run_id": "id"},
        },
        {
            "id": "vc-probe-runs-join",
            "subject": "backend",
            "request": {"method": "POST", "path": "/runs/{run_id}/join", "json": {"name": "s"}},
            "expect": {"status": 200},
        },
    ]

    def _inputs(self, **over):
        # The shk-2 qa.test envelope: the suite was authored at ROOT-level tests/,
        # so package scoping against backend/ source yields nothing.
        base = {
            "expected_artifacts": ["tests/test_api.py"],
            "implementation_artifacts": [
                "backend/routes.py",
                "frontend/src/views/RunsListView.jsx",
            ],
            "contract_probes": self.PROBES,
            "contract_endpoint_owners": self.OWNERS,
        }
        base.update(over)
        return base

    @staticmethod
    def _evidence(rows, drift=None):
        ev = {"validation_result": {"passed": False, "checks": rows}}
        if drift:
            ev["interface_drift"] = drift
        return ev

    def test_failing_probe_leads_target_over_drift_and_failed_suite(self):
        """The shk-2 replay. Both repairs targeted main.py + the suite and the loop
        reproduced the identical 500; routes.py must now LEAD the target while the
        drifted file and the failing suite still ride."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence(
            [
                {"check": "vc-probe-runs", "status": "failed", "criterion_id": "vc-probe-runs"},
                {"check": "tests_pass", "status": "failed"},
            ],
            drift=[{"kind": "extra_endpoint", "file": "backend/main.py", "extra": ["GET /health"]}],
        )
        artifacts, _, _ = _resolve_repair_target(evidence, self._inputs())

        assert artifacts == ["backend/routes.py", "backend/main.py", "tests/test_api.py"]

    def test_suite_only_failure_reaches_source_via_the_language_fallback(self):
        """The other half of shk-2: a failure with NO probe evidence to resolve. The
        pf-24/pf-27 package union anchors on ``tests/`` and matches no ``backend/``
        source, so before the language fallback the target was exactly what shk-2's
        repairs emitted — main.py + the suite, with routes.py unreachable."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence(
            [{"check": "tests_pass", "status": "failed"}],
            drift=[{"file": "backend/main.py"}],
        )
        stripped = self._inputs()
        del stripped["contract_probes"]
        del stripped["contract_endpoint_owners"]

        artifacts, _, _ = _resolve_repair_target(evidence, stripped)
        assert artifacts == ["backend/main.py", "tests/test_api.py", "backend/routes.py"]
        # The RC2 guarantee survives the widening: a backend failure still cannot
        # reach frontend source.
        assert "frontend/src/views/RunsListView.jsx" not in artifacts

    def test_language_fallback_does_not_fire_when_packages_match(self):
        """pf-24's tight rule is strictly narrower and must keep winning — the fallback
        exists for the empty case only, not as a general widening."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        artifacts, _, _ = _resolve_repair_target(
            {},
            {
                "expected_artifacts": ["backend/tests/test_runs.py"],
                "implementation_artifacts": [
                    "backend/routes.py",
                    "scripts/tool.py",  # same language, different package
                ],
            },
        )
        assert artifacts == ["backend/tests/test_runs.py", "backend/routes.py"]

    def test_frontend_suite_failure_stays_on_the_frontend_side(self):
        """The mirror case: a root-level frontend suite must reach views and never
        backend source — the language line, not the directory tree, is the bound."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        artifacts, _, _ = _resolve_repair_target(
            {},
            {
                "expected_artifacts": ["e2e/runs.test.jsx"],
                "implementation_artifacts": [
                    "backend/routes.py",
                    "frontend/src/views/RunsListView.jsx",
                ],
            },
        )
        assert artifacts == ["e2e/runs.test.jsx", "frontend/src/views/RunsListView.jsx"]

    def test_mixed_language_anchors_widen_nothing(self):
        """Anchors straddling both sides exclude nothing, so 'scoping' would be a
        rename for 'take everything' — stay silent rather than widen blindly."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        artifacts, _, _ = _resolve_repair_target(
            {},
            {
                "expected_artifacts": ["qa/suite.py", "qa/view.test.jsx"],
                "implementation_artifacts": ["backend/routes.py", "frontend/src/App.jsx"],
            },
        )
        assert artifacts == ["qa/suite.py", "qa/view.test.jsx"]

    def test_no_drift_probe_failure_still_reaches_the_owning_slot(self):
        """The RC2 branch: a behavioral failure with no drift at all. Without probe
        resolution this returned only the suite (scoped source empty), which is the
        blind loop in a plainer form."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence([{"check": "vc-probe-runs-join", "status": "failed"}])
        artifacts, focus, description = _resolve_repair_target(
            evidence,
            self._inputs(subtask_focus="Backend API pytest suite", subtask_description="Write it"),
        )

        assert artifacts == ["backend/routes.py", "tests/test_api.py"]
        # Retargeting must not swallow the no-drift branch's focus/description
        # passthrough — the repair prompt loses its subject framing without them.
        assert focus == "Backend API pytest suite"
        assert description == "Write it"

    def test_multiple_failing_probes_on_one_slot_name_it_once(self):
        """shk-2 failed four probes, all owned by routes.py — the repair envelope
        must not list the same file four times."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence(
            [
                {"check": "vc-probe-runs", "status": "failed"},
                {"check": "vc-probe-runs-join", "status": "failed"},
            ]
        )
        artifacts, _, _ = _resolve_repair_target(evidence, self._inputs())
        assert artifacts.count("backend/routes.py") == 1

    @pytest.mark.parametrize("status", ["passed", "skipped"])
    def test_non_failing_probe_indicts_no_slot(self, status):
        """A passing probe is not evidence, and a SKIPPED one means the subject never
        booted — blaming an endpoint for a boot failure would aim every repair at the
        first route in the contract. routes.py still arrives via the language fallback,
        but BEHIND the failed artifact rather than leading it."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence(
            [
                {"check": "vc-probe-runs", "status": status},
                {"check": "tests_pass", "status": "failed"},
            ]
        )
        artifacts, _, _ = _resolve_repair_target(evidence, self._inputs())
        assert artifacts == ["tests/test_api.py", "backend/routes.py"]

    def test_unmapped_probe_id_adds_nothing(self):
        """A failing check that is not a probe (or a probe the contract map does not
        cover) must not promote a slot to the front of the target."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence([{"check": "vc-suite-passes", "status": "failed"}])
        artifacts, _, _ = _resolve_repair_target(evidence, self._inputs())
        assert artifacts == ["tests/test_api.py", "backend/routes.py"]

    @pytest.mark.parametrize(
        "inputs_over",
        [
            {"contract_probes": []},  # probe-less contract
            {"contract_endpoint_owners": {}},  # no endpoint_defined criteria
            {"contract_probes": [{"id": "x"}]},  # probe declaring no HTTP request
            {"contract_probes": ["not-a-mapping"]},  # malformed wire row
        ],
    )
    def test_degraded_probe_inputs_never_crash_or_retarget(self, inputs_over):
        """Author mode, probe-less contracts, and malformed wire rows must degrade to
        the pre-#688 ordering rather than raise — a correction path that raises here
        strands the run."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = self._evidence([{"check": "vc-probe-runs", "status": "failed"}])
        artifacts, _, _ = _resolve_repair_target(evidence, self._inputs(**inputs_over))
        assert artifacts == ["tests/test_api.py", "backend/routes.py"]

    def test_trailing_slash_still_joins_probe_to_owner(self):
        """The probe path and the criterion token are rendered from the same manifest,
        but a hand-authored contract may differ by a trailing slash — a formatting
        difference must not silently drop the defect site."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        probes = [
            {
                "id": "vc-probe-runs",
                "subject": "backend",
                "request": {"method": "post", "path": "/runs/"},
                "expect": {"status": 201},
            }
        ]
        evidence = self._evidence([{"check": "vc-probe-runs", "status": "failed"}])
        artifacts, _, _ = _resolve_repair_target(evidence, self._inputs(contract_probes=probes))
        assert artifacts[0] == "backend/routes.py"


class TestOwnArtifactLocusRouting(TestCorrectionRunnerStandalone):
    """#568: a qa.test failure whose OWN artifact is the defect dispatches a
    qa.test_repair step targeted at the failed task's own contract; behavioral
    failures stay on the dev chain with the subject-scoped repair target."""

    def _failed_qa_envelope(self):
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task_qa_failed",
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
                "expected_artifacts": ["backend/tests/test_runs.py"],
                "subtask_focus": "Backend runs API pytest suite",
                "subtask_description": "Comprehensive pytest test file.",
                "acceptance_criteria": ["suite covers all endpoints"],
                "resolved_config": {"dev_capability": "python_fastapi"},
            },
            metadata={"role": "qa"},
        )

    @staticmethod
    def _patch_responder(captured):
        def responder(envelope):
            captured.append(envelope)
            if envelope.task_type == "data.analyze_failure":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"classification": "execution", "analysis_summary": "no artifact"},
                )
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "re-author",
                        "affected_task_types": ["qa.test"],
                    },
                )
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={
                    "artifacts": [
                        {
                            "name": "backend/tests/test_runs.py",
                            "content": "def test_ok(client):\n    assert True\n",
                            "media_type": "text/x-python",
                            "type": "test",
                        }
                    ]
                },
            )

        return responder

    async def test_emission_failure_routes_to_qa_test_repair(self, cycle):
        """Zero-extraction qa.test failure (the pf-32 class): the repair step
        is qa.test_repair aimed at the failed task's OWN artifact — not a dev
        repair aimed at the implementation surface."""
        captured: list = []
        runner, _registry, _vault, _bus = self._make_runner(self._patch_responder(captured))

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_qa_envelope(),
            result=TaskResult(
                task_id="task_qa_failed",
                status="FAILED",
                error="No valid fenced code blocks found",
                outputs={
                    "emission_failure": {
                        "reason": "no_fenced_blocks",
                        "response_chars": 6203,
                        "expected_artifacts": ["backend/tests/test_runs.py"],
                    }
                },
            ),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        repair_envelopes = [e for e in captured if e.task_type.endswith("_repair")]
        assert [e.task_type for e in repair_envelopes] == ["qa.test_repair"]
        repair = repair_envelopes[0]
        assert repair.metadata.get("role") == "qa" or "qa" in repair.agent_id
        assert repair.inputs["expected_artifacts"] == ["backend/tests/test_runs.py"]
        assert repair.inputs["subtask_focus"] == "Backend runs API pytest suite"
        assert repair.inputs["failed_task_type"] == "qa.test"

    async def test_behavioral_failure_stays_on_dev_chain(self, cycle):
        """Exit-1 (tests ran, app failed them) must NEVER reach qa re-authoring
        — the test-gaming guard. The dev chain repairs the subject."""
        captured: list = []
        runner, _registry, _vault, _bus = self._make_runner(self._patch_responder(captured))

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_qa_envelope(),
            result=TaskResult(
                task_id="task_qa_failed",
                status="FAILED",
                error="Tests failed (exit 1)",
                outputs={
                    "validation_result": {
                        "passed": False,
                        "summary": "Tests failed (exit 1)",
                        "missing_components": ["tests_failed:exit_1"],
                        "checks": [
                            {
                                "check": "tests_pass",
                                "executed": True,
                                "exit_code": 1,
                                "tests_passed": False,
                                "passed": False,
                            }
                        ],
                    }
                },
            ),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        repair_envelopes = [e for e in captured if e.task_type.endswith("_repair")]
        assert [e.task_type for e in repair_envelopes] == ["development.correction_repair"]


class TestErrorContractEvidence(TestCorrectionRunnerStandalone):
    """pf-34: the manifest's error-contract raise convention travels into
    failure_evidence so analyze AND the repair prompt state the ApiError
    signature authoritatively (the pf-33/pf-34 repair 500-class killer)."""

    async def test_error_contract_injected_when_manifest_present(self, cycle):
        from pathlib import Path as _Path

        from squadops.capabilities.scaffold import InterfaceManifest

        manifest = InterfaceManifest.from_yaml(
            _Path("examples/03_group_run/interface_manifest.yaml").read_text(encoding="utf-8")
        )
        analyze_inputs: dict = {}

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                analyze_inputs.update(envelope.inputs or {})
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"classification": "work_product", "analysis_summary": "x"},
                )
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={"correction_path": "continue", "decision_rationale": "r"},
            )

        runner, _r, _v, _b = self._make_runner(responder)
        await runner.run_correction_protocol(
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
            interface_manifest=manifest,
        )
        evidence = analyze_inputs.get("failure_evidence") or {}
        lines = evidence.get("error_contract") or []
        assert any("ApiError(code, message)" in ln for ln in lines)
        assert any("run_not_found" in ln for ln in lines)

    async def test_absent_manifest_injects_nothing(self, cycle):
        analyze_inputs: dict = {}

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                analyze_inputs.update(envelope.inputs or {})
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"classification": "work_product", "analysis_summary": "x"},
                )
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={"correction_path": "continue", "decision_rationale": "r"},
            )

        runner, _r, _v, _b = self._make_runner(responder)
        await runner.run_correction_protocol(
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
        assert "error_contract" not in (analyze_inputs.get("failure_evidence") or {})


class TestRetestProbeThreading:
    """#639: the retest envelope must carry the failed task's contract_probes —
    without them _append_contract_probe_rows no-ops on every retest, the final
    verdict keeps the PRE-repair probe pass, and an accepted repair that
    regresses probed behavior ships green (pf-50: 200 against a pinned 201)."""

    _make_runner = TestReexecuteRepairedSuite._make_runner
    _cycle = TestReexecuteRepairedSuite._cycle
    _profile = TestReexecuteRepairedSuite._profile
    _state_kwargs = TestReexecuteRepairedSuite._state_kwargs
    _failed_qa_envelope = TestReexecuteRepairedSuite._failed_qa_envelope

    async def test_contract_probes_thread_into_the_retest_envelope(self):
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        envelope = self._failed_qa_envelope()
        probes = [
            {
                "id": "vc-probe-runs",
                "subject": "backend",
                "request": {"method": "POST", "path": "/runs", "json": {"title": "x"}},
                "expect": {"status": 201},
            }
        ]
        envelope.inputs["contract_probes"] = probes

        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            envelope,
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )
        (env,) = dispatcher.dispatched
        assert env.inputs["contract_probes"] == probes

    async def test_probe_less_envelope_threads_no_key(self):
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            self._failed_qa_envelope(),
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )
        (env,) = dispatcher.dispatched
        assert "contract_probes" not in env.inputs


class TestRetestAnchorThreading:
    """#667: the retest re-dispatches qa.test, which re-authors the suite from
    scratch (the fay-6 new-dice path) — without dom_testid_surface the retest
    author is blind to the DOM anchor contract the original dispatch carried,
    and the re-authored suite asserts invented render details (fay-14's four
    churn rounds)."""

    _make_runner = TestReexecuteRepairedSuite._make_runner
    _cycle = TestReexecuteRepairedSuite._cycle
    _profile = TestReexecuteRepairedSuite._profile
    _state_kwargs = TestReexecuteRepairedSuite._state_kwargs
    _failed_qa_envelope = TestReexecuteRepairedSuite._failed_qa_envelope

    async def test_dom_testid_surface_threads_into_the_retest_envelope(self):
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        envelope = self._failed_qa_envelope()
        lines = [
            "`RunDetailView` (route `/runs/:id`): root container `run-detail`; "
            "anchors: `run-detail`, `participant-list`"
        ]
        envelope.inputs["dom_testid_surface"] = lines

        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            envelope,
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )
        (env,) = dispatcher.dispatched
        assert env.inputs["dom_testid_surface"] == lines

    async def test_anchor_less_envelope_threads_no_key(self):
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            self._failed_qa_envelope(),
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )
        (env,) = dispatcher.dispatched
        assert "dom_testid_surface" not in env.inputs


class TestRetestWorkspaceThreading:
    """#643: the retest envelope must carry the failed task's
    acceptance_workspace_files — without them the retest's typed acceptance
    re-evaluates in a task-artifacts-only workspace and re-fails a correct
    repair on its contract-mandated sibling imports (the fay-1 loop)."""

    _make_runner = TestReexecuteRepairedSuite._make_runner
    _cycle = TestReexecuteRepairedSuite._cycle
    _profile = TestReexecuteRepairedSuite._profile
    _state_kwargs = TestReexecuteRepairedSuite._state_kwargs
    _failed_qa_envelope = TestReexecuteRepairedSuite._failed_qa_envelope

    async def test_workspace_files_thread_into_the_retest_envelope(self):
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        envelope = self._failed_qa_envelope()
        workspace = {"backend/__init__.py": "", "backend/errors.py": "class ApiError: ..."}
        envelope.inputs["acceptance_workspace_files"] = workspace

        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            envelope,
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )
        (env,) = dispatcher.dispatched
        assert env.inputs["acceptance_workspace_files"] == workspace

    async def test_workspace_less_envelope_threads_no_key(self):
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._make_runner(
            lambda env: TaskResult(task_id=env.task_id, status="SUCCEEDED", outputs={})
        )
        await runner.reexecute_repaired_suite(
            "run_001",
            self._cycle(),
            self._failed_qa_envelope(),
            [{"name": "tests/test_api.py", "content": "repaired", "type": "test"}],
            0,
            profile=self._profile(),
            **self._state_kwargs(),
        )
        (env,) = dispatcher.dispatched
        assert "acceptance_workspace_files" not in env.inputs


class TestFrontendBuildProvenanceTargeting:
    """#650 (fay-8, cyc_7f5f1b8b1790): four identical frontend_build failures,
    every repair emitted backend/test files — RC2's package scoping is
    deliberately backend-bounded, so the build-breaking view sat outside every
    target and the loop could not converge. A failing frontend_build row now
    unions the plan's frontend implementation source into the target."""

    _FAY8_INPUTS = {
        "expected_artifacts": ["backend/tests/test_runs.py", "backend/tests/test_validation.py"],
        "implementation_artifacts": [
            "backend/routes.py",
            "frontend/src/views/RunsListView.jsx",
            "frontend/src/views/CreateRunView.jsx",
            "frontend/src/views/RunDetailView.jsx",
        ],
        # #822: which files are views now comes from the contract rather than from a
        # `frontend/` prefix over implementation_artifacts — a prefix is stack #1's layout,
        # not a property of views, and a root-built stack would union nothing. These are the
        # reference contract's actual `view_slots()`, so the assertions below are unchanged
        # and the fixture is closer to a real qa.test envelope, which carries this key.
        "contract_view_slots": [
            "frontend/src/views/RunsListView.jsx",
            "frontend/src/views/CreateRunView.jsx",
            "frontend/src/views/RunDetailView.jsx",
        ],
        "subtask_focus": "Backend API test suite",
        "subtask_description": "pytest suites",
    }

    def test_failing_frontend_build_row_widens_target_to_frontend_source(self):
        # The fay-8 shape, replayed: backend qa.test reports, frontend is broken.
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {
            "validation_result": {
                "summary": "tests_pass exit 1",
                "checks": [
                    {"check": "frontend_build", "passed": False},
                    {"check": "tests_pass", "passed": False},
                ],
            }
        }
        artifacts, _, _ = _resolve_repair_target(evidence, dict(self._FAY8_INPUTS))
        assert "frontend/src/views/RunsListView.jsx" in artifacts
        assert "frontend/src/views/CreateRunView.jsx" in artifacts
        assert "frontend/src/views/RunDetailView.jsx" in artifacts
        # The failing task's own artifacts stay targeted (pf-21: their own bug
        # is fixable too) and backend source stays via RC2 package scoping.
        assert "backend/tests/test_runs.py" in artifacts
        assert "backend/routes.py" in artifacts

    def test_passing_frontend_build_row_does_not_widen(self):
        # fay-3's shape: real backend test failures, frontend fine — the
        # backend-bounded RC2 scope must stay exactly as it is (no frontend
        # noise diluting the repair).
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {
            "validation_result": {
                "summary": "tests_pass exit 1",
                "checks": [
                    {"check": "frontend_build", "passed": True},
                    {"check": "tests_pass", "passed": False},
                ],
            }
        }
        artifacts, _, _ = _resolve_repair_target(evidence, dict(self._FAY8_INPUTS))
        assert not any(a.startswith("frontend/") for a in artifacts)

    def test_widening_applies_on_the_drift_branch_too(self):
        # Drift and a broken frontend can co-occur; the widening must not be
        # lost to the drift branch's earlier return.
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {
            "interface_drift": [
                {
                    "kind": "route_drift",
                    "file": "backend/main.py",
                    "extra": ["GET /"],
                    "missing": [],
                    "instruction": "remove the unauthorized GET / route",
                }
            ],
            "validation_result": {
                "checks": [{"check": "frontend_build", "passed": False}],
            },
        }
        artifacts, _, _ = _resolve_repair_target(evidence, dict(self._FAY8_INPUTS))
        assert "backend/main.py" in artifacts  # drift stays first-class
        assert "frontend/src/views/RunsListView.jsx" in artifacts

    def test_skipped_frontend_build_row_does_not_widen(self):
        # A not-executed row (#306 Node-absent skip shape) is not a failure.
        from adapters.cycles.correction_runner import _resolve_repair_target

        evidence = {
            "validation_result": {
                "checks": [{"check": "frontend_build", "executed": False, "reason": "skipped"}],
            }
        }
        artifacts, _, _ = _resolve_repair_target(evidence, dict(self._FAY8_INPUTS))
        assert not any(a.startswith("frontend/") for a in artifacts)


# ---------------------------------------------------------------------------
# #511 — the budget gates correction-chain dispatch
# ---------------------------------------------------------------------------


class TestBudgetGatesCorrectionDispatch:
    """#511: a run past its time budget must not START correction work.
    run_57807c247bb4 dispatched a whole repair chain after the 7200s mark;
    shk-4's round 2 was admitted 2min before expiry and ran 39min past.
    The guard fires at the runner's single dispatch choke point, BEFORE
    any transport work."""

    @staticmethod
    def _bare_runner():
        from adapters.cycles.correction_runner import CorrectionRunner

        dispatcher = AsyncMock()
        runner = CorrectionRunner(
            cycle_registry=AsyncMock(),
            artifact_vault=AsyncMock(),
            event_bus=MagicMock(),
            task_dispatcher=dispatcher,
            store_artifact=AsyncMock(),
        )
        return runner, dispatcher

    @staticmethod
    def _envelope():
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-1",
            agent_id="neo",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj",
            task_type="development.develop",
            correlation_id="c1",
            causation_id="c1",
            trace_id="t1",
            span_id="s1",
            inputs={},
            metadata={"role": "dev"},
        )

    async def test_expired_budget_blocks_correction_before_any_dispatch(self, cycle):
        from adapters.cycles.execution_errors import _ExecutionError
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._bare_runner()

        def expired_guard() -> None:
            raise _ExecutionError("Time budget exhausted (10s) at correction-chain dispatch")

        with pytest.raises(_ExecutionError, match="Time budget exhausted"):
            await runner.run_correction_protocol(
                run_id="run_001",
                cycle=cycle,
                envelope=self._envelope(),
                result=TaskResult(task_id="task-1", status="FAILED", error="boom"),
                correction_attempts=0,
                prior_outputs={},
                all_artifact_refs=[],
                stored_artifacts=[],
                completed_task_ids=[],
                plan_delta_refs=[],
                budget_guard=expired_guard,
            )
        # The guard must fire BEFORE any transport work — no task_run, no dispatch.
        dispatcher.create_task_run_if_enabled.assert_not_awaited()
        dispatcher.dispatch_task.assert_not_awaited()

    async def test_unexpired_guard_lets_the_chain_dispatch(self, cycle):
        """Polarity: a live guard that does not raise must not block the chain."""
        from squadops.tasks.models import TaskResult

        runner, dispatcher = self._bare_runner()
        dispatcher.create_task_run_if_enabled.return_value = None
        dispatcher.dispatch_task.return_value = TaskResult(
            task_id="corr-1",
            status="SUCCEEDED",
            outputs={"classification": "execution", "analysis_summary": "ok", "role": "data"},
        )

        calls = {"n": 0}

        def live_guard() -> None:
            calls["n"] += 1

        # The decision step reply lacks a correction_path → protocol raises its
        # own error AFTER dispatching both chain steps; what this test pins is
        # that the guard was consulted per dispatch and dispatch happened.
        try:
            await runner.run_correction_protocol(
                run_id="run_001",
                cycle=cycle,
                envelope=self._envelope(),
                result=TaskResult(task_id="task-1", status="FAILED", error="boom"),
                correction_attempts=0,
                prior_outputs={},
                all_artifact_refs=[],
                stored_artifacts=[],
                completed_task_ids=[],
                plan_delta_refs=[],
                budget_guard=live_guard,
            )
        except Exception:
            pass
        assert dispatcher.dispatch_task.await_count >= 1
        assert calls["n"] >= dispatcher.dispatch_task.await_count


class TestProgressAwareTermination:
    """#435 (1.5 A4): an exact adjacent signature repeat with structural
    candidates on both decisions terminates the chain plan_defect BEFORE any
    repair dispatch — shk-4 spent three rounds and ~2h escaping a defect this
    rule names at round 1."""

    @staticmethod
    def _runner():
        from adapters.cycles.correction_runner import CorrectionRunner

        runner = CorrectionRunner(
            cycle_registry=AsyncMock(),
            artifact_vault=AsyncMock(),
            event_bus=MagicMock(),
            task_dispatcher=AsyncMock(),
            store_artifact=AsyncMock(),
        )
        return runner

    @staticmethod
    def _envelope():
        from squadops.tasks.models import TaskEnvelope

        return TaskEnvelope(
            task_id="task-qa-4",
            agent_id="eve",
            cycle_id="cyc_001",
            pulse_id="p1",
            project_id="proj",
            task_type="qa.test",
            correlation_id="c1",
            causation_id="c1",
            trace_id="t1",
            span_id="s1",
            inputs={},
            metadata={"role": "qa"},
        )

    @staticmethod
    def _failed_result():
        from squadops.tasks.models import TaskResult

        return TaskResult(
            task_id="task-qa-4",
            status="FAILED",
            outputs={
                "outcome_class": "semantic_failure",
                "validation_result": {
                    "passed": False,
                    "checks": [
                        {
                            "check": "tests_pass",
                            "passed": False,
                            "status": "failed",
                            "reason": "exit 1",
                            "executed": True,
                            "exit_code": 1,
                        }
                    ],
                },
            },
            error="suite failed",
        )

    @staticmethod
    def _wire_steps(runner, candidate: str):
        from squadops.tasks.models import TaskResult

        def _step(envelope, *args, **kwargs):
            if envelope.task_type == "data.analyze_failure":
                outputs = {"classification": "work_product", "analysis_summary": "s"}
            else:
                outputs = {
                    "correction_path": "continue",
                    "decision_rationale": "r",
                    "structural_plan_change_candidate": candidate,
                }
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs=outputs)

        runner._dispatch_protocol_step = AsyncMock(side_effect=_step)

    async def _run_round(self, runner, cycle, state, attempt: int):
        return await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._envelope(),
            result=self._failed_result(),
            correction_attempts=attempt,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            signature_state=state,
        )

    async def test_adjacent_repeat_with_candidates_terminates(self, cycle):
        from adapters.cycles.execution_errors import _ExecutionError

        runner = self._runner()
        self._wire_steps(runner, "tighten_acceptance")
        state: dict = {}

        await self._run_round(runner, cycle, state, 0)  # round 0: records state
        with pytest.raises(_ExecutionError, match="plan_defect"):
            await self._run_round(runner, cycle, state, 1)

        # the typed record was persisted as a correction_termination artifact
        stored_types = [
            call.args[0].artifact_type for call in runner._artifact_vault.store.call_args_list
        ]
        assert "correction_termination" in stored_types

    async def test_candidate_none_never_terminates(self, cycle):
        runner = self._runner()
        self._wire_steps(runner, "none")
        state: dict = {}

        await self._run_round(runner, cycle, state, 0)
        await self._run_round(runner, cycle, state, 1)  # same signature — no raise

        stored_types = [
            call.args[0].artifact_type for call in runner._artifact_vault.store.call_args_list
        ]
        assert "correction_termination" not in stored_types

    async def test_no_state_threaded_is_todays_behavior(self, cycle):
        # legacy callers without signature_state: byte-identical behavior
        runner = self._runner()
        self._wire_steps(runner, "tighten_acceptance")

        for attempt in (0, 1):
            await runner.run_correction_protocol(
                run_id="run_001",
                cycle=cycle,
                envelope=self._envelope(),
                result=self._failed_result(),
                correction_attempts=attempt,
                prior_outputs={},
                all_artifact_refs=[],
                stored_artifacts=[],
                completed_task_ids=[],
                plan_delta_refs=[],
            )  # no raise


class TestRepairRejectionEvidence(TestCorrectionRunnerStandalone):
    """#870: the executor's rejected-repair record reaches this attempt's evidence."""

    async def test_prior_rejections_reach_failure_evidence(self, cycle):
        """Bug caught: a rejected repair leaving no trace — roll 12's follow-up
        round re-analyzed the task blind to the fact (and the named reason) that
        the previous repair had been rejected as non-compiling."""
        captured: list = []

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                captured.append(envelope)
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "keep going",
                        "affected_task_types": [],
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        rejections = [
            "correction attempt 2: repaired suite retest FAILED — Repaired suite "
            "still fails (exit 1) [frontend_build: frontend build failed (exit 1)]"
        ]

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=self._failed_envelope(),
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=3,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            repair_rejections=rejections,
        )

        assert len(captured) == 1
        evidence = captured[0].inputs["failure_evidence"]
        assert evidence["prior_repair_rejections"] == rejections

    async def test_no_rejections_add_no_key(self, cycle):
        """Bug caught: an empty block rendering a bare authoritative header on
        every first-time correction."""
        captured: list = []

        def responder(envelope):
            if envelope.task_type == "data.analyze_failure":
                captured.append(envelope)
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "keep going",
                        "affected_task_types": [],
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)

        await runner.run_correction_protocol(
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

        assert len(captured) == 1
        assert "prior_repair_rejections" not in captured[0].inputs["failure_evidence"]


class TestOwnershipVeto:
    """#884: a repair step running under a foreign role must not receive the
    failed task's own artifacts. Roll 14 resumes #3/#4: the dev chain was
    handed eve's suite (rewrote it live-fetch, reversed #877) and 7 app files
    (its page rewrite shipped an undefined-variable compile break that blocked
    the verdict). The veto is table-derived from the own-artifact repair map.
    """

    def test_dev_step_loses_qa_owned_suite_but_keeps_app_files(self):
        from adapters.cycles.correction_runner import _apply_ownership_veto

        target = [
            "__tests__/api_runs.test.ts",
            "app/api/runs/route.ts",
            "app/runs/new/page.tsx",
        ]
        result = _apply_ownership_veto(target, "qa.test", "dev", ["__tests__/api_runs.test.ts"])

        assert result == ["app/api/runs/route.ts", "app/runs/new/page.tsx"]

    def test_own_role_step_keeps_its_own_artifacts(self):
        from adapters.cycles.correction_runner import _apply_ownership_veto

        target = ["__tests__/api_runs.test.ts"]
        result = _apply_ownership_veto(target, "qa.test", "qa", ["__tests__/api_runs.test.ts"])

        assert result == target

    def test_task_without_own_artifact_entry_is_untouched(self):
        """development.develop has no own-artifact table entry — its default
        chain already runs under the producing role, so the veto must no-op
        even when its own artifacts ride the target."""
        from adapters.cycles.correction_runner import _apply_ownership_veto

        target = ["app/api/runs/route.ts", "lib/store_use.ts"]
        result = _apply_ownership_veto(
            target, "development.develop", "dev", ["app/api/runs/route.ts"]
        )

        assert result == target

    def test_veto_may_empty_the_target(self):
        """A dev-chain target consisting ONLY of qa-owned artifacts means the
        locus classifier missed an own-artifact case — the veto still holds
        the boundary (empty target) rather than handing the suite across."""
        from adapters.cycles.correction_runner import _apply_ownership_veto

        result = _apply_ownership_veto(
            ["__tests__/api_runs.test.ts"], "qa.test", "dev", ["__tests__/api_runs.test.ts"]
        )

        assert result == []

    def test_owner_role_derives_from_the_own_artifact_table(self):
        from squadops.cycles.task_plan import own_artifact_role

        assert own_artifact_role("qa.test") == "qa"
        assert own_artifact_role("development.develop") is None


class TestOwnershipVetoWiring(TestCorrectionRunnerStandalone):
    """#884 wiring: the veto must reach the dispatched repair envelope — a
    veto computed but not wired leaves the dev chain holding the qa suite
    exactly as before (the mutation this class exists to kill)."""

    async def test_dev_repair_envelope_excludes_qa_owned_suite(self, cycle):
        import dataclasses as _dc

        captured: list = []

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                captured.append(envelope)
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"artifacts": [], "summary": "repaired"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        # The resume-#3/#4 shape: qa.test failed with NO own-artifact signal
        # (empty checks → UNKNOWN locus → dev chain), suite + implementation
        # source in the union via the same-language fallback.
        failed = _dc.replace(
            self._failed_envelope(),
            task_type="qa.test",
            inputs={
                "expected_artifacts": ["__tests__/api_runs.test.ts"],
                "implementation_artifacts": [
                    "app/api/runs/route.ts",
                    "app/runs/new/page.tsx",
                ],
            },
        )

        await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="suite failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        assert len(captured) == 1
        target = captured[0].inputs["expected_artifacts"]
        assert "__tests__/api_runs.test.ts" not in target
        assert "app/api/runs/route.ts" in target
        assert "app/runs/new/page.tsx" in target

    async def test_dev_repair_emission_of_qa_owned_suite_is_discarded(self, cycle):
        """#1014 flow half: the targeting veto edits the brief, but the failing
        suite is in the step's context as evidence and the model can rewrite
        what it can see — V38 slot 6's dev repairs emitted a full qa-suite
        rewrite on all three rounds and storage accepted it, so the retest
        graded the dev by his own tests. The emission veto must drop qa-owned
        files from what reaches ``repair_artifacts`` (→ overlay → retest →
        #389 re-store), while the app-file repairs pass through untouched."""
        import dataclasses as _dc

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type == "development.correction_repair":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "summary": "repaired",
                        "artifacts": [
                            {
                                "name": "app/api/runs/[run_id]/join/route.ts",
                                "content": "return new Response(body, { status: 201 })",
                                "type": "source",
                            },
                            # The #884-class overreach: a rewrite of the exact
                            # file the veto stripped from the brief.
                            {
                                "name": "__tests__/api_runs.test.ts",
                                "content": "// dev-authored suite",
                                "type": "source",
                            },
                            # Basename-pattern match outside __tests__/ — the
                            # invented-new-filename variant the narrow own-set
                            # rule would miss.
                            {
                                "name": "extra.test.ts",
                                "content": "// more dev-authored tests",
                                "type": "source",
                            },
                        ],
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _registry, _vault, _bus = self._make_runner(responder)
        failed = _dc.replace(
            self._failed_envelope(),
            task_type="qa.test",
            inputs={
                "expected_artifacts": ["__tests__/api_runs.test.ts"],
                "implementation_artifacts": ["app/api/runs/[run_id]/join/route.ts"],
                "resolved_config": {"dev_capability": "nextjs_ts"},
            },
        )

        protocol_result = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed,
            result=TaskResult(task_id="task_failed", status="FAILED", error="suite failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

        names = [a["name"] for a in protocol_result.repair_artifacts]
        assert "app/api/runs/[run_id]/join/route.ts" in names
        assert "__tests__/api_runs.test.ts" not in names
        assert "extra.test.ts" not in names

    async def test_qa_own_artifact_repair_keeps_its_suite_emission(self):
        """#1014 non-regression: the veto is FOREIGN-role only. A qa-role
        own-artifact repair re-authoring its own suite (the #568 locus path)
        must pass through untouched — filtering it would make every qa-side
        suite repair a silent no-op."""
        from adapters.cycles.correction_runner import _apply_emission_ownership_veto
        from squadops.cycles.task_plan import own_artifact_role

        owner = own_artifact_role("qa.test")
        assert owner is not None  # premise: qa.test declares an owner
        suite = [{"name": "__tests__/api_runs.test.ts", "content": "fixed", "type": "test"}]
        kept = _apply_emission_ownership_veto(
            suite,
            "qa.test",
            owner,
            ["__tests__/api_runs.test.ts"],
            ("*.test.ts",),
        )
        assert kept == suite

    async def test_emission_veto_passthrough_when_no_declared_owner(self):
        """#1014 scope guard: task types with no own-artifact owner are
        untouched, mirroring the targeting veto exactly — filtering there
        would silently drop legitimate repairs for every default-chain task."""
        from adapters.cycles.correction_runner import _apply_emission_ownership_veto

        arts = [{"name": "__tests__/x.test.ts", "content": "t", "type": "test"}]
        kept = _apply_emission_ownership_veto(
            arts, "development.implement", "dev", [], ("*.test.ts",)
        )
        assert kept == arts


class TestEmptyRepairEmission:
    """#1053: a repair that emits nothing must not be billed as an attempt.

    Arm B of the 2026-08-23 pair (`cyc_d478dda745b9`) banked `repair_output.md` at ZERO
    bytes on two of its three rounds, under the handler's generic fallback name, while
    the lead's diagnosis stayed correct and stable across all three. Each empty file was
    counted, so `Max correction attempts (3) exhausted` described a loop that had
    actually tried once.
    """

    # Borrowed, not inherited: subclassing the standalone suite would re-run every one
    # of its tests under this class's name, which inflates the count and hides which
    # suite actually covers what.
    _make_runner = TestCorrectionRunnerStandalone._make_runner
    _failed_envelope = TestCorrectionRunnerStandalone._failed_envelope

    @staticmethod
    def _responder(artifacts):
        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type.endswith("correction_repair"):
                return TaskResult(
                    task_id=envelope.task_id, status="SUCCEEDED", outputs={"artifacts": artifacts}
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        return responder

    async def _run(self, cycle, artifacts):
        import dataclasses as _dc

        runner, _r, _v, _b = self._make_runner(self._responder(artifacts))
        return await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=_dc.replace(self._failed_envelope(), task_type="qa.test"),
            result=TaskResult(task_id="task_failed", status="FAILED", error="suite failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )

    async def test_a_zero_byte_emission_is_flagged_empty(self, cycle):
        """The banked shape, exactly: one artifact, no content."""
        protocol = await self._run(cycle, [{"name": "repair_output.md", "content": ""}])
        assert protocol.emission_empty is True
        # #998: a pre-signature responder reports nothing to name; the field is honest.
        assert protocol.empty_emission_signatures == ()

    async def test_the_empty_emissions_signature_reaches_the_result_and_the_event(self, cycle):
        """#998: 'converged in 3 after two empty emissions' must also say WHICH nothing.
        The handler's marker rides the repair result; the protocol result and the
        CORRECTION_COMPLETED payload carry its signature."""
        import dataclasses as _dc

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "decision_rationale": "patchable",
                        "affected_task_types": ["development.develop"],
                    },
                )
            if envelope.task_type.endswith("correction_repair"):
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "artifacts": [{"name": "repair_output.md", "content": ""}],
                        "emission_failure": {
                            "reason": "no_fenced_blocks",
                            "response_chars": 0,
                            "completion_tokens": 8192,
                            "completion_cap": 8192,
                            "signature": "cap_exhausted",
                        },
                    },
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _r, _v, bus = self._make_runner(responder)
        protocol = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=_dc.replace(self._failed_envelope(), task_type="qa.test"),
            result=TaskResult(task_id="task_failed", status="FAILED", error="suite failed"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )
        assert protocol.emission_empty is True
        assert protocol.empty_emission_signatures == ("cap_exhausted",)
        completed = [
            c
            for c in bus.emit.call_args_list
            if c.args and c.args[0] == EventType.CORRECTION_COMPLETED
        ]
        assert completed, "CORRECTION_COMPLETED was not emitted"
        assert completed[-1].kwargs["payload"]["empty_emission_signatures"] == ["cap_exhausted"]

    async def test_whitespace_only_content_is_also_empty(self, cycle):
        """A file of newlines is not a repair. Judging on length rather than on content
        would let the same wasted round through under a slightly different emitter."""
        protocol = await self._run(cycle, [{"name": "repair_output.md", "content": "\n  \n"}])
        assert protocol.emission_empty is True

    async def test_a_real_emission_is_not_flagged(self, cycle):
        """The control. Flagging a genuine repair would refund rounds forever and the
        budget would stop bounding anything."""
        protocol = await self._run(
            cycle, [{"name": "app/api/runs/route.ts", "content": "export async function GET() {}"}]
        )
        assert protocol.emission_empty is False

    async def test_one_empty_file_beside_a_real_one_is_not_empty(self, cycle):
        """Judged on the emission as a whole: a repair that wrote a route and an empty
        note produced something to verify."""
        protocol = await self._run(
            cycle,
            [
                {"name": "notes.md", "content": ""},
                {"name": "app/api/runs/route.ts", "content": "export const x = 1"},
            ],
        )
        assert protocol.emission_empty is False

    async def test_a_path_with_no_repair_step_is_never_flagged(self, cycle):
        """A `continue` decision runs no repair and legitimately emits nothing. Marking
        it empty would refund an attempt that was never spent on a repair — the
        distinction `repair_steps_ran` exists for."""
        import dataclasses as _dc

        def responder(envelope):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"correction_path": "continue", "decision_rationale": "proceed"},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        runner, _r, _v, _b = self._make_runner(responder)
        protocol = await runner.run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=_dc.replace(self._failed_envelope(), task_type="qa.test"),
            result=TaskResult(task_id="task_failed", status="FAILED", error="x"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
        )
        assert protocol.emission_empty is False


class TestSuiteProbeFailuresReachTheOwningSlot:
    """#1015 part A — the deterministic half, replayed from the 1.6.3 set's roll 4.

    The three reds failed the join probe INSIDE the suite (`app_contract` observation
    bound to `vc-probe-api-runs-join`), never as an HTTP probe row, so `_failed_probe_ids`
    returned nothing and the #688 chain never started. And on nextjs_ts the owners map was
    empty besides. Both fixed, the target must lead with the join route and withhold the
    language-wide surface the rounds were wasted on.
    """

    IMPL = [
        "app/api/runs/route.ts",
        "app/api/runs/[run_id]/route.ts",
        "app/api/runs/[run_id]/join/route.ts",
        "app/api/runs/[run_id]/leave/route.ts",
        "app/page.tsx",
        "app/runs/new/page.tsx",
        "app/runs/[run_id]/page.tsx",
    ]

    @staticmethod
    def _nextjs_inputs():
        from squadops.capabilities.scaffold_contract import emit_contract_dict
        from squadops.cycles.verification_contract import VerificationContract
        from tests.unit.capabilities._stack_fixtures import manifest_for_stack

        contract = VerificationContract.from_dict(
            emit_contract_dict(manifest_for_stack("nextjs_ts"))
        )
        return {
            "expected_artifacts": ["__tests__/runs-api.test.ts", "__tests__/join-leave.test.ts"],
            "implementation_artifacts": list(TestSuiteProbeFailuresReachTheOwningSlot.IMPL),
            "contract_probes": [p.to_dict() for p in contract.behavioral.probes],
            "contract_endpoint_owners": contract.endpoint_owners(),
        }

    @staticmethod
    def _observation(failure_class, criterion_id):
        return {
            "file": "__tests__/scaffold/x.scaffold.test.ts",
            "slot_id": "slot-x",
            "failure_class": failure_class,
            "criterion_id": criterion_id,
            "owner": "dev",
            "route": "dev_repair",
        }

    def _evidence(self, *observations):
        return {
            "validation_result": {
                "passed": False,
                "checks": [{"check": "tests_pass", "status": "failed"}],
            },
            "scaffold_evidence": {
                "failure_classes": {"app_contract": 1},
                "observations": list(observations),
            },
        }

    def test_an_app_contract_observation_is_a_failed_probe(self):
        from adapters.cycles.correction_runner import _failed_probe_ids

        ev = self._evidence(
            self._observation("app_contract", "vc-probe-api-runs-join"),
            self._observation("fill", ""),  # a fill-layer failure indicts no endpoint
            self._observation(
                "scaffold_invalid", "vc-probe-api-runs"
            ),  # generator layer: not a probe failure
            self._observation("app_contract", "vc-probe-api-runs-join"),  # duplicate, once
        )
        # A failed `tests_pass` row rides the list as before — it joins no owner and is
        # inert; the subject here is which OBSERVATIONS become probe ids.
        assert [i for i in _failed_probe_ids(ev) if i != "tests_pass"] == ["vc-probe-api-runs-join"]

    def test_http_probe_rows_still_lead_and_join_with_suite_observations(self):
        from adapters.cycles.correction_runner import _failed_probe_ids

        ev = self._evidence(self._observation("app_contract", "vc-probe-api-runs-join"))
        ev["validation_result"]["checks"].append({"check": "vc-probe-api-runs", "status": "failed"})
        assert [i for i in _failed_probe_ids(ev) if i != "tests_pass"] == [
            "vc-probe-api-runs",
            "vc-probe-api-runs-join",
        ]

    def test_roll_4_replay_the_join_route_leads_and_the_language_surface_is_withheld(self):
        """Roll 4 (`cyc_a38814afc16d`), rounds 2–3: the decision named the join handler,
        the target listed all seven files, the repair emitted the create route. Now the
        target is the owning slot plus the failed task's own artifacts — nothing else."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        ev = self._evidence(self._observation("app_contract", "vc-probe-api-runs-join"))
        target, _, _ = _resolve_repair_target(ev, self._nextjs_inputs())
        assert target[0] == "app/api/runs/[run_id]/join/route.ts"
        assert "app/api/runs/route.ts" not in target
        assert not any(t.endswith("page.tsx") for t in target)
        assert set(target) == {
            "app/api/runs/[run_id]/join/route.ts",
            "__tests__/runs-api.test.ts",
            "__tests__/join-leave.test.ts",
        }

    def test_without_site_evidence_the_surface_is_what_it_was(self):
        """The narrowing withholds the fallback only when there is a site to narrow to.
        A suite-only failure with no probe echo still reaches the source under test
        through the #688 language fallback — package scoping matches nothing here."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        ev = {
            "validation_result": {
                "passed": False,
                "checks": [{"check": "tests_pass", "status": "failed"}],
            }
        }
        target, _, _ = _resolve_repair_target(ev, self._nextjs_inputs())
        assert set(self.IMPL) <= set(target)

    def test_drift_files_still_ride_beside_the_narrowed_target(self):
        """pf-21: a co-occurring interface drift names a real defect too; narrowing withholds
        only the no-evidence fallback, never named evidence."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        ev = self._evidence(self._observation("app_contract", "vc-probe-api-runs-join"))
        ev["interface_drift"] = [
            {
                "kind": "rename",
                "file": "app/api/runs/route.ts",
                "extra": [],
                "missing": [],
                "instruction": "x",
            }
        ]
        target, _, _ = _resolve_repair_target(ev, self._nextjs_inputs())
        assert target[:2] == ["app/api/runs/[run_id]/join/route.ts", "app/api/runs/route.ts"]
        assert "app/api/runs/[run_id]/leave/route.ts" not in target


class TestAnalyzerImplicatedFilesAreVerifiedBeforeUse:
    """#1015 part A, the analyzer's half, with #968's cheapest check in front of it.

    The analyzer may name the defect site as structured data. It is trusted only where
    the workspace agrees (the failed task's implementation/expected artifacts or a
    contract-owned slot), only when no deterministic site evidence exists, and it
    narrows the target exactly as a probe-owned slot does.
    """

    INPUTS = {
        "expected_artifacts": ["__tests__/runs-api.test.ts"],
        "implementation_artifacts": [
            "app/api/runs/route.ts",
            "app/api/runs/[run_id]/join/route.ts",
            "app/page.tsx",
        ],
    }
    SUITE_FAIL = {
        "validation_result": {
            "passed": False,
            "checks": [{"check": "tests_pass", "status": "failed"}],
        }
    }

    def test_a_verified_claim_narrows_the_target(self):
        from adapters.cycles.correction_runner import _resolve_repair_target

        target, _, _ = _resolve_repair_target(
            self.SUITE_FAIL,
            dict(self.INPUTS),
            {"implicated_files": ["app/api/runs/[run_id]/join/route.ts"]},
        )
        assert target == ["app/api/runs/[run_id]/join/route.ts", "__tests__/runs-api.test.ts"]

    def test_an_unverifiable_claim_is_dropped_and_the_surface_is_what_it_was(self):
        """#968's shape: a confident path the workspace does not contain. It must not
        become the target — and its presence must not remove the fallback either."""
        from adapters.cycles.correction_runner import (
            _resolve_repair_target,
            _verified_implicated_files,
        )

        analysis = {"implicated_files": ["lib/shadow_store.ts", "backend/routes.py"]}
        assert _verified_implicated_files(analysis, dict(self.INPUTS)) == []
        target, _, _ = _resolve_repair_target(self.SUITE_FAIL, dict(self.INPUTS), analysis)
        assert set(self.INPUTS["implementation_artifacts"]) <= set(target)

    def test_deterministic_site_evidence_outranks_the_analyzer(self):
        """A failing probe's owning slot is contract data; the analyzer's file is a claim.
        When both exist the slot wins and the claim is not consulted."""
        from adapters.cycles.correction_runner import _resolve_repair_target

        inputs = {
            **self.INPUTS,
            "contract_probes": [
                {
                    "id": "vc-probe-api-runs-join",
                    "subject": "backend",
                    "request": {"method": "POST", "path": "/api/runs/{run_id}/join", "json": {}},
                    "expect": {"status": 200},
                }
            ],
            "contract_endpoint_owners": {
                "POST /api/runs/{run_id}/join": "app/api/runs/[run_id]/join/route.ts"
            },
        }
        ev = {
            **self.SUITE_FAIL,
            "scaffold_evidence": {
                "failure_classes": {"app_contract": 1},
                "observations": [
                    {
                        "file": "x",
                        "slot_id": "s",
                        "failure_class": "app_contract",
                        "criterion_id": "vc-probe-api-runs-join",
                        "owner": "dev",
                        "route": "dev_repair",
                    }
                ],
            },
        }
        target, _, _ = _resolve_repair_target(
            ev, inputs, {"implicated_files": ["app/api/runs/route.ts"]}
        )
        assert target[0] == "app/api/runs/[run_id]/join/route.ts"
        assert "app/api/runs/route.ts" not in target

    def test_the_analysis_reaches_the_resolver_through_the_locus_step(self):
        from adapters.cycles.correction_runner import _locus_and_repair_target

        _, expected, _, _ = _locus_and_repair_target(
            "qa.test", self.SUITE_FAIL, dict(self.INPUTS), {"implicated_files": ["app/page.tsx"]}
        )
        assert expected[0] == "app/page.tsx"
        assert "app/api/runs/route.ts" not in expected

    @pytest.mark.parametrize(
        "analysis", [None, {}, {"implicated_files": []}, {"implicated_files": None}]
    )
    def test_no_claim_changes_nothing(self, analysis):
        from adapters.cycles.correction_runner import _resolve_repair_target

        with_claim, _, _ = _resolve_repair_target(self.SUITE_FAIL, dict(self.INPUTS), analysis)
        without, _, _ = _resolve_repair_target(self.SUITE_FAIL, dict(self.INPUTS))
        assert with_claim == without


class TestQaRepairReachesFills:
    """1.6.5 D (#970): an own-artifact qa repair of a scaffold-bound task targets the
    shell of the failing slot and receives the task's current shells.

    Bug caught: the own-artifact branch aims at ``expected_artifacts`` (the plan's
    declared additive file), so a failing FILL is structurally unreachable — roll 6 of
    the 1.6.4 set re-produced ``__tests__/runs.test.ts`` twice while every shell rendered
    "no fill received".
    """

    _SHELL = "__tests__/scaffold/vc-probe-api-runs-join.scaffold.test.ts"

    def _evidence(self, *, klass="fill"):
        return {
            "scaffold_evidence": {
                "failure_classes": {klass: 1},
                "observations": [
                    {
                        "file": self._SHELL,
                        "slot_id": "slot-vc-probe-api-runs-join",
                        "failure_class": klass,
                        "detail": "slot disposition filled: expected [] to have a length of 1",
                        "criterion_id": "vc-probe-api-runs-join" if klass != "fill" else "",
                    }
                ],
            }
        }

    def _inputs(self, *, with_scaffold=True):
        inputs = {
            "expected_artifacts": ["__tests__/runs.test.ts"],
            "subtask_focus": "qa",
            "subtask_description": "author the suite",
        }
        if with_scaffold:
            inputs["verification_scaffold"] = {
                "manifest": {},
                "files": [{"name": self._SHELL, "content": "// pristine"}],
            }
        return inputs

    def test_fill_observations_are_read_per_file_and_slot(self):
        from adapters.cycles.correction_runner import _fill_observations

        assert _fill_observations(self._evidence()) == [
            {
                "file": self._SHELL,
                "slot_id": "slot-vc-probe-api-runs-join",
                "detail": "slot disposition filled: expected [] to have a length of 1",
            }
        ]
        assert _fill_observations(self._evidence(klass="app_contract")) == []
        assert _fill_observations({}) == []

    def test_the_own_artifact_target_is_the_failing_slots_shell(self):
        from adapters.cycles.correction_runner import _locus_and_repair_target
        from squadops.cycles.failure_evidence import FailureLocus

        locus, expected, focus, description = _locus_and_repair_target(
            "qa.test", self._evidence(), self._inputs()
        )
        assert locus == FailureLocus.OWN_ARTIFACT
        assert expected == [self._SHELL]
        assert (focus, description) == ("qa", "author the suite")

    def test_without_the_scaffold_the_target_is_the_declared_file_as_before(self):
        from adapters.cycles.correction_runner import _locus_and_repair_target

        _, expected, _, _ = _locus_and_repair_target(
            "qa.test", self._evidence(), self._inputs(with_scaffold=False)
        )
        assert expected == ["__tests__/runs.test.ts"]

    def test_an_app_contract_failure_never_takes_the_qa_branch(self):
        from adapters.cycles.correction_runner import _locus_and_repair_target
        from squadops.cycles.failure_evidence import FailureLocus

        locus, expected, _, _ = _locus_and_repair_target(
            "qa.test", self._evidence(klass="app_contract"), self._inputs()
        )
        assert locus == FailureLocus.SUBJECT
        assert self._SHELL not in expected

    def test_the_qa_repair_receives_the_current_shells_and_the_failing_slots(self):
        from adapters.cycles.correction_runner import _qa_scaffold_repair_inputs

        failed_result = MagicMock()
        failed_result.outputs = {
            "artifacts": [
                {"name": self._SHELL, "content": "// merged, with fills", "type": "test"},
                {"name": "__tests__/runs.test.ts", "content": "// additive", "type": "test"},
                {"name": "test_report.md", "content": "r", "type": "test_report"},
            ]
        }
        out = _qa_scaffold_repair_inputs("qa", self._inputs(), failed_result, self._evidence())
        assert out["verification_scaffold"]["files"] == [
            {"name": self._SHELL, "content": "// pristine"}
        ]
        assert out["verification_scaffold"]["current_files"] == [
            {"name": self._SHELL, "content": "// merged, with fills"}
        ]
        assert [s["slot_id"] for s in out["repair_slots"]] == ["slot-vc-probe-api-runs-join"]

    @pytest.mark.parametrize(
        "role, with_scaffold",
        [("dev", True), ("qa", False)],
        ids=["foreign-role", "no-scaffold"],
    )
    def test_presence_keyed_nothing_otherwise(self, role, with_scaffold):
        from adapters.cycles.correction_runner import _qa_scaffold_repair_inputs

        out = _qa_scaffold_repair_inputs(
            role, self._inputs(with_scaffold=with_scaffold), MagicMock(outputs={}), self._evidence()
        )
        assert out == {}
