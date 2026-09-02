"""Tests for typed acceptance check evaluators (SIP-0092 M1.2).

Coverage:
- Per-check passed/failed/skipped/error matrix.
- Command safelist pattern matching (RC-10a).
- Safety boundary tests across check types: path traversal, absolute path,
  symlink escape, glob match cap.
"""

from __future__ import annotations

import shutil
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

    async def test_prefixed_router_serves_the_declared_paths(self, tmp_path: Path):
        """#1129 (1.6.5 FastAPI+React roll 6): the repair's router was
        ``APIRouter(prefix="/runs")`` with ``@router.post("")`` — the same ``POST /runs``
        the literal form declares — and the check refused a correct fix on the
        decorator's literal path."""
        (tmp_path / "routes.py").write_text(
            "from fastapi import APIRouter\n"
            'router = APIRouter(prefix="/runs", tags=["runs"])\n'
            "other = APIRouter(prefix=some_prefix)\n"
            '@router.get("")\n'
            "def get_runs():\n    return []\n"
            '@router.post("", status_code=201)\n'
            "def post_runs(body):\n    return {}\n"
            '@router.get("/{run_id}")\n'
            "def get_run(run_id: str):\n    return {}\n"
            '@router.post("/{run_id}/join")\n'
            "def join_run(run_id: str, body):\n    return {}\n"
            '@other.get("/x")\n'
            "def x():\n    return {}\n"
        )
        result = await get_check("endpoint_defined").evaluate(
            {
                "file": "routes.py",
                "methods_paths": [
                    "GET /runs",
                    "POST /runs",
                    "GET /runs/{run_id}",
                    "POST /runs/{run_id}/join",
                ],
            },
            tmp_path,
            stack="fastapi",
        )
        assert result.status == "passed", result.actual
        # a computed prefix is not read: that router's route stays literal
        assert "GET /x" in result.actual["found"]

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
            {"argv": ["pyflakes", "app.py"], "timeout_s": 9999},
            tmp_path,
        )
        assert result.status == "passed"
        assert captured["argv"] == ["pyflakes", "app.py"]


# ---------------------------------------------------------------------------
# Command safelist pattern matching (RC-10a)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv,expected",
    [
        # Allowed shapes
        (["python", "-m", "py_compile", "backend/main.py"], True),
        (["node", "--check", "app.js"], True),
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
        # #707: forms this list advertised while no agent image could run them.
        # Measured absent (ruff, tsc) or present-but-unusable (eslint v6.4.0 exits 2
        # with no config); `python -m mypy` cleared BOTH old gates and then failed at
        # evaluation with "No module named mypy" — the case an argv[0] check is blind to.
        (["python", "-m", "mypy", "src/"], False),
        (["ruff", "check", "src/"], False),
        (["tsc", "--noEmit"], False),
        (["eslint", "src/"], False),
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


class TestDeclaredImports:
    """cyc_0a0a33b4776e's loss: a qa test imported `@testing-library/user-event`
    beside three declared `@testing-library/*` siblings. Vite could not resolve it,
    the suite never ran, and three correction rounds went to a defect two files
    already decided — the specifiers are in the source, the dependencies in
    package.json beside it. `unresolved_imports` ignores everything outside the
    workspace by design, so nothing covered this boundary (#1217)."""

    @staticmethod
    async def _run(
        tmp_path: Path,
        source: str,
        manifest: dict | None = None,
        rel: str = "frontend/src/__tests__/runs.test.jsx",
    ):
        import json as _json

        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
        if manifest is not None:
            (tmp_path / "frontend" / "package.json").write_text(_json.dumps(manifest))
        return await get_check("declared_imports").evaluate({"file": rel}, tmp_path)

    _DECLARED = {"devDependencies": {"@testing-library/react": "^16", "vitest": "^2"}}

    async def test_the_undeclared_sibling_package_is_caught(self, tmp_path):
        outcome = await self._run(
            tmp_path,
            'import { render } from "@testing-library/react"\n'
            'import userEvent from "@testing-library/user-event"\n',
            self._DECLARED,
        )
        assert outcome.status == "failed"
        assert outcome.actual["undeclared"] == ["@testing-library/user-event"]

    @pytest.mark.parametrize(
        ("label", "source"),
        [
            ("declared_dep", 'import { render } from "@testing-library/react"\n'),
            ("relative", 'import App from "../App"\n'),
            ("absolute", 'import x from "/abs/thing"\n'),
            ("node_builtin", 'import path from "path"\n'),
            ("node_prefixed", 'import path from "node:path"\n'),
            ("subpath_of_declared", 'import x from "vitest/config"\n'),
        ],
    )
    async def test_resolvable_imports_are_not_reported(self, tmp_path, label, source):
        """Each of these resolves at runtime. A check that fires on them is #645's
        fails-on-correct-content class, which is worse than the gap it closes."""
        outcome = await self._run(tmp_path, source, self._DECLARED)
        assert outcome.status == "passed", f"{label} was wrongly reported"

    async def test_a_next_js_path_alias_is_not_a_scoped_package(self, tmp_path):
        """Bug caught: THE regression this check shipped with. `@/lib/store` is a
        tsconfig path alias; splitting it as the scoped package `@/lib` failed every
        Next.js route file in cyc_05abfc7c1f00, exhausted the run's three correction
        rounds on a defect that did not exist, and took the roll with it. A scoped
        package needs a NON-EMPTY scope."""
        import json as _json

        (tmp_path / "app" / "api" / "runs").mkdir(parents=True)
        (tmp_path / "package.json").write_text(_json.dumps({"dependencies": {"next": "^14"}}))
        (tmp_path / "app/api/runs/route.ts").write_text(
            "import { NextResponse } from 'next/server'\n"
            "import { badRequest } from '@/lib/errors'\n"
            "import { store } from '@/lib/store'\n"
        )
        outcome = await get_check("declared_imports").evaluate(
            {"file": "app/api/runs/route.ts"}, tmp_path
        )
        assert outcome.status == "passed", getattr(outcome, "reason", "")

    async def test_a_declared_tsconfig_alias_is_not_a_package(self, tmp_path):
        """The general form: a project may alias any prefix to any path. An aliased
        specifier is a path, not a package name, whatever the prefix looks like."""
        import json as _json

        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "package.json").write_text(_json.dumps({"dependencies": {}}))
        (tmp_path / "tsconfig.json").write_text(
            _json.dumps({"compilerOptions": {"paths": {"~utils/*": ["./src/utils/*"]}}})
        )
        (tmp_path / "src/a.ts").write_text("import x from '~utils/fmt'\n")
        outcome = await get_check("declared_imports").evaluate({"file": "src/a.ts"}, tmp_path)
        assert outcome.status == "passed"

    async def test_an_unparseable_tsconfig_reports_nothing(self, tmp_path):
        """tsconfig permits comments and trailing commas that json.loads rejects. A
        strict parse failing must not become a report — undecidable is undecidable,
        which is the property this check violated once already."""
        import json as _json

        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "package.json").write_text(_json.dumps({"dependencies": {}}))
        (tmp_path / "tsconfig.json").write_text('{ "compilerOptions": { /* comment */ } }')
        (tmp_path / "src/a.ts").write_text("import x from '@/anything'\n")
        outcome = await get_check("declared_imports").evaluate({"file": "src/a.ts"}, tmp_path)
        assert outcome.status == "passed"

    async def test_require_and_dynamic_import_forms_are_read(self, tmp_path):
        """A specifier is a specifier whichever keyword introduces it. Reading only
        `import ... from` would leave two forms silently unchecked."""
        outcome = await self._run(
            tmp_path,
            'const a = require("missing-cjs")\nconst b = await import("missing-dynamic")\n',
            self._DECLARED,
        )
        assert outcome.status == "failed"
        assert set(outcome.actual["undeclared"]) == {"missing-cjs", "missing-dynamic"}

    async def test_every_undeclared_package_is_reported_not_just_the_first(self, tmp_path):
        """A repair fixes what the evidence names — the same drip-feed reasoning as
        undefined_names below."""
        outcome = await self._run(
            tmp_path,
            'import a from "pkg-one"\nimport b from "pkg-two"\n',
            self._DECLARED,
        )
        assert outcome.actual["undeclared"] == ["pkg-one", "pkg-two"]

    @pytest.mark.parametrize("manifest", [None], ids=["absent"])
    async def test_a_missing_manifest_is_undecidable_not_a_failure(self, tmp_path, manifest):
        """No package.json above the file is not evidence that an import is wrong.
        Failing here would indict every emission in a tree that keeps its manifest
        somewhere this check did not look."""
        outcome = await self._run(tmp_path, 'import x from "anything"\n', manifest)
        assert outcome.status == "skipped"

    async def test_an_unparseable_manifest_is_undecidable_too(self, tmp_path):
        target = tmp_path / "frontend/src/__tests__/runs.test.jsx"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('import x from "anything"\n')
        (tmp_path / "frontend" / "package.json").write_text("{ not json")
        outcome = await get_check("declared_imports").evaluate(
            {"file": "frontend/src/__tests__/runs.test.jsx"}, tmp_path
        )
        assert outcome.status == "skipped"


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

    async def test_a_frontend_target_without_tsc_skips_as_missing_tooling(
        self, tmp_path, monkeypatch
    ):
        """#939: the JS/TS half is tsc, provisioned per role as data; where no role
        declared it (runtime-api today) the check skips and NAMES the tool, the #462
        rule — never a silent pass, never a failure charged to the emission."""
        from squadops.cycles import acceptance_checks

        monkeypatch.setattr(acceptance_checks.shutil, "which", lambda name: None)
        (tmp_path / "view.jsx").write_text("export default function V(){ return <div/> }")
        outcome = await get_check("undefined_names").evaluate({"file": "view.jsx"}, tmp_path)
        assert outcome.status == "skipped"
        assert outcome.reason == "missing_tooling"
        assert outcome.actual["missing_module"] == "tsc"

    async def test_an_extension_outside_the_analysers_skips(self, tmp_path):
        (tmp_path / "util.mjs").write_text("export const x = y\n")
        outcome = await get_check("undefined_names").evaluate({"file": "util.mjs"}, tmp_path)
        assert outcome.status == "skipped"

    def test_tsc_diagnostics_are_filtered_to_the_file_and_to_unresolved_names(self):
        """Bug caught: a workspace materialised without node_modules reports every import
        as TS2307, and another file's TS2304 is another file's — neither may reach this
        file's verdict. Paths are matched after tsc's ``./`` prefix is dropped."""
        from squadops.cycles.acceptance_checks import tsc_syntax_errors_in, tsc_undefined_names

        out = (
            "__tests__/scaffold/red.scaffold.test.ts(1,50): error TS2307: Cannot find module "
            "'vitest' or its corresponding type declarations.\n"
            "__tests__/scaffold/red.scaffold.test.ts(30,30): error TS2304: Cannot find name "
            "'created'.\n"
            "__tests__/other.test.ts(4,3): error TS2304: Cannot find name 'other'.\n"
            "./__tests__/scaffold/red.scaffold.test.ts(41,5): error TS2552: Cannot find name "
            "'partcipants'. Did you mean 'participants'?\n"
            "__tests__/broken.test.ts(2,1): error TS1005: ')' expected.\n"
        )
        assert tsc_undefined_names(out, "__tests__/scaffold/red.scaffold.test.ts") == [
            {"name": "created", "line": 30},
            {"name": "partcipants", "line": 41},
        ]
        assert tsc_undefined_names(out, "./__tests__/other.test.ts") == [
            {"name": "other", "line": 4}
        ]
        assert tsc_undefined_names(out, "__tests__/clean.test.ts") == []
        assert tsc_syntax_errors_in(out, "__tests__/broken.test.ts") is True
        assert tsc_syntax_errors_in(out, "__tests__/scaffold/red.scaffold.test.ts") is False

    async def test_tsc_runs_once_per_workspace_and_each_file_reads_its_own_lines(
        self, tmp_path, monkeypatch
    ):
        """Bug caught: a task emits many files and the criterion is file-scoped — running
        tsc per file multiplies a 700 ms project check by the file count. One run per
        materialised tree; and the verdict for each file is that file's diagnostics."""
        from squadops.cycles import acceptance_checks

        calls: list[list[str]] = []

        async def fake_run(argv, cwd, timeout_s):
            calls.append(argv)
            return (
                2,
                "__tests__/a.test.ts(3,9): error TS2304: Cannot find name 'created'.\n"
                "__tests__/a.test.ts(1,30): error TS2307: Cannot find module 'vitest'.\n",
                "",
            )

        monkeypatch.setattr(acceptance_checks.shutil, "which", lambda name: "/usr/bin/tsc")
        monkeypatch.setattr(acceptance_checks, "_run_argv", fake_run)
        acceptance_checks._TSC_OUTPUT_CACHE.clear()
        (tmp_path / "tsconfig.json").write_text("{}")
        (tmp_path / "__tests__").mkdir()
        (tmp_path / "__tests__" / "a.test.ts").write_text("expect(created)\n")
        (tmp_path / "__tests__" / "b.test.ts").write_text("const b = 1\n")

        a = await get_check("undefined_names").evaluate({"file": "__tests__/a.test.ts"}, tmp_path)
        b = await get_check("undefined_names").evaluate({"file": "__tests__/b.test.ts"}, tmp_path)
        assert a.status == "failed"
        assert a.actual["undefined"] == [{"name": "created", "line": 3}]
        assert b.status == "passed"
        assert len(calls) == 1
        assert calls[0][:4] == ["tsc", "--noEmit", "-p", "."]

    async def test_a_syntax_error_is_the_syntax_gates_and_is_not_reported_twice(
        self, tmp_path, monkeypatch
    ):
        from squadops.cycles import acceptance_checks

        async def fake_run(argv, cwd, timeout_s):
            return 2, "app/x.ts(2,1): error TS1005: ')' expected.\n", ""

        monkeypatch.setattr(acceptance_checks.shutil, "which", lambda name: "/usr/bin/tsc")
        monkeypatch.setattr(acceptance_checks, "_run_argv", fake_run)
        acceptance_checks._TSC_OUTPUT_CACHE.clear()
        (tmp_path / "app").mkdir()
        (tmp_path / "app" / "x.ts").write_text("f(\n")
        outcome = await get_check("undefined_names").evaluate({"file": "app/x.ts"}, tmp_path)
        assert outcome.status == "skipped"
        assert outcome.reason == "unsupported_stack_or_syntax"

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


# ---------------------------------------------------------------------------
# fill_slot_signature (#730 D1 / #504)
# ---------------------------------------------------------------------------

_FILL_SEED_ROUTES = [
    {
        "route": "POST /runs",
        "function": "create_run",
        "params": ["payload"],
        "response_model": "RunEvent",
    }
]

_COMPLIANT_SLOT = """
from fastapi import APIRouter
router = APIRouter()

@router.post("/runs", response_model=RunEvent, status_code=201)
def create_run(payload):
    return payload
"""


class TestFillSlotSignature:
    async def test_divergent_signature_fails_with_the_divergence_list(self, tmp_path):
        """The pf-40 promotion: drift on a reported element now costs the
        producer an acceptance failure carrying exactly what to put back —
        instead of a log line nobody's repair ever read."""
        (tmp_path / "routes.py").write_text(
            _COMPLIANT_SLOT.replace("create_run(payload)", "make_run(data)")
        )
        result = await get_check("fill_slot_signature").evaluate(
            {"file": "routes.py", "routes": list(_FILL_SEED_ROUTES)}, tmp_path
        )
        assert result.status == "failed"
        assert "'create_run'" in result.reason and "'make_run'" in result.reason
        assert len(result.actual["divergences"]) == 2  # handler name + params

    async def test_compliant_slot_passes(self, tmp_path):
        (tmp_path / "routes.py").write_text(_COMPLIANT_SLOT)
        result = await get_check("fill_slot_signature").evaluate(
            {"file": "routes.py", "routes": list(_FILL_SEED_ROUTES)}, tmp_path
        )
        assert result.status == "passed"

    async def test_syntax_broken_emission_skips_not_fails(self, tmp_path):
        # The syntax gate owns unparseable emissions (one defect, one report).
        (tmp_path / "routes.py").write_text("def broken(:\n")
        result = await get_check("fill_slot_signature").evaluate(
            {"file": "routes.py", "routes": list(_FILL_SEED_ROUTES)}, tmp_path
        )
        assert result.status == "skipped"
        assert result.reason == "unsupported_stack_or_syntax"

    async def test_missing_declaration_is_an_injection_bug_not_an_app_gap(self, tmp_path):
        (tmp_path / "routes.py").write_text(_COMPLIANT_SLOT)
        result = await get_check("fill_slot_signature").evaluate(
            {"file": "routes.py", "routes": []}, tmp_path
        )
        assert result.status == "error"
        assert result.reason == "missing_route_declaration"

    async def test_missing_file_fails(self, tmp_path):
        result = await get_check("fill_slot_signature").evaluate(
            {"file": "routes.py", "routes": list(_FILL_SEED_ROUTES)}, tmp_path
        )
        assert result.status == "failed"
        assert result.reason == "file_not_found"


_REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"


@pytest.mark.skipif(
    shutil.which("tsc") is None,
    reason="tsc is provisioned in CI and the dev/qa images (npm-global-packages.txt, #939)",
)
class TestUndefinedNamesReplaysTheRollThatCostIt:
    """1.7.0 roll 4, ``cyc_58d92ca2b407``: a qa repair's scaffold shell used ``created``
    in its fill without declaring it, reached vitest, and failed ``ReferenceError`` —
    nothing between the emission and the runner had looked. The stored shell, replayed
    through the check under the very tsconfig the Next.js skeleton emits, must name it;
    the same shell from the accepted gating roll must pass (the over-rejection control)."""

    @staticmethod
    async def _replay(tmp_path: Path, fixture: str):
        from squadops.capabilities.stack_nextjs_ts import _TSCONFIG
        from squadops.cycles import acceptance_checks

        acceptance_checks._TSC_OUTPUT_CACHE.clear()
        (tmp_path / "tsconfig.json").write_text(_TSCONFIG)
        rel = f"__tests__/scaffold/{fixture}"
        (tmp_path / "__tests__" / "scaffold").mkdir(parents=True)
        (tmp_path / rel).write_text((_REPLAYS / fixture).read_text())
        return await get_check("undefined_names").evaluate({"file": rel}, tmp_path)

    async def test_the_roll_4_shell_is_rejected_naming_the_name_and_the_line(self, tmp_path):
        outcome = await self._replay(
            tmp_path, "1-7-0-roll-4-fill-with-undeclared-name.scaffold.test.ts"
        )
        assert outcome.status == "failed"
        assert outcome.actual["undefined"] == [{"name": "created", "line": 30}]
        assert outcome.actual["analyzer"] == "tsc"

    async def test_the_gating_rolls_shell_passes(self, tmp_path):
        outcome = await self._replay(tmp_path, "1-7-0-roll-6-green.scaffold.test.ts")
        assert outcome.status == "passed"

    async def test_a_react_jsx_suite_without_a_tsconfig_is_checked_too(self, tmp_path):
        """The React stack emits no tsconfig; ``--allowJs --checkJs`` over the explicit
        file list reports the same class in plain JSX (measured 2026-09-01)."""
        from squadops.cycles import acceptance_checks

        acceptance_checks._TSC_OUTPUT_CACHE.clear()
        views = tmp_path / "frontend" / "src"
        views.mkdir(parents=True)
        (views / "views.test.jsx").write_text(
            "import { describe, it, expect } from 'vitest'\n"
            "describe('x', () => { it('y', () => { expect(created).toBe(1) }) })\n"
        )
        (views / "clean.test.jsx").write_text(
            "import { describe, it, expect } from 'vitest'\n"
            "const created = 1\n"
            "describe('x', () => { it('y', () => { expect(created).toBe(1) }) })\n"
        )
        red = await get_check("undefined_names").evaluate(
            {"file": "frontend/src/views.test.jsx"}, tmp_path
        )
        green = await get_check("undefined_names").evaluate(
            {"file": "frontend/src/clean.test.jsx"}, tmp_path
        )
        assert red.status == "failed"
        assert [u["name"] for u in red.actual["undefined"]] == ["created"]
        assert green.status == "passed"


class TestAdditiveContainmentEvaluator:
    """#1022 at the typed-acceptance seam: the injected `additive_containment` check on a
    materialised workspace, replayed from stored suites. The evaluator reads the scaffold
    stack from its own params — the seam's `stack` argument is the check vocabulary,
    which Next.js does not declare, so relying on it would skip every Next.js suite."""

    _REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"

    async def _run(self, tmp_path, fixture: str, rel: str, stack: str | None):
        from squadops.cycles.acceptance_checks import AdditiveContainmentCheck

        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((self._REPLAYS / fixture).read_text(encoding="utf-8"), encoding="utf-8")
        params = {"file": rel} if stack is None else {"file": rel, "stack": stack}
        return await AdditiveContainmentCheck().evaluate(params, tmp_path, stack=None)

    async def test_c3s_stored_suite_fails_naming_the_rule_and_what_the_stack_counts(self, tmp_path):
        outcome = await self._run(
            tmp_path, "v7-c3-repair-00-api-runs.test.ts", "__tests__/api-runs.test.ts", "nextjs_ts"
        )
        assert outcome.status == "failed"
        assert outcome.reason == "1 containment finding(s): no_application_invocation"
        assert outcome.actual["file"] == "__tests__/api-runs.test.ts"
        assert [f["rule"] for f in outcome.actual["findings"]] == ["no_application_invocation"]
        assert "app/api/**/route" in outcome.actual["findings"][0]["detail"]

    @pytest.mark.parametrize(
        ("fixture", "rel", "stack"),
        [
            ("v7-slot-2-green-runs.test.ts", "__tests__/runs.test.ts", "nextjs_ts"),
            ("1-7-0-nextjs-roll-6-runs.test.ts", "__tests__/runs.test.ts", "nextjs_ts"),
            (
                "1-6-6-react-roll-6-frontend-suite.test.jsx",
                "frontend/src/__tests__/runs.test.jsx",
                "fullstack_fastapi_react",
            ),
        ],
    )
    async def test_the_accepted_rolls_suites_pass(self, tmp_path, fixture, rel, stack):
        outcome = await self._run(tmp_path, fixture, rel, stack)
        assert outcome.status == "passed"
        assert outcome.actual == {"file": rel, "findings": []}

    async def test_without_a_stack_param_the_check_skips_rather_than_judging(self, tmp_path):
        """Judged nothing must never read as clean (#986): no declaration, no verdict."""
        outcome = await self._run(
            tmp_path, "v7-c3-repair-00-api-runs.test.ts", "__tests__/api-runs.test.ts", None
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "unknown_stack"

    async def test_a_source_file_is_not_a_suite_and_skips(self, tmp_path):
        outcome = await self._run(
            tmp_path, "v7-slot-2-green-runs.test.ts", "lib/store.ts", "nextjs_ts"
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "not_a_suite"

    async def test_a_missing_file_fails_rather_than_passing_silently(self, tmp_path):
        from squadops.cycles.acceptance_checks import AdditiveContainmentCheck

        outcome = await AdditiveContainmentCheck().evaluate(
            {"file": "__tests__/gone.test.ts", "stack": "nextjs_ts"}, tmp_path, stack=None
        )
        assert outcome.status == "failed"
        assert outcome.reason == "file_not_found"


class TestDomAnchorQueriesEvaluator:
    """#668 at the typed-acceptance seam, replayed from stored suites under their own
    manifests' inventories (the params the planner binds)."""

    _REPLAYS = Path(__file__).resolve().parents[2] / "fixtures" / "roll_replays"

    def _inventory(self, manifest_name: str) -> dict[str, list[str]]:
        import yaml

        manifest = yaml.safe_load((self._REPLAYS / manifest_name).read_text(encoding="utf-8"))
        return {r["view"]: list(r["testids"]) for r in manifest["frontend"]["routes"]}

    async def _run(self, tmp_path, fixture: str, rel: str, anchors: dict):
        from squadops.cycles.acceptance_checks import DomAnchorQueriesCheck

        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((self._REPLAYS / fixture).read_text(encoding="utf-8"), encoding="utf-8")
        return await DomAnchorQueriesCheck().evaluate({"file": rel, "anchors": anchors}, tmp_path)

    async def test_fay_14_fails_naming_the_view_and_its_anchors(self, tmp_path):
        outcome = await self._run(
            tmp_path,
            "fay-14-RunDetailView.test.jsx",
            "frontend/src/tests/RunDetailView.test.jsx",
            self._inventory("fay-14-interface_manifest.yaml"),
        )
        assert outcome.status == "failed"
        assert outcome.reason == "2 anchor finding(s): no_anchor_queries, view_anchors_not_queried"
        assert [f["rule"] for f in outcome.actual["findings"]] == [
            "no_anchor_queries",
            "view_anchors_not_queried",
        ]
        assert outcome.actual["covered_views"] == ["RunDetailView"]
        assert outcome.actual["queried"] == []
        assert outcome.actual["text_queries"] == 55

    async def test_the_accepted_roll_6_suite_passes_with_its_observations_banked(self, tmp_path):
        outcome = await self._run(
            tmp_path,
            "1-6-6-react-roll-6-frontend-suite.test.jsx",
            "frontend/src/tests/runs.test.jsx",
            self._inventory("1-6-6-react-roll-6-interface_manifest.yaml"),
        )
        assert outcome.status == "passed"
        assert outcome.actual["findings"] == []
        assert outcome.actual["unknown_anchors"] == []
        assert len(outcome.actual["queried"]) == 10

    async def test_an_empty_inventory_skips_rather_than_passing(self, tmp_path):
        outcome = await self._run(
            tmp_path, "fay-14-RunDetailView.test.jsx", "frontend/src/tests/x.test.jsx", {}
        )
        assert outcome.status == "skipped"
        assert outcome.reason == "no_anchor_inventory"

    async def test_a_missing_file_fails(self, tmp_path):
        from squadops.cycles.acceptance_checks import DomAnchorQueriesCheck

        outcome = await DomAnchorQueriesCheck().evaluate(
            {"file": "frontend/src/tests/gone.test.jsx", "anchors": {"V": ["v-root"]}}, tmp_path
        )
        assert outcome.status == "failed"
        assert outcome.reason == "file_not_found"
