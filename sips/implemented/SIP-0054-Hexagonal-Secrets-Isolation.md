---
sip_uid: 01KEMAH9QWAH9FWNZZ27NY1QCC
sip_number: 54
title: Hexagonal Secrets Isolation
status: implemented
author: Gemini (Design Partner)
approver: null
created_at: '2026-01-10T00:00:00Z'
updated_at: '2026-01-10T12:00:00Z'
original_filename: SIP-SECRETS-0_8_2-DDD.md
---
# SIP-SECRETS-0_8_2-DDD — Hexagonal Secrets Isolation

**Status:** Implemented  
**Target Version:** 0.8.2 (DDD Migration)  
**Author:** Gemini (Design Partner)  
**Roles Impacted:** Lead, Strategy, Dev, QA, Data

## 1. Purpose and Intent
This SIP formalizes the structural migration of the Centralized Secrets Provider into the Domain-Driven Design (DDD) framework. The intent is to establish a "Locked Architectural Boundary" by moving abstract resolution logic into the Shared Kernel and isolating environment-specific retrieval (env, file, docker) into Hexagonal Adapters.

## 2. Background
The implementation from v0.8.2 successfully introduced the secret:// scheme and centralized manager. However, it lacked a formal boundary, resulting in infrastructure-specific code (e.g., Docker file paths) existing in the same context as the resolution logic, which violates the strict dependency rules of the new 1.0 architecture.

## 3. Problem Statements
**Logic Entanglement:** Concrete retrieval methods (Adapters) are currently interleaved with the URI parsing logic (Core).

**Boundary Leakage:** Without a formal Port interface, the engine cannot be tested in isolation without satisfying environment-level dependencies.

## 4. Scope
### In Scope
- Establishing the SecretsProvider Port interface.
- Relocating the SecretsManager to the Shared Kernel core.
- Implementing concrete Adapters for env, file, and docker.

### Out of Scope
- Changing the secret:// URI format or name mapping logic.
- Adding new cloud providers (AWS/Azure) at this stage.

## 5. Design Overview (Authority vs. Intent)
**Coordination Authority (Ports):** The Port (ports/secrets.py) defines the contract that any secrets provider must satisfy.

**Execution Intent (Core):** The Core (core/secrets.py) parses the URI and orchestrates the resolution via the Port, remaining entirely agnostic of where the secret is stored.

## 6. Functional Requirements
**Core Purity:** The squadops.core.secrets module MUST have zero imports from the adapters/ namespace.

**Adapter Autonomy:** Each adapter MUST be a standalone module that only depends on the Port interface.

## 7. Non-Functional Requirements
**Testability:** The Core MUST be testable by injecting a "MockProvider" through the defined Port.

**Observability:** Resolution logs MUST reference the Port being used but NEVER log the secret value.

## 9. Implementation Considerations
**Migration Bridge:** Logic will be extracted from _v0_legacy/infra/secrets/ and redistributed into the new src/squadops/ and adapters/ structures.

## 10. Executive Summary — What Must Be Built
- [x] Port Interface: src/squadops/ports/secrets.py (The ABC).
- [x] Core Manager: src/squadops/core/secrets.py (The URI Parser).
- [x] Adapter Set: adapters/secrets/env.py, adapters/secrets/file.py, adapters/secrets/docker.py.
- [x] Factory: adapters/secrets/factory.py

## 11. Definition of Done
- [x] squadops.core.secrets successfully resolves values via adapters.
- [x] No circular dependencies exist between core and adapters.
- [x] All imports are refactored to the new squadops.* package structure.

## Implementation Status
**Completed:** 2026-01-10

All requirements have been implemented:
- Port interface established at `src/squadops/ports/secrets.py`
- Core manager migrated to `src/squadops/core/secrets.py` with core purity maintained
- Adapters implemented: `adapters/secrets/env.py`, `adapters/secrets/file.py`, `adapters/secrets/docker.py`
- Factory pattern implemented at `adapters/secrets/factory.py`
- Configuration loader updated to use new structure
- All tests passing with mock provider injection
