"""LLM Query skill - query LLM with prompt.

Atomic skill for LLM interactions.
Part of SIP-0.8.8 Phase 4.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


class LLMQuerySkill(Skill):
    """Atomic skill: query LLM with prompt.

    Inputs:
        prompt: str - The prompt to send to the LLM
        system_prompt: str (optional) - System prompt for context
        model: str (optional) - Model override

    Outputs:
        response: str - The LLM response content
        model: str - Model used for generation
    """

    @property
    def name(self) -> str:
        return "llm_query"

    @property
    def description(self) -> str:
        return "Query LLM with a prompt and return the response"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that prompt is provided."""
        errors = []
        if "prompt" not in inputs:
            errors.append("'prompt' is required")
        elif not isinstance(inputs["prompt"], str):
            errors.append("'prompt' must be a string")
        elif not inputs["prompt"].strip():
            errors.append("'prompt' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute LLM query.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'prompt', optionally 'system_prompt' and 'model'

        Returns:
            SkillResult with LLM response
        """
        start_time = time.perf_counter()

        prompt = inputs["prompt"]
        system_prompt = inputs.get("system_prompt")
        model = inputs.get("model")

        # Build messages
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt))

        # Track LLM call
        context.track_port_call("llm", "chat", model=model or "default")

        try:
            # Call LLM
            response = await context.llm.chat(messages, model=model)
            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "response": response.content,
                "model": model or "default",
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs(outputs),
                port_calls=context.get_port_calls(),
                metadata={"model": model or "default"},
            )

            return SkillResult(
                success=True,
                outputs=outputs,
                _evidence=evidence,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs({"error": str(e)}),
                port_calls=context.get_port_calls(),
                metadata={"error": True},
            )
            return SkillResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=str(e),
            )

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
