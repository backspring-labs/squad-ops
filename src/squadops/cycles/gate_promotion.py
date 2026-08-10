"""What an approved gate does to the run's artifacts (SIP-0086).

Approving a gate promotes every artifact the run produced from ``working`` to
``promoted``, which is how the next workload finds them: promotion is what puts the
plan's ref into ``plan_artifact_refs``, and without it an implementation run is admitted
with no plan and refuses (#424).

**This module exists because that was wired to one of the two approval paths.**
``_promote_run_artifacts`` lived in ``api/routes/cycles/runs.py`` and ran only when a gate
was decided over HTTP — a human running ``squadops runs gate --approve``, or an agent
answering a question. M4's question gate (#807) added a second path: when the manifest
declares no unresolved decision, the executor approves the gate itself and never touches
the route. VS roll 4 (``cyc_c82a401a21f8``) is the first cycle in the repo's history to
take it — one ``system:no_open_questions`` row against 37 ``system:plan_validation``
rejections — and its framing passed, its plan validated, its gate approved, and its
implementation run then failed with the plan sitting promoted-never in the framing run's
artifacts.

So promotion is a consequence of *the gate being approved*, not of *how it was approved*,
and it belongs where both callers can reach it rather than in the transport layer of one.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

logger = logging.getLogger(__name__)


async def promote_run_artifacts(vault: ArtifactVaultPort | None, run_id: str) -> int:
    """Promote every ``working`` artifact this run produced. Returns the count promoted.

    Idempotent — already-promoted artifacts are skipped, so a retried or duplicated
    approval costs nothing.

    **Failures are logged, never raised.** The gate decision is the source of truth and is
    already recorded by the time this runs; making promotion able to fail the decision
    would mean an approval could be lost to a transient vault error. A promotion that did
    not happen surfaces downstream as the #424 refusal, which is loud and correct.

    A ``None`` vault is tolerated for the same reason: test contexts that never wired one
    should not have their gate decisions fail.
    """
    if vault is None:
        logger.warning("no artifact vault; skipping promotion for run %s", run_id)
        return 0

    try:
        artifacts = await vault.list_artifacts(run_id=run_id)
    except Exception:
        logger.exception("failed to list artifacts for run %s during promotion", run_id)
        return 0

    promoted = 0
    for art in artifacts:
        if art.promotion_status == "promoted":
            continue
        try:
            await vault.promote_artifact(art.artifact_id)
            promoted += 1
        except Exception:
            logger.exception("failed to promote artifact %s for run %s", art.artifact_id, run_id)

    logger.info("Promoted %d artifact(s) for run %s on gate approval", promoted, run_id)
    return promoted
