"""Fenced code block parser for build handler output.

Extracts tagged fenced code blocks from LLM responses into structured
file records. Used by DevelopmentDevelopHandler, BuilderAssembleHandler,
and QATestHandler to parse multi-file output.

Recognized formats, in priority order (most explicit first):

1. Strict tagged fence — ``` ``` <language>:<filepath>``` ```
2. Filename in language slot for special names — ``` ``` Dockerfile``` ```,
   ``` ``` Makefile``` ```, etc.
3. Filename heading immediately preceding the fence — ``#`` through ``######``
   ending in a path-like token (``models.py``, ``backend/main.py``,
   ``Dockerfile``).
4. First-line filename comment inside the fence — ``# path/to/file.py`` or
   ``// path/to/file.py`` as the first line of the body. The comment line
   is stripped from the extracted content.

Models naturally drift between these formats; the parser tolerates all of
them so a one-character format slip doesn't drop the whole task on the floor.
The strict format is still the recommended one and round-trips losslessly.

Part of SIP-Enhanced-Agent-Build-Capabilities, Phase 1.
"""

from __future__ import annotations

import re

# Strict format header: ```<lang>:<path>
_STRICT_HEADER_RE = re.compile(r"^```(\w+):(\S+)\s*$", re.MULTILINE)

# Permissive open fence: ```<token> where <token> may be empty. Models
# sometimes emit a bare ``` immediately after a filename heading
# (``## Dockerfile`` then ``` ```\n...```\n`` `), so we cannot require
# a non-empty language slot. The ambiguity with a close fence is resolved
# by sequential scanning: after parsing a fence we advance past its
# close, so a stray unmatched ``` only causes a wasted lookahead.
_OPEN_FENCE_RE = re.compile(r"^```(\S*)\s*$", re.MULTILINE)

# Closing fence: ``` on its own line (possibly trailing whitespace)
_FENCE_CLOSE_RE = re.compile(r"^```\s*$", re.MULTILINE)

# Markdown heading whose text is a path-like token. Accepts headings of the
# form "## models.py", "### `backend/main.py`", "# Dockerfile". Requires
# either an extension (e.g. ``.py``) or a known special name so prose
# headings like "## Implementation Notes" don't match.
_SPECIAL_NAMES = ("Dockerfile", "Makefile", "Rakefile", "Gemfile", "Procfile")
_SPECIAL_NAMES_RE = "|".join(_SPECIAL_NAMES)
_HEADING_RE = re.compile(
    rf"^#{{1,6}}\s+`?(?P<path>[\w./-]+\.[a-zA-Z0-9]+|{_SPECIAL_NAMES_RE})`?\s*$",
    re.MULTILINE,
)

# First line of fence body containing a filename inside a comment. Recognizes
# Python/shell ``#``, C/JS ``//``, SQL ``--``, and C-block ``/*`` openers.
_FILENAME_COMMENT_RE = re.compile(
    rf"^\s*(?:#|//|--|/\*)\s*(?P<path>[\w./-]+\.[a-zA-Z0-9]+|{_SPECIAL_NAMES_RE})\b",
)

# Filenames that LLMs often emit as the language slot (``` ```Dockerfile``` ```).
_SPECIAL_FILENAMES_AS_LANG = set(_SPECIAL_NAMES)

_HEADING_PROSE_DISTANCE_LINES = 4
"""Max newline count between a filename heading and the fence it labels.

Accepts ``heading\\nfence`` (1), ``heading\\n\\nfence`` (2), and a short
prose paragraph (≤4) between them. Tighter than this drops legitimate
patterns; looser starts capturing unrelated headings.
"""


def _path_is_safe(path: str) -> bool:
    """Reject absolute paths, traversal segments, and colons (LLM artifacts)."""
    if path.startswith("/"):
        return False
    if ".." in path.split("/"):
        return False
    if ":" in path:
        return False
    return True


def _strip_trailing_newline(content: str) -> str:
    return content[:-1] if content.endswith("\n") else content


def _resolve_filename_from_heading(
    response: str,
    fence_start: int,
    last_used_heading_pos: int,
) -> tuple[str | None, int]:
    """Return ``(filename, heading_pos)`` if a filename-shaped heading sits
    just before ``fence_start`` (within ``_HEADING_PROSE_DISTANCE_LINES``
    newlines) and *after* ``last_used_heading_pos``. Otherwise
    ``(None, last_used_heading_pos)``.
    """
    window_start = max(last_used_heading_pos + 1, max(0, fence_start - 500))
    window = response[window_start:fence_start]
    matches = list(_HEADING_RE.finditer(window))
    for match in reversed(matches):
        lines_between = window[match.end() : len(window)].count("\n")
        if lines_between <= _HEADING_PROSE_DISTANCE_LINES:
            # Track the END of the heading line so the next fence's window
            # starts on the line *after* this heading. Tracking the start
            # would let the same heading match again on the next iteration
            # (the regex's ^ anchor still finds the line beginning even
            # one character into the heading text).
            return match.group("path"), window_start + match.end()
    return None, last_used_heading_pos


def _resolve_filename_from_first_comment(body: str) -> tuple[str | None, str]:
    """If the first line of ``body`` is a comment containing a filename,
    return ``(filename, body_with_first_line_stripped)``. Otherwise
    ``(None, body)``.
    """
    nl = body.find("\n")
    first_line = body if nl == -1 else body[:nl]
    match = _FILENAME_COMMENT_RE.match(first_line)
    if match is None:
        return None, body
    remainder = "" if nl == -1 else body[nl + 1 :]
    return match.group("path"), remainder


def extract_fenced_files(response: str) -> list[dict]:
    """Parse fenced code blocks into structured file records.

    Tries multiple resolution strategies per fence (see module docstring).
    Returns a list of ``{filename, content, language}`` dicts. Empty list
    if no resolvable, security-safe fences are found.

    Security: rejects absolute paths, paths containing ``..`` segments,
    and paths containing ``:``.

    Args:
        response: Raw LLM response text.

    Returns:
        List of dicts with keys ``filename``, ``content``, ``language``.
    """
    if not response:
        return []

    results: list[dict] = []
    pos = 0
    last_used_heading_pos = -1

    while pos < len(response):
        open_match = _OPEN_FENCE_RE.search(response, pos)
        if not open_match:
            break

        body_start = open_match.end() + 1  # skip newline after header
        close_match = _FENCE_CLOSE_RE.search(response, body_start)
        if not close_match:
            # No closing fence — abandon this opener and resume past it
            pos = body_start
            continue

        body = response[body_start : close_match.start()]
        token = open_match.group(1)
        filename: str | None = None
        language: str = token

        if ":" in token:
            # Strategy 1: strict ```<lang>:<path>
            language, _, filename = token.partition(":")
        elif token in _SPECIAL_FILENAMES_AS_LANG:
            # Strategy 2: ```Dockerfile (filename in language slot)
            filename = token
            language = token.lower()
        else:
            # Strategy 3: filename heading immediately preceding the fence
            heading_filename, last_used_heading_pos = _resolve_filename_from_heading(
                response, open_match.start(), last_used_heading_pos
            )
            if heading_filename is not None:
                filename = heading_filename
            else:
                # Strategy 4: first-line filename comment inside body
                comment_filename, stripped_body = _resolve_filename_from_first_comment(body)
                if comment_filename is not None:
                    filename = comment_filename
                    body = stripped_body

        if filename is None or not _path_is_safe(filename):
            pos = close_match.end()
            continue

        results.append(
            {
                "filename": filename,
                "content": _strip_trailing_newline(body),
                "language": language or "text",
            }
        )
        pos = close_match.end()

    return results
