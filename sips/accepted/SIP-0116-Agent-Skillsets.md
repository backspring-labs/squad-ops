---
sip_uid: '17942318023754850'
title: Agent Skillsets
status: accepted
author: Jason Ladd
created_at: '2026-11-09T00:00:00Z'
sip_number: 116
updated_at: '2026-11-09T17:12:21.413769Z'
---
# SIP-0116: Agent Skillsets

## The work declares the skillsets it requires, the squad's agents declare the skillsets they carry, and cycle preflight compares the two

**Status:** **Accepted (2026-11-09):** the owner, "accept Agent Skillsets, Q67 add headless". Proposed the same day.
Revision 2 applied the owner's outside review, whose answers to Q52–Q65 the owner ruled ("make the revision and yes
they can be rulings"); revision 3 applied the review's refinement on specialization (Q66). **Building:** the phases may
be built in a MacBook worktree during 2.7, as the 2.7 plan's §5a records (the owner's D6 ruling on PR #2972,
2026-11-08). Nothing merges until 2.8 opens and its plan places them.
**Revision:** 3
**Target:** unplaced. A 2.8 feature and the MacBook lane's input to the 2.8 plan. It creates no exception for the stabilization line before it.
**Authors:** Jason Ladd (Backspring Labs / SquadOps)
**Split from:** Capability-Backed Agents (proposed, deferred to 3.x), as the first of the bounded SIPs its §17 plans.
This SIP takes that SIP's four layers (its §21) and its assembly rules (its §27) into 2.x, restated against the
Project, the stack and the squad. Everything else in it stays in 3.x (§11). Section numbers 21 and 27 (and §27a–§27f)
refer to that SIP, which records the split in its §28.
**The owner's direction (2026-11-09):**
- "agree, pull it forward and draft the assembly SIP";
- agents are the ones equipped, and a squad profile is an assembly of agents; the agent's equipment is a *skillset*;
- "for an agent and a skillset, I'd need a spec that could be distributed in the capability pack";
- a *playbook* is what a squad follows, so the word is kept for that;
- lessons are valuable "even across projects of the same stack or skillset".

**Builds on:** SIP-0072 (development profiles), SIP-0075 (squad profiles and their API), SIP-0105 (the stack contract
and its governance), SIP-0112 (the Project and its Development Configuration), SIP-0095 (cycle-create preflight),
SIP-0109 (Campaign policy), SIP-0110 (lessons, instructions, snapshot binding and re-binding), and the task-type rules
of #559.
**First consumer:** the game-dev-roblox plan (PR #2972) and the Game Development Platform SIP (PR #2405). Their
revision 3 calls what this SIP describes a *specialty* and its content *playbooks*; their revision 4 uses skillsets
and skills instead.

## Revision log

- **Revision 1** (2026-11-09): the first draft. The stack's development profile assigned skillsets to roles, which
  equipped every agent in those roles.
- **Revision 2** (2026-11-09): the owner's outside review (on revision 1 at `8dcc547f`), applied in full, with five
  refinements the owner ruled with it:
  - **requirements and supply are separate.** The development profile declares what the work requires; the squad
    profile declares what each agent carries; preflight compares them. Selecting a stack equips no one (§5);
  - **unmet requirements are a cycle-preflight refusal,** naming the squad, the skillset and the responsibility (§9);
  - **the agent the work routes to is the one checked,** and agents may declare skillsets individually (§5.3);
  - **the base set is explicit,** so registering a new handler enables nothing for existing stacks (§6);
  - **the record holds the requirements, the supply, the assignment, the base set and the content digests,** with
    canonical hashing (§10);
  - **the binding holds through repair, retry and resume:** skill content is kept with the cycle (§10);
  - **skills follow the correction path** through the existing repair lineage (§7.1);
  - **runners don't establish engine requirements** (Q58), and §2 now describes today's selection in full;
  - **coverage, authorization and availability are three outcomes** (§8, §9);
  - **prompt budgeting, precedence and lesson handling are complete before activation** (§7, §10a);
  - **the phases separate inert metadata from activation** (§14);
  - the refinements: supply names skillset ids and requirements may constrain versions (Q52); an overlap is refused
    rather than resolved (Q62); repair reuses `repairs_revising` (§7.1); content is kept rather than refused (Q55); the
    roster hash covers declared ids and omits an empty field (Q57).
- **Revision 3** (2026-11-09): the review's refinement on specialization, at the owner's direction ("one more bit of
  feedback coming in to incorporate"):
  - **a skillset specializes engine-neutral capability contracts for a platform.** A contract says what the work is and
    what it must produce; a skillset supplies its skills, prerequisites, tools and verification procedures for one
    platform and variant (§3, §4, §6.1). A new platform adds skillsets and a provider, never a core task type (Q66);
  - **verification modes are distinct and declared,** and supporting one never implies another (§6.2);
  - **a requirement names a concrete skillset,** with its contract, platform and mode checked for consistency, and any
    alternative declared explicitly (§5.1);
  - **a paper compatibility matrix** across Roblox, Unity, Minecraft (Java Edition with GeyserMC) and The Sandbox
    (Sandbox Studio) checks that each platform is declarations plus a provider behind an adapter (Appendix A);
  - with four adjustments proposed to the owner in reply: the contract is defined beside the task type, the three
    existing planned types are their own contracts, contracts live in `squadops.capabilities`, and shared skills are
    included by reference. One addition, a `headless` mode, was ruled at acceptance (Q67).
- **Accepted** (2026-11-09), with Q67 ruled: add the `headless` mode.

---

## Intake check (2026-11-09; revision 2 the same day)

Checked against `sips/PORTFOLIO.md`: every live SIP, plan placement and recorded idea.

- **The split it comes from: Capability-Backed Agents.** Its §21 (identity, capability, skill, tool) and §27 (the
  assembly rules) move here for 2.x. That SIP records the split in its §28. Its pack loading and packaging,
  Switchboard, the interface for shipped pack code, dynamic recruitment, working sets, memory, the evidence ledger,
  the design pack and its console views stay in 3.x. **Q51** (PR #2841's question: whether Capability-Backed Agents
  takes an amendment now that the game work builds none of its mechanism) is re-ruled by this split: it takes one.
- **What a capability pack will carry.** Capability-Backed Agents §7 lists a pack's manifest: capability modules,
  binding contracts, capability-skill contracts, tool requirements. A skillset spec (§4) is the part of that manifest
  2.x needs, in a format the pack carries unchanged. In 3.x packs add definitions, content and execution providers;
  the coverage check of this SIP continues to apply to them. Its §9 named the adopted `SKILL.md` bundles "skill packs
  / playbooks"; here they are *skills* inside a skillset, and *playbook* is kept for a squad's procedure.
- **Overlaps, each with its boundary:**
  - **SIP-0075, squad profiles.** An agent entry gains a `skillsets` field (§5.2), which its API and console carry.
    The roster hash covers it (Q57).
  - **SIP-0072, development profiles** (implemented). A development profile gains a `requires` field (§5.1). The PR
    that adds it carries SIP-0072's amendment (CLAUDE.md step 5a).
  - **The Game Development Platform SIP (PR #2405).** Its engine operations, providers and result readers stay behind
    adapters. Its operation ids become a provider's implementations of engine-neutral capability contracts, each with
    a verification mode (§6.1, §6.2). Its revision 4 applies this.
  - **SIP-0105, the stack contract.** Its governance applies to the new fields: what a missing field means is stated,
    and a field is added only by a SIP. Its ledger moved stack packs and plugin loading "to a successor SIP, not yet
    drafted". This SIP builds no packaging or loading.
  - **SIP-0112, the Project.** It owns the Development Configuration and how a repository-backed product's development
    profile is selected (H.26). A profile with engine requirements is selected only by explicit, validated
    configuration (Q58); which field carries that for a Campaign is settled with SIP-0112.
  - **SIP-0095, cycle-create preflight.** Extended with coverage, authorization and availability outcomes (§9).
  - **SIP-0092 and SIP-0093, the implementation plan and its authoring.** The planner's offered task types become the
    base set plus what the required skillsets serve (§6).
  - **SIP-0109, Campaign policy.** A Campaign pins its skillset record, beside the stack and squad profile it pins
    today (§10).
  - **SIP-0110, Cross-Cycle Memory.** It owns where a lesson applies and the prompt's precedence; skills take a slot
    in that order (§7). Repair lineage reuses its rule for task instructions (§7.1). This SIP supplies the stack a
    repository-backed cycle recalls under, records each lesson as supplied, omitted or flagged, and routes lessons to
    other projects by promotion into skills (§10a). A lesson pool shared across projects would be its amendment.
  - **SIP-0112's size preflight (H.21) and the dispatch-time prompt budget.** Both count the skills a task loads
    before lessons are given space (§7).
  - **#559's task-type rules.** Capabilities stay `TaskType` members, and planning reads a property, never a type's
    identity (§6).
- **A conflict, resolved by the owner's direction:** the game SIPs' revision 3 (PRs #2405 and #2841) puts a
  `specialties` field on the squad profile and a specialty digest into the roster's snapshot hash. This SIP puts
  requirements on the development profile, supply on the agents, and the binding in a separate record (§5, §10). The
  owner directed the game work onto this SIP on 2026-11-09, and those documents' revision 4 applies it.
- **Placement.** The 2.7 plan expects `tasks/task_types.py`, `orchestration/handler_registry.py`,
  `bootstrap/handlers.py` and the profile snapshot hash unchanged (its §5, with the game-dev-roblox plan). This SIP
  changes the first and the last, so it builds in 2.8 at the earliest.
- **Questions:** Q52–Q67, ruled 2026-11-09 (§13 and the portfolio).

## Delivery ledger (current as of 2026-11-10)

| part | status | where |
|---|---|---|
| Phase 1: declarations and the record, inert: the skillset spec and its validation, the capability contracts and the mode list, the agents' `skillsets` field, the profiles' `platform` and `requires` fields, the explicit base set, the versioned record with canonical hashing (§14) | **shipped** | 2.8 (PR #3013, closing #3011) |
| Phase 2: coverage: the preflight refusals and consistency checks, the plan-gate check on the routed agent, the `plannable` property and the offered set (§5.1, §6, §9) | **shipped** | 2.8 (PR #3015, closing #3014) |
| Phase 3, part 1: skills, kept: the catalog holds each skill's text, a cycle keeps a checked copy of the skills its work requires, the record names them by digest, and which skills a task loads is decided from the record and the copy (§7, §10, §17e) | **shipped** | 2.8 (PR #3032; #3028 tracks part 2) |
| Phase 3, part 2: skills, loaded: a task is handed its skills from the kept copy at dispatch, a repair loads the skills of the step it revises, the prompt budget counts them, and where they render (§7, §7.1, §17e) | **shipped** | 2.8 (PR #3033, closing #3028) |
| Phase 4, part 1: tools, checked at creation: the authorization outcome against each provider's registered authority (`ToolAuthorityPort`), and the availability outcome against the worker registry and the sandbox client (§8, §9, §17h) | **shipped** | 2.8 (PR #3077; #3036 tracks part 2) |
| Phase 4, part 2: availability checked again when an operation task is dispatched, its ending classified `worker_unavailable` (§8, §17h) | **shipped** | 2.8 (PR #3078, closing #3036) |
| Phase 5: the Campaign's pin and recorded transitions (§10) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3037 |
| Phase 6, part 1: lessons, the recall identity and declared supersession: a repository-backed cycle recalls under its pinned development profile and records the identity it used, and a lesson a loaded skill supersedes is omitted with its reason (§10a, §17i) | **shipped** | 2.8 (PR #3079; #3038 tracks part 2) |
| Phase 6, part 2: lessons flagged when learned under an earlier version of a skill the task loads, and the promotion review (§10a, §17i) | **placed** (the 2.8 plan, adopted 2026-11-11) | 2.8, #3038 |

**What closes this SIP:** phases 1–6 shipped, with the first consumer's stack (Roblox) switched on and every existing
stack's cycles unchanged.

---

## 1. Summary

A squad profile is an assembly of agents: who they are, their roles and their models. This SIP adds **skillsets**: a
skillset is a spec binding capabilities, the skills an agent loads for them, and the tools they may call.

1. **The work requires; the squad supplies; preflight compares.** A development profile declares the skillsets its
   work requires, for each responsibility. A squad profile declares the skillsets each of its agents carries. Cycle
   preflight checks the agent each responsibility routes to, and refuses with a named reason when it lacks one.
2. **Selecting a stack equips no one.** The operator assembles or chooses the squad. Preflight reports what it can't
   supply; the platform recruits no one.
3. **A skillset is a distributable spec.** One directory holds its declaration and its skills. In 2.x skillsets live
   in the tree; in 3.x a capability pack carries the same directory, and the same check applies.
4. **A skillset specializes; it never defines.** Engine-neutral capability contracts say what the work is and what it
   must produce, over the existing task types. A skillset supplies a contract's skills, prerequisites, tools and
   verification procedures for one platform. A new platform adds skillsets and a provider behind an adapter, never a
   core task type. The base set is explicit, so registering a handler enables nothing.
5. **The binding is recorded and held.** Each cycle records the requirements, the agents that satisfied them, what
   they supplied and the content they loaded, and keeps that content for repair, retry and resume. A Campaign holds
   it until a recorded transition.

This is coverage: it says a squad declares what the work needs. Whether an agent is qualified, and whether the work
it delivers is right, stay separate evidence. For every existing stack the work requires nothing beyond the base set,
so its cycles run exactly as they do today. Roblox is the first platform with requirements, and the first specialization
of the game contracts: a Studio verification skillset for QA and a Luau skillset for development. Appendix A checks the
same model on paper against Unity, Minecraft and The Sandbox.

## 2. The problem: six places decide what a cycle's agents have, and two record it

| what is decided | where it's decided today | what records it |
|---|---|---|
| the stack, for a greenfield product | the cycle's `build_profile` (`stacks/scaffold.py:2375`); a Campaign's `CampaignPolicy.stack`, passed to each launch as `build_profile` and `development_profile` (`campaigns/models.py:620`, `campaigns/launch_requests.py:34`) | the cycle's config |
| the development profile, for a greenfield product | the scaffold stack decides; a declared name may repeat it; otherwise the declared name, or the default `python_cli` (`stacks/scaffold.py:2350`, `stacks/development_profiles.py:658`) | the cycle's config |
| the development profile, for a repository-backed product | a profile the operator names stands, unless it contradicts the product's runners (`api/routes/cycles/cycles.py:365`); otherwise a blueprint with product conventions, then the runner kind, then `product_neutral` (`stacks/development_profiles.py:716`) | `development_profile_selection`, with its origin and fingerprint (`api/routes/cycles/cycles.py:378`) |
| the squad | `squad_profile_id`, required at creation (`api/cycle_schemas.py:73`) | `squad_profile_snapshot_ref`, a hash of the roster (`cycles/lifecycle.py:276`) |
| what each agent can do | the handlers its roles get: a fixed list, filtered by role when an agent process starts (`bootstrap/handlers.py:77`, `orchestration/handler_registry.py:100`) | nothing |
| the planner's task types | a fixed set of three (`cycles/implementation_plan.py:59`); `builder.assemble` is offered only when the squad has a builder, a `build_profile` is set and the cycle isn't an increment (`capabilities/handlers/_plan_authoring_service.py:119`) | nothing |
| prompt text for the stack | four routes: the development profile's text fields, build-profile narratives, stack narratives keyed on `build_profile` (`stacks/stack_narratives.py:26`), and per-stack request templates (`stacks/scaffold.py:2141`) | the development profile's fingerprint, which covers its prompt assets by name only (`stacks/development_profiles.py:754`) |
| tools | ports for files, containers and version control; an agent's ports bundle carries the filesystem only (`agents/base.py:28`). Models have no tool calling and nothing uses MCP | nothing |

What follows from it:
- **A stack can't require a step or an ability.** The planner's vocabulary and each role's handlers are the same for
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

The game work needs all of it: a step only a Studio-equipped QA agent can take (`qa.run_remote_operation`), skills for
Luau and Studio (the first Luau probe's findings), tools on a remote worker (Studio's operations), and a pinned
record. Revision 3 of the game SIPs built these as a *specialty* beside the existing seams. This SIP builds them into
the seams, for every stack.

## 3. The model

**Four layers,** taken from Capability-Backed Agents §21, which settled them on 2026-07-29:

| layer | the question it answers | what it is in SquadOps | the test that places a thing in it |
|---|---|---|---|
| **identity** | who is accountable | an agent in a squad profile: its role, model and the roles it serves | it has memory and accountability |
| **capability** | what the planner may assign | a task type, with its handler, the roles that serve it, its expected artifacts and its correction mapping; where one task type hosts several kinds of work, a capability contract names each (§6.1) | the planner can assign it |
| **skill** | how the model performs a procedure | content loaded into the agent's context for the work; nothing today (removed with #401) | the model loads it to do the work |
| **tool** | what executes | an operation behind a port and its adapter | it's invoked with arguments and returns a result |

**How they're put together:**
- **A squad profile** is an assembly of agents (identity). Each agent may declare the skillsets it carries.
- **A capability contract** defines a kind of work in engine-neutral terms: its task type, what it must produce, and
  the verification modes it may run in (§6.1).
- **A skillset** specializes contracts for a platform and a role: the skills loaded for each, its prerequisites, the
  tools each may request, and its verification procedures. It's a spec, versioned and digested (§4).
- **The stack** is the technology the product is built in: a platform and its variant. Its development profile declares
  the platform and the skillsets the work requires, for each responsibility.
- **Preflight** checks that the agent each responsibility routes to carries what's required (§9).
- **A playbook** is what a squad follows: a procedure across agents. This SIP keeps the word for that and defines
  nothing under it.

## 4. The skillset spec

### 4.1 What a skillset declares

```yaml
api_version: squadops.skillset/v1
skillset:
  id: roblox-studio-qa
  version: 1
  description: Verifies Roblox gameplay headlessly under Lune and by playing frozen scenarios in Roblox Studio
  roles: [qa]
  platform: {id: roblox, variants: [studio-place]}
  prerequisites:
    - provider: lune            # the Luau runner, in the QA container
    - provider: roblox-studio   # Roblox Studio and its MCP server, on a registered worker
  capabilities:
    - contract: game.unit_tests
      modes: [headless]
      skills: [luau-test-loader, shared/luau-conventions]
    - contract: game.scenario_verification
      modes: [play]
      skills: [studio-play-scenario]
      tools:
        - {id: play_scenario, provider: roblox-studio, location: worker}
```

(Illustrative: the game SIPs' revision 4 settles Roblox's content and the game contracts.)

| field | what it holds | rule |
|---|---|---|
| `id`, `version` | the spec's identity | any change to the spec or its skills increments `version`; the digest covers both |
| `description` | one line | shown in records and, later, in a pack's listing |
| `roles` | the roles that may carry it | an agent whose roles it doesn't list can't declare it |
| `platform` | the platform it applies to, and the variants | a requirement on another platform or variant can't be met by it |
| `prerequisites` | the providers it needs: a runner, an editor on a worker | checked at creation as availability (§9) |
| `capabilities[].contract` | a capability contract it specializes (§6.1) | an engine-neutral contract over an existing task type; a skillset never defines a task type, manufactures a handler or widens the base set |
| `capabilities[].modes` | the verification modes it supports for that contract (§6.2) | a subset of the contract's modes; supporting one implies no other |
| `capabilities[].skills` | the skills loaded for that contract's tasks and their repairs (§7.1) | each names a directory under `skills/` holding a `SKILL.md`, or `shared/<skill>`, a shared skill included by reference |
| `capabilities[].tools` | the operations that contract's handler may request: `id`, `provider`, `location` | a request within existing authority, never a grant (§8) |

An empty list means none, and nothing is inherited from another skillset. A shared skill lives once, under
`src/squadops/prompts/skillsets/_shared/`; each skillset that includes it records its digest, and a pack carries a copy.
Including the same shared skill in two skillsets merges nothing: Q62's refusal of overlapping suppliers still applies.
A further field is added only by a SIP: the governance SIP-0105 gives a stack's fields.

### 4.2 One directory per skillset, shaped for a pack

```
roblox-studio-qa/
  skillset.yaml
  skills/
    studio-play-scenario/SKILL.md
    luau-test-loader/SKILL.md
```

In 2.x the tree holds skillsets under the prompts seam, `src/squadops/prompts/skillsets/<id>/` (Q61): a skill's text
is prompt content, and prompt content belongs to PromptService (#448). The spec beside it is data: validated,
preflighted and shown without running anything, which is Capability-Backed Agents' rule for a pack's declarations
("code for execution, data for contract", §21). Runtime resolution, handlers and adapters stay in their own seams.

### 4.3 Distributed in a capability pack, later

A capability pack (Capability-Backed Agents §7, 3.x) carries skillset directories unchanged, with what packaging adds:
discovery, installation, the pack's version and its compatibility range, and execution providers. The spec's
`api_version` lets a later format be told apart. A pack expands where contracts, skillsets, content and providers come
from; the contracts they specialize and the coverage check of §9 are the same as the tree's.

## 5. Requirements and supply

### 5.1 The work declares what it requires, on its development profile (Q52)

A development profile gains `platform`, the platform and variant its work targets, and `requires`: for each
responsibility (a role), the skillsets the work needs, each with an optional version constraint, and the contracts and
modes the work needs from it.

```yaml
platform: {id: roblox, variant: studio-place}
requires:
  qa:
    - skillset: roblox-studio-qa
      version: ">=1"
      needs:
        - {contract: game.unit_tests, mode: headless}
        - {contract: game.scenario_verification, mode: play}
  dev:
    - skillset: luau-dev
      needs:
        - {contract: game.gameplay_implementation}
```

- **A requirement names a concrete skillset.** Preflight checks it for consistency: the skillset specializes each named
  contract, supports each named mode for it, and applies to the profile's platform and variant.
- **An alternative is declared, never inferred:** `any_of: [{skillset: …}, {skillset: …}]` accepts either, each checked
  the same way. No skillset stands in for another because it looks similar.
- **Compatibility is decided by these declared values alone,** never by a model's judgement. A version constraint is an
  exact version or a minimum.
- **Empty means the work requires nothing beyond the base set.** Every existing profile takes the empty value, and the
  profile's fingerprint covers `platform` and `requires`.

### 5.2 Each agent declares what it carries, on its squad profile (Q60)

An agent entry in a squad profile gains `skillsets`: the ids of the skillsets that agent carries. It names ids, not
versions: an agent carries the version the deployment holds, so a skill's revision doesn't require editing every squad
profile, and a requirement's constraint decides whether that version is compatible.

```yaml
- { agent_id: eve, role: qa, model: "qwen3.6:27b", enabled: true, serves_roles: [qa],
    skillsets: [roblox-studio-qa] }
```

Empty means the agent carries none, and every existing entry takes the empty value. A squad can carry skillsets for
several stacks at once: Eve can carry a web skillset and the Roblox one, and only what a cycle's work requires is
loaded. Declarations are static; nothing assembles or recruits a squad at run time.

### 5.3 What is checked: the agent the work routes to

Today a responsibility routes to the first enabled agent serving that role (`cycles/agent_config.py:101`), so each
requirement is checked against exactly that agent. An agent elsewhere in the roster carrying the skillset doesn't
satisfy it. Where several agents may perform a responsibility, coverage by any one of them suffices. Requiring
different agents for different responsibilities applies only when the work declares a separation of duties, which no
profile does in 2.x.

**One supplier per capability (Q62).** A responsibility may require several skillsets, but two that both add skills
or tools to the same capability are refused at creation, by name, and the profile's author resolves the overlap.

**Resolution is a function of declared configuration (Capability-Backed Agents §27b).** The inputs: the cycle's
effective configuration, the Project's Development Configuration at the revision the cycle pins, the squad profile,
and the Campaign's policy when a Campaign launched the cycle. The objective, the PRD, a framing artifact and the plan
never select a requirement or a supplier. It runs at cycle creation, after the development profile is pinned
(`_pin_development_profile`, `api/routes/cycles/cycles.py:334`) and before framing or any model work.

## 6. Capabilities: contracts, modes, the base set and the planner's vocabulary (§27a)

### 6.1 Capability contracts

A capability contract defines a kind of work in engine-neutral terms, once, for every platform:

| field | what it holds |
|---|---|
| `id` | for example `game.scenario_verification` |
| `task_type` | the existing engine-neutral task type it runs as, for example `qa.run_remote_operation` |
| `evidence` | what it must produce, in SIP-0096's vocabulary: for example one executed-passed, executed-failed or not-executed result per assertion |
| `modes` | the verification modes it may run in (§6.2) |

- **They're declarations in `squadops.capabilities`,** beside the task contracts that package already holds (Q23).
  Skill text stays under the prompts seam.
- **The three existing planned types are their own contracts:** `development.develop`, `qa.test` and `builder.assemble`
  need no separate declaration. A domain may declare a contract over one of them when its evidence differs, for
  example `game.gameplay_implementation` over `development.develop` and `game.unit_tests` over `qa.test`.
- **Several contracts may share a task type.** `qa.run_remote_operation` can host scenario verification, build
  verification and capture; the contract and its mode say which. A plan names the contract and mode, never a
  platform's operation id, so plans stay engine-neutral.
- **A platform never adds a core task type.** It adds skillsets that specialize the contracts, and a provider behind
  an adapter that implements their operations (the Game Development Platform SIP's).
- **The game contracts are defined once,** in the game SIPs' revision 4, and only as the first consumer needs them.
  Appendix A shows the others would fit.

### 6.2 Verification modes

A closed list, extended only by a SIP. A contract and a skillset each declare the modes they support, and supporting one
mode never implies another.

| mode | what it exercises |
|---|---|
| `build` | compiling or building the product |
| `headless` | tests that run outside the engine's runtime (Q67) |
| `editor` | the product inside its editor, without running it |
| `play` | the product running: a play session, a dedicated server, a runtime test |
| `multiplayer` | several clients or players at once |
| `capture` | screenshots or recordings, as evidence |

### 6.3 The base set and the planner's vocabulary

- **Capabilities stay central.** Each is a `TaskType` member with its handler, the roles that serve it, its expected
  artifacts and its correction mapping (#559: constants at the core). Nothing a skillset declares reaches the handler
  registry (Q23's rule for packs).
- **Registration isn't enablement.** The base set is explicit and versioned, `base@1`: today's three plannable types
  (`development.develop`, `qa.test`, `builder.assemble`, under today's builder rule) and every step the fixed step
  tables dispatch. Registering a new handler, such as `qa.run_remote_operation`'s, adds nothing to it.
- **Planning reads a property.** `TaskType` gains `plannable`. `_KNOWN_BUILD_TASK_TYPES` becomes derived from the base
  set.
- **The offered set** is the base set's plannable types plus the contracts, in the modes, that the cycle's requirements
  name, each supplied by the agent its responsibility routes to. A skillset an agent carries but the work
  doesn't require widens nothing. Every existing stack is offered exactly today's types, and the guarantee is
  checked with the new handler installed.
- **Plan validity stays decidable offline.** Given a cycle's record, whether a plan is well formed is a property of
  the plan and the record.
- **A new plannable type is its own proposal,** with its handler, expected artifacts, footprint rules, correction
  mapping and every verifier seam that judges it (CLAUDE.md, "Typed checks"). The first is `qa.run_remote_operation`,
  which the Game Development Platform SIP proposes.

## 7. Skills

- **The format:** a `SKILL.md` file: front matter with `name` and `description`, a markdown body, and optional
  resources beside it. Capability-Backed Agents §9 adopted the format on 2026-07-01 because it runs under local
  models as well as frontier ones.
- **The loader is explicit.** A task receives the skills declared for its capability in the required skillsets its
  agent supplies, and those of the step it repairs (§7.1). Skills its agent carries for work this cycle doesn't
  require aren't loaded. The model never chooses skills from their descriptions.
- **Loaded from the kept copy.** The resolved skill text and resources are copied with the cycle's record at creation
  (§10), and every task, repair, retry and resume loads from that copy.
- **Budget.** The dispatch-time prompt budget (`capabilities/prompt_budget.py:124`) counts the skills and resources a
  task loads before optional lessons are given space, and the size preflight (SIP-0112 H.21) counts them before the
  first cycle.
- **Precedence in the prompt,** highest first: authoritative records (the product's owner decisions and repository
  rules), task instructions, project instructions (SIP-0110), skills, the stack text of the four existing routes, then
  lessons. A skill renders in the stack's section, where `system_prompt_supplement` renders today.
- **Authorship:** Q47's rule for the game packs applies to every skill: a frontier model drafts, the owner approves,
  and each skill is replay-tested on the models that will run it before it's used.
- **The existing four routes stay** until a consolidation proposal moves them with a byte-identical test (Q54).

### 7.1 Skills across the correction path

A repair has its own task type: a failing `qa.test` is repaired by `qa.test_repair` when the fault is in its own
artifact, and by `development.correction_repair` when it's in the application (`repair_steps_for`,
`cycles/task_plan.py:417`). Loading by exact capability would give a repair none of the original step's guidance. So
a repair loads the skills of the step whose output it revises, by `repairs_revising` (`cycles/task_plan.py:372`):
the rule SIP-0110 already uses to carry a task type's instructions to its repairs. A retest that dispatches the
original task type again loads that type's skills; a retest that re-runs a check or an operation loads none.

**A failure and its repair, on the Roblox squad of §16:**

| step | agent | loads (from the cycle's kept copy) |
|---|---|---|
| `development.develop` | Neo | `luau-dev`'s skills for `development.develop` |
| `qa.test`: writes the `*.spec.luau` suite | Eve | `luau-test-loader` |
| the suite fails in the test's own file → `qa.test_repair` | Eve | `luau-test-loader`, by lineage from `qa.test` |
| the suite fails in the application → `development.correction_repair` | Neo | `luau-dev`'s skills for `development.develop`, by lineage |
| the suite is re-run | the runner | none: a check |
| `qa.run_remote_operation`: plays a scenario in Studio | Eve | `studio-play-scenario`; Studio's operation is requested through the handler |
| the scenario fails in the application → the dev repair its correction mapping names | Neo | `luau-dev`'s skills, by lineage |
| the operation is re-run | Eve's handler | none: an operation |

## 8. Tools (§27e)

- **A tool is an operation behind a port,** invoked by a capability's handler with arguments. The model never invokes
  a tool itself (Q59).
- **A skillset requests tools; it grants nothing.** Each request is checked against the authority that already
  governs the operation: its deny list, its argument and target validation, and its compatibility checks (for Studio,
  the Game Development Platform's). Carrying a skillset never authorizes an operation. The general plugin permission
  model stays in 3.x.
- **Locations:**

  | location | available when |
  |---|---|
  | `agent` | always: the agent's own container |
  | `sandbox` | the sandbox service is enabled (today's preflight check) |
  | `worker` | a registered worker that declares the tool is online. The worker registry is the Game Development Platform SIP's |

- **Late binding is allowed when declared.** Which worker serves a tool is bound at dispatch; that the tool is
  declared, authorized and has a worker that can serve it is checked at creation.

## 9. Checks (§27c, extending SIP-0095)

**At creation,** in `_run_create_preflight` (`api/routes/cycles/cycles.py:203`), before framing or any model work. Each
outcome is its own refusal, with its own reason, through the existing preflight error:

| outcome | when | example reason |
|---|---|---|
| **coverage** | the agent a responsibility routes to lacks a required skillset, or carries an incompatible version | "Squad skillset requirements not met. Selected squad: `game-dev-roblox`. Missing: `roblox-studio-qa` for `qa` (agent `eve`). Select or configure a squad with an eligible agent carrying that skillset." |
| **declaration** | a skillset is unknown; an agent declares one its roles don't allow; two required skillsets add to one capability; or a requirement is inconsistent: its skillset doesn't specialize the named contract, support the named mode, or apply to the profile's platform and variant | names the skillset, the agent, the contract or the mode |
| **authorization** | a required skillset requests a tool its operation's authority doesn't allow | names the tool and the rule |
| **availability** | a required tool has no available provider: a worker offline, the sandbox disabled | names the tool and the location; the squad still carries the skillset |

**At the plan gate,** where the plan first exists: every task is a base-set type, or a contract and mode the cycle's
requirements name, supplied by the task's routed agent. A plan that fails is refused at the gate with the reason, and the cost
is a re-plan. Dispatch's `handler_not_found` stays as the last line.

Coverage says the squad declares what the work needs. Qualification (whether an agent does the work well) and the
verification of delivered work stay separate evidence (SIP-0096).

## 10. The record, and holding the binding (§27d, §27f)

**The skillset record,** `squadops.skillset-record/v1`, stored with the cycle beside `squad_profile_snapshot_ref`
(Q57):

| part | what is recorded |
|---|---|
| the base set | its version (`base@1`) and the capabilities it enabled |
| the squad | the squad profile's id and its roster hash |
| the development profile | its name, how it was selected, and its fingerprint, which covers `requires` and its assets' content |
| the requirements checked | each responsibility, skillset and version constraint |
| the assignment | for each requirement, the agent it routed to and the skillset it supplied: id, version and digest |
| the content | each loaded skill's and resource's digest, and a reference to the kept copy |
| the digest | a sha256 over the record's canonical JSON (sorted keys, UTF-8, no insignificant whitespace), excluding the digest itself; the hashing rule is versioned with the record |

The record holds enough to validate the assignment later without reading today's files: `base@1` and the supplied
versions and digests identify historical equipment where a role's name alone wouldn't.

**The roster hash** covers each agent's declared `skillsets` and omits the field when it's empty, so every existing
hash stays the same (Q57).

**Holding the binding:**
- **Repair, retry and resume** load skill content from the kept copy, never from the tree. A redeploy that changes a
  skill doesn't reach a paused cycle. Handler and adapter code can't be kept, so a resume after a redeploy names the
  change of deploy in the record, as development-profile drift is named on retry today.
- **Replay** matches the record's digest (`cycles/replay.py:56`).
- **A Campaign** pins its record at creation, and its cycles load from the Campaign's kept copy. A catalog change
  that touches nothing its work requires (a new skillset, another skillset's revision) has no effect. A change to
  the equipment assigned to its work (a requirement, a supplying agent's declaration, a required skillset's version)
  stops the next launch with the changed parts named, and it continues only through the owner's recorded transition.
  The transition preserves earlier evidence, frozen verifier content and the Campaign's pinned lesson snapshot.
  SIP-0110's `rebind` is the precedent for the recorded act (Q55).

## 10a. Lessons and skillsets

Cross-Cycle Memory (SIP-0110) scopes each lesson by project, task type, role, stack and model family
(`memory/lessons.py:53`), and recall matches all five.

- **The stack a repository-backed cycle recalls under (Q63).** Recall reads a cycle's stack from its `build_profile`
  (`cycle_stack`, `cycles/benchmark_registry.py`). A repository-backed cycle has none, so it recalls only lessons
  stored for any stack. Such a cycle falls back to its pinned development profile. The record names which identity
  recall used and the rule's version, and a cycle with a `build_profile`, and every lesson already stored, keeps its
  present meaning.
- **A skill and a lesson (Q64).** Approved skill guidance outranks optional lessons (§7). A version change alone
  doesn't mean a lesson conflicts. A conflict is declared: a skill revision may name the lessons it supersedes, and a
  promoted skill names the lessons it came from. Recall records, for each task, every eligible lesson as **supplied**,
  **omitted** (superseded by a skill the task loads, or over budget), or **flagged** (supplied, and learned under an
  earlier version of a skill the task loads, for review).
- **Lessons across projects of the same stack or skillset (Q65).** Today a lesson names one project
  (`memory/lessons.py:77`). In 2.x a lesson reaches other projects by **promotion into a skill:** rewritten into its
  skillset's skills, owner-approved and replay-tested under Q47's rule, after a generalization and distribution review
  that checks it holds beyond its project and carries nothing specific to one product across its owner's boundary
  (SIP-0112 B.5.1). Every project whose agents carry the skillset then gets it. A shared lesson pool keyed by
  skillset, recalled across projects, is a separate SIP-0110 amendment.

## 11. What stays in Capability-Backed Agents (3.x)

Pack discovery, installation and packaging (its §7), Switchboard as the loader, the interface for shipped pack code and
its versioning (its §21), dynamic recruitment and routing by skillset (its §8), working sets (its §10), memory beyond
§10a (its §11, already deferred to Cross-Cycle Memory), the workspace and evidence ledger (its §12), the design pack
(its §13), the general permission model (its §14–15), and its console views (its §17 item 10). This SIP is the in-tree
starting point of its §17 split: the vocabulary, the assembly rules, and the skillset spec and coverage check a pack
will work within.

## 12. Vocabulary

| word | meaning here |
|---|---|
| **squad profile** | an assembly of agents: roles, models, the roles each serves, and the skillsets each carries |
| **skillset** | a spec specializing capability contracts for a platform and a role: the skills loaded for them, its prerequisites, the tools they may request and the modes it supports; one directory, versioned and digested; what a capability pack carries |
| **capability contract** | an engine-neutral definition of a kind of work: its task type, its evidence and its modes. Capability-Backed Agents §7's *capability modules* are these |
| **verification mode** | one of `build`, `headless`, `editor`, `play`, `multiplayer`, `capture` (§6.2) |
| **platform**, **variant** | the engine or product a stack targets (`roblox`, `unity`, `minecraft-java`, `the-sandbox`) and its form (a local place file, an editor version, a server type, a tool) |
| **requirement** | a skillset, with an optional version constraint, that a development profile declares a responsibility needs |
| **coverage** | the routed agent for each responsibility carries what the work requires; checked at creation, distinct from qualification and verification |
| **skill** | content an agent loads to do the work, in the `SKILL.md` format (Capability-Backed Agents §21). SIP-0040's governed execution unit was removed with #401 |
| **capability** | a dispatchable unit: a task type, its handler, its roles, its artifacts and its correction mapping. The `squadops.capabilities` package holds exactly these: task contracts and handlers (Q23) |
| **base set** | the capabilities enabled with no requirement: explicit and versioned (`base@1`) |
| **tool** | an operation behind a port, invoked with arguments |
| **stack** | the technology a product is built in: a platform and variant; its development profile declares the work's requirements |
| **development profile** | a stack's settings bundle (SIP-0072; one meaning, Q36) |
| **capability pack** | packaging, in 3.x: it carries skillset directories and adds loading and providers (Capability-Backed Agents §7) |
| **stack pack** | packaging, in 3.x: a stack's declaration as a loadable plugin (SIP-0105's intent) |
| **playbook** | what a squad follows: a procedure across agents. Kept for that, and defined by a later SIP |
| **specialty** | retired. The game SIPs' revision 3 used it for what this SIP puts in skillsets |

## 13. Rulings (2026-11-09)

The owner's outside review answered each question, and the owner ruled its answers, with the refinements below, the
same day: "make the revision and yes they can be rulings". Q66 is the review's later refinement, applied at the owner's
direction. Q67 was ruled at acceptance: "Q67 add headless".

| # | question | ruling |
|---|---|---|
| **Q52** | Where requirements and supply live | **The development profile declares required skillsets; the agents in a squad profile declare the skillsets they carry; the two stay separate.** Supply names ids, and a requirement may constrain versions (refinement) |
| **Q53** | The names *skillset*, *skill*, *playbook* | **As written** |
| **Q54** | Skills as a fifth route for a stack's prompt text | **Approved for now,** with explicit loading, precedence, budgeting and content hashing (§7). Consolidating the four existing routes follows separately |
| **Q55** | A Campaign whose equipment changes | **The recorded requirements and bindings are enforced.** Changes to equipment assigned to its work need a recorded transition; unrelated catalog changes have no effect; earlier evidence is never rewritten. Skill content is kept with the Campaign, so a redeploy doesn't change it (refinement) |
| **Q56** | Who selects the squad | **The operator.** Preflight reports unmet requirements; the platform recruits or assembles no replacement |
| **Q57** | Where the binding's digest lives | **A separate, versioned requirements-and-equipment record beside the roster hash,** with the resolved base set and the actual supplying agents. The roster hash covers the declared skillset ids and omits an empty field (refinement) |
| **Q58** | How a repository-backed product's development profile is selected | **Runners supply language and test facts; explicit, validated configuration establishes engine-specific requirements.** Luau alone never implies Studio. A profile with requirements is selected only explicitly |
| **Q59** | Who invokes a tool | **The handler, in 2.x, through authorized operations.** Carrying a skillset grants no permission |
| **Q60** | Per-agent variation | **Explicit, static per-agent declarations,** checked against the agent existing routing selects. No dynamic recruitment or routing by skillset |
| **Q61** | Where skillset directories live | **`src/squadops/prompts/skillsets/<id>/`** for declarations and content; resolution, handlers and adapters stay in their own seams |
| **Q62** | How many skillsets, and overlap | **Several,** checked by id and compatibility. Two required skillsets adding to one capability are refused, and the profile's author resolves it (refinement: no resolver in 2.x) |
| **Q63** | The stack a repository-backed cycle recalls under | **The pinned development profile, as the fallback when no build profile exists,** with the identity used recorded and existing meanings preserved |
| **Q64** | A skill and a lesson | **Approved skill guidance outranks optional lessons.** Supersession is declared; a version change alone isn't a conflict |
| **Q65** | Lessons across projects | **Owner-reviewed, replay-tested promotion into skills in 2.x,** after a generalization and distribution review. A shared cross-project recall pool is a separate SIP-0110 amendment |
| **Q66** | What a skillset specializes | **Engine-neutral capability contracts, for a platform and variant,** with the skills, prerequisites, tools and verification procedures that platform needs. A requirement names a concrete skillset, with its contract, platform and mode checked for consistency; alternatives are declared. A new platform adds skillsets and a provider, never a core task type. The review's refinement, applied in revision 3 at the owner's direction; it reopens none of Q52–Q65 |
| **Q67** | A `headless` verification mode, beside the review's build, editor, play, multiplayer and capture | **Added** (ruled at acceptance). Lune for Roblox and JUnit for Minecraft run tests outside the engine's runtime, which none of the other five describes, and Roblox's first increments depend on it |

**One refinement outside the questions:** a repair loads the skills of the step it revises through the existing
`repairs_revising` lineage (§7.1), so no skillset declares its repair bindings separately.

## 14. Phases, and how each is proved

| phase | what | proved by |
|---|---|---|
| **1. declarations and the record (inert)** | the skillset spec and its validation; the capability contracts and the mode list; the agents' `skillsets` field; the profiles' `platform` and `requires` fields; `base@1`; the versioned record with canonical hashing | every existing cycle's prompts and plans are byte-identical to today's; every existing roster hash is unchanged; a wiring test enters at cycle creation and reads a record holding `base@1` and no requirements |
| **2. coverage** | the preflight outcomes; the plan-gate check on the routed agent; `plannable`; the offered set | with a fixture capability's handler registered for `qa`, an ordinary web cycle isn't offered it; a cycle requiring a skillset its routed agent lacks is refused with §9's reason, and an agent elsewhere carrying it doesn't help; an overlap, a role mismatch, and a requirement whose skillset doesn't specialize its contract, support its mode or apply to its platform are refused |
| **3. skills** | loading with repair lineage; the kept copy; dispatch-time budgeting; precedence; digests | §7.1's failure and repair on a fixture, each step receiving exactly its listed skills; a redeploy that edits a fixture skill leaves a paused cycle on its kept copy |
| **4. tools** | requests within existing authority; the coverage, authorization and availability outcomes | three fixtures, three distinct refusals; an offline worker reads as availability, never as a missing skillset |
| **5. the Campaign** | the pin; recorded transitions | an unrelated catalog addition has no effect; a change to assigned equipment stops the next launch with the parts named; after a recorded transition, earlier evidence, verifier content and the lesson snapshot are unchanged |
| **6. lessons** | the recall identity; supplied, omitted and flagged records; declared supersession; the promotion review | a repository-backed cycle recalls under its development profile and records the identity used, while a cycle with a `build_profile` recalls exactly as before; a superseded lesson is omitted with its reason |

**Activation.** Phase 1 changes no behaviour and may land alone. A development profile that declares requirements is
switched on only after phases 2–6 have shipped: loading, authorization, budgeting, pinning and lesson handling all
apply to it. The Roblox consumer needs all six. The fixtures live in tests only and never in a deployed registry.
Where the code lives is the implementation plan's, within the import-direction rules: `squadops.stacks` holds the
development profiles as data and imports neither `squadops.capabilities` nor `squadops.cycles`
(`tests/unit/architecture/test_package_import_direction.py`).

## 15. Non-goals

- pack discovery, loading, installation and packaging, for stacks or capabilities (3.x);
- dynamic recruitment, assembling a squad automatically, and routing by skillset;
- separation of duties, until a profile declares it;
- model-side tool calling and the general permission model (Q59);
- qualification of an agent, as distinct from coverage;
- squad playbooks;
- working sets and the evidence ledger; memory beyond §10a;
- a lesson pool shared across projects (Q65: a SIP-0110 amendment);
- console views of skillsets, beyond SIP-0075's API carrying the new field;
- any change to what existing stacks' cycles run with;
- consolidating the four existing routes for stack prompt text (Q54);
- the worker registry and the remote execution protocol (the Game Development Platform SIP's);
- any implementation for Unity, Minecraft or The Sandbox: Appendix A is paper only;
- publishing to any platform, and any wallet, token, LAND or other on-chain operation on The Sandbox.

## 16. Two squads, worked through

**An existing web stack, unchanged.** A greenfield cycle with `build_profile: fullstack_fastapi_react` and the `full`
squad. The development profile requires nothing, and no agent declares a skillset.

| record part | value |
|---|---|
| base set | `base@1`: `development.develop`, `qa.test`, `builder.assemble` (the squad has a builder and `build_profile` is set) |
| requirements | none |
| assignment | none |
| offered to the planner | `development.develop`, `qa.test`, `builder.assemble`, as today |

**The first stack with requirements: Roblox.** A Campaign on `z_tower-ascension`, a repository-backed Project. The
operator names the `game_dev_roblox` development profile, which the product's Luau runner doesn't contradict (Q58). It
declares the platform `roblox`, variant `studio-place`, and requires `roblox-studio-qa` (version 1 or later) for `qa`,
for unit tests in `headless` mode and scenario verification in `play` mode, and `luau-dev` for `dev`, for gameplay
implementation. The operator selects the
`game-dev-roblox` squad, in which Eve declares `roblox-studio-qa` and Neo declares `luau-dev`.

| record part | value |
|---|---|
| base set | `base@1` (a repository-backed cycle takes no `build_profile`, so `builder.assemble` isn't offered) |
| requirements | `qa`: `roblox-studio-qa` `>=1`; `dev`: `luau-dev` |
| assignment | `qa` → Eve, `roblox-studio-qa@1` and its digest; `dev` → Neo, `luau-dev@1` and its digest |
| content | the digests of `studio-play-scenario`, `luau-test-loader` and `luau-dev`'s skills, and the kept copy |
| offered to the planner | `development.develop` (as gameplay implementation), `qa.test` (as unit tests), and `qa.run_remote_operation` as scenario verification in `play` mode, which `roblox-studio-qa` specializes |

Had the operator selected `full`, where no agent declares a skillset, the Campaign would be refused at creation:
"Squad skillset requirements not met. Selected squad: `full`. Missing: `roblox-studio-qa` for `qa` (agent `eve`),
`luau-dev` for `dev` (agent `neo`)." Had Eve carried the skillset and Studio's worker been offline, the refusal would
be an availability one, naming the worker. §7.1 shows what each step of a failure and its repair loads. A redeploy that
revises a skill leaves the Campaign on its kept copy; moving to the revision is the owner's recorded transition.

## 17. Post-acceptance amendments

### 17a. Phase 1 as built (2026-11-09)

Building phase 1 (#3011) read the accepted text against the code. Six points narrow or correct it. **Ruled by the
owner on 2026-11-09, each as recommended** ("approve as recommended"), on the implementer's write-up in phase 1's PR
(#3013). The PR merges nothing before 2.8.

1. **The development profile's fingerprint covers its prompt assets by name, as it does today.** §10's table says it
   "covers `requires` and its assets' content", and §2's table had it right: by name only.
   - **Evidence:** `development_profile_fingerprint` digests the profile's dataclass fields
     (`stacks/development_profiles.py`), and an asset is a template name there.
   - **Why it stays:** digesting asset content changes all seven fingerprints. Every stored
     `development_profile_selection` would stop matching, and every retry of a pinned cycle would report drift on a
     profile nobody changed. Covering content belongs with the consolidation of the stack's prompt routes (Q54).
     A skill's content is digested in the record's own `content` part (phase 3), which is what §10 needs.
2. **`platform` and `requires` are covered by the fingerprint where declared.** §5.1 says the fingerprint covers
   them and that every existing profile takes the empty value. A profile that declares neither is digested without
   their keys, so each existing fingerprint is unchanged. It's Q57's rule for the roster hash, applied to the
   profile. `test_profile_requirements.py` holds it for every registered profile.
3. **The record is its own column.** §10 says "stored with the cycle beside `squad_profile_snapshot_ref`". It's
   `cycle_registry.skillset_record` (migration 2200), and `Cycle.skillset_record`.
   - **Why not a key in `execution_overrides`,** where `development_profile_selection` sits: a key there reaches
     every task as part of `resolved_config`, is counted by the prompt budget, and changes each run's
     `resolved_config_hash`. Phase 1 would not be inert.
4. **In phase 1 the record's base-set part names the base set, and the offered set arrives with phase 2.** §16's
   worked example shows `builder.assemble` absent for a repository-backed cycle. That narrowing is today's builder
   rule, applied where the planner is offered its types (`_plan_authoring_service.py`). The record lists
   `base@1`'s three plannable types for every cycle until phase 2 builds the offered set and records it.
   `assignment` and `content` are empty for the same reason: phases 2 and 3 fill them.
5. **How a greenfield cycle's profile was selected is recorded with two new origins.** §2 notes that only a
   repository-backed cycle records a selection. The record's "how it was selected" reads that selection's origin
   where one exists (`operator`, `blueprint`, `derived`), and otherwise `stack` (the scaffold stack requires the
   profile), `operator` (the configuration names it) or `default`.

6. **Until a stack declares requirements, `platform` and `requires` are recorded exceptions to the stack
   contract's admission rule.** SIP-0105's rule, enforced by `test_stack_blueprint_falsification.py`, admits a
   stack field once two stacks demonstrate it, and takes a one-stack field only as a declared optional with its
   reason. A field no stack populates is *unevidenced*, and the rule says it shouldn't be a field. Phase 1 adds
   both fields empty on every stack, by design (§14: declarations first, activation after phases 2–6).
   - **What the PR does:** it records both in the guard's `_UNEVIDENCED` list with this reason, and adds a test
     that fails the day a stack populates either, so the exception can't outlive its reason. When
     `game_dev_roblox` is registered they become declared optionals, with the reason the other stacks leave them
     unset.
   - **The alternative, not taken:** hold the two fields back until the PR that registers the first profile
     declaring them. Phase 2's coverage check reads `requires`, so they would still precede that profile by
     several phases, and the exception would only start later. The owner ruled the recorded exception.
   - This is the one place phase 1 is in tension with a standing rule, and the intake check's "its governance
     applies to the new fields" did not foresee it.

**Corrections to anchors and citations,** none of which changes the design:
- five cited lines sit one line above their target (`cycles/agent_config.py:101`, `stacks/scaffold.py:2350` and
  `:2375`, `cycles/replay.py:56`, `cycles/implementation_plan.py:59`,
  `capabilities/handlers/_plan_authoring_service.py:119`);
- §10's "Replay matches the record's digest (`cycles/replay.py:56`)" describes later work. Today the create route
  compares `prd_ref`, `build_profile` and `contract_ref` only, so the listed `development_profile_fingerprint`
  element is never compared there;
- §6.1 and §12 cite Q23 for the `squadops.capabilities` package holding task contracts. Q23 rules that the package
  keeps its name and that packs never bind into the task-type registry. The contracts it holds today are SIP-0.8.6's
  `TaskContract` manifests, a different record, and the capability contracts sit beside them in
  `capabilities/capability_contracts.py`, as `CapabilityContractDeclaration`: the bare class name is a spelling
  #922 retired for those manifests, and its guard still refuses it;
- §5.3's "first enabled agent serving that role" has one enabled agent per role only for a profile written through
  the API (`validate_agent_entries`). A profile seeded from `config/squad-profiles.yaml` isn't run through that
  check. Phase 2's coverage check reads the routed agent either way.

### 17b. The Roblox dev skillset's id (2026-11-09)

**What changed.** The game SIPs' Q68 asked whether skillset ids take the game-dev-roblox plan's D8 form. **The owner
ruled it on 2026-11-09** ("approve as recommended"): ids keep this SIP's platform-first form, and the Roblox dev
skillset is `roblox-luau-dev`, so that every Roblox skillset sorts together. §5.1, §7.1, §16 and Appendix A write
that skillset as `luau-dev`. Those examples are illustrative (§4.1), and they read as `roblox-luau-dev`.

**The same ruling approved the first consumer's additions** to §16's worked example, which the game SIPs' revision 4
records: a fourth contract, `game.increment_design`, over `strategy.propose_increment`, and a strategy skillset
(`roblox-increment-design`), since strategy writes each play scenario.

### 17c. Phase 2 as built (2026-11-09)

Building phase 2 (#3014) settled five points the accepted text leaves open or states differently. **Ruled by the
owner on 2026-11-10, as written** ("approve both SIP-0116 17c and 17d"), on the implementer's write-up in phase 2's
PR (#3015).

1. **The planner's prompt doesn't render offered contracts yet.** §6.3 says the offered set is what the planner is
   offered. Phase 2 computes it, records it (the record's `offered` part) and enforces it at the plan gate on both
   validation seams. The plan-authoring prompt still lists the base set's task types, as today.
   - **Why:** no contract outside the base set exists until the Game Development Platform SIP's
     `qa.run_remote_operation`. Telling a planner how to name a contract and a mode is prompt content, which belongs
     in a managed prompt asset with a worked example (`docs/PROMPT_AUTHORING_STANDARD.md`), and 2.7 is changing the
     prompt manifest (#2933, #2935).
   - **Where it lands:** with the first planned contract (that SIP's phase 2a). Until then a plan can't name a
     contract its planner was never shown, and the gate refuses one that does.
2. **A plan task names its contract and mode in two optional fields,** `contract` and `mode`. §6.1 says a plan names
   the contract and mode and doesn't say how. A base-set task omits both, and a plan of base-set tasks serializes
   and hashes exactly as before. The multi-contributor path carries both: a role's proposed task, the merge and the
   merged plan's own serializer (§17d point 4).
3. **One supplier per capability is checked per responsibility and task type.** §5.3 (Q62) refuses "two that both
   add skills or tools to the same capability". Two required skillsets overlap when both supply a contract over the
   same task type for the same role. One skillset supplying two contracts over one task type is a single supplier.
4. **A role mismatch is checked on the routed agent's supplying skillset.** §9 lists "an agent declares one its
   roles don't allow" as a declaration outcome. It's refused when that skillset is the one the routed agent would
   supply for a requirement. A squad profile may name skillsets a cycle's work doesn't require, including ones this
   deployment doesn't hold (§5.2), and those aren't this cycle's findings.
5. **The record gains `offered`,** beside `assignment`: each contract and mode a requirement names, with its task
   type, role, routed agent and supplying skillset. It's what the plan gate reads, so a plan's validity stays a
   property of the plan and the record (§6.3).

**Not built in phase 2, as §14 orders it:** the authorization and availability outcomes (phase 4, with the worker
registry).
### 17d. No silent reads (2026-11-10)

**What prompted it.** The owner, on phases 1 and 2 as built: "I also want to be sure we avoid silent fallback that
have been a killer on this project". The code of both phases was read again for anything that fills in, skips or
reinterprets a value without saying so. Each place found now refuses with a named reason.

**Ruled by the owner on 2026-11-10:** "approve both SIP-0116 17c and 17d". That includes point 1's change in
behaviour.

**Phase 1 (#3011):**
1. **An unknown development profile is refused at cycle creation.** This is a change in behaviour, and the one
   exception to phase 1's "inert".
   - **Before:** a cycle naming a profile the registry doesn't hold was accepted, and failed at its first develop
     or test task, after framing. `_pin_development_profile` left an unknown name "to the create preflight", which
     had no such check.
   - **Now:** `development_profile_known_decision` refuses it with the name and the known profiles. The record
     holds the profile's fingerprint and requirements, so an unresolvable name has no record to write.
   - **Who is affected:** a cycle whose configuration misspells its profile, and one that named a profile no step
     ever read (a selftest, a planning-only cycle). Both are refused in seconds with the list to choose from.
2. **A `skillsets` value that isn't a list of ids is refused,** naming the profile and the agent, where a squad
   profile is read from its file or its row. Read leniently, a bare `skillsets: roblox-studio-qa` becomes one
   skillset per character.
3. **A selection's origin is never borrowed.** The record takes "how it was selected" from the cycle's recorded
   selection only when that selection names the profile in force. Otherwise building the record raises.

**Phase 2 (#3014):**
4. **A task's contract and mode survive the proposal, the merge and both serializers.** As first built, a role's
   proposed task dropped both fields, and so did the merger's own serializer. A `qa.test` proposed as a contract in
   `headless` mode would have reached the gate as a plain `qa.test`, which the gate accepts. A test now sets every
   plan-task field and requires each serializer to carry all of them, and it was watched failing with one field
   removed.
5. **A record that is present is read as written at the plan gate.** A record with no base-set version, no
   `offered` list, or a malformed offer is refused as unreadable. Only a cycle with no record at all takes the
   legacy reading below.
6. **A record is written only for a covered cycle.** Building one for a cycle with a coverage finding raises, so a
   caller that skipped preflight can't store requirements beside an empty assignment.
7. **Coverage asks dispatch's own routing rule** (`resolve_agent_config`) which agent a responsibility routes to.
   It first held a second copy of "the first enabled agent serving the role".
8. **Coverage for an unknown development profile raises,** and a profile with a malformed requirement is refused as
   a declaration finding. The first draft answered "requires nothing" for an unknown name, on the strength of a
   preflight check that didn't exist until point 1.

**Left as a stated reading, on purpose:**
- a cycle with no record at all was created before records existed, and reads as `base@1` with nothing offered;
- an agent entry with no `skillsets` key carries none, and a profile with no `requires` requires nothing;
- a deployment with no `skillsets/` directory holds an empty catalog. A profile that requires a skillset is then
  refused at creation as naming one this deployment doesn't hold.

### 17e. Phase 3 is delivered in two parts, and part 1 as built (2026-11-10)

**Not yet ruled:** the points below are the implementer's, for the owner's review in part 1's PR (#3032).

**Two parts,** each with a ledger row:
1. *kept:* the catalog holds each skill's text, a cycle keeps a checked copy, the record names it by digest, and
   which skills a task loads is decided from the record and the copy. Nothing is loaded at dispatch.
2. *loaded:* a task is handed its skills at dispatch, a repair loads the skills of the step it revises, the prompt
   budget counts them, and they render.

**§7 and §10, as part 1 builds them:**

| the SIP's part | as built |
|---|---|
| "the resolved skill text and resources" | **the catalog holds the text.** `Skillset.skill_files` is each skill's `SKILL.md` and resources as text, read once with the catalog and byte for byte, so the text a cycle keeps is the text its digest was taken from |
| "optional resources beside it" (§7) | **a skill's files are UTF-8 text.** A file that isn't is refused by name when the skillset is loaded. A skill is loaded into a prompt, so a resource that can't be read as text can't be part of one |
| "copied with the cycle's record at creation" | **one vault artifact of the cycle,** type `skillset_content`, written before the cycle is stored. It holds every skill of each assigned skillset, and which skills each of that skillset's capabilities loads. A cycle whose skills can't be kept (no vault) isn't created |
| what is kept | **the whole of each assigned skillset,** not only the contracts the work names: a repair loads the skills of the step it revises, and the copy's own capability list decides, never today's tree |
| "each loaded skill's and resource's digest, and a reference to the kept copy" | **the record's `content` part names each kept skill and each of its files by digest, and names no location.** §10 has replay match the record's digest, so the digest has to be a function of the equipment. A vault id differs for every cycle. The copy is found by its cycle and its type, and exactly one is expected |
| loading "from the kept copy, never from the tree" | **the copy is checked before anything is loaded from it:** its skills hash to the digests it states, and it holds exactly what the record names. A record that names skills with no copy raises. Nothing reads the tree in its place |
| "the skills declared for its capability in the required skillsets its agent supplies" | **a task that names a contract loads that contract's skills. A task that names none loads the skills of every required contract that runs as its task type.** §7.1's table loads `luau-test-loader` for a plain `qa.test`, which names no contract until the planner is shown the offered ones. In both cases the agent is the one the record assigned |
| a cycle that requires nothing | keeps nothing. Its record's `content` is `[]`, as before, and its digest is unchanged |

**Two findings for part 2,** recorded here so they aren't met again as surprises:
1. **"A skill renders in the stack's section, where `system_prompt_supplement` renders today" (§7) names a place
   only one task type has.** The supplement renders in `development.develop`'s system prompt alone, and is left out
   there for a repository-backed product. `qa.test` carries its stack text in the request, the repair handlers carry
   none, and `qa.run_remote_operation` calls no model. Task and project instructions render in the request, after
   the system prompt. Part 2 places skills where every consuming task has a place, and amends §7 with what it
   builds.
2. **A repair's envelope names the step it repairs only by `failed_task_type`.** Part 2 resolves the skills from
   the record by the task type the repair revises and the agent it routes to.

**Found while reading for it, and fixed on its own (#3030):** phase 2a's repair-routing entry for
`qa.run_remote_operation` was read by `repairs_revising` as lineage, so a task instruction for the operation also
reached the dev repair. A step that runs an operation authors nothing, and no repair revises its output.

**Citations that moved:** `repairs_revising` and `repair_steps_for` are at `cycles/task_plan.py:377` and `:422`,
and the create preflight at `api/routes/cycles/cycles.py:207`. The text above them cites the lines as they were.

### 17f. Phase 3, part 2 as built: skills loaded, and where they render (2026-11-11)

**Not yet ruled:** the points below are the implementer's, for the owner's review in part 2's PR (#3033). Points 1,
5 and 6 change what §7 says.

| §7's part | as built |
|---|---|
| "a task receives the skills declared for its capability" | **the runtime hands them on the envelope, at every dispatch.** `SkillSupply.hand` reads the cycle's kept copy (checked, §17e) and puts the task's skills on its envelope at its first dispatch, each re-dispatch and each repair. An agent reads no skill from its own tree and has no way to the vault |
| "and those of the step it repairs (§7.1)" | **by the step whose output the repair revises** (`task_plan.revised_task_type`, the repair tables read the other way), from the skillset the repair's own agent supplies. A dev repair is handed the developer's skills whether a suite or an operation failed |
| "Budget … counts the skills and resources a task loads before optional lessons are given space" | **the skills are an envelope input, handed before memory measures the prompt,** so they are counted with the task's other inputs, and the section's framing is added. Lessons are given what they leave |
| "Precedence in the prompt" | **the section says it,** as the instruction sections do: after the task's requirements, the manifest, the application, the task's instructions and the project's; before the stack's general guidance and before any lesson |

**What changes in §7:**
1. **Skills render in a section of their own in the request, after the project's instructions and before the
   lessons.** §7 placed them "in the stack's section, where `system_prompt_supplement` renders today". §17e's
   finding 1 is the evidence: only `development.develop` has that place, and it is left out there for a
   repository-backed product. The slot is in every template that has the instruction slots (13), so every authoring
   seam shows skills the same way. The order on the page is the order of §7's precedence for the three sections
   that share it. The stack's own text stays where each route renders it, and the section's words put skills
   above it.
2. **Skills are handed only to an authoring seam** (`authoring_seam_of`, the seams memory's sections go to). A
   record that offers skills to any other step raises at that step's dispatch, since no other handler has the slot.
3. **A task handed skills that can't be shown fails.** No renderer, no `SKILL.md` or no name raises. A prompt never
   goes out without the skills its task was handed.
4. **A skill is shown as its name, its `SKILL.md` body and each resource under its path.** Its description isn't
   shown: it is for whoever chooses skills, and §7 has no model choose.
5. **`qa.run_remote_operation` is handed none.** §7.1's table loads `studio-play-scenario` for it. Its handler
   calls no model (SIP-0117 R4.4), so a skill has nowhere to be read. A skill for the operation is handed when a
   handler or a provider has a prompt for it, by the SIP that adds one.
6. **The size preflight counts skills with the Campaign's pin (phase 5).** §7 has it count them "before the first
   cycle". It runs at a Campaign's start, before any cycle or record exists, so what it would count is the
   Campaign's pinned record, which phase 5 builds. A standalone cycle has no size preflight today, for skills as for
   any other input.

**Left as it was, and named for phase 4:** `qa.run_remote_operation`'s handler compares the deployed skillset's
digest with the record's before it requests a tool (phase 2a). A redeploy that edits only a skill moves that
digest, so a paused cycle's operation would then be refused. The tool declarations aren't in the kept copy, and
whether they should be is phase 4's (§8).

**Two existing checks changed:** the repair prompt's golden records one more variable per render, empty for a
repair handed no skill; and the manifest author's input contract (SIP-0103 §5c.1) names the skills input, which its
handler reads through the shared slot. No contract runs as that step.

---

### 17g. A skill may hold its provider's scenario vocabulary (2026-11-11)

**What changed.** One resource name in a skill is read by the framework as data:
`scenario_vocabulary.json` at the skill's root. It is the vocabulary of the scenario reader that the
capability's provider executes (SIP-0117 R5.8): its reader id, its actions and observations with their
arguments, and its contexts.
- **At load.** The skillset loader reads it as a vocabulary and refuses the skillset when it can't, naming
  the file. A capability whose skills hold two is refused, since its provider reads one.
- **In the kept copy.** It is a skill file like any other: kept with the cycle, named by digest in the
  record and checked before it is read (§10). A scenario criterion is validated against the supplier's
  vocabulary, read from the cycle's kept copy (`skillset_content.scenario_vocabulary_for`). So a redeploy
  that edits a vocabulary doesn't change what a cycle already created accepts. Two suppliers of one
  contract with different vocabularies are refused.
- **Not a prompt.** An operation task loads no skill (§17f). The file reaches a prompt only where a skill
  that holds it is loaded for an authoring task: a strategy skillset may load the same shared skill, so
  the author of a scenario reads the vocabulary it is validated against.

**Why a resource and not a spec field.** §4.1 adds a spec field only by a SIP. More to the point, the kept
copy's capability rows aren't named in the record, while its skill files are, by digest. A pointer on a
capability row would be the one part of the vocabulary's path the record doesn't check.

**Evidence.** SIP-0117 R4.6's isolation test allows a platform's name only in the skillset directories, the
development profile's entry, the squad profiles, the adapter directory and the worker root's configuration
section. A survey of the seams for #3044's part 2 found no field on a development profile or a capability
contract that could carry provider data. The skillset is the place R4.6 allows, and its content is the one
part that is kept and digested.

**Who ruled.** The MacBook lane, under the owner's "go with your recommendations" (2026-11-11); the design
is on #3044.


### 17h. Phase 4 in two parts, and part 1 as built: tools checked at creation (2026-11-12)

**What was built.** Every tool a required skillset requests, for a contract the cycle's work requires, is
checked in the create preflight (`capabilities/tool_checks.py`). Each failure is its own finding, and goes
through the existing `PreflightRejectedError` (422 `PREFLIGHT_REJECTED`):

| outcome | code | when |
|---|---|---|
| authorization | `skillset_authorization` | an `agent` tool: never refused. A `sandbox` tool: not one of the sandbox's typed operations (`OperationName.ALL`). A `worker` tool: its provider registers no authority, or a rule of that authority refuses it. The refusal names the tool and the rule |
| availability | `skillset_availability` | an `agent` tool: always available. A `sandbox` tool: the runtime binds no sandbox client. A `worker` tool: no registered worker serves it, or every one that does is offline (`WorkerRegistry.no_worker_for`), or the runtime holds no registry. The refusal names the tool and its location, and says the squad still carries the skillset |

**The authority is a port** (`ports/tool_authority.ToolAuthorityPort`). A provider registers its own at the
composition root, keyed by provider name, and the runtime holds them as `tool_authorities`. **None is
registered yet**, so a worker tool is refused, naming its provider: §8's "carrying a skillset never
authorizes an operation", read strictly. Studio's authority is SIP-0117 R4.6's eligibility rules, which come
with its adapter (#3039).

**Where it reads.** `CreationPorts` gains `tool_authorities`, `worker_registry` and `sandbox_client`, filled
by the create route and by a campaign's launch, so both create a cycle by one path. "The sandbox service is
enabled" (§8) is read as the runtime binding a sandbox client (`sandbox_client.provider` isn't `none`): that
client is what runs a sandbox operation.

**Unchanged:** a cycle whose work requires no tool, which is every existing stack's, is checked for nothing.

**Part 2 as built:** an operation task's tool is read available again as it is dispatched, after its
preconditions (`DispatchedFlowExecutor._require_tool_available`), since a worker can go offline after the
cycle was created. The executor reads the worker registry the factory now requires (`worker_registry`), and
its sandbox client. An unavailable tool ends the run `infrastructure_failed`, with the tool and the
registry's reason as its `termination_reason`, and `failure_classification` set to `WORKER_UNAVAILABLE`
(`cycles/failure_attribution.py`). So the Campaign's relaunch budget (#3045) keys on the classification and
never on the reason's words. A task that runs no operation isn't asked.

**Who ruled.** The MacBook lane, under the owner's "go with your recommendations" (2026-11-11); the design is
on #3036, and the dispatch ending was agreed with the Spark lane.

### 17i. Phase 6 in two parts, and part 1 as built: the recall identity and declared supersession (2026-11-12)

**The recall identity (Q63).** A task's recall stack follows one rule (`lesson_supply.recall_stack`):
- the cycle's `build_profile`, so every cycle that has one recalls exactly as before;
- else, for a source-backed cycle, the development profile its skillset record pinned;
- else `""`, which matches only lessons stored for any stack.

A development-profile name is the vocabulary lesson applicability and project instructions already use. A
source-backed cycle created before skillset records has none pinned, and recalls unscoped rather than
under a guessed profile. Each exposure records which source the stack came from (`stack_source`:
`build_profile`, `development_profile` or `unscoped`) and the rule's version (`identity.rule`, 1). An exposure
from before carries no identity, and reads as it did.

**Declared supersession (Q64).** A skill's `SKILL.md` front matter may name the lesson patterns it
supersedes: `supersedes: [pat_…]`, pattern ids as `memory.lessons.pattern_id_for` writes them.
- **At load.** The skillset's load refuses any other value.
- **At dispatch.** Recall reads the `supersedes` of each skill the task is handed. A lesson whose pattern is
  named isn't eligible for that task, since the skill replaces it. It is omitted with the reason
  `superseded_by_skill:<skillset>/<skill>`, which is its own word, because `superseded` is an older revision
  of the same pattern.
- **When every eligible lesson is superseded,** the disposition is `none_eligible`, with each one named.

**Part 2, placed (#3038):**
- **Flagging** needs the skills a lesson was learned under, which no lesson records. Each exposure will record
  its task's skills by digest. Drafting a revision will record the skills of the dispatches its observations
  came from. Recall will then flag a supplied lesson whose learned-under digest differs from the loaded
  skill's.
- **The promotion review** adds `promoted_from` beside `supersedes`, and a review record the promotion
  carries.

**Who ruled.** The MacBook lane, under the owner's "go with your recommendations" (2026-11-11); the design is
on #3038.

## Appendix A. A paper compatibility matrix

Paper only: it commits nothing for Unity, Minecraft or The Sandbox, and changes no 2.7 scope. It checks one claim: each
platform is declarations (a platform and variant, skillsets specializing the same game contracts, verification modes)
plus a provider behind an adapter, with no branch on the engine's name in orchestration and no new task type. The
Roblox row rests on the spikes; the others rest on public documentation and are unspiked.

| platform / variant | illustrative skillsets | execution provider | modes supported | modes not supported or unknown | basis |
|---|---|---|---|---|---|
| **Roblox** / a local place file in Roblox Studio (`studio-place`) | `luau-dev`: gameplay implementation; `roblox-studio-qa`: unit tests, scenario verification | Lune in the QA container (headless); Roblox Studio and its MCP server on a registered worker (editor, play, capture) | `headless`: Lune, with an instance-tree loader (S2); `editor`: script read-back and sync (S1); `play`: play sessions, input and read-back (S1); `capture`: Studio screenshots (S1) | `build`: a Rojo build isn't proven; `multiplayer`: Studio's multi-client test isn't proven | spikes S1 and S2 (2026-11-08) |
| **Unity** / an editor version (for example a 6.x release) | `unity-csharp-dev`; `unity-test-qa` | the Unity editor in batch mode on a licensed worker | `editor`: EditMode tests; `play`: PlayMode tests, in the editor or on a built player (`-runTests -batchmode -testPlatform`, results as XML) | `build`, `capture` and `multiplayer`: not checked for this draft | Unity Test Framework documentation; unspiked |
| **Minecraft** / a Java Edition server (a Paper plugin, or a Fabric or NeoForge mod), with GeyserMC and Floodgate so Bedrock clients on Xbox, mobile and Windows can join | `minecraft-java-dev`; `minecraft-gametest-qa` | Gradle and a dedicated server, in a container or the sandbox; no editor | `build`: Gradle; `headless`: Fabric Loader JUnit; `play`: the server's GameTest runner, which starts a server, runs the game tests and exits with the result | `editor`: none exists; `capture`: Fabric's client game tests need a client; `multiplayer`, and Bedrock clients through Geyser above all: no automated client is known, and Java-only mods and some mechanics behave differently on Bedrock, so cross-play stays unverified | Fabric's automated-testing documentation and GeyserMC setup guides; unspiked |
| **The Sandbox** / Sandbox Studio (2026; gameplay code in TypeScript, in a local project folder) | `sandbox-ts-dev`; `sandbox-studio-qa` | Sandbox Studio and its MCP server, which runs locally on a configured port while a project is open, on a worker | per its documentation: `build`: rebuild the project and read build errors; `editor`: read and edit the scene; `play`: enter and exit Play mode and read its state; `capture`: screenshots, where enabled | `headless`: no test runner is documented; whether state read in Play mode can carry assertions is unknown; `multiplayer`: not exposed through the MCP server | Sandbox Studio's MCP setup guide; unspiked. **No coverage is claimed until a spike settles the unknowns** |

The Sandbox row means Sandbox Studio. The Sandbox's earlier no-code tool, Game Maker, builds games with visual scripting,
so there's no text source for a squad to edit, and it isn't a target.

**What the matrix shows:**
- **Every row is declarations plus a provider.** A platform and variant, skillsets specializing the same contracts
  (`game.gameplay_implementation`, `game.unit_tests`, `game.scenario_verification`), and a provider behind the Game
  Development Platform's adapter port. None needs a new task type or a branch on the engine's name.
- **The modes carry real weight.** Minecraft has no editor, Unity's multiplayer is unchecked, and The Sandbox's play
  mode may not yield assertions. A profile can require only a mode some skillset declares, so an unsupported mode is
  refused at preflight rather than read as passing.
- **Two providers share a shape.** Roblox Studio and Sandbox Studio are each an editor with a local MCP server, on a
  worker. That's evidence the provider port generalizes, not that their operations match.
- **Outside every row:** publishing, and on The Sandbox any wallet, token, LAND or other on-chain operation.

**Sources (read 2026-11-09):** Sandbox Studio's "Set up and use Sandbox Studio MCP" (studio-docs.sandbox.game); Fabric's
"Automated Testing" documentation (docs.fabricmc.net); GeyserMC setup guides from server hosts, to be checked against
geysermc.org; the Unity Test Framework's "Running tests from the command line" (docs.unity3d.com).
