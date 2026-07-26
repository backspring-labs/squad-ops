"""Crash-persistent operation evidence journal (SIP-0102 §7 item 11, #427).

Every typed operation's semantic result is appended to an on-disk JSONL
journal the moment it exists — evidence survives orchestration crashes because
it never waits for one. Reads are tolerant of a truncated final line (the
crash-mid-write case): one damaged line never poisons the journal.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from squadops.execution.models import OperationResult


def result_to_dict(result: OperationResult) -> dict:
    """Serialize any semantic result, tagged with its concrete type so readers
    can interpret op-specific fields without a rehydration registry."""
    payload = dataclasses.asdict(result)
    payload["result_type"] = type(result).__name__
    return payload


class OperationEvidenceJournal:
    """Append-only per-cycle journal under the workspace-store root
    (``<root>/<cycle_id>/evidence/operations.jsonl``)."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _journal_file(self, cycle_id: str) -> Path:
        return self._root / cycle_id / "evidence" / "operations.jsonl"

    def record(
        self, cycle_id: str, result: OperationResult, *, recorded_at: str | None = None
    ) -> None:
        """Append one result. Opens per call so a crash can lose at most the
        line being written, never previously recorded evidence."""
        path = self._journal_file(cycle_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = result_to_dict(result)
        if recorded_at is not None:
            entry["recorded_at"] = recorded_at
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def read(self, cycle_id: str) -> tuple[dict, ...]:
        """Every readable entry, oldest first; malformed/truncated lines are
        skipped rather than raised."""
        path = self._journal_file(cycle_id)
        if not path.is_file():
            return ()
        entries: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return tuple(entries)
