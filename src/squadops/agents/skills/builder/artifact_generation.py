"""Artifact Generation skill — produce runnable artifacts from plans.

Builder agent skill for generating source files, QA handoff documents,
and configuration from implementation plans.
Part of SIP-0071 Phase 3.
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


ARTIFACT_GENERATION_PROMPT = """Generate complete, runnable source files from the following plan:

{plan}

Requirements:
- Use tagged fenced code blocks: ```<language>:<filepath>
- Include all necessary files for a runnable package
- Use relative imports within the package
- Include a qa_handoff.md with sections: ## How to Run, ## How to Test, ## Expected Behavior
"""


class ArtifactGenerationSkill(Skill):
    """Skill for generating runnable artifacts from implementation plans.

    Inputs:
        plan: str - Implementation plan content
        strategy: str (optional) - Strategy analysis context
        build_profile: str (optional) - Build profile name

    Outputs:
        artifacts: str - Raw LLM response with fenced code blocks
        build_profile: str - Profile used for generation
    """

    @property
    def name(self) -> str:
        return "artifact_generation"

    @property
    def description(self) -> str:
        return "Generate runnable artifacts from implementation plans"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that a plan is provided."""
        errors = []
        if "plan" not in inputs:
            errors.append("'plan' is required")
        elif not isinstance(inputs["plan"], str):
            errors.append("'plan' must be a string")
        elif not inputs["plan"].strip():
            errors.append("'plan' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute artifact generation.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'plan'

        Returns:
            SkillResult with generated artifacts
        """
        start_time = time.perf_counter()

        plan = inputs["plan"]
        strategy = inputs.get("strategy", "")
        build_profile = inputs.get("build_profile", "python_cli_builder")

        prompt = ARTIFACT_GENERATION_PROMPT.format(plan=plan)
        if strategy:
            prompt += f"\n\nStrategy context:\n{strategy}"

        context.track_port_call("llm", "chat", purpose="artifact_generation")

        try:
            messages = [
                ChatMessage(
                    role="system",
                    content="You are a builder agent that produces complete, "
                    "runnable application packages from implementation plans. "
                    "Emit each file as a fenced code block: ```<lang>:<path>",
                ),
                ChatMessage(role="user", content=prompt),
            ]
            response = await context.llm.chat(messages)
            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "artifacts": response.content,
                "build_profile": build_profile,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs(
                    {"response_length": len(response.content)},
                ),
                port_calls=context.get_port_calls(),
                metadata={"build_profile": build_profile},
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
