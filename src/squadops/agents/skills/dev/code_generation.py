"""Code Generation skill - generate code from requirements.

Developer agent skill for code creation.
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


CODE_GENERATION_PROMPT = """Generate code based on the following requirements:

Requirements: {requirements}

Language: {language}

Please provide:
1. The complete implementation
2. Brief explanation of the approach
3. Any dependencies needed

Respond with the code first, then the explanation.
"""


class CodeGenerationSkill(Skill):
    """Skill for generating code from requirements.

    Inputs:
        requirements: str - Code requirements/specification
        language: str (optional) - Target language (default: python)
        context_code: str (optional) - Existing code context

    Outputs:
        code: str - Generated code
        explanation: str - Brief explanation
        language: str - Language used
    """

    @property
    def name(self) -> str:
        return "code_generation"

    @property
    def description(self) -> str:
        return "Generate code from requirements specification"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("llm",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate that requirements are provided."""
        errors = []
        if "requirements" not in inputs:
            errors.append("'requirements' is required")
        elif not isinstance(inputs["requirements"], str):
            errors.append("'requirements' must be a string")
        elif not inputs["requirements"].strip():
            errors.append("'requirements' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute code generation.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'requirements'

        Returns:
            SkillResult with generated code
        """
        start_time = time.perf_counter()

        requirements = inputs["requirements"]
        language = inputs.get("language", "python")
        context_code = inputs.get("context_code", "")

        # Build prompt
        prompt = CODE_GENERATION_PROMPT.format(
            requirements=requirements,
            language=language,
        )
        if context_code:
            prompt += f"\n\nExisting code context:\n```\n{context_code}\n```"

        # Track LLM call
        context.track_port_call("llm", "chat", purpose="code_generation")

        try:
            # Query LLM
            messages = [
                ChatMessage(
                    role="system",
                    content=f"You are an expert {language} developer. "
                    "Generate clean, well-documented code.",
                ),
                ChatMessage(role="user", content=prompt),
            ]
            response = await context.llm.chat(messages)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Parse response - extract code and explanation
            code, explanation = self._parse_response(response.content)

            outputs = {
                "code": code,
                "explanation": explanation,
                "language": language,
                "raw_response": response.content,
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs({"code_length": len(code)}),
                port_calls=context.get_port_calls(),
                metadata={"language": language},
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

    def _parse_response(self, response: str) -> tuple[str, str]:
        """Parse LLM response into code and explanation.

        Args:
            response: Raw LLM response

        Returns:
            Tuple of (code, explanation)
        """
        # Look for code blocks
        code = ""
        explanation = ""

        if "```" in response:
            # Extract code from markdown code blocks
            parts = response.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Odd indices are code blocks
                    # Remove language identifier from first line if present
                    lines = part.split("\n")
                    if lines[0].strip() in ["python", "py", "javascript", "js", ""]:
                        code += "\n".join(lines[1:])
                    else:
                        code += part
                elif i > 0:  # After first code block
                    explanation += part.strip()
        else:
            # No code blocks, treat entire response as code
            code = response
            explanation = "Code generated from requirements"

        return code.strip(), explanation.strip()

    def _hash_inputs(self, d: dict[str, Any]) -> str:
        """Create stable hash of inputs."""
        serialized = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
