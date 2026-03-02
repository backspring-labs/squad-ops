---
title: Cycle Event System
status: implemented
author: SquadOps Architecture
created_at: '2026-02-16T00:00:00Z'
sip_number: 77
updated_at: '2026-03-01T21:36:49.942404Z'
---
# SIP-0XXX: Cycle Event System — Canonical Lifecycle Event Bus

**Status:** Proposed\
**Target Release:** SquadOps 0.9.15 (v0)\
**Authors:** SquadOps Architecture\
**Created:** 2026-02-16\
**Revision:** 3 (2026-02-28)

### Revision History

| Rev | Date       | Changes |
|-----|------------|---------|
| 1   | 2026-02-16 | Initial proposal from design note `docs/plans/cycle-event-system-v0.md` |
| 2   | 2026-02-28 | Acceptance-ready rewrite: Design Principles section. Expanded Terminology with formal definitions. Full Python domain model with code (CycleEvent, CycleEventBus, EventSubscriber, EventType constants). Module placement and file paths. Detailed bridge adapter contracts with code. Concrete event sequences (happy path, task failure, pulse repair, gate pause/resume). Phased rollout plan with success gates per phase. 21 numbered acceptance criteria with test specifications. Key Design Decisions section (11 decisions with alternatives considered). Resolved all 5 open questions. Backwards compatibility analysis. Updated target release to 0.9.15. |
| 3   | 2026-02-28 | Implementation tightenings (10 items): (1) Clarify `sequence` monotonicity as within-process invariant, not durable cross-restart guarantee; `event_id` + `occurred_at` remain globally unique. (2) Clarify `semantic_key` uniqueness scope: test-time and within-process invariant in v0; durable enforcement requires v2 event store. (3) Tighten route-level emission ownership: explicit rationale for why API routes are acceptable v0 emission points; note that v1+ may push authority deeper. (4) Define bridge parity as sink-equivalent semantics (same transition meaning, same entity correlation, same resulting sink state), not byte-for-byte output identity. (5) PrefectBridge: `task.dispatched` expected exactly once per task ID; duplicate dispatch is a bug, logged and ignored by bridge. (6) MetricsBridge: derives selective aggregate counters/histograms, not a full lifecycle mirror of all 20 events; preserves events-own-facts / metrics-own-measurements boundary. (7) Explicitly state no durable replay in v0: subscribers handle events inline at emission time; missed events after subscriber failure are not replayed. (8) Refine AC-10 and AC-19: "all 20 events covered" is suite-wide across multiple test scenarios, not expected from a single cycle execution. (9) `artifact.promoted` explicitly aligned to SIP-0076's canonical inter-workload handoff status; baseline setting remains a separate project-level concern. (10) Drift detection framed as registry/event parity validation, not full truth arbitration; events cannot reconstruct or override registry state in v0. |

------------------------------------------------------------------------

## 1. Abstract

This SIP introduces a **Cycle Event System** — a single, canonical source of lifecycle facts for cycles, runs, gates, tasks, pulse verifications, and artifacts. Today the same semantic fact ("run X transitioned to RUNNING") is recorded in up to four places (LangFuse event, Prefect state, OTEL span, structured log) with different schemas, timing, and no coordination.

The event system replaces ad-hoc multi-sink emission with a unified event bus. Telemetry sinks become **subscribers** to events via bridge adapters, not independent emitters. This eliminates drift, enables dedupe, and provides a stable foundation for the pipeline protocol SIPs (Planning, Implementation, Wrap-Up) that depend on reliable lifecycle facts.

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

1. **Schema drift** — the same transition is encoded differently per sink. `DistributedFlowExecutor` emits `cycle.started` via `record_event()` with a `StructuredEvent`; `AgentOrchestrator.submit_batch()` emits the same `cycle.started` event with different message format. Both exist in production.
2. **Timing inconsistency** — sinks are called at different points in the execution path. Prefect state is set before registry is updated; LangFuse events are emitted after.
3. **No coordination** — adding a new lifecycle event requires changes in 3-4 places (`record_event()`, PrefectReporter, structured log, potentially MetricsPort).
4. **No dedupe** — duplicate or near-duplicate signals with no canonical key. The same `cycle.started` fact exists in both `DistributedFlowExecutor` and `AgentOrchestrator`.
5. **Scaling friction** — the pipeline protocol SIPs (Planning Workload, Implementation Run Contract, Wrap-Up Workload) will each add new lifecycle transitions. Without a single emission pattern, each protocol multiplies the coordination problem.

------------------------------------------------------------------------

## 3. Design Principles

### 3.1 Single Source of Lifecycle Truth

Every lifecycle fact is emitted **exactly once** from **exactly one code location**. Multiple sinks receive the fact by subscribing to a canonical event, not by being wired independently at each call site. In v0, events and the cycle registry are validated for parity (drift detection); events do not yet override or reconstruct registry state. In v2, events become the authoritative source that can independently reconstruct lifecycle history.

### 3.2 Emit at the Boundary, Not from the Caller

Events are emitted at the state machine boundary — the point where a state transition is confirmed (e.g., registry port method returns). The caller that requested the transition does not emit; the module that confirms the transition does. In v0, the executor emits immediately after the registry confirms. In v1+, the registry port itself may emit.

### 3.3 Additive Taxonomy

The event taxonomy is append-only within a major schema version. New event types may be added; existing event types are never removed or renamed. Payload fields may be added to existing events but never removed. This guarantees that subscribers written for schema 1.0 continue to work as the taxonomy grows.

### 3.4 Non-Blocking Subscribers, No Durable Replay

All subscribers (bridge adapters) are non-blocking. A subscriber that fails logs the error and swallows the exception. This is the same contract as existing telemetry (`LLMObservabilityPort` methods are documented as "MUST be non-blocking"). Event emission must not slow down or break the execution path.

v0 has **no durable replay**. Subscribers must handle events inline at emission time. If a subscriber fails to process an event (exception swallowed), that event is lost for that subscriber — it is not retried or replayed. This is the tradeoff of the non-blocking contract: reliability of individual subscriber delivery is best-effort. Durable replay (persisted event log with consumer offsets) is a v2 concern.

### 3.5 Incremental Migration, Not Big Bang

The event system is introduced alongside existing telemetry (v0: dual-emit), then existing wired calls are removed one category at a time (v1: rewire). This eliminates the risk of a flag-day cutover. Each migration step has a measurable success gate.

### 3.6 Events Own Facts; Telemetry Owns Signals

Events answer "what happened" (lifecycle facts). Telemetry answers "how long did it take" (spans), "how much" (metrics), and "what did the LLM say" (generations). These are complementary, not competing. Events never carry prompt/response text. Spans never carry lifecycle semantics. Clear ownership prevents both systems from drifting into the other's domain.

------------------------------------------------------------------------

## 4. Terminology

### Lifecycle Fact

A semantic statement about a state transition ("run X started", "gate Y decided as approved"). Emitted exactly once at a state machine boundary. Lifecycle facts are ordered, dedupeable, and sink-agnostic.

### Telemetry-Native Signal

Data that belongs to a telemetry subsystem by nature: LLM generation content (high-volume, redacted, sampled), trace parent/child structure (timing hierarchy), raw metric values (counters, gauges, histograms). Not lifecycle facts — they are measurements. The event system does not replace or capture telemetry-native signals.

### CycleEvent

The canonical event envelope. A frozen dataclass carrying a lifecycle fact with full context, ordering, and dedupe metadata. Versioned by `schema_version`. All subscribers receive `CycleEvent` instances.

### CycleEventBus

The in-process pub/sub dispatcher. Accepts `emit()` calls at state machine boundaries and delivers `CycleEvent` instances to all registered subscribers synchronously. In v0, the bus is in-process with no external dependencies. Future versions may upgrade to async dispatch or an external bus (Redis Streams, NATS), but the `CycleEvent` envelope and subscriber interface remain stable.

### Bridge Adapter (Subscriber)

A subscriber that translates `CycleEvent` instances into sink-specific calls: LangFuse `record_event()`, Prefect `set_flow_run_state()`, Prometheus counter increment. Bridge adapters implement the `EventSubscriber` protocol. They translate; they do not re-emit.

### Semantic Key

A dedupe key computed as `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}`. No two events in the system may share the same semantic key. Duplicates indicate a bug (double emission).

### Event Taxonomy

The complete catalog of event types across all entity lifecycles (cycle, run, gate, task, pulse, artifact). Each event type has a fixed name (`run.started`), a defined emission boundary, and required payload fields.

------------------------------------------------------------------------

## 5. Goals

1. Define a **20-event taxonomy** covering all lifecycle transitions across 6 entity types (cycle, run, gate, task, pulse, artifact).
2. Provide a **stable event envelope** (`CycleEvent`) that is versioned, sink-agnostic, and dedupeable.
3. Implement an **in-process event bus** (`CycleEventBus`) with synchronous pub/sub in v0.
4. Provide **bridge adapters** that translate events to existing sinks (LangFuse, Prefect, Prometheus) with zero dashboard regression.
5. Enable **incremental migration** from direct wired calls to event-first emission across three release phases.
6. Provide **event sequences** as concrete reference for operator debugging ("what happened in this cycle?").

------------------------------------------------------------------------

## 6. Non-Goals

- Replacing `record_generation()` or LLM trace/span lifecycle — these are telemetry-native, not lifecycle facts.
- Introducing an external event bus (Redis Streams, NATS) in v0 — the in-process bus is intentional.
- Removing structured logging — logs are operational signals, orthogonal to semantic events.
- Defining a public event query API in v0 — event store queryability is deferred to v2.
- Implementing the v1 rewire or v2 event-first phases — this SIP covers v0 only. The v1 and v2 phases are described for architectural context but are separate work items.
- Replacing agent heartbeats or health checks — these are infrastructure signals, not lifecycle facts.

------------------------------------------------------------------------

## 7. Event Taxonomy

20 events across 6 entity lifecycles. Each event is emitted **exactly once** at a state machine boundary.

### 7.1 Cycle Events (2)

| Event | Emission Boundary | Required Payload Fields |
|-------|-------------------|------------------------|
| `cycle.created` | `CycleRegistryPort.create_cycle()` returns | `project_id`, `created_by`, `squad_profile_id`, `prd_ref` |
| `cycle.cancelled` | `CycleRegistryPort.cancel_cycle()` returns | `cancelled_by` |

### 7.2 Run Events (7)

| Event | Emission Boundary | Required Payload Fields |
|-------|-------------------|------------------------|
| `run.created` | `CycleRegistryPort.create_run()` returns | `run_number`, `initiated_by`, `workload_type` |
| `run.started` | `update_run_status(RUNNING)` returns | `task_count`, `started_at` |
| `run.completed` | `update_run_status(COMPLETED)` returns | `finished_at`, `artifact_count` |
| `run.failed` | `update_run_status(FAILED)` returns | `finished_at`, `reason`, `error_summary` |
| `run.paused` | `update_run_status(PAUSED)` returns | `gate_name` |
| `run.resumed` | `update_run_status(RUNNING)` from PAUSED | `gate_name`, `decision` |
| `run.cancelled` | `update_run_status(CANCELLED)` returns | `cancelled_by` |

`run.created` includes `workload_type` (may be `null`) to support workload-aware subscribers (SIP-0076).

### 7.3 Gate Events (1)

| Event | Emission Boundary | Required Payload Fields |
|-------|-------------------|------------------------|
| `gate.decided` | `CycleRegistryPort.record_gate_decision()` returns | `gate_name`, `decision`, `decided_by`, `decided_at`, `notes` |

### 7.4 Task Events (3)

| Event | Emission Boundary | Required Payload Fields |
|-------|-------------------|------------------------|
| `task.dispatched` | Envelope published to RabbitMQ | `task_id`, `task_type`, `agent_id`, `step_index` |
| `task.succeeded` | TaskResult received with status=SUCCEEDED | `task_id`, `task_type`, `agent_id`, `artifact_ids`, `duration_ms` |
| `task.failed` | TaskResult received with status=FAILED | `task_id`, `task_type`, `agent_id`, `error_summary`, `duration_ms` |

### 7.5 Pulse Verification Events (5)

| Event | Emission Boundary | Required Payload Fields |
|-------|-------------------|------------------------|
| `pulse.boundary_reached` | Executor detects cadence close or milestone hit | `boundary_id`, `cadence_interval_id`, `bound_suite_count` |
| `pulse.suite_evaluated` | `run_pulse_verification()` returns per suite | `boundary_id`, `suite_id`, `suite_outcome`, `check_count`, `failed_checks` |
| `pulse.boundary_decided` | `determine_boundary_decision()` returns | `boundary_id`, `decision` |
| `pulse.repair_started` | Repair loop begins | `boundary_id`, `repair_attempt`, `failed_suite_ids` |
| `pulse.repair_exhausted` | Max repair attempts reached | `boundary_id`, `total_attempts` |

### 7.6 Artifact Events (2)

| Event | Emission Boundary | Required Payload Fields |
|-------|-------------------|------------------------|
| `artifact.stored` | `ArtifactVaultPort.store()` returns | `task_id`, `artifact_id`, `artifact_name`, `producing_task_type`, `size_bytes` |
| `artifact.promoted` | `ArtifactVaultPort.promote_artifact()` returns | `artifact_id`, `artifact_type`, `promoted_by` |

Note: `artifact.baseline_set` from the design note is replaced by `artifact.promoted` per SIP-0076's artifact promotion model. `artifact.promoted` represents promotion to **canonical inter-workload handoff status** (SIP-0076 §3.5: "Promoted Artifacts as Canonical Inter-Workload Inputs"). Baseline setting (`set_baseline`) remains a separate project-level concern — it is not a lifecycle event because it is a policy decision on top of an already-promoted artifact, not a state transition in the artifact lifecycle.

------------------------------------------------------------------------

## 8. Domain Model

### 8.1 EventType Constants

Following the existing `ArtifactType` and `WorkloadType` pattern (class with string constants, not an enum), event types are free-form strings with well-known constants. This allows the taxonomy to grow without code changes.

```python
class EventType:
    """Well-known cycle event type constants.

    Event types are free-form strings in {entity}.{transition} format.
    These constants document the standard taxonomy. Custom event types
    are permitted for extensibility.
    """
    # Cycle events
    CYCLE_CREATED = "cycle.created"
    CYCLE_CANCELLED = "cycle.cancelled"

    # Run events
    RUN_CREATED = "run.created"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_PAUSED = "run.paused"
    RUN_RESUMED = "run.resumed"
    RUN_CANCELLED = "run.cancelled"

    # Gate events
    GATE_DECIDED = "gate.decided"

    # Task events
    TASK_DISPATCHED = "task.dispatched"
    TASK_SUCCEEDED = "task.succeeded"
    TASK_FAILED = "task.failed"

    # Pulse verification events
    PULSE_BOUNDARY_REACHED = "pulse.boundary_reached"
    PULSE_SUITE_EVALUATED = "pulse.suite_evaluated"
    PULSE_BOUNDARY_DECIDED = "pulse.boundary_decided"
    PULSE_REPAIR_STARTED = "pulse.repair_started"
    PULSE_REPAIR_EXHAUSTED = "pulse.repair_exhausted"

    # Artifact events
    ARTIFACT_STORED = "artifact.stored"
    ARTIFACT_PROMOTED = "artifact.promoted"
```

Placement: `src/squadops/events/types.py`

### 8.2 CycleEvent Envelope

```python
@dataclass(frozen=True)
class CycleEvent:
    """Canonical lifecycle event envelope.

    Versioned, sink-agnostic, dedupeable. All lifecycle facts flow
    through this model. Subscribers receive CycleEvent instances and
    translate them to sink-specific formats.

    Fields are ordered: identity → timing → source → entity → context → data.
    """
    # Identity
    schema_version: str          # "1.0"
    event_id: str                # ULID (time-ordered, globally unique)
    event_type: str              # EventType constant (e.g., "run.started")

    # Timing
    occurred_at: datetime        # UTC wall-clock time at emission
    sequence: int                # Monotonic counter per (cycle_id, run_id)

    # Source
    source_service: str          # Emitting service ("runtime-api", "agent-neo")
    source_version: str          # Code version (e.g., "0.9.15")

    # Entity
    entity_type: str             # "cycle", "run", "gate", "task", "pulse", "artifact"
    entity_id: str               # Entity's primary identifier
    parent_type: str | None      # Parent entity type (e.g., "cycle" for a run event)
    parent_id: str | None        # Parent entity ID

    # Context (correlation)
    context: dict[str, str]      # Always includes cycle_id; may include run_id, project_id, trace_id

    # Data
    payload: dict[str, Any]      # Event-type-specific data (see taxonomy tables)

    # Dedupe
    semantic_key: str            # Computed: {cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}
```

Placement: `src/squadops/events/models.py`

### 8.3 Semantic Key

Computed as `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}`.

Examples:
- `cyc_xyz:run:run_abc:started:4`
- `cyc_xyz:task:tsk_001:succeeded:7`
- `cyc_xyz:gate:progress_plan_review:decided:9`
- `cyc_xyz:pulse:post_dev:boundary_decided:12`

**Invariant:** No two events in the system may share the same `semantic_key`. Duplicates indicate a bug (double emission). The `CycleEventBus` does not enforce uniqueness (it is a dispatcher, not a store), but the acceptance test suite validates this invariant for all event sequences.

**v0 scope:** `semantic_key` uniqueness is a **test-time and within-process invariant**. Because `sequence` resets on process restart (Section 8.5), the same `(cycle_id, run_id)` resumed in a new process could produce duplicate semantic keys. This is a known v0 limitation. Durable global enforcement requires the v2 event store with a persisted sequence counter. In practice, v0 cycles run within a single process lifetime, so collisions are unlikely outside of checkpoint/resume scenarios.

### 8.4 Entity Hierarchy

`parent_type` and `parent_id` encode single-level parentage. This is sufficient for the current hierarchy:

| Entity Type | Parent Type | Parent ID |
|-------------|-------------|-----------|
| `cycle` | `None` | `None` |
| `run` | `cycle` | `cycle_id` |
| `gate` | `run` | `run_id` |
| `task` | `run` | `run_id` |
| `pulse` | `run` | `run_id` |
| `artifact` | `run` | `run_id` |

Multi-level ancestry (task → run → cycle) is available via the `context` dict, which always includes `cycle_id` and `run_id` when applicable. The parent fields are for direct navigation; the context dict is for full correlation.

### 8.5 Sequence Counter

Per `(cycle_id, run_id)` pair, an in-memory monotonic counter increments on each event emission. Enables:

- **Gap detection**: if a consumer sees sequence 5 then 7, sequence 6 was lost.
- **Ordering**: events with lower sequence numbers happened first within a run.
- **Idempotent sinks**: `(event_id, semantic_key)` together uniquely identify an event.

For cycle-level events (`cycle.created`, `cycle.cancelled`), `run_id` is `""` (empty string). The sequence counter for `(cycle_id, "")` tracks cycle-level event ordering independently.

**v0 scope:** The counter is in-memory. `sequence` is **monotonic within a single process lifetime** for a given `(cycle_id, run_id)`. It is **not** a durable global ordering guarantee across process restarts. On process restart, the counter resets to 0. `event_id` (ULID/UUID4) and `occurred_at` remain globally unique and correlatable regardless of sequence counter state. `sequence` is a local ordering aid in v0.

This is acceptable in v0 because:
1. Events carry ULIDs (globally unique regardless of sequence).
2. Sequence gaps after restart are detectable by consumers via `occurred_at` timestamps.
3. v1+ persists the counter in the event store, upgrading to a durable ordering guarantee.

------------------------------------------------------------------------

## 9. Event Bus

### 9.1 CycleEventBus

```python
class EventSubscriber(Protocol):
    """Protocol for event subscribers (bridge adapters)."""

    def on_event(self, event: CycleEvent) -> None:
        """Handle a lifecycle event. MUST be non-blocking.

        Implementations MUST NOT raise exceptions. Errors are logged
        internally and swallowed. This matches the existing telemetry
        contract (LLMObservabilityPort: "All methods MUST be non-blocking").
        """
        ...


class CycleEventBus:
    """In-process synchronous event bus.

    Subscribers are called inline during emit(). If a subscriber fails,
    it logs the exception and continues to the next subscriber. Event
    emission never fails — it returns the CycleEvent regardless of
    subscriber outcomes.

    Thread safety: v0 is single-threaded (asyncio event loop). No
    locking required. If multi-threaded dispatch is needed in the
    future, add a lock around _subscribers and _sequence.
    """

    def __init__(self, source_service: str, source_version: str) -> None:
        self._subscribers: list[EventSubscriber] = []
        self._sequence: dict[tuple[str, str], int] = {}
        self._source_service = source_service
        self._source_version = source_version

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register a subscriber. Subscribers are called in registration order."""
        self._subscribers.append(subscriber)

    def emit(
        self,
        event_type: str,
        *,
        entity_type: str,
        entity_id: str,
        parent_type: str | None = None,
        parent_id: str | None = None,
        context: dict[str, str],
        payload: dict[str, Any],
    ) -> CycleEvent:
        """Emit a lifecycle event.

        Constructs a CycleEvent with auto-generated event_id (ULID),
        occurred_at (UTC now), sequence (monotonic), and semantic_key
        (computed). Delivers to all subscribers synchronously.

        Returns the constructed CycleEvent for caller inspection/logging.
        Never raises — subscriber failures are logged and swallowed.
        """
        cycle_id = context.get("cycle_id", "")
        run_id = context.get("run_id", "")
        seq_key = (cycle_id, run_id)
        seq = self._sequence.get(seq_key, 0) + 1
        self._sequence[seq_key] = seq

        transition = event_type.split(".")[-1] if "." in event_type else event_type
        semantic_key = f"{cycle_id}:{entity_type}:{entity_id}:{transition}:{seq}"

        event = CycleEvent(
            schema_version="1.0",
            event_id=_generate_event_id(),
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            sequence=seq,
            source_service=self._source_service,
            source_version=self._source_version,
            entity_type=entity_type,
            entity_id=entity_id,
            parent_type=parent_type,
            parent_id=parent_id,
            context=context,
            payload=payload,
            semantic_key=semantic_key,
        )

        for subscriber in self._subscribers:
            try:
                subscriber.on_event(event)
            except Exception:
                logger.exception(
                    "Event subscriber %s failed for %s",
                    type(subscriber).__name__,
                    event_type,
                )

        return event
```

Placement: `src/squadops/events/bus.py`

### 9.2 Event ID Generation

```python
def _generate_event_id() -> str:
    """Generate a time-ordered, globally unique event ID.

    Uses ULID format (evt_ prefix + 26-char Crockford base32).
    Falls back to UUID4 with evt_ prefix if ulid library is unavailable.
    """
    try:
        import ulid
        return f"evt_{ulid.new().str}"
    except ImportError:
        return f"evt_{uuid4().hex}"
```

The `ulid-py` library is an optional dependency. UUID4 fallback is acceptable because:
1. ULIDs are preferable (time-ordered, shorter), not required.
2. The `event_id` field is a unique key, not a sort key. `sequence` provides ordering.
3. `semantic_key` provides the canonical dedupe key, not `event_id`.

### 9.3 NoOpEventBus

```python
class NoOpEventBus:
    """No-op event bus for environments where events are not configured.

    Implements the same interface as CycleEventBus but discards all
    events. Used in test harnesses and legacy code paths that have not
    been wired to the event system.
    """

    def subscribe(self, subscriber: EventSubscriber) -> None:
        pass

    def emit(self, event_type: str, **kwargs: Any) -> None:
        pass
```

Placement: `src/squadops/events/bus.py` (same module as `CycleEventBus`)

The always-inject NoOp pattern (Section 3.4 of CLAUDE.md) applies: when no event bus is configured, inject `NoOpEventBus` instead of `None`. This eliminates null checks at every emission point.

------------------------------------------------------------------------

## 10. Telemetry Coexistence

### 10.1 Ownership Principle

| Concern | Owner | Why |
|---------|-------|-----|
| **What happened** (lifecycle facts) | Events (`CycleEvent`) | Semantic, ordered, dedupeable |
| **How long it took** (timing structure) | Spans (OTel/LangFuse) | Parent/child trace hierarchy |
| **How much** (aggregates) | Metrics (derived from events) | Counters, histograms, gauges |
| **What went wrong** (operational detail) | Logs | Debug, grep, operational forensics |
| **What the LLM said** (generation content) | LLM Observability (telemetry-native) | High-volume, sampled, redacted |

### 10.2 Signal Migration Table

| Signal Category | v0 Strategy | v1 Strategy | v2 Strategy |
|----------------|-------------|-------------|-------------|
| Cycle/Run state transitions | **Mirror** — events + existing wired calls | **Replace** — remove `record_event("cycle.*")` and Prefect state calls; bridges only | **Event-only** |
| Gate decisions | **Mirror** — events + existing structured logs | **Replace** — bridges only | **Event-only** |
| Task dispatch/completion | **Mirror** — events alongside LangFuse task spans | **Replace** — remove `record_event("task.*")`; keep task spans | **Event + spans** |
| LLM generations | **Keep as-is** | **Keep as-is** | **Keep as-is** |
| OTEL spans/traces | **Keep as-is** | **Keep as-is** | **Keep as-is** |
| Prometheus metrics | **Keep as-is** — bridge can derive counters | **Derive** from events | **Event-derived** |
| Structured logs | **Keep as-is** | **Keep as-is** | **Keep as-is** |
| Pulse verification | **Mirror** — events alongside existing `_emit_pulse_event()` calls | **Replace** — bridges only | **Event-only** |
| Agent heartbeats | **Keep as-is** — infrastructure | **Keep as-is** | **Keep as-is** |
| Run reports | **Keep as-is** — artifact, not signal | **Keep as-is** | **Keep as-is** |

### 10.3 What Stays Stable Through All Phases

- `start_cycle_trace()` / `end_cycle_trace()` — trace structure is telemetry-native
- `start_task_span()` / `end_task_span()` — span structure is telemetry-native
- `start_pulse_span()` / `end_pulse_span()` — span structure is telemetry-native
- `record_generation()` — generation recording is telemetry-native
- `flush()` / `close()` — lifecycle management is telemetry-native
- All structured logging — operational, not semantic
- All agent heartbeats — infrastructure, not lifecycle

------------------------------------------------------------------------

## 11. Bridge Adapters

Three bridge adapters translate events to existing sinks. All bridges implement the `EventSubscriber` protocol and follow the non-blocking contract (Design Principle 3.4).

### 11.1 LangFuseBridge

Translates lifecycle events to `record_event()` calls on `LLMObservabilityPort`.

```python
class LangFuseBridge:
    """Translates CycleEvent instances to LangFuse record_event() calls.

    In v0, this runs alongside existing direct record_event() calls
    (dual-emit). In v1, this replaces them.

    Requires an active LLMObservabilityPort and a CorrelationContext
    factory to bridge event context to telemetry context.
    """

    def __init__(self, llm_observability: LLMObservabilityPort) -> None:
        self._llm_obs = llm_observability

    def on_event(self, event: CycleEvent) -> None:
        """Translate lifecycle event to LangFuse structured event."""
        ctx = CorrelationContext.for_cycle(
            cycle_id=event.context.get("cycle_id", ""),
            trace_id=event.context.get("trace_id"),
        )
        structured = StructuredEvent(
            name=event.event_type,
            message=self._format_message(event),
            attributes=tuple(
                (k, str(v)) for k, v in event.payload.items()
            ),
        )
        self._llm_obs.record_event(ctx, structured)

    def _format_message(self, event: CycleEvent) -> str:
        """Format a human-readable message from event data."""
        return f"{event.event_type}: {event.entity_type} {event.entity_id}"
```

Placement: `src/squadops/events/bridges/langfuse.py`

### 11.2 PrefectBridge

Translates run and task events to Prefect REST API calls.

```python
class PrefectBridge:
    """Translates CycleEvent instances to PrefectReporter calls.

    Maps run lifecycle events to flow run states and task lifecycle
    events to task run states.
    """

    _RUN_STATE_MAP: ClassVar[dict[str, str]] = {
        EventType.RUN_STARTED: "RUNNING",
        EventType.RUN_COMPLETED: "COMPLETED",
        EventType.RUN_FAILED: "FAILED",
        EventType.RUN_CANCELLED: "CANCELLED",
        EventType.RUN_PAUSED: "PAUSED",
    }

    _TASK_STATE_MAP: ClassVar[dict[str, str]] = {
        EventType.TASK_DISPATCHED: "RUNNING",
        EventType.TASK_SUCCEEDED: "COMPLETED",
        EventType.TASK_FAILED: "FAILED",
    }

    def __init__(self, prefect_reporter: PrefectReporter) -> None:
        self._prefect = prefect_reporter

    def on_event(self, event: CycleEvent) -> None:
        """Translate lifecycle event to Prefect state transition."""
        if event.event_type in self._RUN_STATE_MAP:
            state = self._RUN_STATE_MAP[event.event_type]
            self._prefect.set_flow_run_state(state, state.title())
        elif event.event_type in self._TASK_STATE_MAP:
            state = self._TASK_STATE_MAP[event.event_type]
            if event.event_type == EventType.TASK_DISPATCHED:
                self._prefect.create_task_run(
                    event.payload.get("task_type", "unknown"),
                    event.payload.get("task_id", ""),
                )
            self._prefect.set_task_run_state(
                event.payload.get("task_id", ""),
                state,
                state.title(),
            )
```

Placement: `src/squadops/events/bridges/prefect.py`

**Task dispatch contract:** `task.dispatched` is expected exactly once per `task_id` in v0. The `PrefectBridge` calls `create_task_run()` on dispatch and `set_task_run_state()` on success/failure. A duplicate `task.dispatched` for the same `task_id` is a bug in the emission layer; the bridge logs a warning and ignores the duplicate (does not create a second Prefect task run).

### 11.3 MetricsBridge

Translates events to Prometheus counter/histogram updates.

```python
class MetricsBridge:
    """Translates CycleEvent instances to MetricsPort calls.

    Derives counters and histograms from lifecycle events.
    """

    _COUNTER_MAP: ClassVar[dict[str, str]] = {
        EventType.RUN_COMPLETED: "runs_completed_total",
        EventType.RUN_FAILED: "runs_failed_total",
        EventType.TASK_SUCCEEDED: "tasks_succeeded_total",
        EventType.TASK_FAILED: "tasks_failed_total",
        EventType.PULSE_REPAIR_EXHAUSTED: "pulse_repairs_exhausted_total",
    }

    def __init__(self, metrics_port: MetricsPort) -> None:
        self._metrics = metrics_port

    def on_event(self, event: CycleEvent) -> None:
        """Translate lifecycle event to metric updates."""
        counter_name = self._COUNTER_MAP.get(event.event_type)
        if counter_name:
            self._metrics.increment(counter_name)

        if event.event_type == EventType.TASK_SUCCEEDED:
            duration = event.payload.get("duration_ms")
            if duration is not None:
                self._metrics.observe("task_duration_ms", duration)
```

Placement: `src/squadops/events/bridges/metrics.py`

**Selectivity rule:** `MetricsBridge` derives **aggregate operational counters and histograms only**, not a full lifecycle mirror of all 20 events. The `_COUNTER_MAP` is intentionally selective — only terminal/outcome events drive counters. Not every event type should automatically gain a counter. This preserves the "events own facts; metrics own measurements" boundary (Design Principle 3.6). New metric derivations are added deliberately, not by default.

------------------------------------------------------------------------

## 12. Canonical Emission Rules

### 12.1 Single Emission Point Per Transition

Each event is emitted from exactly one code location — the state machine boundary. For v0, this means the executor emits immediately after the registry port method returns:

```
# v0 pattern: executor emits at registry return boundary
run = await self._registry.update_run_status(run_id, RunStatus.RUNNING)
self._event_bus.emit(
    EventType.RUN_STARTED,
    entity_type="run",
    entity_id=run.run_id,
    parent_type="cycle",
    parent_id=run.cycle_id,
    context={"cycle_id": run.cycle_id, "run_id": run.run_id, "project_id": project_id},
    payload={"task_count": len(plan), "started_at": run.started_at.isoformat()},
)
```

### 12.2 Emitter Is the Authority

The event is emitted by the module that confirms the state transition, not by the caller that requested it. In v0, the executor is the authority because it holds the registry port reference and confirms the transition. In v1+, the registry port itself may emit.

### 12.3 No Downstream Re-Emission

Sinks translate events into their native format, not into new events. If `LangFuseBridge` receives `run.started`, it calls `record_event(StructuredEvent(name="run.started"))`. It does not emit a second `CycleEvent`.

------------------------------------------------------------------------

## 13. Dedupe and Drift Detection

### 13.1 Sink-Side Dedupe

| Strategy | Implementation |
|----------|---------------|
| Primary key: `event_id` (ULID) | All sinks use `event_id` as primary/unique key. Retries are safe. |
| Semantic uniqueness: `semantic_key` | Unique constraint catches double-emission bugs. |
| Retention: 30 days (store), 90 days (archive) | Events older than retention are compacted/archived. |

### 13.2 Drift Detection

Drift detection validates **parity between the canonical event stream and mutable registry state**. It does not imply that events can reconstruct or override registry state independently — that belongs to later event-store phases (v2). In v0, drift detection confirms that the event system and the registry agree on what happened.

Verification approach (periodic or per-cycle):

1. Query event stream for all events with `entity_type=run`, `entity_id=X`.
2. Query cycle registry for Run X's current status and transition history.
3. Compare: every registry state transition should have exactly one matching event. Mismatches flagged as `drift_detected` alerts.

Drift detection is a **test-time concern** in v0 (unit test suite validates event-registry parity for each test scenario). Production drift detection (automated periodic job) is a v2 concern that requires the persistent event store.

------------------------------------------------------------------------

## 14. Event Sequences

Concrete reference sequences showing the event flow for common scenarios. These serve as operator debugging aids and as test oracles.

### 14.1 Happy-Path Cycle

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

### 14.2 Task Failure → Retry → Recovery

```
seq  event_type           entity     payload (key fields)
───  ──────────────────   ────────   ──────────────────────────────
 1   cycle.created        cyc_002    project_id=proj_42
 2   run.created          run_002    run_number=1, initiated_by=cli
 3   run.started          run_002    task_count=5
 4   task.dispatched      tsk_010    task_type=strategy.analyze_prd
 5   task.succeeded       tsk_010    duration_ms=11000
 6   task.dispatched      tsk_011    task_type=development.implement
 7   task.failed          tsk_011    error_summary="LLM timeout after 60s"
 8   run.failed           run_002    reason="Task tsk_011 failed"

     ── operator retries with new run ──

 9   run.created          run_003    run_number=2, initiated_by=retry
10   run.started          run_003    task_count=5
11   task.dispatched      tsk_020    task_type=strategy.analyze_prd
12   task.succeeded       tsk_020    duration_ms=10500
     ... (remaining tasks succeed) ...
19   run.completed        run_003    artifact_count=5
```

### 14.3 Pulse Check Failure → Repair → Recovery

```
seq  event_type               entity     payload (key fields)
───  ────────────────────     ────────   ──────────────────────────
 1   run.started              run_004    task_count=7
 2   task.dispatched          tsk_030    task_type=strategy.analyze_prd
 3   task.succeeded           tsk_030    duration_ms=11000
 4   task.dispatched          tsk_031    task_type=development.implement
 5   task.succeeded           tsk_031    duration_ms=16000

     ── pulse boundary: post_dev ──

 6   pulse.boundary_reached   post_dev   bound_suite_count=1
 7   pulse.suite_evaluated    post_dev   suite_id=dev_health, suite_outcome=FAIL,
                                          failed_checks=["file_exists:src/main.py"]
 8   pulse.boundary_decided   post_dev   decision=FAIL

     ── repair attempt 1 ──

 9   pulse.repair_started     post_dev   repair_attempt=1
10   task.dispatched          tsk_r01    task_type=data.analyze_verification
11   task.succeeded           tsk_r01    duration_ms=8000
12   task.dispatched          tsk_r02    task_type=development.repair
13   task.succeeded           tsk_r02    duration_ms=14000

     ── rerun failed suites only ──

14   pulse.suite_evaluated    post_dev   suite_id=dev_health, suite_outcome=PASS
15   pulse.boundary_decided   post_dev   decision=PASS

     ── execution continues ──

16   task.dispatched          tsk_032    task_type=qa.validate
     ...
25   run.completed            run_004    artifact_count=9
```

### 14.4 Gate Pause → Decision → Resume

```
seq  event_type           entity                  payload (key fields)
───  ──────────────────   ──────────────────────   ──────────────────────
 1   run.created          run_005                  workload_type=planning
 2   run.started          run_005                  task_count=3
 3   task.dispatched      tsk_040                  task_type=strategy.plan
 4   task.succeeded       tsk_040                  duration_ms=15000
 5   run.paused           run_005                  gate_name=progress_plan_review

     ── operator reviews plan (hours later) ──

 6   gate.decided         progress_plan_review     decision=approved, decided_by=admin
 7   run.resumed          run_005                  gate_name=progress_plan_review, decision=approved

     ── next workload begins ──

 8   run.created          run_006                  workload_type=implementation
 9   run.started          run_006                  task_count=5
     ...
```

------------------------------------------------------------------------

## 15. Spec Changes

### 15.1 New Modules

| Module | Contents |
|--------|----------|
| `src/squadops/events/__init__.py` | Public exports: `CycleEvent`, `CycleEventBus`, `NoOpEventBus`, `EventSubscriber`, `EventType` |
| `src/squadops/events/models.py` | `CycleEvent` frozen dataclass |
| `src/squadops/events/types.py` | `EventType` constants class |
| `src/squadops/events/bus.py` | `CycleEventBus`, `NoOpEventBus`, `EventSubscriber` protocol, `_generate_event_id()` |
| `src/squadops/events/bridges/__init__.py` | Bridge adapter exports |
| `src/squadops/events/bridges/langfuse.py` | `LangFuseBridge` subscriber |
| `src/squadops/events/bridges/prefect.py` | `PrefectBridge` subscriber |
| `src/squadops/events/bridges/metrics.py` | `MetricsBridge` subscriber |

### 15.2 Modified Modules (v0)

| Module | Change |
|--------|--------|
| `adapters/cycles/distributed_flow_executor.py` | Add `event_bus` parameter to constructor. Add `event_bus.emit()` at run/task/pulse boundaries. Existing `record_event()` and PrefectReporter calls remain unchanged (dual-emit). |
| `src/squadops/api/runtime/main.py` | Wire `CycleEventBus` at startup. Register bridge subscribers. Inject bus into executor. |
| `src/squadops/api/routes/cycles/cycles.py` | Add `event_bus.emit()` at `cycle.created` and `cycle.cancelled` boundaries. |
| `src/squadops/api/routes/cycles/runs.py` | Add `event_bus.emit()` at `gate.decided` boundary (if gate decisions are recorded via API route). |
| `src/squadops/api/routes/cycles/artifacts.py` | Add `event_bus.emit()` at `artifact.stored` and `artifact.promoted` boundaries. |

**Route-level emission rationale (v0):** Some events (`cycle.created`, `cycle.cancelled`, `gate.decided`, `artifact.stored`, `artifact.promoted`) are emitted from API routes rather than from the executor or registry adapter. This is acceptable in v0 because the API route is the state transition boundary for these operations — the route calls the registry port, receives the confirmed result, and emits the event immediately after. The route is the first code that knows the transition succeeded. In v1+, emission authority may be pushed deeper into the registry port or a domain service, but in v0, the route is the pragmatic boundary. This is consistent with Design Principle 3.2 (emit where the transition is confirmed).

### 15.3 Optional Dependency

`ulid-py` for ULID generation. Falls back to UUID4 if not installed. Added to `requirements-api.txt` as an optional dependency (not required).

------------------------------------------------------------------------

## 16. Backwards Compatibility

### 16.1 Existing Telemetry

All existing `record_event()`, PrefectReporter, and structured logging calls remain unchanged in v0. The event system is purely additive. Dashboards (LangFuse, Prefect, Grafana) see no data regression because:
1. Existing wired calls continue to fire (dual-emit).
2. Bridge adapters produce equivalent output to existing wired calls.
3. No existing code is removed or modified in v0.

### 16.2 Executor Interface

The `DistributedFlowExecutor` gains an optional `event_bus` constructor parameter with a `NoOpEventBus` default. Existing callers that do not pass an event bus are unaffected. The executor's public API does not change.

### 16.3 API Routes

API route functions gain an optional event bus dependency via the existing DI mechanism. Routes that do not have an event bus configured emit no events. No API behavior, request format, or response format changes.

### 16.4 Test Impact

All existing tests pass without modification. The `NoOpEventBus` default means no test needs to provide an event bus unless it specifically tests event emission. New test markers (`domain_events`) are registered in `pyproject.toml`.

------------------------------------------------------------------------

## 17. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Dual-emit divergence in v0 (event says one thing, wired call says another) | Parity test suite compares bridge output to direct call output (AC-7) |
| Bridge failure blocks execution | Non-blocking contract: bridges log and swallow exceptions (Design Principle 3.4) |
| Event bus adds latency to state transitions | Synchronous in-process call; measured overhead target < 1ms per event. 20 events per cycle = < 20ms total overhead |
| 20-event taxonomy is incomplete | Taxonomy is additive (Design Principle 3.3). New events can be added without breaking existing subscribers |
| Sequence counter lost on process restart | Acceptable in v0 (in-memory). Events carry ULIDs for global uniqueness regardless. v1+ persists counter |
| ULID library not available | UUID4 fallback with `evt_` prefix. No functional difference — ULID is a quality-of-life improvement, not a requirement |

------------------------------------------------------------------------

## 18. Rollout Plan

### Phase 1: Domain Models and Event Bus (Foundation)

1. `EventType` constants class in `src/squadops/events/types.py`.
2. `CycleEvent` frozen dataclass in `src/squadops/events/models.py`.
3. `CycleEventBus`, `NoOpEventBus`, `EventSubscriber` protocol in `src/squadops/events/bus.py`.
4. `_generate_event_id()` with ULID/UUID4 fallback.
5. Unit tests: event construction, sequence counter monotonicity, semantic key computation, subscriber dispatch, subscriber failure isolation.

**Success gate:** `CycleEventBus` correctly constructs events, dispatches to subscribers, isolates failures, and maintains monotonic sequences. All new tests pass. `run_new_arch_tests.sh` green.

### Phase 2: Bridge Adapters

1. `LangFuseBridge` in `src/squadops/events/bridges/langfuse.py`.
2. `PrefectBridge` in `src/squadops/events/bridges/prefect.py`.
3. `MetricsBridge` in `src/squadops/events/bridges/metrics.py`.
4. Unit tests: each bridge translates events to correct sink-specific calls.
5. Parity tests: bridge output is sink-equivalent to existing direct wired calls (same transition meaning, same entity correlation, same resulting sink state; message formatting may differ).

**Success gate:** Bridge parity tests pass. Each bridge produces sink-equivalent output to the existing wired calls it will eventually replace.

### Phase 3: Emission Points and Wiring

1. Add `event_bus` parameter to `DistributedFlowExecutor` constructor (default: `NoOpEventBus`).
2. Add `event_bus.emit()` at each of the 20 taxonomy boundaries in executor code.
3. Add cycle/artifact emission points in API routes.
4. Wire `CycleEventBus` in `main.py` startup; register bridge subscribers.
5. Unit tests: each emission point fires the correct event type with required payload fields.
6. Integration test: full happy-path cycle produces complete event sequence with no gaps.

**Success gate:** All 20 events emitting at correct boundaries. Sequence numbers strictly monotonic. No duplicate semantic keys in a full cycle. Existing tests still pass (no behavioral change).

### Phase 4: Drift Detection and Acceptance

1. Drift detection test: every registry state transition has exactly one matching event.
2. Event sequence tests match the reference sequences in Section 14.
3. Register `domain_events` marker in `pyproject.toml`.
4. Version bump.

**Success gate:** Drift detection passes on 100% of test cycles. All acceptance criteria (Section 19) met.

------------------------------------------------------------------------

## 19. Acceptance Criteria

1. `CycleEvent` frozen dataclass exists with all fields from Section 8.2. Test: construct a `CycleEvent` with all fields; verify field access, immutability, and defaults.

2. `EventType` constants class defines all 20 event type strings from Section 7. Test: assert each constant matches `{entity}.{transition}` format.

3. `CycleEventBus` supports `subscribe()` and `emit()`. Test: register a subscriber, emit an event, verify subscriber receives the event.

4. `CycleEventBus.emit()` produces strictly monotonic sequence numbers per `(cycle_id, run_id)`. Test: emit 5 events for the same run, verify sequences are 1, 2, 3, 4, 5.

5. `CycleEventBus.emit()` computes correct `semantic_key` in `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}` format. Test: emit an event, verify semantic_key matches expected format.

6. Subscriber failures do not propagate. Test: register a subscriber that raises `RuntimeError`, emit an event, verify no exception is raised and the event is returned.

7. Bridge parity test passes: bridge output is **sink-equivalent** to direct wired calls for the same lifecycle transitions. Parity means: same transition meaning, same entity identity and correlation, same resulting sink-level state outcome. Message text formatting may differ if the sink behavior and result are equivalent. For example: Prefect parity means the same resulting Prefect state (not byte-for-byte request payload equality); LangFuse parity means the same event name and correlation semantics (not necessarily identical message strings). Test: capture sink API args from bridge and from direct call, compare transition meaning and entity correlation.

8. `PrefectBridge` translates run events to correct Prefect states. Test: emit `run.started`, verify `set_flow_run_state("RUNNING")` is called.

9. `MetricsBridge` translates events to correct metric updates. Test: emit `task.succeeded` with `duration_ms`, verify `observe("task_duration_ms", ...)` is called.

10. All 20 taxonomy events are covered at the correct state machine boundaries **across the test suite**. No single cycle execution is expected to produce all 20 events (e.g., a happy-path cycle will not produce `run.failed`, `pulse.repair_exhausted`, or `run.cancelled`). Test: multiple test scenarios (happy path, task failure, pulse repair, gate pause, cancellation) collectively cover all 20 event types. Each scenario verifies that its expected subset of events is emitted exactly once at the correct boundaries.

11. No two events share the same `semantic_key` in a complete happy-path cycle test. Test: collect all emitted events, assert unique semantic keys.

12. `NoOpEventBus` implements the same interface as `CycleEventBus` without side effects. Test: subscribe and emit with `NoOpEventBus`; verify no errors.

13. `event_id` is globally unique (ULID or UUID4 with `evt_` prefix). Test: generate 1000 event IDs, assert all unique.

14. `EventSubscriber` is a protocol, not an ABC. Test: any class with an `on_event(CycleEvent) -> None` method satisfies the protocol without explicit inheritance.

15. Cycle-level events (`cycle.created`, `cycle.cancelled`) use `run_id=""` for sequence counter key. Test: emit `cycle.created` and `run.created` for the same cycle, verify independent sequence counters.

16. `event_bus.emit()` at `artifact.stored` includes `artifact_id`, `artifact_name`, `producing_task_type`, `size_bytes` in payload. Test: mock vault store, verify event payload.

17. `event_bus.emit()` at `artifact.promoted` includes `artifact_id`, `artifact_type`, `promoted_by` in payload. Test: mock vault promote, verify event payload.

18. `run.created` event includes `workload_type` in payload (may be `null`). Test: create a run with `workload_type="planning"`, verify event payload contains `workload_type`.

19. Drift detection test passes: every registry state transition in a test cycle has exactly one matching event. Test: run one or more cycle scenarios through `MemoryCycleRegistry`, collect emitted events, compare transitions to registry state. Drift detection validates **parity between the event stream and mutable registry state** for each scenario — it does not require all 20 event types in a single test cycle.

20. Existing tests pass without modification. Test: `run_new_arch_tests.sh` green with no test changes.

21. `CycleEventBus` constructor accepts `source_service` and `source_version` parameters. All emitted events carry these values. Test: create bus with `source_service="runtime-api"`, emit event, verify `source_service` on returned event.

------------------------------------------------------------------------

## 20. Key Design Decisions

1. **Event bus is in-process, not external** (resolved from Open Question 1). The v0 bus is synchronous and in-process. No Redis, NATS, or RabbitMQ dependency. This keeps the blast radius small, avoids infrastructure dependencies, and matches the existing telemetry contract (synchronous, non-blocking). Async dispatch is a v1+ concern — the `EventSubscriber` protocol and `CycleEvent` envelope are designed to survive a transport upgrade without interface changes.

2. **Single-parent hierarchy, not multi-level ancestry** (resolved from Open Question 2). `parent_type` and `parent_id` encode single-level parentage (run → cycle, task → run). Multi-level ancestry (task → run → cycle) is available via the `context` dict. This keeps the event model flat and avoids recursive parent resolution. If a subscriber needs the cycle_id for a task event, it reads `context["cycle_id"]`.

3. **`ulid-py` with UUID4 fallback** (resolved from Open Question 3). ULID provides time-ordering (useful for debugging) and is shorter than UUID4. Falls back to UUID4 if the library is unavailable. The `event_id` is a unique key, not a sort key — `sequence` provides ordering within a run.

4. **Event store is a v2 concern** (resolved from Open Question 4). v0 emits events to subscribers (bridge adapters). There is no persistent event store in v0. v2 introduces an event store as a Postgres table (separate from cycle registry). Events and registry data serve different purposes: events are immutable facts; registry data is mutable state.

5. **Pulse events are emitted by this SIP, not SIP-0070** (resolved from Open Question 5). SIP-0070 is already implemented with `_emit_pulse_event()` helper calls. The v0 event system adds `event_bus.emit()` alongside these calls (dual-emit). In v1, the `_emit_pulse_event()` calls are removed and the event bus becomes the sole emission path. The pulse event taxonomy (5 events) is defined here because it is part of the unified 20-event taxonomy.

6. **Subscribers are synchronous in v0**. Async subscribers add complexity (error handling, backpressure, ordering guarantees) without benefit when the bus is in-process. The `EventSubscriber` protocol uses `def on_event()`, not `async def`. If async dispatch is needed in v1+, a new `AsyncEventSubscriber` protocol can be added alongside the sync one.

7. **`EventType` is a constants class, not an enum**. Follows the established `ArtifactType`, `WorkloadType`, and `RunInitiator` pattern. Constants classes are extensible without code changes and avoid `ValueError` on unknown strings. Custom event types are permitted for extensibility.

8. **NoOp bus, not None**. The `NoOpEventBus` follows the always-inject NoOp pattern used by `NoOpLLMObservabilityAdapter`. Every emission point calls `self._event_bus.emit()` unconditionally — no `if self._event_bus:` guards. This eliminates null-check boilerplate and makes the emission points self-documenting.

9. **`semantic_key` is computed, not stored**. The key is derived from `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}` at emission time. It is not a constructor parameter. This prevents callers from computing it incorrectly and ensures consistency.

10. **Dual-emit in v0, not immediate replacement**. The event system runs alongside existing telemetry for an entire release cycle. This provides:
    - Zero-risk deployment (dashboards unchanged).
    - Parity validation (bridge output vs direct call output).
    - Rollback safety (remove event bus, existing calls still work).
    The cost is temporary duplicate signals, which is acceptable for one release.

11. **Bridge adapters are simple translators, not enrichers**. Bridges translate `CycleEvent` fields to sink-specific API calls. They do not query additional data, perform joins, or enrich events. If a sink needs data not in the event payload, the emission point must include it — not the bridge. This keeps bridges testable, stateless, and fast.

------------------------------------------------------------------------

## 21. Test Plan

| Test Suite | File | Tests | Purpose |
|------------|------|-------|---------|
| Event Models | `tests/unit/events/test_models.py` | ~15 | CycleEvent construction, immutability, field defaults, semantic key format |
| Event Types | `tests/unit/events/test_types.py` | ~5 | EventType constants exist, follow naming convention |
| Event Bus | `tests/unit/events/test_bus.py` | ~20 | Emit, subscribe, sequence monotonicity, failure isolation, NoOp bus |
| Bridge: LangFuse | `tests/unit/events/bridges/test_langfuse_bridge.py` | ~10 | Event-to-StructuredEvent translation, CorrelationContext mapping |
| Bridge: Prefect | `tests/unit/events/bridges/test_prefect_bridge.py` | ~10 | Event-to-Prefect-state mapping, task run creation |
| Bridge: Metrics | `tests/unit/events/bridges/test_metrics_bridge.py` | ~10 | Event-to-counter/histogram mapping |
| Emission Coverage | `tests/unit/events/test_event_emission.py` | ~40 | Each of 20 events emitted with correct type and required fields |
| No-Duplicate | `tests/unit/events/test_event_sequences.py` | ~10 | Full cycle: unique semantic keys, monotonic sequences |
| Bridge Parity | `tests/unit/events/test_bridge_parity.py` | ~15 | Bridge output matches direct wired call output |
| Drift Detection | `tests/unit/events/test_drift_detection.py` | ~5 | Registry state transitions match events 1:1 |
| **Total** | | **~140** | |

------------------------------------------------------------------------

## 22. Migration Phases (v1 and v2)

These phases are described for architectural context. They are separate work items, not part of this SIP's implementation scope.

### v1: Rewire Call Sites (1.0)

**Goal:** Remove direct wired calls one category at a time. Bridges become the sole path to LangFuse/Prefect.

| Step | Remove | Bridge Handles |
|------|--------|---------------|
| v1.0 | `record_event("cycle.*")` from executor | LangFuseBridge opens/closes traces from run events |
| v1.1 | Prefect `set_flow_run_state()` from executor | PrefectBridge translates run events |
| v1.2 | Prefect task run calls from executor | PrefectBridge translates task events |
| v1.3 | `record_event("task.*")` from agent shims | LangFuseBridge translates task events |
| v1.4 | `_emit_pulse_event()` from executor | LangFuseBridge translates pulse events |

**Success gate for v2:**
- All wired lifecycle calls removed (only trace/span/generation/flush remain)
- Zero drift alerts over >= 4 weeks
- Dashboard parity verified

### v2: Event-First (1.1+)

**Goal:** Events are the only source of lifecycle truth. `LLMObservabilityPort` narrowed to tracing-only concerns. Event store becomes queryable via API.

------------------------------------------------------------------------

## 23. Source Ideas

- `docs/plans/cycle-event-system-v0.md` — full design note with event taxonomy, envelope schema, migration phases, and event sequences.
