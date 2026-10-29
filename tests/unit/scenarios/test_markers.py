"""A suite's markers, the one definition the P2 sweep and the proposal's evidence share (SIP-0113
§10t ruling 3, §10ad).

What bugs would these catch? A short or letterless value counted as a marker, so every word the
squad writes reads as a leak; a goal that quotes a step's value in an escaped form passing the check
that holds it back; and a goal held back for containing nothing of the suite's. And #2786's two:
a value a step puts in its path never searched for, while a declared route's word, or a ``{name}``
reference to a saved value, is counted as one, so a suite reads clean while saying little.

Every suite here is invented.
"""

from __future__ import annotations

import pytest

from squadops.scenarios.markers import carries_a_marker, distinctive, suite_markers
from squadops.scenarios.models import parse_suite

pytestmark = [pytest.mark.domain_contracts]


@pytest.mark.parametrize("value", ["Pier", "12:30:00", "      ", "a1"])
def test_a_value_too_short_or_without_a_letter_is_no_marker(value):
    assert not distinctive(value)


@pytest.mark.parametrize(
    ("text", "carries"),
    [
        ('A reader exports the "Quarterly ledger" as a file', True),
        # As a JSON document holds it: the quotes escaped.
        ('{"goal": "exports the \\"Quarterly ledger\\""}', True),
        # COPY doubles the backslashes.
        ('exports the \\\\"Quarterly ledger\\\\"', True),
        ("A reader exports a ledger as a file", False),
    ],
)
def test_a_goal_carries_a_marker_in_any_form_a_store_writes_it(text, carries):
    """Bug caught: the check reading only the raw form, so a goal stored JSON-escaped passes."""
    assert carries_a_marker(text, ['"Quarterly ledger"']) is carries


def test_no_markers_hold_nothing_back():
    """Bug caught: an empty suite's marker set read as matching everything."""
    assert not carries_a_marker("any goal at all", [])


#: The first step of every scenario below: it files a varnholt and saves two names from it.
_FILE = {
    "action": "http",
    "method": "POST",
    "path": "/varnholts",
    "json": {"title": "Varnholt Ledger Ninety"},
    "save": {"varnholt_id": "id", "varnholt_title": "title"},
}
_FILED = "Varnholt Ledger Ninety"
#: The first step's endpoint, which every scenario declares, so its path gives no marker.
_POST = {"kind": "http_endpoint", "method": "POST", "path": "/varnholts"}
_SURFACES = [
    {"kind": "http_endpoint", "method": "GET", "path": "/varnholts/{varnholt_id}"},
    {"kind": "page", "path": "/varnholts/{varnholt_id}"},
]


def _markers(
    steps: list[dict], checks: list[dict] | None = None, surfaces: list[dict] | None = None
) -> set[str]:
    scenario = {
        "scenario_id": "varnholt",
        "goal": "A filed varnholt reads back",
        "surfaces": [_POST, *(_SURFACES if surfaces is None else surfaces)],
        "steps": [_FILE, *steps],
        "checks": checks or [{"check": "status", "step": 1, "equals": 201}],
    }
    return set(suite_markers(parse_suite({"name": "invented", "scenarios": [scenario]})))


def _get(path: str) -> dict:
    return {"action": "http", "method": "GET", "path": path}


@pytest.mark.parametrize(
    ("steps", "surfaces", "expected"),
    [
        # A route the scenario declares fits: its word is public, the value at its parameter isn't.
        ([_get("/varnholts/qx-unseen-thing-41")], None, {"qx-unseen-thing-41"}),
        # A page's route, its parameter written as the router writes it.
        (
            [{"action": "visit", "path": "/varnholts/zentrifal-page-77"}],
            [{"kind": "page", "path": "/varnholts/:varnholt_id"}],
            {"zentrifal-page-77"},
        ),
        # A trailing slash on either side is the same route.
        ([_get("/varnholts/qx-unseen-thing-41/")], None, {"qx-unseen-thing-41"}),
        # No declared route fits, by length either way, so every segment is read.
        ([_get("/quorvax-hidden-ledger/archived")], None, {"quorvax-hidden-ledger", "archived"}),
        ([_get("/varnholts/qx-unseen-thing-41/archived")], None,
         {"varnholts", "qx-unseen-thing-41", "archived"}),
        (
            [_get("/quorvax-hidden-ledger")],
            [{"kind": "http_endpoint", "method": "GET", "path": "/quorvax-hidden-ledger/{id}"}],
            {"quorvax-hidden-ledger"},
        ),
        # As long as a declared route, but a different word where the route has one.
        ([_get("/grenwhistle/qx-unseen-thing-41")], None, {"grenwhistle", "qx-unseen-thing-41"}),
        # A page's route is no endpoint's: an HTTP step is read against the endpoints alone.
        (
            [_get("/varnholts/qx-unseen-thing-41")],
            [{"kind": "page", "path": "/varnholts/{varnholt_id}"}],
            {"varnholts", "qx-unseen-thing-41"},
        ),
        # Decoded, as a query value is.
        ([_get("/varnholts/Ostrel%20Banding")], None, {"Ostrel Banding"}),
        # The query string is still read; a reference in it is not.
        ([_get("/varnholts?label=Brindlewick+Annex&owner={varnholt_id}")], None,
         {"Brindlewick Annex"}),
        # Nothing to read.
        ([_get("")], None, set()),
        ([_get("/")], None, set()),
        ([{"action": "visit", "path": "/"}], [{"kind": "page", "path": "/"}], set()),
    ],
    ids=[
        "route-word", "page-route", "trailing-slash", "no-route", "longer-than-route",
        "shorter-than-route", "other-word", "kind", "encoded", "query", "empty", "root",
        "root-page",
    ],
)  # fmt: skip
def test_a_steps_path_segments_are_values_and_a_declared_routes_words_are_not(
    steps, surfaces, expected
):
    """#2786 (1). Bugs caught: a value a step puts in its path never searched for; a route's own
    word counted, so the public check reads it as public in every repository; a route that doesn't
    fit the path, by length, by a word or by its kind, taken to make the path's words public."""
    assert _markers(steps, surfaces=surfaces) == {_FILED, *expected}


@pytest.mark.parametrize(
    ("steps", "checks", "expected"),
    [
        ([], [{"check": "json", "step": 1, "path": "id", "equals": "{varnholt_id}"}], set()),
        ([], [{"check": "json", "step": 1, "path": "", "where": {"title": "{varnholt_title}"}}],
         set()),
        ([], [{"check": "json", "step": 1, "path": "", "in": [" {varnholt_title} "]}], set()),
        ([], [{"check": "json", "step": 1, "path": "", "contains": "{varnholt_id}"}], set()),
        # No declared route fits, so the path is read whole: its word is, its reference isn't.
        ([_get("/grenwhistle/{varnholt_id}")], None, {"grenwhistle"}),
        ([{**_get("/varnholts/{varnholt_id}"), "headers": {"X-Ref": "{varnholt_id}"}}], None,
         set()),
        ([{"action": "http", "method": "POST", "path": "/varnholts",
           "json": {"copy_of": "{varnholt_title}"}}], None, set()),
        (
            [{"action": "visit", "path": "/varnholts/{varnholt_id}"},
             {"action": "fill", "value": "{varnholt_title}",
              "target": {"role": "textbox", "names": ["Title"], "text": "{varnholt_id}"}}],
            [{"check": "text", "step": 3, "pattern": "{varnholt_title}"}],
            set(),
        ),
    ],
    ids=["equals", "where", "in-padded", "contains", "path", "header", "json", "page"],
)  # fmt: skip
def test_a_whole_reference_to_a_saved_value_is_no_marker_wherever_it_is(steps, checks, expected):
    """#2786 (2). Bug caught: ``{varnholt_id}`` counted as a value, so a suite whose checks all
    compare one response with another (§10ab) reports only references, which nothing ever holds."""
    assert _markers(steps, checks) == {_FILED, *expected}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # The rendered value holds each run of text, and never the reference.
        ("Filed under {varnholt_id} by Ostlander Pell", {"Filed under", "by Ostlander Pell"}),
        # Each run is a marker only as any value is: six characters with a letter.
        ("No. {varnholt_id} of Hesketh Marrow", {"of Hesketh Marrow"}),
        ("{varnholt_id}{varnholt_title}", set()),
        # Not a reference (a name starts with a letter), so the text is kept whole, as before.
        ("Sorvane {1} Quillet", {"Sorvane {1} Quillet"}),
    ],
)
def test_a_string_mixing_text_and_references_gives_each_run_of_its_text(value, expected):
    """#2786 (2). Bugs caught: the whole string kept, reference and all, so the value it renders
    is never found where it leaked; a run kept with the space that joined it to a reference."""
    checks = [{"check": "json", "step": 1, "path": "note", "equals": value}]
    assert _markers([], checks) == {_FILED, *expected}


def test_a_patterns_reference_ends_a_run_and_is_none():
    """#2786 (2). Bug caught: a pattern's ``{varnholt_title}`` read as the literal run
    ``varnholt_title``, a name counted as a value."""
    steps = [{"action": "visit", "path": "/varnholts/{varnholt_id}"}]
    checks = [{"check": "text", "step": 2, "pattern": "{varnholt_title}\\s+\\(Sorvane Quay\\)"}]
    assert _markers(steps, checks) == {_FILED, "(Sorvane Quay)"}
