"""The plan-review tier's verdict (SIP-0109 §24bj, #1708).

Bug classes guarded: the tier approving a plan one condition should have escalated (it approves
only when all hold, and it may only approve); a calibration escalated for the builder's notes at
the root, which would park every calibration; a footprint read wrongly, so scope reads true of
nothing; and a verdict whose notes do not say what each condition read.
"""

from __future__ import annotations

import pytest

from squadops.campaigns.models import CycleKind
from squadops.campaigns.plan_review_tier import (
    TierCondition,
    plan_footprint,
    plan_review_tier,
)
from tests.fixtures.merge_decisions import BLOCKING, UNREAD, WARNING, merge_decisions_yaml

SCOPE = ("backend/**", "frontend/**")
#: The calibration footprint this line's plans named (`cyc_17cd76a351a0`): the builder's notes sit
#: at the root, outside the objective's scope.
CALIBRATION_FOOTPRINT = ("backend/routes.py", "frontend/src/App.jsx", "assembly_notes.md")


def _verdict(**overrides):
    values = dict(
        kind=CycleKind.INCREMENT,
        open_questions=(),
        footprint=("backend/routes.py", "backend/tests/test_runs.py"),
        allowed_scope=SCOPE,
        stack="fullstack_fastapi_react",
        refused_framing_runs=(),
        answered_on_record={},
        merge_decisions=merge_decisions_yaml(),
    )
    values.update(overrides)
    return plan_review_tier(**values)


def test_a_plan_every_condition_holds_for_is_approved_with_each_reading_in_its_notes():
    verdict = _verdict()

    assert verdict.approves
    assert verdict.failed == ()
    notes = verdict.notes()
    assert "Plan validation passed" in notes
    assert "no_open_question: held: the design asks nothing" in notes
    assert (
        "inside_scope: held: the 1 product file inside (backend/**, frontend/**); 1 in the qa test "
        "namespace, the framework's: backend/tests/test_runs.py"
    ) in notes
    assert "framed_once: held: the framing ran once" in notes


@pytest.mark.parametrize(
    ("overrides", "failed", "reading"),
    [
        (
            {"open_questions": ("which order does the runs list use?",)},
            TierCondition.NO_OPEN_QUESTION,
            "1 open: which order does the runs list use?",
        ),
        (
            {"open_questions": None},
            TierCondition.NO_OPEN_QUESTION,
            "the cycle has no interface manifest",
        ),
        (
            {"footprint": ("backend/routes.py", "docker-compose.yml")},
            TierCondition.INSIDE_SCOPE,
            "outside (backend/**, frontend/**): docker-compose.yml",
        ),
        ({"footprint": ()}, TierCondition.INSIDE_SCOPE, "the plan names no file"),
        (
            {"refused_framing_runs": ("run_first",)},
            TierCondition.FRAMED_ONCE,
            "plan validation refused and re-rolled run_first",
        ),
    ],
    ids=["an open question", "no manifest", "outside scope", "no footprint", "a re-roll"],
)
def test_any_one_condition_missing_escalates_and_names_what_it_read(overrides, failed, reading):
    verdict = _verdict(**overrides)

    assert not verdict.approves
    assert [c.condition for c in verdict.failed] == [failed]
    assert reading in verdict.failed[0].reading
    assert f"{failed}: FAILED: " in verdict.notes()


@pytest.mark.parametrize(
    ("kind", "approves"),
    [
        (CycleKind.CALIBRATION, True),
        (CycleKind.INCREMENT, False),
        (CycleKind.REPAIR, False),
        (CycleKind.RETRY, False),
    ],
)
def test_only_a_calibration_is_exempt_from_the_scope(kind, approves):
    """The owner's ruling of 2026-10-08: a calibration builds the baseline the scope is read
    against. Bug caught either way: every calibration parked for its builder notes, or an
    increment, repair or retry let out of the scope it evolves inside."""
    verdict = _verdict(kind=kind, footprint=CALIBRATION_FOOTPRINT)

    assert verdict.approves is approves


def test_the_footprint_is_every_tasks_expected_artifacts_once_in_first_seen_order():
    plan = """\
version: 1
project_id: group_run
cycle_id: cyc_x
prd_hash: h
tasks:
  - task_index: 0
    task_type: development.develop
    role: dev
    focus: routes
    description: d
    expected_artifacts: [backend/routes.py, backend/errors.py]
    acceptance_criteria: [a]
  - task_index: 1
    task_type: qa.test
    role: qa
    focus: tests
    description: d
    expected_artifacts: [backend/tests/test_t5.py, backend/routes.py]
    acceptance_criteria: [a]
    depends_on: [0]
summary:
  total_dev_tasks: 1
  total_qa_tasks: 1
  total_tasks: 2
  estimated_layers: [backend]
"""
    assert plan_footprint(plan) == (
        "backend/routes.py",
        "backend/errors.py",
        "backend/tests/test_t5.py",
    )


@pytest.mark.parametrize("plan", [None, "", "::: not yaml :::", "version: 1\ntasks: []\n"])
def test_an_absent_or_unreadable_plan_has_no_footprint_so_it_escalates(plan):
    assert plan_footprint(plan) == ()
    assert not _verdict(footprint=plan_footprint(plan)).approves


@pytest.mark.parametrize(
    ("stack", "held", "reading"),
    [
        (
            "fullstack_fastapi_react",
            True,
            "the 1 product file inside (backend/routes.py); 1 in the qa test namespace, the "
            "framework's: backend/tests/criteria/test_c1.py",
        ),
        ("", False, "outside (backend/routes.py): backend/tests/criteria/test_c1.py"),
    ],
)
def test_a_criterion_test_is_read_against_the_scope_only_where_no_stack_names_its_namespace(
    stack, held, reading
):
    """#2743: the stack's qa test namespace is the framework's, so a plan's criterion test never
    reads against the owner's scope. With no manifest to name the stack there is no namespace,
    and the path stays the scope's. Bug caught: the tier refusing the framework's own test path
    under a narrow scope; or, the mirror, a namespace assumed where none can be named, which
    would wave an unknown tree's paths past the scope."""
    footprint = ("backend/routes.py", "backend/tests/criteria/test_c1.py")
    verdict = _verdict(footprint=footprint, allowed_scope=("backend/routes.py",), stack=stack)

    [scope] = [c for c in verdict.checks if c.condition is TierCondition.INSIDE_SCOPE]
    assert scope.held is held
    assert scope.reading == reading


def test_a_product_file_outside_the_scope_still_fails_beside_the_frameworks_tests():
    """#2743's exemption covers the qa namespace only. Bug caught: a test path in the footprint
    carrying the product file beside it past the scope."""
    verdict = _verdict(
        footprint=("backend/models.py", "backend/tests/test_runs.py"),
        allowed_scope=("backend/routes.py",),
    )

    [scope] = [c for c in verdict.checks if c.condition is TierCondition.INSIDE_SCOPE]
    assert scope.held is False
    assert scope.reading.startswith("outside (backend/routes.py): backend/models.py;")


@pytest.mark.parametrize(
    ("footprint", "held"),
    [
        (("tally/report.py", "checks/check_criterion_R1.py"), True),
        (("tally/report.py", "checks/check_criterion_R1.py", "checks/check_report.py"), False),
    ],
    ids=["the placed criterion file", "the product's own test beside it"],
)
def test_on_a_product_only_the_criterion_files_the_framework_placed_are_the_frameworks(
    footprint, held
):
    """SIP-0109 §24cj, the tier's half of the one reading (§24ch): a repository-backed Project has
    no stack, so no namespace. Bugs caught: the framework's placed criterion file read against the
    scope, so a scope of the product's source refuses every plan; or the product's own test,
    which the scope governs, waved through beside it."""
    verdict = _verdict(
        footprint=footprint,
        allowed_scope=("tally/**",),
        stack="",
        placed=("checks/check_criterion_R1.py",),
    )

    [scope] = [c for c in verdict.checks if c.condition is TierCondition.INSIDE_SCOPE]
    assert scope.held is held
    assert ("checks/check_report.py" in scope.reading) is (not held)


@pytest.mark.parametrize(
    ("design_is_the_change_request", "footprint", "failed"),
    [
        # #2796: a product increment's design is its ruled change request; the plan in scope holds.
        (True, ("tally/report.py", "checks/check_criterion_R1.py"), ()),
        # The plan straying from the request is still the tier's to escalate, on scope alone.
        (True, ("tally/report.py", "ops/deploy.sh"), (TierCondition.INSIDE_SCOPE,)),
        # A cycle with no manifest and no ruled change request still establishes nothing.
        (False, ("tally/report.py",), (TierCondition.NO_OPEN_QUESTION,)),
    ],
    ids=["product-in-scope", "product-out-of-scope", "no-manifest-no-request"],
)
def test_a_product_increments_design_is_its_ruled_change_request(
    design_is_the_change_request, footprint, failed
):
    """#2796. Bug caught: every plan gate of a repository-backed product's increment escalated on
    no_open_question, since a product has no manifest (the 2.6 spike: 3 of 3), so an unattended
    product Campaign needed a person at each one; or the fix waving an out-of-scope plan through."""
    verdict = _verdict(
        open_questions=None,
        footprint=footprint,
        allowed_scope=("tally/**",),
        stack="",
        placed=("checks/check_criterion_R1.py",),
        design_is_the_change_request=design_is_the_change_request,
    )

    assert tuple(c.condition for c in verdict.failed) == failed
    assert verdict.approves is (failed == ())


# --- §24ee (#3164): a conflict the merge escalated is the operator's, not the tier's -------------


@pytest.mark.parametrize(
    ("merge_decisions", "reads"),
    [
        (
            merge_decisions_yaml(BLOCKING),
            "1 escalated to the operator: must_cover_requirements: Blocking conflict raised by "
            "development on must_cover_requirements: The PRD requires a waitlist and the brief "
            "omits it.",
        ),
        (
            merge_decisions_yaml(UNREAD),
            "1 escalated to the operator: unread: brief_conflicts[0]: development raised a brief "
            "conflict that couldn't be read",
        ),
        (
            None,
            "the framing wrote no merge decisions, so the tier can establish nothing about a "
            "conflict a proposer raised with the brief",
        ),
        ("", "the framing wrote no merge decisions"),
        ("version: 1\n", "the merge decisions can't be read: merge_decisions missing required"),
        ("::: not yaml :::", "the merge decisions can't be read: "),
    ],
    ids=[
        "a blocking conflict",
        "an unread conflict",
        "none written",
        "empty",
        "partial",
        "not yaml",
    ],
)
def test_a_plan_whose_merge_escalated_a_conflict_or_left_no_record_is_not_the_tiers(
    merge_decisions, reads
):
    """Bugs caught (#3164): a proposer's blocking disagreement with the brief escalated to an
    operator by the merge and approved by the tier with no operator having seen it; an unread
    conflict (#3163) treated as settled; and merge decisions that are absent or unreadable read
    as "no conflict", which approves on nothing."""
    verdict = _verdict(merge_decisions=merge_decisions)

    assert not verdict.approves
    [failed] = verdict.failed
    assert failed.condition is TierCondition.NO_ESCALATED_CONFLICT
    assert failed.reading.startswith(reads)
    assert f"no_escalated_conflict: FAILED: {reads}" in verdict.notes()


def test_an_unread_conflict_reaches_the_gates_ruler_in_the_proposers_own_words():
    """Bug caught: the escalation naming a conflict and dropping what the proposer wrote, so
    whoever rules the gate has to find the stored proposal to learn what was raised."""
    [failed] = _verdict(merge_decisions=merge_decisions_yaml(UNREAD)).failed

    assert "missing required field: brief_field" in failed.reading
    assert "requirement: M5" in failed.reading
    assert "outside the paths a task may write" in failed.reading


@pytest.mark.parametrize(
    ("raised", "reads"),
    [
        ("", "the merge escalated no brief conflict"),
        (WARNING, "the merge escalated no brief conflict (1 raised and settled by the merge)"),
    ],
    ids=["none raised", "a warning the merge accepted"],
)
def test_a_conflict_the_merge_settled_leaves_the_tier_free_to_approve(raised, reads):
    """The edge the condition must leave alone. Bug caught: every raised conflict escalating,
    warnings included, so one cautious proposer parks every increment."""
    verdict = _verdict(merge_decisions=merge_decisions_yaml(raised))

    assert verdict.approves
    assert [c.condition for c in verdict.checks] == [
        TierCondition.NO_OPEN_QUESTION,
        TierCondition.INSIDE_SCOPE,
        TierCondition.FRAMED_ONCE,
        TierCondition.NO_ESCALATED_CONFLICT,
    ]
    assert f"no_escalated_conflict: held: {reads}" in verdict.notes()
