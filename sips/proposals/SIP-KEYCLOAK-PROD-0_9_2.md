# SIP-KEYCLOAK-PROD-0_9_2 — Version Target 0.9.2  
## Keycloak Production Hardening, Operational Posture, and Enterprise-Ready Configuration

# 1. Purpose and Intent

This SIP defines the **0.9.2 production hardening** requirements for the Keycloak-based Identity Provider used by SquadOps, building on the functional boundary established in **SIP-AUTH-BOUNDARY**.

0.9.2 is the point where Keycloak is treated as a **production-grade** component:
- hardened realm/client configuration,
- clear separation of admin roles,
- safe token/session policies,
- secure exposure of Keycloak surfaces,
- operational readiness (backup/restore, upgrades, scaling posture),
- portability guardrails for future cloud IdP substitution.

This SIP does **not** redefine the auth boundary; it operationalizes it.

# 2. Background

SIP-AUTH-BOUNDARY establishes OIDC-based auth for:
- Console (Authorization Code + PKCE)
- Runtime API (resource server validating JWTs)
- Service-to-service clients (client credentials)

Once enabled, Keycloak becomes critical infrastructure. Poor Keycloak defaults tend to create long-term issues:
- overly permissive redirect URIs,
- weak token lifetime policies,
- overly broad admin access,
- insecure exposure of admin UIs,
- lack of rotation/revocation strategy,
- unclear realm separation and migration paths.

0.9.2 formalizes a secure, repeatable posture.

# 3. Problem Statements

1. Default Keycloak configs are rarely “production safe” without hardening.
2. Console and Runtime API clients require tighter redirect/token/audience discipline.
3. Admin and operational roles must be separated from application-level roles.
4. Secrets and bootstrap credentials must be managed safely and rotated.
5. Production deploys need documented backup/restore and upgrade procedures.

# 4. Scope

## In Scope (0.9.2)
- Realm separation and naming conventions
- Client configuration hardening (public/confidential, redirect URIs, audiences)
- Token and session lifetime policy
- Refresh token rotation strategy
- RBAC hardening and role mapping discipline
- Admin surface controls and audit posture
- Security enhancements (MFA/WebAuthn) as **optional but spec’d**
- Operational guidance: DB, backups, upgrades, logging, scaling notes
- Deployment profile keys and secrets mapping for Keycloak itself

## Out of Scope (0.9.2)
- SCIM provisioning
- Full corporate federation playbooks (SAML/IdP brokering)
- Multi-tenant SaaS isolation model beyond realm separation
- Advanced ABAC engines (OPA/Cedar)
- mTLS between all services (may be separate SIP)

# 5. Design Overview

## 5.1 Environment Strategy (Realm Separation)

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

## 5.2 Client Strategy

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
- support audience discipline (no “everything” tokens)

### Service Clients (Confidential Clients)
- Type: **confidential**
- Flow: Client Credentials
- Secrets: supplied via SIP-SECRETS-MANAGEMENT only
- Rotation: supported and documented

## 5.3 Role Mapping Discipline

Finalize the decision from SIP-AUTH-BOUNDARY:
- `auth.roles.mode = realm | client`

0.9.2 default recommendation:
- **client roles** for application-specific roles (e.g., `squadops-runtime-api`)
- keep realm roles minimal for shared, human-facing roles only if needed

Roles remain:
- `admin`
- `operator`
- `viewer`

# 6. Functional Requirements (Hardening)

## 6.1 Redirect URI and Origin Hardening (Normative)
- No wildcard redirect URIs in staging/prod
- Redirect URIs must be explicit and environment-scoped
- Web origins must be explicit
- Disallow insecure HTTP in staging/prod

## 6.2 Token and Session Policy (Normative)

Define baseline policies (values are recommended defaults; profiles may override with documented rationale):

- Access token lifetime: **short** (e.g., 5–15 minutes)
- Refresh token lifetime: bounded (e.g., hours/days depending on operator workflow)
- Session idle timeout: bounded
- Session max lifespan: bounded
- Clock skew tolerance: minimal and consistent with runtime-api

### Refresh Token Rotation (Normative)
- Enable refresh token rotation where supported
- Define a revocation strategy (logout and admin revoke)
- Document behavior for console sessions and operator workflows

## 6.3 Audience and Claims Discipline (Normative)
- Tokens MUST contain only necessary roles/claims
- Audience MUST be configured so runtime-api can strictly validate it
- Avoid multi-audience “kitchen sink” tokens unless explicitly required and documented

## 6.4 Admin Role Separation (Normative)
Separate:
- **Keycloak admin** (IdP operations)
- **SquadOps admin** (application operations)

Rules:
- Keycloak admin users are not automatically SquadOps admins.
- SquadOps admin role assignment is explicit and least-privilege.

## 6.5 Audit Logging (Normative)
Keycloak MUST be configured so that:
- admin events are auditable
- authentication failures are observable
- high-risk events (role changes, client config changes) are logged

Exact sink (stdout/OTel) is deployment-specific; events must be available.

## 6.6 Optional Strong Auth Features (Spec’d, Optional)
These are optional in 0.9.2 but must be spec’d so enabling them later is low-friction:

- MFA requirement policy for `admin` and/or `operator`
- WebAuthn/FIDO2 enablement path
- Brute-force protection enablement

If enabled:
- admin must require MFA
- operator may require MFA in production
- viewer may remain password-only (policy choice)

# 7. Deployment & Operations

## 7.1 Keycloak Storage (Normative)
Staging/prod Keycloak MUST use an external persistent database (Postgres recommended).

Local/dev may use embedded/dev DB mode for convenience.

## 7.2 Backups and Restore (Normative)
Document and enable:
- DB backup schedule for Keycloak DB
- restore procedure test (at least once) for staging
- realm export/import strategy for disaster recovery

## 7.3 Upgrade Strategy (Normative)
Define:
- version pinning and upgrade cadence
- staging-first upgrade requirement
- rollback posture (DB snapshot prior to upgrade)

## 7.4 Exposure and Network Controls (Normative)
- Keycloak admin UI must not be exposed publicly without explicit decision
- Preferred: restrict admin UI by network boundary (VPN, private subnet, allowlist)
- Runtime API and Console communicate via standard OIDC endpoints

# 8. Configuration Contract (Deployment Profiles)

Auth boundary keys remain in SIP-AUTH-BOUNDARY. This SIP adds Keycloak operational keys:

- `auth.keycloak.realm`
- `auth.keycloak.admin.username`
- `auth.keycloak.admin.password = secret://...`
- `auth.keycloak.admin.allowed_networks` (optional)
- `auth.keycloak.base_url`
- `auth.keycloak.public_url` (if behind proxy/ingress)
- `auth.keycloak.db.dsn = secret://...` (for prod) OR profile-based DB keys if shared bootstrap is used
- `auth.keycloak.token_policy.access_token_minutes`
- `auth.keycloak.token_policy.refresh_token_minutes`
- `auth.keycloak.session_policy.idle_minutes`
- `auth.keycloak.session_policy.max_minutes`
- `auth.keycloak.security.mfa_required_for_admin` (bool)
- `auth.keycloak.security.mfa_required_for_operator` (bool)
- `auth.keycloak.logging.admin_events_enabled` (bool)

All secrets MUST be `secret://` references.

# 9. Must Not (Normative)

1. No wildcard redirect URIs in staging/prod.
2. No public exposure of Keycloak admin UI without explicit allowlist controls.
3. No shared credentials committed to repo or docker compose.
4. No “long-lived access tokens” as a default posture.
5. No automatic mapping of Keycloak admins to SquadOps admins.

# 10. Testing Requirements

## 10.1 Integration Tests (Required)
- Console login works in local realm
- Runtime API rejects:
  - wrong issuer
  - wrong audience
  - expired token
  - insufficient role
- Service client credentials flow succeeds for a protected endpoint
- Logout and refresh token behavior matches configured policy

## 10.2 Operational Checks (Required)
- Realm export/import works (staging)
- Keycloak DB backup/restore drill performed at least once (staging)
- Admin event logging verified (staging)

# 11. Migration Notes

Upgrading from 0.9.1 (boundary enabled) to 0.9.2 (hardened) includes:
- tightening redirect URI allowlists
- adjusting token lifetimes
- enabling rotation/revocation behaviors
- separating admin identities and enforcing least privilege

Any breaking changes to operator workflow must be documented and rolled out via staging first.

# 12. Definition of Done

- [ ] Realms are environment-scoped with clear naming
- [ ] Console client is public + PKCE with strict redirect/origin allowlists
- [ ] Service clients are confidential with secrets via `secret://`
- [ ] Token/session policies are explicitly set and documented
- [ ] Refresh token rotation strategy is enabled or explicitly deferred with rationale
- [ ] Admin roles are separated (Keycloak admin ≠ SquadOps admin)
- [ ] Admin/audit logging posture is enabled and verified
- [ ] Staging/prod Keycloak uses persistent external DB
- [ ] Backup/restore and upgrade procedures are documented and staged
- [ ] Integration tests validate auth hardening behaviors

# 13. Appendix — Portability Notes (Informative)

This SIP hardens Keycloak, but the overall system remains portable because the Runtime API enforces:
- issuer
- audience
- JWKS signature validation
- role/scope checks

If later switching IdP (Cognito/Entra/GCP), ensure:
- equivalent token policies are applied,
- role claims map consistently,
- redirect URI allowlists are enforced,
- client credentials flow exists for service identities.
