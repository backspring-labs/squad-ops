"""
Task Envelope Utilities - Serialization and construction for RabbitMQ.

Constructs TaskEnvelope from canonical TaskLog fields and lineage columns,
not from metrics JSON.

Part of SIP-0.8.8 migration from _v0_legacy/agents/utils/task_envelope.py
"""

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aio_pika

from squadops.tasks.legacy_models import LegacyTaskEnvelope, Task

logger = logging.getLogger(__name__)


def serialize_envelope_to_json(envelope: LegacyTaskEnvelope) -> str:
    """
    Serialize TaskEnvelope to JSON for RabbitMQ delivery.

    Args:
        envelope: TaskEnvelope to serialize

    Returns:
        JSON string representation of the envelope
    """
    return envelope.model_dump_json()


def deserialize_envelope_from_json(json_str: str) -> LegacyTaskEnvelope:
    """
    Deserialize RabbitMQ message JSON to TaskEnvelope.

    Args:
        json_str: JSON string from RabbitMQ message

    Returns:
        TaskEnvelope object

    Raises:
        ValueError: If JSON cannot be parsed or envelope is invalid
    """
    try:
        data = json.loads(json_str)
        return LegacyTaskEnvelope(**data)
    except Exception as e:
        logger.error(f"Failed to deserialize TaskEnvelope from JSON: {e}")
        raise ValueError(f"Invalid TaskEnvelope JSON: {e}") from e


def construct_envelope_from_task(
    task: Task,
    project_id: str,
    pulse_id: str,
    correlation_id: str,
    causation_id: str,
    trace_id: str,
    span_id: str,
    task_type: str,
    inputs: dict[str, Any],
    agent_id: str | None = None,
) -> LegacyTaskEnvelope:
    """
    Construct TaskEnvelope from canonical Task and lineage columns.

    This function builds a TaskEnvelope from database Task record and
    lineage fields stored in schema columns (not metrics JSON).

    Args:
        task: Task record from database
        project_id: Project identifier from schema column
        pulse_id: Pulse identifier from schema column
        correlation_id: Correlation ID from schema column
        causation_id: Causation ID from schema column
        trace_id: Trace ID from schema column
        span_id: Span ID from schema column
        task_type: Task type from schema column
        inputs: Task inputs from schema column (JSONB)
        agent_id: Agent identifier (uses task.agent_id if not provided)

    Returns:
        TaskEnvelope with all required fields

    Raises:
        ValueError: If required fields are missing
    """
    # Use agent_id from task if not provided
    if not agent_id:
        agent_id = task.agent_id or task.agent

    # Validate required fields
    if not task.cycle_id:
        raise ValueError(f"Task {task.task_id} missing cycle_id")
    if not task_type:
        raise ValueError(f"Task {task.task_id} missing task_type")

    # Construct envelope
    envelope = LegacyTaskEnvelope(
        task_id=task.task_id,
        agent_id=agent_id,
        cycle_id=task.cycle_id,
        pulse_id=pulse_id,
        project_id=project_id,
        task_type=task_type,
        inputs=inputs,
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_id=trace_id,
        span_id=span_id,
        priority=task.priority,
        metadata={
            "task_name": task.task_name,
            "phase": task.phase,
            "description": task.description,
        },
        task_name=task.task_name,
    )

    return envelope


def validate_envelope(envelope: LegacyTaskEnvelope) -> bool:
    """
    Validate that TaskEnvelope has all required fields present.

    Args:
        envelope: TaskEnvelope to validate

    Returns:
        True if valid

    Raises:
        ValueError: If envelope is invalid
    """
    # Check required fields
    required_fields = [
        "task_id",
        "agent_id",
        "cycle_id",
        "pulse_id",
        "project_id",
        "task_type",
    ]
    for field in required_fields:
        if not getattr(envelope, field, None):
            raise ValueError(f"TaskEnvelope missing required field: {field}")

    # Check lineage fields (must be present, even if placeholders)
    lineage_fields = ["correlation_id", "causation_id", "trace_id", "span_id"]
    for field in lineage_fields:
        if not getattr(envelope, field, None):
            raise ValueError(f"TaskEnvelope missing required lineage field: {field}")

    # Check inputs exists (can be empty dict but must be present)
    if envelope.inputs is None:
        raise ValueError("TaskEnvelope inputs must be present (can be empty dict)")

    return True


async def send_envelope_to_agent_queue(
    channel: "aio_pika.Channel", agent_id: str, envelope: LegacyTaskEnvelope
) -> None:
    """
    Send TaskEnvelope to agent's RabbitMQ task queue.

    ACI v0.8: RabbitMQ messages are TaskEnvelope JSON only.

    Args:
        channel: aio_pika channel
        agent_id: Target agent identifier
        envelope: TaskEnvelope to send

    Raises:
        ValueError: If envelope is invalid
    """
    import aio_pika

    # Validate envelope before sending
    validate_envelope(envelope)

    # Serialize to JSON
    json_str = serialize_envelope_to_json(envelope)

    # Send to agent's task queue
    queue_name = f"{agent_id.lower()}_tasks"
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json_str.encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=queue_name,
    )

    logger.debug(f"Sent TaskEnvelope {envelope.task_id} to {queue_name}")
