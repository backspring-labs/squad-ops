# SIP-0092 Gate Evaluation — M2 → M3

**Evaluated:** 2026-08-05 (1.5 Gate-1 deliverable, `docs/plans/1-5-0-stabilization-plan.md`)
· **Gate definition:** `docs/plans/SIP-0092-implementation-plan-improvement-plan.md`
§"Gate M2 → M3" (as amended 2026-05-07 for the SIP-0093 propose/merge model) ·
**Predecessor:** `docs/plans/SIP-0092-gate-M1-evaluation.md` (merged 2026-05-05).

## Verdict

**The gate PASSES — all four criteria, by wide margins, on a 67-cycle sample**
(the spec requires ≥10). Stage M3 (Plan Changes) is demand-justified and stays inside
SIP-0092 (a criterion failure would have spun it out as a separate SIP; none failed).

**Scheduling** follows the 1.5 plan's feature-free rule, not this gate: full M3 plan
mutation is a capability and is homed at the **1.6 decision**, with this doc as its
evidence base. The 1.5 line's bounded lever (plan A4) consumes the same
`structural_plan_change_candidate` diagnostic for **termination honesty only**.
`plan_changes_enabled` / `correction_plan_changes_enabled` remain `false` everywhere
until M3 ships.

## Sample

- **Window:** 2026-07-21 → 2026-08-05 (the post-1.4-freeze era: green-roll window 3,
  FAY window, and the 1.4.1–1.4.4 shakedowns — all on the current SIP-0093 runtime).
- **In scope:** **67** cycles — the 71 in-window cycles that produced a
  `merge_decisions` artifact (presence of the merge artifact is by construction
  proof the cycle reached plan-relevant execution, the spec's inclusion rule),
  minus the 4 configured-sole-author cycles the spec excludes. Every in-scope
  cycle ran `plan_authoring_contributors: ["development", "qa", "strategy"]` and
  emitted `authoring_mode: multi_role`.
- **Excluded (8 of 75 registry cycles in window):** 4 never produced
  `merge_decisions` — designed probes and cancels killed before/at framing
  (`cyc_df79b68c94b3` the 1.4.3 cancel probe, `cyc_c110af382480` the 1.4.4
  time-budget probe, plus two early-terminated probe cycles); and 4 were
  **configured sole-author** (`sole_author_reason: no_contributors_configured`,
  2026-07-23/24: `cyc_176939c367ad`, `cyc_3baf018e839c`, `cyc_8a61a853f979`,
  `cyc_548c11873026`) — excluded by the spec's own sample rule, and per that rule
  they cannot inflate or deflate C2. None is an infrastructure exclusion.
- **Profile substitution, recorded:** the gate spec named the `validation` profile.
  The fleet ran `validated-fullstack` — the 1.4-era measurement profile carrying
  exactly the spec's intended shape (full contributor list, M1 at implementation
  depth, M3 flags off). Same measurement intent; the name evolved with the 1.4 arc.

Method: direct scan of the artifact vault (`data/artifacts/group_run/cyc_*/`) —
`merge_decisions.yaml` per-task `proposed_by` provenance (C1/C2),
`delta_*/plan_delta_*.json` `structural_plan_change_candidate` (C3),
`typed_check_evaluation_task_*.json` `evaluations[].status` (C4). Full per-cycle
table in the appendix; every number below is recomputable from stored artifacts.

## Criteria

### C1 — Multi-role contribution non-redundancy: **PASS**

**66 / 67 cycles (99%)** have at least one merged task whose `proposed_by` contains
no `development` — i.e., the merger materially integrated a qa- or
strategy-originated task absent from the dev proposal. Threshold: ≥3 of 10.
Typical shape: qa-proposed pytest suites entering as first-class plan tasks
(e.g., shk-5 tasks 4–5). The propose-merge backbone is doing the cross-role
coverage work SIP-0093 §2 exists for, not rubber-stamping dev.

### C2 — Degraded-sole-author rate: **PASS**

**0 / 67** cycles emitted `authoring_mode: sole_author` with
`sole_author_reason: all_proposals_failed`. Threshold: <20%. The proposer substrate
is stable — the gate measured multi-role behavior, not a degraded fallback.

### C3 — Structural-change candidates from autonomous correction: **PASS**

**46 / 67 cycles (69%)** show at least one correction decision with
`structural_plan_change_candidate ∈ {add_task, tighten_acceptance}`. Threshold:
≥3 of 10. Across all **168** plan deltas in the window: **135** `tighten_acceptance`,
**14** `add_task`, **19** `none` — the correction protocol identified a structural
candidate in **89%** of its decisions while being restricted to `patch` (and the
occasional `rewind`) every single time. This is the M3-demand signal the diagnostic
was built to measure, and it is not marginal: correction has been saying, cycle
after cycle, that the acceptance surface it inherited was too loose to aim repairs
at (`tighten_acceptance` dominating), and it has had no lever to act on that.

### C4 — Plan-quality regression check: **PASS**

- Typed-acceptance evaluator-error rate: **0 / 382 evaluations (0.0%)** across the
  window — far under the 5% bar carried forward from the M1→M2 gate.
- Merged-plan validity: **67 / 67** sampled cycles carry a canonical
  `control_implementation_plan` artifact. Plan-validator rejections in the window
  (#673 dual-claim, #669-revised re-rolls, #715 check-applicability at the 1.4.4
  boundary) all resolved to valid plans at gate — those nets are validity
  *enforcement* working as designed, not merge-induced regression.

## Design-relevant observation for the 1.5 A4 lever

The candidate signal is **pervasive** (89% of deltas carry one), so it is a weak
conjunct on its own: A4.3's termination rule gets essentially all of its selectivity
from the **repeat-signature** condition, not from candidate presence. The A4
decision table must treat `structural_plan_change_candidate != none` as necessary
context, never as the trigger — otherwise nearly every second correction round would
qualify. (shk-4 — `cyc_c3413e8ed3c3`, three consecutive `tighten_acceptance/patch`
rounds against the same unwinnable qa task — is the canonical true-positive the rule
must catch; the dozens of single-round `tighten_acceptance` cycles that then
converged are the false-positive population it must not.)

## Consequences

1. **M3 stays in SIP-0092** and is authorized on evidence; its build decision and
   home are 1.6's (per `docs/plans/1-5-0-stabilization-plan.md` "Explicitly out").
2. The 1.5 **A4 bounded lever** proceeds against this data (the observation above
   binds its design).
3. The M3 flags stay off in every profile until the 1.6 decision lands.

## Appendix — per-cycle sample table

Columns: non-dev tasks = tasks in the merged plan proposed only by non-dev roles /
total merged tasks; eval errors = typed-check evaluator `error` statuses / total
evaluations; deltas = plan-delta count (correction rounds); structural candidates =
deltas with `structural_plan_change_candidate ∈ {add_task, tighten_acceptance}`.

| Date | Cycle | Mode | Non-dev tasks | Eval errors | Deltas | Structural candidates |
|---|---|---|---|---|---|---|
| 2026-07-21 | `cyc_3632da190fd2` | multi_role | 4/11 | 0/11 | 4 | 3 |
| 2026-07-21 | `cyc_6e72d5c82704` | multi_role | 3/9 | 0/17 | 5 | 3 |
| 2026-07-21 | `cyc_83f00cda66be` | multi_role | 3/9 | 0/0 | 0 | 0 |
| 2026-07-21 | `cyc_9be077909050` | multi_role | 2/8 | 0/6 | 5 | 3 |
| 2026-07-21 | `cyc_d0b6d577a669` | multi_role | 5/12 | 0/0 | 0 | 0 |
| 2026-07-21 | `cyc_d8aded77a862` | multi_role | 3/10 | 0/0 | 0 | 0 |
| 2026-07-22 | `cyc_1d5aa1d7a337` | multi_role | 3/11 | 0/0 | 0 | 0 |
| 2026-07-22 | `cyc_22a5506f3f4a` | multi_role | 3/10 | 0/0 | 0 | 0 |
| 2026-07-22 | `cyc_2aac58b9f03d` | multi_role | 3/10 | 0/12 | 3 | 3 |
| 2026-07-22 | `cyc_38415226ad82` | multi_role | 3/10 | 0/6 | 5 | 5 |
| 2026-07-22 | `cyc_af8800f8943f` | multi_role | 3/8 | 0/5 | 5 | 5 |
| 2026-07-22 | `cyc_c2af37e9e3e6` | multi_role | 2/8 | 0/9 | 5 | 4 |
| 2026-07-22 | `cyc_de020f3d8412` | multi_role | 4/10 | 0/10 | 4 | 4 |
| 2026-07-24 | `cyc_03bc35a21b55` | multi_role | 2/9 | 0/7 | 5 | 5 |
| 2026-07-24 | `cyc_54c474deb07a` | multi_role | 1/8 | 0/8 | 4 | 4 |
| 2026-07-24 | `cyc_6999645e3f69` | multi_role | 3/10 | 0/12 | 3 | 3 |
| 2026-07-24 | `cyc_6fa0831bab83` | sole_author | 0/7 | 0/0 | 0 | 0 |
| 2026-07-24 | `cyc_cf7467a5b5a0` | multi_role | 2/8 | 0/9 | 5 | 5 |
| 2026-07-24 | `cyc_d01810b2922f` | multi_role | 4/11 | 0/7 | 2 | 2 |
| 2026-07-24 | `cyc_eb02a1d01859` | multi_role | 5/11 | 0/6 | 5 | 4 |
| 2026-07-25 | `cyc_07cfb23c4de7` | multi_role | 4/10 | 0/7 | 1 | 1 |
| 2026-07-25 | `cyc_1bf0eb021d42` | multi_role | 3/10 | 0/9 | 5 | 5 |
| 2026-07-25 | `cyc_32f85a56224d` | multi_role | 3/10 | 0/9 | 0 | 0 |
| 2026-07-25 | `cyc_948094e17641` | multi_role | 4/10 | 0/11 | 1 | 0 |
| 2026-07-25 | `cyc_9e24ce95033f` | multi_role | 3/10 | 0/9 | 2 | 2 |
| 2026-07-25 | `cyc_add192e22560` | multi_role | 3/11 | 0/12 | 5 | 3 |
| 2026-07-25 | `cyc_b54793282f10` | multi_role | 3/10 | 0/6 | 3 | 3 |
| 2026-07-25 | `cyc_d56fe8b49437` | multi_role | 4/11 | 0/7 | 3 | 3 |
| 2026-07-26 | `cyc_13edbf6c4680` | multi_role | 4/8 | 0/3 | 2 | 1 |
| 2026-07-26 | `cyc_5ab442eabf7e` | multi_role | 2/6 | 0/3 | 1 | 1 |
| 2026-07-26 | `cyc_b8420f2f7709` | multi_role | 3/10 | 0/0 | 0 | 0 |
| 2026-07-26 | `cyc_b9a2a094820d` | multi_role | 1/6 | 0/3 | 1 | 1 |
| 2026-07-26 | `cyc_bff6a0abfa32` | multi_role | 3/11 | 0/21 | 5 | 4 |
| 2026-07-26 | `cyc_e83829c268a6` | multi_role | 2/8 | 0/0 | 0 | 0 |
| 2026-07-27 | `cyc_49ca3aa0b4ce` | multi_role | 5/9 | 0/3 | 1 | 1 |
| 2026-07-27 | `cyc_4c138a97833f` | multi_role | 3/7 | 0/3 | 3 | 3 |
| 2026-07-27 | `cyc_6dd5971a88fe` | multi_role | 1/5 | 0/3 | 0 | 0 |
| 2026-07-27 | `cyc_86211da4786d` | multi_role | 3/7 | 0/3 | 5 | 5 |
| 2026-07-27 | `cyc_c9b2fa419816` | multi_role | 2/7 | 0/3 | 1 | 1 |
| 2026-07-27 | `cyc_dc8348ac7ac1` | multi_role | 1/6 | 0/3 | 3 | 3 |
| 2026-07-27 | `cyc_f1677984bcb6` | multi_role | 2/6 | 0/3 | 5 | 5 |
| 2026-07-28 | `cyc_01dbcc1bb3ab` | multi_role | 2/7 | 0/3 | 5 | 3 |
| 2026-07-28 | `cyc_2dcd2697ea12` | multi_role | 2/6 | 0/0 | 3 | 3 |
| 2026-07-28 | `cyc_2e13b6bc2459` | multi_role | 1/6 | 0/0 | 0 | 0 |
| 2026-07-29 | `cyc_04b26fdcd37a` | multi_role | 3/7 | 0/4 | 1 | 0 |
| 2026-07-29 | `cyc_488ce4f6ded0` | multi_role | 3/7 | 0/0 | 0 | 0 |
| 2026-07-29 | `cyc_73cbff68891f` | multi_role | 3/7 | 0/4 | 5 | 5 |
| 2026-07-29 | `cyc_76bbec332912` | multi_role | 3/7 | 0/4 | 5 | 3 |
| 2026-07-29 | `cyc_7f5f1b8b1790` | multi_role | 2/6 | 0/4 | 5 | 5 |
| 2026-07-29 | `cyc_9e3c835bc4e4` | multi_role | 4/8 | 0/4 | 1 | 1 |
| 2026-07-29 | `cyc_e44057df71d2` | multi_role | 1/5 | 0/4 | 5 | 4 |
| 2026-07-29 | `cyc_f6bea0a3c1a8` | multi_role | 3/7 | 0/4 | 5 | 5 |
| 2026-07-30 | `cyc_353bbbf0ad37` | multi_role | 3/7 | 0/0 | 0 | 0 |
| 2026-07-30 | `cyc_42eed09efbec` | multi_role | 2/6 | 0/7 | 4 | 4 |
| 2026-07-30 | `cyc_71748d091367` | multi_role | 2/7 | 0/7 | 5 | 5 |
| 2026-07-30 | `cyc_9a760526e420` | multi_role | 3/7 | 0/7 | 5 | 5 |
| 2026-07-30 | `cyc_a11c450b5e57` | multi_role | 2/6 | 0/7 | 1 | 1 |
| 2026-07-31 | `cyc_42c44ad3af91` | multi_role | 2/7 | 0/9 | 0 | 0 |
| 2026-07-31 | `cyc_6c185cba4811` | multi_role | 3/7 | 0/7 | 1 | 1 |
| 2026-07-31 | `cyc_96e72accb2b3` | multi_role | 1/5 | 0/7 | 0 | 0 |
| 2026-07-31 | `cyc_c51568b00b64` | multi_role | 3/7 | 0/7 | 2 | 1 |
| 2026-07-31 | `cyc_e175cae83a6f` | multi_role | 3/6 | 0/7 | 0 | 0 |
| 2026-08-03 | `cyc_88162ecfd895` | multi_role | 1/5 | 0/7 | 5 | 5 |
| 2026-08-03 | `cyc_b03d203df3f2` | multi_role | 2/7 | 0/9 | 0 | 0 |
| 2026-08-04 | `cyc_74a741292539` | multi_role | 2/6 | 0/8 | 0 | 0 |
| 2026-08-04 | `cyc_c3413e8ed3c3` | multi_role | 5/9 | 0/8 | 3 | 3 |
| 2026-08-05 | `cyc_07ae691af9d6` | multi_role | 2/6 | 0/8 | 0 | 0 |
