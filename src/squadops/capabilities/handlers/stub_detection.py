"""Detect stub-fallback anti-patterns in generated test files (#276).

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
