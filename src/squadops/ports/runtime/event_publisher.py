"""
RuntimeEventPublisher — abstract seam for runtime-state event publication (SIP-0089 D22).

The coordinator (§2.6) emits mode-transition events through this port rather than
importing an event bridge directly (D26 forbids `runtime/* → events/bridges/*`).
Mirrors the best-effort contract of `CycleEventBusPort`: `emit` is non-blocking
and not part of the caller's success criteria — emission failure is never an
application error.

`event_name` comes from `squadops.runtime.events`; `reason_code` from
`squadops.runtime.reasons`. The two are kept as separate arguments because D18
requires events (what happened) and reasons (why) to stay distinct.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RuntimeEventPublisher(ABC):
    """Port for runtime-state event publication (best-effort)."""

    @abstractmethod
    def emit(
        self,
        event_name: str,
        *,
        agent_id: str,
        reason_code: str,
        payload: dict | None = None,
    ) -> None:
        """Publish a runtime event for `agent_id`. Best-effort; never raises to the caller."""
