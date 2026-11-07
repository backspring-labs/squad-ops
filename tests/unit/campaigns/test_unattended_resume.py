"""The unattended resume's rule, pure (SIP-0109 §24da; the 2.6 plan's D6; #2891): the class each
escalating row records, the declaration a policy accepts, its place in the creation hash, the
increment's spent repairs and retries, and the digest's section.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from squadops.campaigns.escalation import (
    DelegatedMove,
    delegation_verdict,
    resumable_class,
    spent_on_increment,
)
from squadops.campaigns.evidence import digest, package
from squadops.campaigns.lifecycle import creation_request_hash
from squadops.campaigns.models import (
    CampaignState,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    LaunchIntent,
    LaunchIntentState,
    RefusalReason,
    ResumableClass,
)
from tests.unit.campaigns.builders import campaign, move, policy

T0 = datetime(2026, 11, 4, 3, 0, tzinfo=UTC)


def _row(operation, binding, *, next_state=CampaignState.ESCALATED, seq=7) -> ControlLogEntry:
    return ControlLogEntry(
        entry_id=f"ent_{seq}",
        campaign_id="cmp_1",
        seq=seq,
        operation=operation,
        actor="squadops",
        actor_role="completion",
        reason="r",
        target="cyc_1",
        idempotency_key=f"k{seq}",
        request_hash="h",
        binding=binding,
        outcome=ControlOutcome.APPLIED,
        refusal=None,
        prior_state=CampaignState.BUILDING,
        next_state=next_state,
        committed_at=T0,
    )


_ESC = {"action": "escalate", "guard": None, "paused_by": None}


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # A plan gate the tier escalated; a row from before kinds existed is one too.
        (_row(ControlOperation.ESCALATION_OPENED, {"kind": "plan_review"}, next_state=CampaignState.BUILDING), ResumableClass.PLAN_GATE),
        (_row(ControlOperation.ESCALATION_OPENED, {}, next_state=CampaignState.BUILDING), ResumableClass.PLAN_GATE),
        # §24bw: a binding hold is released by re-supply, never resumed.
        (_row(ControlOperation.ESCALATION_OPENED, {"kind": "binding_hold"}, next_state=CampaignState.BUILDING), None),
        # §10 rows 9, 11 and 14: the cycle's own failure.
        (_row(ControlOperation.DECIDE, {**_ESC, "row": 11, "ending": "assessed"}), ResumableClass.IN_CYCLE_FAILURE),
        # Row 17: an operator's input that can't be bound.
        (_row(ControlOperation.DECIDE, {**_ESC, "row": 17, "ending": "held_input"}), None),
        # A launch that couldn't be built (nothing pending, a refused promotion).
        (_row(ControlOperation.DECIDE, {"action": "propose", "guard": "proceed", "ending": "assessed", "unbuilt": "x"}), None),
        # A limit's pause holds an action; it escalates nothing.
        (_row(ControlOperation.DECIDE, {"action": "repair", "guard": "paused", "paused_by": "budget", "ending": "assessed"}, next_state=CampaignState.PAUSED), None),
        (_row(ControlOperation.LAUNCH_BLOCKED, {"attempt": 6}), ResumableClass.LAUNCH_BLOCKED),
        # An attempt short of the count is still blocked, not escalated.
        (_row(ControlOperation.LAUNCH_BLOCKED, {"attempt": 2}, next_state=CampaignState.LAUNCH_BLOCKED), None),
        # The rebase's conflict and the cycle-create path's refusal: an upstream conflict, never.
        (_row(ControlOperation.LAUNCH_REFUSED, {"refusal": "CAMPAIGN_BRANCH_CONFLICT: a"}), None),
        (_row(ControlOperation.BRANCH_REBASED, {"unbuilt": "x"}), None),
        (_row(ControlOperation.PAUSE, {}, next_state=CampaignState.PAUSED), None),
    ],
    ids=[
        "plan-gate", "plan-gate-pre-kinds", "binding-hold", "in-cycle", "held-input", "unbuilt",
        "limit-pause", "launch-blocked", "blocked-attempt", "launch-refused", "rebase-unbuilt",
        "pause",
    ],
)  # fmt: skip
def test_each_escalating_row_reads_as_its_class(row, expected):
    """Bug caught: a never-class (an upstream conflict, a limit's pause, an operator's input)
    read as a delegable one, so the operator resumes what D6 keeps with the owner."""
    assert resumable_class(row) is expected


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        (["upstream_conflict"], "'upstream_conflict' is not an escalation class"),
        (["limit_pause"], "'limit_pause' is not an escalation class"),
        (["security_finding"], "'security_finding' is not an escalation class"),
        (["owners_pause"], "'owners_pause' is not an escalation class"),
        (["plan_gate", "plan_gate"], "names 'plan_gate' twice"),
        ("plan_gate", "is a list of escalation classes"),
    ],
)
def test_a_policy_refuses_what_is_not_a_resumable_class(declared, message):
    """The never-classes are not declarable at all. Bug caught: a definition that delegates a
    limit's pause, accepted because the field took any string."""
    with pytest.raises(ValueError, match=message):
        policy(unattended_resume=declared)


def test_the_declaration_is_part_of_the_creation_hash_only_when_set():
    """Bugs caught: every stored campaign's creation hash moved by the new field (its creation's
    retry then conflicts), or a declaration left out of the hash, so two definitions granting
    different authority read as the same one."""
    plain = campaign(policy=policy())
    stated_empty = campaign(policy=policy(unattended_resume=[]))
    granted = campaign(policy=policy(unattended_resume=["in_cycle_failure"]))
    wider = campaign(policy=policy(unattended_resume=["in_cycle_failure", "plan_gate"]))

    def h(c):
        return creation_request_hash(c, actor="owner", actor_role="admin", reason="r")

    # The hash this definition's creation had before the field existed, computed by main's code
    # without it.
    assert h(plain) == "fba6b2919996fdecb76cf9b83d04fae9dcd99eda7e2104d3170f3b4acfd1fcfd"
    assert h(plain) == h(stated_empty)
    assert len({h(plain), h(granted), h(wider)}) == 3


def _intent(kind: CycleKind, minutes: int, state=LaunchIntentState.LAUNCHED) -> LaunchIntent:
    return LaunchIntent(
        launch_id=f"lnc_{minutes}",
        campaign_id="cmp_1",
        decision_entry_id="ent",
        cycle_kind=kind,
        cycle_request={},
        state=state,
        created_at=T0 + timedelta(minutes=minutes),
    )


def test_the_spent_retries_and_repairs_are_the_current_increments_only():
    """Bugs caught: an earlier increment's retries spending this one's limit, or a retry a rebase
    superseded (never launched) counted against it."""
    intents = [
        _intent(CycleKind.INCREMENT, 1),
        _intent(CycleKind.RETRY, 2),
        _intent(CycleKind.RETRY, 3),
        _intent(CycleKind.INCREMENT, 4),
        _intent(CycleKind.REPAIR, 5),
        _intent(CycleKind.RETRY, 6, LaunchIntentState.SUPERSEDED),
        _intent(CycleKind.RETRY, 7, LaunchIntentState.PENDING),
    ]

    assert spent_on_increment(reversed(intents)) == {CycleKind.REPAIR: 1, CycleKind.RETRY: 1}
    assert spent_on_increment([]) == {CycleKind.REPAIR: 0, CycleKind.RETRY: 0}


@pytest.mark.parametrize(
    ("move_", "spent", "allowed", "why"),
    [
        (DelegatedMove.RETRY, 0, True, "permits retry"),
        (DelegatedMove.RETRY, 1, False, "spent 1 retry cycle(s)"),
        (DelegatedMove.RELAUNCH, 0, False, "permits ['repair', 'retry'], not relaunch"),
        (None, 0, False, "not this resume"),
    ],
)
def test_the_verdict_holds_a_class_to_its_moves_and_its_limit(move_, spent, allowed, why):
    stored = campaign(
        state=CampaignState.ESCALATED, policy=policy(unattended_resume=["in_cycle_failure"])
    )
    row = _row(ControlOperation.DECIDE, {**_ESC, "row": 9, "ending": "assessed"})

    verdict = delegation_verdict(
        stored, row, held="escalated", move=move_, spent={CycleKind.RETRY: spent}
    )

    assert (verdict.allowed, verdict.escalation_class) == (allowed, ResumableClass.IN_CYCLE_FAILURE)
    assert why in verdict.why
    assert verdict.escalation == {"seq": 7, "operation": "decide", "target": "cyc_1"}


async def test_the_digest_lists_each_delegated_resume_and_each_refusal():
    """D6's audit: the digest lists them, from the control log. Bug caught: a refusal recorded
    but invisible in the morning's reading, or a delegated resume read as the owner's word."""
    registry = MemoryCampaignRegistry()
    cid = "cmp_digest000001"
    await registry.create_campaign(
        campaign(cid, policy=policy(unattended_resume=["in_cycle_failure"])),
        actor="owner", actor_role="admin", reason="r", idempotency_key="k",
    )  # fmt: skip
    await registry.transition(cid, move(CampaignState.CALIBRATING, "cal"))
    audit = {
        "delegated": True,
        "class": "in_cycle_failure",
        "move": "retry",
        "escalation": {"seq": 2, "operation": "decide", "target": "cyc_1"},
        "definition_hash": "f" * 64,
    }
    await registry.refuse(
        cid,
        move(CampaignState.CALIBRATING, "operator-1", operation=ControlOperation.RESUME,
             actor="operator", actor_role="campaign-supervisor",
             binding={**audit, "delegated": False, "class": None, "move": "retry",
                      "why": "the pause row (seq 3) escalated the campaign"}),
        RefusalReason.RESUME_NOT_DELEGATED,
    )  # fmt: skip
    await registry.transition(
        cid,
        move(CampaignState.CALIBRATING, "operator-2", operation=ControlOperation.RESUME,
             actor="operator", actor_role="campaign-supervisor", binding=audit),
    )  # fmt: skip
    # The owner's own resume carries no delegation, and is not listed.
    await registry.transition(
        cid, move(CampaignState.CALIBRATING, "owner-1", operation=ControlOperation.RESUME)
    )

    text = digest(
        package(
            await registry.get_campaign(cid),
            await registry.control_log(cid),
            [],
            [],
            outcomes=None,
            interventions=None,
        )
    )

    section = text.split("## Unattended resumes\n\n")[1].split("\n## ")[0]
    assert section.splitlines() == [
        "Declared: `in_cycle_failure`.",
        "1 delegated resume(s), 1 refused.",
        "",
        "- seq 3: refused by operator (campaign-supervisor), class `none`, move `retry`, on decide "
        "row 2; definition `ffffffffffff`. Why: the pause row (seq 3) escalated the campaign",
        "- seq 4: resumed by operator (campaign-supervisor), class `in_cycle_failure`, move `retry`, "
        "on decide row 2; definition `ffffffffffff`",
    ]


async def test_a_campaign_with_nothing_declared_says_so_and_lists_none():
    registry = MemoryCampaignRegistry()
    await registry.create_campaign(
        campaign("cmp_digest000002"), actor="o", actor_role="admin", reason="r",
        idempotency_key="k",
    )  # fmt: skip
    doc = package(
        await registry.get_campaign("cmp_digest000002"),
        await registry.control_log("cmp_digest000002"),
        [],
        [],
        outcomes=None,
        interventions=None,
    )

    assert "## Unattended resumes\n\nDeclared: nothing.\n0 delegated resume(s), 0 refused.\n" in (
        digest(doc)
    )
