# 📝 Change Request — Separate Agent Status from LLM Mode

## 📌 Summary
Introduce a clear separation between **Agent Status** (availability) and **LLM Mode** (type of backend).  
This avoids overloading the `status` field with multiple meanings and provides operators with clarity when managing agents that may be live but configured with mock interfaces.

---

## ✅ Current State
- Agents report a single `status` field in `/health/agents` (values: online, offline, unhealthy).  
- Operators need to distinguish between agents that are *healthy but running in mock mode* vs. those that are *live with a real LLM*.  
- Current workaround: encoding this detail in `notes` only.

---

## 🚨 Problem Statement
- Overloading `status` with mock/live semantics creates ambiguity.  
- Routing logic (e.g., Max deciding where to send tasks) risks dispatching tasks to mock-configured agents.  
- Operators need to pause agents for maintenance, which is not expressible with the current status alone.

---

## 🎯 Proposed Solution
### 1. Keep `status` focused on availability
Valid values:  
- `online` → agent container is up and responsive  
- `offline` → container not reachable  
- `unhealthy` → container reachable but failing checks  
- `paused` → agent is online but explicitly prevented from accepting tasks

### 2. Add new field: `llm_mode`
Valid values:  
- `real` → connected to a live model backend  
- `mock` → connected to a stub or simulated model  
- `hybrid` → local-first with optional premium consult fallback  
- `unset` → no LLM configured

### 3. Optional field: `model_primary`
Human-readable description of the configured model/service (e.g., `llama.cpp:Llama-3.2-3B-Q4`, `Claude 3.5`, `mock://llama`).

### 4. Task routing logic
- Dispatch only if: `status == online` **and** `llm_mode == real` **and** `accept_tasks == true`.  
- Explicitly exclude agents with `llm_mode == mock` unless the task is flagged as simulation-safe.

---

## 📂 Example Payload (`/health/agents`)

```json
[
  {
    "agent": "Max",
    "role": "Leader",
    "status": "online",
    "version": "1.0.0",
    "tps": 12,
    "llm_mode": "mock",
    "model_primary": "mock://llama",
    "notes": "Configured with Mock interface"
  },
  {
    "agent": "Neo",
    "role": "Dev",
    "status": "paused",
    "version": "1.0.0",
    "tps": 0,
    "llm_mode": "real",
    "model_primary": "CodeLlama-70B"
  }
]
```

---

## 🔑 Benefits
- **Clarity** → Status = availability, Mode = backend type.  
- **Routing Safety** → Max avoids dispatching tasks to mock agents by mistake.  
- **Operational Flexibility** → Agents can be paused without misrepresenting them as unhealthy.  
- **Auditability** → WarmBoot logs clearly separate operational status vs. LLM configuration.

---

## 🔄 Migration Steps
1. Extend health check response to include `llm_mode` and `model_primary`.  
2. Update `/health/agents` schema and API docs.  
3. Update routing logic in Lead (Max) to gate on both `status` and `llm_mode`.  
4. Update SquadOps Console UI:  
   - Keep existing status badges.  
   - Add a small badge for mock/hybrid/unset.  
   - Add a “Paused” pill for agents in paused state.  
5. Update WarmBoot logs to include `llm_mode`.

---

## 📅 Priority
**Medium-High** — improves operator clarity and prevents misrouting tasks.

---

## 👤 Requestor
Jason (Repo Owner)

## 👥 Approvers
- Max (Lead / Governance)
- Nat (Strat / Strategy)
- HAL (Audit)
