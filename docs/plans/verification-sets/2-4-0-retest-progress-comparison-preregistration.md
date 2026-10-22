# 2.4: a red retest judged by the tests that fail, before and after — pre-registration

**Written** 2026-10-22 by the Spark lane, before the change merges and before either arm launches.
**Approved** by the supervisor under the owner's grant of 2026-10-19. The 2.4 plan §4.1 places #2306's fix after the
window, "each output-quality change measured on the yardstick, pre-registered as 2.3's #2202 and #2205 comparisons
were".
**Issue:** #2306, question 1, part 1 (ruled 2026-10-22, issuecomment-6340246074). **The change:** the PR that adds
SIP-0086 §12e.
**Uncounted.** Both arms are comparisons, not counted rolls.

## 1. What changes, and what it reads

When a correction round's repair passes its typed verification but its retest still fails, the repair is kept only if
the retest made progress (SIP-0086 §12b). Today's comparison folds the row's facts into every failing test's element:
the suite's health, the exit code and the round's failure category. So a repair that cleared an application error, or
made a suite load, reads as a shift, and the repair is discarded and the task re-rolled. The change judges the failing
tests by identity and the facts by their direction (§12e).

**What it reads:** whether the change keeps the repairs it should and only those. The change acts only on a red
retest, and a pair of rolls rarely has one. So the mechanism is read on the stored corpus (§2). The live pair (§3)
judges any red retest it meets, and reports any difference between the arms beside IR-10's pair. One roll per stack
per arm can't show the build unchanged; it can show a difference.

## 2. The replay: the primary reading

**What it is: a replay of the function, named as one.** It calls `retest_reduction_or_refusal` with each side's rows in
hand. It proves the rule on recorded inputs, and says nothing about whether a live cycle reaches it. §3's pair and the
executor-entry tests (`test_outcome_routing.py`) cover the reach.

**The corpus:** every red retest of the 19 runs terminated as `plan_defect` from 2026-09-14 to 10-22, 20 in all
(#2306's replay).
- **18 are rebuilt as rows** from the stored reports and the runtime's log lines. They're committed as
  `tests/fixtures/roll_replays/2306-red-retests.json`, with free text replaced by labels. Two alternative readings ride
  beside them, where a probe outcome wasn't logged.
- **2 were logged as kept** (6f518c27 r0, d34a3039 r0). Their rows weren't rebuilt, so they aren't read here.

**Calibration:** main's rule reproduces all 18 of the replay's own verdicts on the rebuilt rows.

| # | prediction | falsified by |
|---|---|---|
| P1 | the change keeps exactly four retests main refuses: be3caea2 r0, a1e8f6da r1, 56d6ead9 r0, b56f8bff r0 | any other retest moving from refused to kept, or one of the four still refused |
| P2 | every rebuilt retest main keeps stays kept: 642c6086 r0, 7b9430c9 r0, 2f14e827 r0, and a1e8f6da r1's alternative reading | any of them refused |
| P3 | every repeat is refused as `no_progress`, and 6492fa2d r1, whose retest fails a test that passed in its round, as `regressed=1` | any of them kept |

**What it rests on.** be3caea2's and a1e8f6da's retest probe outcomes were not logged. The replay reads their probes as
passing, from the suites' own output (the create answers 201). The fixture holds the other reading too: be3caea2 is then
a repeat, and refused.

## 3. The live pair

**The arms.**
- **Before:** main as it is when this merges (`ba757d2a` and this document), rebuilt and deployed. The deploy id, commit
  and image ids are recorded on #2306 before the first roll.
- **Between the arms:** the change merges, and nothing else does. Every image is rebuilt from that merge, and its deploy
  is recorded on #2306 before the after arm's first roll.
- **After:** the same configs on the new deploy.

**The rolls.** One uncounted roll per stack per arm, `fullstack_fastapi_react` and `nextjs_ts`, project `group_run`,
`full-38-tf` (TensorFold's NVFP4 recipe), `validated-fullstack`, memory declared disabled.
- **Driver:** `scripts/dev/verification_set_driver.py shakeout`.
- **Configs:** `2-4-0-retest-progress-fastapi-react.yaml` and `2-4-0-retest-progress-nextjs.yaml`, carried from IR-10's.
  - **What changes:** the name, the records home, this pre-registration and the notes. The deploy pins are dropped,
    since an uncounted roll doesn't read them.
  - **The loaded checks:** they track IR-10's 166 rows. Each arm launches from a worktree at its own deploy's commit,
    so each row is read against that arm's own `scripts/dev/loaded_checks.yaml`. The change rewrites one of those rows,
    `2340-runtime`, to read the probe rule through the new comparison. #2306's own row isn't tracked; L1 reads it.
- **The gate** is approved with the set's constant notes.
- **Which checkout reads which deploy.** Each arm launches from a worktree at its own deploy's commit.
  - **The gate:** that worktree's `scripts/dev/verify_loaded.py` answers every row as expected against its deploy.
  - **#2306's own row:** the change's `scripts/dev/loaded_checks.yaml` carries it, so L1 runs it from #2663's checkout
    (`verify_loaded.py --only 2306`) against each deploy.
- **Not run if:** main's CI is red on the deployed commit, the box isn't idle, or the gate answers any row
  unexpectedly.

| # | prediction | read from | falsified by |
|---|---|---|---|
| L1 | **the change is loaded only in the after arm:** `verify_loaded.py --only 2306` prints `movement=shifted` on the before deploy and `kept` on the after deploy | the two answers, recorded on #2306 | any other answer |
| L2 | **every red retest is judged and logged:** each one in either arm logs `progress_kept` or `progress_not_kept why=…`, and each after-arm verdict is what the rule computes on that retest's stored evidence, rebuilt as rows the way the fixture's are | the Prefect log table; the round's and the retest's stored reports | a red retest with no verdict line, or a logged verdict the rebuilt rows contradict |
| L3 | **each keep rests on the stored evidence:** for each repair the after arm keeps, the round's and the retest's stored reports agree that no test the round ran fails in the retest; each criterion credited to patch verification matches a failing row of the round by check and params; each fact logged as improved is visible in the stored rows; and the next round's failure is the retest's | the stored reports, the verification records and the log line | any of the four not borne out |
| L4 | **the yardstick, reported per arm:** each accepted roll's delivered tree is read by held-out suite revision 5 (`92a26ad0…`) through `scripts/dev/read_scenarios.py`, and by the boot audit | the reading tool's records; the roll records | not a rate. A scenario `blocked_unverified` for a reason in the evaluation's own machinery is a finding |
| L5 | **the build is otherwise unchanged:** both arms' verdicts, correction rounds and minutes are recorded beside IR-10's pair on `dep_1b38de8af6b4`. A difference is reported, and only one through a red retest is attributed to the change | the roll records | — |

**When an arm has no red retest,** L2 and L3 are recorded as *not exercised* for it, and that is the expected case.

## 4. What this does not read

- **A rate.** It doesn't read whether keeping these repairs makes more runs accepted. Four of 20 stored retests change
  verdict, so a rate would need many runs.
- **Part 2** (a kept repair surviving a later refused round), and #2306's questions 2 and 3. Each is ruled and measured
  on its own.
- **The replay's reach.** §2 proves the rule on recorded inputs. That a live retest arrives with the rows it was given
  is the executor-entry tests' and L2's.

## 5. If a prediction fails

- **A replay prediction:** the change doesn't merge, and the record goes on #2306.
- **L2 or L3:** the change is reverted, or corrected and measured again, and the record goes on #2306 and SIP-0086
  §12e.
- **L4 or L5:** reported. A finding the change can't have caused is filed on its own.
