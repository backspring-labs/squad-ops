---
sip_uid: '17934561107767162'
title: Game Development Capability Packs and Squad Composition
status: proposed
author: Jason Ladd
created_at: '2026-10-31T00:00:00Z'
---

# SIP: Game Development Capability Packs and Squad Composition

**Status:** Proposed (2026-10-31), for design review
**Authors:** Jason Ladd (the owner's outside review, 2026-10-31); drafted by the Spark lane's supervisor
**Created:** 2026-10-31
**Targets:** unplaced. Acceptance and release placement are the owner's.
**Companion:** Game Development Platform Capability (`SIP-Game-Development-Platform.md`, PR #2405), revision 2:
how an engine is integrated. This SIP is how a squad uses it.
**Builds on:** Capability-Backed Agents (proposed, deferred to 3.x: its §21 taxonomy, §25c and §27);
SIP-0112 (Project Lifecycle Management); SIP-0114 (request-profile taxonomy); SIP-0109 (Campaign
Orchestration); SIP-0095 (cycle-create preflight); SIP-0096 (verification evidence); SIP-0105 (stack
blueprints)

## Intake check

Checked 2026-10-31 against `sips/PORTFOLIO.md`. **Conflicts:** one, for the owner (Q45). **Overlaps,** each
with its boundary (portfolio cluster 17, Q45–Q48):
- **Capability-Backed Agents** (cluster 8, deferred to 3.x on 2026-10-04: "move them to 3.x including
  capability-backed agents"). **The conflict:** this SIP needs a first slice of that SIP's foundation before
  3.x. **The boundary proposed:** this SIP takes the smallest cycle-bound foundation (§4) and nothing else of
  that umbrella: no duty-shaped capabilities, no working-set memory authority, no console surfaces. The
  umbrella stays deferred for the rest, and its §17 split would start from this foundation. **Corrections it
  needs,** recorded in its own header by this PR: its §5 extends the SIP-0040 skill layer, which was deleted
  (#400, #401). Its §21 taxonomy (identity, capability, skill, tool) is what this SIP builds on, and §5's
  premise isn't.
- **The game SIP's engine plugins** (cluster 17). **Boundary:** an engine plugin provides typed operations,
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

## Delivery ledger (current as of 2026-10-31)

| part | status | where |
|---|---|---|
| F1: the foundation (§4): discovery, versioned contracts, explicit bindings, scoped context loading, mediated tools, native runner and result providers, preflight at creation and at the plan gate, the Campaign snapshot | **unplaced**, deliberately: waits for Q45 | — |
| F2: the reusable game-development pack (§5's capabilities, engine-neutral) | **unplaced**, deliberately | — |
| F3: the Roblox pack (Roblox-specific capabilities and skills, on the game SIP's R-1 plugin) | **unplaced**, deliberately | — |
| F4: the Roblox Game Dev Squad composition, and squad profiles that reference it (§3, §6) | **unplaced**, deliberately | — |
| F5: the first end-to-end acceptance demonstration on a small Roblox game (§7) | **unplaced**, deliberately: needs F1–F4 and the game SIP's M0 and R-1 | — |
| F6: the Unity pack, on the game SIP's U-1, as the check that packs generalize across engines | **unplaced**, deliberately: after F5 | — |

**What closes this SIP:** F1–F5 shipped, with §8's "the squad can build and improve a playable game" read
live. F6 shipped or dropped by a numbered amendment.

---

## 1. Summary

A **squad composition** is what makes a squad a game squad. It has five parts, and each lives in exactly one
place:

| part | what it is | where it lives |
|---|---|---|
| roster and models | which identities, which roles, which models | the squad profile (existing), extended with optional specialists |
| reusable game-development capabilities | what each role does on any game | the **game-development pack** |
| engine-specific capabilities | what each role does on a Roblox game | the **Roblox pack** (and later Unity's, Godot's) |
| engine and tool providers, with permissions | the operations a role may invoke, on which workers | the game SIP's engine plugin; the composition grants the permissions |
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

```yaml
composition: roblox-game-dev
version: 1
roster:
  from_profile: full            # the existing roles and their models
  optional_specialists: []      # e.g. [game-designer]: a roster choice, never a pack's
packs:
  - game-dev@1                  # reusable game capabilities
  - roblox@1                    # Roblox-specific capabilities and skills
providers:
  - squadops-engine-roblox@0.x  # the game SIP's plugin
permissions:                    # which role may invoke which operation (§5)
  qa:      [run_studio_script, play_scenario, capture]
  builder: [build_place]
  dev:     [run_studio_script]
```

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
| **lead** | feasibility, scope, handoff review, acceptance, repair coordination, publication decisions | rulings, with reasons | the gate's existing rules | the Campaign |

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
5. **a defect and its repair:** a scenario that fails, its defect routed, the repair, the scenario passing;
6. **accepted source:** the Campaign's gate and the product's runner accept it, onto the campaign branch.

**Independent QA evidence:** the play session's evidence is produced by QA's operation, on the worker, and
read by the plugin's result reader. Never by the role that wrote the code.

**Then Unity (F6),** as the next provider, to show the pack and plugin contracts hold for an engine with a
different test model.

## 8. Two definitions of done, verified separately

| statement | whose | verified by |
|---|---|---|
| **engine integration works** | the game SIP (R2.10) | per engine: the plugin loads and pins, operations run on a matched worker, results read per test, unexecuted modes read not executed, editor changes return as revisions |
| **the squad can build and improve a playable game** | this SIP | §7's demonstration read live: each handoff's artifact present, the player scenario executed, a defect repaired, the source accepted. Then a second increment on the same game, accepted without breaking the first |

Neither implies the other. An engine can integrate cleanly while the squad can't yet build a game on it.

## 9. Open questions for the owner

| # | question | recommendation |
|---|---|---|
| Q45 | **Capability-Backed Agents' 3.x deferral:** may this SIP's foundation (§4, F1) land before 3.x? | **yes, F1 only,** recorded in Capability-Backed Agents as a numbered amendment. The umbrella's rest stays in 3.x |
| Q46 | **Switchboard as the loader** for packs and engine plugins, as for the console's plugins | **yes:** one plugin mechanism, per Capability-Backed Agents §21 |
| Q47 | **who authors a pack's skills** | **a frontier model drafts, the owner approves, and each is replay-tested before release,** as lessons are (the owner's earlier ruling on lesson authorship) |
| Q48 | **an optional specialist identity** (a game designer): a new roster identity, or a role variant | **a new roster identity, optional,** bound to the strategy role's design capability, with its own memory and accountability (Capability-Backed Agents' identity layer) |
