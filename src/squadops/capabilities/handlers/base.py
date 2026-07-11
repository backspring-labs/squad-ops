"""Base classes for capability handlers.

CapabilityHandler is the bridge between capability contracts
and execution. Handlers execute against ports to fulfill a
capability contract.

Part of SIP-0.8.8 Phase 5.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext
    from squadops.capabilities.models import CapabilityContract


@dataclass(frozen=True)
class HandlerEvidence:
    """Evidence of handler execution.

    Enables "No Silent Mocks" verification at the capability level.

    Attributes:
        handler_name: Name of the handler
        capability_id: ID of the capability contract fulfilled
        executed_at: When execution started
        duration_ms: Total execution duration
        inputs_hash: Hash of handler inputs
        outputs_hash: Hash of handler outputs
        metadata: Additional execution metadata
    """

    handler_name: str
    capability_id: str
    executed_at: datetime
    duration_ms: float
    inputs_hash: str = ""
    outputs_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        handler_name: str,
        capability_id: str,
        duration_ms: float,
        inputs_hash: str = "",
        outputs_hash: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> HandlerEvidence:
        """Factory method for creating evidence.

        Args:
            handler_name: Name of the handler
            capability_id: Capability ID being fulfilled
            duration_ms: Execution duration in milliseconds
            inputs_hash: Hash of inputs (for verification)
            outputs_hash: Hash of outputs (for verification)
            metadata: Additional metadata

        Returns:
            HandlerEvidence instance
        """
        return cls(
            handler_name=handler_name,
            capability_id=capability_id,
            executed_at=datetime.now(UTC),
            duration_ms=duration_ms,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class HandlerResult:
    """Result of handler execution.

    Contains outputs satisfying the capability contract
    and evidence of execution for verification.

    Attributes:
        success: Whether execution succeeded
        outputs: Output values per contract spec
        artifacts: Artifact paths produced
        _evidence: Execution evidence (required)
        error: Error message if failed
    """

    success: bool
    outputs: dict[str, Any]
    _evidence: HandlerEvidence
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def evidence(self) -> HandlerEvidence:
        """Get execution evidence (required, never None)."""
        return self._evidence


class CapabilityHandler(ABC):
    """Abstract base for capability handlers.

    Handlers execute against ports to fulfill capability contracts.
    Each handler:
    - Is associated with a specific capability contract
    - Produces outputs/artifacts per contract spec
    - Generates execution evidence for verification

    Subclasses must implement:
    - name: Handler identifier
    - capability_id: Matching contract ID
    - handle(): Execution logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name (for logging/identification)."""
        ...

    @property
    @abstractmethod
    def capability_id(self) -> str:
        """Capability ID this handler fulfills."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        return f"Handler for {self.capability_id}"

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract: CapabilityContract | None = None,
    ) -> list[str]:
        """Validate handler inputs against contract.

        Override to add custom validation beyond contract spec.

        Args:
            inputs: Input values to validate
            contract: Optional contract for spec-based validation

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if contract:
            # Validate required inputs per contract
            for input_spec in contract.inputs:
                if input_spec.required and input_spec.name not in inputs:
                    errors.append(f"'{input_spec.name}' is required")

        return errors

    @abstractmethod
    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Execute the handler to fulfill the capability.

        Args:
            context: ExecutionContext with port access
            inputs: Input values per contract spec

        Returns:
            HandlerResult with outputs and evidence
        """
        ...

    def _hash_dict(self, d: dict[str, Any]) -> str:
        """Create stable hash of a dictionary.

        Args:
            d: Dictionary to hash

        Returns:
            16-character hex hash
        """
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
