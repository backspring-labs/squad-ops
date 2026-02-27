"""Unit tests for agent_labels role label helper."""

from __future__ import annotations

import pytest

from squadops.api.runtime.agent_labels import ROLE_DISPLAY_LABELS, get_role_label


class TestGetRoleLabel:
    def test_known_roles(self):
        assert get_role_label("lead") == "Lead"
        assert get_role_label("dev") == "Developer"
        assert get_role_label("strat") == "Strategy"
        assert get_role_label("qa") == "QA"
        assert get_role_label("builder") == "Builder"
        assert get_role_label("data") == "Analytics"

    def test_unknown_falls_back_to_title(self):
        assert get_role_label("unknown_thing") == "Unknown_Thing"

    def test_empty_string(self):
        assert get_role_label("") == ""

    def test_all_known_roles_covered(self):
        """Every key in the map should round-trip through get_role_label."""
        for slug, label in ROLE_DISPLAY_LABELS.items():
            assert get_role_label(slug) == label
