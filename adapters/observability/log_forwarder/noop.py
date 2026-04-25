"""NoOp log forwarder — the always-inject default.

Used by :func:`create_log_forwarder` whenever no log-forwarding backend is
configured (or its config is disabled). Lets core composition roots call
``await port.aclose()`` unconditionally without branching on enablement.
"""

from __future__ import annotations

from squadops.ports.observability.log_forwarder import LogForwarderPort


class NoOpLogForwarder(LogForwarderPort):
    """Does nothing. Safe to ``aclose()`` multiple times."""

    async def aclose(self) -> None:
        return None
