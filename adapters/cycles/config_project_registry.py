"""
Config-file project registry adapter (SIP-0064).

Loads projects from config/projects.yaml (T3: YAML is the canonical runtime source).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml

from squadops.cycles.models import (
    DevelopmentConfigurationNotFoundError,
    InheritedBaselineNotFoundError,
    Project,
    ProjectNotFoundError,
    ProjectRegistryReadOnlyError,
)
from squadops.ports.cycles.project_registry import ProjectRegistryPort

logger = logging.getLogger(__name__)

_DEFAULT_YAML_PATH = Path("config/projects.yaml")


class ConfigProjectRegistry(ProjectRegistryPort):
    """Loads projects from a YAML config file."""

    def __init__(self, yaml_path: str | Path | None = None) -> None:
        self._yaml_path = Path(yaml_path) if yaml_path else _DEFAULT_YAML_PATH
        self._projects: dict[str, Project] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if not self._yaml_path.exists():
            logger.warning("Projects YAML not found: %s", self._yaml_path)
            self._loaded = True
            return

        with open(self._yaml_path) as f:
            data = yaml.safe_load(f) or {}

        now = datetime.now(UTC)
        for entry in data.get("projects", []):
            project = Project(
                project_id=entry["project_id"],
                name=entry["name"],
                description=entry.get("description", ""),
                created_at=entry.get("created_at", now),
                tags=tuple(entry.get("tags", ())),
                prd_path=entry.get("prd_path"),
            )
            self._projects[project.project_id] = project

        logger.info("Loaded %d projects from %s", len(self._projects), self._yaml_path)
        self._loaded = True

    async def list_projects(self) -> list[Project]:
        self._load()
        return list(self._projects.values())

    async def get_project(self, project_id: str) -> Project:
        self._load()
        if project_id not in self._projects:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return self._projects[project_id]

    async def register_project(self, registration, *, actor: str):
        raise ProjectRegistryReadOnlyError(
            "the config provider is read-only: config/projects.yaml is edited, never written. "
            "Registration needs cycles.project_registry_provider: postgres (SIP-0112 FR-03)"
        )

    async def record_validation(self, project_id, *, commit, diagnostic, actor, idempotency_key):
        raise ProjectRegistryReadOnlyError(
            "the config provider is read-only: its sample applications have no external source "
            "to validate (SIP-0112 FR-03)"
        )

    async def record_development_configuration(
        self, configuration, *, actor, idempotency_key, request_hash
    ):
        raise ProjectRegistryReadOnlyError(
            "the config provider is read-only: a Development Configuration needs the writable "
            "registry (SIP-0112 FR-03)"
        )

    async def get_development_configuration(self, project_id, revision=None):
        raise DevelopmentConfigurationNotFoundError(
            f"Project {project_id} is a sample application: it has no Development Configuration"
        )

    async def record_source_mapping(self, mapping):
        raise ProjectRegistryReadOnlyError("the config provider records no source mappings")

    async def source_mappings(self, project_id, *, workspace_id=None):
        return []

    async def record_inherited_baseline(self, baseline, *, actor, idempotency_key, request_hash):
        raise ProjectRegistryReadOnlyError("the config provider records no baselines")

    async def record_contribution(self, contribution, *, idempotency_key, request_hash):
        raise ProjectRegistryReadOnlyError("the config provider records no contributions")

    async def contributions(self, project_id):
        return []

    async def record_contribution_state(self, project_id, cycle_id, run_id, **kwargs):
        raise ProjectRegistryReadOnlyError("the config provider records no contributions")

    async def record_sync(self, document, *, actor, idempotency_key, request_hash):
        raise ProjectRegistryReadOnlyError("the config provider records no syncs")

    async def source_syncs(self, project_id):
        return []

    async def get_inherited_baseline(self, project_id):
        raise InheritedBaselineNotFoundError(
            f"Project {project_id} is a sample application: it has no inherited baseline"
        )
