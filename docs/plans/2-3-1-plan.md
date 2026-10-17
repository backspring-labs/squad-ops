# 2.3.1 plan — what the 2.3 cut found, fixed small

**Status: ADOPTED (2026-10-16).** The owner ruled §5 at ~15:26 ET: "approve D1-D3 for 2.3.1". The scope was ruled
earlier the same day. After the 2.3.0 cut the owner placed five items here: "place the 2.3.1 candidates you listed
after the cut", and "yes" to adding #2381 the same way. D2 adds a sixth, #2384. A seventh, #2394, came out of the
regression pair's first round: the owner ruled at ~19:44 ET the same day, "approve #2394 for 2.3.1, #2395 to 2.4" (D4).
An eighth, #2398, came out of the first shakeout: the owner ruled at 11:42 ET on 2026-10-17, "approve #2398 for
2.3.1" (D5). Round 3's Next.js roll was rejected on #2395, already placed in 2.4: the owner chose on 2026-10-17 to
count the round for the exit rule and run the shakeout (D6). This plan says how each is built, how the line is
verified, and what it leaves out.

**What 2.3.1 is.** A patch on the 2.3 line (CLAUDE.md, #281: urgent or small fixes, either lane). Every item was found
on the 2.3 line, most of them by its cut. None is urgent: each is a defect that is small, understood, and cheaper to fix
now than to carry into 2.4, whose first campaigns start measuring outcomes. The headline line for 2.4 is its own plan's.

**The claim it makes:**

> **What a campaign's records and checks say is what happened:**
> - a late answer reaches the stored digest, and says who gave it;
> - a correct handler for a declared query parameter is not refused;
> - a check that ran and passed is not recorded as skipped;
> - a cycle that failed does not read `accepted`;
> - a Next.js suite that renders a page fails or passes on its own assertions, not on the scaffold's config;
> - an increment's detail page is read whatever the manifest calls it, and a page nothing could reach is recorded as
>   never read, not as one that failed to render.

---

## 1. The eight items

### #2322: the runtime API's unused RabbitMQ connection and channel are removed

- **The defect:** the runtime API opens an AMQP connection and channel at startup and keeps them on `app.state`
  (`src/squadops/api/runtime/main.py:682-683`, slots at `:126-128`). Nothing reads either, except to close the
  connection at shutdown (`:819-820`). Every publish goes through the queue port, which opens its own connection.
- **The fix:** remove both slots and their startup and shutdown code. First confirm that no route or startup sweep
  reads them through `request.app.state` dynamically. A static search finds none.
- **The test:** one that fails when either slot is set at startup. It runs the composition root's startup with the
  queue port faked.

### #2305: a late answer on a closed campaign updates the stored digest, and can be recorded as an agent's

- **The defect, in three parts:**
  - the answer route applies the transition without re-materializing the stored package (`campaigns.py:395`), while
    the close and the abort do (`_materialize_after_close`). So `campaigns digest` keeps asking for an answer that was
    given;
  - `squadops campaigns answer` has no `--as-agent`, where `runs gate` does (#812). A delegate's answer is recorded
    under the owner's user id;
  - the digest line doubles the question's period.
- **The fix:**
  - re-materialize after a late answer, as the close does, when the campaign is closed;
  - add `--as-agent`, recorded as `runs gate` records it;
  - join the answer without the doubled period.
- **The wiring test** enters at the answer route on a closed campaign. It asserts that the **stored** package, not
  only a digest built from the log, shows the answer and no longer asks for it. That gap is why the existing test
  missed the defect.
- **The ledger:** SIP-0109's row for #2305 moves from "unplaced, deliberately" to placed in 2.3.1, in this plan's PR.

### #2378, the smaller fix: the signature check accepts a declared query parameter

- **The defect:** `fill_slot_signature` pins a route's parameters to the scaffold's, which are the path's
  (`src/squadops/cycles/fill_slot_integrity.py:621`). It refuses any difference (`:682-686`).
  - In the cut's first counted roll, the manifest chose a query parameter for the leave endpoint. The developer's
    correct FastAPI handler was refused.
  - The accepted repair read the parameter through a context variable to get around the check.
- **The fix in 2.3.1:** an added parameter that is neither a path nor a body parameter is accepted. A removed or
  renamed scaffold-owned parameter is still refused, so the check keeps what it is for.
- **Not in 2.3.1:** the proper fix, an endpoint that declares its query parameters as a field the scaffold, QA's prompt
  and the probes read. That is 2.4's output-quality work.
- **The test:** three cases.
  - Today's refused handler, `name: str = Query("")` added beside `run_id`, now passes.
  - A renamed path parameter is still refused.
  - A dropped scaffold parameter is still refused.

  It must also hold on the Next.js stack's route handlers, or say why they don't carry the check.

### #2384: a failed cycle does not roll up as `accepted` (D2, ruled in)

- **The defect:** `aggregate_cycle_outcome` (`src/squadops/cycles/verification_integrity.py:875`) keeps a run's
  adverse verdict at cycle scope only when the run left no reconcilable rows (`:946`).
  - The 2.3 cut's set 1 fourth roll (`cyc_ce31b502b82c`) failed on a framework integrity error. Its implementation
    run's own verdict was `blocked_unverified`, from two optional rows that had executed and passed elsewhere.
  - Reconciliation superseded both rows, so the cycle detail read `accepted` beside the cycle's `failed` status.
  - The roll-up has no notion of a run that failed, only of the rows it left.
- **The fix:** a run that failed carries its adverse verdict to cycle scope, unless a later run re-executes its work.
  The "opaque" rule (#388) extends to a failed run, whatever rows it left. First read every caller of
  `resolve_cycle_outcome` (the cycle-detail API, the release package, wrap-up and gates). The rule is right only if
  none of them relies on today's reading of a failed run.
- **The test:** the issue's shape: a failed implementation run whose summary is `blocked_unverified` with only
  optional, elsewhere-executed unverified rows. Its cycle reads `blocked_unverified`. The edge: a failed run whose
  work a later run re-executed and passed still reads `accepted`. The wiring test enters at the cycle-detail route.
- **The release package keeps its warning** (#2385) as the guard against the next disagreement.

### #2394: the Next.js scaffold's vitest config compiles a page's JSX for the runtime it has (D4, ruled in)

- **The defect:** the seeded `vitest.config.ts` (`src/squadops/stacks/stack_nextjs_ts.py`, `_VITEST_CONFIG`) set no
  JSX runtime. `tsconfig.json`'s `"jsx": "preserve"` leaves JSX to `next build`, so vite compiled each page's JSX as
  `React.createElement`, and a Next.js page does not import React.
  - A suite that renders a page failed "React is not defined" inside the page module, where no repair either role may
    make reaches it.
  - The regression pair's first Next.js roll (`cyc_31a49b2cdde6`) ended there after two correction rounds, and a
    qa.test on 1.8.1 did too (`cyc_4d9602ce0a66`).
- **The fix:** `esbuild: { jsx: 'automatic' }` in the seeded config.
- **The test:** in `tests/integration/capabilities/test_scaffold_skeleton_execution.py`, which CI's integration job
  runs with npm. A suite that renders the expanded scaffold's root page goes through `run_build_validation`, the call
  qa.test makes; the suite passes and `next build` accepts the config. The control removes the line, and the same suite
  fails "React is not defined".
- **What it does not fix:** the roll would still have failed. With the config fixed, the plan's page tests see only
  the loading state, because a server render never runs a page's data-loading effect. That is #2395, placed in 2.4.

### #2398: a detail page spelled apart from its API collection is seeded by its parameter (D5, ruled in)

- **The defect:** to read a detail page, the evaluator first creates the resource it shows. `route_seeds`
  (`src/squadops/campaigns/increment_tree.py`) took the page's own spelling as the API collection. The shakeout's
  calibration (`cyc_bda7ed244671`) declared `/run/:run_id` over `POST /runs`, so it looked for `POST /run`, found none,
  and gave the page no seed.
  - The page was never read. The evaluation recorded `route /run/:run_id: not rendered`, the words for a page the
    browser loaded and found wanting, and no log line said why.
  - The calibration fixes the page's spelling for every later increment, so no build in the campaign could pass.
    Increment 1's build and its repair each met all four criteria and were blocked on that route alone.
  - Across every stored manifest, 4 of 598 parameterized routes had no seed, all spelled `/run/...`.
- **The fix:**
  - When the page's spelling names no create at all, the collection is the one the API names for the same
    parameter. `GET /runs/{run_id}` names `/runs` for `:run_id`.
  - When no endpoint carries the parameter, or two collections do, the page stays unseeded and is not guessed. The
    same holds for a spelling that two creates could serve, as before.
  - A page no seed reaches is logged, and recorded as `not read, no seed brings its page into being`, in the
    evaluation and in the boot audit.
  - With the fix, 597 of the 598 stored routes are seeded. The one left is a 1.7.2 roll's `/run/:id` over
    `{run_id}`, a name no endpoint carries.
- **The tests:**
  - The wiring test enters at `generate_task_plan` with the calibration's own manifest, stored as a fixture. The
    evaluation it plans is handed the seed `POST /runs` for `/run/:run_id`.
  - Two cases stay unseeded and named: two collections carry the parameter, or none does.
  - The handler, the evaluation and the audit each record an unseeded page in those words, and a seeded page that went
    unread as `not rendered`.
  - The new tests fail on main's code.

### #2297, a read first: does QA's test author see the leave endpoint's method and path?

- **The defect:** QA's backend test for leaving a run guessed the endpoint's method or path and got 405. That was 2 of
  the 3 TensorFold React cycles after the seed fix, and two Ollama cycles before.
- **The read:**
  - Is the endpoint's method and path in the `qa.test` prompt? The model sees what it edits
    (`docs/PROMPT_AUTHORING_STANDARD.md`).
  - What did each failing test call, against what the manifest declared?
  - Is it the input stated only in prose, as in #2378?
- **The fix ships in 2.3.1 where the read points:**
  - a prompt fragment (`src/squadops/prompts/fragments/`) when the endpoints are missing from what QA is shown;
  - nothing, with the read recorded on the issue, when they are there and the model ignores them. That is a 2.4
    output-quality question.

### #2381, a read first: a skip at patch verification must not replace a pass

- **The defect:** in a backend-only campaign increment, the view-compile checks were bound to QA's task. A developer
  repair's patch verification re-ran them where Node is missing. Their `missing_tooling` skips replaced QA's executed
  passes, and the record read 17 of 20 (`cyc_024e350cc844`; round 2's seed increment shows the same).
- **The read must answer one question first:** can a **required** row, such as `frontend_build`, be superseded the same
  way? If it can, a correct increment would end `blocked_unverified`. That is the outcome that failed the cut's first
  set, by a different path.
- **It ships in 2.3.1 if the fix stays inside patch verification:**
  - either a row the repaired files don't own keeps the task's executed result;
  - or the row is decided where the toolchain exists.

  Either way, with a wiring test at the live repair's entry. **If it needs the ledger's supersession rule changed, it
  moves to 2.4** with the read.

---

## 2. Not in 2.3.1

| item | why not | where |
|---|---|---|
| #2306, a converging repair ended as a plan defect | changes when correction gives up. The issue itself says to read the 12 recent terminations first | 2.4's plan |
| #2153, slot assertions routed by location | the owner ruled it waits for SIP-0110's measurement window (SIP-0104 §13d) | after the window |
| #2253, QA's output budget | raising it changes what a regression roll measures, so it belongs in a line's plan | 2.4's plan |
| #1469, `frontend_build`'s aggregate signature | still blocked on its corpus | re-read at each cut |
| #1756, stored prompts cut at 10,000 characters | an instrument, not a patch | 2.4's plan |
| #2286, TensorFold operator keys | credentials: the owner's to place | the owner |
| #2395, a Next.js plan asking QA for page-state tests the stack's vitest can't run | a design choice: a planning rule that leaves page rendering to the boot audit, or a DOM test environment for the stack. The owner placed it in 2.4 (D4) | 2.4's plan |

---

## 3. Verification

Two of the items change the build's own path: the signature check every developer task runs (#2378), and possibly
QA's prompt (#2297). So unlike 2.2.1, a campaign alone can't show the build unchanged.

| step | what it shows | cost |
|---|---|---|
| each PR's unit and wiring tests, in CI | each fix at the entry point a live cycle uses | in the PR |
| `rebuild_and_deploy.sh all`, then `verify_loaded.py` from the main checkout | the deploy answers with the fixed code: one new loaded check per fix, plus every tracked row | ~15 min |
| **one regression pair, one roll per stack, uncounted** | the build unchanged on both stacks, with the new checks answering in each roll | **~1 h** |
| **one shakeout campaign**: 2.3's cut shakeout, carried | the campaign path unattended on the fixed deploy, and the reads' shapes where an increment reaches them | **~1.25 h** |
| the cut (CLAUDE.md steps 1–8) | the release, its package and its records | ~1 h |

**The exit rule:** the pair and the shakeout on one deploy, with no new seam finding.
- A finding in a changed seam is fixed, rebuilt and re-run.
- A finding elsewhere is filed and placed. It does not hold the patch unless the fixes caused it.

**What this does not cover:**
- **#2305, live:** a late answer needs a closed campaign with a pending escalation, and the shakeout asks nothing. It is
  read in its wiring test only.
- **#2378, live:** the refusal needs a manifest that chooses a query parameter, which one of the 2.3 cut's eight counted
  rolls did (set 1's first). The pair may not reach it.
- **#2384, live:** the defect needs a run that fails on a framework error, which a passing pair does not produce. It is
  read in its wiring test, and in the roll-up of any cycle in the pair or the shakeout that does fail.
- **#2394, live:** only a plan that asks QA to render a page reaches it. One of the 17 Next.js cycles in the 2.3 line's
  verification sets did, so the second pair probably won't. It is read in its integration test.
- **#2398, live:** only a calibration that spells its detail page apart from its API reaches the new path, which 3 of
  598 stored routes did. A fresh shakeout's calibration authors its own manifest, so it may spell the page `/runs/...`,
  and then the path is read in its wiring test only. Every increment evaluation still reads its pages through the
  changed function.

**Round 1, the first pair** on `dep_4da309b688d4` (69ddf158), from 16:33 to 18:08 ET:
- FastAPI + React, `cyc_ee3b645e51bd`: accepted, 21 of 21 criteria verified, one correction round.
- Next.js, `cyc_31a49b2cdde6`: rejected, 17 of 18 criteria verified. The implementation run ended `plan_defect` after
  two correction rounds; the boot audit passed.
- Both answered all 125 loaded checks, the six 2.3.1 rows as expected.
- The reading stopped the line for the owner. Its cause, #2394 under #2395, was reproduced on the run's rebuilt tree.
  The shakeout was not launched. Round 2 is the pair again on the deploy with #2394, then the shakeout.

**Round 2, the second pair** on `dep_aad7eb54eacc` (de7a09a7), from 20:12 to 21:05 ET:
- FastAPI + React, `cyc_12d8a215d46f`: accepted, 20 of 20 criteria verified, no correction round.
- Next.js, `cyc_c0245ee52747`: accepted, 15 of 15 criteria verified, no correction round.
- Both answered all 126 loaded checks, #2394's row among them. The pair held.

**The first shakeout**, `cmp_dadc7c019ad6`, on the same deploy:
- The calibration, `cyc_bda7ed244671`, was accepted, 20 of 20.
- Increment 1, a run capacity (`prop_bfe02fc06b87`), was approved by the delegate at 21:37 ET. Its build
  (`cyc_f479d21e05ac`) and its repair (`cyc_7c01dc033550`) each met all four criteria and read `/` and `/create` as
  held. Each was blocked on `route /run/:run_id: not rendered`.
- The campaign escalated at 22:16 ET under its policy. Its cause was #2398, and the line stopped for the owner.
  Round 3 is the pair again on the deploy with #2398, then a fresh shakeout on the same deploy.

**Round 3, the third pair** on `dep_d35eb75c759b` (7aecfa0b), from 12:18 to 14:43 ET on 2026-10-17. `verify_loaded.py`
answered all 127 loaded checks on the deploy. Each record carries the 124 its squad containers answer, as expected,
the 2.3.1 rows among them; the other three run in the generalist's, the sandbox service's and the console's containers.
- FastAPI + React, `cyc_a627e48d622d`: accepted, 21 of 21 criteria verified, one correction round.
- Next.js, `cyc_bbedc850e6ff`: rejected, 16 of 17 criteria verified, in 114 minutes. The boot audit passed: the app
  installs, builds and boots, answers its 4 contract probes, and each of its 3 declared routes renders its view. The one
  criterion not credited was the QA suite `__tests__/runs_ui.test.ts`, on #2395:
  - one version of the suite declared a DOM environment the stack doesn't seed (`Cannot find package 'jsdom'`), and was
    never collected;
  - another rendered the pages on the server, and 4 of its 14 tests saw only their loading state;
  - each of the two repairs that changed the suite passed patch verification's 34 static rows and was refused at the
    retest, which runs the suite;
  - the round sent to the developer is #1581's unanimity rule abstaining as designed: the lead's labels were
    `["test", "ui"]`, and `ui` carries no suite-side token. The developer said in prose that the file was QA's and
    changed nothing, and the round was refunded;
  - the last `qa.test` emission ran out of its 12,288-token cap, and the lead chose `continue`.
- No new seam finding. The Next.js plan has asked QA for page tests in 2 of the line's 3 rolls, recorded on #2395. The
  line stopped for the owner, who counted the round (D6).

**The second shakeout**, `cmp_dc2abcf0af3a`, on the same deploy, from 15:31 to 16:39 ET:
- The calibration, `cyc_fd8c6216afac`, was accepted. Its manifest spells the detail page as its API does
  (`/runs/:run_id` over `POST /runs`), so #2398's fallback was not reached; every increment evaluation read its pages
  through the changed function.
- Increment 1, a leave button beside each participant (`prop_67f6ecfb2e3f`), was approved by the delegate at 15:59 ET.
  Its build, `cyc_cbf65f6fb670`, met T1–T2 on its first cycle, and every route held.
- Increment 2, the detail view's empty optional fields hidden (`prop_6c331e858068`), was approved at 16:19 ET. Its
  build, `cyc_f6bfb0b88ebd`, met T3–T5 on its first cycle, T1–T2 held, and every route held.
- The campaign closed `success` on its objective (row 3, `objective_met`), with no repair or retry cycle and no
  escalation.

**The exit rule held** on `dep_d35eb75c759b`, in three rounds of the pair and two shakeouts: round 3's pair, counted by
the owner (D6), and the second shakeout, with no new seam finding.

---

## 4. Sequencing

1. #2322, then #2305, then #2378, then #2384. Each is its own PR, merged on green with main's run read.
2. The two reads, #2297 and #2381, recorded on their issues. Then a fix PR for each read that points to one inside
   2.3.1, or a re-placement to 2.4 with the read.
3. The rebuild, the loaded checks, the pair and the shakeout. Then the cut.
4. After the first pair (D4): #2394 in its own PR, the rebuild and the loaded checks, the pair again, then the shakeout.
5. After the first shakeout (D5): #2398 in its own PR, the rebuild and the loaded checks, the pair again, then a fresh
   shakeout.
6. After round 3 (D6): the fresh shakeout on the same deploy, then the cut.

---

## 5. Decisions (ruled 2026-10-16 and 2026-10-17)

| # | decision | recommendation | ruling |
|---|---|---|---|
| D1 | **the verification** | **§3 as written:** tests, a full rebuild with loaded checks, one uncounted pair and one shakeout campaign, about 2.5 hours of box time. *Heavier:* a counted set, two rolls per stack pre-registered as 2.3's was, about 2 more hours. *Leaner:* the shakeout alone, which leaves #2378's change to the build path read only in tests | **approved** |
| D2 | **#2384, a failed cycle rolling up `accepted`** | **in 2.3.1.** It is a correctness defect in the cycle roll-up that every consumer reads: the API, the console and the release package, which had to work around it at the 2.3 cut. The fix is to let a failed run's adverse verdict stand at cycle scope unless a later run re-executes its work. Read the resolver's callers first | **approved** |
| D3 | **who runs the line** | **the supervisor, on the 2.3 line's terms:** build in §4's order, merge on green with main's run read, rebuilds and uncounted runs. Through the cut, including the tag and the records upload once §3's exit rule holds and the release PR merges with main green. If a reading fails, it stops for the owner. Accepting SIPs and anything security-related stay the owner's. The grant ends at the 2.3.1 cut | **approved** |
| D4 | **#2394 and #2395, from the first pair** (§3, round 1) | **#2394 in 2.3.1:** a one-line fix to a scaffold-owned file that no role can repair, with an integration test, then the pair again on the new deploy. **#2395 in 2.4:** it is a design choice between a planning rule and a DOM test environment for the stack. *The alternative:* both in 2.4 and the Next.js roll re-run on the same deploy, which needed a ruling that the finding does not count against the exit rule | **approved**: "approve #2394 for 2.3.1, #2395 to 2.4" |
| D5 | **#2398, from the first shakeout** (§3) | **in 2.3.1:** the evaluation read a page it never visited as "not rendered", which is the claim this patch makes. 2.4's campaigns would hit it whenever a plan spells a page apart from its API. Then rebuild, the pair again and a fresh shakeout, about three hours. *The alternative:* §3's rule that a finding outside a changed seam is filed and placed. #2398 to 2.4 and a fresh shakeout on the same deploy, which needed a ruling that this escalation does not count against the exit rule | **approved**: "approve #2398 for 2.3.1" |
| D6 | **round 3's Next.js rejection** (§3, round 3) | **count it and run the shakeout:** the roll's only failure was #2395, placed in 2.4 by D4, and its boot audit passed; no new seam finding. *The alternatives:* #2395's smaller fix (a planning rule for the stack) in 2.3.1, then the pair again and the shakeout, about 4–5 hours; or hold for the owner's own read | **approved**: the owner chose to count round 3 and run the shakeout |
