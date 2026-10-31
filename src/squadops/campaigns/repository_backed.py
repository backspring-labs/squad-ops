"""What a Campaign on a repository-backed Project must declare at its creation (SIP-0109 §24bv
point 5, the 2.5 plan's D10 point 3; SIP-0112 H.11).

A repository-backed Project (SIP-0112 E.4.1) is developed from its own tree, so:
- **its objective names its requirements source** (``objective.requirements``). Such a Project has
  no PRD of its own, and its calibration record carries none, so the proposal has nothing else to
  read the product's requirements from;
- **its increments seed no skeleton.** The cycles it launches resolve through its proposal profile
  and its policy's stack (§24bs), and a stack's skeleton laid beside the product's files describes
  a different application. ``seeds_skeleton`` is the one rule (H.11), E.4.3's guard's.

A sample application's objective names no requirements source: its PRD is its campaign's, and a
source given there would be read by nothing. Each refusal names its field and comes at creation
(422), before anything is written, never at the first launch.
"""

from __future__ import annotations

from squadops.campaigns.models import Campaign
from squadops.contracts.cycle_request_profiles import load_profile
from squadops.cycles.preflight import seeds_skeleton


def creation_refusal(campaign: Campaign, *, repository_backed: bool) -> str | None:
    """Why ``campaign`` can't be created on its Project, naming the field, or ``None``."""
    requirements = campaign.objective.requirements
    if not repository_backed:
        if requirements is not None:
            return (
                "objective.requirements names a requirements source, which only a "
                "repository-backed Project's Campaign reads (SIP-0109 §24bv point 5): this "
                "Project is a sample application, whose requirements are its PRD"
            )
        return None
    if requirements is None:
        return (
            "objective.requirements is required for a Campaign on a repository-backed Project: "
            "repo:file:<path>@current, a file in the product read at each increment's head, or a "
            "stored artifact's id (SIP-0109 §24bv point 5)"
        )
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
