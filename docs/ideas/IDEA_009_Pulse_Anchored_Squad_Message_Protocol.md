# IDEA-009: Pulse-Anchored Squad Message Protocol (SMP)
*A foundation for time-synchronized, process-aware communication across autonomous agents.*

---

## Objective
Define a minimal, evolvable foundation for **message passing**, **context framing**, and **temporal synchronization** among agents in a squad.  
The goal is to improve collaboration, maintain context continuity, and enable autonomous build feedback loops — without over-complicating current squad development.

---

## Motivation
As multi-agent squads mature, they need more than task-based prompting; they need **shared temporal rhythm** and **process traceability** to coordinate effectively.  
This idea introduces a **Pulse-Anchored Squad Message Protocol (SMP)** — a structure that binds agent communication to two contextual axes:

- **Pulse** → the *temporal context* (when the squad is thinking)  
- **PID** → the *process context* (what the squad is doing)

Together, these form a 2D coordinate system for coherent, self-organizing squad cognition — mirroring both **biological neural communication** and **network protocol design**.

---

## Conceptual Layers (Initial Sketch)

| Layer | Function | Analogy |
|-------|-----------|---------|
| **1. Signal** | Raw message delivery via queue or API call | Neuronal spikes / network transport |
| **2. Task Frame** | Defines sender, receiver, and task scope (`pid`, `task_type`, `target_agent`) | Data link / frame header |
| **3. Context Layer** | Maintains shared context (`pulse_id`, dependencies, build state) | Session / transport layer |
| **4. Feedback Layer** | Encodes completion, confidence, or error info | Acknowledgment / error control |
| **5. Orchestration Layer** | Routes tasks, manages escalation, and synchronizes context | Routing / application logic |

---

## Dual Anchors of Context

### 🧭 PID — Process Identity
- **Purpose:** Anchor *what* is being done.  
- **Scope:** Long-lived — persists across multiple pulses.  
- **Lifecycle:** From process initiation → completion (e.g., one API build or test cycle).  
- **Analogy:** OS process ID or workflow instance.  
- **Role:** Enables traceability, auditability, and aggregation of quality metrics.  

Example:
```json
"pid": "PID-00721",
"business_process": "api_build_and_deploy"
```

---

### ⚡ Pulse — Temporal Context
- **Purpose:** Anchor *when* the squad is acting — the shared cognitive rhythm.  
- **Scope:** Short-lived — spans a single operational cycle or sync interval.  
- **Lifecycle:** Created, synchronized, and terminated automatically.  
- **Analogy:** A heartbeat or neural oscillation coordinating distributed activity.  
- **Role:** Synchronizes cognition, telemetry, and message grouping.  

Example:
```json
"pulse_id": "pulse-2025-10-18T17:00Z"
```

---

## Pulse + PID = 2D Squad Cognition
| Dimension | Represents | Example |
|------------|-------------|----------|
| **Pulse** | Temporal coherence (squad heartbeat) | “This was the 17:00Z cycle” |
| **PID** | Process lineage (task identity) | “This belongs to the API build process” |

Every message or event can thus be located precisely:
> `(pulse_id, pid)` → *When and what the squad was thinking.*

This separation gives the squad both **temporal order** and **semantic continuity** — like neurons firing in rhythm while encoding different percepts.

---

## Message Envelope (MVP)
```json
{
  "pulse_id": "pulse-2025-10-18T17:00Z",
  "pid": "PID-00721",
  "from_agent": "max",
  "to_agent": "neo",
  "task_type": "api_build",
  "state": "in_progress",
  "payload": {
    "description": "Generate FastAPI endpoint for new user creation"
  },
  "feedback": null,
  "timestamp": "2025-10-18T17:00:00Z"
}
```
This envelope binds every message to a **process lineage** and a **temporal frame**, enabling synchronized, inspectable, and replayable communication.

---

## Implementation Path
1. **Phase 1:**  
   - Implement Layers 1–2 (Signal + Task Frame) with a lightweight queue (e.g., RabbitMQ or in-memory).  
   - Tag every message with a live `pulse_id` and `pid`.  
2. **Phase 2:**  
   - Introduce a simple `pulse_summary` log to measure performance and coherence per pulse.  
   - Track messages grouped by PID for lifecycle analytics.  
3. **Phase 3:**  
   - Integrate with **Neural Pulse Protocol (NPP)** for telemetry-driven feedback.  
   - Promote this concept into **SIP-0XX: Squad Message Protocol (SMP)** when the system stabilizes.  

---

## Benefits
- Provides **traceability** across time and process boundaries.  
- Enables **contextual learning** and auto-improvement loops.  
- Lays groundwork for **autonomous orchestration** and **multi-agent self-awareness**.  
- Supports direct mapping to telemetry dashboards and replay visualization.

---

## Summary
The **Pulse-Anchored Squad Message Protocol** introduces the simplest viable substrate for message passing, temporal synchronization, and process identity in SquadOps.  
By treating `pulse_id` as *when* and `pid` as *what*, the squad gains both rhythm and memory — the foundations of truly autonomous collaboration.
