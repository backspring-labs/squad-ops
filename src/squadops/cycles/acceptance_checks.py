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
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_check_spec import (
    CHECK_SPECS,
    CheckSpec,
    argv_matches_safelist,
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


_HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "options", "head"})


def _normalize_route(path: str) -> str:
    """Normalize trailing slash for tolerant route comparison."""
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path


def _parse_method_path(token: str) -> tuple[str, str] | None:
    """Parse a `'METHOD /path'` token; return (method, path) or None."""
    parts = token.strip().split(maxsplit=1)
    if len(parts) != 2:
        return None
    method, path = parts[0].upper(), _normalize_route(parts[1])
    if method.lower() not in _HTTP_METHODS:
        return None
    return method, path


def _decorator_route(decorator: ast.expr) -> tuple[str, str] | None:
    """Extract (METHOD, path) from `@router.METHOD("/path")` or `@app.METHOD("/path")`."""
    if not isinstance(decorator, ast.Call):
        return None
    if not isinstance(decorator.func, ast.Attribute):
        return None
    method = decorator.func.attr.lower()
    if method not in _HTTP_METHODS:
        return None
    if not decorator.args:
        return None
    arg0 = decorator.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return method.upper(), _normalize_route(arg0.value)
    return None


@register_check("endpoint_defined")
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
            parsed = _parse_method_path(str(token))
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

        ext = file_path.suffix.lower()
        if ext in {".ts", ".js"}:
            # JS/TS regex fallback gated behind frontend_acceptance_checks
            # follow-up flag — out of scope for M1.2.
            return CheckOutcome.skipped(reason="frontend_acceptance_checks_disabled")
        if ext != ".py":
            return CheckOutcome.skipped(reason="unsupported_file_extension")

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

        env = _restricted_env()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
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


# ---------------------------------------------------------------------------
# Module import-time invariant: every spec must have an evaluator.
# ---------------------------------------------------------------------------


assert_registry_complete()
