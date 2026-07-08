"""
JWT Auth Middleware and authorization dependencies (SIP-0062).

Middleware ordering: Request-ID -> Auth -> Exception handling.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from squadops.auth.models import Identity
from squadops.ports.auth.authentication import AuthPort

logger = logging.getLogger(__name__)

# One-time warning latch: #150 — surface a missing audit port instead of silently
# dropping security audit events.
_audit_unavailable_warned = False

# Always allowlisted path prefixes (no token required). Read-only lane: the
# allowlist applies to safe methods (GET/HEAD) only, so a write route mounted
# under /health can never ride the no-auth lane (#326).
_ALWAYS_ALLOWLISTED_PREFIXES = ("/health",)
_ALLOWLISTED_METHODS = ("GET", "HEAD")

# Conditionally allowlisted paths (only when expose_docs=True)
_DOCS_PATHS = {"/docs", "/openapi.json", "/redoc"}


async def validate_and_resolve_identity(token: str, auth_port: AuthPort) -> Identity:
    """Validate token and resolve identity. Used by middleware AND require_auth().

    Raises:
        TokenValidationError / IdentityResolutionError on failure.
    """
    claims = await auth_port.validate_token(token)
    return await auth_port.resolve_identity(claims)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add X-Request-ID header if missing; inject into logging context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT token validation middleware (SIP-0062).

    - Always allows GET/HEAD under /health without a token (read-only probe
      lane); any other method under /health requires a token like every
      protected route (#326).
    - Conditionally allows /docs and /openapi.json when expose_docs=True.
    - When provider='disabled', returns 503 for protected endpoints.
    - Otherwise, validates Bearer token and injects Identity into request.state.
    """

    def __init__(
        self,
        app,
        auth_port: AuthPort | None = None,
        *,
        provider: str = "keycloak",
        expose_docs: bool = False,
        audit_port=None,
    ) -> None:
        super().__init__(app)
        self._auth_port = auth_port
        self._provider = provider
        self._expose_docs = expose_docs
        self._audit_port = audit_port

    def _emit_audit(
        self,
        request: Request,
        *,
        action: str,
        actor_id: str = "anonymous",
        actor_type: str = "unknown",
        result: str = "success",
        denial_reason: str | None = None,
    ) -> None:
        """Emit an audit event if audit_port is configured."""
        audit_port = self._audit_port
        if audit_port is None:
            try:
                from squadops.api.runtime.deps import get_audit_port

                audit_port = get_audit_port()
            except Exception:
                pass
        if audit_port is None:
            global _audit_unavailable_warned
            if not _audit_unavailable_warned:
                logger.warning(
                    "Audit port unavailable — security audit events (including token "
                    "rejections) are not being recorded (#150)."
                )
                _audit_unavailable_warned = True
            return
        try:
            from squadops.auth.models import AuditEvent

            request_id = getattr(request.state, "request_id", None)
            ip_address = request.client.host if request.client else None
            event = AuditEvent(
                action=action,
                actor_id=actor_id,
                actor_type=actor_type,
                resource_type="api",
                resource_id=request.url.path,
                result=result,
                denial_reason=denial_reason,
                request_id=request_id,
                ip_address=ip_address,
            )
            audit_port.record(event)
        except Exception:
            logger.debug("Failed to emit audit event", exc_info=True)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path.rstrip("/") or "/"
        request_id = getattr(request.state, "request_id", "unknown")

        # Always-allowlisted paths (prefix match, safe methods only — #326)
        if request.method in _ALLOWLISTED_METHODS and any(
            path.startswith(prefix) for prefix in _ALWAYS_ALLOWLISTED_PREFIXES
        ):
            return await call_next(request)

        # Conditionally allowlisted docs paths
        if path in _DOCS_PATHS and self._expose_docs:
            return await call_next(request)

        # OPTIONS preflight — never trigger auth
        if request.method == "OPTIONS":
            return await call_next(request)

        # Disabled provider → 503 for all protected endpoints
        if self._provider == "disabled":
            self._emit_audit(
                request,
                action="auth.token_rejected",
                result="error",
                denial_reason="provider_disabled",
            )
            return Response(
                content='{"detail":"Authentication service unavailable"}',
                status_code=503,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )

        # Extract Bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            self._emit_audit(
                request,
                action="auth.token_rejected",
                result="denied",
                denial_reason="missing_bearer_token",
            )
            return Response(
                content='{"detail":"Missing or invalid Authorization header"}',
                status_code=401,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )

        token = auth_header[7:]  # Strip "Bearer "

        # Resolve auth port: use injected port, or fall back to deps
        auth_port = self._auth_port
        if auth_port is None:
            from squadops.api.runtime.deps import get_auth_port

            auth_port = get_auth_port()

        if auth_port is None:
            self._emit_audit(
                request,
                action="auth.token_rejected",
                result="error",
                denial_reason="auth_service_unavailable",
            )
            return Response(
                content='{"detail":"Authentication service unavailable"}',
                status_code=503,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )

        try:
            identity = await validate_and_resolve_identity(token, auth_port)
            request.state.identity = identity
            self._emit_audit(
                request,
                action="auth.token_validated",
                actor_id=identity.user_id,
                actor_type=identity.identity_type,
            )
        except Exception as e:
            logger.warning("Token validation failed: %s", e)
            self._emit_audit(
                request,
                action="auth.token_rejected",
                result="denied",
                denial_reason=str(e),
            )
            return Response(
                content='{"detail":"Invalid or expired token"}',
                status_code=401,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )

        return await call_next(request)


def require_auth(auth_port_getter=None):
    """Factory for a FastAPI dependency that validates Bearer token and returns Identity.

    Does NOT emit audit events — auditing is the middleware's responsibility.
    """

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
            raise HTTPException(401, "Invalid or expired token") from None

    return dependency


async def _enforce_access(
    request: Request, *, roles: list[str], scopes: list[str]
) -> Identity | None:
    """Shared authorization check for :func:`require_roles` / :func:`require_scopes`.

    No-op when no authorization backend is configured — i.e. auth is disabled for
    this deployment (``AuthMiddleware`` is itself only attached when auth is
    enabled, so a protected route must not 401 in an auth-off deployment; this
    matches the pre-#150 behaviour of leaving routes open when auth is off).
    When authz IS configured: 401 without an identity, 403 without the required
    roles/scopes (#150).
    """
    # Import here to avoid circular imports at module level
    from squadops.api.runtime.deps import get_authz_port

    authz = get_authz_port()
    if authz is None:
        return getattr(request.state, "identity", None)

    identity: Identity | None = getattr(request.state, "identity", None)
    if identity is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    ctx = authz.check_access(identity, required_roles=roles, required_scopes=scopes)
    if not ctx.granted:
        raise HTTPException(status_code=403, detail=ctx.denial_reason or "Forbidden")
    return identity


def require_roles(*roles: str) -> Callable:
    """FastAPI dependency: identity has at least one of the required roles.

    No-op when auth is disabled (no authorization backend configured)."""

    async def dependency(request: Request) -> Identity | None:
        return await _enforce_access(request, roles=list(roles), scopes=[])

    return dependency


def require_scopes(*scopes: str) -> Callable:
    """FastAPI dependency: identity has all of the required scopes.

    No-op when auth is disabled (no authorization backend configured)."""

    async def dependency(request: Request) -> Identity | None:
        return await _enforce_access(request, roles=[], scopes=list(scopes))

    return dependency
