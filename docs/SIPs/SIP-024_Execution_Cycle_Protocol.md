# 🧩 Squad Improvement Proposal (SIP-024)
## Title: Execution Cycle Protocol — Unified Governance for WarmBoots and Project Runs
**Author:** Max (Governance)  
**Contributors:** Nat, Data, Neo  
**Date:** 2025-10-09  
**Status:** Approved  
**Version:** 1.0  

---

## 🎯 Objective
To unify the governance, traceability, and data model for all execution cycles within SquadOps—covering **WarmBoot runs**, **Project Requests**, and future **experimental or tuning cycles**—under a single schema and identifier system.

This eliminates the fragmentation between internal benchmark runs and external project builds while preserving distinct governance and review controls for each context.

---

## 🔍 Background
Previous SquadOps iterations treated **WarmBoot runs** and **Project Requests** as separate processes with independent logging, governance, and artifact handling.  
This separation created redundant protocols and complicated traceability across versions.

To future-proof the framework, a **type-agnostic execution model** was needed so that both internal and external cycles could share the same lineage and monitoring infrastructure.

---

## 🧩 Proposal Summary
Introduce a universal **Execution Cycle Identifier (ECID)** and schema that represents any squad execution run—whether initiated automatically (WarmBoot) or manually (Project Request).

**Core Principles:**
1. Every execution is a cycle tied to a **PID (Process ID)**.  
2. Each cycle is uniquely identified by an **ECID (Execution Cycle Identifier)**.  
3. A simple **run_type** attribute distinguishes WarmBoot, Project, Experiment, or Tuning contexts.  
4. All governance, metrics, and artifacts reference `(PID, ECID)` as the composite key.

---

## 🧱 Data Model

### `execution_cycle` Table
```sql
CREATE TABLE execution_cycle (
    ecid TEXT PRIMARY KEY,
    pid TEXT NOT NULL,
    run_type TEXT CHECK (run_type IN ('warmboot','project','experiment','tuning')),
    title TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT now(),
    initiated_by TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT
);
```

### `task_log` Table (linked via ECID)
```sql
CREATE TABLE task_log (
    task_id TEXT PRIMARY KEY,
    pid TEXT,
    ecid TEXT REFERENCES execution_cycle(ecid),
    agent TEXT,
    phase TEXT,
    status TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTERVAL,
    artifacts JSONB,
    dependencies TEXT[],
    error_log TEXT
);
```

---

## 🧭 Governance and Workflow Integration

| Run Type | Governance Owner | Review Points | Outputs |
|-----------|------------------|---------------|----------|
| **warmboot** | Max | WarmBoot Review, RCA | Optimization Score |
| **project** | Max + Human Reviewer | Design & Acceptance Review | Release Artifacts |
| **experiment** | Max / Og | Optional | Learning Report |
| **tuning** | Neo / Data | Automated Metrics | Performance Deltas |

---

## 🧠 Naming Conventions

| Artifact | Naming Pattern | Example |
|-----------|----------------|----------|
| PRD | `PRD-{PID}-{ECID}.md` | `PRD-PID-001-ECID-REQ-2025-10-09-01.md` |
| Test Plan | `TP-{PID}-{ECID}.md` | `TP-PID-001-ECID-WB-007.md` |
| WarmBoot Log | `WBLOG-{ECID}.md` | `WBLOG-ECID-WB-007.md` |
| Metrics Summary | `MET-{PID}-{ECID}.json` | `MET-PID-001-ECID-WB-007.json` |

---

## 🧩 Git & Directory Alignment

| Layer | Example | Notes |
|--------|----------|-------|
| **Branch Naming** | `run/ECID-WB-007` | Each Execution Cycle = 1 branch |
| **Tagging** | `v0.1-ECID-WB-007` | Versioned outputs |
| **Folder Structure** | `/executions/{ECID}/` | Houses all linked artifacts |

---

## ⚙️ Integration Points

| System | ECID Usage |
|---------|------------|
| **SquadOps API** | Every `/task/start` and `/task/complete` includes `ecid` |
| **Prefect (or Orchestrator)** | `flow_run.name = ECID` |
| **Git Workflow** | Branches and tags use ECID for traceability |
| **SOC Dashboard** | Filters and aggregates by ECID |
| **Governance Logs** | RCA and Review reports grouped by ECID |

---

## 🚀 Benefits
- Unified ledger for all execution types  
- Simplified governance (run_type defines review flow)  
- Replayable, auditable history across all PIDs  
- Future-proof schema for scaling to multiple orchestrators  
- Consistent human-readable identifiers

---

## 🧩 Next Steps
1. Update the **SquadOps API** to include `ecid` as a required parameter for all task events.  
2. Migrate existing WarmBoot logs to `execution_cycle` schema.  
3. Update the **SOC Dashboard** to filter and group by ECID.  
4. Add ECID-based branching to the **Git Workflow Protocol**.  
5. Validate schema through next WarmBoot and first Project Request flow.

---

**Status:** ✅ Approved for implementation  
**Effective Date:** 2025‑10‑09  
**Reference Docs:** `Execution_Cycle_Protocol.md`, `Git_Workflow_Protocol.md`, `Doc_Traceability_Protocol.md`
