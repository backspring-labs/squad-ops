"""Tests for the RunCompletion collaborator (SIP-0097 §6.4, slice 2).

Validates that generate_run_report() produces a structured markdown report
stored as a documentation artifact, and that failures don't affect run status.
Moved from test_run_report.py — assertions unmodified; the fixture now
constructs RunCompletion directly, without a DispatchedFlowExecutor instance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from squadops.cycles.models import (
    Cycle,
    GateDecision,
    Run,
    TaskFlowPolicy,
)
from squadops.tasks.models import TaskEnvelope

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_cycle() -> Cycle:
    return Cycle(
        cycle_id="cyc_001",
        project_id="play_game",
        created_at=NOW,
        created_by="system",
        prd_ref="Build a game",
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
    )


def _make_run(
    gate_decisions=(),
    artifact_refs=(),
    started_at=None,
    finished_at=None,
) -> Run:
    return Run(
        run_id="run_001",
        cycle_id="cyc_001",
        run_number=1,
        status="completed",
        initiated_by="api",
        resolved_config_hash="hash",
        started_at=started_at,
        finished_at=finished_at,
        gate_decisions=gate_decisions,
        artifact_refs=artifact_refs,
    )


def _make_plan(count: int = 3) -> list[TaskEnvelope]:
    steps = [
        ("strategy.analyze_prd", "strat", "nat"),
        ("development.design", "dev", "neo"),
        ("qa.validate", "qa", "eve"),
    ]
    envelopes = []
    for i in range(min(count, len(steps))):
        task_type, role, agent = steps[i]
        envelopes.append(
            TaskEnvelope(
                task_id=f"task_{i}",
                agent_id=agent,
                cycle_id="cyc_001",
                pulse_id="pulse_1",
                project_id="play_game",
                task_type=task_type,
                correlation_id="corr_1",
                causation_id="corr_1" if i == 0 else f"task_{i - 1}",
                trace_id="trace_1",
                span_id=f"span_{i}",
                inputs={"prd": "test"},
                metadata={"role": role, "step_index": i},
            )
        )
    return envelopes


@pytest.fixture
def completion():
    """Create a RunCompletion with mocked ports — no executor needed."""
    from adapters.cycles.run_completion import RunCompletion

    vault = AsyncMock()
    vault.store = AsyncMock(side_effect=lambda ref, content: ref)
    registry = AsyncMock()

    return RunCompletion(
        cycle_registry=registry,
        artifact_vault=vault,
    )


class TestReportContainsMetadata:
    async def test_report_contains_metadata(self, completion):
        """Run report includes cycle/run metadata."""
        cycle = _make_cycle()
        run = _make_run(
            started_at=NOW,
            artifact_refs=("art_001", "art_002"),
        )
        completion._cycle_registry.get_run = AsyncMock(return_value=run)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "COMPLETED",
            cycle=cycle,
            plan=_make_plan(),
        )

        # Verify vault.store was called with the report content
        call_args = completion._artifact_vault.store.call_args
        ref = call_args[0][0]
        content_bytes = call_args[0][1]
        content = content_bytes.decode()

        assert ref.filename == "run_report.md"
        assert ref.artifact_type == "document"
        assert "cyc_001" in content
        assert "run_001" in content
        assert "COMPLETED" in content
        assert "play_game" in content
        assert "fresh" in content

    async def test_report_includes_quality_notes(self, completion):
        """Run report includes quality notes section."""
        cycle = _make_cycle()
        run = _make_run()
        completion._cycle_registry.get_run = AsyncMock(return_value=run)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "COMPLETED",
            cycle=cycle,
            plan=None,
        )

        content = completion._artifact_vault.store.call_args[0][1].decode()
        assert "Quality Notes" in content
        assert "All tasks completed successfully" in content

    async def test_report_quality_notes_failed(self, completion):
        """Run report quality notes reflect FAILED status."""
        cycle = _make_cycle()
        run = _make_run()
        completion._cycle_registry.get_run = AsyncMock(return_value=run)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "FAILED",
            cycle=cycle,
            plan=None,
        )

        content = completion._artifact_vault.store.call_args[0][1].decode()
        assert "Quality Notes" in content
        assert "failed" in content.lower()

    async def test_report_includes_task_plan(self, completion):
        """Run report includes task plan breakdown."""
        cycle = _make_cycle()
        run = _make_run()
        completion._cycle_registry.get_run = AsyncMock(return_value=run)
        plan = _make_plan(3)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "COMPLETED",
            cycle=cycle,
            plan=plan,
        )

        content = completion._artifact_vault.store.call_args[0][1].decode()
        assert "Task Plan" in content
        assert "strategy.analyze_prd" in content
        assert "development.design" in content
        assert "qa.validate" in content
        assert "Total tasks: 3" in content

    async def test_report_includes_gate_decisions(self, completion):
        """Run report includes gate decisions when present."""
        cycle = _make_cycle()
        run = _make_run(
            gate_decisions=(
                GateDecision(
                    gate_name="plan-review",
                    decision="approved",
                    decided_by="user",
                    decided_at=NOW,
                    notes="LGTM",
                ),
            ),
        )
        completion._cycle_registry.get_run = AsyncMock(return_value=run)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "COMPLETED",
            cycle=cycle,
            plan=None,
        )

        content = completion._artifact_vault.store.call_args[0][1].decode()
        assert "Gate Decisions" in content
        assert "plan-review" in content
        assert "approved" in content
        assert "LGTM" in content

    async def test_report_includes_artifact_count(self, completion):
        """Run report includes artifact inventory count."""
        cycle = _make_cycle()
        run = _make_run(artifact_refs=("a1", "a2", "a3"))
        completion._cycle_registry.get_run = AsyncMock(return_value=run)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "COMPLETED",
            cycle=cycle,
            plan=None,
        )

        content = completion._artifact_vault.store.call_args[0][1].decode()
        assert "Total artifacts: 3" in content


class TestReportFailureNoStatusChange:
    async def test_report_failure_no_status_change(self, completion):
        """Report generation failure doesn't affect run status."""
        completion._cycle_registry.get_run = AsyncMock(
            side_effect=Exception("registry down"),
        )

        # Should not raise — caller wraps in try/except
        with pytest.raises(Exception, match="registry down"):
            await completion.generate_run_report(
                "cyc_001",
                "run_001",
                "COMPLETED",
            )

        # The run status was NOT updated (no update_run_status calls)
        completion._cycle_registry.update_run_status.assert_not_called()


class TestReportWithoutCycleOrPlan:
    async def test_report_without_cycle_or_plan(self, completion):
        """Report works with minimal data (no cycle, no plan)."""
        run = _make_run()
        completion._cycle_registry.get_run = AsyncMock(return_value=run)

        await completion.generate_run_report(
            "cyc_001",
            "run_001",
            "FAILED",
            cycle=None,
            plan=None,
        )

        call_args = completion._artifact_vault.store.call_args
        ref = call_args[0][0]
        content = call_args[0][1].decode()

        assert ref.project_id == "unknown"
        assert "FAILED" in content
        assert "cyc_001" in content


# ---------------------------------------------------------------------------
# Terminal-status mapping (SIP-0097 slice 2c) — one case per exception class,
# asserting the exact status/event/payload/log consequence execute_run acts on.
# ---------------------------------------------------------------------------


class TestResolveTerminalOutcome:
    def test_cancellation_maps_to_cancelled(self):
        from adapters.cycles.execution_errors import _CancellationError
        from adapters.cycles.run_completion import resolve_terminal_outcome
        from squadops.cycles.models import RunStatus
        from squadops.events.types import EventType

        outcome = resolve_terminal_outcome(_CancellationError("run_1"), "run_1")
        assert outcome.terminal_status == "CANCELLED"
        assert outcome.run_status == RunStatus.CANCELLED
        assert outcome.event_type == EventType.RUN_CANCELLED
        assert outcome.event_payload is None
        assert outcome.log_kind == "info"
        assert outcome.log_message == "Run run_1 cancelled"

    def test_recruitment_rejection_maps_to_paused_with_reason_payload(self):
        """A duty deferral must stay distinguishable from a BLOCKED pause —
        losing the reason/agent payload would break the operator's resume
        triage (SIP-0089 §2.5)."""
        from adapters.cycles.execution_errors import _RecruitmentRejectedError
        from adapters.cycles.run_completion import resolve_terminal_outcome
        from squadops.cycles.models import RunStatus
        from squadops.events.types import EventType

        exc = _RecruitmentRejectedError("max", "hard_duty_window")
        outcome = resolve_terminal_outcome(exc, "run_1")
        assert outcome.terminal_status == "PAUSED"
        assert outcome.run_status == RunStatus.PAUSED
        assert outcome.event_type == EventType.RUN_PAUSED
        assert outcome.event_payload == {
            "reason": "hard_duty_window",
            "deferred_for_agent": "max",
        }
        assert outcome.log_kind == "info"
        assert "recruitment deferred" in outcome.log_message

    def test_paused_error_maps_to_paused_without_payload(self):
        from adapters.cycles.execution_errors import _PausedError
        from adapters.cycles.run_completion import resolve_terminal_outcome
        from squadops.cycles.models import RunStatus
        from squadops.events.types import EventType

        outcome = resolve_terminal_outcome(_PausedError("blocked"), "run_1")
        assert outcome.terminal_status == "PAUSED"
        assert outcome.run_status == RunStatus.PAUSED
        assert outcome.event_type == EventType.RUN_PAUSED
        assert outcome.event_payload is None
        assert outcome.log_message == "Run run_1 paused"

    def test_execution_error_maps_to_failed_with_error_payload(self):
        from adapters.cycles.execution_errors import _ExecutionError
        from adapters.cycles.run_completion import resolve_terminal_outcome
        from squadops.cycles.models import RunStatus
        from squadops.events.types import EventType

        outcome = resolve_terminal_outcome(_ExecutionError("task t-1 failed"), "run_1")
        assert outcome.terminal_status == "FAILED"
        assert outcome.run_status == RunStatus.FAILED
        assert outcome.event_type == EventType.RUN_FAILED
        assert outcome.event_payload == {"error": "task t-1 failed"}
        assert outcome.log_kind == "error"

    def test_unexpected_exception_maps_to_failed_with_traceback_logging(self):
        """An unclassified crash must keep log_kind='exception' — downgrading
        it to 'error' silently drops the traceback from the logs."""
        from adapters.cycles.run_completion import resolve_terminal_outcome
        from squadops.cycles.models import RunStatus
        from squadops.events.types import EventType

        outcome = resolve_terminal_outcome(ValueError("boom"), "run_1")
        assert outcome.terminal_status == "FAILED"
        assert outcome.run_status == RunStatus.FAILED
        assert outcome.event_type == EventType.RUN_FAILED
        assert outcome.event_payload == {"error": "boom"}
        assert outcome.log_kind == "exception"
        assert "unexpected error" in outcome.log_message

    def test_recruitment_rejection_checked_before_generic_paused(self):
        """_RecruitmentRejectedError must not fall through to the payload-less
        PAUSED branch — the reason payload is the resume affordance."""
        from adapters.cycles.execution_errors import _RecruitmentRejectedError
        from adapters.cycles.run_completion import resolve_terminal_outcome

        outcome = resolve_terminal_outcome(_RecruitmentRejectedError(None, None), "run_1")
        assert outcome.event_payload == {"reason": None, "deferred_for_agent": None}


# ---------------------------------------------------------------------------
# RunLedger (SIP-0097 §6.6)
# ---------------------------------------------------------------------------


class TestRunLedger:
    def test_read_before_any_write_is_empty(self):
        """finalize on a run with no pulse boundaries must see zero entries,
        not crash — the report's pulse section is skipped entirely."""
        from squadops.cycles.run_ledger import RunLedger

        ledger = RunLedger()
        assert ledger.pulse_entries == ()

    def test_entries_accumulate_in_order(self):
        from squadops.cycles.run_ledger import RunLedger

        ledger = RunLedger()
        ledger.record_pulse_boundary({"boundary_id": "b1", "decision": "pass"})
        ledger.record_pulse_boundary({"boundary_id": "b2", "decision": "fail"})
        assert [e["boundary_id"] for e in ledger.pulse_entries] == ["b1", "b2"]

    def test_read_accessor_is_immutable_view(self):
        """A consumer mutating its view must not corrupt the ledger —
        the accumulated evidence is append-only by contract."""
        from squadops.cycles.run_ledger import RunLedger

        ledger = RunLedger()
        ledger.record_pulse_boundary({"boundary_id": "b1", "decision": "pass"})
        view = ledger.pulse_entries
        with pytest.raises((TypeError, AttributeError)):
            view.append({"boundary_id": "rogue"})  # type: ignore[attr-defined]
        assert len(ledger.pulse_entries) == 1

    async def test_report_renders_ledger_entries(self):
        """End-to-end through generate_run_report: ledger entries reach the
        pulse section — the seam SIP-0096 will aggregate over."""
        from adapters.cycles.run_completion import RunCompletion
        from squadops.cycles.run_ledger import RunLedger

        vault = AsyncMock()
        vault.store = AsyncMock(side_effect=lambda ref, content: ref)
        registry = AsyncMock()
        registry.get_run = AsyncMock(return_value=_make_run())
        completion = RunCompletion(cycle_registry=registry, artifact_vault=vault)

        ledger = RunLedger()
        ledger.record_pulse_boundary(
            {
                "boundary_id": "post_qa",
                "cadence_interval_id": 0,
                "decision": "pass",
                "repair_attempt": 0,
                "suites": [{"suite_id": "smoke_suite", "outcome": "pass"}],
            }
        )

        await completion.generate_run_report(
            "cyc_001", "run_001", "COMPLETED", cycle=_make_cycle(), ledger=ledger
        )

        content = vault.store.call_args[0][1].decode()
        assert "Pulse Verification" in content
        assert "post_qa" in content
        assert "smoke_suite=pass" in content
