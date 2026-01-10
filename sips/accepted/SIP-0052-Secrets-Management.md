---
sip_uid: 01KDP28PVHN0A20WQ2W8WNST44
sip_number: 52
title: Secrets Management
status: accepted
author: Jason Ladd
approver: null
created_at: '2025-12-29T00:00:00Z'
updated_at: '2025-12-29T17:04:50.154764Z'
original_filename: SIP-Secrets-Management.md
---
# SIP-SECRETS-MANAGEMENT — Version Target 0.8.x
## Centralized Secrets Provider with Secret References, Name Mapping, and Enforcement

## Status
**Draft** — Unnumbered (awaiting maintainer acceptance)  
**Target Version:** 0.8.x  
**Roles Impacted:** All agents, Infrastructure

---

# 1. Purpose and Intent

This SIP defines a **standard secrets management strategy** for SquadOps that:
- eliminates hard-coded or default secrets in configuration,
- establishes a **central Secrets Provider** boundary,
- introduces **secret references** (`secret://name`) and an optional **name mapping** layer for cloud portability,
- adds enforcement mechanisms to prevent regression.

The intent is to ensure SquadOps ports cleanly across:
- local development (env/file)
- container deployments (Docker secrets)
- future cloud deployments (AWS/Azure/GCP secret managers)
**without refactoring application or agent code**.

# 2. Background

SquadOps configuration and bootstrapping flows may currently rely on:
- default credentials (e.g., `postgres/postgres`)
- plaintext secrets in config or compose files
- direct `os.environ` access scattered across modules

These patterns cause real-world pain when:
- secrets must rotate due to policy, audit, or incident response
- environments drift in how secrets are provided
- cloud portability is introduced later

Secrets management is an infrastructure boundary and must be centralized.

# 3. Problem Statements

1. Secrets are not clearly distinguished from standard config values.
2. Direct environment access allows bypassing any centralized control.
3. Default/placeholder secrets can silently reach production deployments.
4. Cloud portability can be blocked by secret-store naming constraints and path conventions.
5. Rotation is risky without a consistent, discoverable secret reference model.

# 4. Scope

## In Scope
- Define a **Secrets Provider contract**
- Define `secret://<logical_name>` references in config
- Add an optional **name mapping layer** to decouple logical names from provider keys/paths
- Implement providers for 0.8.x:
  - `env`
  - `file`
  - `docker_secret`
- Add CI/test enforcement to prevent plaintext secrets and default credentials in repo
- Standardize secret resolution usage across DB, comms, and auth bootstraps

## Out of Scope
- Implement AWS Secrets Manager / Azure Key Vault / GCP Secret Manager providers (planned later)
- Runtime secret rotation / hot reload (restart-based in 0.8.x)
- Encrypting secrets at rest locally (delegated to OS/container runtime)

# 5. Design Overview

## 5.1 Secret References (Logical Names)
Config MUST reference secrets symbolically:

- `secret://<logical_name>`

Example:
- `db.password = secret://db_password`

## 5.2 Name Mapping (Cloud Portability)
A deployment profile MAY define a **name mapping** that translates logical names to provider keys.

Example mapping:
- logical: `db_password`
- provider key: `prod/squadops/db_password`

This prevents cloud provider naming/path conventions from leaking into application config.

## 5.3 Central Resolution Boundary
All secret resolution flows through a single module:

- `secrets.resolve("secret://db_password")`

Application/agent logic MUST NOT call `os.environ` directly.

# 6. Functional Requirements

## 6.1 Secret Reference Format
- Allowed format: `secret://<logical_name>`
- Literal secret values in config are forbidden.
- `<logical_name>` is stable across environments.

## 6.2 Secrets Provider Contract
All providers MUST implement:

- `resolve(secret_ref: str) -> str`
- `exists(secret_ref: str) -> bool`
- `provider_name: str`

Failures MUST raise explicit errors (no silent fallbacks).

## 6.3 Name Mapping Requirements
- Deployment profiles MAY declare `secrets.name_map`.
- If present, mapping MUST be applied before provider resolution.
- Mapping keys are **logical names** (no scheme).
- Mapping values are provider-specific keys/paths.

Behavior:
- If a mapping exists for the logical name, use it.
- Otherwise, use the logical name as the provider key.

Example:
- `secret://db_password`
  - logical name: `db_password`
  - mapped key: `prod/squadops/db_password`
  - provider resolves the mapped key

## 6.4 Supported Providers (0.8.x)

### Environment Variable Provider (`env`)
- Resolution target uses a stable convention:
  - provider key -> env var name
- Default mapping:
  - provider key `db_password` -> `${ENV_PREFIX}DB_PASSWORD`
- Profile setting:
  - `secrets.env_prefix` (e.g., `SQUADOPS_`)

### File Provider (`file`)
- provider key is the file name (or path segment) under `secrets.file_dir`
- default:
  - `${secrets.file_dir}/${provider_key}`

### Docker Secret Provider (`docker_secret`)
- same as `file` with default dir `/run/secrets`

## 6.5 Deployment Profile Integration
Deployment profiles MUST declare:

- `secrets.provider = env | file | docker_secret`
- Optional provider settings:
  - `secrets.env_prefix`
  - `secrets.file_dir`
- Optional mapping:
  - `secrets.name_map.<logical_name> = <provider_key>`

## 6.6 Usage Rules (Normative)
- Code MUST NOT call `os.environ` directly for secret retrieval.
- Secret values MUST NOT be logged.
- Secret references and logical names MAY be logged.
- Bootstraps (DB, MQ, auth) MUST resolve secrets at initialization time.

# 7. Enforcement and Guardrails

## 7.1 Repository Enforcement (Must Not Ship)
Forbidden in repo:
- plaintext passwords, tokens, API keys
- default credentials
- "changeme" patterns

## 7.2 CI / Test Enforcement
Required:
- unit test scanning config + compose + env template files for forbidden patterns
- CI job that fails on banned patterns
Optional:
- pre-commit hook for local detection

## 7.3 Local Development Safety
- `.env.example` MUST be committed with placeholders only
- `.env` MUST NOT be committed
- `secrets/` directory SHOULD be gitignored when using file provider

# 8. Non-Functional Requirements

1. **Portability**: logical names remain stable; provider keys differ by environment via mapping.
2. **Simplicity**: no external vault dependency in 0.8.x.
3. **Auditability**: secret access flows through one module.
4. **Rotation readiness**: value changes do not require config rewrites (only secret store updates).
5. **Safety**: missing secrets cause hard failure early.

# 9. Implementation Considerations

## 9.1 Code Placement
- `infra/secrets/manager.py` — parsing + mapping + provider selection
- `infra/secrets/provider.py` — interface
- `infra/secrets/env_provider.py`
- `infra/secrets/file_provider.py`
- `infra/secrets/docker_provider.py`

## 9.2 Resolution Flow (Normative)
1. Parse `secret://<logical_name>`
2. Apply `secrets.name_map` if present:
   - logical -> provider_key
3. Pass provider_key to the selected provider
4. Return secret value (never log)

## 9.3 Future Cloud Providers (Non-Implementation Note)
Later providers implement the same contract and consume provider keys:
- `aws_secrets_manager`
- `azure_key_vault`
- `gcp_secret_manager`

Name mapping allows provider keys like:
- `prod/squadops/db_password`
- `projects/<id>/secrets/<name>`
- `https://<vault>/secrets/<name>`

without touching app config.

# 10. Executive Summary — What Must Be Built

- Secret reference parsing (`secret://`)
- Name mapping (`secrets.name_map`) applied prior to provider resolution
- Providers: env, file, docker_secret
- Enforcement tests/CI scanning for banned patterns
- Refactors removing direct env var access

# 11. Definition of Done

- [x] `secret://` references are supported across config surfaces
- [x] `secrets.name_map` is supported and validated
- [x] Providers `env`, `file`, `docker_secret` implemented
- [x] No plaintext secrets/default creds in repo
- [x] CI fails on forbidden patterns
- [x] DB/MQ/auth bootstraps use Secrets Manager
- [x] Secret values are never logged

# 12. Appendix

## A. Example Config (Portable)
```yaml
secrets:
  provider: env
  env_prefix: SQUADOPS_
  name_map:
    db_password: DB_PASSWORD
    rabbitmq_password: RABBITMQ_PASSWORD

db:
  password: secret://db_password
```

## B. Example Config (Cloud-style Keys Later)
```yaml
secrets:
  provider: azure_key_vault  # future
  name_map:
    db_password: prod/squadops/db_password

db:
  password: secret://db_password
```

