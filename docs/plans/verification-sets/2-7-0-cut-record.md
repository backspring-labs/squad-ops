# 2.7.0 cut record: what the deploy ran, and what the cut doesn't cover

**The line:** `docs/plans/2-7-0-plan.md`, adopted 2026-11-08, a stabilization release. Its claim is §1's six lines, and
its cut evidence is §4.6's. This record reads each against the pinned deploy. Times are UTC.

## 1. The deploy the cut was read on

- **`dep_d2b4ca823f07`,** every service built from main `ae684458` (#3012), recorded 2026-11-10 03:02:45 by
  `rebuild_and_deploy.sh all` (`deploy_records`).
  - **Its image ids:** runtime-api `1db21765bb19`, max `60da24770386`, neo `d7b8b1d54914`, nat `2a6d72840210`, eve
    `a69d054d4f3a`, data `4c6fc7f09844`, bob `2dc9858c4d8a` (`2-7-0-soak-preregistration.md` §9).
  - **`verify_loaded.py`:** 256 loaded, 0 not. The deploy record describes the 24 services that run.
  - **The scripted model's digest** is `4721341de0a2`, the soak's library digest (§9).
- **What ran on it,** in order:
  1. the shakeout pair (§2);
  2. the soak's dry run `cmp_5113d589fd4e`;
  3. the counted increment (§3);
  4. the soak (§5);
  5. the restart diagnostic `cmp_e27a006adea1` (§5).

  No deploy was made while a Campaign ran. The runtime API and the six agents didn't restart between 03:02 and
  the soak's end (`docker inspect` `StartedAt`, 03:00:59 to 03:02:28).
- **What the tag adds beyond it,** all of it prose (`classify_ci_diff.sh`: every path is under `docs/`):
  - this branch: the shakeout set configs, the soak pre-registration's §9, the restart diagnostic's definition, the
    soak record and this record;
  - the release commit: the version bump, the version markers, the changelog, the ROADMAP timeline and the
    open-issues snapshot.

  Only `pyproject.toml`'s version touches code. The difference is additive. The deploy reports 2.6.1 (the
  shakeout records' `framework 2.6.1`) until the post-tag rebuild, which changes only that.

## 2. The shakeout (plan §4.3): one pair, no seam finding

`docs/plans/verification-sets/README.md`'s loop, with the plan's definitions: one pair on the final deploy, and both
stacks on `group_run`, `full-38-tf`, `validated-fullstack`. The records are under
`var/verification_sets/2-7-0-shakeout/` in the main checkout. Their set configs are
`2-7-0-shakeout-fastapi-react.yaml` and `2-7-0-shakeout-nextjs.yaml`.

| Stack | Cycle | Verdict | Criteria | Correction rounds | Boot audit | Wall clock |
|---|---|---|---|---|---|---|
| FastAPI + React | `cyc_fa03dc263093` | **accepted** | 21 / 21 | 0 | PASS | 21 min |
| Next.js + TS | `cyc_f058965a33b0` | **rejected** | 20 / 21 (`vc-suite-passes` not verified) | 3 | PASS | 38 min |

**The Next.js rejection is the cycle's defect, not a seam's.**
- **The run:** implementation run `run_684eea537dac` failed. Its reason: "plan_defect: correction terminated at round
  2 — failure signature repeated from round 1".
- **The failure:** the built app's own UI tests. The last test report (`art_da91c79e0d1c`, 04:45:12) fails on
  `Unable to find an element by: [data-testid="run-error"]` and `[data-testid="run-not-found"]`. Its view rendered
  neither.
- **Why it isn't a seam:** the boot audit passed, every declared route rendered its view, and P0 held. The plan's §4.3
  says a defect in the application a cycle built is the cycle's, and doesn't reset the loop.

**The one non-execution, `1 missing_tooling`,** is in the Next.js record (`shakeout-20261110T044642Z.md`, "non-execution
by skip reason").
- **Where it was:** one patch verification of `task-run_684eea53-m007-qa.test`, at 04:42:47. Its status was `passed`,
  over 10 checks: 6 were the agent's rows, executed in the qa agent, and the rest were evaluated in the runtime API. The
  log reads `skips=missing_tooling:1`.
- **What was skipped: a check that needs the Node toolchain,** in the runtime API, which has none
  (`command -v npx node npm` finds nothing in `squadops-runtime-api`). A check whose tooling is absent where it runs
  skips as `missing_tooling` and never fails (`acceptance_check_spec.py:1660`).
- **Which check, unverified.** The record doesn't name it. The run's only Node-run typed check is `frontend_compiles`
  (7 rows, all passed, in the agents).
- **The repaired page was then retested in the qa agent:** `retest-run_684eea53-01-s01-qa.test`, dispatched the same
  second. So the skip is a named non-execution on a passing verification, not a finding.

**Rounds: one pair.** The plan's exit rule is a pair on one deploy with no new seam finding. The budget is three pairs,
and this took one. No other shakeout cycle ran in the line (`cycle_registry`, cycles with no Campaign since 2026-11-08).

## 3. Track E: the counted increment (plan §4.5, #2827)

**The Campaign:**
- `cmp_ec6f1c5b709a` on `prj-z-continuum`, squad `full-38-tf`, a real-model run, on the pinned deploy. It was created at
  04:48:18 and completed at 05:03:16, with outcome `success`, at §10 row 3 (`objective_met`, row 10).
- Its calibration record is `calrec_27f5ed34dfee`, at `fad7fba7eb81`, Development Configuration revision 7 (row 3).
- One cycle, `cyc_3654c547f70c`, was accepted and promoted onto the campaign branch (row 8):
  - capture `7c70e1fa4f69`, whose parent is `fad7fba7eb81`;
  - one frozen criterion, `T1`;
  - verification `art_366f62e8862a`.

**The ruling note is wrong.**
- Row 7 (04:51:13, `campaign-supervisor`) reads "unattended scripted run: approved as it stands by the
  pre-registration's written rule (#2892 §3 step 1)".
- That's the soak dry run's text, carried by the watcher's ruler.
- This Campaign was a real-model run, not scripted (squad `full-38-tf`, `cycle_registry`), and #2892 isn't its
  pre-registration. It was approved as it stood.
- The note stays as written.

**The two `scenario_evaluations` rows,** both on suite digest `7ce880421ac1`. Only ids, digests and verdicts are read
here; no goal, step value or scenario content is.

| Evaluation | Of | Tree | Applicable: passed / failed | Not applicable | Start failure |
|---|---|---|---|---|---|
| `evl_2fe64bbc80f8` | the calibration record `calrec_27f5ed34dfee` | `a655d7b41351` | 5 / 4 | 1 | none |
| `evl_ac2e052bd45f` | the increment `cyc_3654c547f70c` | `1611924cad40` | 7 / 2 | 1 | none |

| Reading | Result | Evidence |
|---|---|---|
| **IR-5:** the sandbox revision, the Git commit, the Campaign's accepted tree and the Outcome Evaluation result resolve to one another, and none is stored in another's field | **holds** | The `captured` mapping for `cyc_3654c547f70c` (`project_source_mappings`) holds commit `7c70e1fa4f69…` (40 hex), sandbox revision `c5a2b8f2237b…` (64 hex) and tree `1611924cad40…` (64 hex).<ul><li>Its commit equals `campaigns.accepted_commit` and row 8's capture.</li><li>Its tree equals `campaigns.accepted_identity` and `evl_ac2e052bd45f.evaluated_tree_identity`.</li><li>The verification's `candidate_revision_id` is the sandbox revision, and its `candidate_tree_identity` is the tree.</li><li>The `seeded` mapping's tree `a655d7b41351` is the calibration evaluation's tree, and the increment evaluation's `previous_accepted_tree_identity`.</li></ul>Each identity is in its own field, and the sandbox revision differs from the tree |
| **IR-6's increment half:** an external Project with its own layout and no interface manifest runs through Outcome Evaluation, started by contract 7's commands | **holds** | Configuration revision 7 declares `stack: null` and the start `.venv/bin/continuum run --host 0.0.0.0 --port 4041`. On `evl_ac2e052bd45f`:<ul><li>9 scenarios ran, with no start failure;</li><li>one reads `not_applicable`;</li><li>lint reads `not_measured`, `not_a_scaffold_stack`, so nothing started by a stack and no manifest was read;</li><li>quality reads `not_applicable` with no pages.</li></ul>The evaluation row records neither the start's revision nor its `http_base`, so the start is read from the configuration revision that the calibration row binds |
| **IR-9's increment reading:** an inherited failing native check stays `FAIL`, `inherited`, independently of Outcome Evaluation | **holds** | `art_366f62e8862a`, policy `no-introduced-regression/v2`, verdict `accepted`:<ul><li>`lint` reads `FAIL`, attribution `inherited`, through its findings reader (`ruff`, readable);</li><li>`tests` reads `PASS`, `inherited`.</li></ul>Outcome Evaluation's own lint field on `evl_ac2e052bd45f` is the scaffold lint's `not_a_scaffold_stack`. Neither record reads the other |
| Promotion onto the campaign branch, and the review-request push (SIP-0109 §24ci (b)) | **promotion read again; the push not made** | Promotion is row 8. Row 10's binding says `contribution: {due: true}`, but there is no `project_contributions` row for the cycle, so no review request was pushed for this increment. The push stands on §4.5's historical evidence: BT-11, battle-trainer PR #11 |

- **H.13's two items** were built in #2999 (SIP-0112 H.29). Their loaded checks, `2827-repaired-suite-runners` and
  `2827-planless-qa-view`, read `ok` on this deploy.
- **#2827's done-when** is therefore read. SIP-0109's and SIP-0112's ledger rows for it are still to be marked
  shipped (plan §2, Track E). This record doesn't change them.

## 4. The recording, `cmp_f14bab82c35f`

- **The run:** a real-model Campaign on `prj-shelfnote`, `full-38-tf`, deploy `dep_16a1cb4f54c8` (`40e81a4e`), from
  2026-11-09 12:51:01 to 17:44:38. It is uncounted, and its readings decide nothing (pre-registration §3).
- **Its cycles:** 15 launched. Ten increments ended, six of them accepted: SN-6, 7, 8, 10, 12 and 13.
- **The owner's seat acted twice.**
  - **One resume:** row 31 is the supervisor's resume, refused with `resume_not_delegated`. Row 32 is the owner's
    seat's `abandon_and_propose` after repair `cyc_d5ce68001c7a`'s row 9.
  - **The close:** row 78, an abort when nothing was left pending after row 77's escalation. It is recorded as outcome
    `aborted`.
- **Its dry runs:**
  - **`cmp_10099196fce1`,** on `dep_d67c384673bd` (`1158ea13`). Both proposal runs failed (row 6), on the recorder's
    derived-fields defect. The admin closed it as `aborted` (row 9), and #3012 fixed the defect.
  - **`cmp_5113d589fd4e`,** on the pinned deploy. It completed with `success` at row 3 (row 60), with the soak's
    sequence. It has the same divergence inside launch 8 as the soak (§5).

## 5. The soak

`docs/plans/verification-sets/2-7-0-soak-record.md` reads `cmp_056721e622e2` against its pre-registration.

**What it reads:**
- **The run:** completed `success`, at its sixth acceptance, after 10 h 52 min, with 8 increments ended and 6 accepted.
  The launches, kinds and acceptances are the recording's.
- **Every call was scripted:** 156 scripted calls, and none reached the engine.
- **The injections:**
  - **The pause** (§6.1) was exercised as predicted, including the refresh idle expiry.
  - **The upstream push** (§6.2) reconciled as predicted, with one `branch_rebased` row. The reconcile ran late, because
    of driver defects.
  - **The access token** (§6.4) refreshed silently.
  - **The owner's-seat resume** (§6.5) was as predicted.
- **Not exercised in the soak:**
  - **the controlled restart** (§6.3), because of a driver defect;
  - **the session's maximum lifetime** (§6.4). The driver's false re-logins moved it past the soak's end.

  Both are read on the restart diagnostic `cmp_e27a006adea1`, in the soak record's §6.3a and §6.4a.
- **A divergence inside launch 8's run,** filed as #3020. The Campaign's row is the recording's.

> **[TO BE FILLED by the supervisor, once §6.3a and §6.4a are read]** The diagnostic's verdict on the restart and the
> maximum lifetime, in one line each.

## 6. The cut conditions (plan §4.6, and the claim's lines in §1)

| Condition | Status | Evidence |
|---|---|---|
| The passing shakeout pair (§4.3) | **met** | §2: one pair on `dep_d2b4ca823f07`, with no seam finding |
| The soak's record (§4.4), against the claim's fifth line: at least eight increments over at least nine hours, through a restart, token expiry past the session's maximum lifetime, an upstream push and a pause, with no model in the loop | **not met by the soak alone** | Met: eight increments, 10 h 52 min, the push, the pause and no model. Not met: the restart and the maximum lifetime, neither exercised in the soak. **It needs one of two things.** The restart diagnostic's readings could stand in for the two injections, which the pre-registration doesn't provide for (§6: "recorded *not exercised*"), so they'd need to be accepted as standing in. Or the claim's fifth line is narrowed here, as plan §1 provides. **[TO BE DECIDED, with §6.3a and §6.4a]** |
| Track E's readings (§4.5) | **met** | §3: IR-5, IR-6's increment half and IR-9's increment reading hold on `cyc_3654c547f70c`. The review-request push wasn't made for it, and its evidence stays BT-11's |
| Each fix's live check on the pinned deploy | **met, as loaded checks** | `verify_loaded.py`: 256 loaded, 0 not. They read that the deployed modules carry each fix. They aren't a behavioural reading of each fix, which the fixes' wiring tests carry |
| The vault integrity pass (#2931) | **met: 0 corrupt** | `scripts/dev/vault_integrity.py` over `data/artifacts`, at 2026-11-10 16:07:51 (`var/verification_sets/2-7-0-vault-integrity-20261110T160751Z.json`): 0 for each kind (unreadable metadata, missing content, mismatched content, content without metadata, stray temp files). It ran while the diagnostic was writing, so it's repeated at the tag |
| The SIP sweep, expected none | **to be run at the cut** | Plan §4.6: SIP-0112 (#2709, 2.8), SIP-0115 (the operator's reading) and SIP-0109 (#2287, #2781) each keep open rows |

## 7. The issues placed in 2.7

**Read 2026-11-10 with `gh issue view`.**
- **Closed:** every committed defect and debt item (17), #2495, and the five administrative closures.
- **Open: #2892, #2827 and #2760.**
  - **#2892:** closes on the soak record, once its §6.3a and §6.4a are read and §6's second condition is decided.
  - **#2827:** its done-when is read (§3). It closes with its SIP ledger rows.
  - **#2760:** its readings, not its closure. Its four questions stay the operator's (plan §2, Track D). The readings,
    all for `squadops-supervisor`:
    - **The access token, 600 s:** refreshed silently on every call from 05:43:14 to 15:59:29, at most 780 s apart. The
      API logged no `401` outside §6.1 (soak record §6.4).
    - **The refresh token's idle limit, 1,800 s:** after 2,150 s with no call, the next call got `401` and the CLI didn't
      re-log in by itself. The non-interactive login, the resume and the ruling then succeeded (soak record §6.1).
    - **The session's maximum lifetime, 28,800 s:** **[TO BE FILLED from soak record §6.4a]**.
- **The stretch item #2826** wasn't taken, and stays open.
- **Filed by this record:** #3020, launch 8's replay divergence (soak record §7.2). Not placed.
- **Also open, not placed in 2.7:** #2976 (#2402's follow-up, filed at adoption) and #3000 (#2949's remainder).

## 8. What the cut evidence doesn't cover

- **The tagged tree differs from the deploy only by prose** and the version (§1).
- **The soak's restart and maximum lifetime** were read on a diagnostic, not on the soak (§5, §6).
- **Launch 8's replay** diverged inside its run (#3020). The row comparison §7.2 registers didn't see it, and the dry run's
  "matched" was at the rows only. The run's stored failure reason doesn't name what ended it, which bears on the claim's
  first heading, "a verdict says what happened". It's untraced.
- **The reconcile's timing.** §6.2's reconcile was made during increment 2's build, not at its gate. Whether a push alone
  holds a launch wasn't read.
- **The review-request push** wasn't made for the counted increment. Its evidence is still BT-11's, from `faed0f6f`.
- **The claim's fourth line,** "a power loss, a reboot or a redelivered task leaves a run that recovers", was read live
  only through the restart diagnostic's controlled restart. A power loss and a reboot are read in #2931's and #2932's
  tests, not on the box.
- **The claim's first three lines** (D1, the qa path's rendering, a vitest page criterion) aren't read live by a run
  arranged to trigger them. The shakeout pair and the counted increment ran through those paths. The fixes' wiring
  tests carry each.
- **No model's quality.** The soak is scripted. The counted increment is one cycle on one product, and the shakeout's
  Next.js cycle was rejected on its own app.
- **The Next.js shakeout's one check,** skipped as `missing_tooling` in the runtime API, isn't named by its record (§2).
- **The counted increment's ruling note** says it was scripted, which is wrong (§3).
