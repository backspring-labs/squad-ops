"""
Auth domain models (SIP-0062 Section 6.3).

Frozen dataclasses for identity, token claims, authorization context, and audit events.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


class TokenValidationError(Exception):
    """Raised when a JWT token fails validation."""


class IdentityResolutionError(Exception):
    """Raised when token claims cannot be mapped to a domain Identity."""


class Role:
    """Canonical role constants."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    # Service role held by the squadops-agent service account (#326): lets agent
    # containers report their own status via the authed lane, nothing else.
    AGENT = "agent"


class Scope:
    """Canonical scope constants."""

    CYCLES_READ = "cycles:read"
    CYCLES_WRITE = "cycles:write"
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    ADMIN_WRITE = "admin:write"


# Role → implied scopes (#270). Keycloak is role-centric — it issues realm roles
# (admin/operator/viewer), not fine-grained OAuth scopes — so holding a role
# grants its scopes. The effective scope set (token scopes ∪ role-implied) is
# what `require_scopes` evaluates, which lets #150's scope-gated cycle routes
# honor the realm's documented role model ("operator = start/stop cycles")
# without a Keycloak change. Single-sourced here so route guards and the realm
# stay reconcilable.
ROLE_SCOPES: dict[str, frozenset[str]] = {
    Role.ADMIN: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.CYCLES_WRITE,
            Scope.AGENTS_READ,
            Scope.AGENTS_WRITE,
            Scope.TASKS_READ,
            Scope.TASKS_WRITE,
            Scope.ADMIN_WRITE,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.CYCLES_WRITE,
            Scope.AGENTS_READ,
            Scope.TASKS_READ,
            Scope.TASKS_WRITE,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.AGENTS_READ,
            Scope.TASKS_READ,
        }
    ),
    Role.AGENT: frozenset(
        {
            Scope.AGENTS_WRITE,
        }
    ),
}


def scopes_for_roles(roles: tuple[str, ...]) -> frozenset[str]:
    """Union of the scopes implied by ``roles`` (#270). Unknown roles contribute
    nothing — a token with no mapped role gets no implied scopes."""
    implied: set[str] = set()
    for role in roles:
        implied |= ROLE_SCOPES.get(role, frozenset())
    return frozenset(implied)


class IdentityType:
    """Identity type constants."""

    HUMAN = "human"
    SERVICE = "service"


@dataclass(frozen=True)
class TokenClaims:
    """Parsed JWT claims."""

    subject: str
    issuer: str
    audience: str | tuple[str, ...]
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
    identity_type: str = IdentityType.HUMAN


@dataclass(frozen=True)
class AuthContext:
    """Authorization check result."""

    granted: bool
    identity: Identity | None = None
    denial_reason: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    """Structured security audit event (SIP-0062 Phase 3b)."""

    action: str  # e.g. "auth.token_validated", "auth.token_rejected"
    actor_id: str  # Identity.user_id or "anonymous"
    actor_type: str  # "human" | "service" | "unknown"
    resource_type: str  # e.g. "api"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    resource_id: str | None = None  # e.g. request path
    result: str = "success"  # "success" | "denied" | "error"
    denial_reason: str | None = None
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    request_id: str | None = None  # From X-Request-ID
    ip_address: str | None = None
