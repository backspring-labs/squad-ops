---
title: v1.3.0
---

# v1.3.0

**Released 2026-07-07** · [tag `v1.3.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.3.0)

First **stabilization release** on the even/odd minor cadence (#281): odd minors are
feature-free by rule, and the big risky structural refactors quarantined out of the
feature releases are the *product*. Spark was offline for this cycle, so the entire
core scope landed from the Macbook lane. Every structural change below was
live-validated on the deployed stack before merge.

### Changed
- **SIP-0097 Dispatched Flow Executor decomposition (#186, #295).** The 3,358-line /
  53-method executor god-object decomposed to 1,805 lines across six sliced PRs
  (#341, #344, #347–#350), extracting five plain injected collaborators: pure hoists,
  **`RunLedger` + `RunCompletion`** (append-only run evidence + terminal-outcome
  mapping — the executor now carries **zero per-run mutable state**, and
  `RunCompletion.finalize(ledger, …)` is the seam SIP-0096 §6.4 wires into),
  **`CorrectionRunner`**, **`PulseBoundaryRunner`**, and **`TaskDispatcher`** (the
  interim dispatch callables were replaced by the real collaborator per AC#9). Slice
  6 carried the arc's one behavior addition (#295): the plan-review gate validates
  the run's materialized implementation plan against the squad profile *before*
  pausing — completing SIP-0095's materialized-plan half. SIP-0097 accepted (PR #340)
  and **promoted to implemented** within this release.
- **`cycle_tasks.py` split into the `capabilities/handlers/cycle/` package (#152).**
  The 3,276-line handler monolith is now per-handler modules behind a compat shim
  (PR #339), preceded by hoisting its copy-pasted helpers into `_CycleTaskHandler`
  (#332, PR #338). Shim retirement rides the importer migration filed in #339.
- **Agent comms migrated from queue polling to a persistent push consumer (#323,
  PR #354).** The entrypoint's 1s open/close `consume()` poll is gone; agents hold
  one long-lived `subscribe()` consumer (delivery-time pickup, `prefetch_count=1`,
  ack semantics unchanged). Removes the consumer-count flapping, up-to-1s dispatch
  latency, and the `aio_pika` "closing" INFO flood that was 99.7% of retained agent
  logs — which also closed #329 (the interim log-demotion mitigation) as obsolete.
- **Dead sqlalchemy `DbRuntime` backend removed (#234, PR #356).** Audit found zero
  production callers (its factory was only ever constructed by its own tests, and
  the one production breadcrumb referenced a method that never existed).
  `src/squadops/ports/` now contains no vendor types in any contract; the `postgres`
  extra and sqlalchemy test pin are dropped. Every active persistence path is asyncpg.

### Fixed
- **Prompt-pack drift broke `merge_plan` fleet-wide (#327, PR #351).** Agents resolve
  prompts from the LangFuse registry, which was seeded once and never re-synced —
  SIP-0093's templates were missing at runtime though the files shipped in the image.
  Deploys now re-sync prompts to LangFuse (production label) as a pipeline step; the
  manifest loader hard-fails on hash mismatch (was warn-and-continue); the regen tool
  maintains the whole-manifest hash; CI guards manifest integrity. Design-debt
  follow-ups filed: #352 (registry runtime guard), #353 (build-time fingerprint).
- **`runs resume` insta-failed since 1.1.1 (#342, PR #343).** The resume route
  pre-flipped the run to RUNNING and the executor then re-issued an illegal
  RUNNING→RUNNING transition — every resume died in ~2s. Found by SIP-0097 slice-2
  live validation; pause→resume→complete now verified live end-to-end (closed #258).
- **Test suite is color-env-proof (#345, PR #346).** Shells exporting `FORCE_COLOR`
  broke CLI output assertions (rich token-splits digits under forced color); all
  assertions now ANSI-strip first.

### Added
- **CI docs-drift guards (#336, PR #357).** Version markers across
  CLAUDE.md/README/ROADMAP must equal `pyproject.toml` (this release's bump is the
  first it enforces), accepted-SIP `Targets:` lines must respect even/odd parity,
  and planning-doc references must resolve — lifecycle-aware, with the historical
  residue frozen in an explicit allowlist.

### Docs & SIP lifecycle
- **SIP-0096 Verification Evidence Integrity accepted** (PR #337, rev 2) — the 1.4
  headline alongside SIP-0091; execution plan in `docs/plans/1-4-evidence-arc-plan.md`.
- **SIP-0095 promoted to implemented** (PR #324); SIP-0091's stale `Targets: v1.3`
  remapped to v1.4 per the parity rule (#335).
- **Docs hygiene pass (#335, PR #357):** ROADMAP stats/tables reconciled (they were
  frozen at 1.0.6), Forward Cadence section added (1.3 → 1.4 → 1.6 → 2.0 pillar map),
  referenced-but-untracked drafts committed (Edge Deployment Profile, Experiment
  Queue), and a registry entry pointing at a never-committed file removed.
- **Drafts filed** (proposed, not accepted): Agent Comms Delivery Guarantees
  (PR #355 — Campaign 1.6 gate candidate), Campaign SIP revision + two-lane/evidence
  plans (PR #325).

### Deferred / follow-ups
- **#288** (same-mode lease bypass — a named Campaign 1.6 gate) slipped this release;
  pulled forward into the 1.4 window as hardening.
- **#331** (`planning_tasks.py` split) and **#333** (entrypoint config-masking
  fallbacks) → 1.5 stabilization backlog.
- SIP-0097 post-arc open questions (residual-method review / optional seventh
  collaborator; `RunOrchestrator` rename + #168 sweep) are standalone follow-ups.

## Merged pull requests (20)

| PR | Title | Closes |
|---|---|---|
| [#358](https://github.com/backspring-labs/squad-ops/pull/358) | release: 1.3.0 — first stabilization release | — |
| [#357](https://github.com/backspring-labs/squad-ops/pull/357) | docs(#335) + test(#336): fix doc drift and add the CI ratchet — last pre-1.3.0 item | [#335](https://github.com/backspring-labs/squad-ops/issues/335) [#336](https://github.com/backspring-labs/squad-ops/issues/336) |
| [#356](https://github.com/backspring-labs/squad-ops/pull/356) | refactor(#234): remove the dead sqlalchemy DbRuntime backend | [#234](https://github.com/backspring-labs/squad-ops/issues/234) |
| [#355](https://github.com/backspring-labs/squad-ops/pull/355) | SIP proposal: Agent Comms Delivery Guarantees (Campaign 1.6 gate) | — |
| [#354](https://github.com/backspring-labs/squad-ops/pull/354) | refactor(#323): migrate agent comms from queue polling to a persistent push consumer | [#323](https://github.com/backspring-labs/squad-ops/issues/323) [#329](https://github.com/backspring-labs/squad-ops/issues/329) |
| [#351](https://github.com/backspring-labs/squad-ops/pull/351) | fix(#327): prompt-pack drift — hard-fail manifest verification + deploy-time LangFuse sync | [#327](https://github.com/backspring-labs/squad-ops/issues/327) |
| [#350](https://github.com/backspring-labs/squad-ops/pull/350) | feat(#295): SIP-0097 slice 6 — reject unsatisfiable plans at the plan-review gate | [#186](https://github.com/backspring-labs/squad-ops/issues/186) [#295](https://github.com/backspring-labs/squad-ops/issues/295) |
| [#349](https://github.com/backspring-labs/squad-ops/pull/349) | refactor(#186): SIP-0097 slice 5 — TaskDispatcher extraction, interim callables retired | — |
| [#348](https://github.com/backspring-labs/squad-ops/pull/348) | refactor(#186): SIP-0097 slice 4 — PulseBoundaryRunner extraction | — |
| [#347](https://github.com/backspring-labs/squad-ops/pull/347) | refactor(#186): SIP-0097 slice 3 — CorrectionRunner extraction | — |
| [#346](https://github.com/backspring-labs/squad-ops/pull/346) | fix(#345): assemble-command CLI test assertions immune to FORCE_COLOR environments | [#345](https://github.com/backspring-labs/squad-ops/issues/345) |
| [#343](https://github.com/backspring-labs/squad-ops/pull/343) | fix(#342): resumed runs fail instantly — executor re-issues an illegal RUNNING→RUNNING transition | [#342](https://github.com/backspring-labs/squad-ops/issues/342) |
| [#344](https://github.com/backspring-labs/squad-ops/pull/344) | refactor(#186): SIP-0097 slice 2 — RunLedger + RunCompletion (the SIP-0096 §6.4 seam) | — |
| [#341](https://github.com/backspring-labs/squad-ops/pull/341) | refactor(#186): SIP-0097 slice 1 — hoist pure helpers out of DispatchedFlowExecutor | — |
| [#340](https://github.com/backspring-labs/squad-ops/pull/340) | SIP proposal: Dispatched Flow Executor Decomposition Boundaries (#186 design) | — |
| [#339](https://github.com/backspring-labs/squad-ops/pull/339) | refactor(#152): split cycle_tasks.py into the handlers/cycle package | [#152](https://github.com/backspring-labs/squad-ops/issues/152) |
| [#338](https://github.com/backspring-labs/squad-ops/pull/338) | refactor(#332): hoist copy-pasted helpers to _CycleTaskHandler base (step 0 of #152) | [#332](https://github.com/backspring-labs/squad-ops/issues/332) |
| [#337](https://github.com/backspring-labs/squad-ops/pull/337) | SIP proposal: Verification Evidence Integrity + evidence-arc reconciliation | [#334](https://github.com/backspring-labs/squad-ops/issues/334) |
| [#325](https://github.com/backspring-labs/squad-ops/pull/325) | docs: 2.0 Campaign vision anchor + Campaign Orchestration SIP (1.6) + roadmap reconciliation + 1.3 two-lane plan | — |
| [#324](https://github.com/backspring-labs/squad-ops/pull/324) | chore(SIP-0095): promote Cycle-Create Preflight → implemented | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0090-Agent-Embodiment-Substrate](../../design/sips/SIP-0090-Agent-Embodiment-Substrate.md) | new | accepted |
| [SIP-0091-Duty-Durability-via-Temporal](../../design/sips/SIP-0091-Duty-Durability-via-Temporal.md) | new | accepted |
| [SIP-0095-Cycle-Create-Preflight](../../design/sips/SIP-0095-Cycle-Create-Preflight.md) | new | implemented |
| [SIP-0096-Verification-Evidence-Integrity](../../design/sips/SIP-0096-Verification-Evidence-Integrity.md) | new | accepted |
| [SIP-0097-Dispatched-Flow-Executor-Decomposition](../../design/sips/SIP-0097-Dispatched-Flow-Executor-Decomposition.md) | new | implemented |
| [SIP-Agent-Comms-Delivery-Guarantees](../../design/sips/SIP-Agent-Comms-Delivery-Guarantees.md) | new | proposed |
| [SIP-Campaign-Orchestration](../../design/sips/SIP-Campaign-Orchestration.md) | new | proposed |
| [SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements](../../design/sips/SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md) | new | proposed |
| [SIP-Capability-Backed-Agents](../../design/sips/SIP-Capability-Backed-Agents.md) | new | proposed |
| [SIP-Cycle-Evaluation-Scorecard](../../design/sips/SIP-Cycle-Evaluation-Scorecard.md) | new | proposed |
| [SIP-Edge-Deployment-Profile](../../design/sips/SIP-Edge-Deployment-Profile.md) | new | proposed |
| [SIP-Experiment-Queue-and-Cycle-Assessment](../../design/sips/SIP-Experiment-Queue-and-Cycle-Assessment.md) | new | proposed |
