# Cycle Event System v0 — Design Note

## Context

SquadOps has three telemetry subsystems wired independently:

| Subsystem | Port | Adapter | What it records |
|-----------|------|---------|-----------------|
| LLM Observability | `LLMObservabilityPort` | LangFuse | Traces, spans, generations, structured events (cycle.started/completed, task.*) |
| Workflow Status | (none — direct call) | PrefectReporter | Flow runs + task runs with state transitions (REST API) |
| General Telemetry | `EventPort` + `MetricsPort` | OTel / Console / Null | OTEL spans, Prometheus counters/gauges/histograms |

Plus structured logging (`logger.info("run started", extra={...})`) at every lifecycle boundary.

**Problem**: The same semantic fact ("run X transitioned to RUNNING") is recorded in up to 4 places (LangFuse event, Prefect state update, OTEL span, structured log) with different schemas, different timing, and no coordination. Adding SIP-0070 pulse verification events will make this worse.

**Solution**: A single Cycle Event System that is the **canonical source of lifecycle facts**. Telemetry sinks become **subscribers** to events, not independent emitters.

---

## A. Event Taxonomy

20 high-signal events across 5 entity lifecycles. Each event is emitted **exactly once** at a state machine boundary.

### Cycle Events (2)

| Event | Emission Boundary | Purpose / Decision Enabled | Required Fields | Consumers |
|-------|-------------------|---------------------------|-----------------|-----------|
| `cycle.created` | `CycleRegistryPort.create_cycle()` returns | Audit: who created what, when | `cycle_id`, `project_id`, `created_by`, `squad_profile_id`, `prd_ref` | Storage, UI, audit log |
| `cycle.cancelled` | `CycleRegistryPort.cancel_cycle()` returns | Alert: cycle will accept no more runs | `cycle_id`, `cancelled_by` | UI, alerting |

### Run Events (7)

| Event | Emission Boundary | Purpose / Decision Enabled | Required Fields | Consumers |
|-------|-------------------|---------------------------|-----------------|-----------|
| `run.created` | `CycleRegistryPort.create_run()` returns | Track: new run queued | `cycle_id`, `run_id`, `run_number`, `initiated_by` | Storage, UI |
| `run.started` | `update_run_status(RUNNING)` returns | Duration start; trace anchor | `cycle_id`, `run_id`, `task_count`, `started_at` | Storage, UI, metrics (duration start), LangFuse (trace open) |
| `run.completed` | `update_run_status(COMPLETED)` returns | Duration end; success signal | `cycle_id`, `run_id`, `finished_at`, `artifact_count` | Storage, UI, metrics (duration end), alerting |
| `run.failed` | `update_run_status(FAILED)` returns | Incident trigger; RCA start | `cycle_id`, `run_id`, `finished_at`, `reason`, `error_summary` | Storage, UI, alerting, metrics |
| `run.paused` | `update_run_status(PAUSED)` returns | Gate waiting; human-in-loop signal | `cycle_id`, `run_id`, `gate_name` | UI, alerting (SLA timer starts) |
| `run.resumed` | `update_run_status(RUNNING)` from PAUSED returns | Gate cleared; SLA timer stops | `cycle_id`, `run_id`, `gate_name`, `decision` | UI, metrics (gate wait duration) |
| `run.cancelled` | `update_run_status(CANCELLED)` returns | Cleanup signal | `cycle_id`, `run_id`, `cancelled_by` | Storage, UI |

### Gate Events (1)

| Event | Emission Boundary | Purpose / Decision Enabled | Required Fields | Consumers |
|-------|-------------------|---------------------------|-----------------|-----------|
| `gate.decided` | `CycleRegistryPort.record_gate_decision()` returns | Audit: who approved/rejected, with what notes | `cycle_id`, `run_id`, `gate_name`, `decision`, `decided_by`, `decided_at`, `notes` | Storage, UI, audit log |

### Task Events (3)

| Event | Emission Boundary | Purpose / Decision Enabled | Required Fields | Consumers |
|-------|-------------------|---------------------------|-----------------|-----------|
| `task.dispatched` | Envelope published to RabbitMQ | Track: task in flight; timeout starts | `cycle_id`, `run_id`, `task_id`, `task_type`, `agent_id`, `step_index` | Storage, UI, metrics (in-flight gauge) |
| `task.succeeded` | TaskResult received with status=SUCCEEDED | Artifact available; next task unblocked | `cycle_id`, `run_id`, `task_id`, `task_type`, `agent_id`, `artifact_ids`, `duration_ms` | Storage, UI, metrics (task duration histogram) |
| `task.failed` | TaskResult received with status=FAILED | Error attribution; run will fail | `cycle_id`, `run_id`, `task_id`, `task_type`, `agent_id`, `error_summary`, `duration_ms` | Storage, UI, alerting, metrics |

### Pulse Verification Events (5)

| Event | Emission Boundary | Purpose / Decision Enabled | Required Fields | Consumers |
|-------|-------------------|---------------------------|-----------------|-----------|
| `pulse.boundary_reached` | Executor detects cadence close or milestone hit | Observability: verification about to run | `cycle_id`, `run_id`, `boundary_id`, `cadence_interval_id`, `bound_suite_count` | Storage, UI |
| `pulse.suite_evaluated` | `run_pulse_verification()` returns per suite | Per-suite RCA; which checks passed/failed | `cycle_id`, `run_id`, `boundary_id`, `cadence_interval_id`, `suite_id`, `suite_outcome`, `check_count`, `failed_checks` | Storage, UI, analytics |
| `pulse.boundary_decided` | `determine_boundary_decision()` returns | Boundary-level verdict; repair trigger | `cycle_id`, `run_id`, `boundary_id`, `cadence_interval_id`, `decision` | Storage, UI, alerting |
| `pulse.repair_started` | Repair loop begins | Track: repair attempt in progress | `cycle_id`, `run_id`, `boundary_id`, `cadence_interval_id`, `repair_attempt`, `failed_suite_ids` | Storage, UI |
| `pulse.repair_exhausted` | Max repair attempts reached | Terminal: run will fail with VERIFICATION_EXHAUSTED | `cycle_id`, `run_id`, `boundary_id`, `cadence_interval_id`, `total_attempts` | Storage, UI, alerting |

### Artifact Events (2)

| Event | Emission Boundary | Purpose / Decision Enabled | Required Fields | Consumers |
|-------|-------------------|---------------------------|-----------------|-----------|
| `artifact.stored` | `ArtifactVaultPort.store()` returns | Track: what was produced, by whom | `cycle_id`, `run_id`, `task_id`, `artifact_id`, `artifact_name`, `producing_task_type`, `size_bytes` | Storage, UI |
| `artifact.baseline_set` | Baseline enforcement at route level | Track: which artifact is the golden reference | `cycle_id`, `run_id`, `artifact_id`, `baseline_run_id` | Storage, audit log |

**Total: 20 events.** All emitted at state machine boundaries. No mid-function emissions.

---

## B. Event Envelope Schema

Stable, versioned, sink-agnostic.

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01JMBC3E4G7H8K9LAMBNCP0QRS",
  "event_type": "run.started",
  "occurred_at": "2026-02-16T14:30:00.123456Z",
  "sequence": 4,

  "source": {
    "service": "runtime-api",
    "version": "0.9.9"
  },

  "entity": {
    "type": "run",
    "id": "run_abc123",
    "parent_type": "cycle",
    "parent_id": "cyc_xyz789"
  },

  "context": {
    "cycle_id": "cyc_xyz789",
    "run_id": "run_abc123",
    "project_id": "proj_42",
    "trace_id": "trc_deadbeef",
    "correlation_id": "cor_cafebabe"
  },

  "payload": {
    "task_count": 5,
    "started_at": "2026-02-16T14:30:00.123456Z",
    "execution_mode": "sequential"
  },

  "semantic_key": "cyc_xyz789:run:run_abc123:started:4"
}
```

### Field Definitions

| Field | Type | Purpose |
|-------|------|---------|
| `schema_version` | `"1.0"` | Forward compatibility. Sinks reject unknown major versions. |
| `event_id` | ULID string | Globally unique, time-ordered. Primary dedupe key at sinks. |
| `event_type` | `"{entity}.{transition}"` | Dot-separated, from taxonomy above. |
| `occurred_at` | ISO 8601 UTC | Wall-clock time at emission. |
| `sequence` | int | Monotonic counter per `(cycle_id, run_id)`. Detects gaps and reordering. |
| `source.service` | string | Emitting process (`runtime-api`, `agent-neo`, etc.). |
| `source.version` | string | Code version for schema compatibility tracking. |
| `entity.type` | string | `cycle`, `run`, `gate`, `task`, `pulse`, `artifact`. |
| `entity.id` | string | Entity's primary identifier. |
| `entity.parent_type` | string | Parent entity type (for hierarchy navigation). |
| `entity.parent_id` | string | Parent entity ID. |
| `context` | object | Correlation IDs for trace linking. Always includes `cycle_id`. |
| `payload` | object | Event-type-specific data. Schema per event_type. |
| `semantic_key` | string | `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}`. Dedupe key (see Section D). |

### Python Dataclass

```python
@dataclass(frozen=True)
class CycleEvent:
    schema_version: str          # "1.0"
    event_id: str                # ULID
    event_type: str              # "run.started"
    occurred_at: datetime        # UTC
    sequence: int                # monotonic per (cycle_id, run_id)
    source_service: str          # "runtime-api"
    source_version: str          # "0.9.9"
    entity_type: str             # "run"
    entity_id: str               # "run_abc123"
    parent_type: str             # "cycle"
    parent_id: str               # "cyc_xyz789"
    context: dict[str, str]      # correlation IDs
    payload: dict[str, Any]      # event-specific data
    semantic_key: str            # computed dedupe key
```

---

## C. Telemetry Coexistence & Ownership (Mapping Table)

For each existing signal category: who owns it during migration and what happens at cutover.

### Signal Ownership Table

| Signal Category | Current Owner(s) | v0 Strategy | v1 Strategy | v2 (Event-First) | Justification |
|----------------|-------------------|-------------|-------------|-------------------|---------------|
| **Cycle/Run state transitions** | LangFuse (`record_event`), Prefect (`set_flow_run_state`), structured logs | **Mirror** — events emitted; bridge adapters translate to existing sinks | **Replace** — remove `record_event("cycle.started")` and Prefect state calls from executor; sinks subscribe to events | **Event-only** — no wired calls | State transitions are the core semantic fact. One canonical emission point (registry port return) eliminates drift. |
| **Gate decisions** | Structured logs only (no telemetry) | **Replace** — `gate.decided` event is the first and only emission | **Event-only** | **Event-only** | No existing telemetry to migrate. Clean start. |
| **Task dispatch/completion** | LangFuse (task spans + events), Prefect (task runs), structured logs | **Mirror** — events emitted alongside existing LangFuse task spans | **Replace** — remove `record_event("task.assigned/completed/failed")` from agent shims; keep task spans as telemetry-native | **Event + spans** — events own lifecycle facts; spans own duration/trace structure | Task events and task spans serve different purposes (see below). |
| **LLM generations** | LangFuse (`record_generation`) | **Keep as-is** — telemetry-native | **Keep as-is** | **Keep as-is** | High-volume, sampling-sensitive, redaction-sensitive. Not a lifecycle fact — it's a measurement. Events should never carry prompt/response text. |
| **OTEL spans/traces** | EventPort → OTel adapter | **Keep as-is** — telemetry-native | **Keep as-is** | **Keep as-is** — bridge adapter can open/close spans from events if desired | Spans are structural (parent→child timing). Events are semantic (what happened). Both needed. |
| **Prometheus metrics** | MetricsPort → counters/gauges/histograms | **Keep as-is** — telemetry-native; bridge adapter can derive counters from events | **Derive** — `task.succeeded` event drives `task_duration_histogram`; `run.failed` drives `run_failures_total` | **Event-derived** — metrics are computed from event stream | Metrics are aggregates. Events are facts. Derive the former from the latter. |
| **Structured logs** | stdlib logger with `extra={}` | **Keep as-is** — retain as debug/operational signal | **Keep as-is** — logs are orthogonal (operational, not semantic) | **Keep as-is** — raw logs are always useful | Logs are NOT lifecycle facts. They are operational traces. No conflict with events. |
| **Pulse verification** | (SIP-0070: `record_event` calls planned) | **Replace** — events are the first and only emission (no legacy to migrate) | **Event-only** | **Event-only** | Clean start — design events before code exists. |
| **Run reports** | `_generate_run_report()` in executor | **Keep as-is** — artifact, not telemetry | **Keep as-is** | **Keep as-is** — report generator can subscribe to events for richer content | Report is a derived artifact, not a signal. |
| **Agent heartbeats** | `HealthCheckHttpReporter` | **Keep as-is** — infrastructure signal | **Keep as-is** | **Keep as-is** | Heartbeats are infrastructure, not lifecycle. |

### Key Principle: Events vs Spans vs Metrics vs Logs

| Concern | Owner | Why |
|---------|-------|-----|
| **What happened** (lifecycle facts) | Events | Semantic, ordered, dedupeable |
| **How long it took** (timing structure) | Spans | Parent/child trace hierarchy |
| **How much** (aggregates) | Metrics (derived from events) | Counters, histograms, gauges |
| **What went wrong** (operational detail) | Logs | Debug, grep, operational forensics |
| **What the LLM said** (generation content) | LLM Observability (telemetry-native) | High-volume, sampled, redacted |

---

## D. Dedupe & Canonical Truth Rules

### Semantic Dedupe Key

Every event carries a `semantic_key` computed as:

```
{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}
```

Examples:
- `cyc_xyz:run:run_abc:started:4`
- `cyc_xyz:task:tsk_001:succeeded:7`
- `cyc_xyz:pulse:post_dev:boundary_decided:12`

**Invariant**: No two events in the system may share the same `semantic_key`. If they do, the system has a bug (duplicate emission).

### Canonical Emission Rules

1. **Single emission point per transition.** Each event is emitted from exactly one code location — the state machine boundary (registry port method return or executor boundary detection).

2. **Emitter is the authority, not the caller.** The event is emitted by the module that performs the state transition, not by the caller that requested it.

   ```
   WRONG: executor calls update_run_status(RUNNING), then emits run.started
   RIGHT: update_run_status(RUNNING) returns, executor emits run.started from that return point
   ```

   In v1+, the registry port itself may emit events, but in v0 the executor emits at the boundary between "registry acknowledged transition" and "next action."

3. **No downstream re-emission.** If `run.started` is emitted, no sink adapter may emit a second event with equivalent semantics. Sinks translate events into their native format (LangFuse trace, Prefect state, Prometheus counter), not into new events.

### Sequence Counter

Per `(cycle_id, run_id)` pair, an in-memory monotonic counter increments on each event emission. This enables:

- **Gap detection**: If a consumer sees sequence 5 then 7, sequence 6 was lost.
- **Ordering**: Events with lower sequence numbers happened first within a run.
- **Idempotent sinks**: `(event_id, semantic_key)` together uniquely identify an event. Sinks can `INSERT ... ON CONFLICT DO NOTHING`.

### Sink-Side Dedupe

| Strategy | Implementation |
|----------|---------------|
| **Primary key**: `event_id` (ULID) | All sinks use `event_id` as primary/unique key. Retries are safe. |
| **Semantic uniqueness**: `semantic_key` | Unique constraint on `semantic_key` in event store. Catches bugs where two code paths emit the same transition. |
| **Retention window**: 30 days (event store), 90 days (cold archive) | Events older than retention are compacted/archived. Sinks that lag >30 days replay from archive. |

### Drift Detection

Run a periodic verification job (daily or per-cycle):

1. **Query event store** for all events with `entity_type=run`, `entity_id=X`.
2. **Query cycle registry** for Run X's current status and transition history.
3. **Compare**: Every registry state transition should have exactly one matching event. Flag mismatches as `drift_detected` alerts.

---

## E. Migration Phases & Cutover Gates

### v0: Event Bus + Bridge Adapters (0.9.9)

**Goal**: Events exist and are emitted. Existing sinks still receive data through bridge adapters. Zero behavior change for dashboards/alerts.

**Code changes**:

1. **New module**: `src/squadops/events/` — `CycleEvent` dataclass, `CycleEventBus` (in-process pub/sub), sequence counter.
2. **New module**: `src/squadops/events/bridges/` — `LangFuseBridge` (translates events → `record_event()` calls), `PrefectBridge` (translates events → `set_flow_run_state()` calls), `MetricsBridge` (translates events → counter/histogram calls).
3. **Emission points**: Add `event_bus.emit(event)` at each of the 20 taxonomy boundaries in executor + registry caller code.
4. **Bridge wiring**: `main.py` startup registers bridge adapters as subscribers.
5. **Existing wired calls remain** — both events and direct calls fire during v0 (temporary dual-emit).

**What stays stable**: All existing `record_event()`, Prefect, and logging calls unchanged. Dashboards see no difference.

**What is deprecated**: Nothing yet — v0 is additive only.

**Success gate for v1**:
- [ ] All 20 events emitting in production for ≥2 weeks
- [ ] Bridge adapters produce output indistinguishable from direct wired calls (verified by diff test)
- [ ] Sequence gaps detected = 0 over the measurement window
- [ ] Drift detection job passes on 100% of completed cycles

### v1: Rewire Call Sites (1.0)

**Goal**: Remove direct wired calls one category at a time. Events are the single emission source. Bridges become the sole path to LangFuse/Prefect.

**Code changes** (incremental, one category per release):

| Step | Remove | Event Replaces | Bridge Handles |
|------|--------|---------------|----------------|
| v1.0 | `record_event("cycle.started")` and `record_event("cycle.completed")` from executor | `run.started`, `run.completed`, `run.failed` | LangFuseBridge opens/closes cycle traces from run events |
| v1.1 | Prefect `set_flow_run_state()` calls from executor | `run.started/completed/failed/cancelled` | PrefectBridge translates run events → Prefect REST calls |
| v1.2 | Prefect `create_task_run()` + `set_task_run_state()` from executor | `task.dispatched`, `task.succeeded`, `task.failed` | PrefectBridge translates task events → Prefect REST calls |
| v1.3 | `record_event("task.assigned/started/completed/failed")` from agent shims | `task.dispatched`, `task.succeeded`, `task.failed` | LangFuseBridge translates task events → LangFuse events |

**What stays stable**:
- `start_cycle_trace()` / `end_cycle_trace()` — trace structure is telemetry-native
- `start_task_span()` / `end_task_span()` — span structure is telemetry-native
- `record_generation()` — generation recording is telemetry-native
- `flush()` / `close()` — lifecycle management is telemetry-native
- All structured logging — operational, not semantic
- All Prometheus metrics — derived from events via MetricsBridge

**What is deprecated**:
- Direct `record_event()` calls for lifecycle transitions (replaced by events)
- Direct Prefect reporter calls from executor (replaced by PrefectBridge)

**Success gate for v2**:
- [ ] All wired lifecycle calls removed (only trace/span/generation/flush remain on LLMObservabilityPort)
- [ ] Zero drift alerts over ≥4 weeks
- [ ] Dashboard parity test: screenshots of old vs new dashboards show identical data
- [ ] Bridge adapter latency p99 < 50ms (non-blocking guarantee preserved)

### v2: Event-First (1.1+)

**Goal**: Events are the only source of lifecycle truth. Telemetry is limited to what it does best: traces, spans, generations, raw metrics. Bridges are the permanent integration layer.

**Code changes**:
- Remove `StructuredEvent` lifecycle emissions from `LLMObservabilityPort` (only `record_generation()` + trace/span lifecycle remain)
- `LLMObservabilityPort` renamed or narrowed to `LLMTracingPort` (breaking change, major version)
- PrefectReporter becomes an optional bridge subscriber (not injected into executor)
- Event store becomes a first-class persistence layer (queryable via API)

**What stays stable forever**:
- `CycleEvent` envelope schema (versioned, backward-compatible additions only)
- Bridge adapter interface (subscribers implement `on_event(event)`)
- Event taxonomy (new events added, existing events never removed in same major version)

---

## F. Verification Plan

### 1. Emission Coverage Test

For each of the 20 events in the taxonomy, write a test that:
- Executes the state transition that should emit the event
- Asserts exactly one event was emitted with the correct `event_type`
- Asserts all required fields are present and non-empty
- Asserts `semantic_key` is correctly formatted

**Implementation**: Mock `CycleEventBus`, inject into executor/registry, assert on `emit()` calls.

**Test file**: `tests/unit/events/test_event_emission.py` (~40 tests: 20 events × happy path + missing field rejection)

### 2. No-Duplicate-Emission Test

For a full happy-path cycle (create → run → 5 tasks → complete):
- Collect all emitted events
- Assert every `semantic_key` is unique
- Assert sequence numbers are strictly monotonic per `(cycle_id, run_id)`
- Assert no two events have the same `event_type` + `entity_id` unless they represent different transitions (e.g., task.dispatched and task.succeeded for same task_id)

**Implementation**: Integration-style test with real executor + MemoryCycleRegistry + mock queue.

**Test file**: `tests/unit/events/test_event_sequences.py` (~10 tests)

### 3. Bridge Parity Test

For each bridge adapter (LangFuse, Prefect, Metrics):
- Run the same cycle with **only** direct wired calls (v0 mode)
- Run the same cycle with **only** bridge adapters (v1 mode)
- Diff the output: LangFuse events, Prefect state transitions, metric values
- Assert outputs are semantically identical

**Implementation**: Capture adapter call args in both modes, compare.

**Test file**: `tests/unit/events/test_bridge_parity.py` (~15 tests)

### 4. Drift Detection Test

Simulate a cycle lifecycle, then:
- Query mock event store for all events
- Query MemoryCycleRegistry for final state
- Assert every registry state transition has exactly one matching event
- Assert no events exist without a corresponding registry state

**Test file**: `tests/unit/events/test_drift_detection.py` (~5 tests)

### 5. Dashboard Continuity (Manual, Pre-Cutover)

Before each v1.x step:
1. Run a reference cycle with wired calls active
2. Screenshot LangFuse traces, Prefect flow view, Grafana dashboards
3. Remove wired calls, enable bridge
4. Run identical cycle
5. Screenshot same views
6. Visual diff: any data loss = blocker

---

## Event Sequences

### Sequence 1: Happy-Path Cycle

```
seq  event_type           entity     payload (key fields)
───  ──────────────────   ────────   ──────────────────────────────
 1   cycle.created        cyc_001    project_id=proj_42, created_by=admin
 2   run.created          run_001    run_number=1, initiated_by=api
 3   run.started          run_001    task_count=5, started_at=T0
 4   task.dispatched      tsk_001    task_type=strategy.analyze_prd, agent=nat
 5   task.succeeded       tsk_001    duration_ms=12340, artifact_ids=[art_01]
 6   artifact.stored      art_01     name=prd_analysis.md, size_bytes=4200
 7   task.dispatched      tsk_002    task_type=development.implement, agent=neo
 8   task.succeeded       tsk_002    duration_ms=18200, artifact_ids=[art_02]
 9   artifact.stored      art_02     name=implementation.md, size_bytes=8100
10   task.dispatched      tsk_003    task_type=qa.validate, agent=eve
11   task.succeeded       tsk_003    duration_ms=9800, artifact_ids=[art_03]
12   artifact.stored      art_03     name=qa_report.md, size_bytes=3500
13   task.dispatched      tsk_004    task_type=data.report, agent=data
14   task.succeeded       tsk_004    duration_ms=7600, artifact_ids=[art_04]
15   artifact.stored      art_04     name=analytics_report.md, size_bytes=2900
16   task.dispatched      tsk_005    task_type=governance.review, agent=max
17   task.succeeded       tsk_005    duration_ms=11100, artifact_ids=[art_05]
18   artifact.stored      art_05     name=governance_review.md, size_bytes=3100
19   run.completed        run_001    finished_at=T1, artifact_count=5
```

### Sequence 2: Task Fail → Retry → Recovery

```
seq  event_type           entity     payload (key fields)
───  ──────────────────   ────────   ──────────────────────────────
 1   cycle.created        cyc_002    project_id=proj_42
 2   run.created          run_002    run_number=1, initiated_by=cli
 3   run.started          run_002    task_count=5
 4   task.dispatched      tsk_010    task_type=strategy.analyze_prd, agent=nat
 5   task.succeeded       tsk_010    duration_ms=11000
 6   task.dispatched      tsk_011    task_type=development.implement, agent=neo
 7   task.failed          tsk_011    error_summary="LLM timeout after 60s", duration_ms=60000
 8   run.failed           run_002    reason="Task tsk_011 failed: LLM timeout"

     ── operator retries with new run ──

 9   run.created          run_003    run_number=2, initiated_by=retry
10   run.started          run_003    task_count=5
11   task.dispatched      tsk_020    task_type=strategy.analyze_prd, agent=nat
12   task.succeeded       tsk_020    duration_ms=10500
13   task.dispatched      tsk_021    task_type=development.implement, agent=neo
14   task.succeeded       tsk_021    duration_ms=15200
     ... (remaining tasks succeed) ...
19   run.completed        run_003    artifact_count=5
```

### Sequence 3: Pulse Check Failure → Repair → Replay

```
seq  event_type               entity     payload (key fields)
───  ────────────────────     ────────   ──────────────────────────────
 1   run.started              run_004    task_count=7 (5 plan + 2 build)
 2   task.dispatched          tsk_030    task_type=strategy.analyze_prd
 3   task.succeeded           tsk_030    duration_ms=11000
 4   task.dispatched          tsk_031    task_type=development.implement
 5   task.succeeded           tsk_031    duration_ms=16000

     ── milestone boundary: post_dev ──

 6   pulse.boundary_reached   post_dev   cadence_interval_id=1, bound_suite_count=1
 7   pulse.suite_evaluated    post_dev   suite_id=dev_health, suite_outcome=FAIL,
                                          failed_checks=["file_exists:src/main.py"]
 8   pulse.boundary_decided   post_dev   decision=FAIL

     ── repair attempt 1 ──

 9   pulse.repair_started     post_dev   repair_attempt=1, failed_suite_ids=["dev_health"]
10   task.dispatched          tsk_r01    task_type=data.analyze_verification
11   task.succeeded           tsk_r01    duration_ms=8000
12   task.dispatched          tsk_r02    task_type=governance.root_cause_analysis
13   task.succeeded           tsk_r02    duration_ms=9000
14   task.dispatched          tsk_r03    task_type=strategy.corrective_plan
15   task.succeeded           tsk_r03    duration_ms=7000
16   task.dispatched          tsk_r04    task_type=development.repair
17   task.succeeded           tsk_r04    duration_ms=14000

     ── rerun failed suites only ──

18   pulse.suite_evaluated    post_dev   suite_id=dev_health, suite_outcome=PASS,
                                          repair_attempt=1
19   pulse.boundary_decided   post_dev   decision=PASS

     ── execution continues ──

20   task.dispatched          tsk_032    task_type=qa.validate
     ... (remaining tasks + build tasks) ...
31   run.completed            run_004    artifact_count=9
```

---

## Implementation Notes

### Event Bus (v0 — In-Process)

```python
class CycleEventBus:
    """In-process pub/sub. No external dependencies in v0."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[CycleEvent], None]] = []
        self._sequence: dict[tuple[str, str], int] = {}  # (cycle_id, run_id) → counter

    def subscribe(self, handler: Callable[[CycleEvent], None]) -> None: ...
    def emit(self, event_type: str, entity: ..., context: ..., payload: dict) -> CycleEvent: ...
```

In v0, the bus is synchronous and in-process. Subscribers (bridges) are called inline. This is intentional — it keeps the blast radius small and avoids infrastructure dependencies. If a bridge fails, it logs and swallows (same non-blocking contract as existing telemetry).

Future versions may upgrade to async dispatch or an external event bus (Redis Streams, NATS, etc.), but the `CycleEvent` envelope and subscriber interface remain stable.

### Where Events Are NOT Emitted

- **Inside LLM calls** — generation recording stays in LLMObservabilityPort
- **Inside queue operations** — RabbitMQ publish/consume is infrastructure
- **Inside health checks** — heartbeats are infrastructure
- **Inside log statements** — logs are operational, not semantic
- **Inside test code** — test helpers may create events directly for assertions
