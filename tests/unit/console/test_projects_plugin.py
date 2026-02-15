"""Tests for squadops.projects plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the projects plugin __init__.py using importlib to avoid module name collision
_plugin_path = (
    Path(__file__).parents[3] / "continuum-plugins" / "squadops.projects" / "__init__.py"
)
_spec = importlib.util.spec_from_file_location("squadops_projects_plugin", _plugin_path)
_projects_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_projects_plugin)
register = _projects_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.projects"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestProjectsPluginRegistration:
    """Verify register(ctx) produces expected contributions."""

    def test_total_contributions(self, mock_ctx):
        """1 nav + 2 panels + 1 command = 4 contributions."""
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 4

    def test_nav_contribution(self, mock_ctx):
        register(mock_ctx)
        nav_calls = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"
        ]
        assert len(nav_calls) == 1
        data = nav_calls[0][0][1]
        assert data["label"] == "Projects"
        assert data["icon"] == "folder"
        assert data["priority"] == 600

    def test_panel_projects_list(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        pl = [p for p in panels if p[0][1]["component"] == "squadops-projects-list"]
        assert len(pl) == 1
        assert pl[0][0][1]["slot"] == "ui.slot.main"
        assert pl[0][0][1]["priority"] == 800

    def test_panel_projects_profiles(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        pp = [p for p in panels if p[0][1]["component"] == "squadops-projects-profiles"]
        assert len(pp) == 1
        assert pp[0][0][1]["priority"] == 600

    def test_command_set_active_profile_requires_confirm(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        sap = [c for c in commands if c[0][1]["id"] == "squadops.set_active_profile"]
        assert len(sap) == 1
        assert sap[0][0][1]["danger_level"] == "confirm"

    def test_all_panels_in_discovery_perspective(self, mock_ctx):
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"
        ]
        for call in panel_calls:
            data = call[0][1]
            assert data["perspective"] == "discovery", (
                f"Panel {data['component']} has perspective={data['perspective']}, "
                f"expected 'discovery'"
            )
