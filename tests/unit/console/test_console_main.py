"""Tests for the SquadOps Console main.py.

Verifies COMMAND_HANDLERS registry, config.js endpoint, and router mounting.
ContinuumRuntime and its dependencies are mocked to avoid import errors.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

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
from main import COMMAND_HANDLERS, app  # noqa: E402


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
