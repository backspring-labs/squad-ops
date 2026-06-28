"""Canonical names for cycle-execution artifacts.

Single source of truth for names that are *written* by one component and
*reconstructed* by another. Today: the Prefect flow-run name — produced by the
dispatched flow executor and reconstructed by the cancel routes to find the
flow run to cancel (#77). Keeping the format here means producer and consumer
can never silently drift apart.
"""

from __future__ import annotations


def flow_run_name(project_id: str, cycle_id: str, run_id: str) -> str:
    """Prefect flow-run name for a cycle run: ``<project>/<cyc[:12]>/<run[:12]>``."""
    return f"{project_id}/{cycle_id[:12]}/{run_id[:12]}"
