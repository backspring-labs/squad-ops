"""API Mapping Functions.

Map between API DTOs (Pydantic) and internal domain models (frozen dataclasses).

Part of SIP-0.8.8.
"""

from datetime import UTC, datetime
from typing import Any

from squadops.api.schemas import TaskRequestDTO, TaskResponseDTO, TaskResultDTO
from squadops.core.lineage import new_id, new_span_id, new_trace_id
from squadops.tasks.models import TaskEnvelope, TaskResult


def dto_to_envelope(
    dto: TaskRequestDTO,
    task_id: str | None = None,
    agent_id: str | None = None,
    cycle_id: str | None = None,
    pulse_id: str | None = None,
    project_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> TaskEnvelope:
    """Map API DTO to internal frozen dataclass at ingress.

    Args:
        dto: Task request DTO from API
        task_id: Optional task ID (generated if not provided)
        agent_id: Agent ID (defaults to source_agent from DTO)
        cycle_id: Cycle ID (generated if not provided)
        pulse_id: Pulse ID (generated if not provided)
        project_id: Project ID (generated if not provided)
        correlation_id: Correlation ID (generated if not provided)
        causation_id: Causation ID (generated if not provided)
        trace_id: Trace ID (a fresh 32-hex trace if not provided, #575)
        span_id: Span ID (a fresh 16-hex span if not provided)

    Returns:
        TaskEnvelope frozen dataclass for internal use
    """
    # Generate IDs if not provided — whole ids and a real trace context (#575)
    generated_task_id = task_id or new_id("task")
    generated_cycle_id = cycle_id or new_id("cycle")

    return TaskEnvelope(
        task_id=generated_task_id,
        agent_id=agent_id or dto.source_agent,
        cycle_id=generated_cycle_id,
        pulse_id=pulse_id or new_id("pulse"),
        project_id=project_id or new_id("project"),
        task_type=dto.task_type,
        correlation_id=correlation_id or f"corr-{generated_cycle_id}",
        causation_id=causation_id or f"cause-{generated_task_id}",
        trace_id=trace_id or new_trace_id(),
        span_id=span_id or new_span_id(),
        inputs=dto.inputs,
        priority=str(dto.priority) if dto.priority else None,
        timeout=dto.timeout,
        metadata=dto.metadata,
        task_name=dto.task_name,
    )


def envelope_to_response(
    envelope: TaskEnvelope,
    created_at: datetime | None = None,
) -> TaskResponseDTO:
    """Map internal dataclass to API response at egress.

    Args:
        envelope: TaskEnvelope from internal processing
        created_at: Optional creation timestamp (defaults to now)

    Returns:
        TaskResponseDTO for API response
    """
    return TaskResponseDTO(
        task_id=envelope.task_id,
        task_type=envelope.task_type,
        status="accepted",
        created_at=created_at or datetime.now(UTC),
    )


def result_to_dto(result: TaskResult) -> TaskResultDTO:
    """Map internal TaskResult to API response DTO.

    Args:
        result: TaskResult from internal processing

    Returns:
        TaskResultDTO for API response
    """
    return TaskResultDTO(
        task_id=result.task_id,
        status=result.status,
        outputs=result.outputs,
        error=result.error,
    )


def response_to_dict(response: TaskResponseDTO) -> dict[str, Any]:
    """Convert response DTO to dict for JSON serialization.

    Args:
        response: TaskResponseDTO

    Returns:
        Dictionary suitable for JSON response
    """
    return response.model_dump(mode="json")


def result_dto_to_dict(result_dto: TaskResultDTO) -> dict[str, Any]:
    """Convert result DTO to dict for JSON serialization.

    Args:
        result_dto: TaskResultDTO

    Returns:
        Dictionary suitable for JSON response
    """
    return result_dto.model_dump(mode="json", exclude_none=True)
