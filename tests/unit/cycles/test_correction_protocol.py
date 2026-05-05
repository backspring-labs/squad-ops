"""Tests for SIP-0079 correction protocol in DistributedFlowExecutor.

Covers all 4 correction paths (continue, patch, rewind, abort),
plan delta storage, max_correction_attempts, correction task checkpointing,
and CORRECTION_INITIATED/DECIDED/COMPLETED event emission.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.comms.queue_message import QueueMessage
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


def _make_result_message(
    task_id: str,
    status: str = "SUCCEEDED",
    outputs: dict | None = None,
    error: str | None = None,
    queue_name: str = "cycle_results_run_001",
) -> QueueMessage:
    result = TaskResult(
        task_id=task_id,
        status=status,
        outputs=outputs,
        error=error,
    )
    payload = json.dumps(
        {
            "action": "comms.task.result",
            "metadata": {"correlation_id": "corr"},
            "payload": result.to_dict(),
        }
    )
    return QueueMessage(
        message_id=f"msg_{task_id}",
        queue_name=queue_name,
        payload=payload,
        receipt_handle=f"rh_{task_id}",
        attributes={},
    )


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
def mock_queue():
    mock = AsyncMock()
    mock.publish.return_value = None
    mock.ack.return_value = None
    mock.invalidate_queue.return_value = None
    mock.consume.return_value = []

    async def _consume_blocking(queue_name, timeout, max_messages=1):
        return await mock.consume(queue_name, max_messages=max_messages)

    mock.consume_blocking.side_effect = _consume_blocking
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
def executor(
    mock_registry,
    mock_vault,
    mock_queue,
    mock_squad_profile,
    mock_event_bus,
    cycle,
    run,
):
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    mock_registry.get_cycle.return_value = cycle
    mock_registry.get_run.return_value = run
    ex = DistributedFlowExecutor(
        cycle_registry=mock_registry,
        artifact_vault=mock_vault,
        queue=mock_queue,
        squad_profile=mock_squad_profile,
        task_timeout=5.0,
    )
    ex._cycle_event_bus = mock_event_bus
    return ex


def _build_scripted_consume(mock_queue, script):
    """Build consume side_effect from a list of (status, outputs, error) tuples.

    Each publish gets the next response from the script. After the script
    is exhausted, returns SUCCEEDED with default outputs.
    """
    idx = {"n": 0}

    async def consume_side_effect(queue_name, max_messages=1):
        if not queue_name.startswith("cycle_results_"):
            return []
        last_call = mock_queue.publish.call_args
        if not last_call:
            return []
        msg_data = json.loads(last_call.args[1])
        task_id = msg_data["payload"]["task_id"]

        i = idx["n"]
        idx["n"] += 1

        if i < len(script):
            status, outputs, error = script[i]
        else:
            status, outputs, error = (
                "SUCCEEDED",
                {"summary": "ok", "role": "strat"},
                None,
            )
        return [
            _make_result_message(
                task_id=task_id,
                status=status,
                outputs=outputs,
                error=error,
                queue_name=queue_name,
            )
        ]

    return consume_side_effect


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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
            # Tasks 2-5: succeed
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "dev"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "qa"}, None),
            ("SUCCEEDED", {"summary": "ok", "role": "data"}, None),
        ]
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await executor.execute_run(cycle_id="cyc_001", run_id="run_001")

        # 1 (failed) + 2 (correction) + 2 (repair) + 4 (remaining) = 9
        assert mock_queue.publish.call_count == 9

        status_calls = mock_registry.update_run_status.call_args_list
        terminal_statuses = [c.args[1] for c in status_calls]
        assert RunStatus.COMPLETED in terminal_statuses


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
            squad_profile_id="full-squad",
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
        await executor._store_correction_task_artifacts(
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
            squad_profile_id="full-squad",
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
        await executor._store_correction_task_artifacts(
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
    """max_correction_attempts enforced."""

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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with patch(
            "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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
        import adapters.cycles.distributed_flow_executor as exec_mod
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
        mock_queue.consume.side_effect = _build_scripted_consume(mock_queue, script)

        with (
            patch.object(exec_mod, "generate_task_plan", _gen_with_contract),
            patch(
                "adapters.cycles.distributed_flow_executor.asyncio.sleep",
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

    def test_resolve_agent_config_falls_back_when_role_absent(self):
        """Helper returns (role, None, {}) when profile has no enabled match.

        Reachable only via direct calls (the run-level path validates required
        roles upstream), but the fallback exists so a misconfigured profile
        can't crash the correction loop.
        """
        from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

        class _ProfileStub:
            agents = (
                AgentProfileEntry(agent_id="strat-a", role="strat", model="m", enabled=True),
                AgentProfileEntry(
                    agent_id="data-disabled",
                    role="data",
                    model="m-data",
                    enabled=False,
                ),
            )

        agent_id, model, overrides = DistributedFlowExecutor._resolve_agent_config(
            "data", _ProfileStub()
        )
        assert agent_id == "data"
        assert model is None
        assert overrides == {}
