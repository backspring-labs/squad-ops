---
sip_uid: '17883224960388794'
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
- `sips/implemented/SIP-0040-*` — the existing **Capability / Skill / Tool** system (this SIP extends it; "skill" returns at the **knowledge layer only** — §21 — satisfying the Skill-Layer SIP's incarnation-two contract; the removed code-seam grain stays removed)
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
- **Runtime posture (§25a):** Iris is activated by a cycle assignment; Glyph's stewardship is not a cycle and runs in duty/ambient windows whose deliverable is a published design-system version. What a version owes its consumers is open — §25b.
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
   *Related but distinct: where the PACK CONFIGURATION artifact lives is §26h Q15.*
2. Manifest format — YAML/TOML/Python entry points/registry?
3. Plugin discovery — Python packaging, Switchboard, config, or a dedicated registry?
   *Resolved by owner (2026-07-29): **Switchboard is the presumptive substrate** — §21.*
4. Resource indexing — LanceDB, separate vector store, or a knowledge service?
5. Memory + resource promotion authority — Max / The Lab / operator / steward agents?
6. Preflight strictness — which missing-context cases block vs warn?
   *Advanced (2026-08-16): separate from strictness, preflight has a TIMING gap — the
   plan does not exist at cycle-create, so plan-vs-assembly is unchecked until dispatch.
   §27c proposes a second evaluation at the workload gate.*
7. Console scope in v1 vs CLI/doctor only.
8. **SIP-0040 reconciliation** — exact meaning of `Skill.required_capabilities` vs this SIP's Capability-Skill Contract; which direction is canonical? *(Blocks Phase 1.)*
9. **Claude Skills** — resolved (§9): adopt the `SKILL.md` *format* for content packaging, supply our own dispatch. Remaining detail: the loader / progressive-disclosure implementation for local models.
10. Architecture pack — part of this umbrella or a follow-on SIP?
11. Which native capabilities migrate first after the Design pack?
12. Do binding contracts declare required model class/context, or is model fit advisory?
    *Advanced (2026-08-15): **requirements are data, model choice is host resolution** — §26d.
    Buys a preflight check; the override grain in the configuration artifact remains open.*
13. Version pinning — exact capability versions or semver ranges in roster bindings?
    *Advanced (2026-07-29): layered scheme with loud load-time enforcement — §21; the
    roster-binding pinning grain (exact vs range) remains open.*
14. **Design-system version semantics** — when Glyph publishes v1.4, what do projects built
    against v1.3 owe or receive: pinned library, additive-only, or advisory style guide?
    *Raised 2026-08-15 — §25b. Distinct from Q13, which is about CAPABILITY versions; this
    is about the versioned RESOURCE a capability produces. **Blocks the design pack's
    schema.***

## 21. Recorded owner decisions (2026-07-29): taxonomy, pack mechanics, trust scope

Settled in owner discussion during the first FAY measurement window; recorded here so the
implementation SIPs (§17) inherit decisions, not vibes.

### The taxonomy and its razor

Four layers, distinguished by **audience and contract type**, with a razor that keeps each
honest:

- **Identity** — *who is accountable.* Roster-scoped; memory, history, trust, runtime
  state (SIP-0089). Never ships in a pack (§2's rule, unchanged).
- **Capability** — *what the orchestrator can dispatch.* The SquadOps execution
  interface: task type + binding contract + evidence obligations. The **only**
  dispatchable unit. SquadOps-native vocabulary.
- **Skill** — *how the model performs a procedure.* Industry-format (`SKILL.md`,
  progressive disclosure — §9's resolution stands). Loaded into context at execution;
  **never dispatched, never visible to the planner**.
- **Tool** — *what actually executes.* MCP server, CLI, port. Invoked with arguments,
  returns results, permission-scoped.

**The razor:** if the cycle planner can assign it, it's a capability; if the model loads
it to do the work, it's a skill; if it's invoked with arguments, it's a tool; if it has
memory and accountability, it's an identity.

This resolves why incarnation one of the skill layer died (see the Skill-Layer SIP):
"skill" was placed at the wrong layer — a **code seam** between handlers and ports, which
nothing needed. The knowledge-layer skill has a mandatory consumer from day one (context
assembly for capability work), so it cannot die of disuse. The relations: the roster tags
identity↔capability (prerequisite profiles + SIP-0089 assignments); the capability
declares its skills (§9's Capability-Skill Contract); the skill wraps tools (declared
tool requirements + permission scopes).

**Direction for §5's mandated SIP-0040 audit** (this decides the audit's outcome shape,
not its findings): the word "skill" canonically means the knowledge-layer unit above.
SIP-0040's governed execution unit — permission, budget, evidence enforcement around
tool use — is not discarded: it becomes the **tool-mediation machinery behind the SPI's
tool invoker** (§ Packs ship code), and should be renamed during the audit rather than
keeping the word. One word, one layer.

### Switchboard is the substrate

The peer library `backspring-labs/switchboard` (host-owned, deterministic extensibility)
is the presumptive discovery/loading mechanism — the org already runs this pattern in
production via Continuum (SIP-0069 console plugins). One plugin mechanism, multiple
hosts: console plugins, stack packs (see the Stack-Blueprint draft), capability packs.
The blueprint/binding schemas stay host-owned; Switchboard owns loading.

### Packs ship code — against a narrow, versioned SPI

Owner decision: declaration-only packs are insufficient for meaningful capability work
(real orchestration: tool sequencing, domain parsing, evidence generation). Packs
therefore ship **capability handler code**, under three commitments:

1. **A narrow SPI, not host internals.** Pack handlers receive *mediated* services —
   workspace view, skill loader, tool invoker, LLM access, evidence emitter — and return
   artifacts + typed evidence. Hexagonal DI one level up: BaseAgent gets ports; pack
   handlers get the SPI. Mediation is where the taxonomy gets teeth: pack code reaches
   tools only through its declared requirements, giving permission scoping and evidence
   provenance by construction. (Receipts for why internals-coupling is fatal: #643 and
   #642 changed typed-acceptance workspace assembly and the test-result shape in a
   single week; either would have broken every internals-coupled pack.)
2. **Code for execution, data for contract.** Declarations — binding contract, check
   menu, skill manifest, tool requirements, prerequisite profiles — remain data the host
   validates, preflights (SIP-0095), and displays **without executing pack code**.
3. **Layered versioning, enforced loudly.** SPI semver (host-owned, slow); pack version
   (the distribution unit); per-skill versions (content, fast-churning). A pack declares
   `requires_spi`; mismatch is a **load refusal at preflight, never warn-and-continue**
   (#327 is the scar: prompt-manifest drift across all five role agents was masked by
   exactly that pattern). Run records pin `pack@version` — the deploy-hash discipline
   applied to packs, or pack-backed evidence is unauditable.

**Conformance is executable, not documentary:** the host ships a conformance kit a pack
must pass — canned envelopes in; well-formed evidence out; workspace write authorization
respected; degraded-context behavior honored; tools touched ⊆ tools declared. "Verify
the verifier," applied to packs. Graduated on-ramp: a simple capability may remain
declaration-only (executed by the host's default skilled-task handler); the CX/UX pack
ships real handlers; both pass the same kit.

### Verification requirement carried in from the FAY window

A pack declares its **check menu** — the named, executable checks its capabilities'
acceptance criteria may draw from (the measured lesson: free-form and unknowable checks
are a per-roll failure mode; plans reach for wrong tools wherever a named check is
missing). Design-work evidence (rubric-judged checks for critiques/plans) is a **new
check species needing its own design pass** — flagged, not solved here.

### Trust scope

**First-party packs only.** Hostile-code isolation is a **named non-goal, carved out for
the future**: the SPI's mediation constrains the polite path, not a malicious one, and
designing sandboxing before a real second party exists would be speculation. The carve-out
means: nothing in the SPI, versioning, or conformance design may *assume* trust in a way
that forecloses adding isolation later (e.g., conformance runs must not require the pack
to be already-loaded into a privileged host).

## 22. Product Decisions

1. Capability packs are plugin-backed extensions. 2. Packs do not own named agents. 3. Binding contracts are required (agent-agnostic ≠ prerequisite-free). 4. Roster bindings are explicit (install ≠ authority) — **install materializes a configuration STUB, never a binding (§26a)**. 5. Assignments activate capabilities. 6. Working-set assembly is first-class. 7. Memory is scoped and promoted, never raw accumulation. 8. Workspace artifacts are shared squad work-state. 9. The Design pack is the reference. 10. Iris applies; Glyph stewards — **and their default runtime postures differ: Iris is cycle-bound, Glyph is duty-shaped, with a published design-system version as the duty's unit of output (§25a)**. 11. Existing agents adopt plugin capabilities before any rewrite. 12. **Skill-mediated tool use extends SIP-0040; capabilities never touch raw tools directly.** 13. **Pack configuration is one artifact with many editors — file, CLI and console pane all write the same store (§26b).** 14. **A pack declares secrets by NAME; the host resolves them through the existing provider and the pack never holds a value (§26e).** 15. **Configuration verbs are generic over a declared schema; domain actions are capabilities, not CLI commands (§26f).**

## 23. Relationship to Existing SIPs

- **SIP-0040 (Capability/Skill/Tool)** — this SIP *extends* it (§5); the skill layer is not new.
- **SIP-0068 / SIP-0072** — generalizes capability-specific + stack-aware build behavior into pluggable, agent-bindable packs.
- **SIP-0089 / SIP-0090 / SIP-0091** — preserves identity ≠ capability ≠ embodiment ≠ mode; capability activation is not a mode; duty may activate a capability but is not the capability. **A duty-shaped Glyph additionally makes SIP-0091 a dependency rather than a neighbour — see §25e, which argues for pulling it forward on this evidence.**
- **SIP-0095** — capability preflight extends the cycle-create preflight gate.
- **SIP-0070 / SIP-042** — evidence/acceptance and memory build on pulse verification and LanceDB.
- **Verification Evidence Integrity (proposed, targets 1.4)** — the Evidence Ledger's "evidence is not acceptance" boundary (§12) presumes acceptance signals are themselves integrity-checked; skill evidence adopts the same executed vs not-executed honesty (a skill that could not run is recorded as not-executed with a reason, never silently omitted).
- **SIP-0064 (`TaskFlowPolicy`) / Campaign** — capability activation respects run-level flow policy; cross-cycle capability-driven squad augmentation is the 2.0 Campaign story.
- **SIP-0069 + Continuum Runtime Console** — future console visibility into bindings, active capabilities, working sets, evidence, and design workflows.

## 25. Recorded owner decisions (2026-08-15): the steward is duty-shaped, and versioning is the open question

Settled — and one thing corrected — in owner discussion during the SIP-0104 measurement
window. Recorded in the §21 form so the implementation SIPs (§17) inherit decisions rather
than reconstruct them.

### 25a. Iris is cycle-bound; Glyph is duty-shaped. That distinction is architectural, not scheduling.

§8 and §13 already split *applies* from *stewards*, and §14 already states that capability
activation is orthogonal to RuntimeMode. What neither said is the **default posture of each
agent**, which is the thing that decides what has to be built.

- **Iris runs in `cycle`.** It is activated by an assignment, applies the design system to a
  target project, and its output belongs to that cycle. Nothing here needs machinery this
  platform does not have — Iris can be a roster member the way Bob is.
- **Glyph runs largely in `duty`/`ambient`.** Its work is not a cycle and does not decompose
  into one.

**Correction recorded, because the first framing in discussion was wrong.** This section
originally reasoned that "maintain the design system" was an aspiration rather than a duty,
on the grounds that a duty needs an external trigger and self-directed work is a failure
mode. The owner's counter stands: stewardship is a real discipline with real, non-cycle
work — industry research, adding features and capability, incorporating gap feedback from
projects, exploring new design-system surfaces, running usability testing — and a
**time-boxed duty window is its natural container**. The correct requirement is not a
trigger. It is a **unit of output**:

> A Glyph duty window ends with **a published design-system version, or nothing published
> this window.** That is the deliverable and the stopping condition.

This is what makes the duty falsifiable. A window that produces prose churn and no version
has produced nothing, and says so.

### 25b. The open question this forces: what is a design-system *version*, and what does it owe its consumers?

If Glyph publishes v1.4 while three delivered projects were built against v1.3, the platform
must answer what happens. Three coherent answers, and the choice decides what the design
system *is*:

| Model | Mechanic | What it makes the design system |
|---|---|---|
| **Pinned library** | projects pin a version; Iris re-applies only on request; breaking changes allowed | a dependency, with an upgrade cost and a migration story |
| **Additive-only** | new versions may only add; upgrades are always safe | a growing vocabulary, at the cost of never retiring a mistake |
| **Advisory style guide** | latest is canonical; drift in shipped projects is tolerated | documentation, not a contract |

§13's gap workflow — Iris files a gap, Glyph proposes, governance accepts *canonical* or
*project-local* — implies the **pinned-library** reading, since "project-local" only means
something if canonical is a version a project can be behind. **The SIP has never said so**,
and the implementation SIPs cannot proceed without it: it determines whether a version
carries a migration note, whether Iris gains a re-application capability, and whether the
gap report references a version at all.

**Not settled here.** Recorded as the question that blocks the design pack's schema.

### 25c. A pack may ship a *default binding*, never an identity

The owner's direction is that both agents arrive "via an agent plugin with a default
identity." Taken literally that contradicts §2, §13 and Product Decision 2 — *"the pack owns
neither agent"*, *"if packs own identities, the platform stops being reusable."* The
reconciliation, proposed here for review rather than ruled:

A pack publishes capabilities **and may publish a suggested default binding** — a name, a
persona, and the capability set it is expected to hold. The roster remains the sole
authority: it may adopt the default verbatim, rename it, bind the capabilities to an
existing agent, or ignore the suggestion entirely. Installation becomes one step instead of
two without moving authority into the pack.

**The acceptance test, which belongs in §18:** install the design pack and bind
`design-system-application` to an **existing** agent, with no Iris in the roster at all. If
that works, the default identity is a convenience. If it does not, the pack owns the
identity and §2's warning has come true.

### 25d. Usability testing is the one listed duty with no substrate

Research, gap incorporation and surface exploration are all executable against resources.
**Usability testing needs users or a credible proxy, and the platform has neither.** Left
undecided, it becomes an agent producing plausible findings nobody validated — the
false-green shape SIP-0096 and SIP-0104 both exist to prevent, relocated into design.

Decide explicitly, before Glyph ships: in scope with a named proxy, delegated to a human as
a duty output rather than performed, or out of scope and stated as such. Silence is the one
option that produces fabricated evidence.

### 25e. Sequencing consequence: Glyph is the forcing function for SIP-0091

A duty-shaped steward needs durable duty windows. **SIP-0091 (Duty Durability) has zero code
and sits in the capacity pool**, and SIP-0090's Phase 2+ is the embodiment substrate for the
same reason. Nothing has been pushing on either.

Glyph pushes on both harder than anything currently queued: an agent whose entire value is
bounded self-directed windows producing versioned output is a better justification for duty
durability than any item that has been offered for it. That argues for pulling 0091 forward
on Glyph's evidence, rather than treating Glyph as blocked behind it.

**Iris has no such dependency** and can precede Glyph, which also makes it the cheaper first
proof: Iris applying a versioned design system exercises §13's workflow up to the gap report
without needing duty machinery at all.

### 25f. The near-term rung that already exists

The minimal design system is already in flight: PR #906 adds a frozen, scaffold-owned,
element-scoped baseline stylesheet to the `nextjs_ts` skeleton, requiring **zero cooperation
from any agent** — it styles whatever markup a fill author writes. That is this SIP's thesis
at its smallest: the framework owns the deterministic spine, the model fills judgment.

The path from there is incremental and keeps that property at every step: make the stylesheet
a **versioned resource** → let Iris **select** from it → let Glyph **propose changes** to it.
Each rung is testable before the next is built, and the first rung answers §25b empirically
rather than by argument.

## 26. Pack lifecycle, attribution, and configuration (2026-08-15)

§21 settles the substrate — Switchboard loads, packs ship code against a narrow SPI, and
**declarations are data the host validates and displays without executing pack code**. What
it does not settle is how an installed pack becomes a *configured, attributed* one. This
section proposes that mechanism. §21's "code for execution, data for contract" rule is the
constraint every choice below is derived from.

### 26a. Install, configure, and activate are three events

Conflating them is the failure mode: it produces packs that self-bind on install, or
configuration that can only happen mid-run.

| Event | What happens | What must NOT happen |
|---|---|---|
| **Install** | the pack is discoverable; its declarations are readable | nothing is bound; no pack code runs to read a declaration |
| **Configure** | the operator produces a binding artifact — attribution, model, secrets, pack parameters | the pack does not bind itself |
| **Activate** | an assignment binds a capability to an agent for a task/run/duty (§14) | activation is not a RuntimeMode |

**Install materializes a commented configuration stub derived from the pack's declared
schema** — the operator then edits it. This is the same shape as the profile contract that
`bootstrap` materializes and `doctor` validates: deterministic generation from data. It
produces a **stub, never an active binding**, because Product Decision 4 already holds that
install ≠ authority.

### 26b. One artifact, three editors

Direct file editing, a CLI, and a Continuum pane are all wanted. They must be **editors of
one authoritative artifact**, never three write paths into three stores.

Three independent paths is the two-seams-one-fact defect this project keeps paying for —
#856 and #918 are both instances, and both were a second hand-maintained copy of something
already derived. A pack's configuration is exactly the kind of thing that would sprout a
console-side copy.

- the artifact is authoritative and versioned;
- `doctor` validates it, whichever editor wrote it;
- the console pane and the CLI render from the **same declared schema**, so neither can
  offer a field the other lacks.

### 26c. Attribution: adopt, mint, or ignore — stated, never inferred

The three cases an importer needs, all expressible in the configuration artifact:

1. **Adopt** — bind pack capabilities to an **existing** agent (Neo gains
   `architecture-review`). §8's hybrid agents; the migration bridge.
2. **Mint** — instantiate the pack's suggested default binding (§25c) as a **new roster
   member named by the importer**. The pack proposes `Iris`; the importer may name it
   anything, or nothing.
3. **Ignore** — installed, nothing bound; capabilities remain available for assignment-time
   activation only.

The roster stays the sole authority in all three (§8). The pack contributes a *suggestion*
and a capability set; the artifact records what the operator decided.

### 26d. Model: the pack declares requirements, the host resolves

A pack naming a concrete model is portability poison — it is a deploy-specific fact written
into a distribution unit. **Packs declare capability requirements as data** (context window,
tool-calling, structured output, vision); the host resolves them against pulled models; the
operator may override in the configuration artifact.

This resolves **open question 12** toward *requirements are data, model choice is host
resolution*, and it buys preflight: `doctor` can report "this pack requires vision, no
pulled model provides it" at configure time rather than mid-cycle (SIP-0095's gate,
extended).

### 26e. Secrets: declared by name, resolved by the host, never held by the pack

**A tool URL is configuration. A key is not.** The platform already owns secret resolution
behind `SecretProvider` (env / file / docker_secret).

- the pack declares `requires_secrets: [figma_token]` — **names and purposes, never values**;
- the operator binds each name to an entry in an existing provider;
- the pack reaches the tool only through the mediated invoker (§21), never the raw value.

If configuration artifacts hold key material, the platform has minted a second secrets path
beside the one that exists, and §21's permission scoping degrades from structural to
advisory. This is the ownership-before-extension rule at its most consequential.

### 26f. Verbs: generic over a declared schema; domain work is a capability

The natural objection is that a pack needs domain-specific verbs and the host cannot
possibly genericize them. The resolution is that "verb" is covering two different things.

**Configuration is generic; the parameters are domain-specific.** The host never needs to
know what `brand.primary_hex` *means* — only its type, constraints, and whether it is
secret, which the declared schema supplies. `--set brand.primary_hex=#1c1e21` is
domain-specific data through a generic verb.

*This project already runs that pattern.* `CHECK_SPECS` declares `required_params`,
`optional_params` and `param_types` per check, and plan validation rejects a malformed
criterion without any semantic knowledge of what `name_prefix` does — the same generic
validation over per-entry declared schemas, one layer down. (Exercised 2026-08-15: the
authoring-example guard validates every shipped example's parameters against its spec
across checks it knows nothing about.)

**Domain actions are not CLI verbs — they are capabilities.** "Sync tokens from Figma", "run
a contrast audit", "regenerate component exemplars" are real operations, and the capability
is their container: mediated SPI, typed evidence, permission scoping, evidence-ledger entry.
A CLI verb gets none of that. So the host does not need to genericize domain verbs; domain
work has a better home than the CLI.

**The genuine edge case is interactive, one-time operator setup** — authorizing with a
vendor, pasting a key fetched from a dashboard. Neither configuration-by-flag nor a squad
capability (no cycle, no artifacts, needs a human). Handle it with a **declarative setup
form**: the pack declares the fields, which are secret, their validation, and where to
obtain each; the host renders it as CLI prompts or a console form from the same declaration.
No pack code executes.

```yaml
setup:
  - key: figma.file_key
    prompt: "Figma file key"
    validate: "^[A-Za-z0-9]{22}$"
  - key: figma_token
    secret: true
    obtain_at: "https://figma.com/developers/api#access-tokens"
```

A true browser OAuth exchange does need pack code; it should run as a **declared setup
handler against the SPI**, not as a free-form CLI command. The line is not "may pack code
run" — §21 already says it may. It is **"may pack code run before the host has validated
anything, at CLI-parse time, in the operator's shell"**, and the answer to that is no.

The resulting host surface, uniform across every pack: `packs show` (schema + current
values, secrets masked), `packs configure --set`, `packs setup` (the declared form),
`packs doctor` (completeness + resolvability).

### 26g. What this costs that does not exist yet

Stated so the estimate is not discovered later:

- **A console write path.** The console is read-mostly; a configuration pane needs
  console → config-store writes with the same validation the CLI applies. This is the
  largest single item here and the one that can be deferred without blocking the rest.
- **A configuration schema in the pack manifest**, plus its validator — small, and shaped
  exactly like `CHECK_SPECS`.
- **Doctor extension** for pack configuration completeness — the category mechanism exists.
- **Secret-name binding** in the artifact and its resolution at activation — small, because
  the provider layer exists.

The file-editing mode plus generated CLI plus doctor validation is usable on day one; the
console pane is an addition, not a prerequisite.

### 26h. Open questions this section raises

15. **Where does the configuration artifact live** — repo-tracked config, the config
    directory, or DB-backed? Repo-tracked makes it reviewable and diffable and is the
    presumptive answer; DB-backed is what a console write path would most naturally reach.
    Whichever is chosen must be the *only* store (§26b).
16. **Is the pack's suggested default binding versioned with the pack?** If a pack ships
    `Iris` at v1 and renames its capability set at v2, an importer who minted `Iris` needs
    to know whether their roster entry is stale — the same consumer/producer versioning
    question §25b asks about design-system resources, one level up.

## 27. Assembly: what must stay stable, and when it is checked (2026-08-16)

Narrow addition. §8 already establishes the three capability sources, §9 the skill/tool
hierarchy and the SKILL.md decision, §16 the deterministic preflight. This section adds
only what those leave open: **why the verb set cannot be dynamic, what selects an
assembly, and when the check happens.**

### 27a. A role's verb set is stable, because plan validity must be decidable offline

The planner composes **task types**. If a role's verb set varies per cycle, then whether
a plan is well-formed depends on runtime assembly — and plan validation stops being a
property of the plan.

That property is load-bearing and already paying for itself. Window roll 4
(`cyc_92c44f8704ab`) was system-rejected at the framing gate by `validate_criteria_scope`
before any implementation ran; it cost a re-plan rather than a cycle. The same holds for
`test_authoring_examples_pass_the_gate`, which decides in milliseconds offline what would
otherwise be a framing rejection in production. Both depend on a fixed vocabulary.

So: **`native` capabilities (§8) define the planner's vocabulary and are image-shaped.**
`plugin` and `assignment` sources may extend what an agent can do, but a task type
reachable only through them must be **declared at plan time**, never discovered at
dispatch. An assignment activates a binding; it must not introduce a verb the plan
validator did not know existed.

### 27b. Assembly is selected from declared configuration, never inferred from the objective

The stack is declared at creation (`build_profile`, `dev_capability`) and is mechanical.
The objective is LLM-parsed prose that does not exist until framing has run.

Selecting a squad's abilities from a parsed objective would put nondeterminism upstream
of everything: two cycles with identical inputs could receive different agents, and no
comparison between them would mean anything. It is the same class as branching on string
identity, which the codebase already forbids in orchestration.

**Rule: assembly is a pure function of declared configuration.** Inference may inform a
human's choice of profile; it may not select the assembly itself.

### 27c. Preflight needs a second evaluation, at the workload gate

§16's preflight extends **SIP-0095 Cycle-Create Preflight**. At cycle-create, the
implementation plan **does not exist yet** — it is authored during framing.

So a plan naming a task type that no bound capability serves passes cycle-create cleanly
and fails at **dispatch**: after framing, after the gate, deep into a cycle. That is the
most expensive place to discover it, and it is precisely the failure shape §16 exists to
prevent. The model-availability preflight (#224) has the same shape — it guards the
roster, not the plan.

**Add a gate-time assertion:** every task type in the merged plan is servable by this
cycle's assembly, and every capability those tasks require is bound and valid. Evaluated
at the workload gate, where the plan first exists and the cost of being wrong is a
re-plan.

### 27d. The bound assembly belongs in the cycle's snapshot

Cycles already record `squad_profile_snapshot_ref` — a content hash of the roster as
resolved. Extend that snapshot to cover the **bound capability, skill and tool set with
versions**.

With it, late binding costs nothing in attributability: any run can be replayed against
exactly what it had. Without it, "which capabilities did this agent actually have" becomes
unanswerable weeks later — the position the 2026-08-15 emission-capture investigation was
in for a much smaller question, at a cost of one measurement window.

### 27e. Tools may bind late; capabilities may not

A tool is an effect with a bounded, visible failure mode: the call succeeds or it does
not. A capability is a promise the planner has already composed against.

So tools may be discovered and bound late, **provided a task that requires one declares
it** — which is what lets preflight check reachability instead of a task discovering an
unreachable Figma server halfway through.

### 27f. Campaigns pin assembly at the campaign boundary

A campaign that re-resolves assembly between cycles can drift mid-flight, and no
regression inside it could be attributed to the work rather than the drift. One
composition hash per campaign; changing it is a deliberate act that starts a new
attribution epoch.

Same discipline as holding rebuild scope to one named change inside a measurement window,
for the same reason.

## 24. References

- `src/squadops/agents/skills/` — existing `Skill` / `SkillRegistry` / `ExecutionEvidence` (SIP-0040).
- `sips/implemented/SIP-0089-Agent-Runtime-State.md`, `sips/accepted/SIP-0090-*`, `sips/accepted/SIP-0091-*`, `sips/accepted/SIP-0095-Cycle-Create-Preflight.md`.
- `sips/implemented/SIP-0068-*`, `sips/implemented/SIP-0072-Stack-Aware-Development-Capabilities.md`, `sips/implemented/SIP-0070-*`.
- `docs/plans/roadmap-runtime-maturity-to-2-0.md` — 2.0 sequencing, lane model, Campaign.
- Continuum Runtime Console SIP (`sips/proposed/SIP-Continuum-Runtime-Console.md`) — worked design-gap example (§13).
