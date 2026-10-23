# 2.4.0: the proposal shown its outcomes, read live, pre-registered (SIP-0113 §4.5, §10t ruling 9, §10u; #2677)

**Written** 2026-10-22 by the Spark lane, after §10t's six steps were built (#2683, #2686, #2687, #2688, #2689 and
the step 6 PR) and before the campaign below is created. It fixes the campaign, the ruling rule, the predictions and
how each is read. Nothing here is a suite value: the suite is named by its digest, goals by id, and the readings count.

## 1. The deploy

- **Built from main** after the step 6 PR merges, by `rebuild_and_deploy.sh all`, and recorded (`record_deploy`).
- **Loaded before launch:** `verify_loaded.py` reads every check, and these six answer as expected: `2677-boundary`,
  `2677-moves-goals`, `2677-role-view`, `2677-reader`, `2677-prompt`, `2677-ledger`.
- **Model:** `full-38-tf`'s `qwen3.8-27b-tf-nvfp4`, served by TensorFold, as the 2.4 window's.
- **Frozen while the campaign runs:** no deploy, no other campaign, no cycle outside it. A defect found mid-campaign is
  filed and fixed after it; a seam defect that voids a reading ends the campaign, and the reading is run again as a new
  campaign on the fixed deploy (§5).

## 2. The campaign

- `examples/03_group_run/campaigns/2-4-0-proposal-evidence-fastapi-react.yaml`: `group_run` toward its PRD's
  expansion scope, three increments, FastAPI + React, work class `tier-1`, `unattended`, `full-38-tf`, `plan_gate:
  tier`, the 2.4 window's FastAPI policy unchanged.
- **The suite pinned:** revision 5, `92a26ad0…` (approved 2026-10-22, SIP-0113 §10r).
- **One stack, one campaign.** §10t ruling 9 asks for one; a second stack is not run.
- **Its launches resolve to the window's frozen config hashes** (`test_the_windows_launches_resolve_to_the_hashes_main_recorded`),
  so its calibration and repairs are configured as the window's were.

## 3. The ruling rule

**Every proposal is approved as it stands, at version 1, unless the rails refused it.** The rails' refusals are the
proposal task's own revisions inside its run (§9.1); a proposal the rails accept reaches the gate and is approved
there with the note `§4.5 reading: approved as proposed`. The window's rule (the PRD's priority order) is not used: it
would decide whether a goal-aimed proposal survives, not the evidence. **No ruling note quotes a goal**, and none reads
a scenario. Plan gates are the tier's.

## 4. The predictions: each names a mechanism and how it is falsified

Read from the campaign's own records after it ends. Each counts non-execution beside failure: a proposal run that
failed, an increment never evaluated, a goal `not verified` or `not evaluated`.

- **E0, the evidence reaches the proposal (mechanism, read first).** Every increment's proposal task carries
  `inputs["proposal_evidence"]` with goals, and its rendered request carries the goals section. *Read from* each
  proposal's authoring envelope (`seam = proposal_writing`), by counts. *Falsified by* any proposal task without it.
  If E0 fails, E1 and E2 are not read: the reading is void, not a result.
- **E1, the proposals aim at gaps.** Every proposal after the calibration names at least one goal in `moves_goals`,
  and every goal it names was not passing (`failed` or `not verified`) in the evidence it was shown. *Read from* each
  version 1 change request and the same task's envelope, by id. *Falsified by* a proposal naming none, or naming a goal
  shown `passed`.
- **E2, the named goals move.** Of the goals named by accepted increments, at least half read `moved` in the package's
  `named_goals`. *Falsified by* fewer than half. `not verified` and `not evaluated` are counted apart and are in the
  denominator: a goal that couldn't be read did not move.
- **E3, no step value leaks (P2, unchanged).** `heldout_sweep.py` with revision 5 finds no marker outside the suite's
  own store and the evaluator's records, over the campaign's cycles. *Falsified by* any found or unsearched place.
- **E4, the goals stay on the proposal.** `heldout_sweep.py --goals` finds no goal statement outside the proposal
  task's rows and the evaluator's records, and each LangFuse row it reports (`langfuse_unattributed`) belongs to a
  proposal generation, read by trace. *Falsified by* any other place, or a LangFuse row of another task.

**Counted beside them, with no threshold:** each `unknown_goal` and `goal_text_copied` refusal inside the proposal
runs, and each `already passing` and `regressed` reading.

## 5. Reading rules

- **The record** goes to `var/verification_sets/2-4-0-proposal-evidence/` (counts and ids only), and its summary to
  #2677 and SIP-0113's next amendment. The delivery ledger's §4.5 row moves to **shipped** with that amendment, whatever
  E1 and E2 read: the predictions measure the mechanism, not whether it is delivered.
- **The exit rule:** the campaign's run counts if E0 holds and no seam defect voided a reading. A seam defect found
  ends the campaign; it is fixed and the reading runs again as a new campaign. The record reports how many runs that
  took.
- **Small N.** Three increments read a mechanism, not a rate. E2's half is a direction, and a reading of one or two
  named goals says so.

## 6. What this doesn't cover

- **No control arm.** Nothing here compares proposals shown the evidence with proposals not shown it. E1 and E2 say
  whether the mechanism works as built, not how much it adds.
- **One stack, one model, three increments.**
- **The PRD's priority order** is not enforced (§3), so an approved proposal may skip it.
- **Campaign success:** §4.5's results change nothing a campaign decides. That's §4.7's, held by §10s.
