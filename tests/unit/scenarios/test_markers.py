"""A suite's markers, the one definition the P2 sweep and the proposal's evidence share (SIP-0113
§10t ruling 3).

What bugs would these catch? A short or letterless value counted as a marker, so every word the
squad writes reads as a leak; a goal that quotes a step's value in an escaped form passing the check
that holds it back; and a goal held back for containing nothing of the suite's.
"""

from __future__ import annotations

import pytest

from squadops.scenarios.markers import carries_a_marker, distinctive

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
