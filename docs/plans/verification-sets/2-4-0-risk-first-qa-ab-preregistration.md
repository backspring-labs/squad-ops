# 2.4: risk-first QA instructions, an A/B on replayed increments — pre-registration

**Written** 2026-10-22 by the Spark lane, before either arm launches.
**Revised** the same day, for a fresh second reader's findings, before anything ran (§7).
**Approved** by the supervisor under the owner's grant of 2026-10-19.
**The plan's D6** (ruled 2026-10-17): "the A/B in 2.4; adoption a separate ruling, not before phase 2's decision".
**Issue:** #1966. **The design:** #1966, issuecomment-6341627571, revised as here.
**Uncounted.** It is an experiment, and its arm B never merges unless the owner adopts it.

## 1. The question

`SIP-Verification-Yield` (proposed) §19–§21 and §35–§38 tell QA to work risk-first:
- find the faults a change could plausibly have;
- add the minimum verification that tells each from correct behaviour;
- accept "no additional automated test is justified" as a legal answer beyond what a contract requires.

Does QA, told this, write less verification without letting more defects through?

## 2. The arms

They are deploy against deploy, with the same model on both: `full-38-tf`, TensorFold's frozen NVFP4 recipe. Memory is
declared disabled on both, as every measured roll.

**Arm A:** `dep_787b72fcf866`, from main at `53a78031`.

**Arm B:** a rebuild of `experiment/1966-risk-first` at `cd4e04bf`, which is `53a78031` plus one commit. Its deploy is
recorded on #1966 before its first replay.

**What arm B changes** (3 files, 17 lines). It changes the text the plan-derived `qa.test` path reads, and nothing else:
- **The `qa.test` task fragment's scope discipline** (`fragments/shared/task_type/task_type.qa.test.md`). The plan's QA
  tasks render it on the focused path. Arm B adds:
  - each test catches a named fault of a requirement the task states;
  - each acceptance criterion still gets its test;
  - beyond those, no further test is a correct answer.
- **QA's identity** (`fragments/roles/qa/identity.md`). "Create comprehensive test cases" becomes "find the faults a
  change could plausibly have, and write the tests that tell each from correct behaviour".
- **QA's planning prompt** (`request.qa_propose_plan_tasks.md`):
  - plan by fault, not by count. The worked example drops its `min_count: 5`;
  - no further qa task is a correct answer where the development tasks' criteria already verify a requirement.

**Not in arm B:**
- **#2297's rule** (no case the interface can't express). It is placed in 2.4 on its own, and it would act on exactly the
  rounds V3 counts.
- **A per-test justification line.** The template that would have carried it renders only on the legacy path, which no
  plan-derived task takes.

**Unchanged on both arms:**
- SIP-0109 §8.2: each criterion an increment adds still gets one executable test that fails on its baseline, held by the
  plan gate and the increment evaluation;
- the scaffold's frozen shells and the probes, and every gate;
- the builder role.

**Rendered before launch** (V4's first reading). QA's assembled `qa.test` system prompt, built from each tree's assets the
way the agent's entrypoint builds it:
- **arm A:** sha256 `bf72a4f78c90`. None of arm B's text, and "comprehensive test cases".
- **arm B:** sha256 `62599c45e860`. Arm B's text, and not "comprehensive".

The planning prompt carries "Plan by fault" only on B.

## 3. The increments

The 2.4 window's accepted increments, two per stack, each replayed once per arm. The vehicle is
`scripts/dev/replay_increment.py --campaign C --increment N --squad-profile full-38-tf` (#1959), with #2667's fix: a replay
runs on the stack its source ran on. Each replay runs from its own baseline tree, approved change request and frozen
criteria, outside its campaign.

| # | stack | campaign | increment | its cycle in the window | change request | what it adds |
|---|---|---|---|---|---|---|
| I1 | FastAPI + React | `cmp_83d63c2ebb50` | 1 | `cyc_f9930df7c925` | `art_64e0d711c5d6` | capacity |
| I2 | FastAPI + React | `cmp_83d63c2ebb50` | 3 | `cyc_b7432a9633a5` | `art_122477b8c1d8` | sorting (its accepted second try) |
| I3 | Next.js | `cmp_ae20bfd95bc3` | 1 | `cyc_e5370cec344f` | `art_600396287697` | capacity |
| I4 | Next.js | `cmp_ae20bfd95bc3` | 2 | `cyc_679608d64edc` | `art_c9d2a17bb8b0` | sorting |

With #2667, each dry run resolves on the current deploy to its source's stack.

**The order:**
1. arm A's four replays on `dep_787b72fcf866`;
2. then arm B's rebuild and its four replays.

That is eight cycles, one at a time, only on an idle box, and never while another measurement runs.

**The plan gate** (each replay pauses at `campaign-reference`'s plan review) is approved as it stands, on both arms. The
notes are the same on every replay: "#1966 A/B: approved as proposed". There is no other intervention. A replay that
fails is left to its own rules.

## 4. Predictions

N is 4 per arm. These are mechanism readings, not rates. A replay is read on its accepted tree. A rejected replay is read
under V2 and reported under V1.

| # | prediction | read from | falsified by |
|---|---|---|---|
| V1 | **QA writes fewer tests of its own:** the test functions in the qa-authored test files of B's accepted tree, apart from the criterion tests and the scaffold's shells, are fewer than A's on at least 3 of the 4 increments | each accepted tree's test files in the vault: `def test_` in pytest files, `it(`/`test(` in vitest files, outside `criteria/` and `__tests__/scaffold/` | 2 or more increments where B has as many or more |
| V2 | **no more escapes:** every frozen criterion that discriminates on A still discriminates on B; no held-out scenario (suite revision 5, `92a26ad0…`) fails on an accepted B tree that passes on that increment's accepted A tree; and no increment A accepts is rejected on B | each replay's increment evaluation; `scripts/dev/read_scenarios.py` on each accepted tree | any criterion, scenario or acceptance lost on B |
| V3 | **no more rounds from QA's own tests:** correction rounds whose repair went to QA (`qa.test_repair`) and whose retest then passed, a demonstrated QA-side defect, are no more on B than on A | the rounds' dispatched repair tasks and retest results in the runtime's log | more such rounds on B |
| V4 | **the change is what ran:** on each arm's deploy, the QA container's assembled `qa.test` system prompt carries arm B's text on B and main's on A, as rendered in §2; and the stored `qa.propose_plan_tasks` requests carry "Plan by fault" on B only | `docker exec` the same render in `squadops-eve` on each deploy; the generations' full requests (`scripts/dev/read_full_prompt.py`, #1756) | either arm carrying the other's text |

**Reported beside them, not predicted:**
- qa tokens and the verification share per replay (`squadops cycles assess --format json`, #1960's scorecard);
- the first `qa.test` attempt's completion tokens;
- the window's own source cycles. A against its source shows how far one replay drifts on the same arm.

**A single loss on B (V2) is a finding on its own,** whatever V1 shows.

**A replay that doesn't reach a verdict** (an infrastructure failure, a cancelled run) is recorded with its reason and run
once more on the same arm. A second failure is recorded, and that increment is read as *not run* on both arms.

## 5. What this does not decide

- **Adoption.** That is the owner's ruling, not before phase 2's decision (D4). Arm B's branch merges only then, and only
  if adopted.
- **The rate of anything.** Four increments per arm can show a direction and a loss, not a rate.
- **A criterion file's thinning over later increments.** Fewer tests now may weaken an increment's successors. One
  replay per increment can't see that.

## 6. If a prediction fails

- **V2:** the record names the loss (the criterion, scenario or rejection, and the tree). It weighs against adoption,
  whatever V1 says.
- **V4:** the arms didn't differ as described. The A/B is void, and it is re-run once the rendering is understood.
- **V1 or V3:** reported as the reading. Nothing changes on main either way.

## 7. What the second reader changed

A fresh agent read the first version and the arm B branch before anything ran.

**Two blocking findings:**
- **The Next.js replays would have run on FastAPI + React.** The replay script dropped the stack (fixed by #2667).
- **Half of arm B never reached the model.** The plan-derived `qa.test` path renders the task fragment, not the
  request template the first version changed. And the system prompt isn't stored with a generation, so the first V4
  would have voided the run.

**Also adopted:**
- arm B kept to one intervention (#2297's rule moved out);
- one pre-registered V1 measure, mechanical, instead of either of two token figures;
- the plan gate's rule fixed;
- V3 read from what ran, not from the failure analyses' prose;
- arm B's faults bounded to the requirements the task states;
- "no further test" made a planning-time answer.
