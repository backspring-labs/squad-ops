"""What a Campaign on a repository-backed Project must declare at its creation (SIP-0109 §24bv
point 5, the 2.5 plan's D10 point 3; SIP-0112 H.11).

A repository-backed Project (SIP-0112 E.4.1) is developed from its own tree, so:
- **its objective names its requirements source** (``objective.requirements``), **or its goal set**
  (``objective.goals``, SIP-0115 §5.1), never both and never neither. Such a Project has no PRD of
  its own, and its calibration record carries none, so the proposal has nothing else to read the
  product's requirements from. A goal set is the Project's own (Q44), so ``goals.goal_set`` names
  this Project; the Project has one written, and a pinned revision is one it holds;
- **its increments seed no skeleton.** The cycles it launches resolve through its proposal profile
  and its policy's stack (§24bs), and a stack's skeleton laid beside the product's files describes
  a different application. ``seeds_skeleton`` is the one rule (H.11), E.4.3's guard's.

A sample application's objective names neither: its PRD is its campaign's, and a source or a goal
set given there would be read by nothing. Each refusal names its field and comes at creation
(422), before anything is written, never at the first launch.
"""

from __future__ import annotations

from squadops.campaigns.models import Campaign
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.preflight import seeds_skeleton


def creation_refusal(
    campaign: Campaign, *, repository_backed: bool, latest_goal_set_revision: int | None
) -> str | None:
    """Why ``campaign`` can't be created on its Project, naming the field, or ``None``.

    ``latest_goal_set_revision`` is the Project's latest goal-set revision, ``None`` when it has
    none written (read only when the objective names goals)."""
    objective = campaign.objective
    requirements, goals = objective.requirements, objective.goals
    if not repository_backed:
        named = "requirements" if requirements is not None else "goals" if goals else None
        if named is not None:
            return (
                f"objective.{named} names a requirements source, which only a "
                "repository-backed Project's Campaign reads (SIP-0109 §24bv point 5, SIP-0115 "
                "§5.1): this Project is a sample application, whose requirements are its PRD"
            )
        return None
    if requirements is None and goals is None:
        return (
            "objective.requirements or objective.goals is required for a Campaign on a "
            "repository-backed Project: repo:file:<path>@current, a file in the product read at "
            "each increment's head, or a stored artifact's id (SIP-0109 §24bv point 5); or the "
            "Project's goal set, {goal_set: <project id>, revision: <n> | current} (SIP-0115 §5.1)"
        )
    if goals is not None:
        refusal = _goals_refusal(campaign, latest_goal_set_revision)
        if refusal:
            return refusal
    policy = campaign.policy
    # The increment's launch resolves as ``launch_requests.increment_launch`` builds it: the
    # proposal profile's defaults, under the policy's stack when one is declared (§24bs).
    resolved = dict(load_profile(policy.proposal_profile).defaults)
    if policy.stack:
        resolved.update(build_profile=policy.stack, development_profile=policy.stack)
    if seeds_skeleton(resolved):
        field = "policy.stack" if policy.stack else "policy.proposal_profile"
        return (
            f"{field}: the Campaign's increments would seed a stack's skeleton beside the "
            "product's own files, and a repository-backed Project is developed from its own tree "
            "(SIP-0112 H.4 point 3, H.11). Leave policy.stack unset and name a profile that seeds "
            "nothing, such as campaign-increment-source"
        )
    return None


def _goals_refusal(campaign: Campaign, latest: int | None) -> str | None:
    """Why the goal set ``campaign`` names can't be read, or ``None`` (SIP-0115 §5.1, §5.5)."""
    goals = campaign.objective.goals
    assert goals is not None
    if goals.goal_set != campaign.project_id:
        return (
            f"objective.goals.goal_set {goals.goal_set!r} is not this Campaign's Project "
            f"({campaign.project_id}): a Project has one goal set (SIP-0115 Q44), and a Campaign "
            "works through its own Project's"
        )
    if latest is None:
        return (
            f"objective.goals: Project {campaign.project_id} has no goal set written. Write its "
            "first revision (squadops goals edit) before creating a Campaign on it"
        )
    pinned = goals.pinned
    if pinned is not None and pinned > latest:
        return (
            f"objective.goals.revision {pinned}: Project {campaign.project_id}'s goal set has "
            f"revisions 1 to {latest}"
        )
    return None
