"""A source-backed run's removal of a product file, as the run stores and reads it (#2612,
SIP-0112 H.23).

A step that removes a file says so with the deletion form (``fenced_parser``). Its handler judges
each removal against the task's view and grant, and hands the accepted ones on in its outputs
under :data:`DELETIONS_KEY`, apart from its artifacts: every reader of a task's artifacts reads
files, and a removal read as one is an empty file.

Storage records each accepted removal as an artifact of :data:`DELETION_ARTIFACT_TYPE`: the path,
no content, under the task that removed it. The run's artifact list is a log, so a removal is
ordered among the writes like any emission, and a later write of the path brings it back. The
readers that resolve a path's current state honor it (:func:`deleted_paths`): the task view, the
workspace a task is handed, and the delivery's candidate. A reader that selects by artifact type
never selects one, and sees the path as it was.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from squadops.cycles.emission_integrity import banked_as
from squadops.cycles.models import ArtifactType

#: The task outputs key that carries a step's accepted removals, as repository paths.
DELETIONS_KEY = "deletions"
#: The outputs key that names the removals a step's handler refused, each with why.
DELETIONS_REFUSED_KEY = "deletions_refused"
#: The stored record of one removal. A reader that selects by type never takes it, and one that
#: selects by producer has it removed with the path (``deleted_paths``).
DELETION_ARTIFACT_TYPE = ArtifactType.DELETION


def deletion_record(path: str) -> dict[str, Any]:
    """The artifact dict storage records one removal as."""
    return {"name": path, "content": "", "type": DELETION_ARTIFACT_TYPE, "media_type": "text/plain"}


def is_deletion(ref: Any) -> bool:
    return getattr(ref, "artifact_type", None) == DELETION_ARTIFACT_TYPE


def deleted_paths(
    stored_artifacts: Iterable[tuple[str, Any]], *, skip_producers: Iterable[str] = ()
) -> frozenset[str]:
    """The paths whose latest stored entry is a removal: the run's accepted state has no file
    there. A banked emission (failed or handed off) is never accepted state, and neither is an
    entry from one of ``skip_producers`` (a repair's candidates, until re-stored as the task's own)."""
    skipped = frozenset(skip_producers)
    latest: dict[str, bool] = {}
    for _art_id, ref in stored_artifacts:
        metadata = getattr(ref, "metadata", None) or {}
        if banked_as(metadata.get("emission_status")) is not None:
            continue
        if metadata.get("producing_task_type", "") in skipped:
            continue
        latest[ref.filename] = is_deletion(ref)
    return frozenset(path for path, removed in latest.items() if removed)
