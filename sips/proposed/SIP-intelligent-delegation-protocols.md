# SIP-0XXX: Intelligent Delegation Protocols for SquadOps

## Status
Proposed

## Authors
SquadOps Core Team

## Source
This SIP adapts design principles from the “Intelligent Delegation” paper (arXiv:2602.11865) and applies them to SquadOps’ Cycle / Workload / Pulse / Task execution model and control plane.

---

## 1. Summary

This SIP introduces a first-class **Intelligent Delegation** layer in SquadOps to make delegation **verifiable, auditable, adaptive, and governed**. It standardizes:

- **Contract-first decomposition** (decompose until outputs are verifiable)
- **Verification-gated completion** (no “done” without artifacts)
- **Delegation-chain attestations** (transitive accountability)
- **Adaptive coordination triggers** (external + internal runtime contingencies)
- **Structured observability events** (Task lifecycle + checkpoints)
- **Permission governance** (scoped access, TTLs, continuous validation, circuit breakers, policy-as-code)
- **Complexity-aware execution lanes** (lightweight lane to avoid overhead for trivial work)

---

## 2. Motivation

SquadOps is designed to run autonomous cycles over long durations. As autonomy increases, so does the risk that:

- work decomposition becomes subjective or unverifiable,
- delegated work lacks accountability through chains of sub-delegation,
- progress monitoring becomes inconsistent and hard to automate,
- permissions become static and overly broad (or too brittle),
- coordination becomes either too rigid (static plan) or too chaotic (ad-hoc rework),
- operational overhead (checks, reporting) reduces throughput.

This SIP establishes explicit protocols that turn these failure modes into **enforceable system rules**, enabling trustworthy autonomy without turning Pulse Checks into a productivity bottleneck.

---

## 3. Goals

1. Make all non-trivial work **contracted and verifiable**.
2. Enable **transitive accountability** across delegation chains.
3. Provide **adaptive coordination** via trigger-driven replanning and escalation.
4. Standardize telemetry so Pulse Checks can operate on **events and evidence**, not narrative.
5. Govern permissions via **scoped issuance, continuous validation, automated revocation**, and **policy-as-code**.
6. Prevent process overhead from dominating execution via a **lightweight lane** for low-criticality work.

---

## 4. Non-goals

- Implementing a full economic/reputation marketplace (this SIP only defines the protocol hooks).
- Replacing existing Cycle / Workload / Pulse / Task semantics.
- Introducing new top-level planning primitives beyond SquadOps’ existing hierarchy.

---

## 5. Definitions

- **Verifiability**: A property of an output indicating it can be validated at acceptable cost using a defined method.
- **Verification Plan**: The declared method(s) and artifacts required to validate a task output.
- **Attestation**: A signed summary and evidence bundle produced by a delegate that vouches for delegated work (including sub-delegation outcomes).
- **Trigger**: A structured event indicating a runtime contingency requiring adaptation.
- **Circuit breaker**: Automated system action that constrains or halts execution when safety/quality/cost boundaries are violated.
- **Lightweight lane**: An execution mode that reduces protocol overhead for small/low-risk tasks.

---

## 6. Design Overview

### 6.1 Contract-first decomposition (planner invariant)

**Invariant:** A task MUST NOT enter execution unless it is verifiable under its Verification Plan.

- If a proposed task is not verifiable (or verification cost is excessive), it MUST be decomposed further until verifiable.
- This invariant is enforced during planning by **Lead** and **Strategy** and validated by the control plane.

**Implication:** Planning becomes “split until you can prove correctness,” not “split until it feels manageable.”

### 6.2 Verification-gated completion (execution invariant)

**Invariant:** `TASK_COMPLETED` MUST NOT be emitted unless verification artifacts are attached and pass.

Examples of acceptable artifacts:
- unit/integration test reports
- typecheck and lint outputs
- eval suite scores
- diff references and build logs
- human review acknowledgements (when required)

### 6.3 Delegation-chain attestations (transitive accountability)

When an agent delegates to another agent (or to a worker group), the delegating agent remains accountable for:
- defining the contract,
- validating the verification artifacts,
- emitting an **attestation** that summarizes outcomes and evidence.

When sub-delegation occurs, accountability becomes transitive:
- a delegate provides attestations for its sub-delegations,
- the upstream agent attests to the delegate’s ability to monitor and verify.

### 6.4 Adaptive coordination triggers (runtime adaptation)

Execution must adapt to contingencies. Triggers are classified:

- **External triggers**: dependency changes, spec changes, service/tool outages, repo changes, environment drift.
- **Internal triggers**: repeated task failure, verification regression, escalating cost burn, latency spikes, low confidence, anomalous behavior.

Triggers map to standardized actions:
- pause workload
- re-plan next pulse
- swap delegatee
- narrow scope / decompose further
- escalate to human gate
- open RCA branch and rewind the task graph to a stable checkpoint

### 6.5 Standard observability events (structured telemetry)

SquadOps emits standardized events for automated monitoring and governance:

- `TASK_STARTED`
- `CHECKPOINT_REACHED`
- `RESOURCE_WARNING`
- `TASK_COMPLETED` (verification-gated)
- `TASK_FAILED` (with failure class and retry policy)
- `DELEGATION_ISSUED`
- `ATTESTATION_EMITTED`
- `TRIGGER_FIRED`
- `CIRCUIT_BREAKER_TRIPPED`

Pulse Checks MUST consume these events and attached evidence rather than relying on narrative-only status.

### 6.6 Permission governance (scoped, validated, revocable)

Capabilities and tool access MUST be issued per-task (or per-pulse) with scope + TTL.

Key behaviors:
- **Scoped tokens**: bound to Task/Workload identity and tool/resource set.
- **Continuous validation**: runtime checks maintain that permissions remain safe and necessary.
- **Automated revocation**: circuit breakers revoke credentials and halt actions on violations.
- **Policy-as-code**: rules are versioned, auditable, and testable (checked into the repo).

### 6.7 Complexity-aware execution lanes (avoid delegation overhead)

Delegation has transaction costs (contracting, verification, monitoring). To prevent overhead from dominating:

- Tasks classified as low criticality + low uncertainty + short duration MAY use the **lightweight lane**:
  - reduced checkpoint frequency
  - simplified verification plan
  - minimal attestation requirements
- Non-trivial tasks MUST use the standard lane.

---

## 7. Spec Changes

### 7.1 TaskSpec extensions

Add the following fields to TaskSpec (or equivalent schema):

- `criticality`: `low | medium | high`
- `uncertainty`: `low | medium | high`
- `duration_est`: optional human-readable estimate
- `privacy_level`: `public | internal | restricted`
- `verifiability_mode`: e.g., `tests`, `eval`, `static_analysis`, `human_review`, `hybrid`
- `verification_plan`: structured plan detailing checks and required artifacts
- `permission_scope`: declared tools/resources permitted
- `token_ttl_seconds`: requested TTL for scoped credentials
- `lane`: `lightweight | standard` (default `standard`)

### 7.2 Attestation object

Introduce an `Attestation` record:

- `attestation_id`
- `cycle_id`, `workload_id`, `pulse_id`, `task_id`
- `delegator_agent_id`, `delegatee_agent_id`
- `contract_summary` (what was asked)
- `verification_summary` (what was checked and results)
- `evidence_refs[]` (artifact pointers)
- `cost_summary` (tokens/time/tool calls, as available)
- `subdelegation_attestations[]` (optional)
- `signature` (agent identity signature)

### 7.3 Trigger object

Introduce a `Trigger` record:

- `trigger_id`
- `cycle_id`, `workload_id`, `pulse_id`, optional `task_id`
- `trigger_type`: `external | internal`
- `trigger_code`: enumerated category
- `severity`: `info | warn | critical`
- `evidence_refs[]`
- `recommended_actions[]` (standard action codes)
- `created_at`

### 7.4 Permission policy-as-code

Define a repository-managed policy file (format TBD by implementation; YAML or JSON recommended):

- Allowed capability scopes per role
- Maximum TTLs per scope
- Conditions that require human escalation
- Circuit breaker thresholds (cost/time/failure/anomaly)

---

## 8. Control Plane and Runtime Behavior

### 8.1 Planning responsibilities

- **Lead**: owns enforcement of contract-first decomposition and lane selection.
- **Strategy**: ensures task boundaries map to verifiable outputs and defines verification plans.

### 8.2 Implementation responsibilities

- **Dev**: implements schema extensions, event emission, token scoping, policy checks.
- **QA**: defines verification plan templates, acceptance tests for gating behavior.
- **Data**: defines telemetry payload schema, metrics aggregation, and trigger detectors.

### 8.3 Circuit breaker behaviors

Circuit breakers MAY trip on:
- runaway cost burn relative to budget
- repeated verification failures beyond retry policy
- anomaly detection signals (tool misuse, unexpected network patterns, etc.)
- unauthorized scope attempts

Actions:
- revoke scoped credentials
- freeze workload execution
- require re-plan
- require human escalation for resume

---

## 9. Telemetry and Metrics

Minimum required metrics:
- Task completion rate by lane/criticality
- Verification pass rate (first-pass vs after retries)
- Delegation chain depth and attestation completeness
- Trigger rates by type/severity
- Circuit breaker trips (counts, root causes)
- Cost per verified task (tokens/time/tool calls)

---

## 10. Rollout Plan

1. **Schema introduction**
   - Add TaskSpec fields (non-breaking defaults)
   - Add event types (emitted but not enforced)
2. **Verification gating**
   - Enforce `TASK_COMPLETED` gating for `standard` lane tasks
3. **Attestation enforcement**
   - Require attestations for cross-agent delegation
4. **Permission scoping + TTL**
   - Issue scoped tokens per task/pulse
5. **Circuit breakers**
   - Enable revocation/freeze policies for critical thresholds
6. **Trigger-driven adaptation**
   - Enable automatic action mapping for approved trigger codes
7. **Lightweight lane**
   - Enable policy-based eligibility and reduced protocol overhead

---

## 11. Risks and Mitigations

- **Overhead risk**: Protocol costs could reduce throughput.
  - Mitigation: lightweight lane + policy-based gating; only enforce the full protocol on non-trivial work.
- **False positives**: triggers/circuit breakers may halt useful work.
  - Mitigation: severity thresholds, staged enforcement, and human override gates.
- **Schema complexity**: additional fields increase cognitive load.
  - Mitigation: templates, defaults, and tooling that auto-fills common patterns.

---

## 12. Acceptance Criteria

1. A task cannot be marked complete unless verification artifacts are attached and validated (standard lane).
2. Cross-agent delegation emits an attestation with evidence references.
3. Triggers are emitted with type/severity and map to standardized actions.
4. Permissions are scoped and time-bound; attempts outside scope are blocked and logged.
5. Circuit breakers can revoke credentials and freeze execution on configured thresholds.
6. Pulse Checks can be executed using structured events + artifacts without relying on narrative-only status.

---

## 13. Open Questions

1. Exact signature mechanism for attestations (key management, rotation, trust root).
2. Canonical policy-as-code format and validation tooling.
3. Minimum required verification plan templates by task category.
4. Default trigger codes and standardized action mappings.
5. How to represent evidence pointers (filesystem paths, artifact store URIs, repo refs, Langfuse spans).
