---
sip_uid: 01KEM71ECNVQ8381E1Z63V7F5S
sip_number: null
title: Capability Contracts + Reference Workloads for Delivery-Grade Artifact Proof
status: proposed
author: Framework Committee
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-29T14:00:00Z'
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
- follows **Hexagonal Architecture** (Ports and Adapters) patterns established in SIP-0056 and SIP-0057,
- composes capabilities into repeatable reference workloads,
- enables unit + integration tests that fail fast when infra changes degrade real output production,
- supports nightly autonomic runs with mechanically verifiable outputs suitable for wrap-up and morning status.

This SIP applies **Domain-Driven Design (DDD)** principles to capability management, separating the domain logic (contracts, validation, acceptance checks) from infrastructure concerns (filesystem access, task execution backends).

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

In parallel, SquadOps has established:
- ACI TaskEnvelope as the strict task contract,
- Hexagonal Architecture with Ports and Adapters (SIP-0056: Queue Transport, SIP-0057: Layered Prompts),
- Domain-Driven Design principles separating domain logic from infrastructure,
- Prefect adapter execution,
- lifecycle hooks and structured event scaffolding.

What is missing is a **declarative contract layer** (discoverable without importing Python) that formalizes:
- capability identity, lifecycle intent, and task typing,
- required inputs and required artifact outputs,
- deterministic acceptance checks,
- reference workloads that serve as repeatable delivery integration tests.

---

# 3. Revision Notes (v1.2)

This revision incorporates clarifications to reduce implementation ambiguity:

### v1.1 Changes

| Change | Reasoning |
|--------|-----------|
| **A) Separated Delivery Contract from Execution Policy** | Contract fields now partitioned into "Delivery Expectations" (inputs/outputs/artifacts/acceptance) vs "Execution Policy Metadata" (task_type, roles, lifecycle). Prevents contract drift by clarifying which fields are proof-of-delivery vs runtime routing hints. |
| **B) Defined v1 Schema Subset for Inputs/Outputs** | Added normative statement: v1 supports primitives only (string, number, boolean) with required/optional/default/description. No nested objects or arrays. Removes "schema-like" ambiguity. |
| **C) Added AcceptanceContext Definition** | Canonical context for template resolution: `cycle_id`, `capability_id`, `workload_id`, `run_root`, `vars.*`. Makes acceptance checks deterministic and portable. |
| **D) Added Chroot Path Enforcement** | Security rule: resolved artifact paths MUST be inside `run_root`. Absolute paths and traversal attempts rejected. Prevents path escape vulnerabilities. |
| **E) Defined Workload DAG Failure Semantics** | Default behavior is fail-fast on task or validation failure. WorkloadRunReport still emitted with partial results. Integration tests have deterministic expectations. |
| **F) Fixed WorkloadRunReport Schema** | Report is the delivery proof artifact—now has a stable, versioned schema with required fields for run metadata, per-task records, failures, and headline metrics. |
| **G) Clarified CapabilityExecutor Relationship** | CapabilityExecutor is a domain-specific adapter that internally uses QueuePort (SIP-0056), not a competing abstraction. Keeps hexagonal boundaries clean. |
| **H) Added v1 MVP Requirements** | Explicit 0.8.6 baseline: FileSystemCapabilityRepository required, ACICapabilityExecutor required, PrefectCapabilityExecutor optional. Three core acceptance checks required. |

### v1.2 Changes

| Change | Reasoning |
|--------|-----------|
| **I) Fixed run_root vs runs/ ambiguity** | `run_root` is now the base directory (e.g., `/var/squadops`) containing `runs/`. Templates start with `runs/...` and resolve correctly. |
| **J) Path traversal rule segment-aware** | Clarified `..` rejection applies to path segments only, not substrings. Pseudocode marked illustrative. |
| **K) Symlink policy** | Added: symlinks permitted only if resolved target remains within `run_root`. |
| **L) WorkloadRunReport schema wrapper removed** | Schema example now flat (no `workload_run_report:` wrapper) to match JSON example. |
| **M) Path refs are relative** | Clarified `task_result_ref` and `artifact_refs` are relative to `run_root`. |
| **N) Acceptance checks: supported vs required** | Added sentence clarifying v1 required checks vs optional future checks. |
| **O) Fail-fast wording tightened** | Clarified fail-fast means "no further tasks submitted" while acceptance checks are always fully evaluated. |
| **P) continue_on_failure independent branches** | Added: with `continue_on_failure`, independent DAG branches may still run. |
| **Q) CapabilityExecutor simplified** | Removed `context` parameter from `submit()`—executor is transport only; runner handles context. |

---

# 4. Problem Statements

1. Capabilities are present but **implicit**: there is no normative contract describing required inputs, outputs, artifact paths, and acceptance checks.
2. Infra-level correctness can remain green while **artifact delivery regresses** silently (e.g., missing files, schema drift, path drift, partial writes).
3. There is no canonical mechanism to run a **reference workload** that composes multiple capabilities end-to-end through ACI + Prefect + agent containers.
4. There is no standardized test structure for validating capability delivery at both **unit** and **integration** levels.

---

# 5. Scope

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

# 6. Strategic Domain Design (DDD)

## 6.1 Bounded Context: Capability Delivery

- **Aggregate Root:** `CapabilityContract` — The single source of truth for a capability's inputs, outputs, artifacts, and acceptance criteria.
- **Entity:** `Workload` — An ordered composition of capability invocations forming a DAG.
- **Value Object:** `AcceptanceResult` — Immutable PASS/FAIL outcome with failure reasons.
- **Value Object:** `WorkloadRunReport` — Immutable execution summary with headline metrics and per-task records.
- **Value Object:** `AcceptanceContext` — Immutable context for template resolution and acceptance evaluation.
- **Domain Service:** `WorkloadRunner` — Stateless orchestration logic for workload execution.
- **Domain Service:** `AcceptanceCheckEngine` — Stateless validation logic for deterministic checks.

## 6.2 Core Principles

1. **Contracts define delivery expectations, not implementation.** Handler internals remain opaque to the contract layer.
2. **Deterministic Acceptance:** Given the same artifacts and contract, acceptance checks must produce identical results.
3. **Fail-Fast Sovereignty:** If a contract or workload fails schema validation, execution must halt immediately.
4. **Path Containment:** All artifact paths must resolve within the run root. No path escape is permitted.

---

# 7. Technical Architecture (Hexagonal)

## 7.1 Layered Structure

```
# Domain Layer — Pure business logic, no I/O
src/squadops/capabilities/
├── __init__.py
├── models.py              # CapabilityContract, Workload, WorkloadRunReport, AcceptanceResult, AcceptanceContext
├── exceptions.py          # ContractValidationError, AcceptanceCheckFailedError, WorkloadExecutionError, PathEscapeError
├── runner.py              # WorkloadRunner domain service
├── acceptance.py          # AcceptanceCheckEngine domain service
└── manifests/             # Declarative contracts and workloads
    ├── schemas/
    │   ├── capability_contract.schema.json
    │   ├── workload.schema.json
    │   └── workload_run_report.schema.json
    ├── contracts/
    │   └── data/
    │       ├── collect_cycle_snapshot.yaml
    │       ├── profile_cycle_metrics.yaml
    │       └── compose_cycle_summary.yaml
    └── workloads/
        └── data_cycle_wrapup_smoke.yaml

# Ports Layer — Abstract interfaces (driven ports)
src/squadops/ports/capabilities/
├── __init__.py
├── repository.py          # CapabilityRepository — contract/workload discovery
└── executor.py            # CapabilityExecutor — task submission abstraction

# Adapters Layer — Concrete implementations
adapters/capabilities/
├── __init__.py
├── filesystem.py          # FileSystemCapabilityRepository
├── aci_executor.py        # ACICapabilityExecutor (uses QueuePort from SIP-0056)
├── prefect_executor.py    # PrefectCapabilityExecutor (optional in v1)
└── factory.py             # Config-driven adapter creation
```

## 7.2 Port Interfaces

### CapabilityRepository (Driven Port)

Defines the contract for discovering and loading capability contracts and workloads. Abstracts storage so the Domain logic is isolated from filesystem or remote storage.

```python
class CapabilityRepository(ABC):
    @abstractmethod
    def get_contract(self, capability_id: str) -> CapabilityContract: ...

    @abstractmethod
    def get_workload(self, workload_id: str) -> Workload: ...

    @abstractmethod
    def list_contracts(self, domain: str | None = None) -> list[CapabilityContract]: ...

    @abstractmethod
    def validate_all(self) -> bool: ...
```

### CapabilityExecutor (Driven Port)

Defines the contract for submitting tasks and retrieving results. Abstracts the execution backend (ACI queue, Prefect, mock).

**Architectural Note:** `CapabilityExecutor` is a thin transport wrapper within the Capability Delivery bounded context. The `ACICapabilityExecutor` implementation internally uses `QueuePort` (SIP-0056) for task submission. This is composition, not competition—the executor handles transport while `WorkloadRunner` handles template resolution, acceptance context construction, and acceptance evaluation.

```python
class CapabilityExecutor(ABC):
    @abstractmethod
    async def submit(self, envelope: TaskEnvelope) -> str: ...  # Returns task_id

    @abstractmethod
    async def await_result(self, task_id: str, timeout: float) -> TaskResult: ...

    @abstractmethod
    async def get_status(self, task_id: str) -> TaskStatus: ...
```

## 7.3 Adapter Implementations

- **FileSystemCapabilityRepository:** macOS/POSIX implementation for local development. Loads YAML contracts from `manifests/contracts/` and validates against JSON schemas.
- **ACICapabilityExecutor:** Submits tasks via `QueuePort` (SIP-0056), integrates with existing ACI task flow. Required for v1.
- **PrefectCapabilityExecutor:** Submits tasks via Prefect adapter for orchestrated execution. Optional for v1.

Roles (Lead, Strategy, Dev, QA, Data) remain **eligible executors**, not capability owners. Capability invocation and routing are driven by contract metadata (`task_type`, `allowed_roles`, `preferred_roles`) and runtime availability.

---

# 8. Functional Requirements

## 8.1 Capability Contract (Declarative) Requirements

Each capability intended for runtime invocation MUST have a contract file that declares fields partitioned into two categories:

### 8.1.1 Delivery Expectations (Proof-of-Delivery)

These fields define what the capability MUST produce and how to verify it.

#### Identity
- `capability_id` (string, globally unique, dot-namespaced, e.g., `data.collect_cycle_snapshot`)
- `domain` (string; e.g., `data`, `delivery`, `ops`, `product`)
- `contract_version` (string, semver)

#### Inputs (v1 Schema)
- `inputs` — Declarative input specification. **v1 Constraint:** Only primitive types are supported:
  - `type`: One of `string`, `number`, `boolean`
  - `required`: boolean (default: `false`)
  - `default`: value matching type (optional, only if `required: false`)
  - `description`: string (optional but recommended)
  - **No nested objects or arrays in v1.** Complex structures must be passed as JSON-encoded strings.

#### Outputs (v1 Schema)
- `outputs` — Declarative output specification. Same v1 constraints as inputs:
  - `type`: One of `string`, `number`, `boolean`
  - `required`: boolean
  - `description`: string (optional)

#### Artifact Requirements
- `artifacts` list with:
  - `artifact_id` (string, unique within contract)
  - `type` (enum: `json` | `md` | `text` | `binary` | `directory`)
  - `path_template` (deterministic path; see Section 8.3 for template rules)
  - `required` (boolean)
  - `description` (string)

#### Acceptance Checks (Deterministic)
- `acceptance_checks` list with check types that do not require subjective evaluation:
  - `file_exists` — Target path exists
  - `non_empty` — Target file has size > 0
  - `json_field_equals` — JSON field at path equals expected value
  - `json_schema` — Target validates against referenced schema
  - `md_contains` — Markdown contains specified string (bounded, deterministic)
  - `timestamp_within_cycle_window` — Timestamp field within cycle bounds (if provided)

Acceptance checks MUST produce a machine-readable PASS/FAIL with failure reasons. The engine MUST support at least the v1 required checks (`file_exists`, `non_empty`, `json_field_equals`); other check types MAY be implemented in later versions.

### 8.1.2 Execution Policy Metadata (Runtime Routing)

These fields guide task routing and lifecycle integration but are NOT part of delivery proof.

#### Task Typing
- `task_type` (string; ACI routing taxonomy, e.g., `data_collect`, `data_profile`)

#### Lifecycle Semantics
- `lifecycle_scope` (enum): `agent` | `cycle` | `pulse` | `task`
- `trigger` (enum): `on_demand` | `cycle_start` | `cycle_end` | `pulse_start` | `pulse_end` | `task_start` | `task_end`

#### Execution Eligibility
- `preferred_roles` (list of role names; routing hint, not constraint)
- `allowed_roles` (list of role names; hard constraint on eligibility)

## 8.2 AcceptanceContext (Template Resolution)

All template resolution and acceptance check execution MUST use a canonical `AcceptanceContext`. This ensures deterministic, portable evaluation.

### 8.2.1 Required Context Fields

| Field | Type | Description |
|-------|------|-------------|
| `cycle_id` | string | Current cycle identifier |
| `capability_id` | string | Capability being executed |
| `workload_id` | string | Workload identifier (empty string if standalone) |
| `run_root` | string | Absolute path to the base directory containing `runs/` (e.g., `/var/squadops`) |
| `vars` | dict | Runtime variables (e.g., `runtime_api_url`, `agent_id`) |

### 8.2.2 Template Variable Syntax

Templates use `{variable}` syntax. Allowed variables:

- `{cycle_id}` — Resolves to `context.cycle_id`
- `{capability_id}` — Resolves to `context.capability_id`
- `{workload_id}` — Resolves to `context.workload_id`
- `{vars.<key>}` — Resolves to `context.vars[key]`

**Example:**
```yaml
path_template: "runs/{cycle_id}/capabilities/{capability_id}/output.json"
# With cycle_id="cycle-001", capability_id="data.collect_cycle_snapshot"
# Resolves to: "runs/cycle-001/capabilities/data.collect_cycle_snapshot/output.json"
```

Unknown variables MUST cause template resolution to fail with a descriptive error.

## 8.3 Deterministic Artifact Paths (Chroot Enforcement)

All capability artifacts MUST be written under a deterministic run root:

- `{run_root}/runs/<cycle_id>/capabilities/<capability_id>/...`

### 8.3.1 Path Security Rules (Normative)

1. **Containment:** After template resolution and path normalization, the resolved absolute path MUST be inside `{run_root}`. Paths that escape the run root MUST cause validation failure with `PathEscapeError`.

2. **No Absolute Paths in Templates:** Path templates MUST be relative. Absolute paths (starting with `/`) in templates are rejected.

3. **No Traversal:** Templates containing `..` as a path segment (e.g., `foo/../bar`) are rejected before resolution. Filenames containing `..` as a substring (e.g., `file..name.txt`) are permitted.

4. **Normalization:** After resolution, paths are normalized (resolve `.`, `..`) and checked against run root containment.

5. **Symlinks:** Symlinks are permitted only if the final resolved target remains within `run_root`; otherwise `PathEscapeError` is raised.

**Validation pseudocode (illustrative):**
```python
def validate_resolved_path(path_template: str, context: AcceptanceContext) -> Path:
    if path_template.startswith('/'):
        raise PathEscapeError("Absolute paths not allowed in templates")
    # Check for '..' as a path segment, not substring
    if any(seg == '..' for seg in path_template.split('/')):
        raise PathEscapeError("Path traversal not allowed in templates")

    resolved = resolve_template(path_template, context)
    absolute = (context.run_root / resolved).resolve()

    if not absolute.is_relative_to(context.run_root):
        raise PathEscapeError(f"Resolved path escapes run_root: {absolute}")

    return absolute
```

## 8.4 Contract Discovery and Validation

- Contracts MUST be discoverable via the `CapabilityRepository` port without importing Python handler modules.
- Contracts MUST be validated against a canonical JSON schema:
  - `src/squadops/capabilities/manifests/schemas/capability_contract.schema.json`
- The `FileSystemCapabilityRepository` adapter handles schema validation on load.
- Contract validation MUST run in unit tests and CI.

## 8.5 Reference Workload Requirements

Reference workloads MUST be defined as declarative manifests and validated against a canonical schema:

- `src/squadops/capabilities/manifests/workloads/<workload_id>.yaml`
- `src/squadops/capabilities/manifests/schemas/workload.schema.json`

Each workload MUST declare:
- `workload_id`, `workload_version`, `description`
- `tasks` list where each task includes:
  - `task_id`
  - `capability_id`
  - `inputs` (templated where necessary, using AcceptanceContext variables)
  - `depends_on` (list; optional; defines a DAG)
  - executor routing hints (optional): `preferred_roles_override`
- workload-level `acceptance_checks` (optional)
- workload-level `headline_metrics` configuration

### 8.5.1 Workload DAG Failure Semantics (Normative)

The v1 WorkloadRunner implements **fail-fast** behavior for task submission:

1. **Schema Validation Failure:** If contract or workload schema validation fails, execution halts immediately. No tasks are submitted.

2. **Task Execution Failure:** If any task fails (error, timeout, or rejected), **no further tasks are submitted**. Tasks with unsatisfied `depends_on` are marked `SKIPPED`. Note: fail-fast applies to task submission only; acceptance checks are always fully evaluated (see below).

3. **Acceptance Check Evaluation:** Acceptance checks are evaluated for **all produced artifacts** and **all declared checks**—there is no short-circuit on acceptance failure. If any check fails, the workload is marked `FAILED`.

4. **Partial Results:** On any failure, `WorkloadRunReport` is still emitted containing:
   - Completed task results
   - Skipped task records
   - Failure reasons with stable error codes

5. **Optional Extension:** Workloads MAY include `continue_on_failure: true` to override fail-fast for task execution (not schema validation). When enabled:
   - Failed tasks are recorded but execution continues
   - Tasks not directly or transitively dependent on failed tasks may still run
   - Dependent tasks are skipped
   - Final status reflects all failures

## 8.6 WorkloadRunReport Schema (Normative)

The `WorkloadRunReport` is the delivery proof artifact. It MUST conform to a stable, versioned schema.

### 8.6.1 Required Fields

```yaml
# WorkloadRunReport Schema v1.0 (top-level fields, no wrapper)

# --- Run Metadata (required) ---
report_version: "1.0"
cycle_id: string
workload_id: string
workload_version: string
started_at: ISO8601 timestamp
ended_at: ISO8601 timestamp
duration_seconds: number
executor_backend: "aci" | "prefect" | "mock"
status: "PASSED" | "FAILED" | "PARTIAL"

# --- Per-Task Records (required) ---
tasks:
  - task_id: string
    capability_id: string
    resolved_executor: { role: string, agent_id: string | null }
    status: "COMPLETED" | "FAILED" | "SKIPPED" | "TIMEOUT"
    started_at: ISO8601 timestamp | null
    ended_at: ISO8601 timestamp | null
    duration_seconds: number | null
    task_result_ref: string | null  # Relative path to TaskResult artifact
    artifact_refs: [string]         # Relative paths to produced artifacts
    acceptance_results:
      - check_id: string
        status: "PASS" | "FAIL"
        reason: string | null

# --- Failures (required, may be empty) ---
failures:
  - code: string           # Stable error code (e.g., "TASK_TIMEOUT", "ACCEPTANCE_FAILED")
    task_id: string | null
    check_id: string | null
    message: string
    timestamp: ISO8601 timestamp

# --- Headline Metrics (required) ---
headline_metrics:
  last_cycle_status: "PASSED" | "FAILED" | "PARTIAL"
  autonomic_run_time_seconds: number
  wrapup_score: number | null  # Derived metric, null if not computable
  tasks_completed: number
  tasks_failed: number
  tasks_skipped: number
  acceptance_checks_passed: number
  acceptance_checks_failed: number
```

**Path References:** All path fields (`task_result_ref`, `artifact_refs`) are stored as paths **relative to `run_root`**. Validators resolve them under `run_root` for containment checks.

### 8.6.2 Report Location

Reports MUST be written to:
- `{run_root}/runs/<cycle_id>/workloads/<workload_id>/workload_run_report.json`

## 8.7 Workload Runner Protocol (Domain Service)

The `WorkloadRunner` is a **stateless Domain Service** that depends on:
- `CapabilityRepository` port for contract/workload discovery
- `CapabilityExecutor` port for task submission
- `AcceptanceCheckEngine` domain service for validation

This design enables isolated unit testing with mock ports. The runner MUST implement the following steps:

1. Load workload manifest and validate against workload schema.
2. Resolve each referenced capability contract and validate against contract schema.
3. Construct `AcceptanceContext` with cycle_id, workload_id, run_root, and vars.
4. Resolve executors (role/agent selection) using:
   - workload overrides, then
   - contract preferred/allowed roles, then
   - runtime availability (agent READY state).
5. Construct ACI TaskEnvelope for each workload task:
   - `task_type` MUST come from contract `task_type`.
   - TaskEnvelope `inputs` MUST come only from workload task `inputs` (resolved via AcceptanceContext).
6. Submit tasks through the strict ACI path via `CapabilityExecutor`:
   - `ACICapabilityExecutor` internally uses `QueuePort` (SIP-0056).
   - `PrefectCapabilityExecutor` uses Prefect adapter (optional in v1).
7. Await completion and collect TaskResult outputs.
8. Verify artifacts exist at contract-declared resolved paths (with chroot validation).
9. Execute acceptance checks per contract and workload.
10. Emit `WorkloadRunReport` artifact (always, even on failure).
11. Return PASS/FAIL for test harness gating.

## 8.8 Testing Requirements (Unit + Integration)

### Unit Tests (Domain Isolation - Required)

Unit tests MUST verify domain logic **without filesystem or network access**. Use mock `CapabilityRepository` and `CapabilityExecutor` ports.

Unit tests MUST cover:

1. Contract schema validation
   - valid contracts pass
   - missing required fields fail
   - invalid lifecycle_scope/trigger values fail
   - v1 input/output type constraints enforced
2. Workload schema validation
   - valid workload passes
   - missing task capability_id fails
   - invalid DAG references fail
3. AcceptanceContext construction and template resolution
   - all required fields present
   - unknown variables cause error
   - `{vars.<key>}` resolution works
4. Path template resolution with chroot enforcement
   - resolves deterministically under run_root
   - absolute paths rejected
   - traversal attempts rejected
   - escape attempts caught
5. Acceptance check engine behavior (deterministic)
   - file_exists
   - non_empty
   - json_field_equals
6. TaskEnvelope construction for workload tasks
   - task_type is contract-driven
   - inputs come exclusively from workload inputs (no metadata leakage)
7. WorkloadRunReport generation
   - schema compliance
   - partial results on failure
   - all required fields present

### Integration Tests (Adapter Verification - Required)

Integration tests MUST verify adapter implementations against real infrastructure:
- `FileSystemCapabilityRepository` against actual manifest files
- `ACICapabilityExecutor` against agent Docker containers via `QueuePort` (SIP-0056)
- `PrefectCapabilityExecutor` against Prefect runtime (optional in v1)

At minimum, the suite MUST include:

1. **End-to-End Workload Smoke (ACI + agents)**
   - submit workload tasks
   - tasks delivered via queue
   - agents execute capabilities
   - artifacts produced and validated
   - WorkloadRunReport produced with correct schema
2. **Prefect-backed Workload Smoke (Prefect adapter)** — Optional in v1
   - submit via Prefect adapter and confirm TaskResults
   - verify artifacts and acceptance
   - ensure lineage fields are preserved (as required by ACI)
3. **Regression Gate**
   - a failing acceptance check must fail the integration test deterministically
4. **Failure Semantics Verification**
   - verify fail-fast behavior on task failure
   - verify partial results in WorkloadRunReport
   - verify SKIPPED status for dependent tasks

---

# 9. Non-Functional Requirements

1. **Determinism:** Acceptance checks must not rely on subjective evaluation.
2. **Portability:** Contracts and workloads must not embed provider-specific infra details.
3. **Extensibility:** New domains/capabilities can be added by adding contract + handler, without changing runner semantics.
4. **Reliability:** Workload runner must produce a report even on partial failure (report includes failures).
5. **Performance:** Contract and workload validation must complete quickly (bounded), excluding task execution time.
6. **Security:** Path containment enforced; no artifact escape from run root.

---

# 10. API Surface (If Applicable)

This SIP does not introduce a new external API. It relies on the existing strict ACI Runtime API task submission and status surfaces already established for 0.8.x.

---

# 11. Implementation Considerations

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

# 12. v1 MVP Requirements (0.8.6 Baseline)

This section defines the minimum implementation required for 0.8.6 release. Items marked "optional" may be deferred to 0.8.7+.

### Required for 0.8.6

| Component | Requirement |
|-----------|-------------|
| **FileSystemCapabilityRepository** | Required. Local YAML loading with schema validation. |
| **ACICapabilityExecutor** | Required. Task submission via QueuePort. |
| **AcceptanceCheckEngine** | Required with checks: `file_exists`, `non_empty`, `json_field_equals` |
| **WorkloadRunner** | Required with fail-fast semantics. |
| **WorkloadRunReport** | Required with v1.0 schema. |
| **Path chroot enforcement** | Required. |
| **AcceptanceContext** | Required with all specified fields. |
| **Data domain contracts** | Required: `data.collect_cycle_snapshot`, `data.profile_cycle_metrics`, `data.compose_cycle_summary` |
| **Reference workload** | Required: `data_cycle_wrapup_smoke` |

### Optional (May Defer to 0.8.7+)

| Component | Notes |
|-----------|-------|
| **PrefectCapabilityExecutor** | Optional. ACI path sufficient for v1. |
| **Acceptance checks:** `json_schema`, `md_contains`, `timestamp_within_cycle_window` | Optional. Core three checks sufficient for v1. |
| **`continue_on_failure` workload flag** | Optional. Fail-fast default sufficient for v1. |
| **Additional domain contracts** | Optional. Data domain proves the pattern. |

---

# 13. Executive Summary — What Must Be Built

### Domain Layer (`src/squadops/capabilities/`)
- `models.py` — Frozen dataclasses: `CapabilityContract`, `Workload`, `WorkloadRunReport`, `AcceptanceResult`, `AcceptanceContext`
- `exceptions.py` — Domain exceptions including `PathEscapeError`
- `runner.py` — `WorkloadRunner` domain service
- `acceptance.py` — `AcceptanceCheckEngine` domain service
- `manifests/schemas/capability_contract.schema.json`
- `manifests/schemas/workload.schema.json`
- `manifests/schemas/workload_run_report.schema.json`
- `manifests/contracts/data/*.yaml` — Contracts for data capabilities
- `manifests/workloads/data_cycle_wrapup_smoke.yaml`

### Ports Layer (`src/squadops/ports/capabilities/`)
- `repository.py` — `CapabilityRepository` abstract interface
- `executor.py` — `CapabilityExecutor` abstract interface

### Adapters Layer (`adapters/capabilities/`)
- `filesystem.py` — `FileSystemCapabilityRepository`
- `aci_executor.py` — `ACICapabilityExecutor` (integrates with SIP-0056 QueuePort)
- `prefect_executor.py` — `PrefectCapabilityExecutor` (optional in v1)
- `factory.py` — Config-driven adapter creation

### Tests
- Unit tests for domain logic with mock ports
- Integration tests against agent Docker containers

---

# 14. Definition of Done

### Domain Layer
- [ ] `CapabilityContract`, `Workload`, `WorkloadRunReport`, `AcceptanceResult`, `AcceptanceContext` models implemented as frozen dataclasses
- [ ] `WorkloadRunner` domain service implements the normative algorithm with fail-fast semantics
- [ ] `AcceptanceCheckEngine` domain service implements: `file_exists`, `non_empty`, `json_field_equals`
- [ ] Path chroot enforcement implemented with `PathEscapeError`
- [ ] Contract schema exists at `src/squadops/capabilities/manifests/schemas/`
- [ ] Workload schema exists at `src/squadops/capabilities/manifests/schemas/`
- [ ] WorkloadRunReport schema exists at `src/squadops/capabilities/manifests/schemas/`

### Port Interfaces
- [ ] `CapabilityRepository` port defined in `src/squadops/ports/capabilities/`
- [ ] `CapabilityExecutor` port defined in `src/squadops/ports/capabilities/`

### Adapters
- [ ] `FileSystemCapabilityRepository` implemented in `adapters/capabilities/`
- [ ] `ACICapabilityExecutor` implemented (integrates with QueuePort from SIP-0056)

### Contracts and Workloads
- [ ] Contracts exist (and validate) for:
  - [ ] `data.collect_cycle_snapshot`
  - [ ] `data.profile_cycle_metrics`
  - [ ] `data.compose_cycle_summary`
- [ ] `data_cycle_wrapup_smoke` workload exists (and validates)

### Testing
- [ ] Unit tests pass for domain logic with mock ports:
  - [ ] contract/workload schema validation
  - [ ] AcceptanceContext construction and template resolution
  - [ ] acceptance check engine (file_exists, non_empty, json_field_equals)
  - [ ] path chroot enforcement
  - [ ] TaskEnvelope construction rules
  - [ ] WorkloadRunReport schema compliance
- [ ] Integration tests pass for adapter verification:
  - [ ] FileSystemCapabilityRepository against real manifests
  - [ ] ACICapabilityExecutor against agent Docker containers
  - [ ] deterministic failure behavior when acceptance checks fail
  - [ ] partial results in WorkloadRunReport on failure

### Artifacts
- [ ] WorkloadRunReport is emitted on success and on failure with v1.0 schema:
  - [ ] All required run metadata fields present
  - [ ] Per-task records with acceptance_results
  - [ ] Failures array with stable error codes
  - [ ] Headline metrics computed

---

# 15. Appendix

## 15.1 Worked Example — Capability Contract (Aligned to Existing Data Handlers)

**File:** `src/squadops/capabilities/manifests/contracts/data/collect_cycle_snapshot.yaml`

```yaml
capability_id: data.collect_cycle_snapshot
domain: data
contract_version: "1.0"

# === Execution Policy Metadata (Routing) ===
task_type: data_collect
lifecycle_scope: cycle
trigger: cycle_end
preferred_roles: [Data]
allowed_roles: [Data, Lead]

# === Delivery Expectations (Proof-of-Delivery) ===
inputs:
  cycle_id:
    type: string
    required: true
    description: "Cycle identifier for snapshot collection"
  runtime_api_url:
    type: string
    required: true
    description: "URL of the Runtime API for data retrieval"
  output_dir:
    type: string
    required: false
    default: "runs/{cycle_id}/capabilities/{capability_id}"
    description: "Output directory (relative to run_root)"

outputs:
  snapshot_path:
    type: string
    required: true
    description: "Path to the generated snapshot file"

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

## 15.2 Worked Example — Reference Workload (Data Wrap-up Smoke)

**File:** `src/squadops/capabilities/manifests/workloads/data_cycle_wrapup_smoke.yaml`

```yaml
workload_id: data_cycle_wrapup_smoke
workload_version: "1.0"
description: "Minimal end-to-end workload validating snapshot + metrics + summary artifact delivery."

# Optional: override fail-fast behavior (default: false)
# continue_on_failure: false

tasks:
  - task_id: snapshot
    capability_id: data.collect_cycle_snapshot
    inputs:
      cycle_id: "{cycle_id}"
      runtime_api_url: "{vars.runtime_api_url}"

  - task_id: metrics
    capability_id: data.profile_cycle_metrics
    depends_on: [snapshot]
    inputs:
      cycle_id: "{cycle_id}"
      snapshot_path: "runs/{cycle_id}/capabilities/data.collect_cycle_snapshot/cycle_snapshot.json"

  - task_id: summary
    capability_id: data.compose_cycle_summary
    depends_on: [metrics]
    inputs:
      cycle_id: "{cycle_id}"
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

## 15.3 Worked Example — WorkloadRunReport

**File:** `runs/cycle-001/workloads/data_cycle_wrapup_smoke/workload_run_report.json`

```json
{
  "report_version": "1.0",
  "cycle_id": "cycle-001",
  "workload_id": "data_cycle_wrapup_smoke",
  "workload_version": "1.0",
  "started_at": "2026-01-29T10:00:00Z",
  "ended_at": "2026-01-29T10:05:23Z",
  "duration_seconds": 323,
  "executor_backend": "aci",
  "status": "PASSED",
  "tasks": [
    {
      "task_id": "snapshot",
      "capability_id": "data.collect_cycle_snapshot",
      "resolved_executor": { "role": "Data", "agent_id": "data-001" },
      "status": "COMPLETED",
      "started_at": "2026-01-29T10:00:01Z",
      "ended_at": "2026-01-29T10:01:45Z",
      "duration_seconds": 104,
      "task_result_ref": "runs/cycle-001/capabilities/data.collect_cycle_snapshot/task_result.json",
      "artifact_refs": [
        "runs/cycle-001/capabilities/data.collect_cycle_snapshot/cycle_snapshot.json"
      ],
      "acceptance_results": [
        { "check_id": "snapshot_exists", "status": "PASS", "reason": null },
        { "check_id": "snapshot_non_empty", "status": "PASS", "reason": null },
        { "check_id": "snapshot_cycle_id_matches", "status": "PASS", "reason": null }
      ]
    },
    {
      "task_id": "metrics",
      "capability_id": "data.profile_cycle_metrics",
      "resolved_executor": { "role": "Data", "agent_id": "data-001" },
      "status": "COMPLETED",
      "started_at": "2026-01-29T10:01:46Z",
      "ended_at": "2026-01-29T10:03:12Z",
      "duration_seconds": 86,
      "task_result_ref": "runs/cycle-001/capabilities/data.profile_cycle_metrics/task_result.json",
      "artifact_refs": [
        "runs/cycle-001/capabilities/data.profile_cycle_metrics/cycle_metrics.json"
      ],
      "acceptance_results": []
    },
    {
      "task_id": "summary",
      "capability_id": "data.compose_cycle_summary",
      "resolved_executor": { "role": "Data", "agent_id": "data-001" },
      "status": "COMPLETED",
      "started_at": "2026-01-29T10:03:13Z",
      "ended_at": "2026-01-29T10:05:22Z",
      "duration_seconds": 129,
      "task_result_ref": "runs/cycle-001/capabilities/data.compose_cycle_summary/task_result.json",
      "artifact_refs": [
        "runs/cycle-001/capabilities/data.compose_cycle_summary/cycle_summary.json"
      ],
      "acceptance_results": []
    }
  ],
  "failures": [],
  "headline_metrics": {
    "last_cycle_status": "PASSED",
    "autonomic_run_time_seconds": 323,
    "wrapup_score": 1.0,
    "tasks_completed": 3,
    "tasks_failed": 0,
    "tasks_skipped": 0,
    "acceptance_checks_passed": 4,
    "acceptance_checks_failed": 0
  }
}
```
