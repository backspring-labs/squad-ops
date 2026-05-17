# SIP-0089 Phase 1 — Pre-implementation Spike Notes

Working artifact for plan §1.0. Two spikes required before any code; output gets pasted into the Phase 1 PR body.

---

## Spike 1 — Heartbeat integration (D8) — revised

**Question:** Where is the narrowest place to enrich the heartbeat path with runtime-state without changing agent lifecycle semantics?

**Initial finding (incorrect):** The first read of `agents/entrypoint.py` suggested injecting `RuntimeStatePort` into `HealthCheckHttpReporter` agent-side, then reordering `AgentRunner.start()` to construct the reporter after the system.

**Why that was wrong:** Agents have no direct Postgres dependency today. `HealthCheckHttpReporter` POSTs to `{SQUADOPS_RUNTIME_API_URL}/health/agents/status` over HTTP; only the runtime-api service owns the asyncpg pool. Wiring `RuntimeStatePort` into the agent would have added a brand-new postgres dependency to every agent container — a much larger architectural change than D8 implies.

**Revised decision:**

The integration point is **server-side**, at `POST /agents/status` in `src/squadops/api/routes/platform_health.py` (line 121). The handler already calls `hc.update_agent_status_in_db(...)`; we add a parallel call to `RuntimeStatePort.update_heartbeat(agent_id, runtime_status=...)` against the existing asyncpg pool already held by `HealthChecker`.

Concretely:

1. **No changes to the agent.** `HealthCheckHttpReporter.send_status()` keeps its current payload (agent_id, lifecycle_state, version, tps, memory_count). The reporter does not import or depend on `RuntimeStatePort`.
2. **`HealthChecker` (`src/squadops/api/runtime/health_checker.py`) gains a `runtime_state: RuntimeStatePort` constructor argument.** Wired via the existing health-checker singleton in `api/runtime/deps.py`.
3. **`update_agent_status_in_db` additionally calls `runtime_state.update_heartbeat(agent_id, runtime_status=mapped)`** where `mapped` is derived from `lifecycle_state` via a small helper.
4. **Lifecycle → runtime_status mapping** (locked at end of §1.0):

   | `lifecycle_state` | `runtime_status` |
   |---|---|
   | `STARTING` | `recovering` |
   | `READY` | `online` |
   | `WORKING` | `online` |
   | `BLOCKED` | `degraded` |
   | `CRASHED` | `offline` |
   | `STOPPING` | `recovering` |

   Server-side timeout detection (the agent has not heartbeated for N seconds) → `offline` is Phase-1 in-scope only if trivial to add to the existing reconciliation loop; otherwise deferred.

5. **Coordinator-owned fields stay untouched** (D17). The heartbeat handler calls `update_heartbeat` which writes only `last_heartbeat_at` + `runtime_status`. `ensure_state` is called transparently inside `update_heartbeat`, so the first heartbeat from a new agent creates the row with defaults (`mode=ambient`, `interruptibility=high`).

**Impact on lifecycle semantics:** none. The HTTP heartbeat behaves exactly as today; runtime-api just additionally upserts into `agent_runtime_state`. Failures in the runtime-state write must be isolated (logged, not raised) so they cannot break the existing health-status flow.

**Forbidden-import implication:** `src/squadops/api/runtime/health_checker.py` may import `RuntimeStatePort` (a port). It must NOT import `adapters.persistence.runtime.state_postgres` directly — wiring happens in the bootstrap path, which is the only place adapter imports are permitted. The D26 forbidden-import test will codify this for `health_checker.py` once added.

---

## Spike 2 — Events bridge routing (D22)

**Question:** Do runtime-state events route through the existing `events/bridges/workflow_tracker.py`, or warrant a dedicated `runtime_state` bridge?

**Findings** (`src/squadops/events/bridges/workflow_tracker.py`, 86 lines, last refactored 2026-04-25 in SIP-0087 c3):

- The bridge is structurally **cycle/run/task-shaped, not generic**:
  - `_RUN_STATE_MAP` translates `RUN_STARTED → ("RUNNING", "Running")`, `RUN_COMPLETED → ("COMPLETED", "Completed")`, etc.
  - `_TASK_STATE_MAP` translates `TASK_SUCCEEDED`/`TASK_FAILED` to terminal task-run states.
  - It depends on `flow_run_id` and `task_run_id` in `event.context` — Prefect-specific correlation identifiers.
- The class name was generalized in SIP-0087 c3 (`PrefectBridge` → `WorkflowTrackerBridge`), but the *behavior* remains run/task lifecycle for Prefect tracking. Routing `runtime_state.mode_transition` or `focus_lease.granted` events through it would mean either fabricating run states for non-run concepts, or adding type-discriminating branches that bypass the existing state maps entirely. Both options dilute the bridge's single concern.

**Decision:**

**Dedicated `src/squadops/events/bridges/runtime_state.py` bridge.**

The plan's default rule (D22: "default to dedicated `runtime_state` bridge unless `workflow_tracker` is intentionally generic") applies. The current `workflow_tracker` is not intentionally generic — it's a Prefect-flavored state translator that was renamed to look generic.

The new bridge subscribes to runtime-state events emitted by `src/squadops/runtime/coordinator.py` via the existing `EventPublisherPort`. Initial implementation is minimal: forward events to the event log (postgres) and attach to the active `CorrelationContext` when present (D15). Future SIPs (0090, 0091) extend its subscriber set without touching the workflow_tracker.

**Boundary preserved:** `runtime/coordinator.py` depends on `EventPublisherPort`, not on the bridge directly (D22). The bridge is wired in infrastructure (`src/squadops/events/factory.py` or equivalent) and subscribes to runtime-event types.

**Initial event vocabulary** (locked at end of §1.0, per D14):

| Event name | Reason code examples |
|---|---|
| `runtime_state.mode_transition` | `duty_window_opened`, `duty_window_closed`, `cycle_recruited`, `cycle_completed` |
| `runtime_state.heartbeat_initialized` | (no reason — informational) |
| `runtime_state.heartbeat_recovered` | `runtime_status_changed_to_online` |

Events for `FocusLease` and `Assignment` are deferred to Phases 2/3 but will follow the same event/reason separation (D18).

---

## Pre-Phase-1 checklist

- [x] §1.0 spikes complete (this document)
- [ ] §1.1 — Create `src/squadops/runtime/` package skeleton
- [ ] §1.2 — Migration `1100_agent_runtime_state.sql` + `infra/migrations/README.md` with range registry (per D11)
- [ ] §1.3 — `adapters/persistence/runtime/state_postgres.py`
- [ ] §1.4 — Heartbeat reporter extension per Spike 1 decision
- [ ] §1.5 — `squadops agent state <agent-id>` CLI command
- [ ] §1.6 — Tests including `tests/unit/architecture/test_forbidden_imports.py` (new per D26)
