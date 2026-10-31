# 2.5.0 — pre-registration of phase 3's uncounted Campaign: #2578's increment records, read on the deploy (Track D)

**Status: REGISTERED 2026-10-28, before the campaign is created. RUN and READ the same day (§7): R1–R4 hold, and the
campaign ended `success`. One seam finding outside #2578's records was fixed during the run (#2754).** Uncounted. It reads machinery, and no release claim
rests on its verdicts.

## 1. Why it runs

The 2.5 plan's §3, item 3: #2578's migration changes the campaign cycle records the demonstrations exercise. So it lands
on its own deploy, read by one uncounted sample-application Campaign, before anything counts on it.
- **#2578 is merged:** parts 1–4, SIP-0109 §24ca, §24cf and §24cg.
- **The Track C run-path fixes landed first,** as the plan's revision of 2026-10-27 orders: #2664 (#2746), #2743
  (#2748) and #2602 (#2749).
- **#2253's outcome changes no path yet.** Its second check proposes or doesn't, and a proposal goes through a plan
  row of its own.
- **#1469 stays blocked on its corpus** (#1469, 2026-10-28).

## 2. The deploy and the campaign

- **The deploy:** the night's deploy from main's tip, after #2749 merges (`rebuild_and_deploy.sh all`, then
  `verify_loaded.py` with 0 not loaded). Its `dep_…` id and commit are recorded in §6 when read.
- **The definition:** `examples/03_group_run/campaigns/2-5-0-track-d-uncounted.yaml`. It is the 2.4 cut shakeout's
  policy with revision 6 of the held-out suite pinned (`89bffc19…`, approved 2026-10-24, its validation held).
  - two increments on FastAPI + React;
  - `max_cycles` 7, one repair or retry each;
  - plan gates `tier`;
  - evaluation at each cycle's end, reporting only.
- **Rulings:**
  - **Proposals are the supervisor's,** under the owner's grant of 2026-10-28. Each is approved as it stands unless
    the rails refuse it.
  - **A plan gate the tier escalates** is answered by the supervisor from the PRD.

## 3. The readings, each with what falsifies it

From §24cf and §24cg. Each is read from the stored records after the campaign closes, or as each cycle ends.

1. **R1. Every cycle the campaign launches names its increment, and only its launcher sets it:**
   - the calibration carries no `increment_id`;
   - each increment's `increment_id` is its proposal id, the one its launch's `campaign_proposal` block names in the
     control log;
   - a repair or retry carries its increment's id;
   - a re-proposal carries a new one.

   It is read from `cycle_registry.increment_id` against the control log's launch rows. **It is falsified by** any
   cycle whose id differs from the one its own launch names, or a calibration carrying one. A repair, retry or
   re-proposal the campaign never launches is reported *not exercised*, never *passed*.
2. **R2. Each flow run says which increment and which kind:** Prefect's flow runs carry `kind:<kind>` and, for every
   cycle but the calibration, `increment:<id>`, equal to R1's id. **It is falsified by** a missing or different tag
   on a launched cycle's flow run.
3. **R3. The ledger lists each version's cycles, and the last one's end is its outcome**
   (`squadops campaigns ledger <id>`):
   - each proposal version lists its cycles in launch order, each with its kind;
   - the version's `outcome` is its last cycle's deciding row.

   **It is falsified by** a version whose cycles are missing, out of order or attached to another version, or an
   outcome that is not its last cycle's.
4. **R4. Nothing reads a tag to decide.** No campaign decision row cites a Prefect tag. **It is falsified by** a
   decision that differs from its §10 row's reading of the cycle's verdict.

**Read beside them, without a prediction:**
- the campaign's ending and each cycle's verdict;
- the cycle-end evaluations on revision 6, reported only;
- whether #2664's `slot_subject_dropped` or #2743's namespace rule fired. With scope `backend/**` and `frontend/**`,
  #2743 is not expected to change any verdict here.

## 4. The stop rule

A seam finding in #2578's records, meaning any of R1–R4 falsified, stops the reading:
- the campaign is paused at its next decision;
- the finding is filed with its evidence;
- nothing counts on these records until a fix is read on a further campaign.

A finding elsewhere, in the squad's output or the evaluator, is filed and the campaign continues, since this read is
about the records.

## 5. What it does not cover

- **Next.js.** One stack, as Track D's plan row asks. The demonstrations run their own.
- **Any verdict's quality.** Revision 6's evaluations are reported only. The re-read on the new yardstick waits for
  #2724 and `-7` (phase 2).

## 6. The record

The campaign id, the deploy, each reading's result with its evidence and the stop rule's outcome are appended here
as §7 when read. The outputs, the log windows (`campaign_log_archive.py --follow`) and the reading's queries, go to
`var/campaigns/<campaign_id>/`.

## 7. The reading, 2026-10-28

**The campaign:** `cmp_9c9df268084a`, created 06:46Z on deploy `dep_fbeecffcc625` (main `4ed8d399`, `verify_loaded`
192 of 192). It ended at 09:39Z `completed`, outcome **`success`**, with two increments accepted of two, in 6 of its 7
cycles. The records are in `var/campaigns/cmp_9c9df268084a/`:
- `launches.jsonl` (each launch intent with its cycle);
- `flowruns.json` (Prefect's flow runs);
- `ledger.json` (`GET /api/v1/campaigns/{id}/ledger`);
- `rulings/` (each approved change request);
- the log windows.

**The cycles, in launch order:**

| cycle | kind | `increment_id` | its decision |
|---|---|---|---|
| `cyc_4767164fc2e1` | calibration | none | row 5, accepted (27 files) |
| `cyc_74e1743ae252` | increment | `prop_e900bbf73973` | row 8, `blocked_unverified`, repair |
| `cyc_8422716e6ae1` | repair | `prop_e900bbf73973` | row 9, `blocked_unverified`, escalate |
| `cyc_673996f766e4` | retry | `prop_e900bbf73973` | row 7, accepted (33 files) |
| `cyc_8459b76f9ab0` | increment | `prop_b9579a99644c` | row 16, rejected, `abandon_and_propose` |
| `cyc_b4c6bdd7093c` | increment | `prop_f55daca31572` | row 3, accepted (34 files), `stop_success` |

### 7.1 The readings (§3)

- **R1 holds, 6 of 6.** Each cycle's `cycle_registry.increment_id` equals the `proposal_id` that its own launch
  intent's `campaign_proposal` block names, and the calibration's block names none and it carries none. Every case R1
  names was exercised, none *not exercised*:
  - an increment;
  - its repair and its retry, both carrying its id;
  - two re-proposals, each carrying a new one.
- **R2 holds, 14 of 14 flow runs.** Each carries `kind:<its cycle's kind>`, and every cycle but the calibration carries
  `increment:<R1's id>`. The calibration's two runs carry `kind:calibration` and no increment tag.
- **R3 holds.** The ledger lists three versions, each with its cycles in launch order and kind. Each outcome is its
  last cycle's row:
  - `prop_e900bbf73973` v1: increment, repair, then retry. Outcome row 7;
  - `prop_b9579a99644c` v1: one increment. Outcome row 16;
  - `prop_f55daca31572` v1: one increment. Outcome row 3.
- **R4 holds.** None of the six decision rows' bindings mentions a tag. Each is the row §10 gives for the verdict it
  read:
  - 5 for an accepted calibration;
  - 8 then 9 for `blocked_unverified` with a repair left and then none;
  - 7 for accepted;
  - 16 (§24bq) for a rejection only on a criterion the accepted app already met;
  - 3 for the objective met.

**So #2578's records are as §24cf and §24cg describe,** on every cycle kind a campaign launches. **The stop rule
did not fire.**

### 7.2 The finding outside the records, and the supervisor's one action

- **#2754.** The calibration's manifest declared a catch-all client route, `*` → `NotFoundView`. The increment
  evaluation's page reader requested `*` as written, which is no page. So both the first increment and its repair
  were `blocked_unverified` on `route *: not rendered`, though each was built correctly (137 of 137 verified, all
  four criteria met). Row 9 escalated.
  - Under §4's rule, a finding outside #2578's records is filed and the campaign continues. It was fixed in PR #2755,
    with a wiring test at `qa.evaluate_increment` and 3 of 3 mutations caught.
  - **The agents were rebuilt** (`dep_31949f050a30`, `verify_loaded` 193 of 193).
  - **The campaign was resumed with `retry`.** §10 row 9 leaves the next action to the owner's ruling, and the
    supervisor ruled it under the owner's grant of 2026-10-28. The build was right and the reader wrong, so a retry
    on the fixed deploy was the faithful re-run.
  - The retry was accepted with `*` held, which confirms the fix live.
- **This was the campaign's only intervention.** It is uncounted, and its claim is the records'. A counted campaign
  would name the resume as an intervention.

**Read beside the readings, as §3 lists:**
- **The second increment's rejection was the squad's proposal:** its page criterion T6 already held on the accepted
  app (`no_baseline_failure`). T5 discriminated, and the frozen T1–T4 and every route held. The next proposal, told
  which criterion was already met (row 16), dropped T6 and was accepted.
- **Neither #2664's `slot_subject_dropped` nor #2743's namespace rule** changed a verdict, as expected with this
  scope.
- **The cycle-end evaluations on revision 6** are reported only, and not read here.
- **The proposals' rulings** were each approved as they stood (§2), three in all.

**Box time:** 2 h 53 min, against the plan's guide of about 2, including the fix's merge and rebuild while the
campaign was escalated.
