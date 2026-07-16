"""Unit tests for the QA test runner (real subprocess execution).

Tests ``RunTestsResult``, ``_materialize_files``, and ``run_generated_tests``
from ``squadops.capabilities.handlers.test_runner``.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from squadops.capabilities.handlers.test_runner import (
    RunTestsResult,
    _materialize_files,
    run_generated_tests,
)

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# RunTestsResult properties
# ---------------------------------------------------------------------------


class TestRunTestsResultProperties:
    def test_summary_passed(self):
        r = RunTestsResult(executed=True, exit_code=0, test_file_count=2, source_file_count=3)
        assert "all tests passed" in r.summary
        assert "2 test file(s)" in r.summary
        assert "3 source file(s)" in r.summary

    def test_summary_failed(self):
        r = RunTestsResult(executed=True, exit_code=1, test_file_count=1, source_file_count=1)
        assert "tests failed" in r.summary
        assert "exit code 1" in r.summary

    def test_summary_not_run_with_error(self):
        r = RunTestsResult(executed=False, error="no test files provided")
        assert "tests not run" in r.summary
        assert "no test files" in r.summary

    def test_frozen(self):
        r = RunTestsResult(executed=True, exit_code=0)
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
    async def test_workspace_cleaned_up_after_run(self, monkeypatch):
        source = [{"path": "a.py", "content": "x = 1"}]
        tests = [{"path": "test_a.py", "content": "def test_a():\n    assert True\n"}]

        # Capture the exact workspace this run creates and assert it's gone.
        # (Globbing shared /tmp for qa_run_* is flaky under -n auto: a parallel
        # worker's in-flight workspace leaks into the assertion.)
        import tempfile

        created: list[str] = []
        real_mkdtemp = tempfile.mkdtemp

        def _capturing_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            created.append(path)
            return path

        monkeypatch.setattr(tempfile, "mkdtemp", _capturing_mkdtemp)
        await run_generated_tests(source, tests)

        assert created, "run_generated_tests did not create a workspace"
        assert all(not os.path.exists(p) for p in created)


class TestRunBuildValidationSurfacesFrontend:
    """#407: run_build_validation must attach the frontend BuildCheckResult to its
    RunTestsResult; the folded-away skip is exactly the #306 case qa.test needs."""

    async def test_fullstack_surfaces_frontend_skip(self, monkeypatch):
        from squadops.capabilities.dev_capabilities import TEST_FRAMEWORK_BOTH
        from squadops.capabilities.handlers import test_runner as tr

        async def _fullstack(*a, **k):
            return tr.RunTestsResult(executed=True, exit_code=0)

        async def _frontend(*a, **k):
            return tr.BuildCheckResult(ran=False, error="npm not found — Node.js not installed")

        async def _backend(*a, **k):
            return tr.BuildCheckResult(ran=True, ok=True)

        monkeypatch.setattr(tr, "run_fullstack_tests", _fullstack)
        monkeypatch.setattr(tr, "run_frontend_build", _frontend)
        monkeypatch.setattr(tr, "run_backend_import_check", _backend)

        result = await tr.run_build_validation(TEST_FRAMEWORK_BOTH, [], [])
        assert result.frontend_build is not None
        assert result.frontend_build.ran is False  # the skip is surfaced, not dropped

    async def test_pytest_run_has_no_frontend_build(self, monkeypatch):
        from squadops.capabilities.dev_capabilities import TEST_FRAMEWORK_PYTEST
        from squadops.capabilities.handlers import test_runner as tr

        async def _gen(*a, **k):
            return tr.RunTestsResult(executed=True, exit_code=0)

        async def _backend(*a, **k):
            return tr.BuildCheckResult(ran=True, ok=True)

        monkeypatch.setattr(tr, "run_generated_tests", _gen)
        monkeypatch.setattr(tr, "run_backend_import_check", _backend)

        result = await tr.run_build_validation(TEST_FRAMEWORK_PYTEST, [], [])
        assert result.frontend_build is None


# ---------------------------------------------------------------------------
# #454 — package dirs stay off PYTHONPATH (relative-import scaffolds)
# ---------------------------------------------------------------------------


class TestPackageRelativeImports:
    """#454: the fill-contract scaffold is a package (backend/__init__.py) whose
    modules use relative imports. Putting backend/ itself on PYTHONPATH made
    those modules importable as top-level, where `from .errors import X` dies —
    run_33640d896265's suite passed 35/35 yet exited 1 on exactly this."""

    _PKG_SOURCES = [
        {"path": "backend/__init__.py", "content": ""},
        {"path": "backend/errors.py", "content": "class ApiError(Exception):\n    pass\n"},
        {
            "path": "backend/routes.py",
            "content": "from .errors import ApiError\n\ndef ping():\n    return 'ok'\n",
        },
    ]

    async def test_package_relative_scaffold_tests_pass(self):
        tests = [
            {
                "path": "tests/test_routes.py",
                "content": (
                    "from backend.routes import ping\n\n"
                    "def test_ping():\n    assert ping() == 'ok'\n"
                ),
            },
        ]
        result = await run_generated_tests(self._PKG_SOURCES, tests)
        assert result.executed is True
        assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        assert result.tests_passed is True

    async def test_flat_layout_303_still_works(self):
        """The #303 case this fix must not regress: no __init__.py, test uses
        a bare `from main import app`-style import against a nested dir."""
        sources = [{"path": "backend/main.py", "content": "app = 'the-app'\n"}]
        tests = [
            {
                "path": "test_main.py",
                "content": "from main import app\n\ndef test_app():\n    assert app == 'the-app'\n",
            },
        ]
        result = await run_generated_tests(sources, tests)
        assert result.executed is True
        assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"

    def test_pythonpath_excludes_package_dirs(self, tmp_path):
        from squadops.capabilities.handlers.test_runner import (
            _materialize_files,
            _source_dir_pythonpath,
        )

        ws = str(tmp_path)
        _materialize_files(ws, self._PKG_SOURCES)
        path = _source_dir_pythonpath(ws, self._PKG_SOURCES)
        parts = path.split(os.pathsep)
        assert ws in parts
        assert str(tmp_path / "backend") not in parts  # package dir stays off

    def test_pythonpath_keeps_non_package_dirs(self, tmp_path):
        from squadops.capabilities.handlers.test_runner import (
            _materialize_files,
            _source_dir_pythonpath,
        )

        sources = [{"path": "backend/main.py", "content": "x = 1\n"}]
        ws = str(tmp_path)
        _materialize_files(ws, sources)
        path = _source_dir_pythonpath(ws, sources)
        assert str(tmp_path / "backend") in path.split(os.pathsep)  # #303 preserved
