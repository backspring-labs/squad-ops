---
title: Deterministic Verification Scaffolding with Semantic Fill Slots
status: implemented
author: jladd
created_at: '2026-08-13T00:00:00Z'
sip_number: 104
updated_at: '2026-10-04T17:56:52.584980Z'
---
# SIP-0104: Deterministic Verification Scaffolding with Semantic Fill Slots

## Status
Implemented: promoted at the v2.0.0 cut's SIP sweep (2026-10-04), by §13c's reading. Accepted at rev 3 (§10.4 Stage-1e baseline amended at Phase 0; rev 2 design-review feedback in PR #885).

**Targets:** acceptance decision in the open, against the 1e ledger through roll 17 — per the §10.4 amendment (2026-08-14); implementation in whatever feature window the owner assigns. The change is qa-surface-scoped and stack-opt-in (§8), so it can ride as an even-minor feature or land per-stack.
**Builds on:** SIP-0100 (scaffold ownership, fill slots, the frozen harness — this SIP is its test-side counterpart), SIP-0098 (verification contract; shells derive from the same manifest facts as the behavioral probes), #818 (criteria packs — the per-stack seam, including its asymmetric-default ruling), #877 (execution-model guidance — the experiment whose measured result motivates this), #866 (context completeness), #884 (the cross-role suite rewrite this SIP's frozen spine bounds).

## Delivery ledger (current as of 2026-10-27)

Kept by the rule in CLAUDE.md ("SIP System"): one row per part, updated in the PR that ships or re-places it, read at each release cut. Built from the read-only SIP-portfolio audit of 2026-10-04; `sips/PORTFOLIO.md` indexes it.

| part | status | where |
|---|---|---|
| P0: §10.4 amended; acceptance | **shipped** | 2026-08-14 (PR #893) |
| P1: scaffold emission, frozen/mutable contract | **shipped** | v1.6.0 (PR #894) |
| P2: executable artifact, validity gate | **shipped** | v1.6.0 (PR #895) |
| P3–P4: fill-mode `qa.test`, region enforcement, adversarial producers | **shipped** | v1.6.0 (`docs/plans/sip-0104-p6-window-record.md`: "fill protocol is 60 for 60") |
| P5: per-layer evidence counts | **shipped** | v1.6.x (`scaffold_evidence.py`, #951) |
| P6: the N=6 window (§10.2) and the §13a audit gate | **met** (§13c): ruled complete 2026-08-17; §10.2 read as met on 2026-10-04 | the window record l.100-118, 234 |
| §10.3 economics metric | *unverified* | — |
| stack #1 parity (#1122) | **dropped** (closed `not_planned` 2026-09-29, the owner's 1.9.0 ruling) | — |
| §4.3's "any role", re-read by SIP-0107 §46d item 4 (a dev edit to slot bodies is dropped) | **recorded** (§13c) | SIP-0107 §46d |
| a failing slot assertion routed by demonstrated defect ownership, its location only saying who wrote it (§13d) | **dropped** (§13e, 2026-10-22): the shell's construction already routes it, and 37 days of runs show no route it would change | — |
| §13d's ambiguous case, the guard: no revision resolving it by dropping the failing assertion's subject (§13f) | **shipped** | 2.5: §13f, PR #2746 |
| §13d's ambiguous case, the record: both readings beside the failure. §13f records the failing subject and what the declarations say of it, not the reading that the app is wrong | *unplaced* | — |

**What closes this SIP:** **Closed: promoted to implemented at the v2.0.0 cut's SIP sweep (2026-10-04),** by §13c's reading. Nothing remains placed. The §10.3 economics metric is unverified and is not a promotion criterion. §13d's routing (#2153) was a follow-on to an implemented SIP; §13e drops it. §13f builds §13d's guard against weakening (#2664). §13d's other ask, both readings recorded beside the failure, is unplaced, recorded so it does not read as shipped.

## 1. Abstract

**SquadOps should not spend LLM inference on deterministic test mechanics the framework can derive, verify, and freeze. The framework owns the proven mechanical spine; the agent owns the remaining semantic uncertainty. Proven semantic patterns can subsequently be extracted into deterministic verification primitives (§9).**

The qa suite is the last build artifact whose *mechanical* layer — imports, file placement, invocation form, response-envelope paths — is invented fresh by an LLM every roll. The v1.6 stack-#2 ledger (§3) shows that layer to be the dominant cause of run death, that guidance shrinks the invention space but does not close it, and that every deterministic verification layer added this release has been reliable while the authored mechanical layer failed a new way almost every roll. This SIP applies the release's proven pattern — *scaffold the interface deterministically; the LLM fills judgment only* (SIP-0100) — to verification: the walking-skeleton expander emits a deterministic test scaffold whose shells carry the invocation mechanics and contract-derived assertions pre-written and frozen, and `qa.test` becomes a fill task that supplies domain assertions only. This is a verification-integrity change, not a code-generation convenience: it converts `tests_pass` from a monolithic LLM-authored verdict into layered evidence with per-layer ownership (§5, §6).

## 2. The QA architecture invariant

> SquadOps deterministically materializes all QA mechanics that can be derived from authoritative project facts. The QA agent supplies semantic judgment that cannot be deterministically derived.

**The deterministic layer owns:** test files and placement; imports; harness lifecycle/reset; invocation mechanics; the required-minimum behavior inventory; contract-derived status assertions; dependency discipline; the execution strategy (in-process, serverless).

**The agent layer owns:** domain assertions; edge-case selection; state-transition and cross-operation semantics; assertions not represented in the contract; additional tests; PRD interpretation.

Future QA work extends this boundary; it does not renegotiate it per-roll.

## 3. Problem statement — the mechanical-failure ladder

Every entry is a run-terminating or round-burning failure of the suite's *mechanics*, not its judgment (all `group_run`, stack #2 unless noted):

- **Roll 9** (`cyc_a92eaa4f4052`): suite imports `supertest` — not in `package.json`; collection death.
- **Roll 13** (`cyc_732b773cf323`): suite calls `.get()` on a `Record` (a `Map` assumption about an invisible const shape — #875) and sides with a self-contradictory probe on status.
- **Roll 14** (`run_02cc78b7acbe`, original): live-`fetch` suite against `localhost:3000` — no server exists under `vitest run`; two rounds repaired the crash, not the strategy; run terminated (#877).
- **Roll 14 resume attempts** (post-#877, clean-workspace attempt): a zero-byte emission; a `../`-prefixed fence path; dynamic-route handlers invoked **without the `{ params }` context argument the supplement explicitly teaches**; the error envelope read at an invented path; a probable wrong-module import.
- **#884**: the repair-locus fallback let a dev-role repairer rewrite the suite with no qa guidance — reintroducing live-fetch verbatim. A frozen mechanical spine bounds this class structurally: slot-level repair cannot change invocation strategy (§4.3).

Two structural facts sharpen the cost:

1. **The mechanics tail persists through guidance.** #877 fixed the *strategy* — post-fix suites import handlers and invoke in-process — but the tail (`params` arg, envelope path, module choice) still killed the attempts. This repeats the #871 bounding lesson: `nextId`'s arity was shown and still misused. Teaching shrinks the invention space; only removing the authorship closes it.
2. **The runs these failures kill are otherwise green.** Roll 14's app passed 38/39 checks and, on the clean-workspace attempt, every contract probe over real HTTP. Each mechanical death burns a ~20-minute 27B generation round, and #435 rightly caps correction chains at two rounds. To be explicit about what this evidence does and does not show: it demonstrates that repeated mechanical *authorship* is net-negative; it says nothing against the semantic layer's value, which this SIP preserves and gives cleaner room to operate (§6).

## 4. Design

### 4.1 Scaffold emission

`expand()` for a participating stack additionally emits test-scaffold files, **once per run at seed time** (the #881 ruling: seeding is a run-start act; there is no mid-run regeneration, so fill preservation across regeneration does not arise within a run — across runs, fills are re-authored like all task output). Emission is deterministic: same manifest facts + same expanded tree + same generator version ⇒ **byte-identical output** (§4.4 pins this M0a-style). The scaffold's content hash is recorded in cycle evidence.

Each scaffold file contains **behavior slots** — one per contract-derived behavior (create → declared success status; blank rejection → the derived rejection status per #874's rule; not-found → declared 404 mapping; one per declared endpoint). A behavior slot is a deterministic unit of required coverage, **not necessarily one physical test function**: the generator may emit whatever test topology the behavior needs. Each slot carries a stable **`slot_id`** bound to the contract criterion / probe id it derives from — giving a durable mapping from scaffold → authored fill → failure evidence → correction target (the criterion-stamped-probe-row precedent, SIP-0098 §6.4).

**Derivability rule (normative):** every pre-written element — import path, invocation call, `{ params }` shape, status assertion — MUST be derivable from authoritative facts (manifest, expanded tree, criteria pack). An element the generator cannot derive is **demoted to fill content, never frozen as a guess**. This is #874's lesson stated as law: the scaffold must not relocate hallucination from the LLM into the generator.

### 4.2 The frozen/mutable contract (normative)

| Surface | Status |
|---|---|
| Scaffold file paths and placement | **Frozen** |
| Imports | **Frozen** |
| Harness lifecycle (`beforeEach(reset)`) | **Frozen** |
| Invocation calls (`new Request(...)`, `{ params }` form) | **Frozen** |
| Contract-derived status assertions | **Frozen** |
| Test structure outside slot bodies | **Frozen** |
| Slot bodies (domain assertions) | Mutable — the qa author's surface |
| Additive test files beside the scaffold | Permitted under §4.6 bounds |

Without this table, "fill mode" is not actually deterministic; with it, the boundary is checkable.

### 4.3 Enforcement

SIP-0100 §2.4 freezes whole files; this SIP introduces **region-level** freezing (mutable slots inside frozen files), which needs its own mechanism:

- The generator emits a **scaffold manifest**: the frozen file list, per-file **spine hashes computed with slot bodies elided**, and the slot table (`slot_id` → file, region, bound criterion).
- Verification recomputes spine hashes on every stored emission touching a scaffold file and **rejects any mutation of frozen regions before the suite executes** — the same restore-and-signal posture as 2.4, at region granularity. (Slot-elided hashing is the v1 mechanism; AST-level structural verification is the named escalation if hashing proves too coarse.)
- **Scaffold self-repair is prohibited** (the #884 clause): no repairer — qa, dev, or any locus fallback — may modify frozen regions. A scaffold mismatch surfaces as a structured scaffold defect routed to the scaffold/manifest owner (§7), never to an LLM repair round.

### 4.4 The scaffold validity gate

Rails before mechanism (the M0 pattern, applied a fourth time): before any qa authoring, the emitted scaffold must pass a deterministic self-check —

- every import resolves against the expanded tree; every referenced handler exists;
- every invocation signature is derivable (dynamic segments present, `{ params }` keys match the declared path parameters);
- every asserted status exists in the contract;
- the scaffold **with empty fills collects cleanly** under the stack's runner (the frozen-harness proof, extended to the whole scaffold);
- byte-equivalence: a standing test pins that the reference manifest + generator produce byte-identical scaffold output (the M0a guard shape).

A validity failure **fails run setup loudly** — per the #845 precedent, an unscaffolded verification story is not a degraded run, and it must never consume an LLM correction round.

### 4.5 `qa.test` in fill mode, with a semantic brief

When the workspace carries a valid scaffold, `qa.test` becomes a fill task: the author receives the scaffold and emits **slot fills only**. Alongside the slots, the envelope carries a **semantic brief** enumerating what the deterministic layer already covers (derived for free from the slot table), framing the author's job as *residual semantic coverage*: state effects, cross-operation semantics, edge cases, PRD-derived properties the contract cannot express. (A richer brief that proposes semantic *opportunities* requires inference to generate and is follow-on work, §12.)

Emission failure modes that killed whole attempts — zero-byte files, invented fence paths, wrong placement — become structurally impossible for the spine; a bad fill degrades one slot, not the suite.

### 4.6 Additive tests (bounded)

The author may add whole new test files beside the scaffold. Normative bounds: declared dependencies only (#448); the same in-process execution model — no live-server assumptions (#877's rule); no mutation of frozen scaffold files; subject to the same harness verification as today. Additive tests are the author's judgment surface, not an escape hatch around §4.2.

## 5. Failure taxonomy and ownership matrix

`tests_pass` evidence splits into four distinct classes — the distinction drives correction routing and prevents a deterministic defect from being attributed to the application:

| Failure | Class | Owner / route |
|---|---|---|
| Scaffold import unresolvable, invocation underivable, scaffold won't collect | **scaffold-invalid** | generator defect; fails run setup (§4.4), never an LLM round |
| Frozen shell executes; app violates the declared contract | **app-contract** | dev repair — and a shell status failure and its bound probe's failure are **the same defect observed twice**: the correction router deduplicates on the shared criterion id rather than burning a round on each |
| Authored slot assertion wrong or failing | **fill failure** | qa repair, slot-scoped. **Amended by §13d (2026-10-09):** a failing assertion's location says who wrote it, not what is wrong. It is routed by demonstrated defect ownership. **§13e (2026-10-22):** the frozen spine asserts the contract before the slot runs, so a failing slot assertion always has an app that met the contract, and qa is §13d's route for it |
| Harness/runtime cannot execute | **test-infrastructure** | environment triage, not a work-product round |
| Wrong import / invocation signature / status assertion in a *frozen* region | scaffold-generation defect (impossible unless enforcement failed — a §4.3 violation) |
| Live-server assumption or undeclared dependency in a fill or additive test | prohibited-fill violation — qa repair with the violation named |
| Zero-byte or unextractable emission | emission failure (#566 path), not a suite-execution failure |

## 6. The independence boundary, measured

The shells derive from the manifest — the same source as the app scaffold and the probes. The honest boundary claim: **the scaffold determines what gets mechanically exercised; the author determines which semantic properties beyond the declared contract get asserted.** Shell-level green is *consistency* evidence (implementation ↔ manifest); *intent* evidence (implementation ↔ PRD) lives in the fills and additive tests, which remain an independent PRD reading.

So the claim is falsifiable rather than qualitative, the run report tracks per layer: scaffold-derived behavior count and coverage; authored-fill assertion count; additive test count; failures detected only by fills; failures detected redundantly with probes. These counts are the evidence base for §9's promotion decisions and for evaluating whether the authored layer is earning its inference spend.

## 7. Source-of-truth precedence

- The **manifest / verification contract** defines expected behavior.
- The **expanded tree** defines available implementation surfaces.
- The **generator never reconciles disagreements by inference.** If the manifest declares an endpoint the tree lacks (or any authoritative facts disagree), scaffold generation fails as a **manifest/scaffold contract failure** — evidence-bearing, routed to the scaffold/manifest owner, never a best-effort scaffold and never an LLM repair target. (By construction the tree is `expand(manifest)`, so disagreement implies generator-version drift or a mutated workspace — the failure message names which.)

## 8. Stack scope, opt-in, migration

- **This SIP is deliberately stack-#2-scoped** in its concrete design (route handlers, `Request`, `{ params }`, HTTP statuses). The architectural pattern — *deterministic verification scaffolding with semantic fill slots* — generalizes (component-harness scaffolds, pytest-fixture scaffolds, queue-worker injection scaffolds), but generalizing from one instance produces generic-field-name contracts (the Stack Blueprint's own acceptance lesson); other stacks get designs when they get instances.
- **Opt-in is an explicit `ScaffoldStack` declaration and all-or-nothing.** A stack whose facts cannot support every §4.1 derivation **refuses** rather than emitting a partial scaffold — #818's asymmetric-default ruling applied: silently-wrong has no safe default. No cross-stack default changes; stack #1 is untouched until its pack opts in.
- **Migration:** opting in affects future cycles only. No historical or active workspace is regenerated (no cosmetic mutation of terminal state).

## 9. Promotion: semantic → deterministic (principle only)

Repeated, proven agent-authored patterns are candidates for extraction into the deterministic layer (scaffold shells or probes). The conservative rule is normative:

> Only promote behavior into the deterministic layer when its derivation can be **proven from authoritative facts**. Frequency of generation is never sufficient — promotion by observation alone would relocate probabilistic behavior into a nominally deterministic generator.

Promotion is evidence-driven (recurrence, stable semantics, deterministic derivability, no loss of independent coverage — measured via §6's counts). The promotion *workflow* and its lifecycle are follow-on work (§12); the learning loop this implies is the Cross-Cycle Memory SIP's territory meeting this one, and is deliberately not re-invented here.

## 10. Acceptance evidence and exit criteria

1. **Structural (every roll):** the §4.4 validity gate passes on every scaffold emission, and the byte-equivalence pin holds. Reference stack-#1 contract and manifest hashes unmoved (the M0a guard).
2. **Longitudinal:** **N = 6 consecutive stack-#2 rolls with zero run-terminating mechanical suite failures**, attribution per the §5 taxonomy in the run ledger. N is set *now*, matching the observed baseline window (4 mechanical deaths across ~6 rolls); the owner may adjust it at design review — before results exist, not after.
3. **Economics:** correction rounds and generation-minutes attributable to qa mechanics, before vs. after — the §3 cost claim (~20 min of 27B per mechanical round) captured as a metric, demonstrating the intervention removed the spend and not just the label.
4. **Stage 1e baseline (amended 2026-08-14 — owner ruling at Phase 0 of the implementation plan):** the baseline corpus is the **open** Stage 1e ledger through roll 17 — the roll-by-roll failure attributions §3 cites. As proposed, this item required a *closed* 1e ledger ("acceptance is a reading of a closed ledger, not a retrospective interpretation of a live one"). The owner amended it to accept in the open. Evidence: the trigger the owner named for acting — repeated mechanical suite deaths *despite* the execution-model guidance (#877) and the repair-locus fixes (#884) — has already fired within the recorded ledger; waiting for 1e to close adds rolls to the baseline without changing the attributions this SIP reads. The closed-ledger safeguard is retained in equivalent form as Gate 6's window protocol (implementation plan): any new mechanical failure mode observed after this baseline — before or after 1e closes — names its uncovered surface, joins the §5 matrix, and resets the N=6 window.
5. **Non-goals:** replacing the probes (they remain the boot-and-HTTP layer); capping authored tests; changing `tests_pass` credit semantics (SIP-0096 untouched).

## 11. Alternatives considered

- **More guidance** — tried three times, measured (#877): strategy converged, mechanics tail persisted. Rejected as the complete answer; guidance stays, governing the fills.
- **Correction loops absorb the tail** — each mechanical death burns a ~20-minute generation round, #435 caps chains at two, and #884 shows the repair path can make it worse. Rejected.
- **Probes only, no authored suite** — loses the independent PRD reader and domain-semantics coverage. Rejected; §6 measures the layer instead of deleting it.
- **Author the suite from the PRD with no manifest access** (maximal independence) — maximizes divergence detection but reintroduces every mechanical failure this SIP kills. Rejected for the spine; independence lives in the fills.

## 12. Follow-on work (named, not designed here)

- Semantic-brief enrichment (inference-generated coverage opportunities).
- The QA evidence schema formalizing §6's counts.
- The promotion workflow and lifecycle (EXPLORATORY → OBSERVED → CANDIDATE → DETERMINISTIC), integrated with the Cross-Cycle Memory SIP.
- Cross-stack scaffold designs, one per stack instance, under the §2 invariant.
- Cycle Data Store queries over §6 evidence (which semantic patterns find defects; which are redundant with probes; which mechanics still consume rounds).

## 13. Post-acceptance amendments

### 13a. A window roll must also pass the delivered-app audit (2026-08-15, from roll 3)

**What changed.** §10.2 defines the longitudinal criterion as *"N = 6 consecutive stack-#2
rolls with zero run-terminating mechanical suite failures"*. That remains the mechanical
claim, unchanged and applying to all six rolls. **Added:** from window roll 3 onward, a
roll counts only if the delivered app also passes `audit_delivered_app.py`, which now
includes the UI data-path check. Rolls 1–2 are grandfathered under the original criterion
alone — they were authored before the guidance defect below was fixed, so holding them to
a bar their inputs made unreachable would measure the fix, not the rolls.

**Evidence — why the mechanical criterion alone proved insufficient.** Window roll 1
(`cyc_04d36309d793`) satisfied every existing signal: verdict `accepted`, 36/36 checks
executed and passed, all five contract probes green, `tests_pass` on eight scaffold shells
that collected and executed cleanly, `frontend_build` green, **and the boot audit passing**
(*"installs, builds, boots, answers 5 contract probe(s)"*). Its UI was entirely
non-functional: all five page data calls requested unprefixed paths (`api('/runs')`)
against routes mounted at `/api/runs`, so list, create, detail, join and leave each failed
for every user. The defect was found by a human opening the app in a browser — no
automated layer detected it, because every layer exercises the API *directly* while none
followed the path the UI itself takes.

The root cause was a build-side defect, not a verification one: a single fill-only prompt
appendix served both stacks, so a `nextjs_ts` author was instructed to fill
`backend/routes.py` and `frontend/src/views/*.jsx` — neither of which exists on this stack
— and told that the client seam *"prefixes `/api`"*, which is stack #1's helper. It
followed its instructions exactly. Fixed by per-stack guidance (#902); the detection gap
closed by the UI data-path check (#903).

**Why this does not weaken §10.2.** The two criteria are independent and both are
recorded per roll. The mechanical claim — the one this SIP exists to prove — still spans
all six rolls. The audit criterion is an additional gate from roll 3, so the final
evidence must be stated as it is, never collapsed: *six rolls with zero mechanical suite
failures; rolls 3–6 additionally audited as working applications.* Reading "six clean
rolls" as "six working apps" would be exactly the false-green this amendment exists to
prevent.

**Ruled by the owner, 2026-08-15**, on the reasoning that banking six mechanically-clean
rolls whose deliverables nobody can use would undercut what the window is meant to
demonstrate.

### 13b. The final claim is stated by rule, not by roll number (2026-08-15)

**What changed.** §13a's closing sentence gives the required form of the final evidence as
*"six rolls with zero mechanical suite failures; rolls 3–6 additionally audited as working
applications."* The **rule** it derives from — stated correctly two paragraphs above, and
unchanged here — is *from window roll 3 onward, a roll counts only if the delivered app
also passes the audit*. The phrase "rolls 3–6" was arithmetic on the assumption that rolls
2 through 6 would each count. They did not.

**Evidence.** Of the first four rolls: roll 1 banked clean; roll 2 (`cyc_62ce2fd83bca`) was
terminated by a correction-signature defect and did not count; roll 3
(`cyc_b20f58cc7cbc`) exhausted its correction budget and did not count; roll 4
(`cyc_92c44f8704ab`) was system-rejected at the framing gate without ever reaching qa, so
under the window protocol it neither counts nor resets. The window's sixth counting roll is
therefore not the sixth roll launched, and any fixed numbering in the claim will keep
drifting as rolls are lost.

**The correction.** The final evidence is stated as: *six counting rolls with zero
mechanical suite failures; every counting roll from roll 3 onward additionally audited as a
working application.* Nothing about the criterion changes — §10.2's mechanical claim still
spans all six counting rolls, the audit gate still begins at roll 3, and the two are still
recorded separately and never collapsed. What changes is that the claim no longer names
roll numbers it cannot guarantee.

**Recorded rather than edited in place**, because §13a's sentence is the wording the
acceptance evidence will be quoted from, and a silent correction to a quotable claim is
indistinguishable from the claim having always said this. The 1.6 plan and the
implementation plan were updated to match.

### 13c. Shipped in v1.6.0; the window met §10.2; stack #1 parity dropped; §4.3 re-read (2026-10-04)

**What changed.** This SIP never recorded that it shipped. It does now.
- **Shipped in v1.6.0:** P1 (PR #894) and P2 (PR #895), P3–P4 (the fill-mode `qa.test`, region enforcement, adversarial producers) and P5's per-layer evidence counts (`scaffold_evidence.py`, #951).
- **The P6 window met §10.2.** It was ruled complete on 2026-08-17 (`docs/plans/sip-0104-p6-window-record.md:234`). Rolls 1–5 were accepted. Roll 6 was rejected on a working app, by a fill literal and the repair path, not by the suite mechanics this SIP specifies (the window record, l.100-118). **§10.2 is read as met for the scaffold's mechanics.**
- **Stack #1 parity (#1122) is dropped.** It was closed `not_planned` on 2026-09-29, by the owner's 1.9.0 ruling: React qa repairs are already scoped without fill slots. This SIP's §8 scope was stack #2 by design.
- **§4.3's "any role" is re-read by SIP-0107 §46d item 4:** a dev edit to slot bodies is dropped. The rule change lived only in SIP-0107.
- **The §10.3 economics metric** (before/after round-minutes) has no record found. It is not a promotion criterion.

**Evidence.** The window record; #1122; SIP-0107 §46d; the read-only SIP-portfolio audit of 2026-10-04.

**Who ruled it.** the owner's rulings of 2026-10-04 on the SIP-portfolio audit (`sips/PORTFOLIO.md`): "yes, move them to 3.x including capability-backed agents. I accept all your other recommendations to keep SIPs current, reflecting what gets delivered, and where the work is targeted". The reading of §10.2 is the owner's.

### 13d. A failing slot assertion's location says who wrote it, not what is wrong (2026-10-09)

**What changed.** §5's row "Authored slot assertion wrong or failing → fill failure → qa repair" reads as if an
assertion's location inside a slot settled which side is wrong. It doesn't: the location identifies who **wrote** the
assertion (the qa fill). Whether the assertion or the application is wrong is a separate question, and the answer
decides the route.

**The intended policy: route by demonstrated defect ownership.** For a failing assertion inside a slot:
- **A correct assertion, and a broken application.** The assertion's expected value traces to the manifest, its
  bound contract or the criterion it fills, and the application's answer contradicts it. **Route to dev repair, and the
  assertion is preserved:** it encodes a legitimate requirement, and no repair may weaken it.
- **A wrong assertion, and a correct application.** The assertion's expected value contradicts the manifest, the
  contract or the criterion, or it tests behaviour nothing declares, and the application's answer meets the
  declaration. **Route to qa repair, slot-scoped,** and the repair keeps every legitimate requirement the slot carries.
- **Ambiguous.** Neither side can be shown wrong from the declarations, or both can. **No automatic reroute:** the case
  keeps today's route, with both readings recorded beside the failure, and a repair is never allowed to resolve it by
  deleting or weakening the assertion.

**What does not change now.**
- **The routing code stays as it is through SIP-0110's measurement window** (#2153). Today's vitest classifier cannot
  place a slot assertion at all (`scaffold_evidence.py` reads the declaration line, which vitest does not report), so
  every vitest slot failure is routed as `app-contract`, to dev. That matches the first case's route, and changing it
  mid-window would move a measured input.
- **Building the route by demonstrated ownership,** with the evidence each case needs recorded on the failure, is
  #2153's. It is unplaced, and is placed after the window.

**Evidence.**
- #2153: the classifier places a vitest assertion by `row["line"]`, which is `None` for vitest's JSON report without
  `includeTaskLocation`, so `in_slot` is always `None`.
- **#2152 supports caution.** A dev route-fill error was classed as the fill's, and the repair re-filled correct tests.
  It is a neighbouring incident, about an error raised under the spine's own call, and not an instance of #2153's
  assertion branch. It shows the cost of rewriting correct tests after an application failure.

**Who ruled it.** The owner's review of the 2.2 shakeout (2026-10-09, point 8): "Assertion location identifies who wrote
the assertion, not whether the assertion or the application is wrong … Route based on demonstrated defect ownership,
and preserve legitimate requirements during test repairs. Amend the location-implies-QA design wording."

### 13e. §13d's routing is met by the shell's construction; its build is dropped, and its ambiguous-case guard is unplaced (2026-10-22)

**What §13d said.** Today's vitest classifier can't place a slot assertion, because it reads the declaration line, which
vitest doesn't report. So every vitest slot failure routes as `app-contract`, to dev. Routing by demonstrated defect
ownership was to be #2153's build, placed in 2.4 by the plan's D8.

**What the evidence says.** This is #2153's read of every qa run's stored report from 2026-09-15 to 10-22: the vault's
`test_report.md` files, the merged shells, the scaffold manifests, and the probe and routing lines in the runtime's log.
- **Only the Next.js stack emits shells** (`src/squadops/stacks/verification_scaffold_emission.py:77`).
  - It pins vitest 1.6.0 (`stack_nextjs_ts.py`), and its report places a failure at the line that failed. The 2.4
    window's `cyc_83412d24d2ba` recorded its ten in-slot failures as `fill`, as did four August cycles. All 21 stored
    observation lines equal the first frame in their report.
  - #2153's fixture came from the React stack, which emits no shells.
  - So §13d's "every vitest slot failure is routed to dev" described no stored run. An in-slot failure has routed to qa.
- **The frozen spine asserts the contract before the slot runs** (`stack_nextjs_ts_tests.py`, the shell body): the
  declared status, the error code, the response shape and the declared order.
  - An application that breaks the contract therefore fails the spine, routes to dev, and its slot never runs. That is
    §13d's first case (a correct assertion, a broken application), met by construction.
  - In the 37 days, 22 shell assertions failed in the spine. Each one's own probe failed, and each routed to dev.
- **An in-slot failure always has an application that met the contract** for that request.
  - In the 37 days, 19 failed in a slot: 9 assertions qa wrote, and 10 missing-fill placeholders. Each one's own probe
    passed, and each was classed `fill`.
  - That is §13d's second case (a wrong assertion, which goes to qa) or its ambiguous one (today's route, qa).
  - Routing by demonstrated ownership would have changed no route.

**What changes.** The routing build is dropped. #2153 closes with this amendment. §5's table reads as §13d and this section
amend it.

**What stays unbuilt.** §13d's ambiguous case asks for two things:
- both readings recorded beside the failure;
- a repair never allowed to resolve the failure by deleting or weakening the assertion.

Neither is built. `measure_assertion_strength` (#980) records how much the fills assert; it refuses nothing. Every in-slot
failure is the second or the ambiguous case, so this guard is the one place §13d still acts. It is #2664, **unplaced**.
Whether any of the 9 qa-written failures was repaired by weakening isn't read yet; the slot bodies before and after are
in the vault.

**Who ruled it.** The supervisor, 2026-10-22, under the owner's grant of 2026-10-19 ("autonomy to use good judgement to
approve cycles, PRs, issue choices etc." on the 2.4 feature set). D8 placed the build. This drops it on the evidence above,
and it is reported to the owner, whose ruling can restore it.

### 13f. A slot revision that drops its failing assertion's subject is refused (2026-10-27)

**What changed.** §13d says a repair "is never allowed to resolve [an ambiguous failure] by deleting or weakening the
assertion". §13e found that guard unbuilt, and every in-slot failure is §13d's second or ambiguous case, so the guard is
where §13d still acts. It is built now, as a gate on the slot-region revision (#2664).

**The rule.** When a slot with an open failure is revised, the revision keeps an assertion on the failing assertion's
*subject*: the same field on the same surface, which is the response, the frozen error envelope, or a store table.
Any matcher counts. A revision that keeps none is refused as `slot_subject_dropped`, unless the scaffold's
declarations show that field absent on that surface. Counting assertions was rejected: #2664's read found the weakening
kept or raised its count, while the correct reductions lowered theirs.

**What is built: the MacBook lane's five points.**
1. **The subject** is read from the merged slot body at the failure's line. That is the line `classify_shell_failures`
   already records on each fill observation.
   - Each stack registers a reader for its fill language (`verification_scaffold_emission.slot_assertion_reader`). The
     TypeScript one is `stacks/stack_nextjs_ts_subjects.py`.
   - It maps `body.<f>` to the response, `body.error.<f>` to the error envelope, and `TABLES.<T>` or
     `all(TABLES.<T>)[i].<f>` to store table `T`.
   - Before mapping, it normalises optional chaining, casts, quoted bracket access, `typeof`, `Array.isArray` and the
     body's own aliases (`const rows = all(TABLES.Run)`). The repair this section exists for wrote through such an
     alias.
   - Any other target reads `subject_unreadable`. That is recorded and never refused, and so is a revision whose only
     assertion naming the field cannot be read.
2. **The gate sits in `merge_fills`.** Every write to a slot body is one of its region revisions, and
   `apply_followup_fills` folds into it. For each slot with an open failure, it compares the new body with the body
   that failure was observed on. That covers three paths:
   - the slot-scoped `qa.test_repair`: `_merge_repair_fills` is handed `repair_slots`, now carrying each failure's
     line, and `current_files`;
   - a re-dispatched `qa.test`: the executor carries `prior_slot_failures` onto the re-dispatch, and the qa handler
     builds the same guard;
   - a repair sent for another file that refills every slot: the guard holds every open in-slot failure, not only the
     slots the repair was aimed at.
   A not-applicable disposition on a failing slot asserts nothing, so it is judged like a drop.
3. **The same surface and field, with any matcher, passes.** Two softer signals are recorded and refuse nothing:
   - `matcher_loosened`: the subject is kept only by existence or shape matchers, where the failing assertion pinned a
     value;
   - `lost_subjects`: passing checks the revision dropped beside the failing one.
4. **A refused repair is spent, not refunded**, as #2727 does for a dropped patch.
   - The qa repair handler hands back nothing, and stamps `slot_subject_dropped` on its outputs.
   - `CorrectionRepair` collects the stamp, and `judge_emission` no longer reads the round as empty.
   - The protocol result and the `CORRECTION_COMPLETED` event carry `repair_subject_dropped`.
   - The executor routes the round to `continue` without reaching patch acceptance. Its carry entry, under
     `REPAIR_SUBJECT_DROPPED_MARKER`, names each slot, the subject, and that the declarations show the field there.
   - `repair_not_applied_in_round` reads the marker, so the signature rule doesn't count the round as a repeat.
   - **On a re-dispatched qa.test** there is no patch to spend. The refused slot keeps its accepted body, the rest of
     the emission merges, and the next correction round's carry is told which subject that emission tried to drop.
5. **"Absent there" is read from the scaffold record the task is bound to**, never from the app's code. The source is
   `verification_scaffold.subject_surfaces`, derived from the interface manifest beside `store_tables`:
   - a 2xx shell's response: its entity's declared fields. A collection body declares none;
   - an error shell's response: the frozen envelope, whose only key is `error`, holding `code` and `message`
     (the stack's `ErrorSeam`);
   - each store table: its entity's declared fields.
   - A product with no scaffold has no slots, so nothing changes off the scaffold stacks.

**The registry.** `slot_subject_dropped` is a new `FailureClassification` value, set by the framework, as
`contract_compliance` is. It is declared under `work_product`'s disposition (`producer_output_failure`,
primary-eligible), and the drift test enumerates it. **`ATTRIBUTION_REGISTRY_VERSION` stays 2.** A new value in an
existing vocabulary, declared under an existing disposition, changes no attribution of an existing record. Nor does any
composition rule read `FailureClassification`.

**Evidence: the read before merging.** A read-only replay ran the real gate over the 9 in-slot qa-written failures of
2026-09-15 to 10-22, from the vault's stored shells. A repair revision went through the handler's own merge; a
re-dispatched qa.test's went through `merge_fills` with the guard its handler builds. Each run's stored interface
manifest hashes to its scaffold record's `interface_manifest_hash`, and today's generator reproduces every stored
spine, so the declarations are the ones each run bound.

| # | run, report | failing shell : line, subject | next revision | verdict |
|---|---|---|---|---|
| 1 | `cyc_bb493eb4725b`/`run_642c6086b601`, `art_a3cbfdc754aa` | join `art_1145586f92bf`:44, `participant_count` on store `RunDetail` | the qa repair `art_a05e5962383f`; then the re-dispatch `art_6a558b8bc5ec` | the repair **refused**; the re-dispatch kept the subject |
| 2 | same | join-duplicate `art_3fd5f7eb329c`:44, the same subject | the repair `art_2f83e019d088`; the re-dispatch `art_bdf66cf55b3b` | **refused**; kept |
| 3 | same | leave `art_b19dbf0a0051`:52, the same subject | the repair `art_76feb064177b`; the re-dispatch `art_97105dd0ae52` | **refused**; kept |
| 4–6 | same, `art_c01cc97cda51` | the re-dispatch's join :48, join-duplicate :45 and leave :55, the same subject | none: the run ended `correction_terminated_plan_defect` | nothing to gate |
| 7 | `cyc_b6a4ba977d5e`/`run_f75fd232235d`, `art_cb97ab842e38` | join-duplicate `art_7e5cc1371562`:43, `participants` on the response of a 409 | the re-dispatch `art_573e226b8998`, which moved the check to the store row and added `body.error` checks | passes: `absent_there` (the frozen envelope) |
| 8 | same, `art_490610fa0037`: the retest after a dev repair that revised no slot | the same shell and line | the same re-dispatch | passes: `absent_there` |
| 9 | `cyc_311e2117c21d`/`run_bffc5ecf5b6d`, `art_50efe3cc7568` | `vc-probe-api-runs` `art_e4438d18dc68`:38, `participants` on store `Run` | the re-dispatch `art_bda2682d33ac`, nine expectations down to four | passes: `absent_there` (`Run` declares no `participants`) |

- **So the weakening in `cyc_bb493eb4725b` is refused** on all three slots.
- **The strengthening (7) and both correct reductions pass:** `cyc_b6a4ba977d5e`'s, on the frozen envelope, and
  `cyc_311e2117c21d`'s, on an undeclared entity field.
- **The softer signal** records, on slots 1 and 3, the passing `participant_count` on the response that the repair
  dropped beside the failing check, as #2664's read found.
- **Case 9 has a caveat.** Its failing shell was a qa repair's candidate whose retest failed, so it was never accepted.
  Live, the re-dispatch is gated against the accepted shell (`art_b267e7b4dd0f`), whose report (`art_c518a5ba975c`) has
  no in-slot failure. So the gate has nothing to judge there, and the drop passes either way.

**What is not built.** §13d also asks for "both readings recorded beside the failure". The gate records the failing
subject and what the declarations say of it. That is the assertion-side reading's evidence, but not the reading that
the app is wrong. It stays unplaced; the ledger row says so.

**What the gate does not see, by design or for now:**
- **A matcher loosened on the same subject passes.** That is G4 point 3's blind spot, kept as placed. It is recorded
  (`matcher_loosened`), not refused.
- **A target the reader cannot place is never refused.** Examples are `all(TABLES.T).find(…)?.f` and a helper call.
  When the revision's only assertion naming the field is such a target, the verdict is `subject_unreadable`. So the
  gate refuses less than §13d forbids, never more.
- **One reader exists: TypeScript.** Next.js is the only stack that emits shells today. A test requires every
  shell-emitting stack to register a reader and its declarations, so a new one cannot ship with the gate silently off.

**Who ruled.**
- **The design:** the MacBook lane's G4 of 2026-10-24 on #2664, approved with the five points above.
- **The placement:** the owner, 2026-10-23, in 2.5 ("1 yes, 2 keep, 3–5 yes, 6 delegate"; this was the fourth).
- **The build:** the supervisor (Spark lane).
- **The registry version:** the supervisor, as the registry's owner, which G4 point 4 left to it: no bump.
