"""A repository-backed campaign's branch when upstream moves (SIP-0109 §24bv point 4, §24cd
points 2–5).

Before each launch, the launcher compares the branch's base with the commit and Development
Configuration revision the Project is reconciled at. When they differ:
1. **The launcher never reconciles** (§24cd point 3). The Project must already be reconciled
   there: no relevant drift unreconciled, its inherited baseline captured at that commit and
   revision, and no blocking gap the launch's work meets. Otherwise the launch is refused, and
   the campaign escalates with the intent pending, as for any refused launch (#1971).
2. **The branch's own commits are replayed onto it** in the managed clone
   (``SourceRepositoryPort.rebase``). A commit that conflicts refuses the launch
   (``CAMPAIGN_BRANCH_CONFLICT``), and nothing is resolved by itself. A head upstream already
   holds (the owner merged the review request, §24cd point 4) rebases to the reconciled commit
   itself.
3. **The rebased head is verified** by the product's own checks, attributed against upstream's
   inherited baseline (§24cd point 5), and the verification is stored where ``head`` reads it, so
   it is the next increment's regression baseline. A head whose checks regress, or that no check
   executed and passed, refuses the launch (``REBASED_HEAD_REGRESSED``), naming the stored
   verification. The reconciled commit itself needs none: its baseline is the inherited one.
   The frozen criteria's bundles are not run here: a product's bundles run on its own runner in
   the sandbox, which is §24cd point 6's evaluator, not built yet. The row names each frozen
   criterion left unrun (§24cm).
4. **One ``BRANCH_REBASED`` row** records the base and head before and after, the replayed and
   dropped commits and the verification, and moves the accepted tree. A pending repair or retry,
   built on the old head, is superseded in the same transaction: its increment is abandoned as
   ``upstream_moved``, which counts toward no ``max_unaccepted_increments`` (D10), and row 6's
   fresh proposal is written. Cycles, tokens and time keep their limits: the fresh proposal
   replaces the launch the repair would have been, and the next decision counts its cycle.
5. **The ref follows the row** by compare-and-swap (``CampaignBranch.follow``); the startup and
   sweep re-sync move a ref a stop left behind.
"""

from __future__ import annotations

import dataclasses
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from squadops.campaigns.acceptance_run import frozen_criteria_from
from squadops.campaigns.campaign_branch import (
    BranchBase,
    CampaignBranch,
    CampaignHead,
    branch_base,
    head,
)
from squadops.campaigns.evaluator_trees import FileTree
from squadops.campaigns.increment_tree import frozen_bundle_contents
from squadops.campaigns.launcher import LaunchRefused
from squadops.campaigns.lifecycle import LAUNCHER_ROLE
from squadops.campaigns.models import (
    AcceptedTree,
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    ControlOperationRefused,
    CycleKind,
    LaunchIntent,
    LaunchRequest,
)
from squadops.campaigns.progress import frozen_criteria
from squadops.campaigns.runner_acceptance import (
    ProductTestSurface,
    RunnerAcceptance,
    RunnerSetup,
    SandboxTree,
    frozen_on_runner,
)

if TYPE_CHECKING:
    from squadops.cycles.models import Project
    from squadops.projects.models import CheckoutTree, Rebased
    from squadops.projects.verification import SourceVerification

logger = logging.getLogger(__name__)

#: How an increment the rebase left nothing to continue is abandoned (§24bv point 4, D10).
UPSTREAM_MOVED = "upstream_moved"
#: The refusals a rebase escalates by, as the launch's refusal code (§24bv point 4, §24cm).
CAMPAIGN_BRANCH_CONFLICT = "CAMPAIGN_BRANCH_CONFLICT"
REBASED_HEAD_REGRESSED = "REBASED_HEAD_REGRESSED"
#: The branch's history can't be replayed as a rebase replays it: a merge commit on it, a base
#: that isn't in its history, an id that isn't a commit.
CAMPAIGN_BRANCH_UNREBASEABLE = "CAMPAIGN_BRANCH_UNREBASEABLE"
#: The managed clone doesn't hold the branch: the clone is gone, or a commit is missing from it.
CAMPAIGN_BRANCH_UNAVAILABLE = "CAMPAIGN_BRANCH_UNAVAILABLE"
#: The rebased head can't be verified here: the runtime has no sandbox to run the checks in.
REBASED_HEAD_UNVERIFIABLE = "REBASED_HEAD_UNVERIFIABLE"

#: The repository's refusals that no retry gets past (``SourceUnavailable.reason``), each with the
#: code its launch is refused by. The campaign escalates with the intent pending, and the
#: operator acts. Any other ``SourceUnavailable`` (a timeout, git failing to run, a ref's lock) is
#: an infrastructure fault: nothing is written, the intent stays pending and the campaign where it
#: was, and the next drain (the sweep's, at the latest) repeats the launch.
NEEDS_THE_OPERATOR: dict[str, str] = {
    "not_linear": CAMPAIGN_BRANCH_UNREBASEABLE,
    "not_an_ancestor": CAMPAIGN_BRANCH_UNREBASEABLE,
    "not_a_commit": CAMPAIGN_BRANCH_UNREBASEABLE,
    "commit_missing": CAMPAIGN_BRANCH_UNAVAILABLE,
    "not_cloned": CAMPAIGN_BRANCH_UNAVAILABLE,
}
#: What a rebased head's regression baseline is, as its row names it.
REBASE_VERIFICATION, INHERITED_BASELINE = "rebase_verification", "inherited_baseline"

#: The continuations a rebase supersedes: each continues a candidate built on the old head.
_CONTINUING = frozenset({CycleKind.REPAIR, CycleKind.RETRY})

#: Refuses a launch on a Project not reconciled at its pin (§24cd point 3), raising
#: ``LaunchRefused``: the cycle-create path's own gates, given the launch's request.
Reconciled = Callable[["Project", LaunchIntent], Awaitable[None]]
#: Row 6's fresh proposal on the rebased head, or why it can't be launched; given the campaign
#: as the rebase leaves it and the abandoned increment's cycle (``CampaignProgress``).
ProposeAfterRebase = Callable[[Campaign, "str | None"], Awaitable["LaunchRequest | str"]]


@dataclass(frozen=True)
class FrozenAtRebase:
    """What the frozen criteria's bundles run on at a rebase (§24cd point 5): the rebased head's
    tree (its files and executable bits), every criterion the campaign's promotions froze, and the
    pin whose derived profile names the product's test surface. ``subject_id`` is the rebase's
    own key, so a re-run of the same rebase is the same subject."""

    subject_id: str
    campaign_id: str
    project_id: str
    pin: BranchBase
    tree: CheckoutTree
    frozen: tuple[dict, ...]


#: §24cd point 5's second half, the frozen criteria's bundles on the product's own runner: each
#: criterion's reading by its id, as ``(held, detail)``. The runtime's is
#: ``ProductRunnerFrozen``, #2774's ``runner_acceptance.frozen_on_runner`` called as its §24cl
#: item 10 states.
FrozenOnRunner = Callable[[FrozenAtRebase], Awaitable[Mapping[str, tuple[str, str]]]]
#: The reading a frozen criterion's bundle must give for the rebase to stand.
HELD = "held"


class FrozenUnrunnable(RuntimeError):
    """The frozen criteria can't be run here: no sandbox, or no derived profile at the pin."""


class ProductRunnerFrozen:
    """The frozen criteria's bundles on the rebased head, on the product's runner in the sandbox
    (§24cd point 5): #2774's ``frozen_on_runner``, called exactly as its §24cl item 10 states."""

    def __init__(self, *, sandbox: Any, projects: Any, vault: Any) -> None:
        self._sandbox = sandbox
        self._projects = projects
        self._vault = vault

    async def __call__(self, at: FrozenAtRebase) -> Mapping[str, tuple[str, str]]:
        """Each criterion's reading by its id.

        Raises:
            FrozenUnrunnable: The runtime has no sandbox, or the pin no derived profile.
        """
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import DerivedProfileNotFoundError

        if self._sandbox is None:
            raise FrozenUnrunnable("the runtime API has no sandbox client to run them in")
        try:
            profile = await self._projects.get_derived_profile(
                at.project_id, at=(at.pin.commit, at.pin.revision)
            )
        except DerivedProfileNotFoundError as e:
            raise FrozenUnrunnable(
                f"the pin {at.pin.commit[:12]}, revision {at.pin.revision}, has no derived "
                "profile to name the product's runners"
            ) from e
        configuration = await self._projects.get_development_configuration(
            at.project_id, at.pin.revision
        )
        pinned = [dict(p) for p in at.frozen]
        bundles = await frozen_bundle_contents(
            self._vault, {"campaign_proposal": {"frozen_criteria": pinned}}
        )
        results, _runs = await frozen_on_runner(
            RunnerAcceptance(
                sandbox=self._sandbox,
                profile=profile,
                setup=RunnerSetup.of(configuration.commands),
                workspace_prefix=rebase_workspace_prefix(at.campaign_id, at.tree.commit),
                verified_candidate_revision=None,
            ),
            subject_id=at.subject_id,
            tree=SandboxTree(dict(at.tree.files), frozenset(at.tree.executable)),
            frozen=frozen_criteria_from(pinned, bundles),
            surface=ProductTestSurface.of(profile, {str(p.get("test_path") or "") for p in pinned}),
        )
        return {r.criterion_id: (str(r.held), r.detail) for r in results}


def rebase_workspace_prefix(campaign_id: str, commit: str) -> str:
    """The start of every workspace a rebase's frozen bundles seed: one per overlay."""
    return f"rebase-{campaign_id}-{commit[:12]}-frozen-"


@dataclass(frozen=True)
class RebasedHead:
    """What a rebase made: the rebased head, its tree, and its verification's vault id, or
    ``None`` when the head is the reconciled commit itself."""

    rebased: Rebased
    tree_identity: str
    verification_ref: str | None
    summary: str
    #: The frozen criteria whose bundles ran on the rebased head and held: every one, or the
    #: rebase is refused.
    frozen_held: tuple[str, ...] = ()


def needs_rebase(base: BranchBase | None, project: Project) -> bool:
    """Whether the branch's base is behind the Project's reconciled pin (§24bv point 4): another
    commit, or the same commit at another Development Configuration revision, whose checks the
    head's verification didn't run as the next increment's will (FR-20). A sample application,
    or a Project not yet pinned (refused at cycle creation by name), never rebases."""
    if base is None or project.source is None:
        return False
    commit, revision = (
        project.development_baseline_commit,
        project.development_configuration_revision,
    )
    if commit is None or revision is None:
        return False
    return (base.commit, base.revision) != (commit, revision)


def rebase_transition(
    campaign: Campaign,
    intent: LaunchIntent,
    *,
    base: BranchBase,
    before: CampaignHead,
    onto: BranchBase,
    made: RebasedHead,
    launch: LaunchRequest | None,
    unbuilt: str | None,
    actor: str,
) -> CampaignTransition:
    """The rebase's one row (§24cd point 2). Keyed by the base it moves from and the pin it moves
    to, so a second launcher acting on the same base is a replay or a conflict, never a second
    rebase. A continuation ``intent`` is superseded: the campaign proposes on the rebased head
    (``launch``), or escalates naming why the proposal can't be launched (``unbuilt``)."""
    accepted = campaign.accepted
    assert accepted is not None and made.rebased.commit
    supersedes = intent.cycle_kind in _CONTINUING
    binding: dict[str, Any] = {
        "base_before": base.commit,
        "development_configuration_revision_before": base.revision,
        "head_before": before.commit,
        "base": onto.commit,
        "development_configuration_revision": onto.revision,
        "commit": made.rebased.commit,
        "identity": made.tree_identity,
        "replayed": [list(pair) for pair in made.rebased.replayed],
        "dropped": list(made.rebased.dropped),
        "verification": REBASE_VERIFICATION if made.verification_ref else INHERITED_BASELINE,
        "verification_ref": made.verification_ref,
        "verification_summary": made.summary,
        # §24cd point 5's bundles, run on the product's runner (§24cm): each one held.
        "frozen_criteria_held": list(made.frozen_held),
    }
    next_state = campaign.state
    if supersedes:
        binding |= {
            "superseded_launch_id": intent.launch_id,
            "abandoned": {"kind": intent.cycle_kind.value, "abandoned_as": UPSTREAM_MOVED},
        }
        next_state = CampaignState.AT_PROPOSAL
        if unbuilt is not None:
            binding["unbuilt"] = unbuilt
            next_state = CampaignState.ESCALATED
    return CampaignTransition(
        operation=ControlOperation.BRANCH_REBASED,
        actor=actor,
        actor_role=LAUNCHER_ROLE,
        reason=(
            f"upstream moved: the campaign branch rebased from {base.commit[:12]} onto "
            f"{onto.commit[:12]} (revision {onto.revision}), head {made.rebased.commit[:12]}"
        ),
        idempotency_key=rebase_key(base, onto),
        next_state=next_state,
        expected_state=campaign.state,
        target=intent.launch_id,
        binding=binding,
        accepted=AcceptedTree(
            made.tree_identity,
            cycle_id=accepted.cycle_id,
            calibration_record_id=accepted.calibration_record_id,
            commit=made.rebased.commit,
        ),
        supersedes=intent.launch_id if supersedes else None,
        launch=launch if supersedes and unbuilt is None else None,
    )


def rebase_key(base: BranchBase, onto: BranchBase) -> str:
    """One rebase's identity: the base it moves from and the pin it moves to. Its row's key, and
    the subject its frozen bundles are run under, so a re-run of it is the same subject."""
    return f"rebase:{base.commit}@{base.revision}->{onto.commit}@{onto.revision}"


class BranchRebase:
    """The launcher's step before each launch of a repository-backed campaign (§24bv point 4)."""

    def __init__(
        self,
        *,
        campaigns: Any,
        projects: Any,
        repository: Any,
        sandbox: Any,
        vault: Any,
        branch: CampaignBranch,
        reconciled: Reconciled,
        propose: ProposeAfterRebase,
        actor: str,
        frozen_on_runner: FrozenOnRunner | None = None,
    ) -> None:
        self._campaigns = campaigns
        self._projects = projects
        self._repository = repository
        self._sandbox = sandbox
        self._vault = vault
        self._branch = branch
        self._reconciled = reconciled
        self._propose = propose
        self._actor = actor
        #: ``None`` until #2774's runner is wired (§24cm): every frozen criterion is then named
        #: as unrun on the row.
        self._frozen_on_runner = frozen_on_runner

    async def before_launch(self, campaign: Campaign, intent: LaunchIntent) -> LaunchIntent | None:
        """The intent to launch now: ``intent`` itself when nothing moved, or when a fresh
        increment's branch was rebased under it (it binds the head at drain); the fresh proposal
        that superseded a repair or retry; or ``None`` when nothing launches now (the rebase
        escalated, or the campaign moved since it was read).

        Raises:
            LaunchRefused: The Project isn't reconciled at its pin; the rebase conflicts, or the
                repository refused it in a way no retry gets past (``NEEDS_THE_OPERATOR``); the
                rebased head regressed, by its checks or a frozen criterion; or it can't be
                verified here. The campaign escalates, with ``intent`` pending.
            SourceUnavailable: An infrastructure fault (a timeout, git failing to run). Nothing
                was written; the next drain repeats the launch.
        """
        if intent.cycle_kind is CycleKind.CALIBRATION:
            return intent
        log = await self._campaigns.control_log(campaign.campaign_id)
        base = branch_base(log)
        project = await self._projects.get_project(campaign.project_id)
        if base is None or not needs_rebase(base, project):
            return intent
        await self._reconciled(project, intent)
        assert project.development_baseline_commit and project.development_configuration_revision
        onto = BranchBase(
            project.development_baseline_commit, project.development_configuration_revision
        )
        before = head(campaign, log)
        made = await self._rebased(
            campaign, project, base, before, onto, tuple(frozen_criteria(log))
        )
        launch = unbuilt = None
        if intent.cycle_kind in _CONTINUING:
            accepted = campaign.accepted
            assert accepted is not None  # a branch has a base, so its tree was promoted
            moved = dataclasses.replace(
                campaign,
                accepted=dataclasses.replace(
                    accepted, identity=made.tree_identity, commit=made.rebased.commit
                ),
            )
            built = await self._propose(moved, _continued(intent))
            launch, unbuilt = (built, None) if isinstance(built, LaunchRequest) else (None, built)
        transition = rebase_transition(
            campaign,
            intent,
            base=base,
            before=before,
            onto=onto,
            made=made,
            launch=launch,
            unbuilt=unbuilt,
            actor=self._actor,
        )
        try:
            result = await self._campaigns.transition(campaign.campaign_id, transition)
        except ControlOperationRefused as refused:
            # The campaign moved since it was read (a pause, an abort, another launcher's rebase
            # or launch): its own row says why, and the next drain reads it again.
            logger.info(
                "campaign_branch_rebase_refused",
                extra={"campaign_id": campaign.campaign_id, "refusal": refused.entry.refusal},
            )
            return None
        await self._branch.follow(result.campaign, previous=before.commit)
        logger.warning(
            "campaign_branch_rebased",
            extra={
                "campaign_id": campaign.campaign_id,
                "from": base.commit,
                "onto": onto.commit,
                "head": made.rebased.commit,
                "superseded": transition.supersedes,
            },
        )
        if transition.supersedes is None:
            return intent
        return result.intent

    async def _rebased(
        self,
        campaign: Campaign,
        project: Project,
        base: BranchBase,
        before: CampaignHead,
        onto: BranchBase,
        frozen: tuple[dict, ...],
    ) -> RebasedHead:
        """The branch's commits replayed onto ``onto``, and the rebased head verified: by the
        product's checks, then by the frozen criteria's bundles on the product's runner."""
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.verification import ACCEPTED

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.workspaces import SandboxUnavailable

        rebased = await self._replayed(campaign, base, before, onto)
        tree = await self._repository.tree_at(campaign.project_id, rebased.commit)
        identity = FileTree.of(tree.files).identity
        held = await self._frozen_held(campaign, base, onto, rebased, tree, frozen)
        if rebased.commit == onto.commit:
            return RebasedHead(
                rebased, identity, None, "the reconciled commit: its inherited baseline", held
            )
        try:
            verification = await self._verified(
                campaign, project, tree, base, before, onto, rebased
            )
        except SandboxUnavailable as e:
            raise LaunchRefused(
                f"{REBASED_HEAD_UNVERIFIABLE}: the campaign branch rebased onto the reconciled "
                f"{onto.commit[:12]}, and its head can't be verified here: {e}"
            ) from e
        ref = await self._store(campaign, verification)
        if verification.verdict != ACCEPTED:
            raise LaunchRefused(
                f"{REBASED_HEAD_REGRESSED}: the campaign branch rebased onto the reconciled "
                f"{onto.commit[:12]} at {rebased.commit[:12]}, and its checks read "
                f"{verification.summary()} (verification {ref}): a break upstream caused is "
                "found here, never blamed on the next increment"
            )
        return RebasedHead(rebased, identity, ref, verification.summary(), held)

    async def _replayed(
        self, campaign: Campaign, base: BranchBase, before: CampaignHead, onto: BranchBase
    ) -> Rebased:
        """The clone's rebase, its refusals sorted by who can get past them (§24cm): a conflict,
        and each reason in ``NEEDS_THE_OPERATOR``, escalate; anything else is a fault the next
        drain repeats, logged here by name."""
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.models import RebaseConflict, SourceUnavailable

        try:
            return await self._repository.rebase(
                campaign.project_id, base=base.commit, head=before.commit, onto=onto.commit
            )
        except RebaseConflict as e:
            raise LaunchRefused(
                f"{CAMPAIGN_BRANCH_CONFLICT}: the campaign branch doesn't rebase from "
                f"{base.commit[:12]} onto the reconciled {onto.commit[:12]}: {e}. Resolve it in "
                "the product, reconcile the Project, and resume"
            ) from e
        except SourceUnavailable as e:
            code = NEEDS_THE_OPERATOR.get(e.reason)
            if code is None:
                logger.warning(
                    "campaign_branch_rebase_unavailable",
                    extra={"campaign_id": campaign.campaign_id, "reason": e.reason},
                )
                raise
            raise LaunchRefused(
                f"{code}: the campaign branch can't be rebased from {base.commit[:12]} onto the "
                f"reconciled {onto.commit[:12]} ({e.reason}): {e}"
            ) from e

    async def _frozen_held(
        self,
        campaign: Campaign,
        base: BranchBase,
        onto: BranchBase,
        rebased: Rebased,
        tree: CheckoutTree,
        frozen: tuple[dict, ...],
    ) -> tuple[str, ...]:
        """§24cd point 5: every frozen criterion's bundle on the rebased head, by the product's
        runner. Returns the criteria that held, which is all of them. Fails closed (the third
        review, SIP-0112 H.12): frozen criteria with no runner to run them, or a runner that
        can't run here, refuse the rebase as unverifiable; a reading that isn't ``held`` (a
        blocked one included) or a criterion left unread refuses it as regressed."""
        ids = tuple(str(c["criterion_id"]) for c in frozen)
        if not frozen:
            return ()
        unverifiable = (
            f"{REBASED_HEAD_UNVERIFIABLE}: the campaign branch rebased onto the reconciled "
            f"{onto.commit[:12]} at {rebased.commit[:12]}, and its frozen criteria can't be read "
            f"there"
        )
        if self._frozen_on_runner is None:
            raise LaunchRefused(
                f"{unverifiable}: no runner runs their bundles; unread: {', '.join(ids)}"
            )
        try:
            readings = await self._frozen_on_runner(
                FrozenAtRebase(
                    rebase_key(base, onto), campaign.campaign_id, campaign.project_id, onto,
                    tree, frozen,
                )
            )  # fmt: skip
        except FrozenUnrunnable as e:
            raise LaunchRefused(f"{unverifiable}: {e}; unread: {', '.join(ids)}") from e
        broken = [
            f"{c} ({readings[c][0]}: {readings[c][1]})" if c in readings else f"{c} (unread)"
            for c in ids
            if c not in readings or readings[c][0] != HELD
        ]
        if broken:
            raise LaunchRefused(
                f"{REBASED_HEAD_REGRESSED}: the campaign branch rebased onto the reconciled "
                f"{onto.commit[:12]} at {rebased.commit[:12]}, and its frozen criteria don't all "
                f"hold: {', '.join(broken)}. A break upstream caused is found here, never blamed "
                "on the next increment"
            )
        return ids

    async def _verified(
        self,
        campaign: Campaign,
        project: Project,
        tree: CheckoutTree,
        base: BranchBase,
        before: CampaignHead,
        onto: BranchBase,
        rebased: Rebased,
    ) -> SourceVerification:
        """§24cd point 5: the product's checks on the rebased head, through X-3a as a run's
        candidate's are, attributed against upstream's inherited baseline at the reconciled pin."""
        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.verification import SourceVerification, attributed

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.workspaces import SandboxUnavailable, run_checks, seed_project_tree

        baseline = await self._projects.get_inherited_baseline(campaign.project_id)
        if (baseline.commit, baseline.development_configuration_revision) != (
            onto.commit,
            onto.revision,
        ):
            raise LaunchRefused(
                f"PROJECT_STATE_CONFLICT: the inherited baseline is at {baseline.commit[:12]}, "
                f"revision {baseline.development_configuration_revision}, and the Project is "
                f"reconciled at {onto.commit[:12]}, revision {onto.revision}: capture it there "
                "first (squadops projects baseline)"
            )
        configuration = await self._projects.get_development_configuration(
            campaign.project_id, onto.revision
        )
        upstream = await self._repository.tree_at(campaign.project_id, onto.commit)
        workspace_id = f"rebase-{campaign.campaign_id}-{rebased.commit[:12]}"
        if self._sandbox is None:
            raise SandboxUnavailable("the runtime API has no sandbox client to run checks through")
        await self._sandbox.release_workspace(workspace_id)
        try:
            seeded = await seed_project_tree(
                project,
                rebased.commit,
                workspace_id,
                registry=self._projects,
                repository=self._repository,
                sandbox=self._sandbox,
                campaign_id=campaign.campaign_id,
                tree=tree,
            )
            results, environment = await run_checks(self._sandbox, seeded, configuration.commands)
        finally:
            try:
                await self._sandbox.release_workspace(workspace_id)
            except Exception:
                logger.warning("rebase workspace %s not released", workspace_id, exc_info=True)
        changed = sorted(
            p
            for p in set(tree.files) | set(upstream.files)
            if tree.files.get(p) != upstream.files.get(p)
        )
        return SourceVerification(
            project_id=campaign.project_id,
            cycle_id=None,
            run_id=None,
            baseline_commit=onto.commit,
            development_configuration_revision=configuration.revision,
            candidate_revision_id=seeded.revision_id,
            candidate_tree_identity=FileTree.of(tree.files).identity,
            changed_paths=tuple(changed),
            environment=environment,
            checks=attributed(results, baseline),
            rebase={
                "campaign_id": campaign.campaign_id,
                "base_before": base.commit,
                "head_before": before.commit,
                "commit": rebased.commit,
                "replayed": [list(pair) for pair in rebased.replayed],
                "dropped": list(rebased.dropped),
            },
        )

    async def _store(self, campaign: Campaign, verification: SourceVerification) -> str:
        """The verification, in the vault beside the Project, named for its campaign: the
        document ``head`` and the next increment's delivery read (§24bv point 3)."""
        # deferred (pair): squadops.cycles imports this package at load
        from squadops.cycles.models import ArtifactRef

        # deferred (pair): squadops.projects imports this package at load
        from squadops.projects.verification import (
            SOURCE_VERIFICATION_FILENAME,
            SOURCE_VERIFICATION_TYPE,
        )

        content = json.dumps(verification.to_document(), indent=1).encode()
        ref = ArtifactRef(
            artifact_id=f"art_{uuid4().hex[:12]}",
            project_id=campaign.project_id,
            artifact_type=SOURCE_VERIFICATION_TYPE,
            filename=SOURCE_VERIFICATION_FILENAME,
            content_hash=sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/json",
            created_at=datetime.now(UTC),
            metadata={
                "campaign_id": campaign.campaign_id,
                "branch_rebase": True,
                "commit": (verification.rebase or {}).get("commit"),
            },
        )
        await self._vault.store(ref, content)
        return ref.artifact_id


def _continued(intent: LaunchIntent) -> str | None:
    """The cycle a superseded repair or retry continued: the one its request names."""
    overrides = (intent.cycle_request.get("body") or {}).get("execution_overrides") or {}
    block = overrides.get("campaign_proposal") or {}
    named = block.get("continues") if isinstance(block, dict) else None
    return str(named) if named else None
