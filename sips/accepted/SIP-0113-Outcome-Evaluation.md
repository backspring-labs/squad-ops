---
sip_uid: '1791124609460026'
status: accepted
title: Outcome Evaluation
author: Jason Ladd
created_at: '2026-10-04T00:00:00Z'
sip_number: 113
updated_at: '2026-10-17T23:13:12.320896Z'
---
# SIP-0113: Outcome Evaluation

**Status:** Accepted (2026-10-17, revision 2)
**Revision:** 2 (2026-10-17)
**Target:** 2.4, on the Spark lane (the 2.4 plan, adopted 2026-10-17, `docs/plans/2-4-0-plan.md`):
- **phase 1, the instruments, reporting only:** committed for the 2.4 cut (the plan's D1 and §6.1);
- **phase 2, the feature half:** in 2.4 only if the measurement window's record supports it. The owner decides on that
  record (D4). If it moves, it moves to the next even release with the record.

**Authors:** Jason Ladd (the idea); Claude Code (this draft)
**Source:** `docs/ideas/outcome-oriented-campaign-evaluation.md` (recorded 2026-10-04). This SIP is
that idea's **evaluation half**; the rest stays in the idea as its charter.
**Builds on:**
- SIP-0109 (Campaign);
- SIP-0096 (verification evidence integrity);
- SIP-0102 (the ephemeral application sandbox);
- SIP-0109 §8.3 (route rendering in a real browser);
- the Nostromo IDEA (`docs/ideas/nostromo-framework-optimization-crew.md`).

**Meets:** Project Lifecycle Management (SIP-0112, `sips/accepted/SIP-0112-Project-Lifecycle-Management.md`, accepted
2026-10-17), the MacBook lane's 2.4 feature, at seven shared
contracts (its §8.2). §4.8 says what this SIP produces and reads at each.

---

> **Intake check (2026-10-04, `sips/PORTFOLIO.md`).** What this draft overlaps, and the boundary each gets:
> - **SIP-0109 §10 row 3 (accepted) owns the campaign's success reading** (portfolio cluster 1). §4.7
>   changes it, so §4.7 lands as a **numbered amendment to SIP-0109** in the PR that builds it, not as
>   this SIP's text alone.
> - **"Outcome" already means something in an implemented SIP** (cluster 2). SIP-0108's `CycleAssessment`
>   has an *outcome* dimension (verdict and criteria). This draft's outcome is independent scenarios.
>   Before phase 1 ships, this SIP renames its term (portfolio Q3 recommends "scenario evidence" and
>   "contribution"); SIP-0108's implemented name stays. **Done in revision 2** (§0).
> - **The evaluation corpora** (cluster 3) share one discipline with Verification Yield's fault corpus
>   (#1965), SIP-0108's benchmark registry and the reference scenario: content-addressed and versioned,
>   with different readers.
> - **Complements Verification Yield** (cluster 4): Verification Yield measures the value of the
>   squad's own tests; this SIP adds tests the squad never sees.
> - **Its motivating example is fixed separately.** The 2.0 set's returned proposals, behaviour the app
>   already had, are #1961 and #1962 in 2.1. This SIP's case is that a supervisor reading code should not
>   be the only thing that catches them, not that those two defects stand.
> - **Ruled 2026-10-04** (the owner accepted the portfolio's recommendations):
>   - **Q1:** this SIP's feature half heads 2.4, with Verification Yield's risk-first experiment (#1966)
>     riding on it; the squad-authored backlog is 2.6;
>   - **Q2:** the judgement steps #557, #949 and #950 follow this SIP's scenarios;
>   - **Q3:** §4.7 lands as a SIP-0109 amendment; phase 1 fits 2.3; this SIP renames its term before
>     phase 1 ships.
>
>   §8's question 5 is answered by Q1.
>
> **Intake check, revision 2 (2026-10-17).** One new overlap, by design:
> - **Project Lifecycle Management** (SIP-0112, accepted 2026-10-17; the owner's Q35) makes a Project any
>   registered product: an existing external repository, a greenfield product or a reference application.
>   The two SIPs meet at seven shared contracts, and their boundary is stated in both:
>   - this SIP builds no project model, and assumes no Project is a sample application;
>   - Project Lifecycle Management builds no scenario, runner, quality baseline or reading of its own.
>
>   The Spark lane's compatibility review of its §8 is recorded in its §8.6. Its intent is this
>   revision's design (§4.1, §4.8).
> - **No conflict.**

## Delivery ledger (current as of 2026-10-21)

One row per part that ships separately. Statuses as CLAUDE.md defines them. The 2.4 plan places phase 1 in 2.4
(committed) and phase 2 in 2.4 conditionally. **Phase 1's parts are placed** with the issues filed at acceptance
(2026-10-17), each labelled `sip:0113`. Phase 2's parts stay *unplaced* until the owner rules D4 on the window's record.

| part | status | where |
|---|---|---|
| phase 0: increment replay outside its campaign (#1959) | **shipped** | v2.1.0, PR #2026 |
| phase 0: the per-increment scorecard (#1960) | **shipped** | v2.1.0, PR #2027 |
| phase 0: reporting-only lint findings on the delivered app (#1937) | **shipped** | v2.1.0, PR #2088 |
| phase 1: the scenario store, its suites and the campaign's suite pin (§4.1, §4.7) | **shipped** (§10a) | 2.4.0, PR #2448, issue #2413 |
| phase 1: the runner, outside the squad's containers, on a disposable copy (§4.1; needs the sandbox's X-3, #2421) | **placed** | 2.4.0, #2414: the HTTP runner and the cycle-end hook shipped (§10c); the declared start at the hook remains here, and the browser runner moved to #2564 (§10k) |
| phase 1: the browser runner and page scenarios, in the evaluator's image (§4.1, A2, A3; §10k, proposed; its design review before it is built) | **placed** | 2.4.0, after the window, #2564 |
| phase 1: the evaluation record and its reference (§4.1, contract 5) | **shipped** (§10b) | 2.4.0, PR #2449, issue #2415 |
| phase 1: the quality baselines, Lighthouse, axe and lint, in the evaluator's image (§4.2) | **placed** | 2.4.0, #2416 |
| phase 1: the intervention ledger's classifications (§4.3) | **shipped** (§10d) | 2.4.0, PR #2454, issue #2417 |
| phase 1: contribution and the derived metrics in the digest (§4.4, §4.6) | **placed** | 2.4.0, #2418 |
| phase 2: the proposer sees each goal's result (§4.5) | **unplaced** | 2.4 if D4 rules it in, with its issue filed then; otherwise the next even release |
| phase 2: the objective's scenario measure, read by SIP-0109 §10 row 3, as a SIP-0109 amendment (§4.7) | **unplaced** | 2.4 if D4 rules it in, with its issue filed then; otherwise the next even release |
| quality gates where phase 1's data supports a threshold (§4.2, §6) | **unplaced** | with phase 2, each with its phase-1 evidence |
| phase 1 amendment: Lighthouse and axe on a seeded instance, parameterised pages included (§10j, proposed; its design review before it is built) | **placed** | 2.4.0, after the window, #2562 |
| a repository-backed Project's Campaign: its baseline reading, an evaluation of the calibration record's commit (§10l; SIP-0112 H.4, SIP-0109 §24bv) | **placed** | 2.5.0, #2619 |

**What closes this SIP:** phase 1 shipped and phase 2 shipped, or phase 2 dropped by a numbered amendment the owner
rules.

## 0. Terms (revision 2's rename)

Revision 1 used *outcome* for three things this SIP measures. SIP-0108's `CycleAssessment` already has an *outcome*
dimension, its verdict and criteria, and that name stays (portfolio Q3). So the renamed terms are:
- **scenario evidence:** what revision 1 called outcome evidence. It sits beside the output evidence the squad's own
  criteria produce;
- **held-out scenarios**, or **scenarios:** what it called outcome scenarios;
- **scenario result:** one scenario's `passed`, `failed` or `blocked_unverified` on one increment (§4.1);
- **contribution:** what it called outcome contribution (§4.4);
- **the scenario measure:** §4.7's addition to the objective, with its fields `scenario_suite` and `scenario_target`.

**Two names stay** (A1, ruled; the owner, 2026-10-17: "approve A1-A3 as recommended and accept 2406"):
- the SIP's own name, *Outcome Evaluation*;
- the idea's named metrics (Autonomous Outcome Reliability, the Autonomous Work Envelope).

## 1. Summary

A campaign today is measured by its **outputs**. Its objective reads "three accepted increments" (the
machine reading is `CampaignObjective.target_accepted_increments`, read by SIP-0109 §10 row 3), and
every test that accepts an increment is written by the squad's own qa role.

So a campaign can succeed without anything independent showing that the application got better. And
the evidence of how much help it needed exists only as rows nobody has classified.

This SIP adds **scenario evidence** beside the output evidence, and keeps the two apart:
1. **Held-out scenarios:** jobs a user would do, authored outside the implementing roles and held out from the squad,
   run against each increment's delivered app.
2. **Quality baselines:** Lighthouse, axe and lint scores, measured locally on the same app.
3. **An intervention ledger:** every action a person or the supervisor took, classified by reason
   and severity.
4. **A per-increment reading of contribution**, derived from 1 and 2.
5. **Derived autonomy metrics:** Autonomous Outcome Reliability (AOR) and the Autonomous Work
   Envelope (AWE), computed from the records.

**The rule the idea states, adopted here:** a campaign cannot claim increased autonomy unless product
quality meets its baseline. An autonomy number never travels without the quality reading beside it.

**Any registered Project** (Project Lifecycle Management, SIP-0112) is evaluated the same way. That covers an existing
external repository with its own layout and tooling, a greenfield product, and a reference application such as
`group_run`. A sample application's routes, fixtures or interface manifest are never a default (§4.1).

## 2. Why: the 2.0 evidence

- **The objective counts outputs.** Every 2.0 shakeout and both counted campaigns are measured by
  "three accepted increments". Accepted means the squad's own criteria passed and every earlier
  frozen criterion held. That is necessary. It says nothing about whether the app is better to use.
- **Every acceptance test is self-authored.** A criterion's test file is written by the qa role in
  the squad (SIP-0109 §8.1; `ScaffoldStack.criterion_test_files`), then frozen into a verifier
  bundle. The discrimination rule (it must fail before the change) stops a vacuous test. It does not
  make the test independent.
- **Output-oriented acceptance needs a reader of the code to catch what it misses.** In the 2.0
  counted set, campaign 1's increment 2 proposed, twice, behaviour the accepted app already had:
  - capacity enforcement, already in the join handler;
  - name trimming, already done by the frozen request models (#1962).

  Both would have passed the squad's own criteria and been "accepted". A supervisor reading the code
  caught them; nothing in the campaign's measurement would have.
- **Interventions are recorded, not classified.** The control log keeps every pause, resume, abort,
  ruling, classification and lease change, with actor, reason and key. The digest lists them. Nothing
  turns them into the dataset the outer loop needs, such as which intervention reasons recur and
  which the squad could have resolved.

## 3. What already exists (this SIP does not rebuild it)

| need | already built |
|---|---|
| campaigns commit to outcomes, not plans | SIP-0109: an objective, a measurement and bounds; the strategy role chooses each next increment from the accepted app (§9.1). What changes here is **what it chooses against**, and **what the measurement reads** |
| deterministic engineering gates (the idea's layer 1) | typed acceptance; `required_checks`; SIP-0109 §8.2's discrimination and frozen criteria; the defect-targeted static checks |
| an isolated runtime that boots the delivered app | SIP-0102's sandbox service, which starts an application at a pinned revision in a least-privilege container (`adapters/sandbox/container_backend.py`); SIP-0109 §8.3's route rendering, which stands the candidate up in the QA role's container and reads each page in headless Chromium (`src/squadops/capabilities/handlers/route_rendering.py`) |
| evidence integrity | SIP-0096: only executed-and-passed credits; what could not run is `blocked_unverified`, never passed |
| per-cycle cost and time | each cycle's assessment: `tokens_by_run`, `tokens_by_task_type`, `wall_clock_seconds`, `llm_calls` |
| per-increment roll-up and replay | 2.1: #1960 (the per-increment scorecard), #1959 (replay any increment outside its campaign) |
| lint as evidence | 2.1: #1937 (reporting-only) |
| a tree's identity | SIP-0109's `FileTree.identity` (`src/squadops/campaigns/evaluator_trees.py:60`), the identity a promotion records as the accepted tree (`src/squadops/campaigns/progress.py:612`) |

**Neighbouring proposals, kept separate:**
- `SIP-Verification-Yield`: the value of the tests the squad writes;
- `SIP-Campaign-Self-Improvement-and-Test-Bay`: SquadOps improving itself;
- SIP-0110 (Cross-Cycle Memory): what the squad recalls across cycles. Its outcome metrics (revision 2's
  recall-versus-outcome split) are one consumer of this SIP's evidence;
- Project Lifecycle Management (SIP-0112): what a Project is, its source, its revisions and its own checks. This SIP
  reads its records at seven contracts (§4.8) and keeps a product's own checks apart from its scenarios.

## 4. The design

### 4.1 Held-out scenarios

**What a scenario is.** A job, stated as a goal with a sequence of user actions and a check of the result. An example
from the idea: create a run, join it, leave it, and confirm the participant list is right. A scenario names:
- **its goal**, one sentence. It is the only part the squad may ever see, and only in phase 2 (below);
- **its steps and checks**, held out;
- **the surfaces it needs, by kind:**
  - HTTP endpoints: a method and a path from the product's declared HTTP base;
  - browser pages: a path from its declared UI base;
  - later, other kinds: a command, or a game adapter's surface (Project Lifecycle Management's FR-17).
- **its version**, content-addressed like a verifier bundle (SIP-0109 §8.1), so a result names the exact scenario it
  ran.

**Surfaces are the scenario's own.**
- **A Project's interface manifest, where it has one, only checks that the declared surfaces exist.** It is never
  required, and never their source.
- **A scenario sets up its own data in its own steps.** §8.3's seed derivation from a manifest is not used.

(Revision 1 read surfaces "against the increment's manifest". That could evaluate only a SquadOps blueprint app.)

**Authorship and storage: the independence boundary.**
- **Who writes them:** scenarios are authored outside the implementing roles. No squad role writes one.
  - **Ruled (D2):** the supervisor drafts the first suite, and the owner approves it. It is frozen and
    content-addressed before the measurement window starts.
  - The same holds for the shared demonstration's suite (the 2.4 plan's D13). The squad's own model drafts none.
- **Where they are stored:**
  - in a store of their own, in the runtime API's Postgres, behind its own port;
  - with no route that a squad agent's identity can read;
  - **not in the artifact vault,** which is where squad tasks' inputs come from: an increment's accepted tree is read
    from it (`src/squadops/campaigns/increment_tree.py`).
  - Scenarios are never stored in a product repository, a managed clone or a workspace root.
- **What SquadOps provides:** the seam (the store, the runner and the records). The content is the authors'.

**What the squad sees.**
- **In phase 1, nothing.** No scenario goal or result reaches any squad role, through a prompt, a task's inputs,
  Project Lifecycle Management's Project Context or its handoff.
- **In phase 2, only the proposal run** sees each scenario's goal and whether it passed on the accepted app (§4.5). A
  failing goal is a gap the proposer may choose to close.
- **The steps are never shown.** A scenario whose steps the builder can read becomes one more test it can optimize
  against.

**Running, and where.** After an increment's implementation completes, the runner evaluates the candidate tree.
- **The runner runs outside every squad agent's container.** §8.3's environment is the QA role's container, a squad
  task that is handed its inputs (`src/squadops/capabilities/handlers/cycle/evaluate_increment.py:3-5`). Running
  scenarios there would put their steps in a squad task's inputs.
  - **Its home (A3, ruled 2026-10-17):** the sandbox service (SIP-0102, the Spark lane's).
  - **Why there:** it already starts applications in least-privilege containers and launches the containers it needs.
- **The evaluated tree is started in a disposable copy,** built from the tree and discarded afterwards. It is never
  the live tree.
  - **Why:** today's start mounts the cycle's live tree and runs the app as its owner, so the app can write its state
    there (`adapters/sandbox/container_backend.py:157-164`, `:316-321`).
  - **The rule:** nothing a scenario caused may be captured into a revision, a Git commit or the next increment's tree
    (Project Lifecycle Management's contract 3).
- **How the product is started:**
  - **for a blueprint Project,** by its stack's probe and render profiles, as today
    (`src/squadops/capabilities/handlers/probe_runner.py:133`, `route_rendering.py:77`);
  - **for any other Project,** by its start declaration: install, build, start, readiness and entry points, from its
    Project Development Configuration at the revision the unit pinned (contract 7);
  - the sandbox runs a declared command through `ExecutionSandboxPort`, once the sandbox change X-3 ships (Project
    Lifecycle Management §8.2.2).
  - **This SIP never infers how to start a product from a sample application.**
- **The steps are held in memory only.** The runner fetches them by suite digest for each run. It writes them
  nowhere the evaluated app's process can read.
- **Secrets: evaluation-scoped only** (ruled 2026-10-17, A4 and SIP-0112's Q40: the owner, "approve Q40 as
  recommended").
  - **What the runner resolves:** only the references a Project declares for evaluation, in its start declaration's
    `evaluation_environment` (SIP-0112 §8.2.1), and that the owner approves per Project.
  - **What they are:** test credentials, never the product's production secrets.
  - **How they are handled:** they are resolved into the disposable copy's environment at start, and discarded with
    the copy. They are never written to a file, a log, a record or a squad agent's input.
  - **If a reference isn't declared and approved,** it is not resolved, and every scenario that needs it is
    `blocked_unverified`, reason "secret not available".

**The result**, per scenario per increment:
- **when it runs:** `passed`, `failed` or `blocked_unverified` (SIP-0096). It carries the steps taken, the first
  failing step, the elapsed time and the retries.
- **when it can't run,** it is `blocked_unverified`, never passed and never failed, with its reason:
  - no runner for the surface's kind;
  - no start declaration;
  - the start or readiness check failed;
  - a secret was not available;
  - a surface the scenario needs is absent;
  - the browser was not available.
- **when it doesn't apply:** a scenario whose surface kind the Project doesn't have, such as a browser scenario on a
  product with no pages, is recorded **not applicable**.
  - That is not evidence. It counts in no rate, and it is never reported as `blocked_unverified` or as passed.

**The evaluation record.** One record per evaluation run: a cycle evaluated against one suite. It has its own ID,
because one cycle can be evaluated more than once:
- a re-run after a `blocked_unverified` result;
- a #1959 replay;
- a second suite.

It carries:
- the Project ID;
- the campaign ID, or none for a reference increment (SIP-0109 §11a, #1804) or a replay outside its campaign;
- the cycle ID;
- the evaluated tree's identity and the previous accepted tree's (SIP-0109's `FileTree.identity`);
- the suite's content digest;
- for each scenario: its version, goal, applicability and result.

**What a record never does:**
- **It names no tree by sandbox revision or by Git commit.** A sandbox revision ID is a different hash of the same
  files (`src/squadops/sandbox/models.py:78`), and a candidate has no commit yet when it is evaluated.
  - The Git revision is resolved through Project Lifecycle Management's mapping (contract 4), never copied into the
    record.
  - **Unverified:** whether a candidate's evaluated identity equals the identity its promotion records. They are
    computed from different file sets, so the join to the accepted tree goes through the cycle ID.
- **It never rewrites a product's own check results** (Project Lifecycle Management's inherited verification
  baseline), and never derives from them.

**Regression.** A scenario that passed on the previous accepted tree and fails on this one is a
**regression**, read the way a broken frozen criterion is.

### 4.2 Quality baselines

**What is measured:** on the same evaluated instance the scenarios read, locally, with no external service:
- **Lighthouse:** performance, accessibility and best practices, per declared page;
- **axe:** accessibility violations, by impact;
- **lint:** #1937's fixed rule sets.

**What does not apply:**
- On a Project with no pages, Lighthouse and axe are **not applicable**.
- #1937's rule sets exist only for the scaffold stacks. On any other product, lint is recorded **not measured**.
- **What *not measured* and *not applicable* mean:** each is a record that the measure did not run or does not
  apply, and neither is evidence. Neither counts in any rate, and neither ever reads as a baseline held.
- The product's own linter is never used in its place. That is Project Lifecycle Management's inherited check, a
  separate record.

**Recording:** each measure is recorded per increment with its delta from the previous accepted tree. The
calibration's reading is the campaign's **baseline**.

**Where Lighthouse and axe are installed:**
- **Ruled (D2):** they are added to an image, with the lock files' audit. The ruling named the QA image, because
  Chromium is there for route rendering.
- **A2 (ruled 2026-10-17) moves them to the evaluator's image,** with the same lock-file audit. The baselines measure
  the instance the scenarios read, and that instance runs outside the squad's containers. The evaluator's image is a new
  image, which the sandbox service launches. It carries headless Chromium, Lighthouse, axe and the scenario driver.

**Reporting-only until a later decision** (§6). A threshold becomes a gate only in an even release,
with the reporting-only data in hand: the noise of each measure on unchanged code, and its
correlation with scenario results. The idea's §6 caution applies to every measure: one that does not
track scenario success loses its weight.

### 4.3 The intervention ledger

Every action taken on a campaign by a person, or by the supervisor seat, is a ledger entry with:
- **its reason:** clarification, planning, implementation, verification, environment, tool,
  coordination, memory or context, judgement or escalation, or authorization (the idea's §8 list);
- **its severity:** advisory, unblock, recovery or abort.

**Most entries already exist as control-log rows:**
- a `rule` that returns a proposal;
- a `resume` naming an action;
- an `abort`;
- a `pause`;
- an answer to a plan-gate design question;
- a `classify`;
- SIP-0110's re-binding of a running campaign, which its §A.3.7 writes to the campaign's control log.

The ledger adds the two classifications to each.

**An action outside the interface** (a manual repair, a manual restart) can't be a row by construction. The 2.0
pre-registration's frame (#1908 §3) already voids that campaign's claim of unattended operation. The ledger records it
as a declared entry, so the void is counted rather than only stated.

**"Could the squad have resolved it?"** is the supervisor's reading, recorded with the reason. It is
an opinion, labelled as one.

### 4.4 Contribution, per increment

A reading derived from §4.1 and §4.2, never written by a model. Scenarios recorded *not applicable* take no part:

| reading | when |
|---|---|
| **contributed** | at least one scenario newly passes, and no scenario regressed |
| **neutral** | accepted, with no scenario newly passing and none regressed: "output accepted; contribution negligible" |
| **regressed** | a scenario that passed on the previous accepted tree fails |
| **unverified** | a scenario the increment's surfaces should satisfy is `blocked_unverified` |

Quality deltas are reported beside the reading and do not change it, until §6's gates exist. An
increment can be accepted (its outputs verified) and neutral (no scenario moved). That is a result,
recorded as one.

### 4.5 Evidence-driven next increments (the feature half)

The proposal run (SIP-0109 §9.1) is shown, beside the PRD's expansion scope:
- each scenario goal with its current result;
- the quality readings against the baseline.

So the strategy role can choose the highest-value gap, and its change request may name the scenario
goals it intends to move. **Only the proposal run** sees these. No other squad role does, and no scenario step reaches
any of them.

**Its prediction is checked after the build:** a proposal that names a goal and leaves it failing
reads as such in the ledger (SIP-0109 §9.4). The supervisor still rules on every proposal; nothing
here loosens the gate.

SIP-0109 §24ap's deferred row joins this: accepted increments' `prd_delta` text shown to the proposer, the same seam
(the 2.4 plan §1.4).

### 4.6 Derived metrics

Computed in the digest from the records, never stored as a judgement:
- **Autonomous Outcome Reliability (AOR), per work class:** the share of campaigns of that class that
  reached their objective with no intervention above an `advisory` severity, every quality
  baseline held, and every safety guarantee intact.
  - **"Every quality baseline held" covers only the measures that ran.** A measure recorded *not measured* or
    *not applicable* is named beside the reading and is never counted as held (§4.2).
- **The Autonomous Work Envelope (AWE):** AOR across the work classes.
  - A **work class** is declared in the objective, never inferred. That keeps two campaigns comparable only when they
    declared the same class.
  - **Ruled (D2), the first work classes:** the increment count, the PRD tier, and whether the campaign ran attended
    or unattended.
- **Per-increment cost and time:** from #1960.
- **Comparisons across units:** a comparison of squad behaviour across campaigns names each unit's pinned
  project-instruction set (SIP-0110's snapshot) as a listed input. A difference is a changed input (SIP-0110 §0.12),
  never a gate on the reading. A per-increment reading compares two trees and needs no such match.

**No composite score.** The idea is explicit, and this SIP keeps it: trade-offs are reported, not
averaged away.

### 4.7 The objective gains a scenario measure (the feature half)

**Phase 1** pins the campaign's suite at creation.
- **The field:** an optional `scenario_suite` (a suite digest) on the campaign's creation request
  (`CampaignCreateRequest`, `src/squadops/api/campaign_schemas.py:55`), stored in this SIP's own record and keyed by
  the campaign.
- **It is reporting-only:** no SIP-0109 decision reads it.
- **It is a change to SIP-0109's surface,** so it lands with a numbered SIP-0109 amendment in that PR, through
  Project Lifecycle Management's G4. Nothing is added at `prepare_cycle()` or in a launch request.

**Phase 2** gives `CampaignObjective` its scenario measure, beside `target_accepted_increments`:
- `scenario_suite`: the pinned, content-addressed set of scenarios;
- `scenario_target`: which scenario goals must pass for success;
- `quality_baseline`: which measures must not regress beyond a stated tolerance.

§10 row 3 then reads success as **the scenario target met with the baseline held**, not the accepted count alone. A
campaign that declares no suite keeps today's reading, so 2.0's campaigns stay comparable. This is the SIP-0109
amendment Q3 requires.

### 4.8 What this SIP produces and reads at the shared contracts

Project Lifecycle Management (SIP-0112) states the seven contracts in its §8.2 and §8.2.1. This SIP's side of each is:

| contract | this SIP |
|---|---|
| 1. Project identity and source revision | records the Project ID and the evaluated tree's identity; resolves a Git revision only through contract 4's mapping |
| 2. `prepare_cycle()` and Campaign admission | adds nothing at `prepare_cycle()` or in a launch request; adds `scenario_suite` at Campaign creation (§4.7) |
| 3. `WorkspaceStore` | evaluates a disposable copy, never the live tree; no scenario file enters a workspace; names trees by identity, never by sandbox revision |
| 4. Campaign accepted trees | reads regression against the previous accepted tree, by SIP-0109's identity |
| 5. evaluation references | produces the evaluation record and its reference (`OutcomeEvaluationRef`), with the campaign ID nullable (§4.1); its names follow §0 |
| 6. project instructions | names each unit's pinned set as a listed input when comparing units (§4.6) |
| 7. starting the product | reads the start declaration at the revision the unit pinned; never infers one; with none, every scenario is `blocked_unverified` |

The shared fixture (SIP-0112 §8.2.3, #2407) carries this SIP's recorded evaluation reference, which the
Spark lane adds in the fixture's PR (the 2.4 plan's D12).

## 5. Not in this SIP (they stay in the idea, or belong elsewhere)

- **A temporary HTTPS tunnel to cloud evaluators.** Exposing a sandbox from the home network is a
  security decision for the owner, and local evaluation comes first.
- **LLM-judged UX scores.** At most corroborating, and only once their correlation with scenario
  results is measured.
- **SquadOps proposing its own framework experiments.** Framework self-improvement is deferred; the
  outer loop is the crew's (the owner's direction, 2026-09-28).
- **Confidence numbers on causal claims.** Evidence counts and their records replace them.
- **A project model of its own.** What a Project is, its source and its own checks are Project Lifecycle
  Management's.
- **Evaluating a standalone cycle.** This SIP's unit is a campaign's calibration and its increments, plus reference
  increments and replays. A Project's first standalone cycle is read by Project Lifecycle Management's own checks.

## 6. Phasing

| phase | release | what | verdicts |
|---|---|---|---|
| 0 | 2.1 | #1959 (increment replay) and #1960 (per-increment scorecard): **shipped**, v2.1.0 | none changed |
| 1 | 2.4, committed (the 2.4 plan's D1) | the scenario store and runner, held out; scenarios run per increment, results in the package; Lighthouse, axe and lint per increment with baselines; the intervention ledger's classifications; AOR, the AWE and contribution in the digest | **reporting-only:** no row, gate or prompt changes, and no scenario goal or result reaches a squad role |
| 2 | 2.4, conditional (D4) | §4.5: the proposal sees scenario goals and quality readings. §4.7: the objective's scenario measure, read by row 3. Quality gates where phase 1's data supports a threshold | changed, each with its phase-1 evidence |

**Phase 1's data comes from the measurement window** (the 2.4 plan's D3 and §1.3):
- four campaigns, two per stack, three increments each;
- one deploy, frozen for both lanes (G7);
- the experiment record SIP-0110 §0.12 defines, plus the suite digest and the product revisions;
- a redeploy inside the window ends the series.

**The owner decides phase 2 on the window's record** (D4). It goes ahead only if:
- the scenarios discriminate;
- holding out holds;
- contribution is not the acceptance count by another name;
- each measure phase 2 would gate is stable.

## 7. Verification: how this SIP would know it works

Predictions, each named by its mechanism, to pre-register when phase 1 is built:
1. **The scenarios discriminate.** A scenario fails on a tree known to lack its result and passes
   on one known to have it: the reference scenario's baseline and its accepted increment (#1804).
   One that passes both is not evidence, and is withdrawn.
2. **Holding out holds.** No scenario step appears anywhere the squad or the product can see:
   - in a squad agent's rendered request, read from the authoring envelopes, which reconstruct byte for byte
     (`verify_authoring_envelopes.py`), and from #1756's full prompts where they reach further;
   - in any stored squad task envelope;
   - in a squad agent's container;
   - in a workspace or a product repository.

   In phase 1, no scenario goal or result does either (Project Lifecycle Management's IR-4).
3. **Contribution is not the acceptance count by another name.** Across phase 1's
   campaigns, some accepted increments read `neutral`. If every accepted increment reads
   `contributed`, the suite is too close to the squad's own criteria.
4. **The quality measures are stable.** Each measure's spread on an unchanged tree, re-measured,
   stays inside the tolerance phase 2 would use. A measure that does not is reported and is not
   gated.
5. **The ledger matches the control log.** Every in-interface intervention row has its
   classification, and no classified entry lacks its row.
6. **The evaluation leaves no trace in the product.** After an evaluation, the evaluated tree's identity and the
   cycle's live tree are unchanged, and nothing a scenario wrote reaches a revision or a commit (contract 3).

## 8. The owner's answers (ruled 2026-10-17, the 2.4 plan's D2)

Revision 1 asked five questions. The owner ruled the 2.4 plan's recommendations:
1. **Held out, or visible?** Steps held out, goals visible, as drafted. Goals are shown only to the proposal run, and
   only in phase 2 (§4.1).
2. **Who authors the first suite?** The supervisor drafts it, and the owner approves it. It is frozen and
   content-addressed before the window.
3. **Lighthouse and axe:** added to an image, with the lock files' audit. The ruling named the QA image. A2,
   ruled at acceptance, puts them in the evaluator's image instead (§4.2).
4. **The work classes:** the increment count, the PRD tier, and attended or unattended, declared in the objective
   (§4.6).
5. **Phase 2's placement:** 2.4, conditional on the window's record (D1, D4).

The ruling also renamed the SIP's *outcome* term (§0).

### 8.1 Ruled at acceptance

All four are ruled as recommended: A4 through SIP-0112's Q40, and A1 to A3 at acceptance (the owner, 2026-10-17: "approve A1-A3 as recommended and accept 2406").

| # | question | the ruling |
|---|---|---|
| A1 | **The SIP's own name.** The term is renamed (§0). Does the SIP's name follow, along with the idea's metric names (AOR)? | **Keep "Outcome Evaluation".** Both lanes, the 2.4 plan and Project Lifecycle Management's contracts cite it, and the clash with SIP-0108 was in the records' terms, which are renamed. Renaming it later is a numbered amendment |
| A2 | **Where Lighthouse and axe are installed.** D2 named the QA image | **the evaluator's image,** with the same lock-file audit. The baselines measure the instance the scenarios read, which revision 2 runs outside the squad's containers |
| A3 | **Where the runner runs** | **the sandbox service** (SIP-0102). It already launches least-privilege containers, and it holds the docker socket. It needs the `sandbox` profile on every deploy that evaluates. No compose change is needed. The browser runs in a container the service launches from the evaluator image, and receives a run's steps on its input, never on a mounted path |
| A4 | **Secrets in a start declaration** (SIP-0112's contract 7). The same question as SIP-0112's Q40, so one ruling answers both | **Ruled 2026-10-17** (Q40, the owner: "approve Q40 as recommended"): evaluation-scoped secrets only. The runner resolves only the references a Project declares in `evaluation_environment` and the owner approves per Project. They are test credentials, never production secrets. They are resolved into the disposable copy's environment at start, never written to a file, a log, a record or a squad agent's input, and discarded with the copy (§4.1) |

## 9. Revision history

- **Revision 1 (2026-10-04):** drafted from the owner's idea of the same day, scoped to its
  evaluation half at the owner's agreement ("yes, save the idea and draft the SIP").
- **Revision 2 (2026-10-17), for the owner's acceptance:**
  - **The owner's answers to §8,** ruled as the 2.4 plan's D2.
  - **The term renamed** (§0).
  - **The Spark lane's compatibility review of Project Lifecycle Management** (SIP-0112 §8.6), made design:
    - scenarios declare their own surfaces by kind, and a manifest is optional;
    - the runner runs outside the squad's containers, on a disposable copy of the evaluated tree;
    - scenarios live in a store of their own;
    - phase 1 pins its suite on the campaign at creation;
    - an evaluation record with its own ID;
    - *not applicable* kept apart from `blocked_unverified`;
    - trees named by identity.
  - **Added:**
    - the shared contracts (§4.8);
    - a delivery ledger;
    - prediction 6;
    - the four acceptance questions (A1–A4).
  - **Phasing:** phase 1 committed in 2.4, and phase 2 conditional.
  - **Accepted 2026-10-17** (the owner, 2026-10-17: "approve A1-A3 as recommended and accept 2406"), with A1 to A3 ruled as recommended. Phase 1's parts are placed in 2.4.0 with
    their issues.
  - **After the MacBook lane's review of §4.8** (PR #2406's comment `issuecomment-6244691653`, which found no
    mismatch on this side):
    - contract 5 is named *evaluation references*;
    - *scenario result* is added to §0;
    - *not measured* follows *not applicable*'s rules, and AOR's "every quality baseline held" covers only measures
      that ran;
    - A4 is named as SIP-0112's Q40.
  - **After SIP-0112's acceptance (2026-10-17):**
    - A4 is ruled through Q40;
    - the start declaration's secrets key is `evaluation_environment`;
    - SIP-0112 is cited by number;
    - the shared fixture is #2407.

## 10. Post-acceptance amendments

### 10a. The scenario store as built (2026-10-18, §4.1, §4.7 phase 1, #2413; implementer's record, for the owner)

**What it fixes that §4.1 left open.**
- **Who reads a suite, by scope** (`squadops.auth.models`):
  - `scenarios:read` gives a suite's goals, surfaces and state, never its steps or checks. It's held by
    the owner (`admin`), the supervisor and triage.
  - `scenarios:draft` is the supervisor's (D2) and the owner's.
  - `scenarios:approve` is the owner's alone. It approves a suite, and **reads its full content, steps
    included**, so the owner approves what was drafted.
  - No squad agent's role (`agent`) holds any of them.
- **How steps reach the runner:** in process. The evaluation service in the runtime API reads them from
  the store by suite digest and hands them to the runner over the sandbox's authenticated channel (#2414).
  No route is added for the runner to read them.
- **The boundary in code:** no module under `squadops.agents`, `capabilities`, `prompts` or `execution`
  imports the scenarios' domain, port or store, and no file there names either table, `scenario_suites`
  or `campaign_scenario_suites` (`test_held_out_scenarios_stay_out_of_the_squads_reach.py`).
- **What the boundary doesn't cover: the database.** Every agent's container connects to Postgres as the
  runtime API's own role, so a process holding it could read both tables directly. The route and code
  guards meet "no route a squad agent's identity can read", but not SIP-0112 §8.3 item 1 or IR-4's "any
  squad agent's container". Separation at the database is #2457, and IR-4 waits on it.
- **Surfaces by kind:** `http_endpoint` (a method and a path) and `page` (a path). The name isn't `http`:
  that would read as the same value as unrelated `"http"` literals across the codebase (#380's guard).
- **Steps and checks** are mappings naming an `action` and a `check`. Their vocabulary is the runner's
  (#2414), and a step it can't run is `blocked_unverified`, as §4.1 rules.
- **Content addressing:** a scenario's version is the hash of its canonical content, and a suite's digest
  is the hash of its scenarios' ids and versions. Its name is a label, and the order isn't counted. The
  Postgres store recomputes the digest on every read, and refuses a row whose content no longer hashes to
  its key.
- **The campaign's pin** (§4.7, phase 1) is recorded in SIP-0109 §24bt.
- **The CLI** is `squadops scenarios`:
  - `draft --file` is the supervisor's;
  - `review` (the full content) and `approve` are the owner's;
  - `list` and `show` give goals and surfaces only.

  A suite's file is refused inside any Git working tree, so a held-out suite can't be committed into what the squad
  is built from. Approving a digest approves exactly the content reviewed under it.

**Who ruled it.** The owner accepted §4.1 and §4.7 (2026-10-17). These are the implementer's choices
within them, for the owner's review.

### 10b. The evaluation record and its reference as built (2026-10-18, §4.1, §4.8; contract 5; #2415; implementer's record, for the owner)

- **One record per evaluation run** (`squadops.scenarios.evaluation.EvaluationRecord`, migration 1910),
  with an `evl_` ID. It is built only against the suite it ran: each scenario appears once, at the
  suite's version and goal.
- **Each scenario's outcome keeps applicability apart from the result:**
  - not applicable means no result, and counts in no rate;
  - an applicable scenario has a result, passed, failed or `blocked_unverified`;
  - a blocked result names its reason from §4.1's list, and nothing else names one;
  - a failed result names its first failing step.
- **Trees are named by `FileTree.identity` only.** The table refuses anything but 64 hex characters, so a
  40-character Git commit can't stand in for a tree. **A sandbox revision ID is also 64 hex, so shape
  can't refuse one.** That guarantee is the producer's: the evaluation service (#2414) names the
  evaluated tree by the increment's `FileTree.identity`, never by the revision it ran.
- **The reference lives apart from the results,** in `squadops.scenarios.reference`:
  `OutcomeEvaluationRef`, `parse_reference`, `EvaluationInvalid` and `UnknownSchemaMajor`.
  - It imports only the standard library, and a test holds that.
  - Project history imports that module alone, so no outcome can reach the handoff through it
    (contract 5's phase-1 rule).
  - E.4.3 adds `squadops.projects` and `squadops.cycles` to the held-out guard's squad side, allowing
    that one module.
- **`OutcomeEvaluationRef`'s reader** (`parse_reference`) does three things:
  - it refuses an unknown major version with `UnknownSchemaMajor`, reading none of the reference;
  - it refuses a reference with any field absent, `campaign_id` included, which may be null but never
    absent;
  - it refuses a `campaign_id` that isn't text, so `5` isn't read as `"5"`.

  It holds the shared fixture's four forms (`test_contract5_evaluation_reference.py`), and reads a
  reference with both nullable fields null as nulls. The record yields exactly the fixture's valid
  reference.

### 10c. The scenario runner as built (2026-10-18, §4.1, A3; X-3b; #2414, #2421; implementer's record, for the owner)

- **Where it runs:** `ContainerScenarioRunner`, in the sandbox service (A3). The service answers it at
  `POST /api/v1/evaluations`, and the runtime API calls it through `HttpScenarioRunner`.
- **What one call does:** it takes an evaluated tree, by its `FileTree.identity`, and refuses files that
  hash to anything else. It writes a disposable copy with binaries and executable bits included, and
  starts it.
  - **A Project's own start declaration** (contract 7, read by `declared_start`) is ready at a 2xx from
    its `http` target, or at a connection to its `tcp` port that the app holds. Docker's port proxy
    accepts on the published port as soon as the container starts, before the app binds, and closes
    at once while nothing listens. So a connection counts only if it stays open, or the app speaks
    first. Read live: a bare connect read as ready, and step 1 answered "Server disconnected without
    sending a response".
    - **`command` readiness is `no_runner`, not `no_start_declaration`** (`ReadinessUnsupported`): the
      kind is valid, but its target is a string the contract doesn't define as an argv, so this runner
      doesn't check it.
    - **The reader checks contract 7's schema where it reads it** (`StartUndeclared`,
      `no_start_declaration`). It refuses a string where an argv belongs, a flat `build` list, a working
      directory outside the repository, a missing `timeout_seconds` and an unknown kind. Each would
      otherwise surface as a failed start. The sandbox checks the argvs and directory again with X-3a's
      own rules before running them. `squadops.sandbox` already imports this reader, so the reader can't
      import those rules back. When SIP-0112's E.4.2(b) lands its typed `StartDeclaration`, the runner
      reads that, and the two readers become one.
    - **The declaration's Development Configuration revision** travels with it, and each `TreeEvaluation`
      names the revision that started it (`None` for a blueprint).
  - **A blueprint** starts by its stack's environment contract: install, build, start, and today's
    transport-level readiness (#520/#622).

  It then runs each scenario's steps from the service over loopback. Last, it stops the app and removes
  the copy, whatever happened (§7 prediction 6).
- **The steps and the evaluation secrets** travel in the request and are held for the call. They are
  never written or journaled. The secrets reach only the app's environment (Q40), and every value is
  redacted from the free text the runner returns: the start's detail, the app's own last lines and each
  step's detail. Results, identities and ids are never touched, so a short secret can't rewrite
  `passed` (the MacBook lane's review).
- **An evaluated tree's keys are checked before the copy is written:** absolute, climbing or
  non-normal keys are refused, and nothing runs (contract 3: never the live tree).
- **Scenarios reach the API at its base** (#2421's entry points; #2464):
  - a declared Project at its `http_base` entry point's port and path. On the app network (SIP-0102 §11h)
    that is `http://<the app's name>:<port><path>`, with nothing published; on a host run, with no app
    network, both ports publish to loopback;
  - a blueprint at its stack's `api_prefix` on its app port: `""` for the canonical stack, whose backend
    serves the PRD's paths at the root, and `/api` for Next.js, which serves them as App Router routes.

  So one suite names the PRD's paths (`/runs`, `/runs/{run_id}/join`) on either stack. Read live on
  `cyc_bbedc850e6ff`'s Next.js tree: `GET /runs` reached `/api/runs` and answered 200.
- **Not built yet, on #2421:** resolving only the owner-approved `secret://` references, with `secret not
  available` for the rest. SIP-0102 §11e says where it lands.
- **Found while reading the window's suite live (#2464): the request bodies are not stack-neutral.** The
  PRD leaves the data model to each delivery's interface manifest (its §8). That Next.js tree names the
  run's fields `dateTime` and `meetingLocation`, where the canonical stack's names are `datetime` and
  `location`. A create step with fixed field names therefore fails at step 1 on one of them.
- **So a scenario names a field by its concept** (#2464; `squadops.scenarios.fields`):
  - `@Run:location` appears as a JSON key, as a string value, or as one segment of a dotted JSON path;
  - the scenario's `fields` lists the names a delivery may give each concept, for example
    `Run:location: [meeting_location, location, meetingLocation]`;
  - the evaluation service resolves each concept against the evaluated cycle's own
    `interface_manifest.yaml`, or else that of the accepted cycle it built on, before anything runs;
  - a concept the delivery's manifest declares under none of the names goes under the scenario's first name, and
    the scenario runs. **A manifest's fields are a hint, not a list of what the app holds.** Read live: the §7
    reference increment implemented capacity and stored no manifest of its own, so the one it built on, without
    the field, was all there was to read. Reading an undeclared field as absent hid that job. Sent under its
    first name, a delivery without the feature fails the scenario, as the reading needs;
  - `fields` is in each scenario's content, so in its version, so approving a suite approves its names.
    A scenario without `fields` keeps its content and version byte for byte;
  - **a declared Project reads no manifest** (SIP-0112 §8.3: a sample application's interface manifest is
    never a default, and an external product has none). Its concepts go under the scenario's first name, and
    its endpoints aren't checked, since its surfaces come from its entry points. Only a blueprint delivery's
    own stored `interface_manifest.yaml` is read.
- **Why per delivery, not per stack** (read from the Spark's vault, 2026-10-18, 40 recent completed
  deliveries): the canonical stack's run is `meeting_location` in 26 and `location` in 4. Next.js's is
  snake_case in 5, camelCase in 2 and mixed in 1. Every delivery's manifest names the entity `Run`; only the
  hand-written reference says `RunEvent`.
- **A scenario's `http_endpoint` surfaces are checked against the endpoints the delivery declares,**
  after taking off its stack's API prefix and ignoring parameter names. One the delivery doesn't serve is
  `surface_absent`. In the same 38 manifests, 32 take a join at `/runs/{run_id}/join` and 6 at
  `/runs/{run_id}/participants`, so a `/join` scenario is unverified on those six, not failed. The prefix
  is the stack's, not the manifest's `base_path`, which deliveries set both ways: 16 of the canonical
  stack's say `/api` and serve at the root.
- **A status check may accept several:** `{"check": "status", "in": [400, 422]}`. The PRD says a request is
  "rejected", and each delivery's manifest picks the status: 422 on the canonical stack and 400 on Next.js
  for a validation error, while 404 for an unknown run and 409 for a duplicate hold on both.
- **Read live with one suite on both stacks** (the capacity readings after the first-name fallback):
  - on `cyc_bbedc850e6ff` (Next.js), "a created run reads back" passed, and the capacity scenario failed at
    step 3, since that delivery doesn't hold a run to one place;
  - on `cyc_f6bfb0b88ebd` (the canonical stack), both passed;
  - on `cyc_f479d21e05ac`, which joins at `/participants`, the capacity scenario's `/join` was
    `surface_absent`.
- **The vocabulary** is in `squadops.scenarios.steps`.
  - **Steps:** `http` actions, with saved values threaded into later paths and bodies, and an optional
    `expect_status`.
  - **Checks:** a status, or a JSON path's value, length or contents.
  - **How a scenario ends:** a transport failure, an unexpected status or an unanswerable save fails it
    at that step. An unknown action or check is `blocked_unverified`, `no_runner`. A browser's action is
    `browser_unavailable` until the evaluator's image runs pages (A2).
- **A start that fails** runs no scenario. It carries why: the setup step that exited, or the readiness
  that timed out, with the app's own last lines.
- **Read live on the Spark's Docker** with the shared fixture's tree and its recorded declaration:
  - the tree hashed to the recorded identity;
  - three scenarios passed, the admin route among them, with the secret in no result;
  - readiness at an undeclared path failed the start;
  - the same declaration with `tcp` readiness started and passed, and both runs name revision 1;
  - no copy or container was left.
- **§7 prediction 1, read live on the Spark (2026-10-18):** the held-out capacity scenario (a run with
  one place refuses a second runner, and its list keeps the first). Each tree was started by its stack's
  environment contract from the vault's delivered tree:

  | tree | identity | result |
  |---|---|---|
  | the reference baseline `cyc_7a4b7a6fbf0e` | `dcff44b8…`, its pinned `baseline_tree` | **failed** at step 3: the second join answered 200, not 409 |
  | the reference increment `cyc_20246018f2b8` | `4692c159…` | **passed** |

  The baseline's identity equalling its pin shows the delivered tree's `FileTree.identity` is the identity
  SIP-0109 records for an accepted tree.
- **An authoring rule the run settled:** a scenario's HTTP surfaces name the backend's own paths
  (`/runs`). A manifest's `api.base_path` (`/api`) is the frontend's dev-proxy prefix, and the backend
  answers it 404.
- **The evaluation service** (`squadops.scenarios.evaluate.evaluate_cycle`).
  - **What it does:** it takes the cycle's whole app by SIP-0109's own selection
    (`increment_tree.evaluated_tree_refs`), names it by `FileTree.identity`, and runs the pinned,
    approved suite's applicable scenarios in the runner. It then writes the `EvaluationRecord`.
  - **Applicability:** a scenario whose surface kinds the Project doesn't serve is not applicable and
    never runs.
  - **When nothing can run:** no runner, a failed start, or an undeclared start make every applicable
    scenario `blocked_unverified` with that reason.
  - **Read live on the Spark**, on both reference cycles, with a real vault, a real runner and a suite
    of two scenarios:
    - **the capacity scenario** failed on the baseline at step 3 and passed on the increment;
    - **the page scenario** was `blocked_unverified`, `browser_unavailable`, on both;
    - **prediction 6:** each tree's identity was the same after its evaluation;
    - **prediction 2:** the steps' unique marker was in no file of the vault, no line of the
      deployment database's 337 MB dump, no agent container and not the runtime API's. The run's suite
      was in memory, so the deployed store's side of prediction 2 is read again in the window.
  - **The selection is the release capture's:** `evaluated_tree_refs` gave the capture's identity for
    both trees.
- **The hook at a cycle's end** (`squadops.scenarios.campaign_cycles`, 2026-10-18). Each campaign cycle is
  evaluated against its campaign's pinned suite, and the record is written. Reporting-only: nothing that
  decides the campaign reads it.
  - **When:** in the campaign's hearing of the ending (`CampaignProgress`), after its already-decided check
    and before the decision. So the evaluation has the box between cycles, not beside the next one, and the
    periodic re-hearing never evaluates a cycle it has already decided.
  - **Which endings:** only one that reached its build (`assessed`). An increment rejected at its gate built
    nothing, so it would only re-read the tree it was built on.
  - **What is evaluated:** the cycle's whole app, by SIP-0109's selection. A cycle that delivered nothing
    has no record.
  - **Its previous tree:** the identity the campaign promoted for the accepted cycle this one built on, read
    from the control log's applied promotion. A calibration builds on nothing.
  - **Once per cycle and suite,** so a cycle heard again after a restart (§12a) isn't evaluated twice. A
    failure is logged and never stops the decision.
  - **A delivery's manifest that can't be read** is read as none, with a warning, so the record is still
    written: its concepts go under their first names and its endpoints aren't checked. Found when the hook
    met #2467's manifest read: a malformed manifest had raised out of the evaluation, leaving no record.
  - **A Project that isn't a blueprint** has its applicable scenarios recorded `blocked_unverified`,
    `no_start_declaration`. The hook doesn't read its Development Configuration's start declaration
    (SIP-0112 E.4.2) yet.
  - **The runner** is the sandbox service's, through `create_scenario_runner` on the runtime API's one
    sandbox-client binding (#2451). With `none`, each record says `no_runner`.
- **Still to build for #2414:** the browser runner in the evaluator's image (A2), for `page` surfaces, and
  the declared start at the hook once E.4.2 records it.

### 10d. The intervention ledger as built (2026-10-18, §4.3, §7 prediction 5; #2417; implementer's record, for the owner)

- **A projection of SIP-0109's control log, never a second record of it** (`squadops.outcomes.ledger`).
  An applied row is an intervention in three cases:
  - a `rule` that returns or rejects a proposal (an approval is the gate as designed);
  - an `escalation_closed` whose state is `resolved` (an escalated plan gate a person decided);
  - a `pause`, `resume`, `abort`, `classify` or `escalation_answered` by anyone but the system's own
    roles (`executor`, `sweep`, `launcher`, `completion`). A limit's pause is the campaign running,
    not an intervention.

  SIP-0110's re-binding joins when #2179 adds its row.
- **Outcome Evaluation's record holds only the classifications** (migration 1920), keyed by the row:
  the reason and severity from §4.3's lists, "could the squad have resolved it?" as the supervisor's
  labelled opinion, and a note. A later classification of the same row revises it. A declared entry
  records an action outside the interface.
- **Prediction 5 is read in every ledger read:** `unclassified` names the intervention rows not yet
  classified, and `orphaned` names the classifications whose row isn't one of this campaign's
  interventions. `matches_the_control_log` is true only when both are empty.
- **`/api/v1/intervention-ledgers/{campaign_id}`:**
  - **reading:** `campaigns:read`;
  - **classifying and declaring:** `campaigns:supervise`, the supervisor's seat. A classification
    must name one of the campaign's own intervention rows.
- **Constants, not enums.** Several of the words are other vocabularies' too (`implementation` is a
  workload, `recovery` a prompt mode), and #380's guard reads every such literal as an enum's shadow.

### 10e. Contribution, per increment, as built (2026-10-19, §4.4; #2418; implementer's record, for the owner)

- **The reading** (`squadops.outcomes.contribution`) compares two evaluation records of one suite: the
  increment's tree against the accepted tree it was built on. Records of different suites, or a previous
  record of another tree, are refused (`NotComparable`), so a reading never describes a change that didn't
  happen. A calibration compares with nothing: what passes on it reads as new.
- **What takes no part:** a scenario not applicable, and one that is `surface_absent` on both trees, since
  the product never had that surface. A surface that disappears is different: it passed, and now it's
  absent. That reads `unverified`.
- **Two choices §4.4 leaves open:**
  - **The precedence is regressed, then unverified, then contributed, then neutral.** So a contribution is
    never claimed while a scenario that takes part was blocked: the reading couldn't check it.
  - **A scenario that passed and is now blocked is `unverified`, not `regressed`.** §4.4 says a regression
    *fails*.
- **Each reading names its scenarios by id:** newly passing, regressed, unverified, and those taking no part.
- **The digest's wiring, as built** (2026-10-18, #2418; `squadops.outcomes.campaign_package`). The
  campaign's evidence package (version 4) carries an `outcomes` section, read from the scenario store at its
  materialization, and the digest renders it under **Outcomes**. For each cycle, from its latest record
  against the pinned suite:
  - its scenarios' results, by id;
  - its contribution, read against the record of the tree it built on, or *not read* with why;
  - its quality readings, and what moved against that tree and against the calibration's reading.

  **Never a scenario's goal, steps or checks.** The package is a project-level vault artifact, so the readings
  stay out of every squad task, and a guard holds that (`test_held_out_packages.py`): every vault listing in
  `src/` and `adapters/` names a cycle or a run, or is one of three project-level readers, each named with
  why no squad role reads it (the agent role holds only `agents:write`). A section that can't be read is
  recorded in the package with why, and the package is still written.
- **The work class, as built** (2026-10-18, #2418). **Ruled by the owner, 2026-10-18:** the shape proposed
  on #2418, approved as proposed.
  - **`CampaignObjective.work_class`** has two fields: `prd_tier` (`core`, `tier-1`, `tier-2` or `tier-3`)
    and `attendance` (`attended` or `unattended`). It's declared, never inferred.
  - **The increment count is the objective's `target_accepted_increments`,** one declaration, not two.
  - **Required of every new campaign,** as the target is. The create route refuses a campaign without one,
    and the API refuses a word outside the vocabulary. It's `None` only on a campaign stored before it, whose
    creation still replays, since an undeclared class stays out of the creation's hash, as an undeclared
    stack does.
  - **Where it's declared:** in the campaign definition file's `objective`, which `squadops campaigns create`
    sends as it sends the rest. #2418's proposal named CLI flags, but they would be a second source beside the
    file the CLI reads everything else from. The file is the one place, and its path and sha256 are already
    on the creation row (#1954).
  - **The digest's header names it.** Nothing that decides a campaign reads it.
- **The safety guarantees, as built** (2026-10-19, #2418; `squadops.campaigns.safety_guarantees`). **Ruled by
  the owner, 2026-10-19:** AOR's *every safety guarantee intact* means the 2.0 set's seven
  (`docs/plans/2-0-0-preregistration.md` §3), each read from the package's control log and cycle records.
  - **Each reads held, violated (with the rows that break it), or not read (with why).** A guarantee that
    can't be read is never counted as held, so *intact* is true only when all seven held.
  - **What each is read from:**
    - *no build without an approving ruling:* each non-calibration cycle with an implementation run, against
      the applied approving rulings on the proposal its launch names, at its block's version for a retry or
      a repair, bound to the tree the campaign had accepted when it was ruled;
    - *no stale or conflicting ruling honoured:* each applied ruling against the latest version then
      submitted, by content hash, and no version ruled two ways;
    - *no ruling lost:* at close, every submitted version ruled, superseded, ended by its cycle's decision,
      or ended by an abort;
    - *no duplicate launch:* one cycle per launch intent;
    - *no partial promotion:* every promotion with its tree's reference and a bundle per frozen criterion;
    - *no launch beside a crew model:* no launch while the supervisor held the box. The box's model check
      holds a launch back before it is marked, but a run start that waited on it shows only in the
      runtime's log, which the package doesn't carry, and the reading says so;
    - *the package complete at close:* every launched cycle in it, each readable, with its outcome section.
  - **The digest** renders the seven under **Safety guarantees**.
  - **Read live, over the Spark's 51 stored packages,** before the tests were written: 48 intact, the 2.0
    set's two among them (as its hand reading found), and 3 not read. That read corrected two readings:
    - three campaigns from 2026-10-02 and -03 promoted before #1887 recorded a tree's reference. They read
      *not read*, not violated;
    - a campaign aborted while a version awaited its ruling had read as a lost ruling. An abort ends it.
- **AOR and the AWE, as built** (2026-10-19, #2418; `squadops.outcomes.aor`).
  - **The package carries the intervention ledger** (`interventions`, from `campaign_interventions`): each
    intervention row with its classification's severity, each action declared outside the interface, and
    the rows not yet classified.
  - **Each campaign's four inputs** read `True`, `False`, or `None` when they can't be read:
    - reached its objective: the campaign ended in `success`;
    - no intervention above `advisory`. An unclassified intervention can't be read;
    - every quality baseline held: `None` in phase 1, until prediction 4's tolerance (§10f);
    - every safety guarantee intact: the seven above.

    A campaign with any input unread is never counted reliable.
  - **The digest** shows them under **Autonomy**, with the campaign's standing toward its class's AOR.
  - **The AWE** (`work_envelope`, and `scripts/dev/aor_reading.py` over the deploy's stored packages):
    - AOR per declared work class, never pooled;
    - a class has a rate only once every campaign in it is read;
    - each unread campaign is named with the inputs that kept it from being read;
    - no composite across classes.
  - **Read live over the Spark's 51 stored packages:** every campaign is *none declared* (all predate the
    class), 25 didn't reach their objective, and 26 are unread on the ledger (no earlier package carries it)
    and on baselines. So there's no rate, which is what phase 1 can honestly say before the window.
- **Still to read on #2418,** both in the window: prediction 3 (some accepted increments read `neutral`),
  and "every quality baseline held", once prediction 4's tolerance is read (§10f).

**Who ruled it.** The owner accepted §4.4 (2026-10-17). The precedence and the blocked-now reading are the
implementer's, for the owner's review.

### 10f. Lighthouse and axe, as built (2026-10-18, §4.2, A2, A3; #2416; implementer's record, for the owner)

- **Where they run.** The scenario runner launches the evaluator's image (`infra/evaluator`) on the sandbox's
  app network, beside the started app.
  - It has caps dropped and no new privileges. It gets none of the app's environment and no mounted path.
  - Its request (a base URL and the pages) arrives on its standard input, as A3 rules.
  - It reaches the app by IP, resolved from the app's name. Read live on the Spark: Vite's preview server
    answers a name it doesn't know with 403.
  - Off the app network, on a host run, the reading is *not measured* (`no_app_network`).
- **When.** After the app is ready, and before any scenario runs, so every tree is measured in the same state.
  A reading that can't be taken never stops the scenarios.
- **What serves the pages** (the environment contract's `ui_port` and `ui_serve`):
  - **Next.js:** `next start` serves the pages itself, on the app port.
  - **The canonical stack:** its backend serves only its API. So the build its setup already makes is served
    beside uvicorn by Vite's preview (`vite preview frontend`), whose proxy reaches the same backend as the
    dev server's does. The instance the scenarios read is the one measured.
- **Which pages:**
  - **A blueprint delivery:** its own manifest's routes that load as they are; a route with a parameter
    (`/runs/:id`) needs data no measure creates.
  - **A declared Project:** its `ui_base` entry point.
  - **None at all:** a Project with no `ui_base` is *not applicable*. A blueprint with no readable manifest
    is *not measured* (`no_declared_page`).
- **The reading** (`squadops.scenarios.quality`) is in each evaluation's record (`quality`, migration 1930):
  - *measured*, with each page's three Lighthouse scores and axe's violations by impact, or the error that
    kept the page from being scored. A page that answered an error, or painted nothing (Lighthouse's
    `NO_FCP`), is never scored;
  - *not applicable*;
  - or *not measured*, with why: `no_runner`, `start_failed`, `no_start_declaration`, `no_declared_page`,
    `no_app_network`, `ui_not_ready`, `evaluator_absent` or `evaluator_failed`.

  A record written before this has none. That is never read as measured, nor as not measured.
- **Each measure's version** is the evaluator's tag (`EVALUATOR_IMAGE`), which a guard pins to its sources'
  digest. A changed driver or package needs a new tag, so the window never compares two measures as one.
- **Read live on the Spark** (2026-10-18), on the reference increment's delivered tree `cyc_20246018f2b8`,
  on an internal network:
  - **`/` and `/runs/new`:**
    - Lighthouse: performance 0.93 and 0.94, accessibility 0.96, best practices 0.78;
    - axe: 2 moderate violations each;
    - three re-measures were identical, a first read of §7 prediction 4 on a quiet box;
  - **`/runs` and `/create`, which this delivery doesn't declare,** painted nothing, and read as errors.
- **Lint, as built** (2026-10-18, #2416). #1937's reading of the evaluated tree as delivered, by its own rule
  sets, in each evaluation's record (`lint`, migration 1940):
  - **Where:** in the evaluator's image with no network. It carries ruff and ESLint at #1937's pinned
    versions, and a guard keeps them equal to the qa image's, so the two readings are one measure.
  - **What it's sent:** the files, #1937's ruff command, and its ESLint runner and config, on its input. So
    the rules have one source, and the evaluator's tag covers them.
  - **When:** whatever the start did, since a tree that won't install is still read.
  - **Off the scaffold stacks:** a declared Project's lint is *not measured* (`not_a_scaffold_stack`), and
    its own linter is never read in its place.
  - **Found while building it (#2478):** #1937's ESLint config named no file patterns, so ESLint linted no
    `.jsx` file, while the reading counted them as linted. On the reference increment it read 3 of 11 JS
    files, and never the React UI. The runner now names its patterns, and all 11 are read. The qa path
    reads the same once its image is rebuilt.
- **Each measure's delta, as built** (2026-10-18, #2416; `squadops.outcomes.quality_deltas`). It reads two
  evaluation records, as contribution does, and is reported beside it without changing it (§4.4).
  - **What it compares the increment with:** the tree it was built on (`previous`), or the campaign's
    baseline, the calibration's reading in the same campaign (`baseline`). Any other record is refused
    (`NotComparable`).
  - **Like with like only.** Lighthouse and axe are compared per page that both trees declare and score,
    and lint by rule, when both trees were read by the same tools with none unavailable. Everything else is
    named under `not_compared` with why, never read as a delta of zero:
    - a page on one tree only;
    - a page in error;
    - a measure not measured or not applicable on either side;
    - a different evaluator tag.
  - **What a baseline *held* means is not decided here** (§4.6 needs it for AOR). It needs a tolerance, and
    the tolerance is each measure's spread on an unchanged tree, prediction 4's reading in the window. Until
    then the digest reports the deltas, and names no measure held.
- **Not built yet, on #2416:** prediction 4's spread, recorded across the window, and from it the
  tolerance a *held* baseline is read with.
- **Choices for the owner's review:**
  - measuring before the scenarios;
  - Vite's preview as the canonical stack's page server, a production build behind the scaffold's own proxy;
  - each delivery's own routes as its pages. Deltas then compare only the pages both trees declare.

### 10g. The database boundary, as built (2026-10-19, §8.3 item 1, IR-4; #2457; decided by the supervisor under the owner's grant of 2026-10-19)

**What §10a left open:** every agent's container held the runtime API's own database credential (the
`db_password` secret and `SQUADOPS__DB__URL`). So a process in one could read `scenario_suites` directly, past
the routes and the code guards.

**What #2457 proposed, and what was built instead.** It proposed an agents' role with grants on what they use,
and none on the held-out tables. **No agent uses any table, so agents get no credential at all.**
- **In the code:** no module outside the runtime API reads `config.db`.
- **On the live deploy:** no agent container held a connection on 2026-10-19. The connections came from the
  runtime API, Prefect's server, Keycloak and LangFuse only.
- **From the MacBook lane:** no SIP-0112 table is read or written by an agent. A source-backed task's view of
  the product arrives in its envelope.

So there is no grant to keep current, and a table added later is out of an agent's reach by construction.

**What changed:**
- **The config:** `AppConfig.db` is optional. An agent declares none.
  - `AppConfig.database()` requires it, by name, where a pool is made: the runtime API's startup, its
    migrations and its registry, `record_deploy`, and `campaign_binding_replay`.
  - The runtime API refuses to start without one, before any pool is made.
- **Compose:** the eight agent services lose `db_password` and `SQUADOPS__DB__URL`.
- **The guard:** `test_held_out_scenarios_stay_out_of_the_squads_reach.py` refuses an agent service that holds
  either. Its paired control is the runtime API, which holds both.
- **The loaded check:** row `2457`, run in an agent's container.

**Not covered here: the identity provider's credentials.** Found alongside: every service, the agents included,
mounts Keycloak's admin password and database DSN, which no process reads. That is #2498, fixed before SIP-0112's
brownfield demonstration.

### 10h. The runner's `where` check (2026-10-19, §4.1; #2464; the supervisor, under the owner's grant of 2026-10-19)

**Why:** the independent review of the window's first suite found a core outcome no scenario could check: a created
run appears in the list (the `group_run` PRD's §2 item 2, §5.1, §5.2). The list holds the suite's other runs, in
an order the scenario can't know. `0.title` needs a known order, and `contains` compares whole elements, which
carry fields a scenario can't know.

**What was added:** a json check, `where`. Some element of the list at `path` has every field it names, each equal.
- Its keys may be concepts, resolved per delivery like any other (#2467).
- An element without a named field doesn't match.
- A body that isn't a list matches nothing.
- A `where` that names no field is a check the runner can't read: `blocked_unverified`, `no_runner`. An empty
  condition would otherwise hold vacuously.

### 10i. A scenario's entity resolves on the entities the delivery names itself (2026-10-20, §4.1; #2464; the supervisor, under the owner's grant of 2026-10-19)

**What was wrong:** §10c resolves each concept (`Run:location`) against the delivery's own manifest, by its entity name.
A delivery names its entities itself. The 2.4 Next.js shakeout's round 7 named its run `RunEvent`, beside a
`RunSummary`. So `Run:location` found no entity, and went out under the scenario's first name, `meeting_location`, to
an app that declares `meetingLocation`.
- **Every create was refused.**
- **On the calibration and on the first increment,** 12 applicable scenarios failed at step 1 in 0.01 s, each with 1
  passed and 12 blocked as `surface_absent`.
- **The app was up.** Lighthouse and axe measured its pages in the same evaluation.

**What changed:** an entity the delivery doesn't name is read from the delivery's entities whose names contain it, and
failing those, from every entity it declares. The first of the scenario's names found there is sent. A delivery that
names the entity exactly resolves as before.

**Evidence:**
- Re-resolved against round 7's stored suite and delivered manifest, `Run:location` now goes out as `meetingLocation`
  in all 25 scenarios.
- `test_a_concept_resolves_on_the_entity_the_delivery_named_itself` covers four namings: `RunEvent` as round 7 had it,
  an exact entity winning, an unrelated name, and none declared.
- The wiring test enters at `evaluate_cycle`, now with the reference manifest's own `RunEvent` as well as `Run`. Before,
  it renamed the reference to `Run`, on the premise that every delivered manifest says `Run`, which round 7 disproved.
- With the lookup back to the exact name only, both fail.

### 10j. Lighthouse and axe on a seeded instance, parameterised pages included (proposed 2026-10-20, §4.2, §10f; #2562; queued for after the window by the owner)

**Status: proposed, not built.** The owner, 2026-10-20, answering the proposal to draft it: "yes, draft it and queue it
for after the window."

**The design review is the supervisor's** (the owner, 2026-10-20: "Approve your recommendations"). It happens on #2562,
after the window and before any of it is built, with a fresh reviewer that saw none of the drafting. D4 and every quality
gate stay the owner's. The answers the review starts from, the supervisor's recommendation the owner approved:
- accept the second instance if it adds two minutes or less per evaluation, measured when built;
- seed a run at its capacity as well;
- keep both readings for one series;
- use route rendering's mapping (it is in `src/` already, carries #2084's fix, and reads an id from its create
  response);
- write the window's seeded re-measures as records of their own, so the deltas read them.
The window runs on §10f's reading as it stands. Its deploy is frozen (G7), and a measure changed mid-series is a
different measure.

**What's wrong with §10f's reading.** Lighthouse and axe score a blueprint delivery's declared routes that load as
they are, on the instance the scenarios read, before any scenario writes to it. For `group_run` that is `/` and
`/runs/new`, on an empty app.
- **A route with a parameter is never measured** (`/runs/:id`, "needs data no measure creates").
- **The list is only ever measured empty.**
- **The evidence:** the 2.4 FastAPI shakeout (`cmp_41d4a7185a3a`, on `dep_19dfa94c0a0a`) read identical Lighthouse
  and axe scores on all three of its trees:
  - the calibration `cyc_7f3af6920b55`;
  - capacity `cyc_54a601cec50b`, whose indicator is on `/runs/:id`;
  - sorting `cyc_7280393ca6b9`, which shows only with data.

  The scores were performance 0.93 and 0.94, accessibility 0.96, best practices 0.78, and axe 2 moderate, on both
  pages. Only lint moved: +35 findings, then +8.
- **What follows for the window:**
  - **Every increment's delta reads zero.** Prediction 4 re-measures one unchanged tree, so it reads the same with or
    without a seed. What the empty reading costs is the deltas: a page the increment changed is never one that was
    measured.
  - §4.2's caution ("one that does not track scenario success loses its weight") would then retire Lighthouse and axe
    from phase 2 without their ever having seen an increment.

**What is proposed: a second, seeded reading beside §10f's.**
- **A fixed seed, written through the delivery's own API.**
  - **The file:** one per Project, starting with `examples/03_group_run/quality_seed.json`. It has the shape the
    release screenshots' seed already has: create endpoints, field aliases, records, and a member action that joins
    participants.
  - **The mapping onto the delivery's own `interface_manifest.yaml`** is one of two that exist today. The review
    chooses which the seeded reading uses (item 4), and the chosen one moves into `src/squadops/scenarios/`, shared by
    whatever else uses it:
    - **The release screenshots'** (`plan_seed`, `scripts/dev/capture_delivered_app.py`): the seed's create endpoints
      and field aliases mapped onto the manifest, under the API's base (#1730's `_under_base`). It takes the id it
      photographs from the first row a list endpoint returns.
    - **Route rendering's** (SIP-0109 §8.3; `increment_tree.route_seeds`, with #2084's written-prefix fix,
      `src/squadops/capabilities/handlers/route_rendering.py`). It brings a parameterised route into being with the
      create probe's request, and reads the id from the create response. It runs in the squad's qa container, and
      this measure outside it.
  - **Its own file.** The screenshots' seed may change for a better picture. This one is part of the measure, so its
    sha256 is part of the measure's version.
- **On its own disposable instance.** **This changes §4.2 and §10f,** which measure "on the same evaluated instance the
  scenarios read". The review rules on the change.
  - The same pinned tree is started a second time in a disposable copy, as a blueprint starts: by its stack's
    environment contract (§10c). It is seeded, measured, and discarded.
  - **The sandbox's runner changes:** it starts the tree twice, and seeds before it measures. The sandbox's contract
    3 doesn't change.
  - **The scenarios and §10f's reading are untouched.** They still read a fresh, empty instance. So no outcome
    changes, and every reading taken before this stays comparable.
  - **Why not measure after the scenarios, on their instance:** what the scenarios write depends on which of them
    pass, so the state would differ per tree.
- **Every declared page, parameterised routes included.**
  - Each parameter is filled with the id of the first record the seed created, in whichever form the delivery writes
    it: `:id`, `{id}` or `[id]` (the forms `measurable_pages` already recognises). Where the id is read from is the
    chosen mapping's rule (item 4).
  - A route whose parameter the seed can't fill is listed with why (`no_seed_value`). The rest are still measured.
- **Where it doesn't apply:**
  - a blueprint whose Project has no seed file: *not measured*, `no_seed`;
  - a declared Project (SIP-0112): *not applicable*. Its `ui_base` entry point keeps §10f's reading only.
- **New reasons for *not measured*,** each a record that the measure didn't run, never evidence and never a baseline
  held (§4.2):
  - `seed_refused`: the delivery's interface can't take the seed, because no create endpoint is declared, or a field
    it requires has no value;
  - `seed_failed`: the app answered a seed request with an error. The request and the status are kept.
- **Its version** is the evaluator's tag and the seed's sha256, together. Deltas compare seeded with seeded only, at
  one version (§10f's like-with-like rule).
- **Recorded in its own column** (`quality_seeded`, an additive migration). Nothing that reads `quality` today
  changes, and a record written before it has none. That is never read as measured, nor as not measured.
- **Reporting-only, as §10f is.** No row, gate or prompt reads it. A gate on either reading waits for phase 2's rule
  (§4.2, §6).

**Re-measuring the window's trees.** After the window, on the deploy that builds this, every tree the window evaluated
is re-measured with the seeded reading: each campaign's calibration and each increment. No campaign is re-run.
- **Where the readings land is the review's** (item 5). `remeasure_quality.py` writes nothing today: no evaluation
  record and no store row. But the deltas (§4.2, §10f; `quality_deltas`) read two evaluation records. So the seeded
  readings need a record to land in, or the deltas need a reader that takes re-measures.
- **A request to the owner, not a decision:** D4 might wait for both readings. When D4 rules is the owner's call.

**Predictions, pre-registered for its reading:**

| # | prediction | falsified by |
|---|---|---|
| S1 | the seeded reading is as stable as prediction 4's bounds on an unchanged tree: axe, accessibility and best practices spread 0; performance at most 0.05; three re-measures per tree | a measure beyond its bound on any tree. It is reported, and phase 2 may not gate on it |
| S2 | it sees the increments: across the window's pairs, at least one measure differs on at least one page whose route the increment changed, such as `/runs/:id` for capacity | no difference on any changed page in any pair. Then Lighthouse and axe don't track this app's increments even seeded, and §4.2's weight rule applies to them on that evidence |

**Boundaries:**
- **A declared Project** (SIP-0112) keeps its `ui_base` entry point (§10f). A seed for it would be its own
  declaration's, which is Project Lifecycle Management's. Nothing is asked of SIP-0112.
- **The sandbox's contract 3** doesn't change, so no G4 review is needed. Its runner does (above).
- **The held-out suite:** the seed is public, in the repository, and written without reading the suite. No scenario
  step is in it, and prediction 2's sweep is unaffected.
- **The release capture** keeps its own seed file. It shares the mapping if the review chooses the screenshots' one.

**What the design review settles:**
1. **The second instance's cost:** one more start, seed and measure per evaluation. It is measured when built, and the
   review sees the figure before it lands in a series.
2. **What state the seed reaches:**
   - three runs and three participants on the first, as the screenshots have;
   - or also a run at its capacity, so the full state of a capacity indicator is in the reading, when a delivery has
     one.
3. **Whether the seeded reading should replace §10f's** after one series of both. The proposal keeps both, because
   §10f's reading is what every earlier record has.
4. **Which mapping:** the screenshots' or route rendering's (above). That settles the base-path rule, where an id is
   read from, and what moves into `src/`.
5. **Where the window trees' seeded readings land,** and how their deltas are computed (above).

### 10k. The browser runner and page scenarios (proposed 2026-10-20, §4.1, A2, A3; #2564, split from #2414; queued for after the window by the owner)

**Status: proposed, not built.** The owner, 2026-10-20, answering the proposal to draft the browser steps as §10j's
companion: "yes, draft it and queue it for after the window." These are the same words as §10j's answer, given to its
own question.

**The design review is the supervisor's** (the owner, 2026-10-20: "Approve your recommendations"). It happens on #2564,
after the window and before any of it is built, with a fresh reviewer that saw none of the drafting. D4 and every quality
gate stay the owner's. The answers the review starts from, the supervisor's recommendation the owner approved:
- find by role and names only;
- read a control not found as `surface_absent`, but report each delivery's not-found rate beside its results, so it
  can't hide a job (§10c's finding);
- set the wait bounds from measurement;
- revision 4 gives page scenarios for capacity's indicator, the list's order, and joining from the page;
- keep a failure's evidence with the evaluation record for the line, readable from the owner's console and CLI only;
- report every rate across revisions with its count;
- the sandbox's runner coordinates a mixed scenario.

This is the part of phase 1's runner §10c names as still to build: "the browser runner in the evaluator's image (A2),
for `page` surfaces". It moves from #2414 to #2564, and #2414 keeps the declared start at the hook (E.4.2). The window
runs without it:
- its suite (revision 3) has no page scenario;
- the suite is frozen (D2), and so is the deploy (G7).

**The driver is decided; the rest is for the design review.** The owner passed on a review the same day, whose decision
reads: "Adopt Claude's recommendation to implement browser scenario evaluation using the existing Puppeteer dependency
rather than introducing Playwright at this stage." The review also asked for the following, each folded in below:
- evidence captured with every result;
- the driver kept behind an adapter;
- scenarios that measure completed user outcomes, not interactions;
- comparability that survives a suite revision.

**What's missing.** §4.1 names browser pages as a surface kind, and A2 and A3 put the browser in the evaluator's image,
receiving a run's steps on its input. The vocabulary reserves `visit`, `click`, `fill`, `page` and `browser`, but each is
`blocked_unverified`, `browser_unavailable` (`squadops.scenarios.steps`).
- **So nothing independent checks what a user sees,** such as capacity's "2 / 5 joined", or the list's order on the
  page.
- **Only the squad's own tests check it,** written by the qa role that the held-out suite exists to stand apart from
  (§2).

**What is proposed.**
- **Browser steps, in the suite's own vocabulary,** beside `http`, and mixed freely in one scenario: a scenario can
  create its run over HTTP, join it through the page, and check what the page shows. The table's values are
  illustrations, now public. Revision 4's steps take no value from them: they are written apart and held out.
- **Where a mixed scenario runs** (review item 7). HTTP steps run in Python in the sandbox service
  (`squadops.scenarios.steps`). The browser runs in the evaluator's Node container (`infra/evaluator/driver.mjs`),
  which takes its request on its input.
  - **Proposed:** the sandbox's runner keeps the scenario. It runs the HTTP steps, and hands each run of browser steps
    to the evaluator with the values saved so far, receiving the values the browser steps save. So each action kind
    has one implementation.
  - **The alternative:** port the HTTP vocabulary to Node, and run the whole scenario in the evaluator.

| step or check | what it does |
|---|---|
| `{"action": "visit", "path": "/runs/{run_id}"}` | loads a path under the declared UI base, with saved values threaded in as for `http` |
| `{"action": "fill", "target": {"role": "textbox", "names": ["Name", "Your name"]}, "value": "Ada"}` | types into the first control found |
| `{"action": "click", "target": {"role": "button", "names": ["Join", "Join run"]}}` | clicks it, then waits for the page to settle |
| `{"check": "text", "step": 4, "pattern": "2\\s*/\\s*5"}` | the page after that step shows text matching the pattern |
| `{"check": "count", "step": 4, "target": {"role": "listitem"}, "equals": 2}` | so many elements match |
| `{"check": "order", "step": 4, "target": {"role": "listitem"}, "patterns": ["Nov", "Dec"]}` | elements matching each pattern appear in this order |
| `{"check": "absent", "step": 4, "pattern": "error\|went wrong"}` | the page after that step shows no text matching the pattern: a failure condition the scenario names |

- **Elements are found the way a user finds them:** by role, accessible name and visible text.
  - A step names its candidate names, as a scenario names its fields' candidates (§10i), and the first one found is
    used, case-insensitively.
  - **Never by the delivery's test ids.** §4.1 rules a Project's manifest never a scenario's source, and a test id is
    the squad's own naming. A step that finds controls by accessible name also reads what axe measures, so an
    unlabelled control is visible to both.
- **Outcomes, not interactions.** A page scenario completes a user's job and checks what it left behind. For example:
  create a run, join it from its page, and then, on a fresh load of the page or over HTTP, read the joined count back.
  - A scenario whose checks only say that a page rendered, or that a control could be clicked, isn't one. That is
    route rendering's job (SIP-0109 §8.3).
  - **Each scenario states:**
    - its preconditions, as its own setup steps, held out with the rest, so every run starts from the same known
      state;
    - its user actions;
    - the outcomes it expects;
    - the failure conditions it rules out (`absent`);
    - the evidence it keeps (below).
  - **Where its criteria come from:** the campaign's pinned suite is its outcome contract (§10a). It is written and
    approved outside the squad before the campaign starts (§4.1), never after an implementation by the role that built
    it.
- **When a step can't act:**
  - a control none of the step's names finds is `blocked_unverified`, `surface_absent`, never failed. It is the
    page's version of an endpoint the delivery doesn't declare;
  - a control that is found, whose action leaves the page without what the check reads, **fails** the scenario at that
    check;
  - every wait is bounded. A wait that runs out fails at its step, naming what it waited for.
- **Each scenario gets a fresh browser context,** with no cookies or storage carried from the one before, on the
  instance the scenarios share as today. Each sets up its own data in its own steps (§4.1). §10j's seed is not used.
- **The driver** is Puppeteer, which the evaluator's image already pins (`puppeteer-core`) for Lighthouse and axe,
  with the image's Chromium. It sits behind a small driver interface inside the evaluator: load a path, find by role
  and name, fill, click, read text, capture evidence. So a change of driver changes one module and the image's tag,
  and nothing in the vocabulary or the runner.
  - **No second driver or browser bundle in an audited image.** Steps are the suite's vocabulary and the runner
    executes them, so the driver is the runner's implementation.
  - **Playwright** is reconsidered only on a measured limitation: flake that B2 reads, waits that need its
    auto-waiting, or a browser a product needs that Chromium isn't. That would be a new evaluator tag, so no two
    readings mix drivers.
- **Evidence with every result.**
  - **Every scenario:** each step's timing.
  - **A failed or blocked step:** a screenshot of the page, the accessibility tree around the target, the page's
    console errors and its failed requests.
  - **Where it's kept:** with the evaluation record, in the scenario store's own tables behind its port (§4.1), never
    in the artifact vault, where squad tasks' inputs come from.
- **Held out as the HTTP steps are, evidence included.** Steps reach the browser on its input only (A3), never on a
  mounted path, and no squad role sees them. A screenshot of a filled form shows a step's values, so the evidence is
  held out like the steps. Prediction 2's sweep covers both.
- **A suite revision with page scenarios** is drafted by the supervisor, read by an independent reviewer, and
  approved as revision 3 was (D2, #2464). It keeps revision 3's scenarios unchanged and adds the page scenarios.
- **Comparability survives the revision, per scenario.** Each scenario is content-addressed on its own (§4.1), so
  one that is unchanged between revisions keeps its version, and its results continue their series.
  - **Readings across revisions:** contribution, rates and the package compare only the scenario versions both
    readings share, and report the new ones apart, with their own series.
  - **A changed scenario is a methodology break for that scenario only,** named in the record. It is never averaged
    into the shared set.
  - **Today:** contribution refuses any two readings of different suites (`squadops.outcomes.contribution`,
    `_comparable`). That refusal becomes a comparison of the shared scenario versions, with the rest listed.
  - **Within a window, its own rule stands:** one suite, frozen (the 2.4 pre-registration §7).
- **Unchanged:**
  - the squad's own qa tests, which add no browser framework;
  - route rendering (SIP-0109 §8.3), the framework's own check that each declared route renders;
  - every rule of §4.1 on who writes scenarios and what the squad sees.

**Predictions, pre-registered for its reading:**

| # | prediction | falsified by |
|---|---|---|
| B1 | a page scenario discriminates. It fails on a tree known to lack its outcome and passes on one known to have it. It is read on the reference pair (`cyc_7a4b7a6fbf0e`, `cyc_20246018f2b8`, where the HTTP capacity scenario failed on the first and passed on the second, §10c) if its delivery shows the indicator; otherwise on a pair the review names | a page scenario that passes on a tree known to lack its outcome. One that passes both trees of every pair is withdrawn as evidence. A `blocked_unverified` reading on either tree is not discrimination: B1 is unread for that scenario, and the record says so |
| B2 | it doesn't flake. Every page scenario gives the same result on three runs of one unchanged tree | any differing result. That scenario is withdrawn as evidence, and the driver's waits are the first thing read |
| B3 | its steps stay held out. No page step's value appears anywhere prediction 2's sweep reads | any marker found |

**What the design review settles:**
1. **The locator rule:** role and candidate names only, as proposed, or a delivery's accessible labels resolved like
   §10i's concepts as well.
2. **Whether a control not found is `surface_absent`,** as proposed, or a failure. A failure would count a different
   label as a broken app. `surface_absent` lets a page that names nothing a user can find read as unverified, and it
   repeats what §10c found for fields: "Reading an undeclared field as absent hid that job."
3. **The bound on each wait,** measured when built on both stacks' pages, and the browser's cost per evaluation.
4. **Which outcomes revision 4's page scenarios state:** at least capacity's indicator and the list's order, the two
   increments the shakeout's HTTP-only suite couldn't see on a page.
5. **The evidence's size and how long it's kept,** and who may read it: the owner's console and CLI, never a squad
   identity.
6. **The per-scenario comparison's rules:**
   - how a rate is reported when the shared set is small;
   - whether a scenario whose surfaces changed but whose steps didn't is the same scenario. Its content hash says
     it isn't.
7. **Where a mixed scenario runs:** the sandbox's runner handing browser runs to the evaluator, as proposed, or the
   whole vocabulary in Node (above).

### 10l. A repository-backed Project's Campaign: its baseline reading is an evaluation of the calibration record's commit (2026-10-21, §4.1, §4.2, §4.4; SIP-0112 H.4, SIP-0109 §24bv; #2619; designed, not built: placed in 2.5)

**What changes.** On a repository-backed Project, SIP-0109 §24bv makes a Campaign's calibration a record, not a cycle,
and there's no calibration tree to evaluate. This SIP's unit is "a campaign's calibration and its increments", and
"the calibration's reading is the campaign's baseline" (§4.2). So on such a Project:

- **The baseline reading is an evaluation of the record's commit:**
  - the product started from its start declaration (contract 7) in a disposable copy of that commit (X-3);
  - the Campaign's pinned suite run against it;
  - the quality measures taken on it.

  It runs once, when the record is written, and is stored as an evaluation record that names the calibration record
  in place of a cycle: `calibration_record_id`, an additive field (contract 5's reference, nullable as `campaign_id`
  is).
- **No start declaration, or a start that fails:** every scenario and every quality measure reads `blocked_unverified`
  (§4.1). The Campaign's deltas then say "no baseline reading", never a delta of zero. This is the gap H.4 classes as
  disclosed: it blocks this reading and never the Campaign.
- **Each increment is evaluated at its cycle's end, as today.** Its previous accepted tree is the campaign branch head
  it was built on (§24bv point 2). The record names trees by tree identity, and joins them to commits through contract
  4, never by a commit stored in the record (§4.1's rule).
- **Lint stays as §4.2 states it:**
  - off the scaffold stacks it's *not measured* (`not_a_scaffold_stack`), and the product's own linter is never read
    in its place;
  - a greenfield product that follows a scaffold blueprint is measured by that blueprint's rule set.
- **Contribution (§4.4) reads the same,** with the record's evaluation standing where the calibration's did.

**Unchanged:** a sample application's evaluation, the held-out boundary (IR-4), and phase 1's reporting-only rule.

**Who ruled.** The owner ruled the direction and the 2.5 placement on 2026-10-21. The supervisor wrote this, as SIP-0112
H.4's boundary assigns it, for the MacBook lane's G4.

### 10m. W292 in the 2.4 window's lint readings: an emission defect, not the squad's code (2026-10-21, §4.2, §10f; #2607, #2618; a disclosure, the supervisor's)

**What was read.** #1937's ruff set selects all of `W` (`capabilities/delivered_lint.py:37`), so this SIP's lint
measure counts W292, "no newline at end of file". Until #2618, every file the squad emitted lost its final newline
(#2607), so a Python file the squad wrote carried a W292, where a file SquadOps seeded (the skeleton, a frozen bundle) didn't. In the window's stored evaluations (`scenario_evaluations.lint`,
read-only, 2026-10-21):

| campaign | lint, calibration → last accepted (the readout's) | of which W292 |
|---|---|---|
| 1 (`cmp_83d63c2ebb50`, FastAPI) | 19 → 67 | 2 → 8 |
| 3 (`cmp_e717aefe1143`, FastAPI) | 23 → 78 | 2 → 8 |
| 2 and 4 (Next.js) | — | 0 in every evaluation: no Python file was linted |

**What it means:**
- **The readout stands as a measurement** (`docs/plans/2-4-0-window-close.md`, "Lint grew with every increment").
  Of the FastAPI campaigns' growth, W292 is 6 of 48 in campaign 1 and 6 of 55 in campaign 3. That share is the
  emission defect, and the readout's line now says so.
- **Within a campaign,** on one deploy, the deltas compare like with like.
- **Across #2618's deploy,** a FastAPI tree's lint drops by its emitted-file count. A W292 delta that spans that deploy
  isn't comparable, and the next window's pre-registration names it.
