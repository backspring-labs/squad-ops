"""MetricsBridge — translates selective CycleEvents to MetricsPort counters/histograms.

Not a full lifecycle mirror of all 20 events. Only 5 events produce counter
increments; task.succeeded with duration_ms additionally records a histogram.
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
    EventType.RUN_COMPLETED: "runs_completed_total",
    EventType.RUN_FAILED: "runs_failed_total",
    EventType.TASK_SUCCEEDED: "tasks_succeeded_total",
    EventType.TASK_FAILED: "tasks_failed_total",
}


class MetricsBridge:
    """Subscriber that forwards selective CycleEvents to MetricsPort.

    Increments counters for 5 key lifecycle transitions and records
    a histogram observation for task duration when available.
    """

    def __init__(self, metrics_port: MetricsPort) -> None:
        self._metrics = metrics_port

    def on_event(self, event: CycleEvent) -> None:
        counter_name = _COUNTER_MAP.get(event.event_type)
        if counter_name is None:
            return

        labels = {"entity_type": event.entity_type}
        self._metrics.counter(counter_name, labels=labels)

        # Record task duration histogram when available
        if event.event_type == EventType.TASK_SUCCEEDED:
            duration_ms = event.payload.get("duration_ms")
            if duration_ms is not None:
                self._metrics.histogram(
                    "task_duration_ms",
                    value=float(duration_ms),
                    labels=labels,
                )
