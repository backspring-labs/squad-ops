# 2.8.0 plan: a squad develops and tests a Roblox game

**Status: ADOPTED 2026-11-11 (#3051), revision 3 as ruled, with the owner's rulings and the reconciliation with the MacBook lane (§11).** The owner asked for a 2.8 plan whose headline
is the game-development work, with a review of what the MacBook lane has merged for it and what more it needs to hold
up. An outside review of revision 1 requested changes before adoption (§10). The owner then ruled all nine decisions
as recommended in revision 2's write-up, which takes the review's rulings and adds two of this plan's (§8: "good
with your recommednation. go", 2026-11-11, about 09:00 ET).

**The plan is adopted when the owner merges this PR.** Until then nothing is placed and nothing is built on it. The
issues it proposes are open so the plan can be read against them. They carry no `sip:` label and no ledger row until
the adoption PR (§9).

**Revision 3 reconciles the plan with the MacBook lane's work in flight** (§11). The owner asked for that on
2026-11-11 and is holding the MacBook session until the lanes agree. §11 has:
- one lane per issue;
- the three points where #3052 (the squad's side of remote execution, opened that morning) differs from decision 2;
- the changes to the MacBook lane's own documents;
- what each lane confirms before it resumes.

**The owner ruled §11's open points on 2026-11-11** ("approve both lanes to spark, decision 2 governs"). The MacBook lane confirmed revision 3 with no objection (this PR's comments).

## Revision log

- **Revision 1** (2026-11-11): the first draft.
  - It reviews the game work on main at `5bfa2c7e`.
  - It places every remaining ledger row of SIP-0116, SIP-0117 and SIP-0118.
  - It adds seven hardening items that no ledger row carries (#3044–#3050).
  - It proposes rulings on the six features 2.7 moved here.
- **Revision 2** (2026-11-11): the outside review's round 1, and the owner's rulings.
  - **Campaign delivery gets an owner (#3053).** Campaign acceptance runs each criterion as a test file on the
    product's runner in the sandbox (`campaigns/runner_acceptance.py`). Nothing under `campaigns/` reads a remote
    operation's evidence. So a Studio pass couldn't accept an increment, and the second increment couldn't replay
    the first one's scenario. This was the review's main blocker. Revision 1 missed it.
  - **The scenario is declarative** (#3044, after the review's answer to question 8). Strategy declares actions,
    observations and expected values, and a trusted harness validates them and executes them. Revision 1 called the
    scenario an authored Luau program, which the Studio boundary forbids. The SIPs are amended at adoption (§9).
  - **The baseline must execute and fail** (#3044). The named assertion must fail as executed on the accepted
    baseline before development starts. Anything unread blocks the increment, where the existing pass-on-head check
    proceeds (`execution/criterion_head_check.py:16-20`).
  - **The agent's request is scoped to its current send, idempotent, and superseded by a newer send** (decision 2,
    #3023). The registry mints a new operation id on every enqueue (`remote_execution/registry.py:172-189`), and the
    handler sends the task id as the request's identity (`run_remote_operation.py:136`).
  - **A relaunch budget persisted per logical increment** (decision 3, #3045). `launch_blocked` counts attempts per
    episode, and an unblock ends the episode (`campaigns/launch_blocking.py`).
  - **The machinery check is a two-increment Campaign** (#3050). It starts from a fixture change request and
    reaches the worker through normal plan expansion. It adds two faults: a dropped enqueue response with a
    requester restart, and a superseded send.
  - **Each gate outcome has its own cut evidence** (§5, §6). As drafted, §6 required the counted Studio run even
    after a narrow or a stop.
  - **The demonstration's pre-registration** states the selection, the counting window, the permitted operator
    actions, and that every attempt is reported (#3043).
  - **Settled now:** captures stay outside 2.8's acceptance evidence (#3049). #3009's administrator setting is
    verified in GitHub's 2026-11-16 test window.
- **Revision 3** (2026-11-11): the reconciliation with the MacBook lane (§11).
  - **#3052 is read against decision 2.** It was built on the owner's earlier ruling ("approve part 3 as
    recommended") and opened at 08:41 ET, before decision 2 was ruled. It matches on the transport and the scope.
    It differs on three points (§11.2), and the adoption PR's SIP-0117 amendment becomes R5.7, since #3052 takes R5.6.
  - **#3045 narrows to the Campaign's relaunch budget, Spark lane** (ruled 2026-11-11). #3052's wait and cancel already
    give the in-cycle limits and outcomes it asked for.
  - **#3047, the operator's read surface, goes to the Spark lane** (ruled 2026-11-11).
  - **Every issue has one lane** (§11.1).
- **Revision 3, as ruled** (2026-11-11): the owner ruled both lanes to the Spark and that decision 2 governs ("approve both lanes to spark, decision 2 governs").
  - The MacBook lane confirmed revision 3 with no objection (issuecomment-6798562647).
  - The owner released the MacBook lane's hold, and that lane is building §11.2's three changes on #3052.
- **The Studio first slice, confirmed** (2026-11-11: "confirm the studio first slice, merge 3051"): read-only, `z_tower-ascension` only, nothing published. The MacBook lane reported it as approved that morning, and the owner confirmed it here. It is an early read on §5's gate (below). The plan is adopted by this PR's merge.

## What 2.8 is

An even minor, so a feature release, led by one headline (CLAUDE.md, #281). The headline is the Roblox work. The
Spark lane carries the pieces the headline needs on its own files:
- Campaign delivery (#3053);
- the end-to-end machinery Campaign (#3050);
- the Luau runner (#2906);
- the Campaign's relaunch budget (#3045) and the operator's read surface (#3047), ruled to the Spark lane on 2026-11-11.

It also carries the ride-alongs in §7.

**The claim, as the adopted game-dev-roblox plan states it (§1 there, decision D1, accepted 2026-11-08), with the
evidence rules of revision 2:**

> **A squad running on the Spark takes two consecutive small increments of an existing Roblox game from design to
> accepted source, each proved in a real play session in Roblox Studio, on a private copy of Tower Ascension.** For
> each increment:
> 1. strategy writes a change request with a player-facing criterion and its declarative play scenario, frozen
>    before development;
> 2. the scenario's named assertion executes and fails on the accepted baseline;
> 3. dev writes the Luau change;
> 4. qa's operation syncs the candidate into Studio, plays the frozen scenario and reads its assertion records;
> 5. the same assertion executes and passes on the candidate, and the Campaign accepts the source onto the campaign
>    branch.
>
> The second increment is accepted only with the first increment's frozen scenario re-run and passing on the same
> candidate.

**How it is counted** (the demonstration's pre-registration, #3043):
- the selection of the increments, the counting window and the permitted operator actions are stated before any run;
- every attempt, retry, relaunch and intervention is reported;
- a failed increment is never replaced by an easier one.

**Beside it, labelled apart:** a pre-registered repair diagnostic. A seeded behavioural defect fails the unchanged
verifier as an executed failure, the repair is routed, and the same verifier, by digest, passes. It proves the
correction route. It isn't evidence about the models.

**What the evidence won't show:**
- how the game feels or looks;
- more than one player;
- parts, models or UI built in Studio, since those don't sync to files;
- any effect the harness's scenario vocabulary can't observe.

## 1. What is on main (the review)

The MacBook lane merged five feature PRs and one fix for this work on the evening of 2026-11-10 (ET). The Spark was
rebuilt on them with migrations 2200 and 2300 applied (`dep_2b10f917cd73`, recorded 2026-11-10; not re-read for this
draft).

| what | PR | ledger row |
|---|---|---|
| each agent declares its skillsets; every cycle gets a skillset record, inert | #3013 | SIP-0116 phase 1 |
| coverage: a cycle whose routed agent lacks a required skillset is refused at creation, and a plan naming a contract its requirements don't is refused at the plan gate | #3015 | SIP-0116 phase 2 |
| `qa.run_remote_operation`, the four engine-neutral game contracts, and the correction route (a failed assertion routes the dev repair, and the operation re-runs on the repaired tree), proved with a fixture provider | #3019 | SIP-0117 phase 2a, parts 1 and 2; SIP-0118 phase 2a |
| the worker registry, the claim, lease and fence rules, `/api/v1/workers`, and the worker's own identity | #3024 | SIP-0117 phase 2b, part 1 |
| the worker process, its claim loop, and a fixture tool | #3027 | SIP-0117 phase 2b, part 2 |
| a task instruction for a remote operation stays with the operation | #3031 | none: a defect, #3030 |

**In flight, open:** SIP-0116 phase 3, parts 1 and 2 (#3032, #3033: skills kept with the cycle and handed to tasks at
dispatch). This plan places phase 3 in 2.8 (§2). Both are inert for every profile that requires nothing, and they
continue on their own review (decision 8).

**What the review found.**
- **The code fails closed throughout:**
  - every assertion a scenario declares produces exactly one check row, and one that didn't execute is never a pass
    (`run_remote_operation.py:311-352`);
  - a stale or late result is refused with one of seven named reasons and kept (`leasing.py`, `fence_refusal`);
  - a supplier whose digest moved since the cycle was created is refused;
  - the owner's no-silent-reads sweep (SIP-0116 §17d) took out the fallbacks that were there.
- **No defect was found** in what merged.
- **No live cycle can reach a worker yet,** and no Campaign can use a worker's verdict:
  - **nothing binds the remote-execution port.** No adapter implements `RemoteExecutionPort` outside the tests, so a
    live scenario task reads "not executed: no port bound". That's the squad's side of remote execution (#3023,
    part 3);
  - **nothing produces the frozen scenario.** The handler requires `operation_scenario` and no step in a live cycle
    writes it (SIP-0117 R5.1 says so). No ledger row owns it (#3044);
  - **Campaign acceptance can't read a scenario's evidence** (#3053, found by the outside review);
  - **no skillset, no `game_dev_roblox` profile and no Studio adapter exist,** and the planner's prompt doesn't show
    contracts yet (SIP-0116 §17c point 1).

**Where the ledgers stand.** Across the three SIPs, the rows the headline needs number 18: **7 shipped and 11 to
build.** Eight items no row carries come on top (§3).

## 2. The work

Sizes are the SIPs' own where they give one (S, M, L). A size marked * is this plan's estimate and is unmeasured.

### The engine-neutral path, live

| item | issue | lane | size |
|---|---|---|---|
| **The squad's side of remote execution:** the adapter behind the port, its required selector (`none` = no remote execution), and the request path ruled in decision 2: HTTP; enqueue, read and cancel scoped to the task's current dispatch identity; idempotent on that identity; a newer send cancels an older send's operation. **Built as #3052 (open, draft),** which differs from decision 2 on three points (§11.2) | #3023, part 3 (#3052) | MacBook | M* |
| **Tools:** the authorization and availability refusals at creation, and availability read again at dispatch | #3036 (SIP-0116 phase 4) | MacBook | M |
| **A Campaign whose worker is unavailable:** `launch_blocked` before launch, and a relaunch budget persisted per logical increment, then escalation. The in-cycle wait, cancel and outcomes are #3052's (§11.2) | #3045 | **Spark** (ruled, §11.1) | S* |
| **Campaign delivery:** a scenario criterion discriminates on revision-bound evidence; every earlier increment's scenario is replayed on the same candidate; delivery is refused when one fails | #3053 | Spark | M* |
| **The end-to-end machinery Campaign:** two increments, from a fixture change request, with the scripted squad and the fixture worker, through plan, claim, verdict, repair, re-run and delivery; six injected faults; in CI and as a cut gate | #3050 | Spark | M* |
| its prerequisites: a scripted squad's answer key survives an agent restart; a scripted repair's refused edit is named, not read as empty | #3005, #3020 | Spark | S* each |

### The frozen scenario and the headless half

| item | issue | lane | size |
|---|---|---|---|
| **The frozen scenario:** declarative, frozen with its fixtures, expected values and reader before development; the named assertion must execute and fail on the accepted baseline, and anything unread blocks the increment; observations reviewed at the plan gate for the player-facing effect | #3044 | MacBook | M* |
| **The Luau runner:** a `luau` runner kind, a test-id reader, a worked example | #2906 (SIP-0117 phase 2c) | **Spark** (decision 4) | M |

### Studio

| item | issue | lane | size |
|---|---|---|---|
| **The Studio adapter:** the transaction under one lease, the adapter's own sync, paged read-back, the full baseline before and after play, reset (including reopening Studio), deadlines, the deny list, returned edits as revisions, four operations, and the isolation test SIP-0117 R4.6 commits to | #3039 (SIP-0117 phase 2d) | MacBook | L |
| **The assertion harness and reader:** the harness is the scenario executor over a validated declaration; one structured record per assertion; every outcome produced on purpose | #3040 (SIP-0117 phase 2e) | MacBook | M |
| **Payload limits:** measure the request, claim and row sizes on the real tree (about 1.7 MB), then set explicit limits from the measurements; captures stay outside 2.8's acceptance evidence | #3049 | MacBook | S* |
| **Re-qualification after a Studio update:** a recorded run moves the pin, never a hand edit | #3048 | MacBook | S* |
| **The worker as a service on the MacBook:** launchd, stay-awake, Studio opened on the place, `doctor dev-mac` checks, an optional bootstrap step | #3046 | MacBook | M* |
| **The operator's view of the registry:** a read-only route and `squadops workers list` / `show` | #3047 | **Spark** (ruled, §11.1) | S* |

### Skills, the squad and the product

| item | issue | lane | size |
|---|---|---|---|
| **Skills:** kept with the cycle, handed at dispatch with repair lineage, budgeted (in flight as #3032, #3033) | #3028 (SIP-0116 phase 3) | MacBook | M–L |
| **The Campaign's pin** on the equipment assigned to its work | #3037 (SIP-0116 phase 5) | MacBook | M |
| **Lessons** under the development profile's recall identity | #3038 (SIP-0116 phase 6) | MacBook | M |
| **The squad:** the `game_dev_roblox` profile, three skillsets and their replay-tested skills (strategy's writes declarative scenarios), the squad profiles, the tolerant emission parser, and the planner's contract fragment as a managed prompt asset | #3041 (SIP-0118 phase 2f) | MacBook | M |
| **The product:** `z_tower-ascension`'s eligibility rules, registration and goal set, and a recorded comparison with the live game | #3042 (SIP-0118 phase 2g) | MacBook | S |

### The demonstration

| item | issue | lane | size |
|---|---|---|---|
| the pre-registration, the full-path gate, a rehearsal on `game-dev-roblox-lite-14b`, the repair diagnostic, and the counted two-increment run on the Spark with the MacBook worker, in an attended window | #3043 (SIP-0118 phase 3) | MacBook, then Spark | M |

## 3. The work no ledger row carries

Each is open as its own issue. The adoption PR records each in SIP-0117 by a numbered amendment (§9).

1. **Campaign delivery can't use a Studio verdict** (#3053). Without it there is no accepted source and no replay of
   increment one on candidate two, which is the claim's last step. Found by the outside review.
2. **The frozen scenario has no producer** (#3044). Without it, "fails on the baseline, passes on the candidate"
   can't be shown.
3. **A relaunch budget resets on unblock** (#3045). A worker that is online at every launch and offline at every
   dispatch would never escalate. The requesting side's wait and cancel, which revision 2 also put here, are built
   in #3052 (§11.2).
4. **No test enters at a live cycle and reaches a worker** (#3050). Each seam is proved against fixtures. CLAUDE.md's
   wiring-test rule exists because #1250, #1256 and #1261 were each latent from their own PR and found by a live
   cycle. The scripted squad (#2984) and the fixture worker make a two-increment Campaign deterministic, with no
   model and no MacBook.
5. **The worker isn't a service** (#3046). Part 2 left it out on purpose. The counted run depends on the worker
   being up, Studio open on the right place, and the Mac awake.
6. **An operator can't see the registry** without a database shell (#3047). Part 1 left the read route out on
   purpose.
7. **A Studio update blocks every run, with nothing to clear it** (#3048). The pin and its `not_executed` on a
   mismatch are correct. The missing piece is the recorded run that re-proves and re-pins.
8. **The request and evidence have no size limit** (#3049). The whole tree travels inline, is stored in the
   operation's row and is re-sent on every claim.

**The isolation test** (SIP-0117 R4.6) is a committed design on no ledger row. It goes in with the Studio adapter
(#3039), which gives it something to hold.

**One condition recorded, with no 2.8 work:** one worker credential is accepted for one trusted MacBook. A distinct,
revocable credential per host is required before a second worker is enrolled (the review's answer to question 8;
SIP-0117 R5.4 shares one client identity across workers).

## 4. Order

Sequencing, not dates.

1. **Adoption:** this PR merges, then the adoption PR (§9).
2. **The live engine-neutral path:** #3052 amended as §11.2 says, then merged; #3036 and #3045 after it, since
   availability and the relaunch budget read what #3052 reports.
3. **The frozen scenario and Campaign delivery** (#3044, #3053), built alongside step 2, since they share no files
   with it.
4. **The machinery Campaign** (#3050), after #3005, #3020 and steps 2 and 3. **Nothing from Studio is wired into a
   live cycle until it passes in CI.**

   Also built alongside steps 2–4: the Luau runner (#2906, Spark) and SIP-0116 phases 3, 5 and 6 (#3028, #3037,
   #3038).
5. **Studio:** the first slice (§5: read-only, after #3052's amendment), then the adapter (#3039) with the harness (#3040), payload measurement (#3049), re-qualification (#3048),
   the worker service (#3046) and the read surface (#3047).
6. **The Studio gate** (§5), read at the adapter's exit, before the squad's skills are replay-tested.
7. **The squad and the product** (#3041, #3042). The `game_dev_roblox` profile's requirements are switched on only
   after SIP-0116's phases 2–6 have shipped (SIP-0116 §14).
8. **The demonstration** (#3043), after #3053, #3046's reboot check and #3034:
   - its pre-registration, committed under `docs/plans/verification-sets/` before any of its runs;
   - the full-path gate;
   - the rehearsal;
   - the repair diagnostic;
   - the counted run, in an attended window.
9. **The cut** (§6).

## 5. The Studio gate: go, narrow or stop

The Studio adapter is the one large item, and the headline rests on it. The rule is stated now so the line can't
quietly stretch to fit the claim. It is read at the adapter's exit, and §6 gives each outcome its own cut evidence.

| outcome | when | what the line does |
|---|---|---|
| **go** | each operation is qualified on the worker, unattended, including after a Studio restart with no person involved | the claim stands as written, and the `game_dev_roblox` profile is switched on |
| **narrow** | sync, read-back and reset are proved, but play or the harness isn't reliable unattended | **the play-requiring profile stays switched off.** The claim narrows, by a revision of this plan before the cut, to the engine-neutral path proved end to end, the headless Luau checks, and Studio sync, read-back and reset demonstrated. The release notes state the reduced claim |
| **stop** | the tested state can't be confirmed inside Studio, or the place can't be reset reliably | **the play-requiring profile stays switched off.** The line ships the engine-neutral path and the Luau runner once their gates pass, and the plan returns to the owner with what was found |

**The Studio first slice** (confirmed by the owner, 2026-11-11):
- read-only, on `z_tower-ascension` only, with nothing published;
- part of the Studio adapter (#3039), built by the MacBook lane after #3052's amendment;
- an **early read** on this gate, not the gate's reading. It shows what the adapter's read side does on the real place
  before the transaction's writes and play are built. The gate is still read at the adapter's exit;
- its scope is stated in its own PR.

**If the line has to narrow for time** rather than for Studio:
- SIP-0116's lessons phase (#3038) is the one item to move;
- that move needs a numbered amendment to SIP-0116, since its activation rule requires all six phases;
- it also needs an explicit activation ruling from the owner before the profile is switched on (decision 6).

## 6. The cut

**For every outcome,** on top of CLAUDE.md's release cut procedure:
- **a shakeout pair on the existing stacks** (fastapi-react and nextjs, by the existing per-stack rule) shows those
  cycles unchanged. SIP-0116 closes only "with every existing stack's cycles unchanged";
- **the cut record says what the evidence doesn't cover.**

**The evidence each outcome requires:**

| evidence | go | narrow | stop |
|---|---|---|---|
| the machinery Campaign (#3050) green in CI on the tagged commit | required | required | required |
| the Luau runner's headless checks (#2906) | required | required | required |
| Studio operations qualified unattended, including after a restart | required | — | — |
| Studio sync, read-back and reset demonstrated on the worker | required | required | — |
| the counted two-increment run, read live against its pre-registration | required | — | — |
| the repair diagnostic, labelled apart | required | — | — |
| the reduced claim stated in the release notes | — | required | required |

**What the cut record says the evidence doesn't cover:** feel, visuals, multiplayer, parts or UI built in Studio,
effects outside the scenario vocabulary, and any Studio version the worker wasn't qualified on.

**SIP sweep:**
- SIP-0116 is promotable if all six phases shipped.
- SIP-0117 stays accepted, since Godot and Unity remain.
- SIP-0118 stays accepted, since its Unity row remains.

## 7. The rest of 2.8

**Moved here by 2.7's rulings R1 and R2,** ruled with decision 9:

| issue | what | ruling | why |
|---|---|---|---|
| #2954 | a crew's assessment reaches the digest and the next proposal | **in, Spark lane** | small, and a Campaign's record is incomplete without it |
| #2287 | an operator lease on the box outside Campaigns | **in, Spark lane,** as an operator's handover outside Campaigns | the rehearsals need the Spark to themselves, and today only a Campaign can hold it. **Taking the lease during the counted run is an intervention,** recorded under the pre-registration |
| #2421 | the sandbox runs a product's declared commands and starts a pinned revision in a disposable copy | **in, Spark lane, after #3050 and #2906** | not on the headline's path. It slips before any headline work does |
| #2709 | Project lifecycle completeness (SIP-0112 E.4.5) | **moves to the next feature line** | its files are the MacBook lane's, and that lane is fully on the headline. SIP-0112 stays open |
| #950 | the review packet at the plan gate | **moves to the next feature line** | 2.8 already changes the plan gate (offered contracts), and a second change there makes a regression unattributable |
| #2781 | a change request that adds a parameterized page | **moves to the next feature line** | a design change that needs its own outside review. The refusal stands, as designed |
| #2782 | a route anchor hidden by a stylesheet | **stays deferred** to the next evaluator cut that is explicitly placed (2.7's R5) | unchanged |

**Patches, outside the feature count:**
- **#3009, first, and the owner's:** from 2026-12-02 GitHub blocks `pull_request_target` in public repositories,
  and the required operator branch checks run only on that trigger, so nothing would merge.
  - **The fix is an administrator's setting:** the Actions event policy allows the trigger for
    `operator-branch-checks.yml` only. So no PR closes the issue.
  - **It is verified in GitHub's second test window, 2026-11-16, 16:00–18:00 UTC (11:00–13:00 ET).** A PR updated
    inside that window must get a passing run.
- **#3005 and #3020** before the machinery Campaign's gate.
- **#3034** before the demonstration relies on an approved plan reaching the next run (PR #3035 open).
- **#3010** stays in the patch lane.

**Not in 2.8:**
- Unity, Godot, and capability-pack packaging and loading (3.x);
- Open Cloud, publishing to Roblox, and any write to the real Tower Ascension repository or game;
- multiplayer;
- console views for the worker;
- binary capture evidence;
- #2847 (Project environments) and #2834 (console CLI parity).

## 8. Decisions (ruled 2026-11-11)

**The owner ruled all nine on 2026-11-11, at about 09:00 ET, as recommended in revision 2's write-up:** "good with
your recommednation. go". That recommendation was the outside review's ruling on each decision, plus two additions
from this plan: a newer send supersedes an older one (decision 2), and the machinery check runs as a two-increment
Campaign (§3, #3050). Decision 8 was ruled earlier the same day: "no doesn't cover that session already working".

| # | decision | ruling |
|---|---|---|
| 1 | the headline and its claim | **adopted,** with the pre-registration and reporting rules above |
| 2 | how an agent's request reaches the worker queue | **HTTP, with a second, narrow scope on the agent role:**<br>• enqueue, read and cancel are authorized only for the task the agent is running, at its **current dispatch identity**, which the runtime holds for that task (#2932);<br>• the handler carries that identity instead of the task id;<br>• enqueue is **idempotent** on the task and that identity, so a lost reply or an agent restart recovers the original operation;<br>• an enqueue under a **newer** identity for the same task cancels the older send's operation |
| 3 | what a Campaign does when its worker is unavailable | **wait in `launch_blocked` before launch.** During a cycle:<br>• an unclaimed request is `not_executed` at its limit;<br>• once play may have begun, `interrupted`, with Studio reconciled before any retry;<br>• only an availability-only gap is relaunched automatically, within a finite budget persisted against the logical increment across launches;<br>• each interruption is recorded, and spending the budget escalates |
| 4 | which lane builds the Luau runner (#2906) | **the Spark lane.** It owns the runner code, and it proves the headless path without Studio |
| 5 | the Studio gate | **the three-way gate in §5,** with each outcome's cut evidence written in §6 |
| 6 | SIP-0116's activation rule | **keep all six phases** for a requiring profile. If lessons must slip, a numbered SIP-0116 amendment and an explicit activation ruling come before the profile is switched on |
| 7 | when the counted run runs | **an attended window,** after the worker service's reboot check (#3046). Interventions are recorded under the pre-registration. Overnight counting is allowed only after an unattended rehearsal completes |
| 8 | the MacBook lane's open phase 3 PRs (#3032, #3033) | **they continue on their own review** and may merge on their own evidence. "Don't start any work" bound this session only |
| 9 | the carry-overs and patches | **as §7 rules them** |

## 9. Adoption

**This plan was adopted when #3051 merged (2026-11-11).** The adoption PR, after #3052 merged (`docs/2-8-0-plan-adoption`):
- places each row below in its SIP's ledger with its issue, and applies the `sip:` labels
  (`scripts/maintainer/sync_sip_labels.py`, then `refresh_open_issues.py`);
- writes SIP-0117 **R5.7** (R5.6 is #3052's), with the evidence for each part:
  - the eight items of §3 as new rows;
  - the declarative scenario, and the reading of the game-dev-roblox plan §2.6's "the frozen scenario" as the
    harness's scenario executor over a validated declaration;
  - decision 2's request path;
  - the condition of one credential per host before a second worker;
- writes SIP-0118's matching amendment: strategy's scenario is declarative (#3044, #3041);
- comments each issue's placement on the issue;
- adds the ROADMAP's 2.8 entry and the portfolio's rows.

| SIP | row | issue |
|---|---|---|
| SIP-0116 | phase 3, skills | #3028 |
| SIP-0116 | phase 4, tools | #3036 |
| SIP-0116 | phase 5, the Campaign's pin | #3037 |
| SIP-0116 | phase 6, lessons | #3038 |
| SIP-0117 | phase 2b part 3, the squad's side | #3023: shipped by #3052's own ledger edit when it merges, so the adoption PR places nothing for it |
| SIP-0117 | phase 2c, the Luau runner | #2906 |
| SIP-0117 | phase 2d, the Studio adapter and the isolation test | #3039 |
| SIP-0117 | phase 2e, the assertion harness and reader | #3040 |
| SIP-0117 | new rows (R5.7): the frozen scenario, time limits and waiting, the worker service, the read surface, re-qualification, payload limits, the machinery Campaign, Campaign delivery | #3044–#3050, #3053 |
| SIP-0118 | phase 2f, the squad | #3041 |
| SIP-0118 | phase 2g, the product | #3042 |
| SIP-0118 | phase 3, the demonstration | #3043 |

## 10. The outside review, round 1

It reviewed revision 1 at `8cec8262` and requested changes before adoption. The owner relayed it on 2026-11-11, and
it is posted on this PR. Each answer, with what revision 2 does:

| question | the review's answer | revision 2 |
|---|---|---|
| 1. is two increments sound evidence? | **agree,** if the selection, the counting window and the permitted operator actions are recorded before the run, every attempt is reported, and a failed increment is never swapped for an easier one | the claim's counting rules; #3043's pre-registration |
| 2. does the frozen scenario discriminate? | **change:** require an executed failure of the named assertion on the baseline, with anything unread blocking. Freeze the reader too. Review what it observes, since a check on a changed revision id can turn green while the player still can't open the door | #3044 |
| 3. the agent's request path | **agree with HTTP; change decision 2:** authorize against the current dispatch attempt, and make enqueue idempotent for it | decision 2, plus supersession by a newer send; #3023 |
| 4. relaunching on an unavailable worker | **change:** `interrupted` and a reconcile once play may have begun; a finite relaunch budget persisted per logical increment across launches; test a worker that is online at every launch and offline at every dispatch | decision 3; #3045 |
| 5. the machinery faults | **keep the four, and add a requester-side failure** (a dropped enqueue response and a requester restart give one operation and one credited result). Make #3044 a prerequisite, and enter through normal plan expansion | #3050, plus a superseded send and two increments with Campaign delivery |
| 6. the Studio gate | **change §6 before adopting §5:** give each outcome its own cut evidence | §5, §6 |
| 7. scope | **add an owned Campaign delivery item,** with a two-increment acceptance test, as a prerequisite for #3043 | #3053 |
| 8. worker authority | **accept for one trusted MacBook,** with a distinct, revocable credential per host before a second worker. Resolve what strategy may put in a scenario: declarative actions, observations and expected values, validated and executed by a trusted harness | §3's recorded condition; #3044, #3040, #3041 |

**Also settled on the review's recommendation:**
- **#3009:** an administrator applies the policy, verified in the 2026-11-16 test window;
- **#3049:** captures stay outside 2.8's acceptance evidence, and the limits are set from measurements.

## 11. Lanes, and the reconciliation with the MacBook lane (revision 3)

The owner, 2026-11-11, asked that this plan be reconciled with the MacBook session, and is holding that session's
work until the plan's assignments agree. The MacBook session wasn't reachable from the Spark (no peer session was
running). So this section is the reconciliation, read from the record:
- that lane's open PRs and branches;
- its SIP amendments;
- the adopted game-dev-roblox plan.

Each lane confirms it on this PR before resuming (§11.4).

### 11.1 One lane per issue

The basis is CLAUDE.md's file ownership: executor, handlers and framing are the MacBook lane's; the test runner,
build check, agent image and deploy are the Spark lane's. Where a ruling assigns a lane, the ruling is cited.

| lane | issue | what | basis |
|---|---|---|---|
| MacBook | #3023 → #3052 | the squad's side of remote execution (open, draft; amended per §11.2 before it merges) | the game plan; the owner's part 3 ruling |
| MacBook | #3028 → #3032, #3033 | SIP-0116 phase 3, skills (open) | the game plan; decision 8 |
| MacBook | #3035 | the gate promotes an approved run's artifacts before forwarding them (open, for #3034) | its author's lane |
| MacBook | #3036 | SIP-0116 phase 4, tools | the game plan |
| MacBook | #3037 | SIP-0116 phase 5, the Campaign's pin | the game plan. It touches Campaign launch, so it lands after #3045 (below) |
| MacBook | #3038 | SIP-0116 phase 6, lessons | the game plan |
| MacBook | #3044 | the frozen scenario, declarative | the handler and plan expansion |
| MacBook | #3039, #3040 | the Studio adapter and the harness | the game plan; they need Studio |
| MacBook | #3046, #3048, #3049 | the worker service, re-qualification, payload limits | they need the MacBook and Studio |
| MacBook | #3041, #3042 | the squad and the product | the game plan |
| MacBook, then Spark | #3043 | the demonstration: the rehearsal and the diagnostic on the MacBook; the counted run on the Spark | the game plan §5 |
| Spark | #3053 | Campaign delivery | `campaigns/` acceptance and the product runner |
| Spark | #3050 | the end-to-end machinery Campaign | CI and the scripted squad |
| Spark | #3005, #3020 | the scripted squad's two defects | the scripted provider |
| Spark | #2906 | the Luau runner | decision 4 (the game plan said MacBook; decision 4 moved it) |
| Spark | #3045 | the Campaign's relaunch budget | **ruled 2026-11-11:** `campaigns/launch_blocking.py`. #3052 holds the in-cycle part |
| Spark | #3047 | the operator's read surface | **ruled 2026-11-11:** the Spark runs the runtime the operator reads. The MacBook lane holds every other headline item |
| Spark | #2954, #2287, #2421, #3010 | the ride-alongs and the patch | decision 9 |
| Spark | — | the Spark deploy's `.env` gains `SQUADOPS__REMOTE_EXECUTION__PROVIDER=none` before its first rebuild after #3052 merges | deploy (#3052's own note) |
| the owner | #3009 | the Actions policy, verified 2026-11-16 16:00–18:00 UTC | an administrator's setting |

**Where both lanes change one area,** the order is fixed so neither rebases onto the other's half-built work:
- **`campaigns/`:** #3053, then #3045, then #3037.
- **`remote_execution/`:** #3052, then #3036.
- **SIP-0117's ledger:** #3052's edit, then the adoption PR.

### 11.2 #3052 against decision 2

**The timing.** #3052 was built on the owner's ruling "approve part 3 as recommended", given to the MacBook session
before it opened the PR at 08:41 ET. Decision 2 was ruled about 09:00 ET, after the outside review. It refines the
earlier ruling and doesn't reverse it. **Decision 2 governs where the two differ** (the owner, 2026-11-11: "approve both lanes to spark, decision 2 governs").

**Where they agree, and #3052 stands as built:**
- the transport is HTTP;
- the one scope `operations:request` is held by the agent role alone;
- the selector is required, with `none` binding no port;
- with no worker being heard from, nothing is queued and the result is `not_executed`;
- the 900-second wait ends with a cancel, and a cancelled claim whose lease runs out settles `interrupted`;
- a refusal or an unreadable answer is raised.

Its review points 1–5 and 8 (SIP-0117 R5.6 on its branch) are consistent with this plan. **Proposed: accept them as
built.**

**Where they differ.** #3052's review points 6 and 7 are what decision 2 answers:

| | decision 2 | #3052 as built | proposed change to #3052, before it merges |
|---|---|---|---|
| 1 | enqueue, read and cancel only for the task the agent is running, at its current dispatch identity | any agent may read or cancel any operation whose id it knows (its point 6) | the routes check the operation's origin (task and dispatch identity) against the runtime's current dispatch for that task, and refuse otherwise |
| 2 | enqueue is idempotent on the task and its dispatch identity, so a lost reply or a restart recovers the original operation | no answer to the request to queue reads `not_executed`, "nothing is known to be queued", though the operation may be stored and later run in Studio, read by nobody | create is keyed on the task and its dispatch identity, and a repeat returns the stored operation. The adapter asks again on no answer instead of reporting `not_executed` |
| 3 | an enqueue under a newer dispatch identity for the same task cancels the older send's operation | an agent that dies while it waits leaves its operation to run, read by nobody (its point 7) | create under a newer identity cancels the older send's operation, which then settles as the lease rules say |
| — | the request carries the send's dispatch identity | the handler sends the task id (`run_remote_operation.py:136`) | the handler carries the identity the agent echoes in its reply (#2932) |

**Why before it merges:**
- #3052 is the PR that completes #3023, and it's still a draft;
- the machinery Campaign's dropped-response and superseded-send faults (#3050) have nothing to pass without these
  changes;
- point 2 is an unaccounted operation: Studio, under the owner's login, runs work nobody reads.

### 11.3 What changes in the MacBook lane's documents

Where this plan and the adopted game-dev-roblox plan differ, **this plan governs 2.8.** The adoption PR adds a note at
the top of the game plan naming each difference:

| the game plan | 2.8 | by |
|---|---|---|
| §3: the Luau runner (2c) built by the MacBook lane | the Spark lane | decision 4 |
| §2.6 and §2.7: "the frozen scenario" among the harness's fixed programs, and its assertions in Luau | a declarative scenario of actions, observations and expected values, validated and executed by the harness | #3044; SIP-0117 R5.7 and SIP-0118's amendment |
| §1: "the criterion fails on the accepted baseline" | the named assertion **executes** and fails, and anything unread blocks; the counting rules | #3044, #3043 |
| no row for Campaign delivery | #3053, the Spark lane | the outside review, answer 7 |
| §2.5: the worker protocol | plus decision 2's request path (§11.2) and one credential per host before a second worker | decision 2; §3 |
| §5: the counted run on the Spark | in an attended window, after #3046's reboot check | decision 7 |

### 11.4 Before each lane resumes

**The MacBook session** (after its model is reset) reads, in order:
- this plan at revision 3;
- the outside review and revision 2's response, both comments on this PR;
- the request-path comment on #3023.

It then posts on this PR, for each of §11.1's MacBook rows, §11.2's three points and §11.3, whether it **confirms**
or **objects**, with the evidence for any objection. **Its first work on resuming is §11.2's change to #3052.**

**The Spark session** confirms §11.1's Spark rows on this PR. It builds nothing until the plan is adopted.

**The owner:**
- rules the two proposed lanes (#3045, #3047) and §11.2's "decision 2 governs" (**ruled 2026-11-11:** "approve both lanes to spark, decision 2 governs");
- reads each lane's confirmation;
- merges this PR to adopt the plan.
