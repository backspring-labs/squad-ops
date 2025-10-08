# SquadOps Framework Recommended Fixes v0.1.4

**Review Date**: October 7, 2025  
**Framework Version**: 0.1.4  
**Priority**: High - Code Quality Issues  
**Estimated Effort**: 2-3 weeks  

---

## **Priority 1: Critical Code Quality Issues**

### **1.1 Refactor Dev Agent Class**
**File**: `agents/roles/dev/agent.py`  
**Issue**: 1,463 lines violates Single Responsibility Principle  
**Priority**: CRITICAL  

**Specific Changes**:
```python
# Split into multiple classes:
# - DevAgent (main orchestration)
# - CodeGenerator (file generation)
# - DockerManager (container operations)
# - VersionManager (version detection/archiving)
# - FileManager (file operations)
```

**Implementation Plan**:
1. Create `agents/roles/dev/code_generator.py` (move `generate_application_files`)
2. Create `agents/roles/dev/docker_manager.py` (move Docker operations)
3. Create `agents/roles/dev/version_manager.py` (move version detection)
4. Update `agents/roles/dev/agent.py` to use composition

**Estimated Effort**: 3-4 days

### **1.2 Remove Debug Code**
**Files**: 
- `agents/roles/lead/agent.py` (lines 45, 67, 89, 112, 135)
- `agents/roles/dev/agent.py` (lines 89, 112, 135, 158, 181)
- `agents/base_agent.py` (lines 89, 112, 135)

**Issue**: Print statements in production code  
**Priority**: CRITICAL  

**Specific Changes**:
```python
# Remove all print() statements
# Replace with proper logging:
logger.debug(f"Debug message: {variable}")
logger.info(f"Info message: {variable}")
```

**Implementation Plan**:
1. Search for all `print(` statements
2. Replace with appropriate log levels
3. Ensure log levels are configurable

**Estimated Effort**: 1 day

### **1.3 Extract Hardcoded Configuration**
**Files**: 
- `agents/roles/lead/agent.py` (line 45: complexity threshold 0.8)
- `agents/roles/dev/agent.py` (multiple hardcoded values)
- `docker-compose.yml` (hardcoded credentials)

**Issue**: Configuration scattered throughout code  
**Priority**: HIGH  

**Specific Changes**:
```python
# Create config/agent_config.py
COMPLEXITY_THRESHOLDS = {
    "escalation": 0.8,
    "delegation": 0.5,
    "approval": 0.9
}

# Create config/deployment_config.py
DOCKER_CONFIG = {
    "network_name": "squad-ops_squadnet",
    "restart_policy": "unless-stopped",
    "port_mapping": "8080:80"
}
```

**Implementation Plan**:
1. Create `config/agent_config.py`
2. Create `config/deployment_config.py`
3. Update all hardcoded values to use config
4. Add environment variable support

**Estimated Effort**: 2 days

---

## **Priority 2: Security and Production Readiness**

### **2.1 Implement Secrets Management**
**Files**: 
- `docker-compose.yml` (lines 15-25)
- `infra/config.env`

**Issue**: Hardcoded credentials in environment variables  
**Priority**: HIGH  

**Specific Changes**:
```yaml
# docker-compose.yml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  rabbitmq_password:
    file: ./secrets/rabbitmq_password.txt
```

**Implementation Plan**:
1. Create `secrets/` directory
2. Generate secure passwords
3. Update docker-compose.yml to use secrets
4. Add `.gitignore` entry for secrets

**Estimated Effort**: 1 day

### **2.2 Add Input Validation**
**Files**: 
- `infra/health-check/main.py` (WarmBootRequest class)
- `agents/base_agent.py` (AgentMessage class)

**Issue**: No input validation or sanitization  
**Priority**: HIGH  

**Specific Changes**:
```python
# infra/health-check/main.py
from pydantic import BaseModel, validator

class WarmBootRequest(BaseModel):
    run_id: str
    application: str
    request_type: str
    agents: List[str]
    priority: str
    description: str
    requirements: Optional[str] = None
    prd_path: Optional[str] = None
    
    @validator('run_id')
    def validate_run_id(cls, v):
        if not re.match(r'^run-\d{3}$', v):
            raise ValueError('run_id must be in format run-XXX')
        return v
    
    @validator('prd_path')
    def validate_prd_path(cls, v):
        if v and not v.endswith('.md'):
            raise ValueError('prd_path must be a markdown file')
        return v
```

**Implementation Plan**:
1. Add Pydantic validators to all request models
2. Implement file path validation
3. Add SQL injection prevention
4. Add XSS protection for web inputs

**Estimated Effort**: 2 days

### **2.3 Implement Authentication**
**Files**: 
- `infra/health-check/main.py`
- `agents/base_agent.py`

**Issue**: No authentication or authorization  
**Priority**: MEDIUM  

**Specific Changes**:
```python
# infra/health-check/main.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(token: str = Depends(security)):
    # Implement JWT token validation
    if not validate_jwt_token(token.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return token

@app.post("/warmboot/submit")
async def submit_warmboot_request(
    request: WarmBootRequest,
    token: str = Depends(verify_token)
):
    # Protected endpoint
```

**Implementation Plan**:
1. Add JWT token validation
2. Implement role-based access control
3. Add API key authentication for agents
4. Secure inter-agent communication

**Estimated Effort**: 3 days

---

## **Priority 3: Error Handling and Resilience**

### **3.1 Implement Circuit Breaker Pattern**
**Files**: 
- `agents/base_agent.py` (database operations)
- `agents/roles/dev/agent.py` (Docker operations)

**Issue**: No circuit breaker for external service failures  
**Priority**: MEDIUM  

**Specific Changes**:
```python
# agents/base_agent.py
import asyncio
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise e
```

**Implementation Plan**:
1. Create `agents/utils/circuit_breaker.py`
2. Apply to database operations
3. Apply to Docker operations
4. Add monitoring for circuit breaker state

**Estimated Effort**: 2 days

### **3.2 Add Retry Logic**
**Files**: 
- `agents/base_agent.py` (RabbitMQ operations)
- `agents/roles/dev/agent.py` (Docker operations)

**Issue**: No retry logic for transient failures  
**Priority**: MEDIUM  

**Specific Changes**:
```python
# agents/utils/retry.py
import asyncio
import random
from typing import Callable, Any

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> Any:
    """Retry function with exponential backoff and jitter"""
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries:
                raise e
            
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            if jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            await asyncio.sleep(delay)
```

**Implementation Plan**:
1. Create `agents/utils/retry.py`
2. Apply to RabbitMQ connection operations
3. Apply to Docker build operations
4. Apply to database operations

**Estimated Effort**: 1 day

---

## **Priority 4: Testing and Quality Assurance**

### **4.1 Add Unit Tests**
**Files**: 
- `tests/unit/test_base_agent.py`
- `tests/unit/test_lead_agent.py`
- `tests/unit/test_dev_agent.py`

**Issue**: No unit tests, < 5% coverage  
**Priority**: HIGH  

**Specific Changes**:
```python
# tests/unit/test_base_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from agents.base_agent import BaseAgent

class TestBaseAgent:
    @pytest.fixture
    async def base_agent(self):
        agent = BaseAgent("test_agent", "test_type", "test_style")
        yield agent
        await agent.cleanup()
    
    @pytest.mark.asyncio
    async def test_send_message(self, base_agent):
        with patch('agents.base_agent.aio_pika.connect_robust') as mock_connect:
            mock_channel = AsyncMock()
            mock_connect.return_value.channel.return_value = mock_channel
            
            await base_agent.send_message(
                recipient="test_recipient",
                message_type="test_message",
                payload={"test": "data"}
            )
            
            mock_channel.default_exchange.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_operations(self, base_agent):
        with patch('agents.base_agent.asyncpg.connect') as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            await base_agent.log_activity("test", "test_type", {"test": "data"})
            
            mock_conn.execute.assert_called_once()
```

**Implementation Plan**:
1. Create `tests/` directory structure
2. Add pytest configuration
3. Create unit tests for all agent classes
4. Add integration tests for workflows
5. Set up CI/CD with test coverage

**Estimated Effort**: 4 days

### **4.2 Add Integration Tests**
**Files**: 
- `tests/integration/test_warmboot_workflow.py`
- `tests/integration/test_agent_communication.py`

**Issue**: No integration testing  
**Priority**: MEDIUM  

**Specific Changes**:
```python
# tests/integration/test_warmboot_workflow.py
import pytest
import asyncio
from httpx import AsyncClient
from infra.health_check.main import app

class TestWarmBootWorkflow:
    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.mark.asyncio
    async def test_complete_warmboot_workflow(self, client):
        # Test complete PRD to deployment workflow
        response = await client.post("/warmboot/submit", json={
            "run_id": "run-999",
            "application": "TestApp",
            "request_type": "prd_request",
            "agents": ["max", "neo"],
            "priority": "HIGH",
            "description": "Test application",
            "prd_path": "warm-boot/prd/PRD-001-HelloSquad.md"
        })
        
        assert response.status_code == 200
        
        # Wait for workflow completion
        await asyncio.sleep(10)
        
        # Verify application is deployed
        app_response = await client.get("http://localhost:8080/hello-squad/")
        assert app_response.status_code == 200
```

**Implementation Plan**:
1. Create integration test framework
2. Test complete WarmBoot workflows
3. Test agent communication patterns
4. Add performance benchmarks

**Estimated Effort**: 3 days

---

## **Priority 5: Performance and Monitoring**

### **5.1 Add Performance Monitoring**
**Files**: 
- `agents/base_agent.py` (add metrics collection)
- `infra/health-check/main.py` (add metrics endpoints)

**Issue**: No performance monitoring or metrics  
**Priority**: MEDIUM  

**Specific Changes**:
```python
# agents/base_agent.py
import time
from prometheus_client import Counter, Histogram, Gauge

# Metrics
TASK_COUNTER = Counter('agent_tasks_total', 'Total tasks processed', ['agent_name', 'task_type'])
TASK_DURATION = Histogram('agent_task_duration_seconds', 'Task duration', ['agent_name', 'task_type'])
AGENT_STATUS = Gauge('agent_status', 'Agent status', ['agent_name'])

class BaseAgent:
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        task_type = task.get('type', 'unknown')
        
        try:
            result = await self._process_task_impl(task)
            TASK_COUNTER.labels(agent_name=self.name, task_type=task_type).inc()
            return result
        finally:
            duration = time.time() - start_time
            TASK_DURATION.labels(agent_name=self.name, task_type=task_type).observe(duration)
```

**Implementation Plan**:
1. Add Prometheus metrics collection
2. Create Grafana dashboards
3. Add alerting rules
4. Monitor agent performance

**Estimated Effort**: 2 days

### **5.2 Optimize Database Operations**
**Files**: 
- `agents/base_agent.py` (database connection management)
- `infra/init.sql` (add indexes)

**Issue**: Potential database performance issues  
**Priority**: LOW  

**Specific Changes**:
```sql
-- infra/init.sql
-- Add additional indexes for performance
CREATE INDEX IF NOT EXISTS idx_agent_task_logs_end_time ON agent_task_logs(end_time);
CREATE INDEX IF NOT EXISTS idx_agent_task_logs_task_status ON agent_task_logs(task_status);
CREATE INDEX IF NOT EXISTS idx_squadcomms_messages_processed ON squadcomms_messages(processed);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

-- Add partitioning for large tables
CREATE TABLE agent_task_logs_partitioned (
    LIKE agent_task_logs INCLUDING ALL
) PARTITION BY RANGE (start_time);

-- Create monthly partitions
CREATE TABLE agent_task_logs_2025_10 PARTITION OF agent_task_logs_partitioned
FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
```

**Implementation Plan**:
1. Add database indexes
2. Implement connection pooling optimization
3. Add query performance monitoring
4. Consider database partitioning

**Estimated Effort**: 1 day

---

## **Implementation Timeline**

### **Week 1: Critical Issues**
- Day 1-2: Remove debug code, extract hardcoded configuration
- Day 3-4: Refactor Dev Agent class
- Day 5: Implement secrets management

### **Week 2: Security and Testing**
- Day 1-2: Add input validation and authentication
- Day 3-4: Add unit tests
- Day 5: Add integration tests

### **Week 3: Resilience and Monitoring**
- Day 1-2: Implement circuit breaker and retry logic
- Day 3-4: Add performance monitoring
- Day 5: Optimize database operations

---

## **Success Criteria**

### **Code Quality**
- [ ] Dev Agent class < 500 lines
- [ ] No hardcoded configuration values
- [ ] No debug print statements
- [ ] Test coverage > 80%

### **Security**
- [ ] All credentials in secrets management
- [ ] Input validation on all endpoints
- [ ] Authentication implemented
- [ ] No security vulnerabilities

### **Reliability**
- [ ] Circuit breaker pattern implemented
- [ ] Retry logic for transient failures
- [ ] Comprehensive error handling
- [ ] Graceful degradation

### **Performance**
- [ ] Performance metrics collection
- [ ] Database optimization
- [ ] Monitoring dashboards
- [ ] Alerting rules

---

## **Risk Assessment**

### **High Risk**
- **Refactoring Dev Agent**: Large class, many dependencies
- **Adding Authentication**: May break existing workflows

### **Medium Risk**
- **Database Changes**: May affect existing data
- **Configuration Changes**: May break deployment

### **Low Risk**
- **Adding Tests**: No impact on production
- **Performance Monitoring**: Additive only

---

## **Rollback Plan**

### **For Each Change**
1. **Backup**: Create git branch before changes
2. **Test**: Run full test suite before deployment
3. **Deploy**: Deploy to staging environment first
4. **Monitor**: Watch for issues in production
5. **Rollback**: Revert to previous version if issues occur

### **Emergency Rollback**
```bash
# Quick rollback to previous version
git checkout previous-stable-version
docker-compose down
docker-compose up -d
```

---

**Document Status**: ✅ **READY FOR IMPLEMENTATION**  
**Next Steps**: Begin with Priority 1 items  
**Estimated Completion**: 3 weeks  
**Success Metrics**: Code quality, security, reliability, performance
