# game-dev-roblox plan — a squad that develops and tests a Roblox game

**Status: ADOPTED, revision 3 (2026-11-08), unplaced.** The MacBook lane's input to the 2.8 plan.
- **Phase 0 is done, and the gate is go** (§3a; the record is `game-dev-roblox-spikes.md` in `docs/plans/`).
- **The owner accepted D1–D10 on 2026-11-08** ("accept D1-D10, write revision 3"), so phases 1–3 are adopted (§7).
- **Placement is still the 2.8 plan's.** Nothing here places an issue or a release slot.
- **Adopting the plan doesn't accept either game SIP.** Acceptance follows revision 3 of both SIPs (phase 1) and a
  renewed review (§8).
- **Phase 2 waits for Agent Skillsets (2026-11-09).** The owner asked whether the word *specialty* could change, and
  checking it showed revision 3 had rebuilt Capability-Backed Agents §27 beside the existing stack and development
  profile seams. The owner pulled §21 and §27 forward into a 2.x SIP, Agent Skillsets (PR #3006):
  "agree, pull it forward and draft the assembly SIP. but make sure I can run an outside review before you start
  building". Agents carry *skillsets*, specs a capability pack can later carry; a squad profile stays an assembly of
  agents; and *playbook* is kept for what a squad follows. So:
  - **no building starts** until the owner's outside review of Agent Skillsets has answered its questions and the
    owner accepts it;
  - **revision 4 of this plan and of both game SIPs follows.** It replaces the *specialty* with the `game_dev_roblox`
    development profile assigning skillsets to the dev and QA roles, and renames this plan's *playbooks* to skills.
    Phase 2a becomes Agent Skillsets' phases 1, 2 and 4;
  - until then, §2's *specialty* and *playbooks* read as superseded wherever Agent Skillsets differs.

## Revision log

- **Revision 1** (2026-11-08): the first draft.
- **Revision 2** (2026-11-08): the owner's outside review, 15 points, applied.
  - **The claim:** the repair path becomes a separate diagnostic, and the counted claim no longer needs a failure.
    The claim is conditional on S1 proving the play and input mode (§1).
  - **Runtime guarantees kept** while plugin packaging waits: a digest of the resolved specialty pinned in the
    Campaign snapshot, and preflight at creation and at the plan gate (§2.3).
  - **Task types:** one engine-neutral task type carries specialty operation ids. The guard exception (revision 1's
    D7) is withdrawn, because `task_types._member_or_none` reads any value outside the central enum as `None`, so a
    specialty enum's task types would read `False` on every property, silently (§2.4).
  - **The Studio driver moves under `adapters/`,** and the isolation check covers every place the specialty lives
    (§2.2).
  - **The worker protocol** is specified: claim, assignment identity, the lease over the whole Studio transaction,
    fencing, cancellation, expiry, reconcile before retry, and the worker's authority limits (§2.5).
  - **The tested state is identified:** the exact Studio instance and place, scripts confirmed inside Studio, the
    non-script baseline pinned, and Script Sync's conflict cases (§2.6).
  - **Returned Studio edits** are a new revision that is verified again (§2.6).
  - **A deterministic assertion protocol** (§2.7).
  - **The copy's production hooks, credentials and integrations** are removed (§2.10).
  - **Open Cloud (revision 1's S3) leaves this plan,** which removes the publishing contradiction (§4).
  - **S6 is labelled a first probe,** with a full-path gate before the counted run (§3).
  - **#2906 stays in 2.8:** the owner deferred it on 2026-11-05 (2.7 plan §5), and a new language runner is a
    feature.
  - **Prior rulings Q45 and Q46** are reconciled explicitly (§8).
- **Revision 3** (2026-11-08): the spikes' findings, the gate (go) and the owner's acceptance of D1–D10.
  - **The claim stands as written:** S1 proved play, input and read-back (§1).
  - **The product is a local place file, not a test universe** (§2.10, D2). It's disconnected (PlaceId 0) with saving
    off, and it is reset from a read-only baseline file.
  - **The adapter owns sync (D10):** it writes scripts into Studio through its own fixed harness and reads them back.
    The worker's Studio has no Script Sync link, because Script Sync's links are lost on every Studio restart (§2.6).
  - **The Studio transaction takes S1's tool facts:** paged results, a deadline on every call, identity by PlaceId and
    digest, cleared harness state, the named deny list, and both checks run in full (§2.6).
  - **§2.2 narrows** after S5: a new kind of authored work adds central task types. **Planning becomes
    property-driven:** the planner's fixed set of task types is the seam both this specialty and a designer need
    (§2.4).
  - **The playbooks take S6's findings** (§2.8). The game's title screen is part of every scenario's setup (§2.7).

**What it builds on.**
- The two proposed game SIPs: *Game Development Platform Capability* (PR #2405) and *Game Development Capability
  Packs and Squad Composition* (PR #2841, stacked on it).
- The 2.6 Roblox spike (`docs/plans/roblox-spike-2-6.md`, #2895): pure-Luau logic tests run headless on the Spark
  under Lune, and anything that touches the engine needs Studio. Its gaps are #2906.
- Prior art on the MacBook: a working client for Roblox Studio's built-in MCP server, in the target game's
  repository (`art/studio-bridge/studio_mcp.py`). S1 re-verified the installed tools (38) and their schemas
  directly, through Studio's stdio proxy.

## 1. The claim

**Counted:** a squad running on the Spark takes **two small increments** of an existing Roblox game from design to
accepted source, each proved in a real play session in Roblox Studio, on a private copy of Tower Ascension (§2.10).
For each increment:
1. strategy writes a change request with a player-facing criterion and its play scenario, which are frozen before
   development (§2.7);
2. **the criterion fails on the accepted baseline,** so it discriminates;
3. dev writes the Luau change;
4. QA's operation syncs the candidate to Studio, plays the frozen scenario and reads its assertion records;
5. **the criterion passes on the candidate,** and the Campaign's gate accepts the source onto the campaign branch.

A correct first candidate is acceptable. The second increment is accepted with the first increment's frozen checks
re-run and passing.

**A separate diagnostic, labelled apart from the counted evidence:**
- a pre-registered, seeded behavioural defect;
- the unchanged verifier fails as an executed behavioural failure;
- the repair is routed;
- **the same verifier, by digest, passes.**

It proves the correction route. It's not model evidence.

**S1 settled the condition revision 2 put on the claim:** mouse, keyboard and character navigation all work in an
unattended play session, so the claim stands as written (the gate, §3a).

**What the evidence won't show:** how the game feels, what it looks like, more than one player, and parts, models or
UI built in Studio. Those don't sync to files (§2.10).

## 2. The approach: one specialty built for real, its boundary shaped like a plugin

**The plugin machinery waits for a second specialty.** That means discovery, installation, external packaging,
manifest validation, a versioned interface and the plugin lifecycle. A designer (Capability-Backed Agents §13, the
Iris and Glyph roles) or `game-dev-unity` is the second use that pays for it. Until then, `game-dev-roblox` plugs into
seams the framework already has, and keeps the runtime guarantees a plugin would have (§2.3).

| need | existing seam it uses |
|---|---|
| route a step to a role | the handler registry (by task type and role) and the squad profile's `serves_roles` |
| a roster and its models | a squad profile (`config/squad-profiles.yaml`) |
| prompt text | PromptService fragments, under a directory of the specialty's name |
| playbooks | skill files inside the specialty package |
| treat game steps differently | `TaskType` properties and lookup tables; never a check on the engine's name |
| evidence | SIP-0096's executed-passed, executed-failed and not executed |
| I/O | a port, an adapter behind it, and a composition root that binds it (`docs/architecture/composition-roots.md`) |

### 2.1 Naming: the engine is a suffix, so siblings sort together

Every engine-specific identifier is `game-dev-<engine>`, with underscores where Python requires them. Shared
execution infrastructure keeps generic names.

| item | `game-dev-roblox` | a later sibling |
|---|---|---|
| specialty id (declarations, profiles, evidence) | `game-dev-roblox` | `game-dev-unity` |
| core package (declarations, decisions, pure readers) | `src/squadops/specialties/game_dev_roblox/` | `.../specialties/game_dev_unity/` |
| adapter (MCP, filesystem and network I/O) | `adapters/remote_execution/game_dev_roblox_studio/` | `adapters/remote_execution/game_dev_unity_editor/` |
| prompt fragments | `src/squadops/prompts/fragments/game-dev-roblox/` | `.../fragments/game-dev-unity/` |
| playbooks | `src/squadops/specialties/game_dev_roblox/skills/` | the same, in its own package |
| operation ids | `game-dev-roblox.play_scenario` (§2.6) | `game-dev-unity.run_editmode_tests` |
| squad profiles | `game-dev-roblox` (Spark), `game-dev-roblox-lite-14b` (MacBook machinery check) | `game-dev-unity` |
| plans and records, in `docs/plans/` | `game-dev-roblox-plan.md`, `game-dev-roblox-spikes.md` | `game-dev-unity-plan.md` |
| branches | `feature/game-dev-roblox-<part>`, `docs/game-dev-roblox-<part>` | `feature/game-dev-unity-<part>` |
| issue label | `game-dev-roblox` | `game-dev-unity` |
| shared infrastructure | `ports/remote_execution/`, the worker registry, `/api/v1/workers`, the task type `qa.run_remote_operation` (§2.4) | shared |

**Content shared across engines** gets a name of its own (`game-dev-common`) only when a second engine needs it. The
test product follows the `z_` rule: `z_tower-ascension`. A designer would take its own prefix (`design-<kind>`).
`roblox-spike-2-6.md` keeps its name, because other records cite it.

### 2.2 Guardrails, so the specialty can leave as a plugin later

1. **An isolation test** (`tests/unit/architecture/test_specialty_isolation.py`) covering every place the specialty
   lives:
   - the core package;
   - the adapter directory;
   - the fragment directory;
   - the worker root's configuration section.

   **Inbound:** only the bootstrap's specialty table and the worker composition root reach them. **Outbound:**
   the core package imports core only from an allowed list, and the adapter imports only its port and that list.
   **The allowed list is the plugin interface's first draft,** written from what the specialty actually uses. The
   extraction boundary is those four places, and the test names them.
2. **No engine names in core.** Orchestration consults `TaskType` properties and tables (CLAUDE.md's task-type rules
   3 and 4), and engine specifics stay behind operation ids (§2.4).
3. **The designer test, on paper** (S5, partial pass): the specialty declaration and a squad profile describe the
   Iris design role's identity, handlers, resources, permissions and agent binding with no core change. **Its own
   kinds of authored work are the exception.** So the rule is:
   - a specialty adds operations, handlers, fragments, playbooks and resources without a core change;
   - a specialty that adds a new kind of authored work adds its task types to the central enum, in its own domain
     (`design.`), under #559's rules.

   `game-dev-roblox` is unaffected, because its new work is tool-backed and rides an operation id (§2.4).

**Where the line falls:** a *language* is core, and an *engine* is a specialty. The Luau runner (#2906) is a language
in the derived profile, like Python or JavaScript. Studio, play sessions and the place are `game-dev-roblox`.

**When the plugin machinery gets built,** recorded in the SIPs as the trigger:
- a second specialty duplicates the bootstrap wiring;
- or a specialty must ship on its own cadence;
- or someone outside the team writes one;
- **or a second specialty needs task types of its own** (S5). Then the host-owned lookup (properties, plan
  validation, routing, expected artifacts, correction mappings; §2.4) is the first piece of plugin machinery to
  build.

### 2.3 Runtime guarantees kept without plugin packaging

- **Resolved once, pinned for the Campaign.**
  - At Campaign creation, the squad profile's `specialties` field is resolved to the specialty's declaration, its
    operations and their handlers, result readers, playbooks and permissions.
  - The resolution's digest goes where a cycle's squad is already pinned: the profile snapshot
    (`compute_profile_snapshot_hash` in `cycles/lifecycle.py`, stamped as each cycle's `squad_profile_snapshot_ref`).
    That hash covers every field that decides how a cycle executes, so the profile's `specialties` field and the
    specialty's digest enter it.
  - A Campaign's bound snapshot is the precedent for a recorded re-binding: SIP-0110 Appendix A §3.7, the `rebind`
    event in `campaigns/models.py`.
  - The Spark session doesn't expect 2.7 to change either (2026-11-08).
- **Detection, since in-tree code can't be replayed.** A redeploy can't keep an old version of in-tree code running.
  So every cycle re-resolves and compares digests. A different digest stops the Campaign with a named reason. It
  never runs on a changed specialty under the old snapshot.
- **Preflight at creation:**
  - the specialty resolves;
  - its operations name a registered worker that declares them;
  - the product meets its eligibility rules (§2.10).
- **Preflight at the plan gate:** every task and operation in the plan is one the resolved specialty serves.
  Otherwise the plan is refused before dispatch.

### 2.4 Task types: one engine-neutral type, operations by id

- **The type:** a new member of the central enum, `qa.run_remote_operation`, carrying an operation id
  (`game-dev-roblox.play_scenario`) as its argument.
  - The enum stays the single home of task types, and its properties, routing and correction tables work unchanged.
  - Strings stay on the wire.
  - Writing and repairing code reuse `development.develop` and `development.repair`, with the specialty's context.
- **The operation id is resolved through the specialty table:** argument schema, provider, required worker
  capability, result reader. **Refusals:** an unknown id is refused at the plan gate, and a duplicate registration is
  refused at bootstrap.
- **Planning becomes property-driven** (read in the code for revision 3).
  - **Today:** the plan-authoring prompt offers, and the plan parser accepts, a fixed set of three task types
    (`_KNOWN_BUILD_TASK_TYPES` in `cycles/implementation_plan.py`: develop, `qa.test` and `builder.assemble`). Any
    other type is refused when the plan is parsed.
  - **So `qa.run_remote_operation` can't reach a plan as things stand,** and neither could a designer's `design.`
    types.
  - **The change** (phase 2a): a `TaskType` property marks the types a planner may offer, and the set is derived from
    it (CLAUDE.md's task-type rule 3). The resolved specialty adds which operation ids may be planned, and the plan
    gate's preflight (§2.3) checks them. Both the prompt's list and the parser's check read that one source, so they
    can't disagree (the #426 shape, where the offer and the guard drifted apart).
  - **Its scope (agreed 2026-11-08):** the property goes on today's three types and on `qa.run_remote_operation`,
    and on nothing else in this plan. Every further plannable type is its own proposal (§4).
- **Proved with a fixture first** (phase 2a), with no Studio. The fixture exercises properties, plan validation,
  routing, the expected artifacts and the correction mapping.
- **If the fixture shows a role needs its own extensible task types,** that becomes one host-owned lookup covering
  properties, plan validation, routing, expected artifacts and correction mappings. Unknown and duplicate
  registrations are refused. That's a design change to the SIPs, outside this plan.

### 2.5 Remote execution: the worker and its protocol

**Why a worker.** Studio has no Linux build and can't run headless, and its MCP server is reached only through a
local stdio proxy. So the Spark's squad reaches Studio through a worker on the MacBook. The worker connects outward,
so no port opens on the MacBook.

**The port** (`ports/remote_execution/`) and **the registry:**
- one table and its migration;
- routes under `/api/v1/workers`, conforming to `docs/architecture/api-route-lanes.md`;
- health in the standard states (`online`, `degraded`, `recovering`, `offline`), and *busy* as a lease.

**Delivery: pull, claim, result.**

| step | what happens |
|---|---|
| **register** | the worker session registers its identity, platform, tool versions and the operations it serves, and is given a worker-session id |
| **claim** | the worker asks for an assignment for an operation it serves. The registry gives at most one, with an assignment id, the operation's attempt number, a lease id and an expiry |
| **heartbeat** | renews the lease while the transaction runs |
| **result** | the worker submits a result fenced by assignment, attempt, worker-session and lease ids. A result whose ids aren't current is refused and recorded, **so a late completion never satisfies a newer attempt** |
| **cancel** | the registry marks the assignment cancelled. The worker sees it at its next heartbeat, stops, resets (below), and submits `interrupted` |
| **expiry** | an expired lease frees the assignment for a new attempt. It doesn't prove the old play session stopped, so the next claim on that worker begins with reconcile-and-reset |

- **Built on 2.7's conventions** (the Spark session, 2026-11-08):
  - **Fencing follows #2932's echo convention:** a fresh identity per dispatch, echoed in the reply; a stale reply is
    dropped and counted.
  - **It needs a durable fencing token of its own.** #2932's dispatch identity is deliberately in-memory, because a
    resume mints a new one. A worker's lease crosses the network and outlives a runtime restart, so the convention
    is reused and the storage is not.
  - **The worker's evidence goes through the vault's `store()`** and inherits #2931's durability: content is
    committed before metadata, and metadata before the index. A corrupt artifact a run needs is a typed error that
    fails or escalates the run.
- **Two outcomes kept apart:**
  - `not_executed`: failed before execution began (staging, sync, verification of the tested state);
  - `interrupted`: interrupted after the play session started.

  Neither reads as a behavioural failure or a pass.
- **The worker's authority is the assignment's, and nothing more:**
  - it reads only its assignment's input artifacts;
  - it writes only its own result and evidence;
  - it never rules a Campaign, promotes source, browses the vault or acts as an administrator.

  Its service account is scoped to those calls (D3).
- **The worker shell** is a new composition root, added to `docs/architecture/composition-roots.md`:
  - it binds the adapter through its factory, with typed configuration and a required selector (rules R1 and R2
    there);
  - a fixture adapter proves the protocol with no Studio.

### 2.6 The Studio transaction (`game-dev-roblox-studio`)

**The lease covers the whole transaction:** stage → sync → verify the tested state → play → collect → stop and
reset. Nothing else uses that Studio until the transaction ends or is reconciled.

**What each operation is bound to:**
- **the expected Studio,** re-resolved at every claim and confirmed by identity rather than by id. A restarted
  Studio gets a new id and briefly has no name (S1). So the adapter requires exactly one connected Studio, reading
  `PlaceId` 0, whose baseline digest matches the pin;
- the place file and the digest of its read-only baseline file (§2.10);
- the source manifest (path, digest and expected script class per script);
- the scenario's digest.

**Sync is the adapter's own (D10).**
- **The worker's Studio has no Script Sync link.** S1 found that links on a local place file are lost on every
  Studio restart. A link left in place would also write Studio's script edits straight to disk (0.6 s in S1).
- **The adapter writes the manifest into Studio** through a fixed sync program in its harness. For each script it
  creates the instance of the expected class at its path and sets its source. It also removes scripts the manifest
  drops, inside the three synced folders only. S1 showed `execute_luau` can do each of these.
- **The path-to-class mapping is the repository's own:** `.server.luau` → `Script`, `.local.luau` → `LocalScript`,
  anything else → `ModuleScript`. It matches what Script Sync and S2's Rojo rule assign.
- **Script Sync stays the game owners' workflow** on their own Studio. The eligibility rules keep its layout (§2.10).

**Before play, the tested state is confirmed inside Studio, not from the filesystem.**
- **The adapter reads back every script in the three folders:** contents, class and location, checked against the
  manifest, including moves and deletions.
- **The read-back is paged.** A tool result is capped at 100,000 characters and reports success when truncated, so
  pages stay under 90,000 characters and a truncated page is refused. S1 read all 137 scripts (about 1.7 MB) in
  1.6 s over 23 pages.
- A mismatch reads `not_executed` with the difference.

**The non-script baseline is pinned and checked in full.**
- **The digest covers every instance outside the three script folders,** with a stated property set per kind:
  - parts: position and rotation, size, colour, material, transparency, anchoring and collision, mesh and texture;
  - values, sounds, decals, lights and UI objects;
  - every instance's attributes and tags.
- S1 digested 22,840 instances in 7.0 s over 55 pages. The digest was stable across runs and caught a part moved
  0.01 studs.
- **It is read before play and after stop.** A difference fails the run with the change named.
- The property set is not every property; a change outside it isn't detected, and the evidence says so.

**Reset.**
- **Play state resets on stop:** a part created during play was gone afterwards (S1).
- **The edit place resets from the baseline file.** When the baseline digest doesn't match at a claim, the worker
  reopens the place from a fresh copy of the read-only baseline file. Phase 2d proves that the worker can reopen
  Studio on the file by itself. Until it does, a mismatch reads `not_executed` and needs the owner.

**Returned Studio edits are a new revision.**
- Studio is a staged execution environment, and the sandbox stays the authoritative live tree.
- With no Script Sync link, a script edit made in Studio stays in Studio. The adapter finds it at read-back and
  returns it as a file, which goes through the existing patch and footprint checks (`apply_workspace_patch`) and
  produces revision B.
- A pass on revision A never accepts B. B is synced and tested again.
- QA operations refuse unexplained source mutation: a script that changes during a QA transaction fails it.

**Typed operations, not tools:**

| operation | what it does | Studio tools behind it |
|---|---|---|
| `game-dev-roblox.sync_source` | write a source manifest into Studio and confirm it by read-back | the harness's sync program, then read-back |
| `game-dev-roblox.play_scenario` | the whole transaction for one frozen scenario | play controls, input, the harness |
| `game-dev-roblox.read_console` | collect the session's console | console output |
| `game-dev-roblox.capture` | a viewport capture as supplementary evidence | capture |

- **Validation:** each operation validates its target, its arguments, its artifact references and its paths, and
  confirms the expected Studio before it runs.
- **`execute_luau` runs only the harness's fixed programs:** sync, read-back, baseline and the frozen scenario.
  Nothing an assignment supplies runs as free code. It takes a required `datamodel_type`: `Edit`, or `Server` or
  `Client` during play.
- **The allow-list is deny-by-default.** It names the tools that write to Roblox's servers and refuses them:
  `open_cloud_invoke`, `upload_image`, `insert_asset`, `create_skill`, `edit_skill` and every `generate_*` tool.
  There is no publishing and no saving to Roblox.
- **Every call has a deadline.** A blocking Roblox call can hang a tool call indefinitely (`PreloadAsync`, twice in
  S1). So the harness makes no unbounded blocking call, and a call past its deadline reads `interrupted` or
  `not_executed` by phase.
- **The harness clears its state.** `_G` persists between calls, so the harness clears what it sets and never reads
  state it didn't set in the same call.
- **The client's input tools target the game by instance path.** S1 clicked the title screen's Play button, held a
  key, navigated the character and opened the map this way.
- Studio runs under the owner's Roblox login, and the worker holds only what the operations need.

**Capture** is supplementary. A blank capture (seen before in the prior art) reads as not looked at, and no criterion
in this plan depends on capture.

### 2.7 The assertion protocol

- **Frozen before development:** the approved scenario, its fixtures, the expected outcomes and the result reader,
  each by digest.
- **The harness** (Luau, run in the play session) emits one structured record per assertion:
  - the assertion's id;
  - the observed value;
  - the expected value;
  - the result;
  - the execution context (server or client, and which client);
  - the play-session id and the source revision.

  The reader reads only those records. **Console prose, or a print that looks like success, never establishes a
  pass.**
- **Outcomes kept apart:**

  | outcome | meaning |
  |---|---|
  | `passed` / `failed` | executed, per assertion |
  | `missing` | an assertion the scenario declares produced no record |
  | `setup_failed` | the scenario's fixtures didn't establish |
  | `unsupported_input` | the scenario needs input the worker doesn't provide |
  | `wrong_context` | an assertion ran on the server when it was declared for the client, or the reverse |

  Only `failed` is an executed behavioural failure.
- **The scenario is public QA verification.** It isn't a held-out suite, and no role gains held-out access through
  this plan.
- **What S1 showed the harness must handle:**
  - **the game opens on a title screen,** and the character waits behind it. Every scenario's setup passes it first
    (S1 clicked its Play button by instance path), and a setup that can't reads `setup_failed`;
  - **records travel through the console.** S1 read back a structured line printed by the server, with its nonce.
    Each record carries the play-session id, so a reader never takes a line from an earlier session in the same
    console;
  - **server and client are addressed separately** (`datamodel_type` `Server` or `Client`), which is how an
    assertion's context is known rather than inferred.

### 2.8 The squad

- **Profiles:**
  - `game-dev-roblox`: the Spark's roster and models, with `specialties: [game-dev-roblox]`. The field is new and is
    part of the resolution in §2.3;
  - `game-dev-roblox-lite-14b`: the same on the MacBook. It checks machinery only.
- **The roles** keep their identities (#2841 §5):
  - strategy: change requests with frozen scenarios;
  - dev: Luau inside the footprint;
  - QA: logic tests, `qa.run_remote_operation`, and a statement of what wasn't executed;
  - builder: the source manifest;
  - data: measurements from executed runs;
  - lead: recommendations only.
- **Playbooks** follow #2841's Q47 ruling: a frontier model drafts, the owner approves, and each is replay-tested on
  the intended runtime models, including on a missing prerequisite, where it must stop with a named reason.
- **What S6 puts in them** (six samples from the Spark's 27b model; correct Luau and Roblox API use in all six):
  - **the specialty ships the test loader** for instance-tree requires (S2's design, run under Lune) and a convention
    for where tests live. Both of S6's test files ran nowhere as delivered: one was a Studio script outside the synced
    folders, and the other wrote the loader in Lua 5.x;
  - **each task's context includes the module that owns its concept.** S6's one logic error, the same in both samples
    of one task, came from a missing helper module, not from reasoning;
  - **the emission parser tolerates the two broken formats** S6 saw on a three-file change: no fences, and the path
    line outside its fence;
  - **change requests ask for effects on saved state at deploy.** Neither sample of the server task named that a new
    kind reshuffles the period's seeded set, which saved progress then restores by index.

### 2.9 The headless half

#2906's gaps:
- a `luau` runner kind;
- a test-id reader for the pinned output;
- a Luau worked example;
- optionally, `lute check` as a lint tool.

They're core, built on this plan's feature branch for 2.8.

### 2.10 The product: a private copy of Tower Ascension

- **The real game is live,** with players' saves and a merge hook that posts to its players. The owner's ruling of
  2026-10-21 (nothing pushed to real products until the framework is solid) applies.
- **The squad works on `backspring-labs/z_tower-ascension`,** a private copy (created 2026-11-08). Nothing flows back
  to the real repository under this plan.
- **Its place is a local file, not a test universe (D2).**
  - It was downloaded from the game with File → Download a Copy, once, by the owner, and is opened from disk.
  - **It is disconnected:** `PlaceId`, `GameId` and `CreatorId` read 0, and the game's own startup turns saving off
    without DataStore access. So a play session can't write save data, and nothing on the MacBook can publish it by
    accident.
  - **Its read-only baseline file is the reset point** (§2.6), recorded by digest.
  - **Assets load:** the place uses the owner's Studio login. In S1 every sound decoded on the client and the meshes
    rendered.
- **Removed from the copy** (the sweep, recorded in the spike record):
  - `.github/workflows/discord-update-log.yml` and its webhook secret;
  - two asset-upload scripts that publish to Roblox under the real account.

  `HttpService`'s one use generates a GUID with no network call, so it stays.
- **The copy follows the game, not only its repository.** S1 found the live game carrying 5 scripts newer than the
  repository's `main`. The copy's repository took the game's versions, so the place and the source agree. Any later
  refresh of the copy repeats that comparison and records it.
- **Eligibility rules, checked at preflight:**
  - the Script Sync layout as it is (`src/Server`, `src/Shared`, `src/Client`, `.local.luau` for LocalScripts;
    #2405 §R2.8). The adapter syncs by the same mapping (§2.6), and the game owners keep Script Sync;
  - no attributes or tags on scripts, which Script Sync wouldn't carry for the owners;
  - a footprint of scripts and runtime-created instances only.
- **What it brings:**
  - no tests yet: the squad writes the first ones;
  - mostly engine-coupled code: Studio carries most verification;
  - about 1.7 MB of Luau: the size preflight (H.21) applies, and context selection is measured, not assumed (§3,
    the full-path gate).

## 3. Phases

| phase | what | size | where | exit |
|---|---|---|---|---|
| **0. spikes** | **done 2026-11-08:** S1, S2, S4–S6; nothing merged | S each | MacBook, except S6 | the spike record, `game-dev-roblox-spikes.md` beside this plan, ended at the gate: go (§3a) |
| **1. revision 3 of both SIPs** | §2's design, the spike answers and the reconciliation of prior rulings (§8) | M (prose) | MacBook | the owner's renewed review |
| **2a. the fixture path** | the specialty table and declaration, `qa.run_remote_operation` and operation ids, **the plannable property and the derived planner set (§2.4)**, the digest pin and both preflights, the isolation test, the profile field, a fixture specialty | M | MacBook | the fixture proves properties, plan validation, routing, expected artifacts and the correction mapping; a plan naming an operation the specialty doesn't serve is refused |
| **2b. remote execution** | the port, the registry and its migration, `/api/v1/workers`, the claim/lease/fence protocol, the worker root, the fixture adapter | M–L | MacBook (code); Spark (migration deploy, 2.8 only) | the fixture operation runs end to end; a cancelled, expired or late attempt is refused or reconciled as §2.5 says |
| **2c. the Luau runner** | #2906 | M | MacBook, on the feature branch | a `*.spec.luau` failure is read per test |
| **2d. the Studio adapter** | §2.6's transaction: identity by PlaceId and digest, the adapter's own sync, paged read-back, the full baseline before and after play, reset from the baseline file (including reopening Studio on it), deadlines, the deny list, returned edits as revisions, the four typed operations | L | MacBook | each operation proved on the worker, including after a Studio restart with no person involved. A mode not proved reads not executed (#2405 §R2.4) |
| **2e. the assertion harness and reader** | §2.7 | M | MacBook | every outcome in §2.7 produced on purpose and read correctly |
| **2f. the squad** | the profiles, fragments and playbooks (with S6's items, §2.8), the test loader, the tolerant emission parser, and the replay tests | M | MacBook | the playbooks pass replay on the Spark's models |
| **2g. the product** | §2.10's copy and sweep (done in phase 0), the place file and its baseline (done), eligibility, registration and the goal set | S | MacBook | a Campaign on it passes preflight |
| **3. the demonstration** | **full-path gate first:** representative tasks through the real prompt budget, scoped context, playbook loading and reader, with context selection measured. Then a machinery rehearsal on `game-dev-roblox-lite-14b`, the pre-registered repair diagnostic, and the counted two-increment run on the Spark, handed over as a run plan | M | MacBook, then Spark | §1 read live |

**Phase 2 is gated by 2a.** The fixture path comes first, then Studio execution (2b, 2d, 2e), then squad-driven
development (2f, 3). Discovery, installation, external packaging and plugin lifecycle machinery stay deferred
throughout.

### Phase 0: the spikes (done)

All five ran on 2026-11-08. The record is `game-dev-roblox-spikes.md` in `docs/plans/`.

| spike | the answer |
|---|---|
| **S1. the Studio transaction** | **play, input and read-back proven** on a local copy of the game; the full script read-back (1.6 s) and the full baseline digest (7.0 s) both fit a run, so the scoped fallback isn't needed; Script Sync's links are lost on a Studio restart (D10) |
| **S2. Rojo and Script Sync** | one sync rule gives `.local.luau` the `LocalScript` class Studio assigns; the game's instance-tree requires need a loader to run under Lune |
| **S4. the network path** | the MacBook reaches the Spark's runtime API outward over Tailscale, with no port opened on the MacBook |
| **S5. the designer test** | a partial pass; new kinds of authored work need central task types (§2.2) |
| **S6. a first Luau probe** | correct Luau and Roblox API use in six of six samples; the weak spots are things the specialty supplies (§2.8). A first probe, not a rate |

(S3, revision 1's Open Cloud spike, left the plan: §4.)

### 3a. The spike gate

**The outcome: go (2026-11-08).** S1 proved play, input and read-back, and the owner accepted D1–D10 the same
day. The criteria the record was read against:
- **go:** S1 proves play, input and read-back. The claim stands (§1).
- **narrow:** S1 proves engine assertions in a play session without input, or read-back with gaps, or the full
  baseline digest and read-back are too slow per run and the scoped fallback is proposed. The claim or the tested-state
  check narrows as §1 and S1 say, and the narrowing is written into revision 3.
- **stop:** S1 can't confirm the tested state inside Studio, or a play session can't be reset reliably. The plan
  returns to the owner with what was found. The headless half (#2906) can proceed alone.

## 4. Not in this plan

- the plugin machinery (§2.2's trigger), `game-dev-unity` and `game-dev-godot`;
- `game-dev-common` content;
- **Open Cloud Luau execution:** later research. If taken up, it needs its own spike, scoped credentials and an
  explicit owner authorization to publish to the isolated test place only. A successful API call doesn't add a
  driver;
- publishing to Roblox, and any write to the real Tower Ascension repository or game;
- multiplayer play, judging feel or visuals, and changes to parts, models or UI built in Studio;
- console views for the worker;
- **more plannable task types than `qa.run_remote_operation`.** Phase 2a builds the property that makes a type
  plannable (§2.4) and sets it on the four that need it. Each further type is its own proposal, with its handler,
  expected artifacts, footprint rules, correction mapping and every verifier seam that judges it, because a planned
  type changes planning for every product. A designer's `design.` types are the expected next case;
- Script Sync in the worker's Studio (D10).

## 5. Lanes, 2.7, and the Spark session

**The MacBook lane** builds phases 0–2 in a worktree and rehearses phase 3. **The counted run is the Spark's,**
handed over as a run plan.

**During 2.7** (feature-free, D6):
- **outside 2.7's runtime:** feature merges, migrations, profile activation, worker registration and deployment;
- **allowed:** the MacBook worktree, local rehearsals and prose PRs;
- **no dark merge** because 2.7 runs long.

**Shared state is shared across worktrees too.** A separate worktree doesn't isolate:
- the MacBook stack's Postgres and profile registry;
- prompt mounts and model settings;
- the copy's place file and its baseline file.

So local rehearsals run only while the MacBook stack isn't producing evidence for anything else. Compose runs from
the main checkout with `--no-deps`; running `up` from a worktree took Postgres down on 2026-10-18. Specialty
profiles and worker registrations exist only in that local stack until 2.8.

**Settled with the Spark session (2026-11-08),** answering this plan's note. The 2.7 plan is #2971.
- **Files 2.7 is expected to change** (each PR lists its own):

  | file or package | issue |
  |---|---|
  | `projects/profile_derivation.py` | #2775 |
  | `prompts/` (the manifest and stamp regenerate) | #2933, #2935 |
  | `execution/dispatched_flow_executor.py`, `execution/reply_router.py` | #2932, #2949 |
  | `campaigns/` | R3's control-log allowance, #2783 |
  | `adapters/cycles/filesystem_artifact_vault.py` | #2931, then the filtered-listing index (#2973) |
  | `capabilities/handlers/route_rendering.py` | #2776 |
  | `adapters/sandbox/scenario_runner.py` | #2798 |
  | `squadops.embeddings`, removed | #2736 |

- **Expected unchanged:** `orchestration/handler_registry.py`, `bootstrap/handlers.py`, `tasks/task_types.py`,
  `sandbox/findings` and the profile snapshot hash.
- **A wire-contract change to build on:** the task envelope and the reply payload gain a dispatch identity (#2932).
  `qa.run_remote_operation` carries it.
- **Shared contracts:** #2932 and #2931, as §2.5 uses them.
- **S6 ran** in 2.7's early build window, before the pinned deploy, from a run plan, on TensorFold with the deployed
  options. Its outputs came back by message, and the Spark's copies were deleted afterwards.
- **The 2.7 plan's §5a** records Q45 and Q46 as ruled on 2026-10-31, the open question as whether revision 3
  replaces their foundation (§8), and this plan as a 2.8 input, unplaced.
- **2.8:** recorded as the MacBook lane's input to the 2.8 plan's draft: the demonstration's gate and counted run,
  and the worker registry's migration deploy when 2.8 opens. The slot is the owner's ruling.

## 6. Risks

| risk | what it would do | the response |
|---|---|---|
| Studio's MCP server changes with Studio's updates | a tool's name, schema or behaviour changes under the worker | the worker registers its Studio version and its tool schemas' digest; operations pin what they were proved on and read not executed on a mismatch |
| a blocking call hangs a tool call | a transaction never returns | a deadline on every call, and no unbounded blocking call in the harness (§2.6) |
| Studio restarts | a link or an id the worker relied on is gone | the adapter owns sync (D10) and confirms Studio by PlaceId and digest; phase 2d's exit includes a restart |
| Studio is the owner's interactive app | the worker is unavailable while the owner uses it or the MacBook sleeps | outward connection, leases, `blocked_unverified`; runs scheduled for free time |
| an interrupted play session survives | the next attempt tests a dirty state | reconcile-and-reset at every claim after an expiry or cancel (§2.5) |
| the Spark's models write weak Luau | increments fail framing or the scenario | S6, then the playbooks, then the full-path gate; the claim is two increments, not a rate |
| the code is mostly engine-coupled | few headless tests | increments chosen so their criteria are observable through harness assertions |
| a long branch during 2.7 | rebase cost | the isolation boundary keeps the change to four named places, one table and one port |
| the copy keeps a production integration | a merge on the copy reaches real players | the sweep in §2.10, recorded in the spike record, done |
| the live game moves ahead of the copy | the squad builds on stale source | the copy is compared with the game at each refresh, and the difference recorded (§2.10) |

## 7. Decisions for the owner

**All ten accepted by the owner on 2026-11-08** ("accept D1-D10, write revision 3"), with the planner's scope agreed
the same day ("agree, finish revision 3": §2.4, §4).

| # | decision | accepted |
|---|---|---|
| D1 | the claim (§1) | **two small accepted increments on the private copy,** as written: S1 proved the play and input mode. The repair diagnostic is separate from counted evidence |
| D2 | the product | **`z_tower-ascension` with a local, disconnected place file** (PlaceId 0, saving off), reset from a read-only baseline file, and hooks, credentials and integrations removed (§2.10). No test universe |
| D3 | the worker's identity | **a worker-only service account** with assignment-scoped permissions (§2.5). It doesn't authorize interactive MacBook sessions to operate the Spark |
| D4 | Open Cloud | **out of this plan** (§4). A later, separate authorization if wanted, with an explicit test-place publishing exception and scoped credentials |
| D5 | Studio authority | **typed, deny-by-default operations,** with target, argument, artifact, path and execution-context validation, and `execute_luau` only through the harness (§2.6) |
| D6 | parallel development | **the MacBook worktree and local rehearsals approved.** Merges, migrations, profile activation, worker registration and deployment stay out of 2.7's runtime; no dark merge |
| D7 | task types | **one engine-neutral task type with operation ids** (§2.4), proved with a fixture first, and **planning made property-driven** so the type can reach a plan. An extensible host-owned lookup only if the fixture shows it's needed, as a design change |
| D8 | naming (§2.1) | **`game-dev-<engine>` for specialty identifiers,** generic names for shared execution infrastructure |
| D9 | the SIPs | **keep the two-document split;** revise their normative sections and ledgers after the spikes, reconcile the prior rulings (§8), and accept after renewed review |
| D10 | the worker's sync path | **the adapter owns sync:** it writes the manifest's scripts into Studio through its fixed harness and confirms them by read-back. No Script Sync link in the worker's Studio, since links on a local place are lost on every restart. Script Sync stays the game owners' workflow (§2.6) |

## 8. Reconciling the recorded commitments

Revision 3 of both SIPs states, for each:

| commitment | recorded | what revision 3 does |
|---|---|---|
| **Q45** (#2841 §9): the foundation (F1) may precede 3.x, through a recorded amendment in Capability-Backed Agents, without placing it | ruled 2026-10-31 | **replaced:** F1 shrinks to §2's in-tree seam. Whether Capability-Backed Agents still needs its amendment, or only a note naming this seam as the starting point of its §17 split, is the owner's ruling |
| **Q46**: Switchboard as the loader | ruled 2026-10-31 | **deferred, not reversed:** Switchboard stays the presumptive loader when §2.2's trigger fires. No loader is built in this plan |
| #2405 §R2.3: plugin registration (manifest, `requires_spi`, provider pins) | revision 2 | **deferred to the trigger.** Provider and reader pins become the specialty digest (§2.3) |
| #2405 §R2.2: the remote-execution contract | revision 2 | **kept and specified** (§2.5) |
| #2405 §R2.6 and §R2.7 | revision 2 | **kept and strengthened** (§2.6). Where they assume Script Sync carries the candidate into Studio, revision 3 says the adapter does (D10) |
| #2405's test universe or test place, wherever it appears | revision 2 | **replaced** by the local place file (D2, §2.10) |
| #2841 §4: F1's runtime guarantees (bindings, preflight, the Campaign snapshot) | revision 0 | **kept** (§2.3) |
| #2841 §7: the demonstration | revision 0 | **revised:** the counted claim and the repair diagnostic split (§1) |
| both delivery ledgers | 2026-10-31 | **re-cut** to phases 2a–2g and 3. Rows stay unplaced until the 2.8 plan places them with issues |

**Runtime guarantees retained:** the digest pin, both preflights, SIP-0096's verdict vocabulary, the worker's
authority limits and the revision boundary.
