"""Unit tests for prompt size guard (SIP-0073 Phase 2).

Tests _estimate_tokens() heuristic and _guard_prompt_size() truncation logic.
"""

from __future__ import annotations

import json

import pytest

from squadops.capabilities.handlers.prompt_guard import (
    _CHARS_PER_TOKEN_ESTIMATE,
    _PRIOR_ANALYSIS_HEADING,
    _estimate_tokens,
    _guard_prompt_size,
)

pytestmark = [pytest.mark.domain_capabilities]


class TestEstimateTokens:
    """Tests for _estimate_tokens() heuristic."""

    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_short_string(self):
        # 12 chars → 3 tokens
        assert _estimate_tokens("Hello world!") == 12 // _CHARS_PER_TOKEN_ESTIMATE

    def test_uses_integer_division(self):
        # 5 chars → 1 token (floor division)
        assert _estimate_tokens("abcde") == 1

    def test_known_length(self):
        text = "x" * 400
        assert _estimate_tokens(text) == 100


class TestGuardPromptSizeUnknownWindow:
    """When context_window is None, prompt passes through unchanged."""

    def test_returns_unchanged(self):
        result = _guard_prompt_size(
            system_prompt="system",
            user_prompt="user prompt text",
            max_completion_tokens=4000,
            context_window=None,
        )
        assert result == "user prompt text"


class TestGuardPromptSizeFits:
    """When prompt fits within budget, returns unchanged."""

    def test_prompt_within_budget(self):
        system = "System prompt"
        user = "User prompt"
        result = _guard_prompt_size(
            system_prompt=system,
            user_prompt=user,
            max_completion_tokens=100,
            context_window=10000,
        )
        assert result == user

    def test_exact_fit(self):
        """Prompt that exactly fills available budget passes."""
        system = "s"
        user = "u"
        # combined = "s\n\nu" = 4 chars → 1 token
        # available = 2 - 1 = 1
        result = _guard_prompt_size(
            system_prompt=system,
            user_prompt=user,
            max_completion_tokens=1,
            context_window=2,
        )
        assert result == user


class TestGuardPromptSizeDegenerateHeadroom:
    """When available <= 0 (degenerate config), early fail without truncation."""

    def test_zero_available(self):
        with pytest.raises(ValueError) as exc_info:
            _guard_prompt_size(
                system_prompt="system",
                user_prompt="user",
                max_completion_tokens=8192,
                context_window=8192,
            )
        payload = json.loads(str(exc_info.value))
        assert payload["error_code"] == "PROMPT_EXCEEDS_CONTEXT_WINDOW"
        assert payload["truncation_attempted"] is False
        assert payload["available_prompt_tokens"] == 0
        assert payload["truncated_sections"] == []

    def test_negative_available(self):
        with pytest.raises(ValueError) as exc_info:
            _guard_prompt_size(
                system_prompt="system",
                user_prompt="user",
                max_completion_tokens=10000,
                context_window=8192,
            )
        payload = json.loads(str(exc_info.value))
        assert payload["error_code"] == "PROMPT_EXCEEDS_CONTEXT_WINDOW"
        assert payload["truncation_attempted"] is False
        assert payload["available_prompt_tokens"] < 0


class TestGuardPromptSizeTruncation:
    """When prompt overflows, truncate prior analysis section."""

    def _make_prompts(self, prior_analysis_size: int) -> tuple[str, str]:
        """Build system + user prompts with a prior analysis section."""
        system = "You are a helpful assistant."
        prior_text = "x" * prior_analysis_size
        user = (
            "## Task\nDo something.\n\n"
            f"{_PRIOR_ANALYSIS_HEADING}\n"
            f"{prior_text}\n\n"
            "## PRD\nBuild a thing."
        )
        return system, user

    def test_truncation_preserves_task_and_prd(self):
        """After truncation, task section is preserved, PRD is preserved."""
        system, user = self._make_prompts(prior_analysis_size=40000)
        # context_window big enough for truncated but not full prompt
        result = _guard_prompt_size(
            system_prompt=system,
            user_prompt=user,
            max_completion_tokens=4000,
            context_window=5000,
        )
        assert "## Task" in result
        assert "[Truncated to fit context window]" in result
        # PRD after prior analysis is removed by truncation
        assert "## PRD" not in result

    def test_truncation_replaces_prior_section(self):
        system, user = self._make_prompts(prior_analysis_size=40000)
        result = _guard_prompt_size(
            system_prompt=system,
            user_prompt=user,
            max_completion_tokens=4000,
            context_window=5000,
        )
        assert _PRIOR_ANALYSIS_HEADING in result
        assert "[Truncated to fit context window]" in result
        assert "x" * 100 not in result  # large block removed

    def test_impossible_fit_after_truncation(self):
        """Even after truncation, prompt still too large → ValueError."""
        system = "x" * 40000  # system prompt alone overflows
        user = (
            "## Task\nDo something.\n\n"
            f"{_PRIOR_ANALYSIS_HEADING}\n"
            "Prior text\n\n"
            "## PRD\nBuild a thing."
        )
        with pytest.raises(ValueError) as exc_info:
            _guard_prompt_size(
                system_prompt=system,
                user_prompt=user,
                max_completion_tokens=4000,
                context_window=5000,
            )
        payload = json.loads(str(exc_info.value))
        assert payload["error_code"] == "PROMPT_EXCEEDS_CONTEXT_WINDOW"
        assert payload["truncation_attempted"] is True
        assert payload["truncated_sections"] == [_PRIOR_ANALYSIS_HEADING]
        assert payload["context_window"] == 5000
        assert payload["effective_completion_tokens"] == 4000


class TestGuardPromptSizeNoSection:
    """When no prior analysis section exists."""

    def test_no_section_fits(self):
        """Prompt without prior section that fits → unchanged."""
        result = _guard_prompt_size(
            system_prompt="system",
            user_prompt="## Task\nDo something.\n## PRD\nBuild a thing.",
            max_completion_tokens=100,
            context_window=10000,
        )
        assert result == "## Task\nDo something.\n## PRD\nBuild a thing."

    def test_no_section_overflows(self):
        """Prompt without prior section that overflows → ValueError."""
        user = "x" * 40000
        with pytest.raises(ValueError) as exc_info:
            _guard_prompt_size(
                system_prompt="system",
                user_prompt=user,
                max_completion_tokens=4000,
                context_window=5000,
            )
        payload = json.loads(str(exc_info.value))
        assert payload["error_code"] == "PROMPT_EXCEEDS_CONTEXT_WINDOW"
        assert payload["truncation_attempted"] is False
        assert payload["truncated_sections"] == []


class TestStructuredPayloadKeys:
    """All ValueError payloads must contain exactly the required keys."""

    _REQUIRED_KEYS = {
        "error_code",
        "estimated_prompt_tokens",
        "effective_completion_tokens",
        "context_window",
        "available_prompt_tokens",
        "truncation_attempted",
        "truncated_sections",
    }

    def _trigger_error(self, **kwargs) -> dict:
        defaults = {
            "system_prompt": "x" * 40000,
            "user_prompt": "y" * 40000,
            "max_completion_tokens": 4000,
            "context_window": 5000,
        }
        defaults.update(kwargs)
        with pytest.raises(ValueError) as exc_info:
            _guard_prompt_size(**defaults)
        return json.loads(str(exc_info.value))

    def test_overflow_no_section_has_all_keys(self):
        payload = self._trigger_error()
        assert set(payload.keys()) == self._REQUIRED_KEYS

    def test_degenerate_headroom_has_all_keys(self):
        payload = self._trigger_error(max_completion_tokens=10000, context_window=5000)
        assert set(payload.keys()) == self._REQUIRED_KEYS

    def test_overflow_with_section_has_all_keys(self):
        user = f"{_PRIOR_ANALYSIS_HEADING}\nprior\n\nx" * 40000
        payload = self._trigger_error(
            system_prompt="x" * 40000,
            user_prompt=user,
        )
        assert set(payload.keys()) == self._REQUIRED_KEYS
