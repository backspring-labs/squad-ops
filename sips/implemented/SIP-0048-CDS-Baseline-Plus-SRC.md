---
sip_uid: 01KBH738S3M9TPC9XH3C80T1HC
sip_number: 48
title: CDS Baseline Plus SRC — SquadOps v0.7.x
status: implemented
author: Framework Committee
approver: null
created_at: '2025-12-02T22:55:00Z'
updated_at: '2025-12-06T10:54:52.655978Z'
original_filename: SIP-CDS-Baseline-Plus-SRC-v0-7-x.md
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

### 3.2 Agent actions were not standardized  
Lead, Strategy, Dev, QA, and Data agents each logged work differently.

### 3.3 PIDs were not indexed  
Processes were not connected to their documentation, tests, governance artifacts, or tagging specifications. (PID indexing deferred to v0.8)

### 3.4 No API for runtime visibility  
Without an explicit REST surface, no subsystem can reliably interact with or observe cycle execution.

### 3.5 No unified source-of-record  
Artifacts, tasks, PIDs, and governance lived in scattered places.

CDS must unify these structures to support coherent long-running execution.

---

# 4. Scope

v0.7.x delivers:

- A formalized CDS schema for cycles and tasks (enhanced `execution_cycle` and `agent_task_log` tables)
- A unified task logging mechanism used by all agents (via Runtime API)
- A stable **Runtime REST API** surface integrated directly into the system (cycles, tasks, agents, runtime state, scheduler)
- Project‑agnostic execution behavior

**Deferred to v0.8:** PID index tables, pulses API, artifacts API, `squad_id` field  

This SIP describes the data structures, API surface, and logging conventions required to achieve that.

---

# 5. Design Overview

### 5.1 Unified Execution Model  
All projects use the same model:

- A **cycle** represents an execution attempt  
- **Tasks** represent units of work performed by agents  
- **PIDs** represent governed processes (via `process_registry` table)
- The CDS stores the metadata and associations  
- The Runtime API surface exposes this information to any service (agents use API, not direct DB access)  

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
- cycle_id (renamed from `ecid` in SIP-0048)  
- name  
- goal  
- start_time  
- end_time  
- status  
- inputs (JSON: PIDs, repo, branch)

Note: `squad_id` deferred to v0.8 - keeping single squad assumption for v0.7.x  
Note: Table renamed from `execution_cycle` to `cycle` in SIP-0048 implementation.

## 6.2 Task Log Table (`agent_task_log`)
Standardized agent-based actions:
- task_id  
- cycle_id (renamed from `ecid` in SIP-0048)  
- agent_id  
- task_name  
- pid (nullable)  
- description   
- start_time  
- end_time  
- status  
- artifacts (array)  
- metrics (JSON)  
- dependencies (array)

Note: Table name remains `agent_task_log` (no rename). Uses `agent_id` for agent identification (not role normalization).  

## 6.3 PID Registry (`process_registry`)
- pid  
- process_name  
- status  
- last_updated_version  
- change_notes  

Note: Table name remains `process_registry` (no rename). PID index tables deferred to v0.8.

---

# 7. PID Indexing Requirements

**Deferred to v0.8**

PID index tables and population utilities are deferred to v0.8. The `process_registry` table exists and will be used as-is for v0.7.x.

---

# 8. Task Logging Requirements

All agents must use a unified task logging helper that:

- Logs start and end  
- Records `agent_id` and PID  
- Attaches artifacts  
- Captures metrics  
- Supports dependencies  
- Writes into `agent_task_log` table via Runtime API (no direct DB access)  

This ensures coherent historical reconstruction and maintains separation of concerns (agents use API, not direct database access).

---

# 9. Runtime REST API Surface  

The Runtime API (renamed from `task-api` to `runtime-api`) provides a unified interface for cycle runtime visibility. The following API surface is required to be implemented in v0.7.x.

---

## 9.1 Cycles

### Create a Cycle  
**POST** `/api/v1/cycles`

### Get Cycle State  
**GET** `/api/v1/cycles/{cycle_id}`

### List Cycles  
**GET** `/api/v1/cycles?status=running&limit=20`

### Control a Cycle  
**POST** `/api/v1/cycles/{cycle_id}/actions`  
(actions: pause, resume, cancel)

---

## 9.2 Pulses

**Deferred to v0.8**

Pulse-related endpoints are deferred to v0.8.

---

## 9.3 Tasks

### List Pending Tasks  
**GET** `/api/v1/cycles/{cycle_id}/tasks/pending`

### Submit Task Result  
**POST** `/api/v1/tasks/{task_id}/results`

---

## 9.4 Artifacts

**Deferred to v0.8**

Artifact-related endpoints are deferred to v0.8.

---

## 9.5 Agents

### List Agents  
**GET** `/api/v1/agents`

### Get Agent Runtime State  
**GET** `/api/v1/agents/{agent_id}/state`

---

## 9.6 Runtime State

### Get Cycle Runtime State Snapshot  
**GET** `/api/v1/cycles/{cycle_id}/runtime`

---

## 9.7 Scheduler / Coordination

### Scheduler Health + Queues  
**GET** `/api/v1/scheduler/status`

Note: Pulse coordinator endpoints deferred to v0.8.

---

# 10. Executive Summary — Deliverables

v0.7.x must produce:

1. **Formal CDS Schema** (enhanced `execution_cycle` and `agent_task_log` tables)
2. **Unified Task Logging Helper** (agents use Runtime API, not direct DB access)
3. **Runtime REST API Surface** (cycles, tasks, agents, runtime state, scheduler - pulses and artifacts deferred to v0.8)

**Deferred to v0.8:**
- PID index tables and population utilities
- Pulses API endpoints
- Artifacts API endpoints
- `squad_id` field in `execution_cycle` table

These together establish CDS as the reliable operational Source‑of‑Record for v0.7.x.

---

# 11. Definition of Done

The release is complete when:

- All CDS schema components migrate cleanly (enhanced `execution_cycle` and `agent_task_log` tables)
- All agents use the task logging helper (via Runtime API)
- The Runtime REST API surface is implemented (cycles, tasks, agents, runtime state, scheduler)
- Any project can retrieve and act upon its complete execution context through CDS
- `process_registry` table is verified and used as-is

**Deferred to v0.8:**
- PID index tables and population
- Pulses and Artifacts API endpoints
- `squad_id` field

CDS becomes the structural backbone enabling continuous, governed, multi‑cycle autonomous execution for v0.7.x.


