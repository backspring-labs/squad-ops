"""Duty-scheduler bootstrap (SIP-0089 §2.4 activation).

Composition-root helper that assembles the `DutyScheduler` graph for the
runtime-api process. Kept out of `main.py` so the activation gate (the
`runtime.scheduler.enabled` decision and the pool precondition) is unit-testable
without standing up FastAPI.

This is the composition root — it is allowed to import adapters (unlike
`src/squadops/runtime/*`, which D26 keeps adapter-free). It wires:

    PostgresRuntimeState ─┐
    PostgresAssignment ───┤
    PostgresFocusLease ───┤
    PostgresRuntimeActivity ─┼─→ RuntimeCoordinator ─→ DutyScheduler
    LoggingRuntimeEventPublisher ─┘

The `PostgresFocusLease` makes the coordinator's §3.4 lease arbitration live:
opening a duty window acquires the agent's duty FocusLease (preempting a held
cycle lease), and closing it releases the lease (§3.4). lease ≠ mode — the
coordinator still owns the authoritative `mode` write. `PostgresRuntimeActivity`
wires the §4.5 seam (abort an activity orphaned by a mode change); it is a no-op
in v1.1 until handlers emit activities (§4.4), but kept wired for consistency.

**Single-writer constraint:** the `RuntimeCoordinator` is the sole writer of
`AgentRuntimeState.mode` (D16). This is safe only while a *single* runtime-api
instance runs the loop — today's deployment. If runtime-api is ever scaled to
multiple replicas, two schedulers would both write modes; that needs leader
election (e.g. a Postgres advisory lock) before scaling. Deferred while
single-instance; the `enabled` flag keeps activation deliberate.
"""

from __future__ import annotations

import logging

import asyncpg

from squadops.config.schema import AppConfig
from squadops.runtime.coordinator import RuntimeCoordinator
from squadops.runtime.scheduler import DutyScheduler

logger = logging.getLogger(__name__)


def create_runtime_coordinator(pool: asyncpg.Pool | None) -> RuntimeCoordinator | None:
    """Build the single Postgres-backed ``RuntimeCoordinator``, or ``None`` without a pool.

    This is the **one** coordinator instance the composition root shares between
    the cycle executor (recruitment lease acquisition, §3.5/#233) and the duty
    scheduler. Both must drive the *same* instance because the coordinator is the
    sole writer of ``AgentRuntimeState.mode`` (D16) — building a second one would
    create two mode-writers.

    NOT gated on ``scheduler.enabled``: recruitment acquires cycle leases whether
    or not duty scheduling runs. Returns ``None`` only when no pool is available —
    the focus-lease and runtime-state tables both live in Postgres.
    """
    if pool is None:
        return None

    # Imported here (not at module top) so importing this module never pulls the
    # asyncpg adapter stack into processes that only need the factory signature.
    from adapters.events.runtime_event_publisher import LoggingRuntimeEventPublisher
    from adapters.persistence.runtime import (
        PostgresFocusLease,
        PostgresRuntimeActivity,
        PostgresRuntimeState,
        PostgresRuntimeTransaction,
    )

    state = PostgresRuntimeState(pool)
    focus_lease = PostgresFocusLease(pool)
    activity = PostgresRuntimeActivity(pool)
    publisher = LoggingRuntimeEventPublisher()
    # §4.5/D25: the UoW makes the transition's lease+activity+mode writes atomic —
    # a mode-write failure aborts the transaction rather than best-effort compensating.
    transaction = PostgresRuntimeTransaction(pool)
    return RuntimeCoordinator(
        state,
        events_publisher=publisher,
        focus_lease=focus_lease,
        activity=activity,
        transaction=transaction,
    )


def create_duty_scheduler(
    config: AppConfig,
    pool: asyncpg.Pool | None,
    *,
    coordinator: RuntimeCoordinator | None = None,
) -> DutyScheduler | None:
    """Build the duty scheduler, or return ``None`` when it should not run.

    Returns ``None`` (and the caller starts nothing) when the scheduler is
    disabled by config, or when no Postgres pool is available — the assignment
    and runtime-state tables both live in Postgres, so without a pool there is
    nothing to schedule against.

    ``coordinator`` lets the composition root inject the shared single-writer
    coordinator (D16) so the executor and scheduler drive the same instance. When
    omitted (standalone use / unit tests) the scheduler builds its own via
    :func:`create_runtime_coordinator`.
    """
    if not config.runtime.scheduler.enabled:
        logger.info("Duty scheduler disabled (runtime.scheduler.enabled=false)")
        return None

    if pool is None:
        logger.warning("Duty scheduler enabled but no Postgres pool — scheduler not started")
        return None

    # Imported here (not at module top) so importing this module never pulls the
    # asyncpg adapter stack into processes that only need the factory signature.
    from adapters.events.runtime_event_publisher import LoggingRuntimeEventPublisher
    from adapters.persistence.runtime import PostgresRuntimeState
    from adapters.persistence.runtime.assignments_postgres import PostgresAssignment

    state = PostgresRuntimeState(pool)
    assignments = PostgresAssignment(pool)
    publisher = LoggingRuntimeEventPublisher()
    # Share the composition root's single-writer coordinator (D16) when injected;
    # otherwise build one — the standalone path keeps the §3.4/§4.5 wiring intact.
    if coordinator is None:
        coordinator = create_runtime_coordinator(pool)

    poll_interval = config.runtime.scheduler.poll_interval_seconds
    logger.warning(
        "Duty scheduler ACTIVE (poll=%ss). The coordinator is the single writer "
        "of agent runtime mode; run exactly one runtime-api instance with the "
        "scheduler enabled (no leader election yet).",
        poll_interval,
    )
    return DutyScheduler(
        assignments,
        coordinator,
        state,
        events_publisher=publisher,
        poll_interval_seconds=poll_interval,
    )
