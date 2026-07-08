"""Task-dispatch collaborator (SIP-0097 §6.1).

Owns the request/reply transport, moved verbatim from
``DispatchedFlowExecutor``: ``dispatch_task`` / ``dispatch_with_retry`` /
``create_task_run_if_enabled`` (the callers' surface) and the internal
``_publish_and_await`` / ``_task_heartbeat`` / ``_start_task_activity`` /
``_finish_task_activity``. This is the slice-5 "transport last" extraction:
``CorrectionRunner`` and ``PulseBoundaryRunner`` now depend on this class
directly, retiring their interim executor-supplied dispatch callables
(AC#9).

Per the SIP-0097 observability ownership rule, per-task observability
(RuntimeActivity, Prefect task-run lifecycle, correlation-context scoping)
starts and finishes here.

Outcome *classification/routing* stays with the executor's orchestration
loop (§6.1): ``dispatch_with_retry`` receives the executor's routing
decision as a per-call ``handle_task_outcome`` closure and only acts on the
returned action token — the decision logic never moves.

Cancellation: the transport performs no cancellation checks of its own (it
never did — the orchestration loops check between tasks); the §6.1
cancellation probe is deliberately not wired until a dispatch-boundary
check actually exists (defer-infra-completeness). Likewise the §6.1 LLM
observability dependency: per-task generation traces are recorded
agent-side today, so the port is not taken until this class has a real use
for it.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from typing import TYPE_CHECKING

from adapters.cycles.task_naming import build_task_name
from squadops.events.types import EventType
from squadops.runtime import reasons
from squadops.tasks.models import TaskResult
from squadops.telemetry.context import use_correlation_context, use_run_ids
from squadops.telemetry.models import CorrelationContext

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from adapters.cycles.reply_router import ReplyRouter
    from squadops.cycles.models import Cycle
    from squadops.ports.comms.queue import QueuePort
    from squadops.ports.cycles.workflow_tracker import WorkflowTrackerPort
    from squadops.ports.events.cycle_event_bus import CycleEventBusPort
    from squadops.ports.runtime.activity import RuntimeActivityPort
    from squadops.tasks.models import TaskEnvelope

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """Publishes tasks to agent queues and awaits replies (SIP-0094 pattern).

    Plain injected collaborator (not a port); the executor composes a
    default from its own deps. Independently unit-testable without a
    ``DispatchedFlowExecutor`` instance.
    """

    def __init__(
        self,
        queue: QueuePort | None = None,
        reply_router: ReplyRouter | None = None,
        workflow_tracker: WorkflowTrackerPort | None = None,
        activity_port: RuntimeActivityPort | None = None,
        event_bus: CycleEventBusPort | None = None,
        task_timeout: float = 300.0,
    ) -> None:
        self._queue = queue
        self._reply_router = reply_router
        self._workflow_tracker = workflow_tracker
        self._activity_port = activity_port
        self._event_bus = event_bus
        self._task_timeout = task_timeout

    # SIP-0087: task-run lifecycle lives here (moved out of WorkflowTrackerBridge) so
    # the task_run_id is known before the agent starts producing logs.
    async def create_task_run_if_enabled(
        self,
        flow_run_id: str | None,
        envelope: TaskEnvelope,
    ) -> str | None:
        """Create a Prefect task_run + set RUNNING. Returns task_run_id or None."""
        if self._workflow_tracker is None or not flow_run_id:
            return None
        task_name = build_task_name(envelope)
        task_run_id = await self._workflow_tracker.create_task_run(
            flow_run_id, envelope.task_id, task_name
        )
        await self._workflow_tracker.set_task_run_state(task_run_id, "RUNNING", "Running")
        return task_run_id

    async def _task_heartbeat(
        self,
        envelope: TaskEnvelope,
        *,
        interval: float,
    ) -> None:
        """Log a heartbeat line every ``interval`` seconds until cancelled.

        Runs inside the task's ``use_run_ids`` scope (contextvars copy across
        ``asyncio.create_task``), so emitted records carry the active
        flow_run_id + task_run_id and land in the right Prefect pane.
        """
        start = time.monotonic()
        capability_id = (
            envelope.metadata.get("capability_id", envelope.task_type)
            if envelope.metadata
            else envelope.task_type
        )
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - start
            logger.info(
                "task_heartbeat elapsed=%.1fs capability_id=%s task_id=%s",
                elapsed,
                capability_id,
                envelope.task_id,
            )

    async def dispatch_task(
        self,
        envelope: TaskEnvelope,
        run_id: str,
        *,
        flow_run_id: str | None = None,
        task_run_id: str | None = None,
        heartbeat_interval: float = 30.0,
    ) -> TaskResult:
        """Publish task to agent queue, wait for result on reply queue.

        If ``task_run_id`` is not supplied but ``flow_run_id`` is and a
        :class:`WorkflowTrackerPort` is wired, one is created here — supports
        correction/repair paths that don't pre-create the workflow run.

        Enters a ``CorrelationContext`` scope with flow/task run IDs so the
        ``PrefectLogHandler`` scopes handler logs to the right Prefect task
        pane, and spawns a periodic heartbeat coroutine so long-running LLM
        calls show liveness in the UI.
        """
        if task_run_id is None:
            task_run_id = await self.create_task_run_if_enabled(flow_run_id, envelope)

        # SIP-0087 B1: propagate run IDs to the agent over the wire so the
        # agent's PrefectLogHandler can scope handler logs to the right task
        # pane. The agent enters use_correlation_context(...) on receipt.
        envelope = dataclasses.replace(
            envelope,
            flow_run_id=flow_run_id or "",
            task_run_id=task_run_id or "",
        )

        base_ctx = CorrelationContext.from_envelope(
            envelope,
            agent_id=envelope.agent_id or "",
            agent_role=(envelope.metadata.get("role") if envelope.metadata else None),
        )

        with (
            use_correlation_context(base_ctx),
            use_run_ids(flow_run_id=flow_run_id, task_run_id=task_run_id),
        ):
            heartbeat = asyncio.create_task(
                self._task_heartbeat(envelope, interval=heartbeat_interval),
                name=f"prefect-heartbeat-{envelope.task_id}",
            )
            # SIP-0089 §4.4: open a RuntimeActivity for this task (best-effort).
            activity_id = await self._start_task_activity(envelope)
            try:
                result = await self._publish_and_await(envelope, run_id)
            except BaseException:
                # Reply wait raised (rare — _publish_and_await usually returns a
                # FAILED TaskResult): record the task activity as failed.
                await self._finish_task_activity(activity_id, None)
                raise
            else:
                await self._finish_task_activity(activity_id, result)
                return result
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass

    async def _start_task_activity(self, envelope: TaskEnvelope) -> str | None:
        """Open a RuntimeActivity for a dispatched cycle task (§4.4, executor-side).

        Best-effort: returns the activity id, or None when disabled/failed — it
        must never raise, so observability can't break dispatch. D9 (one active
        activity per agent) is enforced by the partial unique index; a leftover
        active row from a prior crashed task makes this conflict, which we swallow.
        """
        if self._activity_port is None:
            return None
        try:
            activity = await self._activity_port.start_activity(
                envelope.agent_id,
                mode="cycle",
                activity_type=envelope.task_type,
                goal=envelope.task_name or f"{envelope.task_type} ({envelope.cycle_id})",
                source_kind="cycle_task",
                source_ref=envelope.task_id,
                cycle_id=envelope.cycle_id,
                task_id=envelope.task_id,
            )
            return activity.runtime_activity_id
        except Exception:
            logger.warning(
                "best-effort start_activity failed for task %s", envelope.task_id, exc_info=True
            )
            return None

    async def _finish_task_activity(
        self, activity_id: str | None, result: TaskResult | None
    ) -> None:
        """Terminate a task's RuntimeActivity (§4.4, executor-side, best-effort).

        SUCCEEDED → complete; anything else (FAILED/CANCELED/raised/None) → fail.
        Never raises. `update_state`'s active-only guard makes this safe even if
        the activity was already terminalized elsewhere.
        """
        if self._activity_port is None or activity_id is None:
            return
        try:
            if result is not None and result.status == "SUCCEEDED":
                await self._activity_port.complete_activity(activity_id)
            else:
                reason = (result.error if result is not None else None) or reasons.ACTIVITY_FAILED
                await self._activity_port.fail_activity(activity_id, reason)
        except Exception:
            logger.warning("best-effort finish_activity failed for %s", activity_id, exc_info=True)

    async def _publish_and_await(
        self,
        envelope: TaskEnvelope,
        run_id: str,
    ) -> TaskResult:
        """Dispatch over ``{agent_id}_comms`` and await the reply via the router.

        SIP-0094: replaces the per-run ``cycle_results_{run_id}`` polling loop
        with a long-lived per-agent subscription. The reply for ``task_id`` is
        delivered through :class:`ReplyRouter`, which resolves the future this
        method awaits.

        Invariants:
        - **Ordering (D14/#2):** ``ensure_subscribed → register → publish`` — the
          consumer is live before any reply can arrive (no first-dispatch race).
        - **No pending-future leak (#9):** every exit path — success, timeout,
          publish failure, router/await failure, cancellation — removes
          ``task_id`` from the router so it never lingers.
        """
        if self._reply_router is None:
            raise RuntimeError(
                "DispatchedFlowExecutor requires a ReplyRouter to dispatch (SIP-0094)"
            )

        reply_queue = f"{envelope.agent_id}_replies"
        queue_name = f"{envelope.agent_id}_comms"

        # Open the agent's reply subscription and register our future BEFORE
        # publishing, so a fast reply can't arrive before we're listening.
        await self._reply_router.ensure_subscribed(envelope.agent_id)
        fut = self._reply_router.register(envelope.task_id)

        message = {
            "action": "comms.task",
            "metadata": {
                "reply_queue": reply_queue,
                "correlation_id": envelope.correlation_id,
            },
            "payload": envelope.to_dict(),
        }

        # #10: if publish fails after register(), the agent never got the task —
        # drop the pending future so it doesn't leak.
        try:
            await self._queue.publish(queue_name, json.dumps(message))
        except Exception:
            self._reply_router.cancel(envelope.task_id)
            raise

        logger.info(
            "Dispatched task %s (%s) to %s, awaiting reply on %s",
            envelope.task_id,
            envelope.task_type,
            queue_name,
            reply_queue,
        )

        try:
            return await asyncio.wait_for(fut, timeout=self._task_timeout)
        except asyncio.CancelledError:
            self._reply_router.cancel(envelope.task_id)
            raise
        except TimeoutError:
            self._reply_router.cancel(envelope.task_id)
            return TaskResult(
                task_id=envelope.task_id,
                status="FAILED",
                error=f"Timed out waiting for agent {envelope.agent_id} after {self._task_timeout}s",
            )
        except Exception as exc:
            # Router-side failure surfaced via the future (e.g. a malformed
            # reply that failed TaskResult.from_dict, or ReplyRouterStopped on
            # shutdown). The future is already settled; just guard the leak.
            self._reply_router.cancel(envelope.task_id)
            return TaskResult(
                task_id=envelope.task_id,
                status="FAILED",
                error=f"Reply wait for agent {envelope.agent_id} failed: {exc}",
            )

    async def dispatch_with_retry(
        self,
        enriched: TaskEnvelope,
        envelope: TaskEnvelope,
        cycle: Cycle,
        run_id: str,
        *,
        flow_run_id: str | None = None,
        task_run_id: str | None = None,
        handle_task_outcome: Callable[[TaskResult], Awaitable[str]],
    ) -> tuple[bool, TaskResult]:
        """Dispatch a task with retry loop for retryable failures.

        Returns (task_succeeded, result). Raises on unrecoverable failures.

        ``handle_task_outcome`` is the executor's routing decision bound as a
        closure over its orchestration state (§6.1: classification/routing
        stays with the orchestration loop). This method only acts on the
        returned action token: "continue" retries the same task,
        "break_correction" returns to advance past a corrected failure.
        """
        while True:
            result = await self.dispatch_task(
                enriched,
                run_id,
                flow_run_id=flow_run_id,
                task_run_id=task_run_id,
            )

            # SIP-0087: task_run_id carried in context so the bridge can set
            # terminal Prefect state without owning the ID.
            task_context = {
                "cycle_id": cycle.cycle_id,
                "run_id": run_id,
                "task_run_id": task_run_id or "",
            }
            if result.status == "SUCCEEDED":
                self._event_bus.emit(
                    EventType.TASK_SUCCEEDED,
                    entity_type="task",
                    entity_id=envelope.task_id,
                    context=task_context,
                    payload={"task_type": envelope.task_type},
                )
            else:
                self._event_bus.emit(
                    EventType.TASK_FAILED,
                    entity_type="task",
                    entity_id=envelope.task_id,
                    context=task_context,
                    payload={
                        "task_type": envelope.task_type,
                        "error": result.error or "",
                    },
                )

            if result.status != "SUCCEEDED":
                action = await handle_task_outcome(result)

                if action == "continue":
                    continue  # retry same task
                elif action == "break_correction":
                    return False, result

                # "raise" actions handled inside handle_task_outcome

            return True, result
