# SIP-0089 Phase 1 — Pre-implementation Spike Notes

Working artifact for plan §1.0. Two spikes required before any code; output gets pasted into the Phase 1 PR body.

---

## Spike 1 — Entrypoint integration (D8)

**Question:** Where is the narrowest place to enrich heartbeat payloads with runtime-state without changing agent lifecycle semantics?

**Findings** (`src/squadops/agents/entrypoint.py`, 833 lines, last touched by SIP-0087 cleanup):

- `HealthCheckHttpReporter` is constructed in `AgentRunner.start()` at line 156, *before* `_create_system()` builds the ports bundle. It currently takes no constructor arguments and reports only `agent_id`, `lifecycle_state`, and `version` (line 770).
- `_send_heartbeat()` (line 763) is a thin wrapper around `reporter.send_status(...)`. It has no access to `self.system.ports` because the call signature is fixed and the reporter is owned by the runner, not the system.
- `_heartbeat_loop()` (line 738) does not start until line 172 — *after* `_create_system()`. So the reporter is constructed before ports exist, but it does not actually run until after they do.

**Decision:**

Reorder construction in `start()` so the heartbeat reporter is created **after** `_create_system()`, then pass `RuntimeStatePort` to its constructor:

```python
self.system = await self._create_system()
# NEW: pass runtime_state port to the reporter
self._heartbeat_reporter = HealthCheckHttpReporter(
    runtime_state=self.system.ports.runtime_state,
)
```

`HealthCheckHttpReporter.send_status()` then calls `ensure_state(agent_id)` on first heartbeat (idempotent per D17) and `update_heartbeat(agent_id, runtime_status=..., last_heartbeat_at=now)` on every subsequent tick. **It never writes `mode`, `focus`, `current_assignment_ref`, or `current_runtime_activity_id`** — those are coordinator-owned (D16/D17).

**Impact on lifecycle semantics:** none. The reporter still produces the same HTTP heartbeat to the dashboard; it just additionally upserts into `agent_runtime_state` via the new port. If the port is absent or returns an error, the HTTP heartbeat must still succeed (heartbeat is non-authoritative — D17).

**Risk:** the existing `HealthCheckHttpReporter` is in `adapters/observability/healthcheck_http.py`. The port must be an injected dependency, not imported in adapter code (D26 forbidden-import test will catch violations).

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
