"""The scenario runner in the sandbox (SIP-0113 §4.1, §7 prediction 6; X-3b; #2414, #2421)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from adapters.sandbox.scenario_runner import ContainerScenarioRunner
from squadops.campaigns.evaluator_trees import FileTree
from squadops.scenarios.quality import NotMeasured, PageMeasure, QualityReading, QualityStatus
from squadops.scenarios.runner import DeclaredStart
from squadops.tools.models import ContainerResult, ContainerSpec
from tests.unit.sandbox.test_container_backend import FakeContainer

EVALUATOR = "evaluator:pinned"
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

    install, build, start = (s.command for s in container.specs)
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

_ANSWER = {
    "pages": [
        {
            "path": "/",
            "lighthouse": {"performance": 0.93, "accessibility": 0.96, "best-practices": 0.78},
            "axe": {"critical": 0, "serious": 0, "moderate": 2, "minor": 0},
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
            self.events.append("evaluator")
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
    [evaluator] = [s for s in container.specs if s.image == EVALUATOR]
    assert json.loads(evaluator.stdin) == {"base_url": f"http://{start.name}:4173", "pages": ["/"]}
    assert (evaluator.network, evaluator.volumes, evaluator.env) == (
        "squadops-sandbox-apps",
        (),
        (),
    )
    assert evaluator.cap_drop_all and evaluator.no_new_privileges
    assert result.quality == _MEASURED
    assert events == ["evaluator", "scenario"]
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
        ("apps", True, _NO_ANSWER, False, ("/",), NotMeasured.UI_NOT_READY, "nothing answered"),
        ("apps", True, _NO_ANSWER, True, (), NotMeasured.NO_DECLARED_PAGE, None),
    ],
    ids=[
        "a-host-run",
        "no-evaluator-image",
        "the-evaluator-fails",
        "it-answers-for-other-pages",
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
