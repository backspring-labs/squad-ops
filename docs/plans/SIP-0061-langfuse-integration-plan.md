# SIP-0061 Implementation Plan: LangFuse Integration Foundation

**Last Updated**: 2026-02-06 (rev 8)
**Status**: Planning (pre-implementation)
**SIP Reference**: `sips/accepted/SIP-0061-LangFuse-Integration-Foundation.md` (v5)

---

## Pre-Implementation Verification (Repo Reality Check)

All target paths verified against repo as of 2026-02-06:

| Path | Exists | Action |
|------|--------|--------|
| `src/squadops/ports/telemetry/` | Yes | Add `llm_observability.py`, update `__init__.py` |
| `src/squadops/ports/telemetry/__init__.py` | Yes | Currently exports `EventPort`, `MetricsPort` — add `LLMObservabilityPort` |
| `src/squadops/telemetry/models.py` | Yes | Currently has `MetricType`, `Span`, `StructuredEvent` — extend with 4 new models |
| `adapters/telemetry/factory.py` | Yes | Currently has `create_metrics_provider`, `create_event_provider`, `create_telemetry_provider` — add `create_llm_observability_provider` |
| `adapters/telemetry/__init__.py` | Yes | Currently exports 3 adapters + 3 factories — add new exports |
| `adapters/telemetry/null.py` | Yes | Implements `MetricsPort` + `EventPort` — NOT touched; new no-op goes in separate file |
| `adapters/telemetry/langfuse/` | No | Create new directory |
| `src/squadops/config/schema.py` | Yes | `AppConfig` at line 301; `TelemetryConfig` at line 232; `ObservabilityConfig` at line 258 — add `LangFuseConfig` between telemetry and observability sections. **`AppConfig.langfuse` is a sibling to `telemetry`/`observability`, NOT nested inside `TelemetryConfig`.** |
| `src/squadops/execution/agent.py` | Yes | `BaseAgent.__init__` at line 43; keyword-only args; last optional param is `prompt_service` — add `llm_observability` after it |
| `src/squadops/llm/models.py` | Yes | `LLMResponse` at line 25 with `text`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens` — bridge target for helper |
| `tests/unit/telemetry/` | Yes | Has `test_models.py`, `test_ports.py`, `test_adapters.py`, `test_factory.py` — extend all |
| `tests/integration/conftest.py` | Yes | Has container fixtures + health checks — extend with langfuse skip logic |
| `tests/integration/telemetry/` | No | Create new directory |
| `pyproject.toml` | Yes | Markers at line 82 — add `langfuse` marker |
| `.env.example` | Yes | Telemetry section at line 59 — add LangFuse section after it |

---

## Scope Fence (Non-Negotiable)

The following are **explicitly out of scope for 0.9.0** and MUST NOT be introduced during implementation:

- **No evaluation/scoring**: LangFuse Scores, Datasets, or provider-agnostic evaluation features.
- **No EventPort/MetricsPort refactoring**: These ports remain unchanged. `LLMObservabilityPort` is additive.
- **No LangFuse SDK imports outside adapter**: `import langfuse` MUST only appear in `adapters/telemetry/langfuse/` and MUST be lazy (inside `__init__`, not at module top level). Zero LangFuse imports in `src/squadops/` or agent code. Adapter unit tests (`tests/unit/telemetry/test_langfuse_adapter.py`) import the adapter module (which is fine — the module loads without the SDK; only construction triggers the lazy import).
- **No ObservableLLMPort wrapper**: Deferred to future SIP (see SIP-0061 Section 6.8).
- **No prompt template management in LangFuse**: PromptLayerMetadata is metadata-only; prompt content management stays in `PromptService`.

If any work item starts drifting into these areas, stop and split into a separate SIP/PR.

---

## Summary

Implement the LangFuse LLM-observability foundation for SquadOps: a new `LLMObservabilityPort`, frozen domain models for correlation context, a LangFuse adapter with buffered non-blocking emission, and full test coverage — all wired through the existing hexagonal architecture.

**Scope:**
- **1 new port** (`LLMObservabilityPort`)
- **4 new domain models** (`CorrelationContext`, `PromptLayer`, `PromptLayerMetadata`, `GenerationRecord`)
- **2 new adapters** (LangFuseAdapter, NoOpLLMObservabilityAdapter)
- **1 factory extension** (`create_llm_observability_provider`)
- **1 config model** (`LangFuseConfig` added to `AppConfig`)
- **1 DI wiring change** (`BaseAgent` constructor)
- **1 helper** (`build_generation_record`)
- **Orchestrator + agent instrumentation** (lifecycle hooks, generation recording)
- **Full test suite** (unit, contract, integration, resilience)
- **Dev tooling** (`docker-compose.langfuse.yml`, env var updates)

---

## Implementation Strategy

### Phase Overview

| Phase | Scope | Estimate | Rationale |
|-------|-------|----------|-----------|
| Phase A | Core Plumbing | ~400 LOC | Port, models, no-op adapter, factory, config, DI wiring — everything depends on these |
| Phase B | LangFuse Adapter | ~500 LOC | Concrete implementation with buffer, flush, redaction, helper |
| Phase C | Instrumentation | ~300 LOC | Wire lifecycle hooks into orchestrator, agents, queue plumbing |
| Phase D | Tests & Documentation | ~600 LOC | Unit, contract, integration, resilience tests + env/compose updates |

### Milestones

- After Phase A: Port contract exists, no-op adapter wired, all existing tests still green
- After Phase B: LangFuseAdapter functional, `build_generation_record` helper ready
- After Phase C: One end-to-end cycle produces a LangFuse trace with spans and generations
- After Phase D: Full test coverage, CI gating in place, dev tooling ready

### Phase Exit Criteria

| Phase | Exit Criteria |
|-------|---------------|
| Phase A | `LLMObservabilityPort` instantiable via no-op; `BaseAgent` auto-injects NoOp when caller passes `None`; `self.llm_observability` is never `None` at runtime; `LangFuseConfig` loads from env vars; all existing unit tests pass; `@pytest.mark.langfuse` registered |
| Phase B | `LangFuseAdapter` passes port contract; buffer overflow drops oldest + increments counter; `close()` completes within time budget; redaction strips secrets; `build_generation_record` produces valid `GenerationRecord` with UUID4 `generation_id` |
| Phase C | Orchestrator calls `start_cycle_trace` → `end_cycle_trace` → `flush()` → `close()`; at least one agent records a generation with prompt layers; `message.sent`/`message.received` events emitted |
| Phase D | All unit tests pass; contract tests pass against local LangFuse; resilience tests verify graceful degradation; CI skips langfuse tests when env vars absent |

---

## Phase A: Core Plumbing

### A.0 Contract Verification Checklist

Before writing any code, verify the plan matches the SIP canonical surface **exactly**. Check each item:

**LLMObservabilityPort methods** (SIP Section 6.1 — single source of truth):

- [ ] `start_cycle_trace(self, ctx: CorrelationContext) -> None`
- [ ] `end_cycle_trace(self, ctx: CorrelationContext) -> None`
- [ ] `start_pulse_span(self, ctx: CorrelationContext) -> None`
- [ ] `end_pulse_span(self, ctx: CorrelationContext) -> None`
- [ ] `start_task_span(self, ctx: CorrelationContext) -> None`
- [ ] `end_task_span(self, ctx: CorrelationContext) -> None`
- [ ] `record_generation(self, ctx: CorrelationContext, record: GenerationRecord, prompt_layers: PromptLayerMetadata) -> None`
- [ ] `record_event(self, ctx: CorrelationContext, event: StructuredEvent) -> None` — **StructuredEvent only, no dict**
- [ ] `flush(self) -> None`
- [ ] `close(self) -> None`
- [ ] `async health(self) -> dict` — returns `{"status": "ok"|"degraded"|"down", "backend": str, "details": dict}`

**CorrelationContext scope rules** (SIP Section 6.2):

- [ ] `cycle_id: str` — only required field
- [ ] All other fields: `str | None` — nullability checked at port boundary, not dataclass
- [ ] `for_cycle(cycle_id, agent_id=None)` — sets only cycle_id
- [ ] `for_pulse(cycle_id, pulse_id, agent_id=None)` — sets cycle + pulse
- [ ] `from_envelope(envelope, agent_id, agent_role=None)` — populates all lineage from TaskEnvelope
- [ ] No placeholder fabrication: if a field is unknown, it MUST be `None`

**`record_event` type rule** (SIP Section 6.1):

- [ ] `record_event` takes `StructuredEvent` exclusively — no `dict`, no `**kwargs` overload
- [ ] Grep check: no call site passes a raw `dict` to `record_event` (search: `record_event.*\{` in instrumented files)

**GenerationRecord.generation_id rule** (SIP Section 6.7 — non-negotiable):

- [ ] `generation_id: str` — required, not `str | None`
- [ ] Created by `build_generation_record()` via `uuid.uuid4()`
- [ ] Adapter MUST NOT generate or backfill `generation_id`

### A.1 Domain Models

**File**: `src/squadops/telemetry/models.py` (extend existing)

Add four frozen dataclasses after the existing `StructuredEvent`:

```python
@dataclass(frozen=True)
class CorrelationContext:
    cycle_id: str
    pulse_id: str | None = None
    task_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    agent_id: str | None = None
    agent_role: str | None = None
    message_id: str | None = None

    @classmethod
    def for_cycle(cls, cycle_id: str, agent_id: str | None = None): ...

    @classmethod
    def for_pulse(cls, cycle_id: str, pulse_id: str, agent_id: str | None = None): ...

    @classmethod
    def from_envelope(cls, envelope, agent_id: str, agent_role: str | None = None): ...

@dataclass(frozen=True)
class PromptLayer:
    layer_type: str
    layer_id: str
    layer_version: str | None = None
    layer_hash: str | None = None

@dataclass(frozen=True)
class PromptLayerMetadata:
    prompt_layer_set_id: str
    layers: tuple[PromptLayer, ...]

@dataclass(frozen=True)
class GenerationRecord:
    generation_id: str  # UUID4, REQUIRED, caller-supplied
    model: str
    prompt_text: str
    response_text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
```

**Key rules**:
- All fields except `cycle_id` on `CorrelationContext` are `str | None` — nullability checked at port method boundary, not dataclass boundary.
- `GenerationRecord.generation_id` is `str` (required), not `str | None`. Created at record time by `build_generation_record()` via `uuid.uuid4()`. Adapter MUST NOT backfill.
- Use `tuple` for collections, not `list`.

**Verification**: Frozen immutability test (`pytest.raises(AttributeError)`), factory method tests for all three constructors, nullable field coverage.

### A.2 LLMObservabilityPort

**File**: `src/squadops/ports/telemetry/llm_observability.py` (new)

```python
from abc import ABC, abstractmethod
from squadops.telemetry.models import (
    CorrelationContext, GenerationRecord, PromptLayerMetadata, StructuredEvent,
)

class LLMObservabilityPort(ABC):
    """Port for LLM-specific observability. All methods non-blocking."""

    @abstractmethod
    def start_cycle_trace(self, ctx: CorrelationContext) -> None: ...
    @abstractmethod
    def end_cycle_trace(self, ctx: CorrelationContext) -> None: ...
    @abstractmethod
    def start_pulse_span(self, ctx: CorrelationContext) -> None: ...
    @abstractmethod
    def end_pulse_span(self, ctx: CorrelationContext) -> None: ...
    @abstractmethod
    def start_task_span(self, ctx: CorrelationContext) -> None: ...
    @abstractmethod
    def end_task_span(self, ctx: CorrelationContext) -> None: ...
    @abstractmethod
    def record_generation(self, ctx: CorrelationContext, record: GenerationRecord, prompt_layers: PromptLayerMetadata) -> None: ...
    @abstractmethod
    def record_event(self, ctx: CorrelationContext, event: StructuredEvent) -> None: ...
    @abstractmethod
    def flush(self) -> None: ...
    @abstractmethod
    def close(self) -> None: ...
    @abstractmethod
    async def health(self) -> dict: ...
```

**Also update**: `src/squadops/ports/telemetry/__init__.py` to export `LLMObservabilityPort`.

**Preconditions** (enforced by docstrings, validated in tests):
- `start_cycle_trace`: `ctx.cycle_id` MUST NOT be None
- `start_pulse_span`: `ctx.pulse_id` MUST NOT be None
- `start_task_span` / `record_generation`: `ctx.task_id` MUST NOT be None
- `record_event` takes `StructuredEvent` exclusively — no dict overload

### A.3 No-Op Adapter

**File**: `adapters/telemetry/noop_llm_observability.py` (new)

Separate from existing `null.py` (which implements `MetricsPort` + `EventPort`).

```python
class NoOpLLMObservabilityAdapter(LLMObservabilityPort):
    """No-op LLM observability adapter. All methods are silent no-ops.

    Accepts optional status/reason overrides so the factory can signal
    degraded health when the SDK is missing but config.enabled is True.
    """

    def __init__(
        self,
        *,
        health_status: str = "ok",
        health_reason: str | None = None,
    ) -> None:
        self._health_status = health_status   # "ok" (default) or "degraded"
        self._health_reason = health_reason   # e.g. "langfuse SDK not installed"

    # All lifecycle/record methods: pass

    async def health(self) -> dict:
        details = {}
        if self._health_reason:
            details["reason"] = self._health_reason
        return {"status": self._health_status, "backend": "noop", "details": details}
```

**Health status semantics**:
- Default construction (`NoOpLLMObservabilityAdapter()`) → `health()` returns `{"status": "ok", ...}`. This is the normal disabled-by-choice path.
- Factory SDK-missing fallback → `NoOpLLMObservabilityAdapter(health_status="degraded", health_reason="langfuse SDK not installed")`. Health reports `"degraded"` so monitoring can distinguish "intentionally off" from "wanted on but broken."

**Why separate file**: Existing `NullAdapter` implements `MetricsPort` + `EventPort`. Adding a third port to it would conflate concerns. The no-op LLM observability adapter has its own file for clarity and independent testability.

### A.4 Factory Extension

**File**: `adapters/telemetry/factory.py` (extend existing)

Add new function alongside existing `create_metrics_provider` / `create_event_provider` / `create_telemetry_provider`:

```python
def create_llm_observability_provider(
    provider: str = "langfuse",
    config: LangFuseConfig | None = None,
    secret_manager: SecretManager | None = None,
) -> LLMObservabilityPort:
    """Create LLM observability provider.

    Returns NoOpLLMObservabilityAdapter when config is None or config.enabled is False.
    """
```

Follow existing pattern: config-driven provider selection (enabled flag, provider string).

**Also update**: `adapters/telemetry/__init__.py` to export `create_llm_observability_provider`.

### A.5 LangFuseConfig

**File**: `src/squadops/config/schema.py` (extend existing)

Add `LangFuseConfig` as a Pydantic model, then add it to `AppConfig`:

```python
class LangFuseConfig(BaseModel):
    enabled: bool = False
    host: str = "http://localhost:3000"
    public_key: str = ""
    secret_key: str = ""
    redaction_mode: str = "standard"   # prod recommended: "strict"
    sample_rate_percent: int = 100
    flush_interval_seconds: int = 5
    buffer_max_size: int = 1000
    shutdown_flush_timeout_seconds: int = 5

class AppConfig(BaseModel):
    # ... existing fields ...
    langfuse: LangFuseConfig = LangFuseConfig()  # NEW — sibling to telemetry, not nested
```

**Placement**: After existing `TelemetryConfig`, before `ObservabilityConfig`. `LangFuseConfig` is a sibling to `TelemetryConfig`, not nested within it (different backend, different purpose).

**Env var convention**: `SQUADOPS__LANGFUSE__ENABLED=true`, `SQUADOPS__LANGFUSE__PUBLIC_KEY=secret://LANGFUSE_PUBLIC_KEY`, etc.

### A.6 BaseAgent DI Wiring

**File**: `src/squadops/execution/agent.py` (modify existing)

Add `llm_observability` parameter to constructor (default `None`). The constructor **always** converts `None` to `NoOpLLMObservabilityAdapter`, so `self.llm_observability` is never `None` at runtime:

```python
from squadops.ports.telemetry.llm_observability import LLMObservabilityPort

class BaseAgent:
    def __init__(
        self,
        *,
        secret_manager: SecretManager,
        db_runtime: DbRuntime,
        heartbeat_reporter: AgentHeartbeatReporter,
        agent_id: str,
        prompt_service: PromptService | None = None,
        llm_observability: LLMObservabilityPort | None = None,  # NEW
    ) -> None:
        # ... existing assignments ...
        if llm_observability is None:
            from adapters.telemetry.noop_llm_observability import NoOpLLMObservabilityAdapter
            llm_observability = NoOpLLMObservabilityAdapter()
        self.llm_observability = llm_observability  # Always LLMObservabilityPort, never None
```

**Always-available port**: `self.llm_observability` is always a valid `LLMObservabilityPort` instance (real adapter or no-op). Agent code calls methods directly — **no `if self.llm_observability:` guards needed**. This eliminates branching at every call site and ensures telemetry hooks are always structurally present.

**Import**: The NoOp import is lazy (inside `__init__`) to avoid a hard dependency from the core domain on the adapters package at module load time.

### A.7 Pytest Marker

**File**: `pyproject.toml` (modify existing)

Add to `[tool.pytest.ini_options]` markers list:

```toml
"langfuse: Tests that require a running LangFuse instance",
```

### A.8 Phase A Verification

Run after all A.* steps:

```bash
# All existing tests must still pass
pytest tests/unit -v

# New model tests
pytest tests/unit/telemetry/test_models.py -v -k "CorrelationContext or PromptLayer or GenerationRecord"

# New port tests
pytest tests/unit/telemetry/test_ports.py -v -k "LLMObservability"

# New adapter tests
pytest tests/unit/telemetry/test_adapters.py -v -k "NoOpLLMObservability"

# Config loading test
pytest tests/unit/config/ -v -k "langfuse"
```

---

## Phase B: LangFuse Adapter

### B.0 Adapter Implementation Constraints Checklist

Before writing the adapter, verify these constraints are met (SIP Sections 6.1, 6.6, 9, 11):

- [ ] **Buffer type**: `queue.Queue` (sync, stdlib). NOT `asyncio.Queue`, NOT `collections.deque`.
- [ ] **Non-blocking port methods**: Every `record_*`, `start_*`, `end_*` method enqueues and returns. No network I/O on the caller's thread. < 5ms p95.
- [ ] **Buffered + retry/backoff**: Failed flushes retried with exponential backoff (`RETRY_BASE_DELAY_SECONDS` → `RETRY_MAX_DELAY_SECONDS`).
- [ ] **Overflow policy**: Drop oldest, increment counter, rate-limited warning. Never block the caller waiting for buffer space.
- [ ] **`close()` bounded flush**: MUST complete within `shutdown_flush_timeout_seconds` even when LangFuse is unreachable. Unflushed entries discarded with warning.
- [ ] **`flush()` is non-blocking**: Signals background thread to drain. Returns immediately.
- [ ] **Thread-safe span state**: `_span_state` dict protected by `threading.Lock()`. No unprotected reads or writes.
- [ ] **Single background worker thread**: One daemon thread handles all flushing. No thread pool, no executor.
- [ ] **SDK isolation**: `import langfuse` only in `adapters/telemetry/langfuse/`. Zero imports elsewhere.

### B.1 LangFuseAdapter

**Directory**: `adapters/telemetry/langfuse/` (new)

```
adapters/telemetry/langfuse/
├── __init__.py          # Exports LangFuseAdapter
├── adapter.py           # LangFuseAdapter implementation
└── redaction.py         # Redaction strategy classes
```

**File**: `adapters/telemetry/langfuse/adapter.py`

```python
class LangFuseAdapter(LLMObservabilityPort):
    """LangFuse implementation. Non-blocking: enqueue to internal buffer."""

    def __init__(self, config: LangFuseConfig) -> None:
        self._config = config
        self._buffer = queue.Queue(maxsize=config.buffer_max_size)
        self._dropped_events = 0
        self._span_state: dict[str, Any] = {}  # Keyed by cycle_id/pulse_id/task_id
        self._lock = threading.Lock()  # Protects _span_state
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._shutdown = threading.Event()
        # ... LangFuse SDK client init ...
```

**Key implementation details**:

| Concern | Implementation |
|---------|---------------|
| Buffer | `queue.Queue` (sync, thread-safe). NOT `asyncio.Queue`. |
| Overflow | When full, drop oldest via `queue.get_nowait()`, increment `_dropped_events`, rate-limited warning |
| Background flush | Daemon thread, wakes every `flush_interval_seconds` |
| Span state | `dict` protected by `threading.Lock()`. Keys include `task_id` for concurrent task support |
| Retry | Exponential backoff on failed flushes |
| Redaction | Applied before buffering via `redaction.py` |
| Sampling | `sample_rate_percent`: 0 = skip all, 100 = capture all. Decision per-generation at `record_generation()` time via random draw. Sampled-out generations are silently dropped (no buffer entry, no warning). |

**Sampling rule**: Sampling applies ONLY to `record_generation()`. All `start_*`/`end_*` spans and `record_event()` calls always emit regardless of `sample_rate_percent`. Spans and events are lightweight metadata that must remain complete for trace integrity.
| `flush()` | Signals background thread to drain. Non-blocking (best-effort) |
| `close()` | Sets `_shutdown` event, joins thread with `shutdown_flush_timeout_seconds` timeout, discards unflushed with warning |
| `health()` | Returns `{"status": "ok"\|"degraded"\|"down", "backend": "langfuse", "details": {"buffer_size": int, "dropped_events": int, ...}}` |

**Named constants** (define at module level, not magic numbers):

```python
# adapters/telemetry/langfuse/adapter.py
DEFAULT_FLUSH_INTERVAL_SECONDS = 5
DEFAULT_BUFFER_MAX_SIZE = 1000
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 5
OVERFLOW_WARNING_INTERVAL_SECONDS = 30  # Rate-limit overflow warnings
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_DELAY_SECONDS = 60.0
RETRY_BACKOFF_FACTOR = 2.0
```

**Thread-safety invariants** (enforced, not just documented):

- `_buffer`: `queue.Queue` — thread-safe by design; no external lock needed
- `_span_state`: `dict` — protected by `self._lock` (`threading.Lock()`). ALL reads and writes go through `with self._lock:`
- `_dropped_events`: `int` — protected by `self._lock` (same lock as `_span_state`)
- `_shutdown`: `threading.Event` — thread-safe by design
- No mutable shared state exists outside these four structures

**Timing budget compliance** (SIP Section 11):
- Enqueue path (`record_*`, `start_*`, `end_*`): < 5ms p95 — enqueue + return, no I/O
- `flush()`: Non-blocking signal to background thread
- `close()`: Bounded by `shutdown_flush_timeout_seconds` (default 5s)

**Required unit tests for reliability** (Phase D, but design for them now):

| Test | Asserts |
|------|---------|
| `test_buffer_overflow_drops_oldest` | Fill buffer to max, add one more → oldest dropped, `_dropped_events == 1` |
| `test_overflow_warning_rate_limited` | Multiple overflows → warning emitted at most once per `OVERFLOW_WARNING_INTERVAL_SECONDS` |
| `test_close_completes_within_timeout` | `close()` returns within `shutdown_flush_timeout_seconds + 1s` margin, even when LangFuse unreachable |
| `test_close_discards_unflushed_with_warning` | After timeout, remaining buffer entries discarded + warning logged |
| `test_flush_is_nonblocking` | `flush()` returns immediately (< 50ms) regardless of buffer size |
| `test_concurrent_task_spans` | Two tasks recording spans concurrently → both produce correct, non-interleaved data |
| `test_span_state_lock_protects_dict` | Concurrent `start_task_span` / `end_task_span` → no `KeyError` or corruption |
| `test_adapter_does_not_generate_generation_id` | Adapter receives `GenerationRecord` with `generation_id` already set; adapter never calls `uuid.uuid4()` or modifies `generation_id` |
| `test_generation_record_requires_generation_id` | Constructing `GenerationRecord` without `generation_id` raises `TypeError` (frozen dataclass required field) |
| `test_record_generation_requires_prompt_layers` | Calling `record_generation()` with `prompt_layers=None` raises `TypeError` (not `PromptLayerMetadata | None`) |
| `test_health_includes_dropped_events_counter` | After N overflows, `health().details["dropped_events"]` equals N |
| `test_health_includes_buffer_size` | `health().details["buffer_size"]` reflects current `_buffer.qsize()` |

**Generation identifier mapping** (SIP Section 5.2):
- **LangFuse Generation ID** = `GenerationRecord.generation_id` (UUID4, created by caller via `build_generation_record`)
- **`CorrelationContext.trace_id`** and **`CorrelationContext.span_id`** are **correlation fields only** — they link the generation to the Cycle/Pulse/Task hierarchy but are NOT generation identifiers
- The adapter MUST use `generation_id` as the LangFuse Generation's external ID, and `trace_id`/`span_id` for parent association

**LangFuse SDK isolation**: Only this adapter imports `langfuse`. No agent code imports it directly.

### B.2 Redaction Strategies

**File**: `adapters/telemetry/langfuse/redaction.py`

```python
class RedactionStrategy(ABC):
    @abstractmethod
    def redact(self, text: str) -> str: ...

class StandardRedaction(RedactionStrategy):
    """Strips known secret patterns (API keys, tokens, passwords)."""

class StrictRedaction(RedactionStrategy):
    """Strips secrets + PII patterns. Hashes identifiers for correlation."""

def get_redaction_strategy(mode: str) -> RedactionStrategy:
    """Factory for redaction mode selection."""
```

**Applied at**: Buffer ingestion time (before enqueue), not at flush time. This ensures sensitive data never enters the buffer.

### B.3 build_generation_record Helper

**File**: `src/squadops/execution/observability.py` (new)

```python
import uuid
from squadops.llm.models import LLMResponse
from squadops.telemetry.models import GenerationRecord

def build_generation_record(
    llm_response: LLMResponse,
    model: str,
    prompt_text: str,
    latency_ms: float | None = None,
) -> GenerationRecord:
    """Bridge LLMResponse → GenerationRecord with UUID4 generation_id."""
    return GenerationRecord(
        generation_id=str(uuid.uuid4()),
        model=model,
        prompt_text=prompt_text,
        response_text=llm_response.text,
        prompt_tokens=llm_response.prompt_tokens,
        completion_tokens=llm_response.completion_tokens,
        total_tokens=llm_response.total_tokens,
        latency_ms=latency_ms,
    )
```

**Location rationale**: Execution layer (`src/squadops/execution/`), not port layer. Bridges `LLMPort` output into the observability domain.

**Rule**: `generation_id` is REQUIRED and created here. Adapter MUST NOT generate or backfill.

### B.4 Update Factory for LangFuse Provider

**File**: `adapters/telemetry/factory.py` (extend A.4 stub)

Wire the `"langfuse"` provider string to `LangFuseAdapter` with SDK-missing graceful degradation:

```python
def create_llm_observability_provider(
    provider: str = "langfuse",
    config: LangFuseConfig | None = None,
    secret_manager: SecretManager | None = None,
) -> LLMObservabilityPort:
    if config is None or not config.enabled:
        return NoOpLLMObservabilityAdapter()

    if provider == "langfuse":
        try:
            from adapters.telemetry.langfuse.adapter import LangFuseAdapter
            resolved_config = _resolve_secrets(config, secret_manager)
            return LangFuseAdapter(resolved_config)
        except ImportError:
            logger.warning(
                "langfuse SDK not installed; falling back to NoOp adapter. "
                "Install with: pip install 'squadops[langfuse]'"
            )
            return NoOpLLMObservabilityAdapter(
                health_status="degraded",
                health_reason="langfuse SDK not installed",
            )

    raise ValueError(f"Unknown LLM observability provider: {provider}")
```

**Factory health-status mapping** (exhaustive):

| Condition | Adapter returned | `health().status` | `health().details` |
|-----------|-----------------|-------------------|---------------------|
| `enabled=false` (or config=None) | `NoOpLLMObservabilityAdapter()` | `ok` | `{}` |
| `enabled=true`, SDK missing | `NoOpLLMObservabilityAdapter(health_status="degraded", ...)` | `degraded` | `{"reason": "langfuse SDK not installed"}` |
| `enabled=true`, SDK present, host reachable | `LangFuseAdapter(config)` | `ok` | `{"buffer_size": N, "dropped_events": N}` |
| `enabled=true`, SDK present, host unreachable | `LangFuseAdapter(config)` | `down` | `{"buffer_size": N, "dropped_events": N, "error": "..."}` |

This ensures every path has a defined status. `ok` = working as intended, `degraded` = wanted on but SDK missing, `down` = adapter exists but backend unreachable.

### B.5 Phase B Verification

**SDK requirement for adapter unit tests**: Adapter unit tests (`test_langfuse_adapter.py`, `test_langfuse_redaction.py`) construct a `LangFuseAdapter`, which requires the SDK. These tests are **NOT** marked `@pytest.mark.langfuse` — they are regular unit tests that run in every CI build. Default CI installs with `pip install -e ".[langfuse]"` so the SDK is always available for unit tests. Only contract/integration/resilience tests (which need a running LangFuse instance) are marked `@pytest.mark.langfuse` and gated behind env vars.

**Two-tier CI rule**:
- **Default CI**: `pip install -e ".[langfuse]"` + `pytest tests/ -m "not langfuse" -v` → adapter unit tests run, contract/integration skip.
- **LangFuse CI**: same install + all env vars set → everything runs, hard-fail on any failure.

```bash
# Adapter unit tests (requires: pip install -e ".[langfuse]")
pytest tests/unit/telemetry/test_langfuse_adapter.py -v

# Buffer/overflow tests
pytest tests/unit/telemetry/test_langfuse_adapter.py -v -k "overflow or buffer"

# close() bounded flush test
pytest tests/unit/telemetry/test_langfuse_adapter.py -v -k "close"

# Redaction tests
pytest tests/unit/telemetry/test_langfuse_redaction.py -v

# Helper tests (no SDK needed — only uses domain models)
pytest tests/unit/telemetry/test_observability_helper.py -v

# All existing tests still pass
pytest tests/unit -v
```

---

## Phase C: Instrumentation

### C.0 Call-Site Enforcement Rules

These rules prevent double-instrumentation and "who starts what" confusion. They MUST be enforced via code review and unit tests.

| Caller | MUST call | MUST NOT call |
|--------|-----------|---------------|
| **Orchestrator** (WarmBoot / Prefect) | `start_cycle_trace`, `end_cycle_trace`, `start_pulse_span`, `end_pulse_span`, `flush`, `close` | `start_task_span`, `end_task_span`, `record_generation` |
| **Agents** (BaseAgent subclasses) | `start_task_span`, `end_task_span`, `record_generation`, `record_event` (task-level) | `start_cycle_trace`, `end_cycle_trace`, `start_pulse_span`, `end_pulse_span`, `flush`, `close` |
| **Queue plumbing** (QueuePort wrappers) | `record_event` (message-level) | All span/trace lifecycle methods, `record_generation` |

**Enforcement mechanism**: Unit tests MUST assert that forbidden methods are NOT called.

| Test file | Test name | Asserts |
|-----------|-----------|---------|
| `tests/unit/agents/roles/test_dev_agent.py` | `test_agent_does_not_call_cycle_or_pulse_methods` | Agent task execution never calls `start_cycle_trace`, `end_cycle_trace`, `start_pulse_span`, `end_pulse_span`, `flush`, `close` on the mock `llm_observability` |
| `tests/unit/agents/roles/test_dev_agent.py` | `test_agent_does_not_call_flush_or_close` | Agent code never calls `flush()` or `close()` — these are orchestrator-only |
| `tests/unit/telemetry/test_langfuse_adapter.py` | `test_queue_plumbing_must_not_call_lifecycle_methods` | A queue wrapper calling `record_event` does NOT call any span/trace lifecycle methods or `record_generation` |
| `tests/unit/api/` (or orchestrator test) | `test_orchestrator_does_not_call_record_generation` | Orchestrator lifecycle code never calls `record_generation` — that's agent-owned |

**The shutdown sequence is orchestrator-only**: `end_cycle_trace()` → `flush()` → `close()`. Agents MUST NOT call `flush()` or `close()`.

### C.1 Orchestrator Lifecycle Hooks

**Target files**: WarmBoot entrypoint and/or Prefect flow entry.

The orchestrator owns Cycle and Pulse boundaries. Instrument with:

```python
# Cycle start
ctx_cycle = CorrelationContext.for_cycle(cycle_id=cycle_id)
llm_obs.start_cycle_trace(ctx_cycle)
llm_obs.record_event(ctx_cycle, StructuredEvent(name="cycle.started", message=f"Cycle {cycle_id} started"))

# Per pulse
ctx_pulse = CorrelationContext.for_pulse(cycle_id=cycle_id, pulse_id=pulse_id)
llm_obs.start_pulse_span(ctx_pulse)
llm_obs.record_event(ctx_pulse, StructuredEvent(name="pulse.started", message=f"Pulse {pulse_id} started"))
# ... pulse work ...
llm_obs.record_event(ctx_pulse, StructuredEvent(name="pulse.completed", message=f"Pulse {pulse_id} completed"))
llm_obs.end_pulse_span(ctx_pulse)

# Cycle end — deterministic shutdown sequence
llm_obs.record_event(ctx_cycle, StructuredEvent(name="cycle.completed", message=f"Cycle {cycle_id} completed"))
llm_obs.end_cycle_trace(ctx_cycle)
llm_obs.flush()
llm_obs.close()
```

**Shutdown sequence** (SIP Section 5.3): `end_cycle_trace()` → `flush()` → `close()`. This is mandatory.

### C.2 Agent Task + Generation Instrumentation

**Target files**: At least one representative agent role implementation in `src/squadops/execution/squad/`.

Agents own Task and Generation boundaries. The SIP event taxonomy (Section 6.3) requires **all four** task events: `task.assigned`, `task.started`, `task.completed`, `task.failed`.

```python
# Task assigned (when task is dequeued / handed to agent)
ctx_task = CorrelationContext.from_envelope(envelope=envelope, agent_id=self.agent_id, agent_role="dev")
self.llm_observability.record_event(ctx_task, StructuredEvent(name="task.assigned", message=f"Task {envelope.task_id} assigned to {self.agent_id}"))

# Task start (when agent begins execution)
self.llm_observability.start_task_span(ctx_task)
self.llm_observability.record_event(ctx_task, StructuredEvent(name="task.started", message=f"Task {envelope.task_id} started"))

try:
    # LLM call + paired generation recording
    start = time.monotonic()
    response = await self.llm.generate(prompt)
    latency_ms = (time.monotonic() - start) * 1000

    record = build_generation_record(llm_response=response, model=model_name, prompt_text=prompt, latency_ms=latency_ms)
    layers = PromptLayerMetadata(prompt_layer_set_id="PLS-...", layers=(...))
    self.llm_observability.record_generation(ctx_task, record, layers)

    # Task completed (success)
    self.llm_observability.record_event(ctx_task, StructuredEvent(name="task.completed", message=f"Task {envelope.task_id} completed"))
except Exception as exc:
    # Task failed (exception / terminal failure)
    self.llm_observability.record_event(ctx_task, StructuredEvent(
        name="task.failed",
        message=f"Task {envelope.task_id} failed: {exc}",
        level="error",
    ))
    raise
finally:
    self.llm_observability.end_task_span(ctx_task)
```

**Paired instrumentation rule**: Every `LLMPort.generate()` / `.chat()` MUST have a paired `record_generation()`.

**PromptLayerMetadata is always required**: The `prompt_layers` parameter on `record_generation()` is typed `PromptLayerMetadata`, not `PromptLayerMetadata | None`. Callers MUST always construct and pass prompt layer metadata. This matches the SIP Definition of Done: "Every Generation includes `PromptLayerMetadata`." Unit tests MUST fail if `record_generation()` is called without prompt layers.

**No guard pattern needed**: Since `BaseAgent` always injects at least a `NoOpLLMObservabilityAdapter` (see A.6), call sites use `self.llm_observability.record_generation(ctx, record, layers)` directly — no `if self.llm_observability:` branching.

### C.3 Queue Plumbing Message Events

**Target**: QueuePort consumers/producers (SquadComms layer).

```python
# Producer
llm_obs.record_event(ctx, StructuredEvent(
    name="message.sent",
    message=f"Message {msg_id} sent to {recipient}",
    attributes=(("message_id", msg_id), ("sender", sender), ("recipient", recipient)),
))

# Consumer
llm_obs.record_event(ctx, StructuredEvent(
    name="message.received",
    message=f"Message {msg_id} received",
    attributes=(("message_id", msg_id),),
))
```

### C.4 docker-compose.langfuse.yml

**File**: `docker-compose.langfuse.yml` (new, project root)

Standalone compose file for local LangFuse development and CI:

```yaml
# ⚠ LOCAL DEV / CI ONLY — hardcoded secrets below are NOT production-grade.
# For production, use Docker secrets, Vault, or environment injection.
services:
  langfuse-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: langfuse          # ⚠ local dev only
      POSTGRES_DB: langfuse
    ports:
      - "5433:5432"  # Avoid conflict with squadops postgres on 5432
    networks:
      - langfuse-net

  langfuse:
    image: langfuse/langfuse:latest
    environment:
      DATABASE_URL: postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      NEXTAUTH_SECRET: mysecret            # ⚠ local dev only
      NEXTAUTH_URL: http://localhost:3000
      SALT: mysalt                         # ⚠ local dev only
    ports:
      - "3000:3000"
    depends_on:
      - langfuse-db
    networks:
      - langfuse-net

networks:
  langfuse-net:
    driver: bridge
```

**Note**: Fully standalone — uses its own `langfuse-net` bridge network with no external dependencies. Agents and tests reach LangFuse via the published port (`localhost:3000`), not Docker-internal DNS.

**Usage** (local dev / CI only — hardcoded secrets are NOT production-grade):
```bash
# Start langfuse standalone (no dependency on squadops services)
docker compose -f docker-compose.langfuse.yml up -d

# Or start alongside existing services
docker compose up -d && docker compose -f docker-compose.langfuse.yml up -d
```

### C.5 Phase C Verification

```bash
# Orchestrator instrumentation (requires running services)
# Manual or smoke test: start a WarmBoot cycle, verify LangFuse trace appears

# Agent paired instrumentation (unit test)
pytest tests/unit/agents/roles/ -v -k "record_generation"

# All existing tests still pass
pytest tests/unit -v
```

---

## Phase D: Tests & Documentation

### D.1 Unit Tests

**New test files**:

| File | Tests |
|------|-------|
| `tests/unit/telemetry/test_models.py` | Extend with: `CorrelationContext` (frozen, nullable fields, three factories, `from_envelope` bridge), `PromptLayer`, `PromptLayerMetadata` (tuple layers), `GenerationRecord` (generation_id required) |
| `tests/unit/telemetry/test_ports.py` | Extend with: `LLMObservabilityPort` is abstract, method presence check |
| `tests/unit/telemetry/test_adapters.py` | Extend with: `NoOpLLMObservabilityAdapter` satisfies contract, all methods no-op, `health()` returns `"ok"` by default, `health()` returns `"degraded"` when constructed with `health_status="degraded"` |
| `tests/unit/telemetry/test_langfuse_adapter.py` | **New**: LangFuseAdapter payload shapes, CorrelationContext propagation, PromptLayerMetadata presence, buffer overflow (drop oldest + counter), `close()` bounded flush, failure isolation (no propagation), sampling behavior |
| `tests/unit/telemetry/test_langfuse_redaction.py` | **New**: Standard mode strips secrets, strict mode strips PII + hashes, no false positives on normal text |
| `tests/unit/telemetry/test_observability_helper.py` | **New**: `build_generation_record` produces valid record, `generation_id` is UUID4, all fields bridged from `LLMResponse` |
| `tests/unit/telemetry/test_factory.py` | Extend with: `create_llm_observability_provider` returns NoOp(`"ok"`) when disabled, returns LangFuseAdapter when enabled, returns NoOp(`"degraded"`) + logs warning when SDK missing + `enabled=true` |
| `tests/unit/agents/roles/test_*_agent.py` | Extend at least one per role: verify `record_generation()` called when LLM call made (paired instrumentation) |
| `tests/unit/agents/roles/test_dev_agent.py` | **New tests**: `test_agent_emits_task_events_on_success` — success path emits `task.assigned`, `task.started`, `task.completed` (in order). `test_agent_emits_task_events_on_failure` — exception path emits `task.assigned`, `task.started`, `task.failed` (in order). Together these cover all 4 taxonomy events with explicit success/failure separation. |
| `tests/unit/telemetry/test_sdk_isolation.py` | **New**: Import guardrail test — scans all `.py` files under `src/squadops/` and asserts zero lines match `import langfuse` or `from langfuse`. Enforces scope fence: LangFuse SDK MUST only appear in `adapters/telemetry/langfuse/`. |

**Call-site boundary enforcement tests** (required — these are the unit-test equivalents of the C.0 rules):

| File | Test name | Asserts |
|------|-----------|---------|
| `tests/unit/agents/roles/test_dev_agent.py` | `test_agent_does_not_call_flush_or_close` | Agent task execution never calls `flush()` or `close()` on mock `llm_observability` |
| `tests/unit/agents/roles/test_dev_agent.py` | `test_agent_does_not_call_cycle_or_pulse_methods` | Agent never calls `start_cycle_trace`, `end_cycle_trace`, `start_pulse_span`, `end_pulse_span` |
| `tests/unit/api/` (or orchestrator test) | `test_orchestrator_does_not_call_record_generation` | Orchestrator lifecycle code never calls `record_generation` |

These MUST exist as named tests, not just code review guidance. Reviewers can verify their presence by name.

**Fixture additions** (`tests/unit/conftest.py`):

```python
@pytest.fixture
def mock_llm_observability():
    """Mock LLMObservabilityPort for testing."""
    mock = MagicMock()
    mock.health = AsyncMock(return_value={"status": "ok", "backend": "mock", "details": {}})
    return mock
```

Also extend `mock_ports` fixture to include `"llm_observability": MagicMock()`.

### D.2 Contract Tests

**File**: `tests/integration/telemetry/test_langfuse_contract.py` (new)

```python
@pytest.mark.integration
@pytest.mark.langfuse
class TestLangFuseContract:
    """Contract tests: submit telemetry to a running LangFuse instance."""

    def test_submit_trace(self, langfuse_adapter): ...
    def test_submit_spans(self, langfuse_adapter): ...
    def test_submit_generation_with_prompt_layers(self, langfuse_adapter): ...
    def test_submit_event(self, langfuse_adapter): ...
    def test_health_returns_ok(self, langfuse_adapter): ...
```

**Gating**: Skipped by default unless all env vars present.

### D.3 Integration Tests

**File**: `tests/integration/telemetry/test_langfuse_integration.py` (new)

```python
@pytest.mark.integration
@pytest.mark.langfuse
class TestLangFuseIntegration:
    """End-to-end: execute a minimal cycle and verify LangFuse data."""

    def test_cycle_produces_trace(self): ...
    def test_pulse_and_task_spans_exist(self): ...
    def test_generation_has_prompt_layers(self): ...
    def test_message_sent_received_correlation(self): ...
```

### D.4 Resilience Tests

**File**: `tests/integration/telemetry/test_langfuse_resilience.py` (new)

```python
@pytest.mark.integration
@pytest.mark.langfuse
class TestLangFuseResilience:
    """Verify graceful degradation when LangFuse is unavailable."""

    def test_cycle_completes_without_langfuse(self): ...
    def test_adapter_buffers_and_retries(self): ...
    def test_close_completes_within_timeout(self): ...
    def test_warnings_emitted_on_failure(self): ...
```

### D.5 CI Skip Logic

**File**: `tests/integration/conftest.py` (extend existing)

```python
import os
import pytest

_langfuse_available = all([
    os.getenv("SQUADOPS__LANGFUSE__ENABLED", "").lower() == "true",
    os.getenv("SQUADOPS__LANGFUSE__HOST", ""),
    os.getenv("SQUADOPS__LANGFUSE__PUBLIC_KEY", ""),
    os.getenv("SQUADOPS__LANGFUSE__SECRET_KEY", ""),
])

def pytest_collection_modifyitems(config, items):
    if not _langfuse_available:
        skip_langfuse = pytest.mark.skip(reason="LangFuse not configured (need ENABLED + HOST + keys)")
        for item in items:
            if "langfuse" in item.keywords:
                item.add_marker(skip_langfuse)
```

**CI commands** (two tiers):

```bash
# Default CI — installs SDK extra, runs all tests EXCEPT langfuse-marked
# Adapter unit tests (test_langfuse_adapter.py, test_langfuse_redaction.py) run here
pip install -e ".[langfuse]" -r tests/requirements.txt
pytest tests/ -m "not langfuse" -v

# LangFuse CI job (opt-in, requires LangFuse docker compose + env vars)
# Runs everything including contract/integration/resilience
pip install -e ".[langfuse]" -r tests/requirements.txt
SQUADOPS__LANGFUSE__ENABLED=true \
SQUADOPS__LANGFUSE__HOST=http://localhost:3000 \
SQUADOPS__LANGFUSE__PUBLIC_KEY=$LANGFUSE_PK \
SQUADOPS__LANGFUSE__SECRET_KEY=$LANGFUSE_SK \
pytest tests/ -v
```

**Rules** (SIP Sections 10.2–10.5):
- Default CI: `pip install -e ".[langfuse]"` + `pytest -m "not langfuse"` — adapter unit tests run (SDK present), contract/integration/resilience never run, never block.
- LangFuse CI: All 4 env vars set → **all three gated categories** (contract, integration, resilience) also execute. Any failure MUST fail the build. No soft-fail, no soft-warn.
- The `pytest_collection_modifyitems` skip logic is a safety net for running `pytest tests/` locally without env vars — `@pytest.mark.langfuse` tests skip with a message rather than erroring.

### D.6 .env.example Update

**File**: `.env.example` (extend existing)

Add after the existing telemetry section:

```bash
# LangFuse LLM Observability (SIP-0061)
# SQUADOPS__LANGFUSE__ENABLED=false
# SQUADOPS__LANGFUSE__HOST=http://localhost:3000
# SQUADOPS__LANGFUSE__PUBLIC_KEY=secret://LANGFUSE_PUBLIC_KEY
# SQUADOPS__LANGFUSE__SECRET_KEY=secret://LANGFUSE_SECRET_KEY
# SQUADOPS__LANGFUSE__REDACTION_MODE=standard   # use "strict" in production
# SQUADOPS__LANGFUSE__SAMPLE_RATE_PERCENT=100
# SQUADOPS__LANGFUSE__FLUSH_INTERVAL_SECONDS=5
# SQUADOPS__LANGFUSE__BUFFER_MAX_SIZE=1000
# SQUADOPS__LANGFUSE__SHUTDOWN_FLUSH_TIMEOUT_SECONDS=5
```

### D.7 Phase D Verification

```bash
# Full unit test suite
pytest tests/unit -v

# LangFuse-specific unit tests
pytest tests/unit/telemetry/ -v -k "langfuse or LLMObservability or CorrelationContext or GenerationRecord"

# Contract tests (requires local LangFuse)
docker compose -f docker-compose.langfuse.yml up -d
SQUADOPS__LANGFUSE__ENABLED=true \
SQUADOPS__LANGFUSE__HOST=http://localhost:3000 \
SQUADOPS__LANGFUSE__PUBLIC_KEY=pk-lf-... \
SQUADOPS__LANGFUSE__SECRET_KEY=sk-lf-... \
pytest tests/integration/telemetry/ -v -m langfuse

# Verify CI skip (without env vars)
pytest tests/integration/telemetry/ -v -m langfuse  # Should skip all
```

---

## File Change Summary

### New Files

| File | Phase | Description |
|------|-------|-------------|
| `src/squadops/ports/telemetry/llm_observability.py` | A | `LLMObservabilityPort` ABC |
| `adapters/telemetry/noop_llm_observability.py` | A | No-op adapter |
| `adapters/telemetry/langfuse/__init__.py` | B | Package init |
| `adapters/telemetry/langfuse/adapter.py` | B | `LangFuseAdapter` |
| `adapters/telemetry/langfuse/redaction.py` | B | Redaction strategies |
| `src/squadops/execution/observability.py` | B | `build_generation_record` helper |
| `docker-compose.langfuse.yml` | C | Local LangFuse dev environment (**LOCAL DEV / CI ONLY** — contains hardcoded placeholder secrets) |
| `tests/unit/telemetry/test_langfuse_adapter.py` | D | Adapter unit tests |
| `tests/unit/telemetry/test_langfuse_redaction.py` | D | Redaction tests |
| `tests/unit/telemetry/test_observability_helper.py` | D | Helper tests |
| `tests/unit/telemetry/test_sdk_isolation.py` | D | Import guardrail test |
| `tests/integration/telemetry/__init__.py` | D | Package init |
| `tests/integration/telemetry/test_langfuse_contract.py` | D | Contract tests |
| `tests/integration/telemetry/test_langfuse_integration.py` | D | Integration tests |
| `tests/integration/telemetry/test_langfuse_resilience.py` | D | Resilience tests |

### Modified Files

| File | Phase | Change |
|------|-------|--------|
| `src/squadops/telemetry/models.py` | A | Add `CorrelationContext`, `PromptLayer`, `PromptLayerMetadata`, `GenerationRecord` |
| `src/squadops/ports/telemetry/__init__.py` | A | Export `LLMObservabilityPort` |
| `adapters/telemetry/__init__.py` | A | Export `create_llm_observability_provider` |
| `adapters/telemetry/factory.py` | A+B | Add `create_llm_observability_provider` |
| `src/squadops/config/schema.py` | A | Add `LangFuseConfig`, add `langfuse` field to `AppConfig` |
| `src/squadops/execution/agent.py` | A | Add `llm_observability` param to `BaseAgent.__init__` |
| `pyproject.toml` | A | Register `@pytest.mark.langfuse` |
| `.env.example` | D | Add `SQUADOPS__LANGFUSE__*` variables |
| `tests/unit/conftest.py` | D | Add `mock_llm_observability` fixture, extend `mock_ports` |
| `tests/unit/telemetry/test_models.py` | D | Add tests for new domain models |
| `tests/unit/telemetry/test_ports.py` | D | Add `LLMObservabilityPort` abstract test |
| `tests/unit/telemetry/test_adapters.py` | D | Add no-op adapter tests |
| `tests/unit/telemetry/test_factory.py` | D | Add factory tests for new provider |
| `tests/unit/agents/roles/test_dev_agent.py` | D | Add task event taxonomy tests (success + failure paths) |
| `tests/unit/agents/roles/test_*_agent.py` | D | Add `record_generation()` paired instrumentation test (at least one per role) |
| `tests/integration/conftest.py` | D | Add langfuse skip logic |

---

## Dependencies

### Python Package — Optional Extra

The LangFuse SDK is an **optional dependency**, not a core requirement. It is only needed when `langfuse.enabled = true`.

**pyproject.toml** (add optional extra):

```toml
[project.optional-dependencies]
langfuse = ["langfuse>=2.0"]
```

**Install commands**:

```bash
# Production install (no SDK, NoOp adapter used at runtime)
pip install -e .

# Development / CI install (SDK present for adapter unit tests)
pip install -e ".[langfuse]"

# Full test install
pip install -e ".[langfuse]" -r tests/requirements.txt
```

**Lazy import in adapter** — See B.1: `LangFuseAdapter` lazy-imports the SDK inside `__init__`, not at module level. The module can be imported without the SDK; only construction fails.

**Factory graceful degradation** — See B.4: when SDK is missing and `config.enabled` is `True`, the factory returns `NoOpLLMObservabilityAdapter(health_status="degraded")` instead of crashing.

### Infrastructure

- LangFuse instance (local via `docker-compose.langfuse.yml` or remote)
- PostgreSQL for LangFuse's own storage (separate from SquadOps postgres)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LangFuse SDK breaking changes | Low | Medium | Pin SDK version; contract tests catch regressions |
| Buffer overflow under high throughput | Medium | Low | Drop-oldest policy + counter + rate-limited warnings |
| `close()` blocks on shutdown | Medium | High | Bounded by `shutdown_flush_timeout_seconds`; daemon thread auto-dies |
| Redaction misses sensitive data | Low | High | Config default is `standard`; prod deployments SHOULD set `SQUADOPS__LANGFUSE__REDACTION_MODE=strict`; redaction tests with known patterns |
| Port proliferation (3 telemetry ports) | Low | Low | Each port has distinct purpose; documented in SIP Appendix C |
| CI red from langfuse test flakiness | Medium | Medium | Gated behind env vars; default skip; no soft-fail |
| SDK not installed but `enabled=true` | Medium | Low | Factory graceful degradation → NoOp + warning; lazy import prevents import-time crash |
