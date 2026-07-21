"""Fenced code block parser for build handler output.

Extracts tagged fenced code blocks from LLM responses into structured
file records. Used by DevelopmentDevelopHandler, BuilderAssembleHandler,
and QATestHandler to parse multi-file output.

Recognized formats, in priority order (most explicit first):

1. Strict tagged fence — ``` ``` <language>:<filepath>``` ```. A redundant
   ``path:``/``file:`` label wedged before the path (#431 —
   ``` ```python:path:backend/main.py``` ```) is stripped; the residual colon
   would otherwise fail the safety check and drop the whole file.
2. Filename in language slot for special names — ``` ``` Dockerfile``` ```,
   ``` ``` Makefile``` ```, etc.
3. Filename heading immediately preceding the fence — ``#`` through ``######``
   ending in a path-like token (``models.py``, ``backend/main.py``,
   ``Dockerfile``).
4. First-line filename comment inside the fence — ``# path/to/file.py`` or
   ``// path/to/file.py`` as the first line of the body. The comment line
   is stripped from the extracted content.
5. First-line path *prefix* inside the fence (#470) — a bare ``` ```<lang>``` ```
   fence whose first body line is ``path/to/file.py:<code>`` (the path as a
   colon-prefix of the first code line, not a comment). The ``path:`` prefix is
   stripped and the code after the colon becomes the first content line. Because
   this variant carries no comment/heading marker, the path is accepted only when
   it contains ``/`` or ends in a known source extension — a guard prose like
   ``note:todo`` can't trip.
6. Bare filename alone on the first body line (#502) — the whole first line is
   the path, nothing else: ``` ```jsx``` ``` then ``frontend/src/api.js`` on its
   own line, then code. Same acceptance guard as #470 (contains ``/``, known
   source extension, or special name). A lone path line is not valid code in any
   emitted language, so stripping it never eats real content.

Models naturally drift between these formats; the parser tolerates all of
them so a one-character format slip doesn't drop the whole task on the floor.
The strict format is still the recommended one and round-trips losslessly.

Nested fences (#430): a block's body may itself contain fenced examples —
any markdown deliverable with an embedded ``` ```bash``` ``` snippet, or a
docstring quoting fenced code. A ``` ```<token>``` ``` line inside a block
opens a nested level and a bare ``` ``` ``` ``` closes the innermost one; the
block ends only when the depth returns to zero. Trade-off: a body containing
an *unmatched* tokened opener leaves the block unclosed and it is abandoned
whole — rarer and louder than the silent mid-document clip it replaces.

Implicit close at EOF (#431): a model sometimes drops only the closing
``` ``` ``` ```, leaving a valid header and a complete body that runs to the end
of the response. When the text after an unclosed opener contains *no further
fence markers at all*, the body unambiguously ends at EOF and that is taken as
the close — recovering a file that would otherwise be lost. The no-inner-fence
guard is deliberate: if any fence remains, a close may merely be missing
*between* two files, and abandoning the opener is safer than swallowing the next
file's content into this one.

Part of SIP-Enhanced-Agent-Build-Capabilities, Phase 1.
"""

from __future__ import annotations

import re

from squadops.capabilities.handlers.impl._json_extraction import _strip_think_blocks

# Strict format header: ```<lang>:<path>
_STRICT_HEADER_RE = re.compile(r"^```(\w+):(\S+)\s*$", re.MULTILINE)

# Any fence line: ```<token> where <token> may be empty. Models sometimes
# emit a bare ``` immediately after a filename heading (``## Dockerfile``
# then ``` ```\n...```\n`` `), so we cannot require a non-empty language
# slot. The open/close ambiguity of a bare ``` is resolved by depth
# tracking in _find_block_close: a tokened fence opens a nested level, a
# bare fence closes the innermost one.
_OPEN_FENCE_RE = re.compile(r"^```(\S*)\s*$", re.MULTILINE)

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

# First line of fence body as a bare ``path:code`` prefix (#470). No comment
# marker, so the path is disambiguated from prose by the extension guard below.
_FILENAME_PREFIX_RE = re.compile(
    rf"^(?P<path>[\w./-]+\.[a-zA-Z0-9]+|{_SPECIAL_NAMES_RE}):(?P<rest>.*)$",
)

# Redundant path label a model sometimes wedges into a strict header (#431):
# ``` ```python:path:backend/main.py``` ```. Strategy 1 partitions on the first
# colon and is left with ``path:backend/main.py`` as the filename — the residual
# colon then trips ``_path_is_safe`` and the whole file is dropped. A real path
# can never contain a colon, so a leading ``path:``/``file:`` label is always
# spurious and safe to strip.
_PATH_LABEL_RE = re.compile(r"^(?:path|file|filename|filepath)\s*:\s*", re.IGNORECASE)

# Source/deliverable extensions the build handlers emit — the guard that lets an
# unmarked ``path:code`` first line (#470) be read as a filename without
# mis-reading prose or config values (``example.com:8080``, ``note.txt:`` are
# fine only when path-shaped). A path containing ``/`` is accepted regardless.
_SOURCE_EXTENSIONS = frozenset(
    {
        "py",
        "js",
        "jsx",
        "ts",
        "tsx",
        "mjs",
        "cjs",
        "vue",
        "json",
        "yaml",
        "yml",
        "toml",
        "ini",
        "cfg",
        "env",
        "md",
        "rst",
        "txt",
        "html",
        "htm",
        "css",
        "scss",
        "sh",
        "bash",
        "sql",
        "xml",
        "svg",
    }
)

# Filenames that LLMs often emit as the language slot (``` ```Dockerfile``` ```).
_SPECIAL_FILENAMES_AS_LANG = set(_SPECIAL_NAMES)


def _has_source_extension(path: str) -> bool:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext in _SOURCE_EXTENSIONS


def _strip_path_label(filename: str) -> str:
    """#431: drop a redundant ``path:``/``file:`` label from a strict-header
    filename (``python:path:backend/main.py`` → ``backend/main.py``).

    Strictly additive: a well-formed strict filename never starts with one of
    these label words followed by a colon, so conforming headers are untouched;
    only the malformed ones — which ``_path_is_safe`` rejects today — are healed.
    """
    return _PATH_LABEL_RE.sub("", filename, count=1)


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


def _find_block_close(response: str, body_start: int) -> re.Match[str] | None:
    """Find the close fence for a block whose body starts at ``body_start``,
    honoring nesting (#430): a ``` ```<token>``` ``` line inside the body opens
    a nested level, a bare ``` ``` ``` ``` closes the innermost one, and the
    block closes when depth returns to zero. Returns the close-fence match, or
    ``None`` if the block never closes (e.g. an unmatched nested opener).
    """
    depth = 1
    pos = body_start
    while True:
        fence = _OPEN_FENCE_RE.search(response, pos)
        if fence is None:
            return None
        if fence.group(1):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return fence
        pos = fence.end()


def _is_implicit_eof_close(response: str, body_start: int) -> bool:
    """#431: True when the text from ``body_start`` to EOF is a *clean* single
    unterminated block — it contains no further fence markers at all.

    A model sometimes drops only the closing ``` ``` ```, leaving a valid header
    and a complete body that runs to EOF (real cases: two of three sampled
    extraction losses). When nothing else in the remainder looks like a fence,
    the body unambiguously ends at EOF and the close can be inferred. But if the
    remainder *does* carry a fence, boundaries are ambiguous — a close fence may
    merely be missing *between* two files — so we decline and let the block be
    abandoned rather than risk swallowing the next file's content.
    """
    return _OPEN_FENCE_RE.search(response, body_start) is None


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


def _resolve_filename_from_first_line_prefix(body: str) -> tuple[str | None, str]:
    """#470: if the first line of ``body`` is ``path:code`` (a filename as a bare
    colon-prefix of the first code line — no comment marker), return
    ``(filename, body_with_the_prefix_stripped)`` so the code after the colon
    becomes the first content line. Otherwise ``(None, body)``.

    Guarded: the path is accepted only when it contains ``/`` or ends in a known
    source extension (or is a special name), so a prose/config first line like
    ``example.com:8080`` is never mistaken for a filename.
    """
    nl = body.find("\n")
    first_line = body if nl == -1 else body[:nl]
    match = _FILENAME_PREFIX_RE.match(first_line)
    if match is None:
        return None, body
    path = match.group("path")
    if not ("/" in path or _has_source_extension(path) or path in _SPECIAL_FILENAMES_AS_LANG):
        return None, body
    rest = match.group("rest")
    remainder = "" if nl == -1 else body[nl + 1 :]
    if nl == -1:
        new_body = rest
    elif rest == "":
        # ``path:`` alone on the first line — the code starts on the next line,
        # so don't prepend an empty first line.
        new_body = remainder
    else:
        new_body = f"{rest}\n{remainder}"
    return path, new_body


def _resolve_filename_from_first_line_bare(body: str) -> tuple[str | None, str]:
    """#502: if the first line of ``body`` is *exactly* a path-shaped token —
    the bare filename on its own line, no comment marker, no colon — return
    ``(filename, body_with_the_line_stripped)``. Otherwise ``(None, body)``.

    Same guard as #470: accepted only when the token contains ``/``, has a known
    source extension, or is a special name. A lone path line is not valid code in
    any language the build handlers emit, so this never eats real content.
    """
    nl = body.find("\n")
    first_line = (body if nl == -1 else body[:nl]).strip()
    if not first_line or " " in first_line or ":" in first_line:
        return None, body
    if not re.fullmatch(rf"[\w./-]+\.[a-zA-Z0-9]+|{_SPECIAL_NAMES_RE}", first_line):
        return None, body
    if not (
        "/" in first_line
        or _has_source_extension(first_line)
        or first_line in _SPECIAL_FILENAMES_AS_LANG
    ):
        return None, body
    remainder = "" if nl == -1 else body[nl + 1 :]
    return first_line, remainder


def _resolve_block(
    response: str,
    fence_start: int,
    token: str,
    body: str,
    last_used_heading_pos: int,
) -> tuple[str | None, str, str, int]:
    """Resolve ``(filename, language, body, last_used_heading_pos)`` for one
    fenced block by trying the resolution strategies in priority order (see the
    module docstring). ``filename`` is ``None`` when no strategy resolves a path.
    ``body`` is returned possibly trimmed (strategies 4-6 strip their first-line
    marker); ``last_used_heading_pos`` advances when strategy 3 consumes a
    heading so it is not reused by a later fence.
    """
    filename: str | None = None
    language: str = token

    if ":" in token:
        # Strategy 1: strict ```<lang>:<path>
        language, _, filename = token.partition(":")
        filename = _strip_path_label(filename)  # #431: heal ```lang:path:<file>
    elif token in _SPECIAL_FILENAMES_AS_LANG:
        # Strategy 2: ```Dockerfile (filename in language slot)
        filename = token
        language = token.lower()
    else:
        # Strategy 3: filename heading immediately preceding the fence
        heading_filename, last_used_heading_pos = _resolve_filename_from_heading(
            response, fence_start, last_used_heading_pos
        )
        if heading_filename is not None:
            filename = heading_filename
        else:
            # Strategy 4: first-line filename comment inside body
            comment_filename, stripped_body = _resolve_filename_from_first_comment(body)
            if comment_filename is not None:
                filename = comment_filename
                body = stripped_body
            else:
                # Strategy 5 (#470): first-line ``path:code`` prefix inside body
                prefix_filename, prefixed_body = _resolve_filename_from_first_line_prefix(body)
                if prefix_filename is not None:
                    filename = prefix_filename
                    body = prefixed_body
                else:
                    # Strategy 6 (#502): bare filename alone on the first line
                    bare_filename, bare_body = _resolve_filename_from_first_line_bare(body)
                    if bare_filename is not None:
                        filename = bare_filename
                        body = bare_body

    return filename, language, body, last_used_heading_pos


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

    # #130: strip Qwen3-family <think>...</think> reasoning blocks before
    # scanning for fences. Thinking-mode traces can contain stray ``` fences
    # (false matches) or consume the response budget entirely; stripping them
    # first is what PR #128's JSON extractor already does for impl handlers.
    response = _strip_think_blocks(response)

    results: list[dict] = []
    pos = 0
    last_used_heading_pos = -1

    while pos < len(response):
        open_match = _OPEN_FENCE_RE.search(response, pos)
        if not open_match:
            break

        body_start = open_match.end() + 1  # skip newline after header
        close_match = _find_block_close(response, body_start)
        if close_match:
            body = response[body_start : close_match.start()]
            next_pos = close_match.end()
        elif _is_implicit_eof_close(response, body_start):
            # #431: a single unterminated fence whose body runs cleanly to EOF —
            # infer the dropped close rather than losing the whole file.
            body = response[body_start:]
            next_pos = len(response)
        else:
            # No closing fence and inferring one is unsafe — abandon this opener.
            pos = body_start
            continue

        filename, language, body, last_used_heading_pos = _resolve_block(
            response, open_match.start(), open_match.group(1), body, last_used_heading_pos
        )

        if filename is None or not _path_is_safe(filename):
            pos = next_pos
            continue

        results.append(
            {
                "filename": filename,
                "content": _strip_trailing_newline(body),
                "language": language or "text",
            }
        )
        pos = next_pos

    return results
