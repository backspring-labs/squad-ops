"""The writable Project registry, on Postgres (SIP-0112 FR-03, E.4.1, #2408).

Every read goes to the database: there are a handful of Projects, every reader is in the runtime
API, and a cache would only add the invalidation that lets a newly registered Project go unseen
(IR-8). ``config/projects.yaml`` reaches it once per entry, through the seed log.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import asyncpg

from squadops.cycles.models import (
    DerivedProfileNotFoundError,
    DevelopmentConfigurationNotFoundError,
    InheritedBaselineNotFoundError,
    Project,
    ProjectIdTakenError,
    ProjectNotFoundError,
    ProjectRegistryReadOnlyError,
    ProjectStateConflictError,
    RegistrationKeyConflictError,
    StaleConfigurationRevisionError,
)
from squadops.ports.cycles.project_registry import ProjectRegistryPort
from squadops.projects.baseline import InheritedBaseline, parse_baseline
from squadops.projects.contribution import Contribution
from squadops.projects.derived_profile import DerivedProfile, parse_profile
from squadops.projects.development_configuration import (
    DevelopmentConfiguration,
    parse_configuration,
)
from squadops.projects.initialization import ProjectInitialization
from squadops.projects.models import (
    ProjectLifecycleStatus,
    ProjectOwnership,
    ProjectProvenance,
    ProjectSource,
)
from squadops.projects.registration import ProjectRegistration

_COLUMNS = (
    "project_id, name, description, tags, prd_path, lifecycle_status, record_version, "
    "repo_uri, base_ref, contribution_mode, repository_root, ownership, "
    "development_configuration_revision, created_at, development_baseline_commit, "
    "integrated_upstream_commit, validation_diagnostic"
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
        development_baseline_commit=row["development_baseline_commit"],
        integrated_upstream_commit=row["integrated_upstream_commit"],
        validation_diagnostic=row["validation_diagnostic"],
    )


_CONTRIBUTION_COLUMNS = (
    "project_id, cycle_id, run_id, commit, parent_commit, mode, state, branch, review_url, "
    "contributed_by, contributed_at, integrated_commit"
)


_INITIALIZATION_COLUMNS = (
    "project_id, commit, branch, stack, manifest_digest, manifest, files, initialized_by, "
    "initialized_at"
)


def _row_to_initialization(row: asyncpg.Record) -> ProjectInitialization:
    return ProjectInitialization(**{**dict(row), "files": tuple(row["files"])})


def _event_id() -> str:
    return f"pev_{uuid.uuid4().hex[:12]}"


class PostgresProjectRegistry(ProjectRegistryPort):
    """The writable registry: authoritative for every reader once selected (FR-03).

    ``writable=False`` is the write gate closed (R3's rollback, provider ``postgres_read_only``):
    every Project stays readable, and a registration is refused rather than written."""

    def __init__(self, pool: asyncpg.Pool, *, writable: bool = True) -> None:
        self._pool = pool
        self._writable = writable

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

    # --- registration (FR-02, E.4.1) ---

    async def register_project(
        self, registration: ProjectRegistration, *, actor: str
    ) -> tuple[Project, bool]:
        """One transaction: the record at REGISTERING, version 1, and its event carrying the
        idempotency key. Registrations under one key are serialized by an advisory lock, so a
        retry racing its original replays rather than conflicts."""
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only): every "
                "Project stays readable, and none is registered until the gate opens"
            )
        key, digest = registration.idempotency_key, registration.request_hash()
        source, ownership = registration.source, registration.ownership
        async with self._pool.acquire() as conn, conn.transaction():
            # Two-key form, class 112 (SIP-0112): apart from the migrations' single-key lock.
            await conn.execute("SELECT pg_advisory_xact_lock(112, hashtext($1))", key)
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash FROM project_record_events "
                "WHERE idempotency_key = $1",
                key,
            )
            if prior is not None:
                if prior["request_hash"] != digest:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {key!r} registered {prior['project_id']} with "
                        "different content: a retry repeats its request exactly"
                    )
                row = await conn.fetchrow(
                    f"SELECT {_COLUMNS} FROM project_records WHERE project_id = $1",
                    prior["project_id"],
                )
                return _row_to_project(row), True
            now = datetime.now(UTC)
            inserted = await conn.fetchval(
                "INSERT INTO project_records (project_id, name, description, tags, prd_path, "
                "lifecycle_status, record_version, provenance, repo_uri, base_ref, "
                "contribution_mode, repository_root, ownership, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, NULL, $5, 1, $6, $7, $8, $9, $10, $11, $12, $12) "
                "ON CONFLICT (project_id) DO NOTHING RETURNING project_id",
                registration.project_id,
                registration.name,
                registration.description,
                list(registration.tags),
                ProjectLifecycleStatus.REGISTERING.value,
                ProjectProvenance.REGISTERED.value,
                source.repo_uri,
                source.base_ref,
                source.contribution_mode,
                source.repository_root,
                {
                    "owner": ownership.owner,
                    "delegated_actions": list(ownership.delegated_actions),
                    "acceptance_policy_ref": ownership.acceptance_policy_ref,
                },
                now,
            )
            if inserted is None:
                raise ProjectIdTakenError(
                    f"Project {registration.project_id} is already registered"
                )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'register', 1, $3, $4, $5, $6, $7)",
                _event_id(),
                registration.project_id,
                actor,
                key,
                digest,
                {"origin": "import"},
                now,
            )
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM project_records WHERE project_id = $1",
                registration.project_id,
            )
        return _row_to_project(row), False

    # --- validation (E.4.2, §B.6) ---

    async def record_validation(
        self,
        project_id: str,
        *,
        commit: str | None,
        diagnostic: str | None,
        actor: str,
        idempotency_key: str,
    ) -> tuple[Project, bool]:
        """One transaction, under the Project's row lock: the status, the commits or the
        diagnostic, the next record version, and the event. A key that recorded this Project's
        validation before replays it, whatever this attempt found."""
        if (commit is None) == (diagnostic is None):
            raise ValueError("a validation records a commit or a diagnostic, never both")
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        detail = {"commit": commit} if commit else {"diagnostic": diagnostic}
        digest = hashlib.sha256(f"validate:{project_id}".encode()).hexdigest()
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT lifecycle_status, record_version, development_baseline_commit "
                "FROM project_records WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash FROM project_record_events "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None:
                if prior["request_hash"] != digest:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {idempotency_key!r} recorded another operation"
                    )
                return await self._read(conn, project_id), True
            status = ProjectLifecycleStatus(row["lifecycle_status"])
            if status == ProjectLifecycleStatus.READY:
                # E.4.4: a READY Project is re-validated to adopt its upstream's commit. A failed
                # fetch is never recorded against it: it stays READY at the baseline it has.
                if commit is None:
                    raise ProjectStateConflictError(
                        f"Project {project_id} is READY: a re-validation records the commit it "
                        "adopts, and a failed one is reported, not recorded"
                    )
                detail["previous"] = row["development_baseline_commit"]
            elif status not in (
                ProjectLifecycleStatus.REGISTERING,
                ProjectLifecycleStatus.FAILED_REGISTRATION,
            ):
                raise ProjectStateConflictError(
                    f"Project {project_id} is {status.value}: a registering, failed or READY "
                    "Project is validated"
                )
            version = row["record_version"] + 1
            now = datetime.now(UTC)
            await conn.execute(
                "UPDATE project_records SET lifecycle_status = $2, record_version = $3, "
                "development_baseline_commit = COALESCE($4, development_baseline_commit), "
                "integrated_upstream_commit = COALESCE($4, integrated_upstream_commit), "
                "validation_diagnostic = $5, updated_at = $6 WHERE project_id = $1",
                project_id,
                (
                    ProjectLifecycleStatus.READY
                    if commit
                    else ProjectLifecycleStatus.FAILED_REGISTRATION
                ).value,
                version,
                commit,
                diagnostic,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'validate', $3, $4, $5, $6, $7, $8)",
                _event_id(),
                project_id,
                version,
                actor,
                idempotency_key,
                digest,
                {"from": status.value, **detail},
                now,
            )
            return await self._read(conn, project_id), False

    # --- the Development Configuration (§B.5, E.4.2) ---

    async def record_development_configuration(
        self,
        configuration: DevelopmentConfiguration,
        *,
        actor: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[DevelopmentConfiguration, bool]:
        """One transaction, under the Project's row lock: the revision's row, the Project's
        current revision and record version, and the event."""
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        project_id = configuration.project_id
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT record_version, development_configuration_revision FROM project_records "
                "WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash, detail FROM project_record_events "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None:
                if prior["request_hash"] != request_hash or prior["project_id"] != project_id:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {idempotency_key!r} recorded different content"
                    )
                return await self._configuration(
                    conn, project_id, prior["detail"]["revision"]
                ), True
            current = row["development_configuration_revision"] or 0
            if configuration.revision != current + 1:
                raise StaleConfigurationRevisionError(
                    f"Project {project_id} is at Development Configuration revision {current}; "
                    f"revision {configuration.revision} doesn't follow it"
                )
            now = datetime.now(UTC)
            version = row["record_version"] + 1
            await conn.execute(
                "INSERT INTO project_development_configurations (project_id, revision, document, "
                "validated_at_commit, recorded_by, recorded_at) VALUES ($1, $2, $3, $4, $5, $6)",
                project_id,
                configuration.revision,
                configuration.to_document(),
                configuration.validated_at_commit,
                actor,
                now,
            )
            await conn.execute(
                "UPDATE project_records SET development_configuration_revision = $2, "
                "record_version = $3, updated_at = $4 WHERE project_id = $1",
                project_id,
                configuration.revision,
                version,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'configure', $3, $4, $5, $6, $7, $8)",
                _event_id(),
                project_id,
                version,
                actor,
                idempotency_key,
                request_hash,
                {
                    "revision": configuration.revision,
                    "at_commit": configuration.validated_at_commit,
                },
                now,
            )
        return configuration, False

    async def get_development_configuration(
        self, project_id: str, revision: int | None = None
    ) -> DevelopmentConfiguration:
        async with self._pool.acquire() as conn:
            if revision is None:
                revision = await conn.fetchval(
                    "SELECT development_configuration_revision FROM project_records "
                    "WHERE project_id = $1",
                    project_id,
                )
                if revision is None:
                    raise DevelopmentConfigurationNotFoundError(
                        f"Project {project_id} has no Development Configuration"
                    )
            return await self._configuration(conn, project_id, revision)

    async def _configuration(
        self, conn, project_id: str, revision: int
    ) -> DevelopmentConfiguration:
        document = await conn.fetchval(
            "SELECT document FROM project_development_configurations "
            "WHERE project_id = $1 AND revision = $2",
            project_id,
            revision,
        )
        if document is None:
            raise DevelopmentConfigurationNotFoundError(
                f"Project {project_id} has no Development Configuration revision {revision}"
            )
        return parse_configuration(document)

    # --- source mappings and the inherited baseline (contract 3, FR-20; E.4.2) ---

    async def record_source_mapping(self, mapping) -> None:
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO project_source_mappings (project_id, workspace_id, direction, commit, "
                "sandbox_revision_id, tree_identity, cycle_id, campaign_id, recorded_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ON CONFLICT DO NOTHING",
                mapping.project_id,
                mapping.workspace_id,
                mapping.direction,
                mapping.commit,
                mapping.sandbox_revision_id,
                mapping.tree_identity,
                mapping.cycle_id,
                mapping.campaign_id,
                datetime.now(UTC),
            )

    async def source_mappings(self, project_id: str, *, workspace_id: str | None = None):
        # deferred (cycle): workspaces imports this module's port at load
        from squadops.projects.workspaces import SourceMapping

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT project_id, workspace_id, direction, commit, sandbox_revision_id, "
                "tree_identity, cycle_id, campaign_id FROM project_source_mappings "
                "WHERE project_id = $1 AND ($2::text IS NULL OR workspace_id = $2) "
                "ORDER BY recorded_at, direction DESC",
                project_id,
                workspace_id,
            )
        return [SourceMapping(**dict(row)) for row in rows]

    async def record_inherited_baseline(
        self,
        baseline: InheritedBaseline,
        *,
        actor: str,
        idempotency_key: str,
        request_hash: str,
        derived_profile: DerivedProfile | None = None,
    ) -> tuple[InheritedBaseline, bool]:
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        project_id = baseline.project_id
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT record_version FROM project_records WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash, detail FROM project_record_events "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None:
                if prior["request_hash"] != request_hash or prior["project_id"] != project_id:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {idempotency_key!r} recorded different content"
                    )
                document = await conn.fetchval(
                    "SELECT document FROM project_inherited_baselines "
                    "WHERE project_id = $1 AND captured_seq = $2",
                    project_id,
                    prior["detail"]["captured_seq"],
                )
                return parse_baseline(document), True
            seq = 1 + (
                await conn.fetchval(
                    "SELECT COALESCE(MAX(captured_seq), 0) FROM project_inherited_baselines "
                    "WHERE project_id = $1",
                    project_id,
                )
            )
            now = datetime.now(UTC)
            version = row["record_version"] + 1
            await conn.execute(
                "INSERT INTO project_inherited_baselines (project_id, captured_seq, commit, "
                "development_configuration_revision, document, evidence, captured_by, "
                "captured_at, derived_profile) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                project_id,
                seq,
                baseline.commit,
                baseline.development_configuration_revision,
                baseline.to_document(),
                baseline.evidence(),
                actor,
                now,
                derived_profile.to_document() if derived_profile is not None else None,
            )
            await conn.execute(
                "UPDATE project_records SET record_version = $2, updated_at = $3 "
                "WHERE project_id = $1",
                project_id,
                version,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'baseline', $3, $4, $5, $6, $7, $8)",
                _event_id(),
                project_id,
                version,
                actor,
                idempotency_key,
                request_hash,
                {"captured_seq": seq, "commit": baseline.commit, "failing": baseline.failing()},
                now,
            )
        return baseline, False

    async def get_inherited_baseline(self, project_id: str) -> InheritedBaseline:
        async with self._pool.acquire() as conn:
            document = await conn.fetchval(
                "SELECT document FROM project_inherited_baselines WHERE project_id = $1 "
                "ORDER BY captured_seq DESC LIMIT 1",
                project_id,
            )
        if document is None:
            raise InheritedBaselineNotFoundError(f"Project {project_id} has no inherited baseline")
        return parse_baseline(document)

    async def get_derived_profile(self, project_id: str) -> DerivedProfile:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT derived_profile FROM project_inherited_baselines WHERE project_id = $1 "
                "ORDER BY captured_seq DESC LIMIT 1",
                project_id,
            )
        if row is None or row["derived_profile"] is None:
            raise DerivedProfileNotFoundError(
                f"Project {project_id}'s latest inherited baseline has no derived profile"
                + ("" if row is not None else ": none is captured")
            )
        return parse_profile(row["derived_profile"])

    # --- contributions (FR-06; E.4.3) ---

    async def record_contribution(
        self, contribution: Contribution, *, idempotency_key: str, request_hash: str
    ) -> tuple[Contribution, bool]:
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        project_id = contribution.project_id
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT record_version FROM project_records WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash, detail FROM project_record_events "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None and (
                prior["request_hash"] != request_hash or prior["project_id"] != project_id
            ):
                raise RegistrationKeyConflictError(
                    f"idempotency key {idempotency_key!r} recorded different content"
                )
            existing = await conn.fetchrow(
                f"SELECT {_CONTRIBUTION_COLUMNS} FROM project_contributions "
                "WHERE project_id = $1 AND cycle_id = $2 AND run_id = $3",
                project_id,
                contribution.cycle_id,
                contribution.run_id,
            )
            if existing is not None:
                return Contribution(**dict(existing)), True
            now = contribution.contributed_at
            version = row["record_version"] + 1
            await conn.execute(
                f"INSERT INTO project_contributions ({_CONTRIBUTION_COLUMNS}) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)",
                project_id,
                contribution.cycle_id,
                contribution.run_id,
                contribution.commit,
                contribution.parent_commit,
                contribution.mode,
                contribution.state,
                contribution.branch,
                contribution.review_url,
                contribution.contributed_by,
                now,
                contribution.integrated_commit,
            )
            await conn.execute(
                "UPDATE project_records SET record_version = $2, updated_at = $3 "
                "WHERE project_id = $1",
                project_id,
                version,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'contribute', $3, $4, $5, $6, $7, $8)",
                _event_id(),
                project_id,
                version,
                contribution.contributed_by,
                idempotency_key,
                request_hash,
                {
                    "cycle_id": contribution.cycle_id,
                    "run_id": contribution.run_id,
                    "commit": contribution.commit,
                    "mode": contribution.mode,
                    "review_url": contribution.review_url,
                },
                now,
            )
        return contribution, False

    async def contributions(self, project_id: str) -> list[Contribution]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_CONTRIBUTION_COLUMNS} FROM project_contributions "
                "WHERE project_id = $1 ORDER BY contributed_at",
                project_id,
            )
        return [Contribution(**dict(r)) for r in rows]

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
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT record_version FROM project_records WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            updated = await conn.fetchrow(
                "UPDATE project_contributions SET state = $4, integrated_commit = $5 "
                "WHERE project_id = $1 AND cycle_id = $2 AND run_id = $3 "
                f"RETURNING {_CONTRIBUTION_COLUMNS}",
                project_id,
                cycle_id,
                run_id,
                state,
                integrated_commit,
            )
            if updated is None:
                raise ProjectNotFoundError(
                    f"Project {project_id} has no contribution from run {run_id} of {cycle_id}"
                )
            now = datetime.now(UTC)
            version = row["record_version"] + 1
            await conn.execute(
                "UPDATE project_records SET record_version = $2, updated_at = $3 "
                "WHERE project_id = $1",
                project_id,
                version,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'contribution_state', $3, $4, NULL, NULL, $5, $6)",
                _event_id(),
                project_id,
                version,
                actor,
                {
                    "cycle_id": cycle_id,
                    "run_id": run_id,
                    "state": state,
                    "integrated_commit": integrated_commit,
                },
                now,
            )
        return Contribution(**dict(updated))

    async def record_sync(
        self, document: dict, *, actor: str, idempotency_key: str, request_hash: str
    ) -> tuple[dict, bool]:
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        project_id = document["project_id"]
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT record_version FROM project_records WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash, detail FROM project_record_events "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None:
                if prior["request_hash"] != request_hash or prior["project_id"] != project_id:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {idempotency_key!r} recorded different content"
                    )
                stored = await conn.fetchval(
                    "SELECT document FROM project_source_syncs "
                    "WHERE project_id = $1 AND synced_seq = $2",
                    project_id,
                    prior["detail"]["synced_seq"],
                )
                return stored, True
            seq = 1 + (
                await conn.fetchval(
                    "SELECT COALESCE(MAX(synced_seq), 0) FROM project_source_syncs "
                    "WHERE project_id = $1",
                    project_id,
                )
            )
            now = datetime.now(UTC)
            version = row["record_version"] + 1
            await conn.execute(
                "INSERT INTO project_source_syncs (project_id, synced_seq, baseline_commit, "
                "upstream_commit, document, synced_by, synced_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                project_id,
                seq,
                document["baseline_commit"],
                document["upstream_commit"],
                document,
                actor,
                now,
            )
            await conn.execute(
                "UPDATE project_records SET record_version = $2, updated_at = $3 "
                "WHERE project_id = $1",
                project_id,
                version,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'sync', $3, $4, $5, $6, $7, $8)",
                _event_id(),
                project_id,
                version,
                actor,
                idempotency_key,
                request_hash,
                {
                    "synced_seq": seq,
                    "upstream_commit": document["upstream_commit"],
                    "relevant": (document.get("drift") or {}).get("relevant", []),
                },
                now,
            )
        return document, False

    async def source_syncs(self, project_id: str) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT document FROM project_source_syncs WHERE project_id = $1 "
                "ORDER BY synced_seq",
                project_id,
            )
        return [r["document"] for r in rows]

    async def record_initialization(
        self, initialization: ProjectInitialization, *, idempotency_key: str, request_hash: str
    ) -> tuple[ProjectInitialization, bool]:
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off (postgres_read_only)"
            )
        project_id = initialization.project_id
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT record_version FROM project_records WHERE project_id = $1 FOR UPDATE",
                project_id,
            )
            if row is None:
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            prior = await conn.fetchrow(
                "SELECT project_id, request_hash FROM project_record_events "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None and (
                prior["request_hash"] != request_hash or prior["project_id"] != project_id
            ):
                raise RegistrationKeyConflictError(
                    f"idempotency key {idempotency_key!r} recorded different content"
                )
            existing = await conn.fetchrow(
                f"SELECT {_INITIALIZATION_COLUMNS} FROM project_initializations "
                "WHERE project_id = $1",
                project_id,
            )
            if existing is not None:
                return _row_to_initialization(existing), True
            now = initialization.initialized_at
            version = row["record_version"] + 1
            await conn.execute(
                f"INSERT INTO project_initializations ({_INITIALIZATION_COLUMNS}) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                project_id,
                initialization.commit,
                initialization.branch,
                initialization.stack,
                initialization.manifest_digest,
                initialization.manifest,
                list(initialization.files),
                initialization.initialized_by,
                now,
            )
            await conn.execute(
                "UPDATE project_records SET record_version = $2, updated_at = $3 "
                "WHERE project_id = $1",
                project_id,
                version,
                now,
            )
            await conn.execute(
                "INSERT INTO project_record_events (event_id, project_id, operation, "
                "record_version, actor, idempotency_key, request_hash, detail, recorded_at) "
                "VALUES ($1, $2, 'initialize', $3, $4, $5, $6, $7, $8)",
                _event_id(),
                project_id,
                version,
                initialization.initialized_by,
                idempotency_key,
                request_hash,
                {
                    "commit": initialization.commit,
                    "stack": initialization.stack,
                    "manifest_digest": initialization.manifest_digest,
                },
                now,
            )
        return initialization, False

    async def get_initialization(self, project_id: str) -> ProjectInitialization | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_INITIALIZATION_COLUMNS} FROM project_initializations "
                "WHERE project_id = $1",
                project_id,
            )
        return _row_to_initialization(row) if row is not None else None

    async def _read(self, conn, project_id: str) -> Project:
        row = await conn.fetchrow(
            f"SELECT {_COLUMNS} FROM project_records WHERE project_id = $1", project_id
        )
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
