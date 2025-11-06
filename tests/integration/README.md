# SquadOps Integration Tests

## Overview

This directory contains integration tests for the SquadOps framework. These tests verify that all components work together correctly, including agent communication, service integration, and end-to-end workflows.

## Test Structure

### Test Files

- `test_agent_communication.py` - Tests agent-to-agent communication through RabbitMQ
- `test_workflow.py` - Tests the complete workflow with real Ollama integration
- `conftest.py` - Test configuration and fixtures
- `agent_manager.py` - Helper for managing agent containers during tests
- `test_config.env` - Externalized configuration for services

### Test Categories

1. **Agent Communication Tests** - Verify agents can communicate via RabbitMQ
2. **Workflow Integration Tests** - Test complete workflows with real services
3. **Service Integration Tests** - Verify integration with external services

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

### Run All Integration Tests
```bash
cd /Users/jladd/squad-ops
python3 -m pytest tests/integration/ -v
```

### Run Specific Test Categories
```bash
# Agent communication tests only
python3 -m pytest tests/integration/test_agent_communication.py -v

# Workflow tests only
python3 -m pytest tests/integration/test_workflow.py -v
```

### Run with Coverage
```bash
python3 -m pytest tests/integration/ --cov=agents --cov-report=html
```

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

