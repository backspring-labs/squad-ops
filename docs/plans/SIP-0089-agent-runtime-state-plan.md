# SIP-0089: Agent Runtime State — Implementation Plan

**Status:** Draft (under review)
**Targets:** SquadOps v1.1
**Created:** 2026-04-25
**Owner:** Jason Ladd
**Source SIPs:** SIP-0088 (umbrella), SIP-0089 (scope)

---

## Context

This plan implements the v1.1 runtime-state foundation: making persistent SquadOps agents observable, schedulable, and recallable through five primitives — `RuntimeMode`, `Assignment`/`DutyWindow`, `FocusLease`, `RuntimeActivity`, and `runtime_status`. It is the first of three planned releases that emerged from splitting the Agent Runtime Modes umbrella proposal.

This is a **runtime coordination layer**, not a replacement for cycle, workload, task, or handler execution. Existing execution paths continue to do the work; the new primitives observe and arbitrate.

Embodiment (Discord, browser, eventually Minecraft) and durable workflows (Temporal) are explicitly **out of scope** for v1.1. They are addressed by sibling SIPs targeting v1.2 (SIP-0090) and v1.3 (SIP-0091).

---

## Recent main activity (review-time snapshot, 2026-04-25)

Significant changes landed on main between plan drafting and this PR. Reviewers should be aware:

- **Version bumped to 1.0.5** with SIP-0087 (Prefect Task-Scoped Log Streaming) implementation merged and promoted to `implemented/`.
- **New ports:** `src/squadops/ports/cycles/workflow_tracker.py` and `src/squadops/ports/observability/log_forwarder.py`. These are patterns the Phase 1 runtime-state port should mirror for consistency.
- **Events bridge refactored:** `events/bridges/langfuse.py` → `llm_observability.py`, `events/bridges/prefect.py` deleted, `events/bridges/workflow_tracker.py` added. Canonical event-name registration in D14 should follow the new bridge layer's pattern.
- **`src/squadops/agents/entrypoint.py` was significantly extended** (+62 lines). Phase 1 heartbeat changes (D8) need to verify the extension path is still clean.
- **New telemetry primitive:** `src/squadops/telemetry/context.py` (`CorrelationContext`). Worth checking whether runtime-state events should propagate via this context.

These do not block the plan, but the binding decisions and Phase 1 sub-steps should be re-validated against the new code before implementation begins.

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

---

## Out of Scope for v1.1

These SIPs are accepted but not implemented in v1.1:

- `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2)
- `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3)

v1.1 must, however, leave clean seams for both:

- The **ambient irreversibility rule** (no irreversible action without `FocusLease` + `RuntimeActivity`) is encoded in policy from v1.1, even though it isn't fully testable until v1.2 introduces embodiment.
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
- PR body references SIP-0089, SIP-0088, and this plan
- **No `pyproject.toml` version bump until Phase 4 acceptance.** `1.1.0` lands as a single coordinated commit on main when implementation is feature-complete.

---

## Cross-Cutting Requirements (carry through every phase)

These derive from the umbrella SIP and are easy to forget while heads-down on plumbing. Pin them in PR review checklists:

1. **Canonical names in code from the first commit.** `RuntimeMode`, `RuntimeActivity`, `FocusLease`, `Assignment`, `DutyWindow`. Renaming later is painful.
2. **Every transition emits a reason-coded event.** Use the canonical reason codes and event names from SIP-0088. No bespoke names.
3. **Package invariant enforced in review.** Reject any code that uses one primitive as a hidden substitute for another (e.g., conflating `runtime_status` with mode, or making `RuntimeActivity` a parallel execution engine).
4. **Ambient irreversibility hook present from Phase 4.** Even without embodiment, the policy gate must exist so v1.2 plugs in cleanly.

---

## Binding Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | All new primitives live in `src/squadops/runtime/` (new package) | Keeps runtime-coordination layer distinct from `agents/`, `cycles/`, `tasks/`. Hexagonal ports for persistence go in `src/squadops/ports/runtime_state.py` |
| D2 | Postgres is the persistence backend; reuse the existing `DbRuntime` connection pool | Cycle registry already lives there (SIP-0067). Migrations sequenced per D11 |
| D3 | `RuntimeMode`, `runtime_status`, `RuntimeActivity.state` are string-valued enums (not Python `Enum` subclasses in DB) | Matches existing patterns in `cycles/`; simpler migrations and CLI display |
| D4 | `RuntimeActivity` is **emitted by existing handlers and workload runners**, not a new execution engine | Per package invariant. Add a thin observability hook to handlers; do not refactor execution |
| D5 | `FocusLease` resolution returns one of `granted | rejected | queued | preempting`; never silently no-op | Per umbrella; full set is mandatory, not optional |
| D6 | `runtime_status` is scoped to health only: `online | degraded | recovering | offline` | `idle`/`busy`/`paused` are derived from `FocusLease` + `RuntimeActivity` per umbrella boundary table |
| D7 | Pre-duty reserve buffer defaults: 15 minutes for hard duties, 0 for soft. Configurable per `Assignment` via `reserve_before_window` | Per SIP-0089 §11.4 |
| D8 | Heartbeat carries mode/focus/runtime_status by extending `AgentHeartbeatReporter`, not a new reporter. **Re-validate against the recent `agents/entrypoint.py` extension before Phase 1 implementation.** | Cheapest path; existing wiring proven, but entrypoint changed in 1.0.5 |
| D9 | Strict-one current `RuntimeActivity` per agent in v1.1; multi-activity is a future expansion | Per SIP-0089 open question #5 — recommend resolving as strict-one |
| D10 | `Assignment` cardinality: many-per-agent permitted; exactly one current `RuntimeMode`; at most one primary `FocusLease` | Per SIP-0089 §10.2 |
| D11 | Postgres migration sequence numbers reserve the `1100–1199` range for v1.1 work | Prevents collision with Spark 1.0.x migrations (which use `1000–1099`). Coordinate via plan PR comments |
| D12 | All transition handlers are idempotent on a `(agent_id, transition_type, scheduled_at)` key | Required for v1.3 Temporal integration; cheaper to build in from day one than retrofit |
| D13 | Direct human interaction stays cross-cutting per umbrella policy table; no new mode-like field | Hard rule from "what must not happen" |
| D14 | Reason codes and event names are defined as string constants in `src/squadops/runtime/events.py`, single canonical source. **Integrate with the new `events/bridges/workflow_tracker.py` pattern landed in 1.0.5.** | Prevents drift; matches existing patterns and the refactored bridge layer |
| D15 | Runtime-state events propagate via `CorrelationContext` (new in 1.0.5 at `src/squadops/telemetry/context.py`) where applicable | Reuses the existing trace-correlation seam; avoids inventing parallel context |

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

### 1.1 Create `src/squadops/runtime/` package

New files:

- `src/squadops/runtime/__init__.py`
- `src/squadops/runtime/models.py` — `AgentRuntimeState` dataclass
- `src/squadops/runtime/events.py` — reason code + event name string constants (per D14, integrate with `events/bridges/workflow_tracker.py` pattern)
- `src/squadops/ports/runtime_state.py` — `RuntimeStatePort` interface (mirror the structure of `ports/cycles/workflow_tracker.py` for consistency)

`AgentRuntimeState` is a frozen dataclass with the fields from SIP-0089 §10.1, mutated via `dataclasses.replace()` (matching existing cycle/run model patterns).

### 1.2 Postgres migration

New migration: `infra/migrations/1100_agent_runtime_state.sql`

Creates `agent_runtime_state` table:

- `agent_id` (PK)
- `mode` (text, not null) — `duty | cycle | ambient`
- `runtime_status` (text, not null) — `online | degraded | recovering | offline`
- `focus` (text)
- `current_runtime_activity_id` (text)
- `interruptibility` (text) — `none | low | medium | high`
- `last_heartbeat_at` (timestamptz)
- `current_assignment_ref` (text)
- `updated_at` (timestamptz, default now())

### 1.3 Adapter

New: `adapters/persistence/runtime_state_postgres.py` implementing `RuntimeStatePort`.

Reuses existing `DbRuntime` connection pool. Operations:

- `get_state(agent_id)`
- `upsert_state(state)`
- `update_heartbeat(agent_id, **fields)`

### 1.4 Extend `AgentHeartbeatReporter`

In `src/squadops/agents/`:

- Heartbeat payload gains `mode`, `runtime_status`, `focus`, `current_runtime_activity_id`
- Reporter writes to `agent_runtime_state` via `RuntimeStatePort`
- Default values for agents not yet aware of runtime state: `mode=ambient`, `runtime_status=online`

**Pre-implementation check:** verify the integration point against the recent `agents/entrypoint.py` extension (see "Recent main activity" callout). Heartbeat may now flow through different code paths than the original plan assumed.

### 1.5 CLI surface

New: `squadops agent state <agent-id>` command in `src/squadops/cli/`.

Returns current `AgentRuntimeState` as a formatted table or `--json` for machine consumption.

### 1.6 Tests

`tests/unit/runtime/test_agent_runtime_state.py`:

- State upsert and read round-trip
- Heartbeat update mutates only specified fields
- Invalid `mode` value rejected
- Invalid `runtime_status` value rejected (note: `idle`/`busy`/`paused` are NOT valid runtime_status values per D6 — write a test that asserts this rejection, not just success cases)

`tests/unit/cli/test_agent_state_command.py`:

- Command output renders all fields
- `--json` produces valid JSON

**Acceptance for Phase 1:**

- An operator can run `squadops agent state max` and see current mode + RuntimeActivity ID
- Heartbeats update the table on every cycle
- `runtime_status` is health-only; idle/busy/paused are not stored
- All tests pass; `run_regression_tests.sh` clean

---

## Phase 2 — Assignments and Duty Windows

**Goal:** Implement `Assignment` model with hard/soft `DutyWindow`, in-process transition scheduler, and pre-duty reserve buffer policy.

### 2.1 Models

In `src/squadops/runtime/models.py`:

- `Assignment` frozen dataclass per SIP-0089 §10.2
- `DutyWindow` is a nested structure on `Assignment` (no separate table for v1.1)
- `MissedWindowPolicy` enum: `skip | start_late_within_grace | require_operator_review`

### 2.2 Postgres migration

New migration: `infra/migrations/1110_assignments.sql`

Creates `agent_assignments` table:

- `assignment_id` (PK)
- `agent_id` (FK, indexed)
- `assignment_type` (text) — `duty | reserve | cycle_eligibility`
- `assigned_role` (text)
- `priority` (int)
- `strictness` (text) — `hard | soft`
- `window_start`, `window_end`, `timezone`
- `reserve_before_window`, `reserve_after_window` (interval)
- `recall_policy`, `graceful_window`
- `missed_window_policy`
- `allowed_off_window_modes` (text array)
- `active` (bool)

### 2.3 Port + adapter

- `src/squadops/ports/assignments.py` — `AssignmentPort`
- `adapters/persistence/assignments_postgres.py`

### 2.4 In-process transition scheduler

New: `src/squadops/runtime/scheduler.py`

Polling-based scheduler (interval configurable; default 30 seconds):

- Reads active assignments and current agent states
- Computes upcoming transitions (window opens, window closes, reserve buffer enters/exits)
- Requests transitions through the runtime state coordinator (see 2.6)

Designed so the v1.3 Temporal adapter sits behind the same interface (`DutyDurabilityPort` from SIP-0091). For v1.1, only the in-process implementation exists.

### 2.5 Reserve buffer policy in cycle recruitment

Identify the cycle recruitment seam (likely in `src/squadops/orchestration/`) and add a check:

- Before accepting a cycle for an agent, look up active assignments
- If a hard duty window starts within `reserve_before_window`, reject with reason code `cycle_recruitment_rejected_upcoming_duty`
- Emit `cycle_recruitment_rejected_upcoming_duty` event
- Soft duties may permit recruitment if cycle's `can_pause` matches

### 2.6 Runtime state coordinator

New: `src/squadops/runtime/coordinator.py`

Owns mode transitions. Every transition:

1. Validates preconditions (per SIP-0089 §11.2)
2. Resolves `FocusLease` decision (Phase 3 wires this in; Phase 2 stub)
3. Resolves `RuntimeActivity` decision (Phase 4 wires this in; Phase 2 stub)
4. Updates `AgentRuntimeState`
5. Emits canonical event with reason code

Phase 2 lands the coordinator with stubbed FocusLease/RuntimeActivity hooks. Phase 3 and 4 fill them in.

### 2.7 CLI surface

- `squadops assignment create ...` for ad-hoc creation (dev/testing)
- `squadops assignment list <agent-id>`
- `squadops assignment show <assignment-id>`

### 2.8 Tests

`tests/unit/runtime/test_assignment.py`:

- Assignment CRUD
- DutyWindow active/inactive computation across timezones
- Hard vs soft strictness defaults
- Cardinality rule: multiple assignments allowed per agent

`tests/unit/runtime/test_scheduler.py`:

- Window-open transition fires at correct time
- Window-close transition fires at correct time
- Reserve buffer rejects cycle recruitment for hard duty
- Reserve buffer permits cycle recruitment for soft duty when policy allows

`tests/unit/orchestration/test_recruitment_with_assignments.py`:

- Recruitment rejection produces `cycle_recruitment_rejected_upcoming_duty` event
- Soft duty allows pausable cycle within buffer

**Acceptance for Phase 2:**

- An agent can be Ambient now and scheduled to enter Duty later
- An upcoming hard duty window restricts cycle recruitment per the reserve buffer
- All transitions emit canonical reason-coded events
- All tests pass

---

## Phase 3 — Focus Lease

**Goal:** Implement `FocusLease` with the four-outcome resolution model. Make lease the hard gate for primary attention.

### 3.1 Model

`FocusLease` frozen dataclass in `src/squadops/runtime/models.py` per SIP-0089 §10.4.

`LeaseDecision` discriminated union:

- `LeaseGranted(lease_id, expires_at, reason_code)`
- `LeaseRejected(current_owner_ref, reason_code, retry_after?)`
- `LeaseQueued(queue_position, current_owner_ref, reason_code)`
- `LeasePreempting(current_owner_ref, preemption_grace, reason_code)`

### 3.2 Postgres migration

New migration: `infra/migrations/1120_focus_leases.sql`

Creates `focus_leases` table:

- `lease_id` (PK)
- `agent_id` (FK, indexed)
- `owner_type` (text) — `duty | cycle | ambient`
- `owner_ref` (text)
- `acquired_at`, `expires_at`
- `renewal_policy`, `interruptibility`, `recall_policy`
- `released_at` (nullable; current lease has null)

Constraint: at most one `released_at IS NULL` row per `agent_id`. Enforce via partial unique index.

### 3.3 Port + adapter

- `src/squadops/ports/focus_lease.py` — `FocusLeasePort`
- `adapters/persistence/focus_lease_postgres.py`

Operations:

- `request_lease(agent_id, owner_type, owner_ref, ...) -> LeaseDecision`
- `renew_lease(lease_id) -> bool`
- `release_lease(lease_id, reason_code)`

### 3.4 Wire coordinator to use leases

The Phase 2 coordinator stub for FocusLease decisions becomes real:

- `ambient → cycle` transition requests a lease for the cycle owner
- `cycle → duty` requests a lease for the duty owner; previous cycle lease is preempted per policy
- `duty → ambient` releases the duty lease

### 3.5 Cycle recruitment integration

If a cycle recruitment passes the reserve-buffer check (Phase 2), it then must acquire a `FocusLease`. Failure produces `cycle_recruitment_rejected_focus_lease_conflict`.

### 3.6 Tests

`tests/unit/runtime/test_focus_lease.py`:

- Granted: first request succeeds
- Rejected: second request with no preemption fails with current_owner_ref
- Queued: request with `wait` policy queues
- Preempting: higher-priority owner displaces current with grace
- Partial unique index prevents two simultaneous active leases per agent
- Renewal extends `expires_at`
- Release marks `released_at`

`tests/unit/runtime/test_coordinator_with_lease.py`:

- Mode transitions emit `focus_lease.granted` / `.rejected` / `.queued` / `.preempted` events with correct reason codes

**Acceptance for Phase 3:**

- The framework can explain why an agent did or did not accept a cycle request
- All four lease outcomes are observable via canonical events
- Partial unique index enforces single-lease invariant
- All tests pass

---

## Phase 4 — RuntimeActivity Model

**Goal:** Add `RuntimeActivity` records with pause/resume/abort. Wire existing handlers to emit them. Establish the ambient irreversibility hook for v1.2.

### 4.1 Model

`RuntimeActivity` frozen dataclass per SIP-0089 §10.6.

`ActivityState` enum: `pending | running | paused | completed | aborted | failed`.

### 4.2 Postgres migration

New migration: `infra/migrations/1130_runtime_activities.sql`

Creates `runtime_activities` table:

- `runtime_activity_id` (PK)
- `agent_id` (FK, indexed)
- `mode` (text)
- `activity_type` (text)
- `goal` (text)
- `priority` (int)
- `state` (text)
- `source_kind` (text) — `cycle_task | workload | duty_handler | ambient_observation | embodied_action`
- `source_ref` (text) — opaque
- `can_pause`, `can_resume`, `can_abort` (bool)
- `completion_conditions` (jsonb)
- `evidence_requirements` (jsonb)
- `started_at`, `paused_at`, `completed_at` (timestamptz, nullable)

Constraint: at most one row per `agent_id` with `state IN ('pending', 'running', 'paused')`. Partial unique index.

### 4.3 Port + adapter

- `src/squadops/ports/runtime_activity.py` — `RuntimeActivityPort`
- `adapters/persistence/runtime_activity_postgres.py`

Operations:

- `start_activity(agent_id, ...) -> RuntimeActivity`
- `update_state(activity_id, state, ...) -> RuntimeActivity`
- `get_current_activity(agent_id) -> RuntimeActivity | None`

### 4.4 Wire existing execution paths

This is the most invasive sub-step but kept thin. **Do not refactor execution.** Add observability hooks only.

- `src/squadops/capabilities/handlers/cycle_tasks.py`: at task entry, call `start_activity(source_kind=cycle_task, source_ref=task_id)`. At task exit, call `update_state(state=completed/failed)`.
- `src/squadops/capabilities/workload_runner.py`: similar hooks for workload boundaries.
- Duty handlers (created here for the first time as a thin pattern) emit RuntimeActivities with `source_kind=duty_handler`.

Emit canonical `runtime_activity.*` events at each transition (per D14, via the `events/bridges/workflow_tracker.py` integration pattern).

### 4.5 Wire coordinator to RuntimeActivity decisions

The Phase 2 coordinator stub for RuntimeActivity decisions becomes real:

- Mode transition requires resolving the current RuntimeActivity (pause if `can_pause`, abort if `can_abort`, complete if applicable)
- Reject transition if current activity cannot be cleanly resolved and no `operator_override` reason code is supplied

### 4.6 Ambient irreversibility hook (seam for v1.2)

Add a policy gate in `src/squadops/runtime/policy.py`:

- `assert_action_permitted(agent_id, action_kind, irreversible: bool)`
- For ambient agents, raises if `irreversible=True` AND no active `FocusLease` AND no active `RuntimeActivity`

In v1.1 this gate has no real callers (no embodied actions exist yet). It exists so v1.2 plugs into a working policy seam without redesign.

### 4.7 CLI surface

- `squadops agent activity <agent-id>` — show current activity
- `squadops agent activity history <agent-id> --limit N` — recent activities

### 4.8 Tests

`tests/unit/runtime/test_runtime_activity.py`:

- Start/update/complete lifecycle
- Pause/resume/abort transitions
- Partial unique index prevents two simultaneous active activities
- `source_ref` is opaque (no parsing in core)

`tests/unit/runtime/test_coordinator_with_activity.py`:

- Mode transition pauses pausable activity
- Mode transition aborts abortable activity if pause not permitted
- Mode transition rejected if activity is neither pausable nor abortable and no override

`tests/unit/runtime/test_ambient_irreversibility.py`:

- Ambient agent with no lease + no activity is denied irreversible action
- Ambient agent with lease + activity is permitted

`tests/integration/cycles/test_cycle_emits_activity.py`:

- A cycle execution end-to-end produces RuntimeActivity records linked by `source_ref`
- No regression in cycle outcomes

**Acceptance for Phase 4:**

- Current work is observable as a RuntimeActivity, not hidden in prompt history
- The full nightly-research walkthrough from SIP-0089 §16 can be replayed end-to-end
- Ambient irreversibility hook exists and is testable
- No regressions in `run_regression_tests.sh`

---

## Final Acceptance for v1.1

Across all four phases:

1. The framework can answer (for any agent at any time): mode, assignments, current RuntimeActivity, what may claim next.
2. An agent cannot be simultaneously in Duty, Cycle, and Ambient.
3. Cycle recruitment respects future duty windows AND the reserve buffer.
4. All four `FocusLease` outcomes are observable via canonical events.
5. Every transition and lease decision carries a canonical reason code.
6. Existing cycle execution remains intact — `run_regression_tests.sh` continues to pass at its current count (verify pre-implementation baseline; recent SIP-0087 added significant test surface).
7. The end-to-end nightly-research walkthrough from SIP-0089 §16 executes correctly.
8. No `pyproject.toml` version bump until this point. Then bump `1.0.x → 1.1.0` as a single coordinated commit on main.

---

## Coordination with Spark (1.0.x parallel work)

Per the agreed workflow:

- **`git pull --rebase`** at the start of every Mac session
- **Push WIP branches daily** so the Spark sees what's in flight
- **Hot zones — check `git log --oneline -10 <file>` before editing:**
  - `src/squadops/agents/entrypoint.py` — recently extended in 1.0.5; Phase 1 heartbeat work touches here
  - `src/squadops/agents/base_agent.py` — Phase 1 may also touch
  - `src/squadops/cycles/` — Phase 2 will touch recruitment
  - `src/squadops/capabilities/handlers/cycle_tasks.py` — Phase 4 will add observability hooks
  - `src/squadops/events/bridges/` — recently refactored; Phase 1 events register here
  - `src/squadops/telemetry/context.py` — new in 1.0.5; Phase 1 may propagate via this
  - `src/squadops/ports/cycles/` and `src/squadops/ports/observability/` — new ports landed in 1.0.5 set the structural pattern for the new `ports/runtime_state.py`
  - `infra/migrations/` — v1.1 uses `1100–1199` range; Spark 1.0.x uses lower range (per D11)
- **No `pyproject.toml` version bump on the Mac side** — Spark continues `1.0.5+`; v1.1 bump is one coordinated commit at end of Phase 4

If a 1.0.x PR on the Spark needs to touch one of the hot-zone files, sequence with the next v1.1 phase boundary so we don't merge-conflict mid-implementation.

---

## Open Questions to Resolve Before Phase 1

1. Does the agent factory accept new constructor parameters for runtime state, or should it be injected via the existing `PortsBundle`? (SIP-0089 open question #2)
2. Should `current_runtime_activity_id` allow multiple concurrent activities, or strict-one? **Recommend strict-one for v1.1 (D9).**
3. Are the canonical reason codes and event names in SIP-0088 locked in, or do reviewers want adjustments?
4. Confirm migration sequence range `1100–1199` is uncontested with Spark.
5. **NEW (post-1.0.5):** Should runtime-state events route through the new `events/bridges/workflow_tracker.py` bridge layer, or via a dedicated bridge? Affects D14 implementation shape.
6. **NEW (post-1.0.5):** Does the Phase 1 heartbeat extension still slot cleanly into the post-1.0.5 `agents/entrypoint.py` structure?

---

## Risks

| Risk | Mitigation |
|------|------------|
| Migration sequence collision with Spark | Range reservation per D11; coordinate via plan PR comments |
| `RuntimeActivity` becomes a parallel execution model | D4 binding; PR review checklist; reject any PR that makes RuntimeActivity *do* work |
| Heartbeat changes break existing reporters | Default values for unaware agents (D8); incremental rollout. **Re-validate against post-1.0.5 entrypoint** |
| In-process scheduler doesn't survive worker restart | Acceptable for v1.1; v1.3 Temporal adapter (SIP-0091) solves this. Document the limitation in v1.1 release notes |
| Cycle recruitment regressions | Phase 2 + Phase 4 integration tests cover the recruitment + activity emission paths end-to-end |
| Phase 4 observability hooks slow cycle execution | Hooks must be async fire-and-forget where possible; benchmark before/after on a sample cycle |
| Runtime-state events fragment from existing event bus | D14 + D15 bind to the new bridge layer and CorrelationContext; review at Phase 1 PR |

---

## References

- Source SIP (scope): `sips/accepted/SIP-0089-Agent-Runtime-State.md`
- Source SIP (constraints): `sips/accepted/SIP-0088-Agent-Runtime-Modes.md`
- Sibling SIPs (out of scope, future plans): `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2), `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3)
- SIP workflow: `CLAUDE.md` § "SIP System (SquadOps Improvement Proposals)"
- Maintainer tool: `scripts/maintainer/update_sip_status.py`
- Recent landmark: `sips/implemented/SIP-0087-Prefect-Task-Scoped-Log-Streaming.md` (introduced workflow_tracker, log_forwarder, telemetry/context patterns referenced by D8/D14/D15)
- Related implementation patterns: `docs/plans/SIP-0071-builder-role-plan.md` (binding-decisions format), `docs/plans/SIP-0067-postgres-cycle-registry-plan.md` (port/adapter pattern)
