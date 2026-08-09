"""The pre-memory rejection baseline (#809, B1).

The only item in 1.6 whose omission is permanent: once Cross-Cycle Memory exists, the
pre-memory recurrence picture cannot be reconstructed, and memory's whole value claim becomes
unmeasurable.

Bug classes guarded:

- **a rejection recorded without its class** — the defect this closes. A joined error string
  says what went wrong and not which kind of thing went wrong, and re-parsing prose at window
  time is the failure mode the plan names, not the fix;
- classification changing what gets rejected. A baseline is bookkeeping; if a counting bug
  could alter which plans pass, the instrument would be changing the experiment;
- recording a "rejection" when nothing was rejected, which inflates a baseline that is read
  as evidence;
- losing the second dimension. Memory can reduce how often a mistake happens *or* how
  expensively it is recovered from; a recurrence-only baseline scores the second as zero;
- a bookkeeping failure taking down the rejection path with it — a gap in a dataset is
  survivable, a lost cycle is not;
- the two vocabularies drifting: the baseline must speak the same validator names the
  authoring-rules asset teaches, or "did teaching this rule reduce it?" is unanswerable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.plan_authoring_rules import classified_validators
from squadops.cycles.rejection_baseline import (
    RejectionClassifier,
    build_baseline,
    render,
)

pytestmark = [pytest.mark.domain_contracts]

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "authored_v4"


# --------------------------------------------------------------------------- #
# Classifying at the point of rejection
# --------------------------------------------------------------------------- #


def test_collect_records_the_class_and_returns_the_errors_untouched():
    """Pass-through by design: it wraps an existing ``errors.extend(...)``, so a
    classification bug cannot change which plans are rejected."""
    classifier = RejectionClassifier()
    errors = ["a", "b"]

    returned = classifier.collect("validate_unique_expected_artifacts", errors)

    assert returned == errors
    assert classifier.classes == {"validate_unique_expected_artifacts": 2}


def test_a_validator_that_found_nothing_is_not_a_class():
    """Recording a clean validator would report rejections that never happened in a dataset
    read as evidence."""
    classifier = RejectionClassifier()

    classifier.collect("validate_command_checks", [])

    assert classifier.classes == {}
    assert classifier.record("progress_plan_review", []) == {}


def test_repeat_findings_from_one_validator_accumulate():
    classifier = RejectionClassifier()

    classifier.collect("validate_module_existence", ["x"])
    classifier.collect("validate_module_existence", ["y", "z"])

    assert classifier.classes == {"validate_module_existence": 3}


def test_the_record_carries_classes_and_the_prose_it_replaces():
    """Both, not either: the classes are what the baseline counts, and the errors stay so a
    human reading one record can still see what actually happened."""
    classifier = RejectionClassifier()
    classifier.collect("validate_criteria_scope", ["regex on source"])

    record = classifier.record("progress_plan_review", ["regex on source"])

    assert record["gate"] == "progress_plan_review"
    assert record["classes"] == {"validate_criteria_scope": 1}
    assert record["errors"] == ["regex on source"]


def test_the_baselines_vocabulary_is_the_one_authors_are_taught():
    """The names must be the `validate_*` family `plan_authoring_rules` classifies. A baseline
    speaking different names could not answer "did teaching this rule reduce it?" — which is
    the only question it exists to support."""
    known = classified_validators()
    assert known, "the validator classification must be discoverable"

    for name in ("validate_unique_expected_artifacts", "validate_module_existence"):
        assert name in known
        assert name in {n for n in dir(ImplementationPlan) if n.startswith("validate_")}


# --------------------------------------------------------------------------- #
# Assembling the baseline
# --------------------------------------------------------------------------- #


def test_a_cycle_with_no_rejections_has_an_empty_baseline():
    baseline = build_baseline(
        "cyc_clean", rejection_records=[], manifest_provenance=None, framing_run_count=1
    )

    assert baseline.classes == ()
    assert baseline.rerolls == 0


def test_both_dimensions_are_recorded():
    """Recurrence AND time-to-resolution. Memory that halves recovery cost without changing
    recurrence is a real win a recurrence-only baseline would score as zero."""
    baseline = build_baseline(
        "cyc_1",
        rejection_records=[{"classes": {"validate_unique_expected_artifacts": 1}}],
        manifest_provenance={"attempts": 2, "revisions": [{"classes": {"authoring_defect": 1}}]},
        framing_run_count=3,
    )

    assert baseline.attempts == 2
    assert baseline.rerolls == 2
    assert {c.rejection_class: c.occurrences for c in baseline.classes} == {
        "validate_unique_expected_artifacts": 1,
        "authoring_defect": 1,
    }


def test_plan_and_authoring_classes_share_one_baseline():
    """The plan asks for both families. Kept in one record because a reader asking "what did
    this cycle get wrong?" should not have to know which subsystem rejected it."""
    baseline = build_baseline(
        "cyc_2",
        rejection_records=[
            {"classes": {"validate_module_existence": 2}},
            {"classes": {"validate_module_existence": 1, "validate_build_config": 1}},
        ],
        manifest_provenance={"attempts": 1, "revisions": []},
        framing_run_count=1,
    )

    counts = {c.rejection_class: c.occurrences for c in baseline.classes}
    assert counts == {"validate_module_existence": 3, "validate_build_config": 1}


@pytest.mark.parametrize(("runs", "expected"), [(1, 0), (2, 1), (4, 3), (0, 0)])
def test_rerolls_come_from_the_run_count_not_a_counter(runs, expected):
    """The sequence creates one extra framing run per re-roll, so the runs ARE the record —
    nothing extra had to be persisted, and it works retrospectively on cycles that ran before
    this existed."""
    baseline = build_baseline(
        "cyc_3", rejection_records=[], manifest_provenance=None, framing_run_count=runs
    )

    assert baseline.rerolls == expected


def test_malformed_inputs_do_not_break_the_assembly():
    """A record is not a contract. Partial bookkeeping must still yield a usable row."""
    baseline = build_baseline(
        "cyc_4",
        rejection_records=[{}, {"classes": None}],
        manifest_provenance={"revisions": [{}]},
        framing_run_count=1,
    )

    assert baseline.classes == ()
    assert baseline.attempts == 0


# --------------------------------------------------------------------------- #
# Replay over the V4 evidence
# --------------------------------------------------------------------------- #


def test_v4_roll_1s_known_rejection_reproduces_its_class():
    """Roll 1 died on #673's dual claim — two tasks declaring `backend/routes/runs.py`. Run
    the real plan through the real validator and assert the baseline names that class, so the
    end-to-end shape is proven on observed data rather than a hand-made record."""
    plan = ImplementationPlan.from_yaml(
        (_FIXTURES / "implementation_plan.yaml").read_text(encoding="utf-8")
    )
    classifier = RejectionClassifier()
    errors = classifier.collect(
        "validate_unique_expected_artifacts", plan.validate_unique_expected_artifacts()
    )

    assert errors, "roll 1's plan is supposed to trip the dual-claim rule"
    baseline = build_baseline(
        "cyc_9c8c98ea3171",
        rejection_records=[classifier.record("progress_plan_review", errors)],
        manifest_provenance=None,
        framing_run_count=1,
    )

    assert [c.rejection_class for c in baseline.classes] == ["validate_unique_expected_artifacts"]


def test_render_is_json_a_later_reader_can_consume():
    """1.8 reads this; 1.6 reads nothing. It has to be self-describing to someone who was not
    here when it was written."""
    payload = json.loads(
        render(
            [
                build_baseline(
                    "cyc_x", rejection_records=[], manifest_provenance=None, framing_run_count=1
                )
            ]
        )
    )

    assert payload["schema"] == 1
    assert "pre-memory" in payload["purpose"]
    assert payload["cycles"][0]["cycle_id"] == "cyc_x"
