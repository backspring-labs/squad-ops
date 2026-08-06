# 1.5.0 Stabilization Plan — Finish the Promises, Extract the Proven

**Established:** 2026-08-05 · **Revised:** 2026-08-05 after owner review (release-claim
protection: three work classes, three gates, behavioral feature-free definition,
promotion-before-RC, evidence matrix). **Opens:** now (v1.4.4 tagged; no open PRs, no
active cycles). Successor to the 1.4.x patch-line discipline
(`docs/plans/1-4-4-patch-plan.md`): one PR per issue with `Closes`, premise re-verified
against code at build time, targeted verification per fix, live validation before merge
for structural changes, bump only after a green confirmation shakedown. Sequencing, not
dates — **substance gates the cut** (odd-minor rule).

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

### Work classes (release-claim protection)

Everything in this plan is one of three classes. The classes exist so the claim cannot
be held hostage by useful-but-nonessential work, and so the cut cannot satisfy itself
administratively:

- **Release-defining** — without it, 1.5.0 has not delivered its claim. Exits the
  slate ONLY by (a) delivery, (b) proof it was already satisfied, (c) removal because
  the premise was invalid, or (d) an **owner-ratified scope change** that updates the
  release claim and the ROADMAP language. A named-trigger deferral is NOT a valid exit
  for this class.
- **Enabling** — required only because a release-defining item depends on it (the
  Gate-1 proof machinery). Scoped to the minimum that unblocks its dependents.
- **Capacity-bound** — may land while the quarantine is open; **cannot delay the
  cut**. Unfinished capacity items move to the 1.7 candidate pool with a milestone
  update and no new disposition rationale unless their premise or a dependency changed
  — this is the explicit, deliberate exception to the sweep's named-trigger rule,
  which continues to govern everything outside this pool.

| Class | Contents |
|---|---|
| Release-defining | A1–A6, SIP-0096 promotion, B1–B3, C (minimum slice), #506, #724, #583, #452 |
| Enabling (Gate 1) | C minimum slice, A5 registry design, SIP-0092 M2→M3 gate-evaluation doc, workspace-revision spike, evidence matrix, #583 |
| Capacity-bound | B4 pool (categorized), #410, #707, #313 + characterization suite, workspace-revision implementation (unless the spike promotes it), ops riders |

#506 and #724 are release-defining deliberately: #506 was owner-ruled a defect against
SIP-0087's stated purpose and slated 1.5 by that ruling; #724 completes #426's
`resolved_config` semantics. Both are "promises finished," not cleanup. #410, #707,
#313, and the conformance suite are good stabilization work but do not prove the
claim — they are capacity.

### Feature-free, defined behaviorally

Byte-stable contract v9 (`art_4f368ea08799`) and manifest v4 (`art_8becd104e9fc`) are
necessary but not sufficient — several 1.5 items change behavior without touching
either artifact (A4 termination, A1/#629 enforcement, #506 lifecycle timing). The
operative definition:

> **No new user-authored contract fields, manifest fields, request-profile
> capabilities, handler capabilities, execution surfaces, or supported workflow
> types.** Internal enforcement may become *stricter* where it completes
> already-accepted semantics (SIP-0079/0087/0092/0096/0100 — every behavior change in
> this line traces to an accepted design or a ruled defect). New CLI/API surface must
> be classified maintainer-only (SIP-0101's harness entry points are the expected
> case).

Feature-free verification at cut: no schema-version changes beyond #682's additive
migration; no new accepted contract keys, manifest keys, or request-profile fields; no
new squad-facing handler or workflow capability; existing valid inputs remain valid
except where a documented defect ruling says otherwise (each such case is in the
evidence matrix with its ruling).

## Inputs and premise deltas (2026-08-05)

Sources: ROADMAP v1.5 entry · `docs/plans/post-1-4-roadmap-reconciliation.md` (1.5 row)
· the 2026-08-04 sweep dispositions (recorded as issue comments) ·
`docs/plans/sip-promotion-audit-2026-08-03.md` · 1.4.4 filed-forward (#724).

Deltas found while preparing this plan (the standing verify-before-schedule lesson):

- **The reconciliation's 1.5 row is partially stale**: #593/#627/#628 have closed since
  it was written; #571 shipped in 1.4.4. The "show the author the contract" family's
  open remainder is **#629 alone** (enforcement half, widened to both surfaces when
  #590 closed into it). #598 is Stack-Blueprint-shaped and moves with Generalized Build
  (1.6), except for its check-menu question (A5).
- **#481's named trigger has fired, and the seam partially exists.** The trigger was
  "#373 landing makes it three startup sweeps." 1.4.3 landed #373 *and* #710, and
  `src/squadops/api/runtime/startup_reaps.py` now holds three sweeps (leases #373,
  modes #710, activities #672/#561) behind one wiring gate. #481 is therefore "add the
  stranded-cycle sweep as the fourth consumer," not "extract a seam" (B3).
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

Design-gate questions the issue must answer before code (contract-shaped, not
implementation-shaped): does qa receive all framework injections or only qa-applicable
ones; is the same check identity ever evaluated on both the dev and qa surface, and if
so how results deduplicate; does removing/keeping `harness_boundary`'s #671 exemption
expand execution scope or only evaluation scope (the ruling's own caveat).

**Acceptance criterion (lifecycle, not artifact presence):** a qa `.py` emission
receives the applicable framework-injected check set, produces one stable evaluation
per check identity, persists the result with source attribution, and participates in
the same gate and correction behavior as the equivalent non-qa emission. Verification:
shk-3's exhibit inverted; #605's registry-wide skip property untouched.

### A2. SIP-0096 completion — #682 → #683 → #684, then promotion **before the release candidate**

- **#682** gate-waiver slice (§6.5/AC#12): `GateDecision` fields + migration + API +
  roll-up `waived` population. **Defines the line's migration gate:** additive and
  nullable; historical rows remain interpretable (field-absent distinguishable from
  `waived=false`); old code reads new rows and new code reads old rows (the
  1010/`COALESCE` pattern); forward-only, with the no-downgrade policy stated in the
  migration header; replay of pre-migration artifacts produces the same roll-up.
  Range 1000–1099 (Spark-owned). The line expects **two** migrations (see
  Migrations below); any further one is a design-review stop.
- **#683** wrap-up consumes `CycleOutcome` (§10/§14): `ConfidenceClassification` gets
  its structured basis on **every** path — including fallback and replay paths, not
  just the happy path; `wrapup_tasks.py` stops deriving confidence from LLM prose.
- **#684** §9 inert-check detection: N-consecutive-cycles counter on stable check
  identity + reset logic; `CycleOutcome.inert` stops being permanently empty. Stateful
  — verified on a multi-cycle real-store sequence, not mocks.

**Promotion is part of the candidate, not an administrative act after it:** the
promotion PR lands *before* the release candidate is declared, and the final
confirmation shakedown runs against the promoted repository state. The promotion PR
carries the acceptance-criteria mapping (every AC → code/test evidence; every
normative section implemented / intentionally superseded / non-code), the
status-convention conversion, the `accepted/ → implemented/` move, and the five
live-reference repoints (else the #336 guard fails) — per the audit's mechanics notes.
SIP-0096 implemented is the 1.8 scorecard's gate.

**Trigger watch (#414):** the correction-budget reserve becomes buildable the moment a
request profile first declares `required_checks`. If that happens during A2, #414 gets
re-dispositioned then — not silently built against an empty set.

### A3. #687 + #431 — the correction chain's diagnostic inputs *(paired by ruling)*

#687 threads the sandbox app traceback into `failure_evidence`; #431 makes extraction
losses distinguishable from work-product failures. **The pair shares one deliverable
the two issues must not each half-invent: a unified failure-evidence taxonomy.** At
minimum it distinguishes: produced-and-failed-execution · incomplete/truncated ·
could-not-extract · sandbox-failed-pre-execution · app-executed-and-errored ·
verification-infrastructure-failed · evidence-unavailable.

Shared acceptance criteria: an extraction failure never enters behavioral repair; the
app traceback reaches the analyzer as structured evidence, not prose; infrastructure
failures do not consume correction attempts as product failures; replay preserves the
category; authored-vs-framework failures stay distinguishable.

Landing both **fires #557's named trigger**. Writing the #557 SIP proposal is the next
action after A3 lands but is **not cut-gating** — it may happen inside the line or
after it (it changes SIP-0079 §7.7 and gets a SIP before code, per its own ruling).

### A4. #435 + the bounded structural lever — correction termination measures convergence

Principle already ruled: termination may depend on progress, not only on count. This
is the SIP-0079 §7.7 behavioral change the quarantine exists for. It builds as
**three explicit sub-decisions, in order** — the implementation must not encode policy
through incidental control flow:

- **A4.1 Failure-signature model.** Canonical signature over typed-acceptance's
  `(subtask, check_id, reason)` vocabulary: normalization rules, ordering/duplicate
  handling, scope (per round vs per subtask), whether evidence-text changes alter it,
  identity stability across reruns and restarts.
- **A4.2 Convergence classification.** What counts as progress, no-progress,
  regression, and structural-plan suspicion — a binary repeat/no-repeat rule
  terminates prematurely when one failure persists while others are being corrected,
  so partial signature reduction counts as progress.
- **A4.3 Termination behavior.** Default policy (refined at design review): *when two
  consecutive correction rounds produce the same normalized complete failure
  signature, and both rounds carry a non-`none` `structural_plan_change_candidate`,
  the runner terminates with `plan_defect`. Partial signature reduction resets the
  repeat condition.* Signature expansion, subset behavior, and mixed
  infrastructure-failure rounds are settled by an explicit decision table in the issue
  **before code** — the design-gate artifact for this item.

**The plan-defect outcome gets a typed owner before code moves** — a
`CorrectionTermination`-shaped record (reason: exhausted | converged | plan_defect |
infrastructure_failure; repeated signature; candidate; first-seen/terminal round;
supporting artifacts) whose home is decided in the SIP-0079/0092 vocabulary, with
settled answers for: does it alter cycle status, is it persisted and replayed, does it
reach wrap-up confidence (#683 consumes it), is it terminal for the subtask or the
cycle. The implementation PR does not get to decide this ad hoc.

Full M3 plan mutation (~18 deliverables) is a capability and stays out of the odd
minor; the never-written **M2→M3 gate-evaluation doc is a Gate-1 deliverable** so 1.6
can decide M3 on evidence (shk-4's 3-round placebo escape is exhibit one).
Verification: designed-failure probe exercising the decision table's terminate rows
(the #511 pattern), plus a no-false-terminations check on a converging shakedown.

### A5. Typed-check governance — the curated menu as a machine-readable registry *(design gate for A6, #504, #668, #598-check)*

The check vocabulary is 11 checks grown one exhibit at a time. The deliverable is not
a prose list — prose registries drift — but a **governed, machine-readable check
registry** (extending `check_registry`/#686's classification-table precedent) with
validated or generated documentation. Per check, the registry answers at minimum:
stable identity; owning layer; authored/injected/both; blocking or advisory;
applicable artifact types; failure ownership (product / suite / plan / contract /
infrastructure — this is what repair aims with); availability on qa emissions (A1);
participation in correction signatures (A4.1) and `CycleOutcome`; replayability.

It is the ruled decision point for: **#504's trigger** (which fill-slot divergences
restore vs report, now that #689 changed the calculus), **#629's layer-2 shape** (A6),
**#668** (DOM-testid enforcement: 1.5 check or 1.6 defer with named trigger), and
**#598's check-half** (packaging criterion now; structural fix stays on Stack
Blueprint, 1.6).

### A6. #629 — contract-expectation enforcement, split by determinism *(behind A5)*

Layer 1 (authoring injection) shipped. The enforcement half covers two surfaces with
**different evidence quality, which do not share one blocking check just because they
share a phrase**:

- **Assertion-vs-contract** (authored suite vs `behavior_expectation_lines()`):
  deterministic where assertions are extractable — lands as a **blocking typed check**
  feeding failure evidence, so repair aims at the suite when the suite is what's wrong
  (the pf-54 unwinnable loop, made visible).
- **Prose-vs-contract** (plan prose vs pinned statuses): **advisory until it has a
  deterministic representation** — the design must state what qualifies as
  comparable prose and which artifact is presumed authoritative before it may ever
  block. If it cannot be made deterministic in this line, it ships advisory-only and
  the blocking question moves to 1.6 with a named trigger.

## Track B — The structural quarantine

### B1. #663 — executor context-assembly extraction *(the anchor; #186 strangler lineage)*

Per-task context assembly leaves `DispatchedFlowExecutor` (3,225 lines) for a
capability-owned enrichment registry. **Design boundary, decided before code:**
enrichers return **typed context fragments**; the executor owns deterministic
composition (explicit ordering, declared dependencies, defined failure behavior) —
no unrestricted mutation of a shared dict. The biggest risk is replacing a god method
with a distributed implicit pipeline; the composition point stays singular and
readable.

**Responsibility-based exit criteria** (line count is tracked but secondary): the
executor no longer constructs capability-specific task context directly; a new
capability enrichment can be added without editing the executor; **both plan-gate
seams** (`_reject_invalid_plan_before_workload_gate`,
`_reject_unsatisfiable_plan_at_gate`) end the line with one owned validation path or
explicitly documented separate ownership — never a silently dropped seam (the
#718/#719 scar, in writing).

### B2. #331 — `planning_tasks.py` decomposition (1,887 lines, the third god-module)

Follows the `cycle_tasks.py` package + compat-shim shape (#152), but a 1,887-line
module needs its **responsibility boundaries sketched in the issue before
implementation** (plan generation / validation / prompt construction / orchestration /
compat entry points — domain ownership, not function count). Acceptance: no new
cross-package import cycles; the compat shim carries a documented removal condition
and no business logic; public task names stay stable (Prefect serialization);
equivalence evidence per moved responsibility.

### B3. #481 — stranded-cycle sweep as the fourth `startup_reaps` consumer *(trigger fired)*

Predicate: not-terminal cycles with no live run. **Cycle terminality is a domain rule,
not a reap helper** — the canonical predicate lives in the cycles domain beside
`derive_cycle_status` (status is always derived; `Cycle` has no status field), and
`startup_reaps` becomes its consumer, retiring the three per-sweep rebuilds.
Definition covers the awkward rows explicitly: terminal runs but incomplete wrap-up,
no run ever created, legacy rows predating current lifecycle fields.

Acceptance: idempotent repeated startup; concurrent startup workers; **race
protection** — a cycle whose run materializes between scan and mutation is not
reaped; no effect on already-terminal cycles; emitted evidence per reaped cycle
(the 1.4.3 reap-event pattern).

### B4. The capacity pool *(capacity-bound; categorized by risk, not one bucket)*

Four categories with different verification obligations. Unfinished items move to the
1.7 candidate pool per the work-class rule.

| Category | Items | Gate |
|---|---|---|
| Pure / near-pure extractions | #567 fenced-parser engine · #579 frontmatter parser · #574 AMQP URL parsing · #575 lineage-ID entropy | golden-output / byte equivalence |
| Boundary normalization | #559 task-type convention · #381 + #377 status-vocabulary pair (one design, two PRs) · #305 network_status collapse (+ #231 doc) | boundary contract tests; replay where handler-visible |
| Wide infrastructure mechanics | #576 api exception handlers · #577 asyncpg pool factory | full regression + integration weight; quiet windows; **must not overlap each other** |
| Architecture / semantic decisions | #578 graphlib + the depends_on ordering DECISION · #301/#154/#286 composition-root cluster | **design gate first** — these alter runtime initialization or execution semantics and are not "as ready" without a recorded decision |

## Track C — SIP-0101 Cycle Replay Harness *(enabling + release-defining at minimum slice)*

1.4.3/1.4.4 proved the replay pattern by hand four times; the harness turns it into
the verification backbone for this line's own refactors. That creates a circularity
risk (structural work waits on the harness; the harness is itself large), resolved by
defining the **minimum usable slice — the Gate-1 deliverable that unblocks B1/B2**:

> Load a stored cycle/phase artifact set; pin versions and inputs; replay the relevant
> phase without running a full cycle; compare typed outputs and selected side effects;
> emit equivalence or expected-divergence evidence; fail closed on incomplete replay
> inputs; never mutate the source record; stamp harness + application versions.

Everything beyond the slice (per `docs/plans/SIP-0101-cycle-replay-harness-plan.md`)
is capacity-bound and cannot delay structural work. The harness's operator surface is
maintainer-only (feature-free classification).

Its evidence vocabulary distinguishes four things a green must name: **replay
determinism** (same inputs → equivalent outputs), **replay validity** (stored inputs
sufficient and correctly reconstructed), **behavior equivalence** (old vs new
implementation), **expected divergence** (a behavior-changing fix intentionally
differs, with the diff recorded). "Replay-equivalence evidence" without the category
named is not evidence.

## Track D — Operability

**Release-defining** (they complete accepted-design promises):

- **#506** — Prefect task runs materialize at dispatch, transition at terminal (ruled
  a defect against SIP-0087's purpose; touches the workflow-tracker port + adapter —
  stabilization-sized, per ruling). Verified against a real Prefect adapter or
  contract fixture, not mocks.
- **#724** — sweep the executor's direct `applied_defaults` reads onto
  `Cycle.resolved_config()` (the #426 class; `time_budget_seconds` and siblings).

**Capacity-bound:**

- **#410, observability half only** (ruled: thinking stays ON) — thinking tokens
  surfaced to LangFuse. If it destabilizes provider accounting it drops out; it never
  gates the cut.
- **#707** — the two command allowlists unified into one owned seam. **"Unify" hides
  a policy decision: they disagree in both directions, so consolidation cannot be
  behavior-preserving.** The issue's first deliverable is the inventory (command ×
  list-A × list-B × current effective behavior × intended behavior) and an explicit
  union/intersection/precedence ruling — then the refactor.

## Track E — Atlas groundwork *(capacity-bound; provider neutrality, no swap)*

- **#313** — provider-neutral model-availability probe (doctor's `ollama list`
  hardcode; `list_pulled_models` moved on-port).
- **LLM-port characterization suite** — honestly named: with only one live provider,
  it *characterizes* the current contract rather than proving neutrality; it must
  declare semantic capabilities (listing, generation, streaming, usage accounting,
  thinking-token reporting, error normalization, timeout/cancel) as
  required/optional/extension per provider — **not** enshrine Ollama transport
  behavior as the contract. It becomes a conformance suite when Atlas connects
  (post-1.5).

## Track F — Docs, debt, and the rider quota

- **#583** — the defended-bespoke ADR (approved as written; docs-only). Gate 1: it
  stops every later review from re-deriving settled decisions. *(Release-defining.)*
- **#452** — remaining six inline prompt blocks into the fragment system. **Hard
  acceptance test per the sweep note: `render_hash` byte-equivalence** — pre- and
  post-move prompt bytes identical, or it's a behavioral change dressed as a
  refactor. *(Release-defining.)*
- **Ops riders — admission rule, not just a count** (standing quota 2–3 per window):
  a rider must touch files already active in the window or directly verify its work;
  no schema or migration; no public-behavior change; bounded verification; it is
  **automatically dropped from the window if the anchor item destabilizes**, and it
  rides the window's shakedown without adding scenarios of its own. Candidates
  matched to this line: **#637** (locked image deps never exercised by CI — the #571
  lancedb-0.8.2 lesson, adjacent to Track C), **#581** (compose healthchecks +
  `up --wait`, adjacent to every deploy window), **#580** (pytest-asyncio
  deprecation, adjacent to suite-wide touches), **#560** (log hygiene, adjacent to
  #506). Picked at each window, never pre-assigned.

---

## Sequencing — three gates (enablement order, not dates)

### Gate 1 — Establish the proof machinery *(opens the line)*

SIP-0101 minimum slice (C) · A5 registry design · SIP-0092 M2→M3 gate-evaluation doc ·
#583 ADR · the evidence matrix instantiated · **workspace-revision spike concluded**
(below) · the two missing issues filed (A5 menu; workspace-revision, if promoted).

### Gate 2 — Finish the normative integrity promises *(release-defining core)*

#670 (A1) · #687+#431 (A3) · #435+lever (A4, on its decision table) · #682→#683→#684
(A2) · #629 per A6's determinism split · #452 · #506 · #724 · **SIP-0096 promotion
before the release candidate**.

**Gate-2 exit: a confirmation shakedown** (unscored, the shk pattern) on the deployed
integrated state — after promotion, before the structural quarantine opens. This banks
the integrity core as green *before* Gate 3's refactors land on top, so a red in the
cut shakedown is unambiguously structural — the quarantine's own
regression-attribution logic, applied one level down. It also hands Gate 3 a fresh
known-good baseline: its stored artifacts become the replay corpus the structural
anchors verify against (Track C's vocabulary). Gate 3 does not open until this
shakedown is green.

### Gate 3 — Execute the structural quarantine

Anchors #663, #331, #481 (release-defining) · then the categorized B4 pool, Track D/E
capacity items, and riders as capacity allows — none of which can delay the cut.

**Workspace-revision unification** (ROADMAP-slated, no issue, no definition doc):
**the spike must conclude before Gate 2 closes; absent an implementation-ready issue
with bounded acceptance criteria by then, the item defaults to 1.6** — no late scope
expansion. The spike decides whether the non-sandbox half (acceptance-workspace and
repair/retest reconstruction adopting SIP-0102 §4.6 `WorkspaceRevision` pinning) is
1.5-shaped or waits on 102.3's routing. Hard constraint either way: **no mixed
provenance** — a partial adoption where some verifiers report a revision and others
silently use current workspace state is worse than none.

### Concurrency policy *(semantic, beyond lane file-ownership)*

- **One open PR at a time may materially modify `dispatched_flow_executor.py`** — the
  line's hottest file.
- B1 lands before any B4 item that depends on its registry shape; A4 and B1 do not
  overlap unless their file boundaries are proven disjoint.
- #576 and #577 (wide-mechanical) never overlap each other; each lands in a quiet
  window.
- #682's migration and #683's consumer land in consecutive, not concurrent, windows
  (schema before reader) unless explicitly paired in one integration branch.
- The 1.4.4 **integration-branch pattern activates on defined overlap** (two
  behavior-changing items sharing a deploy window), not "if needed."

**Lanes:** both lanes emit structural refactors (the convention; 1.3.0 precedent).
File-ownership pinning applies where surfaces are hot: executor/handlers/framing
(#663, #331, #567, A4) sit on M-lane-owned files; test-runner/build-check/agent-image/
deploy-infra (#637, #581, Track C's container pieces) on S-lane files.

**Migrations:** the line expects exactly **two**, both in the Spark range 1000–1099
and both bound by A2's migration gate: #682's gate-waiver fields, and SIP-0101
Slice 2's `retained` column (1020 — in the accepted SIP-0101 plan all along; the
"only #682" premise here was incomplete, owner-accepted as a scope correction
2026-08-05 at the #735 review). Any further migration is a design-review stop, not
a rider.

## Verification discipline

Standing rules from the 1.4.x lines: premise re-verified against code at build time,
per item; live validation before merge for every structural change (1.3.0 rule);
replay-first — stored-artifact replays before any new cycle is spent; in-container
LOADED checks against pinned image deps (never dev-venv versions); real-store tests
with a revert-check for adapter semantics; both plan-gate seams tested on any executor
change.

**Evidence is item-specific, mapped by change class** (replay is not the sole proof
for stateful changes):

| Change class | Required evidence |
|---|---|
| Pure parsing / rendering (#567, #579, #452) | golden output / byte or `render_hash` equivalence |
| Deterministic handler extraction (B1, B2) | replay equivalence (Track C vocabulary) |
| DB adapter / codec / migration (#682, #577) | real-store tests + revert check; historical-row fixture; forward-compat |
| Startup recovery (B3) | seeded-state integration test + idempotent rerun + race case |
| Workflow lifecycle (#506) | real Prefect adapter test or contract fixture |
| Behavioral correction change (A4) | designed-failure probe matrix + no-false-termination shakedown |
| Enforcement expansion (A1, A6) | live true-positive replay exhibit + silent-on-clean shakedown |
| Provider port (E) | characterization fixtures (honest naming until a second provider) |

### The release evidence matrix *(a cut artifact, not a planning aid)*

Maintained per landed item; the completed matrix is part of the cut record. Every
release-defining item has a filled row before the cut; every behavior-stricter item's
row names the defect ruling that authorizes it (the feature-free check).

**Instantiated 2026-08-05 (Gate 1).** Update the row in the PR that lands the item.

| Item | Behavior class | Primary risk | Required proof | Live validation | Replay/golden artifact | Cut status |
|---|---|---|---|---|---|---|
| A1 #670 | enforcement expansion (ruling: fork 1, 2026-08-04) | false gates on qa emissions | true-positive replay exhibit + silent-on-clean shakedown | shk-6 green `cyc_ea0b82cfbd17`: qa evaluation artifact carries injected `undefined_names`/`harness_boundary`/`contract_assertions_match`, all passed (silent-on-clean) | qa `typed_check_evaluation` artifact | **green (PR #738 + shk-6)** |
| A2 #682 | schema/migration | historical-row compat | real-store + historical fixture + forward-compat | migration 1030 boot-applied 2026-08-05; waiver E2E on `cyc_e2e9cfd0a0c4`: accept-with-waiver on a `blocked_unverified` run — 3 `WaivedCheck` rows recorded, verdict UNCHANGED, undisclosed-check waiver refused | waiver-probe cycle + decision row | **green (PR #742 + probe 2026-08-06)** |
| A2 #683 | consumer change | prose fallback survives on a path | outcome-based wrap-up incl. fallback/replay paths | shk-6 3-workload green `cyc_cc2badb6a6ba`: closeout cites injected `verification_evidence` (17/17) as its confidence basis; ceiling path active | closeout_artifact.md | **green (PR #743 + shk-6)** |
| A2 #684 | stateful detection | counter/reset error | multi-cycle real-store sequence | inert populated (empty, honestly) on live red + green cycle outcomes; real-store sequence in unit suite | — | **green (PR #744 + shk-6)** |
| A3 #687 | evidence threading | traceback arrives unstructured | structured-evidence fixture; replay preserves category | shk-6 roll-4 red: both correction rounds carried structured analyses naming the exact defect | failure_analysis artifacts | **green (PR #739 + shk-6)** |
| A3 #431 | evidence classification | extraction loss enters repair | designed extraction-loss replay | no extraction loss occurred live (correct silence); category machinery unit-proven | — | **green (PR #740; live silence)** |
| A4 #435+lever | behavior change (ruling: progress-aware termination, 2026-08-04) | premature/false termination | designed-failure probe matrix + no-false-termination shakedown | BOTH-SIDED live: fired on roll-4's zero-progress chain (`term_-qa.test_01`); held fire on wp-roll-1's moving 3-round chain (none-candidate round suppressed) → honest exhaustion | termination artifact + 3 deltas | **green (PR #741 + shk-6)** |
| A6 #629 | enforcement expansion | prose side blocks without determinism | deterministic-side exhibit; prose side ships advisory | `contract_assertions_match` evaluated on live qa suites (passed — silent on non-contradicting suites); prose side advisory-only by construction | — | **green (PR #745 + shk-6)** |
| B1 #663 | structural | dropped context/seam | replay equivalence + both-seam tests | — | — | open |
| B2 #331 | structural | task identity drift | handler equivalence replay; stable task names | — | — | open |
| B3 #481 | recovery behavior | race / non-idempotence | seeded-state test + idempotent rerun + race case | — | — | open |
| C SIP-0101 slice | new maintainer-only tooling | invalid replay trusted as green | fail-closed on incomplete inputs; category-named evidence | Gate-1 demo `cyc_cfe6962e8fc8`: 5-task prefix restored from retained boundary 5, 33min vs ~2.5h, `CycleOutcome.replay` + CLI `⚠ REPLAYED` banner; retention live (cp 1,5,6,7 kept) | the replay cycle itself | **green (PRs #735–#737 + demo)** |
| D #506 | lifecycle timing (ruling: SIP-0087 defect, 2026-08-04) | tracker state drift | real Prefect adapter test or contract fixture | mid-cycle `task_runs/filter` showed the in-flight task RUNNING (the diagnosis query, now green) | — | **green (PR #746 + shk-6)** |
| D #724 | config resolution | override silently ignored | override-wins probe + regression | `framing_max_rerolls` + `workload_sequence` overrides honored live (auto-reroll fired; framing-only + implementation-only sequences ran) | — | **green (PR #748 + shk-6)** |
| F #452 | byte-preserving refactor | prompt drift | `render_hash` before/after equivalence | byte-equivalence pinned by test (8 hashes) | pinned hashes in test | **green (PR #747)** |
| F #583 | docs only | — | ADR merged | n/a | n/a | **green (PR #728)** |
| SIP-0096 promotion | status promotion | AC-mapping gaps surface late | promotion PR carries AC mapping; shakedown on promoted state | shakedown ran on the promoted deploy (969f6abf); AC#6 SKIP live disclosure = **owner-accepted surveillance** (2026-08-06): unit-proven; first natural pulse-skip occurrence is the live check | `SIP-0096-promotion-evidence.md` | **green (PR #749 + shk-6)** |
| Gate-2 exit shakedown | line verification | integrity core unbanked | green unscored cycle on promoted state | **GREEN 2026-08-06**: `cyc_ea0b82cfbd17` (accepted, 17/17, 0 corrections) + replay demo + 3-workload wrap-up green + waiver E2E; 2 honest work-product reds (machinery clean); findings filed forward: coarse `tests_pass` signature, bind+sole-author guaranteed rejection | green cycle = Gate 3's replay corpus | **GREEN — Gate 3 open** |

## Rollback seams

The one-PR-per-issue discipline keeps every behavior-changing item independently
revertible by image swap — that property is preserved deliberately: A1, A4, A6, #506,
and #707 must each be revertible without database rollback and without breaking
readability of artifacts they created (a `plan_defect` termination record or a
qa typed-check artifact written under the new code must remain interpretable to the
reverted version, or be additive-only). The #682 migration is the one non-image
rollback boundary: additive/nullable means old code runs against the migrated schema —
rollback is image swap there too, with the column simply unread. Mixed-version workers
during a rolling deploy follow the same rule: new fields ignored, never required.

## Cut gate

1. **Core-claim gate:** the release-defining set is complete — A1–A6, SIP-0096
   promoted (before the RC, per A2), B1–B3, C's minimum slice, #506, #724, #583,
   #452. Removal of any item from this set requires an **owner-ratified scope
   change**: written rationale, impact on the release claim, updated ROADMAP
   language, and confirmation the remainder is still a coherent 1.5.
2. **Capacity roll:** B4 / capacity Track D–E items / riders move to the 1.7 pool
   with a milestone update only (the stated exception to the named-trigger rule).
3. Full regression green; **both confirmation shakedowns green** — the Gate-2 exit
   shakedown (banked the integrity core, against the promoted state) and the cut
   shakedown on the fully integrated line (a red here is attributable to Gate 3's
   structural work by construction); designed-failure probes for behavior changes
   (A4's termination matrix, like #511's probe).
4. Feature-free verification (the behavioral checklist above) + contract v9 /
   manifest v4 hashes unchanged line-wide.
5. The evidence matrix complete for all release-defining rows.
6. Bump via `scripts/maintainer/version_cli.py`; version markers synced (CLAUDE.md,
   README, ROADMAP); ROADMAP timeline entry written at cut with the as-built record.

## Split triggers *(bias toward splitting scope when enabling assumptions fail)*

Any of these forces a scope decision at the next owner checkpoint rather than silent
accumulation:

- Track C's minimum slice cannot produce usable replay evidence in time to support
  B1/B2 → structural anchors fall back to regression + live validation (1.3.0-style)
  and the harness demotes to capacity, or the anchors move to 1.7.
- A4 turns out to require SIP-0092 schema/runtime changes beyond the bounded lever →
  A4 reduces to #435's signature-termination alone; the lever moves to the 1.6 M3
  decision.
- A6's prose-side cannot be made deterministic → ships advisory-only (already the
  default), blocking question to 1.6.
- SIP-0096 compatibility needs a second migration → design-review stop; the line does
  not silently grow migrations.
- B1 reveals context assembly cannot separate without changing handler contracts →
  stop; that is a 1.7 design item, not a 1.5 improvisation.
- More than one core item comes to require a new SIP or an accepted-design amendment
  → the line is carrying feature-shaped work; re-scope.

## Explicitly out (homes named)

| Item | Home |
|---|---|
| SIP-0102 steps 3–7 (in-cycle routing, clean-room verdicts, #306 retirement, golden-path validation) | 1.6 S-lane rider (ratified) |
| SIP-0092 M3 plan mutation | 1.6 decision, on the Gate-1 gate-evaluation doc |
| #557 post-retest governance review | SIP proposal once A3 lands (its trigger); proposal not cut-gating |
| #414 correction-budget reserve | trigger: a profile declares `required_checks` (watch during A2) |
| #598 packaging determinism (structural half) | Stack Blueprint / Generalized Build, 1.6 |
| #376 final-state verification | SIP-0102 step 4, 1.6 |
| #375 Phase-2 conformance | non-gating; revisit at 1.6 planning |
| Agent-comms delivery guarantees | 1.6 hardening rider (ratified) |
| #316 request-profile taxonomy | 1.8, with Campaign |
| Ollama→Atlas provider swap | post-1.5, over Track E's characterization suite |
| Workspace-revision implementation | defaults 1.6 unless the Gate-1 spike promotes a bounded 1.5 slice |

## Risk register

- **A4 changes SIP-0079 §7.7 termination behavior** — the exact class the quarantine
  exists for; decision table before code, typed termination record, designed-failure
  probe + shakedown before cut.
- **A1 makes qa checks load-bearing** — watch the `harness_boundary` exemption
  (ruling's caveat) and expect first-window noise from newly-real gates; the
  silent-on-clean shakedown is the false-red check.
- **B1 on the hottest file** — single-open-PR rule, two-seam invariant, typed-fragment
  composition boundary, replay equivalence.
- **A6 prose-side determinism** — default is advisory; blocking requires proof, never
  enthusiasm.
- **#576/#577 are wide and mechanical** — quiet windows, never overlapping.
- **#452 is only safe byte-identical** — `render_hash` equivalence is the acceptance
  test, not the diff.
- **Promotion-at-RC discovers gaps late** — mitigated by the promotion PR carrying the
  AC mapping (A2) and the audit already existing; if a gap surfaces, the promotion
  slips *with* the RC, never after it.
