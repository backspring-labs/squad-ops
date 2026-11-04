"""The unattended resume at the resume route (SIP-0109 §24da; the 2.6 plan's D6 and D7; #2891).

Entered at ``POST /api/v1/campaigns/{id}/resume`` behind the runtime's authorization adapter, with
the real progress service over the memory campaign registry: the escalations are written by the
completion boundary's own row builder, and a delegated retry is built by ``owner_action``, the
owner's own path, so what reaches the outbox is what the live loop would drain.
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
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.continuation import (
    CampaignLimit,
    ContinuationDecision,
    CycleEnding,
    Guard,
    PendingAction,
)
from squadops.campaigns.gate import ruling_transition, submission
from squadops.campaigns.models import (
    AcceptedTree,
    CampaignState,
    ControlOperation,
    ControlOutcome,
    CycleKind,
    ProposalBinding,
    RefusalReason,
    SubmittedProposal,
)
from squadops.campaigns.progress import CampaignProgress, decision_transition
from squadops.cycles.models import ArtifactRef, Cycle, GateDecisionValue, TaskFlowPolicy
from tests.unit.campaigns.builders import campaign, move, policy

CID = "cmp_unattended01"
NOW = datetime(2026, 11, 4, 3, 0, tzinfo=UTC)
ALL = ["plan_gate", "in_cycle_failure", "launch_blocked"]
BINDING = ProposalBinding("prop_1", 1, "hash-1", "sha-cal")
_CR = ArtifactRef(
    artifact_id="art_cr",
    project_id="group_run",
    artifact_type="change_request",
    filename="change_request.yaml",
    content_hash="h",
    size_bytes=1,
    media_type="text/yaml",
    created_at=NOW,
    cycle_id="cyc_inc",
    run_id="run_1",
)


class _Vault:
    async def list_artifacts(self, **_):
        return []

    async def retrieve(self, artifact_id):
        return _CR, b"proposal_id: prop_1\n"


def _identity(role: str) -> Identity:
    return Identity(
        user_id=f"user-{role}",
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.SERVICE,
    )


class _World:
    def __init__(self) -> None:
        self.campaigns = MemoryCampaignRegistry()
        self.seat = Role.ADMIN
        app = FastAPI()
        world = self

        class Seat(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = _identity(world.seat)
                return await call_next(request)

        app.add_middleware(Seat)
        app.include_router(campaigns_router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        # The failed increment: approved under prop_1 v1 on the accepted tree, its change request
        # among its seeds, so a retry is bound to it as §10a binds one.
        cycles = AsyncMock()
        cycles.get_cycle.return_value = Cycle(
            cycle_id="cyc_inc",
            project_id="group_run",
            created_at=NOW,
            created_by="campaign-launcher",
            prd_ref=None,
            squad_profile_id="full-38",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            campaign_id=CID,
            kind="increment",
            execution_overrides={
                "campaign_proposal": {
                    "proposal_id": "prop_1",
                    "version": 1,
                    "baseline_tree": "sha-cal",
                },
                "plan_artifact_refs": ["art_cr"],
            },
        )
        cycles.list_runs.return_value = []
        app.state.campaign_progress = CampaignProgress(
            campaigns=self.campaigns,
            cycles=cycles,
            vault=_Vault(),
            assess=AsyncMock(),
            launch=AsyncMock(),
            evaluate_outcome=None,
            evaluate_baseline=None,
            outcome_section=None,
            intervention_section=None,
            campaign_branch=None,
            goal_sets=None,
        )
        app.state.campaign_launch = AsyncMock()
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def as_(self, seat: str) -> _World:
        self.seat = seat
        return self

    def resume(self, key: str, **extra):
        return self.client.post(
            f"/api/v1/campaigns/{CID}/resume",
            json={"reason": "overnight", "idempotency_key": key, **extra},
        )

    def pause(self, key: str):
        return self.client.post(
            f"/api/v1/campaigns/{CID}/pause", json={"reason": "hold", "idempotency_key": key}
        )

    async def log(self):
        return await self.campaigns.control_log(CID)


async def _escalated(declared: list[str], last=None) -> _World:
    """A campaign whose approved increment ``cyc_inc`` ended and escalated: by default at §10
    row 11 (an environment failure, no retries left in the decision's reading), the cycle's own
    failure; ``last`` replaces that row with another escalating one."""
    w = _World()
    await w.campaigns.create_campaign(
        campaign(
            CID,
            policy=policy(
                proposal_profile="campaign-increment",
                max_retry_cycles_per_increment=2,
                unattended_resume=tuple(declared),
            ),
        ),
        actor="owner",
        actor_role="admin",
        reason="r",
        idempotency_key="create",
    )
    await w.campaigns.transition(CID, move(CampaignState.CALIBRATING, "cal"))
    await w.campaigns.transition(
        CID,
        move(
            CampaignState.CALIBRATING,
            "promote",
            operation=ControlOperation.PROMOTE,
            accepted=AcceptedTree("sha-cal", "cyc_cal"),
        ),
    )
    await w.campaigns.transition(CID, move(CampaignState.AT_PROPOSAL, "propose"))
    await w.campaigns.transition(
        CID,
        submission(CampaignState.AT_PROPOSAL, SubmittedProposal(BINDING, "cyc_inc", "run_1")),
    )
    await w.campaigns.transition(
        CID,
        ruling_transition(
            GateDecisionValue.APPROVED, BINDING, run_id="run_1", actor="crew",
            actor_role="campaign-supervisor", reason="in scope", idempotency_key="rule-1",
        ),
    )  # fmt: skip
    if last is None:
        stored = await w.campaigns.get_campaign(CID)
        last = decision_transition(
            stored,
            ContinuationDecision("cyc_inc", 11, action=PendingAction.ESCALATE),
            ending=CycleEnding.ASSESSED,
            verdict=None,
            launch=None,
        )
    elif callable(last):
        last = last(await w.campaigns.get_campaign(CID))
    await w.campaigns.transition(CID, last)
    return w


def _audit(row) -> dict:
    b = row.binding
    return {k: b.get(k) for k in ("delegated", "class", "move", "definition_hash")}


async def test_a_declared_class_is_resumed_by_the_crew_and_the_retry_is_launched(world_hash=None):
    """Wiring (§24da, D6's first "done when"): the crew's principal resumes a declared in-cycle
    failure with a retry, and the owner's own path builds it: the outbox holds a retry bound to the
    increment, and the resume row names the principal, the class, the escalation and the
    definition hash. Bugs caught: the delegation refusing a declared class, or allowing it without
    the action executing (``owner_action`` skipped), or a row with no audit fields."""
    w = await _escalated(["in_cycle_failure"])
    [creation, *_rest, decided] = await w.log()

    resp = w.as_(Role.CAMPAIGN_SUPERVISOR).resume("crew-1", action="retry")

    assert resp.status_code == 200, resp.json()
    *_, row = await w.log()
    assert (row.operation, row.outcome, row.actor) == (
        ControlOperation.RESUME,
        ControlOutcome.APPLIED,
        "user-campaign-supervisor",
    )
    assert _audit(row) == {
        "delegated": True,
        "class": "in_cycle_failure",
        "move": "retry",
        "definition_hash": creation.request_hash,
    }
    assert row.binding["escalation"]["seq"] == decided.seq
    assert row.binding["action"] == "retry"
    [intent] = await w.campaigns.launch_intents(CID)
    assert intent.cycle_kind is CycleKind.RETRY
    proposal = intent.cycle_request["body"]["execution_overrides"]["campaign_proposal"]
    assert (proposal["proposal_id"], proposal["continues"]) == ("prop_1", "cyc_inc")
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.RETRYING


def _launch_refused(conflict: str):
    """A launch the rebase refused: an upstream conflict (§24cm), one of D6's never-classes."""

    def row(_campaign):
        return move(
            CampaignState.ESCALATED,
            "refused-1",
            operation=ControlOperation.LAUNCH_REFUSED,
            target="lnc_1",
            binding={"launch_id": "lnc_1", "refused_from": "at_proposal", "refusal": conflict},
        )

    return row


def _limit_pause(stored):
    return decision_transition(
        stored,
        ContinuationDecision(
            "cyc_inc",
            12,
            action=PendingAction.REPAIR,
            guard=Guard.PAUSED,
            paused_by=CampaignLimit.BUDGET,
        ),
        ending=CycleEnding.ASSESSED,
        verdict=None,
        launch=None,
    )


def _unbuilt(stored):
    return decision_transition(
        stored,
        ContinuationDecision("cyc_inc", 7, action=PendingAction.PROPOSE, guard=Guard.PROCEED),
        ending=CycleEnding.ASSESSED,
        verdict=None,
        launch=None,
        unbuilt="the goal set has no pending backlog item",
    )


@pytest.mark.parametrize(
    ("declared", "last", "action", "klass", "why"),
    [
        (["plan_gate"], None, "retry", "in_cycle_failure", "does not declare in_cycle_failure"),
        (ALL, None, "propose", "in_cycle_failure", "not propose"),
        (ALL, None, "abandon_and_propose", "in_cycle_failure", "not abandon_and_propose"),
        (ALL, _launch_refused("CAMPAIGN_BRANCH_CONFLICT: x"), None, None, "of no class"),
        (ALL, _limit_pause, None, None, "paused by a limit"),
        (ALL, _unbuilt, "propose", None, "of no class"),
    ],
    ids=[
        "undeclared",
        "propose-not-permitted",
        "abandon-not-permitted",
        "upstream-conflict",
        "limit-pause",
        "unbuilt-proposal",
    ],
)
async def test_a_crew_resume_outside_its_grant_is_refused_recorded_and_changes_nothing(
    declared, last, action, klass, why
):
    """D6's second "done when": an undeclared class, a move the class doesn't permit and each
    never-class (an upstream conflict, a limit's pause, a proposal that couldn't be built) are
    refused 403 with the reason, recorded as a ``resume_not_delegated`` row naming the principal,
    the class, the escalation and the definition hash; the state and the outbox are untouched."""
    w = await _escalated(declared, last)
    before = await w.campaigns.get_campaign(CID)
    creation = (await w.log())[0]

    resp = w.as_(Role.CAMPAIGN_SUPERVISOR).resume(
        "crew-1", **({"action": action} if action else {})
    )

    error = resp.json()["detail"]["error"]
    assert (resp.status_code, error["code"]) == (403, "RESUME_NOT_DELEGATED")
    assert why in error["message"]
    *_, row = await w.log()
    assert (row.operation, row.outcome, row.refusal, row.actor) == (
        ControlOperation.RESUME,
        ControlOutcome.REFUSED,
        RefusalReason.RESUME_NOT_DELEGATED,
        "user-campaign-supervisor",
    )
    assert row.binding["class"] == klass
    assert row.binding["delegated"] is False
    assert row.binding["definition_hash"] == creation.request_hash
    assert row.binding["escalation"]["seq"] == row.seq - 1
    assert why in row.binding["why"]
    assert error["details"]["entry_id"] == row.entry_id
    after = await w.campaigns.get_campaign(CID)
    assert (after.state, after.updated_at) == (before.state, before.updated_at)
    assert await w.campaigns.launch_intents(CID) == []


async def test_the_owners_pause_revokes_the_grant_and_the_owners_resume_restores_it():
    """D6's third "done when": the owner's pause, which the principal can't resume. Bugs caught:
    the crew lifting the owner's pause, or reading the escalation under it as still delegated;
    and a grant never restored once the owner resumes."""
    w = await _escalated(ALL)
    assert w.as_(Role.ADMIN).pause("owner-pause").status_code == 200

    lift = w.as_(Role.CAMPAIGN_SUPERVISOR).resume("crew-lift")
    retry = w.resume("crew-retry", action="retry")

    for resp in (lift, retry):
        assert (resp.status_code, resp.json()["detail"]["error"]["code"]) == (
            403,
            "RESUME_NOT_DELEGATED",
        )
        assert "paused by the owner" in resp.json()["detail"]["error"]["message"]
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.PAUSED
    assert await w.campaigns.launch_intents(CID) == []

    assert w.as_(Role.ADMIN).resume("owner-resume").status_code == 200
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.ESCALATED
    restored = w.as_(Role.CAMPAIGN_SUPERVISOR).resume("crew-after", action="retry")
    assert restored.status_code == 200, restored.json()


async def test_a_retry_past_the_increments_limit_is_the_owners():
    """§24da "within the limits": the crew's retries spend ``max_retry_cycles_per_increment``
    (2 here). Bug caught: an unattended loop of retries the policy bounds for the owner."""
    w = await _escalated(ALL)
    for n in (1, 2):
        await w.campaigns.transition(
            CID, move(CampaignState.ESCALATED, f"again-{n}", operation=ControlOperation.DECIDE,
                      binding={"action": "escalate", "ending": "assessed", "row": 11},
                      target="cyc_inc")
        ) if n == 2 else None  # fmt: skip
        resp = w.as_(Role.CAMPAIGN_SUPERVISOR).resume(f"crew-{n}", action="retry")
        assert resp.status_code == 200, resp.json()
    await w.campaigns.transition(
        CID,
        move(CampaignState.ESCALATED, "again-3", operation=ControlOperation.DECIDE,
             binding={"action": "escalate", "ending": "assessed", "row": 11}, target="cyc_inc"),
    )  # fmt: skip

    third = w.resume("crew-3", action="retry")

    assert third.status_code == 403
    assert "spent 2 retry cycle(s)" in third.json()["detail"]["error"]["message"]
    assert len(await w.campaigns.launch_intents(CID)) == 2


async def test_a_launch_blocked_escalation_is_relaunched_by_the_crew_when_declared():
    """The ``launch_blocked`` class: the crew's resume without an action returns the campaign to
    ``launch_blocked``, re-attempted at once. Bug caught: the relaunch refused as a missing move."""

    def blocked(_campaign):
        return move(
            CampaignState.ESCALATED,
            "blocked-6",
            operation=ControlOperation.LAUNCH_BLOCKED,
            target="lnc_1",
            binding={"launch_id": "lnc_1", "attempt": 6, "blocked_from": "at_proposal",
                     "refusal": "box_held", "reasons": []},
        )  # fmt: skip

    w = await _escalated(["launch_blocked"], blocked)

    resp = w.as_(Role.CAMPAIGN_SUPERVISOR).resume("crew-relaunch")

    assert resp.status_code == 200, resp.json()
    assert resp.json()["entry"]["binding"]["class"] == "launch_blocked"
    assert (await w.campaigns.get_campaign(CID)).state is CampaignState.LAUNCH_BLOCKED


@pytest.mark.parametrize(
    ("seat", "status", "code"),
    [(Role.ADMIN, 200, None), (Role.VIEWER, 403, "FORBIDDEN"), (Role.CAMPAIGN_TRIAGE, 403, "FORBIDDEN")],
)  # fmt: skip
async def test_the_owners_path_is_unchanged_and_a_reader_is_refused_before_any_row(
    seat, status, code
):
    """The owner resumes an undeclared class as before, with no delegation on the row; a reader
    without ``campaigns:manage`` is refused by the scope check and records nothing."""
    w = await _escalated([])
    rows = len(await w.log())

    resp = w.as_(seat).resume("k-1", action="retry")

    assert resp.status_code == status, resp.json()
    if code is None:
        assert "delegated" not in resp.json()["entry"]["binding"]
    else:
        assert resp.json()["detail"]["error"]["code"] == code
        assert len(await w.log()) == rows
