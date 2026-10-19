"""Tests for the SquadOps Console main.py.

Verifies COMMAND_HANDLERS registry, config.js endpoint, and router mounting.
ContinuumRuntime and its dependencies are mocked to avoid import errors.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter

# ── Mock continuum dependencies before importing main ──────────────────────
# These modules are not installed in the test environment, so we inject
# fake modules into sys.modules before importing main.py.

sys.modules["continuum"] = MagicMock()
sys.modules["continuum.app"] = MagicMock()
sys.modules["continuum.app.runtime"] = MagicMock()
sys.modules["continuum.adapters"] = MagicMock()
sys.modules["continuum.adapters.web"] = MagicMock()
sys.modules["continuum.adapters.web.api"] = MagicMock()

# Set up the mock continuum API router with a real APIRouter
# so that FastAPI can actually mount it
_mock_api_module = sys.modules["continuum.adapters.web.api"]
_mock_api_module.router = APIRouter(prefix="/api/registry")


# Add a dummy /health route and /api/registry route so we can verify mounting
@_mock_api_module.router.get("/health")
async def _mock_health():
    return {"status": "ok"}


@_mock_api_module.router.get("/")
async def _mock_registry():
    return {"plugins": []}


# Add console/app to sys.path
sys.path.insert(0, str(Path(__file__).parents[3] / "console" / "app"))

# Now import main — it will pick up our mocked continuum modules
from httpx import ASGITransport, AsyncClient  # noqa: E402

from tests.unit.console.console_settings import compose_settings  # noqa: E402

# #2431: the console requires every setting compose gives it.
with patch.dict(os.environ, compose_settings()):
    from main import COMMAND_HANDLERS, REQUIRED_SETTINGS, app  # noqa: E402


class TestConsoleMain:
    """Tests for console main.py."""

    def test_command_handlers_registered(self):
        """COMMAND_HANDLERS dict contains expected command IDs."""
        expected_keys = {
            "squadops.health_check",
            "squadops.create_cycle",
            "squadops.create_run",
            "squadops.cancel_cycle",
            "squadops.cancel_run",
            "squadops.gate_approve",
            "squadops.gate_reject",
            "squadops.ingest_artifact",
            "squadops.set_baseline",
            "squadops.download_artifact",
            "squadops.set_active_profile",
        }
        assert set(COMMAND_HANDLERS.keys()) == expected_keys

    async def test_config_js_endpoint(self):
        """GET /config.js returns JS containing window.__SQUADOPS_CONFIG__."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/config.js")

        assert resp.status_code == 200
        assert "application/javascript" in resp.headers["content-type"]
        body = resp.text
        assert "window.__SQUADOPS_CONFIG__" in body
        assert "apiBaseUrl" in body
        assert "prefectBaseUrl" in body
        assert "langfuseBaseUrl" in body
        assert "squadops.apiFetch" in body

    # #198: these two asked whether an included router's paths appear in ``app.routes``.
    # FastAPI 0.136 stopped flattening them — ``include_router`` now appends one mount
    # object with no ``.path``, and the endpoints answer exactly as before. So the old
    # form failed on a version where the app was entirely healthy, which is the worst
    # kind of test: it reads as "the console lost its auth routes".
    #
    # What the app owes its callers is that the paths RESPOND. Asked that way the test
    # is both truer and version-independent — it cannot be broken by the framework
    # changing how it represents a mount, only by the mount not happening.

    @pytest.mark.parametrize("path", ["/auth/login", "/auth/callback", "/auth/refresh"])
    async def test_the_auth_router_answers_at_its_paths(self, path):
        """Bug caught: the auth BFF router is not mounted, so every console login 404s.

        Any status but 404 proves the route resolved — a 302 to the IdP, a 400 for a
        missing parameter and a 500 from an unconfigured stub all mean the mount is
        there, and distinguishing them is the auth BFF suite's job, not this one's.
        """
        # An unconfigured stub raises inside the app. By default the in-process transport
        # re-raises that instead of answering 500, so the test passed only when an earlier
        # test in the same worker had configured the auth BFF — and failed alone, or whenever
        # the suite's split across workers moved it. Returning the app's 500 as a response is
        # what the docstring above already counts as mounted.
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get(path)

        assert resp.status_code != 404, f"{path} is not mounted — the auth router is absent"

    async def test_the_continuum_router_answers_under_its_prefix(self):
        """Bug caught: the plugin registry is not mounted, so the console loads no plugins."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/registry/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestHostProxy:
    """``/api/health/host``, the route the Systems perspective's Host panel calls (#2204b)."""

    async def _get(self, monkeypatch, status: int, body: dict):
        import main as console_main
        from httpx import Response

        calls: list[tuple[str, str]] = []

        async def fake_api_request(method, path, **kwargs):
            calls.append((method, path))
            return Response(status, json=body)

        monkeypatch.setattr(console_main, "_api_request", fake_api_request)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/health/host"), calls

    async def test_the_panel_reads_the_runtime_apis_host_reading_unchanged(self, monkeypatch):
        """Bug caught: the panel calling a route the console never proxies, so it shows "could
        not be read" on a healthy deploy."""
        reading = {"host": {"memory_available_bytes": 7.0e10}, "verdicts": {"memory": {}}}
        resp, calls = await self._get(monkeypatch, 200, reading)
        assert (resp.status_code, resp.json(), calls) == (200, reading, [("GET", "/health/host")])

    async def test_an_upstream_failure_is_passed_on_never_an_empty_reading(self, monkeypatch):
        resp, _ = await self._get(monkeypatch, 503, {"detail": "down"})
        assert (resp.status_code, resp.json()) == (503, {"error": "upstream unavailable"})


@pytest.mark.parametrize(
    ("method", "path", "status", "kept"),
    [
        ("GET", "/health", 200, False),
        ("GET", "/health", 503, True),
        ("GET", "/api/registry/", 200, True),
        ("POST", "/health", 200, True),
    ],
    ids=["probe-ok", "probe-failed", "other-route", "other-method"],
)
def test_the_access_log_drops_only_a_successful_health_probe(method, path, status, kept):
    """#2425, read through the access logger as importing ``main`` leaves it. Bugs caught: the
    filter never installed (every 30 s probe back in the log), or one that also hides a failed
    probe or a person's request."""
    import logging

    record = logging.makeLogRecord(
        {"msg": '%s - "%s %s HTTP/%s" %d', "args": ("c", method, path, "1.1", status)}
    )
    assert bool(logging.getLogger("uvicorn.access").filter(record)) is kept


def test_every_setting_the_console_requires_is_one_compose_gives_it():
    """#2431. Bugs caught: a setting the console requires that compose does not give it, so the
    console no longer starts; and the realm left out of compose again, which a default hid until
    every deploy's tab read "(dev)"."""
    assert "SQUADOPS_REALM" in REQUIRED_SETTINGS
    assert set(REQUIRED_SETTINGS) <= set(compose_settings())


@pytest.mark.parametrize(
    ("name", "value", "starts"),
    [
        ("SQUADOPS_REALM", None, False),
        ("KEYCLOAK_PUBLIC_URL", "", False),
        ("REDIS_URL", None, False),
        ("REDIS_URL", "", True),
    ],
    ids=["realm-missing", "public-url-empty", "redis-missing", "redis-empty-selects-memory"],
)
def test_a_missing_setting_stops_the_console_naming_it(name, value, starts):
    """#2431, at the console's import, as uvicorn's ``main:app`` loads it. Bugs caught: a missing
    or empty setting replaced by a URL nobody configured; and in-memory sessions reached by
    leaving ``REDIS_URL`` out, rather than by setting it empty."""
    settings = compose_settings()
    if value is None:
        settings.pop(name)
    else:
        settings[name] = value
    loaded = sys.modules.pop("main")
    try:
        with patch.dict(os.environ, settings, clear=True):
            if starts:
                assert importlib.import_module("main").REDIS_URL == ""
            else:
                with pytest.raises(RuntimeError, match=f"console: {name} is required"):
                    importlib.import_module("main")
    finally:
        sys.modules["main"] = loaded


class TestChatProxy:
    """``/api/v1/chat/*`` POSTs, which Caddy sends to the console rather than the runtime API."""

    async def _post(self, monkeypatch, path: str):
        import httpx
        import main as console_main

        def answer(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/captures"):
                return httpx.Response(201, json={"record_id": "mrec_1"})
            return httpx.Response(
                200, text='data: {"text": "hi"}\n\n', headers={"content-type": "text/event-stream"}
            )

        upstream = httpx.AsyncClient(transport=httpx.MockTransport(answer), base_url="http://api")

        async def no_session(request):
            return None

        monkeypatch.setattr(console_main, "_api_client", upstream)
        monkeypatch.setattr(console_main, "_authorization_for", no_session)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, json={})

    async def test_a_capture_is_answered_as_the_json_it_is_and_a_turn_as_a_stream(
        self, monkeypatch
    ):
        """#2180. Bug caught: a capture's confirmation relayed as an event stream, so the console
        reads a 201 JSON body labelled text/event-stream, or a turn's reply buffered whole."""
        capture = await self._post(monkeypatch, "/api/v1/chat/sessions/s1/captures")
        turn = await self._post(monkeypatch, "/api/v1/chat/comms-agent")

        assert (capture.status_code, capture.headers["content-type"], capture.json()) == (
            201, "application/json", {"record_id": "mrec_1"},
        )  # fmt: skip
        assert turn.headers["content-type"].startswith("text/event-stream")
        assert turn.text == 'data: {"text": "hi"}\n\n'


def test_every_plugins_nav_opens_a_perspective_the_shell_knows():
    """The second read of PR #2524. Bug caught: a plugin's nav entry opening a perspective neither
    Continuum ships nor this console registers at boot, so the entry opens nothing (the Memory
    perspective, first)."""
    import tomllib

    import main as console_main

    known = set(console_main.BUILTIN_PERSPECTIVES) | {
        p[0] for p in console_main.CUSTOM_PERSPECTIVES
    }
    plugins = Path(__file__).parents[3] / "console" / "continuum-plugins"
    targets = {
        manifest.parent.name: nav["target"]["panel_id"]
        for manifest in plugins.glob("*/plugin.toml")
        for nav in tomllib.loads(manifest.read_text(encoding="utf-8"))
        .get("contributions", {})
        .get("nav", [])
        if nav.get("target", {}).get("type") == "panel"
    }

    assert targets, "no plugin declares a nav entry: the scan no longer reads them"
    assert {p: t for p, t in targets.items() if t not in known} == {}
