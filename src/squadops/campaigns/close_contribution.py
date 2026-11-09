"""A Campaign that closes with an accepted increment has one contribution due to the product, and
the supervisor opens it (SIP-0109 §24dc, #2861).

Campaigns 4 and 6 on ``prj-shelfnote`` closed with accepted increments that lived only on their
campaign branches, and the next Campaign started without them. So:
- **the closing row says what is due.** The row that completes a repository-backed Campaign (its
  terminal decision, or the abort) carries ``contribution``: ``due`` with the accepted increments,
  or not due with why (``no accepted increment``). That is all a close does. It pushes nothing and
  opens nothing, whatever the deploy holds: the owner chose to drop the automatic open on
  2026-11-04, keeping §24ci (b) as ruled;
- **the supervisor opens it.** ``POST /api/v1/campaigns/{id}/contributions``, with the supervisor's
  own token (``squadops campaigns contribute <id> --token-from-gh``), calls
  ``CampaignContribution.open``. ``squadops.projects.contribution.contribute_campaign`` makes one
  commit on the branch's head with the criterion files moved (#2860's interim, made the rule),
  pushes it as ``squadops/<campaign>`` and records it ``pending`` as the Project's contribution.
  ``projects.review_request_tokens`` is never read here. Merging stays the owner's;
- **a failed attempt is recorded.** Each one writes a ``contribution_failed`` row naming why, and
  the contribution stays due for the supervisor's next request.

A Campaign closed before this rule carries no ``contribution`` on its closing row, and the request
is refused: its work was contributed by hand, or is the owner's to contribute.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Mapping
from functools import partial
from typing import Any

from squadops.campaigns.acceptance import Held
from squadops.campaigns.acceptance_run import FrozenCriterion
from squadops.campaigns.campaign_branch import BranchBase, branch_base, head
from squadops.campaigns.evaluator_trees import BundleIncomplete
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
)
from squadops.campaigns.review_push import (
    OPENED_AFTER_CLOSE,
    campaign_push_lock,
    review_body,
    review_title,
)
from squadops.campaigns.runner_acceptance import (
    ProductTestSurface,
    RunnerAcceptance,
    RunnerSetup,
    SandboxTree,
    freeze_product_bundle,
    frozen_on_runner,
)

logger = logging.getLogger(__name__)

#: The closing row's key for what its contribution is (§24dc).
CONTRIBUTION_KEY = "contribution"
#: The kinds whose acceptance is an increment's: the increment itself, or its repair or retry.
INCREMENT_FAMILY = frozenset({CycleKind.INCREMENT, CycleKind.REPAIR, CycleKind.RETRY})
#: Why a closing row records nothing due.
NO_ACCEPTED_INCREMENT = "no accepted increment: the Campaign opens no contribution"


def accepted_on_branch(
    log: Iterable[ControlLogEntry], intents: Iterable[LaunchIntent]
) -> tuple[tuple[str, str | None], ...]:
    """Each accepted increment on the Campaign's branch, in promotion order: its cycle, and the
    commit that holds it now. A rebase (§24bv point 4) replays each commit as a new one, so the
    commit is followed through every rebase since; ``None`` when a rebase dropped it, because the
    commit it rebased onto already held its change (the owner's merge, §24cd point 4). A sample
    application's increments name no commit, and aren't listed."""
    kinds: dict[str, CycleKind] = {i.cycle_id: i.cycle_kind for i in intents if i.cycle_id}
    current: dict[str, str | None] = {}
    for e in log:
        if e.outcome is not ControlOutcome.APPLIED:
            continue
        b = e.binding
        cycle_id = b.get("cycle_id")
        if (
            e.operation is ControlOperation.PROMOTE
            and b.get("commit")
            and isinstance(cycle_id, str)
            and kinds.get(cycle_id) in INCREMENT_FAMILY
        ):
            current.setdefault(cycle_id, b["commit"])
        elif e.operation is ControlOperation.BRANCH_REBASED:
            replayed = {old: new for old, new in b.get("replayed") or ()}
            dropped = set(b.get("dropped") or ())
            for cycle_id, commit in current.items():
                if commit in dropped:
                    current[cycle_id] = None
                elif commit in replayed:
                    current[cycle_id] = replayed[commit]
    return tuple(current.items())


def closing_contribution(
    log: Iterable[ControlLogEntry], intents: Iterable[LaunchIntent], *, repository_backed: bool
) -> dict | None:
    """What the row that closes a Campaign records of its contribution (§24dc): ``None`` for a
    sample application's, which has no product to contribute to; otherwise due with the accepted
    increments' cycles, or not due and why."""
    if not repository_backed:
        return None
    accepted = [cycle_id for cycle_id, _commit in accepted_on_branch(log, intents)]
    if not accepted:
        return {"due": False, "reason": NO_ACCEPTED_INCREMENT}
    return {"due": True, "accepted": accepted}


def closing_binding(
    transition: CampaignTransition,
    log: list[ControlLogEntry],
    intents: Iterable[LaunchIntent],
) -> dict:
    """What a registry adds to a closing row, under the Campaign's lock, from the log and intents
    as the row commits on them (§24dc). A promotion that committed since the caller read anything
    is on the record, so accepted work is never closed over as ``due: false``."""
    if transition.repository_backed is None:
        return {}
    backed = transition.repository_backed or branch_base(log) is not None
    contribution = closing_contribution(log, intents, repository_backed=backed)
    return {} if contribution is None else {CONTRIBUTION_KEY: contribution}


def closing_row(log: Iterable[ControlLogEntry]) -> ControlLogEntry | None:
    """The applied row that completed the Campaign: its terminal decision, or the abort."""
    return next(
        (
            e
            for e in log
            if e.outcome is ControlOutcome.APPLIED
            and e.next_state is CampaignState.COMPLETED
            and e.prior_state is not CampaignState.COMPLETED
        ),
        None,
    )


def criterion_paths(log: Iterable[ControlLogEntry]) -> tuple[str, ...]:
    """Every criterion file the Campaign's promotions froze (§8.1), retired ones too: each is a
    test file the Campaign placed on its branch."""
    paths: list[str] = []
    for e in log:
        if e.operation is ControlOperation.PROMOTE and e.outcome is ControlOutcome.APPLIED:
            for criterion in e.binding.get("frozen_criteria") or ():
                path = criterion.get("test_path")
                if path and path not in paths:
                    paths.append(path)
    return tuple(paths)


def live_criteria(log: Iterable[ControlLogEntry]) -> dict[str, str]:
    """Each criterion the Campaign's promotions froze and none retired, by id, with its test file:
    what its branch must still hold (§8.1)."""
    live: dict[str, str] = {}
    for e in log:
        if e.operation is ControlOperation.PROMOTE and e.outcome is ControlOutcome.APPLIED:
            for criterion_id in e.binding.get("retired_criteria") or ():
                live.pop(criterion_id, None)
            for criterion in e.binding.get("frozen_criteria") or ():
                if criterion.get("test_path"):
                    live[criterion["criterion_id"]] = criterion["test_path"]
    return live


class CampaignContribution:
    """Opens a closed Campaign's contribution, after its close commits (§24dc)."""

    def __init__(
        self,
        *,
        campaigns: Any,
        projects: Any,
        repository: Any,
        forge: Any,
        #: Where the moved criteria are run before anything leaves. ``None`` where the runtime has
        #: no sandbox: a contribution that moved a file is then refused, named.
        sandbox: Any | None,
    ) -> None:
        self._campaigns = campaigns
        self._projects = projects
        self._repository = repository
        self._forge = forge
        self._sandbox = sandbox

    async def open(
        self, campaign_id: str, *, token: str, actor: str, actor_role: str
    ) -> tuple[Any, bool]:
        """Open the closed Campaign's contribution, once, at the supervisor's request and with its
        ``token``. Serialized with the Campaign's review pushes. Returns the contribution and
        whether it was recorded already.

        Raises:
            squadops.projects.contribution.ContributionRefused: The Campaign hasn't closed, closed
                before this rule, or has no accepted increment (nothing written); or the
                contribution path refused it (recorded as ``contribution_failed``).
            squadops.projects.models.SourceUnavailable: The clone or the product refused
                (recorded).
            squadops.ports.projects.review_request.ReviewRequestFailed: The forge refused
                (recorded).
        """
        async with campaign_push_lock(campaign_id):
            return await self._open(campaign_id, token, actor, actor_role)

    async def _open(
        self, campaign_id: str, token: str, actor: str, actor_role: str
    ) -> tuple[Any, bool]:
        # deferred (pair): squadops.projects imports this package at load
        from squadops.ports.projects.review_request import ReviewRequestFailed

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.contribution import ContributionRefused, contribute_campaign

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.models import SourceUnavailable

        campaign = await self._campaigns.get_campaign(campaign_id)
        log = await self._campaigns.control_log(campaign_id)
        self._refuse_unless_due(campaign, log)
        project = await self._projects.get_project(campaign.project_id)
        base = branch_base(log)
        assert base is not None  # an accepted increment is on a branch, which has a base
        try:
            return await contribute_campaign(
                project,
                campaign_id,
                head=head(campaign, log).commit,
                base=base.commit,
                criterion_paths=criterion_paths(log),
                title=review_title(campaign),
                body=review_body(campaign, log, OPENED_AFTER_CLOSE),
                registry=self._projects,
                repository=self._repository,
                forge=self._forge,
                token=token,
                actor=actor,
                idempotency_key=f"campaign-contribution:{campaign_id}",
                verify=partial(
                    self._criteria_held,
                    campaign_id,
                    campaign.project_id,
                    base,
                    live_criteria(log),
                ),
            )
        except (ContributionRefused, SourceUnavailable, ReviewRequestFailed) as e:
            await self._failed(campaign_id, e, actor, actor_role)
            raise

    async def _criteria_held(
        self,
        campaign_id: str,
        project_id: str,
        base: BranchBase,
        criteria: Mapping[str, str],
        moved: Any,
    ) -> None:
        """Each live criterion the move touched, run alone on the product's runner in the sandbox,
        on the moved tree: the acceptance path a rebase's frozen criteria take (§24cd point 5). A
        move changes where a test file runs, so a file that passed at the root may not pass under
        ``tests/``. A retired criterion moves and isn't run.

        Raises:
            squadops.projects.contribution.ContributionRefused: No sandbox; no derived profile at
                the branch's base; a moved file no runner holds, or a runner other than the one
                that held it; a bundle that can't be frozen; or one not held, each named.
        """
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import DerivedProfileNotFoundError

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.contribution import ContributionRefused

        if self._sandbox is None:
            raise ContributionRefused(
                "this runtime has no sandbox to run the moved criterion files in, so they can't "
                "be verified and nothing leaves"
            )
        try:
            profile = await self._projects.get_derived_profile(
                project_id, at=(base.commit, base.revision)
            )
        except DerivedProfileNotFoundError as e:
            raise ContributionRefused(
                f"no derived profile at {base.commit[:12]}, revision {base.revision}, names the "
                "product's runners, so the moved criterion files can't be verified"
            ) from e
        tree = SandboxTree(dict(moved.files), moved.executable)
        surface = ProductTestSurface.of(profile, moved.moves.values())
        frozen = []
        for criterion_id, old in criteria.items():
            new = moved.moves.get(old)
            if new is None:
                continue
            runner = profile.runner_for(new)
            before = profile.runner_for(old)
            if runner is None or (before is not None and before.runner != runner.runner):
                raise ContributionRefused(
                    f"criterion {criterion_id} moved to {new}, where no runner of the product "
                    f"that held {old} reads it"
                )
            try:
                bundle = freeze_product_bundle(criterion_id, tree.file_tree, new, surface, runner)
            except (BundleIncomplete, ValueError) as e:
                raise ContributionRefused(
                    f"criterion {criterion_id} can't be run at {new}: {e}"
                ) from e
            frozen.append(FrozenCriterion(criterion_id, new, bundle))
        configuration = await self._projects.get_development_configuration(
            project_id, base.revision
        )
        try:
            results, _runs = await frozen_on_runner(
                RunnerAcceptance(
                    sandbox=self._sandbox,
                    profile=profile,
                    setup=RunnerSetup.of(configuration.commands),
                    workspace_prefix=f"contribution-{campaign_id}-",
                ),
                subject_id=campaign_id,
                tree=tree,
                frozen=frozen,
                surface=surface,
            )
        except Exception as e:
            logger.exception("campaign_contribution_unverified", extra={"campaign": campaign_id})
            raise ContributionRefused(
                f"the sandbox couldn't run the moved criterion files ({type(e).__name__})"
            ) from e
        paths = {f.criterion_id: f.test_path for f in frozen}
        failed = [
            f"{r.criterion_id} at {paths[r.criterion_id]}: {r.held} ({r.detail})"
            for r in results
            if r.held is not Held.HELD
        ]
        if failed:
            raise ContributionRefused(
                "a moved criterion doesn't hold where it moved, so nothing leaves: "
                + "; ".join(failed)
            )

    def _refuse_unless_due(self, campaign: Campaign, log: list[ControlLogEntry]) -> None:
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.contribution import ContributionRefused

        closing = closing_row(log) if campaign.state is CampaignState.COMPLETED else None
        if closing is None:
            raise ContributionRefused(
                f"campaign {campaign.campaign_id} is {campaign.state.value}: its contribution is "
                "opened after its close (SIP-0109 §24dc)"
            )
        recorded = closing.binding.get(CONTRIBUTION_KEY)
        if recorded is None:
            raise ContributionRefused(
                f"campaign {campaign.campaign_id}'s close records no contribution: a sample "
                "application's, or one closed before SIP-0109 §24dc, is contributed by its owner"
            )
        if not recorded.get("due"):
            raise ContributionRefused(
                f"campaign {campaign.campaign_id} closed with {recorded.get('reason')}"
            )

    async def _failed(self, campaign_id: str, error: Exception, actor: str, role: str) -> None:
        """The attempt's failure, as a record on the closed Campaign: never lost, and never
        raised over the close. Its key is the attempt's own, so each attempt is one row."""
        reason = getattr(error, "reason", None)
        binding = {"error": type(error).__name__, "reason": reason, "message": str(error)[:1000]}
        try:
            await self._campaigns.transition(
                campaign_id,
                CampaignTransition(
                    operation=ControlOperation.CONTRIBUTION_FAILED,
                    actor=actor,
                    actor_role=role,
                    reason=f"the campaign's contribution was not opened: {str(error)[:300]}",
                    idempotency_key=f"contribution-failed:{uuid.uuid4().hex}",
                    next_state=None,
                    binding=binding,
                ),
            )
        except Exception:
            logger.exception(
                "campaign_contribution_failure_not_recorded", extra={"campaign_id": campaign_id}
            )
        logger.warning(
            "campaign_contribution_failed",
            extra={"campaign_id": campaign_id, "error": binding["error"], "reason": reason},
        )
