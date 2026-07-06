---
title: Capability-Backed Agents (Capability Packs, Working Sets, Skill-Mediated Tool Use)
status: proposed
author: Jason Ladd
created_at: '2026-07-01'
---

# SIP-XXXX: Capability-Backed Agents

**Status:** Proposed (2.0 umbrella / architecture target)
**Authors:** Jason Ladd (Backspring Labs / SquadOps)
**Created:** 2026-07-01
**Targets:** v2.0
**Kind:** Umbrella SIP — a design commitment that splits into implementation SIPs (§17)
**Depends on / builds on:**
- `sips/implemented/SIP-0040-*` — the existing **Capability / Skill / Tool** system (this SIP extends it; it does **not** reintroduce "skill")
- `sips/implemented/SIP-0068-Enhanced-Agent-Build-Capabilities.md`, `sips/implemented/SIP-0072-Stack-Aware-Development-Capabilities.md` — capability/handler direction this generalizes
- `sips/implemented/SIP-0089-Agent-Runtime-State.md` — RuntimeMode / Assignment / FocusLease / RuntimeActivity (preserved; capability activation is **not** a fourth mode)
- `sips/accepted/SIP-0090-Agent-Embodiment-Substrate.md`, `sips/accepted/SIP-0091-Duty-Durability-via-Temporal.md` — same identity-vs-capability separation
- `sips/accepted/SIP-0095-Cycle-Create-Preflight.md` — deterministic satisfiability gate this reuses for capability preflight
- `sips/implemented/SIP-0070-*` (pulse/verification), `SIP-042` (LanceDB memory), `SIP-0064` (`TaskFlowPolicy`), `SIP-0069` + Continuum Runtime Console SIP (console surfaces)
**Related roadmap:** `docs/plans/roadmap-runtime-maturity-to-2-0.md` (1.x execution maturity → 2.0 agent-expertise maturity; **Campaign** is where capability-driven squad augmentation lands)

---

## 1. Summary

This SIP moves SquadOps agents from **prompt-defined role personas** to **capability-backed specialists** that operate from explicit, inspectable, reusable, and testable capability packs — with real tool use, scoped memory, prepared working sets, and inspectable evidence.

The core architectural principle:

> **Agents are identities. Plugins publish capabilities and binding contracts. Rosters bind agents to capabilities. Assignments activate those bindings. Working sets supply context. Capabilities activate skills. Skills operate tools through ports/adapters and produce evidence. Memory promotion captures durable lessons.**

The immediate forcing function is a design capability, with **Iris** (applies design systems, produces UX plans/critiques/acceptance criteria, files gap reports) and **Glyph** (stewards design systems, evaluates gaps, proposes reusable changes) as the reference roster expression. But the SIP deliberately does **not** bake Iris or Glyph into the capability pack — that would invert the architecture.

This is a **2.0 umbrella**: it commits the design and splits into implementation SIPs (§17). It builds on, and must reconcile with, the **Capability / Skill / Tool system SquadOps already ships** (SIP-0040 — see §5).

## 2. Problem Statement

- **Expertise is too prompt-bound.** An agent's apparent expertise lives in its role prompt and per-task handler behavior — a role *frame*, not durable, inspectable, project-specific subject-matter expertise (curated references, playbooks, templates, rubrics, memory scopes, handoff protocols, provenance).
- **RAG alone is insufficient.** Retrieval answers "what text might be relevant?" SquadOps needs "which authoritative resources, memories, active artifacts, task context, templates, and rubrics should this agent have before acting in this role, on this assignment, under this capability?" That is **working-set assembly**, of which retrieval is one mechanism.
- **Memory can become hidden global state.** Unscoped memory silently changing behavior is a hidden dependency (stale lessons, cross-project leakage, failure-run poisoning). Memory needs scope, provenance, promotion, and disclosure.
- **Tool use is barely modeled.** SquadOps has a `Skill` primitive (SIP-0040) but almost no skills wrap **real external tools** with governed permission, approval, budget, and evidence. 2.0 agents are meant to do real work with real tools; that boundary must be solidified.
- **Capabilities aren't yet reusable platform extensions.** A design capability should not be hardcoded into Iris, nor an architecture capability into Neo. Capabilities should be installable, inspectable, versioned, and bound to different rosters.
- **Identity and capability are being conflated.** Neo (identity) ≠ architecture-review (capability). Iris (identity) ≠ design-system-application (capability). If packs own identities, the platform stops being reusable.

## 3. Design Intent

Evolve the agent definition from:

> role prompt + model + handler

to:

> agent identity + role charter + bound capabilities + scoped memory + tool permissions + working set + artifact responsibilities + evaluation rubric

…without a disruptive rewrite of existing agents. The reference implementation is a first-party **Design Capability Pack** proving the extension model against real subject-matter work, with design resource modules broader than any one product (ops-console, fintech-retail, e-tailer, brand, labs-DX).

## 4. Non-Goals

This SIP does **not**: rewrite all agents; remove role prompts; force all capabilities into plugins immediately; make Iris/Glyph active in every squad profile; bake any named agent into a pack; replace the handler registry, cycle/task model, or SIP-0089 primitives; make RAG the only knowledge mechanism; introduce fine-tuning; build a third-party marketplace; require Figma/Storybook/tokens in v1; make memory automatically authoritative; let plugins expand agent authority without roster/runtime approval; or make Continuum the universal design system.

## 5. Relationship to the Existing Skill / Capability System (SIP-0040) — read this first

SquadOps **already implements a Capability / Skill / Tool triad** (SIP-0040, on the SIP-0.8.8 Agent Foundation):

- `src/squadops/agents/skills/` — a `Skill` ABC ("the fundamental units of agent work"), `SkillRegistry` (with `get_skills_by_capability` and **evidence enforcement**), `SkillContext`, `SkillContractViolation`, per-role skill packages; `create_skill_registry()` is exported at the top-level package API.
- `Skill` already carries `required_capabilities` and emits `ExecutionEvidence`.

**Therefore this SIP extends SIP-0040; it must not introduce a parallel "skill" concept.** Two consequences bind the implementation:

1. **"skill" and "capability" are already taken words.** SquadOps `Skill` = the governed execution unit. This SIP's **Capability** = a domain-level pluggable ability. SIP-0040 also uses "capability" (as something skills are grouped by / require, via `get_skills_by_capability` / `Skill.required_capabilities`). The implementation SIP **must begin with a code-level audit of SIP-0040's Capability/Skill/Tool semantics** and reconcile the two senses of "capability" and the direction of the Capability↔Skill relationship (SIP-0040's `required_capabilities` vs this SIP's Capability-Skill Contract) rather than assert a new model on top.
2. **The genuinely new work is real tool-wrapping, not inventing skills.** Existing skills are largely internal work units; almost none wrap real external tools with permission/approval/budget/evidence. The 2.0 skill effort = **give the existing skill layer real tool adapters (via ports) + the governance in §9**, plus the pack/binding/working-set/memory/workspace/evidence platform around it.

## 6. Conceptual Model

**Core sentence:** *Plugins publish capabilities and binding contracts. Rosters bind agents to capabilities. Assignments activate bindings. Working sets supply context. Capabilities activate skills; skills operate tools via ports/adapters and produce evidence. Memory promotion captures durable lessons.*

| Concept | Owns | Does not own |
|---|---|---|
| Agent identity | name, role charter, model config, runtime state, memory scopes, permissions | reusable domain capability definitions |
| Capability Pack Plugin | capability defs, resources, templates, rubrics, binding contracts | named agent identities |
| Capability Binding Contract | prerequisites for an agent to use a capability | the final binding decision |
| Capability-Skill Contract | which skills a capability may/​may-not use | how a tool is used safely (that's the Skill) |
| Agent Roster Binding | which named agent may use which capability | runtime activation for a specific task |
| Assignment | which agent/capability is needed for a duty/task/run/cycle | capability definition |
| Working Set | assembled context (incl. authorized skill surface) for one execution | permanent memory authority |
| Skill (SIP-0040) | governed, evidence-producing use of a tool | domain-level outcome |
| Tool | instrument/API/service via ports/adapters | intent or policy |
| Memory Record | durable learned context with provenance and scope | authoritative source docs |
| Squad Artifact Workspace | active collaborative artifacts and handoffs | model weights / hidden prompt state; RuntimeActivity |
| Evidence Ledger | what context/skills were used and why | acceptance itself |

## 7. Capability Pack Plugins

A **Capability Pack Plugin** is a versioned, installable extension that publishes reusable capability modules — not a persona, prompt, or folder of docs.

**Manifest (minimum):** plugin id, name, version, owner; capability modules; resource modules; binding contracts; **capability-skill contracts**; artifact types; memory schemas; handoff contracts; required/optional tools; declared side effects; auth scopes; observability events; contract tests; security notes; compatibility (min SquadOps version, feature flags).

**Capability module** — defines a kind of work (e.g. `design-system-application`, `ux-review`, `component-gap-analysis`, `design-system-stewardship`, `architecture-review`, `adr-proposal`, `qa-acceptance-review`).

**Capability Binding Contract** — what kind of agent can use the capability safely: required agent traits, recommended model profile, required/optional resources, readable/writable memory scopes, workspace permissions, input/output artifacts, handoff contracts, **the capability-skill contract (§9)**, risk constraints, evaluation rubric, degraded-context behavior. It **must not name a required agent identity** ("requires an agent that can apply a design system", never "requires Iris"). Packs may define reusable **prerequisite profiles** (e.g. `product-experience-designer`, `design-system-steward`, `technical-architect`, `qa-reviewer`) that rosters map agents onto.

**Installation ≠ authority.** A capability is usable only when: plugin installed+enabled → capability published → roster binds it to an agent → binding satisfies the contract (or records an explicit override) → an assignment activates it → runtime grants the needed resource/skill/tool/memory/workspace permissions.

## 8. Agent Roster Capability Bindings

The **roster** is the authority for named-agent bindings. It distinguishes three capability sources — **native** (built into the existing agent/handler), **plugin** (published by an installed pack), **assignment** (activated for a specific task/run/cycle/duty) — which is what enables incremental migration.

**Hybrid agents** adopt plugin capabilities without a rewrite: Neo keeps native development behavior while adopting `architecture-review`/`adr-proposal`/`bounded-context-analysis`; Eve adopts `qa-acceptance-review`/`accessibility-review`; Max adopts `capability-binding-review`/`memory-promotion-review`. This is the migration bridge.

**Binding validation** yields visible, conservative outcomes: `valid`, `valid_with_warnings`, `invalid`, `override_required`, `unverifiable`. Missing **required** context never silently degrades. Reference bindings: Iris → `design-system-application`/`ux-review`/`component-gap-analysis`/`design-acceptance-authoring`; Glyph → `design-system-stewardship`/`design-system-change-proposal`/`component-pattern-governance`. The pack owns neither agent.

## 9. Skill-Mediated Tool Use (extends SIP-0040)

**Hierarchy:** *Agents bind to capabilities. Capabilities activate skills. Skills operate tools. Tools are exposed through ports/adapters.* This makes tool use safe, repeatable, inspectable, and governable — and it slots onto the hexagonal architecture: a **skill is a governed port operation with a contract**.

- **Tool** — the instrument (GitHub, Figma, Storybook, browser, filesystem, shell, artifact/resource/memory stores). Exposed only via ports/adapters. Tools expose actions; they carry no intent.
- **Skill** — the approved, evidence-producing operation over a tool (`read_resource_module`, `write_workspace_artifact`, `search_codebase`, `run_tests`, `open_pull_request`, …). A **Skill Contract** declares tool used, input/output contracts, permission requirements, side-effect class, failure behavior, evidence required, allowed scopes, budget policy, approval requirements. **This is the SIP-0040 `Skill`, given real tool adapters + this governance.**
- **Capability-Skill Contract** — per capability: `required_skills`, `optional_skills`, `forbidden_skills`, `skill_scope_overrides`, `approval_required_for`, `degraded_behavior`, `evidence_requirements`, `budget_policy`. (Reconcile with SIP-0040's existing `get_skills_by_capability` / `required_capabilities` — see §5.)

Three distinct contracts, deliberately separate: **Binding Contract** = *what agent* may use a capability; **Capability-Skill Contract** = *what skills* the capability may use; **Skill Contract** = *how a tool* is used safely.

**Skill authority is contextual.** A skill runs only when: tool available → skill registered → capability declares it required/optional → agent bound to the capability → assignment activates the capability → roster/runtime grants permission → the working set includes it in the **authorized skill surface**. An agent must never infer tool authority from its prompt.

**Evidence.** Every skill execution emits evidence (skill, tool, agent, capability, assignment ref, safe input/output summary, side effects, resources touched, artifacts read/written, duration, outcome). Capability evidence aggregates skill evidence into the Evidence Ledger (§12).

**`forbidden_skills` and `approval_required_for` are architecture-fitness-checkable** — they turn "Iris must not mutate the canonical design system" from prompt-level trust into a testable guardrail. Reference surfaces: Iris = read resources/memory, read/write workspace, propose candidate memory/gaps; `forbidden_skills: [mutate_canonical_design_system, write_code, execute_shell, deploy_service]`. Bob (`builder-execution`) has a more powerful surface (`write_file`, `run_tests`, `apply_patch`, optional `execute_shell`) with `approval_required_for: [dependency_install, open_pull_request, deploy_service, external_network_call]`.

**Claude Skills — adopt the format, supply our own dispatch (spike complete, 2026-07-01).** The **Agent Skills** convention is now an open standard (agentskills.io, Dec 2025) already adopted by Ollama-based local agents and 20+ platforms: a `SKILL.md` (YAML `name`/`description` + optional `allowed-tools`/`arguments`) + markdown playbook + bundled resources, with three-level progressive disclosure (metadata always, body on trigger, resources on demand). The spike verdict splits cleanly — **the format is portable; the auto-invocation runtime is Claude-specific.** Decision:
- **Adopt the `SKILL.md` format** as the packaging convention for the *content* inside a capability pack (playbooks + resources + optional scripts). It already runs under Ollama, so it satisfies model-independence, and it buys progressive-disclosure efficiency for free.
- **Do not adopt Claude's description-based auto-invocation** — it relies on Claude's reasoning and would break model-independence. SquadOps supplies its own dispatch (capability→skill binding + the working-set authorized skill surface); a local model gets an explicit loader, not "reason over descriptions."
- **The SquadOps capability/skill layer stays the core.** Execution-context binding, lineage/evidence, config, and SIP-style versioning are exactly what Agent Skills *lack*, so they fill the content/packaging slot only: a capability's playbook/resources are authored as SKILL.md-format **skill packs**, the working set loads them via our loader, and `SkillRegistry` + the Evidence Ledger remain the governance/execution/lineage layer.
- **Name collision resolved:** SquadOps **Skill** = governed execution unit (SIP-0040); adopted SKILL.md bundles = **skill packs / playbooks** inside a capability pack.

## 10. Working Set Assembly

A **Working Set** is the prepared, serializable, inspectable context bundle assembled **before** an agent performs an activated capability — the replacement for ad-hoc prompt stuffing.

**Contents:** request/assignment brief; agent identity + constraints; active capability + playbook; resource modules; scoped memory records; workspace artifacts (current/handoffs/drafts/decisions); input artifacts; output template; evaluation rubric; **authorized skill surface** (skills available, tools behind them, permission scope, side-effect class, approval requirements, budget limits, unavailable required/optional skills); evidence-ledger handle.

**Resource authority tiers:** `canonical` (must follow unless superseded), `reference`, `example`, `historical`, `deprecated`, `untrusted`. Prevents stale/exploratory material being treated as current policy; resources carry freshness/deprecation metadata.

**Degraded working sets** never proceed silently: `complete` / `degraded_but_allowed` (missing optional; output must disclose) / `unverifiable` (required source uncheckable; operator warning) / `blocked` (required context missing and contract forbids proceeding — e.g. Iris cannot apply a fintech design system that isn't loaded; block or request another module, never fabricate).

## 11. Knowledge Surfaces & Memory Model

Three surfaces: **Resources** (curated, versioned, authority-tiered reference material — SIPs, ADRs, design systems, API conventions, repo maps); **Memory** (scoped, provenance-backed, promotable learned context; must not override canonical resources); **Artifact Workspace** (§12).

**Memory scopes:** agent, capability, squad, project, operator, assignment, artifact, domain.

**Memory lifecycle:** observed → proposed → reviewed → promoted → superseded → retired → quarantined. **Agents may propose candidate memories; they do not auto-promote from their own outputs.** Candidates carry provenance (source artifact, run/cycle/duty, proposing agent, capability, evidence type, confidence, scope, expiry/review, conflict-check vs canonical resources).

**Two hard rules:** (a) **disclosure** — if memory materially influences an outcome, the Evidence Ledger lists which records were used (memory is never a hidden global variable); (b) **anti-pollution** — failure diagnosis, critique, and model commentary do not automatically become memory; promotion is gated by acceptance evidence, reviewer confidence, reproducibility, operator approval where appropriate, conflict checks, and scope containment. Memory backing builds on SIP-042 (LanceDB).

## 12. Squad Artifact Workspace & Evidence Ledger

A **Squad Artifact Workspace** is a structured, persistent workspace per project/cycle/run/duty/product surface — an organization + interpretation layer **over** the existing artifact vault (it references artifact IDs; it does not duplicate storage, and it does **not** replace RuntimeActivity).

**Artifact types (initial):** `request_brief`, `working_set_manifest`, `design_brief`, `ux_critique`, `design_system_gap_report`, `design_system_change_proposal`, `architecture_review`, `adr_options`, `qa_acceptance_notes`, `handoff_note`, `decision_log`, `evidence_ledger`, `candidate_memory`, `final_deliverable`. Packs may add types. **Handoffs are explicit artifacts** (from, to-agent-or-capability, reason, inputs, requested output, blocking questions, urgency, acceptance expectations).

**Evidence Ledger** — per capability execution, records agent/capability/plugin+version/assignment ref, loaded resources + authority tiers, memory used, workspace artifacts read/written, templates/rubrics applied, skill evidence (§9), missing/degraded context, handoffs, candidate memories, output artifacts. **Evidence is not acceptance** — acceptance stays governed by acceptance checks, review gates, QA evidence (SIP-0070), and operator approval.

## 13. Design Capability Reference Pack (the proof point)

A first-party pack shipped with SquadOps that (a) provides real design capability and (b) demonstrates the extension model without touching core runtime. **It does not create Iris or Glyph** — it publishes design capabilities; the roster binds agents.

- **Capabilities:** `design-system-application`, `ux-review`, `component-gap-analysis`, `design-system-stewardship`, `design-system-change-proposal`, `component-pattern-governance`, `design-acceptance-authoring`.
- **Resource modules (modular, not Continuum-centric):** `design-core`, `ops-console-design` (one module, not *the* system), `fintech-retail-design`, `backspring-etailer-design`, `backspring-brand`, `squadops-labs-dx`. Product context selects modules.
- **Iris → Glyph gap workflow:** assignment activates Iris (`design-system-application`) → working set loads product/brand modules + prior design memory + template/rubric → Iris produces a design brief + acceptance criteria + a `design_system_gap_report` → runtime/Max routes the gap to an agent bound to `design-system-stewardship` (Glyph) → Glyph produces a `design_system_change_proposal` → governance accepts (canonical) / accepts (project-local) / rejects / defers / marks example → accepted changes become resources; durable learning is *proposed* as candidate memory, never silently saved. Iris identifies gaps and proposes; Iris does not mutate canonical design-system resources.
- **Worked gap** (ties to the Continuum Runtime Console SIP): "Add a Duty perspective." Iris finds no reusable visual grammar distinguishing persistent Duty from active Cycle; Glyph proposes badge/chip semantics, health-vs-mode separation, empty/degraded states, and anti-patterns that conflate health and mode.

## 14. Capability Activation Flow & Runtime Orthogonality

**Flow:** resolve assignment → select agent → select capability → validate binding → assemble working set (incl. authorized skill surface) → open evidence-ledger entry → execute capability (activating skills over tools) → write artifacts → create handoffs → propose candidate memory → evaluate (rubric + acceptance/review/operator) → finalize or route.

**Orthogonality (hard):** capability activation is **not** a RuntimeMode. An agent executes a capability *while in* `cycle`/`duty`/`ambient` mode (SIP-0089), and activation must respect Assignment, FocusLease, RuntimeActivity, runtime status, and budget. If a capability needs primary attention it must hold/be granted a compatible FocusLease first. Capability work surfaces **as** RuntimeActivity (referencing the activated capability, assignment, workspace artifacts, evidence entry) — it does not replace it. **Campaign** (roadmap, 1.6 mechanic / 2.0 augmentation) is where a cross-cycle objective may, in 2.0, compose a *missing* capability into the next cycle's squad — this SIP supplies the capability packs that make that augmentation possible.

## 15. Security & Permission Model

Installation grants nothing. Plugins **declare** required/optional tool permissions, memory read + write/proposal scopes, artifact read/write, external side effects, secret + network requirements, and elevated-risk operations. **Roster/runtime is a permission ceiling** — an agent cannot gain more authority from a plugin than the roster allows; a declared-but-unpermitted tool is excluded from the working set or marks the activation degraded/invalid. **Side-effect classes:** `read_only`, `workspace_write`, `memory_proposal`, `memory_write` (governed), `resource_proposal`, `resource_write` (approval-required), `external_action` (explicit tool permission). The Design pack is initially read-only + workspace-write + proposal-oriented; canonical resource writes require governance.

## 16. Validation & Preflight

Before activation, a **deterministic preflight** gate (extending **SIP-0095 Cycle-Create Preflight**) evaluates installed plugins, published capabilities, roster bindings, agent profile, assignment context, and required resource/memory/skill/tool/workspace permissions → `allow` / `warn_and_allow` (disclosed in evidence) / `block` / `unverifiable`. **Block** on: capability not installed, agent not bound, required resource/artifact/permission/memory-scope missing, contract unsatisfied, side effect exceeding roster permission. A CLI/doctor path surfaces installed packs, invalid bindings, missing/deprecated resources, unavailable memory scopes, and version incompatibilities — mirroring the "proactive diagnosis must not drift from runtime enforcement" principle.

## 17. Delivery Plan (→ implementation SIPs)

Umbrella phases; each becomes its own bounded implementation SIP. Per the roadmap lane model, **Macbook builds the whole path (design, schema, pack/plugin/config wiring, mechanics with fakes/`lite`/`smoke`); Spark is the end-of-lane confirmation gate for 27b deliverable quality only.**

1. **Core vocabulary & contracts** — pack/module/binding/capability-skill/resource/working-set/evidence/workspace/candidate-memory as schema+domain models, reconciled with SIP-0040. No behavior change.
2. **Plugin registry & binding validation** — discover packs, list capabilities, validate bindings, expose invalid/warning states, native+plugin sources.
3. **Working-set assembly v1** — assemble context + authorized skill surface, open evidence ledger, disclose degraded context; support existing handlers without rewrites.
4. **Skill-mediated tool use v1** — real tool adapters (ports) + Skill/Capability-Skill contracts + skill evidence, on top of SIP-0040. Adopts the `SKILL.md` format for content packaging with SquadOps-supplied dispatch/evidence as the core (§9).
5. **Squad Artifact Workspace v1** — typed artifacts, handoffs, evidence, candidate memories, per-capability permissions over the artifact vault.
6. **Scoped memory & promotion** — scopes, candidate→promotion lifecycle, disclosure, anti-pollution.
7. **Design Capability Reference Pack** — capabilities, contracts, resource modules, templates/rubrics, Iris→Glyph workflow.
8. **Optional Iris/Glyph roster config** — reference/design-capable profile; existing profiles unchanged.
9. **Neo hybrid adoption** — Architecture Capability Plugin; Neo bound to plugin capabilities while native behavior persists.
10. **CLI/doctor/console observability** — packs, bindings, working-set summary, evidence, candidate-memory + design-change queues (builds on SIP-0069 / Continuum Runtime Console).

## 18. Acceptance Criteria

**Platform model** — SquadOps can represent a pack independently of named agents; a pack publishes ≥1 capability with a binding contract that names prerequisites, not an agent; the roster binds a named agent to a plugin capability; native vs plugin sources are distinguishable; existing hardwired agents run unchanged; **no new persisted/API-visible status vocabulary** is introduced for capability/skill/memory/evidence beyond reconciling SIP-0040.

**Binding & preflight** — bindings to a missing capability or failing required prerequisites are rejected or require explicit override; missing optional resources warn (never silently degrade); results are visible via a diagnostic surface; installation alone grants no authority.

**Working set & skills** — a capability execution receives a working set (incl. authorized skill surface) before output; required missing context blocks or discloses per contract; a skill runs only via the authorized skill surface; a `forbidden_skill` invocation is blocked; every skill execution and every materially-used resource/memory is recorded in the Evidence Ledger.

**Memory** — records are scoped and provenance-backed; agents propose but do not auto-promote; canonical resources outrank memory on conflict; materially-used memory is disclosed.

**Workspace** — typed artifacts read/written by capabilities; handoffs and evidence are explicit artifacts; workspace does not replace RuntimeActivity.

**Design pack** — ships/loads without defining Iris/Glyph as required; publishes binding contracts for application + stewardship; provides modular resource categories beyond Continuum; Iris produces a brief + gap report from a working set; Glyph consumes the gap and produces a change proposal; accepted changes promote into resources via governance; all executions produce evidence.

**Regression** — cycle creation/execution and existing handler resolution are unchanged; existing profiles don't require Iris/Glyph; **RuntimeMode/Assignment/FocusLease/RuntimeActivity stay separate and capability activation is not a hidden fourth mode.**

## 19. Risks & Mitigations

- **Reinventing SIP-0040** → §5 mandates a code-level audit + extension, not a parallel model. *(Top risk.)*
- **Over-engineering the first pack** → ship the Design pack small; Iris/Glyph as the concrete proof; no marketplace features.
- **Prompt bloat returns as "packs"** → separate resources/memory/templates/rubrics/skills; disclose what's loaded; authority tiers; context-budget checks later.
- **Memory pollution** → candidate-only, review-gated, scoped, provenance + conflict checks.
- **Stale resources as authority** → authority tiers, deprecation, freshness, evidence disclosure.
- **Agent/capability confusion** → the principle is explicit; docs show alternate bindings; reference profiles clearly labeled examples.
- **Plugins expand authority unsafely** → declared side effects; roster permission ceiling; runtime validates before activation; external actions need approval.
- **Design-system governance bottleneck (Glyph)** → severity-classified gaps; Iris proceeds with local guidance on non-blocking gaps; only reusable/canonical changes need governance.
- **Continuum overfit** → resource modules are modular; `ops-console-design` is one module; fintech/e-tailer modules included; product context selects.

## 20. Open Questions

1. Storage layout for the workspace — logical projection over the artifact vault, DB-backed, filesystem-like, or hybrid?
2. Manifest format — YAML/TOML/Python entry points/registry?
3. Plugin discovery — Python packaging, Switchboard, config, or a dedicated registry?
4. Resource indexing — LanceDB, separate vector store, or a knowledge service?
5. Memory + resource promotion authority — Max / The Lab / operator / steward agents?
6. Preflight strictness — which missing-context cases block vs warn?
7. Console scope in v1 vs CLI/doctor only.
8. **SIP-0040 reconciliation** — exact meaning of `Skill.required_capabilities` vs this SIP's Capability-Skill Contract; which direction is canonical? *(Blocks Phase 1.)*
9. **Claude Skills** — resolved (§9): adopt the `SKILL.md` *format* for content packaging, supply our own dispatch. Remaining detail: the loader / progressive-disclosure implementation for local models.
10. Architecture pack — part of this umbrella or a follow-on SIP?
11. Which native capabilities migrate first after the Design pack?
12. Do binding contracts declare required model class/context, or is model fit advisory?
13. Version pinning — exact capability versions or semver ranges in roster bindings?

## 21. Product Decisions

1. Capability packs are plugin-backed extensions. 2. Packs do not own named agents. 3. Binding contracts are required (agent-agnostic ≠ prerequisite-free). 4. Roster bindings are explicit (install ≠ authority). 5. Assignments activate capabilities. 6. Working-set assembly is first-class. 7. Memory is scoped and promoted, never raw accumulation. 8. Workspace artifacts are shared squad work-state. 9. The Design pack is the reference. 10. Iris applies; Glyph stewards. 11. Existing agents adopt plugin capabilities before any rewrite. 12. **Skill-mediated tool use extends SIP-0040; capabilities never touch raw tools directly.**

## 22. Relationship to Existing SIPs

- **SIP-0040 (Capability/Skill/Tool)** — this SIP *extends* it (§5); the skill layer is not new.
- **SIP-0068 / SIP-0072** — generalizes capability-specific + stack-aware build behavior into pluggable, agent-bindable packs.
- **SIP-0089 / SIP-0090 / SIP-0091** — preserves identity ≠ capability ≠ embodiment ≠ mode; capability activation is not a mode; duty may activate a capability but is not the capability.
- **SIP-0095** — capability preflight extends the cycle-create preflight gate.
- **SIP-0070 / SIP-042** — evidence/acceptance and memory build on pulse verification and LanceDB.
- **Verification Evidence Integrity (proposed, targets 1.4)** — the Evidence Ledger's "evidence is not acceptance" boundary (§12) presumes acceptance signals are themselves integrity-checked; skill evidence adopts the same executed vs not-executed honesty (a skill that could not run is recorded as not-executed with a reason, never silently omitted).
- **SIP-0064 (`TaskFlowPolicy`) / Campaign** — capability activation respects run-level flow policy; cross-cycle capability-driven squad augmentation is the 2.0 Campaign story.
- **SIP-0069 + Continuum Runtime Console** — future console visibility into bindings, active capabilities, working sets, evidence, and design workflows.

## 23. References

- `src/squadops/agents/skills/` — existing `Skill` / `SkillRegistry` / `ExecutionEvidence` (SIP-0040).
- `sips/implemented/SIP-0089-Agent-Runtime-State.md`, `sips/accepted/SIP-0090-*`, `sips/accepted/SIP-0091-*`, `sips/accepted/SIP-0095-Cycle-Create-Preflight.md`.
- `sips/implemented/SIP-0068-*`, `sips/implemented/SIP-0072-Stack-Aware-Development-Capabilities.md`, `sips/implemented/SIP-0070-*`.
- `docs/plans/roadmap-runtime-maturity-to-2-0.md` — 2.0 sequencing, lane model, Campaign.
- Continuum Runtime Console SIP (`sips/proposed/SIP-Continuum-Runtime-Console.md`) — worked design-gap example (§13).
