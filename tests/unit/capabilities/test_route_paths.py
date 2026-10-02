"""The manifest's path-parameter reading, shared by every stack expander (#1794).

Each stack renders a parameter in its own router's syntax from this one reading. What a wrong
reading costs is a route that matches nothing (a parameter read as literal) or one that matches
something the manifest never declared (a literal read as a parameter).
"""

from __future__ import annotations

import pytest

from squadops.capabilities.route_paths import PathSegment, path_segments

pytestmark = [pytest.mark.domain_capabilities]

_JOIN = (PathSegment("runs"), PathSegment("run_id", param=True), PathSegment("join"))


@pytest.mark.parametrize(
    "path", ["/runs/{run_id}/join", "/runs/:run_id/join", "runs/{run_id}/join/"]
)
def test_a_parameter_reads_the_same_in_either_spelling(path):
    assert path_segments(path) == _JOIN


@pytest.mark.parametrize("path", ["/", "", "//"])
def test_the_root_has_no_segments(path):
    assert path_segments(path) == ()


@pytest.mark.parametrize("segment", ["{run_id}.json", "{}", ":", "{run_id", "run_id}", "[run_id]"])
def test_a_segment_only_partly_shaped_like_a_parameter_stays_literal(segment):
    assert path_segments(f"/runs/{segment}") == (PathSegment("runs"), PathSegment(segment))
