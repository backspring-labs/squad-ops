"""Development capability handler.

Orchestrates development-related skills (code generation, file operations)
to fulfill development capability contracts.

Part of SIP-0.8.8 Phase 5.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.base import (
    CapabilityHandler,
    HandlerEvidence,
    HandlerResult,
)

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext


class CodeGenerationHandler(CapabilityHandler):
    """Handler for code generation capability.

    Orchestrates code_generation skill to produce code
    from requirements, optionally writing to files.
    """

    @property
    def name(self) -> str:
        return "code_generation_handler"

    @property
    def capability_id(self) -> str:
        return "development.code_generation"

    @property
    def description(self) -> str:
        return "Generate code from requirements"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("code_generation", "file_write")

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "requirements" not in inputs:
            errors.append("'requirements' is required")
        elif not isinstance(inputs["requirements"], str):
            errors.append("'requirements' must be a string")
        elif not inputs["requirements"].strip():
            errors.append("'requirements' cannot be empty")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Generate code using code_generation skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'requirements', optionally 'output_path', 'language'

        Returns:
            HandlerResult with generated code and optional file path
        """
        start_time = time.perf_counter()
        artifacts: dict[str, str] = {}

        try:
            # Generate code
            skill_inputs = {
                "requirements": inputs["requirements"],
            }
            if "language" in inputs:
                skill_inputs["language"] = inputs["language"]

            result = await context.execute_skill("code_generation", skill_inputs)

            if not result.success:
                duration_ms = (time.perf_counter() - start_time) * 1000
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=duration_ms,
                    skill_executions=context.get_skill_executions(),
                    inputs_hash=self._hash_dict(inputs),
                    outputs_hash=self._hash_dict({"error": result.error}),
                    metadata={"error": True},
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=evidence,
                    error=result.error,
                )

            code = result.outputs.get("code", "")
            language = result.outputs.get("language", "python")

            # Optionally write to file
            if "output_path" in inputs and inputs["output_path"]:
                write_result = await context.execute_skill(
                    "file_write",
                    {
                        "path": inputs["output_path"],
                        "content": code,
                    },
                )
                if write_result.success:
                    artifacts["code_file"] = inputs["output_path"]

            duration_ms = (time.perf_counter() - start_time) * 1000

            outputs = {
                "code": code,
                "language": language,
                "written_to_file": "output_path" in inputs,
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"language": language, "code_len": len(code)}),
            )

            return HandlerResult(
                success=True,
                outputs=outputs,
                artifacts=artifacts,
                _evidence=evidence,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"error": str(e)}),
                metadata={"error": True},
            )
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=str(e),
            )


class CodeAnalysisHandler(CapabilityHandler):
    """Handler for code analysis capability.

    Orchestrates file_read and llm_query skills to analyze code.
    """

    @property
    def name(self) -> str:
        return "code_analysis_handler"

    @property
    def capability_id(self) -> str:
        return "development.code_analysis"

    @property
    def description(self) -> str:
        return "Analyze code for quality, patterns, and issues"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("file_read", "llm_query")

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "file_path" not in inputs and "code" not in inputs:
            errors.append("Either 'file_path' or 'code' is required")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Analyze code using file_read and llm_query skills.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'file_path' or 'code'

        Returns:
            HandlerResult with analysis outputs
        """
        start_time = time.perf_counter()

        try:
            # Get code content
            if "code" in inputs:
                code = inputs["code"]
            else:
                read_result = await context.execute_skill(
                    "file_read",
                    {"path": inputs["file_path"]},
                )
                if not read_result.success:
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    evidence = HandlerEvidence.create(
                        handler_name=self.name,
                        capability_id=self.capability_id,
                        duration_ms=duration_ms,
                        skill_executions=context.get_skill_executions(),
                        inputs_hash=self._hash_dict(inputs),
                        outputs_hash=self._hash_dict({"error": read_result.error}),
                        metadata={"error": True},
                    )
                    return HandlerResult(
                        success=False,
                        outputs={},
                        _evidence=evidence,
                        error=f"Failed to read file: {read_result.error}",
                    )
                code = read_result.outputs.get("content", "")

            # Analyze with LLM
            analysis_prompt = f"""Analyze the following code and provide:
1. A brief summary of what the code does
2. Code quality assessment (good/moderate/poor)
3. Any potential issues or improvements
4. Key patterns used

Code:
```
{code}
```

Respond with a structured analysis."""

            llm_result = await context.execute_skill(
                "llm_query",
                {"prompt": analysis_prompt},
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            if not llm_result.success:
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=duration_ms,
                    skill_executions=context.get_skill_executions(),
                    inputs_hash=self._hash_dict(inputs),
                    outputs_hash=self._hash_dict({"error": llm_result.error}),
                    metadata={"error": True},
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=evidence,
                    error=f"Analysis failed: {llm_result.error}",
                )

            outputs = {
                "analysis": llm_result.outputs.get("response", ""),
                "code_length": len(code),
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict({"code_length": len(code)}),
                outputs_hash=self._hash_dict({"analysis_length": len(outputs["analysis"])}),
            )

            return HandlerResult(
                success=True,
                outputs=outputs,
                _evidence=evidence,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"error": str(e)}),
                metadata={"error": True},
            )
            return HandlerResult(
                success=False,
                outputs={},
                _evidence=evidence,
                error=str(e),
            )
