"""Metrics Collection skill - collect and aggregate metrics.

Skill for the data role's metrics duties.
Part of SIP-0.8.8 Phase 4.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any

from squadops.agents.skills.base import ExecutionEvidence, Skill, SkillResult

if TYPE_CHECKING:
    from squadops.agents.skills.context import SkillContext


class MetricsCollectionSkill(Skill):
    """Skill for collecting and aggregating metrics.

    Inputs:
        metric_names: list[str] - Names of metrics to collect
        time_range: dict (optional) - Time range for collection
        aggregation: str (optional) - Aggregation method (sum/avg/count)

    Outputs:
        metrics: dict - Collected metrics
        timestamp: str - Collection timestamp
        aggregation_method: str - Method used
    """

    @property
    def name(self) -> str:
        return "metrics_collection"

    @property
    def description(self) -> str:
        return "Collect and aggregate metrics"

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("metrics",)

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        """Validate metrics collection inputs."""
        errors = []
        if "metric_names" not in inputs:
            errors.append("'metric_names' is required")
        elif not isinstance(inputs["metric_names"], list):
            errors.append("'metric_names' must be a list")
        elif not inputs["metric_names"]:
            errors.append("'metric_names' cannot be empty")
        return errors

    async def execute(
        self,
        context: SkillContext,
        inputs: dict[str, Any],
    ) -> SkillResult:
        """Execute metrics collection.

        Args:
            context: SkillContext providing port access
            inputs: Must contain 'metric_names'

        Returns:
            SkillResult with collected metrics
        """
        start_time = time.perf_counter()

        metric_names = inputs["metric_names"]
        time_range = inputs.get("time_range", {})
        aggregation = inputs.get("aggregation", "latest")

        # Track metrics port call
        context.track_port_call("metrics", "collect", count=len(metric_names))

        try:
            # Collect metrics
            # In a real implementation, this would query a metrics store
            # For now, return placeholder structure
            collected_metrics = {}
            for metric_name in metric_names:
                collected_metrics[metric_name] = {
                    "value": 0,
                    "unit": "count",
                    "labels": {},
                }

            duration_ms = (time.perf_counter() - start_time) * 1000

            from datetime import datetime, timezone

            outputs = {
                "metrics": collected_metrics,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "aggregation_method": aggregation,
                "metric_count": len(collected_metrics),
            }

            evidence = ExecutionEvidence.create(
                skill_name=self.name,
                duration_ms=duration_ms,
                inputs_hash=self._hash_inputs(inputs),
                outputs_hash=self._hash_inputs(
                    {"metric_count": outputs["metric_count"]}
                ),
                port_calls=context.get_port_calls(),
                metadata={"aggregation": aggregation},
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
