"""Prompt size guard for LLM context window management (SIP-0073).

Provides token estimation and prompt truncation to prevent context window
overflow when calling LLM chat(). Extracted to a dedicated module per D8
for clean testability.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN_ESTIMATE = 4

_PRIOR_ANALYSIS_HEADING = "## Prior Analysis from Upstream Roles"


def _estimate_tokens(text: str) -> int:
    """Estimate token count using chars/4 heuristic.

    This is a conservative approximation — real tokenizers vary by model,
    but chars/4 is a widely-used ballpark for English text.
    """
    return len(text) // _CHARS_PER_TOKEN_ESTIMATE


def _guard_prompt_size(
    system_prompt: str,
    user_prompt: str,
    max_completion_tokens: int,
    context_window: int | None,
) -> str:
    """Guard prompt against context window overflow.

    Attempts to truncate the '## Prior Analysis from Upstream Roles' section
    if the prompt exceeds the available token budget. Raises ValueError with
    structured JSON diagnostics if the prompt still cannot fit.

    Args:
        system_prompt: The system prompt text.
        user_prompt: The user prompt text (may be truncated).
        max_completion_tokens: Reserved tokens for LLM completion output.
        context_window: Total context window size in tokens, or None if unknown.

    Returns:
        The (possibly truncated) user_prompt.

    Raises:
        ValueError: If prompt cannot fit within context window, even after
            truncation. The error message is a JSON string with fixed keys.
    """
    if context_window is None:
        logger.debug("No context window known; skipping prompt size guard")
        return user_prompt

    available = context_window - max_completion_tokens

    if available <= 0:
        raise ValueError(
            json.dumps(
                {
                    "error_code": "PROMPT_EXCEEDS_CONTEXT_WINDOW",
                    "estimated_prompt_tokens": _estimate_tokens(
                        system_prompt + "\n\n" + user_prompt
                    ),
                    "effective_completion_tokens": max_completion_tokens,
                    "context_window": context_window,
                    "available_prompt_tokens": available,
                    "truncation_attempted": False,
                    "truncated_sections": [],
                }
            )
        )

    combined = system_prompt + "\n\n" + user_prompt
    estimated = _estimate_tokens(combined)

    if estimated <= available:
        return user_prompt

    # Attempt truncation of prior analysis section
    heading_pos = user_prompt.find(_PRIOR_ANALYSIS_HEADING)

    if heading_pos < 0:
        # No truncatable section found
        raise ValueError(
            json.dumps(
                {
                    "error_code": "PROMPT_EXCEEDS_CONTEXT_WINDOW",
                    "estimated_prompt_tokens": estimated,
                    "effective_completion_tokens": max_completion_tokens,
                    "context_window": context_window,
                    "available_prompt_tokens": available,
                    "truncation_attempted": False,
                    "truncated_sections": [],
                }
            )
        )

    # Truncate: remove from heading to end of prompt, replace with note
    truncated_prompt = (
        user_prompt[:heading_pos].rstrip()
        + "\n\n## Prior Analysis from Upstream Roles\n"
        + "[Truncated to fit context window]\n"
    )

    # Re-estimate with truncated prompt
    truncated_combined = system_prompt + "\n\n" + truncated_prompt
    truncated_estimated = _estimate_tokens(truncated_combined)

    if truncated_estimated <= available:
        logger.info(
            "Prompt truncated to fit context window: %d → %d estimated tokens (available: %d)",
            estimated,
            truncated_estimated,
            available,
        )
        return truncated_prompt

    # Still doesn't fit after truncation
    raise ValueError(
        json.dumps(
            {
                "error_code": "PROMPT_EXCEEDS_CONTEXT_WINDOW",
                "estimated_prompt_tokens": truncated_estimated,
                "effective_completion_tokens": max_completion_tokens,
                "context_window": context_window,
                "available_prompt_tokens": available,
                "truncation_attempted": True,
                "truncated_sections": [_PRIOR_ANALYSIS_HEADING],
            }
        )
    )
