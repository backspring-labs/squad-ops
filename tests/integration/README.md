# SquadOps Integration Tests

## Overview

This directory contains integration tests for the SquadOps framework. These tests verify that all components work together correctly, including agent communication, service integration, and end-to-end workflows.

## Test Structure

### Test Files

- `test_agent_communication.py` - Tests agent-to-agent communication through RabbitMQ
- `test_workflow.py` - Tests the complete workflow with real Ollama integration
- `test_agent_model_validation.py` - Validates that all agent model configurations are available and functional in Ollama
- `test_docker_build.py` - Tests Docker build process and metadata artifacts (manifest.json, agent_info.json, build hash)
- `test_agent_initialization.py` - Tests agent initialization with new metadata flow (agent_info.json loading, role context storage)
- `test_memory_integration.py` - Tests memory provider integration
- `conftest.py` - Test configuration and fixtures
- `agent_manager.py` - Helper for managing agent containers during tests
- `test_config.env` - Externalized configuration for services

### Test Categories

1. **Agent Communication Tests** - Verify agents can communicate via RabbitMQ
2. **Workflow Integration Tests** - Test complete workflows with real services
3. **Service Integration Tests** - Verify integration with external services
4. **Agent Configuration Validation Tests** - Verify agent configurations are valid (model availability, etc.)
5. **Docker Build Tests** - Verify Docker builds, metadata artifacts, and build hash propagation
6. **Agent Initialization Tests** - Verify agent initialization with metadata loading and role context storage

**Note:** End-to-end WarmBoot testing is done manually as a smoke test rather than automated integration tests.

## Prerequisites

### Required Services

Before running integration tests, ensure these services are running:

1. **PostgreSQL** (port 5432)
   - Database: `squadops`
   - User: `squadops`
   - Password: `squadops123`

2. **Redis** (port 6379)
   - Default configuration

3. **RabbitMQ** (port 5672)
   - User: `squadops`
   - Password: `squadops123`
   - Management UI: http://localhost:15672

4. **Ollama** (port 11434)
   - Must have a model available (e.g., `llama3.1`)

5. **Agent Containers**
   - `squadops-max` (LeadAgent)
   - `squadops-neo` (DevAgent)

### Service Setup

#### Start Infrastructure Services
```bash
# Start all infrastructure services
docker-compose up -d postgres redis rabbitmq task-api health-check

# Verify services are running
docker ps --filter "name=squadops" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

#### Start Agent Containers
```bash
# Start agent containers
docker-compose up -d max neo

# Verify agents are running and healthy
docker ps --filter "name=squadops" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

#### Ollama Setup
```bash
# Install and start Ollama
# Download from https://ollama.ai/

# Pull a model
ollama pull llama3.1

# Verify Ollama is running
curl http://localhost:11434/api/version
```

## Running Tests

### Quick Start

```bash
# Recommended: Use the test runner script
cd /Users/jladd/squad-ops
./tests/integration/run_all.sh

# Or use pytest directly
python3 -m pytest tests/integration/ -v
```

### Service Health Check

Before running tests, verify all services are healthy:

```bash
python3 tests/integration/check_services.py --verbose
```

### Run All Integration Tests

```bash
# Using the test runner script (recommended)
./tests/integration/run_all.sh

# Using pytest directly
python3 -m pytest tests/integration/ -v
```

### Run Specific Test Categories

```bash
# Agent communication tests only
./tests/integration/run_all.sh test_agent_communication.py

# Workflow tests only
./tests/integration/run_all.sh test_workflow.py

# Memory integration tests only
./tests/integration/run_all.sh test_memory_integration.py
```

### Run Tests by Marker

```bash
# PostgreSQL-dependent tests
python3 -m pytest tests/integration/ -v -m service_postgres

# RabbitMQ-dependent tests
python3 -m pytest tests/integration/ -v -m service_rabbitmq

# Ollama-dependent tests
python3 -m pytest tests/integration/ -v -m service_ollama

# Agent container-dependent tests
python3 -m pytest tests/integration/ -v -m agent_containers
```

For detailed execution instructions, see [EXECUTION_GUIDE.md](EXECUTION_GUIDE.md).

### Run with Coverage
```bash
python3 -m pytest tests/integration/ --cov=agents --cov-report=html
```

## Test Execution Strategy

### Test Categories and Markers

Tests are organized by service dependencies:

- `@pytest.mark.service_postgres` - Requires PostgreSQL
- `@pytest.mark.service_rabbitmq` - Requires RabbitMQ
- `@pytest.mark.service_redis` - Requires Redis
- `@pytest.mark.service_ollama` - Requires Ollama (optional)
- `@pytest.mark.agent_containers` - Requires agent containers (Max/Neo)

### Retry Logic

Network-dependent tests use retry logic for transient failures:

```python
from tests.integration.conftest import retry_on_network_error

@retry_on_network_error(max_retries=3, delay=1.0, backoff=2.0)
async def test_network_dependent():
    # Test code here
```

### Test Isolation

Tests automatically clean up state between runs:
- Database state (via `clean_database` fixture)
- RabbitMQ queues (via `clean_rabbitmq` fixture)
- Redis cache (via `clean_redis` fixture)

## Test Configuration

### Environment Variables

Tests use the `test_config.env` file for service configuration:

```env
POSTGRES_URL=postgresql://squadops:squadops123@localhost:5432/squadops
RABBITMQ_USER=squadops
RABBITMQ_PASSWORD=squadops123
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
REDIS_URL=redis://localhost:6379
OLLAMA_URL=http://localhost:11434
TASK_API_URL=http://localhost:8001
LOG_LEVEL=INFO
USE_LOCAL_LLM=true
```

### Test Fixtures

- `integration_config` - Loads configuration from `test_config.env`
- `ensure_agents_running_fixture` - Ensures agent containers are running
- `agent_manager` - Provides AgentManager instance for container management
- `clean_database` - Cleans database state between tests
- `clean_rabbitmq` - Cleans RabbitMQ state between tests
- `clean_redis` - Cleans Redis state between tests

## Agent Container Management

### AgentManager Helper

The `AgentManager` class provides utilities for managing agent containers:

```python
from agent_manager import AgentManager

manager = AgentManager()

# Check if agents are running
container_info = manager.get_agent_container_info()

# Ensure agents are running
await manager.ensure_agents_running(['max', 'neo'])

# Rebuild agents if needed
await manager.rebuild_agents(['max', 'neo'])

# Verify agent health
await manager.verify_agent_health('max')
```

### Container Health Checks

Tests automatically verify that:
- Agent containers are running
- Agents respond to health checks
- Agent logs don't contain errors
- Agents can process basic commands

### Metadata Artifacts

Integration tests verify that agent containers include required metadata artifacts:

1. **manifest.json** - Build artifact metadata
   - Location: `/app/manifest.json` in container
   - Contains: `manifest_version`, `role`, `capabilities`, `build_hash`, `build_time_utc`, etc.
   - Verified by: `test_manifest_json_structure()` in `test_docker_build.py`

2. **agent_info.json** - Runtime identity metadata
   - Location: `/app/agent_info.json` in container
   - Contains: `agent_info_version`, `role`, `agent_id`, `build_hash`, `runtime_env`, etc.
   - Verified by: `test_agent_info_json_structure()` in `test_docker_build.py`

3. **Build Hash Propagation** - Ensures build hash matches between build and runtime
   - Verified by: `test_build_hash_propagation()` in `test_docker_build.py`
   - Build hash from `manifest.json` must match `agent_info.json` build_hash

### Agent Initialization Flow

Integration tests verify the new agent initialization flow:

1. **Agent Info Loading** - Agents load `agent_info.json` during initialization (backward compatible if missing)
   - Verified by: `test_agent_loads_agent_info_on_initialize()` in `test_agent_initialization.py`

2. **Memory Provider Initialization** - Agents initialize memory providers (LanceDB, SQL adapter)
   - Verified by: `test_agent_initialization_with_memory_providers()` in `test_agent_initialization.py`

3. **Role Context Storage** - Agents store role context in memory during initialization
   - Verified by: `test_agent_stores_role_context()` in `test_agent_initialization.py`

4. **Backward Compatibility** - Initialization works even without `agent_info.json`
   - Verified by: `test_agent_initialization_backward_compatibility()` in `test_agent_initialization.py`

## Troubleshooting

### Common Issues

1. **Agent containers not running**
   ```bash
   # Check container status
   docker ps --filter "name=squadops"
   
   # Start agents
   docker-compose up -d max neo
   ```

2. **Database connection errors**
   ```bash
   # Check PostgreSQL is running
   docker ps --filter "name=squadops-postgres"
   
   # Check connection
   psql -h localhost -U squadops -d squadops
   ```

3. **RabbitMQ connection errors**
   ```bash
   # Check RabbitMQ is running
   docker ps --filter "name=squadops-rabbitmq"
   
   # Check management UI
   open http://localhost:15672
   ```

4. **Ollama not responding**
   ```bash
   # Check Ollama is running
   curl http://localhost:11434/api/version
   
   # Check available models
   ollama list
   ```

### Agent Container Issues

1. **Container exits immediately**
   ```bash
   # Check logs
   docker logs squadops-max
   docker logs squadops-neo
   
   # Rebuild containers
   docker-compose build --no-cache max neo
   docker-compose up -d max neo
   ```

2. **Import errors in containers**
   - Check that agent code has correct imports
   - Verify Dockerfile copies all necessary files
   - Rebuild containers after code changes

3. **Missing metadata artifacts**
   - Verify `manifest.json` and `agent_info.json` exist in container: `docker exec squadops-eve ls -la /app/*.json`
   - Check build script generated artifacts: `ls -la dist/agents/qa/*.json`
   - Rebuild agent package: `python scripts/build_agent.py qa`

4. **Build hash mismatches**
   - Verify build hash in `manifest.json` matches `agent_info.json` in running container
   - Check Docker image label: `docker inspect squadops/eve:test | grep build_hash`
   - Force rebuild if hash doesn't match: `docker-compose build --no-cache eve`

### Test Failures

1. **Database schema errors**
   - Tests may fail if database tables don't exist
   - Some tests skip database operations to avoid schema requirements

2. **Service connection timeouts**
   - Verify all services are running
   - Check network connectivity
   - Verify service URLs in configuration

## Best Practices

### Test Development

1. **Use real services** - Avoid mocking external services in integration tests
2. **Verify prerequisites** - Check that required services are running
3. **Clean up state** - Use fixtures to clean up between tests
4. **Handle failures gracefully** - Skip tests if prerequisites aren't met

### Agent Management

1. **Rebuild after code changes** - Always rebuild agent containers after modifying code
2. **Check container health** - Verify agents are healthy before running tests
3. **Monitor logs** - Check agent logs for errors during test execution

### Service Configuration

1. **Externalize configuration** - Use `test_config.env` for service URLs and credentials
2. **Use environment variables** - Allow configuration to be overridden
3. **Document requirements** - Clearly document all service prerequisites

## Integration Test Principles

1. **Real Integration** - Tests use actual services, not mocks
2. **End-to-End Validation** - Tests verify complete workflows
3. **Service Verification** - Tests check that all services are available
4. **Agent Health** - Tests ensure agents are running and healthy
5. **State Management** - Tests clean up state between runs

## 🚨 CRITICAL: NO MOCKS IN INTEGRATION TESTS

**Integration tests MUST use real services. Mocks are FORBIDDEN.**

### Validation
Before committing integration test changes, run:
```bash
python3 tests/integration/validate_integration_tests.py
```

This validator will **FAIL** if any integration test uses:
- `unittest.mock`
- `MagicMock`, `AsyncMock`
- `@patch` decorators
- Any mocking of core components

### Why This Matters
- Mocked integration tests provide **false confidence**
- They won't catch real integration issues (like missing packages)
- They violate "No deceptive simulations" principle
- They violate "Quality over speed" principle

### What To Use Instead
- **Real PostgreSQL**: `asyncpg.create_pool(connection_url)`
- **Real adapters**: `SqlAdapter(db_pool)`, `Mem0Adapter(agent_name)`
- **Real agents**: `LeadAgent()`, `DevAgent()` with real connections
- **Real services**: No mocks, no patches, real integration

See `tests/integration/VALIDATION.md` for detailed validation checklist.

## Continuous Integration

For CI/CD pipelines:

1. **Service Setup** - Use Docker Compose to start all services
2. **Agent Management** - Use AgentManager to ensure agents are running
3. **Health Checks** - Verify all services are healthy before running tests
4. **Cleanup** - Clean up containers and state after tests complete

## Related Documentation

- [Unit Tests](../unit/README.md) - Unit test documentation
- [Smoke Tests](../smoke/README.md) - Smoke test documentation
- [Agent Development](../../agents/README.md) - Agent development guide
- [Service Configuration](../../infra/README.md) - Infrastructure setup guide

