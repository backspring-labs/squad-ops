# SquadOps Architecture Diagrams

This directory contains comprehensive Mermaid diagrams documenting the SquadOps multi-agent system architecture.

## Diagram Overview

### 1. [Agent Design Architecture](agent-design.md)
Shows the hierarchical structure of the agent system:
- BaseAgent class and core components
- Role system (lead, dev, strat, qa, data, etc.)
- Capability system and bindings
- Skill system (reusable building blocks)
- Agent instances configuration

### 2. [Data Model](data-model.md)
Documents the data structures and storage:
- Database schema (projects, cycle, agent_task_log)
- CycleDataStore file system structure
- Memory system (LanceDB and SQL adapters)
- Task models and relationships

### 3. [Communication Flow](communication-flow.md)
Shows inter-agent communication patterns:
- RabbitMQ queue architecture
- TaskEnvelope routing
- Capability invocation flow
- Task delegation patterns
- Console chat flow

### 4. [System Overview](system-overview.md)
High-level architecture view:
- Infrastructure components
- Agent containers and relationships
- Cycle execution flow
- External interfaces

### 5. [Agent Lifecycle](agent-lifecycle.md)
Documents the FSM-based lifecycle:
- Lifecycle states and transitions
- Lifecycle hooks
- Event emission flow

## Viewing the Diagrams

These diagrams use Mermaid syntax and can be viewed in:
- GitHub (renders Mermaid automatically)
- VS Code with Mermaid preview extensions
- Online Mermaid editors (https://mermaid.live/)
- Documentation tools that support Mermaid (MkDocs, Docusaurus, etc.)

## Diagram Conventions

- Node IDs use camelCase or underscores (no spaces)
- Special characters in labels are quoted
- Color styling is omitted (uses theme defaults)
- Diagrams reference actual code structure from the codebase


