"""Scenarios and suites are content-addressed (SIP-0113 §4.1; #2413)."""

from __future__ import annotations

import copy

import pytest

from squadops.scenarios.models import ScenarioInvalid, SurfaceKind, parse_suite
from tests.unit.scenarios.suite_fixtures import SUITE, suite_doc


def test_a_suite_is_named_by_its_scenarios_content_not_its_label_or_order():
    """Bug caught: a suite whose digest moved with its name or the order it was written in, so
    the same scenarios read as two suites and a result could not say which it ran; or one whose
    held-out steps changed without its digest moving, so a pinned campaign ran different checks."""
    suite = parse_suite(SUITE)
    renamed = parse_suite(suite_doc(name="another label"))
    reordered = parse_suite(suite_doc(scenarios=list(reversed(SUITE["scenarios"]))))
    changed = suite_doc()
    changed["scenarios"][1]["checks"][0]["equals"] = 422
    edited = parse_suite(changed)

    assert suite.digest == renamed.digest == reordered.digest
    assert edited.digest != suite.digest
    assert edited.scenarios[0].version == suite.scenarios[0].version
    assert edited.scenarios[1].version != suite.scenarios[1].version
    assert suite.scenarios[0].surfaces[0].method == "POST"
    assert suite.scenarios[0].surfaces[1].kind is SurfaceKind.PAGE


def _broken(path: tuple, value) -> dict:
    doc = copy.deepcopy(SUITE)
    target = doc
    for key in path[:-1]:
        target = target[key]
    if value is ...:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return doc


@pytest.mark.parametrize(
    ("doc", "message"),
    [
        (_broken(("scenarios", 0, "goal"), " "), "goal must be non-empty"),
        (_broken(("scenarios", 0, "surfaces", 0, "kind"), "http"), "kind is one of"),
        (_broken(("scenarios", 0, "surfaces", 0, "method"), ...), "method must be non-empty"),
        (_broken(("scenarios", 0, "surfaces", 1, "method"), "GET"), "a page surface has no method"),
        (_broken(("scenarios", 0, "surfaces", 1, "path"), "runs"), "starts with '/'"),
        (_broken(("scenarios", 0, "steps"), []), "steps must be a non-empty list"),
        (_broken(("scenarios", 0, "steps", 0, "action"), ...), "'action' must be non-empty"),
        (_broken(("scenarios", 0, "checks"), ...), "checks must be a non-empty list"),
        (_broken(("scenarios", 1, "scenario_id"), "join-and-leave"), "unique within a suite"),
        (_broken(("scenarios",), []), "non-empty list of scenarios"),
    ],
    ids=[
        "no-goal",
        "unknown-surface-kind",
        "endpoint-without-method",
        "page-with-method",
        "relative-path",
        "no-steps",
        "step-without-action",
        "no-checks",
        "repeated-id",
        "empty-suite",
    ],
)
def test_a_suite_that_cannot_be_held_as_given_is_refused(doc, message):
    """Bug caught: a scenario stored that no runner can run (no steps, no check, a surface of
    no known kind), or two scenarios under one id, so a result names neither."""
    with pytest.raises(ScenarioInvalid, match=message):
        parse_suite(doc)
