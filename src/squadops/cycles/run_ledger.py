"""Per-run verification-evidence accumulator (SIP-0097 §6.6).

Created once at the top of ``execute_run`` and passed explicitly to the
collaborators that need it — never stored on the executor or any long-lived
collaborator, and never retained past finalization (the run report is the
last reader). Append-only writes, immutable read accessors.

Contents are versioned by SIP-0097 §6.6: in v1.3 the ledger carries the
pulse boundary verification summaries (the former executor
``_pulse_report_entries`` instance state); in v1.4, SIP-0096 extends it to
every recorded check result and wires its aggregation function to consume
it at the ``RunCompletion`` seam.

This is an in-memory accumulator, not a persistence abstraction —
persistence stays with the existing registry/report paths.
"""

from __future__ import annotations

from typing import Any


class RunLedger:
    """Append-only per-run evidence ledger with immutable read accessors."""

    __slots__ = ("_pulse_entries",)

    def __init__(self) -> None:
        self._pulse_entries: list[dict[str, Any]] = []

    def record_pulse_boundary(self, entry: dict[str, Any]) -> None:
        """Record one pulse boundary-decision summary (append-only)."""
        self._pulse_entries.append(entry)

    @property
    def pulse_entries(self) -> tuple[dict[str, Any], ...]:
        """Immutable view of the accumulated pulse boundary summaries."""
        return tuple(self._pulse_entries)
