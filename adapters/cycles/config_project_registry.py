"""
Config-file project registry adapter (SIP-0064).

Loads projects from config/projects.yaml (T3: YAML is the canonical runtime source).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import yaml

from squadops.cycles.models import Project, ProjectNotFoundError
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
