"""Tests for SIP-0076 gate boundary status semantics (Phase 5).

Covers AC 18: gate-awaiting runs use `paused` status, which is NOT terminal.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.lifecycle import TERMINAL_STATES
from squadops.cycles.models import (
    Cycle,
    Gate,
    GateDecision,
    Run,
    RunStatus,
    RunTerminalError,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def registry():
    return MemoryCycleRegistry()


@pytest.fixture
async def cycle_with_gate(registry):
    """Create a cycle with a gate and a paused run."""
    cycle = Cycle(
        cycle_id="cyc_001",
        project_id="proj_001",
        created_at=NOW,
        created_by="system",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=TaskFlowPolicy(
            mode="sequential",
            gates=(
                Gate(
                    name="progress_plan_review",
                    description="Review plan",
                    after_task_types=(),
                ),
            ),
        ),
        build_strategy="fresh",
    )
    await registry.create_cycle(cycle)
    return cycle


class TestPausedIsNotTerminal:
    """D7: paused status keeps run gate-decidable."""

    def test_paused_not_in_terminal_states(self):
        assert RunStatus.PAUSED not in TERMINAL_STATES

    def test_completed_is_terminal(self):
        assert RunStatus.COMPLETED in TERMINAL_STATES

    def test_failed_is_terminal(self):
        assert RunStatus.FAILED in TERMINAL_STATES

    def test_cancelled_is_terminal(self):
        assert RunStatus.CANCELLED in TERMINAL_STATES


class TestGateDecisionOnPausedRun:
    """AC 18: paused run accepts gate decisions, terminal run rejects."""

    async def test_paused_run_accepts_gate_decision(self, registry, cycle_with_gate):
        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="h",
        )
        await registry.create_run(run)

        decision = GateDecision(
            gate_name="progress_plan_review",
            decision="approved",
            decided_by="user",
            decided_at=NOW,
        )
        updated = await registry.record_gate_decision("run_001", decision)
        assert len(updated.gate_decisions) == 1
        assert updated.gate_decisions[0].decision == "approved"

    async def test_completed_run_rejects_gate_decision(self, registry, cycle_with_gate):
        run = Run(
            run_id="run_002",
            cycle_id="cyc_001",
            run_number=2,
            status="completed",
            initiated_by="api",
            resolved_config_hash="h",
        )
        await registry.create_run(run)

        decision = GateDecision(
            gate_name="progress_plan_review",
            decision="approved",
            decided_by="user",
            decided_at=NOW,
        )
        with pytest.raises(RunTerminalError):
            await registry.record_gate_decision("run_002", decision)

    async def test_paused_run_accepts_new_decision_values(self, registry, cycle_with_gate):
        """New gate decision values work on paused runs."""
        run = Run(
            run_id="run_003",
            cycle_id="cyc_001",
            run_number=3,
            status="paused",
            initiated_by="api",
            resolved_config_hash="h",
        )
        await registry.create_run(run)

        decision = GateDecision(
            gate_name="progress_plan_review",
            decision="approved_with_refinements",
            decided_by="user",
            decided_at=NOW,
        )
        updated = await registry.record_gate_decision("run_003", decision)
        assert updated.gate_decisions[0].decision == "approved_with_refinements"
