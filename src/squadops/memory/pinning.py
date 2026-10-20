"""Pinning a unit's snapshot when it is admitted (SIP-0110 §0.7; slice 3c, #2096).

A standalone cycle pins when it is created, and a campaign when it is admitted; a campaign's
proposals and cycles use the campaign's. The pin reads the project's lessons and approvals as they
stand at that moment and stores the whole snapshot, once: a restart asks again and gets the
original, so a unit's guidance never changes while it runs.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

from squadops.memory.declarations import memory_context_none, memory_disabled
from squadops.memory.lessons import Approval, RecallPolicy, Snapshot, UnitKind, pin
from squadops.memory.records import MemoryRecord, PinnedInstruction, RecordStatus, in_force
from squadops.memory.reference_binding import bound_instruction
from squadops.memory.references import BindingContext

if TYPE_CHECKING:
    from squadops.ports.memory.cross_cycle import CrossCycleMemoryStorePort
    from squadops.ports.memory.records import MemoryRecordsPort
    from squadops.ports.memory.references import ReferenceResolverPort

logger = logging.getLogger(__name__)


async def pin_unit(
    store: CrossCycleMemoryStorePort,
    *,
    unit_kind: UnitKind,
    unit_id: str,
    project_id: str,
    pinned_at: datetime,
    disabled: bool,
    policy: RecallPolicy | None = None,
    records: MemoryRecordsPort | None = None,
    context_withheld: bool = False,
    resolvers: Mapping[str, ReferenceResolverPort] | None = None,
    source_commit: str | None = None,
) -> Snapshot:
    """The unit's snapshot: the one it already pinned, or a new pin of what is approved now, with
    the project instructions in force now from ``records`` (#2179). Records that can't be read
    don't cost the unit its lessons: the snapshot pins them and says why it has no instructions,
    so a task never reads an unread pin as one that held none (§3.6). A unit that declares
    ``memory_context: none`` reads neither: it pins nothing, and says so (§3.7)."""
    held = await store.get_snapshot(unit_kind, unit_id)
    if held is not None:
        return held
    withholds_lessons = disabled or context_withheld
    instructions: tuple[PinnedInstruction, ...] = ()
    unread = None
    if records is not None and not context_withheld:
        try:
            instructions = in_force(await records.list_project(project_id))
            # #2179 T16: each ``@current`` reference is bound now, at admission, and kept.
            ctx = BindingContext(project_id, unit_kind.value, unit_id, source_commit)
            instructions = tuple(
                [await bound_instruction(p, resolvers or {}, ctx) for p in instructions]
            )
        except Exception as e:  # noqa: BLE001 — the lessons pin; the snapshot records the miss
            unread = f"the project's instructions could not be read at admission ({e})"
            logger.warning(
                "memory_instructions_not_pinned unit=%s:%s", unit_kind, unit_id, exc_info=True
            )
    snapshot = pin(
        unit_kind=unit_kind,
        unit_id=unit_id,
        pinned_at=pinned_at,
        disabled=disabled,
        # A pin that withholds the lessons never reads them, so a lesson store that can't be read
        # doesn't cost it its snapshot.
        revisions=[] if withholds_lessons else await store.list_revisions(project_id),
        approvals=[] if withholds_lessons else await store.list_approvals(project_id),
        policy=policy,
        instructions=instructions,
        instructions_unread=unread,
        context_withheld=context_withheld,
    )
    recorded = await store.record_snapshot(snapshot)
    if recorded.snapshot_id != snapshot.snapshot_id:
        return recorded  # another pin of the unit landed first; it is the unit's
    return await _settled(store, recorded, project_id=project_id, records=records)


def removed_since_read(
    snapshot: Snapshot, records: Iterable[MemoryRecord], approvals: Iterable[Approval]
) -> Snapshot | None:
    """``snapshot`` without the project instructions withdrawn, and the lessons whose approval was
    revoked, after the pin read them; ``None`` when nothing was. A withdrawal or a revocation
    answered between the pin's read and its write found no snapshot to name, and told the
    operator that units admitted from then pin without it (#2545). This makes that true."""
    gone = {r.record_id for r in records if r.status == RecordStatus.WITHDRAWN}
    revoked = {a.approval_id for a in approvals if a.revoked_at is not None}
    instructions = tuple(p for p in snapshot.instructions if p.record_id not in gone)
    entries = tuple(e for e in snapshot.entries if e.approval.approval_id not in revoked)
    if (instructions, entries) == (snapshot.instructions, snapshot.entries):
        return None
    return replace(snapshot, instructions=instructions, entries=entries)


async def _settled(
    store: CrossCycleMemoryStorePort,
    snapshot: Snapshot,
    *,
    project_id: str,
    records: MemoryRecordsPort | None,
) -> Snapshot:
    """The snapshot as the unit's admission ends it: read again once stored, so a revocation or a
    withdrawal that landed while the pin was being taken is honoured. Nothing has dispatched yet,
    since both admissions pin before they launch, so this is the admission's own correction, not
    a re-binding. A read that fails keeps the snapshot as stored, and is logged."""
    try:
        now_records = await records.list_project(project_id) if records is not None else []
        approvals = [] if snapshot.disabled else await store.list_approvals(project_id)
        corrected = removed_since_read(snapshot, now_records, approvals)
        if corrected is None:
            return snapshot
        await store.rebind_snapshot(corrected, after=len(snapshot.rebindings))
    except Exception:  # noqa: BLE001 — the stored pin stands; the miss is logged
        logger.warning(
            "memory_snapshot_not_settled unit=%s:%s", snapshot.unit_kind, snapshot.unit_id,
            exc_info=True,
        )  # fmt: skip
        return snapshot
    logger.info(
        "memory_snapshot_settled unit=%s:%s removed_after_read", snapshot.unit_kind,
        snapshot.unit_id,
    )  # fmt: skip
    return corrected


def source_commit_of(cycle: Any) -> str | None:
    """The commit a cycle's source context pins (SIP-0112 FR-04), which a repository reference
    binds at; ``None`` for a cycle with no source context."""
    context = getattr(cycle, "source_context", None)
    return getattr(context, "development_baseline_commit", None) if context else None


def cycle_binding(cycle: Any) -> BindingContext:
    """What a task instruction's reference is bound for: its cycle, at the commit the cycle's source
    context pins (§3.7; #2178 T16). A campaign's cycle pins its own, unlike the campaign."""
    return BindingContext(
        cycle.project_id, UnitKind.CYCLE.value, cycle.cycle_id, source_commit_of(cycle)
    )


async def pin_standalone_cycle(
    store: CrossCycleMemoryStorePort,
    cycle: Any,
    *,
    now: datetime,
    records: MemoryRecordsPort | None = None,
    resolvers: Mapping[str, ReferenceResolverPort] | None = None,
) -> Snapshot | None:
    """A standalone cycle's pin at its creation (§0.7), or ``None`` for a campaign's cycle, which
    uses its campaign's snapshot."""

    if getattr(cycle, "campaign_id", None):
        return None
    config = cycle.resolved_config()
    withheld = memory_context_none(config)
    return await pin_unit(
        store,
        unit_kind=UnitKind.CYCLE,
        unit_id=cycle.cycle_id,
        project_id=cycle.project_id,
        pinned_at=now,
        disabled=withheld or memory_disabled(config),
        records=records,
        context_withheld=withheld,
        resolvers=resolvers,
        source_commit=source_commit_of(cycle),
    )


async def pin_campaign(
    store: CrossCycleMemoryStorePort,
    campaign: Any,
    *,
    now: datetime,
    records: MemoryRecordsPort | None = None,
    resolvers: Mapping[str, ReferenceResolverPort] | None = None,
) -> Snapshot:
    """A campaign's pin at its admission (§0.7); its proposals and cycles use it. A campaign-level
    memory-disabled declaration, for a live confirmation's off arm (§0.12), arrives with slice 4."""
    return await pin_unit(
        store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id=campaign.campaign_id,
        project_id=campaign.project_id,
        pinned_at=now,
        disabled=False,
        records=records,
        # A campaign has no source context of its own: each of its cycles pins one when it is
        # prepared (SIP-0112), after the campaign's snapshot. So a repository reference has no
        # commit to bind at here, and its resolver refuses it (§5z).
        resolvers=resolvers,
        source_commit=None,
    )
