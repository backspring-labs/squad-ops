"""SIP-0112 H.4 point 3, the recipe (H.11): a repository-backed Project's cycle seeds no skeleton.

Entered at ``prepare_cycle``, the one path the create route and the Campaign launcher share, with
the shared fixture's Project and the request a launch builds from its profile. Bugs caught:
- the increment profile a repository-backed Campaign names pinning a stack, so every increment is
  refused at launch (or, with the guard gone, a skeleton laid beside the product's files);
- the guard refusing ``development_profile``, which seeds nothing;
- a seeded manifest deriving and binding a stack's contract on a product's cycle, the route
  around E.4.3's ``contract_ref`` refusal.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from adapters.cycles.memory_deploy_registry import MemoryDeployRegistry
from squadops.api.cycle_schemas import CycleCreateRequest
from squadops.api.routes.cycles.cycles import CreationPorts, prepare_cycle
from squadops.contracts.cycle_request_profiles import cycle_request_body, load_profile
from squadops.cycles.models import (
    AgentProfileEntry,
    PreflightRejectedError,
    Project,
    SquadProfile,
)
from squadops.cycles.preflight import seeds_skeleton
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import parse_profile
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from tests.fixtures.shared_contract.repository import recorded

NOW = datetime(2026, 10, 28, tzinfo=UTC)
_MANIFEST = Path(__file__).resolve().parents[3] / "examples/03_group_run/interface_manifest.yaml"


def _project(*, source: bool = True) -> Project:
    context = recorded("project_source_context", "valid")
    return Project(
        project_id=context["project_id"],
        name="Tally",
        description="the shared fixture",
        created_at=NOW,
        lifecycle_status=ProjectLifecycleStatus.READY,
        record_version=context["record_version"],
        source=(
            ProjectSource(context["repo_uri"], "refs/heads/main", "review_request")
            if source
            else None
        ),
        development_configuration_revision=context["development_configuration_revision"],
        development_baseline_commit=context["development_baseline_commit"],
        integrated_upstream_commit=context["integrated_upstream_commit"],
    )


class _Ref:
    def __init__(self, artifact_id: str, filename: str, artifact_type: str) -> None:
        self.artifact_id, self.filename, self.artifact_type = artifact_id, filename, artifact_type


class _Vault:
    def __init__(self) -> None:
        manifest = _Ref("art_manifest", "interface_manifest.yaml", "interface_manifest")
        self.items = {"art_manifest": (manifest, _MANIFEST.read_bytes())}
        self.stored: list = []

    async def retrieve(self, artifact_id):
        return self.items[artifact_id]

    async def store(self, ref, content):
        self.stored.append(ref)
        return ref


def _ports(project: Project, vault: _Vault | None = None) -> CreationPorts:
    registry = AsyncMock()
    registry.get_project.return_value = project
    registry.get_inherited_baseline.return_value = parse_baseline(
        recorded("inherited_baseline", "valid")
    )
    registry.get_derived_profile.return_value = parse_profile(recorded("derived_profile", "valid"))
    registry.source_syncs.return_value = []
    roles = [("max", "lead"), ("nat", "strat"), ("neo", "dev"), ("eve", "qa"), ("data", "data")]
    squad = SquadProfile(
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
    profiles = AsyncMock()
    profiles.resolve_snapshot.return_value = (squad, "sha256:abc")
    return CreationPorts(
        project_registry=registry,
        squad_profile=profiles,
        cycle_registry=MemoryCycleRegistry(),
        deploy_registry=MemoryDeployRegistry(),
        artifact_vault=vault,
    )


def _request(profile: str, **user_values) -> CycleCreateRequest:
    return CycleCreateRequest(
        **cycle_request_body(profile, squad_profile_id="full", user_values=user_values)
    )


@pytest.fixture(autouse=True)
def _no_sandbox(monkeypatch):
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


@pytest.mark.parametrize(
    ("config", "seeds"),
    [
        ({}, False),
        # a blueprint's conventions shape the prompts and lay down nothing (H.4 point 3)
        ({"development_profile": "fullstack_fastapi_react"}, False),
        ({"build_profile": "fullstack_fastapi_react"}, True),
        ({"contract_ref": "art_contract"}, True),
        (load_profile("campaign-increment-source").defaults, False),
        (load_profile("campaign-increment").defaults, True),
    ],
    ids=["none", "development_profile", "build_profile", "contract_ref", "source", "sample"],
)
def test_a_skeleton_is_seeded_by_a_build_profile_or_a_contract_never_by_conventions(config, seeds):
    assert seeds_skeleton(config) is seeds


async def test_a_product_cycle_on_the_stack_less_increment_profile_is_prepared_pinned():
    prepared = await prepare_cycle(
        _ports(_project()), "prj-tally", _request("campaign-increment-source")
    )

    assert prepared.cycle.source_context is not None
    assert prepared.cycle.request_profile == "campaign-increment-source"
    assert not seeds_skeleton(prepared.cycle.resolved_config())


@pytest.mark.parametrize("kind", ["retry", "repair"])
def test_a_campaign_can_name_the_stack_less_profile_and_its_bound_cycles_run_from_it(kind):
    """The creation rule's own check, and a bound cycle's workloads (SIP-0109 §10a). Bug caught:
    the profile losing its ruling gate or a workload, so a repository-backed Campaign naming it is
    refused at creation, or its retry or repair can't be launched."""
    from squadops.api.routes.campaigns.campaigns import _require_profiles
    from squadops.campaigns.launch_requests import bound_launch
    from squadops.campaigns.models import CycleKind
    from tests.unit.campaigns.builders import campaign, policy

    stackless = policy(proposal_profile="campaign-increment-source")
    _require_profiles(stackless)
    launch = bound_launch(
        campaign(policy=stackless), CycleKind(kind), {"proposal_id": "prop_1"}, ["art_cr"], None
    )

    body = launch.cycle_request["body"]
    assert not seeds_skeleton({**body["applied_defaults"], **body["execution_overrides"]})


async def test_a_product_cycle_on_a_sample_applications_increment_profile_is_refused():
    """The sample applications' profiles keep their stack (§24bs), so a repository-backed
    Campaign naming one is refused at every launch, by name."""
    with pytest.raises(PreflightRejectedError, match=r"names a stack \(`build_profile`\)"):
        await prepare_cycle(_ports(_project()), "prj-tally", _request("campaign-increment"))


async def test_a_product_cycle_that_seeds_a_manifest_is_refused_before_a_contract_is_stored():
    vault = _Vault()

    with pytest.raises(PreflightRejectedError, match="source_backed_seeded_manifest"):
        await prepare_cycle(
            _ports(_project(), vault),
            "prj-tally",
            _request("implement", plan_artifact_refs=["art_manifest"]),
        )
    assert vault.stored == []


async def test_a_sample_applications_seeded_manifest_still_derives_its_contract():
    """#779 unchanged: the refusal is a product's, keyed on the pinned source alone."""
    vault = _Vault()

    prepared = await prepare_cycle(
        _ports(_project(source=False), vault),
        "prj-tally",
        _request("implement", plan_artifact_refs=["art_manifest"]),
    )

    assert prepared.cycle.source_context is None
    assert prepared.cycle.execution_overrides["contract_ref"] == vault.stored[0].artifact_id
