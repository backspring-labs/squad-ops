"""Per-run verification-evidence accumulator (SIP-0097 §6.6).

Created once at the top of ``execute_run`` and passed explicitly to the
collaborators that need it — never stored on the executor or any long-lived
collaborator, and never retained past finalization (the run report is the
last reader). Append-only writes, immutable read accessors.

Contents are versioned by SIP-0097 §6.6: in v1.3 the ledger carries the
pulse boundary verification summaries (the former executor
``_pulse_report_entries`` instance state); in v1.4, SIP-0096 extends it to
every recorded check result and wires its aggregation function to consume
it at the ``RunCompletion`` seam. In v1.8, SIP-0108 §4.1 adds the loop facts no
store held — each refunded correction round, each round's movement class, each
round's classified failure and each absent emission — which finalization persists as the
run summary.

This is an in-memory accumulator, not a persistence abstraction —
persistence stays with the existing registry/report paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.cycles.run_loop_summary import (
        AbsentEmission,
        MovementRecord,
        RefundedRound,
        RoundFailure,
    )
    from squadops.cycles.verification_integrity import CheckResult


class RunLedger:
    """Append-only per-run evidence ledger with immutable read accessors."""

    __slots__ = (
        "_pulse_entries",
        "_check_results",
        "_refunded_rounds",
        "_movements",
        "_round_failures",
        "_absent_emissions",
    )

    def __init__(self) -> None:
        self._pulse_entries: list[dict[str, Any]] = []
        self._check_results: list[CheckResult] = []
        self._refunded_rounds: list[RefundedRound] = []
        self._movements: list[MovementRecord] = []
        self._round_failures: list[RoundFailure] = []
        self._absent_emissions: list[AbsentEmission] = []

    def record_refunded_round(self, record: RefundedRound) -> None:
        """Record one correction round handed back rather than spent (#1053, append-only)."""
        self._refunded_rounds.append(record)

    @property
    def refunded_rounds(self) -> tuple[RefundedRound, ...]:
        return tuple(self._refunded_rounds)

    def record_movement(self, record: MovementRecord) -> None:
        """Record one failed task's round-over-round movement class (A4.2, append-only)."""
        self._movements.append(record)

    @property
    def movements(self) -> tuple[MovementRecord, ...]:
        return tuple(self._movements)

    def record_round_failure(self, record: RoundFailure) -> None:
        """Record one correction round's classified failure (SIP-0108 §4.2, append-only)."""
        self._round_failures.append(record)

    @property
    def round_failures(self) -> tuple[RoundFailure, ...]:
        return tuple(self._round_failures)

    def record_absent_emission(self, record: AbsentEmission) -> None:
        """Record one emission that yielded no file (#566/#1053, append-only)."""
        self._absent_emissions.append(record)

    @property
    def absent_emissions(self) -> tuple[AbsentEmission, ...]:
        return tuple(self._absent_emissions)

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
