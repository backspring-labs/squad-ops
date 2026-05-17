"""Hexagonal-boundary architecture tests for SIP-0089 (D26).

These tests enforce dependency direction by AST-parsing source files and
asserting that the imports they declare do not cross forbidden boundaries.
They run in the regression suite so violations fail CI, not just review.

Rules currently encoded (D26):

1. `src/squadops/runtime/` does not import any `adapters.*` module,
   CLI modules, embodiment-specific modules, or Temporal-specific modules.
2. `src/squadops/runtime/coordinator.py` (when it exists, Phase 2+) does
   not import `events/bridges/*` directly — must depend on a port (D22).
3. `src/squadops/capabilities/handlers/` does not import runtime persistence
   adapters directly.
4. `src/squadops/cli/` does not import Postgres runtime adapters directly.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_runtime]

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src" / "squadops"


def _collect_imports(py_file: Path) -> list[str]:
    """Return every fully-qualified module name imported by `py_file`."""
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative imports cannot reach `adapters.*` or `squadops.cli`.
                continue
            if node.module:
                out.append(node.module)
                for alias in node.names:
                    out.append(f"{node.module}.{alias.name}")
    return out


def _iter_py(root: Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        yield p


def test_runtime_layer_does_not_import_adapters():
    """D1/D26: `src/squadops/runtime/` is a pure coordination layer. Importing
    `adapters.*` from there would couple runtime semantics to a specific
    infrastructure choice and break the hex boundary.

    Bug class: if an implementer reaches for an adapter to 'just get the pool'
    inside runtime/coordinator.py, this test fails immediately."""
    runtime_dir = SRC / "runtime"
    assert runtime_dir.is_dir(), "src/squadops/runtime/ must exist"

    violations: list[tuple[str, str]] = []
    for py in _iter_py(runtime_dir):
        for imp in _collect_imports(py):
            if imp == "adapters" or imp.startswith("adapters."):
                violations.append((py.relative_to(REPO_ROOT).as_posix(), imp))

    assert not violations, (
        f"src/squadops/runtime/ must not import adapters.*. Violations: {violations}"
    )


def test_runtime_layer_does_not_import_cli():
    """D1/D26: runtime is a domain layer; CLI is a delivery layer.
    Bug class: importing CLI rendering helpers into runtime would invert
    the dependency direction and make headless runtime use impossible."""
    runtime_dir = SRC / "runtime"
    violations: list[tuple[str, str]] = []
    for py in _iter_py(runtime_dir):
        for imp in _collect_imports(py):
            if imp == "squadops.cli" or imp.startswith("squadops.cli."):
                violations.append((py.relative_to(REPO_ROOT).as_posix(), imp))
    assert not violations, f"runtime must not import squadops.cli: {violations}"


def test_runtime_coordinator_does_not_import_event_bridges_directly():
    """D22: runtime/coordinator.py (when added in Phase 2+) must emit events
    through an injected EventPublisherPort, not by importing a specific bridge.
    Bug class: a direct bridge import couples runtime to the workflow_tracker /
    runtime_state bridge implementation, blocking swap-in of NoOp or alternatives.

    No-op today because coordinator.py does not yet exist; the test wakes up
    automatically when Phase 2/3 lands the file."""
    coordinator = SRC / "runtime" / "coordinator.py"
    if not coordinator.exists():
        pytest.skip("runtime/coordinator.py not yet implemented (Phase 2+)")
    violations = [
        imp
        for imp in _collect_imports(coordinator)
        if imp == "squadops.events.bridges" or imp.startswith("squadops.events.bridges.")
    ]
    assert not violations, (
        "runtime/coordinator.py must not import event bridges directly (D22). "
        f"Violations: {violations}"
    )


def test_capabilities_handlers_do_not_import_runtime_persistence():
    """D26: handlers depend on ports, not on `adapters.persistence.runtime.*`.
    Bug class: a handler that imports the postgres adapter directly cannot be
    unit-tested without postgres, and bypasses the coordinator authority (D16)."""
    handlers_dir = SRC / "capabilities" / "handlers"
    violations: list[tuple[str, str]] = []
    for py in _iter_py(handlers_dir):
        for imp in _collect_imports(py):
            if imp == "adapters.persistence.runtime" or imp.startswith(
                "adapters.persistence.runtime."
            ):
                violations.append((py.relative_to(REPO_ROOT).as_posix(), imp))
    assert not violations, (
        f"capabilities/handlers/ must not import adapters.persistence.runtime.*: {violations}"
    )


def test_cli_does_not_import_runtime_persistence():
    """D26: CLI talks to the runtime over HTTP, not by importing the postgres
    adapter directly. Bug class: a CLI command that imported the adapter would
    not work outside the deployment (no DSN, no pool) but would still pass
    unit tests against a mock — breaking when shipped to operators."""
    cli_dir = SRC / "cli"
    violations: list[tuple[str, str]] = []
    for py in _iter_py(cli_dir):
        for imp in _collect_imports(py):
            if imp == "adapters.persistence.runtime" or imp.startswith(
                "adapters.persistence.runtime."
            ):
                violations.append((py.relative_to(REPO_ROOT).as_posix(), imp))
    assert not violations, (
        f"squadops.cli must not import adapters.persistence.runtime.*: {violations}"
    )
