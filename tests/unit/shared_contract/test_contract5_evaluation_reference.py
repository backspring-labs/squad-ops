"""Contract 5, the reference's side (SIP-0112 §8.2.1; SIP-0113 §4.8; #2415): Outcome Evaluation's
record yields the reference the shared fixture records, and the reader refuses what it must.

The fixture's README assigns this side to #2415. The history side (write it into Project history,
read it back) lands with the slice that first writes Project history.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from squadops.scenarios.evaluation import (
    EvaluationInvalid,
    EvaluationRecord,
    UnknownSchemaMajor,
    parse_reference,
)
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
        ({"campaign_id": ""}, "never empty"),
        ({"schema": "something-else/v1"}, "not an outcome evaluation reference"),
    ],
    ids=["a-commit-as-a-tree", "an-empty-campaign", "another-schema"],
)
def test_a_reference_that_names_the_wrong_kind_of_thing_is_refused(change, message):
    """SIP-0112 §8.2.1: identifiers never substitute for one another. Bug caught: a Git commit
    stored where a tree identity belongs, or a document of another kind read as a reference."""
    with pytest.raises(EvaluationInvalid, match=message):
        parse_reference({**recorded("outcome_evaluation_ref", "valid"), **change})
