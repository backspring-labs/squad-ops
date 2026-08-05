# 1.5.0 Stabilization Plan — Finish the Promises, Extract the Proven

**Established:** 2026-08-05 · **Opens:** now (v1.4.4 tagged; no open PRs, no active
cycles). Successor to the 1.4.x patch-line discipline (`docs/plans/1-4-4-patch-plan.md`):
one PR per issue with `Closes`, premise re-verified against code at build time, targeted
verification per fix, live validation before merge for structural changes, bump only
after a green confirmation shakedown. Sequencing, not dates — **substance gates the
cut** (odd-minor rule).

## Character

Feature-free by rule. Two mandates, both owner-ratified:

1. **The structural quarantine** — the big, risky refactors deliberately kept out of
   feature releases, so a regression is unambiguously the refactor (the 1.3.0
   precedent: SIP-0097 executor decomposition, #152, #234).
2. **The bulk drawdown** — the 2026-08-04 backlog sweep's approved policy: 1.5 drains
   the structural-refactor population plus SIP-0096 completion, ≈20–25 issues, with the
   ops bucket draining 2–3 riders per window **by adjacency** (never on its own merits).

One coherent claim: **the 1.4 machinery's normative promises get finished, and the
structure that survived five patch lines gets extracted while nothing else is moving.**

**Feature-free, operationalized:** contract v9 (`art_4f368ea08799`) and manifest v4
(`art_8becd104e9fc`) stay byte-stable across the entire line; no new squad-facing
capability; SIP-0102 migration steps 3–7 are explicitly held to 1.6 (reconciliation
ruling — they would make the odd minor a feature carrier). SIP-0101 and SIP-0096
completion are in scope *because* they are internal machinery finishing already-accepted
designs, not new capability: the 1.3.0 SIP-0097 precedent.

## Inputs and premise deltas (2026-08-05)

Sources: ROADMAP v1.5 entry · `docs/plans/post-1-4-roadmap-reconciliation.md` (1.5 row)
· the 2026-08-04 sweep dispositions (recorded as issue comments) ·
`docs/plans/sip-promotion-audit-2026-08-03.md` · 1.4.4 filed-forward (#724).

Deltas found while preparing this plan (the standing verify-before-schedule lesson):

- **The reconciliation's 1.5 row is partially stale**: #593/#627/#628 have closed since
  it was written; #571 shipped in 1.4.4. The "show the author the contract" family's
  open remainder is **#629 alone** (enforcement half, widened to both surfaces when
  #590 closed into it). #598 is Stack-Blueprint-shaped and moves with Generalized Build
  (1.6), except for its check-menu question (Track A5).
- **#481's named trigger has fired, and the seam partially exists.** The trigger was
  "#373 landing makes it three startup sweeps." 1.4.3 landed #373 *and* #710, and
  `src/squadops/api/runtime/startup_reaps.py` now holds three sweeps (leases #373,
  modes #710, activities #672/#561) behind one wiring gate. #481 is therefore no longer
  "extract a seam" — it is "add the stranded-cycle sweep as the fourth consumer,
  formalizing the shared cycle-terminal predicate the module already reasons about."
- **SIP-0096's remaining normative set is exactly #682/#683/#684** (audit-confirmed);
  the fourth item, #423, shipped in 1.4.4. #375/#376 are Phase-2/enhancement, not
  promotion-gating; #376's substance (final-state verification) is owned by SIP-0102
  step 4 → 1.6.
- **The god-module sizes today**: `dispatched_flow_executor.py` 3,225 lines (back above
  its post-SIP-0097 1,805 — three windows of nets and fixes accreted onto it),
  `planning_tasks.py` 1,887, `correction_runner.py` 1,269.
- `structural_plan_change_candidate` confirmed advisory-only end-to-end
  (`plan_delta.py:37` → `correction_decision.py:149` → `correction_runner.py:980` —
  recorded, persisted, never acted on). It exists to drive the SIP-0092 M3 gate, and
  the audit records that the M2→M3 gate-evaluation doc was never written.

Every premise below still gets re-verified against code at build time.

---

## Track A — Verification & correction integrity (finish the machinery's promises)

### A1. #670 — qa.test joins the typed-acceptance seam *(owner-ruled fork 1, 2026-08-04)*

Bring `qa_test.py` into `_evaluate_typed_acceptance` so authored checks AND framework
injections (#689 `undefined_names` first among them) both reach qa emissions — the
ruling's scope, which retires the M1.3 out-of-scope note at `qa_test.py:73`.
Implementation must re-examine `harness_boundary`'s #671 exemption once qa checks are
load-bearing (the ruling's own caveat). Verification: shk-3's exhibit inverted — a qa
`.py` emission produces a `typed_check_evaluation` artifact with the framework
injection present; #605's registry-wide skip property untouched.

### A2. SIP-0096 completion — #682 → #683 → #684, then promotion

- **#682** gate-waiver slice (§6.5/AC#12): `GateDecision` fields + migration (range
  1000–1099, Spark-owned) + API + roll-up `waived` population.
- **#683** wrap-up consumes `CycleOutcome` (§10/§14): `ConfidenceClassification` gets
  its structured basis; `wrapup_tasks.py` stops deriving confidence from LLM prose.
- **#684** §9 inert-check detection: N-consecutive-cycles counter on stable check
  identity + reset logic; `CycleOutcome.inert` stops being permanently empty.

Order matters: #682's fields are read by #683's consumer. **Promotion rides the 1.5.0
cut** (maintainer ritual per the audit's mechanics notes: status-line + `## Status`
conversion by hand, `accepted/ → implemented/` move, repoint the five live references
or the #336 guard fails). SIP-0096 implemented is the 1.8 scorecard's gate — this line
is where it happens.

**Trigger watch (#414):** the correction-budget reserve becomes buildable the moment a
request profile first declares `required_checks`. If that happens during A2, #414 gets
re-dispositioned then — not silently built against an empty set.

### A3. #687 + #431 — the correction chain's diagnostic inputs *(paired by ruling)*

#687 threads the sandbox app traceback into `failure_evidence` (the analyzer currently
guesses behavioral 500 causes); #431 makes extraction losses distinguishable from
work-product failures so repair stops burning budget on artifacts that were never
whole. Explicitly scoped as a pair by the sweep. Landing both **fires #557's named
trigger** — which per its own instruction then becomes a *SIP proposal* (it changes
SIP-0079 §7.7), not 1.5 code.

### A4. #435 + the bounded structural lever — correction termination measures convergence

Principle already ruled: termination may depend on progress, not only on count. Typed
acceptance gives every failure a machine-comparable `(subtask, check_id, reason)`
signature; a repeat-signature test needs no new taxonomy. **Bounded lever scope:** a
non-`none` `structural_plan_change_candidate` plus a repeating signature stops the
loop and surfaces a *plan-defect* finding to the gate/verdict — the signal becomes
load-bearing for **termination honesty** only. Full M3 plan mutation (~18 deliverables)
is a capability, stays out of the odd minor; the never-written **M2→M3 gate-evaluation
doc is a Wave-0 deliverable here** so 1.6 can decide M3 on evidence (shk-4's 3-round
placebo escape is exhibit one). This is the SIP-0079 §7.7 behavioral change the
quarantine exists for — it lands when nothing else is moving.

### A5. Curated typed-check menu — design doc + issue *(files at line open; no issue exists yet)*

The check vocabulary is 11 checks grown one exhibit at a time. The menu curates it
deliberately and is the ruled decision point for four queued questions:

- **#504's named trigger** — which fill-slot divergences get *restored* vs *reported*,
  now that #689 changed the safety calculus the module's docstring reasons from.
- **#629 layer 2 shape** — how assertion-vs-contract and prose-vs-contract diffs enter
  the vocabulary (both surfaces, per the widened scope).
- **#668** — whether DOM-testid enforcement is a 1.5 check or a 1.6 defer with a named
  trigger.
- **#598's check-half** — whether a packaging criterion (image builds/runs) enters the
  menu now, with the structural fix staying on Stack Blueprint (1.6).

### A6. #629 — contract-expectation enforcement, both surfaces *(behind A5's design)*

Layer 1 (authoring injection) shipped; this is the deterministic backstop — diff
authored-suite assertions AND plan prose against
`contract.behavior_expectation_lines()`, feeding failure evidence so repair aims at
the suite when the suite is what's wrong (the pf-54 unwinnable loop, made visible).

## Track B — The structural quarantine

### B1. #663 — executor context-assembly extraction *(the anchor; #186 strangler lineage)*

Per-task context assembly leaves `DispatchedFlowExecutor` for a capability-owned
enrichment registry. The executor is back to 3,225 lines; this is the 1.5 slice of the
strangler arc that SIP-0097 started. **Standing hazard, in writing: the two-seam
gotcha** — plan nets live on BOTH `_reject_invalid_plan_before_workload_gate` and
`_reject_unsatisfiable_plan_at_gate`; any move keeps both seams or unifies them
explicitly, never drops one (#718/#719 is the scar).

### B2. #331 — `planning_tasks.py` decomposition (1,887 lines, the third god-module)

Fold into the handler-decomposition pattern `cycle_tasks.py` already followed (#152's
package + compat shim shape).

### B3. #481 — stranded-cycle sweep as the fourth `startup_reaps` consumer *(trigger fired)*

Predicate is the reapers' question inverted: not-terminal cycles with no live run
(derived status — `Cycle` has no status field). Formalize the shared cycle-terminal
predicate the module's three sweeps each rebuild.

### B4. The as-ready pool *(land what's ready by cut; the rest rolls to 1.7 without ceremony)*

| Issue | Refactor | Note |
|---|---|---|
| #559 | task-type convention: strings at boundary, constants at core | memory-backed principle; enables #663's registry keys |
| #567 | fenced-parser CommonMark recognition engine | golden-output equivalence gate |
| #579 | frontmatter parser extraction (five byte-identical copies) | |
| #381 + #377 | status-vocabulary pair: translate Prefect/UPPERCASE at adapter boundaries | one design, two PRs |
| #576 | api domain-error exception handlers (~40 envelope blocks deleted) | wide-mechanical; regression-leaning |
| #577 | shared asyncpg pool factory + JSONB codec (retire `parse_jsonb` scatter) | wide-mechanical |
| #578 | graphlib plan-DAG + the depends_on ordering DECISION | decision recorded in-PR |
| #301 / #154 / #286 | composition-root cluster: use factories, adapter imports out of domain, no import-time config | one arc, sliced |
| #305 | collapse `network_status` fallback | model doc #231 updates in same PR |
| #574 / #575 | AMQP URL parsing; lineage ID entropy | small, independent |

## Track C — SIP-0101 Cycle Replay Harness *(implementation; deferral condition spent)*

The reconciliation slates it here, and 1.4.3/1.4.4 proved the pattern by hand four
times (stored shk-4 artifacts as live rejection proofs; replay validators
in-container). The harness turns that manual pattern into the verification backbone
**for this line's own refactors**: behavior-preserving changes (B1/B2, #567, #579)
get replay-equivalence evidence, not just unit greens. That synergy is why it builds
in Wave 0, per `docs/plans/SIP-0101-cycle-replay-harness-plan.md`.

## Track D — Operability

- **#506** — Prefect task runs materialize at dispatch, transition at terminal (ruled
  a defect against SIP-0087's purpose; touches the workflow-tracker port + adapter —
  stabilization-sized, per ruling).
- **#410, observability half only** (ruled: thinking stays ON) — thinking tokens
  surfaced to LangFuse instead of ~60% of paid generation being invisible.
- **#724** — sweep the executor's direct `applied_defaults` reads onto
  `Cycle.resolved_config()` (the #426 class; `time_budget_seconds` and siblings).
- **#707** — the two command allowlists unified into one owned seam (they disagree in
  both directions today).

## Track E — Atlas groundwork *(provider neutrality, no migration yet)*

- **#313** — provider-neutral model-availability probe (doctor's `ollama list`
  hardcode; `list_pulled_models` moved on-port).
- **LLM-port conformance suite** — the seam the endorsed Ollama→Atlas direction
  verifies against (memory-ratified approach). Groundwork only: no provider swap in
  1.5.

## Track F — Docs, debt, and the rider quota

- **#583** — the defended-bespoke ADR (approved as written; docs-only). Wave 0,
  because it stops every later review from re-deriving settled decisions.
- **#452** — remaining six inline prompt blocks into the fragment system. **Hard
  acceptance test per the sweep note: `render_hash` byte-equivalence** — pre- and
  post-move prompt bytes identical, or it's a behavioral change dressed as a refactor.
- **Ops riders (standing quota: 2–3 per window, by adjacency).** Candidates matched to
  this line's work: **#637** (locked image deps never exercised by CI — the #571
  lancedb-0.8.2 lesson, adjacent to Track C's container work), **#581** (compose
  healthchecks + `up --wait`, adjacent to every deploy window this line runs),
  **#580** (pytest-asyncio deprecation, adjacent to suite-wide test touches), **#560**
  (log hygiene, adjacent to #506). Riders are picked at each window, not pre-assigned.

---

## Sequencing (enablement order, not dates)

- **Wave 0 — enablement + design decisions:** SIP-0101 harness (C); #583 ADR; the A5
  menu design doc + issue; the SIP-0092 M2→M3 gate-evaluation doc; workspace-revision
  unification scoping spike (below). Files the two missing issues at line open.
- **Wave 1 — integrity core:** #670 (A1); #687+#431 (A3); #435+lever (A4);
  #682→#683→#684 (A2); then #629 (A6) per the menu's design.
- **Wave 2 — structural quarantine:** #663, #331, #481 anchors; as-ready pool behind
  them, replay-equivalence-verified where behavior-preserving.
- **Wave 3 — operability + groundwork:** #506, #410-half, #724, #707 (D); #313 +
  conformance seam (E).
- **Riders** attach per window throughout (F).

**Workspace-revision unification** (ROADMAP-slated, no issue, no definition doc): the
scoping spike decides whether the non-sandbox half — acceptance-workspace and
repair/retest reconstruction adopting SIP-0102 §4.6 `WorkspaceRevision` pinning, so
every verifier states which revision it ran against — is 1.5-shaped, or whether the
whole item waits on 102.3's in-cycle routing (1.6). Spike output = the issue, with a
slot in Wave 2 if buildable now.

**Lanes:** both lanes emit structural refactors (the convention; 1.3.0 precedent).
File-ownership pinning applies where surfaces are hot: executor/handlers/framing
(#663, #331, #567, A4) sit on M-lane-owned files; test-runner/build-check/agent-image/
deploy-infra (#637, #581, Track C's container pieces) on S-lane files. Coordinate
merges on `dispatched_flow_executor.py` — it is this line's hottest file.

**Migrations:** #682 carries the line's first (Spark range 1000–1099). No other track
item is expected to need one; any surprise migration is a design-review stop, not a
rider.

## Verification discipline (standing, from the 1.4.x lines)

Premise re-verified against code at build time, per item. Live validation before merge
for every structural change (1.3.0 rule). Replay-first: stored-artifact replays as
rejection/equivalence proofs before any new cycle is spent; in-container LOADED checks
against pinned image deps (never dev-venv versions); real-store tests with a
revert-check for adapter semantics. Behavior-preserving refactors carry equivalence
evidence (replay via Track C, `render_hash` for prompts, golden outputs for parsers).
Both plan-gate seams tested on any executor change.

## Cut gate

1. Core slate landed — Tracks A, C, D, E, the B anchors (B1–B3), F's #583/#452 — or
   an item explicitly re-dispositioned with a **named trigger** (never "later").
   B4 pool items land as ready; unfinished pool rolls to 1.7 without ceremony.
2. SIP-0096 promotion executed at the cut (or explicitly deferred with the reason on
   the audit doc).
3. Full regression green; a confirmation shakedown green on the deployed integrated
   line (unscored, the shk pattern); designed-failure probes for behavior changes
   (A4's termination change gets one, like #511 did).
4. Contract v9 / manifest v4 hashes unchanged across the entire line — the
   feature-free proof.
5. Bump via `scripts/maintainer/version_cli.py`; version markers synced (CLAUDE.md,
   README, ROADMAP); ROADMAP timeline entry written at cut with the as-built record.

## Explicitly out (homes named)

| Item | Home |
|---|---|
| SIP-0102 steps 3–7 (in-cycle routing, clean-room verdicts, #306 retirement, golden-path validation) | 1.6 S-lane rider (ratified) |
| SIP-0092 M3 plan mutation | 1.6 decision, on the Wave-0 gate-evaluation doc |
| #557 post-retest governance review | SIP proposal once A3 lands (its trigger) |
| #414 correction-budget reserve | trigger: a profile declares `required_checks` (watch during A2) |
| #598 packaging determinism (structural half) | Stack Blueprint / Generalized Build, 1.6 |
| #376 final-state verification | SIP-0102 step 4, 1.6 |
| #375 Phase-2 conformance | non-gating; revisit at 1.6 planning |
| Agent-comms delivery guarantees | 1.6 hardening rider (ratified) |
| #316 request-profile taxonomy | 1.8, with Campaign |
| Ollama→Atlas provider swap | post-1.5, over Track E's conformance seam |

## Risk register

- **A4 changes SIP-0079 §7.7 termination behavior** — the exact class the quarantine
  exists for; designed-failure probe + shakedown before cut.
- **A1 makes qa checks load-bearing** — watch the `harness_boundary` exemption
  (ruling's caveat) and expect first-window noise from newly-real gates.
- **B1 on the hottest file** — two-seam invariant + lane coordination + replay
  equivalence; the 1.4.4 integration-branch pattern is available if windows overlap.
- **#576/#577 are wide and mechanical** — regression + integration weight, land them
  in quiet windows.
- **#452 is only safe byte-identical** — `render_hash` equivalence is the acceptance
  test, not the diff.
