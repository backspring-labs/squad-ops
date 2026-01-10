---
sip_uid: 01KEM71ECN6QGY4NXPHZ8VYG7E
sip_number: null
title: Queue Transport Layer — Queue Adapter + Provider Loading + Capabilities + Secrets/Profiles
status: proposed
author: Framework Committee
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-10T15:05:29Z'
original_filename: SIP-QUEUE-TRANSPORT-LAYER-0_8_4.md
---
# SIP-QUEUE-TRANSPORT-LAYER — Version Target 0.8.x  
## Queue Adapter + Provider Loading + Capabilities + Secrets/Profiles (RabbitMQ Now, Cloud Later)

# 1. Purpose and Intent

This SIP defines a single, end-to-end **Queue Transport Layer** for SquadOps that:

- standardizes task message transport behind a **QueueAdapter** interface,
- ensures agents and core runtime remain **transport-agnostic** (no RabbitMQ/SQS/Service Bus/Pub/Sub awareness),
- provides **config-driven provider loading** via deployment profiles,
- introduces a **capabilities contract** to prevent accidental reliance on provider-specific semantics,
- integrates with the SquadOps **Secrets Provider** (`secret://` references) for credentials,
- establishes a clean boundary for future cloud transports **without implementing them yet**.

The intent is to make "RabbitMQ locally" and "something else in a target cloud" a **deployment profile decision**, not an application rewrite.

# 2. Background

SquadOps currently delivers tasks to agent containers via **RabbitMQ** queues. In 0.8.x, SquadOps is also establishing a strict **ACI TaskEnvelope** contract and stronger SDLC rigor around contracts and portability. Messaging portability differs from DB portability: different queue providers have meaningfully different semantics (ack, retry, ordering, DLQ, delay).

This SIP defines the abstraction boundary required to preserve ACI behavior while allowing transport substitution later.

# 3. Problem Statements

1. Task delivery is coupled to RabbitMQ-specific logic and semantics.
2. There is no transport-neutral interface for publish/consume/ack/retry/health checks.
3. A future cloud deployment would require touching multiple codepaths unless the boundary exists now.
4. Provider differences (ordering, retries, delays, message limits) can cause subtle drift unless made explicit.
5. Credentials for brokers risk ending up as defaults or literals in repo without a standardized secrets approach.

# 4. Scope

## In Scope (0.8.x)
- Define a **QueueAdapter** interface and transport-neutral `QueueMessage` wrapper.
- Implement **RabbitMQQueueAdapter** using existing RabbitMQ code paths.
- Define a **provider factory** that loads the adapter based on deployment profile configuration.
- Define a **capabilities contract** for adapters and require runtime enforcement where relevant.
- Refactor runtime dispatch and agent container receive loops to use QueueAdapter only.
- Integrate broker credentials via **SIP-SECRETS-MANAGEMENT** secret references.
- Add unit + integration tests for the adapter boundary and ACI payload discipline.

## Out of Scope (0.8.x)
- Implementing SQS, Azure Service Bus, or GCP Pub/Sub adapters.
- Changing ACI TaskEnvelope schema or lineage immutability rules.
- Introducing complex routing topologies (topic exchanges, fanout, shared-queue routing) beyond current per-agent queues.
- Implementing SOC Ledger ingestion (structured events remain separate).

# 5. Design Overview

## 5.1 Contract Boundary (Normative)

- Runtime publishes **TaskEnvelope JSON only** via QueueAdapter.
- Agent container consumes **TaskEnvelope JSON only** via QueueAdapter.
- Agents remain transport-agnostic; they process TaskEnvelope and emit TaskResult per ACI.

## 5.2 Provider Loading (Normative)

A deployment profile selects a provider. The factory instantiates exactly one adapter:

- `comms.provider`: logical provider ID (e.g., `rabbitmq`)
- `comms.provider_class`: dotted path to adapter class (explicit is preferred in 0.8.x)

The factory uses `importlib` to load the class and construct it with provider-specific settings.

## 5.3 Capabilities Contract (Normative)

Adapters expose `capabilities()` so runtime components do not accidentally rely on semantics not supported by the active provider.

Examples of semantics that vary across providers:
- delayed delivery / delay queues
- FIFO ordering
- message priority
- max message size
- DLQ / redrive support

# 6. Functional Requirements

## 6.1 QueueAdapter Interface (Required)

All adapters MUST implement:

- `publish(queue_name: str, payload_json: str, *, headers: dict | None = None, delay_seconds: int | None = None) -> None`
- `consume(queue_name: str, *, max_messages: int = 1, wait_seconds: int = 0) -> list[QueueMessage]`
- `ack(message: QueueMessage) -> None`
- `retry(message: QueueMessage, *, delay_seconds: int | None = None) -> None`
- `ensure_queue(queue_name: str, *, options: dict | None = None) -> None`
- `health() -> QueueHealth`
- `capabilities() -> QueueCapabilities`

Transport-neutral wrapper types:

- `QueueMessage`
  - `payload_json: str`
  - `headers: dict`
  - `receipt_handle: str | None` (provider-specific handle; opaque)
  - `message_id: str | None`
- `QueueHealth`
  - `is_healthy: bool`
  - `details: dict`
- `QueueCapabilities`
  - `supports_delay: bool`
  - `supports_fifo: bool`
  - `supports_priority: bool`
  - `supports_dlq: bool`
  - `max_message_bytes: int`

## 6.2 Payload Contract (Normative)

- Payload MUST be **ACI TaskEnvelope JSON only**.
- Adapters MUST NOT mutate TaskEnvelope identity or lineage fields.
- Transport headers MUST NOT be placed into TaskEnvelope `inputs`.
- Serialization/deserialization MUST round-trip without mutation.

## 6.3 Secrets Integration (Normative)

All broker credentials MUST be provided via SIP-SECRETS-MANAGEMENT:

- config uses `secret://` references (no literal passwords)
- adapter factory resolves secrets via `SecretsProvider`
- secret values MUST NOT be logged

## 6.4 Queue Naming and Topology (0.8.x Default)

- Default queue mode: **per-agent task queues**
- Queue naming MUST be centralized (single helper) and MUST include optional `comms.namespace`.

Example (illustrative):
- `{namespace}.{agent_id}.tasks`

The naming helper must be used consistently by publisher and consumer paths.

# 7. Non-Functional Requirements

1. **Reliability**: no silent drops; publish/consume failures surface as explicit errors.
2. **Integrity**: TaskEnvelope JSON is not modified in transport.
3. **Portability**: provider changes are isolated to deployment profile + adapter.
4. **Observability**: boundary logs at publish/consume/ack/retry (no secret values).
5. **Discipline**: runtime checks capabilities when using optional features (delay/priority/fifo).

# 8. Config and Deployment Profile Contract

Deployment profiles MUST support:

- `comms.provider` (e.g., `rabbitmq`)
- `comms.provider_class` (dotted path to adapter class)
- `comms.namespace` (optional)
- `comms.queue.mode` (default `per_agent`)

Provider-specific blocks (0.8.x RabbitMQ only):

- `comms.rabbitmq.host`
- `comms.rabbitmq.port`
- `comms.rabbitmq.vhost`
- `comms.rabbitmq.username`
- `comms.rabbitmq.password` = `secret://rabbitmq_password`
- `comms.rabbitmq.tls.enabled` (optional)
- `comms.rabbitmq.tls.ca_bundle_path` (optional)

# 9. Implementation Considerations

## 9.1 Code Placement (Normative)

- `infra/comms/queue_adapter.py` — interface + shared types
- `infra/comms/adapter_factory.py` — provider loading, config validation, secrets resolution
- `infra/comms/rabbitmq_adapter.py` — RabbitMQQueueAdapter implementation
- `infra/comms/queue_naming.py` — canonical queue naming helpers

## 9.2 RabbitMQ Semantics (0.8.x)

- `ack()` maps to message acknowledgement.
- `retry()` maps to deliberate requeue behavior:
  - if delay is requested and not supported, adapter must either:
    - fail explicitly, or
    - perform an immediate retry and log capability mismatch (implementation decision must be consistent).
- `ensure_queue()` may be a no-op if queues are provisioned by compose/infra, but MUST exist.

## 9.3 Capability Enforcement (Normative)

Any component requesting advanced behavior MUST check adapter capabilities first.

Examples:
- If `delay_seconds` is used:
  - require `supports_delay == True`
- If priority is configured:
  - require `supports_priority == True`
- If payload exceeds `max_message_bytes`:
  - fail fast with a clear error (future work may introduce payload externalization).

## 9.4 Future Cloud Providers (Non-Implementation Note)

Later adapters may be added behind the same contract:
- `SQSQueueAdapter` (AWS)
- `AzureServiceBusQueueAdapter` (Azure)
- `GcpPubSubQueueAdapter` (GCP)

These providers differ materially; capabilities are required to avoid semantic drift.

# 10. Testing Requirements

## 10.1 Unit Tests (Required)
- Adapter factory loads provider via `provider_class`
- Secrets resolution for adapter config using `secret://` references
- Queue naming helper outputs stable names across publisher/consumer
- Capabilities contract returns expected values for RabbitMQ adapter
- Payload integrity: TaskEnvelope JSON is unchanged after publish/consume serialization boundary

## 10.2 Integration Tests (Required)
- End-to-end publish → consume → ack using RabbitMQ in local/dev profile
- Validate payload is TaskEnvelope JSON only
- Validate that agents consume through QueueAdapter path (no direct RabbitMQ calls)
- Canary test path compatible with ACI smoke test harness (API → DB → Queue → Agent)

# 11. Executive Summary — What Must Be Built

- QueueAdapter interface + shared types
- RabbitMQQueueAdapter implementation
- Adapter factory with explicit class loading + secrets resolution
- Capabilities contract + enforcement points
- Canonical queue naming helper
- Unit and integration tests validating publish/consume/ack and payload integrity

# 12. Definition of Done

- [ ] QueueAdapter interface exists and is used everywhere for task transport.
- [ ] RabbitMQQueueAdapter implements required operations and capabilities.
- [ ] Adapter factory loads adapter via deployment profile (`comms.provider_class`).
- [ ] All RabbitMQ credentials use `secret://` references; no literals in repo.
- [ ] Runtime dispatch uses QueueAdapter only.
- [ ] Agent container receive loop uses QueueAdapter only.
- [ ] TaskEnvelope JSON roundtrip tests confirm no mutation.
- [ ] Integration test validates publish → consume → ack with RabbitMQ.
- [ ] Capability checks exist where advanced features are invoked (delay/priority/fifo).

# 13. Appendix

## A. Example Deployment Profile (RabbitMQ Local)
```
comms:
  provider: rabbitmq
  provider_class: infra.comms.rabbitmq_adapter.RabbitMQQueueAdapter
  namespace: local
  queue:
    mode: per_agent
  rabbitmq:
    host: localhost
    port: 5672
    vhost: /
    username: squadops
    password: secret://rabbitmq_password
```

## B. Capability Defaults (RabbitMQ — Illustrative)
- supports_delay: false (unless a delay topology is explicitly provisioned)
- supports_fifo: false
- supports_priority: optional (depends on queue declaration)
- supports_dlq: optional (depends on queue declaration)
- max_message_bytes: provider-defined (set conservatively and enforce)
