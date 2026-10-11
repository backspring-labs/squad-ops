# 2.2.1 plan — a failed proposal and an abort end with a record, never a wedge

**Status: ADOPTED (2026-10-11); READ: the line's evidence is §6.** The owner ruled §5 at about 10:38 ET: "approve D1-D4 as recommended". The supervisor
runs the line through the cut (D4). **Drafted the same morning.** The owner asked for "a lean verification; don't want to
spend all day on this fix pack". So this plan fixes three defects, verifies each where a live campaign can reach it, and
says plainly what it leaves to tests.

**What 2.2.1 is.** A patch on the 2.2 line (CLAUDE.md, #281: urgent or small fixes, either lane). It carries the three
defects the 2.2 cut's tier diagnostic found, which the owner placed here at the cut (`cmp_4bdd8fb573a0`, uncounted;
`docs/plans/2-2-0-cut-preregistration.md` §2 and §10). Nothing else is in it (§2).

**The claim it makes:**

> **A campaign whose proposal fails, or which is aborted while a cycle waits between workloads, ends with a record
> and no stranded cycle.**

On the 2.2.0 deploy, one refused proposal did all of this:
- it ran the build correction loop inside a proposal run;
- it completed `accepted` with no change request;
- it raised at the increment gate where nothing retrieved the error, and the campaign sat at `at_proposal` for eight
  hours with no row and no bound;
- the abort that ended it left its cycle `active`.

---

## 1. The three fixes

All three are runtime-api code, and each is on a campaign's path only (§3, why no regression set).

### #2212 — a refused proposal is a failed proposal run, never a correction round

- **The defect:** `strategy.propose_increment`, refused by §9.1's rails after its revision budget, fell into the build
  correction loop. Only `governance.define_done` skips it (`TaskType.fails_without_correction`,
  `src/squadops/tasks/task_types.py:104`, consulted at `adapters/cycles/dispatched_flow_executor.py:3156`). The repair
  wrote product source into the proposal run, and the run completed `accepted` with 0 checks executed.
- **The fix:** the proposal step joins the property. A proposal's output is a document the rails judge, so a repair
  can't satisfy them and nothing re-runs them. Its failure aborts the run, and the cycle ends `proposal_failed`
  (`src/squadops/campaigns/progress.py:146`), which the campaign counts under `max_proposal_run_retries`. The
  property's docstring states the reason for both members. That follows the task-type rule: properties over identity.
- **The wiring test** enters at the executor's failed-task path with a refused `strategy.propose_increment` result. It
  asserts no `data.analyze_failure` is dispatched and the run ends failed.

### #2213 — nothing reaches the increment gate without a change request, and an error there is recorded

- **The defect:** the run reached the increment gate with no `change_request.yaml`. `_submit_proposal` raised
  `ValueError` (`adapters/cycles/workload_gate.py:670-700`) inside a task that nothing retrieves
  (`src/squadops/api/campaign_launch.py:221-224`; its done-callback only discards it). The campaign stayed
  `at_proposal`, with no row, no sweep and no bound.
- **The fix, in two parts:**
  - **A proposal run with no change request ends failed,** with that as its reason, so the campaign hears
    `proposal_failed` as in #2212. Where the check sits (before the run is marked completed, or at the gate) is the
    PR's design note.
  - **An exception that escapes a campaign cycle's execution is recorded.** The launch's done-callback reads it, and
    logs it with the cycle and run ids. It also ends the run failed with the exception as its reason, so the campaign
    sweep hears an ending. An exception must never again be the only record of a campaign's stop.
- **The wiring test** enters at the campaign launch with an executor whose gate raises. It asserts that the run ends
  failed, that the campaign records the ending, and that no task exception goes unretrieved.

### #2214 — the abort cancels a cycle waiting between workloads

- **The defect:** `_cancel_launched_cycles` judges "ended" with `derive_cycle_status`, which reads the latest run only
  (`src/squadops/api/routes/campaigns/campaigns.py:871-887`; `src/squadops/cycles/lifecycle.py:99`). So it calls
  `COMPLETED` the same cycle that the cycle route calls `ACTIVE` with `resolve_cycle_status` and the workload progress
  (`src/squadops/api/routes/cycles/mapping.py:244-248`).
- **The fix:** the abort resolves status the way the cycle route does. Both should call one shared helper, so the two
  derivations can't disagree again.
- **The wiring test** enters at the abort route, with a campaign cycle whose only run completed and whose next workload
  is pending. It asserts that the cycle is cancelled and named in the abort's response. That's the test the issue
  asks for.

**Each PR** carries:
- `Closes #N`;
- a tracked loaded check (`scripts/dev/verify_loaded.py`) that answers only on the fixed code;
- its wiring test's entry point named in its Evidence.

---

## 2. Not in 2.2.1

- **#2205, #2206 and #2210** stay in 2.3, by the owner's ruling at the 2.2 cut (its §9, decision 2).
- **#2202 and #2208** are the 2.3 plan's to place.
- **The tier's timeout half, read live,** leaves 2.2.1 (D2). That is the expiry at the bound, the parked cycle,
  `abandon_and_propose`, the no-progress stop and the late answer.
  - The 2.2.0 ROADMAP entry placed it here, "with them". But the 2.2 cut also showed it **cannot be forced on an
    increment without code**. Plan validation holds every plan to its proposal's footprint, and the scope rail holds
    the footprint to `allowed_scope` (`src/squadops/cycles/implementation_plan.py:958`,
    `src/squadops/campaigns/change_request.py:493`). A calibration asks a
    question only part of the time.
  - Forcing it needs a diagnostic-only fault: an increment's plan that declares an open question. Building that and
    running a three-hour campaign is the opposite of lean.
  - Recommended: place the fault and the live reading in 2.3. Until then, unit tests at its seams stay its evidence,
    as 2.2.0's record says.
  - This cut's ROADMAP entry corrects the 2.2.0 line.

---

## 3. Verification: lean, and what it costs

| step | what it shows | cost |
|---|---|---|
| each PR's unit and wiring tests, in CI | each fix at the entry point a live cycle uses | in the PR |
| `rebuild_and_deploy.sh runtime-api`, then `verify_loaded.py` | the deploy answers with the fixed code: the three new loaded checks plus the tracked rows | ~15 min |
| **one diagnostic campaign** (below) | #2212 live, and #2213's first part not reached | **~1.5 h, unattended** |
| the cut (CLAUDE.md steps 1–8) | the release, its package and its records | ~1 h |

**The diagnostic campaign** is uncounted, and runs the roll's own path (#1251).
- **The definition:** the 2.2 cut's tier diagnostic, with the same objective, `allowed_scope` and policy, saved as
  `2-2-1-proposal-failure-diag.yaml`. Its header says what it actually triggers. The 2.2 file's header described an
  escalation that never fires.
- **Why it works:** its `allowed_scope` excludes the test directories, so the scope rail refuses every proposal. That
  makes #2212's trigger certain.
- **The calibration** builds the app first, about 50 minutes on React. A question it asks is answered by the delegate
  inside the 600-second bound, as in 2.2.
- **The increment's proposal runs then fail,** each in about 15 minutes. `max_proposal_run_retries: 1` allows one
  retry.

It reads, with each item falsifiable:
- **R1 (#2212):** no correction-loop task (`data.analyze_failure`, `governance.correction_decision`, a repair) is
  dispatched in either proposal run, and no source is written there.
- **R2 (#2212):** each proposal run ends `failed` with the rails' refusal as its reason, and its cycle ends
  `proposal_failed`.
- **R3 (#2212, #2213):** after its one retry, the campaign closes itself with a close row naming why. No cycle stays
  `active`, and the campaign never sits `at_proposal` past its bound.
- **R4:** no `Task exception was never retrieved` line appears in the runtime-api log from launch to close.

**The exit rule:** one run.
- **A finding in these three seams** is fixed, rebuilt and re-run once. A second finding stops the line for the owner.
- **A finding elsewhere** is filed and placed. It doesn't hold the patch, unless the fixes caused it.

**The calibration doubles as the release's build check.** It's a full greenfield build on the rebuilt runtime, and its
app is what the package photographs. The package guard requires a captured cycle and screenshots.

**No regression set, and why.** Every changed seam is on a campaign's path only:
- the proposal step;
- the increment gate;
- the campaign launch's task;
- the abort route.

A standalone regression roll runs none of them. A set would show the build unchanged, which the calibration already
does once.

**What this does not cover:**
- **#2213's first part, live.** With #2212 fixed, no known path brings a run to the gate without a change request, so
  that guard is read in tests only.
- **#2214, live.** It's a derivation swap read by its wiring test. A live abort needs a campaign held at a gate, which
  costs another campaign. The diagnostic can't show it: with #2212 fixed, its increments never wait between workloads.
  If the owner wants it (D3), a second short campaign, with its plan gate left to the delegate, is aborted at its
  calibration's plan gate once framing completes.
- **The tier's timeout half** (§2).
- **Next.js:** the diagnostic runs on React only.
- **One campaign is not a rate.**

---

## 4. Sequencing

1. **The three PRs**, in issue order, each merged on green with main's run read: #2212, then #2213 (which builds on
   #2212's failed run), then #2214.
2. **Rebuild** `runtime-api` and run `verify_loaded.py`.
3. **The diagnostic campaign,** under a stall-alarmed watcher. Its readout goes in §6 of this plan.
4. **The cut:**
   - the version bump to 2.2.1;
   - the CHANGELOG, and the ROADMAP entry, which corrects 2.2.0's placement of the timeout half;
   - the SIP sweep;
   - the tag and the Release (D4);
   - the package, with the diagnostic as its cycle evidence and its calibration's app on screen;
   - the records, then housekeeping.

**Drift the record declares:** the tagged tree against the rebuilt deploy. It should be prose and the version only.

---

## 5. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| D1 | **the scope** | **the three issues only** (§1, §2) |
| D2 | **the tier's timeout half, read live** | **out of 2.2.1:** placed in 2.3 with a diagnostic fault that makes an increment's plan ask a question (§2) |
| D3 | **the verification** | **§3 as written:** tests, a runtime-only rebuild with loaded checks, and one ~1.5-hour diagnostic campaign. *Leaner:* drop the campaign and photograph a single regression roll, so no fixed seam is read live. *Heavier:* add the live abort for #2214, a second campaign aborted at its calibration's plan gate, about 35 more minutes |
| D4 | **who runs the line** | **the supervisor, on the 2.2 line's terms, through the cut and including the tag and the records upload, once §3's readings hold.** If any reading fails, it stops for the owner. The grant ends at the 2.2.1 cut |

**Ruled 2026-10-11: D1–D4 as recommended** (the owner: "approve D1-D4 as recommended").

---

## 6. The record

**The line ran on 2026-10-11, from the plan's adoption (about 10:38 ET) to the cut.**

**The merges:**
- the three fixes, each with its wiring test and loaded check:
  - #2224 (#2212);
  - #2225 (#2213, with migration 1696 and the `gate_failed` stop reason);
  - #2226 (#2214);
- the diagnostic's definition (#2227);
- the private fix the owner added ("include the .env fix"): #2233, `.env` made owner-only, advisory GHSA-wrfh-h7jx-w578. It was pushed only at the cut, as 2.0.1's was.

**The rebuild:**
- `rebuild_and_deploy.sh runtime-api` at `dba4f0c2`, giving deploy **`dep_b0c134405d55`**;
- `verify_loaded.py`: 71 of 71 loaded checks answering. Row 2212, row 2213 (which reads the live `gate_failed` constraint, so 1696 applied) and row 2214 are among them;
- the deploy record describes the running images.

**The diagnostic, `cmp_bf5daecdf444`** (uncounted). It launched at 11:26 ET and closed itself at 13:53 ET.
- **Its calibration** `cyc_bf66cbcb335e` was accepted with 26 delivered files. The tier approved its plan gate
  (`system:plan_review_tier`), and no question was asked.
- **Four proposal cycles followed:**

  | cycle | failed at |
  |---|---|
  | `cyc_785155745e7e` | 12:47 ET |
  | `cyc_b659b00469ea` | 13:08 ET |
  | `cyc_c00c032b4ab3` | 13:35 ET |
  | `cyc_23980bea6492` | 13:53 ET |

  In every one, the scope rail refused all three revisions, the dispatcher's D5 retry re-ran the task, and it was refused
  three more times.

**The readings:**
- **R1 holds.** No correction-loop task was dispatched in any proposal run.
  - The runtime log has zero `analyze_failure`, `correction_decision` or `correction_repair` lines from launch to
    close.
  - Each proposal flow run's only task type is `strategy.propose_increment`.
  - Each run stored only its `run_report.md`, so no source was written.
- **R2 holds.** All four proposal runs ended `failed`, with the rails' refusal as their reason ("failed (no
  correction): the proposal was refused after its revision budget"). Each cycle ended `proposal_failed` (control log
  rows 7, 9, 11, 13).
- **R3 holds where it matters, and its mechanism was mispredicted.**
  - **It closed itself, and the record names why:** row 13 is `decide`, row 4, cause `total_cycles`, outcome
    `exhausted`.
  - **Nothing was stranded:** no cycle stayed active, and the campaign never sat at `at_proposal`. Each decision came
    within seconds of its cycle's failure.
  - **The plan's wrong prediction:** it said the campaign closes "after one retry (`max_proposal_run_retries`)". That
    misread the field. SIP-0109 §9.5 makes it a bound on in-cycle proposal-run retries, which aren't built, and nothing
    reads it. So the continuation's row 6 proposed again after each failure, by design, until `max_cycles` (5).
  - **That is #2231,** placed in 2.3 by the owner ("let it close, place #2231 in 2.3"). Under §3's exit rule it is a
    finding elsewhere, and it doesn't hold the patch. #2212 didn't cause it: #2212 made `proposal_failed` reachable live
    for the first time.
- **R4 holds.** Zero "Task exception was never retrieved", `campaign_cycle_execution_raised` or
  `inter_workload_gate_failed` lines from launch to close. The only ERROR lines are the four run failures.

**A cost estimate the plan got wrong.**
- **Each proposal run took 19–27 minutes,** not about 15: the D5 task retry doubles a refused proposal's attempts.
- **The campaign took 2 h 27 m,** not about 1.5 h, because #2231 let it run four proposal cycles.

**What the line does not cover, as §3 said:**
- **#2213's completion check, live.** With #2212 fixed, no proposal run completed without a change request, so the check
  never fired.
- **#2214, live.** It is read by its wiring test.
- **The tier's timeout half** (2.3, D2).
- **Next.js.**
- **One campaign is not a rate.**

**Drift the record declares: the tagged tree against the rebuilt deploy (`dba4f0c2`).**
- **Behavioural, tooling only:** #2233's change to the deploy tooling and the doctor:
  - `scripts/dev/ops/deploy_credentials.py`;
  - `scripts/bootstrap/lib/docker_setup.sh`;
  - `src/squadops/bootstrap/setup/credentials.py` and `checks.py`.

  The runtime and the agents don't import them, so no rebuild is needed.
- **Inputs and prose:** the diagnostic's definition (#2227), the 2.3 plan and SIP-0111 §9a (#2228, #2232), and this
  release's version, CHANGELOG, ROADMAP and records.
- **The deploy reports 2.2.0** until its next rebuild.

**The owner's actions:**
- the plan's ruling ("approve D1-D4 as recommended, include the .env fix");
- "let it close, place #2231 in 2.3";
- the 2.3 plan's rulings, recorded in that plan.
