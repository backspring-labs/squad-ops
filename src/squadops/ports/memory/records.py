"""The typed memory records' store (SIP-0110 Appendix A, §A.3.2–§A.3.4; #2177).

Beside Cross-Cycle Memory's own store, in Postgres with an in-memory adapter for tests, selected as
the cycle registry is. Append-only: a record is created once, and then only gains revisions and
status changes. Nothing stored is rewritten (§A.3.8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.memory.records import MemoryRecord, Revision, StatusChange


class RecordConflict(ValueError):
    """A write that lost a race: a record id already taken, or a revision whose number isn't the
    next one. The caller re-reads and decides; nothing was written."""


class MemoryRecordsPort(ABC):
    @abstractmethod
    async def create(self, record: MemoryRecord) -> None:
        """Store a new record with its first revision. Raises ``RecordConflict`` when its id is
        taken."""

    @abstractmethod
    async def append_revision(self, record_id: str, revision: Revision) -> None:
        """Store ``revision`` as the record's next. Raises ``KeyError`` for a record the store
        doesn't hold, and ``RecordConflict`` when its number isn't the next one."""

    @abstractmethod
    async def append_status(self, record_id: str, change: StatusChange) -> None:
        """Store a status change. Raises ``KeyError`` for a record the store doesn't hold."""

    @abstractmethod
    async def get(self, record_id: str) -> MemoryRecord | None:
        """A record with every revision and status change, or ``None``."""

    @abstractmethod
    async def list_project(self, project_id: str) -> list[MemoryRecord]:
        """A project's records, every status, oldest first."""

    @abstractmethod
    async def list_owned(self, owner_id: str) -> list[MemoryRecord]:
        """The user-private records ``owner_id`` holds, every status, oldest first."""
