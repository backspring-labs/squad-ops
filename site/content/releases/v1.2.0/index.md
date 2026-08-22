---
title: v1.2.0
---

# v1.2.0

**Released 2026-07-04** · [tag `v1.2.0`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.2.0)

First **feature release** on the even/odd minor cadence (#281): even minors carry
features, gated by headline feature SIPs. 1.2.0 is led by three — the SIP-0089
runtime-arc completion, the SIP-0090 Agent Embodiment Substrate (Phase 1), and the
SIP-0095 Cycle Create Preflight — riding a hardening base (#158, #231). Two lanes
fed it: features from the Macbook lane, hardening + supporting decisions from Spark.

### Added
- **SIP-0090 Agent Embodiment Substrate — Phase 1 (core model).** The internal
  substrate for embodied agents: an `Embodiment` lifecycle state machine
  (`unattached→attaching→attached→desynced→reconnecting→detached`) with an explicit
  transition allow-list and a single-active-embodiment-per-agent invariant (enforced
  both in code and by a Postgres partial unique index); resource budget primitives
  (attention/compute/action consumables + a concurrency capacity gauge, with
  non-silent exhaustion made type-unrepresentable); an `EmbodimentStatePort` with a
  Postgres adapter; and an `EmbodimentCoordinator` that validates transitions and
  emits canonical events. No adapter yet — Discord/browser embodiments are later
  phases (#312, #317).
- **SIP-0095 Cycle Create Preflight.** A create-time fail-fast gate: a cycle is
  rejected (HTTP 422 `PREFLIGHT_REJECTED`) when the squad can't satisfy the requested
  workloads' required roles, or names a model definitively not pulled (exact
  canonical-tag match, no family inference). An unreachable LLM backend
  warns-and-allows rather than blocking on missing evidence; warnings surface on the
  create response and in the CLI. `squadops doctor` gained model-availability parity
  via the same shared decision (#298, #309, #311, #315, #321).
- **SIP-0089 runtime-arc completion.** Cycle recruitment now routes through the
  RuntimeCoordinator with FocusLease arbitration (a lease conflict is a deferral, not
  a failure) (#233), and coordinator transitions commit lease + activity + mode in a
  single `RuntimeTransaction` unit of work with live-validated rollback (#244).
- **Validated-fullstack request-profile** — instrumentation + builder + stack for
  end-to-end framework validation (#279).

### Changed
- **Health signal consolidated to a single source of truth (#231).** `runtime_status`
  is now the canonical health signal across every read surface (API single + list
  routes, CLI, both console plugins); it is always-populated (the heartbeat ensures
  the runtime row and reconciliation backfills legacy agents), and the
  `runtime_status || network_status` fallback is gone. `network_status` is demoted to
  a deprecated back-compat field (column drop tracked separately) (#302).
- **Squad profiles consolidated to `smoke` / `lite` / `full`** (#173).

### Fixed
- **CLI now renders cycle-route error messages (#319).** They were nested under
  FastAPI's `detail` and silently dropped — the operator saw `validation failed —`
  with no reason (e.g. the preflight's actionable "pull model X"). Found via live
  cycle validation (#320).
- **Operational hardening (#158)** — configurable adapter timeouts + a DDL↔model
  drift guard; the `_schema_migrations` applier remains idempotent.
- Local-spark bootstrap models reconciled with the squad profiles (#285); QA-harness
  robustness + portable-frontend build fixes (#303, #296, #280).

### Deferred / follow-ups
- SIP-0095's materialized-plan capability check at the plan-review gate (#295) —
  deferred to land with the #186 executor decomposition; the dispatch-time check
  remains the net.
- SIP-0090 Phase 1 budget persistence + composition-root wiring — no live consumer
  until Phase 2 (Discord).

## Merged pull requests (28)

| PR | Title | Closes |
|---|---|---|
| [#322](https://github.com/backspring-labs/squad-ops/pull/322) | chore(release): 1.2.0 | — |
| [#321](https://github.com/backspring-labs/squad-ops/pull/321) | feat(SIP-0095 Phase 4): surface create-time preflight warnings (response + CLI) | — |
| [#317](https://github.com/backspring-labs/squad-ops/pull/317) | feat(SIP-0090 Phase 1): embodiment persistence — slice 1b (completes Phase 1) | — |
| [#318](https://github.com/backspring-labs/squad-ops/pull/318) | docs(sip): propose Cycle Request-Profile Naming Taxonomy — for review | — |
| [#320](https://github.com/backspring-labs/squad-ops/pull/320) | fix(#319): render cycle-route error messages in the CLI | [#319](https://github.com/backspring-labs/squad-ops/issues/319) |
| [#315](https://github.com/backspring-labs/squad-ops/pull/315) | feat(SIP-0095 Phase 3): wire create-time preflight into the cycle-create route | [#224](https://github.com/backspring-labs/squad-ops/issues/224) |
| [#314](https://github.com/backspring-labs/squad-ops/pull/314) | feat(#279): validated-fullstack request-profile (instrumentation + builder + stack) | — |
| [#311](https://github.com/backspring-labs/squad-ops/pull/311) | feat(#224): doctor model-availability parity via the shared preflight decision | — |
| [#312](https://github.com/backspring-labs/squad-ops/pull/312) | feat(SIP-0090 Phase 1): core embodiment model — slice 1a (model + budgets + port + coordinator) | — |
| [#310](https://github.com/backspring-labs/squad-ops/pull/310) | fix(#285): reconcile local-spark bootstrap models with squad-profiles | — |
| [#309](https://github.com/backspring-labs/squad-ops/pull/309) | feat(#224): model-availability preflight decision (Spark half of SIP-0095) | — |
| [#308](https://github.com/backspring-labs/squad-ops/pull/308) | docs(plan): SIP-0090 Phase 1 (core embodiment model) — for review | — |
| [#302](https://github.com/backspring-labs/squad-ops/pull/302) | refactor(#231): consolidate the health signal to runtime_status at the read surfaces | — |
| [#307](https://github.com/backspring-labs/squad-ops/pull/307) | docs(plan): 2.0 roadmap + capability-backed-agents/Continuum-console SIPs; reconcile #233/#244 | — |
| [#304](https://github.com/backspring-labs/squad-ops/pull/304) | fix(#303): qa.test harness — discover package.json, block missing frontend build, fix backend pytest path | [#303](https://github.com/backspring-labs/squad-ops/issues/303) |
| [#299](https://github.com/backspring-labs/squad-ops/pull/299) | fix(#158): make hardcoded secondary adapter timeouts configurable | [#158](https://github.com/backspring-labs/squad-ops/issues/158) |
| [#297](https://github.com/backspring-labs/squad-ops/pull/297) | fix(#296): materialize frontend config/entry files into the QA build workspace | [#296](https://github.com/backspring-labs/squad-ops/issues/296) |
| [#298](https://github.com/backspring-labs/squad-ops/pull/298) | feat(cycles): SIP-0095 Cycle Create Preflight — Phase 1 (scaffold + capability check) | [#172](https://github.com/backspring-labs/squad-ops/issues/172) |
| [#294](https://github.com/backspring-labs/squad-ops/pull/294) | Propose SIP: Cycle Create Preflight (#172 + #224) | — |
| [#293](https://github.com/backspring-labs/squad-ops/pull/293) | feat(runtime): RuntimeTransaction UoW — atomic coordinator lease+activity+mode (SIP-0089 §4.5/D25, #244) | [#244](https://github.com/backspring-labs/squad-ops/issues/244) |
| [#292](https://github.com/backspring-labs/squad-ops/pull/292) | fix(#280): generate portable frontend integration (env-driven API base + config CORS) | — |
| [#290](https://github.com/backspring-labs/squad-ops/pull/290) | fix(#276): build-acceptance — verify the frontend actually builds | — |
| [#289](https://github.com/backspring-labs/squad-ops/pull/289) | fix(#276): fail qa acceptance on stub-fallback tests that mask a broken entrypoint (Part 1) | — |
| [#287](https://github.com/backspring-labs/squad-ops/pull/287) | feat(runtime): route cycle recruitment through the coordinator (SIP-0089 §3.5, #233) | [#233](https://github.com/backspring-labs/squad-ops/issues/233) |
| [#283](https://github.com/backspring-labs/squad-ops/pull/283) | docs(plan): correct §5.5 — #198 pin already done, not a do-first item | — |
| [#284](https://github.com/backspring-labs/squad-ops/pull/284) | fix(#173): consolidate squad-profile names to smoke/lite/full + fix active_profile footgun | [#173](https://github.com/backspring-labs/squad-ops/issues/173) |
| [#282](https://github.com/backspring-labs/squad-ops/pull/282) | docs(plan): reconcile 1.2.0 release plan from the Spark-lane review | — |
| [#278](https://github.com/backspring-labs/squad-ops/pull/278) | fix(observability): raw task_type + keep focus in Prefect task names (#277) | [#277](https://github.com/backspring-labs/squad-ops/issues/277) |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [SIP-0095-Cycle-Create-Preflight](../../design/sips/SIP-0095-Cycle-Create-Preflight.md) | new | accepted |
| [SIP-Capability-Backed-Agents](../../design/sips/SIP-Capability-Backed-Agents.md) | new | proposed |
| [SIP-Continuum-Runtime-Console](../../design/sips/SIP-Continuum-Runtime-Console.md) | new | proposed |
| [SIP-Cycle-Request-Profile-Naming-Taxonomy](../../design/sips/SIP-Cycle-Request-Profile-Naming-Taxonomy.md) | new | proposed |
