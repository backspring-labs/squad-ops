"""Reading the artifact vault, where an unreadable ref reads as absent (#1990).

The repository's rule: an artifact that cannot be read reads as absent, with a warning naming
it, never silently. Six reads broke it, each looking through a set of refs for the one it wanted
and skipping a failed retrieve with a bare ``continue``. An unreadable ref was then the same as a
ref of another kind, and a vault fault showed only as its consequence (no manifest, no plan, a
criterion blocked) with nothing saying why.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

logger = logging.getLogger(__name__)


async def retrieve_or_absent(
    vault: ArtifactVaultPort, ref_id: str
) -> tuple[ArtifactRef, bytes] | None:
    """``vault.retrieve(ref_id)``, or ``None`` with a warning naming the ref when it cannot be
    read."""
    try:
        return await vault.retrieve(ref_id)
    except Exception as e:  # noqa: BLE001 — absent by the rule, and named
        logger.warning(
            "artifact %s could not be read, so it reads as absent (%s: %s)",
            ref_id,
            type(e).__name__,
            e,
        )
        return None
