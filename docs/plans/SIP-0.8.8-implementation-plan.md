# SIP-0.8.8 Implementation Plan: Agent Migration & Legacy Retirement

**Last Updated**: 2026-01-31 (rev 4.3)
**Status**: Planning (pre-implementation)

---

## Summary

Complete the hexagonal architecture migration by moving all agent implementations from `_v0_legacy/` to the new structure, then **delete `_v0_legacy/` entirely**.

**Scope:**
- **~25,000 LOC** across **117 Python files** in `_v0_legacy/agents/`
- **~1,500 LOC** across **10 Python files** in `_v0_legacy/infra/`
- **~50 non-Python config files** (grafana, prometheus, otel, migrations)
- **3 deferred items** from SIP-0.8.7 (EmbeddingsPort, PrefectAdapter, TaskEnvelope)

**Scope Note:** Legacy/mock agents (testing-only role implementations: audit, comms, creative, curator, devops, finance) will **not** be migrated in 0.8.8 and will be **removed**, with references cleaned and any remaining usage replaced by contract-driven test harnesses.

---

## Implementation Strategy

### Phase Overview

| Phase | Scope | LOC Estimate | Rationale |
|-------|-------|--------------|-----------|
| Phase 1 | 0.8.7 Deferrals | ~800 | Complete infrastructure layer before application layer |
| Phase 2 | Agent Foundation | ~3,500 | BaseAgent, Factory, SkillRegistry - everything depends on these |
| Phase 3 | Agent Roles | ~2,000 | Migrate 5 real agents (Lead, Dev, QA, Strat, Data) |
| Phase 4 | Skills | ~800 | Atomic operations substrate - capabilities compose these |
| Phase 5 | Capabilities | ~7,500 | Task-level deliverables - orchestrate skills, own acceptance |
| Phase 6 | API & Orchestration | ~2,000 | Runtime API, health check, orchestrator |
| Phase 7 | Config & Cleanup | ~500 | Move configs, delete `_v0_legacy/`, version bump |

### Milestones

- After Phase 1: All SIP-0.8.7 deferrals complete
- After Phase 3: Core agents running on hexagonal ports
- After Phase 6: Full system operational without `_v0_legacy/` imports
- After Phase 7: `_v0_legacy/` deleted, version bumped to 0.8.8

### Phase Exit Criteria

| Phase | Exit Criteria |
|-------|---------------|
| Phase 1 | EmbeddingsPort + adapter tests pass; PrefectAdapter tests pass; TaskEnvelope frozen dataclass tests pass; API DTO ↔ dataclass mapping tested |
| Phase 2 | BaseAgent instantiates with all ports; AgentFactory creates agents; SkillRegistry loads skills |
| Phase 3 | All 5 agents process mock tasks with mocked ports; **Golden Path Gate A passes** (routing & wiring validated) |
| Phase 4 | All skills execute with mocked SkillContext (no agent required) |
| Phase 5 | All capability handlers pass contract acceptance checks; **Golden Path Gate B passes** (full architecture validated) |
| Phase 6 | Runtime API serves requests; health check dashboard works |
| Phase 7 | Zero `_v0_legacy/` imports; all tests pass; CI green for 3 runs |

---

## Phase 1: Complete 0.8.7 Deferrals

### 1.1 EmbeddingsPort

**Problem**: SIP-0.8.7 introduced an `embed_fn` callable seam in LanceDBAdapter. This is a temporary measure.

**Solution**: Create proper EmbeddingsPort and inject it.

```
src/squadops/ports/embeddings/
├── __init__.py
└── provider.py            # EmbeddingsPort ABC

adapters/embeddings/
├── __init__.py
├── ollama.py              # OllamaEmbeddingsAdapter
└── factory.py
```

**Port Interface**:
```python
# src/squadops/ports/embeddings/provider.py
from abc import ABC, abstractmethod

class EmbeddingsPort(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...

    @abstractmethod
    def dimensions(self) -> int:
        """Return embedding dimensions for this model."""
        ...
```

**Adapter**:
```python
# adapters/embeddings/ollama.py
class OllamaEmbeddingsAdapter(EmbeddingsPort):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self._base_url = base_url
        self._model = model
        self._dimensions = 768  # nomic-embed-text default

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text}
            )
            return response.json()["embedding"]
```

**LanceDBAdapter Update**:
```python
# adapters/memory/lancedb.py
class LanceDBAdapter(MemoryPort):
    def __init__(self, db_path: str, embeddings: EmbeddingsPort, **config):
        self._embeddings = embeddings  # Replace embed_fn seam

    async def store(self, entry: MemoryEntry) -> str:
        embedding = await self._embeddings.embed(entry.content)
        # ...
```

### 1.2 PrefectTaskAdapter

**Problem**: SIP-0.8.7 provides a stub that raises `NotImplementedError`.

**Solution**: Implement full Prefect integration.

```python
# adapters/tasks/prefect.py
from prefect import get_client
from prefect.client.schemas.objects import TaskRun

class PrefectTaskAdapter(TaskRegistryPort):
    def __init__(self, api_url: str = "http://localhost:4200/api"):
        self._api_url = api_url

    async def create(self, task: Task) -> str:
        async with get_client() as client:
            task_run = await client.create_task_run(...)
            return str(task_run.id)

    async def get(self, task_id: str) -> Task | None:
        async with get_client() as client:
            task_run = await client.read_task_run(task_id)
            return self._to_task(task_run)

    async def update_status(self, task_id: str, status: TaskState, result: dict | None = None) -> None:
        async with get_client() as client:
            await client.set_task_run_state(task_id, self._to_prefect_state(status))

    async def list_pending(self, agent_id: str | None = None) -> list[Task]:
        async with get_client() as client:
            task_runs = await client.read_task_runs(...)
            return [self._to_task(tr) for tr in task_runs]
```

**Prefect Enablement**:
- Introduce explicit config selector: `task_backend = "prefect" | "sql"`
- SQL is the minimal/test default; Prefect is the production choice
- Pin Prefect version in requirements to ensure API stability
- Integration tests gated by env var (`ENABLE_PREFECT_TESTS=1`) to keep CI stable

```python
# adapters/tasks/factory.py
def create_task_registry_provider(
    backend: str = "sql",  # Default to SQL for minimal deployments
    **config
) -> TaskRegistryPort:
    if backend == "prefect":
        from adapters.tasks.prefect import PrefectTaskAdapter
        return PrefectTaskAdapter(**config)
    elif backend == "sql":
        from adapters.tasks.sql import SQLTaskAdapter
        return SQLTaskAdapter(**config)
    raise ValueError(f"Unknown task backend: {backend}")
```

**Exit Criteria**:
- When `task_backend=prefect`: basic execution path works, integration test passes
- When `task_backend=sql`: system runs without Prefect installed

### 1.3 TaskEnvelope Migration to Frozen Dataclasses

**Problem**: TaskEnvelope/TaskResult are Pydantic models in `_v0_legacy`. The compatibility bridge re-exports them.

**Solution**: Create frozen dataclasses and migrate.

```python
# src/squadops/tasks/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class TaskEnvelope:
    """Immutable task envelope for agent-to-agent communication."""
    task_id: str
    task_type: str
    source_agent: str
    target_agent: str | None = None
    cycle_id: str | None = None
    pulse_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    inputs: tuple[tuple[str, Any], ...] = ()
    priority: int = 5
    created_at: datetime | None = None

@dataclass(frozen=True)
class TaskResult:
    """Immutable task result."""
    task_id: str
    status: str  # "completed", "failed", "blocked"
    outputs: tuple[tuple[str, Any], ...] = ()
    error: str | None = None
    completed_at: datetime | None = None
```

**Migration Strategy**:
1. Create new frozen dataclasses in `src/squadops/tasks/models.py`
2. Update `TaskRegistryPort` to use new models
3. Update all adapters to use new models
4. Remove `squadops.tasks.types` compatibility bridge
5. Update all imports across codebase

### 1.4 API Boundary DTO ↔ Internal Dataclass Mapping

**Requirement**: Keep Pydantic (or equivalent) DTOs at the Runtime API boundary for validation. Map to/from internal frozen dataclasses at ingress/egress.

```python
# src/squadops/api/schemas.py (Pydantic DTOs for API boundary)
from pydantic import BaseModel

class TaskRequestDTO(BaseModel):
    task_type: str
    source_agent: str
    target_agent: str | None = None
    inputs: dict = {}
    priority: int = 5

# src/squadops/api/mapping.py
from squadops.tasks.models import TaskEnvelope

def dto_to_envelope(dto: TaskRequestDTO, task_id: str) -> TaskEnvelope:
    """Map API DTO → internal frozen dataclass at ingress."""
    return TaskEnvelope(
        task_id=task_id,
        task_type=dto.task_type,
        source_agent=dto.source_agent,
        target_agent=dto.target_agent,
        inputs=tuple(dto.inputs.items()),
        priority=dto.priority,
    )

def envelope_to_response(envelope: TaskEnvelope) -> dict:
    """Map internal dataclass → API response at egress."""
    return {
        "task_id": envelope.task_id,
        "task_type": envelope.task_type,
        "status": "accepted",
    }
```

**Exit Criteria for DTO Mapping**:
- Valid task request → internal model created
- Invalid task request → structured error response (no crash)
- Internal TaskResult → API response serialization verified

### 1.5 Tests - Phase 1

```
tests/unit/embeddings/
├── __init__.py
├── test_port.py
├── test_ollama_adapter.py

tests/unit/tasks/
├── test_task_envelope.py      # Frozen dataclass tests
├── test_prefect_adapter.py    # Full adapter tests (mocked Prefect)

tests/unit/api/
├── test_dto_mapping.py        # DTO ↔ dataclass mapping

tests/integration/embeddings/
└── test_ollama_integration.py  # Requires Ollama

tests/integration/tasks/
└── test_prefect_integration.py  # Requires Prefect server
```

### 1.6 Required Integration Test: Memory + Embeddings E2E

**Gate**: This test MUST pass before removing the legacy `embed_fn` seam and before legacy deletion.

```python
# tests/integration/memory/test_embeddings_e2e.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_memory_embeddings_vector_store_e2e(tmp_path):
    """
    E2E test: EmbeddingsPort + MemoryPort + LanceDB.

    Verifies:
    - Embeddings adapter is invoked
    - Vectors are persisted
    - Query returns expected shape (top-k) and non-empty results
    """
    # Boot memory adapter with real EmbeddingsPort
    embeddings = OllamaEmbeddingsAdapter()
    memory = LanceDBAdapter(db_path=str(tmp_path / "test.lancedb"), embeddings=embeddings)

    # Execute: embed → upsert → query
    entry = MemoryEntry(content="The quick brown fox jumps over the lazy dog")
    memory_id = await memory.store(entry)

    results = await memory.search(MemoryQuery(text="fox jumping", limit=5))

    # Assert behavior/shape (metric-agnostic, avoids brittle thresholds)
    assert len(results) > 0, "Search should return at least one result"
    assert any(r.memory_id == memory_id for r in results), "Stored entry should be retrievable"
    assert results[0].score is not None, "Results should have scores"
    assert results[0].score >= results[-1].score, "Results should be sorted by score descending"
```

> **Note**: Different embeddings + distance metrics produce different score ranges. Avoid fixed thresholds like `score > 0.5` which create false failures. If a threshold is needed, make it adapter/metric configurable via settings.

---

## Phase 2: Agent Foundation

### 2.1 BaseAgent Refactoring

**Current State**: `_v0_legacy/agents/base_agent.py` (~2,500 LOC) with:
- Lifecycle hooks (on_agent_start, on_cycle_start, on_pulse_start, etc.)
- EventEmitter and LifecycleHookManager
- Message bus integration (aio_pika)
- Telemetry client integration

**Target**: `src/squadops/agents/base.py` with port injection

```python
# src/squadops/agents/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from squadops.ports.llm import LLMPort
from squadops.ports.memory import MemoryPort
from squadops.ports.telemetry import MetricsPort, EventPort
from squadops.ports.tools import FileSystemPort
from squadops.ports.comms import QueuePort
from squadops.prompts import PromptService

@dataclass(frozen=True)
class PortsBundle:
    """Immutable bundle of all ports for easy passing to contexts."""
    llm: LLMPort
    memory: MemoryPort
    prompt_service: PromptService
    queue: QueuePort
    metrics: MetricsPort
    events: EventPort
    filesystem: FileSystemPort

class BaseAgent(ABC):
    """Base agent with full port injection."""

    def __init__(
        self,
        *,
        agent_id: str,
        role_id: str,
        llm: LLMPort,
        memory: MemoryPort,
        prompt_service: PromptService,
        queue: QueuePort,
        metrics: MetricsPort,
        events: EventPort,
        filesystem: FileSystemPort,
    ):
        self._agent_id = agent_id
        self._role_id = role_id
        # Store individual ports for property access
        self._llm = llm
        self._memory = memory
        self._prompt_service = prompt_service
        self._queue = queue
        self._metrics = metrics
        self._events = events
        self._filesystem = filesystem
        # Store bundle for easy context building
        self._ports = PortsBundle(
            llm=llm, memory=memory, prompt_service=prompt_service,
            queue=queue, metrics=metrics, events=events, filesystem=filesystem
        )
        self._lifecycle = LifecycleHookManager()

    # Lifecycle hooks
    async def on_agent_start(self) -> None: ...
    async def on_agent_stop(self) -> None: ...
    async def on_cycle_start(self, cycle_id: str) -> None: ...
    async def on_cycle_end(self, cycle_id: str) -> None: ...
    async def on_pulse_start(self, pulse_id: str) -> None: ...
    async def on_pulse_end(self, pulse_id: str) -> None: ...

    @abstractmethod
    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        """Process incoming task. Subclasses must implement."""
        ...

    # Port accessors (read-only)
    @property
    def llm(self) -> LLMPort: return self._llm
    @property
    def memory(self) -> MemoryPort: return self._memory
    @property
    def ports(self) -> PortsBundle: return self._ports
    # ... etc
```

### 2.2 AgentFactory

```python
# src/squadops/agents/factory.py
from squadops.agents.base import BaseAgent
from squadops.agents.roles import LeadAgent, DevAgent, QAAgent, StratAgent, DataAgent

class AgentFactory:
    """Factory for creating agents with dependency injection."""

    ROLE_REGISTRY = {
        "lead": LeadAgent,
        "dev": DevAgent,
        "qa": QAAgent,
        "strat": StratAgent,
        "data": DataAgent,
    }

    def __init__(
        self,
        *,
        llm: LLMPort,
        memory: MemoryPort,
        prompt_service: PromptService,
        queue: QueuePort,
        metrics: MetricsPort,
        events: EventPort,
        filesystem: FileSystemPort,
        skill_registry: SkillRegistry,
    ):
        self._ports = {
            "llm": llm,
            "memory": memory,
            "prompt_service": prompt_service,
            "queue": queue,
            "metrics": metrics,
            "events": events,
            "filesystem": filesystem,
        }
        self._skill_registry = skill_registry

    def create(self, role_id: str, agent_id: str | None = None) -> BaseAgent:
        """Create agent by role ID."""
        if role_id not in self.ROLE_REGISTRY:
            raise AgentRoleNotFoundError(f"Unknown role: {role_id}")

        agent_class = self.ROLE_REGISTRY[role_id]
        agent_id = agent_id or f"{role_id}-{uuid4().hex[:8]}"

        return agent_class(
            agent_id=agent_id,
            skill_registry=self._skill_registry,
            **self._ports,
        )
```

### 2.3 SkillRegistry

```python
# src/squadops/agents/skills/registry.py
from squadops.agents.skills.base import Skill
from squadops.agents.skills.context import SkillContext

class SkillRegistry:
    """Registry for discovering, loading, and executing skills."""

    def __init__(self):
        self._skills: dict[str, type[Skill]] = {}

    def register(self, skill_class: type[Skill]) -> None:
        """Register a skill class."""
        self._skills[skill_class.SKILL_ID] = skill_class

    def get(self, skill_id: str) -> type[Skill]:
        """Get skill class by ID."""
        if skill_id not in self._skills:
            raise SkillNotFoundError(f"Unknown skill: {skill_id}")
        return self._skills[skill_id]

    def load_skills(self, skill_ids: list[str]) -> list[Skill]:
        """Instantiate multiple skills (for allowlist/introspection)."""
        return [self.get(sid)() for sid in skill_ids]

    async def execute(self, skill_id: str, inputs: dict, ctx: SkillContext) -> dict:
        """Execute a skill by ID with given inputs and context.

        Instantiates skill per call (v1). Caching/pooling is optional optimization.
        """
        skill_class = self.get(skill_id)
        skill = skill_class()
        return await skill.execute(inputs, ctx)

    @classmethod
    def discover(cls) -> "SkillRegistry":
        """Auto-discover skills from squadops.agents.skills package.

        Discovery uses pkgutil/importlib to scan skill subpackages.
        Each skill module exports a SKILLS list of skill classes.
        """
        import importlib
        import pkgutil

        registry = cls()
        skills_package = importlib.import_module("squadops.agents.skills")

        for importer, modname, ispkg in pkgutil.walk_packages(
            skills_package.__path__, prefix="squadops.agents.skills."
        ):
            module = importlib.import_module(modname)
            if hasattr(module, "SKILLS"):
                for skill_class in module.SKILLS:
                    registry.register(skill_class)
        return registry
```

### 2.4 Directory Structure

```
src/squadops/agents/
├── __init__.py
├── models.py              # Agent, AgentRole, AgentContext dataclasses
├── exceptions.py          # AgentError, SkillNotFoundError, AgentRoleNotFoundError
├── base.py                # BaseAgent with port injection
├── factory.py             # AgentFactory
├── lifecycle.py           # LifecycleHookManager, EventEmitter
├── roles/
│   ├── __init__.py
│   ├── lead.py
│   ├── dev.py
│   ├── qa.py
│   ├── strat.py
│   └── data.py
└── skills/
    ├── __init__.py
    ├── base.py            # Skill ABC
    ├── context.py         # SkillContext
    ├── registry.py        # SkillRegistry
    ├── shared/
    ├── lead/
    ├── dev/
    ├── qa/
    ├── strat/
    └── data/

src/squadops/execution/
├── __init__.py
├── models.py              # ExecutionMode, ExecutionEvidence, MockInRealModeError
└── runner.py              # Execution enforcement logic
```

### 2.5 Tests - Phase 2

```
tests/unit/agents/
├── __init__.py
├── test_base_agent.py     # BaseAgent with mocked ports
├── test_factory.py        # AgentFactory creates agents correctly
├── test_lifecycle.py      # Lifecycle hooks fire correctly
├── test_skill_registry.py # Skill discovery and loading
```

---

## Phase 3: Agent Roles

### 3.1 Migration Strategy

Migrate agents in dependency order:
1. **LeadAgent** - Orchestration, task delegation (depends on nothing)
2. **DevAgent** - Code generation (depends on Lead for tasks)
3. **QAAgent** - Testing (depends on Dev for code)
4. **StratAgent** - Strategy (depends on Lead for direction)
5. **DataAgent** - Analytics (depends on all for metrics)

### 3.2 LeadAgent

```python
# src/squadops/agents/roles/lead.py
class LeadAgent(BaseAgent):
    """Lead agent for task orchestration and delegation."""

    ROLE_ID = "lead"
    DEFAULT_SKILLS = [
        "task_analysis",
        "task_delegation",
        "code_review",
        "cycle_planning",
        "governance_approval",
    ]

    def __init__(self, *, skill_registry: SkillRegistry, **ports):
        super().__init__(role_id=self.ROLE_ID, **ports)
        # Store registry for execution routing
        self._skill_registry = skill_registry
        # Load skill instances for task-type matching (allowlist)
        # DEFAULT_SKILLS acts as allowlist; execution routes through registry
        self._skills = {s.SKILL_ID: s for s in skill_registry.load_skills(self.DEFAULT_SKILLS)}

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        # Convert envelope to skill inputs (task-type specific mapping)
        inputs = self._map_task_to_inputs(envelope)
        skill_id = self._select_skill_id(envelope.task_type)

        # Build context and execute via registry
        ctx = SkillContext.from_ports(self._ports, task_id=envelope.task_id)
        outputs = await self._skill_registry.execute(skill_id, inputs, ctx)

        return TaskResult(
            task_id=envelope.task_id,
            status="completed",
            outputs=tuple(outputs.items()),
        )

    def _select_skill_id(self, task_type: str) -> str:
        for skill_id, skill in self._skills.items():
            if task_type in skill.SUPPORTED_TASK_TYPES:
                return skill_id
        raise SkillNotFoundError(f"No skill handles task type: {task_type}")

    def _map_task_to_inputs(self, envelope: TaskEnvelope) -> dict:
        """Convert TaskEnvelope to skill-specific inputs dict."""
        return dict(envelope.inputs)
```

### 3.3 DevAgent

```python
# src/squadops/agents/roles/dev.py
class DevAgent(BaseAgent):
    """Developer agent for code generation and implementation."""

    ROLE_ID = "dev"
    DEFAULT_SKILLS = [
        "code_generation",
        "code_modification",
        "test_writing",
        "bug_fixing",
        "refactoring",
    ]
```

### 3.4 Mock Agents (Defer)

The 5 mock agents (audit, comms, creative, curator, devops, finance) are NOT migrated in 0.8.8. They remain as stubs or are removed entirely.

### 3.5 Tests - Phase 3

```
tests/unit/agents/roles/
├── __init__.py
├── test_lead_agent.py
├── test_dev_agent.py
├── test_qa_agent.py
├── test_strat_agent.py
├── test_data_agent.py

tests/integration/agents/
├── test_lead_integration.py   # With real LLM
├── test_dev_integration.py    # With real filesystem
```

### 3.6 Golden Path Gate A: Routing & Wiring (Required)

**Gate**: Do not proceed to Phase 4 (Skills) until this gate passes.

**ExecutionMode**: `mock` acceptable (skill stubs return fixture data with `implementation="mock"`)

Validate the routing and wiring layer without full capability execution:
1. Runtime API receives task → validated DTO → mapped internal model
2. AgentOrchestrator routes to agent/role
3. Agent receives task and selects appropriate skill ID
4. SkillContext is constructed from PortsBundle
5. Skill stub returns mock output with `ExecutionEvidence(implementation="mock")`
6. TaskResult is returned via API (report labeled `[MOCK]`)

This gate validates the **plumbing** (routing, DI, context building) before building out all skills and capabilities.

**Polling Strategy (Required for CI stability)**:
- Use bounded polling on `GET /tasks/{id}` until terminal status or timeout
- Constants:
  - `POLL_INTERVAL_SECONDS = 0.2`
  - `MAX_WAIT_SECONDS = 10`
  - `MAX_ATTEMPTS = int(MAX_WAIT_SECONDS / POLL_INTERVAL_SECONDS)`
- On timeout, fail with diagnostics: last known status, last error, log pointer

```python
# tests/integration/test_golden_path_gate_a.py
import asyncio

POLL_INTERVAL_SECONDS = 0.2
MAX_WAIT_SECONDS = 10
MAX_ATTEMPTS = int(MAX_WAIT_SECONDS / POLL_INTERVAL_SECONDS)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_golden_path_gate_a_routing():
    """
    Gate A: Validate routing & wiring layer.

    API → Orchestrator → Agent → Skill selection → Context built → Mock response.
    Does NOT validate full skill/capability execution (that's Gate B).
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Submit task via API
        response = await client.post("/api/v1/tasks", json={
            "task_type": "analyze",
            "source_agent": "test",
            "target_agent": "lead",
            "inputs": {"description": "Test routing"}
        })
        assert response.status_code == 202
        task_id = response.json()["task_id"]

        # 2-4. Poll for response (skill stubs return quickly)
        last_status = None
        for attempt in range(MAX_ATTEMPTS):
            response = await client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200
            data = response.json()
            last_status = data.get("status")

            if last_status in {"completed", "failed"}:
                break
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        else:
            pytest.fail(f"Gate A timeout. Last status: {last_status}")

        # 5. Verify task was routed and processed
        assert last_status == "completed", f"Routing failed: {data.get('error')}"
        assert data.get("agent") == "lead", "Task not routed to correct agent"
```

---

## Phase 4: Skills (Atomic Operations Substrate)

Skills are atomic, reusable operations that capabilities orchestrate. Skills MUST NOT call capabilities or contain acceptance logic.

**Testability**: Skills are testable **without agents**. Unit tests construct a `SkillContext` with mocked ports and invoke `skill.execute(inputs, ctx)` directly. No agent instance is required for skill unit tests.

### 4.1 Skill Base

```python
# src/squadops/agents/skills/base.py
from abc import ABC, abstractmethod

class Skill(ABC):
    """Base class for agent skills - atomic operations without acceptance logic."""

    SKILL_ID: str
    SUPPORTED_TASK_TYPES: list[str]

    @abstractmethod
    async def execute(self, inputs: dict, context: SkillContext) -> dict:
        """Execute atomic operation. Returns outputs, NOT TaskResult."""
        ...
```

**Canonical Skill Signature (Normative)**:
- Skills MUST implement: `execute(inputs: dict, context: SkillContext) -> dict`
- Skills MUST NOT accept `TaskEnvelope` directly
- Skill outputs MUST include `_evidence: ExecutionEvidence`
- Skills MAY be nondeterministic (e.g., LLM calls), but MUST be observable (inputs/outputs logged via context if enabled) and bounded in side effects

**Key constraints:**
- Skills return raw outputs (dict), not TaskResult
- Skills MUST NOT call capabilities
- Skills MUST NOT contain "task complete" semantics
- Skills MUST NOT run acceptance checks

**Agent call pattern:**
```python
# Agents convert TaskEnvelope → inputs, build context, invoke via registry
inputs = map_task_to_inputs(envelope)  # task-type specific mapping
ctx = SkillContext.from_ports(self._ports, task_id=envelope.task_id)
result = await self._skill_registry.execute(skill_id, inputs, ctx)
```

**Capability call pattern:**
```python
# Capabilities invoke skills only via execution context
outputs = await context.skills.execute("skill_id", inputs)
# context.skills.execute() delegates to the same SkillRegistry/SkillContext mechanism
```

> This keeps skills reusable across agents and capabilities and avoids leaking transport/task envelope semantics into skills.

### 4.2 Shared Skills

```python
# src/squadops/agents/skills/shared/llm_query.py
class LLMQuerySkill(Skill):
    """Atomic skill: query LLM with prompt."""
    SKILL_ID = "llm_query"
    SUPPORTED_TASK_TYPES = ["query", "analyze", "generate"]

    async def execute(self, inputs: dict, context: SkillContext) -> dict:
        prompt = inputs["prompt"]
        response = await context.llm.chat([
            ChatMessage(role="user", content=prompt)
        ])
        return {"response": response.content}


# src/squadops/agents/skills/shared/file_write.py
class FileWriteSkill(Skill):
    """Atomic skill: write content to file."""
    SKILL_ID = "file_write"
    SUPPORTED_TASK_TYPES = ["write"]

    async def execute(self, inputs: dict, context: SkillContext) -> dict:
        path = Path(inputs["path"])
        content = inputs["content"]
        context.filesystem.write(path, content)
        return {"path": str(path), "bytes_written": len(content)}
```

### 4.3 Directory Structure

```
src/squadops/agents/skills/
├── __init__.py
├── base.py
├── context.py             # SkillContext (ports accessor)
├── registry.py
├── shared/
│   ├── __init__.py
│   ├── llm_query.py
│   ├── file_write.py
│   ├── file_read.py
│   ├── memory_store.py
│   ├── memory_recall.py
│   └── code_review.py
├── lead/
│   ├── __init__.py
│   └── task_breakdown.py
├── dev/
│   ├── __init__.py
│   ├── code_generation.py
│   └── test_generation.py
├── qa/
│   ├── __init__.py
│   └── test_execution.py
├── strat/
│   └── __init__.py
└── data/
    └── __init__.py
```

### 4.4 Tests - Phase 4

```
tests/unit/agents/skills/
├── __init__.py
├── test_skill_base.py
├── test_registry.py
├── shared/
│   ├── test_llm_query.py
│   ├── test_file_write.py
│   └── test_memory_skills.py
```

---

## Phase 5: Capabilities (Task-Level Deliverables)

Capabilities orchestrate skills to produce certified deliverables. Capabilities own acceptance checks and artifact production.

### 5.1 Capability System Overview

**Current**: 36 capability files (~7,400 LOC) in `_v0_legacy/agents/capabilities/`

**Categories**:
- **Governance** (5): task_coordination, approval, escalation, task_creator, task_delegator
- **Development** (4): build_artifact, docker_builder, docker_deployer, code_review
- **QA** (4): test_design, test_dev, test_execution, validation
- **Data** (4): analysis, modeling, collect_cycle_snapshot, profile_cycle_metrics
- **WarmBoot** (3): memory_handler, validator, wrapup_generator
- **Communications** (2): chat, documentation
- **Task Management** (4): completion_handler, completion_emitter, status_tracker, result_handler
- **Other** (10): telemetry, reasoning, prd_processor, etc.

### 5.2 CapabilityHandler Base

**Contract Injection (Required)**:
- The `CapabilityRegistry` binds: `CAPABILITY_ID` → `CapabilityContract` → `CapabilityHandler` factory
- When creating a handler instance, the registry MUST inject the contract via constructor:
  - `handler = Handler(contract=contract, ...)`
- Prefer constructor injection over global lookups to keep handlers testable and deterministic

```python
# src/squadops/capabilities/base.py
from abc import ABC, abstractmethod

class CapabilityHandler(ABC):
    """Base class for capability handlers aligned to SIP-0058 contracts.

    Capabilities:
    - Orchestrate skills to produce deliverables
    - Own acceptance checks (via AcceptanceCheckEngine)
    - Produce certified artifacts
    - Report completion status
    """

    CAPABILITY_ID: str  # Must match contract capability_id

    def __init__(self, contract: CapabilityContract):
        """Contract injected by registry - no global lookups."""
        self._contract = contract

    @abstractmethod
    async def execute(self, inputs: dict, context: ExecutionContext) -> CapabilityResult:
        """Execute capability, orchestrating skills and running acceptance checks."""
        ...

    def validate_inputs(self, inputs: dict) -> None:
        """Validate inputs against contract schema.

        NOTE: This MUST defer to the injected contract schema (InputSpec/ArtifactSpec)
        as the source of truth. Avoid ad hoc validation that duplicates or diverges
        from contract validation.
        """
        self._contract.validate_inputs(inputs)
```

```python
# src/squadops/capabilities/registry.py
class CapabilityRegistry:
    """Registry that binds contracts to handlers with injection."""

    def get_handler(self, capability_id: str) -> CapabilityHandler:
        contract = self._contracts[capability_id]
        handler_class = self._handlers[capability_id]
        return handler_class(contract=contract)  # Constructor injection
```

### 5.3 CapabilityDispatcher

```python
# src/squadops/capabilities/dispatcher.py
class CapabilityDispatcher:
    """Routes tasks to appropriate capability handlers."""

    def __init__(self, handlers: dict[str, CapabilityHandler]):
        self._handlers = handlers

    async def dispatch(self, capability_id: str, inputs: dict, context: ExecutionContext) -> CapabilityResult:
        if capability_id not in self._handlers:
            raise CapabilityNotFoundError(f"Unknown capability: {capability_id}")

        handler = self._handlers[capability_id]
        handler.validate_inputs(inputs)
        return await handler.execute(inputs, context)

    @classmethod
    def from_registry(cls, registry: CapabilityRegistry) -> "CapabilityDispatcher":
        """Create dispatcher from capability registry."""
        handlers = {cap_id: registry.get_handler(cap_id) for cap_id in registry.list()}
        return cls(handlers)
```

### 5.4 Example: Capability Orchestrating Skills

```python
# src/squadops/capabilities/handlers/data/collect_cycle_snapshot.py
class CollectCycleSnapshotHandler(CapabilityHandler):
    """
    Capability: data.collect_cycle_snapshot
    Orchestrates skills to collect and persist cycle data.
    """

    CAPABILITY_ID = "data.collect_cycle_snapshot"

    async def execute(self, inputs: dict, context: ExecutionContext) -> CapabilityResult:
        cycle_id = inputs["cycle_id"]

        # 1. Orchestrate skills (atomic operations)
        metrics = await context.skills.execute("metrics_collect", {"cycle_id": cycle_id})
        tasks = await context.skills.execute("task_list", {"cycle_id": cycle_id})
        summary = await context.skills.execute("llm_query", {
            "prompt": f"Summarize cycle {cycle_id}: {metrics}, {tasks}"
        })

        # 2. Produce artifact
        snapshot = {"metrics": metrics, "tasks": tasks, "summary": summary["response"]}
        artifact_path = f"runs/{cycle_id}/capabilities/{self.CAPABILITY_ID}/snapshot.json"
        await context.skills.execute("file_write", {"path": artifact_path, "content": json.dumps(snapshot)})

        # 3. Run acceptance checks (capability owns this)
        acceptance = await context.acceptance_engine.check(self.CAPABILITY_ID, {
            "artifact_path": artifact_path,
            "expected_keys": ["metrics", "tasks", "summary"]
        })

        # 4. Return certified result
        return CapabilityResult(
            capability_id=self.CAPABILITY_ID,
            status="completed" if acceptance.passed else "failed",
            artifacts=[artifact_path],
            acceptance_report=acceptance,
        )
```

### 5.5 Directory Structure

```
src/squadops/capabilities/
├── __init__.py
├── base.py                # CapabilityHandler ABC
├── result.py              # CapabilityResult (with evidence, mock_components)
├── dispatcher.py          # CapabilityDispatcher (routing + validation only)
├── runner.py              # WorkloadRunner (evidence aggregation + enforcement)
├── registry.py            # CapabilityRegistry
├── context.py             # ExecutionContext, SkillExecutor (evidence collector)
├── handlers/
│   ├── __init__.py
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── task_coordination.py
│   │   ├── approval.py
│   │   ├── escalation.py
│   │   ├── task_creator.py
│   │   └── task_delegator.py
│   ├── development/
│   │   ├── __init__.py
│   │   ├── build_artifact.py
│   │   ├── docker_builder.py
│   │   └── code_review.py
│   ├── qa/
│   │   ├── __init__.py
│   │   ├── test_design.py
│   │   ├── test_execution.py
│   │   └── validation.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── collect_cycle_snapshot.py
│   │   ├── profile_cycle_metrics.py
│   │   └── compose_cycle_summary.py
│   └── warmboot/
│       ├── __init__.py
│       ├── memory_handler.py
│       ├── validator.py
│       └── wrapup_generator.py
└── manifests/             # From SIP-0058
    ├── schemas/
    ├── contracts/
    └── workloads/
```

### 5.6 Tests - Phase 5

```
tests/unit/capabilities/
├── __init__.py
├── test_dispatcher.py
├── test_registry.py
├── handlers/
│   ├── test_governance.py
│   ├── test_development.py
│   ├── test_qa.py
│   ├── test_data.py
│   └── test_warmboot.py
```

### 5.7 Golden Path Gate B: Full Architecture Validation (Required)

**Gate**: Do not proceed to Phase 6 (API & Orchestration) until this gate passes.

**ExecutionMode**: `real` **required** — test MUST fail if any component returns `implementation="mock"`

Validate the complete execution path including skill execution, capability orchestration, and acceptance checks:

1. Runtime API receives task → validated DTO → mapped internal model
2. AgentOrchestrator routes to agent/role
3. Agent invokes capability handler
4. Capability orchestrates real skills to produce artifacts
5. WorkloadRunner runs acceptance checks via AcceptanceCheckEngine
6. TaskResult + run report available via API status/query

**Polling Strategy (Required for CI stability)**:
- Use bounded polling on `GET /tasks/{id}` until terminal status or timeout
- Constants:
  - `POLL_INTERVAL_SECONDS = 0.2`
  - `MAX_WAIT_SECONDS = 30` (longer than Gate A - full execution)
  - `MAX_ATTEMPTS = int(MAX_WAIT_SECONDS / POLL_INTERVAL_SECONDS)`
- On timeout, fail with diagnostics: last known status, last error, log pointer

```python
# tests/integration/test_golden_path_gate_b.py
import asyncio
import os

POLL_INTERVAL_SECONDS = 0.2
MAX_WAIT_SECONDS = 30
MAX_ATTEMPTS = int(MAX_WAIT_SECONDS / POLL_INTERVAL_SECONDS)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_golden_path_gate_b_full_architecture():
    """
    Gate B: Full architecture validation with REAL execution mode.

    API → Orchestrator → Agent → Capability → Skills → Acceptance → Result.
    This test validates the complete execution path with real skill execution.
    Any mock component will cause immediate failure.
    """
    # REQUIRED: Set execution mode to real - mocks will hard-fail
    os.environ["SQUADOPS_EXECUTION_MODE"] = "real"

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Submit task via API
        response = await client.post("/api/v1/tasks", json={
            "task_type": "analyze",
            "source_agent": "test",
            "target_agent": "lead",
            "inputs": {"description": "Analyze the test coverage"}
        })
        assert response.status_code == 202
        task_id = response.json()["task_id"]

        # 2-5. Poll for completion with bounded retries
        last_status = None
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            response = await client.get(f"/api/v1/tasks/{task_id}")
            assert response.status_code == 200
            data = response.json()
            last_status = data.get("status")
            last_error = data.get("error")

            if last_status in {"completed", "failed"}:
                break
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        else:
            pytest.fail(
                f"Gate B timeout after {MAX_WAIT_SECONDS}s. "
                f"Last status: {last_status}, Last error: {last_error}"
            )

        # 6. Verify success with acceptance evidence
        assert last_status == "completed", f"Expected completed, got {last_status}: {last_error}"
        assert "acceptance_report" in data or "artifacts" in data, "Missing acceptance evidence"

        # 7. Verify execution mode is real (hardened assertions)
        assert data.get("execution_mode") == "real", (
            f"Gate B requires execution_mode=real, got: {data.get('execution_mode')}"
        )

        # 8. Verify no mock components
        assert data.get("mock_components") == [], (
            f"Gate B requires no mock components, got: {data.get('mock_components')}"
        )

        # 9. Verify execution evidence shows real implementation
        evidence = data.get("execution_evidence", {})
        assert evidence.get("implementation") == "real", (
            f"Gate B requires real implementation, got: {evidence}"
        )
```

---

## Phase 6: API & Orchestration

### 6.1 Runtime API Migration

**Current**: `_v0_legacy/infra/runtime-api/main.py` (928 LOC)

**Target**: `src/squadops/api/`

```
src/squadops/api/
├── __init__.py
├── app.py                 # FastAPI application
├── deps.py                # Dependency injection
├── routes/
│   ├── __init__.py
│   ├── tasks.py           # Task CRUD endpoints
│   ├── cycles.py          # Cycle management
│   ├── agents.py          # Agent status
│   └── health.py          # Health endpoints
└── middleware/
    ├── __init__.py
    ├── telemetry.py       # Request tracing
    └── error_handler.py   # Global error handling
```

### 6.2 Dependency Injection

```python
# src/squadops/api/deps.py
from functools import lru_cache
from adapters.llm import create_llm_provider
from adapters.memory import create_memory_provider
# ... other imports

@lru_cache
def get_agent_factory() -> AgentFactory:
    """Singleton AgentFactory with all ports."""
    return AgentFactory(
        llm=create_llm_provider(),
        memory=create_memory_provider(),
        filesystem=create_filesystem_provider(),
        metrics=create_metrics_provider(),
        events=create_event_provider(),
        queue=create_queue_provider(),
        prompt_service=PromptService(create_prompt_repository()),
        skill_registry=SkillRegistry.discover(),
    )

def get_lead_agent() -> LeadAgent:
    return get_agent_factory().create("lead")
```

### 6.3 AgentOrchestrator

```python
# src/squadops/orchestration/orchestrator.py
class AgentOrchestrator:
    """Coordinates agent lifecycle and task distribution."""

    def __init__(
        self,
        factory: AgentFactory,
        queue: QueuePort,
        events: EventPort,
    ):
        self._factory = factory
        self._queue = queue
        self._events = events
        self._agents: dict[str, BaseAgent] = {}

    async def start_agent(self, role_id: str, agent_id: str | None = None) -> str:
        agent = self._factory.create(role_id, agent_id)
        await agent.on_agent_start()
        self._agents[agent.agent_id] = agent
        return agent.agent_id

    async def stop_agent(self, agent_id: str) -> None:
        agent = self._agents.pop(agent_id)
        await agent.on_agent_stop()

    async def dispatch_task(self, envelope: TaskEnvelope) -> None:
        await self._queue.publish(envelope.target_agent, envelope)
```

### 6.4 Health Check Migration

**Current**: `_v0_legacy/infra/health-check/` with HTML dashboard

**Target**: Integrate into `src/squadops/api/routes/health.py`

```python
# src/squadops/api/routes/health.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/", response_class=HTMLResponse)
async def health_dashboard():
    """Render health dashboard HTML."""
    ...

@router.get("/infra")
async def infrastructure_health():
    """Check infrastructure services (Postgres, RabbitMQ, Redis)."""
    ...

@router.get("/agents")
async def agent_health():
    """Check agent status."""
    ...
```

---

## Phase 7: Config & Cleanup

### 7.1 Move Non-Python Configs

```bash
# Move from _v0_legacy/infra/ to root infra/
mv _v0_legacy/infra/grafana infra/
mv _v0_legacy/infra/otel-collector infra/
mv _v0_legacy/infra/prometheus infra/
mv _v0_legacy/infra/migrations infra/
mv _v0_legacy/infra/init.sql infra/
mv _v0_legacy/infra/config.env infra/
```

### 7.2 Update docker-compose.yml

Update volume mounts from `_v0_legacy/infra/` to `infra/`:
```yaml
# Before
volumes:
  - ./_v0_legacy/infra/init.sql:/docker-entrypoint-initdb.d/init.sql

# After
volumes:
  - ./infra/init.sql:/docker-entrypoint-initdb.d/init.sql
```

### 7.3 Delete _v0_legacy/

**Pre-deletion checklist**:
- [ ] All imports updated to new paths
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] CI green for 3 consecutive runs
- [ ] Agent containers build and run
- [ ] check_legacy_imports.py finds zero violations

```bash
rm -rf _v0_legacy/
```

### 7.4 Version Bump

```bash
export SQUADOPS_MAINTAINER=1
python scripts/maintainer/update_sip_status.py sips/proposals/SIP-Agent-Migration-0-8-8.md implemented
python scripts/maintainer/version_cli.py bump 0.8.8 "SIP-XXXX: Agent Migration & Legacy Retirement"
```

---

## Design Decisions

### Decision #1 — Skills vs Capabilities (Normative)

**Architectural Model**:
- **Roles/Agents invoke Capabilities.**
- **Capabilities orchestrate Skills.**
- **Capabilities SHOULD compose Skills, not re-implement primitives.** If a capability needs an operation that could be reusable (LLM query, file write, memory store), factor it out as a Skill.
- **Skills MUST NOT call Capabilities.**
- **Skills MUST NOT contain acceptance logic or "task complete" semantics.**
- **Capabilities own certification**: artifacts, acceptance checks, reporting, rollback.
- **Acceptance checks run at the capability boundary** (WorkloadRunner + AcceptanceCheckEngine), not inside skills.

**Rule of thumb:** If it can be accepted/validated/certified/reported as "complete," it is a **Capability**, not a **Skill**.

### Decision #2 - Mock Agent Disposition

**Question**: What happens to the 6 mock agents?

**Answer**: Mock agents (audit, comms, creative, curator, devops, finance) are NOT migrated in 0.8.8. They will be **removed** from the codebase, with references cleaned and any remaining usage replaced by contract-driven test harnesses. If needed in future, they can be created fresh following the new patterns.

### Decision #3 - Configuration System

**Question**: Use existing `_v0_legacy/infra/config/` or create new?

**Answer**: Migrate the existing config system to `src/squadops/config/`. The Pydantic schemas and loader are well-designed. InfraConfig (from SIP-0.8.7) becomes a typed view over UnifiedConfig.

### Decision #4 - Dockerfile Generation

**Question**: What happens to `docker_generator.py`?

**Answer**: Migrate to `scripts/dev/docker_generator.py` as a dev tool. It's not runtime code.

### Decision #5 - Prefect Adapter

**Question**: How is Prefect integrated?

**Answer**: Prefect is the primary task orchestration backend for SquadOps. The adapter pattern allows selecting between `sql` or `prefect` via configuration, but Prefect is the production choice. PrefectTaskAdapter must be fully implemented (replacing the 0.8.7 stub). SQLTaskAdapter remains available as an alternative for simpler deployments or testing without Prefect infrastructure.

### Decision #6 - ExecutionMode & No Silent Mocks (Normative)

**Problem**: During phased migration, mock stubs can silently pass tests while providing false confidence. Mocks masquerading as real functionality is a critical risk.

**Solution**: Explicit execution mode with hard-fail semantics.

**ExecutionMode**:
- `SQUADOPS_EXECUTION_MODE` ∈ `{mock, real}`
- Default: `mock` (dev + early phases)
- Gate A: `mock` mode acceptable (routing/wiring validation)
- Gate B: `real` mode **required** (full architecture validation)
- Phase 7: `real` mode everywhere; `mock` mode only for isolated unit tests

**Hard Rules**:
1. In `real` mode: the run MUST fail immediately upon detection of any mock evidence. Specifically:
   - `ExecutionContext.skills.execute()` raises `MockInRealModeError` as soon as `_evidence.implementation == "mock"`
   - `WorkloadRunner._aggregate_evidence()` provides defense-in-depth final check
2. In `mock` mode: execution may proceed, but run reports MUST be labeled as `[MOCK]` and enumerate mock components.

**Aggregation Rule**:
- If any child component is `mock` → parent is `mock`
- A capability orchestrating 5 skills where 1 is mock → capability result is `implementation="mock"`

**ExecutionEvidence Model**:

```python
# src/squadops/execution/models.py
from dataclasses import dataclass
from enum import Enum
from typing import Literal

class ExecutionMode(str, Enum):
    MOCK = "mock"
    REAL = "real"

Implementation = Literal["mock", "real"]
EvidenceLevel = Literal["none", "synthetic", "real"]

@dataclass(frozen=True)
class ExecutionEvidence:
    """Metadata proving what actually executed."""
    implementation: Implementation  # "mock" or "real"
    evidence_level: EvidenceLevel   # Quality of output evidence
    limitations: tuple[str, ...] = ()  # Known constraints

# EvidenceLevel definitions:
# - "none": No output/artifact produced (pure side-effect or stub)
# - "synthetic": Deterministic fixture data (structured correctly but not from real execution)
# - "real": Produced by actual component execution (LLM call, file write, etc.)
```

**Evidence Location (Normative)**:

Evidence MUST be wired into result types at specific locations:

1. **Skill outputs** MUST include `_evidence: ExecutionEvidence`:
```python
# Skill output (real)
return {
    "analysis": response.content,
    "_evidence": ExecutionEvidence(implementation="real", evidence_level="real"),
}

# Skill output (mock, during development)
return {
    "analysis": "placeholder",
    "_evidence": ExecutionEvidence(
        implementation="mock",
        evidence_level="synthetic",
        limitations=("LLM not connected", "returns fixture data"),
    ),
}
```

2. **CapabilityResult** MUST include:
```python
@dataclass(frozen=True)
class CapabilityResult:
    capability_id: str
    status: str
    artifacts: tuple[str, ...]
    acceptance_report: AcceptanceReport
    evidence: ExecutionEvidence  # Aggregated from skills
    mock_components: tuple[str, ...] = ()  # e.g., ("skill:llm_query", "skill:file_write")
```

3. **Task status API responses** MUST include:
```python
{
    "task_id": "...",
    "status": "completed",
    "execution_mode": "real",  # From SQUADOPS_EXECUTION_MODE
    "execution_evidence": {"implementation": "real", "evidence_level": "real"},
    "mock_components": [],  # Empty in real mode (or hard-fail)
    ...
}
```

**Single Enforcement Boundary (Normative)**:

- ExecutionMode enforcement MUST occur in `WorkloadRunner.run()`, NOT in Dispatcher.
- `CapabilityDispatcher` remains responsible for routing + input validation only.
- This ensures a single point of enforcement and cleaner separation of concerns.

**Skill Evidence Aggregation Mechanism (Normative)**:

Evidence aggregation uses a **runner-level collector via ExecutionContext.skills**:

1. `ExecutionContext.skills.execute(skill_id, inputs)` MUST:
   - Call `SkillRegistry.execute(skill_id, inputs, skill_context)`
   - Require returned dict includes `_evidence: ExecutionEvidence`
   - Append `(skill_id, evidence)` to a runner-owned collector
   - Optionally: in `real` mode, fail immediately upon detection of mock evidence

2. `WorkloadRunner._aggregate_evidence()` MUST use the collector (not result.skill_results)

```python
# src/squadops/capabilities/context.py
@dataclass
class SkillExecutor:
    """Wrapper that collects evidence from skill invocations."""
    _registry: SkillRegistry
    _skill_context: SkillContext
    _execution_mode: ExecutionMode
    _evidence_collector: list[tuple[str, ExecutionEvidence]]  # Runner-owned

    async def execute(self, skill_id: str, inputs: dict) -> dict:
        """Execute skill and collect evidence."""
        result = await self._registry.execute(skill_id, inputs, self._skill_context)

        # Extract and validate evidence
        evidence = result.get("_evidence")
        if evidence is None:
            raise SkillContractViolation(f"Skill {skill_id} missing required _evidence")

        # Collect evidence for aggregation
        self._evidence_collector.append((skill_id, evidence))

        # Optional: fail immediately in real mode if mock detected
        if self._execution_mode == ExecutionMode.REAL and evidence.implementation == "mock":
            raise MockInRealModeError(
                f"Mock skill detected in REAL mode: skill:{skill_id}"
            )

        return result

# src/squadops/capabilities/runner.py
class WorkloadRunner:
    def __init__(self, execution_mode: ExecutionMode):
        self._execution_mode = execution_mode

    async def run(self, capability_id: str, inputs: dict, context: ExecutionContext) -> CapabilityResult:
        # 1. Create evidence collector for this run
        evidence_collector: list[tuple[str, ExecutionEvidence]] = []

        # 2. Inject collector into context.skills
        context = context.with_evidence_collector(evidence_collector, self._execution_mode)

        # 3. Dispatch to capability handler (skills append to collector during execution)
        result = await self._dispatcher.dispatch(capability_id, inputs, context)

        # 4. Aggregate evidence from collector
        aggregated_evidence, mock_components = self._aggregate_evidence(
            evidence_collector, result.capability_id, result.evidence
        )

        # 5. Final enforcement (redundant if SkillExecutor already checks, but defense-in-depth)
        if self._execution_mode == ExecutionMode.REAL and mock_components:
            raise MockInRealModeError(
                f"Mock components detected in REAL mode: {mock_components}"
            )

        # 6. Return result with aggregated evidence
        return CapabilityResult(
            capability_id=result.capability_id,
            status=result.status,
            artifacts=result.artifacts,
            acceptance_report=result.acceptance_report,
            evidence=aggregated_evidence,
            mock_components=mock_components,
        )

    def _aggregate_evidence(
        self,
        collector: list[tuple[str, ExecutionEvidence]],
        capability_id: str,
        capability_evidence: ExecutionEvidence,
    ) -> tuple[ExecutionEvidence, tuple[str, ...]]:
        """Aggregate evidence from collector.

        Aggregation rule: if ANY skill is mock → capability is mock.
        """
        mock_components: list[str] = []

        for skill_id, evidence in collector:
            if evidence.implementation == "mock":
                mock_components.append(f"skill:{skill_id}")

        if capability_evidence.implementation == "mock":
            mock_components.append(f"capability:{capability_id}")

        # Aggregated implementation: mock if any component is mock
        aggregated_impl: Implementation = "mock" if mock_components else "real"

        return (
            ExecutionEvidence(implementation=aggregated_impl, evidence_level=capability_evidence.evidence_level),
            tuple(mock_components),
        )
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Large codebase migration | Phase incrementally; validate each phase before proceeding |
| Breaking existing tests | Run full test suite after each phase |
| Missing capability handlers | Map all 36 handlers before starting Phase 4 |
| Configuration drift | InfraConfig wraps UnifiedConfig; unit test enforces coverage |
| Docker build failures | Test container builds after Phase 3 |
| Import cycles | check_legacy_imports.py enforced in CI |
| Prefect API changes | Pin Prefect version; integration tests verify adapter |
| Lost functionality | Integration tests verify end-to-end flows |
| Silent mock masquerading | ExecutionMode enforcement; Gate B requires `real` mode; `MockInRealModeError` hard-fails |

---

## File Count Summary

| Phase | New Files | Modified Files | Deleted Files |
|-------|-----------|----------------|---------------|
| Phase 1 | 12 | 5 | 1 |
| Phase 2 | 15 | 0 | 0 |
| Phase 3 | 10 | 0 | 15 |
| Phase 4 (Skills) | 20 | 0 | 15 |
| Phase 5 (Capabilities) | 40 | 0 | 36 |
| Phase 6 | 15 | 2 | 10 |
| Phase 7 | 0 | 5 | ~50 |
| **Total** | **~112** | **~12** | **~127** |

---

## Verification

```bash
# Phase 1
pytest tests/unit/embeddings tests/unit/tasks tests/unit/api/test_dto_mapping.py -v
pytest tests/integration/memory/test_embeddings_e2e.py -v  # Gate: must pass before removing embed_fn seam

# Phase 2
pytest tests/unit/agents -v

# Phase 3
pytest tests/unit/agents/roles -v
pytest tests/integration/agents -v
pytest tests/integration/test_golden_path_gate_a.py -v  # Gate A: routing & wiring validated

# Phase 4 (Skills)
pytest tests/unit/agents/skills -v

# Phase 5 (Capabilities)
pytest tests/unit/capabilities -v
pytest tests/integration/test_golden_path_gate_b.py -v  # Gate B: full architecture validated

# Phase 6
pytest tests/unit/api tests/unit/orchestration -v

# Phase 7 (Final)
python scripts/ci/check_legacy_imports.py
pytest tests/ -v --cov=src/squadops --cov=adapters
```

---

## SIP Lifecycle

1. **Now**: SIP exists in `sips/proposals/SIP-Agent-Migration-0-8-8.md`
2. **After Phase 3**: Promote to accepted
3. **After Phase 7**: Promote to implemented, bump version to 0.8.8

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-31 | Initial draft |
| 2026-01-31 | Rev 2: Applied patch block - Skills vs Capabilities normative model (capabilities orchestrate skills); swapped Phase 4/5 order; added API DTO mapping requirement; added Memory+Embeddings E2E gate; added Prefect config selector; added Golden Path gate; added contract-first validation note |
| 2026-01-31 | Rev 3: Normalized Skill API (single canonical signature, agent/capability call patterns); fixed Memory+Embeddings E2E test assertions (metric-agnostic); added deterministic polling strategy to Golden Path test; clarified contract injection into capability handlers |
| 2026-01-31 | Rev 3.1: Added PortsBundle to BaseAgent for context building; fixed LeadAgent to store skill_registry; added SkillRegistry.execute() method; clarified self._skills as allowlist for task-type matching |
| 2026-01-31 | Rev 4: Split Golden Path into Gate A (routing/wiring, Phase 3) and Gate B (full architecture, Phase 5); fixed missing await in agent call pattern; added normative rule: Capabilities SHOULD compose Skills; clarified Skills testable without agents; added pkgutil/importlib discovery convention |
| 2026-01-31 | Rev 4.1: Added Decision #6 "ExecutionMode & No Silent Mocks" with ExecutionEvidence model, aggregation rules, enforcement location; Gate A allows mock mode, Gate B requires real mode; added MockInRealModeError hard-fail semantics |
| 2026-01-31 | Rev 4.2: Wired ExecutionEvidence into result types (Skill `_evidence`, CapabilityResult `evidence` + `mock_components`, API response fields); single enforcement boundary at WorkloadRunner (not Dispatcher); added WorkloadRunner._aggregate_evidence(); hardened Gate B assertions (execution_mode, mock_components, execution_evidence) |
| 2026-01-31 | Rev 4.3: Resolved skill evidence aggregation via runner-level collector (SkillExecutor wraps registry, appends to collector); clarified immediate failure semantics (fail at point of detection in SkillExecutor, defense-in-depth in WorkloadRunner); made `_evidence` required in Canonical Skill Signature |
