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

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.cycles.verification_integrity import CheckResult


class RunLedger:
    """Append-only per-run evidence ledger with immutable read accessors."""

    __slots__ = ("_pulse_entries", "_check_results")

    def __init__(self) -> None:
        self._pulse_entries: list[dict[str, Any]] = []
        self._check_results: list[CheckResult] = []

    def record_pulse_boundary(self, entry: dict[str, Any]) -> None:
        """Record one pulse boundary-decision summary (append-only)."""
        self._pulse_entries.append(entry)

    @property
    def pulse_entries(self) -> tuple[dict[str, Any], ...]:
        """Immutable view of the accumulated pulse boundary summaries."""
        return tuple(self._pulse_entries)

    def record_check_result(self, result: CheckResult) -> None:
        """Record one normalized verification result (SIP-0096 §6.4, append-only).

        The aggregation target consumed by ``aggregate_verification`` at the
        ``RunCompletion`` seam. Phase 1 leaves this empty (no producer wiring);
        Phase 2 has each verification producer normalize its result into a
        ``CheckResult`` and append it here.
        """
        self._check_results.append(result)

    @property
    def check_results(self) -> tuple[CheckResult, ...]:
        """Immutable view of the accumulated verification results (SIP-0096)."""
        return tuple(self._check_results)
