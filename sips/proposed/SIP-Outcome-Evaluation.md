---
sip_uid: '1791124609460026'
status: proposed
title: Outcome Evaluation
author: Jason Ladd
created_at: '2026-10-04T00:00:00Z'
---
# SIP-XXXX: Outcome Evaluation

**Status:** Proposed (revision 2, for the owner's acceptance)
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

**Meets:** Project Lifecycle Management (proposed, PR #2401), the MacBook lane's 2.4 feature, at seven shared
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
> - **Project Lifecycle Management** (proposed, PR #2401; the owner's Q35, 2026-10-17) makes a Project any
>   registered product: an existing external repository, a greenfield product or a reference application.
>   The two SIPs meet at seven shared contracts, and their boundary is stated in both:
>   - this SIP builds no project model, and assumes no Project is a sample application;
>   - Project Lifecycle Management builds no scenario, runner, quality baseline or reading of its own.
>
>   The Spark lane's compatibility review of its §8 (that PR's §8.6) is recorded there. Its intent is this
>   revision's design (§4.1, §4.8).
> - **No conflict.**

## Delivery ledger (current as of 2026-10-17)

One row per part that ships separately. Statuses as CLAUDE.md defines them. The 2.4 plan places phase 1 in 2.4
(committed) and phase 2 in 2.4 conditionally. **Each part's issue is filed at acceptance,** so until then the rows
read *unplaced*, with the plan's placement named.

| part | status | where |
|---|---|---|
| phase 0: increment replay outside its campaign (#1959) | **shipped** | v2.1.0, PR #2026 |
| phase 0: the per-increment scorecard (#1960) | **shipped** | v2.1.0, PR #2027 |
| phase 0: reporting-only lint findings on the delivered app (#1937) | **shipped** | v2.1.0, PR #2088 |
| phase 1: the scenario store and its suites (§4.1) | **unplaced** | 2.4 by the 2.4 plan (D1, D2); its issue is filed at acceptance |
| phase 1: the runner, outside the squad's containers, on a disposable copy (§4.1; needs the sandbox's X-3, Project Lifecycle Management §8.2.2) | **unplaced** | 2.4 by the 2.4 plan; its issue is filed at acceptance |
| phase 1: the evaluation record and its reference (§4.1, contract 5) | **unplaced** | 2.4 by the 2.4 plan; its issue is filed at acceptance |
| phase 1: the quality baselines, Lighthouse, axe and lint (§4.2) | **unplaced** | 2.4 by the 2.4 plan; its issue is filed at acceptance |
| phase 1: the intervention ledger's classifications (§4.3) | **unplaced** | 2.4 by the 2.4 plan; its issue is filed at acceptance |
| phase 1: contribution and the derived metrics in the digest (§4.4, §4.6) | **unplaced** | 2.4 by the 2.4 plan; its issue is filed at acceptance |
| phase 2: the proposer sees each goal's result (§4.5) | **unplaced** | 2.4 if D4 rules it in; otherwise the next even release |
| phase 2: the objective's scenario measure, read by SIP-0109 §10 row 3, as a SIP-0109 amendment (§4.7) | **unplaced** | 2.4 if D4 rules it in; otherwise the next even release |
| quality gates where phase 1's data supports a threshold (§4.2, §6) | **unplaced** | with phase 2, each with its phase-1 evidence |

**What closes this SIP:** phase 1 shipped and phase 2 shipped, or phase 2 dropped by a numbered amendment the owner
rules.

## 0. Terms (revision 2's rename)

Revision 1 used *outcome* for three things this SIP measures. SIP-0108's `CycleAssessment` already has an *outcome*
dimension, its verdict and criteria, and that name stays (portfolio Q3). So the renamed terms are:
- **scenario evidence:** what revision 1 called outcome evidence. It sits beside the output evidence the squad's own
  criteria produce;
- **held-out scenarios**, or **scenarios:** what it called outcome scenarios;
- **contribution:** what it called outcome contribution (§4.4);
- **the scenario measure:** §4.7's addition to the objective, with its fields `scenario_suite` and `scenario_target`.

**Two names stay until the owner rules (A1):**
- the SIP's own name;
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

**Any registered Project** (Project Lifecycle Management, PR #2401) is evaluated the same way. That covers an existing
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
- Project Lifecycle Management (PR #2401): what a Project is, its source, its revisions and its own checks. This SIP
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
  - **Proposed home (A3):** the sandbox service (SIP-0102, the Spark lane's).
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
- **Secrets:** a start declaration may reference secrets (`secret://`). How a product's secrets reach an evaluation
  environment is a security decision, and it is the owner's (A4). Until it is ruled, the runner resolves no secret
  reference.

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
- The product's own linter is never used in its place. That is Project Lifecycle Management's inherited check, a
  separate record.

**Recording:** each measure is recorded per increment with its delta from the previous accepted tree. The
calibration's reading is the campaign's **baseline**.

**Where Lighthouse and axe are installed:**
- **Ruled (D2):** they are added to an image, with the lock files' audit. The ruling named the QA image, because
  Chromium is there for route rendering.
- **Revision 2 proposes the evaluator's image instead (A2).** The baselines measure the instance the scenarios read,
  and revision 2 runs that instance outside the squad's containers.

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

Project Lifecycle Management (PR #2401) states the seven contracts in its §8.2 and §8.2.1. This SIP's side of each is:

| contract | this SIP |
|---|---|
| 1. Project identity and source revision | records the Project ID and the evaluated tree's identity; resolves a Git revision only through contract 4's mapping |
| 2. `prepare_cycle()` and Campaign admission | adds nothing at `prepare_cycle()` or in a launch request; adds `scenario_suite` at Campaign creation (§4.7) |
| 3. `WorkspaceStore` | evaluates a disposable copy, never the live tree; no scenario file enters a workspace; names trees by identity, never by sandbox revision |
| 4. Campaign accepted trees | reads regression against the previous accepted tree, by SIP-0109's identity |
| 5. outcome references | produces the evaluation record and its reference, with the campaign ID nullable (§4.1); its names follow §0 |
| 6. project instructions | names each unit's pinned set as a listed input when comparing units (§4.6) |
| 7. starting the product | reads the start declaration at the revision the unit pinned; never infers one; with none, every scenario is `blocked_unverified` |

The shared fixture (Project Lifecycle Management §8.2.3) carries this SIP's recorded evaluation reference, which the
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
3. **Lighthouse and axe:** added to an image, with the lock files' audit. The ruling named the QA image. A2 asks
   whether revision 2's evaluator image replaces it.
4. **The work classes:** the increment count, the PRD tier, and attended or unattended, declared in the objective
   (§4.6).
5. **Phase 2's placement:** 2.4, conditional on the window's record (D1, D4).

The ruling also renamed the SIP's *outcome* term (§0).

### 8.1 For the owner at acceptance

| # | question | recommendation |
|---|---|---|
| A1 | **The SIP's own name.** The term is renamed (§0). Does the SIP's name follow, along with the idea's metric names (AOR)? | **Keep "Outcome Evaluation".** Both lanes, the 2.4 plan and Project Lifecycle Management's contracts cite it, and the clash with SIP-0108 was in the records' terms, which are renamed. Renaming it later is a numbered amendment |
| A2 | **Where Lighthouse and axe are installed.** D2 named the QA image | **the evaluator's image,** with the same lock-file audit. The baselines measure the instance the scenarios read, which revision 2 runs outside the squad's containers |
| A3 | **Where the runner runs** | **the sandbox service** (SIP-0102). It already launches least-privilege containers, and it holds the docker socket. It needs the `sandbox` profile on every deploy that evaluates. No compose change is needed. The browser runs in a container the service launches from the evaluator image, and receives a run's steps on its input, never on a mounted path |
| A4 | **Secrets in a start declaration** (Project Lifecycle Management's contract 7) | **the owner's security decision.** Until it is ruled, no secret reference is resolved, and a product that needs one reports every scenario `blocked_unverified`, with reason "secret not available" |

## 9. Revision history

- **Revision 1 (2026-10-04):** drafted from the owner's idea of the same day, scoped to its
  evaluation half at the owner's agreement ("yes, save the idea and draft the SIP").
- **Revision 2 (2026-10-17), for the owner's acceptance:**
  - **The owner's answers to §8,** ruled as the 2.4 plan's D2.
  - **The term renamed** (§0).
  - **The Spark lane's compatibility review of Project Lifecycle Management** (PR #2401 §8.6), made design:
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
