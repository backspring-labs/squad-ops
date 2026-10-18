"""Outcome Evaluation's store for its readings beside scenarios (SIP-0113 §4.3; #2417): the
intervention ledger's classifications and declared entries. Never a control-log row: those stay
SIP-0109's, and the ledger projects them."""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.outcomes.ledger import Classification, DeclaredIntervention


class InterventionLedgerPort(ABC):
    @abstractmethod
    async def save_classification(self, classification: Classification) -> None:
        """Write a row's classification. A later one for the same row revises it."""

    @abstractmethod
    async def classifications(self, campaign_id: str) -> list[Classification]: ...

    @abstractmethod
    async def save_declared(self, declared: DeclaredIntervention) -> None: ...

    @abstractmethod
    async def declared(self, campaign_id: str) -> list[DeclaredIntervention]: ...
