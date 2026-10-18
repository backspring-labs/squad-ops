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
