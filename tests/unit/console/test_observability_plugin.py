"""Tests for squadops.observability plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the observability plugin __init__.py using importlib to avoid module name collision
_plugin_path = (
    Path(__file__).parents[3]
    / "console"
    / "continuum-plugins"
    / "squadops.observability"
    / "__init__.py"
)
_spec = importlib.util.spec_from_file_location("squadops_observability_plugin", _plugin_path)
_observability_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_observability_plugin)
register = _observability_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.observability"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestObservabilityPluginRegistration:
    """Verify register(ctx) produces expected contributions."""

    def test_total_contributions(self, mock_ctx):
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 3  # 3 panels

    def test_panel_artifacts(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        fm = [p for p in panels if p[0][1]["component"] == "squadops-obs-artifacts"]
        assert len(fm) == 1
        assert fm[0][0][1]["slot"] == "ui.slot.main"
        assert fm[0][0][1]["priority"] == 200

    def test_panel_gate_decisions(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        lt = [p for p in panels if p[0][1]["component"] == "squadops-obs-gate-decisions"]
        assert len(lt) == 1
        assert lt[0][0][1]["slot"] == "ui.slot.main"
        assert lt[0][0][1]["priority"] == 100

    def test_panel_cycle_stats_in_right_rail(self, mock_ctx):
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        cs = [p for p in panels if p[0][1]["component"] == "squadops-obs-cycle-stats"]
        assert len(cs) == 1
        assert cs[0][0][1]["slot"] == "ui.slot.right_rail"
        assert cs[0][0][1]["priority"] == 300

    def test_no_nav_contributions(self, mock_ctx):
        register(mock_ctx)
        navs = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"]
        assert len(navs) == 0

    def test_no_command_contributions(self, mock_ctx):
        register(mock_ctx)
        commands = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"
        ]
        assert len(commands) == 0

    def test_all_panels_in_signal_perspective(self, mock_ctx):
        """Observability panels render in the 'signal' perspective."""
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        for call in panels:
            data = call[0][1]
            assert data["perspective"] == "signal", (
                f"Panel {data['component']} has perspective={data['perspective']}, "
                f"expected 'signal'"
            )

    def test_all_panel_components_prefixed(self, mock_ctx):
        """All observability components use the 'squadops-obs-' prefix."""
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        for call in panels:
            comp = call[0][1]["component"]
            assert comp.startswith("squadops-obs-"), (
                f"Component {comp} missing 'squadops-obs-' prefix"
            )

    def test_no_commands_means_read_only(self, mock_ctx):
        """Observability is read-only — no commands registered, so service
        unavailability only affects panel rendering (graceful degradation)."""
        register(mock_ctx)
        all_types = {c[0][0] for c in mock_ctx.register_contribution.call_args_list}
        assert "command" not in all_types
        # Only "panel" contributions — no nav or command that could fail on action
        assert all_types == {"panel"}
