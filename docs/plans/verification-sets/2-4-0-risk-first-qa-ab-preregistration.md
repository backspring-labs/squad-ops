# 2.4: risk-first QA instructions, an A/B on replayed increments — pre-registration

**Written** 2026-10-22 by the Spark lane, before either arm launches.
**Approved** by the supervisor under the owner's grant of 2026-10-19.
**The plan's D6** (ruled 2026-10-17): "the A/B in 2.4; adoption a separate ruling, not before phase 2's decision".
**Issue:** #1966. **The design:** #1966, issuecomment-6341627571.
**Uncounted.** It is an experiment, and its arm B never merges unless the owner adopts it.

## 1. The question

`SIP-Verification-Yield` (proposed) §19–§21 and §35–§38 tell QA to work risk-first:
- find the risks and plausible faults a change introduces;
- add the minimum verification that tells each from correct behaviour;
- accept "no additional automated test is justified" as a legal answer beyond what a contract requires.

Does QA, told this, spend less on verification without letting more defects through?

## 2. The arms

They are deploy against deploy, with the same model on both: `full-38-tf`, TensorFold's frozen NVFP4 recipe. Memory is
declared disabled on both, as every measured roll.

- **Arm A:** `dep_787b72fcf866`, from main at `53a78031`, which is #2306's after-arm deploy.
- **Arm B:** a rebuild of `experiment/1966-risk-first` at `e0eacb26`, which is `53a78031` plus one commit.
  - **Its deploy** is recorded on #1966 before its first replay.
  - **What the commit changes,** and nothing else:
    - **QA's identity** (`src/squadops/prompts/fragments/roles/qa/identity.md`). "Create comprehensive test cases" becomes:
      find the risks first, add the minimum verification that tells each plausible fault from correct behaviour, every
      criterion still gets its test, and beyond that "no additional automated test is justified" is a legal answer.
    - **QA's planning prompt** (`request.qa_propose_plan_tasks.md`):
      - plan by fault, not by count. The worked example drops its `min_count: 5`, and its description names faults
        instead of operations;
      - propose no case the declared interface can't express, such as an empty path segment (#2297).
    - **The qa test request** (`request.qa_test.test_validate.md`): a comment line above each test, naming the behaviour
      it protects and the fault it catches.
- **Unchanged on both arms:**
  - SIP-0109 §8.2: each criterion an increment adds still gets one executable test that fails on its baseline;
  - the scaffold's frozen shells, the probes, and every gate;
  - the builder role, which assembles; in SquadOps, QA writes the suites.

## 3. The increments

The 2.4 window's accepted increments, two per stack, each replayed once per arm by
`scripts/dev/replay_increment.py --campaign C --increment N --squad-profile full-38-tf` (#1959). The replay runs each
increment from its own baseline tree, approved change request and frozen criteria, outside its campaign.

| # | stack | campaign | increment | its cycle in the window | change request | what it adds |
|---|---|---|---|---|---|---|
| I1 | FastAPI + React | `cmp_83d63c2ebb50` | 1 | `cyc_f9930df7c925` | `art_64e0d711c5d6` | capacity |
| I2 | FastAPI + React | `cmp_83d63c2ebb50` | 3 | `cyc_b7432a9633a5` | `art_122477b8c1d8` | sorting (its accepted second try) |
| I3 | Next.js | `cmp_ae20bfd95bc3` | 1 | `cyc_e5370cec344f` | `art_600396287697` | capacity |
| I4 | Next.js | `cmp_ae20bfd95bc3` | 2 | `cyc_679608d64edc` | `art_c9d2a17bb8b0` | sorting |

Each resolves in a dry run on the current deploy (2026-10-22).

**The order:** arm A's four replays on `dep_787b72fcf866`, then arm B's rebuild and its four replays. That is eight cycles,
within the plan's 6–10 h guide. One replay at a time, and only on an idle box.

## 4. Predictions

N is 4 per arm. These are mechanism readings, not rates.

| # | prediction | read from | falsified by |
|---|---|---|---|
| V1 | **less verification spend:** arm B's qa tokens, or its verification share, are lower than arm A's on at least 3 of the 4 increments | the per-increment scorecard (#1960), from each replay's records | 2 or more increments where B spends as much or more on both |
| V2 | **no more escapes:** every frozen criterion that discriminates on A still discriminates on B, and no held-out scenario (suite revision 5, `92a26ad0…`) fails on an accepted B tree that passes on that increment's accepted A tree | each replay's increment evaluation; `scripts/dev/read_scenarios.py` on each accepted tree | any criterion or scenario lost on B |
| V3 | **no more rounds from QA's own tests:** correction rounds whose failure analysis places the defect in the qa suite (`work_product` on a test file) are no more on B than on A | each round's `failure_analysis.md` | more such rounds on B |
| V4 | **the change is what ran:** B's rendered `qa.test` and `qa.propose_plan_tasks` requests carry the risk-first text, and A's don't | the generations' full requests (#1756, `scripts/dev/read_full_prompt.py`) | either arm rendering the other's text |

- **A single escape on B (V2) is a finding on its own,** whatever V1 shows.
- **A replay that doesn't reach a verdict** (an infrastructure failure, a cancelled run) is recorded with its reason and
  run once more on the same arm. A second failure is recorded, and that increment is read as *not run* on both arms.

## 5. What this does not decide

- **Adoption.** That is the owner's ruling, not before phase 2's decision (D4). Arm B's branch merges only then, and only
  if adopted.
- **The rate of anything.** Four increments per arm can show a direction and an escape, not a rate.
- **The planned cases.** #2297's specific defect, a planned case the interface can't express, is a prediction of its own
  only if an increment's plan proposes such a case. These four may not.

## 6. If a prediction fails

- **V2:** the experiment's record names the escape: the criterion or scenario, and the tree. It weighs against adoption,
  whatever V1 says.
- **V4:** the arms didn't differ as described. The A/B is void, and it is re-run once the rendering is understood.
- **V1 or V3:** reported as the reading. Nothing changes on main either way.
