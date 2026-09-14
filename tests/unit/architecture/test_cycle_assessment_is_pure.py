"""SIP-0108 §4.1 (a) / §5 criterion 1 — the cycle assessment performs no I/O.

``assess`` reads only ``CycleOutcome`` and ``CycleEvidence`` (and the caller-supplied assessor
identity, §10c). Held by imports: the module's whole module-level import closure reaches no
store, port, adapter, network client, clock or environment, and the module itself calls none.

Bug caught: a registry read, a vault fetch, a ``datetime.now()`` or a config lookup added inside
the projection — an assessment that changes when nothing in its evidence did, which the
evidence identity could no longer vouch for.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_orchestration]

REPO = Path(__file__).resolve().parents[3]
MODULE = "squadops.cycles.cycle_assessment"

#: Prefixes the closure must not reach: stores and their ports, the wiring, the network, the
#: clock and the process environment.
FORBIDDEN = (
    "adapters",
    "squadops.ports",
    "squadops.api",
    "squadops.config",
    "squadops.runtime",
    "squadops.llm",
    "squadops.agents",
    "squadops.telemetry",
    "squadops.events",
    "asyncpg",
    "aio_pika",
    "httpx",
    "requests",
    "urllib",
    "socket",
    "subprocess",
    "asyncio",
    "os",
    "time",
)


def _module_file(name: str) -> Path | None:
    parts = name.split(".")
    if parts[0] == "squadops":
        base = REPO / "src" / Path(*parts)
    elif parts[0] == "adapters":
        base = REPO / Path(*parts)
    else:
        return None
    if base.with_suffix(".py").exists():
        return base.with_suffix(".py")
    if (base / "__init__.py").exists():
        return base / "__init__.py"
    return None


def _module_level_imports(path: Path) -> list[str]:
    """Imports that run at import time — not ``TYPE_CHECKING`` blocks, not function bodies."""
    out: list[str] = []

    def visit(nodes: list[ast.stmt]) -> None:
        for node in nodes:
            if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.Import):
                out.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                out.append(node.module)
            visit([c for c in ast.iter_child_nodes(node) if isinstance(c, ast.stmt)])

    visit(ast.parse(path.read_text(encoding="utf-8")).body)
    return out


def _closure(root: str) -> tuple[set[str], set[str]]:
    """(first-party modules reached, third-party/stdlib top-level names reached)."""
    seen: set[str] = set()
    external: set[str] = set()
    stack = [root]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        path = _module_file(name)
        if path is None:
            parent = name.rsplit(".", 1)[0]
            if name.startswith(("squadops.", "adapters.")) and _module_file(parent):
                stack.append(parent)
            else:
                external.add(name)
            continue
        seen.add(name)
        stack.extend(_module_level_imports(path))
    return seen, external


def _forbidden(name: str) -> bool:
    return any(name == f or name.startswith(f + ".") for f in FORBIDDEN)


def test_the_projections_import_closure_reaches_no_io_surface():
    first_party, external = _closure(MODULE)

    assert MODULE in first_party
    offenders = sorted(n for n in first_party | external if _forbidden(n))
    assert offenders == [], f"the assessment's import closure reaches I/O surfaces: {offenders}"


def test_the_projection_calls_no_clock_file_or_environment():
    source = (REPO / "src" / "squadops" / "cycles" / "cycle_assessment.py").read_text()
    calls = {
        ast.unparse(node.func) for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)
    }
    banned = [
        c
        for c in calls
        if c in ("open", "input", "print")
        or c.endswith((".now", ".utcnow", ".today", "getenv", ".read_text", ".read_bytes"))
    ]
    assert banned == []


def test_assess_reads_two_arguments_and_a_declared_assessor():
    """The signature is the contract: the outcome, the evidence, and the assessor identity the
    caller supplies (never read inside)."""
    from squadops.cycles.cycle_assessment import assess

    params = inspect.signature(assess).parameters
    assert [(p.name, p.kind) for p in params.values()] == [
        ("outcome", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ("evidence", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ("assessor", inspect.Parameter.KEYWORD_ONLY),
    ]
