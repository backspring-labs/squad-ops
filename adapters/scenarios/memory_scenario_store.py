"""The scenario store in memory, for tests and a memory-backed deploy (SIP-0113 §4.1)."""

from __future__ import annotations

from squadops.ports.scenarios import ScenarioStorePort
from squadops.scenarios.evaluation import EvaluationRecord, QualityRemeasure
from squadops.scenarios.models import CampaignSuitePin, SuiteRecord


class MemoryScenarioStore(ScenarioStorePort):
    def __init__(self) -> None:
        self._suites: dict[str, SuiteRecord] = {}
        self._pins: dict[str, CampaignSuitePin] = {}
        self._evaluations: dict[str, EvaluationRecord] = {}
        self._remeasures: dict[tuple[str, str, int], QualityRemeasure] = {}

    async def save_suite(self, record: SuiteRecord) -> None:
        self._suites[record.digest] = record

    async def get_suite(self, digest: str) -> SuiteRecord | None:
        return self._suites.get(digest)

    async def list_suites(self) -> list[SuiteRecord]:
        return sorted(self._suites.values(), key=lambda r: r.drafted_at, reverse=True)

    async def save_pin(self, pin: CampaignSuitePin) -> None:
        if pin.campaign_id in self._pins:
            raise ValueError(f"campaign {pin.campaign_id} is already pinned")
        self._pins[pin.campaign_id] = pin

    async def get_pin(self, campaign_id: str) -> CampaignSuitePin | None:
        return self._pins.get(campaign_id)

    async def save_evaluation(self, record: EvaluationRecord) -> None:
        if record.suite_digest not in self._suites:
            raise ValueError(
                f"no suite {record.suite_digest} for evaluation {record.evaluation_id}"
            )
        if record.evaluation_id in self._evaluations:
            raise ValueError(f"evaluation {record.evaluation_id} is already written")
        self._evaluations[record.evaluation_id] = record

    async def get_evaluation(self, evaluation_id: str) -> EvaluationRecord | None:
        return self._evaluations.get(evaluation_id)

    async def evaluations_for_cycle(self, cycle_id: str) -> list[EvaluationRecord]:
        found = [r for r in self._evaluations.values() if r.cycle_id == cycle_id]
        return sorted(found, key=lambda r: r.evaluated_at)

    async def save_remeasure(self, remeasure: QualityRemeasure) -> None:
        if remeasure.evaluation_id not in self._evaluations:
            raise ValueError(f"no evaluation {remeasure.evaluation_id} to re-measure")
        key = (remeasure.evaluation_id, remeasure.provenance, remeasure.round)
        if key in self._remeasures:
            raise ValueError(f"re-measure {key} is already written")
        self._remeasures[key] = remeasure

    async def remeasures_for_cycle(self, cycle_id: str) -> list[QualityRemeasure]:
        found = [r for r in self._remeasures.values() if r.cycle_id == cycle_id]
        return sorted(found, key=lambda r: (r.provenance, r.round))
