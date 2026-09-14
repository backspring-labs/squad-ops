"""Structural addressing for JavaScript, JSX, TypeScript and TSX (SIP-0107 §10, §38 steps 5–6).

The React frontend's resolver (step 5) and the Next.js stack's (step 6), beside the Python one. Same contract: **parser for
addressing, raw text for preservation** — tree-sitter locates an entity, the framework splices
into the original bytes, the tree is never re-serialized — and fail-closed on an unparseable
base, an absent selector or an ambiguous one.

**Why tree-sitter** (the owner's choice, 2026-09-14). The React views use syntax a pure-Python
parser does not read (``runs?.length ?? 0``); tree-sitter's JavaScript grammar reads modern
JavaScript and JSX, reports parse errors instead of raising, and ships wheels for the images'
aarch64 and CI's x86_64. It parses error-tolerantly, so every reading here checks for an error
node first: a tree with one is refused, never addressed. TypeScript reads through
``tree-sitter-typescript``'s two grammars — ``.ts`` through TypeScript's, ``.tsx`` through
TSX's — with the same node shapes, so one reading serves all three.

**Entities and their selectors** (whole lines, like Python's):

====================================  ==================================================
 ``function:NAME``                     a top-level function declaration, ``export`` included
 ``function:NAME#body``                its body's lines, between the braces
 ``const:NAME``                        a top-level ``const``/``let`` declaration of ``NAME``
 ``const:NAME#body``                   an arrow or function expression's body lines
 ``function:NAME#try``                 the lines inside its ``try`` block, when the body is one
                                       ``try`` statement (a Next.js route handler's fill)
 ``const:NAME#try``                    the same, for an arrow or function expression
 ``class:NAME``                        a top-level class declaration
 ``interface:NAME`` / ``type:NAME``    a TypeScript interface or type alias
 ``enum:NAME``                         a TypeScript enum
 ``import:SOURCE``                     the one import statement from ``SOURCE``
 ``imports``                           the module's leading import section
====================================  ==================================================

**Why ``#try``** (§39.7): the Next.js route slots are narrower than their functions — the scaffold
owns each handler's signature and its ``catch`` envelope, and the fill is the ``try`` block. A
revision of ``#try`` leaves both byte-identical by construction, where a ``#body`` revision would
have to reproduce the envelope.

An entity is addressable only when it owns its lines: nothing but whitespace shares its first
line before it or its last line after it. A body is addressable only when its ``{`` ends a line,
its ``}`` starts one, and at least one line lies between.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Any

#: The file suffixes each grammar reads.
JAVASCRIPT_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs")
TYPESCRIPT_SUFFIXES = (".ts",)
TSX_SUFFIXES = (".tsx",)
ECMASCRIPT_SUFFIXES = JAVASCRIPT_SUFFIXES + TYPESCRIPT_SUFFIXES + TSX_SUFFIXES
SELECTOR_IMPORTS = "imports"
BODY_SUFFIX = "#body"
TRY_SUFFIX = "#try"

_GRAMMAR_JAVASCRIPT = "javascript"
_GRAMMAR_TYPESCRIPT = "typescript"
_GRAMMAR_TSX = "tsx"
_TS_NAMED_DECLARATIONS = {
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "enum_declaration": "enum",
}


@dataclass(frozen=True)
class JsxEntity:
    selector: str
    start: int
    end: int


def _grammar_for(path: str) -> str | None:
    if path.endswith(JAVASCRIPT_SUFFIXES):
        return _GRAMMAR_JAVASCRIPT
    if path.endswith(TSX_SUFFIXES):
        return _GRAMMAR_TSX
    if path.endswith(TYPESCRIPT_SUFFIXES):
        return _GRAMMAR_TYPESCRIPT
    return None


@cache
def _parser(grammar: str) -> Any:
    """One parser per grammar, built once. Imported here, not at module import: only the agent
    image installs tree-sitter, and a module that imported it eagerly would break any importer
    that never parses these files."""
    from tree_sitter import Language, Parser

    if grammar == _GRAMMAR_JAVASCRIPT:
        import tree_sitter_javascript

        return Parser(Language(tree_sitter_javascript.language()))
    import tree_sitter_typescript

    language = (
        tree_sitter_typescript.language_tsx()
        if grammar == _GRAMMAR_TSX
        else tree_sitter_typescript.language_typescript()
    )
    return Parser(Language(language))


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
    """``None`` when ``content`` parses under the path's grammar, else where it does not (§18).

    A path no grammar here reads has no validator and answers ``None``."""
    grammar = _grammar_for(path)
    if grammar is None:
        return None
    tree = _parser(grammar).parse(content.encode("utf-8"))
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


def _is_directive(node: Any) -> bool:
    return (
        node.type == "expression_statement"
        and node.named_child_count == 1
        and node.named_children[0].type == "string"
    )


def _declaration(node: Any) -> Any:
    """The declaration an ``export`` statement wraps, or the node itself."""
    if node.type == "export_statement":
        inner = node.child_by_field_name("declaration")
        if inner is not None:
            return inner
    return node


def _block_entities(selector: str, body: Any, lines: _Lines) -> list[JsxEntity]:
    """``#body`` for a block body on its own lines, and ``#try`` when that body is exactly one
    ``try`` statement whose block sits on its own lines."""
    if body is None or body.type != "statement_block":
        return []
    entities: list[JsxEntity] = []
    if rows := lines.body_rows(body):
        entities.append(JsxEntity(f"{selector}{BODY_SUFFIX}", *lines.span(*rows)))
    statements = [c for c in body.named_children if c.type != "comment"]
    if len(statements) == 1 and statements[0].type == "try_statement":
        block = statements[0].child_by_field_name("body")
        if block is not None and (rows := lines.body_rows(block)):
            entities.append(JsxEntity(f"{selector}{TRY_SUFFIX}", *lines.span(*rows)))
    return entities


def _named_entities(statement: Any, declaration: Any, lines: _Lines) -> list[JsxEntity]:
    kind = declaration.type
    entities: list[JsxEntity] = []
    statement_span = lines.span(statement.start_point.row, statement.end_point.row)
    if kind in _TS_NAMED_DECLARATIONS:
        name = declaration.child_by_field_name("name")
        if name is not None:
            entities.append(
                JsxEntity(f"{_TS_NAMED_DECLARATIONS[kind]}:{name.text.decode()}", *statement_span)
            )
        return entities
    if kind in (
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "abstract_class_declaration",
    ):
        name = declaration.child_by_field_name("name")
        if name is None:
            return []
        prefix = "class" if kind.endswith("class_declaration") else "function"
        selector = f"{prefix}:{name.text.decode()}"
        entities.append(JsxEntity(selector, *statement_span))
        if prefix == "function":
            entities.extend(
                _block_entities(selector, declaration.child_by_field_name("body"), lines)
            )
    elif kind in ("lexical_declaration", "variable_declaration"):
        declarators = [c for c in declaration.children if c.type == "variable_declarator"]
        if len(declarators) != 1:
            return []
        name = declarators[0].child_by_field_name("name")
        if name is None or name.type != "identifier":
            return []
        selector = f"const:{name.text.decode()}"
        entities.append(JsxEntity(selector, *statement_span))
        value = declarators[0].child_by_field_name("value")
        body = value.child_by_field_name("body") if value is not None else None
        entities.extend(_block_entities(selector, body, lines))
    return entities


def jsx_entities(content: str, path: str = "module.jsx") -> tuple[JsxEntity, ...] | None:
    """Every addressable entity in ``content`` under ``path``'s grammar, or ``None`` when no
    grammar reads the path or the content does not parse cleanly."""
    grammar = _grammar_for(path)
    if grammar is None:
        return None
    tree = _parser(grammar).parse(content.encode("utf-8"))
    root = tree.root_node
    if _first_error(root) is not None:
        return None
    lines = _Lines(content)
    entities: list[JsxEntity] = []
    statements = [c for c in root.children if c.type != "comment"]
    leading = []
    # A directive prologue ('use client', 'use strict') precedes the imports the way a Python
    # module docstring does; the import section starts after it.
    prologue = 0
    while prologue < len(statements) and _is_directive(statements[prologue]):
        prologue += 1
    for statement in statements[prologue:]:
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
    entities = jsx_entities(content, path)
    if entities is None:
        return None
    return [(e.start, e.end) for e in entities if e.selector == selector]
