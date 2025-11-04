# 🧩 IDEA-004: WarmBoot Reasoning & Resource Trace Log

## 📌 Concept Summary

Introduce a combined **Reasoning & Resource Trace Log** --- a single
Markdown artifact generated after every WarmBoot run that reconstructs
both **the full reasoning chain** *and* **verifiable operational
events**.

During the current bootstrap phase (Max + Neo only), this log draws from
**Ollama reasoning traces** and low-level telemetry (compute, DB,
container, and RabbitMQ events) to prove that tangible work occurred ---
not simulated dialogue.

------------------------------------------------------------------------

## 🎯 Purpose

Create a **trustworthy WarmBoot record** that captures *why* actions
happened (reasoning) and *what* actions actually occurred (execution),
providing both transparency and verifiable activity while the Squad Ops
Console is still offline.

------------------------------------------------------------------------

## 🧠 Key Principles

  -----------------------------------------------------------------------
  Principle                        Description
  -------------------------------- --------------------------------------
  **Reasoning + reality**          Pair raw LLM reasoning with concrete
                                   infra telemetry.

  **Verifiable compute**           Every run shows CPU/GPU load,
                                   container actions, and DB events.

  **Readable forensic trail**      Markdown output, easily inspected or
                                   diffed.

  **Incremental maturity**         Manual now → automated SOC ingestion
                                   later.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## ⚙️ Proposed Workflow

### 1️⃣ Capture Logs

-   **Reasoning:**
    -   `ollama_max.log` → PRD → Task reasoning\
    -   `ollama_neo.log` → Dev → Build reasoning\
-   **Infra Telemetry:**
    -   `/var/lib/docker/events.log` or `docker events --since <t>`\
    -   System metrics snapshot (`psutil` or
        `docker stats --no-stream`)\
    -   RabbitMQ event counts via `rabbitmqctl list_queues`\
    -   DB inserts / updates / deletes count from `agent_task_logs`

Each collected feed is timestamped and written under
`/warmboot_runs/run-###/raw_logs/`.

------------------------------------------------------------------------

### 2️⃣ Generate Trace Markdown

The narrative log merges reasoning + operational summaries:

``` markdown
# 🧩 WarmBoot Run 007 — Reasoning & Resource Trace Log
_Date: 2025-10-11_

---

## 1️⃣ PRD Interpretation (Max)
> "PRD confirmed. Deriving tasks for FastAPI health check."
> "Assigning Neo to build endpoint and pytest suite."

---

## 2️⃣ Task Execution (Neo)
> "Scaffolding hello.py with /health route."
> "Running pytest; 1 passed in 0.07 s."

---

## 3️⃣ Artifacts Produced
- `hello.py`  
- `test_hello.py`  
- `warmboot_summary.json`

---

## 4️⃣ 🔍 Resource & Event Summary
| Metric | Value | Notes |
|--------|--------|-------|
| CPU Usage (Avg/Max) | 42 % / 71 % | Measured via psutil snapshot |
| GPU Utilization | 18 % | Captured from nvidia-smi API |
| Memory Usage | 3.4 GB peak | Container aggregate |
| DB Writes | 12 rows inserted / 4 updated | `agent_task_logs`, `warmboot_summary` |
| RabbitMQ Events | 27 messages published / 27 acked | `max.task.assign`, `neo.dev.status` |
| Containers Built | 1 (neo_container:v0.3) | Image digest abc123 |
| Containers Updated | 1 (max_container restarted) | Config patch env vars |
| Containers Removed | 0 | — |
| Execution Duration | 9 min 12 s | From first pulse to final commit |
| Artifacts Checksum | sha256: 1fbd... | Ensures file integrity |

---

## 5️⃣ Metrics Snapshot
| Metric | Value |
|---------|-------|
| Tasks Executed | 2 |
| Tokens Used | 4 120 |
| Reasoning Entries | 19 |
| Pulse Count | 9 |

---

## 6️⃣ Next Steps
- [ ] Automate resource collection via Data agent  
- [ ] Ingest reasoning + telemetry into SOC timeline  
- [ ] Correlate pulse events to compute usage spikes  
```

------------------------------------------------------------------------

## 🧱 Data Sources

  Source                 Description                      Future Owner
  ---------------------- -------------------------------- --------------
  Ollama JSONL logs      Reasoning trace per agent        Max / Neo
  Docker events          Container create/update/remove   Marvin
  RabbitMQ queue stats   Message count and ack ratio      Data
  Postgres event log     Task and metrics writes          Data
  System metrics         CPU, GPU, RAM usage              Marvin
  Artifacts hash         SHA or BLAKE hash per file       EVE (later)

------------------------------------------------------------------------

## 🔍 Benefits

  -----------------------------------------------------------------------
  Benefit                       Description
  ----------------------------- -----------------------------------------
  **Proof of work**             Confirms real compute and I/O occurred
                                each cycle.

  **Deep debug context**        Links reasoning to system behavior under
                                load.

  **Audit ready**               Enables forensic inspection for failures
                                or compliance.

  **Future analytics**          Telemetry can train meta-models on
                                efficiency patterns.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 🚀 Future Integration

When SOC is online: - EVE validates reasoning vs. execution
consistency.\
- Data visualizes compute metrics and Rabbit traffic per pulse.\
- Marvin reports container state diffs to SOC Health tab.\
- Max uses the same telemetry for merge governance decisions.

------------------------------------------------------------------------

## 🧩 Linked Artifacts

  -----------------------------------------------------------------------
  Type             ID         Title                 Status
  ---------------- ---------- --------------------- ---------------------
  **Protocol**     PRO-010    Neural Pulse Protocol Planned

  **Protocol**     PRO-012    WarmBoot Integration  Planned
                              & Merge Governance    

  **SIP**          SIP-024    Neural Pulse          Planned
                              Integration           

  **Agents**       Max, Neo   Active in bootstrap   
                              phase                 
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 🧭 Status

**Idea Stage** --- Active exploration.\
Will evolve into **PRO-013: WarmBoot Reasoning and Resource Trace
Protocol** once telemetry collection is automated and SOC displays
verified compute events per run.
