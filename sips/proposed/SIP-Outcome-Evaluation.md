---
sip_uid: '1791124609460026'
status: proposed
title: Outcome Evaluation
author: Jason Ladd
created_at: '2026-10-04T00:00:00Z'
---
# SIP-XXXX: Outcome Evaluation

**Status:** Proposed (draft, revision 1)
**Revision:** 1 (2026-10-04)
**Target:**
- **the instruments:** reporting-only, 2.3 (a stabilization release; instruments change no verdict);
- **the feature half:** the 2.4 headline, after Cross-Cycle Memory (2.2) and before the squad
  authors its own backlog.

**Authors:** Jason Ladd (the idea); Claude Code (this draft)
**Source:** `docs/ideas/outcome-oriented-campaign-evaluation.md` (recorded 2026-10-04). This SIP is
that idea's **evaluation half**; the rest stays in the idea as its charter.
**Builds on:**
- SIP-0109 (Campaign);
- SIP-0096 (verification evidence integrity);
- SIP-0102 (the ephemeral application sandbox);
- SIP-0109 §8.3 (route rendering in a real browser);
- the Nostromo IDEA (`docs/ideas/nostromo-framework-optimization-crew.md`).

---

## 1. Summary

A campaign today is measured by its **outputs**. Its objective reads "three accepted increments" (the
machine reading is `CampaignObjective.target_accepted_increments`, read by SIP-0109 §10 row 3), and
every test that accepts an increment is written by the squad's own qa role.

So a campaign can succeed without anything independent showing that the application got better. And
the evidence of how much help it needed exists only as rows nobody has classified.

This SIP adds **outcome evidence** beside the output evidence, and keeps the two apart:
1. **Independent outcome scenarios:** jobs a user would do, authored outside the implementing roles
   and held out from the squad, run against each increment's delivered app.
2. **Quality baselines:** Lighthouse, axe and lint scores, measured locally on the same app.
3. **An intervention ledger:** every action a person or the supervisor took, classified by reason
   and severity.
4. **A per-increment reading of outcome contribution**, derived from 1 and 2.
5. **Derived autonomy metrics:** Autonomous Outcome Reliability (AOR) and the Autonomous Work
   Envelope (AWE), computed from the records.

**The rule the idea states, adopted here:** a campaign cannot claim increased autonomy unless product
quality meets its baseline. An autonomy number never travels without the quality reading beside it.

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
| an isolated runtime that boots the delivered app | SIP-0102's sandbox; SIP-0109 §8.3's route rendering stands the candidate up and reads each page in headless Chromium (`src/squadops/capabilities/handlers/route_rendering.py`) |
| evidence integrity | SIP-0096: only executed-and-passed credits; what could not run is `blocked_unverified`, never passed |
| per-cycle cost and time | each cycle's assessment: `tokens_by_run`, `tokens_by_task_type`, `wall_clock_seconds`, `llm_calls` |
| per-increment roll-up and replay | 2.1: #1960 (the per-increment scorecard), #1959 (replay any increment outside its campaign) |
| lint as evidence | 2.1: #1937 (reporting-only) |

**Neighbouring proposals, kept separate:**
- `SIP-Verification-Yield`: the value of the tests the squad writes;
- `SIP-Campaign-Self-Improvement-and-Test-Bay`: SquadOps improving itself;
- `SIP-Cross-Cycle-Memory`: what the squad recalls across cycles. Its outcome metrics (revision 2's
  recall-versus-outcome split) are one consumer of this SIP's evidence.

## 4. The design

### 4.1 Independent outcome scenarios

**What a scenario is.** A job, stated as a goal with a sequence of user actions and an outcome check.
It runs against the delivered app in a real browser and through its API. An example from the idea:
create a run, join it, leave it, and confirm the participant list is right. A scenario names:
- **its goal**, one sentence. It is the only part the squad may ever see (§4.1.3);
- **its steps and checks**, held out;
- **the surfaces it needs**: routes and endpoints, read against the increment's manifest;
- **its version**, content-addressed like a verifier bundle (SIP-0109 §8.1), so a result names the
  exact scenario it ran.

**Authorship and storage: the independence boundary.**
- Scenarios are authored **outside the implementing roles**: by the owner or the crew (Brett, in the
  Nostromo IDEA). No squad role writes one.
- They are stored where no squad task can write them, and **held out**: their steps and checks are
  never placed in a squad agent's inputs, prompts or workspace.
- SquadOps provides the seam: the store, the runner and the results in the evidence package. The
  content is the authors'.

**What the squad sees (§4.1.3).** Each scenario's **goal**, and whether it passed on the accepted
app. A failing goal is a gap the proposer may choose to close (§4.5). The steps are not shown,
because a scenario whose steps the builder can read becomes one more test it can optimize against.

**Running.** After an increment's implementation completes, in the same environment §8.3 already
stands up: the backend on its probe profile, the frontend on its dev server, headless Chromium.

**The result**, per scenario per increment: one of `passed`, `failed` or `blocked_unverified`
(SIP-0096). It carries the steps taken, the first failing step, elapsed time, and retries. A
scenario that could not run (no browser, an app that did not boot, a missing surface) is
`blocked_unverified`, never passed and never failed.

**Regression.** A scenario that passed on the previous accepted tree and fails on this one is a
**regression**, read the way a broken frozen criterion is.

### 4.2 Quality baselines

Measured on the same stood-up app, locally, with no external service:
- **Lighthouse:** performance, accessibility and best practices, per declared route;
- **axe:** accessibility violations, by impact;
- **lint:** #1937's fixed rule sets.

Each is recorded per increment with its delta from the previous accepted tree, and the calibration's
reading is the campaign's **baseline**.

**Reporting-only until a later decision** (§6). A threshold becomes a gate only in an even release,
with the reporting-only data in hand: the noise of each measure on unchanged code, and its
correlation with scenario outcomes. The idea's §6 caution applies to every measure: one that does not
track scenario success loses its weight.

### 4.3 The intervention ledger

Every action taken on a campaign by a person, or by the supervisor seat, is a ledger entry with:
- **its reason:** clarification, planning, implementation, verification, environment, tool,
  coordination, memory or context, judgement or escalation, or authorization (the idea's §8 list);
- **its severity:** advisory, unblock, recovery or abort.

**Most entries already exist as control-log rows:** a `rule` that returns a proposal, a `resume`
naming an action, an `abort`, a `pause`, an answer to a plan-gate design question, and a
`classify`. The ledger adds the two classifications to each. An action **outside** the interface
(a manual repair, a manual restart) cannot be a row by construction. The 2.0 pre-registration's frame
(#1908 §3) already voids that campaign's claim of unattended operation. The ledger records it as a declared entry, so the void is
counted rather than only stated.

**"Could the squad have resolved it?"** is the supervisor's reading, recorded with the reason. It is
an opinion, labelled as one.

### 4.4 Outcome contribution, per increment

A reading derived from §4.1 and §4.2, never written by a model:

| reading | when |
|---|---|
| **contributed** | at least one scenario newly passes, and no scenario regressed |
| **neutral** | accepted, with no scenario newly passing and none regressed: "output accepted; outcome contribution negligible" |
| **regressed** | a scenario that passed on the previous accepted tree fails |
| **unverified** | a scenario the increment's surfaces should satisfy is `blocked_unverified` |

Quality deltas are reported beside the reading and do not change it, until §6's gates exist. An
increment can be accepted (its outputs verified) and neutral (no outcome moved). That is a result,
recorded as one.

### 4.5 Evidence-driven next increments (the feature half)

The proposal run (SIP-0109 §9.1) is shown, beside the PRD's expansion scope:
- each scenario goal with its current result;
- the quality readings against the baseline.

So the strategy role can choose the highest-value gap, and its change request may name the scenario
goals it intends to move.

**Its prediction is checked after the build:** a proposal that names a goal and leaves it failing
reads as such in the ledger (SIP-0109 §9.4). The supervisor still rules on every proposal; nothing
here loosens the gate.

### 4.6 Derived metrics

Computed in the digest from the records, never stored as a judgement:
- **Autonomous Outcome Reliability (AOR), per work class:** the share of campaigns of that class that
  reached their outcome measure with no intervention above an `advisory` severity, every quality
  baseline held, and every safety guarantee intact.
- **The Autonomous Work Envelope (AWE):** AOR across the work classes. A **work class** is declared
  in the objective, never inferred: for example its increment count, its PRD tier, and whether it
  runs unattended. That keeps two campaigns comparable only when they declared the same class.
- **Per-increment cost and time:** from #1960.

**No composite score.** The idea is explicit, and this SIP keeps it: trade-offs are reported, not
averaged away.

### 4.7 The objective gains an outcome measure (the feature half)

`CampaignObjective` gains, beside `target_accepted_increments`:
- `outcome_suite`: a pinned, content-addressed set of scenarios;
- `outcome_target`: which scenario goals must pass for success;
- `quality_baseline`: which measures must not regress beyond a stated tolerance.

§10 row 3 then reads success as **the outcome target met with the baseline held**, not the accepted
count alone. A campaign that declares no outcome suite keeps today's reading, so 2.0's campaigns stay
comparable.

## 5. Not in this SIP (they stay in the idea)

- **A temporary HTTPS tunnel to cloud evaluators.** Exposing a sandbox from the home network is a
  security decision for the owner, and local evaluation comes first.
- **LLM-judged UX scores.** At most corroborating, and only once their correlation with scenario
  outcomes is measured.
- **SquadOps proposing its own framework experiments.** Framework self-improvement is deferred; the
  outer loop is the crew's (the owner's direction, 2026-09-28).
- **Confidence numbers on causal claims.** Evidence counts and their records replace them.

## 6. Phasing

| phase | release | what | verdicts |
|---|---|---|---|
| 0 | 2.1 | #1959 (increment replay) and #1960 (per-increment scorecard), already placed | none changed |
| 1 | 2.3 | the scenario store and runner, held out; scenarios run per increment, results in the package; Lighthouse, axe and lint per increment with baselines; the intervention ledger's classifications; AOR, the AWE and outcome contribution in the digest | **reporting-only:** no row, gate or prompt changes |
| 2 | 2.4 | §4.5: the proposal sees scenario goals and quality readings. §4.7: the objective's outcome measure, read by row 3. Quality gates where phase 1's data supports a threshold | changed, each with its phase-1 evidence |

Phase 1 runs through 2.3's line and the first 2.4 campaigns, so phase 2's thresholds are set from
measured noise, not guessed.

## 7. Verification: how this SIP would know it works

Predictions, each named by its mechanism, to pre-register when phase 1 is built:
1. **The scenarios discriminate.** A scenario fails on a tree known to lack its outcome and passes
   on one known to have it: the reference scenario's baseline and its accepted increment (#1804).
   One that passes both is not evidence, and is withdrawn.
2. **Holding out holds.** No scenario step appears in any squad agent's rendered request. This is
   read from the stored prompts: #1756's full prompts, or the generation records where they suffice.
3. **Outcome contribution is not the acceptance count by another name.** Across phase 1's
   campaigns, some accepted increments read `neutral`. If every accepted increment reads
   `contributed`, the suite is too close to the squad's own criteria.
4. **The quality measures are stable.** Each measure's spread on an unchanged tree, re-measured,
   stays inside the tolerance phase 2 would use. A measure that does not is reported and is not
   gated.
5. **The ledger matches the control log.** Every in-interface intervention row has its
   classification, and no classified entry lacks its row.

## 8. Questions for the owner (and the crew)

1. **Held out, or visible?** This draft holds the steps out and shows the goals. The alternative,
   fully visible scenarios, is simpler, and turns them into one more set of tests to optimize
   against.
2. **Who authors the first suite?** The crew (Brett), the owner, or both. The idea names Brett.
3. **Lighthouse and axe in the qa image.** Chromium is already there for route rendering. Adding
   them is a dependency change, with the lock files' audit.
4. **The work classes** that make AOR comparable: the first set, declared in the objective.
5. **Phase 2's placement:** 2.4 with the squad-authored backlog, or 2.4 alone with the backlog at
   2.6. **The draft's recommendation:** this SIP leads 2.4. The squad chooses its own features only
   once there is an independent measure of whether a feature helped.

## 9. Revision history

- **Revision 1 (2026-10-04):** drafted from the owner's idea of the same day, scoped to its
  evaluation half at the owner's agreement ("yes, save the idea and draft the SIP").
