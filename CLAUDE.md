# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SquadOps is a multi-agent orchestration framework for software development. It uses a hexagonal architecture (ports & adapters) with dependency injection for testability.

**Framework Version**: 0.9.10
**Python Requirement**: 3.11+

## Commands

### Testing
```bash
# Run new architecture tests (recommended, 1830+ tests always pass)
./scripts/dev/run_new_arch_tests.sh -v

# Run tests affected by your changes
./scripts/dev/run_affected_tests.sh           # Staged changes
./scripts/dev/run_affected_tests.sh --branch  # All changes vs main

# Run a single test file or test function
pytest tests/unit/agents/test_base_agent.py -v
pytest tests/unit/agents/test_base_agent.py::TestBaseAgent::test_init -v

# Run domain-specific tests
pytest tests/unit/agents/ -v          # Agent tests
pytest tests/unit/agents/roles/ -v    # Role-specific tests
pytest tests/unit/capabilities/ -v    # Capability tests
pytest tests/unit/api/ -v             # API tests
pytest tests/unit/tasks/ -v           # Task model tests
pytest tests/unit/memory/ -v          # Memory tests
pytest tests/unit/cycles/ -v          # Cycle execution tests
pytest tests/unit/telemetry/ -v       # LangFuse/telemetry tests
pytest tests/unit/auth/ -v            # Auth tests
pytest tests/unit/cli/ -v             # CLI tests

# Run all unit tests (includes legacy tests, some may fail)
pytest tests/unit -v

# Run with coverage
pytest tests/ --cov=src/squadops --cov-report=term-missing
```

### Linting & Formatting
```bash
ruff check . --fix    # Lint with auto-fix
ruff format .         # Format code
```

### Building Agents
```bash
python scripts/dev/build_agent.py <role>           # Build agent package locally (required before Docker build)
./scripts/dev/ops/rebuild_and_deploy.sh agents      # Rebuild and deploy all agents
./scripts/dev/ops/rebuild_and_deploy.sh runtime-api # Rebuild runtime API
./scripts/dev/ops/rebuild_and_deploy.sh all         # Rebuild everything
```

### Docker
```bash
docker-compose up -d                       # Start all services
docker-compose up -d postgres redis rabbitmq  # Start core services only
```

### CLI (Cycle Execution)
```bash
squadops login                             # Authenticate via Keycloak
squadops cycles create <project> --squad-profile full-squad --profile selftest
squadops cycles show <cycle-id>            # Show cycle status + runs
squadops cycles list <project-id>          # List cycles for project
squadops runs list <cycle-id>              # List runs for cycle
squadops gate decide <run-id> <gate-name> --approve  # Approve a gate
squadops artifacts list <run-id>           # List artifacts for run
```

## Architecture

### Hexagonal Structure (Ports & Adapters)
- **`src/squadops/`** - Core domain
  - `ports/` - Abstract interfaces (SecretProvider, DbRuntime, QueuePort, CycleRegistryPort, AuthPort, AuditPort, LLMObservabilityPort)
  - `agents/` - BaseAgent with DI, entrypoint for RabbitMQ message handling
  - `tasks/` - TaskEnvelope, TaskResult models (A2A message format with lineage per SIP-031)
  - `capabilities/` - Capability contracts, workload runner, cycle task handlers, build handlers (SIP-0058, SIP-0068)
  - `orchestration/` - AgentOrchestrator, HandlerExecutor
  - `cycles/` - Cycle/Run/Gate domain models, lifecycle state machine, task planning (SIP-0064)
  - `auth/` - Auth models, JWT validation helpers, middleware (SIP-0062)
  - `cli/` - Typer CLI commands, CRP contract packs (SIP-0065)
  - `api/` - FastAPI runtime API service with routes, DTOs, DI wiring (SIP-0048)
  - `telemetry/` - LLM observability models, CorrelationContext, NoOp adapter (SIP-0061)
  - `memory/` - LanceDB semantic memory (SIP-042)
  - `llm/` - LLM router abstraction with dynamic provider registry
  - `config/` - Configuration loading (`SQUADOPS__*` env vars, double underscores for nesting)
  - `core/` - Core utilities (SecretManager)
- **`adapters/`** - Concrete implementations
  - `secrets/` - env, file, docker_secret providers
  - `comms/` - RabbitMQ adapter
  - `persistence/` - PostgreSQL runtime with connection pooling
  - `cycles/` - DistributedFlowExecutor, MemoryCycleRegistry, PostgresCycleRegistry, factory
  - `telemetry/` - LangFuse adapter (buffered, with redaction) and factory
  - `auth/` - Keycloak adapter, JWT middleware
  - `llm/` - Ollama adapter
  - `capabilities/` - Filesystem repository, ACI executor
- **`infra/`** - Database migrations and DDL

### Key Patterns
- **Dependency Injection**: `BaseAgent` receives `SecretManager`, `DbRuntime`, `AgentHeartbeatReporter` via constructor
- **Factory Pattern**: Adapters use factories for provider selection based on environment
- **Task Envelope**: A2A message format with lineage (correlation_id, causation_id, trace_id) per SIP-031
- **DTO Purity**: Task adapters return canonical DTOs; API formatting happens in FastAPI layer
- **Frozen Dataclasses**: Cycle/Run/Gate models use `@dataclass(frozen=True)` with `dataclasses.replace()` for mutation
- **Always-inject NoOp**: `BaseAgent` and `AgentOrchestrator` auto-inject `NoOpLLMObservabilityAdapter` when `llm_observability=None`
- **Config-driven Selection**: Registry provider (memory vs postgres), auth, LangFuse all selected via config
- **CRP Applied Defaults**: Extra keys in CRP `defaults` flow into `applied_defaults`: `build_tasks`, `plan_tasks`, `pulse_checks`, `cadence_policy`

### Agent Squad
5 agents: Max (Lead), Neo (Dev), Nat (Strategy), Eve (QA), Data (Analytics). Implementations in `src/squadops/agents/`.

## Test Configuration

- Tests auto-receive `unit`/`integration` markers based on file location (`tests/conftest.py`)
- Unit test fixtures (mock_database, mock_redis, mock_ports, sample_task_envelope) are in `tests/unit/conftest.py`
- `asyncio_mode = "auto"` in pyproject.toml — async tests work without `@pytest.mark.asyncio`
- `--strict-markers` is enabled — any new `@pytest.mark.X` must be registered in `pyproject.toml`

### Key Markers
```python
@pytest.mark.unit / @pytest.mark.integration / @pytest.mark.smoke / @pytest.mark.slow
@pytest.mark.database / @pytest.mark.rabbitmq / @pytest.mark.redis / @pytest.mark.docker
@pytest.mark.domain_agents / @pytest.mark.domain_capabilities / @pytest.mark.domain_api
@pytest.mark.domain_memory / @pytest.mark.domain_orchestration / @pytest.mark.domain_telemetry
@pytest.mark.domain_cli / @pytest.mark.domain_contracts / @pytest.mark.domain_pulse_checks
@pytest.mark.langfuse / @pytest.mark.auth
```

## SIP System (SquadOps Improvement Proposals)

SIPs govern architectural decisions. Located in `sips/` with lifecycle:
- `sips/proposals/` - Unnumbered drafts
- `sips/accepted/` - Numbered, approved
- `sips/implemented/` - Matched to code
- `sips/registry.yaml` - Canonical index

Key implemented SIPs:
- **SIP-0061** – LangFuse LLM Observability Foundation
- **SIP-0062** – Auth Boundary (Keycloak OIDC)
- **SIP-0064** – Project Cycle Request API
- **SIP-0065** – CLI for Cycle Execution
- **SIP-0066** – Distributed Cycle Execution Pipeline
- **SIP-0067** – Postgres Cycle Registry
- **SIP-0068** – Enhanced Agent Build Capabilities
- **SIP-0069** – Console Control-Plane UI (Continuum Plugins)
- **SIP-0070** – Pulse Checks and Verification Framework

To move a SIP (maintainer only):
```bash
export SQUADOPS_MAINTAINER=1

# Promote a proposal to accepted (assigns a number)
python scripts/maintainer/update_sip_status.py sips/proposals/SIP-MyIdea.md accepted

# Promote an accepted SIP to implemented (after code is merged)
python scripts/maintainer/update_sip_status.py sips/accepted/SIP-0067-My-Feature.md implemented
```

## Repository Rules

**Read-Only Areas**:
- Never modify `dist/` or generated metadata (`manifest.json`, `agent_info.json`)
- Version bumps via `scripts/maintainer/version_cli.py` only

**Structure**:
- Permanent utilities: `scripts/dev/`
- Maintainer-only: `scripts/maintainer/`
- Temp migrations: `scripts/dev/migrations/temp_*.py`
- New SIP drafts go in `sips/proposals/` (unnumbered)
- Do not create scripts in the project root

**Tests**:
- Never delete/skip tests to make suite pass — fix implementation, not tests

**Docker**:
- Don't modify `docker-compose.yml` or change service/container names without explicit request

## Services (docker-compose.yml)

| Service | Port | Purpose |
|---------|------|---------|
| rabbitmq | 5672, 15672 | Message queue (inter-agent comms) |
| postgres | 5432 | Database (cycle registry, task logging) |
| redis | 6379 | Cache |
| runtime-api | 8001 | Cycle execution API (SIP-0048/0064) |
| prefect-server | 4200 | Workflow orchestration |
| squadops-keycloak | 8180 | OIDC identity provider (SIP-0062) |
| langfuse | 3001 | LLM observability UI (SIP-0061) |
| grafana | 3000 | Metrics dashboards |
| prometheus | 9090 | Metrics collection |
| otel-collector | 4317, 4318 | OpenTelemetry collector |
| squadops-console | — | Control-plane UI (SIP-0069) |
| caddy | 4040 | Reverse proxy for console and API |
| max/neo/nat/eve/data | — | Agent containers |


## Key Files

- `pyproject.toml` - Python config (ruff, pytest, mypy, coverage settings); ruff line-length is 100
- `tests/conftest.py` - Global fixtures, session event loop, auto-markers by file location
- `tests/unit/conftest.py` - Unit-specific mock fixtures (mock_database, mock_ports, sample_task_envelope)
- `.env.example` - Environment template (`SQUADOPS__*` prefix, double underscores for nesting)
- `docker-compose.yml` - 17-service development environment
- `infra/migrations/` - Postgres DDL migrations (applied at runtime-api startup)

## Python Path Setup

The project uses **editable install** for import resolution. Both `squadops` and `adapters` packages are discoverable:

```bash
pip install -e .  # Required: install in editable mode
```

`pyproject.toml` configures setuptools to find packages in `src/` (for `squadops*`) and project root (for `adapters*`).

**If imports fail** (e.g., `ModuleNotFoundError: No module named 'adapters'`):
1. Verify editable install: `pip list | grep squadops`
2. Re-install: `pip install -e .`
3. Ensure venv is active: `source .venv/bin/activate`

## Docker Troubleshooting

- Database migrations are baked into the runtime-api Docker image (`infra/migrations/`)
- Adapter integration tests don't need agent containers: `SKIP_AGENT_CHECK=1 pytest tests/integration/adapters/ -v`

| Symptom | Fix |
|---------|-----|
| Postgres mount error | Verify `docker-compose.yml` volume paths |
| Tests skip with "agents not running" | Set `SKIP_AGENT_CHECK=1` |
| Import errors in pytest | Run `pip install -e .` |
| JSONB round-trip errors | asyncpg returns JSONB as strings; use `_parse_jsonb()` helper |
| Auth 401 errors | Run `squadops login` first |
