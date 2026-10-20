"""Re-binding a running unit (SIP-0110 Appendix A §3.7; #2179 stage 2).

The one way to change what a running unit has bound, and the authorized release of a hold its
pinned binding causes (§3.6). A new revision of a project instruction reaches units admitted later,
and a running unit keeps the revision it pinned until it is re-bound: the record's current revision
replaces it, or nothing does when the record is withdrawn.

It goes **forward** when no run still running was handed the replaced revision: the unit's next
dispatch binds the new one. A run that ended after being handed it is history, kept and never
reused. When a running run was handed it, the run is halted first and the work restarts from a new
run (§3.8's path), so nothing built under the old binding carries into the new one.

Pure: the routes read the stores and the registries, and these rules decide.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime

from squadops.memory.exposures import Exposure
from squadops.memory.lessons import Snapshot
from squadops.memory.records import (
    MemoryRecord,
    Rebinding,
    RecordKind,
    RecordScope,
    RecordStatus,
    pinned_of,
)


class RebindRefused(ValueError):
    """A re-binding the rules refuse, with why. Nothing is stored."""


def rebound(
    snapshot: Snapshot,
    record: MemoryRecord,
    *,
    by: str,
    at: datetime,
    why: str,
    received_by: Iterable[str] = (),
) -> Snapshot:
    """``snapshot`` with ``record``'s bound revision replaced by its current one, or removed when the
    record is withdrawn, and the re-binding recorded. ``received_by`` names the ended runs that were
    handed the replaced revision."""
    unit = f"{snapshot.unit_kind.value} {snapshot.unit_id}"
    if record.kind != RecordKind.INSTRUCTION or record.scope != RecordScope.PROJECT:
        raise RebindRefused(f"{record.record_id} is not a project instruction: no unit binds it")
    if not why.strip():
        raise RebindRefused("a re-binding is an intervention, so it says why")
    if snapshot.context_withheld:
        raise RebindRefused(
            f"{unit} declared memory_context: none, and binds no project instruction"
        )
    if snapshot.instructions_unread is not None:
        raise RebindRefused(
            f"{unit}'s pin couldn't read the project's instructions, so what it binds is unknown"
        )
    held = next((p for p in snapshot.instructions if p.record_id == record.record_id), None)
    if held is None:
        raise RebindRefused(
            f"{unit} binds no revision of {record.record_id}. A re-binding replaces one the unit "
            "bound; an instruction confirmed after admission reaches the units admitted after it"
        )
    replacement = None if record.status == RecordStatus.WITHDRAWN else pinned_of(record)
    if replacement is not None and replacement.revision == held.revision:
        raise RebindRefused(f"{unit} already binds revision {held.revision} of {record.record_id}")
    kept = [p for p in snapshot.instructions if p is not held]
    if replacement is not None:
        kept.insert(snapshot.instructions.index(held), replacement)
    instructions = tuple(kept)
    rebinding = Rebinding(
        record_id=record.record_id,
        replaced=held,
        replacement=replacement,
        by=by,
        at=at,
        why=why,
        received_by=tuple(received_by),
    )
    return replace(
        snapshot, instructions=instructions, rebindings=(*snapshot.rebindings, rebinding)
    )


def runs_handed(
    snapshot: Snapshot, record_id: str, exposures: Iterable[Exposure]
) -> list[tuple[str, str]]:
    """Each ``(cycle_id, run_id)`` of the unit whose dispatch was handed the revision of
    ``record_id`` the unit binds now, in the order first seen. These decide the path: a run still
    running is halted before the unit is re-bound, and an ended one is history."""
    held = next((p for p in snapshot.instructions if p.record_id == record_id), None)
    if held is None:
        return []
    runs: list[tuple[str, str]] = []
    for e in exposures:
        if (e.query.unit_kind, e.query.unit_id) != (snapshot.unit_kind, snapshot.unit_id):
            continue
        supplied = (e.project_instructions or {}).get("supplied") or ()
        if (
            any(
                s.get("record_id") == record_id and str(s.get("revision")) == str(held.revision)
                for s in supplied
            )
            and (e.cycle_id, e.run_id) not in runs
        ):
            runs.append((e.cycle_id, e.run_id))
    return runs


def rebinding_naming(snapshot: Snapshot | None, run_id: str) -> Rebinding | None:
    """The re-binding that names ``run_id`` among the runs handed the revision it replaced, or
    ``None``. Such a run is history: resuming it would carry work done under the replaced revision
    into the re-bound unit, which the restart path never reuses (§3.7, §3.8)."""
    if snapshot is None:
        return None
    return next((r for r in snapshot.rebindings if run_id in r.received_by), None)
