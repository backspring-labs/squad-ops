"""A framing's ``merge_decisions.yaml``, as the plan merger writes it.

Built by the merger itself (``merge_proposals``, ``emit_merge_decisions_yaml``) from the merge
tests' brief and development proposal, so a test that reads merge decisions reads what a live
framing stores.
"""

from __future__ import annotations

from squadops.capabilities.handlers._plan_merger import emit_merge_decisions_yaml, merge_proposals
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks
from tests.unit.capabilities.test_merge_plan_handler import _BRIEF_YAML, _DEV_PROPOSAL_YAML

#: A disagreement that parses, at the severity the merger escalates.
BLOCKING = """
brief_conflicts:
  - brief_field: must_cover_requirements
    proposed_change: Add the waitlist the PRD asks for.
    reason: The PRD requires a waitlist and the brief omits it.
    severity: blocking
"""

#: One the merger settles itself.
WARNING = """
brief_conflicts:
  - brief_field: accepted_stack
    proposed_change: Keep runs in memory.
    reason: The PRD asks for no persistence.
    severity: warning
"""

#: One in field names of the proposer's own, as #3163's cycle raised it.
UNREAD = """
brief_conflicts:
  - requirement: "M5"
    issue: The brief asks a task to emit a file outside the paths a task may write.
"""


def merge_decisions_yaml(raised: str = "") -> str:
    """The merge decisions of a plan whose development proposal carried ``raised``: a
    ``brief_conflicts`` block, or nothing."""
    _plan, decisions = merge_proposals(
        brief=PlanAuthoringBrief.from_yaml(_BRIEF_YAML),
        dev_proposal=ProposedRoleTasks.from_yaml(_DEV_PROPOSAL_YAML.rstrip("\n") + raised),
        qa_proposal=None,
        strategy_guidance=None,
        project_id="p",
        cycle_id="c",
        prd_hash="h",
        configured_contributors=["development"],
        missing_proposals=[],
        criterion_files=(),
    )
    return emit_merge_decisions_yaml(decisions)
