# Agent Design Architecture

This diagram shows the hierarchical structure of the SquadOps agent system, from the base agent class through roles, capabilities, and skills.

```mermaid
graph TB
    subgraph BaseAgent["BaseAgent Class"]
        LLM[LLM Client]
        Memory[Memory Providers]
        Telemetry[Telemetry Client]
        FSM[Lifecycle FSM]
        Config[Configuration]
        RabbitMQ[RabbitMQ Connection]
        Postgres[PostgreSQL Pool]
        Redis[Redis Client]
    end

    subgraph Roles["Agent Roles"]
        Lead[Lead Agent<br/>Governance]
        Dev[Dev Agent<br/>Developer]
        Strat[Strat Agent<br/>Strategy]
        QA[QA Agent<br/>Quality Assurance]
        Data[Data Agent<br/>Analytics]
        Finance[Finance Agent<br/>Finance & Ops]
        Comms[Comms Agent<br/>Communications]
        Curator[Curator Agent<br/>R&D & Curation]
        Creative[Creative Agent<br/>Creative Design]
        Audit[Audit Agent<br/>Monitoring & Audit]
        DevOps[DevOps Agent<br/>DevOps Engineer]
    end

    subgraph Capabilities["Capability System"]
        TaskCap[task.create<br/>task.delegate]
        BuildCap[build.artifact<br/>docker.build]
        GovCap[governance.approval<br/>governance.escalation]
        QACap[qa.test_design<br/>qa.test_execution]
        DataCap[data.collect_cycle_snapshot<br/>data.profile_cycle_metrics]
        ProductCap[product.draft_prd_from_prompt<br/>product.validate_acceptance_criteria]
        CommsCap[comms.chat<br/>comms.documentation]
    end

    subgraph Skills["Skill System"]
        DevSkills[dev.architect_prompt<br/>dev.developer_prompt]
        LeadSkills[lead.prd_analysis_prompt<br/>lead.build_requirements_prompt]
        ProductSkills[product.format_prd_prompt<br/>product.parse_prd_acceptance_criteria]
        QASkills[qa.compare_app_output_to_criteria]
        SharedSkills[shared.text_match]
    end

    subgraph Instances["Agent Instances"]
        Max[Max - Lead]
        Neo[Neo - Dev]
        Nat[Nat - Strat]
        Eve[Eve - QA]
        DataAgent[Data - Analytics]
    end

    BaseAgent --> Roles
    Roles --> Capabilities
    Capabilities --> Skills
    Roles --> Instances

    Lead --> GovCap
    Lead --> TaskCap
    Dev --> BuildCap
    Dev --> TaskCap
    Strat --> ProductCap
    QA --> QACap
    Data --> DataCap

    BuildCap --> DevSkills
    GovCap --> LeadSkills
    ProductCap --> ProductSkills
    QACap --> QASkills
    ProductCap --> SharedSkills

    Max -.->|implements| Lead
    Neo -.->|implements| Dev
    Nat -.->|implements| Strat
    Eve -.->|implements| QA
    DataAgent -.->|implements| Data

    style BaseAgent fill:#e1f5ff
    style Roles fill:#fff4e1
    style Capabilities fill:#e8f5e9
    style Skills fill:#f3e5f5
    style Instances fill:#fce4ec
```

## Component Details

### BaseAgent Core Components

- **LLM Client**: Routes to configured LLM provider (Ollama, OpenAI, etc.)
- **Memory Providers**: LanceDBAdapter for agent-level memory, SqlAdapter for Squad Memory Pool
- **Telemetry Client**: Platform-aware telemetry (OpenTelemetry, AWS, Azure, GCP, Null)
- **Lifecycle FSM**: State machine managing agent lifecycle (STARTING, READY, WORKING, BLOCKED, CRASHED, STOPPING)
- **Configuration**: Centralized config loading from `config/` directory
- **RabbitMQ Connection**: Message queue for inter-agent communication
- **PostgreSQL Pool**: Database connection for task logging and cycle data
- **Redis Client**: Caching and coordination

### Role System

Roles are defined in `agents/roles/registry.yaml` and include:
- **Lead**: Governance and coordination (reasoning_style: governance)
- **Dev**: Code generation and architecture (reasoning_style: deductive)
- **Strat**: Product strategy and planning (reasoning_style: abductive)
- **QA**: Testing and security (reasoning_style: counterfactual)
- **Data**: Analytics and insights (reasoning_style: inductive)
- And more...

### Capability System

Capabilities are reusable functions that agents can execute. They are:
- Defined in `agents/capabilities/catalog.yaml`
- Bound to agents via `agents/capability_bindings.yaml`
- Loaded dynamically via `CapabilityLoader`
- Executed with agent instance context

### Skill System

Skills are lower-level building blocks used by capabilities:
- Domain-specific (dev, lead, product, qa, shared)
- Deterministic or non-deterministic
- Reusable across multiple capabilities
- Defined in `agents/skills/registry.yaml`

### Agent Instances

Agent instances are configured in `agents/instances/instances.yaml`:
- Each instance has an ID, display name, role, and model
- Instances implement roles and inherit their capabilities
- Multiple instances can share the same role


