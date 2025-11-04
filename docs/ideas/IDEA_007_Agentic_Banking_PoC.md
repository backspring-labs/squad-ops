
# IDEA-007: Agentic Banking PoC Build Plan

**Date:** 2025-10-15  
**Project:** Squad Ops — Secure Agentic Delegation Prototype  
**Owner:** Jason Ladd  
**Status:** Draft  

---

## 🎯 Objective
To build a *proof-of-concept* demonstrating secure, verifiable delegation of limited banking operations to a lightweight AI agent **without exposing consumer credentials or verifiable credentials (VCs)**.

This PoC will validate:
- Cryptographically scoped delegation (ZCAP or GNAP)  
- Integration with Open Banking / FDX-style mock APIs  
- Agent orchestration via Squad Ops (Max-led coordination)  
- Full telemetry capture and revocation handling  

---

## 🧩 Context & Purpose
This IDEA tests how Squad Ops can serve as an orchestrator and development framework—not a delegated authority—for **agentic banking prototypes**.  
The goal is to simulate how a personal AI agent could securely act within defined limits using derived proofs instead of direct credentials.

---

## 🔧 Repo Type & Entry Point
| Parameter | Value |
|------------|--------|
| **Repo URL** | _New (local PoC repo)_ |
| **SquadOps Mode** | Build / Validate |
| **Lifecycle Phase** | Prototype / Validation |
| **Entry Point** | Neo initializes the code spine (Python + FastAPI) |

---

## 🧠 Squad Role Assignments

| Role | Responsibility |
|------|----------------|
| **Max** | Oversees PoC build orchestration; manages task assignments and progress tracking. |
| **Nat** | Defines the conceptual and product framing; ensures alignment with ITA principles. |
| **Neo** | Builds the delegation proof engine, OIDC mock, and bank API. |
| **EVE** | Develops automated tests for delegation enforcement, revocation, and telemetry. |
| **Data** | Manages telemetry ingestion, metrics visualization, and operational logging. |
| **Quark** | Tracks PoC cost, resource usage, and inventory metrics. |
| **Marvin** | Ensures sandbox isolation and security boundary enforcement. |

---

## 🧱 Core Deliverables

| Deliverable | Description |
|--------------|--------------|
| **1. Mini Test Agent (`agent_min.py`)** | Lightweight AI agent that performs limited operations using scoped delegation proofs. |
| **2. Delegation Proof Engine** | Generates derived credentials (ZCAP/GNAP) and revocation registries. |
| **3. Mock Bank API (`bank_mock.py`)** | FDX/FAPI-compliant local API for testing consent-based access. |
| **4. Consent & Auth Server** | OIDC/FAPI server handling token issuance and scope enforcement. |
| **5. Test Scenarios (`test_scenarios.yaml`)** | Automated tests validating permission scope, revocation, and anomaly handling. |
| **6. Telemetry Dashboard (`telemetry_dashboard.json`)** | Prometheus/Grafana configuration for monitoring agent and server events. |
| **7. Documentation (`README_IDEA007.md`)** | Overview, setup steps, and outcome metrics. |

---

## 🧠 Mini Test Agent Specifications

**Purpose:** Simulate a personal banking assistant under strict cryptographic delegation.  

**Key Functions:**
- Parse `delegation_proof.json` and enforce its scope.  
- Request OIDC tokens using GNAP or ZCAP proofs.  
- Execute permitted mock transactions (balance check, internal transfer).  
- Handle revocation gracefully; shut down when revoked or expired.  
- Log all operations to telemetry for EVE and Data.  

**Stack:**
- Language: Python 3.11+  
- Model: TinyLlama / Phi-2 / DistilGPT2 (run locally via llama.cpp or ctransformers)  
- API Layer: FastAPI / Prefect Tasks  
- Security: DPoP or mTLS with proof-of-possession  
- Telemetry: OpenTelemetry SDK + Prometheus  

---

## 📈 Success Metrics
1. **Functional:** 100% pass rate on delegation and revocation test suite.  
2. **Security:** No exposure of consumer VC or root keys.  
3. **Performance:** Agent latency < 500ms per authorized transaction.  
4. **Telemetry:** Complete audit trail of all authorization events.  

---

## 🔁 Warm Boot Cycle Plan

| Cycle | Objective | Owner |
|--------|------------|-------|
| **1** | Create mock bank API and OIDC server | Neo |
| **2** | Implement delegation proof issuance (ZCAP/GNAP) | Neo |
| **3** | Build and containerize mini test agent | Max + Neo |
| **4** | Run EVE’s automated test suite | EVE |
| **5** | Integrate telemetry & visualization | Data |
| **6** | Final validation and documentation | Nat + Max |

---

## 🚀 Next Steps
1. Initialize `agentic_banking_poc` repo with SquadOps PID spine.  
2. Implement basic delegation proof engine.  
3. Develop `agent_min.py` and link to mock API.  
4. Run tests for revocation and telemetry tracking.  
5. Document findings for SIP submission.

---

**End of IDEA-007 Document**
