"""The Project Record's parts (SIP-0112 §B.5, §B.6)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProjectLifecycleStatus(StrEnum):
    """§B.6's public lifecycle. ``ACTIVE`` is derived from active work and never stored."""

    REGISTERING = "REGISTERING"
    READY = "READY"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    FAILED_REGISTRATION = "FAILED_REGISTRATION"

    @property
    def accepts_cycles(self) -> bool:
        """Whether a new Cycle may be prepared for a Project in this state (contract 1)."""
        return self in (ProjectLifecycleStatus.READY, ProjectLifecycleStatus.ACTIVE)


class ProjectProvenance(StrEnum):
    """How a Project Record entered the writable registry."""

    #: imported from ``config/projects.yaml`` at the cutover (FR-03)
    SEEDED = "seeded"
    #: enrolled through the lifecycle API (FR-02)
    REGISTERED = "registered"


@dataclass(frozen=True)
class ProjectSource:
    """The external source binding (§B.5): the authoritative locator, never the managed clone."""

    repo_uri: str
    base_ref: str
    contribution_mode: str
    repository_root: str = "."


@dataclass(frozen=True)
class ProjectOwnership:
    """The external product's authority (§B.5.1): who owns it and what they delegate."""

    owner: str
    delegated_actions: tuple[str, ...] = ()
    acceptance_policy_ref: str | None = None


class ContributionMode(StrEnum):
    """How a verified change reaches the external product (FR-06): its owner's process, never
    SquadOps's. Recorded at registration; E.4.3 delivers through it."""

    #: a pull or merge request against ``base_ref``, for the product's own review
    REVIEW_REQUEST = "review_request"
    #: a patch handed to the owner to apply
    PATCH_EXPORT = "patch_export"
    #: a push to ``base_ref``, only where the owner has delegated integration
    DIRECT_PUSH = "direct_push"


class DelegatedAction(StrEnum):
    """What the product's owner delegates to SquadOps (§B.5.1). Anything not named stays the
    owner's; no role has implicit authority over the product."""

    ENGINEERING_DECISIONS = "engineering_decisions"
    CANDIDATE_ACCEPTANCE = "candidate_acceptance"
    CONTRIBUTION = "contribution"
    INTEGRATION = "integration"


class SourceUnavailable(RuntimeError):
    """A product's source could not be reached or read: the reason, never a partial tree."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class RefMoved(SourceUnavailable):
    """A compare-and-swap on a managed clone's ref lost: the ref wasn't at the commit the caller
    expected (SIP-0109 §24cd point 2). ``held`` is the commit it names now, or ``None`` when there
    is no such ref. Nothing was moved."""

    def __init__(self, message: str, *, held: str | None) -> None:
        super().__init__(message, reason="ref_moved")
        self.held = held


class RebaseConflict(SourceUnavailable):
    """A campaign branch's commit that doesn't apply on the commit it is rebased onto (SIP-0109
    §24bv point 4): ``commit`` is the branch's commit that conflicted, and ``paths`` the files it
    conflicts on. Nothing was written to any ref, and nothing is resolved by itself."""

    def __init__(self, message: str, *, commit: str, paths: tuple[str, ...]) -> None:
        super().__init__(message, reason="rebase_conflict")
        self.commit = commit
        self.paths = paths


@dataclass(frozen=True)
class Rebased:
    """A campaign branch's commits replayed onto another commit in the managed clone (SIP-0109
    §24bv point 4). ``commit`` is the rebased head: ``onto`` itself when upstream already holds
    every change (the owner merged them, §24cd point 4). ``replayed`` pairs each commit replayed
    with the commit it became, in order, and ``dropped`` names those upstream already held."""

    commit: str
    replayed: tuple[tuple[str, str], ...]
    dropped: tuple[str, ...]


@dataclass(frozen=True)
class CheckoutTree:
    """A commit's tracked tree, as the sandbox can carry it (X-1, X-2): files as bytes and the
    executable bit. A tracked symlink or submodule, or a path that isn't UTF-8, has no form
    there, so each is listed for the caller to refuse by name (§8.2.1: never seeded in part)."""

    commit: str
    files: dict[str, bytes]
    executable: frozenset[str]
    symlinks: frozenset[str]
    submodules: frozenset[str]
    #: Paths that aren't UTF-8, shown with their bytes escaped: a workspace path is text.
    undecodable_paths: frozenset[str] = frozenset()

    @property
    def capability_gaps(self) -> list[str]:
        """What the sandbox cannot carry, named, in the order a reader fixes them."""
        gaps = []
        if self.undecodable_paths:
            gaps.append(f"paths that aren't UTF-8: {', '.join(sorted(self.undecodable_paths))}")
        if self.symlinks:
            gaps.append(f"tracked symlinks: {', '.join(sorted(self.symlinks))}")
        if self.submodules:
            gaps.append(f"submodules: {', '.join(sorted(self.submodules))}")
        return gaps
