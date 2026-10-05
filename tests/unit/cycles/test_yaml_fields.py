"""#1990: one rule for an optional list of strings, read through each parser that uses it.

What bugs would these catch? A shared parser whose refusal no longer names the document and the
field, so an operator reading "must be a YAML list" cannot tell which one; and the advisory parser
refusing a whole proposal over one malformed optional section, which #187 made a drop.
"""

from __future__ import annotations

import pytest

from squadops.cycles.merge_decisions import MergeDecisions
from squadops.cycles.plan_guidance import PlanGuidance
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks
from squadops.cycles.yaml_fields import str_list

_MERGE = """\
version: 1
target_plan_id: plan-cyc-test
brief_id: brief-test-001
guidance_ids: []
authoring_mode: sole_author
sole_author_reason: no_contributors_configured
proposal_completeness: sole_author
missing_proposals: []
canonical_tasks:
  - task_index: 0
    source_proposal_task_keys: []
    proposed_by: []
    merge_action: gap_filled
    reason: "Sole-author fallback via PlanAuthoringService."
brief_conflicts_disposition: []
operator_notes: ""
"""
_GUIDANCE = "version: 1\nguidance_id: g-1\nsource_brief_id: b-1\nproposing_role: strategy\n"
_PROPOSAL = """\
version: 1
proposing_role: dev
proposal_id: prop-dev-001
source_brief_id: brief-test-001
scope_statement: |
  Dev contributions for the user CRUD feature.
tasks: []
"""


@pytest.mark.parametrize(
    ("parse", "doc", "message"),
    [
        (
            MergeDecisions.from_yaml,
            _MERGE + "proposal_ids: just-one\n",
            "merge_decisions proposal_ids must be a YAML list",
        ),
        (
            PlanGuidance.from_yaml,
            _GUIDANCE + "must_not_skip: 5\n",
            "plan_guidance must_not_skip must be a YAML list",
        ),
    ],
    ids=["merge-decisions", "plan-guidance"],
)
def test_a_strict_document_refuses_a_field_that_is_not_a_list_naming_it(parse, doc, message):
    with pytest.raises(ValueError, match=message):
        parse(doc)


def test_an_advisory_section_that_is_not_a_list_is_dropped_and_named():
    proposal = ProposedRoleTasks.from_yaml(
        _PROPOSAL + "risks: not a list\nassumptions:\n  - '  kept  '\n  - ''\n"
    )

    assert proposal.risks == []
    assert proposal.degraded_sections == ["risks"]
    assert proposal.assumptions == ["kept"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, []), ("", []), ([" a ", "", "  ", 3], ["a", "3"])],
    ids=["absent", "empty", "list"],
)
def test_a_list_is_read_as_stripped_non_empty_strings(raw, expected):
    assert str_list(raw, "f") == expected
