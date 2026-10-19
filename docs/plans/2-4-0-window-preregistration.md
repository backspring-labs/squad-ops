# 2.4.0: pre-registration of the measurement window (plan §1.3, M2; D3, D4; SIP-0113 §7)

**Status: DRAFT, by the supervisor under the owner's grant of 2026-10-19 ("I grant you autonomy to use good judgement
to approve cycles, PRs, issue choices etc."). It is REGISTERED when the five conditions below hold and the pins are read
(§6). Nothing in the window has launched.**

The window is phase 1's data. Phase 2's thresholds come from measured noise, not guesses, and the owner decides D4 on
this record. It also doubles as SIP-0110's next build-side memory experiment: multi-increment campaigns on both stacks,
with memory observing and no lesson approved, so memory supplies nothing (the 2.3 plan's D6).

**What must be true before it is registered:**
1. **The held-out suite is approved, and the window's campaigns pin it** (D2, #2464).
   - **The suite is revision 3, digest `db69fd3707ea65b0c22e64aeefb90f2fc4621565b94244399be6de2ad697044d`,** with 25
     scenarios: 16 core and 9 expansion, counting the variants (§2).
   - **How it got there:**
     - the supervisor drafted it;
     - an independent reviewer, an agent that saw none of the drafting, read it three times: revision 1 *do not
       approve*, revision 2 *do not approve*, revision 3 *approve with notes*;
     - it is approved as `squadops-admin` under the owner's grant, and #2464 records who did what.
   - **The file and its generator** live outside every repository, mode 600.
2. **Every instrument the readings need is deployed and loaded** (§6):
   - the runner's `where` check (#2499), in the runtime API and in the sandbox service, where scenarios run. Without
     it, one scenario is `blocked_unverified` on every tree, and every contribution reading becomes `unverified`;
   - the spread instrument for prediction 4 (#2501).
3. **The final deploy is fixed** (§6). Neither lane deploys a change inside the window (G7). Two changes are decided
   here, under the owner's grant:
   - **#316's rename lands after the window,** not before the freeze as D7 placed it.
     - **Why:** the window's campaigns name only `validated-fullstack` and the campaign profiles. Both stay frozen
       under their old names, and no stack's defaults reach an old or a campaign profile
       (`test_request_profile_taxonomy.py`, PR #2500). So the window resolves identically before and after the rename,
       by construction.
     - **What it saves:** the rename's acceptance waits on a maintainer command, and holding the window for it buys
       nothing the record can see.
   - **#2457 (agents hold no database credential) is in the final deploy if its compose change has landed when the
     deploy is built.** Otherwise it lands after the window, and the record says so. The hole it closes was never used:
     prediction 2's sweep reads every place a step could reach.
4. **The shakeout loop's exit rule holds:** one shakeout campaign per stack on the final deploy, with no new seam
   finding (2.0's rule).
   - **Next.js first:** no Next.js campaign has ever run (`2-4-0-nextjs-shakeout-1.yaml`, carrying the suite).
   - **Then FastAPI + React,** since the cycle-end evaluation (#2472) has never run inside a campaign on either stack
     (`2-4-0-fastapi-shakeout-1.yaml`, carrying the suite).
   - **On a finding:** it is fixed, the deploy rebuilt, and the loop re-run. The record reports how many rounds it took.
5. **The pins are read** (§6), and nothing in the window has launched.

---

## 1. What the window measures

| claim | read from | not a substitute for it |
|---|---|---|
| the scenarios tell a tree that has an outcome from one that lacks it (P1) | the reference pair's evaluations, and each pair a window campaign produces | a scenario that passes on both trees, which is withdrawn as evidence |
| no scenario step reaches anywhere the squad or the product can see (P2) | the sweep (§4) | the route and import guards, which are code-level |
| contribution is not the acceptance count by another name (P3) | each accepted increment's contribution reading, counted by §4's rule | an increment no participating scenario covers |
| each quality measure's spread on an unchanged tree (P4) | `remeasure_quality.py` on each campaign's calibration tree | one evaluation per tree |
| the intervention ledger matches the control log (P5) | the ledger beside each campaign's control log | the digest's Autonomy section alone |
| an evaluation leaves no trace in the product (P6) | each record's evaluated tree identity beside the cycle's accepted tree | the runner's own guarantee |
| memory observes and supplies nothing (SIP-0110) | the exposures, the observations and the repeat report | the regression rolls, which declare memory disabled |

---

## 2. The window

- **Four campaigns, two per stack, three increments each, on one frozen deploy** (D3):
  - `examples/03_group_run/campaigns/2-4-0-window-fastapi-react-1.yaml`, `-2.yaml`;
  - `examples/03_group_run/campaigns/2-4-0-window-nextjs-1.yaml`, `-2.yaml`.
- **Each campaign:**
  - `group_run`, toward its PRD's expansion scope;
  - work class `tier-1`, `unattended` (#2418);
  - `full-38-tf`, `plan_gate: tier`;
  - its stack in its policy (#2443), the campaign profiles as they are;
  - the suite pinned.

  Policy, from 2.3.1's cut shakeout scaled to three increments: `max_cycles: 9`, `max_elapsed_s: 64800`,
  `budget_tokens: 6000000`; every other limit as 2.3.1.
- **Order:** FastAPI 1, Next.js 1, FastAPI 2, Next.js 2. Each campaign runs alone on the box.
- **Proposal rulings are the supervisor's, by one rule fixed here.** A proposal is approved when:
  - its change request stays inside `allowed_scope`;
  - it names a PRD expansion item, in the PRD's priority order or a later one with its reason;
  - its criteria are checkable.

  Otherwise it is rejected with its class (#1947's vocabulary): `outside_scope`, `criteria_not_checkable`,
  `conflicts_with_an_earlier_increment`. The ruling's notes say which condition decided it. **No ruling reads a
  scenario,** so the suite reaches no ruling, and none reaches the squad.
- **The suite, by outcome** (goals are visible by design, D2(1); steps are not, and appear nowhere here):
  - **core:**
    - a created run reads back;
    - a created run is listed;
    - an unknown run is not found;
    - a run needs a title;
    - a joined runner is listed;
    - the same name can't join twice;
    - a runner needs a name;
    - joining a missing run is not found;
    - a runner who leaves is gone;
  - **expansion:**
    - a full run turns the next runner away (Tier 1, capacity);
    - a place freed by a leave can be taken (Tier 1, capacity);
    - runs are listed soonest first (Tier 1, sorting);
    - a name with spaces is the same name (Tier 2, normalization).

  Each join outcome has a variant at `/participants`, and each leave outcome one per leave pairing deliveries
  declare. On the 85 deliveries stored since 10-12 and the 351 since 09-15, exactly one variant per outcome takes
  part, or none for a rare pairing. None double-counts: the others are `surface_absent` (SIP-0113 §10e).

---

## 3. The frame

- **Reporting only** (D1): no scenario result, quality reading or contribution reaches a squad role, a ruling, a gate
  or a decision. Phase 2 is the owner's (D4), on this record.
- **A change inside the record ends the series** (§1.3 of the plan): a rebuild, a merge that reaches the deploy, or an
  approved lesson. The next series starts under a new record. No reading compares two series.
- **Inconclusive:** a campaign ended by a cause outside the framework (a box halt). It is re-run under 1.8.2's void rule
  and does not count.
- **Data, not failure:**
  - a correction round;
  - a rejected proposal;
  - a `regressed` or `unverified` reading;
  - a measure's spread.

---

## 4. The predictions: each names a mechanism and how it is falsified

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | a scenario fails on a tree known to lack its outcome and passes on one known to have it. **On FastAPI, the normalization outcome passes every tree** (the frozen `NonBlankStr` trims), so it is read on a Next.js pair only | the reference pair (`cyc_7a4b7a6fbf0e`, `cyc_20246018f2b8`) evaluated on the final deploy before the window, and each window pair where an increment adds an expansion outcome | a scenario that passes on a tree known to lack its outcome. One that passes both trees of every pair is withdrawn as evidence, not counted |
| P2 | no scenario step appears in any authoring envelope (reconstructed byte for byte, `verify_authoring_envelopes.py`), stored task envelope, LangFuse generation (#1756's full prompts), agent container, workspace or the product's tree | the sweep after the window, searching for the suite's own step values. The markers live with the suite outside the repository, and the sweep reports counts only | any marker found in any of them |
| P3 | some accepted increments read `neutral` | each accepted increment's contribution. **Counted only where a participating scenario covers the increment's PRD item.** A `neutral` from an item no scenario covers, from `surface_absent`, or from behaviour the stack's scaffold already guarantees (normalization on FastAPI) says nothing, and is not counted | every counted increment reading `contributed`. **Inconclusive** with fewer than two counted increments |
| P4 | each measure is stable on an unchanged tree: axe and lint, which are deterministic, spread 0; Lighthouse accessibility and best practices spread 0; Lighthouse performance spreads at most 0.05 | `remeasure_quality.py CALIBRATION_CYCLE 3` on each campaign's calibration tree after the campaign ends: 12 re-measures, 3 per tree | a measure spreading beyond its bound on any tree. It is reported, and phase 2 may not gate on it |
| P5 | every in-interface intervention row has its classification, and no classified entry lacks its row | each campaign's intervention ledger beside its control log (`aor_reading.py`) | a row without its classification, or a classification without its row |
| P6 | an evaluation leaves no trace: the record's evaluated tree identity equals the cycle's accepted tree, and the live tree is unchanged after it | each evaluation record beside its cycle's accepted tree identity | any difference |
| M1 | memory observes and supplies nothing: no approval is in force, every consuming task records its exposure, and observations are recorded where a run produces them | the lesson store (`squadops lessons list`), `memory_exposures`, the observations table, the repeat report | an approval in force, a consuming task without an exposure, or a failed round without an observation |

**Also read, not predicted:**
- **The seven safety guarantees** (#2487), per campaign.
- **AOR's four inputs and the work envelope** across the four campaigns (#2489), by work class.
- **The per-increment scorecard** (#1960).
- **Each increment's quality deltas,** against the tree it built on and against the calibration (#2480).

---

## 5. The record (§1.3 of the plan), written as the window opens

In `var/window/2-4-0/manifest.json`, with a copy committed beside this file when the window closes:
- **The deploy:**
  - its record, and the framework commit it was built from;
  - every service's image id, and the models' digests;
  - the evaluator's image tag, which is each quality measure's version.
- **The suite:** its digest, each scenario's id and version (content hashes; no content).
- **Each campaign:** its id, its definition file's path and sha256 (#1954), and its project and PRD (`group_run`,
  `examples/03_group_run/prd.md` sha256).
- **SIP-0110 §0.12's experiment manifest:**
  - a hash of `src/squadops/prompts/`;
  - `config/` and the request and squad profiles;
  - the model and its settings;
  - the policies;
  - the store's lessons and approvals: two revisions of one pattern, `pat_0b4aef8aea97…`, and no approval in force,
    read 2026-10-19.
- **The scoring rules:** contribution's readings (SIP-0113 §4.4), §4's counting rule for P3, and P4's bounds.

---

## 6. Pins (read at registration)

| pin | value |
|---|---|
| deploy commit | *read at registration* |
| deploy record | *read at registration*, `verify_loaded` all answering, including `where` in the sandbox service |
| image ids | *read at registration*, from the running containers |
| model | `full-38-tf`'s model and its digest, *read at registration* |
| evaluator | *read at registration* (`EVALUATOR_IMAGE`) |
| suite | `db69fd3707ea65b0c22e64aeefb90f2fc4621565b94244399be6de2ad697044d`, approved |
| definitions | the four window files' sha256, *read at registration* |

---

## 7. Prohibited while the window is open

- **Rebuilding or redeploying any Spark service** (G7). A merge to main is free while it reaches no deploy.
- **Approving a lesson.**
- **Running anything else on the box,** the other lane's demonstrations included (D12(4)).
- **Changing the suite.** A suite is content-addressed; a new one is a new series.

## 8. Drift the record must declare

- **Any difference between the registered deploy and main,** each named additive or behavioural.
- **Each void and re-run,** with its cause.
- **Each owner action,** and each supervisor ruling under the grant.
