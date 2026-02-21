"""Test runner for QA build validation — executes LLM-generated pytest files.

Materialises source + test files into a temporary workspace and runs
``pytest`` as a subprocess.  The result is captured as a ``TestRunResult``
frozen dataclass that the QA handler can attach as an artifact.

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
