# game-dev-roblox plan — a squad that develops and tests a Roblox game

**Status: DRAFT, revision 2 (2026-11-08), unplaced.** The MacBook lane's input to the 2.8 plan, for the owner's
review. Nothing here is placed or accepted:
- Placement is the 2.8 plan's.
- Phase 0's spikes are a feasibility study. Their record ends at a decision gate (§3a), and phases 1–3 are adopted
  only past it.
- Approving the spikes doesn't accept either game SIP. Acceptance follows revision 3 of both and a renewed review (§8).

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

**What it builds on.**
- The two proposed game SIPs: *Game Development Platform Capability* (PR #2405) and *Game Development Capability
  Packs and Squad Composition* (PR #2841, stacked on it).
- The 2.6 Roblox spike (`docs/plans/roblox-spike-2-6.md`, #2895): pure-Luau logic tests run headless on the Spark
  under Lune, and anything that touches the engine needs Studio. Its gaps are #2906.
- Prior art on the MacBook: a working client for Roblox Studio's built-in MCP server, in the target game's
  repository (`art/studio-bridge/studio_mcp.py`). S1 re-verifies the installed tools and their schemas rather than
  rely on that client's inventory.

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

**Conditional on S1:**
- If S1 proves play controls and input in a play session, the claim stands as written.
- If S1 proves only assertions on the engine run inside a play session, with no input, the claim narrows to that
  before the run is pre-registered.

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
3. **The designer test, on paper** (S5): the specialty declaration and a squad profile can describe the Iris design
   role with no core change. If they can't, the seam is wrong.

**Where the line falls:** a *language* is core, and an *engine* is a specialty. The Luau runner (#2906) is a language
in the derived profile, like Python or JavaScript. Studio, play sessions and the place are `game-dev-roblox`.

**When the plugin machinery gets built,** recorded in the SIPs as the trigger:
- a second specialty duplicates the bootstrap wiring;
- or a specialty must ship on its own cadence;
- or someone outside the team writes one.

### 2.3 Runtime guarantees kept without plugin packaging

- **Resolved once, pinned for the Campaign.**
  - At Campaign creation, the squad profile's `specialties` field is resolved to the specialty's declaration, its
    operations and their handlers, result readers, playbooks and permissions.
  - The resolution's digest goes in the Campaign snapshot, beside the fragment hashes the prompt stamp already
    records.
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
- the expected Studio instance (`studio_id`);
- the test universe and place;
- the base place version or snapshot;
- the source manifest (path, digest and expected script class per script);
- the scenario's digest.

**Before play, the tested state is confirmed inside Studio, not from the filesystem.**
- The adapter reads back, through Studio, every synced script's contents, class and location, and checks moves and
  deletions against the manifest.
- A filesystem notification is not confirmation.
- A mismatch reads `not_executed` with the difference.

**The non-script baseline is pinned.** The place's parts, models, properties and assets are recorded as a baseline
digest. A change to them during verification fails the run with the change named.

**Script Sync's cases, exercised in S1:**
- create, rename and delete;
- reconnecting after Studio restarts;
- a conflicting edit. Script Sync can stop for manual conflict resolution, and that reads `not_executed` with the
  reason.

Script Sync preserves no attributes or tags on scripts, so that limit is an eligibility rule (§2.10).

**Returned Studio edits are a new revision.**
- Studio is a staged execution environment, and the sandbox stays the authoritative live tree.
- Script edits captured in Studio come back as files and go through the existing patch and footprint checks
  (`apply_workspace_patch`), producing revision B.
- A pass on revision A never accepts B. B is synced and tested again.
- QA operations refuse unexplained source mutation: a script that changes during a QA transaction fails it.

**Typed operations, not tools:**

| operation | what it does | Studio tools behind it |
|---|---|---|
| `game-dev-roblox.sync_source` | sync a source manifest and confirm it in Studio | Script Sync folder writes, then read-back |
| `game-dev-roblox.play_scenario` | the whole transaction for one frozen scenario | play controls, input, the harness |
| `game-dev-roblox.read_console` | collect the session's console | console output |
| `game-dev-roblox.capture` | a viewport capture as supplementary evidence | capture |

- Each operation validates its target, its arguments, its artifact references and its paths, and checks the
  expected universe and place before it runs.
- `execute_luau` is reachable only through the approved harness. It runs the frozen scenario and nothing an
  assignment supplies as free code.
- The allow-list is deny-by-default: no publishing, no saving to Roblox, no asset generation.
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
- **The squad works on `backspring-labs/z_tower-ascension`,** a private copy with **its own Roblox test universe and
  place**. Nothing flows back to the real repository under this plan.
- **What's removed from the copy before registration** (a separate universe doesn't isolate them):
  - `.github/workflows/discord-update-log.yml` and its webhook secret;
  - any other workflow, credential or outbound integration the copy carries, found by a sweep recorded in the spike
    record;
  - DataStore and HTTP integrations, confirmed to reach only the test universe.
- **The baseline:** the copy's test place is created from a recorded base, and its non-script baseline digest is
  pinned (§2.6). Asset ids owned by the real universe may not load in the test universe. S1 checks that, and the
  copy's eligibility records which load.
- **Eligibility rules, checked at preflight:**
  - the Script Sync layout as it is (`src/Server`, `src/Shared`, `src/Client`, `.local.luau` for LocalScripts;
    #2405 §R2.8);
  - no attributes or tags on scripts;
  - a footprint of scripts and runtime-created instances only.
- **What it brings:**
  - no tests yet: the squad writes the first ones;
  - mostly engine-coupled code: Studio carries most verification;
  - about 1.7 MB of Luau: the size preflight (H.21) applies, and context selection is measured, not assumed (§3,
    the full-path gate).

## 3. Phases

| phase | what | size | where | exit |
|---|---|---|---|---|
| **0. spikes** | S1, S2, S4–S6 below; nothing merges | S each | MacBook, except S6 | the spike record, `game-dev-roblox-spikes.md` beside this plan, ending at the gate (§3a) |
| **1. revision 3 of both SIPs** | §2's design, the spike answers and the reconciliation of prior rulings (§8) | M (prose) | MacBook | the owner's renewed review |
| **2a. the fixture path** | the specialty table and declaration, `qa.run_remote_operation` and operation ids, the digest pin and both preflights, the isolation test, the profile field, a fixture specialty | M | MacBook | the fixture proves properties, plan validation, routing, expected artifacts and the correction mapping |
| **2b. remote execution** | the port, the registry and its migration, `/api/v1/workers`, the claim/lease/fence protocol, the worker root, the fixture adapter | M–L | MacBook (code); Spark (migration deploy, 2.8 only) | the fixture operation runs end to end; a cancelled, expired or late attempt is refused or reconciled as §2.5 says |
| **2c. the Luau runner** | #2906 | M | MacBook, on the feature branch | a `*.spec.luau` failure is read per test |
| **2d. the Studio adapter** | §2.6's transaction, its bindings, read-back, baseline, Script Sync cases, returned edits as revisions, the four typed operations | L | MacBook | each operation proved on the worker. A mode not proved reads not executed (#2405 §R2.4) |
| **2e. the assertion harness and reader** | §2.7 | M | MacBook | every outcome in §2.7 produced on purpose and read correctly |
| **2f. the squad** | the profiles, fragments and playbooks, with their replay tests | M | MacBook | the playbooks pass replay on the Spark's models |
| **2g. the product** | §2.10's copy, sweep, test place, baseline, eligibility, registration and goal set | S | MacBook (the owner provisions) | a Campaign on it passes preflight |
| **3. the demonstration** | **full-path gate first:** representative tasks through the real prompt budget, scoped context, playbook loading and reader, with context selection measured. Then a machinery rehearsal on `game-dev-roblox-lite-14b`, the pre-registered repair diagnostic, and the counted two-increment run on the Spark, handed over as a run plan | M | MacBook, then Spark | §1 read live |

**Phase 2 is gated by 2a.** The fixture path comes first, then Studio execution (2b, 2d, 2e), then squad-driven
development (2f, 3). Discovery, installation, external packaging and plugin lifecycle machinery stay deferred
throughout.

### Phase 0: the spikes

| spike | question | needs |
|---|---|---|
| **S1. the Studio transaction** | the installed MCP tools and their schemas, re-verified (`studio_id` targeting, play controls, keyboard and mouse input, character navigation, console, capture); sync and read-back of scripts' contents and classes; Script Sync's create, rename, delete, reconnect and conflict cases; whether a play session runs unattended; reset after an interrupted session; whether the real universe's assets load in a test universe. **The cost of §2.6's two checks, measured on the copy's full place:** the non-script baseline digest (parts, models, properties) and the in-Studio read-back of every synced script (about 1.7 MB of Luau), each timed per run. If either is too slow for a run, the fallback is read-back of the scripts the increment's manifest touches plus a coarse place digest. That fallback is a narrowing, put to the owner at the gate (§3a), never taken silently | Studio on the MacBook, the copy's test place open |
| **S2. Rojo and Script Sync** | does a Rojo build of the Script Sync layout produce the right script classes (`.local.luau` in particular)? It informs the source manifest's expected classes | nothing |
| **S4. the network path** | can a process on the MacBook reach the Spark's runtime API outward, and over which path? Reachability only, no credentials | nothing |
| **S5. the designer test** | §2.2's guardrail 3, on paper | nothing |
| **S6. a first Luau probe** | three representative Tower Ascension tasks prompted to the Spark's models: is the Luau passable, and which Roblox APIs do they get wrong? It informs the playbooks. **Labelled a first probe:** it can't measure context selection or establish a quality rate; phase 3's full-path gate does that | about 30 minutes of Spark box time, run by the Spark session outside 2.7's soak and evidence windows |

(S3, revision 1's Open Cloud spike, left the plan: §4.)

### 3a. The spike gate

The spike record ends with one of three outcomes, put to the owner before phases 1–3 are adopted:
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
- console views for the worker.

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
- Studio's sync directories.

So local rehearsals run only while the MacBook stack isn't producing evidence for anything else. Compose runs from
the main checkout with `--no-deps`; running `up` from a worktree took Postgres down on 2026-10-18. Specialty
profiles and worker registrations exist only in that local stack until 2.8.

**Contracts shared with 2.7's branches:** reuse 2.7's dispatch-freshness conventions and artifact durability
behaviour as they land, rather than building competing versions. The Spark session names which.

**What to settle with the Spark session:** the note beside this plan's PR. In short:
- 2.7's restructured files;
- the shared contracts;
- S6's box time;
- the 2.7 plan's §5a entry;
- the demonstration's slot in 2.8.

## 6. Risks

| risk | what it would do | the response |
|---|---|---|
| Script Sync is a Studio beta feature | a Studio update changes or removes it | the worker registers its Studio version; operations pin what they were proved on and read not executed on a mismatch |
| Studio is the owner's interactive app | the worker is unavailable while the owner uses it or the MacBook sleeps | outward connection, leases, `blocked_unverified`; runs scheduled for free time |
| an interrupted play session survives | the next attempt tests a dirty state | reconcile-and-reset at every claim after an expiry or cancel (§2.5) |
| the Spark's models write weak Luau | increments fail framing or the scenario | S6, then the playbooks, then the full-path gate; the claim is two increments, not a rate |
| the code is mostly engine-coupled | few headless tests | increments chosen so their criteria are observable through harness assertions |
| a long branch during 2.7 | rebase cost | the isolation boundary keeps the change to four named places, one table and one port |
| the copy keeps a production integration | a merge on the copy reaches real players | the sweep in §2.10, recorded in the spike record, before registration |

## 7. Decisions for the owner

| # | decision | recommendation |
|---|---|---|
| D1 | the claim (§1) | **two small accepted increments on the private copy,** conditional on S1 proving the play and input mode; narrowed if only engine assertions are available. The repair diagnostic is separate from counted evidence |
| D2 | the product | **`z_tower-ascension` with its own test universe and place,** a pinned place baseline, and hooks, credentials and integrations removed or isolated (§2.10) |
| D3 | the worker's identity | **a worker-only service account** with assignment-scoped permissions (§2.5). It doesn't authorize interactive MacBook sessions to operate the Spark |
| D4 | Open Cloud | **out of this plan** (§4). A later, separate authorization if wanted, with an explicit test-place publishing exception and scoped credentials |
| D5 | Studio authority | **typed, deny-by-default operations,** with target, argument, artifact, path and execution-context validation, and `execute_luau` only through the harness (§2.6) |
| D6 | parallel development | **the MacBook worktree and local rehearsals approved.** Merges, migrations, profile activation, worker registration and deployment stay out of 2.7's runtime; no dark merge |
| D7 | task types | **one engine-neutral task type with operation ids** (§2.4), proved with a fixture first. An extensible host-owned lookup only if the fixture shows it's needed, as a design change |
| D8 | naming (§2.1) | **`game-dev-<engine>` for specialty identifiers,** generic names for shared execution infrastructure |
| D9 | the SIPs | **keep the two-document split;** revise their normative sections and ledgers after the spikes, reconcile the prior rulings (§8), and accept after renewed review |

## 8. Reconciling the recorded commitments

Revision 3 of both SIPs states, for each:

| commitment | recorded | what revision 3 does |
|---|---|---|
| **Q45** (#2841 §9): the foundation (F1) may precede 3.x, through a recorded amendment in Capability-Backed Agents, without placing it | ruled 2026-10-31 | **replaced:** F1 shrinks to §2's in-tree seam. Whether Capability-Backed Agents still needs its amendment, or only a note naming this seam as the starting point of its §17 split, is the owner's ruling |
| **Q46**: Switchboard as the loader | ruled 2026-10-31 | **deferred, not reversed:** Switchboard stays the presumptive loader when §2.2's trigger fires. No loader is built in this plan |
| #2405 §R2.3: plugin registration (manifest, `requires_spi`, provider pins) | revision 2 | **deferred to the trigger.** Provider and reader pins become the specialty digest (§2.3) |
| #2405 §R2.2: the remote-execution contract | revision 2 | **kept and specified** (§2.5) |
| #2405 §R2.6 and §R2.7 | revision 2 | **kept and strengthened** (§2.6) |
| #2841 §4: F1's runtime guarantees (bindings, preflight, the Campaign snapshot) | revision 0 | **kept** (§2.3) |
| #2841 §7: the demonstration | revision 0 | **revised:** the counted claim and the repair diagnostic split (§1) |
| both delivery ledgers | 2026-10-31 | **re-cut** to phases 2a–2g and 3. Rows stay unplaced until the 2.8 plan places them with issues |

**Runtime guarantees retained:** the digest pin, both preflights, SIP-0096's verdict vocabulary, the worker's
authority limits and the revision boundary.
