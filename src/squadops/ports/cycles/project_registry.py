"""
ProjectRegistryPort — abstract interface for project lookup (SIP-0064 §7.1), and registration
(SIP-0112 FR-02, E.4.1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from squadops.cycles.models import Project
from squadops.projects.baseline import InheritedBaseline
from squadops.projects.development_configuration import DevelopmentConfiguration
from squadops.projects.registration import ProjectRegistration

if TYPE_CHECKING:
    from squadops.projects.contribution import Contribution
    from squadops.projects.workspaces import SourceMapping


class ProjectRegistryPort(ABC):
    """Port for listing and retrieving pre-registered projects."""

    @abstractmethod
    async def list_projects(self) -> list[Project]:
        """Return all registered projects."""

    @abstractmethod
    async def get_project(self, project_id: str) -> Project:
        """Return a project by ID.

        Raises:
            ProjectNotFoundError: If the project_id is not found.
        """

    @abstractmethod
    async def register_project(
        self, registration: ProjectRegistration, *, actor: str
    ) -> tuple[Project, bool]:
        """Register an existing product, as ``REGISTERING``; return it and whether this was a
        replay of an earlier request with the same idempotency key.

        Raises:
            ProjectRegistryReadOnlyError: The registry refuses writes.
            ProjectIdTakenError: The Project ID is held.
            RegistrationKeyConflictError: The key registered different content.
        """

    @abstractmethod
    async def record_validation(
        self,
        project_id: str,
        *,
        commit: str | None,
        diagnostic: str | None,
        actor: str,
        idempotency_key: str,
    ) -> tuple[Project, bool]:
        """Record a registered Project's validation (SIP-0112 E.4.2, §B.6): READY at ``commit``
        when its source was reached, FAILED_REGISTRATION with ``diagnostic`` when not. Exactly
        one of the two is given. Returns the Project and whether this replayed an earlier
        validation under the same key.

        Raises:
            ProjectRegistryReadOnlyError: The registry refuses writes.
            ProjectStateConflictError: The Project is not REGISTERING or FAILED_REGISTRATION.
            RegistrationKeyConflictError: The key recorded a different validation.
        """

    @abstractmethod
    async def record_development_configuration(
        self,
        configuration: DevelopmentConfiguration,
        *,
        actor: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[DevelopmentConfiguration, bool]:
        """Record ``configuration`` as its Project's next revision (SIP-0112 §B.5, E.4.2), which
        must follow the current one. Returns it and whether this replayed an earlier recording
        under the same key.

        Raises:
            ProjectRegistryReadOnlyError: The registry refuses writes.
            StaleConfigurationRevisionError: Its revision doesn't follow the current one.
            RegistrationKeyConflictError: The key recorded different content.
        """

    @abstractmethod
    async def get_development_configuration(
        self, project_id: str, revision: int | None = None
    ) -> DevelopmentConfiguration:
        """A Project's Development Configuration: ``revision``, or the current one.

        Raises:
            DevelopmentConfigurationNotFoundError: None is recorded, or not that revision.
        """

    @abstractmethod
    async def record_source_mapping(self, mapping: SourceMapping) -> None:
        """Record one tree's three identifiers (contract 3). Recording the same one again is a
        no-op: a seed is idempotent, and so is its mapping."""

    @abstractmethod
    async def source_mappings(
        self, project_id: str, *, workspace_id: str | None = None
    ) -> list[SourceMapping]:
        """A Project's recorded mappings, oldest first, or one workspace's."""

    @abstractmethod
    async def record_inherited_baseline(
        self,
        baseline: InheritedBaseline,
        *,
        actor: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[InheritedBaseline, bool]:
        """Record a captured inherited baseline (FR-20). Returns it and whether this replayed an
        earlier capture under the same key."""

    @abstractmethod
    async def get_inherited_baseline(self, project_id: str) -> InheritedBaseline:
        """The Project's latest inherited baseline.

        Raises:
            InheritedBaselineNotFoundError: none is captured.
        """

    @abstractmethod
    async def record_contribution(
        self, contribution: Contribution, *, idempotency_key: str, request_hash: str
    ) -> tuple[Contribution, bool]:
        """Record a run's contribution, pending (FR-06, E.4.3). Returns it and whether this
        replayed an earlier one: the same key, or the same run contributed already."""

    @abstractmethod
    async def contributions(self, project_id: str) -> list[Contribution]:
        """A Project's contributions, oldest first."""

    @abstractmethod
    async def record_contribution_state(
        self,
        project_id: str,
        cycle_id: str,
        run_id: str,
        *,
        state: str,
        integrated_commit: str | None,
        actor: str,
    ) -> Contribution:
        """Record where a contribution now stands (E.4.4): integrated, through the commit the
        product took it by, or closed."""

    @abstractmethod
    async def record_sync(
        self, document: dict, *, actor: str, idempotency_key: str, request_hash: str
    ) -> tuple[dict, bool]:
        """Record one read of upstream against the approved baseline (FR-21). Returns the
        document and whether this replayed an earlier sync under the same key."""

    @abstractmethod
    async def source_syncs(self, project_id: str) -> list[dict]:
        """A Project's syncs, oldest first: the drift findings a later unit resolves (FR-09)."""
