"""PrefectBridge — translates CycleEvent to PrefectReporter state transitions.

Maps run and task lifecycle events to Prefect flow/task run state changes.
PrefectReporter methods are async; this bridge uses asyncio to schedule them
from the synchronous on_event() callback.
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

    Handles run lifecycle → flow run state transitions and
    task lifecycle → task run creation + state transitions.

    Duplicate ``task.dispatched`` events for the same ``(run_id, task_id)``
    are detected and ignored with a warning log.
    """

    def __init__(self, prefect_reporter: PrefectReporter) -> None:
        self._prefect = prefect_reporter
        self._dispatched_tasks: dict[tuple[str, str], str] = {}  # (run_id, task_id) → task_run_id

    def on_event(self, event: CycleEvent) -> None:
        run_id = event.context.get("run_id", "")
        flow_run_id = event.context.get("flow_run_id", "")

        # Run state transitions
        if event.event_type in _RUN_STATE_MAP and flow_run_id:
            state_type, state_name = _RUN_STATE_MAP[event.event_type]
            self._schedule(self._prefect.set_flow_run_state(flow_run_id, state_type, state_name))
            return

        # Task dispatched → create task run + set RUNNING
        if event.event_type == EventType.TASK_DISPATCHED:
            task_key = event.entity_id
            dedup_key = (run_id, task_key)

            if dedup_key in self._dispatched_tasks:
                logger.warning(
                    "Duplicate task.dispatched for (%s, %s) — ignoring",
                    run_id,
                    task_key,
                )
                return

            task_name = event.payload.get("task_name", task_key)
            if flow_run_id:
                task_run_id = self._schedule_with_result(
                    self._prefect.create_task_run(flow_run_id, task_key, task_name)
                )
                self._dispatched_tasks[dedup_key] = task_run_id
                self._schedule(self._prefect.set_task_run_state(task_run_id, "RUNNING", "Running"))
            return

        # Task succeeded/failed → set task run state
        if event.event_type in _TASK_STATE_MAP:
            task_key = event.entity_id
            dedup_key = (run_id, task_key)
            task_run_id = self._dispatched_tasks.get(dedup_key)

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

    @staticmethod
    def _schedule_with_result(coro) -> str:  # noqa: ANN001
        """Run an async coroutine and return its result."""
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, we can't await directly from sync.
            # Use run_coroutine_threadsafe for thread-safe scheduling, but
            # since PrefectReporter is best-effort, we run in a new loop as fallback.
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=10)
        except RuntimeError:
            return asyncio.run(coro)
