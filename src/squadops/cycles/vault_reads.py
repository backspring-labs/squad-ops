"""Reading the artifact vault: what a failed read means, said once.

Two rules, and a read declares which one it is under by the function it calls.

**A recorded artifact is required** (#3128, the 2.9 plan's item 4): :func:`retrieve_recorded`. A
run's record names the artifact, so the vault holds it or the vault is at fault. A read that fails
raises :class:`ArtifactUnavailable`, which ends the run ``infrastructure_failed`` and names the
artifact. An input being optional is decided from the record, before any read: the run wrote
none, so nothing is read. A retrieval that failed is never read as that.

**A ref of unknown kind may read as absent** (#1990): :func:`retrieve_or_absent`. Six reads each
looked through a set of refs for the one they wanted and skipped a failed retrieve with a bare
``continue``. An unreadable ref was then the same as a ref of another kind, and a vault fault
showed only as its consequence, with nothing saying why. This read warns and names the ref. It
stays for callers outside the executor's run (the API's views, the Campaign's ledger), where no
run exists to end.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from squadops.cycles.failure_attribution import (
    ARTIFACT_MISSING,
    ARTIFACT_UNREADABLE,
    ARTIFACT_UNRETRIEVED,
)
from squadops.cycles.models import ArtifactNotFoundError, ArtifactUnreadableError

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef
    from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

logger = logging.getLogger(__name__)


def unavailable_kind(error: Exception) -> str:
    """How a retrieval failed (#3120): a missing artifact and a damaged one are facts about the
    vault's contents, and anything else is the vault not answering, or failing otherwise."""
    if isinstance(error, ArtifactNotFoundError):
        return ARTIFACT_MISSING
    if isinstance(error, ArtifactUnreadableError):
        return ARTIFACT_UNREADABLE
    return ARTIFACT_UNRETRIEVED


class ArtifactUnavailable(RuntimeError):
    """An artifact a run's record names couldn't be read from the vault (#3128).

    ``what`` says what the artifact is to the run, in words a reader of the run's ending can act
    on. ``kind`` is the run's ``failure_classification``: ``artifact_missing``,
    ``artifact_unreadable`` or ``artifact_unretrieved`` (:func:`unavailable_kind`).
    """

    def __init__(self, artifact_id: str, what: str, kind: str, error: Exception):
        self.artifact_id, self.what, self.kind = artifact_id, what, kind
        super().__init__(
            f"{what} (artifact {artifact_id}) couldn't be read from the vault ({kind}): "
            f"{type(error).__name__}: {error}. The run's record names it, so it is never "
            "treated as absent"
        )


async def retrieve_recorded(
    vault: ArtifactVaultPort | None, ref_id: str, *, what: str
) -> tuple[ArtifactRef, bytes]:
    """``vault.retrieve(ref_id)`` for an artifact the run's record names.

    Raises :class:`ArtifactUnavailable` on any failure, a missing vault included. The caller
    lets it propagate: the run ends ``infrastructure_failed`` with the kind as its classification
    (``run_completion.resolve_terminal_outcome``).
    """
    try:
        if vault is None:
            raise LookupError("no artifact vault")
        return await vault.retrieve(ref_id)
    except Exception as e:  # noqa: BLE001 - every way it failed is named, never skipped
        raise ArtifactUnavailable(ref_id, what, unavailable_kind(e), e) from e


async def retrieve_or_absent(
    vault: ArtifactVaultPort | None, ref_id: str
) -> tuple[ArtifactRef, bytes] | None:
    """``vault.retrieve(ref_id)``, or ``None`` with a warning naming the ref when it cannot be
    read. A caller with no vault reads every ref as absent, as it always did (by the same catch)."""
    try:
        if vault is None:
            raise LookupError("no artifact vault")
        return await vault.retrieve(ref_id)
    except Exception as e:  # noqa: BLE001 — absent by the rule, and named
        logger.warning(
            "artifact %s could not be read, so it reads as absent (%s: %s)",
            ref_id,
            type(e).__name__,
            e,
        )
        return None
