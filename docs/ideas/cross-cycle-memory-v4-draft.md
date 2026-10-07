# Cross-Cycle Agent Memory Architecture — v4 draft (2026-08-29)

> **Recorded 2026-10-01** as the owner shared it, during the review of 2.0's SIP proposals. It is a later
> draft of `sips/accepted/SIP-0110-Cross-Cycle-Memory.md`. Its new elements are folded into that SIP as
> **revision 3**, §5a. This file keeps the source.
>
> Its original metadata:
> - title: "Cross-Cycle Agent Memory Architecture — Phase 1: Collaborative Memory Distillation";
> - status: proposed; author: SquadOps Architecture; created 2026-08-29;
> - original filename: `SIP-Cross-Cycle-Memory-Architecture-v4.md`.
>
> **Stale against main on 2026-10-01** (corrected in revision 3):
> - #571, its named prerequisite, is closed;
> - its read seam names `InProcessFlowExecutor`, but live cycles run through the dispatched executor,
>   and recall goes through `plan_rejection_context`;
> - its four-arm experiment asks for at least 30 historical failure plans, but plan-gate rejections
>   stopped on 2026-08-23 (13 records);
> - its experiment names SIP-0101, but the convergence replay harness (#1765) is the per-arm
>   instrument that exists.

## 1. Abstract

The SquadOps framework features highly disciplined, evidence-bearing planning and execution pipelines (SIP-0096, SIP-0103). However, cycle execution currently remains stateless across runs. When a cycle completes or terminates, the rich, structured diagnostic evidence and gate-rejection reasons produced by validators are discarded. Consequently, recurring failure classes reappear across independent cycles, consuming expensive framing and implementation budgets.

This proposal establishes a unified **Cross-Cycle Agent Memory Architecture** for SquadOps, defining three major memory classes: **Episodic Memory** (procedural trajectories), **Semantic Memory** (factual state), and **Behavioral Memory** (corrective constraints).

As its Phase 1 implementation, this SIP introduces **Collaborative Memory Distillation**—an evidence-governed behavioral learning loop that:
1. **Asynchronously extracts** *Verified Behavioral Patterns* (VBPs) from explicit, code-level validator rejections and gate decisions.
2. **Encodes these patterns** via a governed, file-based registry mapping validator-emitted rejection classes to structured, static behavioral templates, ensuring zero model-driven hallucination in the memory-writing loop.
3. **Implements a deterministic Applicability Gate** (evaluating Project, Role, Task, and Stack metadata) and a confidence-weighted recall pipeline, bypassing the "stale-fact poisoning" of unconstrained semantic retrieval.
4. **Injects VBPs** into future cycles using a *Reflective Inversion Prompt*—wrapping recalled rules in external system `<memory>` tags rather than the model's own `<thought>` blocks, bypassing the model's self-correction blind spot.
5. **Enforces a strict trust lifecycle** (Candidate, Validated, Promoted, Deprecated) and measures performance using a rigorous **4-Arm experimental harness** and the **Failure Recurrence Suppression Rate (FRSR)**.

## 2. Core Thesis

**SquadOps memory is not a database of things agents have seen. It is an evidence-governed system through which experience can influence future behavior.**

The framework should not merely store historical records; it must learn which verified failure patterns matter, encode them as reusable behavioral constraints, determine when those constraints apply, and measure whether applying them improves subsequent execution. Memory in SquadOps operates as an *evidence-backed control loop* rather than a static knowledge repository.

## 3. Problem Statement & Motivation

### 3.1 The "Trap of the Shipped Patch"
Currently, when a recurring failure class is identified across runs—such as the developer agent re-implementing an in-memory database parallel to the database-backed Cycle Data Store (CDS) (#301), or generating unresolvable imports (#154)—the only available remedy is for a human developer to manually construct a permanent framework prompt patch. Examples of these manual interventions include:
*   **The `api_behavior_contract` lines (#629):** Patching prompts because five consecutive cycles asserted HTTP 200 instead of HTTP 201.
*   **The `dom_testid_surface` inventory (#659):** Patching prompts because models invented DOM selectors that did not exist in the React frontend.
*   **The framing rejection context (#669):** Patching the in-cycle re-roll prompt because models repeatedly re-emitted identical invalid YAML.

This "patch-per-class" model does not scale. It increases prompt maintenance overhead, dilutes context windows with rules for out-of-scope stacks, and couples cognitive guidance directly to framework releases.

### 3.2 Naive Memory Pitfalls
Attempting to solve this by storing complete raw execution traces or utilizing unconstrained semantic search introduces severe production regressions:
*   **Context Bloat:** Injecting multi-thousand-token raw failure logs quickly saturates the model's context window, degrading attention and driving up latency.
*   **Stale-Fact Poisoning:** Letting an agent remember specific file paths or variable names from a prior project causes it to hallucinate those exact details when executing a completely different task in a new project.
*   **Contradiction Accumulation:** A naive vector store accumulates conflicting instructions over time as the codebase, dependencies, and interfaces evolve.

## 4. The Memory Taxonomy

The Cross-Cycle Agent Memory Architecture organizes persistent state into three distinct, orthogonal memory classes:

1.  **Episodic Memory (Procedural):** Captures temporal, sequence-specific execution trajectories, tool-call responses, and planning decisions. This history is transient, heavy, and intended primarily for in-cycle rollbacks or post-mortem debugging.
2.  **Semantic Memory (Factual):** Stores authoritative, project-level facts and configurations (e.g., active database schemas, approved API endpoints, tool availability, and organizational policies). This knowledge represents static states of the world.
3.  **Behavioral Memory (Corrective):** Houses distilled, de-factualized behavioral constraints derived from verified execution failures. These represent *rules of action* that actively alter the future behavior of generating agents.

*Scope of this SIP:* **Phase 1 of this architecture exclusively implements the Behavioral Memory branch.** Semantic and Episodic persistence interfaces remain open but inert, protected from accidental pollution by behavioral data.

## 5. Design Approach & Concept Topology

The system separates **cognitive decision-making** from **deterministic system control**. Collaborative Memory Distillation treats behavioral memories not as freeform thoughts, but as **immutable behavioral constraints** managed entirely by the orchestrator. A read seam queries the `MemoryPort` and applies the Applicability Gate; a write seam extracts a VBP on a gate or run rejection, matched to its rejection class; both sit over the LanceDB persistence adapter.

### 5.1 Behavioral, Not Factual (De-Factualization)
To prevent stale-fact poisoning, the distillation pipeline never records raw execution facts (e.g., "Line 42 of `api.py` is missing an import"). Instead, when a validator rejects a run, the system maps the error to a pre-defined **rejection class** representing a **behavioral tendency** and its corresponding **corrective rule** (e.g., "API handlers tend to omit required module imports; verify that all imported entities are explicitly declared in the file headers").

### 5.2 Deterministic Seams, No Agent Discretion
Memory operations occur exclusively at explicit pipeline boundaries managed by the orchestration engine:
*   **The Read Seam:** Triggers once during task initialization (within `InProcessFlowExecutor`). The orchestrator queries the `MemoryPort` for memories matching the project namespace, agent role, and active task type.
*   **The Write Seam:** Triggers once upon a formal gate rejection (e.g., Eve QA failure) or run validation failure. The orchestrator maps the failure logs to the corresponding validator metadata to write a VBP candidacy.
Agents have no autonomous `remember()` or `recall()` tool-calls, preserving execution path predictability and repeatability.

### 5.3 Bypassing the Self-Correction Blind Spot (Reflective Inversion)
A model asked to audit its own reasoning trace inside its own `<thought>` blocks suffers from an addressability failure—it lacks a discrete, external handle to act upon. By extracting the failure, translating it into a behavioral rule, and injecting it wrapped in system `<memory>` tags, the orchestration engine transforms a thought-internal error into an authoritative, external source of record.

This shifts the model's cognitive mode from blind self-justification to active memory-reconciliation. Crucially, the role-separated `<memory>` tag is treated as an *initial implementation strategy* rather than an immutable core dependency; the core architectural invariant remains the use of externalized behavioral constraints, keeping the prompt composition modular and experimentally replaceable.

## 6. Core Specifications & Invariants

### 6.1 Concept Domain Schema: `VerifiedBehavioralPattern` (VBP)
At the domain boundary, every VBP record is represented by an immutable structure containing:
*   **Identifier:** A unique, chronologically sortable ULID string.
*   **Scope Boundaries:** `project_id` (limits recall to the originating project context); `owner_role` (the target agent role); `task_type` (the targeted execution task class); `stack_type` (the specific technical stack).
*   **Cognitive Payload:** `rejection_class` (the canonical validator identifier); `behavioral_tendency` (a generic, de-factualized description of the failure pattern); `corrective_rule` (an actionable, prescriptive constraint to govern the generation prompt).
*   **The Triad Metric Model:** `evidence_trustworthiness` (a score in [0.0, 1.0] based on the originating validator's precision, e.g. static syntax compiler = 1.0, heuristic LLM check = 0.6); `historical_effectiveness` (the FRSR over all runs where this VBP was injected); `contextual_applicability` (a dynamically calculated similarity score in [0.0, 1.0] matching active run metadata).
*   **Trust & Lifecycle Metrics:** `status` (`candidate`, `validated`, `promoted`, `deprecated`); `reuse_count`; `decay_counter` (consecutive runs where the error class recurred despite this VBP being injected).
*   **Provenance Stamp:** References to the originating `cycle_id`, `campaign_id` (if any), model family name, and the unique validator execution log ID that triggered the memory.

### 6.2 The Lifecycle & Trust Hierarchy
1.  **Candidate:** Automatically written by the orchestrator upon a verified validator rejection.
2.  **Validated:** Automatically promoted if the next subsequent run of the same task type resolves the targeted error class.
3.  **Promoted:** Manually promoted by an operator via the Continuum UI, elevating the memory from project-specific scope to organization-wide scope (applicable across all projects utilizing the same tech stack).
4.  **Deprecated:** Demoted if the `decay_counter` exceeds a defined threshold K, indicating the rule is ineffective or obsolete.

### 6.3 The Applicability Gate
To eliminate out-of-context retrieval, the system implements a deterministic **Applicability Gate** that executes *before* the vector database is queried: Recall = f(Project, Role, Task Type, Stack Type). A VBP must satisfy these hard meta-filters to be considered eligible for similarity-based ranking.

### 6.4 The Encoding Template Registry Spec
The translation of a raw validation failure into a de-factualized VBP must be entirely deterministic. The framework maintains a checked-in, reviewed registry (YAML-specified) that maps `rejection_class` identifiers directly to static text templates for `behavioral_tendency` and `corrective_rule`.

*Invariant:* The system must raise a system error and default to a `blocked_unverified` state if a validator emits a rejection class that is absent from the encoding registry.

### 6.5 Mode-Neutral Substrate and Operational Modes
*   **Cycle Mode:** Memory access is strictly restricted to deterministic Read/Write pipeline seams. No discretionary agent tool-calls are permitted during execution.
*   **Duty Mode (The Pass-Down Ledger):** At `DutyWindow` startup, the assigned agent queries `MemoryPort` to recall project-scoped and agent-scoped constraints. At shift handover, the outgoing agent's handoff summary is automatically committed as a structured memory.
*   **Ambient Mode (The Quarantine Rule):** Ambient-born memories enter strictly as **`candidate`** status, quarantined and excluded from Cycle-mode recall until audited and promoted by an operator.

## 7. Metrics and Metrology

### 7.1 Failure Recurrence Suppression Rate (FRSR)
FRSR = 1.0 − (N_recurred / N_injected), where N_injected is the number of runs of a task type where a specific VBP was recalled and injected, and N_recurred the number of those runs where the exact rejection class targeted by that VBP recurred.

### 7.2 Context Efficiency
Context Efficiency = (tokens consumed by VBP injection) / (tokens consumed by raw trace replay). The goal is Context Efficiency ≪ 1.0 with equal or superior failure suppression.

## 8. Acceptance Criteria & The 4-Arm Proving Ground

### 8.1 The Prerequisite Boundary (#571)
The LanceDB adapter must apply project namespace, role, and task-type filtering natively at the database level before result limiting occurs, and its similarity metric must be unified on Cosine Similarity.

### 8.2 The 4-Arm Experimental Harness (Falsifiability)
Using the Cycle Replay Harness (SIP-0101), run a 4-arm trial over a pre-registered corpus of at least N = 30 historical failure plans, asserting that Arm D outperforms both Arm B and Arm C under matched cost and budget constraints:
*   **Arm A (Control):** no historical memory context.
*   **Arm B (Raw Replay):** the complete raw terminal trace and linter error logs from the prior failed cycle.
*   **Arm C (Factual Memory):** raw, factual semantic memory entries.
*   **Arm D (VBP):** distilled, de-factualized Verified Behavioral Patterns via the Reflective Inversion Prompt.

## 9. Edge Cases, Risks, & Mitigation Scenarios

### 9.1 Model Upgrades and Prompt Drift
VBPs carry the originating model family name as metadata. The recall query penalizes the contextual applicability score of memories whose originating model differs from the active task model.

### 9.2 Contradictory Validator Rejections
A **Rejection Precedence Hierarchy**: in any given run, only the highest-priority validator failure (Syntax/Compilation → Security Boundaries → Functional Yield → Performance Limits) may write a VBP candidacy.

### 9.3 Cognitive Over-Conservatism
A hard **Memory Density Cap** of 3 recalled memories per task, selected by weighted confidence.

## 10. Alternative Designs Considered

### 10.1 Raw Trace Context Re-rolls
Rejected: severe context bloat and cognitive drift; models were distracted by secondary logs.

### 10.2 Autonomous Agent-Driven Memory
Rejected: agents wrote subjective, imprecise or hallucinated "lessons learned" that contradicted validators. Validator-only writes keep memory an objective feedback loop.

### 10.3 Human-in-the-Loop Interventions Only
Rejected in this draft: a human bottleneck that defeats long-horizon, unattended campaigns. *(Revision 3 records why 2.0 resolves this case with the prior-cycle brief and the crew's outer loop instead; see the SIP's §5a.)*
