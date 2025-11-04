# 💡 IDEA_012 — Reasoning Telemetry Sharing via Reasoning Trace Envelopes (RTE)

**Created:** 2025-11-02  
**Owner:** Max (Governance) + Data (Metrics)  
**Status:** Draft  
**Related Protocols:** Task Logging & Metrics, Comms & Concurrency, Observability & Continuous Improvement  

---

## 🎯 Purpose

Enable agents to **share structured reasoning telemetry** during Execution Cycles so that another agent (typically **Data** or **Max**) can **aggregate, log, and summarize reasoning flow** in the cycle wrap-up.  
This improves **transparency**, **collaboration metrics**, and **root cause analysis** across WarmBoots and full cycles — without exposing raw model reasoning unless explicitly authorized.

---

## 🧠 Concept Summary

Agents emit lightweight **Reasoning Trace Envelopes (RTEs)** during execution.  
These are structured JSON packets representing checkpoints, decisions, hypotheses, or consensus votes.  
An aggregator agent collects these through **SquadComms**, stores them in Postgres/MinIO, and compiles them into a **Cycle Reasoning Digest (CRD)** at wrap-up.

---

## 📦 Message Schema: `rte.v1`

```json
{
  "schema": "rte.v1",
  "cycle_id": "C-2025-11-02-001",
  "pid": "PID-001",
  "task_id": "TID-NEO-004-API-SPEC",
  "trace_id": "trace-9f1a",
  "span_id": "span-a12b",
  "agent": "Neo",
  "role": "Dev",
  "timestamp": "2025-11-02T19:13:22Z",

  "reason_step": "decision|hypothesis|plan|risk|checkpoint|rca|handoff",
  "summary": "Selecting FastAPI due to async needs and ecosystem support.",
  "confidence": 0.74,
  "assumptions": ["Auth via Keycloak OIDC"],
  "alternatives_considered": ["Flask", "Express"],
  "decision_criteria": ["perf", "typing", "team fit"],
  "tool_calls": [{"tool": "pytest", "duration_ms": 8123}],
  "model_meta": {"name": "qwen2.5:7b", "temp": 0.2, "tokens_in": 1234, "tokens_out": 256},
  "latency_ms": 930,
  "cost_est": {"tokens": 1490, "usd": 0.0003},

  "redaction": {"raw_reasoning_included": false},
  "attachments": [{"type": "artifact", "path": "s3://minio/.../api_spec_v1.md"}]
}
```

---

## 🛰️ Transport Layer — RabbitMQ Routing

| Topic Key | Example | Consumer |
|------------|----------|-----------|
| `squad.reasoning.<cycle_id>.<agent>` | `squad.reasoning.C-2025-11-02-001.Neo` | `q.reasoning.aggregate` (Data / Max) |

The **Data agent** consumes and stores RTEs into Postgres (`reasoning_trace_envelopes` table) and manages MinIO artifact attachments.

---

## 🧮 Storage Schema (Postgres)

```sql
CREATE TABLE reasoning_trace_envelopes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cycle_id TEXT NOT NULL,
  pid TEXT,
  task_id TEXT,
  trace_id TEXT,
  span_id TEXT,
  agent TEXT,
  role TEXT,
  ts TIMESTAMPTZ NOT NULL,
  reason_step TEXT,
  payload JSONB
);
CREATE INDEX rte_idx ON reasoning_trace_envelopes(cycle_id, pid, task_id, agent, ts);
```

---

## 📈 Integration with Observability (OpenTelemetry)

Each RTE becomes a **span event** under the same `trace_id`:

| Field | OTel Mapping |
|--------|--------------|
| `trace_id` | Cycle or task trace |
| `span_id` | Step or sub-task |
| `reason_step` | Event name |
| `confidence`, `model_meta`, etc. | Event attributes |

This allows full reasoning timelines to appear in **Jaeger / Grafana** alongside CPU, GPU, and token latency metrics.

---

## 🧠 Privacy & Control

- **Default:** `raw_reasoning_included = false` (summary only).  
- **Debug Mode:** allows raw reasoning for diagnostic cycles.  
- **Sampling:** configurable rate (e.g., every Nth event or on error).  
- **Redaction:** regex filters for secrets, PII, or tokens before publish.

---

## 🗳️ Consensus & Voting Events

RTEs also support decision coordination:

```json
{
  "reason_step": "consensus_vote",
  "proposal_id": "prop-123",
  "vote": "approve|reject|abstain",
  "rationale": "Meets latency SLO; security unchanged.",
  "confidence": 0.68
}
```

Aggregator tallies votes per proposal and logs the outcome in the Cycle Reasoning Digest.

---

## 🧾 Cycle Reasoning Digest (CRD)

Generated automatically at the end of each Execution Cycle.  
Contains:
- Timeline of reasoning events per agent  
- Key assumptions, confidence deltas  
- Consensus summaries and dissent notes  
- Root cause snapshots (RCA)  
- Cost and latency rollups  
- Links to all referenced artifacts  

**Output:**  
`/docs/wrapups/CRD_<cycle_id>.md` + `/docs/wrapups/CRD_<cycle_id>.json`

---

## 🧩 Benefits

- Enables **cross-agent reasoning transparency** without exposing private model output.  
- Simplifies **cycle retrospectives** and **RCA automation**.  
- Provides **structured telemetry** for observability tools.  
- Lays groundwork for **meta-analysis of reasoning efficiency** and **agent consensus modeling**.

---

## 🔮 Future Extensions

- Schema versioning (`rte.v2` with embedding vectors for similarity search).  
- Weighted confidence aggregation for collective reasoning.  
- Visualization dashboard of reasoning flow by agent or time sequence.  
- Integration with **Cycle Scorecards** to correlate reasoning patterns with outcomes.

---

> **Summary:**  
> The **Reasoning Trace Envelope** system allows agents to broadcast their decision checkpoints as structured telemetry.  
> This telemetry becomes the foundation of the squad’s reasoning audit trail — forming the backbone of transparent, measurable, and improvable collaboration in SquadOps.

---
