---
sip_uid: 01KEM71ECNND1QN05SFV5C2QZB
sip_number: 55
title: DB Deployment Profile — Postgres Portability via Deployment Profiles + infra/db/bootstrap
status: accepted
author: Framework Committee
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-10T11:42:29.120074Z'
original_filename: SIP-DB-DEPLOYMENT-PROFILE-0_8_3.md
---
# SIP-DB-DEPLOYMENT-PROFILE-0_8_3
## Postgres Portability via Hexagonal Persistence Port + Deployment Profiles

# 1. Purpose and Intent
This SIP defines a **standard database deployment profile** and a hexagonal **Persistence Adapter** that encapsulates Postgres portability concerns across environments (local Docker, self-managed Postgres, and future managed cloud offerings) **without introducing a “database adapter” abstraction**. 

The intent is to:
- Keep application code **DB-provider-agnostic** (Postgres remains Postgres).
- Centralize environment-specific behavior in **deployment profiles** and **hexagonal adapters**.
- Standardize how components obtain DB sessions via a strict **Port** interface.
- Support cloud portability (TLS, secrets, pooling) through profile changes without code drift.

# 2. Background
SquadOps uses Postgres as the system of record. Moving from local to cloud environments introduces operational concerns (TLS, credential sourcing, connection pooling) that are currently scattered across the framework. These concerns must be managed through **configuration + bootstrapping** within the persistence adapter, not through business logic.

# 3. Problem Statements
1. **Infrastructure Drift**: DB configuration logic (DSN parsing, SSL flags) is scattered, creating drift.
2. **Inconsistent Migrations**: Migration execution varies across services, increasing operational risk.
3. **Boundary Leakage**: Without a standard bootstrap boundary, portability work leaks into agent and runtime components.

# 4. Scope
## In Scope
- Define a **DB Deployment Profile contract** (Section 6.1).
- Implement the **Persistence Adapter** (`adapters/persistence/`) responsible for config validation and engine creation.
- Implement the **DbRuntime Port** (`src/squadops/ports/db.py`) as the single interface for DB access.
## Out of Scope
- Supporting non-Postgres databases (e.g., DynamoDB).
- Implementing multi-tenant routing or read/write splitting.

# 5. Design Overview (Authority vs. Intent)
- **Coordination Authority (Ports)**: `src/squadops/ports/db.py` defines the `DbRuntime` interface.
- **Execution Intent (Adapters)**: `adapters/persistence/postgres/` consumes the profile to create the runtime.
- **The Boundary**: All other code uses only the port exports and does not interpret DB environment variables directly.

# 6. Functional Requirements

## 6.1 DB Deployment Profile Contract
The following keys MUST be supported in the deployment profile:
- `db.dsn`: Full connection string (direct connection target).
- `db.ssl.mode`: `disable | require | verify-full`.
- `db.ssl.ca_bundle_path`: Path to CA bundle (optional).
- `db.pool.size`, `db.pool.max_overflow`, `db.pool.timeout_seconds`.
- `db.migrations.mode`: `off | startup | job`.
- `db.connection.mode`: `direct | proxy`.

## 6.2 Persistence Adapter Responsibilities
The adapter package MUST provide:
- `validate_db_config(profile)`: Ensures all keys are present.
- `get_db_runtime(profile)`: Preferred entry point returning the Port implementation.
- **Secret Integration**: MUST resolve `db.dsn` or passwords via `squadops.core.secrets` if they use the `secret://` scheme.

## 6.3 Migration Invocation Contract
Migration behavior is strictly gated by `db.migrations.mode`:
- `off`: No automatic migrations.
- `startup`: The service runs migrations on startup (only in single-writer contexts).
- `job`: Migrations are run only by an explicit CI/CD or management task.

# 7. Immutable Invariants (The Guardrails)
- **Rule 1**: The Core engine MUST NOT interpret DB environment variables or create engines.
- **Rule 2**: `src/squadops/core/` MUST NOT import from `adapters/persistence/`.
- **Rule 3**: `pool_pre_ping` is enabled by default to ensure reconnect safety.

# 8. Port Interface Specification
The Port at `src/squadops/ports/db.py` MUST define the `DbRuntime` abstract class/interface with the following members:
- `engine`: The SQLAlchemy engine instance.
- `session_factory`: The sessionmaker instance for agents.
- `db_health_check() -> HealthResult`: Standardized connectivity check.
- `dispose() -> None`: Resource cleanup.

# 9. Implementation Considerations
- **Code Placement**: Port at `src/squadops/ports/db.py`; Adapter at `adapters/persistence/postgres/`; Factory at `adapters/persistence/factory.py`.
- **Observability**: The adapter must log the profile fingerprint, SSL mode, and connection mode, but MUST NOT log secret values or unredacted DSNs.

# 10. Executive Summary — What Must Be Built
- [ ] **DbRuntime Port**: The abstract interface for health and sessions.
- [ ] **Postgres Adapter**: Logic for SSL, pooling, and secret resolution.
- [ ] **Adapter Factory**: Maps profile config to the correct runtime instance (called by config loader).

# 11. Definition of Done
- [ ] `adapters/persistence/` is used by all components requiring DB access.
- [ ] No services read DB env vars directly.
- [ ] Migration gating works as specified (`off | startup | job`).
- [ ] Integration tests validate session acquisition using the new Port/Adapter structure.