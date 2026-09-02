---
sip_uid: '17883224960413168'
status: proposed
title: Post-Retest Governance Acceptance Review
---
# SIP: Post-Retest Governance Acceptance Review

## Status

**Proposed** (draft, 2026-08-07). Elaborates #557 (direction marker, deliberately
post-green) into a SIP per its own instruction; companion to #556
(`qa.validate_repair` removal), which vacated the slot this fills. Amends the
SIP-0079 §7.7 correction protocol. Target: 1.6+ acceptance decision — explicitly
**not** 1.5 (feature-free stabilization).

## Why now (the trigger, honestly stated)

#557's pickup condition was two-part: the evidence pipeline must surface real
behavioral truth, and measurement must show the false-green class earning the
step its tokens.

1. **The evidence prerequisite is met.** The 1.5 A3 pair landed it: #687
   (probe-runner spool-delta traceback capture + `build_failure_evidence`
   hoisting `app_tracebacks`) and #431 (emission accounting, extraction-loss
   classification) — plus the failure-evidence taxonomy
   (`FailureEvidenceCategory` ×7), deterministic locus classification (#568),
   and #734's workspace-revision provenance (every acceptance verdict now names
   the tree it ran against). A post-retest reviewer would today receive
   structured behavioral evidence the removed step never had.
2. **The false-green class is observed, not hypothetical.** The 1.4 arc's
   canonical lesson ("cycle `completed` ≠ deliverable works"), pf-54's
   five-version suite loop asserting statuses the contract contradicted (now
   deterministically closed by #629 — but only for *status* assertions), and
   the green-roll baseline's loss modes (#627/#628/#629) all sit in the
   "deterministic green, behavioral doubt" band this review exists for.

## Motivation (from #557, preserved)

The removed `qa.validate_repair` step had the right instinct — an LLM look at
the finished repair — executed in the wrong place with the wrong evidence and no
consumer: it ran *before* the retest, desk-reviewing a diff with no execution
results, and its verdict was discarded. Meanwhile the correction loop's known
judgment failures are evidence problems (#431 diagnosis-blindness; the ApiError
misdiagnosis). If LLM judgment returns to this loop, it must be positioned where
it has the best evidence and bounded so it cannot recreate the #374/#376
false-green class.

## Design (the five principles, now anchored to current code)

1. **Post-retest placement.** The review runs after patch verification
   (`verify_patched_artifacts`, #389) and the behavioral retest
   (`reexecute_repaired_suite`, #456), consuming their outputs — never before.
   Concretely: a new protocol step inside the executor's `_try_accept_patch`
   accept path, after `retest_passed` and before the #389 swap.
2. **Governance role, not qa.** Reviewer ≠ approver: qa produces evidence; the
   accept/reject call belongs to the lead role, which already owns
   `governance.correction_decision`. New task type
   `governance.review_repair_acceptance` (lead), registered like every
   correction-protocol step.
3. **Fail-closed authority.** The review may REJECT or FLAG a deterministic
   green; it may NEVER approve past a deterministic red. Deterministic signals
   stay necessary conditions — the LLM only adds skepticism. Mechanically: the
   step is only dispatched when patch verification AND retest are green; its
   verdict can demote, never promote.
4. **Evidence-first prompting.** Inputs (all existing surfaces): the retest's
   behavioral output (`test_result`, tracebacks via #687), the repair diff, the
   frozen interface contract surfaces, the original acceptance criteria, and
   the workspace revision ids (#734) naming exactly which tree each verdict
   measured. Prompt prose lives in a managed asset (CLAUDE.md #448); Python
   renders data only.
5. **Consumed or absent.** REJECT → the acceptance falls back to "continue"
   (re-dispatch / next correction attempt) with the review's named gap injected
   into `failure_evidence` — the same authoritative-evidence transport the
   deterministic injectors use. FLAG → recorded on the run verdict as an
   unverified-class disclosure (SIP-0096 vocabulary), surfaced by the roll-up.
   If a consumer is not built, its verdict class is not built.

## Governance metadata

The review consumes the #730 registry's vocabulary where it reasons about
checks (`failure_ownership` to aim skepticism; `replayable` to know which
evidence re-verifies). Its own dispositions are protocol records, not typed
checks — it adds no `CHECK_SPECS` entry.

## Verification story (before any acceptance)

- **Designed false-green probe**: a fixture repair whose suite passes by
  construction while the behavior contradicts the contract (the stub-test
  shape) — the review must FLAG or REJECT it.
- **No-false-authority probe**: a deterministic red with a persuasive diff —
  the review's verdict must be unable to accept it (enforced by dispatch
  position, tested at the seam).
- **Token cost measured** against the correction budget it spends from (#511's
  budget guard applies to the step like every dispatch).

## Salvage

The per-artifact / per-criterion / name-the-remaining-gap rubric from
`request.cycle_validate_repair.md` (removed by #556; retrieve from git history
at the removal PR's parent) seeds the review prompt — the richest rubric the
correction chain ever had, previously wired to nothing.

## Non-goals

- No change to deterministic acceptance (patch verification, retest, typed
  checks) — the review is additive skepticism above them.
- No qa-role authority change; no revival of pre-retest desk review.
- No Phase-2-style scoring/memory: one step, one verdict, wired consumers.
