# Communication Flow

This diagram shows how agents communicate, how tasks are routed, and how capabilities are invoked.

```mermaid
sequenceDiagram
    participant Console as Console/Gateway
    participant RabbitMQ as RabbitMQ
    participant LeadAgent as Lead Agent
    participant DevAgent as Dev Agent
    participant CapLoader as CapabilityLoader
    participant Capability as Capability
    participant RuntimeAPI as Runtime API

    Note over Console,RuntimeAPI: Console Chat Flow
    Console->>RabbitMQ: Send comms.chat message<br/>(agent_name_comms queue)
    RabbitMQ->>LeadAgent: Deliver message
    LeadAgent->>CapLoader: Resolve capability
    CapLoader->>Capability: Execute comms.chat
    Capability->>RabbitMQ: Send response<br/>(console_responses queue)
    RabbitMQ->>Console: Deliver response

    Note over Console,RuntimeAPI: Task Execution Flow
    LeadAgent->>RuntimeAPI: Create execution cycle
    RuntimeAPI->>RuntimeAPI: Store cycle in DB
    LeadAgent->>RabbitMQ: Send TaskEnvelope<br/>(agent_name_tasks queue)
    RabbitMQ->>DevAgent: Deliver TaskEnvelope
    DevAgent->>DevAgent: Validate envelope
    DevAgent->>DevAgent: Transition to WORKING
    DevAgent->>CapLoader: Resolve capability from task_type
    CapLoader->>Capability: Execute capability<br/>(e.g., build.artifact)
    Capability->>RuntimeAPI: Update task status
    Capability-->>DevAgent: Return result
    DevAgent->>RuntimeAPI: Log task completion
    DevAgent->>DevAgent: Transition to READY
    DevAgent->>RabbitMQ: Send TaskResult

    Note over Console,RuntimeAPI: Task Delegation Flow
    LeadAgent->>CapLoader: Execute task.delegate
    CapLoader->>Capability: Execute delegation
    Capability->>Capability: Determine target agent
    Capability->>RabbitMQ: Send TaskEnvelope<br/>(target_agent_tasks queue)
    RabbitMQ->>DevAgent: Deliver TaskEnvelope
    DevAgent->>RabbitMQ: Send acknowledgment<br/>(lead_agent_comms queue)
    RabbitMQ->>LeadAgent: Deliver acknowledgment
```

## Queue Architecture

```mermaid
graph LR
    subgraph RabbitMQ["RabbitMQ Message Broker"]
        TaskQueues["Task Queues<br/>{agent}_tasks"]
        CommsQueues["Comms Queues<br/>{agent}_comms"]
        BroadcastQueue["Broadcast Queue<br/>squad_broadcast"]
        ConsoleQueue["Console Queue<br/>console_responses"]
    end

    subgraph Agents["Agents"]
        Lead[Lead Agent]
        Dev[Dev Agent]
        Strat[Strat Agent]
        QA[QA Agent]
    end

    Lead -->|TaskEnvelope| TaskQueues
    Dev -->|TaskEnvelope| TaskQueues
    Strat -->|TaskEnvelope| TaskQueues
    QA -->|TaskEnvelope| TaskQueues

    Lead -->|AgentMessage| CommsQueues
    Dev -->|AgentMessage| CommsQueues
    Strat -->|AgentMessage| CommsQueues
    QA -->|AgentMessage| CommsQueues

    Lead -->|Broadcast| BroadcastQueue
    Dev -->|Broadcast| BroadcastQueue
    Strat -->|Broadcast| BroadcastQueue
    QA -->|Broadcast| BroadcastQueue

    Lead -->|Response| ConsoleQueue
    Dev -->|Response| ConsoleQueue
```

## Capability Invocation Flow

```mermaid
flowchart TD
    Start[Agent Receives Request] --> Validate{Validate<br/>Request}
    Validate -->|Invalid| Reject[Reject Request]
    Validate -->|Valid| Extract[Extract Action]
    Extract --> Resolve[CapabilityLoader<br/>Resolve Capability]
    Resolve -->|Not Found| Error[Return Error]
    Resolve -->|Found| CheckBinding{Check<br/>Capability Binding}
    CheckBinding -->|Bound to Other Agent| Delegate[Delegate to<br/>Other Agent]
    CheckBinding -->|Bound to Self| Prepare[Prepare Arguments<br/>Based on Convention]
    Prepare --> Execute[Execute Capability<br/>with Agent Instance]
    Execute --> Result[Return Result]
    Result --> UpdateStatus[Update Task Status<br/>via Runtime API]
    UpdateStatus --> End[Complete]

    style Start fill:#e1f5ff
    style Execute fill:#e8f5e9
    style Result fill:#fff4e1
```

## Message Types

### TaskEnvelope
- **Format**: JSON serialized ACI TaskEnvelope
- **Queue**: `{agent_id}_tasks`
- **Purpose**: Task execution requests
- **Fields**: task_id, agent_id, cycle_id, task_type, inputs, lineage fields

### AgentMessage
- **Format**: JSON serialized AgentMessage dataclass
- **Queue**: `{agent_id}_comms` or `squad_broadcast`
- **Purpose**: Inter-agent communication
- **Fields**: sender, recipient, message_type, payload, context, timestamp, message_id

### AgentRequest
- **Format**: JSON with action, payload, metadata
- **Queue**: `{agent_id}_comms`
- **Purpose**: Capability invocation requests
- **Fields**: action (capability name), payload, metadata (pid, cycle_id, etc.)

## Routing Rules

1. **Task Routing**:
   - TaskEnvelope routed to `{agent_id}_tasks` queue
   - Agent processes from its own task queue
   - TaskResult returned via same mechanism

2. **Capability Routing**:
   - Capability name resolved via `CapabilityLoader`
   - Binding checked in `capability_bindings.yaml`
   - If bound to different agent, task delegated
   - If bound to self, capability executed directly

3. **Message Routing**:
   - Direct messages: `{recipient}_comms` queue
   - Broadcast messages: `squad_broadcast` queue
   - Console responses: `console_responses` queue

4. **Console Chat Routing**:
   - Gateway sends to `{agent_name}_comms` queue
   - Agent processes via `comms.chat` capability
   - Response sent to `console_responses` queue
   - Gateway matches response via correlation_id


