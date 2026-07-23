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

## RuntimeActivity lifecycle integrity — open requirements (2026-07-23)

**Status:** open — needs a design decision *before* a fix; not a one-line patch.
Surfaced by a smoke cycle (`cyc_1d3960665af6`) where every agent's first cycle task
logged `UniqueViolationError` on `uq_runtime_activities_one_active_per_agent`
(`Key (agent_id)=(eve/data/max) already exists`), swallowed as a best-effort WARNING.

**Why it belongs in this doc.** The canonical signals above derive an agent's
*idle / busy / paused* state from `FocusLease` + `RuntimeActivity` (§10.5). When a
`RuntimeActivity` row orphans (below), `get_current_activity` returns a stale row
indefinitely, so the derived signal reports an agent **busy on a task that ended long
ago**. RuntimeActivity integrity is therefore load-bearing for a claim *this* model makes.

**The mechanism is not a missing close — it's the absence of recovery.** The cycle
dispatcher opens and closes activities correctly on the happy path (`_start_task_activity`
→ try/else/except `_finish_task_activity`, `adapters/cycles/task_dispatcher.py:176-188`).
The failure is structural:

1. **Orphaning.** If the process/container dies between `start_activity` and
   `_finish_task_activity` (crash, `docker restart`, OOM kill), the row stays `running`.
   Nothing terminalizes it on restart — there is no reconciliation. The code concedes it:
   *"a leftover active row from a prior crashed task makes this conflict, which we swallow"*
   (`task_dispatcher.py:199`).
2. **Permanence + poisoning.** The partial unique index (`WHERE state IN
   ('pending','running','paused')`) keeps that orphan "active" forever. From the first
   orphan onward, **every** future `start_activity` for that agent collides and is
   swallowed — the agent never records a new activity again and `get_current_activity`
   is frozen on the orphan.
3. **Advisory writes against a hard invariant.** `start_activity` is deliberately
   best-effort/swallowed (§4.4 — "observability never breaks a real task"), yet the
   invariant it violates is a hard DB constraint. A *dropped* write is silently promoted
   to *permanent* corruption with no path back. The two stances don't compose.

**Requirements to decide (each a fork, not a default):**

1. **Authoritative or advisory?** If RuntimeActivity is advisory telemetry, a hard unique
   index that poisons future writes is the wrong enforcement — replace it with
   supersede-on-write / latest-wins-in-query. If authoritative, it needs a guaranteed close
   **and** crash recovery. Today it is implicitly both. *(Lean: advisory-but-self-healing —
   builds don't depend on it, so favor the lowest-risk coherent stance.)*
2. **Orphan recovery — who heals a stale-active row, on what trigger?** Candidates:
   (a) **supersede-on-start** — `start_activity` terminalizes any existing active row for
   the agent (`aborted`, reason `superseded`) in the same transaction, then inserts
   (self-healing; "current" = latest dispatch); (b) **restart/heartbeat reconciliation** —
   a sweep aborts active rows whose owning process is gone, mirroring the offline
   health-checker; (c) **TTL/lease** — activities expire like `focus_leases` (`expires_at`,
   the `1120` pattern). Not exclusive; (a) is the minimal self-healing floor.
3. **Single owner across writers.** SIP-0089 makes the `RuntimeCoordinator` the activity
   lifecycle owner for mode transitions (`coordinator.py:571` aborts); the cycle dispatcher
   independently opens/closes `mode="cycle"` activities. Two writers, one invariant. The
   contract must state how a coordinator mode-abort and a dispatcher complete/fail interleave
   without corrupting each other — the `update_state` active-only guard covers *some* races
   but is not a stated ownership model.
4. **Crash-recovery contract.** Name what terminalizes activities orphaned by process/
   container death — today: nothing. This is the direct cause of the observed symptom and
   follows from (2).

**Scope.** If the resolution keeps the enforcement stance and adds recovery, it is an
amendment here + a migration. If it changes the SIP-0089 activity lifecycle contract
(§4.2–4.5 — e.g. supersede-on-start becomes normative, or ownership is reassigned), it is a
**SIP-0089 addendum**, not just a doc note. Cycle correctness is unaffected either way: the
swallow keeps builds green — this is agent-status *observability* only.

## Deferred (the rest of #231)

A strangler, not a blocker: collapse `network_status` into `runtime_status` at the
source, and reconcile the accessor names (`get_agent_status` telemetry vs
`get_runtime_state` runtime) once every surface reads from this model.
