# Integration Test Execution Guide

## Overview

This guide provides step-by-step instructions for running all integration tests successfully. Integration tests verify that all SquadOps components work together correctly with real services.

## Quick Start

```bash
# Run all integration tests
cd /Users/jladd/squad-ops
./tests/integration/run_all.sh

# Or use pytest directly
python -m pytest tests/integration/ -v
```

## Prerequisites

### Required Services

Before running integration tests, ensure these services are running:

1. **PostgreSQL** (port 5432)
   ```bash
   docker-compose up -d postgres
   ```

2. **Redis** (port 6379)
   ```bash
   docker-compose up -d redis
   ```

3. **RabbitMQ** (port 5672)
   ```bash
   docker-compose up -d rabbitmq
   ```

4. **Agent Containers** (Max and Neo)
   ```bash
   docker-compose up -d max neo
   ```

5. **Ollama** (port 11434) - Optional but recommended
   ```bash
   # Install Ollama from https://ollama.ai/
   ollama pull llama3.1
   ```

### Service Health Check

Before running tests, verify all services are healthy:

```bash
python tests/integration/check_services.py --verbose
```

This will check:
- PostgreSQL connectivity
- Redis connectivity
- RabbitMQ connectivity
- RabbitMQ Management API (optional)
- Agent containers (Max/Neo)
- Ollama availability (optional)

## Test Execution

### Run All Tests

```bash
# Using the test runner script (recommended)
./tests/integration/run_all.sh

# Using pytest directly
python -m pytest tests/integration/ -v
```

### Run Specific Test Categories

```bash
# Run workflow tests only
./tests/integration/run_all.sh test_workflow.py

# Run agent communication tests only
./tests/integration/run_all.sh test_agent_communication.py

# Run memory integration tests only
./tests/integration/run_all.sh test_memory_integration.py
```

### Run Tests by Marker

```bash
# Run PostgreSQL-dependent tests
python -m pytest tests/integration/ -v -m service_postgres

# Run RabbitMQ-dependent tests
python -m pytest tests/integration/ -v -m service_rabbitmq

# Run Ollama-dependent tests
python -m pytest tests/integration/ -v -m service_ollama

# Run agent container-dependent tests
python -m pytest tests/integration/ -v -m agent_containers
```

## Test Categories

### 1. Service Integration Tests
- **File**: `test_opentelemetry_setup.py`
- **Dependencies**: None (fastest)
- **Duration**: ~5 seconds
- **Markers**: `@pytest.mark.integration`

### 2. Memory Integration Tests
- **File**: `test_memory_integration.py`
- **Dependencies**: PostgreSQL, LanceDB (optional)
- **Duration**: ~30 seconds
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.service_postgres`

### 3. Workflow Tests
- **File**: `test_workflow.py`
- **Dependencies**: Ollama (optional)
- **Duration**: ~60 seconds (with Ollama)
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.service_ollama`
- **Note**: Tests skip if Ollama is unavailable

### 4. Agent Communication Tests
- **File**: `test_agent_communication.py`
- **Dependencies**: PostgreSQL, Redis, RabbitMQ, Agent containers
- **Duration**: ~90 seconds
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.service_rabbitmq`, `@pytest.mark.agent_containers`

### 5. Task Delegation Tests
- **File**: `test_task_delegation_workflow.py`
- **Dependencies**: PostgreSQL, RabbitMQ, Agent containers, Ollama (optional)
- **Duration**: ~120 seconds
- **Markers**: `@pytest.mark.integration`, `@pytest.mark.service_rabbitmq`, `@pytest.mark.agent_containers`

## Expected Test Durations

| Test Category | Duration | Notes |
|--------------|----------|-------|
| Service Integration | ~5s | Fastest, no external dependencies |
| Memory Integration | ~30s | Requires PostgreSQL |
| Workflow Tests | ~60s | Requires Ollama (skips if unavailable) |
| Agent Communication | ~90s | Requires all services |
| Task Delegation | ~120s | Requires all services + Ollama |

**Total**: ~5 minutes for full suite (with all services available)

## Troubleshooting

### Common Issues

#### 1. Service Not Available

**Error**: `PostgreSQL is not running on localhost:5432`

**Solution**:
```bash
# Start the service
docker-compose up -d postgres

# Verify it's running
docker ps --filter "name=squadops-postgres"
```

#### 2. Agent Containers Not Running

**Error**: `Agent containers (Max/Neo) are not running`

**Solution**:
```bash
# Start agent containers
docker-compose up -d max neo

# Verify they're running
docker ps --filter "name=squadops"

# Check logs if needed
docker logs squadops-max
docker logs squadops-neo
```

#### 3. RabbitMQ Connection Failed

**Error**: `RabbitMQ is not running on localhost:5672`

**Solution**:
```bash
# Start RabbitMQ
docker-compose up -d rabbitmq

# Wait for it to be ready (may take 10-20 seconds)
sleep 15

# Verify it's running
docker ps --filter "name=squadops-rabbitmq"
```

#### 4. Ollama Not Available

**Error**: Tests skip with "Ollama not available"

**Solution**:
```bash
# Install Ollama from https://ollama.ai/
# Then pull a model
ollama pull llama3.1

# Verify Ollama is running
curl http://localhost:11434/api/version
```

#### 5. Test Isolation Issues

**Error**: Tests pass individually but fail when run together

**Solution**:
- Ensure `clean_database` fixture is working (resets database state)
- Ensure `clean_rabbitmq` fixture is working (purges queues)
- Ensure `clean_redis` fixture is working (flushes cache)
- Check for module state pollution (rare)

#### 6. Network Timeout Errors

**Error**: `Connection timeout` or `Name or service not known`

**Solution**:
- Tests now have retry logic for network errors
- Check service health: `python tests/integration/check_services.py`
- Verify Docker network connectivity
- Check firewall settings

## Test Execution Best Practices

### 1. Run Service Health Check First

Always verify services are healthy before running tests:

```bash
python tests/integration/check_services.py --verbose
```

### 2. Run Tests in Order

Tests are designed to run in this order:
1. Service integration tests (fastest, no dependencies)
2. Memory integration tests (requires PostgreSQL)
3. Workflow tests (requires Ollama)
4. Agent communication tests (requires all services)

The test runner script (`run_all.sh`) handles this automatically.

### 3. Monitor Test Execution

Watch for:
- Service connection errors (check service health)
- Agent container errors (check Docker logs)
- Network timeout errors (check retry logic)
- Test isolation issues (check fixtures)

### 4. Clean Up After Tests

Tests automatically clean up:
- Database state (via `clean_database` fixture)
- RabbitMQ queues (via `clean_rabbitmq` fixture)
- Redis cache (via `clean_redis` fixture)

No manual cleanup required.

## Continuous Integration

For CI/CD pipelines:

```bash
# 1. Start services
docker-compose up -d postgres redis rabbitmq max neo

# 2. Wait for services to be ready
sleep 30

# 3. Check service health
python tests/integration/check_services.py

# 4. Run tests
python -m pytest tests/integration/ -v --tb=short

# 5. Clean up (optional)
docker-compose down
```

## Validation

Before committing integration test changes:

```bash
# 1. Validate no mocks are used
python tests/integration/validate_integration_tests.py

# 2. Check service health
python tests/integration/check_services.py

# 3. Run all tests
./tests/integration/run_all.sh

# 4. Verify all tests pass
echo $?  # Should be 0
```

## Success Criteria

All integration tests should:
- ✅ Pass when run individually
- ✅ Pass when run together (no isolation issues)
- ✅ Skip gracefully when services unavailable
- ✅ Use real services (no mocks)
- ✅ Clean up state between tests
- ✅ Provide clear error messages

## Related Documentation

- [Integration Test README](README.md) - Overview and structure
- [Validation Guide](VALIDATION.md) - Mock validation rules
- [Service Health Check](check_services.py) - Service verification script
- [Test Runner Script](run_all.sh) - Automated test execution

