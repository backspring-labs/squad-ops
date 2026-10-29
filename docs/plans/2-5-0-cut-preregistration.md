# 2.5.0 — pre-registration of the cut's set (the plan's §4, "The cut")

**Status: DRAFT, 2026-10-29. Not registered.** No condition below holds yet. The pins (§7) and the records (§8) are
blank, and nothing in the set or the shakeout has launched. Written by the Spark lane, which runs the line alone since
2026-10-28 (the plan's §5), after the demonstrations were read and the owner narrowed the claim (2026-10-29: "Narrow
the claim, go to cut"). It is for the supervisor's review and a second reader's, before anything runs. The plan leaves
the cut's numbers to this document (its §8: "the set's size, the predictions' thresholds and the shakeout's budget"):
- **the set's size is 2.4's,** carried as 2.4 carried 2.3's (the plan's §4 and D8);
- **the thresholds are 2.4's,** now read against eleven baselines where 2.4 had seven: 2.4's seven and its four
  counted rolls, each re-read on suite revision 6 (§2);
- **the shakeout's budget is three rounds** (the plan's §4).

**What must be true before the shakeout's first launch:**
1. **The line's last code is merged and deployed.** The Spark is rebuilt from main (`rebuild_and_deploy.sh all`) once
   this document, the shakeout's definition and anything else the cut needs are merged. That rebuild is **the final
   deploy** (§7). Main's last change to a run path today is `d0df8acb` (#2816), and `dep_aa6f0a54c53a` runs it.
   **Not met.**
2. **TensorFold serves the frozen recipe** (new in 2.5): the engine's arguments are
   `infra/tensorfold/recipes/qwen27b-nvfp4.yaml`'s, with no `--parallel`. **Not met.** Read at 21:28Z on 2026-10-29
   (`docker inspect squadops-tensorfold`), the engine runs #2742's two-lane candidate, `--parallel 2`
   (`recipes/candidates/qwen27b-nvfp4-parallel2.yaml`, whose status reads "not the frozen counted-verification
   recipe"). It has run so for four days, so Track D's Campaign and the demonstrations ran on it, and it also serves the
   owner's crews. The switch is the owner's decision (§12).
3. **Every tracked loaded check answers its expected value on the final deploy,** `2253` (D12) among them
   (`verify_loaded.py`, run from the main checkout), and the deploy record is ok. `scripts/dev/loaded_checks.yaml` has
   247 rows at drafting, 68 more than 2.4's 179. **Not met.**
4. **This document is merged, as a draft,** with the shakeout's definition, so the shakeout's predictions (P4, Q3–Q9)
   are fixed before it launches. **Not met.**
5. **The sweeps' baselines are taken** on the final deploy (§4.2), by the `heldout_sweep.py` the readings will use.
   #2819, open at drafting, changes how the sweep walks a cycle's vault. It merges before the baselines or after the
   set's last sweep, never between. **Not met.**

**What must be true before the set is registered:**
6. **The shakeout loop's exit rule holds on the final deploy** (§3): one shakeout campaign with no new seam finding.
7. **The always-pass sets are fixed** (§4.1). **Met by Track B's re-read**
   (`docs/plans/verification-sets/2-5-0-reread-preregistration.md` §6), on `…eslint10.12-7`. It stays met while the
   final deploy's `EVALUATOR_IMAGE` is `…-7`. If the tag moves, every baseline tree is re-read on the final deploy
   before registration, as at 2.4.
8. **Every demonstration reading a later merge voided is repeated on the final deploy, or the owner rules on it**
   (the plan's §3 and §4; §6 here). The repeats run after condition 6, on the deploy the set runs on.
9. **The pins are read** (§7), and nothing in the set has launched.

**Named outside the set's frame: #2751.** `worktree_hygiene.py --apply` would remove the nostromo shared-inference
worktree (`~/.config/nostromo/shared-inference/squadops-reviewed`). It gates the release cut's step 8, not the set or
the tag: the issue is fixed, or step 8's preview is shown to touch nothing under `~/.config/` before `--apply` runs.

---

## 1. What the set measures

2.5 is a stabilization release (odd minor), feature-free by rule. It carries a Campaign on a repository-backed Project
(Track A), the yardstick re-cut once (Track B), and the checks, correction loop, structure and operations the 2.4 line
found weak (Tracks C to E). The counted set reads what those changed on the sample applications' paths, which every
2.4 baseline ran (§4.3). Track A's own claim is read by the demonstrations (§6). The set measures:

| claim | read from | not a substitute for it |
|---|---|---|
| greenfield building did not regress on either stack on the final deploy | each roll's verdict, criteria, correction rounds and boot audit, against §2's eleven baselines | a clean campaign |
| the rolls are IR-10 on the cut deploy: the cadence and pulse paths are inert, and the correction rounds go through the baselines' handlers | P5, which carries IR-10's R3 and R4 | IR-10's 2.4 readings |
| **the line's changes to QA lose no held-out scenario and add no rounds from QA's own tests:** D12, #2664's guard, #2297's declared routes and, on Next.js, #2602's page example | Q1 and Q2 on revision 6, against §4.1's sets and §2's baselines | #2253's replays, which read stored calls, not builds |
| **D12's note reaches every QA first call, and only those** | Q6 | its loaded check, which reads the source |
| **the PRD's list order removes the order question** (D3, #2557) | Q7, on the rolls' plans and the shakeout's calibration | a re-read of old trees, which can't show a plan's behaviour (the plan's §2.2) |
| the campaign evolves the app unattended on the final deploy, with Outcome Evaluation reporting, §4.5's evidence shown, and each increment's records and framing as 2.5 left them | the shakeout's cycles, gate decisions, evaluations, records and close (P4, Q3, Q4, Q8, Q9) | the rolls, which run no campaign; Track D's uncounted run, which a later merge voided (§6.2) |
| no scenario step or goal reaches a squad role on the final deploy | Q5's sweeps over the shakeout | the demonstrations' IR-4 sweeps |

**Beside the set, uncounted, on the final deploy:** IR-1 and IR-2, by the 2.4 integration record's recipe with one
change to IR-2, IR-8's registry half if §12's proposal is taken (§6.1), and the demonstration repeats (§6.3). IR-10 is the set itself. An IR-1 or IR-2 that can't run
on the Spark reports *not run* with §8.5's four fields (G5). They don't change the set's verdict.

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
    by `system:no_open_questions` (`manifest_authoring.py:98`). Either way it is data. Each plan's open questions are
    kept for Q7.
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
    refuse it. A criterion the accepted app already meets is §24bq's row 16, as in 2.4's round 2.
  - **Its calibration reads D3** (Q7). It runs through `validated-fullstack`, the rolls' profile, under the tier.

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
  - **A seam finding** is a framework defect the shakeout shows. That includes a falsification of P4, Q4, Q5, Q6, Q8
    or Q9 whose cause is in the framework.
  - **A finding is fixed,** the deploy rebuilt, the sweeps' baselines re-taken (§4.2), and the shakeout re-run. The
    record reports how many rounds it took.
  - **The budget is three rounds.** A fourth goes to the owner with the findings.
  - **A falsification of Q3 or Q7,** or of P4, Q4, Q5, Q6, Q8 or Q9 with no framework cause, goes to the owner and
    isn't counted as a seam finding.
  - **A fix also re-applies the plan's §3 rule** to every reading §6.2 lets stand, by the paths named there.
- **The chain** runs the four rolls back to back. It stops on a roll that is refused, fails, or isn't accepted, as
  2.4's did. Q1, Q2 and Q6 are read after the chain, so they never stop it.
- **Pass:**
  - **every regression roll is accepted, and its boot audit passes;**
  - **no roll regresses against its stack's baselines beyond variance:** every criterion is verified, and correction
    rounds stay within 0–3 on both stacks. That is 2.3's range on TensorFold, carried. §2's eleven baselines read 0–2
    on FastAPI + React and 0–3 on Next.js;
  - **P1–P3, P5, Q1, Q2 and Q6 hold.**
- **Q7 is outside the verdict.** It reads the PRD, not a build. Its reading goes to the owner and to #2557, whose
  second half it closes or keeps open.
- **Fail:** a roll not accepted, a boot audit failing, or one of those predictions falsified. The record reads the
  cause. A framework defect is fixed, which voids the set, and the set restarts on the fix's deploy after a shakeout.
  A failure with no framework defect goes to the owner, and nothing restarts without the owner's ruling.
- **D12 carries no revert rule** (proposed here; the owner's to confirm or change before registration). 2.4's rule for
  #1966 was the owner's, set when #1966 was adopted. The plan's D12 text sets none: it names what D12 costs, the runs
  read before it voided, and its alternative, no change. Three reasons not to add one here:
  - **A revert rule changes the ruling's terms,** so it is the owner's to add, as #1966's was.
  - **Q1 and Q2 can't attribute a loss to D12.** They read every QA change since 2.4's rolls together: D12, #2664's
    guard, #2297's declared routes and, on Next.js, #2602's page example (§4.3). A revert keyed on them would act on an
    attribution the instrument can't make.
  - **D12's own prediction is its mechanism** (Q6). A note missing or misplaced is a framework defect, which the frame
    already handles: fixed, the set voided, and restarted after a shakeout.

  So a falsification of Q1 or Q2 is a fail with no framework defect: it goes to the owner with the reading. If the
  owner sets a rule like #1966's, 2.4's restart terms carry: one restart on the revert's deploy, after a shakeout, with
  Q6 dropped, since the note it reads is gone.
- **Inconclusive:** a roll ended by a cause outside the framework, such as a box halt, TensorFold failing to serve, or
  another caller's load on the engine. It is re-run under 1.8.2's void rule, and it doesn't spend the budget.
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
  - a development task #2795's merge rule drops, with its operator note.
- **A framework fix during the set:** nothing merges while the set is open. A fix voids the set, and it restarts on a
  new deploy after a shakeout.

---

## 4. The predictions: each names a mechanism and how it is falsified

P1–P5 and Q1–Q5 keep 2.4's numbers, so each reads against its 2.4 reading. Q6 to Q9 are 2.5's.

**In the four rolls:**

| # | prediction | read from | falsified by |
|---|---|---|---|
| P1 | every model call in every roll is served by TensorFold, on `qwen3.8-27b-tf-nvfp4` (2.3's P1). The engine's recipe is a pin (§7), since the metrics can't see it | the agents' per-call metrics over each roll's window: `squadops_llm_call_seconds_count` by `engine` and `model` | any call counted under another engine or model in a roll's window |
| P2 | every tracked loaded check answers its expected value in every roll, `2253` (D12) among them, reading `True True False True True` | each roll's record, its "Loaded, not built" section | any tracked row unanswered, or answering a value other than its `expect` |
| P3 | **memory stays disabled** (2.3's P3 and IR-10's R6): every roll's cycle declares memory disabled and pins only a disabled snapshot with no entries; every consuming task records a `memory_disabled` exposure; no instruction is supplied; every captured envelope reconstructs byte for byte. #2184 retired the legacy per-agent store (#2735, row `2184`), so this is SIP-0110's memory alone | each roll's cycle row, `memory_exposures`, and `verify_authoring_envelopes.py` | a pinned snapshot that is enabled or holds an entry; a consuming task with **no exposure** or another status; a supplied instruction; or an envelope that does not reconstruct |
| P5 | **the cadence and pulse paths stay inert, and every correction round goes through a handler the baselines used** (IR-10's R3 and R4) | each roll's applied defaults, `pulse_verification_records`, the record's "repair responses by revision form" row and its emissions by handler, and the runs' rows | any of the four falsifiers below |
| **Q1** | **no held-out scenario is lost:** on each roll's tree, every scenario in its stack's always-pass set on revision 6 reads `passed`. That is 5 on FastAPI + React, its browser scenario included, and 4 on Next.js (§4.1) | each roll's revision-6 reading on `…-7`, against §4.1 | any always-pass scenario reading anything but `passed`, `blocked_unverified` included, on a reading that started its tree |
| **Q2** | **no extra rounds from QA's own tests:** no roll has more than **one** `qa.test_repair` round whose retest passed. That is the most any of §2's eleven baselines had | each roll's flow-run log, read by `qa_rounds.sh` (§2) | a roll with two or more such rounds |
| **Q6** | **D12's note reaches every QA first call, and only those** (#2759): every captured authoring envelope of `qa.test` and `qa.test_repair` ends with a user message that is `request.keep_reasoning_short`'s text, "keep any reasoning short so that the output fits." (sha256 `f18fdf38…`, #2759's evidence), and no envelope of another task type carries it. The note is appended in `_llm_call` on a call that isn't a self-evaluation pass (`handlers/cycle/base.py:1472-1478`), for the two steps `TaskType.first_call_keeps_reasoning_short` declares (`task_types.py:99-103`), and the envelope is captured from those messages | `authoring_envelopes` for each roll's runs, by `task_type`, each envelope's last message | a `qa.test` or `qa.test_repair` envelope whose last message is anything else; or an envelope of any other task type carrying the note |
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

**In the shakeout:**

| # | prediction | read from | falsified by |
|---|---|---|---|
| P4 | every plan gate whose plan meets the tier's conditions is approved by it, with `decided_by = system:plan_review_tier` and each condition's reading in the notes; a gate that fails one escalates (2.3's P4) | the shakeout's gate decisions and escalation rows | a qualifying gate decided by anyone else, a tier approval missing a condition's reading, or a tier approval on a gate that fails a condition |
| Q3 | **no accepted increment breaks what an earlier one built** (2.4's Q3): no accepted increment reads a scenario `regressed` | each accepted increment's `contribution.regressed` in the campaign's package, now version 8 (`campaigns/evidence.py:39`; #2762, #2788 and #2797 each moved it on from 2.4's 5) | any scenario in an accepted increment's `contribution.regressed`. **Counted as data:** each frozen criterion that rejects a later increment |
| Q4 | **§4.5's evidence reaches each proposal** (§10v's E0, as 2.4 carried it): each proposal's authoring envelope (`seam = proposal_writing`) carries `inputs["proposal_evidence"]` with goals, and its rendered request carries the goals section | each proposal's envelope and rendered request. A proposal is the run whose change request the increment gate ruled on | a proposal without them. **Counted apart, and not a falsification:** a proposal shown no goals because the tree it proposed on has no evaluation by the campaign, and a goal the reader holds back for quoting a marker (`carries_a_marker`, which #2794 widened). **Reported:** whether each proposal also carried its quality moves, which #2762 holds to the measures shown before `-7`, and its accepted PRD |
| Q5 | **no step value or goal leaves where it belongs** (§10v's E3 and E4, carried) | `heldout_sweep.py` and `heldout_sweep.py --goals`, run after the shakeout, against §4.2's baselines, read as §4.2 says | E3: a marker whose provenance the baseline didn't find, outside the suite's store and the evaluator's records, or a place that couldn't be searched. E4: any new hit outside the excused places, a `no_task_span` LangFuse row the shakeout wrote, or a place that couldn't be searched |
| Q6 | as in the rolls, on the shakeout's `qa.test` and `qa.test_repair` envelopes, so a misplaced note is found before the set | the shakeout's `authoring_envelopes` | as in the rolls |
| Q7 | as in the rolls, and **the calibration's plan gate is not escalated on the list's order** | the calibration's tier reading (the `no_open_question` condition lists each open question, `plan_review_tier.py:112-123`) and its escalation rows | an open question on the list's order, or an escalation on it. **To the owner, not a seam finding** (§3) |
| Q8 | **each cycle names its own increment** (#2578; Track D's R1–R4, carried): the calibration carries no `increment_id`; each increment carries its proposal id, the one its own launch's `campaign_proposal` block names; a repair or retry carries its increment's id, and a re-proposal a new one; each flow run carries `kind:<kind>` and, but for the calibration's, `increment:<id>`; the ledger lists each proposal version's cycles in launch order, its outcome its last cycle's row; no decision cites a tag | `cycle_registry.increment_id` against the control log's launch rows; Prefect's flow-run tags; `GET /api/v1/campaigns/{id}/ledger` (`2-5-0-track-d-campaign-preregistration.md` §3) | any of Track D's falsifiers. A repair, retry or re-proposal the campaign never launches is reported *not exercised*, never *passed* |
| Q9 | **an increment's criterion file is the QA task's at the merge** (#2802, SIP-0093 §15b): no increment's framing is refused for a criterion file that a development task and a QA task both claim, and no merge fails for a missing or unreadable list of them. A sample application's increment framing runs the plan proposers (`campaign-increment.yaml:8-14`), so the merge's rule applies to it, with the list composed for it (`context_assembly.py:437-441`) | each framing run's plan-validation refusals and their reasons; the merge task's outcome; the merge's decisions document | such a refusal or failure. **Reported:** each criterion file moved to the QA task, and each development task the rule dropped, with its operator note |

**Q5's positive control:** every goal the proposals were shown is found in the excused places
(`goals_not_found_in_proposals` lists none of them). If any isn't, E4 is void, not held, because the sweep didn't find
what it looks for.

**Read beside the shakeout, without a prediction:**
- the campaign's ending and each cycle's verdict;
- the cycle-end evaluations on revision 6, reported only, and each record's `start_failure`: none on a start that
  succeeded, its cause on one that didn't (SIP-0113 §10ae, #2797);
- whether #2664's `slot_subject_dropped`, #2743's namespace rule or #2297's empty-segment refusal fired;
- a declared catch-all client route read at `/__squadops_unmatched__` (#2755), if the calibration's manifest declares
  one;
- **#2792's hearing:** no promotion or move to `evaluating` refused as stale, and no `campaign_not_decided_campaign_moved`
  line, with no owner action behind it. One would be a seam finding;
- no `branch_rebased` row: a sample application never rebases (`branch_rebase.py:223-227`), though every launch passes
  #2770's `before_launch`.

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

**If the final deploy's `EVALUATOR_IMAGE` differs from `…-7`,** every baseline tree is re-read on the final deploy
before registration, so a roll and its baselines are always read by one evaluator (condition 7).

**What Q1 reads: the whole set, 5 and 4** (proposed; the supervisor's to confirm, §12). 2.4's Q1 read the HTTP
scenarios only and reported the page scenario beside them (the 2.4 cut's §12), because the browser driver could read a
correctly built field as absent when its label ended with a colon (#2706). `-6` fixed that (#2717, SIP-0113 §10x), and
`-7` keeps the browser path byte-identical (#2762). The page scenario passed on all six FastAPI + React trees of §2,
both 2.4 rolls included, and no page result moved on the re-read (R1b). The alternative is 2.4's rule: the HTTP
scenarios predicted, the page scenario reported.

**The spread between builds is wide,** as at 2.4: passed counts run 6–13 on FastAPI + React and 9–12 on Next.js
(§2). A scenario that needs a behaviour one build has and another lacks is outside the set. So the sets are small, and
Q1 is a narrow instrument: it reads only what every pre-#1966 build did. It reads a loss, not a gain.

**Reported beside Q1, not predicted:** each roll's count of passed scenarios, against its stack's range in §2, and each
scenario outside the set whose result differs between the rolls and the baselines.

**What Q1 can't see:**
- **Scenarios blocked on every baseline tree.** They are outside every set, and Q1 says nothing about them.
- **Public values.** Revision 6 replaced the eight revision-5 step values already public (SIP-0113 §10w). #2794 later
  widened the markers to a step's path segments (§10ad). Whether any revision-6 value is public under that reader is
  the supervisor's count after #2794, not this document's. Either way it weakens holding out, not the reading of a
  tree: no squad role reads the repository's history or the vault's other trees.

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

**The marker definition changed since 2.4** (#2794, SIP-0113 §10ad): a step's path is read segment by segment, a
declared route's words are no marker, and a whole `{name}` reference is none. So 2.4's count of provenances (8) doesn't
carry. Each baseline and its reading are taken by one reader, which is why condition 5 holds #2819 outside the window.

### 4.3 What 2.5 changed on the set's paths, merge by merge

Every merge in `v2.4.0..origin/main` (73 commits at drafting) was read for whether it changes a path a roll or the
shakeout runs: the agents' code, the runtime's, the evaluator's image, a request profile, a suite or the PRD (the
plan's §3). Six moved a sample application's plan, prompt or correction goldens since `v2.4.0`: #2727, #2728, #2746,
#2749, #2759 and #2802 (`git log v2.4.0..origin/main -- tests/unit/capabilities/handlers/goldens/qa_dev_handle_characterization.json
tests/unit/cycles/goldens/`). Each is read below.

| merge | issue | what it changes on a path the set runs | how the set reads it |
|---|---|---|---|
| #2717 (`e6a00faa`), #2762 (`b850471c`) | #2706, #2659, #2712, #2469; #2637 | the evaluator's `-6` (a label's trailing colon, the `if_enabled` click, the lock) and `-7` (the finer quality reading, reporting only; the proposal's quality moves held to the measures shown before) | Track B's re-read, which fixed §4.1's sets; Q1 on `-7`; Q4's report |
| #2759 (`d31d6e3a`) | #2253 (D12) | the note on each QA first call; the QA prompt goldens gain one message | **Q6**; Q1 and Q2 |
| #2811 (`4bad2a74`) | #2557 (D3) | the PRD's §5.2, every `group_run` cycle's input | **Q7** |
| #2746 (`eaa64d71`) | #2664 | a slot repair that drops its failing assertion's subject is refused, and spent | P5's handlers; each refusal reported (§4); Q1 and Q2 |
| #2728 (`2f70b40f`) | #2297 | the bound QA suite's row carries `declared_routes`; `contract_assertions_match` refuses an empty required segment unless the router's own answer is asserted | each refusal reported; a correction round inside the range is data; Q1 and Q2 |
| #2727 (`326f6c93`) | #2521 | a repair whose every write was dropped is spent, and the next round is told why | P5's handlers; each `repair_dropped` round reported |
| #2749 (`ca048f36`) | #2602 | on Next.js: the skeleton carries `vitest.pages.ts`, and the QA supplement's page example routes its fetch stub through `callRoute` (`development_profiles.py`); an increment's page appendix | the Next.js rolls (verdict, criteria, rounds, Q1, Q2). **The increment half isn't exercised:** no Next.js campaign runs |
| #2802 (`10a35adb`) | #2795 | an increment framing's merge gives a doubly claimed criterion file to the QA task; the development proposer's appendix | **Q9** |
| #2739, #2741 | #2578 | `increment_id`, the flow-run tags, the ledger's cycles | **Q8** |
| #2729 (`31dd41c7`) | #2553 | an input refusal reads `input_contract_failure`; `ATTRIBUTION_REGISTRY_VERSION` is 2 (`failure_attribution.py:57`) | declared (§10): the set's records are read under version 2, every 2.4 baseline's under version 1, and no comparison of attribution classes crosses them |
| #2735 (`b45a23f0`) | #2184 | the legacy per-agent store retired: the agents' images, entrypoint and compose mounts | P3; P2 (`2184`) |
| #2718 (`3dec9c4a`) | #2493 | the agents' service token read on two clocks | P2 (`2493`) |
| #2755 (`178dd9e1`) | #2754 | a declared catch-all route is read at `/__squadops_unmatched__` on an increment's acceptance | the shakeout, if its calibration declares one (§4) |
| #2748 (`b92143ba`) | #2743 | a proposal's scope leaves the stack's QA namespace to the framework; the tier reads the stack from the manifest | the shakeout's proposals and P4's tier notes. Track D saw no verdict change with this scope |
| #2792 (`5e99418e`) | #2789 | the hearing reads the campaign again before writing, and its writes carry the state it read | the shakeout's hearings (§4) |
| #2794 (`ad6e3ecb`) | #2786 | the marker definition; the runner's placeholder regex renamed, with no behaviour change by its PR | Q5's sweeps (§4.2); Q4's goal filter |
| #2797 (`2f08613c`) | #2793 | a failed start's cause on the evaluation record; the package goes to version 8 | Q3 reads version 8; each record's `start_failure` (§4) |
| #2785 (`693d219b`) | #2784 | a scenario's HTTP checks read the values its steps saved | nothing moves: 0 of revision 6's 59 HTTP checks names a saved value (#2785's count), and R1 held on the re-read's deploy, which carried it |
| #2732 (`0ed38538`) | #2561 | the deploy record names the served weights | a pin (§7) |
| #2807 (`fdd327fc`), #2812 (`6b9ee472`) | #2805, #2810 | the binding budget counts what a QA test or a repair's prompt shows; each handler's prompt is byte-identical (their characterization goldens) | **not exercised:** nothing in the set binds an instruction, so the budget holds nothing whatever it counts. A binding hold falsifies P5 |
| #2816 (`d0df8acb`) | #2815 | a product's QA suite runs on the product's tree. A sample application's run tree is `source_files`, byte for byte (`sample_run_tree_characterization.json`, captured before the change) | **not exercised on a sample application** |
| #2738, #2740 | #2619 | a repository-backed start writes a calibration record; a promotion onto a campaign branch. A sample application's start launches its calibration cycle, and its promotion is from the vault, as before (each PR's control) | Q8's calibration row; otherwise not exercised |
| #2716, #2719, #2726, #2734, #2761, #2763, #2764, #2766, #2769, #2770, #2771, #2772, #2773, #2774, #2777, #2778, #2780, #2788 | #2619, #2414, #2672, #2757, #2779 | products only. Each names its sample-application control: no profile is asked of a sample application (H.7, H.8), its launch passes no head (#2763), its profiles keep their stack (H.11), its skeleton supplement stays (H.13), its increments keep `qa.evaluate_increment` (#2774), its evaluation and package section are unchanged (#2778, #2788). #2780's new prompt sections are optional and empty without an anchor, and the QA and dev prompt golden moved only for D12 | **not exercised on a sample application.** The shakeout's launches pass #2770's `before_launch` unchanged (§4) |
| #2742 (`5aaece83`) | the owner's, nostromo#3 | the TensorFold key reader, and a two-lane candidate recipe beside the frozen one | condition 2 |
| #2720, #2721, #2722, #2725, #2730, #2731, #2747, #2791, #2801, #2803 | — | scripts no run executes, loaded-check rows, monitoring, CI and an integration test | none |

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
claim on 2026-10-29: IR-5, and IR-9's increment reading, weren't exercised, and #2818 is placed first in 2.6 or a 2.5.x
patch (§11). 2.4's G5 doesn't carry for IR-3 to IR-9: a scenario not run needs the owner's ruling, named in the cut
record.

### 6.1 Beside the set: IR-1, IR-2 and IR-10

- **IR-1, as at 2.4.0** (`docs/plans/2-4-0-integration-record.md`, "At the cut"): one `selftest` cycle of each seeded
  project through `cycles create`, one at a time, each completed with its artifacts. 2.4's took 36 min. 2.5 changed
  the create path every cycle takes (`prepare_cycle`: H.8's blocking gap, H.9's pin, H.11's recipe, H.13's blueprint
  pin), each with a sample-application control, so IR-1 reads that each seeded project still creates and runs.
- **IR-2, with one change.** 2.4 compared a standalone cycle with a Campaign's calibration cycle on `prj-z-continuum`
  (`var/campaigns/ir2-cut.yaml`). Since #2738, a repository-backed Campaign's start writes a calibration record and
  launches no cycle (SIP-0109 §24bv point 1, §24cc). So the Campaign's half is its first launched cycle, the
  increment's, which reaches `prepare_cycle` pinned at the record's commit. **It passes when:**
  - both cycles carry the Project's baseline commit and Development Configuration revision, and the same pinned commit
    (H.9: the first increment pins the same tree as a standalone create);
  - `pinned_from` reads `project_baseline` and `campaign_branch`, as H.9 defines them;
  - each pins its own snapshot.

  It runs with §6.3's `z_continuum` start, and both cycles are cancelled once read.
- **IR-10 is the set** (P5 carries its R3 and R4), as at 2.4.0.
- **IR-8's registry half, proposed again** (§12). 2.4 ran it at its cut: a Project imported, read at once, and refused
  a Cycle while `REGISTERING`. 2.5 changed the create path that refusal goes through, so it is worth the minutes. It
  needs a fresh id, since `prj-ir8-cut` stays `REGISTERING` on the Spark.

### 6.2 The demonstrations' readings under the plan's §3 rule

The rule: "A later merge that changes a path an earlier run's cycles executed … voids that run for the release claim.
That run is repeated, or the owner rules on it." It is read here as written, by run. For each voided reading, the table
also says whether the merge changed the path that wrote the reading's own evidence, which is what the owner rules on.

The deploys are read from `deploy_records` and `cycle_registry` (SELECTs, 2026-10-29): `dep_6ed09f6b500c` (`5e99418e`)
carried `z_shelfnote`; `z_continuum`'s rounds 1 to 3 ran on `dep_0a4f31cd9c10` (`10a35adb`), `dep_bf4b8db121fc`
(`fdd327fc`) and `dep_8cd26c67fd90` (`6b9ee472`), and round 3's last two cycles on `dep_aa6f0a54c53a` (`d0df8acb`).

| reading | its evidence | written on | later merges that change a path its run's cycles ran | do they change the path that wrote the evidence? | proposed |
|---|---|---|---|---|---|
| **IR-3**, (a)–(e) | round 3 (`cmp_ce4c95f2f307`): `cyc_60a71c2b2be2` bound the old content; the launch after the sync refused `STALE_SOURCE_PRECONDITION` and escalated until reconciled; `cyc_7e42e45adc6d` bound the new content at its rebased commit; the standalone `cyc_2a817b3e6503` bound the new content; no re-binding row | `dep_8cd26c67fd90` (`6b9ee472`) | #2816: `qa_test.py`, `qa_run_tree.py`, `qa_prompt_contents.py`, `source_repository.py` and `context_assembly.py`, the QA path both increment cycles ran | **No.** The binding, the launch gate, the reconciliation, the rebase and the create route are outside #2816's files. (c)'s new content is also bound by `cyc_ac0cb5a7b6b2` and `cyc_b22aeb556a44`, created on `dep_aa6f0a54c53a`, with the same entry (equal digests of `memory_cycle_bindings.entry_body`, read for this draft) | **the owner rules it stands.** A repeat needs a fresh `z_continuum` Campaign across another outside commit, about 4–6 box-hours, and meets #2818 again |
| **IR-4**, `z_continuum`'s suite | the sweep after round 3: no step value outside the suite's store and the evaluator's records, every place searched | the sweep on `dep_aa6f0a54c53a`; rounds 1–3 on four deploys | rounds 1 and 2, and round 3's cycles before `d0df8acb`: #2807, #2812, #2816 (budget and QA paths) | No: none adds a read of the suite. Round 3's last two cycles, `cyc_ac0cb5a7b6b2` (its proposal, framing and build) and `cyc_b22aeb556a44` (its repair), ran on `d0df8acb`, which no merge since has changed | **stands on those two cycles.** The earlier ones are voided and excluded, which changes nothing, since the sweep found nothing anywhere |
| **IR-4**, `z_shelfnote`'s suite | the same sweep | `z_shelfnote`'s cycles on `dep_6ed09f6b500c` | #2794, #2797, #2802, #2807, #2812, #2816 | No, as above | **repeated** by §6.3's `z_shelfnote` Campaign, with its own baselines before it and its sweep after |
| **IR-5** | — | — | — | — | **not exercised** (the owner's narrowing). No repeat |
| **IR-6**, the calibration records | `evl_36103956b2d1`, `evl_4d91d6076c7f`, `evl_600d64517d5a`, one per round: the page scenario and quality not applicable, lint `not_a_scaffold_stack`, nothing started by a stack | `dep_0a4f31cd9c10`, `dep_bf4b8db121fc`, `dep_8cd26c67fd90` | #2807, #2812 and #2816, on paths each round's later cycles ran | **No.** No merge since `10a35adb` changes `scenarios/`, `campaigns/progress.py`'s hearing, the sandbox's runner or the evaluator's image, and each reading was written at its Campaign's start, before its cycles ran | **repeated, in minutes:** §6.3's `z_continuum` start writes a record and its baseline reading on the final deploy. Or the owner rules they stand |
| **IR-6**, an increment | not exercised: no `z_continuum` increment delivered a tree | — | — | — | **named under the narrowing,** which names IR-5 and IR-9 only. The owner confirms it (§12) |
| **IR-7** | `z_shelfnote` (`cmp_73535ccef891`): the record's baseline reading `evl_29bfb2a58ea0`; the increment's `evl_5016d962be49` on its captured tree, 9 of 9 passed; lint by the blueprint's rule set | `dep_6ed09f6b500c` (`5e99418e`) | #2794 (`steps.py`), #2797 (`evaluate.py`, `evaluation.py`, `runner.py`, the sandbox's `scenario_runner.py`), #2802 (the framing's merge, whose refusals #2795 named), #2807, #2812, #2816 | **Yes, for #2797 and #2794:** the evaluation path, an additive field and a refactor whose PRs record no change of behaviour on a start that succeeds. No, for the rest | **repeated** by §6.3's `z_shelfnote` Campaign |
| **IR-8** | the evaluation records name `prj-z-continuum` and `prj-shelfnote`, and `config/projects.yaml` names neither | as IR-6 and IR-7 | as IR-6 and IR-7 | as IR-6 and IR-7 | **repeated** by both §6.3 runs. The YAML half is read on the tagged tree |
| **IR-9** | the increment reading not exercised. The Project's own baseline reads `lint` FAIL `inherited` at `15fc9a77` and `2070ba46` | — | — | — | **not exercised** (the owner's narrowing). No repeat |
| **#2780's anchored page** | the added page's route held by its anchor, in the increment and its repair | `dep_6ed09f6b500c` | as IR-7. Route rendering runs through the sandbox's `scenario_runner.py`, which #2797 refactored | yes, a refactor with no change of behaviour by its PR | **repeated** with `z_shelfnote` |
| **the missing-route negative** (a replay) | `DeclaredStartRoutes.render` on `cyc_7cbdae00b2ed`'s captured candidate, its route removed: broken, the increment rejected | `dep_6ed09f6b500c` | #2797's runner refactor | yes, as above | **replayed on the final deploy** (`replay-2780-missing-route.py`), in minutes |
| **Track D's uncounted run** (#2578) | R1–R4 on `cmp_9c9df268084a` | `dep_fbeecffcc625`, `dep_31949f050a30` | among others, #2759, #2763, #2770, #2771, #2792 and #2802, on the launch, hearing and framing paths a sample-application campaign runs | **Yes:** #2763 and #2771 change `launch_requests.py`, and #2763 and #2770 `campaign_launch.py`, the files that write the launch binding R1 reads. The plan's §5 judged the run standing before #2770 and #2771 merged | **re-read by the shakeout** (Q8), on the final deploy |
| **Track B's re-read** | R1, R1b, R2; §4.1's sets | `dep_0a4f31cd9c10` (`10a35adb`), `-7` | none: no merge since changes the evaluator's image, the sandbox's runner or `scenarios/` | — | **stands** (condition 7) |

**What the table assumes.** The final deploy runs `d0df8acb`'s code, so every reading taken on `dep_aa6f0a54c53a`
stands. A merge before registration, a shakeout fix among them, re-applies the rule to every row by the paths named
here, and the record names each case.

**The engine isn't one of the rule's paths.** The demonstrations and Track D's run were served by #2742's two-lane
candidate (condition 2). The rule lists the agents' code, the runtime's, the evaluator's image, a request profile, a
suite and the PRD, so the switch to the frozen recipe voids nothing. The record names it (§10), and the owner may rule
otherwise.

### 6.3 The repeats proposed

The supervisor and the owner decide (§12). Each runs on the final deploy after the exit rule holds, and before
registration, so a shakeout fix can't void it.
- **`z_shelfnote`: a fresh Campaign,** from `docs/plans/2-5-0-demonstrations/z_shelfnote-campaign.yaml`, its suite
  `a1a6a0b7…` pinned, with IR-4's baselines taken before it and its sweep after. It is read against the demonstrations'
  pre-registration §4, unchanged: IR-7, IR-8's `prj-shelfnote` half, #2780's anchored page and IR-4 on its suite. Then
  the missing-route replay runs again on its captured candidate.
  - **About 1.5 box-hours.**
  - **Expected:** its increment meets #2799 again, so it ends with nothing accepted, as before. IR-7 and the anchored
    page don't need an accepted increment.
  - **It is `z_shelfnote`'s third Campaign,** where IR-7's text says "first". The scenario reads the evaluation path,
    which the count doesn't change, and the record says so.
- **`z_continuum`: a Campaign started and aborted,** from `docs/plans/2-5-0-demonstrations/z_continuum-campaign.yaml`
  (suite `7ce88042…`), on `prj-z-continuum` at `2070ba46`, revision 6. Its start writes a calibration record and its
  baseline reading, which is IR-6's calibration half and IR-8's `prj-z-continuum` half. Its first launched cycle is
  IR-2's Campaign half (§6.1). It is aborted once that cycle is read. **Minutes,** beside IR-2's standalone cycle.
- **IR-3: the owner's ruling,** recommended as standing (§6.2).

**Box time, as a guide:** the shakeout about 1.5 a round, the chain about 2, the readings about 0.5, IR-1 about 0.6,
and the repeats and IR-2 about 2. That is about 7 box-hours with one shakeout round, against the plan's guide of about
6 for the cut. The supervisor's estimates have run high, so it's a ceiling to report against.

---

## 7. Pins (read at registration)

Blank until registration. Each is read when conditions 1–8 hold.

| pin | value |
|---|---|
| deploy commit | — |
| deploy record | — (`verify_loaded.py` from the main checkout) |
| image ids | — runtime-api, max, neo, nat, bob, eve, data: read from the running containers, equal to both configs' `frozen_image_ids`. The sandbox service's, which runs the held-out readings, read beside them |
| `EVALUATOR_IMAGE` | — expected `squadops-evaluator:lighthouse13.5-axe4.14-ruff0.16-eslint10.12-7` (`sandbox/environment.py:43`), §4.1's |
| model | — expected `qwen3.8-27b-tf-nvfp4` in every agent (`SQUADOPS__LLM__MODEL`), served by `squadops-tensorfold:0.6.6-cb2ebf05`; its weights from the deploy record (#2561); the engine's arguments, the frozen recipe's (condition 2) |
| held-out suite | revision 6, `89bffc198c99b6fd347ef51d6263f6e2360a680a42bb4f01138750e44809854a` |
| squad snapshot | — (`full-38-tf`), read from the deploy's API by the driver's `live_squad_snapshot` |
| loaded checks | — tracked rows in each config, every row of `loaded_checks.yaml`; on the deploy, loaded and not |
| set configs | — `2-5-0-cut-regression-fastapi-react.yaml` and `2-5-0-cut-regression-nextjs.yaml`, carried from the 2.4 cut's by its rules (§2); their sha256 |
| shakeout definition | `examples/03_group_run/campaigns/2-5-0-cut-shakeout.yaml`; its sha256 at registration — |
| record versions | attribution registry 2, campaign package 8 (§4.3) |
| HEAD at preflight | — |

---

## 8. Records, filled as read

| what | value |
|---|---|
| the final deploy | — |
| the engine's recipe | — |
| the sweeps' baselines, each round | — |
| shakeout rounds, and the round that met the exit rule | — |
| the demonstration repeats (§6.3), and the owner's rulings on §6.2 | — |
| registration | — |
| the chain: each roll's cycle, verdict, criteria, boot audit, correction rounds, QA repairs whose retest passed, model calls | — |
| the held-out readings | — |
| each prediction's reading | — |
| D3's reading, recorded on #2557 | — |
| IR-1 and IR-2 | — |
| each void and re-run, and each owner action | — |

---

## 9. Prohibited while the set is open

- **Merging to main.** A fix voids the set. Nothing else merges between opening the release PR and merging it
  (CLAUDE.md, "Release cut").
- **Rebuilding any service, or restarting the engine.**
- **Running anything else on the box** while a roll runs: the shakeout, the repeats, IR-1 and IR-2, and the held-out
  readings, which run after the chain's last roll (§2).
- **Any other caller of the engine** while a roll or the shakeout runs. Since #2742 the owner's crews share TensorFold,
  and the agents' metrics (P1) can't see their calls.

## 10. Drift the record must declare

- **Any difference between the tagged tree and the registered deploy,** each named as additive or behavioural.
- **Each void and re-run,** with its cause.
- **Each owner action,** and each ruling on a §6.2 reading.
- **The engine:** the recipe the set ran on, and the candidate the demonstrations and Track D's run were served by.
- **The record versions:** the set's failure records are attributed under registry version 2, every 2.4 baseline's
  under version 1.

## 11. What this set doesn't cover

- **A reliability rate,** for anything (§2).
- **Track A's narrowing** (the owner, 2026-10-29: "Narrow the claim, go to cut"). 2.5 claims a Campaign on a
  repository-backed Project through its record, proposal, binding, launch, reconciliation and evaluation. It doesn't
  claim an accepted increment on a product whose in-cycle tests need the product's own dependencies (#2818).
  - **Not exercised:** IR-5; IR-9's increment reading; IR-6 on an increment; the review-request push (§24ci (b),
    #2772), since nothing was accepted onto a campaign branch.
  - **Placed first in 2.6 or a 2.5.x patch:** #2818, with the product-path findings the demonstrations filed. Among
    them are #2799 (a vitest product's page criterion can't discriminate) and #2796 (the tier escalates every plan gate
    of a product's cycle), and #2817, #2814, #2809, #2813, #2804, #2798 and #2783 (the plan's §2.6).
- **The deferrals to 2.6:** #2723, suite revision 7, by the plan's deferral rule, since it wasn't ready when `-7` was;
  #2287, the box lease, and #2495, the scripted squad, both deferrable and unbuilt. Also #2421's remainder (the owner,
  2026-10-28) and #2230 (D5).
- **#1469,** unbuilt: blocked on its corpus (#1469, 2026-10-28). It is Track E, not marked deferrable, so it moves to
  2.6 on the owner's word (§12), as does #2286's remainder (the operator-key spec, the rotation, the restart and the
  runbook).
- **Every difference between the tagged tree and the validated deploy,** named at the reading as additive or
  behavioural. Expected: this document, its definition and the set's configs, and the release PR's version files.
- **Next.js on a campaign.** The shakeout runs FastAPI + React, as 2.4's did. On Next.js, D12, #2664, #2297 and
  #2602's page example are read on greenfield rolls only, and #2602's increment half (a page criterion that
  discriminates) isn't exercised.
- **The prompt budget on a sample application** (#2805, #2810). Nothing in the set binds an instruction.
- **Memory supply on a sample application.** Every roll declares memory disabled, and the shakeout supplies nothing.
  IR-3 read a binding on a product.
- **The held-out readings are one reading per tree.** The page scenarios' three-round agreement (SIP-0113 §10r) is the
  instrument's; it isn't re-read here.
- **A pulse check's behaviour.** The regression profile declares none, so P5 reads the pulse path as inert (IR-10's
  limit, carried).
- **#2814, unchanged since 2.4:** a JS or TS file past about 257 lines has no anchored edit form, so a repair of one
  edits without it, as on 2.4's rolls.

## 12. Decisions at this stop

**The owner's:**
1. **The engine** (condition 2). **Recommended:** TensorFold serves the frozen recipe for the shakeout, the repeats and
   the set, with no other caller on it while they run, and the candidate is restored after the set's last reading. The
   frozen recipe's status reads "Any change re-runs both gates", and the candidate's "not the frozen counted-verification
   recipe". **The alternative:** the candidate is ruled in, and the record names it as a difference from every 2.4
   baseline.
2. **The voided demonstration readings** (§6.2). **Recommended:** the `z_shelfnote` repeat and the `z_continuum` start
   (§6.3), and IR-3 ruled as standing. **The alternatives:** each ruled as standing, with no repeat; or IR-3 repeated
   too, about 4–6 box-hours.
3. **IR-6's increment half,** named under the narrowing as IR-5 and IR-9 are. Its cause is the same, #2818.
   **Recommended:** yes.
4. **D12's revert rule** (§3). **Recommended:** none, for the reasons there. The owner can set one before registration.
5. **#1469 and #2286's remainder to 2.6** (§11). **Recommended:** yes. Neither changes a path the set runs.
6. **The tag and the Release stay the owner's.** As at 2.4.0 (D9), the supervisor pushes the tag once the owner says
   go, after a set passes.
7. **D4's eight `*_memory_data` volumes** are kept as a backup until the cut (#2735). Removing them after the tag is
   the owner's.
8. **The set's size** is 2.4's, carried by the supervisor. The owner can change it before registration.

**The supervisor's:**
1. **Q1 reads the page scenario** (§4.1). **Recommended:** yes, since `-6` fixed #2706. The alternative is 2.4's rule.
2. **#2557's Next.js half** (Q7). **Recommended:** the two Next.js rolls' plans stand for a Next.js calibration. A
   roll's framing runs `validated-fullstack`, the profile a campaign's calibration runs, on the same PRD, so its design
   asks the same questions. Only the gate's decider differs. **The alternative:** a Next.js calibration under the tier
   beside the shakeout, about 1 box-hour.
3. **IR-8's registry half, again** (§6.1). 2.4 ran it at its cut, and 2.5 changed the create path it reads.
   **Recommended:** yes, in minutes, beside IR-1.
4. **#2819's timing** (condition 5).
5. **A second reader** reads this draft before anything runs, as 2.4's did.
