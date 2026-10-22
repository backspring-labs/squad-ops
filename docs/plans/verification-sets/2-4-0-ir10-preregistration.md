# 2.4.0 IR-10: the counted regression pair, pre-registered

**Written** 2026-10-22 by the Spark lane, before either roll launches. It is the run SIP-0112 §8.3.1 names:

> IR-10 | The counted regression pair on a deploy carrying both lanes, with `lessons: disabled` (SIP-0110) | the
> cadence policy, pulse-boundary checks and correction paths are unchanged, and the pair holds its verdict; a
> difference in pulse or correction behavior is a finding | both

`docs/plans/2-4-0-integration-record.md` records it as *not yet run*; this pair is its run, and its records go there.

## 1. The deploy

- **`dep_1b38de8af6b4`, from main at `23ed15f3`**, rebuilt on the Spark 2026-10-22. It carries both lanes' 2.4 work through
  #2647, among it:
  - the MacBook lane's #2636 (a run held on its binding sections, SIP-0110 §5ag) and #2639 (a task instruction's
    emergency withdrawal, §5ah), which change the executor's supply sites and its cycle loop: the reason IR-10 waited
    for them;
  - the Spark lane's #2628 and #2643 (a Campaign cycle's binding hold, SIP-0109 §24bw) and #2630 (policy v2);
  - #2564's build steps 1 and 2 (#2646, #2647): the browser vocabulary and the evaluator's driver, which no runner
    calls yet, and the evaluator tag `…-eslint10.12-3`.
- **Loaded checks:** `verify_loaded.py` answers 166 of 166 as expected on this deploy, and the deploy record is ok.
- **Model:** `full-38-tf`'s `qwen3.8-27b-tf-nvfp4`, served by TensorFold from the frozen recipe, as the 2.4 window and
  2.3.1's pairs ran.

## 2. The set

- **Two rolls, one per stack, both counted:** `fullstack_fastapi_react` and `nextjs_ts`, project `group_run`,
  `full-38-tf`, `validated-fullstack`.
- **Launched by `scripts/dev/verification_set_driver.py`** from a worktree pinned at `23ed15f3`, one roll at a time.
  The configs are `2-4-0-ir10-regression-fastapi-react.yaml` and `2-4-0-ir10-regression-nextjs.yaml`, carried from
  2.3.1's round-3 pair, with these changes: the name, the records home, this pre-registration, the notes, all 166
  loaded checks tracked, and this deploy's pins.
- **Every launch declares memory disabled** (D12, the driver's `MEMORY_DECLARATION`): no lesson is supplied, which is
  IR-10's `lessons: disabled`. No task or project instruction is given, and nothing is withdrawn.
- **The gate** (`progress_plan_review`) is approved with the set's constant notes, as every pair's has been.

## 3. The baseline

2.3.1's round-3 pair on `dep_d35eb75c759b`, the line's last, counted by the owner (2.3.1 plan, D6):

| stack | verdict | criteria | correction rounds | minutes | boot audit |
|---|---|---|---|---|---|
| FastAPI + React | accepted | 21/21 | 1 | 27 | PASS |
| Next.js | rejected | 16/17 | 3 | 115 | PASS |

The Next.js rejection was #2395 alone (a Next.js plan could give QA page-state tests the stack's vitest can't run), placed
in 2.4 and fixed there (closed 2026-10-20).

## 4. Predictions

| # | prediction | falsified by |
|---|---|---|
| R1 | the FastAPI + React roll is accepted, with every criterion verified and its boot audit PASS | any other verdict, an unverified criterion, or a boot audit FAIL |
| R2 | the Next.js roll is accepted, with its boot audit PASS, and #2395's signature doesn't recur | a rejection. If #2395's signature recurs, its 2.4 fix didn't hold; any other is a new finding |
| R3 | **the cadence policy and the pulse-boundary checks are unchanged:** as on the baseline, the cycle's applied defaults declare no `cadence_policy` or `pulse_checks`, and `pulse_verification_records` holds no row for either roll's runs | a declared cadence or pulse check, or any pulse record |
| R4 | **the correction paths are unchanged:** a correction round, when one runs, goes through the baseline's handlers (`development_correction_repair_handler`, `governance_correction_decision_handler`, by the record's emissions by handler). None of 2.4's new executor paths fires on a regression roll: no run carries a binding hold, a halt or a restart | a correction handler the baseline didn't use, or any binding hold, halt or restart |
| R5 | every tracked loaded check answers as expected in each roll's record | any check not loaded |
| R6 | memory stays disabled: every consuming task records a disabled exposure, and no lesson or instruction is supplied | any other exposure |

**What R3 can and can't see.** The regression profile declares no pulse checks, and has not since the baseline was set:
the table has held 5 rows in all, the last on 2026-05-16. So IR-10 reads that the pulse path stays inert, as the
pass condition asks. It cannot read a change in how a pulse check behaves when one runs, and the record says so.

## 5. Reading rules

- **A roll is read by its record:** the driver's JSON and markdown under `var/verification_sets/2-4-0-ir10/`, and the
  runs' rows for R3, R4 and R6.
- **A failure is read by its signature,** never re-run to a pass. A finding is filed the same session.
- **A roll lost to the infrastructure** (TensorFold, the registry, the box) is void, not failed. It is re-run on the same
  deploy, and the record says so.
- **Nothing deploys between the two rolls.**

## 6. What IR-10 doesn't cover

- **The cut's own deploy.** Later 2.4 work changes it: #2564's steps 3 to 8, #2551. The integration record names
  IR-10 among what the cut runs on its own deploy.
- **The pulse path's behavior,** above.
- **Outcome Evaluation:** a regression roll is no Campaign cycle, so no scenario runs and no quality is measured.
