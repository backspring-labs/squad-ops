"""GoalSetRegistryPort: a Project's goal-set revisions (SIP-0115 §4, slice 1, #2884).

Its own port, beside the Project registry rather than in it: SIP-0112 owns the Project Record,
and the goal set "adds nothing to the Project Record itself" (SIP-0115's intake check). The
Project's existence is the Project registry's to answer; this store holds the revisions, and the
operator's assessments of them (§5.7, slice 5, #2888), which are appended beside the revisions and are
not one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.projects.goal_set import GoalSetRevision
from squadops.projects.goal_set_assessments import Assessment


class GoalSetRegistryPort(ABC):
    @abstractmethod
    async def record_revision(
        self, revision: GoalSetRevision, *, idempotency_key: str, request_hash: str
    ) -> tuple[GoalSetRevision, bool]:
        """Record ``revision`` as its Project's next goal-set revision, which must follow the
        latest one (1 for the first). Returns it and whether this replayed an earlier write under
        the same key: the stored revision, as it was first written.

        Raises:
            ProjectRegistryReadOnlyError: The store refuses writes.
            StaleGoalSetRevisionError: Its revision doesn't follow the latest one.
            RegistrationKeyConflictError: The key wrote different content.
        """

    @abstractmethod
    async def revision_under_key(
        self, idempotency_key: str, request_hash: str
    ) -> GoalSetRevision | None:
        """The revision ``idempotency_key`` wrote for this request, as it was first written, or
        ``None``: nothing written under it, or another request was (``record_revision`` refuses
        that). A retry's answer, read before anything that may have changed since the write."""

    @abstractmethod
    async def get_revision(self, project_id: str, revision: int | None = None) -> GoalSetRevision:
        """``revision`` of the Project's goal set, or its latest: the active goal set (Q44).

        Raises:
            GoalSetNotFoundError: None is written, or not that revision.
        """

    @abstractmethod
    async def list_revisions(self, project_id: str) -> list[GoalSetRevision]:
        """Every revision of the Project's goal set, newest first; empty when none is written."""

    @abstractmethod
    async def record_assessment(
        self, assessment: Assessment, *, idempotency_key: str, request_hash: str
    ) -> tuple[Assessment, bool]:
        """Append ``assessment`` as the goal set's next in ``sequence``, which the store assigns
        (§5.7). Returns it and whether this replayed an earlier write under the same key: the
        stored assessment, as it was first written.

        Raises:
            ProjectRegistryReadOnlyError: The store refuses writes.
            RegistrationKeyConflictError: The key wrote different content.
        """

    @abstractmethod
    async def list_assessments(
        self,
        project_id: str,
        *,
        campaign_id: str | None = None,
        expected_result: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Assessment]:
        """The Project's assessments, in sequence, narrowed to a Campaign, an expected result or
        both before ``limit`` and ``offset`` apply; ``limit=None`` is every one."""
