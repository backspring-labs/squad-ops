"""Unit tests for Node.js test runner and fullstack test orchestrator (SIP-0072 Phase 3).

Tests run_node_tests() and run_fullstack_tests() with mocked subprocess
(npm/npx may not be available in CI).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadops.capabilities.handlers.test_runner import (
    RunTestsResult,
    run_fullstack_tests,
    run_node_tests,
)

pytestmark = [pytest.mark.domain_capabilities]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SOURCE_FILES = [
    {"path": "package.json", "content": '{"scripts": {}}'},
    {"path": "src/App.jsx", "content": "export default function App() {}"},
]

_TEST_FILES = [
    {"path": "src/App.test.jsx", "content": "test('renders', () => {})"},
]


def _make_proc_mock(returncode=0, stdout=b"1 passed", stderr=b""):
    """Create a mock async subprocess with communicate()."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ---------------------------------------------------------------------------
# run_node_tests — no test files
# ---------------------------------------------------------------------------


class TestRunNodeTestsNoFiles:
    async def test_no_test_files_returns_not_executed(self):
        result = await run_node_tests(_SOURCE_FILES, [])
        assert result.executed is False
        assert "no test files" in result.error


# ---------------------------------------------------------------------------
# run_node_tests — no package.json
# ---------------------------------------------------------------------------


class TestRunNodeTestsNoPackageJson:
    async def test_missing_package_json(self):
        # No package.json anywhere in the file set → discovery finds none → skip.
        result = await run_node_tests(
            [{"path": "src/App.jsx", "content": "export default function App() {}"}],
            _TEST_FILES,
        )
        assert result.executed is False
        assert "package.json" in result.error


# ---------------------------------------------------------------------------
# run_node_tests — Node not installed
# ---------------------------------------------------------------------------


class TestRunNodeTestsNodeNotInstalled:
    @patch("squadops.capabilities.handlers.test_runner._materialize_files")
    @patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("npm"))
    @patch("os.path.isfile", return_value=True)
    @patch("tempfile.mkdtemp", return_value="/tmp/qa_node_test")
    @patch("shutil.rmtree")
    async def test_npm_not_found(self, _rmtree, _mkdtemp, _isfile, _exec, _mat):
        result = await run_node_tests(_SOURCE_FILES, _TEST_FILES)
        assert result.executed is False
        assert "npm not found" in result.error


# ---------------------------------------------------------------------------
# run_node_tests — npm install failure
# ---------------------------------------------------------------------------


class TestRunNodeTestsNpmInstallFailure:
    @patch("squadops.capabilities.handlers.test_runner._materialize_files")
    @patch("os.path.isfile", return_value=True)
    @patch("tempfile.mkdtemp", return_value="/tmp/qa_node_test")
    @patch("shutil.rmtree")
    async def test_npm_install_fails(self, _rmtree, _mkdtemp, _isfile, _mat):
        failed_proc = _make_proc_mock(returncode=1)
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=failed_proc,
        ):
            result = await run_node_tests(_SOURCE_FILES, _TEST_FILES)
        assert result.executed is False
        assert "npm install failed" in result.error


# ---------------------------------------------------------------------------
# run_node_tests — successful vitest run
# ---------------------------------------------------------------------------


class TestRunNodeTestsSuccess:
    @patch("squadops.capabilities.handlers.test_runner._materialize_files")
    @patch("os.path.isfile", return_value=True)
    @patch("tempfile.mkdtemp", return_value="/tmp/qa_node_test")
    @patch("shutil.rmtree")
    async def test_vitest_passes(self, _rmtree, _mkdtemp, _isfile, _mat):
        install_proc = _make_proc_mock(returncode=0)
        vitest_proc = _make_proc_mock(
            returncode=0,
            stdout=b"1 passed",
            stderr=b"",
        )
        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return install_proc
            return vitest_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            result = await run_node_tests(_SOURCE_FILES, _TEST_FILES)

        assert result.executed is True
        assert result.exit_code == 0
        assert "1 passed" in result.stdout

    @patch("squadops.capabilities.handlers.test_runner._materialize_files")
    @patch("os.path.isfile", return_value=True)
    @patch("tempfile.mkdtemp", return_value="/tmp/qa_node_test")
    @patch("shutil.rmtree")
    async def test_vitest_fails(self, _rmtree, _mkdtemp, _isfile, _mat):
        install_proc = _make_proc_mock(returncode=0)
        vitest_proc = _make_proc_mock(
            returncode=1,
            stdout=b"1 failed",
            stderr=b"AssertionError",
        )
        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return install_proc
            return vitest_proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            result = await run_node_tests(_SOURCE_FILES, _TEST_FILES)

        assert result.executed is True
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# run_node_tests — timeout
# ---------------------------------------------------------------------------


class TestRunNodeTestsTimeout:
    @patch("squadops.capabilities.handlers.test_runner._materialize_files")
    @patch("os.path.isfile", return_value=True)
    @patch("tempfile.mkdtemp", return_value="/tmp/qa_node_test")
    @patch("shutil.rmtree")
    async def test_npm_install_timeout(self, _rmtree, _mkdtemp, _isfile, _mat):
        import asyncio

        proc = MagicMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        proc.kill = MagicMock()
        proc.wait = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=proc):
            # Use a very short timeout but we're mocking anyway
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                result = await run_node_tests(
                    _SOURCE_FILES,
                    _TEST_FILES,
                    timeout_seconds=1,
                )

        assert result.executed is False
        assert "timed out" in result.error


# ---------------------------------------------------------------------------
# run_node_tests — package.json discovery (#303, replaces the old target_dir path)
# ---------------------------------------------------------------------------


class TestRunNodeTestsDiscovery:
    @patch("squadops.capabilities.handlers.test_runner._materialize_files")
    @patch("tempfile.mkdtemp", return_value="/tmp/qa_node_test")
    @patch("shutil.rmtree")
    async def test_package_json_in_subdir_is_discovered(self, _rmtree, _mkdtemp, _mat):
        """package.json placed at frontend/src/ (not a fixed dir) is discovered and
        run, instead of being skipped as 'not found' (#303)."""
        install_proc = _make_proc_mock(returncode=0)
        vitest_proc = _make_proc_mock(returncode=0, stdout=b"1 passed")
        call_count = 0

        async def mock_exec(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return install_proc if call_count == 1 else vitest_proc

        source = [{"path": "frontend/src/package.json", "content": '{"scripts": {}}'}]
        tests = [{"path": "frontend/src/App.test.jsx", "content": "test('a', () => {})"}]
        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            result = await run_node_tests(source, tests)

        assert result.executed is True
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# run_fullstack_tests — D13 merge policy
# ---------------------------------------------------------------------------


_RUN_PYTEST_PATH = "squadops.capabilities.handlers.test_runner.run_generated_tests"
_RUN_NODE_PATH = "squadops.capabilities.handlers.test_runner.run_node_tests"

_BACKEND_PASS = RunTestsResult(
    executed=True,
    exit_code=0,
    stdout="backend ok",
    stderr="",
    test_file_count=2,
    source_file_count=3,
)
_BACKEND_FAIL = RunTestsResult(
    executed=True,
    exit_code=1,
    stdout="backend fail",
    stderr="AssertionError",
    test_file_count=2,
    source_file_count=3,
)
_FRONTEND_PASS = RunTestsResult(
    executed=True,
    exit_code=0,
    stdout="frontend ok",
    stderr="",
    test_file_count=1,
    source_file_count=2,
)
_FRONTEND_FAIL = RunTestsResult(
    executed=True,
    exit_code=1,
    stdout="frontend fail",
    stderr="vitest error",
    test_file_count=1,
    source_file_count=2,
)
_FRONTEND_NOT_RUN = RunTestsResult(
    executed=False,
    error="npm not found — Node.js is not installed",
    test_file_count=1,
    source_file_count=2,
)
_BACKEND_NOT_RUN = RunTestsResult(
    executed=False,
    error="no test files provided",
    test_file_count=0,
    source_file_count=3,
)


class TestFullstackTestsBothPass:
    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_PASS)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_PASS)
    async def test_both_pass(self, _mock_pytest, _mock_node):
        source = [
            {"path": "backend/main.py", "content": "pass"},
            {"path": "frontend/src/App.jsx", "content": "export default () => {}"},
        ]
        tests = [
            {"path": "backend/tests/test_main.py", "content": "def test(): pass"},
            {"path": "frontend/src/App.test.jsx", "content": "test('ok', () => {})"},
        ]
        result = await run_fullstack_tests(source, tests)
        assert result.executed is True
        assert result.exit_code == 0
        assert result.tests_passed is True
        assert "Backend (pytest)" in result.stdout
        assert "Frontend (vitest)" in result.stdout


class TestFullstackTestsD13MergePolicy:
    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_FAIL)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_PASS)
    async def test_vitest_fails_but_combined_passes(self, _mock_pytest, _mock_node):
        """D13: Frontend vitest failure is non-blocking."""
        result = await run_fullstack_tests(
            [{"path": "backend/main.py", "content": "pass"}],
            [{"path": "backend/tests/test_main.py", "content": "def test(): pass"}],
        )
        assert result.exit_code == 0  # Backend controls
        assert result.tests_passed is True

    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_PASS)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_FAIL)
    async def test_pytest_fails_combined_fails(self, _mock_pytest, _mock_node):
        """D13: Backend pytest failure controls combined result."""
        result = await run_fullstack_tests(
            [{"path": "backend/main.py", "content": "pass"}],
            [{"path": "backend/tests/test_main.py", "content": "def test(): pass"}],
        )
        assert result.exit_code == 1
        assert result.tests_passed is False

    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_NOT_RUN)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_PASS)
    async def test_vitest_not_run_combined_passes(self, _mock_pytest, _mock_node):
        """D7: Node.js unavailable does not fail the cycle."""
        result = await run_fullstack_tests(
            [{"path": "backend/main.py", "content": "pass"}],
            [{"path": "backend/tests/test_main.py", "content": "def test(): pass"}],
        )
        assert result.exit_code == 0
        assert "non-blocking" in result.error

    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_FAIL)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_NOT_RUN)
    async def test_backend_not_run_frontend_fail_combined_fails(self, _mock_pytest, _mock_node):
        """#501 — the shakedown-3 false green: backend never executed, frontend
        vitest exited 1, yet the merge hardcoded exit 0 and reported 'all tests
        passed'. The sole executed suite's failure must control."""
        result = await run_fullstack_tests(
            [{"path": "frontend/src/App.jsx", "content": "export default () => {}"}],
            [{"path": "frontend/src/App.test.jsx", "content": "test('ok', () => {})"}],
        )
        assert result.exit_code == 1
        assert result.tests_passed is False

    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_PASS)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_NOT_RUN)
    async def test_backend_not_run_frontend_pass_combined_passes(self, _mock_pytest, _mock_node):
        """#501 inverse guard: when the frontend is the only executed suite and it
        passed, the combined result is an honest pass (frontend controls)."""
        result = await run_fullstack_tests(
            [{"path": "frontend/src/App.jsx", "content": "export default () => {}"}],
            [{"path": "frontend/src/App.test.jsx", "content": "test('ok', () => {})"}],
        )
        assert result.exit_code == 0
        assert result.tests_passed is True

    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_NOT_RUN)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_NOT_RUN)
    async def test_neither_suite_executed_is_not_a_pass(self, _mock_pytest, _mock_node):
        """#501: zero tests executed anywhere must never read 'all tests passed' —
        tests_pass verifying on no evidence is the false-green class itself."""
        result = await run_fullstack_tests([], [])
        assert result.executed is False
        assert result.exit_code != 0
        assert result.tests_passed is False


class TestFullstackTestsFileSplit:
    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_PASS)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_PASS)
    async def test_files_split_by_prefix(self, mock_pytest, mock_node):
        source = [
            {"path": "backend/main.py", "content": "pass"},
            {"path": "frontend/src/App.jsx", "content": "export default () => {}"},
        ]
        tests = [
            {"path": "backend/tests/test_main.py", "content": "def test(): pass"},
            {"path": "frontend/src/App.test.jsx", "content": "test('ok', () => {})"},
        ]
        await run_fullstack_tests(source, tests)

        # Backend gets only backend files
        backend_source = mock_pytest.call_args[0][0]
        backend_tests = mock_pytest.call_args[0][1]
        assert all(r["path"].startswith("backend/") for r in backend_source)
        assert all(r["path"].startswith("backend/") for r in backend_tests)

        # Frontend gets only frontend files
        frontend_source = mock_node.call_args[0][0]
        frontend_tests = mock_node.call_args[0][1]
        assert all(r["path"].startswith("frontend/") for r in frontend_source)
        assert all(r["path"].startswith("frontend/") for r in frontend_tests)

    @patch(_RUN_NODE_PATH, return_value=_FRONTEND_PASS)
    @patch(_RUN_PYTEST_PATH, return_value=_BACKEND_PASS)
    async def test_combined_file_counts(self, _mock_pytest, _mock_node):
        result = await run_fullstack_tests(
            [
                {"path": "backend/main.py", "content": "pass"},
                {"path": "frontend/src/App.jsx", "content": "export default () => {}"},
            ],
            [
                {"path": "backend/tests/test_main.py", "content": "def test(): pass"},
                {"path": "frontend/src/App.test.jsx", "content": "test('ok', () => {})"},
            ],
        )
        # Counts are summed from both runners
        assert (
            result.test_file_count == _BACKEND_PASS.test_file_count + _FRONTEND_PASS.test_file_count
        )
        assert (
            result.source_file_count
            == _BACKEND_PASS.source_file_count + _FRONTEND_PASS.source_file_count
        )


# --------------------------------------------------------------------------- #
# test-authorship guard — bug caught: both night measurement rolls shipped only
# qa/test_smoke.js; pytest collected nothing (exit 5) and the failure surfaced
# at run end as an unexplained tests_pass red. The runner must refuse up front
# with a repair-precise reason.
# --------------------------------------------------------------------------- #

from squadops.capabilities.handlers.test_runner import run_generated_tests  # noqa: E402


async def test_js_only_suite_refused_with_authorship_reason():
    result = await run_generated_tests(
        [{"path": "backend/main.py", "content": "app = None"}],
        [{"path": "qa/test_smoke.js", "content": "console.log('hi')"}],
    )
    assert result.executed is False
    assert "no pytest-discoverable test files" in result.error
    assert "qa/test_smoke.js" in result.error
    assert result.tests_passed is False


async def test_misnamed_python_file_refused():
    result = await run_generated_tests(
        [{"path": "backend/main.py", "content": "app = None"}],
        [{"path": "tests/smoke.py", "content": "def test_x(): pass"}],
    )
    assert result.executed is False
    assert "test_*.py" in result.error


async def test_discoverable_pytest_file_still_runs():
    result = await run_generated_tests(
        [{"path": "backend/main.py", "content": "VALUE = 3"}],
        [{"path": "tests/test_value.py", "content": "def test_v():\n    assert 1 + 2 == 3\n"}],
    )
    assert result.executed is True
    assert result.exit_code == 0
