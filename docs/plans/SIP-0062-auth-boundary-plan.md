# SIP-0062: OIDC Authentication & Authorization Boundary — Implementation Plan

## Context

SquadOps needs a coherent authentication and authorization boundary before 1.0. Currently all APIs (health-check on 8000, runtime-api on 8001) are completely unauthenticated. The existing `AuthConfig` in `src/squadops/config/schema.py` is a placeholder with only `enabled: bool = False`. No auth ports, adapters, middleware, domain models, or identity infrastructure exist.

SIP-0062 defines a hexagonal auth boundary: `AuthPort` for token validation, `AuthorizationPort` for RBAC, a Keycloak adapter as the reference implementation, JWT middleware for FastAPI, and domain models for identity/roles/scopes — all following the same port/adapter pattern used for LLMObservabilityPort (SIP-0061), SecretProvider, DbRuntime, etc.

This plan covers **Phase 1** (Ports, Models, Config, Factory, Test Stub) and **Phase 2** (Keycloak Adapter, JWT Middleware, Docker bootstrap). Phases 3a (Console OIDC) and 3b (Service Identities) are independently shippable and will be planned separately.

### Review Resolutions

The following items were identified during plan review and are resolved inline:

- **(A) Docker DNS:** Keycloak compose service name set to `squadops-keycloak` to match `container_name` and `issuer_url`. Docker DNS resolves by service name.
- **(B) auth.enabled default:** Follow the SIP strictly — `enabled: bool = True` in code. Update all test fixtures/profiles to set `enabled` explicitly where needed.
- **(C) Keycloak health check:** Use OIDC discovery endpoint (`{issuer_url}/.well-known/openid-configuration`) for health, plus set `KC_HEALTH_ENABLED=true` env var as fallback.
- **(D) 503 consistency:** Plan enforces 503 for `provider=disabled` everywhere. SIP-0062 will also get a cleanup pass to replace any remaining 403/501 references with 503.
- **(E) Docs endpoint allowlist:** `/health` and `/health/infra` always allowlisted. `/docs` and `/openapi.json` only allowlisted when `auth.expose_docs=true`. The dev profile sets `auth.expose_docs=true`; non-dev profiles set it `false`.
- **(F) Realm import:** Use `--import-realm` in compose only. Drop the manual `kc.sh import` step from docs (keep as optional troubleshooting note).
- **(G) Keycloak image pinning:** Pin to exact patch: `quay.io/keycloak/keycloak:24.0.5` for reproducibility.
- **(H) ConsoleAuthConfig deferral:** `AuthConfig.console` is `Optional` (not required) until Phase 3a. Pydantic validator only enforces `console` presence when Phase 3a is active. No stub values needed.

---

## Phase 1: Ports, Domain Models, Config, Factory, Test Stub

### 1.1 Domain Models — `src/squadops/auth/models.py` (NEW)

Create frozen dataclasses exactly as specified in SIP-0062 Section 6.3:
- `TokenClaims` — parsed JWT claims (subject, issuer, audience, expires_at, issued_at, roles, scopes, raw_claims)
- `Identity` — resolved domain identity (user_id, display_name, roles, scopes, identity_type)
- `AuthContext` — authorization check result (granted, identity, denial_reason)
- `Role` — canonical role constants (ADMIN, OPERATOR, VIEWER)
- `Scope` — canonical scope constants (CYCLES_READ/WRITE, AGENTS_READ/WRITE, TASKS_READ/WRITE, ADMIN_WRITE)
- Auth exceptions: `TokenValidationError`, `IdentityResolutionError`

Add `src/squadops/auth/__init__.py` re-exporting the models.

### 1.2 Port Interfaces — `src/squadops/ports/auth/` (NEW)

- `src/squadops/ports/auth/__init__.py` — re-export `AuthPort`, `AuthorizationPort`
- `src/squadops/ports/auth/authentication.py` — `AuthPort(ABC)` with:
  - `async validate_token(token: str) -> TokenClaims`
  - `async resolve_identity(claims: TokenClaims) -> Identity`
  - `async close() -> None`
- `src/squadops/ports/auth/authorization.py` — `AuthorizationPort(ABC)` with:
  - `check_access(identity: Identity, required_roles: list[str], required_scopes: list[str]) -> AuthContext`

Update `src/squadops/ports/__init__.py` to export `AuthPort`, `AuthorizationPort`.

### 1.3 Config Schema Update — `src/squadops/config/schema.py` (MODIFY)

Replace the placeholder `AuthConfig` with the full schema from SIP-0062 Section 6.5:
- `OIDCConfig` — issuer_url, audience, jwks_url, roles_claim_path, jwks_cache_ttl_seconds, etc.
- `ConsoleAuthConfig` — client_id, redirect_uri, post_logout_redirect_uri
- `ServiceClientConfig` — client_id, client_secret (supports `secret://`)
- `AuthConfig` — enabled, provider ("keycloak"|"disabled"), oidc, console, service_clients, roles_mode, roles_client_id
- Add Pydantic validator: reject `roles_mode="client"` when `roles_client_id` is not set

**Defaults (per SIP, Resolution B):** `enabled: bool = True`, `provider: str = "keycloak"`. Existing test fixtures and profiles that don't configure auth will need explicit `enabled=False` or valid OIDC config. This prevents silent misconfiguration.

**Console config deferral (Resolution H):** `AuthConfig.console: ConsoleAuthConfig | None = None` — optional until Phase 3a. No Pydantic validator enforces its presence. `AuthConfig.oidc: OIDCConfig | None = None` IS required when `enabled=True` and `provider != "disabled"` — add a `model_post_init` validator for this.

**Docs allowlist (Resolution E):** Add `auth.expose_docs: bool = False` to `AuthConfig`. `/docs` and `/openapi.json` are only allowlisted when `auth.expose_docs=true`. The dev profile sets `expose_docs=true`; non-dev profiles leave it `false`. Middleware checks this single flag — no separate profile detection.

### 1.4 Factory Functions — `adapters/auth/factory.py` (NEW)

- `adapters/auth/__init__.py`
- `adapters/auth/factory.py`:
  - `create_auth_provider(provider, secret_manager, **config) -> AuthPort`
  - `create_authorization_provider(provider, **config) -> AuthorizationPort`
  - Raises `ValueError` for unknown providers or `"disabled"` (caller handles disabled mode)

### 1.5 Test Stub — `tests/_stubs/auth.py` (NEW)

- `tests/_stubs/__init__.py`
- `tests/_stubs/auth.py`:
  - `TestStubAuthAdapter(AuthPort)` — requires explicit `default_identity` in constructor
  - `TestStubAuthzAdapter(AuthorizationPort)` — requires explicit grant/deny configuration
  - NOT registered in factory, NOT importable from production code

### 1.6 Pytest Marker Registration

Add `auth: Tests that exercise authentication/authorization logic` to `pytest.ini` markers section.

### 1.7 Phase 1 Tests — `tests/unit/auth/` (NEW)

- `tests/unit/auth/__init__.py`
- `tests/unit/auth/test_models.py`:
  - Frozen dataclass immutability (TokenClaims, Identity, AuthContext)
  - Role/Scope constant values
  - TokenClaims audience handling (single string vs tuple)
- `tests/unit/auth/test_config.py`:
  - Valid AuthConfig construction
  - Invalid: roles_mode="client" without roles_client_id
  - Provider validation ("keycloak", "disabled", unknown)
  - OIDCConfig defaults
- `tests/unit/auth/test_factory.py`:
  - Factory raises ValueError for "disabled"
  - Factory raises ValueError for unknown provider
  - Factory returns KeycloakAuthAdapter for "keycloak" (once Phase 2 is done; mock for now)
- `tests/unit/auth/test_stub.py`:
  - TestStubAuthAdapter requires explicit identity
  - TestStubAuthAdapter validate_token returns controllable claims
  - TestStubAuthzAdapter check_access uses configured rules

---

## Phase 2: Keycloak Adapter, JWT Middleware, Docker Bootstrap

### 2.1 Dependencies — `requirements.txt` (MODIFY)

Add:
```
# Auth (SIP-0062)
python-jose[cryptography]>=3.3.0
httpx>=0.27.0
```
- `python-jose` for JWT decode/verify with JWKS
- `httpx` for async HTTP to fetch JWKS (lighter than aiohttp for this use case; aiohttp also fine)

### 2.2 Keycloak Auth Adapter — `adapters/auth/keycloak/auth_adapter.py` (NEW)

- `adapters/auth/keycloak/__init__.py`
- `KeycloakAuthAdapter(AuthPort)`:
  - Constructor: takes `OIDCConfig` fields (issuer_url, audience, jwks_url, clock_skew_seconds, etc.)
  - `_jwks_cache`: in-memory JWKS key set with TTL (`jwks_cache_ttl_seconds`, default 3600)
  - `_last_forced_refresh`: timestamp for stampede protection (`jwks_forced_refresh_min_interval_seconds`, default 30)
  - `validate_token()`: decode JWT, verify signature against JWKS, check iss/aud/exp/iat with clock skew. On signature failure, force single JWKS refresh and retry once.
  - `resolve_identity()`: map claims to `Identity` domain model (extract `sub`, `preferred_username`/`name`, roles from configurable claim path)
  - `close()`: release HTTP client

### 2.3 Keycloak Authz Adapter — `adapters/auth/keycloak/authz_adapter.py` (NEW)

- `KeycloakAuthzAdapter(AuthorizationPort)`:
  - `check_access()`: evaluate `identity.roles` against `required_roles` and `identity.scopes` against `required_scopes`
  - Role extraction from configurable claim path:
    - `roles_mode="realm"` → `realm_access.roles`
    - `roles_mode="client"` → `resource_access.<roles_client_id>.roles`

### 2.4 JWT Auth Middleware — `src/squadops/api/middleware/auth.py` (NEW)

- `src/squadops/api/middleware/__init__.py`
- `AuthMiddleware(BaseHTTPMiddleware)`:
  - **Always allowlisted** (no token required): `/health`, `/health/infra`
  - **Conditionally allowlisted** (Resolution E): `/docs`, `/openapi.json` only when `auth.expose_docs=true`. The dev profile sets this to `true`; non-dev profiles set it `false`. When `expose_docs=false`, these endpoints return 401 without a valid token.
  - Extract `Authorization: Bearer <token>` header
  - Call `AuthPort.validate_token()` → `AuthPort.resolve_identity()`
  - Inject `Identity` into `request.state.identity`
  - Return 401 on missing/invalid token
  - When `auth.provider = "disabled"`: return 503 for protected endpoints (Resolution D — 503, never 403/501)
- `require_roles(*roles)` / `require_scopes(*scopes)` — FastAPI dependency functions:
  - Extract `request.state.identity`, call `AuthorizationPort.check_access()`
  - Return 403 if denied

### 2.5 Middleware Ordering in Runtime API — `src/squadops/api/runtime/main.py` (MODIFY)

Add middleware in correct order per SIP-0062 Section 5.4:
1. Request-ID middleware (add `X-Request-ID` header if missing; inject into logging context)
2. Auth middleware (token validation, identity injection)
3. Existing error handling remains as-is

Wire auth ports in `startup_event()`:
- Load `AuthConfig` from config
- If `auth.enabled` and `auth.provider != "disabled"`: create adapters via factory, attach middleware
- If `auth.provider == "disabled"`: attach middleware that returns 503 for protected routes
- Set auth adapter globals in `deps.py` for Depends() injection

### 2.6 Auth Dependencies — `src/squadops/api/runtime/deps.py` (MODIFY)

Add:
- `_auth_port: AuthPort | None = None`
- `_authz_port: AuthorizationPort | None = None`
- `set_auth_ports()` / `get_auth_port()` / `get_authz_port()` following existing pattern

### 2.7 Keycloak Docker Compose — `docker-compose.keycloak.yml` (NEW)

Separate compose file (same pattern as `docker-compose.langfuse.yml`):
```yaml
services:
  squadops-keycloak:                              # (A) Service name matches container_name for DNS
    image: quay.io/keycloak/keycloak:24.0.5       # (G) Pinned to exact patch
    container_name: squadops-keycloak
    command: start-dev --import-realm              # (F) Auto-import realm on startup
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin123            # Local dev only
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres:5432/keycloak
      KC_DB_USERNAME: keycloak
      KC_DB_PASSWORD: keycloak
      KC_HEALTH_ENABLED: "true"                    # (C) Enable health endpoints
    ports:
      - "8180:8080"
    volumes:
      - ./infra/auth/squadops-realm.json:/opt/keycloak/data/import/squadops-realm.json
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - squadnet
networks:
  squadnet:
    external: true
    name: squad-ops_squadnet
```

**Note (Resolution F):** Realm import happens automatically via `--import-realm`. No manual `kc.sh import` step needed. If the realm already exists, Keycloak skips re-import. For troubleshooting, operators can manually re-import via `docker compose exec squadops-keycloak /opt/keycloak/bin/kc.sh import --file /opt/keycloak/data/import/squadops-realm.json --override true`.

### 2.8 Keycloak Database Init — `infra/init.sql` (MODIFY)

Add `keycloak` database and user (same pattern as langfuse block):
```sql
CREATE USER keycloak WITH PASSWORD 'keycloak';
CREATE DATABASE keycloak OWNER keycloak;
```

### 2.9 Realm Export — `infra/auth/squadops-realm.json` (NEW)

Pre-configured Keycloak realm JSON containing:
- Realm: `squadops`
- Client: `squadops-console` (public, PKCE-enabled, redirect URIs for localhost)
- Client: `squadops-runtime` (confidential, for service-to-service)
- Realm roles: `admin`, `operator`, `viewer`
- Bootstrap admin user with `admin` role

### 2.10 Health Check — `src/squadops/api/health_app.py` (MODIFY)

Add `check_keycloak()` method (same pattern as `check_langfuse()`):
- **Primary check (Resolution C):** Hit OIDC discovery document `{issuer_url}/.well-known/openid-configuration` — validates the actual OIDC surface the runtime depends on
- **Fallback:** If discovery fails, try `/health/ready` (enabled via `KC_HEALTH_ENABLED=true`)
- Report status, version, and realm in health dashboard

### 2.11 Auth Env Vars for Runtime API — `docker-compose.yml` (MODIFY)

Add to `runtime-api` service:
```yaml
SQUADOPS__AUTH__ENABLED: "true"
SQUADOPS__AUTH__PROVIDER: keycloak
SQUADOPS__AUTH__OIDC__ISSUER_URL: http://squadops-keycloak:8080/realms/squadops  # (A) service name = squadops-keycloak
SQUADOPS__AUTH__OIDC__AUDIENCE: squadops-runtime
SQUADOPS__AUTH__EXPOSE_DOCS: "true"  # (E) Dev only — allow unauthenticated /docs
```

Also add `SQUADOPS__AUTH__OIDC__ISSUER_URL` to health-check service for the Keycloak health check (Resolution C).

### 2.12 Phase 2 Tests

- `tests/unit/auth/test_keycloak_adapter.py`:
  - JWKS fetch and caching (mocked HTTP)
  - Token validation: valid token, expired, wrong issuer, wrong audience, bad signature
  - Forced JWKS refresh on signature failure (rotation handling)
  - Stampede protection (forced refresh rate limiting)
  - Clock skew tolerance
  - Role extraction: realm mode vs client mode
- `tests/unit/auth/test_authz_adapter.py`:
  - check_access: identity has required role → granted
  - check_access: identity missing role → denied with reason
  - check_access: scope checking
- `tests/unit/auth/test_middleware.py`:
  - `/health` and `/health/infra` always pass without token
  - `/docs` passes without token only when `expose_docs=True`
  - `/docs` returns 401 when `expose_docs=False`
  - Missing Authorization header → 401
  - Invalid token → 401
  - Valid token → request.state.identity populated
  - auth.provider="disabled" → 503 for protected endpoints (not 401, not 403)
  - Auth failures include X-Request-ID
- `tests/unit/auth/test_require_roles.py`:
  - Decorator grants access for matching role
  - Decorator denies with 403 for missing role

---

## Files Summary

### New Files
| File | Purpose |
|------|---------|
| `src/squadops/auth/__init__.py` | Auth domain package |
| `src/squadops/auth/models.py` | Identity, TokenClaims, AuthContext, Role, Scope, exceptions |
| `src/squadops/ports/auth/__init__.py` | Auth port package |
| `src/squadops/ports/auth/authentication.py` | AuthPort ABC |
| `src/squadops/ports/auth/authorization.py` | AuthorizationPort ABC |
| `src/squadops/api/middleware/__init__.py` | Middleware package |
| `src/squadops/api/middleware/auth.py` | JWT auth middleware + role/scope decorators |
| `adapters/auth/__init__.py` | Auth adapter package |
| `adapters/auth/factory.py` | create_auth_provider(), create_authorization_provider() |
| `adapters/auth/keycloak/__init__.py` | Keycloak adapter package |
| `adapters/auth/keycloak/auth_adapter.py` | KeycloakAuthAdapter(AuthPort) |
| `adapters/auth/keycloak/authz_adapter.py` | KeycloakAuthzAdapter(AuthorizationPort) |
| `tests/_stubs/__init__.py` | Test stubs package |
| `tests/_stubs/auth.py` | TestStubAuthAdapter, TestStubAuthzAdapter |
| `tests/unit/auth/__init__.py` | Auth test package |
| `tests/unit/auth/test_models.py` | Domain model tests |
| `tests/unit/auth/test_config.py` | AuthConfig validation tests |
| `tests/unit/auth/test_factory.py` | Factory tests |
| `tests/unit/auth/test_stub.py` | Test stub tests |
| `tests/unit/auth/test_keycloak_adapter.py` | Keycloak adapter tests |
| `tests/unit/auth/test_authz_adapter.py` | Authz adapter tests |
| `tests/unit/auth/test_middleware.py` | Middleware tests |
| `tests/unit/auth/test_require_roles.py` | Role/scope decorator tests |
| `docker-compose.keycloak.yml` | Keycloak Docker Compose |
| `infra/auth/squadops-realm.json` | Keycloak realm export |

### Modified Files
| File | Change |
|------|--------|
| `src/squadops/config/schema.py` | Replace placeholder AuthConfig with full OIDCConfig/AuthConfig |
| `src/squadops/ports/__init__.py` | Export AuthPort, AuthorizationPort |
| `src/squadops/api/runtime/main.py` | Add auth middleware, request-ID middleware, startup wiring |
| `src/squadops/api/runtime/deps.py` | Add auth port globals and dependency functions |
| `src/squadops/api/health_app.py` | Add check_keycloak() |
| `src/squadops/api/routes/health.py` | Add keycloak to infra gather |
| `requirements.txt` | Add python-jose, httpx |
| `pytest.ini` | Add `auth` marker |
| `docker-compose.yml` | Add auth env vars to runtime-api |
| `infra/init.sql` | Add keycloak database/user |
| `sips/accepted/SIP-0062-Auth-Boundary-OIDC-Keycloak.md` | Fix 403/501 → 503 consistency (Resolution D) |

---

## Pre-Implementation: SIP-0062 Cleanup Pass (Resolution D)

Before coding begins, update `sips/accepted/SIP-0062-Auth-Boundary-OIDC-Keycloak.md` to replace any remaining "403/501" references for `provider=disabled` with "503 Service Unavailable" for consistency. This is an editorial fix to the spec, not a code change.

## Implementation Order

1. **SIP cleanup pass** — fix 503 consistency in SIP-0062 text
2. **Phase 1** — domain models, ports, config, factory, test stub, tests (~1 session)
3. **Phase 2** — Keycloak adapter, middleware, Docker bootstrap, integration tests (~1-2 sessions)
4. Run full regression suite (`run_new_arch_tests.sh`) after each phase
5. Version bump to 0.9.1 after Phase 2 is verified

## Verification

After Phase 1:
- `pytest tests/unit/auth/ -v` — all domain model, config, factory, stub tests pass
- `./scripts/dev/run_new_arch_tests.sh -v` — regression suite still green (no existing tests broken by config changes)

After Phase 2:
- `docker compose -f docker-compose.yml -f docker-compose.keycloak.yml up -d squadops-keycloak` — Keycloak starts and imports realm
- Keycloak admin UI at http://localhost:8180 — realm `squadops` visible with roles/clients
- `pytest tests/unit/auth/ -v` — all unit tests pass (adapter tests use mocked HTTP)
- Health dashboard shows Keycloak online
- Manual test: obtain token from Keycloak, call runtime-api with Bearer header → 200; call without token → 401
