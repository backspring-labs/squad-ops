"""The scenario runner in the sandbox (SIP-0113 §4.1, §7 prediction 6; X-3b; #2414, #2421)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from adapters.sandbox.scenario_runner import ContainerScenarioRunner
from squadops.campaigns.evaluator_trees import FileTree
from squadops.scenarios.quality import NotMeasured, PageMeasure, QualityReading, QualityStatus
from squadops.scenarios.runner import DeclaredStart
from squadops.tools.exceptions import ToolContainerError
from squadops.tools.models import ContainerResult, ContainerSpec
from tests.unit.sandbox.test_container_backend import FakeContainer

EVALUATOR = "evaluator:pinned"
_T0 = datetime(2026, 10, 22, 5, 0, tzinfo=UTC)
TREE = {"app.py": "print('app')\n", "assets/logo.png": b"\x89PNG\x00", "run.sh": "#!/bin/sh\n"}
DECLARED = DeclaredStart(
    start=("python3", "app.py"),
    port=18407,
    ready_kind="http",
    ready_path="/healthz",
    ready_timeout_seconds=30.0,
    setup=(("make", "build"),),
    configuration_revision=3,
)
SCENARIO = {
    "scenario_id": "counts",
    "steps": [
        {"action": "http", "method": "POST", "path": "/counters/apples", "expect_status": 200}
    ],
    "checks": [{"check": "json", "step": 1, "path": "count", "equals": 1}],
}


class _Container(FakeContainer):
    """Records every spec, what the copy held at each run, and the teardown."""

    def __init__(self, setup_exit: int = 0, logs: str = "Traceback: boom\n", host_port=49999):
        super().__init__(
            ContainerResult("", setup_exit, "", "build failed\n" if setup_exit else "")
        )
        self.held: list[dict[str, bytes]] = []
        self.torn_down: list[str] = []
        self.evaluator_answer = ContainerResult("", 0, "", "")
        self._logs, self._host_port = logs, host_port

    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        return self._host_port

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        if spec.image == EVALUATOR:
            self.specs.append(spec)
            return self.evaluator_answer
        self._hold(spec)
        return await super().run(spec)

    async def run_detached(self, spec: ContainerSpec) -> str:
        self._hold(spec)
        return await super().run_detached(spec)

    def _hold(self, spec: ContainerSpec) -> None:
        root = Path(spec.volumes[0][0])
        self.held.append(
            {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        )
        (root / "written-by-the-app.db").write_text("state", encoding="utf-8")

    async def stop(self, container_id: str) -> None:
        self.torn_down.append(f"stop {container_id}")

    async def remove(self, container_id: str) -> None:
        self.torn_down.append(f"remove {container_id}")

    async def logs(self, container_id: str, tail: int | None = None) -> str:
        return self._logs


def _app(health: int = 200):
    counts: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1" and request.url.port == 49999
        if request.url.path in ("/healthz", "/"):  # each start's readiness path
            return httpx.Response(health, text="ok")
        name = request.url.path.rsplit("/", 1)[-1]
        counts[name] = counts.get(name, 0) + 1
        return httpx.Response(200, json={"name": name, "count": counts[name]})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _runner(tmp_path, container, app=None, **kw) -> ContainerScenarioRunner:
    return ContainerScenarioRunner(
        container=container,
        root=tmp_path / "sandbox",
        image="sandbox:pinned",
        http_client_factory=app or _app(),
        poll_interval_seconds=0.01,
        **{"app_network": None, "evaluator_image": EVALUATOR, **kw},
    )


async def _evaluate(runner, **kw):
    args = dict(
        tree=TREE,
        tree_identity=FileTree.of(TREE).identity,
        executable={"run.sh"},
        stack=None,
        declared=DECLARED,
        scenarios=[SCENARIO],
        environment={"TALLY_ADMIN_TOKEN": "evaluation-token"},
        pages=(),
    )
    args.update(kw)
    return await runner.evaluate_tree(**args)


async def test_a_declared_start_runs_its_scenarios_in_a_copy_that_is_gone_after(tmp_path):
    """Contract 3 and §7 prediction 6. Bug caught: the copy missing a binary file or an
    executable bit, the app's own writes surviving the evaluation, the evaluation secret leaking
    into the result, or the app left running."""
    container = _Container()

    result = await _evaluate(_runner(tmp_path, container))

    setup_spec, start_spec = container.specs
    assert (setup_spec.command, setup_spec.network) == (["make", "build"], "bridge")
    assert start_spec.publish_ports == (18407,) and start_spec.cap_drop_all
    assert ("TALLY_ADMIN_TOKEN", "evaluation-token") in start_spec.env
    assert container.held[0] == {
        p: (c.encode() if isinstance(c, str) else c) for p, c in TREE.items()
    }
    assert (result.started, [r.result for r in result.runs]) == (True, ["passed"])
    assert result.configuration_revision == 3  # the revision that started it, on the record
    assert "evaluation-token" not in json.dumps(result.as_dict())
    assert container.torn_down == ["stop cid-detached", "remove cid-detached"]
    assert not any((tmp_path / "sandbox" / "evaluations").iterdir())


async def test_a_blueprint_tree_starts_by_its_stacks_environment_contract(tmp_path):
    """A blueprint Project starts "by its stack's probe and render profiles, as today" (§4.1).
    Bug caught: a blueprint started by a guessed command, or held to a 2xx a scaffolded app
    never promised (#520/#622: any response is ready); or, since #2416, the canonical stack's
    built pages not served beside its backend, so Lighthouse and axe have nothing to load."""
    container = _Container()

    result = await _evaluate(
        _runner(tmp_path, container, app=_app(health=404)),
        stack="fullstack_fastapi_react",
        declared=None,
    )

    install, build, start = (s.command for s in container.specs if s.image != EVALUATOR)
    assert install[:2] == ["sh", "-c"] and "pip install" in install[2]
    assert build == ["npm", "--prefix", "frontend", "run", "build"]
    assert start[:2] == ["sh", "-c"] and "uvicorn backend.main:app" in start[2]
    assert "& exec frontend/node_modules/.bin/vite preview frontend" in start[2]
    assert container.specs[2].publish_ports == (8000, 4173)
    assert result.started


@pytest.mark.parametrize(
    ("container", "app", "detail"),
    [
        (_Container(setup_exit=2), _app(), "setup step 1 exited 2"),
        (_Container(), _app(health=503), "not ready at /healthz"),
    ],
    ids=["setup-fails", "readiness-times-out"],
)
async def test_a_tree_that_cannot_start_runs_no_scenario_and_says_why(
    tmp_path, container, app, detail
):
    """Contract 7's readiness timeout. Bug caught: scenarios run against an app that never
    became ready, read as the product's failures; or a failed start's evidence (the build's
    output, the app's own last lines) dropped."""
    result = await _evaluate(
        _runner(tmp_path, container, app=app, blueprint_ready_timeout_seconds=0.05),
        declared=DeclaredStart(**{**DECLARED.__dict__, "ready_timeout_seconds": 0.05}),
    )

    assert (result.started, result.runs) == (False, ())
    assert detail in result.start_detail
    assert result.startup_diagnostics in (("build failed",), ("Traceback: boom",))
    assert not any((tmp_path / "sandbox" / "evaluations").iterdir())


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (dict(tree_identity="0" * 64), "not its declared"),
        (dict(executable={"missing.sh"}), "doesn't carry"),
        (dict(declared=None, stack=None), "names its stack"),
    ],
    ids=["identity-mismatch", "executable-not-in-tree", "no-start-at-all"],
)
async def test_a_request_the_runner_cannot_trust_runs_nothing(tmp_path, change, message):
    """Bug caught: a tree evaluated under an identity it doesn't hash to, so the record names a
    tree that never ran."""
    container = _Container()

    with pytest.raises(ValueError, match=message):
        await _evaluate(_runner(tmp_path, container), **change)
    assert container.specs == []


@pytest.mark.parametrize(
    "key", ["../other/workspace/x", "/abs/x", "a/../b", "./app.py"], ids=str.strip
)
async def test_a_tree_key_that_would_write_outside_the_copy_is_refused_and_nothing_runs(
    tmp_path, key
):
    """Contract 3: never the live tree (blocker 2 of #2450's review). The tree is a squad's
    files from the vault. Bug caught: ``../<cycle>/workspace/x`` or an absolute key written
    outside the copy, into a cycle's live tree."""
    container = _Container()
    tree = {**TREE, key: "escaped\n"}

    with pytest.raises(ValueError, match="not a workspace-relative path|normal form"):
        await _evaluate(
            _runner(tmp_path, container), tree=tree, tree_identity=FileTree.of(tree).identity
        )

    assert container.specs == []
    assert not (tmp_path / "other").exists() and not (tmp_path / "sandbox").exists()


async def test_a_secret_the_app_logs_or_answers_with_never_reaches_the_result(tmp_path):
    """Q40: never in a log, a record or an agent's input (blocker 3 of #2450's review). Bug
    caught: an app that logs its environment, or answers with the token, puts the evaluation
    secret into the start's last lines or a step's detail, and so into the evaluation record."""
    leaky = "TALLY_ADMIN_TOKEN=evaluation-token\nTraceback: boom\n"
    echoing = DeclaredStart(**{**DECLARED.__dict__, "ready_timeout_seconds": 0.05})

    not_ready = await _evaluate(
        _runner(tmp_path / "a", _Container(logs=leaky), app=_app(health=503)), declared=echoing
    )
    answered = await _evaluate(
        _runner(tmp_path / "b", _Container(), app=_echo("evaluation-token")),
        scenarios=[
            {**SCENARIO, "checks": [{"check": "json", "step": 1, "path": "count", "equals": 1}]}
        ],
    )

    for result in (not_ready, answered):
        assert "evaluation-token" not in json.dumps(result.as_dict())
    assert not_ready.startup_diagnostics == ("TALLY_ADMIN_TOKEN=[redacted]", "Traceback: boom")
    assert "[redacted]" in answered.runs[0].detail


def _echo(secret: str):
    """An app whose answer carries the token it was started with."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, text="ok")
        return httpx.Response(200, json={"count": f"token {secret}"})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _hold(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.read()  # an app's listener: the connection stays open until the client goes


async def _drop(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    writer.close()  # Docker's port proxy with nothing behind it: accept, then close at once


@pytest.mark.parametrize(
    ("listener", "ready"),
    [(_hold, True), (_drop, False), (None, False)],
    ids=["the-app-listens", "only-the-proxy-accepts", "nothing-listens"],
)
async def test_a_tcp_readiness_is_a_connection_the_app_holds(tmp_path, listener, ready):
    """Contract 7's ``tcp`` kind (blocker 1 of #2450's review). Bug caught: a tcp declaration
    refused; or read as ready with nothing listening, including when Docker's proxy accepts on
    the published port before the app binds, so scenarios run against no app (read live on the
    Spark: step 1 answered "Server disconnected without sending a response")."""
    server = await asyncio.start_server(listener or _drop, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    if listener is None:
        server.close()
        await server.wait_closed()
    declared = DeclaredStart(
        **{**DECLARED.__dict__, "ready_kind": "tcp", "ready_path": "", "ready_timeout_seconds": 0.6}
    )
    try:
        result = await _evaluate(
            _runner(tmp_path, _Container(host_port=port), app=_any_port_app()), declared=declared
        )
    finally:
        server.close()

    assert result.started is ready
    if not ready:
        assert "not ready at port 18407" in result.start_detail


def _any_port_app():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "apples", "count": 1})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_a_short_secret_is_scrubbed_from_free_text_only(tmp_path):
    """The MacBook lane's review of #2450. Bug caught: a secret like ``pass`` rewriting a
    ``passed`` result into ``[redacted]ed``, or a tree identity or scenario id that happens to
    contain it, so the record no longer says what ran."""
    result = await _evaluate(
        _runner(tmp_path, _Container(), app=_echo("pass")),
        environment={"TALLY_ADMIN_TOKEN": "pass"},
        scenarios=[{**SCENARIO, "scenario_id": "passes-through"}],
    )

    [run] = result.runs
    assert (run.scenario_id, run.result) == ("passes-through", "failed")
    assert "pass" not in (run.detail or "").replace("[redacted]", "")
    assert result.tree_identity == FileTree.of(TREE).identity


class _OnTheNetwork(_Container):
    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        raise AssertionError("an app on the app network publishes no host port")


async def test_the_app_holding_the_secrets_runs_on_the_app_network_by_name(tmp_path):
    """The MacBook lane's review of #2460, binding #2450: inside a deploy the service can't reach
    an app on the host's loopback, and an app holding the evaluation secrets must have no route
    out. Bug caught: the runner still publishing to loopback on the default bridge, so every
    evaluation in a deploy fails to connect while its secrets sit on a network with egress."""
    container, seen = _OnTheNetwork(), []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.url.port))
        if request.url.path == "/healthz":
            return httpx.Response(200, text="ok")
        return httpx.Response(200, json={"name": "apples", "count": 1})

    result = await _evaluate(
        _runner(
            tmp_path,
            container,
            app=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            app_network="squadops-sandbox-apps",
        )
    )

    setup_spec, start_spec = container.specs
    assert setup_spec.network == "bridge"  # dependencies install with egress, and no secrets
    assert (start_spec.network, start_spec.publish_ports) == ("squadops-sandbox-apps", ())
    assert ("TALLY_ADMIN_TOKEN", "evaluation-token") in start_spec.env
    assert seen and set(seen) == {(start_spec.name, 18407)}
    assert [r.result for r in result.runs] == ["passed"]


def _api_app(port: int, prefix: str, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.port, request.url.path))
        if request.url.path in ("/", "/healthz"):
            return httpx.Response(200, text="ok")
        if request.url.port != port or not request.url.path.startswith(prefix + "/counters/"):
            return httpx.Response(404, json={"detail": "not here"})
        return httpx.Response(200, json={"name": "apples", "count": 1})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


class _TwoPorts(_Container):
    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        return {18407: 49999, 18410: 49998, 8000: 49999}[container_port]


async def test_a_nextjs_blueprint_reaches_the_prds_paths_under_its_api_prefix(tmp_path):
    """One suite across the window's two stacks (#2464). Bug caught: a scenario's PRD path,
    ``/counters/apples``, sent to a Next.js app at the root, where its API routes aren't, so
    every API scenario on that stack fails 404 and reads as the product's failure."""
    seen: list = []

    result = await _evaluate(
        _runner(tmp_path, _Container(), app=_api_app(49999, "/api", seen)),
        stack="nextjs_ts",
        declared=None,
    )

    assert [r.result for r in result.runs] == ["passed"]
    assert (49999, "/api/counters/apples") in seen


async def test_a_declared_api_on_its_own_port_and_path_is_published_and_reached(tmp_path):
    """#2421's entry points. Bug caught: only the readiness port published, so an API declared
    on another port can't be reached, or its path prefix dropped."""
    seen: list = []
    container = _TwoPorts()
    declared = DeclaredStart(**{**DECLARED.__dict__, "api_port": 18410, "api_path": "/v1"})

    result = await _evaluate(
        _runner(tmp_path, container, app=_api_app(49998, "/v1", seen)), declared=declared
    )

    assert container.specs[-1].publish_ports == (18407, 18410)
    assert [r.result for r in result.runs] == ["passed"]
    assert (49998, "/v1/counters/apples") in seen


async def test_on_the_app_network_a_declared_api_is_reached_by_name_on_its_own_port(tmp_path):
    """#2466 with #2471: the API addressed as ``http://<name>:<api_port><api_path>``. Bug caught:
    the API base still built on loopback's published port, so in a deploy every API scenario
    fails to connect, or the API's port published from a network with no route out."""
    seen: list = []
    container = _OnTheNetwork()
    declared = DeclaredStart(**{**DECLARED.__dict__, "api_port": 18410, "api_path": "/v1"})

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.url.port, request.url.path))
        if request.url.path == "/healthz":
            return httpx.Response(200, text="ok")
        return httpx.Response(200, json={"name": "apples", "count": 1})

    result = await _evaluate(
        _runner(
            tmp_path,
            container,
            app=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            app_network="squadops-sandbox-apps",
        ),
        declared=declared,
    )

    spec = container.specs[-1]
    assert (spec.network, spec.publish_ports) == ("squadops-sandbox-apps", ())
    assert (spec.name, 18407, "/healthz") in seen
    assert (spec.name, 18410, "/v1/counters/apples") in seen
    assert [r.result for r in result.runs] == ["passed"]


# --------------------------------------------------------------------------------------------
# SIP-0113 §4.2 (#2416): Lighthouse and axe on the declared pages, before any scenario
# --------------------------------------------------------------------------------------------

#: SIP-0113 §10y: what the evaluator's -7 reads beside the scores and rule counts, as its driver
#: answers (``infra/evaluator/page_reading.mjs``). Invented values.
_FINER = {
    "axe_nodes": {"critical": 0, "serious": 0, "moderate": 5, "minor": 0},
    "failing": {
        "accessibility": ["heading-order"],
        "best_practices": [],
        "environment": ["is-on-https", "redirects-http"],
        "axe": ["heading-order", "region"],
    },
    "errored": {"accessibility": [], "best_practices": [], "environment": []},
    "best_practices_app": 1,
    "best_practices_app_error": None,
}
_ANSWER = {
    "pages": [
        {
            "path": "/",
            "lighthouse": {"performance": 0.93, "accessibility": 0.96, "best-practices": 0.78},
            "axe": {"critical": 0, "serious": 0, "moderate": 2, "minor": 0},
            **_FINER,
            "error": None,
        }
    ]
}
_MEASURED = QualityReading(
    QualityStatus.MEASURED,
    pages=(
        PageMeasure(
            "/",
            {"performance": 0.93, "accessibility": 0.96, "best_practices": 0.78},
            {"critical": 0, "serious": 0, "moderate": 2, "minor": 0},
            axe_nodes={"critical": 0, "serious": 0, "moderate": 5, "minor": 0},
            failing={
                "accessibility": ("heading-order",),
                "best_practices": (),
                "environment": ("is-on-https", "redirects-http"),
                "axe": ("heading-order", "region"),
            },
            errored={"accessibility": (), "best_practices": (), "environment": ()},
            best_practices_app=1,
        ),
    ),
    evaluator=EVALUATOR,
)


def _ui_app(events: list, *, ui_answers: bool = True):
    """The app by name on the app network: its UI on 4173 (Vite's preview refuses the name with
    a 403, which is still an answer), its backend on the app port."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.port in (4173, 18409):
            if not ui_answers:
                raise httpx.ConnectError("refused")
            return httpx.Response(403, text="Blocked request. This host is not allowed.")
        if request.url.path in ("/", "/healthz"):
            return httpx.Response(200, text="ok")
        events.append("scenario")
        return httpx.Response(200, json={"name": "apples", "count": 1})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


class _Measured(_OnTheNetwork):
    """On the app network, with the evaluator answering as scripted."""

    def __init__(self, events: list, answer: ContainerResult) -> None:
        super().__init__()
        self.events, self.evaluator_answer = events, answer

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        if spec.image == EVALUATOR:
            self.events.append("lint" if b'"lint"' in spec.stdin else "evaluator")
        return await super().run(spec)


async def test_the_pages_are_measured_on_the_app_network_before_any_scenario_writes(tmp_path):
    """§4.2 and A2/A3. Bug caught: the pages measured after the scenarios, so each tree's
    reading depends on what its scenarios wrote; the evaluator given the app's secrets, a mounted
    path or a route out; or its request lost, so it measures nothing."""
    events: list = []
    container = _Measured(events, ContainerResult("", 0, json.dumps(_ANSWER) + "\n", ""))

    result = await _evaluate(
        _runner(tmp_path, container, app=_ui_app(events), app_network="squadops-sandbox-apps"),
        stack="fullstack_fastapi_react",
        declared=None,
        pages=("/",),
    )

    start = container.specs[2]
    [evaluator] = [s for s in container.specs if s.image == EVALUATOR and b"base_url" in s.stdin]
    assert json.loads(evaluator.stdin) == {"base_url": f"http://{start.name}:4173", "pages": ["/"]}
    assert (evaluator.network, evaluator.volumes, evaluator.env) == (
        "squadops-sandbox-apps",
        (),
        (),
    )
    assert evaluator.cap_drop_all and evaluator.no_new_privileges
    assert result.quality == _MEASURED
    assert events == ["evaluator", "scenario", "lint"]
    assert [r.result for r in result.runs] == ["passed"]


_NO_ANSWER = ContainerResult("", 0, "", "")


@pytest.mark.parametrize(
    ("network", "image_present", "answer", "ui_answers", "pages", "reason", "detail"),
    [
        (None, True, _NO_ANSWER, True, ("/",), NotMeasured.NO_APP_NETWORK, None),
        ("apps", False, _NO_ANSWER, True, ("/",), NotMeasured.EVALUATOR_ABSENT, EVALUATOR),
        (
            "apps",
            True,
            ContainerResult("", 1, "", "Error: chromium crashed\n"),
            True,
            ("/",),
            NotMeasured.EVALUATOR_FAILED,
            "chromium crashed",
        ),
        (
            "apps",
            True,
            ContainerResult("", 0, '{"pages": []}\n', ""),
            True,
            ("/",),
            NotMeasured.EVALUATOR_FAILED,
            "other pages",
        ),
        (
            # §10y: a scored page without the finer reading (a driver older than -7's under its
            # tag) is refused, never read as zero nodes and no failing id.
            "apps",
            True,
            ContainerResult(
                "",
                0,
                json.dumps(
                    {"pages": [{k: v for k, v in _ANSWER["pages"][0].items() if k not in _FINER}]}
                )
                + "\n",
                "",
            ),
            True,
            ("/",),
            NotMeasured.EVALUATOR_FAILED,
            "page /: no axe_nodes, failing, errored, best_practices_app, which -7's evaluator reads",
        ),
        ("apps", True, _NO_ANSWER, False, ("/",), NotMeasured.UI_NOT_READY, "nothing answered"),
        ("apps", True, _NO_ANSWER, True, (), NotMeasured.NO_DECLARED_PAGE, None),
    ],
    ids=[
        "a-host-run",
        "no-evaluator-image",
        "the-evaluator-fails",
        "it-answers-for-other-pages",
        "a-scored-page-without-the-finer-reading",
        "the-ui-never-answers",
        "no-declared-page",
    ],
)
async def test_a_measure_that_cant_run_says_why_and_the_scenarios_still_run(
    tmp_path, network, image_present, answer, ui_answers, pages, reason, detail
):
    """§4.2: not measured is a record that the measure didn't run, never evidence. Bug caught:
    a failed measure read as a clean page, or one that keeps the scenarios from running."""
    events: list = []
    container = _Measured(events, answer) if network else _Container()
    container._image_present = image_present

    result = await _evaluate(
        _runner(
            tmp_path,
            container,
            app=_ui_app(events, ui_answers=ui_answers),
            app_network=network,
            blueprint_ready_timeout_seconds=0.05,
        ),
        stack="fullstack_fastapi_react",
        declared=None,
        pages=pages,
    )

    assert (result.quality.status, result.quality.reason) == (QualityStatus.NOT_MEASURED, reason)
    assert detail is None or detail in result.quality.detail
    assert [r.result for r in result.runs] == ["passed"]


async def test_a_declared_project_is_measured_at_its_ui_base_and_serves_its_own_pages(tmp_path):
    """Contract 7's ``ui_base``. Bug caught: a product's own start wrapped in the canonical
    stack's preview server, or its pages measured at the readiness port."""
    events: list = []
    container = _Measured(events, ContainerResult("", 0, json.dumps(_ANSWER) + "\n", ""))
    declared = DeclaredStart(**{**DECLARED.__dict__, "ui_port": 18409, "ui_path": "/app"})

    result = await _evaluate(
        _runner(tmp_path, container, app=_ui_app(events), app_network="squadops-sandbox-apps"),
        declared=declared,
        pages=("/",),
    )

    start = container.specs[1]
    [evaluator] = [s for s in container.specs if s.image == EVALUATOR]
    assert start.command == list(DECLARED.start)
    assert json.loads(evaluator.stdin)["base_url"] == f"http://{start.name}:18409"
    assert result.quality.status is QualityStatus.MEASURED


# --------------------------------------------------------------------------------------------
# SIP-0113 §4.2 (#2416): #1937's lint over the tree as delivered, in the evaluator's image
# --------------------------------------------------------------------------------------------

_LINT_ANSWER = {
    "lint": {
        "root": "/tmp/lint-abc",
        "ruff": {
            "version": "ruff 0.16.6",
            "exit": 0,
            "stdout": json.dumps(
                [{"code": "F401", "filename": "/tmp/lint-abc/app.py"}] * 2
                + [{"code": "E501", "filename": "/tmp/lint-abc/app.py"}]
            ),
            "stderr": "",
        },
        "eslint": None,
    }
}


class _Linted(_Container):
    """The evaluator answering a lint request as scripted, and nothing else differently."""

    def __init__(self, answer: ContainerResult, **kw) -> None:
        super().__init__(**kw)
        self.lint_answer = answer

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        if spec.image == EVALUATOR and b'"lint"' in spec.stdin:
            self.specs.append(spec)
            return self.lint_answer
        return await super().run(spec)


async def test_a_blueprints_tree_is_linted_as_delivered_with_no_network_and_one_source(tmp_path):
    """§4.2 and #1937. Bug caught: the lint read the copy after its install, so the app's
    dependencies count as its findings; the tools given a route out; #1937's rules or ESLint
    config copied into a second place, free to drift; or a binary file sent as text."""
    from squadops.capabilities.delivered_lint import RUFF_ARGS, eslint_runner_source

    container = _Linted(ContainerResult("", 0, json.dumps(_LINT_ANSWER) + "\n", ""))

    result = await _evaluate(
        _runner(tmp_path, container), stack="fullstack_fastapi_react", declared=None
    )

    [lint_spec] = [s for s in container.specs if s.image == EVALUATOR]
    request = json.loads(lint_spec.stdin)["lint"]
    assert set(request["files"]) == {"app.py", "run.sh"}  # the PNG isn't text
    assert request["ruff_args"] == list(RUFF_ARGS)
    assert request["eslint_runner"] == eslint_runner_source()
    assert (lint_spec.network, lint_spec.volumes, lint_spec.env) == ("none", (), ())
    assert result.lint.status is QualityStatus.MEASURED
    assert result.lint.reading["by_rule"] == {"ruff:E501": 1, "ruff:F401": 2}
    assert result.lint.reading["by_file"] == {"app.py": 3}
    assert result.lint.evaluator == EVALUATOR


@pytest.mark.parametrize(
    ("container", "declared", "reason", "detail"),
    [
        (_Linted(ContainerResult("", 0, "", "")), DECLARED, NotMeasured.NOT_A_SCAFFOLD_STACK, None),
        (
            _Linted(ContainerResult("", 2, "", "ruff: not found\n")),
            None,
            NotMeasured.EVALUATOR_FAILED,
            "ruff: not found",
        ),
        (_Linted(ContainerResult("", 0, "{}\n", "")), None, NotMeasured.EVALUATOR_FAILED, "answer"),
    ],
    ids=["a-declared-project", "the-evaluator-fails", "an-answer-with-no-lint"],
)
async def test_a_lint_that_cant_be_read_says_why(tmp_path, container, declared, reason, detail):
    """§4.2: off the scaffold stacks lint is not measured, and the product's own linter is never
    read in its place. Bug caught: a declared Project linted by #1937's rules it never chose, or
    a failed lint read as a clean tree."""
    result = await _evaluate(
        _runner(tmp_path, container),
        stack=None if declared else "fullstack_fastapi_react",
        declared=declared,
    )

    assert (result.lint.status, result.lint.reason) == (QualityStatus.NOT_MEASURED, reason)
    assert detail is None or detail in result.lint.detail
    if declared is not None:
        assert [s for s in container.specs if s.image == EVALUATOR] == []


async def test_a_tree_that_cant_start_is_still_linted(tmp_path):
    """Lint reads the tree, not the instance. Bug caught: a delivery whose install fails losing
    its lint too, so the increments that most need the reading have none."""
    container = _Linted(ContainerResult("", 0, json.dumps(_LINT_ANSWER) + "\n", ""), setup_exit=2)

    result = await _evaluate(
        _runner(tmp_path, container), stack="fullstack_fastapi_react", declared=None
    )

    assert result.started is False
    assert result.lint.status is QualityStatus.MEASURED


# --------------------------------------------------------------------------------------------
# SIP-0113 §10j, §10n (#2562): a second, seeded instance, measured on every page the plan names
# --------------------------------------------------------------------------------------------


def _seed_plan(**change):
    """The group_run seed, planned on the 2.4 window's FastAPI increment's own manifest."""
    import yaml

    from squadops.campaigns import seed_plan
    from squadops.stacks.scaffold import InterfaceManifest

    root = Path(__file__).resolve().parents[3]
    manifest = InterfaceManifest.from_dict(
        yaml.safe_load(
            (root / "tests/fixtures/roll_replays/2-4-0-window-c1-increment-2-interface_manifest.yaml")
            .read_text(encoding="utf-8")
        )
    )  # fmt: skip
    raw = (root / "examples/03_group_run/quality_seed.json").read_bytes()
    seed = {**json.loads(raw), **change}
    return seed_plan.plan(manifest, seed, json.dumps(seed).encode())


class _Seeding(_OnTheNetwork):
    """On the app network: each instance's start recorded by name, the first instance writing a
    file of its own into its copy, and the evaluator scoring whatever pages it's asked for."""

    def __init__(self, events: list, *, seeded_start_fails: bool = False) -> None:
        super().__init__()
        self.events, self.names = events, []
        self.seeded_start_fails = seeded_start_fails

    async def run_detached(self, spec: ContainerSpec) -> str:
        seeded = "eval-seeded" in (spec.name or "")
        self.events.append("start seeded" if seeded else "start")
        if seeded and self.seeded_start_fails:
            raise ToolContainerError("no room for a second instance")
        container_id = await super().run_detached(spec)
        self.names.append(spec.name)
        if not seeded:  # what the first instance writes must never reach the seeded one
            (Path(spec.volumes[0][0]) / "written-by-the-first-instance").write_text("x")
        return container_id

    async def stop(self, container_id: str) -> None:
        self.events.append("stop")
        await super().stop(container_id)

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        if spec.image == EVALUATOR and b"base_url" in spec.stdin:
            asked = json.loads(spec.stdin)["pages"]
            self.events.append(f"measure {len(asked)}")
            self.specs.append(spec)
            page = {
                "lighthouse": {"performance": 0.9, "accessibility": 0.96, "best-practices": 0.78},
                "axe": {"critical": 0, "serious": 0, "moderate": 2, "minor": 0},
                **_FINER,
                "error": None,
            }
            answer = {"pages": [{"path": p, **page} for p in asked]}
            return ContainerResult("", 0, json.dumps(answer) + "\n", "")
        return await super().run(spec)


def _seeded_app(events: list, fail: set[str] = frozenset()):
    """The app by name: its UI answering, its API taking the seed on the seeded instance only,
    a create answering with the new run's id, and ``fail`` paths answering 500."""
    made: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if request.url.port in (4173, 18409) or path in ("/", "/healthz"):
            return httpx.Response(200, text="ok")
        if request.method == "POST" and "eval-seeded" in host:
            events.append(f"seed {path}")
            if path in fail:
                return httpx.Response(500, json={"detail": "boom"})
            if path == "/runs":
                made.append(f"r-{len(made) + 1}")
                return httpx.Response(201, json={"id": made[-1]})
            return httpx.Response(200, json={})
        events.append("scenario")
        return httpx.Response(200, json={"name": "apples", "count": 1})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _evaluate_seeded(tmp_path, container, app, plan):
    return await _evaluate(
        _runner(tmp_path, container, app=app, app_network="squadops-sandbox-apps"),
        stack="fullstack_fastapi_react",
        declared=None,
        pages=("/",),
        seed=plan,
    )


async def test_a_seeded_instance_starts_from_setups_snapshot_after_the_first_and_reads_every_page(
    tmp_path,
):
    """§10j, §10n rulings 3, 4 and 8, entered at ``evaluate_tree``. Bugs caught: the seeded
    instance started on the first one's copy, carrying what the scenarios wrote; started beside
    it; seeded through the scenarios' API prefix; a parameterised page filled with another
    record's id or keyed by its filled URL; or the seeded reading mixed into §10f's."""
    events: list = []
    container = _Seeding(events)
    plan = _seed_plan()

    result = await _evaluate_seeded(tmp_path, container, _seeded_app(events), plan)

    seeded = result.quality_seeded
    assert (
        seeded.status is QualityStatus.MEASURED and result.quality.status is QualityStatus.MEASURED
    )
    assert [(p.path, p.url) for p in seeded.pages] == [
        ("/", None),
        ("/create", None),
        ("/runs/{id}#partial", "/runs/r-1"),
        ("/runs/{id}#at_capacity", "/runs/r-2"),
    ]
    assert [p.path for p in result.quality.pages] == ["/"]
    assert events[: events.index("start seeded")] == ["start", "measure 1", "scenario", "stop"]
    assert events[events.index("start seeded") + 1 :] == [
        "seed /runs", "seed /runs/r-1/join", "seed /runs/r-1/join",
        "seed /runs", "seed /runs/r-2/join", "seed /runs/r-2/join", "seed /runs/r-2/join",
        "seed /runs", "measure 4", "stop",
    ]  # fmt: skip
    [first, second] = [h for h in container.held if "run.sh" in h][-2:]
    assert "written-by-the-first-instance" not in second
    assert seeded.seed["version"] == plan.version
    assert [r["seeded"] for r in seeded.seed["records"]] == [True, True, True]
    assert {"snapshot_s", "start_s", "seed_s", "measure_s", "total_s"} <= set(
        seeded.seed["durations"]
    )
    assert [r.result for r in result.runs] == ["passed"]


async def test_a_record_the_app_refuses_voids_its_own_pages_only(tmp_path):
    """§10n ruling 7. Bug caught: one refused join voiding the whole reading, or the refused
    record's page measured as if its run had reached capacity."""
    events: list = []

    result = await _evaluate_seeded(
        tmp_path, _Seeding(events), _seeded_app(events, fail={"/runs/r-2/join"}), _seed_plan()
    )

    seeded = result.quality_seeded
    assert [p.path for p in seeded.pages] == ["/", "/create", "/runs/{id}#partial"]
    assert ["/runs/:run_id#at_capacity", "seed_failed"] in seeded.seed["unfilled"]
    [refused] = [r for r in seeded.seed["records"] if not r["seeded"]]
    assert refused == {
        "label": "at_capacity", "seeded": False,
        "refusal": "POST /runs/r-2/join answered 500",
    }  # fmt: skip


async def test_a_seed_the_app_refuses_entirely_is_not_measured_and_the_scenarios_stand(tmp_path):
    """Bug caught: a seed that failed throughout read as measured with no pages, or taking the
    scenarios' results and §10f's reading down with it."""
    events: list = []

    result = await _evaluate_seeded(
        tmp_path, _Seeding(events), _seeded_app(events, fail={"/runs"}), _seed_plan()
    )

    seeded = result.quality_seeded
    assert (seeded.status, seeded.reason) == (QualityStatus.NOT_MEASURED, NotMeasured.SEED_FAILED)
    assert "partial: POST /runs answered 500" in seeded.detail
    assert result.quality.status is QualityStatus.MEASURED
    assert [r.result for r in result.runs] == ["passed"]


async def test_a_seeded_instance_that_cant_start_is_its_own_reading_never_the_scenarios(tmp_path):
    """Bug caught: the second start's failure read as the tree's, so its scenarios and §10f's
    reading are lost."""
    events: list = []

    result = await _evaluate_seeded(
        tmp_path, _Seeding(events, seeded_start_fails=True), _seeded_app(events), _seed_plan()
    )

    seeded = result.quality_seeded
    assert (seeded.status, seeded.reason) == (QualityStatus.NOT_MEASURED, NotMeasured.START_FAILED)
    assert result.started and [r.result for r in result.runs] == ["passed"]


#: SIP-0113 §10p (#2564 step 3): a scenario that creates a run over HTTP, then joins it on the page.
BROWSING = {
    "scenario_id": "join-from-the-page",
    "steps": [
        {"action": "http", "method": "POST", "path": "/runs", "json": {"title": "Dawn 5k"},
         "save": {"run_id": "id"}, "expect_status": 201},
        {"action": "visit", "path": "/runs/{run_id}"},
        {"action": "click", "target": {"role": "button", "names": ["Join"]}},
    ],
    "checks": [{"check": "text", "step": 3, "pattern": "1\\s*/\\s*5"}],
}  # fmt: skip
_BROWSED = {
    "browse": {
        "browser": "HeadlessChrome/155.0",
        "steps": [
            {"step": 2, "outcome": "done", "seconds": 1.02},
            {"step": 3, "outcome": "done", "seconds": 0.66},
        ],
        "checks": [{"index": 0, "holds": True, "seen": None}],
        "evidence": None,
        "timings": {"launch_s": 0.12, "total_s": 2.3},
    }
}


def _runs_app():
    """The app by name on the app network: Vite's preview on 4173 refuses the name (an answer
    still), and the backend creates a run."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.port == 4173:
            return httpx.Response(403, text="Blocked request. This host is not allowed.")
        if request.url.path in ("/", "/healthz"):
            return httpx.Response(200, text="ok")
        if request.method == "POST" and request.url.path.endswith("/runs"):
            return httpx.Response(201, json={"id": "r1", "title": "Dawn 5k"})
        return httpx.Response(404, json={"detail": "not here"})

    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


class _Browsing(_OnTheNetwork):
    """On the app network; the evaluator answers each segment of browser steps as scripted, and
    measures nothing else."""

    def __init__(self, answer: ContainerResult) -> None:
        super().__init__()
        self.browse_answer, self.browsed = answer, []

    async def run(self, spec: ContainerSpec) -> ContainerResult:
        if spec.image == EVALUATOR and spec.stdin and b'"browse"' in spec.stdin:
            self.browsed.append(spec)
            return self.browse_answer
        return await super().run(spec)


class _BrowsingOnLoopback(_Browsing):
    """The same, with no app network: the app publishes to loopback, as on a host run."""

    async def resolve_host_port(self, container_id: str, container_port: int) -> int:
        return 49999


async def _browse(tmp_path, container, *, app_network="squadops-sandbox-apps", **kw):
    return await _evaluate(
        _runner(tmp_path, container, app=_runs_app(), app_network=app_network),
        stack="fullstack_fastapi_react",
        declared=None,
        scenarios=[BROWSING],
        **kw,
    )


async def test_a_segment_runs_in_the_evaluator_on_the_app_network_and_its_runner_is_recorded(
    tmp_path,
):
    """§10p rulings 1, 5 and 7. Bugs caught: the segment sent unrendered or with the scenario's
    other checks, given the app's secrets, a mount or a route out, or no deadline of its own; the
    browser's answer dropped between the evaluator and the run; or the runner unrecorded, so a
    change of browser can't be read as a methodology break."""
    container = _Browsing(ContainerResult("", 0, json.dumps(_BROWSED) + "\n", ""))

    result = await _browse(tmp_path, container)

    [spec] = container.browsed
    start = next(s for s in container.specs if s.image != EVALUATOR and s.name)
    sent = json.loads(spec.stdin)["browse"]
    assert sent == {
        "base_url": f"http://{start.name}:4173",
        "first_step": 2,
        "steps": [BROWSING["steps"][1] | {"path": "/runs/r1"}, BROWSING["steps"][2]],
        "checks": [{"index": 0, "check": BROWSING["checks"][0]}],
        "deadline_s": 90.0,
    }
    assert (spec.network, spec.volumes, spec.env) == ("squadops-sandbox-apps", (), ())
    assert spec.cap_drop_all and spec.no_new_privileges and spec.timeout_seconds == 120.0
    [run] = result.runs
    assert (run.result, run.steps_taken) == ("passed", 3)
    assert run.runner == f"{EVALUATOR} HeadlessChrome/155.0"
    assert len(run.step_seconds) == 3 and run.step_seconds[1:] == (1.02, 0.66)


@pytest.mark.parametrize(
    ("answer", "network"),
    [
        (ContainerResult("", 1, "Moonrise-Relay was typed\n", "TypeError: Moonrise-Relay\n"), "apps"),
        (ContainerResult("", 0, "not json\n", ""), "apps"),
        (ContainerResult("", 0, json.dumps(_BROWSED) + "\n", ""), None),
    ],
    ids=["the-browser-exited", "an-answer-it-cant-read", "no-app-network"],
)  # fmt: skip
async def test_a_segment_no_browser_answered_is_browser_unavailable_and_quotes_nothing(
    tmp_path, answer, network
):
    """§10p ruling 1. Bugs caught: a browser that crashed read as the product failing; or the
    container's output, which carries the segment's held-out values, copied into the run's
    detail as ``_quality`` does for its own failures."""
    container = (_Browsing if network else _BrowsingOnLoopback)(answer)

    result = await _browse(tmp_path, container, app_network=network)

    [run] = result.runs
    assert (run.result, run.blocked_reason) == ("blocked_unverified", "browser_unavailable")
    assert "Moonrise" not in (run.detail or "")
    assert len(container.browsed) == (0 if network is None else 1)


async def test_a_browser_scenario_travels_from_the_suite_to_the_record_through_the_real_runner(
    tmp_path, monkeypatch
):
    """The wiring test §10p's build step 3 names, entered at ``evaluate_cycle``, the call a
    campaign cycle's end makes, with the real runner over a fake container. Bugs caught: a browser
    scenario refused by the page-surface check on a route the delivery declares in its own syntax
    (``:id`` against the scenario's ``{id}``); the runner's version or the steps' seconds lost
    between the run and the stored outcome; or the segment never reaching the evaluator."""
    from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
    from squadops.scenarios import evaluate
    from squadops.scenarios.evaluation import ScenarioResult
    from squadops.scenarios.models import parse_suite
    from squadops.scenarios.suites import approve_suite, draft_suite
    from tests.unit.scenarios.test_quality_evaluation import _MANIFEST, _Cycle, _Vault

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    scenario = {
        **BROWSING,
        "goal": "A runner joins a run from its page.",
        "surfaces": [
            {"kind": "http_endpoint", "method": "POST", "path": "/runs"},
            {"kind": "page", "path": "/runs/{id}"},
        ],
    }
    store, suite = MemoryScenarioStore(), parse_suite({"name": "pages", "scenarios": [scenario]})
    await draft_suite(store, suite, actor="supervisor", at=_T0)
    await approve_suite(store, suite.digest, actor="owner", at=_T0)
    container = _Browsing(ContainerResult("", 0, json.dumps(_BROWSED) + "\n", ""))

    record = await evaluate.evaluate_cycle(
        store=store,
        runner=_runner(tmp_path, container, app=_runs_app(), app_network="squadops-sandbox-apps"),
        vault=_Vault(_MANIFEST),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=_T0,
    )

    [outcome] = record.outcomes
    assert outcome.result is ScenarioResult.PASSED
    assert outcome.runner == f"{EVALUATOR} HeadlessChrome/155.0"
    assert len(outcome.step_seconds) == 3
    assert len(container.browsed) == 1
    assert await store.get_evaluation(record.evaluation_id) == record


_FAILED_ON_THE_PAGE = {
    "browse": {
        "browser": "HeadlessChrome/155.0",
        "steps": [
            {"step": 2, "outcome": "done", "seconds": 1.0},
            {"step": 3, "outcome": "action_failed", "detail": "Error", "seconds": 0.5},
        ],
        "checks": [],
        "evidence": {
            "step": 3,
            "png_b64": "iVBORw0KGgo=",
            "role": "button",
            "nodes": [{"name": "Join", "visible": True, "disabled": True}],
            "errors": ["driver: Node is detached; header evaluation-token"],
            "failed_requests": [],
        },
    }
}


async def test_a_failed_page_steps_evidence_leaves_the_sandbox_scrubbed_with_no_screenshot(
    tmp_path,
):
    """§10p ruling 8, with Q40. Bug caught: the browser's evidence leaving the sandbox with an
    evaluation secret in an error it logged, or with a screenshot of a page that could show one."""
    container = _Browsing(ContainerResult("", 0, json.dumps(_FAILED_ON_THE_PAGE) + "\n", ""))

    result = await _browse(tmp_path, container)

    [run] = result.runs
    assert (run.result, run.first_failing_step) == ("failed", 3)
    assert run.evidence["png_b64"] is None
    assert run.evidence["withheld"] == ["screenshot: the evaluation resolved a secret"]
    assert run.evidence["errors"] == ["driver: Node is detached; header [redacted]"]
    assert "evaluation-token" not in json.dumps(run.as_dict())


async def test_a_failed_page_scenarios_evidence_is_stored_beside_its_record_never_on_it(
    tmp_path, monkeypatch
):
    """§10p ruling 8, wired: entered at ``evaluate_cycle`` with the real runner. Bug caught: the
    evidence dropped between the runner and the store, so a page failure can't be read; or written
    onto the outcome, which the package and the digest read."""
    from adapters.scenarios.memory_scenario_store import MemoryScenarioStore
    from squadops.scenarios import evaluate
    from squadops.scenarios.models import parse_suite
    from squadops.scenarios.suites import approve_suite, draft_suite
    from tests.unit.scenarios.test_quality_evaluation import _MANIFEST, _Cycle, _Vault

    async def tree_refs(vault, cycle):
        return {"backend/main.py": "tree"}

    monkeypatch.setattr(evaluate, "evaluated_tree_refs", tree_refs)
    scenario = {
        **BROWSING,
        "goal": "A runner joins a run from its page.",
        "surfaces": [
            {"kind": "http_endpoint", "method": "POST", "path": "/runs"},
            {"kind": "page", "path": "/runs/{id}"},
        ],
    }
    store, suite = MemoryScenarioStore(), parse_suite({"name": "pages", "scenarios": [scenario]})
    await draft_suite(store, suite, actor="supervisor", at=_T0)
    await approve_suite(store, suite.digest, actor="owner", at=_T0)
    container = _Browsing(ContainerResult("", 0, json.dumps(_FAILED_ON_THE_PAGE) + "\n", ""))

    record = await evaluate.evaluate_cycle(
        store=store,
        runner=_runner(tmp_path, container, app=_runs_app(), app_network="squadops-sandbox-apps"),
        vault=_Vault(_MANIFEST),
        cycle=_Cycle(),
        suite_digest=suite.digest,
        campaign_id=None,
        previous_accepted_tree_identity=None,
        evaluated_at=_T0,
    )

    [evidence] = await store.evidence_for(record.evaluation_id)
    assert (evidence.scenario_id, evidence.step, evidence.role) == (
        "join-from-the-page",
        3,
        "button",
    )
    assert "evidence" not in record.outcomes[0].as_dict()


async def test_a_check_reads_a_value_an_earlier_step_saved_at_the_runners_live_seam(tmp_path):
    """#2784, entered where the sandbox service evaluates a tree (``evaluate_tree``, the live
    caller of ``run_scenario``). Bug caught: the runner's checks left unrendered, so a scenario
    comparing two responses fails on a product that answers correctly."""
    compared = {
        "scenario_id": "read-back-by-name",
        "goal": "g",
        "surfaces": [{"kind": "http_endpoint", "path": "/tally/{name}", "method": "GET"}],
        "steps": [
            {"action": "http", "method": "GET", "path": "/tally/first", "save": {"who": "name"}},
            {"action": "http", "method": "GET", "path": "/tally/{who}"},
        ],
        "checks": [
            {"check": "json", "step": 2, "path": "name", "equals": "{who}"},
            {"check": "json", "step": 2, "path": "count", "equals": 2},
        ],
    }

    result = await _evaluate(_runner(tmp_path, _Container()), scenarios=[compared])

    assert [(r.scenario_id, r.result, r.detail) for r in result.runs] == [
        ("read-back-by-name", "passed", None)
    ]
