# IDEA — Mercenary Agent Model (External Specialist Integration)

## Context

In evaluating the integration of OpenClaw into SquadOps, it is important to distinguish between:

- core disciplined agents (aligned to SquadOps operating model)
- external specialist agents (highly capable, but not aligned with governance)

This IDEA proposes a classification:

> OpenClaw should be treated as a “Mercenary Agent” — a bounded, external specialist capability — not a core SquadOps agent.

---

## Core Insight

Some systems provide value precisely because they are optimized for a narrow objective, even if they:

- do not follow SquadOps protocols
- have their own runtime assumptions
- do not align with governance or orchestration

Attempting to deeply integrate such systems introduces:

- abstraction conflicts
- authority ambiguity
- duplicated orchestration
- fragility

Instead, they should be explicitly constrained.

---

## Definition — Mercenary Agent

A Mercenary Agent is:

> an external, capability-rich system invoked for specific missions, not part of command structure.

---

## Characteristics

- not part of squad hierarchy
- no orchestration authority
- not a system of record
- no planning/governance role
- strict interface boundary
- scoped task invocation
- outputs must be normalized

---

## When to Use

- channel integrations (Slack, Discord, etc.)
- local assistant behavior
- rapid capability reuse
- experimentation
- edge-node interactions

---

## When NOT to Use

- orchestration
- planning/strategy
- governance
- memory ownership
- long-running control loops

---

## Integration Model

SquadOps Workload → Routing → Wrapper Agent → OpenClaw → Normalized Output → Evidence

---

## Guardrails

### Input Boundaries
- sanitize inputs
- restrict scope

### Output Normalization
- structured output
- metadata attached

### No Direct Access
- no memory / orchestration / registry access

### Observability
- logs, traceability, evidence

### Revocability
- removable without impact

---

## Architectural Positioning

| Capability        | SquadOps | OpenClaw |
|------------------|---------|----------|
| Orchestration    | Yes     | No       |
| Governance       | Yes     | No       |
| Memory           | Yes     | No       |
| Planning         | Yes     | No       |
| Execution        | Yes     | Yes      |
| Channels         | Optional| Strong   |

---

## Design Principle

Do not let a powerful specialist redefine your architecture.

---

## Implementation Guidance

- thin wrapper agent
- llm=None
- HTTP interface
- capability: edge.openclaw.*
- enforce timeouts and retries

---

## Strategic Value

- fast experimentation
- no tight coupling
- replaceable integration
- preserves system discipline

---

## One-Line Summary

OpenClaw is best used as a mercenary: highly capable, tightly scoped, and never in command.
