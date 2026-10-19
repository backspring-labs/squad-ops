"""Cross-Cycle Memory's lesson routes (SIP-0110 §0.6–§0.7; slice 3d, #2096), entered at the HTTP surface
with the real authorization adapter, over the in-memory store.

What bugs would these catch? Anyone but the owner approving or revoking a lesson (the stop list's
"approving any lesson is the owner's"); an approval stored without the combined check §0.6 requires;
a revocation that names none of the running units holding it; a draft citing evidence the store
never recorded.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from squadops.api.routes.memory import memory_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.models import (
    CampaignNotFoundError,
    CampaignOutcome,
    CampaignState,
    ControlOperation,
)
from squadops.cycles.models import Cycle, CycleNotFoundError, Run, TaskFlowPolicy
from squadops.memory.lessons import UnitKind
from squadops.memory.observations import observe_proposal_rulings
from squadops.memory.pinning import pin_unit
from tests.unit.campaigns.builders import T0, campaign
from tests.unit.memory.test_observations import _entry

pytestmark = pytest.mark.auth

BASE = "/api/v1/projects/group_run"
WHERE = {
    "task_types": ["strategy.propose_increment"],
    "roles": ["strat"],
    "stacks": ["fullstack_fastapi_react"],
    "model_families": ["qwen3.8"],
}


def _identity(role: str) -> Identity:
    return Identity(
        user_id=f"user-{role}",
        display_name=role,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.HUMAN,
    )


class _Units:
    """Each unit's state as the revocation reads it, through the campaign and cycle registries."""

    WORKLOADS = ("framing", "implementation")

    def __init__(self) -> None:
        self.campaigns: dict[str, CampaignState] = {}
        self.runs: dict[str, list[str]] = {}  # each run's status, in workload order

    async def get_campaign(self, campaign_id: str):
        if campaign_id not in self.campaigns:
            raise CampaignNotFoundError(campaign_id)
        state = self.campaigns[campaign_id]
        done = state is CampaignState.COMPLETED
        return campaign(campaign_id, state=state, outcome=CampaignOutcome.SUCCESS if done else None)

    async def get_cycle(self, cycle_id: str) -> Cycle:
        if cycle_id not in self.runs:
            raise CycleNotFoundError(cycle_id)
        return Cycle(
            cycle_id=cycle_id,
            project_id="group_run",
            created_at=T0,
            created_by="owner",
            prd_ref=None,
            squad_profile_id="full",
            squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"),
            build_strategy="fresh",
            applied_defaults={"workload_sequence": [{"type": t} for t in self.WORKLOADS]},
        )

    async def list_runs(self, cycle_id: str, **_) -> list[Run]:
        return [
            Run(
                run_id=f"run_{n}",
                cycle_id=cycle_id,
                run_number=n,
                status=status,
                initiated_by="api",
                resolved_config_hash="x",
                workload_type=self.WORKLOADS[n - 1],
            )
            for n, status in enumerate(self.runs[cycle_id], start=1)
        ]


class _World:
    def __init__(self) -> None:
        self.store = InMemoryCrossCycleMemoryStore()
        self.identity = _identity(Role.ADMIN)
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                request.state.identity = world.identity
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(memory_router)
        app.state.memory_store = self.store
        self.units = _Units()
        app.state.campaign_registry = self.units
        app.state.cycle_registry = self.units
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def draft(self, target: str = "criterion_already_satisfied", **change):
        body = {
            "target_behavior": target,
            "text": "Name the manifest element the criterion checks.",
            "applicability": WHERE,
            "template_id": "lesson.criterion_already_satisfied",
            "template_version": "1",
            "drafter_model": "claude-opus",
            "drafter_version": "5.5",
            "cited_observations": [self.cited],
            **change,
        }
        return self.client.post(f"{BASE}/lessons", json=body)

    def approve(self, revision_id: str, checked=(), verdict="no_conflict", **change):
        body = {
            "ruling": "the owner, 2026-10-09: approve it",
            "replay_check": {"reference": "replay/arm-a-vs-b", "result": "absent 5/6 vs 1/6"},
            "combined_check": {
                "revision_ids": list(checked),
                "verdict": verdict,
                "reference": "auditor/combined",
            },
            **change,
        }
        return self.client.post(f"{BASE}/lessons/{revision_id}/approvals", json=body)


@pytest.fixture
async def world() -> _World:
    w = _World()
    bind = {
        "proposal_id": "prop_1",
        "version": 1,
        "decision": "returned_for_revision",
        "classification": "criteria_not_checkable",
    }
    # A return classified only in prose: no class on the ruling (#2160's case).
    prose = {"proposal_id": "prop_2", "version": 1, "decision": "returned_for_revision"}
    observed, in_prose = observe_proposal_rulings(
        "cmp_1",
        "group_run",
        [_entry(1, ControlOperation.RULE, bind), _entry(2, ControlOperation.RULE, prose)],
    )
    await w.store.record_observations([observed, in_prose])
    w.cited = observed.source_id
    w.prose = in_prose.source_id
    return w


@pytest.mark.parametrize(
    ("role", "route", "status"),
    [
        (Role.VIEWER, "list", 200),
        (Role.CAMPAIGN_TRIAGE, "list", 200),
        (Role.OPERATOR, "draft", 403),
        (Role.CAMPAIGN_SUPERVISOR, "draft", 403),
        (Role.CAMPAIGN_SUPERVISOR, "approve", 403),
        (Role.OPERATOR, "approve", 403),
        (Role.ADMIN, "approve", 201),
    ],
)
async def test_approving_a_lesson_is_the_owners_alone(world, role, route, status):
    """Bug caught: the crew's supervisor, or an operator who writes cycles, approving a lesson into
    every later unit's prompts (the stop list: approving any lesson is the owner's)."""
    revision_id = world.draft().json()["revision_id"]
    world.identity = _identity(role)

    resp = {
        "list": lambda: world.client.get(f"{BASE}/lessons"),
        "draft": lambda: world.draft("another_behavior"),
        "approve": lambda: world.approve(revision_id),
    }[route]()

    assert resp.status_code == status


async def test_a_draft_is_approved_only_with_a_combined_check_of_what_it_would_be_supplied_beside(
    world,
):
    """§0.15 combined guidance through the routes. Bug caught: an approval stored when a lesson
    already approved for the same tasks was never checked beside it."""
    held = world.draft("criterion_names_no_element").json()["revision_id"]
    assert world.approve(held).status_code == 201
    draft = world.draft().json()

    together = world.client.get(f"{BASE}/lessons/{draft['revision_id']}/supplied-together").json()
    refused = world.approve(draft["revision_id"])
    approved = world.approve(draft["revision_id"], checked=together["revision_ids"])

    assert (draft["revision"], together["revision_ids"]) == (1, [held])
    assert (
        refused.status_code == 422 and "not covered" in refused.json()["detail"]["error"]["message"]
    )
    assert approved.status_code == 201
    assert approved.json()["approved_by"] == "user-admin"
    listed = {x["revision_id"]: x for x in world.client.get(f"{BASE}/lessons").json()}
    assert len(listed[draft["revision_id"]]["approvals"]) == 1


async def test_a_revocation_names_the_running_units_that_hold_it_and_stands_once(world):
    """§0.7, D9. Bugs caught: a revocation that says nothing of the units running with the lesson
    pinned, so their measurements are read as if it never happened; or a second revocation
    rewriting who revoked it and why."""
    revision_id = world.draft().json()["revision_id"]
    approval_id = world.approve(revision_id).json()["approval_id"]
    world.units.campaigns["cmp_running"] = CampaignState.BUILDING
    await pin_unit(
        world.store,
        unit_kind=UnitKind.CAMPAIGN,
        unit_id="cmp_running",
        project_id="group_run",
        pinned_at=datetime.now(UTC),
        disabled=False,
    )

    first = world.client.post(f"{BASE}/approvals/{approval_id}/revocation", json={"reason": "harm"})
    again = world.client.post(f"{BASE}/approvals/{approval_id}/revocation", json={"reason": "x"})

    body = first.json()
    assert first.status_code == 200
    assert [u["unit_id"] for u in body["units_holding_it"]] == ["cmp_running"]
    assert (body["approval"]["revoked_by"], body["approval"]["revocation_reason"]) == (
        "user-admin",
        "harm",
    )
    assert "halt or restart" in body["next"]
    assert again.status_code == 409


async def _pin(world, kind: UnitKind, unit_id: str) -> None:
    await pin_unit(
        world.store,
        unit_kind=kind,
        unit_id=unit_id,
        project_id="group_run",
        pinned_at=datetime.now(UTC),
        disabled=False,
    )


async def test_a_revocation_names_only_running_units_as_work_to_halt(world):
    """Entered at the revocation route (#2210). Bug caught: the five finished 2.2 window
    campaigns named as "still held", which buries the one live unit an emergency revocation
    has to halt. A cycle between its workloads still runs though its latest run completed (the
    reading #2214 fixed for the abort); a unit that can't be read is named."""
    approval_id = world.approve(world.draft().json()["revision_id"]).json()["approval_id"]
    world.units.campaigns.update(
        {"cmp_live": CampaignState.AT_PROPOSAL, "cmp_done": CampaignState.COMPLETED}
    )
    world.units.runs.update({"cyc_between": ["completed"], "cyc_done": ["completed", "completed"]})
    for kind, unit_id in [
        (UnitKind.CAMPAIGN, "cmp_live"),
        (UnitKind.CAMPAIGN, "cmp_done"),
        (UnitKind.CYCLE, "cyc_between"),
        (UnitKind.CYCLE, "cyc_done"),
        (UnitKind.CAMPAIGN, "cmp_unreadable"),
    ]:
        await _pin(world, kind, unit_id)

    body = world.client.post(
        f"{BASE}/approvals/{approval_id}/revocation", json={"reason": "harm"}
    ).json()

    assert sorted(u["unit_id"] for u in body["units_holding_it"]) == [
        "cmp_live",
        "cmp_unreadable",
        "cyc_between",
    ]
    assert sorted(u["unit_id"] for u in body["finished_units_holding_it"]) == [
        "cmp_done",
        "cyc_done",
    ]
    assert "halt or restart" in body["next"]


async def test_a_revocation_held_only_by_finished_units_asks_no_one_to_halt(world):
    """Bug caught: the 2026-10-10 revocation telling the operator to halt five completed
    campaigns."""
    approval_id = world.approve(world.draft().json()["revision_id"]).json()["approval_id"]
    world.units.campaigns["cmp_done"] = CampaignState.COMPLETED
    await _pin(world, UnitKind.CAMPAIGN, "cmp_done")

    body = world.client.post(
        f"{BASE}/approvals/{approval_id}/revocation", json={"reason": "disposition"}
    ).json()

    assert body["units_holding_it"] == []
    assert [u["unit_id"] for u in body["finished_units_holding_it"]] == ["cmp_done"]
    assert "halt" not in body["next"]
    assert "set their measurements apart" in body["next"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"cited_observations": ["proposal_ruling:cmp_x:e9"]}, "not citable"),
        ({"applicability": {**WHERE, "model_families": [""]}}, "an applicability names its"),
        ({"text": " "}, "names its text"),
    ],
)
async def test_a_draft_the_rules_refuse_is_a_422_and_stores_nothing(world, change, message):
    resp = world.draft(**change)

    assert resp.status_code == 422
    assert message in resp.json()["detail"]["error"]["message"]
    assert world.client.get(f"{BASE}/lessons").json() == []


async def test_an_exposures_target_is_assessed_and_the_rate_reads_the_supplied_series(world):
    """§0.10 through the routes. Bugs caught: an absence recorded where the work was left out;
    the supplied flag taken from the caller rather than the exposure's own intervention, so the
    memory-on series could be filled by assertion."""
    from squadops.memory.exposures import Exposure
    from squadops.memory.lessons import RecallDisposition, Recalled
    from squadops.memory.recall import RecallQuery

    exposure = Exposure(
        run_id="run_p",
        task_id="task-prop",
        cycle_id="cyc_inc",
        agent_id="nat",
        seam="proposal_writing",
        query=RecallQuery("group_run", "strategy.propose_increment", "strat"),
        recalled={
            **Recalled("snp_x", RecallDisposition.SUPPLIED).exposure(),
            "intervention": [{"revision_id": "pat_a@1"}],
        },
        recorded_at=datetime.now(UTC),
    )
    await world.store.record_exposure(exposure)
    path = f"{BASE}/exposures/{exposure.exposure_id}/assessments"
    body = {"pattern_id": "pat_a", "rubric": "lesson.r@1", "evidence": "change_request v1"}

    leaving_work_out = world.client.post(path, json={**body, "state": "absent"})
    absent = world.client.post(path, json={**body, "state": "absent", "required_work_done": True})
    rates = world.client.get(f"{BASE}/lessons/absence-rates").json()
    listed = world.client.get(f"{BASE}/exposures", params={"run_id": "run_p"}).json()

    assert leaving_work_out.status_code == 422
    assert absent.status_code == 201 and absent.json()["supplied"] is True
    assert rates == [
        {
            "pattern_id": "pat_a",
            "supplied": True,
            "absent": 1,
            "assessed": 1,
            "not_applicable": 0,
            "unassessed": 0,
            "rate": 1.0,
        }
    ]
    assert [a["state"] for a in listed[0]["assessments"]] == ["absent"]


async def test_an_exposure_whose_unit_withheld_memorys_context_is_never_assessed(world):
    """Appendix A §3.7: ``memory_context: none`` withholds the project's instructions too, so its
    exposure would read as the memory-off series with different requirements. Bug caught: it
    assessed into that series, moving a lesson's absence rate with an experiment that never
    measured the lesson."""
    from squadops.memory.exposures import Exposure
    from squadops.memory.lessons import RecallDisposition, Recalled
    from squadops.memory.recall import RecallQuery

    exposure = Exposure(
        run_id="run_none",
        task_id="task-design",
        cycle_id="cyc_none",
        agent_id="neo",
        seam="plan_writing",
        query=RecallQuery("group_run", "development.design_plan", "dev"),
        recalled=Recalled("snp_none", RecallDisposition.CONTEXT_NONE).exposure(),
        recorded_at=datetime.now(UTC),
    )
    await world.store.record_exposure(exposure)

    refused = world.client.post(
        f"{BASE}/exposures/{exposure.exposure_id}/assessments",
        json={
            "pattern_id": "pat_a",
            "rubric": "lesson.r@1",
            "evidence": "the design plan, v1",
            "state": "absent",
            "required_work_done": True,
        },
    )

    assert refused.status_code == 422
    assert "memory_context: none" in refused.json()["detail"]["error"]["message"]
    assert await world.store.list_assessments("group_run") == []
    assert world.client.get(f"{BASE}/lessons/absence-rates").json() == []


ANNOTATION = {
    "values": ["criteria_not_checkable"],
    "target_behavior": "criterion_already_satisfied",
    "evidence": {"ruling": "T3 holds because the accepted app has no capacity concept"},
    "context": {"deploy": "rebuild 20, before #1947", "prompt": "the proposal block, verbatim"},
    "annotator": "claude-opus-5-5",
}


async def test_a_prose_return_is_cited_only_after_the_owner_reviews_its_annotation(world):
    """§0.4 through the routes (#2160). Bugs caught: a lesson citing a return whose class is only in
    prose; an annotation that classifies before review; anyone but the owner reviewing one; a
    review rewritten; the observation itself changed by its annotation."""
    annotations = f"{BASE}/observations/{world.prose}/annotations"

    refused = world.draft(cited_observations=[world.prose])
    proposed = world.client.post(annotations, json=ANNOTATION)
    still_refused = world.draft(cited_observations=[world.prose])
    review_path = f"{BASE}/annotations/{proposed.json()['annotation_id']}/review"
    world.identity = _identity(Role.CAMPAIGN_SUPERVISOR)
    by_supervisor = world.client.post(review_path, json={"note": "read"})
    world.identity = _identity(Role.ADMIN)
    by_owner = world.client.post(review_path, json={"note": "read the ruling and the manifest"})
    again = world.client.post(review_path, json={"note": "twice"})
    cited = world.draft(cited_observations=[world.prose])
    listed = {o["source_id"]: o for o in world.client.get(f"{BASE}/observations").json()}

    assert refused.status_code == 422 and "not citable" in refused.text
    assert proposed.status_code == 201 and proposed.json()["reviewed_by"] is None
    assert still_refused.status_code == 422
    assert by_supervisor.status_code == 403
    assert by_owner.status_code == 200 and by_owner.json()["reviewed_by"] == "user-admin"
    assert again.status_code == 409
    assert cited.status_code == 201
    assert len(listed) == 2
    assert listed[world.prose]["classification"]["vocabulary"] == "unclassified"
    assert listed[world.prose]["effective_classification"]["values"] == ["criteria_not_checkable"]


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"context": {"deploy": "rebuild 20"}}, 422),
        ({"values": ["made_up_class"]}, 422),
    ],
    ids=["no prompt context", "outside the vocabulary"],
)
async def test_an_annotation_the_rules_refuse_is_a_422_and_stores_nothing(world, change, status):
    resp = world.client.post(
        f"{BASE}/observations/{world.prose}/annotations", json={**ANNOTATION, **change}
    )

    assert resp.status_code == status
    assert await world.store.list_annotations("group_run") == []


async def test_an_annotation_of_an_unknown_observation_or_by_an_operator_is_refused(world):
    """Bugs caught: an annotation stored against an observation the project never recorded, and
    one proposed by a role that cannot draft."""
    unknown = world.client.post(
        f"{BASE}/observations/proposal_ruling:cmp_x:e9/annotations", json=ANNOTATION
    )
    world.identity = _identity(Role.OPERATOR)
    by_operator = world.client.post(
        f"{BASE}/observations/{world.prose}/annotations", json=ANNOTATION
    )

    assert (unknown.status_code, by_operator.status_code) == (404, 403)


async def test_each_memory_body_declares_every_field_its_record_carries(world):
    """#1976, through the routes. Bug caught: a record that gains a field its response model does
    not declare. The model passes it on (``extra="allow"``), so no client loses it, but OpenAPI
    stops describing it. Each body's keys are exactly its model's fields, nested ones included."""
    from squadops.api import memory_schemas as schemas
    from squadops.memory.exposures import Exposure
    from squadops.memory.lessons import RecallDisposition, Recalled
    from squadops.memory.recall import RecallQuery

    revision_id = world.draft().json()["revision_id"]
    world.approve(revision_id)
    annotation_id = world.client.post(
        f"{BASE}/observations/{world.prose}/annotations", json=ANNOTATION
    ).json()["annotation_id"]
    world.client.post(f"{BASE}/annotations/{annotation_id}/review", json={"note": "read"})
    exposure = Exposure(
        run_id="run_p",
        task_id="task-prop",
        cycle_id="cyc_inc",
        agent_id="nat",
        seam="proposal_writing",
        query=RecallQuery("group_run", "strategy.propose_increment", "strat"),
        recalled=Recalled("snp_x", RecallDisposition.SUPPLIED).exposure(),
        recorded_at=datetime.now(UTC),
    )
    await world.store.record_exposure(exposure)
    world.client.post(
        f"{BASE}/exposures/{exposure.exposure_id}/assessments",
        json={"pattern_id": "pat_a", "state": "not_applicable", "rubric": "r@1", "evidence": "v1"},
    )
    lessons = world.client.get(f"{BASE}/lessons").json()
    observations = world.client.get(f"{BASE}/observations").json()
    exposures = world.client.get(f"{BASE}/exposures", params={"run_id": "run_p"}).json()

    bodies = [
        *((lesson, schemas.LessonResponse) for lesson in lessons),
        *((lesson["applicability"], schemas.ApplicabilityResponse) for lesson in lessons),
        *((a, schemas.ApprovalResponse) for lesson in lessons for a in lesson["approvals"]),
        *((o, schemas.ObservationResponse) for o in observations),
        *((o["classification"], schemas.ClassificationResponse) for o in observations),
        *((a, schemas.AnnotationResponse) for o in observations for a in o["annotations"]),
        *((e, schemas.ExposureResponse) for e in exposures),
        *((a, schemas.AssessmentResponse) for e in exposures for a in e["assessments"]),
    ]
    undeclared = {
        model.__name__: sorted(set(body) ^ set(model.model_fields))
        for body, model in bodies
        if set(body) != set(model.model_fields)
    }
    assert {model for _, model in bodies} >= {
        schemas.ApprovalResponse,
        schemas.AnnotationResponse,
        schemas.AssessmentResponse,
    }
    assert undeclared == {}
