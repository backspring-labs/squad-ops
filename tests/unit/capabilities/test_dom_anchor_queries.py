"""#668: the DOM anchor contract's enforcement layer — the rules, replayed from the vault.

fay-14's suite (`cyc_42eed09efbec`) made zero anchor queries in every version while the
views carried the manifest's anchors from first fill; prompts alone under-delivered.
Each test names the bug the rule catches; the over-rejection cases are measured against
the accepted rolls' suites, since a rule that flags them costs every roll a retry.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.capabilities.dom_anchor_queries import (
    RULE_NO_ANCHOR_QUERIES,
    RULE_VIEW_ANCHORS_NOT_QUERIED,
    anchor_findings,
    anchor_observations,
)

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _inventory(manifest_name: str) -> dict[str, list[str]]:
    manifest = yaml.safe_load((_REPLAYS / manifest_name).read_text(encoding="utf-8"))
    return {
        r["view"]: list(r["testids"]) for r in manifest["frontend"]["routes"] if r.get("testids")
    }


def _suite(name: str) -> str:
    return (_REPLAYS / name).read_text(encoding="utf-8")


_INVENTORY = {
    "RunListView": ["run-list-view", "run-list", "run-row"],
    "RunDetailView": ["run-detail-view", "run-title", "participant-list"],
}


class TestReplays:
    def test_fay_14s_suite_breaks_both_rules(self):
        """The receipt: 55 text/role/label queries, zero anchor queries, and the
        imported `RunDetailView` never located through any of its anchors."""
        findings = anchor_findings(
            _suite("fay-14-RunDetailView.test.jsx"), _inventory("fay-14-interface_manifest.yaml")
        )
        assert [f.rule for f in findings] == [
            RULE_NO_ANCHOR_QUERIES,
            RULE_VIEW_ANCHORS_NOT_QUERIED,
        ]
        assert "55 text/role/label queries" in findings[0].detail
        assert "imports `RunDetailView` and queries none of its anchors — root `run-detail`" in (
            findings[1].detail
        )
        assert "`participant-list`" in findings[1].detail

    def test_the_accepted_roll_6_suite_is_clean(self):
        """1.6.6 React roll 6's authored suite imports two views and queries ten anchors,
        none of them a root — the rule that would have required the root would have
        cost an accepted roll an authoring retry (seven of nine such suites, measured)."""
        content = _suite("1-6-6-react-roll-6-frontend-suite.test.jsx")
        inventory = _inventory("1-6-6-react-roll-6-interface_manifest.yaml")
        assert anchor_findings(content, inventory) == []
        observed = anchor_observations(content, inventory)
        assert observed["covered_views"] == ["RunListView", "RunDetailView"]
        assert observed["unknown_anchors"] == []
        assert observed["text_queries"] == 0
        assert len(observed["queried"]) == 10
        assert "run-detail-view" not in observed["queried"]


class TestRules:
    def test_a_rendering_suite_with_no_anchor_query_is_flagged(self):
        content = (
            "import { render, screen } from '@testing-library/react'\n"
            "import App from '../App'\n"
            "it('x', () => { render(<App />); expect(screen.getByText('Runs')).toBeTruthy() })"
        )
        findings = anchor_findings(content, _INVENTORY)
        assert [f.rule for f in findings] == [RULE_NO_ANCHOR_QUERIES]
        assert "1 text/role/label queries" in findings[0].detail

    def test_a_suite_that_never_renders_is_not_judged_on_anchors(self):
        """A unit test of a helper renders nothing and owes the DOM nothing."""
        content = "import { fmt } from '../lib/format'\nit('x', () => { expect(fmt(1)).toBe('1') })"
        assert anchor_findings(content, _INVENTORY) == []

    @pytest.mark.parametrize(
        "query",
        [
            "screen.getByTestId('run-title')",
            'screen.findAllByTestId("participant-list")',
            "container.querySelector('[data-testid=\"run-detail-view\"]')",
        ],
    )
    def test_any_anchor_of_the_imported_view_satisfies_it(self, query):
        content = (
            "import { render, screen } from '@testing-library/react'\n"
            "import RunDetailView from '../views/RunDetailView.jsx'\n"
            f"it('x', () => {{ const {{ container }} = render(<RunDetailView />); {query} }})"
        )
        assert anchor_findings(content, _INVENTORY) == []

    def test_an_imported_view_located_only_through_another_views_anchors_is_flagged(self):
        content = (
            "import { render, screen } from '@testing-library/react'\n"
            "import RunDetailView from '../views/RunDetailView'\n"
            "it('x', () => { render(<RunDetailView />); screen.getByTestId('run-list') })"
        )
        findings = anchor_findings(content, _INVENTORY)
        assert [f.rule for f in findings] == [RULE_VIEW_ANCHORS_NOT_QUERIED]

    def test_an_unknown_anchor_is_banked_not_ruled_on(self):
        """The qa-side signal #1123 routes on: an anchor no view declares is an
        assertion no application can satisfy — reported here, judged there."""
        content = (
            "import { render, screen } from '@testing-library/react'\n"
            "import RunListView from '../views/RunListView'\n"
            "it('x', () => { render(<RunListView />); screen.getByTestId('run-list'); "
            "screen.getByTestId('invented-anchor') })"
        )
        assert anchor_findings(content, _INVENTORY) == []
        assert anchor_observations(content, _INVENTORY)["unknown_anchors"] == ["invented-anchor"]

    def test_an_empty_inventory_judges_nothing(self):
        assert anchor_findings("render(<App />)", {}) == []
