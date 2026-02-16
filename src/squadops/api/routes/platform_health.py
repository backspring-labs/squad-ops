"""
Platform health routes — infra probes + agent status.

Replaces the legacy health-check service endpoints with routes
served directly from runtime-api.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["platform-health"])


class AgentStatusCreate(BaseModel):
    agent_id: str
    lifecycle_state: str
    current_task_id: str | None = None
    version: str | None = None
    tps: int = 0
    memory_count: int | None = None
    # Deprecated fields (ignored if present)
    agent_name: str | None = None
    status: str | None = None
    network_status: str | None = None


class AgentStatusUpdate(BaseModel):
    lifecycle_state: str | None = None
    current_task_id: str | None = None
    version: str | None = None
    tps: int | None = None
    memory_count: int | None = None


_VALID_LIFECYCLE_STATES = {"STARTING", "READY", "WORKING", "BLOCKED", "CRASHED", "STOPPING"}


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
            row = await conn.fetchrow(
                "SELECT agent_id, lifecycle_state, network_status, version, tps, "
                "memory_count, last_heartbeat, current_task_id "
                "FROM agent_status WHERE agent_id = $1",
                agent_id.lower(),
            )
        if not row:
            raise HTTPException(status_code=404, detail=f"Agent status {agent_id} not found")

        network_status = hc._compute_network_status(row["last_heartbeat"])
        lifecycle_state = (
            "UNKNOWN" if network_status == "offline" else (row["lifecycle_state"] or "UNKNOWN")
        )

        return {
            "agent_id": row["agent_id"],
            "agent_name": hc._get_display_name(row["agent_id"]),
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


@router.post("/agents/status")
async def create_or_update_agent_status(agent_status: AgentStatusCreate):
    """Create or update agent status (heartbeat endpoint)."""
    hc = _get_health_checker()
    agent_id = agent_status.agent_id
    if agent_status.agent_name and not agent_id:
        agent_id = agent_status.agent_name.lower()

    if agent_status.lifecycle_state not in _VALID_LIFECYCLE_STATES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid lifecycle_state: {agent_status.lifecycle_state}. "
                f"Must be one of {sorted(_VALID_LIFECYCLE_STATES)}"
            ),
        )

    try:
        return await hc.update_agent_status_in_db(
            {
                "agent_id": agent_id,
                "lifecycle_state": agent_status.lifecycle_state,
                "current_task_id": agent_status.current_task_id,
                "version": agent_status.version,
                "tps": agent_status.tps,
                "memory_count": agent_status.memory_count,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent status: {e}") from e


@router.put("/agents/status/{agent_id}")
async def update_agent_status(agent_id: str, update: AgentStatusUpdate):
    """Update agent status fields."""
    hc = _get_health_checker()

    updates = []
    params: list = []
    idx = 1

    if update.lifecycle_state:
        updates.append(f"lifecycle_state = ${idx}")
        params.append(update.lifecycle_state)
        idx += 1
    if update.current_task_id is not None:
        updates.append(f"current_task_id = ${idx}")
        params.append(update.current_task_id)
        idx += 1
    if update.version:
        updates.append(f"version = ${idx}")
        params.append(update.version)
        idx += 1
    if update.tps is not None:
        updates.append(f"tps = ${idx}")
        params.append(update.tps)
        idx += 1
    if update.memory_count is not None:
        updates.append(f"memory_count = ${idx}")
        params.append(update.memory_count)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = datetime.utcnow()
    updates.append(f"last_heartbeat = ${idx}")
    params.append(now)
    idx += 1
    updates.append(f"updated_at = ${idx}")
    params.append(now)
    idx += 1

    params.append(agent_id.lower())
    query = f"UPDATE agent_status SET {', '.join(updates)} WHERE agent_id = ${idx}"

    try:
        async with hc.pg_pool.acquire() as conn:
            result = await conn.execute(query, *params)
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail=f"Agent status {agent_id} not found")
        return {"status": "updated", "agent_id": agent_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent status: {e}") from e
