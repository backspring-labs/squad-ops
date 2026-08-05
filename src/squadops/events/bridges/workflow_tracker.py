"""WorkflowTrackerBridge — translates CycleEvent to WorkflowTrackerPort state transitions.

Maps run lifecycle events to flow-run state changes. The ENTIRE task-run
lifecycle (creation, per-attempt ``RUNNING``, terminal state) lives in
``TaskDispatcher.dispatch_task`` (#506, completing the SIP-0097 rule that
per-task observability starts and finishes in the transport) — the bridge
acting on terminal task events was a second writer of the same state, and
its event-context ``task_run_id`` was blank on exactly the paths that
needed it (retry re-attempts, internally-created ids).

The class name is retained for parity with :class:`LangFuseBridge`, but the
bridge depends on the vendor-neutral :class:`WorkflowTrackerPort` and works
with any compliant adapter (including :class:`NoOpWorkflowTracker`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from squadops.events.types import EventType

if TYPE_CHECKING:
    from squadops.events.models import CycleEvent
    from squadops.ports.cycles import WorkflowTrackerPort

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


class WorkflowTrackerBridge:
    """Subscriber that forwards CycleEvents to a :class:`WorkflowTrackerPort`.

    Handles run-level (flow-run) state transitions only. Task-run lifecycle
    is transport-owned in ``TaskDispatcher.dispatch_task`` (#506).
    """

    def __init__(self, workflow_tracker: WorkflowTrackerPort) -> None:
        self._tracker = workflow_tracker

    def on_event(self, event: CycleEvent) -> None:
        flow_run_id = event.context.get("flow_run_id", "")

        if event.event_type in _RUN_STATE_MAP and flow_run_id:
            state_type, state_name = _RUN_STATE_MAP[event.event_type]
            self._schedule(self._tracker.set_flow_run_state(flow_run_id, state_type, state_name))

    @staticmethod
    def _schedule(coro) -> None:  # noqa: ANN001
        """Schedule an async coroutine from synchronous context."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            # No running event loop — run synchronously as fallback
            asyncio.run(coro)
