"""Every declared route renders (SIP-0109 §8.3; #1705 e, part 3): the orchestration, with its
side effects injected — no browser or Node toolchain needed to judge what it does with them."""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.probe_runner import DEFAULT_PROFILE, profile_for_stack
from squadops.capabilities.handlers.route_rendering import (
    RenderSteps,
    render_profile_for,
    render_routes,
)
from squadops.capabilities.scaffold import render_profile_name_for

PROFILE = render_profile_for("vite_dev_proxy")
ROUTES = {"/": ("run-list-view",), "/runs/:run_id": ("run-detail-view", "capacity-status")}
SEEDS = {
    "/runs/:run_id": {
        "method": "POST",
        "path": "/runs",
        "json": {"title": "sample"},
        "param": "run_id",
    }
}
PAGES = {
    "/": '<div data-testid="run-list-view"><ul data-testid="run-list"></ul></div>',
    "/runs/r-7": '<section data-testid="run-detail-view"><p data-testid="capacity-status">2 / 2</p></section>',
}


def _steps(**overrides) -> tuple[RenderSteps, dict]:
    seen: dict = {"seeded": [], "read": [], "started": [], "stopped": 0}

    def dump_dom(url):
        path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
        seen["read"].append(path)
        return PAGES.get(path)

    def seed(url, body):
        seen["seeded"].append((url, dict(body)))
        return {"id": "r-7"}

    def stop(proc):
        seen["stopped"] += 1

    defaults = dict(
        install_frontend=lambda path: None,
        start=lambda cwd, argv: seen["started"].append(argv) or object(),
        stop=stop,
        ready=lambda url, timeout: True,
        seed=seed,
        dump_dom=dump_dom,
    )
    defaults.update(overrides)
    return RenderSteps(**defaults), seen


def _render(steps: RenderSteps, routes=ROUTES, seeds=SEEDS):
    return render_routes(
        {"frontend/package.json": "{}"},
        routes,
        seeds,
        profile=PROFILE,
        backend=DEFAULT_PROFILE,
        steps=steps,
    )


def test_each_page_is_read_and_a_parameterized_one_is_brought_into_being_first():
    """Bugs caught: a parameterized route read at its literal ``:run_id`` path (an empty page,
    never the view), the seed sent somewhere other than the backend the proxy reaches, or the
    backend booted on a port the frontend's proxy does not target."""
    steps, seen = _steps()

    rendered = _render(steps)

    assert rendered == {
        "/": frozenset({"run-list-view", "run-list"}),
        "/runs/:run_id": frozenset({"run-detail-view", "capacity-status"}),
    }
    assert seen["seeded"] == [("http://127.0.0.1:8000/runs", {"title": "sample"})]
    assert seen["read"] == ["/", "/runs/r-7"]
    assert "8000" in seen["started"][0]
    assert seen["stopped"] == 2  # both servers, whatever happened


@pytest.mark.parametrize(
    ("overrides", "seeds", "expected"),
    [
        # The app would not stand up: nothing can be read.
        (dict(ready=lambda url, timeout: False), SEEDS, {"/": None, "/runs/:run_id": None}),
        (dict(install_frontend=lambda path: "ERESOLVE"), SEEDS, {"/": None, "/runs/:run_id": None}),
        # The app refused the seed, or no seed exists: that page cannot be reached.
        (dict(seed=lambda url, body: None), SEEDS, {"/runs/:run_id": None}),
        ({}, {}, {"/runs/:run_id": None}),
        # The browser read nothing.
        (dict(dump_dom=lambda url: None), SEEDS, {"/": None, "/runs/:run_id": None}),
    ],
    ids=["did-not-boot", "install-failed", "seed-refused", "no-seed", "browser-read-nothing"],
)
def test_a_page_that_could_not_be_read_is_unread_never_passed(overrides, seeds, expected):
    """§8.3, SIP-0096. Bug caught: an unreadable page judged as rendered (an empty set read as
    "nothing missing"), or a failure crashing the evaluation instead of blocking the route."""
    steps, _ = _steps(**overrides)

    rendered = _render(steps, seeds=seeds)

    for route, value in expected.items():
        assert rendered[route] is value


def test_no_declared_routes_reads_nothing():
    steps, seen = _steps()
    assert _render(steps, routes={}) == {}
    assert seen["started"] == []


# --- #1973: a Next.js app serves its own pages ------------------------------------------------

NEXT = render_profile_for(render_profile_name_for("nextjs_ts"))
NEXT_PROBE = profile_for_stack("nextjs_ts")


def _render_next(steps: RenderSteps):
    return render_routes(
        {"package.json": "{}"}, ROUTES, SEEDS, profile=NEXT, backend=NEXT_PROBE, steps=steps
    )


def test_a_nextjs_app_is_built_then_read_from_the_port_it_serves():
    """SIP-0109 §24p for the second stack. Bugs caught: the app booted unbuilt (``next start``
    serves only what ``next build`` produced), a frontend dev server started beside an app that
    has none, or pages read from a port nothing serves."""
    prepared = []
    steps, seen = _steps(
        install_frontend=lambda path: pytest.fail("a Next.js app has no separate frontend"),
        prepare=lambda cwd, argv, timeout: prepared.append((argv, timeout)) or None,
    )

    rendered = _render_next(steps)

    [boot] = seen["started"]
    port = boot[boot.index("--port") + 1]
    assert prepared == [(NEXT_PROBE.prepare_argv, NEXT_PROBE.prepare_timeout_s)]
    assert boot[:3] == ["npx", "next", "start"]
    assert [url for url, _ in seen["seeded"]] == [f"http://127.0.0.1:{port}/runs"]
    assert rendered == {
        "/": frozenset({"run-list-view", "run-list"}),
        "/runs/:run_id": frozenset({"run-detail-view", "capacity-status"}),
    }
    assert seen["stopped"] == 2  # the server, and the absent frontend stopped as a no-op


def test_an_app_that_does_not_build_reads_every_route_unread_and_starts_nothing():
    steps, seen = _steps(prepare=lambda cwd, argv, timeout: "Type error: x is not assignable")

    assert _render_next(steps) == {route: None for route in ROUTES}
    assert seen["started"] == []


def test_a_page_written_with_a_braced_parameter_is_read_at_its_created_id():
    """#1973: ``/runs/{run_id}`` is one parameter, as ``/runs/:run_id`` is. Bug caught: the page
    read at the literal ``{run_id}`` path because only the router's syntax was recognised."""
    steps, seen = _steps()
    braced = {"/runs/{run_id}": ("run-detail-view",)}
    seeds = {"/runs/{run_id}": {**SEEDS["/runs/:run_id"], "segment": "{run_id}"}}

    rendered = _render(steps, routes=braced, seeds=seeds)

    assert seen["read"] == ["/runs/r-7"]
    assert rendered == {"/runs/{run_id}": frozenset({"run-detail-view", "capacity-status"})}
