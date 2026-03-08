"""Postgres-backed cycle registry adapter (SIP-Postgres-Cycle-Registry).

Implements CycleRegistryPort with durable persistence via asyncpg.
Replaces MemoryCycleRegistry for production use.
"""

from __future__ import annotations

import dataclasses
import json
import logging

import asyncpg

from squadops.cycles.checkpoint import RunCheckpoint
from squadops.cycles.lifecycle import (
    GATE_REJECTED_STATES,
    TERMINAL_STATES,
    derive_cycle_status,
    validate_run_transition,
)
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
from squadops.cycles.pulse_models import PulseVerificationRecord
from squadops.ports.cycles.cycle_registry import CycleRegistryPort

logger = logging.getLogger(__name__)


class PostgresCycleRegistry(CycleRegistryPort):
    """Postgres-backed CycleRegistryPort implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # --- Cycle CRUD ---

    async def create_cycle(self, cycle: Cycle) -> Cycle:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO cycle_registry "
                    "(cycle_id, project_id, created_at, created_by, prd_ref, "
                    "squad_profile_id, squad_profile_snapshot_ref, task_flow_policy, "
                    "build_strategy, applied_defaults, execution_overrides, "
                    "expected_artifact_types, experiment_context, notes) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)",
                    cycle.cycle_id,
                    cycle.project_id,
                    cycle.created_at,
                    cycle.created_by,
                    cycle.prd_ref,
                    cycle.squad_profile_id,
                    cycle.squad_profile_snapshot_ref,
                    json.dumps(_policy_to_dict(cycle.task_flow_policy)),
                    cycle.build_strategy,
                    json.dumps(cycle.applied_defaults),
                    json.dumps(cycle.execution_overrides),
                    list(cycle.expected_artifact_types),
                    json.dumps(cycle.experiment_context),
                    cycle.notes,
                )
        except asyncpg.UniqueViolationError as err:
            raise ValidationError(f"Cycle already exists: {cycle.cycle_id}") from err
        return cycle

    async def get_cycle(self, cycle_id: str) -> Cycle:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM cycle_registry WHERE cycle_id = $1", cycle_id)
        if row is None:
            raise CycleNotFoundError(f"Cycle not found: {cycle_id}")
        return self._row_to_cycle(row)

    async def list_cycles(
        self,
        project_id: str,
        *,
        status: CycleStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Cycle]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM cycle_registry WHERE project_id = $1 "
                "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                project_id,
                limit,
                offset,
            )
        if status is None:
            return [self._row_to_cycle(r) for r in rows]

        # N+1 correctness path (D6): derive status via _latest_run_for_cycle
        result = []
        for row in rows:
            cycle = self._row_to_cycle(row)
            latest = await self._latest_run_for_cycle(cycle.cycle_id)
            derived = derive_cycle_status(
                [latest] if latest else [],
                cycle_cancelled=row["cancelled"],
            )
            if derived == status:
                result.append(cycle)
        return result

    async def cancel_cycle(self, cycle_id: str) -> None:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE cycle_registry SET cancelled = TRUE WHERE cycle_id = $1",
                cycle_id,
            )
        if result == "UPDATE 0":
            raise CycleNotFoundError(f"Cycle not found: {cycle_id}")

    # --- Run CRUD ---

    async def create_run(self, run: Run) -> Run:
        async with self._pool.acquire() as conn:
            async with conn.transaction(isolation="serializable"):
                # Lock cycle row and check cancelled (D2, D8)
                cycle_row = await conn.fetchrow(
                    "SELECT cancelled FROM cycle_registry WHERE cycle_id = $1 FOR UPDATE",
                    run.cycle_id,
                )
                if cycle_row is None:
                    raise CycleNotFoundError(f"Cycle not found: {run.cycle_id}")
                if cycle_row["cancelled"]:
                    raise IllegalStateTransitionError(
                        f"Cannot create run on cancelled cycle: {run.cycle_id}"
                    )

                # Allocate next run_number under the lock
                next_num = await conn.fetchval(
                    "SELECT COALESCE(MAX(run_number), 0) + 1 FROM cycle_runs WHERE cycle_id = $1",
                    run.cycle_id,
                )

                # Insert with allocated run_number (caller's run_number is ignored)
                await conn.execute(
                    "INSERT INTO cycle_runs "
                    "(run_id, cycle_id, run_number, status, initiated_by, "
                    "resolved_config_hash, resolved_config_ref, workload_type) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                    run.run_id,
                    run.cycle_id,
                    next_num,
                    run.status,
                    run.initiated_by,
                    run.resolved_config_hash,
                    run.resolved_config_ref,
                    run.workload_type,
                )
        return dataclasses.replace(run, run_number=next_num)

    async def get_run(self, run_id: str) -> Run:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM cycle_runs WHERE run_id = $1", run_id)
            if row is None:
                raise RunNotFoundError(f"Run not found: {run_id}")
            gate_rows = await conn.fetch(
                "SELECT gate_name, decision, decided_by, decided_at, notes "
                "FROM cycle_gate_decisions WHERE run_id = $1 ORDER BY id",
                run_id,
            )
        return self._assemble_run(row, gate_rows)

    async def list_runs(
        self,
        cycle_id: str,
        *,
        workload_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Run]:
        async with self._pool.acquire() as conn:
            if workload_type is not None:
                run_rows = await conn.fetch(
                    "SELECT * FROM cycle_runs WHERE cycle_id = $1 AND workload_type = $2 "
                    "ORDER BY run_number LIMIT $3 OFFSET $4",
                    cycle_id,
                    workload_type,
                    limit,
                    offset,
                )
            else:
                run_rows = await conn.fetch(
                    "SELECT * FROM cycle_runs WHERE cycle_id = $1 "
                    "ORDER BY run_number LIMIT $2 OFFSET $3",
                    cycle_id,
                    limit,
                    offset,
                )
            if not run_rows:
                return []

            run_ids = [r["run_id"] for r in run_rows]
            gate_rows = await conn.fetch(
                "SELECT run_id, gate_name, decision, decided_by, decided_at, notes "
                "FROM cycle_gate_decisions WHERE run_id = ANY($1) ORDER BY id",
                run_ids,
            )

        gates_by_run: dict[str, list] = {}
        for g in gate_rows:
            gates_by_run.setdefault(g["run_id"], []).append(g)

        return [self._assemble_run(r, gates_by_run.get(r["run_id"], [])) for r in run_rows]

    async def update_run_status(self, run_id: str, status: RunStatus) -> Run:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT status FROM cycle_runs WHERE run_id = $1", run_id)
            if row is None:
                raise RunNotFoundError(f"Run not found: {run_id}")

            current = RunStatus(row["status"])
            validate_run_transition(current, status)

            # COALESCE timestamps: set exactly once (§5.2.1)
            if status == RunStatus.RUNNING:
                await conn.execute(
                    "UPDATE cycle_runs SET status = $1, "
                    "started_at = COALESCE(started_at, now()) "
                    "WHERE run_id = $2",
                    status.value,
                    run_id,
                )
            elif status in TERMINAL_STATES:
                await conn.execute(
                    "UPDATE cycle_runs SET status = $1, "
                    "finished_at = COALESCE(finished_at, now()) "
                    "WHERE run_id = $2",
                    status.value,
                    run_id,
                )
            else:
                await conn.execute(
                    "UPDATE cycle_runs SET status = $1 WHERE run_id = $2",
                    status.value,
                    run_id,
                )
        return await self.get_run(run_id)

    async def cancel_run(self, run_id: str) -> None:
        await self.update_run_status(run_id, RunStatus.CANCELLED)

    async def append_artifact_refs(self, run_id: str, artifact_ids: tuple[str, ...]) -> Run:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT artifact_refs FROM cycle_runs WHERE run_id = $1", run_id
            )
            if row is None:
                raise RunNotFoundError(f"Run not found: {run_id}")

            # Python de-duplication preserving order (D5)
            existing = list(row["artifact_refs"])
            existing_set = set(existing)
            for aid in artifact_ids:
                if aid not in existing_set:
                    existing.append(aid)
                    existing_set.add(aid)

            await conn.execute(
                "UPDATE cycle_runs SET artifact_refs = $1 WHERE run_id = $2",
                existing,
                run_id,
            )
        return await self.get_run(run_id)

    # --- Gate decisions ---

    async def record_gate_decision(self, run_id: str, decision: GateDecision) -> Run:
        async with self._pool.acquire() as conn:
            async with conn.transaction(isolation="read_committed"):
                # 1. Load run + validate not terminal
                run_row = await conn.fetchrow(
                    "SELECT status, cycle_id FROM cycle_runs WHERE run_id = $1 FOR UPDATE",
                    run_id,
                )
                if run_row is None:
                    raise RunNotFoundError(f"Run not found: {run_id}")
                if RunStatus(run_row["status"]) in GATE_REJECTED_STATES:
                    raise RunTerminalError(
                        f"Cannot record gate decision on terminal run (status={run_row['status']})"
                    )

                # 2. Validate gate_name exists in cycle's policy
                cycle_row = await conn.fetchrow(
                    "SELECT task_flow_policy FROM cycle_registry WHERE cycle_id = $1",
                    run_row["cycle_id"],
                )
                if cycle_row is None:
                    raise CycleNotFoundError(f"Cycle not found: {run_row['cycle_id']}")
                policy = self._parse_jsonb(cycle_row["task_flow_policy"])
                gate_names = {g["name"] for g in policy.get("gates", ())}
                if decision.gate_name not in gate_names:
                    raise ValidationError(
                        f"Gate {decision.gate_name!r} not found in TaskFlowPolicy"
                    )

                # 3. Check existing decision for this gate
                existing = await conn.fetchrow(
                    "SELECT decision FROM cycle_gate_decisions "
                    "WHERE run_id = $1 AND gate_name = $2",
                    run_id,
                    decision.gate_name,
                )
                if existing is not None:
                    if existing["decision"] == decision.decision:
                        # Idempotent — same decision is a no-op
                        return await self.get_run(run_id)
                    else:
                        raise GateAlreadyDecidedError(
                            f"Gate {decision.gate_name!r} already decided "
                            f"as {existing['decision']!r}"
                        )

                # 4. Insert new decision (decided_at is caller-provided, D4)
                try:
                    await conn.execute(
                        "INSERT INTO cycle_gate_decisions "
                        "(run_id, gate_name, decision, decided_by, decided_at, notes) "
                        "VALUES ($1, $2, $3, $4, $5, $6)",
                        run_id,
                        decision.gate_name,
                        decision.decision,
                        decision.decided_by,
                        decision.decided_at,
                        decision.notes,
                    )
                except asyncpg.UniqueViolationError as err:
                    # Safety net: concurrent race between two transactions
                    raise GateAlreadyDecidedError(
                        f"Gate {decision.gate_name!r} already decided (concurrent race)"
                    ) from err

        return await self.get_run(run_id)

    # --- Pulse Verification (SIP-0070) ---

    async def record_pulse_verification(self, run_id: str, record: PulseVerificationRecord) -> Run:
        """Persist a pulse verification record to Postgres."""
        async with self._pool.acquire() as conn:
            # Validate run exists and is not terminal
            row = await conn.fetchrow("SELECT status FROM cycle_runs WHERE run_id = $1", run_id)
            if row is None:
                raise RunNotFoundError(f"Run not found: {run_id}")
            if RunStatus(row["status"]) in TERMINAL_STATES:
                raise RunTerminalError(
                    f"Cannot record pulse verification on terminal run (status={row['status']})"
                )

            await conn.execute(
                "INSERT INTO pulse_verification_records "
                "(run_id, suite_id, boundary_id, cadence_interval_id, "
                "suite_outcome, repair_attempt, check_results, "
                "repair_task_refs, notes, recorded_at) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)",
                run_id,
                record.suite_id,
                record.boundary_id,
                record.cadence_interval_id,
                record.suite_outcome.value,
                record.repair_attempt_number,
                json.dumps(list(record.check_results)),
                list(record.repair_task_refs),
                record.notes,
                record.recorded_at,
            )
        return await self.get_run(run_id)

    # --- Checkpoint (SIP-0079) ---

    async def save_checkpoint(self, checkpoint: RunCheckpoint, max_keep: int = 5) -> None:
        """Persist a run checkpoint, pruning older checkpoints beyond max_keep."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO run_checkpoints "
                    "(run_id, checkpoint_index, completed_task_ids, prior_outputs, "
                    "artifact_refs, plan_delta_refs, created_at) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    checkpoint.run_id,
                    checkpoint.checkpoint_index,
                    json.dumps(list(checkpoint.completed_task_ids)),
                    json.dumps(checkpoint.prior_outputs),
                    json.dumps(list(checkpoint.artifact_refs)),
                    json.dumps(list(checkpoint.plan_delta_refs)),
                    checkpoint.created_at,
                )
                # Prune: keep only the latest max_keep checkpoints
                await conn.execute(
                    "DELETE FROM run_checkpoints WHERE run_id = $1 "
                    "AND checkpoint_index NOT IN ("
                    "  SELECT checkpoint_index FROM run_checkpoints "
                    "  WHERE run_id = $1 ORDER BY checkpoint_index DESC LIMIT $2"
                    ")",
                    checkpoint.run_id,
                    max_keep,
                )

    async def get_latest_checkpoint(self, run_id: str) -> RunCheckpoint | None:
        """Return the latest checkpoint for a run, or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM run_checkpoints WHERE run_id = $1 "
                "ORDER BY checkpoint_index DESC LIMIT 1",
                run_id,
            )
        if row is None:
            return None
        return self._row_to_checkpoint(row)

    async def list_checkpoints(self, run_id: str) -> list[RunCheckpoint]:
        """Return all checkpoints for a run, ordered by checkpoint_index ascending."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM run_checkpoints WHERE run_id = $1 "
                "ORDER BY checkpoint_index ASC",
                run_id,
            )
        return [self._row_to_checkpoint(r) for r in rows]

    # --- Internal helpers ---

    @staticmethod
    def _parse_jsonb(value):
        """Decode a JSONB column value (asyncpg returns str by default)."""
        if isinstance(value, str):
            return json.loads(value)
        return value  # already a dict (e.g. in tests or with custom codec)

    def _row_to_cycle(self, row: asyncpg.Record) -> Cycle:
        """Reconstruct frozen Cycle from asyncpg Record."""
        tfp = self._parse_jsonb(row["task_flow_policy"])
        gates = tuple(
            Gate(
                name=g["name"],
                description=g["description"],
                after_task_types=tuple(g["after_task_types"]),
            )
            for g in tfp.get("gates", ())
        )
        applied = self._parse_jsonb(row["applied_defaults"]) or {}
        overrides = self._parse_jsonb(row["execution_overrides"]) or {}
        experiment = self._parse_jsonb(row["experiment_context"]) or {}
        return Cycle(
            cycle_id=row["cycle_id"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            created_by=row["created_by"],
            prd_ref=row["prd_ref"],
            squad_profile_id=row["squad_profile_id"],
            squad_profile_snapshot_ref=row["squad_profile_snapshot_ref"],
            task_flow_policy=TaskFlowPolicy(mode=tfp["mode"], gates=gates),
            build_strategy=row["build_strategy"],
            applied_defaults=applied,
            execution_overrides=overrides,
            expected_artifact_types=tuple(row["expected_artifact_types"] or []),
            experiment_context=experiment,
            notes=row["notes"],
        )

    def _assemble_run(self, row: asyncpg.Record, gate_rows: list) -> Run:
        """Reconstruct frozen Run from row + gate decision rows."""
        gate_decisions = tuple(
            GateDecision(
                gate_name=g["gate_name"],
                decision=g["decision"],
                decided_by=g["decided_by"],
                decided_at=g["decided_at"],
                notes=g.get("notes"),
            )
            for g in gate_rows
        )
        return Run(
            run_id=row["run_id"],
            cycle_id=row["cycle_id"],
            run_number=row["run_number"],
            status=row["status"],
            initiated_by=row["initiated_by"],
            resolved_config_hash=row["resolved_config_hash"],
            resolved_config_ref=row.get("resolved_config_ref"),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            gate_decisions=gate_decisions,
            artifact_refs=tuple(row["artifact_refs"] or []),
            workload_type=row.get("workload_type"),
        )

    def _row_to_checkpoint(self, row: asyncpg.Record) -> RunCheckpoint:
        """Reconstruct frozen RunCheckpoint from asyncpg Record."""
        return RunCheckpoint(
            run_id=row["run_id"],
            checkpoint_index=row["checkpoint_index"],
            completed_task_ids=tuple(self._parse_jsonb(row["completed_task_ids"])),
            prior_outputs=self._parse_jsonb(row["prior_outputs"]),
            artifact_refs=tuple(self._parse_jsonb(row["artifact_refs"])),
            plan_delta_refs=tuple(self._parse_jsonb(row["plan_delta_refs"])),
            created_at=row["created_at"],
        )

    async def _latest_run_for_cycle(self, cycle_id: str) -> Run | None:
        """Fetch the single most recent run for status derivation (D6)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM cycle_runs WHERE cycle_id = $1 ORDER BY run_number DESC LIMIT 1",
                cycle_id,
            )
            if row is None:
                return None
            gate_rows = await conn.fetch(
                "SELECT gate_name, decision, decided_by, decided_at, notes "
                "FROM cycle_gate_decisions WHERE run_id = $1 ORDER BY id",
                row["run_id"],
            )
        return self._assemble_run(row, gate_rows)


# --- Helpers ---


def _policy_to_dict(policy: TaskFlowPolicy) -> dict:
    """Serialize TaskFlowPolicy to JSON-compatible dict."""
    return {
        "mode": policy.mode,
        "gates": [
            {
                "name": g.name,
                "description": g.description,
                "after_task_types": list(g.after_task_types),
            }
            for g in policy.gates
        ],
    }
