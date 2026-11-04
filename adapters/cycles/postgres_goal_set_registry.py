"""A Project's goal-set revisions, on Postgres (SIP-0115 §4, slice 1, #2884; migration 2100).

Chosen by the Project registry's selector, beside the records its rows reference: ``postgres``
writes, and ``postgres_read_only`` (the rollback, SIP-0112 R3) and ``config`` read only, as the
Project registry's own writes are gated under them. Under ``config`` no Project has a record
here, so none has a goal set, and a write is refused rather than meeting the foreign key.
"""

from __future__ import annotations

from dataclasses import replace

import asyncpg

from squadops.cycles.models import (
    GoalSetNotFoundError,
    ProjectNotFoundError,
    ProjectRegistryReadOnlyError,
    RegistrationKeyConflictError,
    StaleGoalSetRevisionError,
)
from squadops.ports.projects.goal_sets import GoalSetRegistryPort
from squadops.projects.goal_set import GoalSetRevision, parse_change, parse_goal_set
from squadops.projects.goal_set_assessments import (
    Assessment,
    Cause,
    Reading,
    parse_evidence,
)

#: ``change`` (migration 2101, slice 3): the action that wrote the revision, or NULL for a whole
#: document.
_COLUMNS = "project_id, revision, document, reason, source_ref, author, created_at, change"
#: Two-key advisory locks, class 115 (SIP-0115): a Project's writes, and a key's, each serialized
#: apart from SIP-0112's class 112 and the migrations' single-key lock.
_LOCK_PROJECT = 115
_LOCK_KEY = 1150
#: An assessment's sequence (migration 2103), apart from the revisions': neither waits on the other.
_LOCK_ASSESSMENTS = 1151
_ASSESSMENT_COLUMNS = (
    "project_id, sequence, campaign_id, expected_result, goals_revision, reading, cause, issue, "
    "evidence, supersedes, log_seq, reason, source_ref, author, created_at"
)


def _row_to_revision(row: asyncpg.Record) -> GoalSetRevision:
    return GoalSetRevision(
        project_id=row["project_id"],
        revision=row["revision"],
        goal_set=parse_goal_set(row["document"]),
        author=row["author"],
        reason=row["reason"],
        created_at=row["created_at"],
        source_ref=row["source_ref"],
        change=parse_change(row["change"]) if row["change"] is not None else None,
    )


def _row_to_assessment(row: asyncpg.Record) -> Assessment:
    return Assessment(
        project_id=row["project_id"],
        campaign_id=row["campaign_id"],
        expected_result=row["expected_result"],
        goals_revision=row["goals_revision"],
        reading=Reading(row["reading"]),
        evidence=parse_evidence(row["evidence"]),
        reason=row["reason"],
        author=row["author"],
        created_at=row["created_at"],
        source_ref=row["source_ref"],
        cause=Cause(row["cause"]) if row["cause"] is not None else None,
        issue=row["issue"],
        supersedes=tuple(row["supersedes"]),
        log_seq=row["log_seq"],
        sequence=row["sequence"],
    )


class PostgresGoalSetRegistry(GoalSetRegistryPort):
    def __init__(self, pool: asyncpg.Pool, *, writable: bool = True) -> None:
        self._pool = pool
        self._writable = writable

    async def record_revision(
        self, revision: GoalSetRevision, *, idempotency_key: str, request_hash: str
    ) -> tuple[GoalSetRevision, bool]:
        """One transaction, under the key's and then the Project's advisory lock: a retry racing
        its original replays, and two writers on one Project can't both take the same revision."""
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off: goal sets stay readable, and none "
                "is written until the gate opens"
            )
        project_id = revision.project_id
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock($1, hashtext($2))", _LOCK_KEY, idempotency_key
            )
            await conn.execute(
                "SELECT pg_advisory_xact_lock($1, hashtext($2))", _LOCK_PROJECT, project_id
            )
            prior = await conn.fetchrow(
                f"SELECT {_COLUMNS}, request_hash FROM project_goal_set_revisions "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None:
                if prior["request_hash"] != request_hash or prior["project_id"] != project_id:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {idempotency_key!r} wrote different content: a retry "
                        "repeats its request exactly"
                    )
                return _row_to_revision(prior), True
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM project_records WHERE project_id = $1)", project_id
            ):
                raise ProjectNotFoundError(f"Project not found: {project_id}")
            latest = await conn.fetchval(
                "SELECT COALESCE(MAX(revision), 0) FROM project_goal_set_revisions "
                "WHERE project_id = $1",
                project_id,
            )
            if revision.revision != latest + 1:
                raise StaleGoalSetRevisionError(
                    f"Project {project_id}'s goal set is at revision {latest}; revision "
                    f"{revision.revision} doesn't follow it"
                )
            await conn.execute(
                "INSERT INTO project_goal_set_revisions (project_id, revision, document, reason, "
                "source_ref, author, created_at, idempotency_key, request_hash, change) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)",
                project_id,
                revision.revision,
                revision.goal_set.to_document(),
                revision.reason,
                revision.source_ref,
                revision.author,
                revision.created_at,
                idempotency_key,
                request_hash,
                revision.change.to_document() if revision.change is not None else None,
            )
        return revision, False

    async def revision_under_key(
        self, idempotency_key: str, request_hash: str
    ) -> GoalSetRevision | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_COLUMNS} FROM project_goal_set_revisions "
                "WHERE idempotency_key = $1 AND request_hash = $2",
                idempotency_key,
                request_hash,
            )
        return _row_to_revision(row) if row is not None else None

    async def get_revision(self, project_id: str, revision: int | None = None) -> GoalSetRevision:
        async with self._pool.acquire() as conn:
            if revision is None:
                row = await conn.fetchrow(
                    f"SELECT {_COLUMNS} FROM project_goal_set_revisions WHERE project_id = $1 "
                    "ORDER BY revision DESC LIMIT 1",
                    project_id,
                )
            else:
                row = await conn.fetchrow(
                    f"SELECT {_COLUMNS} FROM project_goal_set_revisions "
                    "WHERE project_id = $1 AND revision = $2",
                    project_id,
                    revision,
                )
        if row is None:
            raise GoalSetNotFoundError(
                f"Project {project_id} has no goal set"
                + (f" revision {revision}" if revision is not None else "")
            )
        return _row_to_revision(row)

    async def list_revisions(self, project_id: str) -> list[GoalSetRevision]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_COLUMNS} FROM project_goal_set_revisions WHERE project_id = $1 "
                "ORDER BY revision DESC",
                project_id,
            )
        return [_row_to_revision(row) for row in rows]

    async def record_assessment(
        self, assessment: Assessment, *, idempotency_key: str, request_hash: str
    ) -> tuple[Assessment, bool]:
        """One transaction, under the key's and then the goal set's advisory lock, as a revision
        is recorded: a retry racing its original replays, and two writers can't take a sequence."""
        if not self._writable:
            raise ProjectRegistryReadOnlyError(
                "the project registry's writes are gated off: assessments stay readable, and none "
                "is written until the gate opens"
            )
        project_id = assessment.project_id
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock($1, hashtext($2))", _LOCK_KEY, idempotency_key
            )
            await conn.execute(
                "SELECT pg_advisory_xact_lock($1, hashtext($2))", _LOCK_ASSESSMENTS, project_id
            )
            prior = await conn.fetchrow(
                f"SELECT {_ASSESSMENT_COLUMNS}, request_hash FROM project_goal_set_assessments "
                "WHERE idempotency_key = $1",
                idempotency_key,
            )
            if prior is not None:
                if prior["request_hash"] != request_hash or prior["project_id"] != project_id:
                    raise RegistrationKeyConflictError(
                        f"idempotency key {idempotency_key!r} wrote different content: a retry "
                        "repeats its request exactly"
                    )
                return _row_to_assessment(prior), True
            sequence = 1 + await conn.fetchval(
                "SELECT COALESCE(MAX(sequence), 0) FROM project_goal_set_assessments "
                "WHERE project_id = $1",
                project_id,
            )
            await conn.execute(
                "INSERT INTO project_goal_set_assessments (project_id, sequence, campaign_id, "
                "expected_result, goals_revision, reading, cause, issue, evidence, supersedes, "
                "log_seq, reason, source_ref, author, created_at, idempotency_key, request_hash) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, "
                "$17)",
                project_id,
                sequence,
                assessment.campaign_id,
                assessment.expected_result,
                assessment.goals_revision,
                assessment.reading.value,
                assessment.cause.value if assessment.cause is not None else None,
                assessment.issue,
                assessment.evidence.to_document(),
                list(assessment.supersedes),
                assessment.log_seq,
                assessment.reason,
                assessment.source_ref,
                assessment.author,
                assessment.created_at,
                idempotency_key,
                request_hash,
            )
        return replace(assessment, sequence=sequence), False

    async def assessment_under_key(
        self, idempotency_key: str, request_hash: str
    ) -> Assessment | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_ASSESSMENT_COLUMNS} FROM project_goal_set_assessments "
                "WHERE idempotency_key = $1 AND request_hash = $2",
                idempotency_key,
                request_hash,
            )
        return _row_to_assessment(row) if row is not None else None

    async def list_assessments(
        self,
        project_id: str,
        *,
        campaign_id: str | None = None,
        expected_result: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Assessment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_ASSESSMENT_COLUMNS} FROM project_goal_set_assessments "
                "WHERE project_id = $1 AND ($2::text IS NULL OR campaign_id = $2) "
                "AND ($3::text IS NULL OR expected_result = $3) "
                "ORDER BY sequence LIMIT $4 OFFSET $5",
                project_id,
                campaign_id,
                expected_result,
                limit,
                offset,
            )
        return [_row_to_assessment(row) for row in rows]
