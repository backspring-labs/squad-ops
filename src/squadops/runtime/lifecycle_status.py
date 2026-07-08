"""
Map agent lifecycle_state → runtime_status for SIP-0089 heartbeat integration.

`lifecycle_state` is the existing agent-status vocabulary used by
`HealthChecker` and the `/api/v1/agents/status` heartbeat endpoint (#326).
`runtime_status` is the SIP-0089 §10.5 health vocabulary on
`agent_runtime_state`.

The mapping is locked v1.1 per §1.0 spike normalization. Server-side
timeout detection (last_heartbeat_at older than N seconds → offline) is
handled by the existing reconciliation loop, not this mapper.
"""

from __future__ import annotations

from typing import Final

_LIFECYCLE_TO_RUNTIME_STATUS: Final[dict[str, str]] = {
    "STARTING": "recovering",
    "READY": "online",
    "WORKING": "online",
    "BLOCKED": "degraded",
    "CRASHED": "offline",
    "STOPPING": "recovering",
}


def runtime_status_from_lifecycle(lifecycle_state: str) -> str | None:
    """Return the SIP-0089 `runtime_status` for an agent `lifecycle_state`.

    Returns `None` for an unmapped `lifecycle_state`. Callers still ensure the
    runtime row exists (#305 Part A — `runtime_status` must never be None at the
    read surfaces); a `None` here means only "don't overwrite the stored status"
    (the row's existing value is kept via COALESCE, and reconciliation owns offline).
    """
    return _LIFECYCLE_TO_RUNTIME_STATUS.get(lifecycle_state)
