"""A run's revision forms as its record (#1710): read from each task's outputs, kept on the run's
summary, and never moving an assessment's identity."""

from __future__ import annotations

import pytest

from squadops.cycles.llm_usage import RunUsageAccumulator
from squadops.cycles.run_loop_summary import RunLoopSummary, revision_forms_of


@pytest.mark.parametrize(
    ("outputs", "kinds"),
    [
        ({"revision_form": {"form": "edits"}}, ["repair"]),
        ({"self_eval_revision_forms": [{"pass": 1}, {"pass": 2}]}, ["self_eval", "self_eval"]),
        ({"qa_retake_revision_form": {"form": "whole_file"}}, ["qa_retake"]),
        ({"artifacts": []}, []),
        (None, []),
    ],
    ids=["repair", "self-eval-passes", "qa-retake", "none", "no-outputs"],
)
def test_each_kind_of_form_is_read_and_named_by_its_task(outputs, kinds):
    """Bug caught: one kind dropped (a self-evaluation's list read as one form, or not at all),
    or a form kept without the task that took it."""
    forms = revision_forms_of("t-1", "qa.test", outputs)
    assert [f["kind"] for f in forms] == kinds
    assert all(f["task_id"] == "t-1" and f["task_type"] == "qa.test" for f in forms)


def test_a_summary_written_before_the_forms_reads_none_and_a_new_one_round_trips():
    """Bug caught: an old row read as a run that took no revision form, which the package would
    report as fact."""
    forms = ({"kind": "repair", "task_id": "t", "task_type": "x", "form": "edits"},)
    new = RunLoopSummary(run_id="r", usage=RunUsageAccumulator().summary(), revision_forms=forms)
    old = new.to_dict()
    del old["revision_forms"]

    assert RunLoopSummary.from_dict(new.to_dict()).revision_forms == forms
    assert RunLoopSummary.from_dict(old).revision_forms is None


def test_the_forms_never_move_an_assessments_identity():
    """Bug caught: the field moving every identity the benchmark registry and the set records
    hold, the way an added evidence field would (#1813's rule)."""
    import dataclasses

    from squadops.cycles.cycle_assessment import evidence_identity
    from tests.unit.cycles.test_cycle_assessment import _accepted_cycle

    outcome, evidence = _accepted_cycle()
    summaries = {
        k: dataclasses.replace(v, revision_forms=({"kind": "repair", "form": "edits"},))
        for k, v in (evidence.loop_summaries or {}).items()
    }
    assert summaries, "the fixture carries a run summary"
    with_forms = dataclasses.replace(evidence, loop_summaries=summaries)
    assert evidence_identity(outcome, with_forms) == evidence_identity(outcome, evidence)
