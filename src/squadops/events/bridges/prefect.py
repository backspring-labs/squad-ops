"""PrefectBridge — translates CycleEvent to PrefectReporter state transitions.

Maps run lifecycle events to Prefect flow run state changes. As of SIP-0087,
task-run lifecycle (creation + state transitions) lives in
``DistributedFlowExecutor._dispatch_task`` where the ``task_run_id`` is
available for correlation-context scoping and the long-task heartbeat.
The bridge still forwards terminal task-state transitions when a
``task_run_id`` is carried in the event context, but it no longer creates
task runs itself.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from squadops.events.types import EventType

if TYPE_CHECKING:
    from adapters.cycles.prefect_reporter import PrefectReporter
    from squadops.events.models import CycleEvent

logger = logging.getLogger(__name__)

# Run events → Prefect flow run state (state_type, state_name)
_RUN_STATE_MAP: dict[str, tuple[str, str]] = {
    EventType.RUN_STARTED: ("RUNNING", "Running"),
    EventType.RUN_COMPLETED: ("COMPLETED", "Completed"),
    EventType.RUN_FAILED: ("FAILED", "Failed"),
    EventType.RUN_CANCELLED: ("CANCELLED", "Cancelled"),
    EventType.RUN_PAUSED: ("PAUSED", "Paused"),
    EventType.RUN_RESUMED: ("RUNNING", "Running"),
}

# Task events → Prefect task run state (state_type, state_name)
_TASK_STATE_MAP: dict[str, tuple[str, str]] = {
    EventType.TASK_SUCCEEDED: ("COMPLETED", "Completed"),
    EventType.TASK_FAILED: ("FAILED", "Failed"),
}


class PrefectBridge:
    """Subscriber that forwards CycleEvents to PrefectReporter.

    Handles run-level state transitions and terminal task-state transitions
    (when the emitter supplies ``task_run_id`` in the event context).
    Task-run creation + ``RUNNING`` transitions are driven by
    ``_dispatch_task`` so the ``task_run_id`` is known before the handler
    starts emitting logs.
    """

    def __init__(self, prefect_reporter: PrefectReporter) -> None:
        self._prefect = prefect_reporter

    def on_event(self, event: CycleEvent) -> None:
        flow_run_id = event.context.get("flow_run_id", "")

        if event.event_type in _RUN_STATE_MAP and flow_run_id:
            state_type, state_name = _RUN_STATE_MAP[event.event_type]
            self._schedule(self._prefect.set_flow_run_state(flow_run_id, state_type, state_name))
            return

        if event.event_type in _TASK_STATE_MAP:
            task_run_id = event.context.get("task_run_id", "")
            if task_run_id:
                state_type, state_name = _TASK_STATE_MAP[event.event_type]
                self._schedule(
                    self._prefect.set_task_run_state(task_run_id, state_type, state_name)
                )
            return

    @staticmethod
    def _schedule(coro) -> None:  # noqa: ANN001
        """Schedule an async coroutine from synchronous context."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            # No running event loop — run synchronously as fallback
            asyncio.run(coro)
