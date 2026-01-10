---
sip_uid: 01KEM71ECNVQ8381E1Z63V7F5S
sip_number: null
title: Capability Contracts + Reference Workloads for Delivery-Grade Artifact Proof
status: proposed
author: Framework Committee
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-10T15:05:29Z'
original_filename: SIP-AGENT-CAPABILITY-CONTRACTS-0_8_6.md
---
# SIP-AGENT-CAPABILITY-CONTRACTS-0_8_6 — Version Target 0.8.6
## Capability Contracts + Reference Workloads for Delivery-Grade Artifact Proof

**Status:** Proposed  
**Target Version:** 0.8.6  
**Author:** Framework Committee  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data

---

# 1. Purpose and Intent

This SIP introduces **Capability Contracts** and **Reference Workloads** as a delivery validation layer that proves SquadOps agents can **produce durable, deterministic artifacts** across a Cycle / Pulse / Task execution—beyond merely executing tasks within ACI and lifecycle boundaries.

The intent is to establish an explicit "what must be produced" contract that:
- aligns to the existing `agents/capabilities/<domain>/` implementation pattern,
- composes capabilities into repeatable reference workloads,
- enables unit + integration tests that fail fast when infra changes degrade real output production,
- supports nightly autonomic runs with mechanically verifiable outputs suitable for wrap-up and morning status.

---

# 2. Background

SquadOps already contains capability implementations organized by domain rather than role. Example (Data domain):

- `agents/capabilities/data/collect_cycle_snapshot.py`
- `agents/capabilities/data/profile_cycle_metrics.py`
- `agents/capabilities/data/compose_cycle_summary.py`

These modules explicitly describe capabilities such as:
- `data.collect_cycle_snapshot` (snapshot collection/normalization)
- `data.profile_cycle_metrics` (metrics computation + report generation)
- `data.compose_cycle_summary` (compact summary composition)

In parallel, SquadOps is establishing:
- ACI TaskEnvelope as the strict task contract,
- Prefect adapter execution,
- lifecycle hooks and structured event scaffolding.

What is missing is a **declarative contract layer** (discoverable without importing Python) that formalizes:
- capability identity, lifecycle intent, and task typing,
- required inputs and required artifact outputs,
- deterministic acceptance checks,
- reference workloads that serve as repeatable delivery integration tests.

---

# 3. Problem Statements

1. Capabilities are present but **implicit**: there is no normative contract describing required inputs, outputs, artifact paths, and acceptance checks.
2. Infra-level correctness can remain green while **artifact delivery regresses** silently (e.g., missing files, schema drift, path drift, partial writes).
3. There is no canonical mechanism to run a **reference workload** that composes multiple capabilities end-to-end through ACI + Prefect + agent containers.
4. There is no standardized test structure for validating capability delivery at both **unit** and **integration** levels.

---

# 4. Scope

## In Scope
- A normative, repository-level **Capability Contract** format.
- A normative **Reference Workload** format that composes capabilities into an ordered DAG.
- A normative **Workload Runner Protocol** suitable for:
  - integration tests, and/or
  - a minimal internal CLI runner used by tests.
- Deterministic artifact directory structure and acceptance checks.
- A worked example capability contract and a worked example reference workload aligned to the existing `agents/capabilities/data/*` handlers.
- Explicit unit and integration testing requirements that validate contract correctness and end-to-end artifact delivery.

## Not Addressed
- Changes to internal implementation of existing capability handlers (this SIP constrains I/O and artifacts, not algorithmic implementation).
- SOC Ledger persistence and storage backends for structured events (compatibility requirements only).

---

# 5. Design Overview

Capability Contracts and Reference Workloads provide a stable "delivery proof" layer above ACI:

- **ACI** guarantees task envelope integrity and execution boundaries.
- **Capability Contracts** guarantee artifact outputs and acceptance criteria.
- **Reference Workloads** provide repeatable, end-to-end delivery validation runs that can be executed nightly.

This SIP preserves the existing domain-based capabilities layout and extends it with declarative manifests:

```
agents/capabilities/
  data/
    collect_cycle_snapshot.py
    profile_cycle_metrics.py
    compose_cycle_summary.py
    contracts/
      data.collect_cycle_snapshot.yaml
      data.profile_cycle_metrics.yaml
      data.compose_cycle_summary.yaml
  workloads/
    data_cycle_wrapup_smoke.yaml
  schemas/
    capability_contract.schema.json
    workload.schema.json
```

Roles (Lead, Strategy, Dev, QA, Data) remain **eligible executors**, not capability owners. Capability invocation and routing are driven by contract metadata (`task_type`, `allowed_roles`, `preferred_roles`) and runtime availability.

---

# 6. Functional Requirements

## 6.1 Capability Contract (Declarative) Requirements

Each capability intended for runtime invocation MUST have a contract file that declares:

### Identity
- `capability_id` (string, globally unique, dot-namespaced, e.g., `data.collect_cycle_snapshot`)
- `domain` (string; e.g., `data`, `delivery`, `ops`, `product`)
- `contract_version` (string)
- `task_type` (string; ACI routing taxonomy)

### Lifecycle Semantics
- `lifecycle_scope` (enum): `agent` | `cycle` | `pulse` | `task`
- `trigger` (enum): `on_demand` | `cycle_start` | `cycle_end` | `pulse_start` | `pulse_end` | `task_start` | `task_end`

### Execution Eligibility
- `preferred_roles` (list of role names)
- `allowed_roles` (list of role names)

### Inputs and Outputs
- `inputs` (declarative schema-like keys/types; includes required vs optional and defaults)
- `outputs` (declarative schema-like keys/types for returned structured outputs)

### Artifact Requirements
- `artifacts` list with:
  - `artifact_id`
  - `type` (json | md | text | binary | directory)
  - `path_template` (deterministic path; must include `{cycle_id}` and `{capability_id}`)
  - `required` boolean
  - `description`

### Acceptance Checks (Deterministic)
- `acceptance_checks` list with check types that do not require subjective evaluation:
  - `file_exists`
  - `json_schema`
  - `non_empty`
  - `json_field_equals`
  - `md_contains` (bounded, deterministic)
  - `timestamp_within_cycle_window` (if cycle window is provided)

Acceptance checks MUST produce a machine-readable PASS/FAIL with failure reasons.

## 6.2 Contract Discovery and Validation

- Contracts MUST be discoverable without importing the Python handler modules.
- Contracts MUST be validated against a canonical JSON schema:
  - `agents/capabilities/schemas/capability_contract.schema.json`
- Contract validation MUST run in unit tests and CI.

## 6.3 Deterministic Artifact Paths

All capability artifacts MUST be written under a deterministic run root:

- `runs/<cycle_id>/capabilities/<capability_id>/...`

Path templates MUST resolve to paths under that root.

## 6.4 Reference Workload Requirements

Reference workloads MUST be defined as declarative manifests and validated against a canonical schema:

- `agents/capabilities/workloads/<workload_id>.yaml`
- `agents/capabilities/schemas/workload.schema.json`

Each workload MUST declare:
- `workload_id`, `workload_version`, `description`
- `tasks` list where each task includes:
  - `task_id`
  - `capability_id`
  - `inputs` (templated where necessary)
  - `depends_on` (list; optional; defines a DAG)
  - executor routing hints (optional): `preferred_roles_override`
- workload-level `acceptance_checks` (optional)
- workload-level "headline metrics" keys for wrap-up summaries:
  - `last_cycle_status`
  - `autonomic_run_time_seconds`
  - `wrapup_score`

## 6.5 Workload Runner Protocol (Normative Algorithm)

A Workload Runner MUST implement the following steps:

1. Load workload manifest and validate against workload schema.
2. Resolve each referenced capability contract and validate against contract schema.
3. Resolve executors (role/agent selection) using:
   - workload overrides, then
   - contract preferred/allowed roles, then
   - runtime availability (agent READY state).
4. Construct ACI TaskEnvelope for each workload task:
   - `task_type` MUST come from contract `task_type`.
   - TaskEnvelope `inputs` MUST come only from workload task `inputs`.
5. Submit tasks through the strict ACI path:
   - Runtime API task creation endpoint (preferred), or
   - Prefect adapter submission when the workload is configured to use Prefect execution.
6. Await completion and collect TaskResult outputs.
7. Verify artifacts exist at contract-declared resolved paths.
8. Execute acceptance checks per contract and workload.
9. Emit a `WorkloadRunReport` artifact under:
   - `runs/<cycle_id>/workloads/<workload_id>/workload_run_report.json`
10. Return PASS/FAIL for test harness gating.

## 6.6 Testing Requirements (Unit + Integration)

### Unit Tests (Required)
Unit tests MUST cover:

1. Contract schema validation
   - valid contracts pass
   - missing required fields fail
   - invalid lifecycle_scope/trigger values fail
2. Workload schema validation
   - valid workload passes
   - missing task capability_id fails
   - invalid DAG references fail
3. Path template resolution
   - resolves deterministically under `runs/<cycle_id>/capabilities/<capability_id>/`
4. Acceptance check engine behavior (deterministic)
   - file_exists
   - non_empty
   - json_field_equals
   - json_schema (schema reference resolution)
5. TaskEnvelope construction for workload tasks
   - task_type is contract-driven
   - inputs come exclusively from workload inputs (no metadata leakage)

### Integration Tests (Required)
Integration tests MUST validate real end-to-end behavior using:
- agent Docker containers (the deployed runtime boundary), and
- the runtime API + queue transport + Prefect adapter (as applicable).

At minimum, the suite MUST include:

1. **End-to-End Workload Smoke (ACI + agents)**
   - submit workload tasks
   - tasks delivered via queue
   - agents execute capabilities
   - artifacts produced and validated
   - WorkloadRunReport produced
2. **Prefect-backed Workload Smoke (Prefect adapter)**
   - submit via Prefect adapter and confirm TaskResults
   - verify artifacts and acceptance
   - ensure lineage fields are preserved (as required by ACI)
3. **Regression Gate**
   - a failing acceptance check must fail the integration test deterministically

---

# 7. Non-Functional Requirements

1. **Determinism:** Acceptance checks must not rely on subjective evaluation.
2. **Portability:** Contracts and workloads must not embed provider-specific infra details.
3. **Extensibility:** New domains/capabilities can be added by adding contract + handler, without changing runner semantics.
4. **Reliability:** Workload runner must produce a report even on partial failure (report includes failures).
5. **Performance:** Contract and workload validation must complete quickly (bounded), excluding task execution time.

---

# 8. API Surface (If Applicable)

This SIP does not introduce a new external API. It relies on the existing strict ACI Runtime API task submission and status surfaces already established for 0.8.x.

---

# 9. Implementation Considerations

1. **Alignment with existing handlers**
   - Contract `capability_id` values MUST match the identifiers described by the existing handler docstrings (Data domain shown in Background).
2. **Task typing**
   - `task_type` MUST be stable and used for routing/metrics aggregation.
3. **Artifact conventions**
   - Capability outputs must remain deterministic even as prompts/lifecycle/backends evolve.
4. **Agent container compatibility**
   - This SIP does not require capability ownership by role; any agent may execute a capability if allowed by contract.
5. **Nightly cycles**
   - Reference workloads provide a stable "always-run" proof point that protects delivery while infra evolves.

---

# 10. Executive Summary — What Must Be Built

- Capability contract JSON schema: `agents/capabilities/schemas/capability_contract.schema.json`
- Workload manifest JSON schema: `agents/capabilities/schemas/workload.schema.json`
- Contract manifests for existing data capabilities:
  - `data.collect_cycle_snapshot`
  - `data.profile_cycle_metrics`
  - `data.compose_cycle_summary`
- A reference workload manifest:
  - `agents/capabilities/workloads/data_cycle_wrapup_smoke.yaml`
- A workload runner usable by integration tests (runner may be CLI or test harness)
- Acceptance check engine + deterministic artifact verification
- Unit tests for schema/validation/path/acceptance logic
- Integration tests that run against agent Docker containers and validate artifact outputs

---

# 11. Definition of Done

- [ ] Contract schema exists and CI validates all contracts against it.
- [ ] Workload schema exists and CI validates all workloads against it.
- [ ] Contracts exist (and validate) for:
  - [ ] `data.collect_cycle_snapshot`
  - [ ] `data.profile_cycle_metrics`
  - [ ] `data.compose_cycle_summary`
- [ ] `data_cycle_wrapup_smoke` workload exists (and validates).
- [ ] Unit tests exist and pass for:
  - [ ] contract/workload schema validation
  - [ ] acceptance check engine
  - [ ] deterministic path resolution
  - [ ] TaskEnvelope construction rules
- [ ] Integration tests exist and pass for:
  - [ ] end-to-end workload execution against agent Docker containers (ACI path)
  - [ ] Prefect adapter workload execution
  - [ ] deterministic failure behavior when acceptance checks fail
- [ ] WorkloadRunReport is emitted on success and on failure, and contains:
  - [ ] last_cycle_status
  - [ ] autonomic_run_time_seconds
  - [ ] wrapup_score

---

# 12. Appendix

## 12.1 Worked Example — Capability Contract (Aligned to Existing Data Handlers)

**File:** `agents/capabilities/data/contracts/data.collect_cycle_snapshot.yaml`

```yaml
capability_id: data.collect_cycle_snapshot
domain: data
contract_version: "1.0"
task_type: data_collect
lifecycle_scope: cycle
trigger: cycle_end

preferred_roles: [Data]
allowed_roles: [Data, Lead]

inputs:
  cycle_id: { type: string, required: true }
  runtime_api_url: { type: string, required: true }
  output_dir:
    type: string
    required: false
    default: "runs/{cycle_id}/capabilities/{capability_id}"

outputs:
  snapshot_path: { type: string, required: true }

artifacts:
  - artifact_id: cycle_snapshot_json
    type: json
    required: true
    path_template: "runs/{cycle_id}/capabilities/{capability_id}/cycle_snapshot.json"
    description: "Normalized snapshot of cycle execution state."

acceptance_checks:
  - id: snapshot_exists
    type: file_exists
    target: "runs/{cycle_id}/capabilities/{capability_id}/cycle_snapshot.json"
  - id: snapshot_non_empty
    type: non_empty
    target: "runs/{cycle_id}/capabilities/{capability_id}/cycle_snapshot.json"
  - id: snapshot_cycle_id_matches
    type: json_field_equals
    target: "runs/{cycle_id}/capabilities/{capability_id}/cycle_snapshot.json"
    field: "cycle_id"
    expected: "{cycle_id}"
```

## 12.2 Worked Example — Reference Workload (Data Wrap-up Smoke)

**File:** `agents/capabilities/workloads/data_cycle_wrapup_smoke.yaml`

```yaml
workload_id: data_cycle_wrapup_smoke
workload_version: "1.0"
description: "Minimal end-to-end workload validating snapshot + metrics + summary artifact delivery."

tasks:
  - task_id: snapshot
    capability_id: data.collect_cycle_snapshot
    inputs:
      runtime_api_url: "{runtime_api_url}"

  - task_id: metrics
    capability_id: data.profile_cycle_metrics
    depends_on: [snapshot]
    inputs:
      snapshot_path: "runs/{cycle_id}/capabilities/data.collect_cycle_snapshot/cycle_snapshot.json"

  - task_id: summary
    capability_id: data.compose_cycle_summary
    depends_on: [metrics]
    inputs:
      snapshot_path: "runs/{cycle_id}/capabilities/data.collect_cycle_snapshot/cycle_snapshot.json"
      metrics_path: "runs/{cycle_id}/capabilities/data.profile_cycle_metrics/cycle_metrics.json"

headline_metrics:
  last_cycle_status: derived
  autonomic_run_time_seconds: measured
  wrapup_score: derived

acceptance_checks:
  - id: summary_exists
    type: file_exists
    target: "runs/{cycle_id}/capabilities/data.compose_cycle_summary/cycle_summary.json"
```
