# SIP-0089: Agent Runtime State — Implementation Plan

**Status:** Draft (under review — revision 2 incorporates plan-PR review feedback)
**Targets:** SquadOps v1.1
**Created:** 2026-04-25
**Owner:** Jason Ladd
**Source SIPs:** SIP-0088 (umbrella constraints), SIP-0089 (scope)

---

## Context

This plan implements the v1.1 runtime-state foundation: making persistent SquadOps agents observable, schedulable, and recallable through five primitives — `RuntimeMode`, `Assignment`/`DutyWindow`, `FocusLease`, `RuntimeActivity`, and `runtime_status`. It is the first of three planned releases that emerged from splitting the Agent Runtime Modes umbrella proposal.

This is a **runtime coordination layer**, not a replacement for cycle, workload, task, or handler execution. Existing execution paths continue to do the work; the new primitives observe and arbitrate.

**The runtime coordinator is the only component allowed to perform authoritative `RuntimeMode` transitions.** Reporters, schedulers, handlers, CLI commands, and future durability adapters may *request* transitions, but the coordinator validates and applies them. This invariant is the spine of v1.1; almost every binding decision below derives from it.

Embodiment (Discord, browser, eventually Minecraft) and durable workflows (Temporal) are explicitly **out of scope** for v1.1. They are addressed by sibling SIPs targeting v1.2 (SIP-0090) and v1.3 (SIP-0091).

---

## Recent main activity (review-time snapshot, 2026-04-25)

Significant changes landed on main between plan drafting and this PR. Reviewers should be aware:

- **Version bumped to 1.0.5** with SIP-0087 (Prefect Task-Scoped Log Streaming) implementation merged and promoted to `implemented/`.
- **New ports:** `src/squadops/ports/cycles/workflow_tracker.py` and `src/squadops/ports/observability/log_forwarder.py`. These are patterns the Phase 1 runtime-state port should mirror for consistency.
- **Events bridge refactored:** `events/bridges/langfuse.py` → `llm_observability.py`, `events/bridges/prefect.py` deleted, `events/bridges/workflow_tracker.py` added. Per D22, runtime-state events route through `workflow_tracker` *only if* it is intentionally generic; otherwise a dedicated `runtime_state` bridge is created.
- **`src/squadops/agents/entrypoint.py` significantly extended** (+62 lines). Phase 1 heartbeat changes (D8) need a pre-implementation spike to confirm the integration seam is still clean.
- **New telemetry primitive:** `src/squadops/telemetry/context.py` (`CorrelationContext`). D15 specifies usage when present; runtime-state operations must not require it.

These do not block the plan, but D8/D14/D15/D22 explicitly require validation against the new code before implementation.

---

## Source SIPs

Implementation work derives from two source documents that play different roles:

| Source | Role | Path |
|--------|------|------|
| **SIP-0089: Agent Runtime State** | Scope of work — phases, primitives, data model, acceptance criteria | `sips/accepted/SIP-0089-Agent-Runtime-State.md` |
| **SIP-0088: Agent Runtime Modes (umbrella)** | Normative constraints — package invariant, conceptual boundary table, canonical terminology, reason codes, event names | `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` |

The umbrella SIP is **not optional reading**. Every PR in this plan must conform to:

- The package invariant: no primitive may be used as a hidden substitute for another
- The conceptual boundary table: each primitive owns only what it is supposed to own
- The canonical terminology: `RuntimeMode`, `RuntimeActivity`, `FocusLease`, `Assignment`, `DutyWindow` (no unqualified `Activity` in code/schema — collides with Temporal's concept)
- The canonical reason codes and event names: shared across the SIP-0089/0090/0091 package
- **The distinction between event, reason code, and state value** — per D18, events describe *what happened*, reason codes describe *why a decision happened*, state values describe *current condition*. None may stand in for another.

---

## Out of Scope for v1.1

These SIPs are accepted but not implemented in v1.1:

- `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2)
- `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3)

v1.1 must, however, leave clean seams for both:

- The **ambient irreversibility rule** (no irreversible action without `FocusLease` + `RuntimeActivity`) is encoded in policy from v1.1, even though it isn't fully testable until v1.2 introduces embodiment. The v1.1 policy gate is intentionally a **seam** — it must be testable, but it must not invent fake embodied actions just to prove the future embodiment path.
- The `DutyWindow` scheduler is in-process; the Temporal adapter in v1.3 will sit behind the same port.

---

## Branching Strategy

All implementation work happens on short-lived feature branches merged to main via PR. **No long-lived `v1.1` branch.** The Spark continues 1.0.x cycle hardening on main in parallel; small PRs reduce drift.

```bash
git checkout -b feature/sip-0089-runtime-state-phase-N
```

- One PR per phase (5 PRs total: Phase 0–4) — keeps review scope manageable
- Each phase must pass `./scripts/dev/run_regression_tests.sh -v` before merge
- PR title format: `feat: SIP-0089 Phase N — <description>`
- PR body references SIP-0089, SIP-0088, this plan, **and the boundary checklist below**
- **No `pyproject.toml` version bump until Phase 4 acceptance.** `1.1.0` lands as a single coordinated commit on main when implementation is feature-complete.

### PR boundary checklist (paste into every phase PR body)

- [ ] Does this PR introduce a new execution path? It should not.
- [ ] Does this PR use `RuntimeActivity` only as observation/control state, not as an executor? It should.
- [ ] Does this PR keep `RuntimeMode` transitions coordinator-owned (no scheduler/heartbeat/handler shortcutting)? It should.
- [ ] Does this PR avoid embodiment and Temporal concerns? It should.
- [ ] Does this PR separate event names (what happened) from reason codes (why)? It must.
- [ ] Does this PR include canonical name usage (`RuntimeMode`, `RuntimeActivity`, etc.) from the first commit? It must.

---

## Cross-Cutting Requirements (carry through every phase)

These derive from the umbrella SIP and the v1.1 coordinator-authority invariant. Pin them in PR review:

1. **Canonical names in code from the first commit.** `RuntimeMode`, `RuntimeActivity`, `FocusLease`, `Assignment`, `DutyWindow`. Renaming later is painful.
2. **Every transition emits a reason-coded event.** Use the canonical reason codes and event names from SIP-0088. No bespoke names.
3. **Package invariant enforced in review.** Reject any code that uses one primitive as a hidden substitute for another (e.g., conflating `runtime_status` with mode, or making `RuntimeActivity` a parallel execution engine).
4. **Ambient irreversibility hook present from Phase 4.** Even without embodiment, the policy gate must exist so v1.2 plugs in cleanly.
5. **Heartbeat is not a transition authority.** It updates liveness/health; it does not set mode against coordinator-owned state.
6. **Scheduler is not a semantic authority.** It detects timing; it requests transitions through the coordinator.
7. **`RuntimeActivity` does not execute work.** Existing handlers and runners do; they emit RuntimeActivity records as observation.
8. **`FocusLease` does not imply `RuntimeMode`.** Acquiring a lease does not transition mode; only the coordinator does.
9. **Hexagonal boundaries enforced by `tests/unit/architecture/test_forbidden_imports.py`** (per D26). New modules added in any phase must pass the import test in CI.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | All new primitives live in `src/squadops/runtime/` (new package). Persistence adapters stay outside. CLI commands must not import Postgres adapters directly | Keeps runtime-coordination layer distinct; matches hexagonal pattern |
| D2 | Postgres is the persistence backend; reuse the existing `DbRuntime` connection pool | Cycle registry already lives there (SIP-0067). Migrations sequenced per D11 |
| D3 | `RuntimeMode`, `runtime_status`, `RuntimeActivity.state` are string-valued enums in DB **with `Literal` types or constants in code** to prevent typo-driven drift. DB migrations include CHECK constraints for known values | Matches existing patterns; CHECK constraint catches invalid writes at DB level, not just test level |
| D4 | `RuntimeActivity` is **emitted by existing handlers and workload runners**, not a new execution engine. Handlers do not import persistence adapters; they call a small `RuntimeActivityReporter`/`RuntimeActivityService` injected via ports | Per package invariant. Hexagonal seam keeps handlers decoupled from runtime-state plumbing |
| D5 | `FocusLease` resolution returns one of `granted | rejected | preempting`. **`queued` is recognized as a v1.2+ outcome and is NOT implemented in v1.1** (per D20). Requests that would require queueing return `rejected` with reason `focus_lease_queueing_not_supported_in_v1.1` | Frozen v1.1 outcomes; avoids fake semantics |
| D6 | `runtime_status` is scoped to health only: `online | degraded | recovering | offline`. CLI may *display* derived availability (`idle`/`busy`/`paused`) computed from FocusLease + RuntimeActivity, but it is never *stored* in `runtime_status` | Per umbrella boundary table |
| D7 | Pre-duty reserve buffer defaults: hard duty `reserve_before_window=15min, reserve_after_window=0`; soft duty `reserve_before_window=0, reserve_after_window=0`. Both fields exist on every Assignment | Per SIP-0089 §11.4; explicit defaults prevent NULL ambiguity |
| D8 | Heartbeat extension carries mode/focus/runtime_status as **reported observations only**. See D17 for non-authoritative semantics. Pre-implementation spike confirms integration with post-1.0.5 `agents/entrypoint.py` | Cheapest path; existing wiring proven, but entrypoint changed in 1.0.5 |
| D9 | **Hard invariant:** in v1.1, an agent has at most one current `RuntimeActivity`. Multi-activity support is explicitly deferred and must not be simulated through multiple active rows, overloaded `source_ref` values, or multiple focus-like fields | Forces clarity; matches partial unique index in Phase 4 |
| D10 | `Assignment` cardinality: many-per-agent permitted; exactly one current `RuntimeMode`; at most one primary `FocusLease` | Per SIP-0089 §10.2 |
| D11 | Postgres migration sequence reservations: `1000–1099` for 1.0.x hardening, `1100–1199` for SIP-0089 (this plan), `1200–1299` tentatively for SIP-0090, `1300–1399` tentatively for SIP-0091. **A migration-range note is added to `infra/migrations/README.md` (or equivalent) before Phase 1 merge** to make the coordination mechanical, not just verbal | Range reservation prevents collision with parallel Spark work |
| D12 | All transition handlers are idempotent on the key `(agent_id, transition_type, owner_ref OR assignment_id, scheduled_at)`. The `owner_ref`/`assignment_id` component prevents collision when two assignments fire the same transition type at the same instant | Required for v1.3 Temporal integration; cheaper to build in from day one |
| D13 | Direct human interaction stays cross-cutting per umbrella policy table; no new mode-like field | Hard rule from "what must not happen" |
| D14 | Reason codes and event names are defined as string constants in `src/squadops/runtime/events.py` (events) and `src/squadops/runtime/reasons.py` (or clearly separated sections in one file). Single canonical source. **A short event-vocabulary normalization pass happens before Phase 1 implementation, then they become locked v1.1 constants** | Prevents drift; per D18, events and reasons must not be conflated |
| D15 | Runtime-state events propagate via `CorrelationContext` (`src/squadops/telemetry/context.py`) **when present**. Operations must not require it; absent context produces a valid event with generated/null correlation | Reuses existing trace-correlation seam without coupling runtime state to it |
| D16 | **Coordinator-authoritative invariant:** the `src/squadops/runtime/coordinator.py` component is the only code that performs `RuntimeMode` transitions. Schedulers, heartbeats, handlers, CLI commands, and future durability adapters may *request* transitions; only the coordinator validates and applies | Single source of truth for mode state |
| D17 | **Heartbeat non-authoritative for mode:** heartbeat may initialize missing runtime state (`mode=ambient, runtime_status=online`) and update `last_heartbeat_at` + `runtime_status`. It must not overwrite coordinator-owned `mode`, `focus`, `current_assignment_ref`, or `current_runtime_activity_id` with defaults | Prevents heartbeat from racing the scheduler/coordinator |
| D18 | **Event names and reason codes are distinct.** Events describe what happened (`cycle.recruitment.rejected`). Reason codes describe why a decision happened (`upcoming_hard_duty_window`). Both are canonical constants; neither stands in for the other | Avoids the conflated "long reason-as-event-name" trap |
| D19 | **`RuntimeActivity` granularity is task/handler-level for v1.1 cycle execution.** Workload boundaries continue to emit workflow/cycle events but **must not** create a competing active `RuntimeActivity` under D9's strict-one rule. Workload context is metadata on the task-level RuntimeActivity (e.g., `source_ref` carries `workload_id`) | Resolves D9-vs-Phase-4 conflict in original draft |
| D20 | **FocusLease queueing is deferred to v1.2+.** v1.1 implements `granted | rejected | preempting` only. Requests that would have queued are rejected with reason `focus_lease_queueing_not_supported_in_v1.1`. Reintroducing `queued` in a future version requires queue persistence storage, a queue-draining processor, and ordering tests | Frozen for v1.1 — prevents queue infrastructure from sneaking in under time pressure |
| D21 | **Scheduler is a claimant, not an authority:** the in-process scheduler detects duty-window timing and submits transition requests to the coordinator. It does not directly mutate `AgentRuntimeState`. Repeated scheduler ticks within the same window must be idempotent (window-open transition fires exactly once per assignment/window) | Prevents duplicate transition events from polling |
| D22 | **Runtime events use shared event infrastructure without semantic leakage.** Routes through `events/bridges/workflow_tracker.py` only if that bridge is intentionally generic. If it is cycle/workflow-specific, a dedicated `events/bridges/runtime_state.py` is introduced. Decision is made during the Phase 1 spike, not deferred to Phase 4 | Avoids contorting runtime events into workflow shapes |
| D23 | **`current_assignment_ref` is active-only, not upcoming.** It is `null` unless the agent is currently operating under that assignment's mode. Future or queued assignments are queried via `AssignmentPort.list_assignments_for_agent`, never copied into `AgentRuntimeState` | Preserves the Mode vs Assignment boundary; prevents `current_assignment_ref` from drifting into "next thing that may claim me" semantics |
| D24 | **Cycle ownership uses `FocusLease.owner_type=cycle` + `owner_ref=<cycle/task identifier>`** without requiring a synthetic `Assignment` row. `Assignment` remains primarily for duty / reserve / cycle_eligibility commitments. Ordinary cycle execution does not create an assignment | Prevents implementers from creating dummy assignment rows for normal cycle work |
| D25 | **Coordinator transitions execute in one Postgres transaction where practical.** All v1.1 runtime ports share the `DbRuntime` pool, so the §4.5 transition steps that touch `AgentRuntimeState`, `FocusLease`, and `RuntimeActivity` are wrapped in a single DB transaction. The §4.5 rollback rule becomes "transaction abort" rather than best-effort compensation. If a future adapter cannot share the transaction, the coordinator must use explicit compensation and emit a transition failure event | Makes rollback semantics concrete; prevents partial-state corruption |
| D26 | **Forbidden-import architecture test enforces hexagonal boundaries.** `tests/unit/architecture/test_forbidden_imports.py` asserts: `src/squadops/runtime/` does not import `adapters.persistence.*`; `src/squadops/capabilities/handlers/` does not import runtime persistence adapters directly; `src/squadops/cli/` does not import Postgres runtime adapters directly | Cheap static guard for boundaries the plan repeatedly relies on |

---

## Phase 0 — SIP Acceptance and Numbering ✅ COMPLETE

**Goal:** Promote the umbrella and v1.1 runtime-state SIPs from `proposed/` to `accepted/` so they get assigned canonical SIP numbers.

**Outcome (PR #63 merged 2026-04-25):**

| Number | Title | Path |
|--------|-------|------|
| SIP-0088 | Agent Runtime Modes (umbrella) | `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` |
| SIP-0089 | Agent Runtime State | `sips/accepted/SIP-0089-Agent-Runtime-State.md` |
| SIP-0090 | Agent Embodiment Substrate | `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` |
| SIP-0091 | Duty Durability via Temporal | `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` |

All four were promoted as a package since they were design-reviewed together. Per the SIP workflow ("acceptance is a design commitment, not an implementation artifact"), accepting v1.2/v1.3 commits the design without triggering implementation.

What was done:

- ✅ YAML frontmatter added to each SIP for the maintainer script
- ✅ `update_sip_status.py` run for all four; numbers assigned
- ✅ H1 lines updated to include numbers (e.g., `# SIP-0088: ...`)
- ✅ Status headers changed from `Proposed` to `Accepted`
- ✅ Internal cross-references rewritten from `sips/proposed/` to `sips/accepted/` with numbered filenames
- ✅ Historical git-show reference preserved in the umbrella (commit `76a1f90` had the original at `sips/proposed/SIP-Agent-Runtime-Modes.md`)
- ✅ This plan file renamed to `SIP-0089-agent-runtime-state-plan.md`

---

## Phase 1 — Minimal Runtime State

**Goal:** Add `mode`, `runtime_status`, `focus`, `current_runtime_activity_id`, `interruptibility`, `last_heartbeat_at`, `current_assignment_ref` to the agent runtime. Make them queryable and heartbeat-reported.

### 1.0 Pre-implementation spikes

Two short spikes happen before any code:

1. **Entrypoint integration spike (D8):** read post-1.0.5 `agents/entrypoint.py` end-to-end. Identify the narrowest place where heartbeat payload enrichment can happen without changing agent lifecycle semantics.
2. **Events bridge spike (D22):** read post-1.0.5 `events/bridges/workflow_tracker.py`. Decide whether runtime-state events route through it or warrant a dedicated `runtime_state` bridge. Document the call in the Phase 1 PR body.

Output of both spikes: 1–2 paragraph notes attached to the Phase 1 PR. No code change required during the spikes themselves.

### 1.1 Create `src/squadops/runtime/` package

New files:

- `src/squadops/runtime/__init__.py`
- `src/squadops/runtime/models.py` — `AgentRuntimeState` dataclass
- `src/squadops/runtime/events.py` — canonical event name string constants
- `src/squadops/runtime/reasons.py` — canonical reason code string constants (per D18, separate from events)
- `src/squadops/ports/runtime_state.py` — `RuntimeStatePort` interface (mirror the structure of `ports/cycles/workflow_tracker.py`)

`AgentRuntimeState` is a frozen dataclass with the fields from SIP-0089 §10.1, mutated via `dataclasses.replace()`. Use `Literal` types in code for string enums per D3.

### 1.2 Postgres migration

New migration: `infra/migrations/1100_agent_runtime_state.sql`

Creates `agent_runtime_state` table:

- `agent_id` (PK)
- `mode` (text, not null, **CHECK in (`duty`, `cycle`, `ambient`)**)
- `runtime_status` (text, not null, **CHECK in (`online`, `degraded`, `recovering`, `offline`)**)
- `focus` (text)
- `current_runtime_activity_id` (text)
- `interruptibility` (text, **CHECK in (`none`, `low`, `medium`, `high`)**)
- `last_heartbeat_at` (timestamptz)
- `current_assignment_ref` (text)
- `created_at` (timestamptz, default now())
- `updated_at` (timestamptz, default now())

Also create/update `infra/migrations/README.md` with the D11 range reservation table.

### 1.3 Adapter

New: `adapters/persistence/runtime_state_postgres.py` implementing `RuntimeStatePort`.

Reuses existing `DbRuntime` connection pool. Operations:

- `get_state(agent_id)`
- `upsert_state(state)`
- `update_heartbeat(agent_id, **fields)` — applies D17 non-authoritative semantics
- `ensure_state(agent_id)` — initializes default state if no row exists; idempotent

### 1.4 Extend `AgentHeartbeatReporter` (non-authoritative per D17)

In `src/squadops/agents/`:

- Heartbeat invokes `RuntimeStatePort.ensure_state(agent_id)` if no row exists, initializing `mode=ambient, runtime_status=online`
- Subsequent heartbeats update `last_heartbeat_at` and `runtime_status` (health) only
- Heartbeat **does not** write `mode`, `focus`, `current_assignment_ref`, or `current_runtime_activity_id` against existing coordinator-owned state. If heartbeat reports a value that conflicts with coordinator state, coordinator state wins
- Default values for agents not yet aware of runtime state come from `ensure_state`, not from per-heartbeat overwrites

**Pre-implementation check:** must align with the §1.0 entrypoint spike. If the spike reveals heartbeat already touches mode-adjacent state, add a transition path with a clear deprecation note.

### 1.5 CLI surface

New: `squadops agent state <agent-id>` command in `src/squadops/cli/`.

Returns current `AgentRuntimeState` as a formatted table or `--json` for machine consumption. Display may show derived `idle`/`busy`/`paused` availability computed from FocusLease + RuntimeActivity (per D6) — but never store it.

No `--watch` flag in v1.1; defer to a follow-up if needed.

### 1.6 Tests

`tests/unit/runtime/test_agent_runtime_state.py`:

- State upsert and read round-trip
- `ensure_state` is idempotent (calling twice doesn't reset)
- Heartbeat update mutates only `last_heartbeat_at` + `runtime_status` (asserts mode/focus/activity_id are unchanged)
- **Heartbeat does NOT overwrite existing duty/cycle mode with ambient default** (likely-bug regression test)
- Invalid `mode` value rejected at DB CHECK constraint level
- Invalid `runtime_status` value rejected (note: `idle`/`busy`/`paused` are NOT valid runtime_status values per D6 — assert these are rejected, not just the success cases)

`tests/unit/cli/test_agent_state_command.py`:

- Command output renders all fields
- `--json` produces valid JSON
- Derived availability is shown when applicable but not persisted

`tests/unit/architecture/test_forbidden_imports.py` (new in Phase 1, expanded in subsequent phases per D26):

- `src/squadops/runtime/` modules do not import `adapters.persistence.*`
- `src/squadops/capabilities/handlers/` modules do not import runtime persistence adapters directly
- `src/squadops/cli/` modules do not import Postgres runtime adapters directly
- Test uses AST parsing or import-graph inspection; runs in the regression suite

**Acceptance for Phase 1:**

- An operator can run `squadops agent state max` and see current mode + RuntimeActivity ID
- Heartbeats update the table on every cycle (last_heartbeat_at + runtime_status only; never coordinator-owned fields)
- `runtime_status` is health-only; `idle`/`busy`/`paused` are not stored
- Spike notes (entrypoint integration, events bridge decision) are attached to the Phase 1 PR
- Migration registry note exists in `infra/migrations/README.md`
- All tests pass; `run_regression_tests.sh` clean

---

## Phase 2 — Assignments and Duty Windows

**Goal:** Implement `Assignment` model with hard/soft `DutyWindow`, in-process transition scheduler, and pre-duty reserve buffer policy.

### 2.0 Pre-implementation spike

Identify the exact cycle recruitment seam in `src/squadops/orchestration/` (or wherever it lives post-1.0.5). Document the file/function in the Phase 2 PR body before coding the reserve-buffer integration.

### 2.1 Models

In `src/squadops/runtime/models.py`:

- `Assignment` frozen dataclass per SIP-0089 §10.2
- `DutyWindow` is a nested structure on `Assignment` (no separate table for v1.1)
- `MissedWindowPolicy` enum: `skip | start_late_within_grace | require_operator_review`

`DutyWindow` exposes a state helper for tests and scheduler logic:

```
window_state(assignment, now) -> Literal[
    "before_window",
    "in_reserve_before",
    "active",
    "in_reserve_after",
    "closed",
    "missed",
]
```

### 2.2 Postgres migration

New migration: `infra/migrations/1110_assignments.sql`

Creates `agent_assignments` table:

- `assignment_id` (PK)
- `agent_id` (FK, indexed)
- `assignment_type` (text, CHECK in (`duty`, `reserve`, `cycle_eligibility`))
- `assigned_role` (text)
- `priority` (int)
- `strictness` (text, CHECK in (`hard`, `soft`))
- `window_start`, `window_end`, `timezone`
- `reserve_before_window`, `reserve_after_window` (interval)
- `recall_policy`, `graceful_window`
- `missed_window_policy` (CHECK against `MissedWindowPolicy` values)
- `allowed_off_window_modes` (text array)
- `active` (bool)
- `created_at`, `updated_at` (timestamptz)

### 2.3 Port + adapter

- `src/squadops/ports/assignments.py` — `AssignmentPort`
- `adapters/persistence/assignments_postgres.py`

Operations needed by scheduler and coordinator (so we don't fetch all assignments and filter in memory):

- `list_active_assignments(now)` — assignments whose window is active or in reserve
- `list_assignments_for_agent(agent_id)`
- `list_claimable_windows(now)` — upcoming duty windows that need a transition request
- `get_assignment(assignment_id)`

### 2.4 In-process transition scheduler (claimant only, per D21)

New: `src/squadops/runtime/scheduler.py`

Polling-based scheduler (interval configurable; default 30 seconds):

- Reads active assignments and current agent states
- Computes upcoming transitions (window opens, window closes, reserve buffer enters/exits)
- **Requests transitions through the runtime state coordinator (§2.6)** — never mutates `AgentRuntimeState` directly
- Repeated polling within the same window must be idempotent: window-open transition fires exactly once per `(assignment_id, window_start)`. The idempotency key from D12 enforces this

Designed so the v1.3 Temporal adapter sits behind the same `DutyDurabilityPort` interface (SIP-0091). For v1.1, only the in-process implementation exists.

**Lifecycle and config:** the scheduler is started by the runtime/bootstrap layer **only when enabled** by config. It must have a clean shutdown path. **It must not start implicitly in unit tests** unless explicitly constructed by the test — this prevents background-tick flakiness.

Config keys:

- `runtime.scheduler.enabled` (bool, default `false` — opt-in for v1.1)
- `runtime.scheduler.poll_interval_seconds` (int, default `30`)

**Missed-window behavior** (§2.4 scheduler enacts the policy declared on each `Assignment`):

| `MissedWindowPolicy` | Scheduler behavior on a missed window |
|----------------------|----------------------------------------|
| `skip` | Do not open the missed window. Emit `assignment.window.skipped` with reason `duty_window_missed`. Do not request a transition |
| `start_late_within_grace` | If `now ≤ window_start + graceful_window`, open the window and request the transition with reason `duty_window_started_late`. Otherwise behave as `skip` |
| `require_operator_review` | Do not transition. Emit `assignment.window.review_required` with reason `duty_window_missed_operator_review`. Block until an `operator_override` reason code is supplied via CLI |

### 2.5 Reserve buffer policy in cycle recruitment

Per the §2.0 spike, the recruitment seam is identified before this sub-step. Recruitment ordering:

1. Basic agent eligibility (existing logic)
2. **Assignment / reserve buffer check** (new)
3. (Phase 3) FocusLease acquisition

For the reserve check:

- Look up active assignments for the agent
- If a hard duty window starts within `reserve_before_window`, reject with reason `upcoming_hard_duty_window` and event `cycle.recruitment.rejected` (per D18 — separate event from reason)
- Soft duties may permit recruitment if the cycle's `can_pause` matches the duty's `recall_policy` graceful semantics

### 2.6 Runtime state coordinator (the authority per D16)

New: `src/squadops/runtime/coordinator.py`

Owns mode transitions. Conceptual API:

```
request_transition(
    agent_id,
    target_mode,
    reason_code,
    requester_kind,    # scheduler | coordinator | cli | external
    owner_ref,
    assignment_id | None,
    scheduled_at,
) -> TransitionOutcome
```

Every transition:

1. Validates preconditions (per SIP-0089 §11.2)
2. Resolves `FocusLease` decision (Phase 3 wires this in; Phase 2 stub)
3. Resolves `RuntimeActivity` decision (Phase 4 wires this in; Phase 2 stub)
4. Updates `AgentRuntimeState`
5. Emits canonical event with reason code (events from D14, distinct from reason per D18)
6. Records idempotency key per D12

Phase 2 lands the coordinator with stubbed FocusLease/RuntimeActivity hooks. Phase 3 and 4 fill them in.

The coordinator does **not** own scheduler polling, handler execution, persistence adapter construction, Temporal-specific logic, or embodiment-specific logic.

### 2.7 CLI surface

- `squadops assignment create ...` — marked **experimental/internal** in v1.1; not yet a public operator command
- `squadops assignment list <agent-id>`
- `squadops assignment show <assignment-id>`

### 2.8 Tests

`tests/unit/runtime/test_assignment.py`:

- Assignment CRUD
- DutyWindow state helper across timezones (`before_window`, `in_reserve_before`, `active`, `in_reserve_after`, `closed`, `missed`)
- Hard vs soft strictness defaults
- Cardinality rule: multiple assignments allowed per agent

`tests/unit/runtime/test_scheduler.py`:

- Window-open transition fires at correct time
- Window-close transition fires at correct time
- **Repeated scheduler tick within the same window does not duplicate transition events** (D21 + D12)
- Reserve buffer rejects cycle recruitment for hard duty
- Reserve buffer permits cycle recruitment for soft duty when policy allows
- Scheduler does NOT directly mutate `AgentRuntimeState` (only requests via coordinator)
- **Scheduler does not run unless explicitly enabled/configured** (no implicit background activation in tests)
- Missed-window behavior matches §2.4 table for each `MissedWindowPolicy` value (one test per policy)

`tests/unit/orchestration/test_recruitment_with_assignments.py`:

- Recruitment rejection produces `cycle.recruitment.rejected` event with reason `upcoming_hard_duty_window`
- Soft duty allows pausable cycle within buffer
- Heartbeat after duty transition does not revert mode (D17)

**Acceptance for Phase 2:**

- An agent can be Ambient now and scheduled to enter Duty later
- An upcoming hard duty window restricts cycle recruitment per the reserve buffer
- All transitions emit canonical reason-coded events with separate event/reason values
- Scheduler ticks are idempotent
- All tests pass

---

## Phase 3 — Focus Lease

**Goal:** Implement `FocusLease` with the explicit-outcome resolution model. Make lease the hard gate for primary attention.

### 3.0 Queue semantics (deferred per D5/D20)

FocusLease queueing is **deferred to v1.2+**. v1.1 implements `granted | rejected | preempting` only. Requests that would have queued return `rejected` with reason `focus_lease_queueing_not_supported_in_v1.1`.

Future versions reintroducing `queued` must include queue persistence storage, a queue-draining processor, and ordering tests. None of those are in scope for this plan.

### 3.1 Model

`FocusLease` frozen dataclass in `src/squadops/runtime/models.py` per SIP-0089 §10.4.

`LeaseDecision` discriminated union (queueing deferred per D20):

- `LeaseGranted(lease_id, expires_at, reason_code)`
- `LeaseRejected(current_owner_ref, reason_code, retry_after?)`
- `LeasePreempting(current_owner_ref, preemption_grace, reason_code)`

`LeaseQueued` is recognized as a v1.2+ outcome and is not part of the v1.1 union.

### 3.2 Postgres migration

New migration: `infra/migrations/1120_focus_leases.sql`

Creates `focus_leases` table:

- `lease_id` (PK)
- `agent_id` (FK, indexed)
- `owner_type` (text, CHECK in (`duty`, `cycle`, `ambient`))
- `owner_ref` (text)
- `acquired_at`, `expires_at`
- `renewal_policy`, `interruptibility`, `recall_policy`
- `released_at` (nullable; current lease has null)
- `idempotency_key` (text, indexed) — for replay-safe acquire/preempt per D12
- `created_at`, `updated_at`

Constraint: at most one `released_at IS NULL` row per `agent_id`. Enforce via partial unique index.

### 3.3 Port + adapter

- `src/squadops/ports/focus_lease.py` — `FocusLeasePort`
- `adapters/persistence/focus_lease_postgres.py`

Operations:

- `request_lease(agent_id, owner_type, owner_ref, idempotency_key, ...) -> LeaseDecision`
- `renew_lease(lease_id) -> bool`
- `release_lease(lease_id, reason_code)` — cooperative completion
- `revoke_lease(lease_id, reason_code)` — non-cooperative removal (preemption case)
- `get_current_lease(agent_id) -> FocusLease | None`

### 3.4 Wire coordinator to use leases (lease ≠ mode)

The Phase 2 coordinator stub for FocusLease decisions becomes real:

- `ambient → cycle` transition requests a lease for the cycle owner
- `cycle → duty` requests a lease for the duty owner; previous cycle lease is revoked per policy
- `duty → ambient` releases the duty lease

**Critical invariant:** acquiring a lease does *not* change `RuntimeMode`. The coordinator must still complete the transition (update `AgentRuntimeState.mode`) for the change to be authoritative. A successful `LeaseGranted` followed by a failed mode update must roll back the lease (per §4.5 transition order).

### 3.5 Cycle recruitment integration

Recruitment that passes the §2.5 reserve check must then acquire a `FocusLease`. Distinct rejection reasons per D18:

| Reason code | Event |
|-------------|-------|
| `upcoming_hard_duty_window` | `cycle.recruitment.rejected` |
| `focus_lease_conflict` | `cycle.recruitment.rejected` |
| `current_activity_cannot_pause` | `cycle.recruitment.rejected` |
| `agent_runtime_status_unavailable` | `cycle.recruitment.rejected` |
| `focus_lease_queueing_not_supported_in_v1.1` | `cycle.recruitment.rejected` (per D20 deferral) |

### 3.6 Tests

`tests/unit/runtime/test_focus_lease.py`:

- Granted: first request succeeds
- Rejected: second request with no preemption fails with `current_owner_ref`
- Preempting: higher-priority owner displaces current with grace
- Partial unique index prevents two simultaneous active leases per agent
- Renewal extends `expires_at`
- Release marks `released_at`
- `revoke_lease` removes the active lease (non-cooperative)
- `get_current_lease` returns null for an agent with no active lease
- Idempotent acquire: same `idempotency_key` does not create a duplicate lease
- Request with `wait` policy is rejected with reason `focus_lease_queueing_not_supported_in_v1.1` (per D20)

`tests/unit/runtime/test_coordinator_with_lease.py`:

- Mode transitions emit `focus_lease.granted` / `.rejected` / `.preempted` events with correct reason codes
- **Lease acquisition alone does not mutate `RuntimeMode`** (asserts mode is unchanged until the full transition completes)
- **Failed transition releases or rolls back newly acquired lease** (no stranded leases) — likely-bug regression test

**Acceptance for Phase 3:**

- The framework can explain why an agent did or did not accept a cycle request via distinct reason codes
- All v1.1 lease outcomes (`granted`/`rejected`/`preempting`) are observable via canonical events
- Partial unique index enforces single-lease invariant
- No stranded leases on failed transitions
- All tests pass

---

## Phase 4 — RuntimeActivity Model

**Goal:** Add `RuntimeActivity` records with pause/resume/abort. Wire existing handlers to emit them at **task-level granularity** (per D19). Establish the ambient irreversibility hook for v1.2.

### 4.1 Model

`RuntimeActivity` frozen dataclass per SIP-0089 §10.6.

`ActivityState` enum: `pending | running | paused | completed | aborted | failed`.

**Source identity columns** (per review feedback): RuntimeActivity carries explicit nullable `cycle_id`, `workload_id`, `task_id` columns for queryability. `source_ref` remains opaque adapter/source-specific detail; **core never parses `source_ref`**. If history-by-cycle / by-workload / by-task is needed, query the explicit columns. New source kinds (e.g., `embodied_action` in v1.2) may add their own columns rather than overload `source_ref`.

Timestamps:

- `started_at` (timestamptz, when state moves to `running`)
- `paused_at` (timestamptz, nullable; last paused)
- `ended_at` (timestamptz, nullable) — single terminal timestamp covering completed/aborted/failed
- `terminal_state` derived from final `state` value

Pending must be **short-lived**. Long queued work must not be represented as RuntimeActivity in v1.1.

### 4.2 Postgres migration

New migration: `infra/migrations/1130_runtime_activities.sql`

Creates `runtime_activities` table:

- `runtime_activity_id` (PK)
- `agent_id` (FK, indexed)
- `mode` (text, CHECK in (`duty`, `cycle`, `ambient`))
- `activity_type` (text)
- `goal` (text)
- `priority` (int)
- `state` (text, CHECK in (`pending`, `running`, `paused`, `completed`, `aborted`, `failed`))
- `source_kind` (text, CHECK in (`cycle_task`, `workload`, `duty_handler`, `ambient_observation`, `embodied_action`))
- `cycle_id` (text, nullable, indexed) — explicit per §4.1
- `workload_id` (text, nullable, indexed) — explicit per §4.1
- `task_id` (text, nullable, indexed) — explicit per §4.1
- `source_ref` (text) — opaque adapter/source-specific detail; **never parsed in core**
- `can_pause`, `can_resume`, `can_abort` (bool)
- `completion_conditions` (jsonb)
- `evidence_requirements` (jsonb)
- `started_at`, `paused_at`, `ended_at` (timestamptz, nullable)
- `created_at`, `updated_at`

Constraint: at most one row per `agent_id` with `state IN ('pending', 'running', 'paused')`. Partial unique index. Enforces D9.

### 4.3 Port + adapter

- `src/squadops/ports/runtime_activity.py` — `RuntimeActivityPort`
- `adapters/persistence/runtime_activity_postgres.py`

Operations:

- `start_activity(agent_id, ...) -> RuntimeActivity`
- `update_state(activity_id, state, ...) -> RuntimeActivity` — generic
- `complete_activity(activity_id, evidence_ref?)` — terminal helper
- `fail_activity(activity_id, reason_code)` — terminal helper
- `abort_activity(activity_id, reason_code)` — terminal helper
- `get_current_activity(agent_id) -> RuntimeActivity | None`

### 4.4 Wire existing execution paths — TASK-LEVEL ONLY (per D19)

This is the most invasive sub-step but kept thin. **Do not refactor execution.** Add observability hooks only. **Single granularity** per D19.

- `src/squadops/capabilities/handlers/cycle_tasks.py`: at handler entry, call `start_activity(source_kind=cycle_task, source_ref=task_id, mode=cycle)`. At exit, call `complete_activity` / `fail_activity` / `abort_activity` as appropriate. The `source_ref` payload may include `workload_id`, `cycle_id`, and other context.
- `src/squadops/capabilities/workload_runner.py`: continues to emit workflow/cycle lifecycle events as today. **It does NOT create a competing active `RuntimeActivity`.** Per D19, workload-level state is tracked by existing workflow events; the active RuntimeActivity belongs to the currently-executing task.
- Duty handlers (created here for the first time as a thin pattern) emit RuntimeActivities with `source_kind=duty_handler, mode=duty`.

Emit canonical `runtime_activity.*` events at each transition (per D14/D22).

### 4.5 Wire coordinator to RuntimeActivity decisions (transition order matters)

The Phase 2 coordinator stub for RuntimeActivity decisions becomes real. **Transition order is binding** to prevent partial-state failures and stranded leases:

1. **Evaluate policy** — preconditions, priorities, interruptibility
2. **Inspect current lease and current activity** — what does the agent hold now?
3. **Determine intended activity action** — pause / abort / complete / none
4. **Request or preempt lease** — atomic FocusLease operation
5. **Apply activity pause / abort / checkpoint** — RuntimeActivity update
6. **Update mode** — `AgentRuntimeState.mode` changes here
7. **Emit transition completed event** — canonical event + reason code

If any step fails, the transition is rejected. Steps before the failure that produced side effects (e.g., a granted lease in step 4) must be rolled back. Prior mode remains authoritative; emit `agent.mode.transition.rejected` with the failure reason code.

**Per D25, steps 4–6 (lease, activity, mode) execute inside a single Postgres transaction since all three ports share the `DbRuntime` pool.** The "rollback" is then a transaction abort, not best-effort compensation. Step 7 (event emission) sits outside the transaction so failures to publish do not corrupt state, but they must produce a follow-up alert.

### 4.6 Ambient irreversibility hook (seam for v1.2)

Add a policy gate in `src/squadops/runtime/policy.py`:

- `assert_action_permitted(agent_id, action_kind, irreversible: bool)`
- Evaluates against ports (`RuntimeStatePort`, `FocusLeasePort`, `RuntimeActivityPort`), not in-memory agent fields, so it works once embodiment adapters arrive
- For ambient agents, raises if `irreversible=True` AND no active `FocusLease` AND no active `RuntimeActivity`
- `irreversible` is a policy property supplied by the caller; v1.1 does not classify every possible action

In v1.1 this gate has no real callers (no embodied actions exist yet). It exists so v1.2 plugs into a working policy seam without redesign.

### 4.7 CLI surface

- `squadops agent activity <agent-id>` — show current activity
- `squadops agent activity history <agent-id> [--limit N]` — recent activities, default limit 20, max 200

### 4.8 Tests

`tests/unit/runtime/test_runtime_activity.py`:

- Start/update/complete lifecycle
- Pause/resume/abort transitions
- Partial unique index prevents two simultaneous active activities
- `source_ref` is opaque (no parsing in core)
- `complete_activity`, `fail_activity`, `abort_activity` set `ended_at` correctly

`tests/unit/runtime/test_coordinator_with_activity.py`:

- Mode transition pauses pausable activity
- Mode transition aborts abortable activity if pause not permitted
- Mode transition rejected if activity is neither pausable nor abortable and no override
- **Transition order from §4.5 holds: failure at step 6 rolls back the lease acquired in step 4** (likely-bug regression test)

`tests/unit/runtime/test_runtime_activity_strict_one.py`:

- **Cycle task RuntimeActivity does not conflict with workload-level activity** (per D19, no workload-level active activity exists)
- Failed handler marks RuntimeActivity `failed` with `ended_at` set
- Exception path does not leave `current_runtime_activity_id` pointing to an active activity forever (cleanup test)

`tests/unit/runtime/test_ambient_irreversibility.py`:

- Ambient agent with no lease + no activity is denied irreversible action
- Ambient agent with lease + activity is permitted
- Gate evaluates via ports, not in-memory state (port-mocked test)

`tests/integration/cycles/test_cycle_emits_activity.py`:

- A cycle execution end-to-end produces RuntimeActivity records linked by `source_ref`
- No regression in cycle outcomes
- Workload boundaries do NOT create competing active RuntimeActivities (D19 enforcement)

**Acceptance for Phase 4:**

- Current work is observable as a RuntimeActivity at task-level granularity
- The full nightly-research walkthrough from SIP-0089 §16 can be replayed end-to-end
- Ambient irreversibility hook exists and is testable via ports
- Strict-one RuntimeActivity invariant (D9) holds even with workload + task code paths
- Transition order in §4.5 prevents stranded leases on failure
- No regressions in `run_regression_tests.sh`

---

## Final Acceptance for v1.1

Across all four phases:

1. The framework can answer (for any agent at any time): mode, assignments, current RuntimeActivity, what may claim next.
2. An agent cannot be simultaneously in Duty, Cycle, and Ambient.
3. Cycle recruitment respects future duty windows AND the reserve buffer.
4. All v1.1 `FocusLease` outcomes (`granted`/`rejected`/`preempting`; queueing deferred per D20) are observable via canonical events.
5. Every transition and lease decision carries a canonical reason code, **distinct from the event name** (D18).
6. Existing cycle execution remains intact — `run_regression_tests.sh` continues to pass at its current count (verify pre-implementation baseline; recent SIP-0087 added significant test surface).
7. The end-to-end nightly-research walkthrough from SIP-0089 §16 executes correctly.
8. No `pyproject.toml` version bump until this point. Then bump `1.0.x → 1.1.0` as a single coordinated commit on main.
9. **Heartbeat cannot overwrite coordinator-owned mode transitions** (D17 verified by regression test).
10. **Scheduler ticks are idempotent** and do not duplicate window-open/window-close transitions (D21).
11. **`RuntimeActivity` instrumentation does not create nested active activities** under the strict-one D9 rule (D19 enforced by integration test).
12. **Event names and reason codes are separated and canonical** (D18 verified by static check or naming convention test).
13. **`current_assignment_ref` is active-only** (D23 verified by Phase 2 test: agent with future-only duty assignment has `current_assignment_ref = null`).
14. **Coordinator transitions are transactional** (D25 verified by Phase 4 test: simulated step-6 failure aborts the transaction and leaves no granted lease).
15. **Forbidden-import test passes on the regression suite** (D26 verified continuously).
16. **Scheduler does not auto-start in tests** (D21 lifecycle verified in Phase 2).
17. **Missed-window policy behavior matches the §2.4 table** for all three policy values.

---

## Coordination with Spark (1.0.x parallel work)

Per the agreed workflow:

- **`git pull --rebase`** at the start of every Mac session
- **Push WIP branches daily** so the Spark sees what's in flight
- **Hot zones — check `git log --oneline -10 <file>` before editing:**
  - `src/squadops/agents/entrypoint.py` — recently extended in 1.0.5; Phase 1 heartbeat work touches here
  - `src/squadops/agents/base_agent.py` — Phase 1 may also touch
  - `src/squadops/cycles/` — Phase 2 will touch recruitment
  - `src/squadops/capabilities/handlers/cycle_tasks.py` — Phase 4 will add task-level observability hooks
  - `src/squadops/events/bridges/` — recently refactored; Phase 1 spike (D22) decides routing
  - `src/squadops/telemetry/context.py` — new in 1.0.5; D15 specifies optional usage
  - `src/squadops/ports/cycles/` and `src/squadops/ports/observability/` — new ports landed in 1.0.5 set the structural pattern for the new `ports/runtime_state.py`
  - `infra/migrations/` — v1.1 uses `1100–1199` range; Spark 1.0.x uses `1000–1099` (per D11). Migration registry note added in Phase 1 (§1.2)
- **No `pyproject.toml` version bump on the Mac side** — Spark continues `1.0.5+`; v1.1 bump is one coordinated commit at end of Phase 4

If a 1.0.x PR on the Spark needs to touch one of the hot-zone files, sequence with the next v1.1 phase boundary so we don't merge-conflict mid-implementation.

---

## Open Questions Resolved (from review)

These were the original open questions; the plan-PR review resolved them as follows:

| # | Question | Resolution |
|---|----------|------------|
| 1 | Constructor params or PortsBundle for runtime-state injection? | **PortsBundle** (or nested `RuntimePorts`). Agent constructors stay minimal |
| 2 | Strict-one or multi RuntimeActivity? | **Hard invariant: strict-one in v1.1** (D9) |
| 3 | Reason codes / event names locked? | **Locked after a one-time normalization pass before Phase 1** (D14) |
| 4 | Migration range `1100–1199` uncontested? | Yes, plus a registry note in `infra/migrations/README.md` (D11) |
| 5 | Runtime events via `workflow_tracker` or dedicated bridge? | **Spike in Phase 1 §1.0; default to dedicated `runtime_state` bridge unless workflow_tracker is intentionally generic** (D22) |
| 6 | Phase 1 heartbeat clean against post-1.0.5 entrypoint? | **Spike in Phase 1 §1.0; D8 + D17 govern integration** |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Migration sequence collision with Spark | Range reservation per D11 + registry note in `infra/migrations/README.md` |
| `RuntimeActivity` becomes a parallel execution model | D4 + D19 bindings; PR boundary checklist; reject any PR that makes RuntimeActivity *do* work |
| Heartbeat overwrites coordinator-owned mode | D17 binding; Phase 1 §1.6 includes an explicit regression test |
| `queued` FocusLease returned without queue processor | D5 + D20 bindings; §3.0 forces an explicit decision before Phase 3 |
| Stranded `FocusLease` on failed transition | §4.5 transition order with rollback; Phase 3 + Phase 4 tests |
| Workload + task RuntimeActivity collision under strict-one | D19 binding; Phase 4 §4.4 single-granularity rule; integration test in §4.8 |
| In-process scheduler doesn't survive worker restart | Acceptable for v1.1; v1.3 Temporal adapter (SIP-0091) solves this. Document the limitation in v1.1 release notes |
| Cycle recruitment regressions | Phase 2 + Phase 4 integration tests cover the recruitment + activity emission paths end-to-end |
| Phase 4 observability hooks slow cycle execution | Hooks must be async fire-and-forget where possible; benchmark before/after on a sample cycle |
| Runtime-state events fragment from existing event bus | D14/D22 bind to deliberate routing decision; review at Phase 1 PR |
| Idempotency key collision on concurrent assignment transitions | D12 expanded key includes `owner_ref`/`assignment_id`; Phase 2 tests cover concurrent windows |
| Event/reason name conflation | D18 + Phase 1 naming separation; static check or naming convention test |

---

## References

- Source SIP (scope): `sips/accepted/SIP-0089-Agent-Runtime-State.md`
- Source SIP (constraints): `sips/accepted/SIP-0088-Agent-Runtime-Modes.md`
- Sibling SIPs (out of scope, future plans): `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2), `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3)
- SIP workflow: `CLAUDE.md` § "SIP System (SquadOps Improvement Proposals)"
- Maintainer tool: `scripts/maintainer/update_sip_status.py`
- Recent landmark: `sips/implemented/SIP-0087-Prefect-Task-Scoped-Log-Streaming.md` (introduced workflow_tracker, log_forwarder, telemetry/context patterns referenced by D8/D14/D15/D22)
- Related implementation patterns: `docs/plans/SIP-0071-builder-role-plan.md` (binding-decisions format), `docs/plans/SIP-0067-postgres-cycle-registry-plan.md` (port/adapter pattern)
