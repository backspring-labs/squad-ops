---
title: Deterministic Test Scaffolding (Fill-Slot QA Suites)
status: proposed
author: jladd
created_at: '2026-08-13T00:00:00Z'
---
# SIP: Deterministic Test Scaffolding (Fill-Slot QA Suites)

## Status
Proposed

**Targets:** acceptance decision after Stage 1e closes (the evidence base is the stack-#2 roll ledger this SIP cites); implementation in whatever feature window the owner assigns — the change is qa-surface-scoped and stack-opt-in, so it can ride as an even-minor feature or land per-stack.
**Builds on:** SIP-0100 (scaffold ownership, fill slots, the frozen harness — this SIP is its test-side completion), SIP-0098 (verification contract; the shells derive from the same manifest facts as the behavioral probes), #877 (execution-model guidance — the experiment whose result motivates this), #866 (context completeness), #818 (criteria packs — the per-stack seam the scaffold emission keys on).

## 1. Abstract

The qa suite is the last build artifact whose *mechanical* layer — imports, file placement, invocation form, response-envelope paths — is invented fresh by an LLM every roll. The v1.6 stack-#2 ledger shows that layer to be the dominant cause of run death, that guidance shrinks the invention space but does not close it, and that every deterministic verification layer added this release (typed checks, derived probes, the compile gate) has been reliable while the authored mechanical layer failed in a new way almost every roll. This SIP applies the release's own proven pattern — *scaffold the interface deterministically; the LLM fills judgment only* (SIP-0100, for app code) — to the test suite: the walking-skeleton expander additionally emits a deterministic test scaffold (correct imports from the shipped tree, harness reset, one test shell per contract-derived behavior with the invocation call and declared-status assertion pre-written), and `qa.test` becomes a fill-mode task whose author supplies **domain assertion bodies only**.

## 2. Problem Statement — the mechanical-failure ladder

Every entry is a run-terminating or round-burning failure of the suite's *mechanics*, not its judgment (all on `group_run`, stack #2 unless noted):

- **Roll 9** (`cyc_a92eaa4f4052`): suite imports `supertest` — not in `package.json`; collection death.
- **Roll 13** (`cyc_732b773cf323`): suite calls `.get()` on a `Record` (a `Map` assumption about an invisible const shape — #875) and sides with a self-contradictory probe on status.
- **Roll 14** (`run_02cc78b7acbe`, original): live-`fetch` suite against `localhost:3000` — no server exists under `vitest run`; two rounds repaired the crash, not the strategy; run terminated (#877).
- **Roll 14 resume attempts** (post-#877 guidance, clean-workspace attempt): a zero-byte emission; a `../`-prefixed fence path the extractor rightly refused; dynamic-route handlers invoked **without the `{ params }` context argument the supplement explicitly teaches**; the error envelope read at an invented path (`error_code` at top level); a probable wrong-module import for the join/leave handlers.
- **#884**: the repair-locus fallback let a dev-role repairer rewrite the suite with no qa guidance — reintroducing live-fetch verbatim. A scaffold-frozen mechanical spine bounds even this class: slot-level repair cannot change the invocation strategy.

Two structural facts sharpen the cost:

1. **The mechanics tail persists through guidance.** #877 fixed the *strategy* — post-fix suites import handlers and invoke in-process — but the tail (`params` arg, envelope path, module choice) still killed the attempts. This repeats the #871 bounding lesson: `nextId`'s arity was shown and still misused. Teaching shrinks the invention space; only removing the authorship closes it.
2. **The runs these failures kill are otherwise green.** Roll 14's app passed 38/39 checks and, on the clean-workspace attempt, passed every contract probe over real HTTP. The one roll where the authored suite caught real app defects (roll 12's 500s), the derived probes caught the same defects independently. The suite's *mechanical* layer has terminated four runs; its unique judgment layer has yet to catch a defect the deterministic layers missed. We are paying ~20 minutes of 27B generation per attempt for the layer with negative observed yield, to obtain the layer with unproven-but-real value.

## 3. Design sketch

### 3.1 Scaffold emission (deterministic)

`expand()` for a participating stack additionally emits test-scaffold files (e.g. `__tests__/api_runs.test.ts`), derived from the same manifest facts the behavioral probes already derive from (SIP-0098; the #874 rule — statuses come from the authored `error_contract`/`success_status`, never hardcoded):

- imports resolved against the **actual expanded tree**: route-handler imports via the stack's taught alias form (`import { POST } from '@/app/api/runs/route'` — the real fill-slot paths, bracket directories included), the store seam, nothing else;
- the harness discipline pre-written: `beforeEach(reset)`;
- **one test shell per contract-derived behavior** (create → declared success status; blank rejection → the derived rejection status; not-found → declared 404 mapping; one shell per declared endpoint), each with the invocation call pre-written — `new Request(...)` construction, the `{ params }` context argument for dynamic routes — and the declared-status assertion in place;
- a **fill slot inside each shell** for domain assertions (response body shape, state effects via the store seam, cross-endpoint semantics), marked exactly like app-side fill slots;
- scaffold-owned and frozen at the spine level: SIP-0100 §2.4 enforcement applies, so no producer — qa author or repairer — can rewrite imports, invocation form, or the pre-written status assertions.

### 3.2 qa.test in fill mode

When the workspace carries a test scaffold, `qa.test` becomes a fill task (the dev-side fill-slot flow, applied to qa): the author receives the scaffold with slots and emits **slot fills only**. Emission failure modes that killed whole attempts (zero-byte file, fence-path invention, wrong placement) become structurally impossible for the spine; a bad fill degrades one test body, not the suite. The author may still add whole new test files beside the scaffold under today's rules (declared-dependency and in-process constraints) — additive judgment is not capped.

### 3.3 What stays LLM judgment

Domain semantics the manifest cannot express: body-shape assertions, state effects, sequence semantics (join-then-leave, duplicate join), edge-case selection, and any additional tests. This is precisely the layer whose value the deterministic stack cannot replace — and the only layer the roll ledger shows the LLM getting *right*.

## 4. Independence disclosure (what this deliberately narrows)

The shells derive from the manifest — the same source as the scaffold and the probes. A fully derived suite would verify implementation↔manifest consistency only and could never catch the squad misreading the PRD; that detection lives in the **fills** (and in the qa author's freedom to add tests), which remain an independent PRD reading. This SIP therefore narrows the suite's independence *to the layer where independence was ever real*, and states plainly: shell-level green is consistency evidence, not intent evidence. The run report should attribute the two layers distinctly (`tests_pass` failures split into shell failures — app-vs-contract — and fill failures — judgment), which also gives the correction router an ownership signal (#884's fix direction benefits directly).

## 5. Acceptance evidence and exit criteria

- **Baseline (already banked):** the §2 ladder — four run-terminating mechanical suite failures across rolls 9–14 under three successive guidance improvements.
- **Exit:** N consecutive stack-#2 rolls (owner sets N) with zero run-terminating *mechanical* suite failures, attribution per the run ledger; reference stack-#1 contract and manifest hashes unmoved (the M0a guard); stack #1 unaffected until its pack opts in (per-stack emission, #818's seam — no cross-stack default change).
- **Non-goals:** replacing the probes (they remain the boot-and-HTTP layer); capping authored tests; any change to `tests_pass` credit semantics (SIP-0096 untouched).

## 6. Alternatives considered

- **More guidance** — tried, three times, measured: strategy converged (#877 worked), mechanics tail persisted. Rejected as the *complete* answer; the guidance stays (it governs the fills).
- **Correction loops absorb the tail** — each mechanical death burns a ~20-minute generation round, #435 rightly caps chains at two rounds, and #884 shows the repair path can make it worse. Rejected.
- **Probes only, no authored suite** — loses the independent PRD reader and all domain-semantics coverage; roll 12's suite did catch real behavior. Rejected.
- **Author the suite from the PRD with no manifest access** (maximal independence) — maximizes divergence detection but reintroduces every mechanical failure this SIP exists to kill; independence lives in the fills instead. Rejected for the spine, preserved for the fills.
