"""SquadOps API layer.

Provides API schemas (Pydantic DTOs) and mapping functions between
API boundary types and internal domain models.

Part of SIP-0.8.8.
"""
from squadops.api.schemas import (
    TaskRequestDTO,
    TaskResponseDTO,
    TaskResultDTO,
    TaskStatusDTO,
)
from squadops.api.mapping import (
    dto_to_envelope,
    envelope_to_response,
    result_to_dto,
)
from squadops.api.service import TaskService, AgentService

__all__ = [
    # DTOs
    "TaskRequestDTO",
    "TaskResponseDTO",
    "TaskResultDTO",
    "TaskStatusDTO",
    # Mapping functions
    "dto_to_envelope",
    "envelope_to_response",
    "result_to_dto",
    # Services (SIP-0.8.8)
    "TaskService",
    "AgentService",
]
