"""Detect generated test files that validate something other than the deliverable.

Two patterns live here, found four months apart in different languages, because they
are one defect wearing two coats: **the suite runs, passes, and never invokes the
application.** Whatever else differs, that is the shared shape, and it is why this
module is the seam rather than two parallel ones.

The module name predates the second pattern and now understates it — nothing here is
specific to stubs any more. Renaming it touches two call sites and their tests and is
deliberately not bundled into a fix landing under a deploy freeze; recorded so the next
reader knows the name is stale rather than the scope narrow.

Detect stub-fallback anti-patterns in generated test files (#276).

A generated test that wraps the entrypoint import in ``except ImportError:`` and
reconstructs the application inline silently validates a **stub** instead of the
delivered module. A structurally broken deliverable (e.g. ``backend/main.py``
missing ``from pydantic import BaseModel``) then passes ``qa.test`` green,
because pytest collects and runs the inline fallback app rather than failing on
the import. This masks the exact class of defect acceptance exists to catch.

This module flags that pattern so the qa acceptance path can fail the task
(triggering the SIP-0086 correction loop to regenerate the test without the
fallback) rather than green-lighting a non-runnable deliverable.

The check is a deliberately conservative heuristic: a test file is flagged only
when it *both* guards an import with ``except ImportError``/``ModuleNotFoundError``
*and* constructs a web-app object in the file (the fallback re-implementation).
That combination is the stub-fallback pattern; a test that merely catches an
optional-dependency ImportError without rebuilding an app is not flagged.
"""

from __future__ import annotations

import re

# Web-app constructors whose presence alongside an import guard signals that the
# test rebuilt the app inline as a fallback (the stub).
_APP_CONSTRUCTORS: tuple[str, ...] = (
    "FastAPI(",
    "Flask(",
    "APIRouter(",
    "Starlette(",
    "express(",
)

# Matches `except ImportError`, `except ModuleNotFoundError`, and the tuple forms
# `except (ImportError, ...)` / `except (ModuleNotFoundError, ...)`.
_IMPORT_GUARD = re.compile(r"except\s*\(?\s*(?:ImportError|ModuleNotFoundError)\b")


def _is_test_file(path: str) -> bool:
    """True for python test files (``test_*.py`` / ``*_test.py``)."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    if not name.endswith(".py"):
        return False
    return name.startswith("test_") or name.endswith("_test.py")


def _file_field(f: dict) -> tuple[str, str]:
    """Extract (path, content) from an artifact/extracted-file dict.

    Handles both the extracted-file shape (``filename``) and the artifact shape
    (``name``); falls back to ``path``.
    """
    path = f.get("filename") or f.get("path") or f.get("name") or ""
    return path, (f.get("content") or "")


def detect_stub_fallback_tests(files: list[dict]) -> list[str]:
    """Return the paths of generated test files that hide a broken entrypoint
    import behind an ``ImportError`` fallback that reconstructs the app.

    Args:
        files: extracted-file or artifact dicts (each with a name/filename/path
            and ``content``).

    Returns:
        Sorted list of offending file paths (empty when none are found).
    """
    offenders: list[str] = []
    for f in files:
        path, content = _file_field(f)
        if not path or not _is_test_file(path):
            continue
        if _IMPORT_GUARD.search(content) and any(ctor in content for ctor in _APP_CONSTRUCTORS):
            offenders.append(path)
    return sorted(offenders)


# --- Self-mocking suites (#915) -------------------------------------------------
#
# The TypeScript sibling of the stub-fallback class, and strictly worse: a stub-fallback
# suite reconstructs the app and then FAILS, because a reconstruction does not behave
# like the real thing. A self-mocking suite tells a mock what to return and asserts what
# it was told, so **its natural state is passing.** It agrees with itself by construction.
#
# Found in window roll 3 (`cyc_b20f58cc7cbc`): 479 lines that set `global.fetch = vi.fn()`,
# primed the mock, called `fetch('/api/runs')`, and asserted on the primed value. The
# application was never invoked. That roll only went red because its scaffold slots were
# also unfilled; had they been filled, `tests_pass` would have gone green on the fills
# while this file read as 479 lines of verification.
#
# Fills cannot do this — SIP-0104's frozen spine imports the route handler and invokes it,
# and region enforcement rejects any edit to that. Additive files carry the same rule as
# prose in the brief and nothing enforced it. This closes that asymmetry.

#: Suffixes of the JS/TS test files a qa author emits. Python suites take the
#: stub-fallback path above; the two vocabularies never overlap.
_JS_TEST_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
)

#: Replacing the network seam. Under the in-process execution model (#877) a suite reaches
#: the app by importing its route handler, so there is no fetch for a correct suite to
#: stub — the presence of a stub means the suite is talking to something it built.
_NETWORK_SEAM_MOCK = re.compile(
    r"""(?x)
      global(?:This)?\s*\.\s*fetch\s*=                          # global.fetch = ...
    | (?:vi|jest)\s*\.\s*stubGlobal\s*\(\s*['"`]fetch['"`]      # vi.stubGlobal('fetch', ...)
    | (?:vi|jest)\s*\.\s*spyOn\s*\(\s*global(?:This)?\s*,\s*['"`]fetch['"`]
    """
)

#: Mocking the subject itself. Unconditional: there is no reading under which replacing
#: the route module under test and then asserting on it verifies the route module.
_ROUTE_MODULE_MOCK = re.compile(r"""(?:vi|jest)\s*\.\s*mock\s*\(\s*['"`][^'"`]*app/api/""")

#: A real import of an application route module — the in-process model's entry point.
#: Required as a *statement* rather than as any occurrence of the path, so that a
#: ``vi.mock('@/app/api/...')`` string cannot satisfy it.
_APP_ROUTE_IMPORT = re.compile(
    r"""^\s*(?:import\b[^\n]*?from\s*|.*\brequire\s*\(\s*)['"`][^'"`]*app/api/""",
    re.MULTILINE,
)

MOCKS_THE_SUBJECT = "mocks the route module under test and asserts on the mock"
MOCKS_THE_NETWORK = (
    "replaces the fetch seam and imports no route module, so the application is "
    "never invoked — the suite asserts what it told its own mock to return"
)


def _is_js_test_file(path: str) -> bool:
    """True for the JS/TS test files a qa author emits (``*.test.ts`` / ``*.spec.tsx``…)."""
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.endswith(_JS_TEST_SUFFIXES)


def detect_self_mocking_tests(files: list[dict]) -> list[tuple[str, str]]:
    """Return ``(path, reason)`` for generated suites that assert against their own mock.

    Deliberately two-clause and conservative, mirroring the stub-fallback heuristic. A
    suite that mocks an *outbound* call while still importing and invoking the real route
    handler is legitimate and is not flagged — mocking is not the defect, mocking
    **instead of** invoking is. The discriminator is whether an application route module
    is imported at all.

    Args:
        files: extracted-file or artifact dicts (each with a name/filename/path
            and ``content``).

    Returns:
        Sorted ``(path, reason)`` pairs; empty when none are found.
    """
    offenders: list[tuple[str, str]] = []
    for f in files:
        path, content = _file_field(f)
        if not path or not _is_js_test_file(path):
            continue
        if _ROUTE_MODULE_MOCK.search(content):
            offenders.append((path, MOCKS_THE_SUBJECT))
        elif _NETWORK_SEAM_MOCK.search(content) and not _APP_ROUTE_IMPORT.search(content):
            offenders.append((path, MOCKS_THE_NETWORK))
    return sorted(offenders)


# --- What the detectors were actually shown (#986) ------------------------------
#
# Both detectors above report offenders and nothing else, so a clean result is
# indistinguishable from a detector that was never reached — or that was reached
# with the wrong file list. Diagnosing one absent row in `cyc_6651d552e06a` cost an
# hour precisely because the run record could not answer "did it look, and at what?".
#
# These return the inventory each detector inspects, so a caller can bank a row
# whether or not it found anything. An empty inventory alongside an executed suite
# is then a visible fact rather than a silence.


CHECK_NO_STUB_FALLBACK = "no_stub_fallback_tests"
CHECK_NO_SELF_MOCKING = "no_self_mocking_tests"


def inspected_python_test_paths(files: list[dict]) -> list[str]:
    """Return the paths ``detect_stub_fallback_tests`` will actually examine."""
    return sorted(path for path, _ in map(_file_field, files) if path and _is_test_file(path))


def inspected_js_test_paths(files: list[dict]) -> list[str]:
    """Return the paths ``detect_self_mocking_tests`` will actually examine."""
    return sorted(path for path, _ in map(_file_field, files) if path and _is_js_test_file(path))
