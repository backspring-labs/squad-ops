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

## Delivery ledger (current as of 2026-11-11)

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
| Phase 2c: the Luau runner (#2906; core, R3.2), built by the Spark lane (the 2.8 plan's decision 4) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #2906 |
| Phase 2d: the Studio adapter: the transaction, the adapter's own sync, read-back, the baseline, reset, the `roblox-studio` provider's four operations, and the isolation test (R3.6, R4.3, R4.6, R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3039 |
| Phase 2e: the assertion harness and reader: the harness executes a declarative scenario (R3.7, R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3040 |
| The frozen scenario: declarative (actions, observations and expected values the harness validates and executes), frozen before development with its reader, and its named assertion executed and failing on the accepted baseline before development starts (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3044 |
| A Campaign whose worker is unavailable: it waits in `launch_blocked` before launch, and an availability-only gap is relaunched within a budget persisted per logical increment, then escalated (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3045 |
| The worker as a service on the MacBook: launchd, stay-awake, Studio opened on the place, `doctor dev-mac` checks, an optional bootstrap step (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3046 |
| The operator's read surface: a read-only workers route and `squadops workers list` and `show` (R5.7) | **shipped** | 2.8 (PR #3059, closing #3047) |
| Re-qualification after a Studio update: a recorded run moves the pin, never a hand edit (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3048 |
| Payload limits: request and evidence sizes measured on the real tree, then explicit limits; captures outside 2.8's acceptance evidence (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3049 |
| The end-to-end machinery Campaign: two increments, the scripted squad and the fixture worker, from a fixture change request through plan, claim, verdict, repair, re-run and delivery, with six faults injected, in CI (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3050 |
| Campaign delivery: a scenario criterion accepted on evidence bound to the candidate's revision, and every earlier increment's scenario replayed on the same candidate (R5.7) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3053 |
| G-1: Godot integration works | **unplaced**, deliberately | — |
| U-1: Unity integration works: EditMode, PlayMode and player tests apart, results read per test, metadata kept, a worker matched by capability (R2.5); the check that the engine boundary generalizes | **unplaced**, deliberately: after Roblox | — |
| B-1: GameBench-01 on more than one engine, and governed publishing | **unplaced**, deliberately: later and optional, never a prerequisite for Roblox (R2.10) | — |

**What closes this SIP:** phases 2a–2e and R5.7's rows shipped (Roblox integration works), then G-1 and U-1 shipped or dropped by a
numbered amendment. B-1 is optional. "The squad can build and improve a playable game" is the companion's to close
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

---

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
