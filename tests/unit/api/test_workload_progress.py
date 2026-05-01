"""Tests for compute_workload_progress (SIP-0083 §5.8).

Verifies positional alignment of runs to workload_sequence entries,
domain-to-DTO status mapping, cancelled run exclusion, and gate
rejection detection.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.api.routes.cycles.mapping import compute_workload_progress
from squadops.cycles.models import GateDecision, GateDecisionValue, Run, RunStatus

pytestmark = [pytest.mark.domain_api]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _run(
    run_id: str = "run_001",
    run_number: int = 1,
    status: str = "completed",
    workload_type: str | None = None,
    gate_decisions: tuple = (),
) -> Run:
    return Run(
        run_id=run_id,
        cycle_id="cyc_001",
        run_number=run_number,
        status=status,
        initiated_by="api",
        resolved_config_hash="hash_abc",
        workload_type=workload_type,
        gate_decisions=gate_decisions,
    )


class TestWorkloadProgress:
    """compute_workload_progress maps runs to workload_sequence entries."""

    def test_empty_sequence_returns_empty(self):
        """No workload_sequence → no progress entries."""
        result = compute_workload_progress([], [])
        assert result == []

    def test_one_completed_two_pending(self):
        """3-entry sequence with 1 completed run → first completed, others pending."""
        ws = [
            {"type": "framing"},
            {"type": "implementation"},
            {"type": "wrapup"},
        ]
        runs = [_run("run_001", 1, "completed", "framing")]

        result = compute_workload_progress(ws, runs)

        assert len(result) == 3
        assert result[0].index == 0
        assert result[0].run_id == "run_001"
        assert result[0].status == "completed"
        assert result[0].workload_type == "framing"
        assert result[1].run_id is None
        assert result[1].status == "pending"
        assert result[2].run_id is None
        assert result[2].status == "pending"

    def test_all_completed(self):
        """All runs completed → all entries have run_ids and completed status."""
        ws = [
            {"type": "framing"},
            {"type": "implementation"},
        ]
        runs = [
            _run("run_001", 1, "completed", "framing"),
            _run("run_002", 2, "completed", "implementation"),
        ]

        result = compute_workload_progress(ws, runs)

        assert all(e.status == "completed" for e in result)
        assert result[0].run_id == "run_001"
        assert result[1].run_id == "run_002"

    def test_cancelled_run_excluded_from_alignment(self):
        """Cancelled run is skipped — next non-cancelled run aligns."""
        ws = [
            {"type": "framing"},
            {"type": "implementation"},
        ]
        runs = [
            _run("run_001", 1, "cancelled", "framing"),
            _run("run_002", 2, "completed", "framing"),
            _run("run_003", 3, "completed", "implementation"),
        ]

        result = compute_workload_progress(ws, runs)

        # run_001 (cancelled) excluded; run_002 aligns to index 0
        assert result[0].run_id == "run_002"
        assert result[0].status == "completed"
        assert result[1].run_id == "run_003"

    def test_rejected_gate_shows_rejected_status(self):
        """Rejected gate decision → status is 'rejected' not raw run status."""
        ws = [
            {"type": "framing", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ]
        decision = GateDecision(
            gate_name="progress_plan_review",
            decision=GateDecisionValue.REJECTED,
            decided_by="user",
            decided_at=NOW,
        )
        runs = [_run("run_001", 1, "completed", "framing", gate_decisions=(decision,))]

        result = compute_workload_progress(ws, runs)

        assert result[0].status == "rejected"
        assert result[1].status == "pending"

    def test_paused_run_shows_gate_awaiting(self):
        """Paused run → status is 'gate_awaiting' not 'paused'."""
        ws = [{"type": "framing"}]
        runs = [_run("run_001", 1, RunStatus.PAUSED.value)]

        result = compute_workload_progress(ws, runs)

        assert result[0].status == "gate_awaiting"

    def test_queued_run_shows_pending(self):
        """Queued run → status is 'pending' not 'queued'."""
        ws = [{"type": "framing"}]
        runs = [_run("run_001", 1, RunStatus.QUEUED.value)]

        result = compute_workload_progress(ws, runs)

        assert result[0].status == "pending"

    def test_running_run_shows_running(self):
        """Running run → status is 'running'."""
        ws = [{"type": "implementation"}]
        runs = [_run("run_001", 1, RunStatus.RUNNING.value)]

        result = compute_workload_progress(ws, runs)

        assert result[0].status == "running"

    def test_approved_with_refinements_shows_completed(self):
        """approved_with_refinements gate does not change status (still completed)."""
        ws = [
            {"type": "framing", "gate": "progress_plan_review"},
            {"type": "implementation"},
        ]
        decision = GateDecision(
            gate_name="progress_plan_review",
            decision=GateDecisionValue.APPROVED_WITH_REFINEMENTS,
            decided_by="user",
            decided_at=NOW,
            notes="Add error handling",
        )
        runs = [_run("run_001", 1, "completed", "framing", gate_decisions=(decision,))]

        result = compute_workload_progress(ws, runs)

        assert result[0].status == "completed"
