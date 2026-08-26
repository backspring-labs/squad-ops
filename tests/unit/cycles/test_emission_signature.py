"""#998 — what KIND of nothing an empty emission was.

Three zero-extraction shapes with opposite remedies were one marker: the V7 roll-1 void
spent 8,192 tokens (the whole completion budget) and 12.7 minutes closing no content, and
the banked analysis guessed "safety filter, context overload". The signature is computed
from facts the LLM call already reports. Each test names the bug it catches.
"""

from __future__ import annotations

import pytest

from squadops.cycles.emission_integrity import (
    SIGNATURE_CAP_EXHAUSTED,
    SIGNATURE_EMPTY,
    SIGNATURE_UNEXTRACTABLE,
    classify_empty_emission,
    emission_retry_reason_line,
    no_fenced_blocks_failure,
)

pytestmark = [pytest.mark.domain_orchestration]


@pytest.mark.parametrize(
    ("chars", "tokens", "cap", "expected"),
    [
        (0, 8192, 8192, SIGNATURE_CAP_EXHAUSTED),  # the V7 roll-1 shape, exactly
        (0, 8300, 8192, SIGNATURE_CAP_EXHAUSTED),  # a provider reporting past the cap still hit it
        (0, 120, 8192, SIGNATURE_EMPTY),  # stopped early with nothing: not a budget problem
        (0, None, 8192, SIGNATURE_EMPTY),  # tokens unknown → the cap cannot be asserted
        (0, 8192, None, SIGNATURE_EMPTY),  # cap unknown → likewise
        (0, 8192, 0, SIGNATURE_EMPTY),  # a zero cap is no cap
        (2500, 8192, 8192, SIGNATURE_UNEXTRACTABLE),  # content came back; the format is the defect
        (40, 40, 8192, SIGNATURE_UNEXTRACTABLE),
    ],
)
def test_the_signature_is_read_from_the_calls_own_facts(chars, tokens, cap, expected):
    assert classify_empty_emission(chars, tokens, cap) == expected


def test_the_marker_carries_the_facts_and_the_signature():
    """Bug caught: a marker that says `no_fenced_blocks` and nothing else — the shape
    the correction decision guessed against."""
    marker = no_fenced_blocks_failure(0, ["app/x.ts"], completion_tokens=8192, completion_cap=8192)
    assert marker["signature"] == SIGNATURE_CAP_EXHAUSTED
    assert marker["completion_tokens"] == 8192
    assert marker["completion_cap"] == 8192
    assert marker["reason"] == "no_fenced_blocks"
    assert marker["expected_artifacts"] == ["app/x.ts"]


def test_a_producer_that_reports_no_tokens_still_emits_a_truthful_marker():
    """Pre-#998 call sites pass no token facts; the marker must not invent a cap verdict."""
    marker = no_fenced_blocks_failure(0, None)
    assert marker["signature"] == SIGNATURE_EMPTY
    assert marker["completion_tokens"] is None and marker["completion_cap"] is None


@pytest.mark.parametrize(
    ("marker", "fragment"),
    [
        (
            no_fenced_blocks_failure(0, None, completion_tokens=8192, completion_cap=8192),
            "full 8192-token completion budget",
        ),
        (
            no_fenced_blocks_failure(0, None, completion_tokens=10, completion_cap=8192),
            "response was empty",
        ),
        (
            no_fenced_blocks_failure(3000, None, completion_tokens=900, completion_cap=8192),
            "3000-character response",
        ),
        ({"reason": "something_else"}, "something_else"),
    ],
)
def test_the_retry_line_names_the_remedy_for_each_signature(marker, fragment):
    """The retry feedback must not tell a budget-exhausted model to 'use fences' — the
    two remedies are opposite, and the line is where the next attempt learns which."""
    assert fragment in emission_retry_reason_line(marker)
