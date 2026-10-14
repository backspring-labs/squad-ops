# 2.3: the plan-review tier's timeout half, read live — pre-registration

**Status:** approved by the owner as written, 2026-10-14, with the three choices in §8. Nothing runs before #2293
and #2295 are merged and deployed (§3).
**Issue:** #2279 (SIP-0109 ledger: "the timeout half, read live", placed 2.3.0). **Plan:** the 2.3 plan, phase 8,
R3's deploy.
**Uncounted.** Both campaigns are diagnostics: their increments declare a fault, so no cycle of theirs counts toward
any set.

## 1. What this reads, and why it needs a fault

SIP-0109 §24bj–§24bm give the plan-review tier a timeout half. Today all five of its parts are read only in unit
tests:
1. **the expiry:** an escalation nobody answers expires at `ruling_bound_s`;
2. **the park:** the expiry cancels the run, and the cycle ends parked;
3. **row 15:** a parked increment is abandoned and the campaign proposes again;
4. **the no-progress stop:** a run of parks ends the campaign at `max_unaccepted_increments` (row 4);
5. **the late answer:** an answer recorded after the expiry is carried into a later increment's baseline, for the same
   question (§24bm), and the tier approves the plan that cites it.

An increment's design never asks a question by itself. Its manifest is the accepted one with a delta applied, and a
delta can't carry a decision (the 2.2.1 plan §2). So the tier reads every increment as quiet, and nothing reaches parts
1–5. The `increment_design_asks` fault (#2280, corrected by #2293) makes the baseline each increment launches on ask one
fixed question: id `injected-open-question`, "should the list of runs be paginated?".

## 2. Why two campaigns

Row 15 launches the next proposal at the moment of the park, and that launch is where §24bm carries late answers into
the baseline. So an answer to increment 1's escalation can't be on record before increment 2 launches. Within one
campaign, every increment would ask unanswered and park, until the no-progress stop. The late answer is read by a
later campaign of the same project. §24bm allows this: "the next campaign for the same project".

- **Campaign A** (`examples/03_group_run/campaigns/2-3-0-tier-timeout-a.yaml`) reads parts 1–4. Nobody answers a plan
  gate. Two increments park, and the no-progress rule ends it.
- **Between them,** the owner's delegate (the supervisor) answers A's first expired escalation late.
- **Campaign B** (`…-b.yaml`) reads part 5. Its first increment launches on a baseline that asks the same question, the
  late answer is carried in, and the tier approves.

Both campaigns use the 2.2 cut shakeout's objective, whose three increments all stayed inside its `allowed_scope`.
That matters for B, because the tier approves only a plan inside the scope.

## 3. The deploy

**R3 + #2293 + #2295,** with the runtime API rebuilt. Both fixes are in the runtime API and the agents are unchanged:
- **#2293** puts the fault where the late answer can reach it;
- **#2295** makes two parks reach a no-progress limit of 2. Without it, the stop takes a third park.

The deploy id, commit and image ids are read from the running containers after the rebuild and recorded on #2279
before campaign A is created. `squad_profile` is `full-38-tf`, and the deploy serves the squad on TensorFold (SIP-0111
§9k). A memory watchdog runs throughout.

**Attempt 1 stopped at A5** (`cmp_62e17d6d4773`, on `dep_7a6cf99f7c11`). A1–A4 held. The expired escalation's cycle
ended `assessed`, not `parked`, because the cycle's end handed the campaign the run as loaded before the gate (#2301).
The owner approved the fix (#2302) and the re-run on 2026-10-14. **The re-run's deploy is this one plus #2302,** with
the runtime API rebuilt and a third loaded-check row showing #2302 loaded. Attempt 1 is aborted before campaign A is
created again. Its readings are on #2279, and nothing else in this pre-registration changes.

**Attempt 2 stopped at A6** (`cmp_391cc2d3cad6`, on `dep_57e39a35bf04`). A1–A5 held: the cycle ended `parked`. But the
parked increment was promoted and met the objective, because its framing run's vacuous `accepted` stood in for the
build it never reached (#2303). The run also carried no reason. The owner approved the fix (#2304) and a third attempt
on 2026-10-14. **Attempt 3's deploy is `dep_c627c2873c3c`, from `8dded804`,** with a fourth loaded-check row showing
#2304 loaded.

**Not run if** main's run for the deployed commit is red, the box isn't idle, or a loaded check fails. Two rows show
the fixes are loaded: the launch applies the fault before the carry, and a park counts at its own decision. They are
added to `scripts/dev/loaded_checks.yaml` with the rebuild.

## 4. What the supervisor does, fixed before launch

- **Increment gates (the proposals, §9.2):** approve each proposal at version 1, as it stands, with the notes "#2279
  diagnostic: approved as proposed; the reading is the plan gate". If the rails refuse a proposal, the runbook's §3
  applies and the refusal is recorded. That is not one of the readings.
- **Campaign A's increment plan gates:** **never decided.** Each must expire.
- **A calibration's plan gate,** in either campaign: if it escalates because its design asks a question of its own,
  decide it within the bound. Approve it, answering each question in the notes with the PRD's reading or "the
  implementer's choice", and record it as an intervention. A calibration that parks ends its campaign (row 2), and the
  reading would be lost.
- **The late answer,** once A has closed: answer A's **first** expired escalation, by its decision id.
  ```bash
  squadops campaigns answer <A> <escalation_id> \
      --answer "injected-open-question=No: the runs list is one page." \
      --reason "#2279: the late answer, for campaign B to carry"
  ```
- **Campaign B's increment plan gate:** never decided by a person. The tier decides it, or it escalates. An escalation
  is a reading; see §5.
- **The memory watchdog and the box:** nothing else runs on the box from A's creation to B's close.

## 5. Predictions

Each one is read from the campaign's control log (`squadops campaigns show/escalations`, the digest), its cycles'
runs and the runtime API's log. A prediction that fails stops the sequence for a read before anything else runs.

**Campaign A:**

| # | prediction | read from |
|---|---|---|
| A1 | the calibration is accepted. Its plan gate passes, or escalates and is decided per §4 | the cycle's verdict; `progress_plan_review`'s decision |
| A2 | increment 1's baseline asks exactly the injected question: its proposal's `baseline_manifest` has one open decision, `injected-open-question` | the launch request's `campaign_proposal` block |
| A3 | its plan gate is not approved by the tier. An `escalation_opened` row names the failed condition `no_open_question` and quotes the injected question | the control log |
| A4 | **the expiry:** an `escalation_closed` row with state `expired`, between `ruling_bound_s` (600 s) and 660 s after the opening. The sweep runs every 60 s | the two rows' times |
| A5 | **the park:** the framing run is cancelled with the reason `escalation_expired`, and the cycle's ending is `parked` | the run; the decision row's `ending` |
| A6 | **row 15:** the decision is row 15, `abandon_and_propose`, guard `proceed`, and increment 2 launches | the decision row; the launch intent |
| A7 | increment 2 repeats A2–A5: asked, escalated, expired, parked | as A2–A5 |
| A8 | **the no-progress stop:** increment 2's decision is row 4, `stop_failure`, cause `unaccepted_increments` | the decision row |
| A9 | the close record and the digest list both escalations as expired and answerable | the digest's Escalations section |

**The late answer:**

| # | prediction | read from |
|---|---|---|
| L1 | the answer is recorded against A's first escalation. The escalation stays `expired` with the answer beside it, and the digest shows it | `squadops campaigns escalations <A>` |

**Campaign B:**

| # | prediction | read from |
|---|---|---|
| B1 | the calibration is accepted (as A1) | as A1 |
| B2 | **the carry:** increment 1's `baseline_manifest` has `injected-open-question` with `choice` "No: the runs list is one page." and a `warrant` naming A's escalation, and no open decision | the launch request's `campaign_proposal` block |
| B3 | **the tier reads it:** the plan gate is approved by `system:plan_review_tier`, and its notes name the carried answer. No escalation opens | the gate decision; the control log |
| B4 | the increment builds. Its verdict is recorded, and is not a reading | the cycle's verdict |

**What a failure would mean:**
- B3 escalating on a condition other than the question (the footprint outside the scope, or a re-rolled framing)
  makes the late-answer reading inconclusive, not falsified. The question's carry (B2) is still read, and the
  escalation's conditions say which.
- B2 failing is the defect #2293 fixed, and stops the sequence.

## 6. Box time

About 2.5–3 hours:
- **Campaign A,** about 1.5 h: a calibration (about 30 min on TensorFold), then two increments, each with its
  proposal, its framing to the gate and the 10-minute bound.
- **Campaign B,** about 1–1.25 h: a calibration and one built increment.

The log archive (`campaign_log_archive.py --follow`) runs beside each campaign.

## 7. Not covered

- **The calibration's own timeout:** a calibration that parks ends its campaign (row 2). §4 decides the calibration's
  gate so the reading isn't lost, so this path is not read.
- **A repair's or a retry's park:** row 15 treats them the same, but no repair or retry is expected to ask.
- **A late answer read within one campaign,** which §2 explains can't happen for an increment's own question.
- **Supervised campaigns,** which carry nothing (§24bm).

## 8. The owner's choices

The owner approved the pre-registration as written on 2026-10-14, which settles these three:

1. Two campaigns (A, then B), as §2 argues, rather than one campaign that reads parts 1–4 only.
2. `ruling_bound_s: 600` and `max_unaccepted_increments: 2`, as the 2.2 cut's tier diagnostic declared.
3. The late answer's text, which is a placeholder for the PRD's reading. The PRD doesn't paginate runs.
