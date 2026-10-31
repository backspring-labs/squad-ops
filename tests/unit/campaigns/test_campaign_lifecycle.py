"""The campaign lifecycle and the control operation's shape (SIP-0109 §15, §17)."""

from __future__ import annotations

import pytest

from squadops.campaigns.lifecycle import (
    LEGAL_TRANSITIONS,
    adjudicate,
    control_log_entry,
    launch_id_for,
)
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignOutcome,
    CampaignState,
    CampaignTransition,
    ControlOperation,
    CycleKind,
    LaunchRequest,
    RefusalReason,
)
from tests.unit.campaigns.builders import T0, campaign, move, policy

S = CampaignState


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.DRAFT, S.CALIBRATING),
        (S.CALIBRATING, S.AT_PROPOSAL),
        (S.AT_PROPOSAL, S.AWAITING_RULING),
        (S.AWAITING_RULING, S.BUILDING),
        (S.AWAITING_RULING, S.AT_PROPOSAL),
        (S.BUILDING, S.EVALUATING),
        (S.EVALUATING, S.PROMOTING),
        (S.EVALUATING, S.REPAIRING),
        (S.EVALUATING, S.RETRYING),
        (S.EVALUATING, S.AT_PROPOSAL),
        (S.PROMOTING, S.AT_PROPOSAL),
        (S.REPAIRING, S.EVALUATING),
        (S.RETRYING, S.EVALUATING),
        # any live state may hold, or complete; a holding state resumes into work
        (S.BUILDING, S.PAUSED),
        (S.AWAITING_RULING, S.ESCALATED),
        (S.CALIBRATING, S.LAUNCH_BLOCKED),
        (S.LAUNCH_BLOCKED, S.ESCALATED),
        (S.PAUSED, S.REPAIRING),
        (S.ESCALATED, S.AT_PROPOSAL),
        (S.DRAFT, S.COMPLETED),
        (S.DRAFT, S.LAUNCH_BLOCKED),
        (S.EVALUATING, S.COMPLETED),
    ],
)
def test_every_arrow_of_the_lifecycle_diagram_is_legal(current, target):
    assert target in LEGAL_TRANSITIONS[current]


@pytest.mark.parametrize(
    ("current", "target", "bug"),
    [
        (S.AT_PROPOSAL, S.BUILDING, "an increment building without a ruling"),
        (S.DRAFT, S.AT_PROPOSAL, "a campaign proposing before its calibration cycle"),
        (S.BUILDING, S.PROMOTING, "a promotion without evaluation"),
        (S.REPAIRING, S.PROMOTING, "a repair promoted without evaluation"),
        (S.PAUSED, S.DRAFT, "a resumed campaign back in draft"),
        (S.DRAFT, S.PAUSED, "a draft paused, though nothing runs in a draft"),
        (S.DRAFT, S.ESCALATED, "a draft escalated, with nothing to escalate"),
        (S.COMPLETED, S.AT_PROPOSAL, "a completed campaign revived"),
        (S.COMPLETED, S.COMPLETED, "a completed campaign completed twice"),
    ],
)
def test_moves_the_diagram_does_not_draw_are_illegal(current, target, bug):
    assert target not in LEGAL_TRANSITIONS[current], bug


def test_the_adjudication_refuses_an_illegal_move_and_a_stale_one():
    at_proposal = campaign(state=S.AT_PROPOSAL)
    assert adjudicate(at_proposal, move(S.BUILDING, "k1"), None).refusal is (
        RefusalReason.ILLEGAL_TRANSITION
    )
    stale = move(S.BUILDING, "k2", expected_state=S.AWAITING_RULING)
    assert adjudicate(at_proposal, stale, None).refusal is RefusalReason.STALE_STATE


def test_a_completed_campaign_accepts_only_a_record():
    done = campaign(state=S.COMPLETED, outcome=CampaignOutcome.ABORTED)
    decide = move(S.AT_PROPOSAL, "k1", launch=LaunchRequest(CycleKind.INCREMENT))
    assert adjudicate(done, decide, None).refusal is RefusalReason.CAMPAIGN_COMPLETED
    mark = CampaignTransition(
        operation=ControlOperation.MARK_LAUNCHED,
        actor="launcher-1",
        actor_role="launcher",
        reason="the launcher created the intent's cycle",
        idempotency_key="lnc_x:launched",
        next_state=None,
    )
    assert adjudicate(done, mark, None).refusal is None


def test_a_refusal_row_leaves_the_state_where_it_was():
    at_proposal = campaign(state=S.AT_PROPOSAL)
    row = control_log_entry(
        at_proposal,
        move(S.BUILDING, "k1"),
        entry_id="ctl_000000000001",
        seq=2,
        committed_at=T0,
        refusal=RefusalReason.ILLEGAL_TRANSITION,
        launch_id=None,
    )
    assert (row.prior_state, row.next_state) == (S.AT_PROPOSAL, S.AT_PROPOSAL)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (dict(next_state=S.COMPLETED), "an outcome is given exactly"),
        (dict(next_state=S.PAUSED, outcome=CampaignOutcome.FAILURE), "an outcome is given exactly"),
        (dict(operation=ControlOperation.MARK_LAUNCHED, next_state=S.PAUSED), "record-only"),
        (dict(next_state=None), "record-only"),
        (dict(operation=ControlOperation.CREATE), "create_campaign"),
        (dict(reason="  "), "reason is required"),
        (dict(idempotency_key=""), "idempotency_key is required"),
        # §12a: the accepted tree moves only by a promotion or (§24bv point 4) a branch's rebase,
        # and each names its tree.
        (dict(accepted=AcceptedTree("sha-1", "cyc_1")), "and only those, names the tree"),
        (dict(operation=ControlOperation.PROMOTE), "and only those, names the tree"),
        (dict(operation=ControlOperation.BRANCH_REBASED), "and only those, names the tree"),
        # §24cd point 2: only a rebase supersedes a pending repair or retry.
        (dict(supersedes="lnc_000000000001"), "only a branch's rebase supersedes"),
    ],
)
def test_a_malformed_control_operation_is_refused_at_construction(kwargs, message):
    values = dict(
        operation=ControlOperation.DECIDE,
        actor="squadops",
        actor_role="system",
        reason="r",
        idempotency_key="k",
        next_state=S.AT_PROPOSAL,
    )
    values.update(kwargs)
    with pytest.raises(ValueError, match=message):
        CampaignTransition(**values)


def test_a_record_cannot_launch():
    with pytest.raises(ValueError, match="cannot launch"):
        CampaignTransition(
            operation=ControlOperation.MARK_LAUNCHED,
            actor="launcher-1",
            actor_role="launcher",
            reason="r",
            idempotency_key="k",
            next_state=None,
            launch=LaunchRequest(CycleKind.INCREMENT),
        )


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (dict(max_cycles=0), "max_cycles must be >= 1"),
        (dict(ruling_bound_s=0), "ruling_bound_s must be >= 1"),
        # Reached at zero: the campaign would stop or pause on its first decision.
        (dict(max_unaccepted_increments=0), "max_unaccepted_increments must be >= 1"),
        (dict(max_repair_cycles_per_increment=-1), "must be >= 0"),
        (dict(budget_tokens=True), "must be an integer"),
        (dict(proposal_profile=" "), "proposal_profile is required"),
        # Every launch names the squad that runs it: a campaign without one cannot launch.
        (dict(squad_profile=""), "squad_profile is required"),
    ],
)
def test_a_policy_limit_outside_its_floor_is_refused(override, message):
    with pytest.raises(ValueError, match=message):
        policy(**override)


@pytest.mark.parametrize(
    ("prd_tier", "attendance", "said"),
    [
        ("tier-4", "attended", "prd_tier"),
        ("core", "half", "attendance"),
        ("Core", "attended", "prd_tier"),
    ],
    ids=["an-unknown-tier", "an-unknown-attendance", "a-tier-in-another-case"],
)
def test_a_work_class_outside_the_ruled_vocabulary_is_refused(prd_tier, attendance, said):
    """SIP-0113 §4.6, D2: the classes are declared from a fixed vocabulary, so two campaigns
    compare only when they declared the same. Bug caught: ``Core`` and ``core`` read as two
    classes, splitting one class's AOR in two."""
    from squadops.campaigns.models import WorkClass

    with pytest.raises(ValueError, match=said):
        WorkClass(prd_tier=prd_tier, attendance=attendance)


def test_a_policy_may_allow_no_repair_cycles():
    assert policy(max_repair_cycles_per_increment=0).max_repair_cycles_per_increment == 0


def test_a_campaign_carries_an_outcome_exactly_when_completed():
    with pytest.raises(ValueError, match="exactly when it is completed"):
        campaign(state=S.COMPLETED)
    with pytest.raises(ValueError, match="exactly when it is completed"):
        campaign(state=S.PAUSED, outcome=CampaignOutcome.SUCCESS)


def test_the_launch_id_is_derived_from_the_deciding_row():
    assert launch_id_for("ctl_3f9a0c1b2d4e") == "lnc_3f9a0c1b2d4e"
    with pytest.raises(ValueError, match="not a control-log entry id"):
        launch_id_for("cyc_3f9a0c1b2d4e")


def test_a_policy_stored_with_two_seat_bounds_reads_as_one_supervisors():
    """§24al: the ruling bound is the supervisor's, whoever holds the seat. Bug caught: every
    campaign stored before the change unreadable (the Postgres loader builds its policy from the
    stored row), or its bound read from the fallback seat instead of the supervisor's."""
    import dataclasses

    from squadops.campaigns.models import CampaignPolicy

    current = dataclasses.asdict(policy(ruling_bound_s=900))
    legacy = {k: v for k, v in current.items() if k != "ruling_bound_s"}
    legacy |= {"crew_ruling_bound_s": 1800, "owner_ruling_bound_s": 43200}

    assert CampaignPolicy.from_stored(legacy).ruling_bound_s == 1800
    assert CampaignPolicy.from_stored(current) == policy(ruling_bound_s=900)


def test_a_policy_stored_before_the_plan_gate_ran_supervised_and_an_unknown_mode_is_refused():
    """§24bj. Bug caught: every campaign stored before the field unreadable (the Postgres loader
    builds its policy from the stored row), one read as the tier it never declared, or a mode
    the tier does not know accepted into a policy."""
    import dataclasses

    from squadops.campaigns.models import CampaignPolicy, PlanGate

    stored = dataclasses.asdict(policy())
    del stored["plan_gate"]

    assert CampaignPolicy.from_stored(stored).plan_gate is PlanGate.SUPERVISED
    assert CampaignPolicy.from_stored({**stored, "plan_gate": "tier"}).plan_gate is PlanGate.TIER
    with pytest.raises(ValueError, match="plan_gate must be one of"):
        policy(plan_gate="auto")


def test_a_creation_without_a_definition_keeps_the_hash_it_was_stored_with():
    """#1954 adds the definition to a creation's content only when one is given. Bug caught: the
    hash of every definition-less creation changing, so a retried create of a campaign stored
    before #1954 reads as a different creation and is refused. The literal is the hash main
    computed for this creation before the change."""
    from dataclasses import replace

    from squadops.campaigns.lifecycle import creation_request_hash
    from squadops.campaigns.models import CampaignDefinition

    # Stored before SIP-0113's work class (#2418), so with none.
    created = campaign("cmp_hash0000001")
    created = replace(created, objective=replace(created.objective, work_class=None))
    before = creation_request_hash(created, actor="owner", actor_role="admin", reason="r")
    with_file = creation_request_hash(
        created,
        actor="owner",
        actor_role="admin",
        reason="r",
        definition=CampaignDefinition("set-1.yaml", "a" * 64),
    )

    assert before == "08aecfc79fc10fe8afb1f8f158f9df08b14e1bba092ef0a0bc0743e2b7d7e76f"
    assert with_file != before
    # §24bj: the supervised plan gate is how the creation above was stored, so it enters the hash
    # as that absence; the tier is a different creation.
    tiered = replace(created, policy=policy(plan_gate="tier"))
    assert creation_request_hash(tiered, actor="owner", actor_role="admin", reason="r") != before
    # §24bs: a stack left undeclared is how the creation above was stored; a declared one is a
    # different creation.
    stacked = replace(created, policy=policy(stack="nextjs_ts"))
    assert creation_request_hash(stacked, actor="owner", actor_role="admin", reason="r") != before
    # SIP-0113 §4.6 (#2418): the same for the objective's work class.
    classified = campaign("cmp_hash0000001")
    assert classified.objective.work_class is not None
    assert (
        creation_request_hash(classified, actor="owner", actor_role="admin", reason="r") != before
    )


@pytest.mark.parametrize("stack", ["python_cli_builder", "", "nextjs"])
def test_a_stack_a_campaign_cannot_run_on_is_refused(stack):
    """§24bs (#2443). Bug caught: a campaign accepted on a stack that has no scaffold or nowhere
    to put a criterion's test, whose first increment can only fail; or an empty stack read as
    the profiles' own instead of refused."""
    with pytest.raises(ValueError, match="not a stack a campaign can run on"):
        policy(stack=stack)


def test_a_policy_stored_before_the_stack_reads_as_its_profiles_own():
    """§24bs. Bug caught: every campaign stored before the field unreadable, as the Postgres
    loader builds its policy from the stored row."""
    import dataclasses

    from squadops.campaigns.models import CampaignPolicy

    stored = dataclasses.asdict(policy())
    del stored["stack"]

    assert CampaignPolicy.from_stored(stored).stack is None
    assert CampaignPolicy.from_stored({**stored, "stack": "nextjs_ts"}).stack == "nextjs_ts"


@pytest.mark.parametrize(
    ("path", "sha256", "message"),
    [
        ("", "a" * 64, "definition.path is required"),
        ("set-1.yaml", "A" * 64, "64 lowercase hex"),
        ("set-1.yaml", "a" * 63, "64 lowercase hex"),
    ],
)
def test_a_definition_that_names_no_file_or_no_hash_is_refused(path, sha256, message):
    from squadops.campaigns.models import CampaignDefinition

    with pytest.raises(ValueError, match=message):
        CampaignDefinition(path, sha256)
