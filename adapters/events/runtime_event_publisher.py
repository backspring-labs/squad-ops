"""Logging-backed `RuntimeEventPublisher` adapter (SIP-0089 §2.6).

The `RuntimeCoordinator` and `DutyScheduler` emit runtime-state events
(`runtime_state.mode_transition`, `assignment.window.skipped`, …) through the
`RuntimeEventPublisher` port. This adapter records each one as a structured log
record so an activated scheduler's transitions are observable in runtime-api
logs (which SIP-0087 forwards) without coupling the runtime layer to any
particular sink.

Runtime-state events are a **separate vocabulary** from the locked cycle-event
taxonomy (D14/D18), so they are deliberately *not* bridged onto
`CycleEventBusPort`. A durable/console sink can replace this adapter behind the
same port later.

Per the port contract, `emit` is best-effort and never raises to the caller —
a logging failure must not turn a successful mode transition into an error.
"""

from __future__ import annotations

import logging

from squadops.ports.runtime.event_publisher import RuntimeEventPublisher

logger = logging.getLogger("squadops.runtime.events")


class LoggingRuntimeEventPublisher(RuntimeEventPublisher):
    """Emit runtime-state events as structured log records (best-effort)."""

    def emit(
        self,
        event_name: str,
        *,
        agent_id: str,
        reason_code: str,
        payload: dict | None = None,
    ) -> None:
        try:
            logger.info(
                "runtime event %s for %s (reason=%s)",
                event_name,
                agent_id,
                reason_code,
                extra={
                    "runtime_event": event_name,
                    "agent_id": agent_id,
                    "reason_code": reason_code,
                    "payload": payload or {},
                },
            )
        except Exception:  # best-effort (D22): emission must never break the caller
            logger.debug("runtime event emission failed", exc_info=True)
