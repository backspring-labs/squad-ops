# SIP Promotion Audit — 2026-08-03 (pre-1.4.1)

Requested by the Mac lane before the 1.4.1 cut, flagged in the post-1.4 roadmap
reconciliation record ("Not moved by this record" — lands with PR #681). Each SIP
audited against its full accepted spec text, every commitment verified in code.
**Outcome: zero promotions — all four stay accepted, each with named gaps.** No
force-promotions; honest stays-accepted is the recorded result.

| SIP | Verdict | One-line reason |
|---|---|---|
| **SIP-0096** Verification Evidence Integrity | **stays accepted** | Core invariant/choke-point/`CycleOutcome`/persistence shipped and live-proven, but 4 normative items open: gate-waiver (#682), wrap-up consumer (#683), §9 inert detection (#684), §8 pulse SKIP-only amendment (#423) — and the SIP binds acceptance to all phases. |
| **SIP-0092** Implementation Plan Improvement | **stays accepted** | M1 fully landed (with recorded deltas); M2 partial (the SIP-0093-delegated 93.4 layer unshipped); **M3 is 100% unimplemented** (~18 deliverables, zero code/config/tests) and its M2→M3 gate-evaluation doc was never written. |
| **SIP-0093** Multi-Role Plan Authoring | **stays accepted** | Runtime path (brief → proposers → merge → sign-off) complete and well-tested incl. the required "Eve proposes what Neo omitted" test, but PR 93.4 (gate package, telemetry, console) never started, §5.8 merge rules 2/3/4/5 unimplemented, two §10 required tests absent. |
| **SIP-0088** Agent Runtime Modes (umbrella) | **stays accepted** | Only 1 of 3 implementing children promoted (0089); embodiment is Phase 1-of-4 under still-accepted 0090 and duty durability (0091) has zero code — both now 1.6-targeted; the umbrella cannot complete before its children. |

## SIP-0096 — exact remaining (gates the 1.8 scorecard; slices are 1.5-hardening-shaped)

Normative:
1. **#682** gate-waiver slice — §6.5/AC#12. Only the `WaivedCheck` shape exists
   (`verification_integrity.py:248-260`); no `GateDecision` fields, migration, API, or
   `CycleOutcome.waived` population.
2. **#683** wrap-up consumer — §10/§14. `CycleOutcome` has one consumer repo-wide (the
   cycle-detail GET); `wrapup_tasks.py` never reads it; `ConfidenceClassification`
   remains LLM-prose-derived.
3. **#684** §9 inert detection — AC#10 second half. Non-executable half landed (doctor
   `verification` category + preflight parity); the N-consecutive-cycles counter,
   stable-identity store, and reset logic don't exist; `CycleOutcome.inert` is
   permanently empty.
4. **#423** §8 pulse SKIP-only→PASS amendment — `pulse_verification.py:250-269`
   unchanged; pulse never reaches the choke point.

Secondary (clean-AC sweep): provenance producers never populate
`executed_at`/`duration_ms`/`subject_ref`/`executor_ref` (exit_code only, AC#9); AC#4
narrative-override injection test absent; AC#11 architecture test on `CycleOutcome`
construction paths absent. Hygiene: **#114's code landed** (typed_check_evaluation.json
emitted from dev/qa/builder incl. failing rows, with tests) — the issue should close.

## SIP-0092 — exact remaining

- **M3 (entire milestone, ~18 deliverables):** `plan_change.py`
  (schema/ops/`unsupported_operation_in_rev_1`), pure `apply_plan_changes` + plan
  hashing + chain validation, `validate_plan_change_for_run`, loader integration
  (RC-20/RC-21), `CONTROL_IMPLEMENTATION_PLAN_CHANGE` artifact type + forwarding,
  change-created task provenance, `decision: plan_change` producer, three config keys +
  startup misconfig rejection, full test matrix. Precondition unmet: the M2→M3
  gate-evaluation doc (`SIP-0092-gate-M2-evaluation.md`, expected under docs/plans/)
  was never written.
- **M2 (§6.2 commitments riding SIP-0093's 93.4):** gate-package artifact split,
  degraded-sole-author warning surfaced at gate/console (text is built but zero
  `sole_author` hits in `api/`/`console/`), discrete `failure_reasons` field, RC-27
  guard test, SIP-0093 promotion itself.
- **M1 deltas (fix-in-place or amend spec text):** `command_check_safelist` declared
  but never read (safelist hardcoded); `command_exit_zero` uses subprocess directly,
  not the ACI executor; out-of-safelist → `error` vs spec's `skipped`; file-missing →
  `failed` vs spec's `skipped` (8 sites); `regex_match` narrowed to documents (#464)
  invalidating the SIP's own §7 example; param-name drift
  (`symbol`/`class_name`/`min_count`/`argv`/`timeout_s`); QA output-validation path
  exempted from typed acceptance (`qa_test.py:83-87`).
- Sanctioned alternative (plan doc `:547`): spin M3 out as a separate proposed SIP →
  0092 promotable on M1+M2 once the M2 items close.

## SIP-0093 — exact remaining

- **PR 93.4 (never started):** gate-package primary/intermediate split in
  `api/routes/cycles/runs.py`; degraded-sole-author operator warning rendering (+ 
  suppression for `no_contributors_configured`); authoring/proposal/merge telemetry
  (the 0092 M2→M3 gate's C1/C2 depend on it); console hooks + degraded banner.
- **Merge machinery:** §5.8 rule 2 (cross-role criteria merge), rule 3
  (strictest-compatible-wins comparator), rule 4 (`rejected_tasks` flat list — dropped
  proposals are currently only `logger.info`'d), rule 5 (scope/dependency/acceptance
  conflicts should block gate, currently advisory prose); `merge_action:
  merged/modified` defined but unreachable.
- **Required tests:** `test_merge_plan_sole_author.py` (nothing exercises
  `_handle_sole_author`), `test_gate_package.py`, plan-authoring metrics test,
  compatible-criteria-survive-merge test.
- **Config/spec reconciliation:** §7 default `["development","qa","strategy"]` vs
  fleet reality `[]` (only `validation-multirole.yaml` sets it) — set it on the
  intended profiles or amend §7; fold the sequential-fan-out amendment into the SIP
  body (§5.11/§6 still claim parallel); field-name drift
  (`focus_key`/`depends_on_focus`/`source_proposal_task_keys`).

## SIP-0088 — why it stays (one line, as requested)

SIP-0088 stays accepted — only 1 of its 3 implementing SIPs is promoted (0089);
embodiment criterion 5 sits at Phase 1-of-4 under still-accepted SIP-0090 and
duty-durability criterion 6 has zero code, both now targeted at 1.6, so the umbrella
cannot be complete before its children.

## Drift fixed in this PR (found during audit)

- SIP-0091 `**Targets:**` said v1.4; SIP-0090 said "Phases 2+ target v1.4+"; SIP-0096
  said "v1.4 … alongside SIP-0091" — all stale vs ROADMAP/evidence-arc (0090 P2 + 0091
  → 1.6; 0096 remaining slices → 1.5 hardening, must implement before the 1.8
  scorecard). Headers updated.
- ROADMAP "Accepted (Next Up)" rows for the four audited SIPs updated with verdicts +
  remaining-item pointers.

## Promotion-mechanics notes (for the next audit run)

`update_sip_status.py` only rewrites `**Status:**` lines — 0092/0093/0088 use the old
bold-line form (no `## Status` section; 0096 has both), and promotion should also
convert the body to the `## Status` + `**Targets:**` convention (SIP-0098/0099/0100
precedent) by hand. A promotion moves the file `accepted/ → implemented/`; live
references to the accepted paths exist in `SIP-Campaign-Orchestration.md`,
`SIP-Cycle-Evaluation-Scorecard.md`, `SIP-Campaign-Self-Improvement-*.md`,
`2-0-roadmap-reconciliation.md`, and the ROADMAP — repoint in the same PR or the #336
docs-path guard fails.
