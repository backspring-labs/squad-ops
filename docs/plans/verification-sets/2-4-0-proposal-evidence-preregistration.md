# 2.4.0: the proposal shown its outcomes, read live, pre-registered (SIP-0113 §4.5, §10t ruling 9, §10u; #2677)

**Written** 2026-10-22 by the Spark lane, after §10t's six steps were built (#2683, #2686, #2687, #2688, #2689 and
#2690) and before the campaign below is created. It fixes the campaign, the ruling rule, the predictions and how each
is read. **Revised the same day** on a second reader's nine findings, all taken: the places a Release attaches went
unsearched; LangFuse had no reading; the excused places were a column test; there was no positive control, no
baseline, no base rate; and E1 and E2 didn't say which records they read. Nothing here is a suite value: the suite is
named by its digest, goals by id, and the readings count.

## 1. The deploy

- **Built from main** after the step 6 PR merges, by `rebuild_and_deploy.sh all`, and recorded (`record_deploy`).
- **Loaded before launch:** `verify_loaded.py` reads every check, and these six answer as expected: `2677-boundary`,
  `2677-moves-goals`, `2677-role-view`, `2677-reader`, `2677-prompt`, `2677-ledger`.
- **Model:** `full-38-tf`'s `qwen3.8-27b-tf-nvfp4`, served by TensorFold, as the 2.4 window's.
- **Frozen while the campaign runs:** no deploy, no other campaign, no cycle outside it. A defect found mid-campaign is
  filed and fixed after it; a seam defect that voids a reading ends the campaign, and the reading is run again as a new
  campaign on the fixed deploy (§5, E0's budget).

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
proposal task's own revisions inside its run (§9.1). A proposal the rails accept reaches the gate and is approved
there with the note `Approved as proposed.`. A note may reach a later proposal (#2598), so it names neither this
reading nor a goal. The window's rule (the PRD's priority order) isn't used: it would decide whether a goal-aimed
proposal survives, not the evidence. **No ruling reads a scenario.** Plan gates are the tier's, and a plan review the
supervisor is asked for is approved as it stands, with the same note.

## 4. Before launch: the baselines

On the deploy of §1, before the campaign is created, both sweeps run over every place §6 names, over the cycles of
every campaign that pins a suite (15), and their reports are kept in the record's directory. **Taken 2026-10-23 from
02:14Z on `dep_1aa6d6f1c4e0`:**
- **`heldout_sweep.py`, the step values:** 9 of revision 5's 59 markers were already found outside the suite's store,
  spanning 8 of its 31 scenarios. They're in older deliveries and caches, and in every agent image alike. §10r B3's
  public value is among them.
- **`heldout_sweep.py --goals`:** no goal outside the excused places. All 17 goal markers are missing from the
  proposals, as they must be before any proposal is shown them.

**How "new" is read.** A sweep keys its marker ids fresh for each run, so ids don't compare across runs. A marker's
provenance (its scenario and the step or check it's from) does. For E3, a marker whose provenance the baseline found
is known (`baseline-p2-public.json`), and only the other 50 can falsify it. For E4, the baseline found nothing, so any
goal outside the excused places is new.

## 5. The predictions: each names a mechanism and how it is falsified

Read from the campaign's own records after it ends, by id and count. Each counts non-execution beside failure.

**Which records:**
- **A proposal** is the proposal run whose change request the increment gate ruled on: the run that stored it. That
  run's authoring envelope (`seam = proposal_writing`) is what it was shown. A proposal run that failed or was retried
  is counted under E0, never read for E1.
- **An increment's result** is its promoted cycle's evaluation: the increment's own, or the repair or retry that
  was promoted. The family's other cycles, and increments abandoned unpromoted, are reported beside it and never read
  for E2 or E5.

**E0, the evidence reaches the proposal (mechanism, read first).** Each proposal's envelope carries
`inputs["proposal_evidence"]` with goals, and its rendered request carries the goals section. *Falsified by* a proposal
without them. Counted apart, and not a falsification: a proposal shown no goals because the tree it proposed on has no
evaluation by the campaign (the evaluator failed, or is reporting-only and wrote none).
- **Void, and the budget.** The campaign's reading is void if fewer than two of its proposals carried the evidence,
  or a seam defect voided a reading. A void campaign is fixed and run again once, as a second campaign on the fixed
  deploy. At most two campaigns are run, and the record reports how many it took.

**E1, the proposals aim at gaps.** Every proposal shown at least one goal that wasn't passing names at least one goal
in `moves_goals`, and every goal it names was shown `failed` or `not verified`. *Falsified by* such a proposal naming
none, or naming a goal shown `passed`. A proposal shown no goal that wasn't passing is excluded and counted.
`held_back` is reported beside it.

**E2, the named goals move.** Of the goals the promoted increments named, at least half read `moved` in the package's
`named_goals`. `not verified` and `not evaluated` are in the denominator, since a goal that couldn't be read didn't
move, and they're counted apart. *Falsified by* fewer than half.

**E5, the base rate (E2's comparison).** On the same promoted increments, of the goals that weren't passing on the
tree each was built on, the share of the named ones that moved is higher than the share of the unnamed ones that
moved. *Read from* the package's per-cycle scenario results against the tree each was built on. *Falsified by* a
named share at or below the unnamed share. With three increments this is a direction, not a rate: the 2.4 window's
increments all read `contributed` (§10e), so goals move without being named.

**E3, no step value leaks (P2).** `heldout_sweep.py` with revision 5, over the campaign's cycles, finds no marker the
baseline didn't (§4), outside the suite's store and the evaluator's records. *Falsified by* any such marker, or any
place §6 names that couldn't be searched.

**E4, the goals stay on the proposal.** `heldout_sweep.py --goals` finds nothing new against its baseline outside the
excused places. Those are exactly the proposal's authoring envelopes, its LangFuse generations (attributed by the
`task-…` span each hangs under) and the evaluator's records. *Falsified by* any new hit anywhere else, by an
`no_task_span` LangFuse row (one hanging under no task span) the campaign wrote, or by any place that couldn't be searched.
- **Its positive control:** every goal the proposals were shown is found in the excused places
  (`goals_not_found_in_proposals` lists none of them). If any isn't, E4 is void, not held: the sweep didn't find what it
  looks for.

**Counted beside them, with no threshold:** each `unknown_goal` and `goal_text_copied` refusal in the proposal runs,
each `already passing` and `regressed` reading. Also each named goal whose `before` in the package disagrees with
what its proposal was shown. They should agree, since both read the accepted tree's latest evaluation, and a
disagreement is reported as a defect.

## 6. Reading rules

- **The places searched** for E3 and E4:
  - the three databases (`squadops`, `langfuse`, `postgres`);
  - the vault's artifacts for the campaign's cycles, and its `_unattached` ones (where the campaign's package and
    digest are kept);
  - every agent container and the runtime and sandbox services;
  - on the host, the campaign's log archive (`--host-root var/campaigns/<campaign>`), written by
    `campaign_log_archive.py --follow` for the whole campaign.

  A Release attaches the package and the archive.
- **The record** goes to `var/verification_sets/2-4-0-proposal-evidence/`, counts and ids only. Its summary goes to
  #2677 and SIP-0113's next amendment. The delivery ledger's §4.5 row moves to **shipped** with that amendment, whatever
  E1, E2 and E5 read: they measure the mechanism, not whether it is delivered.
- **Small N.** Three increments read a mechanism, not a rate.

## 7. What this doesn't cover

- **No control arm.** Nothing compares proposals shown the evidence with proposals not shown it. E5 compares named
  goals with unnamed ones on the same increments, which isn't the same thing.
- **E1 partly measures instruction-following:** the goals asset tells the proposal that gaps are what an increment can
  close.
- **A copy that isn't word for word** goes uncaught. The rail ignores case and spacing, and the sweep matches exactly,
  so a paraphrased goal in a PRD section reaches every role unrefused and unfound.
- **One stack, one model, three increments.**
- **The PRD's priority order** isn't enforced (§3), so an approved proposal may skip it.
- **Campaign success:** §4.5's results change nothing a campaign decides. That's §4.7's, held by §10s.
