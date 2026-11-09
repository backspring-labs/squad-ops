---
sip_uid: '17934561107767162'
title: Game Development Capability Packs and Squad Composition
status: proposed
author: Jason Ladd
created_at: '2026-10-31T00:00:00Z'
---

# SIP: Game Development Capability Packs and Squad Composition

**Status:** Proposed (2026-10-31), for design review. **Revision 3 (2026-11-08):** the composition on an in-tree seam, after the game-dev-roblox plan's spikes and the owner's D1–D10 (§R3, which governs where the body differs). **Revision 4 pending (2026-11-09):** Agent Skillsets (PR #3006), split from Capability-Backed Agents on the owner's direction, replaces §R3's in-tree seam: the composition becomes the squad profile plus the skillsets the `game_dev_roblox` development profile assigns to roles, and the specialty's *playbooks* become skills (*playbook* is kept for what a squad follows). §R3 reads as superseded wherever Agent Skillsets differs, and nothing here is built until the owner's outside review of Agent Skillsets and its acceptance
**Authors:** Jason Ladd (the owner's outside review, 2026-10-31); drafted by the Spark lane's supervisor
**Created:** 2026-10-31
**Targets:** unplaced. Acceptance and release placement are the owner's.
**Companion:** Game Development Platform Capability (`SIP-Game-Development-Platform.md`, PR #2405), revision 3:
how an engine is integrated. This SIP is how a squad uses it.
**Builds on:** Capability-Backed Agents (proposed, deferred to 3.x: its §21 taxonomy, §25c and §27);
SIP-0112 (Project Lifecycle Management); SIP-0114 (request-profile taxonomy); SIP-0109 (Campaign
Orchestration); SIP-0095 (cycle-create preflight); SIP-0096 (verification evidence); SIP-0105 (stack
blueprints)

## Intake check

Checked 2026-10-31 against `sips/PORTFOLIO.md`. **Conflicts:** one, for the owner (Q45). **Overlaps,** each
with its boundary (portfolio cluster 18, Q45–Q48):
- **Capability-Backed Agents** (cluster 8, deferred to 3.x on 2026-10-04: "move them to 3.x including
  capability-backed agents"). **The conflict:** this SIP needs a first slice of that SIP's foundation before
  3.x. **The boundary proposed:** this SIP takes the smallest cycle-bound foundation (§4) and nothing else of
  that umbrella: no duty-shaped capabilities, no working-set memory authority, no console surfaces. The
  umbrella stays deferred for the rest, and its §17 split would start from this foundation. **Corrections it
  needs,** recorded in its own header by this PR: its §5 extends the SIP-0040 skill layer, which was deleted
  (#400, #401). Its §21 taxonomy (identity, capability, skill, tool) is what this SIP builds on, and §5's
  premise isn't.
- **The game SIP's engine plugins** (cluster 18). **Boundary:** an engine plugin provides typed operations,
  workers and result readers. A capability pack provides what a role does with them: prompt guidance,
  skills, which operations it may invoke, the artifacts it owes and the checks that judge them. Both are
  discovered, versioned and pinned by §4's one foundation.
- **Squad profiles** (`config/squad-profiles.yaml`: the roster and its models). **Boundary:** a profile
  references a composition by name and version (§6). It doesn't restate the composition.
- **SIP-0114's request profiles** (the workflow). **Boundary:** independently selectable; a composition never
  selects a workflow, nor a workflow a composition.
- **SIP-0112 and Project Goals and Backlog** (clusters 14 and 16). **Boundary:** the game's brief, goals,
  source, assets and acceptance criteria are the Project's. A pack holds no game content.
- **SIP-0110's project instructions.** **Boundary:** a skill is reusable expertise a pack ships, never a
  project instruction. A Project's own conventions stay SIP-0110's.
- **SIP-0105's blueprints.** **Boundary:** a greenfield game's scaffold is the engine plugin's blueprint (the
  game SIP's R2.8). A pack ships no scaffold.

**Revision 3's intake (2026-11-08).** It follows the game-dev-roblox plan (PR #2972), adopted by the owner with
D1–D10.
- **The conflict this intake recorded (Q45) is replaced** (R3.1): nothing of Capability-Backed Agents' mechanism is
  built. Whether that SIP takes an amendment or a note was Q51: first ruled the note, then re-ruled on 2026-11-09 as an amendment, by the split into Agent Skillsets.
- **Overlaps, no conflict:**
  - SIP-0110's Campaign snapshot and `rebind` event, the precedent for the specialty digest;
  - CLAUDE.md's task-type rules (#559), which the `design.` domain and the plannable property follow;
  - the planner's fixed set of task types (`cycles/implementation_plan.py`), made property-driven (R3.2).

## Delivery ledger (current as of 2026-11-08)

The rows follow the adopted plan's phases (R3.6). The 2.8 plan places them, so none is placed yet.

| part | status | where |
|---|---|---|
| F1 as revision 2 cut it (§4: Switchboard discovery, manifests, the SPI) | **dropped** by Revision 3 (R3.1): replaced by phase 2a's in-tree seam | — |
| F2 and F3 as separate packs | **dropped** by Revision 3 (R3.2): one specialty, `game-dev-roblox`, until a second engine needs shared content | — |
| Phase 2a: the seam: the specialty table and declaration, `qa.run_remote_operation` and operation ids, the plannable property, the digest pin and both preflights, the isolation test, the profile field, a fixture specialty (R3.1, R3.2) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 2f: the squad: the profiles, fragments and playbooks with their replay tests, the test loader, the tolerant emission parser (R3.2, R3.4; replaces F2–F4) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 2g: the product: `z_tower-ascension`'s eligibility, registration and goal set; its copy, sweep and place file already exist | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 3: the demonstration: the full-path gate, the rehearsal, the repair diagnostic and the counted two-increment run (R3.5; replaces F5) | **unplaced**, deliberately: the 2.8 plan places it | — |
| F6: Unity, as the check that the specialty boundary generalizes across engines | **unplaced**, deliberately: after phase 3 | — |

**What closes this SIP:** phases 2a, 2f, 2g and 3 shipped, with §8's "the squad can build and improve a playable
game" read live (R3.5). F6 shipped or dropped by a numbered amendment.

---

## R3. Revision 3 (2026-11-08): the composition on an in-tree seam

**What prompted it.** The owner asked for game development proved without building a plugin architecture first,
and without closing the door on other specialists such as a designer. The game-dev-roblox plan
(`docs/plans/game-dev-roblox-plan.md`, PR #2972) is that design. Its spikes ran on 2026-11-08, its gate came out
go, and **the owner accepted its decisions D1–D10 the same day** ("accept D1-D10, write revision 3"). **Where §1–§9
differ, this section governs.** They're kept as the record of what was proposed. The companion's §R3 is the engine
half.

### R3.1 F1 becomes the in-tree seam

**F1's foundation (§4) isn't built in this revision.** Each of its pieces maps onto a seam the framework already
has, and the plugin machinery waits for a trigger (the companion's R3.1):

| F1 piece (§4) | in revision 3 |
|---|---|
| discovery (Switchboard) | the bootstrap's specialty table. **Switchboard is deferred, not reversed (Q46):** it stays the presumptive loader when the trigger fires |
| versioned contracts, `requires_spi` | the specialty's declaration and its digest. The SPI waits for the trigger |
| explicit bindings | the handler registry (by task type and role) and the squad profile's `serves_roles` |
| scoped context loading | playbooks and fragments loaded by the specialty's handlers for their own tasks, and nowhere else |
| mediated tools | typed operations through the worker, deny-by-default; `execute_luau` only through the harness (D5) |
| native runner and result providers | the Luau runner (#2906, core: a language) and the specialty's result reader |
| preflight at creation and at the plan gate | kept, against the resolved specialty |
| the Campaign snapshot | the specialty's digest in the profile snapshot hash; every cycle compares, and a difference stops the Campaign with a named reason |

**So Q45's exception is no longer needed for this work.** Nothing of Capability-Backed Agents' mechanism is built,
so there is nothing to amend there. Whether that SIP still takes the amendment Q45 called for, or only a note
naming this seam as the starting point of its §17 split, was **Q51** (R3.7). It was first ruled the note, then
re-ruled on 2026-11-09: the owner pulled §21 and §27 forward into Agent Skillsets, which that SIP records as an
amendment.

### R3.2 The composition, as the specialty and its profiles

§1's five parts, each in one place, on the seam:

| part | where it lives now |
|---|---|
| roster and models | the squad profiles `game-dev-roblox` (the Spark) and `game-dev-roblox-lite-14b` (the MacBook's machinery check), each with a new `specialties: [game-dev-roblox]` field |
| reusable game-development capabilities | **not split out yet.** Content shared across engines gets its own name (`game-dev-common`) only when a second engine needs it |
| engine-specific capabilities | the `game-dev-roblox` specialty: fragments, playbooks and resources in its package |
| engine and tool providers, with permissions | the specialty's operations and its adapter (the companion's R3.6) |
| the game itself | the Project: `z_tower-ascension`, a private copy, with a local place file (D2) |

- **The one direction of ownership (§3) stands:** the profile names the specialty, and the specialty supplies
  operations, handlers and permissions. A specialty never imports a profile.
- **§3's YAML composition is replaced** by the profile field and the specialty's declaration. Its version pins
  become the specialty digest.
- **Bindings are by task type,** not by capability name:
  - strategy's change request rides the existing framing steps;
  - code is written and repaired by `development.develop` and `development.repair` with the specialty's context.
    That is the "augment" case, declared in the specialty's handler table;
  - QA's Studio work is `qa.run_remote_operation` with an operation id.
- **The authority ceiling (§3a) stands as written.** A role's permission is the intersection of what it requests,
  what the specialty grants and the existing authority. The lead recommends, and the existing controls rule.
- **Planning becomes property-driven** (the companion's R3.5): a `TaskType` property marks the types a planner may
  offer, set on today's three and `qa.run_remote_operation` only.

### R3.3 A designer, after the paper test

The plan's spike S5 tested whether the seam could describe the Iris design role (Capability-Backed Agents §13)
with no core change. **A partial pass:**
- the seam carries a designer's identity, handlers, resources and permissions, and §25c's binding to an existing
  agent;
- **its own kinds of authored work don't fit.** Applying a design system, reviewing UX and authoring design
  acceptance are new kinds of work, not tool-backed operations, so they need task types of their own: members of
  the central enum in a `design.` domain, under #559's rules.

**So:**
- a specialty adds operations, handlers, fragments, playbooks and resources without a core change;
- a specialty that adds a new kind of authored work adds its task types centrally, and makes them plannable through
  the property;
- **a second specialty needing its own task types is a trigger for the plugin machinery,** starting with a
  host-owned task-type lookup.

**Q48 stands:** the first demonstration uses strategy alone, and a designer is an optional, separate roster
identity.

### R3.4 The roles (§5), as the first milestone has them

- **strategy:** a change request with a player-facing criterion and its play scenario, frozen before development;
- **dev:** Luau inside the footprint;
- **QA:**
  - logic tests run headless under Lune, through the specialty's test loader;
  - `qa.run_remote_operation` for play scenarios;
  - a statement of what wasn't executed;
- **builder: the source manifest** (path, digest and script class per script). **No place build in the first
  milestone,** because the adapter writes the scripts into the copy's place itself (D10);
- **data:** measurements from executed runs;
- **lead:** recommendations only.

**The playbooks follow Q47,** and take what the plan's first Luau probe (S6) found. Six samples from the Spark's
27b model were correct in their Luau and Roblox API use in all six. The gaps were things a specialty supplies:
- **the test loader** for the game's instance-tree requires, and a convention for where tests live. Neither of
  S6's test files ran anywhere as delivered;
- **each task's context includes the module that owns its concept.** S6's one logic error came from a missing
  helper module;
- **the emission parser tolerates** a missing fence and a path line outside its fence;
- **change requests ask for effects on saved state at deploy.**

### R3.5 The demonstration (§7), revised

**Counted (D1):** a squad on the Spark takes **two small increments** of the copy from design to accepted source,
each proved in a real play session. For each:
1. the criterion and its scenario are frozen before development;
2. **the criterion fails on the accepted baseline,** so it discriminates;
3. dev writes the change;
4. QA's operation syncs the candidate, plays the frozen scenario and reads its assertion records;
5. **the criterion passes on the candidate,** and the Campaign's gate accepts the source.

A correct first candidate is acceptable. The second increment re-runs the first's frozen checks.

**The repair path is a separate diagnostic,** labelled apart from the counted evidence:
- a pre-registered, seeded behavioural defect;
- the unchanged verifier fails as an executed behavioural failure;
- the repair is routed;
- **the same verifier, by digest, passes.**

It proves the correction route and is not model evidence. **§7's step 5, which required a defect inside the counted
run, is replaced.**

**Before the counted run:**
1. a full-path gate: representative tasks through the real prompt budget, scoped context, playbook loading and
   reader, with context selection measured;
2. then a machinery rehearsal on `game-dev-roblox-lite-14b`.

The counted run is handed to the Spark as a run plan.

**S1 settled the condition on the claim:** input works in an unattended play session, so the claim stands as
written.

**What the evidence won't show:** how the game feels, what it looks like, more than one player, and parts, models or
UI built in Studio.

**Independent QA evidence and the held-out separation (§7) stand.** The scenario is public QA verification, and no
role gains held-out access.

### R3.6 Delivery

The dependency order replaces §7's:
1. phase 2a, the seam with a fixture specialty;
2. the companion's phases 2b–2e;
3. phase 2f, the squad;
4. phase 2g, the product;
5. phase 3, the demonstration;
6. later, Unity.

The ledger is re-cut to match. **§8's two definitions of done stand.**

### R3.7 Decisions and the prior rulings

**The plan's decisions, accepted 2026-11-08, as they touch this SIP:**
- **D1:** the claim, and the repair diagnostic apart (R3.5);
- **D6:** parallel development during 2.7: the MacBook worktree and rehearsals only; no merge, migration, profile
  activation, worker registration or deployment in 2.7's runtime;
- **D7:** the task type and property-driven planning (R3.2);
- **D8:** `game-dev-<engine>` naming;
- **D9:** this revision, and acceptance after renewed review.

| ruling | revision 3 |
|---|---|
| **Q45** (F1 may precede 3.x through an amendment in Capability-Backed Agents) | **replaced:** F1 becomes the in-tree seam (R3.1), which builds nothing of that SIP |
| **Q46** (Switchboard as the loader) | **deferred, not reversed:** the presumptive loader when the trigger fires |
| **Q47** (frontier-drafted, owner-approved, replay-tested skills) | **stands,** with S6's items (R3.4) |
| **Q48** (an optional designer, a separate roster identity) | **stands,** refined by the paper test (R3.3) |

**Q51, ruled by the owner on 2026-11-09, then re-ruled the same day:** Capability-Backed Agents, given that
nothing of its mechanism is built here.
- **The options:**
  - write the amendment Q45 called for;
  - or keep only a note in its header, naming this seam as the starting point of its §17 split.
- **First ruled: the note** ("note is fine"), on the reasoning that an amendment records a design change and none
  had been made. **Re-ruled the same day: the amendment.** The owner pulled §21 and §27 forward into Agent Skillsets
  ("agree, pull it forward and draft the assembly SIP"), which is a design change to that SIP, recorded as its §28.
  Its 3.x deferral of everything else and its premise correction (§5's deleted skill layer) are unaffected.

---

## 1. Summary

A **squad composition** is what makes a squad a game squad. It has five parts, and each lives in exactly one
place:

| part | what it is | where it lives |
|---|---|---|
| roster and models | which identities, which roles, which models | the squad profile (existing), which references the composition |
| reusable game-development capabilities | what each role does on any game | the **game-development pack** |
| engine-specific capabilities | what each role does on a Roblox game | the **Roblox pack** (and later Unity's, Godot's) |
| engine and tool providers, with permissions | the operations a role may invoke, on which workers | the game SIP's engine plugin; the composition requests, bounded by existing authority (§3a) |
| the game itself | the brief, goals, source, assets and acceptance criteria | the **Project** (SIP-0112, Project Goals and Backlog) |

A selectable **Roblox Game Dev Squad** is a named, versioned composition of those parts. A pack holds
expertise and never a named identity, and a Project holds the game and never expertise.

## 2. Motivation

The owner wants SquadOps to build and improve a real Roblox game, and later games on other engines. The game
SIP covers engine integration. What it leaves open is how the squad knows how to do game work: what the
strategy role asks for in a game increment, what QA counts as evidence that a game works, and how the builder
assembles a place. Today a role's expertise is its prompt fragments, the same for every Project. A game
needs more of it, loaded only where it applies, versioned, and checked before the plan is validated.

Capability-Backed Agents designed most of this, and was deferred to 3.x. This SIP takes the smallest part
of it a game squad needs, so a first Roblox squad doesn't wait for the whole umbrella.

## 3. The composition

**One direction of ownership** (the second outside review): **the squad profile supplies identities and
models, and references a composition. The composition supplies capability requirements and bindings.** A
composition never imports a profile.

```yaml
# config/squad-profiles.yaml (existing): identities and models, and the composition it uses
roblox-game-dev-squad:
  agents: [lead, strat, dev, qa, builder, data]   # with their models, as today
  composition: roblox-game-dev@1

# the composition: what the roles can do, and nothing about who they are
composition: roblox-game-dev
version: 1
packs: [game-dev@1, roblox@1]
providers: [squadops-engine-roblox@0.1]
bindings:                       # capability → role; each named, none implied
  strategy.design_increment:   {role: strat, from: game-dev@1}
  development.implement:       {role: dev,   from: game-dev@1, augmented_by: roblox@1}
  qa.play_scenario:            {role: qa,    from: roblox@1}
  builder.build_place:         {role: builder, from: roblox@1}
requested_operations:           # what each role asks to invoke (§3a bounds it)
  qa:      [run_studio_script, play_scenario, capture]
  builder: [build_place]
  dev:     [run_studio_script]
```

- **Augment or replace, declared per binding, never by load order.** `augmented_by` adds an engine pack's
  skills and checks to a generic capability. A binding naming only an engine pack replaces it. Two packs
  claiming one capability without a declared relationship are refused at preflight.
- **A specialist is routed by capability, not by role.** Today a profile may not enable two agents for one
  role (`src/squadops/cycles/profile_utils.py`). An optional designer is therefore bound to named capabilities
  (`strategy.design_increment` with `{agent: designer}`), with a declared handoff to strategy. That routing
  is part of F1 (§4), and until it exists, the first demonstration uses strategy alone (Q48).

### 3a. The authority ceiling

A composition **requests** operations, and never authorizes beyond what already exists. **A role's effective
permission is the intersection** of what its capability requests, what the composition grants, and the
existing authority: the approved roster and runtime, and the Project's policy (its publishing governance,
SIP-0112). Installing a pack or writing a composition can't, on its own, authorize publishing, unrestricted
scripts or source changes outside the change request's footprint. **The lead produces acceptance and
publication recommendations.** The recorded ruling and the authorization stay with the existing controls: the
Campaign's gates and the Project's publishing approval.

- **Resolved at Campaign creation** from declared configuration, never inferred from the objective
  (Capability-Backed Agents §27b). The resolved composition (every pack, plugin and skill version) is pinned
  in the Campaign's snapshot, so every cycle of the Campaign runs the same one.
- **Known before plan validation.** The task types and checks a composition adds are declared, so the plan
  validator knows them offline (§27a). A plan naming a task type the composition doesn't serve is refused at
  the plan gate, before dispatch (§27c).

## 4. The foundation (F1): the smallest part of Capability-Backed Agents

| piece | what it does | from Capability-Backed Agents |
|---|---|---|
| **discovery** | packs and engine plugins are found and loaded by one host-owned loader (Switchboard, as the console's plugins are) | §21, "Switchboard is the substrate" |
| **versioned contracts** | a pack's manifest is data: its capabilities, skills, tool requirements, artifacts and checks, with `requires_spi`. A mismatch refuses the pack at preflight | §21, "packs ship code against a narrow SPI" |
| **explicit bindings** | a composition binds each capability to a role. Nothing binds itself | §8, §25c |
| **scoped context loading** | a skill (`SKILL.md`, progressive disclosure) is loaded into the context of a task whose capability declares it, and nowhere else. Never dispatched, never seen by the planner | §21's taxonomy |
| **mediated tools** | a pack's handler reaches a tool only through the SPI's tool invoker, for an operation the composition permits, and every invocation is evidence | §21, §9 |
| **native runner and result providers** | an engine plugin's test runner and result reader are used by the existing verification path, as a product's derived-profile runners are | (new here; SIP-0112 H.4's shape) |
| **preflight** | at creation: every pack, plugin and worker requirement resolvable. At the plan gate: every task type in the plan servable by the composition | §16, §27c |
| **the Campaign snapshot** | the resolved composition pinned with the Campaign | §27d |

**Not in F1:** duty-shaped capabilities, working-set memory authority, pack lifecycle beyond install and pin,
console surfaces, and the other packs Capability-Backed Agents names. Those stay with the umbrella.

## 5. The roles' capabilities and handoffs

Every capability declares the same eight things. The table gives each role's; the packs hold the content.

**Each capability declares:**
1. **required context:** what it reads (the game brief, the goals, the accepted source, earlier evidence);
2. **prompt guidance:** task-specific fragments, through PromptService (no inline text);
3. **skills:** the playbooks loaded for it, by name and version;
4. **tool access:** the operations it may invoke (§3's permissions);
5. **output artifacts:** what it must produce;
6. **evaluation checks:** what judges those artifacts;
7. **handoff:** what the next role receives;
8. **missing prerequisite:** what happens when its context, a tool or a worker is unavailable. It always stops
   with a named reason and never improvises (SIP-0096's not executed).

| role | capability | owes | judged by | hands to |
|---|---|---|---|---|
| **strategy / design** | the player experience, the core loop, progression, a bounded increment with measurable playtest goals | a change request naming the backlog item, its player-facing criteria and a playtest scenario for each | criteria observable in a play session; one increment's scope | lead (feasibility), then dev and QA |
| **development** | engine architecture, gameplay, debugging; client and server, replication and persistence rules where the game has them | source changes inside the footprint | the plugin's static and editor checks; the client/server rule checks the pack declares | builder, QA |
| **QA** | logic tests, integration tests, actual gameplay tests through a play scenario; device and multiplayer checks where applicable; whether the evidence suffices | the tests, the scenario runs and their evidence, and a sufficiency statement naming what was not executed | executed results read per test; a gameplay claim only from a play session | lead (acceptance), dev (defects) |
| **builder** | asset import, compilation, assembly, packaging; a reproducible runnable artifact | the place or player build, its build report and hashes | the plugin's build operation; the artifact reproduces from the same revision | QA (the build under test) |
| **data** | playtest telemetry, performance, balance and delivery measurements | a measurement report on the increment | measurements read from executed runs, never estimated | lead, strategy (the next increment) |
| **lead** | feasibility, scope, handoff review, repair coordination, and acceptance and publication **recommendations** | recommendations, with reasons; the rulings stay with the existing controls (§3a) | the gate's existing rules | the Campaign |

**An optional specialist** (a game designer, for example) is a roster choice in the composition. It takes the
strategy role's design capability, and the strategy role keeps scope and goals. No pack names an identity.

## 6. Profiles reference the composition

A squad profile names a composition and version (`composition: roblox-game-dev@1`) and adds nothing of its
content. A request profile (SIP-0114's workflow) is chosen independently. A Roblox squad runs the
`campaign-increment-source` workflow, or any other, without a second copy of either.

## 7. The first end-to-end acceptance demonstration (F5)

**One small Roblox game increment** shows the whole chain, with each handoff recorded:
1. **design:** strategy's change request, with a player-facing criterion and its playtest scenario;
2. **implementation:** dev's source change;
3. **build:** builder's place artifact;
4. **an actual player scenario:** QA drives a play session on the worker and reads the criterion's assertions
   from it;
5. **a defect and its repair, on the same verifier:** the scenario fails as an executed behavioural failure,
   its defect is routed, the repair lands, and **the same scenario, unchanged, passes**;
6. **accepted source:** the Campaign's gate and the product's runner accept it, onto the campaign branch.

**What each run records** (the second outside review): the approved scenario's and assertions' digest, the
tested source revision and the build's identity. A pass after the repair counts only if the scenario digest
is the one that failed. A verifier changed to pass is a new verifier, not a repair.

**Independent QA evidence:** the play session's evidence is produced by QA's operation, on the worker, and
read by the plugin's result reader. Never by the role that wrote the code. **QA execution is not held-out
evaluation.** The public gameplay scenarios reach QA. A private evaluator scenario and its expectations
(SIP-0113's held-out suite) stay isolated from every role and are read only by the evaluator.

**The second increment re-runs the first's frozen checks** (SIP-0109's accumulated acceptance), so "without
breaking the first" is executed, not assumed.

**The dependency order:** F1, proven with a **fixture provider** (registration, binding, invocation and the
result-provider contract, with no worker), then the game SIP's M0 (real remote-worker execution), then its
R-1 (Roblox integration), then F2–F4 (the packs and the composition), then F5 (this demonstration), then F6
(Unity).

**Then Unity (F6),** as the next provider, to show the pack and plugin contracts hold for an engine with a
different test model.

## 8. Two definitions of done, verified separately

| statement | whose | verified by |
|---|---|---|
| **engine integration works** | the game SIP (R2.10) | per engine: the plugin loads and pins, operations run on a matched worker, results read per test, unexecuted modes read not executed, editor changes return as revisions |
| **the squad can build and improve a playable game** | this SIP | §7's demonstration read live: each handoff's artifact present, the player scenario executed, a defect repaired with the same verifier passing, the source accepted. Then a second increment on the same game, accepted with the first increment's frozen checks re-run and passing |

Neither implies the other. An engine can integrate cleanly while the squad can't yet build a game on it.

## 9. The rulings (2026-10-31)

Ruled by the owner's outside reviewer, under the owner's delegation ("I'll have the reviewer answer the open
questions"):

| # | question | ruled |
|---|---|---|
| Q45 | Capability-Backed Agents' 3.x deferral: may F1 land first? | **yes, F1 only,** through an explicit recorded amendment in Capability-Backed Agents. Duties, memory authority, console management and the rest of the umbrella stay deferred. **This scope exception doesn't place the work in a release** |
| Q46 | Switchboard as the loader | **yes:** its discovery and loading, with SquadOps-owned contracts and the runtime SPI. Sharing the loader doesn't mean engine operations run inside the console |
| Q47 | who authors a pack's skills | **a frontier model drafts, the owner approves, and each is replay-tested before its first release:** on representative tasks, on prerequisite failures, and for honest evidence, with the intended runtime models, plus engine-backed tests where they apply. Model-written prose alone is not release evidence |
| Q48 | an optional game-designer specialist | **an optional, separate roster identity, with no new mandatory framework role.** The first demonstration uses strategy. A designer is enabled only with explicit capability-level routing and a design-to-strategy handoff (§3), and strategy keeps scope and the proposal |
