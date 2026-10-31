"""AOR's inputs and the work envelope, from campaign packages (SIP-0113 §4.6; #2418)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.outcomes.memory_ledger import MemoryInterventionLedger
from squadops.campaigns.models import ControlLogEntry, ControlOperation, ControlOutcome
from squadops.outcomes.aor import (
    BASELINES,
    BASELINES_UNREAD,
    INTERVENTIONS,
    OBJECTIVE,
    ClassReading,
    aor_inputs,
    work_envelope,
)
from squadops.outcomes.campaign_package import campaign_interventions
from squadops.outcomes.ledger import Classification, DeclaredIntervention
from tests.unit.campaigns.test_safety_guarantees import GOOD, _doc

T0 = datetime(2026, 10, 19, 5, 0, tzinfo=UTC)
TIER1 = {"prd_tier": "tier-1", "attendance": "unattended"}


def _package(cid, *, outcome="success", work_class=TIER1, target=3, interventions=None):
    doc = _doc(GOOD)
    doc["campaign"] = {
        "campaign_id": cid,
        "state": "completed" if outcome else "calibrating",
        "outcome": outcome,
        "objective": {"target_accepted_increments": target, "work_class": work_class},
    }
    doc["interventions"] = (
        interventions
        if interventions is not None
        else {"entries": [], "unclassified": [], "orphaned": []}
    )
    return doc


def _value(read, name):
    return {n: v for n, v, _ in read.inputs}[name]


@pytest.mark.parametrize(
    ("change", "name", "value"),
    [
        ({"outcome": "exhausted"}, OBJECTIVE, False),
        (
            {"interventions": {"entries": [], "unclassified": ["ent_1"], "orphaned": []}},
            INTERVENTIONS,
            None,
        ),
        (
            {
                "interventions": {
                    "entries": [{"severity": "recovery"}],
                    "unclassified": [],
                    "orphaned": [],
                }
            },
            INTERVENTIONS,
            False,
        ),
        (
            {
                "interventions": {
                    "entries": [{"severity": "advisory"}],
                    "unclassified": [],
                    "orphaned": [],
                }
            },
            INTERVENTIONS,
            True,
        ),
    ],
    ids=["an-exhausted-campaign", "an-unclassified-intervention", "a-recovery", "only-advisory"],
)
def test_each_input_reads_true_false_or_unread(change, name, value):
    """§4.6. Bug caught: an exhausted campaign read as reaching its objective, an unclassified
    intervention read as advisory, or a recovery read as no intervention at all."""
    assert _value(aor_inputs(_package("cmp_1", **change)), name) is value


def test_in_phase_1_every_campaign_is_unread_on_its_baselines_never_reliable():
    """§10f: *held* waits for prediction 4's tolerance. Bug caught: a campaign counted reliable
    with its baselines never read, the rate built on a measure that didn't run."""
    read = aor_inputs(_package("cmp_1"))

    assert {n: v for n, v, _ in read.inputs} == {
        OBJECTIVE: True,
        INTERVENTIONS: True,
        BASELINES: None,
        "every safety guarantee intact": True,
    }
    assert dict((n, w) for n, _, w in read.inputs)[BASELINES] == BASELINES_UNREAD
    assert read.reliable is None and read.work_class == ("tier-1", "unattended", 3)


def test_the_envelope_groups_by_declared_class_and_names_every_unread_campaign():
    """§4.6: classes compare only when declared the same. Bug caught: two classes pooled into one
    rate, a campaign with no class grouped with a declared one, or a campaign still running
    counted."""
    packages = [
        _package("cmp_a"),
        _package("cmp_b", outcome="exhausted"),
        _package("cmp_c", work_class={"prd_tier": "core", "attendance": "attended"}),
        _package("cmp_d", work_class=None),
        _package("cmp_open", outcome=None),
    ]

    readings = work_envelope(packages)

    assert [(r.work_class, r.campaigns) for r in readings] == [
        (("core", "attended", 3), ("cmp_c",)),
        (("tier-1", "unattended", 3), ("cmp_a", "cmp_b")),
        (None, ("cmp_d",)),
    ]
    tier1 = readings[1]
    assert (tier1.not_reliable, tier1.rate) == (("cmp_b",), None)
    assert tier1.unread == (("cmp_a", (BASELINES,)),)


@pytest.mark.parametrize(
    ("unread", "rate"),
    [((), 2 / 3), ((("cmp_c", (BASELINES,)),), None)],
    ids=["all-read", "one-unread"],
)
def test_a_class_has_a_rate_only_once_every_campaign_in_it_is_read(unread, rate):
    reading = ClassReading(
        work_class=("tier-1", "unattended", 3),
        campaigns=("cmp_a", "cmp_b", "cmp_c"),
        reliable=("cmp_a", "cmp_b"),
        not_reliable=() if unread else ("cmp_c",),
        unread=unread,
    )

    assert reading.rate == rate


async def test_the_packages_interventions_carry_each_severity_and_the_gaps():
    """§4.3 into the package. Bug caught: a classified row's severity lost on the way, a declared
    action outside the interface left out, or an unclassified row read as none at all."""
    store = MemoryInterventionLedger()

    def row(entry_id, op, role="admin", **binding):
        return ControlLogEntry(
            entry_id=entry_id,
            campaign_id="cmp_1",
            seq=1,
            operation=op,
            actor="owner",
            actor_role=role,
            reason="r",
            target=None,
            idempotency_key=entry_id,
            request_hash="h",
            binding=binding,
            outcome=ControlOutcome.APPLIED,
            refusal=None,
            prior_state=None,
            next_state="paused",
            committed_at=T0,
        )

    log = [row("ent_pause", ControlOperation.PAUSE), row("ent_resume", ControlOperation.RESUME)]
    await store.save_classification(
        Classification("ent_pause", "cmp_1", "environment", "advisory", "supervisor", T0)
    )
    await store.save_declared(
        DeclaredIntervention(
            "dcl_1", "cmp_1", "environment", "recovery", "restarted the runtime", T0, "owner", T0
        )
    )

    section = await campaign_interventions(store, "cmp_1", log)

    assert [(e["entry_id"], e["severity"]) for e in section["entries"]] == [
        ("ent_pause", "advisory"),
        ("ent_resume", None),
        (None, "recovery"),
    ]
    assert section["unclassified"] == ["ent_resume"]
