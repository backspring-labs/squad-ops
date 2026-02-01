---
sip_uid: 01KG66D5R86Z875596CSRXVTEQ
sip_number: 59
title: Infrastructure Ports Migration — Hexagonal Foundation Layer
status: implemented
author: Framework Committee
approver: null
created_at: '2026-01-29T00:00:00Z'
updated_at: '2026-01-31T21:57:11.607147Z'
original_filename: SIP-Infrastructure-Ports-Migration-0-8-7.md
---
# SIP-INFRASTRUCTURE-PORTS-MIGRATION-0_8_7 — Version Target 0.8.7
## Infrastructure Ports Migration — Hexagonal Foundation Layer

**Status:** Proposed
**Target Version:** 0.8.7
**Author:** Framework Committee
**Depends On:** SIP-0056 (Queue Transport), SIP-0057 (Layered Prompts), SIP-0058 (Capability Contracts)

---

# 1. Purpose and Intent

This SIP migrates the remaining **infrastructure components** from `_v0_legacy/` to the hexagonal architecture established in 0.8.4-0.8.6. It creates the **foundation layer** of ports and adapters that agent implementations depend upon.

The intent is to:
- Complete the **Hexagonal Architecture** (Ports and Adapters) migration for all infrastructure concerns,
- Establish abstract ports for LLM, Tools, Memory, Telemetry, and Tasks,
- Enable agent implementations to depend only on ports, not concrete infrastructure,
- Prepare for SIP-0.8.8 (Agent Migration) by ensuring all dependencies are abstracted.

This SIP applies **Domain-Driven Design (DDD)** principles, separating domain logic from infrastructure by moving all provider-specific code to the adapters layer.

---

# 2. Background

SquadOps 0.8.x has progressively adopted hexagonal architecture:

| Version | SIP | Migration |
|---------|-----|-----------|
| 0.8.4 | SIP-0056 | Queue Transport → `ports/comms/`, `adapters/comms/` |
| 0.8.5 | SIP-0057 | Layered Prompts → `ports/prompts/`, `prompts/` |
| 0.8.6 | SIP-0058 | Capability Contracts → `ports/capabilities/`, `capabilities/` |

The following infrastructure remains in `_v0_legacy/`:

- **LLM** (`agents/llm/`) — LLM client, router, Ollama provider (6 files)
- **Tools** (`agents/tools/`) — FileManager, DockerManager, VersionManager (5 files)
- **Memory** (`agents/memory/`) — LanceDB semantic memory (5 files)
- **Telemetry** (`agents/telemetry/`) — Metrics providers, event emitters (7 files)
- **Tasks** (`agents/tasks/`) — Task registry, Prefect/SQL adapters (7 files)

These components are **foundational** — agent roles, skills, and capabilities depend on them. They must be migrated before agents can be refactored in 0.8.8.

---

# 3. Problem Statements

1. **Tight Coupling:** Agent implementations directly import from `_v0_legacy/agents/llm/`, making it impossible to swap LLM providers without code changes.
2. **No Testing Isolation:** Tools like FileManager perform real I/O, making unit tests slow and brittle.
3. **Memory Lock-in:** The memory system is coupled to LanceDB; no abstraction exists for alternative backends.
4. **Telemetry Sprawl:** Telemetry providers are scattered without a unified port interface.
5. **Task Adapter Inconsistency:** Task adapters predate the hexagonal pattern and don't follow port conventions.

---

# 4. Scope

## In Scope
- Define port interfaces for LLM, Tools, Memory, Telemetry, and Tasks.
- Migrate existing implementations to adapter layer.
- Establish factory patterns for config-driven adapter selection.
- Unit tests with mock ports for domain isolation.
- Integration tests for adapter verification.

## Not Addressed
- Agent role/skill migrations (deferred to SIP-0.8.8).
- Capability handler migrations (deferred to SIP-0.8.8).
- Runtime API migration (deferred to SIP-0.8.8).
- New LLM providers (only migrate existing Ollama adapter).

---

# 5. Strategic Domain Design (DDD)

## 5.1 Bounded Contexts

### LLM Context
- **Port:** `LLMPort` — Contract for text generation and chat completion.
- **Adapter:** `OllamaAdapter` — Ollama-specific implementation.
- **Domain Service:** `LLMRouter` — Stateless routing logic for model selection.

### Tools Context
- **Port:** `FileSystemPort` — Contract for file operations.
- **Port:** `ContainerPort` — Contract for Docker container operations.
- **Port:** `VersionControlPort` — Contract for version management.
- **Adapters:** `LocalFileSystemAdapter`, `DockerAdapter`, `GitAdapter`.

### Memory Context
- **Port:** `MemoryPort` — Contract for semantic memory storage and retrieval.
- **Adapter:** `LanceDBAdapter` — LanceDB-specific implementation.
- **Value Object:** `MemoryEntry` — Immutable memory record with embedding.

### Telemetry Context
- **Port:** `MetricsPort` — Contract for metrics emission.
- **Port:** `EventPort` — Contract for structured event emission.
- **Adapters:** `PrometheusAdapter`, `OTelAdapter`, `ConsoleAdapter`.

### Tasks Context
- **Port:** `TaskRegistryPort` — Contract for task state persistence.
- **Adapters:** `SQLTaskAdapter`, `PrefectTaskAdapter`.

## 5.2 Core Principles

1. **Agents depend on Ports, not Adapters.** All infrastructure access flows through abstract interfaces.
2. **Adapters are swappable.** Deployment profiles select adapters without code changes.
3. **Domain logic is testable in isolation.** Mock ports enable fast, deterministic unit tests.

---

# 6. Technical Architecture (Hexagonal)

## 6.1 Layered Structure

```
# Domain Layer — Pure business logic
src/squadops/llm/
├── __init__.py
├── models.py              # LLMRequest, LLMResponse, ChatMessage
├── exceptions.py          # LLMError, ModelNotFoundError, RateLimitError
└── router.py              # LLMRouter domain service

src/squadops/tools/
├── __init__.py
├── models.py              # FileOperation, ContainerSpec, VersionInfo
└── exceptions.py          # ToolError, FileNotFoundError, ContainerError

src/squadops/memory/
├── __init__.py
├── models.py              # MemoryEntry, MemoryQuery, MemoryResult
└── exceptions.py          # MemoryError, EmbeddingError

src/squadops/telemetry/
├── __init__.py
├── models.py              # MetricEvent, StructuredEvent, Span
└── exceptions.py          # TelemetryError

# Ports Layer — Abstract interfaces
src/squadops/ports/llm/
├── __init__.py
└── provider.py            # LLMPort

src/squadops/ports/tools/
├── __init__.py
├── filesystem.py          # FileSystemPort
├── container.py           # ContainerPort
└── vcs.py                 # VersionControlPort

src/squadops/ports/memory/
├── __init__.py
└── store.py               # MemoryPort

src/squadops/ports/telemetry/
├── __init__.py
├── metrics.py             # MetricsPort
└── events.py              # EventPort

src/squadops/ports/tasks/
├── __init__.py
└── registry.py            # TaskRegistryPort

# Adapters Layer — Concrete implementations
adapters/llm/
├── __init__.py
├── ollama.py              # OllamaAdapter
└── factory.py

adapters/tools/
├── __init__.py
├── local_filesystem.py    # LocalFileSystemAdapter
├── docker.py              # DockerAdapter
├── git.py                 # GitAdapter
└── factory.py

adapters/memory/
├── __init__.py
├── lancedb.py             # LanceDBAdapter
└── factory.py

adapters/telemetry/
├── __init__.py
├── prometheus.py          # PrometheusAdapter
├── otel.py                # OTelAdapter
├── console.py             # ConsoleAdapter
└── factory.py

adapters/tasks/
├── __init__.py
├── sql.py                 # SQLTaskAdapter
├── prefect.py             # PrefectTaskAdapter
└── factory.py
```

## 6.2 Port Interfaces

### LLMPort (Driven Port)

```python
class LLMPort(ABC):
    """Contract for LLM text generation."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text completion."""
        pass

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], model: str | None = None) -> ChatMessage:
        """Multi-turn chat completion."""
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models."""
        pass

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check provider health."""
        pass
```

### FileSystemPort (Driven Port)

```python
class FileSystemPort(ABC):
    """Contract for file system operations."""

    @abstractmethod
    def read(self, path: Path) -> str:
        """Read file contents."""
        pass

    @abstractmethod
    def write(self, path: Path, content: str) -> None:
        """Write file contents."""
        pass

    @abstractmethod
    def exists(self, path: Path) -> bool:
        """Check if path exists."""
        pass

    @abstractmethod
    def list_dir(self, path: Path, pattern: str | None = None) -> list[Path]:
        """List directory contents."""
        pass

    @abstractmethod
    def mkdir(self, path: Path, parents: bool = True) -> None:
        """Create directory."""
        pass

    @abstractmethod
    def delete(self, path: Path) -> None:
        """Delete file or directory."""
        pass
```

### ContainerPort (Driven Port)

```python
class ContainerPort(ABC):
    """Contract for container operations."""

    @abstractmethod
    async def run(self, spec: ContainerSpec) -> ContainerResult:
        """Run a container."""
        pass

    @abstractmethod
    async def stop(self, container_id: str) -> None:
        """Stop a running container."""
        pass

    @abstractmethod
    async def logs(self, container_id: str, tail: int | None = None) -> str:
        """Get container logs."""
        pass

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Check container runtime health."""
        pass
```

### MemoryPort (Driven Port)

```python
class MemoryPort(ABC):
    """Contract for semantic memory storage."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry, return ID."""
        pass

    @abstractmethod
    async def search(self, query: MemoryQuery) -> list[MemoryResult]:
        """Search memory by semantic similarity."""
        pass

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a specific memory by ID."""
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        pass
```

### MetricsPort (Driven Port)

```python
class MetricsPort(ABC):
    """Contract for metrics emission."""

    @abstractmethod
    def counter(self, name: str, value: float = 1, labels: dict | None = None) -> None:
        """Increment a counter metric."""
        pass

    @abstractmethod
    def gauge(self, name: str, value: float, labels: dict | None = None) -> None:
        """Set a gauge metric."""
        pass

    @abstractmethod
    def histogram(self, name: str, value: float, labels: dict | None = None) -> None:
        """Record a histogram observation."""
        pass
```

### EventPort (Driven Port)

```python
class EventPort(ABC):
    """Contract for structured event emission."""

    @abstractmethod
    def emit(self, event: StructuredEvent) -> None:
        """Emit a structured event."""
        pass

    @abstractmethod
    def start_span(self, name: str, parent: Span | None = None) -> Span:
        """Start a tracing span."""
        pass

    @abstractmethod
    def end_span(self, span: Span) -> None:
        """End a tracing span."""
        pass
```

### TaskRegistryPort (Driven Port)

```python
class TaskRegistryPort(ABC):
    """Contract for task state persistence."""

    @abstractmethod
    async def create(self, envelope: TaskEnvelope) -> str:
        """Create a task, return task_id."""
        pass

    @abstractmethod
    async def get(self, task_id: str) -> TaskEnvelope | None:
        """Get task by ID."""
        pass

    @abstractmethod
    async def update_status(self, task_id: str, status: str, result: dict | None = None) -> None:
        """Update task status."""
        pass

    @abstractmethod
    async def list_pending(self, agent_id: str | None = None) -> list[TaskEnvelope]:
        """List pending tasks, optionally filtered by agent."""
        pass
```

## 6.3 Adapter Implementations

### LLM Adapters
- **OllamaAdapter:** Migrated from `_v0_legacy/agents/llm/providers/ollama.py`. Implements `LLMPort` using Ollama REST API.

### Tool Adapters
- **LocalFileSystemAdapter:** Migrated from `_v0_legacy/agents/tools/file_manager.py`. Implements `FileSystemPort` using Python pathlib.
- **DockerAdapter:** Migrated from `_v0_legacy/agents/tools/docker_manager.py`. Implements `ContainerPort` using Docker SDK.
- **GitAdapter:** Migrated from `_v0_legacy/agents/tools/version_manager.py`. Implements `VersionControlPort` using GitPython.

### Memory Adapters
- **LanceDBAdapter:** Migrated from `_v0_legacy/agents/memory/`. Implements `MemoryPort` using LanceDB.

### Telemetry Adapters
- **PrometheusAdapter:** Migrated from `_v0_legacy/agents/telemetry/providers/`. Implements `MetricsPort`.
- **OTelAdapter:** Implements `EventPort` using OpenTelemetry SDK.
- **ConsoleAdapter:** Debug adapter that logs to stdout.

### Task Adapters
- **SQLTaskAdapter:** Migrated from `_v0_legacy/agents/tasks/sql_adapter.py`. Implements `TaskRegistryPort`.
- **PrefectTaskAdapter:** Migrated from `_v0_legacy/agents/tasks/prefect_adapter.py`. Implements `TaskRegistryPort`.

---

# 7. Functional Requirements

## 7.1 LLM Port Requirements

- LLMPort MUST support both single-turn generation and multi-turn chat.
- LLMPort MUST expose model listing for runtime discovery.
- OllamaAdapter MUST handle connection failures gracefully with retry logic.
- LLMRouter MUST support model selection based on task type and availability.

## 7.2 Tool Port Requirements

- FileSystemPort MUST support atomic write operations to prevent partial files.
- ContainerPort MUST support container lifecycle (run, stop, logs).
- VersionControlPort MUST support basic Git operations (status, commit, push).
- All tool ports MUST validate paths to prevent directory traversal attacks.

## 7.3 Memory Port Requirements

- MemoryPort MUST support semantic search with configurable similarity threshold.
- MemoryEntry MUST include metadata for filtering (agent_id, cycle_id, timestamp).
- LanceDBAdapter MUST handle embedding generation internally.

## 7.4 Telemetry Port Requirements

- MetricsPort MUST support counter, gauge, and histogram metric types.
- EventPort MUST support structured events with correlation IDs.
- EventPort MUST support distributed tracing spans.
- All telemetry MUST be non-blocking (fire-and-forget).

## 7.5 Task Port Requirements

- TaskRegistryPort MUST maintain ACI TaskEnvelope integrity (no field mutation).
- TaskRegistryPort MUST support status transitions per ACI lifecycle.
- SQLTaskAdapter MUST use the existing PostgreSQL schema.
- PrefectTaskAdapter MUST integrate with Prefect flow execution.

## 7.6 Factory Requirements

- Each adapter domain MUST have a factory function for config-driven instantiation.
- Factories MUST resolve secrets via `SecretStorePort` (SIP-0054 pattern).
- Unknown provider names MUST raise `ValueError` with clear message.

---

# 8. Testing Requirements (Unit + Integration)

## 8.1 Unit Tests (Domain Isolation - Required)

Unit tests MUST verify domain logic **without infrastructure access**. Use mock ports.

- [ ] LLMRouter correctly selects models based on task type
- [ ] MemoryQuery filtering works with mock MemoryPort
- [ ] StructuredEvent serialization is deterministic
- [ ] TaskEnvelope status transitions follow ACI rules

## 8.2 Integration Tests (Adapter Verification - Required)

Integration tests MUST verify adapters against real infrastructure:

- [ ] OllamaAdapter connects to local Ollama instance
- [ ] LocalFileSystemAdapter reads/writes files correctly
- [ ] DockerAdapter can run/stop containers
- [ ] LanceDBAdapter stores and retrieves embeddings
- [ ] SQLTaskAdapter persists to PostgreSQL
- [ ] PrefectTaskAdapter submits flows

## 8.3 Migration Verification Tests

- [ ] All imports from `_v0_legacy/agents/llm/` are replaced
- [ ] All imports from `_v0_legacy/agents/tools/` are replaced
- [ ] All imports from `_v0_legacy/agents/memory/` are replaced
- [ ] All imports from `_v0_legacy/agents/telemetry/` are replaced
- [ ] All imports from `_v0_legacy/agents/tasks/` are replaced

---

# 9. Non-Functional Requirements

1. **Determinism:** Port interfaces must not introduce non-deterministic behavior.
2. **Performance:** Adapter overhead must be negligible (<1ms per call).
3. **Reliability:** Adapters must handle transient failures with appropriate retries.
4. **Observability:** All adapters must emit metrics via MetricsPort.
5. **Security:** File and container operations must validate inputs to prevent injection.

---

# 10. Migration Strategy

## 10.1 Migration Order

Infrastructure must be migrated in dependency order:

1. **Telemetry** (no dependencies) → enables observability for subsequent migrations
2. **Tools** (depends on telemetry) → FileSystem, Container, VCS
3. **Memory** (depends on telemetry) → LanceDB
4. **LLM** (depends on telemetry) → Ollama
5. **Tasks** (depends on all above) → SQL, Prefect

## 10.2 Compatibility Shim

During migration, a compatibility shim SHOULD be maintained:

```python
# _v0_legacy/agents/llm/__init__.py
import warnings
from adapters.llm import create_llm_provider

warnings.warn(
    "Importing from _v0_legacy/agents/llm is deprecated. "
    "Use adapters.llm.create_llm_provider instead.",
    DeprecationWarning
)

# Re-export for backwards compatibility
__all__ = ["create_llm_provider"]
```

## 10.3 Deletion Criteria

Legacy code MAY be deleted when:
- All imports are migrated (verified by migration tests)
- All integration tests pass with new adapters
- No deprecation warnings are raised in CI

---

# 11. Executive Summary — What Must Be Built

### Domain Layer
| Location | Contents |
|----------|----------|
| `src/squadops/llm/` | `models.py`, `exceptions.py`, `router.py` |
| `src/squadops/tools/` | `models.py`, `exceptions.py` |
| `src/squadops/memory/` | `models.py`, `exceptions.py` |
| `src/squadops/telemetry/` | `models.py`, `exceptions.py` |

### Ports Layer
| Location | Contents |
|----------|----------|
| `src/squadops/ports/llm/` | `LLMPort` |
| `src/squadops/ports/tools/` | `FileSystemPort`, `ContainerPort`, `VersionControlPort` |
| `src/squadops/ports/memory/` | `MemoryPort` |
| `src/squadops/ports/telemetry/` | `MetricsPort`, `EventPort` |
| `src/squadops/ports/tasks/` | `TaskRegistryPort` |

### Adapters Layer
| Location | Contents |
|----------|----------|
| `adapters/llm/` | `OllamaAdapter`, `factory.py` |
| `adapters/tools/` | `LocalFileSystemAdapter`, `DockerAdapter`, `GitAdapter`, `factory.py` |
| `adapters/memory/` | `LanceDBAdapter`, `factory.py` |
| `adapters/telemetry/` | `PrometheusAdapter`, `OTelAdapter`, `ConsoleAdapter`, `factory.py` |
| `adapters/tasks/` | `SQLTaskAdapter`, `PrefectTaskAdapter`, `factory.py` |

### Tests
- Unit tests for domain logic with mock ports
- Integration tests for each adapter
- Migration verification tests

---

# 12. Definition of Done

### Domain Layer
- [ ] `src/squadops/llm/models.py` — `LLMRequest`, `LLMResponse`, `ChatMessage` as frozen dataclasses
- [ ] `src/squadops/tools/models.py` — `FileOperation`, `ContainerSpec`, `VersionInfo` as frozen dataclasses
- [ ] `src/squadops/memory/models.py` — `MemoryEntry`, `MemoryQuery`, `MemoryResult` as frozen dataclasses
- [ ] `src/squadops/telemetry/models.py` — `MetricEvent`, `StructuredEvent`, `Span` as frozen dataclasses

### Port Interfaces
- [ ] `LLMPort` defined with generate, chat, list_models, health methods
- [ ] `FileSystemPort` defined with read, write, exists, list_dir, mkdir, delete methods
- [ ] `ContainerPort` defined with run, stop, logs, health methods
- [ ] `VersionControlPort` defined with status, commit, push methods
- [ ] `MemoryPort` defined with store, search, get, delete methods
- [ ] `MetricsPort` defined with counter, gauge, histogram methods
- [ ] `EventPort` defined with emit, start_span, end_span methods
- [ ] `TaskRegistryPort` defined with create, get, update_status, list_pending methods

### Adapters
- [ ] `OllamaAdapter` migrated and tested
- [ ] `LocalFileSystemAdapter` migrated and tested
- [ ] `DockerAdapter` migrated and tested
- [ ] `GitAdapter` migrated and tested
- [ ] `LanceDBAdapter` migrated and tested
- [ ] `PrometheusAdapter` migrated and tested
- [ ] `OTelAdapter` implemented and tested
- [ ] `ConsoleAdapter` implemented and tested
- [ ] `SQLTaskAdapter` migrated and tested
- [ ] `PrefectTaskAdapter` migrated and tested

### Testing
- [ ] Unit tests pass for all domain models
- [ ] Unit tests pass for LLMRouter with mock LLMPort
- [ ] Integration tests pass for all adapters
- [ ] Migration verification tests confirm no legacy imports remain

### Migration
- [ ] Deprecation warnings added to legacy modules
- [ ] All agent code updated to use new ports (or shims)
- [ ] CI passes with no deprecation warnings

---

# 13. Appendix

## 13.1 Worked Example — LLM Port Usage

```python
# Agent code depends only on port, not adapter
from squadops.ports.llm import LLMPort
from squadops.llm.models import LLMRequest

class LeadAgent:
    def __init__(self, llm: LLMPort, ...):
        self.llm = llm

    async def analyze_task(self, task: str) -> str:
        request = LLMRequest(
            prompt=f"Analyze this task: {task}",
            model="llama3.1:8b",
            max_tokens=500
        )
        response = await self.llm.generate(request)
        return response.text
```

## 13.2 Worked Example — Factory Pattern

```python
# adapters/llm/factory.py
from squadops.ports.llm import LLMPort
from adapters.llm.ollama import OllamaAdapter

def create_llm_provider(
    provider: str = "ollama",
    base_url: str | None = None,
    **kwargs
) -> LLMPort:
    if provider == "ollama":
        return OllamaAdapter(base_url=base_url or "http://localhost:11434", **kwargs)
    raise ValueError(f"Unknown LLM provider: {provider}")
```

## 13.3 Worked Example — Memory Port Usage

```python
from squadops.ports.memory import MemoryPort
from squadops.memory.models import MemoryEntry, MemoryQuery

class AgentMemory:
    def __init__(self, memory: MemoryPort):
        self.memory = memory

    async def remember(self, content: str, metadata: dict) -> str:
        entry = MemoryEntry(
            content=content,
            metadata=metadata,
            timestamp=datetime.utcnow()
        )
        return await self.memory.store(entry)

    async def recall(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        q = MemoryQuery(text=query, limit=limit, threshold=0.7)
        results = await self.memory.search(q)
        return [r.entry for r in results]
```

## 13.4 Migration Dependency Graph

```
                    ┌─────────────┐
                    │  Telemetry  │  (no dependencies)
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
      ┌─────────┐    ┌─────────┐    ┌─────────┐
      │  Tools  │    │  Memory │    │   LLM   │
      └────┬────┘    └────┬────┘    └────┬────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    Tasks    │
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  SIP-0.8.8  │  (Agent Migration)
                    └─────────────┘
```
