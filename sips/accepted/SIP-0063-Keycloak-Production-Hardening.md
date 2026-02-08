---
sip_number: 63
title: Keycloak Production Hardening, Operational Posture, and Enterprise-Ready Configuration
status: accepted
author: Jason Ladd
approver: jladd
created_at: '2026-02-07T00:00:00Z'
updated_at: '2026-02-07T22:00:00Z'
original_filename: SIP-KEYCLOAK-PROD-0_9_2.md
---
# SIP-0063 — Keycloak Production Hardening

**Target Version:** 0.9.2
**Roles Impacted:** Lead, Strategy, Dev, QA, Data

---

# 1. Purpose and Intent

This SIP defines the **0.9.2 production hardening** requirements for the Keycloak-based Identity Provider used by SquadOps, building on the functional boundary established in **SIP-0062** (Auth Boundary).

SIP-0062 established the auth *boundary* — ports, adapters, middleware, domain models. This SIP hardens the *infrastructure behind it*: the Keycloak server configuration, token policies, operational posture, and deployment readiness.

The distinction is important:
- **SIP-0062** governs **client-side validation** — how the Runtime API validates tokens (`AuthPort`, `AuthorizationPort`, JWKS caching, clock skew).
- **SIP-0063** governs **server-side policy** — what Keycloak issues, how long tokens live, which redirect URIs are permitted, how admin access is separated, and how the IdP is operated.

0.9.2 is the point where Keycloak is treated as a **production-grade** component:
- hardened realm/client configuration,
- clear separation of admin roles,
- safe token/session policies,
- secure exposure of Keycloak surfaces,
- MFA enforcement strategy for privileged roles,
- operational readiness (backup/restore, upgrades, scaling posture),
- portability guardrails for future cloud IdP substitution.

This SIP does **not** redefine the auth boundary; it operationalizes it.

---

# 2. Background

SIP-0062 establishes OIDC-based auth for:
- Console (Authorization Code + PKCE)
- Runtime API (resource server validating JWTs)
- Service-to-service clients (client credentials)

Once enabled, Keycloak becomes critical infrastructure. Poor Keycloak defaults create long-term issues:
- overly permissive redirect URIs,
- weak token lifetime policies,
- overly broad admin access,
- insecure exposure of admin UIs,
- lack of rotation/revocation strategy,
- unclear realm separation and migration paths.

0.9.2 formalizes a secure, repeatable posture.

---

# 3. Problem Statements

1. Default Keycloak configs are rarely "production safe" without hardening.
2. Console and Runtime API clients require tighter redirect/token/audience discipline.
3. Admin and operational roles must be separated from application-level roles.
4. Secrets and bootstrap credentials must be managed safely and rotated.
5. Production deploys need documented backup/restore and upgrade procedures.
6. Privileged roles (admin, operator) lack MFA enforcement, leaving credentials as single-factor attack surface.

---

# 4. Scope

## In Scope (0.9.2)
- Realm separation and naming conventions
- Client configuration hardening (public/confidential, redirect URIs, audiences)
- Token and session lifetime policy
- Refresh token rotation strategy
- RBAC hardening and role mapping discipline (connection to SIP-0062 `roles_client_id`)
- Admin surface controls and audit posture
- MFA enforcement strategy (conditional per role, with Keycloak authentication flow config)
- Operational guidance: DB, backups, upgrades, logging, scaling notes
- `KeycloakOperationalConfig` Pydantic schema for deployment profile keys
- Realm export JSON extensions in `infra/auth/`
- Ingress/TLS/proxy correctness requirements and cookie security posture
- Signing key rotation policy and incident recovery procedure
- Audience mapper configuration for Console → Runtime API token flow

## Out of Scope (0.9.2)
- SCIM provisioning
- Full corporate federation playbooks (SAML/IdP brokering)
- Multi-tenant SaaS isolation model beyond realm separation
- Advanced ABAC engines (OPA/Cedar)
- mTLS between all services (may be separate SIP)
- Changes to `AuthPort` or `AuthorizationPort` contracts (SIP-0062 owns these)

---

# 5. Design Overview

## 5.1 Relationship to SIP-0062 (Hexagonal Boundary)

This SIP does **not** introduce new ports or adapters. The hexagonal boundary is established by SIP-0062:

```
src/squadops/ports/auth/     ← SIP-0062 (unchanged)
adapters/auth/keycloak/      ← SIP-0062 (unchanged)
adapters/auth/factory.py     ← SIP-0062 (unchanged)

src/squadops/config/schema.py
  └── AuthConfig             ← SIP-0062 (client-side validation config)
  └── KeycloakOperationalConfig  ← SIP-0063 (server-side policy config, NEW)

infra/auth/
  ├── squadops-realm.json         ← SIP-0062 (bootstrap realm)
  ├── squadops-realm-staging.json ← SIP-0063 (hardened realm, NEW)
  └── squadops-realm-prod.json    ← SIP-0063 (hardened realm, NEW)
```

**SIP-0063 adds configuration and operational posture — not domain logic.**

## 5.2 Environment Strategy (Realm Separation)

Keycloak deployments MUST support environment separation using either:
- **separate realms** per environment within a Keycloak cluster, OR
- separate Keycloak instances per environment

0.9.2 recommendation:
- Local/dev: single instance, single realm
- Staging/prod: separate instance per environment (preferred), or separate realms if operationally simpler

### Realm Naming (Normative)
- `squadops-local`
- `squadops-staging`
- `squadops-prod`

## 5.3 Client Strategy

### Console Client (Public Client)
- Type: **public**
- Flow: Authorization Code + PKCE
- Redirect URIs: explicit allowlist, no wildcards
- Post-logout redirect URIs: explicit allowlist
- Web origins: explicit allowlist
- Token storage: dictated by Console implementation; Keycloak must not encourage unsafe patterns

### Runtime API Resource Server
Runtime API remains the resource server; Keycloak configuration must:
- issue tokens with correct `iss`, `aud`, and role claims
- support audience discipline (no "everything" tokens)

### Service Clients (Confidential Clients)
- Type: **confidential**
- Flow: Client Credentials
- Secrets: supplied via `secret://` references only (SIP-0052)
- Rotation: supported and documented

## 5.4 Role Mapping Discipline (Connection to SIP-0062)

SIP-0062 defines `roles_mode` and `roles_client_id` in `AuthConfig`. This SIP establishes the recommended production posture:

**Staging/prod profile defaults:**
```yaml
auth:
  roles_mode: client
  roles_client_id: squadops-runtime
```

- **Client roles** for application-specific roles, scoped to the `squadops-runtime` client.
- Realm roles reserved for shared, cross-application concerns only.
- This avoids role namespace pollution when Keycloak serves multiple applications.

Application roles remain:
- `admin`
- `operator`
- `viewer`

These are configured as **client roles** on the `squadops-runtime` client in Keycloak, and extracted by `KeycloakAuthzAdapter` via the `roles_client_id` config key.

---

# 6. Functional Requirements (Hardening)

## 6.1 Redirect URI and Origin Hardening (Normative)
- No wildcard redirect URIs in staging/prod
- Redirect URIs must be explicit and environment-scoped
- Web origins must be explicit
- Disallow insecure HTTP in staging/prod (HTTPS only)

## 6.2 Token and Session Policy (Normative)

Define baseline policies. Values are recommended defaults; profiles may override with documented rationale.

| Policy | Default | Notes |
|--------|---------|-------|
| Access token lifetime | 10 minutes | Short-lived; Console refreshes via IdP |
| Refresh token lifetime | 1440 minutes (24h) | Bounded; operator workflow consideration |
| Session idle timeout | 30 minutes | Bounded |
| Session max lifespan | 480 minutes (8h) | Bounded; forces re-auth daily |
| Clock skew tolerance | 60 seconds | Must match SIP-0062 `clock_skew_seconds` |

These are **server-side policies** (what Keycloak issues). The corresponding **client-side tolerance** is `clock_skew_seconds` in SIP-0062's `OIDCConfig`.

### Refresh Token Rotation (Normative)
- Refresh token rotation MUST be enabled in staging/prod.
- On each refresh, Keycloak issues a new refresh token and invalidates the previous one.
- Revocation strategy: logout invalidates all session tokens; admin can revoke per-user.
- Console behavior: on refresh failure, redirect to login (do not retry with stale token).

## 6.3 Audience and Claims Discipline (Normative)
- Tokens MUST contain only necessary roles/claims.
- Audience MUST be configured so Runtime API can strictly validate it.
- Avoid multi-audience "kitchen sink" tokens unless explicitly required and documented.
- Token claim bloat: prefer client roles over realm roles to minimize JWT payload size.

### Keycloak Audience Mapper (Required)

The `squadops-console` client MUST have a **protocol mapper** of type `oidc-audience-mapper` configured so that tokens issued for the Console include the Runtime API's audience value in the `aud` claim:

| Mapper Setting | Value |
|----------------|-------|
| Name | `squadops-runtime-audience` |
| Mapper Type | Audience |
| Included Client Audience | `squadops-runtime` |
| Add to access token | `true` |
| Add to ID token | `false` |

This ensures:
- Console tokens contain `"aud": ["squadops-console", "squadops-runtime"]` (or `"aud": "squadops-runtime"` if single-valued).
- Runtime API validates `aud` against its configured `auth.oidc.audience` value (SIP-0062), which MUST be set to `squadops-runtime`.
- Service client tokens (client credentials for `squadops-runtime`) naturally have `aud: squadops-runtime` without an explicit mapper.

The hardened realm exports (`infra/auth/squadops-realm-staging.json`, `squadops-realm-prod.json`) MUST include this mapper definition.

## 6.4 Admin Role Separation (Normative)

Separate:
- **Keycloak admin** (IdP operations — realm config, client management, user provisioning)
- **SquadOps admin** (application operations — start/stop cycles, manage agents, destructive actions)

Rules:
- Keycloak admin users are NOT automatically SquadOps admins.
- SquadOps admin role assignment is explicit and least-privilege.
- Bootstrap admin user (SIP-0062) is a one-time setup credential; production users MUST be provisioned separately.

## 6.5 Audit Logging (Normative)

Keycloak MUST be configured so that:
- Admin events are auditable (realm config changes, client changes, role assignments)
- Authentication failures are observable (failed logins, expired tokens)
- High-risk events (role changes, client config changes, user deletions) are logged

Exact sink (stdout/OTel) is deployment-specific; events must be available for incident investigation. This complements the application-level `AuditPort` (SIP-0062 Phase 3b) which logs Runtime API authorization decisions.

## 6.6 MFA Enforcement Strategy (Normative)

### 6.6.1 Rationale

Privileged roles (`admin`, `operator`) control destructive actions (start/stop cycles, manage agents, modify configuration). Single-factor authentication (password only) leaves these accounts vulnerable to credential stuffing, phishing, and password reuse. MFA is the industry-standard mitigation.

### 6.6.2 Enforcement Policy

MFA enforcement is **role-conditional**, implemented via Keycloak authentication flow configuration:

| Role | MFA Requirement | Enforcement |
|------|----------------|-------------|
| `admin` | **Required** in staging/prod | Keycloak conditional authentication flow |
| `operator` | **Required** in prod; recommended in staging | Keycloak conditional authentication flow |
| `viewer` | Optional (password-only acceptable) | No flow override |

### 6.6.3 Implementation via Keycloak Conditional Flows

Keycloak supports conditional MFA via **authentication flow overrides**. The implementation:

1. **Create a custom authentication flow** (e.g., `squadops-browser-with-mfa`) that extends the default browser flow:
   - Username/Password form (required)
   - Conditional OTP sub-flow:
     - Condition: user has role `admin` OR `operator` → require OTP
     - Otherwise: skip OTP

2. **Bind the custom flow** as the browser flow for the `squadops-console` client.

3. **Realm export**: The hardened realm JSON (`infra/auth/squadops-realm-prod.json`) MUST include:
   - The custom authentication flow definition
   - OTP policy configuration (TOTP, 6 digits, 30-second period, SHA-1 or SHA-256)
   - The client flow binding override

### 6.6.4 Supported MFA Methods

| Method | Status | Notes |
|--------|--------|-------|
| TOTP (authenticator app) | **Required support** | Google Authenticator, Authy, 1Password, etc. |
| WebAuthn/FIDO2 (security key) | **Optional support** | Higher security; requires Keycloak WebAuthn policy config |

TOTP is the minimum viable MFA method. WebAuthn MAY be enabled as an alternative or upgrade path.

### 6.6.5 Configuration Keys

```yaml
auth:
  keycloak:
    security:
      mfa_required_for_admin: true      # Enforced in staging/prod
      mfa_required_for_operator: true    # Enforced in prod; recommended in staging
      mfa_method: "totp"                 # "totp" | "webauthn" | "totp+webauthn"
      totp_policy:
        algorithm: "HmacSHA1"            # Keycloak default
        digits: 6
        period: 30
```

### 6.6.6 Local Dev Posture

Local dev (`squadops-local` realm) MAY disable MFA for convenience:
```yaml
auth:
  keycloak:
    security:
      mfa_required_for_admin: false
      mfa_required_for_operator: false
```

This is acceptable because local dev already uses the Keycloak bootstrap profile (SIP-0062) and is not exposed externally.

### 6.6.7 Brute-Force Protection

Keycloak's built-in brute-force detection MUST be enabled in staging/prod:
- **Max login failures**: 5 (before temporary lockout)
- **Wait increment**: 60 seconds (doubles on repeated failures)
- **Max wait**: 15 minutes

Configuration key:
```yaml
auth:
  keycloak:
    security:
      brute_force_protection: true
      max_login_failures: 5
      wait_increment_seconds: 60
      max_wait_seconds: 900
```

## 6.7 Ingress, TLS, and Proxy Correctness (Normative)

When Keycloak runs behind an ingress controller or reverse proxy (the expected production topology), misconfigurations cause broken redirects, insecure cookies, and "works in dev, fails in prod" failures. Staging/prod deployments MUST satisfy:

### 6.7.1 Hostname and TLS

- Keycloak MUST be configured with strict hostname enforcement (`hostname_strict: true` in staging/prod). The authoritative external hostname is derived from `public_url`.
- External traffic MUST be HTTPS-only. TLS termination may occur at the ingress/proxy layer (`external_tls_termination: true`) or at Keycloak itself.
- When TLS is terminated externally, Keycloak MUST be configured in proxy mode so it trusts forwarded headers (`X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`) from the proxy.

### 6.7.2 Proxy Mode

The `proxy_mode` config key controls how Keycloak handles reverse proxy headers:

| `proxy_mode` | Meaning | When to use |
|--------------|---------|-------------|
| `edge` | TLS terminated at proxy; Keycloak receives HTTP | Most common: ingress/ALB/nginx terminates TLS |
| `reencrypt` | TLS at both proxy and Keycloak | High-security: end-to-end encryption |
| `passthrough` | Proxy forwards raw TLS; Keycloak terminates | When proxy cannot inspect traffic |
| `none` | No proxy (direct access) | Local dev only |

Staging/prod MUST NOT use `proxy_mode: none`.

### 6.7.3 Cookie Security

Session cookies issued by Keycloak MUST be configured with:
- `Secure` flag: **always** in staging/prod (requires HTTPS)
- `HttpOnly` flag: **always** (prevents JavaScript access to session cookies)
- `SameSite`: set to `Lax` by default. If Console is served from a different origin than Keycloak, evaluate whether `None` is required (with `Secure` flag mandatory per browser rules). The chosen value MUST be documented in the deployment profile.

### 6.7.4 Validation

Pydantic validation for `KeycloakOperationalConfig`:
- `proxy_mode` MUST NOT be `none` when realm name contains `staging` or `prod`.
- `hostname_strict` MUST be `true` when realm name contains `staging` or `prod`.
- `public_url` MUST be set when `external_tls_termination` is `true`.

---

# 7. Configuration Schema (Hex-Compliant)

## 7.1 Pydantic Schema

Keycloak operational config MUST be declared as a Pydantic section within `AppConfig`, loaded by the existing profile loader (SIP-0051). This config governs **server-side Keycloak posture** and is distinct from SIP-0062's `AuthConfig` which governs **client-side token validation**.

```python
# Addition to src/squadops/config/schema.py

class KeycloakTokenPolicyConfig(BaseModel):
    access_token_minutes: int = Field(default=10, ge=1, description="Access token lifetime")
    refresh_token_minutes: int = Field(default=1440, ge=1, description="Refresh token lifetime")
    refresh_token_rotation: bool = Field(default=True, description="Enable refresh token rotation")

class KeycloakSessionPolicyConfig(BaseModel):
    idle_minutes: int = Field(default=30, ge=1, description="Session idle timeout")
    max_minutes: int = Field(default=480, ge=1, description="Session max lifespan")

class KeycloakTotpPolicyConfig(BaseModel):
    algorithm: str = "HmacSHA1"
    digits: int = 6
    period: int = 30

class KeycloakSecurityConfig(BaseModel):
    mfa_required_for_admin: bool = True
    mfa_required_for_operator: bool = True
    mfa_method: str = "totp"  # "totp" | "webauthn" | "totp+webauthn"
    totp_policy: KeycloakTotpPolicyConfig = Field(default_factory=KeycloakTotpPolicyConfig)
    brute_force_protection: bool = True
    max_login_failures: int = Field(default=5, ge=1)
    wait_increment_seconds: int = Field(default=60, ge=1)
    max_wait_seconds: int = Field(default=900, ge=1)

class KeycloakLoggingConfig(BaseModel):
    admin_events_enabled: bool = True
    login_events_enabled: bool = True

class KeycloakAdminConfig(BaseModel):
    username: str = "admin"
    password: str  # Supports secret:// references
    allowed_networks: list[str] = Field(default_factory=list, description="CIDR allowlist for admin UI")

class KeycloakOperationalConfig(BaseModel):
    realm: str = "squadops-local"
    base_url: str = "http://localhost:8180"
    public_url: str | None = None  # Authoritative external URL; required when behind proxy
    db_dsn: str | None = None  # secret:// ref; required for staging/prod
    proxy_mode: str = "none"  # "none" | "edge" | "reencrypt" | "passthrough" (see 6.7.2)
    external_tls_termination: bool = False  # True when TLS terminates at proxy, not Keycloak
    hostname_strict: bool = False  # True in staging/prod; enforces public_url as authoritative
    admin: KeycloakAdminConfig
    token_policy: KeycloakTokenPolicyConfig = Field(default_factory=KeycloakTokenPolicyConfig)
    session_policy: KeycloakSessionPolicyConfig = Field(default_factory=KeycloakSessionPolicyConfig)
    security: KeycloakSecurityConfig = Field(default_factory=KeycloakSecurityConfig)
    logging: KeycloakLoggingConfig = Field(default_factory=KeycloakLoggingConfig)
```

Nested under `AuthConfig`:
```python
class AuthConfig(BaseModel):
    # ... existing SIP-0062 fields ...
    keycloak: KeycloakOperationalConfig | None = None  # Required when provider="keycloak"
```

## 7.2 Environment Variable Mapping

```
SQUADOPS__AUTH__KEYCLOAK__REALM
SQUADOPS__AUTH__KEYCLOAK__BASE_URL
SQUADOPS__AUTH__KEYCLOAK__PUBLIC_URL
SQUADOPS__AUTH__KEYCLOAK__DB_DSN
SQUADOPS__AUTH__KEYCLOAK__PROXY_MODE
SQUADOPS__AUTH__KEYCLOAK__EXTERNAL_TLS_TERMINATION
SQUADOPS__AUTH__KEYCLOAK__HOSTNAME_STRICT
SQUADOPS__AUTH__KEYCLOAK__ADMIN__USERNAME
SQUADOPS__AUTH__KEYCLOAK__ADMIN__PASSWORD
SQUADOPS__AUTH__KEYCLOAK__TOKEN_POLICY__ACCESS_TOKEN_MINUTES
SQUADOPS__AUTH__KEYCLOAK__TOKEN_POLICY__REFRESH_TOKEN_MINUTES
SQUADOPS__AUTH__KEYCLOAK__SESSION_POLICY__IDLE_MINUTES
SQUADOPS__AUTH__KEYCLOAK__SESSION_POLICY__MAX_MINUTES
SQUADOPS__AUTH__KEYCLOAK__SECURITY__MFA_REQUIRED_FOR_ADMIN
SQUADOPS__AUTH__KEYCLOAK__SECURITY__MFA_REQUIRED_FOR_OPERATOR
SQUADOPS__AUTH__KEYCLOAK__SECURITY__BRUTE_FORCE_PROTECTION
SQUADOPS__AUTH__KEYCLOAK__LOGGING__ADMIN_EVENTS_ENABLED
```

All secrets MUST be `secret://` references (SIP-0052).

---

# 8. Deployment & Operations

## 8.1 Keycloak Storage (Normative)

Staging/prod Keycloak MUST use an external persistent database (Postgres recommended).

Local/dev may use embedded/dev DB mode for convenience.

Pydantic validation: `KeycloakOperationalConfig` MUST reject `db_dsn = None` when realm name contains `staging` or `prod`.

## 8.2 Backups and Restore (Normative)

Document and enable:
- DB backup schedule for Keycloak DB
- Restore procedure test (at least once) for staging
- Realm export/import strategy for disaster recovery

## 8.3 Upgrade Strategy (Normative)

Define:
- Version pinning and upgrade cadence
- Staging-first upgrade requirement
- Rollback posture (DB snapshot prior to upgrade)

## 8.4 Signing Key Rotation and Incident Recovery (Normative)

Keycloak realm signing keys (RSA/EC keys used to sign JWTs) require a rotation and recovery strategy. This is the server-side companion to SIP-0062's JWKS caching and forced-refresh behavior.

### Rotation Policy

| Posture | Cadence | Notes |
|---------|---------|-------|
| **Scheduled rotation** | Not required in 0.9.2 | Keycloak auto-generates keys on realm creation; manual rotation is optional |
| **Incident-driven rotation** | On credential compromise or key leak | Rotate immediately; see recovery procedure below |

Scheduled key rotation MAY be introduced in a future SIP if operational maturity warrants it. For 0.9.2, the requirement is that rotation is **possible and safe**, not that it happens on a cadence.

### Key Overlap Requirement

When rotating signing keys, Keycloak MUST retain the previous key as **passive** (verification-only) for at least the duration of the maximum token lifetime + session max lifespan. This ensures:
- Tokens signed with the old key remain valid until natural expiry.
- SIP-0062's JWKS forced-refresh mechanism picks up the new active key.

**Minimum overlap period:** `access_token_minutes` + `session_policy.max_minutes` (default: 10 + 480 = 490 minutes ≈ 8.5 hours).

### Incident Recovery Procedure

If a signing key is compromised:
1. Rotate to a new active key in Keycloak (realm keys settings).
2. **Remove** the compromised key (do not retain as passive) — this intentionally invalidates all tokens signed with it.
3. All active sessions will fail validation on next request; users will be forced to re-authenticate.
4. SIP-0062's JWKS forced-refresh (with stampede protection) handles the thundering herd.
5. Document the incident and rotation in ops log.

## 8.5 Exposure and Network Controls (Normative)
- Keycloak admin UI MUST NOT be exposed publicly without explicit decision.
- Preferred: restrict admin UI by network boundary (VPN, private subnet, `admin.allowed_networks` CIDR allowlist).
- **Admin UI exposure requires BOTH** a network allowlist (or private network placement) **AND** an explicit operator decision recorded in the deployment profile config or release notes. Neither condition alone is sufficient.
- Runtime API and Console communicate via standard OIDC endpoints only.

---

# 9. Must Not (Normative)

1. No wildcard redirect URIs in staging/prod.
2. No public exposure of Keycloak admin UI without explicit allowlist controls.
3. No shared credentials committed to repo or docker compose.
4. No "long-lived access tokens" as a default posture (access tokens MUST be ≤ 15 minutes in staging/prod).
5. No automatic mapping of Keycloak admins to SquadOps admins.
6. No single-factor authentication for `admin` role in staging/prod (MFA required).
7. No disabling brute-force protection in staging/prod.
8. No `proxy_mode: none` or `hostname_strict: false` in staging/prod.
9. No admin UI exposure without both network restriction and explicit operator decision.

---

# 10. Implementation Strategy (Phased)

## Phase 1: Config Schema + Realm Hardening
- Add `KeycloakOperationalConfig` Pydantic schema to `AppConfig`
- Create hardened realm exports (`infra/auth/squadops-realm-staging.json`, `squadops-realm-prod.json`)
- Tighten redirect URI allowlists per environment
- Set token/session lifetime policies
- Configure client roles on `squadops-runtime` client
- Set `roles_mode: client` and `roles_client_id: squadops-runtime` in staging/prod profiles
- Enable refresh token rotation
- Configure MFA conditional authentication flow in realm export
- Enable brute-force protection
- Configure audience mapper on Console client for Runtime API `aud` claim
- Set `proxy_mode`, `hostname_strict`, and `external_tls_termination` per environment profile

*Phase 1 is independently shippable. Delivers code-enforceable security improvements.*

## Phase 2: Operational Posture
- Configure Keycloak with external Postgres for staging/prod
- Document and test backup/restore procedures
- Document upgrade strategy with staging-first requirement
- Enable admin event and login event logging
- Configure admin UI network restrictions
- Verify admin role separation (Keycloak admin ≠ SquadOps admin)
- Perform staging backup/restore drill

*Phase 2 is independently shippable. Delivers operational readiness.*

---

# 11. Testing Requirements

## 11.1 Unit Tests
- `KeycloakOperationalConfig` Pydantic validation (valid and invalid configs)
- `db_dsn` required for staging/prod realm names
- `mfa_required_for_admin` defaults to `true`
- Config profile loading with env var overrides

## 11.2 Integration Tests (Required)
- Console login works in local realm
- Runtime API rejects: wrong issuer, wrong audience, expired token, insufficient role
- Service client credentials flow succeeds for a protected endpoint
- Logout and refresh token behavior matches configured policy
- Refresh token rotation: old refresh token rejected after rotation

## 11.3 Operational Checks (Required, Staging)
- Realm export/import works
- Keycloak DB backup/restore drill performed at least once
- Admin event logging verified (role change event appears in log)
- MFA conditional flow: admin user prompted for OTP, viewer user is not
- Brute-force lockout triggers after configured failure count
- Proxy/hostname correctness: login redirect and post-logout redirect resolve to `public_url` (no internal hostname leakage in Location headers)
- Cookie security: session cookies have `Secure` flag set, `HttpOnly` flag set, and `SameSite` value matches deployment profile

Test markers: `@pytest.mark.auth`, `@pytest.mark.integration`

---

# 12. Migration Notes

Upgrading from 0.9.1 (boundary enabled) to 0.9.2 (hardened) includes:
- Tightening redirect URI allowlists
- Adjusting token lifetimes (may force re-login for active sessions)
- Enabling refresh token rotation (existing refresh tokens may be invalidated)
- Separating admin identities and enforcing least privilege
- Enabling MFA for admin/operator roles (requires user enrollment)

**MFA rollout strategy:**
1. Enable MFA as optional first (users can enroll voluntarily)
2. Communicate enrollment deadline
3. Enable MFA as required (users without enrolled MFA will be prompted at next login)

Any breaking changes to operator workflow must be documented and rolled out via staging first.

---

# 13. Definition of Done

## Phase 1: Config + Realm Hardening
- [ ] `KeycloakOperationalConfig` Pydantic schema in `AppConfig` with profile-based loading
- [ ] Hardened realm exports for staging/prod in `infra/auth/`
- [ ] Console client: public + PKCE with strict redirect/origin allowlists (no wildcards)
- [ ] Service clients: confidential with secrets via `secret://` (SIP-0052)
- [ ] Token/session policies explicitly set per environment profile
- [ ] Refresh token rotation enabled in staging/prod
- [ ] Staging/prod profiles set `roles_mode: client` + `roles_client_id: squadops-runtime`
- [ ] MFA conditional authentication flow configured in realm export
- [ ] Brute-force protection enabled in staging/prod
- [ ] Admin roles separated (Keycloak admin ≠ SquadOps admin)
- [ ] Audience mapper configured on Console client (`aud` includes `squadops-runtime`)
- [ ] `proxy_mode`, `hostname_strict`, `external_tls_termination` set per environment profile
- [ ] Cookie security: `Secure`, `HttpOnly`, `SameSite` configured and documented

## Phase 2: Operational Posture
- [ ] Staging/prod Keycloak uses persistent external DB (`db_dsn` validated)
- [ ] Backup/restore procedures documented and tested in staging
- [ ] Upgrade strategy documented with staging-first requirement
- [ ] Admin/audit logging enabled and verified
- [ ] Admin UI network-restricted via `allowed_networks` config + explicit operator decision documented
- [ ] Signing key rotation procedure documented and tested (incident recovery)
- [ ] Proxy/hostname operational check passes (no internal hostname leakage)
- [ ] Cookie security operational check passes (Secure, HttpOnly, SameSite verified)
- [ ] Integration tests validate hardening behaviors
- [ ] MFA enrollment + enforcement rollout plan documented

---

# 14. Portability Notes (Informative)

This SIP hardens Keycloak, but the overall system remains portable because the Runtime API enforces (via SIP-0062 `AuthPort`):
- issuer validation
- audience validation
- JWKS signature validation
- role/scope checks via `AuthorizationPort`

If later switching IdP (Cognito/Entra/GCP), ensure:
- equivalent token lifetime policies are applied,
- role claims map consistently (via `roles_claim_path` / `roles_client_id`),
- redirect URI allowlists are enforced,
- client credentials flow exists for service identities,
- MFA enforcement is available via the replacement IdP's authentication policy.

---

# 15. References

- **SIP-0051** — Config Profiles and Validation
- **SIP-0052** — Secrets Management (`secret://` scheme)
- **SIP-0062** — OIDC Authentication & Authorization Boundary (ports, adapters, middleware)
