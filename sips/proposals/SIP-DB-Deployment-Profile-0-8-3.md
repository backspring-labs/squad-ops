---
sip_uid: 01KEM71ECNND1QN05SFV5C2QZB
sip_number: null
title: DB Deployment Profile — Postgres Portability via Deployment Profiles + infra/db/bootstrap
status: proposed
author: Framework Committee
approver: null
created_at: '2026-01-10T15:05:29Z'
updated_at: '2026-01-10T15:05:29Z'
original_filename: SIP-DB-DEPLOYMENT-PROFILE-0_8_3.md
---
# SIP-DB-DEPLOYMENT-PROFILE — Version Target 0.8.x  
## Postgres Portability via Deployment Profiles + `infra/db/bootstrap`

# 1. Purpose and Intent

This SIP defines a **standard database deployment profile** and a single **DB bootstrap module** (`infra/db/bootstrap`) that together encapsulate Postgres portability concerns across environments (local Docker, self-managed Postgres, and future managed Postgres offerings in AWS/Azure/GCP) **without introducing a "database adapter" abstraction**.

The intent is to:
- keep application code **DB-provider-agnostic** (Postgres remains Postgres),
- centralize environment-specific DB behavior in **deployment profiles** and **bootstrap defaults**,
- standardize how SquadOps components obtain DB sessions, run health checks, and (optionally) run migrations,
- support cloud portability via profile changes (TLS, secrets, pooling, connectivity modes) without code drift.

# 2. Background

SquadOps uses Postgres as the system of record (e.g., task logs, cycle state). Moving from local/dev environments to cloud environments commonly introduces DB portability concerns that are operational rather than logical:
- TLS/SSL requirements and certificate handling
- credential sourcing (env vars vs secrets managers)
- connection pooling behavior under autoscaling
- migration execution strategy (startup vs job/CI step)
- timeouts and failover/reconnect behavior
- optional proxy/connector connectivity patterns

These concerns are best managed through **configuration + bootstrapping**, not through an abstraction over SQL.

# 3. Problem Statements

1. DB configuration can be scattered across services/modules (DSN parsing, TLS flags, pool tuning), creating drift.
2. Migration execution can become inconsistent (some services run migrations on startup, others not), increasing risk.
3. Cloud environments introduce TLS and pooling expectations that should be addressed centrally.
4. Without a standard bootstrap boundary, portability work leaks into business logic and agent/runtime components.

# 4. Scope

## In Scope
- Define a **DB Deployment Profile contract** (config keys and semantics).
- Implement `infra/db/bootstrap` as the single module responsible for:
  - config validation
  - engine/session factory creation
  - standardized pooling/timeouts
  - standardized health check
  - optional migration orchestration gate (mode-controlled)
- Update all SquadOps components to obtain DB access only through the bootstrap exports.

## Out of Scope
- Supporting non-Postgres databases (e.g., DynamoDB).
- Implementing provider-specific DB APIs (e.g., Aurora Data API).
- Implementing multi-tenant routing, read/write splitting, or blue/green multi-DSN strategies.
- Implementing a managed migration service; this SIP only standardizes invocation and gating.

# 5. Design Overview

The design has two parts:

1) **Deployment Profiles** declare environment-specific DB behavior (DSN, SSL mode, pooling, migration mode, secrets provider, and optional connectivity mode).  
2) **`infra/db/bootstrap`** consumes a profile to create a **DB Runtime**:
- `engine`
- `session_factory` (or equivalent)
- `health_check()`
- `dispose()`
- optional `run_migrations()` gated by `db.migrations.mode`

All other code uses only the bootstrap exports and does not interpret DB environment variables directly.

# 6. Functional Requirements

## 6.1 DB Deployment Profile Contract

The following keys MUST be supported:

- `db.dsn`  
  - Full DSN/connection string (direct connection target)
- `db.ssl.mode`  
  - `disable | require | verify-full` (or equivalent supported by driver)
- `db.ssl.ca_bundle_path` (optional)  
  - Path to CA bundle when using verify modes
- `db.pool.size`  
- `db.pool.max_overflow`  
- `db.pool.timeout_seconds`  
- `db.pool.pre_ping` (default `true`)  
- `db.statement_timeout_ms` (optional)  
- `db.health.timeout_ms`  
- `db.migrations.mode`  
  - `off | startup | job`
- `db.secrets.provider`  
  - `env | file` (0.8.x). Future: cloud secrets managers

### 6.1.1 Optional Cloud Connectivity Mode (Profile-Only)
To support cloud deployment patterns without changing application logic, profiles MAY declare:

- `db.connection.mode`  
  - `direct | proxy`
- `db.connection.proxy_dsn` (optional)  
  - A DSN that points to a local proxy/connector endpoint (e.g., localhost), used when mode is `proxy`.

Behavior:
- If `direct`: use `db.dsn`
- If `proxy`: use `db.connection.proxy_dsn` (required) and ignore `db.dsn` for runtime connections

Note:
- This SIP does not implement proxy process management. It only standardizes DSN selection behavior.

## 6.2 `infra/db/bootstrap` Module

`infra/db/bootstrap` MUST provide:

- `validate_db_config(profile) -> None | raises`
- `create_engine(profile) -> Engine`
- `create_session_factory(engine) -> SessionFactory`
- `get_db_runtime(profile) -> DbRuntime` (preferred single entry point)
- `db_health_check(runtime) -> HealthResult`
- `dispose(runtime) -> None`
- `run_migrations(profile) -> None` (only if mode permits; see 9.3)

`DbRuntime` MUST include:
- `engine`
- `session_factory`
- `profile_fingerprint` (stable string used for logging/debugging)
- `effective_dsn` (the DSN actually used, safe to log only after redaction)

All callers MUST use `DbRuntime` (or the session factory/engine returned by bootstrap) and MUST NOT create their own engines or parse DSNs.

## 6.3 Migration Invocation Contract

Migration behavior MUST be controlled by `db.migrations.mode`:

- `off`: migrations are never run by services automatically
- `startup`: the service may run migrations at startup (only in single-writer contexts)
- `job`: migrations are run only by an explicit job/command (CI/CD, one-shot task)

`infra/db/bootstrap` MUST expose a single authoritative check:
- "Are migrations permitted in this process given the current profile?"

# 7. Non-Functional Requirements

1. **Consistency**: All SquadOps services use the same DB initialization rules and defaults.
2. **Safety**: Defaults must avoid connection storms and support reconnect safety (`pool_pre_ping` or equivalent).
3. **Portability**: Local Postgres and managed Postgres offerings must be supported with profile changes only.
4. **Observability**: Bootstrap must log:
   - profile fingerprint
   - ssl mode
   - pool sizing parameters
   - connection mode (`direct|proxy`)
   - migration mode and whether migrations are executed or skipped
5. **Minimal Behavioral Drift**: Bootstrap preserves current DB behavior unless explicitly changed in profiles.

# 8. API Surface (If Applicable)

No external API surface changes are introduced.

Internal usage patterns are standardized:
- Services import DB runtime/session creation only from `infra/db/bootstrap`.

# 9. Implementation Considerations

## 9.1 Code Placement (Normative)
- `infra/db/bootstrap.py` (or package `infra/db/bootstrap/__init__.py`)
- `infra/db/types.py` (optional) for `DbRuntime`, `HealthResult`
- `infra/db/migrations.py` (optional) for migration runner entrypoints

## 9.2 Defaults (Cloud-Friendly Without Cloud-Specific Code)
Bootstrap should apply safe defaults unless overridden by profile:
- `pool_pre_ping = true`
- bounded pool sizing
- explicit connection + pool timeouts
- statement timeout support (where driver supports it)

## 9.3 Migrations as a Deployment Concern
Preferred default for multi-service/cloud deployments:
- `db.migrations.mode = job`

Rationale:
- prevents multiple replicas from competing to run migrations
- aligns with CI/CD and controlled rollout patterns

`startup` mode is acceptable in local/dev or single-instance contexts.

## 9.4 Secrets Provider Integration
DB bootstrap must obtain credentials via the centralized secrets mechanism (see SIP-SECRETS-MANAGEMENT):
- config may contain `secret://` references
- bootstrap resolves them prior to engine creation

# 10. Executive Summary — What Must Be Built

- A standardized **DB deployment profile contract** (Section 6.1).
- A single `infra/db/bootstrap` module implementing:
  - validation
  - engine + session factory creation
  - DSN selection based on `db.connection.mode`
  - health check
  - disposal
  - migration gating per mode
- Refactors so all DB access in SquadOps routes through bootstrap.
- Unit tests for config validation, runtime creation, DSN selection, and health checks.
- An integration test validating connection and a basic query using the active profile.

# 11. Definition of Done

- [ ] `infra/db/bootstrap` exists and is used by all DB-consuming components.
- [ ] No services read DB env vars or create engines outside bootstrap.
- [ ] Deployment profile keys in Section 6.1 are supported and documented.
- [ ] Optional `db.connection.mode` behavior implemented (`direct|proxy` DSN selection).
- [ ] Migration mode gating works as specified (`off | startup | job`).
- [ ] Unit tests cover:
  - config validation errors
  - engine/session creation with ssl modes
  - DSN selection for direct vs proxy mode
  - health check success/failure
  - migration mode gating behavior
- [ ] Integration test validates:
  - connection using local/dev profile
  - health check output
  - session acquisition and simple query
- [ ] Logging shows profile fingerprint + critical DB parameters at startup (no secret values).

# 12. Appendix  

## A. Cloud Considerations (Informative)

Cloud providers typically impact DB connectivity and ops via:
- TLS expectations (`require` / `verify-full` and CA bundles)
- secret sourcing (cloud secret managers) — handled via SIP-SECRETS-MANAGEMENT
- connection storm risk under autoscaling (pool sizing discipline)
- optional proxy/connector patterns (covered by `db.connection.mode=proxy`)

This SIP intentionally keeps these concerns **profile-driven** so application and agent code do not change.

## B. Example Profile Snippets (Illustrative)

**Local Docker (dev):**
- `db.connection.mode = direct`
- `db.dsn = postgresql+psycopg://user:pass@localhost:5432/squadops`
- `db.ssl.mode = disable`
- `db.pool.size = 5`
- `db.migrations.mode = startup`

**Proxy-based (cloud-style, later):**
- `db.connection.mode = proxy`
- `db.connection.proxy_dsn = postgresql+psycopg://user:pass@127.0.0.1:5432/squadops`
- `db.ssl.mode = require`
- `db.pool.size = 10`
- `db.migrations.mode = job`
