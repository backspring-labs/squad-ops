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


class TestEmissionShapeCapture:
    """#924 — what an LLM call emitted must be inspectable after the fact."""

    def test_the_three_diagnoses_are_distinguishable(self, caplog):
        """Bug caught: a failed emission leaves no trace, so its cause must be guessed.

        SIP-0104 window rolls 3 and 5 both ended with every scaffold slot unfilled and
        nothing recorded what the qa author emitted — fills are parsed and stripped
        before extraction, so a success leaves no artifact and a failure leaves nothing
        at all. Two wrong diagnoses were made from the result rather than the emission.

        These three shapes have opposite fixes and were indistinguishable from outside:
        emitted fills, emitted nothing while billing a full budget, emitted the wrong
        fence kind.
        """
        import logging

        from squadops.capabilities.handlers.cycle.base import _log_emission_shape

        with caplog.at_level(logging.INFO):
            _log_emission_shape("qa", "```fill:slot-a\nexpect(1).toBe(1)\n```", 413)
            _log_emission_shape("qa", "", 6866)
            _log_emission_shape("qa", "```typescript:__tests__/x.test.ts\nx\n```", 900)

        filled, empty, wrong_fence = (r.getMessage() for r in caplog.records[-3:])

        assert "'fill': 1" in filled
        # the signature of a reasoning channel eating the budget: billed, emitted nothing
        assert "chars=0" in empty and "completion_tokens=6866" in empty
        assert "'path': 1" in wrong_fence and "'fill': 0" in wrong_fence

    def test_a_head_sample_is_recorded_and_bounded(self, caplog):
        """A shape with no sample cannot distinguish "wrong fence" from "prose apology".
        Bounded because this runs on every call and must never persist a whole
        completion or its prompt material."""
        import logging

        from squadops.capabilities.handlers.cycle.base import _log_emission_shape

        with caplog.at_level(logging.INFO):
            _log_emission_shape("qa", "I cannot complete this task because " + "x" * 5000, 12)

        message = caplog.records[-1].getMessage()
        assert "I cannot complete this task" in message
        assert len(message) < 600

    def test_a_missing_completion_logs_nothing_rather_than_a_false_zero(self, caplog):
        """`None` means the call did not return content — distinct from an empty string,
        which means it returned nothing. Logging `chars=0` for both would erase the
        difference between a transport failure and an empty emission."""
        import logging

        from squadops.capabilities.handlers.cycle.base import _log_emission_shape

        with caplog.at_level(logging.INFO):
            _log_emission_shape("qa", None, None)

        assert not [r for r in caplog.records if "emission shape" in r.getMessage()]

    def test_the_shape_capture_is_wired_outside_the_observability_gate(self):
        """Bug caught: the helper exists and nothing calls it — or it is called from
        inside ``if llm_obs and context.correlation_context:``.

        Both were live while this was written. The first is the unwired-fix shape a
        pure-function test cannot see: a mutation deleting the call site passed every
        other test in this class. The second is worse — the capture would go silent in
        exactly the deployments without observability configured, which are the ones
        where an unexplained emission is hardest to diagnose.
        """
        import ast
        from pathlib import Path as _Path

        source = (
            _Path(__file__).resolve().parents[3]
            / "src/squadops/capabilities/handlers/cycle/base.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)

        call_lines = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_log_emission_shape"
        ]
        assert call_lines, "the emission-shape capture is defined but never called"

        gated: set[int] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
            if "llm_obs" not in names:
                continue
            for stmt in node.body:
                gated.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))

        inside = sorted(set(call_lines) & gated)
        assert not inside, (
            f"the capture is inside the observability gate at {inside} — it would go "
            f"silent wherever llm_observability is not configured"
        )

    def test_the_fill_seam_capture_is_wired_at_the_parse_site(self):
        """Bug caught: the one distinction that cannot be recovered afterwards.

        P3 renders a REJECTED fill as the same failing state as a MISSING one, so
        "emitted nothing", "emitted fills that were refused", and "emitted a file
        instead of fills" all present identically as unfilled slots. Window roll 5's
        cause could not be determined from its stored artifacts for exactly that reason
        — the shells were unfilled, and the zero-extraction guard stayed silent because
        something else parsed.

        Pinned at the parse site specifically: a capture placed after the merge would
        report the merged result, which is the thing that already loses the difference.
        """
        import ast
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[3]
            / "src/squadops/capabilities/handlers/cycle/qa_test.py"
        ).read_text(encoding="utf-8")

        assert "emission parse:" in source, "the fill-seam capture is gone"

        tree = ast.parse(source)
        parse_calls = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "parse_fill_emission"
        ]
        log_lines = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "info"
            and any(
                isinstance(a, ast.Constant) and "emission parse:" in str(a.value) for a in node.args
            )
        ]
        assert parse_calls and log_lines, "parse site or capture missing"
        assert min(log_lines) > min(parse_calls), (
            "the capture must follow the parse — before it, there is nothing to report"
        )
