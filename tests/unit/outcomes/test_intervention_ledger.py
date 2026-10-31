"""The intervention ledger (SIP-0113 §4.3, §7 prediction 5; #2417)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.campaigns.models import (
    CampaignState,
    ControlLogEntry,
    ControlOperation,
    ControlOutcome,
)
from squadops.outcomes.ledger import (
    Classification,
    DeclaredIntervention,
    LedgerInvalid,
    check_classifiable,
    is_intervention,
    ledger,
)

T0 = datetime(2026, 10, 18, 23, 30, tzinfo=UTC)


def _row(op, *, seq=1, role="admin", outcome=ControlOutcome.APPLIED, **binding) -> ControlLogEntry:
    return ControlLogEntry(
        entry_id=f"ent_{seq:03d}",
        campaign_id="cmp_ledger000001",
        seq=seq,
        operation=op,
        actor="owner" if role == "admin" else role,
        actor_role=role,
        reason="r",
        target=None,
        idempotency_key=f"k{seq}",
        request_hash="h",
        binding=binding,
        outcome=outcome,
        refusal=None,
        prior_state=CampaignState.BUILDING,
        next_state=CampaignState.BUILDING,
        committed_at=T0 + timedelta(minutes=seq),
    )


@pytest.mark.parametrize(
    ("row", "intervenes"),
    [
        (_row(ControlOperation.PAUSE), True),
        (_row(ControlOperation.PAUSE, role="sweep"), False),
        (_row(ControlOperation.RESUME, role="campaign-supervisor"), True),
        (_row(ControlOperation.ABORT, outcome=ControlOutcome.REFUSED), False),
        (_row(ControlOperation.RULE, decision="approved"), False),
        (_row(ControlOperation.RULE, decision="returned_for_revision"), True),
        (_row(ControlOperation.RULE, decision="rejected"), True),
        (_row(ControlOperation.ESCALATION_CLOSED, role="sweep", state="resolved"), True),
        (_row(ControlOperation.ESCALATION_CLOSED, role="sweep", state="expired"), False),
        (_row(ControlOperation.ESCALATION_ANSWERED), True),
        (_row(ControlOperation.CLASSIFY, role="campaign-supervisor"), True),
        (_row(ControlOperation.DECIDE, role="completion"), False),
        (_row(ControlOperation.MARK_LAUNCHED, role="launcher"), False),
        (_row(ControlOperation.CREATE), False),
    ],
    ids=[
        "owner-pause",
        "a-limit-pause",
        "supervisor-resume",
        "refused-abort",
        "approval",
        "return",
        "rejection",
        "escalation-a-person-resolved",
        "escalation-that-expired",
        "late-answer",
        "classify",
        "the-continuation-decision",
        "the-launcher",
        "creation",
    ],
)
def test_an_intervention_is_a_person_acting_on_the_campaign(row, intervenes):
    """§4.3's list. Bug caught: the system's own rows (a limit's pause, a launch, a decision)
    counted as interventions, which would read a campaign that ran unattended as an attended one;
    an approval at the gate counted as one; or a returned proposal or a refused abort miscounted."""
    assert is_intervention(row) is intervenes


def test_the_ledger_names_every_unclassified_row_and_every_classification_without_one():
    """§7 prediction 5. Bug caught: a ledger that reads as complete while an intervention went
    unclassified, or keeps a classification whose row isn't an intervention of this campaign."""
    log = [
        _row(ControlOperation.PAUSE, seq=1),
        _row(ControlOperation.RESUME, seq=2),
        _row(ControlOperation.RULE, seq=3, decision="approved"),
    ]
    classified = [
        Classification("ent_001", "cmp_ledger000001", "verification", "unblock", "supervisor", T0),
        Classification("ent_003", "cmp_ledger000001", "planning", "advisory", "supervisor", T0),
    ]
    declared = [
        DeclaredIntervention(
            "dcl_1", "cmp_ledger000001", "environment", "recovery", "restarted the runtime API",
            occurred_at=T0 + timedelta(seconds=90), declared_by="owner", declared_at=T0,
        )
    ]  # fmt: skip

    read = ledger("cmp_ledger000001", log, classified, declared)

    assert [e.operation for e in read.entries] == ["pause", "declared", "resume"]
    assert (read.unclassified, read.orphaned) == (("ent_002",), ("ent_003",))
    assert not read.matches_the_control_log


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: check_classifiable(_row(ControlOperation.CREATE), "cmp_ledger000001"), "not an intervention"),
        (lambda: check_classifiable(_row(ControlOperation.PAUSE), "cmp_other0000001"), "no such control-log row"),
        (lambda: check_classifiable(None, "cmp_ledger000001"), "no such control-log row"),
        (lambda: Classification("e", "c", "laziness", "advisory", "s", T0), "reason 'laziness'"),
        (lambda: Classification("e", "c", "tool", "catastrophic", "s", T0), "severity 'catastrophic'"),
        (lambda: DeclaredIntervention("d", "c", "tool", "advisory", " ", T0, "s", T0), "says what was done"),
    ],
    ids=["not-an-intervention", "another-campaign", "no-row", "unknown-reason", "unknown-severity", "empty-declaration"],
)  # fmt: skip
def test_what_the_ledger_cannot_hold_is_refused(make, message):
    """Bug caught: a classification that names a row the ledger never counts (or another
    campaign's), a reason outside §4.3's list, or a declared entry that says nothing."""
    with pytest.raises(LedgerInvalid, match=message):
        make()
