"""
Map agent lifecycle_state → runtime_status for SIP-0089 heartbeat integration.

`lifecycle_state` is the existing agent-status vocabulary used by
`HealthChecker` and the `/health/agents/status` endpoint. `runtime_status`
is the SIP-0089 §10.5 health vocabulary on `agent_runtime_state`.

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

    Returns `None` for unknown values so callers can skip the runtime-state
    update entirely rather than write a default that would mask drift.
    """
    return _LIFECYCLE_TO_RUNTIME_STATUS.get(lifecycle_state)
