---
title: Prefect Task-Scoped Log Streaming
status: implemented
author: SquadOps Architecture
created_at: '2026-04-18T00:00:00Z'
sip_number: 87
updated_at: '2026-04-24T22:18:28.183182Z'
---
# SIP-0087: Prefect Task-Scoped Log Streaming

**Status:** Accepted
**Authors:** SquadOps Architecture
**Created:** 2026-04-18
**Revision:** 2

## 1. Abstract

The Prefect UI shows "Waiting for logs..." for every flow run in SquadOps because `PrefectReporter` only posts flow/task run state transitions — it never calls `/api/logs`. As a result, operators watching a cycle in Prefect can see tasks transition Running → Completed but have zero visibility into *what the task is actually doing*. This SIP wires SquadOps' existing structured logs (handler events, LLM throughput, manifest retries, validation warnings) into Prefect as per-task log streams, scoped by `task_run_id` so clicking a task in the UI reveals only that task's log entries.

## 2. Problem Statement

Cycle runs on DGX Spark routinely take 10–60 minutes, with individual handler tasks spending 5–9 minutes in a single 32b-model LLM call. During those minutes the operator has no signal in the Prefect UI beyond "task is Running." Questions like "is the model still producing tokens?", "did the manifest retry fire?", "which subtask is Neo on right now?" all require SSH-ing to the host and tailing `docker logs squadops-max`.

Concrete gaps:

- **No `/api/logs` emission.** `adapters/cycles/prefect_reporter.py` has methods for flow/task creation and state transitions but no `create_logs()`. The UI log pane polls an empty endpoint.
- **Logs already exist** — handlers emit `executing_capability`, `handler_succeeded`, manifest production, retry attempts, LLM throughput (`t/s=45.2, tokens=960`), validation warnings. They go to stdout and disappear from the UI's perspective.
- **No task-scoped correlation surface** — even if we broadcast all logs at the flow level, the UI can't filter per task. Each record must carry `task_run_id`.
- **No long-task heartbeat** — tasks spending 5+ minutes in a single LLM call give no UI signal between dispatch and completion, leading to "is it dead?" ambiguity.

This matters for the Spark validation work in progress (SIP-0086 build convergence loop): diagnosing run failures is currently a log-grep exercise that could be a click-and-read exercise.

## 3. Goals

1. Forward `squadops.*` and `adapters.*` log records to Prefect's `/api/logs` endpoint, tagged with the active `flow_run_id` and `task_run_id`.
2. Batching + best-effort delivery so cycle execution never blocks on telemetry, and a Prefect outage degrades gracefully (drop the batch, log one warning, continue).
3. Task-scoped filtering in the UI: clicking a task in the flow run diagram shows only that task's logs.
4. Add a periodic heartbeat log for tasks running longer than a threshold (default 60s) so the UI shows liveness for long LLM calls.
5. Zero handler changes — handlers keep calling `logger.info(...)`. The plumbing is in a logging.Handler + a forwarder.

## 4. Non-Goals

- **Not** a replacement for LangFuse. LangFuse tracks LLM traces + prompts + token usage per generation for evaluation. Prefect log streaming is for operator situational awareness during a run.
- **Not** a log store. Retention policy follows whatever Prefect is configured with (typically 7 days on the OSS server). For long-term audit, we still write to stdout + agent_task_log table.
- **Not** a custom progress-bar primitive. OSS Prefect 2.x has no per-task progress percentage API; logs in the pane *are* the "what's happening now" signal.
- **Not** changing `PrefectReporter`'s existing state-transition methods.
- **Not** filtering at the source — handlers log what they log. Filtering happens in the forwarder (by logger name / level).

## 5. Approach Sketch

### Forwarder component

New module `adapters/cycles/prefect_log_forwarder.py`:

- `PrefectLogForwarder` — async batching client, same shape as `PrefectReporter` (httpx.AsyncClient, graceful-degradation on connection errors).
- `enqueue(record: logging.LogRecord, flow_run_id, task_run_id)` — non-blocking put onto an asyncio.Queue.
- Background flush task drains the queue every N seconds (default 1s) or when batch reaches M records (default 50), POSTs to `/api/logs`.
- On POST failure: log one warning, drop the batch, continue. Never block the producer.
- `close()` flushes pending logs with a bounded timeout.

### Logging handler bridge

New `PrefectLogHandler(logging.Handler)`:

- On each `emit()`, reads `flow_run_id` and `task_run_id` from the current `CorrelationContext` (a contextvar).
- If either is missing, drops the record (system-level log, not task-scoped).
- Filters by logger name prefix (`squadops`, `adapters`) — skip `aio_pika`, `uvicorn`, `httpx` heartbeat noise.
- Filters by level (default INFO+).
- Calls `forwarder.enqueue(record, ...)`.

### Correlation propagation

`CorrelationContext` already carries trace/causation IDs. Add `flow_run_id` and `task_run_id` fields populated by `_dispatch_task` in `distributed_flow_executor.py` when a Prefect task_run is created. Handlers inherit the context via the existing task envelope + contextvar machinery; no handler code changes.

### Heartbeat

In `_dispatch_task` (executor side), spawn a background heartbeat coroutine when a task starts:
- Every 30s (configurable) log `task_heartbeat elapsed=Xs capability_id=...` at INFO level.
- Cancel when the handler completes.
- The heartbeat goes through the same logging pipeline → Prefect UI sees "still running at T+30s, T+60s, T+90s" lines.

### Wiring

- Runtime-api startup: if Prefect is enabled, install `PrefectLogHandler` on the root logger.
- Agent entrypoints: install it at agent boot, keyed to the agent's log root.
- Config flag: `SQUADOPS__PREFECT__LOG_FORWARDING=true|false` (default `true` when Prefect URL is configured).

## 6. Key Design Decisions

1. **Batching over per-record POST** — 1s flush cadence with 50-record batches. Matches LangFuse adapter pattern. Keeps Prefect API load low under burst conditions (e.g., a chat_stream loop emitting throughput lines rapidly).

2. **Drop on failure, don't queue indefinitely** — if Prefect is unreachable for >N retries, drop the batch. Prevents unbounded memory growth during a Prefect outage. A single WARN is emitted per outage window.

3. **Filter at the handler layer, not at the forwarder** — `PrefectLogHandler` checks logger name / level *before* enqueueing. Cheap to reject noise; we don't pay queue overhead for `aio_pika` heartbeats.

4. **task_run_id is the primary key, not capability_id** — Prefect's UI filter operates on task_run_id. The mapping from our handler's capability_id to Prefect's task_run_id happens at task_run creation time in the executor; handlers just see "your log went to the right place."

5. **Heartbeat is executor-side, not handler-side** — handlers are synchronous from their own perspective (one LLM call = one blocking await). The executor spawns the heartbeat as a sibling coroutine. Keeps handler code simple.

6. **System-level events still go somewhere** — logs with no active task_run_id (agent startup, orchestrator-level events) land at the flow_run level when a flow_run_id is set, or are dropped otherwise. They don't pollute task panes.

## 7. Acceptance Criteria

1. Clicking a task in the Prefect UI flow-run diagram shows only that task's logs in the bottom pane (not a global stream).
2. Clicking the parent flow run shows orchestrator-level logs (workload_advanced, gate decisions, executor warnings) but not per-task detail.
3. A long-running task (>60s) shows periodic `task_heartbeat` entries in the UI.
4. LLM throughput lines (`t/s=45.2, tokens=960`) appear within ~2s of being logged by the handler.
5. Manifest retry events (SIP-0086) appear in the `governance.assess_readiness` task log pane with enough detail to diagnose fallback cause.
6. Stopping Prefect mid-cycle does not pause or fail the cycle; cycle completes and a single WARN records the forwarder outage.
7. Agent startup / system-bootstrap logs do NOT appear in any task pane (they're pre-correlation-context).
8. Enabling/disabling the forwarder via `SQUADOPS__PREFECT__LOG_FORWARDING` takes effect on next agent restart without code changes.
9. Existing `PrefectReporter` flow/task-run state transitions are unchanged.
10. New tests cover: batching, drop-on-failure, context propagation, level/name filtering, heartbeat cancel-on-completion.

## 8. Source Ideas

- Live conversation 2026-04-18 — operator blocked on `Waiting for logs...` UI pane during SIP-0086 validation cycle. Identified missing `/api/logs` emission in PrefectReporter.
- LangFuse adapter (`adapters/telemetry/langfuse/adapter.py`) — buffered, best-effort, graceful-degradation pattern used as reference.
- Prefect OSS 2.x `/api/logs` endpoint contract.

## 9. Resolved Decisions

Questions from the Revision 1 draft, resolved at acceptance (Revision 2, 2026-04-24):

1. **Heartbeat cadence — global 30s default.** Per-capability tuning is premature; a 30s heartbeat during a 5-min LLM call produces ~10 lines (acceptable noise), and short handlers emit 0–1 heartbeats. Revisit if a specific handler class pollutes the UI.

2. **Log level — INFO+ default, overridable via `SQUADOPS__PREFECT__LOG_LEVEL`.** The logger-name prefix filter (`squadops.*`, `adapters.*`) already excludes 3rd-party DEBUG firehoses (`aio_pika`, `httpx`, `asyncpg`), so lowering the threshold stays safe for diagnosis sessions.

3. **Rate limits — no client-side throttling.** OSS Prefect 2.x has no documented server-side limits; the local Prefect-server deployment is trusted. Drop-on-failure already handles any future 429 responses. Revisit only if rate-limit rejections are observed in practice.

4. **Log replay tool — out of scope.** Prefect's 7-day retention on OSS + LangFuse traces + the `agent_task_log` table cover post-hoc analysis. A replay tool can be proposed as a follow-up SIP if a concrete need surfaces.

5. **Failed-batch disk persistence — fire-and-forget.** Matches the LangFuse adapter pattern. Stdout and `agent_task_log` remain the durable record; disk persistence adds corruption risk, cleanup policy, and write-path failure modes for minimal gain.
