# SIP-0090 Phase 1 (Core Embodiment Model) — Implementation Plan

**Status:** draft (for review before implementation) · **Created:** 2026-07-01 · **Branch:** `feature/sip-0090-phase-1-embodiment`
**Implements:** `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` §13 Phase 1 (accepted, targets v1.2)
**Depends on:** SIP-0089 (v1.1 runtime substrate — shipped). **Lane:** Macbook.

Phase 1 builds the **core embodiment model with no adapter** (§13 acceptance: *"Embodiment records exist and transition states cleanly. No adapter required yet."*). It mirrors the SIP-0089 Phase 1 shape (pure model + port + lifecycle logic first; migration + Postgres adapter second). **Read §2–§3 first — the migration split is what lets us start now.**

---

## 1. Scope (SIP-0090 §13, Phase 1)

In:
- `EmbodimentPort` interface
- `Embodiment` record + Postgres table (§5.3 fields)
- Lifecycle state machine (§5.2)
- Canonical `embodiment.*` event emission (SIP-0088 set)
- Resource budget primitives — 4 dimensions, decrement rules, non-silent exhaustion (§7)
- `SecretManager` integration via `credentials_ref` (§9)

Explicitly **deferred** (later phases, no Phase-1 code):
- Any adapter (Discord = Phase 2, browser = Phase 4)
- RuntimeActivity `requires_embodiment` scheduling + FocusLease coupling (Phase 3)
- `EmbodiedAction` first-class ledger (§5.6 — deferred to a follow-on SIP)
- Multi-embodiment presence (§5.5 — deferred)

---

## 2. The #158 split — start now, finish after the applier hardens

Like SIP-0089 Phase 1, the model layer is pure and CI-able **without a database**. Only the persistence layer needs a migration, and Mac runtime migrations want **#158** (schema_migrations + applier hardening, in progress on the Spark lane) first. So Phase 1 splits:

| | Slice | Needs #158? | Executable |
|---|---|---|---|
| **1a** | Embodiment model + lifecycle + budgets + port + events + `EmbodimentCoordinator` | **No** — pure, fake-backed unit tests | **Now** |
| **1b** | `1140_embodiments.sql` (+ single-active index) + `agent_budgets` migration + Postgres adapters + composition-root wiring | **Yes** | After #158 |

1a is the bulk of Phase 1's value and satisfies "transition states cleanly" at the unit level. 1b satisfies "records exist" live. **This plan front-loads 1a; 1b lands once #158 is on main.**

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
- `_ALLOWED_ATTACHMENT_TRANSITIONS` — the §5.2 state machine as an explicit allow-list (so an illegal transition is rejected, not applied), same shape as SIP-0089's `_ALLOWED_TRANSITIONS`.
- `is_active_attachment(state) -> bool` — `attached|desynced|reconnecting` count as "active" for the single-active rule (§5.5).
- `Location` dataclass (§5.4) with the **opacity contract in the docstring**: core may compare `location_ref` for equality and route it back to the owning adapter, but MUST NOT parse/branch on its contents.

### 4.2 `src/squadops/runtime/budgets.py` — budget primitives (§7)
- `AgentBudget` — the 4 dimensions (`attention_budget`, `compute_budget`, `action_budget`, `concurrency_allowance`), **attached to the agent** so cross-embodiment usage sums.
- `ExhaustionOutcome` literal — the 5 §7.2 outcomes (`reject_new_activity|pause_current_activity|detach_embodiment|transition_to_ambient|require_operator_override`).
- `budget_decision(budget, dimension, amount, policy) -> BudgetDecision` — a **pure decision** (mirrors `reserve_buffer_decision`): applies the decrement rule, and on exhaustion returns `exhausted=True` with a chosen `ExhaustionOutcome` and a `budget_exhausted` finding. **Never returns a silent pass on exhaustion** — the type makes silent degradation unrepresentable (§7.2 / acceptance #7).

### 4.3 `src/squadops/ports/runtime/embodiment.py` — the port
- `EmbodimentPort` (ABC): record persistence + state transition only — `create_embodiment`, `get_embodiment`, `get_active_embodiment(agent_id)`, `list_for_agent`, `transition_state`, `update_health`, `update_location`.
- **Authority boundary baked into the surface (§6):** the port has **no** method that decides intent/mode/priority or "executes an action" — action execution is an *adapter* concern (Phase 2), and even then only for *already-authorized* requests. The port is a record/lifecycle store, not a brain. Driver-agnostic (`Any` for opaque handles), adapter-free (D26).

### 4.4 Events + reasons (canonical, SIP-0088)
- Add the `embodiment.*` events (`embodiment.attaching/attached/desynced/reconnecting/detached`, `embodiment.health_changed`) + `budget.exhausted` to `runtime/events.py`, and the matching reason codes (`budget_exhausted`, the attachment-transition reasons) to `runtime/reasons.py` — same D14/D18 events-vs-reasons split SIP-0089 uses.

### 4.5 `EmbodimentCoordinator` (`runtime/embodiment_coordinator.py`)
- Pure orchestration mirroring `RuntimeCoordinator`: validates an attachment transition against the §5.2 allow-list, **enforces the single-active rule** (rejects `attach` when the agent already holds an active embodiment — the logic-level guard; the DB partial-unique index in 1b is the hard backstop), emits the canonical event on success, and is the seam where budget exhaustion drives an outcome. Takes an injected `EmbodimentPort` (+ event publisher), so it's fully unit-testable with fakes.

### 4.6 Credentials seam (§9)
- The model carries `credentials_ref` only; a small validator rejects a non-`secret://` value so a raw credential can never land in a record. Resolution via the existing `SecretManager` happens at **attach** (Phase 2 adapters); Phase 1 wires the validation + the resolution helper signature, not a live resolve.

---

## 5. Persistence (1b — after #158)
- `infra/migrations/1140_embodiments.sql` — the `embodiments` table (§5.3) + a **partial unique index enforcing one active embodiment per agent** (`WHERE attachment_state IN ('attached','desynced','reconnecting')`), exactly mirroring SIP-0089's single-active-lease index (`1120_focus_leases.sql`).
- `1141_agent_budgets.sql` — per-agent budget rows seeded from global defaults (OQ2).
- `adapters/persistence/runtime/embodiment_postgres.py` + `budgets_postgres.py` — the port adapters (asyncpg, same conventions as the SIP-0089 adapters; JSONB for `capability_set`).
- Composition-root wiring (`scheduler_bootstrap` / `main.py`) — build the coordinator with the real adapters, gated on a pool (graceful-degrade when absent), same pattern as the runtime coordinator.

---

## 6. Slices
1. **Model + lifecycle** (`embodiment.py`) — dataclass, literals, transition allow-list, single-active helper, Location + opacity docstring; unit tests.
2. **Budget primitives** (`budgets.py`) — dimensions, decrement, non-silent exhaustion policy; unit tests.
3. **Port + events/reasons** — `EmbodimentPort`, canonical events/reasons; D26 import guard.
4. **EmbodimentCoordinator** — transition validation + single-active enforcement + event emission; fake-backed unit tests (the "transition states cleanly" acceptance).
5. *(after #158)* **Persistence + wiring** — migrations, Postgres adapters, composition root; live single-active-index validation (rolled-back txn, like #1120).

Slices 1–4 are migration-free and land now; slice 5 waits on #158.

---

## 7. Testing (maps to SIP §14 acceptance)
- **Lifecycle (§14.4):** every §5.2 transition applies; **illegal transitions are rejected** (e.g. `unattached→attached`, `detached→attached`); each applied transition emits the matching canonical event.
- **Single-active (§14.2):** `attach` is rejected when the agent already holds an active embodiment; a `detached` embodiment does not block a new attach.
- **Budgets (§14.7):** decrement rules per dimension; **exhaustion is never silent** — it produces `budget_exhausted` + one of the 5 outcomes; each outcome is representable and selected per policy.
- **Credentials (§14.8):** a record cannot be created with a non-`secret://` `credentials_ref`; no field carries a raw credential.
- **Location opacity (§14.5):** core compares `location_ref` by equality only; a test guards that no core module parses it (extend the architecture-import test spirit).
- **Authority boundary (§14.3):** the `EmbodimentPort` surface exposes no intent/mode/priority decision — asserted structurally.
- **No regression (§14.12):** `run_regression_tests.sh` stays green; v1.1 runtime primitives untouched.

---

## 8. Risks / notes
- **Authority creep** (§15) — the port having *no* action-execution method is the structural guard; Phase 2 adapters translate only already-authorized requests.
- **Budget quagmire** (§15) — hold the line at 4 dimensions; the `budget_decision` signature discourages ad-hoc additions.
- **Location leakage** — opacity is a docstring *contract* + an import guard, not just convention.
- **#158 gate** — slice 5 (persistence) must not land before #158; slices 1–4 are unaffected.
- **FocusLease coupling deferred** — do not wire embodiment↔lease in Phase 1 (OQ1); it's Phase 3.

---

## 9. Summary of decisions baked in (for review)
1. **Migration split:** 1a (model/port/lifecycle/budgets/coordinator) executes now, migration-free; 1b (persistence) waits on #158.
2. **OQ1:** no new lease type, no lease coupling in Phase 1 (reuse primary FocusLease, wired in Phase 3).
3. **OQ2:** per-agent budgets seeded from global defaults; per-role deferred.
4. **Authority boundary** enforced in the *port surface* (no action/intent methods), not just docs.

Awaiting review before implementation begins.
