---
sip_uid: 01KG66J4NK2SW0MYMEVXX2HN8Y
sip_number: 60
title: Agent Migration — Hexagonal Application Layer & Legacy Retirement
status: implemented
author: Framework Committee
approver: null
created_at: '2026-01-29T00:00:00Z'
updated_at: '2026-02-01T09:46:27.764693Z'
original_filename: SIP-Agent-Migration-0-8-8.md
---

> **Historical Note (2026-03-06 audit):** This SIP is a migration guide written in future tense.
> The migration it describes has been completed — agents are implemented in `src/squadops/agents/`
> following hexagonal patterns and the legacy `_v0_legacy/` code has been retired.
> This document is retained for historical reference only.

# SIP-AGENT-MIGRATION-0_8_8 — Version Target 0.8.8
## Agent Migration — Hexagonal Application Layer & Legacy Retirement

**Status:** Proposed
**Target Version:** 0.8.8
**Author:** Framework Committee
**Depends On:** SIP-0056, SIP-0057, SIP-0058, SIP-0.8.7 (Infrastructure Ports)

---

# 1. Purpose and Intent

This SIP completes the hexagonal architecture migration by moving all **agent implementations** from `_v0_legacy/` to the new structure. Upon completion, the `_v0_legacy/` directory will be **deleted entirely**.

The intent is to:
- Migrate all agent roles to depend exclusively on ports defined in SIP-0.8.7,
- Migrate skill implementations to the new structure,
- Migrate capability handlers to align with SIP-0058 contracts,
- Migrate the Runtime API to hexagonal patterns,
- **Retire `_v0_legacy/`** — marking the completion of the 0.8.x architecture transition.

This SIP represents the **final migration milestone** before SquadOps 0.9.x, which will focus on observability, benchmarking, and production hardening.

---

# 2. Background

The 0.8.x series has systematically migrated SquadOps to hexagonal architecture:

| Version | SIP | Layer | Status |
|---------|-----|-------|--------|
| 0.8.4 | SIP-0056 | Queue Transport | ✅ Implemented |
| 0.8.5 | SIP-0057 | Layered Prompts | ✅ Implemented |
| 0.8.6 | SIP-0058 | Capability Contracts | Proposed |
| 0.8.7 | SIP-0.8.7 | Infrastructure Ports | Proposed |
| **0.8.8** | **This SIP** | **Agent Migration** | **Proposed** |

After SIP-0.8.7, the following remains in `_v0_legacy/`:

| Area | Files | Description |
|------|-------|-------------|
| `agents/roles/` | 15 | Agent role implementations (Lead, Dev, QA, etc.) |
| `agents/skills/` | 15 | Skill implementations per role |
| `agents/capabilities/` | 36 | Capability handlers |
| `agents/factory/` | 3 | Agent instantiation factory |
| `agents/context/` | 2 | Pulse/cycle context management |
| `agents/specs/` | 4 | Agent specifications |
| `agents/utils/` | 5 | Shared utilities |
| `agents/base_agent.py` | 1 | Legacy base agent class |
| `agents/cycle_data/` | 2 | Cycle data management |
| `agents/instances/` | 1 | Agent instance tracking |
| `agents/templates/` | 3 | Legacy templates |
| `infra/runtime-api/` | 3 | Runtime API (FastAPI) |
| `infra/health-check/` | 2 | Health check service |
| `infra/config/` | 6 | Configuration loading |
| `config/` | 2 | Version and agent config |
| `infra/grafana/` | — | Dashboards (non-Python, move only) |
| `infra/otel-collector/` | — | OTel config (non-Python, move only) |
| `infra/prometheus/` | — | Prometheus config (non-Python, move only) |
| `infra/migrations/` | — | SQL migrations (non-Python, move only) |

**Total: ~100 files** to migrate or retire, plus non-Python configs to relocate.

---

# 3. Problem Statements

1. **Split Codebase:** Agent implementations span both `_v0_legacy/` and `src/squadops/`, creating confusion and import complexity.
2. **Legacy Dependencies:** Agents still import directly from legacy paths instead of using ports.
3. **Inconsistent Patterns:** Different agents follow different patterns; no unified structure.
4. **Runtime API Coupling:** The Runtime API is tightly coupled to legacy agent implementations.
5. **Technical Debt:** Maintaining two parallel structures increases maintenance burden.

---

# 4. Scope

## In Scope
- Migrate all agent role implementations to `src/squadops/agents/roles/`.
- Migrate all skill implementations to `src/squadops/agents/skills/`.
- Migrate capability handlers to `src/squadops/capabilities/handlers/` (aligned to SIP-0058).
- Migrate Runtime API to `src/squadops/api/`.
- Migrate health-check service to `src/squadops/api/` or dedicated health module.
- Migrate `agents/cycle_data/` to `src/squadops/orchestration/`.
- Migrate `agents/instances/` or retire if unused.
- Migrate `agents/templates/` to prompt system or inline.
- Update agent factory to use dependency injection with ports.
- Move non-Python infra configs (`grafana/`, `otel-collector/`, `prometheus/`, `migrations/`) to root-level `infra/` directory.
- Delete `_v0_legacy/` directory entirely.

### 0.8.7 Deferral Pickup (Infrastructure Completion)

The following items were explicitly deferred from SIP-0.8.7 to this SIP:

1. **EmbeddingsPort**: SIP-0.8.7 introduced an `embed_fn` callable seam in `LanceDBAdapter`. This SIP introduces a proper `EmbeddingsPort` in `src/squadops/ports/embeddings/` and injects it into memory adapters, replacing the seam.

2. **PrefectTaskAdapter**: SIP-0.8.7 provides a stub that raises `NotImplementedError`. This SIP implements the full Prefect adapter in `adapters/tasks/prefect.py`.

3. **TaskEnvelope/TaskResult Migration**: SIP-0.8.7 uses a compatibility bridge (`squadops.tasks.types`) re-exporting Pydantic models from `_v0_legacy`. This SIP migrates `TaskEnvelope`, `TaskResult`, `TaskState`, and `FlowState` to frozen dataclasses in `src/squadops/tasks/models.py` and removes the bridge.

## Not Addressed
- New agent roles or capabilities (feature freeze during migration).
- Performance optimization (deferred to 0.9.x).
- New observability features (deferred to 0.9.x).
- New LLM providers (Anthropic, OpenAI) — deferred to 0.9.x unless explicitly requested.

---

# 5. Strategic Domain Design (DDD)

## 5.1 Bounded Context: Agent Execution

- **Aggregate Root:** `Agent` — The runtime agent instance managing lifecycle and task execution.
- **Entity:** `AgentRole` — Configuration defining an agent's identity, capabilities, and prompts.
- **Entity:** `Skill` — A composable unit of agent behavior.
- **Value Object:** `AgentContext` — Immutable snapshot of cycle/pulse state.
- **Domain Service:** `AgentFactory` — Stateless factory for agent instantiation with DI.
- **Domain Service:** `SkillRegistry` — Discovery and loading of available skills.

## 5.2 Bounded Context: Capability Execution

- **Entity:** `CapabilityHandler` — Implementation of a capability contract.
- **Domain Service:** `CapabilityDispatcher` — Routes tasks to appropriate handlers.

## 5.3 Bounded Context: Runtime API

- **Application Service:** `RuntimeAPI` — HTTP interface for task submission and status.
- **Application Service:** `AgentOrchestrator` — Coordinates agent lifecycle and task distribution.

## 5.4 Core Principles

1. **Agents are composable.** Roles combine skills; skills combine capabilities.
2. **All I/O flows through ports.** No agent code directly accesses LLM, files, memory, or queues.
3. **Configuration over code.** Agent behavior is driven by role configuration, not hardcoded logic.

---

# 6. Technical Architecture (Hexagonal)

## 6.1 Final Directory Structure

```
src/squadops/
├── agents/                        # Agent domain
│   ├── __init__.py
│   ├── models.py                  # Agent, AgentRole, AgentContext
│   ├── exceptions.py              # AgentError, SkillNotFoundError
│   ├── factory.py                 # AgentFactory domain service
│   ├── base.py                    # BaseAgent (refactored from execution/agent.py)
│   ├── roles/                     # Role implementations
│   │   ├── __init__.py
│   │   ├── lead.py                # LeadAgent
│   │   ├── dev.py                 # DevAgent
│   │   ├── qa.py                  # QAAgent
│   │   ├── strat.py               # StratAgent
│   │   ├── data.py                # DataAgent
│   │   └── ...
│   └── skills/                    # Skill implementations
│       ├── __init__.py
│       ├── registry.py            # SkillRegistry
│       ├── shared/                # Cross-role skills
│       │   ├── task_analysis.py
│       │   ├── code_review.py
│       │   └── ...
│       ├── lead/                  # Lead-specific skills
│       ├── dev/                   # Dev-specific skills
│       └── ...
│
├── capabilities/                  # Capability domain (SIP-0058)
│   ├── __init__.py
│   ├── models.py                  # From SIP-0058
│   ├── exceptions.py
│   ├── runner.py                  # WorkloadRunner
│   ├── acceptance.py              # AcceptanceCheckEngine
│   ├── dispatcher.py              # CapabilityDispatcher (NEW)
│   ├── handlers/                  # Capability implementations
│   │   ├── __init__.py
│   │   ├── data/
│   │   │   ├── collect_cycle_snapshot.py
│   │   │   ├── profile_cycle_metrics.py
│   │   │   └── compose_cycle_summary.py
│   │   ├── delivery/
│   │   ├── ops/
│   │   └── product/
│   └── manifests/                 # From SIP-0058
│       ├── schemas/
│       ├── contracts/
│       └── workloads/
│
├── api/                           # Runtime API
│   ├── __init__.py
│   ├── app.py                     # FastAPI application
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── tasks.py               # Task submission endpoints
│   │   ├── agents.py              # Agent status endpoints
│   │   ├── health.py              # Health check endpoints
│   │   └── cycles.py              # Cycle management endpoints
│   ├── deps.py                    # Dependency injection
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py
│       └── telemetry.py
│
├── orchestration/                 # Orchestration domain
│   ├── __init__.py
│   ├── models.py                  # Cycle, Pulse, Squad
│   ├── orchestrator.py            # AgentOrchestrator
│   └── scheduler.py               # Task scheduling logic
│
├── config/                        # Configuration domain
│   ├── __init__.py
│   ├── models.py                  # DeploymentProfile, AgentConfig
│   ├── loader.py                  # Config loading logic
│   └── profiles/                  # Deployment profiles
│       ├── local.yaml
│       ├── docker.yaml
│       └── production.yaml
│
├── core/                          # Existing core (secrets, etc.)
├── ports/                         # All port interfaces
│   ├── embeddings/                # NEW in 0.8.8: EmbeddingsPort
│   │   ├── __init__.py
│   │   └── provider.py            # EmbeddingsPort ABC
├── prompts/                       # SIP-0057
├── comms/                         # SIP-0056
└── ...

adapters/                          # All adapter implementations
├── llm/                           # SIP-0.8.7
├── tools/                         # SIP-0.8.7
├── memory/                        # SIP-0.8.7
├── telemetry/                     # SIP-0.8.7
├── tasks/                         # SIP-0.8.7 (PrefectAdapter completed in 0.8.8)
├── embeddings/                    # NEW in 0.8.8: EmbeddingsAdapter
│   ├── __init__.py
│   ├── ollama.py                  # OllamaEmbeddingsAdapter
│   └── factory.py
├── comms/                         # SIP-0056
├── prompts/                       # SIP-0057
├── capabilities/                  # SIP-0058
└── ...

infra/                             # Non-Python configs (moved from _v0_legacy/infra/)
├── grafana/                       # Dashboards and provisioning
├── otel-collector/                # OTel collector config
├── prometheus/                    # Prometheus config
└── migrations/                    # SQL migrations
```

## 6.2 Agent Composition Model

```
┌─────────────────────────────────────────────────────────┐
│                      AgentFactory                        │
│  (injects all ports via dependency injection)           │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      BaseAgent                           │
│  - LLMPort                                              │
│  - MemoryPort                                           │
│  - PromptService                                        │
│  - QueuePort                                            │
│  - MetricsPort                                          │
│  - EventPort                                            │
│  - FileSystemPort                                       │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │ LeadAgent │   │  DevAgent │   │  QAAgent  │
    │           │   │           │   │           │
    │ + skills  │   │ + skills  │   │ + skills  │
    └───────────┘   └───────────┘   └───────────┘
```

## 6.3 Agent Role Implementation Pattern

```python
# src/squadops/agents/roles/lead.py
from squadops.agents.base import BaseAgent
from squadops.agents.skills.registry import SkillRegistry

class LeadAgent(BaseAgent):
    """Lead agent responsible for task orchestration and delegation."""

    ROLE_ID = "lead"
    DEFAULT_SKILLS = [
        "task_analysis",
        "task_delegation",
        "code_review",
        "cycle_planning",
    ]

    def __init__(
        self,
        *,
        agent_id: str,
        llm: LLMPort,
        memory: MemoryPort,
        prompt_service: PromptService,
        queue: QueuePort,
        metrics: MetricsPort,
        events: EventPort,
        filesystem: FileSystemPort,
        skill_registry: SkillRegistry,
    ):
        super().__init__(
            agent_id=agent_id,
            role_id=self.ROLE_ID,
            llm=llm,
            memory=memory,
            prompt_service=prompt_service,
            queue=queue,
            metrics=metrics,
            events=events,
            filesystem=filesystem,
        )
        self._skills = skill_registry.load_skills(self.DEFAULT_SKILLS)

    async def handle_task(self, envelope: TaskEnvelope) -> TaskResult:
        """Route task to appropriate skill based on task_type."""
        skill = self._select_skill(envelope.task_type)
        return await skill.execute(envelope, self)
```

## 6.4 Skill Implementation Pattern

```python
# src/squadops/agents/skills/shared/task_analysis.py
from squadops.agents.skills.base import Skill
from squadops.agents.skills.context import SkillContext

class TaskAnalysisSkill(Skill):
    """Analyzes incoming tasks and produces structured breakdowns."""

    SKILL_ID = "task_analysis"
    SUPPORTED_TASK_TYPES = ["analyze", "decompose", "estimate"]

    async def execute(self, inputs: dict, context: SkillContext) -> dict:
        """Execute skill with inputs dict and SkillContext (no agent required)."""
        # Get system prompt from PromptService via context
        prompt = context.prompt_service.assemble(
            role=context.role_id,
            hook="task_execute",
            task_type="analyze"
        )

        # Use LLM via port from context
        response = await context.llm.chat(
            messages=[
                {"role": "system", "content": prompt.content},
                {"role": "user", "content": inputs.get("task_description")}
            ]
        )

        # Store in memory via port from context
        await context.memory.store(MemoryEntry(
            content=response.content,
            metadata={"task_id": context.task_id, "skill": self.SKILL_ID}
        ))

        # Return outputs dict (not TaskResult - agents wrap this)
        return {"analysis": response.content}
```

> **Note**: Skills receive `SkillContext` (which wraps ports), not `BaseAgent`. This makes skills testable without instantiating agents - unit tests create a `SkillContext` with mocked ports.

## 6.5 Capability Handler Pattern

```python
# src/squadops/capabilities/handlers/data/collect_cycle_snapshot.py
from squadops.capabilities.base import CapabilityHandler
from squadops.ports.tools import FileSystemPort

class CollectCycleSnapshotHandler(CapabilityHandler):
    """
    Handler for data.collect_cycle_snapshot capability.
    Aligned to contract: manifests/contracts/data/collect_cycle_snapshot.yaml
    """

    CAPABILITY_ID = "data.collect_cycle_snapshot"

    def __init__(self, filesystem: FileSystemPort, metrics: MetricsPort):
        self.filesystem = filesystem
        self.metrics = metrics

    async def execute(self, inputs: dict) -> dict:
        cycle_id = inputs["cycle_id"]
        output_dir = inputs.get("output_dir", f"runs/{cycle_id}/capabilities/{self.CAPABILITY_ID}")

        # Collect snapshot data
        snapshot = await self._collect_snapshot(cycle_id)

        # Write artifact via FileSystemPort
        output_path = f"{output_dir}/cycle_snapshot.json"
        self.filesystem.write(Path(output_path), json.dumps(snapshot, indent=2))

        # Emit metrics
        self.metrics.counter("capability_executions", labels={"capability": self.CAPABILITY_ID})

        return {"snapshot_path": output_path}
```

---

# 6.6 Definitions (Normative)

The following definitions are normative for this SIP and the implementation plan:

**Skill**: An atomic, reusable operation that produces outputs from inputs. Skills:
- MUST implement `execute(inputs: dict, context: SkillContext) -> dict`
- MUST NOT accept `TaskEnvelope` directly (agents map envelopes to inputs)
- MUST NOT call Capabilities
- MUST NOT contain acceptance logic or "task complete" semantics
- MAY be nondeterministic (e.g., LLM calls) but MUST be observable and bounded in side effects

**Capability**: A task-level deliverable that orchestrates Skills. Capabilities:
- MUST produce certified artifacts
- MUST own acceptance checks (via AcceptanceCheckEngine)
- SHOULD compose Skills, not re-implement primitives
- MAY invoke multiple Skills in sequence or parallel
- Report completion status with acceptance evidence

**Acceptance**: Validation that a Capability produced correct outputs. Acceptance:
- Runs at the Capability boundary, not inside Skills
- Uses AcceptanceCheckEngine with contract-defined checks
- Produces an acceptance report attached to CapabilityResult

**Composition Rule**: Capabilities orchestrate Skills; Skills MUST NOT call Capabilities. This ensures:
- Skills remain atomic and reusable
- Acceptance logic is centralized in Capabilities
- Testing is simplified (Skills test with mocked ports; Capabilities test with mocked Skills)

---

# 7. Functional Requirements

## 7.1 Agent Role Requirements

- All agents MUST extend `BaseAgent` and receive ports via constructor injection.
- Agents MUST NOT import from `_v0_legacy/`.
- Agents MUST use `PromptService` for all prompt assembly.
- Agents MUST use `LLMPort` for all LLM interactions.
- Agents MUST use `MemoryPort` for all memory operations.
- Agents MUST emit lifecycle events via `EventPort`.

## 7.2 Skill Requirements

- Skills MUST be registered in `SkillRegistry` with unique SKILL_ID.
- Skills MUST declare supported task types.
- Skills MUST implement `execute(inputs: dict, context: SkillContext) -> dict`.
- Skills MUST be stateless (all state flows through SkillContext ports).
- Skills MUST return outputs dict (agents wrap this in TaskResult).
- Skills MUST NOT accept TaskEnvelope directly (agents map envelopes to inputs).
- Skills MUST NOT call Capabilities or contain acceptance logic.

## 7.3 Capability Handler Requirements

- Handlers MUST implement `CapabilityHandler` base class.
- Handler CAPABILITY_ID MUST match contract `capability_id`.
- Handlers MUST produce artifacts at contract-specified paths.
- Handlers MUST pass all contract acceptance checks.

## 7.4 Runtime API Requirements

- API MUST use FastAPI with dependency injection.
- API MUST inject ports via `deps.py` module.
- API MUST emit telemetry for all endpoints.
- API MUST validate requests against ACI TaskEnvelope schema.

## 7.5 Agent Factory Requirements

- Factory MUST instantiate agents with all required ports.
- Factory MUST resolve ports via adapter factories (SIP-0.8.7).
- Factory MUST support deployment profile selection.
- Factory MUST validate agent configuration before instantiation.

---

# 8. Testing Requirements (Unit + Integration)

## 8.1 Unit Tests (Domain Isolation - Required)

Unit tests MUST verify agent logic **without infrastructure access**:

- [ ] BaseAgent correctly dispatches to skills
- [ ] SkillRegistry loads and validates skills
- [ ] Each skill produces correct TaskResult with mock ports
- [ ] CapabilityDispatcher routes to correct handler
- [ ] AgentFactory creates agents with all ports injected

## 8.2 Integration Tests (Adapter Verification - Required)

Integration tests MUST verify full agent operation:

- [ ] LeadAgent completes task_analysis with real LLM
- [ ] DevAgent completes code_generate with real filesystem
- [ ] QAAgent completes test_execution with real containers
- [ ] DataAgent completes cycle_snapshot with real memory
- [ ] Runtime API accepts and processes task submissions

## 8.3 Migration Verification Tests

- [ ] Zero imports from `_v0_legacy/` in `src/squadops/`
- [ ] Zero imports from `_v0_legacy/` in `adapters/`
- [ ] All agent containers build successfully
- [ ] All existing integration tests pass with new structure

---

# 9. Non-Functional Requirements

1. **Backwards Compatibility:** Existing ACI TaskEnvelope contracts remain unchanged.
2. **Performance:** Agent instantiation must complete in <100ms.
3. **Reliability:** Agent failures must not crash the Runtime API.
4. **Observability:** All agent operations must emit traces and metrics.
5. **Testability:** All agent code must be testable with mock ports.

---

# 10. Migration Strategy

## 10.1 Migration Phases

### Phase 1: Foundation (Week 1)
- Create `src/squadops/agents/` directory structure
- Migrate `BaseAgent` from `execution/agent.py`
- Implement `AgentFactory` with port injection
- Implement `SkillRegistry`

### Phase 2: Agents (Week 2)
- Migrate LeadAgent
- Migrate DevAgent
- Migrate QAAgent
- Migrate StratAgent
- Migrate DataAgent

### Phase 3: Skills (Week 3)
- Migrate shared skills
- Migrate role-specific skills
- Update skill registrations

### Phase 4: Capabilities (Week 4)
- Migrate data capability handlers
- Migrate delivery capability handlers
- Migrate ops capability handlers
- Verify against SIP-0058 contracts

### Phase 5: API & Cleanup (Week 5)
- Migrate Runtime API to `src/squadops/api/`
- Update all imports
- Run migration verification tests
- Delete `_v0_legacy/`

## 10.2 Rollback Strategy

If critical issues arise:
1. Git revert the migration commits
2. Restore `_v0_legacy/` from git history
3. Update imports to use legacy paths
4. Document issues for retry

## 10.3 Legacy Deletion Criteria

The `_v0_legacy/` directory MAY be deleted when:
- [ ] All migration verification tests pass
- [ ] All agent containers build and run
- [ ] All integration tests pass
- [ ] No imports reference `_v0_legacy/`
- [ ] CI/CD pipelines pass for 3 consecutive runs

---

# 11. Executive Summary — What Must Be Built

### Agent Domain (`src/squadops/agents/`)
| File | Description |
|------|-------------|
| `models.py` | Agent, AgentRole, AgentContext dataclasses |
| `exceptions.py` | AgentError, SkillNotFoundError |
| `base.py` | BaseAgent with port injection |
| `factory.py` | AgentFactory domain service |
| `roles/*.py` | LeadAgent, DevAgent, QAAgent, StratAgent, DataAgent |
| `skills/registry.py` | SkillRegistry |
| `skills/base.py` | Skill base class |
| `skills/shared/*.py` | Shared skill implementations |
| `skills/<role>/*.py` | Role-specific skill implementations |

### Capability Domain (`src/squadops/capabilities/`)
| File | Description |
|------|-------------|
| `dispatcher.py` | CapabilityDispatcher |
| `handlers/base.py` | CapabilityHandler base class |
| `handlers/data/*.py` | Data capability handlers |
| `handlers/delivery/*.py` | Delivery capability handlers |
| `handlers/ops/*.py` | Ops capability handlers |
| `handlers/product/*.py` | Product capability handlers |

### API Domain (`src/squadops/api/`)
| File | Description |
|------|-------------|
| `app.py` | FastAPI application |
| `deps.py` | Dependency injection |
| `routes/tasks.py` | Task endpoints |
| `routes/agents.py` | Agent endpoints |
| `routes/health.py` | Health endpoints |
| `routes/cycles.py` | Cycle endpoints |

### Orchestration Domain (`src/squadops/orchestration/`)
| File | Description |
|------|-------------|
| `models.py` | Cycle, Pulse, Squad |
| `orchestrator.py` | AgentOrchestrator |
| `scheduler.py` | Task scheduler |

### Configuration (`src/squadops/config/`)
| File | Description |
|------|-------------|
| `models.py` | DeploymentProfile, AgentConfig |
| `loader.py` | Config loading |
| `profiles/*.yaml` | Deployment profiles |

---

# 12. Definition of Done

### Agent Domain
- [ ] `BaseAgent` refactored with full port injection
- [ ] `AgentFactory` creates agents with all ports
- [ ] `SkillRegistry` discovers and loads skills
- [ ] `LeadAgent` migrated and tested
- [ ] `DevAgent` migrated and tested
- [ ] `QAAgent` migrated and tested
- [ ] `StratAgent` migrated and tested
- [ ] `DataAgent` migrated and tested

### Skills
- [ ] All shared skills migrated
- [ ] All lead skills migrated
- [ ] All dev skills migrated
- [ ] All qa skills migrated
- [ ] All strat skills migrated
- [ ] All data skills migrated
- [ ] No skill contains acceptance logic
- [ ] No skill calls Capabilities
- [ ] All skills testable with mocked SkillContext (no agent required)

### Capabilities
- [ ] `CapabilityDispatcher` implemented
- [ ] All data handlers migrated and pass contract acceptance
- [ ] All delivery handlers migrated
- [ ] All ops handlers migrated
- [ ] All product handlers migrated
- [ ] Capabilities invoke skills via SkillRegistry (not re-implemented inline)
- [ ] All capabilities own acceptance checks (via AcceptanceCheckEngine)

### API
- [ ] Runtime API migrated to `src/squadops/api/`
- [ ] All endpoints use dependency injection
- [ ] Health checks pass

### Orchestration
- [ ] `AgentOrchestrator` implemented
- [ ] Cycle/Pulse lifecycle management works

### 0.8.7 Deferral Completion
- [ ] `EmbeddingsPort` implemented in `src/squadops/ports/embeddings/`
- [ ] `OllamaEmbeddingsAdapter` implemented in `adapters/embeddings/`
- [ ] `LanceDBAdapter` updated to use injected `EmbeddingsPort` (remove `embed_fn` seam)
- [ ] `PrefectTaskAdapter` fully implemented (replace stub)
- [ ] `TaskEnvelope`/`TaskResult` migrated to frozen dataclasses
- [ ] `squadops.tasks.types` compatibility bridge removed

### Migration Verification
- [ ] Zero imports from `_v0_legacy/`
- [ ] All agent containers build
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] CI passes for 3 consecutive runs

### Cleanup
- [ ] `_v0_legacy/` directory deleted
- [ ] Non-Python configs moved to root `infra/`
- [ ] `docker-compose.yml` volume paths updated
- [ ] Git history preserved for reference
- [ ] Documentation updated

---

# 13. Appendix

## 13.1 Migration File Mapping

| Legacy Path | New Path |
|-------------|----------|
| `_v0_legacy/agents/base_agent.py` | `src/squadops/agents/base.py` |
| `_v0_legacy/agents/roles/lead/` | `src/squadops/agents/roles/lead.py` |
| `_v0_legacy/agents/roles/dev/` | `src/squadops/agents/roles/dev.py` |
| `_v0_legacy/agents/skills/shared/` | `src/squadops/agents/skills/shared/` |
| `_v0_legacy/agents/capabilities/data/` | `src/squadops/capabilities/handlers/data/` |
| `_v0_legacy/agents/factory/` | `src/squadops/agents/factory.py` |
| `_v0_legacy/infra/runtime-api/` | `src/squadops/api/` |
| `_v0_legacy/config/` | `src/squadops/config/` |

## 13.2 Dependency Injection Example

```python
# src/squadops/api/deps.py
from functools import lru_cache
from adapters.llm import create_llm_provider
from adapters.memory import create_memory_provider
from adapters.tools import create_filesystem_provider
from adapters.telemetry import create_metrics_provider, create_event_provider
from adapters.comms import create_queue_provider
from adapters.prompts import create_prompt_repository
from squadops.prompts.assembler import PromptAssembler
from squadops.agents.factory import AgentFactory

@lru_cache
def get_agent_factory() -> AgentFactory:
    """Create singleton AgentFactory with all ports."""
    return AgentFactory(
        llm=create_llm_provider(),
        memory=create_memory_provider(),
        filesystem=create_filesystem_provider(),
        metrics=create_metrics_provider(),
        events=create_event_provider(),
        queue=create_queue_provider(),
        prompt_service=PromptAssembler(create_prompt_repository()),
    )

def get_lead_agent():
    """Dependency for LeadAgent."""
    factory = get_agent_factory()
    return factory.create("lead")
```

## 13.3 Version Milestone Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    SquadOps 0.8.x Migration                      │
├─────────┬─────────────────────────────────────────┬─────────────┤
│ Version │ SIP                                     │ Layer       │
├─────────┼─────────────────────────────────────────┼─────────────┤
│ 0.8.4   │ Queue Transport                         │ Infra       │
│ 0.8.5   │ Layered Prompts                         │ Domain      │
│ 0.8.6   │ Capability Contracts                    │ Domain      │
│ 0.8.7   │ Infrastructure Ports                    │ Infra       │
│ 0.8.8   │ Agent Migration + Legacy Deletion       │ Application │
├─────────┴─────────────────────────────────────────┴─────────────┤
│                                                                  │
│  After 0.8.8: _v0_legacy/ DELETED                               │
│  Ready for 0.9.x: Observability, Benchmarking, Production       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 14. Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Initial draft |
| 2026-01-31 | Added 0.8.7 deferral pickup items (EmbeddingsPort, PrefectTaskAdapter, TaskEnvelope migration) |
| 2026-01-31 | Added missing directories (cycle_data, instances, templates, health-check) |
| 2026-01-31 | Added non-Python config relocation (grafana, otel, prometheus, migrations) |
| 2026-01-31 | Updated Definition of Done with deferral completion checklist |
| 2026-01-31 | Added Definitions (Normative) section with Skills, Capabilities, Acceptance, Composition Rule |
| 2026-01-31 | Updated Skill pattern to use SkillContext (not agent) for testability |
| 2026-01-31 | Added DoD checklist items enforcing composition rule |
