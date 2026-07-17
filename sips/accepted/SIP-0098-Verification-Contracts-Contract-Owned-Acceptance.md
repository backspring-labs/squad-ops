---
title: Verification Contracts — Contract-Owned Acceptance Criteria
status: accepted
author: jladd (drafted with Claude)
created_at: '2026-07-17T00:00:00Z'
sip_number: 98
updated_at: '2026-07-16T21:34:29.685072Z'
---
# SIP-0098: Verification Contracts — Contract-Owned Acceptance Criteria

## Status
Accepted

**Targets:** v1.4 arc (Lane M), sequenced immediately after SIP-0099 (Contract-First Build Scaffolding)'s expander — this SIP extends the expander's output; the two ship as one contract surface. Implements the durable half of #465; #464's mechanical vocabulary guard remains as the universal fallback net.
**Builds on:** SIP-0092 (typed acceptance vocabulary + `TypedCheck`), SIP-0096 (verification evidence integrity), the #419/#420 typed-acceptance seam, the Phase-0.5 fill-only spike (attempts 3.5–3.14, the evidence base below).
**Coordinates with:** SIP-0099 Contract-First Build Scaffolding (skeleton emission — this SIP adds *how the skeleton's fill is verified* to the same emission), SIP-Externalized-Build-Sandbox (the contract's behavioral probes become the sandbox's probe script; ordering-as-data-dependency and uniform-check-environment notes from #458/#462 land here), the objective→PRD rung (blocked until the PRD sheds its embedded technical contract — §6.6 unblocks it).
**Motivating cases:** #465 (filed from attempt 3.10), plus the full criteria-lottery record: 3.9 (`cyc_323a1e35bee5`), 3.10 (`cyc_d7327f521f64`), 3.13 (`cyc_3f3132c8f675`), 3.14 (`cyc_ff5e1ecc839f`).

---

## 1. Abstract

Today, every cycle roll asks a framing LLM to re-invent the acceptance criteria for a fill contract that has not changed since the skeleton was authored. The result is a per-roll lottery: across six reviewed manifests, half contained criteria that **correct code cannot satisfy** — style-prescriptive source regexes, environment-mismatched commands, syntactically broken patterns. Prompt guidance moved the rate; it cannot zero it, because the deeper problem is ownership: the planner is authoring assertions about a surface it does not own. The criteria are fixed properties of the scaffold; only their per-roll restatement varies — and that restatement is where the defects enter. Verification belongs with the interface owner, regardless of how capable future planning models become.

This SIP makes the **verification contract a first-class, roll-invariant artifact**: a purely declarative statement of what must be true, authored once alongside the skeleton by the expander, validated mechanically *and empirically* at emission time (against the bare skeleton and against a reference fill), seeded into cycles with the skeleton, and **consumed — not authored — by framing**. Plans *bind* to contract criteria by stable ID; framing keeps decomposition, sequencing, context assembly, and prose; execution mechanics live in a separate runner-owned execution profile (§6.5). The contract is the **API between the deterministic scaffold and the probabilistic planner** — the same boundary OpenAPI draws between provider and consumer, drawn here between generation regimes. Verification stops being a dice throw and becomes a versioned, testable, diffable part of the scaffold contract.

## 2. Motivation — the evidence

The Phase-0.5 spike's bar is "built AND verified by the cycle." The build half has been repeatedly proven (manual boot + endpoint probes since attempt 3.8; the generated suite passed 4/4 three consecutive executions inside attempt 3.12). Every failed attempt since 3.8 traces to **verification**, and the residual failure class after the harness hardening arc (#437–#474) is criteria authoring:

| Attempt | Authored criteria defect | Cost |
|---|---|---|
| 3.9 | `command_exit_zero: [node, --check, …]` on **dev** tasks — Node is qa-only (#306) | 3 correct implementations failed every attempt; all 3 shared corrections burned; run dead (~2 h) |
| 3.10 | `runs_store\s*=\s*\[` (fill wrote `runs_db = {}`); quote-delimited `apiFetch` regexes that cannot match template literals | Caught only by human gate review; revision path false-approved (#466); cycle dead |
| 3.11 | (clean roll) | — |
| 3.12 | (clean roll) | — |
| 3.13 | `regex_match` on `tests/test_routes.py` — taught by the proposer fragment's own example (#472) | Framing round (~50 min); silent orchestrator death (#473) |
| 3.14 | Nine source-file regexes incl. double-escaped patterns unable to match anything | Framing round (~50 min); caught & recorded by #464/#473 |

Three structural observations:

1. **The lottery is roll-variance, not skill.** The same model, fragments, PRD, and skeleton produced clean plans in 3.11/3.12 and unwinnable ones in 3.13/3.14 — after the teaching-example fix (#472) was deployed. Guidance is sampled, not obeyed.
2. **The criteria are the only varying input.** Decomposition, skeleton, PRD, and squad were identical across all six rolls. We re-randomize exactly one thing per roll, and it is the thing that keeps failing.
3. **The criteria are knowable in advance.** Every correct criterion these plans ever needed — the five endpoints, the `ApiError` seam, the frozen files, "suite passes," "frontend builds," "app boots and answers probes" — is a fixed property of the skeleton, known at skeleton-authoring time. Re-deriving fixed properties stochastically per roll is pure downside.

External evidence points the same direction. OpenAI's *SWE-bench Verified* exists precisely because incidental/generated verification is unreliable at scale — roughly 30% of "solved" patches in the original benchmark did not match developer intent and ~8% failed fuller test suites, so a human-curated, rigor-checked verifier subset had to be built ([SWE-Bench++ analysis](https://arxiv.org/html/2512.17419v1), [benchmark field guide](https://medium.com/@adnanmasood/code-generation-repository-level-software-engineering-benchmarks-a-field-guide-to-llm-benchmarks-330bc3015d80)). SWT-Bench shows generated tests work well as *filters* precisely when their harness is fixed and trusted ([SWT-Bench](https://arxiv.org/pdf/2406.12952)). The industry lesson matches ours: **verifier quality is the binding constraint, and verifiers must be curated artifacts, not per-run emissions.**

## 3. Problem inventory

Everything this SIP must solve, each with its field evidence:

- **P1 — Criteria lottery.** Per-roll LLM authoring of typed checks produces unwinnable criteria ~50% of rolls (table above). Root cause: structural matchers against unwritten code assert *style*, and one roll cannot predict another roll's style.
- **P2 — PRD contamination.** The PRD carries the technical fill contract (file lists, `apiFetch` examples, "keep every decorator"). It anchors bad criteria habits (quoted examples → quoted regexes), makes the PRD unmaintainable as a product document, and hard-blocks the objective→PRD rung (a strategy-role-authored PRD can never contain interface specs).
- **P3 — No criteria identity.** Criteria live inline in each roll's `implementation_plan.yaml`. They cannot be versioned, diffed across rolls, validated once, or referenced by evidence. "Same check failed in two rolls" is currently unknowable except by hand.
- **P4 — Environment blindness.** Checks execute in role containers with different toolchains (#462: Node is qa-only; #469: package context). Criteria carry no environment requirements, so authoring keeps colliding with reality.
- **P5 — No enforcement of the check hierarchy.** Doctrine says behavioral > structural (AST) > textual, but nothing structural encodes it; textual checks against source files kept reappearing until #464 banned them mechanically.
- **P6 — Test-expectation ambiguity.** What the generated suite must cover (happy paths, 409/404 behaviors, isolation) was negotiated via PRD-addendum bullets (the 3.8 amendment debate) and per-roll prose — it belongs in a stable contract.
- **P7 — Frozen-surface protection is prose.** "Keep every decorator, path, and signature" is an instruction, not a check. Nothing mechanically detects a fill that rewires the skeleton.
- **P8 — Nobody verifies the verifier.** Authored criteria are never themselves tested. 3.14's patterns were syntactically incapable of matching anything; nothing could have noticed before the gate.
- **P9 — Generality.** The fix must work for any expander/build-profile, and degrade gracefully for contract-less work (novel apps, future objective→PRD cycles) without dual-path feature flags.
- **P10 — Repeatability is unmeasured.** The roadmap's Functional App Yield metric needs a stable verifier to mean anything: yield over a shifting verifier measures the verifier's variance, not the system's.

## 4. Design principles

0. **Ownership decides authorship.** The planner does not own the scaffold, so the planner does not author the scaffold's verification. This holds independent of model capability — it is the same reason a service consumer does not write the provider's API spec. The empirical lottery record (§2) is the *evidence* the boundary was missing, not the argument for it.
1. **Interface vs. implementation, extended to checks.** The scaffolding SIP scaffolds interface deterministically and lets the LLM fill implementation. Verification criteria *are* interface — they describe the contract the fill must satisfy — so they are authored deterministically, once, with the skeleton. (Doctrine: `docs/ideas/IDEA-Scaffold-Interface-vs-Implementation.md`.)
2. **Behavioral > structural > textual, enforced by construction.** The contract leads with executable probes (boot the app, hit the endpoints, run the suite, build the frontend), uses AST checks for wiring, and permits textual checks only against contract-owned documents. This codifies the #374/#376 lesson — the manual boot-and-probe validation performed by hand after every attempt becomes a contract artifact.
3. **Author once, validate twice.** A criterion enters the contract only after (a) mechanical linting and (b) empirical validation against both the bare skeleton and a reference fill (§6.2). The verifier is itself verified — the SWE-bench Verified lesson applied at the source.
4. **Bind, don't author.** Framing's value in contract-seeded cycles is decomposition, sequencing, and context — it references contract criteria by ID. Generation of checks is reserved for genuinely novel surfaces, under the #464 mechanical net.
5. **Data-driven modes, no flags.** Contract present → bind mode; contract absent → author mode. Behavior follows the artifact, never a config flag (house rule: no dual-path flags).
6. **Sandbox-forward.** Probes are declared as environment-neutral specs (command + env requirements; HTTP request + expected response). Today they execute in the qa container; when the sandbox SIP lands, the identical contract drives the ephemeral container. No rework.

## 5. What framing still owns

Explicitly unchanged: task decomposition (which files per task, how many tasks), sequencing (subject to #458 invariant ordering), context assembly, prose descriptions and prose acceptance criteria (non-blocking per #420), and textual criteria for artifacts the *plan itself* introduces (e.g. `qa_handoff.md` section headers — the one place document regexes have been winnable in every attempt). The contract constrains what a *verifiable claim about the fill* looks like; it does not plan the work.

## 6. Design

### 6.1 The artifact: `verification_contract.yaml`

Emitted by the expander alongside the skeleton, as a sibling of the interface manifest. One contract per skeleton; content-hashed; the hash recorded in each consuming run's resolved config (provenance, P3).

```yaml
contract_version: 1
skeleton:
  expander: fullstack_fastapi_react
  interface_manifest_hash: <sha256>          # binds contract to the exact skeleton
capabilities: [python, node]                   # P4: tools this contract's checks REQUIRE
                                               # (declarative; where they run is the
                                               # execution profile's concern, §6.5)

frozen:                                        # P7: mechanical frozen-surface protection
  - {path: backend/errors.py,  sha256: <…>}
  - {path: frontend/src/api.js, sha256: <…>}
  # … every non-fill file in the skeleton

fill_files:
  backend/routes.py:
    interface:                                 # signatures the fill must preserve
      - {check: endpoint_defined, id: vc-routes-endpoints,
         methods_paths: [GET /runs, POST /runs, GET /runs/{id},
                         POST /runs/{id}/join, POST /runs/{id}/leave]}
      - {check: import_present, id: vc-routes-apierror,
         module: ".errors", symbol: ApiError}
    implementation:                            # must fail/skip on bare skeleton (§6.2)
      - {check: command_exit_zero, id: vc-routes-compiles,
         argv: [python, -m, py_compile, backend/routes.py], requires: python}
  frontend/src/views/RunDetailView.jsx:
    interface:
      - {check: import_present, id: vc-detail-apifetch,
         module: "../api", symbol: apiFetch}
    implementation:
      - {check: command_exit_zero, id: vc-detail-parses,
         argv: [node, --check, frontend/src/views/RunDetailView.jsx], requires: node}

behavioral:                                    # the last word on the deliverable
  build:
    - {check: frontend_build, id: vc-frontend-builds, requires: node}
  suite:                                       # P6: the test contract, stable at last
    - {check: tests_pass, id: vc-suite-passes, requires: python}
    coverage_expectations:                     # consumed by qa.test prompting
      - create/list/get/join/leave happy paths
      - duplicate join → 409, unknown run/participant → 404
      - order-independent tests; module-level state reset per test
  probes:                                      # codified manual validation (#376) —
    - {id: vc-probe-create, subject: backend,  # declarative request/expect only; boot
       request: {method: POST, path: /runs,    # procedure/retries/timeouts are the
                 json: {title: T, datetime: D, location: L}},  # execution profile's
       expect: {status: 200, json_has: [id, participants]}}
    - {id: vc-probe-dup-join, expect: {status: 409, error_code: duplicate_participant}, …}
    # … one probe per PRD §5 behavior
```

Key schema properties: every criterion has a **stable `id`** (P3 — evidence rows, gate notes, and cross-roll diffs reference it); every executable criterion declares what it **`requires`** as a capability, not where it runs (P4 — requirements are validated against the active execution profile at plan time, not discovered at spawn time); criteria are classed **`interface`** (may pass on the bare skeleton — frozen decorators make `endpoint_defined` true pre-fill) vs **`implementation`/`behavioral`** (must *not* pass on the bare skeleton — they measure the fill). Textual (`regex_match`) criteria are schema-restricted to document artifacts, aligning the schema itself with #464 rather than relying on the runtime guard.

**Ownership at a glance:**

| Responsibility | Owner |
|---|---|
| Author the contract | Expander (with the skeleton) |
| Validate the contract | Scaffold CI (lint + bare-skeleton + reference-fill gates, §6.2) |
| Bind plans to criteria | Planner (framing — refs only, never authorship) |
| Materialize executable checks | Dispatch enrichment (refs → `TypedCheck`, via the execution profile) |
| Execute checks & probes | Verifier runtime (today: role containers; later: sandbox) |
| Record outcomes | Evidence subsystem (SIP-0096 rows, keyed by criterion ID) |

### 6.2 Emission-time validation: verifying the verifier (P8)

The expander's CI (the scaffolding SIP's Mac-owned skeleton gate) grows three contract jobs:

1. **Lint** — schema validity; regex compilation; `regex_match` targets are documents; `command_exit_zero` argv on the safelist; every `env` maps to a known environment; IDs unique.
2. **Bare-skeleton run** — every `interface` criterion **passes** against the freshly expanded skeleton (they describe frozen surface); every `implementation`/`behavioral` criterion **fails or skips** (proving it measures the fill, not the scaffold — an implementation check that passes on stubs is the #276 false-green admitted at authoring time).
3. **Reference-fill run** — the full contract **passes** against a checked-in known-good fill (the first reference fill is the manually validated 3.8/3.12 composition). This is the winnability proof: no criterion enters the contract that correct code has not already satisfied once. It is also a regression harness for the contract itself: editing the skeleton or contract re-runs both.

A contract that survives all three cannot, by construction, produce 3.9/3.10/3.13/3.14: env mismatches die in lint, unmatchable patterns die in lint or reference-fill, style prescriptions die in reference-fill (the reference fill *is* a style sample), and false-green checks die in the bare-skeleton run.

### 6.3 Orchestration: bind, don't author

- **Seeding**: the contract artifact is ingested with the skeleton set and referenced in `execution_overrides` (`contract_ref`, alongside `plan_artifact_refs`). Presence of `contract_ref` switches the cycle to bind mode (P9 — data-driven, no flag).
- **Proposers**: in bind mode, proposer prompts receive the contract's criteria index (IDs + summaries) with the instruction *bind, don't author*: each plan task lists `criteria_refs` for the fill files in its `expected_artifacts`. Authoring typed criteria for contract-covered files is rejected at plan validation; prose criteria and plan-introduced-document regexes remain legal.
- **Plan validation** (the #295/#464/#473 seam, both nets): `criteria_refs` must resolve against the contract; every contract-covered fill file in the plan must carry its `interface` + `implementation` refs (no silent descoping of verification — the #439 lesson at the criteria level); any authored typed criterion passes the existing vocabulary guard. Violations record a system-rejected gate decision (#473 semantics).
- **Dispatch**: enrichment resolves `criteria_refs` into `TypedCheck` objects (existing seam, #420) stamped with contract IDs; evaluation, correction, patch verification, and the retest path (#456) operate unchanged.
- **Rollup**: evidence rows carry criterion IDs; `RunVerificationSummary` and cycle outcome gain contract-coverage accounting — *n of m contract criteria executed-and-passed* — making "verified" quantitative and the Functional App Yield metric (P10) well-defined: a run is green iff all contract criteria pass; yield = green runs / rolls, measured against a **fixed contract hash**. Stable IDs also turn verification into **longitudinal engineering data** rather than transient run output: which criteria fail most often, which contracts yield highest, whether a given SIP moved reliability, which contract revision reduced correction cycles — the raw material for the self-improvement campaign direction and for roadmap decisions grounded in evidence rather than anecdote.

### 6.4 Behavioral probes execution

A new probe runner executes `behavioral.probes`: materialize workspace → boot the declared entrypoint → issue the declared HTTP requests → compare status/shape → emit standard check rows (`executed`, `passed`, criterion ID). Near-term it runs where `frontend_build` runs today (the qa container has the toolchain); the runner consumes only the contract's neutral probe spec, so the sandbox SIP later re-homes execution without touching the contract (design note carried from #458/#462: ordering as data dependency, uniform check environment).

### 6.5 Execution profiles: intent vs. mechanics

The contract states **what must be true**; a runner-owned **execution profile** states **how to make the checks run**: the capability→environment mapping (`python` → qa container today, sandbox image later), boot procedures for probe subjects, retry policy, timeouts, and port allocation. One default profile ships with the verifier runtime — Phase 1 needs nothing per-contract — and the sandbox SIP later ships a second profile that re-homes execution **without a single contract revision**. The two artifacts evolve on their natural cadences: contracts with skeletons, profiles with infrastructure.

One nuance is deliberate: capability *requirements* (`requires: node`) stay in the contract because they are facts about the check, not about infrastructure — and keeping them declarative preserves the #462 lesson as a lint/plan-time validation (requirement unsatisfiable under the active profile → rejected before dispatch, never discovered at spawn).

### 6.6 Contract-less mode (P9)

No `contract_ref` → today's behavior exactly: framing authors criteria under the #464 vocabulary net and #473 recorded rejection. This is the lane for genuinely novel surfaces and the future objective→PRD rung until its own contract-generation step exists. The two modes share every downstream mechanism; the only difference is where criteria come from.

### 6.7 PRD hygiene (P2)

The fill contract leaves the PRD: file lists, frozen-file language, interface examples, and test-mechanics move into the interface manifest + verification contract. The PRD returns to product-only content (features, behaviors, scope). Concretely for group_run: PRD v0.4 drops the fill-contract addendum; the contract carries it. This unblocks the objective→PRD rung by construction — a strategy-authored PRD never needs to contain a technical spec again.

## 7. Implementation phases

1. **Schema + models + linter** — `verification_contract.py` (pure, `src/squadops/cycles/` or `capabilities/scaffold/`), contract loader, lint rules; unit-tested standalone.
2. **Expander emission + CI gates** — `fullstack_fastapi_react` emits the group_run contract; bare-skeleton and reference-fill validation jobs in the skeleton CI gate; reference fill checked in from the validated 3.12 composition.
3. **Orchestration binding** — seeding (`contract_ref`), proposer prompt index + bind instruction (fragment edits), plan validation extensions at the existing gate/dispatch nets, dispatch-time `criteria_refs` resolution, evidence IDs.
4. **Probe runner** — behavioral probes in the qa-container battery; `tests_pass`/`frontend_build` re-expressed as contract entries; rollup contract-coverage accounting.
5. **Migration + measurement** — PRD v0.4 split; spike re-run in bind mode; **Functional App Yield baseline over N=5 rolls against the frozen contract hash** — the spike's exit metric and this SIP's acceptance evidence.
6. **Sandbox convergence** (coordination, not blocking) — probe execution re-homed to the ephemeral container when SIP-Externalized-Build-Sandbox lands.

## 8. Acceptance criteria

- Expander CI proves: lint clean; every interface criterion passes on the bare skeleton; every implementation/behavioral criterion fails-or-skips on the bare skeleton; full contract passes on the reference fill.
- A bind-mode cycle's plan contains **zero** framing-authored typed criteria for contract-covered files, and its evidence rows carry contract criterion IDs end-to-end (plan → envelope → check row → rollup).
- Plan validation rejects (recorded, #473-style): unresolvable refs, missing implementation-coverage for a planned fill file, authored typed criteria on contract-covered files.
- Contract-less cycles behave byte-identically to today (regression-guarded).
- Five consecutive bind-mode rolls of group_run produce zero criteria-caused failures (plan rejections or unwinnable-check run failures); yield is reported against the contract hash.

## 9. Non-goals

- Replacing the #464/#473 nets — they remain the floor for authored criteria everywhere.
- The sandbox itself (execution re-homing is a new execution profile, §6.5/§7.6).
- Objective→PRD contract *generation* (a later rung; this SIP only removes its blocker).
- Judging fill quality beyond the contract (maintainability, style) — execution-based verification is a floor, not a ceiling ([REDO](https://arxiv.org/pdf/2410.09117) discusses the gap class).

## 10. Risks & open questions

- **Contract/skeleton drift** — mitigated by hash-binding + CI co-validation; open question: should `contract_ref` resolution *fail* on interface-manifest hash mismatch or warn?
- **Reference-fill maintenance** — a second artifact to keep green; mitigated by it being exactly the expander CI's existing boot target plus fills.
- **Over-constraint** — a too-specific contract re-creates the style problem deterministically; the reference-fill gate bounds this (any criterion a real fill failed would block CI), and probes/AST checks are style-free by construction.
- **Probe flakiness** (ports, timing) — probes run against an in-process boot with retries; flake policy inherits the suite-runner's timeout discipline.
- **Amortization** — per the project value thesis, contract authoring is a per-*system* cost: one expander's contract serves every roll and every project on that stack. The spike's own history is the cost of not having it (~6 burned rolls ≈ many hours + tokens vs. an afternoon of contract authoring).
- **Future extension (not required initially): contract composition.** As expanders multiply, higher-level contracts should be able to *extend* generic ones — a domain-specific scaffold inheriting a base FastAPI contract (frozen-surface rules, boot probe shapes) and adding domain criteria — rather than restating every rule. The stable-ID + hash model accommodates this (child contracts reference parent hashes); design deferred until a second expander exists.
- **Open**: should `coverage_expectations` eventually compile to executable meta-checks over the generated suite (e.g., AST-count assertions) rather than prompt guidance? Deferred; prompt-level first, measured by yield.

## 11. Prior art

- **Consumer-driven contract testing** (Pact): consumers pin providers to versioned, machine-checked contracts instead of re-deriving expectations per integration — the bind-don't-author move, applied here between framing and the fill.
- **Schema-driven verification** (OpenAPI + Schemathesis): interface spec as the single source from which checks are *derived*, not authored ad hoc — our interface manifest → contract relationship.
- **Executable specifications** (FIT/Gherkin) and **Design by Contract** (Meyer): acceptance expressed as versioned, runnable artifacts owned by the spec, not the implementer.
- **Golden/characterization tests**: a known-good output as the winnability oracle for the verifier itself.
- **SWE-bench Verified / SWT-Bench**: at scale, verification quality — not generation — is the binding constraint, and trustworthy verifiers are curated, validated artifacts ([SWE-Bench++](https://arxiv.org/html/2512.17419v1), [SWT-Bench](https://arxiv.org/pdf/2406.12952), [field guide](https://medium.com/@adnanmasood/code-generation-repository-level-software-engineering-benchmarks-a-field-guide-to-llm-benchmarks-330bc3015d80)).

## 12. Relationship to the arc (traceability)

This SIP is the structural closure of the 2026-07 hardening arc: #464/#472 (vocabulary + teaching examples) become schema constraints; #462/#469 (environment/package context) become declared `env` requirements validated at authoring; #456/#458 (retest, ordering) remain the runtime enforcement the contract's evidence flows through; #473's recorded rejection is the failure mode for bind violations; #465 and the "hardwired manifest" / "no code structure in a PRD" design calls (2026-07-16) are its requirements statement.
