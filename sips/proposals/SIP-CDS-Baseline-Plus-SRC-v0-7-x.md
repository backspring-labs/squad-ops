---
sip_uid: "PLACEHOLDER_ULID_GENERATE_WITH_SCRIPT"
sip_number: null
title: "CDS Baseline Plus SRC — SquadOps v0.7.x"
status: "proposed"
author: "Framework Committee"
approver: null
created_at: "2025-12-02T22:55:00Z"
updated_at: "2025-12-02T22:55:00Z"
original_filename: "SIP-CDS-Baseline-Plus-SRC-v0-7-x.md"
---

# SIP_CDS_BASELINE_PLUS_SRC — SquadOps v0.7.x  
## Cycle Data Store as the Operational Source-of-Record

**Status:** Draft  
**Target Version:** SquadOps v0.7.x  
**Author:** Framework Committee  
**Roles:** Lead, Strategy, Dev, QA, Data

---

# 1. Purpose and Intent

The purpose of v0.7.x is to evolve the **Cycle Data Store (CDS)** into the **operational Source-of-Record (SoR)** for all SquadOps execution. This is the release where the squad transitions from ad‑hoc cycle logging to a cohesive, governed, multi-cycle execution substrate capable of supporting sustained autonomous workflows.

CDS becomes the system-wide backbone that unifies:

- Cycles  
- Tasks performed by agents  
- PIDs and their governance artifacts  
- Documentation, testing, tagging, and data-governance structures  
- A consistent API surface for cycle runtime visibility  

The outcome is a reliable data foundation that supports continuous execution and prepares the architecture for upcoming phases (0.8 Prefect pulse orchestration, 0.9 Langfuse tracing, 1.0 SOC dashboards).

---

# 2. Background

Before v0.7.x:

- Cycle tracking was minimal.  
- PID-level governance artifacts lived only in Markdown.  
- No unified index existed to link tasks → PIDs → artifacts.  
- Role actions were recorded inconsistently.  
- No API surface existed for cycle state, task state, agent readiness, or scheduler interactions.  

The lack of a unified data model and runtime API created fragility:

- Long-running work could not be reconstructed.  
- Governance completeness was not measurable.  
- Agents and external services had no stable interface for querying execution context.  

v0.7.x establishes a structurally coherent execution and governance layer that will support multi-cycle continuity.

---

# 3. Problem Statements

### 3.1 No uniform cycle representation  
A project cycle must capture more than a timestamp. It must reflect intention, PIDs involved, runtime state, and task progress.

### 3.2 Role actions were not normalized  
Lead, Strategy, Dev, QA, and Data each logged work differently.

### 3.3 PIDs were not indexed  
Processes were not connected to their documentation, tests, governance artifacts, or tagging specifications.

### 3.4 No API for runtime visibility  
Without an explicit REST surface, no subsystem can reliably interact with or observe cycle execution.

### 3.5 No unified source-of-record  
Artifacts, tasks, PIDs, and governance lived in scattered places.

CDS must unify these structures to support coherent long-running execution.

---

# 4. Scope

v0.7.x delivers:

- A formalized CDS schema for cycles, tasks, PIDs, documentation, testing, governance, and tagging artifacts  
- A unified task logging mechanism used by all roles  
- PID index population utilities  
- A stable **Cycle Runtime REST API** surface integrated directly into the system  
- Project‑agnostic execution behavior  

This SIP describes the data structures, API surface, and logging conventions required to achieve that.

---

# 5. Design Overview

### 5.1 Unified Execution Model  
All projects use the same model:

- A **cycle** represents an execution attempt  
- **Tasks** represent units of work performed by roles  
- **PIDs** represent governed processes  
- Governance artifacts (docs, tests, tagging, KDEs) attach to PIDs  
- The CDS stores the metadata and associations  
- The API surface exposes this information to any service  

### 5.2 Why This Matters  
This model enables:

- Full traceability  
- Multi-cycle continuity  
- A clear record of what happened, why, and by whom  
- Reliable project-state reconstruction  
- Readiness for orchestration and observability layers

### 5.3 Framework Positioning  
v0.7.x is the foundation that allows all future subsystems (Pulse orchestrator, agent scheduler, SOC) to interact with the runtime consistently.

---

# 6. CDS Schema Requirements

## 6.1 Execution Cycle Table (`cycle`)
Stores cycle metadata:
- ecid  
- name  
- goal  
- squad_id  
- start_time  
- end_time  
- status  
- inputs (JSON: PIDs, repo, branch)  

## 6.2 Task Log Table (`task_log`)
Standardized role-based actions:
- task_id  
- ecid  
- role  
- task_name  
- pid (nullable)  
- description   
- start_time  
- end_time  
- status  
- artifacts (array)  
- metrics (JSON)  
- dependencies (array)  

## 6.3 PID Registry (`pid_registry`)
- pid  
- process_name  
- status  
- last_updated_version  
- change_notes  

## 6.4 PID Indices  
### Documentation (`pid_artifact_index`)  
### Testing (`pid_testing_index`)  
### Data Governance (`pid_data_governance_index`)  
### Tagging (`pid_tagging_index`)  

Each stores PID → repo paths for relevant artifacts.

---

# 7. PID Indexing Requirements

The system must support repo-scanning to populate CDS indices for:

- Documentation (BP, UC, WF, diagrams, metrics)  
- Testing artifacts (plans, cases, results, checklists)  
- Data governance assets (KDE registry, data dictionary, metrics, lineage)  
- Tagging structures (specs, schemas, tagging layer definitions)  

Indexes must remain synchronized with the repository.

---

# 8. Task Logging Requirements

All roles must use a unified task logging helper that:

- Logs start and end  
- Records role and PID  
- Attaches artifacts  
- Captures metrics  
- Supports dependencies  
- Writes into `task_log` with consistent structure  

This ensures coherent historical reconstruction.

---

# 9. Cycle Runtime REST API Surface  
### (Integrated exactly as defined in CYCLE_RUNTIME_REST_API_SURFACE.md)

The following API surface is required to be implemented in v0.7.x.

---

## 9.1 Cycles

### Create a Cycle  
**POST** `/api/v1/cycles`

### Get Cycle State  
**GET** `/api/v1/cycles/{ecid}`

### List Cycles  
**GET** `/api/v1/cycles?status=running&limit=20`

### Control a Cycle  
**POST** `/api/v1/cycles/{ecid}/actions`  
(actions: pause, resume, cancel)

---

## 9.2 Pulses (deferred for now)

### List Pulses for a Cycle  
**GET** `/api/v1/cycles/{ecid}/pulses`

### Submit Pulse Readiness  
**POST** `/api/v1/pulses/readiness`

### Get Latest Pulse  
**GET** `/api/v1/cycles/{ecid}/pulses/latest`

---

## 9.3 Tasks

### List Pending Tasks  
**GET** `/api/v1/cycles/{ecid}/tasks/pending`

### Submit Task Result  
**POST** `/api/v1/tasks/{task_id}/results`

---

## 9.4 Artifacts

### List Artifacts for a Cycle  
**GET** `/api/v1/cycles/{ecid}/artifacts`

### Get Artifact Metadata  
**GET** `/api/v1/artifacts/{artifact_id}`

### Upload Artifact (signed URL workflow)  
**POST** `/api/v1/artifacts/upload-request`

---

## 9.5 Agents

### List Agents  
**GET** `/api/v1/agents`

### Get Agent Runtime State  
**GET** `/api/v1/agents/{agent_id}/state`

---

## 9.6 Runtime State

### Get Cycle Runtime State Snapshot  
**GET** `/api/v1/cycles/{ecid}/runtime`

---

## 9.7 Scheduler / Coordination

### Pulse Coordination Status  
**GET** `/api/v1/pulse-coordinator/status`

### Scheduler Health + Queues  
**GET** `/api/v1/scheduler/status`

---

# 10. Executive Summary — Deliverables

v0.7.x must produce:

1. **Formal CDS Schema**  
2. **Unified Task Logging Helper**  
3. **PID Index Population Utilities**  
4. **Full Cycle Runtime REST API Surface** (exactly as defined in section 9)

These together establish CDS as the reliable operational Source‑of‑Record.

---

# 11. Definition of Done

The release is complete when:

- All CDS schema components migrate cleanly  
- All roles use the task logging helper  
- PID registry and indices are populated  
- The full REST API surface is implemented  
- Any project can retrieve and act upon its complete execution context through CDS  

CDS becomes the structural backbone enabling continuous, governed, multi‑cycle autonomous execution.


