---
sip_uid: 01KEM71ECNSHEVZPZDPKGZK6ZV
sip_number: null
title: Layered Prompt System — Deterministic Prompt Assembly for Agent Lifecycle + ACI Task Types
status: proposed
author: Framework Committee
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-10T15:05:29Z'
original_filename: SIP-LAYERED-PROMPTS-0_8_5.md
---
# SIP-LAYERED-PROMPTS-0_8_5 — Version Target 0.8.5  
## Layered Prompt System: Deterministic Prompt Assembly for Agent Lifecycle + ACI Task Types

# 1. Purpose and Intent

This SIP defines a **Layered Prompt System** for SquadOps that assembles prompts deterministically from a small set of **versioned, reusable fragments** aligned to:

- agent identity and operating constraints,
- lifecycle hooks (agent/cycle/pulse/task),
- ACI `task_type` taxonomy,
- recovery and failure handling.

The intent is to:
- reduce drift across agents and projects,
- make agent behavior more deterministic and testable,
- prepare a stable foundation for 0.9.x observability (e.g., Langfuse),
- ensure dynamic run state is carried in **message context**, not prompt text.

# 2. Background

SquadOps is standardizing runtime execution via ACI TaskEnvelope and lifecycle hooks. Without a prompt system, agents tend to accumulate:
- ad-hoc prompt strings,
- inconsistent role behavior,
- duplicated instructions across agents,
- hard-to-debug changes in behavior from minor edits.

Layering prompts provides:
- a stable behavior contract,
- predictable assembly based on lifecycle and task type,
- auditable versions and hashes for later telemetry and RCA.

# 3. Problem Statements

1. Prompt instructions drift across agents and tasks without centralized control.
2. Mixing dynamic execution data into prompt text creates security and determinism issues.
3. Observability systems require stable prompt boundaries to attach meaningful traces.
4. Without a standard assembly pipeline, "prompt changes" are untestable and non-repeatable.

# 4. Scope

## In Scope (0.8.5)
- Prompt fragment taxonomy and folder structure
- Prompt assembly algorithm (PromptAssembler)
- Prompt manifest and versioning strategy
- Integration points in BaseAgent (lifecycle hooks + task execution)
- ACI task_type → prompt layer mapping
- Prompt immutability rules per cycle/task
- Hashing and metadata injection for traceability
- Unit tests for assembly correctness and immutability

## Out of Scope (0.8.5)
- Langfuse integration (0.9.0)
- Prompt A/B testing system
- Dynamic prompt generation from external sources
- Remote prompt registry service

# 5. Core Principles (Normative)

1. **Prompts define behavior, not state.**
2. **Dynamic run data must be passed via message context**, never as dynamic prompt fragments.
3. **Assembly is deterministic** given the same inputs (agent role, hook, task_type, prompt version).
4. **Prompt fragments are versioned and immutable once a cycle starts.**
5. **Avoid verbose English when possible** by using structured task inputs and standardized task types; prompts should be concise and directive.

# 6. Prompt Layer Model

## 6.1 Prompt Layers (Normative)

Prompt is assembled in this order:

1. **Identity Layer**  
   Agent role identity, tone constraints, boundaries, operating principles.

2. **Global Constraints Layer**  
   Non-negotiables: safety, non-leakage of secrets, ACI immutability rules, logging discipline.

3. **Lifecycle Layer**  
   Instructions specific to the current lifecycle hook (agent_start, cycle_start, pulse_start, task_start, task_complete, task_failed).

4. **Task Type Layer**  
   Task-type-specific behavioral instructions (code_generate, test_execute, document_create, etc.).

5. **Recovery Layer (Conditional)**  
   Added only when executing failure analysis or recovery tasks.

6. **Local Overrides Layer (Optional, Strictly Controlled)**  
   Only allowed for explicitly configured projects, and only via static, versioned fragments (no runtime injection).

### Ordering Rule
Earlier layers have higher priority; later layers must not contradict earlier layers.

## 6.2 Prompt Fragment Format

Prompt fragments MUST be plain text or Markdown. Each fragment MUST include a small header block (machine-parseable) at top:

- `fragment_id`
- `version`
- `description`
- `applies_to` (agent roles and/or hooks/task_types)
- `hash` (computed; stored separately in manifest)

Example header (illustrative):
```
fragment_id: lifecycle.task_start
version: 0.8.5
description: Instructions to begin a task deterministically
applies_to: hooks=task_start
```

# 7. Prompt Manifest and Versioning

## 7.1 Manifest (Normative)

A manifest file MUST enumerate all fragments included in a release:

- fragment_id → file path
- fragment version
- SHA256 hash
- applicable roles/hooks/task_types

Recommended location:
- `agents/prompts/manifest.yaml`

## 7.2 Versioning (Normative)

- Prompt system version is pegged to the SquadOps version (e.g., 0.8.5).
- A cycle MUST record:
  - prompt_system_version
  - fragment hashes used
  - assembled_prompt_hash

## 7.3 Immutability Rules (Normative)

- Once `on_cycle_start` begins, fragments used for that cycle MUST NOT change.
- Editing a fragment requires bumping version and regenerating manifest hashes.
- Runtime must detect hash mismatches and fail fast in strict mode.

# 8. PromptAssembler

## 8.1 Responsibilities (Required)

PromptAssembler MUST:
- select the correct fragments for:
  - agent role
  - lifecycle hook
  - task_type
  - recovery mode
- assemble in the defined order
- validate no missing required fragments
- produce:
  - `assembled_prompt_text`
  - `assembled_prompt_hash`
  - `fragment_hashes` (map)

## 8.2 Inputs to Assembly (Normative)

Assembly inputs are **static selectors**, not dynamic content:

- agent_role (Lead, Strategy, Dev, QA, Data, etc.)
- lifecycle_hook (agent_start, cycle_start, pulse_start, task_start, task_complete, task_failed)
- task_type (ACI taxonomy)
- prompt_system_version
- optional project prompt profile (static allowlist)

Dynamic run state (cycle context, task inputs, lineage IDs, prior outputs) is NOT used to select or modify fragments unless explicitly allowed via static configuration.

# 9. Integration Points

## 9.1 BaseAgent Integration (Required)

BaseAgent MUST:
- call PromptAssembler at each lifecycle hook that results in an LLM invocation
- attach prompt metadata to the task context:
  - prompt_system_version
  - assembled_prompt_hash
  - fragment_hashes
- ensure task execution uses assembled prompt + task inputs as message context

## 9.2 Task Type Mapping (Required)

Define a canonical mapping:
- `task_type` → prompt fragment (or fragment group)

Examples (illustrative):
- `code_generate` → `task_types/code_generate.md`
- `test_execute` → `task_types/test_execute.md`
- `document_create` → `task_types/document_create.md`
- `chat` → `task_types/chat.md`
- `failure_analysis` → `recovery/failure_analysis.md`

# 10. Must Not (Normative)

1. No runtime injection of new prompt fragments from task inputs, DB, or external sources.
2. No mixing dynamic execution data into prompt fragment files.
3. No bypassing PromptAssembler by constructing ad-hoc prompts in agents.
4. No mutation of prompt fragments or manifest during a running cycle.
5. No project-specific prompt overrides unless explicitly allowlisted as static fragments.

# 11. Testing Requirements

## 11.1 Unit Tests (Required)
- fragment selection given role/hook/task_type
- deterministic assembly given same selectors
- hash generation correctness
- missing fragment detection fails fast
- immutability enforcement (hash mismatch triggers failure in strict mode)

## 11.2 Integration Tests (Required)
- run a minimal task through an agent and verify:
  - prompt metadata attached
  - assembled_prompt_hash recorded
  - task output produced with correct task_type mapping

# 12. Implementation Plan (0.8.5)

1. Create prompt folder structure and seed fragments:
   - identity/
   - constraints/
   - lifecycle/
   - task_types/
   - recovery/
2. Implement manifest generation script (dev tool) or build step:
   - compute hashes and write manifest.yaml
3. Implement PromptAssembler and integrate into BaseAgent
4. Enforce "no ad-hoc prompts" rule via code review checks and tests
5. Add metadata fields to relevant runtime data structures (cycle/task context)

# 13. Definition of Done

- [ ] Prompt fragments are organized and versioned under `agents/prompts/`
- [ ] manifest.yaml exists with fragment hashes and metadata
- [ ] PromptAssembler assembles prompts deterministically and produces hashes
- [ ] BaseAgent uses PromptAssembler for lifecycle/task LLM invocations
- [ ] Prompt immutability is enforced per cycle (hash mismatch fails fast in strict mode)
- [ ] ACI task_type mapping to prompt fragments is implemented
- [ ] Unit + integration tests cover assembly and immutability

# 14. Appendix — Suggested Folder Structure (Normative)

```
agents/
  prompts/
    manifest.yaml
    identity/
      lead.md
      strategy.md
      dev.md
      qa.md
      data.md
    constraints/
      global_constraints.md
      secrets_nonleak.md
      aci_immutability.md
    lifecycle/
      agent_start.md
      cycle_start.md
      pulse_start.md
      task_start.md
      task_complete.md
      task_failed.md
    task_types/
      code_generate.md
      test_execute.md
      document_create.md
      chat.md
    recovery/
      failure_analysis.md
      retry_strategy.md
      rewind_proposal.md
```

# 15. Prompt Pack Packaging and Migration from Role-Exclusive Prompts (Normative)

This section clarifies how the layered prompt system supports **individual agent container builds** while migrating from the current structure where prompts may be **exclusive under each role**.

## 15.1 Target Packaging Model (Option B — Normative)

Prompt assets SHALL be organized into two tiers:

1) **Shared Prompt Pack**  
   - includes global constraints, lifecycle prompts, common task_type prompts, and recovery prompts.
2) **Role Prompt Pack**  
   - includes only the role-specific identity (and any approved role-specific specializations).

Recommended structure (normative):

```
agents/
  prompts/
    manifest.yaml
    shared/
      constraints/
      lifecycle/
      task_types/
      recovery/
    roles/
      lead/
        identity.md
      strategy/
        identity.md
      dev/
        identity.md
      qa/
        identity.md
      data/
        identity.md
```

The **shared** folder is identical across all agent builds.
Each agent container image MAY include only:
- `agents/prompts/shared/**`
- `agents/prompts/roles/<role>/**`

This keeps per-agent images lean while preserving a single canonical prompt system.

## 15.2 PromptAssembler Search Path (Required)

PromptAssembler MUST support an ordered search path:

1) `agents/prompts/roles/<role>/...` (role-specific)
2) `agents/prompts/shared/...` (shared)

Selection rules:
- If a required fragment exists in both tiers, the **role-specific** fragment wins.
- If a required fragment exists only in shared, shared is used.
- Missing required fragments MUST fail fast in strict mode.

This enables role-only images without duplicating shared fragments.

## 15.3 Manifest Strategy (Normative)

Two acceptable approaches:

A) **Single Manifest (Canonical)**
- `manifest.yaml` includes entries for both shared and all roles.
- Role-only images ship the same manifest but only include their role folder + shared.
- PromptAssembler MUST validate presence for only the fragments required by that role/hook/task_type.

B) **Split Manifests (Optional)**
- `manifest.shared.yaml` for shared pack
- `manifest.role.<role>.yaml` for role pack
- PromptAssembler merges manifests at startup.

0.8.5 preference: **A (Single Manifest)** to reduce moving parts.

## 15.4 Migration Guidance for Cursor (From Role-Exclusive to Shared + Role Packs)

Current state assumption:
- Prompt files exist under per-role directories only (duplicated lifecycle/constraints/task_type prompts across roles).

Migration steps (required):

1) **Identify shared fragments**
   - global constraints
   - lifecycle hook prompts
   - task_type prompts
   - recovery prompts

2) **Move shared fragments to `agents/prompts/shared/`**
   - preserve filenames and fragment_ids where possible to avoid churn
   - update paths in the manifest accordingly

3) **Keep role identity prompts in `agents/prompts/roles/<role>/`**
   - each role MUST have an identity fragment
   - role identity fragment MUST remain role-scoped

4) **Eliminate duplication**
   - remove per-role copies of lifecycle/constraints/task_type prompts
   - only override shared prompts when a role requires a materially different behavior, and document that override

5) **Update PromptAssembler**
   - implement the search path rules in 15.2
   - ensure deterministic assembly remains unchanged

6) **Regenerate manifest hashes**
   - update `manifest.yaml` to reflect new paths and hashes
   - enforce immutability rules per cycle

7) **Update tests**
   - add tests validating:
     - role-only prompt pack can assemble a full prompt
     - shared fragments are used when role fragments are absent
     - role fragments override shared when both exist

## 15.5 Container Build Guidance (Normative)

Agent container builds SHOULD:
- COPY `agents/prompts/shared/**` into the image
- COPY `agents/prompts/roles/<role>/**` into the image
- COPY `agents/prompts/manifest.yaml` into the image

Prompts MUST be mounted/read-only at runtime if using volume mounts for local development.
For production-style runs, embedding prompts in the image is preferred for hermetic builds.
