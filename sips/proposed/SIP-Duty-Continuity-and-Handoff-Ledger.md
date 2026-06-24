---
title: Duty Continuity and Handoff Ledger (DutyLog)
status: proposed
author: Jason Ladd
created_at: '2026-06-24'
---
# SIP: Duty Continuity & Handoff Ledger (DutyLog)

**Status:** Proposed
**Authors:** Jason Ladd
**Created:** 2026-06-24
**Targets:** v1.2 candidate (lands *after* SIP-0089)
**Parent vision:** `sips/accepted/SIP-0088-Agent-Runtime-Modes.md` (umbrella index)
**Depends on:** `sips/accepted/SIP-0089-Agent-Runtime-State.md` (Assignment, DutyWindow, RuntimeActivity)
**Sibling SIPs:**
- `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md` (v1.2 — embodiment continuity)
- `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` (v1.3 — *execution* durability; this SIP is *knowledge* durability)

---

## 1. Summary

SIP-0089 makes duty work **observable** (via `RuntimeActivity`) and **schedulable** (via `Assignment` + `DutyWindow`), but it leaves a gap: a duty window has no intrinsic accomplishment. A cycle *completes* against acceptance criteria; a duty window merely *ends* when time elapses. That means "what did the agent accomplish on duty, and what must the next agent pick up?" is not answerable from runtime state alone.

This SIP introduces the **DutyLog** — a durable, append-only, agent-authored continuity ledger anchored to an `Assignment`. Each duty window occupancy ("shift") produces a `DutyLogEntry` capturing three things:

1. **Accomplishments** — what got done (referencing the window's `RuntimeActivity` records as evidence).
2. **Handoffs** — open items the *next* on-duty agent must take up.
3. **Escalations** — items that exceed duty's bounded authority and must be routed *out* — to an operator, a human, or a **cycle**.

The DutyLog is what turns "an agent sat on duty" into "a responsibility a **squad** can hold indefinitely, handing off shift to shift." It is the operational analog of a shift pass-down log (NOC / SRE on-call / nursing handover).

**This SIP adds a domain object and persistence; it does not add autonomous behavior or a new execution engine.** Duty handlers (SIP-0089) still do the work; this SIP records and routes its continuity.

---

## 2. Problem Statement

Once SIP-0089 lands, an agent can enter Duty mode for a `DutyWindow` and emit `RuntimeActivity` records as work happens. But:

- **No accomplishment record survives the window.** RuntimeActivities are runtime observability atoms (`pending → running → completed`), resolved at window close. There is no authored summary of *what mattered*.
- **No cross-agent continuity.** If Max holds the 01:00–06:00 `support_duty` window and Neo holds 06:00–12:00, nothing carries "ticket #4412 is still half-investigated, watch the flapping monitor" from Max to Neo. Continuity lives in prompt history or evaporates.
- **No structured escalation path out of duty.** Duty has *bounded authority* — it triages, it doesn't undertake large fixes. There is no first-class way to say "this needs a real fix" and route it to a cycle, with the linkage recorded.
- **No product surface for duty-as-a-service.** Per the Backspring operating-company direction (reselling duty work), the auditable deliverable of an overnight ops shift *is* the handoff log. Today there is nothing to show.

> How does a standing operational responsibility accumulate institutional memory and hand off cleanly across agents and windows, without turning duty into a cycle?

---

## 3. Design Intent

1. **Anchor continuity to the responsibility, not the agent or the window.** The DutyLog belongs to an `Assignment`; entries accrete across windows and across whichever agent held each window.
2. **Author, don't derive.** Accomplishment/handoff/escalation carry *intent* that cannot be reconstructed from `RuntimeActivity` states. Entries are authored at shift boundaries, and *reference* RuntimeActivities as evidence rather than replacing them.
3. **Close the loop.** Handoffs written at window close become inputs read at the next window open. The read-at-open / write-at-close cycle is the continuity mechanism.
4. **Make escalation the bridge back to structured work.** An escalation may spawn a cycle; the link is recorded. Duty *detects and triages*; cycle *resolves*; the DutyLog *records the handoff between them*.
5. **Stay a record, not a runtime.** No mode transitions, no FocusLease arbitration, no execution. Those remain SIP-0089's coordinator concerns.
6. **Keep it small.** A single anchored entity with three structured sections and a thin port.

---

## 4. Non-Goals

This SIP does **not** propose:

- **A duty execution engine.** How work items arrive and get processed within a window (duty handlers, ticket ingestion, scheduled triggers) is SIP-0089 / future work, not here.
- **Cross-window *execution* durability** — resuming an interrupted long-running duty task across windows is SIP-0091 (Temporal). This SIP carries *knowledge*, not in-flight execution state.
- **Autonomous escalation resolution.** Whether an escalation auto-spawns a cycle or requires operator approval is a *policy* this SIP exposes a hook for; the default is operator-gated.
- **Embodiment.** Discord/browser/world surfaces are SIP-0090.
- **Replacing RuntimeActivity, artifacts, or run reports.** DutyLog is the duty-mode continuity layer; it sits *above* RuntimeActivity and *beside* the cycle artifact/run model.

---

## 5. Relationship to the Runtime SIP Family

| SIP | Layer | This SIP's relationship |
|-----|-------|-------------------------|
| 0088 Runtime Modes | Vision/index | DutyLog is a duty-mode primitive under the umbrella |
| **0089 Runtime State** | Modes, windows, focus, RuntimeActivity | **Hard dependency** — DutyLog references `Assignment`, `DutyWindow`, `RuntimeActivity` |
| 0090 Embodiment | Embodied action surfaces (v1.2) | Orthogonal; embodied actions become RuntimeActivities a DutyLog can cite |
| 0091 Duty Durability | Temporal-backed *execution* durability (v1.3) | Complementary: 0091 = resume the *work*; DutyLog = carry the *context*. DutyLog is arguably the more foundational of the two for the product. |

**Boundary with RuntimeActivity (the critical distinction):**

| | RuntimeActivity (SIP-0089 §10.6) | DutyLogEntry (this SIP) |
|---|---|---|
| Author | Machine — emitted by handlers | Agent-authored, intentional |
| Granularity | Per work-item, real-time | Per shift (one window occupancy) |
| Purpose | Observability / control | Continuity / coordination |
| Lifetime | Resolved at window close | Durable, append-only, outlives the agent |
| Analogy | Commit log | Release notes / shift handoff |

A `DutyLogEntry` *summarizes and references* the window's RuntimeActivities. Atoms → narrative.

---

## 6. Data Model

All identifiers are opaque strings. Persistence mechanics (child tables vs. JSONB) are an implementation choice; the conceptual model is normative.

### 6.1 DutyLogEntry

```yaml
DutyLogEntry:
  entry_id: string
  assignment_id: string          # FK → Assignment (SIP-0089 §10.2); the standing responsibility — the anchor
  window_ref: string             # the DutyWindow occupancy this shift covers (assignment_id + window_start)
  agent_id: string               # who held this shift
  opened_at: timestamp
  closed_at: timestamp | null    # null while the shift is in progress
  status: open | handed_off | acknowledged | superseded
  summary: string | null         # optional free-text narrative for the shift
  accomplishments: [Accomplishment]
  handoffs: [Handoff]
  escalations: [Escalation]
  authored_by: string            # agent_id, or operator id if authored/edited by a human
  created_at: timestamp
  updated_at: timestamp
```

**Invariant:** at most one `open` entry per `(assignment_id, window_ref)`. The closing duty→ambient transition (SIP-0089 §11) finalizes the open entry to `handed_off`.

### 6.2 Accomplishment

```yaml
Accomplishment:
  description: string
  activity_refs: [string]        # RuntimeActivity ids — the evidence atoms
  evidence: [string]             # artifact/vault refs produced during the shift
  outcome: completed | partial | failed
```

### 6.3 Handoff (forward — to the next on-duty agent)

```yaml
Handoff:
  handoff_id: string
  description: string
  priority: integer
  suggested_action: string | null
  state: open | claimed | resolved | dropped
  claimed_by_entry_id: string | null   # the later DutyLogEntry that picked it up
```

### 6.4 Escalation (outward — out of duty's bounded authority)

```yaml
Escalation:
  escalation_id: string
  description: string
  severity: low | medium | high | critical
  target:
    kind: operator | human | cycle | external
    ref: string | null           # e.g. operator id; populated with cycle_id once a cycle is spawned
  state: open | acknowledged | in_progress | resolved | rejected
  resolution_ref: string | null  # cycle_id (if a cycle was spawned to resolve it), ticket id, etc.
```

---

## 7. Lifecycle

The continuity loop has three moments, all tied to SIP-0089 mode transitions:

1. **Read at window open (`ambient → duty`).** The agent's *first* duty RuntimeActivity is "read prior handoffs": fetch the most recent `handed_off` entries for this `assignment_id` and surface their `open` handoffs and `open`/`acknowledged` escalations. This is how shift N's handoffs become shift N+1's inputs.
2. **Append during the shift.** Accomplishments accrue (referencing RuntimeActivities as they complete). Escalations may be raised mid-shift if something urgent exceeds duty authority.
3. **Author + finalize at window close (`duty → ambient`, within the graceful window).** The agent writes the shift summary, the forward handoffs, and any remaining escalations. The closing transition flips `status: open → handed_off`. Claiming a prior handoff in a new entry sets `claimed_by_entry_id` and may flip the prior entry to `acknowledged`.

**Missed windows.** If SIP-0089's `MissedWindowPolicy` records a missed window, a `superseded`/stub entry should note the gap so continuity readers see "no shift was held" rather than silently skipping.

---

## 8. The Escalation → Cycle Bridge

The most valuable coupling. An `Escalation` with `target.kind = cycle` is the seam from duty (reactive, bounded authority) back to the structured, acceptance-gated world:

```
duty detects/triages  →  escalation(target=cycle)  →  cycle request created  →  cycle resolves  →  resolution_ref = cycle_id
```

- The DutyLog **does not execute** the cycle; it records the routing decision and, once a cycle is created via the existing cycle request API, stores the `cycle_id` in `resolution_ref` so the trail is auditable both ways.
- **Spawn policy is a hook, not a default behavior.** v1 default: escalations are *raised* and surfaced to an operator; a human (or a future policy) decides whether to spawn a cycle. Auto-spawn is an explicit opt-in per assignment.

---

## 9. Ports & Adapters

Follows the SIP-0089 hex shape (runtime domain → port → Postgres adapter):

- **Port:** `src/squadops/ports/runtime/duty_log.py` — `DutyLogPort`
- **Adapter:** `adapters/persistence/runtime/duty_log_postgres.py`

Minimal operations (so callers don't fetch-all-and-filter):

```
append_entry(entry) -> DutyLogEntry
get_entry(entry_id) -> DutyLogEntry | None
list_entries_for_assignment(assignment_id, limit) -> [DutyLogEntry]   # most-recent first
open_handoffs(assignment_id) -> [Handoff]                              # unclaimed, across recent entries
claim_handoff(handoff_id, by_entry_id) -> Handoff
record_escalation(entry_id, escalation) -> Escalation
resolve_escalation(escalation_id, resolution_ref, state) -> Escalation
```

**Persistence:** Postgres table(s) `duty_log_entries` (+ child tables or JSONB arrays for accomplishments/handoffs/escalations). Migration range: this lands in the runtime (`track:macbook`) lane's `1100–1199` range — coordinate the exact number against SIP-0089's `1110` and any later runtime migrations.

---

## 10. CLI / API Surface (sketch)

```
squadops duty log show <assignment-id>                 # recent shift entries
squadops duty handoffs <assignment-id>                 # open handoffs awaiting the next shift
squadops duty escalations <assignment-id> [--open]     # escalations + their resolution refs
squadops duty escalate <entry-id> --severity high --target cycle   # raise an escalation (operator-gated spawn)
```

API routes mirror these under the runtime surface. The operator-facing handoff/escalation views are the **duty-as-a-service product surface** referenced in §12.

---

## 11. Open Questions / Decisions Needed

1. **Materialized vs. event-sourced.** Store entries as mutable rows finalized at close, or append immutable events and project the entry? (Leaning mutable-row for v1 simplicity; entries are append-only at the *collection* level regardless.)
2. **Authoring trigger.** Is the entry authored by the agent as a deliberate RuntimeActivity ("write_handoff"), or assembled by the coordinator at the closing transition from accumulated state? (Leaning: agent authors summary/handoffs/escalations; coordinator stamps boundaries and finalizes status.)
3. **Handoff addressing.** Are handoffs always to "the next holder of this assignment," or can they target a specific agent/role? (Default: the assignment, not a named agent — preserves squad fungibility.)
4. **Escalation auto-spawn policy.** Per-assignment opt-in, global default off — confirm.
5. **Retention.** How long do entries live? Ops continuity may want long horizons; confirm retention/rollup policy.

---

## 12. Why This Matters — Backspring Operations

Per the Backspring operating-company direction (squads that *resell duty work*), the DutyLog is not a logging nicety — it is **the product surface of duty-as-a-service**:

- It is the auditable deliverable of a shift: "here is what your AI ops squad did overnight, here is what is escalated to **you**, here is the running handoff."
- It makes duty work **sellable** (provable output), **auditable** (evidence-linked), and **continuous across agents** (squad-level, not agent-level).
- It is the spine of institutional memory for a persistent operation like *Backspring Industries Ops* — the mechanism by which a *squad* (not a single agent) holds a standing responsibility indefinitely.

This reframes DutyLog from "an observability feature" to "the coordination substrate that makes persistent, sellable duty operations possible."

---

## 13. Forward-Compatibility Requirements on SIP-0089 (do now, build later)

This SIP is **not** implemented as part of SIP-0089 Phase 2. But Phase 2 must avoid painting it into a corner. Concretely, Phase 2 should ensure:

1. **`Assignment` has a stable `assignment_id`** to anchor the ledger (already true per SIP-0089 §10.2).
2. **`RuntimeActivity` exposes a stable `runtime_activity_id`**, and its `source_ref` carries `assignment_id` + window identity — so accomplishments can reference activities and entries can be scoped to a window.
3. **Window identity is stable and addressable** as `(assignment_id, window_start)` — the `window_ref` key.

These are zero-cost constraints on Phase 2's models; building the DutyLog itself waits for this SIP's own acceptance and implementation.

---

## 14. Implementation Sketch (post-acceptance)

1. Models — `DutyLogEntry`, `Accomplishment`, `Handoff`, `Escalation` in `src/squadops/runtime/`.
2. `DutyLogPort` + Postgres adapter + migration (`11xx_duty_log.sql`).
3. Coordinator hooks — read-at-open / finalize-at-close wired into SIP-0089's mode-transition coordinator (the coordinator *invokes* the port; it does not own the ledger).
4. Escalation→cycle bridge against the existing cycle request API (operator-gated).
5. CLI/API surface + operator handoff/escalation views.
