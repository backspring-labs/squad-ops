"""The delta between what a manifest declares and what the scaffold verifies (#951).

Bug this guards: the scaffold covers what it can *derive*, not what the manifest
*declares*, and the difference was recorded nowhere — so silence read as coverage.
Window roll 2 (`cyc_2f63e2d841eb`) banked green, 26/26 checks and 9/9 criteria, with
join and leave — the entire point of the application — untouched by every deterministic
layer. The feature was carried by a freely-authored additive suite that happened to be
good; nothing required that and nothing would have reported its absence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_coverage import (
    derive_scaffold_coverage,
    slot_routes,
    summarize_coverage,
)

pytestmark = [pytest.mark.domain_capabilities]

_REFERENCE = Path("examples/03_group_run/interface_manifest.yaml")

#: Roll 2's shape: join and leave folded into ONE endpoint discriminated by a request-body
#: field, which the probe deriver cannot reach (#948) and no minted read covers.
_ROLL_2_ROUTES = [
    ("GET", "/api/runs"),
    ("POST", "/api/runs"),
    ("GET", "/api/runs/{run_id}"),
    ("POST", "/api/runs/{run_id}"),
]


class TestTheDeltaIsReported:
    def test_an_endpoint_no_layer_reaches_is_named(self):
        """Roll 2's defect, in one line at seed time instead of by hand days later."""
        coverage = summarize_coverage(
            _ROLL_2_ROUTES,
            probe_routes=[("POST", "/api/runs", "vc-probe-api-runs")],
            slot_routes=[
                ("GET", "/api/runs", "slot-vs-get-api-runs"),
                ("POST", "/api/runs", "slot-vc-probe-api-runs"),
                ("GET", "/api/runs/{run_id}", "slot-vs-get-api-runs-run-id"),
            ],
        )
        assert [(e.method, e.path) for e in coverage.uncovered] == [("POST", "/api/runs/{run_id}")]
        assert coverage.declared == 4
        assert len(coverage.covered) == 3

    def test_the_summary_names_the_route_rather_than_counting_it(self):
        """A bare count invites "3 of 4, close enough". The name invites the only
        question worth asking — whether the one left out is the feature."""
        coverage = summarize_coverage(
            _ROLL_2_ROUTES, probe_routes=[], slot_routes=[("GET", "/api/runs", "slot-a")]
        )
        summary = coverage.summary()
        assert "POST /api/runs/{run_id}" in summary
        assert "GET /api/runs/{run_id}" in summary

    def test_full_coverage_says_so_explicitly(self):
        coverage = summarize_coverage(
            [("GET", "/api/runs")], probe_routes=[], slot_routes=[("GET", "/api/runs", "slot-a")]
        )
        assert coverage.uncovered == ()
        assert "none uncovered" in coverage.summary()


class TestWhatCountsAsCoverage:
    def test_a_probe_alone_covers_an_endpoint(self):
        coverage = summarize_coverage(
            [("POST", "/api/runs")], probe_routes=[("POST", "/api/runs", "p1")], slot_routes=[]
        )
        assert coverage.uncovered == ()
        assert coverage.endpoints[0].probe_ids == ("p1",)

    def test_a_parameter_name_mismatch_still_matches(self):
        """A probe path carries capture placeholders (`{created_id}`) while the manifest
        declares its own parameter name (`{run_id}`). Coverage is a question about the
        route, not about whose name for the parameter won — comparing them literally
        would report every parameterized endpoint as uncovered."""
        coverage = summarize_coverage(
            [("POST", "/api/runs/{run_id}/join")],
            probe_routes=[("POST", "/api/runs/{created_id}/join", "p-join")],
            slot_routes=[],
        )
        assert coverage.uncovered == ()
        assert coverage.endpoints[0].probe_ids == ("p-join",)

    def test_declaration_order_is_preserved(self):
        """The report reads in the order of the manifest it is about."""
        coverage = summarize_coverage(
            [("POST", "/b"), ("GET", "/a"), ("DELETE", "/c")], probe_routes=[], slot_routes=[]
        )
        assert [(e.method, e.path) for e in coverage.endpoints] == [
            ("POST", "/b"),
            ("GET", "/a"),
            ("DELETE", "/c"),
        ]

    def test_a_verb_with_no_derivation_source_is_reported_uncovered(self):
        """PUT/PATCH/DELETE have no source of scaffold behaviours at all, for any
        manifest. That is the class #951 names as surviving a #948 fix."""
        coverage = summarize_coverage(
            [("DELETE", "/api/runs/{run_id}")], probe_routes=[], slot_routes=[]
        )
        assert len(coverage.uncovered) == 1
        assert "NO deterministic coverage" in coverage.uncovered[0].describe()


class TestPrerequisitesAreNotCoverage:
    def test_a_replayed_create_does_not_credit_the_create_endpoint(self):
        """A behaviour that creates a run in order to read it asserts on the READ. If
        setup counted, a manifest could reach full coverage while asserting on one
        endpoint — inflating exactly the number this report exists to deflate."""

        class _Step:
            def __init__(self, method, url_path):
                self.method, self.url_path = method, url_path

        class _Behavior:
            def __init__(self, behavior_id, final, prerequisites):
                self.behavior_id, self.final, self.prerequisites = (
                    behavior_id,
                    final,
                    prerequisites,
                )

        behavior = _Behavior(
            "vs-get-api-runs-run-id",
            final=_Step("GET", "/api/runs/{run_id}"),
            prerequisites=(_Step("POST", "/api/runs"),),
        )
        assert slot_routes([behavior]) == [
            ("GET", "/api/runs/{run_id}", "slot-vs-get-api-runs-run-id")
        ]


class TestAgainstTheRealManifest:
    """The reference manifest is the worked example every other layer is pinned to, so
    a coverage report that disagreed with it would be reporting on something else."""

    @pytest.mark.skipif(not _REFERENCE.exists(), reason="reference manifest absent")
    def test_the_reference_manifest_is_fully_covered(self):
        manifest = InterfaceManifest.from_dict(yaml.safe_load(_REFERENCE.read_text()))
        coverage = derive_scaffold_coverage(manifest)
        assert coverage.uncovered == ()
        assert coverage.declared == len(manifest.api.endpoints)
        # every endpoint reached by at least one slot — the shells are the floor
        assert all(e.slot_ids for e in coverage.endpoints)

    @pytest.mark.skipif(not _REFERENCE.exists(), reason="reference manifest absent")
    def test_the_evidence_shape_carries_the_uncovered_list(self):
        """Banked so the delta is recoverable after the fact rather than re-derived."""
        manifest = InterfaceManifest.from_dict(yaml.safe_load(_REFERENCE.read_text()))
        banked = derive_scaffold_coverage(manifest).as_dict()
        assert banked["uncovered"] == []
        assert banked["declared"] == banked["covered"] == len(manifest.api.endpoints)
        assert {"method", "path", "probe_ids", "slot_ids"} <= set(banked["endpoints"][0])
