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


class Scope:
    """Canonical scope constants."""

    CYCLES_READ = "cycles:read"
    CYCLES_WRITE = "cycles:write"
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    ADMIN_WRITE = "admin:write"


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
