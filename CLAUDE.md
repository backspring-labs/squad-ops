# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SquadOps is a multi-agent orchestration framework for software development. It uses a hexagonal architecture (ports & adapters) with dependency injection for testability.

**Framework Version**: 0.8.9
**Python Requirement**: 3.11+

## Commands

### Testing
```bash
# Run new architecture tests (recommended, always pass)
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
```

### Docker
```bash
docker-compose up -d                       # Start all services
docker-compose up -d postgres redis rabbitmq  # Start core services only
```

## Architecture

### Hexagonal Structure (Ports & Adapters)
- **`src/squadops/`** - Core domain
  - `ports/` - Abstract interfaces (SecretProvider, DbRuntime, QueuePort)
  - `execution/` - Agent implementations with DI; role implementations in `execution/squad/`
  - `tasks/` - TaskEnvelope, TaskResult models (A2A message format with lineage per SIP-031)
  - `capabilities/` - Capability contracts and workload runner (SIP-0058)
  - `api/` - FastAPI runtime API service (SIP-0048)
  - `memory/` - LanceDB semantic memory (SIP-042)
  - `llm/` - LLM router abstraction with dynamic provider registry
  - `telemetry/` & `observability/` - OpenTelemetry with trace correlation
  - `config/` - Configuration loading (`SQUADOPS__*` env vars, double underscores for nesting)
  - `core/` - Core utilities (SecretManager)
- **`adapters/`** - Concrete implementations
  - `secrets/` - env, file, docker_secret providers
  - `comms/` - RabbitMQ adapter
  - `persistence/` - PostgreSQL runtime with connection pooling
  - `capabilities/` - Filesystem repository, ACI executor
- **`_v0_legacy/`** - Legacy v0 infrastructure (avoid modifying)

### Key Patterns
- **Dependency Injection**: `BaseAgent` receives `SecretManager`, `DbRuntime`, `AgentHeartbeatReporter` via constructor
- **Factory Pattern**: Adapters use factories for provider selection based on environment
- **Task Envelope**: A2A message format with lineage (correlation_id, causation_id, trace_id) per SIP-031
- **DTO Purity**: Task adapters return canonical DTOs; API formatting happens in FastAPI layer

### Agent Squad
5 agents: Max (Lead), Neo (Dev), Nat (Strategy), Eve (QA), Data (Analytics). Implementations in `src/squadops/execution/squad/`.

## Test Configuration

- Tests auto-receive `unit`/`integration` markers based on file location (`tests/conftest.py`)
- Unit test fixtures (mock_database, mock_redis, mock_ports, sample_task_envelope) are in `tests/unit/conftest.py`
- `asyncio_mode = "auto"` in pyproject.toml — async tests work without `@pytest.mark.asyncio`

### Key Markers
```python
@pytest.mark.unit / @pytest.mark.integration / @pytest.mark.smoke / @pytest.mark.slow
@pytest.mark.database / @pytest.mark.rabbitmq / @pytest.mark.redis / @pytest.mark.docker
@pytest.mark.domain_agents / @pytest.mark.domain_capabilities / @pytest.mark.domain_api / @pytest.mark.domain_memory
```

## SIP System (SquadOps Improvement Proposals)

SIPs govern architectural decisions. Located in `sips/` with lifecycle:
- `sips/proposals/` - Unnumbered drafts
- `sips/accepted/` - Numbered, approved
- `sips/implemented/` - Matched to code
- `sips/registry.yaml` - Canonical index

To move a SIP (maintainer only):
```bash
export SQUADOPS_MAINTAINER=1
python scripts/maintainer/update_sip_status.py sips/proposals/SIP-MyIdea.md accepted
```

## Repository Rules

**Read-Only Areas**:
- Never modify `dist/`, `_v0_legacy/config/version.py`, or generated metadata (`manifest.json`, `agent_info.json`)
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
| rabbitmq | 5672, 15672 | Message queue |
| postgres | 5432 | Database |
| redis | 6379 | Cache |
| runtime-api | 8001 | SIP-0048 runtime API |
| health-check | 8000 | Health monitoring |
| prefect-server | 4200 | Workflow orchestration |

## Key Files

- `pyproject.toml` - Python config (ruff, pytest, mypy, coverage settings); ruff line-length is 100
- `tests/conftest.py` - Global fixtures, session event loop, auto-markers by file location
- `tests/unit/conftest.py` - Unit-specific mock fixtures (mock_database, mock_ports, sample_task_envelope)
- `.env.example` - Environment template (`SQUADOPS__*` prefix, double underscores for nesting)

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

- Infrastructure configs are in `_v0_legacy/infra/` (migration in progress). Volume mount paths in `docker-compose.yml` should point there, not `infra/`.
- Adapter integration tests don't need agent containers: `SKIP_AGENT_CHECK=1 pytest tests/integration/adapters/ -v`

| Symptom | Fix |
|---------|-----|
| Postgres mount error | Check docker-compose.yml points to `_v0_legacy/infra/init.sql` |
| Tests skip with "agents not running" | Set `SKIP_AGENT_CHECK=1` |
| Import errors in pytest | Run `pip install -e .` |
