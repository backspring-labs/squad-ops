"""The writable Project registry against real Postgres (SIP-0112 FR-03, IR-1, IR-8; #2408).

The unit tests hold the cutover's decisions over a recorder. Only a database proves what the
cutover claims of the store: the config file's projects read back as the config registry reads
them, in its order; a seed is applied once, so an edit to the file after the cutover is not; a
registered Project keeps its ID against the seed; and every read goes to the database, so a
Project written by anyone is seen at once.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from adapters.cycles.config_project_registry import ConfigProjectRegistry
from adapters.cycles.postgres_project_registry import (
    PostgresProjectRegistry,
    writable_registry_provenances,
)
from adapters.persistence.pool import create_pool
from squadops.cycles.models import ProjectNotFoundError
from squadops.projects.cutover import problems_after_seeding
from squadops.projects.models import ProjectLifecycleStatus, ProjectProvenance
from tests.integration.conftest import integration_postgres_dsn

pytestmark = [pytest.mark.docker, pytest.mark.domain_orchestration]

POSTGRES_URL = integration_postgres_dsn()  # #1099: never the deployment DB
CONFIG_YAML = Path(__file__).parents[3] / "config" / "projects.yaml"
REFERENCED = "registry_it_cycle_project"

asyncpg = pytest.importorskip("asyncpg")


def _pg_available() -> bool:
    import socket

    url = urlparse(POSTGRES_URL)
    try:
        with socket.create_connection((url.hostname or "localhost", url.port or 5432), timeout=2):
            return True
    except OSError:
        return False


if not _pg_available():
    pytest.skip("Postgres not reachable at the integration DSN", allow_module_level=True)


@pytest_asyncio.fixture
async def pool():
    from squadops.api.runtime.migrations import apply_migrations

    pool = await create_pool(POSTGRES_URL, min_size=1, max_size=4)
    await apply_migrations(pool, Path(__file__).parents[3] / "infra" / "migrations")
    async with pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE project_record_events, project_records, project_seed_log CASCADE"
        )
        await conn.execute("DELETE FROM cycle_registry WHERE project_id = $1", REFERENCED)
    yield pool
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cycle_registry WHERE project_id = $1", REFERENCED)
    await pool.close()


async def _config_projects():
    return await ConfigProjectRegistry(CONFIG_YAML).list_projects()


async def _insert_registered(pool, project_id: str) -> None:
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO project_records (project_id, name, description, tags, lifecycle_status, "
            "record_version, provenance, repo_uri, base_ref, contribution_mode, repository_root, "
            "ownership, created_at, updated_at) VALUES ($1, 'Registered', '', '{}', "
            "'REGISTERING', 1, 'registered', 'https://code.example.invalid/x.git', "
            "'refs/heads/main', 'review_request', '.', $2, $3, $3)",
            project_id,
            {
                "owner": "Owner",
                "delegated_actions": ["contribution"],
                "acceptance_policy_ref": None,
            },
            now,
        )


async def test_the_seeded_registry_reads_as_the_config_file_reads(pool):
    """IR-1 at the registry. Bugs caught: a field dropped or re-typed in the seed (tags as a
    string, a lost prd_path), the listing reordered, or a sample application read as anything
    but READY at version 1 with no source."""
    config = await _config_projects()
    registry = PostgresProjectRegistry(pool)

    seeded = await registry.seed_from_config(config, source="config/projects.yaml")
    listed = await registry.list_projects()

    assert seeded == [p.project_id for p in config]
    for before, after in zip(config, listed, strict=True):
        assert dataclasses.replace(after, created_at=before.created_at) == before
        assert after.lifecycle_status is ProjectLifecycleStatus.READY
    assert [await registry.get_project(p.project_id) for p in config] == listed
    assert (
        problems_after_seeding([p.project_id for p in config], await registry.provenances()) == []
    )


async def test_a_second_seed_applies_nothing_and_a_file_edit_after_it_is_not_applied(pool):
    """FR-03: after the cutover the writable registry is the authority. Bug caught: every
    restart re-applying the config file, so an edit to it silently rewrites a Project."""
    config = await _config_projects()
    registry = PostgresProjectRegistry(pool)
    await registry.seed_from_config(config, source="config/projects.yaml")

    edited = [dataclasses.replace(config[0], name="Renamed in the file"), *config[1:]]
    again = await registry.seed_from_config(edited, source="config/projects.yaml")

    assert again == []
    assert (await registry.get_project(config[0].project_id)).name == config[0].name


async def test_a_registered_project_keeps_its_id_against_the_seed_and_is_named(pool):
    """Bug caught: the seed overwriting a registered Project that shares a sample's ID, or the
    conflict passing unnamed so the registered Project silently answers for the sample."""
    config = await _config_projects()
    taken = config[1].project_id
    await _insert_registered(pool, taken)
    registry = PostgresProjectRegistry(pool)

    await registry.seed_from_config(config, source="config/projects.yaml")
    held = await registry.get_project(taken)
    problems = problems_after_seeding([p.project_id for p in config], await registry.provenances())

    assert (held.name, held.lifecycle_status) == ("Registered", ProjectLifecycleStatus.REGISTERING)
    assert held.source.repo_uri == "https://code.example.invalid/x.git"
    assert held.ownership.delegated_actions == ("contribution",)
    assert [p.project_id for p in problems] == [taken]
    assert (await writable_registry_provenances(pool))[taken] is ProjectProvenance.REGISTERED


async def test_a_project_written_after_the_first_read_is_read_at_once(pool):
    """IR-8. Bug caught: a registry that caches its first read, so a Project registered while
    the runtime API runs stays invisible to every reader until a restart."""
    registry = PostgresProjectRegistry(pool)
    assert await registry.list_projects() == []

    await _insert_registered(pool, "prj-tally")

    assert [p.project_id for p in await registry.list_projects()] == ["prj-tally"]
    assert (await registry.get_project("prj-tally")).project_id == "prj-tally"


async def test_an_unknown_project_is_not_found(pool):
    with pytest.raises(ProjectNotFoundError, match="prj-nowhere"):
        await PostgresProjectRegistry(pool).get_project("prj-nowhere")


async def test_the_projects_cycles_hold_are_read_from_the_cycle_table(pool):
    """FR-03's report. Bug caught: the query reading the wrong column or table, so a cycle's
    unknown project is never reported."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO cycle_registry (cycle_id, project_id, created_by, squad_profile_id, "
            "squad_profile_snapshot_ref, task_flow_policy, build_strategy) "
            "VALUES ('cyc_registry_it', $1, 'it', 'full', 'sha256:x', '{}', 'fresh')",
            REFERENCED,
        )

    assert REFERENCED in await PostgresProjectRegistry(pool).referenced_project_ids()
