"""Tests for the robust JSON extraction helper used by SIP-0079 impl handlers.

The pre-existing parse pattern (strip-leading-fence then ``json.loads``)
fails on every common LLM-output shape that isn't pure JSON: thinking
blocks, prose preamble, json-in-fence-after-prose. This regression hit
``governance.establish_contract`` on cyc_a4e6dc3afe7a (2026-05-05) and
silently aborted the implementation phase in ~4 minutes. The tolerant
extractor below is the load-bearing fix.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.impl._json_extraction import (
    JSONExtractionError,
    extract_first_json_object,
)

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Happy path — pure JSON
# ---------------------------------------------------------------------------


class TestPureJSON:
    def test_minimal_object(self):
        assert extract_first_json_object('{"x": 1}') == {"x": 1}

    def test_nested_object(self):
        text = '{"outer": {"inner": [1, 2, {"deep": true}]}}'
        assert extract_first_json_object(text) == {"outer": {"inner": [1, 2, {"deep": True}]}}

    def test_pure_json_with_surrounding_whitespace(self):
        assert extract_first_json_object('\n  {"x": 1}  \n') == {"x": 1}


# ---------------------------------------------------------------------------
# Real LLM-output shapes — the failure modes the cycle hit
# ---------------------------------------------------------------------------


class TestRealLLMShapes:
    def test_think_block_then_json(self):
        """Qwen3-family models emit <think>...</think> before content.
        Strict parsing sees `<` as char 0 and dies with the same error
        cyc_a4e6dc3afe7a hit."""
        text = (
            "<think>\n"
            "The user wants a contract. Let me think about the objective...\n"
            "Acceptance criteria should cover the join/leave endpoints.\n"
            "</think>\n"
            '{"objective": "Build runs app", "acceptance_criteria": ["passes tests"]}'
        )
        assert extract_first_json_object(text) == {
            "objective": "Build runs app",
            "acceptance_criteria": ["passes tests"],
        }

    def test_json_in_fence_with_prose_preamble(self):
        """The dominant mode: lead role narrating before emitting JSON."""
        text = (
            "Here is the run contract:\n\n"
            "```json\n"
            '{"correction_path": "patch", "decision_rationale": "fix it"}\n'
            "```\n\n"
            "Let me know if you have questions."
        )
        assert extract_first_json_object(text) == {
            "correction_path": "patch",
            "decision_rationale": "fix it",
        }

    def test_json_then_trailing_prose(self):
        """Some models emit JSON first, then explain. Trailing prose
        must be tolerated — we want the JSON, not the explanation."""
        text = (
            '{"objective": "x", "acceptance_criteria": []}\n\n'
            "Above is the contract. Note that I had to..."
        )
        assert extract_first_json_object(text) == {
            "objective": "x",
            "acceptance_criteria": [],
        }

    def test_think_block_and_fence_combined(self):
        """Belt-and-suspenders: thinking mode + fenced output is common."""
        text = (
            '<think>reasoning here</think>\n\nSure, here\'s the JSON:\n```\n{"path": "abort"}\n```'
        )
        assert extract_first_json_object(text) == {"path": "abort"}

    def test_only_first_object_returned_when_multiple_present(self):
        """If the LLM emits two JSON blocks, take the first — every
        impl handler expects exactly one decision/contract object."""
        text = '{"correction_path": "patch"}\n\nAnd an alternative:\n{"correction_path": "abort"}'
        assert extract_first_json_object(text) == {"correction_path": "patch"}


# ---------------------------------------------------------------------------
# String-aware brace matching
# ---------------------------------------------------------------------------


class TestBraceMatchingStringAware:
    """Brace-matcher must ignore { and } inside double-quoted strings.
    A JSON value like ``"description": "Use {} for placeholders"`` must
    not throw the matcher off-balance — this is the bug that would
    surface most often on values that quote source code or templates."""

    def test_braces_in_string_value_dont_break_matcher(self):
        text = '{"format": "Use {} for placeholders", "ok": true}'
        assert extract_first_json_object(text) == {
            "format": "Use {} for placeholders",
            "ok": True,
        }

    def test_escaped_quote_in_string_value(self):
        text = '{"msg": "She said \\"hi\\" with a {brace}", "n": 1}'
        assert extract_first_json_object(text) == {
            "msg": 'She said "hi" with a {brace}',
            "n": 1,
        }

    def test_brace_in_string_followed_by_real_brace(self):
        text = '{"k": "value with } inside"}'
        assert extract_first_json_object(text) == {"k": "value with } inside"}


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrors:
    def test_empty_response_raises(self):
        with pytest.raises(JSONExtractionError, match="empty"):
            extract_first_json_object("")

    def test_no_braces_at_all_raises(self):
        with pytest.raises(JSONExtractionError, match="no balanced"):
            extract_first_json_object("just prose, no JSON anywhere")

    def test_unbalanced_open_brace_raises(self):
        with pytest.raises(JSONExtractionError, match="no balanced"):
            extract_first_json_object('{"x": 1')  # missing closing }

    def test_top_level_array_raises(self):
        """Every impl handler expects a top-level object. An array is
        a contract violation; reject it with a clear error."""
        with pytest.raises(JSONExtractionError, match="object"):
            # The brace-matcher only finds {...} so a bare [...] gets
            # the no-balanced error, but a {...} containing array-only
            # content is technically still an object — this is fine.
            extract_first_json_object("[1, 2, 3]")

    def test_malformed_json_inside_braces_raises(self):
        with pytest.raises(JSONExtractionError, match="json.loads"):
            extract_first_json_object('{"x": notvalid}')

    def test_raw_excerpt_on_error(self):
        """The raw_excerpt attribute on the error carries the truncated
        response so callers can log it without having to re-truncate."""
        with pytest.raises(JSONExtractionError) as exc_info:
            extract_first_json_object("not json at all" * 100)
        assert exc_info.value.raw_excerpt.startswith("not json at all")
        assert len(exc_info.value.raw_excerpt) <= 500

    def test_raw_excerpt_respects_length_param(self):
        with pytest.raises(JSONExtractionError) as exc_info:
            extract_first_json_object("xxxxxxxxxxxxxx" * 50, excerpt_length=10)
        assert len(exc_info.value.raw_excerpt) == 10
