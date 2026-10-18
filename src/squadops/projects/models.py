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
