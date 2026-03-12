---
title: Prompt Registry Integration Using Langfuse
status: accepted
author: Jason Ladd
created_at: '2026-03-11'
target_release: 1.0.1
supersedes: null
extends: SIP-0057
sip_number: 84
updated_at: '2026-03-11T22:47:39.427254Z'
---
# SIP — Prompt Registry Integration Using Langfuse

# 1. Summary

This SIP proposes extending the existing prompt system (SIP-0057) with a Langfuse-backed prompt registry, externalizing governed prompt asset storage and versioning while preserving SquadOps' internal control of runtime assembly, artifact provenance, and execution semantics.

## 1.1 Relationship to SIP-0057

SIP-0057 established the Hexagonal Layered Prompt System that SquadOps uses today. It introduced:

- A `PromptServicePort` with `assemble()` and `get_system_prompt()` methods
- A `PromptAssembler` with 5 deterministic layers (identity → constraints → lifecycle → task_type → recovery)
- SHA256 integrity hashing of assembled system prompts
- Fragment-based composition from filesystem sources

This foundation is sound. This SIP preserves it and extends it with governed external storage.

## 1.2 Two Governed Asset Types

This SIP introduces two distinct governed prompt asset types:

1. **System prompt fragments** — behavioral prompt content composed through SIP-0057's deterministic layered assembly (role identity, constraints, shared guidance, lifecycle behavior, task-family behavior, recovery behavior). Currently stored on the filesystem, retrieved via `PromptServicePort`.

2. **Request templates** — task instruction templates used by handlers to structure requests to the LLM. Currently constructed inline by handler methods across 32 handlers in 3 base class hierarchies (`_CycleTaskHandler`, `_PlanningTaskHandler`, `_RepairTaskHandler`) plus 9 handlers with custom construction.

Both asset types benefit from governed storage, versioning, environment promotion, and provenance tracking. However, they are architecturally distinct and must not be unified into a single assembly model.

## 1.3 What Is NOT a Governed Prompt Asset

**Runtime request payloads** — the dynamic content that handlers inject into request templates at execution time — are explicitly excluded from governed prompt asset management. This includes:

- PRD content
- Prior artifact outputs
- Implementation plans, strategies, and diffs
- Acceptance criteria and failure evidence
- Repository context and file listings
- Time budgets and capability supplements

These are runtime inputs derived from task context, artifacts, and execution state. They are not prompt fragments. They are not request templates. They must not be stored in or governed by the prompt registry.

**Capability supplements** are also runtime concerns. They are contextual additions attached by handlers based on the active capability and execution state. Unless separately promoted into the governed asset model by explicit future design, capability supplements remain handler-owned runtime content.

## 1.4 Scope Summary

| Concern | Governed Asset? | Managed By |
|---|---|---|
| System prompt fragments | Yes | Registry (Langfuse) |
| Request templates | Yes | Registry (Langfuse) |
| Runtime request payloads | No | Handler code at execution time |
| Capability supplements | No | Handler code at execution time |
| Prompt assembly logic | No | SquadOps runtime (`PromptAssembler`) |
| Prompt guard / truncation | No | SquadOps runtime (SIP-0073) |
| Execution semantics | No | SquadOps runtime |

---

# 2. Intent

The intent of this SIP is to establish prompts as first-class governed assets within the SquadOps architecture.

Governed prompt assets — system prompt fragments and request templates — should be treated similarly to source code, configuration, and architectural specifications. They should be:

- versioned
- centrally stored
- independently evolvable
- traceable within system evidence
- insulated behind stable platform interfaces

This change ensures that SquadOps can support long-running cycles, reproducibility, and governance without requiring code deployments for prompt changes and without coupling core runtime behavior directly to Langfuse.

---

# 3. Justification

Several pressures make prompt registry capabilities necessary at this stage of development.

## 3.1 Prompt Governance

Prompts embedded in code couple behavioral changes to application releases. This prevents safe iteration and creates unnecessary friction when refining agent behavior.

A registry allows prompt updates to be managed and promoted independently of application deployments.

## 3.2 Evidence and Traceability

SquadOps places strong emphasis on evidence generation and explainability. If prompts remain embedded in source code, reconstructing the precise prompt used during a historical cycle becomes difficult.

A registry allows every artifact to reference:

- the system prompt fragment identities and versions
- the request template identity and version
- the compiled hashes for both stages

This ensures reproducibility of agent behavior and strengthens evidence trails during review and root cause analysis.

## 3.3 Faster Iteration

Prompt tuning is expected to be a continuous activity as agents evolve.

Separating prompts from code allows:

- controlled refinement
- safer rollout of prompt improvements
- faster development loops
- more disciplined promotion between environments

## 3.4 Architectural Separation of Concerns

This SIP cleanly separates responsibilities.

Langfuse becomes responsible for:

- prompt asset storage (fragments and request templates)
- prompt versioning
- environment labeling
- prompt governance

SquadOps remains responsible for:

- runtime prompt resolution
- cycle context injection
- system prompt assembly (SIP-0057 layered model)
- request template rendering (handler-owned)
- artifact provenance
- execution semantics

This avoids placing orchestration responsibilities inside the prompt registry and avoids placing vendor-specific concerns into core runtime behavior.

## 3.5 Architectural Consistency

SquadOps follows Domain-Driven Design and Hexagonal Architecture. Prompt registry integration should follow the same discipline.

If Langfuse is referenced directly throughout runtime services or agent logic, the platform becomes unnecessarily coupled to a specific external system. Introducing a port and adapter boundary preserves consistency with the rest of the architecture and prevents the prompt registry from becoming an architectural exception.

---

# 4. Architecture Overview

## Current State

System prompts are externalized via SIP-0057's `PromptServicePort` and assembled from filesystem-stored fragments through the `PromptAssembler`. This layer is already well-abstracted.

Request construction is performed inline by 32 handlers across 3 base class hierarchies:

| Base Class | Location | Injects | Handler Count |
|---|---|---|---|
| `_CycleTaskHandler` | `cycle_tasks.py:72` | PRD + prior outputs | 5 |
| `_PlanningTaskHandler` | `planning_tasks.py:103` | PRD + time budget + prior outputs | 14 (planning + wrapup) |
| `_RepairTaskHandler` | `repair_tasks.py:20` | PRD + verification context + upstream outputs | 4 |
| Custom inline | various | handler-specific context | 9 |

Handlers with custom construction include `DevelopmentDevelopHandler`, `QATestHandler`, `BuilderAssembleHandler`, `GovernanceIncorporateFeedbackHandler`, `DataAnalyzeFailureHandler`, `GovernanceCorrectionDecisionHandler`, and the SIP-0079 implementation handlers.

Each handler currently mixes two concerns that should be separated:

1. **Template structure** — the skeleton of the request with sections for instructions, context slots, and output format guidance
2. **Runtime payload construction** — filling in PRD content, artifact text, time budgets, plans, diffs, and other dynamic data

This couples request template changes to application releases and makes prompt provenance difficult to reconstruct after a cycle run.

## Proposed State: Three-Stage Prompt Pipeline

This SIP introduces a three-stage prompt pipeline that preserves the SIP-0057 assembly boundary while adding governed request template management and cleanly separating runtime invocation composition.

### Stage 1: System Prompt Assembly (SIP-0057 — unchanged)

- Deterministic layered assembly from governed fragments
- Layers: identity → constraints → lifecycle → task_type → recovery
- Fragment retrieval delegated to `PromptAssetSourcePort` (new abstraction over filesystem/Langfuse)
- Integrity hash and provenance capture via `assembled.hash`

The SIP-0057 layer stack is NOT extended to include request content. The existing layer model works because it is mostly static and behavioral. Request content is dynamic, instance-specific, and often artifact-derived. Pulling it into fragment assembly would undermine determinism and provenance.

### Stage 2: Request Template Rendering

- Handler resolves a governed request template by identity through the `PromptAssetSourcePort`
- Handler prepares runtime variables from task context, artifacts, and execution state
- Handler renders the template by injecting variables into placeholders
- Rendered template hash is captured for provenance

The registry governs the template. The handler governs what fills it.

### Stage 3: Runtime Invocation Composition (handler-owned)

- Handler composes the final LLM invocation from the assembled system prompt (Stage 1) and the rendered request (Stage 2)
- Handler attaches capability supplements and any additional runtime context
- Prompt guard and summarization apply before submission (SIP-0073)
- Full invocation bundle hash is optionally captured for observability

Runtime invocation composition remains entirely handler-owned. It is not governed by the registry and is not part of deterministic fragment assembly.

### Boundary Rules

- Dynamic request content — plans, diffs, acceptance criteria, failures, artifact excerpts, repo context — are runtime inputs, not prompt fragments. They must not be added as another fragment layer in the SIP-0057 assembly model.
- Request templates may define structure, instructional wording, and placeholders, but must not encode workload routing, retry policy, task sequencing, or context-selection logic.

---

# 5. Recommended Design: PromptAssetSourcePort

This SIP introduces a `PromptAssetSourcePort` as a pluggable backend for retrieving governed prompt assets. The port serves both governed asset types — system prompt fragments and request templates — through a unified retrieval interface.

The current `PromptAssembler` reads system prompt fragments from the filesystem. This SIP introduces an abstraction over the asset source so that governed assets can come from:

- the local filesystem (existing behavior, retained as default and fallback)
- Langfuse (new adapter)
- any future registry implementation

The `PromptAssetSourcePort` should represent capabilities such as:

- resolve a system prompt fragment by identity (e.g., `identity`, `task_type.code_generate`)
- resolve a request template by identity (e.g., `request.development_develop.code_generate`)
- retrieve asset version metadata (version number, environment label)
- retrieve asset content as text

The `PromptServicePort` interface remains unchanged for system prompt assembly — handlers continue to call `assemble()` and `get_system_prompt()`. The change is internal: the assembler delegates fragment retrieval to the configured `PromptAssetSourcePort` instead of reading the filesystem directly.

Request template retrieval is a new capability exposed through the same port, but invoked separately by handlers during Stage 2 rendering. It does not flow through the deterministic assembly pipeline.

---

# 6. Recommended Design: LangfusePromptAssetAdapter

Langfuse will initially be implemented as the concrete adapter behind the `PromptAssetSourcePort`.

This adapter is responsible for translating SquadOps asset resolution requests into Langfuse prompt management API calls and returning normalized content back to the platform.

Langfuse therefore becomes an infrastructure adapter, not a platform dependency exposed to the rest of the system.

This provides several advantages:

- Langfuse can be replaced later without changing core runtime behavior
- test environments can inject alternative adapters (e.g., in-memory, fixture-based)
- the filesystem adapter is retained as a fallback
- registry integration remains aligned with Hexagonal Architecture principles

This SIP does not require additional registry implementations immediately, but the architecture preserves that option from the start.

---

# 7. Recommended Design: Request Template Management

Request templates are governed prompt assets with different characteristics than system prompt fragments. They must be managed accordingly.

### What Request Templates Contain

A request template defines the structural skeleton of a handler's request to the LLM. It includes:

- task-specific instructions and expectations
- named placeholders for runtime variables (e.g., `{{prd_content}}`, `{{prior_outputs}}`, `{{time_budget}}`)
- output format guidance
- section ordering constraints

### What Request Templates Do NOT Contain

Request templates must not contain:

- runtime payload content (PRD text, artifact outputs, plans, diffs, failure evidence, repo listings)
- capability supplements (handler-owned runtime context)
- workload routing, retry policy, task sequencing, or context-selection logic
- execution semantics of any kind

### Handler Ownership

Handlers continue to own:

- request template selection (choosing which template to resolve)
- runtime variable preparation (gathering context from task, artifacts, and execution state)
- context inclusion decisions (what artifacts and findings to attach)
- capability supplement attachment
- truncation and summarization policy (prompt guard, SIP-0073)
- final invocation composition and render timing

The registry owns:

- template storage
- versioning
- environment labels
- retrieval
- audit metadata

Not execution semantics.

### Runtime Payload Rules

- Request templates may define placeholders for runtime variables
- Handlers may inject runtime values at render time
- Injected runtime values are not prompt fragments and are not governed by the registry
- Injected values must remain traceable to source artifacts and task context
- Oversized runtime payloads must pass through summarization and prompt budget controls before render (SIP-0073)

Design constraint: prior analysis must remain the LAST section in the rendered request to preserve prompt guard truncation behavior.

---

# 8. Recommended Design: Caching, Resilience, and Cycle Immutability

Because SquadOps executes multi-hour cycles with many agent invocations, prompt asset retrieval must include a local caching, resilience, and consistency strategy.

### Caching

- Cache assets by identity and resolved version
- Maintain cache for the duration of a cycle run (ensures prompt consistency within a cycle)
- Invalidate cache between cycle runs to pick up promotions

### Cycle Immutability Rule

- Cycle startup may fail if required governed assets cannot be resolved from the registry
- Once a cycle begins, the resolved asset set for that cycle is immutable
- The platform must not re-resolve assets mid-cycle even if environment labels change in the registry
- If mid-cycle refresh is needed in the future, it must be introduced by explicit design with its own governance model

This prevents subtle inconsistency where a long-running cycle begins with one prompt asset version and later resolves another because an environment label changed underneath it.

### Resilience and Failure Behavior

The following failure modes must be handled explicitly:

| Scenario | Behavior |
|---|---|
| Langfuse unavailable at cycle start | Fail the cycle with a clear error — do not silently fall back to stale or empty assets |
| Langfuse becomes unavailable mid-cycle | Continue using cached assets for the remainder of the cycle; log a warning |
| Asset not found in registry | Fail the task with an explicit error identifying the missing asset identity |
| Langfuse available but slow | Cache hit serves immediately; cache miss blocks with a configurable timeout (default: 10s) |

Caching should remain an internal runtime concern and should not weaken the authority of the external registry as the source of managed prompt assets.

---

# 9. Recommended Design: Naming Conventions

Prompt asset identities should follow structured naming conventions aligned with agent roles, handler hierarchies, and the existing SIP-0057 fragment identity patterns.

### System Prompt Fragments

Retain existing SIP-0057 identity patterns:

- `identity` — agent identity layer
- `constraints.global` — global constraints
- `lifecycle.{hook}` — lifecycle-specific (e.g., `lifecycle.agent_start`)
- `task_type.{task_type}` — task-type-specific (e.g., `task_type.code_generate`)
- `recovery` — recovery context

### Request Templates

New naming convention for request templates:

```
request.{handler_class}.{task_type}
```

Examples:

- `request.development_develop.code_generate`
- `request.qa_test.test_validate`
- `request.builder_assemble.build_assemble`
- `request.data_analyze_failure.analyze_failure`
- `request.governance_correction_decision.correction_decision`
- `request.planning_base.strategy_define` (base class template used by multiple planning handlers)

This convention supports:

- predictable asset discovery
- clear mapping between templates and handler responsibilities
- easier governance and auditing
- cleaner environment promotion workflows

Asset names should remain stable across versions, while version numbers and labels track evolution and release state.

---

# 10. Recommended Design: Prompt Lifecycle

Prompt asset management should follow a lightweight lifecycle consistent with governed change management.

A recommended lifecycle is:

- draft
- staging
- production

The purpose of this lifecycle is to ensure that prompt improvements can be developed and reviewed safely before they are promoted into active cycle execution.

Langfuse labels or equivalent environment markers should be used to support this promotion path, while SquadOps should resolve assets by environment or deployment context rather than by ad hoc selection.

This keeps prompt change management disciplined without overcomplicating the initial implementation.

---

# 11. Recommended Design: Provenance Hashing

Provenance hashing is separated into stages matching the three-stage prompt pipeline. Provenance should prefer recording asset identifiers and versions alongside rendered hashes, as the combination gives much better reproducibility and makes comparison across runs easier than relying on rendered hashes alone.

### Stage 1: System Prompt Assembly Provenance

The existing `PromptAssembler` (SIP-0057) already generates SHA256 hashes of assembled system prompts via `assembled.hash`. This behavior is unchanged.

Provenance records:
- fragment identities and versions used in assembly
- assembled system prompt hash

### Stage 2: Request Template Rendering Provenance

A separate deterministic hash is generated for the fully rendered request.

Provenance records:
- request template identity and version
- rendered request hash (after variable injection)

### Stage 3: Invocation Composition Provenance (optional)

An optional `full_invocation_bundle_hash` may be computed by combining the Stage 1 hash, Stage 2 hash, and any capability supplement identities. This provides a single fingerprint for the complete LLM invocation for simplified comparison.

This separation ensures that system prompt assembly provenance and request rendering provenance can be analyzed independently — critical for RCA, replay, and experiment comparison. When investigating a cycle outcome, the asset identifier plus version plus rendered hash gives a complete picture: what template was used, which version, and what it looked like after rendering.

---

# 12. Artifact Provenance Enhancements

Artifact metadata should include prompt provenance fields, separated by pipeline stage.

These fields allow SquadOps to reconstruct prompt usage during historical analysis, evidence review, and root cause investigations.

### Provenance Fields

| Field | Stage | Description |
|---|---|---|
| `system_prompt_bundle_hash` | 1 | SHA256 of assembled system prompt (from SIP-0057) |
| `system_fragment_ids` | 1 | List of fragment identities used in assembly |
| `system_fragment_versions` | 1 | Corresponding version numbers |
| `request_template_id` | 2 | Identity of the request template used |
| `request_template_version` | 2 | Version of the request template |
| `request_render_hash` | 2 | SHA256 of the fully rendered request |
| `capability_supplement_ids` | 3 | Identities of any capability supplements attached (runtime, not governed) |
| `full_invocation_bundle_hash` | — | Optional combined hash of Stage 1 + Stage 2 + Stage 3 |
| `prompt_environment` | — | Environment label at time of resolution (draft/staging/production) |

These fields should be added to the `ArtifactRef` dataclass as optional fields, defaulting to `None` for backward compatibility with existing artifacts.

---

# 13. Responsibility Boundaries

Responsibility boundaries should remain explicit.

## Langfuse Responsibilities

Langfuse is the governed prompt asset registry and observability layer. It is responsible for:

- managed storage of prompt assets (system fragments and request templates)
- prompt versioning
- prompt labels and environment association
- external governance of prompt changes

## SquadOps Responsibilities

SquadOps retains full authority over execution. It is responsible for:

- asset source abstraction through `PromptAssetSourcePort`
- runtime asset retrieval through the configured adapter
- system prompt assembly via SIP-0057 layered model (Stage 1)
- request template rendering with handler-owned variable injection (Stage 2)
- runtime invocation composition (Stage 3)
- runtime request payload construction
- compiled provenance hashing (all stages)
- artifact provenance recording
- workload semantics
- handler behavior and context selection
- retry and recovery logic
- execution policy
- caching, resilience, and cycle immutability

Langfuse must not become a hidden orchestration dependency. SquadOps must not offload core runtime responsibilities — workload semantics, handler behavior, context selection, retry/recovery logic, or execution policy — into prompt assets or the registry.

---

# 14. Migration Strategy

Migration should proceed in stages to minimize disruption.

## Stage 1 — Prompt Asset Inventory and Extraction

Catalog all governed prompt content across the codebase:

- System prompt fragments currently in the filesystem (SIP-0057 layer files)
- Request templates currently constructed inline by handler methods across 3 base classes and 9 custom handlers
- Identify template variable placeholders needed for each request template
- Document which runtime values each handler injects (these stay in code)
- Identify capability supplements (these remain runtime concerns, not governed assets)

Extract governed assets into Langfuse using the naming convention from Section 9.

**Estimated scope**: ~15 system fragments + ~20 request templates.

## Stage 2 — PromptAssetSourcePort and Adapter

Introduce the `PromptAssetSourcePort` abstraction. Refactor the existing `PromptAssembler` to delegate fragment retrieval to the configured source instead of reading the filesystem directly. Implement the `LangfusePromptAssetAdapter` and retain the filesystem adapter as the default.

## Stage 3 — Request Template Resolution

Refactor the 3 base class handler methods to resolve request templates through the port and inject runtime variables into placeholders. Refactor custom handlers to use the same pattern. Verify that:

- prompt guard truncation behavior is preserved (SIP-0073)
- prior analysis remains the last section in rendered requests
- all runtime payload injection remains in handler code
- capability supplements remain handler-attached runtime content

## Stage 4 — Artifact Provenance Integration

Add prompt provenance fields (Section 12) to `ArtifactRef`. Update artifact generation in handlers to record system prompt assembly provenance and request rendering provenance as separate tracked events.

## Stage 5 — Validation Cycles

Run validation cycles to confirm that asset resolution, caching, cycle immutability, resilience behavior, and artifact tracing work correctly across realistic multi-hour runs. Verify that prompt assets can be updated in Langfuse and picked up by subsequent cycles without redeployment.

---

# 15. Risks

## Prompt Drift

Prompt asset updates may unintentionally alter agent behavior.

Mitigation includes:

- controlled promotion through draft → staging → production lifecycle
- environment labels preventing accidental production exposure
- cycle immutability rule preventing mid-cycle asset changes
- artifact provenance that records exact asset identities, versions, and compiled hashes
- ability to reconstruct and compare prompts across cycle runs

## Registry Dependency

SquadOps runtime will depend on Langfuse availability for cycle startup.

Mitigation includes:

- `PromptAssetSourcePort` insulation
- per-cycle asset caching with mid-cycle resilience (Section 8)
- explicit failure-at-start rather than silent fallback to prevent cycles running with wrong prompts
- filesystem adapter retained as a manually-configured fallback for disaster recovery

## Over-Coupling to the Initial Vendor

Even when the registry is useful, direct Langfuse dependency in core runtime services would create long-term architectural debt.

Mitigation includes introducing the port and adapter boundary as part of the initial implementation rather than as a later cleanup effort.

## Template Variable Mismatch

Request templates with variable placeholders could drift from the handler code that injects values, causing runtime errors or incomplete requests.

Mitigation includes:

- validation at template registration time (required variables documented per template)
- handler tests that verify all template variables are populated
- clear error messages when a required variable is missing

## Registry Scope Creep

Without clear boundaries, orchestration decisions, execution policies, or runtime logic could gradually migrate into prompt assets or registry configuration.

Mitigation includes:

- the explicit responsibility boundary in Section 13
- the normative rule that runtime request payloads and capability supplements are not governed assets
- the three-stage pipeline separation that keeps assembly, rendering, and composition architecturally distinct
- the hard rule that request templates must not encode workload routing, retry policy, task sequencing, or context-selection logic
- code review enforcement that prompt assets contain only behavioral guidance and structural templates, never execution logic

---

# 16. Benefits

Adopting a prompt registry with a port and adapter boundary provides several key benefits.

- independent prompt governance without code deployments
- faster prompt iteration cycles
- stronger artifact traceability with multi-stage provenance
- reproducible agent behavior across cycle runs via cycle immutability
- improved runtime resilience through caching
- cleaner alignment with DDD and Hexagonal Architecture
- reduced architectural coupling to Langfuse
- natural extension of SIP-0057's layered prompt system without diluting it
- clean separation between governed prompt assets and runtime request payloads
- observability and experimentation support for both system prompts and request templates

This capability also prepares SquadOps for more advanced prompt lifecycle management in the future without forcing premature complexity into the current release.

---

# 17. Future Extensions

Potential future enhancements include:

- alternative registry adapters (e.g., Git-backed, S3-backed)
- file-backed fallback prompt registry for air-gapped deployments
- prompt evaluation pipelines (A/B testing prompt variants)
- prompt experimentation frameworks
- automated prompt RCA analysis (correlating prompt versions with cycle outcomes)
- prompt performance analytics (token efficiency, output quality by prompt version)
- request template composition models (sharing template sections across handler families)
- governed capability supplement promotion (if supplements mature into stable behavioral assets)
- mid-cycle refresh protocol (if long-running cycles require controlled asset updates)

These capabilities are intentionally excluded from this SIP in order to keep the initial implementation focused, low risk, and appropriate for 1.0.1.

---

# 18. Decision

If accepted, this SIP will be implemented in SquadOps v1.0.1.
