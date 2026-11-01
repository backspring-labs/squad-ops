# 2.6.0 plan — a multi-hour Campaign on the owner's own product

**Status: §0 ADOPTED for the weekend spike (2026-10-30); everything else a DRAFT.** The owner: "merge both once
appropriate", after two outside review passes, each applied in full. D1–D15 stay open, and §0's readings revise the
plan after the spike. §8 lists what the outside reviewer was asked to challenge.

**Revised 2026-10-30, the same day:** the owner asked to incorporate the 2.5.1 fix line's assumptions. §1a names the
ten defects 2.6 assumes 2.5.1 fixes, with a fallback rule if one slips; they leave §2's tracks, and D11 rules the split.

**Revised a fourth time the same day: a CLI spike first** (§0). A narrowed 2.5.1 with #2818 moved into it, then one
attended Campaign on the owner's product from the CLI, before any 2.6 feature.

**Revised a third time the same day: the crew drives.** The owner: "By buzz convo, what I meant was interacting
with the Nostromo crew driving the campaign execution and outcome assessment. They can determine if outcomes are
being met or if squad ops framework bugs or functional gaps need to be covered to advance the app building work. Not an
embodiment of squad ops agents in buzz." So the crew is an API client: the headline's slice 5 is its surface and its
assessment record; the overnight identity is the crew's existing broker principals (D7); notices are the crew's
watcher's; the Campaigns plugin is read-only (D13); and the crew's own changes are named as a dependency (D14).

**Revised again the same day: the headline is a new SIP,** Project Goals and Backlog (PR #2833), on the owner's
direction that a Project's goals and expected outcomes be "persisted in db records of the project definition", with
Buzz as "the collab and convo on achieving those goals", MECE across the tools, and "get away from a claude terminal to
build apps and games". Track D becomes that SIP's slices (§2.4), and D1, D5 and §8 follow. The owner told the
supervisor to "do what you think is best" with it.

**The owner's goal for 2.6** (2026-10-30, spelling corrected): "aggressively focus on the ability to drive a multi hour
campaign that will enhance and improve a real application", with "features that will provide the best chance of a
multi-hour iteration of a campaign for an external application (not our sample apps)". The owner named two domains:
a Roblox game and a financial application. Game-development skills are a separate proposal (PR #2405).

**What 2.6 is.** An even minor, a feature release, gated by at least one headline feature SIP (CLAUDE.md, #281). This
draft proposes one headline and no second: **Project Goals and Backlog** (PR #2833, proposed). A Project's goals,
expected results and ordered backlog become versioned records in SquadOps, edited in the console, discussed in Buzz,
and worked through by a Campaign one item per increment (§2.4, D1). **It stands on a floor:** a Campaign on a
repository-backed product that can accept an increment, carry itself past a failure and run unattended, built as the
completion of SIP-0109 (Campaign Orchestration) and SIP-0112 (Project Lifecycle Management) with numbered amendments
(Tracks A to C). Everything in §2 is chosen by one test: does it remove a reason a product Campaign stops before it
has run for hours, or a reason the owner has to drive it from a terminal?

**The question it answers:**

> **Can a Campaign on a product the owner actually wants built run for hours, accepting increments onto its campaign
> branch, carrying itself past its own failures, and stopping only for reasons it names, with the owner touching it
> only at the points this plan declares?**

**This replaces the ROADMAP's 2.6 row** ("the squad-authored backlog (no SIP yet)"), if adopted. The backlog part is
kept, narrowed to the owner-ordered half: the squad records candidates, and the strategy role ordering its own
features waits (§2.4, D5). The ROADMAP and `sips/PORTFOLIO.md` change in the PR
that adopts this plan, not in this draft.

---

## 0. The first step: a CLI spike on 2.5.1, before any 2.6 feature

**Added 2026-10-30 at the owner's request,** with a quarter of the owner's weekly usage left: "Could I complete a 2.5.1
fix line and a very minimal slice of 2.6 to attempt a campaign for real via cli and not require the full front-end
capability?" The rest of this plan stands as the line's design. This section is what runs first.

**The weekend shape, recorded 2026-10-30** (the owner: "add the dependency and stop at three", with 22% of the
weekly usage left). This narrows the table below for the weekend:
- **2.5.1 this weekend is #2818 and #2824 only,** merged and deployed, with no release cut. #2817, #2814, #2804, #2809
  and #2813 follow next week with the cut. Shelfnote's plain pytest config and backend-only items don't reach them; if
  the spike does, that is its finding.
- **No 2.6 feature this weekend.** This plan and the SIP stay as written; the spike's readings revise §0.
- **The product is `z_shelfnote`**, not the financial application: already a configured product on the same
  `fullstack_fastapi_react` template, as a dress rehearsal. **One commit before the Campaign** makes its existing code
  use a library the QA image lacks (checked first), so the in-cycle run needs the product's own install, which is
  #2818's case. It must be in the baseline: an increment that adds a dependency is a separate, unplaced gap (SIP-0109's
  "an increment that needs packaging changed"). The push needs the owner's OK.
- **Three backlog items,** backend-only: search (`GET /books?q=`), reading status (with a 422 for an invalid one) and
  tags. `target_accepted_increments: 3`.
- **The Nostromo crew drives the Campaign** through its existing harness, on its own provider budgets, once the owner
  approves the definition in Buzz; Ripley answers the plan gates #2796 escalates. The supervisor builds, deploys,
  prepares the product and reads the result.
- **#2818 gets one outside review** through the owner's reviewer, from a packet on its PR.
- **Stop points:** after #2818, if little usage is left (the crew can run the Campaign later); after the product's
  runner check, if it fails; and two Campaign rounds at most.

**The idea.** 2.5's product Campaigns were stopped by a short list of defects, not by missing features (§1). Fix
those, and an attended Campaign on the owner's own product can run on today's machinery from the CLI, with no goal
set, no console work and no unattended running.

| step | what | notes |
|---|---|---|
| 1. **2.5.1, narrowed to the Campaign's path** | **#2818** first (a product's in-cycle tests on its own runner in the sandbox, D4's shape, moved from 2.6 into the patch), then **#2824**, **#2817**, **#2814**, **#2804**, **#2809**, **#2813** | #2818 is labelled a bug, and its shape reuses the setup acceptance already runs. §1a's other four (#2798, #2765, #2830, #2402) move to a later patch: none is on a Campaign's path |
| 2. **deploy main, then the loaded checks** | `rebuild_and_deploy.sh`, then `verify_loaded.py` | no release cut is needed to run; 2.5.1 is cut when it's cheap to |
| 3. **the proving Project** | the financial application, created greenfield from the `fullstack_fastapi_react` blueprint (the path `z_shelfnote` proved); configure, baseline. **Synthetic data only** (D10) | |
| 4. **the goals by hand** | a structured requirements file in the product's repository: the goal, expected results, an ordered backlog, out of scope (the shape of Project Goals and Backlog §4, PR #2833). The Campaign names it as `objective.requirements: repo:file:<path>@current`, with `target_accepted_increments: 3`. **The first three backlog items are backend features with API-level criteria,** since a page criterion for an added page still meets #2799 | slice 1 later loads its goal set from this file |
| 5. **an attended Campaign** | driven by the owner from the CLI, or by the Nostromo crew through its existing harness (which needs no D14 change for a requirements-based definition). Every product plan gate escalates (#2796), so whoever drives answers each from the requirements | no held-out suite: the owner, or the crew's closing interpretation, judges the outcome |

**The product-runner path, and why it needs no #2421 work** (the outside review's blocker, 2026-10-30). #2421's
declared-commands half **shipped in 2.4**: a product's declared command run against a pinned revision in a disposable
copy (SIP-0102 X-3a, PR #2447), and a product started from its declaration (X-3b, PRs #2450 and #2474). Acceptance on
the product's runner already uses it: `RunnerSetup` (`src/squadops/campaigns/runner_acceptance.py:209`) runs the
runner's argv in the configuration's working directory after its install and build steps. **#2818 routes the
in-cycle suite run and its retest through that same path.** Only #2421's secrets remainder is open, and the spike
needs no secret (synthetic data, D10). This draft's §2.1 listed the declared-commands half as unbuilt; that row was
wrong and is removed.

**The spike's prerequisites,** checked before the Campaign is created:
- the financial application's Development Configuration records its install and build steps, its test runner and
  its start declaration, and `projects configure` reports no blocking gap;
- `projects baseline --capture` succeeds, so the product's own checks run in the sandbox with that setup;
- the deploy carries step 1's fixes, read by `verify_loaded.py`;
- **a criterion-capable runner** (the second outside review): no blocking gap and a clean baseline don't show that
  one criterion can be judged, because `runner_not_scopable` and `no_test_id_reader` are disclosed gaps that refuse
  nothing (`src/squadops/projects/derived_profile.py:64-65`), and acceptance can't credit a criterion without them.
  So `projects show` must name, for the runner that covers the planned criterion files, a suite command, a
  single-file command, and the pytest test-id reader. A configuration check, not a feature.

**What the first criteria look like:** each API criterion exercises the app's existing client against an endpoint and
fails **on a behaviour assertion** on the accepted tree. A test that imports a module the change adds fails at setup
on the baseline and can't discriminate (`src/squadops/campaigns/acceptance.py`, `SETUP_CLASSES`). Nothing a
criterion asserts may already hold through FastAPI's default 404. Whoever rules the proposal returns one that breaks
either rule.

**What each round records,** so a failed round still teaches something:
- **the product setup:** the configuration revision, each install and build command and how it ended;
- **the in-cycle test:** the runner, its argv, and the pass, fail and setup-failure counts, on the product's runner;
- **the acceptance result:** each criterion's discrimination reading and the verdict, with the row it took;
- **the promotion:** the campaign branch's commit after an accepted increment;
- **the stop:** what ended the round, by control-log row, with the issue filed for any defect.

**Stop rule:** at most two Campaign rounds. A live run usually finds the next seam (2.5's did four times). If round
2 finds a new defect, it is filed and the spike stops, with what it learned recorded.

**What it reads:** rung 1 of §4, **an accepted increment** on a product, promoted onto its campaign branch, and
whether rung 2 (three in one Campaign) is in reach on today's machinery. **An accepted increment is the squad's
criteria passing on the product's runner. It is not evidence that the app's expected results improved:** the spike
has no held-out suite, and §4 reserves that reading for later. **Its result is scoped** to the
`fullstack_fastapi_react` stack, a greenfield product and synthetic data. **What it doesn't:** anything unattended, the goal
set, the console, or the held-out yardstick.

**What it changes in the rest of the plan:** §1a's 2.5.1 list is replaced by step 1's (D11), and #2818 leaves Track A.
Everything else in §2 waits for the spike's reading, which may reorder it.

### 0a. The second spike: a crew-driven Campaign, steered from Buzz, on outcome goals

**Added 2026-11-01 at the owner's request,** with about 10% of the owner's weekly usage left. Spike 1's readings
(`var/verification_sets/2-6-0-spike/readings.md`) went past its stop rule: the overnight run `cmp_828bfc06aa63` accepted
10 of 10 items unattended. Every one of those runs was launched and steered from a terminal. Spike 2 asks the next
question, and changes what the squad is given.

**What the crew's first attempts showed (2026-11-01).** Four crew-launched Shelfnote Campaigns were aborted. The
last, `cmp_7c4c28bb4118`, was launched from a plain-language request and approved by the owner's one-word reply
(Nostromo PRs #27 and #28):
- **Ripley over-ruled the increment gate.** She returned the proposal twice:
  - first for exact rules on `GET /books?q=`;
  - then for "a seam table covering every evaluator", which is the engineering discipline in her prompt for her
    own repository work, not a bar for a squad's proposal.
  Two revisions used up `max_proposal_revisions`, and v3 escalated.
- **The owner had no way to answer from Buzz.** In the owner's words: Ripley "was holding the campaign and not a
  clear way for me to approve moving forward", and "her changes requested seem like things that should go in a
  framing plan".
- **The goals weren't read.** Each crew draft said Shelfnote's `goals.md` was unreadable and recovered the list from an
  older Campaign. Ripley's first request was item 1 of that file, word for word.
- **A busy box parked the Campaign.** On `cmp_4edfa3d9746b`, SquadOps refused the launch because the crew's own
  call was on the shared engine. That is fixed by #2852 (SIP-0109 §24cu). Nostromo then parked the Campaign on the
  transient `launch_blocked` and had no way back.

**The goals are outcomes, not a specification.** The owner, reading Shelfnote's `goals.md`: "those aren't really
goals in my opinion, these are very specific technical changes".
- **Where the file stands.** Its Goal and E1–E5 are goals. Its backlog fixes endpoints, status codes, orders and a
  CSV header. Those were written there so unattended criteria would discriminate. That is part of why the overnight
  run went 10 of 10, and it means that run showed the squad implementing a specification, not turning a goal into
  a design.
- **The change.**
  - The goals and the backlog are written as reader outcomes, one line per item, with no endpoint or status code.
  - The squad's framing plan turns each item into behaviour, endpoints and tests.
  - The increment gate asks only whether the plan serves the item, stays in scope and can be tested.
  - This is the split Track D's SIP already describes (PR #2833): goals and backlog are the owner's; the technical
    design is framing's output.
- **What it costs.** Without exact behaviour handed to it, the squad has to design criteria that still fail before
  the change. Expect lower acceptance at first. That is the reading this spike exists to take.

**Before the launch.**
1. **Nostromo** (the Nostromo session's work, on the owner's prompt):
   - **Ripley's rubric.** She returns a proposal only when it is out of the item's scope, can't be tested, or
     contradicts the goal or an accepted increment. How-to-build detail is an approval with notes for framing. Her
     design discipline stays with her own repository work.
   - **Escalations answered in Buzz.** Mother asks a plain question with the choices, and the owner's reply rules.
   - **Goals read live.** Drafting reads the product's current goals. If it can't, it says so and stops; it never
     substitutes an older list.
   - **`launch_blocked` is not a park.** SquadOps retries it.
2. **SquadOps:** the increment ruling's notes reach that increment's framing run as reviewer guidance.
   - What is known: a gate's `approved_with_refinements` notes are kept as an artifact, and "nothing renders them to
     a model" (`execution/workload_gate.py`).
   - What is unverified: whether an increment ruling's notes reach the framing run at all. That is checked first.
   - Without this, Ripley's notes would be dropped, so it lands before the run.
3. **Shelfnote:** its `goals.md` is rewritten in outcome form. The goal, E1–E5 and the out-of-scope list stay. The
   ten backlog items become one reader outcome each, in the same order.

**The run.**
- First, a small Campaign (3 increments), asked for in Buzz: "@Mother start a small campaign on ShelfNote, search
  first."
- If it closes clean, the 8-increment run, unattended, overnight.

**What it reads.**
- **Launched, ruled and closed with no terminal step.** Any escalation is answered by one Buzz reply.
- **At least 2 of the 3 increments accepted.**
- **Ripley's notes visible in the framing plan** of the increment they were about.
- **Each criterion's discrimination reading.** The squad's own criteria have to fail before the change without a
  specification to copy from.

**What it doesn't read:** the held-out yardstick, a real-size product, or Nebulus. **Stop rule:** as spike 1's. A
round that finds a new defect files it and stops, with what it learned recorded here.

**How each objective advances this plan.** The owner, 2026-11-01: "make sure you are tracking these spike objective
against the existing 2.5.1 and 2.6 plans so we are advancing to the same common plan goals". The spike adds no goal
of its own. Each objective is a piece of a track or a rung below, and its result is read back there.

| spike objective | advances | what the reading feeds |
|---|---|---|
| launched, ruled and closed from Buzz, no terminal step | §4 rung 3 ("the owner works through the crew in Buzz… not a terminal"); §2.3 Track C and D14, the crew dependency | §2.3's **unverified** question, whether the crew's harness (which parks on any missing evidence, worker error or blocking review) can run unattended for hours, is read on this run instead of on the first proving run |
| an escalation answered by one Buzz reply | §1's third person-at-every-turn item ("resuming an escalation is admin-only"); D6's declared touchpoints | each escalation's class and who answered it, which §4 says every run records |
| Ripley rules on scope, can it be tested, and the goal; design detail goes to framing as notes | §1's first item (every plan gate escalated on a product); §2.2 Track B, a Campaign that carries itself past a failure | the escalations by class, and whether `max_proposal_revisions` is still the row that stops a run |
| Ripley's notes reach the increment's framing run (SquadOps) | §2.2 Track B | is filed as an issue once its current behaviour is checked, sized there, and lands before the run |
| goals and backlog as reader outcomes; design in framing | §2.4 Track D, the headline: the SIP's MECE split (intent in the goal set, design in framing). Until slice 1 lands, Shelfnote's `goals.md` stands in for the goal set, as §2.4 already allows | the first evidence for D8's claim that a Project's goals can be written as outcomes and still produce accepted increments |
| the squad's own criteria discriminate without a specification | §1's second item (the same non-discriminating criterion proposed three times); D9's early criterion check; #2613 | whether D9 is needed before rung 2, from the discrimination reading of each criterion |
| a small Campaign, then the 8-increment overnight | the shape of §4 rungs 2 and 3, on Shelfnote, not the proving Project | a rehearsal, not a rung: rung 2 needs the proving Project (§2.6 Track F), and rung 3 also needs the held-out threshold and the console (§2.7 Track G) |

**What it does not advance:** §2.5 Track E (the scripted squad), §2.6 Track F (Nebulus and its held-out suite),
§2.7 Track G (the console) and §2.4's slices themselves. Those stay sequenced as §3 has them.

**Against 2.5.1** (D11, §1a): spike 1's fixes and #2852 are the 2.5.1 patch so far, recorded under `[Unreleased]` in
`CHANGELOG.md`. Spike 2's SquadOps item is a 2.6 change, not a patch (§1a: "2.5.1 is not a feature release"). The
rest of 2.5.1 (#2817, #2814, #2804, #2809, #2813, #2798, #2765, #2830, #2402, #2839) is not advanced by the spike,
and still decides the 2.5.1 cut.

---

## 1. Why 2.5's product Campaigns lasted under an hour

2.5 ran six Campaigns on two repository-backed products (`z_continuum`, `z_shelfnote`). **None accepted an increment.**
The longest ran 48 minutes. Every one stopped at a defect, not at a limit or the end of its work.

| Campaign | where it stopped | the cause | class |
|---|---|---|---|
| `cmp_e9485af88196` (`z_continuum` round 1) | the first `qa.test` | the binding budget counted the whole product tree, about 105k tokens, against a 65,536-token window (#2805, fixed by #2807) | the product's size |
| `cmp_1399cc189ef5` (round 2) | the development repair | the same class in the repair contract (#2810, fixed with a guard over every task type) | the product's size |
| `cmp_ce4c95f2f307` (round 3) | `qa.test` | the qa run lacked the product's tree (#2815, fixed by #2816), then its dependencies: `tomli` is not in the qa image (#2818) | the product's environment |
| `cmp_73535ccef891` (`z_shelfnote`) | acceptance on the product's runner | a vitest test of a page the change adds can't load on the accepted tree, so it reads `only_setup_failures` (#2799) | the product's environment |
| `cmp_725a9e2ee446` (cut repeat, `z_shelfnote`, 34 min) | the same, on the increment and its repair | #2799 again | the product's environment |
| `cmp_d30d964599df` (cut repeat, `z_continuum`, 48 min) | the repair's launch | #2818's class failed the increment; the repair couldn't be built, because the approved proposal was a revision (#2824) | the Campaign's continuation |

Records: `var/verification_sets/2-5-0-demonstrations/z_continuum-rounds.md`, `…/z_shelfnote-readings.md`,
`var/verification_sets/2-5-0-cut/repeats.md`.

**Beside the stops, three things needed a person at every turn:**
- **Every plan gate escalated** on a product: the plan-review tier can establish nothing without an interface manifest,
  and a product has none (#2796). The supervisor answered each from the requirements, within a minute.
- **The squad proposed the same non-discriminating criterion three times** (an unknown id answers 404, which
  FastAPI's own 404 meets). The owner ruled a manual rule mid-run ("Return such a criterion"), since one more
  abandonment would have ended the Campaign at `max_unaccepted_increments`.
- **Resuming an escalation is admin-only** (`campaigns:control`), and a CLI session lasts at most 8 hours with a
  30-minute idle limit (#2760). An overnight Campaign that escalates waits for the owner.

**So the order of work follows the order of the stops.** A Campaign can't last hours until one increment is accepted
on a product (§2.1). It then needs to carry itself past an ordinary failure (§2.2), to run without a person at each
gate (§2.3), and to have enough right-sized work to keep going (§2.4). The machinery's own durability over hours is
checked without a model first (§2.5), so a long run's failure can be attributed.

---

## 1a. What 2.6 assumes 2.5.1 fixes first

> **Superseded by §0's seven** (D11, revised 2026-10-30): #2818, #2824, #2817, #2814, #2804, #2809 and #2813 are
> 2.5.1. The table below is kept as the reasoning for each; #2798, #2765, #2830 and #2402 go to a later patch.

**2.6 is planned on top of a 2.5.1 patch** (D11). The 2.5 cut left small defects that need no design, several of them
on the product path §1 traces. They ship as a patch, not as 2.6 features, so 2.6 starts from a product path whose
known defects are fixed and its tracks hold only the work that needs design or is new. No 2.5.1 list existed before
this draft; this is the proposed one.

| issue | what 2.5.1 fixes | why 2.6 depends on it |
|---|---|---|
| **#2824** | a repair or retry binds the cycle's approved proposal version, not the launch block's first | ended the cut's `z_continuum` repeat. Any Campaign whose returned proposal's revision fails needs it to carry on (Track B) |
| **#2817** | the product's own pytest configuration can't stop or redirect the squad's suite, and runner patterns match only under their roots | a real product's pytest config will be richer than `z_continuum`'s two keys |
| **#2814** | the JS/TS structural resolver reads files past about 257 lines | a real product's files are longer; past that length an anchored edit can't resolve |
| **#2804** | a criterion file the merge gave to qa is matched by a cwd-relative argv or a glob, not only its named path | a product's typed checks name paths every way |
| **#2809** | qa.test's monolithic prompt path is measured through the shared rendering | the binding-budget class (#2805, #2810) that stopped two 2.5 rounds |
| **#2813** | the anchored-edit retry's refusal lines are counted in the repair's binding budget, and the repair's call has a prompt guard | the same class, in the repair |
| **#2798** | a declared start that never became ready says what its readiness URL last answered | an unattended run's start failure has to be readable from the record |
| **#2765** | a scenario diagnostic's evaluation isn't stored as the real cycle's | the proving Project's suite validation would otherwise overwrite its cycles' latest evaluation |
| **#2830** | the release attach scans for held-out content, not only credentials | 2.5.1's own cut uploads records; each cut has needed this by hand |
| **#2402** | `run_prose_lane.sh` runs under macOS's bash 3.2 | no run depends on it; it's small and it's a defect |

**What these assumptions mean for 2.6:**
- **The 2.5.1 claim is narrow.** Each fix is read by replaying the stored envelope or record that found it, plus the
  regression suite. No product Campaign is run for the patch: the live reading of #2824, #2817 and #2814 is 2.6's
  phase 4 shakeout (§3), on the deploy that carries them.
- **A fallback rule.** An item not in a released 2.5.1 when 2.6's Track A starts moves into Track A, sized as above,
  and the cut record names it. Nothing in 2.6 is deferred because 2.5.1 slipped.
- **Not in 2.5.1, because each needs design:** #2818 (D4's shape), #2799 (a loader a product's bundle carries), #2796
  (what a product's plan gate reads), #2613 and #2612. They are 2.6's.
- **2.5.1 is not a feature release,** so nothing in §2 lands in it, and 2.6's box time isn't spent on the patch beyond
  its replays.

---

## 2. The work

Sizes are S (a day or less), M (a few days) and L (a week or more), as guides. "New" means no issue exists yet; one
is filed when the plan is adopted. Every item below assumes §1a's fixes have shipped.

### 2.1 Track A: an increment accepted on a real product (the floor)

2.5's unfinished half (#2827). Nothing else in 2.6 is measurable until this holds.

| item | what | size |
|---|---|---|
| **#2818** | a product's in-cycle suite run and its retest run **on the product's own runner in the sandbox**, with its configured setup, as acceptance and the baseline already do (shape 1 in the issue; D4). This is also what makes a non-Python product possible without stack code in shared code: the product declares its commands, the sandbox runs them | M–L |
| **#2799** | a vitest page criterion for a page the change adds can fail as an assertion on a tree without it (a loader the bundle carries, as #2749 did for the Next.js sample stack) | M |
| **#2827 item 2** | H.13's two unbuilt items: a product's repaired suite read by the product's runners, not the scaffold's `__tests__/` rule; a plan-less product cycle's test author shown the product | M |
| **a size preflight** (new) | before a Campaign starts on a product, every task type the profile dispatches is rendered against the product's real tree at the pinned commit, and a binding that can't fit is a blocking gap, named before the first cycle. #2805 and #2810 were found one at a time, live, an hour in. The proving product will be larger than `z_continuum` | S–M |

**Evidence before merge:** each fix replays the stored envelope that found it (`cyc_ac0cb5a7b6b2` for #2818,
`cyc_7cbdae00b2ed` for #2799), and a wiring test enters at the caller the live cycle uses.

### 2.2 Track B: a Campaign that carries itself past a failure

| item | what | size |
|---|---|---|
| **a criterion checked against the head as soon as its test exists** (new; D9) | at the ruling only a criterion's statement and observable exist; its executable test is written later in the increment's cycle (SIP-0109's workload order, the second outside review). So the check runs at the earliest point a test exists: when the cycle's QA task has written a criterion's test, it runs on the campaign branch's head in the sandbox, before development's work is accepted. One that already passes ends the increment as `criteria_not_checkable`, returned to a new proposal with its reason. That replaces the owner's manual rule from 2.5 and spends one framing and one QA task instead of a whole cycle and its repair. A check at the ruling itself would need a verifier-authoring step before the gate: not proposed | M |
| **#2613** | a regression the product's own checks find at the end of the plan gets one repair round inside the cycle's correction budget, instead of failing the run. Its own text says to build it when a live run needs it; a multi-hour run on a real product will | M |
| **#2612** | a change can delete a file. A real product's refactors remove what they replace | M |
| **#2783** | the anchors of pages earlier increments added reach the next proposal, so a later increment can't reuse one. It only shows after two UI increments, which is the multi-hour case | S–M |
| **#2781** (deferrable) | a seed for an added page whose path has a parameter, so it is read instead of refused | M |

### 2.3 Track C: unattended for hours

| item | what | size |
|---|---|---|
| **#2796** | the plan-review tier decides a product's plan gate from the approved change request and the plan's own open-question fields, instead of escalating every one. The rule is written into SIP-0109 §24bj, not left as a fallthrough | M |
| **an escalation policy for unattended runs** (new; D6) | a Campaign declares which escalation classes the crew's `campaign-supervisor` principal may resume on its own, within the Campaign's limits. Today only `campaigns:control` (admin) resumes, and the crew's broker deliberately holds no admin role, so every overnight escalation waits for the owner. Everything outside D6's classes still does | M |
| **the overnight identity: confirm, don't build** (D7) | the crew's broker already holds scoped service principals (`campaign-operations`, `campaign-review`, `campaign-evidence`, private-key JWT clients in the `squadops-local` realm, none with `admin`; Nostromo's campaign execution harness document, in `backspring-labs/nostromo`). That answers most of #2760: no CLI session, no 8-hour limit. What remains is D6's resume grant to that principal. **Security, so the owner's** | S |
| **#2287** | the box lease outside Campaigns, so nothing else takes the GPU during an overnight window, built as SIP-0109 §9.3 is written. The crew's `crewctl mode counted` is its own local-role guard, not this lease | M |

**Notices are the crew's.** Its watcher already posts each Campaign's transitions and closing record to Buzz, and
the owner talks to the crew there, so SquadOps builds no notice. The hard-stop notice this draft listed earlier is
dropped from SquadOps's work.

### 2.4 Track D, the headline: Project Goals and Backlog (PR #2833)

A multi-hour Campaign is several increments, each sized for one cycle, toward a goal the owner can see and steer
without a terminal. 2.5's proposals came from a flat two-feature requirements file, nothing recorded which part was
done, and the squad repeated itself. The SIP's design is under review in its own PR. This track places its slices.

**The MECE split the SIP sets** (its §3): intent (the goal, expected results, the backlog's order) in the goal set;
progress derived from the control log; proof in the evaluation records; **the crew's assessment** of each expected
result, and whose work a shortfall is (the squad's, or a framework defect or gap), on the goal set; framework work as
squad-ops issues; the owner's conversation with the crew in Buzz; decisions written through the API; code in the
product's repository.

**Who drives:** the Nostromo crew runs the Campaign and assesses its outcomes, and the owner directs it in Buzz (the
owner, 2026-10-30: "interacting with the Nostromo crew driving the campaign execution and outcome assessment").
SquadOps holds the records the crew and the owner read and write. No SquadOps agent is in Buzz.

| item | what | size |
|---|---|---|
| **slice 1: the goal set** | the versioned record beside the Project Record (goal, expected results, constraints, out of scope, backlog, candidates), its API under `/api/v1/projects/{id}/goal-set` and `squadops goals …` | M |
| **slice 2: a Campaign on a goal set** | `objective.goals`; the proposer shown the backlog with each item's derived status; one pending item per proposal, a rail returning one that names none; `stop_when: backlog_done`. A SIP-0109 amendment in the same PR | M–L |
| **slice 3: candidates** | the squad, the crew or the system adds what it finds; the owner, or the crew if delegated (Q41), promotes or drops it | S–M |
| **slice 4: the console's goals panel** | a Continuum plugin (SIP-0069): goal, expected results, backlog with status and increments, candidates waiting, history. Editing writes a revision | M |
| **slice 5: the crew's surface** | the goal set and derived backlog readable by the supervisor and triage principals; each gate's evidence names its backlog item and carries the expected results, so the crew's reviewer judges an increment against the goal; candidates and **assessments** written by the crew (the SIP's §5.7: `met`/`not_met`/`unclear`, and a shortfall's cause: `app_work`, `framework_defect`, `framework_gap` or `needs_owner`, with the squad-ops issue it filed) | M |

**The crew's side, in Nostromo's repository, not this plan's to build.** For rung 3 the crew's harness has to use
slice 5:
- its broker's fixed command list gains the goal-set reads, candidates and assessments;
- its gate-evidence contract carries the backlog item and expected results;
- its ruling role's closing interpretation is written as assessments;
- its Campaign definitions name `objective.goals`.

Those are the crew's changes. The plan names them as a dependency with the owner (D14), so neither repository
assumes the other did them. **Unverified:** whether the crew's harness, which parks a Campaign on any missing
evidence, worker error or blocking review, with no automatic retry, can run unattended for hours. That is the crew's
policy, read on the first attended proving run.

**The proving Project's goals are written into a goal set** (slice 1) before its Campaign starts, not into a file in
this repository. Until slice 1 lands, phase 1 drafts them as text to load.

### 2.5 Track E: the machinery over hours, without a model

| item | what | size |
|---|---|---|
| **#2495** | the scripted squad: every task answered from a recorded script behind the LLM port, so handlers, gates and the correction loop run as they do with a model. The owner asked for it on 2026-10-19 ("we don't need to test model quality just execution machinery") | L |
| **a scripted soak** | a scripted Campaign of eight or more increments on the proving product's real repository, with a deploy restart, a token expiry, an upstream push and a pause in the middle. It reads whether the control loop lasts hours, apart from whether the model's work is accepted | M |

### 2.6 Track F: the proving Project

| item | what | size |
|---|---|---|
| **the financial application** (D2) | the counted proving Project. If it doesn't exist yet, it is created greenfield from the `fullstack_fastapi_react` blueprint (SIP-0105), the stack the framework knows best and the path `z_shelfnote` proved (IR-7). Its requirements file carries the backlog (§2.4) and is the owner's. **Synthetic data only** (D10): no real accounts, statements or credentials in the repository, a prompt, the suite or a record | S to set up |
| **its held-out suite** | drafted, reviewed and approved as 2.5's demonstration suites were (2.5 plan D11), so the yardstick reads whether the product improved, not only whether the squad's tests passed | M |
| **a Roblox spike** (D3, no box time) | can a Rojo project's Luau tests run headless on Linux inside the sandbox from declared commands? **Unverified:** which runner (a standalone Luau runtime, or a test framework that needs Roblox's own APIs) and what it can't exercise. If yes, a Roblox game is an ordinary repository-backed Project once Track A lands, and its game-specific skills come from PR #2405. If it needs Roblox Studio, it is #2405's remote worker, not 2.6 | S |

### 2.7 Track G: the console, so the owner drives a Campaign off the terminal (#2834)

The headline's goals panel (slice 4) is one screen. Today **a Campaign has no console surface at all:** `squadops
campaigns` has 17 commands and no plugin, and `squadops.projects` shows a list and squad profiles, none of SIP-0112's
lifecycle (#2834: SIP-0069's normative CLI parity, broken since 2.0). The owner directs the Campaign through the crew in Buzz.
This track is where the owner **reads** it without a terminal: the goals, the backlog, the Campaign's state and the
crew's assessments.

**Where the work is:** the plugins live in this repository (`console/continuum-plugins/`, SIP-0069 D2), so the track is
SquadOps work. Continuum itself is pinned at `v1.0.2` (`console/continuum.lock`), and SIP-0069's principle 5 is "zero
shell modification". **No Continuum change is planned,** pending the fit check below.

| item | what | size |
|---|---|---|
| **a Continuum fit check** (first, no box time) | can the pinned shell do what the views below need: a list that refreshes while a Campaign runs, an ordered list edited in place, a view per Project and per Campaign, and a write that goes through the command bus with its danger level? **Unverified.** If it can't, the gap is named, and the choice (a plugin-local workaround, or a Continuum release) comes back to the owner before any view is built | S |
| **a Campaigns plugin** (new, `squadops.campaigns`), **read-only in 2.6** | **what's happening:** state, the current increment, the ledger, the digest, open escalations and proposals waiting, and the crew's latest assessment of each expected result. **The controls stay with the crew** (it launches, rules and pauses through its broker) and the CLI. Console controls are #2834's parity debt, for a later line | M |
| **the goals panel** | the SIP's slice 4 (§2.4), as a panel of the Projects plugin, linked to each Campaign that reads it | M (counted in §2.4) |
| **Project setup views** (deferrable) | validate, configure, capture a baseline, sync, and see the gaps. These run once per Project, or when upstream moves, so the CLI is tolerable for 2.6 and they defer first | M–L |
| **not in the console** | `scenarios draft` and `review` (held-out content stays with the supervisor and the owner, SIP-0113's independence), and `acquire`/`release` (operator tools). #2834 asks for a SIP-0069 amendment naming these exceptions, not a silent gap | — |

**What "off the terminal" means for the release claim:** on the proving Campaign, the owner writes the goals in the
console, directs the crew in Buzz, and reads the Campaign's state and the crew's assessments in the console (§4,
rung 3). Setting up the Project once may still use the CLI if Project setup defers.

### 2.8 Riding along (hardening, any lane order)

#2826 (the list-shape convention placed by the 2.5 cut), #2736, #2737. Each is small and touches no Campaign path the
proving run reads, or lands before phase 3. (#2830, #2765 and #2402 are 2.5.1's, §1a.)

### 2.9 Not in 2.6

- **The TensorFold 1.x upgrade** (#2230): deferred to 3.x by the owner, 2026-10-30.
- **The judgement steps** (#557, #949, #950) and **Test-First's greenfield gate** (#1978): none removes a stop §1 found.
- **SIP-0112's lifecycle completeness** (#2709): update history, archive and restore. The concurrency part a long
  Campaign meets (an outside push mid-run) is already IR-3's and shipped.
- **Held-out suite revision 7** (#2723) and any other re-cut of the sample applications' yardstick.
- **#2421's secrets half:** a live financial data source waits until a synthetic-data Campaign has held (D10).
- **Game-specific capability** (#2405): its placement is its own decision, after the spike.
- **#1965, #1039:** unplaced, as before.

---

**What is cut first** if the line runs long (the second outside review): Project setup views (Track G), #2781's
parameterized pages, the repository export (the SIP's slice 6), and §2.8's unrelated hardening. **Kept while the
overnight claim stands:** recovery (Track B), the bounded resume (D6) and the box lease (#2287). §0 runs first, and
what it finds may reorder everything after it.

## 3. Sequencing

The Spark is one GPU and one deploy.

0. **2.5.1** (§0, step 1): its seven fixes, each replayed against the envelope or record that found it, the regression suite,
   and the patch cut. About 1 box-hour for the replays and the deploy, as a guide. 2.6's builds start beside it.
1. **No box time.** The owner rules §7. The proving Project's requirements and backlog are written, its Development
   Configuration recorded, its suite drafted. The Roblox spike runs on the CPU, and Track G's Continuum fit check runs
   beside it.
2. **Track A, then Track B,** on top of 2.5.1, each fix replayed against 2.5's stored envelopes. Any §1a item not in a
   released 2.5.1 by now joins Track A (§1a's fallback rule). Track C's design pieces (D6, D7, #2796)
   are reviewed in parallel; D7 waits for the owner. The headline's slices and Track G's views are built beside them: no box time,
   and each view is read against a running Campaign before the proving run.
3. **The scripted soak** (Track E). Machinery only, so a failure here is the framework's, never the model's.
4. **A short model Campaign on `z_continuum` and `z_shelfnote`** as the product path's shakeout. Not the goal, but
   cheap and already configured, and it reads 2.5's narrowed half (IR-5, IR-6's increment half, IR-9's increment
   reading) before the proving product's time is spent. It is also **the live reading of 2.5.1's product-path fixes**
   (#2824, #2817, #2814), which the patch read only by replay. Its exit rule: one Campaign with an accepted increment and no
   new seam finding.
5. **The proving Campaign** on the owner's product, first attended, then unattended overnight under D6's policy.
6. **The cut.**

**What invalidates earlier evidence:** 2.5's rule carries. A merge that changes a path an earlier run executed voids
that run for the release claim.

---

## 4. The release claim (D8)

A ladder, each rung pre-registered before its run:
1. **An accepted increment** on a product, promoted onto its campaign branch, with its review request pushed
   (#2827's done-when). It reads that the squad's criteria passed on the product's runner, not that an expected
   result improved; that is the held-out suite's reading, from rung 2 on.
2. **Three accepted increments in one Campaign** on the proving product, each from a different backlog item.
3. **Four hours or more of one Campaign on the proving product,** which itself reaches its accepted-increment target
   and **a pre-registered held-out improvement threshold** on the proving product's suite (elapsed time and passing
   tests don't show that the app improved), of which at least part is unattended overnight, with
   no intervention outside D6's declared touchpoints, and every stop attributed to a named rule. Its goals are a goal
   set written in the console (slice 4), each item's status reads back from the control log, the crew runs it and
   records at least one assessment per expected result it reached, and the owner works through the crew in Buzz and
   the console (Track G), not a terminal.

**Recommended:** rungs 1 and 2 are required for the cut; rung 3 is the headline claim. If rung 3 doesn't hold, the
claim narrows only on the owner's ruling, named in the cut record, as at 2.5. **Each run records** its wall-clock
time, increments proposed, accepted, repaired and abandoned, escalations by class and who answered each, and the
model's share of the time.

The predictions are mechanisms, not rates: at this N a rate reads nothing.

---

## 5. Lanes and roles

**One lane, the Spark's,** as from 2026-10-28. The owner's second review on a shared contract goes through the owner's
outside reviewer (a self-contained packet on the PR). **2.5's terms carry** (D12): the supervisor builds, merges on
green with main's run read, and runs the deploys and uncounted runs. The owner keeps compose, security (D7 among it),
lesson approvals, the Release and the tag.

---

## 6. Box-time budget

About **25–35 box-hours**, as a ceiling to report against, 2.5.1's replays (about 1) not counted: the size preflight and the replays about 2; the scripted
soak 4–8 (model-free, so the GPU is idle); the shakeout on the two existing products about 3–4; the proving Campaign
twice, 4–8 each; the cut about 6. **Checkpoints:** after Track A (rung 1 on a product), after the soak, and after
the first attended proving run. Track D is build time, not box time: the proving Campaign reads it.

---

## 7. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| D1 | **the headline and its SIP** | **Project Goals and Backlog (PR #2833), accepted and its slices 1–5 built.** Slice 5, the crew's minimum surface (reads, the backlog item in gate evidence, assessments), is **required**: the console's assessments, rung 3 and the SIP's close depend on it. Only slice 6, the repository export, is not in 2.6. Tracks A to C are its floor, built as the completion of SIP-0109 and SIP-0112 with numbered amendments for the escalation policy (§2.3) and the criterion check (§2.2). Its design review is in its own PR, and its Q41–Q44 are yours. **The alternative:** no new SIP, the backlog as a SIP-0109 amendment over a requirements file, which keeps the goals in a file edited from a terminal, which your direction rules out |
| D2 | **the proving Project** | **the financial application,** greenfield from the `fullstack_fastapi_react` blueprint if it doesn't exist. It sits on the stacks the framework reads best, so a stop there is the Campaign's, not the stack's. **The alternatives:** a Roblox game first (blocked on D3), or another existing repository of yours |
| D3 | **Roblox in 2.6** | **the spike only,** in phase 1. If its tests run headless on Linux, a Roblox Project is a second, uncounted Campaign late in the line. #2405's placement is decided after the spike |
| D4 | **#2818's shape** | **shape 1, the sandbox's product runner,** as §24bv point 3 judges a product: on its own runner. It costs a sandbox round trip per suite run, and it's the only shape that covers a non-Python product |
| D5 | **who authors the backlog** | **you order it; the squad proposes from it** and records what it finds as candidates, which you, or the crew if Q41 delegates it, promote or drop. The strategy role ordering its own features waits for a later line, once a Campaign has lasted hours on yours |
| D6 | **what the crew's supervisor principal may resume unattended, enforced and audited** | **these classes:** a plan gate answered from the requirements; a repair or retry after a named in-cycle failure, within the limits; `launch_blocked` after the box is quiet. **Never:** an upstream conflict, a limit's pause, a security finding, or the owner's pause. **Enforced** at the resume route: the escalation's class is checked against the Campaign's declared `unattended_resume` list, fixed at creation and part of its definition hash, and against the caller's principal; anything else is refused with its reason. **Audited:** every resume and every refusal is a control-log row naming the principal, the class, the escalation and the definition hash, and the digest lists them. **Revoked** by the owner's pause, which the principal can't resume. It is a grant to the crew's broker principal, which holds no admin role today |
| D7 | **the overnight identity** | **the crew's existing broker principals, unchanged,** plus D6's resume grant. No new identity is built. Security, so yours. **The alternative:** a separate SquadOps service account for unattended supervision, which duplicates what the crew's broker already holds |
| D8 | **the release claim** | §4: rungs 1 and 2 required; rung 3 the headline, and its Campaign must itself reach the accepted-increment target and a held-out improvement threshold pre-registered before it starts (the second outside review) |
| D9 | **a criterion already met** | **checked as soon as the criterion's test exists,** in the increment's cycle, against the head (§2.2), since no test exists at the ruling. **The alternative:** keep row 16's abandonment after a spent cycle, or add a verifier-authoring step before the gate (larger, not proposed) |
| D10 | **the financial application's data** | **synthetic only in 2.6:** fixtures the squad and the owner write, no live data source, no real credentials. #2421's secrets half stays unbuilt |
| D11 | **2.5.1's contents** (revised for §0's spike) | **§0's seven:** #2818 (moved from 2.6), #2824, #2817, #2814, #2804, #2809 and #2813, the fixes on a Campaign's path. §1a's other four (#2798, #2765, #2830, #2402) go to a later patch. #2799, #2796, #2613 and #2612 stay in 2.6. **The alternative:** §1a's original ten without #2818, which leaves 2.5's main stop unfixed until 2.6 |
| D12 | **who runs the line** | 2.5's terms (§5) |
| D13 | **the console's scope** (Track G, #2834) | **the goals panel and a read-only Campaigns plugin required** (state, ledger, escalations, the crew's assessments, which slice 5 makes required too); controls stay with the crew and the CLI; Project setup views deferrable; held-out drafting and the lease tools kept out of the console by a SIP-0069 amendment. No Continuum change unless the fit check finds one, and then it comes back to you. **The alternative:** console controls too (an L), duplicating the crew's broker path |
| D14 | **the crew's side of slice 5** (Nostromo's repository): **a release dependency with a readiness check** | **you place it with the crew,** beside 2.6's slice 5: the broker's commands, the gate-evidence contract, assessments from the closing interpretation, and definitions naming `objective.goals`. **The readiness check,** before the proving run is pre-registered: on an uncounted Campaign, the crew's broker reads the goal set, a gate's packet carries the backlog item and its expected results, and the crew writes one assessment that reads back. It is recorded in the cut's pre-registration. **If it doesn't pass,** rung 3 can't be claimed, and the claim narrows only on your ruling |
| D15 | **SIP Q41, before slice 1 is built** (the outside review) | **rule it first:** the crew may promote a candidate and split an item within a Campaign you started, each recorded with its reason; never reorder. Slices 1 and 3 build to that rule |

---

## 8. For the outside reviewer

The questions this draft is least sure of:
1. **Is the stop order right?** §1 orders the work by what stopped 2.5's six Campaigns. Is there a class that will stop
   a real product's Campaign that 2.5's two small products couldn't show (repository size, build time, flaky tests, a
   long install)?
2. **Is D4's cost acceptable?** A sandbox round trip per in-cycle suite run lengthens every cycle. Is a cached product
   environment per Campaign needed in 2.6 to keep a multi-hour run productive?
3. **Is D6 too wide or too narrow?** Which escalation class would you refuse to let an unattended supervisor resume?
4. **Is the headline the right size for 2.6?** Project Goals and Backlog (D1, PR #2833) adds a record, an API, a
   Campaign binding and a console panel beside Tracks A to C. Is that too much for one line, and if something has to
   give, is it the console (slice 4 and Track G's Campaigns plugin, an M and an L) or the
   floor's unattended track (C)? Is §3 of the SIP the right MECE split
   between the database, Buzz and the repository?
5. **Is the financial application (D2) the right proving target,** given its data rule, or does a target with a public
   data source read the Campaign better?
6. **Is §1a's split right?** Ten defects go to 2.5.1, read by replay only, and their live reading waits for 2.6's
   shakeout. Should any of them (#2817 and #2814 most likely) be read on a live product before the patch is cut?
7. **Is the crew boundary right?** The crew drives and assesses as an API client, and SquadOps records its
   assessments (`met`/`not_met`/`unclear` and a shortfall's cause) without letting them decide anything. Should an
   assessment of `framework_defect` pause the Campaign by itself, or stay the crew's to act on?
8. **What is missing** that a multi-hour run needs: cost or token limits per hour, checkpointing the campaign branch
   for the owner to review mid-run, or a way for the owner to steer the backlog while it runs?
