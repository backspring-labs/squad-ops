"""
Lineage Generator - Generates and propagates ACI lineage identifiers.

Ensures all lineage fields are always present (never silently omitted).
Generates placeholders when tracing is not enabled.

Part of SIP-0.8.8 migration from _v0_legacy/agents/utils/lineage_generator.py
"""

import logging

logger = logging.getLogger(__name__)


class LineageGenerator:
    """
    Generates and propagates ACI lineage identifiers.

    All lineage fields must be present in every TaskEnvelope. This class
    ensures missing fields are generated with deterministic, reproducible values.
    """

    @staticmethod
    def generate_correlation_id(cycle_id: str) -> str:
        """
        Generate correlation_id from cycle_id (cycle-scoped, stable within cycle).

        Format: corr-{cycle_id}
        Note: Leave room for future project-wide correlation without changing envelope.
        """
        return f"corr-{cycle_id}"

    @staticmethod
    def generate_causation_id(
        parent_task_id: str | None = None, parent_event_id: str | None = None
    ) -> str:
        """
        Generate causation_id from parent event/task/message.

        Prefers parent_task_id if available, otherwise uses parent_event_id.
        If neither provided, generates a root causation identifier.
        """
        if parent_task_id:
            return f"cause-task-{parent_task_id}"
        elif parent_event_id:
            return f"cause-event-{parent_event_id}"
        else:
            # Root event - no parent
            return "cause-root"

    @staticmethod
    def generate_trace_id(task_id: str, use_placeholder: bool = True) -> str:
        """
        Generate trace_id. Returns placeholder if tracing not enabled.

        Format when placeholder: trace-placeholder-{task_id}
        When tracing enabled, this would be replaced with actual trace ID.
        """
        if use_placeholder:
            return f"trace-placeholder-{task_id}"
        # Future: integrate with actual tracing system
        return f"trace-{task_id}"

    @staticmethod
    def generate_span_id(task_id: str, use_placeholder: bool = True) -> str:
        """
        Generate span_id. Returns placeholder if tracing not enabled.

        Format when placeholder: span-placeholder-{task_id}
        When tracing enabled, this would be replaced with actual span ID.
        """
        if use_placeholder:
            return f"span-placeholder-{task_id}"
        # Future: integrate with actual tracing system
        return f"span-{task_id}"

    @classmethod
    def ensure_lineage_fields(
        cls,
        cycle_id: str,
        task_id: str,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_task_id: str | None = None,
        parent_event_id: str | None = None,
        tracing_enabled: bool = False,
    ) -> dict[str, str]:
        """
        Ensure all lineage fields are present. Generate missing fields.

        Args:
            cycle_id: Execution cycle identifier (required)
            task_id: Task identifier (required)
            correlation_id: Existing correlation_id (optional, will be generated if None)
            causation_id: Existing causation_id (optional, will be generated if None)
            trace_id: Existing trace_id (optional, will be generated if None)
            span_id: Existing span_id (optional, will be generated if None)
            parent_task_id: Parent task ID for causation (optional)
            parent_event_id: Parent event ID for causation (optional)
            tracing_enabled: Whether distributed tracing is enabled (default: False)

        Returns:
            Dictionary with all lineage fields guaranteed to be present:
            - correlation_id
            - causation_id
            - trace_id
            - span_id
        """
        # Generate correlation_id if not provided
        if not correlation_id:
            correlation_id = cls.generate_correlation_id(cycle_id)

        # Generate causation_id if not provided
        if not causation_id:
            causation_id = cls.generate_causation_id(parent_task_id, parent_event_id)

        # Generate trace_id if not provided
        if not trace_id:
            trace_id = cls.generate_trace_id(task_id, use_placeholder=not tracing_enabled)

        # Generate span_id if not provided
        if not span_id:
            span_id = cls.generate_span_id(task_id, use_placeholder=not tracing_enabled)

        return {
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "trace_id": trace_id,
            "span_id": span_id,
        }
