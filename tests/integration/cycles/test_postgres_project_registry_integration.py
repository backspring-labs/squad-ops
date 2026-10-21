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


def _registration(key="import-1", **overrides):
    from squadops.projects.registration import LocatorPolicy, prepare_registration

    fields = {
        "idempotency_key": key,
        "name": "Tally",
        "repo_uri": "https://code.example.invalid/tally/tally.git",
        "base_ref": "refs/heads/main",
        "contribution_mode": "review_request",
        "owner": "Tally Maintainer",
        "delegated_actions": ["contribution"],
        "policy": LocatorPolicy(),
        **overrides,
    }
    return prepare_registration(**fields)


async def test_a_registration_is_written_registering_and_read_back_whole(pool):
    """E.4.1, IR-8. Bugs caught: a field lost between the registration and the record; the
    record written READY before its source is proven; the event missing its key, so a retry
    could not replay."""
    registry = PostgresProjectRegistry(pool)
    await registry.seed_from_config(await _config_projects(), source="config/projects.yaml")

    project, replayed = await registry.register_project(_registration(), actor="owner")

    assert replayed is False
    assert (project.project_id, project.lifecycle_status) == (
        "prj-tally",
        ProjectLifecycleStatus.REGISTERING,
    )
    assert project.source.base_ref == "refs/heads/main"
    assert project.ownership.owner == "Tally Maintainer"
    assert [p.project_id for p in await registry.list_projects()][-1] == "prj-tally"
    assert await registry.get_project("prj-tally") == project
    async with pool.acquire() as conn:
        event = await conn.fetchrow(
            "SELECT operation, actor, idempotency_key, record_version FROM project_record_events "
            "WHERE project_id = 'prj-tally'"
        )
    assert dict(event) == {
        "operation": "register",
        "actor": "owner",
        "idempotency_key": "import-1",
        "record_version": 1,
    }


async def test_a_retry_replays_and_another_body_under_its_key_is_refused(pool):
    from squadops.cycles.models import RegistrationKeyConflictError

    registry = PostgresProjectRegistry(pool)
    first, _ = await registry.register_project(_registration(), actor="owner")

    again, replayed = await registry.register_project(_registration(), actor="owner")
    with pytest.raises(RegistrationKeyConflictError, match="import-1"):
        await registry.register_project(_registration(base_ref="refs/heads/dev"), actor="owner")

    assert (again, replayed) == (first, True)
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM project_record_events") == 1


async def test_two_retries_racing_under_one_key_register_once(pool):
    """Bug caught: a retry racing its original, both past the key check, so the loser fails
    on the unique index as a 500 instead of replaying."""
    import asyncio

    registry = PostgresProjectRegistry(pool)

    results = await asyncio.gather(
        *(registry.register_project(_registration(), actor="owner") for _ in range(4))
    )

    assert sorted(replayed for _, replayed in results) == [False, True, True, True]
    assert len({project for project, _ in results}) == 1


async def test_a_taken_id_and_a_closed_gate_write_nothing(pool):
    from squadops.cycles.models import ProjectIdTakenError, ProjectRegistryReadOnlyError

    registry = PostgresProjectRegistry(pool)
    await registry.seed_from_config(await _config_projects(), source="config/projects.yaml")

    with pytest.raises(ProjectIdTakenError, match="play_game"):
        await registry.register_project(_registration(project_id="play_game"), actor="owner")
    with pytest.raises(ProjectRegistryReadOnlyError, match="gated off"):
        await PostgresProjectRegistry(pool, writable=False).register_project(
            _registration(), actor="owner"
        )

    assert (await registry.get_project("play_game")).name != "Tally"
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM project_record_events WHERE operation = 'register'"
            )
            == 0
        )


async def test_a_validation_moves_a_registration_ready_or_failed_and_a_retry_recovers(pool):
    """E.4.2, §B.6. Bugs caught: READY written without the commit contract 1 pins; a failure's
    diagnostic surviving the retry that fixed it; a validation applied twice under one key; a
    READY Project validated again here, where re-validation is E.4.4's drift."""
    from squadops.cycles.models import ProjectStateConflictError

    registry = PostgresProjectRegistry(pool)
    await registry.register_project(_registration(), actor="owner")
    commit = "c" * 40

    failed, _ = await registry.record_validation(
        "prj-tally", commit=None, diagnostic="clone: denied", actor="owner", idempotency_key="v-1"
    )
    ready, replayed = await registry.record_validation(
        "prj-tally", commit=commit, diagnostic=None, actor="owner", idempotency_key="v-2"
    )
    again, again_replayed = await registry.record_validation(
        "prj-tally", commit=commit, diagnostic=None, actor="owner", idempotency_key="v-2"
    )
    with pytest.raises(ProjectStateConflictError, match="READY"):
        await registry.record_validation(
            "prj-tally", commit=commit, diagnostic=None, actor="owner", idempotency_key="v-3"
        )

    assert (failed.lifecycle_status, failed.validation_diagnostic, failed.record_version) == (
        ProjectLifecycleStatus.FAILED_REGISTRATION,
        "clone: denied",
        2,
    )
    assert (ready.lifecycle_status, ready.record_version, replayed) == (
        ProjectLifecycleStatus.READY,
        3,
        False,
    )
    assert (ready.development_baseline_commit, ready.integrated_upstream_commit) == (commit, commit)
    assert ready.validation_diagnostic is None
    assert (again, again_replayed) == (ready, True)
    async with pool.acquire() as conn:
        events = await conn.fetch(
            "SELECT operation, record_version, detail FROM project_record_events "
            "WHERE project_id = 'prj-tally' ORDER BY record_version"
        )
    assert [(e["operation"], e["record_version"]) for e in events] == [
        ("register", 1),
        ("validate", 2),
        ("validate", 3),
    ]
    assert events[2]["detail"] == {"from": "FAILED_REGISTRATION", "commit": commit}


async def test_configuration_revisions_follow_one_another_and_read_back_as_recorded(pool):
    """E.4.2, §B.5. Bugs caught: a revision overwritten instead of added; a recording against a
    stale revision accepted, losing the other; a document that doesn't read back as written."""
    import dataclasses

    from squadops.cycles.models import (
        DevelopmentConfigurationNotFoundError,
        StaleConfigurationRevisionError,
    )
    from squadops.projects.development_configuration import parse_configuration

    registry = PostgresProjectRegistry(pool)
    await registry.register_project(_registration(), actor="owner")
    with pytest.raises(DevelopmentConfigurationNotFoundError):
        await registry.get_development_configuration("prj-tally")
    first = dataclasses.replace(
        parse_configuration(recorded_configuration()), project_id="prj-tally", revision=1
    )

    _, replayed = await registry.record_development_configuration(
        first, actor="owner", idempotency_key="c-1", request_hash="h1"
    )
    again, again_replayed = await registry.record_development_configuration(
        first, actor="owner", idempotency_key="c-1", request_hash="h1"
    )
    with pytest.raises(StaleConfigurationRevisionError, match="revision 1"):
        await registry.record_development_configuration(
            first, actor="owner", idempotency_key="c-2", request_hash="h2"
        )
    second = dataclasses.replace(first, revision=2, target="python3")
    await registry.record_development_configuration(
        second, actor="owner", idempotency_key="c-3", request_hash="h3"
    )

    assert (replayed, again_replayed, again) == (False, True, first)
    assert await registry.get_development_configuration("prj-tally") == second
    assert await registry.get_development_configuration("prj-tally", 1) == first
    project = await registry.get_project("prj-tally")
    assert (project.development_configuration_revision, project.record_version) == (2, 3)


def recorded_configuration():
    from tests.fixtures.shared_contract.repository import recorded

    return recorded("development_configuration", "valid")


async def test_mappings_resolve_both_ways_and_baselines_read_back(pool):
    """Contract 3's mapping, and FR-20's record. Bugs caught: a seed recorded twice making two
    rows; a mapping that can't be read back by commit, revision or tree; a baseline replay that
    captures again; the evidence lost or mixed into the document."""
    from squadops.cycles.models import InheritedBaselineNotFoundError
    from squadops.projects.baseline import parse_baseline
    from squadops.projects.workspaces import SourceMapping
    from tests.fixtures.shared_contract.repository import recorded

    registry = PostgresProjectRegistry(pool)
    await registry.register_project(_registration(), actor="owner")
    entry = recorded("workspace_commit_mapping", "valid")["entries"][1]
    mapping = SourceMapping(
        project_id="prj-tally",
        workspace_id="baseline-prj-tally-962858eb0e32",
        direction="seeded",
        commit=entry["commit"],
        sandbox_revision_id=entry["sandbox_revision_id"],
        tree_identity=entry["tree_identity"],
    )

    await registry.record_source_mapping(mapping)
    await registry.record_source_mapping(mapping)
    mappings = await registry.source_mappings("prj-tally")

    assert mappings == [mapping]
    by = {m.commit: m for m in mappings}, {m.sandbox_revision_id: m for m in mappings}
    assert by[0][entry["commit"]].sandbox_revision_id == entry["sandbox_revision_id"]
    assert by[1][entry["sandbox_revision_id"]].commit == entry["commit"]

    with pytest.raises(InheritedBaselineNotFoundError):
        await registry.get_inherited_baseline("prj-tally")
    baseline = parse_baseline(recorded("inherited_baseline", "valid"))
    baseline = dataclasses.replace(baseline, project_id="prj-tally")
    _, replayed = await registry.record_inherited_baseline(
        baseline, actor="owner", idempotency_key="b-1", request_hash="h"
    )
    again, again_replayed = await registry.record_inherited_baseline(
        baseline, actor="owner", idempotency_key="b-1", request_hash="h"
    )

    assert (replayed, again_replayed, again) == (False, True, baseline)
    assert await registry.get_inherited_baseline("prj-tally") == baseline
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM project_inherited_baselines") == 1


async def test_a_cycles_pinned_source_context_round_trips_and_a_sample_apps_stays_null(pool):
    """Contract 1's persistence (§D.3: persisted before dispatch). Bugs caught: the context
    dropped by the cycle registry's insert or read; a sample application's cycle given one."""
    import uuid
    from datetime import UTC, datetime

    from adapters.cycles.postgres_cycle_registry import PostgresCycleRegistry
    from adapters.persistence.transient import TransientRetry
    from squadops.cycles.models import Cycle, TaskFlowPolicy
    from squadops.projects.source_context import parse_source_context
    from tests.fixtures.shared_contract.repository import recorded

    cycles = PostgresCycleRegistry(pool=pool, retry=TransientRetry(attempts=1, backoff_seconds=0.0))
    context = parse_source_context(recorded("project_source_context", "valid"))

    def cycle(source_context):
        return Cycle(
            cycle_id=f"cyc_{uuid.uuid4().hex[:12]}",
            project_id=REFERENCED,
            created_at=datetime.now(UTC),
            created_by="it",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            source_context=source_context,
        )

    external, sample = cycle(context), cycle(None)
    await cycles.create_cycle(external)
    await cycles.create_cycle(sample)

    assert (await cycles.get_cycle(external.cycle_id)).source_context == context
    assert (await cycles.get_cycle(sample.cycle_id)).source_context is None


async def test_a_contribution_is_recorded_once_and_its_key_names_one_run(pool):
    """FR-06's record (E.4.3). Bugs caught:
    - a retried contribution making a second row, or bumping the record version again;
    - a key reused for another run accepted;
    - a review request recorded without its branch and URL, which the table refuses."""
    from squadops.cycles.models import RegistrationKeyConflictError
    from squadops.projects.contribution import Contribution

    registry = PostgresProjectRegistry(pool)
    await registry.register_project(_registration(), actor="owner")
    contribution = Contribution(
        project_id="prj-tally",
        cycle_id="cyc_1",
        run_id="run_1",
        commit="a" * 40,
        parent_commit="b" * 40,
        mode="review_request",
        state="pending",
        branch="squadops/cyc_1",
        review_url="https://github.com/owner/tally/pull/7",
        contributed_by="owner",
        contributed_at=datetime(2026, 10, 18, tzinfo=UTC),
    )

    _, replayed = await registry.record_contribution(
        contribution, idempotency_key="c-1", request_hash="h"
    )
    again, again_replayed = await registry.record_contribution(
        contribution, idempotency_key="c-2", request_hash="h2"
    )
    with pytest.raises(RegistrationKeyConflictError):
        await registry.record_contribution(
            dataclasses.replace(contribution, run_id="run_2"), idempotency_key="c-1",
            request_hash="other",
        )  # fmt: skip
    with pytest.raises(asyncpg.CheckViolationError):
        await registry.record_contribution(
            dataclasses.replace(contribution, run_id="run_3", review_url=None),
            idempotency_key="c-3",
            request_hash="h3",
        )

    assert (replayed, again_replayed, again) == (False, True, contribution)
    assert await registry.contributions("prj-tally") == [contribution]
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM project_record_events WHERE operation = 'contribute'"
            )
            == 1
        )
