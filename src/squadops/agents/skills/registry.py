"""SkillRegistry for skill discovery and execution.

Provides a central registry for skills with:
- Registration and discovery
- Capability validation
- Execution with evidence collection

Part of SIP-0.8.8 Agent Foundation.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from squadops.agents.exceptions import SkillContractViolation, SkillNotFoundError
from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Registry for skill discovery and execution.

    Manages skill registration and provides execution with:
    - Capability validation
    - Input validation
    - Execution evidence collection
    - Contract enforcement (no silent mocks)
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill.

        Args:
            skill: Skill instance to register

        Raises:
            ValueError: If skill with same name already registered
        """
        if skill.name in self._skills:
            raise ValueError(f"Skill '{skill.name}' already registered")
        self._skills[skill.name] = skill
        logger.info("skill_registered", extra={"skill_name": skill.name})

    def unregister(self, skill_name: str) -> bool:
        """Unregister a skill.

        Args:
            skill_name: Name of skill to remove

        Returns:
            True if removed, False if not found
        """
        if skill_name in self._skills:
            del self._skills[skill_name]
            logger.info("skill_unregistered", extra={"skill_name": skill_name})
            return True
        return False

    def get(self, skill_name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill if found, None otherwise
        """
        return self._skills.get(skill_name)

    def list_skills(self) -> list[str]:
        """List all registered skill names.

        Returns:
            List of skill names
        """
        return list(self._skills.keys())

    def get_skills_by_capability(self, capability: str) -> list[Skill]:
        """Get all skills that require a specific capability.

        Args:
            capability: Capability name (e.g., "llm", "filesystem")

        Returns:
            List of skills requiring that capability
        """
        return [
            skill
            for skill in self._skills.values()
            if capability in skill.required_capabilities
        ]

    async def execute(
        self,
        skill_name: str,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute a skill with full evidence collection.

        Args:
            skill_name: Name of the skill to execute
            context: SkillContext for port access
            inputs: Input parameters for the skill

        Returns:
            SkillResult with outputs and execution evidence

        Raises:
            SkillNotFoundError: If skill not registered
            SkillContractViolation: If skill fails to produce evidence
        """
        skill = self._skills.get(skill_name)
        if skill is None:
            raise SkillNotFoundError(f"Skill '{skill_name}' not found in registry")

        # Validate inputs
        validation_errors = skill.validate_inputs(inputs)
        if validation_errors:
            return self._create_error_result(
                skill_name,
                f"Input validation failed: {'; '.join(validation_errors)}",
                inputs,
            )

        # Clear port calls for tracking
        context.clear_port_calls()

        # Execute with timing
        start_time = time.perf_counter()
        try:
            result = await skill.execute(context, inputs)
        except Exception as e:
            logger.exception(
                "skill_execution_error",
                extra={"skill_name": skill_name, "error": str(e)},
            )
            return self._create_error_result(skill_name, str(e), inputs)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Validate evidence was produced
        if not hasattr(result, "_evidence") or result._evidence is None:
            raise SkillContractViolation(
                f"Skill '{skill_name}' failed to produce execution evidence. "
                "All skills must return SkillResult with _evidence field."
            )

        # Validate evidence fields
        evidence = result._evidence
        if evidence.skill_name != skill_name:
            raise SkillContractViolation(
                f"Evidence skill_name mismatch: expected '{skill_name}', "
                f"got '{evidence.skill_name}'"
            )

        logger.info(
            "skill_executed",
            extra={
                "skill_name": skill_name,
                "success": result.success,
                "duration_ms": duration_ms,
                "port_calls": len(context.get_port_calls()),
            },
        )

        return result

    def _create_error_result(
        self,
        skill_name: str,
        error: str,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Create error result with evidence.

        Args:
            skill_name: Name of the skill
            error: Error message
            inputs: Original inputs

        Returns:
            SkillResult indicating failure
        """
        evidence = ExecutionEvidence.create(
            skill_name=skill_name,
            duration_ms=0.0,
            inputs_hash=self._hash_dict(inputs),
            outputs_hash=self._hash_dict({"error": error}),
            port_calls=[],
            metadata={"error": True},
        )
        return SkillResult(
            success=False,
            outputs={},
            _evidence=evidence,
            error=error,
        )

    @staticmethod
    def _hash_dict(d: dict[str, Any]) -> str:
        """Create stable hash of a dictionary.

        Args:
            d: Dictionary to hash

        Returns:
            SHA-256 hash string (first 16 chars)
        """
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
