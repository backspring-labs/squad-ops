# 2.4.0 — pre-registration of the cut's set (the plan's §6.2, "the release evidence")

**Status: DRAFT, not registered.** Written 2026-10-23 by the Spark lane, which runs the line under D11, before anything
in it launches, and revised the same day on a second reader's findings (§11) and on shakeout round 1, a diagnostic
round (§12). It registers when the conditions below
hold, and nothing in the set launches before then. The plan leaves the cut's numbers to this document (§8: "each is
written as a pre-registration when its batch is built"):
- **the set's size is 2.3's,** carried as 2.3 carried 2.2's;
- **Q1's and Q2's thresholds are new.** The supervisor set them under D11, from §2's baselines, for the owner's revert
  rule (§10).

**What must be true before the shakeout's first launch:**
1. **Both lanes' last 2.4 code is merged and deployed.** That means #2700 (#1966's qa half, merged as `551c9388`) and
   the MacBook lane's #2702 (#2183's T16 pair report). It also covers any other PR the MacBook lane names, in writing, as
   2.4 code the cut needs: #2705 (#2704, a cycle stopped at its plan gate promoted as accepted), named on 2026-10-23. The Spark is rebuilt from main at that commit, and that rebuild is **the final deploy** (§6).
2. **Every tracked loaded check answers its expected value on the final deploy,** `1966` among them
   (`verify_loaded.py`, run from the main checkout), and the deploy record is ok.
3. **This document is merged, as a draft,** so the shakeout's predictions (P4, Q3–Q5) are fixed before it launches.
4. **The sweeps' baselines are taken** on the final deploy (§4.2).

**What must be true before the set is registered:**
5. **The shakeout loop's exit rule holds on the final deploy** (§3): one shakeout campaign with no new seam finding.
6. **The always-pass sets are fixed** (§4.1): every baseline tree is read on the final deploy's evaluator, and the
   counts are in §4.1.
7. **The pins are read** (§6), and nothing in the set has launched.

---

## 1. What the set measures

2.4 is a feature release (even minor). Its headline is Project Lifecycle Management, with Outcome Evaluation's
phase 1 as the yardstick (D14). It also carries Outcome Evaluation's §4.5 (D4, the split), the memory entry points
(SIP-0110) and #1966's risk-first QA instructions (adopted 2026-10-23). The set measures:

| claim | read from | not a substitute for it |
|---|---|---|
| greenfield building did not regress on either stack on the final deploy | each regression roll's verdict, criteria, correction rounds and boot audit, against §2's baselines | a clean campaign |
| the rolls are IR-10 on the cut deploy: the cadence, pulse and correction paths are unchanged | P5, which carries IR-10's R3 and R4 | IR-10's own pair, on `dep_1b38de8af6b4` |
| **#1966's qa half loses no held-out scenario and adds no rounds from QA's own tests** | Q1 and Q2, against §2's and §4.1's baselines | the A/B, which replayed four increments once each |
| the campaign evolves the app unattended on the final deploy, with Outcome Evaluation reporting and §4.5's evidence shown | the shakeout's cycles, gate decisions, evaluations and close (P4, Q3, Q4) | the regression rolls, which run no campaign |
| no scenario step or goal reaches a squad role on the final deploy | Q5's sweeps over the shakeout | the window's and §4.5's own sweeps |

**Beside the set, uncounted, on the final deploy:** IR-1, IR-2 and IR-8. The integration record's last column names
each to repeat on the cut deploy (`docs/plans/2-4-0-integration-record.md`). They run after the set's last reading,
by that record's recipe, and their results go there. A scenario that can't run on the Spark reports *not run* with
§8.5's four fields (G5): the missing prerequisite, the contract affected, the evidence that is missing, and the effect
on the release claim. They don't change the set's verdict.

---

## 2. The set

- **Regression rolls: two per stack** (2.3's number), `fullstack_fastapi_react` and `nextjs_ts`.
  - They run on `validated-fullstack` with `full-38-tf`, project `group_run`, launched by the verification-set driver
    one roll at a time, in one chain from the main checkout.
  - Their configs are carried from IR-10's (`2-4-0-ir10-regression-*.yaml`). What changes: the name, the records home
    (`var/verification_sets/2-4-0-cut/`), this pre-registration, two rolls, every row of
    `scripts/dev/loaded_checks.yaml` tracked, and the final deploy's pins.
  - **Every launch declares `memory: disabled`,** the driver's `MEMORY_DECLARATION` (the 2.2 plan's D12, carried). No
    lesson, project instruction or task instruction is supplied, which is IR-10's `lessons: disabled`.
  - **The plan gate** is approved with the set's constant notes. Where the plan has no open question, it is decided
    by `system:no_open_questions`, as IR-10's Next.js roll and two of 2.3's set-2 rolls were. Either way it is data.
  - **The held-out readings run after the chain's last roll.** Each roll's accepted tree is read against revision 5
    (`92a26ad0…`) once, by `scripts/dev/read_scenarios.py`, the tool that read §4.1's baselines. The tool boots each
    app in the sandbox, so it never runs beside a roll. It writes a record with no campaign, so it changes no
    campaign's reading.
- **The baselines:** the line's own greenfield rolls before #1966.
  - **The regression baseline is IR-10's pair,** the line's last counted pair.
  - **The other five are campaign calibrations** from the same PRD and squad. They are greenfield builds through the
    same `validated-fullstack` profile, and they read Q1's and Q2's baselines.

  | roll | deploy | stack | verdict | correction rounds (by repairing task) | `qa.test_repair` rounds whose retest passed |
  |---|---|---|---|---|---|
  | IR-10 `cyc_00f7cec8da9b` | `dep_1b38de8af6b4` | FastAPI + React | accepted, 21/21, boot audit PASS | 0 | 0 |
  | IR-10 `cyc_17dcac259f6f` | `dep_1b38de8af6b4` | Next.js | accepted, 24/24, boot audit PASS | 3 (2 `development.correction_repair`, 1 `qa.test_repair`) | 1 |
  | window c1's calibration `cyc_4145fa7e4b4a` | `dep_19dfa94c0a0a` | FastAPI + React | accepted | 0 | 0 |
  | window c2's calibration `cyc_23232c9e72da` | `dep_19dfa94c0a0a` | Next.js | accepted | 0 | 0 |
  | window c3's calibration `cyc_413e75801797` | `dep_19dfa94c0a0a` | FastAPI + React | accepted | 1 (`qa.test_repair`) | 1 |
  | window c4's calibration `cyc_42ad92a3290d` | `dep_19dfa94c0a0a` | Next.js | accepted | 2 (1 `builder.assemble_repair`, 1 `development.correction_repair`) | 0 |
  | §4.5's calibration `cyc_f34b2bc781ee` | `dep_1aa6d6f1c4e0` | FastAPI + React | accepted | 1 (`qa.test_repair`) | 1 |

  **Read by `var/verification_sets/2-4-0-cut/qa_rounds.sh`** from the runtime's lines in Prefect's `log` table, by
  each implementation run's flow run, in time order (`baseline-qa-rounds.txt`):
  - **a repair round** is a `Dispatched task repair-<run>-NN-sNN-<type> (<type>)` line;
  - **its retest** is the first `patch_retest …` line after it, before the next repair.

  This is the A/B's V3 measure, "QA repairs whose retest passed". **On the old prompts** the A/B's arm A, increment 3
  (`run_ff1bd7d6e954`), dispatched two `qa.test_repair` rounds, one of which passed its retest. So a count of
  dispatches reaches 2 without #1966, and the passed-retest count is what Q2 reads.
- **The shakeout campaign:** one campaign of **two increments** on FastAPI + React, opening with its calibration
  (`examples/03_group_run/campaigns/2-4-0-cut-shakeout.yaml`). It is 2.3's cut shakeout, carried, with three changes:
  - **`scenario_suite`: revision 5** is pinned. Each cycle is evaluated at its end (Outcome Evaluation's phase 1,
    reporting only), and each proposal is shown its accepted tree's goals (§4.5).
  - **`policy.stack: fullstack_fastapi_react` and the objective's `work_class`**, as §4.5's campaign declared them.
    The create API requires `work_class` since the window (`campaigns.py`).
  - **The ruling rule is §4.5's:** each proposal is approved as it stands, at version 1, unless the rails refuse it.
    2.3's left the ruling to the delegate. A fixed rule keeps the delegate's judgement out of Q3 and Q4.

  Plan gates stay `tier`. The increment gate is never the tier's, so the delegate rules each proposal by that rule.
  It is the exit rule's shakeout (§3) and the set's campaign reading. It is uncounted. A new seam finding in it is
  fixed and re-run before registration, never counted.
- **What the sample can say:** four rolls and one campaign show:
  - the final deploy working on both stacks;
  - the new QA instructions running without a loss Q1 and Q2 can see, on greenfield builds and across two increments;
  - the campaign's unattended path, with the yardstick on.

  They are not a reliability rate, and the record says so.

---

## 3. The frame

- **The shakeout's exit rule:** one shakeout campaign on the final deploy with no new seam finding (2.0's rule).
  - **A seam finding** is a framework defect the shakeout shows. That includes a falsification of P4, Q4 or Q5 whose
    cause is in the framework.
  - **A finding is fixed,** the deploy rebuilt, the sweeps' baselines re-taken (§4.2), and the shakeout re-run. The
    record reports how many rounds it took.
  - **The budget is three rounds.** A fourth goes to the owner with the findings.
  - **A falsification of Q3,** or of P4, Q4 or Q5 with no framework cause, goes to the owner and isn't counted as a
    seam finding.
- **The chain** runs the four rolls back to back. It stops on a roll that is refused, fails, or isn't accepted, as
  2.3's set 2 did (2.3's §6b). Q1 and Q2 are read after the chain, so they never stop it.
- **Pass:**
  - **every regression roll is accepted, and its boot audit passes;**
  - **no roll regresses against its stack's baseline beyond variance:** every criterion is verified, and correction
    rounds stay within 0–3 on both stacks. That is 2.3's range on TensorFold. §2's 2.4 baselines read 0–1 on
    FastAPI + React and 0–3 on Next.js;
  - **P1–P3, P5, Q1 and Q2 hold.**
- **Fail:** a roll not accepted, a boot audit failing, or one of those predictions falsified. The record reads the
  cause. A framework defect is fixed, which voids the set, and the set restarts on the fix's deploy after a shakeout.
  A failure with no framework defect goes to the owner, and nothing restarts without the owner's ruling.
- **#1966's revert rule** (the owner's ruling, 2026-10-23): if Q1 or Q2 is falsified, #2700 is reverted before the tag.
  - **A revert is a change,** so it voids the set. The set restarts once on the revert's deploy, after a shakeout,
    under this frame.
  - **On the restart,** Q1, Q2 and P2's `1966` row are dropped, since the prompts they read are gone. Q3 becomes a
    reading, not a prediction.
  - **A failure of the restarted set** goes to the owner.
  - The record names the falsifying reading.
- **Inconclusive:** a roll ended by a cause outside the framework, such as a box halt or TensorFold failing to serve.
  It is re-run under 1.8.2's void rule, and it doesn't spend the budget.
  - **A held-out reading whose evaluation never started its tree** (`read_scenarios.py` exits 1) is re-read once, on
    the same tree.
  - **A second reading that doesn't start** leaves that roll's Q1 inconclusive, and it goes to the owner.
- **Data, not failure:**
  - a correction round inside the range, a repaired qa suite, and lint findings;
  - a plan gate decided by `system:no_open_questions`;
  - a plan gate the tier escalated in the shakeout, answered by the delegate within the bound;
  - a frozen criterion rejecting a later increment in the shakeout (Q3's note).
- **A framework fix during the set:** nothing merges while the set is open. A fix voids the set, and it restarts on a
  new deploy after a shakeout.

---

## 4. The predictions: each names a mechanism and how it is falsified

**In the four rolls:**

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | every model call in every roll is served by TensorFold, on `qwen3.8-27b-tf-nvfp4` (2.3's P1) | the agents' per-call metrics over each roll's window: `squadops_llm_call_seconds_count` by `engine` and `model` | any call counted under another engine or model in a roll's window |
| P2 | every tracked loaded check answers its expected value in every roll, `1966` among them | each roll's record, its "Loaded, not built" section | any tracked row unanswered, or answering a value other than its `expect` |
| P3 | **memory stays disabled** (2.3's P3 and IR-10's R6): every roll's cycle declares memory disabled and pins only a disabled snapshot with no entries; every consuming task records a `memory_disabled` exposure; no instruction is supplied; every captured envelope reconstructs byte for byte | each roll's cycle row, `memory_exposures`, and `verify_authoring_envelopes.py` | a pinned snapshot that is enabled or holds an entry; a consuming task with **no exposure** or another status; a supplied instruction; or an envelope that does not reconstruct |
| P5 | **the cadence and pulse paths stay inert, and the correction paths are the baseline's** (IR-10's R3 and R4) | each roll's applied defaults, `pulse_verification_records`, the record's "repair responses by revision form" row and its emissions by handler, and the runs' rows | any of the four falsifiers below |
| **Q1** | **no held-out scenario is lost** (#1966): on each roll's tree, every **HTTP** scenario in its stack's always-pass set (§4.1) reads `passed`. The set's browser scenario is reported beside it, not predicted (§12) | each roll's revision-5 reading, against §4.1 | any always-pass HTTP scenario reading anything but `passed`, `blocked_unverified` included, on a reading that started its tree |
| **Q2** | **no extra rounds from QA's own tests** (#1966): no roll has more than **one** `qa.test_repair` round whose retest passed. That is the most any of §2's seven baselines had, and the most the A/B's arm A had on any increment | each roll's flow-run log, read by `qa_rounds.sh` (§2) | a roll with two or more such rounds |

**P5's falsifiers:**
- a declared `cadence_policy` or `pulse_checks` in a roll's applied defaults;
- any `pulse_verification_records` row for a roll's runs;
- a correction round through a handler other than `development_correction_repair_handler`,
  `governance_correction_decision_handler`, `qa_test_repair_handler` and `builder_assemble_repair_handler`. Those are
  the four the baselines used;
- any run carrying a binding hold, a halt or a restart.

**In the shakeout:**

| # | prediction | read from | falsified by |
|---|---|---|---|
| P4 | every plan gate whose plan meets the tier's conditions is approved by it, with `decided_by = system:plan_review_tier` and each condition's reading in the notes; a gate that fails one escalates (2.3's P4) | the shakeout's gate decisions and escalation rows | a qualifying gate decided by anyone else, a tier approval missing a condition's reading, or a tier approval on a gate that fails a condition |
| Q3 | **QA's thinner suites don't let a later increment break what an earlier one built,** the risk the A/B couldn't see (its pre-registration's §5): no accepted increment reads a scenario `regressed` | each accepted increment's `contribution.regressed` in the campaign's package (version 5) | any scenario in an accepted increment's `contribution.regressed`. **Counted as data, beside the window's count:** each frozen criterion that rejects a later increment. That is the frozen criteria working, as window c3's increment 2 (`cyc_e5086ed84385`, frozen T1) shows |
| Q4 | **§4.5's evidence reaches each proposal** (§10v's E0, carried as written): each proposal's authoring envelope (`seam = proposal_writing`) carries `inputs["proposal_evidence"]` with goals, and its rendered request carries the goals section | each proposal's envelope and rendered request. A proposal is the run whose change request the increment gate ruled on | a proposal without them. **Counted apart, and not a falsification:** a proposal shown no goals because the tree it proposed on has no evaluation by the campaign. **Reported:** whether each proposal also carried its quality moves and accepted PRD. The first proposal's accepted PRD is empty by construction (`proposal_reader.py`) |
| Q5 | **no step value or goal leaves where it belongs** (§10v's E3 and E4, carried) | `heldout_sweep.py` and `heldout_sweep.py --goals`, run after the shakeout, against §4.2's baselines, read as §4.2 says | E3: a marker whose provenance the baseline didn't find, outside the suite's store and the evaluator's records, or a place that couldn't be searched. E4: any new hit outside the excused places, a `no_task_span` LangFuse row the shakeout wrote, or a place that couldn't be searched |

**Q5's positive control:** every goal the proposals were shown is found in the excused places
(`goals_not_found_in_proposals` lists none of them). If any isn't, E4 is void, not held, because the sweep didn't find
what it looks for.

### 4.1 The always-pass sets (Q1)

A stack's always-pass set is every revision-5 scenario that reads `passed` on **every** baseline tree of that stack
(§2): four FastAPI + React trees and three Next.js trees. **All seven are read on the final deploy's evaluator,** with
one tool and one suite:
- five were read on `dep_e503f2cfabfd` (`var/verification_sets/2-4-0-cut/baseline-heldout.json`);
- window c2's and c3's calibrations are re-read (`baseline-heldout-reread.json`). Their first readings, in B1
  (`var/window/2-4-0/page-scenarios/b1-reading.json`), ran on the evaluator before #2661 moved its tag to `…-5`, which
  changed the browser step's bound.

B1 also holds a fault-injected tree made from c3's calibration (`3838e324…`, §10r's F1). It's a diagnostic, not a
build, and it's left out.

**If the final deploy's `EVALUATOR_IMAGE` differs from the baselines'** (`…eslint10.12-5`), every baseline tree is
re-read on the final deploy before registration, so a roll and its baselines are always read by one evaluator. 2.4
has no evaluator change left to land: #2659's and #2706's driver changes are placed with suite revision 6.

**The counts,** all seven trees on `…eslint10.12-5` (`var/verification_sets/2-4-0-cut/always-pass.json`, which names
each tree, its evaluation and the set's scenario ids):

| stack | baseline trees | passed on each tree | always-pass set | passed on at least one tree |
|---|---|---|---|---|
| FastAPI + React | 4 | 11, 11 (c3, re-read), 11, 6 (IR-10's) | **5** of 31 | 17 |
| Next.js | 3 | 11 (c2, re-read), 11, 12 (IR-10's) | **4** of 31 | 19 |

The re-read changed no result on either tree against B1. Condition 6 holds unless the final deploy moves the
evaluator's tag.

**What Q1 reads** (amended before registration, §12): the always-pass sets' HTTP scenarios, **4 on each stack**.
FastAPI + React's fifth, `a-runner-joins-from-the-run-page`, runs in the browser, and the browser driver can read a
correctly built field as absent (#2706). Its result on each roll is reported, with its blocked reason, and
falsifies nothing.

**The spread between builds is wide:**
- IR-10's FastAPI + React tree passed 6 scenarios where each calibration passed 11;
- five scenarios that passed on window c1's calibration failed on it, each after its first step, so the app started and
  answered.

Greenfield builds of one PRD differ, and a scenario that needs a behaviour one build has and another lacks is outside
the set. So the sets are small, and Q1 is a narrow instrument: it reads only what every pre-adoption build did. It
reads a loss, not a gain.

**Reported beside Q1, not predicted:** each roll's count of passed scenarios, against its stack's baseline range, and
each scenario outside the set whose result differs between the rolls and the baselines.

**What Q1 can't see:**
- **Public values.** 8 of revision 5's 59 step values are already public (§10w's check). That weakens holding out, not
  the reading of a tree: no squad role reads the repository's history or the vault's other trees.
- **Blocked scenarios.** Fourteen scenarios read `blocked_unverified` for `surface_absent` on every tree the A/B read.
  So they are outside every always-pass set, and Q1 says nothing about them.

### 4.2 The sweeps' baselines (Q5)

**Before each shakeout round's launch,** on its deploy, both sweeps run over every place §10v's sweep named, over the
cycles of every campaign that pins a suite, and their reports are kept in the record's directory. A rebuild changes
the images a sweep searches, so each round takes its own.

**How "new" is read** (§4.5's pre-registration §4, carried). A sweep keys its marker ids fresh for each run
(`heldout_sweep.py`'s `_KEY`), so ids don't compare across runs. A marker's provenance (its scenario, and the step or
check it's from) does. For E3, a marker whose provenance the baseline found is known, and only the others can
falsify. For E4, any goal outside the excused places that the baseline didn't find is new. The excused places are:
- the proposals' authoring envelopes;
- their LangFuse generations, attributed by the `task-…` span each hangs under;
- the evaluator's records.

---

## 5. The campaign's policy

**The shakeout:** 2.3's cut shakeout (`2-3-0-cut-shakeout.yaml`), carried, with §2's three changes.

| field | value | basis |
|---|---|---|
| `objective.target_accepted_increments` | **2** | §2, as 2.3 |
| `objective.work_class` | `prd_tier: tier-1`, `attendance: unattended` | as §4.5's campaign; the create API requires it |
| `max_cycles` | **7** | 1 calibration, 2 increments, one repair or retry each, 2 replacements: 2.1's rule |
| `ruling_bound_s` | **1800** | 2.3's |
| `plan_gate` | **`tier`** | as 2.3 |
| `squad_profile` | **`full-38-tf`** | as 2.3 |
| `stack` | **`fullstack_fastapi_react`** | §2 |
| `scenario_suite` | **revision 5, `92a26ad00f26a822458e18f4864853adb431aecd5706ed4e4146232ad9eb67fd`** | §2 |
| every other field | 2.3's cut shakeout | unchanged by this line |

---

## 6. Pins (read at registration)

*Read when conditions 1–6 hold:*
- the deploy commit and record;
- the image ids, read from the running containers and equal to both configs' `frozen_image_ids`;
- `EVALUATOR_IMAGE`;
- the model;
- the tracked loaded checks and both counting preflights;
- the set configs' sha256;
- HEAD at preflight.

---

## 7. Prohibited while the set is open

- **Merging to main.** A fix voids the set.
- **Rebuilding any service.**
- **Running anything else on the box** while a roll runs: the shakeout, IR-1, IR-2 and IR-8, and the held-out
  readings, which run after the chain's last roll (§2).

## 8. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or behavioural.
- **Each void and re-run,** with its cause.
- **Each owner action.**

## 9. What this set doesn't cover

- **A reliability rate,** for anything (§2).
- **#1966 on a Next.js campaign.** The shakeout runs FastAPI + React only, as 2.3's did. The Next.js rolls read it on
  greenfield builds.
- **The memory entry points live.** They are #2183's matrix, run by the MacBook lane on the Mac, and every roll here
  declares memory disabled. The cut record names each of #2183's cases as passed or *not run*.
- **Outcome Evaluation of an external Project:** IR-4 to IR-7, and the evaluation halves of IR-8 and IR-9 (#2619).
  They are in 2.5, by the owner's ruling ("go with 2.5").

## 10. The owner's decisions at this stop

- **The tag and the Release stay the owner's** (2026-10-23, "2 keep"). The supervisor brings the release PR to green
  once a set passes, and asks once.
- **#1966's adoption and its revert rule** (2026-10-23, "1 yes"). The rule's thresholds, Q1's and Q2's, are the
  supervisor's (above).
- **The set's size** is 2.3's, carried by the supervisor under D11. The owner can change it before registration.

## 11. What the second reader changed

A fresh agent read the first draft before anything ran.

**Three blocking findings:**
- **Q2 would have fired on the old prompts.** It counted `qa.test_repair` dispatches, and the A/B's arm A dispatched
  two on one increment. It now counts V3's measure, rounds whose retest passed, and names its query.
- **Q3 would have fired on the frozen criteria doing their job.** A frozen criterion rejecting a later increment is now
  data. Q3 reads only `regressed` scenarios, and its falsification goes to the owner.
- **Q5 couldn't be read.** A sweep's marker ids are keyed fresh each run. It now carries §4.5's provenance rule, the
  positive control, the `no_task_span` rule and the unsearchable-place falsifier, with a baseline before each round.

**Also adopted:**
- two baseline trees re-read on one evaluator, with `EVALUATOR_IMAGE` pinned;
- Q1 falsified by anything but `passed`, not only by `failed`, with a rule for a reading that never starts;
- Q4 carried as §10v's E0 was written;
- the frame's loops bounded: a single restart after a revert, the predictions dropped on it, the chain's stop rule
  carried, and each shakeout falsification routed;
- P5's handlers named;
- P3's "no exposure" and P4's `decided_by` restored;
- the readings moved after the chain;
- condition 1 names #2702;
- smaller corrections: D12's source, `work_class` being required, the shakeout's third change, the range's source, the
  plan gate's deciders, G5's four fields, and §9's evaluation halves.

**Found outside this document:** the integration record's IR-10 R4 reading named two correction handlers. The Next.js
roll's record shows `qa_test_repair_handler` ran too, and the baseline used it as well, so R4 still holds. The reading
is corrected in this PR.

## 12. Before registration: shakeout round 1, a diagnostic round

**Why it can't meet the exit rule.** Round 1 ran on `dep_7daa36f7adb9`, from main at `f8309507`, which is #2703's merge,
13:45–15:11Z on 2026-10-23. All four pre-launch conditions held. At 14:16Z the MacBook lane named #2704 as 2.4 code
the cut needs: a cycle stopped at its framing run's plan gate fell through `cycle_ending` to `assessed`, and its
framing summary's empty `accepted` promoted a calibration that built nothing. The fix is #2705. Round 1's deploy is
superseded, so the round ran to the end as a diagnostic and counts toward the three-round budget.

**What it read:** `cmp_73d227af5da0` completed `success`.
- **Its cycles:** the calibration `cyc_28da0e568e9f` and both increments (`cyc_d5bd8cd5c8ff`, capacity;
  `cyc_189b357041b2`, a seeded sample run) were each accepted on their first cycle. There was no repair, retry or
  escalation, and each proposal was approved as proposed.
- **P4 holds:** the tier approved all three plan gates, each with its three readings.
- **Q3 holds:** no cycle's contribution has a `regressed` scenario.
- **Q4 holds:** both proposals' envelopes carried the evidence, and their requests rendered the goals section.
- **Q5 holds:** E3 found no marker whose provenance the baseline didn't find (8 provenances before and after). E4
  found no goal outside the excused places, and the positive control held. No place went unsearched.

**What it found: #2706.** On every cycle, two browser scenarios read `control_absent`:
- **The app built the field.** It labels the join field with a trailing colon. The driver matches a field's name
  exactly after folding, and the scenario accepts a name that differs only by that colon.
- **The evaluator works:** on the same deploy, a baseline tree whose label has no colon passes the same scenario.
- **The cost:** each cycle's contribution reads `unverified` where it would read `contributed`. That's reporting only
  in 2.4.

**Why it changes Q1.** Under the reader's rule (§11), any always-pass reading other than `passed` falsifies Q1, and a
falsification reverts #1966. A roll whose app labels its field the same way would revert #1966 on a measurement
artifact, not on QA's work. So, before registration, Q1 reads the always-pass sets' HTTP scenarios (4 per stack). The
browser scenario is reported beside it.

**Why the driver isn't fixed for the cut.** Fixing it moves the evaluator's tag (SIP-0113 §10p ruling 6), so every
2.4 reading, the window's, §4.5's and §4.1's baselines among them, would sit on the other side of the move from the
cut's. #2706 is placed in 2.5 with #2659 and suite revision 6, which move the tag together.

**The next round** runs on the rebuild after #2705 merges, which is the final deploy, with the sweeps' baselines taken
again.
