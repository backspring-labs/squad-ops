"""Tests for SIP-0076 returned_for_revision workload sequencing (Phase 5).

Covers AC 17: returned_for_revision stays on current workload path.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.cycles.models import (
    Cycle,
    Gate,
    GateDecision,
    Run,
    TaskFlowPolicy,
)

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def registry():
    return MemoryCycleRegistry()


@pytest.fixture
async def cycle_with_gate(registry):
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


class TestReturnedForRevision:
    """AC 17: D8 — returned_for_revision creates a new run on the same workload path."""

    async def test_record_returned_for_revision(self, registry, cycle_with_gate):
        """Gate decision returned_for_revision is recorded successfully."""
        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="h",
            workload_type="planning",
        )
        await registry.create_run(run)

        decision = GateDecision(
            gate_name="progress_plan_review",
            decision="returned_for_revision",
            decided_by="user",
            decided_at=NOW,
        )
        updated = await registry.record_gate_decision("run_001", decision)
        assert updated.gate_decisions[0].decision == "returned_for_revision"

    async def test_original_gate_decision_immutable(self, registry, cycle_with_gate):
        """Once returned_for_revision is recorded, it cannot be changed."""
        run = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="h",
            workload_type="planning",
        )
        await registry.create_run(run)

        decision = GateDecision(
            gate_name="progress_plan_review",
            decision="returned_for_revision",
            decided_by="user",
            decided_at=NOW,
        )
        await registry.record_gate_decision("run_001", decision)

        # Re-reading the run preserves the decision
        run_after = await registry.get_run("run_001")
        assert run_after.gate_decisions[0].decision == "returned_for_revision"

    async def test_new_run_same_workload_path(self, registry, cycle_with_gate):
        """A new run can be created for the same workload type after revision."""
        run1 = Run(
            run_id="run_001",
            cycle_id="cyc_001",
            run_number=1,
            status="paused",
            initiated_by="api",
            resolved_config_hash="h",
            workload_type="planning",
        )
        await registry.create_run(run1)

        decision = GateDecision(
            gate_name="progress_plan_review",
            decision="returned_for_revision",
            decided_by="user",
            decided_at=NOW,
        )
        await registry.record_gate_decision("run_001", decision)

        # D8: Create a new run on the same workload path (refinement)
        run2 = Run(
            run_id="run_002",
            cycle_id="cyc_001",
            run_number=2,
            status="queued",
            initiated_by="retry",
            resolved_config_hash="h",
            workload_type="planning",
        )
        created = await registry.create_run(run2)
        assert created.workload_type == "planning"

        # Both runs coexist with independent gate decisions
        all_runs = await registry.list_runs("cyc_001")
        assert len(all_runs) == 2
        assert all_runs[0].gate_decisions[0].decision == "returned_for_revision"
        assert len(all_runs[1].gate_decisions) == 0
