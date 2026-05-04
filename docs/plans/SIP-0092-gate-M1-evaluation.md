# SIP-0092 Gate M1 → M2 Evaluation

**Status:** Deferred (insufficient sample; directional evidence supports M2)
**Signed:** Jason Ladd
**Date:** 2026-05-04
**SIP:** [SIP-0092 — Implementation Plan Improvement](../../sips/accepted/SIP-0092-Implementation-Plan-Improvement.md)
**Plan:** [SIP-0092 Implementation Plan](./SIP-0092-implementation-plan-improvement-plan.md)

## TL;DR

We have **5 long-cycle group_run cycles** in the tracking window against a target of ≥10. The qualitative C3 signal (planning defects detectable from plan + PRD) is **strong and recurring** — the same `qa_handoff.md` acceptance-coverage gap appears in 4 of 5 cycles, and is exactly the defect class M2's structured reviewer is designed to catch. C1 and C2 cannot be measured from current artifacts because evaluator-error and typed-check-trigger events are not surfaced as first-class artifact data.

**Decision: defer M2 dev.** Run 3–5 more cycles on the now-stable substrate (post-PR #111) and add minimal evaluator instrumentation, then re-call. The directional evidence already supports M2; the deferral is about formal sample size and instrumentation, not about doubting the design.

## Tracking window

Five SIP-0092-tagged cycles on the `validation` profile, all reached the planning-phase gate (all framing runs completed and produced an `implementation_plan.yaml`). Per the gate's inclusion rule ("runs that reach planning or build and surface plan, validation, correction, or review behavior count toward the sample even if they ultimately fail to produce a working app"), all five are in scope.

| # | Cycle ID | Date | Status | Implementation Run | Framing | Implementation | Notes |
|---|----------|------|--------|--------------------|---------|----------------|-------|
| 1 | `cyc_11367982fd06` | 2026-05-03 | failed | `run_5e56b2a9aea2` | completed | failed | "M1 gate evidence cycle 1" |
| 2 | `cyc_4178f25a0dff` | 2026-05-03 | failed | `run_d15681138926` | completed | failed | "M1→M2 gate-batch cycle" |
| 3 | `cyc_d1c1a259c983` | 2026-05-03 | failed | `run_271201dc9bcf` | completed | failed | post PR #104 repair fixes |
| 4a | `cyc_546099e10b7a` | 2026-05-03 | failed | `run_6f7b531c8a0c` | completed | failed | post PRs #104+#105+#106+#108 |
| 4b | `cyc_f05a626ac181` | 2026-05-04 | **completed** | `run_bef616da5792` | completed | completed | post PR #111 (correction-loop model fix) |

Cycle 4 was re-run as 4b after PR #111 fixed the correction-loop model resolution bug that had been throttling the correction LLM to the small model. 4b is the first cycle where the correction-decision diagnostics were emitted by the intended `qwen3.6:27b` model.

### Exclusions

None. All five cycles produced planning artifacts and at least one task-level failure with a recorded plan_delta. The implementation-phase failures in cycles 1–4a were caused by squadops framework bugs (correction-loop model resolution, fenced-block parser tolerance, repair-task wiring) — these are squadops-substrate failures, but they are *not* "infrastructure-only failures unrelated to the plan artifact" in the gate's narrow sense (RabbitMQ outage, Postgres down, OOM). They reached planning, exercised the correction protocol, and produced plan_deltas. Excluding them would discard the evidence we actually have about how M1's machinery behaves under load, so we keep them in.

## Per-criterion measurement

### C1 — Typed-acceptance evaluator-error rate < 5%

| Measured | Threshold | Status |
|---|---|---|
| **Unknown — not measurable from current artifacts** | < 5% per cycle | **Cannot evaluate** |

**Why we can't measure it.** The gate criterion is about how often the typed-check evaluator itself errors (vs. legitimately passes/fails a check). The evaluator does not currently emit a per-check log artifact recording `(check_id, file, status ∈ {passed, failed, evaluator_error})`. The closest signal we have is the absence of crash-class failures in the framing runs (all five framings completed cleanly), which is necessary but not sufficient.

**Action implied:** before the next gate-batch cycle, the evaluator should emit a per-cycle `typed_check_evaluation.json` artifact with one row per check evaluated, including a distinguishable `evaluator_error` status. This is a small instrumentation patch (handler-side, no schema change) and would let us tick C1 cleanly. Without it, future gate evaluations also can't measure C1 — this is a structural gap, not a sample-size gap.

### C2 — Cycles where typed acceptance changed an outcome

| Measured | Threshold | Status |
|---|---|---|
| **Likely 4 of 5, but unverified** | ≥5 of 10 | **Probable hit, formally unverified** |

**Reasoning.** Across the five cycles, six plan_deltas were emitted; all were triggered by `task_failure:*` events. Of these, four (cycles 1, 2 third delta, 3, 4b first and second deltas) were `qa_handoff.md` content failures — the file existed but was missing sections required by the implementation_plan's `regex_match` acceptance check. Under filename-only validation these would have passed (file present). Under M1's typed check they failed and triggered correction. By the criterion's plain reading, those qualify.

**Why "unverified".** The plan_delta `trigger` field records `task_failure:builder.assemble`, not `typed_check_failed:<check_id>`. There is no artifact tying the task failure back to which specific typed check from the implementation_plan tripped it. We're inferring the linkage from the analysis prose ("qa_handoff missing required sections") plus the implementation_plan content. The inference is reasonable but not auditable. A future evaluator log (see C1) would solve this in the same patch.

**Counter-cycles.** Two of the six deltas in this window (cycle 2 first and second — `development.develop` execution failures) are clearly not C2 hits. Those were code-generation breakdowns, not typed-check trips.

### C3 — Cycles with planning defect detectable from plan + PRD before build (M2-justification criterion)

| Measured | Threshold | Status |
|---|---|---|
| **4 of 5 cycles show the same recurring acceptance-coverage gap** | ≥3 of 10 mapping to `coverage` / `dependency` / `role` / `acceptance` | **Hit (qualitative); strong directional signal for M2** |

This is the criterion the gate exists to answer. **The evidence is unambiguous.** Four of the five cycles failed in implementation on the same defect, and that defect is visible from the plan + PRD without inspecting build outputs:

#### The recurring defect — `qa_handoff` acceptance coverage gap

The PRD requires the `qa_handoff.md` document to include both **How to Test** and **Expected Behavior** sections (cycle 4b's delta_1 cites this as PRD §10). The framing-produced `implementation_plan.yaml` task 5 declares only:

```yaml
- check: regex_match
  description: "QA handoff covers run and test instructions"
  file: qa_handoff.md
  pattern: "how to run backend|how to run frontend|how to test"
  count_min: 3
- check: regex_match
  description: "Handoff documents acceptance criteria mapping"
  file: qa_handoff.md
  pattern: "acceptance|validation|duplicate.*name"
  count_min: 2
```

Neither check enforces the PRD-mandated "Expected Behavior" section. Bob then ships a `qa_handoff.md` that satisfies the typed checks but violates the PRD; downstream validation (which checks against PRD, not the typed checks) catches it; correction fires. This recurs cycle after cycle.

This is exactly an `acceptance_concern` in M2.2's `plan_review.yaml` schema: a `coverage_concern` between PRD requirements and plan acceptance_criteria, with a concrete `suggested_check` (add a regex_match for "Expected Behavior"). A reviewer with read access to PRD + plan, and the SIP-0086 framing of "is the plan's acceptance set sufficient to satisfy the PRD," catches this. Neo authoring alone (M1's combined-author/reviewer model) does not.

#### Cycle 4b additional defects (plan ↔ run-contract divergence)

In cycle 4b we also observed contract/plan divergences not surfaced by any SIP-0092 mechanism:
- `run_contract.required_artifacts` listed `backend/app.py`; implementation_plan declared `backend/main.py`.
- Contract listed `backend/tests/test_api.py`; plan declared `tests/test_runs.py`.
- Contract listed `qa_handoff.md`, `README.md`, `requirements.txt`, `package.json` as required; the run completed without any of those registered as artifacts.

These are **adjacent** to the M2-justification criterion (they're plan-vs-contract gaps, where the criterion's surface is plan-vs-PRD), so we do not count them toward C3. But they argue strongly that some structured reviewer step is load-bearing — whether against PRD (M2 as written) or against the run_contract (orthogonal hardening item).

#### Cycles where the defect did not appear

Cycle 2 (`cyc_4178f25a0dff`) failed earlier on a `development.develop` execution breakdown ("no valid code was provided for execution"), which is not plan-detectable. Its third delta did surface the qa_handoff defect later in the run, so we include it in the C3 count.

#### Net C3 reading

Five cycles, four with the same plan-detectable acceptance-coverage defect. If this rate holds across five more cycles, C3 lands at ≈8 of 10 — well above the 3/10 threshold. **The qualitative case for M2 is already made; we are deferring on sample-size formality and adjacent instrumentation, not on the underlying signal.**

## Honest assessment — should we ship M2?

The plan-quality defect class M2 is designed to catch is **already biting on the validation profile**, and biting in the same place across cycles. The framing LLM is not catching it (Neo and Max both authoring/reviewing through the same monolithic step), and the correction loop is having to repair it after the fact at a cost of ~30 minutes per repair. Over a 10-cycle window at the current rate, that's roughly 4 cycles × 30 min = 2 hours of compute spent on a class of defect that a structured plan-review step would catch in seconds.

If we ship M2 on this evidence, the worst case is the proposer-judge collapse failure mode (SIP-0092 §6.1.3 / SIP-0086 §6.1.3) materializes — i.e., Max rubber-stamps Neo's plan and we've added a second LLM call for nothing. The M2 → M3 gate explicitly measures that ("≥3 of 10 cycles show structured revision the proposer would not have caught alone"), so the worst case is bounded: we'd discover it during M2 tracking and not advance to M3, and M2 itself would be inert rather than harmful.

If we defer M2 indefinitely, the qa_handoff defect class continues to cost a correction loop per cycle, and the contract↔plan gaps continue to ship as completed runs. Neither is fatal, but neither improves on its own.

## Decision

**Defer M2 dev,** with two parallel actions before re-calling the gate:

1. **Run 3–5 more validation-profile cycles** on the now-stable substrate. Re-call the gate when the tracking window reaches 8–10 cycles. The cycle-by-cycle evaluation policy (see internal memory `project_sip0092_gate_evaluation_approach`) does not require hitting exactly 10, but 5 is too thin to formally call.
2. **Add minimal evaluator instrumentation** before the next batch:
   - Per-cycle `typed_check_evaluation.json` artifact: one row per check, fields `(task_index, check_type, file, status ∈ {passed, failed, evaluator_error}, message)`.
   - Plan_delta `trigger` field extended to optionally reference the failing check (`typed_check_failed:<task_index>:<check_index>`) when the task failure traces back to a typed-check trip.

These two patches close the C1 and C2 measurement gaps for all future gate evaluations (M2 → M3 will need them too), and are <half-day work each.

If both conditions are met and the next batch produces results consistent with the current directional read (C3 continues to fire on plan-detectable defects, C1 evaluator-error rate stays low, C2 typed-check trips are confirmed), then the gate passes and M2 dev starts.

If the next batch is inconsistent — e.g. C3 stops firing because the qa_handoff defect was an artifact of a specific PRD/plan pair rather than a recurring structural issue — then we re-evaluate honestly, possibly spinning M2 out as a separate proposed SIP per the plan's stop-and-re-evaluate default.

## What this evaluation does NOT cover

- **Whether the multi-role authoring alternative** (`SIP-Multi-Role-Plan-Authoring` per gate doc reference) should ship instead of M2. This evaluation only measures whether *some* authoring change is justified; it doesn't compare designs. That comparison should happen as a separate review before M2 dev starts, regardless of the gate decision here.
- **Run-contract enforcement, run_report fidelity, builder/qa pre-completion checks, per-role first-pass success tracking.** These are real gaps observed during this evaluation (especially in cycle 4b) but they are orthogonal to the M1 → M2 gate. Filed as 1.0.x hardening follow-ups.

## References

- Cycle artifacts under `data/artifacts/group_run/cyc_*/run_*/art_*/` for the five cycles listed above.
- Plan_delta excerpts (truncated for this doc) at `/tmp/sip0092_eval/` during evaluation; canonical copies live in the artifact registry.
- `docs/plans/SIP-0092-implementation-plan-improvement-plan.md` — Milestone Gates section defines the criteria measured here.
- Internal memory `project_sip0092_gate_evaluation_approach` — cycle-by-cycle evaluation policy.
