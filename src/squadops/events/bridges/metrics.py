"""MetricsBridge — translates selective CycleEvents to MetricsPort counters, gauges and histograms.

Not a full lifecycle mirror of every event. A run's start and end, a campaign's transitions and the
task, correction and cycle moments below increment counters; task.succeeded with duration_ms also
records a histogram; and the run and campaign moments set an event-time marker (#2204).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.events.types import EventType

if TYPE_CHECKING:
    from squadops.events.models import CycleEvent
    from squadops.ports.telemetry.metrics import MetricsPort

logger = logging.getLogger(__name__)

# Selective counter map: event_type → counter metric name
_COUNTER_MAP: dict[str, str] = {
    EventType.CYCLE_CREATED: "cycles_created_total",
    EventType.RUN_STARTED: "runs_started_total",
    EventType.RUN_COMPLETED: "runs_completed_total",
    EventType.RUN_FAILED: "runs_failed_total",
    EventType.RUN_CANCELLED: "runs_cancelled_total",
    EventType.TASK_SUCCEEDED: "tasks_succeeded_total",
    EventType.TASK_FAILED: "tasks_failed_total",
    EventType.CORRECTION_INITIATED: "corrections_initiated_total",
    EventType.CORRECTION_COMPLETED: "corrections_completed_total",
    EventType.CAMPAIGN_TRANSITIONED: "campaign_transitions_total",
}

#: #2204: when each run and campaign moment happened, as a gauge holding the event's own time in
#: epoch seconds. Grafana draws each distinct value as a marker on every chart ("series value as
#: timestamp"). A counter can't: it says how many, never when, and Prometheus's ``increase()``
#: misses a series' first count, which is every first run after a restart.
_MARKER_MAP: dict[str, tuple[str, dict[str, str]]] = {
    EventType.RUN_STARTED: ("run_started_timestamp_seconds", {}),
    EventType.RUN_COMPLETED: ("run_finished_timestamp_seconds", {"outcome": "completed"}),
    EventType.RUN_FAILED: ("run_finished_timestamp_seconds", {"outcome": "failed"}),
    EventType.RUN_CANCELLED: ("run_finished_timestamp_seconds", {"outcome": "cancelled"}),
    EventType.CAMPAIGN_TRANSITIONED: ("campaign_transition_timestamp_seconds", {}),
}


def _state_label(event: CycleEvent) -> dict[str, str]:
    """A campaign transition is read by the state it reached; every other event by its type."""
    if event.event_type == EventType.CAMPAIGN_TRANSITIONED:
        return {"next_state": str((event.payload or {}).get("next_state") or "unknown")}
    return {}


class MetricsBridge:
    """Subscriber that forwards selective CycleEvents to MetricsPort.

    Increments a counter for each mapped lifecycle moment, records a histogram observation for
    task duration when available, and sets the run and campaign markers.
    """

    def __init__(self, metrics_port: MetricsPort) -> None:
        self._metrics = metrics_port

    def on_event(self, event: CycleEvent) -> None:
        counter_name = _COUNTER_MAP.get(event.event_type)
        if counter_name is not None:
            labels = {"entity_type": event.entity_type}
            self._metrics.counter(counter_name, labels={**labels, **_state_label(event)})

            # Record task duration histogram when available
            if event.event_type == EventType.TASK_SUCCEEDED:
                duration_ms = event.payload.get("duration_ms")
                if duration_ms is not None:
                    self._metrics.histogram(
                        "task_duration_ms",
                        value=float(duration_ms),
                        labels=labels,
                    )

        marker = _MARKER_MAP.get(event.event_type)
        if marker is not None:
            name, labels = marker
            self._metrics.gauge(
                name, event.occurred_at.timestamp(), labels={**labels, **_state_label(event)}
            )
