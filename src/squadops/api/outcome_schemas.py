"""The intervention ledger's HTTP shapes (SIP-0113 §4.3; #2417)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ClassificationRequest(BaseModel):
    entry_id: str
    reason: str
    severity: str
    #: "Could the squad have resolved it?": the supervisor's reading, an opinion.
    squad_could_resolve: bool | None = None
    note: str = ""


class DeclaredRequest(BaseModel):
    reason: str
    severity: str
    description: str
    occurred_at: datetime
    squad_could_resolve: bool | None = None


class ClassificationDTO(BaseModel):
    entry_id: str
    reason: str
    severity: str
    squad_could_resolve: bool | None
    note: str
    classified_by: str
    classified_at: datetime


class DeclaredDTO(BaseModel):
    declared_id: str
    reason: str
    severity: str
    description: str
    occurred_at: datetime
    declared_by: str
    declared_at: datetime
    squad_could_resolve: bool | None


class LedgerEntryDTO(BaseModel):
    entry_id: str | None
    operation: str
    actor: str
    at: datetime
    classification: ClassificationDTO | None = None
    declared: DeclaredDTO | None = None


class LedgerResponse(BaseModel):
    campaign_id: str
    entries: list[LedgerEntryDTO]
    #: §7 prediction 5: intervention rows not yet classified, and classifications naming none.
    unclassified: list[str]
    orphaned: list[str]
    matches_the_control_log: bool
