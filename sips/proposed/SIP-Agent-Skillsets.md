---
sip_uid: '17942318023754850'
title: Agent Skillsets
status: proposed
author: Jason Ladd
created_at: '2026-11-09T00:00:00Z'
---
# SIP-XXXX: Agent Skillsets

## What each agent in a squad is equipped with for a cycle, declared as a spec a capability pack can carry

**Status:** Proposed (2026-11-09), revision 1, for the owner's outside review. **Building waits for that review:**
no implementation starts until the review has answered §13's questions and the owner accepts this SIP (the owner,
2026-11-09: "make sure I can run an outside review before you start building").
**Revision:** 1
**Target:** unplaced. A 2.8 candidate and the MacBook lane's input to the 2.8 plan, which places it.
**Authors:** Jason Ladd (Backspring Labs / SquadOps)
**Split from:** Capability-Backed Agents (proposed, deferred to 3.x), as the first of the bounded SIPs its §17 plans.
This SIP takes that SIP's four layers (its §21) and its assembly rules (its §27) into 2.x, restated against the
Project and the stack, and puts them on the agent. Everything else in it stays in 3.x (§11). Section numbers 21 and 27
(and §27a–§27f) refer to that SIP, which records the split in its §28.
**The owner's direction (2026-11-09):**
- "agree, pull it forward and draft the assembly SIP";
- agents are the ones equipped, and a squad profile is an assembly of agents; the agent's equipment is a *skillset*;
- "for an agent and a skillset, I'd need a spec that could be distributed in the capability pack";
- a *playbook* is what a squad follows, so the word is kept for that.

**Builds on:** SIP-0072 (development profiles), SIP-0071 (build profiles), SIP-0105 (the stack contract and its
governance), SIP-0112 (the Project and its Development Configuration), SIP-0095 (cycle-create preflight), SIP-0109
(Campaign policy), SIP-0110 (snapshot binding and re-binding), and the task-type rules of #559.
**First consumer:** the game-dev-roblox plan (PR #2972) and the Game Development Platform SIP (PR #2405). Their
revision 3 calls what this SIP describes a *specialty* and its content *playbooks*; their next revision uses skillsets
and skills instead.

---

## Intake check (2026-11-09)

Checked against `sips/PORTFOLIO.md`: every live SIP, plan placement and recorded idea.

- **The split it comes from: Capability-Backed Agents.** Its §21 (identity, capability, skill, tool) and §27 (the
  assembly rules) move here for 2.x. That SIP records the split in its §28. Its pack loading and packaging,
  Switchboard, the interface for shipped pack code, per-agent capability bindings beyond roles, working sets, memory,
  the evidence ledger, the design pack and its console views stay in 3.x. **Q51** (PR #2841's question: whether
  Capability-Backed Agents takes an amendment now that the game work builds none of its mechanism) is re-ruled by
  this split: it takes one.
- **What a capability pack will carry.** Capability-Backed Agents §7 lists a pack's manifest: capability modules,
  binding contracts, capability-skill contracts, tool requirements. A skillset spec (§4) is the part of that manifest
  2.x needs, in a format the pack carries unchanged. Its §9 named the adopted `SKILL.md` bundles "skill packs /
  playbooks"; here they are *skills* inside a skillset, and *playbook* is kept for a squad's procedure.
- **Overlaps, each with its boundary:**
  - **SIP-0105, the stack contract.** The same governance applies to a skillset's fields: what a missing field means
    is stated, and a field is added only by a SIP. Its ledger moved stack packs and plugin loading "to a successor
    SIP, not yet drafted". This SIP builds no packaging or loading.
  - **SIP-0072, development profiles** (implemented). A stack assigns skillsets to roles on its development profile
    (§5.2, Q52). The PR that adds that field carries SIP-0072's amendment (CLAUDE.md step 5a).
  - **SIP-0112, the Project.** It owns the Development Configuration and the selection of a repository-backed
    product's development profile from its runners (H.26). This SIP reads the selection; Q58 asks whether the
    configuration's `target` should take part in it.
  - **SIP-0095, cycle-create preflight.** Extended with the skillsets' checks (§9).
  - **SIP-0092 and SIP-0093, the implementation plan and its authoring.** The planner's offered task types become
    what the squad's skillsets cover (§6).
  - **SIP-0109, Campaign policy.** A Campaign pins its agents' skillsets, beside the stack and squad profile it pins
    today (§10).
  - **SIP-0110.** Its `rebind` event is the precedent for re-binding pinned skillsets, and its project instructions
    outrank a skill where the two conflict (§7). Skills reach a prompt through PromptService, outside SIP-0110's
    context-assembly port.
  - **SIP-0112's size preflight (H.21).** It counts the skills an agent carries (§7).
  - **#559's task-type rules.** Capabilities stay `TaskType` members, and planning reads a property, never a type's
    identity (§6).
- **A conflict, resolved by the owner's direction:** the game SIPs' revision 3 (PRs #2405 and #2841) puts a
  `specialties` field on the squad profile and a specialty digest into the roster's snapshot hash. This SIP assigns a
  stack's skillsets to roles on its development profile and records them in a separate skillset record (§5, §10). The
  owner directed the game work onto this SIP on 2026-11-09, and those documents' next revision applies it. Both
  documents name the conflict until then.
- **Placement.** The 2.7 plan expects `tasks/task_types.py`, `orchestration/handler_registry.py`,
  `bootstrap/handlers.py` and the profile snapshot hash unchanged (its §5, with the game-dev-roblox plan). This SIP
  changes the first and reads the others, so it builds in 2.8 at the earliest.
- **New questions:** Q52–Q61, in §13 and the portfolio.

## Delivery ledger (current as of 2026-11-09)

| part | status | where |
|---|---|---|
| Phase 1: each agent's skillsets resolved and recorded on every cycle, with the base skillsets derived from the handler configuration, the digest and the replay field; no change in behaviour (§14) | **unplaced**, deliberately: the 2.8 plan places it, after this SIP's review | — |
| Phase 2: the skillset spec and its loader, the development profile's assignments, the `plannable` property, the planner's vocabulary from the squad's skillsets, and the checks at creation and at the plan gate (§4–§6, §9) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 3: skills: the format, the loader, the digests and the size preflight's count (§7) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 4: tools: declarations, locations and the reachability check (§8) | **unplaced**, deliberately: the 2.8 plan places it, with the Game Development Platform's worker registry for the `worker` location | — |
| Phase 5: the Campaign's pin, its comparison at each launch, and the owner's re-bind (§10) | **unplaced**, deliberately: the 2.8 plan places it | — |

**What closes this SIP:** phases 1–5 shipped, with the first consumer's stack (Roblox) running on skillsets and every
existing stack's cycles unchanged.

---

## 1. Summary

A squad profile is an assembly of agents: who they are, their roles and their models. This SIP gives each agent, for
each cycle, the **skillsets** it carries. A skillset is a spec: the capabilities it serves, the skills the agent loads
for them, and the tools they may call.

1. **A skillset is a distributable spec.** One directory holds its declaration and its skills. In 2.x skillsets live
   in the tree; in 3.x a capability pack carries the same directory, and packaging adds loading, not a new format.
2. **An agent's skillsets come from declared configuration.** Each role it serves has a base skillset, and the
   stack's development profile adds skillsets per role. The objective, the PRD and the plan never select one.
3. **Capabilities stay central.** A skillset serves `TaskType` members; it never defines one. The planner may use
   what the squad's skillsets cover together.
4. **They're checked twice:** at creation, that the squad carries what the stack needs and its tools are reachable;
   at the plan gate, that each task's agent carries its capability.
5. **They're recorded and pinned.** Each cycle records every agent's skillsets and one digest. A Campaign pins the
   digest, and a change between its cycles stops it with a named reason.

For every existing stack, each agent carries only its roles' base skillsets, which are what it runs with today.
Roblox is the first stack to add skillsets: a QA skillset that plays scenarios in Roblox Studio on a remote worker,
and a development skillset for Luau.

## 2. The problem: six places decide what a cycle's agents have, and two record it

| what is decided | where it's decided today | what records it |
|---|---|---|
| the stack, for a greenfield product | the cycle's `build_profile` (`stacks/scaffold.py:2375`); a Campaign's `CampaignPolicy.stack`, passed to each launch as `build_profile` and `development_profile` (`campaigns/models.py:620`, `campaigns/launch_requests.py:34`) | the cycle's config |
| the development profile | the scaffold stack, a declared name, or the default `python_cli` (`stacks/scaffold.py:2350`, `stacks/development_profiles.py:658`); for a repository-backed product, its runners (`api/routes/cycles/cycles.py:334-385`, `stacks/development_profiles.py:716`) | `development_profile_selection` and its fingerprint, for repository-backed cycles only (`api/routes/cycles/cycles.py:378`) |
| the squad | `squad_profile_id`, required at creation (`api/cycle_schemas.py:73`) | `squad_profile_snapshot_ref`, a hash of the roster (`cycles/lifecycle.py:276`) |
| what each agent can do | the handlers its roles get: a fixed list, filtered by role when an agent process starts (`bootstrap/handlers.py:77`, `orchestration/handler_registry.py:100`) | nothing |
| the planner's task types | a fixed set of three (`cycles/implementation_plan.py:59`); `builder.assemble` is offered only when the squad has a builder, a `build_profile` is set and the cycle isn't an increment (`capabilities/handlers/_plan_authoring_service.py:119`) | nothing |
| prompt text for the stack | four routes: the development profile's text fields, build-profile narratives, stack narratives keyed on `build_profile` (`stacks/stack_narratives.py:26`), and per-stack request templates (`stacks/scaffold.py:2141`) | the development profile's fingerprint, which covers its prompt assets by name only (`stacks/development_profiles.py:754`) |
| tools | ports for files, containers and version control; an agent's ports bundle carries the filesystem only (`agents/base.py:28`). Models have no tool calling and nothing uses MCP | nothing |

What follows from it:
- **A stack can't add a step or equip an agent.** The planner's vocabulary and each role's handlers are the same for
  every stack (`cycles/task_plan.py:116`).
- **A stack's procedures have one home,** the development profile's text fields, and the fragment system has no
  stack dimension. `capabilities/handlers/build_profiles.py:18-20` calls adding one "the deferred SIP-sized question".
- **An unknown step fails late.** A plan naming a task type outside the fixed set fails to parse; the plan gate logs
  it and defers to dispatch (`execution/dispatched_flow_executor.py:5210`), where the task fails as
  `handler_not_found` (`orchestration/handler_executor.py:140`).
- **A Campaign pins names, never definitions.** It fixes the stack's and the squad profile's names. A redeploy that
  changes a development profile mid-Campaign is unrecorded; the fingerprint's drift is logged only when a run is
  retried (`api/routes/cycles/runs.py:163`).
- **No single record says what each agent had.**

The game work needs all of it: a step the Roblox stack's QA agent can take (`qa.run_remote_operation`), skills for
Luau and Studio (the first Luau probe's findings), tools on a remote worker (Studio's operations), and a pinned
record. Revision 3 of the game SIPs built these as a *specialty* beside the existing seams. This SIP builds them into
the seams, on the agent, for every stack.

## 3. The model

**Four layers,** taken from Capability-Backed Agents §21, which settled them on 2026-07-29:

| layer | the question it answers | what it is in SquadOps | the test that places a thing in it |
|---|---|---|---|
| **identity** | who is accountable | an agent in a squad profile: its role, model and the roles it serves | it has memory and accountability |
| **capability** | what the planner may assign | a task type, with its handler, the roles that serve it, its expected artifacts and its correction mapping | the planner can assign it |
| **skill** | how the model performs a procedure | content loaded into the agent's context for the work; nothing today (removed with #401) | the model loads it to do the work |
| **tool** | what executes | an operation behind a port and its adapter | it's invoked with arguments and returns a result |

**How they're put together:**
- **A squad profile** is an assembly of agents (identity), as today.
- **A skillset** binds the other three for a role: the capabilities it serves, the skills loaded for each, and the
  tools each may call. It's a spec, versioned and digested (§4).
- **An agent carries skillsets** in a cycle: its roles' base skillsets, plus those the stack assigns to its roles (§5).
- **The stack** is the technology the product is built in. Its development profile says which skillsets each role
  carries.
- **A playbook** is what a squad follows: a procedure across agents. This SIP keeps the word for that and defines
  nothing under it.

## 4. The skillset spec

### 4.1 What a skillset declares

```yaml
api_version: squadops.skillset/v1
skillset:
  id: roblox-studio-qa
  version: 1
  description: Plays frozen scenarios in Roblox Studio on a worker and reads their assertions
  roles: [qa]
  capabilities:
    - task_type: qa.run_remote_operation
      skills: [studio-play-scenario]
      tools:
        - id: game-dev-roblox.play_scenario
          location: worker
    - task_type: qa.test
      skills: [luau-test-loader]
```

(Illustrative: the Game Development Platform SIP's next revision settles Roblox's content.)

| field | what it holds | rule |
|---|---|---|
| `id`, `version` | the spec's identity | any change to the spec or its skills increments `version`; the digest covers both |
| `description` | one line | shown in records and, later, in a pack's listing |
| `roles` | the roles that may carry it | assigning it to another role is refused at creation |
| `capabilities[].task_type` | a capability it serves | a `TaskType` member; a skillset never defines one (§6) |
| `capabilities[].skills` | the skills loaded for that capability's tasks | each names a directory under `skills/` holding a `SKILL.md` |
| `capabilities[].tools` | the tools that capability's handler may call: `id` and `location` | §8 |

An empty list means none, and nothing is inherited from another skillset. A further field is added only by a SIP:
the governance SIP-0105 gives a stack's fields.

### 4.2 One directory per skillset, shaped for a pack

```
roblox-studio-qa/
  skillset.yaml
  skills/
    studio-play-scenario/SKILL.md
    luau-test-loader/SKILL.md
```

The directory is the unit a capability pack will carry. In 2.x the tree holds it under the prompts seam,
`src/squadops/prompts/skillsets/<id>/` (Q61), because a skill's text is prompt content and prompt content belongs to
PromptService (#448). The spec is data: it's validated, preflighted and shown without running anything, which is
Capability-Backed Agents' rule for a pack's declarations ("code for execution, data for contract", §21).

### 4.3 Distributed in a capability pack, later

A capability pack (Capability-Backed Agents §7, 3.x) carries skillset directories unchanged, with what packaging
adds: discovery, installation, the pack's version and its compatibility range. The spec's `api_version` lets a later
format be told apart. Two things a pack may add in 3.x that 2.x refuses: a capability the host doesn't define (a pack
shipping handler code, Capability-Backed Agents §21), and a skillset for one agent rather than a role (§13, Q60).

## 5. Which skillsets an agent carries in a cycle

### 5.1 Each role's base skillset

A role's base skillset is what the handler configuration gives that role today (`bootstrap/handlers.py:77`): the
capabilities its handlers serve, with today's prompt routes and no skills or tools beyond today's ports. It's derived,
not written as a spec, and named `base:<role>` in the record. So every existing cycle's agents carry exactly what they
run with now.

### 5.2 The stack assigns skillsets to roles, on its development profile (Q52)

A development profile is already a stack's settings bundle: it's selected for greenfield and repository-backed cycles
alike and pinned with a fingerprint. It gains one field:

```yaml
skillsets:            # role -> the skillsets agents in that role carry, each pinned by version
  qa: [roblox-studio-qa@1]
  dev: [luau-dev@1]
```

Empty means base skillsets only. Every existing profile takes the empty value. The profile's fingerprint covers the
assignments, and the skillsets' own digests are recorded beside it (§10).

### 5.3 Resolution: a function of declared configuration (Capability-Backed Agents §27b)

**The inputs:** the cycle's effective configuration (its request profile's defaults and the operator's overrides),
the Project's Development Configuration at the revision the cycle pins (repository-backed cycles), the squad profile,
and the Campaign's policy when a Campaign launched the cycle.

**The rule:** each agent carries the base skillset of each role it serves, plus every skillset the development profile
assigns to those roles. The same inputs give the same skillsets. The objective, the PRD, a framing artifact and the
plan never select one. Inference may help a person choose a profile; it never makes the choice.

**Agents in the same role carry the same skillsets** in 2.x, so routing stays as it is: task, then role, then the
first enabled agent serving that role (`cycles/agent_config.py:101`). Giving one agent a skillset its role's other
agents lack is Capability-Backed Agents §8's roster binding, in 3.x (Q60).

**When:** at cycle creation, after the development profile is pinned (`_pin_development_profile`,
`api/routes/cycles/cycles.py:334`) and before framing. The record is written then, and no later step changes it.

## 6. Capabilities: the planner's vocabulary (§27a)

- **Capabilities stay central.** Each is a `TaskType` member with its handler, the roles that serve it, its expected
  artifacts and its correction mapping (#559: constants at the core). A skillset serves capabilities by name; it never
  defines one, and nothing a skillset declares reaches the handler registry (Q23's rule for packs).
- **Planning reads a property.** `TaskType` gains `plannable`, set on today's three (`development.develop`,
  `qa.test`, `builder.assemble`). `_KNOWN_BUILD_TASK_TYPES` becomes derived from it.
- **The offered set** is the plannable capabilities the squad's skillsets cover, then today's builder rule. Every
  existing stack is offered exactly today's types.
- **Plan validity stays decidable offline.** Given a cycle's skillset record, whether a plan is well formed is a
  property of the plan and the record. No step reachable only at dispatch enters a plan.
- **A new plannable type is its own proposal,** with its handler, expected artifacts, footprint rules, correction
  mapping and every verifier seam that judges it (CLAUDE.md, "Typed checks"), because a planned type changes planning
  for every product whose squad carries it. The first is `qa.run_remote_operation`, which the Game Development
  Platform SIP proposes.

## 7. Skills

- **The format:** a `SKILL.md` file: front matter with `name` and `description`, a markdown body, and optional
  resources beside it. Capability-Backed Agents §9 adopted the format on 2026-07-01 because it runs under local
  models as well as frontier ones.
- **The home:** inside its skillset's directory (§4.2), served by PromptService and listed in the prompt manifest.
- **The loader is explicit.** A task's prompt receives the skills its agent's skillsets declare for that task's
  capability. The model never chooses skills from their descriptions.
- **Placement in the prompt:** the stack's section, where `system_prompt_supplement` renders today. Where a skill and
  a project instruction (SIP-0110) disagree, the instruction wins: the product's own rules come before the
  framework's advice about its stack (SIP-0112 B.5.1).
- **Size:** the size preflight (SIP-0112 H.21) counts the skills each agent carries, so a skill that can't fit its
  model's window is named before the first cycle.
- **Authorship:** Q47's rule for the game packs applies to every skill: a frontier model drafts, the owner approves,
  and each skill is replay-tested on the models that will run it before it's used.
- **The existing four routes stay** until a later consolidation (Q54). New procedural content for a stack goes in a
  skill.

## 8. Tools (§27e)

- **A tool is an operation behind a port,** invoked by a capability's handler with arguments. The model never invokes
  a tool itself (Q59). A handler is given the tools its agent's skillsets declare for its capability, through its
  ports.
- **Locations:**

  | location | reachable when |
  |---|---|
  | `agent` | always: the agent's own container |
  | `sandbox` | the sandbox service is enabled (today's preflight check) |
  | `worker` | a registered worker declares the tool. The worker registry is the Game Development Platform SIP's |

- **Late binding is allowed when declared.** Which worker serves a tool is bound at dispatch; that the tool is
  declared, and that some worker can serve it, is checked at creation.

## 9. Checks (§27c, extending SIP-0095)

**At creation,** in `_run_create_preflight` (`api/routes/cycles/cycles.py:203`), each refusal with a named reason:
- every skillset the development profile assigns exists at the pinned version, and lists the role it's assigned to;
- every capability those skillsets serve is carried by at least one agent in the squad;
- every skill's content is present, and its digest is recorded;
- every tool is reachable at its location.

**At the plan gate,** where the plan first exists: every task's type is a capability its role's agent carries. A plan
that fails is refused at the gate with the reason, and the cost is a re-plan. Dispatch's `handler_not_found` stays as
the last line.

## 10. Recording and pinning (§27d, §27f)

- **The skillset record,** stored with the cycle beside `squad_profile_snapshot_ref` (Q57):

  | part | what is recorded |
  |---|---|
  | the squad | the squad profile's id and its roster hash (unchanged) |
  | the development profile | its name, how it was selected, and its fingerprint, which now covers its assets' content |
  | each agent | its id, its roles, and each skillset it carries: `id@version` and digest, or `base:<role>` |
  | the digest | one hash over all of the above |

  The roster hash keeps its meaning, and the hashes already recorded stay comparable.
- **Replay** matches the record's digest (`cycles/replay.py:56`).
- **A retried run** whose skillsets have changed names the change, as development-profile drift is named today.
- **A Campaign** pins the digest at creation. Each launch re-resolves and compares. A difference stops the Campaign
  with a named reason that lists the changed parts. It continues only by the owner's recorded re-bind, which starts a
  new attribution epoch (Q55). In-tree content can't be kept at its old version across a redeploy, so the Campaign
  detects the change and stops. SIP-0110's `rebind` is the precedent for the recorded act.

## 11. What stays in Capability-Backed Agents (3.x)

Pack discovery, installation and packaging (its §7), Switchboard as the loader, the interface for shipped pack code and
its versioning (its §21), per-agent capability bindings beyond roles and their validation (its §8), working sets (its
§10), memory (its §11, already deferred to Cross-Cycle Memory), the workspace and evidence ledger (its §12), the design
pack (its §13), activation and permissions (its §14–15), and its console views (its §17 item 10). This SIP is the
in-tree starting point of its §17 split: the vocabulary, the assembly rules and the skillset spec a pack will carry.

## 12. Vocabulary

| word | meaning here |
|---|---|
| **squad profile** | an assembly of agents: roles, models and the roles each serves (unchanged) |
| **skillset** | a spec binding capabilities, the skills loaded for them and the tools they may call, for a role; one directory, versioned and digested; what a capability pack carries (Q53) |
| **skill** | content an agent loads to do the work, in the `SKILL.md` format (Capability-Backed Agents §21). SIP-0040's governed execution unit was removed with #401 |
| **capability** | a dispatchable unit: a task type, its handler, its roles, its artifacts and its correction mapping. The `squadops.capabilities` package holds exactly these: task contracts and handlers (Q23) |
| **tool** | an operation behind a port, invoked with arguments |
| **stack** | the technology a product is built in; its development profile assigns skillsets to roles |
| **development profile** | a stack's settings bundle (SIP-0072; one meaning, Q36) |
| **capability pack** | packaging, in 3.x: it carries skillset directories and adds loading (Capability-Backed Agents §7) |
| **stack pack** | packaging, in 3.x: a stack's declaration as a loadable plugin (SIP-0105's intent) |
| **playbook** | what a squad follows: a procedure across agents. Kept for that, and defined by a later SIP |
| **specialty** | retired. The game SIPs' revision 3 used it for what this SIP puts in skillsets |

## 13. Questions for the outside review

Each has one recommendation. The review's answers are recorded here and in the portfolio before acceptance.

| # | question | recommendation |
|---|---|---|
| **Q52** | Where a stack assigns skillsets to roles: on its development profile, or on a new stack declaration that references the scaffold, development and build profile registries | **the development profile.** It's already the per-stack bundle, selected for greenfield and repository-backed cycles alike and pinned with a fingerprint. A new declaration would be a fourth registry keyed by the same names |
| **Q53** | The names: *skillset* for the spec an agent carries, *skill* kept for the content inside it, and *playbook* kept for a squad's procedure | **as written.** One word per layer: a skillset holds skills and binds them to the capabilities and tools they serve |
| **Q54** | Skills add a fifth route for a stack's prompt text | **add it, and consolidate later.** New procedural content goes in skills; the four existing routes stay until a consolidation proposal moves them with a byte-identical test. Consolidating first would put a refactor of every existing stack ahead of the first new one |
| **Q55** | A Campaign whose skillsets change between its cycles | **stop with a named reason; continue only by the owner's recorded re-bind,** which starts a new attribution epoch. Continuing silently would let a regression inside the Campaign be blamed on the work when the equipment changed |
| **Q56** | How a cycle's squad profile is chosen | **as today, by the operator, checked against the skillsets** (§9). A Project or stack naming a default squad can be added later as declared configuration, under the same rule |
| **Q57** | Where the skillset record's digest lives | **a separate record beside `squad_profile_snapshot_ref`.** Folding it into the roster hash (the game SIPs' revision 3) changes what that hash means and makes the hashes recorded before it incomparable |
| **Q58** | Selecting a repository-backed product's development profile | **by its runners, as SIP-0112 H.26 does today,** with a Luau runner selecting the Roblox profile; the Development Configuration's `target` stays descriptive. The runners are the deciding fact because they're what executes the product's tests |
| **Q59** | Who invokes a tool | **a capability's handler, never the model,** in 2.x. Model-side tool calling stays with Capability-Backed Agents in 3.x, where its permission model is designed |
| **Q60** | Whether one agent may carry a skillset its role's other agents lack | **not in 2.x:** agents in a role carry the same skillsets, so routing stays by role. Per-agent bindings are Capability-Backed Agents §8, in 3.x, where routing by skillset is designed with them |
| **Q61** | Where skillset directories live in the tree | **under the prompts seam, `src/squadops/prompts/skillsets/<id>/`,** because a skill's text is prompt content (#448). The spec beside it is data read by a loader, and the directory is what a pack carries |

## 14. Phases, and how each is proved

| phase | what | proved by |
|---|---|---|
| **1** | resolve and record each agent's skillsets on every cycle, with base skillsets derived from the handler configuration; the digest; the replay field | every existing request profile and stack records only base skillsets, and the prompts and plans are byte-identical to today's; a wiring test enters at cycle creation and reads the record |
| **2** | the skillset spec and its loader; the development profile's assignments; the `plannable` property; the offered set from the squad's skillsets; the checks at creation and at the plan gate | existing stacks are offered exactly today's types (entering at the plan-authoring service); a fixture profile assigning a fixture skillset with an extra capability gets it offered; a plan naming a capability no agent carries is refused at the gate with its reason; a skillset assigned to a role it doesn't list is refused at creation |
| **3** | skills: the loader, the digests, the size preflight's count | a fixture skill reaches the prompts of the tasks whose capability declares it, for the agents that carry it, and no others; a content change changes the digest |
| **4** | tools: declarations, locations, the reachability check | a fixture tool at the `worker` location is refused at creation when no registered worker declares it, and accepted when one does |
| **5** | the Campaign's pin, its comparison at each launch, and the re-bind | a Campaign whose skillsets change between launches stops with the changed parts named; after a recorded re-bind it continues, in a new attribution epoch |

The fixtures live in tests only and never in a deployed registry. Where the code lives is the implementation plan's,
within the import-direction rules: `squadops.stacks` holds the development profiles as data and imports neither
`squadops.capabilities` nor `squadops.cycles` (`tests/unit/architecture/test_package_import_direction.py`).

## 15. Non-goals

- pack discovery, loading, installation and packaging, for stacks or capabilities (3.x);
- model-side tool calling (Q59);
- per-agent skillsets beyond the role (Q60);
- squad playbooks;
- working sets, memory and the evidence ledger;
- console views of skillsets;
- any change to what existing stacks' cycles run with;
- consolidating the four existing routes for stack prompt text (Q54);
- the worker registry and the remote execution protocol (the Game Development Platform SIP's).

## 16. Two squads, worked through

**An existing web stack, unchanged.** A greenfield cycle with `build_profile: fullstack_fastapi_react` and the `full`
squad. The development profile `fullstack_fastapi_react` assigns no skillsets.

| agent | roles | carries |
|---|---|---|
| Neo | dev | `base:dev` |
| Eve | qa | `base:qa` |
| Bob | builder | `base:builder` |
| Max, Nat, Data | lead, strat, data | their roles' base skillsets |

The planner is offered `development.develop`, `qa.test` and `builder.assemble`, as today.

**The first new stack: Roblox.** A Campaign on `z_tower-ascension`, a repository-backed Project whose Development
Configuration records `project_type: game`, `target: roblox` and a Luau test runner. Its runner selects the
`game_dev_roblox` development profile (Q58), which assigns `luau-dev@1` to dev and `roblox-studio-qa@1` to qa.

| agent | roles | carries |
|---|---|---|
| Neo | dev | `base:dev`, `luau-dev@1` (Luau conventions and the test-loader skill for `development.develop`) |
| Eve | qa | `base:qa`, `roblox-studio-qa@1` (`qa.run_remote_operation` with the play-scenario skill and Studio's operations at the `worker` location; the test-loader skill for `qa.test`) |
| the others | their roles | their roles' base skillsets |

The planner is offered `development.develop`, `qa.test` and `qa.run_remote_operation`. A repository-backed cycle
takes no `build_profile`, so `builder.assemble` isn't offered. The Campaign pins the record's digest. If a redeploy
changes the play-scenario skill between increments, the next launch stops and names it. The game-dev-roblox plan's
fixture path becomes this SIP's phases 1, 2 and 4, built for every stack, and the Roblox-specific parts (the worker,
the Studio adapter, the operations and the skills' content) follow on that base.
