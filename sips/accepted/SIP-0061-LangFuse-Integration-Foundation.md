---
title: LangFuse Integration Foundation
status: accepted
author: Framework Committee
created_at: '2025-12-01T00:00:00Z'
updated_at: '2026-02-06T19:37:53.364399Z'
original_filename: SIP-LANGFUSE-INTEGRATION-0_9_0.md
sip_number: 61
---
# SIP-0061 — LangFuse Integration (Foundation)

**Target Version:** 0.9.0
**Roles Impacted:** Lead, Strategy, Dev, QA, Data

---

# 1. Purpose and Intent

This SIP establishes the **LangFuse integration foundation** for SquadOps.

The intent is to provide a **canonical LLM-observability port**, a **LangFuse adapter implementing that port**, and the **domain models for correlation context** — so future 0.9.x work can safely build higher-order features (Cycle Imprint, Inflection Points, Majority Report decisioning) without reworking the plumbing.

This SIP is intentionally scoped to **instrumentation + correlation + reliability + redaction + testability**, expressed through the project's hexagonal architecture (ports & adapters), dependency injection, and frozen-dataclass domain models.

---

# 2. Background

SquadOps executes work via **Cycles / Pulses / Tasks**, with coordination through **SquadComms** (`QueuePort`) and traceability through lineage fields (`correlation_id`, `causation_id`, `trace_id`, `span_id`) on `TaskEnvelope`. The system also uses layered prompt construction (system/role/task/memory/tooling/runtime) via `PromptService`.

The existing telemetry surface consists of two ports:

- **`EventPort`** (`src/squadops/ports/telemetry/events.py`) — `emit(StructuredEvent)`, `start_span()`, `end_span()`, context-manager `span()`. Contract: non-blocking.
- **`MetricsPort`** (`src/squadops/ports/telemetry/metrics.py`) — `counter()`, `gauge()`, `histogram()`. Contract: non-blocking.

These ports handle generic tracing and metrics but lack **LLM-specific observability**: generation capture with prompt-layer metadata, token accounting, and model-call correlation. LangFuse's core strength is exactly this LLM-native telemetry.

---

# 3. Problem Statements

1. LLM calls (via `LLMPort.generate()` / `.chat()`) are not captured as first-class telemetry with prompt-layer detail.
2. There is no port interface for LLM-specific observability (generation recording, prompt-layer correlation).
3. There is no canonical mapping from Cycle/Pulse/Task identifiers into LangFuse traces/spans.
4. SquadComms message correlation to execution lineage is not standardized in telemetry.
5. Prompt layering changes — a primary tuning lever — are not observable.
6. Telemetry reliability and redaction rules are not formalized, risking fragile runs and unsafe capture.

---

# 4. Scope

## In Scope (0.9.0)

- A new **`LLMObservabilityPort`** in `src/squadops/ports/telemetry/` defining the LLM-observability contract.
- A **LangFuse adapter** in `adapters/telemetry/langfuse/` implementing `LLMObservabilityPort`.
- **Domain models** (frozen dataclasses) for correlation context and prompt-layer metadata in `src/squadops/telemetry/models.py`.
- **Configuration** via the existing `AppConfig` schema (`src/squadops/config/schema.py`), loaded by the profile loader.
- **Factory function** in `adapters/telemetry/factory.py` for adapter selection.
- **Constructor injection** of the new port into `BaseAgent`.
- Prescriptive **call-site responsibility** for lifecycle boundaries.
- Prescriptive **redaction + resilience** requirements including buffer/flush/shutdown policies.
- Prescriptive **test strategy** (unit + contract + integration + resilience) with CI gating.

## Out of Scope (future 0.9.x)

- Cycle Imprint artifact definition and generation
- Inflection Point capture and alternate-path analysis
- Majority Report synthesis and decisioning
- Automated gating policies driven by LangFuse scores
- `ObservableLLMPort` wrapper that guarantees every `LLMPort` call is instrumented (see Section 6.8)

---

# 5. Design Overview

## 5.1 Hexagonal Architecture Alignment

```
┌─────────────────────────────────────────────────┐
│                  Core Domain                     │
│  src/squadops/                                   │
│  ├── ports/telemetry/                            │
│  │   ├── events.py        (existing EventPort)   │
│  │   ├── metrics.py       (existing MetricsPort) │
│  │   └── llm_observability.py  (NEW)             │
│  ├── telemetry/models.py  (extended)             │
│  └── execution/agent.py   (BaseAgent + DI)       │
├─────────────────────────────────────────────────┤
│                  Adapters                        │
│  adapters/telemetry/                             │
│  ├── factory.py           (adapter selection)    │
│  └── langfuse/                                   │
│      ├── __init__.py                             │
│      ├── adapter.py       (LangFuseAdapter)      │
│      └── redaction.py     (redaction strategies) │
└─────────────────────────────────────────────────┘
```

## 5.2 Canonical Telemetry Mapping

LangFuse concepts map to SquadOps execution lineage:

| LangFuse Concept | SquadOps Concept | Identifier | Correlated By |
|------------------|------------------|------------|---------------|
| **Trace** | Execution Cycle | `cycle_id` | — (root) |
| **Span** | Pulse boundary | `pulse_id` | `cycle_id` |
| **Span** (nested) | Task boundary | `task_id` | `cycle_id` / `pulse_id` |
| **Generation** | LLM invocation (`LLMPort.generate()` / `.chat()`) | `generation_id` (UUID, per-call) | `cycle_id` / `pulse_id` / `task_id` + `trace_id` / `span_id` |
| **Event** | Lifecycle milestone | via `StructuredEvent.name` | `CorrelationContext` fields |
| **Score** | Reserved for 0.9.x gating | — | — |

Note: `trace_id` and `span_id` from `TaskEnvelope` are **correlation fields** carried on `CorrelationContext`, not generation identifiers. Each LLM invocation gets its own `generation_id` (UUID4) on `GenerationRecord`.

## 5.3 Call-Site Responsibility

Lifecycle boundaries are owned by the component that naturally controls them. This prevents inconsistent dual-instrumentation and clarifies who calls which port methods.

| Owner | Boundaries | Port Methods | Events |
|-------|-----------|--------------|--------|
| **Orchestrator** (WarmBoot entrypoint / Prefect flow) | Cycle, Pulse, Shutdown | `start_cycle_trace()`, `end_cycle_trace()`, `start_pulse_span()`, `end_pulse_span()`, `flush()`, `close()` | `cycle.started`, `cycle.completed`, `pulse.started`, `pulse.completed` |
| **Agents** (BaseAgent + task executors) | Task, Generation | `start_task_span()`, `end_task_span()`, `record_generation()` | `task.assigned`, `task.started`, `task.completed`, `task.failed` |
| **Queue plumbing** (QueuePort consumers/producers) | Message correlation | `record_event()` | `message.sent`, `message.received` |

The orchestrator is also responsible for calling `flush()` at cycle end (since the adapter's background loop may not have drained yet), followed by `close()` to ensure deterministic shutdown of the background flush thread. The sequence is: `end_cycle_trace()` → `flush()` → `close()`.

### Coexistence with EventPort / MetricsPort

- Existing `EventPort` spans remain unchanged. `LLMObservabilityPort` does NOT replace `EventPort`; it adds LLM-specific traceability and prompt-layer metadata.
- The ownership rules above prevent random dual-instrumentation at the same layer. If `EventPort.start_span()` is already called for a task boundary, the `LLMObservabilityPort.start_task_span()` call adds LangFuse-specific context alongside it — they are complementary, not competing.

## 5.4 Canonical Correlation Fields

All telemetry emitted through `LLMObservabilityPort` carries fields from `CorrelationContext` (Section 6.2). Fields are sourced from `TaskEnvelope` lineage and agent identity where available:

- `cycle_id` — always required (from `TaskEnvelope.cycle_id` or orchestrator)
- `pulse_id` — present at pulse and task level; `None` at cycle level
- `task_id` — present at task level; `None` at cycle/pulse level
- `correlation_id` — from `TaskEnvelope.correlation_id`; `None` when no envelope exists
- `causation_id` — from `TaskEnvelope.causation_id`; `None` when no envelope exists
- `trace_id` — from `TaskEnvelope.trace_id`; `None` when no envelope exists
- `span_id` — from `TaskEnvelope.span_id`; `None` when no envelope exists
- `agent_id` — from `BaseAgent.agent_id`; `None` at orchestrator level
- `agent_role` — optional; derived from agent profile
- `message_id` — present only when the event is triggered by handling a SquadComms message

## 5.5 Prompt Layer Correlation

Prompt construction is layered (system, role, task, memory, tooling, runtime). Changes to these layers are **first-class tuning inputs** and MUST be observable.

For every LLM Generation, the adapter MUST attach `PromptLayerMetadata` (Section 6.2) containing:

- `prompt_layer_set_id` — stable identifier for the ordered set of layers
- Per-layer detail: `layer_type`, `layer_id`, `layer_version` or `layer_hash`

Telemetry MUST NOT rely only on a flattened prompt string; `PromptLayerMetadata` with per-layer detail MUST always be included. Prompt and response text MAY be captured on `GenerationRecord` subject to redaction and sampling.

---

# 6. Functional Requirements

## 6.1 LLMObservabilityPort (New Port) — Canonical Definition

> **Single source of truth.** The code block below is the ONE canonical definition of `LLMObservabilityPort`. All prose, mapping tables, call-site tables, and examples in this SIP MUST agree with this definition. If any other section appears to conflict, this code block wins.

A new abstract base class MUST be added at `src/squadops/ports/telemetry/llm_observability.py`:

```python
from abc import ABC, abstractmethod
from squadops.telemetry.models import (
    CorrelationContext,
    GenerationRecord,
    PromptLayerMetadata,
    StructuredEvent,
)


class LLMObservabilityPort(ABC):
    """Port for LLM-specific observability (generation capture, prompt-layer correlation).

    All methods MUST be non-blocking. Implementations MUST buffer/enqueue
    internally and never raise exceptions to the caller.
    """

    @abstractmethod
    def start_cycle_trace(self, ctx: CorrelationContext) -> None:
        """Begin a trace for an execution cycle.

        Precondition: ctx.cycle_id MUST NOT be None.
        """

    @abstractmethod
    def end_cycle_trace(self, ctx: CorrelationContext) -> None:
        """End the active cycle trace. Caller SHOULD call flush() after this."""

    @abstractmethod
    def start_pulse_span(self, ctx: CorrelationContext) -> None:
        """Begin a span for a pulse within the active cycle trace.

        Precondition: ctx.pulse_id MUST NOT be None.
        """

    @abstractmethod
    def end_pulse_span(self, ctx: CorrelationContext) -> None:
        """End the active pulse span."""

    @abstractmethod
    def start_task_span(self, ctx: CorrelationContext) -> None:
        """Begin a span for a task within the active pulse span.

        Precondition: ctx.task_id MUST NOT be None.
        """

    @abstractmethod
    def end_task_span(self, ctx: CorrelationContext) -> None:
        """End the active task span."""

    @abstractmethod
    def record_generation(
        self,
        ctx: CorrelationContext,
        record: GenerationRecord,
        prompt_layers: PromptLayerMetadata,
    ) -> None:
        """Record an LLM generation inside the active task span.

        Precondition: ctx.task_id MUST NOT be None.
        """

    @abstractmethod
    def record_event(self, ctx: CorrelationContext, event: StructuredEvent) -> None:
        """Record a lifecycle event (task.assigned, message.sent, etc.).

        Uses the existing StructuredEvent model for consistency with EventPort.
        CorrelationContext provides the hierarchy correlation that
        StructuredEvent.span_id alone cannot express.
        """

    @abstractmethod
    def flush(self) -> None:
        """Flush buffered telemetry. Non-blocking best-effort."""

    @abstractmethod
    def close(self) -> None:
        """Attempt a bounded flush and release resources.

        MUST NOT block indefinitely. Implementations SHOULD enforce
        a max time budget for the final flush attempt.
        """

    @abstractmethod
    async def health(self) -> dict:
        """Health check for the observability backend.

        Returns:
            {"status": "ok" | "degraded" | "down",
             "backend": "langfuse",
             "details": { ... adapter-specific diagnostics ... }}
        """
```

### Design Decisions

- **Non-blocking contract**: Matches existing `EventPort` and `MetricsPort` conventions — implementations MUST enqueue/buffer, never block the caller.
- **CorrelationContext parameter**: All methods receive context explicitly rather than relying on thread-local or global state, consistent with the DI-first design.
- **Method preconditions**: `start_task_span` / `record_generation` require `task_id != None`; `start_pulse_span` requires `pulse_id != None`; `start_cycle_trace` requires only `cycle_id`. This makes invalid calls visible at the API level.
- **`record_event` takes `StructuredEvent` exclusively**: Reuses the existing frozen dataclass from `src/squadops/telemetry/models.py`. There is no `dict` or `**kwargs` overload — every event payload is typed and immutable. `CorrelationContext` provides the hierarchy correlation that `StructuredEvent.span_id` alone cannot express.
- **`end_cycle_trace`**: Added (was missing from original SIP) so the orchestrator can close the trace symmetrically.
- **`close()`**: Provides bounded shutdown flush with resource cleanup, critical for container lifecycle.
- **Separate from EventPort**: `LLMObservabilityPort` is purpose-built for LLM telemetry. It does NOT replace `EventPort` (generic tracing) or `MetricsPort` (counters/gauges). The 0.9.0 `LangFuseAdapter` implements `LLMObservabilityPort` only. `record_event()` is for LangFuse's LLM observability stream; it does not replace `EventPort` emissions.
- **`health()` method**: Follows the adapter health-check pattern used by `LLMPort`, `QueuePort`, `MemoryPort`, etc.

## 6.2 Domain Models (Frozen Dataclasses)

Added to `src/squadops/telemetry/models.py`, following the project's frozen-dataclass convention (SIP-0.8.8):

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CorrelationContext:
    """Immutable correlation context threaded through Cycle → Pulse → Task → LLM call.

    Fields are nullable to support context at different hierarchy levels:
    - Cycle level: only cycle_id is required
    - Pulse level: cycle_id + pulse_id required
    - Task level: cycle_id + pulse_id + task_id + lineage fields required
    """
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
    def for_cycle(cls, cycle_id: str, agent_id: str | None = None):
        """Construct context at cycle level (orchestrator use)."""
        return cls(cycle_id=cycle_id, agent_id=agent_id)

    @classmethod
    def for_pulse(cls, cycle_id: str, pulse_id: str, agent_id: str | None = None):
        """Construct context at pulse level (orchestrator use)."""
        return cls(cycle_id=cycle_id, pulse_id=pulse_id, agent_id=agent_id)

    @classmethod
    def from_envelope(cls, envelope, agent_id: str, agent_role: str | None = None):
        """Construct from a TaskEnvelope and agent identity (task level).

        Populates all lineage fields from the envelope.
        """
        return cls(
            cycle_id=envelope.cycle_id,
            pulse_id=envelope.pulse_id,
            task_id=envelope.task_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            trace_id=envelope.trace_id,
            span_id=envelope.span_id,
            agent_id=agent_id,
            agent_role=agent_role,
        )


@dataclass(frozen=True)
class PromptLayer:
    """Single prompt layer with version/hash for observability."""
    layer_type: str   # system, role, task, memory, tooling, runtime
    layer_id: str
    layer_version: str | None = None
    layer_hash: str | None = None


@dataclass(frozen=True)
class PromptLayerMetadata:
    """Ordered set of prompt layers attached to an LLM generation."""
    prompt_layer_set_id: str
    layers: tuple[PromptLayer, ...]


@dataclass(frozen=True)
class GenerationRecord:
    """LLM generation data for observability.

    generation_id is a UUID4 string uniquely identifying this LLM invocation.
    It is the LangFuse Generation identifier. trace_id/span_id on
    CorrelationContext are correlation fields, not generation identifiers.
    """
    generation_id: str         # UUID4, unique per LLM call
    model: str
    prompt_text: str           # Full prompt (subject to redaction)
    response_text: str         # Full response (subject to redaction)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
```

### Design Decisions

- **Frozen**: Immutable once created, consistent with `TaskEnvelope`, `TaskResult`, `Span`, `StructuredEvent`.
- **`tuple` for collections**: `PromptLayerMetadata.layers` uses `tuple[PromptLayer, ...]` instead of `list` for hashability and immutability.
- **Nullable fields on `CorrelationContext`**: `pulse_id`, `task_id`, and lineage fields (`correlation_id`, `causation_id`, `trace_id`, `span_id`) are `str | None` to support context at cycle, pulse, and task levels without fabricating placeholder values.
- **Three factory methods**: `for_cycle()`, `for_pulse()`, and `from_envelope()` provide type-safe construction at each hierarchy level. `from_envelope()` bridges `TaskEnvelope` lineage fields into the observability domain without coupling the port to the task model.
- **Scope consistency rule**: Every field except `cycle_id` is `str | None`. The port's method preconditions (Section 6.1) enforce which fields MUST be non-None at each level. No code path may require `pulse_id: str` or `task_id: str` as non-optional types on `CorrelationContext` itself — nullability is checked at the port method boundary, not the dataclass boundary.

## 6.3 Event Taxonomy (Foundation)

The following events MUST be supported at minimum via `record_event()`. Events use the existing `StructuredEvent` model with the `name` field matching the taxonomy below:

- `cycle.started`, `cycle.completed`
- `pulse.started`, `pulse.completed`
- `task.assigned`, `task.started`, `task.completed`, `task.failed`
- `message.sent`, `message.received`

## 6.4 SquadComms Message Correlation

When messages traverse `QueuePort`:

- Producer MUST emit `message.sent` with `message_id`, `sender`, `recipient`, and correlation fields.
- Consumer MUST emit `message.received` with the same `message_id`.
- Correlation MUST include `cycle_id` and SHOULD include `pulse_id` / `task_id` when applicable.
- If `pulse_id` / `task_id` are not known at send time, they MUST be `None` on `CorrelationContext` (never fabricated).

## 6.5 Redaction and Privacy

Telemetry MUST enforce:

- No secrets stored (API keys, tokens, passwords).
- No raw PII stored by default.
- Redaction mode configurable via `AppConfig.langfuse.redaction_mode` with at least: `strict`, `standard`.
- Hashing MUST be supported for stable correlation without exposure.

Redaction logic lives in `adapters/telemetry/langfuse/redaction.py` — it is adapter-specific, not part of the port contract.

## 6.6 Reliability and Failure Isolation

Telemetry emission MUST:

- **Never crash the agent runtime.** This is the non-blocking contract inherited from `EventPort`/`MetricsPort`.
- Implement retry with backoff.
- Implement buffering when LangFuse is unavailable.
- Emit local warnings (via Python `logging`) when telemetry cannot be delivered.

### Buffer and Flush Policies

- **Thread-safety**: Adapter MUST use `queue.Queue` (sync) for the internal buffer. The port methods are sync (non-blocking contract); `asyncio.Queue` is not appropriate.
- **Overflow policy**: When `buffer_max_size` is reached, the adapter MUST **drop the oldest entries**. Newest data is more valuable for debugging. The adapter MUST increment a `dropped_events` counter and emit rate-limited warnings via `logging`.
- **Shutdown behavior**: The `close()` method MUST attempt a bounded flush with a configurable max time budget (default: 5 seconds). It MUST NOT block the process indefinitely. Unflushed entries after the time budget are discarded with a warning. This is critical for container shutdown — the last few generations of a cycle are often the most valuable.
- **Periodic flush**: A background thread flushes the buffer at `config.flush_interval_seconds` intervals.

## 6.7 Instrumentation Helpers

To reduce boilerplate and the risk of missed instrumentation, the execution layer MUST provide a helper:

```python
import uuid

def build_generation_record(
    llm_response: LLMResponse,
    model: str,
    prompt_text: str,
    latency_ms: float | None = None,
) -> GenerationRecord:
    """Build a GenerationRecord from an LLMResponse.

    Bridges LLMPort output into the observability domain.
    Generates a unique generation_id (UUID4) for each invocation.
    """
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

This lives alongside agent code (e.g., `src/squadops/execution/observability.py` or similar) — not in the port layer.

### Rule: `generation_id` is REQUIRED and created at record time

`GenerationRecord.generation_id` is a required field (`str`, not `str | None`). The `build_generation_record()` helper generates it via `uuid.uuid4()` at construction time. The adapter MUST NOT generate or backfill `generation_id` — it is the caller's responsibility to supply it. This ensures every `GenerationRecord` is uniquely identifiable before it enters the buffer.

### Convention: paired instrumentation

Any agent code path that calls `LLMPort.generate()` or `.chat()` MUST have a paired `record_generation()` call. Unit tests for at least one representative agent (per role) MUST verify that `record_generation()` is invoked when an LLM call is made.

## 6.8 Future: ObservableLLMPort Wrapper (Explicitly Out of Scope)

A follow-on SIP MAY introduce an `ObservableLLMPort` that wraps `LLMPort` + `LLMObservabilityPort` to guarantee every generation is recorded without relying on manual pairing. This is deferred from 0.9.0 to avoid introducing a new architectural pattern before the port is proven.

---

# 7. Configuration

## 7.1 AppConfig Extension

LangFuse configuration MUST be added to the existing `AppConfig` schema (`src/squadops/config/schema.py`) as a new `LangFuseConfig` Pydantic model:

```python
class LangFuseConfig(BaseModel):
    """LangFuse observability configuration."""
    enabled: bool = False
    host: str = "http://localhost:3000"
    public_key: str = ""          # Supports secret:// references
    secret_key: str = ""          # Supports secret:// references
    redaction_mode: str = "standard"   # "strict" | "standard"
    sample_rate_percent: int = 100      # 0–100
    flush_interval_seconds: int = 5
    buffer_max_size: int = 1000
    shutdown_flush_timeout_seconds: int = 5
```

Added to `AppConfig` as:

```python
class AppConfig(BaseModel):
    # ... existing fields ...
    langfuse: LangFuseConfig = LangFuseConfig()
```

Environment variable mapping follows the existing convention:
- `SQUADOPS__LANGFUSE__ENABLED=true`
- `SQUADOPS__LANGFUSE__HOST=https://langfuse.example.com`
- `SQUADOPS__LANGFUSE__PUBLIC_KEY=secret://LANGFUSE_PUBLIC_KEY`
- `SQUADOPS__LANGFUSE__SECRET_KEY=secret://LANGFUSE_SECRET_KEY`
- `SQUADOPS__LANGFUSE__REDACTION_MODE=strict`
- `SQUADOPS__LANGFUSE__SAMPLE_RATE_PERCENT=100`

Secret references (`secret://`) are resolved by `SecretManager` during config loading, consistent with `DbConfig.dsn` and other secret-bearing fields.

## 7.2 No Scatter

Direct `os.getenv()` reads for LangFuse configuration in agent code are forbidden. All configuration flows through `AppConfig` → adapter factory → constructor injection.

---

# 8. Dependency Injection

## 8.1 BaseAgent Extension

`BaseAgent` (`src/squadops/execution/agent.py`) MUST accept an optional `LLMObservabilityPort` via constructor injection:

```python
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
```

When `llm_observability` is `None`, no LLM telemetry is emitted (graceful degradation). This follows the existing pattern where `prompt_service` is optional.

## 8.2 Factory

A factory function MUST be added at `adapters/telemetry/factory.py`:

```python
def create_llm_observability_provider(
    provider: str = "langfuse",
    config: LangFuseConfig | None = None,
    secret_manager: SecretManager | None = None,
) -> LLMObservabilityPort:
```

This follows the same pattern as `create_llm_provider()`, `create_memory_provider()`, etc.

When `config.enabled` is `False`, the factory MUST return a **no-op adapter** that satisfies the port contract without side effects.

---

# 9. LangFuse Adapter Implementation

The concrete adapter lives at `adapters/telemetry/langfuse/adapter.py`:

```python
class LangFuseAdapter(LLMObservabilityPort):
    """LangFuse implementation of LLMObservabilityPort.

    Non-blocking: all methods enqueue to an internal buffer.
    A background flush thread sends batches to LangFuse.
    """

    def __init__(self, config: LangFuseConfig) -> None:
        ...
```

### Key Implementation Details

- **Internal buffer**: `queue.Queue` (sync, thread-safe) for telemetry events; flushed periodically or on `flush()`.
- **Overflow**: When `buffer_max_size` is reached, drop oldest entries. Increment `dropped_events` counter. Emit rate-limited warnings.
- **Background flush**: A daemon thread flushes the buffer at `config.flush_interval_seconds` intervals.
- **Retry with backoff**: Failed flushes are retried with exponential backoff.
- **Trace/span state**: Managed internally keyed by `cycle_id` / `pulse_id` / `task_id` from `CorrelationContext`. Span mappings MUST support concurrent tasks; keys include `task_id` and adapter internals are thread-safe (lock-protected maps + queue-based ingestion).
- **Redaction**: Applied before buffering via `redaction.py` strategies selected by `config.redaction_mode`.
- **Sampling**: `config.sample_rate_percent` controls probabilistic sampling (0 = none, 100 = all).
- **`close()`**: Signals the background thread to stop, attempts a bounded flush within `config.shutdown_flush_timeout_seconds`, then releases resources.

Direct LangFuse SDK calls are confined to this adapter. Agents MUST NOT import `langfuse` directly.

---

# 10. Testing Strategy

## 10.1 Unit Tests (`tests/unit/telemetry/`)

- MUST validate that the `LangFuseAdapter` constructs expected LangFuse payload shapes for each method.
- MUST verify `CorrelationContext` field propagation for every call, including nullable field behavior at cycle/pulse/task levels.
- MUST verify `PromptLayerMetadata` is present for every `record_generation()`.
- MUST verify redaction behavior for each `redaction_mode`.
- MUST verify failure isolation: adapter exceptions do not propagate to the caller.
- MUST verify the no-op adapter satisfies the port contract without side effects.
- MUST verify `close()` performs bounded flush and does not hang.
- MUST verify buffer overflow drops oldest entries and increments `dropped_events`.
- MUST include at least one representative agent test (per role) verifying `record_generation()` is invoked when an LLM call is made.
- Use `mock_ports` fixture pattern from `tests/unit/conftest.py`.

## 10.2 Contract Tests (`tests/integration/telemetry/`)

- MUST submit: a trace, spans, events, and a generation to a running LangFuse instance.
- MUST run against `SQUADOPS__LANGFUSE__HOST`.
- Marked with `@pytest.mark.integration` and a new `@pytest.mark.langfuse` marker.
- **CI gating**: Contract tests are skipped by default unless the environment explicitly enables them (`SQUADOPS__LANGFUSE__ENABLED=true` + host + keys present). If executed, submission failures MUST fail the build.
- A `docker-compose.langfuse.yml` (or equivalent dev target) MUST be provided for local and CI execution of contract tests.

## 10.3 Integration Tests (`tests/integration/telemetry/`)

- MUST execute a minimal Cycle and assert that a trace exists for the `cycle_id`.
- MUST assert at least one Pulse span and one Task span exist.
- MUST assert at least one Generation exists with prompt-layer metadata.
- MUST emit a `message.sent` and `message.received` pair and verify correlation.
- Also gated behind `@pytest.mark.langfuse`; same skip/fail rules as contract tests.

## 10.4 Resilience Tests

- MUST simulate LangFuse unavailable (connection refused / timeout).
- The runtime MUST complete the Cycle successfully while emitting local warnings.
- The adapter MUST demonstrate retry/backoff and buffering.
- MUST verify that `close()` completes within the time budget when LangFuse is unreachable.

## 10.5 Test Marker Registration and CI Skip Logic

The `@pytest.mark.langfuse` marker MUST be added to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    # ... existing markers ...
    "langfuse: Tests that require a running LangFuse instance",
]
```

### CI gating rules (explicit)

Default CI behavior: **langfuse-marked tests are skipped** unless all of the following environment variables are set:

- `SQUADOPS__LANGFUSE__ENABLED=true`
- `SQUADOPS__LANGFUSE__HOST` (non-empty)
- `SQUADOPS__LANGFUSE__PUBLIC_KEY` (non-empty)
- `SQUADOPS__LANGFUSE__SECRET_KEY` (non-empty)

Skip logic MUST be implemented in `tests/integration/conftest.py` (or a shared fixture) using `pytest.mark.skipif`, following the same pattern as the existing `@pytest.mark.database` / `@pytest.mark.rabbitmq` markers. When the conditions are met and tests execute, any submission failure MUST fail the build — there is no "soft fail" mode. This prevents accidental red builds on default CI while ensuring real failures are caught when a LangFuse instance is explicitly configured.

---

# 11. Non-Functional Requirements

- **Overhead** (three tiers):
  - **Enqueue path** (`record_*`, `start_*`, `end_*`): MUST be < 5ms p95. These are non-blocking — they enqueue to the internal buffer and return. No network I/O on the caller's thread.
  - **`flush()`**: Best-effort, non-blocking. The background thread performs actual network sends. When called explicitly (e.g., by the orchestrator at cycle end), it signals the background thread to drain the buffer but does NOT block the caller waiting for completion.
  - **`close()`**: Bounded blocking. Attempts a final flush within `config.shutdown_flush_timeout_seconds` (default: 5s), then releases resources. MUST NOT exceed the time budget.
- **Consistency**: All agents MUST use the same port and correlation fields; no per-role wiring.
- **Backward compatibility**: Existing `EventPort`/`MetricsPort` telemetry remains valid; LangFuse is additive.
- **Extensibility**: Domain models use frozen dataclasses with optional fields; new fields can be added without breaking existing data.

---

# 12. Migration Notes

- The existing `EventPort` and `MetricsPort` are NOT replaced or modified. They continue to serve generic tracing and metrics.
- `LLMObservabilityPort` is a new, parallel port for LLM-specific concerns.
- If a future SIP consolidates all telemetry behind a single port, it should supersede the relevant sections of this SIP.
- The `TelemetryConfig` section of `AppConfig` (backend, otlp_endpoint, etc.) remains for OpenTelemetry. `LangFuseConfig` is a sibling, not a replacement.

---

# 13. Implementation Phasing

Implementation is split into four phases, each independently shippable and reviewable:

### Phase A — Core Plumbing
- `LLMObservabilityPort` (port ABC)
- Domain models (`CorrelationContext`, `PromptLayer`, `PromptLayerMetadata`, `GenerationRecord`)
- No-op adapter
- Factory function (`create_llm_observability_provider`)
- `LangFuseConfig` added to `AppConfig`
- `BaseAgent` optional injection (`llm_observability: LLMObservabilityPort | None`)
- `@pytest.mark.langfuse` marker registered

### Phase B — LangFuse Adapter
- `LangFuseAdapter` with buffer, background flush thread, retry/backoff, `close()`
- Redaction strategies (`adapters/telemetry/langfuse/redaction.py`)
- Buffer overflow policy (drop oldest + counter)
- `build_generation_record()` helper

### Phase C — Instrumentation
- Orchestrator: cycle/pulse lifecycle hooks (`start_cycle_trace` / `end_cycle_trace`, `start_pulse_span` / `end_pulse_span`, `flush()`)
- One representative agent/task path instrumented end-to-end (task span + generation recording)
- Queue plumbing: `message.sent` / `message.received` events
- `docker-compose.langfuse.yml` for local LangFuse

### Phase D — Tests and Documentation
- Unit tests (port contract, adapter payloads, no-op, overflow, close, redaction, paired instrumentation)
- Contract tests (gated, against running LangFuse)
- Integration tests (minimal cycle end-to-end)
- Resilience tests (LangFuse unavailable)
- `.env.example` updated with `SQUADOPS__LANGFUSE__*` variables

---

# 14. Executive Summary — What Must Be Built

| Artifact | Location | Type | Phase |
|----------|----------|------|-------|
| `LLMObservabilityPort` | `src/squadops/ports/telemetry/llm_observability.py` | Port (ABC) | A |
| `CorrelationContext` | `src/squadops/telemetry/models.py` | Domain model (frozen dataclass) | A |
| `PromptLayerMetadata`, `PromptLayer` | `src/squadops/telemetry/models.py` | Domain model (frozen dataclass) | A |
| `GenerationRecord` | `src/squadops/telemetry/models.py` | Domain model (frozen dataclass) | A |
| No-op adapter | `adapters/telemetry/noop.py` | Adapter (fallback) | A |
| `create_llm_observability_provider()` | `adapters/telemetry/factory.py` | Factory | A |
| `LangFuseConfig` | `src/squadops/config/schema.py` | Config (Pydantic) | A |
| `BaseAgent` constructor extension | `src/squadops/execution/agent.py` | DI wiring | A |
| `LangFuseAdapter` | `adapters/telemetry/langfuse/adapter.py` | Adapter | B |
| Redaction strategies | `adapters/telemetry/langfuse/redaction.py` | Adapter internals | B |
| `build_generation_record()` | `src/squadops/execution/observability.py` | Helper | B |
| Orchestrator lifecycle hooks | WarmBoot / Prefect entrypoint | Instrumentation | C |
| Agent task + generation instrumentation | Role implementations | Instrumentation | C |
| `docker-compose.langfuse.yml` | Project root | Dev tooling | C |
| Unit tests | `tests/unit/telemetry/` | Tests | D |
| Contract + integration tests | `tests/integration/telemetry/` | Tests | D |

---

# 15. Definition of Done

- `LLMObservabilityPort` exists and follows the non-blocking, DI-injected port pattern.
- `LangFuseAdapter` implements the port and is wired via factory + constructor injection.
- `close()` performs bounded shutdown flush within time budget.
- Buffer overflow drops oldest entries and increments a counter.
- A WarmBoot Cycle produces a LangFuse trace correlated to `cycle_id`.
- Pulses and tasks are represented as spans with correct identifiers.
- Every model call is recorded as a LangFuse Generation inside a Task span.
- Every Generation includes `PromptLayerMetadata`.
- At least one message send/receive pair is recorded with correlation.
- Telemetry continues functioning when LangFuse is unavailable (buffer + retry/backoff) without failing the run.
- Redaction modes prevent secrets and default PII capture.
- No-op adapter is used when `langfuse.enabled` is `False`.
- Contract/integration tests are gated behind `@pytest.mark.langfuse` and skip when no LangFuse instance is available.
- All tests (unit, contract, integration, resilience) pass when executed.

---

# 16. Appendix

## A. Example CorrelationContext at Each Hierarchy Level

```python
from squadops.telemetry.models import CorrelationContext

# Cycle level (orchestrator)
ctx_cycle = CorrelationContext.for_cycle(cycle_id="Cycle-0123")

# Pulse level (orchestrator)
ctx_pulse = CorrelationContext.for_pulse(
    cycle_id="Cycle-0123",
    pulse_id="Pulse-03",
)

# Task level (agent, from TaskEnvelope)
ctx_task = CorrelationContext.from_envelope(
    envelope=task_envelope,
    agent_id="neo-001",
    agent_role="dev",
)
```

## B. Example Generation Recording

```python
from squadops.telemetry.models import (
    GenerationRecord,
    PromptLayer,
    PromptLayerMetadata,
)
from squadops.execution.observability import build_generation_record

# Using the helper to bridge LLMResponse → GenerationRecord
record = build_generation_record(
    llm_response=response,
    model="llama3.2",
    prompt_text="<segmented prompt content>",
    latency_ms=2340.5,
)

layers = PromptLayerMetadata(
    prompt_layer_set_id="PLS-042",
    layers=(
        PromptLayer(layer_type="system", layer_id="sys", layer_version="1.3"),
        PromptLayer(layer_type="role", layer_id="dev", layer_version="2.1"),
        PromptLayer(layer_type="task", layer_id="impl", layer_version="0.9"),
        PromptLayer(layer_type="tooling", layer_id="tools", layer_version="1.0"),
        PromptLayer(layer_type="runtime", layer_id="rt", layer_version="0.4"),
    ),
)

# Usage in agent code (via injected port):
self.llm_observability.record_generation(ctx_task, record, layers)
```

## C. Relationship to Existing Ports

```
EventPort (generic tracing)          ← unchanged
MetricsPort (counters/gauges)        ← unchanged
LLMObservabilityPort (NEW)           ← LLM-specific telemetry
    ├── LangFuseAdapter              ← concrete implementation
    └── NoOpAdapter                  ← fallback when disabled
```

## D. Revision History

- **v1 (initial)**: Original draft with monolithic adapter design.
- **v2 (hex arch alignment)**: Restructured as port/adapter/factory/DI per project conventions.
- **v3 (addendum)**: Added call-site responsibility (Section 5.3), nullable `CorrelationContext` with hierarchy factories (Section 6.2), `record_event` using `StructuredEvent` (Section 6.1), buffer/flush/shutdown policies (Section 6.6), `close()` on port (Section 6.1), CI gating for contract tests (Section 10.2), `build_generation_record` helper (Section 6.7), implementation phasing (Section 13).
- **v4 (fix list)**: Added `generation_id` (UUID4) to `GenerationRecord` and mapping table; clarified prompt text capture vs prompt-layer metadata; added concurrency safety note to adapter internals (Section 9); defined `health()` return contract; clarified `LangFuseAdapter` implements `LLMObservabilityPort` only (not `EventPort`); renamed `sample_rate` → `sample_rate_percent`; rephrased overhead NFR as enqueue-path p95 latency.
- **v5 (doc + spec consistency)**: Marked Section 6.1 as single canonical port definition; added explicit `generation_id` REQUIRED rule with caller responsibility (Section 6.7); added CorrelationContext scope consistency rule (Section 6.2); locked `record_event` to `StructuredEvent` exclusively — no dict overload; split NFR overhead into three tiers (enqueue / flush / close) with distinct budgets (Section 11); expanded CI gating with explicit skip logic and env var requirements (Section 10.5); added `flush()` + `close()` to orchestrator call-site responsibility (Section 5.3).
