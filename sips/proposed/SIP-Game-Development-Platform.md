---
sip_uid: '17922784453538440'
sip_number: null
title: "Game Development Platform Capability"
revision: 2
status: "proposed"
author: "Framework Committee"
approver: null
created_at: "2026-10-16T00:00:00Z"
updated_at: "2026-10-16T00:00:00Z"
original_filename: "SIP-Game-Development-Platform.md"
---
# SIP-XXX — Game Development Platform Capability
## Engine integration plugins (Roblox, Godot, Unity) and Remote Tool Execution

**Status:** Proposed (the owner's draft, filed 2026-10-17)  
**Target Version:** TBD  
**Author:** Framework Committee  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data  
**Date:** 2026-10-16  
**Document Revision:** 2 (2026-10-31) — the owner's outside review applied: engine integration as versioned plugins, Unity as a third provider, the remote-execution contract apart from game operations, per-adapter verification modes, editor changes through the revision boundary, greenfield blueprints apart from existing repositories, one delivery milestone per engine, and tailored squads (§R2, which governs where the body below differs). Revision 1: the owner's draft, filed as written  
**Related SIPs:** SIP-0112 (Project Lifecycle Management, accepted 2026-10-17: its FR-17 is what this SIP builds on); SIP-0070 (Pulse Checks); SIP-0071 (Builder Role); SIP-0072 (stack development profiles); SIP-0086 (Build Convergence Loop); SIP-0096 (Verification Evidence Integrity); SIP-0103 (owns the word *manifest*); SIP-0105 (stack blueprints); SIP-0108 (Cycle Evaluation Scorecard); SIP-0113 (Outcome Evaluation, accepted 2026-10-17); Edge Deployment Profile (proposed, deferred to 3.x)  
**Companion:** Game Development Capability Packs and Squad Composition (`sips/proposed/SIP-Game-Capability-Packs.md`): what a game squad is composed of. This SIP is how engines are integrated; that one is how a squad uses them.  
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
- **Sources Appendix D cites:** the IDEA above, now `docs/ideas/IDEA_Cycle_Orchestrator_Pulses_and_Surges.md`
  (non-normative, Q33); the testing, task-logging and documentation-traceability protocols, kept as
  `docs/ideas/Testing protocol.txt`, `docs/ideas/Task logging and metrics.txt` and
  `docs/ideas/Doc traceability.txt`; the repository's SIP template, `sips/TEMPLATE.md`.

## Delivery ledger (current as of 2026-10-31)

One row per part that ships separately, from §9.5's slices. Statuses: *shipped* (the release, the PR,
and the issue it closed), *placed* (the release and the open issue tracking it, labelled `sip:NNNN` once
numbered), *unplaced* (said deliberately), *dropped* (by the numbered amendment that dropped it), or
*deferred to N.x (ruled <date>)*. Updated in the PR that ships or re-places a part
(`tests/unit/architecture/test_sip_ledgers.py` holds it). The target is TBD, so no row is placed.

| part | status | where |
|---|---|---|
| Slices A–E of revision 1 (§9.5) | **dropped** by Revision 2 (R2.10): restructured into the milestones below. None was placed | — |
| M0: the remote-execution contract and worker registry (R2.2), on the companion's plugin foundation | **unplaced**, deliberately: awaits acceptance and placement | — |
| R-1: Roblox integration works: the plugin, Rojo build, the Studio worker, its modes proven or declared not executed, editor changes as revisions (R2.4, R2.6, R2.7) | **unplaced**, deliberately: the first engine | — |
| G-1: Godot integration works | **unplaced**, deliberately | — |
| U-1: Unity integration works: EditMode, PlayMode and player tests apart, results read per test, metadata kept, a worker matched by capability (R2.5); the check that the plugin contract generalizes | **unplaced**, deliberately: after R-1 | — |
| B-1: GameBench-01 on more than one engine, and governed publishing | **unplaced**, deliberately: later and optional, never a prerequisite for R-1 (R2.10) | — |

**What closes this SIP:** M0 and R-1 shipped, then G-1 and U-1 shipped or dropped by a numbered amendment. B-1
is optional. "The squad can build and improve a playable game" is the companion's to close (R2.10).

---

# R2. Revision 2 (2026-10-31): engine integration plugins

**What prompted it.** The owner's outside review of this draft asked for engine integration as versioned
plugins, Unity beside Roblox and Godot, the reusable remote-execution contract apart from game operations,
per-adapter verification modes, editor changes returned through the revision boundary, greenfield
blueprints apart from existing repositories, one delivery milestone per engine, and tailored squads. **Where
the body (§1–§12) differs, this section governs.** The body is kept as the owner's draft, edited only where
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
