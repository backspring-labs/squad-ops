"""A chat turn's context assembly (SIP-0110 Appendix A §3.6; #2180 stage A), in the runtime API, which owns the
records' store and the recall policy (SIP-0110 §0.8). The rules that choose and bound what a turn holds are the
memory domain's (``squadops.memory.chat``); this reads the stores they choose from, and records the exposure."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from squadops.auth.models import Scope
from squadops.memory.chat import (
    CHAT_SECTIONS,
    ChatExposure,
    ChatLimits,
    LessonsLoaded,
    Loaded,
    asks_about_lessons,
    chat_context,
)
from squadops.memory.context import (
    ChatTurn,
    ContextBundle,
    ContextRequest,
    Disposition,
    Need,
    ProjectBound,
    Section,
    SectionKind,
)
from squadops.ports.memory.context_assembly import ContextAssemblyPort

logger = logging.getLogger(__name__)


class ChatContextAssembly(ContextAssemblyPort):
    """The context-assembly port for a chat turn (§3.6), in the runtime API, which owns the store and the
    recall policy. Three reads: the person's own records, the bound project's, and the notes ranked for
    the turn (§3.10: scope and status filtered in Postgres first, then full-text match and recency). A
    fourth when a bound turn asks about lessons and its person holds ``memory:read``: the project's
    lessons, approvals and exposures, as the lessons API serves them, to inspect (#2181). It never
    raises: a read that fails is that section's ``failed``."""

    def __init__(
        self,
        records: Any,
        exposures: Any,
        *,
        limits: ChatLimits,
        now: datetime,
    ) -> None:
        self._records = records
        self._exposures = exposures
        self._limits = limits
        self._now = now

    async def assemble(self, request: ContextRequest) -> ContextBundle:
        turn = request.consumer
        if not isinstance(turn, ChatTurn):
            raise TypeError("ChatContextAssembly assembles a chat turn's context")
        project_id = (
            request.binding.project_id if isinstance(request.binding, ProjectBound) else None
        )
        if self._records is None:
            sections = tuple(
                Section(kind, Need.OPTIONAL, Disposition.DISABLED)
                for kind in (*CHAT_SECTIONS, SectionKind.INSPECTED_LESSONS, SectionKind.LESSONS)
            )
            return ContextBundle(request, sections, complete=True, chat=None)
        # Project notes only for a bound turn whose person may read the project (§3.3).
        notes_project = project_id if Scope.MEMORY_READ in turn.viewer_scopes else None
        owned = await self._read(
            "owned", lambda: self._records.list_owned(turn.user_id), session=turn.session_id
        )
        project = (
            await self._read(
                "project", lambda: self._records.list_project(project_id), session=turn.session_id
            )
            if project_id is not None
            else Loaded()
        )
        notes = await self._read(
            "notes",
            lambda: self._records.search_notes(
                owner_id=turn.user_id, project_id=notes_project, text=turn.text
            ),
            session=turn.session_id,
        )
        lessons = (
            await self._lessons(project_id, session=turn.session_id)
            if project_id is not None
            and Scope.MEMORY_READ in turn.viewer_scopes
            and asks_about_lessons(turn.text)
            else None
        )
        try:
            sections, handed = chat_context(
                turn=turn,
                project_id=project_id,
                reads={
                    SectionKind.PROJECT_INSTRUCTIONS: project,
                    SectionKind.TASK_INSTRUCTIONS: project,
                    SectionKind.PREFERENCES: owned,
                    SectionKind.NOTES: notes,
                },
                limits=self._limits,
                lessons=lessons,
            )
        except Exception:  # noqa: BLE001 — a record the rules can't read fails the context, not the turn
            logger.warning("chat_context_unassembled session=%s", turn.session_id, exc_info=True)
            return _all_failed(request, project_id)
        return ContextBundle(request, sections, complete=True, chat=handed)

    async def _lessons(self, project_id: str, *, session: str) -> LessonsLoaded:
        if self._exposures is None:
            return LessonsLoaded(failure="no memory store is configured")
        try:
            return LessonsLoaded(
                revisions=tuple(await self._exposures.list_revisions(project_id)),
                approvals=tuple(await self._exposures.list_approvals(project_id)),
                exposures=tuple(await self._exposures.list_project_exposures(project_id)),
            )
        except Exception as e:  # noqa: BLE001 — the section is failed and disclosed; the turn runs
            logger.warning("chat_context_read_failed lessons session=%s", session, exc_info=True)
            return LessonsLoaded(failure=f"{type(e).__name__}: {e}")

    @staticmethod
    async def _read(what: str, read: Any, *, session: str) -> Loaded:
        try:
            return Loaded(tuple(await read()))
        except Exception as e:  # noqa: BLE001 — the section is failed and disclosed; the turn runs
            logger.warning("chat_context_read_failed %s session=%s", what, session, exc_info=True)
            return Loaded(failure=f"{type(e).__name__}: {e}")

    async def disclose(self, bundle: ContextBundle) -> None:
        if self._exposures is None:
            return
        exposure = ChatExposure.of(bundle, at=self._now)
        try:
            await self._exposures.record_chat_exposure(exposure)
        except Exception:  # noqa: BLE001 — the port never raises: a missing exposure is logged
            logger.warning(
                "chat_exposure_not_recorded session=%s message=%s",
                exposure.session_id,
                exposure.message_id,
                exc_info=True,
            )


def _all_failed(request: ContextRequest, project_id: str | None) -> ContextBundle:
    """A context that couldn't be assembled: every section ``failed``, and the reply says so."""
    kinds = (*CHAT_SECTIONS, SectionKind.INSPECTED_LESSONS)
    sections = (
        *(Section(kind, Need.OPTIONAL, Disposition.FAILED) for kind in kinds),
        Section(SectionKind.LESSONS, Need.OPTIONAL, Disposition.NOT_APPLICABLE),
    )
    handed = {"project_id": project_id, "sections": [], "unavailable": [k.value for k in kinds]}
    return ContextBundle(request, sections, complete=True, chat=handed)
