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

## Delivery ledger (current as of 2026-10-18)

One row per part that ships separately. Statuses as CLAUDE.md defines them. The 2.4 plan places phase 1 in 2.4
(committed) and phase 2 in 2.4 conditionally. **Phase 1's parts are placed** with the issues filed at acceptance
(2026-10-17), each labelled `sip:0113`. Phase 2's parts stay *unplaced* until the owner rules D4 on the window's record.

| part | status | where |
|---|---|---|
| phase 0: increment replay outside its campaign (#1959) | **shipped** | v2.1.0, PR #2026 |
| phase 0: the per-increment scorecard (#1960) | **shipped** | v2.1.0, PR #2027 |
| phase 0: reporting-only lint findings on the delivered app (#1937) | **shipped** | v2.1.0, PR #2088 |
| phase 1: the scenario store, its suites and the campaign's suite pin (§4.1, §4.7) | **shipped** (§10a) | 2.4.0, PR #2448, issue #2413 |
| phase 1: the runner, outside the squad's containers, on a disposable copy (§4.1; needs the sandbox's X-3, #2421) | **placed** | 2.4.0, #2414 |
| phase 1: the evaluation record and its reference (§4.1, contract 5) | **shipped** (§10b) | 2.4.0, PR #2449, issue #2415 |
| phase 1: the quality baselines, Lighthouse, axe and lint, in the evaluator's image (§4.2) | **placed** | 2.4.0, #2416 |
| phase 1: the intervention ledger's classifications (§4.3) | **shipped** (§10d) | 2.4.0, PR #2454, issue #2417 |
| phase 1: contribution and the derived metrics in the digest (§4.4, §4.6) | **placed** | 2.4.0, #2418 |
| phase 2: the proposer sees each goal's result (§4.5) | **unplaced** | 2.4 if D4 rules it in, with its issue filed then; otherwise the next even release |
| phase 2: the objective's scenario measure, read by SIP-0109 §10 row 3, as a SIP-0109 amendment (§4.7) | **unplaced** | 2.4 if D4 rules it in, with its issue filed then; otherwise the next even release |
| quality gates where phase 1's data supports a threshold (§4.2, §6) | **unplaced** | with phase 2, each with its phase-1 evidence |

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
- **Still to build for #2414:**
  - the runtime API's runner client, and the reporting-only hook at an increment's end. Both wait on
    #2451, the compose ruling that lets the runtime API call the sandbox service.

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
- **Not built yet, on #2418:**
  - the digest's wiring, which comes with the hook at an increment's end (#2414);
  - AOR and AWE, which need the objective's declared work class, a contract 2 field with the MacBook lane's
    review;
  - "every quality baseline held", which needs #2416's baselines.

**Who ruled it.** The owner accepted §4.4 (2026-10-17). The precedence and the blocked-now reading are the
implementer's, for the owner's review.
