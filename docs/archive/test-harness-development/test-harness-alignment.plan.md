# 🧪 SquadOps Test Harness Alignment Plan

**Date**: January 2025  
**Purpose**: Strategic plan to achieve 90%+ test coverage for SquadOps core framework  
**Goal**: Prevent regressions during rapid AI-assisted development  

---

## 🎯 **Current Status**

### **Coverage Metrics**
- **Current Coverage**: 69% (814 statements covered)
- **Target Coverage**: 90%+ 
- **Gap to Target**: 21% (174+ statements)
- **Tests**: 63 passing, 20 failing, 83 total
- **Execution Time**: 0.25 seconds
- **Pass Rate**: 76% (63/83)

### **Test Suite Breakdown**
- **BaseAgent**: 23 tests (all passing) - Core agent functionality
- **LeadAgent**: 17 tests (all passing) - Governance and delegation
- **AuditAgent**: 10 tests (5 failing) - Monitoring and audit
- **RoleFactory**: 11 tests (all passing) - Role management
- **AgentFactory**: 11 tests (6 failing) - Agent instantiation
- **QAAgent**: 11 tests (9 failing) - Testing and QA

### **Test Categories**
- **Unit Tests**: 83 tests across 6 agent/factory types
- **Integration Tests**: Infrastructure ready (testcontainers) - not yet validated
- **Regression Tests**: Basic tests created in tests/regression/
- **Performance Tests**: Planned

---

## ✅ **Completed Work**

### **Test Infrastructure Built**
- **Unit Test Framework**: Complete pytest setup with async support
- **Mock Infrastructure**: Proper database, Redis, RabbitMQ, Ollama mocks in conftest.py
- **Test Runner**: Shell script (run_tests.sh) with multiple test levels (smoke, unit, regression, integration, all)
- **Import Path Resolution**: Fixed agent import issues for /app and agents directories
- **Test Configuration**: pytest.ini with custom markers and coverage settings

### **Test Suites Created**
- **BaseAgent**: 23 tests covering initialization, communication, database, file operations, LLM, task logging
- **LeadAgent**: 17 tests covering initialization, PRD analysis, task creation, delegation, message handling
- **AuditAgent**: 10 tests covering monitoring, audit, anomaly detection, report generation
- **RoleFactory**: 11 tests covering role loading, agent class generation, config generation, error handling
- **AgentFactory**: 11 tests covering agent creation, validation, error scenarios
- **QAAgent**: 11 tests covering testing workflows (9 failing due to syntax/import errors)

### **Integration Testing Infrastructure**
- **Testcontainers Setup**: Created tests/integration/conftest.py with PostgreSQL, RabbitMQ, Redis fixtures
- **Integration Tests**: Created tests/integration/test_agent_communication.py (not yet validated)
- **Database Schema**: Init.sql schema ready for test database

### **Documentation Created**
- **SIP-026**: Testing Framework and Philosophy protocol
- **Test Guides**: DEVELOPMENT_SAFETY_GUIDE.md, TEST_LEVEL_GUIDE.md, TEST_INTEGRITY_GUIDE.md
- **Architecture Docs**: CORE_VS_BUILD_SEPARATION.md
- **Strategic Plan**: AGENT_ASSISTED_DEVELOPMENT_ADVANCEMENT_PLAN.md
- **Test README**: Comprehensive tests/README.md with quick start

### **Coverage Achievements**
- **Starting Coverage**: 49% (before test expansion)
- **Current Coverage**: 69% (after test expansion)
- **Improvement**: +20 percentage points
- **Test Execution**: Fast (<0.3 seconds for unit tests)

---

## 🚀 **Phase 1: Fix Failing Tests (Immediate)**

**Goal**: Fix 20 failing tests to achieve 100% pass rate and improve coverage to 75-80%

### **Priority 1: QAAgent Syntax/Import Errors (9 tests failing)**
- **Issue**: QAAgent test file has syntax errors or import issues causing 9/11 tests to fail
- **Root Cause**: Likely NameError, AttributeError, or missing imports in test_qa_agent.py
- **Action**: 
  - Read test_qa_agent.py and identify syntax/import errors
  - Compare with actual QAAgent implementation in agents/roles/qa/agent.py
  - Fix test class name conflicts (TestAuditAgent instead of TestQAAgent)
  - Align test methods with actual QAAgent interface
- **Expected Gain**: +8% coverage (fix 9 tests)
- **Estimated Time**: 2-3 hours

### **Priority 2: AgentFactory Mocking Issues (6 tests failing)**
- **Issue**: Mocking recursion errors in `test_agent_factory.py`
- **Root Cause**: Mock setup for `importlib.import_module` and `getattr` causing infinite loops or incorrect returns
- **Action**: 
  - Fix mock_agent_class instantiation in test_create_agent_success
  - Ensure mock returns are properly configured before AgentFactory.create_agent call
  - Fix test_validate_instance_config_invalid_types assertion
- **Expected Gain**: +5% coverage (fix 6 tests)
- **Estimated Time**: 1-2 hours

### **Priority 3: AuditAgent Assertion Errors (5 tests failing)**
- **Issue**: Tests failing due to incorrect assertions about AuditAgent behavior
- **Root Cause**: Test expectations don't match actual AuditAgent method outputs
- **Action**: 
  - Fix test_perform_audit to call monitor_agent_activities first
  - Fix test_detect_anomalies to use audit results that trigger anomalies
  - Fix test_generate_audit_report to match actual report structure
  - Fix test_handle_activity_log to verify correct state changes
  - Fix test_handle_anomaly_alert to assert correct message routing
- **Expected Gain**: +3% coverage (fix 5 tests)
- **Estimated Time**: 1-2 hours

---

## 🎯 **Phase 2: Coverage Expansion (Next)**

### **Target Areas for 90% Coverage**

#### **1. BaseAgent (Target: 85%+)**
- **Current**: 62% coverage
- **Missing**: Error handling, connection retry logic, file operation edge cases
- **Tests Needed**: 15-20 additional tests
- **Expected Gain**: +15% coverage

#### **2. LeadAgent (Target: 90%+)**
- **Current**: 73% coverage
- **Missing**: Complex PRD scenarios, advanced task delegation, governance decisions
- **Tests Needed**: 10-15 additional tests
- **Expected Gain**: +10% coverage

#### **3. Additional Agent Types**
- **DevAgent**: Complete test suite (currently blocked by missing dependencies)
- **QAAgent**: Full test coverage
- **CommsAgent**: Message handling tests
- **DataAgent**: Data processing tests
- **Expected Gain**: +20% coverage

#### **4. Factory Classes (Target: 95%+)**
- **RoleFactory**: Edge cases, error handling
- **AgentFactory**: Complex instantiation scenarios
- **Expected Gain**: +8% coverage

---

## 🏗️ **Phase 3: Advanced Testing (Following)**

### **Integration Tests**
- **Real Agent Communication**: RabbitMQ message flow
- **Database Operations**: PostgreSQL task management
- **Service Integration**: Health check, task API
- **Expected Gain**: +5% coverage

### **Regression Tests**
- **Snapshot Testing**: Critical workflow validation
- **Contract Testing**: API interface stability
- **Behavior Testing**: Agent behavior consistency
- **Expected Gain**: +3% coverage

### **Performance Tests**
- **Load Testing**: Agent startup, message processing
- **Memory Profiling**: Resource usage monitoring
- **Expected Gain**: +2% coverage

---

## 📊 **Coverage Strategy**

### **Test Coverage Goals by Component**

| Component | Tests | Pass/Fail | Current | Target | Gap | Priority |
|-----------|-------|-----------|---------|--------|-----|----------|
| BaseAgent | 23 | 23/0 ✅ | 70%* | 85% | 15% | High |
| LeadAgent | 17 | 17/0 ✅ | 78%* | 90% | 12% | High |
| AuditAgent | 10 | 5/5 ⚠️ | 90%* | 95% | 5% | Medium |
| RoleFactory | 11 | 11/0 ✅ | 62% | 95% | 33% | High |
| AgentFactory | 11 | 5/6 ⚠️ | 66% | 95% | 29% | High |
| QAAgent | 11 | 2/9 ❌ | ~50%* | 85% | 35% | High |
| DevAgent | 0 | 0/0 | 0% | 85% | 85% | Medium |
| Other Agents | 0 | 0/0 | 0% | 80% | 80% | Low |

*Estimated based on test coverage; actual may vary due to failing tests

### **Coverage Projection**
- **Current**: 69% (814 statements covered, ~365 uncovered)
- **Phase 1 (Fix Failing Tests)**: +6-8% → 75-77% coverage
  - Fix 20 failing tests
  - Minor coverage gains from test fixes
- **Phase 2 (Expand Existing)**: +8-13% → 85-90% coverage
  - Add BaseAgent edge cases (15+ tests)
  - Add LeadAgent complex scenarios (10+ tests)
  - Expand RoleFactory/AgentFactory tests (10+ tests)
- **Phase 3 (New Coverage)**: +5-10% → 90-95% coverage
  - Add DevAgent test suite (20+ tests)
  - Add integration tests with testcontainers
  - Add regression/performance tests

---

## 🛠️ **Implementation Plan**

### **Week 1: Fix Failing Tests → 75-77% Coverage**
**Goal**: Achieve 100% test pass rate (83/83 passing)

1. **Day 1**: Fix QAAgent syntax/import errors (9 tests)
   - Read test_qa_agent.py and identify errors
   - Fix test class name (TestAuditAgent → TestQAAgent)
   - Align with actual QAAgent interface
   - Run tests: `pytest tests/unit/test_qa_agent.py -v`
   - **Target**: 11/11 QAAgent tests passing

2. **Day 2**: Fix AgentFactory mocking issues (6 tests)
   - Fix mock_agent_class setup in test_create_agent_success
   - Fix test_create_agent_attribute_error mock configuration
   - Fix test_validate_instance_config_invalid_types assertions
   - Run tests: `pytest tests/unit/test_agent_factory.py -v`
   - **Target**: 11/11 AgentFactory tests passing

3. **Day 3**: Fix AuditAgent assertion errors (5 tests)
   - Update test_perform_audit to populate agent_activity first
   - Fix test_detect_anomalies to trigger actual anomalies
   - Fix test_generate_audit_report structure assertions
   - Fix message handling tests
   - Run tests: `pytest tests/unit/test_audit_agent.py -v`
   - **Target**: 10/10 AuditAgent tests passing

4. **Day 4**: Validate all unit tests and measure coverage
   - Run full unit test suite: `pytest tests/unit/ -v`
   - Generate coverage report: `pytest tests/unit/ --cov=agents --cov-report=html`
   - **Target**: 83/83 tests passing, 75-77% coverage

5. **Day 5**: Document fixes and plan Phase 2
   - Update TEST_IMPLEMENTATION_STATUS.md
   - Identify specific coverage gaps for Phase 2
   - Create detailed test plan for BaseAgent/LeadAgent expansion

### **Week 2: Coverage Expansion → 85-90% Coverage**
**Goal**: Add 35-50 new tests for existing components

1. **Day 1-2**: BaseAgent edge cases (15-20 tests)
   - Connection failures and retry logic
   - Error handling in initialize/cleanup
   - File operation edge cases (missing dirs, permissions)
   - Command execution errors
   - LLM timeout/error handling

2. **Day 3-4**: LeadAgent complex scenarios (10-15 tests)
   - Complex PRD parsing (malformed, edge cases)
   - Advanced task delegation (multiple agents, failures)
   - Governance decisions (escalation, approval workflows)
   - Message routing edge cases

3. **Day 5**: RoleFactory/AgentFactory expansion (10+ tests)
   - RoleFactory: Missing registry, invalid YAML, template errors
   - AgentFactory: Complex configurations, validation edge cases
   - **Target**: 85-90% coverage

### **Week 3: New Agent Coverage → 90%+ Coverage**
**Goal**: Add test suites for remaining agents

1. **Day 1-2**: DevAgent test suite (20+ tests)
   - Resolve component dependencies (CodeGenerator, DockerManager, etc.)
   - Test task processing, code generation, Docker operations
   - Test file management, version management

2. **Day 3-4**: Additional agent tests (15+ tests)
   - CommsAgent: Message handling, broadcasting
   - DataAgent: Data processing, analytics
   - StratAgent: Strategic planning workflows

3. **Day 5**: Coverage validation
   - Run full test suite with coverage
   - **Target**: 90%+ coverage achieved

### **Week 4: Advanced Testing & Validation**
**Goal**: Integration tests, regression prevention, performance baselines

1. **Day 1-2**: Integration tests with testcontainers
   - Validate PostgreSQL, RabbitMQ, Redis containers
   - Test real agent-to-agent communication
   - Test database persistence and transactions

2. **Day 3-4**: Regression and snapshot tests
   - Implement snapshot testing for critical workflows
   - Add contract tests for API interfaces
   - Establish performance baselines

3. **Day 5**: Final validation and documentation
   - Run complete test suite (unit + integration + regression)
   - Update all test documentation
   - Create test maintenance guide
   - **Target**: 95%+ coverage, full test suite passing

---

## 🎯 **Success Metrics**

### **Coverage Milestones**
- **Week 1 Target**: 75-77% coverage (fix 20 failing tests, 83/83 passing)
- **Week 2 Target**: 85-90% coverage (add 35-50 tests for existing components)
- **Week 3 Target**: 90%+ coverage (add DevAgent + additional agent tests)
- **Week 4 Target**: 95%+ coverage (integration + regression + performance tests)

### **Quality Targets**
- **Test Execution**: <2 minutes for full unit suite ✅ (currently 0.25s)
- **Test Reliability**: 100% pass rate ⚠️ (currently 76% - 63/83)
- **Code Quality**: No linting errors
- **Documentation**: Complete test documentation ✅

### **Phase Exit Criteria**

**Phase 1 Complete When**:
- ✅ All 83 unit tests passing (0 failures)
- ✅ Coverage ≥75%
- ✅ All test files properly aligned with actual implementations
- ✅ Test execution <1 second for unit tests

**Phase 2 Complete When**:
- ✅ Coverage ≥85%
- ✅ BaseAgent has ≥80% coverage
- ✅ LeadAgent has ≥85% coverage
- ✅ RoleFactory/AgentFactory have ≥90% coverage
- ✅ All edge cases and error scenarios tested

**Phase 3 Complete When**:
- ✅ Coverage ≥90%
- ✅ DevAgent test suite complete (20+ tests)
- ✅ All core agents have test coverage
- ✅ Integration tests validated with testcontainers

**Phase 4 Complete When**:
- ✅ Coverage ≥95%
- ✅ Integration tests passing with real services
- ✅ Regression tests prevent breaking changes
- ✅ Performance baselines established

---

## 📝 **Immediate Next Steps**

### **Start Here (Week 1, Day 1)**
1. **Fix QAAgent tests** (Priority 1 - 9 failing tests)
   - Command: `pytest tests/unit/test_qa_agent.py -v --tb=short`
   - Read test_qa_agent.py and identify syntax/import errors
   - Fix test class name conflict (TestAuditAgent → TestQAAgent)
   - Align with actual QAAgent implementation
   - **Goal**: 11/11 tests passing

2. **Fix AgentFactory tests** (Priority 2 - 6 failing tests)
   - Command: `pytest tests/unit/test_agent_factory.py -v --tb=short`
   - Fix mock_agent_class setup and return values
   - Fix test_validate_instance_config_invalid_types assertions
   - **Goal**: 11/11 tests passing

3. **Fix AuditAgent tests** (Priority 3 - 5 failing tests)
   - Command: `pytest tests/unit/test_audit_agent.py -v --tb=short`
   - Update test expectations to match actual behavior
   - Fix assertion errors in test_perform_audit, test_detect_anomalies, etc.
   - **Goal**: 10/10 tests passing

4. **Validate and measure** (Week 1, Day 4)
   - Command: `pytest tests/unit/ --cov=agents --cov-report=term-missing --cov-report=html`
   - Confirm 83/83 tests passing (100% pass rate)
   - Measure coverage (target: 75-77%)
   - Review htmlcov/index.html to identify gaps

5. **Plan Phase 2** (Week 1, Day 5)
   - Analyze coverage report for specific missing lines
   - Create detailed test plan for BaseAgent/LeadAgent expansion
   - Update TEST_IMPLEMENTATION_STATUS.md with Phase 1 results

---

## 🏆 **Expected Outcomes**

### **Technical Benefits**
- **90%+ test coverage**: Comprehensive code validation
- **Regression prevention**: Catch breaking changes early
- **Code quality**: Maintainable, reliable codebase
- **Development speed**: Faster iteration with confidence

### **Strategic Benefits**
- **AI-assisted development**: Safe rapid iteration
- **Framework stability**: Reliable core components
- **Team confidence**: Trust in code changes
- **Production readiness**: Enterprise-grade quality

---

---

## 📊 **Progress Tracking**

### **Completed** ✅
- Test infrastructure (pytest, mocks, fixtures, test runner)
- BaseAgent test suite (23 tests, all passing)
- LeadAgent test suite (17 tests, all passing)
- RoleFactory test suite (11 tests, all passing)
- AuditAgent test suite (10 tests, 5 passing)
- AgentFactory test suite (11 tests, 5 passing)
- QAAgent test suite (11 tests, 2 passing)
- Integration test infrastructure (testcontainers)
- Comprehensive documentation (SIP-026, guides)
- Coverage improved from 49% → 69% (+20 points)

### **In Progress** 🔄
- Fixing 20 failing tests across QAAgent, AgentFactory, AuditAgent
- Aligning tests with actual agent implementations

### **Upcoming** ⏭️
- Coverage expansion to 85-90% (Phase 2)
- DevAgent test suite (Phase 3)
- Integration test validation (Phase 4)
- 90%+ coverage target (Phase 3-4)

---

**Status**: Phase 1 in progress (fixing failing tests)  
**Current Coverage**: 69% (target: 90%+)  
**Current Pass Rate**: 76% (63/83 tests passing)  
**Next Milestone**: 75-77% coverage, 100% pass rate (Week 1)  
**Timeline**: 4 weeks to 90%+ coverage  
**Updated**: January 2025

