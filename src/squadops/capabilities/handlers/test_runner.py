"""Test runner for QA build validation — executes LLM-generated test files.

Materialises source + test files into a temporary workspace and runs
test frameworks (pytest, vitest, or both) as subprocesses.  The result
is captured as a ``RunTestsResult`` frozen dataclass that the QA handler
can attach as an artifact.

All exceptions are caught so that a test-runner failure never crashes
the handler — callers always get a ``RunTestsResult``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from squadops.capabilities.app_invocation import JS_SUITE_SUFFIXES

logger = logging.getLogger(__name__)

_STDOUT_LIMIT = 64 * 1024  # 64 KB


@dataclass(frozen=True)
class RunTestsResult:
    """Outcome of running generated tests in a temporary workspace."""

    executed: bool
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    test_file_count: int = 0
    source_file_count: int = 0
    # #626: runner identity + a runner-NEUTRAL suite-health verdict, classified
    # HERE because this module owns test-framework knowledge. The locus
    # classifier (cycles/failure_evidence) consumes the neutral fact instead of
    # applying pytest exit-code semantics to every runner. suite_broken:
    # True = the suite itself cannot run (collection/transform/import death,
    # or no collectable suite exists at all (#665) — the producing role
    # re-authors); False = the suite ran and judged the subject; None =
    # ambiguous (falls back to legacy exit-code semantics).
    runner: str = ""
    suite_broken: bool | None = None
    # #407: the fullstack frontend build outcome, surfaced distinctly so qa.test
    # can emit a frontend_build SIP-0096 CheckResult. None when no frontend was in
    # scope (non-fullstack run). A skip (``ran=False``) is otherwise folded away by
    # run_build_validation — exactly the #306 not-executed case that must not read
    # green once frontend_build is a required check.
    frontend_build: BuildCheckResult | None = None
    # SIP-0104 P5: per-failure observation rows from the runner's machine report
    # (vitest JSON reporter): {file, title, messages, line, suite_level}. The evidence
    # pipeline classifies scaffold-shell failures from these; empty when the runner
    # produced no machine report (pytest runs, report write failure) — additive, never
    # load-bearing for the pass/fail verdict.
    test_failures: tuple[dict, ...] = ()
    # Test files handed to the runner that it never collected — authored suites that
    # cannot run and therefore verify nothing, while the surrounding suite reads green.
    # Measured on SIP-0104 window roll 1 (cyc_04d36309d793): qa authored a ~9KB suite at
    # `tests/api/runs.test.ts`, outside this stack's `**/__tests__/**/*.test.ts` include,
    # so 9 files went in and 8 collected — the semantic layer's additive half evaporated
    # silently. Reported, not verdict-changing (promotion to a blocking check is a
    # deliberate decision, not a side effect of detection).
    uncollected_test_files: tuple[str, ...] = ()

    @property
    def tests_passed(self) -> bool:
        return self.executed and self.exit_code == 0

    @property
    def summary(self) -> str:
        if not self.executed:
            return f"tests not run: {self.error}" if self.error else "tests not run"
        if self.exit_code == 0:
            return (
                f"all tests passed "
                f"({self.test_file_count} test file(s), "
                f"{self.source_file_count} source file(s))"
            )
        return (
            f"tests failed (exit code {self.exit_code}, "
            f"{self.test_file_count} test file(s), "
            f"{self.source_file_count} source file(s))"
        )


def _materialize_files(
    workspace: str,
    files: list[dict[str, str]],
) -> None:
    """Write ``[{"path": ..., "content": ...}, ...]`` into *workspace*.

    SIP-0100 2.2: delegates to the single unified ``materialize`` so the qa.test workspace and the
    typed-acceptance / patch-verify workspaces share ONE write path — 0.1 found these were separate
    and that this one (the pf-26 pytest workspace) bypassed the chokepoint. Behavior-preserving
    today (no authorization passed); ownership authorization is wired in 2.4."""
    from squadops.cycles.patch_verification import materialize

    materialize(files, workspace)


def _find_package_json_dir(files: list[dict[str, str]]) -> str | None:
    """Return the workspace-relative dir of the shallowest ``package.json``.

    Discovers where the Node project root actually is instead of assuming a fixed
    ``frontend/`` — models sometimes place ``package.json`` at ``frontend/src/``
    or the workspace root (#303). ``""`` means the workspace root; ``None`` means
    no ``package.json`` was produced at all.
    """
    dirs = [
        os.path.dirname(rec["path"])
        for rec in files
        if os.path.basename(rec["path"]) == "package.json"
    ]
    if not dirs:
        return None
    # Shallowest (fewest path segments, then shortest) is the real project root.
    return min(dirs, key=lambda d: (d.count("/") if d else -1, len(d)))


def _source_dir_pythonpath(workspace: str, source_files: list[dict[str, str]]) -> str:
    """Build a ``PYTHONPATH`` covering every dir that holds a Python source file.

    So a ``backend/``-nested app whose test does ``from main import app`` (main at
    ``backend/main.py``) imports cleanly even though pytest runs from the
    workspace root (#303).

    #454: a directory that IS a package (has ``__init__.py``) never goes on the
    path directly — putting ``backend/`` itself on PYTHONPATH makes its modules
    importable as top-level, where ``from .errors import X`` raises "attempted
    relative import with no known parent package" (the fill-contract scaffold's
    35/35-passing suite failed on exactly this in run_33640d896265). Instead,
    walk up to the first non-package ancestor (usually the workspace root,
    already present). Flat layouts without ``__init__.py`` keep the #303
    behavior unchanged.
    """
    dirs = {
        os.path.dirname(os.path.join(workspace, rec["path"]))
        for rec in source_files
        if rec["path"].endswith(".py")
    }
    resolved: set[str] = set()
    for d in dirs:
        while os.path.exists(os.path.join(d, "__init__.py")) and len(d) > len(workspace):
            d = os.path.dirname(d)
        resolved.add(d)
    existing = os.environ.get("PYTHONPATH", "")
    parts = [workspace, *sorted(resolved)]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


async def run_generated_tests(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> RunTestsResult:
    """Run *test_files* against *source_files* in an isolated temp directory.

    Each element is ``{"path": "<relative>", "content": "<text>"}``.

    Returns a ``RunTestsResult`` — never raises.
    """
    if not test_files:
        # #665: zero suite = the producing role's own artifact is missing, an
        # explicit verdict, not ambiguity — without it fay-13's absent suite
        # classified UNKNOWN and burned every correction round on dev repairs.
        return RunTestsResult(
            executed=False,
            error="no test files provided",
            test_file_count=0,
            source_file_count=len(source_files),
            suite_broken=True,
        )

    # Test-authorship guard: pytest discovers only test_*.py / *_test.py. Both
    # night measurement rolls shipped a single qa/test_smoke.js — pytest
    # collected nothing (exit 5) and the red surfaced at run end with no
    # actionable reason. Refuse up front with a repair-precise message so the
    # correction loop fixes authorship, not symptoms.
    discoverable = [
        f
        for f in test_files
        if f.get("path", "").endswith(".py")
        and (Path(f["path"]).name.startswith("test_") or f["path"].endswith("_test.py"))
    ]
    if not discoverable:
        got = ", ".join(sorted(f.get("path", "?") for f in test_files)) or "none"
        return RunTestsResult(
            executed=False,
            error=(
                "no pytest-discoverable test files — backend tests must be Python "
                f"files named test_*.py (got: {got})"
            ),
            test_file_count=len(test_files),
            source_file_count=len(source_files),
            # #665: nothing collectable exists — same own-artifact verdict as
            # the empty case (this is the pre-emptive form of pytest exit 5).
            suite_broken=True,
        )

    workspace = tempfile.mkdtemp(prefix="qa_run_")
    try:
        all_files = source_files + test_files
        _materialize_files(workspace, all_files)

        env = {**os.environ, "PYTHONPATH": _source_dir_pythonpath(workspace, source_files)}
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pytest",
            ".",
            "--tb=short",
            "-q",
            cwd=workspace,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            raw_stdout, raw_stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return RunTestsResult(
                executed=False,
                error=f"pytest timed out after {timeout_seconds}s",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        stdout = raw_stdout.decode(errors="replace")[:_STDOUT_LIMIT]
        stderr = raw_stderr.decode(errors="replace")[:_STDOUT_LIMIT]

        exit_code = proc.returncode or 0
        return RunTestsResult(
            executed=True,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            test_file_count=len(test_files),
            source_file_count=len(source_files),
            runner="pytest",
            # pytest speaks suite-health through exit codes: 2/5 = the suite
            # itself is broken; 1 = it ran and judged the subject; 3/4 stay
            # ambiguous (the pf-35 exit-4 lesson — app-import failures surface
            # there too).
            suite_broken={2: True, 5: True, 1: False, 0: False}.get(exit_code),
        )

    except Exception as exc:
        logger.warning("Test runner error: %s", exc, exc_info=True)
        return RunTestsResult(
            executed=False,
            error=str(exc),
            test_file_count=len(test_files),
            source_file_count=len(source_files),
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


async def run_node_tests(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> RunTestsResult:
    """Run vitest in a Node workspace (D6).

    Materializes files, discovers the ``package.json`` dir (#303 — don't assume a
    fixed ``frontend/``), then runs ``npm install`` and ``npx vitest run`` there.

    Returns a ``RunTestsResult`` — never raises.
    """
    if not test_files:
        # #665: zero suite = own-artifact verdict, same as the pytest runner.
        return RunTestsResult(
            executed=False,
            error="no test files provided",
            test_file_count=0,
            source_file_count=len(source_files),
            suite_broken=True,
        )

    workspace = tempfile.mkdtemp(prefix="qa_node_")
    try:
        all_files = source_files + test_files
        _materialize_files(workspace, all_files)

        # Discover where package.json actually is (#303) — don't assume a fixed dir.
        pkg_dir = _find_package_json_dir(all_files)
        if pkg_dir is None:
            return RunTestsResult(
                executed=False,
                error="No package.json found — cannot run vitest",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )
        cwd = os.path.join(workspace, pkg_dir) if pkg_dir else workspace

        # npm install
        try:
            install_proc = await asyncio.create_subprocess_exec(
                "npm",
                "install",
                "--no-audit",
                "--no-fund",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(
                    install_proc.communicate(),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                install_proc.kill()
                await install_proc.wait()
                return RunTestsResult(
                    executed=False,
                    error=f"npm install timed out after {timeout_seconds}s",
                    test_file_count=len(test_files),
                    source_file_count=len(source_files),
                )

            if install_proc.returncode != 0:
                return RunTestsResult(
                    executed=False,
                    error="npm install failed (dependency resolution error)",
                    test_file_count=len(test_files),
                    source_file_count=len(source_files),
                )
        except FileNotFoundError:
            return RunTestsResult(
                executed=False,
                error="npm not found — Node.js is not installed",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        # npx vitest run. The JSON reporter writes the machine report to a file while
        # verbose keeps stdout human-shaped — the suite-health markers (#626) and the
        # report readers both stay fed. A missing/unwritable report degrades to
        # test_failures=() (SIP-0104 P5: observation is additive, never load-bearing).
        report_path = os.path.join(cwd, _VITEST_REPORT_FILENAME)
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx",
                "vitest",
                "run",
                "--reporter=verbose",
                "--reporter=json",
                f"--outputFile.json={report_path}",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return RunTestsResult(
                executed=False,
                error="npx not found — Node.js is not installed",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        try:
            raw_stdout, raw_stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return RunTestsResult(
                executed=False,
                error=f"vitest timed out after {timeout_seconds}s",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        stdout = raw_stdout.decode(errors="replace")[:_STDOUT_LIMIT]
        stderr = raw_stderr.decode(errors="replace")[:_STDOUT_LIMIT]

        report = _read_vitest_report(report_path)
        failure_rows = parse_vitest_failure_rows(report, cwd) if report else []
        uncollected = (
            uncollected_test_files(report, cwd, [f["path"] for f in test_files]) if report else []
        )
        if uncollected:
            logger.warning(
                "vitest collected no suite for %d handed-in test file(s): %s — these "
                "verify nothing while the collected suites read green",
                len(uncollected),
                ", ".join(uncollected),
            )

        exit_code = proc.returncode or 0
        return RunTestsResult(
            executed=True,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            test_file_count=len(test_files),
            source_file_count=len(source_files),
            runner="vitest",
            # vitest cannot speak suite-health through exit codes (everything
            # is 1) — classify from output signatures instead (#626; pf-53's
            # "No test suite found" routed repairs to dev for a defect in the
            # qa role's own file).
            suite_broken=_vitest_suite_broken(exit_code, stdout, stderr),
            test_failures=tuple(failure_rows),
            uncollected_test_files=tuple(uncollected),
        )

    except Exception as exc:
        logger.warning("Node test runner error: %s", exc, exc_info=True)
        return RunTestsResult(
            executed=False,
            error=str(exc),
            test_file_count=len(test_files),
            source_file_count=len(source_files),
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


@dataclass(frozen=True)
class BuildCheckResult:
    """Outcome of a deliverable build/boot check (#276).

    ``ran`` is False when the check was skipped (no build script, no npm, or no
    frontend source) — a skip is not a failure. ``ok`` is True only when the
    check actually ran and succeeded.
    """

    ran: bool
    ok: bool = False
    exit_code: int = -1
    error: str = ""
    stderr: str = ""

    @property
    def failed(self) -> bool:
        """True only when the check ran and did not succeed (skips are not failures)."""
        return self.ran and not self.ok


async def run_frontend_build(
    source_files: list[dict[str, str]],
    target_dir: str | None = "frontend",
    timeout_seconds: int = 120,
) -> BuildCheckResult:
    """Verify the frontend actually builds (#276).

    Materializes the frontend source, ``npm install``s, then runs the package's
    ``build`` script (falling back to ``npx vite build``). Catches deliverables
    that pass vitest unit tests but cannot build — e.g. a Vite app missing its
    root ``index.html`` (observed in cyc_2f415e43f9cf: ``vite build`` failed
    immediately, yet the run shipped green).

    Skips (``ran=False``) when there is no frontend source at all, or Node is
    unavailable — a skip is never a failure. But frontend source present with no
    discoverable ``package.json`` is a BLOCKING failure (#303) — a frontend that
    can't build is broken, not absent. Never raises.
    """
    frontend_source = (
        [rec for rec in source_files if rec["path"].startswith(f"{target_dir}/")]
        if target_dir
        else source_files
    )
    if not frontend_source:
        return BuildCheckResult(ran=False, error="no frontend source")

    workspace = tempfile.mkdtemp(prefix="qa_build_")
    try:
        _materialize_files(workspace, frontend_source)
        # Discover the package.json dir (#303) — don't assume target_dir/package.json.
        pkg_dir = _find_package_json_dir(frontend_source)
        if pkg_dir is None:
            # Frontend source exists (checked above) but no package.json anywhere:
            # the deliverable can't build — a real failure, not a benign skip (#303).
            return BuildCheckResult(
                ran=True,
                ok=False,
                exit_code=1,
                error="frontend source present but no package.json found — cannot build",
            )
        cwd = os.path.join(workspace, pkg_dir) if pkg_dir else workspace
        pkg_path = os.path.join(cwd, "package.json")

        # Prefer the package's own build script; fall back to vite build.
        import json

        try:
            scripts = json.loads(open(pkg_path, encoding="utf-8").read()).get("scripts", {})
        except (OSError, ValueError):
            scripts = {}
        build_cmd = ["npm", "run", "build"] if "build" in scripts else ["npx", "vite", "build"]

        try:
            install = await asyncio.create_subprocess_exec(
                "npm",
                "install",
                "--no-audit",
                "--no-fund",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, inst_err = await asyncio.wait_for(install.communicate(), timeout=timeout_seconds)
            except TimeoutError:
                install.kill()
                await install.wait()
                return BuildCheckResult(
                    ran=False, error=f"npm install timed out after {timeout_seconds}s"
                )
            if install.returncode != 0:
                return BuildCheckResult(
                    ran=False,
                    error="npm install failed (dependency resolution) — cannot assess build",
                    stderr=inst_err.decode(errors="replace")[:_STDOUT_LIMIT],
                )
        except FileNotFoundError:
            return BuildCheckResult(ran=False, error="npm not found — Node.js not installed")

        try:
            proc = await asyncio.create_subprocess_exec(
                *build_cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return BuildCheckResult(
                ran=False, error=f"{build_cmd[0]} not found — Node.js not installed"
            )

        try:
            _, raw_stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return BuildCheckResult(ran=False, error=f"build timed out after {timeout_seconds}s")

        exit_code = proc.returncode or 0
        return BuildCheckResult(
            ran=True,
            ok=exit_code == 0,
            exit_code=exit_code,
            stderr=raw_stderr.decode(errors="replace")[:_STDOUT_LIMIT],
            error="" if exit_code == 0 else f"frontend build failed (exit {exit_code})",
        )
    except Exception as exc:  # never raise — a runner error is a skip, not a failure
        logger.warning("Frontend build check error: %s", exc, exc_info=True)
        return BuildCheckResult(ran=False, error=str(exc))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


# Subprocess driver for run_backend_import_check (#276). Byte-compiling is not
# enough — the canonical bug (``backend/main.py`` using ``BaseModel`` without
# importing it) is a NameError that only surfaces when the module *body runs* —
# so this executes each delivered module via ``exec_module`` and writes, to the
# path in argv[1], a JSON verdict of which modules failed. A ModuleNotFoundError
# whose missing top-level module is not itself a delivered module is recorded as
# a dependency gap (the runner lacks the dep), not a deliverable failure, so a
# missing third-party never produces a false red. Output goes to a file, not
# stdout, so a module that prints on import can't corrupt the verdict.
_BACKEND_IMPORT_DRIVER = r"""
import importlib as _il, importlib.util as _u, json as _json, pathlib as _pl, sys as _sys

_out = _sys.argv[1]
_root = _pl.Path(".").resolve()
_delivered = {}
for _p in _root.rglob("*.py"):
    if "__pycache__" in _p.parts:
        continue
    _name = _p.name
    if _name.startswith("test_") or _name.endswith("_test.py") or _name == "conftest.py":
        continue
    _delivered[str(_p.relative_to(_root))] = _p
_stems = {_p.stem for _p in _delivered.values()}


def _qualified(_path):
    # #469: a module inside a package must be imported by its package-
    # qualified name — executing backend/main.py under a fake top-level
    # name breaks its relative imports ("no known parent package") and
    # false-reds correct code (attempt 3.12: pytest passed 4/4 three
    # times while this check failed the run). Returns
    # (module_name, package_base) or None for top-level files.
    if not (_path.parent / "__init__.py").exists():
        return None
    _parts = [] if _path.name == "__init__.py" else [_path.stem]
    _dir = _path.parent
    while (_dir / "__init__.py").exists() and _dir != _root:
        _parts.insert(0, _dir.name)
        _dir = _dir.parent
    if not _parts:
        return None
    return ".".join(_parts), str(_dir)


_failures, _assessed, _skipped = [], 0, []
for _rel, _path in sorted(_delivered.items()):
    _qual = _qualified(_path)
    try:
        if _qual is not None:
            _mod_name, _base = _qual
            if _base not in _sys.path:
                _sys.path.insert(0, _base)
            _il.import_module(_mod_name)
        else:
            _spec = _u.spec_from_file_location(
                "_qa_imp_" + _rel.replace("/", "_")[:-3], str(_path)
            )
            if _spec is None or _spec.loader is None:
                continue
            _mod = _u.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
        _assessed += 1
    except ModuleNotFoundError as _e:
        _missing = (getattr(_e, "name", "") or "").split(".")[0]
        if _missing and _missing in _stems:
            _failures.append({"module": _rel, "error": "ModuleNotFoundError: " + str(_e)})
        else:
            _skipped.append(_missing or _rel)
    except Exception as _e:
        _failures.append({"module": _rel, "error": type(_e).__name__ + ": " + str(_e)})

with open(_out, "w", encoding="utf-8") as _fh:
    _json.dump({"failures": _failures, "assessed": _assessed, "skipped_deps": sorted(set(_skipped))}, _fh)
"""


async def run_backend_import_check(
    source_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> BuildCheckResult:
    """Verify the delivered backend actually imports (#276).

    Executes each delivered backend Python module (everything not under
    ``frontend/``) in a subprocess, using the same ``PYTHONPATH`` model as the
    generated tests so sibling imports resolve. The canonical bug — a
    ``backend/main.py`` that references ``BaseModel`` without importing it —
    passes the (stubbed) generated suite but raises ``NameError`` here, exactly
    the ``cyc_2f415e43f9cf`` false-green. Complements ``compute_missing_required_files``
    (#291), which checks a required file is *present*; this checks it *runs*.

    A *skip* (``ran=False``) never fails: no backend Python source, a runner
    crash or timeout, or import failures that are only missing third-party
    dependencies not installed in the runner (not the deliverable's fault). A
    module that raises anything else — ``NameError``, ``SyntaxError``,
    ``ImportError`` of a delivered sibling — is a BLOCKING failure: a backend
    that can't import is broken, not absent. Never raises.
    """
    backend_py = [
        rec
        for rec in source_files
        if rec["path"].endswith(".py") and not rec["path"].startswith("frontend/")
    ]
    if not backend_py:
        return BuildCheckResult(ran=False, error="no backend Python source")

    workspace = tempfile.mkdtemp(prefix="qa_import_")
    try:
        _materialize_files(workspace, backend_py)
        outfile = os.path.join(workspace, "__qa_import_result.json")
        env = {**os.environ, "PYTHONPATH": _source_dir_pythonpath(workspace, backend_py)}
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                _BACKEND_IMPORT_DRIVER,
                outfile,
                cwd=workspace,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return BuildCheckResult(ran=False, error="python interpreter not found")

        try:
            _, raw_err = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return BuildCheckResult(
                ran=False, error=f"backend import check timed out after {timeout_seconds}s"
            )

        import json

        try:
            with open(outfile, encoding="utf-8") as fh:
                report = json.load(fh)
        except (OSError, ValueError):
            # Driver never wrote a verdict (hard crash / segfault / sys.exit on
            # import): can't assess, so skip rather than fabricate a failure.
            logger.warning(
                "backend import check produced no result; stderr: %s",
                raw_err.decode(errors="replace")[:500],
            )
            return BuildCheckResult(ran=False, error="backend import check produced no result")

        failures = report.get("failures", [])
        if failures:
            first = failures[0]
            return BuildCheckResult(
                ran=True,
                ok=False,
                exit_code=1,
                error=f"backend module {first['module']} failed to import: {first['error']}",
                stderr="\n".join(f"{f['module']}: {f['error']}" for f in failures)[:_STDOUT_LIMIT],
            )
        if not report.get("assessed"):
            skipped = ", ".join(report.get("skipped_deps", [])) or "unknown"
            return BuildCheckResult(
                ran=False, error=f"backend deps unavailable — cannot assess ({skipped})"
            )
        return BuildCheckResult(ran=True, ok=True, exit_code=0)
    except Exception as exc:  # never raise — a runner error is a skip, not a failure
        logger.warning("Backend import check error: %s", exc, exc_info=True)
        return BuildCheckResult(ran=False, error=str(exc))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


#: Where run_node_tests asks vitest's JSON reporter to write the machine report.
_VITEST_REPORT_FILENAME = ".vitest_report.json"


def failing_test_identities(test_failures) -> tuple[str, ...]:
    """Stable identities for the tests that failed — ``file::title``, sorted and deduped.

    **Identity only: no messages, no line numbers.** The correction signature's standing
    rule is that evidence text never alters identity, so a re-described identical failure
    still reads as a repeat. A suite-level row (the file died before any test ran) has no
    title and is identified by its file alone — a distinct and correct identity, since the
    whole file is what failed.
    """
    identities = set()
    for row in test_failures or ():
        if not isinstance(row, dict):
            continue
        file = str(row.get("file") or "")
        title = str(row.get("title") or "")
        if not file and not title:
            continue
        identities.add(f"{file}::{title}" if title else file)
    return tuple(sorted(identities))


def failed_tests_pass_row(result: RunTestsResult) -> dict:
    """The ``tests_pass`` check row for a failing run.

    One builder because there are two call sites (first pass and retest) that must not
    drift: #626 added ``runner``/``suite_broken`` to both by hand, and the next field
    added to only one of them is a silent, per-path behavior difference. Two seams, one
    fact — the class of bug this repo has paid for more than once.
    """
    return {
        "check": "tests_pass",
        "executed": result.executed,
        "exit_code": result.exit_code,
        "tests_passed": result.tests_passed,
        "passed": False,
        # #626: runner identity + the runner-neutral suite-health verdict, so locus
        # routing stops reading pytest exit semantics into vitest failures.
        "runner": result.runner,
        "suite_broken": result.suite_broken,
        # #878 (full): WHICH tests failed, so two different suite failures stop
        # collapsing into one aggregate signature. Empty for runners that produce no
        # machine report (pytest today) — the signature then falls back byte-identically
        # to the aggregate form.
        "failing_tests": failing_test_identities(result.test_failures),
    }


def parse_vitest_failure_rows(report: dict, workspace_root: str) -> list[dict]:
    """Per-failure observation rows from a vitest JSON report (SIP-0104 P5).

    One row per failed test — ``{file, title, messages, line, suite_level}`` with
    ``file`` workspace-relative — plus one ``suite_level`` row per suite that died
    before any test ran (unresolved import / transform crash). Pure, so the evidence
    pipeline's corpus runs against synthesized and captured reports alike.
    """
    from squadops.capabilities.handlers.scaffold_execution import _VITEST_STATUS_FAILED

    root = workspace_root.rstrip("/") + "/"
    rows: list[dict] = []
    for suite in report.get("testResults", ()):
        name = str(suite.get("name", ""))
        rel = name[len(root) :] if name.startswith(root) else name
        results = suite.get("assertionResults") or []
        if suite.get("status") == _VITEST_STATUS_FAILED and not results:
            rows.append(
                {
                    "file": rel,
                    "title": "",
                    "messages": [str(suite.get("message", ""))[:2000]],
                    "line": None,
                    "suite_level": True,
                }
            )
            continue
        for result in results:
            if result.get("status") != _VITEST_STATUS_FAILED:
                continue
            location = result.get("location") or {}
            rows.append(
                {
                    "file": rel,
                    "title": str(result.get("title", "")),
                    "messages": [str(m)[:2000] for m in (result.get("failureMessages") or [])],
                    "line": location.get("line"),
                    "suite_level": False,
                }
            )
    return rows


def _read_vitest_report(report_path: str) -> dict | None:
    import json

    try:
        with open(report_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def collected_files(report: dict, workspace_root: str) -> set[str]:
    """Workspace-relative paths of every suite the runner actually collected."""
    root = workspace_root.rstrip("/") + "/"
    names = {str(suite.get("name", "")) for suite in report.get("testResults", ())}
    return {name[len(root) :] if name.startswith(root) else name for name in names}


def uncollected_test_files(report: dict, workspace_root: str, handed_in: list[str]) -> list[str]:
    """Handed-in runnable suites the runner never collected (SIP-0104, roll 1).

    Silent non-collection is the #884 class one step down: not "no test files found"
    but "this one was ignored", which every other signal reports as green because the
    files that DID collect passed.

    A helper module beside the tests is legitimately uncollected; a file the harness
    collects by suffix (``JS_SUITE_SUFFIXES`` — vitest's vocabulary, declared once) never
    is. Until #1131 this read a ``.ts``-only copy of that list, so an ignored
    ``*.test.jsx`` on the React stack was never named.
    """
    collected = collected_files(report, workspace_root)
    return sorted(
        path for path in handed_in if path.endswith(JS_SUITE_SUFFIXES) and path not in collected
    )


_VITEST_SUITE_BROKEN_MARKERS = (
    "No test suite found",
    # #884: vitest's OTHER no-suite message — the include glob matched zero
    # files (suite emitted at an undiscoverable path). "No test suite found"
    # is a file that collects but contains no tests; missing either marker
    # sends a producing-role defect down the dev repair chain (roll 14
    # resume #4: a suite-placement failure became a dev rewrite of 7 app
    # files that shipped a compile break).
    "No test files found",
    "Failed to resolve import",
    "Failed to load",
    "Transform failed",
    "Cannot find module",
    "Error: Cannot find package",
)


def _vitest_suite_broken(exit_code: int, stdout: str, stderr: str) -> bool | None:
    """Runner-owned suite-health verdict for vitest (#626).

    True = the suite could not run (missing/unloadable/untransformable test
    modules — the authoring role's defect). False = tests executed and some
    failed (the subject's defect). None = ambiguous; the consumer falls back
    to legacy semantics (which route toward the dev chain, the conservative
    test-gaming direction).
    """
    if exit_code == 0:
        return False
    combined = stdout + "\n" + stderr
    if any(marker in combined for marker in _VITEST_SUITE_BROKEN_MARKERS):
        return True
    if re.search(r"Tests\s+\d+ failed", combined):
        return False
    return None


def _merged_exit_code(backend: RunTestsResult, frontend: RunTestsResult) -> int:
    """D13 merge: backend controls the combined outcome — *when it executed*.

    #501: the old fallback hardcoded exit 0 whenever the backend suite didn't
    execute, discarding the only evidence there was (a failing vitest run
    reported "all tests passed" while zero tests executed anywhere). When the
    frontend is the sole executed suite it controls; when nothing executed the
    result is not a pass — "0 tests ran" must never verify ``tests_pass``.
    """
    if backend.executed:
        return backend.exit_code
    if frontend.executed:
        return frontend.exit_code
    return -1


async def run_fullstack_tests(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> RunTestsResult:
    """Run both pytest (backend) and vitest (frontend) tests (D12).

    Splits files by path prefix (``backend/`` vs ``frontend/``), runs
    both test suites, and merges results per the V1 merge policy (D13):
    backend pytest controls pass/fail; frontend vitest is non-blocking.

    Returns a ``RunTestsResult`` — never raises.
    """
    # Split files by path prefix
    backend_source, frontend_source = [], []
    backend_tests, frontend_tests = [], []

    for rec in source_files:
        if rec["path"].startswith("frontend/"):
            frontend_source.append(rec)
        else:
            backend_source.append(rec)

    for rec in test_files:
        if rec["path"].startswith("frontend/"):
            frontend_tests.append(rec)
        else:
            backend_tests.append(rec)

    # Run backend (pytest) — blocking
    backend_result = await run_generated_tests(
        backend_source,
        backend_tests,
        timeout_seconds=timeout_seconds,
    )

    # Run frontend (vitest) — non-blocking (D7, D13)
    frontend_result = await run_node_tests(
        frontend_source,
        frontend_tests,
        timeout_seconds=timeout_seconds,
    )

    # Merge results (D13): backend controls pass/fail
    combined_stdout_parts = []
    if backend_result.stdout:
        combined_stdout_parts.append(f"=== Backend (pytest) ===\n{backend_result.stdout}")
    if frontend_result.stdout:
        combined_stdout_parts.append(f"=== Frontend (vitest) ===\n{frontend_result.stdout}")

    combined_stderr_parts = []
    if backend_result.stderr:
        combined_stderr_parts.append(f"=== Backend (pytest) ===\n{backend_result.stderr}")
    if frontend_result.stderr:
        combined_stderr_parts.append(f"=== Frontend (vitest) ===\n{frontend_result.stderr}")

    combined_executed = backend_result.executed or frontend_result.executed
    combined_exit_code = _merged_exit_code(backend_result, frontend_result)

    # Build combined error
    error_parts = []
    if backend_result.error:
        error_parts.append(f"backend: {backend_result.error}")
    if frontend_result.error:
        error_parts.append(f"frontend (non-blocking): {frontend_result.error}")

    # #626: the controlling side (D13 — backend when it executed, else the
    # frontend) supplies runner identity and the suite-health verdict.
    controlling = backend_result if backend_result.executed else frontend_result
    return RunTestsResult(
        executed=combined_executed,
        exit_code=combined_exit_code,
        runner=controlling.runner,
        suite_broken=controlling.suite_broken,
        test_failures=controlling.test_failures,
        uncollected_test_files=controlling.uncollected_test_files,
        stdout="\n\n".join(combined_stdout_parts)[:_STDOUT_LIMIT],
        stderr="\n\n".join(combined_stderr_parts)[:_STDOUT_LIMIT],
        error="; ".join(error_parts) if error_parts else "",
        test_file_count=backend_result.test_file_count + frontend_result.test_file_count,
        source_file_count=backend_result.source_file_count + frontend_result.source_file_count,
    )


def _effective_sources(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
) -> list[dict[str, str]]:
    """The deliverable as the suite actually saw it — patches overlay by path.

    **Why this exists.** On the retest path the two inputs come from different eras.
    ``source_files`` is read from the FAILED task's envelope (``correction_runner``:
    ``failed_inputs = envelope.inputs``), so it is *pre-repair*; ``test_files`` carries
    the patched artifacts, and after a development repair those are the repaired
    **application** files, handed through as test files.

    The suite therefore ran against the repaired code while the build checks compiled
    the stale set — so a correction could regress the build and the verdict could not
    see it. Diagnostic ``cyc_831dfe6ac551`` (2026-08-16): the repair rewrote a page into
    something that does not typecheck, ``tests_pass`` and ``frontend_build`` both went
    green, and the delivered app did not compile.

    Overlay only where a patch occupies an existing source path. A test file at a test
    path is not part of the deliverable and does not belong in the build's input —
    widening this to the full union would change what the build compiles, which is a
    separate decision (see #939 on typechecking emitted tests).
    """
    by_path: dict[str, dict[str, str]] = {rec["path"]: rec for rec in source_files}
    for rec in test_files:
        if rec["path"] in by_path:
            by_path[rec["path"]] = rec
    return list(by_path.values())


async def run_build_validation(
    test_framework: str,
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> RunTestsResult:
    """Run the framework-appropriate test suite plus build/boot checks, as one result.

    Single entry point that owns all test-framework dispatch (pytest / vitest /
    both) and the #276 deliverable checks — the frontend *build* check and the
    backend *import* check — so callers stay framework-agnostic.

    A build/boot *failure* is BLOCKING (a non-building frontend or a non-importing
    backend is broken) even where unit tests passed and are otherwise non-blocking
    (D13). A *skip* — no frontend/backend source, no ``package.json``, no Node, or
    a missing third-party dep the runner lacks — never turns a passing suite red.
    Returns a ``RunTestsResult`` — never raises.
    """
    from squadops.capabilities.dev_capabilities import (
        TEST_FRAMEWORK_BOTH,
        TEST_FRAMEWORK_VITEST,
    )

    if test_framework == TEST_FRAMEWORK_VITEST:
        result = await run_node_tests(source_files, test_files, timeout_seconds=timeout_seconds)
        frontend_target: str | None = None
        run_frontend, run_backend = True, False
    elif test_framework == TEST_FRAMEWORK_BOTH:
        result = await run_fullstack_tests(
            source_files, test_files, timeout_seconds=timeout_seconds
        )
        frontend_target = "frontend"
        run_frontend, run_backend = True, True
    else:
        # pytest / backend-only: no frontend to build, but the backend must import
        result = await run_generated_tests(
            source_files, test_files, timeout_seconds=timeout_seconds
        )
        frontend_target = None
        run_frontend, run_backend = False, True

    # The build checks judge the DELIVERABLE, so they must see it as the suite did.
    # Passing `source_files` here made both checks stale on the retest path.
    built_files = _effective_sources(source_files, test_files)

    checks: list[BuildCheckResult] = []
    frontend_check: BuildCheckResult | None = None
    if run_frontend:
        frontend_check = await run_frontend_build(
            built_files, target_dir=frontend_target, timeout_seconds=timeout_seconds
        )
        checks.append(frontend_check)
    if run_backend:
        checks.append(await run_backend_import_check(built_files, timeout_seconds=timeout_seconds))

    failed = [check for check in checks if check.failed]
    if failed:
        merged_error = "; ".join(
            part for part in (result.error, *(check.error for check in failed)) if part
        )
        result = replace(
            result,
            exit_code=result.exit_code or failed[0].exit_code or 1,
            error=merged_error,
        )
    # #407: attach the frontend build outcome distinctly (a skip is dropped by the
    # `failed` merge above, so qa.test can't otherwise see it). None ⇒ no frontend.
    if frontend_check is not None:
        result = replace(result, frontend_build=frontend_check)
    return result
