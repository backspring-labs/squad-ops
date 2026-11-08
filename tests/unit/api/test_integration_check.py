"""``POST /api/v1/projects/{id}/integration-check`` (SIP-0112 H.30, #2862): the check the next
Campaign's draft makes, which syncs and re-validates where the Project's unintegrated set asks for
it, then answers the set that remains.

Entered at the route, as the runtime mounts it, for the supervisor's seat, over
``test_close_contribution``'s world: Tally, a real managed clone and real deliveries, a Campaign
closed by its accepted increment, and its contribution opened through the supervisor's route. The
owner's merge is made in the fixture's own repository, as the owner makes it on the forge. The forge
is the real GitHub adapter over a recorded transport, so every request it makes is seen; the
Project's records keep keys and replays as the Postgres registry does. Tokens are invented.
"""

from __future__ import annotations

import dataclasses
from typing import get_args

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from adapters.auth.keycloak.authz_adapter import KeycloakAuthzAdapter
from adapters.cycles.factory import create_project_registry
from adapters.tools.github_review_request import GitHubReviewRequests
from squadops.api.cycle_schemas import IntegrationCheckRowResponse
from squadops.api.error_handlers import register_domain_error_handlers
from squadops.api.routes.cycles.projects import router as projects_router
from squadops.auth.models import Identity, IdentityType, Role, scopes_for_roles
from squadops.projects.integration_check import WaitsOn
from tests.fixtures.shared_contract.repository import _git
from tests.unit.api.test_campaign_calibration_record import PROJECT
from tests.unit.api.test_unintegrated_increments import _OWNER, INCREMENT, _integrated_at
from tests.unit.campaigns.test_close_contribution import BRANCH, CID, _World

CHECK = f"/api/v1/projects/{PROJECT}/integration-check"
UNINTEGRATED = f"/api/v1/projects/{PROJECT}/unintegrated-increments"
HOST = "forge.example.invalid"
URL = f"https://{HOST}/tally-owner/tally/pull/9"
PULL = "/repos/tally-owner/tally/pulls/9"
TOKEN = "github_pat_inventedForTheCheck0003"
STORED = "github_pat_inventedStoredToken0004"


@pytest.fixture(autouse=True)
def _sandbox_provider(monkeypatch):
    """#1568: the create-time sandbox preflight reads the provider from the process env."""
    monkeypatch.setenv("SQUADOPS__SANDBOX__PROVIDER", "noop")


class _Forge:
    """Opens a review request as the fixture's recorder does, and reads one's state through the
    real GitHub adapter. ``pull`` is the forge's answer for the request, ``status`` its HTTP
    status, and ``requests`` every request the adapter made, with its method and token."""

    def __init__(self) -> None:
        self.opened: list[dict] = []
        self.requests: list[tuple[str, str, str]] = []
        self.pull: dict = {"state": "open", "merged": False, "merge_commit_sha": None}
        self.status = 200
        self.reader = GitHubReviewRequests(
            api_base=f"https://api.{HOST}", host=HOST, transport=httpx.MockTransport(self._answer)
        )

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(
            (request.method, request.url.path, request.headers.get("Authorization", ""))
        )
        if request.method == "GET" and request.url.path == PULL:
            return httpx.Response(self.status, json=self.pull if self.status == 200 else {})
        return httpx.Response(404, json={"message": "Not Found"})

    async def open_review_request(self, **request) -> str:
        self.opened.append(request)
        return URL

    async def review_request_state(self, *, url: str, token: str):
        return await self.reader.review_request_state(url=url, token=token)


class _CheckWorld(_World):
    """The close's world, with the forge above and the Project's writes a check makes: each
    contribution's state, a sync and a validation, keyed as the Postgres registry keys them (a
    key replays its record, and a key with other content is refused)."""

    def __init__(self, tmp_path) -> None:
        super().__init__(tmp_path)
        self.forge = _Forge()
        self.contribution = self.contributing(sandbox=self.reading_sandbox)
        self.keys: dict[str, tuple[str, object]] = {}
        self.validations: list[str] = []
        projects = self.projects
        projects.record_contribution_state = self._record_state
        projects.record_sync = self._record_sync
        projects.record_validation = self._record_validation

    async def _record_state(self, project_id, cycle_id, run_id, *, state, integrated_commit, actor):
        [held] = [c for c in self.book.recorded if (c.cycle_id, c.run_id) == (cycle_id, run_id)]
        updated = dataclasses.replace(held, state=state, integrated_commit=integrated_commit)
        self.book.recorded[self.book.recorded.index(held)] = updated
        return updated

    def _replayed(self, key: str, digest: str):
        held = self.keys.get(key)
        if held is None:
            return None
        assert held[0] == digest, f"idempotency key {key!r} recorded different content"
        return held[1]

    async def _record_sync(self, document, *, actor, idempotency_key, request_hash):
        stored = self._replayed(idempotency_key, request_hash)
        if stored is not None:
            return stored, True
        self.projects.syncs.append(document)
        self.keys[idempotency_key] = (request_hash, document)
        return document, False

    async def _record_validation(self, project_id, *, commit, diagnostic, actor, idempotency_key):
        if self._replayed(idempotency_key, f"validate:{project_id}") is not None:
            return self.projects.project, True
        assert commit is not None, "a READY Project's re-validation records the commit it adopts"
        self.validations.append(commit)
        self.projects.project = dataclasses.replace(
            self.projects.project,
            development_baseline_commit=commit,
            integrated_upstream_commit=commit,
        )
        self.keys[idempotency_key] = (f"validate:{project_id}", None)
        return self.projects.project, False

    async def contributed(self):
        """The Campaign closed by its increment, at an integrated commit that doesn't carry it, and
        its contribution opened by the supervisor: recorded pending."""
        await self.started()
        await self.accepted_with_criterion()
        await _integrated_at(self, self.repo.second_commit)
        client = self.client()
        opened = client.post(f"/api/v1/campaigns/{CID}/contributions", json={"token": TOKEN})
        assert opened.status_code == 201, opened.text
        assert opened.json()["contribution"]["review_url"] == URL
        return client

    def squash_merged(self, *, files: dict[str, str] | None = None) -> str:
        """The owner squash-merges the review request on the product, so the merge is a new
        commit no contribution names, and the forge says so. Returns the merge."""
        _git(self.repo.path, "merge", "-q", "--squash", BRANCH, env=_OWNER)
        for path, target in (files or {}).items():
            (self.repo.path / path).symlink_to(target)
            _git(self.repo.path, "add", path)
        _git(self.repo.path, "commit", "-q", "-m", "squash the campaign", env=_OWNER)
        merge = _git(self.repo.path, "rev-parse", "HEAD").strip()
        self.forge.pull = {"state": "closed", "merged": True, "merge_commit_sha": merge}
        return merge

    def refs(self) -> str:
        """Every ref of the product's repository, the forge's side of the clone."""
        return _git(self.repo.path, "for-each-ref", "--format=%(refname) %(objectname)")


async def test_a_merged_request_is_integrated_the_baseline_moves_and_the_draft_may_proceed(
    tmp_path,
):
    """The ruling's path, entered at the route the draft calls. Bugs caught:
    - a merge the owner made left ``contribution_pending``, so the draft waits on work that is in
      (#2862);
    - the sync recorded and the Project never re-validated, so the integrated commit stays put and
      the row moves to ``merged_not_synced`` instead of clearing;
    - a squash merge, which no contribution's commit is in, missed by reading ancestry alone;
    - the answer clear while the read route still lists the row."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    before = world.projects.project.integrated_upstream_commit
    merge = world.squash_merged()

    resp = client.post(CHECK, json={"token": TOKEN})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["clear"], body["remaining"]) == (True, [])
    assert (body["integrated_commit_before"], body["integrated_commit"]) == (before, merge)
    assert body["revalidated_at"] == merge == world.projects.project.development_baseline_commit
    [taken] = body["sync"]["document"]["contributions"]
    assert (taken["state"], taken["integrated_commit"]) == ("integrated", merge)
    assert (body["merge_state_unread"], body["validation_failed"]) == (None, None)
    assert "capture its inherited baseline" in body["next_step"]
    assert client.get(UNINTEGRATED).json() == []


async def test_the_check_only_reads_the_forge_and_pushes_nothing(tmp_path):
    """The ruling's limit. Bugs caught: a check that comments on, labels or merges the request, or
    opens another; a push to the product (a branch, a tag, a ref moved) from the sync's clone; the
    caller's token not the one the forge read is made with."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    world.squash_merged()
    refs, opened = world.refs(), list(world.forge.opened)

    assert client.post(CHECK, json={"token": TOKEN}).json()["clear"] is True

    assert world.forge.requests == [("GET", PULL, f"Bearer {TOKEN}")]
    assert world.forge.opened == opened
    assert world.refs() == refs


async def test_an_open_request_keeps_the_draft_waiting_and_names_the_row(tmp_path):
    """Bugs caught: an unmerged request read as integrated, so a draft starts without it; the row
    left out of the answer, or answered with no address, so the supervisor can't say what it
    waits on; the baseline moved with nothing integrated."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    before = world.projects.project

    body = client.post(CHECK, json={"token": TOKEN}).json()

    assert body["clear"] is False
    [row] = body["remaining"]
    assert (row["cycle_id"], row["standing"], row["review_url"], row["waits_on"]) == (
        INCREMENT,
        "contribution_pending",
        URL,
        "merge",
    )
    assert URL in row["clears_when"] and "refs/heads/main" in row["clears_when"]
    assert body["sync"]["document"]["contributions"][0]["state"] == "pending"
    assert (body["revalidated_at"], world.validations) == (None, [])
    assert world.projects.project == before


async def test_a_second_check_at_the_same_upstream_commit_records_no_second_sync(tmp_path):
    """The draft is asked for again before anything merged. Bug caught: a sync recorded at every
    draft, so the Project's sync history grows by one per question and a key the caller never
    chose collides with another's."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()

    first = client.post(CHECK, json={"token": TOKEN}).json()
    second = client.post(CHECK, json={"token": TOKEN}).json()

    assert len(world.projects.syncs) == 1
    assert (first["sync"]["replayed"], second["sync"]["replayed"]) == (False, True)
    assert second["sync"]["document"] == first["sync"]["document"]


async def test_with_no_token_the_merge_state_is_named_unread_never_read_as_not_merged(tmp_path):
    """Neither the request nor the deploy holds a token for the Project. Bugs caught: the sync run
    with no token, whose forge reading silently answers pending, so a merged request reads "not
    merged"; a check that skips the row and answers clear; no reason given."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    world.squash_merged()

    body = client.post(CHECK, json={}).json()

    assert body["clear"] is False
    assert body["merge_state_unread"]["reason"] == "no_token"
    assert [r["waits_on"] for r in body["remaining"]] == ["merge_state_unread"]
    assert "no_token" in body["remaining"][0]["clears_when"]
    assert (body["sync"], world.projects.syncs, world.forge.requests) == (None, [], [])


@pytest.mark.parametrize(
    ("passed", "held", "used"),
    [
        (TOKEN, {PROJECT: STORED}, TOKEN),  # the caller's own wins
        (None, {PROJECT: STORED}, STORED),  # else the deploy's, for this Project
    ],
)
async def test_the_token_is_the_requests_else_the_one_held_for_the_project(
    tmp_path, passed, held, used
):
    """The two sources the sync route reads, in its order. Bugs caught: the deploy's token used
    over the caller's; a Project's held token not used when the caller passes none, so a deploy
    that holds one never syncs at the draft."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    world.squash_merged()
    client.app.state.review_request_tokens = held

    body = client.post(CHECK, json={"token": passed} if passed else {}).json()

    assert body["clear"] is True
    assert world.forge.requests == [("GET", PULL, f"Bearer {used}")]


async def test_a_refused_forge_read_is_reported_and_nothing_is_validated(tmp_path):
    """The forge answers 503 while the merge is in the repository. Bugs caught: the refusal
    swallowed, so the row reads "not merged"; the Project re-validated anyway, moving its baseline
    on a sync that never recorded what it took; the sync retried in silence; the token echoed in
    the answer."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    world.squash_merged()
    world.forge.status = 503
    before = world.projects.project

    resp = client.post(CHECK, json={"token": TOKEN})

    body = resp.json()
    assert TOKEN not in resp.text  # the refusal's message never carries the token

    assert body["merge_state_unread"]["reason"] == "forge_unavailable"
    assert "503" in body["merge_state_unread"]["message"]
    assert [r["waits_on"] for r in body["remaining"]] == ["merge_state_unread"]
    assert (body["sync"], world.projects.syncs, world.validations) == (None, [], [])
    assert world.projects.project == before
    assert len(world.forge.requests) == 1


async def test_a_failed_revalidation_is_reported_and_the_next_check_tries_it_again(tmp_path):
    """The merge brings a symlink, which the sandbox can't carry: the sync records it integrated,
    and the re-validation refuses the tree. Bugs caught: the failure answered clear, or as a 500;
    the row's reason lost; the next check never retrying, so the row stands ``merged_not_synced``
    for good with nothing saying why."""
    world = _CheckWorld(tmp_path)
    client = await world.contributed()
    world.squash_merged(files={"latest-readme": "README.md"})

    first = client.post(CHECK, json={"token": TOKEN}).json()
    second = client.post(CHECK, json={"token": TOKEN}).json()

    for body in (first, second):
        assert body["clear"] is False
        assert body["validation_failed"]["reason"] == "capability_gap"
        [row] = body["remaining"]
        assert (row["standing"], row["waits_on"]) == ("merged_not_synced", "revalidation")
        assert "capability_gap" in row["clears_when"]
    assert (len(world.projects.syncs), world.validations) == (1, [])
    assert second["sync"] is None


async def test_with_nothing_pending_the_check_records_nothing_and_reads_no_forge(tmp_path):
    """A Campaign closed and never contributed. Bugs caught: a sync recorded for a draft with
    nothing to read, so every draft fetches and grows the Project's history; the row answered
    without saying the supervisor opens it."""
    world = _CheckWorld(tmp_path)
    await world.started()
    await world.accepted_with_criterion()

    body = world.client().post(CHECK, json={"token": TOKEN}).json()

    assert [(r["standing"], r["waits_on"]) for r in body["remaining"]] == [
        ("not_contributed", "contribution_not_opened")
    ]
    assert f"/api/v1/campaigns/{CID}/contributions" in body["remaining"][0]["clears_when"]
    assert (body["sync"], world.projects.syncs, world.forge.requests) == (None, [], [])


@pytest.mark.parametrize(
    ("role", "status"), [(Role.CAMPAIGN_TRIAGE, 403), (Role.VIEWER, 403), (Role.ADMIN, 200)]
)
async def test_only_a_seat_that_drafts_a_campaign_may_run_the_check(tmp_path, role, status):
    """The check writes a sync and moves a baseline. Bug caught: a read-only seat (triage, a
    viewer) able to run it."""
    world = _CheckWorld(tmp_path)
    await world.contributed()

    resp = world.client(role).post(CHECK, json={"token": TOKEN})

    assert resp.status_code == status, resp.text


def test_the_answer_names_every_wait_the_check_can_give():
    """Bug caught: a wait added to the check that the response refuses, so the route answers 500
    on the row it was added for."""
    field = IntegrationCheckRowResponse.model_fields["waits_on"].annotation
    assert set(get_args(field)) == {w.value for w in WaitsOn}


def test_a_sample_application_is_refused_never_answered_clear():
    """Bug caught: a Project with no repository answered ``clear``, which a draft reads as
    "everything integrated"."""
    app = FastAPI()

    class InjectIdentity(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            roles = (Role.CAMPAIGN_SUPERVISOR,)
            request.state.identity = Identity(
                user_id="supervisor", display_name="supervisor", roles=roles,
                scopes=tuple(sorted(scopes_for_roles(roles))), identity_type=IdentityType.HUMAN,
            )  # fmt: skip
            return await call_next(request)

    app.add_middleware(InjectIdentity)
    app.include_router(projects_router)
    register_domain_error_handlers(app)
    app.state.project_registry = create_project_registry("config")
    app.state.authz_port = KeycloakAuthzAdapter()
    # The runtime always wires these; a sample application's refusal reads none of them.
    app.state.source_repository = app.state.campaign_registry = object()
    app.state.goal_set_registry = object()

    resp = TestClient(app).post("/api/v1/projects/group_run/integration-check", json={})

    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["error"]["code"] == "NO_SOURCE_REPOSITORY"
