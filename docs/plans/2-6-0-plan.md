# 2.6.0 plan — a multi-hour Campaign on the owner's own product

**Status: DRAFT (2026-10-30), for outside review.** Nothing here is ruled. §7's decisions are the owner's, and each
has a recommendation. §8 lists what the outside reviewer is asked to challenge.

**Revised 2026-10-30, the same day:** the owner asked to incorporate the 2.5.1 fix line's assumptions. §1a names the
ten defects 2.6 assumes 2.5.1 fixes, with a fallback rule if one slips; they leave §2's tracks, and D11 rules the split.

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
| **#2421, the declared-commands half** | the sandbox runs a product's declared install, build, test and start commands at the pinned revision, in a disposable copy. #2818's shape 1 needs it, so they are built together. The secrets half stays unbuilt (D10) | M |
| **#2799** | a vitest page criterion for a page the change adds can fail as an assertion on a tree without it (a loader the bundle carries, as #2749 did for the Next.js sample stack) | M |
| **#2827 item 2** | H.13's two unbuilt items: a product's repaired suite read by the product's runners, not the scaffold's `__tests__/` rule; a plan-less product cycle's test author shown the product | M |
| **a size preflight** (new) | before a Campaign starts on a product, every task type the profile dispatches is rendered against the product's real tree at the pinned commit, and a binding that can't fit is a blocking gap, named before the first cycle. #2805 and #2810 were found one at a time, live, an hour in. The proving product will be larger than `z_continuum` | S–M |

**Evidence before merge:** each fix replays the stored envelope that found it (`cyc_ac0cb5a7b6b2` for #2818,
`cyc_7cbdae00b2ed` for #2799), and a wiring test enters at the caller the live cycle uses.

### 2.2 Track B: a Campaign that carries itself past a failure

| item | what | size |
|---|---|---|
| **a criterion checked against the head before launch** (new; D9) | at the ruling, each proposed criterion's test runs on the campaign branch's head in the sandbox. One that already passes is returned for revision automatically, with its reason, before a cycle is spent. This replaces the owner's manual rule from 2.5 and saves the abandonment that counts toward `max_unaccepted_increments` | M |
| **#2613** | a regression the product's own checks find at the end of the plan gets one repair round inside the cycle's correction budget, instead of failing the run. Its own text says to build it when a live run needs it; a multi-hour run on a real product will | M |
| **#2612** | a change can delete a file. A real product's refactors remove what they replace | M |
| **#2783** | the anchors of pages earlier increments added reach the next proposal, so a later increment can't reuse one. It only shows after two UI increments, which is the multi-hour case | S–M |
| **#2781** (deferrable) | a seed for an added page whose path has a parameter, so it is read instead of refused | M |

### 2.3 Track C: unattended for hours

| item | what | size |
|---|---|---|
| **#2796** | the plan-review tier decides a product's plan gate from the approved change request and the plan's own open-question fields, instead of escalating every one. The rule is written into SIP-0109 §24bj, not left as a fallthrough | M |
| **an escalation policy for unattended runs** (new; D6) | a Campaign declares which escalation classes the supervisor identity may resume on its own, within the Campaign's limits. Everything else waits for the owner, as today | M |
| **a supervisor identity that lasts the night** (new; D7) | an identity for an unattended supervisor that isn't bound by the 8-hour session: a service account with client credentials, scoped to `campaign-supervisor` plus D6's resumes. With #2760's answers from the Nostromo crew. **Security, so the owner's** | S–M |
| **#2287** | the box lease outside Campaigns, so nothing else takes the GPU during an overnight window, built as SIP-0109 §9.3 is written | M |
| **a hard-stop notice** (new) | when a Campaign stops, pauses at a limit or escalates to the owner, one push notice names why. Nothing on progress | S |

### 2.4 Track D, the headline: Project Goals and Backlog (PR #2833)

A multi-hour Campaign is several increments, each sized for one cycle, toward a goal the owner can see and steer
without a terminal. 2.5's proposals came from a flat two-feature requirements file, nothing recorded which part was
done, and the squad repeated itself. The SIP's design is under review in its own PR. This track places its slices.

**The MECE split the SIP sets** (its §3): intent (the goal, expected results, the backlog's order) in the goal set;
progress derived from the control log; proof in the evaluation records; deliberation in Buzz; decisions as recorded
actions; code in the product's repository. **Discussed in Buzz, decided in SquadOps.**

| item | what | size |
|---|---|---|
| **slice 1: the goal set** | the versioned record beside the Project Record (goal, expected results, constraints, out of scope, backlog, candidates), its API under `/api/v1/projects/{id}/goal-set` and `squadops goals …` | M |
| **slice 2: a Campaign on a goal set** | `objective.goals`; the proposer shown the backlog with each item's derived status; one pending item per proposal, a rail returning one that names none; `stop_when: backlog_done`. A SIP-0109 amendment in the same PR | M–L |
| **slice 3: candidates** | the squad, the crew or the system adds what it finds; the owner, or the crew if delegated (Q41), promotes or drops it | S–M |
| **slice 4: the console's goals panel** | a Continuum plugin (SIP-0069): goal, expected results, backlog with status and increments, candidates waiting, history. Editing writes a revision | M |
| **slice 5: Buzz** (deferrable) | notices first (a Campaign stopped, a candidate waiting, an item accepted, each with its console link); decisions as API actions carrying the thread's link, once D7's identity exists (Q43). The bridge's mechanics aren't designed yet | M |

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

### 2.7 Riding along (hardening, any lane order)

#2826 (the list-shape convention placed by the 2.5 cut), #2736, #2737. Each is small and touches no Campaign path the
proving run reads, or lands before phase 3. (#2830, #2765 and #2402 are 2.5.1's, §1a.)

### 2.8 Not in 2.6

- **The TensorFold 1.x upgrade** (#2230): deferred to 3.x by the owner, 2026-10-30.
- **The judgement steps** (#557, #949, #950) and **Test-First's greenfield gate** (#1978): none removes a stop §1 found.
- **SIP-0112's lifecycle completeness** (#2709): update history, archive and restore. The concurrency part a long
  Campaign meets (an outside push mid-run) is already IR-3's and shipped.
- **Held-out suite revision 7** (#2723) and any other re-cut of the sample applications' yardstick.
- **#2421's secrets half:** a live financial data source waits until a synthetic-data Campaign has held (D10).
- **Game-specific capability** (#2405): its placement is its own decision, after the spike.
- **#1965, #1039:** unplaced, as before.

---

## 3. Sequencing

The Spark is one GPU and one deploy.

0. **2.5.1** (§1a): its ten fixes, each replayed against the envelope or record that found it, the regression suite,
   and the patch cut. About 1 box-hour for the replays and the deploy, as a guide. 2.6's builds start beside it.
1. **No box time.** The owner rules §7. The proving Project's requirements and backlog are written, its Development
   Configuration recorded, its suite drafted. The Roblox spike runs on the CPU.
2. **Track A, then Track B,** on top of 2.5.1, each fix replayed against 2.5's stored envelopes. Any §1a item not in a
   released 2.5.1 by now joins Track A (§1a's fallback rule). Track C's design pieces (D6, D7, #2796)
   are reviewed in parallel; D7 waits for the owner.
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
1. **One increment accepted** on a product and promoted onto its campaign branch, with its review request pushed
   (#2827's done-when).
2. **Three accepted increments in one Campaign** on the proving product, each from a different backlog item.
3. **Four hours or more of one Campaign on the proving product,** of which at least part is unattended overnight, with
   no intervention outside D6's declared touchpoints, and every stop attributed to a named rule. Its goals are a goal
   set written in the console (slice 4), and each item's status reads back from the control log.

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
| D1 | **the headline and its SIP** | **Project Goals and Backlog (PR #2833), accepted and its slices 1–4 built, with slice 5 deferrable;** Tracks A to C as its floor, built as the completion of SIP-0109 and SIP-0112 with numbered amendments for the escalation policy (§2.3) and the criterion check (§2.2). Its design review is in its own PR, and its Q41–Q44 are yours. **The alternative:** no new SIP, the backlog as a SIP-0109 amendment over a requirements file in the product's repository. It is smaller, but keeps the goals in a file edited from a terminal, which your direction rules out |
| D2 | **the proving Project** | **the financial application,** greenfield from the `fullstack_fastapi_react` blueprint if it doesn't exist. It sits on the stacks the framework reads best, so a stop there is the Campaign's, not the stack's. **The alternatives:** a Roblox game first (blocked on D3), or another existing repository of yours |
| D3 | **Roblox in 2.6** | **the spike only,** in phase 1. If its tests run headless on Linux, a Roblox Project is a second, uncounted Campaign late in the line. #2405's placement is decided after the spike |
| D4 | **#2818's shape** | **shape 1, the sandbox's product runner,** as §24bv point 3 judges a product: on its own runner. It costs a sandbox round trip per suite run, and it's the only shape that covers a non-Python product |
| D5 | **who authors the backlog** | **you order it; the squad proposes from it** and records what it finds as candidates, which you, or the crew if Q41 delegates it, promote or drop. The strategy role ordering its own features waits for a later line, once a Campaign has lasted hours on yours |
| D6 | **what an unattended supervisor may resume** | **these classes:** a plan gate answered from the requirements; a repair or retry after a named in-cycle failure, within the limits; `launch_blocked` after the box is quiet. **Never on its own:** an upstream conflict, a limit's pause, a security finding, or the owner's pause |
| D7 | **the overnight identity** | **a service account with client credentials,** scoped to `campaign-supervisor` and D6's resumes, its secret held as the deploy's other secrets are. Security, so yours. **The alternative:** keep the password re-login before each ruling, which works but ties an overnight run to one supervisor session |
| D8 | **the release claim** | §4: rungs 1 and 2 required, rung 3 the headline |
| D9 | **a criterion already met** | **checked at the ruling, returned automatically,** as §2.2 says. **The alternative:** keep row 16's abandonment after a spent cycle |
| D10 | **the financial application's data** | **synthetic only in 2.6:** fixtures the squad and the owner write, no live data source, no real credentials. #2421's secrets half stays unbuilt |
| D11 | **2.5.1's contents, and 2.6 planned on top of them** | **§1a's ten:** #2824, #2817, #2814, #2804, #2809, #2813, #2798, #2765, #2830 and #2402, each a defect with no design, read by replay. 2.6's tracks assume them, with §1a's fallback rule if one slips. #2818, #2799, #2796, #2613 and #2612 stay in 2.6, since each needs a design. **The alternative:** no 2.5.1, and the ten join 2.6's Track A, which lengthens phase 2 by a few days and puts the patch's fixes behind 2.6's designs |
| D12 | **who runs the line** | 2.5's terms (§5) |

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
   give, is it the console panel (slice 4) or the floor's unattended track (C)? Is §3 of the SIP the right MECE split
   between the database, Buzz and the repository?
5. **Is the financial application (D2) the right proving target,** given its data rule, or does a target with a public
   data source read the Campaign better?
6. **Is §1a's split right?** Ten defects go to 2.5.1, read by replay only, and their live reading waits for 2.6's
   shakeout. Should any of them (#2817 and #2814 most likely) be read on a live product before the patch is cut?
7. **What is missing** that a multi-hour run needs: cost or token limits per hour, checkpointing the campaign branch
   for the owner to review mid-run, or a way for the owner to steer the backlog while it runs?
