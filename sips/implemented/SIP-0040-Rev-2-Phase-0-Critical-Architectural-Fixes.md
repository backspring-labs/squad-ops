---
sip_uid: "17642554775954486"
sip_number: 40
title: "Rev-2-Phase-0-Critical-Architectural-Fixes"
status: "implemented"
author: "SquadOps Build Partner"
approver: "None"
created_at: "2025-01-XX"
updated_at: "2025-11-27T10:12:48.900946Z"
original_filename: "SIP-040-REV2-PHASE0-ARCHITECTURAL-FIXES.md"
---

# SIP-040 Rev 2 Phase 0: Critical Architectural Fixes

**Author:** SquadOps Build Partner  
**Date:** 2025-01-XX  
**Status:** Draft - **HIGH PRIORITY**  
**Relates:** SIP-040 (Capability System MVP), SIP-046 (Agent Specs)  
**Supersedes:** SIP-040 MVP (v0.6.0)

---

## 1) Purpose

Fix **critical architectural violations** where business logic is hardcoded in agents instead of being encapsulated in capabilities. This violates SIP-040 principles where agents should be thin routing layers and capabilities should contain all business logic.

**Priority:** **CRITICAL** - Must be completed before multi-agent expansion to prevent architectural debt from compounding.

---

## 2) Scope

### 2.1 LeadAgent Violations

**Current State:** Business logic hardcoded in `handle_agent_request()` method

**Violations:**
- `governance.approval` - Hardcoded in lines 128-142
- `governance.escalation` - Hardcoded in lines 143-151
- `governance.task_coordination` - Hardcoded in lines 110-127
- `validate.warmboot` - Special handling instead of capability (lines 152-175)

**Problem:** These capabilities are defined in `catalog.yaml` and bound to Max in `capability_bindings.yaml`, but implemented as hardcoded logic in the agent instead of proper capability classes.

### 2.2 DevAgent Violations

**Current State:** Business logic methods in agent class

**Violations:**
- `_create_documentation` (lines 625-670, ~46 lines) - Should use `comms.documentation` capability
- `_emit_developer_completion_event` (lines 533-623, ~91 lines) - Should be a capability
- `_create_technical_requirements` (lines 132-205, ~74 lines) - Dead code? Check usage

**Problem:** These methods contain business logic that should be in capabilities, making agents harder to test and violating separation of concerns.

---

## 3) Motivation

### 3.1 Architectural Violations

**SIP-040 Principle:** Agents are thin routing layers that delegate to capabilities. Capabilities contain all business logic.

**Current Reality:**
- LeadAgent contains ~72 lines of governance business logic
- DevAgent contains ~156-230 lines of business logic methods
- Capabilities defined in catalog but not implemented as classes
- Agents contain routing AND business logic (violation)

### 3.2 Impact

**Technical Debt:**
- Hard to test agent logic separately from business logic
- Difficult to reuse governance logic in other agents
- Violates single responsibility principle
- Makes multi-agent expansion harder (more violations to fix)

**Code Quality:**
- ~228 lines of business logic in wrong place
- Inconsistent with rest of codebase
- Makes codebase harder to understand

### 3.3 Benefits

1. **Architectural Compliance**: Business logic in capabilities, agents are thin routers
2. **Testability**: Capabilities can be tested independently
3. **Reusability**: Governance capabilities can be used by other agents
4. **Maintainability**: Clear separation of concerns
5. **Multi-Agent Ready**: Clean architecture for adding remaining 7 agents

---

## 4) Specification

### 4.1 New Capability Classes

**LeadAgent Capabilities:**
1. `agents/capabilities/governance_approval.py` - `GovernanceApproval` class
   - Implements `governance.approval` capability
   - Extracts logic from LeadAgent lines 128-142
   - Handles complexity threshold checks and approval decisions

2. `agents/capabilities/governance_escalation.py` - `GovernanceEscalation` class
   - Implements `governance.escalation` capability
   - Extracts logic from LeadAgent lines 143-151
   - Handles task escalation to premium consultation

3. `agents/capabilities/governance_task_coordination.py` - `GovernanceTaskCoordination` class
   - Implements `governance.task_coordination` capability
   - Extracts logic from LeadAgent lines 110-127
   - Coordinates task delegation across squad

4. Verify `validate.warmboot` - Check if `wrapup_generator.py` handles this or create `warmboot_validator.py`

**DevAgent Capabilities:**
5. `agents/capabilities/task_completion_emitter.py` - `TaskCompletionEmitter` class
   - Extracts `_emit_developer_completion_event` from DevAgent
   - Handles completion event emission to Max
   - Calculates task duration, hashes artifacts, extracts reasoning

6. `agents/capabilities/documentation_creator.py` - `DocumentationCreator` class
   - Implements `comms.documentation` capability (already in catalog.yaml)
   - Replaces `_create_documentation` method in DevAgent
   - Creates task documentation files

7. Check `_create_technical_requirements` usage - Extract to capability if used, or remove if dead code

### 4.2 Capability Structure

Each capability class follows standard pattern:

```python
class GovernanceApproval:
    """
    Governance Approval - Implements governance.approval capability
    
    Processes approval requests and makes governance decisions.
    """
    
    def __init__(self, agent_instance):
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
        # Access agent's escalation_threshold if needed
    
    async def approve(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process approval request.
        
        Implements the governance.approval capability.
        
        Args:
            request: Request dictionary with 'complexity' key
            
        Returns:
            Dictionary containing:
            - approved: Boolean approval decision
            - decision: Decision type ('approved' or 'escalated')
            - approval_time: Time taken for decision
        """
        # Extracted business logic here
```

### 4.3 Agent Refactoring

**LeadAgent Changes:**
- Remove hardcoded logic from `handle_agent_request()` (lines 107-178)
- Replace with single `capability_loader.execute()` call
- Remove special handling for governance capabilities

**DevAgent Changes:**
- Remove `_create_documentation` method (use `comms.documentation` capability)
- Remove `_emit_developer_completion_event` method (use new capability)
- Remove `_create_technical_requirements` if unused
- Update `_handle_task_delegation` to use capabilities

---

## 5) Implementation Plan

### Step 1: Create Governance Capabilities

1. Create `agents/capabilities/governance_approval.py`
   - Extract approval logic from LeadAgent lines 128-142
   - Handle complexity threshold checks
   - Return proper capability result format

2. Create `agents/capabilities/governance_escalation.py`
   - Extract escalation logic from LeadAgent lines 143-151
   - Call `agent.escalate_task()` method
   - Return proper capability result format

3. Create `agents/capabilities/governance_task_coordination.py`
   - Extract coordination logic from LeadAgent lines 110-127
   - Use `task.determine_target` capability for delegation
   - Send messages via agent's `send_message()` method
   - Return proper capability result format

4. Verify `validate.warmboot`
   - Check if `wrapup_generator.py` already handles this
   - If not, create `warmboot_validator.py` capability

### Step 2: Create DevAgent Capabilities

5. Create `agents/capabilities/task_completion_emitter.py`
   - Extract `_emit_developer_completion_event` from DevAgent
   - Handle task duration calculation
   - Handle artifact hashing (SHA256)
   - Extract reasoning summaries
   - Send completion events to Max

6. Create `agents/capabilities/documentation_creator.py`
   - Implement `comms.documentation` capability
   - Replace `_create_documentation` method
   - Create markdown documentation files
   - Return proper capability result format

7. Check `_create_technical_requirements` usage
   - Search codebase for references
   - If used, extract to capability or use `build.requirements.generate`
   - If unused, remove dead code

### Step 3: Update CapabilityLoader

8. Update `CapabilityLoader.CAPABILITY_MAP` to include new capabilities:
   ```python
   'governance.approval': ('agents.capabilities.governance_approval', 'GovernanceApproval', 'approve'),
   'governance.escalation': ('agents.capabilities.governance_escalation', 'GovernanceEscalation', 'escalate'),
   'governance.task_coordination': ('agents.capabilities.governance_task_coordination', 'GovernanceTaskCoordination', 'coordinate'),
   'task.completion.emit': ('agents.capabilities.task_completion_emitter', 'TaskCompletionEmitter', 'emit'),
   'comms.documentation': ('agents.capabilities.documentation_creator', 'DocumentationCreator', 'create'),
   ```

### Step 4: Refactor Agents

9. Update `LeadAgent.handle_agent_request()`
   - Remove hardcoded if/elif chains (lines 107-178)
   - Replace with single `capability_loader.execute()` call
   - Remove special handling for governance capabilities

10. Update `DevAgent._handle_task_delegation()`
    - Replace `_create_documentation` call with `comms.documentation` capability
    - Replace `_emit_developer_completion_event` call with `task.completion.emit` capability
    - Remove method definitions

11. Remove unused methods from DevAgent
    - Delete `_create_documentation` method
    - Delete `_emit_developer_completion_event` method
    - Delete `_create_technical_requirements` if unused

### Step 5: Update Tests

12. Update `tests/unit/test_lead_agent.py`
    - Update tests to expect capability-based execution
    - Mock capability loader instead of agent methods
    - Test governance capabilities independently

13. Update integration tests
    - Verify governance capabilities work end-to-end
    - Verify DevAgent capabilities work end-to-end

---

## 6) Key Files

### New Files

**Capabilities:**
- `agents/capabilities/governance_approval.py`
- `agents/capabilities/governance_escalation.py`
- `agents/capabilities/governance_task_coordination.py`
- `agents/capabilities/task_completion_emitter.py`
- `agents/capabilities/documentation_creator.py`
- `agents/capabilities/warmboot_validator.py` (if needed)

### Modified Files

**Core:**
- `agents/capabilities/loader.py` - Add new capabilities to `CAPABILITY_MAP`
- `agents/roles/lead/agent.py` - Remove hardcoded governance logic (~72 lines)
- `agents/roles/dev/agent.py` - Remove hardcoded methods (~156-230 lines)

**Tests:**
- `tests/unit/test_lead_agent.py` - Update for capability-based execution
- `tests/integration/test_workflow.py` - Verify capabilities work end-to-end

---

## 7) Code Reduction Estimate

### LeadAgent (`agents/roles/lead/agent.py`)
- Hardcoded governance logic: ~72 lines → 0 lines
- **Total: ~72 lines removed (~9% reduction)**

### DevAgent (`agents/roles/dev/agent.py`)
- `_create_documentation`: ~46 lines → 0 lines
- `_emit_developer_completion_event`: ~91 lines → 0 lines
- `_create_technical_requirements`: ~74 lines → 0 lines (if unused)
- **Total: ~137-211 lines removed (~17-26% reduction)**

### Combined
- **Total reduction: ~209-283 lines** from agents
- **New capability classes: ~300-400 lines** (properly organized)
- **Net: Cleaner architecture, better separation of concerns**

---

## 8) Risks & Mitigation

**Risk 1: Breaking existing functionality**
- **Mitigation:** Test each capability independently before removing agent code
- **Mitigation:** Keep agent methods temporarily, call capabilities, then remove

**Risk 2: Missing dependencies**
- **Mitigation:** Capabilities access agent methods (e.g., `send_message()`, `escalate_task()`)
- **Mitigation:** Pass agent instance to capability constructor

**Risk 3: Test failures**
- **Mitigation:** Update tests incrementally
- **Mitigation:** Run full test suite after each capability extraction

---

## 9) Success Criteria

- ✅ All governance capabilities implemented as proper classes
- ✅ All DevAgent business logic extracted to capabilities
- ✅ LeadAgent `handle_agent_request()` is < 50 lines (thin router)
- ✅ DevAgent business logic methods removed
- ✅ All capabilities registered in `CAPABILITY_MAP`
- ✅ All existing tests pass
- ✅ Integration tests verify capabilities work end-to-end
- ✅ No hardcoded business logic in agents

---

## 10) Timeline

**Estimated Effort:** 1-2 days

**Breakdown:**
- Create governance capabilities: 4-6 hours
- Create DevAgent capabilities: 4-6 hours
- Refactor agents: 2-3 hours
- Update tests: 2-3 hours
- Integration testing: 1-2 hours

---

## 11) Related Work

- **SIP-040 MVP**: Original capability system implementation
- **SIP-040 Rev 3**: Decorator-based refactoring (future enhancement)
- **SIP-046**: Agent specs and configuration

---

**Status:** Draft - **HIGH PRIORITY** - Should be completed before multi-agent expansion


