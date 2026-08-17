"""Tests for stub-fallback test detection (#276).

Bug this guards: a generated test that wraps the entrypoint import in
``except ImportError:`` and rebuilds the app inline validates a stub, so a
non-runnable deliverable (broken import) passes qa green. The detector must
flag that pattern and must NOT flag legitimate tests.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.stub_detection import (
    MOCKS_THE_NETWORK,
    MOCKS_THE_SUBJECT,
    detect_self_mocking_tests,
    detect_stub_fallback_tests,
)

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


# --- Self-mocking suites (#915) -------------------------------------------------

#: Window roll 3's real emission (`cyc_b20f58cc7cbc`), condensed: the mock is primed,
#: the mock is called, and the assertion reads back what the mock was told to return.
#: 479 lines that never touched the application, and green by construction.
_SELF_MOCKING = """\
import { describe, expect, it, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn();
global.fetch = mockFetch as any;

describe('POST /api/runs', () => {
  it('rejects a blank title', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ error_code: 'validation_error' }),
    });
    const response = await fetch('/api/runs', { method: 'POST', body: '{}' });
    const data = await response.json();
    expect(data.error_code).toBe('validation_error');
  });
});
"""

#: Window roll 2's real additive suite, condensed. The in-process model done right:
#: the route module is imported and its handler invoked with a real Request. This is
#: the suite the detector must never flag.
_REAL_ADDITIVE = """\
import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, insert } from '@/lib/store'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRuns from '@/app/api/runs/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

describe('join', () => {
  it('adds a participant', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', { method: 'POST', body: '{}' }),
    );
    expect(res.status).toBe(201);
  });
});
"""


class TestSelfMockingSuites:
    """#915. The TypeScript sibling of the stub-fallback class and strictly worse: a
    stub-fallback suite reconstructs the app and then fails, because a reconstruction
    misbehaves. A self-mocking suite asserts what it told its own mock to return, so
    passing is its natural state. Roll 3 only went red because its scaffold slots were
    also unfilled — with them filled, 479 lines of nothing would have read as
    verification."""

    def test_roll_threes_real_suite_is_flagged(self):
        offenders = detect_self_mocking_tests(
            [{"name": "__tests__/api/runs.test.ts", "content": _SELF_MOCKING}]
        )
        assert offenders == [("__tests__/api/runs.test.ts", MOCKS_THE_NETWORK)]

    def test_the_real_additive_suite_is_not_flagged(self):
        """The false positive that would matter most. Roll 2's additive suite is the
        model answer — imports the route module, invokes the handler, asserts on the
        real response — and a detector that flags it would reject correct work."""
        assert (
            detect_self_mocking_tests(
                [{"name": "__tests__/participants.test.ts", "content": _REAL_ADDITIVE}]
            )
            == []
        )

    def test_mocking_an_outbound_call_while_invoking_the_route_is_legitimate(self):
        """Mocking is not the defect; mocking INSTEAD of invoking is. A suite that
        stubs an outbound dependency and still drives the real handler is exactly what
        a caller should be allowed to write."""
        content = _REAL_ADDITIVE + "\nglobal.fetch = vi.fn()  // stub the upstream weather API\n"
        assert (
            detect_self_mocking_tests([{"name": "__tests__/x.test.ts", "content": content}]) == []
        )

    def test_mocking_the_route_module_is_flagged_even_when_it_is_also_imported(self):
        """The hole the import-based discriminator would otherwise leave: mock the
        subject, import the mock, assert on it. Every clause of the two-clause rule is
        satisfied and the application is still never invoked, so this one is
        unconditional."""
        content = (
            "import { vi } from 'vitest'\n"
            "vi.mock('@/app/api/runs/route')\n"
            "import * as route from '@/app/api/runs/route'\n"
        )
        offenders = detect_self_mocking_tests([{"name": "__tests__/y.test.ts", "content": content}])
        assert offenders == [("__tests__/y.test.ts", MOCKS_THE_SUBJECT)]

    @pytest.mark.parametrize(
        "stub_line",
        [
            "global.fetch = vi.fn()",
            "globalThis.fetch = vi.fn()",
            "vi.stubGlobal('fetch', vi.fn())",
            'vi.spyOn(global, "fetch")',
        ],
    )
    def test_each_way_of_replacing_the_seam_is_recognised(self, stub_line):
        content = f"import {{ vi }} from 'vitest'\n{stub_line}\nawait fetch('/api/runs')\n"
        offenders = detect_self_mocking_tests([{"name": "__tests__/z.test.ts", "content": content}])
        assert offenders == [("__tests__/z.test.ts", MOCKS_THE_NETWORK)]

    def test_a_non_test_file_is_ignored(self):
        """The delivered client seam legitimately calls fetch; it is not a test."""
        content = "export async function api(path: string) { return fetch(path) }\n"
        assert detect_self_mocking_tests([{"name": "lib/api.ts", "content": content}]) == []

    def test_the_two_detectors_do_not_reach_into_each_others_languages(self):
        """One module, two vocabularies. A Python stub-fallback is not a self-mocking
        suite and a TypeScript mock is not an ImportError guard; each detector seeing
        only its own extension is what keeps both heuristics conservative."""
        files = [
            {"name": "test_api.py", "content": _STUB_FALLBACK},
            {"name": "__tests__/runs.test.ts", "content": _SELF_MOCKING},
        ]
        assert detect_stub_fallback_tests(files) == ["test_api.py"]
        assert [path for path, _ in detect_self_mocking_tests(files)] == ["__tests__/runs.test.ts"]

    def test_multiple_offenders_are_sorted(self):
        files = [
            {"name": "__tests__/b.test.ts", "content": _SELF_MOCKING},
            {"name": "__tests__/a.spec.tsx", "content": _SELF_MOCKING},
            {"name": "__tests__/ok.test.ts", "content": _REAL_ADDITIVE},
        ]
        assert [path for path, _ in detect_self_mocking_tests(files)] == [
            "__tests__/a.spec.tsx",
            "__tests__/b.test.ts",
        ]

    @pytest.mark.parametrize(
        "files",
        [
            [],
            [{"name": "__tests__/empty.test.ts", "content": ""}],
            [{"name": "", "content": _SELF_MOCKING}],
            [{"content": _SELF_MOCKING}],
        ],
    )
    def test_empty_or_nameless_inputs_do_not_crash(self, files):
        assert detect_self_mocking_tests(files) == []
