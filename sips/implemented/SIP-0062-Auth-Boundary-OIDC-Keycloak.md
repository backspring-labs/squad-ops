---
sip_number: 62
title: OIDC-Based Authentication & Authorization Boundary (Keycloak-First, Provider-Portable)
status: implemented
author: Jason Ladd
approver: jladd
created_at: '2026-02-07T00:00:00Z'
updated_at: '2026-02-07T20:19:45.902321Z'
original_filename: SIP-AUTH-BOUNDARY-0_9_1.md
---
# SIP-0062 — OIDC Authentication & Authorization Boundary

**Target Version:** 0.9.1
**Roles Impacted:** Lead, Strategy, Dev, QA, Data

---

# 1. Purpose and Intent

This SIP defines the **authentication and authorization boundary** for SquadOps, expressed through the project's hexagonal architecture (ports & adapters), dependency injection, and DDD-patterned domain models.

The design establishes:
- An **`AuthPort`** for token validation and identity resolution — the contract that any OIDC provider must satisfy.
- An **`AuthorizationPort`** for role/scope enforcement — provider-agnostic RBAC evaluation.
- A **Keycloak adapter** as the 0.9.x reference implementation.
- **Domain models** (frozen dataclasses) for identity, roles, and authorization context.
- **Factory functions** for adapter selection based on deployment profiles.
- **Core purity**: domain auth logic MUST NOT import from `adapters/`.

The intent is to prevent "bolt-on" security, introduce consistent identity and access control before 1.0, and ensure the auth boundary is testable in isolation via mock port injection — the same pattern used for `SecretProvider`, `DbRuntime`, `QueuePort`, and `LLMObservabilityPort`.

---

# 2. Background

SquadOps is evolving toward nightly autonomous cycles and a broader operational console (Continuum). As soon as you can start/stop cycles, inspect agent state, view logs/artifacts, and trigger actions, you need a coherent security boundary.

The existing hexagonal architecture provides clean separation:
- **Ports** (`src/squadops/ports/`) define abstract contracts
- **Adapters** (`adapters/`) provide concrete implementations
- **Core** (`src/squadops/core/`) holds domain logic with zero adapter imports
- **Config** (`src/squadops/config/schema.py`) uses Pydantic models with profile-based loading

ACI lineage, observability, and admin surfaces are materially more valuable with authenticated identity attached. This SIP extends the hexagonal pattern to cover identity and authorization as first-class ports.

Keycloak provides an open-source OIDC Identity Provider suitable for local and self-hosted deployments and is commonly used as an IdP in enterprise environments.

---

# 3. Problem Statements

1. The Console and Runtime API require a consistent identity model and access control.
2. Without a formal **port interface**, auth logic cannot be tested in isolation without standing up a real IdP.
3. Admin functions require stronger controls than basic read-only status views.
4. Tokens and secrets must be managed safely via the existing `secret://` scheme (SIP-0052).
5. The system must support both human users and service identities (client credentials).
6. Without a boundary, "internal" endpoints will proliferate without protection.

---

# 4. Scope

## In Scope (0.9.1)
- `AuthPort` interface in `src/squadops/ports/auth/`
- `AuthorizationPort` interface in `src/squadops/ports/auth/`
- Domain models for `Identity`, `AuthContext`, `Role`, `TokenClaims` in `src/squadops/auth/models.py`
- Keycloak adapter in `adapters/auth/keycloak/`
- Factory function in `adapters/auth/factory.py`
- JWT validation middleware for Runtime API (FastAPI dependency)
- Role/scope-based authorization decorators
- Auth config section in `AppConfig` schema (`src/squadops/config/schema.py`)
- Keycloak bootstrap profile for local development (Docker Compose)
- Service-to-service authentication (client credentials) for trusted internal services
- Secret resolution for client secrets via `secret://` references (SIP-0052)
- OIDC login for Console (Authorization Code + PKCE)
- JWKS caching and key rotation handling
- Middleware ordering specification for FastAPI

## Out of Scope
- SCIM provisioning, HR integrations
- Advanced policy engines (OPA, Cedar) beyond role/scope checks
- Full multi-tenant SaaS isolation model
- FIDO2/WebAuthn policy tuning
- mTLS everywhere
- SSO federation to corporate IdPs (Keycloak supports it; not required in 0.9.1 DoD)
- Token refresh proxy endpoint on Runtime API (Console owns refresh directly with IdP)

---

# 5. Design Overview

## 5.1 Hexagonal Structure

```
src/squadops/
├── ports/auth/
│   ├── __init__.py
│   ├── authentication.py    # AuthPort (ABC) — token validation, identity resolution
│   └── authorization.py     # AuthorizationPort (ABC) — role/scope enforcement
├── auth/
│   └── models.py            # Identity, AuthContext, Role, TokenClaims (frozen dataclasses)
└── config/
    └── schema.py            # AuthConfig added to AppConfig

adapters/auth/
├── __init__.py
├── factory.py               # create_auth_provider(), create_authorization_provider()
└── keycloak/
    ├── __init__.py
    ├── auth_adapter.py      # KeycloakAuthAdapter(AuthPort)
    └── authz_adapter.py     # KeycloakAuthzAdapter(AuthorizationPort)

tests/
└── _stubs/
    └── auth.py              # TestStubAuthAdapter (test-only, never in runtime config)
```

**Dependency Rule:** `src/squadops/` MUST NOT import from `adapters/`. Adapters depend inward on ports.

**Runtime Provider Rule:** The runtime MUST NOT support any authentication provider that grants privileges without credential validation in non-test environments.

## 5.2 Surfaces and Trust Boundaries

| Surface | Type | Auth Mechanism |
|---------|------|----------------|
| Console UI | Public client | Authorization Code + PKCE |
| Runtime API | Resource server | Bearer JWT validation via `AuthPort` |
| Agent-to-runtime | Internal (network boundary) | Optional client credentials |
| Health checks | Internal | Unauthenticated allowlist (`/health`) |
| SOC ledger ingestion | Internal service | Client credentials via `AuthPort` |

**Policy:** Runtime API is a protected resource server even if network-private.

## 5.3 Call-Site Responsibility

| Component | Owns |
|-----------|------|
| **FastAPI middleware** | Token extraction, `AuthPort.validate_token()` call |
| **Endpoint decorators** | `AuthorizationPort.check_access()` per route |
| **Console frontend** | OIDC login flow, token storage, token refresh (directly with IdP) |
| **Config loader** | Auth config validation, secret resolution |
| **Factory** | Adapter instantiation based on `auth.provider` profile key |

## 5.4 Middleware Ordering (Normative)

Auth middleware MUST be ordered within the FastAPI middleware stack as follows:

1. **Request-ID injection middleware** — runs first, so all downstream logs (including auth failures) are traceable.
2. **Auth middleware** — extracts bearer token, calls `AuthPort.validate_token()`, injects `Identity` into request state.
3. **Exception-to-response mapping** — runs after auth, so 401/403 semantics are not masked by generic error handlers.

This ordering ensures auth failures are always traceable (request-ID present) and always return correct HTTP status codes (not wrapped in 500).

---

# 6. Functional Requirements

## 6.1 AuthPort Contract

```python
# src/squadops/ports/auth/authentication.py
from abc import ABC, abstractmethod
from squadops.auth.models import Identity, TokenClaims

class AuthPort(ABC):
    """Contract for token validation and identity resolution.

    Adapters MUST validate issuer, audience, signature, and expiry.
    Adapters MUST enforce clock skew tolerance.
    Adapters MUST reject tokens missing required claims.
    """

    @abstractmethod
    async def validate_token(self, token: str) -> TokenClaims:
        """Validate a bearer token and return parsed claims.

        Raises:
            TokenValidationError: Invalid, expired, or malformed token.
        """
        pass

    @abstractmethod
    async def resolve_identity(self, claims: TokenClaims) -> Identity:
        """Map validated claims to a domain Identity.

        Raises:
            IdentityResolutionError: Claims cannot map to a valid identity.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Release resources (JWKS cache, HTTP clients)."""
        pass
```

## 6.2 AuthorizationPort Contract

```python
# src/squadops/ports/auth/authorization.py
from abc import ABC, abstractmethod
from squadops.auth.models import Identity, AuthContext

class AuthorizationPort(ABC):
    """Contract for role/scope-based access control.

    Implementations enforce RBAC rules against the resolved Identity.
    """

    @abstractmethod
    def check_access(
        self, identity: Identity, required_roles: list[str], required_scopes: list[str]
    ) -> AuthContext:
        """Evaluate whether identity has required roles/scopes.

        Returns AuthContext with granted=True/False and denial reason.
        """
        pass
```

## 6.3 Domain Models

```python
# src/squadops/auth/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class TokenClaims:
    """Parsed JWT claims — provider-agnostic.

    audience may be a single string or a tuple of strings (per RFC 7519 §4.1.3).
    Validation: the configured audience (from OIDCConfig) MUST be contained in
    the token's aud claim — either as a string match or membership in the list.
    """
    subject: str
    issuer: str
    audience: str | tuple[str, ...]  # Single value or multi-valued per RFC 7519
    expires_at: datetime
    issued_at: datetime
    roles: tuple[str, ...] = field(default_factory=tuple)
    scopes: tuple[str, ...] = field(default_factory=tuple)
    raw_claims: dict = field(default_factory=dict, repr=False)

@dataclass(frozen=True)
class Identity:
    """Resolved domain identity."""
    user_id: str
    display_name: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    scopes: tuple[str, ...] = field(default_factory=tuple)
    identity_type: str = "human"  # "human" | "service"

@dataclass(frozen=True)
class AuthContext:
    """Result of an authorization check."""
    granted: bool
    identity: Identity | None = None
    denial_reason: str | None = None

class Role:
    """Canonical role constants."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class Scope:
    """Canonical scope constants."""
    CYCLES_READ = "cycles:read"
    CYCLES_WRITE = "cycles:write"
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    ADMIN_WRITE = "admin:write"
```

## 6.4 Authorization Model (RBAC Baseline)

| Role | Capabilities |
|------|-------------|
| `admin` | Full control, destructive actions allowed |
| `operator` | Start/stop cycles, manage runs, view most status |
| `viewer` | Read-only status and reports |

Endpoints MUST declare their required role/scope in code (decorators or routing config).

There is no "admin by default" mode. Privileged roles MUST be granted via IdP (Keycloak) role configuration, even in local development.

## 6.5 Configuration Schema

Auth config MUST be declared as a Pydantic section within `AppConfig`, loaded by the existing profile loader (SIP-0051):

```python
# Addition to src/squadops/config/schema.py
class OIDCConfig(BaseModel):
    issuer_url: str
    audience: str | list[str]  # Single string or list; see TokenClaims.audience
    jwks_url: str | None = None  # Derived from issuer if not set
    roles_claim_path: str = "realm_access.roles"  # Configurable for client role mode
    jwks_cache_ttl_seconds: int = 3600  # JWKS key cache TTL (see 6.9)
    jwks_forced_refresh_min_interval_seconds: int = 30  # Stampede protection (see 6.9)
    clock_skew_seconds: int = 60  # Tolerance for exp/iat/nbf validation

class ConsoleAuthConfig(BaseModel):
    client_id: str
    redirect_uri: str
    post_logout_redirect_uri: str | None = None

class ServiceClientConfig(BaseModel):
    client_id: str
    client_secret: str  # Supports secret:// references

class AuthConfig(BaseModel):
    enabled: bool = True
    provider: str = "keycloak"  # Supported: "keycloak" | "disabled"
    oidc: OIDCConfig | None = None  # Required when provider != "disabled"
    console: ConsoleAuthConfig | None = None  # Required when provider != "disabled"
    service_clients: dict[str, ServiceClientConfig] = Field(default_factory=dict)
    roles_mode: str = "realm"  # "realm" | "client"
    roles_client_id: str | None = None  # Required when roles_mode="client"
```

**Role claim mapping by `roles_mode`:**

| `roles_mode` | `roles_claim_path` default | JWT claim structure |
|--------------|---------------------------|---------------------|
| `realm` | `realm_access.roles` | `{"realm_access": {"roles": ["admin", "operator"]}}` |
| `client` | `resource_access.<roles_client_id>.roles` | `{"resource_access": {"squadops-runtime": {"roles": ["admin"]}}}` |

When `roles_mode = "client"`, `KeycloakAuthzAdapter` MUST extract roles from `resource_access.{roles_client_id}.roles`. The `roles_client_id` is an **explicit config key** — it MUST NOT be inferred from `oidc.audience`, because audience and client ID are often not equivalent in real Keycloak setups (e.g., audience may be a resource server identifier while roles live under a different client). Pydantic validation MUST reject `roles_mode = "client"` when `roles_client_id` is not set. Operators MAY override `roles_claim_path` directly for non-standard claim layouts.

**Provider values:**
- `"keycloak"` — Default for all environments (dev, staging, prod). Full OIDC validation.
- `"disabled"` — Explicitly disables auth. Protected endpoints MUST return **503 Service Unavailable** (auth subsystem is not configured, not a user permission outcome). **Does not silently allow access.**

**HTTP status code semantics (normative):**

| Code | Meaning | When |
|------|---------|------|
| 401 Unauthorized | Missing or invalid token | `auth.provider` is active; token absent, expired, or malformed |
| 403 Forbidden | Authenticated but not authorized | Token valid, but identity lacks required role/scope |
| 503 Service Unavailable | Auth subsystem not configured | `auth.provider = "disabled"`; protected endpoint is unreachable by design |

Future provider values (`"cognito"`, `"entra"`, `"google"`) require only a new adapter — see Section 12.

**Auth provider defaults by environment:**

| Environment | `auth.provider` | Notes |
|-------------|-----------------|-------|
| `dev` | `keycloak` | Local Keycloak via Docker Compose bootstrap |
| `staging` | `keycloak` | Deployed Keycloak instance |
| `prod` | `keycloak` | Production Keycloak (or future provider via adapter) |
| `test` | `keycloak` | Integration tests use Keycloak; unit tests use `TestStubAuthAdapter` (see 6.7) |

Environment variable mapping: `SQUADOPS__AUTH__OIDC__ISSUER_URL`, etc.

## 6.6 Factory Function

```python
# adapters/auth/factory.py
def create_auth_provider(
    provider: str = "keycloak",
    secret_manager: SecretManager | None = None,
    **config,
) -> AuthPort:
    """Factory for AuthPort adapters.

    Resolves secret:// references before constructing the adapter.

    Raises:
        ValueError: If provider is unknown or "disabled" (caller must
            handle disabled mode before reaching the factory).
    """
    if provider == "keycloak":
        return KeycloakAuthAdapter(**config)
    raise ValueError(f"Unknown auth provider: {provider}")
```

When `auth.provider = "disabled"`, the application startup code MUST NOT call the factory. Instead, it MUST wire protected endpoints to return 503 Service Unavailable. App startup validates `auth.provider` and wires the route registry accordingly before the DI container is built and before middleware attaches.

## 6.7 Test-Only Stub Strategy

The runtime MUST NOT support any authentication provider that grants privileges without credential validation in non-test environments.

For unit tests that need to exercise auth-dependent code paths without standing up Keycloak, a **test-only stub** MAY be provided:

```python
# tests/_stubs/auth.py
class TestStubAuthAdapter(AuthPort):
    """Test-only stub. NOT a runtime provider.

    MUST only be used in test fixtures. MUST NOT be selectable
    via AuthConfig or the factory function.

    Tests supply identity explicitly via constructor or per-call override,
    keeping auth behavior visible in test assertions.
    """

    def __init__(self, default_identity: Identity | None = None):
        self._default_identity = default_identity

    async def validate_token(self, token: str) -> TokenClaims:
        """Returns claims derived from token string for test control."""
        ...

    async def resolve_identity(self, claims: TokenClaims) -> Identity:
        """Returns the explicitly configured test identity."""
        ...

    async def close(self) -> None:
        pass
```

**Enforcement:** `TestStubAuthAdapter` lives in `tests/_stubs/`, not in `adapters/`. It is not importable from production code paths. The factory function does not reference it.

**CI/QA enforcement:** A CI check (grep denylist or linter rule) MUST verify that `adapters/auth/` does not contain any file matching `noop_auth`, `NoOpAuthAdapter`, or similar pass-through provider names. This enforces the Runtime Provider Rule (Section 5.1) and prevents accidental introduction of a runtime stub.

## 6.8 OIDC Flows

### Console (Human Users)
- MUST use Authorization Code + PKCE.
- MUST store tokens securely (browser memory; avoid `localStorage` if possible).
- MUST refresh tokens directly with the IdP (Keycloak). The Console frontend owns the entire refresh lifecycle.
- Runtime API MUST NOT accept refresh tokens and MUST NOT provide a `/token/refresh` proxy endpoint in v0.9.1. If a proxy is needed later, it will be introduced via a separate SIP.

### Service-to-Service
- MUST use Client Credentials.
- MUST be configured as confidential clients with secrets provided via `secret://` references.

## 6.9 JWKS Caching and Key Rotation (Normative)

The `KeycloakAuthAdapter` MUST implement the following JWKS management strategy, governed by config keys in `OIDCConfig` (Section 6.5):

1. **Caching:** JWKS keys MUST be cached with TTL governed by `jwks_cache_ttl_seconds` (default: 3600).
2. **Rotation handling:** On JWT signature verification failure, the adapter MUST force a single JWKS refresh and retry verification once. This handles key rotation without requiring manual intervention.
3. **Stampede protection:** Forced JWKS refresh MUST be rate-limited per `jwks_forced_refresh_min_interval_seconds` (default: 30) to prevent thundering-herd scenarios during mass token validation with a rotated key.
4. **Clock skew:** Token expiry/issued-at/not-before validation MUST apply `clock_skew_seconds` (default: 60) tolerance.
5. **Startup:** The adapter MUST fetch JWKS on initialization (`__init__` or first `validate_token()` call) and fail fast if the JWKS endpoint is unreachable.

## 6.10 Secrets Management (Normative)

- Client secrets and admin bootstrap credentials MUST be supplied via `secret://` scheme (SIP-0052).
- No secrets in committed config.
- Token contents MUST NOT be logged (claims may be logged only if redacted).

---

# 7. Must Not (Normative)

1. No unauthenticated access to protected Runtime API endpoints beyond explicit allowlist (e.g., `/health`).
2. No storing bearer tokens in plaintext persistent storage without explicit decision.
3. No "admin by default" mode in any environment. Privileged roles MUST be granted via IdP role configuration.
4. No reliance on network-private posture alone for authorization.
5. No hard-coded realm/client secrets in repo or compose files.
6. `src/squadops/auth/` and `src/squadops/ports/auth/` MUST NOT import from `adapters/`.
7. No runtime authentication provider that grants privileges without credential validation. Test stubs are restricted to `tests/` and MUST NOT be selectable via `AuthConfig` or the factory.
8. When auth is disabled (`auth.provider = "disabled"`), protected endpoints MUST return 503 Service Unavailable — they MUST NOT silently allow access or return 401/403 (which imply an active auth subsystem).

---

# 8. Implementation Strategy (Phased)

## Phase 1: Ports, Models, and Config
- Define `AuthPort` and `AuthorizationPort` in `src/squadops/ports/auth/`
- Define domain models in `src/squadops/auth/models.py`
- Add `AuthConfig` to `AppConfig` schema (with `"keycloak"` and `"disabled"` as provider options)
- Add factory function in `adapters/auth/factory.py`
- Create `TestStubAuthAdapter` in `tests/_stubs/auth.py`
- Register `auth` pytest marker in `pytest.ini`

## Phase 2: Keycloak Adapter and JWT Middleware
- Implement `KeycloakAuthAdapter` with JWKS caching, rotation handling, and stampede protection
- Implement `KeycloakAuthzAdapter` (role extraction from configurable claim path)
- Add FastAPI middleware with correct ordering (after request-ID, before exception mapping)
- Add endpoint authorization decorators using `AuthorizationPort.check_access()`
- Keycloak Docker Compose bootstrap profile with pre-configured realm

## Phase 3a: Console OIDC Login
- Integrate Console OIDC login (Auth Code + PKCE)
- Implement login/logout flows
- Console-owned token refresh (directly with IdP, no Runtime proxy)
- Add role-aware UI gating (hide admin actions unless role allows)

*Phase 3a is independently shippable.*

## Phase 3b: Service Identities and Audit
- Add client-credentials support for internal services
- Add service client config and secret resolution
- Add audit logging for service actions (who/what/when)

*Phase 3b is independently shippable.*

---

# 9. Bootstrap and Local Development

## 9.1 Official Local Dev Path

Local development MUST use the Keycloak Docker Compose bootstrap profile. There is no "NoOp" or "skip auth" mode for local development — developers exercise real OIDC flows from day one.

## 9.2 Dev Quickstart

```bash
# 1. Start Keycloak (alongside other infra services)
docker-compose --profile auth up -d keycloak

# 2. Import the SquadOps realm (pre-configured clients + roles)
#    Realm export JSON lives in infra/auth/squadops-realm.json
docker-compose exec keycloak /opt/keycloak/bin/kc.sh import --file /opt/keycloak/data/import/squadops-realm.json

# 3. Create dev user(s)
#    Admin user credentials via secret:// references in config/profiles/dev.yaml
#    Additional viewer user can be created via Keycloak Admin UI at http://localhost:8180

# 4. Start Runtime API + Console against local issuer
#    config/profiles/dev.yaml sets:
#      auth.provider: keycloak
#      auth.oidc.issuer_url: http://localhost:8180/realms/squadops
docker-compose up -d runtime-api
```

## 9.3 Realm Bootstrap Contents

The pre-configured realm (`infra/auth/squadops-realm.json`) MUST include:
- Realm: `squadops`
- Client: `squadops-console` (public, PKCE-enabled)
- Client: `squadops-runtime` (confidential, for service-to-service)
- Roles: `admin`, `operator`, `viewer`
- One bootstrap admin user (password set via environment variable, sourced from `secret://`)

## 9.4 Unit Test Path

Unit tests do NOT require Keycloak. Tests use `TestStubAuthAdapter` (from `tests/_stubs/auth.py`) injected via test fixtures. The stub requires explicit identity configuration — it does not grant default privileges.

---

# 10. Testing Requirements

## 10.1 Pytest Marker Registration

The repository MUST register the following markers in `pytest.ini` (strict-markers compatible):
- `auth` — tests that exercise authentication/authorization logic
- `integration` — tests that require external services (Keycloak, etc.)

## 10.2 Unit Tests
- JWT validation with good/bad tokens (issuer/aud/exp) — mock `AuthPort`
- Role enforcement per endpoint — mock `AuthorizationPort`
- Config validation for auth keys (valid and invalid `AuthConfig`)
- Redaction of auth config/log fields
- `TestStubAuthAdapter` requires explicit identity (no default admin)
- Domain model immutability (`TokenClaims`, `Identity`, `AuthContext` are frozen)
- `auth.provider = "disabled"` results in 503 for protected endpoints
- JWKS cache TTL and forced-refresh behavior (mocked HTTP)
- Middleware ordering: auth failures include request-ID in response

## 10.3 Integration Tests
- Spin up Keycloak in Docker Compose
- Console obtains token and calls Runtime API
- Service client obtains token via client credentials and calls a protected endpoint
- Negative tests: invalid token rejected, insufficient role rejected
- JWKS rotation: rotate key in Keycloak, verify adapter recovers via forced refresh

Test markers: `@pytest.mark.auth`, `@pytest.mark.integration`

---

# 11. Definition of Done

- [ ] `AuthPort` and `AuthorizationPort` defined in `src/squadops/ports/auth/`
- [ ] Domain models (`TokenClaims`, `Identity`, `AuthContext`, `Role`, `Scope`) in `src/squadops/auth/models.py`
- [ ] `AuthConfig` section in `AppConfig` with `"keycloak"` and `"disabled"` providers
- [ ] `KeycloakAuthAdapter` validates JWTs with JWKS caching and rotation handling
- [ ] Factory function routes based on `auth.provider` config key (no NoOp/stub provider)
- [ ] `TestStubAuthAdapter` in `tests/_stubs/auth.py` (not importable from production code)
- [ ] FastAPI middleware ordered: request-ID → auth → exception mapping
- [ ] `auth.provider = "disabled"` returns 503 for protected endpoints (not silent allow)
- [ ] Console can login via OIDC (PKCE) and call protected Runtime API endpoints
- [ ] Console owns token refresh directly with IdP (no Runtime proxy)
- [ ] Service-to-service auth via client credentials works for at least one internal client
- [ ] All secrets sourced via `secret://` references (SIP-0052)
- [ ] Core purity: zero imports from `adapters/` in `src/squadops/`
- [ ] Keycloak Docker Compose bootstrap profile with realm export
- [ ] `auth` and `integration` markers registered in `pytest.ini`
- [ ] CI denylist check: no `NoOpAuthAdapter` or pass-through provider in `adapters/auth/`
- [ ] Tests: unit + integration cover happy and failure paths

---

# 12. Portability (Informative)

This boundary is portable because it relies on OIDC/OAuth2 standards and is expressed as abstract ports.

Future `auth.provider` values:
- `cognito` — AWS Cognito adapter
- `entra` — Azure Entra ID adapter
- `google` — Google Identity Platform adapter

Each requires only a new adapter in `adapters/auth/<provider>/` implementing `AuthPort` and `AuthorizationPort`. No changes to domain models, middleware, or core logic. The `roles_claim_path` config key supports provider-specific claim structures without code changes.

---

# 13. References

- **SIP-0051** — Config Profiles and Validation
- **SIP-0052** — Secrets Management (`secret://` scheme)
- **SIP-0053** — Repository Reorganization for DDD and Hexagonal Isolation
- **SIP-0054** — Hexagonal Secrets Isolation (reference pattern for this SIP)
- **SIP-0061** — LangFuse Integration Foundation (port/adapter template)
