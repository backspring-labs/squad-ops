"""Fenced code block parser for build handler output.

Extracts tagged fenced code blocks from LLM responses into structured
file records. Used by DevelopmentBuildHandler and QABuildValidateHandler
to parse multi-file output.

Part of SIP-Enhanced-Agent-Build-Capabilities, Phase 1.
"""

from __future__ import annotations

import re

# Match fence headers: ```<lang>:<path>
# Language is \w+, path is \S+ (no spaces), no other content on the line.
_FENCE_HEADER_RE = re.compile(r"^```(\w+):(\S+)\s*$", re.MULTILINE)

# Match a closing fence: ``` on its own line (possibly with trailing whitespace)
_FENCE_CLOSE_RE = re.compile(r"^```\s*$", re.MULTILINE)


def extract_fenced_files(response: str) -> list[dict]:
    """Parse ``<lang>:<path>`` fenced code blocks into structured file records.

    Scans the LLM response for fenced code blocks whose opening line matches
    the pattern ``\\`\\`\\`<language>:<filepath>``. Extracts the content between
    the opening and closing fences.

    Security: rejects absolute paths and paths containing ``..`` segments.

    Args:
        response: Raw LLM response text.

    Returns:
        List of dicts with keys ``filename``, ``content``, ``language``.
        Empty list if no valid tagged fences are found.
    """
    if not response:
        return []

    results: list[dict] = []
    pos = 0

    while pos < len(response):
        header_match = _FENCE_HEADER_RE.search(response, pos)
        if not header_match:
            break

        language = header_match.group(1)
        filepath = header_match.group(2)

        # Start of content is after the header line
        content_start = header_match.end() + 1  # skip newline after header

        # Find the closing fence
        close_match = _FENCE_CLOSE_RE.search(response, content_start)
        if not close_match:
            # No closing fence — skip this header
            pos = content_start
            continue

        content = response[content_start : close_match.start()]

        # Security: reject absolute paths
        if filepath.startswith("/"):
            pos = close_match.end()
            continue

        # Security: reject path traversal
        if ".." in filepath.split("/"):
            pos = close_match.end()
            continue

        # Reject colons in filenames (invalid on macOS/Windows, LLM artifact)
        if ":" in filepath:
            pos = close_match.end()
            continue

        # Strip single trailing newline from content (fence artifact)
        if content.endswith("\n"):
            content = content[:-1]

        results.append({
            "filename": filepath,
            "content": content,
            "language": language,
        })

        pos = close_match.end()

    return results
