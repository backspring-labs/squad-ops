"""Skill base class for atomic operations.

Skills are the fundamental units of agent work. Each skill:
- Performs a single, atomic operation
- Must return ExecutionEvidence (no silent mocks)
- Has access to ports via SkillContext

Part of SIP-0.8.8 Agent Foundation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


@dataclass(frozen=True)
class ExecutionEvidence:
    """Evidence that a skill was executed (not mocked).

    Every skill execution must produce evidence that proves real work was done.
    This is the "No Silent Mocks" guard from SIP-0.8.8.
    """

    skill_name: str
    executed_at: datetime
    duration_ms: float
    inputs_hash: str
    outputs_hash: str
    port_calls: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        skill_name: str,
        duration_ms: float,
        inputs_hash: str,
        outputs_hash: str,
        port_calls: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionEvidence:
        """Create evidence with current timestamp.

        Args:
            skill_name: Name of the skill that executed
            duration_ms: Execution duration in milliseconds
            inputs_hash: Hash of skill inputs
            outputs_hash: Hash of skill outputs
            port_calls: List of port method calls made
            metadata: Additional metadata

        Returns:
            ExecutionEvidence instance
        """
        return cls(
            skill_name=skill_name,
            executed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            inputs_hash=inputs_hash,
            outputs_hash=outputs_hash,
            port_calls=tuple(port_calls or []),
            metadata=metadata or {},
        )


@dataclass(frozen=True)
class SkillResult:
    """Result of skill execution.

    Contains both the output data and execution evidence.
    """

    success: bool
    outputs: dict[str, Any]
    _evidence: ExecutionEvidence
    error: str | None = None

    @property
    def evidence(self) -> ExecutionEvidence:
        """Get execution evidence (required for all results)."""
        return self._evidence


class Skill(ABC):
    """Base class for atomic skill operations.

    Skills are the building blocks of agent capabilities. Each skill:
    - Has a unique name for registry lookup
    - Declares required capabilities (which ports it needs)
    - Executes a single atomic operation
    - Must return SkillResult with ExecutionEvidence

    Subclasses must implement:
    - name property: Unique skill identifier
    - required_capabilities property: List of required port capabilities
    - execute method: The actual skill logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier.

        Returns:
            Skill name (e.g., "code_generation", "test_execution")
        """
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what this skill does.

        Returns:
            Description string (defaults to empty)
        """
        return ""

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        """Capabilities (ports) this skill requires.

        Returns:
            Tuple of capability names (e.g., ("llm", "filesystem"))
        """
        return ()

    @abstractmethod
    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute the skill.

        Args:
            context: SkillContext providing port access
            inputs: Input parameters for the skill

        Returns:
            SkillResult with outputs and execution evidence
        """
        ...

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate skill inputs.

        Override to add input validation. Default accepts all inputs.

        Args:
            inputs: Input parameters to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return []
