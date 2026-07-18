# Plan: SIP-0098 Verification Contracts

## Context

SIP-0098 makes the verification contract a first-class, roll-invariant artifact: authored
once by the expander alongside the skeleton, validated at emission time (lint +
bare-skeleton + reference-fill gates), and **bound — not authored — by framing**. The full
design lives in `sips/accepted/SIP-0098-Verification-Contracts-Contract-Owned-Acceptance.md`.
This plan pins lane routing, phase ordering, per-phase file surfaces, verification strategy,
and readiness couplings. Sequencing is expressed as couplings and exit criteria, never
calendar dates.

**SIP:** `sips/accepted/SIP-0098-Verification-Contracts-Contract-Owned-Acceptance.md`
**Sibling SIP:** `sips/accepted/SIP-0099-Contract-First-Build-Scaffolding.md` — SIP-0098
extends its expander's output; the two ship as one contract surface (see Couplings).
**Arc:** v1.4 (even minor, feature release), Lane M Scaffold headline surface.
**Evidence base:** Phase-0.5 spike attempts 3.5–3.14; the criteria-lottery record in SIP-0098 §2.

## Status & handoff (updated 2026-07-18)

The single in-repo source of truth for where the arc stands — read this first.

| Phase | State | PR |
|---|---|---|
| 98.1 Schema + linter | ✅ merged | — |
| 98.2 Expander emission + CI gates | ✅ merged | — |
| 98.3 Orchestration binding | ✅ merged | #488 |
| 98.4 Probe runner | ✅ merged **as A+B+C only** (see carve-out) | #489 |
| 98.5 Migration + measurement | ⬜ **next — Spark** | — |

**98.4 carve-out (decided 2026-07-18).** 98.4 shipped its CI-provable core:
**(A)** the probe runner + default execution profile (`src/squadops/capabilities/handlers/probe_runner.py`),
**(B)** the reference-fill/bare-skeleton CI gate running probes (the §8-bullet-1 exit criterion),
and **(C)** contract-criterion coverage accounting (`criteria_verified`/`criteria_total`/
`criteria_coverage` on `RunVerificationSummary`/`CycleOutcome`, keyed on `CheckResult.criterion_id`).

**Deferred out of 98.4 → the 98.5 lead-in:** the *live* qa.test-handler probe emission (running
probes inside a real cycle so probe rows land in run evidence). It boots uvicorn in the deployed
qa container (a Spark-owned image dependency, #306-adjacent) and can only be validated by a live
bind-mode cycle, so it is built next to its validation rather than landed unexercised on Mac —
the same call made for 98.3's live-validation deferral.

**Spark pick-up order for 98.5 (do in this sequence):**
1. **qa-handler probe emission** (the deferred 98.4 piece): the executor injects the seeded
   contract's `behavioral.probes` into the `qa.test` task inputs (mirror 98.3's criteria-index
   injection in `generate_task_plan`); `QATestHandler` reconstructs `Probe`s, calls
   `run_probes(workspace, probes)` against the materialized app workspace, and appends
   `probe_check_rows(outcomes)` to `outputs["validation_result"]["checks"]`. Provision uvicorn in
   the qa agent image so the boot succeeds (else probes degrade to `skipped`).
2. **PRD v0.4 split** (§6.7): move file lists / frozen-file language / interface examples / test
   mechanics out of the group_run PRD into the interface manifest + verification contract; human
   gate-review the diff.
3. **Shakedown + N=5 yield baseline** (§8 bullet 5): one bind-mode roll to prove the pipeline
   end-to-end on the real deployment, then five bind-mode rolls against a **frozen contract hash**;
   a run is green iff all contract criteria pass; report per-criterion failure counts. This is the
   Functional App Yield metric and SIP-0098's acceptance evidence.

**Reusable seams already built (98.1–98.4):** contract model + linter (`cycles/verification_contract.py`);
emission (`capabilities/scaffold_contract.py`); the emission-time gate (`scripts/dev/contract_gate.py`);
bind-mode seeding + both plan-validation nets + dispatch `criteria_refs`→`TypedCheck` + evidence
`criterion_id` (98.3, in `cycles/` + `adapters/cycles/dispatched_flow_executor.py`); the probe runner
+ execution profile + rollup coverage (98.4). **Contract seeding is still operator/`contract_ref`-only**
— 98.5 owns wiring a real contract into a live cycle (the expander-emits-at-runtime path or a
migration-seeded `contract_ref`).

## Lane routing & session assignment

| Phase | Lane / box | Rationale |
|---|---|---|
| 98.1 Schema + linter | **Mac** | New pure module in the cycles domain (Mac-owned surface) |
| 98.2 Expander emission + CI gates | **Mac** | Expander + skeleton CI are the scaffolding SIP's Mac-owned surface |
| 98.3 Orchestration binding | **Mac** | Executor / framing fragments / plan validation — all Mac-owned |
| 98.4 Probe runner | **Mac** (see note) | New self-contained runner module in the handler battery + rollup accounting in the cycles domain |
| 98.5 Migration + measurement | **Spark** | Bind-mode rolls need the agents/GPU/group_run deployment; the yield baseline is run here |
| 98.6 Sandbox convergence | coordination only | Non-blocking; activates when SIP-Externalized-Build-Sandbox lands |

**98.4 routing note:** the probe runner is pinned as a *new* module precisely so phase 4 does
not edit `test_runner.py` / build-check surfaces (Spark-owned by the file-ownership rule).
If implementation discovers it genuinely must modify those files beyond registration, that
slice routes to the Spark lane — coordinate rather than absorb.

## Verification strategy per phase

Ratified up front (2026-07-16): phases 1–4 are verifiable without the Spark box.

| Phase | How it is verified | Cycles needed? |
|---|---|---|
| 98.1 | Pure unit tests (schema, loader, hash, every lint rule incl. rejection cases) | None |
| 98.2 | Deterministic, LLM-free CI jobs: lint / bare-skeleton / reference-fill runs | None |
| 98.3 | Fixture tests driven through the **real `execute_cycle` entry point** (the #464/#473 test pattern — never test a hand-picked seam); then end-to-end **lite** cycles on Mac | Lite |
| 98.4 | Reference fill doubles as the probe fixture (deterministic boot + probe pass); lite cycle confirms evidence-row wiring only | Lite (wiring only) |
| 98.5 | Full 27b squad, frozen contract hash, N=5 rolls | Full (Spark) |

**Profile discipline: lite, never smoke.** The smoke profile (3b) has no builder role, so the
`builder.assemble → qa.test` tail the evidence flows through does not exist there. Lite's 7b
models are the *right* instrument for phases 3–4: their mistakes are organic fault injection
for the rejection nets, and a #473-style recorded rejection during a lite roll is machinery
evidence, not failure. What lite cannot measure — fill quality at representative model
strength — is exactly what 98.5 exists to measure.

## What already exists (do not re-create)

- **Typed check vocabulary + evaluators** — SIP-0092 `TypedCheck`, `acceptance_checks.py`
  (incl. #462 missing-tooling → `skipped`), `acceptance_check_spec.py`
  (`REGEX_DOCUMENT_SUFFIXES`, `regex_target_is_document()`).
- **The #420 seam** — `split_acceptance_criteria`; typed criteria materialize at dispatch
  enrichment. 98.3 extends this seam; it does not replace it.
- **Both plan-validation nets (#464)** — dispatch-time in `generate_task_plan`
  (`validate_criteria_scope()` raise) and the inter-workload pre-gate check in
  `DispatchedFlowExecutor._reject_invalid_plan_before_workload_gate`. Field-proven 3.14.
- **Recorded rejection semantics (#473)** — pre-gate violations record a
  `system:plan_validation` REJECTED gate decision + `GATE_DECIDED`; never a silent death.
- **Evidence integrity (SIP-0096)** — per-(check_id, subject) supersession; `tests_pass`
  synthesized from `outputs["test_result"]`; `frontend_build` from validation rows.
- **Retest path (#456)** and **invariant tail ordering (#458)** — the runtime enforcement the
  contract's evidence flows through; unchanged by this SIP.
- **The spike expander** — `src/squadops/capabilities/scaffold.py` (`InterfaceManifest`,
  `expand()`), landed via the Phase-0.5 spike (PR #429). 98.2 extends its emission; its
  productionization belongs to the scaffolding SIP.
- **The reference-fill source** — the manually validated 3.8/3.12 group_run composition
  (suite passed 4/4 three consecutive executions in 3.12; endpoints hand-probed since 3.8).

## Readiness couplings (sequencing, not dates)

1. **SIP-0099's skeleton-CI gate (phase 99.1) must land before 98.2 starts.** SIP-0099
   (Contract-First Build Scaffolding) is accepted alongside this SIP; its implementation is
   planned in `docs/plans/SIP-0099-contract-first-build-scaffolding-plan.md`, which also
   pins the recommended interleaving of the two plans' phases. 98.1 has no such dependency
   and can start immediately once this plan is approved.
2. **#433 and #434 land before 98.5.** Both are Spark-box reliability items
   (log-forwarding/restart integrity); a five-roll baseline on a box that can lose evidence
   mid-roll is not a baseline. The UPS question (Spark hard-halt history) should be resolved
   or explicitly risk-accepted before the baseline starts.
3. **Rebuild before every 98.5 roll** — agent + runtime-api images rebuilt from the tested
   merge; restart alone does not pick up new code.
4. **#470 is concurrent-safe** — may land any time; no coordination needed.
5. **#435 / #452 stay deferred** — #452 requires re-triage before it is scheduled anywhere;
   neither blocks any phase.
6. **No further spike rolls before 98.5.** The Phase-0.5 spike is closed as a manual
   exercise; its exit metric (Functional App Yield) is produced by 98.5, not by more
   hand-shepherded attempts.
7. **Release gating:** SIP-0098 is Lane M headline surface for 1.4 alongside the scaffolding
   SIP. 98.5's yield report is this SIP's acceptance evidence (§8 bullet 5) and therefore
   gates calling the headline done — but intermediate phases merge to main continuously as
   they pass review (no long-lived integration branch; the Phase-0.5 merge-cadence lesson).

## Branch model

Each phase is a feature branch off main (`feature/sip-0098-phase-N-*`) → PR → merge before
the next phase branches. Incremental commits per step within a phase. **Phases 1, 2, and 4
are inert by construction** (new modules + CI jobs; no runtime route changes). **Phase 3 is
inert until data arrives**: bind mode activates only when a cycle seeds `contract_ref` —
contract-less cycles must be byte-identical to today, and phase 3 ships the regression test
proving it. There is no feature flag anywhere (house rule; SIP-0098 principle 5).

## Phases

### 98.1 — Contract schema, models, linter (Mac)

- **New:** `src/squadops/cycles/verification_contract.py` — frozen dataclasses for the
  contract (`VerificationContract`, criterion classes for `interface` / `implementation` /
  `behavioral`, probe spec), YAML loader, content hash, and `lint()` returning
  `list[str]` errors.
  - Placement rationale: consumed by planning/dispatch (cycles domain) and emitted by the
    expander; it sits beside `acceptance_check_spec.py`, whose document-suffix rules and
    argv safelist it reuses — single-source, do not duplicate.
- Lint rules (SIP §6.2 job 1): schema validity; unique stable IDs; regexes compile;
  `regex_match` targets documents (reuse `regex_target_is_document`); `command_exit_zero`
  argv on the existing safelist; every `requires:` names a known capability;
  `interface_manifest_hash` present; criterion class rules (interface vs
  implementation/behavioral) well-formed.
- **Tests:** unit only — exact-value assertions on loader output and hash stability; one
  rejection test per lint rule; malformed-YAML / duplicate-ID / unknown-capability edge
  cases.
- **Exit:** module importable with zero orchestration imports (pure); lint catches every §2
  defect class expressible at schema level (env mismatch via `requires`, broken regexes,
  source-file regexes).

### 98.2 — Expander emission + CI gates (Mac; after SIP-0099's skeleton-CI gate lands)

- Expander emits `verification_contract.yaml` alongside the skeleton + interface manifest
  (sibling artifacts; contract binds `interface_manifest_hash`). Emission code lives with
  the expander surface, not in the cycles domain.
- **Reference fill checked in** under `tests/fixtures/reference_fills/fullstack_fastapi_react/group_run/`
  — the validated 3.8/3.12 composition (fill files only; the skeleton is expanded fresh in
  CI so drift is caught, not frozen in).
- **Three CI jobs** on the skeleton gate (SIP §6.2):
  1. Lint (98.1's linter).
  2. Bare-skeleton run — every `interface` criterion passes; every
     `implementation`/`behavioral` criterion fails-or-skips (false-green admitted at
     authoring time is a CI failure).
  3. Reference-fill run — full contract passes against skeleton + reference fill
     (winnability proof). `behavioral.probes` entries are exercised here only after 98.4
     lands the runner; `build`/`suite` behavioral checks run from day one (the toolchain
     already exists in CI).
- **Tests:** the CI jobs are themselves the tests; plus unit tests for the emission function
  (contract content derived from a fixture `InterfaceManifest`, hash determinism).
- **Exit:** SIP §8 bullet 1 green in CI; editing skeleton or contract re-runs both gates.

### 98.3 — Orchestration binding (Mac)

- **Seeding:** `contract_ref` accepted in `execution_overrides` (alongside
  `plan_artifact_refs`); ingestion with the skeleton set; contract hash recorded in the
  run's resolved config. Presence of `contract_ref` = bind mode; absence = today's behavior
  (data-driven, SIP §6.3/§6.6).
- **Proposer fragments:** bind-mode criteria index (IDs + one-line summaries) + the
  *bind, don't author* instruction in the dev/qa proposer and governance merge fragments.
  Fragment edits follow the anchored-hash discipline (recompute per-fragment sha256 +
  `manifest_hash` via `FileSystemPromptRepository.hash_fragment_file` +
  `PromptManifest.compute_manifest_hash`).
- **Plan validation, both existing nets** (extend, do not fork): `criteria_refs` resolve
  against the contract; every contract-covered fill file in the plan carries its
  `interface` + `implementation` refs (no silent descoping); authored typed criteria on
  contract-covered files rejected; capability `requires` satisfiable under the active
  execution profile. Violations at the pre-gate net record the #473 system rejection.
- **Dispatch:** enrichment resolves `criteria_refs` → `TypedCheck` stamped with contract
  criterion IDs (the #420 seam); correction / patch verification / retest untouched.
- **Evidence:** check rows carry criterion IDs end-to-end (plan → envelope → row → rollup).
- **Tests:** through real `execute_cycle` (bind-mode fixtures: resolving plan passes;
  unresolvable ref / missing coverage / authored-criteria-on-covered-file each record a
  rejection); dispatch enrichment exact-value tests; **contract-less byte-identical
  regression test**; fragment index injection unit tests.
- **Lite verification on Mac:** one bind-mode lite cycle (contract seeded) reaching dispatch
  with contract-ID-stamped checks in evidence; one deliberately broken seeding (bad ref) →
  recorded rejection. SIP §8 bullets 2–4.
- **Exit:** bind-mode plan contains zero framing-authored typed criteria for contract-covered
  files; evidence rows carry contract IDs; contract-less cycles regression-green.

### 98.4 — Probe runner (Mac; new module — see routing note)

- **New:** probe runner in the handler battery (e.g.
  `src/squadops/capabilities/handlers/probe_runner.py`): materialize workspace → boot the
  declared entrypoint per the execution profile → issue declared HTTP requests → compare
  status/shape → emit standard check rows (`executed`/`passed`, criterion ID).
- **Default execution profile** (SIP §6.5) ships with the verifier runtime: capability →
  environment mapping (today: qa container), boot procedure, retry/timeout policy, port
  allocation. Runner-owned; one profile only in this SIP.
- `tests_pass` / `frontend_build` re-expressed as contract entries surfacing through the same
  rollup (emission stays in the qa.test handler — Mac surface; SIP-0096 synthesis rules
  unchanged).
- Rollup gains contract-coverage accounting: *n of m contract criteria executed-and-passed*
  on `RunVerificationSummary` and cycle outcome.
- **Tests:** probe runner against the reference fill (deterministic pass) and against the
  bare skeleton (probes fail — stubs answer nothing); flake policy inherits suite-runner
  timeout discipline; rollup accounting exact-value tests.
- **Lite verification on Mac:** probe rows land in a lite cycle's evidence with criterion IDs.
- **Exit:** 98.2's reference-fill CI job runs the full contract including probes; §8 bullet 1
  fully green.

### 98.5 — Migration + measurement (Spark)

- **PRD v0.4:** fill contract leaves the PRD (file lists, frozen-file language, interface
  examples, test mechanics → interface manifest + contract). PRD returns to product-only
  content. Human gate review of the v0.4 diff before any roll consumes it.
- **Shakedown:** one bind-mode roll of group_run on the full squad (rebuilt images) to prove
  the pipeline end-to-end on the real deployment before measurement begins.
- **Yield baseline:** N=5 bind-mode rolls against the **frozen contract hash**. A run is
  green iff all contract criteria pass; yield = green runs / rolls. Report per-criterion
  failure counts (the longitudinal-analytics seed, SIP §6.3).
- **Exit:** SIP §8 bullet 5 — five consecutive rolls with zero criteria-caused failures
  (plan rejections or unwinnable-check run failures); yield reported against the contract
  hash. This closes the Phase-0.5 spike and provides the SIP's acceptance evidence.

### 98.6 — Sandbox convergence (coordination, non-blocking)

When SIP-Externalized-Build-Sandbox lands, it ships a second execution profile re-homing
probe/check execution to the ephemeral container — **zero contract revisions** by design
(§6.5). This plan only reserves the constraint; no work items here.

## Acceptance mapping (SIP §8 → phases)

| §8 bullet | Proven by | Environment |
|---|---|---|
| 1 — CI: lint clean; interface passes bare; impl/behavioral fail-or-skip bare; full contract passes reference fill | 98.2 (+98.4 for probes) | CI, deterministic |
| 2 — bind-mode plan has zero authored typed criteria for covered files; evidence carries contract IDs end-to-end | 98.3 | Unit + lite (Mac) |
| 3 — plan validation records rejections (unresolvable refs, missing coverage, authored criteria on covered files) | 98.3 | Unit + lite (Mac) |
| 4 — contract-less cycles byte-identical (regression-guarded) | 98.3 | Unit (Mac) |
| 5 — five consecutive bind-mode rolls, zero criteria-caused failures, yield vs frozen hash | 98.5 | Full squad (Spark) |

## Open decisions (resolve at the flagged phase, not before)

1. **`contract_ref` hash mismatch — fail or warn?** (SIP §10.) Recommendation: **fail** at
   seeding — a contract validated against a different skeleton is exactly the
   stale-evidence-after-mutation class; a warning would be read once and never again.
   Decide at 98.3 review.
2. **`coverage_expectations` → executable meta-checks?** Deferred per SIP §10; prompt-level
   first, revisit with 98.5 yield data.
3. **Reference-fill refresh procedure** — when a future skeleton change invalidates the
   checked-in fill, is the fix a new manual fill or a promoted cycle output? Decide when it
   first happens; record in the scaffolding SIP's CI docs.

## Out of scope

- The sandbox itself (SIP-Externalized-Build-Sandbox owns it; §98.6 is coordination only).
- Objective→PRD contract generation (later rung; this SIP removes its blocker via 98.5's
  PRD split).
- Replacing the #464/#473 nets — they remain the floor for authored criteria in
  contract-less mode and for plan-introduced documents everywhere.
- Fill-quality judgments beyond the contract (style, maintainability).
