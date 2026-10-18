"""The writable Project registry, on Postgres (SIP-0112 FR-03, E.4.1, #2408).

Every read goes to the database: there are a handful of Projects, every reader is in the runtime
API, and a cache would only add the invalidation that lets a newly registered Project go unseen
(IR-8). ``config/projects.yaml`` reaches it once per entry, through the seed log.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import asyncpg

from squadops.cycles.models import Project, ProjectNotFoundError
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.projects.models import (
    ProjectLifecycleStatus,
    ProjectOwnership,
    ProjectProvenance,
    ProjectSource,
)

_COLUMNS = (
    "project_id, name, description, tags, prd_path, lifecycle_status, record_version, "
    "repo_uri, base_ref, contribution_mode, repository_root, ownership, "
    "development_configuration_revision, created_at"
)


def _row_to_project(row: asyncpg.Record) -> Project:
    ownership = row["ownership"]
    return Project(
        project_id=row["project_id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        tags=tuple(row["tags"]),
        prd_path=row["prd_path"],
        lifecycle_status=ProjectLifecycleStatus(row["lifecycle_status"]),
        record_version=row["record_version"],
        source=(
            ProjectSource(
                repo_uri=row["repo_uri"],
                base_ref=row["base_ref"],
                contribution_mode=row["contribution_mode"],
                repository_root=row["repository_root"],
            )
            if row["repo_uri"] is not None
            else None
        ),
        ownership=(
            ProjectOwnership(
                owner=ownership["owner"],
                delegated_actions=tuple(ownership["delegated_actions"]),
                acceptance_policy_ref=ownership["acceptance_policy_ref"],
            )
            if ownership is not None
            else None
        ),
        development_configuration_revision=row["development_configuration_revision"],
    )


def _event_id() -> str:
    return f"pev_{uuid.uuid4().hex[:12]}"


class PostgresProjectRegistry(ProjectRegistryPort):
    """The writable registry: authoritative for every reader once selected (FR-03)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_projects(self) -> list[Project]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT {_COLUMNS} FROM project_records ORDER BY listed_order")
        return [_row_to_project(row) for row in rows]

    async def get_project(self, project_id: str) -> Project:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM project_records WHERE project_id = $1", project_id
            )
        if row is None:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return _row_to_project(row)

    # --- the cutover (FR-03) ---

    async def seed_from_config(self, projects: Sequence[Project], *, source: str) -> list[str]:
        """Seed each config Project not seeded before, in the file's order; return those seeded.

        One transaction per Project: the seed log's claim, the record and its event commit
        together. A record already holding the ID (a registered Project) keeps it; the cutover's
        check names the conflict.
        """
        seeded = []
        async with self._pool.acquire() as conn:
            for project in projects:
                async with conn.transaction():
                    now = datetime.now(UTC)
                    claimed = await conn.fetchval(
                        "INSERT INTO project_seed_log (project_id, source, seeded_at) "
                        "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING RETURNING project_id",
                        project.project_id,
                        source,
                        now,
                    )
                    if claimed is None:
                        continue
                    inserted = await conn.fetchval(
                        "INSERT INTO project_records (project_id, name, description, tags, "
                        "prd_path, lifecycle_status, record_version, provenance, created_at, "
                        "updated_at) VALUES ($1, $2, $3, $4, $5, $6, 1, $7, $8, $8) "
                        "ON CONFLICT (project_id) DO NOTHING RETURNING project_id",
                        project.project_id,
                        project.name,
                        project.description,
                        list(project.tags),
                        project.prd_path,
                        ProjectLifecycleStatus.READY.value,
                        ProjectProvenance.SEEDED.value,
                        now,
                    )
                    if inserted is None:
                        continue
                    await conn.execute(
                        "INSERT INTO project_record_events (event_id, project_id, operation, "
                        "record_version, actor, detail, recorded_at) "
                        "VALUES ($1, $2, 'seed', 1, 'squadops', $3, $4)",
                        _event_id(),
                        project.project_id,
                        {"source": source},
                        now,
                    )
                    seeded.append(project.project_id)
        return seeded

    async def provenances(self) -> dict[str, ProjectProvenance]:
        """Every record's ID and how it entered the registry."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT project_id, provenance FROM project_records")
        return {row["project_id"]: ProjectProvenance(row["provenance"]) for row in rows}

    async def referenced_project_ids(self) -> set[str]:
        """The Project IDs cycles and campaigns hold, which no foreign key ties to a record."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT project_id FROM cycle_registry UNION SELECT project_id FROM campaigns"
            )
        return {row["project_id"] for row in rows}


async def writable_registry_provenances(pool: asyncpg.Pool) -> dict[str, ProjectProvenance] | None:
    """The writable registry's records, read on the config provider's start; ``None`` when its
    table does not exist, as on a deploy that has never applied migration 1800."""
    async with pool.acquire() as conn:
        present = await conn.fetchval("SELECT to_regclass('public.project_records') IS NOT NULL")
    if not present:
        return None
    return await PostgresProjectRegistry(pool).provenances()
