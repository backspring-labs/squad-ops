"""The proposal's outcome evidence, read from the campaign's own records (SIP-0113 §4.5; §10t step 3).

What a campaign's increment proposal is shown of the tree it proposes on (§10t ruling 2):
- **each goal** of the pinned suite, with its result on the accepted tree from that tree's latest
  evaluation by this campaign: ``passed``, ``failed`` or ``not verified``. A ``blocked_unverified``
  outcome loses its reason, and a ``not_applicable`` goal isn't shown;
- **each quality measure** against the calibration's reading, averaged over the pages both records
  measured, since no page's URL is shown. The seeded reading is left out (§10o's S2);
- **the PRD as the accepted increments left it:** their ``prd_delta`` folded by section id, in the
  order they were promoted.

Only ``scenario_id``, ``goal`` and ``result`` are read from an evaluation's outcomes: no step,
check, value or evidence. **A goal that carries one of its suite's markers is held back** and
counted (§10t ruling 3), so a goal quoting a step's value never reaches the proposer.

**Nothing to show is not a failed read.** A campaign with no pinned suite, or an accepted tree its
evaluator wrote no record for, shows no goals. **A read that fails raises** (§10t ruling 6), and so
does a pin naming a suite the store doesn't hold: the proposal run fails, and the campaign proposes
again.

The executor never imports this module. It holds the held-out store, and the composition root
injects it behind ``ProposalEvidencePort``.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from squadops.campaigns.change_request import PrdOp, load_stored_change_request
from squadops.campaigns.increment_tree import built_change_request
from squadops.campaigns.models import ControlOperation, ControlOutcome, CycleKind
from squadops.outcomes.contribution import NotComparable
from squadops.outcomes.proposal_evidence import (
    AcceptedSection,
    GoalEvidence,
    GoalResult,
    ProposalEvidence,
    QualityMove,
)
from squadops.outcomes.quality_deltas import Against, quality_deltas
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort
from squadops.ports.cycles.campaign_registry import CampaignRegistryPort
from squadops.ports.cycles.cycle_registry import CycleRegistryPort
from squadops.ports.outcomes import ProposalEvidencePort
from squadops.ports.scenarios import ScenarioStorePort
from squadops.scenarios.evaluation import Applicability, EvaluationRecord, ScenarioResult
from squadops.scenarios.markers import carries_a_marker, suite_markers

logger = logging.getLogger(__name__)

#: An outcome's result as the proposer is shown it: a blocked one without its reason.
_SHOWN = {
    ScenarioResult.PASSED: GoalResult.PASSED,
    ScenarioResult.FAILED: GoalResult.FAILED,
    ScenarioResult.BLOCKED_UNVERIFIED: GoalResult.NOT_VERIFIED,
}
#: The kinds whose promotion accepts an increment, as against the calibration's baseline.
_INCREMENT_FAMILY = frozenset({CycleKind.INCREMENT, CycleKind.REPAIR, CycleKind.RETRY})
_SEEDED = "seeded:"


class StoredProposalEvidence(ProposalEvidencePort):
    def __init__(
        self,
        *,
        scenarios: ScenarioStorePort,
        campaigns: CampaignRegistryPort,
        cycles: CycleRegistryPort,
        vault: ArtifactVaultPort,
    ) -> None:
        self._scenarios = scenarios
        self._campaigns = campaigns
        self._cycles = cycles
        self._vault = vault

    async def for_proposal(self, *, campaign_id: str, accepted_cycle_id: str) -> ProposalEvidence:
        promoted = await self._promoted(campaign_id)
        calibration = next((c for c, kind in promoted if kind == CycleKind.CALIBRATION), None)
        goals, held_back, quality = await self._outcomes(
            campaign_id, accepted_cycle_id, calibration
        )
        accepted_prd = await self._accepted_prd(
            [c for c, kind in promoted if kind in _INCREMENT_FAMILY]
        )
        return ProposalEvidence(
            goals=goals, quality=quality, accepted_prd=accepted_prd, held_back=held_back
        )

    async def _promoted(self, campaign_id: str) -> list[tuple[str, CycleKind | None]]:
        """Each cycle the campaign promoted, once, in the order of its first applied promotion,
        with the kind its launch gave it."""
        intents = await self._campaigns.launch_intents(campaign_id)
        kinds = {i.cycle_id: i.cycle_kind for i in intents if i.cycle_id}
        rows = sorted(
            (
                e
                for e in await self._campaigns.control_log(campaign_id)
                if e.operation == ControlOperation.PROMOTE and e.outcome == ControlOutcome.APPLIED
            ),
            key=lambda e: e.seq,
        )
        # A calibration record's promotion (§24cc) names no cycle, so it has no evaluation by
        # cycle to compare with: the record's own reading is SIP-0113 §10l's, not built here.
        order = dict.fromkeys(
            str(e.binding.get("cycle_id")) for e in rows if e.binding.get("cycle_id")
        )
        return [(cycle_id, kinds.get(cycle_id)) for cycle_id in order]

    async def _evaluation(
        self, campaign_id: str, cycle_id: str, suite_digest: str
    ) -> EvaluationRecord | None:
        """The cycle's latest evaluation by this campaign against its pinned suite. A reading of
        the same suite written with no campaign never stands in for the campaign's own."""
        held = [
            r
            for r in await self._scenarios.evaluations_for_cycle(cycle_id)
            if r.campaign_id == campaign_id and r.suite_digest == suite_digest
        ]
        return max(held, key=lambda r: r.evaluated_at) if held else None

    async def _outcomes(
        self, campaign_id: str, accepted_cycle_id: str, calibration: str | None
    ) -> tuple[tuple[GoalEvidence, ...], int, tuple[QualityMove, ...]]:
        pin = await self._scenarios.get_pin(campaign_id)
        if pin is None:
            return (), 0, ()
        record = await self._evaluation(campaign_id, accepted_cycle_id, pin.suite_digest)
        if record is None:
            logger.warning(
                "proposal_evidence_unevaluated",
                extra={"campaign_id": campaign_id, "cycle_id": accepted_cycle_id},
            )
            return (), 0, ()
        stored = await self._scenarios.get_suite(pin.suite_digest)
        if stored is None:
            raise LookupError(
                f"campaign {campaign_id} pins suite {pin.suite_digest[:12]}, which the scenario "
                "store doesn't hold"
            )
        markers = list(suite_markers(stored.suite))
        goals: list[GoalEvidence] = []
        held_back = 0
        for outcome in record.outcomes:
            if outcome.applicability == Applicability.NOT_APPLICABLE:
                continue
            if carries_a_marker(outcome.goal, markers):
                held_back += 1
                continue
            result = GoalResult.NOT_VERIFIED if outcome.result is None else _SHOWN[outcome.result]
            goals.append(GoalEvidence(outcome.scenario_id, outcome.goal, result))
        quality: tuple[QualityMove, ...] = ()
        if calibration is not None and calibration != accepted_cycle_id:
            baseline = await self._evaluation(campaign_id, calibration, pin.suite_digest)
            if baseline is not None:
                quality = _quality_moves(record, baseline)
        return tuple(goals), held_back, quality

    async def _accepted_prd(self, cycle_ids: list[str]) -> tuple[AcceptedSection, ...]:
        """The PRD sections the accepted increments added or modified and didn't later retire, in
        the order each was first added."""
        sections: dict[str, str] = {}
        for cycle_id in cycle_ids:
            cycle = await self._cycles.get_cycle(cycle_id)
            runs = await self._cycles.list_runs(cycle_id)
            if not runs:
                continue
            last = max(runs, key=lambda r: r.run_number)
            document = await built_change_request(self._vault, self._cycles, cycle, last)
            if document is None:
                continue
            for section in load_stored_change_request(document).prd_delta:
                if section.op is PrdOp.RETIRE:
                    sections.pop(section.id, None)
                else:
                    sections[section.id] = section.text
        return tuple(AcceptedSection(section_id, text) for section_id, text in sections.items())


def _quality_moves(record: EvaluationRecord, baseline: EvaluationRecord) -> tuple[QualityMove, ...]:
    """Each measure the two records both took, averaged over the pages they both measured, by its
    first appearance. Records that can't be compared show none."""
    try:
        read = quality_deltas(record, baseline, against=Against.BASELINE)
    except NotComparable:
        return ()
    by_measure: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for delta in read.deltas:
        if not delta.measure.startswith(_SEEDED):
            by_measure[delta.measure].append((delta.before, delta.after))
    return tuple(
        QualityMove(
            measure,
            round(sum(b for b, _ in pairs) / len(pairs), 2),
            round(sum(a for _, a in pairs) / len(pairs), 2),
        )
        for measure, pairs in by_measure.items()
    )
