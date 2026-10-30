# 2.5.0 — pre-registration of the cut's set (the plan's §4, "The cut")

**Status: REGISTERED** on 2026-10-30 at 02:30Z (22:30 ET on 2026-10-29), when all eleven conditions below held (§14).
Drafted 2026-10-29 and revised the same day on a second reader's findings and the owner's rulings (§13), then merged as
a draft (#2822) before anything ran. The exit rule held in shakeout round 1, and the repeats ran on the final deploy
after it. Nothing in the set launched before registration. Written by the Spark lane, which runs the line alone since
2026-10-28 (the plan's §5), after the demonstrations were read and the owner narrowed the claim (2026-10-29: "Narrow
the claim, go to cut").
The plan leaves the cut's numbers to this document (its §8: "the set's size, the predictions' thresholds and the
shakeout's budget"):
- **the set's size is 2.4's,** carried as 2.4 carried 2.3's (the plan's §4 and D8);
- **the thresholds are 2.4's,** now read against eleven baselines where 2.4 had seven: 2.4's seven and its four
  counted rolls, each re-read on suite revision 6 (§2);
- **the shakeout's budget is three rounds** (the plan's §4).

**The owner's rulings at this stop (2026-10-29):**
1. **The engine:** the owner chose "Frozen recipe". The shakeout, the repeats and the set run on the frozen counted
   recipe, switched from #2742's two-lane candidate, and the candidate is restored after the set's last reading and
   the runs beside it (IR-1, IR-8's registry half). The basis is the plan's D5: 2.5's regression reads against 2.4's
   baselines "with no engine change beside the evaluator's".
2. **The voided demonstration readings:** the owner chose "Repeat the cheap ones": a fresh `z_shelfnote` Campaign, a
   `z_continuum` start, and the missing-route replay, each on the final deploy (§6.3).
3. **IR-3:** the owner chose to repeat it ("1 yes"), on that `z_continuum` start, across one more outside commit
   (§6.3).
4. **Other callers of the engine:** the owner chose to read them ("2 metrics"). The crews keep running. Each roll's
   window is read on TensorFold's own metrics, and a roll is inconclusive for another caller's load on that evidence
   only (§3, §4).
5. **The narrowing and the deferrals:** the owner chose "Yes to both". IR-6's increment half joins IR-5 and IR-9's
   increment reading under the narrowing, and #1469 and #2286's remainder move to 2.6 (§11).
6. **D12:** the owner chose "No revert rule" (§3).

**And during the repeats (2026-10-30):**
7. **The `z_continuum` repeat's escalation:** increment 1's repair couldn't be built (#2824). The owner chose "Abandon
   and propose" to resume it, which continued IR-3 (§14).
8. **#2824:** the owner chose "Name it, fix after". It is placed in 2.5.x or 2.6 beside #2818 and named in §11. The exit
   rule and the final deploy stand, since neither the rolls nor the shakeout reach it.

**What must be true before the shakeout's first launch,** in this order:
1. **This document is merged, as a draft,** with the shakeout's definition, so the shakeout's predictions are fixed
   before it launches. **Met:** #2822, merged as `ffc32804`.
2. **The engine serves the frozen recipe.** `scripts/dev/ops/engine_switch.py to-tensorfold
   infra/tensorfold/recipes/qwen27b-nvfp4.yaml` runs before the rebuild. It refuses while a run is running, queued or
   paused, or a campaign is open (`engine_switch.py:195-204`), recreates every model client, and writes a deploy
   record. **Not met:** read at 22:30Z on 2026-10-29 (`docker inspect squadops-tensorfold`), the engine runs #2742's
   candidate, `recipes/candidates/qwen27b-nvfp4-parallel2.yaml` (`--parallel 2`, its status "not the frozen
   counted-verification recipe"), started 2026-10-24 at 22:50Z, five days. So Track D's Campaign, D12's evidence and
   the demonstrations all ran on it (§10). **Met:** the switch ran 23:09:09–23:09:39Z on 2026-10-29, exit 0, on a
   free box (record `var/engine_switch/20261029T230909Z-to-tensorfold.jsonl`).
3. **The line's last code is deployed, after the switch.** The Spark is rebuilt from main (`rebuild_and_deploy.sh
   all`) once this document, condition 7's script and anything else the cut needs are merged. That rebuild is **the
   final deploy**, and its deploy record is the last one written before registration (§7). Main's last change to a
   run path today is `d0df8acb` (#2816). **Met:** rebuilt from `f69ce0e2` (#2823 merged) at 23:23Z:
   **`dep_eb111413d45d`**.
4. **The engine is read** (§7), and its reading is the pin:
   - **its `Args`** from `docker inspect` are exactly the line from `serve` onward that `serve_command` builds from the
     frozen recipe (`engine_switch.py:302-353`), which is today's line without `--parallel 2`;
   - **its `.Image`** equals the recipe's `image_id`;
   - **its `State.StartedAt`** is recorded.

   They are read again after each shakeout round, at registration and at each roll's start and end (P1). **The exact
   line and image are the pin,** since nothing else tells the recipes apart:
   - `verify_tensorfold` checks only that each of the recipe's flags is on the line (`engine_switch.py:458-462`), so
     the candidate's line passes it against the frozen recipe;
   - the deploy record's weights key on the served id (#2732), which both recipes serve.

   **Met** at 23:23:51Z: `Args` from `serve` equal `serve_command`'s line for the frozen recipe (compared in code),
   `.Image` `sha256:b62567b8…` equals the recipe's `image_id`, and `State.StartedAt` is `2026-10-29T23:09:10.78Z`.
   The rebuild didn't restart it. Unchanged after shakeout round 1 and at registration.
5. **Every tracked loaded check answers its expected value on the final deploy,** `2253` (D12) among them
   (`verify_loaded.py`, run from the main checkout), and the deploy record is ok. `scripts/dev/loaded_checks.yaml` has
   247 rows at drafting, 68 more than 2.4's 179. **Met:** 247 loaded, 0 not; "dep_eb111413d45d describes what runs:
   24 services".
6. **The sweeps' baselines are taken** on the final deploy (§4.2), by `heldout_sweep.py` as main carries it since
   #2819 (`b5b12c12`), with §4.2's `--campaign` list. **Met** before round 1's launch, `--campaign cmp_9c9df268084a`:
   61 step markers and 17 goal markers; none found outside; nothing unsearched.
7. **The engine's callers can be read** (the owner chose "2 metrics"). `scripts/dev/engine_callers.py`, which the
   supervisor builds (§4, "The engine's other callers"), exists, is merged, and has been read once against the live
   engine, with the counter's key labels confirmed. **Met:** #2823, merged as `f69ce0e2`; its first reading from main,
   at 23:24:54Z, read the counter by `key` and `status` (`squadops`: 10 replies, all `200`) and both gauges at 0.

**What must be true before the set is registered:**
8. **The shakeout loop's exit rule holds on the final deploy** (§3): one shakeout campaign with no new seam finding.
   **Met in round 1** (§14): `cmp_cea660c0a6a6`, 23:26–00:50Z. The loop took one round of three.
9. **The always-pass sets are fixed** (§4.1). **Met by Track B's re-read**
   (`docs/plans/verification-sets/2-5-0-reread-preregistration.md` §6), on `…eslint10.12-7`. It stays met while
   nothing it read has moved. Every baseline tree is re-read on the final deploy before registration if the final
   deploy's `EVALUATOR_IMAGE` is not `…-7`, or if anything under `src/squadops/scenarios/`, `src/squadops/sandbox/` or
   `adapters/sandbox/` changes after `10a35adb`, the re-read's commit. **Still met at registration:** the evaluator is
   `-7`, and no file under those paths differs between `10a35adb` and `f69ce0e2`.
10. **The repeats the owner chose have run on the final deploy,** after condition 8, and their readings are in §8
    (§6.3). If the engine's reading changes between condition 4 and registration, the repeats run since the change
    are run again. **Met:** `z_shelfnote` (`cmp_725a9e2ee446`) and `z_continuum` (`cmp_d30d964599df`), 00:58–02:22Z,
    and the missing-route replay (§14). The engine didn't change.
11. **The pins are read** (§7), and nothing in the set has launched. **Met** at 02:30Z on 2026-10-30.

**#2751 is closed** by #2821 (`7e631321`): `worktree_hygiene.py` now judges only the checkout's own worktrees and
keeps another tool's checkout wherever git lists it, so the release cut's step 8 no longer threatens the nostromo
shared-inference worktree (`~/.config/nostromo/shared-inference/squadops-reviewed`). Step 8's preview is still read
before `--apply`, as the cut's procedure says.

---

## 1. What the set measures

2.5 is a stabilization release (odd minor), feature-free by rule. It carries a Campaign on a repository-backed Project
(Track A), the yardstick re-cut once (Track B), and the checks, correction loop, structure and operations the 2.4 line
found weak (Tracks C to E). The counted set reads what those changed on the sample applications' paths, which every
2.4 baseline ran (§4.3). Track A's own claim is read by the demonstrations and their repeats (§6). The set measures:

| claim | read from | not a substitute for it |
|---|---|---|
| greenfield building did not regress on either stack on the final deploy | each roll's verdict, criteria, correction rounds and boot audit, against §2's eleven baselines | a clean campaign |
| the rolls are IR-10 on the cut deploy: the cadence and pulse paths are inert, and the correction rounds go through the baselines' handlers | P5, which carries IR-10's R3 and R4 | IR-10's 2.4 readings |
| **the line's changes to QA lose no held-out scenario and add no rounds from QA's own tests:** D12, #2664's guard, #2297's declared routes, #2727's spent rounds, #2807's and #2812's rendering moves, #2816's run tree and, on Next.js, #2602's page example | Q1 and Q2 on revision 6, against §4.1's sets and §2's baselines | #2253's replays, which read stored calls, not builds |
| **D12's note reaches every QA first call, and only those** | Q6 | its loaded check, which reads the source |
| **the PRD's list order removes the order question** (D3, #2557) | Q7, on the rolls' plans and the shakeout's calibration | a re-read of old trees, which can't show a plan's behaviour (the plan's §2.2) |
| the campaign evolves the app unattended on the final deploy, with Outcome Evaluation reporting, §4.5's evidence shown, each increment's records and framing as 2.5 left them, and Track A's changes inert on a sample application | the shakeout's cycles, gate decisions, evaluations, records and close (P4, Q3, Q4, Q8, Q9, Q10) | the rolls, which run no campaign; Track D's uncounted run, which a later merge voided (§6.2) |
| no scenario step or goal reaches a squad role on the final deploy | Q5's sweeps over the shakeout | the demonstrations' IR-4 sweeps |

**Beside the set, uncounted, on the final deploy:** IR-1 and IR-2, by the 2.4 integration record's recipe with one
change to IR-2, IR-8's registry half if §12's proposal is taken (§6.1), and the repeats the owner chose (§6.3). IR-10
is the set itself. An IR-1 or IR-2 that can't run on the Spark reports *not run* with §8.5's four fields (G5). They
don't change the set's verdict.

---

## 2. The set

- **Regression rolls: two per stack** (2.4's number), `fullstack_fastapi_react` and `nextjs_ts`.
  - They run on `validated-fullstack` with `full-38-tf`, project `group_run`, launched by the verification-set driver
    one roll at a time, in one chain from the main checkout.
  - Their configs are carried from the 2.4 cut's (`docs/plans/verification-sets/2-4-0-cut-regression-*.yaml`). What
    changes: the name, the records home (`var/verification_sets/2-5-0-cut/`), this pre-registration, the notes, every
    row of `scripts/dev/loaded_checks.yaml` tracked, and the final deploy's pins.
  - **Every launch declares `memory: disabled`,** the driver's `MEMORY_DECLARATION`
    (`scripts/dev/verification_set_driver.py:1195`, the 2.2 plan's D12, carried). No lesson, project instruction or
    task instruction is supplied, which is IR-10's `lessons: disabled`.
  - **The plan gate** is approved with the set's constant notes. Where the plan has no open question, it is decided
    by `system:no_open_questions` (`src/squadops/cycles/manifest_authoring.py:98`). Either way it is data. Each plan's
    open questions are kept for Q7.
  - **The held-out readings run after the chain's last roll.** Each roll's accepted tree is read against revision 6
    (`89bffc19…`) once, by `scripts/dev/read_scenarios.py`, on `…-7`, the tool and evaluator that read §4.1's
    baselines. The tool boots each app in the sandbox, so it never runs beside a roll. It writes a record with no
    campaign, so it changes no campaign's reading.
- **The baselines: the 2.4 cut's eleven greenfield trees,** all re-read by Track B on revision 6 and `-7`
  (`2-5-0-reread-preregistration.md` §6). That reading's R1, R1b and R2 hold: no HTTP result of 275 and no page result
  of 66 moved from `-5`, and only #2659's changed scenario differs between the revisions. So each tree's passed count
  is the same on all three readings, and the counts and ranges below carry from 2.4.
  - **2.4's seven baselines,** read before #1966 (the 2.4 cut's §2): IR-10's pair and five campaign calibrations.
  - **2.4's four counted rolls,** read with #1966 (the 2.4 cut's §13). They are 2.4.0's shipped behaviour, so they
    are baselines here. They were read, never used to derive an always-pass set (§4.1).

  | tree | deploy | stack | verdict | correction rounds (by repairing task) | QA repairs whose retest passed | passed on revision 6 |
  |---|---|---|---|---|---|---|
  | window c1's calibration `cyc_4145fa7e4b4a` | `dep_19dfa94c0a0a` | FastAPI + React | accepted | 0 | 0 | 11 |
  | window c3's calibration `cyc_413e75801797` | `dep_19dfa94c0a0a` | FastAPI + React | accepted | 1 (`qa.test_repair`) | 1 | 11 |
  | §4.5's calibration `cyc_f34b2bc781ee` | `dep_1aa6d6f1c4e0` | FastAPI + React | accepted | 1 (`qa.test_repair`) | 1 | 11 |
  | IR-10 `cyc_00f7cec8da9b` | `dep_1b38de8af6b4` | FastAPI + React | accepted, 21/21 | 0 | 0 | 6 |
  | 2.4 roll 1 `cyc_de4b598fb1d2` | `dep_d7ff50b9b39c` | FastAPI + React | accepted, 22/22 | 2 (`development.correction_repair`) | 0 | 13 |
  | 2.4 roll 2 `cyc_1aa7a36f28b1` | `dep_d7ff50b9b39c` | FastAPI + React | accepted, 21/21 | 1 (`qa.test_repair`) | 1 | 11 |
  | window c2's calibration `cyc_23232c9e72da` | `dep_19dfa94c0a0a` | Next.js | accepted | 0 | 0 | 11 |
  | window c4's calibration `cyc_42ad92a3290d` | `dep_19dfa94c0a0a` | Next.js | accepted | 2 (1 `builder.assemble_repair`, 1 `development.correction_repair`) | 0 | 11 |
  | IR-10 `cyc_17dcac259f6f` | `dep_1b38de8af6b4` | Next.js | accepted, 24/24 | 3 (2 `development.correction_repair`, 1 `qa.test_repair`) | 1 | 12 |
  | 2.4 roll 1 `cyc_0b6cbf9ab49c` | `dep_d7ff50b9b39c` | Next.js | accepted, 17/17 | 0 | 0 | 9 |
  | 2.4 roll 2 `cyc_007ec7f73c86` | `dep_d7ff50b9b39c` | Next.js | accepted, 19/19 | 1 (`development.correction_repair`) | 0 | 10 |

  **The ranges:** correction rounds 0–2 on FastAPI + React and 0–3 on Next.js; at most one QA repair whose retest
  passed on any tree; passed scenarios 6–13 of 31 on FastAPI + React and 9–12 of 31 on Next.js.

  **Read by `qa_rounds.sh`,** carried from `var/verification_sets/2-4-0-cut/` into `var/verification_sets/2-5-0-cut/`:
  - **a repair round** is a `Dispatched task repair-<run>-NN-sNN-<type> (<type>)` line in the implementation run's
    flow-run log;
  - **its retest** is the first `patch_retest …` line after it, before the next repair.

  A round that #2521's rule spends or #2664's guard refuses is routed to `continue` without patch acceptance (#2727,
  #2746), so it has no retest and never counts as passed.
- **The shakeout campaign:** one campaign of **two increments** on FastAPI + React, opening with its calibration
  (`examples/03_group_run/campaigns/2-5-0-cut-shakeout.yaml`). It is the 2.4 cut's shakeout, carried, with **one
  change: `scenario_suite` is revision 6** (`89bffc19…`). Field for field it is Track D's definition
  (`2-5-0-track-d-uncounted.yaml`), and its launches resolve to the 2.4 window's pinned config hashes
  (`test_request_profile_taxonomy.py`, which now reads it).
  - **The ruling rule is §4.5's, as at 2.4:** each proposal is approved as it stands, at version 1, unless the rails
    refuse it. A criterion the accepted app already meets is §24bq's row 16, as in 2.4's round 2. **The owner's
    "Return such a criterion"** (the demonstrations' deviation 2, for a product's criterion that its framework's
    default behaviour already meets) **is not applied here** (recommended; the owner's to confirm, §12): it was chosen
    for product Campaigns, and §24bq's row 16 already answers it on a sample application.
  - **Its calibration reads D3** (Q7). It runs through `validated-fullstack`, the rolls' profile, under the tier.
  - **Its create `--reason` names its definition file** and this document. `provenance.yaml` matches a campaign to
    definitions by their fields, and this one's equal Track D's, so only the reason tells them apart.

  Plan gates stay `tier`. The increment gate is never the tier's, so the delegate rules each proposal by that rule. It
  is the exit rule's shakeout (§3) and the set's campaign reading. It is uncounted. A new seam finding in it is fixed
  and re-run before registration, never counted.
- **What the sample can say:** four rolls and one campaign show:
  - the final deploy working on both stacks;
  - the line's QA changes running without a loss Q1 and Q2 can see, on greenfield builds and across two increments;
  - D12's note where it belongs, and the order question gone or not;
  - the campaign's unattended path, with the yardstick on and 2.5's increment records written.

  They are not a reliability rate, and the record says so.

---

## 3. The frame

- **The shakeout's exit rule:** one shakeout campaign on the final deploy with no new seam finding (2.0's rule).
  - **A seam finding** is a framework defect the shakeout shows. That includes a falsification of P4, Q4, Q5, Q6, Q8,
    Q9 or Q10 whose cause is in the framework.
  - **A finding is fixed,** the deploy rebuilt, the engine read again (condition 4), the sweeps' baselines re-taken
    (§4.2), and the shakeout re-run. The record reports how many rounds it took.
  - **A round on a changed engine is void:** its `Args`, `.Image` or `State.StartedAt` after the round differ from
    before it. It doesn't spend the budget. A changed `Args` or `.Image` also means condition 2 is redone first.
  - **The budget is three rounds.** A fourth goes to the owner with the findings.
  - **A falsification of Q3 or Q7,** or of P4, Q4, Q5, Q6, Q8, Q9 or Q10 with no framework cause, goes to the owner and
    isn't counted as a seam finding.
  - **A launch the crews' load holds back is data.** A campaign launch is refused while an engine is serving a request
    the launch didn't start (`src/squadops/campaigns/box.py:89-110`, read at
    `src/squadops/campaigns/box_reading.py:104-107`). The launcher records it as `launch_blocked` and tries again
    (`launch_blocked_interval_s` 300, `launch_blocked_attempts` 6). It is not a seam finding.
  - **If the crews' load outlasts the attempts,** the campaign escalates after the sixth, about 30 min, and only the
    owner resumes it (`src/squadops/campaigns/launch_blocking.py:9`, `:76`;
    `src/squadops/campaigns/launcher.py:16-19`). The record counts that resume as an intervention in an unattended
    campaign. It is data, not a seam finding, so a round with such an escalation can still meet the exit rule,
    **provided the metrics show the crews' load caused it**: another key label's requests counted, or the gauges at
    the threshold (§4), at each refused attempt.
  - **A fix re-applies the plan's §3 rule** to every reading §6.2 lets stand, by the paths named there.
- **The chain** runs the four rolls back to back. It stops on a roll that is refused, fails, or isn't accepted, as
  2.4's did. Q1, Q2 and Q6 are read after the chain, so they never stop it.
  - **A create the crews' load refuses is not a refused roll.** The create route refuses a launch while an engine is
    serving a request it didn't start (409 `BOX_REFUSED`, `box_not_quiet`;
    `src/squadops/api/routes/cycles/cycles.py:858-871`). Nothing ran, so the roll is launched again once the engine is
    idle, by the driver's `chain --resume` (`scripts/dev/verification_set_driver.py:7140`), and the record names each
    such refusal with the metrics read at it.
- **Pass:**
  - **every regression roll is accepted, and its boot audit passes;**
  - **no roll regresses against its stack's baselines beyond variance:** every criterion is verified, and correction
    rounds stay within 0–3 on both stacks. That is 2.3's range on TensorFold, carried. §2's eleven baselines read 0–2
    on FastAPI + React and 0–3 on Next.js;
  - **P1–P3, P5, Q1, Q2 and Q6 hold.**
- **Q7 is outside the verdict.** It reads the PRD, not a build. Its reading goes to the owner and to #2557.
- **Fail:** a roll not accepted, a boot audit failing, or one of those predictions falsified. The record reads the
  cause. A framework defect is fixed, which voids the set, and the set restarts on the fix's deploy after a shakeout.
  A failure whose cause isn't found in the framework goes to the owner, and nothing restarts without the owner's
  ruling.
- **D12 carries no revert rule:** the owner chose "No revert rule" (2026-10-29). 2.4's rule for #1966 was the owner's,
  set when #1966 was adopted; the plan's D12 text sets none. So a falsification of Q1 or Q2 is read as any fail is:
  - **the record reads its cause.** A framework defect is fixed, the set voided, and restarted after a shakeout;
  - **a cause not found in the framework goes to the owner** with the reading;
  - **Q1 and Q2 can't attribute a loss to D12 alone.** They read every QA change since 2.4's rolls together: D12,
    #2664's guard, #2297's declared routes, #2727's spent rounds, #2807's and #2812's rendering moves, #2816's run
    tree and, on Next.js, #2602's page example (§4.3);
  - **if the owner reverts D12 on such a reading,** the set restarts once on the revert's deploy, after a shakeout,
    with Q6 and P2's `2253` row dropped, since what they read is gone.
- **Inconclusive:** a roll ended by a cause outside the framework, such as a box halt or TensorFold failing to serve.
  It is re-run under 1.8.2's void rule, and it doesn't spend the budget.
  - **Another caller's load** makes a roll inconclusive **only on the engine's own metrics** (the owner chose "2
    metrics"): another key label's requests counted across the roll's window, and the gauges at the threshold at the
    time of the failure that ended the roll (§4, "The engine's other callers"). Never on assertion.
  - **An engine restarted within a roll's window,** its `State.StartedAt` changed with the same `Args` and `.Image`,
    makes that roll inconclusive, as TensorFold failing to serve (P1).
  - **A held-out reading whose evaluation never started its tree** (`read_scenarios.py` exits 1) is re-read once, on
    the same tree.
  - **A second reading that doesn't start** leaves that roll's Q1 inconclusive, and it goes to the owner.
- **Data, not failure:**
  - a correction round inside the range, a repaired qa suite, and lint findings;
  - a plan gate decided by `system:no_open_questions`;
  - a plan gate the tier escalated in the shakeout, answered by the delegate within the bound;
  - a frozen criterion rejecting a later increment in the shakeout (Q3's note);
  - a round #2521's rule spends (`repair_dropped`), a repair #2664's guard refuses (`slot_subject_dropped`), and a
    `contract_assertions_match` refusal that names the router's own answer (#2297), each with its carry entry;
  - a development task #2795's merge rule drops, with its operator note;
  - a launch the crews' load holds back or refuses, as above;
  - **correction rounds the crews' load may have added without ending a roll** (a call slowed or cut while another
    caller held the engine). They count toward the range as any round does, and each roll's rounds are reported beside
    the counter's other-key totals for its window.
- **A finding in a repeat** (§6.3):
  - **on the narrowed product path,** #2818's class (a product's in-cycle verification, #2799 among it): filed, not
    fixed. The narrowing already names it;
  - **on a claimed reading** (IR-3, IR-6, IR-7, IR-8 or #2780's anchored page): to the owner before any fix;
  - **any fix** is a merge and a new final deploy, so the loop restarts at the shakeout.
- **No merge from the exit rule's round to the set's last reading.** A merge between the exit rule and registration
  re-applies the plan's §3 rule to the round and the repeats. A fix during the set voids it, and it restarts on a new
  deploy after a shakeout.

---

## 4. The predictions: each names a mechanism and how it is falsified

P1–P5 and Q1–Q5 keep 2.4's numbers, so each reads against its 2.4 reading. Q6 to Q10 are 2.5's.

**In the four rolls:**

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | every model call in every roll is served by TensorFold, on `qwen3.8-27b-tf-nvfp4` (2.3's P1), **by the frozen recipe's engine through the chain** | the agents' per-call metrics over each roll's window: `squadops_llm_call_seconds_count` by `engine` and `model`; the engine's `Args`, `.Image` and `State.StartedAt` (condition 4), read at registration and at each roll's start and end, beside the counter (§4, "The engine's other callers") | any call counted under another engine or model in a roll's window, or an engine whose `Args` or `.Image` differ from registration's. **A changed `State.StartedAt` alone** (the same line and image, restarted) makes the roll whose window holds it inconclusive, as TensorFold failing to serve (§3), and it re-runs |
| P2 | every tracked loaded check answers its expected value in every roll, `2253` (D12) among them, reading `True True False True True` | each roll's record, its "Loaded, not built" section | any tracked row unanswered, or answering a value other than its `expect` |
| P3 | **memory stays disabled** (2.3's P3 and IR-10's R6): every roll's cycle declares memory disabled and pins only a disabled snapshot with no entries; every consuming task records a `memory_disabled` exposure; no instruction is supplied; every captured envelope reconstructs byte for byte. #2184 retired the legacy per-agent store (#2735, row `2184`), so this is SIP-0110's memory alone | each roll's cycle row, `memory_exposures`, and `verify_authoring_envelopes.py` | a pinned snapshot that is enabled or holds an entry; a consuming task with **no exposure** or another status; a supplied instruction; or an envelope that does not reconstruct |
| P5 | **the cadence and pulse paths stay inert, and every correction round goes through a handler the baselines used** (IR-10's R3 and R4) | each roll's applied defaults, `pulse_verification_records`, the record's "repair responses by revision form" row and its emissions by handler, and the runs' rows | any of the four falsifiers below |
| **Q1** | **no held-out scenario is lost:** on each roll's tree, every scenario in its stack's always-pass set on revision 6 reads `passed`. That is 5 on FastAPI + React, its page scenario included, and 4 on Next.js (§4.1) | each roll's revision-6 reading on `…-7`, against §4.1 | any always-pass scenario reading anything but `passed`, `blocked_unverified` included, on a reading that started its tree |
| **Q2** | **no extra rounds from QA's own tests:** no roll has more than **one** `qa.test_repair` round whose retest passed. That is the most any of §2's eleven baselines had | each roll's flow-run log, read by `qa_rounds.sh` (§2) | a roll with two or more such rounds |
| **Q6** | **D12's note reaches every QA first call, and only those** (#2759). Every captured authoring envelope of `qa.test` and `qa.test_repair` ends with a user message whose content **equals** `request.keep_reasoning_short`'s text, "keep any reasoning short so that the output fits." (sha256 `f18fdf38…`, #2759's evidence). No envelope of another task type has a message whose content equals it. Equality is the test, since the cut-off re-ask's asset embeds the same clause in a longer message. The note is appended in `_llm_call` on a call that isn't a self-evaluation pass (`src/squadops/capabilities/handlers/cycle/base.py:1472-1478`), for the two steps `TaskType.first_call_keeps_reasoning_short` declares (`src/squadops/tasks/task_types.py:99-103`), and the envelope is captured from those messages | `authoring_envelopes` for each roll's runs, by `task_type`, each envelope's messages | a `qa.test` or `qa.test_repair` envelope whose last message isn't the note; or an envelope of any other task type with a message equal to it. **A roll with no `qa.test` envelope** leaves Q6 void for it, not held |
| **Q7** | **the core list's order is no longer an open question** (D3, #2811): no roll's plan asks in what order the core list shows runs. The PRD's §5.2 now says the list shows runs in the order they were created, with date sorting left in Expansion Tier 1 | each roll's design's open questions, in its interface manifest, which its plan gate reads | a roll's plan whose open questions ask the list's order. **Outside the verdict** (§3) |

**P5's falsifiers:**
- a declared `cadence_policy` or `pulse_checks` in a roll's applied defaults;
- any `pulse_verification_records` row for a roll's runs;
- a correction round through a handler other than `development_correction_repair_handler`,
  `governance_correction_decision_handler`, `qa_test_repair_handler` and `builder_assemble_repair_handler`. Those are
  the four the baselines used;
- any run carrying a binding hold, a halt or a restart.

**Two correction changes are read beside P5, as data.** #2727 spends a repair whose every file write was dropped,
where it was refunded, and #2746 refuses a slot repair that drops its failing assertion's subject. Both run inside the
same handlers, and both are ruled changes (SIP-0107 §22's reading, extended; SIP-0104 §13f). So under IR-10's text ("a
difference in pulse or correction behavior is a finding") each is a declared difference, not a finding. The record
counts each `repair_dropped` round and each `slot_subject_dropped` refusal, with its carry entry.

**Reported beside Q6, not predicted:** the QA calls cut at the output cap or exhausted by it (the agents' emission-shape
lines, labelled `…:cap_truncated` and `…:cap_exhausted`), and QA's tokens, against 2.4's four rolls. #2253's read
replayed 46 calls the cap had cut. Four rolls can't show a rate.

**What Q7 can and can't show.** It reads absence over five plans at most, and the question was intermittent before D3
(#2557's comment of 2026-10-20: Next.js round 10's calibration passed its gate without it). So Q7 can falsify D3, but
holding can't show D3 removed the question. If it holds, #2557 closes on the reading with that limit, and with its
departures from its done-when ("a calibration on each stack passes its plan gate without this escalation") recorded on
the issue: the reading's limit, and the Next.js half read on rolls if §12's proposal is taken.

**The engine's other callers** (the owner chose "2 metrics"). The crews keep running. Each roll's window, and each
shakeout round's and repeat's, is read on TensorFold's own `/metrics` by **`scripts/dev/engine_callers.py`,** a new
script the supervisor builds (condition 7; this document doesn't build it). It reads `/metrics` inside the deploy,
with the key the deploy holds, and never prints a key. It records:
- **`tensorfold:requests_total{key,status}`,** a cumulative counter of HTTP replies by API key label and status, at
  each roll's start and end, beside the engine's `State.StartedAt` (P1). Any increase on a label other than the
  deploy's own (`squadops`, #2742) is another caller's requests in the window. Its source,
  `tensorfold/server/metrics.py:98-105` and `:167-168`, was read inside the image `squadops-tensorfold:0.6.6-cb2ebf05`
  for this draft (read-only, 2026-10-29). The script's first reading against the live engine confirms the family and
  its labels (condition 7);
- **the gauges `tensorfold:requests_running` and `requests_waiting`,** the two the adapter already reads before each
  request (`adapters/llm/tensorfold.py:391-403`), every 5 s through the window. **The threshold:** the frozen recipe
  serves one lane, so `requests_running + requests_waiting ≥ 2` while the squad has a call out is another caller's
  load.

They are reported beside P1 and decide nothing, except as the only evidence for "another caller's load" (§3). A
restart of the engine resets the counter, which `State.StartedAt` shows (P1).

**In the shakeout:**

| # | prediction | read from | falsified by |
|---|---|---|---|
| P4 | every plan gate whose plan meets the tier's conditions is approved by it, with `decided_by = system:plan_review_tier` and each condition's reading in the notes; a gate that fails one escalates (2.3's P4) | the shakeout's gate decisions and escalation rows | a qualifying gate decided by anyone else, a tier approval missing a condition's reading, or a tier approval on a gate that fails a condition |
| Q3 | **no accepted increment breaks what an earlier one built** (2.4's Q3): no accepted increment reads a scenario `regressed` | each accepted increment's `contribution.regressed` in the campaign's package, now version 8 (`src/squadops/campaigns/evidence.py:39`; #2762, #2788 and #2797 each moved it on from 2.4's 5) | any scenario in an accepted increment's `contribution.regressed`. **Counted as data:** each frozen criterion that rejects a later increment |
| Q4 | **§4.5's evidence reaches each proposal** (§10v's E0, as 2.4 carried it): each proposal's authoring envelope (`seam = proposal_writing`) carries `inputs["proposal_evidence"]` with goals, and its rendered request carries the goals section | each proposal's envelope and rendered request. A proposal is the run whose change request the increment gate ruled on | a proposal without them. **Counted apart, and not a falsification:** a proposal shown no goals because the tree it proposed on has no evaluation by the campaign, and a goal the reader holds back for quoting a marker (`carries_a_marker`, which #2794 widened). **Reported:** whether each proposal also carried its quality moves, which #2762 holds to the measures shown before `-7`, and its accepted PRD |
| Q5 | **no step value or goal leaves where it belongs** (§10v's E3 and E4, carried) | `heldout_sweep.py` and `heldout_sweep.py --goals`, run after the shakeout, against §4.2's baselines, read as §4.2 says | E3: a marker whose provenance the baseline didn't find, outside the suite's store and the evaluator's records, or a place that couldn't be searched. E4: any new hit outside the excused places, a `no_task_span` LangFuse row the shakeout wrote, or a place that couldn't be searched |
| Q6 | as in the rolls, on the shakeout's `qa.test` and `qa.test_repair` envelopes, so a misplaced note is found before the set | the shakeout's `authoring_envelopes` | as in the rolls |
| Q7 | as in the rolls, and **the calibration's plan gate is not escalated on the list's order** | the calibration's tier reading (the `no_open_question` condition lists each open question, `src/squadops/campaigns/plan_review_tier.py:112-123`) and its escalation rows | an open question on the list's order, or an escalation on it. **To the owner, not a seam finding** (§3) |
| Q8 | **each cycle names its own increment** (#2578; Track D's R1–R4, carried): the calibration carries no `increment_id`; each increment carries its proposal id, the one its own launch's `campaign_proposal` block names; a repair or retry carries its increment's id, and a re-proposal a new one; each flow run carries `kind:<kind>` and, but for the calibration's, `increment:<id>`; the ledger lists each proposal version's cycles in launch order, its outcome its last cycle's row; no decision cites a tag | `cycle_registry.increment_id` against the control log's launch rows; Prefect's flow-run tags; `GET /api/v1/campaigns/{id}/ledger` (`2-5-0-track-d-campaign-preregistration.md` §3) | any of Track D's falsifiers. A repair, retry or re-proposal the campaign never launches is reported *not exercised*, never *passed* (§12) |
| Q9 | **an increment's criterion file is the QA task's at the merge** (#2802, SIP-0093 §15b): no increment's framing is refused for a criterion file that a development task and a QA task both claim, and no merge fails for a missing or unreadable list of them. A sample application's increment framing runs the plan proposers (`src/squadops/contracts/cycle_request_profiles/profiles/campaign-increment.yaml:8-14`), so the merge's rule applies to it, with the list composed for it (`src/squadops/capabilities/context_assembly.py:437-441`) | each framing run's plan-validation refusals and their reasons; the merge task's outcome; the merge's decisions document | such a refusal or failure. **Reported, as a count:** each criterion file moved to the QA task, and each development task the rule dropped, with its operator note. **A count of zero** means the rule's move wasn't exercised, though its list was |
| Q10 | **Track A's changes leave a sample application's campaign as it was:** the calibration is a cycle, and no calibration record is written (#2738); no accepted tree names a commit, and no `branch_rebased` row is written (#2740, #2770; a sample application never rebases, `src/squadops/campaigns/branch_rebase.py:223-227`); no cycle carries a source context (#2761, #2763); every increment's plan carries `qa.evaluate_increment` (#2774); and the hearing refuses no promotion or move to `evaluating` as stale, and logs no `campaign_not_decided_campaign_moved`, without an owner action behind it (#2792) | the control log, `cycle_registry.source_context`, each increment's task plan, and the runtime's log | any of them |

**Q5's positive control:** every goal the proposals were shown is found in the excused places
(`goals_not_found_in_proposals` lists none of them). If any isn't, E4 is void, not held, because the sweep didn't find
what it looks for.

**Read beside the shakeout, without a prediction:**
- the campaign's ending and each cycle's verdict;
- the cycle-end evaluations on revision 6, reported only, and each record's `start_failure`, with its cause where a
  start failed (SIP-0113 §10ae, #2797);
- whether #2664's `slot_subject_dropped`, #2743's namespace rule or #2297's empty-segment refusal fired;
- a declared catch-all client route read at `/__squadops_unmatched__` (#2755), if the calibration's manifest declares
  one;
- each `launch_blocked` row the crews' load caused, with the metrics read at it.

### 4.1 The always-pass sets (Q1)

A stack's always-pass set is every revision-6 scenario that reads `passed` on **every** one of its baseline trees, as
2.4 defined it (the 2.4 cut's §4.1): 2.4's four FastAPI + React and three Next.js pre-#1966 trees. 2.4's counted rolls
are read, never used to derive a set (`2-5-0-reread-preregistration.md` §4).

**The sets, on `…eslint10.12-7`** (`var/verification_sets/2-5-0-recut/always-pass-rev6.json`). They are 2.4's sets, id
for id:

| stack | baseline trees | always-pass set on revision 6 | its scenarios |
|---|---|---|---|
| FastAPI + React | 4 | **5** of 31 | `a-created-run-is-listed`, `a-created-run-reads-back`, `a-run-needs-a-title`, `a-runner-joins-from-the-run-page` (a page scenario), `an-unknown-run-is-not-found` |
| Next.js | 3 | **4** of 31 | `a-created-run-is-listed`, `a-created-run-reads-back`, `a-run-needs-a-title`, `an-unknown-run-is-not-found` |

**A roll and its baselines are always read by one evaluator and one runner:** if either moves before registration,
every baseline tree is re-read on the final deploy first (condition 9).

**What Q1 reads: the whole set, 5 and 4** (proposed; the supervisor's to confirm, §12). 2.4's Q1 read the HTTP
scenarios only and reported the page scenario beside them (the 2.4 cut's §12), because the browser driver could read a
correctly built field as absent when its label ended with a colon (#2706). `-6` reads such a label (#2717, SIP-0113
§10x), and `-7` keeps the browser path byte-identical (#2762). The page scenario passed on all six FastAPI + React
trees of §2, both 2.4 rolls included, and no page result moved on the re-read (R1b). The alternative is 2.4's rule:
the HTTP scenarios predicted, the page scenario reported.

**The spread between builds is wide,** as at 2.4: passed counts run 6–13 on FastAPI + React and 9–12 on Next.js
(§2). A scenario that needs a behaviour one build has and another lacks is outside the set. So the sets are small, and
Q1 is a narrow instrument: it reads only what every pre-#1966 build did. It reads a loss, not a gain.

**Reported beside Q1, not predicted:** each roll's count of passed scenarios, against its stack's range in §2, and each
scenario outside the set whose result differs between the rolls and the baselines. D3's PRD line is every roll's input
(§4.3), so a list-order scenario's result can move with it, and the record names any that does.

**What Q1 can't see:**
- **Scenarios blocked on every baseline tree.** They are outside every set, and Q1 says nothing about them.
- **Public values.** Revision 6 replaced the eight revision-5 step values already public (SIP-0113 §10w). #2794 later
  widened the markers to a step's path segments (§10ad). Whether any revision-6 value is public under that reader is
  the supervisor's count after #2794, not this document's. Either way it weakens holding out, not the reading of a
  tree: no squad role reads the repository's history or the vault's other trees.

### 4.2 The sweeps' baselines (Q5)

**Before each shakeout round's launch,** on its deploy, both sweeps run over every place §10v's sweep named, and their
reports are kept in the record's directory. A rebuild changes the images a sweep searches, so each round takes its own.

**The command:** `heldout_sweep.py --suite <revision 6's file> --digest 89bffc19 --campaign <list>`, and the same with
`--goals`. The databases and the containers are searched whole. `--campaign` names the campaigns whose cycles' vault
trees are walked (`heldout_sweep.py`'s `window_cycles`):
- **the list is every campaign that pins revision 6 when the baseline is taken.** Today that is Track D's
  `cmp_9c9df268084a` alone (`campaign_scenario_suites`, read 2026-10-29), and a later round adds the rounds before it;
- **the baseline and its reading take the same list,** and the reading adds only the round's own shakeout campaign;
- **each list goes in §8.**

**How "new" is read** (§4.5's pre-registration §4, carried). A sweep keys its marker ids fresh for each run
(`heldout_sweep.py`'s `_KEY`), so ids don't compare across runs. A marker's provenance (its scenario, and the step or
check it's from) does. For E3, a marker whose provenance the baseline found is known, and only the others can
falsify. For E4, any goal outside the excused places that the baseline didn't find is new. The excused places are:
- the proposals' authoring envelopes;
- their LangFuse generations, attributed by the `task-…` span each hangs under;
- the evaluator's records.

**The marker definition changed since 2.4** (#2794, SIP-0113 §10ad): a step's path is read segment by segment, a
declared route's words are no marker, and a whole `{name}` reference is none. So 2.4's count of provenances (8) doesn't
carry. Each baseline and its reading are taken by one reader: `heldout_sweep.py` as main carries it since #2819
(`b5b12c12`), which walks each cycle's vault under its own project.

### 4.3 What 2.5 changed on the set's paths, merge by merge

Every merge in `v2.4.0..origin/main` (75 commits at this revision, #2819 and #2821 the last) was read for whether it
changes a path a roll or the shakeout runs: the agents' code, the runtime's, the evaluator's image, a request profile,
a suite or the PRD (the plan's §3). Six moved a sample application's plan, prompt or correction goldens since
`v2.4.0`: #2727, #2728, #2746, #2749, #2759 and #2802 (`git log v2.4.0..origin/main --
tests/unit/capabilities/handlers/goldens/qa_dev_handle_characterization.json tests/unit/cycles/goldens/`). Each is
read below.

| merge | issue | what it changes on a path the set runs | how the set reads it |
|---|---|---|---|
| #2717 (`e6a00faa`), #2762 (`b850471c`) | #2706, #2659, #2712, #2469; #2637 | the evaluator's `-6` (a label's trailing colon, the `if_enabled` click, the lock) and `-7` (the finer quality reading, reporting only; the proposal's quality moves held to the measures shown before) | Track B's re-read, which fixed §4.1's sets; Q1 on `-7`; Q4's report |
| #2759 (`d31d6e3a`) | #2253 (D12) | the note on each QA first call; the QA prompt goldens gain one message | **Q6**; Q1 and Q2 |
| #2811 (`4bad2a74`) | #2557 (D3) | the PRD's §5.2, every `group_run` cycle's input | **Q7**, and every roll's and the shakeout's build: the verdicts, the criteria, Q1, and the passed counts beside it (§4.1) |
| #2746 (`eaa64d71`) | #2664 | a slot repair that drops its failing assertion's subject is refused, and spent | P5's handlers; each refusal reported (§4); Q1 and Q2 |
| #2728 (`2f70b40f`) | #2297 | the bound QA suite's row carries `declared_routes`; `contract_assertions_match` refuses an empty required segment unless the router's own answer is asserted | each refusal reported; a correction round inside the range is data; Q1 and Q2 |
| #2727 (`326f6c93`) | #2521 | a repair whose every write was dropped is spent, and the next round is told why | P5's handlers; each `repair_dropped` round reported; Q1 and Q2 |
| #2749 (`ca048f36`) | #2602 | on Next.js: the skeleton carries `vitest.pages.ts`, and the QA supplement's page example routes its fetch stub through `callRoute` (`development_profiles.py`); an increment's page appendix | the Next.js rolls (verdict, criteria, rounds, Q1, Q2). **The increment half isn't exercised:** no Next.js campaign runs |
| #2802 (`10a35adb`) | #2795 | an increment framing's merge gives a doubly claimed criterion file to the QA task; the development proposer's appendix | **Q9** |
| #2739, #2741 | #2578 | `increment_id`, the flow-run tags, the ledger's cycles | **Q8** |
| #2807 (`fdd327fc`), #2812 (`6b9ee472`) | #2805, #2810 | every `qa.test` renders its tree through `qa_test_prompt_contents`, and every repair its sections through `repair_prompt_contents`, moved from the handlers; the binding budget counts what each shows | **exercised on every roll as moves:** each handler's prompt is byte-identical by its characterization golden (#2807's, captured from `origin/main`; `repair_prompt_characterization.json`, captured on `cf1fbe23`). Read by Q1, Q2 and the verdicts. **The budget's binding isn't exercised:** nothing in the set binds an instruction, and a binding hold falsifies P5 |
| #2816 (`d0df8acb`) | #2815 | every QA suite and retest runs on `suite_run_tree`. On a product it is the product's tree; on a sample application it is `source_files`, byte for byte | **exercised on every roll:** `sample_run_tree_characterization.json`, captured on `6b9ee472` before the change, pins all five development profiles on the focused, monolithic and retest paths. Read by Q1, Q2 and the verdicts |
| #2729 (`31dd41c7`) | #2553 | an input refusal reads `input_contract_failure`; `ATTRIBUTION_REGISTRY_VERSION` is 2 (`src/squadops/cycles/failure_attribution.py:57`) | declared (§10): the set's records are read under version 2, every 2.4 baseline's under version 1, and no comparison of attribution classes crosses them |
| #2735 (`b45a23f0`) | #2184 | the legacy per-agent store retired: the agents' images, entrypoint and compose mounts | P3; P2 (`2184`) |
| #2718 (`3dec9c4a`) | #2493 | the agents' service token read on two clocks | P2 (`2493`) |
| #2755 (`178dd9e1`) | #2754 | a declared catch-all route is read at `/__squadops_unmatched__` on an increment's acceptance | the shakeout, if its calibration declares one (§4) |
| #2748 (`b92143ba`) | #2743 | a proposal's scope leaves the stack's QA namespace to the framework; the tier reads the stack from the manifest | the shakeout's proposals and P4's tier notes. Track D saw no verdict change with this scope |
| #2792 (`5e99418e`) | #2789 | the hearing reads the campaign again before writing, and its writes carry the state it read | **Q10** |
| #2794 (`ad6e3ecb`) | #2786 | the marker definition; the runner's placeholder regex renamed, with no behaviour change by its PR | Q5's sweeps (§4.2); Q4's goal filter |
| #2797 (`2f08613c`) | #2793 | a failed start's cause on the evaluation record; the package goes to version 8 | Q3 reads version 8; each record's `start_failure` (§4) |
| #2785 (`693d219b`) | #2784 | a scenario's HTTP checks read the values its steps saved | nothing moves: 0 of revision 6's 59 HTTP checks names a saved value (#2785's count), and R1 held on the re-read's deploy, which carried it |
| #2732 (`0ed38538`) | #2561 | the deploy record names the served weights | a pin (§7). It names the same weights for both recipes, so it doesn't pin the recipe (condition 4) |
| #2738, #2740, #2761, #2763, #2770, #2774 | #2619 | repository-backed paths, each with a sample-application control: a sample application's start launches its calibration cycle, its promotion is from the vault, its launch passes no head, it never rebases, and its increments keep `qa.evaluate_increment` | **Q10**; Q8's calibration row |
| #2716, #2719, #2726, #2734, #2764, #2766, #2769, #2771, #2772, #2773, #2777, #2778, #2780, #2788 | #2619, #2414, #2672, #2757, #2779 | products only. Each names its sample-application control: no profile is asked of a sample application (H.7, H.8), its profiles keep their stack (H.11), its skeleton supplement stays (H.13), its evaluation and package section are unchanged (#2778, #2788). #2780's new prompt sections are optional and empty without an anchor, and the QA and dev prompt golden moved only for D12 | **not exercised on a sample application** |
| #2742 (`5aaece83`) | the owner's, nostromo#3 | the TensorFold key reader, and the two-lane candidate recipe beside the frozen one | conditions 2, 4 and 7 |
| #2720, #2721, #2722, #2725, #2730, #2731, #2747, #2791, #2801, #2803, #2819 (`b5b12c12`), #2821 (`7e631321`) | — | scripts no run executes, loaded-check rows, monitoring, CI and an integration test. #2819 is the sweep's own reader (§4.2) | none, but §4.2 |

**No loaded-check row** reads #2297's, #2521's or #2553's code. The deploy is rebuilt from one commit, and the deploy
record and the image ids stand for them.

---

## 5. The campaign's policy

**The shakeout:** the 2.4 cut's shakeout (`2-4-0-cut-shakeout.yaml`), carried, with §2's one change.

| field | value | basis |
|---|---|---|
| `objective.target_accepted_increments` | **2** | §2, as 2.4 |
| `objective.work_class` | `prd_tier: tier-1`, `attendance: unattended` | as 2.4; the create API requires it |
| `max_cycles` | **7** | 1 calibration, 2 increments, one repair or retry each, 2 replacements: 2.1's rule |
| `ruling_bound_s` | **1800** | 2.3's |
| `plan_gate` | **`tier`** | as 2.4 |
| `squad_profile` | **`full-38-tf`** | as 2.4 |
| `stack` | **`fullstack_fastapi_react`** | as 2.4 |
| `scenario_suite` | **revision 6, `89bffc198c99b6fd347ef51d6263f6e2360a680a42bb4f01138750e44809854a`** | §2; the yardstick re-read in Track B |
| every other field | the 2.4 cut's shakeout | unchanged by this line |

---

## 6. The cross-lane scenarios at the cut

The plan's §3: "The release claim needs the cross-lane scenarios to pass." IR-3 to IR-9 were read on the two
demonstrations (`docs/plans/verification-sets/2-5-0-demonstrations-preregistration.md` §9). The owner narrowed the
claim on 2026-10-29 ("Narrow the claim, go to cut"), and chose "Yes to both" on IR-6's increment half the same day:
IR-5, IR-6's increment half and IR-9's increment reading weren't exercised, and #2818 is placed first in 2.6 or a
2.5.x patch (§11). 2.4's G5 doesn't carry for IR-3 to IR-9: a scenario not run needs the owner's ruling, named in the
cut record.

### 6.1 Beside the set: IR-1, IR-2 and IR-10

- **IR-1, as at 2.4.0** (`docs/plans/2-4-0-integration-record.md`, "At the cut"): one `selftest` cycle of each seeded
  project through `cycles create`, one at a time, each completed with its artifacts. **It runs after the set's last
  reading and before the engine is restored,** so it reads the final deploy; 2.4's took 36 min. A create the crews'
  load refuses is made again once the engine is idle (§3). 2.5 changed the
  create path every cycle takes (`prepare_cycle`: H.8's blocking gap, H.9's pin, H.11's recipe, H.13's blueprint
  pin), each with a sample-application control, so IR-1 reads that each seeded project still creates and runs.
- **IR-2, with one change.** 2.4 compared a standalone cycle with a Campaign's calibration cycle on `prj-z-continuum`
  (`var/campaigns/ir2-cut.yaml`). Since #2738, a repository-backed Campaign's start writes a calibration record and
  launches no cycle (SIP-0109 §24bv point 1, §24cc). So the Campaign's half is its first launched cycle, the
  increment's, which reaches `prepare_cycle` pinned at the record's commit. **It passes when:**
  - both cycles carry the Project's baseline commit and Development Configuration revision, and the same pinned commit
    (H.9: the first increment pins the same tree as a standalone create);
  - `pinned_from` reads `project_baseline` and `campaign_branch`, as H.9 defines them;
  - each pins its own snapshot.

  It is read on §6.3's `z_continuum` Campaign, with the standalone cycle created and cancelled as §6.3 says.
- **IR-10 is the set** (P5 carries its R3 and R4), as at 2.4.0.
- **IR-8's registry half, proposed again** (§12). 2.4 ran it at its cut: a Project imported, read at once, and refused
  a Cycle while `REGISTERING`. 2.5 changed the create path that refusal goes through, so it is worth the minutes. It
  runs beside IR-1, with a fresh id, since `prj-ir8-cut` stays `REGISTERING` on the Spark. Its create is read only
  when the box gate passed it: a `BOX_REFUSED` is the gate's, not the registry's, and is made again on an idle engine,
  as at 2.4.

### 6.2 The demonstrations' readings under the plan's §3 rule

The rule: "A later merge that changes a path an earlier run's cycles executed … voids that run for the release claim.
That run is repeated, or the owner rules on it." It is read here as written, by run: a run is voided when any of its
cycles ran a path a later merge changed. For each voided reading, the table also says whether the merge changed the
path that wrote the reading's own evidence.

The deploys are read from `deploy_records` and `cycle_registry` (SELECTs, 2026-10-29): `dep_6ed09f6b500c` (`5e99418e`)
carried `z_shelfnote`; `z_continuum`'s rounds 1 to 3 ran on `dep_0a4f31cd9c10` (`10a35adb`), `dep_bf4b8db121fc`
(`fdd327fc`) and `dep_8cd26c67fd90` (`6b9ee472`), and round 3's last two cycles on `dep_aa6f0a54c53a` (`d0df8acb`).

| reading | its evidence | written on | later merges that change a path its run's cycles ran | do they change the path that wrote the evidence? | at the cut |
|---|---|---|---|---|---|
| **IR-3**, (a)–(e) | round 3 (`cmp_ce4c95f2f307`): `cyc_60a71c2b2be2` bound the old content; the launch after the sync refused `STALE_SOURCE_PRECONDITION` and escalated until reconciled; `cyc_7e42e45adc6d` bound the new content at its rebased commit; the standalone `cyc_2a817b3e6503` bound the new content; no re-binding row | `dep_8cd26c67fd90` (`6b9ee472`) | #2816: `qa_test.py`, `qa_run_tree.py`, `qa_prompt_contents.py`, `source_repository.py` and `context_assembly.py`, the QA path both increment cycles ran | No. The binding, the launch gate, the reconciliation, the rebase and the create route are outside #2816's files | **repeated** on §6.3's `z_continuum` Campaign: the owner chose to ("1 yes") |
| **IR-4**, `z_continuum`'s suite | the sweep after round 3: no step value outside the suite's store and the evaluator's records, every place searched | the sweep on `dep_aa6f0a54c53a`; the run's cycles on four deploys | round 3's cycles on `dep_8cd26c67fd90`, and rounds 1 and 2: #2807, #2812, #2816 (budget and QA paths) | No: none adds a read of the suite | **repeated:** swept again after §6.3's `z_continuum` Campaign, with baselines before it (minutes) |
| **IR-4**, `z_shelfnote`'s suite | the same sweep | `z_shelfnote`'s cycles on `dep_6ed09f6b500c` | #2794, #2797, #2802, #2807, #2812, #2816 | No, as above | **repeated** by §6.3's `z_shelfnote` Campaign, with its own baselines before it and its sweep after |
| **IR-5** | — | — | — | — | **not exercised** (the narrowing). No repeat |
| **IR-6**, the calibration records | `evl_36103956b2d1`, `evl_4d91d6076c7f`, `evl_600d64517d5a`, one per round: the page scenario and quality not applicable, lint `not_a_scaffold_stack`, nothing started by a stack | `dep_0a4f31cd9c10`, `dep_bf4b8db121fc`, `dep_8cd26c67fd90` | #2807, #2812 and #2816, on paths each round's later cycles ran | No. No merge since `10a35adb` changes `scenarios/`, `campaigns/progress.py`'s hearing, the sandbox's runner or the evaluator's image, and each reading was written at its Campaign's start, before its cycles ran | **repeated** by §6.3's `z_continuum` start |
| **IR-6**, an increment | not exercised: no `z_continuum` increment delivered a tree | — | — | — | **not exercised,** under the narrowing (the owner chose "Yes to both") |
| **IR-7** | `z_shelfnote` (`cmp_73535ccef891`): the record's baseline reading `evl_29bfb2a58ea0`; the increment's `evl_5016d962be49` on its captured tree, 9 of 9 passed; lint by the blueprint's rule set | `dep_6ed09f6b500c` (`5e99418e`) | #2794 (`steps.py`), #2797 (`evaluate.py`, `evaluation.py`, `runner.py`, the sandbox's `scenario_runner.py`), #2802 (the framing's merge, whose refusals #2795 named), #2807, #2812, #2816 | **Yes, for #2797 and #2794:** the evaluation path, an additive field and a refactor whose PRs record no change of behaviour on a start that succeeds. No, for the rest | **repeated** by §6.3's `z_shelfnote` Campaign |
| **IR-8** | the evaluation records name `prj-z-continuum` and `prj-shelfnote`, and `config/projects.yaml` names neither | as IR-6 and IR-7 | as IR-6 and IR-7 | as IR-6 and IR-7 | **repeated** by both §6.3 Campaigns. The YAML half is read on the tagged tree |
| **IR-9** | the increment reading not exercised. The Project's own baseline reads `lint` FAIL `inherited` at `15fc9a77` and `2070ba46` | — | — | — | **not exercised** (the narrowing). No repeat |
| **#2780's anchored page** | the added page's route held by its anchor, in the increment and its repair | `dep_6ed09f6b500c` | as IR-7. Route rendering runs through the sandbox's `scenario_runner.py`, which #2797 refactored | yes, a refactor with no change of behaviour by its PR | **repeated** with `z_shelfnote` |
| **the missing-route negative** (a replay) | `DeclaredStartRoutes.render` on `cyc_7cbdae00b2ed`'s captured candidate, its route removed: broken, the increment rejected | `dep_6ed09f6b500c`, by the script's time | #2797's runner refactor | yes, as above | **replayed on the final deploy** (`replay-2780-missing-route.py`), in minutes |
| **Track D's uncounted run** (#2578) | R1–R4 on `cmp_9c9df268084a` | `dep_fbeecffcc625`, `dep_31949f050a30` | among others, #2759, #2763, #2770, #2771, #2792 and #2802, on the launch, hearing and framing paths a sample-application campaign runs | **Yes:** #2763 and #2771 change `launch_requests.py`, and #2763 and #2770 `campaign_launch.py`, the files that write the launch binding R1 reads | **re-read by the shakeout** (Q8). The void **reverses the plan's §5 judgement,** which named #2763 among the merges that don't touch how #2578's records are written, and was made before #2770 and #2771 merged |
| **Track B's re-read** | R1, R1b, R2; §4.1's sets | `dep_0a4f31cd9c10` (`10a35adb`), `-7` | none: no merge since changes the evaluator's image, the sandbox's runner or `scenarios/` | — | **stands** (condition 9) |

**What the table assumes.** Every reading the table keeps is repeated or re-read on the final deploy, except Track B's
re-read, whose paths no merge has changed. A merge before registration, a shakeout fix among them, re-applies the rule
to every row by the paths named here, and the record names each case.

**The engine isn't one of the rule's paths.** The demonstrations and Track D's run were served by #2742's two-lane
candidate (condition 2). The rule lists the agents' code, the runtime's, the evaluator's image, a request profile, a
suite and the PRD, so the switch to the frozen recipe voids nothing by itself. The record names it (§10).

### 6.3 The repeats the owner chose

The owner chose "Repeat the cheap ones" and, for IR-3, "1 yes" (2026-10-29). Each repeat runs on the final deploy
after the exit rule holds (condition 8) and before registration, so a shakeout fix can't void it, and each campaign's
create `--reason` names its definition file. They read the demonstrations' pre-registration §4, unchanged, except
where named below. **The owner's "Return such a criterion"** (the demonstrations' deviation 2) applies to both, since
both are product Campaigns (recommended; §12). A finding in a repeat is routed by §3's rule.
- **`z_continuum`: one Campaign, which carries IR-2, IR-6, IR-8 and IR-3,** from
  `docs/plans/2-5-0-demonstrations/z_continuum-campaign.yaml` (suite `7ce88042…`), on `prj-z-continuum` at
  `2070ba46`, revision 6, with IR-4's baselines taken before it and project instruction `mrec_54f96f55d3a54ad8` bound
  to `repo:file:CLAUDE.md@current` as before:
  1. **Its start** writes a calibration record and its baseline reading: IR-6's calibration half and IR-8's
     `prj-z-continuum` half.
  2. **Its first launched cycle** is IR-2's Campaign half (§6.1). IR-2's standalone cycle is created while the
     Campaign is paused or waiting at a gate, since the create route refuses a launch while the engine serves a
     request it didn't start (`src/squadops/api/routes/cycles/cycles.py:858-871`). It is cancelled once its snapshot
     is pinned (`memory_snapshots`), before it dispatches.
  3. **IR-3, repeated:**
     - the first increment's cycle runs, and the Campaign is paused while it does;
     - the supervisor pushes one more one-line commit to `CLAUDE.md` on `z_continuum`'s `main`, from the owner's
       account, as for round 3;
     - `projects sync`, then resume;
     - the next launch is held or refused by the Project's own gate until the supervisor reconciles: `projects
       validate`, `configure` (revision 7, the same technical block) and `baseline --capture`. Resuming before the
       reconciliation is the demonstrations' order (their §3), and it is what lets (b) be read;
     - the launcher rebases the campaign branch onto the reconciled commit, and the next cycle launches;
     - a standalone cycle is created after the reconciliation, in the same way as IR-2's (step 2), and cancelled once
       its binding is written, before it dispatches;
     - (a)–(e) are read as the demonstrations' §4 states them.
  4. **The Campaign is aborted** once (e) is read, and IR-4's sweep runs over it.

  **About 1 box-hour.** Its increments are expected to meet #2818 again, which the narrowing names. IR-3 doesn't need
  an accepted increment.
- **`z_shelfnote`: a fresh Campaign,** from `docs/plans/2-5-0-demonstrations/z_shelfnote-campaign.yaml`, its suite
  `a1a6a0b7…` pinned, with IR-4's baselines taken before it and its sweep after. It reads IR-7, IR-8's `prj-shelfnote`
  half, #2780's anchored page and IR-4 on its suite. Then the missing-route replay runs again on its captured
  candidate.
  - **About 1.5 box-hours.**
  - **Expected:** its increment meets #2799 again, so it ends with nothing accepted, as before. IR-7 and the anchored
    page don't need an accepted increment.
  - **IR-4 is read as a leak test,** as the demonstrations' §9 did: no step value outside the suite's store and the
    evaluator's records. Its goal half can't hold on a product, since §4.5's evidence isn't shown to a product's
    proposal (`src/squadops/execution/proposal_evidence.py:38-45`), so the goals are found only in the evaluator's
    records (§11).
  - **It is `z_shelfnote`'s third Campaign,** where IR-7's text says "first". The scenario reads the evaluation path,
    which the count doesn't change, and the record says so.

**Box time, as a guide:** the shakeout about 1.5 a round, the repeats about 2.5, the chain about 2, the readings about
0.5, and IR-1 about 0.6. That is about 7 box-hours with one shakeout round, against the plan's guide of about 6 for the
cut. The supervisor's estimates have run high, so it's a ceiling to report against.

---

## 7. Pins (read at registration)

Read at 02:30Z on 2026-10-30, when conditions 1–10 held:

| pin | value |
|---|---|
| deploy commit | **`f69ce0e2`**: #2823 on #2822's tree, rebuilt at 23:23Z on 2026-10-29 |
| deploy record | **`dep_eb111413d45d`**, the last one written; "describes what runs: 24 services" (`verify_loaded.py` from the main checkout) |
| engine | `squadops-tensorfold`: **`Args`** from `serve` equal `serve_command`'s line for `qwen27b-nvfp4.yaml`, with no `--parallel` (compared in code); **`.Image`** `sha256:b62567b8d89fca5ca126e614162d65b4a6eecaacd63d75699fdf70ff268f45f8`, the recipe's `image_id`; **`State.StartedAt`** `2026-10-29T23:09:10.782597083Z` |
| image ids | **runtime-api `bb84894026a2`, max `3cf4e7e34a36`, neo `8802daa948d8`, nat `b4aa7e8cf1f2`, bob `885fbccf90d7`, eve `cc079a0e97d1`, data `024c789f54eb`**: read from the running containers, equal to both configs' `frozen_image_ids`. The sandbox service: `45acbcd492c0` |
| `EVALUATOR_IMAGE` | `squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-7` (`src/squadops/sandbox/environment.py:43`; image `40cb987918c0`), §4.1's |
| model | `qwen3.8-27b-tf-nvfp4` in every agent (`SQUADOPS__LLM__MODEL`, read in max, neo, nat, bob, eve and data), served by `squadops-tensorfold:0.6.6-cb2ebf05`; weights `hf:nvidia/Qwen3.8-27B-NVFP4@482ca0f3…` (the deploy record, #2561) |
| held-out suite | revision 6, `89bffc198c99b6fd347ef51d6263f6e2360a680a42bb4f01138750e44809854a` |
| squad snapshot | **`a1280ff8ed4398b3`** (`full-38-tf`), read from the deploy's API by the driver's `live_squad_snapshot`; 2.4's |
| loaded checks | 247 tracked rows in each config, every row of `loaded_checks.yaml`. On the deploy, 247 loaded, 0 not |
| set configs | `2-5-0-cut-regression-fastapi-react.yaml` and `2-5-0-cut-regression-nextjs.yaml`, carried from the 2.4 cut's: name, records home, this pre-registration, notes, every row tracked, and these pins. sha256: fastapi-react **`5d3fe39a41a8d8b1…`**, nextjs **`7edb27b1f829c041…`** |
| shakeout definition | `examples/03_group_run/campaigns/2-5-0-cut-shakeout.yaml`, sha256 `241759cb94f63133…` |
| record versions | attribution registry 2 (`failure_attribution.py:57`), campaign package 8 (`evidence.py:39`) |
| HEAD at preflight | **`42d4e395`**, this registration's branch, at both counting preflights (02:28Z and 02:29Z), both clean. The preflight only reads it; roll 1 pins the HEAD it launches from, this registration's merge. Its difference from the deploy commit is the set's configs and this document. Nothing under `src/` or `adapters/` differs |

---

## 8. Records, filled as read

| what | value |
|---|---|
| the engine switch, and the engine's readings (at the switch, after each shakeout round, at registration, at each roll's start and end) | the switch: 23:09:09–23:09:39Z, exit 0 (`var/engine_switch/20261029T230909Z-to-tensorfold.jsonl`). The same `Args`, `.Image` and `State.StartedAt` (§7) at condition 4 (23:23:51Z), after round 1 (00:50Z) and at registration (`var/verification_sets/2-5-0-cut/engine-reading-condition4.txt`). The rolls' readings: — |
| `engine_callers.py`'s first reading against the live engine: the counter's family and key labels (condition 7) | 23:24:54Z from main at `f69ce0e2`: `tensorfold:requests_total` by `key` and `status`, one label (`squadops`, 10 replies, all `200`); `requests_running` 0, `requests_waiting` 0 |
| the final deploy | `dep_eb111413d45d` from `f69ce0e2` (`var/plans-2-5/cut/rebuild-final.log`) |
| the sweeps' baselines and readings, each with its `--campaign` list | round 1's baseline, `--campaign cmp_9c9df268084a`, and reading, `--campaign cmp_9c9df268084a cmp_cea660c0a6a6` (`var/verification_sets/2-5-0-cut/sweeps/`). The repeats' IR-4 baselines and readings in `repeats/ir4/`, each list in its `.campaigns.txt` |
| shakeout rounds, and the round that met the exit rule | **round 1, `cmp_cea660c0a6a6`, met it** (§14; `var/verification_sets/2-5-0-cut/shakeout-round1.md`) |
| the repeats (§6.3): each campaign, the outside commit, the reconciliation, and each reading | `z_shelfnote` `cmp_725a9e2ee446`; `z_continuum` `cmp_d30d964599df`; the outside commit `fad7fba` on `backspring-labs/z_continuum`; the reconciliation at `fad7fba`, revision 7; the missing-route replay on `2d3f3948` (§14; `var/verification_sets/2-5-0-cut/repeats.md`) |
| registration | 02:30Z on 2026-10-30, at `42d4e395` (§7) |
| the chain: each roll's cycle, verdict, criteria, boot audit, correction rounds, QA repairs whose retest passed, model calls | — |
| each roll's window on the engine's metrics: the counter by key label and `State.StartedAt` at its start and end, the gauges' samples, and the other-key totals beside its correction rounds | — |
| the held-out readings | — |
| each prediction's reading | — |
| D3's reading, recorded on #2557 with its departures from the done-when | — |
| IR-1, IR-2 and IR-8's registry half | IR-2 **passes** on the `z_continuum` repeat (§14). IR-1 and IR-8's registry half: — |
| the engine's restoration | — |
| each void and re-run, and each owner action | before registration: no void and no re-run. The owner's actions: "Abandon and propose" (resuming the `z_continuum` repeat) and "Name it, fix after" (#2824). The set's: — |

---

## 9. Prohibited from the exit rule's round to the set's last reading

- **Merging to main.** A merge between the exit rule and registration re-applies the plan's §3 rule to the round and
  the repeats, and a fix during the set voids it. Nothing else merges between opening the release PR and merging it
  (CLAUDE.md, "Release cut").
- **Rebuilding any service, or restarting or switching the engine,** until the set's last reading and the runs beside
  it (§6.1) are done.
- **Running anything else on the box** while a roll runs: the shakeout, the repeats, IR-1, IR-2 and IR-8's registry
  half, and the held-out readings, which run after the chain's last roll (§2).

**Not prohibited:** the owner's crews on the engine. The owner chose to read them ("2 metrics"), so their load is read
(§4, "The engine's other callers"), not prevented.

## 10. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or behavioural.
- **Each void and re-run,** with its cause.
- **Each owner action,** and each ruling.
- **The engine:** the frozen recipe the set ran on; the candidate it was switched from and restored to; and the runs
  served by the candidate. Those are Track D's Campaign, the demonstrations, and D12's own evidence, #2253's replays
  (#2747, merged 2026-10-27, and #2752, merged 2026-10-28), all after the candidate started on 2026-10-24.
- **The crews' load:** the set and the shakeout ran beside the owner's crews on the engine, while 2.4's baselines
  ran without them. The counter's totals by key label for each roll's window are recorded (§8).
- **The record versions:** the set's failure records are attributed under registry version 2, every 2.4 baseline's
  under version 1.

## 11. What this set doesn't cover

- **A reliability rate,** for anything (§2).
- **Track A's narrowing** (the owner chose "Narrow the claim, go to cut", and "Yes to both", 2026-10-29). 2.5 claims a
  Campaign on a repository-backed Project through its record, proposal, binding, launch, reconciliation and
  evaluation. It doesn't claim an accepted increment on a product whose in-cycle tests need the product's own
  dependencies (#2818).
  - **Not exercised:** IR-5; IR-6 on an increment; IR-9's increment reading; the review-request push (§24ci (b),
    #2772), since nothing was accepted onto a campaign branch.
  - **IR-4's goal half on a product:** §4.5's evidence isn't shown to a product's proposal, which no ruling has placed
    (`proposal_evidence.py:38-45`). IR-4 on the products is a leak test of the step values.
  - **Placed first in 2.6 or a 2.5.x patch:** #2818, with the product-path findings the demonstrations filed. Among
    them are #2799 (a vitest product's page criterion can't discriminate) and #2796 (the tier escalates every plan gate
    of a product's cycle), and #2817, #2814, #2809, #2813, #2804, #2798 and #2783 (the plan's §2.6).
  - **The plan's §8 leaves three of §24bv's questions open** until after the demonstrations: whether the review
    request stays a draft until the Campaign ends, a per-increment review request beside the Campaign's, and how a
    frozen bundle snapshots fixtures for runners other than pytest and vitest.
  - **The demonstrations' own limits** (their §7): Next.js, and a product with no Python; `z_continuum`'s UI, whose
    page surface is not applicable; the page scenario's validation on `z_shelfnote`, read there for the first time;
    any verdict's quality; and the secrets resolution (#2421).
- **The deferrals to 2.6:** #2723, suite revision 7, by the plan's deferral rule, since it wasn't ready when `-7` was;
  #2287, the box lease, and #2495, the scripted squad, both deferrable and unbuilt; and, by the owner's choice of "Yes
  to both", #1469 (unbuilt, blocked on its corpus) and #2286's remainder (the operator-key spec, the rotation, the
  restart and the runbook). Also #2421's remainder (the owner, 2026-10-28) and #2230 (D5).
- **Every difference between the tagged tree and the validated deploy,** named at the reading as additive or
  behavioural. Expected: this document, its definition and the set's configs, and the release PR's version files.
- **Next.js on a campaign.** The shakeout runs FastAPI + React, as 2.4's did. On Next.js, D12, #2664, #2297 and
  #2602's page example are read on greenfield rolls only, and #2602's increment half (a page criterion that
  discriminates) isn't exercised.
- **#2578's repair and retry records.** The shakeout launched none, so they are *not exercised* on the final deploy
  (Q8; §12).
- **#2824** (the owner chose "Name it, fix after"): a Campaign can't repair or retry an increment whose approved
  proposal is a revision, since the repair's binding reads the launch block's first version. Found in the
  `z_continuum` repeat (§14). Placed in 2.5.x or 2.6 beside #2818. Neither the rolls nor the shakeout reach it: the
  rolls aren't Campaigns, and the shakeout approves each proposal as it stands.
- **The prompt budget's binding on a sample application** (#2805, #2810). Nothing in the set binds an instruction;
  the rendering moves are read (§4.3).
- **Memory supply on a sample application.** Every roll declares memory disabled, and the shakeout supplies nothing.
  IR-3 reads a binding on a product.
- **The held-out readings are one reading per tree.** The page scenarios' three-round agreement (SIP-0113 §10r) is the
  instrument's; it isn't re-read here.
- **A pulse check's behaviour.** The regression profile declares none, so P5 reads the pulse path as inert (IR-10's
  limit, carried).
- **#2814, unchanged since 2.4:** a JS or TS file past about 257 lines has no anchored edit form, so a repair of one
  edits without it, as on 2.4's rolls.

## 12. Decisions at this stop

**The owner's:**
1. **#2578's repair and retry records** (Q8). The shakeout launches a repair or retry only if an increment fails, and
   Track D's readings of them were voided (§6.2). **Recommended:** if the shakeout launches none, they are named *not
   exercised* on the final deploy in the cut record, rather than forced by a fault. **At registration:** the shakeout
   launched none, so they are named *not exercised* (§11), as recommended. The owner hadn't ruled it, and can still
   ask for a fault-forced reading before the cut's record is written.
2. **The scope of "Return such a criterion"** (the demonstrations' deviation 2). **Recommended:** it applies to the
   `z_continuum` and `z_shelfnote` repeats, which are product Campaigns, and not to the `group_run` shakeout, which
   keeps "approved as it stands" and §24bq's row 16 (§2). **At registration:** applied as recommended, and the owner
   hadn't ruled it. It returned one `z_continuum` proposal (§14). No shakeout proposal had a criterion the accepted
   application already met, so the scope didn't change the shakeout either way.
3. **The tag and the Release stay the owner's.** As at 2.4.0 (D9), the supervisor pushes the tag once the owner says
   go, after a set passes.
4. **D4's eight `*_memory_data` volumes** are kept as a backup until the cut (#2735). Removing them after the tag is
   the owner's.
5. **The set's size** is 2.4's, carried by the supervisor. The owner can change it before registration.

**The supervisor's:**
1. **Q1 reads the page scenario** (§4.1). **Recommended:** yes, since `-6` reads a label that ends with a colon. The
   alternative is 2.4's rule. **Decided:** yes.
2. **#2557's Next.js half** (Q7). **Recommended:** the two Next.js rolls' plans stand for a Next.js calibration. A
   roll's framing runs `validated-fullstack`, the profile a campaign's calibration runs, on the same PRD, so its design
   asks the same questions. Only the gate's decider differs. The departure is recorded on #2557. **The alternative:** a
   Next.js calibration under the tier beside the shakeout, about 1 box-hour. **Decided:** the rolls' plans stand, and
   the departure goes on #2557 with the reading.
3. **IR-8's registry half, again** (§6.1). 2.4 ran it at its cut, and 2.5 changed the create path it reads.
   **Recommended:** yes, in minutes, beside IR-1. **Decided:** yes.

## 13. What the second reader and the owner changed

A fresh agent read the first draft (PR #2822 at `ea4384d7`) before anything ran, and the owner ruled the draft's
decisions the same day (the rulings above).

**The engine (the second reader's P1, and the owner's "Frozen recipe" and "2 metrics"):**
- the engine switch is ordered before the final deploy's rebuild, and the final deploy is the last record written;
- the engine's exact command line, image and start time are pinned and re-read, since neither the switch's check nor the
  deploy record tells the recipes apart;
- the crews keep running, and another caller's load is read on TensorFold's own counter and gauges, which decide
  "inconclusive" and nothing else;
- a crew call that holds back or refuses a launch is data, not a seam finding or a refused roll.

**The second reader's re-read at `193281a3`:**
- the conditions are reordered so each comes after what it needs: the document merged, the engine switched, the
  rebuild, the engine read, the loaded checks, the sweeps' baselines, and the engine's caller reader;
- a campaign escalated by the crews' load after its six attempts is resumed by the owner, counted as an intervention,
  and is data when the metrics show the load caused it;
- the metrics reader is named, `scripts/dev/engine_callers.py`, the supervisor's to build, with a condition before the
  shakeout;
- the engine pin adds `.Image`; a restart alone makes a roll inconclusive, and a changed line or image fails P1;
- the gauges' threshold, the crews' load read beside the correction rounds, and §10's declaration of that load;
- IR-2's and IR-3's standalone cycles are created while the Campaign is paused or at a gate, and cancelled before
  they dispatch;
- a refused roll is re-launched by the driver's `chain --resume`; the repeats are re-run if the engine changes
  before registration; and the restore follows the runs beside the set.

**Stale facts:** #2819 and #2821 merged (`b5b12c12`, `7e631321`), so condition 6 names #2819's reader, #2751's note
names #2821, and §4.3 counts 75 commits.

**The frame:**
- a Q1 or Q2 falsification is no longer pre-judged as having no framework cause: the record reads it;
- the list Q1 and Q2 can't separate adds #2727, #2807, #2812 and #2816;
- a D12 revert would drop P2's `2253` row as well as Q6;
- a rule for a finding in a repeat;
- no merge from the exit rule's round to the set's last reading.

**The predictions:**
- Q6 tests equality, and a roll with no `qa.test` envelope voids it;
- Q7 says what absence can't show, and how #2557 records it;
- Q9 reports a count, and zero is *not exercised*;
- Q10 is new: the sample-application controls the draft read "beside", made a prediction;
- condition 9 re-reads the baselines on a change to the scenario runner, not only the evaluator's tag.

**§4.3:** #2807, #2812 and #2816 are read as exercised moves with their goldens, not as unexercised, and #2811 is read
by every build, not by Q7 alone.

**§6 (the owner's "Repeat the cheap ones", "1 yes" and "Yes to both"):**
- IR-3 is repeated, not ruled;
- IR-4 on `z_continuum` is voided by its run's own cycles, and swept again;
- the `z_shelfnote` repeat's IR-4 is a leak test;
- the Track D void is said to reverse the plan's §5 judgement;
- IR-6's increment half joins the narrowing.

**Smaller:**
- §4.2 names the sweep's `--campaign` list;
- each campaign's create reason names its definition file;
- IR-1's timing is stated;
- "Return such a criterion" is scoped;
- §10 names D12's evidence on the candidate engine;
- §11 adds §24bv's three open questions and the demonstrations' limits;
- the citations are corrected: full paths, and "five days".

## 14. Before registration: the shakeout and the repeats

The records are in `var/verification_sets/2-5-0-cut/`: `shakeout-round1.md` and `repeats.md`, with the sweeps, the
caller readings and the repeats' artifacts beside them. Counts and identities only.

### 14a. Shakeout round 1: the exit rule holds

**On the final deploy:** `cmp_cea660c0a6a6` on `dep_eb111413d45d`, 23:26–00:50Z on 2026-10-29/30, completed
`success` (§10 row 3, objective met).
- **The calibration and both increments were accepted on their first cycle:** `cyc_d8ff5104cac8`,
  `cyc_d16225d07876` (a run capacity, 4 criteria) and `cyc_88f5a7cffc9e` (runs listed soonest first, 1 criterion,
  `must_not_break` T1–T4).
- **Each proposal was approved as it stood,** within two minutes of its submit. No repair, retry, re-proposal,
  escalation or intervention.
- **The engine** was unchanged across the round. Its counter showed one key label, `squadops`; `running + waiting` never
  reached 2 (917 readings, no gap).
- **Every shakeout prediction holds:**
  - **P4:** the tier approved all three plan gates, each with its three readings;
  - **Q3:** no outcome record has a `regressed` scenario;
  - **Q4:** both proposals carried 31 goals, none held back, and rendered the goals section;
  - **Q5:** no step marker or goal outside the excused places, no `no_task_span` row, nothing unsearched; the positive
    control held;
  - **Q6:** all 15 `qa.test` and `qa.test_repair` envelopes end with D12's note, and none of the 27 others carries it;
  - **Q7:** the calibration's design asks nothing, and its gate wasn't escalated;
  - **Q8:** each cycle names its own increment; its repair, retry and re-proposal halves are *not exercised*;
  - **Q9:** no framing refused, and both merges complete. The criterion-file move wasn't exercised (0 files moved, no
    development task dropped);
  - **Q10:** no calibration record or commit, no `branch_rebased` row, no source context; both increments ran
    `qa.evaluate_increment`; no stale refusal.
- **Read beside:** correction rounds 1, 3 and 0 (one `qa.test_repair` retest passed on the calibration and one on
  increment 1); no `slot_subject_dropped`, `repair_dropped` or `contract_assertions_match` refusal in any log; no
  `start_failure`; no catch-all route declared.

**The loop took one round of three.**

### 14b. The repeats

**`z_shelfnote`** (`cmp_725a9e2ee446`, 00:58–01:32Z):
- **IR-7 holds:** the baseline reading names the calibration record and `prj-shelfnote` (5 passed, 4 failed), and the
  increment's evaluation is on its captured tree (9 of 9 passed).
- **#2780's anchored page holds:** `/search` held in the increment and its repair.
- **The missing-route negative holds, as a replay:** held as built, broken with the route removed.
- **IR-8's `prj-shelfnote` half holds.**
- **IR-4 holds as a leak test,** a fresh clone of the product included.
- **The increment and its repair were rejected on #2799 alone,** as expected. T1 (pytest) and T2 (vitest, rendering
  the App) discriminate; T3 imports the view the change adds. Aborted after the readings.

**`z_continuum`** (`cmp_d30d964599df`, 01:34–02:22Z):
- **IR-2 passes:** the standalone cycle and the Campaign's first cycle carry the same baseline, revision and pinned
  commit, each with its own snapshot.
- **IR-6's calibration half and IR-8's `prj-z-continuum` half hold.**
- **The owner's "Return such a criterion"** returned v1 for a T2 the framework's own 404 meets, classified
  `criteria_not_checkable`. v2 was approved.
- **Increment 1 failed in its cycle on #2818's class,** as expected. Its repair couldn't be built: **#2824**, filed.
  The owner chose "Abandon and propose".
- **IR-3 (a)–(e) hold on the final deploy:**
  - (a) the first cycle bound `CLAUDE.md@2070ba46`;
  - (b) after the outside commit `fad7fba` was synced, the next launch was refused `STALE_SOURCE_PRECONDITION` until the
    reconciliation (revision 7 at `fad7fba`);
  - (c) the launcher rebased the branch and the next cycle bound `CLAUDE.md@fad7fba`;
  - (d) a standalone cycle created after the reconciliation bound the new content;
  - (e) no re-binding.
- **IR-4 holds as a leak test,** the product's fresh clone and mirror included. Aborted after (e).

**The registration's own merge** changes only this document and the set's two configs, all under `docs/`. No path in
the plan's §3 rule moves, so it voids neither the round nor the repeats.
