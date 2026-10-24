"""A repository-backed Campaign's accepted tree is a branch in the managed clone (SIP-0109 §24bv
point 2, §24cd points 1 and 2).

The branch is ``refs/squadops/campaign/<campaign_id>`` in the Project's managed clone. It starts at
the calibration record's commit, and it moves only by promotion: to each accepted increment's
captured commit, in order. The rebase of §24bv point 4 is a later build.

**The control log is the authority, and the ref is its projection** (§24cd point 2). A ref can't
join the registry's transaction, so:
1. the PROMOTE row commits first, with the commit beside the tree's identity
   (``AcceptedTree.commit``);
2. the ref then follows it by compare-and-swap, from the commit the row replaced;
3. a ref that disagrees with its campaign's row is moved to the row, at startup and on the
   sweep's interval. A process can stop between steps 1 and 2, and a follow can fail.

Everything that reads the head reads the row (:func:`head`), never the ref.

**An increment is promoted only from its own capture** (contract 3). Its run's delivery captured
the candidate as one commit on the commit it seeded, and recorded both mappings. The promotion
takes that commit only when its parent is the head, so the branch holds the accepted increments
in order. A capture built on any other commit is refused, and the campaign escalates naming it.
A failed increment's capture stays at its own ref (``refs/squadops/<cycle>/<run>``), off the
branch, as evidence (§7.5).

Nothing here pushes. Whether and when the Campaign's review request is pushed is the owner's
ruling (§24cd point 7).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from squadops.campaigns.models import (
    AcceptedTree,
    Campaign,
    CampaignError,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)

if TYPE_CHECKING:
    from squadops.cycles.models import ArtifactRef
    from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
    from squadops.ports.cycles.project_registry import ProjectRegistryPort
    from squadops.ports.projects.source_repository import SourceRepositoryPort

logger = logging.getLogger(__name__)


def campaign_ref(campaign_id: str) -> str:
    """Where a campaign's branch is kept in the managed clone: our namespace, which no fetch
    writes or prunes."""
    return f"refs/squadops/campaign/{campaign_id}"


@dataclass(frozen=True)
class CampaignHead:
    """The head of a campaign's branch, as its control log records it (§24cd point 1): what the
    next increment is pinned at and compared against."""

    commit: str
    tree_identity: str
    #: The source verification of the increment whose promotion made this the head: the next
    #: increment's regression baseline (§24bv point 3). ``None`` at the calibration record's
    #: commit, whose baseline is the record's inherited one.
    previous_verification_ref: str | None


class NoCampaignHead(CampaignError):
    """The campaign's accepted tree names no commit: a sample application's, one not promoted
    yet, or a record promoted before the branch existed. An increment needing a head is refused,
    never given a default."""


class PromotionRefused(CampaignError):
    """An increment the cycle accepted can't be promoted onto the branch, and why. Nothing was
    written: the accepted tree and the branch stay where they were (§7.5)."""


def head(campaign: Campaign, log: Iterable[ControlLogEntry]) -> CampaignHead:
    """The head of ``campaign``'s branch, read from its row and its control log, never from the
    clone's ref.

    Raises:
        NoCampaignHead: The accepted tree names no commit.
    """
    accepted = campaign.accepted
    if accepted is None or accepted.commit is None:
        raise NoCampaignHead(
            f"campaign {campaign.campaign_id}'s accepted tree names no commit, so it has no "
            "campaign branch to build on (SIP-0109 §24bv point 2)"
        )
    verification = None
    for entry in log:
        if (
            entry.operation is ControlOperation.PROMOTE
            and entry.outcome is ControlOutcome.APPLIED
            and entry.binding.get("commit") == accepted.commit
        ):
            verification = entry.binding.get("verification_ref")
    return CampaignHead(accepted.commit, accepted.identity, verification)


@dataclass(frozen=True)
class BranchPromotion:
    """What an increment's promotion onto the branch commits: the tree it makes the accepted one,
    the commit the branch held before it, and the run's source verification."""

    accepted: AcceptedTree
    parent: str
    verification_ref: str


class CampaignBranch:
    """The campaign branch's reads and moves, over the Project's mappings and its managed
    clone."""

    def __init__(self, *, projects: ProjectRegistryPort, repository: SourceRepositoryPort) -> None:
        self._projects = projects
        self._repository = repository

    async def promotion(
        self, campaign: Campaign, cycle_id: str, run_id: str, run_artifacts: list[ArtifactRef]
    ) -> BranchPromotion:
        """The promotion of run ``run_id``'s captured change onto ``campaign``'s branch, read
        before anything is written. A replay, after a restart between the promotion and the
        decision, finds the capture already the head and promotes the same tree again.

        Raises:
            PromotionRefused: The campaign has no head; the run captured nothing, or recorded no
                verification; or the capture's parent isn't the head.
        """
        # deferred (pair): squadops.projects imports this package at load (workspaces' FileTree)
        from squadops.projects.verification import SOURCE_VERIFICATION_TYPE

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.workspaces import captured_change

        try:
            at = head(campaign, ())
        except NoCampaignHead as e:
            raise PromotionRefused(str(e)) from e
        mappings = await self._projects.source_mappings(campaign.project_id)
        try:
            capture = captured_change(mappings, cycle_id, run_id)
        except ValueError as e:
            raise PromotionRefused(str(e)) from e
        if capture is None:
            raise PromotionRefused(
                f"run {run_id} of cycle {cycle_id} captured no change: only a change the "
                "product's own checks accepted is promoted onto the campaign branch"
            )
        if at.commit not in (capture.parent, capture.commit):
            raise PromotionRefused(
                f"cycle {cycle_id}'s capture {capture.commit[:12]} was built on "
                f"{capture.parent[:12]}, and the campaign branch's head is {at.commit[:12]}: only "
                "a change built on the head follows it (SIP-0109 §24bv point 2)"
            )
        verifications = sorted(
            (r for r in run_artifacts if r.artifact_type == SOURCE_VERIFICATION_TYPE),
            key=lambda r: str(r.created_at),
        )
        if not verifications:
            raise PromotionRefused(
                f"run {run_id} of cycle {cycle_id} recorded no source verification: a capture is "
                "promoted with the checks that accepted it"
            )
        return BranchPromotion(
            accepted=AcceptedTree(capture.tree_identity, cycle_id, commit=capture.commit),
            parent=capture.parent,
            verification_ref=verifications[-1].artifact_id,
        )

    async def follow(self, campaign: Campaign, *, previous: str | None) -> None:
        """Move the branch's ref to the head ``campaign``'s row now records, after that row has
        committed: a compare-and-swap from ``previous``, the commit the row replaced (``None``
        creates the branch). A ref already at the head is a replayed promotion's, or the
        re-sync's. Any other refusal or failure is logged and never raised: the row is the
        authority, and :meth:`resync` moves the ref to it on the sweep's next pass."""
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.models import RefMoved, SourceUnavailable

        accepted = campaign.accepted
        if accepted is None or accepted.commit is None:
            return
        try:
            await self._repository.update_ref(
                campaign.project_id,
                campaign_ref(campaign.campaign_id),
                new_commit=accepted.commit,
                expected_commit=previous,
            )
        except RefMoved as moved:
            if moved.held != accepted.commit:
                logger.error(
                    "campaign_branch_behind_its_row",
                    extra={
                        "campaign_id": campaign.campaign_id,
                        "held": moved.held,
                        "row": accepted.commit,
                    },
                )
        except SourceUnavailable:
            logger.exception(
                "campaign_branch_not_moved",
                extra={"campaign_id": campaign.campaign_id, "commit": accepted.commit},
            )

    async def resync(self, campaigns: CampaignRegistryPort) -> list[str]:
        """Each repository-backed campaign whose ref disagrees with its row is moved to the row
        (§24cd point 2). The ref is read before the row, so a promotion committing in between
        is never undone: the row read is never older than the ref. One that can't be moved is
        logged and does not stop the rest. Returns the campaigns moved."""
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.models import RefMoved

        moved = []
        for project in await self._projects.list_projects():
            if project.source is None:
                continue
            for listed in await campaigns.list_campaigns(project.project_id):
                if listed.accepted is None or listed.accepted.commit is None:
                    continue
                ref = campaign_ref(listed.campaign_id)
                try:
                    held = await self._repository.ref_commit(project.project_id, ref)
                    row = (await campaigns.get_campaign(listed.campaign_id)).accepted
                    if row is None or row.commit is None or row.commit == held:
                        continue
                    await self._repository.update_ref(
                        project.project_id, ref, new_commit=row.commit, expected_commit=held
                    )
                except RefMoved:
                    logger.info(
                        "campaign_branch_moved_meanwhile", extra={"campaign_id": listed.campaign_id}
                    )
                    continue
                except Exception:
                    logger.exception(
                        "campaign_branch_resync_failed", extra={"campaign_id": listed.campaign_id}
                    )
                    continue
                logger.warning(
                    "campaign_branch_resynced",
                    extra={"campaign_id": listed.campaign_id, "from": held, "to": row.commit},
                )
                moved.append(listed.campaign_id)
        return moved
