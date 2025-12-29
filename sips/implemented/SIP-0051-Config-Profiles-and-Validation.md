---
sip_uid: 01KCY12K6D8SRH663DASX7MR9M
sip_number: 51
title: Config Profiles and Validation
status: implemented
author: Jason Ladd
approver: null
created_at: '2025-01-15T00:00:00Z'
updated_at: '2025-12-29T16:58:07.899725Z'
original_filename: SIP-Config-Profiles-and-Validation.md
---
# SIP-CONFIG-PROFILES-AND-VALIDATION — Version Target 0.8.x  
## Centralized Configuration Loading, Deployment Profiles, Schema Validation, and Redaction

# 1. Purpose and Intent

This SIP defines a **single, centralized configuration system** for SquadOps that:

- loads configuration deterministically using **layered precedence**,
- supports **deployment profiles** (local/dev/stage/prod) as first-class inputs,
- enforces **schema validation** and fails fast on invalid configuration,
- provides **redaction rules** for safe logging and diagnostics,
- standardizes **override mechanisms** without scattering `os.environ` reads throughout the codebase.

The intent is to prevent configuration drift as SquadOps expands across:
- local developer runs,
- containerized environments,
- future cloud deployments (AWS/Azure/GCP),
- multiple services (runtime-api, health-check, agent containers, console, orchestrator).

# 2. Background

SquadOps is introducing portability primitives (DB bootstrap, queue adapter, secrets provider) that depend on consistent, validated config. Without a standardized config system, the codebase tends to accumulate:

- duplicated parsing logic,
- inconsistent default values,
- environment-variable reads in random modules,
- partial validation and late failures,
- accidental secret leakage in logs.

Configuration is a cross-cutting concern and must be centralized.

# 3. Problem Statements

1. Config parsing and defaults can diverge between services.
2. Environment variable overrides can be applied inconsistently.
3. Invalid config often fails late (runtime) rather than early (startup).
4. Secrets and sensitive values can be logged accidentally without unified redaction.
5. Portability features (DB, comms, secrets, auth) require stable config contracts.

# 4. Scope

## In Scope (0.8.x)
- A single **ConfigLoader** used by all services.
- Deployment profiles with deterministic precedence rules.
- Schema validation with clear error messages.
- Redaction for logs and diagnostics.
- Standardized override mechanisms (env + CLI flags where applicable).
- A stable config "shape" for shared infra components:
  - `secrets.*`
  - `db.*`
  - `comms.*`
  - `auth.*` (placeholder keys; full auth SIP defines semantics)
  - `prefect.*` (placeholder keys; orchestration SIP defines semantics)

## Out of Scope (0.8.x)
- A full GUI for profile editing.
- Dynamic config reload at runtime.
- A remote config service (e.g., Consul).
- Secret encryption (handled by SIP-SECRETS-MANAGEMENT providers).

# 5. Design Overview

## 5.1 Configuration Layers (Deterministic Precedence)

Configuration is assembled from layers in order (lowest → highest precedence):

1. **Built-in defaults** (code constants, committed)
2. **Base config file** (committed; non-secret)
3. **Deployment profile file** (committed; per environment; non-secret)
4. **Local override file** (uncommitted; developer use only; optional)
5. **Environment overrides** (CI/CD, container runtime)
6. **CLI overrides** (optional; explicit runtime arguments)

Higher precedence overwrites lower precedence.

## 5.2 Deployment Profile Selection

A profile is selected via one of:
- CLI arg: `--profile <name>`
- env var: `SQUADOPS_PROFILE=<name>`
- default: `local`

Profile selection must be logged at startup.

## 5.3 Schema Validation

A single schema validates the merged configuration before any service bootstraps its dependencies.

Validation outcomes:
- Missing required keys: hard failure
- Invalid values or enums: hard failure with actionable error text
- Unknown keys: configurable behavior
  - default for 0.8.x: **warn** (to avoid breaking future expansions)
  - optional strict mode: **fail** (for CI and production)

## 5.4 Redaction and Safe Logging

Configuration may be logged for diagnostics only after applying redaction rules:

- Secrets must never be logged (values)
- Secret references (`secret://name`) may be logged
- Tokens, passwords, keys, and connection strings must be redacted
- Redaction must be centralized and deterministic

# 6. Functional Requirements

## 6.1 Config Loader API (Required)

A shared module MUST provide:

- `load_config(profile: str | None = None, *, strict: bool = False) -> AppConfig`
- `get_config() -> AppConfig` (optional convenience; prevents reloading)
- `validate_config(cfg: dict, *, strict: bool) -> None | raises`
- `redact_config(cfg: dict) -> dict` (safe to log)
- `config_fingerprint(cfg: dict) -> str` (stable identifier for debugging)

`AppConfig` may be a Pydantic model (preferred) or a typed dataclass.

## 6.2 File Layout (Normative)

Recommended config layout:

- `config/defaults.yaml` (committed)
- `config/base.yaml` (committed)
- `config/profiles/<profile>.yaml` (committed)
- `config/local.yaml` (gitignored; optional)
- `.env` (gitignored; optional; used only to set override env vars)
- `.env.example` (committed; placeholders only)

## 6.3 Environment Overrides (Normative)

Environment overrides must be supported using one of:

- explicit mapping file (preferred), or
- a stable prefix + path convention

Required behavior:
- Only keys declared overrideable may be overridden (to limit blast radius), OR
- allow all keys but warn on unknown targets (implementation choice must be consistent)

Recommended convention (illustrative):
- `SQUADOPS__DB__POOL__SIZE=10` maps to `db.pool.size`

## 6.4 CLI Overrides (Optional, Service-Specific)

Services may support explicit CLI overrides, e.g.:
- `--profile`
- `--strict-config`
- `--config-local-path`

CLI overrides must be applied last and must be logged (key names only; values redacted).

## 6.5 Strict Mode

Strict mode rules:
- Unknown keys fail validation
- Missing required keys fail validation
- Invalid values fail validation
- Used in CI and production deployments by default (recommended)

# 7. Must Not (Normative)

The following are forbidden patterns after this SIP is implemented:

1. **No direct `os.environ` reads** for configuration outside the ConfigLoader (exception: the loader itself).
2. **No per-service config parsing** duplicating the loader logic.
3. **No secrets in config files** (values). Secrets must be provided via `secret://` references (SIP-SECRETS-MANAGEMENT).
4. **No logging of raw config** without redaction.
5. **No silent fallback** to defaults when required config is missing in strict mode.

# 8. Non-Functional Requirements

1. **Determinism**: same inputs produce the same merged config.
2. **Fast failure**: invalid config fails at startup, before connecting to dependencies.
3. **Observability**: startup logs include:
   - selected profile
   - strict mode on/off
   - config fingerprint
4. **Safety**: redaction is applied uniformly across services.
5. **Portability**: profile + env override model supports local and cloud deployments.

# 9. Implementation Considerations

## 9.1 Code Placement (Normative)

- `infra/config/loader.py` — load/merge/override orchestration
- `infra/config/schema.py` — Pydantic models and enums
- `infra/config/redaction.py` — redaction rules and helpers
- `infra/config/fingerprint.py` — stable fingerprint generation
- `infra/config/errors.py` — structured validation errors

## 9.2 Schema Strategy

Prefer Pydantic models for:
- strong typing
- clear error messages
- support for nested structures
- default management

## 9.3 Redaction Strategy

Redaction MUST include:
- explicit key-based redaction for:
  - `password`, `secret`, `token`, `api_key`, `private_key`
- DSN redaction (strip credentials)
- support for redacting nested keys
- support for redacting provider blocks, e.g.:
  - `comms.rabbitmq.password`
  - `auth.keycloak.client_secret`

## 9.4 Service Adoption Plan

Each service must be refactored to:

1. call `load_config()` at startup,
2. validate and log fingerprint (redacted config),
3. pass `AppConfig` into:
   - secrets manager
   - db bootstrap
   - queue adapter factory
   - auth middleware initialization (when implemented)

# 10. Testing Requirements

## 10.1 Unit Tests (Required)
- merge precedence correctness across all layers
- profile selection behavior
- environment override mapping behavior
- strict vs non-strict unknown key behavior
- schema validation errors are actionable
- redaction removes values while preserving shape
- fingerprint stability given same config

## 10.2 Integration Tests (Required)
- runtime-api startup succeeds with local profile
- startup fails fast with missing required keys in strict mode
- redacted config is loggable and contains no secret values

# 11. Definition of Done

- [ ] A single ConfigLoader exists and is used by all services.
- [ ] Deployment profiles exist and are selectable via CLI/env.
- [ ] Schema validation runs at startup for every service.
- [ ] Strict mode is available and enabled in CI (recommended).
- [ ] Redaction exists and raw config logging is eliminated.
- [ ] Direct `os.environ` reads outside the loader are removed (or explicitly justified exceptions).
- [ ] Unit and integration tests for loader, validation, redaction pass.

# 12. Appendix

## A. Example Precedence Walkthrough (Illustrative)

- defaults set `db.pool.size = 5`
- base config sets `db.pool.size = 8`
- profile `prod` sets `db.pool.size = 12`
- env override sets `SQUADOPS__DB__POOL__SIZE=20`

Effective result: `db.pool.size = 20`

## B. Example Startup Log Fields (Illustrative)

- profile: `local`
- strict_config: `false`
- config_fingerprint: `cfg-<hash>`
- db.ssl.mode: `disable`
- comms.provider: `rabbitmq`

