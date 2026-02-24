"""Test runner for QA build validation — executes LLM-generated test files.

Materialises source + test files into a temporary workspace and runs
test frameworks (pytest, vitest, or both) as subprocesses.  The result
is captured as a ``TestRunResult`` frozen dataclass that the QA handler
can attach as an artifact.

All exceptions are caught so that a test-runner failure never crashes
the handler — callers always get a ``TestRunResult``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_STDOUT_LIMIT = 64 * 1024  # 64 KB


@dataclass(frozen=True)
class TestRunResult:
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
) -> TestRunResult:
    """Run *test_files* against *source_files* in an isolated temp directory.

    Each element is ``{"path": "<relative>", "content": "<text>"}``.

    Returns a ``TestRunResult`` — never raises.
    """
    if not test_files:
        return TestRunResult(
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
            sys.executable, "-m", "pytest", ".", "--tb=short", "-q",
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            raw_stdout, raw_stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return TestRunResult(
                executed=False,
                error=f"pytest timed out after {timeout_seconds}s",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        stdout = raw_stdout.decode(errors="replace")[:_STDOUT_LIMIT]
        stderr = raw_stderr.decode(errors="replace")[:_STDOUT_LIMIT]

        return TestRunResult(
            executed=True,
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            test_file_count=len(test_files),
            source_file_count=len(source_files),
        )

    except Exception as exc:
        logger.warning("Test runner error: %s", exc, exc_info=True)
        return TestRunResult(
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
) -> TestRunResult:
    """Run vitest in a Node workspace (D6).

    Materializes files, runs ``npm install`` then ``npx vitest run``.
    *target_dir* is the subdirectory within the workspace where
    ``package.json`` lives (e.g., ``"frontend"`` for fullstack projects).

    Returns a ``TestRunResult`` — never raises.
    """
    if not test_files:
        return TestRunResult(
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
            return TestRunResult(
                executed=False,
                error=f"No package.json found in {target_dir or 'workspace root'}",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        # npm install
        try:
            install_proc = await asyncio.create_subprocess_exec(
                "npm", "install", "--no-audit", "--no-fund",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                await asyncio.wait_for(
                    install_proc.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                install_proc.kill()
                await install_proc.wait()
                return TestRunResult(
                    executed=False,
                    error=f"npm install timed out after {timeout_seconds}s",
                    test_file_count=len(test_files),
                    source_file_count=len(source_files),
                )

            if install_proc.returncode != 0:
                return TestRunResult(
                    executed=False,
                    error="npm install failed (dependency resolution error)",
                    test_file_count=len(test_files),
                    source_file_count=len(source_files),
                )
        except FileNotFoundError:
            return TestRunResult(
                executed=False,
                error="npm not found — Node.js is not installed",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        # npx vitest run
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "vitest", "run", "--reporter=verbose",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return TestRunResult(
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
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return TestRunResult(
                executed=False,
                error=f"vitest timed out after {timeout_seconds}s",
                test_file_count=len(test_files),
                source_file_count=len(source_files),
            )

        stdout = raw_stdout.decode(errors="replace")[:_STDOUT_LIMIT]
        stderr = raw_stderr.decode(errors="replace")[:_STDOUT_LIMIT]

        return TestRunResult(
            executed=True,
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            test_file_count=len(test_files),
            source_file_count=len(source_files),
        )

    except Exception as exc:
        logger.warning("Node test runner error: %s", exc, exc_info=True)
        return TestRunResult(
            executed=False,
            error=str(exc),
            test_file_count=len(test_files),
            source_file_count=len(source_files),
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


async def run_fullstack_tests(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    timeout_seconds: int = 60,
) -> TestRunResult:
    """Run both pytest (backend) and vitest (frontend) tests (D12).

    Splits files by path prefix (``backend/`` vs ``frontend/``), runs
    both test suites, and merges results per the V1 merge policy (D13):
    backend pytest controls pass/fail; frontend vitest is non-blocking.

    Returns a ``TestRunResult`` — never raises.
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
        backend_source, backend_tests, timeout_seconds=timeout_seconds,
    )

    # Run frontend (vitest) — non-blocking (D7, D13)
    frontend_result = await run_node_tests(
        frontend_source, frontend_tests,
        target_dir="frontend",
        timeout_seconds=timeout_seconds,
    )

    # Merge results (D13): backend controls pass/fail
    combined_stdout_parts = []
    if backend_result.stdout:
        combined_stdout_parts.append(
            f"=== Backend (pytest) ===\n{backend_result.stdout}"
        )
    if frontend_result.stdout:
        combined_stdout_parts.append(
            f"=== Frontend (vitest) ===\n{frontend_result.stdout}"
        )

    combined_stderr_parts = []
    if backend_result.stderr:
        combined_stderr_parts.append(
            f"=== Backend (pytest) ===\n{backend_result.stderr}"
        )
    if frontend_result.stderr:
        combined_stderr_parts.append(
            f"=== Frontend (vitest) ===\n{frontend_result.stderr}"
        )

    # D13: backend exit code controls combined outcome
    combined_executed = backend_result.executed or frontend_result.executed
    combined_exit_code = backend_result.exit_code if backend_result.executed else 0

    # Build combined error
    error_parts = []
    if backend_result.error:
        error_parts.append(f"backend: {backend_result.error}")
    if frontend_result.error:
        error_parts.append(f"frontend (non-blocking): {frontend_result.error}")

    return TestRunResult(
        executed=combined_executed,
        exit_code=combined_exit_code,
        stdout="\n\n".join(combined_stdout_parts)[:_STDOUT_LIMIT],
        stderr="\n\n".join(combined_stderr_parts)[:_STDOUT_LIMIT],
        error="; ".join(error_parts) if error_parts else "",
        test_file_count=backend_result.test_file_count + frontend_result.test_file_count,
        source_file_count=backend_result.source_file_count + frontend_result.source_file_count,
    )
