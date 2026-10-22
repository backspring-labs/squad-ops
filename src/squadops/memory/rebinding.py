"""Re-binding a running unit (SIP-0110 Appendix A §3.7; #2179 stage 2).

The one way to change what a running unit has bound, and the authorized release of a hold its
pinned binding causes (§3.6). A new revision of a project instruction reaches units admitted later,
and a running unit keeps the revision it pinned until it is re-bound: the record's current revision
replaces it, or nothing does when the record is withdrawn.

It goes **forward** only when no dispatch of the unit was handed the replaced revision: the unit's
next dispatch binds the new one, and nothing it builds on was made under the old. When one was, a
later task would build on that work, which §3.7 sends down the restart path: halt, re-bind, restart
from the earliest affected task, and keep the history without reusing it. That path isn't built, so
such a unit is refused, and its work restarts as a new unit (§5u).

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
    PinnedInstruction,
    Rebinding,
    RecordKind,
    RecordScope,
    RecordStatus,
    is_current,
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
    replacement: PinnedInstruction | None = None,
) -> Snapshot:
    """``snapshot`` with ``record``'s bound revision replaced by its current one, or removed when the
    record is withdrawn, and the re-binding recorded. ``replacement`` is that current revision with
    its ``@current`` references bound for the unit (``bound_instruction``), which the caller does
    since binding asks the resolvers; without it, a revision naming ``@current`` is refused, so a
    re-binding never puts one in the snapshot verbatim (the second read of #2179 T16)."""
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
    if record.status == RecordStatus.WITHDRAWN:
        replacement = None
    else:
        replacement = replacement or pinned_of(record)
        if replacement.record_id != record.record_id:
            raise RebindRefused(f"{replacement.record_id} is not a revision of {record.record_id}")
        if any(is_current(r.ref) for r in replacement.references) and not replacement.unbound:
            raise RebindRefused(
                f"revision {replacement.revision} of {record.record_id} names @current: it is bound "
                "for the unit before it is re-bound, never stored verbatim"
            )
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
    )
    return replace(
        snapshot,
        instructions=instructions,
        rebindings=(*snapshot.rebindings, rebinding),
        version=snapshot.version + 1,
    )


def runs_handed(
    snapshot: Snapshot, record_id: str, exposures: Iterable[Exposure]
) -> list[tuple[str, str]]:
    """Each ``(cycle_id, run_id)`` of the unit whose dispatch was handed the revision of
    ``record_id`` the unit binds now, in the order first seen. Any one sends the re-binding down the
    restart path: the unit's later work would build on what it made. Read from the exposures, so a
    dispatch whose exposure wasn't recorded isn't seen (§5v). A held task's exposure handed nothing
    (#2178): the re-binding that releases it goes forward."""
    held = next((p for p in snapshot.instructions if p.record_id == record_id), None)
    if held is None:
        return []
    runs: list[tuple[str, str]] = []
    for e in exposures:
        if e.held or (e.query.unit_kind, e.query.unit_id) != (snapshot.unit_kind, snapshot.unit_id):
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
