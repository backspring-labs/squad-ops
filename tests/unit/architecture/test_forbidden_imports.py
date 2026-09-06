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
5. (#154) Every `src/squadops` package: `adapters.*` is imported ONLY from a declared
   composition root — the runtime API's wiring, the agent entrypoint, the sandbox
   service's main, and the bootstrap package. Two-sided: a root that no longer wires
   adapters is stale and fails too.
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


#: The composition roots — the only modules under src/squadops that may import
#: ``adapters.*`` — each with the reason it wires infrastructure (#154). A new root is a
#: deliberate decision recorded here, never a default; a domain module reaching for an
#: adapter ("just get the pool") fails the test below.
COMPOSITION_ROOTS: dict[str, str] = {
    "squadops.api.runtime": "the runtime API's wiring — deps, main, scheduler_bootstrap",
    "squadops.agents.entrypoint": "the agent container's wiring: queue, LLM, memory, prompts, telemetry",
    "squadops.sandbox.main": "the sandbox service's wiring",
    "squadops.bootstrap": "the bootstrap package: system composition, the doctor's checks, the secrets provider",
}


def _module_name(py: Path) -> str:
    rel = py.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_under(module: str, root: str) -> bool:
    return module == root or module.startswith(root + ".")


def test_only_composition_roots_import_adapters():
    """#154: the hexagonal boundary, whole. Before this the guard covered four directories
    and the orchestrator lazily imported the NoOp observability adapter, the config loader
    imported the secrets factory — deliberate patterns with the import pointing the wrong
    way. Bug class: a domain module that imports an adapter cannot be tested without that
    infrastructure and cannot have the adapter swapped from the composition root."""
    violations: list[tuple[str, str]] = []
    for py in _iter_py(SRC):
        module = _module_name(py)
        if any(_is_under(module, root) for root in COMPOSITION_ROOTS):
            continue
        for imp in _collect_imports(py):
            if imp == "adapters" or imp.startswith("adapters."):
                violations.append((py.relative_to(REPO_ROOT).as_posix(), imp))
    assert not violations, (
        "only the composition roots import adapters.* (#154) — inject the port from a "
        f"root in COMPOSITION_ROOTS instead. Violations: {violations}"
    )


def test_every_declared_composition_root_still_wires_adapters():
    """The other side: a root listed here that imports no adapter is a stale entry that
    would quietly license the next domain module placed under it."""
    stale = []
    for root, _reason in COMPOSITION_ROOTS.items():
        wires = any(
            imp == "adapters" or imp.startswith("adapters.")
            for py in _iter_py(SRC)
            if _is_under(_module_name(py), root)
            for imp in _collect_imports(py)
        )
        if not wires:
            stale.append(root)
    assert not stale, f"composition roots that import no adapters (stale allowlist): {stale}"


@pytest.mark.parametrize(
    "module", ["squadops.orchestration.orchestrator", "squadops.config.loader"]
)
def test_the_two_named_leaks_are_closed(module):
    """The sites #154 named: the orchestrator's NoOp fallback and the loader's secrets
    factory. Kept by name so the fix cannot regress under the general rule's allowlist."""
    py = SRC.parent / Path(*module.split(".")).with_suffix(".py")
    assert not [imp for imp in _collect_imports(py) if imp.startswith("adapters")]
