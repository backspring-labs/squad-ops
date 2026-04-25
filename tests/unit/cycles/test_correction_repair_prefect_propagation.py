"""SIP-0087 B2 contract tests: correction + pulse-repair tasks must create
Prefect task_runs and emit TASK_DISPATCHED/SUCCEEDED/FAILED with both
``flow_run_id`` and ``task_run_id`` in the event context.

Without this, correction tasks (SIP-0079) and pulse-repair tasks (SIP-0086)
have no Prefect task pane and the bridge can't transition terminal state —
acceptance criterion §7.5 ("manifest retry events appear in
governance.assess_readiness task pane") is unreachable.

These tests drive ``_run_correction_protocol`` and ``_verify_with_repair``
directly and pin the contract by inspecting the spied call args of
``_create_task_run_if_enabled`` / ``_dispatch_task`` / event emissions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import Cycle, TaskFlowPolicy
from squadops.events.types import EventType
from squadops.tasks.models import TaskEnvelope, TaskResult

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
pytestmark = [pytest.mark.domain_orchestration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cycle() -> Cycle:
    return Cycle(
        cycle_id="cyc_001",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref="prd_ref_123",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


@pytest.fixture
def failed_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task_failed",
        agent_id="neo",
        cycle_id="cyc_001",
        pulse_id="pulse_001",
        project_id="proj_001",
        task_type="development.implement",
        correlation_id="corr_001",
        causation_id="cause_001",
        trace_id="trace_001",
        span_id="span_001",
        metadata={"role": "dev"},
    )


@pytest.fixture
def mock_prefect_reporter() -> AsyncMock:
    """``PrefectReporter`` test double; ``create_task_run`` returns sequential IDs."""
    reporter = AsyncMock()
    counter = {"n": 0}

    async def make_id(*_args, **_kwargs):
        counter["n"] += 1
        return f"tr_{counter['n']:03d}"

    reporter.create_task_run.side_effect = make_id
    reporter.set_task_run_state = AsyncMock()
    return reporter


def _make_executor(mock_prefect_reporter):
    """Build a minimally-wired executor for direct method calls."""
    from adapters.cycles.distributed_flow_executor import DistributedFlowExecutor

    registry = AsyncMock()
    vault = AsyncMock()
    vault.store.side_effect = lambda ref, _content: ref
    queue = AsyncMock()
    squad = AsyncMock()
    ex = DistributedFlowExecutor(
        cycle_registry=registry,
        artifact_vault=vault,
        queue=queue,
        squad_profile=squad,
        task_timeout=5.0,
        workflow_tracker=mock_prefect_reporter,
    )
    ex._cycle_event_bus = MagicMock()
    return ex


# ---------------------------------------------------------------------------
# B2.1 — correction tasks (SIP-0079, governance.* steps)
# ---------------------------------------------------------------------------


class TestCorrectionTaskRunPropagation:
    """`_run_correction_protocol` must create Prefect task_runs for each
    correction step and tag every emitted task event with both run IDs."""

    async def test_correction_steps_create_task_runs_and_emit_full_context(
        self, mock_prefect_reporter, cycle, failed_envelope
    ):
        ex = _make_executor(mock_prefect_reporter)

        # Stub _dispatch_task: capture kwargs and return a "continue"
        # correction decision so the protocol terminates without entering
        # the patch branch (covered separately).
        captured: list[dict] = []

        async def fake_dispatch(envelope, _run_id, *, flow_run_id=None, task_run_id=None, **_):
            captured.append(
                {
                    "task_id": envelope.task_id,
                    "task_type": envelope.task_type,
                    "flow_run_id": flow_run_id,
                    "task_run_id": task_run_id,
                }
            )
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "continue",
                        "decision_rationale": "transient",
                        "classification": "execution",
                        "analysis_summary": "ok",
                        "affected_task_types": [],
                    },
                )
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={"summary": "ok"},
            )

        ex._dispatch_task = fake_dispatch

        await ex._run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed_envelope,
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            flow_run_id="fr_main",
        )

        # Each correction step gets its own Prefect task_run.
        assert mock_prefect_reporter.create_task_run.await_count == len(captured)
        assert all(c["flow_run_id"] == "fr_main" for c in captured)
        assert all(
            c["task_run_id"] is not None and c["task_run_id"].startswith("tr_")
            for c in captured
        )

        # Every TASK_DISPATCHED / TASK_SUCCEEDED / TASK_FAILED for these
        # correction tasks carries flow_run_id + task_run_id.
        emit = ex._cycle_event_bus.emit
        for call in emit.call_args_list:
            event_type = call.args[0] if call.args else call.kwargs.get("event_type")
            if event_type not in (
                EventType.TASK_DISPATCHED,
                EventType.TASK_SUCCEEDED,
                EventType.TASK_FAILED,
            ):
                continue
            ctx = call.kwargs["context"]
            assert ctx["flow_run_id"] == "fr_main"
            assert ctx["task_run_id"].startswith("tr_")

    async def test_correction_skips_task_run_creation_when_flow_run_id_missing(
        self, mock_prefect_reporter, cycle, failed_envelope
    ):
        """No Prefect flow context → no task_runs created (consistent with
        main path); event contexts carry empty-string IDs (not None)."""
        ex = _make_executor(mock_prefect_reporter)

        async def succeed(envelope, *_a, **_k):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={"correction_path": "continue", "affected_task_types": []},
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        ex._dispatch_task = succeed

        await ex._run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed_envelope,
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            flow_run_id=None,
        )

        mock_prefect_reporter.create_task_run.assert_not_awaited()
        for call in ex._cycle_event_bus.emit.call_args_list:
            event_type = call.args[0] if call.args else call.kwargs.get("event_type")
            if event_type != EventType.TASK_DISPATCHED:
                continue
            ctx = call.kwargs["context"]
            assert ctx["flow_run_id"] == ""
            assert ctx["task_run_id"] == ""


# ---------------------------------------------------------------------------
# B2.2 — repair tasks driven by the patch path inside correction
# ---------------------------------------------------------------------------


class TestCorrectionPatchRepairTaskRunPropagation:
    """When correction decides 'patch', repair tasks dispatched inside the
    correction protocol must also create per-step task_runs."""

    async def test_patch_repairs_create_task_runs_and_carry_full_context(
        self, mock_prefect_reporter, cycle, failed_envelope
    ):
        ex = _make_executor(mock_prefect_reporter)

        seen_repair_dispatches: list[dict] = []

        async def fake_dispatch(envelope, _run_id, *, flow_run_id=None, task_run_id=None, **_):
            if envelope.task_type == "governance.correction_decision":
                return TaskResult(
                    task_id=envelope.task_id,
                    status="SUCCEEDED",
                    outputs={
                        "correction_path": "patch",
                        "affected_task_types": ["development.implement"],
                    },
                )
            if envelope.task_id.startswith("repair-"):
                seen_repair_dispatches.append(
                    {
                        "task_id": envelope.task_id,
                        "flow_run_id": flow_run_id,
                        "task_run_id": task_run_id,
                    }
                )
            return TaskResult(task_id=envelope.task_id, status="SUCCEEDED", outputs={})

        ex._dispatch_task = fake_dispatch

        await ex._run_correction_protocol(
            run_id="run_001",
            cycle=cycle,
            envelope=failed_envelope,
            result=TaskResult(task_id="task_failed", status="FAILED", error="bad"),
            correction_attempts=0,
            prior_outputs={},
            all_artifact_refs=[],
            stored_artifacts=[],
            completed_task_ids=[],
            plan_delta_refs=[],
            flow_run_id="fr_main",
        )

        # At least one repair task was dispatched and carries both IDs.
        assert seen_repair_dispatches, "patch path must dispatch repair tasks"
        for entry in seen_repair_dispatches:
            assert entry["flow_run_id"] == "fr_main"
            assert entry["task_run_id"] is not None
            assert entry["task_run_id"].startswith("tr_")


# ---------------------------------------------------------------------------
# B2.3 — pulse-repair tasks (SIP-0086 verification chain)
# ---------------------------------------------------------------------------


class TestPulseRepairTaskRunPropagation:
    """`_verify_with_repair` is reached when a pulse-check boundary FAILs.
    Each repair task must get a dedicated Prefect task_run + full event ctx.
    """

    async def test_pulse_repair_dispatches_carry_run_ids(
        self, mock_prefect_reporter, cycle, failed_envelope
    ):
        from squadops.cycles.pulse_models import (
            PulseDecision,
            SuiteOutcome,
        )

        ex = _make_executor(mock_prefect_reporter)

        # Stub the boundary verification: report FAIL on the first pass and
        # PASS on the second so the loop runs exactly one repair attempt.
        verification_calls = {"n": 0}

        async def fake_verify(*, suites, **_):
            verification_calls["n"] += 1
            if verification_calls["n"] == 1:
                return PulseDecision.FAIL, [
                    MagicMock(suite_outcome=SuiteOutcome.FAIL) for _ in suites
                ]
            return PulseDecision.PASS, [
                MagicMock(suite_outcome=SuiteOutcome.PASS) for _ in suites
            ]

        ex._run_boundary_verification = fake_verify

        captured: list[dict] = []

        async def fake_dispatch(envelope, _run_id, *, flow_run_id=None, task_run_id=None, **_):
            captured.append(
                {
                    "task_type": envelope.task_type,
                    "flow_run_id": flow_run_id,
                    "task_run_id": task_run_id,
                }
            )
            return TaskResult(
                task_id=envelope.task_id,
                status="SUCCEEDED",
                outputs={"summary": "ok"},
            )

        ex._dispatch_task = fake_dispatch

        suite = MagicMock(suite_id="suite_a")
        await ex._verify_with_repair(
            suites=[suite],
            boundary_id="boundary_x",
            cadence_interval_id=0,
            run_id="run_001",
            cycle=cycle,
            obs_ctx=None,
            engine=MagicMock(),
            context=MagicMock(),
            envelope=failed_envelope,
            prior_outputs={},
            stored_artifacts=[],
            all_artifact_refs=[],
            max_repair_attempts=2,
            flow_run_id="fr_main",
            agent_resolver={"strat": "nat", "dev": "neo", "qa": "eve", "lead": "max"},
        )

        # Repair task_runs were created and IDs threaded through dispatch.
        assert captured, "at least one pulse-repair task should dispatch"
        for entry in captured:
            assert entry["flow_run_id"] == "fr_main"
            assert entry["task_run_id"] is not None
            assert entry["task_run_id"].startswith("tr_")

        # Every pulse-repair TASK_* event carries both IDs.
        for call in ex._cycle_event_bus.emit.call_args_list:
            event_type = call.args[0] if call.args else call.kwargs.get("event_type")
            if event_type not in (
                EventType.TASK_DISPATCHED,
                EventType.TASK_SUCCEEDED,
                EventType.TASK_FAILED,
            ):
                continue
            ctx = call.kwargs["context"]
            assert ctx["flow_run_id"] == "fr_main"
            assert ctx["task_run_id"].startswith("tr_")
