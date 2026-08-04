"""Typed acceptance check evaluators (SIP-0092 M1.2).

Builds on the M1.1 ``CHECK_SPECS`` registry in ``acceptance_check_spec.py``.
Each spec there declares the contract; this module supplies the runtime
evaluator. The pairing is enforced at module import: any ``CHECK_SPECS``
entry without a matching ``_CHECK_IMPLS`` registration will raise.

Outcomes follow RC-9a: ``error`` is reserved for evaluator failures
(unsafe path, command not in safelist, regex pathological input, etc.) —
not for application gaps. ``skipped`` is reserved for stack-context-unset
or syntax-not-supported cases that authoring-time validation deliberately
allowed through (RC-12 / RC-12a).

This module is import-clean: nothing in the runtime path consumes it yet.
M1.3 wires it into ``_validate_output_focused``.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_check_spec import (
    CHECK_ENDPOINT_DEFINED,
    CHECK_SPECS,
    CHECK_UNDEFINED_NAMES,
    FRONTEND_SUFFIXES,
    HTTP_METHODS,
    CheckSpec,
    argv_matches_safelist,
    normalize_route,
    parse_method_path,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckOutcome:
    """Result of evaluating a single typed check.

    ``status`` ∈ {passed, failed, skipped, error}; see RC-9a / RC-12 for
    the semantic distinction between ``failed`` (app gap) and ``error``
    (evaluator failure) and ``skipped`` (intentionally not run).
    """

    status: str
    actual: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    @classmethod
    def passed(cls, reason: str = "ok", **actual: Any) -> CheckOutcome:
        return cls(status="passed", actual=dict(actual), reason=reason)

    @classmethod
    def failed(cls, reason: str, **actual: Any) -> CheckOutcome:
        return cls(status="failed", actual=dict(actual), reason=reason)

    @classmethod
    def skipped(cls, reason: str, **actual: Any) -> CheckOutcome:
        return cls(status="skipped", actual=dict(actual), reason=reason)

    @classmethod
    def error(cls, reason: str, **actual: Any) -> CheckOutcome:
        return cls(status="error", actual=dict(actual), reason=reason)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


DEFAULT_GLOB_MATCH_CAP = 10_000
DEFAULT_COMMAND_TIMEOUT_S = 10
MAX_COMMAND_TIMEOUT_S = 60
DEFAULT_REGEX_INPUT_CAP_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_REGEX_PATTERN_CAP_CHARS = 4096
# #648: the frontend build is the one check that runs a package manager — its
# ceilings are its own (measured: install ~6s cold / ~0.9s with the agent
# container's warm npm cache; build ~0.9s). The install ceiling absorbs a
# first-ever cold-network install; the command ceilings above stay untouched.
FRONTEND_INSTALL_TIMEOUT_S = 240
FRONTEND_BUILD_TIMEOUT_S = 120


class _SafetyError(Exception):
    """Internal signal — a path/glob/regex/command violated a safety bound.

    Caught at the check boundary and converted to ``CheckOutcome.error``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _safe_resolve(path_str: str, workspace_root: Path) -> Path:
    """Resolve a workspace-relative path, rejecting traversal/absolute/symlink-escape.

    Raises ``_SafetyError("path_escapes_workspace")`` on:
    - absolute path
    - resolved path lying outside ``workspace_root``
    - symlink whose target lies outside ``workspace_root``
    """
    if not isinstance(path_str, str) or not path_str:
        raise _SafetyError("path_escapes_workspace")
    p = Path(path_str)
    if p.is_absolute():
        raise _SafetyError("path_escapes_workspace")

    root_resolved = workspace_root.resolve()
    candidate = (workspace_root / path_str).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise _SafetyError("path_escapes_workspace") from exc

    # Symlink escape: any symlink WITHIN the user-supplied path (at or below
    # workspace_root) whose target lies outside the workspace. Strict ancestors
    # of workspace_root are trusted and skipped — they are frequently symlinked
    # (e.g. /var -> /private/var on macOS, symlinked mount points on Linux) and
    # are not attacker-controlled, so walking into them produces false escapes.
    cur = workspace_root / path_str
    while True:
        if cur.is_symlink():
            target = cur.resolve()
            try:
                target.relative_to(root_resolved)
            except ValueError as exc:
                raise _SafetyError("path_escapes_workspace") from exc
        if cur == workspace_root or cur == cur.parent:
            break
        cur = cur.parent
    return candidate


def _restricted_env() -> dict[str, str]:
    """Build a clean restricted env for subprocess execution.

    Strips LD_PRELOAD, PYTHONPATH, LD_LIBRARY_PATH, and similar injection
    surfaces. Keeps a small allowlist of locale / path basics.
    """
    import os

    keep = {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ"}
    return {k: v for k, v in os.environ.items() if k in keep}


# Bare interpreter names a contract may emit for `command_exit_zero`.
_BARE_INTERPRETERS = frozenset({"python", "python3"})


def _resolve_interpreter(argv: list[str]) -> list[str]:
    """Substitute the running interpreter for a bare python name in ``argv[0]``.

    #498: ``command_exit_zero`` argv is authored (or scaffold-emitted) as a
    *name*, and resolving that name through the inherited ``PATH`` at spawn made
    the outcome depend on an environment detail. Ubuntu ships only
    ``/usr/bin/python3`` — there is no ``python`` — so ``python -m py_compile``
    raised ``FileNotFoundError`` and the check degraded to
    ``skipped(missing_tooling)``. A structural criterion that silently stops
    executing on a host detail is exactly what the bare-skeleton gate exists to
    rule out (SIP-0098 §7).

    The evaluator *is* a Python process, so ``sys.executable`` is by definition a
    working interpreter — which makes ``_CHECK_ENV_EXECUTABLES``' claim that the
    check environment provides ``python``/``python3`` true by construction
    instead of by image accident. It also fixes contracts already seeded with the
    bare name (v9 among them), which emitting ``python3`` could not do — and that
    would have moved the contract hash besides.

    Runs strictly *after* the safelist gate: the safelist governs what a contract
    may ask for (a name), and resolution is a spawn detail. Reversing the order
    would force every safelist pattern to know about absolute interpreter paths.
    """
    if not argv or argv[0] not in _BARE_INTERPRETERS or not sys.executable:
        return argv
    return [sys.executable, *argv[1:]]


# ---------------------------------------------------------------------------
# Base + registry
# ---------------------------------------------------------------------------


class BaseCheck:
    """Abstract evaluator for a typed acceptance check.

    Subclasses register against a ``CheckSpec`` from ``CHECK_SPECS`` via
    ``@register_check(name)``. The registration links ``cls.spec`` so the
    evaluator can introspect required/optional params and supported stacks
    if it needs to.
    """

    spec: CheckSpec  # set by @register_check

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        raise NotImplementedError


_CHECK_IMPLS: dict[str, type[BaseCheck]] = {}


def register_check(name: str) -> Callable[[type[BaseCheck]], type[BaseCheck]]:
    """Class decorator: bind an evaluator to a ``CHECK_SPECS`` entry."""

    def decorator(cls: type[BaseCheck]) -> type[BaseCheck]:
        if name not in CHECK_SPECS:
            raise ValueError(
                f"register_check: '{name}' is not in CHECK_SPECS. "
                f"Add the spec to acceptance_check_spec.py first."
            )
        if name in _CHECK_IMPLS:
            raise ValueError(f"register_check: duplicate registration for '{name}'")
        cls.spec = CHECK_SPECS[name]
        _CHECK_IMPLS[name] = cls
        return cls

    return decorator


def get_check(name: str) -> BaseCheck:
    """Instantiate the evaluator registered for a check name."""
    if name not in _CHECK_IMPLS:
        raise KeyError(f"no evaluator registered for check '{name}'")
    return _CHECK_IMPLS[name]()


def assert_registry_complete() -> None:
    """Verify every ``CHECK_SPECS`` entry has a registered evaluator.

    Called at module import so a missing pairing fails fast at deploy
    rather than at first use mid-cycle.
    """
    missing = set(CHECK_SPECS.keys()) - set(_CHECK_IMPLS.keys())
    if missing:
        raise RuntimeError(
            f"CHECK_SPECS entries lack evaluators in _CHECK_IMPLS: {sorted(missing)}"
        )


def _skip_unsupported_stack() -> CheckOutcome:
    """RC-12a: unset/unsupported stack → skipped, not error."""
    return CheckOutcome.skipped(reason="unsupported_stack_or_syntax")


# ---------------------------------------------------------------------------
# Concrete checks
# ---------------------------------------------------------------------------


def _decorator_route(decorator: ast.expr) -> tuple[str, str] | None:
    """Extract (METHOD, path) from `@router.METHOD("/path")` or `@app.METHOD("/path")`."""
    if not isinstance(decorator, ast.Call):
        return None
    if not isinstance(decorator.func, ast.Attribute):
        return None
    method = decorator.func.attr.lower()
    if method not in HTTP_METHODS:
        return None
    if not decorator.args:
        return None
    arg0 = decorator.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return method.upper(), normalize_route(arg0.value)
    return None


# Every AST-based check parses Python. Handed anything else, `ast.parse` raises and the
# check reports `error` — which `patch_verification` maps to `evaluator_error:<check>` and
# turns into an UNVERIFIABLE patch: neither accepted nor rejected, so it lands unverified.
# pf-41 lost a roll to exactly that (a `function_defined` aimed at a `.jsx` test file), and
# the contrast with pf-40 is the proof: same bad repairs, but there verification returned a
# verdict, rejected them, and nothing landed. Skipping is the honest outcome for a file we
# cannot analyse — `import_present` already did this; the other four did not (#605).
# Family definition lives in the spec module (two readers — see #688).


def _unparseable_source_skip(file_path: Path) -> CheckOutcome | None:
    """A skip outcome when ``file_path`` is not Python, else None."""
    ext = file_path.suffix.lower()
    if ext in FRONTEND_SUFFIXES:
        # JS/TS analysis is gated behind the frontend_acceptance_checks follow-up.
        return CheckOutcome.skipped(reason="frontend_acceptance_checks_disabled")
    if ext != ".py":
        return CheckOutcome.skipped(reason="unsupported_file_extension")
    return None


@register_check(CHECK_UNDEFINED_NAMES)
class UndefinedNamesCheck(BaseCheck):
    """Names a ``.py`` file uses but never binds — the call-time ``NameError`` class (#689).

    shk-2 shipped a ``backend/routes.py`` whose ``create_run`` called ``RunEvent(...)``
    without importing it. Nothing caught it: ``py_compile`` sees valid syntax,
    ``import_present`` checks the imports that ARE there, ``endpoint_defined`` reads
    decorators, and ``module_imports`` (#628) imports the module successfully because
    the name only resolves when the handler runs. First invocation was the qa suite —
    500, probe cascade, and a correction loop that never reached the defect.

    Implemented on pyflakes, in-process. It is the reference implementation ruff's
    F-rules reimplement, it is pure Python with no transitive dependencies, and running
    it in-process keeps the check free of subprocess/PATH/restricted-env concerns.

    **A missing pyflakes is an ``error``, never a ``skipped``.** The #462 skip-never-fail
    rule is for tooling with per-role variance, provisioned through
    ``agents/instances/<role>/system-packages.txt`` and declared in the SIP-0096
    ``check_registry`` (Node lives in the qa image alone, which is why it earns
    ``TOOL_NODE``). A base-lock pip dependency is present in every image by
    construction, so its absence is a build defect rather than an environment gap.
    Skipping there would ship this check as exactly the looks-enforced-but-isn't no-op
    SIP-0096 exists to kill — on the one defect class that already cost a full
    correction budget.
    """

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            # The syntax gate owns unparseable emissions; reporting it twice would
            # make one defect look like two.
            return CheckOutcome.skipped(reason="unsupported_stack_or_syntax")

        try:
            from pyflakes.checker import Checker
            from pyflakes.messages import UndefinedName
        except ImportError:  # a baked dependency is missing ⇒ the image is wrong
            return CheckOutcome.error(reason="missing_analyzer", analyzer="pyflakes")

        undefined = [
            {"name": str(m.message_args[0]), "line": m.lineno}
            for m in Checker(tree, filename=str(file_path)).messages
            if isinstance(m, UndefinedName)
        ]
        if undefined:
            names = ", ".join(f"{u['name']} (line {u['line']})" for u in undefined)
            return CheckOutcome.failed(
                reason=f"undefined name(s): {names}",
                file=str(params["file"]),
                undefined=undefined,
            )
        return CheckOutcome.passed(file=str(params["file"]))


@register_check(CHECK_ENDPOINT_DEFINED)
class EndpointDefinedCheck(BaseCheck):
    """FastAPI route decorator presence — `@app.METHOD('/path')` / `@router.METHOD('/path')`."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        if stack != "fastapi":
            return _skip_unsupported_stack()
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return CheckOutcome.error(reason="parse_failed")

        found: set[tuple[str, str]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for dec in node.decorator_list:
                    parsed = _decorator_route(dec)
                    if parsed is not None:
                        found.add(parsed)

        expected: list[tuple[str, str]] = []
        malformed: list[str] = []
        for token in params["methods_paths"]:
            parsed = parse_method_path(str(token))
            if parsed is None:
                malformed.append(token)
            else:
                expected.append(parsed)
        if malformed:
            return CheckOutcome.error(reason="malformed_methods_paths", malformed=malformed)

        missing = [f"{m} {p}" for (m, p) in expected if (m, p) not in found]
        found_strs = sorted(f"{m} {p}" for (m, p) in found)
        if missing:
            return CheckOutcome.failed(
                reason="endpoints_missing",
                found=found_strs,
                missing=missing,
            )
        return CheckOutcome.passed(found=found_strs)


@register_check("import_present")
class ImportPresentCheck(BaseCheck):
    """Import statement presence — Python AST; .ts/.js gated off in M1.2."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)

        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip

        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return CheckOutcome.error(reason="parse_failed")

        target_module = params["module"]
        target_symbol = params.get("symbol")

        module_imported = False
        symbol_imported = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == target_module:
                        module_imported = True
                        if target_symbol is None:
                            symbol_imported = True
            elif isinstance(node, ast.ImportFrom):
                # ast stores relative-import dots in `level`, never in `module`:
                # `from .errors import X` → ImportFrom(module='errors', level=1).
                prefix = "." * node.level
                effective_module = prefix + (node.module or "")
                # #441: a dotless spec follows author intent — `module: errors`
                # accepts `from .errors import X` at any level. A dotted spec
                # stays exact (`.errors` still rejects `backend.errors`).
                dotless_match = (
                    not target_module.startswith(".")
                    and node.level > 0
                    and (node.module or "") == target_module
                )
                if effective_module == target_module or dotless_match:
                    module_imported = True
                    if target_symbol is None:
                        symbol_imported = True
                    else:
                        for alias in node.names:
                            if alias.name == target_symbol:
                                symbol_imported = True
                elif node.module is None and target_symbol is None:
                    # `from . import errors` imports module `.errors`
                    for alias in node.names:
                        if prefix + alias.name == target_module:
                            module_imported = True
                            symbol_imported = True

        if not module_imported:
            return CheckOutcome.failed(reason="module_not_imported", module=target_module)
        if target_symbol is not None and not symbol_imported:
            return CheckOutcome.failed(
                reason="symbol_not_imported",
                module=target_module,
                symbol=target_symbol,
            )
        return CheckOutcome.passed(module=target_module, symbol=target_symbol)


def _classdef_field_names(cls_node: ast.ClassDef) -> set[str]:
    """Collect declared field names from a class body.

    Covers:
    - ``name: Type`` (AnnAssign) — dataclasses, Pydantic v2.
    - ``name = field(...)`` / ``name = Field(...)`` (Assign with Name target).
    """
    names: set[str] = set()
    for stmt in cls_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


@register_check("field_present")
class FieldPresentCheck(BaseCheck):
    """Class field presence — Python dataclasses + Pydantic v2."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        if stack is None:
            return _skip_unsupported_stack()
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return CheckOutcome.error(reason="parse_failed")

        target_class = params["class_name"]
        cls_node: ast.ClassDef | None = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == target_class:
                cls_node = node
                break
        if cls_node is None:
            return CheckOutcome.failed(reason="class_not_found", class_name=target_class)

        declared = _classdef_field_names(cls_node)
        expected = [str(f) for f in params["fields"]]
        missing = [f for f in expected if f not in declared]
        if missing:
            return CheckOutcome.failed(
                reason="fields_missing",
                class_name=target_class,
                declared=sorted(declared),
                missing=missing,
            )
        return CheckOutcome.passed(class_name=target_class, declared=sorted(declared))


def _defined_function_names(tree: ast.AST) -> list[str]:
    """Names of every ``def``/``async def`` in the tree — top-level, methods,
    and nested. The AST answer to 'what functions does this file define'."""
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


@register_check("function_defined")
class FunctionDefinedCheck(BaseCheck):
    """Function-definition count by name prefix — Python AST, style-immune.

    The sanctioned answer to 'this source file defines functions named X'
    (e.g. pytest ``test_*``): it matches the real ``def`` name via the AST, so
    it never prescribes another roll's wording the way a #464 source regex does.
    """

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        if stack is None:
            return _skip_unsupported_stack()
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return CheckOutcome.error(reason="parse_failed")

        name_prefix = params["name_prefix"]
        min_count = int(params.get("min_count", 1))
        matched = [n for n in _defined_function_names(tree) if n.startswith(name_prefix)]
        if len(matched) >= min_count:
            return CheckOutcome.passed(
                name_prefix=name_prefix, matched_count=len(matched), min_count=min_count
            )
        return CheckOutcome.failed(
            reason="function_count_below_minimum",
            name_prefix=name_prefix,
            matched=sorted(matched),
            matched_count=len(matched),
            min_count=min_count,
        )


def _harness_boundary_violations(
    tree: ast.AST, entry_modules: frozenset[str], client_ctor: str
) -> list[str]:
    """SIP-0100: the ways a QA test authors its own app boundary instead of consuming the
    scaffold-owned fixture — importing an app entry module (static / from-import /
    ``importlib.import_module``), or directly constructing the app test client."""

    def _is_entry(mod: str) -> bool:
        return any(mod == m or mod.startswith(m + ".") for m in entry_modules)

    viols: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_entry(alias.name):
                    viols.add(f"imports app entry module '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_entry(node.module):
                viols.add(f"imports from app entry module '{node.module}'")
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and _is_entry(node.args[0].value)
            ):
                viols.add(f"dynamically imports app entry module '{node.args[0].value}'")
            ctor = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if ctor == client_ctor:
                viols.add(f"directly constructs the app test client '{client_ctor}'")
    return sorted(viols)


@register_check("harness_boundary")
class HarnessBoundaryCheck(BaseCheck):
    """SIP-0100: a QA test consumes the scaffold-owned test boundary (the ``client`` fixture)
    and never authors its own app import or client construction. Python AST.

    Fails a test that imports an app entry module (``entry_modules``) or directly constructs the
    app test client (``client_ctor``, default ``TestClient``). A pure unit test that never touches
    the app — or one that only uses the injected ``client`` fixture — passes. Indirect / dynamically
    obscured bypasses are out of first scope (plan §1.2 / SIP-0100 review #6)."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        if stack is None:
            return _skip_unsupported_stack()
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return CheckOutcome.error(reason="parse_failed")

        entry_modules = frozenset(str(m) for m in (params.get("entry_modules") or []))
        client_ctor = str(params.get("client_ctor") or "TestClient")
        viols = _harness_boundary_violations(tree, entry_modules, client_ctor)
        if viols:
            return CheckOutcome.failed(reason="; ".join(viols), violations=viols)
        return CheckOutcome.passed(entry_modules=sorted(entry_modules), client_ctor=client_ctor)


@register_check("regex_match")
class RegexMatchCheck(BaseCheck):
    """Regex match count — stack-agnostic, size-bounded against ReDoS surface."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)

        pattern = params["pattern"]
        if not isinstance(pattern, str) or len(pattern) > DEFAULT_REGEX_PATTERN_CAP_CHARS:
            return CheckOutcome.error(reason="regex_pattern_too_large")

        count_min = int(params.get("count_min", 1))
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))

        try:
            size = file_path.stat().st_size
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        if size > DEFAULT_REGEX_INPUT_CAP_BYTES:
            return CheckOutcome.error(reason="regex_input_too_large", size_bytes=size)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        try:
            compiled = re.compile(pattern)
        except re.error:
            return CheckOutcome.error(reason="regex_invalid", pattern=pattern)

        matches = compiled.findall(content)
        match_count = len(matches)
        if match_count >= count_min:
            return CheckOutcome.passed(match_count=match_count, count_min=count_min)
        return CheckOutcome.failed(
            reason="match_count_below_minimum",
            match_count=match_count,
            count_min=count_min,
        )


@register_check("count_at_least")
class CountAtLeastCheck(BaseCheck):
    """Glob match count — workspace-chrooted, capped at 10k matches."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        glob_str = str(params["glob"])
        if Path(glob_str).is_absolute() or ".." in Path(glob_str).parts:
            return CheckOutcome.error(reason="path_escapes_workspace")

        min_count = int(params["min_count"])

        # Stream rather than materialize, so we can short-circuit at the cap.
        matches: list[Path] = []
        try:
            for i, m in enumerate(workspace_root.glob(glob_str)):
                if i >= DEFAULT_GLOB_MATCH_CAP:
                    return CheckOutcome.error(
                        reason="glob_match_cap_exceeded",
                        cap=DEFAULT_GLOB_MATCH_CAP,
                    )
                matches.append(m)
        except (OSError, ValueError) as exc:
            return CheckOutcome.error(reason="glob_failed", detail=str(exc))

        count = len(matches)
        if count >= min_count:
            return CheckOutcome.passed(count=count, min_count=min_count)
        return CheckOutcome.failed(reason="count_below_minimum", count=count, min_count=min_count)


def _tail(text: str, max_chars: int = 1024) -> str:
    """Return the last `max_chars` characters of text, for compact evidence."""
    if len(text) <= max_chars:
        return text
    return "..." + text[-max_chars:]


@register_check("command_exit_zero")
class CommandExitZeroCheck(BaseCheck):
    """Run a safelist-matched command in workspace and check exit code."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        argv = params["argv"]
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            return CheckOutcome.error(reason="command_must_be_argv")
        if not argv:
            return CheckOutcome.error(reason="command_must_be_argv")
        if not argv_matches_safelist(argv):
            return CheckOutcome.error(reason="command_not_in_safelist", argv=argv)

        timeout_s = int(params.get("timeout_s", DEFAULT_COMMAND_TIMEOUT_S))
        timeout_s = max(1, min(timeout_s, MAX_COMMAND_TIMEOUT_S))

        cwd_str = params.get("cwd")
        if cwd_str is None:
            cwd_path = workspace_root.resolve()
        else:
            try:
                cwd_path = _safe_resolve(cwd_str, workspace_root)
            except _SafetyError as exc:
                return CheckOutcome.error(reason=exc.reason)
            if not cwd_path.is_dir():
                return CheckOutcome.error(reason="cwd_not_a_directory")

        # #498: spawn the running interpreter rather than whatever `python` the
        # inherited PATH happens to resolve to. `argv` stays the authored form so
        # evidence reads back as the contract wrote it, not as an absolute path.
        spawn_argv = _resolve_interpreter(argv)
        env = _restricted_env()
        try:
            proc = await asyncio.create_subprocess_exec(
                *spawn_argv,
                cwd=str(cwd_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            # #462: a missing binary is an environment gap, not an app defect —
            # the evaluating role's container simply lacks the tool (e.g. `node`
            # in the dev container, #306). RC-9 skipped: never blocks the task,
            # never counts as executed evidence, surfaces with its reason —
            # an unrunnable check must not fail correct code or burn the
            # shared correction budget (attempt 3.9, cyc_323a1e35bee5).
            return CheckOutcome.skipped(reason="missing_tooling", command=argv[0], detail=str(exc))
        except (OSError, ValueError) as exc:
            return CheckOutcome.error(reason="command_spawn_failed", detail=str(exc))

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            try:
                await proc.wait()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            return CheckOutcome.error(reason="command_timeout", timeout_s=timeout_s)

        exit_code = proc.returncode
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        if exit_code == 0:
            return CheckOutcome.passed(exit_code=exit_code)
        return CheckOutcome.failed(
            reason="non_zero_exit",
            exit_code=exit_code,
            stdout_tail=_tail(stdout),
            stderr_tail=_tail(stderr),
        )


_MODULE_NOT_FOUND_RE = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")


@register_check("module_imports")
class ModuleImportsCheck(BaseCheck):
    """Import the file's module in a subprocess — the only runtime-level check.

    pf-54 (#628): a fill file can satisfy every static check (AST finds the
    decorators and imports, py_compile accepts the syntax) while raising at
    import time — module-level NameError is invisible until something actually
    imports the module, which until this check was the QA conftest, five
    correction attempts too late.
    """

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if (skip := _unparseable_source_skip(file_path)) is not None:
            return skip
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))

        root = workspace_root.resolve()
        parts = list(file_path.relative_to(root).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or not all(p.isidentifier() for p in parts):
            return CheckOutcome.error(
                reason="not_an_importable_module_path", file=str(params["file"])
            )
        module = ".".join(parts)

        timeout_s = int(params.get("timeout_s", DEFAULT_COMMAND_TIMEOUT_S))
        timeout_s = max(1, min(timeout_s, MAX_COMMAND_TIMEOUT_S))
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                f"import {module}",
                cwd=str(root),
                env=_restricted_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            return CheckOutcome.error(reason="command_spawn_failed", detail=str(exc))
        try:
            _stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            try:
                await proc.wait()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            return CheckOutcome.error(reason="command_timeout", timeout_s=timeout_s)

        if proc.returncode == 0:
            return CheckOutcome.passed(module=module)

        stderr = stderr_b.decode("utf-8", errors="replace")
        not_found = _MODULE_NOT_FOUND_RE.search(stderr)
        if not_found is not None:
            missing_top = not_found.group(1).split(".")[0]
            in_workspace = (root / missing_top).exists() or (root / f"{missing_top}.py").exists()
            if not in_workspace and missing_top != module.split(".")[0]:
                # A third-party dependency the evaluating container lacks is an
                # environment gap, not an app defect (#462): never fail correct
                # code on tooling the evaluator doesn't have. A missing module
                # whose top-level package IS in the workspace stays a failure —
                # that is the app referencing itself wrongly.
                return CheckOutcome.skipped(
                    reason="missing_tooling", missing_module=not_found.group(1)
                )
        return CheckOutcome.failed(
            reason="module_import_failed", module=module, stderr_tail=_tail(stderr)
        )


@register_check("frontend_compiles")
class FrontendCompilesCheck(BaseCheck):
    """Run the real frontend build against the workspace tree (#648).

    fay-4 and fay-8 both shipped a view with a rollup bind-time error (an
    undefined identifier) — invisible to every static check and to
    ``node --check`` (which refuses ``.jsx`` outright, #645), first surfacing
    at final verification where no correction budget can reach it. Only the
    actual bundler sees this class, so this check runs it at task time: the
    #643 acceptance workspace carries the full tree, ``npm install`` is
    sub-second against the agent container's warm cache, and the build's
    stderr tail becomes repair-relevant evidence.

    ``file`` anchors blame (and #641 binding) to the view under evaluation;
    the build necessarily covers the whole frontend. Skips, never fails, on
    environment gaps (#462): npm absent, or a workspace without
    ``frontend/package.json`` (pre-#643 envelopes, non-fullstack stacks).
    An install failure also skips — ``package.json`` is scaffold-frozen, so a
    failing install is a network/registry gap, not an artifact defect.
    """

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        try:
            file_path = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))

        frontend_dir = workspace_root / "frontend"
        if not (frontend_dir / "package.json").is_file():
            return CheckOutcome.skipped(reason="no_frontend_tree")
        if shutil.which("npm") is None:
            return CheckOutcome.skipped(reason="missing_tooling", missing_module="npm")

        if not (frontend_dir / "node_modules").is_dir():
            rc, _, stderr = await self._run(
                ["npm", "install", "--no-audit", "--no-fund"],
                frontend_dir,
                FRONTEND_INSTALL_TIMEOUT_S,
            )
            if rc is None:
                return CheckOutcome.error(
                    reason="command_timeout", timeout_s=FRONTEND_INSTALL_TIMEOUT_S
                )
            if rc != 0:
                return CheckOutcome.skipped(reason="install_failed", stderr_tail=_tail(stderr))

        timeout_s = int(params.get("timeout_s", FRONTEND_BUILD_TIMEOUT_S))
        timeout_s = max(1, min(timeout_s, FRONTEND_BUILD_TIMEOUT_S))
        rc, _, stderr = await self._run(["npm", "run", "build"], frontend_dir, timeout_s)
        if rc is None:
            return CheckOutcome.error(reason="command_timeout", timeout_s=timeout_s)
        if rc != 0:
            return CheckOutcome.failed(
                reason="frontend_build_failed",
                file=str(params["file"]),
                stderr_tail=_tail(stderr),
            )
        return CheckOutcome.passed(file=str(params["file"]))

    @staticmethod
    async def _run(argv: list[str], cwd: Path, timeout_s: int) -> tuple[int | None, str, str]:
        """Run one build step; ``(returncode, stdout, stderr)``, rc None on timeout."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(cwd),
                env=_restricted_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as exc:
            return 1, "", f"spawn failed: {exc}"
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            try:
                await proc.wait()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass
            return None, "", ""
        return (
            proc.returncode,
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
        )


# ---------------------------------------------------------------------------
# Module import-time invariant: every spec must have an evaluator.
# ---------------------------------------------------------------------------


assert_registry_complete()
