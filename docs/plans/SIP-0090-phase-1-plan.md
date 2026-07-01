# SIP-0090 Phase 1 (Core Embodiment Model) — Implementation Plan

**Status:** draft (for review before implementation) · **Created:** 2026-07-01 · **Branch:** `feature/sip-0090-phase-1-embodiment`
**Implements:** `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` §13 Phase 1 (accepted, targets v1.2)
**Depends on:** SIP-0089 (v1.1 runtime substrate — shipped). **Lane:** Macbook.

Phase 1 builds the **core embodiment model with no adapter** (§13 acceptance: *"Embodiment records exist and transition states cleanly. No adapter required yet."*). It mirrors the SIP-0089 Phase 1 shape (pure model + port + lifecycle logic first; migration + Postgres adapter second). **Read §2–§3 first — the migration split is what lets us start now.**

---

## 1. Scope (SIP-0090 §13, Phase 1)

In:
- `EmbodimentStatePort` interface (record/lifecycle store — **not** an action surface; see §4.3)
- `Embodiment` record + Postgres table (§5.3 fields)
- Lifecycle state machine (§5.2) — explicit transition matrix in §4.1
- Canonical `embodiment.*` event emission (SIP-0088 set)
- Resource budget primitives — 4 dimensions, decrement rules, non-silent exhaustion (§7)
- `credentials_ref` validation + a SecretManager-compatible seam (§9) — **no live resolution in 1a**

Explicitly **deferred** (later phases, no Phase-1 code):
- Any adapter (Discord = Phase 2, browser = Phase 4)
- RuntimeActivity `requires_embodiment` scheduling + FocusLease coupling (Phase 3)
- `EmbodiedAction` first-class ledger (§5.6 — deferred to a follow-on SIP)
- Multi-embodiment presence (§5.5 — deferred)

---

## 2. The 1a / 1b split (design boundary; #158 gate now cleared)

Like SIP-0089 Phase 1, the model layer is pure and CI-able **without a database**; only the persistence layer needs a migration. When this plan was drafted, Mac runtime migrations were gated on **#158** (operational hardening). **#158 has since closed** (PR #299; the `_schema_migrations` applier was already idempotent), so 1b is **no longer blocked** — the split below is now a *design/review* boundary, not a scheduling one, and 1a + 1b can land in sequence.

| | Slice | Kind |
|---|---|---|
| **1a** | Embodiment model + lifecycle + budgets + `EmbodimentStatePort` + events + `EmbodimentCoordinator` | pure, fake-backed unit tests |
| **1b** | `1140_embodiments.sql` (+ single-active index) + `agent_budgets` migration + Postgres adapters + composition-root wiring | live persistence |

**Acceptance boundary (be precise about "done"):** 1a satisfies the **model-level** acceptance — lifecycle correctness, budget enforcement, event emission — proven by unit tests. **Full SIP-0090 Phase 1 acceptance is NOT met until 1b lands persistence and live records** (§13: "Embodiment records exist *and* transition states cleanly"). Nobody marks Phase 1 "done" on 1a alone.

---

## 3. Open-question resolutions (SIP §16) relevant to Phase 1

- **OQ1 — embodiment ↔ FocusLease.** SIP recommends reusing the primary FocusLease. **Decision: Phase 1 mints no new lease type and adds no lease coupling** — the model is lease-agnostic. The "an activity requires an attached embodiment" seam is **Phase 3**. This keeps Phase 1 free of a premature lease-vs-embodiment decision (§5.7's integration seam is declared, not wired).
- **OQ2 — budgets per-role vs global.** §7.1 says budgets attach to the **agent**. **Decision: per-agent budget records seeded from global defaults; per-role configuration deferred** (resist additions, §15 risk "budgets become a policy quagmire"). Phase 1 ships the 4 dimensions with global default values; a per-role override table is a future concern.
- OQ3/OQ4/OQ5 (Discord extras, attached-event payload shape, browser engine) are Phase 2/4 — out of scope.

---

## 4. Design (1a — the migration-free core)

Mirrors SIP-0089's `runtime/*` + `ports/runtime/*` layering. New modules; imports no adapters (D26).

### 4.1 `src/squadops/runtime/embodiment.py` — model + lifecycle
- `Embodiment` frozen dataclass with the §5.3 fields (`embodiment_id`, `agent_id`, `embodiment_type`, `platform`, `attachment_state`, `health`, `capability_set: tuple[str,...]`, `location_ref: str | None`, `last_health_check_at`, `credentials_ref`).
- Literals: `AttachmentState` (`unattached|attaching|attached|desynced|reconnecting|detached`), `Health` (`healthy|degraded|failed`), `EmbodimentType` (`discord|browser|minecraft|cli|other`).
- `_ALLOWED_ATTACHMENT_TRANSITIONS` — the §5.2 state machine as an **explicit allow-list** (illegal transitions are rejected, not applied), same shape as SIP-0089's `_ALLOWED_TRANSITIONS`. **The exact matrix — spelled out so the implementation cannot infer illegal shortcuts:**

  | From | Allowed → |
  |---|---|
  | `unattached` | `attaching` |
  | `attaching` | `attached`, `detached` |
  | `attached` | `desynced`, `detached` |
  | `desynced` | `reconnecting`, `detached` |
  | `reconnecting` | `attached`, `detached` |
  | `detached` | *(terminal — no outgoing)* |

  Everything else is illegal — notably `unattached → attached` (never skip `attaching`), `attached → reconnecting` (recovery only via `desynced`), and any edge out of `detached`. **Conform-or-flag:** SIP §5.2's ASCII draws only the happy path plus `attached ↘ detached`; this matrix *completes* it by making the failure-termination edges explicit — a failed attach (`attaching → detached`), an abandoned desync and a failed reconnect (`desynced | reconnecting → detached`) must all terminate at `detached`. That's a deliberate refinement of an under-specified diagram, not a contradiction. `detached` is **terminal** in Phase 1; re-embodiment (reset vs. new record) is deferred.
- `is_active_attachment(state) -> bool` — `attached|desynced|reconnecting` count as "active" for the single-active rule (§5.5).
- `Location` dataclass (§5.4), **opaque by contract**: it exposes **no parsed fields**; core may compare `location_ref` for equality and route it back to the owning adapter, but never parses or branches on its contents (enforced by a concrete test — see §7).

### 4.2 `src/squadops/runtime/budgets.py` — budget primitives (§7)
Budgets attach to the **agent**, not the embodiment (§7.1), so cross-embodiment usage sums. Phase 1 models **decrement/acquire, release, exhaustion detection, and the enforcement decision** — *not* reset. **Two distinct shapes** (SIP §7.1 itself splits three cumulative counters from one "simultaneously-open" gauge):

- **Consumable budgets** — `attention_budget`, `compute_budget`, `action_budget`. Stored as **`{limit, consumed}`** (remaining = `limit - consumed`). Decrement = `consumed += amount`; **exhausted** when `consumed >= limit`. Storing the limit (not remaining-only) is deliberate — it keeps a future reset (`consumed → 0`) and observability ("70% used") possible without a rework.
- **Capacity budget** — `concurrency_allowance`. A **gauge, not a consumable** (SIP: "simultaneously-open RuntimeActivities or held leases"). Stored as **`{allowance, in_use}`** with explicit **`acquire`** (`in_use += 1`, on activity/lease open) and **`release`** (`in_use -= 1`, on close); **exhausted** when `in_use >= allowance`. `release` is first-class — the model must make "acquire without release" a visible bug, not a silent leak.
- `ExhaustionOutcome` literal — the 5 §7.2 outcomes (`reject_new_activity | pause_current_activity | detach_embodiment | transition_to_ambient | require_operator_override`).
- `budget_decision(budget, dimension, amount, policy) -> BudgetDecision` — a **pure decision** (mirrors `reserve_buffer_decision`): applies the decrement/acquire rule and, on exhaustion, returns `exhausted=True` with a chosen `ExhaustionOutcome` and a `budget_exhausted` finding. **Never a silent pass on exhaustion** — the type makes silent degradation unrepresentable (§7.2 / acceptance #7).
- **Deferred (explicit):** budget **reset / replenishment policy** — per-run, daily, per-duty-assignment, or manual — is **out of Phase 1 scope**. Phase 1 models only decrement/acquire, release, exhaustion, and the enforcement decision (keeps scheduling policy out of the substrate).

### 4.3 `src/squadops/ports/runtime/embodiment.py` — the state port
- `EmbodimentStatePort` (ABC): **record persistence + lifecycle state only** — `create_embodiment`, `get_embodiment`, `get_active_embodiment(agent_id)`, `list_for_agent`, `transition_state`, `update_health`, `update_location`. Named to mirror SIP-0089's `RuntimeStatePort` (a record/state store), **not** a bare `EmbodimentPort`.
- **Why `State` is in the name (a point of care):** Phase 2 needs a *separate* adapter-facing surface for `attach` / `detach` / `send` / `listen` — call it `EmbodimentSurfacePort` (or `EmbodimentAdapterPort`). Reserving that split now stops "port" from getting overloaded between "record/lifecycle store" (this) and "external-surface driver" (Phase 2); the two never merge.
- **Authority boundary baked into this surface (§6):** `EmbodimentStatePort` has **no** method that decides intent/mode/priority or *executes an action* — action execution is the Phase-2 surface's job, and even then only for *already-authorized* requests. This port is a record/lifecycle store, not a brain. Driver-agnostic (`Any` for opaque handles), adapter-free (D26).

### 4.4 Events + reasons (canonical, SIP-0088)
- Add the `embodiment.*` events (`embodiment.attaching/attached/desynced/reconnecting/detached`, `embodiment.health_changed`) + **`budget.exhausted`** to `runtime/events.py`, and the matching reason codes to `runtime/reasons.py` — same D14/D18 events-vs-reasons split SIP-0089 uses.
- **Standardized budget-exhaustion vocabulary (use these exact tokens in code and tests):** the **event** is `budget.exhausted`; the **reason code** is `budget_exhausted`; the **outcome** is one of the five `ExhaustionOutcome` values. Event vs. reason differ only by the `.`/`_` convention — tests must not conflate the three.

### 4.5 `EmbodimentCoordinator` (`runtime/embodiment_coordinator.py`)
- Pure orchestration mirroring `RuntimeCoordinator`: validates an attachment transition against the §4.1 allow-list, **enforces the single-active rule** (rejects `attach` when the agent already holds an active embodiment — the logic-level guard; the DB partial-unique index in 1b is the hard backstop), emits the canonical event on success, and is the seam where budget exhaustion drives an outcome. Takes an injected `EmbodimentStatePort` (+ event publisher), so it's fully unit-testable with fakes.
- **Adapter-free by named acceptance check (D26):** `runtime/embodiment_coordinator.py` imports only runtime models, ports, events/reasons, and typing/utilities — **no** concrete Discord/browser/persistence adapter. Asserted by an import test (§7), so the substrate can't couple to a surface early.

### 4.6 Credentials seam (§9) — validation + seam only, no live resolution
- The model carries `credentials_ref` only; a validator rejects any non-`secret://` value so a raw credential can never land in a record. **Phase 1a is `credentials_ref` validation + a SecretManager-*compatible* seam** (the resolution helper's signature), **not** a live resolve. Actual resolution via `SecretManager` happens at **attach** (1b / Phase 2), never in the migration-free, adapter-free core.

---

## 5. Persistence (1b — now unblocked, #158 closed)
- `infra/migrations/1140_embodiments.sql` — the `embodiments` table (§5.3) + a **partial unique index enforcing one active embodiment per agent** (`WHERE attachment_state IN ('attached','desynced','reconnecting')`), exactly mirroring SIP-0089's single-active-lease index (`1120_focus_leases.sql`).
- `1141_agent_budgets.sql` — per-agent budget rows seeded from global defaults (OQ2).
- `adapters/persistence/runtime/embodiment_postgres.py` + `budgets_postgres.py` — the port adapters (asyncpg, same conventions as the SIP-0089 adapters; JSONB for `capability_set`).
- Composition-root wiring (`scheduler_bootstrap` / `main.py`) — build the coordinator with the real adapters, gated on a pool (graceful-degrade when absent), same pattern as the runtime coordinator.

---

## 6. Slices
1. **Model + lifecycle** (`embodiment.py`) — dataclass, literals, the §4.1 transition allow-list, single-active helper, opaque `Location`; unit tests.
2. **Budget primitives** (`budgets.py`) — consumable `{limit,consumed}` + capacity `{allowance,in_use}` (acquire/release), non-silent exhaustion policy; unit tests.
3. **State port + events/reasons** — `EmbodimentStatePort`, canonical events/reasons; D26 import guard.
4. **EmbodimentCoordinator** — transition validation + single-active enforcement + event emission; fake-backed unit tests (the model-level "transition states cleanly" acceptance).
5. **Persistence + wiring** — migrations (`1140_embodiments.sql`, `1141_agent_budgets.sql`), Postgres adapters, composition root; live single-active-index validation (rolled-back txn, like #1120). *(No longer #158-gated — see §2.)*

Slices 1–4 are migration-free; slice 5 is now unblocked (#158 closed) and lands right after.

---

## 7. Testing (maps to SIP §14 acceptance)
- **Lifecycle (§14.4):** every §4.1 allowed transition applies; **illegal transitions are rejected** — assert specifically that `unattached→attached`, `attached→reconnecting`, and any edge out of `detached` all raise; each applied transition emits the matching canonical event.
- **Single-active (§14.2):** `attach` is rejected when the agent already holds an active embodiment; a `detached` embodiment does not block a new attach.
- **Budgets (§14.7):** consumable decrement + `consumed>=limit` exhaustion; capacity `acquire`/`release` + `in_use>=allowance` exhaustion, and **`acquire` then `release` returns to available** (guards the concurrency-leak bug); **exhaustion is never silent** — it yields the `budget.exhausted` event + `budget_exhausted` reason + one of the 5 outcomes (the §4.4 vocabulary).
- **Credentials (§14.8):** a record cannot be created with a non-`secret://` `credentials_ref`; no field carries a raw credential.
- **Location opacity (§14.5) — concrete, enforceable rules (not "spirit"):** (a) `Location` exposes no parsed fields; (b) no core module imports a surface-specific location parser; (c) no core code branches on `location_type` values (`== "discord_channel"`, `"minecraft_xyz"`, …) — equality / adapter-routing only. Enforced by an import/AST guard test.
- **Authority boundary (§14.3):** the `EmbodimentStatePort` surface exposes no intent/mode/priority/action method — asserted structurally.
- **Coordinator is adapter-free (D26):** a named import test asserts `embodiment_coordinator.py` imports no concrete Discord/browser/persistence adapter (§4.5).
- **No regression (§14.12):** `run_regression_tests.sh` stays green; v1.1 runtime primitives untouched.

---

## 8. Risks / notes
- **Authority creep** (§15) — `EmbodimentStatePort` having *no* action-execution method is the structural guard; the Phase-2 surface port translates only already-authorized requests.
- **Budget quagmire** (§15) — hold the line at 4 dimensions; the consumable/capacity split + the `budget_decision` signature discourage ad-hoc additions; reset policy stays deferred.
- **Concurrency leak** — `concurrency_allowance` is a gauge; every `acquire` needs a `release`, guarded by test.
- **Location leakage** — opacity is a *contract* + a concrete import/branch guard (§7), not just convention.
- **Naming overload** — Phase 1's `EmbodimentStatePort` (records) and Phase 2's `EmbodimentSurfacePort` (driver) stay separate; don't merge them.
- **FocusLease coupling deferred** — do not wire embodiment↔lease in Phase 1 (OQ1); it's Phase 3.
- **#158** — no longer a gate (closed, PR #299); 1b lands after 1a in sequence.

---

## 9. Summary of decisions baked in (for review)
1. **1a / 1b split:** 1a (model/state-port/lifecycle/budgets/coordinator) is migration-free; 1b (persistence) is unblocked (#158 closed) and lands right after. **1a alone ≠ Phase 1 done** (§2 acceptance boundary).
2. **Port naming:** `EmbodimentStatePort` (record/lifecycle store) in Phase 1; the Phase-2 driver surface is a *separate* `EmbodimentSurfacePort`. "Port" is never overloaded.
3. **Lifecycle:** the explicit §4.1 transition matrix is authoritative (completes SIP §5.2's happy-path diagram); `detached` is terminal.
4. **Budgets:** consumable `{limit,consumed}` vs capacity `{allowance,in_use}` (acquire/release); reset/replenishment **deferred**.
5. **OQ1:** no new lease type / no lease coupling in Phase 1 (reuse primary FocusLease, wired Phase 3).
6. **OQ2:** per-agent budgets from global defaults; per-role deferred.
7. **Authority + opacity + adapter-freedom** enforced by *structural tests* (port surface, location import/branch guard, coordinator import guard), not just docs.
8. **Credentials:** `credentials_ref` validation + a SecretManager-compatible seam in 1a; live resolution in 1b/Phase 2.

Incorporates dev-plan review feedback (2026-07-01). Awaiting approval before implementation begins.
