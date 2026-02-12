# SIP — Provider-Agnostic OIDC Boundary With Keycloak Isolation

**Status:** Proposed  
**Evolves:** Existing implemented auth + Keycloak hardening without rewriting prior SIPs  
**Primary Outcome:** Keycloak is fully isolated so the framework is not “Keycloak-shaped,” while preserving current behavior.

---

## 1) Intent

This SIP defines a **provider-agnostic OIDC auth design** for SquadOps and establishes a **hard isolation boundary** around Keycloak-specific configuration, artifacts, and operational guidance.

This SIP does **not** deprecate or modify previously implemented SIPs; it introduces a **new standard** for how auth providers are represented in code, config, and documentation going forward.

---

## 2) Goals

1) The core framework MUST be **OIDC-first** (issuer discovery + JWKS validation), not Keycloak-first.  
2) The codebase MUST NOT require Keycloak-specific nouns (realm, clients, proxy settings) outside of a Keycloak provider module.  
3) Keycloak MUST remain supported (local/dev and optional prod), but MUST be selectable by config/profile only.  
4) It MUST be possible to introduce a managed provider later (Cognito/Entra/Identity Platform) without reworking core types.

---

## 3) Non-goals

- Implementing a managed-provider pack now.
- Rewriting or renumbering existing implemented SIPs.
- Changing runtime behavior of current deployments unless explicitly stated as a follow-on step.

---

## 4) Normative Architecture

### 4.1 Core boundary rule (MANDATORY)

The Runtime API MUST depend only on the following provider-agnostic primitives:

- OIDC discovery: `issuer_url` → `/.well-known/openid-configuration`
- JWKS validation: `jwks_uri`
- Claim validation: `iss`, `aud`, `exp`, `nbf`, `sub`
- Role extraction via configurable mapping rules

Any provider-specific operational constructs (e.g., Keycloak realm export/import, proxy modes, hostname strictness) MUST be contained within a provider-specific module and MUST NOT be referenced by core runtime logic.

---

## 5) Configuration Model (Prescriptive)

### 5.1 Core auth configuration (MANDATORY)

A single provider-agnostic config MUST exist and be the default for all runtime code paths:

```yaml
auth:
  enabled: true
  provider: "oidc"
  oidc:
    issuer_url: "https://issuer.example.com"
    expected_audiences: ["squadops-runtime"]
    clock_skew_seconds: 60
    jwks_cache:
      ttl_seconds: 3600
      refresh_on_kid_miss: true
      refresh_on_signature_failure: true
      min_refresh_interval_seconds: 30

  claims:
    subject_path: "sub"
    email_path: "email"
    roles:
      mode: "claim"            # claim | static
      claim_path: "roles"      # provider-specific value via profile
      normalize: ["lower"]
      map: {}                  # optional mapping from provider values -> app roles
```

**Rules:**
- `auth.provider` MUST be `"oidc"` in core runtime usage.
- The `auth.oidc` block MUST be provider-agnostic.
- The `auth.claims` block MUST be provider-agnostic, with provider-specific values supplied by profiles.

### 5.2 Provider selection (OPTIONAL convenience, MUST NOT affect core types)

For operator convenience only, a non-normative hint MAY exist:

```yaml
auth:
  provider_kind: "keycloak" | "entra" | "cognito" | "gcp_identity_platform" | "generic"
```

**Rule:** `provider_kind` MAY be used to select default claim mapping presets, but MUST NOT change the core runtime interface or require provider-specific config blocks.

---

## 6) Code-Level Interfaces (Prescriptive)

### 6.1 OIDC Provider Port (MANDATORY)

The framework MUST define an application-layer port (interface) that represents “OIDC verification”:

**`OidcVerifierPort`**
- `verify_access_token(token: str) -> VerifiedToken`
- `get_userinfo(token: str) -> UserInfo` (optional; MUST be implementable as “not supported”)
- `close()`

`VerifiedToken` MUST include:
- `subject`
- `issuer`
- `audiences`
- `expires_at`
- raw claims dictionary (for role extraction)

### 6.2 Identity resolution (MANDATORY)

The framework MUST define a provider-agnostic identity resolver:

**`IdentityResolver`**
- input: `VerifiedToken` + `ClaimsMappingConfig`
- output: `Identity` (subject, email, roles)

Role extraction MUST be implemented here, not inside a provider module.

### 6.3 Keycloak isolation module (MANDATORY)

All Keycloak-specific concerns MUST live under a dedicated module, e.g.:

- `infra/auth/providers/keycloak/*`
- `docs/auth/providers/keycloak/*`
- `config/profiles/keycloak-*`

**Rule:** Core runtime code MUST NOT import any `keycloak.*` module.

---

## 7) Artifact + Documentation Isolation (Prescriptive)

### 7.1 Filesystem placement (MANDATORY)

Keycloak-specific artifacts MUST be stored under a provider-scoped folder, e.g.:

- `infra/auth/providers/keycloak/docker-compose.keycloak.yml`
- `infra/auth/providers/keycloak/realm-exports/*.json`
- `infra/auth/providers/keycloak/scripts/*`
- `docs/auth/providers/keycloak/production-hardening.md`

Provider-agnostic auth docs MUST live under:

- `docs/auth/oidc-boundary.md`
- `docs/auth/claims-mapping.md`

### 7.2 Documentation rule (MANDATORY)

Keycloak hardening documentation MUST be explicitly labeled as:
- **“Provider-specific implementation guidance”**
and MUST reference the provider-agnostic boundary as the source of truth for runtime verification semantics.

---

## 8) Validation and Guardrails (Prescriptive)

### 8.1 Config validation (MANDATORY)

Core config validation MUST enforce:
- `issuer_url` is present when `auth.enabled=true`
- `expected_audiences` is non-empty
- `jwks_cache` refresh rules are enabled for kid-miss and signature failure
- `claims.roles.mode` and `claims.roles.claim_path` are consistent

Core validation MUST NOT require any Keycloak-specific config.

### 8.2 Import boundary tests (MANDATORY)

Add an automated test that fails if core auth modules import provider-specific modules:

- No imports from `infra.auth.providers.keycloak` (or equivalent) in core runtime packages.

### 8.3 Behavior conformance tests (MANDATORY)

At minimum, a provider-agnostic test suite MUST validate:
- discovery fetch works (mocked)
- JWKS caching refresh-on-failure works (mocked)
- `aud` enforcement works
- role extraction works for:
  - roles claim as list
  - roles claim nested path
  - mapping table transforms provider groups -> app roles

These tests MUST not reference Keycloak-specific claims by default; they must use synthetic claims and mapping config.

---

## 9) Migration Plan (Prescriptive)

### Phase 1 — Introduce provider-agnostic config and ports (no runtime behavior change)
- Implement `OidcVerifierPort` using current JWKS verification logic.
- Implement `IdentityResolver` and route role extraction through it.
- Add provider-agnostic config blocks as described in Section 5.
- Keep existing Keycloak deployment working by expressing it as a profile that sets:
  - `issuer_url`
  - `expected_audiences`
  - `claims.roles.claim_path`
  - any claim mapping needed

### Phase 2 — Isolate Keycloak artifacts and docs (organization change)
- Move Keycloak compose, realm exports, and scripts under `infra/auth/providers/keycloak/`.
- Move Keycloak-specific hardening docs under `docs/auth/providers/keycloak/`.
- Ensure all examples in general docs are OIDC-generic.

### Phase 3 — Enforce isolation (guardrails)
- Add import-boundary test.
- Add config validation to prevent requiring Keycloak blocks in core.
- Add “provider_kind presets” as optional convenience without affecting core.

---

## 10) Acceptance Criteria

This SIP is accepted when:

1) The Runtime API runs with `auth.provider="oidc"` and does not require Keycloak-specific configuration.  
2) Existing Keycloak-based environments continue to work via profile config only.  
3) No core runtime modules import Keycloak provider modules (enforced by tests).  
4) Keycloak artifacts and docs are physically isolated under provider-specific directories.  
5) Role mapping is entirely data-driven via `claims.roles.*` config and tested without Keycloak assumptions.

---

## 11) Open Questions (Non-blocking)

- Whether `userinfo` is required for Console flows or optional for MVP.
- Whether `provider_kind` presets are desired now or deferred.
