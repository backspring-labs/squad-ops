# ⚙️ Concurrency and Utilization Patterns for SquadOps

This guide outlines concurrency, utilization, and dependency management strategies to maximize squad productivity when executing a development plan.

---

## 1. Concurrency Models

- **Work Queue (classic MQ):**
  - Each agent consumes from a role-specific queue (`dev.tasks`, `qa.tasks`).
  - Simple and effective but requires back-pressure tuning (`prefetch`, `capacity`).
  
- **Token-bucket / Leaky-bucket:**
  - Agents have a credit system to limit concurrency (e.g., Finance allocates tokens for costly LLM calls).
  - Good for cost and rate-limiting.

- **Pipeline (producer–consumer chain):**
  - Sequential flow: Dev → QA → Audit → Lead.
  - Matches SDLC stages; can bottleneck if one link is slower.

- **Work-stealing / Pool:**
  - Pool of similar agents steal tasks from each other’s queues.
  - Maximizes utilization and avoids idle capacity.

---

## 2. Dependency Management

- **Topological ordering:**
  - Represent PID → UC → TC as a DAG.
  - Tasks only start when dependencies are satisfied.

- **Critical Path Method (CPM):**
  - Identify the longest chain of dependent tasks.
  - Assign capacity/priority to critical path tasks.

- **Parallelism with barriers:**
  - Allow concurrency until synchronization points (e.g., QA starts only after all Dev subtasks complete).

---

## 3. Utilization Algorithms

- **Round-robin vs. Priority:**
  - Round-robin spreads load but ignores task weight.
  - Priority queues let urgent QA/Audit tasks jump the line.

- **Shortest Job First (SJF):**
  - Agents handle small tasks first for throughput gains.
  - Add *aging* to prevent starvation of larger tasks.

- **Weighted Fair Queuing (WFQ):**
  - Assign percentages by role (Lead 10%, Dev 40%, QA 20%, Audit 10%).
  - Matches workload distribution to squad composition.

- **Dynamic load-balancing:**
  - Agents report utilization in health checks.
  - Router directs new tasks to least-loaded agents.

---

## 4. Practical Knobs in SquadOps

- **`accept_tasks=false`** → Pause agents when overloaded.
- **`capacity=N`** → Max concurrent tasks per agent.
- **`priority`** → Add to message schema for routing urgency.
- **Checkpoints** → Verify stability before raising concurrency (e.g., from 1 → 3 tasks).
- **warm-boot cycles** → Tune concurrency knobs iteratively.

---

## 5. Suggested Algorithmic Mix

1. **Represent dev plan as DAG** (PID → UC → TC → tasks).  
2. Use **topological scheduling** with **critical path bias**.  
3. Apply **token-bucket per agent role** for LLM calls (cost/latency).  
4. Within each role’s queue, use **Shortest Job First with aging**.  
5. Add **dynamic load-balancing** when scaling Dev/QA pools.  

---

## 6. Key Benefits

- **Productivity** → maximize throughput, minimize idle capacity.  
- **Traceability** → checkpoints ensure concurrency changes are safe.  
- **Cost-control** → token buckets + Finance agent manage spend.  
- **Adaptability** → squad profile evolves via warm-boot cycles.

---
