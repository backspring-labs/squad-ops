"""Contract 1 at ``prepare_cycle()`` (SIP-0112 §8.2.1; E.4.3), with the shared fixture's Project.

Entered at the create route and at the Campaign launcher, the two paths a Cycle is prepared by
(IR-2). The fixture's recorded source context is what both must pin. Bugs caught:
- a Cycle of an external product dispatched with no source pinned, or with one read from the
  caller's text rather than the registry;
- a stale precondition accepted and silently re-pinned to the current commit;
- the Campaign launcher pinning something other than the create route pins.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry
from squadops.api.cycle_schemas import CycleCreateRequest
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.cycles import CreationPorts, prepare_cycle, router
from squadops.cycles.models import (
    AgentProfileEntry,
    InheritedBaselineNotFoundError,
    Project,
    SquadProfile,
)
from squadops.projects.baseline import parse_baseline
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from squadops.projects.source_context import parse_source_context
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.campaigns.builders import QuietBox

NOW = datetime(2026, 10, 18, tzinfo=UTC)


def _project(**overrides) -> Project:
    context = recorded("project_source_context", "valid")
    fields = {
        "project_id": context["project_id"],
        "name": "Tally",
        "description": "the shared fixture",
        "created_at": NOW,
        "lifecycle_status": ProjectLifecycleStatus.READY,
        "record_version": context["record_version"],
        "source": ProjectSource(context["repo_uri"], "refs/heads/main", "review_request"),
        "development_configuration_revision": context["development_configuration_revision"],
        "development_baseline_commit": context["development_baseline_commit"],
        "integrated_upstream_commit": context["integrated_upstream_commit"],
    }
    return Project(**{**fields, **overrides})


def _profile():
    roles = [("max", "lead"), ("nat", "strat"), ("neo", "dev"), ("eve", "qa"), ("data", "data")]
    return SquadProfile(
        profile_id="full",
        name="Full",
        description="",
        version=1,
        agents=tuple(
            AgentProfileEntry(agent_id=a, role=r, model="gpt-4", enabled=True, serves_roles=(r,))
            for a, r in roles
        ),
        created_at=NOW,
    )


@pytest.fixture
def ports():
    registry = AsyncMock()
    registry.get_project.return_value = _project()
    registry.get_inherited_baseline.return_value = parse_baseline(
        recorded("inherited_baseline", "valid")
    )
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (_profile(), "sha256:abc")
    return CreationPorts(
        project_registry=registry,
        squad_profile=profiles,
        cycle_registry=MemoryCycleRegistry(),
        deploy_registry=MemoryDeployRegistry(),
    )


@pytest.fixture
def client(ports, monkeypatch):
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")
    app = FastAPI()
    app.include_router(router)
    register_domain_error_handlers(app)
    app.state.project_registry = ports.project_registry
    app.state.cycle_registry = ports.cycle_registry
    app.state.deploy_registry = ports.deploy_registry
    app.state.squad_profile = ports.squad_profile
    app.state.flow_executor = AsyncMock()
    app.state.box_reader = QuietBox()
    return TestClient(app)


def test_the_create_route_pins_the_fixtures_recorded_source_context(client):
    resp = client.post("/api/v1/projects/prj-tally/cycles", json={"squad_profile_id": "full"})

    assert resp.status_code == 201, resp.json()
    assert resp.json()["source_context"] == recorded("project_source_context", "valid")


def test_a_stale_precondition_is_refused_never_re_pinned(client):
    stale = recorded("project_source_context", "stale_commit")

    resp = client.post(
        "/api/v1/projects/prj-tally/cycles",
        json={
            "squad_profile_id": "full",
            "source_precondition": {
                "development_baseline_commit": stale["development_baseline_commit"]
            },
        },
    )

    error = resp.json()["detail"]["error"]
    assert (resp.status_code, error["code"]) == (409, "STALE_SOURCE_PRECONDITION")


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"development_configuration_revision": None}, "PROJECT_STATE_CONFLICT"),
        ({"development_baseline_commit": None}, "PROJECT_STATE_CONFLICT"),
        ({"lifecycle_status": ProjectLifecycleStatus.REGISTERING}, "PROJECT_NOT_READY"),
    ],
    ids=["unconfigured", "never-reached", "registering"],
)
def test_a_project_not_ready_for_development_is_refused(client, ports, overrides, code):
    ports.project_registry.get_project.return_value = _project(**overrides)

    resp = client.post("/api/v1/projects/prj-tally/cycles", json={"squad_profile_id": "full"})

    assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (409, code)


@pytest.mark.parametrize(
    "baseline",
    [
        None,
        {
            "commit": recorded("project_source_context", "stale_commit")[
                "development_baseline_commit"
            ]
        },
        {"development_configuration_revision": 2},
    ],
    ids=["never-captured", "another-commit", "another-revision"],
)
def test_a_cycle_without_the_baseline_of_its_pin_is_refused_before_dispatch(
    client, ports, baseline
):
    """FR-20, FR-09. Bug caught: a source-backed Cycle dispatched with no baseline at its pin,
    whose hours of work could then only end in a candidate nothing can be compared with."""
    if baseline is None:
        ports.project_registry.get_inherited_baseline.side_effect = InheritedBaselineNotFoundError(
            "none"
        )
    else:
        ports.project_registry.get_inherited_baseline.return_value = parse_baseline(
            {**recorded("inherited_baseline", "valid"), **baseline}
        )

    resp = client.post("/api/v1/projects/prj-tally/cycles", json={"squad_profile_id": "full"})

    error = resp.json()["detail"]["error"]
    assert (resp.status_code, error["code"]) == (409, "PROJECT_STATE_CONFLICT")
    assert "capture the baseline there first" in error["message"]
    assert ports.cycle_registry._cycles == {}


@pytest.mark.parametrize(
    "overrides",
    [{"build_profile": "fullstack_fastapi_react"}, {"contract_ref": "contracts/x.yaml"}],
    ids=["build-profile", "contract-ref"],
)
def test_a_cycle_of_an_external_product_naming_a_stack_is_refused(client, overrides):
    """SIP-0112 E.4.3. Bug caught: a stack's skeleton, manifest or seeded contract set beside
    the product's own files, so the squad fills a skeleton instead of changing the product."""
    resp = client.post(
        "/api/v1/projects/prj-tally/cycles",
        json={"squad_profile_id": "full", "execution_overrides": overrides},
    )

    error = resp.json()["detail"]["error"]
    assert (resp.status_code, error["code"]) == (422, "PREFLIGHT_REJECTED")
    assert "develops an external product from its own tree" in error["message"]


async def test_the_campaign_launch_pins_what_the_create_route_pins(ports, monkeypatch):
    """IR-2's preparation half: the launcher's request body, built by the campaign, reaches
    ``prepare_cycle()`` and pins the same source context as a standalone create."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")
    standalone = await prepare_cycle(
        ports, "prj-tally", CycleCreateRequest(squad_profile_id="full")
    )
    launched = await prepare_cycle(
        ports,
        "prj-tally",
        CycleCreateRequest(squad_profile_id="full"),
        campaign_id="cmp_2407a0000001",
        kind="increment",
    )

    assert launched.cycle.source_context == standalone.cycle.source_context
    assert launched.cycle.source_context == parse_source_context(
        recorded("project_source_context", "valid")
    )


def test_the_recorded_bad_forms_are_refused_by_the_reader():
    from squadops.projects.source_context import SourceContextInvalid

    for form in ("missing_field", "unknown_major"):
        with pytest.raises(SourceContextInvalid):
            parse_source_context(recorded("project_source_context", form))
    doc = copy.deepcopy(recorded("project_source_context", "valid"))
    doc["integrated_upstream_commit"] = None
    assert parse_source_context(doc).integrated_upstream_commit is None
