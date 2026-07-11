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
import shutil
import sys
import tempfile
from dataclasses import dataclass, replace

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
    """Write ``[{"path": ..., "content": ...}, ...]`` into *workspace*."""
    for rec in files:
        dest = os.path.join(workspace, rec["path"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(rec["content"])


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
    """
    dirs = {
        os.path.dirname(os.path.join(workspace, rec["path"]))
        for rec in source_files
        if rec["path"].endswith(".py")
    }
    existing = os.environ.get("PYTHONPATH", "")
    parts = [workspace, *sorted(dirs)]
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
        return RunTestsResult(
            executed=False,
            error="no test files provided",
            test_file_count=0,
            source_file_count=len(source_files),
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

        return RunTestsResult(
            executed=True,
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            test_file_count=len(test_files),
            source_file_count=len(source_files),
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
        return RunTestsResult(
            executed=False,
            error="no test files provided",
            test_file_count=0,
            source_file_count=len(source_files),
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

        # npx vitest run
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx",
                "vitest",
                "run",
                "--reporter=verbose",
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

        return RunTestsResult(
            executed=True,
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            test_file_count=len(test_files),
            source_file_count=len(source_files),
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
import importlib.util as _u, json as _json, pathlib as _pl, sys as _sys

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

_failures, _assessed, _skipped = [], 0, []
for _rel, _path in sorted(_delivered.items()):
    _spec = _u.spec_from_file_location("_qa_imp_" + _rel.replace("/", "_")[:-3], str(_path))
    if _spec is None or _spec.loader is None:
        continue
    _mod = _u.module_from_spec(_spec)
    try:
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

    # D13: backend exit code controls combined outcome
    combined_executed = backend_result.executed or frontend_result.executed
    combined_exit_code = backend_result.exit_code if backend_result.executed else 0

    # Build combined error
    error_parts = []
    if backend_result.error:
        error_parts.append(f"backend: {backend_result.error}")
    if frontend_result.error:
        error_parts.append(f"frontend (non-blocking): {frontend_result.error}")

    return RunTestsResult(
        executed=combined_executed,
        exit_code=combined_exit_code,
        stdout="\n\n".join(combined_stdout_parts)[:_STDOUT_LIMIT],
        stderr="\n\n".join(combined_stderr_parts)[:_STDOUT_LIMIT],
        error="; ".join(error_parts) if error_parts else "",
        test_file_count=backend_result.test_file_count + frontend_result.test_file_count,
        source_file_count=backend_result.source_file_count + frontend_result.source_file_count,
    )


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

    checks: list[BuildCheckResult] = []
    if run_frontend:
        checks.append(
            await run_frontend_build(
                source_files, target_dir=frontend_target, timeout_seconds=timeout_seconds
            )
        )
    if run_backend:
        checks.append(await run_backend_import_check(source_files, timeout_seconds=timeout_seconds))

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
    return result
