"""Tests for the SquadOps Home plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the home plugin __init__.py using importlib to avoid module name collision
_plugin_path = (
    Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.home" / "__init__.py"
)
_spec = importlib.util.spec_from_file_location("squadops_home_plugin", _plugin_path)
_home_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_home_plugin)
register = _home_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.home"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestHomePluginRegistration:
    """Tests for squadops.home plugin register() function."""

    def test_register_calls_register_contribution(self, mock_ctx):
        """register() calls ctx.register_contribution at least once."""
        register(mock_ctx)
        assert mock_ctx.register_contribution.called

    def test_register_total_contributions(self, mock_ctx):
        """register() produces exactly 2 contributions (1 nav + 1 panel)."""
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 2

    def test_nav_contribution(self, mock_ctx):
        """register() adds a nav contribution with correct properties."""
        register(mock_ctx)
        nav_calls = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"]
        assert len(nav_calls) == 1
        data = nav_calls[0][0][1]
        assert data["slot"] == "ui.slot.left_nav"
        assert data["label"] == "Home"
        assert data["icon"] == "home"
        assert data["priority"] == 999

    def test_panel_contribution(self, mock_ctx):
        """register() adds a panel contribution with correct properties."""
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"
        ]
        assert len(panel_calls) == 1
        data = panel_calls[0][0][1]
        assert data["slot"] == "ui.slot.main"
        assert data["perspective"] == "signal"
        assert data["component"] == "squadops-home-summary"
        assert data["priority"] == 999

    def test_nav_target_panel_id(self, mock_ctx):
        """Nav contribution points to the 'signal' perspective."""
        register(mock_ctx)
        nav_call = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"][0]
        data = nav_call[0][1]
        assert data["target"] == {"type": "panel", "panel_id": "signal"}

    def test_no_command_contributions(self, mock_ctx):
        """Home plugin does not register any command contributions."""
        register(mock_ctx)
        command_calls = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"
        ]
        assert len(command_calls) == 0
