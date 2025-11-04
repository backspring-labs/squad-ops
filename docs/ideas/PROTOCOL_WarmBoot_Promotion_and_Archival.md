# 🧩 PROTOCOL: WarmBoot Promotion & Archival (Phased Execution Model)

**Version:** 1.1  
**Date:** 2025-10-15  
**Phases:** 3 (Local Sequential → Semi-Automated → Full Autonomous)  
**Applies To:** Neo, Devin, EVE, Data, Max  
**Related Docs:** `PROTOCOL_CodeDelivery_MultiEnv.md`, `PROTOCOL_WarmBoot_Modes.md`

---

## 🧭 Purpose
Define a **phased WarmBoot lifecycle** that adapts to the available compute and concurrency limits of the deployment environment — allowing the same protocol to operate efficiently whether you’re running on a **MacBook**, **DGX Spark**, or **cloud cluster**.

---

## ⚙️ Overview: Progressive Execution Phases

| Phase | Environment | Agent Concurrency | Mode | Objective |
|--------|--------------|------------------|------|------------|
| **Phase 1** | Local constrained (MacBook, 1–2 agents) | Sequential | Manual/semi-automated | Establish correctness and reproducibility |
| **Phase 2** | Mid-tier (DGX Spark or local server) | Partial parallelism (3–5 agents) | Queued handoffs | Validate automated promotion and data logging |
| **Phase 3** | Full-scale cloud or DGX Spark | Full parallel | Autonomous orchestration | Continuous WarmBoot testing and auto-promotion |

---

## 🧩 PHASE 1 — Sequential Local Execution
### Context
- Runs on **MacBook** or other limited device.  
- You can only run **Neo** + **Devin** (EVE and Data simulated or deferred).  
- WarmBoots are executed **serially**, one PID at a time.

### Flow
```
Neo → Devin → (Manual Test) → Tar.gz Archive or Git Promotion
```

### Characteristics
| Aspect | Description |
|--------|-------------|
| **Validation** | Manual or lightweight script; EVE not active. |
| **Metrics** | Logged minimally to local CSV or JSON. |
| **Promotion** | Neo executes `squad promote PID-###` manually. |
| **Archival** | `.tar.gz` created automatically at end of run. |
| **Storage** | `/runs` and `/archive` on host filesystem. |

### Example Command
```bash
squad run PID-001 && squad archive PID-001
```

This mode ensures you can test WarmBoot reproducibility without high resource cost.

---

## 🧩 PHASE 2 — Queued Semi-Automated Mode
### Context
- Runs on **DGX Spark** or mid-tier server.  
- You can run **Neo, Devin, and EVE sequentially**; Data optional.  
- Introduce **Prefect or MQ queueing** for task handoff.  

### Flow
```
Neo → Devin (build + test) → EVE (validation) → Data (log) → Max (review)
```

### Characteristics
| Aspect | Description |
|--------|-------------|
| **Validation** | EVE executes full regression after Devin finishes. |
| **Metrics** | Data logs stored in local DB or flatfiles. |
| **Promotion** | Automated via queue trigger; Max approves merge. |
| **Archival** | Automated `.tar.gz` of every completed run (pass/fail). |

### Example Command
```bash
squad queue warmboot PID-032
```
Neo enqueues the run → Devin builds → EVE consumes job → reports result → Data stores metrics.

---

## 🧩 PHASE 3 — Full Autonomous Parallel Mode
### Context
- Runs on **DGX Spark (multi-GPU)** or **cloud cluster** (ECS, GKE, etc.).  
- Full squad online: **Neo, Devin, EVE, Data, Max** all concurrent.  
- WarmBoot runs occur continuously and autonomously.

### Flow
```
Neo dispatches → Devin executes → EVE validates → Data logs → Max approves
```

### Characteristics
| Aspect | Description |
|--------|-------------|
| **Validation** | EVE runs in real-time via message bus events. |
| **Metrics** | Data aggregates results across all PIDs into telemetry DB. |
| **Promotion** | Automated upon test pass and Max policy compliance. |
| **Archival** | Tarballs for all runs retained by Data with retention policy. |
| **Concurrency** | Multiple WarmBoots in flight, resource-aware scheduling. |

### Example Command
```bash
squad warmboot auto --parallel=5
```

---

## 🧠 Promotion Criteria (All Phases)
- ✅ All required tests pass (manual or automated).  
- ✅ Coverage ≥ threshold (default: 90%).  
- ✅ PID and ECID linked.  
- ✅ Governance (Max) approval or policy compliance.  

---

## 📦 Archival Format
WarmBoot artifacts are compressed for storage and portability:
```bash
tar -czf /archive/warmboots/PID-###_artifacts.tar.gz /runs/PID-###/
sha256sum /archive/warmboots/PID-###_artifacts.tar.gz > /archive/warmboots/PID-###.sha256
```

**Metadata example**
```yaml
pid: PID-044
status: archived
phase: 2
metrics:
  coverage: 0.91
  duration: 312
archived_at: 2025-10-15T21:15Z
checksum: 32b4f91c...
```

---

## 🧭 Phase Transition Triggers

| Transition | Trigger | Notes |
|-------------|----------|--------|
| 1 → 2 | DGX Spark deployed or 3-agent concurrency available | EVE activated |
| 2 → 3 | Prefect + MQ operational; Data agent online | Full squad autonomy |
| Any → 1 | Running offline or debugging locally | Manual fallback mode |

---

## 📈 Benefits
- **Scales with hardware** — same logic, different depth.  
- **Consistent artifacts** — same `.tar.gz` structure at every phase.  
- **Graceful degradation** — never blocked by missing agents.  
- **Predictable telemetry** — even local runs feed learning loops.

---

> _This protocol defines a progressive WarmBoot lifecycle that adapts to available resources, allowing SquadOps to grow from single-device experiments to fully autonomous multi-agent orchestration._
