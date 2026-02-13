"""
Behavioral contract tests for CycleRegistryPort (SIP-0064, D13).

These tests run ONLY against MemoryCycleRegistry and verify port-level
behavioral invariants that any correct CycleRegistryPort implementation
must satisfy.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from squadops.cycles.models import (
    Cycle,
    CycleNotFoundError,
    Gate,
    GateAlreadyDecidedError,
    GateDecision,
    IllegalStateTransitionError,
    Run,
    RunNotFoundError,
    RunStatus,
    RunTerminalError,
    TaskFlowPolicy,
    ValidationError,
)

pytestmark = [pytest.mark.domain_orchestration]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

_POLICY = TaskFlowPolicy(
    mode="sequential",
    gates=(
        Gate(
            name="qa_gate",
            description="QA check",
            after_task_types=("dev",),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cycle(cycle_id="cyc_001", project_id="proj_1"):
    return Cycle(
        cycle_id=cycle_id,
        project_id=project_id,
        created_at=NOW,
        created_by="admin",
        prd_ref=None,
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="sha256:abc",
        task_flow_policy=_POLICY,
        build_strategy="fresh",
    )


def _make_run(run_id="run_001", cycle_id="cyc_001", run_number=1):
    return Run(
        run_id=run_id,
        cycle_id=cycle_id,
        run_number=run_number,
        status="queued",
        initiated_by="api",
        resolved_config_hash="hash123",
    )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def registry():
    from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry

    return MemoryCycleRegistry()


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


async def test_create_cycle_then_get(registry):
    """Create a cycle and retrieve it — all fields must round-trip."""
    cycle = _make_cycle()
    created = await registry.create_cycle(cycle)

    assert created.cycle_id == "cyc_001"
    assert created.project_id == "proj_1"

    fetched = await registry.get_cycle("cyc_001")
    assert fetched.cycle_id == cycle.cycle_id
    assert fetched.project_id == cycle.project_id
    assert fetched.created_at == cycle.created_at
    assert fetched.created_by == cycle.created_by
    assert fetched.prd_ref == cycle.prd_ref
    assert fetched.squad_profile_id == cycle.squad_profile_id
    assert fetched.squad_profile_snapshot_ref == cycle.squad_profile_snapshot_ref
    assert fetched.task_flow_policy.mode == cycle.task_flow_policy.mode
    assert len(fetched.task_flow_policy.gates) == 1
    assert fetched.task_flow_policy.gates[0].name == "qa_gate"
    assert fetched.build_strategy == cycle.build_strategy


async def test_create_run_then_update_status(registry):
    """Create a run, transition to running, and verify status update."""
    await registry.create_cycle(_make_cycle())
    await registry.create_run(_make_run())

    updated = await registry.update_run_status("run_001", RunStatus.RUNNING)
    assert updated.status == RunStatus.RUNNING.value

    fetched = await registry.get_run("run_001")
    assert fetched.status == RunStatus.RUNNING.value


async def test_illegal_transition_raises(registry):
    """Illegal transition running -> queued raises IllegalStateTransitionError."""
    await registry.create_cycle(_make_cycle())
    await registry.create_run(_make_run())
    await registry.update_run_status("run_001", RunStatus.RUNNING)

    with pytest.raises(IllegalStateTransitionError):
        await registry.update_run_status("run_001", RunStatus.QUEUED)


async def test_gate_decision_lifecycle(registry):
    """Gate decision: new -> idempotent repeat -> conflicting decision error."""
    await registry.create_cycle(_make_cycle())
    await registry.create_run(_make_run())
    # Transition to running so the run is not in a terminal state
    await registry.update_run_status("run_001", RunStatus.RUNNING)

    decision_approved = GateDecision(
        gate_name="qa_gate",
        decision="approved",
        decided_by="eve",
        decided_at=NOW,
        notes="looks good",
    )

    # First decision records successfully
    run = await registry.record_gate_decision("run_001", decision_approved)
    assert len(run.gate_decisions) == 1
    assert run.gate_decisions[0].gate_name == "qa_gate"
    assert run.gate_decisions[0].decision == "approved"

    # Idempotent repeat of the same decision — no error, same result
    run_again = await registry.record_gate_decision("run_001", decision_approved)
    assert len(run_again.gate_decisions) == 1

    # Conflicting decision raises GateAlreadyDecidedError
    decision_rejected = GateDecision(
        gate_name="qa_gate",
        decision="rejected",
        decided_by="max",
        decided_at=NOW,
        notes="needs rework",
    )
    with pytest.raises(GateAlreadyDecidedError):
        await registry.record_gate_decision("run_001", decision_rejected)


async def test_cancel_cycle_blocks_new_runs(registry):
    """Cancelling a cycle prevents creation of new runs."""
    await registry.create_cycle(_make_cycle())
    await registry.cancel_cycle("cyc_001")

    with pytest.raises(IllegalStateTransitionError):
        await registry.create_run(_make_run())


async def test_append_artifact_refs_dedup_and_order(registry):
    """Artifact refs are de-duplicated and maintain insertion order."""
    await registry.create_cycle(_make_cycle())
    await registry.create_run(_make_run())

    run = await registry.append_artifact_refs("run_001", ("a", "b"))
    assert run.artifact_refs == ("a", "b")

    run = await registry.append_artifact_refs("run_001", ("b", "c"))
    assert run.artifact_refs == ("a", "b", "c")


async def test_list_cycles_with_pagination(registry):
    """List cycles respects limit and offset for pagination."""
    for i in range(5):
        await registry.create_cycle(_make_cycle(cycle_id=f"cyc_{i:03d}"))

    page = await registry.list_cycles("proj_1", limit=2, offset=2)
    assert len(page) == 2
    # All returned cycles belong to the correct project
    for cycle in page:
        assert cycle.project_id == "proj_1"
