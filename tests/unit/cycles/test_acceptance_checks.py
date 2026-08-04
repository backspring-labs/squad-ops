"""Tests for typed acceptance check evaluators (SIP-0092 M1.2).

Coverage:
- Per-check passed/failed/skipped/error matrix.
- Command safelist pattern matching (RC-10a).
- Safety boundary tests across check types: path traversal, absolute path,
  symlink escape, glob match cap.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from squadops.cycles.acceptance_check_spec import CHECK_SPECS, argv_matches_safelist
from squadops.cycles.acceptance_checks import (
    _CHECK_IMPLS,
    _resolve_interpreter,
    _safe_resolve,
    assert_registry_complete,
    get_check,
)

pytestmark = [pytest.mark.domain_contracts]


# ---------------------------------------------------------------------------
# Registry invariants
# ---------------------------------------------------------------------------


class TestRegistryInvariants:
    def test_every_spec_has_an_evaluator(self):
        # Module import already runs assert_registry_complete; calling again
        # is a no-op when the invariant holds.
        assert_registry_complete()
        assert set(CHECK_SPECS.keys()) == set(_CHECK_IMPLS.keys())

    def test_get_check_unknown_raises(self):
        with pytest.raises(KeyError):
            get_check("not_a_real_check")

    def test_evaluator_spec_back_reference(self):
        for name in CHECK_SPECS:
            evaluator = get_check(name)
            assert evaluator.spec is CHECK_SPECS[name]

    @pytest.mark.parametrize(
        "check_name",
        sorted(n for n, s in CHECK_SPECS.items() if s.applicable_extensions == frozenset({".py"})),
    )
    @pytest.mark.parametrize("target", ["view.jsx", "notes.md"])
    async def test_python_parsing_checks_skip_a_non_python_target(
        self, check_name, target, tmp_path
    ):
        """#605, pinned registry-wide rather than per-check.

        A Python-parsing check handed a non-Python file must *skip*. If it lets
        `ast.parse` raise, the check reports `error`, `patch_verification` maps
        that to `evaluator_error:<check>`, and the patch lands UNVERIFIABLE —
        neither accepted nor rejected. pf-41 lost a roll to exactly that (a
        `function_defined` aimed at a `.jsx`), and pf-40 is the control: same bad
        repairs, but verification returned a verdict and rejected them.

        The property held by construction and was asserted nowhere. Derived from
        `applicable_extensions` so a Python check added later inherits the test
        instead of quietly opting out of it.
        """
        (tmp_path / target).write_text("const App = () => <div/>;\n")
        params = dict(CHECK_SPECS[check_name].example) | {"file": target}

        result = await get_check(check_name).evaluate(params, tmp_path, stack="fastapi")

        assert result.status == "skipped", f"{check_name} -> {result.status} ({result.reason})"


# ---------------------------------------------------------------------------
# endpoint_defined
# ---------------------------------------------------------------------------


_FASTAPI_SOURCE = """
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()


@app.get("/users")
def list_users():
    return []


@router.post("/items/")
async def create_item():
    return {}


@app.delete("/users/{uid}")
def delete_user(uid: int):
    pass
"""


@pytest.fixture
def fastapi_workspace(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text(_FASTAPI_SOURCE)
    return tmp_path


class TestEndpointDefined:
    async def test_all_present_passed(self, fastapi_workspace):
        result = await get_check("endpoint_defined").evaluate(
            {
                "file": "main.py",
                "methods_paths": ["GET /users", "POST /items", "DELETE /users/{uid}"],
            },
            fastapi_workspace,
            stack="fastapi",
        )
        assert result.status == "passed"
        assert "GET /users" in result.actual["found"]
        assert "POST /items" in result.actual["found"]

    async def test_missing_one_failed(self, fastapi_workspace):
        result = await get_check("endpoint_defined").evaluate(
            {"file": "main.py", "methods_paths": ["GET /users", "PUT /users"]},
            fastapi_workspace,
            stack="fastapi",
        )
        assert result.status == "failed"
        assert result.actual["missing"] == ["PUT /users"]
        assert "GET /users" in result.actual["found"]

    async def test_stack_unset_skipped(self, fastapi_workspace):
        result = await get_check("endpoint_defined").evaluate(
            {"file": "main.py", "methods_paths": ["GET /users"]},
            fastapi_workspace,
            stack=None,
        )
        assert result.status == "skipped"
        assert result.reason == "unsupported_stack_or_syntax"

    async def test_other_stack_skipped(self, fastapi_workspace):
        result = await get_check("endpoint_defined").evaluate(
            {"file": "main.py", "methods_paths": ["GET /users"]},
            fastapi_workspace,
            stack="flask",
        )
        assert result.status == "skipped"

    async def test_missing_file_failed(self, fastapi_workspace):
        result = await get_check("endpoint_defined").evaluate(
            {"file": "does_not_exist.py", "methods_paths": ["GET /x"]},
            fastapi_workspace,
            stack="fastapi",
        )
        assert result.status == "failed"
        assert result.reason == "file_not_found"

    async def test_unparseable_python_error(self, tmp_path):
        (tmp_path / "broken.py").write_text("def @@@ broken syntax")
        result = await get_check("endpoint_defined").evaluate(
            {"file": "broken.py", "methods_paths": ["GET /x"]},
            tmp_path,
            stack="fastapi",
        )
        assert result.status == "error"
        assert result.reason == "parse_failed"

    async def test_malformed_methods_paths_error(self, fastapi_workspace):
        result = await get_check("endpoint_defined").evaluate(
            {"file": "main.py", "methods_paths": ["bogus token"]},
            fastapi_workspace,
            stack="fastapi",
        )
        assert result.status == "error"
        assert result.reason == "malformed_methods_paths"


# ---------------------------------------------------------------------------
# import_present
# ---------------------------------------------------------------------------


class TestImportPresent:
    @pytest.fixture
    def py_workspace(self, tmp_path):
        (tmp_path / "code.py").write_text(
            "import json\nfrom pathlib import Path, PurePath\nfrom os import getcwd as cwd\n"
        )
        return tmp_path

    async def test_module_present_passed(self, py_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "code.py", "module": "json"},
            py_workspace,
        )
        assert result.status == "passed"

    async def test_module_with_symbol_passed(self, py_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "code.py", "module": "pathlib", "symbol": "Path"},
            py_workspace,
        )
        assert result.status == "passed"

    async def test_module_present_symbol_missing_failed(self, py_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "code.py", "module": "pathlib", "symbol": "PosixPath"},
            py_workspace,
        )
        assert result.status == "failed"
        assert result.reason == "symbol_not_imported"

    async def test_module_missing_failed(self, py_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "code.py", "module": "ssh_keys"},
            py_workspace,
        )
        assert result.status == "failed"
        assert result.reason == "module_not_imported"

    @pytest.fixture
    def relative_import_workspace(self, tmp_path):
        (tmp_path / "routes.py").write_text(
            "from .errors import ApiError\nfrom ..pkg.util import helper\nfrom . import models\n"
        )
        return tmp_path

    async def test_relative_module_with_symbol_passed(self, relative_import_workspace):
        # #436 regression: ast stores the dot in `level`, so `from .errors
        # import ApiError` never matched spec module='.errors' — 13 identical
        # acceptance failures against correct code in run_39a3bca8746b.
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": ".errors", "symbol": "ApiError"},
            relative_import_workspace,
        )
        assert result.status == "passed"

    async def test_relative_module_level_two_passed(self, relative_import_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": "..pkg.util", "symbol": "helper"},
            relative_import_workspace,
        )
        assert result.status == "passed"

    async def test_from_dot_import_module_form_passed(self, relative_import_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": ".models"},
            relative_import_workspace,
        )
        assert result.status == "passed"

    async def test_relative_spec_rejects_absolute_import(self, tmp_path):
        # Exact-form matching is deliberate: `from backend.errors import X`
        # does not satisfy module='.errors' (documented in #436).
        (tmp_path / "routes.py").write_text("from backend.errors import ApiError\n")
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": ".errors", "symbol": "ApiError"},
            tmp_path,
        )
        assert result.status == "failed"
        assert result.reason == "module_not_imported"

    async def test_relative_module_wrong_symbol_failed(self, relative_import_workspace):
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": ".errors", "symbol": "NotThere"},
            relative_import_workspace,
        )
        assert result.status == "failed"
        assert result.reason == "symbol_not_imported"

    async def test_from_dot_import_does_not_bind_symbol(self, relative_import_workspace):
        # `from . import models` imports the module but binds no symbol from it.
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": ".models", "symbol": "RunEvent"},
            relative_import_workspace,
        )
        assert result.status == "failed"

    async def test_ts_extension_skipped(self, tmp_path):
        (tmp_path / "x.ts").write_text("import { foo } from 'bar';")
        result = await get_check("import_present").evaluate(
            {"file": "x.ts", "module": "bar"},
            tmp_path,
        )
        assert result.status == "skipped"
        assert result.reason == "frontend_acceptance_checks_disabled"

    async def test_unknown_extension_skipped(self, tmp_path):
        (tmp_path / "x.rb").write_text("require 'json'")
        result = await get_check("import_present").evaluate(
            {"file": "x.rb", "module": "json"},
            tmp_path,
        )
        assert result.status == "skipped"
        assert result.reason == "unsupported_file_extension"


# ---------------------------------------------------------------------------
# field_present
# ---------------------------------------------------------------------------


_PYDANTIC_MODEL = """
from pydantic import BaseModel, Field
from dataclasses import dataclass


class User(BaseModel):
    name: str
    age: int = Field(default=0)


@dataclass
class Item:
    sku: str
    qty: int = 1
"""


class TestFieldPresent:
    @pytest.fixture
    def models_workspace(self, tmp_path):
        (tmp_path / "models.py").write_text(_PYDANTIC_MODEL)
        return tmp_path

    async def test_all_fields_passed(self, models_workspace):
        result = await get_check("field_present").evaluate(
            {"file": "models.py", "class_name": "User", "fields": ["name", "age"]},
            models_workspace,
            stack="python",
        )
        assert result.status == "passed"

    async def test_dataclass_fields_passed(self, models_workspace):
        result = await get_check("field_present").evaluate(
            {"file": "models.py", "class_name": "Item", "fields": ["sku", "qty"]},
            models_workspace,
            stack="python",
        )
        assert result.status == "passed"

    async def test_partial_failed(self, models_workspace):
        result = await get_check("field_present").evaluate(
            {"file": "models.py", "class_name": "User", "fields": ["name", "email"]},
            models_workspace,
            stack="python",
        )
        assert result.status == "failed"
        assert result.actual["missing"] == ["email"]

    async def test_class_not_found_failed(self, models_workspace):
        result = await get_check("field_present").evaluate(
            {"file": "models.py", "class_name": "Ghost", "fields": ["x"]},
            models_workspace,
            stack="python",
        )
        assert result.status == "failed"
        assert result.reason == "class_not_found"

    async def test_stack_unset_skipped(self, models_workspace):
        result = await get_check("field_present").evaluate(
            {"file": "models.py", "class_name": "User", "fields": ["name"]},
            models_workspace,
            stack=None,
        )
        assert result.status == "skipped"


# ---------------------------------------------------------------------------
# function_defined
# ---------------------------------------------------------------------------


_TEST_SUITE_SOURCE = """
import pytest


def test_create():
    assert True


def test_list():
    assert True


async def test_async_flow():
    assert True


class TestDetail:
    def test_detail_view(self):
        assert True

    def helper_setup(self):
        return 1


def build_app():
    return None
"""


class TestFunctionDefined:
    @pytest.fixture
    def suite_workspace(self, tmp_path):
        (tmp_path / "test_runs.py").write_text(_TEST_SUITE_SOURCE)
        return tmp_path

    async def test_meets_min_count_passed(self, suite_workspace):
        # 4 `test_` functions: two top-level, one async, one method.
        result = await get_check("function_defined").evaluate(
            {"file": "test_runs.py", "name_prefix": "test_", "min_count": 3},
            suite_workspace,
            stack="python",
        )
        assert result.status == "passed"
        assert result.actual["matched_count"] == 4

    async def test_below_min_count_failed_and_counts_methods_and_async(self, suite_workspace):
        # Proves async defs and class methods are counted: the matched list is
        # exactly the four `test_` names, but the min of 5 is unmet.
        result = await get_check("function_defined").evaluate(
            {"file": "test_runs.py", "name_prefix": "test_", "min_count": 5},
            suite_workspace,
            stack="python",
        )
        assert result.status == "failed"
        assert result.reason == "function_count_below_minimum"
        assert result.actual["matched"] == [
            "test_async_flow",
            "test_create",
            "test_detail_view",
            "test_list",
        ]
        assert result.actual["matched_count"] == 4
        assert result.actual["min_count"] == 5

    async def test_default_min_count_is_one(self, suite_workspace):
        # No min_count → 1; a single matching def satisfies it.
        result = await get_check("function_defined").evaluate(
            {"file": "test_runs.py", "name_prefix": "build_"},
            suite_workspace,
            stack="python",
        )
        assert result.status == "passed"
        assert result.actual["matched_count"] == 1

    async def test_nonmatching_prefix_failed(self, suite_workspace):
        # Prefix specificity: `helper_setup` must NOT match `test_`, and a
        # prefix that matches nothing fails rather than erroring.
        result = await get_check("function_defined").evaluate(
            {"file": "test_runs.py", "name_prefix": "spec_", "min_count": 1},
            suite_workspace,
            stack="python",
        )
        assert result.status == "failed"
        assert result.actual["matched_count"] == 0

    async def test_file_not_found_failed(self, suite_workspace):
        result = await get_check("function_defined").evaluate(
            {"file": "missing.py", "name_prefix": "test_"},
            suite_workspace,
            stack="python",
        )
        assert result.status == "failed"
        assert result.reason == "file_not_found"

    async def test_syntax_error_is_error(self, tmp_path):
        (tmp_path / "broken.py").write_text("def test_x(:\n    pass\n")
        result = await get_check("function_defined").evaluate(
            {"file": "broken.py", "name_prefix": "test_"},
            tmp_path,
            stack="python",
        )
        assert result.status == "error"
        assert result.reason == "parse_failed"

    async def test_stack_unset_skipped(self, suite_workspace):
        result = await get_check("function_defined").evaluate(
            {"file": "test_runs.py", "name_prefix": "test_"},
            suite_workspace,
            stack=None,
        )
        assert result.status == "skipped"


# ---------------------------------------------------------------------------
# regex_match
# ---------------------------------------------------------------------------


class TestRegexMatch:
    @pytest.fixture
    def text_workspace(self, tmp_path):
        (tmp_path / "log.txt").write_text("ERROR: a\nERROR: b\nINFO: c\nERROR: d\n")
        return tmp_path

    async def test_meets_min_passed(self, text_workspace):
        result = await get_check("regex_match").evaluate(
            {"file": "log.txt", "pattern": r"ERROR:", "count_min": 2},
            text_workspace,
        )
        assert result.status == "passed"
        assert result.actual["match_count"] == 3

    async def test_default_count_min_one_passed(self, text_workspace):
        result = await get_check("regex_match").evaluate(
            {"file": "log.txt", "pattern": r"INFO"},
            text_workspace,
        )
        assert result.status == "passed"

    async def test_below_min_failed(self, text_workspace):
        result = await get_check("regex_match").evaluate(
            {"file": "log.txt", "pattern": r"ERROR:", "count_min": 10},
            text_workspace,
        )
        assert result.status == "failed"
        assert result.actual["match_count"] == 3

    async def test_invalid_regex_error(self, text_workspace):
        result = await get_check("regex_match").evaluate(
            {"file": "log.txt", "pattern": "((unclosed"},
            text_workspace,
        )
        assert result.status == "error"
        assert result.reason == "regex_invalid"

    async def test_oversized_pattern_error(self, text_workspace):
        result = await get_check("regex_match").evaluate(
            {"file": "log.txt", "pattern": "x" * 10_000},
            text_workspace,
        )
        assert result.status == "error"
        assert result.reason == "regex_pattern_too_large"

    async def test_oversized_input_error(self, tmp_path, monkeypatch):
        # Avoid actually allocating a 10MiB file by patching the cap.
        from squadops.cycles import acceptance_checks as ac

        big = tmp_path / "big.txt"
        big.write_text("x" * 1024)
        monkeypatch.setattr(ac, "DEFAULT_REGEX_INPUT_CAP_BYTES", 100)
        result = await get_check("regex_match").evaluate(
            {"file": "big.txt", "pattern": "x"},
            tmp_path,
        )
        assert result.status == "error"
        assert result.reason == "regex_input_too_large"


# ---------------------------------------------------------------------------
# count_at_least
# ---------------------------------------------------------------------------


class TestCountAtLeast:
    @pytest.fixture
    def files_workspace(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "d.py").write_text("")
        return tmp_path

    async def test_meets_min_passed(self, files_workspace):
        result = await get_check("count_at_least").evaluate(
            {"glob": "*.py", "min_count": 2},
            files_workspace,
        )
        assert result.status == "passed"
        assert result.actual["count"] == 2

    async def test_recursive_glob_passed(self, files_workspace):
        result = await get_check("count_at_least").evaluate(
            {"glob": "**/*.py", "min_count": 3},
            files_workspace,
        )
        assert result.status == "passed"
        assert result.actual["count"] == 3

    async def test_below_min_failed(self, files_workspace):
        result = await get_check("count_at_least").evaluate(
            {"glob": "*.py", "min_count": 10},
            files_workspace,
        )
        assert result.status == "failed"
        assert result.actual["count"] == 2

    async def test_traversal_error(self, files_workspace):
        result = await get_check("count_at_least").evaluate(
            {"glob": "../*", "min_count": 1},
            files_workspace,
        )
        assert result.status == "error"
        assert result.reason == "path_escapes_workspace"

    async def test_absolute_glob_error(self, files_workspace):
        result = await get_check("count_at_least").evaluate(
            {"glob": "/etc/*", "min_count": 1},
            files_workspace,
        )
        assert result.status == "error"
        assert result.reason == "path_escapes_workspace"

    async def test_cap_exceeded_error(self, tmp_path, monkeypatch):
        from squadops.cycles import acceptance_checks as ac

        for i in range(20):
            (tmp_path / f"f{i}.txt").write_text("")
        monkeypatch.setattr(ac, "DEFAULT_GLOB_MATCH_CAP", 5)
        result = await get_check("count_at_least").evaluate(
            {"glob": "*.txt", "min_count": 1},
            tmp_path,
        )
        assert result.status == "error"
        assert result.reason == "glob_match_cap_exceeded"


# ---------------------------------------------------------------------------
# command_exit_zero
# ---------------------------------------------------------------------------


class TestCommandExitZero:
    @pytest.fixture
    def py_workspace(self, tmp_path):
        (tmp_path / "ok.py").write_text("x = 1\n")
        (tmp_path / "broken.py").write_text("def @@@ ::: invalid\n")
        return tmp_path

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX subprocess assumed")
    async def test_absolute_interpreter_path_is_not_in_the_safelist(self, py_workspace):
        # The safelist patterns match the *authored name*, so a contract may not
        # smuggle in an arbitrary interpreter path. (#498 resolves the name to
        # sys.executable at spawn, strictly after this gate.)
        result = await get_check("command_exit_zero").evaluate(
            {"argv": [sys.executable, "-m", "py_compile", "ok.py"]},
            py_workspace,
        )
        assert result.status == "error"
        assert result.reason == "command_not_in_safelist"

    async def test_string_instead_of_list_error(self, py_workspace):
        result = await get_check("command_exit_zero").evaluate(
            {"argv": "python -m py_compile ok.py"},
            py_workspace,
        )
        assert result.status == "error"
        assert result.reason == "command_must_be_argv"

    async def test_empty_argv_error(self, py_workspace):
        result = await get_check("command_exit_zero").evaluate(
            {"argv": []},
            py_workspace,
        )
        assert result.status == "error"
        assert result.reason == "command_must_be_argv"

    async def test_non_string_elements_error(self, py_workspace):
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["python", 123]},
            py_workspace,
        )
        assert result.status == "error"
        assert result.reason == "command_must_be_argv"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX subprocess assumed")
    async def test_bare_python_runs_with_no_python_on_path(self, py_workspace, monkeypatch):
        """#498 verbatim: Ubuntu ships only /usr/bin/python3, so a bare `python`
        raised FileNotFoundError and `vc-*-compiles` degraded to
        skipped(missing_tooling) — a structural criterion silently not executing
        on a host detail, which is exactly what the bare-skeleton gate exists to
        rule out."""
        monkeypatch.setenv("PATH", "/nonexistent")

        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["python", "-m", "py_compile", "ok.py"]},
            py_workspace,
        )

        assert result.status == "passed"

    @pytest.mark.parametrize(
        ("argv", "rewritten"),
        [
            (["python", "-m", "py_compile", "x.py"], True),
            # Not authorable today (no python3 safelist pattern), so this is the
            # only place the branch is reachable — kept because a later safelist
            # entry would otherwise silently reintroduce the PATH dependency.
            (["python3", "-m", "py_compile", "x.py"], True),
            (["node", "--check", "x.js"], False),
            (["pyflakes", "x.py"], False),
            ([], False),
        ],
    )
    def test_only_bare_python_names_are_rewritten(self, argv, rewritten):
        resolved = _resolve_interpreter(argv)

        assert resolved == ([sys.executable, *argv[1:]] if rewritten else argv)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX subprocess assumed")
    async def test_resolved_interpreter_still_catches_bad_code(self, py_workspace, monkeypatch):
        """Guard against resolving the check into a no-op: it must still fail on
        code that does not compile, not just stop skipping."""
        monkeypatch.setenv("PATH", "/nonexistent")

        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["python", "-m", "py_compile", "broken.py"]},
            py_workspace,
        )

        assert result.status == "failed"

    async def test_a_non_interpreter_command_is_left_alone(self, tmp_path, monkeypatch):
        """Only bare python names are rewritten. A genuinely missing tool must
        still report the #462 environment gap under its *authored* name — an
        absolute path in the evidence can't be matched back to the contract."""
        monkeypatch.setenv("PATH", "/nonexistent")
        (tmp_path / "x.js").write_text("const a = 1;\n")

        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["node", "--check", "x.js"]},
            tmp_path,
        )

        assert result.status == "skipped"
        assert result.reason == "missing_tooling"
        assert result.actual["command"] == "node"

    async def test_resolution_never_precedes_the_safelist(self, py_workspace):
        """Ordering pin. The safelist gates the name a contract may ask for; if
        resolution ran first, argv[0] would already be an absolute path and no
        pattern would match — so either everything errors, or the gate has to be
        loosened to accept arbitrary interpreter paths."""
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["python", "-c", "import os; os.system('id')"]},
            py_workspace,
        )

        assert result.status == "error"
        assert result.reason == "command_not_in_safelist"

    async def test_safelist_run_passes(self, tmp_path):
        # Use /bin/true via a synthetic safelist entry — actually, the simpler
        # path is to test a real safelist match that produces zero exit.
        # `pyflakes ok.py` is in the safelist; test instead with a real
        # subprocess via the matched pattern. To avoid dep on pyflakes being
        # installed, we run the safelist-matcher directly here, then run a
        # known-good command via the safelist for end-to-end coverage.
        (tmp_path / "ok.py").write_text("x = 1\n")
        # pyflakes may not be installed; gate.
        import shutil

        if shutil.which("pyflakes") is None:
            pytest.skip("pyflakes not on PATH")
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["pyflakes", "ok.py"]},
            tmp_path,
        )
        assert result.status == "passed"

    async def test_safelist_run_fails(self, tmp_path):
        import shutil

        if shutil.which("pyflakes") is None:
            pytest.skip("pyflakes not on PATH")
        (tmp_path / "broken.py").write_text("import not_a_module\n")
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["pyflakes", "broken.py"]},
            tmp_path,
        )
        # pyflakes warns about the unused import → non-zero exit.
        assert result.status == "failed"
        assert "exit_code" in result.actual

    async def test_timeout_clamped_below_max(self, tmp_path, monkeypatch):
        # Verify the clamp logic works without invoking a real long process.

        captured: dict = {}

        async def fake_create_subprocess_exec(*argv, cwd, env, stdout, stderr):
            captured["argv"] = list(argv)

            class FakeProc:
                returncode = 0

                async def communicate(self):
                    return (b"", b"")

                def kill(self):
                    pass

                async def wait(self):
                    pass

            return FakeProc()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_create_subprocess_exec)
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["tsc", "--noEmit"], "timeout_s": 9999},
            tmp_path,
        )
        assert result.status == "passed"
        assert captured["argv"] == ["tsc", "--noEmit"]


# ---------------------------------------------------------------------------
# Command safelist pattern matching (RC-10a)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv,expected",
    [
        # Allowed shapes
        (["python", "-m", "py_compile", "backend/main.py"], True),
        (["python", "-m", "mypy", "src/"], True),
        (["python", "-m", "mypy", "--strict", "src/"], True),
        (["node", "--check", "app.js"], True),
        (["ruff", "check", "src/"], True),
        (["ruff", "check", "src/", "--select", "E"], True),
        (["tsc", "--noEmit"], True),
        (["eslint", "src/"], True),
        (["pyflakes", "main.py"], True),
        # Rejected shapes
        (["python", "-c", "print(1)"], False),
        (["python", "-m", "pip", "install", "anything"], False),
        (["python", "-m", "unknown_module"], False),
        (["python"], False),
        (["node", "-e", "console.log(1)"], False),
        (["pyflakes"], False),  # missing the file arg → not exact-then-one-path
        (["pyflakes", "a.py", "b.py"], False),  # exact-then-ONE-path
        (["bash", "-c", "echo hi"], False),
        (["sh", "echo hi"], False),
    ],
)
def test_argv_matches_safelist(argv, expected):
    assert argv_matches_safelist(argv) is expected


# ---------------------------------------------------------------------------
# Path safety (RC-10)
# ---------------------------------------------------------------------------


class TestSafeResolve:
    def test_traversal_rejected(self, tmp_path):
        with pytest.raises(Exception):  # _SafetyError, but it's module-private
            _safe_resolve("../etc/passwd", tmp_path)

    def test_absolute_rejected(self, tmp_path):
        with pytest.raises(Exception):
            _safe_resolve("/etc/passwd", tmp_path)

    def test_empty_rejected(self, tmp_path):
        with pytest.raises(Exception):
            _safe_resolve("", tmp_path)

    def test_relative_ok(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        resolved = _safe_resolve("f.txt", tmp_path)
        assert resolved == (tmp_path / "f.txt").resolve()

    def test_symlink_to_outside_rejected(self, tmp_path):
        outside = tmp_path.parent / "outside_target.txt"
        outside.write_text("secret")
        link = tmp_path / "evil"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported in this environment")
        with pytest.raises(Exception):
            _safe_resolve("evil", tmp_path)

    def test_symlink_inside_workspace_ok(self, tmp_path):
        target = tmp_path / "real.txt"
        target.write_text("ok")
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported in this environment")
        resolved = _safe_resolve("link.txt", tmp_path)
        assert resolved.is_relative_to(tmp_path.resolve())


# ---------------------------------------------------------------------------
# Cross-check safety boundary — every path-taking check rejects traversal/abs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "check_name,params",
    [
        ("endpoint_defined", {"file": "../escape.py", "methods_paths": ["GET /x"]}),
        ("import_present", {"file": "../escape.py", "module": "json"}),
        ("field_present", {"file": "../escape.py", "class_name": "X", "fields": ["a"]}),
        ("function_defined", {"file": "../escape.py", "name_prefix": "test_"}),
        ("regex_match", {"file": "../escape.py", "pattern": "x"}),
    ],
)
async def test_path_traversal_all_path_checks_error(check_name, params, tmp_path):
    stack = "fastapi" if check_name == "endpoint_defined" else "python"
    result = await get_check(check_name).evaluate(params, tmp_path, stack=stack)
    assert result.status == "error"
    assert result.reason == "path_escapes_workspace"


@pytest.mark.parametrize(
    "check_name,params",
    [
        ("endpoint_defined", {"file": "/etc/passwd", "methods_paths": ["GET /x"]}),
        ("import_present", {"file": "/etc/passwd", "module": "json"}),
        ("field_present", {"file": "/etc/passwd", "class_name": "X", "fields": ["a"]}),
        ("function_defined", {"file": "/etc/passwd", "name_prefix": "test_"}),
        ("regex_match", {"file": "/etc/passwd", "pattern": "x"}),
    ],
)
async def test_absolute_path_all_path_checks_error(check_name, params, tmp_path):
    stack = "fastapi" if check_name == "endpoint_defined" else "python"
    result = await get_check(check_name).evaluate(params, tmp_path, stack=stack)
    assert result.status == "error"
    assert result.reason == "path_escapes_workspace"


class TestCommandMissingTooling:
    """#462: a safelisted command whose binary is absent from the evaluating
    container (node --check on a dev task — Node is qa-only, #306) must skip,
    not error: an error blocks the task, fails correct code, and burns the
    run's shared correction budget on a check that can never pass there
    (attempt 3.9 lost all 3 corrections to it)."""

    async def test_missing_binary_skips_with_reason(self, tmp_path, monkeypatch):
        (tmp_path / "view.jsx").write_text("export default 1\n")

        async def _no_such_binary(*_a, **_k):
            raise FileNotFoundError(2, "No such file or directory: 'node'")

        monkeypatch.setattr(
            "squadops.cycles.acceptance_checks.asyncio.create_subprocess_exec",
            _no_such_binary,
        )
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["node", "--check", "view.jsx"]}, tmp_path
        )

        assert result.status == "skipped"
        assert result.reason == "missing_tooling"
        assert result.actual["command"] == "node"

    async def test_other_spawn_failures_still_error(self, tmp_path, monkeypatch):
        """Guard: only the missing-binary case is an environment gap; a
        permission failure is an evaluator fault and must stay blocking."""

        async def _denied(*_a, **_k):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(
            "squadops.cycles.acceptance_checks.asyncio.create_subprocess_exec",
            _denied,
        )
        result = await get_check("command_exit_zero").evaluate(
            {"argv": ["node", "--check", "view.jsx"]}, tmp_path
        )

        assert result.status == "error"
        assert result.reason == "command_spawn_failed"


class TestImportPresentDotlessLeniency:
    """#441: a dotless module spec matches a relative import of the same name.

    Attempt 3.5's framing authored `module: errors` for code using
    `from .errors import ApiError` — exact-form matching made the check
    unwinnable against correct code (the #436 class, from the spec side).
    """

    @pytest.fixture
    def relative_ws(self, tmp_path):
        (tmp_path / "routes.py").write_text("from .errors import ApiError\n")
        return tmp_path

    async def test_dotless_spec_matches_relative_import(self, relative_ws):
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": "errors", "symbol": "ApiError"},
            relative_ws,
        )
        assert result.status == "passed"

    async def test_dotless_spec_still_matches_absolute_import(self, tmp_path):
        (tmp_path / "app.py").write_text("from errors import ApiError\n")
        result = await get_check("import_present").evaluate(
            {"file": "app.py", "module": "errors", "symbol": "ApiError"},
            tmp_path,
        )
        assert result.status == "passed"

    async def test_dotted_spec_stays_exact_rejects_absolute(self, tmp_path):
        (tmp_path / "app.py").write_text("from backend.errors import ApiError\n")
        result = await get_check("import_present").evaluate(
            {"file": "app.py", "module": ".errors", "symbol": "ApiError"},
            tmp_path,
        )
        assert result.status == "failed"
        assert result.reason == "module_not_imported"

    async def test_dotless_spec_rejects_different_name(self, relative_ws):
        result = await get_check("import_present").evaluate(
            {"file": "routes.py", "module": "exceptions", "symbol": "ApiError"},
            relative_ws,
        )
        assert result.status == "failed"
        assert result.reason == "module_not_imported"

    async def test_dotless_spec_does_not_match_plain_import_of_submodule(self, tmp_path):
        # `import backend.errors` is alias 'backend.errors', not 'errors' —
        # dotless leniency applies only to relative ImportFrom nodes.
        (tmp_path / "app.py").write_text("import backend.errors\n")
        result = await get_check("import_present").evaluate(
            {"file": "app.py", "module": "errors"},
            tmp_path,
        )
        assert result.status == "failed"


# ---------------------------------------------------------------------------
# SIP-0100 harness_boundary — a QA test consumes the scaffold-owned fixture
# ---------------------------------------------------------------------------

_BOUNDARY = {"entry_modules": ["backend.main", "app.main"], "client_ctor": "TestClient"}


class TestHarnessBoundary:
    async def _run(self, tmp_path, source: str):
        (tmp_path / "test_x.py").write_text(source)
        return await get_check("harness_boundary").evaluate(
            {"file": "test_x.py", **_BOUNDARY}, tmp_path, stack="python"
        )

    async def test_fixture_use_passes(self, tmp_path):
        """The sanctioned shape: consume the injected `client` fixture, never import the app."""
        result = await self._run(
            tmp_path,
            "def test_health(client):\n    assert client.get('/health').status_code == 200\n",
        )
        assert result.status == "passed"

    async def test_pure_unit_test_with_no_app_access_passes(self, tmp_path):
        """Review #7: a test that never touches the app need not use the fixture."""
        result = await self._run(tmp_path, "def test_add():\n    assert 1 + 2 == 3\n")
        assert result.status == "passed"

    async def test_from_import_of_app_entry_fails(self, tmp_path):
        result = await self._run(
            tmp_path, "from backend.main import app\n\ndef test_x():\n    assert app\n"
        )
        assert result.status == "failed"
        assert "backend.main" in result.reason

    async def test_import_statement_of_app_entry_fails(self, tmp_path):
        result = await self._run(
            tmp_path, "import app.main\n\ndef test_x():\n    assert app.main\n"
        )
        assert result.status == "failed"
        assert "app.main" in result.reason

    async def test_direct_client_construction_fails(self, tmp_path):
        """Even without importing the app module, constructing the client directly is a bypass."""
        result = await self._run(
            tmp_path,
            "from fastapi.testclient import TestClient\nfrom backend.main import app\n"
            "c = TestClient(app)\n\ndef test_x():\n    assert c\n",
        )
        assert result.status == "failed"
        assert "TestClient" in result.reason

    async def test_dynamic_import_of_app_entry_fails(self, tmp_path):
        result = await self._run(
            tmp_path,
            "import importlib\napp = importlib.import_module('backend.main').app\n\n"
            "def test_x():\n    assert app\n",
        )
        assert result.status == "failed"
        assert "backend.main" in result.reason

    async def test_stack_unset_skips(self, tmp_path):
        (tmp_path / "test_x.py").write_text("from backend.main import app\n")
        result = await get_check("harness_boundary").evaluate(
            {"file": "test_x.py", **_BOUNDARY}, tmp_path, stack=None
        )
        assert result.status == "skipped"

    async def test_missing_file_failed(self, tmp_path):
        result = await get_check("harness_boundary").evaluate(
            {"file": "nope.py", **_BOUNDARY}, tmp_path, stack="python"
        )
        assert result.status == "failed"
        assert result.reason == "file_not_found"

    async def test_syntax_error_is_error(self, tmp_path):
        result = await self._run(tmp_path, "def test_x(:\n    pass\n")
        assert result.status == "error"


class TestNonPythonFilesSkipRatherThanError:
    """#605: an AST check handed a JavaScript file used to raise, and an erroring check
    turns patch verification into `unverifiable` — neither accepted nor rejected, so the
    unverified patch lands.

    pf-41 lost a roll to it: `function_defined` was aimed at `run.test.jsx`, verification
    never returned a verdict, and three bad repairs landed unchecked. pf-40 had the same
    bad repairs but verification worked, rejected them, and nothing landed.

    Only `import_present` guarded; its four siblings did not.
    """

    @staticmethod
    def _params(check_name: str, file: str) -> dict:
        base: dict[str, dict] = {
            "endpoint_defined": {"methods_paths": [["GET", "/x"]]},
            "import_present": {"module": "x"},
            "field_present": {"class_name": "X", "fields": ["a"]},
            "function_defined": {"name_prefix": "test_", "min_count": 1},
            "harness_boundary": {"entry_modules": ["backend.main"], "client_ctor": "TestClient"},
        }
        return {"file": file, **base[check_name]}

    @pytest.mark.parametrize(
        "check_name",
        [
            "endpoint_defined",
            "import_present",
            "field_present",
            "function_defined",
            "harness_boundary",
        ],
    )
    @pytest.mark.parametrize("suffix", [".jsx", ".js", ".ts", ".tsx"])
    async def test_frontend_file_skips(self, check_name, suffix, tmp_path):
        from squadops.cycles.acceptance_checks import get_check

        target = tmp_path / f"thing{suffix}"
        target.write_text("export default function Thing() { return null }\n")

        outcome = await get_check(check_name).evaluate(
            self._params(check_name, target.name), tmp_path, stack="fastapi"
        )

        assert outcome.status == "skipped", (
            f"{check_name} on {suffix} returned {outcome.status}"
            f"({getattr(outcome, 'reason', None)}) — an error makes the patch unverifiable"
        )

    @pytest.mark.parametrize(
        "check_name",
        [
            "endpoint_defined",
            "import_present",
            "field_present",
            "function_defined",
            "harness_boundary",
        ],
    )
    async def test_other_non_python_file_skips(self, check_name, tmp_path):
        """Not just JS — a markdown or YAML target must skip too, not crash the verdict."""
        from squadops.cycles.acceptance_checks import get_check

        target = tmp_path / "notes.md"
        target.write_text("# not python\n")

        outcome = await get_check(check_name).evaluate(
            self._params(check_name, target.name), tmp_path, stack="fastapi"
        )
        assert outcome.status == "skipped"

    async def test_python_files_are_still_evaluated(self, tmp_path):
        """The guard must not disable the checks it protects — a real Python file with
        real test functions must still pass."""
        from squadops.cycles.acceptance_checks import get_check

        target = tmp_path / "test_thing.py"
        target.write_text("def test_a():\n    pass\n\n\ndef test_b():\n    pass\n")

        outcome = await get_check("function_defined").evaluate(
            {"file": target.name, "name_prefix": "test_", "min_count": 2},
            tmp_path,
            stack="fastapi",
        )
        assert outcome.status == "passed"

    async def test_broken_python_still_errors(self, tmp_path):
        """A Python file that genuinely will not parse is a real problem and must NOT be
        silently skipped — the guard is about file type, not about hiding failures."""
        from squadops.cycles.acceptance_checks import get_check

        target = tmp_path / "broken.py"
        target.write_text("def oops(:\n")

        outcome = await get_check("function_defined").evaluate(
            {"file": target.name, "name_prefix": "test_", "min_count": 1},
            tmp_path,
            stack="fastapi",
        )
        assert outcome.status != "skipped"


# ---------------------------------------------------------------------------
# module_imports (#628)
# ---------------------------------------------------------------------------


class TestModuleImports:
    async def test_module_level_name_error_fails(self, tmp_path):
        # The pf-54 shape: decorators reference a name the module never defines.
        # AST checks and py_compile both pass this file; import cannot.
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "__init__.py").write_text("")
        (tmp_path / "backend" / "routes.py").write_text(
            "@router.get('/runs')\ndef list_runs():\n    return []\n"
        )
        outcome = await get_check("module_imports").evaluate(
            {"file": "backend/routes.py"}, tmp_path
        )
        assert outcome.status == "failed"
        assert outcome.reason == "module_import_failed"
        assert "NameError" in outcome.actual["stderr_tail"]

    async def test_clean_module_passes(self, tmp_path):
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "__init__.py").write_text("")
        (tmp_path / "backend" / "util.py").write_text("X = 1\n")
        (tmp_path / "backend" / "routes.py").write_text("from .util import X\nY = X + 1\n")
        outcome = await get_check("module_imports").evaluate(
            {"file": "backend/routes.py"}, tmp_path
        )
        assert outcome.status == "passed"
        assert outcome.actual["module"] == "backend.routes"

    async def test_missing_third_party_dependency_skips(self, tmp_path):
        # #462 philosophy: a dep the evaluating container lacks must not fail
        # correct code — it is an environment gap, reported as such.
        (tmp_path / "app.py").write_text("import nonexistent_dep_zq91\n")
        outcome = await get_check("module_imports").evaluate({"file": "app.py"}, tmp_path)
        assert outcome.status == "skipped"
        assert outcome.reason == "missing_tooling"
        assert outcome.actual["missing_module"] == "nonexistent_dep_zq91"

    async def test_missing_workspace_internal_module_fails(self, tmp_path):
        # The missing module's top-level package IS in the workspace — that is
        # the app referencing itself wrongly, not an environment gap.
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "__init__.py").write_text("")
        (tmp_path / "backend" / "routes.py").write_text("from backend.storee import reset\n")
        outcome = await get_check("module_imports").evaluate(
            {"file": "backend/routes.py"}, tmp_path
        )
        assert outcome.status == "failed"
        assert outcome.reason == "module_import_failed"

    async def test_self_import_not_found_fails(self, tmp_path):
        # Root-level module importing a sibling that does not exist anywhere:
        # the missing top-level equals the module's own package guard branch.
        (tmp_path / "solo.py").write_text("import solo_helper\n")
        outcome = await get_check("module_imports").evaluate({"file": "solo.py"}, tmp_path)
        assert outcome.status == "skipped"  # helper is not in workspace → env-gap semantics
        (tmp_path / "solo_helper.py").write_text("raise RuntimeError('boom')\n")
        outcome = await get_check("module_imports").evaluate({"file": "solo.py"}, tmp_path)
        assert outcome.status == "failed"

    async def test_init_py_imports_the_package(self, tmp_path):
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "__init__.py").write_text("PKG = True\n")
        outcome = await get_check("module_imports").evaluate(
            {"file": "backend/__init__.py"}, tmp_path
        )
        assert outcome.status == "passed"
        assert outcome.actual["module"] == "backend"

    async def test_file_not_found_fails(self, tmp_path):
        outcome = await get_check("module_imports").evaluate(
            {"file": "backend/absent.py"}, tmp_path
        )
        assert outcome.status == "failed"
        assert outcome.reason == "file_not_found"

    async def test_path_traversal_errors(self, tmp_path):
        outcome = await get_check("module_imports").evaluate({"file": "../outside.py"}, tmp_path)
        assert outcome.status == "error"

    async def test_frontend_extension_skips(self, tmp_path):
        (tmp_path / "App.jsx").write_text("export default 1;\n")
        outcome = await get_check("module_imports").evaluate({"file": "App.jsx"}, tmp_path)
        assert outcome.status == "skipped"


class TestFrontendCompiles:
    """#648 (fay-4/fay-8): a view with a rollup bind-time error passes every
    static check and first fails at final verification, out of correction
    reach. This check runs the real bundler at task time. Build execution is
    stubbed here (no node in the unit environment); the real thing is proven
    by the contract gate (bare-skeleton/reference-fill 14/14) and the fay-8
    deliverable replay."""

    def _workspace(self, tmp_path, *, with_frontend=True):
        views = tmp_path / "frontend" / "src" / "views"
        views.mkdir(parents=True)
        (views / "RunsListView.jsx").write_text("export default function V() {}\n")
        if with_frontend:
            (tmp_path / "frontend" / "package.json").write_text('{"name": "x"}\n')
        return tmp_path

    async def test_no_frontend_tree_skips(self, tmp_path):
        ws = self._workspace(tmp_path, with_frontend=False)
        outcome = await get_check("frontend_compiles").evaluate(
            {"file": "frontend/src/views/RunsListView.jsx"}, ws
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "no_frontend_tree"

    async def test_missing_npm_skips_as_tooling(self, tmp_path, monkeypatch):
        # #462: never fail correct code on tooling the evaluator lacks.
        from squadops.cycles import acceptance_checks as ac

        ws = self._workspace(tmp_path)
        monkeypatch.setattr(ac.shutil, "which", lambda _: None)
        outcome = await get_check("frontend_compiles").evaluate(
            {"file": "frontend/src/views/RunsListView.jsx"}, ws
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "missing_tooling"

    async def test_missing_view_file_fails(self, tmp_path):
        ws = self._workspace(tmp_path)
        outcome = await get_check("frontend_compiles").evaluate(
            {"file": "frontend/src/views/Nope.jsx"}, ws
        )
        assert outcome.status == "failed"
        assert outcome.reason == "file_not_found"

    async def test_build_failure_fails_with_stderr_evidence(self, tmp_path, monkeypatch):
        # The fay-8 shape: install fine, bundler rejects an undefined
        # identifier — the stderr tail is the repair-relevant evidence.
        from squadops.cycles import acceptance_checks as ac
        from squadops.cycles.acceptance_checks import FrontendCompilesCheck

        monkeypatch.setattr(ac.shutil, "which", lambda _: "/usr/bin/npm")

        ws = self._workspace(tmp_path)
        (ws / "frontend" / "node_modules").mkdir()

        async def _fake_run(argv, cwd, timeout_s):
            assert argv == ["npm", "run", "build"]
            return 1, "", "RollupError: 'runId' is not defined"

        monkeypatch.setattr(FrontendCompilesCheck, "_run", staticmethod(_fake_run))
        outcome = await get_check("frontend_compiles").evaluate(
            {"file": "frontend/src/views/RunsListView.jsx"}, ws
        )
        assert outcome.status == "failed"
        assert outcome.reason == "frontend_build_failed"
        assert "RollupError" in outcome.actual["stderr_tail"]

    async def test_clean_build_passes_and_installs_when_needed(self, tmp_path, monkeypatch):
        from squadops.cycles import acceptance_checks as ac
        from squadops.cycles.acceptance_checks import FrontendCompilesCheck

        monkeypatch.setattr(ac.shutil, "which", lambda _: "/usr/bin/npm")

        ws = self._workspace(tmp_path)  # no node_modules -> install expected first
        calls: list[list[str]] = []

        async def _fake_run(argv, cwd, timeout_s):
            calls.append(argv)
            return 0, "", ""

        monkeypatch.setattr(FrontendCompilesCheck, "_run", staticmethod(_fake_run))
        outcome = await get_check("frontend_compiles").evaluate(
            {"file": "frontend/src/views/RunsListView.jsx"}, ws
        )
        assert outcome.status == "passed"
        assert calls == [["npm", "install", "--no-audit", "--no-fund"], ["npm", "run", "build"]]

    async def test_install_failure_skips_not_fails(self, tmp_path, monkeypatch):
        # package.json is scaffold-frozen: a failing install is a
        # network/registry gap, never an artifact defect.
        from squadops.cycles import acceptance_checks as ac
        from squadops.cycles.acceptance_checks import FrontendCompilesCheck

        monkeypatch.setattr(ac.shutil, "which", lambda _: "/usr/bin/npm")

        ws = self._workspace(tmp_path)

        async def _fake_run(argv, cwd, timeout_s):
            return 1, "", "npm ERR! network ETIMEDOUT"

        monkeypatch.setattr(FrontendCompilesCheck, "_run", staticmethod(_fake_run))
        outcome = await get_check("frontend_compiles").evaluate(
            {"file": "frontend/src/views/RunsListView.jsx"}, ws
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "install_failed"


# ---------------------------------------------------------------------------
# undefined_names (#689) — the call-time NameError class
# ---------------------------------------------------------------------------


class TestUndefinedNames:
    """shk-2's loss: `create_run` called `RunEvent(...)` without importing it. Valid
    syntax, imports fine, every AST check green — the name resolves nowhere only when
    the handler runs, so the first invocation was a 500 in the qa suite."""

    @staticmethod
    async def _run(tmp_path: Path, source: str, rel: str = "backend/routes.py"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
        return await get_check("undefined_names").evaluate({"file": rel}, tmp_path)

    async def test_name_used_only_inside_a_function_body_is_caught(self, tmp_path):
        outcome = await self._run(
            tmp_path,
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            '@router.post("/runs")\n'
            "def create_run(body):\n"
            "    return RunEvent(id=1)\n",
        )
        assert outcome.status == "failed"
        assert outcome.actual["undefined"] == [{"name": "RunEvent", "line": 5}]
        assert "RunEvent" in outcome.reason

    async def test_every_undefined_name_is_reported_not_just_the_first(self, tmp_path):
        """A repair fixes what the evidence names. Reporting one of three sends it back
        for two more rounds — the same drip-feed that cost pf-41 three attempts."""
        outcome = await self._run(
            tmp_path,
            "def f():\n    return RunEvent(), Participant(), uuid.uuid4()\n",
        )
        assert [u["name"] for u in outcome.actual["undefined"]] == [
            "RunEvent",
            "Participant",
            "uuid",
        ]

    @pytest.mark.parametrize(
        ("label", "source"),
        [
            ("imported", "from .models import RunEvent\ndef f():\n    return RunEvent()\n"),
            ("fixture_params", "def test_x(client, monkeypatch):\n    return client.get('/')\n"),
            ("star_import", "from .models import *\ndef f():\n    return RunEvent()\n"),
            ("conditional", "import os\nif os.name:\n    Y = 1\ndef f():\n    return Y\n"),
            ("comprehension", "def f(items):\n    return [i for i in items if i]\n"),
            ("class_scope", "class A:\n    x = 1\n    def m(self):\n        return self.x\n"),
            (
                "forward_annotation",
                "from __future__ import annotations\ndef f() -> 'L': ...\nclass L: ...\n",
            ),
            ("global_decl", "def f():\n    global G\n    G = 1\ndef g():\n    return G\n"),
        ],
    )
    async def test_legitimate_scoping_shapes_do_not_false_fail(self, tmp_path, label, source):
        """Every one of these would break a real emission if flagged. Pytest fixtures
        bind as parameters (every qa suite), a star import is undecidable so it must
        not be guessed at, and conditional/global/comprehension/class scopes are
        ordinary Python the check must understand rather than approximate."""
        assert (await self._run(tmp_path, source)).status == "passed"

    async def test_syntax_error_skips_so_one_defect_is_not_reported_twice(self, tmp_path):
        """The pf-31 syntax gate owns truncated emissions. Failing here too would show
        one defect as two and split the repair's attention."""
        outcome = await self._run(tmp_path, "def f(:\n    pass\n")
        assert outcome.status == "skipped"
        assert outcome.reason == "unsupported_stack_or_syntax"

    async def test_missing_analyzer_is_an_error_never_a_skip(self, tmp_path, monkeypatch):
        """The corollary that decides whether this check is real. #462's skip-never-fail
        rule is for per-role provisioned tooling (Node in the qa image, TOOL_NODE); a
        base-lock pip dependency is present in every image by construction, so its
        absence is a build defect. Skipping would ship #689 as exactly the
        looks-enforced-but-isn't no-op SIP-0096 exists to kill."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("pyflakes"):
                raise ImportError("no pyflakes")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        outcome = await self._run(tmp_path, "def f():\n    return Undefined()\n")
        assert outcome.status == "error"
        assert outcome.reason == "missing_analyzer"
        assert outcome.actual["analyzer"] == "pyflakes"

    async def test_missing_file_fails_rather_than_passing_vacuously(self, tmp_path):
        outcome = await get_check("undefined_names").evaluate(
            {"file": "backend/absent.py"}, tmp_path
        )
        assert outcome.status == "failed"
        assert outcome.reason == "file_not_found"

    async def test_non_python_target_skips(self, tmp_path):
        (tmp_path / "view.jsx").write_text("export default function V(){ return <div/> }")
        outcome = await get_check("undefined_names").evaluate({"file": "view.jsx"}, tmp_path)
        assert outcome.status == "skipped"

    async def test_path_escaping_the_workspace_is_an_error(self, tmp_path):
        outcome = await get_check("undefined_names").evaluate(
            {"file": "../../etc/passwd"}, tmp_path
        )
        assert outcome.status == "error"
        assert outcome.reason == "path_escapes_workspace"


def test_undefined_names_is_framework_injected_and_out_of_the_authoring_vocabulary():
    """#689 D0: the framework applies it to every emission, so asking a plan author to
    select it is redundant work that can only be authored wrong — and an authored row
    would also be absent from bind-mode cycles, whose contract is pinned."""
    from squadops.cycles.acceptance_check_spec import render_typed_acceptance_vocabulary

    assert CHECK_SPECS["undefined_names"].framework_injected is True
    assert "undefined_names" not in render_typed_acceptance_vocabulary()
    # Every other check stays advertised — the flag must not hide the vocabulary.
    assert "endpoint_defined" in render_typed_acceptance_vocabulary()
