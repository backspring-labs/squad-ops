"""Unit tests for the QA test runner (real subprocess execution).

Tests ``RunTestsResult``, ``_materialize_files``, and ``run_generated_tests``
from ``squadops.capabilities.handlers.test_runner``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

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
        # #665: zero suite is an explicit own-artifact verdict, not ambiguity —
        # without it the locus classifier routed fay-13's missing suite to the
        # dev chain, which can never author the qa role's test files.
        assert result.suite_broken is True

    async def test_non_discoverable_files_carry_the_zero_suite_verdict(self):
        """fay-13's actual emission shape: a doc artifact rode as the only
        test-file candidate — nothing pytest can collect exists."""
        result = await run_generated_tests(
            source_files=[{"path": "main.py", "content": "x = 1"}],
            test_files=[{"path": "qa_handoff.md", "content": "# QA Handoff\n"}],
        )
        assert result.executed is False
        assert "no pytest-discoverable" in result.error
        assert result.suite_broken is True


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
        # #665 boundary: a timeout is env-ambiguous — it must NOT read as the
        # zero-suite own-artifact verdict.
        assert result.suite_broken is None


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


class TestVitestSuiteBroken:
    """#626: vitest speaks suite-health through output, not exit codes —
    misreading exit 1 as 'subject failed' routed pf-53's own-artifact defect
    (a comment-only test file) to the dev repair chain five times."""

    def test_no_test_suite_found_is_broken(self):
        from squadops.capabilities.handlers.test_runner import _vitest_suite_broken

        assert _vitest_suite_broken(1, "No test suite found in file x.test.jsx", "") is True

    def test_unresolvable_import_is_broken(self):
        from squadops.capabilities.handlers.test_runner import _vitest_suite_broken

        assert _vitest_suite_broken(1, "", "Error: Failed to resolve import '../Appp.jsx'") is True

    def test_no_test_files_found_is_broken(self):
        """#884: vitest's OTHER no-suite message — the include glob matched zero
        files. Roll 14 resume #4: the suite was emitted at an undiscoverable
        path, this marker was missing, suite_broken stayed None, and the
        placement defect routed to the dev chain — whose repair shipped a
        compile break that blocked the verdict."""
        from squadops.capabilities.handlers.test_runner import _vitest_suite_broken

        assert _vitest_suite_broken(1, "", "No test files found, exiting with code 1") is True

    def test_real_test_failures_are_not_broken(self):
        from squadops.capabilities.handlers.test_runner import _vitest_suite_broken

        out = " Test Files  1 failed (1)\n      Tests  3 failed | 2 passed (5)\n"
        assert _vitest_suite_broken(1, out, "") is False

    def test_exit_zero_is_not_broken(self):
        from squadops.capabilities.handlers.test_runner import _vitest_suite_broken

        assert _vitest_suite_broken(0, "Tests  5 passed", "") is False

    def test_unrecognized_failure_is_ambiguous(self):
        from squadops.capabilities.handlers.test_runner import _vitest_suite_broken

        assert _vitest_suite_broken(1, "something exploded", "") is None


class TestMergedRunnerIdentity:
    """#626: the combined D12 result carries the CONTROLLING side's runner
    identity and suite-health verdict (backend when it executed, else the
    frontend) — asserted through the real merge, not a re-derivation."""

    async def test_backend_controls_when_executed(self, monkeypatch):
        import squadops.capabilities.handlers.test_runner as tr

        async def _backend(*_a, **_k):
            return tr.RunTestsResult(executed=True, exit_code=2, runner="pytest", suite_broken=True)

        async def _frontend(*_a, **_k):
            return tr.RunTestsResult(
                executed=True, exit_code=1, runner="vitest", suite_broken=False
            )

        monkeypatch.setattr(tr, "run_generated_tests", _backend)
        monkeypatch.setattr(tr, "run_node_tests", _frontend)
        result = await tr.run_fullstack_tests(
            [{"path": "backend/a.py", "content": "x"}],
            [
                {"path": "backend/tests/test_a.py", "content": "x"},
                {"path": "frontend/src/__tests__/a.test.jsx", "content": "x"},
            ],
        )
        assert result.exit_code == 2
        assert result.runner == "pytest"
        assert result.suite_broken is True

    async def test_frontend_controls_when_backend_did_not_execute(self, monkeypatch):
        import squadops.capabilities.handlers.test_runner as tr

        async def _backend(*_a, **_k):
            return tr.RunTestsResult(executed=False, error="no test files provided")

        async def _frontend(*_a, **_k):
            return tr.RunTestsResult(executed=True, exit_code=1, runner="vitest", suite_broken=True)

        monkeypatch.setattr(tr, "run_generated_tests", _backend)
        monkeypatch.setattr(tr, "run_node_tests", _frontend)
        result = await tr.run_fullstack_tests(
            [], [{"path": "frontend/src/__tests__/a.test.jsx", "content": "x"}]
        )
        assert result.exit_code == 1
        assert result.runner == "vitest"
        assert result.suite_broken is True


class TestFailingTestIdentities:
    """#878 (full) — which tests failed, as a stable identity set."""

    def test_messages_and_lines_never_enter_the_identity(self):
        """The correction signature's standing rule is that evidence text never alters
        identity, so the same failure re-described (a different assertion message, a
        shifted line number) must still compare equal — otherwise every round looks
        like new work and termination can never fire on a genuinely stuck run.
        """
        from squadops.capabilities.handlers.test_runner import failing_test_identities

        first = failing_test_identities(
            [
                {
                    "file": "a.test.ts",
                    "title": "creates",
                    "messages": ["expected 500 to be 201"],
                    "line": 12,
                    "suite_level": False,
                }
            ]
        )
        second = failing_test_identities(
            [
                {
                    "file": "a.test.ts",
                    "title": "creates",
                    "messages": ["AssertionError: nope"],
                    "line": 44,
                    "suite_level": False,
                }
            ]
        )

        assert first == second == ("a.test.ts::creates",)

    def test_identities_are_sorted_deduped_and_suite_rows_use_the_file(self):
        """Order comes from the runner's report and must not affect comparison; a
        suite-level row has no title and is the file itself."""
        from squadops.capabilities.handlers.test_runner import failing_test_identities

        rows = [
            {"file": "b.test.ts", "title": "z", "suite_level": False},
            {"file": "a.test.ts", "title": "", "suite_level": True},
            {"file": "b.test.ts", "title": "z", "suite_level": False},
        ]

        assert failing_test_identities(rows) == ("a.test.ts", "b.test.ts::z")

    def test_junk_rows_are_dropped_rather_than_producing_empty_identities(self):
        """A malformed report must not inject a `::`-shaped phantom identity that
        would make two unrelated rounds compare equal."""
        from squadops.capabilities.handlers.test_runner import failing_test_identities

        assert failing_test_identities([{}, {"file": "", "title": ""}, "not-a-dict", None]) == ()
        assert failing_test_identities(None) == ()


class TestFailedTestsPassRow:
    def test_both_qa_seams_build_the_row_through_this_one_builder(self):
        """#626 added `runner`/`suite_broken` to two hand-written copies of this dict;
        a third field added to only one seam is a silent per-path behavior difference
        (first-pass vs retest). This pins that both call sites route through here.
        """
        import ast
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[3]
            / "src/squadops/capabilities/handlers/cycle/qa_test.py"
        ).read_text(encoding="utf-8")

        calls = sum(
            1
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "failed_tests_pass_row"
        )

        assert calls == 2, "both the first-pass and retest seams must use the shared builder"
        assert '"check": "tests_pass",' not in source, (
            "a hand-built tests_pass failure row reappeared — route it through "
            "failed_tests_pass_row so the two seams cannot drift"
        )

    def test_the_row_carries_the_failing_test_identities(self):
        from squadops.capabilities.handlers.test_runner import (
            RunTestsResult,
            failed_tests_pass_row,
        )

        row = failed_tests_pass_row(
            RunTestsResult(
                executed=True,
                exit_code=1,
                runner="vitest",
                suite_broken=False,
                test_failures=({"file": "a.test.ts", "title": "creates"},),
            )
        )

        assert row["failing_tests"] == ("a.test.ts::creates",)
        assert row["passed"] is False
        assert row["runner"] == "vitest"


# ---------------------------------------------------------------------------
# #1130: pytest's ``-q --tb=short`` text is its machine report
# ---------------------------------------------------------------------------

_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


def _stored_stdout(report_name: str) -> str:
    """The pytest block a stored ``test_report.md`` carries — the bytes the runner saw."""
    text = (_REPLAYS / report_name).read_text(encoding="utf-8")
    return text.split("## stdout", 1)[1].split("```")[1]


class TestParsePytestFailureRows:
    """Replayed against stored reports: the roll whose routing defect this fixes and the
    controls that must not read as suite defects. A parser tested on invented text
    would pass on text no roll ever produced."""

    def test_roll_3_yields_one_row_per_failed_test_with_the_raising_frame(self):
        from squadops.capabilities.handlers.test_runner import parse_pytest_failure_rows

        rows = parse_pytest_failure_rows(
            _stored_stdout("1-6-5-react-roll-3-round-0-test_report.md"),
            ["backend/tests/test_runs.py"],
        )

        assert [(r["title"], r["line"], r["exception"]) for r in rows] == [
            ("test_join_and_leave_run", 69, "TypeError"),
            ("test_empty_participant_name_on_leave", 149, "TypeError"),
            ("test_leave_unknown_participant", 167, "TypeError"),
        ]
        assert {r["file"] for r in rows} == {"backend/tests/test_runs.py"}
        assert all(r["suite_level"] is False for r in rows)
        # The only frame is the test's own — the harness raised while binding arguments.
        assert rows[0]["frames"] == [
            {"file": "backend/tests/test_runs.py", "line": 69, "func": "test_join_and_leave_run"}
        ]
        assert rows[0]["messages"] == [
            "TypeError: TestClient.delete() got an unexpected keyword argument 'json'"
        ]

    def test_a_path_printed_below_the_rootdir_resolves_to_the_handed_in_artifact(self):
        """1.6.6 roll 6 printed ``tests/test_runs.py`` (an emitted ``backend/pytest.ini``
        moved pytest's rootdir); the artifact is ``backend/tests/test_runs.py`` and the
        innermost frame is the application's — nine rows, none the suite's own."""
        from squadops.capabilities.handlers.test_runner import parse_pytest_failure_rows

        rows = parse_pytest_failure_rows(
            _stored_stdout("1-6-6-react-roll-6-round-0-test_report.md"),
            ["backend/tests/test_runs.py"],
        )

        assert len(rows) == 9
        assert {r["file"] for r in rows} == {"backend/tests/test_runs.py"}
        assert {r["exception"] for r in rows} == {"AttributeError"}
        assert {r["frames"][-1]["file"] for r in rows} == {"backend/routes.py"}
        assert rows[0]["frames"][0] == {
            "file": "backend/tests/test_runs.py",
            "line": 40,
            "func": "test_create_run_success",
        }

    def test_a_collection_error_is_one_suite_level_row_naming_the_file(self):
        from squadops.capabilities.handlers.test_runner import parse_pytest_failure_rows

        rows = parse_pytest_failure_rows(
            _stored_stdout("collection-error-cyc_1d2e21ab0cfb-test_report.md"),
            ["backend/tests/test_api.py"],
        )

        assert len(rows) == 1
        assert rows[0]["file"] == "backend/tests/test_api.py"
        assert rows[0]["title"] == ""
        assert rows[0]["suite_level"] is True
        assert rows[0]["line"] is None
        assert rows[0]["exception"] == "ModuleNotFoundError"
        assert rows[0]["frames"][-1] == {
            "file": "backend/tests/test_api.py",
            "line": 3,
            "func": "<module>",
        }

    def test_a_rewritten_assert_reads_as_an_assertion_error(self):
        from squadops.capabilities.handlers.test_runner import parse_pytest_failure_rows

        rows = parse_pytest_failure_rows(
            _stored_stdout("1-6-6-react-roll-6-assert-test_report.md"),
            ["backend/tests/test_runs.py"],
        )

        assert [(r["title"], r["line"], r["exception"]) for r in rows] == [
            ("test_join_run_duplicate_rejected", 165, "AssertionError")
        ]
        assert rows[0]["messages"][0] == "assert 200 == 409"

    @pytest.mark.parametrize(
        "stdout",
        ["", "........   [100%]\n11 passed in 0.05s\n", "no tests ran in 0.01s\n"],
    )
    def test_output_without_a_failure_section_yields_no_rows(self, stdout):
        from squadops.capabilities.handlers.test_runner import parse_pytest_failure_rows

        assert parse_pytest_failure_rows(stdout, ["backend/tests/test_runs.py"]) == []


class TestSuiteDefects:
    """Which failures the suite raised in its own frame before any application code ran —
    the routing signal. Over-attribution here sends an app defect to a test re-author
    (the test-gaming guard's failure mode), so every ambiguous shape must stay out."""

    def _rows(self, report_name: str, handed_in: str):
        from squadops.capabilities.handlers.test_runner import parse_pytest_failure_rows

        return parse_pytest_failure_rows(_stored_stdout(report_name), [handed_in])

    def test_roll_3s_binding_errors_at_the_harness_call_are_the_suites_own(self):
        from squadops.capabilities.handlers.test_runner import suite_defects

        rows = self._rows("1-6-5-react-roll-3-round-0-test_report.md", "backend/tests/test_runs.py")
        sources = [{"path": "backend/routes.py", "content": "def leave_run():\n    pass\n"}]

        assert suite_defects(rows, sources, "pytest") == [
            {
                "file": "backend/tests/test_runs.py",
                "title": title,
                "line": line,
                "exception": "TypeError",
                "message": (
                    "TypeError: TestClient.delete() got an unexpected keyword argument 'json'"
                ),
            }
            for title, line in [
                ("test_join_and_leave_run", 69),
                ("test_empty_participant_name_on_leave", 149),
                ("test_leave_unknown_participant", 167),
            ]
        ]

    @pytest.mark.parametrize(
        ("report_name", "handed_in", "why"),
        [
            (
                "1-6-6-react-roll-6-round-0-test_report.md",
                "backend/tests/test_runs.py",
                "the innermost frame is backend/routes.py — the app raised",
            ),
            (
                "collection-error-cyc_1d2e21ab0cfb-test_report.md",
                "backend/tests/test_api.py",
                "an import the app should satisfy stays ambiguous (the pf-35 lesson)",
            ),
            (
                "1-6-6-react-roll-6-assert-test_report.md",
                "backend/tests/test_runs.py",
                "an assertion is the suite judging the app",
            ),
        ],
    )
    def test_stored_controls_are_not_the_suites_own(self, report_name, handed_in, why):
        from squadops.capabilities.handlers.test_runner import suite_defects

        assert suite_defects(self._rows(report_name, handed_in), [], "pytest") == [], why

    def test_a_binding_error_into_a_callee_the_app_defines_stays_ambiguous(self):
        """``create_run(name=…)`` failing to bind may be the app's signature drifting
        from its declaration — the dev chain's question, not a test re-author's."""
        from squadops.capabilities.handlers.test_runner import (
            parse_pytest_failure_rows,
            suite_defects,
        )

        stdout = (
            "F\n"
            "=================================== FAILURES ===================================\n"
            "______________________________ test_direct_call ______________________________\n"
            "backend/tests/test_runs.py:12: in test_direct_call\n"
            "    create_run(name='x', pace=3)\n"
            "E   TypeError: create_run() got an unexpected keyword argument 'pace'\n"
            "=========================== short test summary info ============================\n"
            "FAILED backend/tests/test_runs.py::test_direct_call - TypeError: create_run()...\n"
            "1 failed in 0.01s\n"
        )
        rows = parse_pytest_failure_rows(stdout, ["backend/tests/test_runs.py"])
        app = [{"path": "backend/routes.py", "content": "def create_run(name):\n    ...\n"}]

        assert suite_defects(rows, [], "pytest") != []
        assert suite_defects(rows, app, "pytest") == []

    def test_a_name_error_in_the_test_module_is_the_suites_own(self):
        from squadops.capabilities.handlers.test_runner import (
            parse_pytest_failure_rows,
            suite_defects,
        )

        stdout = (
            "______________________________ test_uses_undefined ______________________________\n"
            "backend/tests/test_runs.py:30: in test_uses_undefined\n"
            "    assert created['id']\n"
            "E   NameError: name 'created' is not defined\n"
            "=========================== short test summary info ============================\n"
            "FAILED backend/tests/test_runs.py::test_uses_undefined - NameError: name 'cr...\n"
        )
        rows = parse_pytest_failure_rows(stdout, ["backend/tests/test_runs.py"])

        assert suite_defects(rows, [], "pytest") == [
            {
                "file": "backend/tests/test_runs.py",
                "title": "test_uses_undefined",
                "line": 30,
                "exception": "NameError",
                "message": "NameError: name 'created' is not defined",
            }
        ]

    def test_a_frame_below_the_test_is_not_the_suites_own(self):
        """The same binding error raised inside the frozen conftest's helper: the
        innermost frame is not the failing file, so the row is not the suite's."""
        from squadops.capabilities.handlers.test_runner import (
            parse_pytest_failure_rows,
            suite_defects,
        )

        stdout = (
            "______________________________ test_via_helper ______________________________\n"
            "backend/tests/test_runs.py:12: in test_via_helper\n"
            "    leave(client, 'Alice')\n"
            "backend/tests/conftest.py:40: in leave\n"
            "    return client.delete('/x', json={'name': name})\n"
            "E   TypeError: TestClient.delete() got an unexpected keyword argument 'json'\n"
        )
        rows = parse_pytest_failure_rows(
            stdout, ["backend/tests/test_runs.py", "backend/tests/conftest.py"]
        )

        assert rows[0]["file"] == "backend/tests/test_runs.py"
        assert rows[0]["frames"][-1]["file"] == "backend/tests/conftest.py"
        assert suite_defects(rows, [], "pytest") == []


class TestFailedTestsPassRowOwnership:
    def test_the_row_stamps_each_defect_with_the_stacks_ownership(self):
        """A defect in ``backend/tests/`` is the qa role's on the React stack; one in a
        file outside the namespace is not; and with no predicate nothing is — the
        conservative direction the locus classifier relies on."""
        from squadops.capabilities.handlers.test_runner import (
            RunTestsResult,
            failed_tests_pass_row,
        )
        from squadops.capabilities.scaffold import is_qa_test_path_for_stack

        defects = (
            {"file": "backend/tests/test_runs.py", "title": "t", "line": 1, "exception": "E"},
            {"file": "backend/routes_test.py", "title": "u", "line": 2, "exception": "E"},
        )
        result = RunTestsResult(
            executed=True, exit_code=1, runner="pytest", suite_broken=False, suite_defects=defects
        )

        stamped = failed_tests_pass_row(
            result, qa_owned=lambda p: is_qa_test_path_for_stack(p, "fullstack_fastapi_react")
        )
        assert [(d["file"], d["qa_owned"]) for d in stamped["suite_defects"]] == [
            ("backend/tests/test_runs.py", True),
            ("backend/routes_test.py", False),
        ]
        unstamped = failed_tests_pass_row(result)
        assert [d["qa_owned"] for d in unstamped["suite_defects"]] == [False, False]


# ---------------------------------------------------------------------------
# #1123: the failing cases the repair brief names
# ---------------------------------------------------------------------------


class TestParseVitestFailureText:
    """The text fallback for a missing JSON report, and the shape every stored
    ``test_report.md`` carries — replayed from the rolls #1123 was filed from."""

    def test_roll_6s_final_report_names_its_one_failing_case(self):
        from squadops.capabilities.handlers.test_runner import parse_vitest_failure_text

        rows = parse_vitest_failure_text(
            _stored_stdout("1-6-6-react-roll-6-frontend-final-test_report.md")
        )
        assert rows == [
            {
                "file": "src/__tests__/runs.test.jsx",
                "title": (
                    "RunDetailView > renders participant names and submits join with expected payload"
                ),
                "messages": ["expected undefined to be defined"],
                "line": None,
                "suite_level": False,
            }
        ]

    def test_the_shakeouts_four_dom_failures_are_four_rows_with_their_anchors_named(self):
        from squadops.capabilities.handlers.test_runner import parse_vitest_failure_text

        rows = parse_vitest_failure_text(
            _stored_stdout("1-6-5-react-shakeout-round-0-test_report.md")
        )
        assert [r["messages"][0] for r in rows] == [
            'Found multiple elements by: [data-testid="runs-view"]',
            'Unable to find an element by: [data-testid="create-run-error"]',
            'Found multiple elements by: [data-testid="create-run-title"]',
            'Found multiple elements by: [data-testid="join-name-input"]',
        ]
        assert {r["file"] for r in rows} == {"src/__tests__/runs.test.jsx"}
        assert rows[0]["title"].startswith("RunsListView > shows the empty state")

    @pytest.mark.parametrize(
        "stdout", ["", " ✓ src/x.test.ts > a > b\n Test Files  1 passed (1)\n"]
    )
    def test_a_green_report_yields_no_rows(self, stdout):
        from squadops.capabilities.handlers.test_runner import parse_vitest_failure_text

        assert parse_vitest_failure_text(stdout) == []


class TestFailingCases:
    def test_the_row_carries_each_case_with_its_first_message_bounded(self):
        from squadops.capabilities.handlers.test_runner import (
            RunTestsResult,
            failed_tests_pass_row,
        )

        rows = (
            {
                "file": "a.test.jsx",
                "title": "renders",
                "messages": ["x" * 500, "second"],
                "line": 12,
            },
            {"file": "a.test.jsx", "title": "", "messages": [], "line": None, "suite_level": True},
            {"file": "", "title": ""},
        )
        row = failed_tests_pass_row(
            RunTestsResult(executed=True, exit_code=1, runner="vitest", test_failures=rows)
        )
        assert row["failing_cases"] == [
            {"file": "a.test.jsx", "title": "renders", "line": 12, "message": "x" * 300},
            {"file": "a.test.jsx", "title": "", "line": None, "message": ""},
        ]

    def test_a_hundred_case_red_is_bounded(self):
        from squadops.capabilities.handlers.test_runner import failing_cases

        rows = [{"file": "a.test.jsx", "title": f"case {i}", "messages": ["m"]} for i in range(100)]
        assert len(failing_cases(rows)) == 40


class TestVitestOwnFrameShapes:
    """#1270: the own-frame classifier is per runner, and the vitest side had no shapes.

    The oracle is 1.7.1 React roll 4's own machine report: the roll's suite
    (`art_b119474ce8fa`) re-run against the roll's own views inside the deployed qa image,
    reproducing the three `TypeError`s at lines 108/124/182 exactly as the stored
    `test_report.md` (`art_ca049f81b1c7`) recorded them. The JSON report is the live path —
    the roll's own log says it was written — so that is what these read.
    """

    _REPORT = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "roll_replays"
        / ("1-7-1-react-roll-4-vitest-report.json")
    )
    _ROOT = "/tmp/roll4ws"
    _HANDED_IN = [
        "frontend/src/__tests__/harness.test.jsx",
        "frontend/src/__tests__/runs.test.jsx",
    ]
    _SUITE = "frontend/src/__tests__/runs.test.jsx"

    def _rows(self):
        import json

        from squadops.capabilities.handlers.test_runner import parse_vitest_failure_rows

        report = json.loads(self._REPORT.read_text(encoding="utf-8"))
        return parse_vitest_failure_rows(report, self._ROOT, self._HANDED_IN)

    def test_roll_4s_wrong_import_dies_in_the_suites_own_frame(self):
        """`userEvent` imported from `@testing-library/react` instead of
        `.../user-event`: the call dies at the suite's call site before any component
        method runs. R2 read this as falsified; the row matched neither pytest shape."""
        from squadops.capabilities.handlers.test_runner import suite_defects

        defects = suite_defects(self._rows(), [], "vitest")
        assert [(d["file"], d["line"], d["exception"]) for d in defects] == [
            (self._SUITE, 108, "TypeError"),
            (self._SUITE, 124, "TypeError"),
            (self._SUITE, 182, "TypeError"),
        ]

    def test_a_method_the_application_defines_stays_ambiguous(self):
        """The other half of the same JavaScript shape: `store.addParticipant is not a
        function` when the app forgot the export is the APP's defect, and must stay on the
        dev chain. Only the application's knowledge of the name separates the two."""
        from squadops.capabilities.handlers.test_runner import suite_defects

        rows = [
            {
                "file": self._SUITE,
                "title": "joins a run",
                "messages": ["TypeError: __vi_import_1__.store.addParticipant is not a function"],
                "line": None,
                "suite_level": False,
                "exception": "TypeError",
                "frames": [{"file": self._SUITE, "line": 40, "func": ""}],
            }
        ]
        app = [
            {
                "path": "frontend/src/store.js",
                "content": "export const store = {\n  addParticipant: (id, name) => null,\n}\n",
            }
        ]
        assert suite_defects(rows, [], "vitest") != []
        assert suite_defects(rows, app, "vitest") == []

    def test_a_jsx_attribute_is_not_a_definition_of_the_method(self):
        """The guard that decides the case above must not be satisfied by `type="text"`.
        The roll-4 views carry eleven of those, and a definition test that accepted one
        would leave `userEvent.type is not a function` attributed to the application —
        exactly the misrouting this fixes."""
        from squadops.capabilities.handlers.test_runner import suite_defects

        views = [
            {
                "path": "frontend/src/views/RunCreateView.jsx",
                "content": '<input type="text" data-testid="create-title" />\n',
            }
        ]
        defects = suite_defects(self._rows(), views, "vitest")
        assert len(defects) == 3

    def test_a_reference_error_is_javascripts_name_error(self):
        from squadops.capabilities.handlers.test_runner import suite_defects

        rows = [
            {
                "file": self._SUITE,
                "title": "renders",
                "messages": ["ReferenceError: renderWithRouter is not defined"],
                "line": None,
                "suite_level": False,
                "exception": "ReferenceError",
                "frames": [{"file": self._SUITE, "line": 12, "func": ""}],
            }
        ]
        assert [d["exception"] for d in suite_defects(rows, [], "vitest")] == ["ReferenceError"]

    def test_an_assertion_is_the_suite_judging_the_application(self):
        """The control: vitest's assertion diffs carry no stack, so no frame says the
        suite raised — and an assertion is the suite doing its job, not failing at it."""
        from squadops.capabilities.handlers.test_runner import suite_defects

        rows = [
            {
                "file": self._SUITE,
                "title": "creates a run",
                "messages": ["AssertionError: expected 500 to be 201 // Object.is equality"],
                "line": 21,
                "suite_level": False,
                "exception": "AssertionError",
                "frames": [],
            }
        ]
        assert suite_defects(rows, [], "vitest") == []

    def test_a_runner_with_no_declared_shapes_says_so(self, caplog):
        """A runner absent from the table produces no defects — which is what the vitest
        side silently did for a whole line. It is named in the log now."""
        from squadops.capabilities.handlers.test_runner import suite_defects

        with caplog.at_level("WARNING"):
            assert suite_defects(self._rows(), [], "jest") == []
        assert any("'jest'" in m or '"jest"' in m or "jest" in m for m in caplog.messages)

    def test_framework_frames_are_dropped_so_the_raising_frame_is_the_suites(self):
        """Roll 4's stacks are ten frames deep and nine are vitest's own runner. If those
        counted, `frames[-1]` would be a `node_modules` file and nothing would classify."""
        rows = self._rows()
        assert all(len(r["frames"]) == 1 for r in rows)
        assert all(r["frames"][-1]["file"] == self._SUITE for r in rows)

    def test_a_collected_suite_is_never_reported_uncollected(self):
        """Roll 4's stored report says `NOT COLLECTED (these ran nothing):
        frontend/src/__tests__/runs.test.jsx` about a suite that had just run six tests.
        vitest reports relative to `frontend/`, the handed-in paths are workspace-relative,
        and nothing resolved the two — so the analyzer's evidence carried a false claim on
        every React roll with a frontend suite."""
        import json

        from squadops.capabilities.handlers.test_runner import uncollected_test_files

        report = json.loads(self._REPORT.read_text(encoding="utf-8"))
        assert uncollected_test_files(report, self._ROOT, self._HANDED_IN) == []

    def test_a_genuinely_ignored_suite_is_still_named(self):
        """The control for the line above: resolution must not turn the signal off."""
        import json

        from squadops.capabilities.handlers.test_runner import uncollected_test_files

        report = json.loads(self._REPORT.read_text(encoding="utf-8"))
        handed_in = [*self._HANDED_IN, "frontend/src/__tests__/ignored.test.jsx"]
        assert uncollected_test_files(report, self._ROOT, handed_in) == [
            "frontend/src/__tests__/ignored.test.jsx"
        ]


class TestTheFullstackMergeKeepsBothSidesEvidence:
    """#1305: the merge dropped every `suite_defect`, so #1130 and #1270 were inert on the
    only stack that takes this path.

    Every existing test for the own-frame detectors calls `run_generated_tests` or
    `run_node_tests` directly. That is exactly why a merge which discards their output was
    never a failure — the guard has to be at the fullstack level, which is where the React
    stack actually runs.
    """

    async def _merge(self, monkeypatch, backend, frontend):
        from squadops.capabilities.handlers import test_runner as tr

        async def _be(*a, **k):
            return backend

        async def _fe(*a, **k):
            return frontend

        monkeypatch.setattr(tr, "run_generated_tests", _be)
        monkeypatch.setattr(tr, "run_node_tests", _fe)
        return await tr.run_fullstack_tests(
            [{"path": "backend/main.py", "content": ""}],
            [
                {"path": "backend/tests/test_runs.py", "content": ""},
                {"path": "frontend/src/__tests__/views.test.jsx", "content": ""},
            ],
        )

    def _result(self, runner, defect_file, failure_file, executed=True):
        from squadops.capabilities.handlers.test_runner import RunTestsResult

        return RunTestsResult(
            executed=executed,
            exit_code=1,
            runner=runner,
            suite_defects=(
                {"file": defect_file, "title": "t", "line": 1, "exception": "TypeError"},
            ),
            test_failures=({"file": failure_file, "title": "t"},),
            uncollected_test_files=(f"uncollected-{runner}",),
        )

    async def test_a_frontend_own_frame_defect_survives_a_backend_that_also_ran(self, monkeypatch):
        """The live shape: the backend suite runs, the frontend suite dies at its own call
        site, and the frontend defect is the one that decides who repairs it. Before this,
        the merge kept neither side's."""
        merged = await self._merge(
            monkeypatch,
            self._result("pytest", "backend/tests/test_runs.py", "backend/tests/test_runs.py"),
            self._result(
                "vitest",
                "frontend/src/__tests__/views.test.jsx",
                "frontend/src/__tests__/views.test.jsx",
            ),
        )
        files = [d["file"] for d in merged.suite_defects]
        assert "frontend/src/__tests__/views.test.jsx" in files
        assert "backend/tests/test_runs.py" in files
        assert len(merged.suite_defects) == 2

    async def test_the_frontend_failure_rows_reach_the_evidence_too(self, monkeypatch):
        """`test_failures` took the controlling side only, so a frontend failure was
        invisible whenever the backend had also executed. Non-blocking (D13) governs the
        verdict, not what is recorded."""
        merged = await self._merge(
            monkeypatch,
            self._result("pytest", "backend/tests/test_runs.py", "backend/tests/test_runs.py"),
            self._result(
                "vitest",
                "frontend/src/__tests__/views.test.jsx",
                "frontend/src/__tests__/views.test.jsx",
            ),
        )
        assert len(merged.test_failures) == 2
        assert len(merged.uncollected_test_files) == 2

    async def test_the_verdict_still_comes_from_the_controlling_side_alone(self, monkeypatch):
        """The half that must NOT change: D13 says the backend decides pass/fail and #626
        says one runner identity. Merging evidence must not merge the verdict."""
        backend = self._result("pytest", "backend/tests/test_runs.py", "backend/tests/test_runs.py")
        frontend = self._result(
            "vitest",
            "frontend/src/__tests__/views.test.jsx",
            "frontend/src/__tests__/views.test.jsx",
        )
        merged = await self._merge(monkeypatch, backend, frontend)
        assert merged.runner == "pytest", "the controlling side names the runner"
        assert merged.suite_broken == backend.suite_broken

    async def test_a_backend_that_did_not_run_leaves_the_frontend_controlling(self, monkeypatch):
        """The other branch of D13, so the merge is not just tested in one direction."""
        backend = self._result(
            "pytest", "backend/tests/test_runs.py", "backend/tests/test_runs.py", executed=False
        )
        frontend = self._result(
            "vitest",
            "frontend/src/__tests__/views.test.jsx",
            "frontend/src/__tests__/views.test.jsx",
        )
        merged = await self._merge(monkeypatch, backend, frontend)
        assert merged.runner == "vitest"
        assert len(merged.suite_defects) == 2, "evidence is still kept from both"
