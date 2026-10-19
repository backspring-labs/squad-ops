"""The typed memory records' store, in memory and in Postgres (SIP-0110 Appendix A; #2177).

Postgres keeps three tables (``1780_memory_records.sql``): the record's identity, its revisions (each
the revision's whole document, keyed by number) and its status changes. Append-only. The pool's
codecs carry JSONB as Python values (``adapters.persistence.pool``).
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from squadops.memory.records import (
    MemoryRecord,
    RecordKind,
    RecordScope,
    RecordStatus,
    Revision,
    StatusChange,
    revision_document,
    revision_from_document,
)
from squadops.ports.memory.records import MemoryRecordsPort, RecordConflict


class InMemoryMemoryRecords(MemoryRecordsPort):
    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}

    async def create(self, record: MemoryRecord) -> None:
        if record.record_id in self._records:
            raise RecordConflict(f"{record.record_id} exists")
        self._records[record.record_id] = record

    async def append_revision(self, record_id: str, revision: Revision) -> None:
        record = self._records[record_id]
        if revision.number != record.current.number + 1:
            raise RecordConflict(
                f"{record_id}'s next revision is {record.current.number + 1}, not {revision.number}"
            )
        self._records[record_id] = replace(record, revisions=(*record.revisions, revision))

    async def append_status(self, record_id: str, change: StatusChange) -> None:
        record = self._records[record_id]
        self._records[record_id] = replace(record, status_changes=(*record.status_changes, change))

    async def get(self, record_id: str) -> MemoryRecord | None:
        return self._records.get(record_id)

    async def list_project(self, project_id: str) -> list[MemoryRecord]:
        return [r for r in self._records.values() if r.project_id == project_id]

    async def list_owned(self, owner_id: str) -> list[MemoryRecord]:
        return [
            r
            for r in self._records.values()
            if r.owner_id == owner_id and r.scope == RecordScope.USER
        ]

    async def search_notes(
        self, *, owner_id: str, project_id: str | None, text: str
    ) -> list[MemoryRecord]:
        # Postgres's full-text rank, approximated: the words a note shares with the turn.
        words = set(_WORD.findall(text.lower()))
        notes = [
            r
            for r in self._records.values()
            if r.kind == RecordKind.NOTE
            and r.status == RecordStatus.ACTIVE
            and (
                (r.scope == RecordScope.USER and r.owner_id == owner_id)
                or (
                    project_id is not None
                    and r.scope == RecordScope.PROJECT
                    and r.project_id == project_id
                )
            )
        ]
        return sorted(
            notes,
            key=lambda r: (
                -len(words & set(_WORD.findall(r.current.body.lower()))),
                -r.current.created_at.timestamp(),
                r.record_id,
            ),
        )


_WORD = re.compile(r"[a-z0-9]+")


class PostgresMemoryRecords(MemoryRecordsPort):
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def create(self, record: MemoryRecord) -> None:
        import asyncpg

        first = record.revisions[0]
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "INSERT INTO memory_records (record_id, kind, scope, project_id, owner_id, "
                    "created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                    record.record_id,
                    record.kind,
                    record.scope,
                    record.project_id,
                    record.owner_id,
                    first.created_at,
                )
                await self._insert_revision(conn, record.record_id, first)
        except asyncpg.UniqueViolationError as e:
            raise RecordConflict(f"{record.record_id} exists") from e

    @staticmethod
    async def _insert_revision(conn: Any, record_id: str, revision: Revision) -> None:
        await conn.execute(
            "INSERT INTO memory_record_revisions (record_id, number, document, created_at) "
            "VALUES ($1, $2, $3, $4)",
            record_id,
            revision.number,
            revision_document(revision),
            revision.created_at,
        )

    async def append_revision(self, record_id: str, revision: Revision) -> None:
        import asyncpg

        async with self._pool.acquire() as conn, conn.transaction():
            held = await conn.fetchval(
                "SELECT max(number) FROM memory_record_revisions WHERE record_id = $1", record_id
            )
            if held is None:
                raise KeyError(record_id)
            if revision.number != held + 1:
                raise RecordConflict(
                    f"{record_id}'s next revision is {held + 1}, not {revision.number}"
                )
            try:
                await self._insert_revision(conn, record_id, revision)
            except asyncpg.UniqueViolationError as e:
                raise RecordConflict(f"{record_id} revision {revision.number} exists") from e

    async def append_status(self, record_id: str, change: StatusChange) -> None:
        async with self._pool.acquire() as conn:
            if not await conn.fetchval(
                "SELECT 1 FROM memory_records WHERE record_id = $1", record_id
            ):
                raise KeyError(record_id)
            await conn.execute(
                "INSERT INTO memory_record_status_changes (record_id, status, changed_by, "
                "changed_at, why) VALUES ($1, $2, $3, $4, $5)",
                record_id,
                change.status,
                change.by,
                change.at,
                change.why,
            )

    async def _read(self, conn: Any, rows: list[Any]) -> list[MemoryRecord]:
        ids = [row["record_id"] for row in rows]
        if not ids:
            return []
        revisions = await conn.fetch(
            "SELECT record_id, document FROM memory_record_revisions "
            "WHERE record_id = ANY($1::text[]) ORDER BY record_id, number",
            ids,
        )
        changes = await conn.fetch(
            "SELECT record_id, status, changed_by, changed_at, why "
            "FROM memory_record_status_changes WHERE record_id = ANY($1::text[]) "
            "ORDER BY record_id, seq",
            ids,
        )
        by_revision: dict[str, list[Revision]] = {i: [] for i in ids}
        for r in revisions:
            by_revision[r["record_id"]].append(revision_from_document(r["document"]))
        by_change: dict[str, list[StatusChange]] = {i: [] for i in ids}
        for c in changes:
            by_change[c["record_id"]].append(
                StatusChange(c["status"], c["changed_by"], c["changed_at"], c["why"])
            )
        return [
            MemoryRecord(
                record_id=row["record_id"],
                kind=row["kind"],
                scope=row["scope"],
                project_id=row["project_id"],
                owner_id=row["owner_id"],
                revisions=tuple(by_revision[row["record_id"]]),
                status_changes=tuple(by_change[row["record_id"]]),
            )
            for row in rows
        ]

    _COLUMNS = "record_id, kind, scope, project_id, owner_id"

    async def get(self, record_id: str) -> MemoryRecord | None:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {self._COLUMNS} FROM memory_records WHERE record_id = $1", record_id
            )
            found = await self._read(conn, list(rows))
        return found[0] if found else None

    async def list_project(self, project_id: str) -> list[MemoryRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {self._COLUMNS} FROM memory_records WHERE project_id = $1 "
                "ORDER BY created_at, record_id",
                project_id,
            )
            return await self._read(conn, list(rows))

    async def list_owned(self, owner_id: str) -> list[MemoryRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {self._COLUMNS} FROM memory_records WHERE owner_id = $1 AND scope = $2 "
                "ORDER BY created_at, record_id",
                owner_id,
                RecordScope.USER,
            )
            return await self._read(conn, list(rows))

    async def search_notes(
        self, *, owner_id: str, project_id: str | None, text: str
    ) -> list[MemoryRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_SEARCH_NOTES, owner_id, project_id, text)
            return await self._read(conn, list(rows))


#: §A.3.10: the notes in scope with their current revision and status, filtered in Postgres before the
#: rank orders them. ``plainto_tsquery`` takes the turn as words, never as query syntax.
_SEARCH_NOTES = f"""
WITH latest_revision AS (
    SELECT DISTINCT ON (record_id) record_id, document, created_at
    FROM memory_record_revisions ORDER BY record_id, number DESC
), latest_status AS (
    SELECT DISTINCT ON (record_id) record_id, status
    FROM memory_record_status_changes ORDER BY record_id, seq DESC
)
SELECT r.record_id, r.kind, r.scope, r.project_id, r.owner_id
FROM memory_records r
JOIN latest_revision c ON c.record_id = r.record_id
LEFT JOIN latest_status s ON s.record_id = r.record_id
WHERE r.kind = '{RecordKind.NOTE}'
  AND COALESCE(s.status, '{RecordStatus.ACTIVE}') = '{RecordStatus.ACTIVE}'
  AND ((r.scope = '{RecordScope.USER}' AND r.owner_id = $1)
       OR ($2::text IS NOT NULL AND r.scope = '{RecordScope.PROJECT}' AND r.project_id = $2))
ORDER BY ts_rank(to_tsvector('english', c.document->>'body'), plainto_tsquery('english', $3)) DESC,
         c.created_at DESC, r.record_id
"""


def create_memory_records(provider: str, **kwargs: Any) -> MemoryRecordsPort:
    """The records' store for ``provider``, the cycle registry's (``memory`` or ``postgres``).
    Required: an unknown or missing name is refused, never defaulted (#1568)."""
    if provider == "memory":
        return InMemoryMemoryRecords()
    if provider == "postgres":
        return PostgresMemoryRecords(pool=kwargs["pool"])
    raise ValueError(f"unknown memory records provider {provider!r}")
