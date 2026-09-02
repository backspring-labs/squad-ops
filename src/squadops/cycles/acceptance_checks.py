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
import json
import logging
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_check_spec import (
    CHECK_ADDITIVE_CONTAINMENT,
    CHECK_ASSERTION_KINDS,
    CHECK_CONTAINER_PACKAGING,
    CHECK_CONTRACT_ASSERTIONS,
    CHECK_DECLARED_IMPORTS,
    CHECK_DOM_ANCHOR_QUERIES,
    CHECK_ENDPOINT_DEFINED,
    CHECK_FILL_SLOT_SIGNATURE,
    CHECK_SECTIONS_PRESENT,
    CHECK_SPECS,
    CHECK_UNDEFINED_NAMES,
    CHECK_UNTERMINATED_SOURCE,
    FRONTEND_SUFFIXES,
    HTTP_METHODS,
    CheckSpec,
    argv_matches_safelist,
    normalize_route,
    parse_method_path,
    parse_method_path_status,
)
from squadops.cycles.container_packaging import packaging_findings
from squadops.cycles.source_termination import (
    SCANNABLE_EXTENSIONS,
    check_termination,
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


async def _run_argv(argv: list[str], cwd: Path, timeout_s: int) -> tuple[int | None, str, str]:
    """Run one tool under the restricted env; ``(returncode, stdout, stderr)``, rc None on
    timeout. Shared by the checks that shell out (the frontend build, tsc)."""
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


def _router_prefixes(tree: ast.AST) -> dict[str, str]:
    """``name -> prefix`` for every ``name = APIRouter(prefix="...")`` in the module.

    The prefix is a routing fact, not a stylistic one: FastAPI serves ``prefix + path``.
    Only a literal string prefix is read; anything computed leaves the router unprefixed,
    which is the conservative reading (the check then looks for the literal path).
    """
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        ctor = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if ctor != "APIRouter":
            continue
        prefix = next(
            (
                kw.value.value
                for kw in node.value.keywords
                if kw.arg == "prefix"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ),
            None,
        )
        if prefix is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                prefixes[target.id] = prefix
    return prefixes


def _decorator_route(
    decorator: ast.expr, prefixes: dict[str, str] | None = None
) -> tuple[str, str] | None:
    """Extract (METHOD, path) from `@router.METHOD("/path")` or `@app.METHOD("/path")`.

    With ``prefixes`` (#1129), a decorator on a prefixed router yields the path the app
    actually serves — ``@runs.post("")`` on ``runs = APIRouter(prefix="/runs")`` is
    ``POST /runs``.
    """
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
        receiver = decorator.func.value
        prefix = (prefixes or {}).get(receiver.id, "") if isinstance(receiver, ast.Name) else ""
        path = arg0.value
        if prefix:
            path = f"{prefix.rstrip('/')}/{path.lstrip('/')}"
        return method.upper(), normalize_route(path or "/")
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


@register_check(CHECK_UNTERMINATED_SOURCE)
class UnterminatedSourceCheck(BaseCheck):
    """The emission ends inside an unclosed construct — it was cut off (#1082).

    `cyc_87c12c7f199e` banked a 407-byte route ending on ``throw new`` with three
    unclosed braces. Nothing questioned it: the bytes look like code, and the
    checks that would reject it — ``frontend_compiles``, ``tests_pass`` — run at
    acceptance, long after the producing task finished. So it surfaced as the
    suite failing two whole test files, one of which merely imported the module,
    and the analyzer diagnosed from that output instead of from the emission.

    Injected onto the producer's OWN artifacts, so a truncation is charged to the
    task that wrote it while that task still owns the round.

    **The claim is deliberately narrow.** Not "this file is valid" — only "this
    file stops mid-construct". On Python that means filtering ``compile``'s
    SyntaxError down to the EOF-shaped ones; on the brace languages it means
    delimiter balance and nothing more. Widening it would make this the general
    syntax gate, which it cannot be on languages it does not parse.

    Validated before it shipped, which is the bar a guard has to clear: swept
    across all 4,513 scannable source artifacts in the banked corpus, it flagged
    8 — every one a genuine truncation on inspection, zero false positives. Two
    false positives found during that sweep drove real fixes rather than a
    threshold: JSX punctuation (``/>``, ``</``) misread as a regex opener, and
    parens counted inside JSX text, where an unmatched bracket is legal. A guard
    that rejects a healthy emission manufactures the defect it exists to prevent.
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
        if file_path.suffix.lower() not in SCANNABLE_EXTENSIONS:
            return CheckOutcome.skipped(reason="unsupported_file_extension")
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        result = check_termination(source, file_path.suffix)
        if not result.terminated:
            return CheckOutcome.failed(
                reason=f"emission ends mid-construct: {result.reason}",
                file=str(params["file"]),
                line=result.line,
                size_bytes=len(source),
            )
        return CheckOutcome.passed(file=str(params["file"]))


# --- undefined_names on JS/TS (#939) ---------------------------------------------------
#
# The per-file unresolved-name check the Python half gets from pyflakes, on the four
# frontend extensions, from ``tsc``. A TypeScript project (a ``tsconfig.json`` at the
# workspace root — the Next.js skeleton emits one) is checked as a project, so ``paths``
# and ``include`` are the app's own; a tree without one (the React SPA's ``frontend/``) is
# checked as an explicit file list with ``--allowJs --checkJs``, which reports ``Cannot
# find name`` in plain JS/JSX too (measured 2026-09-01 in the qa image, typescript 5.5.3).
# tsc runs ONCE per materialised tree and the diagnostics are filtered per file, because
# the criterion is file-scoped and a task emits many files. Only the unresolved-name codes
# count: a workspace materialised without ``node_modules`` reports every import as TS2307,
# and that is not this check's question — ``declared_imports`` and the build own it.
TSC_TIMEOUT_S = 60
TSC_UNDEFINED_NAME_CODES: frozenset[str] = frozenset({"TS2304", "TS2552"})
_TSC_SOURCE_SUFFIXES: frozenset[str] = frozenset({".ts", ".tsx", ".js", ".jsx"})
_TSC_EXPLICIT_FLAGS: tuple[str, ...] = (
    "--noEmit",
    "--allowJs",
    "--checkJs",
    "--jsx",
    "react-jsx",
    "--target",
    "es2022",
    "--module",
    "esnext",
    "--moduleResolution",
    "bundler",
    "--skipLibCheck",
)
_TSC_DIAGNOSTIC = re.compile(
    r"^(?P<path>[^\n(]+?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<message>.*)$"
)
_TSC_UNDEFINED_NAME = re.compile(r"Cannot find name '(?P<name>[^']+)'")
_TSC_SKIP_DIRS: frozenset[str] = frozenset({"node_modules", ".next", "dist", "build", ".git"})
#: tsc output per (workspace, mode, tree signature) — a task's criteria evaluate one file
#: each over one materialised tree, so the second file must not pay for a second run.
_TSC_OUTPUT_CACHE: dict[tuple, str | None] = {}
_TSC_OUTPUT_CACHE_MAX = 8


def _normalise_rel(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def tsc_undefined_names(output: str, file_rel: str) -> list[dict[str, Any]]:
    """``[{name, line}]`` for the unresolved-name diagnostics tsc reported in ``file_rel``.

    tsc prints one diagnostic per line, ``path(line,col): error TScode: message``, with the
    path relative to its working directory; only the codes in ``TSC_UNDEFINED_NAME_CODES``
    and only the lines for ``file_rel`` count, so a workspace full of TS2307 (no
    ``node_modules``) and another file's defects leave this file's verdict alone.
    """
    want = _normalise_rel(file_rel)
    found: list[dict[str, Any]] = []
    for raw in output.splitlines():
        m = _TSC_DIAGNOSTIC.match(raw.strip())
        if not m or m["code"] not in TSC_UNDEFINED_NAME_CODES:
            continue
        if _normalise_rel(m["path"]) != want:
            continue
        name = _TSC_UNDEFINED_NAME.search(m["message"])
        found.append({"name": name["name"] if name else m["message"], "line": int(m["line"])})
    return found


#: tsc's syntax diagnostics are TS1000–TS1999. The five-digit TS18xxx family (``'x' is
#: possibly 'undefined'``, ``'x' is of type 'unknown'``) is type checking — and it shares
#: the ``TS1`` prefix. The Next.js shakeout on dfe466ab (cyc_9c379355b5e8) skipped
#: ``undefined_names`` on five of nine accepted test files for exactly that (#1261).
_TSC_SYNTAX_CODES = range(1000, 2000)


def tsc_is_syntax_code(code: str) -> bool:
    """Whether a ``TSnnnn`` code is a syntax diagnostic (TS1000–TS1999), by value not prefix."""
    try:
        return int(code[2:]) in _TSC_SYNTAX_CODES
    except ValueError:
        return False


def tsc_syntax_errors_in(output: str, file_rel: str) -> bool:
    """True when tsc reported a syntax diagnostic (TS1000–TS1999) in ``file_rel``."""
    want = _normalise_rel(file_rel)
    for raw in output.splitlines():
        m = _TSC_DIAGNOSTIC.match(raw.strip())
        if m and tsc_is_syntax_code(m["code"]) and _normalise_rel(m["path"]) == want:
            return True
    return False


def _tsc_sources(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in _TSC_SOURCE_SUFFIXES
        and not (set(p.relative_to(root).parts[:-1]) & _TSC_SKIP_DIRS)
    )


async def _tsc_output(root: Path, *, project: bool) -> str | None:
    """tsc's combined output for ``root`` (``None`` on timeout), cached per tree.

    ``project`` checks the tree under its own ``tsconfig.json``; otherwise the explicit
    file list with the JS-capable flags.
    """
    sources = _tsc_sources(root)
    signature = (
        str(root),
        project,
        tuple((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns) for p in sources),
    )
    if signature in _TSC_OUTPUT_CACHE:
        return _TSC_OUTPUT_CACHE[signature]
    if project:
        argv = ["tsc", "--noEmit", "-p", ".", "--pretty", "false"]
    else:
        argv = [
            "tsc",
            *_TSC_EXPLICIT_FLAGS,
            "--pretty",
            "false",
            *(str(p.relative_to(root)) for p in sources),
        ]
    rc, stdout, stderr = await _run_argv(argv, root, TSC_TIMEOUT_S)
    output = None if rc is None else f"{stdout}\n{stderr}"
    if len(_TSC_OUTPUT_CACHE) >= _TSC_OUTPUT_CACHE_MAX:
        _TSC_OUTPUT_CACHE.pop(next(iter(_TSC_OUTPUT_CACHE)))
    _TSC_OUTPUT_CACHE[signature] = output
    return output


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

    **The JS/TS half (#939)** is ``tsc`` — see the module comment above the helpers. It
    is provisioned per role as data (``agents/instances/<role>/npm-global-packages.txt``,
    the dev and qa images), which is the #462 skip-never-fail case, exactly as ``npm`` is
    for ``frontend_compiles``: absent where no role declared it (runtime-api today, until
    #1229 moves repair verification to the agent), the check skips as ``missing_tooling``
    and says so. 1.7.0 roll 4 (``cyc_58d92ca2b407``) is the replay: a scaffold shell's
    fill used ``created`` without declaring it, reached vitest, and failed
    ``ReferenceError`` — with node in the image and no analyser, nothing looked.
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
        if file_path.suffix.lower() in _TSC_SOURCE_SUFFIXES:
            return await self._evaluate_frontend(params, file_path, workspace_root)
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

    async def _evaluate_frontend(
        self, params: dict[str, Any], file_path: Path, workspace_root: Path
    ) -> CheckOutcome:
        """The JS/TS half (#939): tsc's unresolved-name diagnostics for this one file."""
        if not file_path.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        if shutil.which("tsc") is None:
            return CheckOutcome.skipped(reason="missing_tooling", missing_module="tsc")
        project = (workspace_root / "tsconfig.json").is_file() and file_path.suffix.lower() in {
            ".ts",
            ".tsx",
        }
        output = await _tsc_output(workspace_root, project=project)
        if output is None:
            return CheckOutcome.error(reason="command_timeout", timeout_s=TSC_TIMEOUT_S)
        rel = _normalise_rel(str(params["file"]))
        if tsc_syntax_errors_in(output, rel):
            # The syntax gate owns unparseable emissions; reporting it twice would make
            # one defect look like two (the same rule as the Python half).
            return CheckOutcome.skipped(reason="unsupported_stack_or_syntax")
        undefined = tsc_undefined_names(output, rel)
        if undefined:
            names = ", ".join(f"{u['name']} (line {u['line']})" for u in undefined)
            return CheckOutcome.failed(
                reason=f"undefined name(s): {names}",
                file=str(params["file"]),
                undefined=undefined,
                analyzer="tsc",
            )
        return CheckOutcome.passed(file=str(params["file"]), analyzer="tsc")


#: Node's own modules are provided by the runtime, not by the manifest, so importing
#: one is not an undeclared dependency. `node:`-prefixed forms are handled separately.
_NODE_BUILTINS = frozenset(
    {
        "assert",
        "buffer",
        "child_process",
        "cluster",
        "console",
        "crypto",
        "dns",
        "events",
        "fs",
        "http",
        "http2",
        "https",
        "net",
        "os",
        "path",
        "perf_hooks",
        "process",
        "querystring",
        "readline",
        "stream",
        "string_decoder",
        "timers",
        "tls",
        "tty",
        "url",
        "util",
        "v8",
        "vm",
        "worker_threads",
        "zlib",
    }
)

#: `import x from "pkg"`, `export ... from "pkg"`, `require("pkg")`, `import("pkg")`.
#: Regex rather than a JS parser on purpose: no JS/TS parser exists in the agent
#: image (measured — `tsc` is not on PATH and eslint 6.4.0 exits 2 without a config),
#: and the specifier is a string literal in a fixed keyword position, which is the one
#: part of JS syntax a regex reads safely. Anything it cannot see, it does not report.
_JS_IMPORT_SPECIFIER = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|\bimport\s+)['"]([^'"]+)['"]""",
)


#: A scoped package is `@scope/name` with a NON-EMPTY scope; everything else takes the
#: first path segment, so `lodash/merge` is declared by `lodash`.
#:
#: The empty-scope case is why this returns None rather than a name (#1217 follow-up):
#: `@/lib/store` is a tsconfig path alias, not a package, and treating it as the scoped
#: package `@/lib` failed every Next.js route file in cyc_05abfc7c1f00 and burned the
#: run's whole correction budget on a defect that did not exist.
def _package_root(specifier: str) -> str | None:
    parts = specifier.split("/")
    if specifier.startswith("@"):
        scope = parts[0][1:]
        if not scope:
            return None  # `@/...` — a path alias, decidable only against tsconfig
        return "/".join(parts[:2])
    return parts[0]


def _alias_prefixes(file_path: Path, workspace_root: Path) -> tuple[str, ...]:
    """Path-alias prefixes declared in the nearest tsconfig/jsconfig, e.g. ``("@/",)``.

    A project may alias anything to anywhere, and an aliased specifier is a path, not a
    package — reporting one is the #645 fails-on-correct-content class this check spent
    a roll proving it could still commit. Read as prefixes rather than resolved, because
    the question here is only "is this a package name", never "where does it point".
    """
    current = file_path.parent
    root = workspace_root.resolve()
    while True:
        for name in ("tsconfig.json", "jsconfig.json"):
            candidate = current / name
            if not candidate.is_file():
                continue
            try:
                # tsconfig permits comments and trailing commas; a strict parse failing
                # must not turn into a report. Undecidable is undecidable.
                config = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return ()
            paths = (config.get("compilerOptions") or {}).get("paths") or {}
            return tuple(sorted(p.split("*")[0] for p in paths if isinstance(p, str)))
        if current.resolve() == root or current.parent == current:
            return ()
        current = current.parent


def _nearest_package_json(file_path: Path, workspace_root: Path) -> Path | None:
    """The `package.json` governing ``file_path``, searching upward to the workspace root.

    Upward rather than at a fixed location because a stack may nest one (`frontend/`)
    or hold it at the root, and hard-coding either would make the check silently
    inapplicable on the other — the #1216 failure mode this check exists to avoid
    reproducing.
    """
    current = file_path.parent
    root = workspace_root.resolve()
    while True:
        candidate = current / "package.json"
        if candidate.is_file():
            return candidate
        if current.resolve() == root or current.parent == current:
            return None
        current = current.parent


@register_check(CHECK_DECLARED_IMPORTS)
class DeclaredImportsCheck(BaseCheck):
    """Bare-specifier imports a JS/TS emission uses but the workspace never declares (#1217).

    `cyc_0a0a33b4776e` shipped a `runs.test.jsx` importing
    `@testing-library/user-event` beside three declared `@testing-library/*` siblings.
    Vite failed to resolve it, the suite never ran, and three correction rounds went
    to a defect two files could have decided at emission time: the specifiers are in
    the source, the dependencies are in `package.json` beside it.

    `unresolved_imports` (#591) cannot cover this — it ignores everything outside the
    workspace by design. This is that check's counterpart at the boundary it excludes.

    **Conservative in the same way its Python sibling is.** It reports only when the
    manifest is present, parses, and demonstrably does not declare the package. A
    missing or unparseable `package.json` is undecidable, not a failure — a JS file
    with no manifest above it is not evidence of anything.
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
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        manifest_path = _nearest_package_json(file_path, workspace_root)
        if manifest_path is None:
            return CheckOutcome.skipped(reason="no_package_json_above_file")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return CheckOutcome.skipped(reason="package_json_unreadable")

        declared = set()
        for section in (
            "dependencies",
            "devDependencies",
            "peerDependencies",
            "optionalDependencies",
        ):
            value = manifest.get(section)
            if isinstance(value, dict):
                declared.update(value)

        aliases = _alias_prefixes(file_path, workspace_root)
        missing: list[str] = []
        for specifier in _JS_IMPORT_SPECIFIER.findall(source):
            # Relative and absolute paths are unresolved_imports' business, and a
            # builtin is provided by the runtime rather than by the manifest.
            if specifier.startswith((".", "/")) or specifier.startswith("node:"):
                continue
            if aliases and specifier.startswith(aliases):
                continue  # a declared path alias resolves to a file, not a package
            root = _package_root(specifier)
            if root is None:
                continue  # empty-scope specifier: an alias by construction
            if root in declared or root in _NODE_BUILTINS:
                continue
            if root not in missing:
                missing.append(root)

        if missing:
            return CheckOutcome.failed(
                reason=f"undeclared import(s): {', '.join(missing)}",
                file=str(params["file"]),
                undeclared=missing,
                manifest=str(manifest_path.relative_to(workspace_root)),
            )
        return CheckOutcome.passed(file=str(params["file"]))


def _client_http_call(expr: ast.expr) -> tuple[str, str] | None:
    """``(METHOD, path)`` when ``expr`` is a client-style HTTP call with a string-
    literal path — ``client.post("/runs", ...)``, any receiver, ``await`` unwrapped —
    else ``None``. Style-immune by construction: the receiver is whatever name the
    suite uses (``harness_boundary`` guarantees it is the scaffold client)."""
    if isinstance(expr, ast.Await):
        expr = expr.value
    if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute)):
        return None
    if expr.func.attr.lower() not in HTTP_METHODS or not expr.args:
        return None
    arg0 = expr.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return expr.func.attr.upper(), arg0.value
    return None


def _assert_status_triples(
    node: ast.Assert, bindings: list[tuple[str, int, tuple[str, str]]]
) -> list[tuple[str, str, int, int]]:
    """``(METHOD, path, asserted_status, lineno)`` rows an assert deterministically
    pins: ``assert <resp>.status_code == <int>`` (either operand order, ``Eq`` only),
    where ``<resp>`` is a name bound from a client call earlier in the function or
    the client call itself. Anything else is unextractable — out of scope (#629:
    deterministic where assertions are extractable, never a guess)."""
    test = node.test
    if not (
        isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)
    ):
        return []
    left, right = test.left, test.comparators[0]
    if isinstance(right, ast.Constant) and isinstance(right.value, int):
        attr, status = left, right.value
    elif isinstance(left, ast.Constant) and isinstance(left.value, int):
        attr, status = right, left.value
    else:
        return []
    if not (isinstance(attr, ast.Attribute) and attr.attr == "status_code"):
        return []
    base = attr.value
    call = _client_http_call(base)
    if call is None and isinstance(base, ast.Name):
        # latest binding of this name before the assert (source order, not walk order)
        prior = [b for name, line, b in bindings if name == base.id and line < node.lineno]
        call = prior[-1] if prior else None
    if call is None:
        return []
    return [(call[0], call[1], status, node.lineno)]


def _extract_status_assertions(tree: ast.AST) -> list[tuple[str, str, int, int]]:
    """Every deterministically-extractable ``(METHOD, path, status, lineno)`` a
    suite asserts, per function (response bindings do not leak across tests)."""
    out: list[tuple[str, str, int, int]] = []
    for func in (
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ):
        bindings: list[tuple[str, int, tuple[str, str]]] = []
        nodes = sorted(
            (n for n in ast.walk(func) if isinstance(n, ast.Assign | ast.Assert)),
            key=lambda n: n.lineno,
        )
        for node in nodes:
            if isinstance(node, ast.Assign):
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    call = _client_http_call(node.value)
                    if call is not None:
                        bindings.append((node.targets[0].id, node.lineno, call))
            else:
                out.extend(_assert_status_triples(node, bindings))
    return out


def _prefixed_pinned_path(
    method: str, path: str, pinned: dict[tuple[str, str], set[int]]
) -> str | None:
    """The pinned path ``path`` reaches through an undeclared prefix, or ``None``.

    pf-54: three of five suite versions prefixed every call with ``/api`` — the
    proxy-owned prefix that must not appear in backend paths — making the status
    rule blind (no pinned match) while every call deterministically 404s against
    the harness client. A request path that is NOT itself pinned but ends with a
    pinned path at a segment boundary (``/api`` + ``/runs``) is that violation."""
    for (m, p), _statuses in pinned.items():
        if m == method and path != p and path.endswith(p):
            return p
    return None


# --- assertion_kinds_match (#1153) ----------------------------------------------------
#
# A free-authored suite asserts a response field equals a literal; the manifest declares
# the field's kind. When the literal's kind cannot be the declared kind, no application
# can satisfy the assertion and no repair should try. Both extractors return
# ``(field, literal kind, line)`` and deliberately stop at what is decidable from the
# text: a comparison to a name, a call, ``None``/``null``, a negated matcher, or a field
# the manifest names with more than one kind, is not this check's to judge.

_KIND_BOOLEAN = "boolean"
_KIND_NUMBER = "number"
_KIND_STRING = "string"
_KIND_LIST = "list"
_KIND_OBJECT = "object"


def _py_accessed_field(node: ast.AST) -> str | None:
    """``x["field"]`` / ``x.get("field")`` → ``field``; anything else → None."""
    if isinstance(node, ast.Subscript):
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return key.value
        return None
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _py_literal_kind(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool):
            return _KIND_BOOLEAN
        if isinstance(value, int | float):
            return _KIND_NUMBER
        if isinstance(value, str):
            return _KIND_STRING
        return None
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, int | float)
        and not isinstance(node.operand.value, bool)
    ):
        return _KIND_NUMBER
    if isinstance(node, ast.List | ast.Tuple):
        return _KIND_LIST
    if isinstance(node, ast.Dict):
        return _KIND_OBJECT
    return None


def assertion_literal_kinds_python(tree: ast.AST) -> list[tuple[str, str, int]]:
    """Every ``assert <field access> == <literal>`` (either order, ``is`` included), as
    ``(field, literal kind, line)``."""
    out: list[tuple[str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
            continue
        cmp = node.test
        if len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq | ast.Is):
            continue
        left, right = cmp.left, cmp.comparators[0]
        for access, other in ((left, right), (right, left)):
            field = _py_accessed_field(access)
            kind = _py_literal_kind(other)
            if field and kind:
                out.append((field, kind, node.lineno))
                break
    return out


_JS_MATCHER = re.compile(r"\.\s*(?:toBe|toEqual|toStrictEqual)\s*\(")
_JS_FIELD_TAIL = re.compile(r"""(?:\.([A-Za-z_$][\w$]*)|\[\s*['"]([^'"]+)['"]\s*\])\s*$""")
_JS_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _js_literal_kind(literal: str) -> str | None:
    if not literal or literal in ("null", "undefined"):
        return None
    if literal in ("true", "false"):
        return _KIND_BOOLEAN
    if literal[0] in "'\"`":
        return _KIND_STRING
    if _JS_NUMBER.fullmatch(literal):
        return _KIND_NUMBER
    if literal[0] == "[":
        return _KIND_LIST
    if literal[0] == "{":
        return _KIND_OBJECT
    return None


def assertion_literal_kinds_js(source: str) -> list[tuple[str, str, int]]:
    """Every ``expect(<...>.field).toBe(<literal>)`` / ``toEqual`` / ``toStrictEqual``, as
    ``(field, literal kind, line)``. A ``.not.`` before the matcher is skipped."""
    out: list[tuple[str, str, int]] = []
    for m in _JS_MATCHER.finditer(source):
        head = source[: m.start()].rstrip()
        if re.search(r"\.\s*not$", head) or not head.endswith(")"):
            continue
        depth, i = 0, len(head) - 1
        while i >= 0:
            if head[i] == ")":
                depth += 1
            elif head[i] == "(":
                depth -= 1
                if depth == 0:
                    break
            i -= 1
        if i < 0 or not head[:i].rstrip().endswith("expect"):
            continue
        tail = _JS_FIELD_TAIL.search(head[i + 1 : -1].strip())
        if not tail:
            continue
        depth, j = 1, m.end()
        while j < len(source) and depth:
            depth += {"(": 1, ")": -1}.get(source[j], 0)
            j += 1
        kind = _js_literal_kind(source[m.end() : j - 1].strip())
        if kind:
            out.append((tail.group(1) or tail.group(2), kind, source.count("\n", 0, m.start()) + 1))
    return out


@register_check(CHECK_ASSERTION_KINDS)
class AssertionKindsMatchCheck(BaseCheck):
    """A suite's literal assertions diffed against the manifest's declared field kinds (#1153).

    1.6.6 React roll 3 (``cyc_38d1e1689766``): the manifest declared
    ``LeaveResult.removed: boolean``; every qa emission asserted
    ``body["removed"] == "Carol"``; the round-0 repair set it ``True`` — correct per the
    contract — and was rejected by the suite's own assertion, three rounds running. The
    free-authored counterpart of #1094's fill kind gate: the contradiction is between
    the assertion and a declared kind, so it is decidable at emission, and the suite is
    re-authored with the field and its kind named rather than a correct app repaired
    against a wrong test.

    Params are self-contained (the #629 pattern): ``field_kinds`` carries the manifest's
    kinds by name, only for names the manifest declares with one kind, so the evaluator
    needs no manifest and never guesses which entity a body is.
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
        kinds = params.get("field_kinds")
        if not isinstance(kinds, dict) or not kinds:
            # An injected check with no declaration is an injection bug, never the
            # suite's fault (the same rule as fill_slot_signature).
            return CheckOutcome.error(reason="missing_field_kinds")
        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")
        ext = file_path.suffix.lower()
        if ext == ".py":
            try:
                asserted = assertion_literal_kinds_python(
                    ast.parse(source, filename=str(file_path))
                )
            except SyntaxError:
                return CheckOutcome.skipped(reason="unsupported_stack_or_syntax")
        elif ext in _TSC_SOURCE_SUFFIXES:
            asserted = assertion_literal_kinds_js(source)
        else:
            return CheckOutcome.skipped(reason="unsupported_file_extension")
        contradictions = [
            {"line": line, "field": field, "asserted": kind, "declared": str(kinds[field])}
            for field, kind, line in asserted
            if field in kinds and str(kinds[field]) != kind
        ]
        if contradictions:
            detail = "; ".join(
                f"line {c['line']}: {c['field']} asserted as {c['asserted']}, "
                f"the manifest declares {c['field']}: {c['declared']}"
                for c in contradictions
            )
            return CheckOutcome.failed(
                reason=f"assertion contradicts a declared field kind: {detail}",
                file=str(params["file"]),
                contradictions=contradictions,
            )
        return CheckOutcome.passed(file=str(params["file"]), assertions_read=len(asserted))


@register_check(CHECK_FILL_SLOT_SIGNATURE)
class FillSlotSignatureCheck(BaseCheck):
    """The fill slot's scaffold-owned signature surface, enforced (#730 D1/#504).

    pf-40: the stub header's "scaffold-owned signatures, fill-only bodies" was
    instruction, not enforcement — the producer dropped response_model and
    renamed the handler and its params, and only the body-independent elements
    (status_code, router assignment) could be safely RESTORED at storage.
    The rest was report-only, so the drift was free. This check makes it cost:
    any divergence on a reported element fails acceptance with the divergence
    list as evidence, routing repair at the producer — the framework never
    rewrites producer code.

    Params are self-contained (the #629 pattern): ``routes`` carries the
    seed's declared signature surface, so evaluation needs no scaffold access.
    A dropped route is ``endpoint_defined``'s job; an unparseable emission is
    the syntax gate's.
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
            ast.parse(source, filename=str(file_path))
        except SyntaxError:
            # The syntax gate owns unparseable emissions; reporting it twice
            # would make one defect look like two.
            return CheckOutcome.skipped(reason="unsupported_stack_or_syntax")

        declared = params.get("routes")
        if not isinstance(declared, list) or not declared:
            # An injected check with no declaration is an injection bug, not
            # an app gap — never fail the producer for it.
            return CheckOutcome.error(reason="missing_route_declaration")

        from squadops.cycles.fill_slot_integrity import signature_divergences

        divergences = signature_divergences(declared, source)
        if divergences:
            return CheckOutcome.failed(
                reason="scaffold-owned signature diverged: " + "; ".join(divergences),
                file=str(params["file"]),
                divergences=divergences,
            )
        return CheckOutcome.passed(file=str(params["file"]))


@register_check(CHECK_CONTRACT_ASSERTIONS)
class ContractAssertionsMatchCheck(BaseCheck):
    """Suite status assertions diffed against the contract's pinned statuses (#629, 1.5 A6/D2).

    pf-54: the contract pinned ``POST /runs → 201``; all five authored suite versions
    asserted 200-on-create, and five dev-chain repairs of a contract-correct app were
    honestly rejected against a suite the contract says is wrong — the full correction
    budget burned on an unwinnable objective. Layer 1 (#629's authoring injection)
    states the pins to the author; this check is the guarantee.

    A violation requires an exact pinned ``(METHOD, path)`` whose asserted status is
    outside pinned ∪ allowed-error — asserting 422 after a blank-input POST is
    contract-correct, never flagged — or a pinned path requested through an
    undeclared prefix. Unextractable assertions and non-contract paths are out of
    scope by design: a false positive in a BLOCKING check recreates the unwinnable
    loop this kills.
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
            # The syntax gate owns unparseable emissions (#605 sibling semantics).
            return CheckOutcome.skipped(reason="unsupported_stack_or_syntax")

        pinned: dict[tuple[str, str], set[int]] = {}
        for token in params.get("endpoints") or []:
            parsed = parse_method_path_status(str(token))
            if parsed is not None:
                pinned.setdefault((parsed[0], parsed[1]), set()).add(parsed[2])
        if not pinned:
            # The injection only fires with pinned endpoints in hand — an empty
            # or unparseable param set is an evaluator-contract bug (RC-9a).
            return CheckOutcome.error(reason="invalid_endpoints_param")
        allowed_errors = {
            int(s) for s in params.get("allowed_error_statuses") or [] if str(s).isdigit()
        }

        violations: list[str] = []
        for method, raw_path, status, lineno in _extract_status_assertions(tree):
            path = normalize_route(raw_path)
            statuses = pinned.get((method, path))
            if statuses is not None:
                if status not in statuses | allowed_errors:
                    violations.append(
                        f"line {lineno}: {method} {path} asserts {status}; "
                        f"contract pins {sorted(statuses | allowed_errors)}"
                    )
            else:
                hit = _prefixed_pinned_path(method, path, pinned)
                if hit is not None:
                    violations.append(
                        f"line {lineno}: {method} {path} requests pinned path "
                        f"{hit} through an undeclared prefix"
                    )
        if violations:
            shown = violations[:5]
            if len(violations) > len(shown):
                shown.append(f"+{len(violations) - len(shown)} more")
            return CheckOutcome.failed(
                reason="; ".join(shown),
                file=str(params["file"]),
                violations=len(violations),
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

        # #1129: a router built with ``APIRouter(prefix="/runs")`` serves ``/runs`` from
        # ``@router.post("")`` — the same endpoint the literal form declares. Reading only
        # the decorator's literal refused a correct repair (1.6.5 FastAPI+React roll 6).
        prefixes = _router_prefixes(tree)
        found: set[tuple[str, str]] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                for dec in node.decorator_list:
                    parsed = _decorator_route(dec, prefixes)
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

        # #822: which directory holds the buildable project is a STACK fact, not a property
        # of frontends. `fullstack_fastapi_react` builds in `frontend/`; a Next.js app builds
        # at the root. Hardcoding it meant a second stack's every view check reported
        # `no_frontend_tree` — not-executed for the whole stack, which SIP-0096 declines to
        # credit but which also silently removes the only bundler-level coverage those views
        # have. The default preserves stack #1 byte-for-byte: its criteria pack emits no
        # `project_dir`, so its contract is unchanged.
        try:
            frontend_dir = _safe_resolve(str(params.get("project_dir", "frontend")), workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
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
        return await _run_argv(argv, cwd, timeout_s)


@register_check(CHECK_DOM_ANCHOR_QUERIES)
class DomAnchorQueriesCheck(BaseCheck):
    """#668: a frontend suite locates elements through the manifest's anchors.

    ``anchors`` is the inventory the planner bound (``{view: [data-testid, ...]}``); the
    rules and the banked observations are ``dom_anchor_queries``' (pure over the bytes).
    An empty inventory judges nothing and skips — the planner never binds one, but a
    hand-authored row could."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        from squadops.capabilities.dom_anchor_queries import (
            anchor_findings,
            anchor_observations,
        )

        rel = str(params["file"])
        inventory = {
            str(view): [str(a) for a in anchors]
            for view, anchors in (params.get("anchors") or {}).items()
            if isinstance(anchors, (list, tuple)) and anchors
        }
        if not inventory:
            return CheckOutcome.skipped(reason="no_anchor_inventory", file=rel)
        try:
            target = _safe_resolve(rel, workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if not target.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=rel)
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        observations = anchor_observations(content, inventory)
        findings = anchor_findings(content, inventory)
        if findings:
            rules = sorted({f.rule for f in findings})
            return CheckOutcome.failed(
                reason=f"{len(findings)} anchor finding(s): {', '.join(rules)}",
                file=rel,
                findings=[{"rule": f.rule, "detail": f.detail} for f in findings],
                **observations,
            )
        return CheckOutcome.passed(file=rel, findings=[], **observations)


@register_check(CHECK_SECTIONS_PRESENT)
class SectionsPresentCheck(BaseCheck):
    """#1255: a markdown document carries every required section, by name, in any order.

    ``sections`` are the build profile's (the framework binds them onto the builder task
    that owns the handoff); the rule is ``handoff_sections.missing_sections`` — the same
    one the builder handler's validation applies. An empty ``sections`` judges nothing
    and skips."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        from squadops.capabilities.handoff_sections import missing_sections

        rel = str(params["file"])
        sections = [str(s) for s in (params.get("sections") or []) if str(s).strip()]
        if not sections:
            return CheckOutcome.skipped(reason="no_sections_declared", file=rel)
        try:
            target = _safe_resolve(rel, workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if not target.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=rel)
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        missing = missing_sections(content, sections)
        if missing:
            return CheckOutcome.failed(
                reason=f"missing section(s): {', '.join(missing)}",
                file=rel,
                missing=missing,
                sections=sections,
            )
        return CheckOutcome.passed(file=rel, missing=[], sections=sections)


@register_check(CHECK_ADDITIVE_CONTAINMENT)
class AdditiveContainmentCheck(BaseCheck):
    """#1022: an author-written JS/TS suite is contained by the stack's own definition.

    Two rules over the suite's bytes (``additive_containment.containment_findings``): a
    fetch of a live server inside the in-process harness, and a suite that invokes
    nothing the stack counts as the application. The stack is the ``stack`` param the
    framework injected (the scaffold name; the evaluator's ``stack`` argument carries the
    check vocabulary, which Next.js does not declare); without it, or for a stack that
    declares no ``AppInvocation``, the check skips — judged nothing, never clean. The
    failure names each rule and what the stack counts, so the re-emission brief and the
    repair carry it."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        from squadops.capabilities.additive_containment import containment_findings
        from squadops.capabilities.scaffold import app_invocation_for

        rel = str(params["file"])
        invocation = app_invocation_for(str(params.get("stack") or ""))
        if invocation is None:
            return CheckOutcome.skipped(
                reason="unknown_stack", file=rel, stack=params.get("stack") or stack
            )
        if not invocation.is_suite(rel):
            return CheckOutcome.skipped(reason="not_a_suite", file=rel)
        try:
            target = _safe_resolve(rel, workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if not target.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=rel)
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        findings = containment_findings(rel, content, invocation)
        if findings:
            rules = sorted({f.rule for f in findings})
            return CheckOutcome.failed(
                reason=f"{len(findings)} containment finding(s): {', '.join(rules)}",
                file=rel,
                findings=[{"rule": f.rule, "detail": f.detail} for f in findings],
            )
        return CheckOutcome.passed(file=rel, findings=[])


@register_check(CHECK_CONTAINER_PACKAGING)
class ContainerPackagingCheck(BaseCheck):
    """#598: the emitted container's packaging, read statically and reported only.

    The recipe (``file``) against the materialised tree — the accepted workspace plus this
    task's own artifacts, which is the build context an image would be built from. The
    findings are the three pf-38 defects (``container_packaging.packaging_findings``); the
    outcome fails with them named so they are banked, and the warning severity the spec
    declares keeps that failure advisory everywhere it is read. Never builds an image."""

    async def evaluate(
        self,
        params: dict[str, Any],
        workspace_root: Path,
        *,
        stack: str | None = None,
    ) -> CheckOutcome:
        try:
            recipe = _safe_resolve(params["file"], workspace_root)
        except _SafetyError as exc:
            return CheckOutcome.error(reason=exc.reason)
        if not recipe.is_file():
            return CheckOutcome.failed(reason="file_not_found", file=str(params["file"]))
        try:
            text = recipe.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return CheckOutcome.error(reason="file_unreadable")

        root = workspace_root.resolve()
        tree: list[str] = []
        for path in root.rglob("*"):
            if len(tree) >= DEFAULT_GLOB_MATCH_CAP:
                break
            if path.is_file():
                tree.append(path.relative_to(root).as_posix())

        def read_file(rel: str) -> str | None:
            try:
                target = _safe_resolve(rel, root)
            except _SafetyError:
                return None
            if not target.is_file():
                return None
            try:
                return target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None

        findings = packaging_findings(text, str(params["file"]), tree, read_file)
        if findings:
            codes = sorted({f["finding"] for f in findings})
            return CheckOutcome.failed(
                reason=f"{len(findings)} packaging finding(s): {', '.join(codes)}",
                file=str(params["file"]),
                findings=findings,
            )
        return CheckOutcome.passed(file=str(params["file"]), findings=[])


# ---------------------------------------------------------------------------
# Module import-time invariant: every spec must have an evaluator.
# ---------------------------------------------------------------------------


assert_registry_complete()
