"""SIP-0109 §24cd point 1: the launcher reads the campaign branch's head at drain and hands it to
cycle creation, entering at ``CampaignLaunchService.drain()`` as the runtime's sweep calls it.

A repository-backed Campaign's cycle runs on the shared fixture's Project (Tally), with the
create path's own ``prepare_cycle``. A sample application's runs on the config registry's
``group_run``, as every Campaign so far has.

The repository-backed campaigns here propose with the stack-less ``validate`` profile, standing
in for H.4's source-backed increment profile (the MacBook lane's recipe, not built yet): the
template stack of ``campaign-increment`` is refused for a source-backed cycle at preflight,
before the head is read.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cycles.factory import create_project_registry, create_squad_profile_port
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api import campaign_launch
from squadops.api.campaign_launch import CampaignLaunchService
from squadops.api.routes.cycles.cycles import CreationPorts
from squadops.campaigns.campaign_branch import CampaignHead
from squadops.campaigns.launch_requests import (
    bound_at_head,
    bound_launch,
    increment_launch,
)
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    CycleKind,
    LaunchIntentState,
    LaunchRequest,
)
from squadops.contracts.cycle_request_profiles import cycle_request_body
from squadops.cycles.models import AgentProfileEntry, Project, SquadProfile
from squadops.projects.baseline import parse_baseline
from squadops.projects.derived_profile import parse_profile
from squadops.projects.models import ProjectLifecycleStatus, ProjectSource
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.campaigns.builders import campaign, move, policy, quiet_box

S = CampaignState
CID = "cmp_headdrain001"
_CONTEXT = recorded("project_source_context", "valid")
#: The Project's baseline commit: where the calibration record leaves the campaign branch.
_BASE = _CONTEXT["development_baseline_commit"]
#: An accepted increment's captured commit, the branch's head after its promotion.
_HEAD = "a1" * 20
_HEAD_TREE = "d" * 64
_RECORD_TREE = "e" * 64
_VERIFICATION = "art_verifyhead01"


class _Executor:
    async def execute_cycle(self, *_args, **_kwargs) -> None:
        return None


class _Deploys:
    async def latest(self):
        return None


class _Vault:
    """The vault, holding the source verification that made the head: an accepted one of the
    head's own tree, as ``require_campaign_head`` reads it."""

    async def retrieve(self, artifact_id):
        if artifact_id != _VERIFICATION:
            raise KeyError(artifact_id)
        ref = SimpleNamespace(artifact_type="source_verification")
        document = {"verdict": "accepted", "candidate_tree_identity": _HEAD_TREE}
        return ref, json.dumps(document).encode()


def _tally() -> Project:
    return Project(
        project_id=_CONTEXT["project_id"],
        name="Tally",
        description="the shared fixture",
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
        lifecycle_status=ProjectLifecycleStatus.READY,
        record_version=_CONTEXT["record_version"],
        source=ProjectSource(_CONTEXT["repo_uri"], "refs/heads/main", "review_request"),
        development_configuration_revision=_CONTEXT["development_configuration_revision"],
        development_baseline_commit=_BASE,
        integrated_upstream_commit=_CONTEXT["integrated_upstream_commit"],
    )


def _squad() -> SquadProfile:
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
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
    )


def _repository_ports(cycles: MemoryCycleRegistry) -> CreationPorts:
    registry = AsyncMock()
    registry.get_project.return_value = _tally()
    registry.list_projects.return_value = [_tally()]
    registry.get_inherited_baseline.return_value = parse_baseline(
        recorded("inherited_baseline", "valid")
    )
    registry.get_derived_profile.return_value = parse_profile(recorded("derived_profile", "valid"))
    registry.source_syncs.return_value = []
    squads = AsyncMock()
    squads.resolve_snapshot.return_value = (_squad(), "sha256:abc")
    return CreationPorts(
        project_registry=registry,
        squad_profile=squads,
        cycle_registry=cycles,
        deploy_registry=_Deploys(),
        artifact_vault=_Vault(),
    )


def _sample_ports(cycles: MemoryCycleRegistry) -> CreationPorts:
    return CreationPorts(
        project_registry=create_project_registry("config"),
        squad_profile=create_squad_profile_port("config"),
        cycle_registry=cycles,
        deploy_registry=_Deploys(),
    )


def _service(campaigns, ports: CreationPorts) -> CampaignLaunchService:
    return CampaignLaunchService(
        campaigns=campaigns,
        creation=ports,
        flow_executor=_Executor(),
        event_bus=MagicMock(),
        box_verdict=quiet_box,
    )


def _block(request_or_body: dict) -> dict:
    return request_or_body["body"]["execution_overrides"]["campaign_proposal"]


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


@pytest.fixture
def heads(monkeypatch) -> list:
    """Each ``campaign_head`` the launcher hands ``prepare_cycle``, beside what it creates."""
    seen: list = []
    real = campaign_launch.prepare_cycle

    async def recording(*args, **kwargs):
        seen.append(kwargs.get("campaign_head"))
        return await real(*args, **kwargs)

    monkeypatch.setattr(campaign_launch, "prepare_cycle", recording)
    return seen


async def _repository_campaign(accepted: AcceptedTree, verification: str | None):
    """A repository-backed campaign whose branch is at ``accepted``, promoted by a row naming its
    commit and the verification that made it, as ``CampaignProgress`` writes one."""
    reg = MemoryCampaignRegistry()
    on_tally = campaign(CID, project_id=_CONTEXT["project_id"], policy=policy(
        proposal_profile="validate"
    ))  # fmt: skip
    await reg.create_campaign(
        on_tally, actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    await reg.transition(CID, move(S.CALIBRATING, "k-start", operation=ControlOperation.START))
    await reg.transition(CID, move(S.ESCALATED, "k-hold"))
    await reg.transition(
        CID,
        move(
            S.PROMOTING,
            "k-promote",
            operation=ControlOperation.PROMOTE,
            accepted=accepted,
            binding={
                **({"commit": accepted.commit} if accepted.commit else {}),
                **({"verification_ref": verification} if verification else {}),
            },
        ),
    )
    return reg, await reg.get_campaign(CID)


def _proposal_on_record() -> LaunchRequest:
    """The increment a proposal on the calibration record's commit writes: §24bv point 5's, the
    MacBook lane's, not built yet. ``increment_launch`` refuses a record's tree, so it is written
    as point 5 will write it: a block that binds no tree."""
    return LaunchRequest(
        CycleKind.INCREMENT,
        {
            "body": cycle_request_body(
                "validate",
                squad_profile_id="full-38",
                user_values={"campaign_proposal": {"proposal_id": "prop_onrecord01", "version": 1}},
                notes="an increment on the calibration record",
            )
        },
    )


@pytest.mark.parametrize(
    ("accepted", "verification", "pinned"),
    [
        (
            AcceptedTree(_HEAD_TREE, cycle_id="cyc_increment01", commit=_HEAD),
            _VERIFICATION,
            (_HEAD, "campaign_branch", _VERIFICATION),
        ),
        (
            AcceptedTree(_RECORD_TREE, calibration_record_id="cal_tally00001", commit=_BASE),
            None,
            (_BASE, "campaign_branch", None),
        ),
    ],
    ids=["after an accepted increment", "at the calibration record's commit"],
)
async def test_a_repository_backed_increment_is_pinned_at_the_head_read_at_drain(
    heads, accepted, verification, pinned
):
    """Entry: ``drain()``. Bugs caught: the head never handed to ``prepare_cycle``, so every
    repository-backed increment is refused; the head read from anything but the row and its
    PROMOTE (the verification lost); the intent's tree bound at the decision instead of the
    head's at drain; the Project's baseline overwritten by the head."""
    campaigns, at_head = await _repository_campaign(accepted, verification)
    launch = (
        increment_launch(at_head, baseline_manifest="")
        if accepted.cycle_id
        else _proposal_on_record()
    )
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-propose", launch=launch))
    cycles = MemoryCycleRegistry()

    await _service(campaigns, _repository_ports(cycles)).drain()

    [intent] = await campaigns.launch_intents(CID)
    assert intent.state is LaunchIntentState.LAUNCHED
    assert "baseline_tree" not in _block(intent.cycle_request)  # the intent binds no tree
    cycle = await cycles.get_cycle(intent.cycle_id)
    context = cycle.source_context
    assert (context.pinned_commit, context.pinned_from, context.previous_verification_ref) == pinned
    assert context.development_baseline_commit == _BASE  # H.2's gate still keys on it
    assert cycle.resolved_config()["campaign_proposal"]["baseline_tree"] == accepted.identity
    assert heads == [CampaignHead(accepted.commit, accepted.identity, verification)]


async def test_a_repository_backed_launch_with_no_head_escalates_and_creates_no_cycle(heads):
    """The edge: the campaign's accepted tree names no commit (nothing promoted onto a branch).
    Bugs caught: the increment defaulted to the Project's baseline; the refusal repeated on every
    drain instead of escalating, since no re-drain gives the campaign a head."""
    campaigns, at = await _repository_campaign(
        AcceptedTree("f" * 64, cycle_id="cyc_increment01"), None
    )
    launch = increment_launch(at, baseline_manifest="")
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-propose", launch=launch))
    cycles = MemoryCycleRegistry()

    await _service(campaigns, _repository_ports(cycles)).drain()

    [intent] = await campaigns.launch_intents(CID)
    assert intent.state is LaunchIntentState.PENDING
    assert await cycles.list_cycles(_CONTEXT["project_id"]) == []
    after = await campaigns.get_campaign(CID)
    assert after.state is CampaignState.ESCALATED
    refused = (await campaigns.control_log(CID))[-1]
    assert refused.operation is ControlOperation.LAUNCH_REFUSED
    assert refused.binding["refusal"].startswith("PROJECT_STATE_CONFLICT: ")
    assert "its launch names none" in refused.binding["refusal"]
    assert heads == [None]


async def test_a_repair_built_on_a_tree_the_head_moved_past_escalates(heads):
    """The edge: a repair whose bound tree is no longer the head. Bug caught: it launched on the
    head with a candidate built on the old tree, so its capture would revert what moved the head
    (§24bv point 2)."""
    campaigns, at_head = await _repository_campaign(
        AcceptedTree(_HEAD_TREE, cycle_id="cyc_increment01", commit=_HEAD), _VERIFICATION
    )
    block = {
        "proposal_id": "prop_repaired01",
        "version": 1,
        "baseline_tree": "c" * 64,
        "continues": "cyc_failed00001",
        "repair_of": "cyc_failed00001",
    }
    repair = bound_launch(at_head, CycleKind.REPAIR, block, [], None)
    await campaigns.transition(CID, move(S.ESCALATED, "k-hold-2"))
    await campaigns.transition(CID, move(S.REPAIRING, "k-repair", launch=repair))
    cycles = MemoryCycleRegistry()

    await _service(campaigns, _repository_ports(cycles)).drain()

    assert await cycles.list_cycles(_CONTEXT["project_id"]) == []
    refused = (await campaigns.control_log(CID))[-1]
    assert refused.operation is ControlOperation.LAUNCH_REFUSED
    assert refused.binding["refusal"] == (
        f"VALIDATION_ERROR: the repair is bound to tree {'c' * 12}, and the campaign branch's "
        f"head is {_HEAD[:12]}, tree {_HEAD_TREE[:12]}: a launch is built on the head "
        "(SIP-0109 §24cd point 1)"
    )
    assert heads == []  # refused before cycle creation


async def test_a_sample_applications_increment_launches_as_it_did_with_no_head(heads):
    """A sample application's campaign is unchanged (§24cd point 1). Bugs caught: its tree, the
    vault's, unbound from its intent; a head invented for a tree that names no commit, which
    ``prepare_cycle`` would refuse for a Project with no source."""
    campaigns = MemoryCampaignRegistry()
    await campaigns.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create-1"
    )
    at_base = campaign(
        CID, accepted=AcceptedTree(identity="tree_base0001", cycle_id="cyc_base0001")
    )
    increment = increment_launch(at_base, baseline_manifest="the accepted manifest")
    await campaigns.transition(CID, move(S.CALIBRATING, "k-cal"))
    await campaigns.transition(CID, move(S.AT_PROPOSAL, "k-inc", launch=increment))
    cycles = MemoryCycleRegistry()

    await _service(campaigns, _sample_ports(cycles)).drain()

    [intent] = await campaigns.launch_intents(CID)
    assert intent.state is LaunchIntentState.LAUNCHED
    cycle = await cycles.get_cycle(intent.cycle_id)
    assert cycle.source_context is None
    assert cycle.resolved_config()["campaign_proposal"] == _block(increment.cycle_request)
    assert _block(increment.cycle_request)["baseline_tree"] == "tree_base0001"
    assert heads == [None]


_AT = CampaignHead(_HEAD, _HEAD_TREE, _VERIFICATION)


def _request(block: dict | None) -> dict:
    overrides = {"campaign_proposal": block} if block is not None else {}
    return {"body": {"squad_profile_id": "full", "execution_overrides": overrides}}


@pytest.mark.parametrize(
    ("kind", "block", "head", "bound"),
    [
        (CycleKind.INCREMENT, {"proposal_id": "p"}, None, None),
        (CycleKind.CALIBRATION, None, _AT, None),
        (CycleKind.INCREMENT, {"proposal_id": "p"}, _AT, _HEAD_TREE),
        (CycleKind.INCREMENT, {"proposal_id": "p", "baseline_tree": _HEAD_TREE}, _AT, _HEAD_TREE),
        (CycleKind.RETRY, {"proposal_id": "p", "baseline_tree": _HEAD_TREE}, _AT, _HEAD_TREE),
        (CycleKind.INCREMENT, {"proposal_id": "p", "baseline_tree": "c" * 64}, _AT, ValueError),
        (CycleKind.RETRY, {"proposal_id": "p"}, _AT, ValueError),
    ],
    ids=[
        "no head: as written",
        "a calibration: as written",
        "an increment: the head's tree bound",
        "an increment naming the head: kept",
        "a retry on the head: kept",
        "an increment naming another tree: refused",
        "a retry naming no tree: refused",
    ],
)  # fmt: skip
def test_a_launch_is_bound_at_the_head_or_refused(kind, block, head, bound):
    """``bound_at_head``'s every branch. Bugs caught: a sample application's request changed; a
    continuation re-bound to the head it wasn't built on, or one naming no tree let through."""
    request = _request(block)
    if bound is ValueError:
        with pytest.raises(ValueError, match="a launch is built on the head"):
            bound_at_head(kind, request, head)
        return
    result = bound_at_head(kind, request, head)
    if bound is None:
        assert result is request
        return
    assert _block(result) == {**block, "baseline_tree": bound}
    assert block.get("baseline_tree") in (None, bound)  # the written intent isn't mutated


def test_a_branch_trees_increment_intent_binds_no_tree_and_a_sample_applications_does():
    """``increment_launch`` (§24cd point 1). Bug caught: a repository-backed intent fixing the tree
    at its decision, which a rebase before the drain makes stale; or a sample application's tree
    unbound, leaving its proposal nothing to bind its ruling to."""
    on_branch = campaign(accepted=AcceptedTree(_HEAD_TREE, cycle_id="cyc_inc", commit=_HEAD))
    in_vault = campaign(accepted=AcceptedTree(_HEAD_TREE, cycle_id="cyc_inc"))

    branch_block = _block(increment_launch(on_branch, "").cycle_request)
    vault_block = _block(increment_launch(in_vault, "m").cycle_request)

    assert "baseline_tree" not in branch_block
    assert vault_block["baseline_tree"] == _HEAD_TREE
    assert set(vault_block) - set(branch_block) == {"baseline_tree"}
