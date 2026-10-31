"""The cycles a campaign launches, as launch requests (SIP-0109 §12b).

A launch intent carries the whole cycle-create request, built here from the campaign's policy
when the deciding row is written, so a launch re-drained after a restart creates the cycle the
decision named, not one rebuilt from whatever the profiles say by then.

One thing is bound at drain instead: a repository-backed increment's tree, the campaign branch's
head, which can move after the decision (SIP-0109 §24cd point 1, ``bound_at_head``).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from squadops.campaigns.calibration_record import BINDING_KEY, CalibrationRecord
from squadops.campaigns.change_request import IncrementBasis
from squadops.campaigns.models import (
    Campaign,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    CycleKind,
    LaunchRequest,
)
from squadops.contracts.cycle_request_profiles import cycle_request_body, load_profile

if TYPE_CHECKING:
    from squadops.campaigns.campaign_branch import CampaignHead


def _stack_values(campaign: Campaign) -> dict:
    """The campaign's stack, as every launch carries it (§24bs, #2443): both of a cycle's stack
    keys, which #832 holds in agreement, or nothing when the profiles' own stack stands."""
    stack = campaign.policy.stack
    return {"build_profile": stack, "development_profile": stack} if stack else {}


def calibration_launch(campaign: Campaign) -> LaunchRequest:
    """The calibration cycle (§11): the policy's calibration profile, run by its squad, on the
    campaign's project. Its accepted tree becomes the first baseline."""
    policy = campaign.policy
    return LaunchRequest(
        CycleKind.CALIBRATION,
        {
            "body": cycle_request_body(
                policy.calibration_profile,
                squad_profile_id=policy.squad_profile,
                user_values=_stack_values(campaign),
                notes=f"campaign {campaign.campaign_id}: calibration (SIP-0109 §11)",
            )
        },
    )


def start_transition(
    campaign: Campaign,
    *,
    actor: str,
    actor_role: str,
    reason: str,
    idempotency_key: str,
    record: CalibrationRecord | None = None,
) -> CampaignTransition:
    """The owner's start: a draft campaign moves to calibrating. Acted on the draft only.

    - A sample application's: its calibration cycle's launch intent is written in the same
      transaction (§12b).
    - A repository-backed Project's (§24bv point 1): ``record`` is its calibration record, written
      in this row's binding, and nothing is launched. Its promotion and decision follow
      (``CampaignProgress.calibration_recorded``)."""
    return CampaignTransition(
        operation=ControlOperation.START,
        actor=actor,
        actor_role=actor_role,
        reason=reason,
        idempotency_key=idempotency_key,
        next_state=CampaignState.CALIBRATING,
        expected_state=CampaignState.DRAFT,
        binding={BINDING_KEY: record.to_binding()} if record is not None else {},
        launch=calibration_launch(campaign) if record is None else None,
    )


def increment_launch(
    campaign: Campaign,
    baseline_manifest: str | None,
    frozen: tuple[dict, ...] = (),
    abandoned: dict | None = None,
    qa_proposed: list[dict] | None = None,
    unapproved: list[dict] | None = None,
) -> LaunchRequest:
    """An increment cycle (§7.3): the policy's proposal profile, run by its squad, proposing
    against the accepted tree. The ``campaign_proposal`` block carries what the proposal run
    reads — the accepted tree's identity and its manifest's text (the agent has no vault, #1821),
    the objective — and the campaign's revision budget, which the increment gate spends (§9.5).

    ``frozen`` is every criterion earlier increments froze (§8.1), each with its own test file and
    its verifier bundle's artifact: pinned at launch, so the proposal knows the ids it may not
    reuse and the evaluation runs exactly these bundles, whatever is promoted meanwhile.

    ``abandoned`` is the brief of the increment this one replaces (row 13), when there is one.

    ``qa_proposed`` is what the qa authors proposed instead of testing (#1884), when anything.

    ``unapproved`` is each proposal the campaign ruled on and never approved, by its last ruling
    (#2593), when there is any.

    **A repository-backed increment's intent binds no tree** (§24cd point 1). Its accepted tree is
    the campaign branch's head, which a rebase can move between this decision and the drain
    (§24bv point 4), so the launcher binds the head it reads at drain (``bound_at_head``). A
    sample application's tree is the vault's, never moves but by promotion, and is bound here.

    **A repository-backed increment** (§24bv point 5) proposes on the campaign branch, whose
    accepted tree is a commit, not a vault tree with a manifest. Its block names that basis
    (``basis: campaign_branch``), the one marker every increment seam reads, and carries no
    manifest and no accepted cycle: what its proposal reads of the product is composed at its run,
    at the head its cycle pins (``execution.product_proposal``). Its objective carries its
    requirements source.

    Raises ``ValueError`` for a sample application's campaign whose accepted tree is no cycle's,
    or one given no manifest: every seam downstream reads ``accepted_cycle_id`` as the cycle the
    increment builds on, and its manifest as the tree it changes, so neither is written empty.
    And for a manifest given to a campaign branch's, which has none to change."""
    policy = campaign.policy
    accepted = campaign.accepted
    on_branch = accepted is not None and accepted.commit is not None
    if accepted is None or (not on_branch and accepted.cycle_id is None):
        raise ValueError(
            f"campaign {campaign.campaign_id}'s accepted tree names no cycle to propose on: "
            + (
                f"it is calibration record {accepted.calibration_record_id}'s"
                if accepted is not None
                else "it has none"
            )
        )
    if on_branch == (baseline_manifest is not None):
        raise ValueError(
            f"campaign {campaign.campaign_id}'s increment is proposed on "
            + (
                "its campaign branch, which has no interface manifest to be given"
                if on_branch
                else "its accepted cycle's tree, and is given no manifest of it"
            )
        )
    tree: dict = (
        # §24cd point 1: bound at drain (``bound_at_head``). §24bv point 5: no manifest.
        {"basis": str(IncrementBasis.CAMPAIGN_BRANCH)}
        if on_branch
        else {
            "baseline_tree": accepted.identity,
            # The cycle whose delivered files the increment builds on (§7.1).
            "accepted_cycle_id": accepted.cycle_id,
            "baseline_manifest": baseline_manifest,
        }
    )
    requirements = campaign.objective.requirements
    return LaunchRequest(
        CycleKind.INCREMENT,
        {
            "body": cycle_request_body(
                policy.proposal_profile,
                squad_profile_id=policy.squad_profile,
                user_values={
                    **_stack_values(campaign),
                    "campaign_proposal": {
                        "proposal_id": f"prop_{uuid.uuid4().hex[:12]}",
                        "version": 1,
                        **tree,
                        "objective": {
                            "statement": campaign.objective.statement,
                            "allowed_scope": list(campaign.objective.allowed_scope),
                            "measurement": campaign.objective.measurement,
                            **({"requirements": requirements} if requirements else {}),
                        },
                        "prior_criteria": [f["criterion_id"] for f in frozen],
                        "frozen_criteria": [dict(f) for f in frozen],
                        "max_revisions": policy.max_proposal_revisions,
                        # Row 13 (#1692): why the increment this one replaces was abandoned. Its
                        # own key, read by the proposal alone — never ``prior_cycle``, which tells
                        # every author the increment was attempted before.
                        **({"abandoned_increment": dict(abandoned)} if abandoned else {}),
                        # #1884: behaviour a qa author judged desirable that nothing accepted
                        # required, returned as a proposal rather than a test.
                        **({"qa_proposed_behaviours": list(qa_proposed)} if qa_proposed else {}),
                        # #2593: each proposal the campaign never approved, with the ruling's
                        # reason. A revision is shown its note; a rejection's fresh successor was
                        # shown nothing, and proposed the rejected change again.
                        **({"unapproved_proposals": list(unapproved)} if unapproved else {}),
                    },
                },
                notes=f"campaign {campaign.campaign_id}: increment (SIP-0109 §7.3)",
            )
        },
    )


#: What a repair or a retry carries of the increment it continues (§10a): the binding, and what
#: every increment seam reads of it, as ``increment_launch`` wrote them. A continuation's block is
#: built from this list and its own lineage (``continues``, ``repair_of``, ``prior_cycle``), never by
#: copying the failed cycle's block and deleting from it: #2558 and #2576 were lineage keys of one
#: cycle carried into the next that way, and a key added later would have leaked by default (#2578).
#: What only a proposal reads (``abandoned_increment``, ``qa_proposed_behaviours``,
#: ``unapproved_proposals``, a revision's note) stays with the proposal: a continuation runs none.
CONTINUED_KEYS = (
    "proposal_id",
    "version",
    "baseline_tree",
    # §24bv point 5: a repository-backed increment's continuation is one too.
    "basis",
    "accepted_cycle_id",
    "baseline_manifest",
    "objective",
    "prior_criteria",
    "frozen_criteria",
    "max_revisions",
)


def increment_id_of(kind: CycleKind, cycle_request: dict) -> str | None:
    """#2578 part 2: the increment a launch's cycle belongs to, its proposal's id, read from the
    launch's own ``campaign_proposal`` block: ``increment_launch`` wrote it, and ``CONTINUED_KEYS``
    carries it into a repair's or retry's. Never from the predecessor's row, which is the
    copy-then-delete class part 1 closed. ``None`` for a calibration, which belongs to no increment.

    Raises ``ValueError`` for an increment, repair or retry whose block names no proposal: its
    cycle would read as belonging to none, and is refused rather than defaulted."""
    if kind is CycleKind.CALIBRATION:
        return None
    body = cycle_request.get("body") or {}
    block = (body.get("execution_overrides") or {}).get("campaign_proposal") or {}
    proposal_id = block.get("proposal_id") if isinstance(block, dict) else None
    if not (isinstance(proposal_id, str) and proposal_id.strip()):
        raise ValueError(f"a {kind} launch's campaign_proposal block names no proposal_id")
    return proposal_id


def bound_at_head(kind: CycleKind, cycle_request: dict, head: CampaignHead | None) -> dict:
    """§24cd point 1: the cycle request a repository-backed launch is built from, bound at the
    campaign branch's head the launcher read at drain. ``head`` is ``None`` for a sample
    application (its tree names no commit), and its request is returned as it was written.

    - **An increment** binds no tree in its intent (``increment_launch``), so the head's tree
      is bound here: its proposal is given, and its ruling binds to, the tree it is built on.
    - **A repair or a retry** continues a candidate built on the tree its block names
      (``CONTINUED_KEYS``), so that tree must still be the head. One the head has moved past
      was built on another tree, and nothing it built can follow the head (§24bv point 2).
    - **A calibration** carries no block, and is returned as it was written.

    Raises ``ValueError`` for an increment whose intent names a tree other than the head, or a
    continuation whose tree is not the head or that names none: refused, never re-bound."""
    if head is None:
        return cycle_request
    body = cycle_request.get("body") or {}
    overrides = body.get("execution_overrides") or {}
    block = overrides.get("campaign_proposal")
    if not isinstance(block, dict):
        return cycle_request
    named = block.get("baseline_tree")
    if named is None and kind is CycleKind.INCREMENT:
        block = {**block, "baseline_tree": head.tree_identity}
    elif named != head.tree_identity:
        raise ValueError(
            f"the {kind} is bound to tree {str(named)[:12]}, and the campaign branch's head is "
            f"{head.commit[:12]}, tree {head.tree_identity[:12]}: a launch is built on the head "
            "(SIP-0109 §24cd point 1)"
        )
    return {
        **cycle_request,
        "body": {**body, "execution_overrides": {**overrides, "campaign_proposal": block}},
    }


#: The workloads each bound cycle runs (§10a): a retry frames afresh and builds; a repair builds
#: only, under the failed cycle's approved plan.
BOUND_WORKLOADS = {
    CycleKind.RETRY: ("framing", "implementation"),
    CycleKind.REPAIR: ("implementation",),
}


def bound_launch(
    campaign: Campaign,
    kind: CycleKind,
    block: dict,
    plan_artifact_refs: list[str],
    contract_ref: str | None,
) -> LaunchRequest:
    """A cycle that reuses an increment's bound change request, ruling, baseline and footprint
    (§10a): the policy's proposal profile — so the stack is the campaign's — keeping only the
    kind's workloads (``BOUND_WORKLOADS``): no proposal is run and no ruling is asked, and a
    repair runs the build alone. It carries the increment's
    ``campaign_proposal`` block and the approved seeds, so every increment seam reads it as the
    increment it continues."""

    policy = campaign.policy
    keep = BOUND_WORKLOADS[kind]
    sequence = [
        dict(w)
        for w in load_profile(policy.proposal_profile).defaults["workload_sequence"]
        if w.get("type") in keep
    ]
    if [w["type"] for w in sequence] != list(keep):
        raise ValueError(
            f"profile {policy.proposal_profile!r} cannot run a {kind}: it does not hold the "
            f"workloads {list(keep)}"
        )
    user_values: dict = {
        **_stack_values(campaign),
        "campaign_proposal": dict(block),
        "plan_artifact_refs": list(plan_artifact_refs),
        "workload_sequence": sequence,
    }
    if contract_ref:
        user_values["contract_ref"] = contract_ref
    return LaunchRequest(
        kind,
        {
            "body": cycle_request_body(
                policy.proposal_profile,
                squad_profile_id=policy.squad_profile,
                user_values=user_values,
                notes=f"campaign {campaign.campaign_id}: {kind} of {block.get('proposal_id')} "
                "(SIP-0109 §10a)",
            )
        },
    )
