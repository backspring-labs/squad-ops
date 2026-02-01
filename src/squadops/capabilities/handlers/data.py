"""Data capability handler.

Orchestrates data-related skills (data analysis, metrics collection)
to fulfill data capability contracts.

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


class DataAnalysisHandler(CapabilityHandler):
    """Handler for data analysis capability.

    Orchestrates data_analysis skill to analyze data
    and produce insights.
    """

    @property
    def name(self) -> str:
        return "data_analysis_handler"

    @property
    def capability_id(self) -> str:
        return "data.analysis"

    @property
    def description(self) -> str:
        return "Analyze data and produce insights"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("data_analysis",)

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "data" not in inputs:
            errors.append("'data' is required")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Analyze data using data_analysis skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'data', optionally 'analysis_type'

        Returns:
            HandlerResult with analysis results
        """
        start_time = time.perf_counter()

        try:
            skill_inputs = {"data": inputs["data"]}
            if "analysis_type" in inputs:
                skill_inputs["analysis_type"] = inputs["analysis_type"]

            result = await context.execute_skill("data_analysis", skill_inputs)

            duration_ms = (time.perf_counter() - start_time) * 1000

            if not result.success:
                evidence = HandlerEvidence.create(
                    handler_name=self.name,
                    capability_id=self.capability_id,
                    duration_ms=duration_ms,
                    skill_executions=context.get_skill_executions(),
                    inputs_hash=self._hash_dict({"data_type": type(inputs["data"]).__name__}),
                    outputs_hash=self._hash_dict({"error": result.error}),
                    metadata={"error": True},
                )
                return HandlerResult(
                    success=False,
                    outputs={},
                    _evidence=evidence,
                    error=result.error,
                )

            outputs = {
                "statistics": result.outputs.get("statistics", {}),
                "summary": result.outputs.get("summary", ""),
                "insights": result.outputs.get("insights", []),
                "recommendations": result.outputs.get("recommendations", []),
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict({"data_type": type(inputs["data"]).__name__}),
                outputs_hash=self._hash_dict({"has_statistics": bool(outputs["statistics"])}),
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


class MetricsCollectionHandler(CapabilityHandler):
    """Handler for metrics collection capability.

    Orchestrates metrics_collection skill to gather
    and aggregate metrics.
    """

    @property
    def name(self) -> str:
        return "metrics_collection_handler"

    @property
    def capability_id(self) -> str:
        return "data.metrics_collection"

    @property
    def description(self) -> str:
        return "Collect and aggregate metrics"

    @property
    def required_skills(self) -> tuple[str, ...]:
        return ("metrics_collection",)

    def validate_inputs(
        self,
        inputs: dict[str, Any],
        contract=None,
    ) -> list[str]:
        errors = super().validate_inputs(inputs, contract)

        if "metric_names" not in inputs:
            errors.append("'metric_names' is required")
        elif not isinstance(inputs.get("metric_names"), list):
            errors.append("'metric_names' must be a list")
        elif not inputs["metric_names"]:
            errors.append("'metric_names' cannot be empty")

        return errors

    async def handle(
        self,
        context: ExecutionContext,
        inputs: dict[str, Any],
    ) -> HandlerResult:
        """Collect metrics using metrics_collection skill.

        Args:
            context: ExecutionContext with skill access
            inputs: Must contain 'metric_names'

        Returns:
            HandlerResult with collected metrics
        """
        start_time = time.perf_counter()

        try:
            skill_inputs = {"metric_names": inputs["metric_names"]}
            if "aggregation" in inputs:
                skill_inputs["aggregation"] = inputs["aggregation"]

            result = await context.execute_skill("metrics_collection", skill_inputs)

            duration_ms = (time.perf_counter() - start_time) * 1000

            if not result.success:
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

            outputs = {
                "metrics": result.outputs.get("metrics", {}),
                "metric_count": result.outputs.get("metric_count", 0),
                "timestamp": result.outputs.get("timestamp", ""),
                "aggregation_method": result.outputs.get("aggregation_method", "latest"),
            }

            evidence = HandlerEvidence.create(
                handler_name=self.name,
                capability_id=self.capability_id,
                duration_ms=duration_ms,
                skill_executions=context.get_skill_executions(),
                inputs_hash=self._hash_dict(inputs),
                outputs_hash=self._hash_dict({"metric_count": outputs["metric_count"]}),
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
