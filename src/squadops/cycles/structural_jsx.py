"""Structural addressing for JavaScript and JSX — the React frontend's resolver (SIP-0107 §10, §38 step 5).

The second half of step 5's first stack, beside the Python resolver. Same contract: **parser for
addressing, raw text for preservation** — tree-sitter locates an entity, the framework splices
into the original bytes, the tree is never re-serialized — and fail-closed on an unparseable
base, an absent selector or an ambiguous one.

**Why tree-sitter** (the owner's choice, 2026-09-14). The React views use syntax a pure-Python
parser does not read (``runs?.length ?? 0``); tree-sitter's JavaScript grammar reads modern
JavaScript and JSX, reports parse errors instead of raising, and ships wheels for the images'
aarch64 and CI's x86_64. It parses error-tolerantly, so every reading here checks for an error
node first: a tree with one is refused, never addressed. TypeScript (``.ts``/``.tsx``, the
Next.js stack) needs its own grammar and is step 6's.

**Entities and their selectors** (whole lines, like Python's):

====================================  ==================================================
 ``function:NAME``                     a top-level function declaration, ``export`` included
 ``function:NAME#body``                its body's lines, between the braces
 ``const:NAME``                        a top-level ``const``/``let`` declaration of ``NAME``
 ``const:NAME#body``                   an arrow or function expression's body lines
 ``class:NAME``                        a top-level class declaration
 ``import:SOURCE``                     the one import statement from ``SOURCE``
 ``imports``                           the module's leading import section
====================================  ==================================================

An entity is addressable only when it owns its lines: nothing but whitespace shares its first
line before it or its last line after it. A body is addressable only when its ``{`` ends a line,
its ``}`` starts one, and at least one line lies between.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

#: The file suffixes this grammar reads.
JAVASCRIPT_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")
SELECTOR_IMPORTS = "imports"
BODY_SUFFIX = "#body"


@dataclass(frozen=True)
class JsxEntity:
    selector: str
    start: int
    end: int


@lru_cache(maxsize=1)
def _parser() -> Any:
    """The JavaScript parser, built once. Imported here, not at module import: only the agent
    image installs tree-sitter, and a module that imported it eagerly would break any importer
    that never parses JSX."""
    import tree_sitter_javascript
    from tree_sitter import Language, Parser

    return Parser(Language(tree_sitter_javascript.language()))


def _first_error(node: Any) -> Any | None:
    if node.type == "ERROR" or node.is_missing:
        return node
    if not node.has_error:
        return None
    for child in node.children:
        if (found := _first_error(child)) is not None:
            return found
    return node


def jsx_syntax_error(path: str, content: str) -> str | None:
    """``None`` when ``content`` parses as JavaScript/JSX, else where it does not (§18).

    A path this grammar does not read has no validator here and answers ``None``."""
    if not path.endswith(JAVASCRIPT_SUFFIXES):
        return None
    tree = _parser().parse(content.encode("utf-8"))
    error = _first_error(tree.root_node)
    if error is None:
        return None
    return f"line {error.start_point.row + 1}: {'missing' if error.is_missing else 'unexpected'} {error.type}"


class _Lines:
    """Row → character offsets, and whether a node owns the rows it spans."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.rows = content.split("\n")
        self.starts = [0]
        for row in self.rows[:-1]:
            self.starts.append(self.starts[-1] + len(row) + 1)
        self.encoded = [row.encode("utf-8") for row in self.rows]

    def span(self, first_row: int, last_row: int) -> tuple[int, int]:
        start = self.starts[first_row]
        end = self.starts[last_row + 1] if last_row + 1 < len(self.starts) else len(self.content)
        return start, end

    def owns(self, node: Any) -> bool:
        (row0, col0), (row1, col1) = node.start_point, node.end_point
        return not self.encoded[row0][:col0].strip() and not self.encoded[row1][col1:].strip()

    def body_rows(self, block: Any) -> tuple[int, int] | None:
        """The rows strictly inside a ``{ … }`` block, when its braces own their lines."""
        (row0, col0), (row1, col1) = block.start_point, block.end_point
        if row1 - row0 < 2:
            return None
        if self.encoded[row0][col0 + 1 :].strip() or self.encoded[row1][: col1 - 1].strip():
            return None
        return row0 + 1, row1 - 1


def _declaration(node: Any) -> Any:
    """The declaration an ``export`` statement wraps, or the node itself."""
    if node.type == "export_statement":
        inner = node.child_by_field_name("declaration")
        if inner is not None:
            return inner
    return node


def _named_entities(statement: Any, declaration: Any, lines: _Lines) -> list[JsxEntity]:
    kind = declaration.type
    entities: list[JsxEntity] = []
    if kind in ("function_declaration", "generator_function_declaration", "class_declaration"):
        name = declaration.child_by_field_name("name")
        if name is None:
            return []
        prefix = "class" if kind == "class_declaration" else "function"
        selector = f"{prefix}:{name.text.decode()}"
        entities.append(
            JsxEntity(selector, *lines.span(statement.start_point.row, statement.end_point.row))
        )
        body = declaration.child_by_field_name("body")
        if prefix == "function" and body is not None and (rows := lines.body_rows(body)):
            entities.append(JsxEntity(f"{selector}{BODY_SUFFIX}", *lines.span(*rows)))
    elif kind in ("lexical_declaration", "variable_declaration"):
        declarators = [c for c in declaration.children if c.type == "variable_declarator"]
        if len(declarators) != 1:
            return []
        name = declarators[0].child_by_field_name("name")
        if name is None or name.type != "identifier":
            return []
        selector = f"const:{name.text.decode()}"
        entities.append(
            JsxEntity(selector, *lines.span(statement.start_point.row, statement.end_point.row))
        )
        value = declarators[0].child_by_field_name("value")
        body = value.child_by_field_name("body") if value is not None else None
        if body is not None and body.type == "statement_block" and (rows := lines.body_rows(body)):
            entities.append(JsxEntity(f"{selector}{BODY_SUFFIX}", *lines.span(*rows)))
    return entities


def jsx_entities(content: str) -> tuple[JsxEntity, ...] | None:
    """Every addressable entity in ``content``, or ``None`` when it does not parse cleanly."""
    tree = _parser().parse(content.encode("utf-8"))
    root = tree.root_node
    if _first_error(root) is not None:
        return None
    lines = _Lines(content)
    entities: list[JsxEntity] = []
    statements = [c for c in root.children if c.type != "comment"]
    leading = []
    for statement in statements:
        if statement.type != "import_statement":
            break
        leading.append(statement)
    if leading and all(lines.owns(s) for s in leading):
        entities.append(
            JsxEntity(
                SELECTOR_IMPORTS,
                *lines.span(leading[0].start_point.row, leading[-1].end_point.row),
            )
        )
    for statement in statements:
        if not lines.owns(statement):
            continue
        if statement.type == "import_statement":
            source = statement.child_by_field_name("source")
            if source is not None:
                text = source.text.decode().strip("'\"`")
                entities.append(
                    JsxEntity(
                        f"import:{text}",
                        *lines.span(statement.start_point.row, statement.end_point.row),
                    )
                )
            continue
        entities.extend(_named_entities(statement, _declaration(statement), lines))
    return tuple(entities)


def resolve_jsx_entity(path: str, content: str, selector: str) -> list[tuple[int, int]] | None:
    """Every span ``selector`` names in ``content`` — ``None`` when this grammar does not read
    ``path`` or the content does not parse cleanly. The transaction decides what zero or several
    spans mean (a redeclaration is refused as ambiguous, never picked)."""
    if not path.endswith(JAVASCRIPT_SUFFIXES):
        return None
    entities = jsx_entities(content)
    if entities is None:
        return None
    return [(e.start, e.end) for e in entities if e.selector == selector]
