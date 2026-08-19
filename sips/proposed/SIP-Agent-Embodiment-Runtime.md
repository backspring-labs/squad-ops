---
status: proposed
title: Agent Embodiment Runtime
author: Jason Ladd
created_at: '2026-08-19T00:00:00Z'
---
# SIP: Agent Embodiment Runtime

## Status
Draft (proposed)

**Author:** Jason Ladd
**Created:** 2026-08-19
**Revision:** 1
**Targets:** the **v2.2 era** (even-minor feature lane; headline candidate). Placement is a
sequencing intent, not a date — every phase is gated by the readiness conditions in §9, and
the earliest structural work (the §7 amendments) belongs to the odd minor that precedes it.
**Builds on:** SIP-0088 (runtime modes, umbrella), SIP-0089 (agent runtime state),
**SIP-0090 (Agent Embodiment Substrate — this SIP extends and amends it; it does not
replace it)**, SIP-0091 (duty durability), SIP-031 (TaskEnvelope / A2A lineage), SIP-0096
(verification evidence integrity), SIP-0102 (sandbox environment contract),
`sips/proposed/SIP-Cross-Cycle-Memory.md` (the memory seam this SIP constrains).
**Absorbs:** two idea documents (J. Ladd, 2026-08-18): *Agent Embodiment Runtime
Architecture* (the thesis, normatively specified here) and *Distributed Agent Embodiment
Across Heterogeneous Infrastructure* (the moon shot — Appendix A, explicitly non-roadmap).
**Amends:** SIP-0090 §5.3 (record shape), §5.5 (reaffirmed, not changed), §7 (budget
dimensions extended to surface attachments), and its open question 2 — see §7 below,
recorded per the step-5a amendment discipline at acceptance.

---

## 1. Summary

> **SquadOps owns the agent. A runtime is the agent's current embodiment. The native
> BaseAgent loop is one embodiment among several — not the definition of the agent.**

This SIP makes the execution runtime a first-class, registry-described axis of the
existing SIP-0090 embodiment model, so that a persistent SquadOps agent — its identity,
memory, behavioral contract, governance, experience, and evidence — can act through
interchangeable execution engines (the native BaseAgent loop, Goose, Codex, a
Claude-oriented runtime) without losing continuity, and can hold budgeted, reconciled
attention across multiple surfaces at once.

It deliberately builds the **boundary before any second runtime**: the schema and
contract changes land while they are cheap (the `embodiments` table is empty), the native
loop is modeled as the first entry in the runtime namespace, and a foreign runtime is
admitted only after the verification program has banked the baseline that makes
cross-runtime comparison mean something.

## 2. Motivation

Three facts, in tension:

1. **Execution runtimes are the fastest-churning layer of the stack.** Agent loops, MCP
   integration, session engines, and tool frameworks are evolving monthly. Any platform
   that welds its durable concepts to today's execution machinery inherits that churn.
2. **SquadOps's durable concepts are already runtime-shaped elsewhere.** Ports and
   adapters everywhere; config-driven provider selection; the planned Ollama→Atlas
   migration is this exact play at the *model* seam. The execution seam is the one
   boundary not yet drawn — the BaseAgent loop is currently inseparable from the domain.
3. **The verification arc made runtime plurality safe.** The 1.4→1.6 program (SIP-0096,
   deterministic scaffolding, the delivered-app audit, the FAY windows) is built on the
   premise that *an agent's self-report is worthless; only executed evidence against
   delivered artifacts counts*. A system that does not trust its own native runtime's
   claims can admit a foreign runtime without weakening anything — the evidence bar was
   never lowered for the incumbent.

The strategic ordering this SIP asserts: **verification is the differentiated asset;
embodiment is distribution for it.** Identity and memory alone are table stakes — every
framework has an `agent_id` and a memory store. What is rare is machinery that proves
function. This SIP exists so that machinery can govern work executed *anywhere*.

## 3. Ownership boundary

| Layer | Owns |
|---|---|
| **SquadOps** | identity, lifecycle, behavioral contracts (prompt bundles), memory, experience, organizational context (squad, project, authority), governance, **verification and evidence**, the runtime registry, portable context, checkpoints, normalized events |
| **Embodiment runtime** | the reasoning/execution loop, model interaction, tool calls, sessions, streaming, interruption, runtime-local state |
| **Infrastructure** | containers, compute, networking, isolation, secrets, placement |

Squad membership is **organizational context — identity-side, permanently**. It is not an
embodiment, does not need an embodiment row, and survives every runtime swap for free
because identity survives. (A `squad` embodiment type was considered during design and
rejected on exactly this ground.)

## 4. The model

### 4.1 Three identities

```
agent_id        who            durable; owns continuity
embodiment_id   which body     one incarnation of the agent through one runtime
execution_id    which work     ephemeral (cycle/run/task ids — already exist)
```

`embodiment_id` is *the run_id of a body*. It is not redundant with
`(agent_id, embodiment_runtime)` for three reasons: **re-attachment** (SIP-0090's
`detached` is terminal, so a reconnect is a new incarnation with its own lifecycle and
health history), **simultaneity** (the Appendix-A fabric requires two bodies on the same
runtime at different locations — keying by the pair would foreclose it), and **evidence
anchoring** (executions FK the incarnation that performed them: which container, which
credentials epoch, which runtime version — the same attribution discipline the FAY
windows apply to deploys).

### 4.2 Two orthogonal axes

```
embodiment_runtime   the ENGINE   squadops-native | goose | codex | claude-code | …
location             the PLACE    discord guild, minecraft server, terminal, container/host
```

These are independent: the same agent embodied on `squadops-native` or on `goose` can
stand in the same Discord guild. A surface is somewhere an agent *is*, not something an
agent *runs on*.

SIP-0090's original `embodiment_type` enum (`discord | browser | minecraft | cli |
other`) dissolves under this reading — and SIP-0090's own location model proves the
point: it already carried `location_system: "discord"`. The type column was duplicated
location data, and `platform: "discord:guild_id"` additionally smuggled a location
fragment into a would-be identity field. Both columns are replaced by the single
`embodiment_runtime` id; surfaces live only in the location model, where they always
belonged.

The amended record:

```
embodiment_id           the incarnation
agent_id                who
embodiment_runtime      engine id → runtime registry (§4.3)
attachment_state        lifecycle of this body (SIP-0090 §5.2 allow-list, unchanged)
health                  (unchanged)
capability_set          (unchanged)
location_ref            place(s) — surface + position; §5 extends to one-to-many
last_health_check_at    (unchanged)
credentials_ref         secret:// indirection (SIP-0090 §9 invariant, unchanged)
```

### 4.3 The runtime registry

One identity string, classified by a registry — the established house pattern
(`FrameworkCheck`, `ScaffoldStack`): the id is the only per-row identity; everything else
is registry metadata, never a second column.

```yaml
runtime_id: goose
adapter: squadops.runtime.adapters.goose
protocol: acp                # wire protocol the adapter binds (§4.5); `custom` if none
capabilities: [shell, filesystem, mcp, streaming, persistent_sessions]
deployment_modes: [ephemeral, persistent]
contract: {agent_context: v1, events: v1, checkpoint: v1}
```

The vocabulary is closed and registry-validated; adding a runtime is a deliberate act (a
registry entry plus migration), exactly as adding a framework check is. A closed-
vocabulary pin test guards the enumeration, as `FRAMEWORK_CHECKS`'s does.

### 4.4 The native loop as peer

`embodiment_runtime: squadops-native` models the containerized BaseAgent worker — the
embodiment every agent has held invisibly since the platform existed. Its RabbitMQ
attachment, heartbeat, and agent secret are the *transport and credential details of one
platform*, exactly as a Goose adapter has its own. Two unifications fall out:

- **SIP-0089's `agent_runtime_state` becomes the health record of the native
  embodiment** — no new state is invented; already-tracked state gets its proper home.
- The standing cleanup of the hardcoded agent-name→role map in `entrypoint.py` is
  Invariant 1 (§6) in miniature and precedes any of this mechanically.

Enumerating the native loop as a peer of `goose` and `codex` is the thesis stated in the
data model: *the loop we built is not privileged; it is the embodiment we happen to be
using.*

### 4.5 The execution surface contract

SIP-0090 Phase 1 is deliberately record-only, with the action surface reserved for the
Phase-2 `EmbodimentSurfacePort`. For a presence surface that port is send/listen; for an
execution runtime it is the deliberately small `AgentRuntime` contract:

```
initialize · capabilities · create_session · execute · stream
pause · resume · cancel · inspect · terminate
```

A runtime adapter (the Goose adapter, the native adapter) is that port's implementation,
selected by `embodiment_runtime` through the adapters factory pattern. Same coordinator,
same lifecycle machinery, no parallel structure. The contract stays lifecycle-and-
execution shaped; it must never grow toward replicating any runtime's internal API.

**Wire protocol: bind to ACP where the runtime offers it** *(owner-ruled 2026-08-19)*.
The Agent Client Protocol — the open JSON-RPC standard for driving a coding agent
(session/turn model over stdio) — maps nearly one-to-one onto this contract:
`create_session`/`execute`/`stream`/`cancel` are ACP's session and prompt-turn
primitives. The rule:

- An execution runtime that speaks ACP is bound through **one shared ACP adapter**;
  its registry entry declares `protocol: acp`. Goose — the named first foreign
  embodiment — speaks ACP natively, so its adapter is protocol translation plus
  evidence capture, not behavior invention, and any future ACP-speaking runtime
  arrives nearly free.
- The **port stays protocol-neutral**: a runtime without ACP gets a bespoke adapter
  (`protocol: custom`), and `squadops-native` needs no wire at all. ACP is the
  preferred binding, never a requirement the port encodes.
- **Do not conflate with A2A** (SIP-0085, already implemented): A2A is agent↔agent
  over HTTP/SSE with agent cards — how something outside talks *to* a SquadOps
  agent. ACP is client↔agent — how SquadOps *drives* a runtime it embodies an agent
  through. The two answer different questions and both coexist with the RabbitMQ
  TaskEnvelope fabric (SIP-031), which remains the native platform's internal
  transport.
- Evidence discipline is unchanged by the protocol: ACP notifications map to the
  normalized runtime events (§4.7), and nothing a runtime reports over ACP is
  credited as verification.

### 4.6 Portable context and checkpoints — extend, don't duplicate

The portability artifacts largely exist:

- **Portable Agent Context ≈ `TaskEnvelope` + prompt bundles.** The A2A envelope already
  carries task, lineage, and inputs; the system-prompt bundle (hash-pinned) *is* the
  behavioral contract serialized. The SIP adds only what a foreign runtime needs bolted
  on: governance grants and recalled memory, as envelope extensions — not a new format.
- **ExecutionCheckpoint ≈ `run_checkpoints`.** Completed task ids, prior outputs, and
  artifact refs already exist; the extension is a normalized `next_action`/pending set
  sufficient for semantic resume. Extending the existing table is mandatory; a parallel
  checkpoint entity is prohibited (ownership-before-extension).

**The boundary test, stated in advance:** *a process that is not BaseAgent consumes a
TaskEnvelope and returns a TaskResult whose evidence survives SIP-0096 unchanged.* That
single sentence is Phase P3's exit criterion, and it is deliberately much smaller than
"integrate a runtime."

### 4.7 The evidence boundary

Runtimes **report**; SquadOps **verifies**. A runtime emits normalized events
(`session.created`, `tool.completed`, `artifact.created`, `execution.failed`, …) and
artifacts; verification, acceptance, and the evidence roll-up remain SquadOps-side and
unchanged. No runtime self-report is ever credited as verification — the same rule the
native runtime lives under today. Runtime id and version are recorded on every execution
(the deploy-pinning discipline the measurement windows already practice, applied per
execution).

## 5. Distributed attention

*The design model, owed to a well-read owner: a primary locus of identity that can push
bounded processing and attention out to peripheral surfaces — drones, cameras — while the
center holds, because attention is finite and reconciliation is centralized.*

### 5.1 Surface attachments

One embodiment may hold **one-to-many surface attachments** (Discord guild and terminal
simultaneously), each with its own attachment state — a Discord connection can drop while
the terminal holds. Attachments are managed by the surface port; they are properties *of*
an embodiment, never embodiments themselves. Singular `location_ref` grows into this
attachment set; the SIP-0090 location model (`location_system`/`location_type`) is
reused per attachment.

### 5.2 Attention is the budget — and the machinery exists

"How many places at once?" is **not a cardinality constant; it is a budget decision.**
SIP-0090 §7 already built the enforcement skeleton, implemented in
`src/squadops/runtime/budgets.py`:

- `attention` is a first-class `BudgetDimension`;
- budgets attach to the **agent**, not the embodiment — cross-embodiment usage sums,
  which is precisely "finite resources tied to a centralized identity";
- exhaustion is never silent: `budget_exhausted` forces one of the declared outcomes
  (`reject_new_activity`, `pause_current_activity`, `detach_embodiment`,
  `transition_to_ambient`, …).

This SIP makes surface attachments **consumers of that budget**: every attachment holds
an attention allocation; opening one is an acquire, dropping one a release; exhaustion
sheds peripherals by rule rather than degrading silently.

### 5.3 Posture: primary and ambient

Attention is not N equal slices. Each attachment carries a **posture** — `primary` (the
foreground locus) or `ambient` (cheap, background, watch-and-alert) — and ambient
allocations are priced lower. The vocabulary hooks exist: SIP-0089's `mode` is posture,
and `transition_to_ambient` is already an exhaustion outcome. This also answers
SIP-0090's open question 2 (per-role budget configurability) with something better than
a config knob: budgets stay uniform; *posture pricing* is where allocation policy lives.

### 5.4 Reconciliation is a named contract

Peripheral attachments observe; observations flow back and reconcile into central state
and memory through the coordinator. This obligation is explicit: an attachment that
cannot deliver its observations centrally is `desynced`, not quietly autonomous. Durable
experience is extracted to the agent's memory (the Cross-Cycle Memory seam); runtime- and
surface-local history is disposable.

### 5.5 The control plane: three dials, three owners

Concurrency, locus, and per-runtime cardinality are governed by three distinct
mechanisms — two already merged, one a registry field:

| Quantity | Controller | State |
|---|---|---|
| Embodiments at once | the `concurrency` **capacity budget** (`budgets.py`: `{allowance, in_use}`, acquire at attach / release at detach, agent-scoped so bodies sum across runtimes) | machinery merged (SIP-0090 §7) |
| Where main attention resides | the **primary FocusLease** — one per agent; the embodiment whose activity holds it is the locus; `interruptibility` and `recall_policy` are lease terms, so attention is reclaimable on declared conditions | `focus_leases` live in prod |
| Bodies per runtime type | `max_instances_per_agent` on the **registry entry**, coordinator-enforced, DB backstop at per-`(agent, runtime)` uniqueness for caps of 1 | registry field (this SIP) |

A consequence worth stating: **the §5.5 single-active invariant becomes the
concurrency allowance's default of 1.** The Appendix-A multi-body relaxation is then
not an architectural change — it is governance raising a number the enforcement
machinery already meters. Invariant and moon shot collapse into one dial.

The autonomy split: **governance sets allowances** (concurrency, attention limits,
per-runtime caps, posture prices — an agent can never raise its own); **the agent
allocates within them** (moves its primary lease, opens and sheds ambient
attachments); **the coordinator is the sole enforcement point** (every exhaustion is
an event with a forced outcome, never silent); **lease terms are the override**
(`recall_policy` reclaims attention regardless of the agent's preference). The
`AmbientPolicy` seam (SIP-0089 §4.6, merged) already closes the action side: no
primary lease + started activity → no irreversible action, so ambient peripherals
are constitutionally watch-and-alert.

**Budgets ground out in economics — three pools, distinguished by what the meter is
attached to:**

| Pool | Shape | Meter attaches to | Idle cost | Thinking cost |
|---|---|---|---|---|
| Local hardware | capacity | *occupancy* (VRAM/memory/disk held) | free, but occupies | free |
| Cloud compute | consumable | *existence* (VM/GPU-hours) | burns currency | burns currency |
| Frontier API tokens | consumable | *cognition* (tokens in/out) | free | metered per token |

The substrate enforces all three whether modeled or not — an OOM, an invoice, a rate
limit — so modeling them buys legible exhaustion instead of surprises. Two rules follow:

- **The embodiment declares a draw set, not a pool.** Placement × model provider
  determines it, and draws can be simultaneous (a cloud VM calling a frontier API is
  metered on duration *and* tokens). SIP-0090 §7.1's `compute` dimension is already the
  token meter; the refinement is that consumable pools are per-wallet — each provider's
  limit and replenishment its own — never one global scalar.
- **Posture pricing is pool-aware.** Ambient attention is nearly free on a token pool,
  free-but-occupying on capacity, and the worst possible tenant on a duration pool — so
  ambient attachments belong on token pools or local capacity, while duration pools are
  for foreground bursts, attached late and detached promptly. "Local-first, cloud-burst"
  falls out as the coarse default; the pool-aware refinement is the actual policy.

### 5.6 The guardrail

**Distributed attention ≠ distributed identity.** Peripheral attachments carry no
identity, no memory of their own, and render no verdicts — they are sensors and effectors
with delegated attention, centrally reconciled. This is what keeps the model clear of the
rejected "projections" pattern (Appendix A): peripheral attention extends one agent; it
never mints peer agents.

## 6. Invariants

1. Agent identity is never owned by a runtime.
2. Durable memory never exists exclusively inside a runtime; the memory seam is
   service-addressable (constraint on `SIP-Cross-Cycle-Memory` — see §9).
3. Runtime failure is infrastructure failure, never agent death.
4. A runtime may hold private operational state; SquadOps owns durable state.
5. The same agent must be able to inhabit different runtimes; the native loop is a peer,
   not a privileged case.
6. Runtime capabilities are discovered from the registry, never assumed.
7. Execution state is normalized sufficiently for recovery (checkpoint = extended
   `run_checkpoints`).
8. SquadOps does not recreate runtime functionality to avoid an adapter — no second
   agent loop, no MCP implementation, no session engine.
9. **Verification independence is an identity boundary.** The verifying agent of record
   never shares identity or writable memory with the producing agent. No embodiment,
   projection, or attachment arrangement may route a producer's work to a verifier that
   is the same identity.

## 7. Amendments to SIP-0090 (applied at acceptance, step-5a discipline)

| # | Amendment | Evidence |
|---|---|---|
| A1 | §5.3 record shape: `embodiment_type` and `platform` are replaced by `embodiment_runtime`; surfaces live only in the location model | The type enum was platform-granular, not a class axis; `location_system` already carried the surface; `platform: "discord:guild_id"` mixed identity with location. `embodiments` table has zero rows — the change is free now and a migration later |
| A2 | §5.5 single-active invariant: **reaffirmed as written**, one active embodiment per agent | Evaluated for per-class scoping during design and found unnecessary: one body attached to N surfaces is one row. The multi-body relaxation is Appendix-A future work, taken deliberately or not at all |
| A3 | §7 budgets: surface attachments become attention-budget consumers; attachments carry posture (`primary`/`ambient`) with posture-differentiated pricing | §5.2–§5.3 above; `budgets.py` machinery already enforces agent-level sums and non-silent exhaustion |
| A4 | Open question 2 (per-role budget config) answered by posture pricing, not per-role knobs | §5.3 above |

## 8. What this SIP does NOT do

- **No second live runtime before the FAY baseline is banked.** The measurement program's
  attribution depends on a small frozen deploy boundary; a foreign runtime is admitted
  only against a banked baseline it can be compared to.
- **No new agent loop, MCP implementation, tool framework, or session engine** (Invariant 8).
- **No distributed fabric.** Appendix A is explicitly non-roadmap; this SIP only avoids
  foreclosing it (chiefly via `embodiment_id` and the registry).
- **No movement of verification.** SIP-0096 and the acceptance machinery are untouched;
  they gain a new class of subject, not a new shape.
- **No renaming of SIP-0090's concept.** This is encapsulation and extension of the
  existing Embodiment substrate, not a parallel vocabulary.

## 9. Sequencing (readiness-gated; the 2.2 label is placement, not a date)

**Prerequisites, each named to its owner:**

- FAY baseline banked by the 1.6→1.8 measurement program (the number cross-runtime
  evaluation compares against).
- `SIP-Cross-Cycle-Memory` accepted with a **service-addressable** memory seam — the one
  assumption that would silently preclude this SIP. This constraint should be checked in
  that SIP's design review, which precedes this SIP's implementation by several releases.
- SIP-0102's environment contract expressed as a capability declaration (it is the
  execution-environment seam in embryo; writing it registry-shaped costs nothing now).
- The `entrypoint.py` name→role cleanup (already filed) — Invariant 1's mechanical floor.

**Phases (each gates the next; no dates):**

| Phase | Delivers | Exit criterion |
|---|---|---|
| P1 | SIP-0090 amendments A1–A4; registry skeleton; enum pin test | Schema amended while the table is empty; belongs in the odd minor preceding 2.2 (structural, feature-free) |
| P2 | Native modeled: `squadops-native` registry entry; a live embodiment row per worker; SIP-0089 state re-homed as its health | Every running agent container is one honest row; no behavior change |
| P3 | First foreign adapter (Goose) behind the surface port | **The §4.6 boundary test**: a non-BaseAgent process consumes a TaskEnvelope and returns SIP-0096-surviving evidence |
| P4 | Attention: attachment set, budget consumption, posture, reconciliation contract | An exhaustion event sheds an ambient attachment by rule, observably |
| P5 | Cross-runtime evaluation harness | The same pre-registered roll set run per runtime, scored with the window methodology — the payoff that justified the boundary |

Semantic checkpoint **migration** (resume on a different runtime) is deliberately outside
this SIP's committed scope: it is research-grade, and it is listed in Appendix A.

## Appendix A — Distributed Embodiment (moon shot; explicitly non-roadmap)

Absorbed from the second idea document. Recorded so its constraints shape today's
interfaces; none of it is committed scope.

- **Multi-body**: one agent, simultaneous embodiments across heterogeneous
  infrastructure (local + cloud). Requires the deliberate relaxation of §5.5 (A2) and an
  embodiment scheduler. `embodiment_id` and the registry keep it possible.
- **Memory federation**: local per-embodiment memory with CRDT-like convergence into the
  canonical store; sovereignty policy (sensitive memory local-only) as a first-class
  attribute of recall.
- **Agent presence**: "where is eve" answered as a distributed operational status.
- **Runtime migration**: checkpoint → alternate runtime → semantic resume. Semantic
  continuity, not session continuity.
- **Rejected permanently, not deferred:** the "projections" pattern — role-specialized
  embodiments of one identity (research/implementation/verification) sharing memory.
  It violates Invariant 9: an agent verifying work produced by its own identity's other
  embodiment, with shared memory, is self-mocking at organizational scale — the precise
  failure class the verification arc exists to kill.

## Provenance

Derived from the two 2026-08-18 idea documents and a 2026-08-18/19 design session whose
four rulings are normative here: **encapsulate, don't redefine** (extend SIP-0090); **no
`squad` type** (squad membership is identity-side organizational context); **collapse to
one runtime axis, orthogonal to location** (the joi-on-native vs joi-on-goose, both on
Discord, argument); **multi-surface cardinality is an attention budget with a primary
locus and centralized reconciliation** (finite delegated attention, priced by posture).
A fifth ruling (2026-08-19, mid-V7): **ACP as the preferred execution-surface wire**, §4.5.
