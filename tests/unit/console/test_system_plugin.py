"""Tests for the SquadOps System plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the system plugin __init__.py using importlib to avoid module name collision
_plugin_path = Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.system" / "__init__.py"
_spec = importlib.util.spec_from_file_location("squadops_system_plugin", _plugin_path)
_system_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_system_plugin)
register = _system_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.system"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestSystemPluginRegistration:
    """Tests for squadops.system plugin register() function."""

    def test_register_total_contributions(self, mock_ctx):
        """register() produces exactly 5 contributions (1 nav + 3 panel + 1 command)."""
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 5

    def test_nav_contribution(self, mock_ctx):
        """register() adds a nav contribution with correct properties."""
        register(mock_ctx)
        nav_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "nav"
        ]
        assert len(nav_calls) == 1
        data = nav_calls[0][0][1]
        assert data["label"] == "Systems"
        assert data["icon"] == "settings"
        assert data["priority"] == 400

    def test_panel_count(self, mock_ctx):
        """register() adds exactly 3 panel contributions."""
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "panel"
        ]
        assert len(panel_calls) == 3

    def test_system_health_panel(self, mock_ctx):
        """register() adds a system-health panel with priority 800."""
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "panel"
        ]
        health_panels = [c for c in panel_calls if c[0][1]["component"] == "squadops-system-health"]
        assert len(health_panels) == 1
        assert health_panels[0][0][1]["priority"] == 800

    def test_system_plugins_panel(self, mock_ctx):
        """register() adds a system-plugins panel with priority 600."""
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "panel"
        ]
        plugin_panels = [
            c for c in panel_calls if c[0][1]["component"] == "squadops-system-plugins"
        ]
        assert len(plugin_panels) == 1
        assert plugin_panels[0][0][1]["priority"] == 400

    def test_system_infra_panel(self, mock_ctx):
        """register() adds a system-infra panel with priority 600."""
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "panel"
        ]
        infra_panels = [
            c for c in panel_calls if c[0][1]["component"] == "squadops-system-infra"
        ]
        assert len(infra_panels) == 1
        assert infra_panels[0][0][1]["priority"] == 600

    def test_command_contribution(self, mock_ctx):
        """register() adds a command contribution for health_check."""
        register(mock_ctx)
        cmd_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "command"
        ]
        assert len(cmd_calls) == 1
        data = cmd_calls[0][0][1]
        assert data["id"] == "squadops.health_check"
        assert data["danger_level"] == "safe"

    def test_all_panels_in_systems_perspective(self, mock_ctx):
        """All panel contributions target the 'systems' perspective."""
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list
            if c[0][0] == "panel"
        ]
        for call in panel_calls:
            data = call[0][1]
            assert data["perspective"] == "systems", (
                f"Panel {data['component']} has perspective={data['perspective']}, "
                f"expected 'systems'"
            )
