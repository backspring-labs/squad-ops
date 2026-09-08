"""
Lineage Generator - Generates and propagates ACI lineage identifiers.

Ensures all lineage fields are always present (never silently omitted). Ids carry their
full entropy and a trace id is inherited from the parent, never derived from a task id
(#575 — the placeholders and the truncated uuid4 ids this module and its callers used
to synthesize).

Part of SIP-0.8.8 migration from _v0_legacy/agents/utils/lineage_generator.py
"""

import logging
import secrets
import uuid

logger = logging.getLogger(__name__)


def new_trace_id() -> str:
    """A fresh trace id: 32 hex characters (16 random bytes, the W3C trace-context width)."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """A fresh span id: 16 hex characters (8 random bytes)."""
    return secrets.token_hex(8)


def new_id(prefix: str) -> str:
    """A fresh prefixed identifier carrying a whole uuid4 — ``task-<32 hex>``.

    #575: ``uuid4().hex[:8]`` / ``[:12]`` discarded 80–96 of the 122 random bits and let
    collision odds grow with volume for nothing; the event bus already keeps whole ids.
    """
    return f"{prefix}-{uuid.uuid4().hex}"


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
    def generate_trace_id(parent_trace_id: str | None = None) -> str:
        """The trace this envelope belongs to: the parent's when there is one, else new.

        #575: the former ``trace-placeholder-{task_id}`` satisfied the always-present
        contract and defeated the one thing a trace id is for — two envelopes in one
        causal chain carried two different, meaningless ids, so nothing downstream could
        join them. A trace id is 32 hex characters (16 random bytes, the W3C trace-context
        width) and is inherited, never derived from a task id.
        """
        return parent_trace_id or new_trace_id()

    @staticmethod
    def generate_span_id() -> str:
        """A fresh span for this envelope — 16 hex characters (8 random bytes), never
        derived from the task id (#575)."""
        return new_span_id()

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
        parent_trace_id: str | None = None,
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
            parent_trace_id: The parent's trace id — a child envelope joins its parent's
                trace and takes a fresh span (#575)

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

        # The trace is inherited, the span is always this envelope's own (#575)
        if not trace_id:
            trace_id = cls.generate_trace_id(parent_trace_id)

        if not span_id:
            span_id = cls.generate_span_id()

        return {
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "trace_id": trace_id,
            "span_id": span_id,
        }
