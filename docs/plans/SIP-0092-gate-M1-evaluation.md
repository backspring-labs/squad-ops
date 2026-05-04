# SIP-0092 Gate M1 → M2 Evaluation

**Status:** Approved — proceed to M2 dev
**Signed:** Jason Ladd
**Date:** 2026-05-04 (revised — initial deferral 2026-05-04 morning, proceed-to-M2 same day after cycles 5–6)
**SIP:** [SIP-0092 — Implementation Plan Improvement](../../sips/accepted/SIP-0092-Implementation-Plan-Improvement.md)
**Plan:** [SIP-0092 Implementation Plan](./SIP-0092-implementation-plan-improvement-plan.md)

## TL;DR

Seven long-cycle group_run cycles in the tracking window. **C3 (the M2-justification criterion) is met conclusively** — the same plan-detectable defect class recurs in 5 of 7 cycles. **C1 and C2 remain structurally unmeasurable** on the current substrate; cycle 6 demonstrated that closing them requires more debugging cycles whose ROI is poor. Cycle 6 also surfaced a finding stronger than C3 alone: even when M1's prompt-engineering produces a defect-free plan (PR #116), the downstream generator (Bob) ignores the typed acceptance_criteria and reproduces the defect anyway. **This is the proposer-judge collapse SIP-0092 §6.1.3 and SIP-0086 §6.1.3 named explicitly, observed under load.**

**Decision: proceed to M2 dev.** The C1/C2 measurement gap is acknowledged and not gating; M2's structured `plan_review.yaml` (per SIP §6.2.2) provides equivalent C2-class signal directly, independent of M1's evaluator instrumentation.

## Tracking window

Seven SIP-0092-tagged cycles on the `validation` profile, all reached the planning-phase gate. Per the gate's inclusion rule, all are in scope.

| # | Cycle ID | Date | Status | Notes |
|---|----------|------|--------|-------|
| 1 | `cyc_11367982fd06` | 2026-05-03 | failed | "M1 gate evidence cycle 1" |
| 2 | `cyc_4178f25a0dff` | 2026-05-03 | failed | "M1→M2 gate-batch cycle" |
| 3 | `cyc_d1c1a259c983` | 2026-05-03 | failed | post PR #104 repair fixes |
| 4a | `cyc_546099e10b7a` | 2026-05-03 | failed | post PRs #104+#105+#106+#108 |
| 4b | `cyc_f05a626ac181` | 2026-05-04 | **completed** | post PR #111 (correction-loop model fix) |
| 5 | `cyc_7febd710e565` | 2026-05-04 | **cancelled at gate** | post PR #113 — exposed PR #113 patched the wrong handler; framing reproduced the qa_handoff defect class; cancelled before implementation to save compute. PR #116 was the real fix. |
| 6 | `cyc_897459e05965` | 2026-05-04 | completed | post PR #116 (PRD coverage discipline in the right handler). Framing produced a clean plan; implementation regressed on the same defect anyway. |

### Exclusions

None. Every cycle reached planning, exercised the relevant SIP-0092 machinery, and produced auditable evidence.

## Per-criterion measurement

### C1 — Typed-acceptance evaluator-error rate < 5%

| Measured | Threshold | Status |
|---|---|---|
| **Structurally unmeasurable** | < 5% per cycle | **Cannot evaluate; not gating M2** |

**Why we can't measure it.** The earlier deferral assumed adding `typed_check_evaluation.json` artifact emission (PR #115) would close C1. PR #115 merged and was deployed; cycle 6 produced **zero** `typed_check_evaluation_*.json` artifacts and zero `typed_acceptance_summary` log lines despite the code being present in the running image (`docker exec squadops-neo` confirms). The instrumentation either isn't fired by the dev tasks' validation dispatch path (`_validate_output` at `cycle_tasks.py:1069` routes to `_validate_focused` only when `subtask_focus is not None`; if the executor isn't passing it, the dev tasks fall through to `_validate_monolithic` which skips typed-check evaluation entirely), or some other condition skips it. Diagnosing further is itself a multi-cycle project.

**Why this no longer blocks M2.** M2's design produces a structured `plan_review.yaml` (per SIP §6.2.2) directly. M2 → M3's gate measures reviewer behavior from that artifact, not from `typed_check_evaluation`. The C1 instrumentation is still desirable for triage but is no longer a precondition for M2.

### C2 — Cycles where typed acceptance changed an outcome

| Measured | Threshold | Status |
|---|---|---|
| **Likely 5 of 7, but unverified** | ≥5 of 10 | **Probable hit; formally unverified; not gating M2** |

**Reasoning.** Across the seven cycles, eight plan_deltas were emitted with `qa_handoff` content failures (cycles 1, 2 third delta, 3, 4b first and second deltas, 6 first delta). Each was a typed-check trip (file existed but missing required content per the plan's `regex_match` checks). Under filename-only validation these would have passed; under M1 they failed and triggered correction.

**Why "unverified".** The plan_delta `trigger` field still records `task_failure:builder.assemble`, not the extended `typed_check_failed:*` shape PR #115 was supposed to introduce. Cycle 6 confirmed the extended shape doesn't fire — `_compose_failure_trigger` correctly falls through to legacy because the `task_index` / `check_index` identity fields don't reach `failure_evidence.validation_result.checks`. Same root cause as C1: the dev/qa validation dispatch isn't going through the path PR #115 instrumented.

**Counter-cycles.** Cycle 2's first two deltas were `development.develop` execution failures (no valid code), not typed-check trips. Cycle 6's second delta was a `tests_pass` synthetic-check failure (pytest exit 5 — discovery issue), not a typed acceptance check.

### C3 — Cycles with planning defect detectable from plan + PRD before build (M2-justification criterion)

| Measured | Threshold | Status |
|---|---|---|
| **5 of 7 cycles show the same plan-detectable defect class** | ≥3 of 10 | **Passed conclusively** |

This is the criterion the gate exists to answer. The evidence is unambiguous and was strengthened (not weakened) by cycle 6.

#### Cycles 1–4: the framing-time defect

The PRD requires `qa_handoff.md` to include `## How to Test` and `## Expected Behavior` sections. The framing-produced `implementation_plan.yaml` task 5 (in those cycles) declared only loose `regex_match` patterns like `"how to run backend|how to run frontend|how to test"` (alternation, count_min: 3) and `"acceptance|validation|duplicate.*name"` — neither of which enforces the section headers. Bob then shipped a `qa_handoff.md` that satisfied the typed checks but violated the PRD; downstream validation caught it; correction fired. Recurred 4 of 5 times.

This is the textbook `acceptance_concern` / `coverage_concern` from M2.2's `plan_review.yaml` schema. A reviewer with read access to PRD + plan, framed by "is the plan's acceptance set sufficient to satisfy the PRD," catches it. Neo authoring alone (M1's combined-author/reviewer model) does not.

#### Cycle 5: the patch-the-wrong-handler discovery

PR #113 attempted to fix the C3 defect class via prompt discipline added to `GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION` in `cycle_tasks.py`. Cycle 5's framing reproduced the defect anyway — the framing flow uses `GovernanceReviewAssessReadinessHandler._produce_manifest` in `planning_tasks.py`, which never sees the `_MANIFEST_PROMPT_EXTENSION`. Cycle 5 was cancelled at the gate to save compute. PR #116 was the real fix (extracted the discipline section to a shared module-level constant, wired into the planning_tasks.py prompt path).

This is C3-positive at a meta level: the gate audit found a defect — wrong-handler patching — that the same audit caught and corrected. M2's structured reviewer would similarly catch coverage and dependency concerns the proposer missed.

#### Cycle 6: the strongest signal — proposer fixes don't transfer to the generator

Cycle 6 ran post-PR-#116. The framing produced an excellent plan: task 4 (builder.assemble producing `qa_handoff.md`) had six explicit `regex_match` typed checks for required section headers (`## How to Run Backend`, `## How to Run Frontend`, `## How to Test`, `## Expected Behavior`, `## Known Limitations`, `## Implemented Scope`), each `severity: error`, `count_min: 1`. Max also produced an audit-trail comment block at the top of the YAML mapping each PRD requirement to its covering check.

**Bob ignored the typed checks and shipped a `qa_handoff.md` missing `## How to Test` and `## Expected Behavior`.** Delta 0's `analysis_summary`:

> "missing the explicitly required sections '## How to Test' and '## Expected Behavior'."

This is **C3 with a stronger interpretation than originally specified**. The original C3 measured "is the defect detectable from plan + PRD?" — Yes, demonstrated 4 of 5 cycles. Cycle 6 demonstrates the deeper failure: even when the proposer (with M1's prompt discipline) writes a defect-free plan, the generator doesn't honor it. The fix mechanism — "give Bob explicit targets via typed checks so he satisfies them" — does not work. The typed acceptance_criteria are downstream-validation data (validator-facing), not upstream-generation guidance (generator-facing). M2's structured reviewer step exists precisely because per-cycle prompt discipline at one position (proposer) doesn't propagate to other positions (judge, generator) without architectural separation.

#### Net C3 reading

5 of 7 cycles (1, 3, 4a, 4b, 6) show the same plan-detectable defect class — 71%, well above the 30% threshold. Cycle 6's evidence (proposer-fixed plan, generator-broken artifact) elevates the verdict from "M2 would catch this kind of plan" to "even M1's best plan-time fix doesn't transfer downstream; the architectural separation M2 introduces is required."

## Honest assessment of the prompt-engineering loop

Between cycles 4b and 6, four PRs went into M1 prompt patches: #111 (correction-loop model resolution, foundational), #113 (PRD coverage — wrong handler), #115 (typed_check_evaluation instrumentation — silent), #116 (PRD coverage — right handler). Approximately 7 hours of GPU spent on validation cycles. Net delta on the qa_handoff defect rate: 4 of 5 → 5 of 7 (i.e., still recurring at the same rate, with cycle 6 isolating the failure mode to the proposer↔generator interface that M1 cannot bridge).

Continuing to iterate on M1 patches (e.g., a PR #117 to inject acceptance_criteria into Bob's generation prompt) is the same pattern: prompt-engineer one position, hope the bug doesn't reappear at another. The M2 design takes that pattern off the critical path.

## Decision

**Proceed to M2 dev.** Concretely:

- Start the M2.1 PR (`development.plan_implementation` handler + shared `PlanAuthoringService`) per the SIP-0092 plan §M2.1.
- Default `split_implementation_planning: false` (per SIP §M2 ship policy). Default-flip is a separate small follow-up after the SIP §6.2.4 metrics bake.
- The C1/C2 instrumentation gap is acknowledged. It is **not** a precondition for M2 because M2 produces its own structured `plan_review.yaml` artifact that provides equivalent reviewer-behavior signal for the M2→M3 gate. The gap remains worth closing for triage and for M2→M3's "Plan-quality regression check" (SIP §6.2.4) but can ship asynchronously.

### What this decision does NOT do

- It does not close the qa_handoff defect class. M2 ships with `split_implementation_planning: false`; the defect will continue to fire at its current rate until the flag flips. The flip happens after M2 default-flip metrics are met (SIP §6.2.4) — separate decision.
- It does not abandon the alternative authoring SIPs (`SIP-Multi-Role-Plan-Authoring`). That comparison happens during M2 design review of the first PR, not in this gate eval.
- It does not commit to M3. The M2 → M3 gate has its own criteria and remains conditional per SIP-0092 plan.

## Open hardening items (non-gating, surfaced by this evaluation)

These are real gaps observed during evaluation but orthogonal to the M1 → M2 gate. None block M2 dev.

- **PR #115 instrumentation didn't fire** — issue to file: investigate `_validate_output` dispatch path; confirm whether dev tasks reach `_validate_focused` or fall through to `_validate_monolithic`. The fix is likely small (executor not passing `subtask_focus` through, or similar) once root cause is found, but is not a productive blocker for M2.
- **Run-contract enforcement against `required_artifacts`** — cycle 4b and cycle 6 both completed as "successful" while missing PRD-required artifacts (`qa_handoff.md` not in registry despite repair tasks being dispatched). Same silent-failure pattern observed across cycles.
- **Builder-side pre-completion check** — Bob declares `assemble` done without verifying that all `expected_artifacts` exist. Same defect class as the qa-side `pytest --collect-only > 0` gap.
- **`run_report.md` correction-loop visibility** — still says "All tasks completed successfully" with zero mention of plan_deltas.

## References

- Cycle artifacts under `data/artifacts/group_run/cyc_*/run_*/art_*/` for the seven cycles listed above.
- `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` — Milestone Gates section defines the criteria measured here.
- Internal memory `project_sip0092_gate_evaluation_approach` — cycle-by-cycle evaluation policy.

## Revision History

- **2026-05-04 morning** — Initial deferral. 5 cycles, C3 qualitatively positive, C1/C2 unmeasurable. Recommended 3–5 more cycles + minimal evaluator instrumentation (later shipped as PR #115) before re-call.
- **2026-05-04 evening (this revision)** — Proceed to M2. Two more cycles in window (5 cancelled at gate, 6 completed). Cycle 6 strengthened C3 with the proposer↔generator-transfer finding; PR #115 confirmed unmeasurable on this substrate; further M1 prompt-patching has poor ROI vs M2's architectural fix.
