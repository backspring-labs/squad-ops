# 2.4.0 plan — the yardstick first: Outcome Evaluation leads and measures before it changes anything, and Project Lifecycle Management develops products SquadOps doesn't own

**Status: DRAFT (2026-10-16), for the owner's review of §7.** The headline's shape is ruled. The owner, on 2026-10-16,
agreed to the supervisor's recommendation ("agree, draft the 2.4 plan that way after the cut"):
- Outcome Evaluation leads 2.4;
- its design review comes early;
- its feature half is conditional on its instruments' data arriving in the line;
- if that data is late, SIP-0110's memory entry points carry 2.4 as its feature.

This plan proposes everything else, and nothing starts before §7 is ruled. 2.3.1 cut on 2026-10-17.

**Revised 2026-10-17: Project Lifecycle Management is added** (§2). The owner made it 2.4's feature on the MacBook
lane (Q35, PR #2401), so the release carries one feature per lane. D1 stands for the Spark lane's. The SIP's §8.5
gives this plan its schedule, and the contracts and gates are the SIP's, ruled.

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

## 1. The headline: Outcome Evaluation (`sips/proposed/SIP-Outcome-Evaluation.md`)

### 1.1 The design review, first

The SIP is still proposed, and accepting it is the owner's design review. Its §8 asks five questions. This plan's
recommendations are in §7 (D2). The review comes before any of the SIP's code, and its answers become the accepted
text.

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
    (the Spark lane's intent for the design review, in its review of Project Lifecycle Management, PR #2401; SIP-0109
    §8.3's environment runs in the QA role's container, which would put the steps in a squad task's inputs);
  - results go in the package, as `passed`, `failed` or `blocked_unverified`;
  - a regression is read the way a broken frozen criterion is;
- **quality baselines:** Lighthouse, axe and lint per increment, with deltas from the previous accepted tree;
- **the intervention ledger's classifications** on the control log's rows;
- **in the digest:** each increment's outcome contribution, and the autonomy readings (AOR and the work envelope).

**Nothing in phase 1 changes a row, a gate or a prompt.** A scenario result reaches no squad role. This is the line's
first build, on branches, merged in reviewable steps, each with its wiring test and loaded check.

**The first suite** is authored outside the implementing roles. This plan recommends the supervisor drafts it and the
owner approves it (D2, the SIP's question 2), following the auditor rule the owner set for lessons: a frontier model
drafts, a person approves, and the squad's own model drafts none. The suite is frozen and content-addressed before the
window starts.

### 1.3 The measurement window: phase 1's data

Phase 2's thresholds have to come from measured noise, not guesses. So phase 1 runs on a window of campaigns,
pre-registered before the first one launches.
- **Recommended (D3):** four campaigns, two per stack, of three increments each, on one frozen deploy. The deploy is
  frozen for both lanes (Project Lifecycle Management's G7, ruled): neither deploys a change inside the window (§2.6).
- **They double as the next build-side memory experiment** (SIP-0110's ledger, unplaced; the 2.3 plan's D6 put it in
  2.4 beside Outcome Evaluation). That experiment needs multi-increment campaigns on both stacks with memory on and no
  build-side lesson approved, so memory observes and supplies nothing. The window's campaigns can be exactly that,
  which gives one set of campaigns two readings.

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
next even release with the record, and **the memory entry points carry 2.4 as its feature** (§3).

**SIP-0109 §24ap's deferred row joins phase 2:** accepted increments' `prd_delta` text to the proposer ("a 2.4
question", ruled 2026-10-03). It is the same seam: what the proposer is shown.

---

## 2. The MacBook lane's feature: Project Lifecycle Management (proposed, PR #2401)

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

A change to a file the other lane owns carries that lane's review.

### 2.2 What 2.4 carries, and its two demonstrations

These are the SIP's delivery slices (its E.4 and its delivery ledger):

| slice | what | in 2.4 |
|---|---|---|
| E.4.1 | registering an existing product: the writable registry cutover, its tested rollback, the proof that existing projects are unchanged (IR-1), and the minimum enrollment | yes |
| E.4.2 | discovering the repository's own instructions and capturing its inherited baseline, with the start declaration (contract 7) | yes |
| E.4.3 | the first scoped feature through the shared cycle path (IR-2) | yes |
| E.4.4 | the second feature, after an outside contribution | yes |
| E.4.5 | lifecycle completeness: update history, archive and restore, concurrency and conflict recovery | **no:** required before the SIP closes, not in 2.4 (the owner, 2026-10-17) |
| E.4.6 | creating a greenfield Project at an owner-approved destination | **yes, shipped by the cut** (G6, the owner's ruling) |
| E.4.7 | writing in place in an existing checkout | optional |

**The order:**
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

| contract | in brief |
|---|---|
| 1. Project identity and source revision | one registry for every reader. Outcome Evaluation records the identity of the tree it evaluated, never a Git commit |
| 2. `prepare_cycle()` and Campaign admission | each lane adds its own typed fields. Outcome Evaluation adds nothing at `prepare_cycle()` and pins its suite on the campaign |
| 3. `WorkspaceStore` | a Git checkout becomes the live tree through the sandbox's own seeding. No scenario runs against a live tree |
| 4. Campaign accepted trees | SIP-0109's identity, mapped to the Git revision it became |
| 5. outcome references | Project history stores Outcome Evaluation's evaluation ID and suite digest. No outcome result reaches a squad role before phase 2, and after it only the proposal run |
| 6. project instructions | SIP-0110's one store and its binding. #2179 changes this seam in 2.4 too |
| 7. starting the product | the Development Configuration declares install, build, start, readiness and entry points. Outcome Evaluation reads the declaration and never infers one (approved by the owner as written, 2026-10-17) |

**The shared fixture lands first** (its §8.2.3).
- **What it is:** one small product with its own layout, its own native commands, one check that fails before any
  change, and one binary file.
- **What comes with it:** each lane's recorded outputs. Each is recorded valid, with a field missing, with an unknown
  schema version, and with a stale commit.
- **How it lands:** as one PR both lanes review, before either lane's first contract PR.
- **Recommended (D12):** the MacBook lane writes it, and the Spark lane adds its recorded evaluation reference in the
  same PR.

**Every PR that changes a shared contract** must:
- name the contract;
- carry the other lane's review;
- add a wiring test that enters where the live cycle does;
- only add, never repurpose or remove (G4).

### 2.4 The three sandbox changes (its §8.2.2)

The sandbox is the Spark lane's. **Recommended (D12):** the Spark lane builds all three, and the MacBook lane reviews
each one as its consumer (G4).

| change | what it fixes on `main` | what needs it | when |
|---|---|---|---|
| **X-1:** a revision origin for a Git checkout | `RevisionOrigin` is a closed set (`src/squadops/sandbox/models.py:23`), and a revision with any other origin is refused (`:103`) | E.4.2 can't seed a checkout without it | first, right after the fixture: E.4.2 waits on it |
| **X-2:** binary files | seeding, reading the tree and persisting revisions handle UTF-8 text only (`src/squadops/sandbox/workspace.py:205`). Until X-2 ships, a product with binary files is refused at seeding, with that gap named | most real repositories carry some binary files (images, fonts) | before the brownfield demonstration, unless its product is text-only. Every existing revision ID stays the same: hashing the raw bytes gives today's digest for UTF-8 text |
| **X-3:** a product's own commands | `ExecutionSandboxPort` (`src/squadops/ports/sandbox.py:33`) runs the environment's fixed install, build, test and start commands | contract 7: Outcome Evaluation starts an external product from its declaration | with Outcome Evaluation's runner, before IR-6 |

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
  - **Recommended (D12):** before the freeze if IR-1 has passed, otherwise after the window.
- **The demonstrations need a live deploy.** The lanes agree where they run: on the Spark, or on the MacBook's own
  deploy. If they run on the Spark, they run outside the window (D12).
- **Project Lifecycle Management's slices run on the MacBook lane's own schedule.** This plan fixes only where they meet
  the Spark lane:
  - the fixture comes first;
  - X-1 comes before E.4.2;
  - the cutover never deploys inside the window;
  - the integration scenarios run once the owner opens the integration branch.

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
- **Q29: conversation history's retention** is set before #2180 ships (D5).
- **They change squad behaviour only through approved records.** A task or project instruction reaches the squad
  only when the operator writes one. The window's campaigns write none, so the entry points don't touch the window's
  readings.

**If phase 2 moves,** the entry points are the release's headline feature. #2183's acceptance matrix, live, is then
the headline's evidence.

---

## 4. Riding along

### 4.1 In 2.4 (recommended)

| item | what | when in the line |
|---|---|---|
| #316, the request-profile taxonomy (`sips/proposed/SIP-Cycle-Request-Profile-Naming-Taxonomy.md`) | names drawn from one axis, with old names resolving as aliases (Q13) | its SIP's design review early; the rename lands before the window's deploy freezes, so the window runs on the final names |
| #1966, risk-first QA and builder instructions | an A/B on replayed increments (#1959), read on the per-increment scorecard (#1960) and the window's scenarios | **the A/B runs in 2.4; adoption is a separate ruling, not before phase 2's decision,** so the release doesn't change two squad behaviours at once and lose both readings |
| #2378's proper fix | an endpoint declares its query parameters as a field the scaffold, QA's prompt and the probes read | after the window, each output-quality change measured on the yardstick, pre-registered as 2.3's #2202 and #2205 comparisons were |
| #2153's build | a failing slot assertion routed by demonstrated defect ownership (SIP-0104 §13d), now that SIP-0110's window has closed | after the window, as above |
| #2306 | a converging repair ended as a plan defect: read the 12 recent terminations first, then fix | the read early; the fix after the window if the read finds converging repairs |
| #1756 | the full rendered request stored once per generation, readable by id, with the redaction applied | early, as an instrument: it reaches the seams the authoring envelopes don't |
| #2253 | QA's output budget: read the headroom across every recorded `qa.test` call, then decide | the read early; any budget change only between measurements, named in the record |

### 4.2 Not in 2.4 (recommended)

| item | why | where |
|---|---|---|
| #557, #949, #950: the judgement steps | they follow Outcome Evaluation and are measured on it, and 2.4 already changes the proposer. Adding judgement steps would make neither change readable | 2.5 or later, re-read at 2.4's cut |
| #2230, Qwen3.8-Flash-Next on TensorFold | the owner on 2026-10-15: "no second tensorfold candidate at this time" | **unplaced, deliberately,** with the owner's words, until the owner places it (D9) |
| #1978, test-first verification | "after Outcome Evaluation's baseline": it needs phase 1's data first | 2.5 or later |
| #1965, the framework suite's test-value audit | the crew's first optimization experiment, an outer-loop item with no 2.4 dependency | the owner's to place |
| the squad authoring its own backlog | portfolio Q1: 2.6, with its own SIP. The squad chooses features only once there's an independent measure of whether a feature helped | 2.6 |
| #2184, retiring the legacy store | placed 2.5.0 (SIP-0110) | 2.5 |
| #2286, TensorFold operator keys | credentials: the owner's to place | the owner |
| #2287, a box-level operator lease | no 2.4 dependency | the owner's to place |

---

## 5. Sequencing: the box is the constraint

Most of the work is code. The box's time goes to the window, the reads and the cut.

1. **2.3.1 cuts first.** Done, 2026-10-17.
2. **The design reviews,** Outcome Evaluation's and #316's, as two PRs with the owner's rulings recorded, and the
   owner's acceptance of Project Lifecycle Management (PR #2401). No box time.
3. **The shared fixture,** one PR both lanes review (§2.3), **then X-1** (§2.4).
4. **Phase 1's build, #316's rename, #1756, and the entry points' first rows,** on branches, merged in steps. Each
   rebuild runs its regression pair and its loaded checks, as 2.3's rounds did. **X-3 is built with phase 1's runner,
   and X-2 before the brownfield demonstration.** Project Lifecycle Management's slices run on the MacBook lane's
   own schedule (§2.6).
5. **The early reads:** #2306's terminations and #2253's headroom. No box time; they read stored records.
6. **The window's pre-registration, then the window:** the suite frozen, the deploy frozen for both lanes (G7), four
   campaigns. The registry cutover deploys before the freeze or after the window (§2.6).
7. **The owner's phase-2 decision** on the window's record (D4). Then either phase 2's build and its own pre-registered
   reading, or the record that moves it.
8. **The output-quality changes** (#2378, #2153, #2306's fix if any), each measured on the yardstick.
9. **#1966's A/B** on replayed increments, at any point after the window, read on its scenarios.
10. **The entry points' acceptance matrix, live** (#2183), on the final deploy.
11. **The integration scenarios** IR-1 to IR-10, once the owner opens the integration branch (G5).
12. **The cut:** a pre-registered set and shakeout, written when the last batch is built, as 2.0–2.3 did, with G6's
    conditions: the integration scenarios passed or *not run*, the brownfield demonstration read, and greenfield shipped.

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

---

## 6. What the release claims, and what it does not

**If phase 2 ships,** the claim is that a campaign can be read by its outcomes. Its success is a declared outcome
target met with a quality baseline held, and the proposer aims at what still fails. The evidence is the window's
record and phase 2's own reading.

**If phase 2 moves,** the claim is the entry points: an operator's instruction reaches the task it names and only
that task, and chat works on the memory substrate. The evidence is the acceptance matrix, live. Phase 1's instruments
still ship as reporting only, so the release carries the yardstick either way.

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

---

## 7. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| D1 | **the headline** | **ruled 2026-10-16:** Outcome Evaluation leads; its design review comes early; phase 2 is conditional on phase 1's data; the entry points carry 2.4 if it moves. **Since then (2026-10-17):** the owner made Project Lifecycle Management the MacBook lane's 2.4 feature (Q35, PR #2401). D1 stands for the Spark lane's (§2) |
| D2 | **Outcome Evaluation's five questions** (its §8) | **(1)** steps held out, goals visible, as drafted. **(2)** The supervisor drafts the first suite and the owner approves it, frozen before the window. **(3)** Lighthouse and axe in the QA image, with the lock files' audit. **(4)** The first work classes: increment count, PRD tier, and attended or unattended, declared in the objective. **(5)** Phase 2 in 2.4, conditional (D1, D4). Also rename the SIP's "outcome" term (§1.1) |
| D3 | **the window** | **four campaigns, two per stack, three increments each, on one frozen deploy,** pre-registered. With memory on and no build-side lesson approved, they double as SIP-0110's next build-side experiment |
| D4 | **phase 2's condition** | **the window's record shows:** the scenarios discriminate, holding out holds, contribution is not the acceptance count, and each measure phase 2 would gate is stable. The owner decides on that record |
| D5 | **the entry points** | **in 2.4 as placed,** in parallel. **Q29: conversation history's retention** is the owner's, set before #2180 ships |
| D6 | **#1966** | **the A/B in 2.4; adoption a separate ruling,** not before phase 2's decision |
| D7 | **#316** | **in 2.4, after its SIP's design review,** landing before the window's deploy freezes |
| D8 | **the 2.3 cut's output-quality findings** | **#2378's proper fix and #2153's build after the window,** each measured on the yardstick. **#2306 and #2253 as reads first.** **#1756 early,** as an instrument |
| D9 | **#2230** | **unplaced, deliberately,** with the owner's words of 2026-10-15, until the owner places it. If ruled, its SIP-0111 ledger row moves to unplaced in this plan's PR before it merges |
| D10 | **the judgement steps (#557, #949, #950) and #1978** | **not in 2.4;** re-read at 2.4's cut |
| D11 | **who runs the line** | **the supervisor runs the Spark lane, on the 2.3 line's terms:** build in §5's order, merge on green with main's run read, rebuilds and uncounted runs. The MacBook lane is run by its own session, on its own grant. **The owner's:** the SIP acceptances (Outcome Evaluation, #316, Project Lifecycle Management), opening the integration branch (G2), the first suite's approval, Q29, the phase-2 decision, lesson approvals, compose changes, and the tag and Release unless delegated at the cut |
| D12 | **when the lanes meet** (§2; the contracts and gates are Project Lifecycle Management's, ruled) | **(1)** The shared fixture first: the MacBook lane writes it, the Spark lane adds its recorded evaluation reference, and both review. **(2)** X-1 to X-3 are built by the Spark lane, which owns the sandbox, and reviewed by the MacBook lane: X-1 right after the fixture; X-2 before the brownfield demonstration unless its product is text-only; X-3 with phase 1's runner, including starting a pinned revision in a disposable copy. **(3)** The registry cutover deploys before the window's freeze if IR-1 has passed, otherwise after the window (G7). **(4)** The lanes agree where the demonstrations run; on the Spark, they run outside the window |

---

## 8. What this plan does not decide

- **Outcome Evaluation's and #316's designs.** Each is decided at its own design review (D2, D7).
- **Project Lifecycle Management's design, contracts and gates.** Its SIP states them, and accepting it is the owner's
  (§2).
- **Whether phase 2 ships.** D4 sets the condition; the owner decides on the window's record.
- **The window's and the cut's numbers.** Each is written as a pre-registration when its batch is built.
- **Any lesson.** Memory supplies nothing until the owner approves one (SIP-0110).
