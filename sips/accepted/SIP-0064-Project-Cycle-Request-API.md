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
## Cycle Execution API Foundation, Squad Profiles, Task Flow Policy, and Artifact Vault

**Status:** Accepted
**Target Release:** SquadOps v0.9.3
**Scope:** API Foundation + Domain Models + Hex Ports (CLI and SOC deferred beyond v0.9.3)
**Impact:** High (new domain entities, ports, API resources, persistence; WarmBoot deprecated; PCR demoted from entity to experiment record on Cycle)

---

## 1. Overview

SquadOps is evolving into a system that supports reproducible benchmarking, longitudinal learning, and coordinated agent execution across multiple projects. To support this, v0.9.3 establishes a domain-driven, API-level foundation for submitting and executing work in a consistent, inspectable, and comparable way.

This SIP introduces:

- **Projects** as pre-registered, long-lived entities
- **Cycles** as the experiment record — capturing intent ("run this project"), the experiment configuration (PRD ref, squad formation, orchestration strategy), and extensible context
- **Runs** as individual execution attempts within a cycle
- **Squad Profiles** as saved, versioned squad configurations with an active default
- **Task Flow Policy** as explicit orchestration intent (separate from concrete DAG wiring)
- **Artifact Vault** integration via immutable **ArtifactRefs**
- **Experiment Context** as an extensible dict for emerging experiment dimensions without schema migrations

This SIP also **deprecates WarmBoot** as a standalone execution concept. All execution is represented as Project → Cycle → Run (and Tasks).

This SIP **demotes PCR (Project Cycle Request)** from a standalone versioned entity to structured experiment configuration fields on the Cycle record. The "cycle request" is the Cycle itself — not a separate template.

---

## 2. Decisions and Scope Clarifications

### 2.1 WarmBoot Deprecation

**Decision:** WarmBoot is deprecated as a standalone domain construct and API.

- All execution is represented as **Project → Cycle → Run → Tasks**.
- "Power-on self test" and example workloads are implemented as **built-in Example Projects with default configurations**, executed via `POST /projects/{project_id}/cycles` (not `/warmboot/submit`).
- Existing WarmBoot API routes (`/warmboot/*`) remain **functional but frozen** — no new features, no bug fixes. **WarmBoot routes will be removed no later than v0.9.5; WarmBoot models will be removed at v1.0.**
- Historical WarmBoot data is **not migrated** into Cycle+Run records. It remains queryable via legacy routes for continuity but is not promoted into the new model.

### 2.2 PCR Demotion: Entity → Experiment Record

**Decision:** PCR is not a standalone versioned entity with its own identity, port, or API endpoints.

PCR is the **experiment configuration** — the collection of knobs and dials set when a cycle is created. These fields are stored directly on the Cycle record:

- **Requirements variable** — which PRD version (`prd_ref`)
- **Squad formation variable** — which agents, models, roles (`squad_profile_id` + snapshot)
- **Orchestration variable** — sequential, fan-out, gates (`task_flow_policy`)

Plus execution mechanics (`build_strategy`, `execution_overrides`) and an open `experiment_context` dict for emerging dimensions.

The value of this record is retrospective analysis: when a cycle underperforms, isolate which knob was the problem. Same PRD + different squad = squad was wrong. Same squad + different PRD = requirements were vague. Same everything + different flow policy = orchestration was inefficient.

There is no `PCRRegistryPort`. There are no PCR API endpoints. The cycle history IS the query surface for experiment configurations.

### 2.3 PRD: Industry-Standard Artifact, Not a Proprietary Entity

**Decision:** PRDs are industry-standard product requirements documents. The framework does not own the format, does not impose schema, and does not manage PRD lifecycle.

- PRDs are maintained by operators in source control (markdown or whatever format they prefer).
- The framework ingests PRDs as artifacts via `ArtifactVaultPort` with `artifact_type: "prd"`.
- Cycles reference PRDs via `prd_ref` (an `artifact_id`).
- There is no `PRDRegistryPort`, no PRD domain entity, no PRD lifecycle states.
- PRD versioning is handled by artifact versioning (operators ingest new versions as new artifacts).

### 2.4 Experiment Context Extensibility

**Decision:** New experiment dimensions do not require schema migrations.

Core experiment dimensions (PRD ref, squad formation, orchestration strategy) are named typed fields on the Cycle model. Emerging dimensions are recorded in `experiment_context` (a JSONB dict). When a dimension becomes universal, it is promoted to a named field via schema migration.

| Layer | Mechanism | Schema migration? |
|-------|-----------|-------------------|
| Core dimensions (PRD, squad, flow) | Named typed fields | Already exists |
| New experiment variables | `experiment_context` dict | No |
| Promotion to core | Named field + data migration | Yes, when mature |

Example: deployment infrastructure (`infra_profile: "gpu-a100-4x"`) starts in `experiment_context`. If it becomes universal, it gets promoted to a named Cycle field in a future release.

### 2.5 Pulse / Surge Vocabulary

Pulse and Surge are **future coordination constructs** (not delivered in 0.9.3). If referenced in implementation, they should be labeled as "future terminology." The `pulse_id` field on `TaskEnvelope` is retained for forward compatibility but has no lifecycle semantics in 0.9.3.

### 2.6 Client Strategy

The APIs defined in this SIP are designed for two primary consumers (both deferred beyond v0.9.3):

- **CLI** — command-line tool for operators (cycle submission, status queries, artifact retrieval)
- **SOC Control Plane** — web application for squad management and observability

The existing health dashboard and console are **not target consumers**. No new investment will be made in the health dashboard for cycle management. API error responses are JSON-structured and machine-parseable to support CLI consumption.

### 2.7 Legacy Model Plan

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
- inability to isolate which experiment variable (requirements, formation, orchestration) caused a failure

The goal of v0.9.3 is to make cycle submission and run provenance explicit, durable, and API-driven — with a single execution model and clear experiment dimensions.

---

## 4. Design Goals

1. **API-first submission model** for cycles: all experiment parameters in one request
2. **Project continuity** as the unit of learning and comparison
3. **Cycle as experiment record** — captures the configuration snapshot (what PRD, what squad, what orchestration, what overrides)
4. **PRD** defines *what is being built* (product semantics) — an industry-standard artifact, not a proprietary entity
5. **Cycle → Run** hierarchy: Cycle is intent + configuration, Run is execution attempt
6. **Squad Profiles** are saved and selectable; Runs always record the chosen profile snapshot
7. **Task Flow Policy** is declared and stored for observability and comparability
8. **Artifacts are immutable evidence** stored in an external vault; domain stores refs only
9. **One execution model** — WarmBoot absorbed, not maintained in parallel
10. **Minimal proprietary surface** — leverage industry practice (PRDs, markdown); custom domain objects only where SquadOps adds unique value (cycles, runs, profiles, flow policy)
11. **Extensibility without schema migrations** — `experiment_context` dict for emerging dimensions

---

## 5. Core Concepts

### 5.1 Project

A pre-registered, long-lived entity that owns cycles, artifacts, and scorecard histories. Projects are the unit of learning and longitudinal comparison.

### 5.2 PRD (Product Requirements Document)

An industry-standard artifact (typically markdown) maintained by operators in source control. The framework stores PRDs as artifacts in the vault and references them by `artifact_id`. PRDs are not proprietary domain entities — the framework does not define PRD format, schema, or lifecycle.

When a cycle is created, the caller provides a `prd_ref` (artifact_id) pointing to the PRD version used. This enables the comparison query: "how did the same requirements perform with different squad formations?"

### 5.3 Cycle

The **experiment record**: a unit of intent ("run this project") plus the full configuration snapshot. A Cycle captures:

- **Which requirements** — `prd_ref` (artifact_id of the PRD version used)
- **Which squad** — `squad_profile_id` + `squad_profile_snapshot_ref` (deterministic hash)
- **Which orchestration** — `task_flow_policy` (sequential, fan-out, gates)
- **Which build strategy** — `build_strategy` (fresh vs incremental)
- **Which overrides** — `execution_overrides` (any additional knobs)
- **Open context** — `experiment_context` (emerging dimensions like infra profile, cost tier)

A Cycle is created once and may have multiple Runs (retry/replay). Cycles are the comparison unit — "how did the same intent perform across different runs?"

**Execution parameter set (immutable per Cycle):** `(prd_ref, squad_profile_id, task_flow_policy, build_strategy, execution_overrides, experiment_context)`. Any change to these constitutes a new Cycle. Environmental differences (infrastructure state, LLM temperature drift, external service availability) do not require a new Cycle — they are recorded as a new Run of the same Cycle.

### 5.4 Run

A **single execution attempt** of a Cycle. Each Run is an immutable record of what actually happened.

Every Run MUST reference:
- `squad_profile_snapshot_ref` (immutable hash of the resolved squad profile)
- `task_flow_policy_ref` (hash or version of resolved policy)
- `resolved_config_hash` (hash of the full merged configuration for comparison/dedup)
- `artifact_refs` produced (or a manifest ref)

A Cycle MAY have multiple Runs (retry/replay). If execution parameters change, that is a **new Cycle** (new intent), not a new Run.

### 5.5 Squad Profile

A saved, versioned squad configuration (models per role, tools, concurrency defaults, etc.). There is an "active" profile and optional recommended profiles, but Cycles do not hard-bind to a profile.

### 5.6 Task Flow Policy

Declared orchestration intent: `sequential`, `fan_out_fan_in`, `fan_out_soft_gates`. The in-process executor owns the concrete dispatch; SquadOps persists the declared policy and gates.

- `sequential` — orchestrator submits tasks one at a time, each awaiting completion before the next.
- `fan_out_fan_in` — orchestrator submits all tasks concurrently, waits for all to complete.
- `fan_out_soft_gates` — orchestrator submits tasks concurrently with named decision points (gates) where execution pauses for operator approval.

Gate decisions are recorded on the Run record. Gate approval/rejection affects Run status.

### 5.7 Artifact Vault

External system storing immutable cycle outputs and ingested documents (including PRDs). The database stores only `ArtifactRef` metadata and retrieval references. The vault stores bytes.

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

The SIP defines API shapes (inbound adapter: FastAPI) and requires the following application-layer ports. Database, filesystem, and S3 are outbound adapters behind these ports.

### 7.1 Port Definitions

| Port | Responsibility | v0.9.3 Adapter |
|------|---------------|----------------|
| `ProjectRegistryPort` | List/get projects | Config-file loader (YAML/JSON); DB later |
| `CycleRegistryPort` | Create/query cycles; create/update Runs; record Run lifecycle transitions; experiment configuration queries | PostgreSQL adapter |
| `SquadProfilePort` | Read-only profile access; active selection; resolve immutable snapshot (hash) for a Run | Config-file loader + hash; full CRUD deferred |
| `ArtifactVaultPort` | Ingest/retrieve/list artifacts (including PRDs); baseline promotion | Filesystem adapter; S3 later |
| `FlowExecutionPort` | Interpret TaskFlowPolicy; construct task execution plan; report Run/task events back to CycleRegistryPort; manage gate decisions | In-process executor (wraps AgentOrchestrator); Prefect adapter deferred |

### 7.2 Hex Boundaries

```
┌─────────────────────────────────────────────┐
│  Inbound Adapters                           │
│  ├─ FastAPI routes (/projects, /cycles)     │
│  └─ CLI (deferred beyond v0.9.3)            │
├─────────────────────────────────────────────┤
│  Domain                                     │
│  ├─ Project (entity)                        │
│  ├─ Cycle (entity + experiment config)      │
│  ├─ Run (entity)                            │
│  ├─ SquadProfile (entity + snapshot)        │
│  ├─ ArtifactRef (value object)              │
│  ├─ TaskFlowPolicy, Gate (value objects)    │
│  ├─ GateDecision (value object)             │
│  ├─ CycleStatus, RunStatus (enums)          │
│  └─ TaskEnvelope, TaskResult (existing)     │
├─────────────────────────────────────────────┤
│  Ports (abstract interfaces)                │
│  ├─ ProjectRegistryPort                     │
│  ├─ CycleRegistryPort                       │
│  ├─ SquadProfilePort                        │
│  ├─ ArtifactVaultPort                       │
│  └─ FlowExecutionPort                       │
├─────────────────────────────────────────────┤
│  Outbound Adapters                          │
│  ├─ PostgreSQL (cycles, runs)               │
│  ├─ Filesystem / S3 (artifact vault)        │
│  ├─ YAML/JSON loaders (projects, profiles)  │
│  └─ Prefect (optional, deferred)            │
└─────────────────────────────────────────────┘
```

### 7.3 Adapter Notes

- **ProjectRegistryPort** is read-only for v0.9.3. Projects are pre-registered via config files (YAML/JSON), not created via API. This keeps the first adapter simple. DB-backed CRUD can be added later without changing the port interface.
- **CycleRegistryPort** handles all cycle and run persistence, including experiment configuration queries ("all cycles for project X with squad profile Y"). The experiment configuration fields and `experiment_context` dict are stored as JSONB for flexible querying.
- **SquadProfilePort** loads profiles from config files and computes a deterministic hash as the snapshot identifier. Profiles are **read-only in v0.9.3** (config-loaded); only "set active" is a mutable operation. Full CRUD (create/update/delete via API) is deferred until runtime profile management is needed.
- **ArtifactVaultPort** handles all artifact storage including PRDs. PRDs are ingested as artifacts with `artifact_type: "prd"`. No separate PRD port is needed.
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

### 8.2 Cycle (Experiment Record)

The Cycle is the experiment record. It captures the full configuration snapshot at creation time.

```python
@dataclass(frozen=True)
class Cycle:
    cycle_id: str
    project_id: str
    created_at: datetime
    created_by: str  # Identity.user_id or "system"

    # --- Core experiment dimensions (named, typed, indexed) ---

    # Dimension 1: Requirements — which PRD version was used
    prd_ref: str | None  # artifact_id of the PRD; None for example projects

    # Dimension 2: Squad formation — which agents, models, roles
    squad_profile_id: str
    squad_profile_snapshot_ref: str  # deterministic hash

    # Dimension 3: Orchestration strategy
    task_flow_policy: TaskFlowPolicy

    # --- Execution mechanics ---
    build_strategy: str  # "fresh" | "incremental"
    applied_defaults: dict  # system-applied defaults for this project/context
    execution_overrides: dict  # caller-provided overrides (explicit intent)
    expected_artifact_types: tuple[str, ...]
    # The API merges applied_defaults + execution_overrides to produce the
    # resolved config. Analysis can diff the two to distinguish "system chose"
    # from "operator chose" for any parameter.

    # --- Extensible experiment context (no schema migration for new dimensions) ---
    experiment_context: dict  # e.g., {"infra_profile": "gpu-a100-4x", "region": "us-east-1"}

    notes: str | None = None
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

### 8.4 Run

```python
@dataclass(frozen=True)
class Run:
    run_id: str
    cycle_id: str
    run_number: int  # sequential within cycle (1, 2, 3...)
    status: str  # RunStatus enum value
    initiated_by: str  # "api" | "cli" | "retry" | "system"
    resolved_config_hash: str  # SHA-256 of the full merged config for comparison/dedup
    resolved_config_ref: str | None = None  # artifact_id of vault-stored config snapshot (deep inspection)
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

### 8.5 ArtifactRef

```python
@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    project_id: str
    cycle_id: str | None  # None for PRDs and other project-level artifacts
    run_id: str | None  # None for PRDs and other non-run artifacts
    artifact_type: str  # e.g., "prd", "code", "test_report", "build_plan"
    filename: str
    content_hash: str  # SHA-256 of bytes
    size_bytes: int
    media_type: str  # MIME type
    created_at: datetime
    metadata: dict = field(default_factory=dict)
    vault_uri: str | None = None  # None only during ingestion; populated by ArtifactVaultPort.store()
```

### 8.6 SquadProfile

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

### 9.2 Squad Profiles

- `GET /api/v1/squad-profiles` — Lists saved squad profiles.
- `GET /api/v1/squad-profiles/{profile_id}` — Retrieves a specific profile.
- `GET /api/v1/squad-profiles/active` — Retrieves the active profile.
- `POST /api/v1/squad-profiles/active` — Sets active profile (admin operation).

### 9.3 Cycles

- `POST /api/v1/projects/{project_id}/cycles` — Creates a Cycle + first Run.
- `GET /api/v1/projects/{project_id}/cycles` — Lists cycles for a project (filterable by status).
- `GET /api/v1/projects/{project_id}/cycles/{cycle_id}` — Returns Cycle with current status and Run history.
- `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/cancel` — Cancels the Cycle (no further Runs).

### 9.4 Runs

- `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs` — Creates a new Run (retry) for an existing Cycle.
- `GET /api/v1/projects/{project_id}/cycles/{cycle_id}/runs` — Lists Runs for a Cycle.
- `GET /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}` — Returns Run details including provenance.
- `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/cancel` — Cancels a Run.
- `POST /api/v1/projects/{project_id}/cycles/{cycle_id}/runs/{run_id}/gates/{gate_name}` — Approve/reject a gate.

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

**Cycle creation request payload (self-contained — no PCR indirection):**
```json
{
  "prd_ref": "art_prd_v3",
  "squad_profile_id": "full-squad",
  "task_flow_policy": {"mode": "sequential", "gates": []},
  "build_strategy": "fresh",
  "execution_overrides": {},
  "expected_artifact_types": ["code", "test_report"],
  "experiment_context": {"infra_profile": "gpu-a100-4x"},
  "notes": "Benchmark run after model upgrade"
}
```

**Cycle creation response:**
```json
{
  "cycle_id": "cyc_abc123",
  "project_id": "run_crysis",
  "run_id": "run_001",
  "run_number": 1,
  "status": "queued",
  "prd_ref": "art_prd_v3",
  "squad_profile_id": "full-squad",
  "squad_profile_snapshot_ref": "sha256:abcdef...",
  "task_flow_policy": {"mode": "sequential", "gates": []},
  "resolved_config_hash": "sha256:123456..."
}
```

### 9.5 Artifact Vault

- `POST /api/v1/artifacts` — Ingests an artifact (including PRDs) and returns an `ArtifactRef`.
- `GET /api/v1/artifacts/{artifact_id}` — Retrieves artifact metadata.
- `GET /api/v1/artifacts/{artifact_id}/download` — Retrieves artifact bytes or signed URL.
- `GET /api/v1/projects/{project_id}/artifacts` — Lists artifacts for a project (filterable by cycle, run, artifact_type).
- `GET /api/v1/projects/{project_id}/cycles/{cycle_id}/artifacts` — Lists artifacts produced by a cycle.
- `POST /api/v1/projects/{project_id}/baseline/{artifact_type}` — Promotes an artifact as the baseline for the given type (incremental builds only).
- `GET /api/v1/projects/{project_id}/baseline/{artifact_type}` — Gets current baseline artifact ref for the given type.
- `GET /api/v1/projects/{project_id}/baseline` — Lists all current baselines (keyed by artifact_type).

**PRD ingestion** uses the same artifact endpoint:
```json
{
  "project_id": "run_crysis",
  "artifact_type": "prd",
  "filename": "prd-v3.md",
  "media_type": "text/markdown"
}
```
The returned `artifact_id` is used as `prd_ref` when creating cycles.

**Baseline rules (normative):**
- Baseline promotion is only valid when the cycle's build strategy is `incremental`.
- Fresh build artifacts cannot be promoted as baselines.

---

## 10. Validation and Enforcement (Normative)

### 10.1 PRD Boundary Enforcement
Cycle `execution_overrides` are strictly constrained to execution mechanics. Domain-level variability belongs in the PRD content (the artifact), not in cycle overrides.

### 10.2 Task Flow Policy Enforcement
Cycles MUST declare one of the supported flow policies. Runs persist the declared policy; this is required even if the runtime wiring evolves.

### 10.3 Reproducibility Enforcement
Every Run MUST store:
- `resolved_config_hash` (SHA-256 of the full merged configuration — `applied_defaults` + `execution_overrides`)
- `resolved_config_ref` (OPTIONAL) — artifact_id of the full resolved config snapshot stored in the vault. When present, enables deep inspection beyond the hash.
- Cycle record carries `squad_profile_id` + `squad_profile_snapshot_ref` + `applied_defaults` + `execution_overrides` + `experiment_context`

### 10.3.1 Defaults vs Overrides (Analysis)
The Cycle stores both `applied_defaults` (what the system filled in) and `execution_overrides` (what the caller explicitly provided). This enables retrospective analysis: "the system defaulted to sequential, but the operator overrode to fan_out_fan_in." The API merges both to produce the resolved config; the two fields are preserved separately for diffing.

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
    "code": "VALIDATION_ERROR",
    "message": "Override key 'product_name' is not an execution mechanic",
    "details": {
      "field": "execution_overrides.product_name",
      "constraint": "execution_overrides must not contain domain semantics"
    }
  }
}
```

**Standard error codes and HTTP status mappings:**

| Scenario | HTTP Status | Error Code |
|----------|-------------|------------|
| Unknown project_id | 404 | `PROJECT_NOT_FOUND` |
| Unknown cycle_id / run_id | 404 | `CYCLE_NOT_FOUND` / `RUN_NOT_FOUND` |
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
- Project, Cycle, Run, ArtifactRef frozen dataclass construction and validation
- TaskFlowPolicy mode + gate validation
- CycleStatus derivation from RunStatus (including cancelled run edge case)
- Run state machine transition validation (legal and illegal)
- SquadProfile snapshot hash determinism
- Cycle experiment_context extensibility (arbitrary keys accepted)

### 12.2 Port Contract Tests (Unit)
- ProjectRegistryPort: list/get with config-file adapter
- CycleRegistryPort: create cycle, create run, update run status, query by experiment dimensions, query by experiment_context keys
- SquadProfilePort: list/get, active resolution, snapshot hash
- ArtifactVaultPort: ingest (including PRDs), retrieve, list, baseline promote/reject
- FlowExecutionPort: policy interpretation for each mode

### 12.3 API Integration Tests
- Built-in projects discoverable via `GET /api/v1/projects`
- Create cycle with self-contained payload:
  - all parameters provided
  - prd_ref = null (example project, no PRD)
  - invalid execution_overrides rejected (422)
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
  - PRD ingestion + retrieval
  - Cycle artifact ingestion + retrieval + listing
  - Baseline promotion (incremental allowed, fresh rejected)
- Experiment context:
  - Arbitrary keys stored and queryable
  - Cycle comparison queries across dimensions
- Error responses match standard contract (Section 11)

### 12.4 End-to-End API Smoke Runs
- Create cycle for each built-in project with default configuration
- Assert expected artifact types are emitted as ArtifactRefs
- Assert Run provenance includes resolved_config_hash
- Assert CycleStatus is correctly derived from Run outcomes

---

## 13. Non-Goals

v0.9.3 does not:
- Specify SOC UI behavior or screens (deferred beyond v0.9.3)
- Implement CLI tool (deferred beyond v0.9.3; APIs designed for CLI consumption)
- Implement artifact diffing or lineage visualization
- Define scoring rubrics (covered by future Agent Scoring SIP)
- Mandate a specific vault backend (filesystem for v0.9.3; S3/NAS later)
- Invest in health dashboard or console integration for cycle management
- Migrate historical WarmBoot data
- Implement Pulse/Surge coordination semantics (future)
- Implement project creation via API (config-file registration for v0.9.3)
- Define PRD format or lifecycle (PRDs are industry-standard artifacts, operator-managed)
- Implement cycle templates or presets (operators re-submit parameters; tooling sugar deferred)

---

## 14. Acceptance Criteria

1. Projects, Cycles, Runs, and Squad Profiles are first-class domain entities with frozen dataclass models.
2. Five hex ports are defined and have at least one working adapter each.
3. Cycles can be created via `POST /api/v1/projects/{project_id}/cycles` with a self-contained payload (no PCR indirection).
4. Cycle records capture all experiment dimensions: prd_ref, squad profile, task flow policy, build strategy, overrides, experiment_context.
5. Runs record full provenance: resolved_config_hash, gate decisions, artifact_refs.
6. Run lifecycle follows the defined state machine; illegal transitions are rejected.
7. CycleStatus is derived from latest non-cancelled Run status (not independently managed).
8. Artifact Vault API supports ingest (including PRDs), retrieval, listing, and baseline promotion (incremental only).
9. `experiment_context` accepts arbitrary keys without schema migration.
10. All API errors use the standard error contract (Section 11).
11. Built-in example projects replace WarmBoot as the primary "hello world" execution path.
12. Legacy `FlowRun`/`FlowCreate`/`FlowState` models are superseded by new domain models.
13. WarmBoot routes remain functional but frozen; no new features.
