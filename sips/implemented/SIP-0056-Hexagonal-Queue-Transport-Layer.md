---
sip_uid: 01KFR7F1T4XMPE08BBT50VQ7MB
sip_number: 56
title: Hexagonal Queue Transport Layer
status: implemented
author: Framework Committee (Refactored for Hexagonal)
approver: null
created_at: '2026-01-24T00:00:00Z'
updated_at: '2026-01-24T19:40:31.171190Z'
original_filename: SIP-Queue-Transport-Layer-0-8-4.md
---
# SIP-0055: Hexagonal Queue Transport Layer

**Status:** Proposed (DDD/0.8.4 Refactor)
**Version:** 0.8.4
**Author:** Framework Committee (Refactored for Hexagonal)
**Refers to:** SIP-0054 (Hexagonal Secrets Isolation)

---

## 1. Purpose and Intent
This SIP refactors the Queue Transport Layer into a **Hexagonal (Ports and Adapters)** architecture. The goal is to isolate Domain Logic (Agent Tasking) from Infrastructure Logic (RabbitMQ/Cloud Messaging).

- **Standardizes** task transport behind a Domain-level `QueuePort`.
- **Enforces DDD Boundaries**: The Core and Agents remain strictly transport-agnostic.
- **Config-Driven Loading**: Adapters are loaded via deployment profiles, facilitating the "RabbitMQ locally / Cloud later" strategy.
- **Secrets Integration**: Credentials must be resolved via the `SecretStorePort` defined in SIP-0054.

## 2. Background & DDD Pivot
SquadOps is transitioning to a strict separation of concerns. Messaging portability differs from DB portability due to provider-specific semantics (ack, retry, ordering). In 0.8.4, the **Domain** defines the interface ("How we talk"), and the **Infrastructure** implements the delivery ("The wires").



## 3. Problem Statements
1. **Domain Leaks**: Task delivery is currently coupled to RabbitMQ-specific logic.
2. **Missing Abstraction**: No transport-neutral interface exists in the `src/domain/ports` layer.
3. **Rigid Implementation**: Changing providers requires touching core runtime logic.
4. **Secret Exposure**: Broker credentials risk literal exposure without a standardized secrets approach.

## 4. Scope

### In Scope (0.8.4)
- **Define the Port**: Establish `src/domain/ports/queue_port.py` as a Python Protocol.
- **Define the Message Contract**: Establish `src/domain/models/queue_message.py` as a transport-neutral wrapper.
- **Implement the Adapter**: Create `src/infrastructure/adapters/comms/rabbitmq_adapter.py`.
- **Implement the Factory**: Create a DDD-compliant `AdapterFactory` that resolves secrets via the `SecretStorePort`.
- **Unit + Integration Tests**: Focus on payload integrity and port-to-adapter mapping.

### Out of Scope
- Implementing SQS, Azure Service Bus, or GCP Pub/Sub adapters.
- Changing ACI TaskEnvelope schema or lineage immutability rules.

## 5. Design Overview

### 5.1 Contract Boundary (Normative)
- **Domain Layer**: Publishes/Consumes **ACI TaskEnvelope JSON** via the `QueuePort`.
- **Infrastructure Layer**: Handles the provider-specific connection, serialization, and acknowledgement logic.

### 5.2 Provider Loading & Secrets
A deployment profile selects the provider (e.g., `rabbitmq`). The `AdapterFactory` resolves credentials (e.g., `secret://rabbitmq_password`) before instantiating the adapter, ensuring the Domain never sees a literal password.

### 5.3 Capabilities Contract
Adapters must expose a `capabilities()` method so runtime components do not rely on features (delay, FIFO, priority) not supported by the active provider.

## 6. Functional Requirements

### 6.1 QueuePort Interface (Required)
The Port in `src/domain/ports/` must define:
- `publish(queue_name, payload, delay_seconds)`
- `consume(queue_name, max_messages)`
- `ack(message)`
- `retry(message, delay_seconds)`
- `health()`
- `capabilities()`

### 6.2 Payload Contract
- Payload MUST be **ACI TaskEnvelope JSON only**.
- Adapters MUST NOT mutate TaskEnvelope identity or lineage fields.

## 7. Testing Requirements

### 7.1 Unit Tests (Required)
- **Port Isolation**: Verify that the Domain layer can call `QueuePort` methods without RabbitMQ dependencies installed.
- **Factory Resolution**: Ensure the `AdapterFactory` correctly resolves `secret://` references using a mock `SecretStorePort`.
- **Payload Integrity**: Validate that `TaskEnvelope` JSON remains unchanged after a round-trip through the adapter.

### 7.2 Integration Tests (Required)
- **RabbitMQ Roundtrip**: Execute a full `publish -> consume -> ack` cycle using a local RabbitMQ container.
- **Namespace Verification**: Confirm that `comms.namespace` is correctly prepended to all generated queue names.

## 8. Definition of Done
- [ ] `QueuePort` protocol exists in `src/domain/ports/`.
- [ ] `RabbitMQAdapter` implemented in `src/infrastructure/adapters/comms/`.
- [ ] All broker credentials resolved via `SecretStorePort`.
- [ ] Integration tests confirm ACI payload integrity through the RabbitMQ boundary.