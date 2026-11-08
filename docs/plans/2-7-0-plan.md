# 2.7.0 plan: the 2.6 line's debts, closed

**Status: DRAFT for review (2026-11-08).** The owner asked for a 2.7 plan that closes as many of the 44 open issues as it
can, while keeping 2.7 free of new features. Nothing here is built until the owner adopts it. §6 lists the rulings the
plan needs.

**What 2.7 is.** An odd minor, so a stabilization release, feature-free by rule (CLAUDE.md, #281). Every item below is
one of these:
- a defect in shipped behaviour;
- a seam the 2.6 line left unfinished;
- debt;
- the verification the 2.6 cut moved here: the overnight soak, and an accepted product increment end to end.

Five issues the SIP ledgers placed in 2.7.0 are new capabilities, so this plan proposes moving them to 2.8 (§5, ruling R1).

**The claim it makes:**

> **On a Campaign, a verdict says what happened, and the box survives what happens to it:**
> - a criterion that asserts nothing, or passes on the head, is refused to qa, not read as already met;
> - a page reads as rendered only when it rendered, and a correct added page can be accepted;
> - a power loss, a reboot or a redelivered task leaves a run that recovers or says why it can't;
> - a Campaign runs eight increments overnight through a restart, a token expiry, an upstream push and a pause,
>   with no model in the loop;
> - an accepted product increment is read end to end on a repository-backed Project.

## 1. The count

| Bucket | Issues | Count |
|---|---|---|
| Fixed in 2.7 (committed) | §2, Tracks A–E | 22 |
| Fixed in 2.7 if time allows (stretch) | #2826 | 1 |
| Closed on evidence, nothing to build | #2944, #2893, #2230 | 3 |
| In if the owner rules so (recommended) | #2954, #2862 (build); #1469, #557, #949 (close) | 5 |
| Out: new capabilities, or not SquadOps work | §5 | 13 |
| **Total open on 2026-11-08** | | **44** |

**Expected: 27 closed, ceiling 31.** The ceiling is 22 + 3 + 5 + 1, with every recommended ruling taken. The
expectation leaves out the items most likely to slip: the soak (Track D, 3 issues) can find a defect that takes the
rest of the line, and #2782 needs a new evaluator image. Earlier (2026-11-08) the estimate was 11. That counted only
what the ledgers and the 2.6.x cuts had placed, before the debt and verdict defects were triaged.

Two candidates found during 2.6.1 have no issue yet. They are filed when the plan is adopted and fixed in Track B, so
they add to the closed count without changing the 44:
- an index for the artifact store, so a listing doesn't walk the tree (the real fix behind #2921);
- an explanation on the console's Memory view when a Project has no records, saying what makes one.

## 2. The tracks

### Track A: a verdict says what happened (10)

| # | Defect | The fix, in short |
|---|---|---|
| #2933 | **D1.** A criterion test that asserts nothing passes on the head, and row 19 abandons a real backlog item, uncounted | The owner ruled option (a) on 2026-11-07 (2.6.1 plan §3): a criterion that passes on the head on qa's first emission is refused to qa as not failing on the head, spending one repair round, and the item is abandoned only if the round ends the same way. A succeeded qa result has to become a failure before acceptance, so the correction loop sends it to `qa.test_repair`. A SIP-0109 amendment beside §24dh. Needs the typed-check seam table and a wiring test through a live dispatch |
| #2935 | One criterion passing on the head abandons the increment, though another fails there | Gap 1: the proposal brief says how to write an item that's half true today (the guard goes inside the failing criterion). Gap 2 waits for ruling R3. With D1, the half that passes goes to qa instead of ending the run |
| #2949 | A suite handed to the product's runner reads as failed with exit -1 before the runner passes it | The analysis in the 2.6.1 plan's item 4 stands: keep `failed` as the stored marker, and name the hand-off where it's read, with the runner's verdict beside it. First, a table of the seven readers of `failed` in the PR's Evidence |
| #2839 | A dev repair rewrote product code to drop a declared dependency the qa image lacked | Verify first: since #2818 a product's suite runs on its own install, which may have removed the trigger. If a replay shows it can't recur, close on that evidence. Otherwise a repair that removes a use of a declared dependency is refused |
| #2799 | On a vitest product, a page criterion for an added page fails at setup on the accepted tree, so it can't discriminate | #2602's shape on a product: the test reaches the new view in a way that fails as an assertion, not at import, with no product-specific loader |
| #2783 | A change request can reuse the anchor of a page an earlier increment added | Anchor uniqueness also checks the pages earlier increments added, read from the integrated tree |
| #2781 | A change request can't add a page whose route has a parameter | A seed for an added parameterized route, from the approved manifest, so the page is read instead of `blocked_unverified` |
| #2776 | The qa role's route rendering counts a `data-testid` in a script's text, a `<template>` or a `<noscript>` as rendered | The qa role uses `view_anchors` (`route_rendering.py`), which the product path has used since #2777 |
| #2782 | A route anchor hidden by a stylesheet reads as rendered | Visibility read from the live DOM in the next evaluator image tag |
| #2775 | A vitest config that imports or computes its settings can set reporters the derivation never reads | Where the effective config can't be read from the file's own text, the runner gets no reader, and `no_test_id_reader` says why |

### Track B: a run survives what happens to the box (5, plus the two new issues)

| # | Defect | The fix, in short |
|---|---|---|
| #2931 | A power loss leaves empty artifact metadata, and one empty file strands a re-attached run | #2968 made metadata writes atomic. What remains: fsync before the rename; a listing skips an unreadable record and names it; a re-attach that raises records the run as failed or escalates. The last needs a line in SIP-0109 §12a |
| #2932 | A stale failure can wait in the reply queue after a reboot (ask 2; ask 1 shipped in 2.6.1) | A dispatcher resuming a run discards replies that predate its dispatch |
| #2765 | A scenario diagnostic's evaluation is stored as the real cycle's | A diagnostic's evaluation is never stored as the cycle's latest. `remeasure_quality.py --record` reads the latest evaluation of the tree it measured. The stored diagnostic rows are named and marked |
| #2798 | A start that never became ready doesn't say what its readiness URL last answered | The last status, or the connection error, goes in the failure detail |
| #2286 | TensorFold's key file is read as one key | The reader takes `label: key` lines, and SquadOps reads its own label. A second client gets its own key, and rotation leaves it alone |

### Track C: debt (3)

| # | Debt | The fix |
|---|---|---|
| #2402 | Shared scripts fail on macOS's bash 3.2 (`mapfile`), and bootstrap uses bare `sed -i` | Portable forms, and a check that runs the shared scripts under bash 3.2 |
| #2736 | The embeddings port and its adapter have no caller | Removed. SIP-0110 §A.3.10's semantic index adds a port back when it's placed |
| #2737 | The integration guides name tests that don't exist, and `docs/diagrams/` shows a retired memory design | The guides name what exists. The diagrams are redrawn or removed |

### Track D: the overnight soak (3)

| # | What | Done when |
|---|---|---|
| #2495 | A scripted squad: every task answered from a recorded script, no model | Machinery cycles reach the path under test without depending on a model's output. This is test infrastructure, not a product feature |
| #2892 | A scripted soak: eight or more increments on a real repository, with a restart, a token expiry, an upstream push and a pause | The soak completes, or stops only for named reasons, and each injected event is recovered from or named. Pre-registered, in a verification-set record |
| #2760 | Whether the auth picture holds for an operator supervising an overnight Campaign | Answered by the soak's token-expiry event, and by the operator's confirmation. Closed with both |

**The soak runs on a SquadOps sample product, not on battle-trainer.** battle-trainer's goals are the game maker's and
the operator's, and a scripted squad would write nothing to it that anyone asked for.

### Track E: an accepted product increment end to end (1)

| # | What | Done when |
|---|---|---|
| #2827 | SIP-0112 H.4's remainder: an accepted product increment end to end, plus H.13's two unbuilt items (`nextjs_ts`'s collected-test vocabulary; a plan-less product cycle's test author shown the product) | One counted increment, accepted and read end to end on a repository-backed sample Project, after #2799 lands. The two H.13 items built. SIP-0112's ledger row shipped |

### Stretch

- **#2826:** a stack convention that pins a collection endpoint's response to a bare list. It changes what a roll
  builds, so it needs the line's pre-registration for an output-quality change, with rolls before and after. In only
  if Tracks A–E leave room.

## 3. Closed on evidence, nothing to build (3)

- **#2944:** the product's reading reaches the next proposal. Shipped in 2.6.0 (PR #2945, SIP-0109 §24dk). Its
  remainder, the squad choosing its own next item, was ruled on 2026-11-07: backlog goals are written for the squad, so
  SIP-0115 §5.3 stands.
- **#2893:** register battle-trainer as 2.6's proving Project. Done: `prj-battle-trainer` ran the 2.6.0 cut.
- **#2230:** the TensorFold 1.x upgrade. The owner deferred it to 3.x on 2026-10-30, and SIP-0111's ledger says so. A
  row deferred to a later major line needs no open issue until that line's first plan (CLAUDE.md, the delivery ledger).

## 4. How the line is built and verified

- **Order:**
  1. Track B, which is operational and small.
  2. D1 and #2949, which share the executor's qa seam and the readers of `failed`, so one seam table serves both.
  3. The rest of Track A.
  4. Track E once #2799 is in.
  5. Track D last, because the soak is cut evidence and has to run on the final code.
  6. Track C fits anywhere.
- **Each issue is its own PR,** with `Closes #N` or `Refs #N — remaining: …`, merged on green with main's CI finished
  at its tip, under whatever merge grant the owner gives for the line.
- **Each changed seam has a wiring test** that enters at the caller the live cycle uses (TEST_QUALITY_STANDARD 6a), and
  each typed-check change has the seam table (CLAUDE.md, typed checks). D1 and #2949 need both.
- **Each SIP change is a numbered amendment in the PR that diverges:**
  - D1: SIP-0109, beside §24dh;
  - #2931's re-attach: SIP-0109 §12a;
  - #2935's gap 2 (if ruled): SIP-0115 §5.3;
  - #2827: SIP-0112's ledger.
- **Deploys happen only when no Campaign is running.**
- **The cut's evidence:**
  - the soak's record (Track D);
  - the counted product increment (Track E);
  - each fix's live check on the final deploy;
  - one `group_run` cycle for the package, named `shakeout`.

  The shakeout loop's exit rule: a pair on one deploy with no new seam finding, and the record says how many rounds it
  took.
- **What the cut won't claim:** that a model plays a product better. A sealed play claim on battle-trainer is the
  operator's to make, with the operator's goals.

## 5. Out of 2.7 (13)

**New capabilities. The ledgers placed five of them in 2.7.0, and R1 proposes moving them to 2.8:**
- **#2938:** an increment's play measured in the product's simulator (SIP-0109). The owner ruled it report-only, but it
  is still a new reading.
- **#2287:** an operator lease outside Campaigns (SIP-0109 §9.3).
- **#2421:** the sandbox running a product's declared commands (SIP-0102, SIP-0112 X-3).
- **#2709:** lifecycle completeness: update history, archive and restore (SIP-0112 E.4.5).
- **#950:** the review packet at the plan gate (SIP-0093). Its ledger already says "2.7 or later".

**New capabilities, already unplaced or for a feature line:**
- **#1978:** the test-first red gate. It changes verdicts and needs calibration.
- **#2173:** the memory entry points epic.
- **#2834:** console surfaces for the campaigns, projects and scenarios commands. SIP-0069 D7 makes parity normative,
  but closing it is about forty new commands and panels.
- **#2847:** Project environments.
- **#2906:** a Luau runner kind. The owner deferred it on 2026-11-05.

**Not SquadOps build work:**
- **#1039:** the docs site's design pass. It rides along whenever the docs are next touched.
- **#1965:** Verification Yield, ruled the operator's first optimization experiment (2026-10-04).
- **#2723:** held-out suite revision 7. The cut needs no new suite revision.

## 6. Rulings for the owner

- **R1. Move the five ledger-placed capabilities to 2.8:** #2938, #2287, #2421, #2709, #950. **Recommended: yes.** They
  are features, and 2.7 is odd. If adopted, the adoption PR re-places their ledger rows. Otherwise each one needs a
  named exception to the odd-minor rule.
- **R2. Two seams the owner placed in 2.7 that read as features:**
  - **#2954:** an operator's assessment shown in the Campaign digest and the next proposal. The 2.6.1 plan called it a
    feature. The record exists, and the change shows it to the squad.
  - **#2862:** a merged contribution syncs its Project. The owner chose its design on 2026-11-05.

  **Recommended: both in, as named exceptions.** Each closes a gap an operator meets on every increment: an assessment
  that reaches no one, and a product read stale after every merge. Neither adds a surface.
- **R3. #2935's gap 2:** on a goal-set Campaign, an item abandoned at row 19 reads `abandoned` and is never proposed
  again, though row 19 says the Campaign "proposes anew". **Recommended:** an item abandoned at row 19 stays eligible
  once, and the next proposal for it is shown why it was abandoned. That's a SIP-0115 §5.3 amendment. With D1 built,
  fewer items reach row 19 at all.
- **R4. Close three issues as not worth building:**
  - **#1469** (`frontend_build` contributes one signature element): one occurrence in 1,050 recorded runs (read
    2026-10-28).
  - **#557 and #949:** direction markers after Outcome Evaluation. Each is already recorded in `sips/PORTFOLIO.md`, and
    a SIP picks it up when it's placed.

  **Recommended: yes.** Each closing comment names where the idea stays recorded.
- **R5. A merge grant for the line,** as for 2.6.1: merge on green, with main's CI finished at its tip. The rulings stay
  the owner's.
