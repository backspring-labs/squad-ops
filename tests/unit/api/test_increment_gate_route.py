"""The increment ruling through the existing gate path (SIP-0109 §9.2, §13; #1801).

``POST /api/v1/projects/{p}/cycles/{c}/runs/{r}/gates/progress_increment_ruling``, entered at the HTTP
surface with the real authorization adapter, over the memory registries. The campaign is at the
gate with a submitted proposal; what each ruling leaves on the campaign and on the run is read
back.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.memory_campaign_registry import MemoryCampaignRegistry
from adapters.cycles.memory_cycle_registry import MemoryCycleRegistry
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles import runs_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.gate import INCREMENT_RULING_GATE, submission
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ProposalBinding,
    SubmittedProposal,
)
from squadops.cycles.models import Cycle, Gate, Run, TaskFlowPolicy
from tests.unit.campaigns.builders import campaign, move

pytestmark = pytest.mark.auth

NOW = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
CID = "cmp_route0000001"
BINDING = {
    "proposal_id": "prop_cap",
    "version": 1,
    "content_hash": "hash-cap-v1",
    "baseline_tree": "sha-accepted",
}
_GATES = (
    Gate(INCREMENT_RULING_GATE, "the supervisor's ruling", ()),
    Gate("progress_plan_review", "the plan review", ()),
)


def _identity(role: str) -> Identity:
    return Identity(
        user_id=f"user-{role}",
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.HUMAN,
    )


class _World:
    def __init__(self) -> None:
        self.campaigns = MemoryCampaignRegistry()
        self.cycles = MemoryCycleRegistry()
        self.identity = _identity(Role.CAMPAIGN_SUPERVISOR)
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(runs_router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        app.state.cycle_registry = self.cycles
        app.state.artifact_vault = AsyncMock()
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def rule(self, gate: str = INCREMENT_RULING_GATE, **body):
        payload = {
            "decision": "approved",
            "notes": "the footprint stays inside the create view",
            "binding": BINDING,
            "idempotency_key": "rule-1",
            **body,
        }
        return self.client.post(
            f"/api/v1/projects/group_run/cycles/cyc_inc/runs/run_prop/gates/{gate}",
            json={k: v for k, v in payload.items() if v is not None},
        )

    async def gate_decisions(self) -> list[tuple[str, str]]:
        run = await self.cycles.get_run("run_prop")
        return [(d.gate_name, d.decision) for d in run.gate_decisions]


@pytest.fixture
async def world() -> _World:
    w = _World()
    await w.campaigns.create_campaign(
        campaign(CID), actor="owner", actor_role="owner", reason="r", idempotency_key="create"
    )
    await w.campaigns.transition(CID, move(CampaignState.CALIBRATING, "cal"))
    await w.campaigns.transition(
        CID,
        move(
            CampaignState.CALIBRATING,
            "promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-accepted", "cyc_cal"),
        ),
    )
    await w.campaigns.transition(CID, move(CampaignState.AT_PROPOSAL, "propose"))
    await w.campaigns.transition(
        CID,
        submission(
            CampaignState.AT_PROPOSAL,
            SubmittedProposal(ProposalBinding(**BINDING), "cyc_inc", "run_prop"),
        ),
    )
    await w.cycles.create_cycle(
        Cycle(
            cycle_id="cyc_inc",
            project_id="group_run",
            created_at=NOW,
            created_by="launcher",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential", gates=_GATES),
            build_strategy="fresh",
            campaign_id=CID,
            kind="increment",
        )
    )
    await w.cycles.create_run(
        Run(
            run_id="run_prop",
            cycle_id="cyc_inc",
            run_number=1,
            status="completed",
            initiated_by="system",
            resolved_config_hash="cfg",
            workload_type="proposal",
        )
    )
    return w


@pytest.mark.parametrize(
    ("role", "gate", "status"),
    [
        (Role.CAMPAIGN_SUPERVISOR, INCREMENT_RULING_GATE, 200),
        (Role.ADMIN, INCREMENT_RULING_GATE, 200),
        # An operator writes cycles, and never rules an increment.
        (Role.OPERATOR, INCREMENT_RULING_GATE, 403),
        (Role.CAMPAIGN_TRIAGE, INCREMENT_RULING_GATE, 403),
        # The supervisor rules the increment gate, and writes no other.
        (Role.CAMPAIGN_SUPERVISOR, "progress_plan_review", 403),
    ],
)
async def test_the_increment_gate_is_the_supervisors_and_only_that_gate(world, role, gate, status):
    """The owner's ruling (10-02): the supervisor rules at the increment gate, with no cycle
    writes. Bug caught: the gate route's cycles:write letting an operator approve an increment,
    or campaigns:supervise opening every gate."""
    world.identity = _identity(role)
    body = {} if gate == INCREMENT_RULING_GATE else {"binding": None, "idempotency_key": None}
    assert world.rule(gate, **body).status_code == status


async def test_a_stale_ruling_is_refused_recorded_and_decides_nothing(world):
    """§19 criterion 5: no increment builds without a ruling bound to its current proposal.
    Bug caught: the gate decision recorded before (or despite) the binding check — the executor
    would build on it."""
    resp = world.rule(binding={**BINDING, "content_hash": "hash-edited"})

    log = await world.campaigns.control_log(CID)
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["details"]["refusal"] == "stale_binding"
    assert (log[-1].operation, log[-1].refusal) == ("rule", "stale_binding")
    assert await world.gate_decisions() == []


async def test_an_approval_records_one_row_and_one_decision_and_a_repeat_neither(world):
    first = world.rule()
    again = world.rule()

    rules = [e for e in await world.campaigns.control_log(CID) if e.operation == "rule"]
    assert (first.status_code, again.status_code) == (200, 200)
    assert len(rules) == 1
    assert rules[0].actor == "user-campaign-supervisor"
    assert await world.gate_decisions() == [(INCREMENT_RULING_GATE, "approved")]
    assert (await world.campaigns.get_campaign(CID)).state is CampaignState.BUILDING


@pytest.mark.parametrize(
    ("gate", "body", "message"),
    [
        (INCREMENT_RULING_GATE, {"binding": None}, "requires binding"),
        (INCREMENT_RULING_GATE, {"notes": " "}, "the ruling's reason"),
        (INCREMENT_RULING_GATE, {"waived_checks": ["tests_pass"]}, "takes no waiver"),
        ("progress_plan_review", {}, "belong to the progress_increment_ruling gate only"),
        # SIP-0109 §24bi (the 2.2 plan's D2): a return names what went wrong, or says none fits.
        (
            INCREMENT_RULING_GATE,
            {"decision": "returned_for_revision"},
            "carries its classification",
        ),
        (INCREMENT_RULING_GATE, {"decision": "rejected"}, "carries its classification"),
        (
            INCREMENT_RULING_GATE,
            {"decision": "rejected", "classification": "unclassified"},
            "carries a rationale",
        ),
        (
            INCREMENT_RULING_GATE,
            {"decision": "returned_for_revision", "classification": "bad_luck"},
            "unknown classification",
        ),
        (INCREMENT_RULING_GATE, {"classification": "scope_too_large"}, "carries none"),
    ],
)
async def test_a_malformed_ruling_is_a_422_and_records_nothing(world, gate, body, message):
    """Bugs caught for §24bi: a return recorded with no class, so Cross-Cycle Memory observes it
    as unclassified with nothing to say why (SIP-0110 §0.4); a novel defect forced into a class by
    a vocabulary with no way out; or a class on an approval, which has nothing wrong to name."""
    world.identity = _identity(Role.ADMIN)
    resp = world.rule(gate, **body)

    assert resp.status_code == 422
    assert message in resp.json()["detail"]["error"]["message"]
    assert await world.gate_decisions() == []
    log = await world.campaigns.control_log(CID)
    assert not [e for e in log if e.operation is ControlOperation.RULE]


@pytest.mark.parametrize(
    ("body", "recorded"),
    [
        (
            {"decision": "returned_for_revision", "classification": "scope_too_large"},
            {"classification": "scope_too_large"},
        ),
        (
            {
                "decision": "rejected",
                "classification": "unclassified",
                "classification_rationale": "the delta names a route the manifest forbids",
            },
            {
                "classification": "unclassified",
                "classification_rationale": "the delta names a route the manifest forbids",
            },
        ),
        ({"decision": "approved"}, {}),
    ],
)
async def test_a_returns_classification_rides_its_ruling_row(world, body, recorded):
    """§24bi, entered at the gate route. Bug caught: the class accepted and then dropped, so the
    ledger and Cross-Cycle Memory read the return as unclassified."""
    resp = world.rule(**body)

    [row] = [
        e for e in await world.campaigns.control_log(CID) if e.operation is ControlOperation.RULE
    ]
    assert resp.status_code == 200
    assert {k: v for k, v in row.binding.items() if k.startswith("classification")} == recorded
