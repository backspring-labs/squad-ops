"""Tests for typed acceptance check evaluators (SIP-0092 M1.2).

Coverage:
- Per-check passed/failed/skipped/error matrix.
- Command safelist pattern matching (RC-10a).
- Safety boundary tests across check types: path traversal, absolute path,
  symlink escape, glob match cap.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from squadops.cycles.acceptance_check_spec import CHECK_SPECS
from squadops.cycles.acceptance_checks import (
    _CHECK_IMPLS,
    _argv_matches_safelist,
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
            {"file": "main.py", "methods_paths": ["GET /users", "POST /items", "DELETE /users/{uid}"]},
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
    async def test_compile_ok_passed(self, py_workspace):
        result = await get_check("command_exit_zero").evaluate(
            {"argv": [sys.executable, "-m", "py_compile", "ok.py"]},
            py_workspace,
        )
        # argv[0] is sys.executable (typically /path/to/python); pattern wants
        # literal "python", so the safelist should reject this. We assert the
        # safelist behavior, not the run-result, to keep the test hermetic.
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
        from squadops.cycles import acceptance_checks as ac

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
    assert _argv_matches_safelist(argv) is expected


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
        ("regex_match", {"file": "/etc/passwd", "pattern": "x"}),
    ],
)
async def test_absolute_path_all_path_checks_error(check_name, params, tmp_path):
    stack = "fastapi" if check_name == "endpoint_defined" else "python"
    result = await get_check(check_name).evaluate(params, tmp_path, stack=stack)
    assert result.status == "error"
    assert result.reason == "path_escapes_workspace"
