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
import dataclasses
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry
from squadops.api.cycle_schemas import CycleCreateRequest
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.cycles import CreationPorts, prepare_cycle, router
from squadops.campaigns.campaign_branch import CampaignHead
from squadops.cycles.models import (
    AgentProfileEntry,
    InheritedBaselineNotFoundError,
    Project,
    SquadProfile,
    StaleSourcePreconditionError,
)
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import parse_profile
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from squadops.projects.source_context import parse_source_context
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.campaigns.builders import QuietBox

NOW = datetime(2026, 10, 18, tzinfo=UTC)
#: The head a repository-backed Campaign's calibration record leaves: the Project's baseline
#: commit, with no verification before it (SIP-0109 §24cd point 1).
_FIRST_HEAD = CampaignHead(
    recorded("project_source_context", "valid")["development_baseline_commit"], "t" * 64, None
)


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
    # Tally's profile names no blocking gap (contract 8).
    registry.get_derived_profile.return_value = parse_profile(recorded("derived_profile", "valid"))
    registry.source_syncs.return_value = []
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
    ("synced", "refused"),
    [
        ({"relevant": ["instructions"], "changed": {"instructions": ["CONTRIBUTING.md"]}}, True),
        ({"relevant": [], "changed": {"source": ["tally/notes.py"]}}, False),
        (None, False),
    ],
    ids=["instructions-drifted", "source-only", "a-baseline-since-replaced"],
)
async def test_a_sync_that_found_drift_past_the_baseline_holds_new_cycles(
    client, ports, synced, refused
):
    """#2608, the brownfield demonstration's stage 5 probe, entered at the create route and at the
    Campaign launcher. Bugs caught: a Cycle accepted at a baseline a sync already found upstream
    past, with the instructions it relies on changed; source drift alone holding a Cycle whose
    pinned evidence still describes its tree; a sync read against a baseline validation has
    since replaced still holding Cycles."""
    baseline = _project().development_baseline_commit
    read_at = baseline if synced is not None else "e" * 40
    drift = synced or {"relevant": ["instructions"], "changed": {"instructions": ["CLAUDE.md"]}}
    ports.project_registry.source_syncs.return_value = [
        {"baseline_commit": baseline, "upstream_commit": baseline, "drift": None},
        {"baseline_commit": read_at, "upstream_commit": "f" * 40, "drift": drift},
    ]

    resp = client.post("/api/v1/projects/prj-tally/cycles", json={"squad_profile_id": "full"})
    try:
        await prepare_cycle(
            ports, "prj-tally", CycleCreateRequest(squad_profile_id="full"),
            campaign_id="cmp_2407a0000001", kind="increment", campaign_head=_FIRST_HEAD,
        )  # fmt: skip
        launched = None
    except StaleSourcePreconditionError as e:
        launched = str(e)

    if refused:
        error = resp.json()["detail"]["error"]
        assert (resp.status_code, error["code"]) == (409, "STALE_SOURCE_PRECONDITION")
        assert f"upstream is at {'f' * 40}" in error["message"]
        assert "with instructions changed" in error["message"]
        assert launched == error["message"]
        assert ports.cycle_registry._cycles == {}
    else:
        assert resp.status_code == 201, resp.json()
        assert launched is None


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
        campaign_head=_FIRST_HEAD,
    )

    assert standalone.cycle.source_context == parse_source_context(
        recorded("project_source_context", "valid")
    )
    # The first increment is pinned at the head the calibration record leaves, the Project's
    # baseline commit: the same tree, pinned from the campaign branch (H.4).
    assert launched.cycle.source_context == dataclasses.replace(
        standalone.cycle.source_context, pinned_from="campaign_branch"
    )


def test_the_recorded_bad_forms_are_refused_by_the_reader():
    from squadops.projects.source_context import SourceContextInvalid

    for form in ("missing_field", "unknown_major"):
        with pytest.raises(SourceContextInvalid):
            parse_source_context(recorded("project_source_context", form))
    doc = copy.deepcopy(recorded("project_source_context", "valid"))
    doc["integrated_upstream_commit"] = None
    assert parse_source_context(doc).integrated_upstream_commit is None


@pytest.mark.parametrize(
    "policy",
    [
        {"mode": "sequential", "gate": []},
        {"mode": "sequential", "gates": [{"name": "g", "description": "d", "after": ["x"]}]},
    ],
    ids=["policy-key", "gate-key"],
)
def test_a_misspelt_key_inside_the_task_flow_policy_is_refused_never_dropped(client, policy):
    """Contract 2: the create request forbids extras, and so do the models nested in it. Bug
    caught: a gate declared under a misspelt key silently dropped, so the cycle runs ungated."""
    resp = client.post(
        "/api/v1/projects/prj-tally/cycles",
        json={"squad_profile_id": "full", "task_flow_policy": policy},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "extra_forbidden"


_SECOND = recorded("project_source_context", "valid")["development_baseline_commit"]
_HEAD = "a" * 40


class _Verifications:
    """The vault, holding one run's source verification: the record a promotion names."""

    def __init__(self, verdict: str = "accepted", tree: str = "b" * 64) -> None:
        ref = SimpleNamespace(artifact_type="source_verification")
        self.document = {"verdict": verdict, "candidate_tree_identity": tree}
        self.stored = {"art_verification": (ref, json.dumps(self.document).encode())}

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]


@pytest.mark.parametrize(
    ("head", "vault", "refused"),
    [
        (None, None, "its launch names none"),
        (CampaignHead(_HEAD, "b" * 64, None), None, "names no verification"),
        (CampaignHead(_HEAD, "b" * 64, "art_missing"), _Verifications(), "isn't an accepted"),
        (CampaignHead(_HEAD, "b" * 64, "art_verification"), _Verifications("regressed"), "isn't an accepted"),
        (CampaignHead(_HEAD, "c" * 64, "art_verification"), _Verifications(), "isn't an accepted"),
        (CampaignHead(_HEAD, "b" * 64, "art_verification"), _Verifications(), None),
    ],
    ids=[
        "an increment with no head",
        "a head past the baseline with no verification",
        "a verification the vault doesn't hold",
        "a verification that regressed",
        "a verification of another tree",
        "the accepted verification of the head's tree",
    ],
)  # fmt: skip
async def test_an_increment_is_pinned_at_its_campaign_branchs_head_and_its_verification(
    ports, monkeypatch, head, vault, refused
):
    """H.4's increment pin (SIP-0109 §24cd point 1), entered at ``prepare_cycle``, which the
    Campaign launcher calls. Bugs caught: an increment defaulted to the Project's baseline when
    its launch named no head; a head pinned with no regression baseline behind it, or one whose
    verification regressed or describes another tree; the Project's baseline overwritten by the
    head, which would blind H.2's gate."""
    from squadops.cycles.models import ProjectStateConflictError

    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")
    launch = dict(campaign_id="cmp_2407a0000001", kind="increment", campaign_head=head)
    ports = dataclasses.replace(ports, artifact_vault=vault)

    if refused:
        with pytest.raises(ProjectStateConflictError, match=refused):
            await prepare_cycle(
                ports, "prj-tally", CycleCreateRequest(squad_profile_id="full"), **launch
            )
        return
    prepared = await prepare_cycle(
        ports, "prj-tally", CycleCreateRequest(squad_profile_id="full"), **launch
    )
    context = prepared.cycle.source_context
    assert (context.pinned_commit, context.pinned_from, context.previous_verification_ref) == (
        _HEAD,
        "campaign_branch",
        "art_verification",
    )
    assert context.development_baseline_commit == _SECOND
    assert parse_source_context(context.to_document()) == context  # it round-trips as stored


@pytest.mark.parametrize(
    ("change", "read_as"),
    [
        ({}, ("project_baseline", _SECOND, None)),
        ({"pinned_commit": None}, "pinned_commit is a Git commit"),
        ({"pinned_from": "elsewhere"}, "pinned_from is one of"),
        ({"pinned_commit": "c" * 40}, "a project_baseline pin is the development baseline commit"),
    ],
    ids=["a context stored before the pin", "a pin with no commit", "an unknown provenance",
         "a baseline pin elsewhere"],
)  # fmt: skip
def test_the_pin_is_read_as_stored_and_a_context_from_before_it_as_pinned_at_the_baseline(
    change, read_as
):
    """Contract 1's additive fields (H.4). Bugs caught: every Cycle stored before 2.5 unreadable;
    one of the pin's fields missing beside the others read as a default; a baseline pin naming
    another commit."""
    from squadops.projects.source_context import SourceContextInvalid

    doc = copy.deepcopy(recorded("project_source_context", "valid"))
    if change:
        doc.update(change)
    else:
        for key in ("pinned_commit", "pinned_from", "previous_verification_ref"):
            del doc[key]

    if isinstance(read_as, str):
        with pytest.raises(SourceContextInvalid, match=read_as):
            parse_source_context(doc)
        return
    context = parse_source_context(doc)
    assert (
        context.pinned_from,
        context.pinned_commit,
        context.previous_verification_ref,
    ) == read_as
