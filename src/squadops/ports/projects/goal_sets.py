"""GoalSetRegistryPort: a Project's goal-set revisions (SIP-0115 §4, slice 1, #2884).

Its own port, beside the Project registry rather than in it: SIP-0112 owns the Project Record,
and the goal set "adds nothing to the Project Record itself" (SIP-0115's intake check). The
Project's existence is the Project registry's to answer; this store holds the revisions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.projects.goal_set import GoalSetRevision


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
    async def get_revision(self, project_id: str, revision: int | None = None) -> GoalSetRevision:
        """``revision`` of the Project's goal set, or its latest: the active goal set (Q44).

        Raises:
            GoalSetNotFoundError: None is written, or not that revision.
        """

    @abstractmethod
    async def list_revisions(self, project_id: str) -> list[GoalSetRevision]:
        """Every revision of the Project's goal set, newest first; empty when none is written."""
