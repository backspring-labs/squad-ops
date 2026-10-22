"""``/api/v1/scenario-suites``: Outcome Evaluation's held-out scenario suites (SIP-0113 §4.1, §4.7;
#2413).

- **read** (``scenarios:read``): a suite's goals, surfaces and state, never its steps or checks;
- **draft** (``scenarios:draft``): the supervisor drafts a suite (the 2.4 plan's D2). The same
  content again is the same suite, so a retry replays;
- **approve** (``scenarios:approve``, the owner alone): approve a suite before any campaign pins
  it, and read its full content, steps included, to approve what was drafted.

No squad agent's role holds any of these scopes, and nothing here supplies a squad task. A
campaign pins its suite at creation (``campaigns.create_campaign``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from squadops.api.errors import http_error
from squadops.api.middleware.auth import require_scopes
from squadops.api.runtime.deps import get_scenario_store
from squadops.api.scenario_schemas import (
    ScenarioSummaryDTO,
    SuiteContentResponse,
    SuiteDraftRequest,
    SuiteSummaryResponse,
    SurfaceDTO,
)
from squadops.auth.models import Identity, Scope
from squadops.ports.scenarios import ScenarioStorePort
from squadops.scenarios.models import ScenarioInvalid, SuiteRecord, parse_suite
from squadops.scenarios.suites import SuiteRefused, approve_suite, draft_suite

router = APIRouter(prefix="/api/v1/scenario-suites", tags=["scenarios"])

_STATUS = {"SUITE_NOT_FOUND": 404, "SUITE_INVALID": 422}


def _actor(identity: Identity | None) -> str:
    return identity.user_id if identity is not None else "system"


def _store(request: Request) -> ScenarioStorePort:
    store = get_scenario_store(request)
    if store is None:
        raise http_error(503, "SCENARIO_STORE_UNAVAILABLE", "the scenario store is not configured")
    return store


def _summary(record: SuiteRecord) -> SuiteSummaryResponse:
    return SuiteSummaryResponse(
        digest=record.digest,
        name=record.suite.name,
        state=record.state.value,
        drafted_by=record.drafted_by,
        drafted_at=record.drafted_at,
        approved_by=record.approved_by,
        approved_at=record.approved_at,
        scenarios=[
            ScenarioSummaryDTO(
                scenario_id=s.scenario_id,
                version=s.version,
                goal=s.goal,
                surfaces=[SurfaceDTO(**surface.as_dict()) for surface in s.surfaces],
            )
            for s in record.suite.scenarios
        ],
    )


@router.post("", status_code=201)
async def draft(
    request: Request,
    body: SuiteDraftRequest,
    identity: Identity | None = Depends(require_scopes(Scope.SCENARIOS_DRAFT)),
) -> SuiteSummaryResponse:
    try:
        suite = parse_suite(body.model_dump())
        record = await draft_suite(
            _store(request), suite, actor=_actor(identity), at=datetime.now(UTC)
        )
    except ScenarioInvalid as e:
        raise http_error(422, "SUITE_INVALID", str(e)) from e
    except SuiteRefused as e:
        raise http_error(_STATUS.get(e.code, 409), e.code, str(e)) from e
    return _summary(record)


@router.get("")
async def list_suites(
    request: Request,
    identity: Identity | None = Depends(require_scopes(Scope.SCENARIOS_READ)),
) -> list[SuiteSummaryResponse]:
    return [_summary(r) for r in await _store(request).list_suites()]


@router.get("/{digest}")
async def get_suite(
    request: Request,
    digest: str,
    identity: Identity | None = Depends(require_scopes(Scope.SCENARIOS_READ)),
) -> SuiteSummaryResponse:
    record = await _store(request).get_suite(digest)
    if record is None:
        raise http_error(404, "SUITE_NOT_FOUND", f"no suite {digest}")
    return _summary(record)


@router.get("/{digest}/content")
async def get_suite_content(
    request: Request,
    digest: str,
    identity: Identity | None = Depends(require_scopes(Scope.SCENARIOS_APPROVE)),
) -> SuiteContentResponse:
    """The full suite, held-out steps included: the owner reads what they approve (D2)."""
    record = await _store(request).get_suite(digest)
    if record is None:
        raise http_error(404, "SUITE_NOT_FOUND", f"no suite {digest}")
    return SuiteContentResponse(
        digest=record.digest, state=record.state.value, content=record.suite.content()
    )


@router.post("/{digest}/approval")
async def approve(
    request: Request,
    digest: str,
    identity: Identity | None = Depends(require_scopes(Scope.SCENARIOS_APPROVE)),
) -> SuiteSummaryResponse:
    try:
        record = await approve_suite(
            _store(request), digest, actor=_actor(identity), at=datetime.now(UTC)
        )
    except SuiteRefused as e:
        raise http_error(_STATUS.get(e.code, 409), e.code, str(e)) from e
    return _summary(record)
