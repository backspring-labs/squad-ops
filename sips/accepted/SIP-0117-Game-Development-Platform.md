---
sip_uid: '17922784453538440'
sip_number: 117
title: Game Development Platform Capability
revision: 4
status: accepted
author: Framework Committee
approver: null
created_at: '2026-10-16T00:00:00Z'
updated_at: '2026-11-10T13:51:38.893678Z'
original_filename: SIP-Game-Development-Platform.md
---
# SIP-0117 — Game Development Platform Capability
## Engine integration plugins (Roblox, Godot, Unity) and Remote Tool Execution

**Status:** **Accepted (2026-11-10):** the owner, "accept 2405 then 2841", after the renewed review D9 called for. Filed 2026-10-17 as the owner's draft. **Building:** its phases may be built in a MacBook worktree during 2.7 (D6); nothing merges until 2.8 opens and its plan places them.  
**Revision 4 (2026-11-09):** on SIP-0116, Agent Skillsets, accepted the same day. Roblox integration is a development profile that requires skillsets, agents that carry them, and a provider behind the remote-execution adapter (§R4, which governs where §R3, §R2 or the body differs). Its design calls and Q68 were ruled by the owner on 2026-11-09 (R4.8).  
**Target Version:** TBD  
**Author:** Framework Committee  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data  
**Date:** 2026-10-16  
**Document Revision:** 4 (2026-11-09) — Roblox as skillsets, a provider and a development profile, on SIP-0116: operations implement engine-neutral capability contracts, each in a declared verification mode, and `qa.run_remote_operation` is proposed as the first new plannable type (§R4, which governs). Revision 3 (2026-11-08): the in-tree `game-dev-roblox` specialty, the spikes' evidence and the owner's decisions D1–D10 (§R3, which governs where §R2 or the body differs). Revision 2 (2026-10-31): the owner's outside review applied: engine integration as versioned plugins, Unity as a third provider, the remote-execution contract apart from game operations, per-adapter verification modes, editor changes through the revision boundary, greenfield blueprints apart from existing repositories, one delivery milestone per engine, and tailored squads (§R2, which governs where the body below differs). Revision 1: the owner's draft, filed as written  
**Related SIPs:** SIP-0112 (Project Lifecycle Management, accepted 2026-10-17: its FR-17 is what this SIP builds on); SIP-0070 (Pulse Checks); SIP-0071 (Builder Role); SIP-0072 (stack development profiles); SIP-0086 (Build Convergence Loop); SIP-0096 (Verification Evidence Integrity); SIP-0103 (owns the word *manifest*); SIP-0105 (stack blueprints); SIP-0108 (Cycle Evaluation Scorecard); SIP-0113 (Outcome Evaluation, accepted 2026-10-17); SIP-0116 (Agent Skillsets, accepted 2026-11-09: this SIP is its first consumer); Edge Deployment Profile (proposed, deferred to 3.x)  
**Companion:** SIP-0118, Game Development Capability Packs and Squad Composition (`sips/accepted/SIP-0118-Game-Development-Capability.md`, accepted 2026-11-10): what a game squad is composed of. This SIP is how engines are integrated; that one is how a squad uses them.  
**Scope:** SquadOps framework capability; no new agent role required; tailored squad configurations of the existing roles are supported (§R2.9)

## Intake check

Checked against `sips/PORTFOLIO.md` on 2026-10-17, before this draft was recorded (CLAUDE.md, "SIP
System"). The owner's direction on PR #2401 was to file this SIP separately (Q33), with Project Lifecycle
Management's FR-17 describing the capabilities it offers future game adapters. The body below is the
owner's text, unchanged. The findings wait for its first revision, and three wait for the owner (Q37–Q39
in the portfolio's §4).

- **Builds on, and the boundary:** **SIP-0112, Project Lifecycle Management** (accepted 2026-10-17, PR
  #2401; the MacBook lane's 2.4 feature). Its FR-17 lists what a target adapter builds on, and its UC-D is this SIP's flow. A
  game is an ordinary Project, with no registry or orchestration of its own:
  - its identity is the registry's Project Record (Q32: the registry stays authoritative), so the Game
    Project Contract's `game.id` (§5.2) reads as a reference to the registered `project_id`, never a
    second identity;
  - its engine, engine version, native commands and toolchain are the technical target in its *Project
    Development Configuration* (Q36);
  - the Game Project Contract carries what is particular to a game: mechanics, controls, success and
    failure paths, verification modes and benchmark scenarios;
  - its `publishing.mode` reads under the Project Record's `governance.publishing`, and publish
    credentials stay in secret storage (Project Lifecycle FR-13);
  - the remote worker is an execution resource, never a Project or an agent (FR-17's last item, and this
    SIP's §5.4).
- **Overlaps, and the boundary each gets:**
  - **SIP-0070 and SIP-0086, read under Q33.** The body's Cycle → Pulse → Surge → Task semantics come from
    `docs/ideas/IDEA_Cycle_Orchestrator_Pulses_and_Surges.md`, which Appendix D cites as an uploaded file.
    SIP-0112's PR (#2401) committed it with a non-normative header. By Q33, SIP-0070's cadence-bounded Pulse governs
    where the two differ, and the code has no Surge. The body's own rule stands: this SIP changes no Cycle
    or Pulse semantics. FR-13's "non-gating repair Surges" read as repair through the existing paths,
    SIP-0070's repair loop at a pulse boundary and SIP-0086's correction loop, and FR-08's rule that a
    worker never rewinds a Cycle or emits a Pulse reads against the same paths.
  - **SIP-0072, SIP-0105 and SIP-0071: where a stack is declared.** A Godot or Roblox target is a new
    stack: a SIP-0072 §10a *development profile*, selected by the cycle request's `development_profile`
    key and checked against SIP-0071's `build_profile` in `prepare_cycle()`, and a SIP-0105 blueprint
    for what a greenfield game scaffolds. The first revision states which of §5.3's operations the stack
    declares and which the adapter adds.
  - **SIP-0071's builder role.** The `full` and `lite` squads carry a builder, which produces the
    runnable artifacts; Appendix B gives building to Dev and names no builder. "Dev" here reads as the
    role the task plan assigns the build step, and no role changes (the body's §4).
  - **SIP-0096: verification evidence.** FR-09, FR-10 and FR-12's PASS, FAIL and UNVERIFIED are SIP-0096's
    three evidence families: executed-and-passed, executed-and-failed and not-executed, with
    `blocked_unverified` as a run verdict. Game checks report through that vocabulary and its roll-up,
    and only executed-and-passed credits.
  - **SIP-0108 and Outcome Evaluation: benchmarking.** GameBench-01 (Appendix A) is a reference Project
    with a benchmark profile (Project Lifecycle B.4 and B.4.1), graded in SIP-0108's benchmark registry.
    FR-15's squad measures (duration, cost, attempts, interventions) are SIP-0108's scorecard and
    Outcome Evaluation's intervention ledger, with no parallel scorecard. The squad's own game tests
    (QA's, FR-12) and any held-out scenarios are separate corpora (the portfolio's clusters 3 and 5).
    Held-out scenarios stay out of every Project record, workspace and repository (Project Lifecycle
    §8.3).
  - **Remote Tool Execution, the Edge Deployment Profile and SIP-0102.** FR-05's worker registry (identity,
    capabilities, health) has the shape of the Edge Deployment Profile's `EdgeNodeRegistryPort`, which is
    deferred to 3.x (Q8), and the portfolio's cluster 12 gives remote nodes to Edge "if kept" (Q38).
    SIP-0102's sandbox keeps the live tree: a worker receives staged, checksummed inputs and returns
    evidence (FR-06, FR-07), and holds no second live tree.
  - **`play_game` and `agent_chess`** are registered sample projects (`config/projects.yaml`), with no
    engine target. Outcome Evaluation assumes no sample application (Project Lifecycle §8.3), and
    GameBench-01 enters as a Project through Project Lifecycle.
  - **`docs/ideas/IDEA-Governed-Outputs-Beyond-Apps.md`** names verification vocabulary as each output
    family's bottleneck. FR-10's three verification modes are this family's vocabulary. It complements
    this SIP.
  - **The two 2.4 lanes.** The MacBook in this draft is a runtime execution worker, and the MacBook *lane*
    (CLAUDE.md, "Versioning") is a development lane. By file ownership the remote execution, engine checks
    and worker deployment are the Spark lane's surfaces (test runner, build check, deploy infrastructure),
    and the target adapters' handler and framing parts are the MacBook lane's. Placement decides.
- **Conflict, for the owner (Q37):** §5.2 requires every game project to contain `game_project.yaml` and
  `GAME_DESIGN.md`, and FR-11 suggests a `game/` tree. Project Lifecycle FR-19 registers an existing
  repository "with no SquadOps metadata files and no onboarding edits to its source tree", and keeps its
  records as SquadOps Project metadata, with any in-repository export opt-in (B.5). **Recommended:** the
  Game Project Contract is SquadOps Project metadata by default, referenced from the Development
  Configuration. A greenfield game the squad creates may carry it in its repository as product content,
  and an existing game is never required to.
- **For the owner (Q38): one registry of remote execution resources.** **Recommended:** this SIP's worker
  registry is that registry, and Edge, if revived at 3.0, registers its nodes there. Worker health uses
  the canonical status vocabulary (`docs/agent-runtime-status-model.md`: `online`, `degraded`,
  `recovering`, `offline`), the precedent the 2026-10-04 ruling set for Edge, and *busy* is a lease on the
  worker's concurrency, apart from its health.
- **For the owner (Q39): the draft's vocabulary.** **Recommended,** for the first revision:
  - *manifest*: SIP-0103 owns the word, and Q32 renamed Project Lifecycle's for that reason. The "game
    project manifest" (§4) becomes the *Game Project Contract*, the body's own §5.2 name, and
    `ASSET_MANIFEST.json` (FR-11) becomes an *asset register*.
  - *outcome*: FR-15's *game outcome* and *squad outcome* would add two meanings to the word (cluster 2;
    Q3 keeps SIP-0108's, and SIP-0113, Outcome Evaluation, renamed its own to *scenario evidence*). They become *game quality* and *squad delivery*, each read through SIP-0108's
    scorecard dimensions.
  - *gate*: FR-12's QG-1 to QG-9 are checks, and a Cycle's gate is a decided workload gate (`Gate`,
    `GateDecision`). They become the *game checks*.
- **Revision 2's intake (2026-10-31):**
  - **The companion, *Game Development Capability Packs and Squad Composition*,** filed beside this revision:
    this SIP integrates engines, and it composes the squad that uses them. Both register through its plugin
    foundation, so there is one extension mechanism.
  - **Capability-Backed Agents** (proposed, deferred to 3.x, portfolio cluster 8): R2.3's manifest, SPI and
    pinning take its §21 taxonomy and pack mechanics as the starting point. The companion reconciles its
    deferral (its Q45).
  - **SIP-0102:** R2.7 returns editor changes as workspace patches, so the sandbox keeps the live tree.
  - **Project Goals and Backlog** (proposed): a game's goals and backlog are the Project's, as any product's.
- **Revision 3's intake (2026-11-08):** checked against `sips/PORTFOLIO.md` (cluster 18).
  - **The plan this revision follows:** the game-dev-roblox plan (`docs/plans/game-dev-roblox-plan.md`, PR #2972),
    adopted by the owner on 2026-11-08 with D1–D10, and its spike record beside it.
  - **Overlaps, no conflict:**
    - SIP-0110's Campaign snapshot and its `rebind` event (Appendix A §3.7), the precedent R3.4's digest pin follows;
    - SIP-0112's size preflight (H.21), which applies to the copy's 1.7 MB of Luau;
    - #2906, the 2.6 Roblox spike's gaps: a Luau runner kind, a language and so core (R3.2);
    - 2.7's dispatch identity (#2932) and the vault's durability (#2931), which R3.3's protocol builds on;
    - CLAUDE.md's task-type rules (#559), which R3.5's task type and planning change follow.
  - **Changes recorded rather than conflicts:**
    - R2.3's plugin registration is deferred to a trigger;
    - the body's inbound SSH transport is replaced by a worker that connects outward;
    - the body's Studio command-line `RunScript` mode is replaced by Studio's MCP server, which S1 proved;
    - the test universe is replaced by a local place file.

  Each is stated in §R3 with its evidence.
- **Revision 4's intake (2026-11-09):** checked against `sips/PORTFOLIO.md` (clusters 18 and 19).
  - **What this revision follows:** SIP-0116, Agent Skillsets, accepted 2026-11-09. Its intake recorded one conflict
    with this SIP's revision 3, resolved by the owner's direction: revision 3 put a `specialties` field on the squad
    profile and a specialty digest into the roster's hash. Revision 4 applies the resolution (R4.1).
  - **The boundary with SIP-0116:**
    - it owns the skillset spec, the capability-contract and verification-mode declarations, coverage at preflight
      and at the plan gate, the record, and the Campaign's pin;
    - this SIP owns the providers behind the remote-execution adapter, their operations and result readers, the
      worker registry, and the `qa.run_remote_operation` task type;
    - the companion owns the game contracts and the Roblox skillsets' content.
  - **Overlaps, no conflict:**
    - SIP-0072: the `game_dev_roblox` development profile is an ordinary profile with `platform` and `requires`;
    - SIP-0075: the squad profiles carry each agent's `skillsets`;
    - SIP-0112: how a profile with requirements is selected for a Campaign (Q58), settled by its amendment in the
      building PR;
    - SIP-0096: the contracts' evidence is its three families.
  - **One question (Q68), ruled 2026-11-09:** skillset ids keep SIP-0116's platform-first form, and the Roblox dev
    skillset is `roblox-luau-dev` (R4.8).
- **Sources Appendix D cites:** the IDEA above, now `docs/ideas/IDEA_Cycle_Orchestrator_Pulses_and_Surges.md`
  (non-normative, Q33); the testing, task-logging and documentation-traceability protocols, kept as
  `docs/ideas/Testing protocol.txt`, `docs/ideas/Task logging and metrics.txt` and
  `docs/ideas/Doc traceability.txt`; the repository's SIP template, `sips/TEMPLATE.md`.

## Delivery ledger (current as of 2026-11-26, the 2.9 plan's adoption)

One row per part that ships separately. Statuses: *shipped* (the release, the PR, and the issue it closed),
*placed* (the release and the open issue tracking it, labelled `sip:NNNN` once numbered), *unplaced* (said
deliberately), *dropped* (by the numbered amendment that dropped it), or *deferred to N.x (ruled <date>)*. Updated in
the PR that ships or re-places a part (`tests/unit/architecture/test_sip_ledgers.py` holds it). The rows follow the
adopted plan's phases, as revision 4 orders them (R4.7). The 2.8 plan places them, so none is placed yet. SIP-0116's
phases are in its own ledger.

| part | status | where |
|---|---|---|
| Slices A–E of revision 1 (§9.5) | **dropped** by Revision 2 (R2.10): restructured into milestones. None was placed | — |
| M0 as revision 2 cut it, on the companion's plugin foundation | **dropped** by Revision 3 (R3.9): re-cut as phase 2b on the in-tree seam | — |
| Phase 2a, part 1: `qa.run_remote_operation`: the task type, the engine-neutral request, result and assertion records, the remote-execution port, the handler and its evidence rows, the plan checks and the envelope, proved with a fixture provider (R4.4, R5.1) | **shipped** | 2.8 (PR #3019, closing #3017 and #3018) |
| Phase 2a, part 2: the correction route for a remote operation: a dev repair aimed at the implementation, the operation re-run on the repaired tree as the repair's deciding evidence, and the repaired source delivered (R4.4's correction mapping, R5.2) | **shipped** | 2.8 (PR #3019, closing #3017 and #3018) |
| Phase 2b, part 1: the runtime's side of remote execution: the worker registry and its migration, the claim, lease and fence rules, `/api/v1/workers`, and the worker's own identity (R3.3, R5.3, R5.4) | **shipped** | 2.8 (PR #3024) |
| Phase 2b, part 2: the worker: its composition root, the claim loop, and a fixture adapter (R3.3, R5.4) | **shipped** | 2.8 (PR #3027) |
| Phase 2b, part 3: the squad's side: the adapter behind the remote-execution port, its selector on every service that loads the configuration, and how an agent's request reaches the queue (R3.3, R5.3, R5.4, R5.6) | **shipped** | 2.8 (PR #3052, closing #3023) |
| Phase 2c: the Luau runner (#2906; core, R3.2), built by the Spark lane (the 2.8 plan's decision 4) | **shipped** | 2.8 (PR #3090, closing #2906; R5.13) |
| Phase 2d, the first slice: the Studio adapter's read side (the session, the tool check, identity as far as reading allows, paged read-back) and the isolation test (R3.6, R4.6, R5.11) | **shipped** | 2.8 (PR #3088; #3039 tracks the rest) |
| Phase 2d, the sync: the harness's fixed programs (identity and sync), `PlaceId` 0 confirmed before any write, and the adapter's own sync with its whole read-back (R3.6, D5, D10, R5.15) | **shipped** | 2.8 (PR #3107; #3039 tracks the rest) |
| Phase 2d, the place's state: the non-script baseline held through play, the synced scripts checked for attributes and tags, and play started and stopped (R3.6, R5.16) | **shipped** | 2.8 (PR #3112; #3039 tracks the rest) |
| Phase 2d, the reset: the place restored from its pinned baseline file and Studio reopened with no person involved, the reopened place confirmed unpublished and holding the pinned non-script baseline (R3.6, R5.17) | **shipped** | 2.8 (PR #3113; #3039 tracks the rest) |
| Phase 2d, the worker's side: the provider's settings in the worker's section, the runner found in its package, each claim held to the Studio it was proved on and the place's pinned baseline (a drifted place reset once), scripts held through play, and `play_scenario` the one operation served (R3.6, R4.3, R5.19) | **shipped** | 2.8 (PR #3116; #3039 tracks the rest) |
| Phase 2d, the rest: `play_scenario` proved on the worker's own loop against the real Studio, including after a Studio restart with no person involved (R2.4, R5.19, R5.20) | **shipped** | 2.8 (PR #3117, closing #3039) |
| Phase 2e: the assertion harness and reader: the harness executes a declarative scenario (R3.7, R5.7, R5.18) | **shipped** | 2.8 (PR #3115, #3040) |
| The frozen scenario, part 1: the declaration read strictly against a vocabulary handed in, its digest, the request carrying its text, the provider's check, one reading shape, the baseline rule, and the fixture's declared-scenario operation (R5.8) | **shipped** | 2.8 (PR #3058; #3044 tracks part 2) |
| The frozen scenario, part 2: the change request's scenario criterion and its placement, the operation task at plan expansion, and the named assertion executed and failing on the accepted baseline before development starts (R5.7, R5.8) | **shipped** | 2.8 (PRs #3063, #3066, #3067, #3068, #3070, #3073 and #3075, closing #3044) |
| A Campaign whose worker is unavailable: it waits in `launch_blocked` before launch, and an availability-only gap is relaunched within a budget persisted per logical increment, then escalated (R5.7) | **shipped** | 2.8 (PRs #3086 and #3087, closing #3045; R5.10 and R5.12) |
| The worker as a service on the MacBook: a per-user LaunchAgent started at login and again on exit, its tool reset (Studio opened on the place) before it registers, its own status recorded, a recorded run window, `doctor dev-mac`'s worker checks and an optional bootstrap step (R5.7, R5.23) | **shipped** | 2.8 (PR #3123; #3046 tracks the rest) |
| The worker service, the rest: registered with the Spark's runtime, and back after a restart of the MacBook and the owner's login, read once on 2026-11-16 and closed on the owner's ruling (R5.23, R5.24) | **shipped** | 2.8 (PR #3130, closing #3046) |
| The operator's read surface: a read-only workers route and `squadops workers list` and `show` (R5.7) | **shipped** | 2.8 (PR #3059, closing #3047) |
| Re-qualification after a Studio update: a recorded run moves the pin, never a hand edit (R5.7, R5.21) | **shipped** | 2.8 (PR #3119, closing #3048) |
| Payload limits: request and evidence sizes measured on the real tree, then explicit limits; captures outside 2.8's acceptance evidence (R5.7, R5.22) | **shipped** | 2.8 (PR #3121, closing #3049) |
| The end-to-end machinery Campaign: two increments, the scripted squad and the fixture worker, from a fixture change request through plan, claim, verdict, repair, re-run and delivery, with six faults injected, in CI (R5.7) | **shipped** | 2.8 (PRs #3074, #3080 and #3084, closing #3050). The faults are read on the remote-execution path, on Postgres in the integration job (#3074). The two-increment Campaign runs in the unit regression job, as it needs no service (#3084) |
| Campaign delivery: a scenario criterion accepted on evidence bound to the candidate's revision, and every earlier increment's scenario replayed on the same candidate (R5.7) | **shipped** | 2.8 (PRs #3057, #3061, #3064, #3069, #3072 and #3076, closing #3053) |
| The reader reads a screen's visibility: `gui_state` `visible` of a `ScreenGui` is its `Enabled`, with the provider's version moved and the worker requalified (R5.25) | **shipped** | 2.8 (PR #3175, closing #3176) |
| The worker's lease: a renewal carries the health read before the claim and never probes a running tool, and an operation that ended while a renewal was out submits its result and isn't reset (R5.26) | **shipped** | 2.8 (PR #3186, closing #3185) |
| The reset names a Studio update: Studio's version is read before the quit and after the reopening, a Studio that isn't the proved version is refused before anything is touched, and every reset's outcome goes on the worker's status (R5.27) | **shipped** | 2.8 (PR #3188, closing #3184) |
| A worker whose tool isn't ready is read as an absent one: `tool_unready` on a `not_executed` the worker returns for its own environment, so an increment blocked only by it is retried, never repaired (R5.28) | **shipped** | 2.8 (PR #3195, closing #3192) |
| Studio's qualification identity includes its release channel: read from the running Studio's startup log, held to the proof at every claim and across every reset, recorded in the qualification record and in each result's `ran_with` beside the proof's (R5.29) | **shipped** | 2.8.1 (PR #3220, closing #3206) |
| An owner's cancel: a cycle's cancel and a Campaign's abort stop the remote operations they own, a result that arrives after the cancel is kept as the late result and is no evidence, and nothing new is queued for a cancelled owner (R5.30) | **shipped** | 2.9 (PR #3256; #3236 tracks the MacBook lane's half) |
| A qualification names each tool whose definition changed: each tool's own digest in the record (schema `/3`), `tools_changed` beside the added and removed, the worker's refusal naming the tools that differ, and a comparison against an earlier record read as unavailable, never as no change (R5.31) | **shipped** | 2.9 (PR #3262, closing #3230) |
| A result the worker builds itself names what its run had established: the cancel's and a raise's `interrupted` carry the runner's `running_with()`, read before the reset (R5.34) | **shipped** | 2.9 (PR #3277; #3236 tracks the live cancel round on real Studio) |
| A play reads the place's non-script state twice, at its pin check and after play, the second held to the first; a place without a synced root its scripts go into is refused by name (R5.36) | **shipped** | 2.9 (PR #3290) |
| The checks that guard a person hold for every input play: R5.33's conditions read whether or not Studio is in front, the lock and session on any worker, the front read once, the activation by the proved process's id, the lease and window read again before the first input, the lock and counter during the play, the session entry by entry, `front.input` on every input play (R5.37) | **shipped** | 2.9 (PR #PRNUM, closing #3300) |
| A candidate's own setup failure, the core: a play's result names the script errors its provider read, the registry writes who served it, and six conditions read from the cycle's records attribute a setup failure to the candidate, which then gets one correction in the run; the reading is kept either way, and anything else keeps its routing, not executed (R5.32) | **shipped** | 2.9 (PR #3275) |
| A candidate's own setup failure, on Studio: the provider reads its console for script errors and names its environment (the MacBook lane; R5.32's Studio half) | **shipped** | 2.9 (PR #3288) |
| A candidate's own setup failure, played: the diagnostic goes from baseline to attributed failure to repair to the same frozen scenarios passing (R5.32; the certification window's case 9) | **placed** (the 2.9 plan, adopted 2026-11-26) | 2.9, #3200 |
| A dedicated worker brings Studio to the front: inside its declared window, after the idle threshold and a fresh read of human input, each activation and refusal recorded in `ran_with`, and anything uncertain a refusal (R5.33; the Spark lane wrote the rule and the MacBook lane built it) | **shipped** | 2.9 (PR #3269, closing #3193) |
| G-1: Godot integration works | **unplaced**, deliberately | — |
| U-1: Unity integration works: EditMode, PlayMode and player tests apart, results read per test, metadata kept, a worker matched by capability (R2.5); the check that the engine boundary generalizes | **unplaced**, deliberately: after Roblox | — |
| B-1: GameBench-01 on more than one engine, and governed publishing | **unplaced**, deliberately: later and optional, never a prerequisite for Roblox (R2.10) | — |

**What closes this SIP:** phases 2a–2e and R5.7's rows shipped (Roblox integration works), the 2.9 plan's rows
shipped, then G-1 and U-1 shipped or dropped by a numbered amendment. B-1 is optional. "The squad can build and improve a playable game" is the companion's to close
(R2.10).

---

# R5. Post-acceptance amendments

## R5.1 Phase 2a is delivered in two parts, and part 1 as built (2026-11-10)

**Ruled by the owner on 2026-11-10:** "approve R5.1 and build part 2 next", on the implementer's write-up in part 1's
PR (#3019).

**What changed.** R4.4 lists the type's correction mapping and verifier seams as part of phase 2a. Building it showed
the correction loop can't yet serve this type, so phase 2a is delivered in two parts and the ledger has a row for
each.

**The evidence** (the correction loop as it stands, read on 2026-11-10):
- a failed task's repair defaults to the dev repair, aimed at the failed task's own expected artifacts. For this type
  those are evidence files;
- the retest after a repair re-runs a test suite. Nothing re-runs an operation, so a repaired run would end on the
  original failed assertions or as a deadlock;
- a patch accepted from a failure is stored under the failed task's type, and delivery leaves out a producer that
  authors neither source nor a suite. The repaired source would be missing from the delivered change;
- no task outcome means "not executed: no repair, and don't stop the run".

**Part 1** builds everything the framework owns before correction, and holds the type out of the loop:
- **A failed assertion leaves the run `rejected`,** with the assertion, the observed value and the expected value
  named. No repair is attempted.
- **A failed task of this type ends the run** (`TaskType.fails_without_correction`), so nothing reaches a repair
  aimed at evidence.
- **Part 2** adds the route R4.4 describes. It changes the correction runner, patch acceptance and delivery. The 2.7
  changes to those files (#2932, #2949) are merged, so it can be built next.

**R4.4, as part 1 builds it:**

| R4.4's part | as built |
|---|---|
| the type | `TaskType.QA_RUN_REMOTE_OPERATION`, `plannable`, outside `base@1`. Its handler is registered for `qa` on every stack and offered to none |
| the handler | reads the contract, mode and supplying skillset from the task's inputs, which the plan step takes from the cycle's skillset record. It refuses when the deployment doesn't hold that skillset, when its digest isn't the recorded one, or when the skillset requests no single tool for the contract. **One tool per contract** is the operation it runs |
| the port | `squadops.ports.remote_execution.RemoteExecutionPort`, one method. It is an optional field of the agent's ports bundle, and no adapter binds it yet: the adapter, its factory and its configuration selector are phase 2b's. With no port bound, the operation is reported as not executed, with that reason |
| a result is checked before it's believed | a stale echo, a record for an assertion the scenario doesn't declare, two records for one assertion, or a non-completion with no reason credits nothing. Every declared assertion then reads not executed |
| expected artifacts | the handler's own: `operation_assertions.json` and the provider's evidence items. **A plan task of this type declares no `expected_artifacts`** (`validate_operation_tasks`), which also keeps it out of an increment's footprint check |
| `not_executed`, `interrupted`, and an assertion that didn't execute | each is a not-executed row marked as a criterion the run couldn't verify (SIP-0096's evidence-gap rule, #423). The run's verdict is `blocked_unverified`, and takes precedence over a failure |
| the scenario | required on the task's inputs as `operation_scenario` (its id, digest and declared assertions), and refused when absent. Nothing supplies it in a live cycle yet: phases 2e and 2f take it from the change request |
| the wire | the request carries the task's id as its identity and the result must echo it. #2932's dispatch identity (merged, `793bb7ba`) is the transport's: it rides in the message's metadata and isn't handed to a handler. Phase 2b's protocol adds the durable token R3.3 calls for |
| verifier seams | the table is in part 1's PR. No seam evaluates this task's criteria on a container's tree: its evidence comes from the provider |

## R5.2 Phase 2a, part 2 as built: the correction route (2026-11-10)

**Ruled by the owner on 2026-11-10, as written** ("approve all as recommended"). The owner had ruled the split and
asked for part 2 ("approve R5.1 and build part 2 next"); this records how it was built.

**What changed from R5.1.** Part 1 held the type out of the correction loop. Part 2 lets it in for one kind of
failure and builds the route R4.4 describes.

| R4.4's correction mapping | as built |
|---|---|
| an executed failure in the application routes to the dev repair | a failed assertion fails the task, and the loop runs. `repair_steps_for` holds an explicit row for the type: the dev repair, for every locus |
| `not_executed` and `interrupted` route to no repair | `TaskType.corrects_only_executed_failures`: a failure of this type with no executed failed row ends the run, named. That covers an operation that never ran, a supplier the deployment can't vouch for, and a provider that raised. A run whose assertions only didn't execute isn't a failed task at all: it succeeds with its unverified rows and reads `blocked_unverified` (R5.1) |
| where the repair is aimed | the plan's implementation: the source the plan's development tasks author, carried on the operation's envelope. It is narrowed to the files the analyzer named when those are files of the plan. It is never the operation's own artifacts, which are evidence. A plan that runs an operation and authors no source is refused (`validate_operation_tasks`) |
| a re-run after a repair is an operation | `CorrectionRunner.reexecute_operation` dispatches the same task type to the same role with the same contract, supplier and frozen scenario, on the candidate tree with the repair's files laid over it. The tree's revision id is cut from exactly that mapping. No model is called and no skill is loaded |
| what accepts the repair | the re-run alone. The operation's task carries no typed criterion, so nothing else could decide. **Every declared assertion must execute and pass.** A re-run that still fails, that leaves any assertion unexecuted, or that didn't run refuses the repair, and the next round is told which |
| the evidence | the re-run's assertion records and provider evidence replace the failed run's on acceptance (both artifact types join `EVIDENCE_ARTIFACT_TYPES`). The task's check rows are the re-run's |
| delivery | an accepted repair is re-stored as the failed task's own, as every accepted patch is. Delivery now takes source from a task that runs an operation, and leaves its evidence out by type |

**Two things the first reading of the correction loop got right, and one it got wrong** (R5.1's evidence list):
- the repair default would have been aimed at evidence, and nothing re-ran an operation: both are fixed above;
- delivery left the repaired source out: fixed above;
- **a later task's workspace does include the repaired source.** The workspace filter selects by artifact type as
  well as by producer, so a source file stored under the operation is read by the tasks after it. No change was
  needed, and the operation's evidence types are selected by neither rule.

**Not built, and why:**
- **Keeping a partial improvement.** A suite retest that clears some failures and breaks nothing is kept for the
  next round (#1522). An operation's re-run is refused unless it passes whole. Whether a partly better scenario run
  should be kept is a question for the first real provider's evidence.
- **The verifier's typed checks for the repaired files.** Where a cycle has an interface manifest, the criteria that
  own the repaired files are still evaluated on the patch before the re-run, as for any repair. An operation's own
  task adds none.

## R5.3 Phase 2b: three decisions, ruled before it is built (2026-11-10)

Phase 2b (R3.3: the port's transport, the worker registry and its migration, `/api/v1/workers`) touches three things
that are the owner's to decide. **Ruled by the owner on 2026-11-10, each as recommended** ("approve all as
recommended"):

| decision | ruling |
|---|---|
| editing `docker-compose.yml`, which CLAUDE.md reserves | **approved:** one selector literal for the remote-execution adapter on each service that loads the configuration, as the composition-root rule requires (R2). It merges with 2.8 |
| a new required `.env` key on every deploy | **approved,** with a value that means "no remote execution" shipped in `.env.example` and written by the bootstrap. A deploy that runs no worker, the Spark's included, needs that one line, at 2.8. The Spark session is told when the PR opens |
| the worker's service account (D3) | **approved:** a new client-credentials client in the realm exports, with one scope for the workers API, and its secret generated per deploy into `.env` as the agent client's is |

## R5.4 Phase 2b: the transport re-examined and kept, three parts, and part 1 as built (2026-11-10)

**Ruled by the owner on 2026-11-10:** "yes resume part 1", after the transport was re-examined at the owner's
question. **Not yet ruled:** the points of part 1 as built, in the table below. They are the implementer's, for the
owner's review in part 1's PR.

**The transport (R3.3), re-examined.** The owner asked why anything on the MacBook calls the runtime, having expected
the Spark to connect to the tool's host. The evidence, gathered the same day:
- **Roblox's documentation:** the Studio MCP server "runs as a local process on your machine and communicates with
  the AI client using `stdio` transport". It names no other transport.
- **The proxy** (`StudioMCP` 1.0.0, in the Studio application): its options are verbose logging, help, version and a
  stdio flag its own help calls a no-op. It has no option for an address or a port.
- **Observed with Studio open:** the proxy hosts a WebSocket on `127.0.0.1:13469`, and Studio connects to it. Studio
  listens on no port. The link is token-checked (the proxy's log: "WS authentication mode: Enforce"), with the token
  in a file only the signed-in user can read.
- **So Studio is reached from another machine in two ways only:** by carrying the proxy's stdio over a sign-in to its
  host, or by a process on its host that connects outward.
- **The owner's two constraints:** no remote sign-in on the MacBook ("I'm not crazy about opening this macbook to
  remote login even over tailnet"); and the PC is to become a Bazzite Linux machine. Studio has no Linux build. On
  Linux it runs only through Vinegar, a community project over Wine, which is reported to break for days after a
  Studio update and is unproven for Studio's MCP server.
- **The result:** the MacBook is the one supported Studio host, and it accepts no connection in. The worker connects
  outward, as R3.3 says, and the body's SSH transport stays replaced.

Two things recorded for later:
- **The worker runs on whichever machine hosts the tool.** If Vinegar proves sound on the Bazzite machine, the same
  worker serves it as a second host. That is a spike of its own, after the machine is installed.
- **The proxy's cache listed 33 tools,** and S1 recorded 38. Phase 2d counts again against a live `tools/list` before
  its allow-list is written.

**Three parts.** Phase 2b is delivered in three PRs, each provable alone, and the ledger has a row for each:
1. the runtime's side: the registry, the rules, the routes and the worker's identity;
2. the worker: its composition root, its claim loop and a fixture adapter;
3. the squad's side: the adapter behind the port, its selector, and how an agent's request reaches the queue. The
   agent's service account holds one scope today, so that last point needs the owner's ruling before it is built.

**R3.3, as part 1 builds it:**

| R3.3's part | as built |
|---|---|
| "assignment" | **named the operation and its attempt.** `assignment` is SIP-0089's (`agent_assignments`, `/api/v1/assignments`). R3.3's assignment id is the operation id |
| the registry | `squadops.remote_execution.registry.WorkerRegistry` applies the rules to rows behind `WorkerRegistryStorePort`, each call in one exclusive transaction. The rules are pure decisions in `squadops.remote_execution.leasing`. One contract suite runs over the memory store and over Postgres |
| where it is kept | chosen by `cycles.registry_provider`, as the scenario store and the campaign registry are. Part 1 adds no selector. The remote-execution selector R5.3 approved is part 3's |
| the migration | `2300_remote_execution.sql`, in the next free range (2300–2399) |
| "a durable token of its own" | **the lease is the operation's own row:** the operation, attempt, session and lease ids. A registry built after a restart accepts the held claim's heartbeat and its result |
| the fence | all four ids are the current ones and the lease has not run out. Otherwise the result is refused with one of seven named reasons, and the refusal is kept in `remote_operation_refusals` |
| a result after its lease ran out | **refused, even when no newer claim exists.** R3.3 says expiry frees the assignment. A worker that stopped renewing is one whose state the runtime can no longer vouch for. The cost is a second run when a result arrives just late |
| when expiry is seen | when the operation is next touched: a claim, a heartbeat, a result or a read. Part 1 has no background sweep |
| attempts | the requester sets how many. A lease that runs out with an attempt left queues the operation again, and the next claim advances the number. On the last attempt it settles as `interrupted`: a worker held it, so it may have started |
| cancel | a queued operation settles as `not_executed`. A claimed one is marked, and its worker sees that at its next heartbeat |
| a repeated submission | the same claim submitting the result it already had accepted is answered as accepted, and nothing is stored again |
| a worker that registers again | has restarted: its earlier session ends with the attempt it held, and its next claim is told to reconcile and reset first |
| health | the canonical vocabulary. A session silent for 45 seconds reads `offline`. The heartbeat interval (15 seconds) and the lease's length (60 seconds) are told to the worker when it registers |
| the routes | four, under `/api/v1/workers`: register a session, heartbeat, claim, submit a result. A refused result is a 409 carrying its reason |
| the worker's identity (R5.3) | the role `worker` and one scope, `workers:serve`, which no other role holds. The client `squadops-worker` is in all four realm exports **with no secret committed**; its per-deploy value is `SQUADOPS_WORKER_CLIENT_SECRET`, generated by the deploy |
| one identity for every worker | every worker signs in as that one client, so a session is not tied to its caller's identity. What protects a claim is its lease id. An identity per worker waits for a second worker |

**Not in part 1:** a route for a person to read the registry, a background sweep for expired leases, and anything
that queues an operation in a live cycle (part 3).

## R5.5 Phase 2b, part 2 as built: the worker (2026-11-10)

**Not yet ruled:** the points below are the implementer's, for the owner's review in part 2's PR. Part 2 changes no
ruling of R5.3 or R5.4.

**What part 2 is.** The worker is a process on the machine that hosts a tool. It registers, claims one operation,
runs it, renews its lease while it runs, and submits the result. It connects outward and listens on nothing.

| part | as built |
|---|---|
| the process | `python -m squadops.remote_execution.worker_main`, a fifth composition root. It reads its own section, `SQUADOPS__WORKER__*`, and never the platform configuration, as the sandbox service does: the worker's machine holds one secret, its own client's |
| its configuration | six fields, each required: the worker's id, the runtime API's address, the identity provider's token endpoint, the client's id and secret (a `secret://` reference is resolved; one with no secrets provider is refused), and `provider`, a `Literal` whose one value today is `fixture` |
| its two ports | `WorkerApiPort`, the runtime as the worker calls it, and `OperationRunnerPort`, the tool. The loop (`squadops.remote_execution.serving`) knows neither HTTP nor any tool |
| the way to the runtime | HTTP, with the worker client's token. Every answer is read strictly. A 404 is "no such session" only when it carries the route's own code, so a worker pointed at an address that isn't the runtime stops with what it received |
| three ways a call fails | *unreachable* (no answer, or a server failure): tried again. *Refused* (credentials, scope, a request the runtime can't read) and *unreadable* (an answer that isn't this version's document): the worker stops, exit code 1, with the reason |
| the fixture provider | one operation, `fixture/staged_files`. Each assertion names a path, and passes when the request stages a file with content there. Its evidence is a manifest of the staged paths and their digests. A staged `.fixture/hold_seconds` makes it wait, so a rehearsal sees a lease renewed and a cancel arrive. It drives no tool |

**What the worker does with each thing that can happen while it holds a claim:**

| what happens | what the worker does |
|---|---|
| the operation ends | submits the result. While the runtime can't be reached it submits again, renewing the lease, for one lease's length at most |
| a cancel, seen at a renewal | stops the tool, resets it, and submits `interrupted` (R3.3) |
| a renewal is refused | stops the tool and resets it. It submits nothing: the runtime would refuse it |
| the runtime can't be reached | the operation runs on and the renewal is tried at each interval, until the lease's last known expiry. Then it stops the tool and resets it |
| the runtime no longer knows the session | stops the tool, resets it, and registers again |
| the tool raises | submits `interrupted` with what it raised, and resets the tool |
| the worker is stopped | stops the tool and submits nothing |

**For the owner's review:**
1. **A stopped worker submits nothing.** The lease runs out and the operation is queued again while it has an
   attempt left. Submitting `interrupted` would settle it, and a restart of the worker would then cost the requester
   its operation.
2. **What the tool raises is `interrupted`, and it settles the operation.** It had started. The requester decides
   whether to ask again.
3. **The tool is reset after any ending but a returned result,** and once per ending: a reset made when the claim
   was lost is not made again when the next claim says "reconcile first". **A tool that can't be reset runs
   nothing.** The next operation is answered `not_executed` with why, and the reset is tried again at the claim
   after.
4. **A result is tried for one lease's length.** A worker whose submissions alone keep failing would otherwise hold
   its claim for ever.
5. **The worker asks for work every 3 seconds.** That number is the worker's. The heartbeat interval and the lease's
   length stay the runtime's, told at registration.
6. **The worker has no time limit of its own on an operation.** The requester cancels (part 3).

**Changed in part 1's files:** the two error codes a worker acts on are named once, in
`squadops.remote_execution.wire`, and the route uses them. The reading of one configuration section from the
environment, and of the secrets provider's selection, moved from the sandbox root to shared homes
(`squadops.config.env_section`, `squadops.bootstrap.secrets`), since the worker is their second user.

**Found while building it:** the worker read its own stop request as its tool's, and served on. A test holds it.

**Not in part 2:** running the worker as a service on its machine, the Studio provider (phase 2d), and anything that
queues an operation in a live cycle (part 3).

## R5.6 Phase 2b, part 3 as built: the squad's side (2026-11-11)

**Ruled by the owner on 2026-11-11, in two steps.**
- First: "approve part 3 as recommended", on the recommendation in R5.4's third part. An
  agent's request reaches the queue under the agent's own service identity, which gains one
  scope.
- Then: the 2.8 plan's decision 2 (`docs/plans/2-8-0-plan.md` §8, after its outside review),
  with "decision 2 governs" over the first ruling where the two differ (§11.2). An agent's
  calls are scoped to the send of its task the runtime is waiting on, one operation is queued
  per send, and a newer send stops the older sends' operations.

The plan proposed accepting points 1–5 and 8 below as built, and it was adopted when it merged
(#3051). Points 6 and 7 are answered by decision 2, as built below.

**What part 3 is.** The handler of `qa.run_remote_operation` runs in an agent, and the worker
that runs its operation is on another machine. Part 3 joins them: the handler's port now has an
adapter, the adapter queues the operation through the runtime API, and a deploy says with one
required setting whether it runs remote execution.

| part | as built |
|---|---|
| the scope | `operations:request`, held by the `agent` role alone. A scope is implied by a role (#270), so no realm export changes and no deploy re-imports a realm. A worker's role doesn't hold it, so a worker can't queue work for itself; no person's role does |
| the requester's routes | three, under `/api/v1/remote-operations`: **create** queues an operation (201), **read** returns it as it stands with its result once it has one, and **cancel** asks for it to stop |
| the request's send | the request names its task and the send of it: the dispatch id the runtime minted for that dispatch (#2932), which the agent's envelope carries. The handler executor puts it on the handler's context, and the handler sends it. A task that came in no named send asks for nothing and fails with the reason; the task id is never sent in its place |
| only the current send | every route answers only while the request's send is the one the runtime's reply router waits on for its task. Otherwise 403 `REMOTE_OPERATION_SEND_NOT_CURRENT`. One client identity serves all the squad's agents, so the send is what tells one requester from another. A send that isn't current would have its reply dropped as stale, so nothing is done under it |
| one operation per send | create is keyed on the task and the send, unique in Postgres (migration 2301). A send that asks again is answered 200 with the operation it asked for, whether or not a worker is heard from now. The same send asking with a different request is refused, 409 `REMOTE_OPERATION_SEND_CONFLICT`, and the first stands |
| a newer send | create stops every operation an older send of the task asked for that has no result yet: a queued one settles with the reason that it was superseded, and a claimed one is marked for its worker to stop. This holds when no worker can run the newer send's operation, and after a runtime restart, since it reads the stored operations |
| with no worker to run it | create queues nothing and answers 409 with the registry's reason: no registered worker serves the operation, or the ones that do are offline, named |
| who asked | the operation's origin is the agent's id, from the adapter, and `requested_by`, which the route writes from the identity the call was made under. The task and the send are the request's |
| the adapter | `RuntimeApiRemoteExecution`, behind `RemoteExecutionPort`. It queues the operation, reads it every 2 seconds until it has its result, and returns the result |
| the selector | `remote_execution.provider`, required, with no default: `none` or `runtime_api`. It is on the runtime API and all eight agents in `docker-compose.yml`, read from `.env` (R5.3), and `.env.example` ships `none` |
| `none` | binds no port. The handler reports the operation as not executed, saying no port is bound, as it did before part 3 |
| the agent's identity | its existing service client (#326), through one token client per process, shared with the heartbeats. With no identity configured the calls carry no token, as the heartbeats' do: a runtime that authenticates refuses them, and that is raised |
| two tunables | `remote_execution.wait_seconds` (900) and `remote_execution.max_attempts` (2), each with a default, as tunables have (the composition-root rules' R5) |

**How each thing that can happen to an operation is told to the handler.** The port's rule
stands: an operation that didn't run is `not_executed`, one that may have started and has no
result is `interrupted`, and neither is a pass or a failure.

| what happens | the result |
|---|---|
| no worker serves the operation, or none is being heard from | `not_executed`, with the registry's reason |
| the runtime gives no answer to the request to queue | the adapter asks again every 2 seconds, within the same wait. Asking again is safe: the runtime keeps one operation per send |
| the runtime gives no answer to any request to queue within the wait | `interrupted`: the operation may be queued, and whether it ran is unknown. The task's next send stops it |
| the send is no longer the task's current one, at any call | `interrupted`: the task was sent again, or the runtime restarted and waits on no send of it. Its reply would be dropped as stale, and an operation may be queued under the send. The task's next send stops it |
| the operation settles | its result, as the worker or the registry wrote it |
| no result within the wait | the adapter cancels. A queued operation settles `not_executed`. A claimed one's worker answers `interrupted`, or its lease runs out. Either happens within one lease's length, which every answer tells the adapter |
| still unsettled one lease after the cancel | `interrupted`, naming its state |
| a result that crosses the cancel | stands as it was submitted |
| the runtime is briefly unreachable during the wait | the adapter reads again, and names each read that got no answer |
| the runtime restarts during the wait | its reply router is new and waits on no send, so the next read is refused as not current: `interrupted`, as above. The operation and its lease are in Postgres (R5.4), and the resumed run's send of the task stops it (found in review by the Spark session) |
| the runtime can't be reached when the wait ends | `interrupted`: it was queued, and whether it ran is unknown |
| the runtime no longer knows the operation | `interrupted`, likewise |
| the runtime refuses the agent, or its answer can't be read | **raised.** The task fails with the reason and the run ends on it (R5.2: a failure with no executed failed row). A deploy's defect is never read as an operation that didn't run |

**Two rules of part 1 changed.** The registry's contract suite holds both over memory and
Postgres.
- **A claimed operation that is cancelled, and whose lease then runs out, settles as
  `interrupted`,** whatever attempts it had left. Part 1 queued it again while an attempt was
  left, still marked cancelled: no worker could claim it and nothing settled it. Part 1 had no
  requester to wait on it.
- **A queued operation whose earlier attempt's lease ran out settles as `interrupted` when it
  is stopped,** naming that attempt. Part 1 settled it `not_executed`, "cancelled before a
  worker claimed it", though the earlier attempt had begun in the tool and may have run there.
  A cancel and a supersession both reach this rule.

**The points reviewed with the plan (1–5 and 8 accepted as built; 6 and 7 answered by
decision 2):**
1. **`none` binds no port.** The alternative was an adapter that answers `not_executed`. The
   handler already names an unbound port, and a port that exists is one a later caller might
   trust.
2. **With no worker being heard from, nothing is queued.** A worker that registers a minute
   later is not waited for. The cycle reads `blocked_unverified` with the reason, and is run
   again.
3. **The wait is 900 seconds.** It must stay under the deploy's task timeout (1,800 seconds
   on both deploys), so a long operation ends with its own named ending and not as a hung
   agent. The first real provider's timings may move it.
4. **Two attempts.** The second is for a worker that restarted. A tool that fails the same
   way twice costs two runs.
5. **A refusal raises.** A scope the agent lacks, credentials the identity provider refuses,
   and an answer this version can't read each fail the task and end the run with the reason.
6. **Every agent signs in as the one agent client.** As first built, any agent could read or
   cancel any operation whose id it knew. **Now:** only the task's current send may, by the
   send the request names. An identity per agent still waits for a second reason, as an
   identity per worker does (R5.4).
7. **An agent that dies while it waits.** As first built, its operation was left to run, read
   by nobody. **Now:** the runtime sends the task again under a new send (a retry, or a
   resumed run), and that send's create stops the older operation. An agent stopped in order
   still asks for its operation to stop, and names it when that fails.
8. **The agent reads its operation every 2 seconds.** That number is the adapter's.

**Changed in parts 1 and 2's files:** the HTTP calls to the runtime API and the strict reading
of its answers moved from the worker's adapter to a shared module, since the requester's
adapter is their second user. The worker's adapter behaves as it did, and its tests pass
unchanged.

**What a deploy needs at 2.8.** One line in its `.env`:
`SQUADOPS__REMOTE_EXECUTION__PROVIDER=none`. Without it every compose command stops and names
the key. A fresh bootstrap copies it from `.env.example`. The MacBook's deploy sets
`runtime_api` when it runs a worker.

**Rows of the earlier shape.** The request now carries `task_id`, which it lacked. An operation
queued before this change has none: no send matches it, and reading its request raises. Only
rehearsal rows on the MacBook's deploy are of that shape, since no other deploy had the create
route.

**Not in part 3:**
- **A live cycle that queues an operation.** Nothing supplies a scenario yet (R5.1): phases 2e
  and 2f do.
- **The preflight at cycle creation** that a registered worker serves the plan's operations
  (R3.4). The create route's refusal says the same thing at dispatch.
- **A route for a person to read the registry, and a background sweep for expired leases.**
  An expired lease is ended when its operation is next read, and a waiting requester reads it
  every 2 seconds.
- **The worker as a service on its machine, and the Studio provider** (phase 2d).

## R5.7 The 2.8 plan's additions, adopted (2026-11-11)

**Ruled by the owner on 2026-11-11:**
- the 2.8 plan's nine decisions (`docs/plans/2-8-0-plan.md` §8), after an outside review of its revision 1: "good with your recommednation. go";
- its lanes and the order of the two rulings on the request path: "approve both lanes to spark, decision 2 governs";
- the Studio first slice: "confirm the studio first slice, merge 3051".

The plan was adopted by its merge (#3051).

**What changed, with the evidence for each:**

| addition | evidence | issue |
|---|---|---|
| **the frozen scenario is declarative.** Strategy declares actions, observations and expected values. The harness validates them against its own vocabulary and executes them, and nothing an assignment supplies runs as Luau. The game-dev-roblox plan's "the frozen scenario" among the harness's fixed programs (§2.6) reads as the harness's scenario executor over a validated declaration | the outside review's answer to question 8: freezing a file establishes its identity, not what it may do under the owner's Studio login. Revision 1 of the plan had called the scenario an authored Luau program | #3044 |
| **the baseline must execute and fail.** The named assertion executes and fails on the accepted baseline before development starts, and anything unread (no record, `setup_failed`, no worker) blocks the increment. The reader is frozen with the scenario | the outside review's answer to question 2. The existing pass-on-head check proceeds where it can't run (`execution/criterion_head_check.py:16-20`) | #3044 |
| **Campaign delivery reads scenario evidence.** A scenario criterion is accepted on evidence bound to the candidate's revision, and every earlier increment's scenario is replayed on the same candidate | the outside review's answer to question 7. Campaign acceptance runs criteria as files on the product's runner (`campaigns/runner_acceptance.py`), and nothing under `campaigns/` read an operation's evidence | #3053 |
| **an unavailable worker is waited for, within a budget.** `launch_blocked` before launch, and an availability-only gap relaunched within a budget persisted per logical increment, then escalated. The in-cycle wait, cancel and outcomes are R5.6's | the outside review's answer to question 4. `launch_blocked` counts attempts per episode, and an unblock ends the episode (`campaigns/launch_blocking.py`) | #3045 |
| **the machinery Campaign** proves the path with no model and no MacBook, through two increments and six injected faults, including a dropped create response and a superseded send | the outside review's answer to question 5; CLAUDE.md's wiring-test rule | #3050 |
| **the worker as a service, the operator's read surface, re-qualification after a Studio update, payload limits** | R5.4 and R5.5 left the first two out on purpose. A pin with no recorded way to move it blocks every run after a Studio update. The request carries the whole tree inline | #3046–#3049 |
| **the isolation test** (R4.6) is a committed design that no row carried. It ships with the Studio adapter | — | #3039 |
| **one credential per host before a second worker.** One worker credential is accepted for one trusted MacBook | the outside review's answer to question 8; R5.4 shares one client identity across workers | — (a condition, no work in 2.8) |
| **the Studio first slice,** an early read on the plan's Studio gate: read-only, `z_tower-ascension` only, nothing published, built after R5.6's changes | confirmed by the owner, 2026-11-11 | #3039 |

**R5.6's request path** is decision 2's: an agent's calls are scoped to its task's current send, there is one operation per send, and a newer send stops the older sends' operations. It is recorded in R5.6, as built in PR #3052.


## R5.8 The frozen scenario, part 1 as built: the declaration, its digest, the wire and the baseline rule (2026-11-11)

**Ruled:** the shape was posted on #3044 (2026-11-11) and agreed with the Spark lane, which builds Campaign
delivery against it (#3053). The owner's word was "go with your recommendations and merge as you need". #3044 is
built in two parts. This is part 1.

**What changed, with the evidence for each:**

| change | evidence |
|---|---|
| **A scenario is a declaration**, schema `squadops.scenario/1`: `reader`, `setup`, `steps`, `assertions` (each an observation in a context and an expectation) and `named_assertion`. A key outside the schema, or a kind or argument outside the reader's vocabulary, is refused with every defect named (`remote_execution.scenario`) | R5.7's first row: nothing an assignment supplies runs as code |
| **Core holds no vocabulary.** The validator takes a `ScenarioVocabulary` value, and a provider ships its own as data. The fixture's reader is `fixture/1`. `roblox-studio/1` ships with the development profile (#3041) and the Studio adapter (#3039) | R4.6's isolation test allows a platform's name only in the skillset directories, the development profile's entry, the squad profiles, the adapter directory and the worker root's configuration section. #3044's first post put the vocabulary beside the capability contracts, which that test refuses |
| **The digest** is `sha256:` over the declaration's canonical text (sorted keys, no whitespace, UTF-8, NaN refused, and a repeated key refused rather than kept). The text names the reader, the setup, the steps and the expected values, so one digest freezes all four, as R3.7 asks | — |
| **The request carries the declaration.** `Scenario` gains `named_assertion` and `document`, and the wire requires both. A provider digests the text it was handed and refuses a difference, another reader, or a declaration it can't read, as `not_executed` (`handed_scenario_defects`). The handler reads the text from the candidate tree at the path the scenario was placed, so an edit made to the file after freezing reads `not_executed` at the provider | #3044's done-when: "A scenario edited after freezing is refused by the provider as `not_executed`" |
| **The request's revision is that of exactly what it stages**: `staged_revision(source_files)`, with no executable bit, since the wire carries text only. The handler took the workspace's revision id until now, which on a baseline overlay names another tree | the Spark lane's review of #3044's shape, point 2, and its correction |
| **One reading shape.** `models.records_document` writes the assertion-records artifact for every lane: the `side` (`baseline` or `candidate`), the revision, the paths left out of staging (`not_staged`), the scenario with its digest, named assertion and text, and one record per declared assertion. The handler stages text files and names every other path there | the Spark lane's review: a pass on a tree without its binary files must be visible to whoever reads it. Whether a non-empty `not_staged` blocks credit is #3039's to decide |
| **The baseline rule is one function**, `baseline_verdict`. It judges in this order: a gap blocks; then a named assertion that passes is refused to its author; then a precondition that fails is refused; else development may start. Campaign acceptance (#3053) calls the same function | the Spark lane's review, point 1 |
| **An observation of an instance that isn't there executes.** It observes `absent`, a value of its own, and is compared like any other. Only a setup that isn't established reads `setup_failed` | without it, every feature not yet built would read not executed on the baseline, and block, instead of failing |
| **The fixture provider runs `fixture/declared_scenario`**, which reads a staged `.fixture/world.json`, in place of `fixture/staged_files`. Its hold for the lease rehearsal stays | every scenario is now a declaration, which `staged_files`' paths-as-assertions were not. Nothing outside the tests named it |

**Rows of the earlier shape.** A stored request without `named_assertion` and `document` raises when it is read
back, as R5.6 records for `task_id`. Only rehearsal rows are of that shape, all settled, on the MacBook's deploy and
the Spark's.

**Part 2, still to build:**
- the change request's scenario criterion (`Criterion.scenario`, `SurfaceKind.scenario`), validated when it is
  stored, and placed at `.squadops/scenarios/<criterion>.json`;
- `operation_scenario` at plan expansion, with one operation task per scenario criterion;
- the baseline step before development, which keeps its reading as a cycle artifact;
- the plan gate's view of each assertion's observation.


## R5.9 The frozen scenario, part 2: the vocabulary's source and the scenario criterion (2026-11-11)

**Ruled:** part 2's design was posted on #3044 (2026-11-11, comment 6806301917) after a survey of the seams, under
the owner's "go with your recommendations and merge as you need". Part 2 ships in several PRs, and this
section grows with them.

**What changed, with the evidence for each:**

| change | evidence |
|---|---|
| **The vocabulary a scenario is frozen against is the supplier's kept one.** It is a skill's `scenario_vocabulary.json` (SIP-0116 §17g), read from the cycle's kept copy for the skillset its record names as a remote operation's supplier. The runtime puts it on the proposal's input (`scenario_vocabulary`), and the rails read it from there. Two operation suppliers with different vocabularies are refused | R5.8 left the vocabulary's source to part 2. No development-profile or contract field can carry provider data, and R4.6 allows a platform's name in a skillset directory |
| **A scenario criterion** is `surface_kind: scenario`, with its declaration in `scenario`. Its surface is the path its named assertion observes, and its declaration's `scenario_id` is the criterion's id. It exists only on a repository-backed increment | the plan gate shows a reviewer the surface as the criterion's observed effect (R5.7's first row) |
| **Refusals.** A scenario criterion is refused as `scenario_unverifiable` when the cycle keeps no vocabulary. It is refused as `scenario_outside_vocabulary` when the reader can't run its declaration, when it names another criterion's id, or when its surface isn't its named assertion's path | — |
| **It is placed by the framework** at `.squadops/scenarios/criterion_<id>.json`. No runner places it, since none runs it. Its file is named for its criterion, as every placed criterion file is (§24cj). The load-time placement check refuses a scenario anywhere else, or anything else at that path | R5.8 named the file `<criterion>.json`. The placement rule names each criterion's file by its id |
| **One resolver names the operation a scenario runs under**: `capabilities.operation_supply.scenario_operation(record, catalog)`. It reads the one contract the cycle's record offers that runs an operation in `play` mode, with its supplier, and that supplier's one tool from the catalog, checked against the recorded digest. None or more than one is refused, never chosen between. Plan expansion's step, the baseline step, the handler and Campaign delivery each call it (#3067) | the Spark lane's review: three seams each resolving a scenario's tool could disagree about which provider runs it |
| **The declaration is the framework's file.** It is derived from the approved change request wherever it is needed (`placed_scenarios`), as page loaders are (#2799). It is laid over the squad's change at delivery (`placed_framework_files`), so the candidate Campaign acceptance reads holds it as frozen. It is left out of everything that holds a qa suite to a file: the planner's criterion index, the gate's criterion-file rule and the head check (`suite_criterion_files`). It is also left out of the footprint a planner is shown. A task that names it is refused at the plan gate (`validate_increment_scenario_files`) | a squad's copy would be discarded at delivery unread; a qa task held to writing it would block every plan |
| **Plan expansion appends one operation step per scenario criterion** (`task_plan.ScenarioOperationStep`), after the plan's body has built the candidate. It runs under the operation `scenario_operation` names, with the criterion's `operation_scenario` (its id, digest, declared assertions, named assertion, placed path and canonical text) and the plan's implementation surface for a repair. A request whose scenarios no supplier can run stops plan expansion by name | the planner model authors plan tasks, and nothing would make it write exactly one operation task per criterion |
| **The step's workspace holds the framework's declaration.** At dispatch, the operation's tree has the declaration laid in from its `operation_scenario` over whatever the vault holds at that path, and its revision is cut after that | the vault holds only the squad's files, and a squad's copy at that path is never the frozen one |
| **The baseline step** (`execution/scenario_baseline.py`) runs before an increment's implementation run dispatches anything, and a resumed run skips it. Each scenario its plan plays is read on the baseline-evaluator overlay delivery's acceptance judges (`baseline_scenario_overlay`, #3072). The read goes through the runtime's port under `acceptance_task_id(..., BASELINE)`, and the reading is kept as the cycle's `remote_operation_assertions` (side `baseline`) | R5.7's second row: the named assertion must execute and fail on the accepted baseline before development starts. One overlay for both lanes, so delivery can credit the reading (#3053) |
| **The step's endings** use what the Campaign already reads. `may_start` for every scenario dispatches development. A named assertion that already passes, or a failed precondition, ends the run `criteria_not_checkable`: the Campaign abandons the increment for a new proposal (row 19), so the scenario is refused to its author. Anything not read ends it `infrastructure_failed` with the reason, and it is retried until #3045's relaunch budget takes it over. A refusal outranks a gap. A pass isn't recorded as met | the owner's §24do ruling: a criterion passing where the work hasn't been done says it proved nothing about the work, never that the behaviour exists |
| **The reviewer's view.** A proposal whose request names scenarios also emits `scenario_review.md` (`change_request.scenario_review`): for each scenario criterion, its claim, its reader, setup and steps, and a table of each assertion's observation, context and expectation, with the named one marked. It is derived from the request and never stored in it, so the ruled document and its hash are unchanged | #3044: what a scenario observes is reviewed when the increment is ruled on. An observation must read the player-facing effect, and the stored YAML doesn't make that reviewable at a glance |

**Part 2 is complete with this row,** and #3044 closes. Every item of its done-when list is met: the wiring test at plan expansion (#3070), a pass on the baseline refused to its author and an unread baseline holding development (#3073), an edited scenario refused by the provider (#3058), and a scenario outside the vocabulary refused when frozen (#3066).

**For #3041.** A planner isn't offered a remote operation until the offered-contracts prompt asset exists
(SIP-0116 §17c). When #3041 writes that asset, it says that a scenario criterion's operation is the
framework's step, so a planner writes none.

Campaign acceptance's runner side is the Spark lane's (#3053).

**No proposal can carry a scenario criterion yet:** no skillset ships a vocabulary, so every one is refused as
unverifiable until those land.

## R5.10 An increment blocked only for want of a worker is retried, never repaired: #3045, part A as built (2026-11-15)

**What changed.** A delivery that can't read a scenario because no worker took its operation used to read
`blocked_unverified` like any other unread gap. The Campaign then repaired it (SIP-0109 §10 row 8), rebuilding a
candidate nothing had faulted and spending the increment's repairs on an outage. Now:

| Point | As built | Why |
|---|---|---|
| **Availability is a fact on the result, never prose.** `RemoteOperationResult.unavailable` means no worker took the operation. It is set only by a requester, from three structured facts: the registry's `NoWorker` (`RegistryRemoteExecution`); the route's `ERROR_NO_WORKER` (`RuntimeApiRemoteExecution`); and the requester's own wait, when its cancel settled an operation no worker had claimed (`waiting.await_result`). It is never set on a result a worker returned | the decision a hearing takes on it must not rest on a reason's words |
| **Left out on purpose: a worker that claimed the operation and went silent.** Its lease lapsing reads `interrupted`, whether it ran is unknown, and it isn't flagged. So it still goes to repair. It is an outage too, but a different fact, and the conservative choice is to leave it with the work's routing | the MacBook lane's review of the plan, point 2 |
| **Every reading's document carries the key** (`records_document`), so "not flagged" is read, not inferred. A reading kept before the key reads as not flagged (`reading_unavailable`), and keeps the routing it had then | the MacBook lane's review, point 1 |
| **Delivery records one fact for the hearing.** A scenario's `Discrimination` or `FrozenResult` is flagged when it is unread only because a side's reading was taken by no worker. The evaluation's `blocked_only_by_availability` is true when it is `blocked_unverified` and every gap that blocks it is so flagged. A missing bundle, a route not rendered, or a runner with no test-id reader beside the outage leaves it false. A failure beside the outage rejects, as before | the shortcut is taken only when building again can change nothing |
| **The hearing retries it** (`EndedCycle.blocked_only_by_availability`, read from the stored evaluation; absent reads false). It takes rows 10 and 11, the rows of a run that failed outside the work: a retry while `max_retry_cycles_per_increment` lasts, then escalation. The retries are counted on the increment across its launches (`derive_counters`), so nothing resets them | #3045's budget, persisted per logical increment. SIP-0109 §10's rows are unchanged; the input that reaches rows 10 and 11 is widened |
| **At dispatch nothing changes.** #3036's `worker_unavailable` ends the run `infrastructure_failed`, which reads as the environment, so rows 10 and 11 already apply. So does the baseline step's blocked ending | |

**The evidence.** `test_machinery_campaign`: a worker that is there at every launch and gone at every reading. The
Campaign takes rows 5, 10 and 11, launches an increment and one retry, no repair, and escalates. Both evaluations
read `blocked_only_by_availability`. Making the hearing ignore the flag, or the requester not set it, fails that
test. The decisions on mixed gaps are `test_retry_for_want_of_a_worker`.

**Who ruled it.** The shape was agreed with the MacBook lane on 2026-11-12 (relaunch only when every gap is
availability, never read from prose). It was reviewed again on 2026-11-15, with the three points above.

**What remained for #3045 (part B)** is R5.12.

## R5.11 The Studio first slice as built: the adapter's read side, and the isolation test (2026-11-14)

The 2.8 plan §5 confirmed the first slice: read-only, on `z_tower-ascension` only, with nothing published, as an early
read on the Studio gate. Its scope was posted on #3039 before the build.

**What Studio 0.747 showed (read on `ta-copy.rbxl`, 2026-11-14):**
- **The live `tools/list` has 38 tools,** as S1 recorded. 18 are marked read-only. `http_get` and `search_asset` are
  among them, and both reach outside Studio, so the allow-list is named, never derived from the marks.
- **`search_game_tree` stops three levels down by default** and summarizes the rest (`unexploredChildCount`).
- **`inspect_instance` answers a miss as a success** (`isError: false`, text `Error: …`).
- **`PlaceId` is out of the read-only tools' reach:** the DataModel can't be inspected through them.
- **`script_read` returns the source exactly:** its numbered lines, rejoined with newlines, are the file byte for
  byte. A range past the end carries a note giving the length, and a range starting past it is an error.

**As built** (`adapters/remote_execution/game_dev_roblox_studio/`):

| R3.6 / §2.6 says | the first slice |
|---|---|
| a deadline on every call | every JSON-RPC call to `StudioMCP` has one, and the adapter starts that program itself |
| deny-by-default tools, counted against a live `tools/list` | the allow-list is `list_roblox_studios`, `get_studio_state`, `search_game_tree`, `script_read` and `get_console_output`. Each must be offered and marked read-only, and any other tool is refused before it is sent. An answer that is an error, however it is marked, raises |
| exactly one connected Studio, `PlaceId` 0, its baseline digest matching the pin | **narrowed for reading:** exactly one Studio, in Edit mode, holding a place never saved to the cloud (`persistedToCloud: false`). `PlaceId` 0 and the baseline digest take `execute_luau`, which is the harness's (#3040) |
| paged read-back of the three folders, pages under 90,000 characters, a truncated page refused | every script in `ServerScriptService.Server`, `ReplicatedStorage.Shared` and `StarterPlayer.StarterPlayerScripts.Client`. A tree read with anything unexplored, or that fills its limit, is refused. Pages are read in line ranges; one that reaches 90,000 characters is read again in halves, and a single line that does is refused. The comparison with a manifest names each missing, extra, re-classed or changed script, and each file under a synced folder the provider doesn't place |
| the worker registers its provider version, its Studio version and its tool-schema digest | `tool_versions`: `roblox-studio` 1, Studio's version from the app bundle `StudioMCP` sits in, and `studio_tools` as the count and the schema digest |
| the four operations | **none is served yet.** Each is served once it is proved on the worker (§R2.4), so `run` answers `not_executed` and says so |

**The suffixes are the product's.** `z_tower-ascension` writes `.server.luau` for a Script, `.local.luau` for a
LocalScript and `.luau` for a ModuleScript. A file with any other suffix under a synced folder is named, not placed.

**The worker's configuration waits for the first served operation.** The registry refuses a worker that serves
nothing (`leasing.registration_errors`), so `provider: roblox-studio` is added to `WorkerConfig` and the factory with
the first operation. Until then the read side runs from `scripts/dev/studio_read_back.py`. The factory's line will be
the composition point, which R4.6's list doesn't name; that addition is recorded when it lands.

**The isolation test** (`tests/unit/architecture/test_platform_isolation.py`):
- **The names it confines** are `roblox` and `studiomcp`, in any case, across `src/`, `adapters/` and `config/`.
  `luau` is a language, so it isn't one of them.
- **They may appear only in R4.6's five places,** each named in the test with its reason. Three existing mentions
  were prose examples, and were rephrased neutrally.
- **The adapter's imports:** beyond the standard library and itself, it may import only:
  - its port (`squadops.ports.remote_execution`);
  - the types the port speaks: `squadops.remote_execution.models`, `squadops.remote_execution.workers` and
    `squadops.runtime.models`.

  That is R4.6's first draft of a capability pack provider's interface.

**The early read:** on the MacBook, against `ta-copy.rbxl`.
- Identity held, and Studio 0.747.0.7471481 registered with 38 tools.
- All 137 scripts read back in about 5 seconds, and match `z_tower-ascension`'s `src/` byte for byte.
- A manifest changed five ways had each change named.

**Left for the adapter's next parts:** the transaction under one lease; sync writes; play and capture; the baseline
digest; reset from the read-only file, and reopening Studio; `PlaceId` through the harness; serving the four
operations; the worker's configuration; and whether a non-empty `not_staged` blocks credit (R5.8).

**Who ruled.** The owner confirmed the slice (2026-11-11). Its as-built narrowing is the MacBook lane's, under the
owner's "go with your recommendations" (2026-11-12).

## R5.12 A launch refused only for want of a worker waits in `launch_blocked`: #3045, part B as built (2026-11-15)

**What changed.** A Campaign's launch whose cycle the create path refused because no worker could run a tool its
work requires escalated at once, like any other create refusal (SIP-0109 §24e item 5, #1971). That refusal is the
one a create can outgrow: the MacBook sleeps, and wakes. Now it waits, as a busy box does, and escalates only at the
policy's count:

| Point | As built | Why |
|---|---|---|
| **The refusal is read from codes, never the message.** `PreflightRejectedError` carries its blocking findings' codes (`codes`). The launch reads a refusal as availability-only when every code is `skillset_availability` (`AVAILABILITY_REFUSAL`, single-sourced beside the finding kinds in `skillset_coverage`). It raises `LaunchUnavailable`, a `LaunchRefused`. Any other code beside it keeps the immediate escalation | the same rule as R5.10: the decision rests on a structured fact |
| **The campaign waits in `launch_blocked`** with the intent pending. The row is the box's row shape, with refusal `worker_unavailable` (`LaunchRefusal.WORKER_UNAVAILABLE`), and its reason names the create path and the tool. The sweep's due attempt unblocks it, and the drain creates the cycle again, which reads the worker afresh through the create path's own availability check | no second reading of the registry beside the one creation already makes |
| **Its attempts are counted on the launch, not the episode** (`launch_blocking.unavailable_launch`). Each attempt unblocks the campaign before the create that refuses it, which ends the box's episode, so an episode's count would restart at every attempt and never escalate. So every such row for the launch since the owner last resumed counts. The attempt that reaches `launch_blocked_attempts` escalates, and the owner's resume starts the count afresh | the issue's own warning: a count an unblock resets never escalates |

The plan said each retry would re-read the worker through `no_worker_for`. As built, the create path's availability
check (#3036) is that read, made at each attempt's create, so the launcher reads no registry of its own.

**The evidence.** `test_machinery_campaign`, entered at the calibration record and the runtime's sweep
(`CampaignLaunchService.retry_blocked`):
- **A worker offline throughout:** attempts 1 and 2 wait in `launch_blocked`, attempt 3 escalates, and no cycle is
  created, nothing is dispatched, and no `launch_refused` row is written. After the owner's resume, the next attempt
  is 1 again.
- **A worker that comes back during the wait:** the next attempt creates the cycle, and the increment is accepted.

**These mutations fail those tests:** the launch escalating at once; the attempts counted per episode; the resume
not resetting the count.

**#3045 closes with this part.** Its done-when: a worker offline at launch waits in `launch_blocked` and escalates
with no increment spent (here). An operation no worker claims within its limit ends `not_executed`, and one
interrupted after play began ends `interrupted` (R5.6, with R5.10's flag). A worker there at every launch and gone
at every reading spends the retries and escalates (R5.10). No other gap is relaunched by this rule (R5.10).

## R5.13 Phase 2c as built: the `luau` runner and the Luau runner contract (#2906, 2026-11-15)

**What it is.** A Roblox game's headless Luau tests are run by a runner script in the product's own tree,
under Lune, Zune or Lute: `lune run tests/run.luau`. Run with one spec file's path after the script, it runs
that file alone. The derived profile reads such a check as a `luau` runner (contract 8, SIP-0112 H.31). Its
output is read by the `luau` findings reader, which reads **the Luau runner contract** below, so any Luau
product can conform.

**The runner and its loader are the product's,** not a skillset's. A skillset's files are shown to the model
(SIP-0116 §17f point 4), and the check must run the same with or without SquadOps. `z_tower-ascension` is synced
by Roblox's Script Sync, not Rojo, with `src/Server`, `src/Shared` and `src/Client` and the suffixes
`.server.luau`, `.local.luau` and `.luau`. #3042 adds its `tests/run.luau` and the instance-tree loader that maps
those folders for `require(script.Parent.X)`. #3041's `test-loader` skill teaches the squad to write tests
against that runner, as text. This replaces R4's table row that put the test loader in the skillset.

**The contract**, one line each, matched on the whole line:

| Line | Means | Read as |
|---|---|---|
| `PASS <file> > <name>` | the test ran and passed | counted. The summary's `passed` must equal the number of these lines |
| `FAIL <file> > <name> [assertion] <message>` | the test's own assert failed | key `FAILED <file> > <name>`, class `assertion`: the test's own failure |
| `FAIL <file> > <name> [error] <message>` | the test ran and something raised, the product's own code included | key `FAILED <file> > <name>`, class `error`: the test's own failure |
| `FAIL <file> > <name> [setup] <message>` | loading what it tests failed: a require of the module under test, or a before hook | key `ERROR <file> > <name>`, class `setup`, a setup class: it never discriminates |
| `FAIL <file> [setup] <message>` | the spec file itself failed to load | key `ERROR <file>`. None of its tests prints `PASS` |
| `Tests: <p> passed, <f> failed, <e> errored, <s> setup, <t> total` | the summary, exactly one | `collected` = t, `passed` = p |

- **Readable** at exit 0 and 1 when:
  - the `PASS` lines and the `[assertion]`, `[error]` and `[setup]` lines equal p, f, e and s;
  - p + f + e + s = t;
  - the exit is 1 exactly when something failed.
- **Anything else is unreadable, never clean.**
- **A line the contract doesn't name is left unread.** A test mustn't print a line shaped like one of these.
- **How a loader tells the three tags apart:** its `require` shim `pcall`s each module load and rethrows a
  failure as `error({kind = "setup", …})`, as do a spec file's own load and any before hook. The assert helper
  raises `{kind = "assertion", …}`. The runner `pcall`s each test: a table with a `kind` keeps it, and a string
  error is `error`. Luau keeps an error table intact through `pcall`, under Lune too.
- **`[error]` is the test's own failure,** as a non-setup exception is for pytest. A regression that makes the
  product's code raise must discriminate, so only `[setup]` is a setup class (`SETUP_CLASSES["luau"]`).

**What a `PASS` line does and doesn't give.** It makes the passed count honest: a summary whose passes no lines
name is unreadable. It doesn't make acceptance credit a pass by its id. As for pytest and vitest, a reading keeps
its failures by key and its counts, a criterion's test that fails on the baseline is credited on the candidate
by its absence from the candidate's failures, and `ran_every_test` requires the candidate's passes and failures
to cover every test it collected.

**frktest** names neither a failure's kind nor a passing test. So a project that declares it, in `pesde.toml`,
`wally.toml` or `.luaurc`, gets no reader. Its `no_test_id_reader` gap is disclosed, closed by a runner script
that prints this contract.

**Not built:** `lute check` and `lute lint` as a lint check with a findings reader (#2906's optional item 4).
Nothing reads engine behaviour headless. That stays with the worker (R3.6).

**Who ruled.** The contract was agreed between the lanes on 2026-11-15. The Spark lane proposed two tags. The
MacBook lane added `setup` as the third, so product code raising still discriminates, and required the `PASS`
lines. The placement is the 2.8 plan's decision 4.


## R5.14 In the first milestone an operation is the framework's step, and the plan gate refuses a planned one (2026-11-15)

**What changed.** `ImplementationPlan.validate_operation_tasks` refuses every plan task whose type runs an operation,
naming it: "runs an operation, which is the framework's step in this milestone: plan expansion appends one for each
scenario criterion, with its frozen scenario (SIP-0117 R5.9). Plan none". Both plan-gate seams already call it. It
replaces R4.4's two checks on a planned operation: no expected artifacts, and some task authoring source.

**Evidence.** R5.9 made a scenario criterion's operation the framework's step: plan expansion appends it with the
frozen scenario it plays. R4.3 says `sync_source`, `read_console` and `capture` aren't planned on their own in the
first milestone. A planned operation would reach dispatch with no scenario to play. Nothing planned one: the Spark
lane's harnesses use only the appended step (its reply, 2026-11-15). And no planner is shown an operation, since
SIP-0116 §17k re-places the offered-contracts fragment.

**When it changes again:** with the first milestone that plans an operation, together with the fragment that teaches
a planner its shape.

**Who ruled.** The MacBook lane, with the Spark lane's agreement (2026-11-15), under the owner's "go with your
recommendations" (2026-11-12).


## R5.15 Phase 2d, the sync as built: the harness's fixed programs, and the adapter's own sync (#3039, 2026-11-15)

**The harness's programs are files,** `adapters/remote_execution/game_dev_roblox_studio/harness/*.luau`, each named
by its digest (`harness.digests()`). D5 holds: `execute_luau` is never on the session's allow-list, and a session
opened for the harness reaches it only through `run_program`, which sends one of those files in the Edit datamodel.
- **Input is data, never code.** A program that takes input holds one `{{PAYLOAD}}` token. A call puts its input
  there as hex-encoded JSON, so the code sent is the file's text with only `0-9a-f` where the token was. A source
  file holding `]]`, a quote or Luau is written as text.
- **`identity`** reads `PlaceId`, `GameId`, Edit and running. R5.11 left `PlaceId` 0 to the harness, and this is
  it: a sync refuses before writing unless `PlaceId` and `GameId` are 0, Studio is in Edit, and no play is running.
- **`sync`** writes scripts with their classes and removes scripts. A script whose class changed becomes a new
  instance of the new class and keeps its children. A missing folder is made.

**The adapter's sync** (`place.sync`, `RobloxStudioRunner.sync`, D10):
- **What it writes:** only what differs from a read of the place: a missing script, changed text, or a changed class.
- **What it removes:** every script in the three folders the manifest doesn't hold.
- **Ordering:** writes go parents first and removes children first, in calls of at most 200,000 bytes of source.
- **Refused before anything is written:**
  - a manifest that drops a script it keeps a script inside;
  - a file under a synced folder the provider can't place;
  - a place that isn't a local one in Edit.
- **Confirmed by reading the place back whole.** A sync is done only when the read-back matches the manifest, and
  any difference is named. The program's own count is checked, and never taken as the confirmation.
- **Script Sync's `X/init.luau`** is the script `X`, and the other files in `X/` are its children. R5.11's mapping
  placed it as a script named `init` inside a folder `X`, where the game's `require(script.Parent.X)` would find a
  Folder. `X.luau` beside `X/init.luau` is two scripts with one name, and is refused.

**Evidence on the real place** (Studio 0.747, `ta-copy.rbxl`, `scripts/dev/studio_sync.py --round-trip`):
- **Identity** read `PlaceId` 0 and `GameId` 0, in Edit.
- **A changed tree** was synced in 12.0 s: one Shared module edited, one added (with `é`, `]]` and backslashes in its
  text), and one client module removed. It wrote 2, removed 1, and matched on read-back.
- **The repository's own `src/`** was synced back in 12.9 s, and `studio_read_back.py` then read 137 scripts with 0
  differences.

Nothing was saved and nothing was published.

**Not served yet.** `serves()` is still empty: `sync_source` is served once it is proved on the worker, a Studio
restart included (R2.4). The transaction, the non-script baseline, reset and reopening Studio, and play are #3039's
rest. The owner approved writing into the local `ta-copy.rbxl` on 2026-11-15.

**Who ruled.** The MacBook lane, under the owner's "go with your recommendations" (2026-11-12) and their approval of
writes to the local copy (2026-11-15).

## R5.16 Phase 2d, the place's state as built: the baseline, the script marks and the frame around play (#3039, 2026-11-15)

**The non-script baseline is the harness's `baseline` program.** It reads only.
- **The lines:** it walks the place's services and writes one line per instance: its path, its class, its attributes,
  its CollectionService tags, and the properties a stated set names for the classes it is. Examples are a part's
  `CFrame`, `Size` and `Material`; a light's `Brightness`; a joint's `Part0` and `Part1` as paths; a `ValueBase`'s
  `Value`; a GUI object's layout; and a sound's id. Numbers are written to nine significant digits.
- **Exclusions,** each for its reason:
  - Scripts outside the three synced folders carry their whole source.
  - The synced folders' contents are left to the script read-back, which covers them whole.
  - Camera instances are left out, because Studio moves the camera with the viewport.
  - Terrain's voxels are left out, because no property reads them.
- **Pages:** the lines are sorted, kept in `_G` under a snapshot id, and paged back in pages of at most 40,000
  characters. The worker digests them. A total that moves between pages, or a page that doesn't advance, is
  refused. The snapshot is released however the read ends.
- **`baseline_changes`** names each instance that appeared, went or changed, with each changed field's old and new
  value. "The place changed" alone isn't enough to act on.

**The script marks are the harness's `script_marks` program.** It names every script in the three synced folders
that carries attributes or tags. This is #3042's eligibility rule, placed at the worker: Script Sync's files can't
carry either, so the tree read at creation can't show them (SIP-0118 R5.3).

**Play:**
- `start_stop_play` is a control tool, not marked read-only. So it is named in the session's `CONTROL_TOOLS` and
  allowed only to a session opened for the harness. A harness session requires both it and `execute_luau` offered.
- Each start and stop waits, under a deadline, until Studio reports Play or Edit.

**`RobloxStudioRunner.play_round`** is the frame `play_scenario` will run inside:
1. Confirm an unpublished local place in Edit.
2. Refuse marked scripts before play.
3. Take the baseline.
4. Start play, then stop it.
5. Take the baseline again.
6. Refuse any change, naming it.

**Evidence on the real place** (Studio 0.747, `ta-copy.rbxl`):
- **Stable:** the baseline read 22,852 instances (S1 counted 22,840) and 10.5 million characters, in 266 pages of
  about 19 s. Two reads gave the same digest, and no property was unreadable.
- **Sensitive:** a scratch program moved `Workspace/Baseplate` by 0.01 studs. The comparison named that one instance
  and its `CFrame`. Moving it back restored the original baseline exactly.
- **A whole round held:** `scripts/dev/studio_play_round.py` started play (about 4 s), stopped it, and held 22,852
  instances with one digest before and after. It took 42.8 s.

Nothing was saved and nothing was published.

**Still #3039's:**
- the transaction under one lease;
- reset from `ta-copy.pristine.rbxl` with Studio reopened and no person involved;
- the four operations served, once each is proved across a Studio restart;
- editor edits returned as a revision;
- the worker's configuration, with its provider found the way the runtime finds `eligibility.AUTHORITY` (R4.6).

**Who ruled.** The MacBook lane, under the owner's "go ahead with #3039" (2026-11-15) and their approval of writes to
the local copy.

## R5.17 Phase 2d, the reset as built: the place restored, and Studio reopened with no person involved (#3039, 2026-11-15)

**`RobloxStudioRunner.reset()`** answers R3.6's open item: "reopening Studio on that file without a person is phase
2d's to prove". The worker is configured with `PlaceFiles`:
- the place file Studio opens;
- the read-only baseline file;
- the baseline file's pinned sha256;
- the pinned non-script baseline digest (R5.16) the reopened place must hold.

**The steps, each refusing when it can't be done safely:**
1. **The baseline file must match its pin,** or nothing is touched.
2. **Only its own Studio is quit.** That means exactly one Studio process, whose MCP server reports exactly the place
   file. More than one, a Studio holding another file, or one whose server doesn't answer is refused, and a person is
   needed. A Studio showing a save prompt ignores a quit, so the reset asks first and kills only when it won't go.
3. **Studio's lock is removed only when the process it names is gone.** A lock held by a running process, or one
   naming no process, is refused, since opening the place twice would let one save overwrite the other.
4. **The baseline is copied in whole:** staged, made writable for Studio, and renamed into place, then checked against
   its pin.
5. **Studio is reopened** (`open -a`). The reopened place must come back as the place file, as an unpublished local
   place in Edit, holding the pinned non-script baseline.

**A runner given no place files refuses to reset.** The first slice's reset only confirmed identity, a no-op the
worker would have read as a place ready for the next transaction.

**`StudioApp`** is what the reset asks of the Mac: process ids, liveness, quit or kill, and open. `MacStudioApp`
(`pgrep -x`, a signal, `open -a`) is the real one, and a test stands in for it. The module is `studio_app.py`, marked
`# Platform: dev-mac`.

**Found live, and fixed:** `StudioMCP` lists no Studio for its first seconds. A reset that read the first answer
refused to quit the Studio it was resetting. `place.connected_studios` now polls, as `identity` did, and both use it.

**Evidence on the real place** (Studio 0.747, with the owner's approval of 2026-11-15):
- **The first live reset was done by hand:** SIGTERM was ignored, so it took SIGKILL. A stale lock was removed, the
  pristine file copied in and Studio reopened. MCP saw the place in Edit within 2 s under a new Studio id, and no
  dialog appeared.
- **The adapter's reset:**
  - **Setup:** the Baseplate was first moved 0.01 studs, so the baseline read `3ccc8c0f…`.
  - **The run:** `scripts/dev/studio_reset.py` quit Studio, restored the file and reopened it, holding the pinned
    `354636ad…`, in 27.0 s.
- **On the restarted Studio:**
  - the tool list was unchanged (38 tools, schema digest `1ba499d8…`);
  - a read-back gave 0 differences against `src/`;
  - a sync round trip wrote 2 and removed 1, then restored them;
  - a play round held 22,852 instances.

The place file overwritten by the first reset was kept: it was last saved during S1, and its sha256 is `afebe669…`.

**Still #3039's:**
- the transaction under one lease;
- the four operations served, each with its worker configuration. The provider will be found the way the runtime finds
  `eligibility.AUTHORITY` (R4.6);
- editor edits returned as a revision.

`play_scenario` serves once #3040's harness executes a scenario.

**Who ruled.** The owner approved the force-quit and reopening on 2026-11-15 ("Yes, now"). The design is the
MacBook lane's, under "go ahead with #3039".

## R5.18 Phase 2e as built: the scenario executor, its records, and Studio in front (#3040, 2026-11-15)

**`RobloxStudioRunner.run` serves `roblox-studio/play_scenario`** as one transaction:
1. the handed scenario checked against its frozen digest and the `roblox-studio/1` vocabulary;
2. every candidate file checked as one the adapter places;
3. Studio checked as the app in front;
4. identity, sync and the script-marks check;
5. the non-script baseline;
6. play started, then the scenario's setup, steps and assertions;
7. play stopped in a `finally`;
8. the baseline read again.

Anything before play ends `not_executed` with its reason, and so does a place whose non-script state moved through
play. A session that fails after play began ends `interrupted`.

**Where R3.7 is narrowed or changed, with the evidence:**

| R3.7 says | As built | Evidence |
|---|---|---|
| the harness emits one structured record per assertion, and S1 showed the console as its channel | **The channel is the `observe` program's answer, never the console.** Each observation runs the fixed `observe` program (R5.15's mechanism, with a hex payload) in the context's datamodel, Server or Client. It answers exactly one of `value`, `absent`, `unsupported`, `unreadable` or `wrong_context`. The adapter builds the record from that answer. Console text is kept as evidence and never read for an outcome, so a line from an earlier session can't be read either | a value returned by a call can't be confused with another session's line. Printing and parsing console lines would add a channel and a nonce for nothing |
| each record carries the play-session id and the source revision | **Each record carries its assertion id, outcome, observed and expected values, and context.** The play-session id (a fresh one per transaction) and the source revision are on the result's `ran_with` and in `play_log.json`, once per run | one transaction is one session and one revision |
| the execution context: server or client, and which client | **One client:** `@player` names the session's one player, `LocalPlayer` on the client and the only player on the server. More than one player reads `missing` | Studio's play session has one client |
| `wrong_context` | **The program checks `RunService` against the context it was sent for.** No correct declaration produces `wrong_context`, since the adapter maps each context to its datamodel. It is the guard against that mapping going wrong | produced live by swapping the two datamodels on the real path (below) |
| a game with a title screen passes it in every scenario's setup | **The scenario's author declares it,** with `wait_until` and `click_gui`, and the reviewer sees it in `scenario_review.md` (R5.9). A setup that can't pass it makes every assertion read `setup_failed`. The executor doesn't require it of a scenario, since a game with no title screen has none | z_tower-ascension's scenarios pass `TA_Title` this way |
| — | **The vocabulary as executed:** `click_gui` moves the mouse to the object and presses and releases it, in one call, after checking that the object is shown. `hold_key` holds a key down for its seconds. `move_to` navigates and waits until the character is within 1 stud. `wait_until` polls. A setup that can't be done, or a setup `wait_until` that isn't met, makes every assertion `setup_failed`. A step that can't be done does too. A step's `wait_until` that isn't met doesn't stop the scenario | Studio's one-step click never answered. A hidden button takes a click and does nothing, which would read as done |
| — | **Studio must be the app in front.** A scenario with any input action (`click_gui`, `hold_key`, `move_to`) is refused before anything syncs unless a Studio process is in front (`StudioApp.frontmost`, `lsappinfo` on the Mac). The refusal also covers no app in front, and a front that can't be read | **found live:** with Terminal in front, the click hung three times at 60 s. With Studio clicked to the front, it passed at once, twice running. Keys and navigation answered with Studio behind, and whether they took effect wasn't established, so they're held to the same rule |
| — | **The session player's account name is never returned.** It is read once per run and replaced by `@player` in every record and in the evidence. When it can't be read, the run ends `interrupted` with no records and no evidence | whoever is signed in to Studio is the player, and the console names them. The evidence goes into Releases |

**Evidence on the real game.** Studio 0.747, `z_tower-ascension` at `0beaac09`, Studio in front, about 55 s per run
(`scripts/dev/studio_play_scenario.py`):
- **passed:** the title gone, Energy 50 on the server and the HUD shown on the client all passed, on two separate runs.
- **failed:** the same scenario expecting Energy 49 failed only that assertion, observing 50.
- **missing:** an assertion on `Nowhere.Thing`, a path that starts at no service.
- **unsupported_input:** an assertion on `Player.NoSuchProperty`.
- **setup_failed:** a click on a button that isn't there made all three assertions `setup_failed`, and the log names
  the setup action.
- **wrong_context:** every assertion, with the two datamodels swapped after setup on the real path.
- **refused before play:** a `teleport` action was refused as outside `roblox-studio/1`, and Studio wasn't touched.

No run printed the player's name. Each one left the place's non-script baseline unchanged.

**Still to do:**
- **R5.9's vocabulary source:** the vocabulary file ships as a skill's `scenario_vocabulary.json` in #3041's QA
  skillset (#3105), held equal to the adapter's;
- **#3039:** the worker's configuration, the provider found by discovery, and the run on the Mac's worker, where
  Studio in front is part of the run window (#3046).

**Who ruled.** The MacBook lane built it under the owner's "go ahead with #3040" (2026-11-15). The owner brought Studio
to the front for the live check.

## R5.19 Phase 2d, the worker's side as built: settings, discovery, the proved-on pins and one operation (#3039, 2026-11-15)

**The worker creates the `roblox-studio` runner from its own section.** `WorkerConfig` takes `provider:
roblox-studio` and the provider's seven settings, `SQUADOPS__WORKER__ROBLOX_STUDIO_*`:
- `MCP`, `PLACE_FILE` and `BASELINE_FILE`;
- `BASELINE_SHA256` and `BASELINE_DIGEST` (R5.17's pins);
- `PROVED_VERSION` and `PROVED_TOOLS`.

Each is required for that provider and refused for any other (`PROVIDER_SETTINGS`), so a setting the worker would
ignore can't read as configured. A file that isn't there stops the worker before it registers.

**The provider is found, never named, outside its directory (R4.6).** `create_operation_runner` takes the provider
and its settings, and finds the one provider package whose `worker.PROVIDER` matches. That package's
`worker.create_runner(settings)` builds the runner. This is the way `create_tool_authorities` finds
`eligibility.AUTHORITY`. None, or two, is refused, naming the providers found. A test holds the adapter's list of
settings equal to the schema's.

**What each claim confirms, beyond R5.18's transaction:**

| check | as built | why |
|---|---|---|
| **the Studio it was proved on (R2.4)** | Studio's version and its tool list (`<count>:<schema digest>`) are held to `PROVED_VERSION` and `PROVED_TOOLS`. Another reads `not_executed` before any write. A runner given no pins runs nothing | Studio updates itself unasked. `ToolCheck` was built for this comparison, and nothing made it until now |
| **the place's pinned baseline (R3.6's bindings)** | before sync, the place's non-script baseline is read and held to its pin. A place that drifted is reset (R5.17) and the transaction begun again once, with every check run again, Studio in front included. A reset that fails, or a place still drifted, reads `not_executed` with both reasons | the worker resets its tool only after an `interrupted` run or an unknown state. Without this, a drifted place would refuse every claim until a person stepped in |
| **the scripts after play (R3.6)** | after stop, the synced folders are read back and held to the manifest. A script changed in Studio during the run fails it as `not_executed`, naming the script | "a script that changes during a QA transaction fails it" |

**The lease.** The worker's loop already holds one lease across the runner's `run` and renews it while the call runs
(R5.5). A cancel stops the call, play is stopped in the transaction's `finally`, and the tool is reset. So the
transaction is under one lease because it is one call.

**One operation is served: `play_scenario`.** This narrows R3.6's four typed operations and withdraws R5.15's "`sync_source`
is served once it is proved":
- **`sync_source` and `read_console` are steps of `play_scenario`** (R4.3), and every request carries a scenario;
- **nothing dispatches an operation on its own** in the first milestone: R5.14's plan gate refuses a planned one;
- **`capture`** is supplementary evidence (R3.6), and #3049 keeps captures out of 2.8's acceptance evidence.

Serving an operation nothing can ask for would register a mode with no proof behind it. **When it changes:** with the
first milestone that plans an operation of its own (R5.14).

**Editor edits returned as a revision (R2.7) wait for an operation that edits.** In this milestone `execute_luau` runs
only the harness's fixed programs, so nothing SquadOps runs makes an editor edit. Any edit found is someone else's,
and it fails the run (above). Returning edits as revision B, through `apply_workspace_patch`, belongs with the first
operation that edits in Studio.

**R3.6's "unattended, including with Studio behind other windows" is narrowed** by R5.18. Observations, sync and
play run with Studio behind other windows. Studio's input tools act only on a Studio in front.

**Evidence on the real Studio** (0.747.0.7471481, `z_tower-ascension`, the runner built from the worker's settings by
`scripts/dev/studio_play_scenario.py`):
- a click scenario with another app in front was refused in 0.0 s, naming the process in front;
- an input-free scenario passed both its assertions, through the proof check, the pinned baseline and the read-back
  after play, in 78 s;
- a wrong `PROVED_VERSION` was refused in 0.5 s, before any write.

**Still #3039's:** the live run on the Mac's worker, registered with the Spark and claiming `play_scenario`,
including after a Studio restart with no person involved (its done-when).

**Who ruled.** The MacBook lane, under the owner's "go ahead with #3039" and their "yes" to this piece (2026-11-15).

## R5.20 Phase 2d proved on the worker, across a Studio restart with no person involved (#3039, 2026-11-16)

**What changed.** #3039's done-when ("each operation is proved on the worker, including after a Studio restart with no
person involved", R2.4) is met for the one operation R5.19 serves, `play_scenario`. The worker's registration with the
Spark's runtime moves to #3046, the worker as a service on the MacBook, which already registers with the target
runtime as its done-when.

**The proof:** `scripts/dev/studio_worker_proof.py`.
- **The worker's own loop** (`Worker.serve`, the call `worker_main` makes) runs the runner its package creates from the
  worker's settings (`SQUADOPS__WORKER__ROBLOX_STUDIO_*`).
- **The runtime** is the real `WorkerRegistry` over its memory store, in the same process. It is called as the worker's
  HTTP client calls the routes, so the enqueue, claim, lease, cancel and fenced submit are the registry's own.

**Evidence on the real Studio** (0.747.0.7471481, `z_tower-ascension`, 2026-11-16). The scenario clicks the title
screen's Play button, then reads three assertions: the title gone (client), Energy 50 (server) and the HUD shown
(client).
- **Registration:** the worker registered `roblox-studio/play_scenario`, its Studio version and its tool-list digest.
- **Round 1:** the operation was claimed in 2 s and completed in 85 s, and each of the three assertions passed.
- **Round 2:** the operation was cancelled after 20 s of play.
  - The worker saw the cancel at its next lease renewal, 30 s after the claim. It stopped the run and reset its tool.
    Studio was quit, the place restored from its baseline file and Studio reopened, in 32 s, with no person involved.
  - The operation was submitted `interrupted` and accepted.
  - Studio's process changed from 31620 to 87522, and the place file's sha256 equals the baseline's again.
- **Round 3, on the reopened Studio:** the operation was claimed in 3 s and completed in 82 s, and each of the three
  assertions passed.
  - The reopened Studio came to the front by itself, so the click's front check (R5.18) passed with nobody at the Mac.

**What this evidence leaves to other rows:**
- **#3046:** the worker against the Spark's runtime, over its HTTP client and the tailnet. PR #3027's wiring test runs
  the same loop over HTTP against the real routes, on one machine.
- **#3041 and #3105:** an operation queued by a cycle. Only an agent's own task can queue one
  (`operations:request`), so it needs a cycle on the Roblox development profile with a scenario criterion.
- **#3046:** the worker running as a service.

**Who ruled.** The MacBook lane, under the owner's "go ahead with #3039" and their go-ahead for this proof, including
the Studio restart (2026-11-15).

## R5.21 Re-qualification after a Studio update as built: the record is the pin (#3048, 2026-11-16)

**What changed.** R5.19 pinned the worker to the Studio it was proved on with two settings, `PROVED_VERSION` and
`PROVED_TOOLS`. Studio updates itself, so after an update every claim read `not_executed` (R2.4) until someone edited
those settings by hand. R5.7 rules that a recorded run moves the pin, never a hand edit. So the two settings are
replaced by one, `SQUADOPS__WORKER__ROBLOX_STUDIO_QUALIFICATIONS`: the directory of the worker's qualification
records.

**The run** (`scripts/dev/studio_requalify.py`, `qualification.requalify`), on the Studio the Mac runs now:
1. The live Studio's version and its tool list are read.
2. The qualification scenario is played with Studio held to exactly those.
3. The place is reset: Studio is quit, the place restored and Studio reopened (R5.17).
4. The scenario is played again.

It passes when both plays complete with every assertion passed and the reset succeeds. A step that fails ends the run.

**The record** is one JSON document per run, passed or failed. It names:
- the Studio version, the tool list (`<count>:<schema digest>`) and the tool names;
- the record it would replace, and the tools added and removed since then;
- the scenario's digest and the source revision played;
- each step's outcome, and the first failing step by name.

Records carry assertion ids and outcomes only, so the player's account appears in none.

**The pin.**
- **Which record:** the newest passing record for this provider version. A failed run leaves the pin where it was.
- **When it's read:** at each claim, so the claim after a passing re-qualification runs with no restart.
- **Recorded with each result:** each result's `ran_with` names the record (`qualified_by`).

**What is refused, by name, before any tool is called:**
- no passing record;
- a record that can't be read. Skipping it could pin an older record over a newer one;
- a record whose body doesn't match its own digest, because it was edited after it was recorded.

**Studio is used by one process at a time.** A re-qualification holds a lock file in the same directory for its
whole run.
- **A claim that finds it held** reads `not_executed`.
- **A worker's reset that finds it held** raises, and the worker tries again at its next claim (R5.5).
- **A re-qualification started during a claim** is refused, and nothing is recorded.

**R5.7's "the provider's four operations" is read as the operation R5.19 serves:** `play_scenario`, whose transaction
includes the sync and the console read, plus the reset.

**Evidence on the real Studio** (0.747.0.7471481, `z_tower-ascension`, 2026-11-16, with an input-free scenario while
the Mac was locked):
- **No record yet:** a play was refused in 0.0 s: "no passing qualification of roblox-studio 1 is recorded …
  re-qualify".
- **The re-qualification passed in 191 s.** Both plays passed both assertions. The reset quit and reopened Studio,
  and its process changed from 87522 to 4514. The record pins `38:1ba499d8…`, the tool list R5.19 was proved on.
- **The next play read its pin from that record** and passed both assertions, in 76.5 s.

**What it doesn't show live.** Studio didn't update during the run, so the version-mismatch refusal after an update
is shown by the tests over the stand-in. R5.19 showed that refusal live, for a wrong pinned version, in 0.5 s.

**Who ruled.** The MacBook lane, under the owner's "go on 3049 and 3048" (2026-11-16).

## R5.22 Payload limits as built: measured on the real tree, and set with the product's own (#3049, 2026-11-16)

**What prompted the change in plan.** Measuring for #3049 found that a source-backed run refuses z_tower-ascension
at checkout, before any request is built: 2,298 KB of source and config against a 384 KB cap (#3118). A request
limit set below whatever cap replaced it would refuse at the worker's port a tree the run carries whole. The owner
placed #3118 in 2.8 with #3049 (2026-11-16: "put 3118 in 2.8 with 3049"). SIP-0112 H.32 records the cap and the
resolution's limit.

**The measurements** (z_tower-ascension at `0beaac0`, 2026-11-16):

| what | size |
|---|---|
| the whole tree as staged: 234 text files, as a request on the wire | 3,059,816 bytes |
| the same request stored as JSONB in Postgres, after compression | 1,255,666 bytes |
| `src/` alone: 137 files, as a request on the wire | 1,855,801 bytes |
| `src/` alone, stored in Postgres | 696,552 bytes |

The registry rewrites an operation's row, request included, at each lease renewal (every 15 s).

On the real Studio, a play's evidence items were 197 bytes (`play_log.json`) and 6,936 bytes (`console.txt`), and
the whole result 8,216 bytes on the wire. The runner keeps at most 20,000 characters of console.

**The limits:**
- **The request:** its staged tree may hold up to 4 MiB in UTF-8 (`REQUEST_TREE_LIMIT_BYTES`). That is the
  resolution's limit, held equal by a test. The executor holds the tree it stages, with the scenario's file in it,
  to the same limit, so a tree it passes is never refused at the port.
- **Each evidence item:** up to 256 KiB (`EVIDENCE_ITEM_LIMIT_BYTES`), about three times the console's largest
  possible tail.

**Refused by name, and nothing truncated:**
- **At the port.** Both ports refuse a request past the limit before anything is queued or sent. It reads
  `not_executed` with its size, the limit and its three largest files, and it isn't flagged as no worker being
  available.
- **At the worker.** A result with an item past the limit is settled `not_executed`, naming the item. Its
  records aren't returned without the evidence they rest on, and the item never reaches the operation's row.
- **When the handler reads a result,** `result_defects` names an item past the limit, for a provider that isn't
  this worker's.

**Captures stay outside 2.8's acceptance evidence**, as ruled. No binary evidence path is built.

**Not measured here:** a claim's time over the tailnet. That needs the worker registered with the Spark, which is
#3046's.

**Who ruled.** The owner: "go on 3049 and 3048", then "put 3118 in 2.8 with 3049" (2026-11-16). The limits are the
MacBook lane's, from the measurements.

## R5.23 The worker as a service on the MacBook as built, and what a restart needs (#3046, 2026-11-16)

**The service.** The worker runs as the per-user LaunchAgent `xyz.backspring.squadops.worker`, named to the owner
before it was installed. It is a user agent, not a system daemon, because Studio needs the user's session.
- **When it runs:** launchd starts it at login, and again 30 s after it exits.
- **The network:** it connects outward only and opens no listener.
- **Installing it:** `scripts/dev/worker_service.py install --env-file <file>` reads the worker's settings from one
  env file, strictly. It refuses:
  - a setting outside the worker's section and the secrets provider's;
  - a key given twice;
  - a quoted value;
  - a client secret written in, since the agent's document is plain text under `~/Library/LaunchAgents`;
  - any secrets provider but `file`;
  - a secret file others can read;
  - a reference that doesn't resolve;
  - a provider setting naming a file that isn't there.

  Only then is the agent written and loaded.
- **The other commands:**
  - `status` reports the agent's state, the worker's status and any run window;
  - `run-window --hours N` holds `caffeinate -d -i` for that long, so a click scenario finds Studio unlocked and in
    front, and records the window;
  - `uninstall` removes the agent.
- **`bootstrap dev-mac --with-worker`** runs the install. Every other profile refuses the flag.

**The worker resets its tool before it registers.** What an earlier process left in the tool is unknown, and a
worker whose tool is closed reads offline, so no request would be queued for it.
- For Studio, the reset is R5.17's: quit, restore, reopen. So Studio opens on the place by itself when the service
  starts, with no step of its own.
- A reset that fails leaves the worker registered, with each claim answered `not_executed` and the reset tried
  again, as after any unknown state (R5.5).

**The worker records its own status** in `SQUADOPS__WORKER__STATUS_FILE`, a new required setting, written whole and
readable by its user alone. It holds:
- whether the tool reset at start, and why not;
- the session it registered as;
- when the runtime last answered a registration, heartbeat or renewal;
- when it last couldn't be reached, and why.

The Mac never calls the runtime itself (the owner's rule of 2026-11-10), so its doctor reads this instead.

**`squadops doctor dev-mac`'s `worker` checks** run only on a Mac with the agent installed. Each is named:
- `service`: running, from launchctl;
- `config`: valid, with its secret reference resolving;
- the provider's own checks, found in its package as `worker.host_checks` (R4.6). For Studio:
  - `studio`: installed, with a version that reads;
  - `studio_mcp`: present and executable;
  - `place`: the place file there, and the baseline equal to its pin;
  - `qualified`: a passing re-qualification of the Studio installed now;
- `registered`: a session, and the runtime answering within one lease.

**What a restart needs: the owner's login.** This MacBook has FileVault on and no automatic login. After a restart,
nothing of the user's runs until the password is typed at startup, and a LaunchAgent can't start before then.

#3046's done-when ("after a reboot of the MacBook, the worker registers and serves … with no person involved") can't
be met on this Mac without turning FileVault off. That is a security setting, and the owner's alone, and FileVault
stays on. So the done-when is read, as the owner ruled (2026-11-16), as **after a restart and the owner's login, the
worker comes back and serves with nothing more to do.** That holds for 2.8's counted run, which is attended
(decision 7).

An unattended overnight run needs no change for this, as long as the Mac doesn't restart: a run window keeps it
awake. A restart during one, such as a macOS update, leaves the worker offline until the owner next logs in, and no
request is queued for an offline worker (R5.10, R5.12).

**Also narrowed: "serves a fixture operation".** That was written before the Studio provider existed. A
`roblox-studio` worker serves `play_scenario` only (R5.19), so the check after a restart is an input-free
`play_scenario`.

**Evidence on the MacBook** (2026-11-16). The worker is registered with this Mac's own deploy, standing in for the
Spark's until the owner carries the worker's secret across.
- **Install:**
  - the agent loaded, and the worker started;
  - Studio was quit, the place restored and Studio reopened, in 32 s;
  - the worker registered and recorded its session.
- **`doctor dev-mac --check worker`:** 7 of 7, each named.
- **The worker killed:** launchd started it again (`runs = 2`). It reset Studio again and registered as a new session,
  32 s after the kill.
- **A run window of 36 s:** held both assertions, and `status` and its record showed it.
- **The Spark, read from the Mac:** `spark` resolves by MagicDNS to its tailnet address, and its runtime answers
  `/health`.
  - The Spark session confirmed the `squadops-worker` client issues tokens with the `worker` role.
  - The token endpoint must be addressed as `http://spark:8180/...`, because the runtime accepts only that issuer.

**Registered with the Spark's runtime** (2026-11-16, 15:46 UTC). The owner carried the worker's secret to the Mac by
hand. The service, reinstalled from the main checkout at `912a922b`:
- reset Studio and registered as session `wks-c4655eb7…`;
- has its heartbeats answered;
- reads 7 of 7 in `doctor`.

The Spark session's `squadops workers list` shows `macbook` online, serving `roblox-studio/play_scenario`, with Studio
0.747.0.7471481 and the tool-list digest it was qualified on.

#3124 fixed a race this reinstall found: `launchctl bootout` returns before the old agent is gone.

**Still #3046's:** the check after a restart and the owner's login.

**Found here:** `python -m squadops.cli.main` ran no command, so the doctor run that ends every bootstrap checked
nothing (#3122, fixed in the same PR).

**Who ruled.** The owner: "go ahead with #3046" (2026-11-16), after the service's label was named. The reading of
the done-when for FileVault is the owner's too, the same day ("I'm good with your recommendations").

## R5.24 The worker service after a restart: read once, and closed on the owner's ruling (#3046, 2026-11-16)

**What changed.** R5.23 left one check: after a restart of the MacBook and the owner's login, the worker comes back
and serves with nothing more to do. It was read once, on 2026-11-16. The worker came back by itself. Its
registration waited on the MacBook's tailnet connection, which the owner started by hand. The owner then set the
connection to start at login and ruled that the check is not repeated. #3046 closes on that ruling, and the ledger
row is shipped.

**The reading** (the MacBook restarted and the owner logged in at about 18:00 UTC):
- **The service:** launchd started the worker at 18:00:21 (`runs = 1`, never exited).
- **The tool:** the reset at start succeeded at 18:00:45. Studio was reopened on the place, and the worker's status
  reads `tool_ready: true` with an empty note.
- **Registration:** from 18:00:46 to 18:06:20 each attempt, one every 3 s, failed at the token endpoint, because
  `spark` resolves only on the tailnet and the MacBook's Tailscale had come up stopped. None of those attempts reached
  the Spark. The owner started Tailscale, and the next attempt registered, at 18:06:23, as session `wks-5a21e237…`.
  The worker was not restarted.
- **`doctor dev-mac --check worker`** at 18:15: 7 of 7 (`service`, `config`, `studio`, `studio_mcp`, `place`,
  `qualified`, `registered`).
- **The Spark's side:** the old session was last heard at 17:55:22. The new one is online, serving
  `roblox-studio/play_scenario` on Studio 0.747.0.7471481 with the tool list it was qualified on, its heartbeats
  answered and no refusals.
- **One claims poll failed** at 18:06:47 with an empty read error. The Spark's log shows claims paused from 18:06:41
  to 18:06:50 and resumed on a new connection. The session was kept.

**What needed a person, and what was done about it.** Tailscale was not a login item on the MacBook, so after the
restart the app was not running. The owner added it as a macOS login item the same day. It is a setting on the
owner's machine, outside the repository, and `bootstrap dev-mac --with-worker` does not set it.

**What this reading leaves unshown:**
- **Tailscale connecting by itself after it launches at login.** The owner ruled that no second restart is run for it.
  If it fails, the worker's status file and its log name the cause, as they did here, and the worker registers once
  the name resolves.
- **A `play_scenario` claimed from the Spark's runtime by this worker.** R5.23 named an input-free `play_scenario` as
  the check after a restart. The runtime queues an operation only for a cycle's task (R5.6), and no cycle requests
  one until the `game_dev_roblox` profile exists (#3041). The reading above is registration, heartbeats, `doctor` and
  the worker's status. The first operation claimed from the Spark's runtime is read in #3041's cycle on the Spark,
  and that reading is recorded there. `play_scenario` on the worker's own loop against the real Studio is R5.20's.

**A restart during a run window** now has two conditions before the worker is back: the owner's login (R5.23) and
the tailnet connection. No request is queued for an offline worker (R5.10, R5.12).

**Who ruled.** The owner, 2026-11-16: "we don't need another restart test", after adding the login item, and "go" on
the MacBook lane's proposal to close #3046 on that ruling.
---

## R5.25 The reader reads a screen's visibility (#3176, 2026-11-17; R5.9; SIP-0118 R5.5)

**What changed.** `gui_state` `visible` reads a screen (a `ScreenGui`, any `LayerCollector`) as enabled. The
harness read `gui_state` of a GUI object alone and refused a screen as unsupported.

**The evidence.** The 2.8 demonstration's full-path gate, second attempt (`cmp_1afaeaaacd46`): both baseline
plays ran in Studio and stopped at the scenario's third setup action, "…TA_HUD can't be observed (…is a
ScreenGui, not a GUI object)". The setup stopped, no assertion executed, and the baseline read was blocked. The
strategy skill's worked example observes the HUD with `property` `Enabled`, which works. The proposals wrote
`gui_state visible` on the screen in three of three (#3041's part 5 and both attempts of this gate).

**The rule.**
- **`visible` of a screen is its `Enabled`,** which is what the harness already read of the screen a GUI object
  sits in (`harness/observe.luau`, `shown`).
- **`text` of a screen stays unsupported,** naming its class: a screen has none.
- **Additive.** No scenario that executed before reads differently, and the vocabulary's declaration
  (`scenario_vocabulary.json`) is unchanged, so the reader is still `roblox-studio/1` and no skill's copy moves.
- **The provider's version is 2.** A qualification pins the version it was proved under, so the worker refuses
  to play until it is requalified on its Studio (`scripts/dev/studio_requalify.py`).

**The evidence it works.** The harness's observation script runs only inside Studio, so no unit test executes
it. It is read live: the requalification on the MacBook's Studio plays a scenario that waits on a screen's
visibility, and its record is named in the PR. The adapter's tests hold the version and the refusal a worker
with no record of it gives.

**Who ruled.** The Spark lane read the plays. The change is the MacBook lane's, which owns the Studio adapter.

---

## R5.26 A renewal doesn't wait on the tool, and a result that ended behind one is submitted (#3185, 2026-11-17; R5.5, R3.3)

**What changed.** Three things in the worker's loop (`squadops.remote_execution.serving`):
1. **A renewal carries the health read before the claim.** The tool is probed only between claims. R5.5's loop
   probed it at every renewal, while it ran the operation.
2. **An operation that ended while a renewal was out submits its result,** whatever the renewal answered. R5.5's
   table read a refused renewal as "stops the tool and resets it. It submits nothing".
3. **A tool whose last run returned a result isn't reset when the next claim says "reconcile first".** R5.5's rule 3
   already said the tool is reset after any ending but a returned result. The loop reset it on that claim anyway.

**The evidence.** The 2.8 demonstration's first rehearsal (`cmp_85f97e001320`, 2026-11-17), B-1's first candidate
play, `rop-847b84b405ce4ec6bc7610f4b730bfc7`:
- **The runtime's side:** renewals arrived every 15 seconds up to 19:27:26.5 UTC, and the next at 19:28:41.6. The
  60-second lease ended at 19:28:27.47 as `expired`, and the late renewal was answered `not_claimed`. No result
  was posted for the attempt.
- **The worker's side:** Studio's log shows the play begin and stop on the same offsets as the two baseline plays
  before it, and the operation's connection to Studio close 76 seconds after the claim, where both baseline plays
  completed. A second connection then held for sixty seconds. That was the renewal's probe
  (`RobloxStudioRunner.health` opens a session of its own), started as the operation's session was closing.
- **What followed:** the worker read the refusal as a running operation, reset the tool, and the reset's relaunch
  of Studio met a pending update (#3184). The worker had no proof for the new version and the window ended.

**The rule.**
- **`OperationRunnerPort.health` is asked only of an idle tool.** It asks whether the tool can run an operation
  now. A tool that is running one can't answer without being reached into, and for Studio the probe is a second
  session beside the operation's own.
- **Nothing the tool does holds a renewal back.** The lease is the runtime's only sign that the operation is
  still held, so a renewal is sent at its interval with what the worker already knows.
- **A finished operation's result is what the worker says next.** A claim the runtime had given up refuses the
  result and records the refusal (R3.3: "a late completion never satisfies a newer attempt"). That record is how
  an operator learns a finished result arrived late. Before, the only trace was a line in the worker's own log.
- **The reset follows what the worker knows of its tool.** A tool that returned a result left a known state. It
  isn't stopped, and it isn't reset then or at the next claim. Every other ending resets as R5.5 has it: a
  cancel, a refused renewal or an ended lease while the tool still runs, an ended session, a tool that raises or
  reports `interrupted`, and a worker that has just started.

**Not changed.** The lease's length (60 seconds) and the renewal's interval (15). A renewal the runtime answers
late can still outlast the lease. What changes is what the worker does then: it submits the result it holds and
keeps its tool as it is.
- **The heartbeat between claims still waits on its probe.** A probe that answers late there delays the next
  claim and holds no lease. It is left as it is. The claim and heartbeat timeouts seen near a run's start may be
  the same stall, which is unconfirmed.
- **Each claim renews with the reading made just before it.** The probe is made after a claim ends and before
  the next is asked for, so a renewal's reading is as old as its operation is long.

**The tests.** Both enter at `Worker.serve()` over the real registry
(`tests/unit/remote_execution/test_worker_serving.py`): a tool that answers a probe after 90 seconds while it
runs keeps its lease through a 150-second operation and is never probed; and an operation that ends inside a
70-second renewal has its result refused and recorded, with no stop and no reset, and the second attempt runs.

**Who ruled.** The Spark lane read the runtime's side and filed #3185. The change is the MacBook lane's, which
built the worker.

---

## R5.27 The reset names a Studio update (#3184, 2026-11-17; R3.6, R5.17, R5.21)

**What changed.** The reset (R5.17: Studio quit, the place restored from its baseline file, Studio reopened)
reads Studio's installed version, and the worker's status records every reset.
1. **Before anything is touched,** a Studio that isn't the version the worker's proof names is refused, with both
   versions and the re-qualification it needs. So is a bundle whose version can't be read.
2. **After the reopening,** the version is read again. A Studio that changed across the reopening is named with
   both versions, whatever the reopened Studio then read, and whether or not the place came back.
3. **The worker's status** (`worker-status.json`: `tool_ready`, `tool_note`) is written at every reset, held or
   failed. It was written at the reset made at the worker's start alone.

**The evidence.** The 2.8 demonstration's first rehearsal (`cmp_85f97e001320`, 2026-11-17, times ET), after the
worker lost a claim (R5.26):
- 14:28:44 the reset quit Studio 0.747.0.7471481, which had run since 10:31 and played every operation of the day.
- 14:28:48 the reset's open of the place file started Studio. It logged "Latest version 0.748.0.7481526", launched
  its installer with launch intent `None` and exited.
- 14:29:08 the installer replaced the application, and at 14:29:09 started Studio 0.748 holding no place.
- 14:29:13 the reset failed with "the place in Studio (None) is saved to the cloud, or doesn't say".
- 14:29:17 the next claim's reset failed with "the running Studio holds [None], not ta-copy.rbxl; the reset
  doesn't quit it". That is the reason the runtime recorded.
- The worker's status file read `tool_ready: true` with no note throughout, while the runtime's row read offline.
- Neither message named the update, the versions, or the re-qualification. The cause was read from Studio's and
  the installer's own logs.

**The rule.**
- **The reset's reopening is a launch, and Studio updates itself at a launch.** The reset reads the installed
  version on both sides of it. This is the one point where the worker itself causes the version to move.
- **A version the worker has no proof for is said first.** An updated Studio comes back holding no place, and
  "holds no place" is the least of what happened. The first refusal is the version, and what the reopened Studio
  read follows it.
- **The remedy is in the message:** re-qualify on the new version with the place open in it
  (`scripts/dev/studio_requalify.py`, R5.21). The installer starts Studio with no place, so a person opens the
  place file first.
- **A re-qualification's own reset is held to the same rule.** Its runner is pinned to the live version, so an
  update that lands at its reset fails the run by name, and the run is made again on the new version.
- **With no proof at all** the reset has nothing to hold Studio to and compares only across its reopening. Every
  play is already refused by name then (R2.4).
- **The version read is the installed bundle's,** as a play's own check reads it (R5.19). Studio's installer
  ends every running Studio before it replaces the bundle (its log, 14:29:06: "Terminating apps with bundleId
  com.Roblox.RobloxStudio", then the move). So the bundle and a running Studio differ only while a replacement is
  under way, and a reset that meets one refuses. That is the intended failure: the running Studio is about to end.

**Deliberately not built: holding an update back.**
- **What was read:** Roblox's Studio setup page and its developer forum (2026-11-17). They describe no setting
  that stops Studio updating at launch, and a forum request for one is open. Studio's own log shows the check
  made at each start, before any place is opened.
- **So a waiting update lands at the next launch, whoever makes it.** A reset that refused to relaunch would
  leave the place in an unknown state on a Studio nothing can restore, and the update would still land at the
  next launch.
- **What keeps it out of a run is when the pin is read.** A measured run starts with a fresh launch of Studio
  and a reading of its version against the pin, with a re-qualification first when it moved. That is the run's
  procedure (the 2.8 demonstration's pre-registration), and the reset's part is to say so when it happens anyway.

**The tests.** `tests/unit/remote_execution/test_roblox_studio_reset.py`, entered at `RobloxStudioRunner.reset`:
an update at the reopening that leaves no place, one where the place reopens, and a bundle unreadable
mid-replacement, each named; a Studio that isn't the proved version, and one whose version can't be read, each
refused with nothing touched. The wiring test enters at `Worker.serve()` with the real runner over the real
registry and asserts the reason the runtime records and the worker's status.
`tests/unit/remote_execution/test_worker_serving.py` holds the status through a reset that fails at a claim and
one that then holds.

**Who ruled.** The MacBook lane read the Mac's logs and owns the Studio adapter. The Spark lane read the
runtime's side.

## R5.28 A worker whose tool isn't ready is read as R5.10 reads an absent one (#3192, 2026-11-17; R5.10, R5.18)

**What changed.** R5.10 retries an increment that is blocked only because no worker took its scenarios, and
leaves anything a worker returned to the work's routing. A worker that took a scenario and refused it because its
own tool couldn't run it then fell on the work's side. The Campaign read it as a gap in the candidate and repaired
it (SIP-0109 §10 row 8), rebuilding a candidate nothing had faulted. Now:

| Point | As built | Why |
|---|---|---|
| **The worker says so, as a fact on the result.** `RemoteOperationResult.tool_unready` means a worker took the operation and its tool wasn't ready to run it, for a reason of the worker's own environment. It is set only by a worker, only on `not_executed`, and never read from a reason's words. The wire refuses it on any other status | the routing must not rest on prose (R5.10's first point) |
| **Where the Studio provider sets it:** another app in front of Studio (R5.18); Studio not the version the worker was proved on, or busy (R2.4); no place files or pins given; a drifted place the reset couldn't restore, or still drifted after it; and, before play, a session that won't open or a place it can't read. The serving loop sets it on the `not_executed` it answers when its tool couldn't be reset | each is this Mac's state, and building the candidate again changes none of them |
| **Where it doesn't:** a scenario outside the vocabulary or changed after it was frozen, a script the provider can't place, a sync refused, a place whose state play changed, and scripts changed in Studio during the run | each could be the request's or the candidate's. Left with the work's routing, as R5.10 left a worker that went silent |
| **Every reading's document carries the key** (`records_document`), and every result on the wire (`result_to_wire`). A result or reading stored before the key reads as not flagged: the routing it had then. On the wire the key is the one optional one, since every settled row is read back through `result_from_wire` | R5.10's third point |
| **Delivery reads the two facts together** (`reading_for_want_of_a_worker`, in `runner_acceptance`). A scenario unread because no worker took it, or because the one that took it wasn't ready, is flagged as R5.10 flags it. So the evaluation's `blocked_only_by_availability` and the hearing's rows 10 and 11 apply unchanged | SIP-0109 §10's rows are unchanged; the input that reaches rows 10 and 11 is widened again |

**The evidence.** The 2.8 demonstration's rehearsal 2 (`cmp_66aab9993dc8`, 2026-11-17, times ET). Between 20:02:18
and 20:02:57 five plays were refused with "the scenario acts through Studio's input, which acts only on a Studio in
front, and process 1124 is in front": the run's two scenario plays, and the Campaign's candidate plays of S3, S4 and
the frozen S1. Process 1124 was Terminal; the owner had clicked into it ("yes I clicked terminal"). The cycle
ended at row 8 (repair), and the Campaign's elapsed-time pause stopped the repair before it launched.

**The tests.** `tests/unit/campaigns/test_machinery_campaign.py` enters at the Campaign's start, with the worker
taking every operation over HTTP and refusing each candidate reading for its tool. The Campaign takes rows 5, 10 and
11, launches an increment and one retry, no repair, and escalates. Taking the flag out of delivery, or out of the
wire, gives rows 5, 8 and 9. `test_wire.py` holds the key across the wire, a result stored before it, and the
refusals. The Studio provider's tests hold the flag on an app in front and a place the reset couldn't restore, and
off on a request's own defect. `test_worker_serving.py` holds it on a reset that failed at a claim.

**Who ruled.** The owner, 2026-11-17: "go ahead and fix 3192". The Spark lane built it. Whether the provider should
bring Studio to the front itself is #3193, for the owner's ruling, and isn't this.

## R5.29 Studio's qualification identity includes its release channel (#3206, 2026-11-18; R2.4, R5.19, R5.21, R5.27, R5.28)

**What changed.** The Studio a worker is proved on was its version and its tool list (R5.19, R5.21). It is now its
version, its release channel and its tool list.

| Point | As built |
|---|---|
| **Where the channel is read** | From the startup log the running Studio holds open (`[FLog::ClientRunInfo] The channel is …`), found through `lsof` on Studio's one process. So it is the channel of the Studio a play would run on, never of an earlier launch whose log is in the same directory |
| **When it's compared** | At every claim, before any tool is called, with the version and the tool list (`_held_to_proof`). At a reset, before anything is touched and again after the reopening (R5.27's two readings). A claim replayed after a reset is checked again |
| **A channel that differs** | The claim reads `not_executed`, naming both channels, and is flagged `tool_unready` (R5.28). So the increment is retried and the candidate never repaired |
| **A channel that can't be read** | Refused the same way, naming why: no Studio running, more than one, no startup log held open or more than one, a log naming no channel, or `lsof` failing. No channel is assumed |
| **A proof that names no channel** | The newest passing record is the pin (R5.21). One made before this amendment names no channel, and the worker runs nothing on it. An older record that does name one is never used in its place |
| **The record** | Schema `squadops.studio-qualification/2` adds `studio_channel`. A `/1` record is still read as the run it was, with the digest it was written with, so the directory stays readable and a re-qualification can say what it replaces |
| **Each result** | `ran_with` carries the proof's identity (`qualified.studio_version`, `qualified.studio_channel`, `qualified.studio_tools`) and the identity the play ran on (`played.…`), beside `qualified_by` |
| **The worker's registration** | `tool_versions` gains `studio_channel`. A worker registers before its Studio is up when its first reset fails (R5.23), so a channel not read then registers as `unread`. Each claim reads it again |
| **`squadops doctor`** | The `qualified` check names the pin's channel, fails a pin that names none, and fails when a running Studio is on another channel or doesn't say its channel. With no Studio running it has no channel to compare, and says so |

**The evidence.**
- **The move that prompted it** (#3206): on 2026-11-18, after the 2.8 demonstration's window closed, Studio on the
  worker's Mac restarted through its installer. Its version (`0.748.0.7481526`) and tool list (`38:1ba499d8…`) were
  unchanged, and its channel went from `production` to `zluauordereddensehashmapcontrol`. Every check the worker made
  passed. The channel was read by hand, and the worker re-qualified before it played again.
- **It wasn't the first.** The Mac's kept startup logs (44 launches, 2026-10-29 to 2026-11-18) name five channels.
  At `0.747.0.7471481` alone Studio launched on three:

  | launches (UTC) | version | channel |
  |---|---|---|
  | 2026-11-10 (2 launches) | `0.747.0.7471481` | `production` |
  | 2026-11-14 to 2026-11-16 (11 launches) | `0.747.0.7471481` | `zmimalloc747control` |
  | 2026-11-17, 15:13 and 15:31 | `0.747.0.7471481` | `zliveforbeta` |
  | 2026-11-17 19:28 | `0.747.0.7471481` | `production` |
  | 2026-11-17 19:29 to 2026-11-18 13:06 (9 launches) | `0.748.0.7481526` | `production` |
  | 2026-11-18 18:36 onward | `0.748.0.7481526` | `zluauordereddensehashmapcontrol` |

  Read against the qualification records' times, no play of the 2.8 line ran on a channel other than its
  record's. One launch did differ: 2026-11-17 19:28, on `production` under a record made on `zliveforbeta`. It
  exited into the 0.748 update before it played (R5.27). Nothing recorded any of this, and nothing would have
  refused a play had a move fallen between a record and a run.
- **Every kept log names its channel once,** on the same line, within the first second of the launch.

**The rules.**
- **A channel move is a change of the proved Studio,** as an update is. A channel can carry another build or flag
  set at one version number. Only a recorded re-qualification moves the pin (R5.21).
- **Missing evidence refuses.** The owner's ruling against silent fallbacks: an unread channel, and a proof that
  names none, each run nothing and say so.
- **The reset's reopening is a launch, and Roblox's updater moves channels at a launch.** R5.27's rule for a
  version is applied to the channel:
  - a running Studio on a channel the proof doesn't name is refused before anything is touched, with the
    re-qualification it needs;
  - a Studio that comes back on another channel is named with both, whether or not the place came back. On
    2026-11-18 the moved Studio came back holding no place, as an updated one does;
  - a reopened Studio that doesn't say its channel is refused.
- **The Studio a reset is about to quit may not say its channel,** and that stops nothing. It is being reset
  because its state is unknown, and the reopened Studio is the one a play would run on.
- **With no proof at all** (the reset run by hand) the channel is compared across the reopening alone, as the
  version is.
- **The provider's version stays 2.** What the harness reads of a game is unchanged. A re-qualification is forced
  by the pin naming no channel, which the refusal says, and a version move would have said less.

**What isn't known.** Whether any of these channels' builds behaves differently from `production`'s at the same
version. Nothing compared them. The rule doesn't rest on it.

**Its limits.**
- **The read is the Mac's.** `lsof` and Studio's log naming are behind `StudioApp.channel()`, and another platform's
  worker supplies its own.
- **Studio's log format is Roblox's.** A Studio that stops writing the line, or renames its log, reads as a channel
  that can't be read, and every claim is refused by name until the reader is changed.

**The tests.**
- `tests/unit/remote_execution/test_roblox_studio_play_scenario.py`, entered at `RobloxStudioRunner.run`, each on a
  Studio at the proved version: another channel, a channel that can't be read and a proof naming no channel each
  run nothing, flagged, with no tool called; a Studio that comes back from the reset's relaunch on another channel,
  or not saying its channel, runs nothing. A completed play's `ran_with` carries both identities.
- `test_roblox_studio_requalification.py`: a Studio that moved channel runs nothing, a failed re-qualification on
  the new channel leaves the pin and the worker refusing, and a passed one moves it and the plays run. A
  re-qualification on a Studio that doesn't say its channel fails at its tool check. The 2.8 worker's own record,
  byte for byte, is read with its digest, is refused as a pin, and no older record stands in. The wiring test
  enters at `Worker.serve()` with the runner as `create_runner` builds it, over the real registry, and reads the
  reason and the flag the runtime stores, for a pin from 2.8 and for a Studio on another channel.
- `test_roblox_studio_reset.py`, entered at `RobloxStudioRunner.reset`: a move at the reopening with the place
  back, with no place, and with no proof; a reopened Studio that doesn't say its channel; a running Studio on
  another channel refused with nothing touched; and a Studio that doesn't say its channel before the quit, reset.
- `test_roblox_studio_channel.py`, entered at `MacStudioApp.channel` with `pgrep` and `lsof` answered as the Mac's
  answered: the running Studio's log among another launch's, a log open on two descriptors, a line a game script
  printed, and each way of not reading it.
- Fifteen mutations of these rules each fail at least one test.

**Who ruled.** The owner adopted the 2.8.1 plan on 2026-11-18, whose item 3 states the identity, the comparisons,
the refusal and the record. The MacBook lane built it and owns the Studio adapter.

## R5.30 A cycle's cancel and a Campaign's abort stop the operations they own (#3236, 2026-11-26; R3.3, R5.4, R5.5, R5.6)

**What changed.** A remote operation was stopped only by its own requester: at the end of its wait, or when the
requester itself was stopped (R5.6). It is now also stopped by the cancel of the cycle it verifies for, and by the
abort of that cycle's Campaign.

| Point | As built |
|---|---|
| **Whose an operation is** | Every request for one names its owner: the cycle, and the Campaign when the cycle is one's and the asker knows it (`OperationOwner`). It is a required argument of the port's `run_operation`, and it is stored in the operation's `origin` beside who asked. The agent's route refuses a request whose origin names no cycle (`REMOTE_OPERATION_OWNER_MISSING`), and the registry raises for one |
| **A cycle's cancel** | The one cancel path asks every operation the cycle owns that has no result yet to stop (`WorkerRegistry.cancel_owned`), and records the cycle as cancelled. A Campaign's abort reaches it through each cycle it cancels |
| **A Campaign's abort** | After its cycles' cancels, it asks every operation that names the Campaign to stop, whatever cycle asked for it. A cycle that had ended is cancelled by nothing, and a play it left out is reached here |
| **A run's cancel** | Asks the cycle's operations to stop, since a cycle runs one workload at a time. It doesn't record the cycle as cancelled: the cycle may go on to another run |
| **A queued operation** | Settled at once: `not_executed`, or `interrupted` when an earlier attempt had begun. Its reason says what ended its owner |
| **A claimed operation** | Marked, as a requester's cancel marks it. Its worker is told at its next renewal, stops its tool, resets it and answers `interrupted`. When its worker goes silent, its lease ends it as `interrupted` and it is never queued again. Both are unchanged (R5.5) |
| **A result that arrives after the cancel** | Taken in and kept as the operation's `late_result`. The operation's own result reads `interrupted`, with a reason that says a result arrived after the cancel. The attempt closes `cancelled`. The worker is answered as for any accepted result, and a repeat is answered as a repeat |
| **A result that came first** | Stands. The operation had its result when the cancel arrived, and the cancel doesn't touch it |
| **Nothing new for a cancelled owner** | A request for an operation whose cycle was cancelled, or whose Campaign was aborted, queues nothing and reads `not_executed` with the reason (`REMOTE_OPERATION_OWNER_CANCELLED` at the route). A send that had already asked still reads the operation it asked for |
| **The answers** | A cycle's and a run's cancel answer `remote_operations_cancelled`. An abort's answer counts the operations that named the Campaign and were still out after its cycles' cancels. A count of 0 says none were out; a null count, with `remote_operations_cancel_failure`, says they couldn't be asked |
| **The store** | Migration 2302: `late_result`, two partial indexes that read the owner from `origin`, the cancelled owners, and `cancelled` among an attempt's outcomes |

**The evidence** (#3236). In the 2.8.1 row-8 window, on 2026-11-19, Campaign `cmp_ab3a75290809` was aborted at
12:34:18 ET and its repair cycle `cyc_bd5078b22c8e` was cancelled.
- The cycle's baseline play, `rop-dacb6e57…`, had been created at 12:33:42 and claimed at 12:33:44.
- It was played to its end. It settled `completed`, its attempt `accepted`, at 12:35:23, and its
  `cancel_requested` read `false`.
- Read on main at `5c93b8ba`:
  - nothing in the cycle's cancel path or the abort route called the registry;
  - an operation recorded its task and send and no cycle, so the store couldn't be asked for a cycle's operations;
  - a result under a valid fence was settled as the operation's result, whether or not a cancel had been asked.

**The rules.**
- **The registry's order decides a race, and the rows say which came first.** Each call is one exclusive
  transaction (R5.4). A result settled before the cancel is the operation's result. A cancel recorded before the
  result makes the result late.
- **A late result is no evidence.** It is kept because it is what ran. No reader is asked to notice a flag: the
  operation's own result reads `interrupted`, which every reader already treats as nothing verified.
- **A worker's own `interrupted` is the operation's result,** cancel or not: the worker saw the cancel and stopped.
- **The owner is the caller's to name, never inferred.**
  - The runtime's own plays name the cycle and its Campaign.
  - A task's handler names its cycle, which is all its context holds. A Campaign's abort reaches that operation
    through the cycle's cancel.
- **A cancel is safe to repeat.** Nothing settled changes, a marked operation stays marked, and the time an owner
  was cancelled at is the first.
- **A failure to reach the registry never blocks the cancel it serves, and is never read as "none were out".** The
  cancel's answer then carries a null count and names the failure, where 0 says none were out. Each operation's
  lease and its requester's wait still end it, and its result is then an ordinary one.

**What isn't changed.** The worker, its serve loop and the Studio runner (R5.5, R5.26). What a worker does at a
cancel was already built. It wasn't reached, because nothing asked.

**Its limits.**
- **A worker hears a cancel at its next renewal.** A claimed play runs for up to one heartbeat (15 s) after the
  cancel, and then its tool is reset.
- **An operation queued before this amendment names no owner.** No owner's cancel finds it, and it ends as it
  always did.
- **An agent's operation names no Campaign.** One still out after its cycle had ended without a cancel wouldn't be
  found by the abort. A task's operation ends with its task, and none is known to outlive its cycle.
- **`ran_with` on a result the worker builds itself,** such as an abandoned play's `interrupted`, isn't here. It is
  the MacBook lane's half of #3236, with the live cancel round on the real runner. It is R5.34.

**The tests.**
- `tests/unit/remote_execution/registry_contract.py`, run on the memory store and on Postgres:
  - an owner's cancel settles its queued operation, marks its claimed one and touches no other cycle's;
  - a result after the cancel is kept as the late one, and a repeat of it is answered as a repeat;
  - a result settled first stands;
  - a cancelled operation whose worker never answers is never run again, whether the worker went silent before the
    cancel or after it;
  - a cancelled cycle and an aborted Campaign are asked nothing new, and a run's cancel leaves its cycle open;
  - an abort reaches a play whose cycle had ended;
  - a repeated cancel changes nothing;
  - an operation with no owner is refused.
- `remote_path.py`, from the agent's port over HTTP to the worker's tool: a cycle cancelled during a play stops the
  worker's tool, which is reset once, the requester reads `interrupted`, and its next request runs nothing.
- `tests/unit/api/test_remote_operation_routes.py`: the route refuses an origin that names no owner, and a request
  for a cancelled cycle.
- **The wiring,** each entered where a live cancel enters:
  - the cycle's cancel route and the run's (`tests/unit/cycles/test_api_cycles.py`, `test_api_runs.py`);
  - the abort route, with a play of the running cycle and one of a cycle that had ended
    (`tests/unit/api/test_campaign_routes.py`);
  - the task's handler, whose operation is read at the registry with its cycle and stopped by that cycle's cancel
    (`tests/unit/capabilities/test_run_remote_operation.py`).
- Loaded-check rows `3236-owner-cancel` and `3236-handler-names-its-cycle`.
- `test_migration_vocabularies.py` holds each column's CHECK list to its vocabulary across the registry's
  migrations. It failed on the new attempt outcome until migration 2302 declared it.

**Who ruled.** The owner adopted the 2.9 plan on 2026-11-26. Its item 2 states the rule: an abort or a cancel asks
every operation it owns to stop, a result after the cancel is kept and is no evidence, and a race has one stated
precedence. The Spark lane built the runtime's half. The MacBook lane, which owns the worker and the Studio
adapter, agreed the seam on 2026-11-26: the serve loop and the runner are unchanged.

## R5.31 A qualification names each tool whose definition changed (#3230, 2026-11-26; R2.4, R5.21, R5.29; the 2.9 plan's item 11, adopted by the owner)

**What changed.** A qualification record held one digest for Studio's whole tool list, and the names (R5.21). It
now also holds each tool's own definition digest, and names the tools whose definition changed since the pin it
replaces. The worker's refusal of a Studio whose tool list differs names the tools too.

| Point | As built |
|---|---|
| **Each tool's digest** | The sha256 of the tool's definition as Studio's `tools/list` gives it, with sorted keys (`session.tool_check`, `ToolCheck.digests`). The list's digest is unchanged, and is still what holds Studio to the proof |
| **The record** | Schema `squadops.studio-qualification/3` adds `tool_digests` (name to digest) and `tools_changed` beside `tools_added` and `tools_removed`. A `/2` and a `/1` record are still read as the runs they were, with the digests they were written with |
| **A `/2` record as the pin** | Still pins. The list's digest holds Studio to it as before, so no worker needs a re-qualification because this shipped |
| **The comparison, when the replaced pin holds no per-tool digests** | `tools_changed` is `null`, and the summary says it can't be said. It is never an empty list, which would read as a comparison that found nothing |
| **The first qualification** | Replaces nothing, so `tools_changed` is empty |
| **The worker's refusal** | `Studio's tools read …, and the operation was proved on … (changed script_read)`, with `added` and `removed` beside it when there are any. Against a pin with no per-tool digests it says the tools that differ can't be named and the comparison is unavailable |
| **What isn't narrowed** | The proof. The whole list stays the identity (R5.21): a change to a tool the adapter never calls still refuses the play, and is now named |

**The evidence** (#3230).
- **2026-11-19, the requalification for #3206:** play 1 completed on a Studio whose list read `38:1ba499d8…`. The
  reset reopened Studio, and play 2 read `not_executed`: the list read `38:3d29f729…`. The version, the channel and
  the 38 names were the same on both sides. Both records read `tools added [], removed []`.
- **2026-11-20, a fresh launch before the #3199 plays:** the channel read `production` and the list `39:b7cd2a22…`,
  with three tools added and two removed. Two changed descriptions among the tools that kept their names were
  found only by diffing two dumps of the list by hand.

**Who ruled it.** The 2.9 plan's item 11 and its D4, adopted by the owner on 2026-11-26. The MacBook lane built it.

**The tests.** `tests/unit/remote_execution/test_roblox_studio_requalification.py` enters at `requalify` and at
`RobloxStudioRunner.run` with the worker's pins read from its records, over the stand-in `StudioMCP`:
- a tool redescribed under the same name, at one Studio version: the claim is refused naming it, the
  re-qualification's record names it in `tools_changed` with nothing added or removed, and the next claim runs;
- a pin written under `/2`: it still pins, a refusal against it says the comparison is unavailable, and the
  record that replaces it holds `tools_changed: null` and every tool's digest;
- a `/3` record missing its per-tool keys is refused by name, as any record with the wrong keys is.

The live runs on the Mac's Studio are in the PR.

## R5.32 A candidate's own setup failure gets one correction in the run (#3200, 2026-11-26; R3.7, R4.4, R5.1, R5.7, R5.28, R5.29; SIP-0096)

**What changed.** A play whose scenario's world wasn't established reads `setup_failed` for every assertion.
That is *not executed*, and it stays so: nothing is credited and nothing failed. One thing is added. Before
such a play is accepted as unverified, the run reads whether the failure is the candidate's own, by six
conditions, each read from a record. When all six hold, the run spends one correction on the candidate, with
the error its provider named in the correction's evidence. When any doesn't, the routing is what it was.

**The evidence.** The 2.8 demonstration's rehearsal 3 (`cmp_83836022543d`, 2026-11-18), cycle
`cyc_4c0ec08c327d`. The candidate set a property its screen object doesn't have, so its client raised as it
started and the title screen never appeared. All six candidate plays read `setup_failed`, and each play's
console named the error and its line. Both baselines had met the same setup minutes earlier. The run made no
correction, the cycle ended `blocked_unverified`, and about 12 minutes of plays were spent on a fault the
first play's console had already named.

**The six conditions** (`remote_execution/setup_attribution.py`, pure: it reads two reading documents and what
the caller knows of the candidate's tree).

| # | Condition | Read from |
|---|---|---|
| 1 | The same frozen scenario's setup was met on the baseline, in this cycle | The cycle's stored baseline reading of the criterion (R5.7): the same scenario digest, completed, every assertion executed |
| 2 | Both plays ran in one environment, served by one worker | `ran_with["environment"]`, which the provider names, and `ran_with["served_by"]`, which the registry writes. Both present and equal on both readings |
| 3 | The candidate's provider named an error in a file the candidate changed, inside its approved footprint | The candidate reading's `script_errors`; the staged tree against the pinned checkout; the approved change request's footprint |
| 4 | The error was logged before the setup's first unmet wait ran out | Every assertion of the candidate's play reads `setup_failed`: the play stopped at its setup, which is where its provider reads the log |
| 5 | The baseline's play named no such error | The baseline reading's `script_errors`. A reading kept before readings carried the key can't say it had none, and fails this. So does one whose list can't be read: a value that isn't a list, or any entry that isn't a path, a line and a message. Nothing is dropped and read around, on either side |
| 6 | Neither play was refused for the worker's own environment | `tool_unready` and `unavailable` false on both, and both completed, so each was held to its proof (R5.28, R5.29) |

**As built.**

| Point | As built | Why |
|---|---|---|
| **The provider reports facts; core attributes** | `RemoteOperationResult.script_errors`: each a staged path, a line and the tool's message. A provider sets it, only on `completed`. The wire carries it as an optional key, and every reading's document carries it. A result naming an error in a file the request didn't stage is refused whole (`result_defects`) | A console is engine prose, and R3.7 has core read no prose. The provider owns mapping its tool's name for a script back to the staged file |
| **What a provider reports** | Only an error with a stack, whose raising frame is a staged file, and the first such block: an error raised by the provider's own probe, an engine or network error with no stack, and the follow-on errors a failed module load raises in each requirer up the chain are not reported | The MacBook lane's reading of Studio's own logs (2026-11-26): about 200 stackless engine errors a day on the place. And the six candidate consoles the vault holds (three cycles, 2026-11-18 and 11-19): a module that fails to load writes its own block and then one follow-on block for each requirer above it, two in the 2.8.1 diagnostic's plays; no line carries a level prefix; and each console holds one play's output |
| **Who served a play is the registry's word** | `ran_with["served_by"]` is written at acceptance, from the session that submitted the result. A worker's own value under that key is dropped first, whatever follows, and a late result kept after a cancel (R5.30) is stamped the same way. A session the store can't return at an accepted fence is a defect, and raises: nothing settles without the name | Two readings can then be told to share a worker without believing either one's own name for itself |
| **The environment is one value, the provider's** | `ran_with["environment"]`: equal for two plays only when everything the provider holds fixed between them is equal (for Studio: the pinned place, the qualified identity and the harness). A provider that can't say leaves it out, and condition 2 then fails | Core compares one value and names no engine's keys |
| **"Before the setup's first unmet wait" is read as "in the log when the setup stopped"** | Condition 4, above | The console carries no timestamps, and the provider reads it once, after the scenario stops at its first unmet setup wait. An error that arrived before the wait began can't be told from one that arrived during it. Read strictly, the condition would fail on the case this amendment exists for, since the client raised as the wait began. Ruled by the Spark lane under the owner's grant of 2026-11-26, and named here because it narrows the plan's wording |
| **Where it is read** | `execution/setup_failure_correction.py`, at the executor's last word on an attempt an agent reported succeeded (`_TaskOutcomeRouter.screen`), for a task that runs an operation | The same seam SIP-0109 §24do uses to refuse a suite that passes on the head: the one place a succeeded result becomes a failure the correction loop routes |
| **The reading is always kept** | `setup_attribution.json`, beside the play's evidence: all six conditions, held or not, each with its evidence, the errors, the baseline reading's artifact id, and whether a correction was dispatched and why not | The plan's item 7: the evidence for each condition is kept and linked from the attribution |
| **One correction, when there is one to spend** | Once per task. None when the run has no correction left: `max_correction_attempts` 0, or its corrections spent. The reading then says `not_dispatched` and why, and the play goes on as unverified | With in-run correction off, the cycle still ends `blocked_unverified` and the Campaign routes §10 row 8, as the 2.8.1 diagnostic's profile needs. A refusal there would end the run on an exhausted budget instead |
| **No unexecuted assertion becomes an executed failure** | The refused result keeps the play's own check rows, every one not executed. The correction's gate, which admits a played task only for an executed failure (R5.1), admits this one more case by the attribution on the result | SIP-0096: only executed-and-passed credits, and only executed-and-failed fails |
| **The repair** | The existing correction for a played task (R4.4): a development repair aimed at the plan's implementation, then the operation re-run on the repaired tree. The error's file, line and message are in the failure it is handed | Nothing new is built to repair with |

**The tests.**
- `tests/unit/remote_execution/test_setup_attribution.py`: an attributable fault; each condition failing alone,
  eleven ways; a play that went past its setup; a baseline that can't say; a record that isn't one.
- `tests/unit/cycles/test_setup_failure_correction.py` enters at `_TaskOutcomeRouter.screen`, which the
  dispatcher is handed as `screen_success`, and then at the executor's classification of what it returns: an
  attributed failure refused with the error, its rows untouched, and let on to correction; three ways of not
  being attributed, each keeping today's routing with the reading kept; the newest baseline reading read; no
  correction to spend, three ways; a pin that can't be read. Five mutations each fail one.
- The wire, the registry's stamp and the fixture provider's stand-in for a tool's log each have their own.

**The Studio provider's half, as built** (the MacBook lane, 2026-11-27; `game_dev_roblox_studio/console_errors.py`,
the runner's transaction).

| Point | As built | Why |
|---|---|---|
| **The block** | The line before `Stack Begin` is the message, as Studio wrote it, and the first `Script '<path>', Line N[ - function f]` frame after it is where it was raised. No line is keyed on a level | Studio's console tool writes no `Error:`, `Info:` or `Warning:` prefix: 0 of about 580 lines across six stored consoles (2026-11-26), and none in tonight's reads on the Mac |
| **What is skipped** | A block whose message is a failed module load's follow-on (`Requested module experienced an error while loading`), at every step up the require chain; one raised in the command a probe ran (`AssistantCommand`); one with no frame before `Stack End`; an error with no stack; and an engine warning with a stack, `Infinite yield possible on …` | The follow-ons name scripts that only required the faulty one. A warning isn't an error raised (ruled with the Spark lane, 2026-11-26) |
| **What is reported** | The first block whose raising frame is a script the request staged, and only that one. A client script runs as the player's copy (`Players.<player>.PlayerScripts.…`), which is read as the script under `StarterPlayer.StarterPlayerScripts.…`. The script's path in Studio is read back to the staged file it came from (`place.script_files`), and a frame that maps to no staged file isn't reported | Core compares by staged file, so a path it can't hold is never guessed |
| **Redacted** | The message passes through the session's player-name redaction before it is put on the result, as every record and log of the play does | A message names the runtime path, which names the player |
| **This play's lines** | The console is read three times: before play starts, just after, and when the scenario has ended. If the read just after play started begins with the one before, the console wasn't cleared, and this play's lines are what follows it. Otherwise Studio cleared it at the start, and the last read is this play's whole console when it begins with the read just after the start. Anything else, such as a console that rolled past the play's start, is unestablished, and so is a read just after the start that begins with whole lines the read before ended with: a capped console that kept its tail reads like a cleared one, with an earlier play's lines at its start (the Spark lane's review). An empty read just after the start is a cleared console. Only exact prefixes are compared | Read on the Mac on 2026-11-26: Studio clears its console when play starts, and a play's console begins with the game's own start-up lines, which repeat play to play. A match on runs of lines could cut a play's start, where its start-up errors are |
| **Unestablished** | No script error is named and **no `environment`**, so condition 2 fails for that reading on either side | The Spark lane's hardening: a window that can't be read never reads as "looked and found none" |
| **`environment`** | A 16-hex digest of the provider and its reader, the pinned place's baseline digest, the qualified Studio's version, channel and tools, and the harness's digests. Named only on a play whose console window was established | An older worker names none, so its readings are never comparable, and its empty `script_errors` can't make condition 5 hold |
| **`console_window`** | `ran_with` names how the window was read: `cleared`, `appended` or `unestablished` | So a reading with no `environment` says why |
| **A console that can't be read before play** | Nothing is played, and the refusal is the Mac's (`tool_unready`), as a session that won't open is | The window needs the read |

**Its tests** (`tests/unit/remote_execution/test_roblox_studio_console_errors.py`, entered at `RobloxStudioRunner.run`
over the stand-in `StudioMCP`, which now models a console that play's start clears and one that rolls):
- a console that names a staged script's error reports it as the staged file, redacted, and an earlier play's error in
  the edit-mode log is never read as this one's;
- a play with no staged error names none and names its environment, the same for two plays on one pin;
- an error raised outside the staged tree, and each of the five skips, are never reported;
- a console that rolled past the play's start names no error and no environment;
- **end to end:** a baseline play and a candidate play whose setup failed with an error in the file it changed, read as
  core keeps them, hold all six conditions, and the fault is attributed to that file.

Five mutations each fail a test: the errors left off the result, the message unredacted, Studio's path kept, the
edit-mode log read as the play's, and the environment named without a window.

**Not in this amendment.**
- **The played diagnostic** of the plan's item 7 (baseline, attributed failure, repair, the same frozen
  scenarios passing), which needs both halves.
- **A row-8 repair cycle's evidence** (#3272): the Campaign's repair is still sent no script error.

**Who ruled.** The owner adopted the 2.9 plan on 2026-11-26, whose item 7 and ruling D2 state the six
conditions. The Spark lane built the core, and ruled condition 4's reading as said above.

## R5.33 A dedicated worker brings Studio to the front, inside its declared window (#3193, 2026-11-26; R5.18, R5.28, R5.29; the 2.9 plan's item 12, D1, D7, D12)

**What changes.** R5.18 refuses a scenario that acts through Studio's input unless Studio is the app in front, and R5.28 reads that refusal as the worker's own. Both stand. This adds one thing: on a worker its owner has declared dedicated, inside the window its owner has declared, the runner may bring Studio to the front itself, once per operation, before R5.18's refusal. It does so only when every condition below holds at the moment it is read. Anything else, and anything it can't read, is R5.18's refusal as before.

**The conditions.** All of them, each read by the runner, none assumed.

| # | Condition | How it is read | When it doesn't hold |
|---|---|---|---|
| 1 | **The worker is declared dedicated, and the time is inside its declared window** | The worker's own settings: a dedicated flag, the window's start and its end. Each carries a UTC offset. The time is the system clock's, read in the runner. Inside means start ≤ now < end | Refused. A missing flag, start or end is "not dedicated": nothing is defaulted. A start or end without an offset, one that doesn't parse, or an end at or before its start is refused as a setting that can't be read |
| 2 | **The worker holds the operation's lease** | Read from the serving loop's own record of the lease: its last renewal was accepted and its expiry is ahead of the worker's clock. Read explicitly, and never taken from "the runner only runs under a claim" | Refused. A lease the loop can't vouch for is not held |
| 3 | **Nobody has used the Mac for at least the threshold** | The system's idle counter, which needs no permission. The threshold is in the worker's settings, in seconds | Refused. A threshold under 60 seconds is refused as a setting, whatever the counter reads: "dedicated" never means taking the front from someone at the keyboard |
| 4 | **The Mac is unlocked and its session is available** | Read from the system | Refused. A locked screen is never unlocked, dismissed or worked around |
| 5 | **Nobody has touched it since** | The idle counter is read again **immediately before** the activation. It must still be at or over the threshold, and no lower than condition 3's reading. The clock is read again too, and must still be inside the window | Refused. A lower reading means input arrived between the reads |
| 6 | **A proved Studio is already running** | R2.4's and R5.29's checks, which run before this as they do today | Refused as today. The activation never starts Studio |

**The activation.** One call that brings the running Studio to the front, and nothing else. It closes, hides and quits nothing, answers no dialog, and sends no key or click of its own: the only input a play sends is its scenario's. It is tried once per operation. Studio's process ids are read immediately before and after it, and a set that changed is a refusal: the call starts an app that isn't running (the review's change 1).

**Measured** (the MacBook, 2026-11-26, 17:15 ET): bringing a running app forward with `open -a` leaves the idle counter rising. It read 1193.2 s, then 1194.9 s after a 1.7 s activation, so the read after the activation tells a person's input from the activation itself.

**After it.** Two reads, and both must hold before anything is played:
- Studio is the app in front, by the same read R5.18 uses. If it isn't, the result is a refusal; there is no second try.
- The idle counter is read once more. A reading lower than condition 5's means a person arrived during the activation. (The rule's text first held it to the time since condition 5's read; the review of the build held it to the reading itself, which leaves no gap between the two reads and needs no clock.) Then nothing is played and no input is sent. The runner does not move the front again, since it can't know whose it now is.

**Every refusal here is R5.18's:** `not_executed`, flagged `tool_unready` (R5.28). So the increment is retried by rows 10 and 11 and never repaired, and no criterion ever reads failed for it. A read that raises, times out or returns something unexpected is a refusal: there is no path on which an unread condition counts as held.

**The record.** Whenever R5.18's check finds Studio behind, the result's `ran_with` says what happened, on a refusal as on a play:

| Key | Value |
|---|---|
| `front.activated` | `true` or `false` |
| `front.was` | `studio`, `other`, `none` or `unread`. **Never** an app's name, a window's title or anything else about what the person was doing: these records are attached to a public Release |
| `front.idle_s` | The idle counter at condition 5's read, in whole seconds; absent when it wasn't reached |
| `front.refused` | Absent on an activation. Otherwise one of: `not_dedicated`, `window_unreadable`, `outside_window`, `lease_not_held`, `threshold_too_low`, `idle_below_threshold`, `locked`, `session_unavailable`, `input_before_activation`, `outside_window_at_activation`, `activation_failed`, `input_during_activation`, `read_failed` |

The refusal's `reason` says the same in a sentence. It may name the pid in front, as R5.18's does today, and no app.

**What is not added.** No reservation service and no new authority. The window, the flag and the threshold are written by the person who owns the Mac, in the worker's settings. No lane writes them, and code ships with none.

**Who ruled.** The owner, by adopting the 2.9 plan on 2026-11-26 (D1, D7, D12). The text is the Spark lane's; the build is the MacBook lane's.

**As built.**

| Point | As built |
|---|---|
| **The check** | `game_dev_roblox_studio/front.py`: `bring_studio_forward`, a pure function of the app, the declaration, the lease record and the clock. It never raises: every way a read fails is `read_failed` |
| **Where it sits** | `RobloxStudioRunner._transaction`, after the session opens and R2.4 and R5.29 hold the running Studio to its proof, and before anything is synced or played. R5.18's check used to come first; condition 6 needs the proof to come before it. A Studio that isn't running, or isn't the proved one, is refused as before, and no condition is read |
| **The lease** | `squadops.remote_execution.held_lease`: the serving loop's record, set for the one run it starts and kept at every renewal. The claim accepts it, a renewal that doesn't reach the runtime leaves it unaccepted, and a refused one or an expiry ends it. Outside a serving loop there is none, which reads not held |
| **The readings** | `StudioApp.idle_seconds`, `locked` and `session_available`, from `ioreg`, which needs no macOS permission |
| **The activation** | `open -a`, which starts an app that isn't running. Studio's process ids are read immediately before and after: none before, or a different set after, is `activation_failed` |
| **The third read** | Held to condition 5's reading: lower than it is input since |
| **The settings** | Four optional worker settings, `SQUADOPS__WORKER__ROBLOX_STUDIO_DEDICATED`, `_WINDOW_START`, `_WINDOW_END`, `_IDLE_THRESHOLD_S`, read as written and checked at each activation, so a value that can't be read refuses that activation and never stops the worker from serving |
| **A threshold not written, or not a whole number** | Not written is `not_dedicated`, as a missing start or end is. One that isn't a whole number of seconds is `threshold_too_low`, with the reason saying it isn't a whole number of at least 60. The closed list has no reason for an unreadable threshold, and this is the nearest; the Spark lane's review accepted it as built (2026-11-26) |
| **The runbook** | `docs/ops/STUDIO_WORKER_RUNBOOK.md`: how the worker starts and stops, and how its owner declares the window |
| **The proof script** | `scripts/dev/studio_worker_proof.py` builds its runner from the same settings the worker reads, with the four optional ones when written (`worker_settings`), and names an owner for each round (#3282) |
| **Read live** (the MacBook, 2026-11-26, 22:28–22:31 ET, on the requalified Studio, record `edcbf9c1…`) | Through `Worker.serve()` over the real registry, another app in front after the worker's start-up reset, a window of 21 minutes and a 60 s threshold in that run's own environment: `front.activated` `true`, `front.was` `other`, `front.idle_s` `1345`, the play `completed` in 99.2 s with both assertions passed. The run before it, with the four settings not reaching the runner, read `not_executed`, `tool_unready`, `front.refused` `not_dedicated`, `front.was` `other`: R5.18's refusal as before |

**The tests the rule requires**, as the Spark lane wrote them, and where each is:

Entered at the runner's transaction, where R5.18's check sits, with the app, the clock, the idle counter, the lock and the activation as fakes. Each asserts the result's status, `tool_unready`, the `front.*` keys, and **whether the activation was called**. None may end as a failed criterion.

1. **The front lost and recovered:** every condition holds, the activation is called exactly once, Studio reads in front, the scenario plays, and `front.activated` is `true` with `front.was` `other`.
2. **Each condition failing alone,** parametrized, the activation never called, each with its own `front.refused`:
   - no dedicated flag; a flag with no start, and with no end;
   - a start or end with no offset, one that doesn't parse, and an end at or before its start;
   - the time before the start, exactly at the end, and after it;
   - the lease's last renewal refused, and its expiry passed;
   - the idle counter under the threshold; a threshold of 59 with the counter far over it;
   - a locked screen; a session that isn't available.
3. **Each read failing:** the clock, the idle counter (first, second and third read), the lock and the front, each raising in turn. Each is `read_failed`, and nothing is played.
4. **Input between the two reads:** the second idle reading is lower than the first. No activation.
5. **The window closing between the two reads:** inside at condition 1, past the end at condition 5. No activation.
6. **Input during the activation:** the third idle reading is lower than the second (as the review changed it). The activation was called once, nothing is played, no input is sent, and the front is not moved again.
7. **An activation that fails:** the call raises, and separately it returns with Studio still behind. Both read `tool_unready` with `activation_failed`, and the call was made once.
8. **Studio not running, and a Studio that isn't the proved one:** refused as today, with no activation. The second is run twice: after a Studio restart and after a worker restart, so the qualification checks are shown to come first each time.
9. **A scenario with no input action** never reads a condition and never activates: R5.18's scope is unchanged.
10. **`front.was` carries no name:** with a named app in front, the whole result (its `ran_with`, its reason, its evidence) holds neither the app's name nor a window title.
11. **Wiring, from the serving loop:** an operation claimed and then run after its renewal was refused reaches the runner with a lease that reads not held, and no activation is made. This is the test that shows condition 2 is read and not assumed.
12. **A worker with no dedicated setting at all** behaves exactly as today, byte for byte in its refusal's status and flag, with `front.refused` `not_dedicated`.

Mutation checks for the PR's evidence: each condition's check removed in turn must fail a test in 2 or 3 to 6.

**Where each test is:** `tests/unit/remote_execution/test_roblox_studio_front.py`. Tests 1 to 10 and 12 enter at
`RobloxStudioRunner.run` over the stand-in `StudioMCP`; test 11 enters at `Worker.serve()` with the registry in
process. Each of `front.py`'s twelve checks removed in turn fails a test, and so does removing either of
the serving loop's updates to the lease record.

## R5.34 A result the worker builds itself names what its run had established (#3236, 2026-11-26; R5.30, R5.5, R5.29)

**What changed.** R5.30 left one part to the MacBook lane. A worker answers some results itself: the `interrupted`
it sends after stopping a cancelled run, and the one it sends for a tool that raised. Those carried an empty
`ran_with`. So a play cancelled part way named no Studio, no place and no harness, and what had run wasn't on the
record. They now carry what the run had established when it stopped.

**The evidence** (#3236, run on main at `54011a70` on 2026-11-26). `Worker.serve()` ran over the real registry with
`RobloxStudioRunner` over the stand-in `StudioMCP`, and the cycle was cancelled while the setup's click was out.
The proof, the sync and the place's baseline had all been read. The stored result read `interrupted | cancelled
while the operation was running | ran_with {} | evidence 0`.

**The seam**, agreed with the Spark lane on 2026-11-26 before either built it (the 2.9 plan's item 2):

| Point | As built |
|---|---|
| **The port** | `OperationRunnerPort.running_with()`, required, with no default: a copy of the `ran_with` the run in progress has established. A fact goes in only once it has been read, and the copy is empty before a run begins |
| **The serve loop** | Reads it after the run has stopped and before the tool is reset, and puts it on the `interrupted` it builds for a cancel (`_cancelled`) and for a tool that raised (`_result_of`). It adds no key of its own, since the status and the reason say who ended the run. `served_by` stays the registry's, written at acceptance (R5.32) |
| **A tool that can't say** | When `running_with()` raises, the worker still answers. The result carries no `ran_with`, and its reason says why, ending "what it ran with couldn't be read: …" |
| **The Studio runner** | Keeps one record per run, starting fresh at each run and at each reset. The run's own facts go in once the request reads as its own: the provider, the reader, the harness and the source revision. Then each fact is added as it is read: `qualified.*`, `played.*` and `qualified_by` once the running Studio is held to its proof; `place_baseline` after the sync; `play_session` once the scenario has ended. A completed play's `ran_with` is that record, so the record a cancel leaves and the one a return leaves can't disagree. Each attempt at the transaction starts from the run's own facts, so after R5.17's reset nothing read of the Studio the reset quit is carried into the next attempt |
| **The fixture provider** | Its identity (the version and the reader) once a run of its own operation has begun |
| **Not changed** | The runner's own refusals, and the `not_executed` a worker answers for a tool it couldn't reset, since nothing ran |

**The tests.**
- `tests/unit/remote_execution/test_roblox_studio_cancel.py` enters at `Worker.serve()` with the real runner over the
  stand-in. Each case holds the play's own session at one step and cancels its cycle there:
  - before the session opened, the play names the run's own facts and no Studio;
  - after the proof and before the place was found, it names the Studio and no place;
  - at the setup's click, it names the place's baseline and no play session;
  - a play after one that completed names none of the first's facts;
  - a second attempt after a drifted place names none of the first attempt's facts.
- `test_worker_serving.py`: a cancel's and a raise's `interrupted` carry what the run established, read before the
  reset (the harness's reset clears it). A `running_with()` that raises is still answered, and says so.
- `remote_path.py`: a cancelled play's facts reach the requester over the wire.
- Five mutations each fail a test: the loop reading after the reset, the cancel's answer dropping the record, the
  proof recorded before it is read, a run that doesn't start a fresh record, and an attempt that doesn't start from
  the run's facts.

**What remains** (#3236): the live cancel round on real Studio, after the worker is requalified.

**Who ruled.** The owner adopted the 2.9 plan on 2026-11-26, whose item 2 splits #3236 by host. The Spark lane
agreed the seam, and the MacBook lane built it.

## R5.35 An agent's operation is owned by the cycle the runtime holds, and by that cycle's Campaign (#3236, 2026-11-26; R5.30)

**What changed.** R5.30 has every operation name its owner, and has a task's handler name its cycle, "which is
all its context holds". The agent's create route took that name on the body's word. Now it reads the cycle
from the runtime's own record:

| Point | As built | Why |
|---|---|---|
| **A cycle the runtime doesn't hold is refused** | 422 `REMOTE_OPERATION_OWNER_UNKNOWN`, naming the cycle id. Nothing is queued | No cycle's cancel and no Campaign's abort could reach an operation queued under it, so it would run until its requester's wait ran out: the gap R5.30 closed, by another door |
| **The Campaign is the cycle's own** | `origin["campaign_id"]` is written from the cycle's record, over whatever the body said under that key, and removed for a cycle in no Campaign | R5.30 reached an agent's operation from a Campaign's abort only through the cycle's cancel. With the Campaign on the operation, the abort reaches it directly, as it reaches the runtime's own plays. And a body can't put an operation under a Campaign its cycle isn't in, where that Campaign's abort would stop another's work |
| **The handler is unchanged** | It still names its cycle alone (`OperationOwner(context.cycle_id)`) | The route holds the record; the task's context doesn't |

**The evidence.** Recorded on #3236 when R5.30 shipped (PR #3256), as the follow-up its review left: the route
read the owner's shape and never whether the cycle existed.

**The tests** (`tests/unit/api/test_remote_operation_routes.py`) enter at the agent's create: an unknown cycle
refused with nothing for a worker to claim; the cycle's Campaign added, written over a forged one, and left
out for a cycle in none; and a Campaign's `cancel_owned` reaching an operation an agent asked for.

**Who ruled.** The Spark lane, under the owner's grant of 2026-11-26, as a completion of R5.30 inside the 2.9
plan's item 2.

## R5.36 A play reads the place's state twice, at its pin check and after play (#3250, 2026-11-27; R3.6, R5.17, R5.34; the 2.9 plan's item 13)

**What changed.** A play read the place's non-script state three times: at the pin check before the sync, again
after the sync and before play, and after play stopped. The read after play was compared with the read after the
sync. Now the read after the sync is gone. The pin check's own reading is the play's "before", and the read after
play is held to it.

**The evidence** (#3250, comment 7213635288: the before set, 20 plays of the matched scenario on the pin
`edcbf9c1…`, 2026-11-27 02:56–03:30 ET). Median claim to completion was 98.339 s, and the three reads took 67.8 s
of it (`place_state_s` 22.577, `baseline_before_s` 22.610, `baseline_after_s` 22.596). The target is a cut of 20%,
19.67 s. On every play the read after the sync gave the pin's own digest (`place_baseline` `354636ad417cda41`).

**Why the read after the sync could go.** The sync writes only inside the three synced folders, and the state read
leaves their contents out: the scripts' read-back covers them. So that read could see nothing the sync did. It
differed from the pin check only if something else changed the place in the sync's 14 seconds, and the read after
play sees that change too.

**What moves, in both directions** (the Spark lane's review):
- **Stricter.** A change made during the sync and left in place was credited before, since the two later reads
  agreed on it. It is refused now.
- **Looser, in one corner.** A change made during the sync and undone before play ends was refused before. It
  passes now. It takes something acting on the place twice inside one play. That is what is lost.
- **Whose refusal it is, unchanged.** A changed place is `not_executed`, with no `tool_unready`, and read as the
  work's. The window it covers grows by the sync's 14 seconds, so a person or a tool touching Studio during the sync
  now ends as the work's refusal, where before it went unseen. In a dedicated window that is rare, and it fails toward
  not crediting. The reason reads "changed between its pin check and the end of play", with `baseline_changes`'
  list of what changed.

**A place without a synced root.** The state read holds each synced root as a line. The sync creates any missing
folder on a write's path, the root included. So a place lacking a root its scripts go into would read differently
from its pin after every play. So right after the pin check, before anything is written, each synced root the request
writes into, and each folder above it below its service, must have its line in the pin check's reading. A missing
one is `not_executed` with `tool_unready`, naming the folder: it is the place's setup, the Mac's, and is retried,
never repaired. On the product in use every root is there.

**`place_baseline`** is the pin check's own reading, established right after it, never the pinned constant copied in.
So a play cancelled during the sync names it now (R5.34), which is earlier than before.

**`stages.json`** carries no `baseline_before_s`: a stage that didn't run is absent (amendment 13a's point 1).

**The tests** (`tests/unit/remote_execution/test_roblox_studio_state_reads.py`, entered at `RobloxStudioRunner.run`
over the stand-in, whose sync can now change the state, `baseline_after_sync`):
- a change made while the sync ran, and left in place, is refused as the work's, naming the window and the change;
- a play reads the state twice and records the pin check's own digest;
- a place without the synced root its scripts go into is refused by name, with nothing synced.

Each fails on main's runner before this change: the change is credited, the state is read three times, and the
rootless place plays. A play cancelled during the sync names `place_baseline`
(`test_roblox_studio_cancel.py`). The changes through play and the drift before the sync are refused as before, by
their existing tests.

**Who ruled.** The two lanes, under the owner's grant of 2026-11-26 for the 2.9 line: the Spark lane froze the
matched set and read the design, and the MacBook lane built it. It narrows no done-when and changes no claim.

## R5.37 The checks that guard a person hold for every input play, not only for an activation (#3300, 2026-11-27; R5.18, R5.28, R5.29, R5.33; the 2.9 plan's D14)

**What changed.** R5.33 read its conditions only when Studio was behind and the runner meant to bring it forward.
When Studio was already in front, nothing was read: not the lock, not the idle counter, not the console session,
not the lease. After the worker's start-up reset, Studio is in front, so that was the common path. And nothing was
read after the checks, so a person who arrived, or a screen that locked, during a play didn't stop its input.
R5.33's guarantee was a guarantee about the activation; what the person needs is a guarantee about the input.
This rule moves the checks from the activation to the input. R5.33's conditions, its activation and its record
stand, except where a point below changes them.

**The evidence.** The outside review of #3269 (D14, read 2026-11-27), each finding confirmed by the Spark lane in
the code at `8e586529` before it was written here:
- `RobloxStudioRunner._in_front` returns as soon as Studio is in front, before any condition is read
  (`runner.py:573-575`);
- the activation is `open -a`, which starts an app that isn't running (`studio_app.py:183`). The read after it
  refuses the play, but the launch has happened;
- a failed read of the front became a reason, and `bring_studio_forward` was then called with a second read;
- the lease was read once, before the activation;
- `session_available_in` asked whether any session was on the console and whether any session had finished logging
  in (`studio_app.py:206`), which two different sessions can answer;
- a play with Studio already in front carried no `front.*` key.

**The rule.**

1. **Every play with an input action reads the conditions, whether or not Studio is in front.**
   - *On a dedicated worker:* R5.33's conditions 1 to 5 are read in their order for every play whose scenario has
     an input action (`click_gui`, `hold_key`, `move_to`). The conditions are the window, the lease, the idle
     counter, the lock and the session, then the idle counter again. Studio already in front skips the activation,
     and only the activation.
   - *On a worker that isn't dedicated:* R5.18 is unchanged, except that the lock and the console session are read
     for every input play. A locked screen is never played on, dedicated or not. The idle counter isn't held to a
     threshold there, because a worker that isn't dedicated runs attended by its definition.
2. **The front is read once, with four outcomes:** Studio, another app, none, or a read that failed. A failed read
   refuses with `read_failed`, and nothing after it is read. No later read authorizes a play that an earlier read
   couldn't.
3. **The activation can't start an app.** It brings forward the running Studio that R2.4 and R5.29 proved, by that
   process's id, through a call that acts on a running process and has no path that launches one. Studio's process
   ids are still read before and after it, and a changed set still refuses. *If no such call exists on the Mac
   without a change to its settings or permissions* (the owner's standing ruling: no host setting beyond the
   worker's own), the activation stays `open -a` with the reads either side. R5.33's "the activation never starts
   Studio" then reads "an activation that started Studio is refused", and the cut record says so. The MacBook lane
   reports which, and the as-built table below names it.
4. **Authority is read again before input.** Immediately before the first input action, after the activation or
   after the already-in-front check, the lease and the window are read again. Either one not holding refuses, as
   condition 2 or 1 refuses. The activation's own call is bounded by the lease's remaining time, and a cancel that
   arrives during it is the cancel's (R5.30), never an activation's refusal.
5. **The console session is read entry by entry.** The system's list of console users is read as entries. The
   session is available only when exactly one entry is on the console and that same entry has finished logging in.
   No entry, two on the console, or a contradiction within one entry is `session_unavailable`.
6. **During the play.** Immediately before each input action after the first, the lock and the idle counter are
   read. A locked screen stops the play: nothing more is sent, and the result is `not_executed` with `tool_unready`
   and `front.refused` `locked_during_play`. A counter lower than the runner's previous reading means a person's
   input, and stops the play the same way, with `input_during_play`.
   - *What this needs first:* the scenario's own input mustn't move the counter. The MacBook lane measures whether
     a `click_gui` and a `hold_key` reset macOS's idle counter. If they don't, the rule is as written. If they do,
     only the lock is read during the play, input during a play is not detected, and the cut record says so. The
     measurement goes in the as-built table either way.
   - *A held key* is read before the hold starts and as soon as it ends. A person arriving during a hold is seen at
     its end, at most the hold's length later (20 s in the window's scenarios), and nothing after it is sent.
   - *What a stop is:* the assertions already read are not evidence. A play stopped by either reading is the
     worker's refusal, retried by rows 10 and 11 (R5.28), and never a criterion read as failed.
7. **Every input play records why it was allowed.** `ran_with` carries the `front.*` keys on every play with an
   input action, not only when Studio was behind:
   - `front.input`, either `permitted` or `refused`;
   - `front.activated`, which is `false` when Studio was already in front;
   - `front.was`;
   - `front.idle_s`, on a dedicated worker;
   - `front.refused`, on a refusal.

   The closed list of refusals gains `locked_during_play`, `input_during_play` and, from point 4,
   `lease_not_held_before_input` and `outside_window_before_input`. Still no app's name, window title or anything
   about what the person was doing.

**What is not added.** No new authority, no new setting, and no change to the scenario vocabulary. The four
settings are still the owner's to write.

**Who ruled.** The owner, on 2026-11-27, on the outside review and the Spark lane's assessment of it: "Yes, go
ahead with the fixes and 13f." The text is the Spark lane's, written before the build, so the lane that takes the
front doesn't write its own safety rule. The build is the MacBook lane's.

**The tests the rule requires,** entered at `RobloxStudioRunner.run` over the stand-in, with the app, clock,
counter, lock, session and activation as fakes. Each asserts the status, `tool_unready`, the `front.*` keys,
whether the activation was called and whether any input was sent:

1. Studio already in front with the screen locked: no input, `locked`.
2. Studio already in front with the counter under the threshold: no input, `idle_below_threshold`.
3. Studio already in front, idle, unlocked, inside the window: the play runs, `front.input` `permitted`,
   `front.activated` `false`.
4. The counter dropping between the activation and the first input action: no input, `input_before_activation`
   (the check before input re-reads it).
5. A lock read before the second input action: the first action was sent, the second wasn't, `locked_during_play`.
6. The lock or the session unreadable, with Studio in front: `read_failed`, no input.
7. A worker that isn't dedicated, Studio in front, the screen locked: no input, `locked`. And the same worker
   unlocked: the play runs as today.
8. A failure injected into the first front read: `read_failed`, no activation, no input, and no second read.
9. Studio gone before the activation: no launch call made. The process set changing during it: refused. Studio
   running: exactly one activation call. An activation that fails: no retry and no other call.
10. Two Studios running: only the proved one is brought forward, or the play is refused.
11. The lease's expiry passing during the activation, and the window closing during it: refused before input with
    point 4's refusal. A cancel during the activation: the cancel's `interrupted`.
12. A synthetic console-user list with two users, one on the console and the other logged in: `session_unavailable`.
13. Wiring, through `Worker.serve()` with the registry in process: a play claimed with Studio already in front and
    the screen locked sends no input and is answered `tool_unready`.
14. If point 6's measurement shows the counter is moved by the scenario's own input: a test that the counter isn't
    read during the play, so the play can't refuse itself.

Each check removed in turn fails a test.

**R5.37 as built** (the MacBook lane, 2026-11-27; PR #PRNUM, closing #3300). The two readings the rule asked for, both
taken by hand on the MacBook with the worker stopped and nothing claimed, on Studio 0.748.0.7481526 and Darwin 25.5,
with the owner's go-ahead in the MacBook session:

| Point | Reading | So |
|---|---|---|
| 3, the activation | 12:57–12:58 ET. Three rounds of another app brought to the front, then `MacStudioApp.activate(pid)`: AppKit's `NSRunningApplication.runningApplicationWithProcessIdentifier(pid).activateWithOptions(…)` through `osascript -l JavaScript`. Each answered in 0.06–0.09 s with Studio's process the same before and after and the proved Studio read in front. No prompt, and no setting or permission changed. A process id that isn't running answered `gone`, and no Studio started | **Built as written.** The activation acts on the running process and has no path that launches one; `open -a` is no longer called to bring Studio forward |
| 6, the idle counter | 12:58–13:00 ET. A hand play of the qualification setup (its `click_gui`) then a 10 s `hold_key`, with macOS's idle counter sampled every 0.25 s: 190 samples over 88 s, rising from 152.7 s to 240.9 s and never lower than the sample before. The activation rounds above didn't move it either | **Built as written.** The counter is the person's alone, so it is read during the play, `input_during_play` is detected, and test 14's conditional branch fell away |

**What the build settled where the rule left it open:**
- **A worker that isn't dedicated reads only the lock during the play,** as well as the lock and the session before
  it. It holds no idle threshold (point 1), so its counter isn't read at all.
- **The lock is read before the first input action too,** not only before each one after it.
- **Point 4's read is one read,** immediately before the first input action, after the activation or the in-front
  check: the lease, the window and the idle counter. A counter lower there than the check's last reading is
  `input_before_activation` (test 4).
- **The proved Studio** is the one process running when the proof read Studio's channel (which reads exactly one).
  Two, none, or a read that fails is no proved process, so nothing is brought forward, and another Studio in front
  reads as another app.
- **Off the serving loop's event loop.** The runner runs on the serving loop's own loop
  (`serving.Worker._serve_claim`: `asyncio.ensure_future(self._runner.run(request))`), and every read here is a
  process the Mac answers. So the check and each read around an input action run through `asyncio.to_thread`, and
  the lease goes on renewing during them. A cancel during the activation is the cancel's: the run raises
  `CancelledError`, and nothing after it is sent (test 11).
- **The activation's own call** is bounded by the lease's time left, at most 30 s, and isn't made with under a
  second of it left (`lease_not_held`).

**The tests** are R5.37's, numbered as the rule numbers them, in `tests/unit/remote_execution/test_roblox_studio_front.py`:
1 to 12 at `RobloxStudioRunner.run`, 13 through `Worker.serve()`, and in test 14's place an `input_during_play` test
whose held key is the scenario's last input. R5.33's conditions, each failing alone, run with Studio behind and
with it in front. **Mutations,** each check removed in turn, all failing a test (16): the conditions skipped with
Studio in front; no lock or session on a worker that isn't dedicated; a failed front read going on; any Studio taken
for the proved one; the proved process unchecked; the process set not compared after; the timeout unbounded; no
floor on the lease left; the guard skipping the lease and window; the guard reading no lock; no counter during the
play; a held key's end not read; the runner passing no guard; any session's "on the console" paired with any's
"logged in"; a contradictory entry read as available; no record with Studio in front.

# R4. Revision 4 (2026-11-09): Roblox as skillsets, a provider and a development profile

**What prompted it.** SIP-0116, Agent Skillsets, was accepted on 2026-11-09. The owner split it from Capability-Backed
Agents after revision 3's *specialty* turned out to rebuild that SIP's assembly rules beside the stack and
development-profile seams. SIP-0116 names this SIP as its first consumer and leaves three things to this revision:
- the engine operations as a provider's implementations of engine-neutral capability contracts, each with a
  verification mode (its §6.1 and §6.2);
- the proposal for `qa.run_remote_operation` as a plannable task type (its §6.3);
- the worker registry its `worker` tool location relies on (its §8).

**Where §R3, §R2 or the body differs, this section governs.** They're kept as the record of what was proposed.

**The rule: the development profile requires, the selected agents supply, and the provider executes.**

**What stands from revision 3, unchanged:**
- the remote-execution contract (R3.3);
- Roblox as proven, and the Studio transaction (R3.6);
- the assertion protocol (R3.7);
- the product and publishing (R3.8);
- the owner's decisions D2–D5, D9 and D10. D7 and D8 are read as R4.4 and R4.8 say.

## R4.1 What takes the specialty's place

Revision 3 gathered Roblox integration into one unit, the `game-dev-roblox` specialty. Revision 4 has no such unit.
Each of its parts is a declaration in a seam that owns it:

| revision 3 | revision 4 | owned by |
|---|---|---|
| the specialty and the bootstrap's specialty table | four kinds of declared thing: the `game_dev_roblox` development profile, the skillsets `roblox-increment-design`, `roblox-luau-dev` and `roblox-studio-qa` (the companion's R4.3), the `roblox-studio` provider, and a squad profile whose agents carry the skillsets | SIP-0072 and SIP-0116 §5.1; SIP-0116 §4; this SIP (R4.2); SIP-0075 and SIP-0116 §5.2 |
| the squad profile's `specialties` field | each agent's `skillsets` field. Selecting the stack equips no one | SIP-0116 §5.2 |
| the core package `src/squadops/specialties/game_dev_roblox/` | not built. The skillsets are directories under `src/squadops/prompts/skillsets/`, the game contracts are declarations in `squadops.capabilities`, and the development profile is data in `squadops.stacks` | SIP-0116 §4.2 and §6.1; the companion's R4.2 |
| *playbooks* | skills: `SKILL.md` files inside the skillsets. *Playbook* is kept for what a squad follows | SIP-0116 §7 |
| fragments under `prompts/fragments/game-dev-roblox/` | the skills, and the development profile's own text fields | SIP-0116 §7 (Q54) |
| an operation id named in a plan (`game-dev-roblox.play_scenario`) | a plan names a contract and a mode. The provider maps them to its operation (R4.3) | SIP-0116 §6.1 |
| the specialty's digest in the profile snapshot hash, re-resolved by every cycle | the skillset record beside the roster hash, the kept copy of skill content, and the Campaign's pin with its recorded transition | SIP-0116 §10 |
| preflight against the resolved specialty | the coverage, declaration, authorization and availability outcomes at creation, and the plan gate's check on the routed agent | SIP-0116 §9 |
| the trigger for plugin machinery (R3.1) | a capability pack, in 3.x, carries the skillset directories unchanged and adds the provider's packaging | SIP-0116 §4.3 and §11 |

## R4.2 The provider, which is what this SIP owns

- **`roblox-studio` is the execution provider.** Its adapter is `adapters/remote_execution/game_dev_roblox_studio/`,
  behind `ports/remote_execution/`. It owns the Studio transaction, the harness, its operations and their result
  readers, the deny list and its compatibility checks (R3.6). It runs on a registered worker.
- **`lune` is the headless provider:** the Luau runner in the QA container (#2906). A language is core, as R3.2 says.
- **A skillset names providers; it holds none.** `roblox-studio-qa` lists both under `prerequisites` and requests
  `roblox-studio`'s operation under `tools`, at the `worker` location. The worker registry of R3.3 says which worker
  serves a provider.
- **R2.1's table stands,** with "a provider and the skillsets that use it" in place of "an engine integration
  plugin". Core runs operations, and a provider declares them and reads their results.
- **No engine name in core** (R3.2 stands). The game contracts are engine-neutral, and orchestration reads `TaskType`
  properties and the cycle's skillset record.

## R4.3 Operations implement contracts

The companion defines the game contracts once (its R4.2). Roblox's providers implement them:

| contract | task type | mode | provider and operation | basis |
|---|---|---|---|---|
| `game.increment_design` | `strategy.propose_increment` | none | none: an authored change request, whose play scenarios the harness reads | R3.7 |
| `game.gameplay_implementation` | `development.develop` | none | none: authored source | S6 |
| `game.unit_tests` | `qa.test` | `headless` | `lune`: the `luau` runner kind, with the skillset's test loader | S2: the game's modules need the loader; phase 2c |
| `game.scenario_verification` | `qa.run_remote_operation` | `play` | `roblox-studio`: `play_scenario` | S1: play, input and read-back proven |

- **A plan never names an operation id.** It names the contract and the mode. The handler reads the cycle's skillset
  record for the supplying skillset, takes that skillset's tool request, and resolves it in the provider's operation
  table: the argument schema, the required worker capability and the result reader.
- **Refusals:** a contract or mode the cycle's requirements don't name is refused at the plan gate (SIP-0116 §9). A
  duplicate operation registration is refused at bootstrap.
- **An operation is qualified by its provider,** so R3.6's ids drop the `game-dev-roblox.` prefix: `play_scenario`,
  `sync_source`, `read_console` and `capture`, of `roblox-studio`.
- **Three of the four run inside the transaction.** `play_scenario` is the whole transaction for one frozen scenario.
  It uses `sync_source` before play, `read_console` to collect the session's records, and `capture` for
  supplementary evidence. None of those three is planned by itself in the first milestone.

## R4.4 `qa.run_remote_operation`, the first new plannable type

SIP-0116 §6.3 makes each new plannable type its own proposal and names this one as the first. The proposal:

| part | what it is |
|---|---|
| the type | a member of the central enum, served by the `qa` role. It carries a contract, a mode and its frozen inputs by artifact reference |
| planning | `plannable`, and outside `base@1`. It's offered only where a cycle's requirements name a contract over it and the routed QA agent supplies that contract. A cycle on any existing stack is offered today's types |
| the handler | engine-neutral. It requests the tool, stages inputs from the vault, waits for the fenced result and passes it to the provider's reader |
| expected artifacts | the assertion records of R3.7, and the evidence bundle: the console, the source manifest, the baseline digests, and the provider, worker and tool versions |
| footprint | it authors no source. An edit made in the editor returns as a new revision through `apply_workspace_patch` (R3.6) |
| correction mapping | an executed failure in the application routes to the dev repair, which loads the dev skillset's skills by lineage (SIP-0116 §7.1). `not_executed` and `interrupted` route to no repair, and the run reads `blocked_unverified`. A re-run after a repair is an operation and loads no skills |
| verifier seams | the PR that builds it carries the table CLAUDE.md's "Typed checks" asks for: each seam that evaluates the task's criteria, the tree it sees, and its outcome when the worker's evidence is absent |
| the wire | it carries 2.7's dispatch identity (#2932) |

- **D7 stands, read this way:** the operation ids are the provider's, and "planning made property-driven" is
  SIP-0116's `plannable` property and offered set, built in its phase 2. `_KNOWN_BUILD_TASK_TYPES` becomes derived
  from the base set there.
- **It's proved with a fixture provider first,** with no Studio and no worker (phase 2a).

## R4.5 Verification modes

R2.4's modes take SIP-0116 §6.2's names, a closed list: `build` (R2.4's static / build), `headless` (new, Q67),
`editor`, `play` (runtime / play), `multiplayer` and `capture` (graphical capture). **Supporting one mode implies no
other.** R2.4's rule stands: a check that didn't run reads not executed.

| mode | Roblox, on the evidence | declared by `roblox-studio-qa` in the first milestone |
|---|---|---|
| `build` | S2 built a place with Rojo, and all 137 files mapped. No check reads a build result, and no build runs on the worker | no |
| `headless` | Lune runs pure-Luau tests (the 2.6 spike). The game's instance-tree requires need the loader (S2) | **yes,** for `game.unit_tests` |
| `editor` | proven in S1: `execute_luau` in the edit place reads and writes scripts and instances. The transaction uses it for sync and read-back | no: no contract in the first milestone runs in it |
| `play` | proven in S1, unattended, with input | **yes,** for `game.scenario_verification` |
| `multiplayer` | not proven | no |
| `capture` | works in S1, as supplementary evidence | no: no criterion depends on it |

- **A profile can require only a mode a skillset declares.** So a requirement for an undeclared mode is refused at
  creation as a declaration outcome, and nothing unproven reads as passing.
- **SIP-0116's Appendix A lists what the platform can support** (`headless`, `editor`, `play`, `capture`). This table
  is what the first skillset declares. A later contract that needs `editor` or `capture` adds the mode with its
  proof. Appendix A's "a Rojo build isn't proven" reads as this table's `build` row: S2 built a place, and `build`
  as a verification mode is unproven.
- **R2.4's Godot and Unity columns** stand as claims to prove, under the new names. Unity's EditMode tests are
  `editor`, and its PlayMode and built-player tests are `play` (R2.5 keeps the three apart as separate operations).

## R4.6 The guarantees, and what holds the boundary

R3.4's guarantees are kept, and SIP-0116 now supplies them:
- **Checked at creation and at the plan gate** (its §9), on the agent each responsibility routes to.
- **Recorded and held** (its §10): the skillset record, the kept copy of skill content, and the Campaign's pin. A
  change to the equipment assigned to a Campaign's work stops its next launch with the changed parts named.
- **Provider and reader code can't be kept with a cycle.** So the worker registers its provider version, its Studio
  version and the digest of its tool schemas, and each operation's evidence records them. An operation is pinned to
  what it was proved on and reads `not_executed` on a mismatch. A resume after a redeploy names the change of deploy
  in the record (SIP-0116 §10).
- **The product's eligibility rules (R3.8) are the provider's compatibility checks.** SIP-0116 §8 checks each tool
  request against them at creation. A product that fails one is refused as an authorization outcome, naming the tool
  and the rule.
- **The development profile is selected explicitly** (Q58). A Luau runner in the product's derived profile never
  selects `game_dev_roblox` and never implies Studio. Which field carries the selection for a Campaign is settled
  with SIP-0112, by its amendment in the PR that builds it.

**The isolation test** (R3.1's, re-cut) holds the boundary:
- a platform's or provider's name appears only in the skillset directories, the development profile's entry, the
  squad profiles, the adapter directory and the worker root's configuration section;
- the adapter imports only its port and an allowed list. That list is the first draft of the interface a capability
  pack's provider will be written against.

## R4.7 Delivery

**The dependency order** replaces R3.9's:
1. SIP-0116's phases 1 and 2: the declarations, the record and coverage (its ledger);
2. phase 2a: `qa.run_remote_operation` (R4.4) and the companion's game contracts, proved with a fixture provider;
3. phase 2b: remote execution. SIP-0116's phase 4 (tools) builds with its worker registry;
4. phases 2c–2e: the Luau runner, the Studio adapter and the assertion harness;
5. SIP-0116's phases 3, 5 and 6: skills, the Campaign's pin and lessons;
6. phase 2f: the companion's squad. The `game_dev_roblox` profile's requirements are switched on only after
   SIP-0116's phases 2–6 have shipped;
7. phase 3: the demonstration.

The ledger is re-cut to match. Godot, Unity and GameBench-01 are unchanged, each after Roblox.

**R2.10's two definitions of done stand:** "engine integration works" is this SIP's, for phases 2a–2e, and "the squad
can build and improve a playable game" is the companion's.

## R4.8 Decisions and questions

The plan's D1–D10 stand as the owner accepted them on 2026-11-08. Two are read against SIP-0116:

| # | decision | in revision 4 |
|---|---|---|
| D7 | one engine-neutral task type with operation ids; planning property-driven | stands. The type is R4.4's. The operation ids are the provider's, and a plan names a contract and mode. The property is SIP-0116's `plannable` |
| D8 | `game-dev-<engine>` naming for specialty identifiers | stands for the development profile (`game_dev_roblox`), the squad profiles, the adapter directory, the plans, the branches and the issue label. Skillset and provider ids are in SIP-0116's platform-first form (`roblox-increment-design`, `roblox-luau-dev`, `roblox-studio-qa`; `roblox-studio`, `lune`), by **Q68** |

**Q68, ruled by the owner on 2026-11-09 ("approve as recommended"):** skillset ids keep SIP-0116's platform-first
form, and the Roblox dev skillset is `roblox-luau-dev`, so that every Roblox skillset sorts together. D8 named the
*specialty's* identifiers for that purpose, before skillset ids existed. SIP-0116's examples write the id as
`luau-dev`; they're marked illustrative, and its §17b records the name.

**Ruled the same day, with the same words,** revision 4's design calls:
- the product's eligibility rules are the provider's compatibility checks, refused at creation as an authorization
  outcome (R4.6);
- the first Roblox skillset declares `headless` and `play` only (R4.5);
- the companion's fourth contract, `game.increment_design`, with a strategy skillset, and its builder with no step in
  the first milestone (its R4.2).

**Accepted by the owner on 2026-11-10** ("accept 2405 then 2841"), as SIP-0117, with the companion accepted after it.

---

# R3. Revision 3 (2026-11-08): an in-tree specialty, and what the spikes proved

**What prompted it.** The owner asked for game development proved without building a plugin architecture first,
and without closing the door on other specialists such as a designer. The game-dev-roblox plan
(`docs/plans/game-dev-roblox-plan.md`, PR #2972) is that design. Its spikes ran on 2026-11-08 against a private copy
of Tower Ascension, its gate came out go, and **the owner accepted its decisions D1–D10 the same day** ("accept
D1-D10, write revision 3"). **Where §R2 or the body differs, this section governs, and §R4 governs all three.** §R2
and the body are kept as the record of what was proposed. Its *specialty* and *playbooks* are superseded by §R4.

**The boundary with the companion is unchanged:** this SIP is how an engine is integrated, and the companion is how
a squad uses it. What changes is the mechanism both register through.

## R3.1 The specialty, in-tree, with a boundary shaped like a plugin

- **The plugin machinery waits for a trigger.** That means discovery, installation, external packaging, the
  manifest validated without running plugin code, a versioned SPI and the plugin lifecycle (R2.3). It's built when:
  - a second specialty duplicates the bootstrap wiring;
  - or a specialty must ship on its own cadence;
  - or someone outside the team writes one;
  - or a second specialty needs task types of its own. Then the host-owned task-type lookup is the first piece to
    build (the companion's designer test).
- **Until then, Roblox integration is the `game-dev-roblox` specialty,** built in-tree on seams that already exist:

  | need | the existing seam |
  |---|---|
  | route a step to a role | the handler registry and the squad profile's `serves_roles` |
  | a roster and its models | a squad profile |
  | prompt text | PromptService fragments, under a directory of the specialty's name |
  | treat game steps differently | `TaskType` properties and lookup tables, never a check on an engine's name |
  | evidence | SIP-0096's executed-passed, executed-failed and not executed |
  | I/O | a port, an adapter behind it, and a composition root that binds it |

- **The extraction boundary is four named places:**
  - the core package (`src/squadops/specialties/game_dev_roblox/`);
  - the adapter (`adapters/remote_execution/game_dev_roblox_studio/`);
  - the fragments (`src/squadops/prompts/fragments/game-dev-roblox/`);
  - the worker root's configuration section.

  An isolation test holds them: only the bootstrap's specialty table and the worker's composition root reach in,
  and the specialty imports core only from an allowed list. **That list is the plugin interface's first draft,**
  written from what the specialty actually uses.
- **Naming:** every engine-specific identifier is `game-dev-<engine>` (`game-dev-unity` would be next), and shared
  execution infrastructure keeps generic names (`ports/remote_execution/`, `/api/v1/workers`).

## R3.2 What core owns, and what the specialty owns

R2.1's table stands with "the specialty" in place of "an engine integration plugin", and two refinements:
- **A language is core, an engine is a specialty.** The Luau runner (#2906) is a language in the derived profile,
  like Python or JavaScript. Studio, play sessions and the place are `game-dev-roblox`.
- **No engine name in core.** Orchestration consults `TaskType` properties and tables (CLAUDE.md's task-type rules
  3 and 4). Engine specifics stay behind operation ids (R3.5).

## R3.3 The remote-execution contract, specified (R2.2 kept)

- **The worker connects outward.** Studio has no Linux build, and its MCP server is reached only through a local
  stdio proxy, so the squad on the Spark reaches Studio through a worker on the MacBook. **The body's inbound
  SSH transport (§5.4, FR-06, §9.2) is replaced:** the worker connects outward to the runtime API over Tailscale, so
  no port opens on the MacBook. The spike proved the path (S4: `/health` in 14 ms, no credentials).
- **Delivery is pull, claim and result:**

  | step | what happens |
  |---|---|
  | register | the worker session registers its identity, platform, tool versions and the operations it serves |
  | claim | at most one assignment, with an assignment id, an attempt number, a lease id and an expiry |
  | heartbeat | renews the lease while the transaction runs |
  | result | fenced by assignment, attempt, worker-session and lease ids. A result whose ids aren't current is refused and recorded, so a late completion never satisfies a newer attempt |
  | cancel | seen at the next heartbeat; the worker stops, resets and submits `interrupted` |
  | expiry | frees the assignment for a new attempt; the next claim on that worker begins with reconcile-and-reset |

- **It reuses 2.7's contracts:**
  - #2932's echo convention for fencing, with a durable token of its own, because a lease outlives a runtime
    restart;
  - the vault's `store()` with #2931's durability for the worker's evidence.
- **`not_executed` and `interrupted` are kept apart,** before and after the play session starts, and neither reads
  as a failure or a pass.
- **The worker's authority is the assignment's:** it reads only its inputs, writes only its result and evidence,
  and has a service account scoped to those calls (D3).
- **Health** is the canonical vocabulary, with *busy* as a lease (R2.2 and Q38 stand).

## R3.4 Registration, deferred (R2.3), and the guarantees kept without it

R2.3's manifest, `requires_spi` and provider pins wait for the trigger (R3.1). The runtime guarantees they gave
are kept another way:
- **Resolved once, pinned for the Campaign:** at creation, the squad profile's `specialties` field resolves to the
  specialty's declaration, operations, handlers, readers, playbooks and permissions. Its digest enters the profile
  snapshot hash (`compute_profile_snapshot_hash`, stamped as each cycle's `squad_profile_snapshot_ref`). SIP-0110's
  `rebind` event is the precedent for a recorded re-binding.
- **Detected, since in-tree code can't be replayed:** every cycle re-resolves and compares digests. A difference
  stops the Campaign with a named reason.
- **Preflight at creation:** the specialty resolves, its operations name a registered worker that serves them, and
  the product meets its eligibility rules. **At the plan gate:** every task and operation in the plan is one the
  resolved specialty serves.
- **The provider and reader pins become the specialty's digest,** recorded in the evidence.

## R3.5 Task types and planning

- **One engine-neutral task type, `qa.run_remote_operation`,** a member of the central enum, carries an operation
  id (`game-dev-roblox.play_scenario`) as its argument. The enum's properties, routing and correction tables work
  unchanged. Code is written and repaired by `development.develop` and `development.repair`, with the specialty's
  context. A specialty enum was rejected: `task_types._member_or_none` reads any value outside the central enum as
  `None`, so its types would read `False` on every property, silently.
- **The operation id resolves through the specialty table:** argument schema, provider, required worker
  capability and result reader. An unknown id is refused at the plan gate, and a duplicate at bootstrap.
- **Planning becomes property-driven.** Today the planner offers, and the plan parser accepts, a fixed set of three
  task types (`_KNOWN_BUILD_TASK_TYPES` in `cycles/implementation_plan.py`), so `qa.run_remote_operation` couldn't
  reach a plan. A `TaskType` property marks the plannable types instead, and the prompt's list and the parser's
  check read it. **Scope (agreed 2026-11-08):** set on today's three and `qa.run_remote_operation` only. Every
  further plannable type is its own proposal, with its handler, expected artifacts, footprint rules, correction
  mapping and verifier seams.

## R3.6 Roblox, as proven (R2.4's Roblox column, R2.6 and R2.7)

**The spike (S1) ran against Studio's MCP server through its stdio proxy, on a local copy of the game.**

| mode (R2.4) | Roblox, after S1 |
|---|---|
| static / build | **a Rojo build proven** (S2): one sync rule gives `.local.luau` the `LocalScript` class Studio assigns, and all 137 files map. Luau analysis isn't proven |
| editor | **proven through MCP's `execute_luau` in the edit place,** which reads and writes scripts and instances. **It replaces the body's Studio command-line `RunScript` (FR-10, §9.3),** which nothing tested and the plan doesn't use |
| runtime / play | **proven, unattended,** including with Studio behind other windows. The server and client are each scriptable, and input works: a click on a UI element by instance path, held keys, and character navigation (to within 0.7 studs) |
| multiplayer | **not proven, and not in the plan** |
| graphical capture | **works, as supplementary evidence only.** No criterion depends on it |

**The tool facts the adapter is built on:**
- **38 tools.** Some write to Roblox's servers: `open_cloud_invoke`, `upload_image`, `insert_asset`, `create_skill`,
  `edit_skill` and the `generate_*` family. The deny-by-default allow-list refuses them.
- **`execute_luau` takes a required `datamodel_type`:** `Edit`, or `Server` or `Client` during play.
- **A result is capped at 100,000 characters** and reports success when truncated, so readers page and refuse a
  truncated page.
- **A blocking call has no timeout** (`PreloadAsync` hung the tool twice), so every call has a deadline and the
  harness makes no unbounded blocking call.
- **`_G` persists between calls,** so the harness clears its own state.
- **A restarted Studio has a new id,** so the worker confirms Studio by identity (R3.6's bindings), not by id.

**The transaction (strengthens R2.6 and R2.7):**
- **The lease covers the whole transaction:** stage → sync → verify the tested state → play → collect → stop and
  reset.
- **Bound to:** the Studio confirmed by `PlaceId` 0 and its baseline digest, the place file and its baseline file,
  the source manifest (path, digest and class per script), and the scenario's digest.
- **The adapter owns sync (D10).** It writes the manifest's scripts into Studio through a fixed harness program,
  with the class from the repository's mapping, and removes what the manifest drops. **The worker's Studio has no
  Script Sync link:** S1 found that links on a local place are lost on every Studio restart, and that a live link
  writes Studio's edits straight to disk. Script Sync stays the game owners' own workflow.
- **The tested state is confirmed inside Studio:** every script read back (137 scripts, about 1.7 MB, in 1.6 s),
  and the non-script baseline digested in full before play and after stop (22,840 instances in 7.0 s; it caught a
  part moved 0.01 studs). The baseline covers a stated property set, not every property.
- **Reset:** play state resets on stop. The edit place resets from a read-only baseline file. Reopening Studio on
  that file without a person is phase 2d's to prove; until then a mismatch reads not executed.
- **Editor changes return as a revision (R2.7 kept):** with no Script Sync link, an edit made in Studio is found at
  read-back and returned as a file, through `apply_workspace_patch`, as revision B. A pass on A never accepts B, and
  a script that changes during a QA transaction fails it.
- **Typed operations:** `game-dev-roblox.sync_source`, `.play_scenario`, `.read_console` and `.capture`.
  `execute_luau` runs only the harness's fixed programs (sync, read-back, baseline and the frozen scenario).

## R3.7 The assertion protocol

- **Frozen before development:** the scenario, its fixtures, the expected outcomes and the reader, each by digest.
- **The harness** emits one structured record per assertion (its id, the observed and expected values, the result,
  the server or client context, the play-session id and the source revision). The reader reads only those
  records. Console prose never establishes a pass.
- **Outcomes kept apart:** `passed` and `failed` (executed), `missing`, `setup_failed`, `unsupported_input` and
  `wrong_context`. Only `failed` is an executed behavioural failure.
- **S1 showed the channel:** a structured line printed by the server came back through the console with its nonce.
  A game that opens on a title screen passes it in every scenario's setup.

## R3.8 The product, and publishing

- **The first game is a private copy:** `backspring-labs/z_tower-ascension`. Its integrations were swept: the
  Discord update-log workflow and two asset-upload scripts were removed.
- **Its place is a local, disconnected file (D2), not a test universe.** `PlaceId` reads 0, the game turns saving
  off without DataStore access, and the read-only baseline file is the reset point. Assets load under the owner's
  Studio login. **This replaces revision 2's test universe and place.**
- **Publishing is out of the first milestone.** FR-04's Open Cloud publishing and FR-14 stand as the design for a
  later milestone, with their own spike, scoped credentials and the owner's explicit authorization (D4). Nothing in
  this revision writes to a real game or its repository.
- **Eligibility, checked at preflight:**
  - the Script Sync layout as it is (R2.8);
  - no attributes or tags on scripts;
  - a footprint of scripts and runtime-created instances only.

## R3.9 Delivery

**The dependency order** replaces R2.10's:
1. phase 2a: the companion's seam, proved with a fixture;
2. phase 2b: remote execution;
3. phases 2c–2e: the Luau runner, the Studio adapter and the assertion harness;
4. phase 2f: the companion's squad;
5. phase 3: the demonstration.

Revision 2's M0 is re-cut as phase 2b, and R-1 as phases 2c–2e (the ledger). Godot, Unity and GameBench-01 are
unchanged, each after Roblox.

**R2.10's two definitions of done stand:**
- "engine integration works" is this SIP's, for Roblox phases 2b–2e;
- "the squad can build and improve a playable game" is the companion's.

## R3.10 Decisions (2026-11-08)

The plan's D1–D10, accepted by the owner on 2026-11-08, as they touch this SIP:

| # | decision | where |
|---|---|---|
| D2 | a local, disconnected place file; no test universe | R3.8 |
| D3 | a worker-only service account, scoped to its assignment | R3.3 |
| D4 | Open Cloud out of this milestone | R3.8 |
| D5 | typed, deny-by-default operations; `execute_luau` only through the harness | R3.6 |
| D7 | one engine-neutral task type with operation ids; planning property-driven | R3.5 |
| D8 | `game-dev-<engine>` naming | R3.1 |
| D9 | the two-document split kept; acceptance after renewed review | this revision; accepted 2026-11-10 |
| D10 | the adapter owns sync | R3.6 |

D1 (the claim) and D6 (parallel development) are the companion's and the plan's.

---

# R2. Revision 2 (2026-10-31): engine integration plugins

**What prompted it.** The owner's outside review of this draft asked for engine integration as versioned
plugins, Unity beside Roblox and Godot, the reusable remote-execution contract apart from game operations,
per-adapter verification modes, editor changes returned through the revision boundary, greenfield
blueprints apart from existing repositories, one delivery milestone per engine, and tailored squads. **Where
the body (§1–§12) differs, this section governs, and §R3 governs both.** The body is kept as the owner's draft, edited only where
it contradicted this section (§1, §4, §9.5, §10, §11).

**The boundary with the companion proposal.** This SIP is how an engine is integrated: the plugin, its
operations, its workers and its evidence. *Game Development Capability Packs and Squad Composition*
(`SIP-Game-Capability-Packs.md`) is how a squad uses it: which roles, which capabilities, which skills, and
the Project's own game content. Both register through one plugin foundation, defined there (its §4), so
there is one extension mechanism, not two.

## R2.1 What core owns, and what a plugin owns

| SquadOps core (no engine knowledge) | an engine integration plugin (versioned) |
|---|---|
| Cycle and Campaign orchestration, gates, the correction loop | the Game Project Contract's engine section and its schema version |
| plugin discovery, binding and pinning (the companion's foundation) | the engine adapter: the typed operations of R2.3 |
| permissions: which role may invoke which operation | scaffolding: the greenfield blueprint for its engine (R2.8) |
| worker registry, capability matching and scheduling (R2.2) | engine-specific checks and their result readers |
| source revisions, the live tree (SIP-0102), artifacts (the vault), verification (SIP-0096) | the verification modes it supports (R2.4), with worker requirements |
| evidence aggregation and the run's verdict | compatibility: engine versions, worker platforms, other plugins |

A plugin never orchestrates, never decides a gate and never writes a revision. It declares operations and
reads results. Core runs them.

## R2.2 The remote-execution contract, apart from game operations

The reusable part is engine-free:
- **A worker** registers its identity, platform, installed tools with versions, and capabilities (named,
  versioned strings such as `unity.editor.batchmode@6000.0`), and reports health in the canonical vocabulary
  (`online`, `degraded`, `recovering`, `offline`). *Busy* is a lease on its concurrency, not a health state
  (Q38's recommendation).
- **An operation** is a typed request: the operation name a plugin declared, its inputs by artifact
  reference (never a live tree), a timeout and an idempotency key. It returns a typed result, its evidence
  by artifact reference, and the worker and tool versions it ran with.
- **Scheduling** matches an operation's declared requirement to a worker that holds it, leases the worker,
  and reports `blocked_unverified` with the reason when none can (asleep, offline, missing the capability).
- **Inputs, outputs and verdicts reuse what exists.** Inputs are staged from the artifact vault, outputs are
  stored in it, and results enter SIP-0096's verification as executed-passed, executed-failed or not executed.
  The live tree stays the sandbox's (SIP-0102). **No parallel artifact, sandbox or verification path.**

Game operations (`build_place`, `run_editmode_tests`, `play_scenario`, …) are what a plugin declares on top
of it. Nothing game-specific is in the contract.

## R2.3 How a plugin registers, declares and exposes

A plugin is an installable package discovered by the companion's foundation (Switchboard, the host-owned
loader the console already uses; Capability-Backed Agents §21). Its manifest is **data the host validates
without executing plugin code**:

```yaml
plugin: squadops-engine-unity
version: 0.1.0
requires_spi: "1"
provides:
  engine: unity
  contract_schema: game-project-contract/unity@1
  blueprints: [unity-urp-3d-starter@1]
compatibility:
  engine_versions: [">=6000.0,<6001"]
  worker_platforms: [macos, windows, linux]   # each per operation below
depends_on: []
operations:
  - name: run_editmode_tests
    mode: editor
    requires: [unity.editor.batchmode]
    inputs: {source: revision, test_filter: string?}
    result: unity-test-results@1        # read by the plugin's result reader
  - name: run_playmode_tests
    mode: runtime_play
    requires: [unity.editor.batchmode]
    result: unity-test-results@1
  - name: build_player
    mode: static_build
    requires: [unity.editor.batchmode, unity.build_target.<target>]
    result: unity-build-report@1
  - name: run_player_tests
    mode: runtime_play
    requires: [unity.player.<target>]
    result: unity-test-results@1
```

- **Each operation maps, in full, to code the plugin supplies** (the second outside review, 2026-10-31):

  | operation + argument schema | → versioned provider | → required worker capability | → result schema and reader |
  |---|---|---|---|
  | `run_editmode_tests {source: revision, test_filter?}` | `unity-testrunner@0.1.0`, the plugin's executor for the operation | `unity.editor.batchmode` | `unity-test-results@1`, read by the plugin's reader |

  The **provider** is the plugin's executable side: the engine-specific command construction, staging and
  output collection for one operation on one worker platform. **Core schedules, enforces policy and runs the
  provider on the matched worker. It never constructs an engine command itself,** so engine logic can't
  migrate into core. The provider's version is pinned in the execution evidence beside the reader's.
- **Registration** is the manifest plus that code (providers and result readers), against a narrow,
  versioned SPI (Capability-Backed Agents §21: "packs ship code against a narrow SPI").
  A `requires_spi` mismatch refuses the plugin at preflight. It never loads with a warning.
- **An adapter directory is not the mechanism.** Discovery, the manifest, the SPI and the pin are.
- **Compatibility is checked at preflight**: the Project's engine version against the plugin's range, and each
  operation's requirement against a registered worker. A gap is a blocking or disclosed gap, as SIP-0112 H.4
  names a product's.
- **The bound plugin versions are pinned** in the Cycle's and the Campaign's snapshot, so evidence names the
  `plugin@version` that produced it.

## R2.4 Verification modes, per adapter

Each operation declares one mode. A check the adapter can't run, or didn't, reads **not executed**
(SIP-0096), never passed.

| mode | what it can show | Roblox | Godot | Unity |
|---|---|---|---|---|
| static / build | the project builds and its static checks hold | Rojo build of the place; Luau analysis | `--headless` import and export | batchmode compile; player build |
| editor | scripts and objects as the editor sees them | Studio `RunScript` (FR-10) | headless editor scripts | EditMode tests |
| runtime / play | the game running, driven by a scenario | Studio play controls and input simulation through Studio MCP (R2.6) | headless run with scripted input | PlayMode tests in the editor; tests in a built player |
| multiplayer | several clients and a server | Studio's local server test (to be proven on the worker) | per project | per project |
| graphical capture | what a player would see | Studio MCP capture (R2.6) | a rendering run (needs a GPU or software renderer) | built-player capture |

**Every cell is a claim to prove on the configured worker before it's relied on.** Until it is, the mode is
declared and its checks read not executed. This draft records no cell as proven.

## R2.5 Unity

- **Three kinds of test, never merged:** EditMode tests (in the editor, no play loop), PlayMode tests (in the
  editor's play mode) and tests in a built player. Each is its own operation and its own evidence.
- **Results are read from the test run's own results file,** not from the exit code. Unity's test runner is
  run in batchmode with its test platform and a results path, and the plugin's reader parses that file into
  per-test outcomes, so a run that collected nothing reads not executed. *The exact flags and the results
  format are verified on the worker before the reader is written.*
- **Scene, prefab and asset metadata are preserved:** `.unity`, `.prefab` and `.asset` files, and each asset's
  `.meta` file with its GUID (narrowed on the second outside review). **Allowed:** an intentional deletion or
  move of an asset together with its `.meta`, and a valid new `.meta` for a new asset. **A failed check:** a
  surviving asset whose `.meta` is missing, or whose GUID changed. References break silently on either.
- **The worker is chosen by capability.** The Unity editor isn't assumed to run on the Spark: licensing, the
  editor build for the platform, and GPU needs decide it, and an operation is scheduled on a worker that
  declares the editor version and build target it needs.

## R2.6 Roblox: the tool inventory, updated

FR-04 and FR-10 stand, with Studio MCP's current tools added as operations, **each validated on the
configured worker before any check relies on it**:
- **play controls:** start and stop a play session (play solo; a local server with clients, if available);
- **input simulation:** drive a character or UI with scripted input inside a play session;
- **capture:** screenshots of a play session, as evidence.

They are the runtime/play, multiplayer and capture modes of R2.4. MCP inspection is still never presented as
gameplay unless a play session ran and its scenario's assertions were read (FR-10's rule). *Which of these
the installed Studio MCP exposes, and under which names, is unverified here.* The worker's registration
records what it actually offers.

## R2.7 Editor-created changes return through the revision boundary

A change made in an editor (a Studio edit, a Unity scene or prefab saved, a Godot resource) never commits
itself. The worker returns the changed files as artifacts: Rojo-synced sources, serialized scenes and
prefabs, `.meta` files, resources. Core applies them as a workspace patch, a new revision of the live tree
(SIP-0102 `apply_workspace_patch`). They then go through the same acceptance as any change: the squad's
checks, the product's runner and the Campaign's gate. A change the worker can't return as files is not a
change SquadOps made.

## R2.8 Greenfield blueprints, and existing game repositories

- **A greenfield game** is created from an engine plugin's blueprint (SIP-0105's model). It may carry its Game
  Project Contract in its repository as product content.
- **An existing game keeps its conventions.** It is registered as SIP-0112 registers any product, with no
  mandatory onboarding edits. Its derived profile is read from its tree (SIP-0112 H.4), and its Game Project
  Contract is SquadOps Project metadata. This is Q37's recommendation, now the design.

## R2.9 Tailored squads

The body's "not … a separate game-specific squad" is replaced. **A tailored squad configuration of the
existing roles is supported:** a roster, models, capability packs and tool permissions composed for game
work. An optional specialist, such as a game designer, is a roster choice. The companion proposal defines the
composition, and this SIP adds no role.

## R2.10 Delivery: one milestone per engine, and two definitions of done

**Two things, verified separately:**
- **"Engine integration works"** (this SIP): the plugin loads and pins, its operations run on a matched worker,
  its results are read per test into SIP-0096's evidence, its unexecuted modes read not executed, and editor
  changes come back as revisions.
- **"The squad can build and improve a playable game"** (the companion): a tailored squad takes a small game
  increment from design to accepted source, with an actual player scenario and independent QA evidence.

**The dependency order** (the second outside review):
**F1** (the companion's foundation, proven with a fixture provider: registration, binding, invocation and
the result-provider contract, no worker) → **M0** (real remote-worker execution) → **R-1** (Roblox engine
integration) → the companion's Roblox pack and composition (F2–F4) → **F5** (the playable-game demonstration)
→ **U-1** (Unity, the generalization). F1 needs no worker, so neither waits on the other.

**One milestone per engine, each standing alone.** Roblox first. Godot and Unity follow, and Unity is the
check that the plugin contract generalizes. **No cross-engine benchmark is a prerequisite** for the first
useful Roblox squad. GameBench-01 on several engines (Appendix A) becomes a later, optional milestone.

## R2.11 The rulings (2026-10-31)

Ruled by the owner's outside reviewer, under the owner's delegation ("I'll have the reviewer answer the open
questions"):
- **Q37, where the Game Project Contract lives:** Project metadata by default, with no mandatory onboarding
  edits (R2.8). An optional copy in the repository declares its relationship to the record, export or
  authority. The game's goals stay in the Project's goal records.
- **Q38, the worker registry:** one generic, host-owned registry. Plugins declare requirements, and core
  matches and schedules workers. Health uses the canonical states, and *busy* is a concurrency lease (R2.2).
- **Q39, vocabulary:** *Game Project Contract*, *asset register*, *game quality*, *squad delivery* and
  *game checks* are adopted. The qualified term *plugin manifest* is kept for installable package metadata.
  The body's older terms (`game_project.yaml` as a requirement, *quality gates*, *game outcome*) are
  replaced when this SIP is accepted.

---

# 1. Purpose and Intent

Enable SquadOps squads to autonomously design, implement, validate, package, and iteratively improve playable games, initially targeting **Godot 4.x (GDScript)** and **Roblox (Luau)**.

This SIP is a *platform capability*, not an implementation plan for one game. Tailored squad configurations of the existing roles are supported (R2.9; the companion proposal composes them). It adds:

1. A target-neutral Game Project Contract.
2. Godot and Roblox target adapters.
3. Game-specific automated verification and evidence.
4. Asset tracking and governed packaging/publishing.
5. A reusable **Remote Tool Execution** capability for tools that cannot run on the squad's primary Linux host.
6. A controlled cross-platform GameBench reference game and performance measurements.

The primary operating model is **agents on DGX Spark (Linux)**. For Roblox Studio validation, the **MacBook (macOS)** serves as an on-demand **remote execution worker** reachable over the approved Tailscale/SSH path. The MacBook is **not** an agent, a separate squad, or a second orchestration authority.

Normal **Cycle → Pulse → Surge → Task** semantics remain unchanged: Cycle owns execution truth and recovery; the Cycle Orchestrator alone emits coordination pulses; Surges group related tasks without gating execution; tasks carry throughput.

**Outcome:** A squad takes game intent through verified, playable, reproducible output, including when verification requires a remote GUI-capable machine, while retaining traceability and measurement of both game quality and squad autonomy.

# 2. Background

SquadOps already coordinates specialized roles, task dependencies, artifact production, QA, and metrics. Game development requires additional concepts: worlds/scenes, player input, physics, collisions, game states, rendering, asset provenance, multiplayer and persistence (when requested), performance, and—critically—**playability**.

**Godot** supports a CLI/headless build-and-test workflow suitable for local Linux execution.

**Roblox** development can be represented as Git-tracked Luau plus Rojo project files and built into Roblox place artifacts. However, **Roblox Studio runs on macOS or Windows, not Linux**, so reliable Studio-dependent validation should execute on a supported remote host. The documented macOS executable is:

`/Applications/RobloxStudio.app/Contents/MacOS/RobloxStudio`

Roblox Studio documents `--task RunScript`, `--runScriptFile`, `--outputFile`, and `--quitAfterExecution`, which provide an automation entry point for scripted checks. Studio also exposes a separate MCP integration through:

`/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP`

**Important distinction:** Studio CLI script execution, Studio MCP interaction, Rojo filesystem/build workflows, and Open Cloud publishing are separate mechanisms. None, individually, proves a completely unattended, display-free Roblox game-playtest solution. The adapter must report what was actually verified and what requires a GUI session or human involvement.

This SIP adopts the current SIP authoring standard: architectural intent and context first, testable requirements, implementation notes, executive summary, and explicit Definition of Done. It does not assign an unverified SIP number or roadmap version.

# 3. Problem Statements

1. No engine-neutral representation of game intent, playable behaviors, project metadata, or target capability requirements.
2. No standard Godot/Roblox bootstrap, build, run, test, export, or packaging operation.
3. No reliable game-specific QA that distinguishes a *compiling project* from a *working gameplay loop*.
4. No traceable game assets or game runtime evidence.
5. No cross-platform execution abstraction for workloads requiring macOS/Windows or a desktop session.
6. Risk of embedding MacBook-specific SSH logic in the Roblox adapter or granting squad agents broad remote shell access.
7. No worker discovery, availability/capability negotiation, timeout/cancellation, result transfer, or recovery protocol.
8. No distinction between a CLI script check, Studio edit-mode inspection, and a genuine simulated player/playtest.
9. No governed publishing boundary for Roblox Open Cloud or distributable Godot builds.
10. No repeatable cross-engine reference benchmark to assess progress in the game's quality *and* the framework's autonomy, quality, speed, and cost.

# 4. Scope

## Included

- Game project manifest and design artifacts.
- Godot 4.x / GDScript adapter with Linux-friendly headless execution and export.
- Roblox / Luau adapter using Rojo-compatible filesystem projects.
- Roblox Studio-based test and validation workflow on a registered macOS execution worker.
- Target-neutral capability requests and structured operation results.
- Remote worker discovery, authorization, task dispatch, staging, lifecycle, evidence collection, timeouts, cancellation, audit, and recovery.
- Game tests, quality gates, smoke tests, performance criteria, and runtime evidence.
- Source/asset provenance and governed publication.
- GameBench-01 implemented and scored against both engines.

## Explicit boundaries

- No new Game Developer agent role; existing roles are extended by capabilities and context, and composed into tailored squads (R2.9).
- No change to Cycle/Pulse/Surge/task coordination semantics.
- No assumption that Roblox Studio can run on Spark/Linux.
- No assertion that Studio GUI/player simulation can always run unattended in a login-free environment.
- No requirement for advanced 3D asset generation or AAA-quality content.
- Multiplayer, online persistence, storefront submission, marketplace moderation, and public launch are optional project requirements, not mandatory in GameBench-01.
- No unrestricted general-purpose remote shell API exposed to model agents.

# 5. Design Overview

## 5.1 Logical architecture

```text
Game Intent / GAME_DESIGN.md
             |
     Game Project Contract
             |
     SquadOps Cycle Orchestrator
     (sole coordination authority)
             |
   Tasks / non-gating Surges
             |
       Game Capability Port
          /       \
       Godot      Roblox
       Adapter    Adapter
         |          |
   Spark/Linux   Rojo + Luau
   Godot CLI          |
         |       Remote Tool Execution Port
         |          |
         |     Approved worker transport
         |       Tailscale + SSH
         |          |
         |     MacBook / macOS worker
         |     Roblox Studio CLI / MCP
         |          |
         +----------+
             |
    Build / Test / Evidence Results
             |
  QA Gates + Cycle Artifact Ledger
             |
      Benchmark / Outcomes
```

**Remote Tool Execution** is platform-neutral and reusable for other tools (e.g., future creative software) with a dedicated target adapter. The engine adapter declares a capability requirement; core infrastructure resolves an authorized worker and executes a bounded operation.

## 5.2 Game Project Contract

Each project MUST contain a machine-readable `game_project.yaml` and a human-readable `GAME_DESIGN.md`. Minimum dimensions:

- project ID, title, engine target and compatible version;
- game dimension, supported player counts/platforms;
- gameplay objective, required mechanics, player actions and controls;
- explicit win, failure, reset/replay paths;
- optional multiplayer, data persistence, physics, audio and visual requirements;
- QA quality gates and benchmark scenarios;
- output/package expectations and publishing policy.

Illustrative example (schema to be finalized during implementation):

```yaml
game:
  id: gamebench-01
  title: Collect & Escape
  target: roblox
  engine_version: current-supported
  dimension: 3d
  players: {min: 1, max: 1}
  gameplay:
    objective: collect five keys then reach the exit
    success_conditions: [all_keys_collected, exit_reached]
    failure_conditions: [hazard_triggered]
  verification:
    boot: true
    core_loop: true
    evidence_required: true
  publishing:
    mode: approval_required
```

## 5.3 Adapter contract

The target-neutral adapter MUST implement the logical lifecycle:

```text
detect
validate_environment
bootstrap
validate_project
build
run
test
capture_evidence
package
publish
```

Operations MUST return structured status, duration, failure classification, artifact/evidence references, engine/worker version, and correlation to task/Cycle identifiers. If unavailable or unsupported, results MUST say so explicitly rather than claiming a pass.

## 5.4 Remote Tool Execution: distributed worker, not agent

The MacBook is an **execution resource**. It must not make Cycle decisions, emit Pulses, assign tasks, adjudicate QA outcomes, or act autonomously as an agent. Its responsibilities are to stage validated inputs, invoke allowlisted local operations, stream/persist diagnostics, and return structured results/evidence.

An initial worker can be a narrow SSH-invoked executor rather than a continuously running control-plane service, provided it still meets capability discovery, identity, idempotency, status, cancellation, timeouts, and artifact contracts. Later implementations may use a persistent worker daemon without changing the port contract.

The worker is registered by logical ID and capabilities, not hardcoded hostnames in game logic:

```yaml
worker:
  id: macbook-studio-01
  platform: macos
  transport: ssh
  network: tailscale
  capabilities:
    - roblox.studio.cli.run_script
    - roblox.studio.cli.api_dump
    - roblox.studio.mcp  # optional, verified at registration
  concurrency: 1
  status: available
```

This is an example declaration, **not** evidence that all capabilities are configured or operational.

# 6. Functional Requirements

## FR-01 — Game intent and traceability

Strategy MUST define mechanics, controls, levels, player success/failure states, testable acceptance criteria, supported target(s), and a minimal game design brief. Gameplay behavior MUST be linked to existing SquadOps task/artifact and applicable PID/Use Case traceability.

## FR-02 — Target discovery

A Cycle selects `godot` or `roblox`; adapters advertise required tools/versions and supported operations. Unsupported requirements MUST fail validation before implementation tasks begin or generate explicit blocked conditions.

## FR-03 — Godot adapter

The Godot adapter MUST:

- discover and pin a compatible Godot version;
- bootstrap `project.godot`, scenes, resources, GDScript, UI, and basic physics/game state;
- validate import and project load;
- execute smoke/runtime checks through documented CLI/headless operations where supported;
- report script/runtime errors, test outputs and evidence;
- export configured platform builds and record export profile, hashes, and logs;
- avoid committing sensitive export credentials.

## FR-04 — Roblox adapter

The Roblox adapter MUST:

- bootstrap a Rojo-compatible Luau project;
- create script/world/service structure from source-controlled assets;
- build a `.rbxl`/`.rbxlx` place artifact where supported by the pinned Rojo version;
- use the MacBook Studio worker for Studio-required validation;
- invoke documented Studio CLI script execution with output files and appropriate exit behavior;
- optionally use Studio MCP for supported interactive inspection/edit operations, with separately reported capabilities;
- distinguish editor/script validation from actual play simulation;
- use Open Cloud for approved publishing where supported, recording place/universe IDs and returned version/result;
- surface constructs not fully represented by Rojo instead of silently discarding them.

## FR-05 — Worker registration and capability discovery

Remote execution MUST support:

- logical worker identity, OS/architecture, capability names and versions;
- configured transport and approved network reachability;
- availability/health probe (on demand or heartbeat);
- worker status: `available`, `busy`, `unavailable`, `degraded`;
- capability-specific preflight: installed Studio, CLI behavior, Rojo/project files, session availability where GUI operations are requested;
- explicit results when a worker is offline, sleeping, disconnected, unconfigured, or lacks a required session.

Worker requirements MUST be resolved by the infrastructure/capability layer, never by hardcoded `ssh macbook ...` strings inside agent prompts.

## FR-06 — Secure remote execution

The executor MUST:

- authenticate with scoped, key-based or equivalent approved transport over Tailscale/private network;
- run as a dedicated least-privileged local account where practical;
- accept **allowlisted named operations** with validated typed arguments, not arbitrary shell commands from agents;
- use per-Cycle/per-task isolated workspaces;
- verify staged input paths and artifact checksums;
- limit filesystem, secrets, and network access;
- prevent sensitive credentials from entering logs or source artifacts;
- enforce publishing authorization separately from ordinary build/test rights;
- record worker identity, caller, operation, request, timestamps, and result for audit;
- provide configurable CPU/time/concurrency limits where supported.

## FR-07 — Remote execution lifecycle

The dispatcher/executor MUST support:

1. `requested`: operation and correlation IDs recorded.
2. `preflight`: host and capability validated.
3. `staging`: immutable source/build inputs transferred or pulled.
4. `running`: named operation launched, with process tracking.
5. `collecting`: logs and evidence finalized.
6. terminal result: `succeeded`, `failed`, `timed_out`, `cancelled`, or `unavailable`.

Repeated delivery of the same execution request MUST be idempotent or explicitly deduplicated. Distinguish a transport disconnect from an engine test failure. Do not silently retry publishing or other non-idempotent actions.

## FR-08 — Timeouts, cancellation, and recovery

The executor MUST implement operation timeouts, best-effort cancellation and child-process cleanup, and bounded retries only for safe operations. If the MacBook sleeps or becomes unreachable, the associated Task MUST remain auditable, with a structured transient/infrastructure failure classification. Recovery and replay MUST follow ordinary Cycle authority; a remote worker MUST NOT rewind a Cycle or emit a Pulse.

## FR-09 — Evidence return and provenance

Every remote operation MUST return or register:

- Cycle ID, Pulse/Surge/task IDs where relevant;
- worker ID, engine and adapter version;
- command/operation descriptor (with sensitive fields redacted);
- start/end timestamps, exit code and normalized state;
- stdout/stderr/log file references and script-result JSON;
- requested screenshots/video/frame captures when actually supported and produced;
- checksum, build/source revision, and artifact provenance.

Evidence MUST be associated with the initiating Cycle and QA contract. A missing screenshot or unavailable full play simulation MUST be shown as unverified, not replaced by a generic success result.

## FR-10 — Roblox Studio automation modes

Support three distinct verification modes with truthful reporting:

| Mode | Mechanism | What it can prove |
|---|---|---|
| Static/build | Rojo + Luau checks | filesystem/build correctness and static constraints |
| Studio script | Studio `RunScript` CLI | script assertions and inspected Studio/game objects at the invoked privilege/context |
| Interactive/play | supported Studio session, MCP and/or a project-specific play harness | only the actual behaviors exercised and evidenced |

The implementation MUST prove CLI behavior on the configured MacBook. GUI session startup, play-mode control and screenshots are environment-dependent and MUST be tested explicitly before any unattended claim. MCP integration MUST NOT be presented as equivalent to gameplay simulation.

## FR-11 — Assets and project structure

Asset manifests MUST record source, licensing/provenance, hash, target path, import status, and revision. Primitive placeholders are permitted where gameplay criteria can be validated.

Suggested repo structure:

```text
game/
  game_project.yaml
  GAME_DESIGN.md
  ASSET_MANIFEST.json
  project/                 # engine-native source/project
  testing/
    GAME_TEST_PLAN.md
    automated/
    evidence/
  build/
  metrics/
```

Actual placement SHALL honor existing DDD/hexagonal architecture and repository conventions.

## FR-12 — Automated game quality gates

Mandatory gates:

- **QG-1** Project integrity and load/import.
- **QG-2** Successful build/compilation.
- **QG-3** Boot/initial playable state.
- **QG-4** Core player action and primary mechanic.
- **QG-5** Defined success path.
- **QG-6** No unexpected fatal errors in the tested path.
- **QG-7** Performance within explicitly defined project thresholds.
- **QG-8** Platform/device/input/multiplayer/persistence behavior where required.
- **QG-9** Inspectable evidence and explicit verification provenance.

A successful Rojo build or `RunScript` result MUST NOT automatically satisfy a full gameplay or frame-rate gate.

## FR-13 — QA repair loop

Failed gates MUST produce structured defects with expected/actual values and evidence references. Lead MAY issue repair tasks or non-gating repair Surges through standard Cycle coordination. The worker must not choose governance transitions.

## FR-14 — Publishing controls

The default mode is `approval_required`. Publishing MUST be separated from local staging/testing and require explicit authorization according to configured policy. Roblox publish credentials must be narrowly scoped and kept out of project files. Godot export/publish artifacts must record hashes, export profile, and target. Automatic publishing, if ever enabled, requires a separately approved policy.

## FR-15 — Benchmarking and learning

A run MUST record both:

**Game outcome:** passed gates, core-loop completion, stability, performance, and evidence coverage.

**Squad outcome:** Cycle duration, cost/tokens, model/agent execution time, build attempts, QA iterations, defects, repair rate, time-to-first-playable, human interventions, time blocked on remote worker, and reuse of validated prior patterns.

Measure remote infrastructure wait time separately from agent reasoning and engine execution time to avoid misleading optimization conclusions.

# 7. Non-Functional Requirements

- **Portability:** Godot runs on eligible local workers; Roblox Studio operations can be dispatched to an available supported OS host without agent relocation.
- **Security:** No unrestricted remote shell; least-privilege scoped credentials; Tailscale/private transport; sensitive fields redacted; isolated workspaces.
- **Reproducibility:** Source SHA, engine version, tool/adapter versions, build arguments, assets, worker environment, and test scripts recorded.
- **Resilience:** Offline/sleeping MacBook yields an explicit blocked/unavailable result; retry policy and cancellation are deterministic and recorded.
- **Observability:** Correlation IDs and linked evidence survive transport failures; partial logs retained where safely possible.
- **Concurrency:** Initial Roblox Studio worker MAY use `concurrency: 1` to avoid conflicting GUI sessions.
- **Compatibility:** Existing non-game Cycles and adapters unaffected.
- **Extensibility:** Future target engines or remote workers require no Cycle FSM changes.
- **Performance targets:** Operation-specific timeouts and project FPS/load criteria are configured per environment and game; no universal FPS threshold is assumed.

# 8. API Surface

Logical capability interface (not a claim of existing endpoints):

```text
game.environment.validate
game.project.bootstrap
game.project.validate
game.build
game.run
game.test
game.evidence.capture
game.package
game.publish

remote.worker.register
remote.worker.capabilities
remote.worker.health
remote.operation.submit
remote.operation.status
remote.operation.cancel
remote.operation.artifacts
```

Example execution request (illustrative schema):

```json
{
  "request_id": "remote-op-0001",
  "cycle_id": "cycle-001",
  "task_id": "task-qa-010",
  "target": "roblox",
  "required_capability": "roblox.studio.cli.run_script",
  "operation": "studio.run_script",
  "input_artifacts": ["build/gamebench-01.rbxlx", "testing/automated/smoke.luau"],
  "timeout_seconds": 300,
  "publication_authorized": false
}
```

Example result:

```json
{
  "request_id": "remote-op-0001",
  "worker_id": "macbook-studio-01",
  "status": "succeeded",
  "verification_mode": "studio_script",
  "exit_code": 0,
  "duration_ms": 47120,
  "artifacts": [
    "testing/evidence/studio-smoke.log",
    "testing/evidence/studio-smoke-result.json"
  ],
  "claims": ["studio_script_assertions_passed"],
  "not_verified": ["interactive_player_playthrough"]
}
```

Implementation MAY use existing SquadOps APIs/messages where appropriate; do not proliferate endpoints when the capability can be expressed through an existing invocation port. All schema changes MUST be versioned and validated.

# 9. Implementation Considerations

## 9.1 Preferred ownership split

| Responsibility | Execution location |
|---|---|
| Lead/Strategy/Dev/QA/Data agent reasoning | DGX Spark / SquadOps |
| Luau authoring and Rojo build | Spark (subject to tool compatibility) |
| Godot CLI/headless tests | Spark or eligible local worker |
| Roblox Studio CLI script execution | MacBook macOS worker |
| Studio MCP interaction | MacBook worker, optional and separately validated |
| Game evidence and QA scorecard | Stored in SquadOps Cycle artifacts |
| Roblox Open Cloud publishing | Governed operation with approved credentials; does not require an agent on MacBook |

## 9.2 MacBook worker setup

Prerequisites:

1. Tailscale installed and connectivity to Spark proven.
2. SSH remote login restricted to an approved key/account (or equivalent approved transport).
3. Roblox Studio installed and executable discovered.
4. Studio CLI `RunScript` verified with a harmless probe and an output file.
5. Rojo integration and artifact transfer path configured.
6. A macOS user/desktop session available where a requested operation needs one.
7. Local workspace, cleanup policy, log/artifact staging, and concurrency limit configured.
8. Worker capability profile registered and preflightable.
9. Credential access rules and publishing approval flow verified.

**Operational constraint:** MacBook must be powered, reachable, and capable of running Studio for Studio-required tasks. A sleeping/offline MacBook does not block unrelated Spark game development; only the specific remote-dependent tasks are blocked.

## 9.3 CLI and MCP strategy

**MVP:** Use Studio's documented CLI script operation for bounded smoke assertions and diagnostics. Prefer this over GUI click automation for predictable automation.

**Extension:** Evaluate official Studio MCP for environment inspection/editing, but place it behind a validated optional capability with explicit session requirements. Add automated in-game play simulation only after proving that it executes the intended game state and records reliable evidence.

## 9.4 Proposed package boundaries

```text
game_capability/
  contracts/
  adapters/
    godot/
    roblox/
  testing/
  evidence/

remote_execution/
  ports/
  dispatcher/
  transports/
    ssh/
  worker/
    macos/
  security/
```

Adapt names and placement to actual `squadops`/`continuum`/`switchboard` repository boundaries after codebase inspection. The **logical interfaces** are normative; this directory suggestion is not.

## 9.5 Implementation slices (not fixed Cycle counts)

- **Slice A:** Game contract, engine-neutral results, Godot bootstrap/test/export.
- **Slice B:** Rojo project/build and Studio-required capability declaration.
- **Slice C:** Generic remote execution port, MacBook registration, preflight, secure script execution, artifact return.
- **Slice D:** Game QA contracts, defect/repair loop, evidence and outcomes.
- **Slice E:** Dual-engine GameBench-01, performance measurement, governed publishing verification.

These are capability increments, **not** hardcoded Campaign or Pulse stages. A Campaign can continue through as many Cycles as outcomes require.

**Superseded by Revision 2:** the slices are now one milestone per engine, on a shared remote-execution
contract (R2.10 and the delivery ledger).

# 10. Executive Summary — What Must Be Built

1. Game Project Contract, design brief, and asset manifest schema.
2. Target-neutral Game Target Adapter interface.
3. Godot 4.x/GDScript adapter with validated build, runtime test, export and evidence.
4. Roblox/Luau/Rojo adapter with place build, Studio validation, and governed publishing.
5. Reusable Remote Tool Execution port and secure dispatcher.
6. MacBook/macOS Roblox Studio execution-worker implementation using Tailscale/SSH or equivalent approved transport.
7. Worker discovery/capabilities/preflight, operation lifecycle, timeout/cancellation, artifacts, and audit.
8. Strict distinction between Studio CLI, MCP, and real playtesting evidence.
9. Game-specific QA gates and structured repair outcomes.
10. GameBench-01 on more than one engine, as a later optional milestone, never a prerequisite for the first Roblox squad (R2.10).
11. Comparative game quality and squad autonomy/efficiency scorecards.
12. Documentation for operating the MacBook worker and extending to future targets/workers.

# 11. Definition of Done

**Revision 2:** the checklist below is split by R2.10 into "engine integration works" (this SIP, per engine)
and "the squad can build and improve a playable game" (the companion). The engine milestones are independent;
where an item below names both engines together, read it per engine.

## Capability and architecture
- [ ] Game project schema and design artifacts validate.
- [ ] Godot and Roblox target adapters implement the common contract.
- [ ] No engine-/MacBook-specific logic is embedded in Cycle orchestration.
- [ ] Existing Cycle/Pulse/Surge/task semantics remain unchanged.

## Godot
- [ ] Squad bootstraps and edits Godot source/project without manual code authoring.
- [ ] Headless validation and executable smoke tests produce structured results.
- [ ] A configured export is produced with traceable metadata.

## Roblox
- [ ] Squad bootstraps Luau/Rojo project and produces a place artifact.
- [ ] Registered MacBook worker reports Roblox Studio CLI availability.
- [ ] Squad dispatches a Studio `RunScript` smoke test over the approved transport.
- [ ] Captured output and explicit test assertions return to the originating Cycle.
- [ ] Unsupported GUI/interactive checks are explicitly marked unverified until proven.
- [ ] Optional Studio MCP integration, if enabled, passes its own capability test.

## Remote tool execution
- [ ] Worker health and capabilities are discoverable without direct agent SSH.
- [ ] Missing/sleeping/unreachable MacBook yields truthful blocked/unavailable reporting.
- [ ] Only allowlisted typed operations can run.
- [ ] Workspace separation, input validation, least privilege and audit are enforced.
- [ ] Operation timeout, cancellation, duplicate-delivery handling and safe retry are tested.
- [ ] Logs, checksums, version data and artifacts are linked to Cycle/task IDs.
- [ ] Remote worker cannot emit Pulses, modify Cycle governance or publish without authorization.

## QA, outcomes and publishing
- [ ] Mandatory game gates produce PASS/FAIL/UNVERIFIED with evidence.
- [ ] Failure findings can generate traceable repair tasks.
- [ ] Publishing is independently gated and secrets remain outside source control.
- [ ] GameBench-01, when its optional milestone is taken, succeeds per engine on objectively testable scoped criteria.
- [ ] Engine limitations and manual interventions are reported rather than hidden.
- [ ] Benchmark dashboard/report distinguishes game outcome from squad outcome and isolates remote wait time.

# 12. Appendix

## A. GameBench-01: Collect & Escape

A minimal, identical behavior specification for both engines:

- one player and a bounded 3D world;
- movement and camera control;
- five collectibles;
- one hazard;
- HUD counter;
- locked exit that unlocks once all collectibles are obtained;
- success screen when the player reaches the exit;
- reset/replay behavior.

A test plan MUST identify which checks are static, Studio script, interactive play, or manually observed, with no false equivalence between verification modes.

## B. Authority and roles

- **Strategy:** defines game loop, scope, desired player outcome and acceptance criteria.
- **Lead:** authorizes coordination and repair work; governs publishing.
- **Dev:** builds engine projects through target adapters.
- **QA:** owns test cases, executable acceptance gates and evidence sufficiency.
- **Data:** tracks quality, cost, duration, remote blocking and learning trends.
- **Remote worker:** executes bounded tasks and returns evidence; **not an agent**.

## C. Remote flow example

```text
QA Task on Spark
    -> resolve capability roblox.studio.cli.run_script
    -> registered MacBook worker selected
    -> preflight (reachable, Studio installed, session requirements)
    -> stage version-pinned .rbxlx and smoke.luau
    -> execute Studio CLI RunScript with log output
    -> return exit code, assertions, logs, checksums
    -> QA evaluates actual claims, records missing evidence
    -> Lead coordinates any repairs
```

## D. Sources and implementation references

- SquadOps SIP Template v1 (uploaded project file): intent-preserved 12-section structure, impersonal role names.
- SquadOps IDEA: Cycle Orchestrator, Pulses and Surges (uploaded): only orchestrator emits pulses, surges never gate.
- SquadOps testing protocol, task logging, documentation traceability (uploaded): quality and provenance expectations.
- Roblox official Studio CLI documentation: https://create.roblox.com/docs/studio/command-line-interface
- Roblox official Studio MCP documentation: https://create.roblox.com/docs/studio/mcp
- Roblox Creator Cloud documentation: https://create.roblox.com/docs/cloud
- Rojo documentation: https://rojo.space/docs/
- Godot CLI documentation: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html

**Source distinction:** SquadOps architectural semantics and SIP structure come from the supplied project files. Engine CLI/MCP/Open Cloud/Rojo mechanisms are from external vendor documentation. The proposed remote worker contracts, verification taxonomy and GameBench metrics are *design requirements in this draft*, not claims that they already exist.
