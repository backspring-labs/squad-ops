"""A repository-backed product's client routes, rendered on its candidate started from its declared
start, in the sandbox (SIP-0109 §24co, §24bv point 3, §8.3; SIP-0112 contract 7, H.7).

The runner is the sandbox's own (``ContainerScenarioRunner``), the browser's container the fake's,
answering each URL as Chromium's dumped DOM would. The product is invented: ``shelfkeeper``, made
from a blueprint, its approved manifest naming four routes and a create.

What bugs would these catch?
- a route held because its page was read, with nothing on it showing its view: the root anchor
  the judgement keys on (#659) taken from somewhere other than the approved manifest, or a route
  with no anchor read as rendered;
- a route the app doesn't serve read as unread, not broken, so an increment that dropped a page is
  only ever blocked, never rejected (the sample-app rule reads it broken);
- every route passed or skipped when nothing could start the product: no start declaration, one
  the runner can't read, a secret nobody approved, no runner, or a start that failed (contract 7);
- the candidate read other than the one delivery verified;
- the reason a route wasn't read lost from what the campaign reads.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from adapters.sandbox.scenario_runner import ContainerScenarioRunner
from squadops.campaigns.acceptance import Held, RouteResult
from squadops.campaigns.product_routes import (
    NO_ANCHOR,
    NO_ANCHOR_REQUESTED,
    NO_MANIFEST,
    ProductRoutes,
)
from squadops.campaigns.runner_acceptance import CandidateNotDelivered, SandboxTree
from squadops.projects.development_configuration import (
    Commands,
    DevelopmentConfiguration,
    EntryPoint,
    Readiness,
    StartDeclaration,
)
from squadops.projects.initialization import ProjectInitialization
from squadops.sandbox.models import compute_revision_id
from squadops.scenarios.declared_routes import DeclaredStartRoutes, product_start
from squadops.scenarios.runner import RunnerUnavailable
from tests.unit.campaigns.test_runner_acceptance_sandbox import HEAD, _profile
from tests.unit.sandbox.test_scenario_runner import EVALUATOR
from tests.unit.sandbox.test_scenario_runner_routes import _app, _Browser, _dom, _ip

APP_IP = "10.89.0.7"
ROUTES = ["/", "/add", "/shelves/:shelf_id", "*", "/about", "/tags/:tag"]
MANIFEST = """
version: 1
kind: interface_manifest
project_id: shelfkeeper
stack: fullstack_fastapi_react
entities:
  - name: Shelf
    fields:
      - { name: id, type: string, required: true, generated: true }
      - { name: title, type: string, required: true }
api:
  base_path: ""
  request_shapes:
    ShelfCreate:
      required: [title]
  endpoints:
    - { method: GET, path: /shelves, summary: list shelves, response: "list[Shelf]" }
    - { method: POST, path: /shelves, summary: add a shelf, request: ShelfCreate,
        response: Shelf, success_status: 201 }
    - { method: GET, path: "/shelves/{shelf_id}", summary: one shelf, response: Shelf }
frontend:
  routes:
    - { path: "/", view: ShelfListView, testids: [shelf-list, add-shelf-link] }
    - { path: "/add", view: AddShelfView, testids: [add-shelf-view, shelf-title-input] }
    - { path: "/shelves/:shelf_id", view: ShelfView, testids: [shelf-detail] }
    - { path: "*", view: NotFoundView, testids: [not-found-view] }
    - { path: "/about", view: AboutView }
    - { path: "/tags/:tag", view: TagView, testids: [tag-view] }
"""
INITIALIZATION = ProjectInitialization(
    "prj-shelf", "a" * 40, "main", "fullstack_fastapi_react", "sha256:m", MANIFEST, (), "owner",
    datetime(2026, 10, 28, 12, 0, tzinfo=UTC),
)  # fmt: skip
START = StartDeclaration(
    working_directory=".",
    start=("python3", "-m", "shelfkeeper", "serve"),
    readiness=Readiness("http", "http://127.0.0.1:8000/healthz", 20),
    entry_points=(
        EntryPoint("http_base", "http://127.0.0.1:8000/"),
        EntryPoint("ui_base", "http://127.0.0.1:5173/"),
    ),
    install=(("pip", "install", "-e", "."),),
)
#: Each page as a correct candidate renders it.
PAGES = {
    f"http://{APP_IP}:5173/": _dom("shelf-list", "add-shelf-link"),
    f"http://{APP_IP}:5173/add": _dom("add-shelf-view"),
    f"http://{APP_IP}:5173/shelves/sh-9": _dom("shelf-detail"),
    f"http://{APP_IP}:5173/__squadops_unmatched__": _dom("not-found-view"),
    f"http://{APP_IP}:5173/about": _dom(),
}
CHANGES = {"shelfkeeper/web.py": b"PAGES = 5\n"}


async def render_product_routes(*, runner, requested_routes=(), **kw) -> ProductRoutes:
    """The renderer the runtime root builds over the sandbox's runner, rendering once."""
    return await DeclaredStartRoutes(runner).render(requested_routes=requested_routes, **kw)


def _configuration(start=START) -> DevelopmentConfiguration:
    return DevelopmentConfiguration(
        project_id="prj-shelf",
        revision=6,
        validated_at_commit="a" * 40,
        project_type="service",
        target="python",
        stack="fullstack_fastapi_react",
        commands=Commands(working_directory=".", checks=(), start=start),
        instruction_sources=(),
    )


def _runner(tmp_path, container, seen=None) -> ContainerScenarioRunner:
    return ContainerScenarioRunner(
        container=container,
        root=tmp_path / "sandbox",
        image="sandbox:pinned",
        http_client_factory=_app(seen if seen is not None else [], created={"id": "sh-9"}),
        poll_interval_seconds=0.01,
        app_network="squadops-sandbox-apps",
        evaluator_image=EVALUATOR,
        resolve_host=_ip,
    )


def _candidate() -> tuple[SandboxTree, str]:
    tree = SandboxTree(HEAD, changes=CHANGES)
    return tree, compute_revision_id(tree.content, frozenset())


async def _render(tmp_path, *, pages=PAGES, configuration=None, runner="sandbox", **kw):
    candidate, revision = _candidate()
    return await render_product_routes(
        profile=kw.pop("profile", _profile(client_routes=ROUTES)),
        configuration=configuration or _configuration(),
        initialization=kw.pop("initialization", INITIALIZATION),
        runner=_runner(tmp_path, _Browser(pages)) if runner == "sandbox" else runner,
        candidate=candidate,
        verified_candidate_revision=kw.pop("verified", revision),
        requested_routes=kw.pop("requested", ()),
    )


def _held(routes: ProductRoutes) -> dict[str, tuple[str, str]]:
    return {r.path: (str(r.held), r.detail) for r in routes.results}


async def test_each_route_renders_its_view_on_the_candidate_started_from_its_declaration(tmp_path):
    """The reading end to end. Bugs caught: a route held with no anchor of its view on the page;
    the catch-all read as written; the parameterized route never brought into being; the started
    tree other than the candidate, or the start other than the declared one."""
    container = _Browser(PAGES)
    candidate, revision = _candidate()

    routes = await render_product_routes(
        profile=_profile(client_routes=ROUTES),
        configuration=_configuration(),
        initialization=INITIALIZATION,
        runner=_runner(tmp_path, container),
        candidate=candidate,
        verified_candidate_revision=revision,
    )

    assert _held(routes) == {
        "*": ("held", ""),
        "/": ("held", ""),
        "/about": ("blocked_unverified", NO_ANCHOR),
        "/add": ("held", ""),
        "/shelves/:shelf_id": ("held", ""),
        "/tags/:tag": ("blocked_unverified", ""),
    }
    # No create carries ``tag``: nothing brings its page into being, and the verdict says so.
    [tag] = [r for r in routes.results if r.path == "/tags/:tag"]
    assert tag.unseeded
    assert routes.record["start"] == {
        "tree_identity": candidate.file_tree.identity,
        "configuration_revision": 6,
        "started": True,
        "detail": None,
    }
    by_route = {r["route"]: r for r in routes.record["routes"]}
    assert by_route["/shelves/:shelf_id"] == {
        "route": "/shelves/:shelf_id",
        "source": "approved_manifest",
        "held": "held",
        "anchor": "shelf-detail",
        "read_at": "/shelves/sh-9",
        "seen": ["shelf-detail"],
        "detail": None,
    }
    # The declared start, in a copy of the candidate: its install, then its own start argv.
    setup, app = [s for s in container.specs if s.image == "sandbox:pinned"]
    assert (setup.command, app.command) == (
        ["pip", "install", "-e", "."],
        ["python3", "-m", "shelfkeeper", "serve"],
    )
    assert container.held[0] == candidate.content


@pytest.mark.parametrize(
    "page",
    [
        _dom("shelf-list"),
        _dom("shelf-title-input"),
        "<html><body><h1>404 Not Found</h1></body></html>",
        # The outside review's P2 on 8c09cd4f: a fallback page carrying the view's anchor only in an
        # inert template (or a noscript), which Chromium's dump keeps.
        '<html><body><p data-testid="not-found-view"></p><template><form '
        'data-testid="add-shelf-view"></form></template></body></html>',
        '<html><body><p data-testid="not-found-view"></p><noscript><form '
        'data-testid="add-shelf-view"></form></noscript></body></html>',
    ],
    ids=[
        "another-views-page",
        "its-root-anchor-missing",
        "the-app-doesnt-serve-it",
        "a-fallback-with-the-anchor-only-in-a-template",
        "a-fallback-with-the-anchor-only-in-a-noscript",
    ],
)
async def test_a_route_whose_page_lacks_its_views_root_anchor_is_broken(tmp_path, page):
    """§8.3 and #659, as a sample application reads it: a page read without its view's root
    anchor is broken, so the increment is rejected, not merely blocked. Bugs caught: any page
    read counted as rendered; one of the view's other anchors taken for its root; a page the app
    doesn't serve (its 404 page, or another view's) read as unread."""
    routes = await _render(tmp_path, pages={**PAGES, f"http://{APP_IP}:5173/add": page})

    [add] = [r for r in routes.results if r.path == "/add"]
    assert (add.held, add.missing) == (Held.BROKEN, ("add-shelf-view",))


async def test_a_page_the_browser_never_read_is_blocked_with_the_runners_reason(tmp_path):
    """SIP-0096: a page nothing read is unread, never broken, and the verdict says why. Bug
    caught: the runner's reason lost, so the campaign and a successor's brief read only "not
    rendered" for a page the browser couldn't read."""
    pages = {url: dom for url, dom in PAGES.items() if not url.endswith("/add")}

    routes = await _render(tmp_path, pages=pages)

    assert _held(routes)["/add"] == ("blocked_unverified", "the browser read no page")


def _with(start, **kw):
    return dataclasses.replace(start, **kw)


@pytest.mark.parametrize(
    ("configuration", "detail"),
    [
        (_configuration(start=None), "no start declaration: the Project declares no start"),
        (
            _configuration(
                start=_with(
                    START, evaluation_environment=(("SHELF_TOKEN", "secret://shelf_token"),)
                )
            ),
            "secret not available: the start declares SHELF_TOKEN, and no approval releases it",
        ),
        (
            _configuration(
                start=_with(START, readiness=Readiness("command", "python3 -m probe", 20))
            ),
            "no runner: no runner for readiness 'command'",
        ),
        (
            _configuration(start=_with(START, entry_points=())),
            "no start declaration: the declaration names no entry_points: contract 7 declares "
            "at least one",
        ),
    ],
    ids=["none", "a-secret-nobody-approved", "a-command-readiness", "malformed"],
)
async def test_without_a_start_the_runner_can_run_every_route_is_blocked_naming_why(
    tmp_path, configuration, detail
):
    """Contract 7 (SIP-0112 §8.2.1): no declaration, or one that can't be run, blocks every
    route with its reason, and nothing is started. Bugs caught: the gap relaxed, so routes pass
    or vanish; a secret started without, so a start that needed it reads as the app's failure."""
    container = _Browser(PAGES)
    candidate, revision = _candidate()

    routes = await render_product_routes(
        profile=_profile(client_routes=ROUTES),
        configuration=configuration,
        initialization=INITIALIZATION,
        runner=_runner(tmp_path, container),
        candidate=candidate,
        verified_candidate_revision=revision,
    )

    assert set(_held(routes).values()) == {("blocked_unverified", detail)}
    assert container.specs == []


class _FailingSetup(_Browser):
    async def run(self, spec):
        if spec.image == "sandbox:pinned":
            self.specs.append(spec)
            from squadops.tools.models import ContainerResult

            return ContainerResult("", 2, "", "pip: no matching distribution\n")
        return await super().run(spec)


class _Unavailable:
    async def evaluate_tree(self, **kw):
        raise RunnerUnavailable("the sandbox service is unreachable: refused")


@pytest.mark.parametrize(
    ("runner", "detail"),
    [
        ("failing", "start failed: setup step 1 exited 2"),
        (None, "no runner: this runtime runs no scenario runner"),
        (_Unavailable(), "no runner: the sandbox service is unreachable: refused"),
    ],
    ids=["a-start-that-fails", "no-runner", "the-runner-unreachable"],
)
async def test_a_start_that_fails_or_no_runner_blocks_every_route(tmp_path, runner, detail):
    """Contract 7's "start failed" and §4.1's "no runner". Bugs caught: a failed start read as
    every page broken, so the squad is told its pages are wrong when nothing ran; or no runner
    read as nothing to render."""
    if runner == "failing":
        runner = _runner(tmp_path, _FailingSetup(PAGES))

    routes = await _render(tmp_path, runner=runner)

    assert set(_held(routes).values()) == {("blocked_unverified", detail)}


@pytest.mark.parametrize(
    ("profile", "initialization", "expected"),
    [
        (_profile(), INITIALIZATION, {}),
        (_profile(client_routes=[]), INITIALIZATION, {}),
        (
            _profile(client_routes=["/"]),
            None,
            {"/": ("blocked_unverified", NO_MANIFEST)},
        ),
        (
            _profile(client_routes=["/"]),
            dataclasses.replace(INITIALIZATION, manifest="frontend: [unclosed"),
            {"/": ("blocked_unverified", NO_MANIFEST)},
        ),
    ],
    ids=["no-blueprint", "no-routes", "no-initialization", "an-unreadable-manifest"],
)
async def test_routes_apply_only_where_the_profile_names_them_and_need_their_anchors(
    tmp_path, profile, initialization, expected
):
    """§24bv point 3: not applicable where the profile names no route. Where it names some, the
    anchors are the approved manifest's: none readable blocks every route. Bug caught: a route
    judged with no anchor, which reads any page as rendered."""
    routes = await _render(tmp_path, profile=profile, initialization=initialization)

    assert _held(routes) == expected
    assert (routes.record is None) == (not expected)


async def test_a_candidate_other_than_the_verified_one_is_never_read(tmp_path):
    """§24cl item 4's rule, for the routes. Bug caught: the pages read on a tree delivery never
    verified, so an increment is accepted on another candidate's pages."""
    with pytest.raises(CandidateNotDelivered, match="the routes would be read on another tree"):
        await _render(tmp_path, verified="0" * 64)


def test_the_start_is_read_from_the_configuration_at_its_revision():
    """Contract 7, as the scenario runner runs it. Bug caught: the start read from another
    revision, or its ui_base dropped, so no page can be read."""
    start, why = product_start(_configuration())

    assert why is None
    assert (start.start, start.setup, start.configuration_revision) == (
        ("python3", "-m", "shelfkeeper", "serve"),
        (("pip", "install", "-e", "."),),
        6,
    )
    assert (start.port, start.api_port, start.ui_port, start.ready_path) == (
        8000,
        8000,
        5173,
        "/healthz",
    )


def test_a_blocked_routes_reason_reaches_what_the_campaign_reads():
    """The verdict's ``blocked`` lines are what the campaign and a successor's brief read. Bug
    caught: a product route's reason dropped, so the squad is told only "not rendered"."""
    from squadops.campaigns.acceptance import increment_acceptance

    acceptance = increment_acceptance(
        (), (), (RouteResult("/add", Held.BLOCKED_UNVERIFIED, detail="start failed: boom"),)
    )

    assert acceptance.blocked == ("route /add: not rendered: start failed: boom",)


@pytest.mark.parametrize(
    "page",
    [
        _dom("archive-view"),  # the new view renders: still no anchor the request names
        "<html><body><h1>500</h1></body></html>",  # the new route is broken
        None,  # the browser read nothing there
    ],
    ids=["it-renders", "it-is-broken", "nothing-read"],
)
async def test_a_route_the_change_request_adds_is_judged_and_never_held_without_an_anchor(
    tmp_path, page
):
    """The outside review of #2777 (P2): a route the candidate adds was outside the route checks,
    so it could be broken without affecting acceptance. The change request's ``client_route``
    criteria name it, so it's in the expected set beside the pinned ones. A product's request
    carries no manifest delta (§24bv point 5), so nothing names its view's anchor: it blocks,
    whatever its page shows, and the increment can't be accepted with it. Bugs caught: an added
    route left out; one held because its page was read; the pinned routes dropped when one is
    added, so removing an existing page goes unseen."""
    archive = f"http://{APP_IP}:5173/shelves/archive"
    pages = {**PAGES, **({archive: page} if page is not None else {})}

    routes = await _render(tmp_path, pages=pages, requested=["/shelves/archive", "/add"])

    held = _held(routes)
    assert held["/shelves/archive"] == ("blocked_unverified", NO_ANCHOR_REQUESTED)
    # The pinned routes are judged as before; a route the request names and the profile pins is
    # judged once, by its pinned anchor.
    assert (held["/"], held["/add"]) == (("held", ""), ("held", ""))
    by_route = {r["route"]: r for r in routes.record["routes"]}
    assert (by_route["/shelves/archive"]["source"], by_route["/add"]["source"]) == (
        "change_request",
        "approved_manifest",
    )


async def test_an_added_route_blocks_the_increment_and_a_dropped_pinned_one_rejects_it(tmp_path):
    """The verdict the campaign reads (``increment_acceptance``). Bugs caught: an increment with
    an added route accepted; a pinned route the candidate dropped read as anything but broken."""
    from squadops.campaigns.acceptance import IncrementVerdict, increment_acceptance

    added = await _render(tmp_path / "added", requested=["/shelves/archive"])
    dropped = await _render(
        tmp_path / "dropped",
        pages={**PAGES, f"http://{APP_IP}:5173/add": _dom("not-found-view")},
        requested=["/shelves/archive"],
    )

    blocked = increment_acceptance((), (), added.results)
    rejected = increment_acceptance((), (), dropped.results)
    assert blocked.verdict is IncrementVerdict.BLOCKED_UNVERIFIED
    assert f"route /shelves/archive: not rendered: {NO_ANCHOR_REQUESTED}" in blocked.blocked
    assert rejected.verdict is IncrementVerdict.REJECTED
    assert rejected.unmet == ("route /add: missing add-shelf-view",)


async def test_a_product_with_no_blueprint_judges_the_routes_its_request_adds(tmp_path):
    """A product whose profile names no route (no blueprint, so no manifest) can still add a page
    under its ui_base. Bug caught: no pinned routes read as nothing to judge, so the added page is
    never read and the increment is accepted on its criteria alone."""
    routes = await _render(tmp_path, profile=_profile(), initialization=None, requested=["/report"])

    assert _held(routes) == {"/report": ("blocked_unverified", NO_ANCHOR_REQUESTED)}
