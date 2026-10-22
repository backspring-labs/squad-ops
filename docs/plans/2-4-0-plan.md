# 2.4.0 plan — the yardstick first: Outcome Evaluation leads and measures before it changes anything, and Project Lifecycle Management develops products SquadOps doesn't own

**Status: ADOPTED (2026-10-17).** The owner ruled every decision in §7: D1 on 2026-10-16, D13 on 2026-10-17, and D2–D12
and D14 the same evening ("approve D2-D12 and D14 as recommended"). The headline's shape came first. The owner, on 2026-10-16,
agreed to the supervisor's recommendation ("agree, draft the 2.4 plan that way after the cut"):
- Outcome Evaluation leads 2.4;
- its design review comes early;
- its feature half is conditional on its instruments' data arriving in the line;
- if that data is late, SIP-0110's memory entry points carry 2.4 as its feature. D14 (2026-10-17) replaces this
  fallback: Project Lifecycle Management is then the headline.

This plan proposed everything else, and the owner ruled it (§7). 2.3.1 cut on 2026-10-17.

**Revised 2026-10-17: Project Lifecycle Management is added** (§2). The owner made it 2.4's feature on the MacBook
lane (Q35, PR #2401), so the release carries one feature per lane. D1 stands for the Spark lane's. The SIP's §8.5
gives this plan its schedule, and the contracts and gates are the SIP's, ruled.

**Revised again 2026-10-17,** from a review the owner brought. This revision adds:
- the contract matrix (§2.3);
- the shared demonstration, as the owner chose it (§2.7, D13);
- what the window records (§1.3);
- the two-lane checkpoints (§5);
- the scope and acceptance matrices, and what the release reads (§6);
- each decision's status (§7).

**What 2.4 is.** An even minor, a feature release, gated by at least one headline feature SIP (CLAUDE.md, #281). It is
the first release framed by the owner's output-quality turn (2026-10-09): "things have stabilized to the point I feel
like we can make real tweaks to focus on code and app output quality instead of continually fixing framework bugs".
That turn's first rule is to fix the yardstick before the tweaks. Today a campaign is measured by its outputs: accepted
increments, each accepted by tests the squad's own QA role wrote. Nothing independent says whether the app got better.

**The question it answers:**

> **Does the app the squad builds get better in ways an independent check can see? And once the squad can see which
> goals still fail, does it aim its next increment at them?**

The first half is Outcome Evaluation's instruments (phase 1), reporting only. The second is its feature half (phase 2),
which changes what the proposer sees and what a campaign's success means. Phase 2 is built only on phase 1's data.

**The MacBook lane's question** (§2): can SquadOps develop a product it doesn't own, in that product's own repository
and by its own rules, both when the product already exists and when SquadOps creates it?

---

## 1. The Spark lane's feature: Outcome Evaluation (SIP-0113, `sips/accepted/SIP-0113-Outcome-Evaluation.md`)

### 1.1 The design review, first

**Accepted 2026-10-17 as SIP-0113** (the owner: "approve A1-A3 as recommended and accept 2406"), after its design review and before any of its code. Its §8's five
answers are D2's (§7), and its acceptance questions A1 to A4 are ruled in its §8.1. A2 moves D2(3)'s Lighthouse and axe
to the evaluator's image. Phase 1's parts are placed with issues #2413–#2418.

Two things the review should also settle, both found while drafting this plan:
- **"Outcome" is already a word in an implemented SIP.** SIP-0108's `CycleAssessment` has an *outcome* dimension. The
  draft's intake note recommends renaming its own term before phase 1 ships ("scenario evidence", "contribution").
- **Holding out can be checked on what already exists.** The SIP's second prediction reads the squad's rendered
  requests for scenario steps, from #1756's full prompts "or the generation records where they suffice". The authoring
  envelopes already reconstruct byte for byte, as every 2.3 counted roll showed (`verify_authoring_envelopes.py`). They
  are the full request at each authoring seam, so holding out is checkable there without #1756.

### 1.2 Phase 1: the instruments, reporting only

As the SIP's §6 lists them:
- **the scenario store and runner, held out:**
  - scenarios run per increment, on a disposable copy of the evaluated tree, outside every squad agent's container
    in the sandbox service (SIP-0113 §4.1, A3; SIP-0109 §8.3's environment runs in the QA role's container, which would
    put the steps in a squad task's inputs);
  - results go in the package, as `passed`, `failed` or `blocked_unverified`;
  - a regression is read the way a broken frozen criterion is;
- **quality baselines:** Lighthouse, axe and lint per increment, with deltas from the previous accepted tree;
- **the intervention ledger's classifications** on the control log's rows;
- **in the digest:** each increment's outcome contribution, and the autonomy readings (AOR and the work envelope).

**Nothing in phase 1 changes a row, a gate or a prompt.** A scenario result reaches no squad role. This is the line's
first build, on branches, merged in reviewable steps, each with its wiring test and loaded check.

**The first suite** is authored outside the implementing roles. The owner ruled that the supervisor drafts it and the
owner approves it (D2, the SIP's question 2), following the auditor rule the owner set for lessons: a frontier model
drafts, a person approves, and the squad's own model drafts none. The suite is frozen and content-addressed before the
window starts.

### 1.3 The measurement window: phase 1's data

Phase 2's thresholds have to come from measured noise, not guesses. So phase 1 runs on a window of campaigns,
pre-registered before the first one launches.
- **Ruled (D3):** four campaigns, two per stack, of three increments each, on one frozen deploy. The deploy is
  frozen for both lanes (Project Lifecycle Management's G7, ruled): neither deploys a change inside the window (§2.6).
- **They double as the next build-side memory experiment** (SIP-0110's ledger, unplaced; the 2.3 plan's D6 put it in
  2.4 beside Outcome Evaluation). That experiment needs multi-increment campaigns on both stacks with memory on and no
  build-side lesson approved, so memory observes and supplies nothing. The window's campaigns can be exactly that,
  which gives one set of campaigns two readings.

**What the window records,** so that its readings compare only like with like:
- the deploy, and the framework commit it was built from;
- the scenario suite's content digest, and each scenario's version;
- each campaign's Project and its source revision, and after the registry cutover its Development Configuration
  revision too;
- SIP-0110 §0.12's experiment manifest: the prompts and fragments, the squad and request profiles, the model and
  provider settings, the policies, the evaluator, and the store's lessons and approvals;
- the scoring rules: the contribution readings (the SIP's §4.4) and each quality measure's version.

**A change inside that record ends the series.**
- If either lane has to redeploy inside the window, the series closes.
- The next series starts under a new record, with its own baseline and its own pre-registration (SIP-0110 §0.12).
- No reading compares two series as though the environment were the same.
- G7 exists to prevent this. This is what happens if it is broken.

**What the window reads,** each pre-registered as a mechanism and how it is falsified (the SIP's §7):
- the scenarios discriminate on a tree known to lack and one known to have each outcome;
- no scenario step appears in any authoring envelope;
- some accepted increments read `neutral`. If every one reads `contributed`, the suite is too close to the squad's own
  criteria;
- each quality measure's spread on an unchanged tree, re-measured;
- the ledger and the control log agree;
- for memory, the repeat report and the auditor's reading of what repeats.

### 1.4 Phase 2: the feature half, conditional

Phase 2 is the SIP's §4.5 and §4.7:
- **§4.5:** the proposal run sees each scenario goal's current result and the quality readings beside the PRD's
  expansion scope, so the strategy role can aim at a failing goal. A proposal that names a goal and leaves it failing
  reads so in the ledger. The supervisor still rules on every proposal.
- **§4.7:** `CampaignObjective` gains an outcome suite, an outcome target and a quality baseline. SIP-0109 §10 row 3
  reads success as the target met with the baseline held. A campaign that declares none reads as today, so earlier
  campaigns stay comparable. That is a numbered amendment to SIP-0109, in the PR that builds it.

**The condition** (D4): phase 2 is built in 2.4 only if the window's readings support it. That means:
- the scenarios discriminate;
- holding out holds;
- outcome contribution is not the acceptance count by another name;
- each measure that phase 2 would gate has a spread inside its tolerance.

The owner reads the window's record and decides. If the data is late or doesn't support it, phase 2 moves to the
next even release with the record. **Project Lifecycle Management is then the release's headline, with phase 1 as the
yardstick** (D14), and the memory entry points ship as placed (§3).

**SIP-0109 §24ap's deferred row joins phase 2:** accepted increments' `prd_delta` text to the proposer ("a 2.4
question", ruled 2026-10-03). It is the same seam: what the proposer is shown.

---

## 2. The MacBook lane's feature: Project Lifecycle Management (SIP-0112, accepted 2026-10-17)

**Added 2026-10-17.** The owner made Project Lifecycle Management 2.4's feature on the MacBook lane. The ruling is Q35,
from the SIP's design review in PR #2401. The release carries one feature per lane: Project Lifecycle Management on the
MacBook lane and Outcome Evaluation on the Spark lane (§1). The lanes develop independently and meet at seven shared
contracts.

The SIP's §8 states the agreement, and its §8.5 gives this plan the schedule. This section sequences what the SIP
states and changes none of it. Read at revision 7, commit `3755c352`.

The SIP is still proposed. Until the owner accepts it, it has no number, no issues and no placement (its G1). There is
no integration branch until the owner opens one (G2).

### 2.1 The lanes (its §8.1)

| | MacBook lane | Spark lane |
|---|---|---|
| owns | Project Lifecycle Management | Outcome Evaluation, and the sandbox (`src/squadops/sandbox/`, SIP-0102) |
| builds | the Project Record and the registry cutover; the Project Development Configuration, with its start declaration; managed clones; inherited verification baselines; Git revisions and their mappings; repository instruction discovery and drift detection; the project CLI and API writes | the held-out scenario store and runner; quality baselines; the intervention ledger's classifications; contribution and the derived metrics; the objective's outcome measure (a SIP-0109 amendment); the three sandbox changes (§2.4) |
| never builds | scenarios, a scenario runner, quality baselines or outcome readings | a project model of its own, or anything that assumes a Project is a sample application |

A change to a file the other lane owns carries that lane's review. Each lane works on branches off `main` and
integrates through reviewed PRs. There is no integration branch until the owner opens one (G2).

### 2.2 What 2.4 carries, and its two demonstrations

These are the SIP's delivery slices (its E.4 and its delivery ledger):

| slice | what | in 2.4 |
|---|---|---|
| E.4.1 (#2408) | registering an existing product: the writable registry cutover, its tested rollback, the proof that existing projects are unchanged (IR-1), and the minimum enrollment | yes |
| E.4.2 (#2409) | discovering the repository's own instructions and capturing its inherited baseline, with the start declaration (contract 7) | yes |
| E.4.3 (#2410) | the first scoped feature through the shared cycle path (IR-2) | yes |
| E.4.4 (#2411) | the second feature, after an outside contribution | yes |
| E.4.5 | lifecycle completeness: update history, archive and restore, concurrency and conflict recovery | **no:** required before the SIP closes, not in 2.4 (the owner, 2026-10-17) |
| E.4.6 (#2412) | creating a greenfield Project at an owner-approved destination | **yes, shipped by the cut** (G6, the owner's ruling) |
| E.4.7 | writing in place in an existing checkout | optional |

**The order:**
- the shared fixture (#2407) first, before either lane's first shared-contract PR;
- E.4.1, then E.4.2, then E.4.3, then E.4.4;
- E.4.6 follows E.4.3.

**Both demonstrations are run and read in 2.4:**
- **brownfield** (its §7), pre-registered before it runs:
  - an unfamiliar existing repository is registered without changes to its source;
  - a first feature goes through the product's normal contribution process;
  - an outside developer changes the repository;
  - a second feature follows, after the drift is reconciled.
- **greenfield** (E.4.6): shipped by the cut.

*Not run* never covers either demonstration (the owner's clarification of G5 and G6).

### 2.3 The seven contracts and the shared fixture (its §8.2)

The SIP defines the contracts (its §8.2 and §8.2.1). This plan says who produces and reads each one, when it
freezes, and which integration scenario exercises it.

| contract | produced by | read by | frozen by | its test (the SIP's §8.2.1) | exercised by |
|---|---|---|---|---|---|
| 1. Project identity and source revision | the MacBook lane (`ProjectSourceContext`, E.4.1 and E.4.3) | cycle preparation, the Campaign launcher, Outcome Evaluation | the shared fixture's PR | `prepare_cycle()` with the fixture's Project: ready, not ready, and a stale commit | IR-1, IR-2, IR-5, IR-8 |
| 2. `prepare_cycle()` and Campaign admission | both lanes, each its own fields: the MacBook lane's source context and preconditions; the Spark lane's suite pin and objective fields; SIP-0110's snapshot (#2179) | cycle and Campaign preparation | each field, when its PR merges with the other lane's review (G4) | the standalone and Campaign preparation tests, on every change | IR-2 |
| 3. `WorkspaceStore` | the Spark lane's sandbox (X-1 to X-3); the MacBook lane's seeding and its revision-to-commit mapping | the MacBook lane's capture; Outcome Evaluation's runner | the fixture's PR for the mapping; X-1 before E.4.2 | seed the fixture at a commit, capture a change back, and resolve the mapping both ways | IR-4, IR-5 |
| 4. Campaign accepted trees | SIP-0109, whose identity is unchanged; the MacBook lane's mapping to Git | Outcome Evaluation's regression reading; Project history | already, for the identity; the mapping with E.4.3 | IR-5 | IR-5 |
| 5. outcome references | the Spark lane (`OutcomeEvaluationRef`) | the MacBook lane's Project history | the fixture's PR, after Outcome Evaluation renames its term (D2) | write the fixture's reference, read it back, and refuse an unknown major version | IR-4, IR-5 |
| 6. project instructions | SIP-0110 (#2179); the MacBook lane's discovery and resolver | both lanes | when #2179 merges | IR-3 | IR-2, IR-3 |
| 7. starting the product | the MacBook lane: the Development Configuration's start declaration (E.4.2) | Outcome Evaluation's runner, through X-3 | the fixture's PR | start the fixture from its declaration; a missing declaration; a readiness timeout | IR-6, IR-7 |

- **Frozen** means the fixture's recorded output is the shape the other lane builds against. Changing it after that
  is a shared-contract change (G4).
- **When a contract's data is absent,** what each consumer does is the SIP's rule (its §8.2.1, "absent, stale or
  unavailable").
- **At the plan's level:** each lane builds against the fixture's recorded outputs until the other lane's code ships.
  An integration scenario whose prerequisite hasn't shipped reports *not run* (G5).
- **One of each:** there is one Project registry, one workspace authority and one source-revision model. Neither lane
  builds a second.

**The shared fixture lands first** (its §8.2.3).
- **What it is:** one small product with its own layout, its own native commands, one check that fails before any
  change, and one binary file.
- **What comes with it:** each lane's recorded outputs. Each is recorded valid, with a field missing, with an unknown
  schema version, and with a stale commit.
- **How it lands:** as one PR both lanes review, before either lane's first contract PR.
- **Ruled (D12):** the MacBook lane writes it, and the Spark lane adds its recorded evaluation reference in the
  same PR.

**Every PR that changes a shared contract** must:
- name the contract;
- carry the other lane's review;
- add a wiring test that enters where the live cycle does;
- only add, never repurpose or remove (G4).

### 2.4 The three sandbox changes (its §8.2.2)

The sandbox is the Spark lane's. **Ruled (D12):** the Spark lane builds all three, and the MacBook lane reviews
each one as its consumer (G4).

| change | what it fixes on `main` | what needs it | when |
|---|---|---|---|
| **X-1** (#2419): a revision origin for a Git checkout | `RevisionOrigin` is a closed set (`src/squadops/sandbox/models.py:23`), and a revision with any other origin is refused (`:103`) | E.4.2 can't seed a checkout without it | first, right after the fixture: E.4.2 waits on it |
| **X-2** (#2420): binary files | seeding, reading the tree and persisting revisions handle UTF-8 text only (`src/squadops/sandbox/workspace.py:205`). Until X-2 ships, a product with binary files is refused at seeding, with that gap named | most real repositories carry some binary files (images, fonts) | before the brownfield demonstration, unless its product is text-only. Every existing revision ID stays the same: hashing the raw bytes gives today's digest for UTF-8 text |
| **X-3** (#2421): a product's own commands | `ExecutionSandboxPort` (`src/squadops/ports/sandbox.py:33`) runs the environment's fixed install, build, test and start commands | contract 7: Outcome Evaluation starts an external product from its declaration | **split 2026-10-18 (the lanes, on #2407):** X-3a, a declared command such as a product's check, run against a pinned revision in a disposable copy, straight after X-2 and before E.4.2's inherited baseline (FR-20); X-3b, starting the product from its declaration with readiness and the evaluation secrets, with Outcome Evaluation's runner, before IR-6 |

**X-3 also starts a pinned revision in a disposable copy.** Today's start mounts the cycle's live tree and runs the app as
the tree's owner, so the app can write its state there (`adapters/sandbox/container_backend.py:157-164`, `:316-321`). Contract 3 rules that out
for a scenario.

### 2.5 The integration scenarios and the gates (its §8.4 and §8.5)

**IR-1 to IR-10 are the integration's evidence.** They run on a deploy carrying both lanes, once the owner opens the
integration branch (G5).
- **MacBook lane:**
  - IR-1: existing projects are unchanged after the registry cutover;
  - IR-2: a standalone launch and a Campaign launch see the same source context;
  - IR-3: an instruction changes after a Campaign is admitted, and the Campaign keeps its binding;
  - IR-8: a newly registered Project is visible everywhere at once.
- **Spark lane:**
  - IR-6: an external Project with no interface manifest, started by contract 7's commands.
- **Both lanes:**
  - IR-4: no scenario step anywhere the squad or the product can see;
  - IR-5: every identity resolves through the mappings;
  - IR-7: a greenfield Project's first Campaign;
  - IR-9: an inherited failing check stays the product's own;
  - IR-10: the counted regression pair is unchanged with both lanes deployed.

**G4 to G7, all ruled 2026-10-17:**
- **G4:** the shared-contract rule above.
- **G5:** each lane's feature is done on its own evidence.
  - An integration scenario whose other-lane prerequisite hasn't shipped reports *not run*.
  - A *not run* record names the prerequisite, the contract affected, the evidence that is missing, and whether the
    release claim is affected.
- **G6, the cut:**
  - IR-1 to IR-10 pass or report *not run*;
  - IR-4 to IR-9 need only Outcome Evaluation's phase 1, and its phase 2 is not required;
  - the brownfield demonstration is pre-registered and read, and greenfield has shipped;
  - the cut record says what each lane's evidence does not cover.
- **G7:** the window's deploy is frozen for both lanes (§2.6).

### 2.6 Where the lanes meet in time

- **Outcome Evaluation's phase 2 stays conditional** (D1, D4). Neither Project Lifecycle Management nor the cut requires
  it (G6).
- **The window's deploy is frozen for both lanes, and neither lane deploys a change inside the window** (G7, §1.3).
  - The window runs `group_run` campaigns, and the registry cutover (E.4.1) changes how `group_run` is resolved.
  - So the cutover deploys before the freeze, with IR-1 read, or after the window closes.
  - **Ruled (D12):** before the freeze if IR-1 has passed, otherwise after the window.
- **The demonstrations need a live deploy.** The lanes agree where they run: on the Spark, or on the MacBook's own
  deploy. If they run on the Spark, they run outside the window (D12).
- **Project Lifecycle Management's slices run on the MacBook lane's own schedule.** This plan fixes only where they meet
  the Spark lane:
  - the fixture comes first;
  - X-1 comes before E.4.2;
  - the cutover never deploys inside the window;
  - the integration scenarios run once the owner opens the integration branch.

### 2.7 The shared demonstration: the vehicle for the cross-lane scenarios

**The owner's choice, 2026-10-17 (D13):** the shared demonstration is the proposed vehicle for the cross-lane
scenarios, not a release requirement.

**What it is:** one Campaign on an unfamiliar external web application that SquadOps didn't build:
1. the product is enrolled as a Project, its native development configuration is discovered, and its source
   revision is pinned;
2. its inherited verification baseline is captured;
3. a Campaign starts on it, and a feature cycle runs;
4. the accepted tree is mapped to the Git commit it became;
5. Outcome Evaluation starts the product from its start declaration (contract 7) and evaluates it on held-out
   scenarios, reporting only;
6. the evaluation record is stored with its Project, Campaign, cycle and tree references (contract 5);
7. an outside developer pushes a change, and a second feature follows.

**How it works:**
- **What it exercises:** IR-4, IR-5, IR-6 and IR-9, live, in one run. Its purpose is to find boundary defects
  between the lanes, not to merge the two designs.
- **What it needs first:**
  - contract 7 (E.4.2), X-3 and Outcome Evaluation's phase-1 runner;
  - a scenario suite of its own, since the window's suite is written for `group_run`. The supervisor drafts it, and
    the owner approves it (D2).
- **What it doesn't replace:** each feature's own acceptance tests, the brownfield demonstration and the greenfield
  proof. Those run and are read on their own, and *not run* never covers them (G6).
- **If it can't run before the cut:** its scenarios report *not run*, each with its missing prerequisite (G5). The
  release ships on each lane's own evidence.
- **It stays held out:** neither the product nor the squad sees a scenario step (the SIP's §8.3, IR-4).
- **Not run in 2.4** (the owner, 2026-10-21: "go with 2.5"). A Campaign on a repository-backed Project runs its
  calibration but can't launch an increment (#2619). Its profiles pin a template stack that source-backed cycles refuse,
  and a proposal needs an interface manifest the product has none of. So the demonstration's feature cycles can't run,
  and its scenarios report *not run* with #2619 as the missing prerequisite. The fix is SIP-0112's amendment H.4,
  placed in 2.5: a development profile derived from the product, its capability gaps named, calibration as the inherited
  baseline, and proposals read from the product's tree.

---

## 3. Beside it: SIP-0110's memory entry points (accepted, placed in 2.4.0)

Seven placed rows, each with its open issue (SIP-0110 Appendix A, epic #2173):

| issue | what |
|---|---|
| #2177 | typed memory records: notes, preferences, project and task instructions, with permissions by kind and provenance |
| #2178 | task instructions: an operator's directive reaches the task it names, and only that task |
| #2179 | project instructions pinned in the unit snapshot and binding; a lesson comparison varies only the lessons |
| #2180 | chat on the memory substrate: project-scoped context, capture with confirmation, an exposure per turn |
| #2181 | chat explains approved lessons and never applies them; a conversational claim never becomes a lesson |
| #2182 | the console's memory view: a record's source, scope, status, revisions, consuming tasks and results |
| #2183 | the acceptance matrix, T1–T17, live on a deploy |

**The relationship is one-way** (SIP-0110 Q25). Outcome Evaluation supports quality claims about memory, but it isn't
needed to deliver the entry points, and they don't block it. So they build in parallel, on their own branches.

**Two things to settle before they ship:**
- **Q29: conversation history's retention** is ruled (2026-10-17, SIP-0110 §A.8): no automatic expiry while the deploy
  has one operator; a person deletes their own sessions; a record confirmed from a deleted session stays, marked so.
- **They change squad behaviour only through approved records.** A task or project instruction reaches the squad
  only when the operator writes one. The window's campaigns write none, so the entry points don't touch the window's
  readings.

**If phase 2 moves,** Project Lifecycle Management is the release's headline (D14). The entry points are claimed on their
own evidence, #2183's acceptance matrix, live.

---

## 4. Riding along

### 4.1 In 2.4

| item | what | when in the line |
|---|---|---|
| #316, the request-profile taxonomy (`sips/accepted/SIP-0114-Cycle-Request-Profile-Naming.md`, accepted 2026-10-19) | names drawn from one axis, with old names resolving as aliases (Q13) | its SIP's design review early; the rename lands before the window's deploy freezes, so the window runs on the final names |
| #1966, risk-first QA and builder instructions | an A/B on replayed increments (#1959), read on the per-increment scorecard (#1960) and the window's scenarios | **the A/B runs in 2.4; adoption is a separate ruling, not before phase 2's decision,** so the release doesn't change two squad behaviours at once and lose both readings |
| #2378's proper fix | an endpoint declares its query parameters as a field the scaffold, QA's prompt and the probes read | after the window, each output-quality change measured on the yardstick, pre-registered as 2.3's #2202 and #2205 comparisons were. **Built 2026-10-22** (SIP-0103's amendment of that date): one manifest in 404 since 09-15 chose a query input, so it is read by a replay of #2378's own cycle, not a rate. No probe is derived for it; a `DELETE` gets none today |
| #2153's build | a failing slot assertion routed by demonstrated defect ownership (SIP-0104 §13d), now that SIP-0110's window has closed | after the window, as above. **Dropped 2026-10-22 (SIP-0104 §13e):** the frozen spine asserts the contract before the slot runs, so the routing is met by construction; 37 days of runs show no route it would change. The unbuilt ambiguous-case guard is #2664, unplaced |
| #2306 | a converging repair ended as a plan defect: read the 12 recent terminations first, then fix | the read early; the fix after the window if the read finds converging repairs |
| #1756 | the full rendered request stored once per generation, readable by id, with the redaction applied | early, as an instrument: it reaches the seams the authoring envelopes don't |
| #2253 | QA's output budget: read the headroom across every recorded `qa.test` call, then decide | the read early; any budget change only between measurements, named in the record |
| #2443, a campaign's stack (found 2026-10-18, a prerequisite of D3) | a campaign can't run on Next.js: each launch carries only a profile name, and every campaign profile pins FastAPI. The campaign's policy gains its stack, passed to every launch as an override; a contract 2 field, with the MacBook lane's review (G4), and a SIP-0109 amendment | **before the window's pre-registration:** the window runs two campaigns per stack (D3), and a Next.js campaign has never run, so uncounted Next.js shakeout campaigns come first |
| #2395 (placed in 2.4 by the owner, the 2.3.1 plan's D4) | a Next.js plan asks QA for page-state tests the stack's vitest can't run: one suite needed a DOM library the stack doesn't seed, another rendered on the server and saw only the loading state (2.3.1's round 3) | **before the window's deploy freezes:** it rejected 2.3.1's last Next.js roll, and the window runs two Next.js campaigns, so left in place it would decide their increments rather than the app's outcome |
| #2297 (placed in 2.4 by the owner after the 2.3.0 cut) | QA's test author was shown the leave endpoint and used it exactly, but the planned "empty name" case can't be expressed against a name in the path | after the window, with the other output-quality changes (D8) |

### 4.2 Not in 2.4

| item | why | where |
|---|---|---|
| #557, #949, #950: the judgement steps | they follow Outcome Evaluation and are measured on it, and 2.4 already changes the proposer. Adding judgement steps would make neither change readable | 2.5 or later, re-read at 2.4's cut |
| #2230, the upgrade to TensorFold 1.x (redirected by the owner on 2026-10-18 from Qwen3.8-Flash-Next on TensorFold; SIP-0111 §9m) | the owner on 2026-10-15: "no second tensorfold candidate at this time"; on 2026-10-18: "I will want to tackle this move to 1.1.0 - but not just yet", and "I think this model change will come after 2.4 and the outcome evaluation work" | **unplaced, deliberately,** with the owner's words, until the owner places it (D9) |
| #1978, test-first verification | "after Outcome Evaluation's baseline": it needs phase 1's data first | 2.5 or later |
| #2619, Campaigns on a repository-backed Project (SIP-0112 H.4) | a Campaign on an external or greenfield product can't launch an increment. The fix derives the product's development profile, names its capability gaps and reads proposals from its tree. That needs SIP-0109's counterpart and a live full-squad run. The shared demonstration (§2.7) reports *not run* in 2.4 | **2.5**, the owner, 2026-10-21 |
| #2414's remainder (the declared start at the cycle-end hook) and #2421's (an owner-approved evaluation secret resolved at start) | each one's only consumer is the evaluation of a repository-backed Project's Campaign, which moved to 2.5 with #2619. Every 2.4 evaluation is a sample application's, started by its stack | **2.5**, re-placed by the supervisor, 2026-10-21 |
| #1965, the framework suite's test-value audit | the crew's first optimization experiment, an outer-loop item with no 2.4 dependency | the owner's to place |
| the squad authoring its own backlog | portfolio Q1: 2.6, with its own SIP. The squad chooses features only once there's an independent measure of whether a feature helped | 2.6 |
| #2184, retiring the legacy store | placed 2.5.0 (SIP-0110) | 2.5 |
| #2433, the Spark board-thermal rule's no-data alert on boxes without that board, and the deploy never starting node-exporter | the owner on 2026-10-18: "we can pickup 2433 in 2.5 if it's not a blocker to anything". It isn't one: on the Spark both exporters run and the rule reads Normal, and nothing in 2.4 reads them. The MacBook pays log noise until then | 2.5 |
| #2286, TensorFold operator keys | credentials: the owner's to place | the owner |
| #2287, a box-level operator lease | no 2.4 dependency | the owner's to place |

---

## 5. Sequencing: the box is the constraint

Most of the work is code. The box's time goes to the window, the demonstrations, the integration scenarios and the
cut.

**Each lane moves through these checkpoints on its own.** They are not a serial order:
- the window doesn't wait for the MacBook lane's demonstrations;
- an integration scenario runs as soon as its prerequisites have shipped.

| checkpoint | MacBook lane | Spark lane | together | it starts when |
|---|---|---|---|---|
| **M0, ready to build** | the owner accepts Project Lifecycle Management (PR #2401): **done 2026-10-17, SIP-0112** | Outcome Evaluation's design review (D2): **done 2026-10-17, SIP-0113**; and #316's | this plan's decisions are ruled; the shared fixture merges, freezing contracts 1, 3, 5 and 7 (§2.3) | 2.3.1 has cut: done, 2026-10-17 |
| **M1, building alone** | E.4.1, then E.4.2 (after X-1), then E.4.3 | phase 1: the scenario store and runner, the baselines, the ledger; X-1 first, X-3 with the runner, X-2 before the brownfield demonstration; #316's rename; #1756; the entry points' first rows. The early reads (#2306, #2253) need no box time | each lane's contract tests run against the fixture; every contract change goes through G4 | M0, for that lane |
| **M2, measuring** | the registry cutover deploys before the freeze or after the window (§2.6) | the window: suite and deploy frozen (G7), four campaigns, recorded as §1.3 says | neither lane deploys inside the window | phase 1 is built and its suite approved |
| **M3, each lane's acceptance** | the brownfield demonstration (E.4.3, then E.4.4), then greenfield (E.4.6) | the window's record read; the phase-2 decision (D4), then phase 2's build and reading, or the record that moves it; after the window, the output-quality changes (#2378, #2153, #2306's fix if any) and #1966's A/B | on the Spark, the demonstrations run outside the window | M1 for the MacBook lane; M2 for the Spark lane |
| **M4, integrating** | IR-1, IR-2, IR-3, IR-8 | IR-6 | IR-4, IR-5, IR-7, IR-9, IR-10; the shared demonstration (§2.7) runs IR-4, IR-5, IR-6 and IR-9 live | the owner opens the integration branch (G2), and each scenario's prerequisites have shipped |
| **M5, the cut** | — | — | the entry points' acceptance matrix, live (#2183); the cut's pre-registered set and shakeout, written when the last batch is built; the cut record, with G6's conditions (§6.2) | the last batch is built |

**The dependencies across the lanes,** and only these:
- the fixture before either lane's first contract PR;
- X-1 before E.4.2;
- X-3a before E.4.2's inherited baseline (split from X-3 on 2026-10-18, #2407);
- X-2 before the brownfield demonstration, unless its product is text-only;
- contract 7 (E.4.2) and X-3 before Outcome Evaluation reads any external Project (IR-6, the shared demonstration);
- the registry cutover never inside the window;
- the integration scenarios only after the owner opens the integration branch.

**Box-time guides** (guides, never triggers; the owner's rule from 2.3):

| step | guide |
|---|---|
| each rebuild's regression pair | ~1 h |
| the window: four campaigns of three increments | ~10–12 h |
| phase 2's reading, if built | ~4–6 h |
| #1966's A/B on replays | ~6–10 h |
| the acceptance matrix, live | ~2 h |
| the cut's set and shakeout | ~4 h |
| Project Lifecycle Management's two demonstrations | set in their pre-registrations, by the MacBook lane |
| the shared demonstration | set in its pre-registration |

---

## 6. What the release claims, and what it does not

**If phase 2 ships,** the claim is that a campaign can be read by its outcomes. Its success is a declared outcome
target met with a quality baseline held, and the proposer aims at what still fails. The evidence is the window's
record and phase 2's own reading.

**If phase 2 moves,** the headline is Project Lifecycle Management (D14, below), and phase 1's instruments still ship as
reporting only, so the release carries the yardstick either way. The entry points are claimed on their own evidence,
the acceptance matrix, live: an operator's instruction reaches the task it names and only that task, and chat works on
the memory substrate.

**Project Lifecycle Management's claim stands on its own evidence either way** (G5):
- SquadOps develops an independently owned product in its own repository:
  - it is registered without changes to its source;
  - a feature goes through the product's normal contribution process;
  - a second feature follows an outside change;
  - a greenfield product is created and developed the same way.
- The evidence is the two demonstrations, and the integration scenarios that ran.

**Not claimed in either case:**
- that the squad's apps are better;
- that memory helps;
- that every product layout or toolchain is supported, or that a product with binary files works before X-2 ships.

Each would need a pre-registered comparison on the yardstick this release builds. Making that comparison possible is
what the release is for.

### 6.1 What is committed

| category | what | on what authority |
|---|---|---|
| **committed: the cut needs it** | Project Lifecycle Management's E.4.1–E.4.4 and E.4.6, and both demonstrations; Outcome Evaluation's phase 1, reporting only; IR-1 to IR-10, each run or reported *not run*; the cut's set and shakeout | G6 and the owner's rulings of 2026-10-17; D1 |
| **conditional** | Outcome Evaluation's phase 2 (its §4.5 and §4.7), with SIP-0109 §24ap's row | D4: built only if the window's record supports it. Its absence does not fail the release |
| **placed, built in parallel** | the memory entry points (#2177–#2183); #316; §4.1's riding-along items | SIP-0110's placement (D5); D6 to D8 |
| **not in 2.4** | E.4.5, before the SIP closes; E.4.7, optional; #557, #949, #950 and #1978 (D10); #2230 (D9); the rest of §4.2 | the owner's rulings; D9, D10 |

Where review or box time runs short, the committed rows come first. The placed rows never displace them.

### 6.2 The release acceptance matrix

| tier | evidence | does the cut need it? | gate | if it is missing |
|---|---|---|---|---|
| **contract verification** | each contract's minimum test (the SIP's §8.2.1), green on `main` against the shared fixture | yes | G4 | the contract change does not merge |
| **Project Lifecycle Management's acceptance** | E.4.1–E.4.4 and E.4.6 shipped; the brownfield demonstration pre-registered, run and read; the greenfield proof run and read; the SIP's E.7 checklist | yes | G6 | no cut. *Not run* never covers either demonstration |
| **Outcome Evaluation's phase 1** | the instruments shipped reporting only, each with its wiring test and loaded check; no scenario result reaching a squad role | yes | D1 | no cut on D1's terms, unless the owner rules otherwise |
| **Outcome Evaluation's phase 2** | its build and its own pre-registered reading, on the window's record | only if D4 rules it in | D4 | it moves to the next even release, with its record |
| **cross-lane integration** | IR-1 to IR-10 on a deploy carrying both lanes; the shared demonstration as the live vehicle for IR-4, IR-5, IR-6 and IR-9 | each one runs, or reports *not run* | G5, G6 | *not run* names the missing prerequisite, the contract affected, the evidence that is missing and the effect on the release claim. It is never counted as passed |
| **release evidence** | the cut's pre-registered set and shakeout; IR-10's regression pair; the cut record, saying what each lane's evidence does not cover | yes | G6 | no cut |

**The gates:**
- **G1:** Project Lifecycle Management stays proposal-only until the owner accepts it.
- **G2:** there is no integration branch until the owner opens one.
- **G3:** the Spark lane's compatibility review is recorded. It was met on 2026-10-17.
- **G4 to G7:** ruled 2026-10-17 (§2.5).

Changing any gate is the owner's decision.

### 6.3 What the release reads

| question | evidence | claimed or reported |
|---|---|---|
| Can SquadOps develop an independent external codebase, across an outside change? | the brownfield demonstration's two features; IR-3 | claimed, once read |
| Does it keep source identity right? | IR-5; the tests for contracts 1, 3 and 4 | claimed |
| Does it keep inherited failures apart from introduced ones? | IR-9; the check results' attribution (FR-20) | claimed |
| Can it create a greenfield Project and develop it? | the greenfield proof (E.4.6); IR-7 | claimed |
| Do the independent scenarios detect real differences, and reproducibly? | the window's discrimination reading, and each measure's spread on an unchanged tree (§1.3) | reported; it decides phase 2 |
| Do the readings tell improvement from regression? | contribution per increment; scenario regressions | reported |
| Is the evidence attributed correctly? | the evaluation records and their references (contract 5); IR-5 | claimed |
| Does holding out hold? | no scenario step in any authoring envelope or squad task's inputs (§1.3; IR-4) | claimed, or recorded as a finding |
| How the squad worked: cycle completion, cost and time per accepted increment, interventions, defects found, regressions caught | the per-increment scorecard (#1960), the intervention ledger, the issues filed, the frozen criteria and scenario regressions | reported, and never claimed as autonomy on its own |
| Does app quality improve across increments? | contribution and the quality deltas, per increment | reported. A claim needs a pre-registered comparison, as above |

Output volume and completed cycles alone are never evidence of autonomy. An autonomy reading travels with the quality
reading beside it (Outcome Evaluation §1).

---

## 7. The owner's decisions

| # | decision | status | the ruling (as recommended, unless the row says otherwise) |
|---|---|---|---|
| D1 | **the headline** | **ruled** 2026-10-16. Q35 added the MacBook lane's feature (2026-10-17) | **ruled 2026-10-16:** Outcome Evaluation leads; its design review comes early; phase 2 is conditional on phase 1's data; the entry points carry 2.4 if it moves. **Since then (2026-10-17):** the owner made Project Lifecycle Management the MacBook lane's 2.4 feature (Q35, PR #2401). D1 stands for the Spark lane's (§2) |
| D2 | **Outcome Evaluation's five questions** (its §8) | **ruled** 2026-10-17, as recommended. The Spark lane's intent from its #2401 review (the runner, the storage, the surfaces) is for this review; written into SIP-0113, accepted 2026-10-17, where A2 moves (3)'s Lighthouse and axe to the evaluator's image | **(1)** steps held out, goals visible, as drafted. **(2)** The supervisor drafts the first suite and the owner approves it, frozen before the window. **(3)** Lighthouse and axe in the QA image, with the lock files' audit. **(4)** The first work classes: increment count, PRD tier, and attended or unattended, declared in the objective. **(5)** Phase 2 in 2.4, conditional (D1, D4). Also rename the SIP's "outcome" term (§1.1) |
| D3 | **the window** | **ruled** 2026-10-17, as recommended. G7, ruled, freezes the window's deploy for both lanes | **four campaigns, two per stack, three increments each, on one frozen deploy,** pre-registered. With memory on and no build-side lesson approved, they double as SIP-0110's next build-side experiment |
| D4 | **phase 2's condition** | **ruled** 2026-10-17, as recommended | **the window's record shows:** the scenarios discriminate, holding out holds, contribution is not the acceptance count, and each measure phase 2 would gate is stable. The owner decides on that record |
| D5 | **the entry points** | **ruled** 2026-10-17, as recommended. The entry points are placed in 2.4.0 (SIP-0110) | **in 2.4 as placed,** in parallel. **Q29: conversation history's retention** is the owner's, set before #2180 ships: **ruled 2026-10-17** (SIP-0110 §A.8) |
| D6 | **#1966** | **ruled** 2026-10-17, as recommended | **the A/B in 2.4; adoption a separate ruling,** not before phase 2's decision |
| D7 | **#316** | **ruled** 2026-10-17, as recommended | **in 2.4, after its SIP's design review,** landing before the window's deploy freezes |
| D8 | **the 2.3 cut's output-quality findings** | **ruled** 2026-10-17, as recommended | **#2378's proper fix and #2153's build after the window,** each measured on the yardstick. **#2306 and #2253 as reads first.** **#1756 early,** as an instrument |
| D9 | **#2230** | **ruled** 2026-10-17, as recommended | **unplaced, deliberately,** with the owner's words of 2026-10-15, until the owner places it. Its SIP-0111 ledger row moved to unplaced in this plan's PR. Redirected by the owner on 2026-10-18 to the upgrade to TensorFold 1.x, and still unplaced (SIP-0111 §9m) |
| D10 | **the judgement steps (#557, #949, #950) and #1978** | **ruled** 2026-10-17, as recommended | **not in 2.4;** re-read at 2.4's cut |
| D11 | **who runs the line** | **ruled** 2026-10-17, as recommended. Q35 split the line into two lanes | **the supervisor runs the Spark lane, on the 2.3 line's terms:** build in §5's order, merge on green with main's run read, rebuilds and uncounted runs. The MacBook lane is run by its own session, on its own grant. **The owner's:** the SIP acceptances (Outcome Evaluation, #316, Project Lifecycle Management), opening the integration branch (G2), the first suite's approval, Q29, the phase-2 decision, lesson approvals, compose changes, and the tag and Release unless delegated at the cut |
| D12 | **when the lanes meet** (§2; the contracts and gates are Project Lifecycle Management's, ruled) | **ruled** 2026-10-17, as recommended | **(1)** The shared fixture first: the MacBook lane writes it, the Spark lane adds its recorded evaluation reference, and both review. **(2)** X-1 to X-3 are built by the Spark lane, which owns the sandbox, and reviewed by the MacBook lane: X-1 right after the fixture; X-2 before the brownfield demonstration unless its product is text-only; X-3 with phase 1's runner, including starting a pinned revision in a disposable copy. **(3)** The registry cutover deploys before the window's freeze if IR-1 has passed, otherwise after the window (G7). **(4)** The lanes agree where the demonstrations run; on the Spark, they run outside the window |
| D13 | **the shared demonstration** (§2.7) | **ruled** 2026-10-17 | **The owner's choice:** the proposed vehicle for the cross-lane scenarios (IR-4, IR-5, IR-6 and IR-9), not a release requirement. If it can't run, its scenarios report *not run* (G5) |
| D14 | **D1's fallback, now that Project Lifecycle Management is committed** | **ruled** 2026-10-17, as recommended | D1 made the memory entry points 2.4's headline if phase 2 moves, so that an even minor has a feature. Project Lifecycle Management now meets that on its own. **Recommended:** if phase 2 moves, the release's headline is Project Lifecycle Management, with phase 1 as the yardstick, and the entry points ship as placed and are claimed on their own acceptance matrix (#2183). This replaces D1's fallback |

---

## 8. What this plan does not decide

- **Outcome Evaluation's and #316's designs.** Each is decided at its own design review (D2, D7).
- **Project Lifecycle Management's design, contracts and gates.** Its SIP states them, and accepting it is the owner's
  (§2).
- **Whether phase 2 ships.** D4 sets the condition; the owner decides on the window's record.
- **Any change to a gate.** G1 to G7 are the owner's rulings, and only the owner changes them.
- **The window's and the cut's numbers.** Each is written as a pre-registration when its batch is built.
- **Any lesson.** Memory supplies nothing until the owner approves one (SIP-0110).
