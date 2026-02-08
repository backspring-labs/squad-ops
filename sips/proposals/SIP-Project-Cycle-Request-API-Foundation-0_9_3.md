# SIP-0.9.3  
## Project Cycle Request API Foundation, Squad Profiles, Task Flow Policy, and Artifact Vault

**Status:** Draft – Review  
**Target Release:** SquadOps v0.9.3  
**Scope:** API Foundation (SOC UI deferred to v1.0)  
**Impact:** Medium (new API resources + persistence, no breaking behavior)

---

## 1. Overview

SquadOps is evolving into a system that supports reproducible benchmarking, longitudinal learning, and coordinated agent execution across multiple projects. To support this, v0.9.3 establishes an API-level foundation for submitting and executing work in a consistent, inspectable, and comparable way.

This SIP introduces:

- **Projects** as pre-registered, long-lived entities  
- **Project Cycle Requests (PCRs)** as execution templates for launching cycles  
- **Squad Profiles** as saved, versioned squad configurations with an active default  
- **Task Flow Policy** as explicit orchestration intent (separate from concrete DAG wiring)  
- **Artifact Vault** integration via immutable **ArtifactRefs**  

SOC will later consume these APIs, but **SOC UI requirements are explicitly deferred to v1.0**.

---

## 2. Motivation

Without a formal submission and execution API layer, SquadOps risks:

- non-reproducible benchmark results  
- hidden state (“whatever the squad was configured as that day”)  
- inability to compare runs across model sizes and tunings  
- unclear lifecycle of build deliverables (fresh vs incremental)  
- artifacts leaking into source repos and contaminating DDD boundaries  

The goal of v0.9.3 is to make cycle submission and run provenance explicit, durable, and API-driven.

---

## 3. Design Goals

1. **API-first submission model** for cycles: deterministic defaults + explicit overrides  
2. **Project continuity** as the unit of learning and comparison  
3. **PCR** defines *how a cycle runs* (execution mechanics)  
4. **PRD** defines *what is being built* (product semantics)  
5. **Squad Profiles** are saved and selectable; runs always record the chosen profile  
6. **Task Flow Policy** is declared and stored for observability and comparability  
7. **Artifacts are immutable evidence** stored in an external vault; domain stores refs only  

---

## 4. Core Concepts

### 4.1 Project
A pre-registered, long-lived entity that owns cycles, artifacts, and scorecard histories.

### 4.2 PCR (Project Cycle Request)
An execution template attached to a project. PCR defines cycle mechanics and expectations, not domain semantics.

### 4.3 PRD Boundary
Domain-level variability and product semantics belong in PRD content referenced by a project/PCR. PCR must not become a parameter bag for domain knobs.

### 4.4 Squad Profile
A saved, versioned squad configuration (models per role, tools, concurrency defaults, etc.). There is an “active” profile and optional recommended profiles per PCR, but PCR does not hard-bind to a profile.

### 4.5 Task Flow Policy
Declared orchestration intent: `sequential`, `fan_out_fan_in`, `fan_out_soft_gates`. Prefect owns the concrete DAG; SquadOps persists the declared policy and gates.

### 4.6 Artifact Vault
External system storing immutable cycle outputs. SquadOps stores only `ArtifactRef` metadata and retrieval references.

---

## 5. API Surface (Normative)

### 5.1 Projects

- `GET /projects`  
  Lists pre-registered projects.

- `GET /projects/{project_id}`  
  Returns project metadata and available PCRs.

**v0.9.3 ships with built-in projects:**
- `hello_squad`
- `run_crysis`
- `group_run`

---

### 5.2 PCRs

- `GET /projects/{project_id}/pcrs`  
  Lists PCR templates for a project.

- `GET /projects/{project_id}/pcrs/{pcr_id}`  
  Returns PCR definition including:
  - declared build strategy default (fresh/incremental)
  - declared task flow policy + named gates (if any)
  - default execution controls (planning pause, scoring, wrap-up emission)
  - expected artifact types
  - override allowlist/schema (execution mechanics only)
  - optional `recommended_squad_profile_id` (non-binding)

**PCR Override Constraints (normative):**
- Overrides must be namespaced to **execution mechanics** only.
- Domain inputs (product semantics) are not allowed as PCR overrides.

---

### 5.3 Squad Profiles

- `GET /squad_profiles`  
  Lists saved squad profiles.

- `GET /squad_profiles/{profile_id}`  
  Retrieves a specific profile.

- `GET /squad_profiles/active`  
  Retrieves the active profile.

- `POST /squad_profiles/active`  
  Sets active profile (admin/controlled operation).

**Run provenance requirement (normative):**
Every cycle run must record:
- `squad_profile_id`
- and an immutable snapshot identifier (`profile_version` or `profile_hash`)

This ensures runs remain reproducible even if profiles evolve.

---

### 5.4 Cycle Creation from PCR

- `POST /cycles`  
  Creates a cycle run from a project + PCR.

**Request payload:**
- `project_id`
- `pcr_id`
- optional `execution_overrides` (mechanics only; validated)
- optional `squad_profile_id` (default = active)
- optional `notes` (free text, audit)

**Response:**
- `cycle_id`
- resolved defaults + overrides (normalized)
- resolved `squad_profile_id` + snapshot identifier
- declared `task_flow_policy`

---

### 5.5 Artifact Vault APIs

- `POST /artifacts`  
  Ingests an artifact and returns an `ArtifactRef`.

- `GET /artifacts/{artifact_id}`  
  Retrieves artifact metadata.

- `GET /artifacts/{artifact_id}/download`  
  Retrieves artifact bytes or a signed URL.

- `GET /projects/{project_id}/artifacts`  
  Lists artifacts for a project (filterable by cycle).

- `GET /cycles/{cycle_id}/artifacts`  
  Lists artifacts produced by a cycle.

- `POST /projects/{project_id}/baseline`  
  Promotes an artifact as the baseline (incremental builds only).

- `GET /projects/{project_id}/baseline`  
  Gets current baseline artifact ref.

**Baseline rules (normative):**
- Baseline promotion is only valid when the cycle’s build strategy is `incremental`.
- Fresh build artifacts cannot be promoted as baselines.

---

## 6. Validation & Enforcement (Normative)

### 6.1 PRD Boundary Enforcement
PCR schemas must reject override keys that represent domain semantics (unbounded “inputs” bag is disallowed). PCR overrides are strictly constrained to execution mechanics.

### 6.2 Task Flow Policy Enforcement
PCR must declare one of the supported flow policies. Cycles persist the declared policy; this is required even if the runtime wiring evolves.

### 6.3 Reproducibility Enforcement
Cycle runs must store the resolved `squad_profile_id` and immutable snapshot identifier.

### 6.4 Artifact Integrity
ArtifactRefs must include integrity metadata (e.g., hash) and stable retrieval URIs/handles.

---

## 7. Testing Strategy (API-only)

### 7.1 Contract / Schema Tests
- Project schema validation  
- PCR schema + override allowlist validation  
- Squad profile schema validation + active resolution  
- ArtifactRef schema validation  

### 7.2 API Integration Tests
- Built-in projects discoverable via `/projects`  
- PCRs discoverable per project  
- Create cycle from PCR with:
  - defaults only
  - allowed overrides
  - disallowed override keys rejected
- Create cycle with:
  - active profile default
  - explicit profile selection
  - run records profile snapshot identifier
- Artifact ingest + retrieval + listing works
- Baseline promotion:
  - allowed for incremental
  - rejected for fresh builds

### 7.3 End-to-End API Smoke Runs
- Create cycle for each built-in project using its default PCR
- Assert expected artifact types are emitted as ArtifactRefs
- Assert run provenance includes task flow policy + profile snapshot id

---

## 8. Non-Goals

v0.9.3 does not:
- specify SOC UI behavior or screens (deferred to v1.0)
- implement artifact diffing or lineage visualization
- define scoring rubrics (covered by Agent Scoring SIP)
- mandate a specific vault backend (FS vs S3 vs NAS)

---

## 9. Acceptance Criteria

- Projects, PCRs, and Squad Profiles are first-class API resources.
- Cycles can be created via `POST /cycles` referencing `project_id + pcr_id`.
- Cycle provenance records:
  - resolved defaults + overrides
  - declared task flow policy
  - squad profile id + snapshot identifier
- Artifact Vault API supports ingest, retrieval, listing, and baseline promotion (incremental only).
- PCR override validation enforces the PRD boundary (no domain knobs in PCR).
