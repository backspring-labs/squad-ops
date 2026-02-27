"""Tests for squadops.squad plugin registration (SIP-0075 §4.2)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the squad plugin __init__.py using importlib to avoid module name collision
_plugin_path = (
    Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.squad" / "__init__.py"
)
_spec = importlib.util.spec_from_file_location("squadops_squad_plugin", _plugin_path)
_squad_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_squad_plugin)
register = _squad_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.squad"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestSquadPluginRegistration:
    """Verify register(ctx) produces expected contributions."""

    def test_total_contributions(self, mock_ctx):
        """1 nav + 1 panel = 2 contributions."""
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 2

    def test_nav_contribution(self, mock_ctx):
        register(mock_ctx)
        nav_calls = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"]
        assert len(nav_calls) == 1
        data = nav_calls[0][0][1]
        assert data["label"] == "Squad"
        assert data["icon"] == "users"
        assert data["priority"] == 700

    def test_nav_target_panel_id(self, mock_ctx):
        register(mock_ctx)
        nav_calls = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"]
        data = nav_calls[0][0][1]
        assert data["target"]["type"] == "panel"
        assert data["target"]["panel_id"] == "squad"

    def test_single_composite_panel(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        assert len(panels) == 1
        data = panels[0][0][1]
        assert data["component"] == "squadops-squad-perspective"
        assert data["slot"] == "ui.slot.main"
        assert data["perspective"] == "squad"
        assert data["priority"] == 800

    def test_no_command_contributions(self, mock_ctx):
        """Squad plugin has no commands in V1."""
        register(mock_ctx)
        commands = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"
        ]
        assert len(commands) == 0
