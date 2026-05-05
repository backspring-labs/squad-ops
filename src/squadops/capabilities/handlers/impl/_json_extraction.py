"""Robust JSON extraction for SIP-0079 impl handlers.

The three SIP-0079 implementation handlers (establish_contract,
correction_decision, analyze_failure) ask the LLM to return a JSON
object as the entire response. Strict-from-start parsing is brittle —
LLMs commonly emit:

- ``<think>...</think>`` blocks (Qwen3-family thinking mode) before
  the actual content.
- Prose preamble like ``"Here is the contract:"`` before a fenced
  JSON block.
- Trailing prose after the JSON.
- Code fences (``` json ... ```) anywhere in the response, not just
  at the start.

Any of those produce ``json.loads("<think>...") -> "char 0"`` errors
even when the actual JSON the LLM emitted is well-formed.

This module provides ``extract_first_json_object(text)`` — a tolerant
parser that finds the first balanced ``{...}`` after stripping
fences and brace-matching, returning the parsed object or raising
``JSONExtractionError`` with the truncated raw response so callers
can log it for triage.

The brace-matcher is string-aware: it ignores ``{`` and ``}`` inside
double-quoted strings (handling escaped quotes) so a JSON value like
``"description": "Use {} for placeholders"`` doesn't false-match.
"""

from __future__ import annotations

import json
import re
from typing import Any


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class JSONExtractionError(ValueError):
    """Raised when no parseable JSON object is present in the response.

    Carries ``raw_excerpt`` (first N chars of the response) so the
    caller can include it in a structured log line without having to
    re-truncate.
    """

    def __init__(self, message: str, raw_excerpt: str) -> None:
        super().__init__(message)
        self.raw_excerpt = raw_excerpt


def _strip_think_blocks(text: str) -> str:
    """Remove any ``<think>...</think>`` segments anywhere in the text.

    Qwen3-family models emit these blocks regardless of where they
    appear in the response. The handler doesn't care about reasoning
    traces — only the final JSON object.
    """
    return _THINK_BLOCK_RE.sub("", text)


def _strip_all_fences(text: str) -> str:
    """Strip every `````...````` block's
    fence markers (keeping the inner content).

    Handles `````json``, ```````,
    `````yaml``, etc. — every fence-language tag — by
    replacing the opening and closing fences with empty strings and
    leaving the inner content in place. JSON inside any fence becomes
    candidate text for the brace matcher.
    """
    fence_open = re.compile(r"```[a-zA-Z0-9_+\-]*\s*\n?")
    fence_close = re.compile(r"\n?```")
    text = fence_open.sub("", text)
    text = fence_close.sub("", text)
    return text


def _find_first_balanced_object(text: str) -> str | None:
    """Locate the first balanced ``{...}`` substring.

    String-aware: ignores ``{`` and ``}`` inside double-quoted strings
    so a JSON value like ``"format: {field}"`` doesn't false-match.

    Returns the balanced substring (including the surrounding braces)
    or ``None`` if no balanced object is found.
    """
    start: int | None = None
    depth = 0
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        ch = text[i]

        if in_string:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                if start is None:
                    start = i
                depth += 1
            elif ch == "}" and start is not None:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        i += 1

    return None


def extract_first_json_object(
    text: str,
    *,
    excerpt_length: int = 500,
) -> dict[str, Any]:
    """Parse the first JSON object from a possibly-noisy LLM response.

    Tolerates (in order):

    1. ``<think>...</think>`` reasoning blocks (Qwen3-family thinking
       mode).
    2. Markdown code fences anywhere in the text.
    3. Prose preamble or trailing content around the JSON.
    4. Whitespace.

    Args:
        text: The raw LLM response.
        excerpt_length: How many leading chars to include in the
            ``JSONExtractionError.raw_excerpt`` for diagnostic logging.

    Returns:
        The parsed JSON object (always a dict — JSON arrays raise
        ``JSONExtractionError`` because every impl handler expects a
        top-level object).

    Raises:
        JSONExtractionError: when no balanced ``{...}`` block exists,
        when the matched block fails ``json.loads``, or when the
        decoded value is not a dict.
    """
    if not text:
        raise JSONExtractionError("empty response", "")

    # Build an excerpt up-front so the caller always has it, even if
    # the rest of this function mutates `text` for parsing.
    raw_excerpt = text[:excerpt_length]

    cleaned = _strip_think_blocks(text)
    cleaned = _strip_all_fences(cleaned)

    candidate = _find_first_balanced_object(cleaned)
    if candidate is None:
        raise JSONExtractionError(
            "no balanced JSON object found in response",
            raw_excerpt,
        )

    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, ValueError) as exc:
        raise JSONExtractionError(
            f"first balanced object failed json.loads: {exc}",
            raw_excerpt,
        ) from exc

    if not isinstance(parsed, dict):
        raise JSONExtractionError(
            f"top-level JSON must be an object, got {type(parsed).__name__}",
            raw_excerpt,
        )

    return parsed
