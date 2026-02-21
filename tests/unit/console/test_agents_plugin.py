"""Tests for squadops.agents plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the agents plugin __init__.py using importlib to avoid module name collision
_plugin_path = Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.agents" / "__init__.py"
_spec = importlib.util.spec_from_file_location("squadops_agents_plugin", _plugin_path)
_agents_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_agents_plugin)
register = _agents_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.agents"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestAgentsPluginRegistration:
    """Verify register(ctx) produces expected contributions."""

    def test_total_contributions(self, mock_ctx):
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 2  # 2 panels, no nav, no commands

    def test_panel_agents_status_in_right_rail(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        status_panels = [
            p for p in panels if p[0][1]["component"] == "squadops-agents-status"
        ]
        assert len(status_panels) == 1
        assert status_panels[0][0][1]["slot"] == "ui.slot.right_rail"
        assert status_panels[0][0][1]["priority"] == 800

    def test_panel_agents_run_activity_in_main(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        run_activity_panels = [
            p for p in panels if p[0][1]["component"] == "squadops-agents-run-activity"
        ]
        assert len(run_activity_panels) == 1
        assert run_activity_panels[0][0][1]["slot"] == "ui.slot.main"
        assert run_activity_panels[0][0][1]["priority"] == 300

    def test_no_nav_contributions(self, mock_ctx):
        register(mock_ctx)
        navs = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"]
        assert len(navs) == 0

    def test_no_command_contributions(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        assert len(commands) == 0
