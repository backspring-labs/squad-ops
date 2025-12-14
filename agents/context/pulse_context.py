"""
PulseContext - Formal context abstraction for coordinating multi-agent work

PulseContext represents a coherent unit of work inside a Cycle, typically:
- A group of related tasks
- Often involving multiple agents
- Aligned to a short-term objective

PulseContext is persisted in CycleDataStore at:
cycle_data/{project_id}/{cycle_id}/pulses/{pulse_id}/pulse_context.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agents.cycle_data import CycleDataStore
from config.unified_config import get_config

logger = logging.getLogger(__name__)


class PulseContext(BaseModel):
    """
    Pulse Context model - shared context for a pulse of work within a cycle.

    A Pulse is a coherent unit of work inside a Cycle, typically:
    - A group of related tasks
    - Often involving multiple agents
    - Aligned to a short-term objective
    """

    pulse_id: str = Field(..., description="Unique pulse identifier within a cycle")
    cycle_id: str = Field(..., description="Execution cycle identifier")
    name: str = Field(..., description="Human-readable pulse name")
    description: str = Field(..., description="Short description of the pulse objective")
    agents_involved: list[str] = Field(
        default_factory=list, description="Agent IDs or roles participating in this pulse"
    )
    task_ids: list[str] = Field(
        default_factory=list, description="Task identifiers associated with this pulse"
    )
    artifacts: dict[str, Any] = Field(
        default_factory=dict,
        description="References to artifacts produced/consumed within the pulse",
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional constraints (time bounds, guards, resource limits)",
    )
    acceptance_criteria: dict[str, Any] = Field(
        default_factory=dict, description="Optional criteria describing when the pulse is 'done'"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Free-form metadata for future extensions"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


async def _get_cycle_data_store_async(
    cycle_id: str, project_id: str | None = None
) -> CycleDataStore:
    """
    Get CycleDataStore instance for a cycle (async version).

    Args:
        cycle_id: Execution cycle identifier
        project_id: Optional project identifier (will be fetched from cycle if not provided)

    Returns:
        CycleDataStore instance
    """
    config = get_config()
    cycle_data_root = config.get_cycle_data_root()

    # If project_id not provided, try to get it from the cycle
    if not project_id:
        # Default to warmboot_selftest if we can't determine project
        project_id = "warmboot_selftest"

        # Try to get project_id from cycle in database
        try:
            from agents.tasks.registry import get_tasks_adapter

            # Get adapter and fetch cycle
            adapter = await get_tasks_adapter()
            flow = await adapter.get_flow(cycle_id)
            if flow and flow.project_id:
                project_id = flow.project_id
        except Exception as e:
            logger.debug(f"Could not determine project_id for cycle {cycle_id}: {e}")

    return CycleDataStore(cycle_data_root, project_id, cycle_id)


def _get_cycle_data_store(cycle_id: str, project_id: str | None = None) -> CycleDataStore:
    """
    Get CycleDataStore instance for a cycle (sync version, uses default project_id).

    Args:
        cycle_id: Execution cycle identifier
        project_id: Optional project identifier

    Returns:
        CycleDataStore instance
    """
    config = get_config()
    cycle_data_root = config.get_cycle_data_root()

    # Use provided project_id or default
    if not project_id:
        project_id = "warmboot_selftest"

    return CycleDataStore(cycle_data_root, project_id, cycle_id)


def _get_pulse_path(cycle_store: CycleDataStore, pulse_id: str) -> Path:
    """
    Get the path to a pulse's directory.

    Args:
        cycle_store: CycleDataStore instance
        pulse_id: Pulse identifier

    Returns:
        Path to pulse directory
    """
    cycle_path = cycle_store.get_cycle_path()
    pulse_path = cycle_path / "pulses" / pulse_id
    pulse_path.mkdir(parents=True, exist_ok=True)
    return pulse_path


async def create_pulse_context(
    pulse_id: str,
    cycle_id: str,
    name: str,
    description: str,
    project_id: str | None = None,
    agents_involved: list[str] | None = None,
    task_ids: list[str] | None = None,
    artifacts: dict[str, Any] | None = None,
    constraints: dict[str, Any] | None = None,
    acceptance_criteria: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> PulseContext:
    """
    Create a new PulseContext and persist it to CycleDataStore.

    Args:
        pulse_id: Unique pulse identifier within the cycle
        cycle_id: Execution cycle identifier
        name: Human-readable pulse name
        description: Short description of the pulse objective
        project_id: Optional project identifier
        agents_involved: Optional list of agent IDs or roles
        task_ids: Optional list of task identifiers
        artifacts: Optional artifact references
        constraints: Optional constraints
        acceptance_criteria: Optional acceptance criteria
        metadata: Optional free-form metadata

    Returns:
        Created PulseContext
    """
    pulse_context = PulseContext(
        pulse_id=pulse_id,
        cycle_id=cycle_id,
        name=name,
        description=description,
        agents_involved=agents_involved or [],
        task_ids=task_ids or [],
        artifacts=artifacts or {},
        constraints=constraints or {},
        acceptance_criteria=acceptance_criteria or {},
        metadata=metadata or {},
    )

    # Persist to CycleDataStore
    cycle_store = await _get_cycle_data_store_async(cycle_id, project_id)
    pulse_path = _get_pulse_path(cycle_store, pulse_id)

    # Write pulse_context.json
    pulse_context_file = pulse_path / "pulse_context.json"
    pulse_context_file.write_text(pulse_context.model_dump_json(indent=2), encoding="utf-8")

    logger.info(f"Created PulseContext {pulse_id} for cycle {cycle_id}")
    return pulse_context


async def load_pulse_context(
    pulse_id: str,
    cycle_id: str,
    project_id: str | None = None,
) -> PulseContext | None:
    """
    Load an existing PulseContext from CycleDataStore.

    Args:
        pulse_id: Pulse identifier
        cycle_id: Execution cycle identifier
        project_id: Optional project identifier

    Returns:
        PulseContext if found, None otherwise
    """
    try:
        cycle_store = await _get_cycle_data_store_async(cycle_id, project_id)
        pulse_path = _get_pulse_path(cycle_store, pulse_id)
        pulse_context_file = pulse_path / "pulse_context.json"

        if not pulse_context_file.exists():
            logger.debug(f"PulseContext {pulse_id} not found for cycle {cycle_id}")
            return None

        # Read and parse JSON
        content = pulse_context_file.read_text(encoding="utf-8")
        data = json.loads(content)

        # Parse datetime fields
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

        pulse_context = PulseContext(**data)
        logger.debug(f"Loaded PulseContext {pulse_id} for cycle {cycle_id}")
        return pulse_context
    except Exception as e:
        logger.error(f"Failed to load PulseContext {pulse_id} for cycle {cycle_id}: {e}")
        return None


async def update_pulse_context(
    pulse_context: PulseContext,
    **updates: Any,
) -> PulseContext:
    """
    Update an existing PulseContext and persist changes.

    Args:
        pulse_context: Existing PulseContext to update
        **updates: Fields to update (agents_involved, task_ids, artifacts, etc.)

    Returns:
        Updated PulseContext
    """
    # Update fields
    for key, value in updates.items():
        if hasattr(pulse_context, key):
            setattr(pulse_context, key, value)

    # Update timestamp
    pulse_context.updated_at = datetime.utcnow()

    # Persist to CycleDataStore
    cycle_store = await _get_cycle_data_store_async(pulse_context.cycle_id)
    pulse_path = _get_pulse_path(cycle_store, pulse_context.pulse_id)

    # Write updated pulse_context.json
    pulse_context_file = pulse_path / "pulse_context.json"
    pulse_context_file.write_text(pulse_context.model_dump_json(indent=2), encoding="utf-8")

    logger.debug(
        f"Updated PulseContext {pulse_context.pulse_id} for cycle {pulse_context.cycle_id}"
    )
    return pulse_context


async def list_pulses_for_cycle(
    cycle_id: str,
    project_id: str | None = None,
) -> list[PulseContext]:
    """
    List all pulses for a given cycle.

    Args:
        cycle_id: Execution cycle identifier
        project_id: Optional project identifier

    Returns:
        List of PulseContext objects
    """
    try:
        cycle_store = await _get_cycle_data_store_async(cycle_id, project_id)
        cycle_path = cycle_store.get_cycle_path()
        pulses_dir = cycle_path / "pulses"

        if not pulses_dir.exists():
            return []

        pulse_contexts = []
        for pulse_dir in pulses_dir.iterdir():
            if pulse_dir.is_dir():
                pulse_id = pulse_dir.name
                pulse_context = await load_pulse_context(pulse_id, cycle_id, project_id)
                if pulse_context:
                    pulse_contexts.append(pulse_context)

        logger.debug(f"Found {len(pulse_contexts)} pulses for cycle {cycle_id}")
        return pulse_contexts
    except Exception as e:
        logger.error(f"Failed to list pulses for cycle {cycle_id}: {e}")
        return []
