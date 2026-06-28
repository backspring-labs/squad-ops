# Agent Status vs Runtime State — Canonical Model

**Status:** canonical reference (SIP-0089) · addresses the terminology half of #231.

SquadOps tracks several overlapping signals about an agent. They are easy to
conflate. This is the canonical model that surfaces (APIs, dashboard, CLI) MUST
conform to. The remaining *consolidation* work (collapsing the legacy field,
renaming the accessors) is tracked in #231.

## The two tables

| Table | Owns | Written by |
|-------|------|-----------|
| `agent_status` | heartbeat **telemetry**: `lifecycle_state`, `last_heartbeat`, `network_status`, `tps`, `memory_count`, `current_task_id` | the agent heartbeat flow (`update_agent_status_in_db`) |
| `agent_runtime_state` (SIP-0089) | **runtime posture + health**: `mode`, `runtime_status`, `focus`, `current_runtime_activity_id`, `interruptibility`, `current_assignment_ref` | the `RuntimeCoordinator` only (D16) — the single mode-writer |

They are intentionally separate (D17: the heartbeat is **non-authoritative** for
runtime state). The health-checker reconciliation loop mirrors an agent that has
gone offline (by heartbeat age) into `agent_runtime_state.runtime_status` so the
coordinator's §11.3 `offline → duty` guard sees a fresh value.

## The canonical signals

- **Mode** (`mode`) — *work posture*: `ambient` | `cycle` | `duty`. What the agent
  is currently doing. Source of truth: `agent_runtime_state.mode`. Only the
  coordinator writes it.
- **Runtime status** (`runtime_status`) — *health / availability*: `online` |
  `degraded` | `recovering` | `offline`. **This is the canonical health signal.**
  Source: `agent_runtime_state.runtime_status`. Whether an agent is "idle",
  "busy", or "paused" is **derived** from FocusLease + RuntimeActivity (§10.5),
  not stored here.
- **Lifecycle state** (`lifecycle_state`, on `agent_status`) — the agent process /
  heartbeat lifecycle (`READY`, etc.). It **feeds** health via
  `runtime_status_from_lifecycle()`; it is not itself the health signal.
- **`network_status`** (computed on `agent_status` from heartbeat age) — a legacy,
  derived reachability flag. **Deprecated** in favour of `runtime_status`; kept
  only for back-compat until the consolidation in #231 lands.

## The rule for surfaces (APIs / dashboard / CLI)

> **Health = `runtime_status`. Posture = `mode`.**
> `lifecycle_state` feeds health; `agent_status` is telemetry; `network_status`
> is legacy-derived — do not introduce new dependencies on it.

Concretely:
- A health pill/badge shows `runtime_status` (falling back to `network_status`
  only for back-compat while an agent has no `agent_runtime_state` row yet).
- A separate posture indicator shows `mode`.
- `GET /health/agents` carries both `runtime_status` and `mode` per agent (plus
  `network_status`/`lifecycle_state` for back-compat); `mode`/`runtime_status`
  are `null` when an agent has no runtime-state row (#230).

## Deferred (the rest of #231)

A strangler, not a blocker: collapse `network_status` into `runtime_status` at the
source, and reconcile the accessor names (`get_agent_status` telemetry vs
`get_runtime_state` runtime) once every surface reads from this model.
