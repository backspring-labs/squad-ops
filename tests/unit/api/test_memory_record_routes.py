"""The typed memory records' routes (SIP-0110 Appendix A; #2177), entered at the HTTP surface with
the real authorization adapter, over the in-memory stores.

What bugs would these catch? The permission table (§A.3.3) holding in the domain but not through the
API; another user's private record or another project's answering a query, or reached by id; a
correction or a withdrawal that loses a revision; a task instruction aimed at another project's
cycle; a failed write reported as success.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.memory.cross_cycle import InMemoryCrossCycleMemoryStore
from adapters.memory.records import InMemoryMemoryRecords
from squadops.api.routes.memory import memory_records_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.cycles.models import Cycle, CycleNotFoundError, TaskFlowPolicy

pytestmark = pytest.mark.auth

URL = "/api/v1/memory-records"
T0 = datetime(2026, 10, 19, tzinfo=UTC)


def _identity(user: str, role: str) -> Identity:
    return Identity(
        user_id=user,
        display_name=user,
        roles=(role,),
        scopes=tuple(sorted(scopes_for_roles((role,)))),
        identity_type=IdentityType.HUMAN,
    )


class _Cycles:
    """Two cycles of ``group_run``, one a campaign's, and one of another project."""

    CYCLES = {"cyc_solo": ("group_run", None), "cyc_camp": ("group_run", "cmp_1"), "cyc_other": ("play_game", None)}  # fmt: skip

    async def get_cycle(self, cycle_id: str) -> Cycle:
        if cycle_id not in self.CYCLES:
            raise CycleNotFoundError(cycle_id)
        project, campaign = self.CYCLES[cycle_id]
        return Cycle(
            cycle_id=cycle_id, project_id=project, created_at=T0, created_by="owner", prd_ref=None,
            squad_profile_id="full", squad_profile_snapshot_ref="sha256:abc",
            task_flow_policy=TaskFlowPolicy(mode="sequential"), build_strategy="fresh",
            campaign_id=campaign,
        )  # fmt: skip


@pytest.fixture
def world():
    class World:
        def __init__(self) -> None:
            self.identity = _identity("ada", Role.ADMIN)
            app = FastAPI()
            outer = self

            class InjectIdentity(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next):
                    request.state.identity = outer.identity
                    return await call_next(request)

            app.add_middleware(InjectIdentity)
            app.include_router(memory_records_router)
            app.state.memory_records = InMemoryMemoryRecords()
            # A task instruction written here is checked against its cycle's dispatches (#2178).
            app.state.memory_store = InMemoryCrossCycleMemoryStore()
            app.state.cycle_registry = _Cycles()
            app.state.authz_port = KeycloakAuthzAdapter()
            self.client = TestClient(app)

        def as_(self, user: str, role: str):
            self.identity = _identity(user, role)
            return self

        def create(self, **body):
            return self.client.post(URL, json={"body": "keep the join idempotent", **body})

    return World()


ANYWHERE = {"task_types": ["*"], "roles": ["*"], "stacks": ["*"]}


@pytest.mark.parametrize(
    ("role", "body", "status"),
    [
        (Role.VIEWER, {"kind": "note", "scope": "user"}, 201),
        (Role.VIEWER, {"kind": "note", "scope": "project", "project_id": "group_run"}, 403),
        (Role.ADMIN, {"kind": "note", "scope": "project", "project_id": "group_run"}, 201),
        (Role.OPERATOR, {"kind": "instruction", "scope": "project", "project_id": "group_run", "applicability": ANYWHERE}, 403),
        (Role.ADMIN, {"kind": "instruction", "scope": "project", "project_id": "group_run", "applicability": ANYWHERE}, 201),
        (Role.OPERATOR, {"kind": "instruction", "scope": "task", "project_id": "group_run", "target": {"cycle_id": "cyc_solo", "task_types": ["qa.test"]}}, 201),
        (Role.OPERATOR, {"kind": "instruction", "scope": "task", "project_id": "group_run", "target": {"cycle_id": "cyc_camp", "task_types": ["qa.test"]}}, 403),
        (Role.CAMPAIGN_SUPERVISOR, {"kind": "instruction", "scope": "task", "project_id": "group_run", "target": {"cycle_id": "cyc_camp", "task_types": ["qa.test"]}}, 201),
        (Role.ADMIN, {"kind": "instruction", "scope": "task", "project_id": "group_run", "target": {"cycle_id": "cyc_other", "task_types": ["qa.test"]}}, 422),
        (Role.ADMIN, {"kind": "note", "scope": "project", "project_id": "group_run", "references": [{"ref": "manifest:decision:d@3", "content": "x"}]}, 422),
    ],
    ids=[
        "anyone-keeps-a-private-note", "a-viewer-cant-write-a-project-note",
        "an-admin-writes-a-project-note", "an-operator-cant-instruct-a-project",
        "an-admin-instructs-a-project", "an-operator-directs-a-standalone-cycle",
        "an-operator-cant-direct-a-campaigns-cycle", "the-supervisor-directs-a-campaigns-cycle",
        "a-task-instruction-for-another-projects-cycle", "a-reference-carrying-a-copy",
    ],
)  # fmt: skip
def test_each_permission_rule_holds_through_the_api(world, role, body, status):
    """§A.3.3's table, entered at the HTTP surface with the real role-to-scope mapping."""
    response = world.as_("ada", role).create(**body)

    assert response.status_code == status, response.text
    if status == 403:
        assert response.json()["detail"]["error"]["code"] == "FORBIDDEN"


def test_a_query_answers_with_its_binding_only_and_a_hidden_record_is_not_found(world):
    """T4 through the API. Bug caught: another user's private note listed or fetched by id, or a
    project's records answering an unbound query."""
    world.as_("ada", Role.ADMIN)
    private = world.create(kind="note", scope="user").json()["record_id"]
    project = world.create(kind="note", scope="project", project_id="group_run").json()["record_id"]

    world.as_("bo", Role.VIEWER)
    bound = [
        r["record_id"] for r in world.client.get(URL, params={"project_id": "group_run"}).json()
    ]
    unbound = world.client.get(URL).json()

    assert bound == [project]
    assert unbound == []
    assert world.client.get(f"{URL}/{private}").status_code == 404
    assert world.client.get(f"{URL}/{project}").status_code == 200


def test_a_correction_and_a_withdrawal_keep_every_revision(world):
    """§A.3.8 through the API. Bug caught: a correction replacing the record, a withdrawn record
    still listed, or one whose history is gone."""
    world.as_("ada", Role.ADMIN)
    rid = world.create(kind="note", scope="project", project_id="group_run").json()["record_id"]

    revised = world.client.post(f"{URL}/{rid}/revisions", json={"body": "and say why"})
    gone = world.client.post(f"{URL}/{rid}/withdrawal", json={"why": "now an instruction"})
    listed = world.client.get(URL, params={"project_id": "group_run"}).json()
    history = world.client.get(f"{URL}/{rid}").json()

    assert revised.status_code == 201 and revised.json()["current"]["supersedes"] == 1
    assert gone.status_code == 201 and gone.json()["status"] == "withdrawn"
    assert listed == []
    assert [r["body"] for r in history["revisions"]] == ["keep the join idempotent", "and say why"]
    assert world.client.post(f"{URL}/{rid}/revisions", json={"body": "again"}).status_code == 422


def test_only_the_owner_corrects_a_private_record(world):
    """Bug caught: an admin rewriting someone's private note because they hold every scope."""
    world.as_("ada", Role.VIEWER)
    rid = world.create(kind="preference", scope="user").json()["record_id"]

    world.as_("bo", Role.ADMIN)
    assert world.client.post(f"{URL}/{rid}/revisions", json={"body": "x"}).status_code == 404


@pytest.mark.parametrize(
    ("applicability", "named"),
    [
        ({"task_types": ["*"], "roles": ["development"], "stacks": ["*"]}, "role 'development'"),
        ({"task_types": ["development.implement"], "roles": ["*"], "stacks": ["*"]}, "task type 'development.implement'"),
        ({"task_types": ["*"], "roles": ["dev"], "stacks": ["nextjs"]}, "stack 'nextjs'"),
    ],
)  # fmt: skip
def test_an_applicability_naming_what_no_dispatch_carries_is_refused(world, applicability, named):
    """The second read of PR #2515. Bug caught: ``roles: [development]`` accepted, then matching
    no dispatch (whose role is ``dev``), so the instruction binds nothing and nothing says so."""
    body = {"kind": "instruction", "scope": "project", "project_id": "group_run"}
    refused = world.as_("ada", Role.ADMIN).create(**body, applicability=applicability)
    fitting = world.create(**body, applicability={"task_types": ["qa.test"], "roles": ["qa"], "stacks": ["nextjs_ts"]})  # fmt: skip

    assert refused.status_code == 422
    assert named in refused.json()["detail"]["error"]["message"]
    assert fitting.status_code == 201, fitting.text


@pytest.mark.parametrize(
    ("resolvers", "scope", "status", "stored"),
    [
        ((), "project", 422, None),
        (("fake",), "project", 201, {"ref": "fake:doc:spec@current", "required": True}),
        ((), "task", 422, None),
        (("fake",), "task", 201, {"ref": "fake:doc:spec@r1", "required": True,
                                  "digest": "sha256:r1", "written": "fake:doc:spec@current"}),
    ],
    ids=["no-resolver-for-the-family", "a-resolver-binds-it-at-admission",
         "no-resolver-for-a-task-instruction", "a-task-instruction-binds-it-with-its-cycle"],
)  # fmt: skip
def test_at_current_is_written_only_where_a_resolver_will_bind_it(
    world, resolvers, scope, status, stored
):
    """#2179 and #2178 T16. Bugs caught: ``@current`` accepted for a family nothing binds, so every
    task the instruction applies to is held at its first dispatch; a task instruction's stored as
    written, so its cycle's tasks would read whatever is current at dispatch; a project
    instruction's bound at write, when each unit pinning it binds its own."""
    from tests.unit.memory.test_reference_binding import _Resolver

    world.client.app.state.reference_resolvers = {f: _Resolver() for f in resolvers}
    body = {
        "kind": "instruction",
        "scope": scope,
        "project_id": "group_run",
        "references": [{"ref": "fake:doc:spec@current", "required": True}],
    }
    if scope == "project":
        body["applicability"] = ANYWHERE
    else:
        body["target"] = {"cycle_id": "cyc_solo", "task_types": ["qa.test"]}

    response = world.as_("ada", Role.ADMIN).create(**body)

    assert response.status_code == status, response.text
    if stored:
        assert response.json()["revisions"][-1]["references"] == [stored]


class _BindsNothingFor:
    """A family that binds nothing for one project, as the repository family binds nothing for a
    Project with no source repository; and, as ``fails``, one whose answer can't be read."""

    def __init__(self, project: str | None = None, fails: bool = False) -> None:
        self.project, self.fails = project, fails

    async def binds_nothing_for(self, project_id: str) -> str | None:
        if self.fails:
            raise TimeoutError("the repository did not answer")
        return "it has no source repository" if project_id == self.project else None


@pytest.mark.parametrize(
    ("family", "status"),
    [(_BindsNothingFor("group_run"), 422), (_BindsNothingFor("prj-other"), 201),
     (_BindsNothingFor(fails=True), 201)],
    ids=["a-project-the-family-binds-nothing-for", "a-project-it-may-bind-for", "an-unread-answer"],
)  # fmt: skip
def test_a_project_instruction_names_only_what_some_unit_of_its_project_can_bind(
    world, family, status
):
    """SIP-0110 §5ac, contract 6. Bugs caught: a project instruction naming ``repo:file:…@current``
    accepted for a Project with no source repository, where every unit pins it unbound and a
    required one holds every task it applies to; the write refused for a project the family may
    bind for; an unread answer refusing a write the admission would bind or hold anyway."""
    world.client.app.state.reference_resolvers = {"repo": family}
    body = {
        "kind": "instruction", "scope": "project", "project_id": "group_run",
        "applicability": ANYWHERE,
        "references": [{"ref": "repo:file:CONTRIBUTING.md@current", "required": True}],
    }  # fmt: skip

    response = world.as_("ada", Role.ADMIN).create(**body)

    assert response.status_code == status, response.text
    if status == 422:
        assert "it has no source repository" in response.json()["detail"]["error"]["message"]


def test_a_revision_naming_what_no_unit_of_its_project_can_bind_is_refused(world):
    """§5ac, the revise path. Bug caught: a project instruction created plain, then revised to name
    a reference its project's units can never bind, past the check its creation meets."""
    world.client.app.state.reference_resolvers = {"repo": _BindsNothingFor("group_run")}
    body = {"kind": "instruction", "scope": "project", "project_id": "group_run",
            "applicability": ANYWHERE}  # fmt: skip
    created = world.as_("ada", Role.ADMIN).create(**body)
    rid = created.json()["record_id"]

    revised = world.client.post(
        f"{URL}/{rid}/revisions",
        json={"body": "Follow CONTRIBUTING.", "applicability": ANYWHERE,
              "references": [{"ref": "repo:file:CONTRIBUTING.md@current", "required": True}]},
    )  # fmt: skip

    assert created.status_code == 201, created.text
    assert revised.status_code == 422, revised.text
    assert "it has no source repository" in revised.json()["detail"]["error"]["message"]
