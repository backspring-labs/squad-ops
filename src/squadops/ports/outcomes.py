"""Outcome Evaluation's store for its readings beside scenarios (SIP-0113 §4.3; #2417): the
intervention ledger's classifications and declared entries. Never a control-log row: those stay
SIP-0109's, and the ledger projects them.

And what a proposal run is shown of its accepted tree (§4.5, §10t ruling 1): the executor asks
``ProposalEvidencePort``, so it never imports the held-out store the evidence is read from."""

from __future__ import annotations

from abc import ABC, abstractmethod

from squadops.outcomes.ledger import Classification, DeclaredIntervention
from squadops.outcomes.proposal_evidence import ProposalEvidence


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


class ProposalEvidencePort(ABC):
    @abstractmethod
    async def for_proposal(self, *, campaign_id: str, accepted_cycle_id: str) -> ProposalEvidence:
        """What a proposal on ``accepted_cycle_id``'s tree is shown. An empty answer means there is
        nothing to show. A read that fails raises (§10t ruling 6), and the proposal run fails with
        it: a proposal is never dispatched without its evidence."""
