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
    # containers report their own status via the authed lane, and ask for a remote
    # operation, read it and cancel it (SIP-0117 R5.6). Nothing else.
    AGENT = "agent"
    # Service role held by the squadops-worker service account (SIP-0117 R5.3): lets a
    # remote-execution worker register, claim an operation and report on it, nothing else.
    WORKER = "worker"
    # SIP-0109 §13 (#1799): the operator's two seats. The supervisor supervises a campaign —
    # reads it, rules at its increment gate, takes and releases the box lease, and pauses
    # it — and manages it (#1940, §24az): creates, starts and aborts it, materializes its
    # package, and resumes its own pause. Resuming an escalation, a limit's pause or the
    # owner's pause stays the owner's (``admin``). Triage reads, and nothing else (#1719).
    CAMPAIGN_SUPERVISOR = "campaign-supervisor"
    CAMPAIGN_TRIAGE = "campaign-triage"


class Scope:
    """Canonical scope constants."""

    CYCLES_READ = "cycles:read"
    CYCLES_WRITE = "cycles:write"
    AGENTS_READ = "agents:read"
    AGENTS_WRITE = "agents:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    ADMIN_WRITE = "admin:write"
    # SIP-0109 §13: read a campaign and its control log; supervise it (rule, lease, pause);
    # manage it (create, start, abort, package, resume the supervisor's pause; #1940, §24az; and
    # the draft's integration check, SIP-0112 H.30, which may sync a Project and re-validate it only
    # within its bounded delegation: READY, after its own sync, at that sync's commit, fenced. It
    # implies no other validation: POST …/syncs and …/validate stay admin:write);
    # control it (resume an escalation, a limit's pause or the owner's pause; grant the operator a
    # Campaign's goal-set curation, SIP-0115 Q41) — the last is the owner's alone.
    CAMPAIGNS_READ = "campaigns:read"
    CAMPAIGNS_SUPERVISE = "campaigns:supervise"
    CAMPAIGNS_MANAGE = "campaigns:manage"
    CAMPAIGNS_CONTROL = "campaigns:control"
    # SIP-0110 §0.6 (slice 3d): read Cross-Cycle Memory's lessons; draft a revision (the auditor,
    # the outer loop's seat, D15); approve or revoke one, which is the owner's alone.
    MEMORY_READ = "memory:read"
    MEMORY_DRAFT = "memory:draft"
    MEMORY_APPROVE = "memory:approve"
    # SIP-0110 Appendix A §A.3.3 (#2177): write a project note; write and confirm a project
    # instruction. Held by the admins who hold memory:approve until a project membership model
    # exists (Q27). A user-private note or preference needs neither: its owner writes it.
    MEMORY_NOTE = "memory:note"
    MEMORY_INSTRUCT = "memory:instruct"
    # SIP-0113 §4.1 (#2413): Outcome Evaluation's held-out scenario suites. Read a suite's goals and
    # state; draft one (the supervisor, the 2.4 plan's D2); approve one and read its held-out steps,
    # which is the owner's alone. No squad agent's role holds any of them.
    SCENARIOS_READ = "scenarios:read"
    SCENARIOS_DRAFT = "scenarios:draft"
    SCENARIOS_APPROVE = "scenarios:approve"
    # SIP-0117 R3.3, R5.3: the workers API, as a worker uses it: register a session, heartbeat,
    # claim an operation and submit its result. Held by the worker role alone; no person's role
    # and no squad agent's holds it.
    WORKERS_SERVE = "workers:serve"
    # #3047: read the worker registry: each live session's health, what it serves and holds,
    # and its worker's recent refused results. A person's read; a worker's role doesn't hold it.
    WORKERS_READ = "workers:read"
    # SIP-0117 R5.6 (ruled 2026-11-11): ask for a remote operation, read it and cancel it. Held
    # by the agent role alone: the handler of ``qa.run_remote_operation`` runs in an agent, and
    # this is how its request reaches the queue. A worker's role doesn't hold it, so a worker
    # can't queue work for itself, and no person's role does.
    OPERATIONS_REQUEST = "operations:request"


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
            Scope.CAMPAIGNS_READ,
            Scope.CAMPAIGNS_SUPERVISE,
            Scope.CAMPAIGNS_MANAGE,
            Scope.CAMPAIGNS_CONTROL,
            Scope.MEMORY_READ,
            Scope.MEMORY_DRAFT,
            Scope.MEMORY_APPROVE,
            Scope.MEMORY_NOTE,
            Scope.MEMORY_INSTRUCT,
            Scope.SCENARIOS_READ,
            Scope.SCENARIOS_DRAFT,
            Scope.SCENARIOS_APPROVE,
            Scope.WORKERS_READ,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.CYCLES_WRITE,
            Scope.AGENTS_READ,
            Scope.TASKS_READ,
            Scope.TASKS_WRITE,
            Scope.CAMPAIGNS_READ,
            Scope.MEMORY_READ,
            Scope.WORKERS_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.AGENTS_READ,
            Scope.TASKS_READ,
            Scope.CAMPAIGNS_READ,
            Scope.MEMORY_READ,
            Scope.WORKERS_READ,
        }
    ),
    Role.AGENT: frozenset(
        {
            Scope.AGENTS_WRITE,
            Scope.OPERATIONS_REQUEST,
        }
    ),
    Role.WORKER: frozenset(
        {
            Scope.WORKERS_SERVE,
        }
    ),
    Role.CAMPAIGN_SUPERVISOR: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.CAMPAIGNS_READ,
            Scope.CAMPAIGNS_SUPERVISE,
            Scope.CAMPAIGNS_MANAGE,
            Scope.MEMORY_READ,
            Scope.SCENARIOS_READ,
            Scope.SCENARIOS_DRAFT,
            Scope.WORKERS_READ,
        }
    ),
    Role.CAMPAIGN_TRIAGE: frozenset(
        {
            Scope.CYCLES_READ,
            Scope.CAMPAIGNS_READ,
            Scope.MEMORY_READ,
            Scope.SCENARIOS_READ,
            Scope.WORKERS_READ,
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
