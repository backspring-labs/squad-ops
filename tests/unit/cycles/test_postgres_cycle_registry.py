"""
Tests for PostgresCycleRegistry adapter (asyncpg-backed CycleRegistryPort).

NOTE: Unit tests only assert SQL call patterns and exception mapping.
Concurrency, locking, and uniqueness are validated by integration tests (Phase 3).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.cycles.models import (
    Cycle,
    CycleNotFoundError,
    CycleStatus,
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

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)

_POLICY = TaskFlowPolicy(
    mode="sequential",
    gates=(Gate(name="qa_gate", description="QA check", after_task_types=("dev",)),),
)

_CYCLE = Cycle(
    cycle_id="cyc_001",
    project_id="proj_1",
    created_at=NOW,
    created_by="admin",
    prd_ref=None,
    squad_profile_id="full-squad",
    squad_profile_snapshot_ref="sha256:abc",
    task_flow_policy=_POLICY,
    build_strategy="fresh",
)

_RUN = Run(
    run_id="run_001",
    cycle_id="cyc_001",
    run_number=1,
    status="queued",
    initiated_by="api",
    resolved_config_hash="hash123",
)


# ---------------------------------------------------------------------------
# Async context-manager fakes (asyncpg.Pool.acquire is *not* a coroutine)
# ---------------------------------------------------------------------------


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakeTxnCtx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _make_pool(conn):
    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquireCtx(conn)
    return pool


def _make_conn():
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_FakeTxnCtx())
    return conn


# ---------------------------------------------------------------------------
# Mock asyncpg Record helpers (dict-like since adapter uses row["field"])
# ---------------------------------------------------------------------------


def _cycle_row(**overrides):
    base = {
        "cycle_id": "cyc_001",
        "project_id": "proj_1",
        "created_at": NOW,
        "created_by": "admin",
        "prd_ref": None,
        "squad_profile_id": "full-squad",
        "squad_profile_snapshot_ref": "sha256:abc",
        "task_flow_policy": {
            "mode": "sequential",
            "gates": [
                {
                    "name": "qa_gate",
                    "description": "QA check",
                    "after_task_types": ["dev"],
                }
            ],
        },
        "build_strategy": "fresh",
        "applied_defaults": {},
        "execution_overrides": {},
        "expected_artifact_types": [],
        "experiment_context": {},
        "notes": None,
        "cancelled": False,
    }
    base.update(overrides)
    return base


def _run_row(**overrides):
    base = {
        "run_id": "run_001",
        "cycle_id": "cyc_001",
        "run_number": 1,
        "status": "queued",
        "initiated_by": "api",
        "resolved_config_hash": "hash123",
        "resolved_config_ref": None,
        "started_at": None,
        "finished_at": None,
        "artifact_refs": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestPostgresCycleRegistry:
    # NOTE: Unit tests only assert SQL call patterns and exception mapping.
    # Concurrency, locking, and uniqueness are validated by integration tests (Phase 3).

    @pytest.fixture
    def conn(self):
        return _make_conn()

    @pytest.fixture
    def pool(self, conn):
        return _make_pool(conn)

    @pytest.fixture
    def registry(self, pool):
        from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry

        return PostgresCycleRegistry(pool)

    # ------------------------------------------------------------------
    # 1. create_cycle — verify INSERT called with correct params
    # ------------------------------------------------------------------

    async def test_create_cycle_inserts_row(self, registry, conn):
        conn.execute.return_value = None

        result = await registry.create_cycle(_CYCLE)

        assert result is _CYCLE
        conn.execute.assert_awaited_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO cycle_registry" in sql
        # Verify all 14 positional params ($1 ... $14)
        args = conn.execute.call_args[0][1:]
        assert args[0] == "cyc_001"  # cycle_id
        assert args[1] == "proj_1"  # project_id
        assert args[2] == NOW  # created_at
        assert args[3] == "admin"  # created_by
        assert args[4] is None  # prd_ref
        assert args[5] == "full-squad"  # squad_profile_id
        assert args[6] == "sha256:abc"  # squad_profile_snapshot_ref
        # task_flow_policy is JSON-serialized
        policy_dict = json.loads(args[7])
        assert policy_dict["mode"] == "sequential"
        assert policy_dict["gates"][0]["name"] == "qa_gate"
        assert args[8] == "fresh"  # build_strategy

    # ------------------------------------------------------------------
    # 2. get_cycle — not found raises CycleNotFoundError
    # ------------------------------------------------------------------

    async def test_get_cycle_not_found(self, registry, conn):
        conn.fetchrow.return_value = None

        with pytest.raises(CycleNotFoundError, match="cyc_999"):
            await registry.get_cycle("cyc_999")

        conn.fetchrow.assert_awaited_once()
        sql = conn.fetchrow.call_args[0][0]
        assert "SELECT * FROM cycle_registry" in sql

    # ------------------------------------------------------------------
    # 3. get_cycle — reconstructs frozen dataclass from JSONB row
    # ------------------------------------------------------------------

    async def test_get_cycle_reconstructs_frozen_dataclass(self, registry, conn):
        conn.fetchrow.return_value = _cycle_row()

        cycle = await registry.get_cycle("cyc_001")

        assert isinstance(cycle, Cycle)
        assert cycle.cycle_id == "cyc_001"
        assert cycle.project_id == "proj_1"
        assert cycle.created_at == NOW
        assert isinstance(cycle.task_flow_policy, TaskFlowPolicy)
        assert cycle.task_flow_policy.mode == "sequential"
        assert len(cycle.task_flow_policy.gates) == 1
        gate = cycle.task_flow_policy.gates[0]
        assert isinstance(gate, Gate)
        assert gate.name == "qa_gate"
        assert gate.after_task_types == ("dev",)

    # ------------------------------------------------------------------
    # 4. create_run — cancelled cycle raises IllegalStateTransitionError
    # ------------------------------------------------------------------

    async def test_create_run_on_cancelled_cycle_raises(self, registry, conn):
        conn.fetchrow.return_value = {"cancelled": True}

        with pytest.raises(IllegalStateTransitionError, match="cancelled cycle"):
            await registry.create_run(_RUN)

        # Verify FOR UPDATE lock SQL
        sql = conn.fetchrow.call_args[0][0]
        assert "FOR UPDATE" in sql
        assert "cancelled" in sql.lower()

    # ------------------------------------------------------------------
    # 5. create_run — allocates run_number under lock (FOR UPDATE + MAX+1)
    # ------------------------------------------------------------------

    async def test_create_run_allocates_run_number_under_lock(self, registry, conn):
        # First fetchrow: cycle row (not cancelled)
        conn.fetchrow.return_value = {"cancelled": False}
        # fetchval: COALESCE(MAX(run_number), 0) + 1 = 3
        conn.fetchval.return_value = 3
        conn.execute.return_value = None

        result = await registry.create_run(_RUN)

        # Caller's run_number (1) is ignored; DB-allocated (3) is returned
        assert result.run_number == 3
        assert result.run_id == "run_001"

        # Verify FOR UPDATE on cycle row
        fetchrow_sql = conn.fetchrow.call_args[0][0]
        assert "FOR UPDATE" in fetchrow_sql

        # Verify COALESCE(MAX(run_number), 0) + 1 SQL shape
        fetchval_sql = conn.fetchval.call_args[0][0]
        assert "COALESCE" in fetchval_sql
        assert "MAX(run_number)" in fetchval_sql
        assert "+ 1" in fetchval_sql

        # Verify INSERT INTO cycle_runs with allocated run_number
        execute_sql = conn.execute.call_args[0][0]
        assert "INSERT INTO cycle_runs" in execute_sql
        insert_args = conn.execute.call_args[0][1:]
        assert insert_args[0] == "run_001"  # run_id
        assert insert_args[1] == "cyc_001"  # cycle_id
        assert insert_args[2] == 3  # allocated run_number (not caller's 1)

    # ------------------------------------------------------------------
    # 6. create_run — cycle not found raises CycleNotFoundError
    # ------------------------------------------------------------------

    async def test_create_run_cycle_not_found(self, registry, conn):
        conn.fetchrow.return_value = None

        with pytest.raises(CycleNotFoundError, match="cyc_001"):
            await registry.create_run(_RUN)

    # ------------------------------------------------------------------
    # 7. update_run_status — sets started_at on RUNNING via COALESCE
    # ------------------------------------------------------------------

    async def test_update_run_status_sets_started_at_on_running(self, registry, conn):
        # First call: fetchrow for current status
        conn.fetchrow.side_effect = [
            {"status": "queued"},  # current status lookup
            _run_row(status="running"),  # get_run after update (row)
        ]
        conn.fetch.return_value = []  # gate_rows for get_run
        conn.execute.return_value = None

        await registry.update_run_status("run_001", RunStatus.RUNNING)

        # Find the UPDATE execute call
        execute_calls = conn.execute.call_args_list
        assert len(execute_calls) >= 1
        update_sql = execute_calls[0][0][0]
        assert "UPDATE cycle_runs SET status" in update_sql
        assert "COALESCE(started_at, now())" in update_sql
        # Should NOT contain finished_at
        assert "finished_at" not in update_sql

    # ------------------------------------------------------------------
    # 8. update_run_status — sets finished_at on terminal states
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "terminal_status",
        [
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        ],
    )
    async def test_update_run_status_sets_finished_at_on_terminal(
        self, registry, conn, terminal_status
    ):
        # Map each terminal status to a valid source status
        source_map = {
            RunStatus.COMPLETED: "running",
            RunStatus.FAILED: "running",
            RunStatus.CANCELLED: "running",
        }
        conn.fetchrow.side_effect = [
            {"status": source_map[terminal_status]},  # current status
            _run_row(status=terminal_status.value),  # get_run row
        ]
        conn.fetch.return_value = []  # gate_rows
        conn.execute.return_value = None

        await registry.update_run_status("run_001", terminal_status)

        execute_calls = conn.execute.call_args_list
        update_sql = execute_calls[0][0][0]
        assert "COALESCE(finished_at, now())" in update_sql
        # Should NOT set started_at in this branch
        assert "started_at" not in update_sql

    # ------------------------------------------------------------------
    # 9. update_run_status — not found raises RunNotFoundError
    # ------------------------------------------------------------------

    async def test_update_run_status_not_found(self, registry, conn):
        conn.fetchrow.return_value = None

        with pytest.raises(RunNotFoundError, match="run_999"):
            await registry.update_run_status("run_999", RunStatus.RUNNING)

    # ------------------------------------------------------------------
    # 10. append_artifact_refs — preserves order and deduplicates
    # ------------------------------------------------------------------

    async def test_append_artifact_refs_preserves_order(self, registry, conn):
        # First fetchrow: existing artifact_refs
        conn.fetchrow.side_effect = [
            {"artifact_refs": ["a", "b"]},  # existing refs
            _run_row(artifact_refs=["a", "b", "c"]),  # get_run row after update
        ]
        conn.fetch.return_value = []  # gate_rows for get_run
        conn.execute.return_value = None

        await registry.append_artifact_refs("run_001", ("c", "a"))

        # Verify UPDATE with merged list preserving order: [a, b, c]
        execute_calls = conn.execute.call_args_list
        update_sql = execute_calls[0][0][0]
        assert "UPDATE cycle_runs SET artifact_refs" in update_sql
        # The merged list passed as $1 should be [a, b, c] — 'a' not re-added
        merged = execute_calls[0][0][1]
        assert merged == ["a", "b", "c"]

    # ------------------------------------------------------------------
    # 11. append_artifact_refs — not found raises RunNotFoundError
    # ------------------------------------------------------------------

    async def test_append_artifact_refs_not_found(self, registry, conn):
        conn.fetchrow.return_value = None

        with pytest.raises(RunNotFoundError, match="run_001"):
            await registry.append_artifact_refs("run_001", ("art_1",))

    # ------------------------------------------------------------------
    # 12. record_gate_decision — inserts new decision
    # ------------------------------------------------------------------

    async def test_record_gate_decision_inserts_new(self, registry, conn):
        decision = GateDecision(
            gate_name="qa_gate",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )

        # Sequence of fetchrow calls within record_gate_decision:
        # 1. run_row (FOR UPDATE) — status + cycle_id
        # 2. cycle_row — task_flow_policy
        # 3. existing gate decision — None (new)
        # Then get_run calls fetchrow again for the run + fetch for gate_rows
        conn.fetchrow.side_effect = [
            {"status": "running", "cycle_id": "cyc_001"},  # run FOR UPDATE
            {
                "task_flow_policy": {
                    "mode": "sequential",
                    "gates": [
                        {"name": "qa_gate", "description": "QA check", "after_task_types": ["dev"]}
                    ],
                }
            },  # cycle policy
            None,  # no existing gate decision
            _run_row(status="running"),  # get_run row
        ]
        conn.fetch.return_value = []  # gate_rows for get_run
        conn.execute.return_value = None

        await registry.record_gate_decision("run_001", decision)

        # Verify INSERT INTO cycle_gate_decisions was called
        execute_calls = conn.execute.call_args_list
        assert len(execute_calls) >= 1
        insert_sql = execute_calls[0][0][0]
        assert "INSERT INTO cycle_gate_decisions" in insert_sql
        insert_args = execute_calls[0][0][1:]
        assert insert_args[0] == "run_001"  # run_id
        assert insert_args[1] == "qa_gate"  # gate_name
        assert insert_args[2] == "approved"  # decision
        assert insert_args[3] == "operator"  # decided_by
        assert insert_args[4] == NOW  # decided_at

    # ------------------------------------------------------------------
    # 13. record_gate_decision — idempotent (same decision is no-op)
    # ------------------------------------------------------------------

    async def test_record_gate_decision_idempotent(self, registry, conn):
        decision = GateDecision(
            gate_name="qa_gate",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )

        conn.fetchrow.side_effect = [
            {"status": "running", "cycle_id": "cyc_001"},  # run FOR UPDATE
            {
                "task_flow_policy": {
                    "mode": "sequential",
                    "gates": [
                        {"name": "qa_gate", "description": "QA", "after_task_types": ["dev"]}
                    ],
                }
            },  # cycle policy
            {"decision": "approved"},  # existing — same decision
            _run_row(status="running"),  # get_run row
        ]
        conn.fetch.return_value = []  # gate_rows for get_run

        await registry.record_gate_decision("run_001", decision)

        # No INSERT should have been called — idempotent no-op
        conn.execute.assert_not_awaited()

    # ------------------------------------------------------------------
    # 14. record_gate_decision — conflicting decision raises
    # ------------------------------------------------------------------

    async def test_record_gate_decision_conflict_raises(self, registry, conn):
        decision = GateDecision(
            gate_name="qa_gate",
            decision="rejected",
            decided_by="operator",
            decided_at=NOW,
        )

        conn.fetchrow.side_effect = [
            {"status": "running", "cycle_id": "cyc_001"},  # run FOR UPDATE
            {
                "task_flow_policy": {
                    "mode": "sequential",
                    "gates": [
                        {"name": "qa_gate", "description": "QA", "after_task_types": ["dev"]}
                    ],
                }
            },  # cycle policy
            {"decision": "approved"},  # existing — different decision
        ]

        with pytest.raises(GateAlreadyDecidedError, match="qa_gate"):
            await registry.record_gate_decision("run_001", decision)

    # ------------------------------------------------------------------
    # 15. record_gate_decision — unknown gate raises ValidationError
    # ------------------------------------------------------------------

    async def test_record_gate_decision_unknown_gate_raises(self, registry, conn):
        decision = GateDecision(
            gate_name="nonexistent_gate",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )

        conn.fetchrow.side_effect = [
            {"status": "running", "cycle_id": "cyc_001"},  # run FOR UPDATE
            {
                "task_flow_policy": {
                    "mode": "sequential",
                    "gates": [
                        {"name": "qa_gate", "description": "QA", "after_task_types": ["dev"]}
                    ],
                }
            },  # cycle policy — does NOT contain "nonexistent_gate"
        ]

        with pytest.raises(ValidationError, match="nonexistent_gate"):
            await registry.record_gate_decision("run_001", decision)

    # ------------------------------------------------------------------
    # 16. record_gate_decision — terminal run raises RunTerminalError
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("rejected_status", ["failed", "cancelled"])
    async def test_record_gate_decision_gate_rejected_run_raises(
        self, registry, conn, rejected_status
    ):
        """GATE_REJECTED_STATES (failed/cancelled) raise RunTerminalError."""
        decision = GateDecision(
            gate_name="qa_gate",
            decision="approved",
            decided_by="operator",
            decided_at=NOW,
        )

        conn.fetchrow.side_effect = [
            {"status": rejected_status, "cycle_id": "cyc_001"},
        ]

        with pytest.raises(RunTerminalError, match="gate-rejected run"):
            await registry.record_gate_decision("run_001", decision)

    # ------------------------------------------------------------------
    # 17. list_cycles — N+1 derivation pattern with status filter
    # ------------------------------------------------------------------

    async def test_list_cycles_with_status_filter(self, registry, conn):
        # list_cycles fetches all cycle rows, then for each derives status via
        # _latest_run_for_cycle (N+1 pattern).
        row_active = _cycle_row(cycle_id="cyc_001", cancelled=False)
        row_created = _cycle_row(cycle_id="cyc_002", cancelled=False)

        # First acquire: conn.fetch returns two cycle rows
        # Then for each cycle, _latest_run_for_cycle calls acquire again:
        #   - cyc_001: has a queued run => derives ACTIVE
        #   - cyc_002: no runs => derives CREATED
        conn.fetch.side_effect = [
            [row_active, row_created],  # list_cycles main query
            # _latest_run_for_cycle for cyc_001: gate_rows
            [
                {
                    "gate_name": "qa_gate",
                    "decision": "approved",
                    "decided_by": "op",
                    "decided_at": NOW,
                    "notes": None,
                }
            ],
            # _latest_run_for_cycle for cyc_002: gate_rows (empty, but won't reach)
        ]

        conn.fetchrow.side_effect = [
            # _latest_run_for_cycle for cyc_001: run row
            _run_row(cycle_id="cyc_001", status="queued"),
            # _latest_run_for_cycle for cyc_002: no run
            None,
        ]

        result = await registry.list_cycles("proj_1", status=CycleStatus.ACTIVE)

        # Only cyc_001 should be returned (ACTIVE); cyc_002 is CREATED
        assert len(result) == 1
        assert result[0].cycle_id == "cyc_001"

        # Verify the main query used ORDER BY, LIMIT, OFFSET
        main_fetch_sql = conn.fetch.call_args_list[0][0][0]
        assert "ORDER BY created_at DESC" in main_fetch_sql
        assert "LIMIT" in main_fetch_sql
        assert "OFFSET" in main_fetch_sql

    # ------------------------------------------------------------------
    # 18. list_runs — batch gate fetch via ANY($1) pattern
    # ------------------------------------------------------------------

    async def test_list_runs_batch_gate_fetch(self, registry, conn):
        run_row_1 = _run_row(run_id="run_001", run_number=1)
        run_row_2 = _run_row(run_id="run_002", run_number=2)

        gate_row = {
            "run_id": "run_001",
            "gate_name": "qa_gate",
            "decision": "approved",
            "decided_by": "op",
            "decided_at": NOW,
            "notes": None,
        }

        conn.fetch.side_effect = [
            [run_row_1, run_row_2],  # run rows
            [gate_row],  # gate decisions batch query
        ]

        runs = await registry.list_runs("cyc_001")

        assert len(runs) == 2
        assert runs[0].run_id == "run_001"
        assert runs[1].run_id == "run_002"

        # Verify batch gate query uses ANY($1) pattern
        gate_fetch_sql = conn.fetch.call_args_list[1][0][0]
        assert "ANY($1)" in gate_fetch_sql
        assert "cycle_gate_decisions" in gate_fetch_sql

        # Verify the run_ids list passed to the batch query
        batch_run_ids = conn.fetch.call_args_list[1][0][1]
        assert batch_run_ids == ["run_001", "run_002"]

        # Verify gate decisions are associated correctly
        assert len(runs[0].gate_decisions) == 1
        assert runs[0].gate_decisions[0].gate_name == "qa_gate"
        assert len(runs[1].gate_decisions) == 0
