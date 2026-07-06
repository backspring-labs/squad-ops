---
title: Verification Evidence Integrity
status: proposed
author: jladd
created_at: '2026-07-05T00:00:00Z'
---
# SIP: Verification Evidence Integrity

## Status
Proposed

**Targets:** v1.4 (feature minor — headline feature SIP candidate, alongside SIP-0091)
**Motivated by:** the 2026-07-04 health assessment finding that orchestration maturity is outrunning evidence quality: the framework cannot yet distinguish "this check passed" from "this check never ran." The 2.0 self-improvement arc (Campaign → Test Bay → capability promotion) automates decisions over cycle evidence; this SIP is what makes that evidence worth deciding on.
**Builds on:** SIP-0070 (pulse checks / verification framework, `PulseVerificationRecord`), SIP-0092 (typed acceptance — the check *types*; this SIP owns the trust semantics of their *results*), SIP-0079 (outcome classes, failure classification), SIP-0086 (output validation / build convergence), SIP-0095 (deterministic-gate + doctor-parity precedent), SIP-0077 (cycle event system), SIP-0064 (Cycle/Run/Gate).
**Proof cases (existing bugs this SIP prevents as a class):** #276 (generated tests stub-fallback on ImportError → acceptance passes on an app that never ran), #306 (agent image lacks Node.js → frontend build + vitest checks are permanently inert), #296 (`source_filter` excludes package.json/configs → buildable frontend never materializes, checks skip), #291 (`build_profile.required_files` declared but unenforced at run completion).

---

## 1. Summary

Introduce a single, framework-wide **integrity invariant** for every acceptance and verification signal:

> Every check result is exactly one of **executed-and-passed**, **executed-and-failed**, or **not-executed** (with a machine-readable reason) — and **a not-executed result never aggregates as a pass**. A run whose *required* checks include any not-executed result cannot report acceptance.

SquadOps already has most of the vocabulary: `CheckOutcome.status ∈ {passed, failed, skipped, error}` with documented RC-9a/RC-12 semantics (`src/squadops/cycles/acceptance_checks.py:40`), a `tests_not_executed` detail in the QA path, and `not_executed` handling in the test runner's timeout path. What it does not have is the **enforcement**: skipped/error/inert results flow into acceptance aggregation without blocking it, and nothing detects a check that has *never* executed across many cycles. Every proof-case bug above is the same defect — a verification signal silently degraded to "no signal" and the framework counted the silence as success.

This SIP adds exactly three things: (1) the **aggregation rule** enforced at a single choke point, (2) **execution provenance** on every check result, and (3) **inert-check detection** across cycles. It defines the `CycleOutcome` evidence contract that the Campaign continuation policy (1.6) will consume — certifying the ground truth before the framework automates decisions over it.

---

## 2. Motivation / Problem

The 1.x arc built substantial verification *machinery*: typed acceptance checks (SIP-0092), pulse checks and verification records (SIP-0070), output validation (SIP-0086), correction protocols keyed on failure classes (SIP-0079). But the machinery has a systemic soft spot: **when a check cannot run, the failure mode is silence, and silence reads as green.**

Concretely, today:

- A generated test suite that fails to import falls back to a stub — and *passes* (#276). This is worse than a skip: it is a fabricated positive.
- The frontend build check and vitest have never executed on the deployed agent image (no Node.js) — every cycle since has "passed" them by permanent skip (#306), and the source filter guarantees there is never a frontend to check anyway (#296).
- `required_files` is a declared contract with no enforcement point (#291).

Each was filed as an individual bug, but the class keeps reappearing (#187 called its instance "the 3rd whack-a-mole failure") because no rule makes the class impossible. Meanwhile the roadmap is about to raise the stakes: the Campaign SIP's continuation decision (§7.2) and the entire self-improvement direction *act automatically* on this evidence. `stop_success` "must point to verification evidence" — which is only a safeguard if verification evidence cannot be a stub, a skip, or an inert check. Scorecards, Test Bay promotion gates, and nightly improvement Campaigns all inherit the same dependency.

This is the codebase's existing hard rule — *no fallbacks that mask a missing data source* — applied to verification itself.

---

## 3. Decision

1. Adopt the **integrity invariant** (§6) as a framework-wide rule over all acceptance/verification surfaces (§8), enforced at a single aggregation choke point per run — following the established pure-decision-at-a-choke-point pattern (SIP-0089 reserve-buffer guard, SIP-0095 preflight, Campaign continuation).
2. Extend the existing result vocabulary, not replace it: `CheckOutcome`'s four states remain; the invariant formalizes `skipped`/`error` (and runner-level `not_executed`) as the **not-executed family**, adds required **execution provenance** (§7), and defines how the family aggregates (never as pass; blocking when the check is required).
3. Add **inert-check detection**: a required or declared check that reports not-executed for N consecutive cycles is surfaced via doctor, the console, and a cycle event — because a permanently skipping check is indistinguishable from no check at all.
4. Define the **run/cycle evidence roll-up** (`CycleOutcome` contract, §10) — the durable, honest summary of what was verified, what failed, and what was never checked — as the input contract for wrap-up (SIP-0080), gates, and later the Campaign continuation decision.

---

## 4. Scope

- **In:** the integrity invariant and its aggregation choke point; execution-provenance fields on check results; conformance of the five existing verification surfaces (§8); the required-vs-optional check distinction in profiles; inert-check detection + doctor/console surfacing; the `CycleOutcome` evidence roll-up; SIP-0077 events for not-executed and inert findings; retrofit of the four proof-case paths as conformance proof.
- **In (reuse, not rebuild):** `CheckOutcome` and the typed-check registry (SIP-0092), `PulseVerificationRecord` persistence (SIP-0070), outcome classes (SIP-0079), gate/HITL mechanics (SIP-0064).
- **Applies to:** typed acceptance checks, generated-test execution, build-profile checks, required-files enforcement, and pulse-check verification — anything whose result can gate acceptance or feed a continuation/wrap-up decision.

---

## 5. Non-Goals

- **No new check types.** Check semantics belong to SIP-0092; this SIP governs the trust semantics of results, whatever the check.
- **No scorecard.** The Cycle Evaluation Scorecard (proposed) *measures* quality; it sequences after this SIP so its inputs cannot be fabricated. Nothing here scores anything.
- **No Test Bay / capability promotion.** 2.0 consumers of trustworthy evidence, not part of producing it.
- **No Campaign mechanics.** This SIP defines the evidence contract Campaign reads; the continuation policy stays in the Campaign SIP.
- **No third evidence vocabulary.** The implementation must extend `CheckOutcome` + `PulseVerificationRecord` + SIP-0079 outcome classes after a reconciliation audit (Phase 0), never introduce a parallel model. (The 2.0 umbrella SIPs' overlapping-vocabulary problem is the cautionary tale.)
- **No blanket "everything is required."** Profiles legitimately run degraded on small local models (`smoke`/`lite`); the invariant forces *honesty* about what didn't run, not maximal strictness. Which checks are required is profile policy (§6.3).

---

## 6. The Integrity Invariant

### 6.1 Result states

Every verification signal resolves to exactly one of:

| Family | States (existing vocabulary) | Meaning |
|---|---|---|
| **executed-and-passed** | `passed` | The check ran against the real subject and met its criterion. |
| **executed-and-failed** | `failed` | The check ran and the criterion was not met (RC-9a: app gap). |
| **not-executed** | `skipped`, `error`, `not_executed` | The check did not evaluate the real subject — intentional skip, evaluator failure (RC-12), missing tooling, missing subject, timeout, or stub substitution. Carries a machine-readable `reason`. |

**Hard rule:** substituting a stand-in subject (a stub module, a placeholder file, an empty suite) and reporting `passed` is an integrity violation, not a fallback. The #276 stub path must report `not_executed(reason="import_error")`, never pass.

### 6.2 Aggregation rule (the choke point)

A pure function, evaluated once per run at the acceptance boundary:

```
aggregate_verification(results, required_check_ids) -> RunVerificationSummary
```

- not-executed **never** counts toward pass totals, thresholds, or "all checks green."
- If any **required** check is in the not-executed family → the run's acceptance verdict is `blocked_unverified` (a distinct verdict — neither passed nor failed; the correction protocol and gates can route on it).
- **Optional** checks in the not-executed family never block, but are always disclosed in the roll-up (§10) — silence is still forbidden; it is just non-blocking.
- No side effects in the function; enforcement only at the boundary that acts on the summary. An architecture test asserts purity (Campaign-SIP AC#7 precedent).

### 6.3 Required vs optional is declared, not inferred

Cycle request profiles / build profiles declare which checks are required (extending the existing profile schema in the SIP-0092 style). Defaults are conservative per profile tier: `smoke` may mark most checks optional (honest disclosure, no blocking); `full` marks the build/test spine required. Preflight (SIP-0095) gains a parity check: if a *required* check's tooling is knowably absent at create time (e.g. no Node.js for a required frontend build — #306), that is a create-time warn or 422, not a mid-run surprise.

---

## 7. Execution Provenance

Every check result carries evidence that it actually ran (extending `CheckOutcome.actual` / `PulseVerificationRecord`, exact fields reconciled in Phase 0):

`executed_at`, `duration_ms`, `subject_ref` (what was checked — file set hash, artifact ID, endpoint), `executor_ref` (where — container/image), and for command-backed checks `exit_code` + a bounded output digest. For the not-executed family, `reason` is mandatory and machine-readable (`missing_tooling:node`, `import_error`, `timeout`, `subject_missing`, `filtered_out`).

Provenance is what makes an audit ("did this ever run?") answerable from records instead of log archaeology — and it is the raw material for #114's typed-check evaluation surfacing.

---

## 8. Surfaces That Must Conform

| Surface | Today | Conformance change |
|---|---|---|
| Typed acceptance checks (`cycles/acceptance_checks.py`, SIP-0092) | 4-state `CheckOutcome`, semantics documented, aggregation permissive | provenance fields; results flow through §6.2 |
| Generated-test runner (`capabilities/handlers/test_runner.py`) | timeout path already yields not-executed; **ImportError path stubs and passes (#276)** | stub fallback removed → `not_executed(import_error)`; provenance (exit code, duration) |
| Build checks (frontend build, vitest — #306/#296) | permanently skip; skip does not block | report `not_executed(missing_tooling / subject_missing)`; required-in-profile ⇒ blocking; preflight parity |
| `required_files` (#291) | declared, unenforced | becomes a required typed check evaluated at run completion through the same choke point |
| Pulse checks (SIP-0070, `PulseVerificationRecord`) | records persist; executed-vs-skipped distinction not enforced in roll-ups | records carry the state family + provenance; wrap-up consumes the honest roll-up |

---

## 9. Inert-Check Detection

A check (by stable check ID) that reports not-executed for **N consecutive cycles** in the same project/profile (default N=3) is an **inert check** — operationally equivalent to no check, and historically how #306 stayed invisible.

- `squadops doctor` gains an inert-check report (deployed-image parity: which declared checks *cannot* execute here — the #306 class detectable before any cycle runs).
- The console cycle/run views badge not-executed and inert results distinctly from passes (never folded into a green count).
- A cycle event (`verification.check_inert`, taxonomy addition per SIP-0077's drift-parity tests) fires on detection.

---

## 10. The `CycleOutcome` Evidence Roll-Up

The durable per-cycle summary — the contract downstream consumers read:

`verified` (executed-and-passed, with provenance refs) / `failed` (executed-and-failed) / `unverified` (not-executed, with reasons) / `inert` (chronic) / `verdict` (`accepted | rejected | blocked_unverified`) — all as references into the SIP-0070/0092 records, not copies.

Consumers, in order of arrival: **wrap-up** (SIP-0080 confidence classification gets an honest basis — "partial completion with honest confidence" becomes computable), **operator gates** (a gate presented with `blocked_unverified` sees *why*), and — the strategic one — the **Campaign continuation decision** (1.6), whose §7.2 "no `stop_success` on agent narrative alone" is only as strong as this contract. This SIP deliberately ships one even-minor ahead of Campaign so the contract exists, live-validated, before anything automates over it.

---

## 11. Phasing (within the 1.4 arc)

- **Phase 0 — Reconciliation audit (docs-only, can run during 1.3).** Read the accepted SIP-0092 spec + SIP-0070/0079 models against §6–§7; produce the field-level mapping (what extends `CheckOutcome`, what extends `PulseVerificationRecord`, where SIP-0079 outcome classes meet the not-executed family). Gate: no third vocabulary.
- **Phase 1 — Invariant + provenance.** The pure aggregation function + `blocked_unverified` verdict + provenance fields + required/optional profile schema. Choke point wired at the run acceptance boundary. (Behavior change only where a required check already reports skip/error — knowingly none in default profiles until Phase 2 retrofits.)
- **Phase 2 — Retrofit the proof cases.** #276 stub removal, #306/#296 honest reporting + preflight parity, #291 required-files check. Each lands with a live `lite` cycle demonstrating the honest result (per the live-validation rule). **This phase will turn silently-green paths honestly red — that is the point; profile required-lists are the throttle.**
- **Phase 3 — Detection + surfaces.** Inert-check detection, doctor report, console badging, `verification.check_inert` event, `CycleOutcome` roll-up consumed by wrap-up.

Acceptance of the SIP is all phases (SIP-0089/0090 precedent). The proof-case *bugs* remain independently fixable as patches at any time; this SIP is the rule that keeps them fixed.

---

## 12. Acceptance Criteria

1. A check result in the not-executed family can never contribute to a pass count, threshold, or acceptance verdict — property-tested at the aggregation function.
2. A run with any required check not-executed yields `blocked_unverified`, never `accepted`; the verdict is distinct from `rejected` and routable by gates/correction.
3. The #276 path: an ImportError in generated tests produces `not_executed(import_error)` and (where tests are required) `blocked_unverified` — demonstrated by the previously-stubbed fixture.
4. The #306/#296 paths: on an image without Node.js, frontend checks report `not_executed(missing_tooling:node)`; doctor reports them as inert-capable before any cycle; a profile marking them required fails preflight (SIP-0095 parity).
5. `required_files` (#291) is enforced at run completion through the same choke point.
6. Every executed check result carries provenance (§7); every not-executed result carries a machine-readable reason. No verification surface can emit a bare pass.
7. A check not-executed for N consecutive cycles surfaces via doctor + console + `verification.check_inert` (event-taxonomy parity tests updated).
8. The `CycleOutcome` roll-up is persisted per cycle and consumed by wrap-up; its `unverified`/`inert` sets are never empty-by-construction (i.e., the roll-up cannot be produced by a path that discards not-executed results).
9. Vocabulary reconciliation: no new persisted status vocabulary beyond the documented extension of `CheckOutcome`/`PulseVerificationRecord`; an architecture test pins the aggregation function's purity.
10. Existing default-profile cycles still complete (the invariant changes verdicts only where a *required* check was silently degrading — each such flip is an intended, documented Phase 2 change).

---

## 13. Risks

- **Honest red is disruptive.** Paths that "worked" for months will start blocking (that is the SIP working). *Mitigation:* required-lists are per-profile policy (§6.3) — the throttle is explicit declaration, never a report-only mode (a report-only mode would recreate the masking this SIP exists to kill); Phase 2 lands per-path with live cycles.
- **Small-model ergonomics.** `smoke`/`lite` cycles on the Mac legitimately can't run everything; if defaults are too strict the invariant gets worked around. *Mitigation:* conservative per-tier required-lists; disclosure (not blocking) is the floor everywhere.
- **Vocabulary collision with SIP-0092/0070.** *Top design risk; Phase 0 exists to kill it before code.*
- **Choke-point placement inside the #186 decomposition.** The acceptance boundary lives in executor territory being restructured in 1.3. *Mitigation:* targeting 1.4 sequences this after the decomposition lands; the choke point attaches to the post-#186 completion boundary (same seam the Campaign SIP plans to use).
- **Provenance bloat.** Digests and refs, not payloads; caps follow the existing acceptance-check safety caps pattern.

---

## 14. Relationships

- **SIP-0092** — owns check types and typed-criteria authoring; this SIP owns result trust + aggregation. #114 (typed-check evaluation surfacing) is the observability sibling and can ride Phase 3.
- **SIP-0070 / SIP-0080** — verification records gain the state family + provenance; wrap-up's confidence classification consumes the roll-up.
- **SIP-0095** — preflight gains required-check tooling parity (the create-time half of #306's lesson).
- **Campaign Orchestration (1.6)** — consumes `CycleOutcome` (§10); this SIP is its evidence prerequisite (see #334).
- **Cycle Evaluation Scorecard (proposed)** — sequences after; scores presume un-fabricated inputs.
- **Issues:** closes the *class* behind #276, #306, #296, #291; enables #114; feeds #334.

---

## 15. Testing

- **Aggregation (unit, property-style):** every combination of {passed, failed, skipped, error, not_executed} × {required, optional} → asserted verdict; not-executed can never flip a verdict to accepted; purity architecture test.
- **Proof-case regression fixtures:** the exact #276 stub scenario, a no-Node image simulation (#306), a filtered-out frontend (#296), a missing required file (#291) — each asserting the honest state + reason, not just "doesn't pass."
- **Inert detection:** N-cycle sequences in the registry fixtures → detection fires at exactly N, resets on execution.
- **Doctor parity:** doctor's inert-capability report agrees with runtime behavior on the same profile (SIP-0095 parity precedent).
- **E2E (live, per the live-validation rule):** one `lite` cycle with a deliberately unrunnable required check → `blocked_unverified` + gate shows the reason; one with it optional → completes with disclosure in the roll-up.

---

## 16. Open Questions

1. Exact verdict name (`blocked_unverified` vs extending SIP-0079's outcome classes) — Phase 0 decides with the reconciliation mapping.
2. Does `blocked_unverified` route to the correction protocol (repair the *harness*, not the app) or straight to a gate? Leaning: gate first; harness-repair correction is a later refinement.
3. N for inert detection — fixed default (3) vs profile-tunable.
4. Where the roll-up persists — new columns on the run/cycle records vs a `verification_summary` artifact. Leaning: registry columns for the verdict + an artifact for the full roll-up.
5. Should provenance `subject_ref` hashing reuse the artifact-vault identity scheme (Campaign §22.1 traceability enablers) so run→artifact traceability composes for free?

---

## Appendix A — Implementation Seams (non-normative)

- **Aggregation:** a pure module `cycles/verification_integrity.py` (mirrors `cycles/preflight.py`), importable by executor, wrap-up, and tests without boundary violations.
- **Choke point:** the run-completion acceptance boundary — post-#186, the decomposed executor's completion collaborator (the same seam Appendix A of the Campaign SIP targets for continuation).
- **Provenance:** extend `CheckOutcome.actual` conventions + `PulseVerificationRecord` fields; migration in whichever lane owns the touched registry tables at implementation time.
- **Doctor:** a new check category alongside the SIP-0095 model-availability checks (`squadops doctor <profile> --check verification`).
- **Profiles:** `required_checks` key in the cycle-request-profile schema, validated at load like `time_budget_seconds` (SIP-0082 precedent). Coordinate naming with the #316 taxonomy work.
