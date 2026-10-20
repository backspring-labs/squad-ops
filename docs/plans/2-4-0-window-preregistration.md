# 2.4.0: pre-registration of the measurement window (plan §1.3, M2; D3, D4; SIP-0113 §7)

**Status: REGISTERED 2026-10-20, pins read at 18:38:29Z, by the supervisor under the owner's grant of 2026-10-19 ("I
grant you autonomy to use good judgement to approve cycles, PRs, issue choices etc."). The five conditions below hold, each
with its reading (§0), and the pins are in §6. Nothing in the window had launched when they were read.**

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

## 0. The conditions, as read at registration (2026-10-20)

1. **The suite is approved and pinned.** Revision 3 (`db69fd37…`) is approved (#2464). Each of the four window
   definitions pins it (`scenario_suite`) and carries §2's policy (`max_cycles: 9`, `max_elapsed_s: 64800`,
   `budget_tokens: 6000000`) and its stack.
2. **The instruments are deployed and loaded.**
   - `verify_loaded.py` reads 157 of 157 checks loaded, the runner's `where` check among them, in both services:
     `2464-where-sandbox` and `2464-where-runtime`.
   - The spread instrument (`remeasure_quality.py`, which runs in the runtime image) imports
     `squadops.outcomes.quality_spread` and the quality readers in the running runtime API.
3. **The final deploy is fixed:** `dep_19dfa94c0a0a`, built from `92e26330` by `rebuild_and_deploy.sh all`, 24 services.
   `verify_loaded.py` reads that the record describes what runs, and no later deploy is recorded.
   - **#2457 (agents hold no database credential) is not in it.** Its compose change (#2506) hasn't landed, so it lands
     after the window, as condition 3 allows.
   - **#316's rename** lands after the window, as decided above.
4. **The shakeout loop's exit rule holds.**
   - **The loop:** ten Next.js rounds and one FastAPI campaign, across nine deploys.
   - **What it found and fixed:** ten seam findings, fixed by nine PRs: #2511 and #2512, #2522, #2531, #2534, #2536, #2538, #2540,
     #2542 and #2547. Each was fixed by its PR (#2514, #2523, #2532, #2535, #2537, #2539, #2541, #2543, #2548), and the
     deploy rebuilt.
   - **On the final deploy:**
     - **round 9** (Next.js, `cmp_51011c06ed90`) had no new seam finding, but its calibration ended as #2306's known
       `plan_defect` before any increment ran;
     - **the FastAPI campaign** (`cmp_41d4a7185a3a`) completed with success: the calibration and two increments
       (capacity, sorting) accepted with no repair or retry, all seven safety guarantees held, no seam finding;
     - **round 10** (Next.js, `cmp_7197fdc82778`) completed with success: the calibration accepted, capacity accepted
       through one repair, and sorting accepted.
       - Capacity's first implementation failed on a squad defect: its T1 task wrote a page test for T3 into an API
         suite, in node, and the correction loop ended it as #2306's known `plan_defect`.
       - The repair ran T3's own page suite in jsdom, passing, with `acceptance:additive_containment` passing on every
         task. That is #2547's fix, live.
       - No seam finding.
5. **The pins are read** (§6) at 18:38:29Z, after round 10 ended at 18:35:54Z. Nothing in the window had launched.

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

Read 2026-10-20 at 18:38:29Z, from the running deploy, its record and the tree it was built from.

| pin | value |
|---|---|
| deploy commit | `92e26330` |
| deploy record | `dep_19dfa94c0a0a`, recorded 2026-10-20 14:18:10Z by `rebuild_and_deploy.sh all`, 24 services; the latest record. `verify_loaded.py`: 157 of 157 loaded, `where` included in the sandbox service and the runtime API, and the record describes what runs |
| image ids | `squadops-bob` d4472067f0e7; `squadops-caddy` d6f3b771cd41; `squadops-console` 2aa630029b8b; `squadops-data` 7d86219bf347; `squadops-dcgm-exporter` ad8339fcb648; `squadops-eve` 7680d996eca4; `squadops-grafana` 618b96f5c3f1; `squadops-han` 031c0d5345ac; `squadops-joi` 8b51d31944b6; `squadops-keycloak` bbc4de472c9d; `squadops-langfuse` bfb03bde31de; `squadops-max` 1d53ef08e81c; `squadops-nat` 1e43ac9eab3f; `squadops-neo` e434a0df96c2; `squadops-node-exporter` 95133add9e51; `squadops-otel-collector` 9acf2ba42604; `squadops-postgres` 8e044a3419af; `squadops-prefect-server` af308092ef5b; `squadops-prometheus` 5ccfaca220fc; `squadops-rabbitmq` 95cf051f517d; `squadops-redis` 49898aa0365c; `squadops-runtime-api` a56ce18b4015; `squadops-sandbox-service` aca9adf3b800; `squadops-tensorfold` b62567b8d89f |
| model | `full-38-tf`'s `qwen3.8-27b-tf-nvfp4`, served by TensorFold. Its identity is the frozen recipe `infra/tensorfold/recipes/qwen27b-nvfp4.yaml`, sha256 `a3d260ecd24ca895e882063f9ed0530f1f913a3231fda29fad16c966919bc283`, and the `squadops-tensorfold` image above. **The deploy record names no digest for any model** (#2561, below) |
| evaluator | `squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-2` (`EVALUATOR_IMAGE`, read from the running sandbox service) |
| suite | `db69fd3707ea65b0c22e64aeefb90f2fc4621565b94244399be6de2ad697044d`, approved |
| definitions | `2-4-0-window-fastapi-react-1.yaml` `2d9c74f1ca2e1cd77c057b67f12fd5c3806d9374c3028257c93137f11b39d82d`; `-fastapi-react-2.yaml` `e12484cb97a9ff6e18c6065a5e409a1727f0ab09aca6e0c84817a12aac198c36`; `-nextjs-1.yaml` `a2ff593a5d29b15310dc993d8c2b8f3eca262879b9943898af9831df78c515f9`; `-nextjs-2.yaml` `4a0cccc71e49a2be8f0e987ee0adc7c4e94c45cc930691cec9eda8270d0f93c1` |
| PRD | `examples/03_group_run/prd.md` sha256 `de1555a68cd3d0602e2c8968c8a499fc15bdf067322397915e4482604ab70d16` |
| prompts and config | `src/squadops/prompts/` `145583c612d52af92626edc2b05f4cea3c813f6a4f7b19a39acba975ae3b8a3e`; `config/` `afa24ce69262341fe58738ec4d28bdb1a7c7dd1a74ece32ee192f4c052dea431`. Each is the sha256 of its files' sha256 list, sorted by path, read where neither differs from `92e26330` |

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

**Declared at registration.** main (`f3f6f0a7`) is ahead of the deploy (`92e26330`) by seven PRs. None is in the window's
runtime, because the window runs the deploy. For a reader comparing the two:
- **Additive and inert for the window's campaigns:**
  - #2552: a loaded check's row only;
  - #2554: `prepare_cycle` builds a cycle's admitted task instructions, and a campaign's launch stores them;
  - #2555 and #2559: `@current` bound for project and task instructions;
  - #2567: a reference no unit of its project can bind, refused at write.

  No window campaign gives a task instruction or names `@current`, and no resolver is registered on the deploy.
- **#2556** adds `carries_into` and the increment gate's `task_instructions`, neither of which a window ruling uses (§2's
  rule names none). It also adds a `continues` key to a repair's or a retry's `campaign_proposal` block. That key enters
  the repair's or retry's config hash (its `execution_overrides`, as `repair_of` and `prior_cycle` already do), and no
  window rule reads it.
- **#2563** is documentation.
- **The verification-set driver** (`scripts/dev/verification_set_driver.py`, run from the checkout, not the deploy) also
  changed in #2555 and #2556: its pinned instruction set, and its count of after-admission instructions, which now leaves
  out `gate_decision`. The window doesn't use it. Its intervention ledger is read with `aor_reading.py`, and no window
  campaign gives instructions.

## 9. Declared before launch: what the window's evidence does not cover, and what it is expected to show

- **No user-interface outcome is measured independently.** Revision 3's 25 scenarios all name `http_endpoint`
  surfaces, so what a page shows is checked only by the squad's own tests. The browser runner and page scenarios are
  SIP-0113 §10k (#2564), after the window.
- **Lighthouse and axe see only the parameterless pages, on an empty app** (`/` and `/runs/new`). They will mostly read
  flat across a campaign. A flat reading is not a baseline held for the pages increments change. The seeded reading is
  SIP-0113 §10j (#2562), after the window, and the window's trees are re-measured with it then.
- **The model is pinned by its recipe and image, not by a digest.** Every deploy record since 2026-10-14 names no model
  digest (#2561).
- **Expected once per calibration at most, and answered identically:** the plan review's list-order question. PRD §5.2
  states no core list order (#2557).
  - The answer: the core list shows runs in insertion order, and sorting is Expansion Tier 1 item 2.
  - The intervention ledger counts each, and the readout names them. Round 10's calibration didn't raise it.
- **Known shapes that may appear, and are named, not new:**
  - #2306, a correction ended as `plan_defect` when its failure signature repeats;
  - #2558, a retry of a failed repair starting from the original increment's candidate. The readout checks whether
    any retry followed a repair.
