---
sip_uid: '17942318023754850'
title: Agent Skillsets
status: proposed
author: Jason Ladd
created_at: '2026-11-09T00:00:00Z'
---
# SIP-XXXX: Agent Skillsets

## The work declares the skillsets it requires, the squad's agents declare the skillsets they carry, and cycle preflight compares the two

**Status:** Proposed (2026-11-09), **revision 2:** the owner's outside review applied, and its answers to Q52–Q65 ruled
by the owner the same day ("make the revision and yes they can be rulings"). **Building waits for acceptance:** no
implementation starts until the owner accepts this SIP and the 2.8 plan places it.
**Revision:** 2
**Target:** unplaced. A 2.8 feature and the MacBook lane's input to the 2.8 plan. It creates no exception for 2.7.
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
- **Questions:** Q52–Q65, ruled 2026-11-09 (§13 and the portfolio).

## Delivery ledger (current as of 2026-11-09)

| part | status | where |
|---|---|---|
| Phase 1: declarations and the record, inert: the skillset spec and its validation, the agents' `skillsets` field, the profiles' `requires` field, the explicit base set, the versioned record with canonical hashing (§14) | **unplaced**, deliberately: the 2.8 plan places it, after acceptance | — |
| Phase 2: coverage: the preflight refusals, the plan-gate check on the routed agent, the `plannable` property and the offered set (§6, §9) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 3: skills: loading with repair lineage, the kept copy, dispatch-time budgeting, precedence and digests (§7, §10) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 4: tools: requests within existing authority, and the coverage, authorization and availability outcomes (§8, §9) | **unplaced**, deliberately: the 2.8 plan places it, with the Game Development Platform's worker registry | — |
| Phase 5: the Campaign's pin and recorded transitions (§10) | **unplaced**, deliberately: the 2.8 plan places it | — |
| Phase 6: lessons: the recall identity, supplied, omitted and flagged records, supersession, and the promotion review (§10a) | **unplaced**, deliberately: the 2.8 plan places it | — |

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
4. **Capabilities stay central, and the base set is explicit.** A skillset serves `TaskType` members and never defines
   one. Registering a handler enables nothing; the planner may use the base set plus what the required skillsets
   serve.
5. **The binding is recorded and held.** Each cycle records the requirements, the agents that satisfied them, what
   they supplied and the content they loaded, and keeps that content for repair, retry and resume. A Campaign holds
   it until a recorded transition.

This is coverage: it says a squad declares what the work needs. Whether an agent is qualified, and whether the work
it delivers is right, stay separate evidence. For every existing stack the work requires nothing beyond the base set,
so its cycles run exactly as they do today. Roblox is the first stack with requirements: a Studio verification
skillset for QA and a Luau skillset for development.

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
| **capability** | what the planner may assign | a task type, with its handler, the roles that serve it, its expected artifacts and its correction mapping | the planner can assign it |
| **skill** | how the model performs a procedure | content loaded into the agent's context for the work; nothing today (removed with #401) | the model loads it to do the work |
| **tool** | what executes | an operation behind a port and its adapter | it's invoked with arguments and returns a result |

**How they're put together:**
- **A squad profile** is an assembly of agents (identity). Each agent may declare the skillsets it carries.
- **A skillset** binds the other three for a role: the capabilities it serves, the skills loaded for each, and the
  tools each may request. It's a spec, versioned and digested (§4).
- **The stack** is the technology the product is built in. Its development profile declares the skillsets the work
  requires, for each responsibility.
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

(Illustrative: the Game Development Platform SIP's revision 4 settles Roblox's content.)

| field | what it holds | rule |
|---|---|---|
| `id`, `version` | the spec's identity | any change to the spec or its skills increments `version`; the digest covers both |
| `description` | one line | shown in records and, later, in a pack's listing |
| `roles` | the roles that may carry it | an agent whose roles it doesn't list can't declare it |
| `capabilities[].task_type` | a capability it serves | a `TaskType` member; a skillset never defines one, manufactures a handler or widens the base set (§6) |
| `capabilities[].skills` | the skills loaded for that capability's tasks and their repairs (§7.1) | each names a directory under `skills/` holding a `SKILL.md` |
| `capabilities[].tools` | the tools that capability's handler may request: `id` and `location` | a request within existing authority, never a grant (§8) |

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

In 2.x the tree holds skillsets under the prompts seam, `src/squadops/prompts/skillsets/<id>/` (Q61): a skill's text
is prompt content, and prompt content belongs to PromptService (#448). The spec beside it is data: validated,
preflighted and shown without running anything, which is Capability-Backed Agents' rule for a pack's declarations
("code for execution, data for contract", §21). Runtime resolution, handlers and adapters stay in their own seams.

### 4.3 Distributed in a capability pack, later

A capability pack (Capability-Backed Agents §7, 3.x) carries skillset directories unchanged, with what packaging adds:
discovery, installation, the pack's version and its compatibility range, and execution providers. The spec's
`api_version` lets a later format be told apart. A pack expands where skillsets come from; the coverage check of §9
applies to them as it does to the tree's.

## 5. Requirements and supply

### 5.1 The work declares what it requires, on its development profile (Q52)

A development profile gains `requires`: for each responsibility (a role), the skillsets the work needs, each with an
optional version constraint.

```yaml
requires:
  qa:  [{skillset: roblox-studio-qa, version: ">=1"}]
  dev: [{skillset: luau-dev}]
```

Empty means the work requires nothing beyond the base set. Every existing profile takes the empty value. A version
constraint is an exact version or a minimum. Compatibility is decided by these declared values alone, never by a
model's judgement. The profile's fingerprint covers `requires`.

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

## 6. Capabilities: the base set and the planner's vocabulary (§27a)

- **Capabilities stay central.** Each is a `TaskType` member with its handler, the roles that serve it, its expected
  artifacts and its correction mapping (#559: constants at the core). Nothing a skillset declares reaches the handler
  registry (Q23's rule for packs).
- **Registration isn't enablement.** The base set is explicit and versioned, `base@1`: today's three plannable types
  (`development.develop`, `qa.test`, `builder.assemble`, under today's builder rule) and every step the fixed step
  tables dispatch. Registering a new handler, such as `qa.run_remote_operation`'s, adds nothing to it.
- **Planning reads a property.** `TaskType` gains `plannable`. `_KNOWN_BUILD_TASK_TYPES` becomes derived from the base
  set.
- **The offered set** is the base set's plannable types plus the plannable capabilities the cycle's required
  skillsets serve, each supplied by the agent its responsibility routes to. A skillset an agent carries but the work
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
| **declaration** | a skillset is unknown, an agent declares one its roles don't allow, or two required skillsets add to one capability | names the skillset, the agent or the capability |
| **authorization** | a required skillset requests a tool its operation's authority doesn't allow | names the tool and the rule |
| **availability** | a required tool has no available provider: a worker offline, the sandbox disabled | names the tool and the location; the squad still carries the skillset |

**At the plan gate,** where the plan first exists: every task's type is in the base set or served by a required
skillset that the task's routed agent supplies. A plan that fails is refused at the gate with the reason, and the cost
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
| **skillset** | a spec binding capabilities, the skills loaded for them and the tools they may request, for a role; one directory, versioned and digested; what a capability pack carries |
| **requirement** | a skillset, with an optional version constraint, that a development profile declares a responsibility needs |
| **coverage** | the routed agent for each responsibility carries what the work requires; checked at creation, distinct from qualification and verification |
| **skill** | content an agent loads to do the work, in the `SKILL.md` format (Capability-Backed Agents §21). SIP-0040's governed execution unit was removed with #401 |
| **capability** | a dispatchable unit: a task type, its handler, its roles, its artifacts and its correction mapping. The `squadops.capabilities` package holds exactly these: task contracts and handlers (Q23) |
| **base set** | the capabilities enabled with no requirement: explicit and versioned (`base@1`) |
| **tool** | an operation behind a port, invoked with arguments |
| **stack** | the technology a product is built in; its development profile declares the work's requirements |
| **development profile** | a stack's settings bundle (SIP-0072; one meaning, Q36) |
| **capability pack** | packaging, in 3.x: it carries skillset directories and adds loading and providers (Capability-Backed Agents §7) |
| **stack pack** | packaging, in 3.x: a stack's declaration as a loadable plugin (SIP-0105's intent) |
| **playbook** | what a squad follows: a procedure across agents. Kept for that, and defined by a later SIP |
| **specialty** | retired. The game SIPs' revision 3 used it for what this SIP puts in skillsets |

## 13. Rulings (2026-11-09)

The owner's outside review answered each question, and the owner ruled its answers, with the refinements below, the
same day: "make the revision and yes they can be rulings".

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

**One refinement outside the questions:** a repair loads the skills of the step it revises through the existing
`repairs_revising` lineage (§7.1), so no skillset declares its repair bindings separately.

## 14. Phases, and how each is proved

| phase | what | proved by |
|---|---|---|
| **1. declarations and the record (inert)** | the skillset spec and its validation; the agents' `skillsets` field; the profiles' `requires` field; `base@1`; the versioned record with canonical hashing | every existing cycle's prompts and plans are byte-identical to today's; every existing roster hash is unchanged; a wiring test enters at cycle creation and reads a record holding `base@1` and no requirements |
| **2. coverage** | the preflight outcomes; the plan-gate check on the routed agent; `plannable`; the offered set | with a fixture capability's handler registered for `qa`, an ordinary web cycle isn't offered it; a cycle requiring a skillset its routed agent lacks is refused with §9's reason, and an agent elsewhere carrying it doesn't help; an overlap and a role mismatch are refused |
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
- the worker registry and the remote execution protocol (the Game Development Platform SIP's).

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
requires `roblox-studio-qa` (version 1 or later) for `qa` and `luau-dev` for `dev`. The operator selects the
`game-dev-roblox` squad, in which Eve declares `roblox-studio-qa` and Neo declares `luau-dev`.

| record part | value |
|---|---|
| base set | `base@1` (a repository-backed cycle takes no `build_profile`, so `builder.assemble` isn't offered) |
| requirements | `qa`: `roblox-studio-qa` `>=1`; `dev`: `luau-dev` |
| assignment | `qa` → Eve, `roblox-studio-qa@1` and its digest; `dev` → Neo, `luau-dev@1` and its digest |
| content | the digests of `studio-play-scenario`, `luau-test-loader` and `luau-dev`'s skills, and the kept copy |
| offered to the planner | `development.develop`, `qa.test`, and `qa.run_remote_operation`, which `roblox-studio-qa` serves |

Had the operator selected `full`, where no agent declares a skillset, the Campaign would be refused at creation:
"Squad skillset requirements not met. Selected squad: `full`. Missing: `roblox-studio-qa` for `qa` (agent `eve`),
`luau-dev` for `dev` (agent `neo`)." Had Eve carried the skillset and Studio's worker been offline, the refusal would
be an availability one, naming the worker. §7.1 shows what each step of a failure and its repair loads. A redeploy that
revises a skill leaves the Campaign on its kept copy; moving to the revision is the owner's recorded transition.
