"""The scenario runner reads a started tree's client routes (SIP-0109 §24co, §8.3; SIP-0113 §4.1).

The app is started from its declaration in the disposable copy, as every evaluation's is, and each
route's page is read by the evaluator image's own Chromium on the app network, with the flags the
qa role reads a sample application's with (``route_rendering.DUMP_DOM_FLAGS``). The browser's
container is the fake's, answering each URL as a dumped DOM would.

What bugs would these catch?
- a page read by the image's driver, or by anything but its Chromium, or with flags of its own, so
  a product's route is read apart from a sample application's (and the image's tag would move);
- a page read at the app's name, which a UI server may refuse, or off the declared UI base;
- a catch-all route read as written (``*``), so no page is read at all (#2754);
- a parameterized route read with its parameter unfilled, or its seed sent through the scenarios'
  API prefix rather than to the app's own address (§10n ruling 8);
- a test id in a script's text counted as rendered;
- a page nothing read reported with test ids, or with no reason.
"""

from __future__ import annotations

import json

import httpx
import pytest

from squadops.campaigns.evaluator_trees import FileTree
from squadops.capabilities.handlers.route_rendering import DUMP_DOM_FLAGS
from squadops.sandbox.environment import EVALUATOR_BROWSER
from squadops.scenarios.runner import DeclaredStart, RouteReading, RouteRequest, TreeEvaluation
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerResult, ContainerSpec
from tests.unit.sandbox.test_scenario_runner import EVALUATOR, TREE, _Container, _runner

NETWORK = "squadops-sandbox-apps"
APP_IP = "10.89.0.7"
START = DeclaredStart(
    start=("python3", "-m", "shelfkeeper"),
    port=8000,
    ready_kind="http",
    ready_path="/healthz",
    ready_timeout_seconds=5.0,
    configuration_revision=4,
    api_port=8000,
    api_path="/api",
    ui_port=5173,
    ui_path="",
)
SEED = {
    "method": "POST",
    "path": "/shelves",
    "json": {"title": "Field notes"},
    "param": "shelf_id",
    "segment": ":shelf_id",
}


def _dom(*ids: str, script: str = "") -> str:
    body = "".join(f'<div data-testid="{i}"></div>' for i in ids)
    return f"<html><body>{body}<script>{script}</script></body></html>\n"


class _Browser(_Container):
    """The app network, with Chromium's dumped DOM answered by the URL it was pointed at."""

    def __init__(self, pages: dict[str, str], *, exit_code: int = 0, fails: bool = False) -> None:
        super().__init__()
        self.pages, self.exit_code, self.fails = pages, exit_code, fails

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        if spec.image == EVALUATOR and spec.entrypoint == EVALUATOR_BROWSER:
            self.specs.append(spec)
            if self.fails:
                raise ToolContainerError("docker: no such network")
            return ContainerResult("", self.exit_code, self.pages.get(spec.command[-1], ""), "")
        return await super().run(spec)


def _app(seen: list, *, created: dict | None = None, status: int = 201):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.host, request.url.port, request.url.path))
        if request.method == "POST":
            seen.append(json.loads(request.content))
            return httpx.Response(status, json=created if created is not None else {})
        return httpx.Response(200, text="ok")

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _ip(name: str) -> str:
    assert name.startswith("squadops-app-eval-")
    return APP_IP


async def _read(tmp_path, container, routes, *, start=START, app=None, **kw) -> TreeEvaluation:
    runner = _runner(
        tmp_path,
        container,
        app=app or _app([]),
        app_network=kw.pop("app_network", NETWORK),
        resolve_host=_ip,
    )
    return await runner.evaluate_tree(
        tree=TREE,
        tree_identity=FileTree.of(TREE).identity,
        executable={"run.sh"},
        stack=None,
        declared=start,
        scenarios=[],
        environment={},
        pages=[],
        routes=routes,
    )


def _url(path: str) -> str:
    return f"http://{APP_IP}:5173{path}"


async def test_each_route_is_read_by_the_images_chromium_at_the_apps_ip_on_the_ui_base(tmp_path):
    """The reading end to end. Bugs caught: the driver run instead of Chromium, or other flags;
    the page read at the app's name or off its UI base; the browser given a route out or a
    privilege; a catch-all read as ``*``; a test id in a script's text counted."""
    container = _Browser(
        {
            _url("/"): _dom("shelf-list", "add-link", script="h = '<p data-testid=\"ghost\">'"),
            _url("/__squadops_unmatched__"): _dom("not-found"),
        }
    )

    result = await _read(tmp_path, container, [RouteRequest("/"), RouteRequest("*")])

    assert result.routes == (
        RouteReading("/", "/", ("add-link", "shelf-list")),
        RouteReading("*", "/__squadops_unmatched__", ("not-found",)),
    )
    browsers = [s for s in container.specs if s.entrypoint == EVALUATOR_BROWSER]
    assert [s.command for s in browsers] == [
        [*DUMP_DOM_FLAGS, _url("/")],
        [*DUMP_DOM_FLAGS, _url("/__squadops_unmatched__")],
    ]
    for spec in browsers:
        assert (spec.network, spec.volumes, spec.env, spec.stdin) == (NETWORK, (), (), None)
        assert spec.cap_drop_all and spec.no_new_privileges
    # The app was torn down after the pages were read: nothing is left running.
    assert container.torn_down[-2:] == ["stop cid-detached", "remove cid-detached"]


async def test_a_parameterized_route_is_read_once_its_seed_brought_its_page_into_being(tmp_path):
    """§8.3's seed, sent to the app's own address with the path as the manifest writes it
    (§10n ruling 8), never through the declared API prefix. Bugs caught: the seed sent under
    ``/api``; the page read with ``:shelf_id`` unfilled; the seed's body lost."""
    seen: list = []
    container = _Browser({_url("/shelves/sh-41"): _dom("shelf-detail")})

    result = await _read(
        tmp_path,
        container,
        [RouteRequest("/shelves/:shelf_id", SEED)],
        app=_app(seen, created={"id": "sh-41"}),
    )

    assert result.routes == (
        RouteReading("/shelves/:shelf_id", "/shelves/sh-41", ("shelf-detail",)),
    )
    [app] = [s for s in container.specs if s.name and s.name.startswith("squadops-app-eval-")]
    posted = seen.index(("POST", app.name, 8000, "/shelves"))
    assert seen[posted + 1] == {"title": "Field notes"}


@pytest.mark.parametrize(
    ("container", "start", "app", "network", "route", "reading"),
    [
        (
            _Browser({}),
            DeclaredStart(**{**START.__dict__, "ui_port": None}),
            None,
            NETWORK,
            RouteRequest("/"),
            RouteReading(
                "/", None, None, "the start declares no ui_base, so no page of it can be read"
            ),
        ),
        (
            _Browser({}),
            START,
            None,
            NETWORK,
            RouteRequest("/shelves/:shelf_id"),
            RouteReading("/shelves/:shelf_id", None, None, "no seed brings its page into being"),
        ),
        (
            _Browser({}),
            START,
            "refused",
            NETWORK,
            RouteRequest("/shelves/:shelf_id", SEED),
            RouteReading(
                "/shelves/:shelf_id", None, None, "its seed's create was refused or named no id"
            ),
        ),
        (
            _Browser({}, exit_code=133),
            START,
            None,
            NETWORK,
            RouteRequest("/"),
            RouteReading("/", "/", None, "the browser exited 133"),
        ),
        (
            _Browser({}),
            START,
            None,
            NETWORK,
            RouteRequest("/"),
            RouteReading("/", "/", None, "the browser read no page"),
        ),
        (
            _Browser({}, fails=True),
            START,
            None,
            NETWORK,
            RouteRequest("/"),
            RouteReading(
                "/", "/", None, "the browser's container didn't run: docker: no such network"
            ),
        ),
    ],
    ids=[
        "no-ui-base",
        "no-seed",
        "a-seed-refused",
        "the-browser-crashed",
        "nothing-dumped",
        "the-container-didnt-run",
    ],
)
async def test_a_page_nothing_read_is_unread_with_why(
    tmp_path, container, start, app, network, route, reading
):
    """SIP-0096: a page never read has no test ids, and says why. Bugs caught: a page with no
    reading reported as an empty one (which the judgement would read as broken, not unread), or
    a crashed browser's partial output read as the page."""
    result = await _read(
        tmp_path,
        container,
        [route],
        start=start,
        app=_app([], status=409) if app == "refused" else None,
        app_network=network,
    )

    assert result.routes == (reading,)


async def test_off_the_app_network_or_without_the_image_no_page_is_read(tmp_path):
    """The browser reaches the app only on the app network, and only from the evaluator's image.
    Bug caught: a page read by a browser on the host, outside the sandbox's posture."""
    absent = _Browser({})
    absent._image_present = False

    off = await _read(tmp_path / "off", _Browser({}), [RouteRequest("/")], app_network=None)
    gone = await _read(tmp_path / "gone", absent, [RouteRequest("/")])

    assert off.routes == (
        RouteReading("/", None, None, "no app network, so no browser can reach the app"),
    )
    assert gone.routes == (
        RouteReading("/", None, None, f"the evaluator's image is absent: {EVALUATOR}"),
    )


def test_a_reading_crosses_the_wire_as_it_was_and_an_older_service_answers_none():
    """The runtime reads the service's answer (``TreeEvaluation.from_dict``). Bugs caught: an
    unread page's ``None`` arriving as an empty reading, so it is judged broken; an answer with no
    ``routes`` key (a service that predates §24co) failing, rather than leaving each route
    unread."""
    evaluation = TreeEvaluation(
        "t" * 64,
        started=True,
        routes=(RouteReading("/", "/", ("shelf-list",)), RouteReading("*", None, None, "why")),
    )
    wire = json.loads(json.dumps(evaluation.as_dict()))
    older = {k: v for k, v in wire.items() if k != "routes"}

    assert TreeEvaluation.from_dict(wire).routes == evaluation.routes
    assert TreeEvaluation.from_dict(older).routes == ()
    request = RouteRequest("/shelves/:shelf_id", SEED)
    assert RouteRequest.from_dict(json.loads(json.dumps(request.as_dict()))) == request


async def test_the_routes_are_read_after_the_quality_reading_and_the_scenarios(tmp_path):
    """A route's seed writes to the instance, so it comes last. Bug caught: the routes read first,
    so a seeded record changes the pages Lighthouse and axe measure, or what a scenario finds."""
    from tests.unit.sandbox.test_scenario_runner import _ANSWER, SCENARIO

    events: list = []

    class _Ordered(_Browser):
        async def run(self, spec):
            if spec.image == EVALUATOR and spec.entrypoint == EVALUATOR_BROWSER:
                events.append("route")
            elif spec.image == EVALUATOR:
                events.append("quality")
                return ContainerResult("", 0, json.dumps(_ANSWER) + "\n", "")
            return await super().run(spec)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/shelves":
            events.append("seed")
            return httpx.Response(201, json={"id": "sh-1"})
        if request.url.path.startswith("/api/counters/"):
            events.append("scenario")
            return httpx.Response(200, json={"name": "apples", "count": 1})
        return httpx.Response(200, text="ok")

    runner = _runner(
        tmp_path,
        _Ordered({}),
        app=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        app_network=NETWORK,
        resolve_host=_ip,
    )
    await runner.evaluate_tree(
        tree=TREE, tree_identity=FileTree.of(TREE).identity, executable={"run.sh"}, stack=None,
        declared=START, scenarios=[SCENARIO], environment={}, pages=["/"],
        routes=[RouteRequest("/shelves/:shelf_id", SEED)],
    )  # fmt: skip

    assert events == ["quality", "scenario", "seed", "route"]


async def test_a_route_is_read_under_the_declared_ui_bases_path(tmp_path):
    """SIP-0113 §4.1: a page is "a path from its declared UI base". Bug caught: a product served
    under a base path read at its origin's root, so every one of its pages reads broken."""
    container = _Browser({f"http://{APP_IP}:5173/shelf/add": _dom("add-view")})

    result = await _read(
        tmp_path,
        container,
        [RouteRequest("/add")],
        start=DeclaredStart(**{**START.__dict__, "ui_path": "/shelf"}),
    )

    assert result.routes == (RouteReading("/add", "/add", ("add-view",)),)
