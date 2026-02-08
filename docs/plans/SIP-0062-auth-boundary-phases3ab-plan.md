# SIP-0062 Phases 3a & 3b — Implementation Plan

## Context

Phases 1 and 2 of SIP-0062 are complete (85 auth tests, 629 regression tests passing). They established the auth boundary: `AuthPort`, `AuthorizationPort`, Keycloak adapter with JWKS caching, JWT middleware on the Runtime API, and Docker bootstrap.

Phases 3a and 3b complete the remaining SIP-0062 DoD items:
- **Phase 3a**: Console OIDC — backend plumbing for a future control plane console + minimal JS proof-of-concept in the health dashboard + securing `/console/*` routes
- **Phase 3b**: Service identities — client credentials token acquisition, `secret://` resolution, and structured audit logging

The user intends to build a separate control plane app that will consume the backend auth APIs. The health dashboard PoC is throwaway (will be reimplemented). The backend plumbing (CORS, `/auth/userinfo`, route-level auth, audit) persists.

---

## Phase 3a: Console OIDC Foundation

### 3a.1 CORS Middleware on Runtime API

**File: `src/squadops/api/runtime/main.py` (MODIFY)**

Add `CORSMiddleware` so browser-based clients (health dashboard PoC, future control plane) can call the Runtime API on port 8001.

**Origin derivation**: Add a `_extract_origin(uri: str) -> str` helper that parses a URI and returns `scheme://host:port` only (e.g., `http://localhost:8000/health` → `http://localhost:8000`). Apply to both `ConsoleAuthConfig.redirect_uri` and `post_logout_redirect_uri` to build the allowed origins set. Never pass a full path as a CORS origin.

**Middleware invariants** (must be satisfied regardless of add-order):
1. `X-Request-ID` MUST be present on all responses including 401/403
2. `OPTIONS` preflight MUST never trigger auth (returns 200/204 with CORS headers)
3. `/auth/userinfo` MUST return correct CORS headers for allowed origins

### 3a.2 Shared Auth Helper (DRY token validation)

**File: `src/squadops/api/middleware/auth.py` (MODIFY)**

Extract shared logic into a helper used by BOTH `AuthMiddleware.dispatch()` and `require_auth()`:

```python
async def validate_and_resolve_identity(
    token: str, auth_port: AuthPort
) -> Identity:
    """Validate token and resolve identity. Used by middleware AND dependency.

    Raises:
        TokenValidationError / IdentityResolutionError on failure.
    """
    claims = await auth_port.validate_token(token)
    return await auth_port.resolve_identity(claims)
```

Both `AuthMiddleware.dispatch()` and `require_auth()` call this helper, ensuring identical error semantics (401 for invalid token, 503 for missing auth port). No drift between code paths.

### 3a.3 `/auth/userinfo` Endpoint

**File: `src/squadops/api/routes/auth.py` (NEW)**

Protected endpoint returning the current identity from `request.state.identity`:

```python
router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/userinfo")
async def userinfo(request: Request):
    identity = getattr(request.state, "identity", None)
    if not identity:
        raise HTTPException(401, "Not authenticated")
    return {
        "user_id": identity.user_id,
        "display_name": identity.display_name,
        "roles": list(identity.roles),
        "scopes": list(identity.scopes),
        "identity_type": identity.identity_type,
    }
```

**File: `src/squadops/api/runtime/main.py` (MODIFY)** — Include the auth router.

### 3a.4 Route-Level Auth on `/console/*` (Health App)

**Design decision**: Use a reusable `require_auth()` FastAPI dependency rather than full middleware on the health app. The health app serves unauthenticated infrastructure endpoints (`/health`, `/health/infra`, agent heartbeats) that must remain open. Route-level auth gives fine-grained control.

**File: `src/squadops/api/middleware/auth.py` (MODIFY)**

Add `require_auth()` factory that returns a FastAPI `Depends()` function. Uses `validate_and_resolve_identity()` from 3a.2:

```python
def require_auth(auth_port_getter=None):
    """Factory for a FastAPI dependency that validates Bearer token and returns Identity."""
    async def dependency(request: Request) -> Identity:
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Missing or invalid Authorization header")
        token = auth_header[7:]
        if auth_port_getter:
            auth_port = auth_port_getter()
        else:
            from squadops.api.runtime.deps import get_auth_port
            auth_port = get_auth_port()
        if auth_port is None:
            raise HTTPException(503, "Authentication service unavailable")
        try:
            identity = await validate_and_resolve_identity(token, auth_port)
            request.state.identity = identity
            return identity
        except Exception:
            raise HTTPException(401, "Invalid or expired token")
    return dependency
```

**File: `src/squadops/api/health_deps.py` (NEW)**

Auth port globals for the health app (same pattern as `runtime/deps.py`):
- `set_health_auth_ports(auth, authz)`, `get_health_auth_port()`, `get_health_authz_port()`

**File: `src/squadops/api/routes/console.py` (MODIFY)**

Add auth dependency. `init_routes()` gains `auth_dependency` param. When provided, console routes use `Depends(auth_dependency)`.

**Disabled-provider semantics for `/console/*`**: When `auth.provider == "disabled"`, the health app startup MUST still pass an auth dependency that raises 503 (not leave routes open). `/console/*` is a protected surface — `provider="disabled"` means the surface is unreachable, not unprotected. Concretely:

```python
# In health_app.py startup:
if auth_config.provider == "disabled":
    # Protected endpoints return 503 when auth is disabled
    async def _disabled_dependency(request: Request):
        raise HTTPException(503, "Authentication service unavailable")
    auth_dep = _disabled_dependency
elif auth_config.enabled and auth_config.provider != "disabled":
    # Normal: validate tokens
    auth_dep = require_auth(get_health_auth_port)
else:
    # auth.enabled=False: no auth dependency (test/scratch only)
    auth_dep = None
```

**File: `src/squadops/api/health_app.py` (MODIFY)**

In `startup_event()`: initialize auth adapters via factory (same as runtime API), set health auth ports, create dependency per above logic, pass to `console_routes.init_routes()`.

### 3a.5 Keycloak Realm Update

**File: `infra/auth/squadops-realm.json` (MODIFY)**

Add `http://localhost:8000/*` to `squadops-console` client `redirectUris` and `http://localhost:8000` to `webOrigins` (for the health dashboard PoC).

**Realm import is single source**: `--import-realm` in compose is authoritative. Manual `kc.sh import` is troubleshooting-only.

### 3a.6 OIDC JavaScript Proof-of-Concept

**File: `src/squadops/api/templates/health_dashboard.html` (MODIFY)**

Add an "Auth" tab alongside Dashboard, WarmBoot, Agent Console. The tab contains:
- Login/Logout buttons
- Token status display (logged in as, roles, expiry)
- "Test API Call" button demonstrating an authenticated fetch to `/auth/userinfo` on port 8001

Inline vanilla JS (~140 lines) implementing:
- **PKCE flow**: generate `code_verifier` (random 43-128 chars), compute `code_challenge` (SHA-256 base64url), redirect to Keycloak `/authorize`
- **state parameter**: random value stored in `sessionStorage`, verified on callback (CSRF protection)
- **nonce parameter**: random value included in auth request, verified against `id_token` `nonce` claim if decoded (replay protection)
- **Callback**: on page load, check for `code` + verify `state` match, exchange for tokens via Keycloak `/token` endpoint
- **Token storage**: in JS memory variables (not localStorage, per SIP Section 6.8)
- **Token refresh**: call Keycloak `/token` with `grant_type=refresh_token` when access token is within `REFRESH_MARGIN_SECONDS = 30` of expiry. **On refresh failure: clear all tokens and force re-login** (no retry loop).
- **Logout**: redirect to Keycloak `/logout`
- `redirect_uri` = `http://localhost:8000/health` (the dashboard URL itself)

OIDC config injected via Jinja2 context variables from `ConsoleAuthConfig` + `OIDCConfig`.

**File: `src/squadops/api/routes/health.py` (MODIFY)**

Pass OIDC config to template context:

```python
oidc_context = {}
if config.auth.enabled and config.auth.console and config.auth.oidc:
    oidc_context = {
        "oidc_issuer": config.auth.oidc.issuer_url,
        "oidc_client_id": config.auth.console.client_id,
        "oidc_redirect_uri": config.auth.console.redirect_uri,
        "runtime_api_url": config.runtime_api_url,
    }
```

### 3a.7 Docker Compose Env Vars

**File: `docker-compose.yml` (MODIFY)**

Add to health-check and runtime-api services:
```yaml
SQUADOPS__AUTH__CONSOLE__CLIENT_ID: squadops-console
SQUADOPS__AUTH__CONSOLE__REDIRECT_URI: http://localhost:8000/health
SQUADOPS__AUTH__CONSOLE__POST_LOGOUT_REDIRECT_URI: http://localhost:8000/health
```

### 3a.8 Phase 3a Tests

| Test File | Tests |
|-----------|-------|
| `tests/unit/auth/test_validate_helper.py` (NEW) | `validate_and_resolve_identity()`: valid token → Identity; invalid → raises; shared by middleware + dependency |
| `tests/unit/auth/test_require_auth.py` (NEW) | Valid token → Identity; missing header → 401; invalid token → 401; auth port None → 503; custom auth_port_getter |
| `tests/unit/auth/test_auth_routes.py` (NEW) | `/auth/userinfo` returns identity when authenticated; 401 when not; correct fields for human vs service |
| `tests/unit/auth/test_console_auth.py` (NEW) | `/console/command` requires Bearer when auth enabled; 401 without token; **503 when provider=disabled**; routes open only when auth.enabled=False |
| `tests/unit/auth/test_cors.py` (NEW) | Preflight from console origin → correct headers + no auth triggered (200/204); unknown origin → no CORS headers; `/auth/userinfo` includes CORS headers |
| `tests/unit/auth/test_middleware_invariants.py` (NEW) | Request-ID present on 401/403 responses; OPTIONS preflight never triggers auth; middleware ordering invariants |

---

## Phase 3b: Service Identities & Audit

### 3b.1 ServiceTokenClient (Client Credentials Flow)

**File: `src/squadops/auth/client_credentials.py` (NEW)**

Domain-level code (no adapter imports). `ServiceTokenClient` acquires tokens via OAuth2 `grant_type=client_credentials`:

```python
@dataclass(frozen=True)
class ServiceToken:
    access_token: str
    expires_at: float  # time.monotonic() base + expires_in (avoids wall-clock jumps)
    token_type: str = "Bearer"

class ServiceTokenClient:
    def __init__(self, token_endpoint: str, client_id: str, client_secret: str,
                 *, refresh_margin_seconds: int = 30):
        ...
        self._lock = asyncio.Lock()  # Prevent concurrent refresh stampede

    async def get_token(self) -> str:
        """Return cached token, refreshing if near expiry.

        Guarded by asyncio.Lock so concurrent callers don't
        simultaneously trigger token fetches.
        """
        async with self._lock:
            if self._cached and time.monotonic() < (self._cached.expires_at - self._refresh_margin):
                return self._cached.access_token
            token = await self._fetch_token()
            self._cached = token
            return token.access_token

    async def _fetch_token(self) -> ServiceToken:
        """POST to token endpoint with client_credentials grant.

        expires_at = time.monotonic() + expires_in (monotonic base avoids time-jump issues).
        """
    async def close(self) -> None:
        """Release httpx client."""
```

Uses `httpx.AsyncClient`. `asyncio.Lock` prevents concurrent refresh stampede when multiple coroutines call `get_token()` simultaneously.

### 3b.2 Factory Secret Resolution

**File: `adapters/auth/factory.py` (MODIFY)**

- Add `secret_manager: SecretManager | None = None` param to `create_auth_provider()` (matches SIP Section 6.6 signature)
- Add `create_service_token_client(service_name, service_config, oidc_config, secret_manager)` factory:
  - Resolves `secret://` references in `ServiceClientConfig.client_secret` via `SecretManager.resolve()`
  - Derives `token_endpoint` from `OIDCConfig.issuer_url`
  - Returns `ServiceTokenClient`

**File: `src/squadops/api/runtime/main.py` (MODIFY)**

In `startup_event()`, after auth adapter init, create service token clients for configured `auth.service_clients`.

### 3b.3 AuditEvent Model

**File: `src/squadops/auth/models.py` (MODIFY)**

Add `AuditEvent` frozen dataclass alongside existing auth models:

```python
@dataclass(frozen=True)
class AuditEvent:
    """Structured security audit event (SIP-0062)."""
    event_id: str           # UUID4
    timestamp: datetime     # MUST be timezone-aware UTC: datetime.now(timezone.utc)
    action: str             # e.g. "auth.token_validated", "auth.token_rejected"
    actor_id: str           # Identity.user_id or "anonymous" (consistent sentinel)
    actor_type: str         # "human" | "service" | "unknown"
    resource_type: str      # e.g. "api"
    resource_id: str | None = None  # e.g. request path
    result: str = "success" # "success" | "denied" | "error"
    denial_reason: str | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    request_id: str | None = None  # ALWAYS populate from X-Request-ID when available
    ip_address: str | None = None
```

**Timestamp convention**: All `AuditEvent.timestamp` values MUST use `datetime.now(timezone.utc)`, never naive `datetime.utcnow()`. The logging adapter serializes via `.isoformat()` which preserves the `+00:00` suffix.

**Actor convention**: Unauthenticated requests use `actor_id="anonymous"`, `actor_type="unknown"`. `request_id` is always populated when `X-Request-ID` is available.

### 3b.4 AuditPort Interface

**File: `src/squadops/ports/audit.py` (NEW)**

Flat port (not nested under auth — audit could expand beyond auth later):

```python
class AuditPort(ABC):
    @abstractmethod
    def record(self, event: AuditEvent) -> None:
        """Record audit event. MUST NOT raise — swallow errors internally."""
    @abstractmethod
    def close(self) -> None: ...
```

**File: `src/squadops/ports/__init__.py` (MODIFY)** — Export `AuditPort`.

### 3b.5 Logging Audit Adapter

**File: `adapters/audit/__init__.py` (NEW)**
**File: `adapters/audit/logging_adapter.py` (NEW)**

Emits audit events as structured JSON log entries via `logging.getLogger("squadops.audit")`. Serializes `timestamp` via `.isoformat()`. No database. Logs go to stdout for collection by any aggregation system.

**File: `adapters/audit/factory.py` (NEW)**

`create_audit_provider(provider="logging") -> AuditPort`

### 3b.6 Wire Audit into Middleware (No Double-Emits)

**File: `src/squadops/api/middleware/auth.py` (MODIFY)**

`AuthMiddleware.__init__()` gains optional `audit_port` param. Emits:
- `auth.token_validated` on successful authentication (includes actor_id, path, request_id, IP)
- `auth.token_rejected` on auth failure (includes path, request_id, IP, denial reason)

**No double-emit rule**: Audit events are emitted ONLY in `AuthMiddleware`. The `require_auth()` dependency does NOT emit audit events — it reuses `validate_and_resolve_identity()` but leaves auditing to the middleware layer. For health app routes using `require_auth()` without middleware, audit is deferred (the health app may add its own audit later if needed). This prevents one request producing two audit entries.

**File: `src/squadops/api/runtime/main.py` (MODIFY)**

Initialize `LoggingAuditAdapter` at startup, pass to `AuthMiddleware`.

### 3b.7 CI Denylist Check

**File: `scripts/dev/check_no_noop_auth.sh` (NEW)**

Simple grep: fail if `NoOpAuth`, `noop_auth`, `NoopAuth` found in `adapters/auth/`. Addresses SIP DoD item.

### 3b.8 Phase 3b Tests

| Test File | Tests |
|-----------|-------|
| `tests/unit/auth/test_client_credentials.py` (NEW) | Token fetch (mocked HTTP); caching within TTL; refresh near expiry; **concurrent get_token() only fetches once (lock test)**; HTTP error handling; close() |
| `tests/unit/auth/test_secret_resolution.py` (NEW) | `create_service_token_client` resolves `secret://`; passes through literal secrets; missing secret raises |
| `tests/unit/auth/test_audit_model.py` (NEW) | AuditEvent frozen immutability; required fields; defaults for optionals; **timestamp must be timezone-aware** |
| `tests/unit/auth/test_audit_adapter.py` (NEW) | `record()` emits JSON to logger; JSON contains all fields; **timestamp serialized with timezone**; swallows internal errors; `close()` is no-op |
| `tests/unit/auth/test_audit_middleware.py` (NEW) | Success emits `auth.token_validated`; failure emits `auth.token_rejected`; events include request_id/IP; middleware works when `audit_port=None`; **exactly one audit event per request (no double-emit)** |

---

## Files Summary

### Phase 3a — New Files

| File | Purpose |
|------|---------|
| `src/squadops/api/routes/auth.py` | `/auth/userinfo` endpoint |
| `src/squadops/api/health_deps.py` | Auth port globals for health app |
| `tests/unit/auth/test_validate_helper.py` | Shared `validate_and_resolve_identity()` tests |
| `tests/unit/auth/test_require_auth.py` | `require_auth()` dependency tests |
| `tests/unit/auth/test_auth_routes.py` | `/auth/userinfo` endpoint tests |
| `tests/unit/auth/test_console_auth.py` | Console route auth tests (incl. 503 for disabled) |
| `tests/unit/auth/test_cors.py` | CORS middleware tests |
| `tests/unit/auth/test_middleware_invariants.py` | Ordering invariant tests |

### Phase 3a — Modified Files

| File | Change |
|------|--------|
| `src/squadops/api/runtime/main.py` | CORS middleware (with `_extract_origin()` helper), include auth router |
| `src/squadops/api/middleware/auth.py` | Extract `validate_and_resolve_identity()`, add `require_auth()` factory |
| `src/squadops/api/routes/console.py` | Optional auth dependency on routes |
| `src/squadops/api/routes/health.py` | Pass OIDC config to template context |
| `src/squadops/api/health_app.py` | Init auth adapters at startup, disabled-provider → 503 dependency, pass to console routes |
| `src/squadops/api/templates/health_dashboard.html` | Auth tab + inline OIDC JS PoC with state+nonce (~140 lines) |
| `infra/auth/squadops-realm.json` | Add `localhost:8000` to redirectUris/webOrigins |
| `docker-compose.yml` | Add `SQUADOPS__AUTH__CONSOLE__*` env vars |

### Phase 3b — New Files

| File | Purpose |
|------|---------|
| `src/squadops/auth/client_credentials.py` | `ServiceTokenClient` + `ServiceToken` (with asyncio.Lock) |
| `src/squadops/ports/audit.py` | `AuditPort` ABC |
| `adapters/audit/__init__.py` | Audit adapter package |
| `adapters/audit/logging_adapter.py` | `LoggingAuditAdapter` (JSON to stdout) |
| `adapters/audit/factory.py` | `create_audit_provider()` |
| `scripts/dev/check_no_noop_auth.sh` | CI denylist check |
| `tests/unit/auth/test_client_credentials.py` | ServiceTokenClient tests (incl. lock/stampede) |
| `tests/unit/auth/test_secret_resolution.py` | Factory secret resolution tests |
| `tests/unit/auth/test_audit_model.py` | AuditEvent model tests (incl. TZ-aware timestamp) |
| `tests/unit/auth/test_audit_adapter.py` | LoggingAuditAdapter tests |
| `tests/unit/auth/test_audit_middleware.py` | Audit middleware tests (incl. no-double-emit) |

### Phase 3b — Modified Files

| File | Change |
|------|--------|
| `src/squadops/auth/models.py` | Add `AuditEvent` frozen dataclass (TZ-aware timestamps) |
| `src/squadops/ports/__init__.py` | Export `AuditPort` |
| `adapters/auth/factory.py` | Add `secret_manager` param, add `create_service_token_client()` |
| `src/squadops/api/middleware/auth.py` | Add `audit_port` to `AuthMiddleware`, emit audit events (single point) |
| `src/squadops/api/runtime/main.py` | Init audit adapter, pass to middleware, init service clients |

---

## Implementation Order

1. **Phase 3a** (7 steps + tests)
2. Run `pytest tests/unit/auth/ -v` → ~115 tests passing
3. Run `./scripts/dev/run_new_arch_tests.sh -v` → regression green
4. **Phase 3b** (7 steps + tests)
5. Run `pytest tests/unit/auth/ -v` → ~140 tests passing
6. Run `./scripts/dev/run_new_arch_tests.sh -v` → regression green

## Verification

**After Phase 3a:**
- `pytest tests/unit/auth/ -v` — all pass
- Health dashboard shows Auth tab with Login button
- Login redirects to Keycloak, callback verifies `state`, exchanges code, token displayed
- "Test API Call" calls `/auth/userinfo` on port 8001 with Bearer → shows identity + CORS headers
- `/console/command` returns 401 without Bearer (when auth enabled)
- `/console/command` returns 503 when `provider=disabled`
- Regression suite green
- Quick smoke: `curl {issuer}/.well-known/openid-configuration` returns 200; `curl localhost:8001/auth/userinfo` returns 401; `curl -H "Authorization: Bearer <token>" localhost:8001/auth/userinfo` returns 200

**After Phase 3b:**
- `pytest tests/unit/auth/ -v` — all pass
- `ServiceTokenClient` test fetches token with mocked Keycloak, lock prevents concurrent fetches
- Audit events appear as structured JSON in logs on auth success/failure (exactly one per request)
- Audit timestamps include `+00:00` suffix
- `scripts/dev/check_no_noop_auth.sh` passes
- Regression suite green

**SIP-0062 DoD items addressed:**
- Console can login via OIDC (PKCE) — 3a.6
- Console owns token refresh directly with IdP — 3a.6 (JS handles refresh, fails → re-login)
- Service-to-service auth via client credentials — 3b.1 + 3b.2
- All secrets sourced via `secret://` — 3b.2
- CI denylist check — 3b.7
