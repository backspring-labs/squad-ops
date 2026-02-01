"""API Schemas (Pydantic DTOs).

Pydantic models for API boundary validation.
These are separate from internal frozen dataclasses to allow
validation and serialization at the API layer.

Part of SIP-0.8.8.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskRequestDTO(BaseModel):
    """Pydantic DTO for task submission requests.

    Used at API ingress for validation before mapping to internal TaskEnvelope.
    """

    task_type: str = Field(..., description="Task type/behavior category")
    source_agent: str = Field(..., description="Source agent ID")
    target_agent: str | None = Field(None, description="Target agent ID")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Task inputs")
    priority: int = Field(5, ge=1, le=10, description="Priority (1-10, 5=default)")
    timeout: float | None = Field(None, ge=0, description="Timeout in seconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")
    task_name: str | None = Field(None, description="Human-readable task name")

    model_config = {"extra": "forbid"}


class TaskResponseDTO(BaseModel):
    """Pydantic DTO for task submission response.

    Returned at API egress after task creation.
    """

    task_id: str = Field(..., description="Assigned task ID")
    task_type: str = Field(..., description="Task type")
    status: str = Field("accepted", description="Initial task status")
    created_at: datetime | None = Field(None, description="Creation timestamp")

    model_config = {"from_attributes": True}


class TaskResultDTO(BaseModel):
    """Pydantic DTO for task result response.

    Used to serialize TaskResult for API responses.
    """

    task_id: str = Field(..., description="Task ID")
    status: str = Field(..., description="Final status (SUCCEEDED, FAILED, CANCELED)")
    outputs: dict[str, Any] | None = Field(None, description="Task outputs (if succeeded)")
    error: str | None = Field(None, description="Error message (if failed/canceled)")

    model_config = {"from_attributes": True}


class TaskStatusDTO(BaseModel):
    """Pydantic DTO for task status response.

    Used to return task status with execution evidence.
    """

    task_id: str
    status: str
    task_type: str | None = None
    source_agent: str | None = None
    target_agent: str | None = None
    execution_mode: str | None = None
    execution_evidence: dict[str, Any] | None = None
    mock_components: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error: str | None = None

    model_config = {"from_attributes": True}
