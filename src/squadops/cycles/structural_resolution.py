"""Which structural resolver reads an artifact — one dispatch for the transaction and the prompt.

SIP-0107 §43.2: the resolver is replaceable, the fail-closed contract is not. Each resolver owns
one language (``structural_python`` for ``.py``, ``structural_jsx`` for JavaScript and JSX); this
module routes by file suffix, so the transaction, the repair prompt's entity listing and the
syntax check all ask the same resolver about the same file. A file no resolver reads has no
structural reading: its entity lookups answer ``None`` (refused as ``unreadable_structure``),
its listing is ``None``, and it has no syntax validator here.
"""

from __future__ import annotations

from squadops.cycles.structural_jsx import (
    JAVASCRIPT_SUFFIXES,
    jsx_entities,
    jsx_syntax_error,
    resolve_jsx_entity,
)
from squadops.cycles.structural_python import (
    python_entities,
    python_syntax_error,
    resolve_python_entity,
)

PYTHON_SUFFIXES = (".py",)


def reads_structure(path: str) -> bool:
    return path.endswith(PYTHON_SUFFIXES) or path.endswith(JAVASCRIPT_SUFFIXES)


def resolve_entity(path: str, content: str, selector: str) -> list[tuple[int, int]] | None:
    """Every span ``selector`` names in ``content`` under the file's resolver, or ``None``."""
    if path.endswith(PYTHON_SUFFIXES):
        return resolve_python_entity(path, content, selector)
    if path.endswith(JAVASCRIPT_SUFFIXES):
        return resolve_jsx_entity(path, content, selector)
    return None


def syntax_error(path: str, content: str) -> str | None:
    """Why ``content`` does not parse under the file's grammar, or ``None`` (§18)."""
    if path.endswith(PYTHON_SUFFIXES):
        return python_syntax_error(path, content)
    if path.endswith(JAVASCRIPT_SUFFIXES):
        return jsx_syntax_error(path, content)
    return None


def entity_selectors(path: str, content: str) -> tuple[str, ...] | None:
    """The selectors a repair may target in ``content``, in source order — ``None`` when no
    resolver reads the file or it does not parse."""
    if path.endswith(PYTHON_SUFFIXES):
        entities = python_entities(content)
    elif path.endswith(JAVASCRIPT_SUFFIXES):
        entities = jsx_entities(content)
    else:
        return None
    if entities is None:
        return None
    ordered = sorted(entities, key=lambda e: (e.start, -e.end))
    return tuple(dict.fromkeys(e.selector for e in ordered))
