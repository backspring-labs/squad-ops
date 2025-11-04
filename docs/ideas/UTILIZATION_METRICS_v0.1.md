# ⚙️ **SquadOps — Agent Utilization & Metrics Framework (v0.1)**
*A guide for measuring, visualizing, and optimizing agent workload utilization across logical and physical dimensions.*

---

## 🧠 **1. Purpose**

Define a consistent framework for measuring when an agent is **fully utilized**, identifying **bottlenecks** (logical or resource-based), and improving performance across **Execution** and **WarmBoot** cycles.

---

## 🧩 **2. Definition of “Fully Utilized”**

An agent is **fully utilized** when it spends nearly all of its available cycle time performing **productive execution** (not waiting or blocked), **without quality degradation** or excessive latency.

---

## 🧭 **3. Agent State Model**

| **State** | **Description** |
|------------|-----------------|
| **Active-Exec** | Actively executing assigned tasks (coding, testing, writing). |
| **Active-Comms** | Performing non-blocking communications or checkpoints that contribute to progress. |
| **Waiting-Deps** | Blocked on another agent’s output or external I/O. |
| **Governance-Hold** | Awaiting approval, escalation, or override from Max. |
| **Idle-Available** | Ready but unassigned. |

---

## 📊 **4. Core Metrics (per agent, per cycle)**

| **Metric** | **Formula** | **Meaning** |
|-------------|-------------|-------------|
| **Busy Time** | `time(Active-Exec) + time(Active-Comms)` | Total productive time. |
| **Utilization (U)** | `Busy / (Cycle Time – Maintenance)` | Logical activity ratio. |
| **Wait Ratio (W)** | `(Waiting-Deps + Governance-Hold) / Cycle Time` | Portion of time spent blocked. |
| **Throughput (T)** | `completed_tasks / Cycle Time` | Productivity per unit time. |
| **Quality Factor (Q)** | Weighted composite: test pass rate, defect density, governance overrides. |
| **Effective Utilization (U_eff)** | `U × Q` | True productive utilization adjusted for quality. |
| **Context Switch Overhead (CSO)** | `count(checkpoints + task swaps) × avg(switch cost)` | Cognitive friction due to interruptions. |

---

## 🎯 **5. Target Thresholds**

| **Metric** | **Optimal Range** | **Guidance** |
|-------------|------------------|--------------|
| **U** | 0.80 – 0.92 | Peak efficiency band before queueing penalties. |
| **U_eff** | ≥ 0.75 | Adjusted for quality; sustainable performance. |
| **W** | ≤ 0.15 | Avoid excessive waiting or dependencies. |
| **CSO** | Stable / declining | Indicates reduced churn. |

A squad is approaching **full utilization** when active agents sustain  
**U ≈ 0.85–0.9** and **Q ≥ 0.85** without spikes in latency or quality loss.

---

## 🧮 **6. Deriving Metrics from Logs**

Use the structured task logs (`agent`, `task_id`, `state`, `start_time`, `end_time`) to compute durations by state, then roll up by agent:

```sql
SELECT
  agent_name,
  SUM(EXTRACT(EPOCH FROM end_time - start_time)) FILTER (WHERE state='Active-Exec') AS exec_time,
  SUM(EXTRACT(EPOCH FROM end_time - start_time)) FILTER (WHERE state='Waiting-Deps') AS wait_time,
  ...
FROM agent_task_logs
GROUP BY agent_name;
```

Then compute `U`, `W`, `T`, `Q`, and `U_eff` for each agent per cycle.

---

## 📈 **7. SOC Dashboard Recommendations**

- **Gauges:** Live `U` and `U_eff` per agent (rolling 60 min).  
- **Stacked Bars:** Time distribution by state (Active, Waiting, Idle).  
- **Sparklines:** Defects / overrides per 100 tasks to show quality drift.  
- **Alerts:**  
  - `U > 0.92 && latency↑` → possible overload.  
  - `U < 0.70 && resources < 60 % used` → idle potential.

---

## 🧠 **8. Container-Level Correlation & Resource Health**

Logical utilization means little without physical context.  
Pair agent metrics with container telemetry to separate orchestration issues from resource bottlenecks.

| **Plane** | **Key Metrics** | **Goal** |
|------------|-----------------|----------|
| **Logical (Agent)** | Busy %, Wait %, U_eff, CSO | Maximize useful agent time. |
| **Physical (Container)** | CPU %, GPU %, Memory, I/O, Network Latency | Optimize runtime throughput. |

**Examples**

| **Symptom** | **Likely Cause** | **Remedy** |
|--------------|------------------|-------------|
| High Wait % + High GPU Usage | Model latency / token backlog | Reduce context, batch requests, scale GPU. |
| High Wait % + Low Resource Usage | Dependency / orchestration delay | Improve task scheduling. |
| High Memory % + Restarts | Context bloat or leaks | Flush embeddings, reset sessions. |
| High Network Latency | External API delay | Move model local or cache responses. |

---

## 🧩 **9. Agent Efficiency Index (AEI)**

Combine logical and physical metrics:

```
AEI = U_eff × (1 - Resource_Saturation_Penalty)
```

Where:

```
Resource_Saturation_Penalty =
  (CPU% / 100)^α +
  (Memory% / 100)^β +
  (GPU_Queue_Time / Max_Allowed)^γ
```

An agent is **truly fully utilized** when both  
**U_eff ≥ 0.8** *and* **Resource_Saturation_Penalty ≤ 0.2**.

---

## 🧪 **10. Adaptive Resource Management**

1. **Dynamic Scaling** — spin up additional model workers as token latency grows.  
2. **Priority Queues** — favor short context tasks to keep pipelines flowing.  
3. **Agent-Aware Scheduling** — share expected token or compute load with the scheduler.  
4. **Health Pings** — agents include container telemetry in status updates so Max can rebalance tasks.

---

## 🧩 **11. Summary**

To achieve true squad-level performance, utilization must be viewed on **two axes**:  
**Agent throughput** and **Container health**.  
Maximizing both yields the highest sustained throughput without degradation — turning the squad into the **operating system of its own productivity**.
