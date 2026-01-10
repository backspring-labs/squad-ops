# Agent Lifecycle

This diagram shows the FSM-based agent lifecycle, state transitions, and lifecycle hooks.

```mermaid
stateDiagram-v2
    [*] --> STARTING: Agent Initialization

    STARTING --> READY: to_ready()<br/>Initialization Complete
    STARTING --> CRASHED: crash()<br/>Initialization Failed

    READY --> WORKING: start_work()<br/>Task Received
    READY --> STOPPING: stop()<br/>Shutdown Requested

    WORKING --> READY: complete_work()<br/>Task Completed
    WORKING --> BLOCKED: block()<br/>Waiting for Dependency
    WORKING --> CRASHED: crash()<br/>Fatal Error

    BLOCKED --> WORKING: unblock()<br/>Dependency Resolved
    BLOCKED --> CRASHED: crash()<br/>Fatal Error

    CRASHED --> STOPPING: stop()<br/>Recovery/Shutdown

    STOPPING --> [*]: Cleanup Complete

    note right of STARTING
        on_agent_start()
        Initialize connections
        Load capabilities
        Setup queues
    end note

    note right of READY
        Agent ready for tasks
        Listening to queues
        Sending heartbeats
    end note

    note right of WORKING
        on_task_start()
        Processing TaskEnvelope
        Executing capability
        on_task_complete()
    end note

    note right of BLOCKED
        Waiting for:
        - Task dependency
        - External resource
        - Agent response
    end note

    note right of CRASHED
        on_exception()
        on_failure()
        Error logged
        May attempt recovery
    end note
```

## Lifecycle Hooks

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Hooks as LifecycleHookManager
    participant Emitter as EventEmitter
    participant Store as CycleDataStore

    Note over Agent,Store: Agent Startup
    Agent->>Hooks: on_agent_start(context)
    Hooks->>Emitter: emit(agent_started)
    Emitter->>Store: Log event (if cycle_id available)

    Note over Agent,Store: Cycle Start
    Agent->>Hooks: on_cycle_start(context)
    Hooks->>Emitter: emit(cycle_started)
    Emitter->>Store: Log event

    Note over Agent,Store: Task Processing
    Agent->>Hooks: on_task_created(context)
    Hooks->>Emitter: emit(task_created)
    Agent->>Hooks: on_task_start(context)
    Hooks->>Emitter: emit(task_started)
    Agent->>Agent: Execute capability
    Agent->>Hooks: on_task_complete(context)
    Hooks->>Emitter: emit(task_completed)
    Emitter->>Store: Log event

    Note over Agent,Store: Task Failure
    Agent->>Hooks: on_task_failed(context, error)
    Hooks->>Emitter: emit(task_failed)
    Agent->>Hooks: on_exception(context, error)
    Hooks->>Emitter: emit(exception)
    Emitter->>Store: Log event

    Note over Agent,Store: Cycle End
    Agent->>Hooks: on_cycle_end(context)
    Hooks->>Emitter: emit(cycle_ended)
    Emitter->>Store: Log event

    Note over Agent,Store: Agent Shutdown
    Agent->>Hooks: on_agent_stop(context)
    Hooks->>Emitter: emit(agent_stopped)
    Emitter->>Store: Log event
```

## State Transitions

### Allowed Transitions

| From State | Trigger | To State | Description |
|------------|---------|----------|-------------|
| STARTING | `to_ready()` | READY | Initialization successful |
| STARTING | `crash()` | CRASHED | Initialization failed |
| READY | `start_work()` | WORKING | Task received |
| READY | `stop()` | STOPPING | Shutdown requested |
| WORKING | `complete_work()` | READY | Task completed successfully |
| WORKING | `block()` | BLOCKED | Waiting for dependency |
| WORKING | `crash()` | CRASHED | Fatal error occurred |
| BLOCKED | `unblock()` | WORKING | Dependency resolved |
| BLOCKED | `crash()` | CRASHED | Fatal error occurred |
| CRASHED | `stop()` | STOPPING | Recovery or shutdown |
| STOPPING | (cleanup) | [*] | Agent terminated |

### Invalid Transitions

- Any transition not listed above will raise `MachineError`
- Auto-transitions are disabled for safety
- State validation ensures agents follow proper lifecycle

## Lifecycle Events

### Event Structure

All lifecycle events include:
- `event_type`: Type of event (e.g., "agent_started", "task_completed")
- `agent_id`: Agent identifier
- `project_id`: Project identifier
- `cycle_id`: Execution cycle identifier
- `pulse_id`: Pulse identifier (if applicable)
- `task_id`: Task identifier (if applicable)
- `correlation_id`: Correlation identifier
- `causation_id`: Causation identifier
- `trace_id`: Distributed tracing identifier
- `span_id`: Span identifier
- `timestamp`: Event timestamp
- `metadata`: Additional event metadata

### Event Flow

1. **Lifecycle Hook Called**: Agent calls hook method (e.g., `on_task_start`)
2. **Context Built**: Hook builds context with full lineage fields
3. **Event Created**: `StructuredEvent` created from context
4. **Event Emitted**: Event sent to `EventEmitter`
5. **Event Logged**: Event logged to CycleDataStore (if cycle_id available)
6. **Non-Blocking**: Event emission is async and fail-safe

## State Entry Callbacks

When entering a state, the agent:
1. Logs the transition to CycleDataStore
2. Records previous and new lifecycle state
3. Includes cycle_id and task_id in transition log
4. Updates agent status in health check system

## Error Handling

- **FSM Errors**: Invalid transitions raise `MachineError`
- **Hook Errors**: Hook failures are logged but don't break execution
- **Event Emission Errors**: Event emission failures are non-fatal
- **Crash Recovery**: Agents can transition from CRASHED to STOPPING for cleanup

## Lifecycle State Properties

- **lifecycle_state**: Current state from FSM (read-only property)
- **state**: Internal FSM state (managed by Transitions library)
- **current_task**: Currently executing task ID
- **lifecycle_fsm**: FSM machine instance


