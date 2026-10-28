# 2.5.0 — pre-registration of phase 3's uncounted Campaign: #2578's increment records, read on the deploy (Track D)

**Status: REGISTERED 2026-10-28, before the campaign is created.** Uncounted. It reads machinery, and no release claim
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
