"""Replay evidence rails — rendering surface (SIP-0101 Slice 1).

The ``ReplayProvenance`` record itself lives in ``verification_integrity``
beside its evidence-disclosure siblings (``UnverifiedCheck``, ``WaivedCheck``)
so the aggregation module stays import-pure; it is re-exported here as the
SIP-0101-named import path. This module owns the human-facing wording.
"""

from __future__ import annotations

from squadops.cycles.verification_integrity import ReplayProvenance

__all__ = ["ReplayProvenance", "replay_marker_lines"]


def replay_marker_lines(replay: ReplayProvenance) -> list[str]:
    """The human-facing replay disclosure, shared by every rendering surface.

    One source for the wording so the report, CLI, and any future surface
    cannot drift into softer language: evidence at or before the boundary is
    inherited, not earned.
    """
    return [
        f"⚠ REPLAYED — prefix restored from {replay.source_run_id} "
        f"at boundary {replay.boundary_index}",
        "Evidence at or before the boundary is inherited from the source run, "
        "not earned by this execution.",
    ]
