"""
Platform health routes — infra probes + agent status.

Replaces the legacy health-check service endpoints with routes
served directly from runtime-api.

Read-only lane: /health/* is unauthenticated (middleware allowlist), so only
GET probes may live here. Agent-status writes are on the authed /api/v1 lane
(routes/agent_status.py, #326).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from squadops.api.runtime.agent_labels import get_role_label

router = APIRouter(prefix="/health", tags=["platform-health"])


def _get_health_checker():
    from squadops.api.runtime.deps import get_health_checker

    return get_health_checker()


@router.get("/infra")
async def health_infra():
    """Run all infrastructure probes concurrently."""
    hc = _get_health_checker()
    results = await asyncio.gather(
        hc.check_rabbitmq(),
        hc.check_postgres(),
        hc.check_redis(),
        hc.check_prefect(),
        hc.check_prometheus(),
        hc.check_grafana(),
        hc.check_otel_collector(),
        hc.check_langfuse(),
        hc.check_keycloak(),
    )
    return list(results)


@router.get("/agents")
async def health_agents():
    """Get agent health status."""
    hc = _get_health_checker()
    return await hc.get_agent_status()


@router.get("/agents/status/{agent_id}")
async def get_agent_status_by_id(agent_id: str):
    """Get a single agent's status."""
    hc = _get_health_checker()
    try:
        async with hc.pg_pool.acquire() as conn:
            # LEFT JOIN the SIP-0089 runtime row so the single-agent route carries
            # posture (mode) + the canonical health signal (runtime_status), at
            # parity with GET /health/agents (#230). network_status stays as a
            # legacy/back-compat field only — health is runtime_status (#231).
            row = await conn.fetchrow(
                "SELECT s.agent_id, s.lifecycle_state, s.version, s.tps, "
                "s.memory_count, s.last_heartbeat, s.current_task_id, "
                "r.mode, r.runtime_status "
                "FROM agent_status s "
                "LEFT JOIN agent_runtime_state r ON r.agent_id = s.agent_id "
                "WHERE s.agent_id = $1",
                agent_id.lower(),
            )
        if not row:
            raise HTTPException(status_code=404, detail=f"Agent status {agent_id} not found")

        network_status = hc._compute_network_status(row["last_heartbeat"])
        lifecycle_state = (
            "UNKNOWN" if network_status == "offline" else (row["lifecycle_state"] or "UNKNOWN")
        )

        instances = hc._load_instances()
        info = instances.get(row["agent_id"], {})
        role = info.get("role", "unknown")

        return {
            "agent_id": row["agent_id"],
            "agent_name": hc._get_display_name(row["agent_id"]),
            "role": role,
            "role_label": get_role_label(role),
            # SIP-0089 posture + canonical health (None when no runtime row) — #231
            "mode": row["mode"],
            "runtime_status": row["runtime_status"],
            # Legacy/back-compat — derived from heartbeat age; do not depend on it (#231).
            "network_status": network_status,
            "lifecycle_state": lifecycle_state,
            "version": row["version"],
            "tps": row["tps"],
            "memory_count": row.get("memory_count", 0) or 0,
            "last_seen": (
                row["last_heartbeat"].isoformat() + "Z" if row["last_heartbeat"] else None
            ),
            "current_task_id": row["current_task_id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {e}") from e


@router.get("/agents/{agent_id}/runtime-state")
async def get_agent_runtime_state(agent_id: str):
    """Return the SIP-0089 AgentRuntimeState for an agent.

    Returns 404 if no row exists yet (agent has not heartbeated since the
    runtime-state migration applied).
    """
    hc = _get_health_checker()
    try:
        # Normalize case to match the sibling /agents/status/{agent_id} route,
        # which lower-cases agent_id; rows are stored lower-cased.
        state = await hc.get_runtime_state(agent_id.lower())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read runtime state: {e}") from e
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"No runtime state for agent_id={agent_id}",
        )
    return state


@router.get("/agents/{agent_id}/activity")
async def get_agent_current_activity(agent_id: str):
    """Return the agent's current (active) RuntimeActivity (SIP-0089 §4.7).

    Returns 404 when the agent has no active activity (idle), or when the
    runtime-api has no RuntimeActivityPort wired.
    """
    hc = _get_health_checker()
    try:
        activity = await hc.get_current_activity(agent_id.lower())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read activity: {e}") from e
    if activity is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active activity for agent_id={agent_id}",
        )
    return activity


# NOTE: POST /health/agents/status and PUT /health/agents/status/{agent_id}
# moved to /api/v1/agents/status (routes/agent_status.py) in #326 — /health is
# the unauthenticated lane and must stay read-only.
