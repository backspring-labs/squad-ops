"""Unit tests for the QA test runner (real subprocess execution).

Tests ``TestRunResult``, ``_materialize_files``, and ``run_generated_tests``
from ``squadops.capabilities.handlers.test_runner``.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from squadops.capabilities.handlers.test_runner import (
    TestRunResult,
    _materialize_files,
    run_generated_tests,
)

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# TestRunResult properties
# ---------------------------------------------------------------------------


class TestTestRunResultProperties:
    def test_summary_passed(self):
        r = TestRunResult(executed=True, exit_code=0, test_file_count=2, source_file_count=3)
        assert "all tests passed" in r.summary
        assert "2 test file(s)" in r.summary
        assert "3 source file(s)" in r.summary

    def test_summary_failed(self):
        r = TestRunResult(executed=True, exit_code=1, test_file_count=1, source_file_count=1)
        assert "tests failed" in r.summary
        assert "exit code 1" in r.summary

    def test_summary_not_run_with_error(self):
        r = TestRunResult(executed=False, error="no test files provided")
        assert "tests not run" in r.summary
        assert "no test files" in r.summary

    def test_frozen(self):
        r = TestRunResult(executed=True, exit_code=0)
        with pytest.raises(AttributeError):
            r.exit_code = 42  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _materialize_files
# ---------------------------------------------------------------------------


class TestMaterializeFiles:
    def test_flat_files(self):
        workspace = tempfile.mkdtemp(prefix="test_mat_")
        try:
            _materialize_files(
                workspace,
                [
                    {"path": "main.py", "content": "print('hi')"},
                    {"path": "helper.py", "content": "x = 1"},
                ],
            )
            assert os.path.isfile(os.path.join(workspace, "main.py"))
            assert os.path.isfile(os.path.join(workspace, "helper.py"))
            with open(os.path.join(workspace, "main.py")) as f:
                assert f.read() == "print('hi')"
        finally:
            import shutil

            shutil.rmtree(workspace)

    def test_nested_directories(self):
        workspace = tempfile.mkdtemp(prefix="test_mat_")
        try:
            _materialize_files(
                workspace,
                [
                    {"path": "pkg/__init__.py", "content": ""},
                    {"path": "pkg/core.py", "content": "val = 1"},
                    {"path": "tests/test_core.py", "content": "assert True"},
                ],
            )
            assert os.path.isfile(os.path.join(workspace, "pkg", "__init__.py"))
            assert os.path.isfile(os.path.join(workspace, "pkg", "core.py"))
            assert os.path.isfile(os.path.join(workspace, "tests", "test_core.py"))
        finally:
            import shutil

            shutil.rmtree(workspace)

    def test_multiple_files_same_dir(self):
        workspace = tempfile.mkdtemp(prefix="test_mat_")
        try:
            _materialize_files(
                workspace,
                [
                    {"path": "tests/test_a.py", "content": "a"},
                    {"path": "tests/test_b.py", "content": "b"},
                ],
            )
            assert os.path.isfile(os.path.join(workspace, "tests", "test_a.py"))
            assert os.path.isfile(os.path.join(workspace, "tests", "test_b.py"))
        finally:
            import shutil

            shutil.rmtree(workspace)


# ---------------------------------------------------------------------------
# run_generated_tests — real subprocess execution
# ---------------------------------------------------------------------------


class TestRunGeneratedTestsNoFiles:
    async def test_no_test_files_returns_not_executed(self):
        result = await run_generated_tests(
            source_files=[{"path": "main.py", "content": "x = 1"}],
            test_files=[],
        )
        assert result.executed is False
        assert "no test files" in result.error
        assert result.source_file_count == 1
        assert result.test_file_count == 0


class TestRunGeneratedTestsPassing:
    async def test_passing_tests(self):
        source = [{"path": "mylib.py", "content": "def add(a, b):\n    return a + b\n"}]
        tests = [
            {
                "path": "test_mylib.py",
                "content": (
                    "from mylib import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
                ),
            },
        ]
        result = await run_generated_tests(source, tests)
        assert result.executed is True
        assert result.exit_code == 0
        assert result.tests_passed is True
        assert result.test_file_count == 1
        assert result.source_file_count == 1
        assert "passed" in result.stdout.lower() or "1 passed" in result.stdout


class TestRunGeneratedTestsFailing:
    async def test_failing_tests(self):
        source = [{"path": "mylib.py", "content": "def add(a, b):\n    return a - b\n"}]
        tests = [
            {
                "path": "test_mylib.py",
                "content": (
                    "from mylib import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
                ),
            },
        ]
        result = await run_generated_tests(source, tests)
        assert result.executed is True
        assert result.exit_code != 0
        assert result.tests_passed is False


class TestRunGeneratedTestsImportError:
    async def test_import_error_gives_nonzero_exit(self):
        tests = [
            {
                "path": "test_bad.py",
                "content": (
                    "from nonexistent_module import Foo\n\ndef test_foo():\n    assert Foo()\n"
                ),
            },
        ]
        result = await run_generated_tests(source_files=[], test_files=tests)
        assert result.executed is True
        assert result.exit_code != 0


class TestRunGeneratedTestsPackageImport:
    async def test_package_import_works(self):
        """Source in a sub-package can be imported by test files."""
        source = [
            {"path": "mypkg/__init__.py", "content": ""},
            {"path": "mypkg/core.py", "content": "def greet():\n    return 'hi'\n"},
        ]
        tests = [
            {
                "path": "tests/test_core.py",
                "content": (
                    "from mypkg.core import greet\n\n"
                    "def test_greet():\n"
                    "    assert greet() == 'hi'\n"
                ),
            },
        ]
        result = await run_generated_tests(source, tests)
        assert result.executed is True
        assert result.exit_code == 0
        assert result.tests_passed is True


class TestRunGeneratedTestsTimeout:
    async def test_timeout_returns_not_executed(self):
        tests = [
            {
                "path": "test_slow.py",
                "content": ("import time\n\ndef test_slow():\n    time.sleep(30)\n"),
            },
        ]
        result = await run_generated_tests(source_files=[], test_files=tests, timeout_seconds=2)
        assert result.executed is False
        assert "timed out" in result.error


class TestRunGeneratedTestsCleanup:
    async def test_workspace_cleaned_up_after_run(self):
        source = [{"path": "a.py", "content": "x = 1"}]
        tests = [{"path": "test_a.py", "content": "def test_a():\n    assert True\n"}]

        # We can't easily capture the workspace path, but we can verify
        # that repeated runs don't accumulate temp dirs (smoke test).
        import glob
        import tempfile

        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "qa_run_*")))
        await run_generated_tests(source, tests)
        after = set(glob.glob(os.path.join(tempfile.gettempdir(), "qa_run_*")))
        # No new dirs should remain
        assert after - before == set()
