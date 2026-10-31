"""The intervention ledger's store in memory, for tests and a memory-backed deploy."""

from __future__ import annotations

from squadops.outcomes.ledger import Classification, DeclaredIntervention
from squadops.ports.outcomes import InterventionLedgerPort


class MemoryInterventionLedger(InterventionLedgerPort):
    def __init__(self) -> None:
        self._classified: dict[str, Classification] = {}
        self._declared: dict[str, DeclaredIntervention] = {}

    async def save_classification(self, classification: Classification) -> None:
        self._classified[classification.entry_id] = classification

    async def classifications(self, campaign_id: str) -> list[Classification]:
        return [c for c in self._classified.values() if c.campaign_id == campaign_id]

    async def save_declared(self, declared: DeclaredIntervention) -> None:
        if declared.declared_id in self._declared:
            raise ValueError(f"declared intervention {declared.declared_id} is already written")
        self._declared[declared.declared_id] = declared

    async def declared(self, campaign_id: str) -> list[DeclaredIntervention]:
        return [d for d in self._declared.values() if d.campaign_id == campaign_id]
