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


# Add docker/console to sys.path
sys.path.insert(0, str(Path(__file__).parents[3] / "docker" / "console"))

# Now import main — it will pick up our mocked continuum modules
from main import app, COMMAND_HANDLERS  # noqa: E402

from httpx import ASGITransport, AsyncClient  # noqa: E402


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

    def test_app_includes_auth_router(self):
        """App has routes with /auth prefix."""
        auth_paths = [route.path for route in app.routes if hasattr(route, "path")]
        auth_routes = [p for p in auth_paths if p.startswith("/auth")]
        assert len(auth_routes) >= 4, (
            f"Expected at least 4 /auth routes (login, callback, refresh, logout), "
            f"found: {auth_routes}"
        )

    def test_app_includes_continuum_router(self):
        """App has routes from the continuum API router."""
        all_paths = [route.path for route in app.routes if hasattr(route, "path")]
        # The continuum router was mounted with /api/registry prefix
        registry_routes = [p for p in all_paths if "/api/registry" in p]
        assert len(registry_routes) >= 1, (
            f"Expected at least 1 continuum API route, found paths: {all_paths}"
        )
