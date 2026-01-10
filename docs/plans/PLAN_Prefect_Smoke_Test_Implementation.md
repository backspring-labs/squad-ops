---
name: Prefect Smoke Test Implementation
overview: Implement a Prefect-based smoke integration test that validates Prefect integration with SquadOps by orchestrating tasks across all 5 core roles (Lead, Strategy, Dev, QA, Data) using Prefect flows.
todos:
  - id: create-role-dispatch-helper
    content: Create tests/integration/support/role_dispatch.py with execute_role_task() function that reads instances.yaml, creates tasks via runtime-api, sends RabbitMQ messages, and polls for completion
    status: pending
  - id: create-pulse-context-helper
    content: Add helper function to create pulse context in test setup using create_pulse_context() from agents.context.pulse_context
    status: pending
  - id: create-prefect-flow
    content: Create prefect_smoke_flow() with 5 Prefect tasks (planning_phase, design_phase, implementation_phase, verification_phase, wrapup_phase) in tests/integration/test_prefect_smoke_flow_end_to_end.py
    status: pending
    dependencies:
      - create-role-dispatch-helper
  - id: implement-phase-tasks
    content: Implement each of the 5 Prefect task functions to call execute_role_task() with appropriate role and task_type, and return structured results
    status: pending
    dependencies:
      - create-role-dispatch-helper
  - id: create-main-test
    content: Create test_prefect_smoke_flow_end_to_end() test function with setup (cycle creation, pulse creation, role validation), flow execution, and comprehensive assertions
    status: pending
    dependencies:
      - create-prefect-flow
      - create-pulse-context-helper
  - id: add-test-markers
    content: Add @pytest.mark.integration and @pytest.mark.smoke markers to test function
    status: pending
    dependencies:
      - create-main-test
  - id: add-error-handling
    content: Add error handling for missing roles, agent timeouts, and task failures with clear error messages
    status: pending
    dependencies:
      - create-main-test
  - id: validate-test-execution
    content: Verify test can be run successfully and meets performance target (<30s)
    status: pending
    dependencies:
      - add-error-handling
      - add-test-markers
---

# Prefect Smoke Test Implementation Plan

## Overview

Implement a smoke integration test that validates Prefect integration with SquadOps 0.8.0 by executing a Prefect flow that orchestrates tasks across all 5 core roles.

## Key Files to Create/Modify

### 1. Prefect Flow Definition

**File:** `tests/integration/test_prefect_smoke_flow.py`

Create a Prefect flow with 5 tasks, one per role:

- `planning_phase` → Lead role
- `design_phase` → Strategy role  
- `implementation_phase` → Dev role
- `verification_phase` → QA role
- `wrapup_phase` → Data role

Each Prefect task will:

- Resolve role → agent_id from `instances.yaml`
- Create a SquadOps task via runtime-api
- Send a message to the agent via RabbitMQ
- Poll for task completion
- Return task results

### 2. Test Helper Module

**File:** `tests/support/role_dispatch.py` (or `tests/integration/support/role_dispatch.py`)

Create helper function `execute_role_task()` that:

- Takes role, task_type, cycle_id, pulse_id, inputs
- Reads `instances.yaml` to map role → agent_id
- Creates task via runtime-api (`POST /api/v1/tasks/start`)
- Sends task delegation message to agent via RabbitMQ
- Polls task status via adapter until completion
- Returns task result as dict

**Constraints:**

- Must use existing runtime-api endpoints
- Must not create new core runtime modules
- Must read role mapping from `instances.yaml`

### 3. Main Integration Test

**File:** `tests/integration/test_prefect_smoke_flow_end_to_end.py`

Test function `test_prefect_smoke_flow_end_to_end()` that:

- Sets up test environment (validates instances.yaml has all 5 roles)
- Creates cycle via runtime-api (`POST /api/v1/execution-cycles`)
- Creates pulse context via `create_pulse_context()`
- Executes Prefect flow programmatically
- Asserts:
  - Prefect flow completed successfully
  - All 5 tasks exist with correct cycle_id/pulse_id
  - Each task has role ∈ {Lead, Strategy, Dev, QA, Data}
  - All tasks have status = completed
  - Each task has non-empty result payload
  - Data role output references prior phases

**Markers:**

- `@pytest.mark.integration`
- `@pytest.mark.smoke`

### 4. Dependencies & Configuration

**Required:**

- Prefect package (already in requirements)
- Access to runtime-api (localhost:8001 or configured)
- Access to RabbitMQ (for agent messaging)
- Valid `instances.yaml` with all 5 roles mapped
- Agents deployed and reachable

**Configuration:**

- Use `TASKS_BACKEND=prefect` environment variable
- Runtime-api URL from config or environment

## Implementation Details

### Role-to-Agent Resolution

Read `agents/instances/instances.yaml` and map:

- `lead` → agent_id (e.g., "max")
- `strat` → agent_id (e.g., "nat")  
- `dev` → agent_id (e.g., "neo")
- `qa` → agent_id (e.g., "eve")
- `data` → agent_id (e.g., "data")

### Task Creation Flow

1. Create task via `POST /api/v1/tasks/start` with:

   - `task_id`: unique ID (e.g., `prefect_smoke_planning_{timestamp}`)
   - `cycle_id`: from flow parameter
   - `agent_id`: resolved from role
   - `task_name`: e.g., `prefect_smoke_planning`
   - `description`: phase-specific description
   - `status`: "started"

2. Send RabbitMQ message to agent's comms queue:

   - Queue: `{agent_id}_comms`
   - Message type: `task_delegation`
   - Payload: task dict with task_id, cycle_id, task_type, description

3. Poll task status via adapter:

   - Use `get_task(task_id)` from adapter
   - Check `status` field
   - Wait until status = "completed" or timeout (30s max)

4. Return task result:

   - Extract artifacts/outputs from task
   - Return as dict for Prefect task result

### Prefect Flow Structure

```python
@flow
def prefect_smoke_flow(cycle_id: str, pulse_id: str) -> None:
    plan = planning_phase(cycle_id, pulse_id)
    design_phase(cycle_id, pulse_id, plan)
    implementation_phase(cycle_id, pulse_id, plan)
    verification_phase(cycle_id, pulse_id)
    wrapup_phase(cycle_id, pulse_id)
```

### Task Artifacts/Outputs

Each role should produce simple JSON-like output:

- **Lead**: `{"summary": "Plan for Prefect smoke run", "steps": [...]}`
- **Strategy**: `{"design": "Brief design note", "references_plan": true}`
- **Dev**: `{"implementation": "Implementation note", "status": "done"}`
- **QA**: `{"verification": "PASS", "notes": "All checks passed"}`
- **Data**: `{"summary": "Wrap-up summary", "phases_executed": 5, "roles": [...]}`

## Error Handling

- **Missing role mapping**: Fail fast with clear error message
- **Agent unreachable**: Timeout after 30s, fail with clear error
- **Task creation failure**: Raise exception, fail test
- **Prefect flow failure**: Let exception bubble up

## Performance Target

- Complete in < 30 seconds on typical dev machine
- Fast enough for CI pipeline regression checks

## Testing Strategy

1. **Unit test helper** (optional): Test `execute_role_task()` with mocks
2. **Integration test**: Full end-to-end with real agents
3. **CI integration**: Run on every main branch commit

## Files Summary

**New Files:**

- `tests/integration/test_prefect_smoke_flow_end_to_end.py` - Main test
- `tests/integration/support/role_dispatch.py` - Helper for role-based task execution
- `tests/integration/support/__init__.py` - Package init

**Modified Files:**

- None (test-only changes, no core runtime modifications)

## Definition of Done

1. Test passes reliably on correctly configured environment
2. Test marked with `@pytest.mark.integration` and `@pytest.mark.smoke`
3. All 5 roles execute via normal agent pipeline (no mocks at flow level)
4. Uses `instances.yaml` for role mapping (no hardcoded agent IDs)
5. No new core runtime APIs created solely for this test
6. Clear failure messages distinguish: Prefect wiring, role mapping, agent execution
7. Can be run from Cursor, CI, and as first-line regression check








