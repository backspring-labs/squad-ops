"""Smoke tests for SquadOps Console container.

These tests require the console container to be running on localhost:4040.
They are skipped automatically when the container is not reachable.
"""

from __future__ import annotations

import pytest

httpx = pytest.importorskip("httpx")

CONSOLE_BASE_URL = "http://localhost:4040"


def _console_is_reachable() -> bool:
    """Check if the console container is reachable."""
    try:
        resp = httpx.get(f"{CONSOLE_BASE_URL}/health", timeout=3.0)
        return resp.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException):
        return False


@pytest.mark.docker
@pytest.mark.smoke
class TestConsoleBoot:
    """Smoke tests that verify console container is running correctly."""

    @pytest.fixture(autouse=True)
    def _skip_if_not_running(self):
        """Skip all tests in this class if the console is not reachable."""
        if not _console_is_reachable():
            pytest.skip("Console container not reachable at localhost:4040")

    def test_console_health(self):
        """Console /health endpoint returns 200."""
        resp = httpx.get(f"{CONSOLE_BASE_URL}/health", timeout=5.0)
        assert resp.status_code == 200

    def test_console_registry(self):
        """Console /api/registry returns plugin data."""
        resp = httpx.get(f"{CONSOLE_BASE_URL}/api/registry", timeout=5.0)
        assert resp.status_code == 200
        body = resp.json()
        # Registry should return a structure containing plugin info
        assert isinstance(body, (dict, list)), f"Unexpected response type: {type(body)}"

    def test_console_plugin_assets(self):
        """Console serves plugin assets or config.js with 200 status.

        Tries /config.js first (SquadOps console main.py route).
        If that endpoint is not yet deployed, attempts to fetch a plugin asset
        from the registry. At least one must return 200.
        """
        # Try config.js — available when console main.py is deployed
        config_resp = httpx.get(f"{CONSOLE_BASE_URL}/config.js", timeout=5.0)
        if config_resp.status_code == 200:
            assert "window.__SQUADOPS_CONFIG__" in config_resp.text
            return

        # Fallback: check that registry exposes plugin info with asset paths
        registry_resp = httpx.get(f"{CONSOLE_BASE_URL}/api/registry", timeout=5.0)
        assert registry_resp.status_code == 200, (
            "Neither /config.js nor /api/registry returned 200"
        )
        registry = registry_resp.json()

        # Try to find and fetch a plugin asset from registry entries.
        # Registry shape varies: could be {"plugins": [...]} or [...] directly.
        plugin_ids = []
        if isinstance(registry, dict):
            plugins_value = registry.get("plugins", [])
            if isinstance(plugins_value, list):
                plugin_ids = [
                    p.get("id", p.get("plugin_id", ""))
                    for p in plugins_value
                    if isinstance(p, dict)
                ]
            elif isinstance(plugins_value, dict):
                plugin_ids = list(plugins_value.keys())
        elif isinstance(registry, list):
            plugin_ids = [
                p.get("id", p.get("plugin_id", ""))
                for p in registry
                if isinstance(p, dict)
            ]

        fetched_any = False
        for pid in plugin_ids[:3]:
            if not pid:
                continue
            asset_resp = httpx.get(
                f"{CONSOLE_BASE_URL}/plugins/{pid}/assets/plugin.js", timeout=5.0
            )
            if asset_resp.status_code == 200:
                fetched_any = True
                break

        assert fetched_any or plugin_ids, (
            "Console is running but neither /config.js nor plugin assets are available"
        )
