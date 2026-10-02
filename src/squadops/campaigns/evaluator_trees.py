"""The trees an increment is evaluated on, test identity, and verifier bundles (SIP-0109 §7.4,
§8.1; #1806).

Pure, and isolated by construction:
- **the baseline-evaluator overlay** is the accepted tree's product code plus the candidate's test
  files and test configuration. It never holds candidate product code, so a new test that passes
  on it passed against the accepted app (§8.2's discrimination check);
- **the candidate-verifier overlay** is the candidate's product code plus one frozen criterion's
  verifier bundle. It never holds the candidate's own test files, so a frozen criterion runs as
  it was frozen (§8.1);
- **a verifier bundle** is a criterion's test file, the helpers and fixtures it imports (resolved
  transitively at freeze time), and the stack's test configuration, plus its invocation. Its
  address is the hash of exactly that, so adding a criterion moves no other bundle;
- **test identity** is a test's file path and name, as the stack's runner names it. Against the
  accepted tree, each candidate test is new, modified (same id, changed body) or renamed (same
  body, new id), and an accepted test the candidate lacks is removed.

Nothing here writes a tree. The accepted tree is a value; an overlay is a new value.
"""

from __future__ import annotations

import ast
import hashlib
import posixpath
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

# =============================================================================
# Trees
# =============================================================================


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class FileTree:
    """An immutable set of files. Its identity is the hash of every path and its content."""

    files: tuple[tuple[str, bytes], ...]

    @classmethod
    def of(cls, files: Mapping[str, bytes | str]) -> FileTree:
        return cls(
            tuple(
                sorted(
                    (path, content.encode("utf-8") if isinstance(content, str) else bytes(content))
                    for path, content in files.items()
                )
            )
        )

    @property
    def identity(self) -> str:
        return _sha(
            b"".join(p.encode("utf-8") + b"\0" + _sha(c).encode() + b"\n" for p, c in self.files)
        )

    def paths(self) -> tuple[str, ...]:
        return tuple(p for p, _ in self.files)

    def get(self, path: str) -> bytes | None:
        return next((c for p, c in self.files if p == path), None)

    def as_dict(self) -> dict[str, bytes]:
        return dict(self.files)


@dataclass(frozen=True)
class TestSurface:
    """Which files are the test runner's: under a qa namespace, or a test-config file."""

    __test__ = False  # not a pytest class

    namespaces: tuple[str, ...]
    config_files: tuple[str, ...]

    @classmethod
    def for_stack(cls, stack: str) -> TestSurface:
        from squadops.capabilities.scaffold import (
            qa_test_namespace_for_stack,
            test_config_files_for_stack,
        )

        return cls(qa_test_namespace_for_stack(stack), test_config_files_for_stack(stack))

    def is_test(self, path: str) -> bool:
        if path in self.config_files:
            return True
        return any(path.startswith(ns) or f"/{ns}" in f"/{path}" for ns in self.namespaces)


@dataclass(frozen=True)
class Overlay:
    tree: FileTree
    identity: str


def baseline_evaluator_overlay(
    accepted: FileTree, candidate: FileTree, surface: TestSurface
) -> Overlay:
    """The accepted tree's product code, plus the candidate's test files and test config (§7.4).

    Never the candidate's product code, by construction: every product path comes from
    ``accepted``. The identity is the accepted identity plus the hash of the overlaid test set.
    """
    product = {p: c for p, c in accepted.files if not surface.is_test(p)}
    tests = {p: c for p, c in candidate.files if surface.is_test(p)}
    test_set = FileTree.of(tests)
    return Overlay(
        FileTree.of({**product, **tests}), _sha(f"{accepted.identity}|{test_set.identity}".encode())
    )


@dataclass(frozen=True)
class VerifierBundle:
    """A frozen criterion's executable form (§8.1). Its address is its content."""

    criterion_id: str
    files: FileTree
    invocation: tuple[str, ...]

    @property
    def address(self) -> str:
        return _sha(
            f"{self.criterion_id}|{self.files.identity}|{chr(31).join(self.invocation)}".encode()
        )


def candidate_verifier_overlay(
    candidate: FileTree, bundle: VerifierBundle, surface: TestSurface
) -> Overlay:
    """The candidate's product code, plus one frozen bundle (§7.4).

    Never the candidate's own test files, by construction: every test path comes from the
    bundle. The identity is the candidate identity plus the bundle's address.
    """
    product = {p: c for p, c in candidate.files if not surface.is_test(p)}
    return Overlay(
        FileTree.of({**product, **bundle.files.as_dict()}),
        _sha(f"{candidate.identity}|{bundle.address}".encode()),
    )


class BundleIncomplete(ValueError):
    """A criterion test, or something it imports from the test surface, is not in the tree."""


def freeze_bundle(
    criterion_id: str,
    tree: FileTree,
    test_path: str,
    surface: TestSurface,
    invocation: Iterable[str],
) -> VerifierBundle:
    """Freeze a criterion's bundle from ``tree`` (§8.1): its test file, every test-surface file it
    imports, transitively, and the stack's test-config files present in the tree.

    Raises:
        BundleIncomplete: If the test file, or a test-surface module it imports, is absent:
            a bundle that cannot run is never frozen (a missing bundle is ``blocked_unverified``).
    """
    files: dict[str, bytes] = {}
    pending = [test_path]
    while pending:
        path = pending.pop()
        if path in files:
            continue
        content = tree.get(path)
        if content is None:
            raise BundleIncomplete(f"{criterion_id}: {path} is not in the tree")
        files[path] = content
        found, unresolved = _imported_paths(path, content.decode("utf-8"), tree)
        if unresolved:
            raise BundleIncomplete(
                f"{criterion_id}: {path} imports {', '.join(unresolved)}, which is not in the tree"
            )
        for imported in found:
            if surface.is_test(imported) and imported not in files:
                pending.append(imported)
    for config in surface.config_files:
        content = tree.get(config)
        if content is not None:
            files[config] = content
    return VerifierBundle(criterion_id, FileTree.of(files), tuple(invocation))


_JS_IMPORT = re.compile(
    r"""(?:import\s[^'"`]*?from\s|import\s|require\()\s*['"`](\.{1,2}/[^'"`]+)['"`]"""
)
_JS_EXTENSIONS = ("", ".js", ".jsx", ".ts", ".tsx", "/index.js", "/index.jsx", "/index.ts")


def _imported_paths(path: str, source: str, tree: FileTree) -> tuple[list[str], list[str]]:
    """The tree paths a test file imports, and the relative references that resolve to none.

    A relative reference names a file of the tree, so one that resolves to nothing is a bundle
    that cannot run. An absolute one may name an installed package, and is not judged here.
    """
    present = set(tree.paths())
    found: list[str] = []
    unresolved: list[str] = []
    if path.endswith(".py"):
        try:
            module = ast.parse(source)
        except SyntaxError:
            return found, unresolved
        for node in ast.walk(module):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                base = node.module.replace(".", "/")
                if node.level:
                    up = posixpath.dirname(path)
                    for _ in range(node.level - 1):
                        up = posixpath.dirname(up)
                    base = posixpath.join(up, base)
                names.append(base)
            elif isinstance(node, ast.Import):
                names.extend(alias.name.replace(".", "/") for alias in node.names)
            relative = isinstance(node, ast.ImportFrom) and bool(node.level)
            for name in names:
                hits = [c for c in (f"{name}.py", f"{name}/__init__.py") if c in present]
                found.extend(hits)
                if relative and not hits:
                    unresolved.append(name)
    else:
        for ref in _JS_IMPORT.findall(source):
            base = posixpath.normpath(posixpath.join(posixpath.dirname(path), ref))
            hit = next((base + ext for ext in _JS_EXTENSIONS if base + ext in present), None)
            if hit is None:
                unresolved.append(ref)
            else:
                found.append(hit)
    return found, unresolved


# =============================================================================
# Test identity
# =============================================================================


@dataclass(frozen=True, order=True)
class TestId:
    """A test as the stack's runner names it: its file and its name (§7.4)."""

    __test__ = False

    path: str
    name: str


class TestChange(StrEnum):
    __test__ = False

    NEW = "new"
    MODIFIED = "modified"
    RENAMED = "renamed"
    UNCHANGED = "unchanged"
    REMOVED = "removed"


def test_inventory(path: str, source: str) -> dict[TestId, str]:
    """Each test in a file, with the hash of its body (its name excluded, so a rename keeps it).

    Python: module-level ``test_*`` functions and ``Test*`` classes' ``test_*`` methods, named
    ``Class::test`` as pytest does. JavaScript and TypeScript: ``describe``/``it``/``test``
    calls, named ``describe > it`` as vitest does.
    """
    if path.endswith(".py"):
        return _python_inventory(path, source)
    return _js_inventory(path, source)


test_inventory.__test__ = False  # type: ignore[attr-defined]


def classify_tests(
    accepted: Mapping[TestId, str], candidate: Mapping[TestId, str]
) -> dict[TestId, TestChange]:
    """Every candidate test against the accepted ones, and every accepted test the candidate
    lacks. A rename is a new id whose body equals the body of an accepted test that is gone."""
    gone_bodies: dict[str, TestId] = {
        body: tid for tid, body in accepted.items() if tid not in candidate
    }
    result: dict[TestId, TestChange] = {}
    renamed_from: set[TestId] = set()
    for tid, body in candidate.items():
        if tid in accepted:
            result[tid] = TestChange.UNCHANGED if accepted[tid] == body else TestChange.MODIFIED
        elif body in gone_bodies:
            result[tid] = TestChange.RENAMED
            renamed_from.add(gone_bodies.pop(body))
        else:
            result[tid] = TestChange.NEW
    for tid in accepted:
        if tid not in candidate and tid not in renamed_from:
            result[tid] = TestChange.REMOVED
    return result


def _python_inventory(path: str, source: str) -> dict[TestId, str]:
    module = ast.parse(source)
    found: dict[TestId, str] = {}

    def body_hash(node: ast.AST) -> str:
        unnamed = ast.Module(body=[*getattr(node, "body", [])], type_ignores=[])
        return _sha(ast.dump(unnamed, include_attributes=False).encode())

    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test"
        ):
            found[TestId(path, node.name)] = body_hash(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(
                    item, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and item.name.startswith("test"):
                    found[TestId(path, f"{node.name}::{item.name}")] = body_hash(item)
    return found


_JS_CALL = re.compile(r"\b(describe|it|test)(?:\.(?:only|skip|concurrent))?\s*\(")


def _js_inventory(path: str, source: str) -> dict[TestId, str]:
    found: dict[TestId, str] = {}
    _scan_js(path, source, 0, len(source), (), found)
    return found


def _scan_js(
    path: str, src: str, start: int, end: int, prefix: tuple[str, ...], found: dict
) -> None:
    i = start
    while i < end:
        i = _skip_trivia(src, i, end)
        m = _JS_CALL.match(src, i) if i < end else None
        if m is None:
            i = _next_token(src, i, end)
            continue
        kind = m.group(1)
        name_start = _skip_ws(src, m.end(), end)
        name, after_name = _string_literal(src, name_start, end)
        close = _matching(src, m.end() - 1, end)
        if name is None or close is None:
            i = m.end()
            continue
        if kind == "describe":
            _scan_js(path, src, after_name, close, (*prefix, name), found)
        else:
            body = re.sub(r"\s+", " ", src[after_name:close]).strip()
            found[TestId(path, " > ".join((*prefix, name)))] = _sha(body.encode())
        i = close + 1


def _skip_ws(src: str, i: int, end: int) -> int:
    while i < end and src[i].isspace():
        i += 1
    return i


def _skip_trivia(src: str, i: int, end: int) -> int:
    while i < end:
        if src[i].isspace():
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = end if j < 0 else j + 1
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = end if j < 0 else j + 2
        else:
            break
    return i


def _next_token(src: str, i: int, end: int) -> int:
    """Advance past one token, stepping over a whole string so a quoted 'it(' is never a call."""
    if i >= end:
        return end
    if src[i] in "'\"`":
        _, after = _string_literal(src, i, end)
        return after if after > i else i + 1
    return i + 1


def _string_literal(src: str, i: int, end: int) -> tuple[str | None, int]:
    if i >= end or src[i] not in "'\"`":
        return None, i
    quote, j, out = src[i], i + 1, []
    while j < end:
        ch = src[j]
        if ch == "\\" and j + 1 < end:
            out.append(src[j + 1])
            j += 2
            continue
        if ch == quote:
            return "".join(out), j + 1
        out.append(ch)
        j += 1
    return None, end


def _matching(src: str, open_index: int, end: int) -> int | None:
    """The index of the paren closing the one at ``open_index``, skipping strings and comments."""
    depth, i = 0, open_index
    while i < end:
        i = _skip_trivia(src, i, end) if src[i] in " \t\n/" else i
        if i >= end:
            break
        ch = src[i]
        if ch in "'\"`":
            _, i = _string_literal(src, i, end)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None
