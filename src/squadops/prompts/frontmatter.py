"""The YAML frontmatter block: the one parser for the ``---`` header (#579).

Governed prompt assets (fragments and request templates) and two LLM-authored artifacts
(the wrap-up closeout and handoff, and the readiness assessment) open with::

    ---
    key: value
    ---
    body

Five copies of the split lived on the tree before this module, and they had drifted: two
compiled the pattern with ``re.MULTILINE``, the fragment repository loaded an empty header as
``None`` and crashed where the renderer and asset adapter used ``{}``, and the two handler
copies were strict with messages of their own. Byte identity with the stored assets is pinned
by ``tests/unit/prompts/test_frontmatter_characterization.py``, captured from those copies.

**Two readings, because the two kinds of content want different failures.**

- ``read_frontmatter`` is lenient, for assets the framework ships. No block, invalid YAML and
  an empty header all read as no header, which is what every asset reader already did for the
  first two. A header that parses to something other than a mapping still fails loudly: it
  crashed every lenient copy with an ``AttributeError``, and now raises ``FrontmatterError``.
- ``parse_frontmatter`` is strict, for content a model authored, where a missing or malformed
  header is the defect the caller must report.

``re.MULTILINE`` is not carried over, and dropping it changes nothing: every copy called
``.match``, which anchors at position 0, and the pattern has no ``$`` and only a leading ``^``.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

#: ``FrontmatterError.kind`` values.
MISSING = "missing"
INVALID_YAML = "invalid_yaml"
NOT_MAPPING = "not_mapping"


class FrontmatterError(ValueError):
    """A frontmatter block that is absent, unparseable, or not a mapping.

    ``str(error)`` is the message the wrap-up handlers have always reported; a caller with its
    own wording composes it from ``kind``.
    """

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def split_frontmatter(content: str) -> tuple[str | None, str]:
    """The raw header text and the body after the block, or ``(None, content)`` without one.

    The body is not stripped; callers that hash or render it decide that.
    """
    match = FRONTMATTER_PATTERN.match(content)
    if match is None:
        return None, content
    return match.group(1), content[match.end() :]


def read_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """The header as a mapping and the body, leniently: for assets the framework ships.

    No block, invalid YAML, or an empty or otherwise falsy header read as ``{}``.

    Raises:
        FrontmatterError: the header parsed to a non-empty value that is not a mapping.
    """
    header, body = split_frontmatter(content)
    if header is None:
        return {}, body
    try:
        loaded = yaml.safe_load(header)
    except yaml.YAMLError:
        return {}, body
    if not loaded:
        return {}, body
    if not isinstance(loaded, dict):
        raise FrontmatterError(NOT_MAPPING, "YAML frontmatter is not a mapping")
    return loaded, body


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """The header as a mapping and the body, strictly: for content a model authored.

    Raises:
        FrontmatterError: no block (``MISSING``), unparseable YAML (``INVALID_YAML``, the
            parser's message appended), or a header that is not a mapping, an empty one
            included (``NOT_MAPPING``).
    """
    header, body = split_frontmatter(content)
    if header is None:
        raise FrontmatterError(MISSING, "missing YAML frontmatter (expected --- delimiters)")
    try:
        loaded = yaml.safe_load(header)
    except yaml.YAMLError as exc:
        raise FrontmatterError(INVALID_YAML, f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(loaded, dict):
        raise FrontmatterError(NOT_MAPPING, "YAML frontmatter is not a mapping")
    return loaded, body
