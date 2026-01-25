# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SquadOps is a multi-agent orchestration framework for software development. It uses a hexagonal architecture (ports & adapters) with dependency injection for testability.

**Framework Version**: 0.8.4
**Python Requirement**: 3.11+

## Commands

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/unit -v
pytest tests/integration -v

# Run single test file
pytest tests/unit/test_base_agent.py -v

# Run with coverage
pytest tests/ --cov=src/squadops --cov-report=term-missing

# Using the test runner script
./tests/run_tests.sh unit        # Unit tests
./tests/run_tests.sh integration # Integration tests
./tests/run_tests.sh all         # All tests
```

### Linting & Formatting
```bash
ruff check . --fix    # Lint with auto-fix
ruff format .         # Format code
```

### Building Agents
```bash
# Build agent package locally (required before Docker build)
python scripts/dev/build_agent.py <role>

# Rebuild and deploy all agents
./scripts/dev/ops/rebuild_and_deploy.sh agents
```

### Docker
```bash
docker-compose up -d                       # Start all services
docker-compose up -d postgres redis rabbitmq  # Start core services only
```

## Architecture

### Hexagonal Structure (Ports & Adapters)
- **`src/squadops/`** - Core domain with port interfaces
  - `ports/` - Abstract interfaces (SecretProvider, DbRuntime, QueuePort)
  - `execution/` - Agent implementations with DI
  - `core/` - Core utilities
- **`adapters/`** - Concrete implementations
  - `secrets/` - env, file, docker_secret providers
  - `comms/` - RabbitMQ adapter
  - `persistence/` - PostgreSQL runtime
- **`_v0_legacy/`** - Legacy v0 infrastructure (avoid modifying)

### Key Patterns
- **Dependency Injection**: `BaseAgent` receives `SecretManager`, `DbRuntime`, `AgentHeartbeatReporter` via constructor
- **Factory Pattern**: Adapters use factories for provider selection based on environment
- **Task Envelope**: A2A message format with lineage (correlation_id, causation_id, trace_id) per SIP-031

### Agent Squad
10 agents total: 4 functional (Max/Lead, Neo/Dev, Nat/Strategy, Eve/QA) + 6 mock agents. Agents are in `src/squadops/execution/squad/`.

## Test Markers
```python
@pytest.mark.unit          # Unit tests (mocked deps)
@pytest.mark.integration   # Integration tests (real services)
@pytest.mark.database      # Requires PostgreSQL
@pytest.mark.rabbitmq      # Requires RabbitMQ
@pytest.mark.redis         # Requires Redis
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

## Repository Rules (from .cursorrules)

**Read-Only Areas**:
- Never modify `dist/` directory
- Never modify `_v0_legacy/config/version.py` directly
- Version bumps via `scripts/maintainer/version_cli.py` only

**Structure**:
- Permanent utilities: `scripts/dev/`
- Maintainer-only: `scripts/maintainer/`
- Temp migrations: `scripts/dev/migrations/temp_*.py`

**Tests**:
- Never delete/skip tests to make suite pass
- Fix implementation, not tests

**Docker**:
- Don't modify `docker-compose.yml` without explicit request
- Don't change service/container names

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

- `pyproject.toml` - Python config, ruff/pytest/mypy settings
- `tests/conftest.py` - Global fixtures with automatic LLM/config patching for unit tests
- `tests/requirements.txt` - Test dependencies
- `.env.example` - Environment template (SQUADOPS__* prefix, nested via double underscores)

## Python Path Setup

The project uses **editable install** for import resolution. Both `squadops` and `adapters` packages are discoverable:

```bash
# Required: Install in editable mode
pip install -e .
```

This works because `pyproject.toml` configures setuptools to find packages in both locations:
```toml
[tool.setuptools.packages.find]
where = ["src", "."]              # Search both src/ and project root
include = ["squadops*", "adapters*"]  # Include both packages
```

**If imports fail** (e.g., `ModuleNotFoundError: No module named 'adapters'`):
1. Verify editable install: `pip list | grep squadops` should show path to repo
2. Re-install if needed: `pip install -e .`
3. Ensure virtual environment is activated: `source .venv/bin/activate`

## Docker Troubleshooting

### Volume Mount Paths
Infrastructure configs are in `_v0_legacy/infra/` (migration in progress). If containers fail with mount errors:
- Check `docker-compose.yml` volume paths point to `_v0_legacy/infra/` not `infra/`
- Key files: `init.sql`, `otel-collector/config.yaml`, `prometheus/prometheus.yml`, `grafana/`

### Starting Core Services
```bash
# Start just the services needed for adapter integration tests
docker-compose up -d postgres redis rabbitmq

# Verify health
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "postgres|redis|rabbitmq"
```

### Integration Tests Without Agents
Adapter tests (queue, persistence) don't need agent containers. Skip the agent health check:
```bash
SKIP_AGENT_CHECK=1 pytest tests/integration/adapters/ -v
```

### Common Issues
| Symptom | Cause | Fix |
|---------|-------|-----|
| Postgres won't start, mount error | `infra/init.sql` path wrong | Check docker-compose.yml points to `_v0_legacy/infra/init.sql` |
| Tests skip with "agents not running" | Agent containers required by default | Set `SKIP_AGENT_CHECK=1` for adapter-only tests |
| Import errors in pytest | Editable install missing | Run `pip install -e .` |
