"""Drafting, approving and revoking a lesson (SIP-0110 §0.4, §0.6–§0.7; slice 3d, #2096). Each test is
one of §0.15's rows (combined guidance, approval, pattern identity, lesson provenance) at the core."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from squadops.memory.approval import (
    CONFLICT,
    NO_CONFLICT,
    CombinedCheck,
    LessonRefused,
    approve,
    draft_revision,
    overlaps,
    revoke,
    supplied_together,
)
from squadops.memory.lessons import ANY_STACK, pin
from squadops.memory.recall import UnitKind
from tests.unit.memory.test_lessons import T0, WHERE

pytestmark = [pytest.mark.domain_memory]

OBS = ("proposal_ruling:cmp_c4b81554bd59:e14", "proposal_ruling:cmp_c4b81554bd59:e17")
REPLAY = {"reference": "replay/2026-10-09/arm-a-vs-b", "result": "target absent 5/6 vs 1/6"}


def _draft(target="criterion_already_satisfied", where=WHERE, revisions=(), now=T0, **kw):
    fields = {
        "target_behavior": target,
        "text": "Name the manifest element the criterion checks.",
        "applicability": where,
        "template_id": "lesson.criterion_already_satisfied",
        "template_version": "1",
        "drafter_model": "claude-opus",
        "drafter_version": "5.5",
        "cited_observations": OBS,
        "known_observations": OBS,
        "revisions": revisions,
        "now": now,
    }
    return draft_revision(**{**fields, **kw})


def _approve(
    revision,
    *,
    where=None,
    checked=(),
    verdict=NO_CONFLICT,
    revisions=(),
    approvals=(),
    now=T0,
    **kw,
):
    fields = {
        "applicability": where or revision.applicability,
        "approved_by": "owner",
        "ruling": "the owner, 2026-10-09: approve it",
        "replay_check": REPLAY,
        "combined_check": CombinedCheck(tuple(checked), verdict, "auditor/combined/2026-10-09"),
        "revisions": revisions,
        "approvals": approvals,
        "now": now,
    }
    return approve(revision, **{**fields, **kw})


def test_a_draft_is_its_patterns_next_revision_and_cites_recorded_observations():
    """§0.15 lesson provenance and pattern identity. Bugs caught: a second draft of a target
    reusing revision 1 (overwriting the lesson units already pinned), or a draft citing evidence
    the store never recorded."""
    first = _draft()
    second = _draft(revisions=[first], text="Check the manifest before naming a criterion.")

    assert (first.revision, second.revision) == (1, 2)
    assert first.pattern_id == second.pattern_id
    assert (second.drafter_model, second.cited_observations) == ("claude-opus", OBS)
    with pytest.raises(LessonRefused, match="not recorded"):
        _draft(cited_observations=("proposal_ruling:cmp_x:e1",))
    with pytest.raises(LessonRefused, match="cites the observations"):
        _draft(cited_observations=())


def test_a_lesson_supplied_beside_an_approved_one_needs_their_combined_check():
    """§0.15 combined guidance. Bugs caught: two lessons under different patterns, each approved
    alone, reaching one task together untested; or a conflicting set approved as it stands."""
    held = _draft("criterion_names_no_element")
    held_approval = _approve(held)
    draft = _draft()
    known = {
        "revisions": [held, draft],
        "approvals": [held_approval],
        "now": T0 + timedelta(hours=1),
    }

    with pytest.raises(LessonRefused, match=f"not covered: \\['{held.revision_id}'\\]"):
        _approve(draft, **known)
    with pytest.raises(LessonRefused, match="conflicting set is not approved"):
        _approve(draft, checked=[held.revision_id], verdict=CONFLICT, **known)
    approval = _approve(draft, checked=[held.revision_id], **known)

    assert approval.combined_check["revision_ids"] == [held.revision_id]
    assert (approval.ruling, approval.replay_check) == ("the owner, 2026-10-09: approve it", REPLAY)


def test_the_combined_set_is_what_a_task_could_receive_and_nothing_else():
    """§0.8: one revision per pattern, and only approvals in force whose applicability meets the
    draft's. Bug caught: a check demanded for a lesson no task could receive beside the draft (its
    own older revision, a revoked approval, another role's lesson), which only an approval that
    pads its check could pass."""
    older = _draft()
    other_role = _draft("x", where=dataclasses.replace(WHERE, roles=("dev",)))
    revoked = _draft("y")
    draft = _draft(revisions=[older])
    approvals = [
        _approve(older),
        _approve(other_role),
        revoke(_approve(revoked), by="owner", reason="harmful", now=T0 + timedelta(minutes=5)),
    ]

    together = supplied_together(
        WHERE,
        pattern_id=draft.pattern_id,
        revisions=[older, other_role, revoked, draft],
        approvals=approvals,
        at=T0 + timedelta(hours=1),
    )

    assert together == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"where": dataclasses.replace(WHERE, roles=("strat", "dev"))}, "never widen"),
        ({"where": dataclasses.replace(WHERE, model_families=("qwen3", "qwen3.8"))}, "never widen"),
        ({"ruling": " "}, "owner's ruling"),
        ({"replay_check": {"reference": "r"}}, "replay check"),
    ],
)
def test_an_approval_never_widens_its_revision_and_records_what_it_rests_on(change, message):
    """§0.15 approval and model scope: widened applicability, or another model family, needs its
    own draft and replay check. Bug caught: an approval reaching tasks the replay never tested."""
    with pytest.raises(LessonRefused, match=message):
        _approve(_draft(), **change)


def test_an_approval_may_narrow_its_revision_and_a_revocation_stands_once():
    revision = _draft(where=dataclasses.replace(WHERE, stacks=(ANY_STACK,)))
    narrow = dataclasses.replace(WHERE, stacks=("nextjs_ts",))
    approval = _approve(revision, where=narrow)
    revoked = revoke(approval, by="owner", reason="harmful", now=T0 + timedelta(hours=2))

    assert approval.applicability == narrow
    assert (revoked.revoked_by, revoked.revocation_reason) == ("owner", "harmful")
    with pytest.raises(LessonRefused, match="was revoked"):
        revoke(revoked, by="owner", reason="again", now=T0 + timedelta(hours=3))
    with pytest.raises(LessonRefused, match="says why"):
        revoke(approval, by="owner", reason=" ", now=T0 + timedelta(hours=3))


def test_a_new_draft_of_a_revoked_lesson_is_not_resurrected_by_its_old_approval():
    """§0.15 pattern identity. Bug caught: a recurrence's new draft riding the revoked revision's
    approval back into prompts unapproved."""
    first = _draft()
    approval = revoke(_approve(first), by="owner", reason="harmful", now=T0 + timedelta(hours=1))
    second = _draft(revisions=[first], now=T0 + timedelta(hours=2))

    snapshot = pin(
        unit_kind=UnitKind.CYCLE,
        unit_id="cyc_later",
        pinned_at=T0 + timedelta(hours=3),
        disabled=False,
        revisions=[first, second],
        approvals=[approval],
    )

    assert second.revision == 2 and snapshot.entries == ()


def test_lessons_overlap_only_where_some_task_falls_inside_both():
    assert overlaps(WHERE, dataclasses.replace(WHERE, stacks=(ANY_STACK,)))
    assert not overlaps(WHERE, dataclasses.replace(WHERE, roles=("dev",)))
    assert not overlaps(WHERE, dataclasses.replace(WHERE, project_id="play_game"))
