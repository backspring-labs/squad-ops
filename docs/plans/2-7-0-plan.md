# 2.7.0 plan: the 2.6 line's debts, closed

**Status: DRAFT, revision 4, with the owner's rulings (2026-11-08).** The owner asked for a 2.7 plan that closes as
many of the 44 open issues as it can, while keeping 2.7 free of new features. The owner ruled R1–R9 on 2026-11-08 at
about 08:30 ET, with a second round of review (§6). The plan is adopted when this PR merges. Until then nothing is
built, and the merge grant (R9) covers only the adopted scope.

## Revision log

- **Revision 1** (2026-11-08): the first triage. 22 committed; expected 27, ceiling 31.
- **Revision 2:** each claim checked against the code, the ledgers and the issues.
  - Moved out: #2781 (a design change) and #2782 (it moves the evaluator tag).
  - Narrowed: #2286 (half shipped in `e4a3d20d`) and #2931.
  - Recast: #2938's and #2421's remainders.
  - Added rulings: R6 (the soak's repository) and R7 (the operator-name guard).
- **Revision 3:** §5a, the four open design pull requests, and the ruling on #2872.
- **Revision 4:** the two review rounds and the owner's rulings.
  - **The soak is a release gate,** not an expected slip (§1, §4.4). The scripted squad is built first, and the final
    soak runs last.
  - **Track E is a fixture-and-evidence table** (§4.5). BT-11's records give the promotion and the review-request push.
    They can't give IR-5, IR-6 or IR-9, so one counted increment runs on `z_continuum`.
  - **Contracts written out:**
    - D1's ending, and how it relates to §24dh;
    - the vault's write order and how corruption fails;
    - #2932's dispatch identity at `reply_router`;
    - #2783's accepted-page inventory;
    - the shakeout, by the existing per-stack rule.
  - **Corrected:**
    - #2935's gap 1 shipped (§24di);
    - the evaluator is on `-8`, not `-7`;
    - #2760 can't close on a generic soak;
    - #2402 and #2765 regain their omitted acceptance conditions.
  - **Recounted** (§1): defects, evidence and administrative closures are reported separately, and new work items
    apart from the 44.

## What 2.7 is

An odd minor, so a stabilization release, feature-free by rule (CLAUDE.md, #281). Every committed item is one of these:
- a defect in shipped behaviour;
- debt;
- the verification the 2.6.0 cut moved here: the overnight soak, and an accepted product increment read end to end.

One exception is named, by the owner's ruling (R2): #2862, a merged contribution syncs its Project. It corrects
stale Project state through the seam that exists today (§2, Track E).

**The claim it makes:**

> **On a Campaign, a verdict says what happened, and the box survives what happens to it:**
> - a criterion whose test passes before the change is refused to qa, and SquadOps never reads a pass on the head as
>   the behaviour already existing;
> - on the qa path, a page reads as rendered only when an element rendered it: not text in a script, nor content
>   inside a `<template>` or a `<noscript>`. Visibility a stylesheet computes is still unjudged (R5);
> - a page criterion on a vitest product can fail as an assertion;
> - a power loss, a reboot or a redelivered task leaves a run that recovers, or fails saying why;
> - a scripted Campaign runs at least eight increments over at least nine hours through a restart, token expiry past
>   the session's maximum lifetime, an upstream push and a pause, with no model in the loop (§4.4);
> - an accepted product increment is read end to end on a repository-backed Project, and a merged contribution
>   reaches the Project it came from.

**If the soak is deferred,** the fifth line comes out of the claim and the cut conditions, by an explicit narrowing
recorded in the cut record. A soak that stops early for a named, safe reason can validate that stop's prediction. It
can't stand in for eight increments overnight.

## 1. The count

**Where the 44 go:**

| Kind | Issues | Count |
|---|---|---|
| Defects fixed | Track A: #2933, #2935, #2949, #2839, #2799, #2783, #2776, #2775. Track B: #2931, #2932, #2765, #2798, #2286. Track E: #2862 | 14 |
| Debt fixed | Track C: #2402, #2736, #2737 | 3 |
| Verification built and evidence completed | Track D: #2495, #2892. Track E: #2827 | 3 |
| **Committed** | | **20** |
| Stretch | #2826 | 1 |
| Administrative closures, on conditions (§3) | #2944, #2893, #2230, #949, #2938 | 5 |
| Open, awaiting the operator (§2, Track D) | #2760 | 1 |
| Out of 2.7 (§5) | | 17 |
| **Total open on 2026-11-08** | | **44** |

**Expected closures, by scenario:**

| Scenario | Defects and debt | Verification and evidence | Administrative | Total |
|---|---|---|---|---|
| **The plan as adopted:** every committed item, every administrative closure | 17 | 3 | 5 | **25** |
| plus the stretch item (#2826) | 18 | 3 | 5 | 26 |
| plus #2760 transferred to the operator's own tracking (an administrative closure, never "verified") | 17 | 3 | 6 | 26 |
| The soak deferred, with the claim narrowed: the scripted squad ships, the soak doesn't | 17 | 2 | 5 | 24 |
| The soak deferred, and the scripted squad with it | 17 | 1 | 5 | 23 |

The headline is **25 issues closed, of which 20 are work and 5 are administrative.** The administrative closures are
reported apart, so they can't stand in for the release claim.

**New work items, not among the 44.** Each is filed at adoption with the acceptance conditions below:

| Item | Track | Acceptance |
|---|---|---|
| **A filtered-listing index for the artifact store.** The adapter already keeps an artifact-id index (`filesystem_artifact_vault.py:46-60`). A listing by project, cycle, run or type still walks every `metadata.json` under its directory (`:269`), which is what made Home slow (#2921). | B, after #2931 | A listing reads the index, not the tree. The index is rebuilt from the tree when it's missing or behind. A listing's results match the walk's on a fixture vault, in the same order. Its time on the box is recorded before and after |
| **An explanation on the console's Memory view when a Project has no records.** | B, anywhere | An empty table says what makes a record: an instruction (`--instruction`) or a chat note. It says that approved lessons are a separate surface. It names the Project. A view with records is unchanged |
| **The operator-name guard, renamed and generalized (R7).** | C, after its design is reviewed | §6, R7 |

## 2. The tracks

### Track A: a verdict says what happened (8)

| # | Defect | The fix, and what closes it |
|---|---|---|
| #2933 | **D1.** A criterion test that passes on the head on qa's first emission ends the item at row 19, and the next proposal is told the behaviour is met | **The rule:** a pass on the head says the test proved nothing about the work, never that the behaviour exists. It extends §24dh, which already refuses a *repaired* test that passes on the head, to qa's first emission.<ul><li>**The refusal:** a first emission whose criterion test passes on the head is refused to `qa.test_repair`, spending one repair round, as §24dh's refusal is. The head check runs after the emission is accepted (`dispatched_flow_executor.py:2356`), and nothing fails a succeeded task today, so the succeeded result becomes a failure before acceptance.</li><li>**When the allowance is spent:** §24dh's backstop applies. A later emission that still passes on the head fails the run with no terminal kind, so the Campaign reads an ordinary failure, repairs it, and **counts it.** It's never `criteria_not_checkable`.</li><li>**Nothing tells the next proposal "already met":** neither path writes `criterion_head_check`, the record `_already_met_stated` reads.</li></ul>A SIP-0109 amendment beside §24dh. **The wiring test** enters at the executor's qa dispatch with a first emission whose test passes on the head, and asserts that a `qa.test_repair` is dispatched. After the allowance it asserts that the Campaign reads an ordinary counted failure, and that the next proposal's input carries no "already met" text for that criterion. Seam table in the PR |
| #2935 | One criterion passing on the head ended the increment, though another failed there | **Gap 1 shipped:** the proposal brief keeps what the product already does inside the criterion that changes it (`request.strategy_propose_product_increment.md:56`, with the CSV and no-output example; SIP-0109 §24di). Every new criterion must still discriminate. **The remainder is R3, as ruled:** an item that ends at row 19 gets one automatic re-proposal, shown the abandonment's reason. The allowance is derived from the control log, so a restart, a reorder or an unrelated goal revision can't reset it. A second row-19 ending leaves the item abandoned. The rules for choosing the next eligible item are unchanged. A SIP-0115 §5.3 amendment. The wiring test enters at the Campaign's next-proposal step after a row-19 ending, and again after a restart |
| #2949 | A suite handed to the product's runner reads as failed with exit -1 before the runner passes it | **As built (the #2949 PR):** a new stored value, `handed_off`, written only when the runner's pass of a hand-off is accepted, since the router now reads the runner before the bank. Every reader of the marker reads it through one vocabulary (`EmissionStatus`, `banked_as`), so no `==` check is passed by it; the Prefect task run, the activity and `task.failed` are #3000. **As planned:** keep `failed` as the stored marker, since the vault is write-once and the bytes really are the image's unrun attempt. Name the hand-off where it's read, with the runner's verdict beside it. First, a table of every reader of `failed` (at least seven: `source_delivery.py:130`, `source_checkout.py:197`, `delivered_tree.py:66`, `deletions.py:53`, `cycle_assessment.py:368`, `dispatched_flow_executor.py:1854` and `:1953`). The wiring test enters at the qa dispatch with a result left to the product's runner, and a runner that passes |
| #2839 | A dev repair rewrote product code to drop a declared dependency the qa image lacked, and the increment was accepted | Verify first. The incident (2026-10-31) predates #2818: a suite the qa image fails is now judged on the product's runner (`judge_on_product_runner`, `dispatched_flow_executor.py:4810`), where the declared dependency is installed. If a replay of the incident's inputs shows no repair is dispatched, close on that replay. Otherwise a repair that removes an import of a declared dependency is refused, with a wiring test on that case |
| #2799 | On a vitest product, a page criterion for an added page fails at setup on the accepted tree, so it can't discriminate | The issue's option 1: a framework-placed loader resolves the view by path at run time and renders a not-found marker where it's missing, so the baseline fails at the anchor's assertion, as #2749 does for Next.js. Option 2 depends on the model following an idiom. The seam table covers emission, the qa repair, the verifier, the evaluator's accepted and candidate sides, and a later increment's frozen criterion |
| #2783 | A change request can reuse the anchor of a page an earlier increment added, and the new page can read held though it was never built | **The full scope, as the issue states it:**<ul><li>**One authoritative accepted-page inventory:** the pages accepted increments added, with their anchors, written at acceptance and keyed by the accepted tree's identity.</li><li>**It reaches three places:** the proposal's input, as the frozen criteria do (§24ap); the rails' uniqueness check, beside `anchor_conflicts` (`campaigns/change_request.py:1146`); and the renderer's expected route set.</li><li>**A product with no approved manifest** is covered by the same inventory.</li><li>**Review:** it changes what a proposal is shown, so it takes SIP-0112 H.12's outside review before it merges.</li></ul>**The acceptance case:** a new page that was never built, on an app whose single-page fallback renders an earlier page carrying the reused anchor, is refused |
| #2776 | The qa role's route rendering counts a `data-testid` in a script's text, a `<template>` or a `<noscript>` as rendered | The qa path reads `_TESTID.findall(dom)` (`route_rendering.py:53`, `:182`). It uses `view_anchors` instead, which the product path has used since #2777. Each of the three cases is a test, and so is a visible element |
| #2775 | A vitest config that imports or computes its settings can set reporters the derivation never reads | Where `_vitest_unread` (`projects/profile_derivation.py:255`) can't read the effective config from the file's own text (a relative import, `mergeConfig` with an imported base, a spread, a function call), the runner gets no reader, and `no_test_id_reader` says why |

### Track B: a run survives what happens to the box (5)

| # | Defect | The fix, and what closes it |
|---|---|---|
| #2931 | A power loss left empty artifact metadata, and one empty file stranded a re-attached run | **The write order** (the crash-consistency contract), for `store()`:<ol><li>The content goes to a temp file in the artifact's directory, is fsynced and renamed into place. The directory is fsynced.</li><li>The metadata, carrying the content's `content_hash` and `size_bytes`, is written the same way. **The metadata's rename is the commit point:** an artifact exists when its metadata is readable and its content matches it.</li><li>The artifact-id index is updated the same way.</li><li>`store()` returns, and only then can a caller's checkpoint in Postgres reference the artifact.</li></ol>Baselines (`.baselines.json`, `:311`) and the index get the same writer. Today content is a bare `write_bytes` (`:110`), the baselines a `write_text`, and nothing is fsynced.<br>**Detection:** an unreadable metadata file, or one whose content is missing or doesn't match its size, is a corrupt record. Content with no metadata is no artifact.<br>**Containment, two cases:**<ul><li>**A listing** skips a corrupt record and names it in a structured warning (`artifact_record_unreadable`), so a listing for an unrelated run survives. The listing routes return a bare list, and a skipped count in the response would change its shape or add a header convention, so the count is the integrity pass's (`scripts/dev/vault_integrity.py`, revised in #2931's PR). The original outage was the opposite: one bad file failed a different run's listing (`_load_metadata`, `:283`).</li><li>**A read that needs a specific artifact** (a checkpoint's restore, an evaluation's input, a retrieve by id) gets a typed error naming it. The run then fails, or escalates, with the artifact named. It never stays `running` with no owner, which is what a raising re-attach does today.</li></ul>That needs a line in SIP-0109 §12a. No quarantine mechanism is built.<br>**At the cut:** an integrity pass over the line's records counts corrupt records, and the cut record names each one. Tests cover a crash between each pair of steps, and a listing beside a corrupt record |
| #2932 | A stale failed reply waiting in the reply queue can be taken by a resumed run (ask 2; ask 1 shipped in 2.6.1) | **Today** `reply_router._handle_reply` pops the waiter by `task_id` before it reads the result (`reply_router.py:117`), and a resume re-dispatches the same `task_id`.<br>**The fix:**<ul><li>Logical task ids stay stable.</li><li>Each dispatch, including a retry or a resume, gets a fresh dispatch identity. The waiter is registered under it, the envelope carries it, and the agent echoes it in its reply, through the reply contract.</li><li>The router matches the logical task **and** the current dispatch identity before it removes or resolves the waiter. A stale reply, including a failure that arrives first, is dropped and counted, and the current waiter stays for the current reply.</li><li>A reply with no identity is stale under the new contract: agents and the runtime API are rebuilt together, so only a reply in flight at the upgrade lacks one, and its dispatch times out and is re-sent.</li></ul>The identity lives in memory with its waiter. A resume makes a new dispatch and so a new identity, so freshness needs no durable store.<br>**The test** enters at `reply_router`: a stale failure, then the current success, for one logical task, and the waiter resolves with the success |
| #2765 | A scenario diagnostic's evaluation is stored as the real cycle's | <ul><li>`read_scenarios.py --fault` (`:136`) never stores a diagnostic's evaluation as the cycle's latest.</li><li>`remeasure_quality.py --record` records against the latest evaluation **of the tree it measured**, and prints its readings before it writes, so a refused write can't lose a measurement.</li><li>The stored diagnostic rows (9 on `cyc_840e72247f38` from 2026-10-24, and the Next.js cycle's) are named and marked.</li></ul> |
| #2798 | A start that never became ready doesn't say what its readiness URL last answered | `_answers` (`adapters/sandbox/scenario_runner.py:828`) reduces each poll to a bool. The last status, or the connection error, goes in the failure detail. Tested with a URL that answers 403 on every poll |
| #2286 | TensorFold's key file was read as one key | **Shipped in `e4a3d20d`** (2026-10-24): readers take the `squadops` line by its label, and rotation rewrites only that line. **Remaining:** `docs/ops/credential_rotation.md` says how an operator key is added, rotated and removed by hand, with the restart through `engine_switch.py` when the box is idle, and that the launch gate reads a request on that key as busy, as intended. The issue's managed `SQUADOPS_TENSORFOLD_OPERATOR_KEYS` is dropped as unneeded, and the closing comment says so |

### Track C: debt (3)

| # | Debt | What closes it |
|---|---|---|
| #2402 | Shared scripts fail on macOS's bash 3.2 | **The issue's done-when, in full:**<ul><li>`run_prose_lane.sh` **runs** under stock macOS's `/bin/bash` 3.2, on the MacBook. Parsing under bash 3.2 can't catch a missing `mapfile` or BSD `sed`, so this is an execution.</li><li>The portability rule is in CLAUDE.md's Structure list: bash 3.2 is the floor, use only flags BSD and GNU share, and a newer tool is a declared requirement.</li><li>The architecture guard scans `scripts/**/*.sh`. It has a case it refuses (`mapfile` in an undeclared script) and one it accepts (the same construct in a script that declares `local-spark`).</li><li>`ollama_setup.sh`'s `stat -c` declares its platform or uses a portable form.</li><li>The bare `sed -i` in `docker_setup.sh` and `langfuse_setup.sh:196-212` is portable.</li></ul>The issue's second comment lists 35 unit tests that assume Linux. They're named in a follow-up issue, filed at adoption and not placed |
| #2736 | The embeddings port and its adapter have no caller | Removed, the issue's recommendation 2. SIP-0110 §A.3.10's semantic index designs its own port when it's placed |
| #2737 | The integration guides name tests that don't exist, and `docs/diagrams/` shows a retired memory design | `tests/integration/README.md` and `EXECUTION_GUIDE.md` name only tests that exist, with the commands that run them. The diagrams are redrawn against `docs/architecture/overview.md`, or removed |

### Track D: the overnight soak (2, and one left open)

| # | What | What closes it |
|---|---|---|
| #2495 | A scripted squad: a `machinery` squad profile whose every task is answered from a recorded script | **Built first** (§4.1), since it's the line's largest piece of new code. It's test infrastructure, not a product feature.<ul><li>**One seam:** the scripted provider sits behind the existing LLM port, so dispatch, emission, correction and acceptance run their normal paths.</li><li>**No fallback:** a missing script entry fails the task visibly, naming the entry. It never falls back to a model.</li><li>**Labelled evidence:** each run records the script's version, and a scripted run's records say so, so scripted evidence is never read as model evidence.</li><li>**Scripts are data,** recorded from real runs' emissions where one exists.</li></ul> |
| #2892 | A scripted soak: at least eight increments with a deploy restart, a token expiry, an upstream push and a pause | **A release gate** (§1). Run last, on the pinned deploy, on `z_shelfnote` (R6), to the pre-registration contract in §4.4. At adoption, the issue's repository condition is amended to `z_shelfnote`, citing R6 |
| #2760 | Whether the auth picture holds for an operator supervising an overnight Campaign | **Not closed by the soak.** The soak reads three expiries with the intended supervision identity, `squadops-supervisor` (role `campaign-supervisor`):<ul><li>the access token's 600 s lifetime;</li><li>the refresh token's 1,800 s idle limit, crossed during the pause;</li><li>the session's 28,800 s maximum lifetime, crossed by a soak of more than nine hours.</li></ul>Those readings are posted on the issue. Its four questions (the operator's identity, machine and token cache; the failures it has seen; what an unattended run needs; and corrections) stay open for the operator. The owner may instead transfer them to the operator's own tracking, closing the issue as administrative, never as verified |

### Track E: a product increment end to end, and the Project reads what merged (2)

| # | What | What closes it |
|---|---|---|
| #2827 | SIP-0112 H.4's remainder and H.13's two unbuilt items | **The issue's done-when, unchanged:** a product increment accepted and promoted live, with IR-5, IR-6's increment half and IR-9's increment reading read. And H.13's two items (`nextjs_ts`'s collected-test vocabulary; a plan-less product cycle's test author shown the product) built, or dropped by a numbered amendment. The evidence plan is §4.5's table. Then SIP-0109's and SIP-0112's rows for #2827 are marked shipped |
| #2862 | After a contribution merges, the Project's `integrated_upstream_commit` stays put until someone syncs by hand | **The owner's exception (R2), at the existing seam:** the sync that `POST /api/v1/projects/{id}/syncs` runs today now runs when the next Campaign's draft waits on a pending contribution: `POST /api/v1/projects/{id}/integration-check` (R2's second ruling, SIP-0112 H.30).<ul><li>It uses the request's token, else the one the deploy holds for the Project, and only reads the forge.</li><li>The sync re-validates, so new cycles wait for configure and baseline capture, as after any sync.</li><li>A sync that can't reconcile reads `unreconciled` on the Project, and is never retried in silence.</li><li>The contribution is marked taken against the integrated commit.</li></ul>**What stays the same:** the sync route, its result, the Project record's fields and the console. The one new surface is the check's route and its CLI command, `projects check-integration` |

### Stretch

- **#2826:** a stack convention that pins a collection endpoint's response to a bare list. It changes what a roll
  builds, so it needs the line's pre-registration for an output-quality change, with rolls before and after. In only
  if the committed tracks leave room.

## 3. Administrative closures, each on its condition (5)

| # | Closed when | The record that keeps it |
|---|---|---|
| #2944 | Now: shipped in 2.6.0 (PR #2945, SIP-0109 §24dk). Its remainder, the squad choosing its own next item, was ruled on 2026-11-07: backlog goals are written for the squad, so SIP-0115 §5.3 stands | PR #2945 and §24dk |
| #2893 | Now. Its done-when (validated READY, a baseline with `contract_tests` PASS, the vitest runner and package surface derived) was met before the 2.6.0 cut, which ran on `prj-battle-trainer` | `docs/plans/verification-sets/2-6-0-cut-record.md` |
| #2230 | Now: deferred to 3.x on 2026-10-30 (R4). A row deferred to a later major line needs no open issue until that line's first plan | SIP-0111's ledger row, linked in the closing comment |
| #949 | Once `sips/PORTFOLIO.md` states its remaining work (a revision restart boundary derived from the reviewer's note, not `REVISION_RESTART_TASK_TYPE`) and its pickup condition (after Outcome Evaluation, with a SIP) | The portfolio's theme 9 row, edited in the adoption PR |
| #2938 | Once a numbered SIP-0109 amendment drops the replay-viewer row from SquadOps's scope, and the closing comment links the product's own record of the viewer work (battle-trainer PR #3) | The amendment and the linked product record |

**Kept open by R4:** #1469, deferred and blocked. Its parser is unbuilt, and its latest comment proposes a corpus made
by the real bundler; low incidence isn't a fix. And #557, which tracks its proposed SIP through acceptance and
implementation, as its 2026-08-07 comment commits.

## 4. How the line is built and verified

### 4.1 Order

1. **Early, in parallel:** Track B's small items (#2798, #2765, #2286), and **#2495, the scripted squad**, started first
   because it's the largest risk. Its first scripted machinery cycle runs before Track A finishes.
2. #2931 and #2932, then the filtered-listing index.
3. D1 (#2933) and #2949, which share the qa path and the readers of `failed`, so one seam table serves both. Then
   #2935's R3.
4. The rest of Track A, and #2862. #2783 waits for its outside review.
5. Track C, and the Memory view's empty state, anywhere.
6. **The final deploy:** shakeout pairs until one passes (§4.3), then the deploy is pinned.
7. On the pinned deploy: Track E's counted increment (§4.5), then **the soak, last** (§4.4).

### 4.2 Rules for every item

- **Each issue is its own PR,** with `Closes #N` or `Refs #N — remaining: …`, merged under R9's grant.
- **Each changed seam has a wiring test** that enters at the caller the live cycle uses (TEST_QUALITY_STANDARD 6a). Each
  typed-check change has the seam table (CLAUDE.md, typed checks). D1, #2949, #2799 and #2783 need both.
- **Each SIP change is a numbered amendment in the PR that diverges:**
  - D1: SIP-0109, beside §24dh;
  - #2931's failed re-attach: SIP-0109 §12a;
  - R3: SIP-0115 §5.3;
  - #2938's scope: SIP-0109;
  - #2827: the SIP-0109 and SIP-0112 ledgers.
- **No deploy while a Campaign is running,** with one exception: the soak's controlled restart (§4.4).

### 4.3 The shakeout, by the existing procedure

`docs/plans/verification-sets/README.md`, "The shakeout loop and its exit rule", applies as written. Its
definitions are used, not new ones:
- **A pair** is one shakeout per stack on one deploy: `group_run` on FastAPI + React and on Next.js + TS.
- **The exit:** a pair on one deploy with no new seam finding.
- **A finding** is a defect in a seam the line touched, or a prediction's readout that can't see its own miss. A defect
  in the application a cycle built is the cycle's, and doesn't reset the loop.
- **A fix supersedes the deploy:** it merges, the deploy is rebuilt from main, and both stacks run again. So does any
  code change merged after a passing pair. A prose-only change doesn't (`classify_ci_diff.sh`).
- **The budget:** three pairs. The supervisor records each pair, its findings and its pins in the cut record, with how
  many pairs it took. A fourth pair needs the owner's word.

### 4.4 The soak's pre-registration contract

Written as the line's soak pre-registration in `docs/plans/verification-sets/`, and committed before launch. It names:
- **The fixture:**
  - `backspring-labs/z_shelfnote` at a named base commit;
  - the Campaign's backlog;
  - the scripts and their version, for at least eight accepted increments.
- **The duration:** at least nine hours elapsed. Scripted answers replay each recorded answer's latency, so the
  increments take real time. The backlog holds enough items to cover the time, and the run ends at whichever comes later:
  eight accepted increments, or nine hours.
- **Each injection:** the task or gate it lands on, and its expected recovery or refusal.

  | Injection | Lands at | Expected |
  |---|---|---|
  | **Controlled restart** of the runtime API and agents, on the pinned code and images | a dispatched task in flight | The run re-attaches and resumes from its checkpoint. A stale reply is dropped (#2932) |
  | **Access-token expiry** (600 s) | throughout | silent refresh |
  | **Refresh-token idle expiry** (1,800 s) | during the pause | a re-login with no prompt, and the next ruling succeeds |
  | **Maximum session lifetime** (28,800 s) | past eight hours | a re-login with no prompt |
  | **Upstream push:** a pre-registered commit to `z_shelfnote`'s `main`, outside the Campaign's allowed scope, by the supervisor's GitHub identity, which needs write access to that repository | an open increment gate | The next increment reconciles onto the new base, or is refused as diverged, by the existing reconcile rules. Which one is predicted in advance |
  | **Pause and resume** by the supervisor, held longer than the refresh idle limit | an increment gate | The Campaign resumes where it paused |

- **What's recorded:** every event, every failure, and every injection that didn't land where it was meant to, as *not
  exercised*.
- **The controlled restart** is the one deploy action allowed during a Campaign. It restarts the pinned code and images,
  and changes nothing.
- **A behavioural fix found by the soak** supersedes the deploy (§4.3), and the soak runs again on the new pin.

### 4.5 Track E's fixture-and-evidence table

| Requirement (SIP-0112 §8.4, the integration regression scenarios) | Its precondition | Source | Status |
|---|---|---|---|
| Promotion onto the campaign branch, and the review-request push (SIP-0109 §24ci (b)), live | an accepted increment on a repository-backed Project | **BT-11:** `cmp_6963834274e0`, `cyc_2efc17faf3e5`, contribution `9de088f165e4`, battle-trainer PR #11, now integrated. Immutable records on deploy `dep_2b6c8b9da0ca` (`faed0f6f`) | **Historical evidence holds.** Since `faed0f6f` the path changed only by #2955 (wording) and #2953 (what qa is shown). It's read again on the new increment below |
| **IR-5:** sandbox revision, Git commit, the Campaign's accepted tree and the Outcome Evaluation result resolve to one another | an accepted increment **with an Outcome Evaluation result** | Not BT-11: battle-trainer has no `scenario_evaluations` row. Not `z_continuum`'s earlier records either: its two contributions (2026-10-21) came from plain cycles, and its four evaluations are Campaign-level with no accepted increment | **A new counted increment** on `prj-z-continuum` |
| **IR-6's increment half:** an external Project with its own layout and no SquadOps interface manifest runs through Outcome Evaluation, started by contract 7's commands | own layout; no interface manifest; a declared start | `prj-z-continuum`: its own layout, `stack: null`, and a declared start (`.venv/bin/continuum run`, Development Configuration revision 7). battle-trainer declares no start (`no_start_declaration`) | the same new increment |
| **IR-9's increment reading:** an inherited failing native check stays `FAIL`, `inherited`, independently of Outcome Evaluation | a check that genuinely fails on the inherited baseline | `prj-z-continuum`'s `lint`, FAIL in all 7 inherited baselines. battle-trainer's only check, `contract_tests`, passes | the same new increment |

**The new increment:**
- **The goal:** written by the supervisor for `z_continuum`, a SquadOps sample product, never for battle-trainer.
- **Where and when:** it runs on the pinned deploy, so its readings are the final deploy's.
- **Readings repeated on a deploy change:** a deploy superseded after it means each reading whose path the change touched
  is read again, and the cut record names which.
- **#2799 doesn't block it:** `z_continuum`'s page surface is not applicable.

### 4.6 The cut

- **The cut's evidence:**
  - the passing shakeout pair (§4.3);
  - the soak's record (§4.4);
  - Track E's readings (§4.5);
  - each fix's live check on the pinned deploy;
  - the vault integrity pass (#2931).
- **The SIP sweep, expected:** none promotes.
  - SIP-0112 stays open, with #2709 in 2.8 (R1).
  - SIP-0115 closes on an operator's reading of three accepted items in one Campaign, which is the operator's work.
  - SIP-0109 keeps open rows (#2287, #2781).
- **What the cut won't claim:** that a model plays a product better. A sealed play claim on battle-trainer is the
  operator's to make, with the operator's goals.

### 4.7 The adoption PR

It lands after this plan merges, and before any build. It:
- re-places the ledger rows R1 moves to 2.8;
- edits `sips/PORTFOLIO.md` for #949;
- adds the ROADMAP's 2.7 row;
- files the three new work items and #2402's follow-up;
- amends #2892's repository condition (R6);
- posts the plan's reading on #2760 and #2827.

## 5. Out of 2.7 (17)

**Moved to 2.8 by R1 and R2:**
- **#2287:** an operator lease outside Campaigns (SIP-0109 §9.3).
- **#2421:** the remainder of SIP-0102's X-3b, resolving an owner-approved evaluation secret at start. The declared
  commands shipped as X-3a.
- **#2709:** SIP-0112 E.4.5, update history, archive and restore, and concurrency and conflict recovery. **The
  authorization, idempotency and conflict protections already required of existing operations are kept.** Concurrency
  hardening comes into 2.7 only if a concrete defect is found, with a fix that can be verified on its own. SIP-0112
  stays open.
- **#950:** the review packet at the plan gate (SIP-0093).
- **#2781:** a change request that adds a page whose route has a parameter. It's a design change to §7.2 that needs an
  outside review. Until then the refusal stands, as designed.
- **#2954:** an operator's assessment shown in the digest and the next proposal. It changes what a proposal receives,
  and the adopted 2.6.1 plan classed it as a feature (R2).

**Deferred by R5:**
- **#2782:** a route anchor hidden by a stylesheet. Reading visibility from the live DOM changes `driver.mjs`, so the
  evaluator image's tag moves from `-8`, the tag in use. It waits for the next evaluator cut that is explicitly placed,
  with a window re-read. A new tag starts a new series, so the readings can't be read as one series; archived evidence
  stays valid. Meanwhile the claim says stylesheet-computed visibility is unjudged.

**Kept open by R4:**
- **#1469** (deferred, blocked on its corpus) and **#557** (tracking its SIP).

**New capabilities, already unplaced or for a feature line:**
- **#1978:** the test-first red gate. It changes verdicts and needs calibration.
- **#2173:** the memory entry points epic.
- **#2834:** console surfaces for the CLI. The read-only Campaigns view shipped in 2.6.0. The Campaigns write commands
  and the projects and scenarios groups remain.
- **#2847:** Project environments.
- **#2906:** a Luau runner kind. The owner deferred it on 2026-11-05.

**Not SquadOps build work on this line:**
- **#1039:** the docs site's design pass. It rides along whenever the docs are next touched.
- **#1965:** Verification Yield, ruled the operator's first optimization experiment (2026-10-04).
- **#2723:** held-out suite revision 7. A revision needs its own independent review and validation rolls, and no 2.7
  claim reads the held-out suite.

## 5a. Open design pull requests (not counted in the 44)

Revised at adoption (2026-11-08): #2841's rulings, and #2972 added.

**Merging a proposed SIP or a draft plan isn't a feature, so 2.7 can carry their reviews.** Each merges only as a
proposal: unnumbered for a SIP, still a draft for a plan. Accepting and building it are separate decisions, for a
feature line (R8).

| PR | What | State on 2026-11-08 | In 2.7 |
|---|---|---|---|
| #2872 | Battle Training Squad Harness, the owner's draft SIP | Conflicts with main. Its intake predates 2.6. 46 added lines name the operator | Edited into a framework-only proposal (R8), rebased, intake repeated, merged as proposed |
| #2405 | Game Development Platform, a proposed SIP at revision 2 | Q37–Q39 ruled on 2026-10-31 under the owner's delegation | Review continues, and it merges as proposed |
| #2841 | Game Capability Packs and Squad Composition, stacked on #2405 | Mergeable. Q45 (the foundation, F1, may precede 3.x by an amendment to Capability-Backed Agents) and Q46 (Switchboard as the loader) were ruled on 2026-10-31 | Merges as proposed after #2405. **The open question** is whether these SIPs' revision 3 replaces the foundation Q45 and Q46 selected, as #2972 §8 proposes (F1 shrinks to an in-tree seam; the loader deferred, not reversed) |
| #2972 | The game-dev-roblox plan, revision 2: the MacBook lane's input to 2.8 (a Roblox specialty, QA playing frozen scenarios in Roblox Studio through a worker on the MacBook) | Open for the owner's review, added 2026-11-08 | **Nothing in 2.7:** nothing merges to main for it, and #2906 stays out. A 2.8 input, not placed: the 2.8 plan places its demonstration and the worker registry's migration, on the owner's ruling |
| #2848 | Nebulus, the proving Project plan | A draft. Its environment is #2847, which is out of 2.7. 9 added lines name the operator | Stays a draft until #2847 is placed. Its names are fixed when it's next revised |

## 6. The owner's rulings (2026-11-08)

Each ruling is recorded as the owner gave it, in the second review round.

- **R1. The feature work moves to 2.8:** #2287, #2421, #950, #2781, and #2709's additional lifecycle operations.
  - The authorization, idempotency and conflict protections already required of existing operations are explicitly
    kept.
  - Concurrency hardening is split into 2.7 only if a concrete defect and a fix that can be verified on its own are
    identified.
  - SIP-0112 stays open.
- **R2. #2862 is in, and #2954 moves to 2.8.**
  - **The credential, ruled again on 2026-11-08:** the host's current GitHub access, used only to read, in place of a separate read-only token (SIP-0112 H.28).
  - **The timer, ruled against on 2026-11-08** (option 1): no host sweep, and the check at the point of use. The next Campaign's draft calls `POST /api/v1/projects/{id}/integration-check`, which syncs, re-validates and answers what still waits, with the request's token, else the one the deploy holds for the Project (SIP-0112 H.30, superseding H.28; SIP-0109 §24ds).
  - #2862 corrects stale Project state after a merged contribution. It uses the read-only fetch credential already
    chosen, the sync and its revalidation gates, and a visible `unreconciled` result when synchronization fails.
  - #2954 changes what the next proposal receives, and the adopted 2.6.1 plan classed it as a feature. Deferring it
    keeps the owner's feature-free instruction.
- **R3. One automatic re-proposal after row 19.**
  - **Dropped on 2026-11-08** by SIP-0115 §10f: SIP-0109 §24do (#2992, D1) left no path that ends an item at row 19, so the rule had nothing to act on.
  - The abandonment's reason is kept and shown to the replacement proposal.
  - The retry allowance is derived from the control log, so a restart, a reorder or an unrelated goal revision can't
    reset it.
  - A second row-19 abandonment leaves the item abandoned.
  - Every criterion still discriminates, and the rules for selecting the next eligible item are unchanged.
- **R4. Not all five are closed.**
  - #1469 stays open, as blocked or deferred.
  - #557 stays open under its tracking commitment.
  - #949 is closed administratively once its remaining work and pickup condition are explicit in the portfolio.
  - #2230 is closed as deferred to 3.x, with its ledger link.
  - #2938's SquadOps remainder is closed after a numbered scope amendment and a linked product-side record of the
    viewer work.
- **R5. #2782 is deferred to the next explicitly placed evaluator cut and window re-read.**
  - It's a scheduling choice. A tag change keeps different measures from being treated as one series; it doesn't
    invalidate archived evidence.
  - The evaluator in use is `-8`.
  - Until then, the rendering claim is narrowed to the markup cases actually fixed, and says stylesheet-computed
    visibility remains unjudged.
- **R6. The soak uses `z_shelfnote`.**
  - The adopted 2.6.1 plan keeps release verification off battle-trainer, whose goals belong to the game maker and the
    operator.
  - #2892's older repository condition is amended.
  - The chosen commits, the scripted changes, the upstream-push injection and the reconciliation expectations are
    pre-registered.
  - The real repository flow is exercised on that fixture.
- **R7. Keep the protection, and generalize its names and configuration.**
  - The policy is read from administrator-controlled settings, or from configuration trusted on the default branch, so
    a guarded pull request can't control the policy that judges it.
  - Missing configuration, an unknown role and a failed identity resolution never silently disable the protection.
  - The order:
    1. the replacement check is established;
    2. the required rulesets are switched, which is the owner's act;
    3. the old check is retired.

    So protection stays continuous.
- **R8. #2872 is edited into a framework-only proposal.**
  - The external personas, messaging, broker and launch details move to the operator's repository.
  - Sealed-suite independence is kept: no squad role gains access to a sealed cohort, or runs one.
  - The generic simulator-score step stays future feature design.
  - It's rebased, its intake is repeated, and it merges only as proposed and unnumbered. Acceptance and implementation
    stay separate decisions.
  - The same distinction applies to the other design PRs in §5a.
- **R9. A bounded merge-on-green grant for the adopted implementation scope.**
  - The PR's checks, and every job of main's CI, finish green at the current tip.
  - Outside the grant: the owner's rulings, branch-protection changes, secret provisioning, and changes to the release
    claim.
