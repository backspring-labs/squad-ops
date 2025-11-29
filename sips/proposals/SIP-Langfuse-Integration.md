---
sip_uid: "01KB65Q1GT0JENW79K4P456DWR"
sip_number: null
title: "Langfuse Integration for SquadOps"
status: "proposed"
author: "Jason Ladd"
approver: null
created_at: "2025-11-28T21:25:43Z"
updated_at: "2025-11-28T21:25:43Z"
original_filename: "SIP-LangFuse-Integration.md"
---

# SIP: Langfuse Integration for SquadOps

**Status:** Draft v0.1 (directional)  
**Owner:** Nexa Squad (Max • Nat • Neo)  
**Depends On:** SIP‑021 (Memory), SIP‑036 (Capability Binding), SIP‑039/SIP‑040 (Capability System & Loader), Observability baseline (OpenTelemetry + Prefect)

---

## 1. Purpose

This SIP defines **how SquadOps will integrate Langfuse** as the primary **LLM / agent observability plane** while retaining **OpenTelemetry** for system-wide metrics, logs, and distributed tracing.

Goals:

- Provide deep, LLM- and agent-specific telemetry (prompts, models, tokens, tool calls, costs, evals) **without reinventing Langfuse's feature set**.
- Keep **OpenTelemetry** for infra-level metrics/logs and cross-system traces.
- Standardize where and how SquadOps emits Langfuse events so that every **Capability**, **Tool**, and **Agent** can be inspected and evaluated over time.
- Make Langfuse a first-class input to **WarmBoot scorecards**, **fitness routing**, and **SIR/SIP feedback loops**.

Non-goal: Replace or significantly refactor OpenTelemetry; OTel remains the underlying cross-system observability standard.

---

## 2. Scope

Included:

- Architectural relationship between **SquadOps**, **Langfuse**, and **OpenTelemetry**.
- Definition of **integration points** (Agent, Capability, Tool, LLM Provider Abstraction, Prefect workflows).
- Core **event/trace attributes** shared between OTel and Langfuse (IDs, capability names, costs, quality signals).
- **Privacy and security** expectations for logging prompts and outputs.
- **Phase-based rollout plan** for adding Langfuse without destabilizing the system.

Out of scope:

- Detailed deployment scripts or Helm charts.
- UI workflows inside the Langfuse Console.
- Tool-specific or cloud-provider-specific configuration.

---

## 3. High-Level Architecture

### 3.1 Conceptual Stack

From top to bottom:

- **SquadOps Runtime**
  - Agents (Max, Nat, Neo, EVE, etc.)
  - Capabilities, Skills, Tools
  - Capability Loader
  - Memory (SIP‑021)
  - Prefect flows / tasks

- **Observability Layer**
  - **Langfuse** → LLM + agent traces, prompts, tokens, cost, tool chains, evals.
  - **OpenTelemetry** → metrics, logs, infrastructure traces, Prefect span linkage.

- **Model & Service Layer**
  - Local/remote LLMs (Ollama, Docker models, cloud APIs)
  - External services and tools (APIs, CLIs, MCP tools, DBs, scanners)
  - Postgres, Redis, RabbitMQ, etc.

### 3.2 Responsibilities Split

- **Langfuse**
  - LLM call tracing (prompt, response, tokens, latency, cost, model/provider).
  - Agent chain and tool-call visualization.
  - Multi-step, multi-agent traces linked to a single user/task.
  - Evaluations and human feedback.
  - Dataset and prompt version tracking.

- **OpenTelemetry**
  - System metrics (CPU/memory, queue depth, DB metrics, flow throughput).
  - Logs (errors, warnings, infra events).
  - Cross-service traces (Prefect, agents, loaders, DB calls, queue operations).

SquadOps does **not** attempt to replicate Langfuse's LLM-focused analytics; instead it uses Langfuse as the specialized lens on top of OTel-compatible traces and attributes.

---

## 4. Integration Points (Where SquadOps Talks to Langfuse)

### 4.1 LLM Provider Abstraction Layer

- Every LLM call (local via Ollama/Docker, remote via cloud provider) is wrapped by a provider abstraction.
- The abstraction is responsible for:
  - Emitting **Langfuse events/spans** around each LLM call.
  - Capturing model name, provider, latency, token counts, approximate cost, and error details.
  - Attaching trace IDs and capability/agent context (capability name, agent name, task_id, ecid, pid, correlationId).

**Direction:** This is the **primary integration point** for Langfuse and must be implemented first.

### 4.2 Capability Execution

- Each **Capability execution** becomes a Langfuse "trace segment" or "span" that associates:
  - Agent name and capability@version.
  - Input type (summary, hash, or schema reference; not raw secrets).
  - Outcome status (success, failure, partial, escalated).
  - Child LLM calls and Tool calls (linked to the capability's trace via IDs).
- WarmBoot scorecards for capabilities will read cost/latency/error rates primarily from Langfuse, not custom metrics.

### 4.3 Tool Calls (including MCP Tools)

- Tools that call external systems (HTTP, CLI, MCP, DB) are represented as Langfuse "tool" or "step" entries.
- Each call records:
  - Tool name@version and subtype (e.g., `mcp`, `http`, `cli`).
  - Endpoint/host (non-sensitive form), latency, status, and high-level error class.
  - Linkage to the parent Capability and Agent trace.
- MCP Tools inherit the same behavior but additionally record protocol (`MCP/1.x`) and logical operation (e.g., "retrieve context", "write note").

### 4.4 Agent-Level Events

- Agents log Langfuse events for:
  - Task received / Task completed.
  - Escalations and HALT conditions.
  - Autonomy events (spawned sub-tasks, retries, rollbacks) within bounded autonomy rules.
- These events are correlated with LLM and capability-level spans using SquadOps IDs (ecid, pid, task_id, correlationId) so traces can be reconstructed end-to-end.

### 4.5 Prefect & Flows

- Prefect flows and tasks already emit OpenTelemetry spans.
- Each flow run propagates a **correlationId** that is also attached to Langfuse traces.
- This enables correlation in the Console: "which Prefect runs and infra spans correspond to this Langfuse agent trace?"

---

## 5. Shared IDs & Attribute Conventions

To avoid divergence, SquadOps uses the same ID set in both OTel and Langfuse:

- `ecid` — Execution Cycle ID (WarmBoot run ID or similar).
- `pid` — Process or pipeline ID (macro-level process/workflow).
- `task_id` — Logical task ID from the planner (1:1 with a capability invocation).
- `capability` — Capability name@version (e.g., `code_review@1.1.0`).
- `agent` — Agent name (e.g., `Neo`, `EVE`).
- `correlationId` — Conversation or objective-level correlation (often OID from SIP‑038).

Standard attribute groups in Langfuse traces:

- **LLM attributes:**
  - `model`, `provider`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `cached` (Y/N).
- **Capability attributes:**
  - `capability`, `agent`, `status` (ok/error/partial/escalated), `duration_ms`, `tool_calls`, `warmboot_cycle`.
- **Tool attributes:**
  - `tool_name`, `tool_version`, `tool_subtype`, `endpoint_host`, `scope` (read_only/read_write), `latency_ms`, `status`.
- **Autonomy attributes (optional):**
  - `spawned_tasks`, `retries`, `rollback_count`, `escalated_to`.

These same attributes can be mirrored as OTel span attributes for consistency, but Langfuse remains the primary place to explore them in detail.

---

## 6. Data Minimization, Privacy, and Redaction

Langfuse integration must obey strict data minimization:

- **Secrets and credentials** are **never logged**.
- Sensitive payloads (PII, production customer data) are **summarized or hashed**, not stored verbatim.
- SquadOps will prefer:
  - Schema names, IDs, and hashes over full payloads.
  - Short text summaries (e.g., "order update payload v3") over raw JSON.
- Capabilities and Tools may define which fields are safe to log in their registry entries (e.g., `loggable_fields`, `sensitive_fields`).
- Redaction policies are enforced at the telemetry emission layer so individual Capabilities/Tools do not have to reimplement scrubbing logic.

---

## 7. WarmBoot & Langfuse

WarmBoot (SquadOps' continuous regression mechanism) will use Langfuse as a **primary data source** for:

- Per-capability error rates, median latency, cost, and flakiness.
- LLM model performance across different tasks.
- Reliability of Tools (especially MCP Tools) under different workloads.

Directionally:

- WarmBoot scorecards are computed by aggregating Langfuse traces for each capability over the last N runs or time window.
- Custom metrics remain optional; the focus is on reusing Langfuse's rich trace data instead of duplicating metrics.

---

## 8. Rollout Plan (Phased)

**Phase 1 — Foundations (LLM Provider Integration)**  
- Add Langfuse to the LLM provider abstraction.  
- Emit minimal spans for each LLM call with model, tokens, cost, error, and IDs.  
- Keep OTel unchanged; verify Langfuse is receiving data and traces can be linked to OTel spans via shared IDs.

**Phase 2 — Capability & Tool Coverage**  
- Wrap capability execution with Langfuse spans/events.  
- Add basic tool call spans (including MCP Tools) with latency and status.  
- Define the initial attribute set for capabilities and tools.

**Phase 3 — WarmBoot & Scorecards**  
- Switch WarmBoot scorecards to read error/latency/cost metrics from Langfuse traces.  
- Set thresholds and create alerts/dashboards using Langfuse's analytics capability.

**Phase 4 — Evals & Feedback (Optional)**  
- Introduce automated evaluations (where safe) to score output quality.  
- Allow human feedback on key flows (e.g., PR quality, test quality) and store scores in Langfuse.  
- Feed evaluation results back into SIP/SIR recommendations and SIP‑040's fitness routing ideas.

---

## 9. Governance & Controls

- **Ownership:** Neo + EVE own the Langfuse integration; Max owns policy.  
- **Change control:** Any expansion of logged content must be reviewed for data sensitivity and approved via SIP or SIR.  
- **Access:** Langfuse Console access is restricted to engineering and observability roles; audit logging enabled.  
- **Disaster recovery:** Misconfigured logging that exposes sensitive data requires immediate rotation of credentials and purging (where possible), plus a follow-up SIR.

---

## 10. Acceptance Criteria (v0.1)

- Langfuse receives traces for **all LLM calls** via the provider abstraction.  
- Every capability execution is represented in Langfuse with at least: `agent`, `capability`, `task_id`, `ecid`, `status`, `duration_ms`.  
- At least one Tool (ideally an MCP Tool) emits Langfuse tool-call spans.  
- WarmBoot is able to consume Langfuse data for at least one capability's scorecard.  
- OTel remains intact, and standard system dashboards (metrics/logs) continue to function without regression.

---

## 11. Directional Summary

- Langfuse becomes the **LLM and agent telemetry cockpit** for SquadOps.  
- OpenTelemetry remains the **infra-wide observability backbone**.  
- SquadOps focuses on orchestration, autonomy, and capability design—not building a homegrown Langfuse clone.  
- Shared IDs (ecid, pid, task_id, correlationId) and consistent attributes prevent fragmentation between the two observability views.  
- WarmBoot and fitness routing gain richer signals with much less custom work.

This SIP establishes the north star for how and where Langfuse fits into the SquadOps architecture, so implementation can proceed incrementally without revisiting foundational decisions.

