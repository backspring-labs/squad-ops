"""Contract 5, the reference's side (SIP-0112 §8.2.1; SIP-0113 §4.8; #2415): Outcome Evaluation's
record yields the reference the shared fixture records, and the reader refuses what it must.

The fixture's README assigns this side to #2415. The history side (write it into Project history,
read it back) lands with the slice that first writes Project history.
"""

from __future__ import annotations

import ast
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadops.scenarios import reference
from squadops.scenarios.evaluation import EvaluationRecord
from squadops.scenarios.reference import EvaluationInvalid, UnknownSchemaMajor, parse_reference
from tests.fixtures.shared_contract.repository import recorded


def test_a_record_yields_exactly_the_reference_the_fixture_records():
    """Bug caught: a field renamed, dropped or added on the way to the reference, so Project
    history stores something other than the shape both lanes froze."""
    valid = recorded("outcome_evaluation_ref", "valid")
    record = EvaluationRecord(
        evaluation_id=valid["evaluation_id"],
        project_id=valid["project_id"],
        campaign_id=valid["campaign_id"],
        cycle_id=valid["cycle_id"],
        evaluated_tree_identity=valid["evaluated_tree_identity"],
        previous_accepted_tree_identity=valid["previous_accepted_tree_identity"],
        suite_digest=valid["suite_digest"],
        outcomes=(),
        evaluated_at=datetime(2026, 10, 18, tzinfo=UTC),
    )

    assert record.reference().to_dict() == valid
    assert parse_reference(valid) == record.reference()


@pytest.mark.parametrize(
    ("form", "error", "message"),
    [
        ("missing_field", EvaluationInvalid, r"no \['campaign_id'\]"),
        ("unknown_major", UnknownSchemaMajor, "not a major version this reader knows"),
    ],
)
def test_the_reader_refuses_the_fixtures_bad_forms(form, error, message):
    """Bug caught: an absent campaign_id read as null (a campaign's evaluation filed as one
    outside a campaign), or a v2 reference read in part as v1."""
    with pytest.raises(error, match=message):
        parse_reference(recorded("outcome_evaluation_ref", form))


def test_a_stale_reference_reads_as_what_it_names():
    """The stale form is a valid reference to the first commit's tree. Mapping it to that commit,
    never the baseline, is the reader's (``test_outcome_evaluation_ref_recording.py``). Bug caught:
    a reader refusing a reference for naming an older tree, so history loses earlier evaluations."""
    stale = recorded("outcome_evaluation_ref", "stale_commit")

    assert parse_reference(stale).evaluated_tree_identity == stale["evaluated_tree_identity"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"evaluated_tree_identity": "15c7a12b8ed45f63ae47e90e3e854f6b3a2775f1"},
            "64 lowercase hex",
        ),
        ({"campaign_id": ""}, "campaign_id is text"),
        ({"campaign_id": 5}, "campaign_id is text"),
        ({"schema": "something-else/v1"}, "not an outcome evaluation reference"),
    ],
    ids=["a-commit-as-a-tree", "an-empty-campaign", "a-number-as-a-campaign", "another-schema"],
)
def test_a_reference_that_names_the_wrong_kind_of_thing_is_refused(change, message):
    """SIP-0112 §8.2.1: identifiers never substitute for one another. Bug caught: a Git commit
    stored where a tree identity belongs, a number coerced to a campaign ID (``5`` read as
    ``"5"``), or a document of another kind read as a reference."""
    with pytest.raises(EvaluationInvalid, match=message):
        parse_reference({**recorded("outcome_evaluation_ref", "valid"), **change})


def test_a_reference_outside_a_campaign_with_no_previous_tree_reads_its_nulls_as_nulls():
    """The reference scenario's and a replay's shape: no campaign, no accepted tree before it. Bug
    caught: a reader that takes a null for an absent field and refuses it, or one that drops the
    keys, so Project history stores a reference the next reader refuses."""
    doc = {
        **recorded("outcome_evaluation_ref", "valid"),
        "campaign_id": None,
        "previous_accepted_tree_identity": None,
    }

    ref = parse_reference(doc)

    assert (ref.campaign_id, ref.previous_accepted_tree_identity) == (None, None)
    assert ref.to_dict() == doc


def _calibration_reading(**change):
    """SIP-0113 §10l: a repository-backed Campaign's baseline reading, its calibration record's
    commit evaluated, as the shared fixture records it. It names the record in place of a cycle,
    and builds on nothing."""
    form = recorded("outcome_evaluation_ref", "calibration_record")
    fields = dict(
        evaluation_id=form["evaluation_id"],
        project_id=form["project_id"],
        campaign_id=form["campaign_id"],
        cycle_id=None,
        evaluated_tree_identity=form["evaluated_tree_identity"],
        previous_accepted_tree_identity=None,
        suite_digest=form["suite_digest"],
        outcomes=(),
        evaluated_at=datetime(2026, 10, 28, tzinfo=UTC),
        calibration_record_id=form["calibration_record_id"],
    )
    return EvaluationRecord(**{**fields, **change})


def test_a_calibration_records_reading_yields_exactly_the_form_the_fixture_records():
    """§10l, contract 5's additive field (SIP-0112 H.14). Bugs caught: the record's id dropped on
    the way to the reference, so Project history stores a reading that names no unit; a reader
    that refuses the null cycle_id such a reading carries; or the key written on every cycle's
    reference, so the shape both lanes froze changes under every reader."""
    form = recorded("outcome_evaluation_ref", "calibration_record")
    ref = _calibration_reading().reference()

    assert ref.to_dict() == form
    assert parse_reference(form) == ref
    valid = recorded("outcome_evaluation_ref", "valid")
    assert "calibration_record_id" not in valid
    assert parse_reference(valid).calibration_record_id is None


def test_a_calibration_reference_that_names_a_previous_tree_is_refused():
    """The second review of #2788 (P3-3): the reader holds the record's rule, so a reference the
    record would refuse is never read. Bug caught: a calibration reading naming a tree before it
    accepted by Project history, which then reads it as an increment's."""
    form = recorded("outcome_evaluation_ref", "calibration_record")
    earlier = recorded("outcome_evaluation_ref", "valid")["previous_accepted_tree_identity"]

    with pytest.raises(EvaluationInvalid, match="builds on nothing"):
        parse_reference({**form, "previous_accepted_tree_identity": earlier})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"cycle_id": None}, "exactly one of cycle_id and calibration_record_id"),
        ({"calibration_record_id": "calrec_10l0000001"}, "exactly one of cycle_id and"),
        ({"calibration_record_id": ""}, "calibration_record_id must be non-empty text or null"),
        ({"calibration_record_id": 7}, "calibration_record_id must be non-empty text or null"),
        ({"cycle_id": ""}, "cycle_id must be non-empty text or null"),
    ],
    ids=["names-neither", "names-both", "an-empty-record", "a-number-as-a-record", "empty-cycle"],
)
def test_a_reference_names_exactly_one_unit_or_is_refused(change, message):
    """§10l: a reading names a cycle or a calibration record, as the accepted tree does (SIP-0109
    §24cc). Bugs caught: a reference naming no unit read as a cycle's; one naming both read as
    either; a record id coerced from a number (``7`` read as ``"7"``)."""
    with pytest.raises(EvaluationInvalid, match=message):
        parse_reference({**recorded("outcome_evaluation_ref", "valid"), **change})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"calibration_record_id": None}, "exactly one of cycle_id and calibration_record_id"),
        ({"cycle_id": "cyc_10l000000001"}, "exactly one of cycle_id and calibration_record_id"),
        ({"previous_accepted_tree_identity": "b" * 64}, "builds on nothing"),
    ],
    ids=["names-neither", "names-both", "a-calibration-with-a-previous-tree"],
)
def test_an_evaluation_record_names_exactly_one_unit_and_a_calibration_builds_on_nothing(
    change, message
):
    """§10l. Bugs caught: a record written for no unit, which no reader can join to a cycle or a
    campaign; or a calibration reading naming a tree before it, which the package would then read
    as an increment, with a contribution against something that was never accepted."""
    with pytest.raises(EvaluationInvalid, match=message):
        _calibration_reading(**change)


def test_the_reference_module_imports_nothing_an_evaluation_found():
    """Contract 5's phase-1 rule: no result reaches the handoff. Project history imports this
    module alone. Bug caught: the reference importing an outcome or a result type, so the module
    Project history reads can carry one (the MacBook lane's review of #2449)."""
    tree = ast.parse(Path(reference.__file__).read_text(encoding="utf-8"))
    imported = {
        (node.module if isinstance(node, ast.ImportFrom) else alias.name).split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }

    assert imported - {"__future__"} <= set(sys.stdlib_module_names)
