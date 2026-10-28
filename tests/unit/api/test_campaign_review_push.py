"""The supervisor pushes a repository-backed Campaign's review request (SIP-0109 §24ci (b)).

Entered at ``POST /api/v1/campaigns/{id}/review-pushes``, as ``squadops campaigns push-review``
calls it, over the world ``test_branch_rebase`` builds: the shared fixture's Tally, a real managed
clone, real deliveries and a real rebase. The product the branch is pushed to is the fixture's own
repository, the Project's locator. The forge is a recorder, and the token is invented.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.campaigns import campaigns_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.campaigns.campaign_branch import campaign_ref
from squadops.campaigns.models import (
    CampaignOutcome,
    CampaignState,
    ControlOperation,
    ControlOutcome,
)
from tests.fixtures.shared_contract.repository import _git
from tests.unit.campaigns.builders import move
from tests.unit.campaigns.test_branch_rebase import _World
from tests.unit.campaigns.test_campaign_branch import CID

TOKEN = "github_pat_inventedForTheTest0001"
BRANCH = f"squadops/{CID}"
URL = "https://forge.example.invalid/tally/pull/7"


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


class _Forge:
    """Where a review request is opened: each call recorded, the token kept to compare."""

    def __init__(self) -> None:
        self.opened: list[dict] = []

    async def open_review_request(self, **request) -> str:
        self.opened.append(request)
        return URL


class _Pushing(_World):
    """The rebase world, with the campaign routes over it as the runtime mounts them."""

    def __init__(self, tmp_path) -> None:
        super().__init__(tmp_path)
        self.forge = _Forge()
        self.seat = (Role.CAMPAIGN_SUPERVISOR, "supervisor")
        app = FastAPI()
        world = self

        class InjectIdentity(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                role, user = world.seat
                request.state.identity = Identity(
                    user_id=user,
                    display_name=user,
                    roles=(role,),
                    scopes=tuple(sorted(scopes_for_roles((role,)))),
                    identity_type=IdentityType.HUMAN,
                )
                return await call_next(request)

        app.add_middleware(InjectIdentity)
        app.include_router(campaigns_router)
        register_domain_error_handlers(app)
        app.state.campaign_registry = self.campaigns
        app.state.project_registry = self.projects
        app.state.source_repository = self.clones
        app.state.review_requests = self.forge
        app.state.authz_port = KeycloakAuthzAdapter()
        self.client = TestClient(app)

    def push(self, key: str, token: str | None = TOKEN):
        body = {"idempotency_key": key, **({"token": token} if token is not None else {})}
        return self.client.post(f"/api/v1/campaigns/{CID}/review-pushes", json=body)

    def remote(self) -> str:
        return _git(self.repo.path, "rev-parse", f"refs/heads/{BRANCH}").strip()

    async def pushes(self) -> list:
        return [
            e
            for e in await self.campaigns.control_log(CID)
            if e.operation is ControlOperation.REVIEW_PUSHED
        ]


async def test_the_review_request_is_pushed_then_forced_under_its_lease_after_a_rebase(
    tmp_path, caplog
):
    """§24ci (b), the wiring. The first push opens the review request on the branch; after
    upstream moves and the branch is rebased, the next push replaces the branch under a lease on
    the first. Bugs caught:
    - the rebased head refused for good, so the owner's review never shows upstream's change;
    - a second review request opened per push, where the open one follows the branch;
    - the lease taken from anything but the last recorded push;
    - the invented token stored on a row, returned, or logged."""
    caplog.set_level(logging.DEBUG)
    world = _Pushing(tmp_path)
    await world.started()
    first = await world.accepted()

    opened = world.push("push-1")
    onto = world.upstream({"README.md": b"Tally, moved on\n"}, "docs")
    await world.reconciled(onto)
    await world.proposing()
    await world.service().drain()
    rebased = (await world.campaigns.get_campaign(CID)).accepted.commit
    forced = world.push("push-2")

    assert opened.status_code == 201, opened.text
    assert {k: opened.json()[k] for k in ("branch", "commit", "lease", "forced", "review_url")} == {
        "branch": BRANCH, "commit": first, "lease": None, "forced": False, "review_url": URL,
    }  # fmt: skip
    assert forced.status_code == 201, forced.text
    assert (forced.json()["commit"], forced.json()["lease"], forced.json()["forced"]) == (
        rebased,
        first,
        True,
    )
    assert world.remote() == rebased
    [request] = world.forge.opened
    assert (request["head"], request["base"], request["token"]) == (BRANCH, "main", TOKEN)
    rows = await world.pushes()
    assert [(r.binding["commit"], r.binding["lease"]) for r in rows] == [
        (first, None),
        (rebased, first),
    ]
    assert {r.actor for r in rows} == {"supervisor"}
    log = await world.campaigns.control_log(CID)
    assert TOKEN not in repr(log)
    assert TOKEN not in opened.text + forced.text
    assert TOKEN not in caplog.text


async def test_a_branch_someone_else_moved_is_refused_and_left_as_they_left_it(tmp_path):
    """§24ci (b): forced only with a lease. After the first push, someone else pushed to the
    review branch; the campaign then rebased. Bugs caught: their commit overwritten by the
    rebased head; a refusal recorded as a push, so the next lease names a commit the product
    never held."""
    world = _Pushing(tmp_path)
    await world.started()
    await world.accepted()
    assert world.push("push-1").status_code == 201
    _git(world.repo.path, "fetch", "-q", str(tmp_path / "cache" / "prj-tally.git"),
         f"+{world.repo.second_commit}:refs/heads/{BRANCH}")  # fmt: skip
    await world.reconciled(world.upstream({"README.md": b"moved\n"}, "docs"))
    await world.proposing()
    await world.service().drain()

    refused = world.push("push-2")

    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["error"]["code"] == "REVIEW_BRANCH_MOVED"
    assert TOKEN not in refused.text
    assert world.remote() == world.repo.second_commit
    assert len(await world.pushes()) == 1


async def test_a_retry_and_an_unchanged_head_answer_the_recorded_push(tmp_path):
    """The edges of idempotency: the same key again, and a new key with the head already
    pushed. Bugs caught: a second row for one push; a second review request opened."""
    world = _Pushing(tmp_path)
    await world.started()
    await world.accepted()

    first = world.push("push-1")
    again = world.push("push-1")
    unchanged = world.push("push-other")

    assert (again.json()["entry_id"], again.json()["replayed"]) == (first.json()["entry_id"], True)
    assert unchanged.json()["entry_id"] == first.json()["entry_id"]
    assert len(await world.pushes()) == 1 and len(world.forge.opened) == 1


@pytest.mark.parametrize("case", ["nothing-accepted", "patch-export", "ref-behind", "no-token"])
async def test_a_push_the_campaign_cant_make_is_refused_and_nothing_leaves(tmp_path, case):
    """Bugs caught: a branch with nothing upstream lacks pushed as a review request; a
    patch_export Project's branch pushed anyway; a ref behind its row pushed, so the review shows
    an older head than the control log; a push with no token falling back to a deploy token,
    which §24ci (b) says nothing stores for this."""
    import dataclasses

    world = _Pushing(tmp_path)
    await world.started()
    if case != "nothing-accepted":
        await world.accepted()
    if case == "patch-export":
        source = dataclasses.replace(
            world.projects.project.source, contribution_mode="patch_export"
        )
        world.projects.project = dataclasses.replace(world.projects.project, source=source)
    if case == "ref-behind":
        held = await world.branch()
        await world.clones.update_ref(
            "prj-tally",
            campaign_ref(CID),
            new_commit=world.repo.second_commit,
            expected_commit=held,
        )

    refused = world.push("push-1", token=None if case == "no-token" else TOKEN)

    assert refused.status_code == (422 if case == "no-token" else 409), refused.text
    if case != "no-token":
        assert refused.json()["detail"]["error"]["code"] == "REVIEW_PUSH_REFUSED"
    assert await world.pushes() == [] and world.forge.opened == []
    branches = _git(world.repo.path, "for-each-ref", "--format=%(refname)", "refs/heads/squadops")
    assert branches.strip() == ""


async def test_a_completed_campaign_is_pushed_at_its_close(tmp_path):
    """§24ci (b): "at the Campaign's close". Bug caught: the push recorded by an operation a
    completed campaign refuses, so the one moment the ruling names is the one it can't happen."""
    world = _Pushing(tmp_path)
    await world.started()
    first = await world.accepted()
    await world.campaigns.transition(
        CID,
        move(CampaignState.COMPLETED, "k-close", operation=ControlOperation.ABORT,
             outcome=CampaignOutcome.ABORTED),
    )  # fmt: skip

    pushed = world.push("push-close")

    assert pushed.status_code == 201, pushed.text
    [row] = await world.pushes()
    assert (row.outcome, row.binding["commit"], world.remote()) == (
        ControlOutcome.APPLIED,
        first,
        first,
    )


async def _rebased_again(world: _Pushing, content: bytes, message: str) -> str:
    """Upstream moves, the Project is reconciled there, and the branch is rebased at the next
    drain. Returns the rebased head."""
    await world.reconciled(world.upstream({"README.md": content}, message))
    await world.proposing(f"k-propose-{message}")
    await world.service().drain()
    return (await world.campaigns.get_campaign(CID)).accepted.commit


async def test_each_push_is_leased_on_the_one_before_it(tmp_path):
    """Three pushes across two rebases. Bug caught: the lease read from the first push rather
    than the last, so the third push is refused as a moved branch when nobody but the campaign
    moved it."""
    world = _Pushing(tmp_path)
    await world.started()
    first = await world.accepted()
    world.push("push-1")
    second = await _rebased_again(world, b"moved once\n", "once")
    world.push("push-2")
    third = await _rebased_again(world, b"moved twice\n", "twice")

    pushed = world.push("push-3")

    assert pushed.status_code == 201, pushed.text
    assert (pushed.json()["lease"], pushed.json()["commit"]) == (second, third)
    assert [r.binding["lease"] for r in await world.pushes()] == [None, first, second]
    assert world.remote() == third


async def test_a_retried_key_answers_its_push_even_after_the_head_moved(tmp_path):
    """The retry of a request whose response was lost, sent after the branch was rebased. Bug
    caught: the retry pushing the new head under the old key, whose row is then refused as a
    conflicting key, so the push lands on the product with no row and the next lease is stale."""
    world = _Pushing(tmp_path)
    await world.started()
    first = await world.accepted()
    original = world.push("push-1")
    await _rebased_again(world, b"moved\n", "once")

    retried = world.push("push-1")

    assert (retried.status_code, retried.json()["replayed"]) == (201, True)
    assert retried.json()["entry_id"] == original.json()["entry_id"]
    assert (retried.json()["commit"], world.remote()) == (first, first)
    assert len(await world.pushes()) == 1
