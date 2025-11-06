# Integration Test Validation Checklist

## 🚨 CRITICAL: Integration Tests Must Use Real Services

**ANY integration test file that uses mocks is INCORRECT and violates explicit rules.**

## Pre-Commit Validation

Before committing any integration test:

1. **Search for mocks:**
   ```bash
   grep -r "from unittest.mock\|import.*Mock\|@patch\|MagicMock\|AsyncMock" tests/integration/
   ```
   **Result should be EMPTY** (except for `conftest.py` which may have configuration wrappers)

2. **Verify real services:**
   - ✅ Real PostgreSQL connections (`asyncpg.create_pool`)
   - ✅ Real RabbitMQ connections (no mock message queues)
   - ✅ Real Redis connections (no mock caches)
   - ✅ Real agent instances (no mocked BaseAgent)
   - ✅ Real adapters (no mocked SqlAdapter, Mem0Adapter, etc.)

3. **Check test names:**
   - ✅ Test names should describe actual integration scenarios
   - ❌ Tests with "mock" in name are NOT integration tests

## Definition of Integration Test

An integration test MUST:
- ✅ Use real services (PostgreSQL, RabbitMQ, Redis)
- ✅ Use real components (agents, adapters, services)
- ✅ Verify actual interactions between components
- ✅ Fail if services are unavailable (skipping is acceptable)
- ✅ Test end-to-end workflows

An integration test MUST NOT:
- ❌ Mock core components under test
- ❌ Use MagicMock/AsyncMock for primary components
- ❌ Skip integration verification
- ❌ Claim to test integration while using mocks

## Violation Detection

Run this check before committing:

```bash
# Detect mocked integration tests
python3 -c "
import os
import re

violations = []
for root, dirs, files in os.walk('tests/integration'):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            path = os.path.join(root, file)
            with open(path, 'r') as f:
                content = f.read()
                if 'from unittest.mock' in content or '@patch' in content:
                    if 'MagicMock' in content or 'AsyncMock' in content:
                        violations.append(path)

if violations:
    print('❌ VIOLATION: Integration tests using mocks:')
    for v in violations:
        print(f'  - {v}')
    exit(1)
else:
    print('✅ All integration tests use real services')
"
```

## Rules Reference

From `tests/integration/README.md`:
- **Line 238**: "Use real services - Avoid mocking external services in integration tests"
- **Line 257**: "Real Integration - Tests use actual services, not mocks"

From `SQUADOPS_BUILD_PARTNER_PROMPT.md`:
- **No deceptive simulations** - real implementation or nothing
- **Quality over speed** - never prioritize speed over correctness

## Fixing Violations

If you find mocked integration tests:

1. **Delete them immediately** - they provide false confidence
2. **Rewrite them** with real components
3. **Verify** they catch real integration issues
4. **Document** what real integration scenario they test

## Last Updated

Created: 2025-01-04
Reason: Prevent recurrence of mocked integration tests violating explicit rules

