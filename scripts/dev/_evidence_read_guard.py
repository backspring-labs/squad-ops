"""Evidence-read guard shared by the scripts that read the live registry and vault.

``assemble_cycle_evidence`` reads an artifact it cannot open as absent, logging a warning and
carrying on: right for the assessment route, which reports what it could read. A script that
writes records from that evidence, or proves equality on it, must not: a cycle read with missing
artifacts yields degraded records that pass any before/after comparison, because both sides
degrade the same way. Found 2026-10-02: the vault's index is root-only (mode 600), and two
snapshot runs read 20 artifacts as unreadable without saying so.
"""

from __future__ import annotations

import logging
from pathlib import Path

_EVIDENCE_LOGGER = "adapters.cycles.cycle_evidence"


def require_readable_vault(vault_dir: Path) -> None:
    """Refuse to start when the vault's index cannot be read (or is missing: the vault would
    write one on construction)."""
    index = vault_dir / "_index.json"
    try:
        with index.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        raise SystemExit(
            f"cannot read the vault index {index} ({exc.strerror}): run where the vault is readable, "
            "e.g. inside the runtime image with the vault mounted read-only"
        ) from exc


class UnreadableEvidence(logging.Handler):
    """Counts the artifacts evidence assembly could not read, between ``reset()`` calls."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.artifacts: list[str] = []
        logging.getLogger(_EVIDENCE_LOGGER).addHandler(self)

    def emit(self, record: logging.LogRecord) -> None:
        if "unreadable" in record.getMessage():
            self.artifacts.append(record.getMessage())

    def reset(self) -> list[str]:
        seen, self.artifacts = self.artifacts, []
        return seen
