# Plan: SIP-0077 Cycle Event System Implementation

## Context

SIP-0077 introduces a canonical lifecycle event bus for SquadOps cycles. Today the same semantic fact ("run X started") is recorded independently in 3-4 places (LangFuse `record_event()`, Prefect state, structured log, OTEL span) with different schemas, timing, and no coordination. This creates drift, makes adding new lifecycle transitions expensive (3-4 code changes per event), and blocks the pipeline protocol SIPs that depend on reliable lifecycle facts.

The event system introduces an `CycleEventBusPort` with a 20-event taxonomy, an in-process adapter (`InProcessCycleEventBus`), three bridge subscribers (LangFuse, Prefect, Metrics), and dual-emit alongside existing telemetry (v0 scope). No existing code is removed. The event bus follows the same hexagonal port/adapter pattern as every other subsystem (`CycleRegistryPort`, `LLMObservabilityPort`, `QueuePort`, etc.).

**Branch:** `feature/sip-0077-cycle-event-system` (already created off main)
**SIP:** `sips/accepted/SIP-0077-Cycle-Event-System.md` (Rev 3)
**Target version:** 0.9.15

---

## Phase 1: Domain Models and Event Bus (Foundation)

### Commit 1a: EventType constants + CycleEvent model

**New files:**

| File | Contents |
|------|----------|
| `src/squadops/events/__init__.py` | Public exports: `CycleEvent`, `CycleEventBusPort`, `EventSubscriber`, `EventType` |
| `src/squadops/events/types.py` | `EventType` constants class (20 constants, `{entity}.{transition}` format) |
| `src/squadops/events/models.py` | `CycleEvent` frozen dataclass (13 fields: identity, timing, source, entity, context, payload, semantic_key) |

**Pattern references:**
- `EventType` follows `WorkloadType` / `ArtifactType` pattern (class with string constants, not enum): `src/squadops/cycles/models.py`
- `CycleEvent` follows frozen dataclass pattern: `src/squadops/cycles/models.py` (Cycle, Run, Gate)

**Tests:** `tests/unit/events/test_types.py` (~5), `tests/unit/events/test_models.py` (~15)
- EventType constants exist and follow `{entity}.{transition}` naming
- CycleEvent construction, immutability, field access, required fields

### Commit 1b: CycleEventBusPort, EventSubscriber protocol

**New files:**

| File | Contents |
|------|----------|
| `src/squadops/ports/events/__init__.py` | Exports: `CycleEventBusPort` |
| `src/squadops/ports/events/cycle_event_bus.py` | `CycleEventBusPort` ABC with `emit()` and `subscribe()` abstract methods |
| `src/squadops/events/subscriber.py` | `EventSubscriber` protocol: `on_event(event: CycleEvent) -> None` |

`CycleEventBusPort` follows the same pattern as `CycleRegistryPort`, `LLMObservabilityPort`, etc.:
- ABC in `src/squadops/ports/`
- `emit(event_type, *, entity_type, entity_id, parent_type, parent_id, context, payload) -> CycleEvent | None`
- `subscribe(subscriber: EventSubscriber) -> None`

**Port-level `emit()` contract:**
- `emit()` is best-effort, non-blocking publication. It is not part of the caller's transactional success criteria in v0. Callers must not treat emission failure as an application error.
- **Caller vs adapter responsibility:** callers provide semantic inputs (`event_type`, entity/context/payload). The adapter enriches transport/publication metadata (`event_id`, `occurred_at`, `sequence`, `semantic_key`, `source_service`, `source_version`). Application code must not construct envelope fields — that is adapter-internal.

**Port-level `subscribe()` semantics:** `subscribe()` is on the port ABC because the in-process adapter uses it for local bridge registration. However, subscriber registration is adapter-defined behavior — future external adapters (e.g., persistent event store, message broker) may implement subscription differently or treat it as an adapter-local concern. `subscribe()` is not a universal consumption contract.

`EventSubscriber` is a `Protocol` (structural typing, no inheritance required), placed in the domain layer alongside the event models. `EventSubscriber.on_event()` is synchronous in v0. Subscribers must be lightweight and non-blocking in practice — long-running I/O or expensive reconciliation inside a subscriber will stall the calling request/executor path.

### Commit 1c: InProcessCycleEventBus adapter + NoOpCycleEventBus adapter + factory

**New files:**

| File | Contents |
|------|----------|
| `adapters/events/__init__.py` | Package init |
| `adapters/events/in_process_cycle_event_bus.py` | `InProcessCycleEventBus(source_service, source_version)` — implements `CycleEventBusPort` |
| `adapters/events/noop_cycle_event_bus.py` | `NoOpCycleEventBus` — implements `CycleEventBusPort`, all methods are no-ops |
| `adapters/events/factory.py` | `create_cycle_event_bus(provider, **kwargs)` — config-driven selection |

`InProcessCycleEventBus` (was `CycleEventBus`):
  - `subscribe(subscriber)` — appends to `_subscribers` list
  - `emit(event_type, ...) -> CycleEvent` — constructs event, dispatches to subscribers
  - `_sequence: dict[tuple[str, str], int]` — per `(cycle_id, run_id)` monotonic counter
  - `_generate_event_id()` — ULID with `evt_` prefix, UUID4 fallback
  - Subscriber exceptions: logged and swallowed (never propagate)

**v0 adapter scope:** `InProcessCycleEventBus` is the v0 adapter for local publication and bridge fanout. It is not the long-term durable event continuity layer. A future persistent adapter (event store, message broker) will replace it for durable publication guarantees. The in-process adapter establishes the contract surface and proves the taxonomy; durability is a v2 concern.

`NoOpCycleEventBus`:
  - Implements `CycleEventBusPort`, all methods are no-ops
  - `emit()` returns `None`
  - Follows `NoOpLLMObservabilityAdapter` pattern: `adapters/telemetry/noop_llm_observability.py`
  - **Intent:** `NoOpCycleEventBus` is a valid degraded production adapter for best-effort publication when event infrastructure is absent. Running with NoOp means no canonical event publication guarantees are present — this is an acceptable operational mode, not a configuration mistake, but operators should be aware of it (see degraded-mode logging in Commit 3a).

`create_cycle_event_bus(provider, **kwargs)` selects the configured `CycleEventBusPort` adapter implementation:
  - `"in_process"` → `InProcessCycleEventBus(source_service=..., source_version=...)`
  - `"noop"` → `NoOpCycleEventBus()`
  - Follows `create_cycle_registry()` / `create_llm_observability_provider()` pattern

**`emit()` return-value contract:** `InProcessCycleEventBus.emit()` returns a `CycleEvent`; `NoOpCycleEventBus.emit()` returns `None`. The port declares return type `CycleEvent | None`. Callers MUST NOT depend on the return value of `emit()`. This is a hard contract — any code that uses the returned event will break under NoOp substitution.

**Optional dependency:** `ulid-py` added to `requirements/api.txt`. Falls back to UUID4 if not installed.

**Tests:** `tests/unit/events/test_bus.py` (~20)
- Emit returns CycleEvent with correct fields
- Subscriber receives event on emit
- Multiple subscribers called in registration order (this is an `InProcessCycleEventBus` guarantee, not a port-level contract — future adapters may not preserve ordering)
- Subscriber failure (raises RuntimeError) does not propagate
- Sequence monotonicity: 5 events for same run produce sequences 1-5
- Independent sequences: different run_ids have independent counters
- Cycle-level events use `run_id=""` for sequence key
- Semantic key format: `{cycle_id}:{entity_type}:{entity_id}:{transition}:{sequence}`
- Event ID uniqueness (1000 IDs, all unique)
- NoOpCycleEventBus: subscribe and emit without errors, emit returns None
- EventSubscriber is a Protocol (structural typing, no inheritance required)
- Both adapters satisfy `isinstance(bus, CycleEventBusPort)`

**v0 scope note:** `semantic_key` uniqueness is validated within process lifetime and test scenarios. Durable cross-restart uniqueness is deferred until a persistent event store and sequence source exist (v2). Tests assert uniqueness within a single bus instance, not across process restarts.

**pyproject.toml:** Register `domain_events` marker.

**Test conftest:** `tests/unit/events/__init__.py` and `tests/unit/events/conftest.py` with shared fixtures.

---

## Phase 2: Bridge Adapters

### Commit 2a: LangFuseBridge

**New files:**
| File | Contents |
|------|----------|
| `src/squadops/events/bridges/__init__.py` | Exports: `LangFuseBridge`, `PrefectBridge`, `MetricsBridge` |
| `src/squadops/events/bridges/langfuse.py` | `LangFuseBridge(llm_observability: LLMObservabilityPort)` |

Translates `CycleEvent` → `CorrelationContext` + `StructuredEvent` → `record_event()`.

**Existing code used:**
- `CorrelationContext.for_cycle()`: `src/squadops/telemetry/models.py:74`
- `StructuredEvent`: `src/squadops/telemetry/models.py:41`
- `LLMObservabilityPort.record_event()`: `src/squadops/ports/telemetry/llm_observability.py`

**Tests:** `tests/unit/events/bridges/test_langfuse_bridge.py` (~10)
- Event translates to correct StructuredEvent name and message
- CorrelationContext uses cycle_id and trace_id from event context
- Payload attributes are included in StructuredEvent attributes

### Commit 2b: PrefectBridge

**New file:** `src/squadops/events/bridges/prefect.py`

`PrefectBridge(prefect_reporter: PrefectReporter)`:
- `_RUN_STATE_MAP`: maps run events to Prefect states (RUNNING, COMPLETED, FAILED, CANCELLED, PAUSED)
- `_TASK_STATE_MAP`: maps task events to Prefect states
- `task.dispatched` → `create_task_run()` + `set_task_run_state(RUNNING)`
- Duplicate `task.dispatched` detection keyed by `(run_id, task_id)` — safe across cycles. Log warning, ignore duplicate

**Existing code used:**
- `PrefectReporter`: `adapters/cycles/prefect_reporter.py`
- State mapping pattern already exists in `DistributedFlowExecutor._execute_sequential()` (lines 571-594)

**Tests:** `tests/unit/events/bridges/test_prefect_bridge.py` (~10)
- `run.started` → `set_flow_run_state("RUNNING")`
- `task.dispatched` → `create_task_run()` + `set_task_run_state("RUNNING")`
- `task.succeeded` → `set_task_run_state("COMPLETED")`
- Events not in state maps → no calls
- Duplicate `task.dispatched` for same `(run_id, task_id)` → warning logged, no second `create_task_run()`

### Commit 2c: MetricsBridge

**New file:** `src/squadops/events/bridges/metrics.py`

`MetricsBridge(metrics_port: MetricsPort)`:
- `_COUNTER_MAP`: selective (5 events → 5 counters)
- `task.succeeded` with `duration_ms` → `observe("task_duration_ms", duration)`
- NOT a full lifecycle mirror of all 20 events

**Existing code used:**
- `MetricsPort`: `src/squadops/ports/telemetry/metrics.py` (methods: `increment()`, `observe()`)

**Tests:** `tests/unit/events/bridges/test_metrics_bridge.py` (~10)
- `run.completed` → `increment("runs_completed_total")`
- `task.succeeded` with duration_ms → `increment()` + `observe()`
- Events not in counter map → no calls

### Commit 2d: Bridge parity tests

**New file:** `tests/unit/events/test_bridge_parity.py` (~15)

Validates sink-equivalent semantics: for each lifecycle transition, bridge output produces the same transition meaning and entity correlation as the existing direct wired calls in the executor.

**Approach:** Capture mock call args from bridge path vs simulated direct path. Comparison basis per sink:
- **LangFuse:** event name + correlation identity (cycle_id, trace_id) + key payload attributes match current direct `record_event()` semantics
- **Prefect:** resulting state transition meaning on flow/task run matches (not raw payload equality)
- **Metrics:** counter/histogram effect matches (counter name + increment count, histogram metric name + observed value)

---

## Phase 3: Emission Points and Wiring

### Commit 3a: Executor `event_bus` parameter + DI wiring

**Modified files:**

| File | Change |
|------|--------|
| `adapters/cycles/distributed_flow_executor.py` | Add `event_bus: CycleEventBusPort` param to `__init__` (default `NoOpCycleEventBus()`). Store as `self._cycle_event_bus`. Import from port, not adapter. |
| `adapters/cycles/factory.py` | Accept and pass `event_bus` kwarg to `DistributedFlowExecutor` constructor |
| `src/squadops/api/runtime/deps.py` | Add `_cycle_event_bus: CycleEventBusPort` singleton, `set_cycle_event_bus()`, `get_cycle_event_bus()`. Bus is set once at startup; production code must not mutate it after startup. Test code may replace/reset it explicitly via `set_cycle_event_bus()`. |
| `src/squadops/api/runtime/main.py` | Create event bus via factory, register bridges, inject into executor, call `set_cycle_event_bus()` |

**Wiring in `main.py` startup** (after line 290, inside the cycle ports try block):

```python
from adapters.events.factory import create_cycle_event_bus
from src.squadops.events.bridges.langfuse import LangFuseBridge
from src.squadops.events.bridges.prefect import PrefectBridge

event_bus = create_cycle_event_bus(
    "in_process",
    source_service="runtime-api",
    source_version=SQUADOPS_VERSION,
)
if llm_obs:
    event_bus.subscribe(LangFuseBridge(llm_obs))
if _prefect_reporter:
    event_bus.subscribe(PrefectBridge(_prefect_reporter))
# MetricsBridge deferred: no MetricsPort wired in runtime-api yet

from squadops.api.runtime.deps import set_cycle_event_bus
set_cycle_event_bus(event_bus)
```

Pass `event_bus=event_bus` to `create_flow_executor()`.

**Type annotations:** The executor and deps module type-hint against `CycleEventBusPort` (the port), never against `InProcessCycleEventBus` (the adapter). This matches how the executor takes `CycleRegistryPort`, not `PostgresCycleRegistry`.

### Commit 3b: Executor emission points (run lifecycle: 6 events)

Add `event_bus.emit()` calls in `DistributedFlowExecutor.execute_run()`:

| Event | Location in executor | After existing code |
|-------|---------------------|---------------------|
| `run.started` | After `update_run_status(RUNNING)` (line 140) | After existing LangFuse `record_event("cycle.started")` |
| `run.completed` | After `update_run_status(COMPLETED)` (line 233) | Alongside existing terminal state |
| `run.failed` | In `except _ExecutionError` (line 243) | After `_safe_transition(FAILED)` |
| `run.cancelled` | In `except _CancellationError` (line 237) | After `_safe_transition(CANCELLED)` |
| `run.paused` | In `_handle_gate()` after `update_run_status(PAUSED)` (line 785) | New |
| `run.resumed` | In `_handle_gate()` after `update_run_status(RUNNING)` from PAUSED (line 797) | New |

Note: `run.created` is emitted from the API route (Commit 3d), not the executor, because `create_run()` is called by the route.

### Commit 3c: Executor emission points (task + pulse: 8 events)

**Task events (3):**
| Event | Location |
|-------|----------|
| `task.dispatched` | In `_execute_sequential()` before `_dispatch_task()` (line 586) |
| `task.succeeded` | After `result.status == "SUCCEEDED"` check (line 597) |
| `task.failed` | Before `raise _ExecutionError` on task failure (line 598) |

Also add in `_execute_fan_out()` for parallel dispatch path.

**Pulse events (5):**
| Event | Location |
|-------|----------|
| `pulse.boundary_reached` | In `_run_boundary_verification()` before running suites (line 854) |
| `pulse.suite_evaluated` | In `_run_boundary_verification()` per record, after persist (line 876) |
| `pulse.boundary_decided` | In `_run_boundary_verification()` after `determine_boundary_decision()` (line 898) |
| `pulse.repair_started` | In `_verify_with_repair()` before dispatching repair chain (line 993) |
| `pulse.repair_exhausted` | In `_verify_with_repair()` at max attempts (line 972) |

The executor needs `cycle_id`, `run_id`, and `project_id` in scope for context dict construction. These are already available in all emission locations.

### Commit 3d: API route emission points (6 events)

**Modified files:**

| File | Events |
|------|--------|
| `src/squadops/api/routes/cycles/cycles.py` | `cycle.created` (line 98, after `create_run()`), `cycle.cancelled` (line 162, after `cancel_cycle()`) |
| `src/squadops/api/routes/cycles/runs.py` | `run.created` (line 42, after `create_run()`), `gate.decided` (line 103, after `record_gate_decision()`) |
| `src/squadops/api/routes/cycles/artifacts.py` | `artifact.stored` (line 71, after `vault.store()`), `artifact.promoted` (line 114, after `vault.promote_artifact()`) |

Each route imports `get_cycle_event_bus` from deps. Event bus is obtained inside the try block (lazy import pattern matching existing code). If event bus is not configured, uses NoOpCycleEventBus.

```python
# Example: cycle.created emission in cycles.py
from squadops.api.runtime.deps import get_cycle_event_bus
from squadops.events.types import EventType

event_bus = get_cycle_event_bus()
event_bus.emit(
    EventType.CYCLE_CREATED,
    entity_type="cycle",
    entity_id=cycle.cycle_id,
    context={"cycle_id": cycle.cycle_id, "project_id": project_id},
    payload={
        "project_id": project_id,
        "created_by": cycle.created_by,
        "squad_profile_id": cycle.squad_profile_id,
        "prd_ref": cycle.prd_ref,
    },
)
```

**Route-level emission ownership (v0):** Route-level emission is acceptable in v0 when the route is the confirmed transition boundary — the route calls the registry/vault port, receives the confirmed result, and emits the event immediately after. The route is the first code that knows the transition succeeded. In v1+, emission authority may be pushed deeper into the registry port or a domain service, but this does not change the event taxonomy or subscriber contract.

**deps.py `get_cycle_event_bus()` returns `NoOpCycleEventBus` instead of raising RuntimeError** — this differs from other getters because event emission is best-effort, not required. Routes should never fail because the event bus is unconfigured. When `get_cycle_event_bus()` falls back to `NoOpCycleEventBus`, it emits a warning log once per process indicating canonical event publication is disabled/degraded. This preserves best-effort behavior without making degraded event mode invisible in production.

### Commit 3e: Emission coverage tests + sequence tests

**New files:**

| File | Tests |
|------|-------|
| `tests/unit/events/test_event_emission.py` | ~40 tests: each of 20 taxonomy events has at least one valid emission point with correct type, entity fields, and required payload fields |
| `tests/unit/events/test_event_sequences.py` | ~10 tests: scenario-specific lifecycle paths (happy path, failure, gate pause, pulse repair) produce expected event subsets with monotonic sequences and unique semantic keys |

**Test scope distinction:** `test_event_emission.py` proves that every taxonomy event is wired to at least one emission point. `test_event_sequences.py` proves that specific scenarios produce their expected event subsets — no single scenario is expected to cover all 20 events.

Emission tests mock the registry/vault/queue and inject a real `InProcessCycleEventBus` with a collecting subscriber. Verify each emission point fires the correct `EventType` with required payload fields from the taxonomy (SIP Section 7).

---

## Phase 4: Drift Detection and Acceptance

### Commit 4a: Drift detection tests

**New file:** `tests/unit/events/test_drift_detection.py` (~5)

For each test scenario (happy path, task failure, gate pause), compare registry state transitions against emitted canonical events. Assertion target: for each canonical lifecycle transition (registry status change), exactly one canonical event should match. Supplemental telemetry/log emissions from dual-emit are ignored for drift purposes — drift detection validates the canonical bus only, not the full dual-emit output.

Uses `MemoryCycleRegistry` with a collecting `EventSubscriber`.

### Commit 4b: Version bump + final cleanup

- Bump version to `0.9.15` in `pyproject.toml`
- `pip install -e .` to refresh
- Update `requirements/api.txt` with `ulid-py` (optional)
- Regenerate lock files: `./scripts/maintainer/update_deps.sh`
- Promote SIP-0077 to implemented: `python scripts/maintainer/update_sip_status.py sips/accepted/SIP-0077-Cycle-Event-System.md implemented`
- Update `docs/ROADMAP.md` with v0.9.15 entry

---

## File Summary

### New files (19)

| File | Purpose |
|------|---------|
| `src/squadops/ports/events/__init__.py` | Port package exports |
| `src/squadops/ports/events/cycle_event_bus.py` | `CycleEventBusPort` ABC (`emit()`, `subscribe()`) |
| `src/squadops/events/__init__.py` | Domain model public API |
| `src/squadops/events/types.py` | EventType constants (20) |
| `src/squadops/events/models.py` | CycleEvent frozen dataclass |
| `src/squadops/events/subscriber.py` | `EventSubscriber` protocol |
| `src/squadops/events/bridges/__init__.py` | Bridge exports |
| `src/squadops/events/bridges/langfuse.py` | LangFuseBridge |
| `src/squadops/events/bridges/prefect.py` | PrefectBridge |
| `src/squadops/events/bridges/metrics.py` | MetricsBridge |
| `adapters/events/__init__.py` | Adapter package |
| `adapters/events/in_process_cycle_event_bus.py` | `InProcessCycleEventBus` — v0 in-process adapter |
| `adapters/events/noop_cycle_event_bus.py` | `NoOpCycleEventBus` — no-op adapter |
| `adapters/events/factory.py` | `create_cycle_event_bus()` factory |
| `tests/unit/events/__init__.py` | Test package |
| `tests/unit/events/conftest.py` | Shared event test fixtures |
| `tests/unit/events/bridges/__init__.py` | Bridge test package |
| `tests/unit/events/bridges/test_langfuse_bridge.py` | LangFuse bridge tests |
| `tests/unit/events/bridges/test_prefect_bridge.py` | Prefect bridge tests |
| `tests/unit/events/bridges/test_metrics_bridge.py` | Metrics bridge tests |

### New test files (7 more)

| File | Tests |
|------|-------|
| `tests/unit/events/test_types.py` | ~5 |
| `tests/unit/events/test_models.py` | ~15 |
| `tests/unit/events/test_bus.py` | ~20 |
| `tests/unit/events/test_bridge_parity.py` | ~15 |
| `tests/unit/events/test_event_emission.py` | ~40 |
| `tests/unit/events/test_event_sequences.py` | ~10 |
| `tests/unit/events/test_drift_detection.py` | ~5 |

### Modified files (9)

| File | Change |
|------|--------|
| `adapters/cycles/distributed_flow_executor.py` | `event_bus` constructor param + 15 emit() calls |
| `adapters/cycles/factory.py` | Pass `event_bus` kwarg |
| `src/squadops/api/runtime/deps.py` | `_cycle_event_bus`, `set_cycle_event_bus()`, `get_cycle_event_bus()` |
| `src/squadops/api/runtime/main.py` | Create bus, register bridges, inject |
| `src/squadops/api/routes/cycles/cycles.py` | 2 emit() calls |
| `src/squadops/api/routes/cycles/runs.py` | 2 emit() calls |
| `src/squadops/api/routes/cycles/artifacts.py` | 2 emit() calls |
| `pyproject.toml` | `domain_events` marker, version bump, `ulid-py` dep |
| `requirements/api.txt` | `ulid-py` |

**Estimated new tests:** ~140
**Estimated total after:** ~2,625

---

## Verification

**Test scope separation:** Tests are grouped by what they prove:
- **Port contract tests** — `CycleEventBusPort` implementations accept expected calls, `emit()` returns correct type or `None`, `subscribe()` does not raise. These are universal and must pass for any adapter.
- **In-process adapter tests** — subscriber registration-order delivery, sequence counter monotonicity, semantic key construction, ULID generation, subscriber exception swallowing. These are `InProcessCycleEventBus`-specific and would not apply to an external adapter.

This separation makes future adapter additions easier — port contract tests are reusable, adapter-specific tests are scoped.

1. `./scripts/dev/run_new_arch_tests.sh -v` — all existing 2,485+ tests pass (no behavioral changes)
2. `pytest tests/unit/events/ -v` — all ~140 new event tests pass
3. `pytest tests/unit/events/ -v -m domain_events` — marker works
4. Manual: `docker-compose build runtime-api` succeeds with `ulid-py` installed
5. Manual: start services, create a cycle, verify event bus logs show emission (check runtime-api logs for "Event subscriber" log entries if any bridge fails)
6. Manual: trigger a task failure or gate pause and verify the expected event subset is emitted and bridge failures (if simulated) do not fail the run
7. **MetricsBridge:** unit tests pass (`tests/unit/events/bridges/test_metrics_bridge.py`). Runtime-api wiring for MetricsBridge is intentionally deferred until `MetricsPort` is available in the runtime-api process — MetricsBridge is implemented and tested but not active in production in v0.

## Gotchas

- **`get_cycle_event_bus()` returns `NoOpCycleEventBus` not `RuntimeError`** — unlike other port getters. Event emission is best-effort; routes must never fail because the bus is unconfigured. Fallback logs a warning once per process so degraded mode is visible.
- **Dual-emit means temporary duplicate signals** — LangFuse will see both the existing `record_event()` calls AND the bridge-forwarded events. This is intentional and acceptable for one release. v1 removes the direct calls.
- **Pulse events: 5 taxonomy events vs ~8 existing `_emit_pulse_event()` call sites** — The SIP taxonomy has 5 pulse events. The existing `_emit_pulse_event()` has ~8 distinct event names (suite_started, suite_passed, suite_failed, boundary_decision, repair_started, binding_skipped, etc.). The new events map to the 5 taxonomy events; the others (suite_started, binding_skipped) remain as structured logs only.
- **Fan-out path** — `_execute_fan_out()` also dispatches tasks and records Prefect state. It needs task.dispatched/succeeded/failed emissions too, same as sequential.
- **`NoOpCycleEventBus.emit()` returns `None`** — callers MUST NOT depend on the return value (see `emit()` return-value contract in Phase 1b).
- **Test isolation** — event tests should not import runtime-api deps. Use `InProcessCycleEventBus` directly with mock subscribers.
- **Port, not concrete class** — all type annotations in the executor, deps, and routes reference `CycleEventBusPort`, never `InProcessCycleEventBus`. This matches how `CycleRegistryPort` is used instead of `PostgresCycleRegistry`.
