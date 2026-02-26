"""Tests for squadops.cycles plugin registration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load the cycles plugin __init__.py using importlib to avoid module name collision
_plugin_path = Path(__file__).parents[3] / "console" / "continuum-plugins" / "squadops.cycles" / "__init__.py"
_spec = importlib.util.spec_from_file_location("squadops_cycles_plugin", _plugin_path)
_cycles_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cycles_plugin)
register = _cycles_plugin.register


@pytest.fixture()
def mock_ctx():
    """Create a mock plugin context that records contributions."""
    ctx = MagicMock()
    ctx.plugin_id = "squadops.cycles"
    ctx.discovery_index = 0
    ctx.contributions = []

    def _record(contribution_type, data):
        ctx.contributions.append({"type": contribution_type, **data})

    ctx.register_contribution.side_effect = _record
    return ctx


class TestCyclesPluginRegistration:
    """Verify register(ctx) produces expected contributions."""

    def test_total_contributions(self, mock_ctx):
        """1 nav + 1 composite panel + 6 commands = 8 contributions (SIP-0074)."""
        register(mock_ctx)
        assert mock_ctx.register_contribution.call_count == 8

    def test_nav_contribution(self, mock_ctx):
        register(mock_ctx)
        nav_calls = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "nav"
        ]
        assert len(nav_calls) == 1
        data = nav_calls[0][0][1]
        assert data["label"] == "Cycles"
        assert data["icon"] == "clock"
        assert data["priority"] == 800

    def test_single_composite_panel(self, mock_ctx):
        """SIP-0074: 3 separate panels replaced by 1 composite perspective panel."""
        register(mock_ctx)
        panels = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"]
        assert len(panels) == 1
        data = panels[0][0][1]
        assert data["component"] == "squadops-cycles-perspective"
        assert data["slot"] == "ui.slot.main"
        assert data["perspective"] == "cycles"
        assert data["priority"] == 800

    def test_command_create_cycle_is_safe(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        create = [c for c in commands if c[0][1]["id"] == "squadops.create_cycle"]
        assert len(create) == 1
        assert create[0][0][1]["danger_level"] == "safe"

    def test_command_cancel_cycle_requires_confirm(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        cancel = [c for c in commands if c[0][1]["id"] == "squadops.cancel_cycle"]
        assert len(cancel) == 1
        assert cancel[0][0][1]["danger_level"] == "confirm"

    def test_command_gate_approve_is_safe(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        approve = [c for c in commands if c[0][1]["id"] == "squadops.gate_approve"]
        assert len(approve) == 1
        assert approve[0][0][1]["danger_level"] == "safe"

    def test_command_gate_reject_requires_confirm(self, mock_ctx):
        register(mock_ctx)
        commands = [c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "command"]
        reject = [c for c in commands if c[0][1]["id"] == "squadops.gate_reject"]
        assert len(reject) == 1
        assert reject[0][0][1]["danger_level"] == "confirm"

    def test_all_panels_in_cycles_perspective(self, mock_ctx):
        register(mock_ctx)
        panel_calls = [
            c for c in mock_ctx.register_contribution.call_args_list if c[0][0] == "panel"
        ]
        for call in panel_calls:
            data = call[0][1]
            assert data["perspective"] == "cycles", (
                f"Panel {data['component']} has perspective={data['perspective']}, "
                f"expected 'cycles'"
            )
