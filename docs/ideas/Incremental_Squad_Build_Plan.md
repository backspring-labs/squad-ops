# 🪜 Incremental Squad Build Plan

## Phase 1 — Base Infra + Mock Agents
- Bring up the core platform (RabbitMQ, Postgres, health checks, task logging).  
- Run **mock agents** to test comms, routing, and warm-boot logging.  
- Validate *infra works* before any real LLM is in the loop.  
- **Output:** `WB-001 Infra Baseline` report.

---

## Phase 2 — 2 Agents (HelloSquad)
- Introduce **Max (lead)** and **Neo (dev)**.  
- Real LLMs, but simple task: HelloSquad API + HTML page.  
- Validate:  
  - End-to-end assignment → execution → verification.  
  - Health page shows real `llm_mode=real`.  
  - PID registry + warm-boot log are working.  
- **Output:** `PID-001 v0.1` + `WB-002` report.

---

## Phase 3 — Add Agents Incrementally
- Add one new agent per cycle: QA, Data, Finance, Comms, Curator, Creative, Audit.  
- Each addition expands **HelloSquad** with a small but meaningful requirement:  
  - QA → adds automated test coverage beyond API/HTML basics.  
  - Data → logs/metrics aggregation (e.g., time to complete, tokens).  
  - Finance → cost logging for LLM calls.  
  - Comms → simple notification (Slack/email stub).  
  - Curator → gather context artifacts.  
  - Creative → tiny visual (ASCII logo on the HTML page).  
  - Audit → check traceability (PID, WB, artifacts).  
- Each step:  
  - Increment PID version (`PID-001 v0.2`, v0.3, …).  
  - New warm-boot run (`WB-003`, `WB-004`…) verifies integration.

---

## Phase 4 — Fully Formed Squad
- All 10 agents are online, roles assigned, routable rules working.  
- HelloSquad now demonstrates contributions from the whole squad.  
- This becomes your **golden reference app**.

---

## Phase 5 — Next App (Fitness Tracker)
- With a proven squad, move to a real testbed app (`PID-002 Personal Fitness Tracker`).  
- New PRD, new UC/TC, new scope — but the *squad profile is stable*.  
- First runs here prove the system can generalize beyond HelloSquad.

---

## 🔑 Why this path works
- **Safety:** Breaks the complexity into digestible checkpoints.  
- **Traceability:** Every phase tied to PID/WB for audit trail.  
- **Confidence:** You never move forward unless the last checkpoint is verifiably working.  
- **Learning:** Each new agent tests a different dimension (QA = quality, Finance = cost, Audit = governance).  

---
