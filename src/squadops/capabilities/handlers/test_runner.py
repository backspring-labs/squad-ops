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

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pytest",
            ".",
            "--tb=short",
            "-q",
            cwd=workspace,
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
    target_dir: str | None = None,
    timeout_seconds: int = 60,
) -> RunTestsResult:
    """Run vitest in a Node workspace (D6).

    Materializes files, runs ``npm install`` then ``npx vitest run``.
    *target_dir* is the subdirectory within the workspace where
    ``package.json`` lives (e.g., ``"frontend"`` for fullstack projects).

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

        # Resolve cwd: workspace/target_dir if provided, else workspace
        cwd = os.path.join(workspace, target_dir) if target_dir else workspace

        # Check for package.json
        if not os.path.isfile(os.path.join(cwd, "package.json")):
            return RunTestsResult(
                executed=False,
                error=f"No package.json found in {target_dir or 'workspace root'}",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

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

    Skips (``ran=False``) when there is no frontend source, no ``package.json``,
    or Node is unavailable — a skip is never a failure. Never raises.
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
        cwd = os.path.join(workspace, target_dir) if target_dir else workspace

        pkg_path = os.path.join(cwd, "package.json")
        if not os.path.isfile(pkg_path):
            return BuildCheckResult(ran=False, error="no package.json — cannot build")

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
        target_dir="frontend",
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
    """Run the framework-appropriate test suite plus a build check, as one result.

    Single entry point that owns all test-framework dispatch (pytest / vitest /
    both) and the #276 frontend build check, so callers stay framework-agnostic.

    A frontend *build* failure is BLOCKING (a non-building app is broken) even
    where frontend unit tests are non-blocking (D13). A build *skip* — no
    frontend, no ``package.json``, or no Node — never fails. Returns a
    ``RunTestsResult`` — never raises.
    """
    from squadops.capabilities.dev_capabilities import (
        TEST_FRAMEWORK_BOTH,
        TEST_FRAMEWORK_VITEST,
    )

    if test_framework == TEST_FRAMEWORK_VITEST:
        result = await run_node_tests(source_files, test_files, timeout_seconds=timeout_seconds)
        build_target: str | None = None
    elif test_framework == TEST_FRAMEWORK_BOTH:
        result = await run_fullstack_tests(
            source_files, test_files, timeout_seconds=timeout_seconds
        )
        build_target = "frontend"
    else:
        # pytest / backend-only: nothing to build
        return await run_generated_tests(source_files, test_files, timeout_seconds=timeout_seconds)

    build = await run_frontend_build(
        source_files, target_dir=build_target, timeout_seconds=timeout_seconds
    )
    if build.failed:
        merged_error = "; ".join(part for part in (result.error, build.error) if part)
        result = replace(
            result,
            exit_code=result.exit_code or build.exit_code or 1,
            error=merged_error,
        )
    return result
