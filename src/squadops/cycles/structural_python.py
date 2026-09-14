"""Structural addressing for Python source — the first structural resolver (SIP-0107 §10, §38 step 5).

**Parser for addressing; raw text for preservation.** The stdlib ``ast`` locates an entity; the
framework splices the change into the original bytes and never re-serializes the tree, so
comments, formatting, quoting and every unrelated byte stay out of the generative path. The
resolver is replaceable; its fail-closed contract is not (§43.2): an unparseable base, an absent
selector and an ambiguous selector each resolve to nothing, never to a guess.

**Why Python first, and why ``ast``.** The first structural stack is React (§43.6), which
carries a Python backend and a JSX frontend; §43.2 leaves the order to this PR. The backend goes
first: the whole-file repair failures that motivate the SIP were ``backend/routes.py`` rewrites
(1.6.5 rolls 5 and 6, §1.2), and ``ast`` gives exact line and column extents with no dependency.
The JSX resolver follows in its own PR.

**Entities and their selectors.** A selector names an entity within one artifact at one
revision; the transaction binds it to the base (§7, §12). Ranges are whole lines — from the start
of the entity's first line (its first decorator) through the newline ending its last — so a
replacement, insertion or removal composes with the surrounding lines intact.

====================================  ==================================================
 ``function:NAME``                     a module-level function, decorators included
 ``function:NAME#body``                its body statements
 ``class:NAME``                        a module-level class, decorators included
 ``method:CLASS.NAME``                 a method, decorators included
 ``method:CLASS.NAME#body``            its body statements
 ``import:MODULE``                     the one import statement of ``MODULE``
 ``imports``                           the module's leading import section
====================================  ==================================================

A body is addressable only when it starts on its own line; ``def f(): return 1`` has none.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

SELECTOR_IMPORTS = "imports"
BODY_SUFFIX = "#body"


@dataclass(frozen=True)
class PythonEntity:
    selector: str
    start: int
    end: int


def _line_starts(source: str) -> list[int]:
    """Character offset of the start of each 1-based line (index 0 unused), plus the end."""
    starts = [0, 0]
    for index, char in enumerate(source):
        if char == "\n":
            starts.append(index + 1)
    starts.append(len(source))
    return starts


def _lines_span(starts: list[int], first_line: int, last_line: int, source: str) -> tuple[int, int]:
    start = starts[first_line]
    end = starts[last_line + 1] if last_line + 1 < len(starts) - 1 else len(source)
    return start, end


def _first_line(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", None) or []
    return min([node.lineno, *(d.lineno for d in decorators)])


def _body_entity(
    selector: str, node: ast.FunctionDef | ast.AsyncFunctionDef, starts: list[int], source: str
) -> PythonEntity | None:
    first, last = node.body[0], node.body[-1]
    if first.lineno == node.lineno:
        return None
    start, end = _lines_span(starts, first.lineno, last.end_lineno or last.lineno, source)
    return PythonEntity(selector=f"{selector}{BODY_SUFFIX}", start=start, end=end)


def _import_module(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.ImportFrom):
        return "." * node.level + (node.module or "")
    return ",".join(alias.name for alias in node.names)


def _import_section(tree: ast.Module, starts: list[int], source: str) -> PythonEntity | None:
    """The contiguous imports leading the module, after its docstring, as one entity."""
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    leading: list[ast.stmt] = []
    for node in body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            break
        leading.append(node)
    if not leading:
        return None
    start, end = _lines_span(
        starts, leading[0].lineno, leading[-1].end_lineno or leading[-1].lineno, source
    )
    return PythonEntity(selector=SELECTOR_IMPORTS, start=start, end=end)


def _function_entities(
    selector: str, node: ast.FunctionDef | ast.AsyncFunctionDef, starts: list[int], source: str
) -> list[PythonEntity]:
    span = _lines_span(starts, _first_line(node), node.end_lineno or node.lineno, source)
    entities = [PythonEntity(selector, *span)]
    if (body_entity := _body_entity(selector, node, starts, source)) is not None:
        entities.append(body_entity)
    return entities


def python_entities(source: str) -> tuple[PythonEntity, ...] | None:
    """Every addressable entity in ``source``, or ``None`` when it does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    starts = _line_starts(source)
    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    entities: list[PythonEntity] = []
    if (section := _import_section(tree, starts, source)) is not None:
        entities.append(section)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            span = _lines_span(starts, node.lineno, node.end_lineno or node.lineno, source)
            entities.append(PythonEntity(f"import:{_import_module(node)}", *span))
        elif isinstance(node, functions):
            entities.extend(_function_entities(f"function:{node.name}", node, starts, source))
        elif isinstance(node, ast.ClassDef):
            span = _lines_span(starts, _first_line(node), node.end_lineno or node.lineno, source)
            entities.append(PythonEntity(f"class:{node.name}", *span))
            for member in node.body:
                if isinstance(member, functions):
                    entities.extend(
                        _function_entities(
                            f"method:{node.name}.{member.name}", member, starts, source
                        )
                    )
    return tuple(entities)


def resolve_python_entity(_path: str, content: str, selector: str) -> list[tuple[int, int]] | None:
    """Every span ``selector`` names in ``content`` — ``None`` when the content does not parse.

    The transaction decides what zero or several spans mean; the resolver only reports them, so a
    redefined function or a module imported twice is refused as ambiguous, never picked.
    """
    entities = python_entities(content)
    if entities is None:
        return None
    return [(e.start, e.end) for e in entities if e.selector == selector]


def python_syntax_error(_path: str, content: str) -> str | None:
    """``None`` when ``content`` parses, else the parser's message with its line (§18)."""
    try:
        ast.parse(content)
    except SyntaxError as exc:
        return f"line {exc.lineno}: {exc.msg}"
    return None
