"""The held-out scenario suites' HTTP shapes (SIP-0113 §4.1; #2413).

A summary carries a suite's goals and surfaces, never its steps or checks. The full content
(``SuiteContentResponse``) answers only ``scenarios:approve``: the owner reads what they approve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SuiteDraftRequest(BaseModel):
    """The suite's document, as ``squadops.scenarios.models.parse_suite`` reads it."""

    name: str
    scenarios: list[dict[str, Any]]


class SurfaceDTO(BaseModel):
    kind: str
    path: str
    method: str | None = None


class ScenarioSummaryDTO(BaseModel):
    scenario_id: str
    version: str
    goal: str
    surfaces: list[SurfaceDTO]


class SuiteSummaryResponse(BaseModel):
    digest: str
    name: str
    state: str
    drafted_by: str
    drafted_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None
    scenarios: list[ScenarioSummaryDTO]


class SuiteContentResponse(BaseModel):
    """The suite as drafted, held-out steps and checks included: the owner's review."""

    digest: str
    state: str
    content: dict[str, Any]


class ScenarioEvidenceResponse(BaseModel):
    """A failed or blocked page scenario's evidence (SIP-0113 §10p ruling 8): the owner's alone
    (``scenarios:approve``), since a screenshot of a filled form shows a step's values."""

    scenario_id: str
    step: int
    png_b64: str | None = None
    role: str | None = None
    nodes: list[dict[str, Any]]
    errors: list[str]
    failed_requests: list[str]
    withheld: list[str]
    sha256: str
    size: int


class EvidencePurgeRequest(BaseModel):
    """The cut's purge (§10p ruling 8, cut step 8): every evaluation made before ``before``."""

    before: datetime


class EvidencePurgeResponse(BaseModel):
    before: datetime
    purged: int
