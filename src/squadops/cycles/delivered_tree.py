"""The files a run delivered, from its stored artifacts' records: one rule, for every reader.

Per filename, the latest **workspace** artifact (``source``, ``test``, ``config``) the run
accepted, where:
- **a failed emission is never delivered** (#971). It is banked as triage evidence, and is often
  the only copy of its file, so last-wins would deliver bytes already proven not to work;
- **a repair candidate is never delivered.** It is unaccepted by construction: an accepted repair
  is re-stored under its task's own type (#389), so taking a candidate would deliver a rejected
  repair that happens to be newer (pf-54);
- **a scaffold-seeded artifact never shadows produced content** (#881). A resumed run can
  re-seed a stub after the fill that replaced it, and stubs throw by design.

The readers: the delivered-app audit (``scripts/dev/audit_delivered_app.py``), the release
screenshots (``scripts/dev/capture_delivered_app.py``) and a campaign's accepted tree (SIP-0109
§7.1). Each kept its own copy of this rule before, and the copies had drifted: the capture took
the newest file by name whatever produced it, and the audit had no seeded-stub rule.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.cycles.emission_integrity import EMISSION_STATUS_FAILED
from squadops.cycles.task_plan import REPAIR_TASK_TYPES

#: The artifact types a run's application is made of.
WORKSPACE_ARTIFACT_TYPES = frozenset({"source", "test", "config"})


@dataclass(frozen=True)
class StoredArtifact:
    """What the rule reads of one stored artifact."""

    artifact_id: str
    filename: str
    artifact_type: str
    #: Sortable: the vault stores an ISO timestamp, and every artifact of a run carries one.
    created_at: str
    producing_task_type: str = ""
    emission_status: str | None = None
    scaffold_seeded: bool = False

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> StoredArtifact:
        """From a vault ``metadata.json`` (or an ``ArtifactRef`` as a mapping)."""
        meta = record.get("metadata") or {}
        return cls(
            artifact_id=str(record["artifact_id"]),
            filename=str(record["filename"]),
            artifact_type=str(record.get("artifact_type") or ""),
            created_at=str(record.get("created_at") or ""),
            producing_task_type=str(meta.get("producing_task_type") or ""),
            emission_status=meta.get("emission_status"),
            scaffold_seeded=bool(meta.get("scaffold_seeded")),
        )


def delivered_files(stored: Iterable[StoredArtifact]) -> dict[str, str]:
    """filename → the artifact id the run delivered under it."""
    chosen: dict[str, StoredArtifact] = {}
    for art in sorted(stored, key=lambda a: (a.created_at, a.artifact_id)):
        if art.artifact_type not in WORKSPACE_ARTIFACT_TYPES:
            continue
        if art.emission_status == EMISSION_STATUS_FAILED:
            continue
        if art.producing_task_type in REPAIR_TASK_TYPES:
            continue
        held = chosen.get(art.filename)
        if art.scaffold_seeded and held is not None and not held.scaffold_seeded:
            continue
        chosen[art.filename] = art
    return {name: art.artifact_id for name, art in sorted(chosen.items())}
