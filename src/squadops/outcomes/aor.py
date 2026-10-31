"""Autonomous Outcome Reliability and the Autonomous Work Envelope (SIP-0113 §4.6; #2418).

Computed from campaign packages, never stored as a judgement. A campaign counts toward its work
class's AOR when it reached its objective with no intervention above ``advisory``, every quality
baseline held, and every safety guarantee intact. Each of the four reads ``True``, ``False``, or
``None`` when it can't be read, and a campaign with any input unread is never counted reliable:
it is named, with what kept it from being read (§4.6: a measure not run is never counted as held).

The AWE is AOR across the work classes. Classes are compared only when declared the same (the
objective's ``work_class`` with its ``target_accepted_increments``). A campaign stored before the
class existed has none, and is grouped as such. No composite score: each class reports its own
counts, and nothing is averaged across them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from squadops.campaigns.models import CampaignOutcome
from squadops.campaigns.safety_guarantees import all_intact, safety_guarantees
from squadops.outcomes.ledger import InterventionSeverity

#: §4.6's four inputs, in its order.
OBJECTIVE = "reached its objective"
INTERVENTIONS = "no intervention above advisory"
BASELINES = "every quality baseline held"
GUARANTEES = "every safety guarantee intact"

#: Why *every quality baseline held* reads ``None`` in phase 1 (SIP-0113 §10f).
BASELINES_UNREAD = "waits for prediction 4's tolerance, read in the window"


@dataclass(frozen=True)
class AorInputs:
    campaign_id: str
    #: ``(prd_tier, attendance, target increments)``, or ``None`` when none was declared.
    work_class: tuple[str, str, int | None] | None
    inputs: tuple[tuple[str, bool | None, str], ...]

    @property
    def reliable(self) -> bool | None:
        """All four held: ``True``; any failed: ``False``; otherwise ``None``."""
        values = [value for _, value, _ in self.inputs]
        if False in values:
            return False
        if None in values:
            return None
        return True


def _work_class(objective: Mapping[str, Any]) -> tuple[str, str, int | None] | None:
    declared = objective.get("work_class")
    if not declared:
        return None
    return declared["prd_tier"], declared["attendance"], objective.get("target_accepted_increments")


def _interventions(doc: Mapping[str, Any]) -> tuple[bool | None, str]:
    section = doc.get("interventions")
    if not section:
        return None, "the package carries no intervention ledger"
    if section.get("unclassified"):
        return None, f"{len(section['unclassified'])} intervention(s) not yet classified"
    above = [e for e in section["entries"] if e.get("severity") != InterventionSeverity.ADVISORY]
    if above:
        worst = ", ".join(sorted({str(e.get("severity")) for e in above}))
        return False, f"{len(above)} above advisory ({worst})"
    return True, f"{len(section['entries'])} intervention(s), all advisory"


def aor_inputs(doc: Mapping[str, Any]) -> AorInputs:
    """One campaign's four inputs, from its package alone."""
    campaign = doc["campaign"]
    outcome = campaign.get("outcome")
    reached = None if outcome is None else outcome == CampaignOutcome.SUCCESS.value
    intact = all_intact(safety_guarantees(doc))
    interventions, said = _interventions(doc)
    return AorInputs(
        campaign_id=campaign["campaign_id"],
        work_class=_work_class(campaign["objective"]),
        inputs=(
            (OBJECTIVE, reached, f"ended {outcome}" if outcome else "has not ended"),
            (INTERVENTIONS, interventions, said),
            (BASELINES, None, BASELINES_UNREAD),
            (
                GUARANTEES,
                intact,
                {True: "all seven held", False: "one violated", None: "not all read"}[intact],
            ),
        ),
    )


@dataclass(frozen=True)
class ClassReading:
    """One work class's AOR: how many of its campaigns were reliable, not, or unread."""

    work_class: tuple[str, str, int | None] | None
    campaigns: tuple[str, ...]
    reliable: tuple[str, ...]
    not_reliable: tuple[str, ...]
    #: Each unread campaign, with the inputs it couldn't be read on.
    unread: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def rate(self) -> float | None:
        """AOR over the class, or ``None`` while any of its campaigns is unread: an unread campaign
        is neither in the numerator nor safely out of the denominator."""
        if self.unread or not self.campaigns:
            return None
        return len(self.reliable) / len(self.campaigns)


def work_envelope(packages: Iterable[Mapping[str, Any]]) -> tuple[ClassReading, ...]:
    """The AWE: AOR per declared work class, from each campaign's package, classes in a stable
    order (undeclared last). A package of a campaign that hasn't closed takes no part."""
    by_class: dict[Any, list[AorInputs]] = {}
    for doc in packages:
        if doc["campaign"].get("outcome") is None:
            continue
        read = aor_inputs(doc)
        by_class.setdefault(read.work_class, []).append(read)
    readings = []
    for work_class in sorted(by_class, key=lambda c: (c is None, c or ("", "", 0))):
        reads = by_class[work_class]
        readings.append(
            ClassReading(
                work_class=work_class,
                campaigns=tuple(r.campaign_id for r in reads),
                reliable=tuple(r.campaign_id for r in reads if r.reliable is True),
                not_reliable=tuple(r.campaign_id for r in reads if r.reliable is False),
                unread=tuple(
                    (r.campaign_id, tuple(name for name, value, _ in r.inputs if value is None))
                    for r in reads
                    if r.reliable is None
                ),
            )
        )
    return tuple(readings)
