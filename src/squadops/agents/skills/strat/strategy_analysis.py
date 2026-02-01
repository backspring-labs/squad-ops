"""Strategy Analysis skill - analyze strategic options.

Strategy agent skill for strategic planning.
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


STRATEGY_ANALYSIS_PROMPT = """Analyze the following strategic situation:

Context: {context}
Goals: {goals}

Please provide:
1. Current state assessment
2. Strategic options (at least 3)
3. Recommended approach
4. Key risks and mitigations
5. Success metrics

Respond in JSON format with keys: assessment, options, recommendation, risks, metrics
"""


class StrategyAnalysisSkill(Skill):
    """Skill for analyzing strategic situations and options.

    Inputs:
        context: str - Situational context
        goals: list[str] - Strategic goals
        constraints: dict (optional) - Constraints to consider

    Outputs:
        assessment: str - Current state assessment
        options: list[dict] - Strategic options
        recommendation: str - Recommended approach
        risks: list[dict] - Risks and mitigations
        metrics: list[str] - Success metrics
    """

    @property
    def name(self) -> str:
        return "strategy_analysis"

    @property
    def description(self) -> str:
        return "Analyze strategic situations and recommend approaches"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate strategy analysis inputs."""
        errors = []
        if "context" not in inputs:
            errors.append("'context' is required")
        if "goals" not in inputs:
            errors.append("'goals' is required")
        elif not isinstance(inputs["goals"], list):
            errors.append("'goals' must be a list")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute strategy analysis.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'context' and 'goals'

        Returns:
            SkillResult with strategic analysis
        """
        start_time = time.perf_counter()

        situation_context = inputs["context"]
        goals = inputs["goals"]
        constraints = inputs.get("constraints", {})

        # Build prompt
        prompt = STRATEGY_ANALYSIS_PROMPT.format(
            context=situation_context,
            goals=json.dumps(goals),
        )
        if constraints:
            prompt += f"\n\nConstraints: {json.dumps(constraints)}"

        # Track LLM call
        context.track_port_call("llm", "chat", purpose="strategy_analysis")

        try:
            # Query LLM
            messages = [
                ChatMessage(
                    role="system",
                    content="You are a strategic planning expert. "
                    "Provide clear, actionable strategic analysis.",
                ),
                ChatMessage(role="user", content=prompt),
            ]
            response = await context.llm.chat(messages)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Parse response
            try:
                analysis = json.loads(response.content)
            except json.JSONDecodeError:
                analysis = {
                    "assessment": response.content[:500],
                    "options": [],
                    "recommendation": "See assessment",
                    "risks": [],
                    "metrics": [],
                }

            outputs = {
                "assessment": analysis.get("assessment", ""),
                "options": analysis.get("options", []),
                "recommendation": analysis.get("recommendation", ""),
                "risks": analysis.get("risks", []),
                "metrics": analysis.get("metrics", []),
                "raw_response": response.content,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs(
                    {"options_count": len(outputs["options"])}
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
