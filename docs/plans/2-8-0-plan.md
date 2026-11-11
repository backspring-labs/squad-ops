# 2.8.0 plan: a squad develops and tests a Roblox game

**Status: DRAFT, revision 1 (2026-11-11), for an outside review.** The owner asked for a 2.8 plan whose headline is
the game-development work, with a review of what the MacBook lane has merged for it and what more it needs to hold
up. **Nothing is placed and nothing is built on this plan until the owner adopts it after the outside review.** The
issues it proposes are open so the review can read them, and they carry no `sip:` label and no ledger row until
adoption (§9).

## Revision log

- **Revision 1** (2026-11-11): the first draft. It reviews the game work on main at `5bfa2c7e`, places every
  remaining ledger row of SIP-0116, SIP-0117 and SIP-0118, adds seven hardening items that no ledger row carries
  (#3044–#3050), and proposes rulings on the six features 2.7 moved here.

## What 2.8 is

An even minor, so a feature release, led by one headline (CLAUDE.md, #281). The headline is the Roblox work. The
Spark lane carries the end-to-end machinery cycle and the Luau runner that the headline needs, and the ride-alongs in
§7.

**The claim, as the adopted game-dev-roblox plan states it (§1 there, decision D1, accepted 2026-11-08):**

> **A squad running on the Spark takes two small increments of an existing Roblox game from design to accepted
> source, each proved in a real play session in Roblox Studio, on a private copy of Tower Ascension.** For each
> increment:
> 1. strategy writes a change request with a player-facing criterion and its play scenario, frozen before
>    development;
> 2. the criterion fails on the accepted baseline;
> 3. dev writes the Luau change;
> 4. qa's operation syncs the candidate into Studio, plays the frozen scenario and reads its assertion records;
> 5. the criterion passes on the candidate, and the Campaign's gate accepts the source onto the campaign branch.
>
> The second increment is accepted with the first increment's frozen checks re-run and passing.

**Beside it, labelled apart:** a pre-registered repair diagnostic. A seeded behavioural defect fails the unchanged
verifier as an executed failure, the repair is routed, and the same verifier, by digest, passes. It proves the
correction route. It isn't evidence about the models.

**What the evidence won't show:** how the game feels or looks, more than one player, and parts, models or UI built in
Studio, since those don't sync to files.

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
dispatch). This plan places phase 3 in 2.8 (§2). Both are inert for every profile that requires nothing.

**What the review found.**
- **The code fails closed throughout.** Every assertion a scenario declares produces exactly one check row, and
  one that didn't execute is never a pass (`run_remote_operation.py:311-352`). A stale or late result is refused
  with one of seven named reasons and kept (`leasing.py`, `fence_refusal`). A supplier whose digest moved since the
  cycle was created is refused. The owner's no-silent-reads sweep (SIP-0116 §17d) took out the fallbacks that were
  there.
- **No defect was found** in what merged.
- **No live cycle can reach a worker yet.** Three links are missing:
  - **nothing binds the remote-execution port.** No adapter implements `RemoteExecutionPort` outside the tests, so a
    live scenario task reads "not executed: no port bound". That's the squad's side of remote execution (#3023,
    part 3);
  - **nothing produces the frozen scenario.** The handler requires `operation_scenario` and no step in a live cycle
    writes it (SIP-0117 R5.1 says so). No ledger row owns it (#3044);
  - **no skillset, no `game_dev_roblox` profile and no Studio adapter exist,** and the planner's prompt doesn't show
    contracts yet (SIP-0116 §17c point 1).

**Where the ledgers stand.** Across the three SIPs, the rows the headline needs number 18: **7 shipped and 11 to
build.** Seven hardening items no row carries come on top (§3).

## 2. The work

Sizes are the SIPs' own where they give one (S, M, L). A size marked * is this plan's estimate and is unmeasured.

### The engine-neutral path, live

| item | issue | lane | size |
|---|---|---|---|
| **The squad's side of remote execution:** the adapter behind the port, its required selector (`none` = no remote execution), and how an agent's request reaches the queue (needs the ruling in §8, decision 2) | #3023, part 3 | MacBook | M* |
| **Tools:** the authorization and availability refusals at creation, and availability read again at dispatch | #3036 (SIP-0116 phase 4) | MacBook | M |
| **Time limits and an unavailable worker:** a limit on waiting for a claim and on the whole operation; a Campaign whose worker is unavailable waits in `launch_blocked` instead of spending increments | #3045 | MacBook | M* |
| **The end-to-end machinery cycle:** the scripted squad and the fixture worker through plan, claim, verdict, repair, re-run and delivery, with four injected faults, in CI and as a cut gate | #3050 | Spark | M* |
| its prerequisites: a scripted squad's answer key survives an agent restart; a scripted repair's refused edit is named, not read as empty | #3005, #3020 | Spark | S* each |

### The frozen scenario and the headless half

| item | issue | lane | size |
|---|---|---|---|
| **The frozen scenario:** carried by strategy's change request as a criterion file, digested before development, run on the accepted baseline and refused when it already passes there. It reuses the increment's frozen criterion files and the first-emission-passes-on-head rule (#2992) | #3044 | MacBook | M* |
| **The Luau runner:** a `luau` runner kind, a test-id reader, a worked example | #2906 (SIP-0117 phase 2c) | **Spark** (§8, decision 4) | M |

### Studio

| item | issue | lane | size |
|---|---|---|---|
| **The Studio adapter:** the transaction under one lease, the adapter's own sync, paged read-back, the full baseline before and after play, reset (including reopening Studio), deadlines, the deny list, returned edits as revisions, four operations, and the isolation test SIP-0117 R4.6 commits to | #3039 (SIP-0117 phase 2d) | MacBook | L |
| **The assertion harness and reader:** one structured record per assertion; every outcome produced on purpose | #3040 (SIP-0117 phase 2e) | MacBook | M |
| **Payload limits:** measure the request, claim and row sizes on the real tree (about 1.7 MB), then refuse past a stated limit; decide how a capture travels | #3049 | MacBook | S* |
| **Re-qualification after a Studio update:** a recorded run moves the pin, never a hand edit | #3048 | MacBook | S* |
| **The worker as a service on the MacBook:** launchd, stay-awake, Studio opened on the place, `doctor dev-mac` checks, an optional bootstrap step | #3046 | MacBook | M* |
| **The operator's view of the registry:** a read-only route and `squadops workers list` / `show` | #3047 | either | S* |

### Skills, the squad and the product

| item | issue | lane | size |
|---|---|---|---|
| **Skills:** kept with the cycle, handed at dispatch with repair lineage, budgeted (in flight as #3032, #3033) | #3028 (SIP-0116 phase 3) | MacBook | M–L |
| **The Campaign's pin** on the equipment assigned to its work | #3037 (SIP-0116 phase 5) | MacBook | M |
| **Lessons** under the development profile's recall identity | #3038 (SIP-0116 phase 6) | MacBook | M |
| **The squad:** the `game_dev_roblox` profile, three skillsets and their replay-tested skills, the squad profiles, the tolerant emission parser, and the planner's contract fragment as a managed prompt asset | #3041 (SIP-0118 phase 2f) | MacBook | M |
| **The product:** `z_tower-ascension`'s eligibility rules, registration and goal set, and a recorded comparison with the live game | #3042 (SIP-0118 phase 2g) | MacBook | S |

### The demonstration

| item | issue | lane | size |
|---|---|---|---|
| the full-path gate, a rehearsal on `game-dev-roblox-lite-14b`, the repair diagnostic, and the counted two-increment run on the Spark with the MacBook worker | #3043 (SIP-0118 phase 3) | MacBook, then Spark | M |

## 3. The hardening no ledger row carries

Each is open as its own issue, and the adoption PR records each in SIP-0117 by a numbered amendment (§9).

1. **The frozen scenario has no producer** (#3044). This is the largest gap. Without it, "fails on the baseline,
   passes on the candidate" can't be shown, and that's the claim.
2. **Nothing on the requesting side bounds the wait** (#3045). Part 1 has no background sweep of leases, the worker
   has no time limit of its own, and SIP-0117 R5.5 leaves cancelling to the requester. If the MacBook sleeps, an
   operation sits queued, or an overnight Campaign spends its increments as `blocked_unverified`.
3. **No test enters at a live cycle and reaches a worker** (#3050). Each seam is proved against fixtures. CLAUDE.md's
   wiring-test rule exists because #1250, #1256 and #1261 were each latent from their own PR and found by a live
   cycle. The scripted squad (#2984) and the fixture worker make that cycle deterministic, with no model and no
   MacBook.
4. **The worker isn't a service** (#3046). Part 2 left it out on purpose. The counted run depends on the worker
   being up, Studio open on the right place, and the Mac awake.
5. **An operator can't see the registry** without a database shell (#3047). Part 1 left the read route out on
   purpose.
6. **A Studio update blocks every run, with nothing to clear it** (#3048). The pin and its `not_executed` on a
   mismatch are correct. The missing piece is the recorded run that re-proves and re-pins.
7. **The request and evidence have no size limit** (#3049). The whole tree travels inline, is stored in the
   operation's row and is re-sent on every claim, and evidence is text only.

**The isolation test** (SIP-0117 R4.6) is a committed design on no ledger row. It goes in with the Studio adapter
(#3039), which gives it something to hold.

## 4. Order

Sequencing, not dates.

1. **The outside review, then adoption** (this PR, then the adoption PR). The ruling on how an agent's request
   reaches the queue (§8, decision 2) comes before #3023 part 3 is built.
2. **The live engine-neutral path:** #3023 part 3, #3036 and #3045 together, since availability and the time limits
   share the registry read.
3. **The machinery cycle** (#3050), after #3005 and #3020. **Nothing from Studio is wired into a live cycle until
   it passes in CI.**

   Built alongside steps 2 and 3, since they share no files with them: the frozen scenario (#3044), the Luau runner
   (#2906, Spark), and SIP-0116 phases 3, 5 and 6 (#3028, #3037, #3038).
4. **Studio:** the adapter (#3039) with the harness (#3040), payload measurement (#3049), re-qualification (#3048),
   the worker service (#3046) and the read surface (#3047).
5. **The Studio gate** (§5), read at the adapter's exit, before the squad's skills are replay-tested.
6. **The squad and the product** (#3041, #3042). The `game_dev_roblox` profile's requirements are switched on only
   after SIP-0116's phases 2–6 have shipped (SIP-0116 §14).
7. **The demonstration** (#3043): its pre-registration first, committed under `docs/plans/verification-sets/`
   before any of its runs, then the full-path gate, the rehearsal, the repair diagnostic, and the counted run.
8. **The cut** (§6).

## 5. The Studio gate: go, narrow or stop

The Studio adapter is the one large item, and the headline rests on it. The rule is stated now so the line can't
quietly stretch to fit the claim. It is read at the adapter's exit.

| outcome | when | what the line does |
|---|---|---|
| **go** | each operation is proved on the worker, including after a Studio restart with no person involved | the claim stands as written |
| **narrow** | sync, read-back and the baseline are proved, but play or the harness isn't reliable unattended | the claim narrows, before the cut and in this plan by revision: the engine-neutral path proved end to end with the fixture provider in CI, Luau logic tests run headless, and the Studio transaction without play. The narrowing is said in the release notes |
| **stop** | the tested state can't be confirmed inside Studio, or the place can't be reset reliably | the `game_dev_roblox` profile isn't switched on in 2.8. The line ships the engine-neutral path and the Luau runner, and the plan returns to the owner with what was found |

If the line has to narrow for time rather than for Studio, SIP-0116's lessons phase (#3038) is the one item to move.
That move needs a numbered amendment to SIP-0116, since its activation rule requires all six phases (§8, decision 6).

## 6. The cut

On top of CLAUDE.md's release cut procedure:
- **the counted run** read live against its pre-registration;
- **the repair diagnostic** read, labelled apart from the counted evidence;
- **the machinery cycle** green in CI on the tagged commit;
- **a shakeout pair on the existing stacks** (fastapi-react and nextjs, by the existing per-stack rule) showing those
  cycles unchanged. SIP-0116 closes only "with every existing stack's cycles unchanged";
- **the cut record says what the evidence doesn't cover:** feel, visuals, multiplayer, parts or UI built in Studio,
  and any Studio version the worker wasn't qualified on;
- **SIP sweep:** SIP-0116 is promotable if all six phases shipped. SIP-0117 stays accepted, since Godot and Unity
  remain. SIP-0118 stays accepted, since its Unity row remains.

## 7. The rest of 2.8

**Moved here by 2.7's rulings R1 and R2.** A recommendation on each:

| issue | what | recommendation | why |
|---|---|---|---|
| #2954 | a crew's assessment reaches the digest and the next proposal | **in, Spark lane** | small, and a Campaign's record is incomplete without it |
| #2287 | an operator lease on the box outside Campaigns | **in, Spark lane** | the counted run and the rehearsals need the Spark to themselves, and today only a Campaign can hold it |
| #2421 | the sandbox runs a product's declared commands and starts a pinned revision in a disposable copy | **in, Spark lane, after #3050 and #2906** | not on the headline's path. It may slip to the next feature line without touching the claim |
| #2709 | Project lifecycle completeness (SIP-0112 E.4.5) | **move to the next feature line** | its files are the MacBook lane's, and that lane is fully on the headline. SIP-0112 stays open |
| #950 | the review packet at the plan gate | **move to the next feature line** | 2.8 already changes the plan gate (offered contracts), and a second change there makes a regression unattributable |
| #2781 | a change request that adds a parameterized page | **move to the next feature line** | a design change that needs its own outside review. The refusal stands, as designed |
| #2782 | a route anchor hidden by a stylesheet | **stays deferred** to the next evaluator cut that is explicitly placed (2.7's R5) | unchanged |

**Patches, outside the feature count, either lane:**
- **#3009, first and on a fixed date:** from 2026-12-02 GitHub blocks `pull_request_target` in public repositories,
  and the required operator branch checks run only on that trigger, so nothing would merge.
- #3010 (the weekly dependency refresh fails on the tree-sitter cap), #3034 (an approved gate's next run can start
  before the approved run's artifacts are promoted; PR #3035 open), and #3005 and #3020 (above).

**Not in 2.8:** Unity, Godot, capability-pack packaging and loading (3.x), Open Cloud, publishing to Roblox, any write
to the real Tower Ascension repository or game, multiplayer, console views for the worker, #2847 (Project
environments) and #2834 (console CLI parity).

## 8. Decisions for the owner

Each has a recommendation. The owner overrules; nothing is left open.

| # | decision | recommendation | why |
|---|---|---|---|
| 1 | the headline and its claim | **as above**, unchanged from the adopted game plan | it was accepted with the spike gate's go on 2026-11-08 |
| 2 | how an agent's request reaches the worker queue (#3023's open question) | **a second, narrow scope on the agent role:** request and read an operation only for the task the agent is running, checked against the task's dispatch identity | plain HTTP gives typed refusals and the standard error envelope. The queue path needs a new message type and a reply waiter held for minutes, with redelivery semantics across an agent restart, the area 2.7 spent effort making hold. SIP-0116 §8 is unaffected: the scope carries a request, and the operation's own deny list still decides what runs |
| 3 | what a Campaign does when its worker is unavailable (#3045) | **at launch, wait in `launch_blocked`** and escalate as a busy engine does today. **In a cycle,** a limit on the claim wait and on the operation, each `not_executed` with its reason. **An increment whose only gap is availability is re-launched,** not counted as spent, within `launch_blocked`'s existing attempts, then escalated | reuses the Campaign's existing waiting state. An overnight Campaign doesn't burn its increments while the MacBook sleeps |
| 4 | which lane builds the Luau runner (#2906) | **the Spark lane** | it's test-runner code (the Spark lane's by file ownership), it runs headless under Lune on the Spark, and it takes load off the MacBook lane, which holds every other headline item |
| 5 | the Studio gate's rule (§5) | **adopt it as written** | the headline rests on one large item, and the rule keeps a narrowing explicit |
| 6 | SIP-0116's activation rule (all six phases before a requiring profile is switched on) | **keep it.** If the line must narrow for time, the lessons phase is the candidate, by amendment | the rule exists so loading, authorization, budgeting, pinning and lessons all apply to the first consumer |
| 7 | when the counted run runs | **in an attended window,** with the worker service's reboot check (#3046) passed first | the worker depends on the MacBook being awake and Studio open. An overnight counted run waits until the service has run unattended through a rehearsal |
| 8 | the MacBook lane's open phase 3 PRs (#3032, #3033) during the review | **continue to review and merge them on their own terms** | SIP-0116 is accepted, phase 3 is inert for every profile that requires nothing, and this plan places it in 2.8 unchanged |
| 9 | the carry-overs and patches (§7) | **as recommended there** | — |

## 9. Adoption

The adoption PR, after the outside review:
- places each row below in its SIP's ledger, with its issue, and applies the `sip:` labels
  (`scripts/maintainer/sync_sip_labels.py`, then `refresh_open_issues.py`);
- records the seven hardening items in SIP-0117 as a numbered amendment (R5.6) with the evidence for each. They add
  design: the time limits, the Campaign's waiting, re-qualification and the payload limit;
- comments each issue's placement on the issue;
- adds the ROADMAP's 2.8 entry and the portfolio's rows.

| SIP | row | issue |
|---|---|---|
| SIP-0116 | phase 3, skills | #3028 |
| SIP-0116 | phase 4, tools | #3036 |
| SIP-0116 | phase 5, the Campaign's pin | #3037 |
| SIP-0116 | phase 6, lessons | #3038 |
| SIP-0117 | phase 2b part 3, the squad's side | #3023 |
| SIP-0117 | phase 2c, the Luau runner | #2906 |
| SIP-0117 | phase 2d, the Studio adapter and the isolation test | #3039 |
| SIP-0117 | phase 2e, the assertion harness and reader | #3040 |
| SIP-0117 | new rows (R5.6): the frozen scenario, time limits and waiting, the worker service, the read surface, re-qualification, payload limits, the machinery cycle | #3044–#3050 |
| SIP-0118 | phase 2f, the squad | #3041 |
| SIP-0118 | phase 2g, the product | #3042 |
| SIP-0118 | phase 3, the demonstration | #3043 |

## 10. Questions for the outside review

1. **Is the claim sound evidence for "a squad develops and tests a game"** at two increments, given the
   repair diagnostic is labelled apart? What would make two increments misleading?
2. **The frozen scenario (#3044):** is a scenario carried as a criterion file, frozen by digest and refused when it
   passes on the baseline, enough to show the criterion discriminates? What can a scenario author do to pass it
   vacuously that the harness's per-assertion records wouldn't catch?
3. **The agent's request path (§8, decision 2):** is a second agent scope bound to the running task's dispatch
   identity the right trade against carrying the request over the task queue?
4. **An unavailable worker (#3045):** is re-launching an increment whose only gap is availability right, or does it
   hide a worker that is down more than it is up?
5. **The machinery cycle (#3050):** are the four injected faults (a worker stopped mid-lease, a cancel, a late result
   after a re-claim, offline at dispatch) the right set? What failure of the live path would still get past it?
6. **The Studio gate (§5):** is "narrow" stated tightly enough that it can't be read as "go"?
7. **Scope:** is anything in §2 not needed for the claim, or anything missing that the claim needs?
8. **Security:** the worker holds one client secret on the MacBook and acts under the owner's Studio login. Is the
   authority boundary in the game plan's §2.5 (it reads only its operation's inputs, writes only its result, and
   never rules, promotes or browses) enough, given one client identity is shared by every worker (SIP-0117 R5.4)?
