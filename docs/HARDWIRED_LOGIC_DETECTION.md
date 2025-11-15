# Hardwired Logic Detection Guide

## Problem: Why Wasn't This Caught?

When we refactored `DevAgent.process_task()` to use generic capability routing, we updated its unit tests to verify generic routing. However, `LeadAgent.process_task()` still had hardcoded logic, and its tests were **validating the wrong behavior** - they were testing that the hardcoded logic worked, not that it was removed.

## Anti-Patterns to Detect

### 1. Hardcoded Task Type Checks in `process_task()`

**BAD - Hardwired Logic:**
```python
async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
    task_type = task.get('type', 'unknown')
    
    if task_type == "governance":
        return await self._handle_governance_task(task)
    elif task_type == "warmboot_wrapup":
        return await self._handle_wrapup_task(task)
    elif task_type == "development":
        return await self._handle_development_task(task)
    else:
        return await self._handle_generic_task(task)
```

**GOOD - Generic Routing:**
```python
async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
    capability_name = self.capability_loader.get_capability_for_task(task)
    if not capability_name:
        return {'status': 'error', 'error': 'No capability mapping found'}
    
    args = self.capability_loader.prepare_capability_args(capability_name, task)
    return await self.capability_loader.execute(capability_name, self, *args)
```

### 2. Hardcoded Action Checks

**BAD:**
```python
requirements = task.get('requirements', {})
action = requirements.get('action')

if action == "build":
    return await self._handle_build(task)
elif action == "deploy":
    return await self._handle_deploy(task)
```

**GOOD:**
```python
# Action is resolved via get_capability_for_task() which checks TASK_TO_CAPABILITY_MAP
capability_name = self.capability_loader.get_capability_for_task(task)
```

### 3. Hardcoded Escalation/Complexity Logic

**BAD:**
```python
complexity = task.get('complexity', 0.5)
if complexity > self.escalation_threshold:
    await self.escalate_task(task_id, task)
    return {'status': 'escalated'}
else:
    # Process normally
```

**GOOD:**
```python
# Escalation logic should be in governance.escalation capability
# Agent just routes to capability
capability_name = self.capability_loader.get_capability_for_task(task)
```

### 4. Hardcoded Delegation Logic

**BAD:**
```python
if task_type == "development":
    target = "dev-agent"
elif task_type == "testing":
    target = "qa-agent"
else:
    target = "dev-agent"  # default

await self.send_message(recipient=target, ...)
```

**GOOD:**
```python
# Delegation should use task.determine_target capability
delegation_result = await self.capability_loader.execute(
    'task.determine_target', self, task_type
)
target = delegation_result.get('target_agent')
```

## Test Patterns to Detect Hardwired Logic

### ❌ BAD Test - Validates Hardcoded Behavior

```python
def test_process_task_governance(self):
    task = {'task_id': 'task-001', 'type': 'governance'}
    result = await agent.process_task(task)
    
    # ❌ Testing hardcoded behavior
    assert result['status'] == 'completed'
    assert 'governance_decision' in result  # Hardcoded response format
    # Missing: No verification that capability routing was used
```

### ✅ GOOD Test - Validates Generic Routing

```python
def test_process_task_governance(self):
    task = {'task_id': 'task-001', 'type': 'governance'}
    
    # Mock capability routing
    agent.capability_loader.get_capability_for_task = MagicMock(
        return_value='governance.task_coordination'
    )
    agent.capability_loader.prepare_capability_args = MagicMock(
        return_value=(task,)
    )
    agent.capability_loader.execute = AsyncMock(return_value={
        'status': 'completed',
        'task_id': 'task-001'
    })
    
    result = await agent.process_task(task)
    
    # ✅ Verify generic routing was used
    agent.capability_loader.get_capability_for_task.assert_called_once_with(task)
    agent.capability_loader.prepare_capability_args.assert_called_once()
    agent.capability_loader.execute.assert_called_once()
    assert result['status'] == 'completed'
```

## Detection Checklist

When reviewing `process_task()` implementations, check for:

- [ ] **No hardcoded `if task_type == X` checks** - Should use `get_capability_for_task()`
- [ ] **No hardcoded `if requirements.action == X` checks** - Should use capability mapping
- [ ] **No direct method calls based on task type** - Should use `capability_loader.execute()`
- [ ] **No hardcoded escalation logic** - Should be in `governance.escalation` capability
- [ ] **No hardcoded delegation logic** - Should use `task.determine_target` capability
- [ ] **Tests verify `get_capability_for_task()` is called** - Not just that result is correct
- [ ] **Tests verify `prepare_capability_args()` is called** - Ensures calling conventions are used
- [ ] **Tests verify `capability_loader.execute()` is called** - Ensures capability execution

## Code Review Questions

1. **Does `process_task()` have any `if task_type ==` or `elif task_type ==` statements?**
   - If yes → **HARDWIRED LOGIC DETECTED** ❌

2. **Does `process_task()` call methods like `_handle_X_task()` based on task type?**
   - If yes → **HARDWIRED LOGIC DETECTED** ❌

3. **Do the unit tests verify that `get_capability_for_task()` was called?**
   - If no → **TEST VALIDATES WRONG BEHAVIOR** ❌

4. **Do the unit tests mock `capability_loader.execute()`?**
   - If no → **TEST VALIDATES WRONG BEHAVIOR** ❌

## Current Status

### ✅ Agents Using Generic Routing
- `DevAgent.process_task()` - Fully generic
- `LeadAgent.process_task()` - Now fully generic (after refactor)

### ❌ Agents Still Using Hardwired Logic
- `DevopsAgent.process_task()` - Has `if task_type == "devops_task"`
- `CreativeAgent.process_task()` - Has multiple `if task_type ==` checks
- `FinanceAgent.process_task()` - Has `if 'budget' in task_type.lower()`
- `StratAgent.process_task()` - No hardcoded checks, but doesn't use capability routing
- `CuratorAgent.process_task()` - No hardcoded checks, but doesn't use capability routing
- `DataAgent.process_task()` - Unknown (needs review)
- `CommsAgent.process_task()` - Unknown (needs review)
- `QAAgent.process_task()` - Unknown (needs review)

### ⚠️ Agents Using Hardwired Logic in `handle_agent_request()`
All agents have hardcoded `if action == X` checks in `handle_agent_request()`. These should also be refactored to use generic routing via `prepare_capability_args()`.

## Action Items

1. **Create linter rule** to detect hardcoded task type checks
2. **Update test templates** to always verify capability routing
3. **Add code review checklist** item for hardwired logic detection
4. **Refactor remaining agents** to use generic routing
5. **Update all unit tests** to verify generic routing, not hardcoded behavior

