---
title: Verification Evidence Integrity
status: implemented
author: jladd
created_at: '2026-07-05T00:00:00Z'
sip_number: 96
updated_at: '2026-08-05T18:36:50.247703Z'
---
# SIP: Verification Evidence Integrity

## Status
**Status:** Implemented (2026-08-06, v1.5 line) — accepted 2026-07-06 (PR #337) at **revision 2**; core shipped across the 1.4 windows and live-proven; the audit's remaining normative set (`docs/plans/sip-promotion-audit-2026-08-03.md`) closed in the 1.5 Gate-2 arc: gate-waiver #682 (PR #742), wrap-up consumer #683 (PR #743), §9 inert detection #684 (PR #744), §8 pulse SKIP-only amendment (AC#6, the promotion PR). Full AC→evidence mapping: `docs/plans/SIP-0096-promotion-evidence.md`

**Targets:** shipped v1.4 arc (core) + v1.5 Gate 2 (completion); the v1.8 scorecard's gate on this SIP is now satisfied
**Motivated by:** the 2026-07-04 health assessment finding that orchestration maturity is outrunning evidence quality. The 2.0 arc (Campaign → Test Bay → capability promotion) automates decisions over cycle evidence; this SIP must land before Campaign continuation automation because Campaign decisions must not consume unclassified or non-creditable verification evidence.
**Builds on:** SIP-0070 (pulse checks / verification framework, `PulseVerificationRecord`, decisions D13/D18), SIP-0092 (typed acceptance — the check *types* and severity model; **this SIP does not amend SIP-0092 §6.1.4** — see §6.1), SIP-0079 (outcome classes), SIP-0086 (output validation), SIP-0095 (deterministic-gate + doctor-parity precedent), SIP-0077 (cycle event system), SIP-0064 (Cycle/Run/Gate).
**Proof cases:** #291 (`required_files` declared but unenforced), #306 (agent image lacks Node.js → frontend checks cannot execute and their results merge non-blocking), the SIP-0070 `determine_boundary_decision` SKIP-only→PASS rule, and — as *predecessors whose class this SIP locks* — #276 (stub-fallback, detection shipped in PR #289), #290 (frontend build check, shipped), #296 (source-filter, **closed** `5cb22ce`).

---

## 1. Summary

Introduce a single, framework-wide **integrity invariant** over acceptance and verification evidence:

> **For aggregation purposes, every verification result resolves to exactly one evidence family: executed-and-passed, executed-and-failed, or not-executed. Only executed-and-passed credits as success. Not-executed results are non-creditable: they never improve a pass count, threshold, or all-green rule, and — when the check is required — they block acceptance as `blocked_unverified` rather than disappearing.**

SquadOps enforces pieces of this already (SIP-0092 evaluator errors block per severity; SIP-0070 D18 fails a suite on timeout-skips; the QA path blocks on `executed=False`; PR #289 detects stub-fallback tests). What it lacks is the *rule* — so the remaining leaks each read silence as green in a different way: pulse boundary decisions treat SKIP-only records as PASS, fullstack frontend results merge non-blocking even when the toolchain is absent (#306), typed-check `skipped` never blocks anything, `required_files` is a contract nothing enforces (#291), and no run-level evidence roll-up exists at all.

This SIP adds: (1) the **classification and aggregation rule** enforced at a single choke point, (2) **execution provenance** on every result, (3) **non-executable/inert check detection** (doctor-first), and (4) the **`CycleOutcome` roll-up** — the honest per-cycle evidence contract consumed by wrap-up, gates, and later the Campaign continuation decision.

---

## 2. Motivation / Problem

The 1.x arc built substantial verification machinery, and parts of it already refuse to credit silence. But the enforcement is per-surface and inconsistent, so the same defect class keeps reappearing wherever a surface lacks it:

- **Pulse boundary decisions credit silence:** `determine_boundary_decision` treats SKIP-only records as PASS ("no guardrail evidence to block") — the purest shipped instance of not-executed aggregating as success. Meanwhile the *same subsystem's* D18 correctly fails a suite when timeout skips checks. Two rules, one framework.
- **Frontend verification is invisible when it cannot run:** the fullstack path merges frontend build/test results non-blocking (SIP-0070 D13), and the deployed agent image lacks Node.js (#306) — so every fullstack cycle has "passed" frontend verification that never executed.
- **Typed-check `skipped` never blocks**, whatever the reason — a designed graceful bound (RC-12a `unsupported_stack`) and a missing subject look identical in aggregation.
- **Declared contracts go unenforced:** `build_profile.required_files` (#291) — a run shipped without the Dockerfile its own profile required, green.
- **No run-level roll-up exists:** runs terminate in `RunStatus` and gates record `GateDecision`s, but nothing durable answers "what was verified, what failed, what never ran."

The class has already produced the #276 incident (a `completed`, qa-green run whose backend could not import and whose frontend could not build). The individual fixes that followed (#289, #290, #296) were whack-a-mole wins; this SIP is the rule that makes the class unrepresentable. The stakes rise at 1.6: Campaign's continuation policy acts automatically on this evidence, and `stop_success` on fabricated green is the failure mode the whole 2.0 direction cannot afford.

This is the codebase's existing hard rule — *no fallbacks that mask a missing data source* — applied to verification itself.

---

## 3. Decision

1. Adopt the **integrity invariant** (§6) as a framework-wide rule, enforced at a single pure aggregation choke point per run (§6.4) — the established pure-decision-at-a-choke-point pattern (SIP-0089 reserve-buffer guard, SIP-0095 preflight).
2. **Classify, don't re-vocabulary:** producers keep their existing persisted statuses; every result is *classified* into an evidence family for aggregation (§6.1). No new persisted status vocabulary.
3. Add **execution provenance** (§7) and **non-executable/inert detection** (§9, doctor-first).
4. Define the **`CycleOutcome` roll-up** (§10) as the durable evidence contract for wrap-up, gates, and the Campaign continuation decision.
5. Decide the previously-open semantics **in this text**: `error` classification (§6.1), `blocked_unverified` routing, lifecycle mapping and operator waiver (§6.5), the check-identity model (§6.3), and the severity × required interaction (§6.3).

---

## 4. Scope

- **In:** the classification + aggregation rule and its choke point; provenance; the required-check declaration model; the conformance changes in §8; non-executable/inert detection (doctor); the `CycleOutcome` roll-up; the SIP-0095 preflight parity extension.
- **In (reuse, not rebuild):** `CheckOutcome` and typed-check severity (SIP-0092), `PulseVerificationRecord` + D13/D18 (SIP-0070, with the two amendments named in §8), outcome classes (SIP-0079), gate/HITL mechanics (SIP-0064).
- **Applies to:** typed acceptance checks, generated-test execution, build-profile checks, `required_files`, and pulse-check verification.

---

## 5. Non-Goals

- **No new check types** (SIP-0092's lane) and **no new persisted status vocabulary** — classification is derived (§6.1).
- **No amendment to SIP-0092 §6.1.4**: evaluator `error` remains an executed, severity-governed failure. This SIP names its two SIP-0070 amendments explicitly (§8) rather than overriding silently.
- **No scorecard, no Test Bay, no Campaign mechanics** — downstream consumers of trustworthy evidence.
- **No global report-only mode.** A framework-wide soft switch would recreate the masking this SIP exists to kill. The throttle is per-check declaration (§6.3) — optional checks are, by design, per-check disclosure-without-blocking.
- **No blanket "everything is required."** `smoke`/`lite` legitimately run degraded; the invariant forces honesty about what didn't run, not maximal strictness.
- **No automated harness repair** beyond what already ships (#289's correction path). Expanding agent authority to rewrite verification harnesses is explicitly deferred until the system can distinguish harness defects from product defects with high confidence.

---

## 6. The Integrity Invariant

### 6.1 Three layers, deliberately separate

| Layer | Vocabulary | Status |
|---|---|---|
| **Persisted result status** | `CheckOutcome.status` (`passed/failed/skipped/error`), runner `executed`/`not_executed`, `PulseVerificationRecord` outcomes | **unchanged** — producers emit what they emit today |
| **Evidence family** (aggregation-time classification) | `executed-and-passed` · `executed-and-failed` · `not-executed` | **new, derived** — from persisted status + reason + provenance; not persisted per-producer |
| **Run verdict** | `accepted` · `rejected` · `blocked_unverified` | **new** — computed once per run by the choke point, recorded on the roll-up (§10); **not** a `RunStatus` (§6.5) |

This SIP does not require any producer to emit a new status. It requires every result to be *classifiable*:

- `passed` → **executed-and-passed** (only when provenance shows the real subject was evaluated — see the stub rule, §6.6).
- `failed` → **executed-and-failed**.
- `error` → **executed-and-failed** — preserving SIP-0092 §6.1.4 (evaluator errors block per severity and route to correction). An evaluator that crashed *attempting* the real subject is executed context, not silence. Its `reason` distinguishes it for diagnostics; its aggregation family does not credit it and does not soften it.
- `skipped` / `not_executed` → **not-executed**, with a mandatory machine-readable reason (§7). This family includes designed skips (`config_disabled`, `unsupported_stack` per RC-12a), environment gaps (`missing_tooling`), subject gaps (`subject_missing`, `import_error`, `filtered_out`), and `timeout_before_execution`. These are semantically different diagnoses; the invariant is not that they are identical — it is that **none of them can aggregate as success**.

### 6.2 Aggregation rule

A single **pure aggregation decision** evaluates all of a run's recorded check results against the declared required-check set and produces the run verification summary. (Signature and module placement are implementation detail — Appendix A.)

- **Not-executed results are excluded from both the numerator and all success-credit calculations, and their presence is separately disclosed.** They may not improve a percentage, satisfy an all-green rule, or be treated as neutral success evidence. "0 failed out of 0 executed" is not 100%; it is zero evidence.
- Any **required** check classified not-executed → verdict `blocked_unverified`.
- **Executed-and-failed** results keep their existing blocking/correction semantics (SIP-0092 severity for typed checks; existing QA/build blocking elsewhere). This SIP changes nothing about how genuine failures route.
- **Optional** checks are non-blocking but **never invisible**: their failed and not-executed outcomes are recorded and surfaced in the roll-up. Optional means non-blocking, never irrelevant.
- The decision is **pure** — no persistence or dispatch inside; side effects only at the boundary that acts on it (architecture-tested, per the SIP-0095/Campaign precedent).

### 6.3 Required vs optional: declared, scoped to stable checks

Required-vs-optional classification is resolved **only from explicit profile/build-profile declarations** — never inferred from check names, check types, historical behavior, or agent narrative.

**Check identity model (which checks are even addressable):**

- **Framework and profile-declared checks have stable identity** and are the domain of `required_checks`: the test-execution check, stub detection, the frontend build check, `required_files`, and pulse suites (by `suite_id`). These are the checks a profile can require and the only checks §9 tracks across cycles.
- **Plan-authored typed checks (SIP-0092) have per-cycle identity only** (they are LLM-authored inside each cycle's plan). They are classified into evidence families and disclosed in the roll-up, but they are **not** profile-addressable as required and are excluded from cross-cycle inert detection. Their blocking behavior remains governed by SIP-0092 **severity**, unchanged.

This also resolves the severity × required interaction: **severity governs plan-authored checks; required/optional governs framework/profile checks. The domains are disjoint by construction.**

Defaults are conservative per profile tier: `smoke`/`lite` mark most framework checks optional (honest disclosure, no blocking); `full` marks the build/test spine required. **Ordering constraint:** a profile may not mark a check required whose tooling is knowably absent from the deployment it targets — concretely, `full` cannot require frontend checks before #306's image fix ships. SIP-0095 preflight gains the parity check: a *required* check whose tooling is absent at create time is a create-time warn/422, never a mid-run surprise.

### 6.4 Choke point placement (and the #186 relationship)

The aggregation decision runs once per run at completion. Because the executor is being decomposed in 1.3, the placement is stated as a **requirement on #186's design, not a dependency on its outcome**: the decomposition must produce a completion collaborator that computes the run verification summary — this SIP's aggregation function is that collaborator's first client. **Fallback if #186 lands differently or slips:** the aggregation call attaches to the current executor's run-finalization path; the pure module is seam-independent either way.

### 6.5 `blocked_unverified`: routing, lifecycle, and waiver

**`blocked_unverified` is a harness/evidence-integrity verdict, not an application-quality verdict.** `failed` means the product did not satisfy a criterion and routes to product correction. `blocked_unverified` means the framework cannot honestly claim verification — the repair target is the harness, environment, profile, or source set. Console and wrap-up copy must preserve this distinction (§13).

- **Lifecycle:** the verdict is recorded on the roll-up (§10); it introduces **no new `RunStatus`**. The run terminates per existing lifecycle semantics; acceptance surfaces (gates, wrap-up, Campaign) read the verdict, not the lifecycle.
- **Routing, by reason class:**
  - *Harness-diagnosable during the run* (stub substitution, generated-test import failure): the existing correction path keeps working exactly as PR #289 wired it — detection → validation failure → correction regenerates the harness. This SIP does not convert that self-healing loop into an operator interrupt; the verdict reflects the *final* state after correction has had its bounded attempts.
  - *Create-time-knowable* (`missing_tooling` for a required check): SIP-0095 preflight 422 — never reaches a run.
  - *Residual at run end* (required check still not-executed after the above): the verdict is `blocked_unverified` and routes to the **gate**.
- **Operator waiver:** a gate presented with `blocked_unverified` may explicitly **accept-with-waiver**, recording the waived checks and reason on the gate decision and the roll-up. This is consistent with SIP-0092 §6.3.2's prohibition on `loosen_acceptance`: the check results stand unaltered and un-loosened; the waiver is an operator decision recorded *above* the evidence, never a mutation of it. A waiver is never implicit.

### 6.6 Evidence integrity violations (named class)

The following are **evidence integrity violations** — the phrase is normative so QA and architecture tests can assert against it:

1. **Stub substitution reporting pass:** no verification producer may substitute a stub, placeholder, empty suite, mock subject, or generated fallback artifact and report `passed`, unless that substitution is explicitly the subject under test and disclosed in provenance.
2. **A missing required check yielding `accepted`.**
3. **Dropping not-executed results from the roll-up** (silent disclosure failure).
4. **Narrative override:** agent narrative, self-report, generated summaries, or wrap-up prose cannot override the structured verification verdict.

---

## 7. Execution Provenance

Every check result carries evidence that it ran — or a machine-readable reason it did not (extending `CheckOutcome.actual` conventions / `PulseVerificationRecord` fields; exact field names are implementation detail):

`executed_at`, `duration_ms`, `subject_ref` (what was checked — file-set hash, artifact ID, endpoint), `executor_ref` (where), and for command-backed checks exit metadata + a bounded output digest. For not-executed results the `reason` is mandatory and machine-readable; the taxonomy must include SIP-0092's designed skips (`config_disabled`, `unsupported_stack`) alongside `missing_tooling`, `import_error`, `subject_missing`, `filtered_out`, `timeout_before_execution`.

**Provenance captures bounded identifiers, hashes, exit metadata, and digests; it must not persist unbounded logs or payload copies** (the existing acceptance-check caps pattern applies).

---

## 8. Surfaces That Must Conform (corrected against actual current behavior)

| Surface | Today (verified) | Conformance change |
|---|---|---|
| Pulse boundary decision (SIP-0070) | **D18 already fails** a suite on timeout-skips; but `determine_boundary_decision` treats **SKIP-only records as PASS** | **Named amendment to SIP-0070:** SKIP-only is zero evidence, not PASS — classify per §6.1, aggregate per §6.2 |
| Fullstack frontend results (SIP-0070 D13) | Frontend build/vitest results **merge non-blocking**; toolchain absent on deployed image (#306) so they never execute, invisibly | **Named amendment to SIP-0070 D13:** when frontend checks are profile-required, not-executed blocks per §6.2; #306 image fix makes them executable; preflight parity covers the required-but-absent case |
| Typed acceptance checks (SIP-0092) | `error` **already blocks** per severity; `skipped` **never blocks**, whatever the reason | No semantics change to severity routing; results gain reasons + provenance and are classified/disclosed in the roll-up. Designed skips stay non-blocking (plan-authored checks are not required-addressable, §6.3) |
| Generated-test execution | QA path **already blocks** on `executed=False`; stub detection **shipped** (PR #289) and self-heals via correction | Keep both. Conformance = classification + provenance (stub detections recorded as integrity events, §6.6), not behavior change |
| `required_files` (#291) | Declared in build profiles, **enforced nowhere** | Remains a build/profile **contract**; its enforcement **emits a normal check result** aggregated through the same choke point — not a parallel mechanism |

(Rev-1 errata, for the record: rev 1 claimed `error` flowed through aggregation without blocking and listed #296 as open — both wrong; #296 closed via `5cb22ce` before rev 1 was drafted, and PRs #289/#290 had already landed the stub-detection and frontend-build checks.)

---

## 9. Non-Executable and Inert Checks

Two related conditions, deliberately distinct:

- **Non-executable** — knowable before or during a run: this check cannot execute in the current environment/profile (missing tooling, absent subject class). Surfaced by **doctor** (`squadops doctor` gains a verification category reporting, per profile, which declared checks are non-executable in the target environment) and by SIP-0095 preflight when the check is required.
- **Inert** — historical: a check with stable identity has reported not-executed for **N consecutive cycles** (default N=3) in the same project/profile. A permanently skipping check is indistinguishable from no check.

Rules:

- Detection keys on **stable logical check identity** (§6.3's stable subset only) — not transient runner names, generated file paths, or display labels — and must survive refactors and profile reloads.
- The inert counter **resets only when the check evaluates the real subject** — not when the check disappears, is renamed, or is reclassified optional. Disappearance of a previously-required check is itself surfaced.
- **v1.4 ships doctor-only.** The console badging and a dedicated SIP-0077 event are deferred until demand — preflight parity + required-check blocking already cover the acute cases; the detector's residual v1 value is optional-check hygiene, which doctor serves.

---

## 10. The `CycleOutcome` Evidence Roll-Up

The durable per-cycle summary — the contract downstream consumers read:

`verified` (executed-and-passed, provenance refs) / `failed` (executed-and-failed) / `unverified` (not-executed, with reasons) / `inert` (chronic) / `waived` (operator gate waivers, §6.5) / `verdict` (`accepted | rejected | blocked_unverified`) — all as references into the SIP-0070/0092 records, not copies.

Consumers, in order of arrival: **wrap-up** (SIP-0080 confidence classification gets an honest basis), **operator gates** (a `blocked_unverified` gate sees the harness-vs-product distinction and the waiver option), and — the strategic one — the **Campaign continuation decision** (1.6), whose rule that `stop_success` requires accepted evidence, and that `blocked_unverified` yields only `repair`/`escalate`, is only as strong as this contract. This SIP ships one even-minor ahead of Campaign so the contract exists, live-validated, before anything automates over it.

---

## 11. Phasing (within the 1.4 arc)

- **Phase 0 — Verification audit (docs-only, can run during 1.3).** *Confirm* the §6.1 classification mapping and §8 conformance table against the code and the accepted SIP-0092/0070 texts — including the known 0092 spec-vs-code divergence (out-of-safelist commands: spec says `skipped`, code returns `error`). Phase 0 verifies the mapping this SIP specifies; it does **not** decide semantics — those are decided above. Gate: any discovered conflict returns to this SIP as a revision, not a silent reinterpretation.
- **Phase 1 — Classification + aggregation + provenance.** The pure aggregation module, evidence-family classification, `blocked_unverified` verdict on the roll-up, provenance fields, `required_checks` declaration schema, choke-point wiring per §6.4 (fallback seam if #186 hasn't landed). Inert by construction in default profiles (no required lists shipped yet).
- **Phase 2 — Conformance of the real gaps.** (a) The two named SIP-0070 amendments: SKIP-only→PASS fix and D13 required-frontend blocking; (b) #306 image fix (makes frontend checks executable) + preflight parity; (c) #291 `required_files` as a checked contract; (d) provenance/classification retrofit of the already-shipped #289/#290 checks (no behavior change). Each lands with a live `lite` cycle demonstrating the honest result. **This phase turns silently-green paths honestly red where a profile requires them — that is the point; the per-profile required lists are the throttle.**
- **Phase 3 — Surfaces.** `CycleOutcome` roll-up persisted + consumed by wrap-up; gate waiver flow; doctor verification category. #114 (typed-check evaluation surfacing) rides here.

Acceptance of the SIP is all phases (SIP-0089/0090 precedent).

---

## 12. Acceptance Criteria

1. **Aggregation property (tested property-style):** across all combinations of persisted status × required/optional, only executed-and-passed credits toward any pass count, threshold, percentage, or all-green rule; not-executed results are excluded from numerator and success credit and always disclosed; "0 failed of 0 executed" yields zero evidence, never 100%.
2. A run with any required check not-executed yields verdict `blocked_unverified` — distinct from `rejected`, carried on the roll-up (no new `RunStatus`), routed per §6.5, and presented by gates as a harness/evidence problem, not a product failure.
3. **Anti-stub (integrity violation #1):** no verification producer may substitute a stub, placeholder, empty suite, mock subject, or fallback artifact and report `passed` unless the substitution is explicitly the subject under test and disclosed in provenance — regression-tested with the #276 stub fixture; #289's detection path records an integrity event in provenance.
4. **No narrative override (integrity violation #4):** agent narrative, self-report, or wrap-up prose cannot alter the structured verdict — tested by injecting a contradicting narrative and asserting the verdict stands.
5. **Declared, not inferred:** required-vs-optional resolves only from explicit profile/build-profile declarations; a test asserts no code path infers requiredness from names, types, or history. Plan-authored typed checks are not required-addressable and remain severity-governed (SIP-0092 unchanged).
6. **Pulse amendment:** SKIP-only pulse records no longer produce PASS; the boundary decision reflects zero evidence per §6.2 (the D18 timeout rule is unchanged).
7. **Frontend amendment (#306):** on the fixed image, frontend checks execute; where a profile requires them, absence of tooling is a create-time preflight warn/422 and a run-time not-executed never merges silently (D13 amended for the required case).
8. **`required_files` (#291):** enforced at run completion as a check result through the same choke point; a missing declared file on a profile that requires it yields a blocking verdict per its Open-Q6 classification, never silent completion.
9. **Provenance:** every executed result carries provenance; every not-executed result carries a machine-readable reason from the taxonomy (including `config_disabled`/`unsupported_stack` designed skips); provenance is bounded (no raw logs/payloads).
10. **Inert/non-executable:** doctor reports non-executable checks per profile/environment before any cycle; a stable-identity check not-executed for N consecutive cycles is reported inert; the counter keys on logical identity, survives renames, and resets only on real-subject evaluation.
11. **Roll-up integrity (violation #3):** the roll-up is constructible only via the aggregation decision, which receives every recorded check result — architecture-tested so no construction path can discard not-executed results.
12. **Waiver:** an operator can accept a `blocked_unverified` run only through an explicit gate decision that records the waived checks and reason on the roll-up; no implicit waiver path exists; check results are never mutated by a waiver.
13. **Purity + no third vocabulary:** the aggregation decision is side-effect-free (architecture test); producers emit no new persisted status vocabulary — the evidence family is derived at aggregation time from the §6.1 mapping as written in this SIP.
14. **Compatibility, honestly stated:** existing default-profile cycles continue to complete **except** where they currently rely on a required check silently degrading; Phase 2 enumerates the exact default-profile verdict flips in advance (expected: none until profiles opt into required lists), and no verdicts outside that enumeration change.

---

## 13. Risks

- **Honest red is disruptive.** Paths that "worked" start blocking where profiles require them — that is the SIP working. *Mitigation:* per-profile required lists are the only throttle (no global report-only mode, §5); Phase 2 lands per-path with live cycles; preflight converts create-time-knowable cases into 422s before any run spends compute.
- **Run-time-only reasons bite mid-run.** `import_error`/`subject_missing` cannot be caught at create time; on `smoke`/`lite` most checks are optional so blocking behavior is under-exercised until `full` (Spark) runs. *Mitigation:* the §6.5 routing keeps #289's correction self-healing for harness-diagnosable reasons (no new operator interrupts there); the E2E tests (§15) exercise a required blocking case on `lite` deliberately before any long Spark cycle depends on it.
- **Operator confusion between `failed` and `blocked_unverified`.** *Mitigation:* §6.5's framing is normative — console and wrap-up copy must distinguish failed verification from unverified evidence and show the repair-target category; the gate waiver flow makes the operator path explicit.
- **Vocabulary collision with SIP-0092/0070.** Mitigated structurally: the three-layer model (§6.1) leaves persisted vocabularies untouched, `error` semantics are preserved, and the two SIP-0070 amendments are named rather than implicit. Phase 0 verifies rather than decides.
- **#186 lands differently or slips.** *Mitigation:* §6.4 states the completion boundary as a requirement on #186's design with a pre-#186 fallback seam; the pure module is placement-independent.
- **Provenance bloat.** Digests and refs only, bounded per §7.

---

## 14. Relationships

- **SIP-0092** — unchanged: check types, plan-authored typed checks, severity routing, `error`-blocks semantics, and the `loosen_acceptance` prohibition (the §6.5 waiver records above evidence; it never loosens a check). #114 rides Phase 3.
- **SIP-0070** — two named amendments (§8): SKIP-only→PASS and D13's non-blocking frontend merge for the required case. D18 unchanged. `PulseVerificationRecord` gains reasons/provenance.
- **SIP-0079/0080** — outcome classes and wrap-up consume the roll-up; wrap-up's confidence classification gets an honest basis.
- **SIP-0095** — preflight gains required-check tooling parity.
- **Campaign Orchestration (1.6)** — consumes `CycleOutcome` (§10); this SIP is its named evidence prerequisite.
- **Cycle Evaluation Scorecard (proposed)** — sequences after.
- **Issues:** closes the class behind #276 (predecessors #289/#290/#296 already shipped), #306, #291; enables #114; feeds #334.

---

## 15. Testing

- **Aggregation (unit, property-style):** the full status × required/optional matrix per AC#1; purity architecture test; the "0 of 0 executed" case explicitly.
- **Integrity-violation fixtures:** the #276 stub scenario (detection → integrity event in provenance), a narrative-override attempt, a roll-up construction path that tries to drop not-executed results (must be impossible), an implicit-waiver attempt.
- **Amendment regressions:** SKIP-only pulse records (was PASS, now zero evidence), required-frontend on a no-Node image (preflight 422; run-time not-executed blocks), `required_files` missing file.
- **Identity/inert:** N-cycle sequences with a rename mid-sequence (counter must not reset), a disappearing required check (surfaced), reset on real execution.
- **Doctor parity:** doctor's non-executable report agrees with runtime behavior for the same profile (SIP-0095 precedent).
- **E2E (live, per the live-validation rule):** one `lite` cycle with a deliberately unrunnable **required** check → `blocked_unverified`, gate shows harness framing, waiver path exercised and recorded; one with the check optional → completes with disclosure in the roll-up.

---

## 16. Open Questions

1. Verdict naming only (`blocked_unverified` vs an SIP-0079-style spelling) — cosmetic; the semantics, routing, lifecycle mapping, and waiver are decided in §6.5.
2. ~~Gate vs correction routing~~ — **decided in §6.5** (by reason class; #289's correction path preserved; gate for residuals; waiver explicit). Automated harness repair beyond #289 is explicitly deferred (§5) until the system can distinguish harness defects from product defects with high confidence.
3. N for inert detection — fixed default (3) vs profile-tunable.
4. Roll-up persistence — registry columns for the verdict + an artifact for the full roll-up (leaning), vs columns only.
5. Should provenance `subject_ref` hashing reuse the artifact-vault identity scheme so run→artifact traceability (Campaign §22.1 enabler) composes for free?
6. `required_files` family classification: is a missing declared file "not-executed" (subject missing) or "executed-and-failed" (contract checked, violated)? Leaning executed-and-failed (the check *can* run; the file is absent) — Phase 0 confirms against the #291 implementation seam.

---

## Appendix A — Candidate Implementation Seams (non-normative)

- **Aggregation:** a pure module (e.g. `cycles/verification_integrity.py`, mirroring `cycles/preflight.py`), importable by executor, wrap-up, and tests without boundary violations; plausible shape `aggregate_verification(results, required_check_ids) -> RunVerificationSummary`.
- **Choke point:** post-#186, the decomposed executor's completion collaborator (this function as its first client); pre-#186 fallback at the current executor's run-finalization path.
- **Provenance:** extend `CheckOutcome.actual` conventions + `PulseVerificationRecord` fields; migration in whichever lane owns the touched registry tables at implementation time.
- **Doctor:** a verification category alongside the SIP-0095 model-availability checks.
- **Profiles:** a `required_checks` key in the cycle-request-profile / build-profile schema, validated at load (SIP-0082 precedent); naming coordinated with the #316 taxonomy work.
- **Waiver:** a field on the existing `GateDecision` record + roll-up reference — no new gate type.

---

## 17. Post-implementation amendments

### 17a. 2026-09-15 — a contested result: the producer's dispute becomes evidence (built — the as-built paragraphs below record what shipped; 1.8.2)

**Status.** Drafted on the owner's ask of 2026-09-15 and targeted for 1.8.1 by the owner's
ruling of the same day; **re-targeted to 1.8.2 on 2026-09-17** by the owner's ruling on the
1.8.1 plan's review (`docs/plans/1-8-1-plan.md` §2.3, §6): the 1.8.1 line carries the flip and the
Solo window alone, so the window measures the substrate 1.8.0 measured, and 1.8.2 is the
model-capability tranche — this amendment, SIP-0086 §12a and their diagnostics (the
`false-criterion` shape is fixed in that plan's §6; #1581 moves with it). Not built. Until the PR that builds it lands and amends this section
with what shipped, nothing below describes main.

**The invariant is unchanged.** Every result still resolves to exactly one of the three
families of §6, and only executed-and-passed credits. A contested result is an **attribute on
a row**, never a fourth family: it does not credit, it does not block on its own, and it never
turns a failure into a pass. What it adds is a voice the evidence has never carried.

**The gap.** The framework has refused correct work more often than it has caught the model
producing wrong work of the same kind, and each refusal spent a round and handed the producer
a brief telling it to fix something that was not broken: a correct `@/lib` alias import refused
by a false-positive `declared_imports` on 2026-09-01, which the model then degraded to a
relative path to comply (fixed at `acceptance_checks.py:760`); a correct dev fix refused twice
because the check ran on a tree without the qa suite (#1259); dead Python-AST checks on `.jsx`
files that burned two rolls' full correction budgets (pf-47, pf-49); an uncollected `.test.tsx`
suite that rewrote seven app files and rejected an unchanged suite (#1532, #1533); a builder
repair discarded unheard (#1255). The repair prompt asks the model to "say why in one line
rather than making it silently" when it believes a change beyond the named failure is needed
(`request.cycle_repair_task.md`), and nothing reads that line. The producer is judged by
checks it cannot contest.

**What changes.**

1. **A typed dispute output.** Every build and repair task may emit one structured block,
   `disputed_checks`, listing `{check, criterion_id, subject, reason}` for a criterion it
   believes is wrong or inapplicable — through the prompt-asset system, never a prose line.
   The extractor stores it on the task outputs beside the artifacts; a response with no block
   disputes nothing.
2. **`contested` on the row.** At the verification choke point (§6.1), a row whose check,
   criterion and subject match a dispute gains `contested: {by: <role>, reason}`. The family
   is unchanged. A dispute that matches no row is recorded as `unmatched_dispute` and read as
   nothing.
3. **The failure evidence carries contested rows in their own block**, and the analyzer's
   prompt asks one question of each: does the evidence support the dispute? Its answer is a
   typed field on the analysis output, `dispute_confirmed: true|false`, with the reason.
4. **Routing.** A contested row the analyzer confirms routes the round to the harness path
   that `blocked_unverified` already uses (§6.5): the round is refunded (SIP-0108 §4.1's
   refund rule), the check is named in the run's terminal decision, and an issue is opened by
   the driver's readout, not by the cycle. A contested row the analyzer does not confirm
   proceeds exactly as an uncontested failure, with the dispute and the rejection recorded.
   The lead's decision inputs show contested rows and the analyzer's answer; no agent gains
   waiver authority, which stays the operator's (§6.5).
5. **The readout.** The verification-set driver counts contested rows per cell beside failed
   and not-executed ones, split by confirmed and rejected, so a check with a history of
   confirmed disputes is visible as a check defect (SIP-0108 §4.2:
   `criteria_or_contract_failure`), and a producer that disputes everything is visible too.

**Why.** A gate that cannot be contested converts every false positive into a lost round and a
misleading brief, and the record shows the false positives were real and recurring. Giving
the producer a typed, read, adjudicated voice costs one field and one question to the
analyzer, and it turns each false positive into a filed check defect on the round it occurs
instead of a rejected roll read out a week later.

**Evidence.** The cases above, each with its issue or fix; the repair template's unread line;
`docs/plans/1-8-0-rejection-baseline.md` for the classes those refusals produced.

**Ruled by.** The owner, 2026-09-15: drafted on the question "does the framework constrain
the model it runs", and targeted for 1.8.1. The design is the implementer's, for review on
the PR that builds it. **Re-targeted to 1.8.2 by the owner, 2026-09-17**, on the 1.8.1 plan's review
(the status line above).

**As built — change 1 (2026-09-24, 1.8.2 plan §3.3).** A build or repair response may end with
one fenced block whose info string is `disputed_checks`, a YAML list of
`{check, file, criterion_id, reason}` (`src/squadops/capabilities/disputed_checks.py`).
`_llm_call` strips it from every response before anything reads the response, and collects its
entries on the task's `ExecutionContext`. The strip has to come first: the fence has no path, so
on a task expecting one file the single-expected-file fallback (`fenced_parser.py`, #566) would
store the block as that file. The handler executor carries the entries on the task's outputs as
`disputed_checks` on every result a handler reached, the failed one included, and adds no key
when there is no dispute.

**The section names what it offers.** A dispute has to name its check, and no prompt named one.
A build task's expectation lines say what each criterion requires but never its check or
criterion id (`contract_expectations.expectation_line`). A repair and a self-evaluation pass see
only "Typed checks failed: N of M" (`develop.py`, `qa_test.py`), plus the analyzer's prose. So
the section, rendered from one asset (`request.disputed_checks_appendix`), lists the checks the
task may dispute, each as `check`, `file` and `criterion_id`:
- a build task gets its typed criteria, under the `acceptance:` name their rows will carry
  (`criterion_identities`)
- a repair gets the blocking-failed rows of its failure evidence, each with its reason
  (`failing_row_identities`)

A task judged by no named check gets no section. The paths that carry typed criteria render it:
develop and qa test on the plan-driven path (the path every manifest-driven task takes),
builder assemble, and the three correction repairs (dev, builder, qa). The legacy monolithic
paths carry no typed criteria, so they have nothing to offer. The repair template's "say why in
one line" sentence, which nothing read, now points at the block instead. The pulse-check repair
chain's `development.repair` (`request.repair_task_base`) is not given the section yet: whether a
pulse check can be contested is decided with change 2. The self-evaluation follow-up
named no check either; SIP-0086 §12a change 3 rewrote it as an asset, and it now carries the
section, listing the pass's failing rows as a repair's does. **Diverges from the text above:** the
dispute names `file`, not `subject`. A row's `subject` is the plan-task id that produced it
(`CheckResult.subject`, §6.3), which the producer does not see. It is implied by which task
disputed, so matching (change 2) takes it from the task. `file` is what separates one check run
on several files: a typed row carries it as `params.file`.
`check` and `reason` are required; an entry without either disputes nothing and is logged.

**As built — change 2 (2026-09-24).** The handler executor stamps each dispute with the role
that made it (`by`), because a failed result's outputs don't always carry the role elsewhere.
`mark_contested` puts `contested: {by, reason}` on each **blocking-failed** row a dispute names:
- the same check, with or without the `acceptance:` prefix
- the same `params.file` and `criterion_id` wherever the dispute gives them

A row that passed, or failed only as advice, has nothing to contest, so a dispute naming only
such rows is `unmatched`. It marks at the two readers of a task's rows, over the same outputs:
- **`normalize_task_checks`**, the §6.1 producer adapter. The result gains
  `CheckResult.contested` and the roll-up `FailedCheck.contested`, stored with the summary
  (`failed_detail[].contested`). A dispute of `tests_pass` rides the result synthesized from
  `test_result`, since the row itself is skipped. The family and the verdict are unchanged,
  and a test holds the verdict equal with and without a contest.
- **`build_failure_evidence`**, where the analyzer reads. Contested rows are carried in their
  own block, `contested_rows` (change 3's question is asked of it). Disputes that named no
  failing row go in `unmatched_disputes`, recorded and read as nothing. `contested` is a
  structural row key, so it never enters a derived reason or the correction signature.

**A repair's dispute is carried to the next round.** Each round re-dispatches the failed task
and runs its analyzer before its repair, so a repair's dispute (#1581's shape) is read in the
next round or nowhere. The repair outcome collects the steps' disputes. The runner writes them
to a run-lived `dispute_carry`, which the executor threads the way it threads `signature_state`
(#435), and the next round marks them onto its evidence beside the task's own. A round reads its
own predecessor's: the carry is replaced each round, not appended.

**As built — change 3 (2026-09-24).** When the evidence carries `contested_rows`, the analyzer's
request gains one section, `request.data_analyze_failure_contested_appendix`. It lists each
contested row (its identity, why it failed, who disputed it and why) and asks one question of
each: does the evidence support the dispute? Its task-type fragment names the answer as an
optional field. The answer is `dispute_rulings` on the analysis output:
`{check, file?, criterion_id?, dispute_confirmed, reason}`, one per contested row. This
diverges from the text above, which names a single `dispute_confirmed`: an analysis can carry
several contested rows, so the answer is per row.

The rulings are parsed **leniently**. A ruling without a boolean `dispute_confirmed`, a `check`
and a `reason` is dropped and logged, never a reason to reject the analysis: rejecting it would
send the round to NEEDS_REPLAN for want of an answer that was only ever optional. An analysis
with no contested row is asked nothing new, and its outputs carry no `dispute_rulings` key.

**Not asked where there is no analyzer.** A profile whose correction steps omit `analyze`
(Solo's `[repair]`, SIP-0108 §10i) records its contests (change 2) and never adjudicates them;
each proceeds as an uncontested failure.

**As built — change 4 (2026-09-24).** After the diagnosis and before any repair, the runner
reads the rulings against the contested rows (`rule_contests`: a ruling names a row the
way a dispute does). If any contested row is confirmed, the chain ends there, through the
termination path `plan_defect` already uses (#435):
- **a typed `CorrectionTermination`** with a new reason, `contested_check`, stored as the run's
  `correction_termination` artifact with each confirmed contest: identity, dispute, ruling
- **the round refunded**: a `RefundedRound` with a new reason, `confirmed_dispute`, and the
  `correction attempt N refunded: …` line the driver already reads
- **the run's `RunTerminalDecision`** (`correction_terminated` / `contested_check`) naming the
  confirmed checks in a new field, `contested_checks`
- **attribution:** `contested_check` is attributed `criteria_or_contract_failure` (SIP-0108
  §4.2), the check-defect class change 5 names

The failing row stays failed and the verdict stays whatever the rows make it. The operator
decides, as for a residual `blocked_unverified` (§6.5).

**Why the chain ends rather than the row being set aside.** A confirmed dispute says the check
fails on correct work. A repair can't pass it, so every further round would be spent on work the
check refuses again, which is the loop this amendment exists to end. A verifier that discounted
the row would be turning a failure into a pass, and no agent may do that. So when a round's
confirmed rows sit beside uncontested failures, it still ends: the uncontested failures are named
in the same evidence, and the operator reads both.

A contest the analyzer **did not confirm** (ruled against, not ruled on, or ruled on by a
ruling that names no contested row) proceeds exactly as an uncontested failure. The lead's
decision step already receives both the contested rows (`failure_evidence`) and the rulings
(`failure_analysis`).

**Wrong check, or wrong artifact.** #1581's dev answered that the qa suite, not its file, was
wrong. That isn't a wrong check: `tests_pass` did its job on another role's artifact, and a qa
repair can fix it. Confirming it would end a chain that a repair could have converged. So the
analyzer's question says so: a failure caused by another artifact is ruled **rejected**, and that
artifact is named in `implicated_files`. The own-artifact routing already acts on that name
(`analyzer_and_decision_unanimous`, the routing half of #1581, fixed earlier). The dispute is
still heard: its reason is in the evidence the analyzer reads and the verdict is recorded. It
just doesn't end the chain.

**As built — change 5 (2026-09-24).** The runner logs one line per round that carried a dispute,
whatever came of it:

    contested_rows task=<id> round=<n> confirmed=<c> rejected=<r> unruled=<u> unmatched=<m> by=<roles> — <check>: <verdict>; …

The verification-set driver reads it as `loop_texture.contested_rows`, one entry per round.
The record row shows confirmed / rejected / unruled / naming-no-failing-row totals, by role,
and names each confirmed check. So a check confirmed across cycles reads as the check defect it
is (the `contested_check` termination is attributed `criteria_or_contract_failure`), and a
producer that disputes everything is visible too. The line has a real-line sample in the
marker self-check (#1632), and a test feeds the runner's own line to the driver's reader. No
issue is opened automatically. **Diverges from the text above**, which has the readout open the
issue: the driver never writes to GitHub, because it's a measurement tool run against a public
repository. It names the confirmed check, and whoever reads the readout files the issue, as for
every other readout. The half that matters holds: the cycle opens nothing.
