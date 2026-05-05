"""Data Analysis skill - analyze data and generate insights.

Skill for the data role's analytics duties.
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


class DataAnalysisSkill(Skill):
    """Skill for analyzing data and generating insights.

    Inputs:
        data: dict | list - Data to analyze
        analysis_type: str (optional) - Type of analysis
        questions: list[str] (optional) - Specific questions to answer

    Outputs:
        summary: str - Analysis summary
        insights: list[str] - Key insights
        statistics: dict - Computed statistics
        recommendations: list[str] - Recommendations based on analysis
    """

    @property
    def name(self) -> str:
        return "data_analysis"

    @property
    def description(self) -> str:
        return "Analyze data and generate insights"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate data analysis inputs."""
        errors = []
        if "data" not in inputs:
            errors.append("'data' is required")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute data analysis.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'data'

        Returns:
            SkillResult with analysis results
        """
        start_time = time.perf_counter()

        data = inputs["data"]
        analysis_type = inputs.get("analysis_type", "general")
        questions = inputs.get("questions", [])

        # Compute basic statistics
        statistics = self._compute_statistics(data)

        # Build analysis prompt
        prompt = f"""Analyze the following data:

Data: {json.dumps(data, default=str)[:2000]}

Analysis type: {analysis_type}

Computed statistics: {json.dumps(statistics)}

{"Questions to answer: " + json.dumps(questions) if questions else ""}

Provide:
1. Summary of the data
2. Key insights (3-5 points)
3. Recommendations

Respond in JSON format with keys: summary, insights, recommendations
"""

        # Track LLM call
        context.track_port_call("llm", "chat", purpose="data_analysis")

        try:
            # Query LLM for insights
            messages = [
                ChatMessage(
                    role="system",
                    content="You are a data analyst. Provide clear, actionable insights.",
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
                    "summary": response.content[:500],
                    "insights": [],
                    "recommendations": [],
                }

            outputs = {
                "summary": analysis.get("summary", ""),
                "insights": analysis.get("insights", []),
                "statistics": statistics,
                "recommendations": analysis.get("recommendations", []),
                "raw_response": response.content,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs({"data_size": len(str(data))}),
                outputs_hash=self._hash_inputs(
                    {"insights_count": len(outputs["insights"])}
                ),
                port_calls=context.get_port_calls(),
                metadata={"analysis_type": analysis_type},
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

    def _compute_statistics(self, data: Any) -> dict[str, Any]:
        """Compute basic statistics from data.

        Args:
            data: Data to analyze

        Returns:
            Dictionary of computed statistics
        """
        stats: dict[str, Any] = {}

        if isinstance(data, list):
            stats["count"] = len(data)
            stats["type"] = "list"

            # If list of numbers
            numeric = [x for x in data if isinstance(x, (int, float))]
            if numeric:
                stats["numeric_count"] = len(numeric)
                stats["sum"] = sum(numeric)
                stats["mean"] = sum(numeric) / len(numeric)
                stats["min"] = min(numeric)
                stats["max"] = max(numeric)

        elif isinstance(data, dict):
            stats["key_count"] = len(data)
            stats["type"] = "dict"
            stats["keys"] = list(data.keys())[:10]  # First 10 keys

        else:
            stats["type"] = type(data).__name__

        return stats

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
