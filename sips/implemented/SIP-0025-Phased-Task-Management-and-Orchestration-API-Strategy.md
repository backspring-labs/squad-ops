---
sip_uid: "17642554775901562"
sip_number: 25
title: "Phased-Task-Management-and-Orchestration-API-Strategy"
status: "implemented"
author: "Max (Governance)"
approver: "None"
created_at: "2025-10-09T00:00:00Z"
updated_at: "2025-11-27T10:12:48.893693Z"
original_filename: "SIP-025_Phasing_Task_Management_and_Orchestration_API.md"
---

# 🧩 Squad Improvement Proposal (SIP-025)
## Title: Phased Task Management and Orchestration API Strategy
**Author:** Max (Governance)  
**Contributors:** Neo, Data, Nat, EVE  
**Date:** 2025-10-09  
**Status:** Draft  
**Version:** 1.0  

---

## 🎯 Objective
To establish a **multi-phase task management and orchestration strategy** that allows SquadOps to start lightweight—with simple Postgres tracking and a custom API—and scale seamlessly to Prefect (or any future orchestrator) without breaking existing agent workflows.

This SIP formalizes the design of:
1. The **phased task management roadmap** (DB → Prefect).  
2. The **SquadOps API layer** that abstracts away orchestration internals.  
3. The **governance model** that ensures continuity across WarmBoot and Project ECIDs.

---

## 🔍 Background
Early SquadOps prototypes relied on manual task logging in Postgres and Markdown files for traceability.  
As squads scale to multi-agent, multi-phase operations, a proper orchestration system is required to manage dependencies, retries, and flow visualization.

Direct integration with Prefect, however, risks:
- Hard-coupling agents to one orchestration backend  
- Exposing orchestration tokens and runtime schemas  
- Reducing flexibility to migrate or downgrade in air-gapped setups  

Therefore, a **SquadOps Orchestration API** will serve as a thin, persistent layer that mediates between agents and the chosen orchestration engine.

---

## 🧩 Phase Plan Overview

| Phase | Title | Scope | Objective |
|-------|--------|--------|-----------|
| **Phase 1** | Lightweight Ledger Mode | API + Postgres only | Capture agent task lifecycle with minimal infra |
| **Phase 2** | Prefect Integration | API + Prefect backend | Add orchestration, retries, DAGs, and phases |
| **Phase 3** | Distributed Mode | API + Prefect + RMQ federation | Multi-squad scaling with live feedback and governance hooks |

---

## 🧱 Phase 1 — Lightweight Ledger Mode

### Components
- `FastAPI` service at `/api/v1/tasks`
- `Postgres` tables for task ledger
- Optional `RabbitMQ` for notifications

### Schema
```sql
CREATE TABLE task_log (
    id SERIAL PRIMARY KEY,
    task_id TEXT UNIQUE,
    pid TEXT,
    ecid TEXT,
    agent TEXT,
    phase TEXT,
    status TEXT,
    priority TEXT,
    description TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTERVAL,
    artifacts JSONB,
    dependencies TEXT[],
    error_log TEXT
);
```

### Example Endpoints
| Endpoint | Method | Purpose |
|-----------|--------|----------|
| `/api/v1/tasks/start` | POST | Record task start |
| `/api/v1/tasks/complete` | POST | Record completion + artifacts |
| `/api/v1/tasks/fail` | POST | Log errors, mark failed |
| `/api/v1/tasks/state/{task_id}` | GET | Query task status |

Agents interact *only* with these endpoints; the API writes directly to the DB and publishes events to RabbitMQ for UI updates.

---

## 🧠 Phase 2 — Prefect Integration Layer

### Concept
Add a **Prefect Adapter** inside the SquadOps API.  
The external contract remains identical, but now the API forwards state transitions to Prefect’s REST API.

### Adapter Example
```python
class PrefectAdapter:
    BASE_URL = "http://prefect-server:4200/api"
    TOKEN = os.getenv("PREFECT_API_TOKEN")

    async def set_state(self, payload, state):
        data = {"state": state, "message": payload.get("msg", "")}
        task_run_id = payload["prefect_run_id"]
        r = await httpx.post(
            f"{self.BASE_URL}/task_runs/{task_run_id}/set_state",
            headers={"Authorization": f"Bearer {self.TOKEN}"},
            json=data,
            timeout=10,
        )
        r.raise_for_status()
        return task_run_id
```

### Flow
```
Agents → SquadOps API → {Postgres Ledger + Prefect Adapter + RMQ}
```

Prefect becomes the authoritative orchestration state machine while the local DB remains the governance ledger.

---

## ⚙️ Phase 3 — Distributed Orchestration and Scaling

- Enable **multiple squads or nodes** to report into the same orchestration namespace.  
- Add a **Task Governor Flow** in Prefect to monitor queue depth and throttle load.  
- Integrate **Quark** for cost ceilings and **Max** for escalation control.  
- Persist ECID tags for each Prefect flow run to unify metrics with governance.

---

## 🧩 SquadOps API Design (Stable Contract)

### Purpose
Provide a **future-proof abstraction** for all task orchestration events.

### Core Endpoints
| Method | Path | Function |
|---------|------|-----------|
| `POST` | `/api/v1/tasks/start` | Agent declares task start |
| `POST` | `/api/v1/tasks/complete` | Report success & artifacts |
| `POST` | `/api/v1/tasks/fail` | Report failure |
| `GET` | `/api/v1/tasks/state/{id}` | Query task status |
| `POST` | `/api/v1/flows/trigger` | Launch multi-phase or Prefect flow |
| `GET` | `/api/v1/metrics/summary` | Aggregate status and performance |

All responses include:
```json
{
  "task_id": "TID-NEO-001",
  "ecid": "ECID-WB-007",
  "pid": "PID-001",
  "state": "Completed",
  "source": "db" // or "prefect"
}
```

### Internal Adapters
- **DBAdapter:** Writes/reads Postgres  
- **PrefectAdapter:** Calls Prefect API (Phase 2+)  
- **RMQAdapter:** Publishes squad-wide signals (optional)  

Agents never need Prefect credentials or internal schema knowledge.

---

## 🧭 Governance Integration
- **Max:** Monitors ECID + run_type across all tasks via API dashboards  
- **Quark:** Augments each `/complete` call with cost metrics  
- **EVE:** Attaches test coverage evidence to artifacts  
- **Nat & Joi:** Use task summaries to evaluate PRD and UX quality per ECID

---

## 🧱 Benefits
- 🚀 **Progressive enhancement:** Start simple, evolve seamlessly  
- 🔒 **Security isolation:** Prefect tokens remain internal  
- 🧠 **Governance continuity:** Same API across WarmBoot and Project runs  
- 🧩 **Interchangeable backend:** Replace Prefect with Temporal, Dagster, etc.  
- 🧾 **Traceability:** Unified ledger anchored by PID + ECID  

---

## 🧩 Next Steps
1. Implement `/api/v1/tasks` FastAPI service with DBAdapter (Phase 1).  
2. Add PrefectAdapter behind feature flag for Phase 2 testing.  
3. Update SIP-024 (Execution Cycle Protocol) to reference ECID linkage.  
4. Integrate with the SOC dashboard for visualization.  
5. Validate API contract stability across at least two orchestrator backends.  

---

**Status:** 🧠 Draft for Implementation  
**Effective Date:** TBD (post-SIP-024 adoption)  
**Reference Docs:**  
- `SIP-024_Execution_Cycle_Protocol.md`  
- `Doc_Traceability_Protocol.md`  
- `Git_Workflow_Protocol.md`  
- `SquadOps_Console.md`
