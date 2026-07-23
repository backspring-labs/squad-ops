"""SIP-0100 Phase 2 (Task 2.1) — contract-governed write authorization.

Two separate concepts (plan review #2/#3):

- ``WorkspaceOwnership`` — **permanent** for a bound build attempt: the frozen paths and the
  declared writable surfaces (fill slots + QA namespace), derived from the bind-time
  ``BoundScaffoldRecord`` (Task 0.3).
- ``WriteGrant`` — **transient**, resolved per producer *before* generation: the exact set of
  paths/prefixes this producer may write now (+ any explicit single-correction delegation).

``WriteAuthorization`` evaluates a **normalized** emitted path against both. Normalization is the
same canonical-target identity materialization uses (plan D7, Linux sandbox scope): ``./`` and
``//`` collapsed, ``..`` resolved lexically, absolute/escaping paths rejected. No filesystem
access — this runs *before* any write.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from enum import StrEnum

from squadops.cycles.bound_scaffold_record import BoundScaffoldRecord


class AuthzDecision(StrEnum):
    ALLOWED = "allowed"
    # Maps to the Task 0.5 contract-compliance reason codes.
    FORBIDDEN_FROZEN = "frozen_path_emission"
    FORBIDDEN_UNAUTHORIZED = "unauthorized_slot_emission"
    FORBIDDEN_UNDECLARED = "undeclared_path_emission"


def normalize_ws_path(path: str) -> str | None:
    """Canonical workspace-relative path, or ``None`` for an absolute or workspace-escaping path.

    Lexical only (no fs access): ``./a`` → ``a``; ``a//b`` → ``a/b``; ``a/../a/b`` → ``a/b``;
    ``/etc`` / ``../x`` → ``None``. Authorization and materialization MUST share this identity so
    they can never disagree (D7)."""
    p = str(path).strip()
    if not p or posixpath.isabs(p):
        return None
    norm = posixpath.normpath(p)
    if norm == ".." or norm.startswith("../"):
        return None
    return norm


def _in_surface(norm: str, tokens: frozenset[str]) -> bool:
    """A path is in a surface if it equals a token (an exact fill-slot file) or is under a
    directory token (a namespace prefix ending in ``/``)."""
    return any(norm == t or norm.startswith(t) for t in tokens)


@dataclass(frozen=True)
class WorkspaceOwnership:
    """Permanent bind-time ownership. Frozen paths are exact normalized files; writable surfaces
    are prefix tokens (exact slot files + QA namespace dir prefixes)."""

    frozen_paths: frozenset[str]
    fill_slots: frozenset[str]
    qa_namespace: frozenset[str]

    @classmethod
    def from_record(cls, record: BoundScaffoldRecord) -> WorkspaceOwnership:
        return cls(
            frozen_paths=frozenset(n for p in record.frozen_paths() if (n := normalize_ws_path(p))),
            fill_slots=frozenset(n for p in record.fill_slots if (n := normalize_ws_path(p))),
            qa_namespace=frozenset(record.qa_namespace),  # dir prefixes, kept verbatim
        )

    def declared_writable(self) -> frozenset[str]:
        """Every surface a producer *could* be granted (fill slots ∪ QA namespace) — not what any
        single producer may write. Used to distinguish 'unauthorized' from 'undeclared'."""
        return self.fill_slots | self.qa_namespace


@dataclass(frozen=True)
class WriteGrant:
    """Transient per-producer authority: the normalized paths/prefixes this producer may write,
    resolved before generation (never inferred from emitted artifacts at materialize time)."""

    producer: str
    stage: str
    writable: frozenset[str]
    delegated: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def for_dev_fill(cls, producer: str, ownership: WorkspaceOwnership) -> WriteGrant:
        """A dev fill/repair may write the scaffold fill slots (routes.py, views)."""
        return cls(producer=producer, stage="dev_fill", writable=ownership.fill_slots)

    @classmethod
    def for_qa(cls, producer: str, ownership: WorkspaceOwnership) -> WriteGrant:
        """A QA fill/correction may write only the QA test namespace (plan §4.4)."""
        return cls(producer=producer, stage="qa", writable=ownership.qa_namespace)


@dataclass(frozen=True)
class ResponseAuthz:
    """Result of authorizing a producer's complete emitted set (response-atomic, D5)."""

    allowed: bool
    decisions: tuple[tuple[str, AuthzDecision], ...]  # (original path, decision)
    violations: tuple[tuple[str, AuthzDecision], ...]  # subset with decision != ALLOWED


class WriteAuthorization:
    """Evaluate emitted paths against ownership + grant (plan review #2)."""

    def __init__(self, ownership: WorkspaceOwnership, grant: WriteGrant) -> None:
        self.ownership = ownership
        self.grant = grant

    def authorize(self, path: str) -> AuthzDecision:
        norm = normalize_ws_path(path)
        if norm is None:
            return AuthzDecision.FORBIDDEN_UNDECLARED  # absolute/escaping is not a declared surface
        if norm in self.ownership.frozen_paths:
            return AuthzDecision.FORBIDDEN_FROZEN
        if _in_surface(norm, self.grant.writable) or _in_surface(norm, self.grant.delegated):
            return AuthzDecision.ALLOWED
        if _in_surface(norm, self.ownership.declared_writable()):
            return AuthzDecision.FORBIDDEN_UNAUTHORIZED
        return AuthzDecision.FORBIDDEN_UNDECLARED

    def authorize_response(self, paths: list[str]) -> ResponseAuthz:
        """Authorize the COMPLETE normalized set before any write (D5). Any forbidden path — or a
        duplicate that normalizes to the same target as another (D7) — makes the whole response
        forbidden (response-atomic; §4.6)."""
        decisions: list[tuple[str, AuthzDecision]] = [(p, self.authorize(p)) for p in paths]

        # Duplicate-normalize-to-same-target is itself a violation (D7 / review #9): mark the
        # later collisions FORBIDDEN_UNDECLARED so the response is rejected.
        seen: set[str] = set()
        for i, p in enumerate(paths):
            norm = normalize_ws_path(p)
            if norm is not None and norm in seen and decisions[i][1] == AuthzDecision.ALLOWED:
                decisions[i] = (p, AuthzDecision.FORBIDDEN_UNDECLARED)
            if norm is not None:
                seen.add(norm)

        violations = tuple((p, d) for p, d in decisions if d != AuthzDecision.ALLOWED)
        return ResponseAuthz(
            allowed=not violations, decisions=tuple(decisions), violations=violations
        )
