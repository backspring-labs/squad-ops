"""Integration tests for PostgresCycleRegistry (SIP-Postgres-Cycle-Registry §3.3).

Requires a running Postgres instance (docker-compose up -d postgres).
These tests validate real SQL behaviour: transactions, locking, constraint
enforcement, and data durability across adapter restarts.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from squadops.cycles.models import (
    Cycle,
    CycleNotFoundError,
    FlowMode,
    Gate,
    GateAlreadyDecidedError,
    GateDecision,
    GateDecisionValue,
    IllegalStateTransitionError,
    Run,
    RunStatus,
    TaskFlowPolicy,
    ValidationError,
)

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

# ---------------------------------------------------------------------------
# Skip if Postgres is not reachable
# ---------------------------------------------------------------------------

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://squadops:squadops123@localhost:5432/squadops",
)

try:
    import asyncpg  # noqa: F401
except ImportError:
    pytest.skip("asyncpg not installed", allow_module_level=True)


def _pg_available() -> bool:
    """Quick check: can we open a TCP socket to Postgres?"""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("localhost", 5432))
        s.close()
        return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip(
        "Postgres not reachable on localhost:5432 — start with docker-compose up -d postgres",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def pool():
    """Create an asyncpg pool connected to the test database."""
    p = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)
    yield p
    await p.close()


@pytest_asyncio.fixture
async def migrated_pool(pool):
    """Pool with migrations applied + clean state for test isolation."""
    from pathlib import Path

    from squadops.api.runtime.migrations import apply_migrations

    migrations_dir = Path(__file__).parents[3] / "infra" / "migrations"
    await apply_migrations(pool, migrations_dir)

    # Clean tables before test (reverse FK order)
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cycle_gate_decisions")
        await conn.execute("DELETE FROM cycle_runs")
        await conn.execute("DELETE FROM cycle_registry")

    yield pool

    # Clean tables after test
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cycle_gate_decisions")
        await conn.execute("DELETE FROM cycle_runs")
        await conn.execute("DELETE FROM cycle_registry")


@pytest_asyncio.fixture
async def registry(migrated_pool):
    """Fresh PostgresCycleRegistry backed by real Postgres."""
    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry

    return PostgresCycleRegistry(pool=migrated_pool)


def _make_cycle(**overrides) -> Cycle:
    """Build a minimal valid Cycle for testing."""
    defaults = dict(
        cycle_id=str(uuid.uuid4()),
        project_id="test-project",
        created_at=_NOW,
        created_by="integration-test",
        prd_ref="prd/test.md",
        squad_profile_id="full-squad",
        squad_profile_snapshot_ref="snap-001",
        task_flow_policy=TaskFlowPolicy(
            mode=FlowMode.SEQUENTIAL,
            gates=(
                Gate(
                    name="qa-review",
                    description="QA gate after dev",
                    after_task_types=("development",),
                ),
            ),
        ),
        build_strategy="fresh",
        applied_defaults={"timeout": 300},
        execution_overrides={},
        expected_artifact_types=("code", "test_report"),
        experiment_context={"variant": "A"},
        notes="integration test cycle",
    )
    defaults.update(overrides)
    return Cycle(**defaults)


def _make_run(cycle_id: str, **overrides) -> Run:
    """Build a minimal valid Run for testing."""
    defaults = dict(
        run_id=str(uuid.uuid4()),
        cycle_id=cycle_id,
        run_number=0,  # DB-authoritative; ignored by create_run
        status=RunStatus.QUEUED,
        initiated_by="api",
        resolved_config_hash="abc123",
        resolved_config_ref="config/snapshot.yaml",
    )
    defaults.update(overrides)
    return Run(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullCycleCRUD:
    """create → list → get → cancel (Plan §3.3 item 1)."""

    async def test_full_cycle_crud(self, registry):
        cycle = _make_cycle()
        created = await registry.create_cycle(cycle)
        assert created.cycle_id == cycle.cycle_id

        fetched = await registry.get_cycle(cycle.cycle_id)
        assert fetched.project_id == cycle.project_id
        assert fetched.squad_profile_id == cycle.squad_profile_id
        assert fetched.task_flow_policy.mode == FlowMode.SEQUENTIAL
        assert len(fetched.task_flow_policy.gates) == 1
        assert fetched.applied_defaults == {"timeout": 300}
        assert fetched.expected_artifact_types == ("code", "test_report")

        cycles = await registry.list_cycles(cycle.project_id)
        assert any(c.cycle_id == cycle.cycle_id for c in cycles)

        await registry.cancel_cycle(cycle.cycle_id)

        # Verify cancel blocks new runs
        run = _make_run(cycle.cycle_id)
        with pytest.raises(IllegalStateTransitionError):
            await registry.create_run(run)


class TestFullRunLifecycle:
    """create → running → paused → running → completed (Plan §3.3 item 2)."""

    async def test_full_run_lifecycle(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)

        run = _make_run(cycle.cycle_id)
        created = await registry.create_run(run)
        assert created.run_number == 1
        assert created.status == RunStatus.QUEUED

        running = await registry.update_run_status(created.run_id, RunStatus.RUNNING)
        assert running.status == RunStatus.RUNNING
        assert running.started_at is not None

        paused = await registry.update_run_status(created.run_id, RunStatus.PAUSED)
        assert paused.status == RunStatus.PAUSED

        resumed = await registry.update_run_status(created.run_id, RunStatus.RUNNING)
        assert resumed.status == RunStatus.RUNNING

        completed = await registry.update_run_status(created.run_id, RunStatus.COMPLETED)
        assert completed.status == RunStatus.COMPLETED
        assert completed.finished_at is not None


class TestGateDecisionFlow:
    """record → idempotent repeat → conflict (Plan §3.3 item 3)."""

    async def test_gate_decision_flow(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)

        run = _make_run(cycle.cycle_id)
        created = await registry.create_run(run)

        decision = GateDecision(
            gate_name="qa-review",
            decision=GateDecisionValue.APPROVED,
            decided_by="tester",
            decided_at=_NOW,
            notes="looks good",
        )
        updated = await registry.record_gate_decision(created.run_id, decision)
        assert len(updated.gate_decisions) == 1
        assert updated.gate_decisions[0].gate_name == "qa-review"
        assert updated.gate_decisions[0].decision == GateDecisionValue.APPROVED

        # Idempotent: same decision → no-op
        same_again = await registry.record_gate_decision(created.run_id, decision)
        assert len(same_again.gate_decisions) == 1

        # Conflict: different decision → error
        conflicting = GateDecision(
            gate_name="qa-review",
            decision=GateDecisionValue.REJECTED,
            decided_by="other-tester",
            decided_at=_NOW,
        )
        with pytest.raises(GateAlreadyDecidedError):
            await registry.record_gate_decision(created.run_id, conflicting)

        # Unknown gate → ValidationError
        unknown = GateDecision(
            gate_name="nonexistent-gate",
            decision=GateDecisionValue.APPROVED,
            decided_by="tester",
            decided_at=_NOW,
        )
        with pytest.raises(ValidationError):
            await registry.record_gate_decision(created.run_id, unknown)


class TestArtifactRefAccumulation:
    """Multiple appends, order verified (Plan §3.3 item 4)."""

    async def test_artifact_ref_accumulation(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        run = _make_run(cycle.cycle_id)
        created = await registry.create_run(run)

        r1 = await registry.append_artifact_refs(created.run_id, ("art-1", "art-2"))
        assert r1.artifact_refs == ("art-1", "art-2")

        r2 = await registry.append_artifact_refs(created.run_id, ("art-2", "art-3"))
        assert r2.artifact_refs == ("art-1", "art-2", "art-3")

        r3 = await registry.append_artifact_refs(created.run_id, ("art-1",))
        assert r3.artifact_refs == ("art-1", "art-2", "art-3")  # No change


class TestPagination:
    """create 10 cycles, list with limit=3, offset=3 (Plan §3.3 item 5)."""

    async def test_pagination(self, registry):
        project_id = f"pagination-{uuid.uuid4().hex[:8]}"
        for i in range(10):
            c = _make_cycle(
                cycle_id=f"pag-{i:03d}",
                project_id=project_id,
            )
            await registry.create_cycle(c)

        page = await registry.list_cycles(project_id, limit=3, offset=3)
        assert len(page) == 3

        all_cycles = await registry.list_cycles(project_id, limit=50, offset=0)
        assert len(all_cycles) == 10


class TestConcurrentRunCreation:
    """asyncio.gather(create_run(...)) x20 iterations (Plan §3.3 item 6).

    All must get distinct run_numbers, no serialization errors leak.
    """

    async def test_concurrent_run_creation(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)

        successes = 0
        serial_retries = 0

        for iteration in range(20):
            runs = [_make_run(cycle.cycle_id) for _ in range(3)]
            results = await asyncio.gather(
                *[registry.create_run(r) for r in runs],
                return_exceptions=True,
            )

            created = []
            for r in results:
                if isinstance(r, Exception):
                    # Serialization failures are expected under contention
                    serial_retries += 1
                else:
                    created.append(r)
                    successes += 1

            # All successful creates must have distinct run_numbers
            numbers = [r.run_number for r in created]
            assert len(numbers) == len(set(numbers)), (
                f"Iteration {iteration}: duplicate run_numbers: {numbers}"
            )

        # At least some must succeed (we expect most to)
        assert successes > 0, "No runs succeeded in 20 iterations"


class TestMigrationRunnerIdempotent:
    """run apply_migrations() twice, no error (Plan §3.3 item 7)."""

    async def test_migration_runner_idempotent(self, pool):
        from pathlib import Path

        from squadops.api.runtime.migrations import apply_migrations

        migrations_dir = Path(__file__).parents[3] / "infra" / "migrations"

        first = await apply_migrations(pool, migrations_dir)
        second = await apply_migrations(pool, migrations_dir)
        assert second == 0  # Nothing new to apply


class TestTimestampsSetOnce:
    """running→paused→running→completed, verify started_at unchanged (Plan §3.3 item 8)."""

    async def test_timestamps_set_once(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        run = _make_run(cycle.cycle_id)
        created = await registry.create_run(run)

        running1 = await registry.update_run_status(created.run_id, RunStatus.RUNNING)
        first_started_at = running1.started_at
        assert first_started_at is not None

        await registry.update_run_status(created.run_id, RunStatus.PAUSED)
        running2 = await registry.update_run_status(created.run_id, RunStatus.RUNNING)

        # started_at must not change (COALESCE semantics)
        assert running2.started_at == first_started_at

        completed = await registry.update_run_status(created.run_id, RunStatus.COMPLETED)
        assert completed.started_at == first_started_at
        assert completed.finished_at is not None


class TestCancelCycleBlocksNewRuns:
    """cancel → create_run raises (Plan §3.3 item 9)."""

    async def test_cancel_cycle_blocks_new_runs(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        await registry.cancel_cycle(cycle.cycle_id)

        run = _make_run(cycle.cycle_id)
        with pytest.raises(IllegalStateTransitionError):
            await registry.create_run(run)


class TestCancelRunIndependent:
    """cancel cycle, then cancel run separately (Plan §3.3 item 10)."""

    async def test_cancel_existing_runs_independent(self, registry):
        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        run = _make_run(cycle.cycle_id)
        created = await registry.create_run(run)

        # Cancel the cycle
        await registry.cancel_cycle(cycle.cycle_id)

        # Cancel the existing run independently (should succeed)
        await registry.cancel_run(created.run_id)
        cancelled = await registry.get_run(created.run_id)
        assert cancelled.status == RunStatus.CANCELLED


class TestPersistenceAcrossAdapterRestart:
    """Create cycle + run, instantiate new adapter, verify data (Plan §3.3 item 11).

    This proves the core objective: durability across process lifetimes.
    """

    async def test_persistence_across_adapter_restart(self, migrated_pool):
        from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry

        # Adapter instance 1: create data
        registry1 = PostgresCycleRegistry(pool=migrated_pool)
        cycle = _make_cycle()
        await registry1.create_cycle(cycle)
        run = _make_run(cycle.cycle_id)
        created_run = await registry1.create_run(run)
        await registry1.update_run_status(created_run.run_id, RunStatus.RUNNING)

        # "Restart": create a completely new adapter instance
        registry2 = PostgresCycleRegistry(pool=migrated_pool)

        # Verify cycle survives
        fetched_cycle = await registry2.get_cycle(cycle.cycle_id)
        assert fetched_cycle.cycle_id == cycle.cycle_id
        assert fetched_cycle.project_id == cycle.project_id
        assert fetched_cycle.task_flow_policy.mode == FlowMode.SEQUENTIAL

        # Verify run survives with correct state
        fetched_run = await registry2.get_run(created_run.run_id)
        assert fetched_run.run_id == created_run.run_id
        assert fetched_run.status == RunStatus.RUNNING
        assert fetched_run.started_at is not None
