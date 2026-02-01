"""Task Analysis skill - analyze and break down tasks.

Lead agent skill for task understanding.
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


TASK_ANALYSIS_PROMPT = """Analyze the following task and provide a structured breakdown:

Task: {description}

Please provide:
1. A summary of what needs to be done
2. Key requirements identified
3. Suggested approach
4. Estimated complexity (low/medium/high)
5. Potential risks or blockers

Respond in JSON format with keys: summary, requirements, approach, complexity, risks
"""


class TaskAnalysisSkill(Skill):
    """Skill for analyzing and breaking down tasks.

    Inputs:
        description: str - Task description to analyze
        context_info: dict (optional) - Additional context

    Outputs:
        summary: str - Task summary
        requirements: list[str] - Identified requirements
        approach: str - Suggested approach
        complexity: str - Estimated complexity
        risks: list[str] - Potential risks
    """

    @property
    def name(self) -> str:
        return "task_analysis"

    @property
    def description(self) -> str:
        return "Analyze and break down a task into components"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that description is provided."""
        errors = []
        if "description" not in inputs:
            errors.append("'description' is required")
        elif not isinstance(inputs["description"], str):
            errors.append("'description' must be a string")
        elif not inputs["description"].strip():
            errors.append("'description' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute task analysis.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'description'

        Returns:
            SkillResult with analysis breakdown
        """
        start_time = time.perf_counter()

        description = inputs["description"]
        context_info = inputs.get("context_info", {})

        # Build prompt
        prompt = TASK_ANALYSIS_PROMPT.format(description=description)
        if context_info:
            prompt += f"\n\nAdditional context: {json.dumps(context_info)}"

        # Track LLM call
        context.track_port_call("llm", "chat", purpose="task_analysis")

        try:
            # Query LLM
            messages = [ChatMessage(role="user", content=prompt)]
            response = await context.llm.chat(messages)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Parse response (attempt JSON, fallback to structured)
            try:
                analysis = json.loads(response.content)
            except json.JSONDecodeError:
                # Fallback to basic structure
                analysis = {
                    "summary": response.content[:500],
                    "requirements": [],
                    "approach": "See summary",
                    "complexity": "medium",
                    "risks": [],
                }

            outputs = {
                "summary": analysis.get("summary", ""),
                "requirements": analysis.get("requirements", []),
                "approach": analysis.get("approach", ""),
                "complexity": analysis.get("complexity", "medium"),
                "risks": analysis.get("risks", []),
                "raw_response": response.content,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs(
                    {"complexity": outputs["complexity"]}
                ),
                port_calls=context.get_port_calls(),
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
