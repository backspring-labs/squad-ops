"""Factory for :class:`WorkflowTrackerPort` implementations.

Selects a concrete adapter based on configuration. Mirrors the selection
recipe established by SIP-0061 (LangFuse) and SIP-0087 (log forwarder):

- Prefect-shaped config with ``api_url`` set → :class:`PrefectReporter`.
- Anything else → :class:`NoOpWorkflowTracker`.

The returned port is always non-None — callers never null-check.
"""

from __future__ import annotations

import logging

from adapters.cycles.noop_workflow_tracker import NoOpWorkflowTracker
from squadops.config.schema import PrefectConfig
from squadops.ports.cycles import WorkflowTrackerPort

logger = logging.getLogger(__name__)


def create_workflow_tracker(prefect_cfg: PrefectConfig | None) -> WorkflowTrackerPort:
    """Build the right workflow tracker for the given config."""
    if prefect_cfg is None or not prefect_cfg.api_url:
        return NoOpWorkflowTracker()
    try:
        from adapters.cycles.prefect_reporter import PrefectReporter

        tracker = PrefectReporter(api_url=prefect_cfg.api_url)
        logger.info(
            "Workflow tracker initialized (backend=prefect, api_url=%s)",
            prefect_cfg.api_url,
        )
        return tracker
    except Exception as e:
        logger.error("Failed to initialize workflow tracker; falling back to NoOp: %s", e)
        return NoOpWorkflowTracker()


__all__ = ["create_workflow_tracker"]
