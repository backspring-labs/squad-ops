"""A cycle's failure records: its failure events, persisted at completion (SIP-0109 §14, #1710).

``failure_events(outcome, evidence)`` is the one producer of a cycle's failure events. At
completion, each event is persisted as a ``FailureRecord`` with the class ``compose()`` gives it
and the registry version that composed it, and each input the attribution could not read is
persisted as a record in state ``unaskable`` naming that input, so a missing input is never
silently absent. The assessment's attribution is then computed from exactly the persisted
events (``events_of``): no consumer re-derives them.

A cycle's records are one write-once set. ``None`` from the registry means the set was never
written (a cycle that ended before this existed, or whose write failed); an empty set means the
cycle was recorded and had no failures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadops.cycles.failure_attribution import (
    ATTRIBUTION_REGISTRY_VERSION,
    AttributionClass,
    FailureEvent,
    compose,
)


class FailureRecordState(StrEnum):
    RECORDED = "recorded"
    UNASKABLE = "unaskable"


@dataclass(frozen=True)
class FailureRecord:
    """One failure record (§14, §15). A ``recorded`` record carries its event and the class it
    composes to (``None`` for a declared non-failure); an ``unaskable`` one names the input the
    attribution could not read, and carries no event."""

    cycle_id: str
    event_index: int
    state: FailureRecordState
    registry_version: int
    event: FailureEvent | None = None
    attribution_class: AttributionClass | None = None
    unasked_input: str | None = None
    campaign_id: str | None = None
    increment_id: str | None = None

    def __post_init__(self) -> None:
        recorded = self.state is FailureRecordState.RECORDED
        if recorded != (self.event is not None) or recorded == (self.unasked_input is not None):
            raise ValueError(
                f"{self.cycle_id}#{self.event_index}: a recorded record carries its event, an "
                "unaskable one names its input, and neither carries both"
            )


def failure_records(
    cycle_id: str,
    events: tuple[FailureEvent, ...],
    unrecorded: tuple[str, ...],
    *,
    campaign_id: str | None = None,
    increment_id: str | None = None,
) -> tuple[FailureRecord, ...]:
    """The records a completion persists: its events in the producer's order, then one
    ``unaskable`` record per input the attribution could not read."""
    common = {
        "cycle_id": cycle_id,
        "registry_version": ATTRIBUTION_REGISTRY_VERSION,
        "campaign_id": campaign_id,
        "increment_id": increment_id,
    }
    recorded = tuple(
        FailureRecord(
            event_index=i,
            state=FailureRecordState.RECORDED,
            event=event,
            attribution_class=compose(event),
            **common,
        )
        for i, event in enumerate(events)
    )
    unaskable = tuple(
        FailureRecord(
            event_index=len(events) + i,
            state=FailureRecordState.UNASKABLE,
            unasked_input=name,
            **common,
        )
        for i, name in enumerate(unrecorded)
    )
    return recorded + unaskable


def events_of(records: tuple[FailureRecord, ...]) -> tuple[FailureEvent, ...]:
    """The persisted events, in their recorded order: what the attribution is computed from."""
    ordered = sorted(records, key=lambda r: r.event_index)
    return tuple(r.event for r in ordered if r.event is not None)
