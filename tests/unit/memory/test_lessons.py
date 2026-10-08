"""Lessons, approvals, the pinned snapshot and deterministic recall (SIP-0110 §0.6–§0.8; slice 3c).
Each test is one of §0.15's acceptance rows, at the pure core."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from squadops.memory.lessons import (
    ANY_STACK,
    Applicability,
    Approval,
    PatternRevision,
    RecallDisposition,
    RecallPolicy,
    UnitKind,
    pattern_id_for,
    pin,
    recall,
)
from squadops.memory.recall import RecallQuery

pytestmark = [pytest.mark.domain_memory]

T0 = datetime(2026, 10, 8, tzinfo=UTC)
WHERE = Applicability(
    project_id="group_run",
    task_types=("strategy.propose_increment",),
    roles=("strat",),
    stacks=("fullstack_fastapi_react",),
    model_families=("qwen3",),
)
ASK = RecallQuery(
    "group_run", "strategy.propose_increment", "strat", "fullstack_fastapi_react", "qwen3"
)


def _revision(
    behavior: str, revision: int = 1, text: str = "Name the manifest element.", where=WHERE
):
    return PatternRevision(
        pattern_id=pattern_id_for("group_run", behavior, "strategy.propose_increment"),
        revision=revision,
        target_behavior=behavior,
        text=text,
        applicability=where,
        template_id="lesson.criterion_already_satisfied",
        template_version="1",
        drafter_model="claude-opus",
        drafter_version="5.5",
        cited_observations=("proposal_ruling:cmp_c4b81554bd59:e14",),
        created_at=T0,
    )


def _approve(revision: PatternRevision, at: datetime = T0, where=WHERE, **kw) -> Approval:
    return Approval(
        approval_id=f"apr_{revision.revision_id}_{at.isoformat()}",
        revision_id=revision.revision_id,
        applicability=where,
        approved_by="owner",
        approved_at=at,
        **kw,
    )


def _snapshot(revisions, approvals, *, at=T0 + timedelta(hours=1), disabled=False, policy=None):
    return pin(
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_x",
        pinned_at=at,
        disabled=disabled,
        revisions=revisions,
        approvals=approvals,
        policy=policy,
    )


def test_an_approved_lesson_reaches_exactly_the_applicability_it_was_approved_for():
    """Bug caught: a lesson reaching another project, another stack or another role (§0.15
    isolation), or an unknown read as "everywhere"."""
    rev = _revision("criterion_already_satisfied")
    snapshot = _snapshot([rev], [_approve(rev)])

    assert recall(snapshot, ASK).disposition is RecallDisposition.SUPPLIED
    for other in (
        dataclasses.replace(ASK, project_id="play_game"),
        dataclasses.replace(ASK, stack="nextjs_ts"),
        dataclasses.replace(ASK, role="dev"),
        dataclasses.replace(ASK, task_type="development.develop"),
        RecallQuery("group_run", "strategy.propose_increment"),  # the 2.1 rails' query: no scope
    ):
        assert recall(snapshot, other).disposition is RecallDisposition.NONE_ELIGIBLE


def test_a_lesson_approved_for_one_model_family_is_not_recalled_for_another():
    """§0.15 model scope. Bug caught: a lesson tuned on one family's mistakes handed to another."""
    rev = _revision("criterion_already_satisfied")
    snapshot = _snapshot([rev], [_approve(rev)])

    assert recall(snapshot, dataclasses.replace(ASK, model_family="gemma3")).supplied == ()


def test_a_stack_independent_lesson_says_so_explicitly():
    """Bug caught: an empty stack list read as every stack."""
    anywhere = dataclasses.replace(WHERE, stacks=(ANY_STACK,))
    rev = _revision("criterion_already_satisfied", where=anywhere)
    snapshot = _snapshot([rev], [_approve(rev, where=anywhere)])

    assert (
        recall(snapshot, dataclasses.replace(ASK, stack="nextjs_ts")).disposition
        is RecallDisposition.SUPPLIED
    )


def test_tied_approvals_and_more_than_three_lessons_select_the_same_three_every_time():
    """§0.15 determinism. Bug caught: a selection that varies between two identical units, so the
    comparison of arms moves under itself."""
    revisions = [_revision(f"behavior_{n}", text="x" * 40) for n in range(5)]
    approvals = [_approve(r) for r in revisions]  # every approval at the same instant

    first = recall(_snapshot(revisions, approvals), ASK)
    again = recall(_snapshot(list(reversed(revisions)), list(reversed(approvals))), ASK)

    assert [e.revision.revision_id for e in first.supplied] == [
        e.revision.revision_id for e in again.supplied
    ]
    assert len(first.supplied) == 3
    assert sorted(first.supplied, key=lambda e: e.revision.pattern_id) == list(first.supplied)
    assert {why for _, why in first.omitted} == {"budget"}


def test_a_lesson_over_the_token_budget_is_left_out_whole_never_cut():
    """§0.15 budget. Bug caught: a lesson truncated mid-sentence into a prompt."""
    small = _revision("small", text="Check the manifest first.")
    large = _revision("large", text="y" * 4000)
    snapshot = _snapshot(
        [small, large], [_approve(small), _approve(large, at=T0 + timedelta(minutes=1))]
    )

    out = recall(snapshot, ASK)

    assert [e.revision.text for e in out.supplied] == ["Check the manifest first."]
    assert out.omitted == ((large.revision_id, "budget"),)
    only_large = recall(_snapshot([large], [_approve(large)]), ASK)
    assert only_large.disposition is RecallDisposition.OMITTED_BY_BUDGET


def test_a_pattern_supplies_its_latest_approved_revision_only():
    """Bug caught: two revisions of one lesson both supplied, or the older one."""
    v1 = _revision("criterion_already_satisfied", revision=1, text="v1")
    v2 = _revision("criterion_already_satisfied", revision=2, text="v2")
    out = recall(_snapshot([v1, v2], [_approve(v1), _approve(v2)]), ASK)

    assert [e.revision.text for e in out.supplied] == ["v2"]
    assert (v1.revision_id, "superseded") in out.omitted


def test_a_unit_that_declares_memory_disabled_pins_and_recalls_nothing():
    """§0.15 memory disabled. Bug caught: a counted regression roll handed a lesson (D12)."""
    rev = _revision("criterion_already_satisfied")
    snapshot = _snapshot([rev], [_approve(rev)], disabled=True)

    assert snapshot.entries == ()
    assert recall(snapshot, ASK).disposition is RecallDisposition.DISABLED
    assert recall(None, ASK).disposition is RecallDisposition.DISABLED


def test_a_unit_keeps_what_it_pinned_whatever_is_approved_or_revoked_later():
    """§0.15 unit freeze, and §0.6. Bugs caught: an approval given after admission reaching a
    running unit, a revocation after admission changing it (emergency revocation restarts the
    work instead, §0.7), or an approval that widens its revision's applicability."""
    rev = _revision("criterion_already_satisfied")
    pinned = T0 + timedelta(hours=1)
    wider = dataclasses.replace(WHERE, roles=("strat", "dev"))

    late = _snapshot([rev], [_approve(rev, at=pinned + timedelta(minutes=1))], at=pinned)
    revoked_after = _snapshot(
        [rev], [_approve(rev, revoked_at=pinned + timedelta(minutes=5))], at=pinned
    )
    revoked_before = _snapshot(
        [rev], [_approve(rev, revoked_at=pinned - timedelta(minutes=5))], at=pinned
    )
    widened = _snapshot([rev], [_approve(rev, where=wider)], at=pinned)

    assert late.entries == () and revoked_before.entries == () and widened.entries == ()
    assert len(revoked_after.entries) == 1


def test_the_exposure_records_what_was_supplied_and_what_was_left_out_and_why():
    """Bug caught: an exposure that cannot say which lessons a prompt carried, so an assessment
    attaches to nothing (§0.10)."""
    small = _revision("small", text="ok")
    large = _revision("large", text="z" * 4000)
    out = recall(
        _snapshot([small, large], [_approve(small), _approve(large)], policy=RecallPolicy()), ASK
    )

    exposure = out.exposure()

    assert exposure["disposition"] == "supplied" and exposure["snapshot"].startswith("snp_")
    assert [i["revision_id"] for i in exposure["intervention"]] == [small.revision_id]
    assert exposure["omitted"] == [{"revision_id": large.revision_id, "reason": "budget"}]
