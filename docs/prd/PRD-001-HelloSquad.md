# 📄 Product Requirements Document — HelloSquad (PID-001)

## 1. Overview
**HelloSquad** is the inaugural reference app for SquadOps.  
It validates the end-to-end lifecycle of a two-agent squad:
- **Max (Lead)** assigns the task and verifies results.  
- **Neo (Dev)** implements a real FastAPI service and test suite.  

The HelloSquad app serves both an **API** and an **HTML page** that consumes that API, and it is logged as a **warm-boot run** tied to a unique **Process ID (PID)**.

---

## 2. Objectives
- Prove the minimal but complete SquadOps workflow:
  - Task assignment → execution → verification → logging.
- Enforce **PID tagging** for traceability across business docs, use cases, and tests.
- Integrate PID into the warm-boot cycle and PDR standard.
- Deliver a reusable reference for future apps.

---

## 3. Scope

### In Scope
- **API endpoint**  
  - `GET /api/hello`  
  - Returns JSON: `{ "message": "Hello, Squad!" }`

- **HTML page**  
  - `GET /hello`  
  - Displays greeting by fetching `/api/hello` via client-side JS.

- **Agents**  
  - Max (Lead): assignment, verification, logging.  
  - Neo (Dev): builds API + HTML + tests.

- **Tests**  
  - API test: `/api/hello` returns JSON.  
  - HTML test: `/hello` renders greeting from API.

- **Infra**  
  - RabbitMQ (comms), Postgres (logs), Health checks, Task logging schema.

### Out of Scope
- Additional agents beyond Lead + Dev.  
- UI console styling.  
- Scaling, HA, or security features.

---

## 4. Requirements

### Functional
1. **Task Assignment**  
   - Max issues a `TASK_ASSIGNMENT` message to Neo with PID included.  
   - Payload includes objective, acceptance criteria, and `warmboot_id`.

2. **Task Execution**  
   - Neo implements FastAPI with `/api/hello` and `/hello`.  
   - Includes pytest for API + HTML validation.

3. **Verification**  
   - Max confirms endpoints behave as expected.  
   - Issues `VERDICT verified`.

4. **Logging**  
   - All messages and status updates must be persisted with:  
     - `pid` (e.g., PID-001)  
     - `warmboot_id`  
     - `task_id`  
     - timestamps and verdict

5. **Health Reporting**  
   - `/health/agents` shows `status=online` and `llm_mode=real`.

### Non-Functional
- App must run under Docker Compose.  
- Execution cycle completes within one squad warm-boot iteration.  
- PID is **mandatory** in warm-boot logs and PDR compliance checks.

---

## 5. Deliverables
- **Source Code:**  
  - `hello.py` (FastAPI app)  
  - `test_api_hello.py`, `test_html_hello.py` (pytest)

- **Docs:**  
  - `BP-001-HelloSquad.md` (business process)  
  - `UC-001-HelloSquad.md` (use case)  
  - `TC-001-HelloSquad.md` (test case)

- **Registry:**  
  - `process_registry.md` entry: `PID-001: HelloSquad`

- **Artifacts:**  
  - warm-boot report `WB-001` with PID attached

---

## 6. Test Plan

### API Tests
- **TC-API-001:** GET `/api/hello` returns `200` + correct JSON.  
- **TC-API-002:** Wrong method (POST) returns `405`.

### HTML Tests
- **TC-HTML-001:** GET `/hello` renders page with greeting from API.  
- **TC-HTML-002:** API error → page displays error message.

### Integration Tests
- **TC-INT-001:** Lead assigns task (PID-001), Dev executes, Lead verifies, warm-boot logs all steps.

---

## 7. Acceptance Criteria
1. `/api/hello` returns correct JSON.  
2. `/hello` renders greeting in browser by calling API.  
3. All pytest cases pass.  
4. Health reports agents `online` + `llm_mode=real`.  
5. warm-boot log includes PID-001, task_id, warmboot_id, verdict.  
6. PDR check confirms PID assigned and traced across BP, UC, TC, and warm-boot log.

---

## 8. Risks & Mitigations
- **PID omission** → enforce schema validation in warm-boot log.  
- **HTML test fragility** → use retry/wait for DOM element `#greeting`.  
- **Nano resource constraints** → start with lightweight LLM.

---

## 9. Timeline (aligned with SquadOps cycle)
- **Phase 1: PID Proposal & Alignment**  
  - Assign PID-001, draft BP, UC, TC docs.  
- **Phase 2: Build & Test**  
  - Neo implements API + HTML + tests.  
- **Phase 3: warm-boot Run**  
  - Max assigns and verifies; run tagged `WB-001`.  
- **Phase 4: Retrospective**  
  - Capture learnings; update protocols if needed.  

---
