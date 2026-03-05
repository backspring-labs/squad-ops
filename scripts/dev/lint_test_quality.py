#!/usr/bin/env python3
"""AST-based test quality linter.

Parses a Python test file and flags anti-patterns defined in docs/TEST_QUALITY_STANDARD.md.
Exits 0 if clean, exits 1 with diagnostics on stderr if violations found.

Usage:
    python scripts/dev/lint_test_quality.py tests/unit/foo/test_bar.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _is_test_function(node: ast.AST) -> bool:
    """Return True if node is a test function or method (def test_*)."""
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
        "test_"
    )


def _is_constant(node: ast.AST) -> bool:
    """Return True if node is a literal constant (str, int, float, bool, None, bytes)."""
    return isinstance(node, ast.Constant)


def _is_attr_eq_constant(node: ast.Assert) -> bool:
    """Return True if assert is `assert obj.attr == constant`."""
    test = node.test
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], (ast.Eq, ast.Is)):
        return False
    if len(test.comparators) != 1:
        return False
    # Left side must be an attribute access
    if not isinstance(test.left, ast.Attribute):
        return False
    # Right side must be a constant
    return _is_constant(test.comparators[0])


def _has_nontrivial_call(body: list[ast.stmt]) -> bool:
    """Return True if the function body exercises behavior beyond construction and assertions.

    Nontrivial means: method calls (obj.method()), awaits, or non-constructor function calls.
    Plain constructors (ClassName(...)) in assignments are just setup, not behavior.
    """
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Await):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            # Method calls (obj.method()) always count — they exercise behavior
            if isinstance(func, ast.Attribute):
                return True
            # Skip builtins that are passive checks
            if isinstance(func, ast.Name) and func.id in ("isinstance", "type", "len", "str"):
                continue
            # Skip constructor-like calls: CapitalizedName(...)
            # These are just setting up the test subject
            if isinstance(func, ast.Name) and func.id[:1].isupper():
                continue
            # Other function calls (lowercase names like process(), transform()) count
            if isinstance(func, ast.Name):
                return True
    return False


def _collect_asserts(body: list[ast.stmt]) -> list[ast.Assert]:
    """Collect all assert statements in a function body (including nested)."""
    asserts = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Assert):
            asserts.append(node)
    return asserts


_MOCK_ASSERT_METHODS = frozenset({
    "assert_called",
    "assert_called_once",
    "assert_called_with",
    "assert_called_once_with",
    "assert_any_call",
    "assert_has_calls",
    "assert_not_called",
    "assert_awaited",
    "assert_awaited_once",
    "assert_awaited_with",
    "assert_awaited_once_with",
    "assert_any_await",
    "assert_has_awaits",
    "assert_not_awaited",
})


def _has_mock_assertions(body: list[ast.stmt]) -> bool:
    """Return True if the function body calls mock assertion methods."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _MOCK_ASSERT_METHODS:
                return True
    return False


def _has_pytest_raises(body: list[ast.stmt]) -> bool:
    """Return True if the function body uses pytest.raises as a context manager."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.With) or isinstance(node, ast.AsyncWith):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call):
                    func = ctx.func
                    # pytest.raises(...)
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr == "raises"
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "pytest"
                    ):
                        return True
    return False


def _is_sole_is_not_none(asserts: list[ast.Assert]) -> bool:
    """Return True if there is exactly 1 assert and it is `assert X is not None`."""
    if len(asserts) != 1:
        return False
    test = asserts[0].test
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    op = test.ops[0]
    comp = test.comparators[0]
    return isinstance(op, ast.IsNot) and isinstance(comp, ast.Constant) and comp.value is None


def _is_sole_isinstance(asserts: list[ast.Assert]) -> bool:
    """Return True if there is exactly 1 assert and it is `assert isinstance(X, Y)`."""
    if len(asserts) != 1:
        return False
    test = asserts[0].test
    if not isinstance(test, ast.Call):
        return False
    func = test.func
    return isinstance(func, ast.Name) and func.id == "isinstance"


def lint_file(filepath: str) -> list[str]:
    """Lint a test file and return a list of diagnostic messages."""
    source = Path(filepath).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return [f"{filepath}:{e.lineno}: syntax error: {e.msg}"]

    diagnostics: list[str] = []

    for node in ast.walk(tree):
        if not _is_test_function(node):
            continue

        body = node.body
        asserts = _collect_asserts(body)
        has_raises = _has_pytest_raises(body)

        has_mock_asserts = _has_mock_assertions(body)
        has_calls = _has_nontrivial_call(body)

        # Anti-pattern 4: No assertions and no pytest.raises and no mock assertions
        # Skip if there are nontrivial calls — they may be implicit "does not raise" tests
        if not asserts and not has_raises and not has_mock_asserts and not has_calls:
            diagnostics.append(
                f"{filepath}:{node.lineno}: {node.name}: "
                f"no assertions — test has no assert statements or pytest.raises"
            )
            continue

        if not asserts:
            # Has pytest.raises or mock assertions but no plain asserts — that's fine
            continue

        # Anti-pattern 1: Attribute-only test
        if (
            len(asserts) >= 1
            and all(_is_attr_eq_constant(a) for a in asserts)
            and not _has_nontrivial_call(body)
        ):
            diagnostics.append(
                f"{filepath}:{node.lineno}: {node.name}: "
                f"attribute-only test — all assertions check class attributes "
                f"without exercising behavior"
            )
            continue

        # Anti-pattern 2: Sole `is not None` assertion
        if _is_sole_is_not_none(asserts) and not has_raises:
            diagnostics.append(
                f"{filepath}:{node.lineno}: {node.name}: "
                f"sole 'is not None' assertion — assert on exact expected values instead"
            )
            continue

        # Anti-pattern 3: Sole `isinstance` assertion
        if _is_sole_isinstance(asserts) and not has_raises:
            diagnostics.append(
                f"{filepath}:{node.lineno}: {node.name}: "
                f"sole 'isinstance' assertion — assert on exact expected values instead"
            )
            continue

    return diagnostics


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <test_file.py>", file=sys.stderr)
        return 2

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        return 2

    diagnostics = lint_file(filepath)
    if diagnostics:
        for d in diagnostics:
            print(d, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
