"""Tests for the backend import-acceptance check (#276).

Bug this guards: a backend can pass its generated pytest suite yet fail to
import. The generated ``test_api.py`` wraps ``from backend.main import app`` in
a ``try/except ImportError`` that silently substitutes an inline stub app, so a
``backend/main.py`` that raises ``NameError`` on import (``BaseModel`` used
without ``from pydantic import BaseModel``) shipped green in a ``completed`` run
(cyc_2f415e43f9cf). ``run_backend_import_check`` must FAIL when a delivered
module can't import, and must SKIP (not fail) when it genuinely can't assess:
no backend source, or a missing third-party dependency the runner lacks.

These run real subprocesses (they must actually *execute* module bodies to catch
a NameError — byte-compiling wouldn't), but need only the Python interpreter, so
they are hermetic.
"""

from __future__ import annotations

import pytest

import squadops.capabilities.handlers.test_runner as tr
from squadops.capabilities.dev_capabilities import TEST_FRAMEWORK_PYTEST
from squadops.capabilities.handlers.test_runner import (
    RunTestsResult,
    run_backend_import_check,
    run_build_validation,
)

pytestmark = [pytest.mark.domain_capabilities]


def _rec(path: str, content: str) -> dict[str, str]:
    return {"path": path, "content": content}


# --- run_backend_import_check: real import execution --------------------------


async def test_nameerror_module_is_a_failure():
    """The canonical #276 case: BaseModel referenced without importing it. The
    module byte-compiles fine but NameErrors when its body runs."""
    result = await run_backend_import_check(
        [_rec("backend/main.py", "class RunCreateRequest(BaseModel):\n    pass\n")]
    )
    assert result.ran is True
    assert result.ok is False
    assert result.failed is True
    assert "main.py" in result.error
    assert "NameError" in result.error


async def test_clean_backend_imports_ok():
    result = await run_backend_import_check(
        [_rec("backend/main.py", "VALUE = 1\n\n\ndef add(a, b):\n    return a + b\n")]
    )
    assert result.ran is True
    assert result.ok is True
    assert result.failed is False


async def test_no_backend_python_source_skips():
    """A frontend-only deliverable has no backend to import — skip, not fail."""
    result = await run_backend_import_check([_rec("frontend/src/App.jsx", "export default 1")])
    assert result.ran is False
    assert result.failed is False


async def test_missing_third_party_dep_is_skip_not_failure():
    """A module importing a package the runner doesn't have can't be assessed —
    a SKIP, not a deliverable failure (don't punish the app for our env). The
    guard against false reds."""
    result = await run_backend_import_check(
        [_rec("backend/main.py", "import totally_absent_pkg_xyz_9000\n")]
    )
    assert result.ran is False
    assert result.failed is False


async def test_syntax_error_is_a_failure():
    result = await run_backend_import_check([_rec("backend/main.py", "def broken(:\n    pass\n")])
    assert result.ran is True
    assert result.failed is True


async def test_only_backend_is_checked_not_frontend_py():
    """A stray broken .py under frontend/ is excluded (the frontend build check
    owns frontend); a clean backend passes despite it."""
    result = await run_backend_import_check(
        [
            _rec("frontend/tooling.py", "class X(NotDefinedAnywhere):\n    pass\n"),
            _rec("backend/main.py", "OK = True\n"),
        ]
    )
    assert result.ran is True
    assert result.ok is True


async def test_broken_delivered_sibling_fails_via_entrypoint():
    """The entrypoint imports a delivered sibling that NameErrors — importing the
    entrypoint surfaces it (not a missing-dep skip), so the real defect blocks."""
    result = await run_backend_import_check(
        [
            _rec("backend/main.py", "from schemas import Thing\n\napp = Thing\n"),
            _rec("backend/schemas.py", "class Thing(BaseModel):\n    pass\n"),
        ]
    )
    assert result.ran is True
    assert result.failed is True
    assert "NameError" in result.error


# --- run_build_validation: pytest branch folds the backend import failure ------


async def test_pytest_build_validation_folds_backend_import_failure(monkeypatch):
    """#276 end-to-end: generated tests pass (against a stub) yet the real
    backend won't import → the run is red, not green."""

    async def _generated(*_a, **_k):
        return RunTestsResult(executed=True, exit_code=0)  # tests green against the stub

    monkeypatch.setattr(tr, "run_generated_tests", _generated)
    result = await run_build_validation(
        TEST_FRAMEWORK_PYTEST,
        [_rec("backend/main.py", "class Req(BaseModel):\n    pass\n")],
        [_rec("backend/tests/test_api.py", "def test_ok():\n    assert True\n")],
    )
    assert result.tests_passed is False
    assert result.exit_code != 0
    assert "import" in result.error


async def test_pytest_build_validation_clean_backend_stays_green(monkeypatch):
    """A clean backend must not turn a passing suite red (no false positive)."""

    async def _generated(*_a, **_k):
        return RunTestsResult(executed=True, exit_code=0)

    monkeypatch.setattr(tr, "run_generated_tests", _generated)
    result = await run_build_validation(
        TEST_FRAMEWORK_PYTEST,
        [_rec("backend/main.py", "app = object()\n")],
        [_rec("backend/tests/test_api.py", "def test_ok():\n    assert True\n")],
    )
    assert result.tests_passed is True
    assert result.exit_code == 0
