"""Tests for stub-fallback test detection (#276).

Bug this guards: a generated test that wraps the entrypoint import in
``except ImportError:`` and rebuilds the app inline validates a stub, so a
non-runnable deliverable (broken import) passes qa green. The detector must
flag that pattern and must NOT flag legitimate tests.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.stub_detection import detect_stub_fallback_tests

pytestmark = [pytest.mark.domain_capabilities]


_STUB_FALLBACK = """\
try:
    from backend.main import app
except ImportError:
    # Fallback inline app guarantees pytest collection succeeds.
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}


def test_health():
    assert app is not None
"""

_CLEAN_TEST = """\
from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200
"""


def test_flags_import_error_fallback_with_fastapi():
    offenders = detect_stub_fallback_tests(
        [{"name": "backend/tests/test_api.py", "content": _STUB_FALLBACK}]
    )
    assert offenders == ["backend/tests/test_api.py"]


def test_flags_module_not_found_and_flask():
    content = "try:\n    from app import app\nexcept ModuleNotFoundError:\n    from flask import Flask\n    app = Flask(__name__)\n"
    offenders = detect_stub_fallback_tests([{"filename": "test_app.py", "content": content}])
    assert offenders == ["test_app.py"]


def test_flags_tuple_except_form():
    content = (
        "try:\n    from backend.main import app\n"
        "except (ImportError, AttributeError):\n"
        "    from fastapi import FastAPI\n    app = FastAPI()\n"
    )
    offenders = detect_stub_fallback_tests([{"name": "test_x.py", "content": content}])
    assert offenders == ["test_x.py"]


def test_clean_test_not_flagged():
    assert detect_stub_fallback_tests([{"name": "test_api.py", "content": _CLEAN_TEST}]) == []


def test_import_guard_without_app_constructor_not_flagged():
    """Catching an optional-dependency ImportError without rebuilding an app is
    legitimate — must not be flagged (false-positive guard)."""
    content = (
        "try:\n    import ujson as json\nexcept ImportError:\n    import json\n\n"
        "def test_parse():\n    assert json.loads('{}') == {}\n"
    )
    assert detect_stub_fallback_tests([{"name": "test_parse.py", "content": content}]) == []


def test_non_test_file_ignored():
    """The real deliverable (main.py) is not a test file — even if it constructs
    an app and (hypothetically) guards an import, it must not be flagged."""
    content = "from fastapi import FastAPI\ntry:\n    import x\nexcept ImportError:\n    pass\napp = FastAPI()\n"
    assert detect_stub_fallback_tests([{"name": "backend/main.py", "content": content}]) == []


def test_multiple_offenders_sorted():
    files = [
        {"name": "test_b.py", "content": _STUB_FALLBACK},
        {"name": "test_a.py", "content": _STUB_FALLBACK},
        {"name": "test_ok.py", "content": _CLEAN_TEST},
    ]
    assert detect_stub_fallback_tests(files) == ["test_a.py", "test_b.py"]


@pytest.mark.parametrize(
    "files",
    [
        [],
        [{"name": "test_empty.py", "content": ""}],
        [{"name": "", "content": _STUB_FALLBACK}],
        [{"content": _STUB_FALLBACK}],  # missing name/filename/path
    ],
)
def test_empty_or_nameless_inputs_do_not_crash(files):
    assert detect_stub_fallback_tests(files) == []
