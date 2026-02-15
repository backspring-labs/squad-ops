"""Tests for squadops.artifacts plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the artifacts plugin __init__.py using importlib to avoid module name collision
_plugin_path = Path(__file__).parents[3] / "continuum-plugins" / "squadops.artifacts" / "__init__.py"
_spec = importlib.util.spec_from_file_location("squadops_artifacts_plugin", _plugin_path)
_artifacts_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_artifacts_plugin)
register = _artifacts_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.artifacts"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestArtifactsPluginRegistration:
    """Verify register(ctx) produces expected contributions."""

    def test_total_contributions(self, mock_ctx):
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 6  # 3 panels + 3 commands

    def test_panel_artifacts_list(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        list_panels = [
            p for p in panels if p[0][1]["component"] == "squadops-artifacts-list"
        ]
        assert len(list_panels) == 1
        assert list_panels[0][0][1]["slot"] == "ui.slot.main"
        assert list_panels[0][0][1]["perspective"] == "signal"

    def test_panel_artifacts_browser(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        browser_panels = [
            p for p in panels if p[0][1]["component"] == "squadops-artifacts-browser"
        ]
        assert len(browser_panels) == 1
        assert browser_panels[0][0][1]["perspective"] == "discovery"

    def test_panel_artifacts_detail_in_right_rail(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        detail_panels = [
            p for p in panels if p[0][1]["component"] == "squadops-artifacts-detail"
        ]
        assert len(detail_panels) == 1
        assert detail_panels[0][0][1]["slot"] == "ui.slot.right_rail"

    def test_command_ingest_artifact(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        ingest = [c for c in commands if c[0][1]["id"] == "squadops.ingest_artifact"]
        assert len(ingest) == 1
        assert ingest[0][0][1]["danger_level"] == "safe"

    def test_command_set_baseline_requires_confirm(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        baseline = [c for c in commands if c[0][1]["id"] == "squadops.set_baseline"]
        assert len(baseline) == 1
        assert baseline[0][0][1]["danger_level"] == "confirm"

    def test_command_download_artifact(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        download = [c for c in commands if c[0][1]["id"] == "squadops.download_artifact"]
        assert len(download) == 1
        assert download[0][0][1]["danger_level"] == "safe"

    def test_no_nav_contributions(self, mock_ctx):
        register(mock_ctx)
        navs = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"]
        assert len(navs) == 0
