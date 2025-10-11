# 🧪 SquadOps Test Harness
## Comprehensive Testing Framework for Core Components

**Purpose**: Test SquadOps core framework without full WarmBoot dependency  
**Goal**: Prevent regressions during rapid AI-assisted development  
**Coverage**: Agents, Factory, Base Classes, Communication, Database  
**Protocol**: [SIP-026: Testing Framework and Philosophy](../docs/SIPs/SIP-026-Testing-Framework-Protocol.md)

---

## 🏗️ **Hybrid Testing Approach**

This test harness implements a hybrid testing strategy defined in SIP-026:

- **Unit Tests**: Fast, isolated testing with mocked dependencies
- **Integration Tests**: Real service testing with testcontainers
- **Regression Tests**: Snapshot testing for critical workflows
- **Performance Tests**: System performance validation

---

## 🎯 **Test Categories**

### **1. Unit Tests** (`tests/unit/`)
- **Agent Core Logic**: BaseAgent, LeadAgent, DevAgent methods
- **Factory Operations**: RoleFactory, AgentFactory instantiation
- **Communication**: Message handling, RabbitMQ integration
- **Database**: Connection pooling, query execution
- **Configuration**: Agent configs, deployment settings

### **2. Integration Tests** (`tests/integration/`)
- **Agent Communication**: Inter-agent messaging via RabbitMQ with testcontainers
- **Database Integration**: Task management, execution cycles with real PostgreSQL
- **Service Integration**: Health check, task API with real Redis
- **Container Operations**: Real Docker containers for isolated testing

### **3. Regression Tests** (`tests/regression/`)
- **Core Workflows**: PRD processing, task delegation
- **Agent Behavior**: Expected agent responses and state changes
- **API Contracts**: Health check, task management endpoints
- **Database Schema**: Migration compatibility

### **4. Performance Tests** (`tests/performance/`)
- **Agent Startup**: Time to initialize agents
- **Message Processing**: Throughput and latency
- **Database Operations**: Query performance
- **Memory Usage**: Agent memory footprint

---

## 🚀 **Quick Start**

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test category
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/regression/ -v

# Run with coverage
python -m pytest tests/ --cov=agents --cov-report=html

# Run specific test
python -m pytest tests/unit/test_base_agent.py::test_agent_initialization -v
```

---

## 📊 **Test Coverage Goals**

- **Unit Tests**: 90%+ coverage for core agent logic
- **Integration Tests**: 80%+ coverage for inter-agent communication
- **Regression Tests**: 100% coverage for critical workflows
- **Performance Tests**: Baseline metrics for all operations

---

## 🔧 **Test Configuration**

Tests use:
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking framework
- **coverage**: Code coverage reporting
- **faker**: Test data generation
- **testcontainers**: Real service integration testing

---

## 🎯 **Regression Prevention**

The test harness includes:
- **Snapshot Testing**: Compare agent outputs against known good states
- **Contract Testing**: Verify API interfaces remain stable
- **Behavior Testing**: Ensure agent behavior doesn't drift
- **Performance Baselines**: Detect performance regressions

---

## 📁 **Directory Structure**

```
tests/
├── unit/                 # Unit tests for individual components
├── integration/          # Integration tests for component interactions
├── regression/           # Regression tests for critical workflows
├── performance/          # Performance and load tests
├── fixtures/             # Test data and fixtures
├── conftest.py          # Pytest configuration
└── utils/               # Test utilities and helpers
```
