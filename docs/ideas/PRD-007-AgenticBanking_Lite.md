# 🏦 **PRD-007: Agentic Banking PoC (Lite Edition)**
*(Max + Neo)*

---

## 📘 **Overview**
A lightweight proof-of-concept showing how a **single delegated agent (Neo)** can securely perform basic banking operations under **Max's orchestration**, without exposing credentials.  
The goal is a small, testable example demonstrating scoped delegation and revocation handling — minimal infra, maximum clarity.

---

## 🎯 **Objectives**

| # | Goal | Success Metric |
|---|------|----------------|
| 1 | Demonstrate secure, scoped agent delegation | 100 % success in authorized API calls |
| 2 | Enforce revocation and proof expiration | Agent halts on revoked/expired proof |
| 3 | Capture simple telemetry for traceability | Every action logged with timestamp |
| 4 | Build and run locally with no dependencies beyond FastAPI + SQLite | Repo spins up in < 2 min |

---

## 🧩 **Scope**

### In-Scope
- Minimal **mock bank API** (`/balance`, `/transfer`)  
- **Delegation proof file** (`delegation_proof.json`) scoped to specific endpoints  
- **Mini agent** (`agent_min.py`) that reads the proof, performs permitted calls, and respects expiry  
- **Max orchestrator script** (`max_controller.py`) assigning tasks and monitoring Neo  
- Basic telemetry log file (`telemetry.log`)  

### Out-of-Scope
- Full OIDC/FAPI server  
- Prometheus, Prefect, or Grafana integration  
- Multi-agent orchestration or compliance automation  

---

## ⚙️ **Functional Requirements**

| ID | Requirement | Owner | Output |
|----|--------------|--------|--------|
| FR-001 | Create minimal FastAPI server simulating bank API | Neo | `bank_mock.py` |
| FR-002 | Build delegation proof parser & verifier | Neo | `delegation_engine.py` |
| FR-003 | Develop mini agent that reads proof and performs allowed operations | Neo | `agent_min.py` |
| FR-004 | Implement Max controller to assign and monitor Neo tasks | Max | `max_controller.py` |
| FR-005 | Log all actions with timestamps to a text or JSON log | Neo + Max | `telemetry.log` |
| FR-006 | Add simple revocation test (delete proof → stop agent) | Max | Manual trigger or unit test |

---

## 🧠 **Agent Roles**

| Agent | Responsibilities |
|--------|------------------|
| **Max** | Assigns tasks, loads the proof file, monitors Neo's status, and terminates process on revocation. |
| **Neo** | Runs the agent logic, calls permitted API endpoints, and writes logs. |

---

## 🧱 **System Overview**

```
+------------------+         +----------------+         +------------------+
| max_controller.py|  --->  | agent_min.py   |  --->  | bank_mock.py     |
+------------------+         +----------------+         +------------------+
         ↑                          |                           |
         |-------------- telemetry.log <-------------------------+
```

---

## 🔒 **Security & Constraints**
- Delegation proof stored as JSON with fields: `scope`, `expiry`, `allowed_endpoints`.  
- No sensitive data or real credentials.  
- API only accepts local connections.  
- Proof expiry auto-checked per request.

---

## 📊 **Success Criteria**

| Metric | Target |
|---------|--------|
| Authorized calls succeed | 100 % |
| Unauthorized calls blocked | 100 % |
| Agent shutdown on revocation | < 1 s |
| Local runtime | < 5 min setup, < 50 MB RAM |

---

## 🧩 **Deliverables**

| File | Description |
|------|-------------|
| `bank_mock.py` | FastAPI server with `/balance` and `/transfer` |
| `delegation_engine.py` | Validates scope & expiry |
| `agent_min.py` | Executes delegated actions |
| `max_controller.py` | Orchestrates tasks and revocation |
| `delegation_proof.json` | Sample delegation proof |
| `telemetry.log` | Execution log with timestamps |

---

## 🧱 **Tech Stack**
- **Python 3.11+**  
- **FastAPI** (mock server)  
- **Requests** (client calls)  
- **SQLite** (optional telemetry DB or flat log file)

---

## 🚀 **Next Steps**
1. Initialize repo `agentic_banking_lite`.  
2. Neo builds `bank_mock.py` and `agent_min.py`.  
3. Max implements controller and revocation logic.  
4. Run simple local test:  
   ```bash
   uvicorn bank_mock:app --reload  
   python max_controller.py
   ```  
5. Verify proof expiration stops agent actions.

---
