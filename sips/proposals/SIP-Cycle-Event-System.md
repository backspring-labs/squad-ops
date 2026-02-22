# SIP-0XXX: Cycle Event System — Canonical Lifecycle Event Bus

**Status:** Proposed\
**Target Release:** SquadOps 0.9.9 (v0), SquadOps 1.0 (v1), SquadOps 1.1+ (v2)\
**Authors:** SquadOps Architecture\
**Created:** 2026-02-16\
**Revision:** 1

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-16 | Initial proposal from design note `docs/plans/cycle-event-system-v0.md` |

------------------------------------------------------------------------

## 1. Abstract

This SIP introduces a **Cycle Event System** — a single, canonical source of lifecycle facts for cycles, runs, gates, tasks, pulse verifications, and artifacts. Today the same semantic fact ("run X transitioned to RUNNING") is recorded in up to four places (LangFuse event, Prefect state, OTEL span, structured log) with different schemas, timing, and no coordination.

The event system replaces ad-hoc multi-sink emission with a unified event bus. Telemetry sinks become **subscribers** to events via bridge adapters, not independent emitters. This eliminates drift, enables dedupe, and provides a stable foundation for SIP-0070 pulse verification events and future observability features.

------------------------------------------------------------------------

## 2. Problem Statement

SquadOps has three telemetry subsystems wired independently:

| Subsystem | Port | Adapter | What it records |
|-----------|------|---------|-----------------|
| LLM Observability | `LLMObservabilityPort` | LangFuse | Traces, spans, generations, structured events |
| Workflow Status | (direct call) | PrefectReporter | Flow runs + task runs via REST |
| General Telemetry | `EventPort` + `MetricsPort` | OTel / Console / Null | OTEL spans, Prometheus metrics |

Plus structured logging (`logger.info("run started", extra={...})`) at every lifecycle boundary.

**Observed problems:**

1. **Schema drift** — the same transition is encoded differently per sink.
2. **Timing inconsistency** — sinks are called at different points in the execution path.
3. **No coordination** — adding a new lifecycle event requires changes in 3-4 places.
4. **No dedupe** — duplicate or near-duplicate signals with no canonical key.
5. **Scaling friction** — SIP-0070 pulse verification events will multiply the problem unless a single emission pattern exists first.

------------------------------------------------------------------------

## 3. Goals

1. Define a **20-event taxonomy** covering all lifecycle transitions across 6 entity types (cycle, run, gate, task, pulse, artifact).
2. Provide a **stable event envelope** (`CycleEvent`) that is versioned, sink-agnostic, and dedupeable.
3. Implement an **in-process event bus** (`CycleEventBus`) with synchronous pub/sub in v0.
4. Provide **bridge adapters** that translate events to existing sinks (LangFuse, Prefect, Prometheus) with zero dashboard regression.
5. Enable **incremental migration** from direct wired calls to event-first emission across three release phases.

## 4. Non-Goals

- Replacing `record_generation()` or LLM trace/span lifecycle — these are telemetry-native, not lifecycle facts.
- Introducing an external event bus (Redis Streams, NATS) in v0 — the in-process bus is intentional.
- Removing structured logging — logs are operational signals, orthogonal to semantic events.
- Defining a public event API in v0 — event store queryability is deferred to v2.

------------------------------------------------------------------------

## 5. Definitions

- **Lifecycle fact** — a semantic statement about a state transition ("run X started"). Emitted exactly once at a state machine boundary.
- **Telemetry-native signal** — data that belongs to a telemetry subsystem by nature (LLM generation content, trace parent/child structure, raw metric values). Not lifecycle facts.
- **Bridge adapter** — a subscriber that translates `CycleEvent` instances into sink-specific calls (LangFuse `record_event()`, Prefect `set_flow_run_state()`, Prometheus counter increment).
- **Semantic key** — a dedupe key computed as `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}`.

------------------------------------------------------------------------

## 6. Event Taxonomy

20 events across 6 entity lifecycles. Each event is emitted **exactly once** at a state machine boundary.

### 6.1 Cycle Events (2)

| Event | Emission Boundary | Required Fields |
|-------|-------------------|-----------------|
| `cycle.created` | `CycleRegistryPort.create_cycle()` returns | `cycle_id`, `project_id`, `created_by`, `squad_profile_id`, `prd_ref` |
| `cycle.cancelled` | `CycleRegistryPort.cancel_cycle()` returns | `cycle_id`, `cancelled_by` |

### 6.2 Run Events (7)

| Event | Emission Boundary | Required Fields |
|-------|-------------------|-----------------|
| `run.created` | `CycleRegistryPort.create_run()` returns | `cycle_id`, `run_id`, `run_number`, `initiated_by` |
| `run.started` | `update_run_status(RUNNING)` returns | `cycle_id`, `run_id`, `task_count`, `started_at` |
| `run.completed` | `update_run_status(COMPLETED)` returns | `cycle_id`, `run_id`, `finished_at`, `artifact_count` |
| `run.failed` | `update_run_status(FAILED)` returns | `cycle_id`, `run_id`, `finished_at`, `reason`, `error_summary` |
| `run.paused` | `update_run_status(PAUSED)` returns | `cycle_id`, `run_id`, `gate_name` |
| `run.resumed` | `update_run_status(RUNNING)` from PAUSED | `cycle_id`, `run_id`, `gate_name`, `decision` |
| `run.cancelled` | `update_run_status(CANCELLED)` returns | `cycle_id`, `run_id`, `cancelled_by` |

### 6.3 Gate Events (1)

| Event | Emission Boundary | Required Fields |
|-------|-------------------|-----------------|
| `gate.decided` | `CycleRegistryPort.record_gate_decision()` returns | `cycle_id`, `run_id`, `gate_name`, `decision`, `decided_by`, `decided_at`, `notes` |

### 6.4 Task Events (3)

| Event | Emission Boundary | Required Fields |
|-------|-------------------|-----------------|
| `task.dispatched` | Envelope published to RabbitMQ | `cycle_id`, `run_id`, `task_id`, `task_type`, `agent_id`, `step_index` |
| `task.succeeded` | TaskResult received with status=SUCCEEDED | `cycle_id`, `run_id`, `task_id`, `task_type`, `agent_id`, `artifact_ids`, `duration_ms` |
| `task.failed` | TaskResult received with status=FAILED | `cycle_id`, `run_id`, `task_id`, `task_type`, `agent_id`, `error_summary`, `duration_ms` |

### 6.5 Pulse Verification Events (5)

| Event | Emission Boundary | Required Fields |
|-------|-------------------|-----------------|
| `pulse.boundary_reached` | Executor detects cadence close or milestone hit | `cycle_id`, `run_id`, `boundary_id`, `cadence_interval_id`, `bound_suite_count` |
| `pulse.suite_evaluated` | `run_pulse_verification()` returns per suite | `cycle_id`, `run_id`, `boundary_id`, `suite_id`, `suite_outcome`, `check_count`, `failed_checks` |
| `pulse.boundary_decided` | `determine_boundary_decision()` returns | `cycle_id`, `run_id`, `boundary_id`, `decision` |
| `pulse.repair_started` | Repair loop begins | `cycle_id`, `run_id`, `boundary_id`, `repair_attempt`, `failed_suite_ids` |
| `pulse.repair_exhausted` | Max repair attempts reached | `cycle_id`, `run_id`, `boundary_id`, `total_attempts` |

### 6.6 Artifact Events (2)

| Event | Emission Boundary | Required Fields |
|-------|-------------------|-----------------|
| `artifact.stored` | `ArtifactVaultPort.store()` returns | `cycle_id`, `run_id`, `task_id`, `artifact_id`, `artifact_name`, `producing_task_type`, `size_bytes` |
| `artifact.baseline_set` | Baseline enforcement at route level | `cycle_id`, `run_id`, `artifact_id`, `baseline_run_id` |

------------------------------------------------------------------------

## 7. Event Envelope Schema

Stable, versioned, sink-agnostic.

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
    context: dict[str, str]      # correlation IDs (cycle_id, run_id, project_id, trace_id)
    payload: dict[str, Any]      # event-specific data
    semantic_key: str            # computed dedupe key
```

### JSON Wire Format

```json
{
  "schema_version": "1.0",
  "event_id": "evt_01JMBC3E4G7H8K9LAMBNCP0QRS",
  "event_type": "run.started",
  "occurred_at": "2026-02-16T14:30:00.123456Z",
  "sequence": 4,
  "source": { "service": "runtime-api", "version": "0.9.9" },
  "entity": { "type": "run", "id": "run_abc123", "parent_type": "cycle", "parent_id": "cyc_xyz789" },
  "context": { "cycle_id": "cyc_xyz789", "run_id": "run_abc123", "project_id": "proj_42", "trace_id": "trc_deadbeef" },
  "payload": { "task_count": 5, "started_at": "2026-02-16T14:30:00.123456Z" },
  "semantic_key": "cyc_xyz789:run:run_abc123:started:4"
}
```

### Semantic Key

Computed as `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}`.

**Invariant:** No two events in the system may share the same `semantic_key`. Duplicates indicate a bug (double emission).

### Sequence Counter

Per `(cycle_id, run_id)` pair, an in-memory monotonic counter increments on each event emission. Enables gap detection, ordering guarantees, and idempotent sinks.

------------------------------------------------------------------------

## 8. Event Bus

### v0 — In-Process Pub/Sub

```python
class CycleEventBus:
    """In-process pub/sub. No external dependencies in v0."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[CycleEvent], None]] = []
        self._sequence: dict[tuple[str, str], int] = {}

    def subscribe(self, handler: Callable[[CycleEvent], None]) -> None: ...
    def emit(self, event_type: str, entity: ..., context: ..., payload: dict) -> CycleEvent: ...
```

The bus is synchronous and in-process. Subscribers (bridges) are called inline. If a bridge fails, it logs and swallows (same non-blocking contract as existing telemetry). Future versions may upgrade to async dispatch or an external bus (Redis Streams, NATS), but the `CycleEvent` envelope and subscriber interface remain stable.

------------------------------------------------------------------------

## 9. Telemetry Coexistence

### Ownership Principle

| Concern | Owner | Why |
|---------|-------|-----|
| **What happened** (lifecycle facts) | Events | Semantic, ordered, dedupeable |
| **How long it took** (timing structure) | Spans (OTel/LangFuse) | Parent/child trace hierarchy |
| **How much** (aggregates) | Metrics (derived from events) | Counters, histograms, gauges |
| **What went wrong** (operational detail) | Logs | Debug, grep, operational forensics |
| **What the LLM said** (generation content) | LLM Observability (telemetry-native) | High-volume, sampled, redacted |

### Signal Migration Table

| Signal Category | v0 Strategy | v1 Strategy | v2 Strategy |
|----------------|-------------|-------------|-------------|
| Cycle/Run state transitions | **Mirror** — events + existing wired calls | **Replace** — remove `record_event("cycle.*")` and Prefect state calls; bridges only | **Event-only** |
| Gate decisions | **Replace** — event is first and only emission | **Event-only** | **Event-only** |
| Task dispatch/completion | **Mirror** — events alongside LangFuse task spans | **Replace** — remove `record_event("task.*")`; keep task spans | **Event + spans** |
| LLM generations | **Keep as-is** | **Keep as-is** | **Keep as-is** |
| OTEL spans/traces | **Keep as-is** | **Keep as-is** | **Keep as-is** |
| Prometheus metrics | **Keep as-is** — bridge can derive counters | **Derive** from events | **Event-derived** |
| Structured logs | **Keep as-is** | **Keep as-is** | **Keep as-is** |
| Pulse verification | **Replace** — events are first emission | **Event-only** | **Event-only** |

------------------------------------------------------------------------

## 10. Bridge Adapters

Three bridge adapters translate events to existing sinks:

### LangFuseBridge

Translates lifecycle events to `record_event()` calls on `LLMObservabilityPort`. In v1, replaces direct `record_event("cycle.started")` etc. from the executor.

### PrefectBridge

Translates run/task events to Prefect REST API calls (`set_flow_run_state()`, `create_task_run()`, `set_task_run_state()`). In v1, replaces direct PrefectReporter calls from the executor.

### MetricsBridge

Translates events to Prometheus counter/histogram updates. `task.succeeded` drives `task_duration_histogram`; `run.failed` drives `run_failures_total`.

All bridges implement the subscriber interface: `on_event(event: CycleEvent) -> None`. All bridges are non-blocking and swallow exceptions (log + continue).

------------------------------------------------------------------------

## 11. Canonical Emission Rules

1. **Single emission point per transition.** Each event is emitted from exactly one code location — the state machine boundary.

2. **Emitter is the authority, not the caller.** The event is emitted by the module that performs the state transition, not by the caller that requested it. In v0, the executor emits at the boundary between "registry acknowledged transition" and "next action." In v1+, the registry port itself may emit.

3. **No downstream re-emission.** Sinks translate events into their native format, not into new events.

------------------------------------------------------------------------

## 12. Dedupe and Drift Detection

### Sink-Side Dedupe

| Strategy | Implementation |
|----------|---------------|
| Primary key: `event_id` (ULID) | All sinks use `event_id` as primary/unique key. Retries are safe. |
| Semantic uniqueness: `semantic_key` | Unique constraint catches double-emission bugs. |
| Retention: 30 days (store), 90 days (archive) | Events older than retention are compacted/archived. |

### Drift Detection

Periodic verification job (daily or per-cycle):

1. Query event store for all events with `entity_type=run`, `entity_id=X`.
2. Query cycle registry for Run X's current status and transition history.
3. Compare: every registry state transition should have exactly one matching event. Mismatches flagged as `drift_detected` alerts.

------------------------------------------------------------------------

## 13. Migration Phases

### v0: Event Bus + Bridge Adapters (0.9.9)

**Goal:** Events exist and are emitted. Existing sinks still receive data through both bridge adapters and direct wired calls. Zero dashboard regression.

**Code changes:**
1. New module: `src/squadops/events/` — `CycleEvent`, `CycleEventBus`, sequence counter.
2. New module: `src/squadops/events/bridges/` — `LangFuseBridge`, `PrefectBridge`, `MetricsBridge`.
3. Emission points: `event_bus.emit()` at each of the 20 taxonomy boundaries.
4. Bridge wiring: `main.py` startup registers bridges as subscribers.
5. Existing wired calls remain unchanged (temporary dual-emit).

**Success gate for v1:**
- All 20 events emitting in production for >= 2 weeks
- Bridge output indistinguishable from direct wired calls (verified by parity test)
- Sequence gaps = 0 over measurement window
- Drift detection passes on 100% of completed cycles

### v1: Rewire Call Sites (1.0)

**Goal:** Remove direct wired calls one category at a time. Bridges become the sole path to LangFuse/Prefect.

| Step | Remove | Bridge Handles |
|------|--------|---------------|
| v1.0 | `record_event("cycle.*")` from executor | LangFuseBridge opens/closes traces from run events |
| v1.1 | Prefect `set_flow_run_state()` from executor | PrefectBridge translates run events |
| v1.2 | Prefect task run calls from executor | PrefectBridge translates task events |
| v1.3 | `record_event("task.*")` from agent shims | LangFuseBridge translates task events |

**Success gate for v2:**
- All wired lifecycle calls removed (only trace/span/generation/flush remain)
- Zero drift alerts over >= 4 weeks
- Dashboard parity verified

### v2: Event-First (1.1+)

**Goal:** Events are the only source of lifecycle truth. `LLMObservabilityPort` narrowed to tracing-only concerns. Event store becomes queryable via API.

------------------------------------------------------------------------

## 14. Spec Changes

### New Modules

| Module | Contents |
|--------|----------|
| `src/squadops/events/__init__.py` | `CycleEvent` dataclass |
| `src/squadops/events/bus.py` | `CycleEventBus` (in-process pub/sub) |
| `src/squadops/events/bridges/langfuse.py` | `LangFuseBridge` subscriber |
| `src/squadops/events/bridges/prefect.py` | `PrefectBridge` subscriber |
| `src/squadops/events/bridges/metrics.py` | `MetricsBridge` subscriber |

### Modified Modules (v0)

| Module | Change |
|--------|--------|
| `adapters/cycles/distributed_flow_executor.py` | Add `event_bus.emit()` at run/task boundaries |
| `src/squadops/api/runtime/main.py` | Wire `CycleEventBus`, register bridge subscribers at startup |
| `src/squadops/api/routes/cycles/` | Add `event_bus.emit()` at cycle/gate/artifact boundaries |

### Optional Dependency

`ulid-py` (or equivalent) for ULID generation. Falls back to UUID4 if not installed.

------------------------------------------------------------------------

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Dual-emit divergence in v0 (event says one thing, wired call says another) | Parity test suite compares bridge output to direct call output |
| Bridge failure blocks execution | Non-blocking contract: bridges log and swallow exceptions |
| Event bus adds latency to state transitions | Synchronous in-process call; measured overhead target < 1ms per event |
| 20-event taxonomy is incomplete | Taxonomy is additive — new events can be added without breaking existing ones |
| Sequence counter lost on process restart | Acceptable in v0 (in-memory); v1+ persists counter in event store |

------------------------------------------------------------------------

## 16. Acceptance Criteria

1. `CycleEvent` frozen dataclass exists with all fields from Section 7.
2. `CycleEventBus` supports `subscribe()` and `emit()` with monotonic sequence counter.
3. All 20 taxonomy events are emitted at the correct state machine boundaries.
4. `LangFuseBridge`, `PrefectBridge`, and `MetricsBridge` translate events to existing sink calls.
5. No two events share the same `semantic_key` in a complete happy-path cycle test.
6. Sequence numbers are strictly monotonic per `(cycle_id, run_id)`.
7. Bridge parity test passes: bridge output is semantically identical to direct wired calls.
8. Drift detection test passes: every registry state transition has exactly one matching event.
9. Existing dashboards (LangFuse, Prefect, Grafana) show no data regression.
10. All existing tests continue to pass (no behavioral change in v0).

------------------------------------------------------------------------

## 17. Test Plan

| Test Suite | File | Tests | Purpose |
|------------|------|-------|---------|
| Emission Coverage | `tests/unit/events/test_event_emission.py` | ~40 | Each of 20 events emitted with correct type and required fields |
| No-Duplicate-Emission | `tests/unit/events/test_event_sequences.py` | ~10 | Full cycle: unique semantic keys, monotonic sequences |
| Bridge Parity | `tests/unit/events/test_bridge_parity.py` | ~15 | Bridge output matches direct wired call output |
| Drift Detection | `tests/unit/events/test_drift_detection.py` | ~5 | Registry state transitions match events 1:1 |

------------------------------------------------------------------------

## 18. Open Questions

1. Should the event bus support async subscribers in v0, or defer to v1?
2. Should `entity.parent_type` / `entity.parent_id` support multi-level ancestry (e.g., task → run → cycle), or is single-parent sufficient?
3. Exact ULID library choice (`python-ulid`, `ulid-py`, or inline implementation).
4. Should the event store (v2) be a new Postgres table, or reuse the existing cycle registry tables with an `events` column?
5. Interaction with SIP-0070 pulse events: should pulse event emission be implemented in this SIP or in SIP-0070's implementation?
