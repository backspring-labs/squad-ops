---
title: Project Cycle Request API Foundation
status: accepted
author: Jason Ladd
created_at: '2026-02-08T00:00:00Z'
original_filename: SIP-Project-Cycle-Request-API-Foundation-0_9_3.md
sip_number: 64
updated_at: '2026-02-08T09:57:22.643719Z'
---
# SIP-0064
## Project Cycle Request API Foundation, Squad Profiles, Task Flow Policy, and Artifact Vault

**Status:** Accepted
**Target Release:** SquadOps v0.9.3
**Scope:** API Foundation + Domain Models + Hex Ports (SOC UI and CLI deferred to v1.0)
**Impact:** High (new domain entities, ports, API resources, persistence; WarmBoot deprecated)

---

## 1. Overview

SquadOps is evolving into a system that supports reproducible benchmarking, longitudinal learning, and coordinated agent execution across multiple projects. To support this, v0.9.3 establishes a domain-driven, API-level foundation for submitting and executing work in a consistent, inspectable, and comparable way.

This SIP introduces:

- **Projects** as pre-registered, long-lived entities
- **Project Cycle Requests (PCRs)** as immutable, versioned execution templates for launching cycles
- **Cycles** as units of intent ("run this project with this PCR")
- **Runs** as individual execution attempts within a cycle
- **Squad Profiles** as saved, versioned squad configurations with an active default
- **Task Flow Policy** as explicit orchestration intent (separate from concrete DAG wiring)
- **Artifact Vault** integration via immutable **ArtifactRefs**

This SIP also **deprecates WarmBoot** as a standalone execution concept. All execution is represented as Project → PCR → Cycle → Run (and Tasks).

---

## 2. Decisions and Scope Clarifications

### 2.1 WarmBoot Deprecation

**Decision:** WarmBoot is deprecated as a standalone domain construct and API.

- All execution is represented as **Project → PCR → Cycle → Run → Tasks**.
- "Power-on self test" and example workloads are implemented as **built-in Example Projects with default PCRs**, executed via `POST /cycles` (not `/warmboot/submit`).
- Existing WarmBoot API routes (`/warmboot/*`) remain **functional but frozen** — no new features, no bug fixes. **WarmBoot routes will be removed no later than v0.9.5; WarmBoot models will be removed at v1.0.**
- Historical WarmBoot data is **not migrated** into Cycle+Run records. It remains queryable via legacy routes for continuity but is not promoted into the new model.

### 2.2 Pulse / Surge Vocabulary

Pulse and Surge are **future coordination constructs** (not delivered in 0.9.3). If referenced in implementation, they should be labeled as "future terminology." The `pulse_id` field on `TaskEnvelope` is retained for forward compatibility but has no lifecycle semantics in 0.9.3.

### 2.3 Client Strategy

The APIs defined in this SIP are designed for two primary consumers (both deferred to v1.0):

- **CLI** — command-line tool for operators (cycle submission, status queries, artifact retrieval)
- **SOC Control Plane** — web application for squad management and observability

The existing health dashboard and console are **not target consumers**. No new investment will be made in the health dashboard for cycle management. API error responses are JSON-structured and machine-parseable to support CLI consumption.

### 2.4 Legacy Model Plan

The existing `FlowRun`, `FlowCreate`, `FlowState` Pydantic models in `legacy_models.py` are **replaced** by the new Cycle, Run, and related frozen dataclass models defined in this SIP. They are not wrapped behind ports; they are superseded. The legacy models remain in the codebase until all adapter references are migrated, at which point they are deleted. Goal: avoid three parallel model stacks.

---

## 3. Motivation

Without a formal submission and execution API layer, SquadOps risks:

- non-reproducible benchmark results
- hidden state ("whatever the squad was configured as that day")
- inability to compare runs across model sizes and tunings
- unclear lifecycle of build deliverables (fresh vs incremental)
- artifacts leaking into source repos and contaminating DDD boundaries
- two parallel execution models (WarmBoot vs cycles) with no shared provenance

The goal of v0.9.3 is to make cycle submission and run provenance explicit, durable, and API-driven — with a single execution model.

---

## 4. Design Goals

1. **API-first submission model** for cycles: deterministic defaults + explicit overrides
2. **Project continuity** as the unit of learning and comparison
3. **PCR** defines *how a cycle runs* (execution mechanics) — immutable per version
4. **PRD** defines *what is being built* (product semantics) — referenced by project/PCR, not embedded
5. **Cycle → Run** hierarchy: Cycle is intent, Run is execution attempt
6. **Squad Profiles** are saved and selectable; Runs always record the chosen profile snapshot
7. **Task Flow Policy** is declared and stored for observability and comparability
8. **Artifacts are immutable evidence** stored in an external vault; domain stores refs only
9. **One execution model** — WarmBoot absorbed, not maintained in parallel

---

## 5. Core Concepts

### 5.1 Project

A pre-registered, long-lived entity that owns cycles, artifacts, and scorecard histories. Projects are the unit of learning and longitudinal comparison.

### 5.2 PCR (Project Cycle Request)

A **domain entity** (not just an API schema) with identity and versioning. Each PCR version is immutable once published.

- PCR defines cycle mechanics and expectations, not domain semantics.
- Overrides applied at cycle creation produce a **resolved config snapshot** stored on the Run — they do not mutate the PCR.
- PCR is the boundary between "what to build" (PRD) and "how to run it" (execution template).

**PCR Override Constraints (normative):**
- Overrides MUST be namespaced to **execution mechanics** only.
- Domain inputs (product semantics) are NOT allowed as PCR overrides.
- The allowed override schema is declared per PCR and enforced at cycle creation.

### 5.3 PRD Boundary

Domain-level variability and product semantics belong in PRD content referenced by a project/PCR. PCR must not become a parameter bag for domain knobs.

### 5.4 Cycle

A **unit of intent**: "run this project with this PCR." A Cycle is created once and may have multiple Runs (retry/replay). Cycles are the comparison unit — "how did the same intent perform across different runs?"

### 5.5 Run

A **single execution attempt** of a Cycle. Each Run is an immutable record of what actually happened.

Every Run MUST reference:
- `pcr_id` + `pcr_version` (the specific template version used)
- `squad_profile_snapshot_ref` (immutable hash of the resolved squad profile)
- `task_flow_policy` (declared orchestration intent, or hash/version)
- `resolved_overrides` (the merged PCR defaults + caller overrides)
- `artifact_refs` produced (or a manifest ref)

A Cycle MAY have multiple Runs (retry/replay). If execution parameters change, that is a **new Cycle** (new intent), not a new Run.

**Execution parameter set (immutable per Cycle):** `(pcr_id, pcr_version, squad_profile_id, resolved_overrides, task_flow_policy)`. Any change to these constitutes a new Cycle. Environmental differences (infrastructure state, LLM temperature drift, external service availability) do not require a new Cycle — they are recorded as a new Run of the same Cycle.

### 5.6 Squad Profile

A saved, versioned squad configuration (models per role, tools, concurrency defaults, etc.). There is an "active" profile and optional recommended profiles per PCR, but PCR does not hard-bind to a profile.

### 5.7 Task Flow Policy

Declared orchestration intent: `sequential`, `fan_out_fan_in`, `fan_out_soft_gates`. Prefect owns the concrete DAG; SquadOps persists the declared policy and gates.

- `sequential` — orchestrator submits tasks one at a time, each awaiting completion before the next.
- `fan_out_fan_in` — orchestrator submits all tasks concurrently, waits for all to complete.
- `fan_out_soft_gates` — orchestrator submits tasks concurrently with named decision points (gates) where execution pauses for operator approval.

Gate decisions are recorded on the Run record. Gate approval/rejection affects Run status.

### 5.8 Artifact Vault

External system storing immutable cycle outputs. The database stores only `ArtifactRef` metadata and retrieval references. The vault stores bytes.

---

## 6. Lifecycle and State Machines

### 6.1 Cycle Status

CycleStatus is **derived from the latest Run status**. The Cycle itself only holds:

- `created` — Cycle exists but no Run has been started
- `active` — At least one Run is in progress
- `completed` — Latest Run completed successfully
- `failed` — Latest Run failed
- `cancelled` — Operator cancelled the Cycle (no further Runs permitted)

### 6.2 Run Status

RunStatus is the authoritative lifecycle:

- `queued` — Run created, awaiting execution
- `running` — Tasks are being executed
- `paused` — Execution paused at a gate or by operator
- `completed` — All tasks finished successfully
- `failed` — One or more tasks failed (terminal)
- `cancelled` — Operator cancelled this Run (terminal)

**Legal transitions:**
```
queued → running → completed
queued → running → failed
queued → running → paused → running → completed
queued → running → paused → cancelled
queued → cancelled
running → cancelled
```

### 6.3 CycleStatus Derivation

| Latest Run Status | Derived Cycle Status |
|-------------------|---------------------|
| (no runs)         | `created`           |
| `queued`          | `active`            |
| `running`         | `active`            |
| `paused`          | `active`            |
| `completed`       | `completed`         |
| `failed`          | `failed`            |
| `cancelled`       | see below           |

**Cancelled Run derivation:** CycleStatus is derived from the latest *non-cancelled* Run. If the Cycle itself has been explicitly cancelled (no further Runs permitted), CycleStatus = `cancelled`. If all Runs are cancelled but the Cycle is not, CycleStatus reverts to `created` (another Run may be started). A cancelled Run never masks a prior successful or failed Run's status.

---

## 7. Ports and Adapter Boundaries (Hex)

The SIP defines API shapes (inbound adapter: FastAPI) and requires the following application-layer ports. Database, filesystem, S3, and Prefect are outbound adapters behind these ports.

### 7.1 Port Definitions

| Port | Responsibility | v0.9.3 Adapter |
|------|---------------|----------------|
| `ProjectRegistryPort` | List/get projects | Config-file loader (YAML/JSON); DB later |
| `PCRRegistryPort` | List/get PCRs; resolve PCR version for cycle creation | Config-file loader (YAML/JSON); DB later |
| `CycleRegistryPort` | Create/query cycles; create/update Runs; record Run lifecycle transitions | PostgreSQL adapter |
| `SquadProfilePort` | Read-only profile access; active selection; resolve immutable snapshot (hash) for a Run | Config-file loader + hash; full CRUD deferred |
| `ArtifactVaultPort` | Ingest/retrieve/list artifacts; baseline promotion | Filesystem adapter; S3 later |
| `FlowExecutionPort` | Interpret TaskFlowPolicy; construct task execution plan; report Run/task events back to CycleRegistryPort; manage gate decisions | In-process executor (wraps AgentOrchestrator); Prefect adapter deferred |

### 7.2 Hex Boundaries

```
┌─────────────────────────────────────────┐
│  Inbound Adapters                       │
│  ├─ FastAPI routes (/cycles, /projects) │
│  └─ CLI (v1.0)                          │
├─────────────────────────────────────────┤
│  Domain                                 │
│  ├─ Project, PCR, Cycle, Run (entities) │
│  ├─ SquadProfile (entity + snapshot)    │
│  ├─ ArtifactRef (value object)          │
│  ├─ TaskFlowPolicy (value object)       │
│  ├─ CycleStatus, RunStatus (enums)      │
│  └─ TaskEnvelope, TaskResult (existing) │
├─────────────────────────────────────────┤
│  Ports (abstract interfaces)            │
│  ├─ ProjectRegistryPort                 │
│  ├─ PCRRegistryPort                     │
│  ├─ CycleRegistryPort                   │
│  ├─ SquadProfilePort                    │
│  ├─ ArtifactVaultPort                   │
│  └─ FlowExecutionPort                   │
├─────────────────────────────────────────┤
│  Outbound Adapters                      │
│  ├─ PostgreSQL (cycles, runs)           │
│  ├─ Filesystem / S3 (artifact vault)    │
│  ├─ YAML/JSON loaders (projects, PCRs)  │
│  └─ Prefect (optional flow execution)   │
└─────────────────────────────────────────┘
```

### 7.3 Adapter Notes

- **ProjectRegistryPort** and **PCRRegistryPort** are read-only for v0.9.3. Projects and PCRs are pre-registered via config files (YAML/JSON), not created via API. This keeps the first adapter simple. DB-backed CRUD can be added later without changing the port interface.
- **SquadProfilePort** loads profiles from config files and computes a deterministic hash as the snapshot identifier. Profiles are **read-only in v0.9.3** (config-loaded); only "set active" is a mutable operation. Full CRUD (create/update/delete via API) is deferred until runtime profile management is needed.
- **FlowExecutionPort** interprets `TaskFlowPolicy` at runtime. The **v0.9.3 default adapter is an in-process executor delegating to `AgentOrchestrator`** with sequential task dispatch. Prefect is a future adapter option, not a v0.9.3 deliverable. For v0.9.3: `sequential` = submit tasks one at a time; `fan_out_fan_in` = submit all, await all; `fan_out_soft_gates` = submit with pause points where the Run enters `paused` status and awaits operator approval via API.

---

## 8. Domain Models (Normative)

All domain models are **frozen dataclasses** (consistent with `TaskEnvelope`/`TaskResult` convention from SIP-0.8.8).

### 8.1 Project

```python
@dataclass(frozen=True)
class Project:
    project_id: str
    name: str
    description: str
    created_at: datetime
    tags: tuple[str, ...] = ()  # e.g., ("example", "selftest", "benchmark")
```

### 8.2 PCR

```python
@dataclass(frozen=True)
class PCR:
    pcr_id: str
    project_id: str
    version: int
    name: str
    description: str
    build_strategy: str  # "fresh" | "incremental"
    task_flow_policy: TaskFlowPolicy
    execution_defaults: dict  # default execution controls
    override_schema: dict  # JSON Schema for allowed overrides
    expected_artifact_types: tuple[str, ...]
    recommended_squad_profile_id: str | None = None
```

### 8.3 TaskFlowPolicy

```python
@dataclass(frozen=True)
class TaskFlowPolicy:
    mode: str  # "sequential" | "fan_out_fan_in" | "fan_out_soft_gates"
    gates: tuple[Gate, ...] = ()

@dataclass(frozen=True)
class Gate:
    name: str
    description: str
    after_task_types: tuple[str, ...]  # gate triggers after these tasks complete
    # Gate evaluation matches after_task_types against TaskEnvelope.task_type
    # values persisted on completed task records within the current Run.
```

### 8.4 Cycle

```python
@dataclass(frozen=True)
class Cycle:
    cycle_id: str
    project_id: str
    pcr_id: str
    pcr_version: int
    created_at: datetime
    created_by: str  # Identity.user_id or "system"
    notes: str | None = None
```

### 8.5 Run

```python
@dataclass(frozen=True)
class Run:
    run_id: str
    cycle_id: str
    run_number: int  # sequential within cycle (1, 2, 3...)
    status: str  # RunStatus enum value
    squad_profile_id: str
    squad_profile_snapshot_ref: str  # deterministic hash
    resolved_overrides: dict  # merged PCR defaults + caller overrides
    task_flow_policy_ref: str  # hash or version of resolved policy
    started_at: datetime | None = None
    finished_at: datetime | None = None
    gate_decisions: tuple[GateDecision, ...] = ()
    artifact_refs: tuple[str, ...] = ()  # artifact_ids

@dataclass(frozen=True)
class GateDecision:
    gate_name: str
    decision: str  # "approved" | "rejected"
    decided_by: str  # Identity.user_id
    decided_at: datetime
    notes: str | None = None
```

### 8.6 ArtifactRef

```python
@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    project_id: str
    cycle_id: str
    run_id: str
    artifact_type: str  # e.g., "code", "test_report", "build_plan"
    filename: str
    content_hash: str  # SHA-256 of bytes
    size_bytes: int
    media_type: str  # MIME type
    created_at: datetime
    metadata: dict = field(default_factory=dict)
    vault_uri: str | None = None  # None only during ingestion; populated by ArtifactVaultPort.store()
```

### 8.7 SquadProfile

```python
@dataclass(frozen=True)
class SquadProfile:
    profile_id: str
    name: str
    description: str
    version: int
    agents: tuple[AgentProfileEntry, ...]
    created_at: datetime

@dataclass(frozen=True)
class AgentProfileEntry:
    agent_id: str
    role: str
    model: str
    enabled: bool
    config_overrides: dict = field(default_factory=dict)
```

---

## 9. API Surface (Normative)

All API routes are under `/api/v1/` on the runtime-api service. Error responses use a standard JSON shape (see Section 11).

### 9.1 Projects

- `GET /api/v1/projects` — Lists pre-registered projects.
- `GET /api/v1/projects/{project_id}` — Returns project metadata.

**v0.9.3 ships with built-in projects:**
- `hello_squad` — Simple single-agent greeting (replaces warmboot_selftest)
- `run_crysis` — Multi-agent coordinated build
- `group_run` — Full squad parallel execution

### 9.2 PCRs

- `GET /api/v1/projects/{project_id}/pcrs` — Lists PCR templates for a project.
- `GET /api/v1/projects/{project_id}/pcrs/{pcr_id}` — Returns full PCR definition. **Version resolution:** returns the latest version by default; use `?version=N` to fetch a specific version.

### 9.3 Squad Profiles

- `GET /api/v1/squad-profiles` — Lists saved squad profiles.
- `GET /api/v1/squad-profiles/{profile_id}` — Retrieves a specific profile.
- `GET /api/v1/squad-profiles/active` — Retrieves the active profile.
- `POST /api/v1/squad-profiles/active` — Sets active profile (admin operation).

### 9.4 Cycles

- `POST /api/v1/cycles` — Creates a Cycle + first Run from a project + PCR.
- `GET /api/v1/cycles` — Lists cycles (filterable by project_id, status).
- `GET /api/v1/cycles/{cycle_id}` — Returns Cycle with current status and Run history.
- `POST /api/v1/cycles/{cycle_id}/cancel` — Cancels the Cycle (no further Runs).

### 9.5 Runs

- `POST /api/v1/cycles/{cycle_id}/runs` — Creates a new Run (retry) for an existing Cycle.
- `GET /api/v1/cycles/{cycle_id}/runs` — Lists Runs for a Cycle.
- `GET /api/v1/cycles/{cycle_id}/runs/{run_id}` — Returns Run details including provenance.
- `POST /api/v1/cycles/{cycle_id}/runs/{run_id}/cancel` — Cancels a Run.
- `POST /api/v1/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}` — Approve/reject a gate.

**Gate decision request payload:**
```json
{
  "decision": "approve",
  "notes": "QA review passed, approving deployment gate"
}
```
`decision` is required: `"approve"` or `"reject"`. `notes` is optional.

**Gate idempotency rules:**
- Double-approve (same gate, same decision): returns `200 OK` (no-op).
- Approve after already rejected (or vice versa): returns `409 Conflict` (`GATE_ALREADY_DECIDED`).
- Gate decision after Run is in a terminal state (`completed`/`failed`/`cancelled`): returns `409 Conflict` (`RUN_TERMINAL`).

**PCR version resolution at cycle creation:** If `pcr_version` is omitted, the system resolves to the latest published version at creation time and records it on the Cycle. Callers may provide an explicit `pcr_version` for reproducibility.

**Cycle creation request payload:**
```json
{
  "project_id": "hello_squad",
  "pcr_id": "default",
  "pcr_version": null,
  "execution_overrides": {},
  "squad_profile_id": null,
  "notes": "Benchmark run after model upgrade"
}
```

**Cycle creation response:**
```json
{
  "cycle_id": "cyc_abc123",
  "run_id": "run_001",
  "run_number": 1,
  "status": "queued",
  "resolved_overrides": {},
  "squad_profile_id": "default",
  "squad_profile_snapshot_ref": "sha256:abcdef...",
  "task_flow_policy": {"mode": "sequential", "gates": []}
}
```

### 9.6 Artifact Vault

- `POST /api/v1/artifacts` — Ingests an artifact and returns an `ArtifactRef`.
- `GET /api/v1/artifacts/{artifact_id}` — Retrieves artifact metadata.
- `GET /api/v1/artifacts/{artifact_id}/download` — Retrieves artifact bytes or signed URL.
- `GET /api/v1/projects/{project_id}/artifacts` — Lists artifacts for a project (filterable by cycle, run).
- `GET /api/v1/cycles/{cycle_id}/artifacts` — Lists artifacts produced by a cycle.
- `POST /api/v1/projects/{project_id}/baseline/{artifact_type}` — Promotes an artifact as the baseline for the given type (incremental builds only).
- `GET /api/v1/projects/{project_id}/baseline/{artifact_type}` — Gets current baseline artifact ref for the given type.
- `GET /api/v1/projects/{project_id}/baseline` — Lists all current baselines (keyed by artifact_type).

**Baseline rules (normative):**
- Baseline promotion is only valid when the cycle's build strategy is `incremental`.
- Fresh build artifacts cannot be promoted as baselines.

---

## 10. Validation and Enforcement (Normative)

### 10.1 PRD Boundary Enforcement
PCR schemas MUST reject override keys that represent domain semantics. PCR overrides are strictly constrained to execution mechanics. The allowed override schema is declared per PCR and validated at `POST /cycles` time.

### 10.2 Task Flow Policy Enforcement
PCR MUST declare one of the supported flow policies. Runs persist the declared policy; this is required even if the runtime wiring evolves.

### 10.3 Reproducibility Enforcement
Every Run MUST store:
- `squad_profile_id` + `squad_profile_snapshot_ref` (immutable hash)
- `resolved_overrides` (merged PCR defaults + caller overrides)
- `task_flow_policy_ref`

### 10.4 Artifact Integrity
ArtifactRefs MUST include `content_hash` (SHA-256). `vault_uri` is `None` only during the brief ingestion window (artifact created but not yet stored); once `ArtifactVaultPort.store()` returns, `vault_uri` MUST be populated. ArtifactRefs returned by API endpoints always have `vault_uri` populated.

### 10.5 State Transition Enforcement
Cycle and Run status transitions MUST follow the legal transition rules defined in Section 6. Invalid transitions return `409 Conflict`.

---

## 11. Error Response Contract (Normative)

All API errors use a standard JSON shape for machine-parseability (CLI and future SOC consumers):

```json
{
  "error": {
    "code": "INVALID_OVERRIDE",
    "message": "Override key 'product_name' violates PRD boundary",
    "details": {
      "field": "execution_overrides.product_name",
      "constraint": "not in allowed override schema"
    }
  }
}
```

**Standard error codes and HTTP status mappings:**

| Scenario | HTTP Status | Error Code |
|----------|-------------|------------|
| Unknown project_id | 404 | `PROJECT_NOT_FOUND` |
| Unknown pcr_id | 404 | `PCR_NOT_FOUND` |
| Unknown cycle_id / run_id | 404 | `CYCLE_NOT_FOUND` / `RUN_NOT_FOUND` |
| Invalid override key (PRD boundary) | 422 | `INVALID_OVERRIDE` |
| Invalid override value (schema) | 422 | `OVERRIDE_VALIDATION_ERROR` |
| Illegal state transition | 409 | `ILLEGAL_STATE_TRANSITION` |
| Baseline promotion on fresh build | 409 | `BASELINE_NOT_ALLOWED` |
| Gate already decided (conflicting decision) | 409 | `GATE_ALREADY_DECIDED` |
| Gate decision on terminal Run | 409 | `RUN_TERMINAL` |
| Artifact not found | 404 | `ARTIFACT_NOT_FOUND` |
| Missing required field | 422 | `VALIDATION_ERROR` |
| Authentication required | 401 | `AUTH_REQUIRED` |
| Insufficient permissions | 403 | `FORBIDDEN` |

---

## 12. Testing Strategy

Testing is API-driven (pytest + httpx). No browser or health dashboard testing investment.

### 12.1 Domain Model Tests (Unit)
- Project, PCR, Cycle, Run, ArtifactRef frozen dataclass construction and validation
- TaskFlowPolicy mode + gate validation
- CycleStatus derivation from RunStatus
- Run state machine transition validation (legal and illegal)
- SquadProfile snapshot hash determinism

### 12.2 Port Contract Tests (Unit)
- ProjectRegistryPort: list/get with config-file adapter
- PCRRegistryPort: list/get, version resolution
- CycleRegistryPort: create cycle, create run, update run status, query
- SquadProfilePort: list/get, active resolution, snapshot hash
- ArtifactVaultPort: ingest, retrieve, list, baseline promote/reject
- FlowExecutionPort: policy interpretation for each mode

### 12.3 API Integration Tests
- Built-in projects discoverable via `GET /api/v1/projects`
- PCRs discoverable per project
- Create cycle from PCR with:
  - defaults only
  - allowed overrides
  - disallowed override keys rejected (422)
- Cycle + Run lifecycle:
  - create → run → complete
  - create → run → fail
  - create → run → pause at gate → approve → complete
  - create → cancel (no further runs)
  - retry (new Run on existing Cycle)
- Squad profile:
  - active profile default
  - explicit profile selection
  - Run records profile snapshot ref
- Artifacts:
  - ingest + retrieve + listing
  - baseline promotion (incremental allowed, fresh rejected)
- Error responses match standard contract (Section 11)

### 12.4 End-to-End API Smoke Runs
- Create cycle for each built-in project using its default PCR
- Assert expected artifact types are emitted as ArtifactRefs
- Assert Run provenance includes task flow policy + profile snapshot ref
- Assert CycleStatus is correctly derived from Run outcomes

---

## 13. Non-Goals

v0.9.3 does not:
- Specify SOC UI behavior or screens (deferred to v1.0)
- Implement CLI tool (deferred to v1.0; APIs designed for CLI consumption)
- Implement artifact diffing or lineage visualization
- Define scoring rubrics (covered by future Agent Scoring SIP)
- Mandate a specific vault backend (filesystem for v0.9.3; S3/NAS later)
- Invest in health dashboard or console integration for cycle management
- Migrate historical WarmBoot data
- Implement Pulse/Surge coordination semantics (future)
- Implement project or PCR creation via API (config-file registration for v0.9.3)

---

## 14. Acceptance Criteria

1. Projects, PCRs, Cycles, Runs, and Squad Profiles are first-class domain entities with frozen dataclass models.
2. Six hex ports are defined and have at least one working adapter each.
3. Cycles can be created via `POST /api/v1/cycles` referencing `project_id + pcr_id`.
4. Runs record full provenance: resolved overrides, squad profile snapshot ref, task flow policy ref.
5. Run lifecycle follows the defined state machine; illegal transitions are rejected.
6. CycleStatus is derived from latest Run status (not independently managed).
7. Artifact Vault API supports ingest, retrieval, listing, and baseline promotion (incremental only).
8. PCR override validation enforces the PRD boundary (no domain knobs in PCR).
9. All API errors use the standard error contract (Section 11).
10. Built-in example projects replace WarmBoot as the primary "hello world" execution path.
11. Legacy `FlowRun`/`FlowCreate`/`FlowState` models are superseded by new domain models.
12. WarmBoot routes remain functional but frozen; no new features.
