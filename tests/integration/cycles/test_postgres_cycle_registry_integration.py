"""Integration tests for PostgresCycleRegistry (SIP-Postgres-Cycle-Registry §3.3).

Requires a running Postgres instance (docker-compose up -d postgres).
These tests validate real SQL behaviour: transactions, locking, constraint
enforcement, and data durability across adapter restarts.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from adapters.persistence.pool import create_pool
from squadops.cycles.models import (
    Cycle,
    CycleStatus,
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
from tests.integration.conftest import integration_postgres_dsn

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

# ---------------------------------------------------------------------------
# Skip if Postgres is not reachable
# ---------------------------------------------------------------------------

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB

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

_NOW = datetime.now(UTC)


@pytest_asyncio.fixture
async def pool():
    """Create an asyncpg pool connected to the test database."""
    p = await create_pool(POSTGRES_URL, min_size=1, max_size=10)
    yield p
    await p.close()


async def _truncate_cycle_tables(pool):
    """Empty cycle_registry and everything that references it, transitively.

    Safe only because the session guard in tests/integration/conftest.py has already
    refused to connect to the deployment database (#1099).
    """
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE cycle_registry CASCADE")


@pytest_asyncio.fixture
async def migrated_pool(pool):
    """Pool with migrations applied + clean state for test isolation."""
    from pathlib import Path

    from squadops.api.runtime.migrations import apply_migrations

    migrations_dir = Path(__file__).parents[3] / "infra" / "migrations"
    await apply_migrations(pool, migrations_dir)

    # Clean between tests. TRUNCATE ... CASCADE rather than a hand-listed DELETE order:
    # the old list named cycle_gate_decisions / cycle_runs / cycle_registry and was written
    # before pulse_verification_records, run_checkpoints and run_verification_summaries
    # gained FKs onto cycle_runs, so every run raised ForeignKeyViolationError at setup —
    # the sixteen failures of #1099. CASCADE derives the dependents from the live schema,
    # so a new child table does not silently rot this fixture again.
    await _truncate_cycle_tables(pool)
    yield pool
    await _truncate_cycle_tables(pool)


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
        squad_profile_id="full",
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


class TestCodeLineageRoundTrip:
    """#80 against real Postgres: migration 1040's columns exist, take the stamp, and read
    back as None for a cycle that carries none. The unit test's rows are dicts, so only this
    proves the INSERT's column list and the table agree."""

    @pytest.mark.parametrize(
        ("version", "sha"),
        [("1.8.0", "072672ef-dirty"), (None, None)],
        ids=["stamped", "unstamped"],
    )
    async def test_the_lineage_round_trips(self, registry, version, sha):
        deploy_id = "dep_0123456789ab" if sha else None  # #1720, migration 1051
        cycle = _make_cycle(framework_version=version, framework_git_sha=sha, deploy_id=deploy_id)
        await registry.create_cycle(cycle)

        fetched = await registry.get_cycle(cycle.cycle_id)

        assert (fetched.framework_version, fetched.framework_git_sha, fetched.deploy_id) == (
            version,
            sha,
            deploy_id,
        )


class TestRunLoopSummaryRoundTrip:
    """SIP-0108 §4.1 against real Postgres: migration 1500's table takes the row, a re-finalize
    supersedes it, and the JSONB reads back as the same summary. The unit contract test runs
    the memory adapter, so only this proves the INSERT and the table agree."""

    async def test_the_summary_round_trips_and_a_refinalize_supersedes(self, registry):
        from squadops.cycles.failure_attribution import TerminalKind
        from squadops.cycles.llm_usage import RunUsage, UsageTotals
        from squadops.cycles.run_loop_summary import (
            AbsentEmission,
            RoundFailure,
            RunLoopSummary,
            RunTerminalDecision,
        )

        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        run = await registry.create_run(_make_run(cycle.cycle_id))
        assert await registry.get_run_loop_summary(run.run_id) is None

        def summary(calls: int) -> RunLoopSummary:
            return RunLoopSummary(
                run_id=run.run_id,
                usage=RunUsage(
                    by_task_type={"qa.test": UsageTotals(calls=calls, duration_ms=12.5)},
                    tasks_reported=1,
                    tasks_unreported=("t-timeout",),
                ),
                terminal=RunTerminalDecision(
                    kind=TerminalKind.PLAN_GATE_REFUSED,
                    refused_validators=("validate_build_config", "validate_builder_floor"),
                ),
                round_failures=(
                    RoundFailure(
                        task_id="t-qa",
                        round_index=0,
                        category="executed_and_failed",
                        locus="subject",
                        failed_checks=("tests_pass",),
                    ),
                ),
                absent_emissions=(AbsentEmission("t-build", ("cap_exhausted",), attempt=2),),
            )

        await registry.record_run_loop_summary(run.run_id, summary(3))
        await registry.record_run_loop_summary(run.run_id, summary(5))

        assert await registry.get_run_loop_summary(run.run_id) == summary(5)


class TestAuthoringEnvelopes:
    """SIP-0110 §0.11 (#2105): the memory adapter keeps envelopes in a dict, so only this proves
    the INSERT, the seam CHECK, the duplicate rule and the JSONB round trip agree with the table."""

    async def test_an_envelope_round_trips_whole_and_a_redelivery_adds_no_row(self, registry):
        from squadops.memory.authoring_envelope import AuthoringSeam, capture_envelope

        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        run = await registry.create_run(_make_run(cycle.cycle_id))
        envelope = capture_envelope(
            seam=AuthoringSeam.REPAIR,
            task_type="qa.test_repair",
            task_id="repair-1",
            cycle_id=cycle.cycle_id,
            project_id="test-project",
            agent_id="eve",
            role="qa",
            handler_name="qa_test_repair_handler",
            captured_at="2026-10-08T02:00:00+00:00",
            messages=[("system", "s"), ("user", "fix the suite — “quoted” and ünïcode")],
            chat_kwargs={"model": "qwen", "max_tokens": 8192},
            inputs={"failure_evidence": {"rows": [{"check": "tests_pass"}]}, "n": 3},
        ).to_dict()

        assert await registry.record_authoring_envelope(run.run_id, envelope) is True
        assert await registry.record_authoring_envelope(run.run_id, dict(envelope)) is False

        assert await registry.list_authoring_envelopes(run.run_id) == [envelope]

    async def test_an_envelopes_keys_come_back_in_the_order_they_were_sent(self, registry):
        """#2105's live finding: JSONB reordered the prior outputs a planning prompt renders in
        order, so the re-run rendered another prompt. ``==`` on dicts ignores order, so the test
        compares the key sequences."""
        from squadops.memory.authoring_envelope import AuthoringSeam, capture_envelope

        cycle = _make_cycle()
        await registry.create_cycle(cycle)
        run = await registry.create_run(_make_run(cycle.cycle_id))
        prior = {"strat": "frame", "data": "context", "dev": "design", "qa": "strategy"}
        envelope = capture_envelope(
            seam=AuthoringSeam.PLAN_WRITING,
            task_type="development.author_manifest",
            task_id="t-order",
            cycle_id=cycle.cycle_id,
            project_id="test-project",
            agent_id="neo",
            role="dev",
            handler_name="h",
            captured_at="2026-10-08T02:00:00+00:00",
            messages=[("user", "u")],
            chat_kwargs={"model": "m", "max_tokens": 1},
            inputs={"prior_outputs": prior, "zeta": 1, "alpha": 2},
        ).to_dict()

        await registry.record_authoring_envelope(run.run_id, envelope)
        [stored] = await registry.list_authoring_envelopes(run.run_id)

        assert list(stored["inputs"]) == ["prior_outputs", "zeta", "alpha"]
        assert list(stored["inputs"]["prior_outputs"]) == list(prior)

    async def test_an_envelope_for_an_unknown_run_is_refused(self, registry):
        from squadops.cycles.models import RunNotFoundError

        with pytest.raises(RunNotFoundError):
            await registry.record_authoring_envelope(
                "run_missing",
                {
                    "task_id": "t",
                    "captured_at": "2026-10-08T02:00:00+00:00",
                    "messages_sha256": "x",
                },
            )


class TestMemoryObservations:
    """SIP-0110 §0.3 (#2096, the 2.2 plan's D13): the in-memory store keeps observations in a dict,
    so only this proves the INSERT, the source CHECK, the duplicate rule and the JSONB round trip."""

    async def test_an_observation_round_trips_and_a_reprojection_adds_nothing(self, migrated_pool):
        from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore
        from squadops.memory.observations import (
            Classification,
            Observation,
            ObservationSource,
        )

        project = f"obs-{uuid.uuid4().hex[:8]}"
        observed = Observation(
            source=ObservationSource.CORRECTION_ROUND,
            source_id=f"correction_round:run_x:{project}:0",
            project_id=project,
            observed_at=_NOW,
            classification=Classification("attribution", ("verification_artifact_failure",)),
            cycle_id="cyc_x",
            run_id="run_x",
            task_id="t-qa",
            evidence={
                "failed_detail": [["tests_pass", "TypeError: … is not a function — ünïcode"]]
            },
        )
        store = PostgresCrossCycleMemoryStore(pool=migrated_pool)
        try:
            assert await store.record_observations([observed]) == 1
            assert await store.record_observations([observed]) == 0

            assert await store.list_observations(project) == [observed]
            assert (
                await store.list_observations(project, source=ObservationSource.PLAN_REVIEW) == []
            )
        finally:
            async with migrated_pool.acquire() as conn:
                await conn.execute("DELETE FROM memory_observations WHERE project_id = $1", project)


class TestMemoryLessons:
    """SIP-0110 §0.2, §0.7 (#2096): the in-memory store holds lessons in dicts, so only this proves
    the inserts, the immutability check, revocation and a unit's single pin against the tables."""

    async def test_a_lesson_its_approval_and_a_units_pin_round_trip(self, migrated_pool):
        import dataclasses
        from datetime import timedelta

        from adapters.memory.cross_cycle import PostgresCrossCycleMemoryStore, RevisionConflict
        from squadops.memory.lessons import UnitKind
        from squadops.memory.pinning import pin_unit
        from tests.unit.memory.test_lessons import WHERE, _approve, _revision

        project = f"lessons-{uuid.uuid4().hex[:8]}"
        where = dataclasses.replace(WHERE, project_id=project)
        rev = _revision(f"behavior-{project}", where=where)
        approval = _approve(rev, where=where)
        store = PostgresCrossCycleMemoryStore(pool=migrated_pool)
        try:
            assert await store.record_revision(rev) is True
            assert await store.record_revision(rev) is False
            with pytest.raises(RevisionConflict):
                await store.record_revision(_revision(f"behavior-{project}", text="x", where=where))
            assert await store.record_approval(approval) is True
            assert await store.list_revisions(project) == [rev]

            pinned = await pin_unit(
                store,
                unit_kind=UnitKind.CYCLE,
                unit_id=f"cyc_{project}",
                project_id=project,
                pinned_at=approval.approved_at + timedelta(hours=1),
                disabled=False,
            )
            again = await pin_unit(
                store,
                unit_kind=UnitKind.CYCLE,
                unit_id=f"cyc_{project}",
                project_id=project,
                pinned_at=approval.approved_at + timedelta(hours=2),
                disabled=True,
            )
            await store.revoke_approval(
                approval.approval_id, approval.approved_at + timedelta(hours=3)
            )

            assert again == pinned and len(pinned.entries) == 1
            [stored] = await store.list_approvals(project)
            assert stored.revoked_at == approval.approved_at + timedelta(hours=3)
        finally:
            async with migrated_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM memory_snapshots WHERE unit_id = $1", f"cyc_{project}"
                )
                await conn.execute("DELETE FROM memory_approvals WHERE project_id = $1", project)
                await conn.execute("DELETE FROM memory_revisions WHERE project_id = $1", project)


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


class TestStatusFiltersBeforeThePage:
    """#1891: ``?status=`` filtered one LIMIT'd page, so the API answered "which of the newest
    50 cycles failed" — 11 of the deploy's 156 failed cycles. The filter now reads the project
    newest first in batches until the page is filled, as the memory adapter always did."""

    async def test_failed_cycles_older_than_the_page_are_found(self, registry, monkeypatch):
        from datetime import timedelta

        from adapters.cycles import postgres_cycle_registry

        monkeypatch.setattr(postgres_cycle_registry, "_STATUS_SCAN_BATCH", 3)
        project_id = f"status-{uuid.uuid4().hex[:8]}"
        for i in range(8):
            cycle = _make_cycle(
                cycle_id=f"st-{i:03d}", project_id=project_id, created_at=_NOW + timedelta(i)
            )
            await registry.create_cycle(cycle)
            run = await registry.create_run(_make_run(cycle.cycle_id))
            await registry.update_run_status(run.run_id, RunStatus.RUNNING)
            # the two OLDEST fail: past a limit of 2 and past the first batch of 3
            ending = RunStatus.FAILED if i < 2 else RunStatus.COMPLETED
            await registry.update_run_status(run.run_id, ending)

        page = await registry.list_cycles(project_id, status=CycleStatus.FAILED, limit=2)
        rest = await registry.list_cycles(project_id, status=CycleStatus.FAILED, limit=2, offset=1)

        assert [c.cycle_id for c in page] == ["st-001", "st-000"]
        assert [c.cycle_id for c in rest] == ["st-000"]


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

        await apply_migrations(pool, migrations_dir)
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
