# 📑 warm-boot vs Iterative Squad Development

## 1. warm-boot Cycles
warm-boot is about **squad-level configuration refinement** — not feature delivery.

- **Purpose:** Benchmark and tune the *squad itself* (agents, roles, comms, config parameters).  
- **When triggered:** At startup, after major squad config changes, or when testing a new reference app.  
- **Inputs:**  
  - Agent roles + reasoning styles  
  - Infra + comms setup  
  - Reference app spec (e.g., HelloSquad, Fitness Tracker)  
- **Outputs:**  
  - Telemetry logs (time, errors, message count, quality)  
  - Performance scorecard  
  - Change log for config adjustments  
- **Registry:** Results tied to **warm-boot Run IDs** (e.g., `WB-001`) and **PIDs** for traceability.

🔑 warm-boot = **“How good is the squad config?”**

---

## 2. Iterative Squad Development (SDLC)
The iterative dev cycle is about **application feature evolution**.

- **Purpose:** Build, test, and release apps in progressive increments.  
- **When triggered:** Normal development work on apps (e.g., HelloSquad → Fitness Tracker).  
- **Inputs:**  
  - Business process docs (BP-XXX)  
  - Use cases (UC-XXX)  
  - Test cases (TC-XXX)  
  - Existing codebase + infra  
- **Outputs:**  
  - Incremental features or bugfixes  
  - Updated PIDs in the registry  
  - New tests (functional + comms/health)  
- **Registry:** Linked to **PID registry** + version control tags (e.g., `v0.2.1`).  

🔑 Iterative SDLC = **“How good is the app we’re building?”**

---

## 3. Relationship Between the Two
- **warm-boot** evaluates/tunes the squad as a *meta-system* (how the team is configured).  
- **SDLC cycles** drive forward *application delivery*.  
- They share the same **PID + registry system** so that both squad changes and app changes are traceable.  
- You might run a **warm-boot cycle before or after a dev sprint** to see if adjustments to agents/config improve delivery quality.  

---

## 4. Example Workflow
1. Run **WB-001** with Max + Neo on HelloSquad.  
   → Logs show Neo overloaded, so config changes are made.  
2. Enter **Dev Cycle 002** for HelloSquad.  
   → Add HTML response + API test (PID-001).  
3. Run **WB-002** to measure if new config (e.g., giving EVE more checkpointing authority) improves performance.  
4. Continue **Dev Cycle 003** to add features, refine tests, etc.  

---

## 5. Why Both Matter
- **warm-boot** prevents squads from stagnating or drifting — ensures *operational excellence*.  
- **Iterative SDLC** ensures squads continue to deliver *user value*.  
- Together, they create a **dual feedback loop**:
  - *Inner loop:* Dev cycles (fast, feature-focused).  
  - *Outer loop:* warm-boot cycles (meta, config-focused).  
