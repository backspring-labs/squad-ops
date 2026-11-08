# 2.7.0 plan: the 2.6 line's debts, closed

**Status: DRAFT for review (2026-11-08, revision 2).** The owner asked for a 2.7 plan that closes as many of the 44 open
issues as it can, while keeping 2.7 free of new features. Nothing here is built until the owner adopts it. §6 lists
the rulings the plan needs.

**Revision 2** checks each claim in revision 1 against the code, the SIP ledgers and the issues' own text. These
changed:
- **Moved out of the committed list:**
  - #2781 is a design change that needs an outside review, and its refusal is the documented behaviour until then.
  - #2782 moves the evaluator image's tag, which ends every quality series on `-7` (R5).
- **Narrowed:**
  - Half of #2286 shipped in `e4a3d20d`.
  - #2931 has more left than "fsync".
  - #2827 may be readable from the 2.6.0 cut's records, with no new run.
- **Recast:**
  - #2938's SquadOps part shipped (§24dj). Its remainder is in battle-trainer's own viewer, so it's a close, not a move to 2.8 (R4).
  - #2421's remainder is the approved-secret resolution, not the declared commands, which shipped as X-3a.
- **Added:**
  - where the soak runs (R6): the issue says battle-trainer's real repository;
  - the operator-name guard (R7);
  - what R1 costs SIP-0112.

**What 2.7 is.** An odd minor, so a stabilization release, feature-free by rule (CLAUDE.md, #281). Every committed item
is one of these:
- a defect in shipped behaviour;
- a seam the 2.6 line left unfinished;
- debt;
- the verification the 2.6.0 cut moved here: the overnight soak, and an accepted product increment read end to end.

**The claim it makes:**

> **On a Campaign, a verdict says what happened, and the box survives what happens to it:**
> - a criterion that asserts nothing, or passes on the head, is refused to qa, not read as already met;
> - a page reads as rendered only when an element rendered it, and a page criterion on a vitest product can fail as
>   an assertion;
> - a power loss, a reboot or a redelivered task leaves a run that recovers or says why it can't;
> - a Campaign runs eight increments overnight through a restart, a token expiry, an upstream push and a pause, with
>   no model in the loop;
> - an accepted product increment is read end to end on a repository-backed Project.

## 1. The count

| Bucket | Issues | Count |
|---|---|---|
| Fixed in 2.7 (committed) | §2, Tracks A–E | 20 |
| Fixed if time allows (stretch) | #2826 | 1 |
| Closed on evidence, nothing to build | #2944, #2893 | 2 |
| In if the owner rules so (recommended) | R2: #2954, #2862 (built). R4: #1469, #557, #949, #2230, #2938 (closed) | 7 |
| Out: new capabilities, design changes, or not SquadOps build work | §5 | 14 |
| **Total open on 2026-11-08** | | **44** |

**Expected: 26 closed, ceiling 30.** The ceiling is 20 + 2 + 7 + 1, with every recommended ruling taken. The expectation
assumes the soak's three issues (Track D) slip. The soak needs the scripted squad built first, it's the line's largest
piece of new code, and a soak can find a defect that takes the rest of the line. The same piece slipped out of 2.6.

Three items have no issue yet. They are filed when the plan is adopted and fixed in Track B, so they add to the
closed count without changing the 44:
- an index for the artifact store, so a listing doesn't walk the tree. #2968 moved the walk off the event loop, but
  each page still reads every `metadata.json` under its scan directory;
- an explanation on the console's Memory view when a Project has no records, saying what makes one;
- the operator-name guard, if R7 is ruled as recommended.

## 2. The tracks

### Track A: a verdict says what happened (8)

| # | Defect | The fix, in short |
|---|---|---|
| #2933 | **D1.** A criterion test that asserts nothing passes on the head, and row 19 abandons a real backlog item, uncounted | Ruled option (a) on 2026-11-07 (2.6.1 plan §3): a criterion that passes on the head on qa's first emission is refused to qa as not failing on the head, spending one repair round, and the item is abandoned only if the round ends the same way. The head check runs after the qa emission is accepted (`dispatched_flow_executor.py:2356`) and nothing fails a succeeded task, so a succeeded qa result has to become a failure before acceptance for the correction loop to send it to `qa.test_repair`. A SIP-0109 amendment beside §24dh. Needs the typed-check seam table and a wiring test through a live dispatch |
| #2935 | One criterion passing on the head abandons the increment, though another fails there | Gap 1: the proposal brief says how to write an item that's half true today, with the guard inside the failing criterion, not as a criterion of its own. Not yet in any fragment. Gap 2 waits for R3. With D1 built, the half that passes goes to qa instead of ending the run |
| #2949 | A suite handed to the product's runner reads as failed with exit -1 before the runner passes it | The 2.6.1 plan's item 4 stands. Keep `failed` as the stored marker, since the vault is write-once and the bytes really are the image's unrun attempt. Name the hand-off where it's read, with the runner's verdict beside it. First, a table of the seven readers of `failed` in the PR's Evidence |
| #2839 | A dev repair rewrote product code to drop a declared dependency the qa image lacked, and the increment was accepted | Verify first. The incident (2026-10-31) predates 2.5.1's #2818: a suite the qa image fails is now judged on the product's runner (`judge_on_product_runner`, `dispatched_flow_executor.py:4810`), where the declared dependency is installed, so no repair is dispatched when it passes there. If a replay of the incident's inputs shows that, close on that evidence. Otherwise a repair that removes a declared dependency's import is refused |
| #2799 | On a vitest product, a page criterion for an added page fails at setup on the accepted tree, so it can't discriminate | A design choice first (the issue's two options): (1) a framework-placed loader that resolves the view by path at run time and renders a not-found marker, as #2749 did for Next.js; (2) the test-scope appendix shows qa the run-time import idiom. **Recommended: (1),** since it doesn't depend on the model following an idiom. Either needs the seam table |
| #2783 | A change request can reuse the anchor of a page an earlier increment added | `anchor_conflicts` (`campaigns/change_request.py:1146`) checks the approved manifest's views and the request's own added pages. It also checks the pages earlier increments added, read from the integrated tree |
| #2776 | The qa role's route rendering counts a `data-testid` in a script's text, a `<template>` or a `<noscript>` as rendered | The qa path reads `_TESTID.findall(dom)` (`route_rendering.py:53`, `:182`). It uses `view_anchors` instead, which the product path has used since #2777 |
| #2775 | A vitest config that imports or computes its settings can set reporters the derivation never reads | Where `_vitest_unread` (`projects/profile_derivation.py:255`) can't read the effective config from the file's own text, the runner gets no reader, and `no_test_id_reader` says why |

### Track B: a run survives what happens to the box (5, plus the new issues)

| # | Defect | What remains |
|---|---|---|
| #2931 | A power loss leaves empty artifact metadata, and one empty file strands a re-attached run | #2968 made metadata writes atomic (temp file, then rename). Still to do: <ul><li>content is written with a bare `write_bytes` (`filesystem_artifact_vault.py:110`), and the baselines with `write_text` (`:311`);</li><li>nothing is fsynced;</li><li>`_load_metadata` (`:283`) raises on an unreadable file, which fails every listing that walks past it;</li><li>a re-attach that raises leaves the run `running` with no owner.</li></ul>The fix: the same atomic write for content and baselines, with fsync of the file and its directory; a listing skips an unreadable record and names it; a re-attach that raises records the run as failed or escalates. The last needs a line in SIP-0109 §12a |
| #2932 | Ask 2 (ask 1 shipped in 2.6.1): a stale failed reply can wait in the reply queue and be read by a resumed run | A resume re-dispatches the same `task_id`, and `reply_router` drops only unknown tasks, so the two can't be told apart today. Each dispatch carries an identity its reply echoes, and a resumed run discards replies to an earlier dispatch. This is the issue's second option, chosen because it lives at one seam where the first needs every agent to probe its engine |
| #2765 | A scenario diagnostic's evaluation is stored as the real cycle's | `read_scenarios.py --fault` calls `evaluate_cycle(store=…, cycle=cycle)` (`:136`). A diagnostic's evaluation is never stored as the cycle's latest. `remeasure_quality.py --record` reads the latest evaluation of the tree it measured. The stored diagnostic rows are named and marked |
| #2798 | A start that never became ready doesn't say what its readiness URL last answered | `_answers` (`adapters/sandbox/scenario_runner.py:828`) returns a bool. The last status or connection error goes in the failure detail |
| #2286 | TensorFold's key file was read as one key | Shipped in `e4a3d20d` (2026-10-24): readers take the `squadops` line by its label, and rotation rewrites only that line. Remaining: `docs/ops/credential_rotation.md` says how an operator key is added, rotated and removed by hand, with the restart through `engine_switch.py` when the box is idle, and that the launch gate reads a request on that key as busy, as intended. The issue's managed `SQUADOPS_TENSORFOLD_OPERATOR_KEYS` is dropped as unneeded, which is said when the issue closes |

### Track C: debt (3)

| # | Debt | The fix |
|---|---|---|
| #2402 | Shared scripts fail on macOS's bash 3.2: `mapfile` in `run_prose_lane.sh`, and bare `sed -i` in `scripts/bootstrap/lib/langfuse_setup.sh:196-212` | Portable forms, and a check that the shared scripts parse under bash 3.2 |
| #2736 | The embeddings port and its adapter have no caller | Removed, the issue's recommendation 2. SIP-0110 §A.3.10's semantic index designs its own port when it's placed |
| #2737 | `tests/integration/README.md` and `EXECUTION_GUIDE.md` name tests that don't exist, and `docs/diagrams/` shows a retired memory design | The guides name what exists. The diagrams are redrawn or removed |

### Track D: the overnight soak (3)

| # | What | Done when |
|---|---|---|
| #2495 | A scripted squad: a `machinery` squad profile whose every task is answered from a recorded script behind the LLM port | Machinery cycles reach the path under test without a model. **It is new code,** but test infrastructure, not a product feature. The 2.6.0 cut moved the soak here, and the soak needs it. A scripted run never counts as evidence about a model or a prompt, and its record says it was scripted |
| #2892 | A scripted soak: eight or more increments, with a deploy restart, a token expiry, an upstream push and a pause | The soak completes, or stops only for named reasons, and each injected event is recovered from or named. Pre-registered, in a verification-set record. Where it runs is R6 |
| #2760 | Whether the auth picture holds for an operator supervising an overnight Campaign | The soak's token-expiry event reads the refresh path under the realm's lifetimes. The operator is asked to confirm. If no confirmation comes before the cut, the issue closes on the soak's evidence and says so |

### Track E: an accepted product increment end to end (1)

| # | What | Done when |
|---|---|---|
| #2827 | SIP-0112 H.4's remainder: an accepted product increment end to end (IR-5, IR-6's increment half, IR-9's increment reading), plus H.13's two unbuilt items (`nextjs_ts`'s collected-test vocabulary; a plan-less product cycle's test author shown the product) | **First, read the readings from records that exist.** The 2.6.0 cut accepted BT-11 on battle-trainer (`cyc_2efc17faf3e5`), and it reached a review request (battle-trainer PR #11) and main. IR-5, IR-6's increment half and IR-9 are read from that increment's records, with no Campaign run on battle-trainer. A reading those records can't give gets one counted increment on `z_shelfnote` after #2799, for example IR-6, since battle-trainer declares no start. Then build the two H.13 items, and mark SIP-0112's ledger row shipped |

### Stretch

- **#2826:** a stack convention that pins a collection endpoint's response to a bare list. It changes what a roll
  builds, so it needs the line's pre-registration for an output-quality change, with rolls before and after. In only
  if Tracks A–E leave room.

## 3. Closed on evidence, nothing to build (2)

- **#2944:** the product's reading reaches the next proposal. Shipped in 2.6.0 (PR #2945, SIP-0109 §24dk). PR #2945
  left one remainder, the squad choosing its own next item. The owner ruled on 2026-11-07 that backlog goals are written
  for the squad, so SIP-0115 §5.3 stands and there is nothing left to build.
- **#2893:** register battle-trainer as 2.6's proving Project. Its done-when (validated READY, a baseline with
  `contract_tests` PASS, the vitest runner and the package surface derived) was met before the 2.6.0 cut, which ran on
  `prj-battle-trainer`.

## 4. How the line is built and verified

- **Order:**
  1. Track B, which is operational and small.
  2. D1 and #2949, which share the executor's qa path and the readers of `failed`, so one seam table serves both.
  3. The rest of Track A.
  4. Track E, reading BT-11's records first, then #2799 before any new increment.
  5. Track D last, because the soak is cut evidence and has to run on the final code.
  6. Track C fits anywhere.
- **Each issue is its own PR,** with `Closes #N` or `Refs #N — remaining: …`, merged on green with main's CI finished
  at its tip, under whatever merge grant the owner gives for the line (R8).
- **Each changed seam has a wiring test** that enters at the caller the live cycle uses (TEST_QUALITY_STANDARD 6a), and
  each typed-check change has the seam table (CLAUDE.md, typed checks). D1, #2949 and #2799 need both.
- **Each SIP change is a numbered amendment in the PR that diverges:**
  - D1: SIP-0109, beside §24dh;
  - #2931's re-attach: SIP-0109 §12a;
  - #2935's gap 2, if ruled: SIP-0115 §5.3;
  - #2827: SIP-0112's ledger.
- **Deploys happen only when no Campaign is running.**
- **The cut's evidence:**
  - the soak's record (Track D);
  - the end-to-end readings (Track E);
  - each fix's live check on the final deploy;
  - one `group_run` cycle for the package, named `shakeout`.

  The shakeout loop's exit rule: a pair on one deploy with no new seam finding, and the record says how many rounds it
  took.
- **The SIP sweep at the cut, expected:** none promotes.
  - SIP-0112 can't close while E.4.5 (#2709) is open (R1).
  - SIP-0115 closes on an operator's reading of three accepted items in one Campaign, which is the operator's work on
    battle-trainer, not this plan's.
  - SIP-0109 keeps open rows (#2287, #2781).
- **What the cut won't claim:** that a model plays a product better. A sealed play claim on battle-trainer is the
  operator's to make, with the operator's goals.
- **The adoption PR, after the rulings:**
  - re-places the ledger rows R1 and R4 move;
  - adds the ROADMAP's 2.7 row;
  - files the three new issues.

## 5. Out of 2.7 (14)

**New capabilities the ledgers placed in 2.7.0. R1 moves them to 2.8:**
- **#2287:** an operator lease outside Campaigns (SIP-0109 §9.3).
- **#2421:** the remainder of SIP-0102's X-3b: resolving an owner-approved evaluation secret into the copy's environment
  at start. The declared commands shipped as X-3a. A design waits for the owner's ruling, in the issue's 2026-10-24
  comment.
- **#2709:** SIP-0112 E.4.5: update history, archive and restore, and concurrency and conflict recovery.
- **#950:** the review packet at the plan gate (SIP-0093). Its ledger already says "2.7 or later".

**A design change:**
- **#2781:** a change request that adds a page whose route has a parameter. It extends §7.2's change request (the create
  endpoint, its body, the parameter the created id fills), so it needs its own design and an outside review (SIP-0112
  H.12). Until then the refusal stands, as designed. Its SIP-0109 row moves with R1.

**Deferred by R5:**
- **#2782:** a stylesheet-hidden route anchor read as rendered. The fix moves the evaluator image's tag.

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
- **#2723:** held-out suite revision 7. A suite revision needs its own independent review and validation rolls, and no
  2.7 claim reads the held-out suite.

## 6. Rulings for the owner

- **R1. Move #2287, #2421, #2709 and #950 to 2.8, with #2781's row.** **Recommended: yes.** They are new capabilities,
  and 2.7 is odd.
  - **The cost:** SIP-0112 can't close until #2709 ships. The owner ruled on 2026-10-23 to close SIP-0112 in 2.6, and
    SIP-0112's own record (line 3291) already says that can't happen.
  - **An alternative:** split #2709. Concurrency and conflict recovery (two writers to one Project, and recovery when
    they conflict) is hardening and could be built in 2.7. Update history and archive and restore are features, and go
    to 2.8. This plan doesn't count the split.
- **R2. Two seams the owner placed in 2.7 that read as features:**
  - **#2954:** an operator's assessment shown in the Campaign digest and the next proposal. The 2.6.1 plan called it a
    feature. The record exists, and the change shows it to the squad.
  - **#2862:** a merged contribution syncs its Project. The owner chose its design on 2026-11-05: a read-only credential
    for the merge sweep's fetch, and the sync re-validates. Adding the secret to the deploy is the owner's act.

  **Recommended: both in, as named exceptions to the odd-minor rule.** Each closes a gap an operator meets on every
  increment: an assessment that reaches no one, and a product read stale after every merge. Neither adds a surface.
- **R3. #2935's gap 2:** on a goal-set Campaign, an item abandoned at row 19 reads `abandoned` and is never proposed
  again, though row 19 says the Campaign "proposes anew". **Recommended:** an item abandoned at row 19 stays eligible
  once, and its next proposal is shown why it was abandoned. That's a SIP-0115 §5.3 amendment. With D1 built, fewer
  items reach row 19 at all.
- **R4. Close five issues, each with a comment naming where its remainder stays recorded:**
  - **#1469** (`frontend_build` contributes one signature element): one occurrence in 1,050 recorded runs, and that
    one predates #2028 (read 2026-10-28).
  - **#557:** the proposed SIP `SIP-Post-Retest-Governance-Acceptance-Review.md` carries it.
  - **#949:** `sips/PORTFOLIO.md` theme 9 and Q2 carry it.
  - **#2230:** the TensorFold 1.x upgrade, deferred to 3.x on 2026-10-30. SIP-0111's ledger says so, and a row deferred
    to a later major line needs no open issue until that line's first plan.
  - **#2938:** SquadOps's part shipped in 2.6.0 (§24dj, report-only readings). What remains is battle-trainer's replay
    viewer recording a new version with no step by hand. That viewer is the product's own tool (`tools/viewer/`,
    battle-trainer PR #3, awaiting the owner's merge), so SquadOps has nothing to build. SIP-0109's row is dropped by a
    numbered amendment in the adoption PR.

  **Recommended: yes.**
- **R5. #2782 and the evaluator image.** Reading visibility from the live DOM changes `driver.mjs`, so the evaluator
  image's tag moves and every quality series on `-7` ends (`test_evaluator_image.py`). **Recommended:** defer it to the
  next line that re-reads a measurement window. 2.7 has none, and an ended series with no new window to start is a
  loss with nothing in return.
- **R6. Where the soak runs.** #2892 and the 2.6 plan say "the proving product's real repository": battle-trainer.
  Since 2026-11-07, battle-trainer holds no rule the game maker didn't set, and the supervisor writes no project code.
  A scripted squad pushes recorded, supervisor-chosen changes, and the upstream push is part of the test. **Recommended:**
  `backspring-labs/z_shelfnote`, the private repository the owner approved as a SquadOps destination on 2026-10-20.
  It's already a configured product on the Spark. The soak tests the control loop, which is the same on either product.
- **R7. The operator-name guard.** The owner's ruling of 2026-11-07 kept, through 2.6, the required check that guards an
  operator's branches: its workflow, script, path-boundary config and branch rulesets. All four carry the operator's
  name, so the repository still names one. Dated records keep their words, under the same ruling. **Recommended: keep
  the protection and rename it.**
  - It becomes "operator branch checks".
  - The operator's branch prefix, bot identities and role names move out of tracked files into repository settings,
    so the repository no longer names the operator.
  - Removing the guard would leave an outside party's pull requests unconstrained by path.
  - Renaming a required check and its rulesets is a change to branch protection, which is the owner's act.
- **R8. A merge grant for the line,** as for 2.6.1: merge on green, with main's CI finished at its tip. The rulings stay
  the owner's.
