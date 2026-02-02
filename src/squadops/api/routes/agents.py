"""
Agent status and lifecycle routes.

Part of SIP-0.8.9 Health Check refactor.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from squadops.api.health_app import HealthChecker

router = APIRouter(prefix="/health/agents", tags=["agents"])

# Will be injected at startup
_health_checker: "HealthChecker | None" = None


def init_routes(health_checker: "HealthChecker") -> None:
    """Initialize routes with dependencies."""
    global _health_checker
    _health_checker = health_checker


# Pydantic models for Agent Status
class AgentStatusCreate(BaseModel):
    """Agent status creation/update request."""

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
    """Agent status update request."""

    lifecycle_state: str | None = None
    current_task_id: str | None = None
    version: str | None = None
    tps: int | None = None
    memory_count: int | None = None


@router.get("")
async def health_agents():
    """Get agent health status"""
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    agents = await _health_checker.get_agent_status()
    return agents


@router.post("/status")
async def create_or_update_agent_status(agent_status: AgentStatusCreate):
    """Create or update agent status (heartbeat endpoint)

    SIP-Agent-Lifecycle: Accepts agent_id and lifecycle_state from agent.
    Ignores any status or network_status fields (agents don't send these).
    """
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    try:
        # Use agent_id (required), ignore deprecated agent_name if present
        agent_id = agent_status.agent_id
        if agent_status.agent_name and not agent_id:
            agent_id = agent_status.agent_name.lower()

        # Validate lifecycle_state
        valid_states = ["STARTING", "READY", "WORKING", "BLOCKED", "CRASHED", "STOPPING"]
        if agent_status.lifecycle_state not in valid_states:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid lifecycle_state: {agent_status.lifecycle_state}. Must be one of {valid_states}",
            )

        result = await _health_checker.update_agent_status_in_db(
            {
                "agent_id": agent_id,
                "lifecycle_state": agent_status.lifecycle_state,
                "current_task_id": agent_status.current_task_id,
                "version": agent_status.version,
                "tps": agent_status.tps,
                "memory_count": agent_status.memory_count,
            }
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update agent status: {str(e)}"
        ) from e


@router.put("/status/{agent_id}")
async def update_agent_status(agent_id: str, update: AgentStatusUpdate):
    """Update agent status fields

    SIP-Agent-Lifecycle: Uses agent_id instead of agent_name.
    network_status is derived by Health Check, not updated directly.
    """
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    try:
        if not _health_checker.pg_pool:
            await _health_checker.init_connections()

        updates = []
        params = []
        param_count = 1

        if update.lifecycle_state:
            updates.append(f"lifecycle_state = ${param_count}")
            params.append(update.lifecycle_state)
            param_count += 1

        if update.current_task_id is not None:
            updates.append(f"current_task_id = ${param_count}")
            params.append(update.current_task_id)
            param_count += 1

        if update.version:
            updates.append(f"version = ${param_count}")
            params.append(update.version)
            param_count += 1

        if update.tps is not None:
            updates.append(f"tps = ${param_count}")
            params.append(update.tps)
            param_count += 1

        if update.memory_count is not None:
            updates.append(f"memory_count = ${param_count}")
            params.append(update.memory_count)
            param_count += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updates.append(f"last_heartbeat = ${param_count}")
        params.append(datetime.utcnow())
        param_count += 1
        updates.append(f"updated_at = ${param_count}")
        params.append(datetime.utcnow())
        param_count += 1

        params.append(agent_id.lower())
        query = f"UPDATE agent_status SET {', '.join(updates)} WHERE agent_id = ${param_count}"

        async with _health_checker.pg_pool.acquire() as conn:
            result = await conn.execute(query, *params)
            if result == "UPDATE 0":
                raise HTTPException(
                    status_code=404, detail=f"Agent status {agent_id} not found"
                )

        return {"status": "updated", "agent_id": agent_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update agent status: {str(e)}"
        ) from e


@router.get("/status/{agent_id}")
async def get_agent_status_by_id(agent_id: str):
    """Get agent status by agent_id

    SIP-Agent-Lifecycle: Uses agent_id instead of agent_name.
    Returns network_status (derived) and lifecycle_state.
    """
    if not _health_checker:
        raise RuntimeError("Health checker not initialized")

    try:
        if not _health_checker.pg_pool:
            await _health_checker.init_connections()

        async with _health_checker.pg_pool.acquire() as conn:
            status = await conn.fetchrow(
                """
                SELECT agent_id, lifecycle_state, network_status, version, tps, memory_count, last_heartbeat, current_task_id
                FROM agent_status WHERE agent_id = $1
            """,
                agent_id.lower(),
            )

            if not status:
                raise HTTPException(
                    status_code=404, detail=f"Agent status {agent_id} not found"
                )

            # Derive network_status from last_heartbeat timing
            network_status = _health_checker._compute_network_status(status["last_heartbeat"])

            # Get lifecycle_state: UNKNOWN if offline, otherwise use stored value
            if network_status == "offline":
                lifecycle_state = "UNKNOWN"
            else:
                lifecycle_state = (
                    status["lifecycle_state"] if status["lifecycle_state"] else "UNKNOWN"
                )

            # Get display name from instances.yaml
            agent_name = _health_checker._get_display_name(status["agent_id"])

            return {
                "agent_id": status["agent_id"],
                "agent_name": agent_name,
                "network_status": network_status,
                "lifecycle_state": lifecycle_state,
                "version": status["version"],
                "tps": status["tps"],
                "memory_count": status.get("memory_count", 0) or 0,
                "last_seen": status["last_heartbeat"].isoformat() + "Z"
                if status["last_heartbeat"]
                else None,
                "current_task_id": status["current_task_id"],
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get agent status: {str(e)}"
        ) from e
