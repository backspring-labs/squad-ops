# 2.3.0 — pre-registration of the cut's set (plan §3 step 9, the cut's criteria)

**Status: DRAFT, written 2026-10-15 on the owner's ruling (§9).** It registers when the conditions below hold and the
pins in §6 are read; nothing in the set launches before then. The plan leaves the regression set's size and the
shakeout's exit rule to this document, written when the line's last batch is built (the 2.3 plan §7), as 2.0, 2.1 and
2.2 did. The owner's ruling sets its numbers: **2.2's** (§9).

**What must be true before it is registered:**
1. **The line's last batch is built, merged and deployed** (§6): #1994's last two rounds, the correction runner and the
   task-plan builder, each with its own rebuild and regression pair; then the fixes round (#2363, #2204's last piece,
   #2354 and the deferral record), with its own rebuild and pair. That rebuild is the final deploy.
2. **Every tracked loaded check answers its expected value on the final deploy** (`verify_loaded.py`, run from the main
   checkout).
3. **The shakeout loop's exit rule holds** (§3): one shakeout campaign on the final deploy with no new seam finding.
4. **The pins are read** (§6), and nothing in the set has launched.

---

## 1. What the set measures

2.3 is a stabilization release (odd minor). Its engine changed: the owner adopted TensorFold at G4 on 2026-10-13, so
every cycle since phase 7 runs on `qwen3.8-27b-tf-nvfp4` through TensorFold. And its structure moved: the cycle
orchestration left `adapters/cycles` (#1992), a `stacks` package (#1993), 606 deferred imports hoisted (#2062), and the
five largest units split into named steps (#1994). The set measures:
- the final deploy still builds what the line built, on both stacks, on the engine 2.3 ships with;
- every structural round's code is what runs;
- the campaign still evolves the app unattended on the final deploy.

| claim | read from | not a substitute for it |
|---|---|---|
| greenfield building did not regress on either stack, on TensorFold | each regression roll's verdict, criteria, correction rounds and boot audit, against §2's baselines | a clean campaign |
| every model call of the set is served by TensorFold | the agents' per-call metrics (`squadops_llm_call_seconds_count`, label `engine`) | a deploy record naming the engine |
| the line's structural rounds are the code that runs | each roll's loaded-check answers, the structural rounds' rows among them | the rounds' own regression pairs, each on its own deploy |
| the campaign evolves the app unattended on the final deploy | the shakeout's cycles, gate decisions and close | the regression rolls, which run no campaign |

---

## 2. The set

- **Regression rolls: two per stack** (2.2's number), `fullstack_fastapi_react` and `nextjs_ts`.
  - They run on `validated-fullstack` with `full-38-tf`, launched by the verification-set driver.
  - Their configs are carried from the fixes round's, with the final deploy's tracked loaded checks and pins.
  - **Every launch declares `memory: disabled`** (D12, carried from 2.2).
  - **The baselines** are the line's own regression pairs on TensorFold, from the third rebuild (after the cutover):

    | round | deploy | React: verdict, criteria, rounds, boot audit, minutes | Next.js: verdict, criteria, rounds, boot audit, minutes |
    |---|---|---|---|
    | R3 | `e30ec9cb` | accepted, 20/20, 2, PASS, 28 | accepted, 16/16, 0, PASS, 42 |
    | R4 | `8f98c070` | accepted, 21/21, 0, PASS, 26 | accepted, 16/16, 0, PASS, 27 |
    | R5 (second pair) | `7cc1990d` | accepted, 21/21, 0, PASS, 23 | **rejected**, 11/16, 2, FAIL, 34 (#2340, fixed by #2343) |
    | R6 | `8cc3f8b3` | accepted, 20/20, 0, PASS, 23 | accepted, 16/16, 0, PASS, 27 |
    | R6's fixes | `de811cf2` | accepted, 17/17, 0, PASS, 21 | accepted, 17/17, 1, PASS, 32 |
    | #1994 unit 1 | `125c9db6` | accepted, 22/22, 3, PASS, 32 | accepted, 18/18, 1, PASS, 30 |
    | #1994 unit 2 | `012208ee` | accepted, 21/21, 0, PASS, 24 | accepted, 20/20, 1, PASS, 30 |
    | #1994 unit 3 | `f609f15a` | accepted, 21/21, 0, PASS, 24 | **rejected**, 14/15, 3, PASS, 42 (#2363, the store had no delete) |
    | #1994 units 4 and 5, the fixes round | — | added at registration | added at registration |

- **The shakeout campaign:** one campaign of **two increments** on React, opening with its calibration cycle
  (`examples/03_group_run/campaigns/2-3-0-cut-shakeout.yaml`). It is 2.2's cut shakeout, carried, on `full-38-tf`.
  - **It declares `plan_gate: tier`,** as 2.2's did. The tier's escalation and timeout halves were read live in 2.3
    (#2279's diagnostic, `dep_c627c2873c3c`), so the shakeout reads its approval path on the final deploy.
  - Its proposal rulings stay with the owner's delegate, since the increment gate is never the tier's.
  - It is the exit rule's shakeout (§3) and the set's campaign reading. It is uncounted, and a new seam finding in it
    is fixed and re-run before registration, never counted.
- **What the sample can say:** four rolls and one campaign show the final deploy working on TensorFold, the structural
  rounds' code running, and the campaign's unattended path. They are not a reliability rate, and the record says so.

---

## 3. The frame

- **The shakeout's exit rule:** one shakeout campaign on the final deploy with no new seam finding (2.0's rule). A
  finding is fixed, the deploy rebuilt, and the shakeout re-run. The record reports how many rounds it took.
- **Pass:**
  - **every regression roll is accepted, and its boot audit passes;**
  - **no roll regresses against its stack's baseline beyond variance:** every criterion verified, and correction rounds
    within the line's observed range on TensorFold (React 0–3, Next.js 0–3);
  - **P1–P4 hold** (§4).
- **Fail:** a roll rejected, a boot audit failing, or a prediction falsified.
- **Inconclusive:** a roll ended by a cause outside the framework, such as a box halt. It is re-run under 1.8.2's void
  rule and does not spend the budget.
- **Data, not failure:** a correction round, a repaired qa suite, lint findings, and a plan gate the tier escalated in
  the shakeout because a calibration asked a question, answered by the delegate within the bound.
- **A framework fix during the set:** nothing merges while the set is open. A fix voids the set, and it restarts on a
  new deploy after a shakeout.

---

## 4. The predictions: each names a mechanism and how it is falsified

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | every model call in every roll is served by TensorFold, on `qwen3.8-27b-tf-nvfp4` | the agents' per-call metrics over each roll's window: `squadops_llm_call_seconds_count` by `engine` and `model` | any call counted under another engine or model in a roll's window |
| P2 | every tracked loaded check answers its expected value in every roll, the structural rounds' rows among them (`1992-runtime`, `1994-qa-agent`, `1994-handler-base`, `1994-executor-task`, `1994-correction-runner`, `1994-task-plan`) | each roll's record, its "Loaded, not built" section, against `scripts/dev/loaded_checks.yaml` | any tracked row unanswered, or answering a value other than its `expect` |
| P3 | every roll's cycle declares memory disabled and pins no snapshot; every consuming task records a `memory_disabled` exposure; every captured envelope reconstructs byte for byte (2.2's P1, carried) | each roll's cycle row, `memory_exposures`, and `verify_authoring_envelopes.py` | a pinned snapshot, a consuming task with no exposure or another status, or an envelope that does not reconstruct |
| P4 | in the shakeout, every plan gate whose plan meets the tier's conditions is approved by it, with `decided_by = system:plan_review_tier` and each condition's reading in the notes; a gate that fails one escalates (2.2's P3 and P4, carried) | the shakeout's gate decisions and escalation rows | a qualifying gate decided by anyone else, a tier approval missing a condition's reading, or a tier approval on a gate that fails a condition |

---

## 5. The campaign's policy

**The shakeout:** 2.2's cut shakeout (`2-2-0-cut-shakeout.yaml`), carried, with one change: `squad_profile: full-38-tf`.

| field | value | basis |
|---|---|---|
| `objective.target_accepted_increments` | **2** | §2, as 2.2 |
| `max_cycles` | **7** | 1 calibration, 2 increments, one repair or retry each, 2 replacements: 2.1's rule |
| `ruling_bound_s` | **1800** | 2.2's |
| `plan_gate` | **`tier`** | as 2.2 |
| `squad_profile` | **`full-38-tf`** | the engine the owner adopted at G4 |
| every other field | 2.2's cut shakeout | unchanged by this line |

---

## 6. Pins (read at registration)

| pin | value |
|---|---|
| deploy commit | read at registration: the fixes round's rebuild |
| deploy record | read at registration: the latest record, from the main checkout |
| image ids | read from the running containers, equal to both configs' `frozen_image_ids` |
| model | `qwen3.8-27b-tf-nvfp4` on TensorFold, the frozen NVFP4 recipe |
| loaded checks | the configs' tracked rows, every one answering: both counting preflights clean |
| set configs | `2-3-0-cut-regression-fastapi-react.yaml`, `2-3-0-cut-regression-nextjs.yaml` (sha256 at registration) |
| HEAD at preflight | read at registration |

---

## 7. Prohibited while the set is open

- **Merging to main.** A fix voids the set.
- **Rebuilding any service.**
- **Running anything else on the box,** the shakeout included once the rolls start.

## 8. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or behavioural.
- **Each void and re-run,** with its cause.
- **Each owner action.**

## 9. The owner's decisions at this stop

**The owner's rulings, 2026-10-15, in session:**
- **The set:** "yes to #2", to the question "write the cut set's pre-registration on 2.2's numbers and start its
  counted run once the last round passes". So: two regression rolls per stack and one shakeout campaign of two
  increments, as 2.2.
- **What is not in 2.3:** "ok to defer" (the request-profile taxonomy, #316, and Outcome Evaluation's instruments move
  to 2.4, PR #2366); "no second tensorfold candidate at this time" (#2230, in 2.4 since 2026-10-12).
- **The engine:** TensorFold, adopted at G4 on 2026-10-13 (#2282, #2285).

The supervisor registers the set when §1's conditions hold, and launches it. The owner pushes the tag and approves the
records' upload, as at 2.2's cut.

## 10. The set's readings

Written when the set is read.
