"""No squad-side package can reach the held-out scenarios (SIP-0113 §4.1; IR-4; #2413).

A scenario's steps reach the runner, never a squad role: not through a prompt, a task's inputs or
an agent's container. This holds it in the code. The packages that build what a squad agent reads
or runs import neither the scenarios' domain, nor their port, nor their store.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_contracts]

ROOT = Path(__file__).resolve().parents[3]
SQUAD_SIDE = ("agents", "capabilities", "prompts", "execution")
HELD_OUT = ("squadops.scenarios", "squadops.ports.scenarios", "adapters.scenarios")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_squad_side_module_imports_the_held_out_scenarios():
    """Bug caught: a handler, a prompt or the executor importing the scenario store, the first
    step of a scenario's steps reaching an authoring envelope or a squad task's inputs."""
    reached = sorted(
        f"{path.relative_to(ROOT)} imports {name}"
        for package in SQUAD_SIDE
        for path in (ROOT / "src" / "squadops" / package).rglob("*.py")
        for name in _imports(path)
        if name.startswith(HELD_OUT)
    )
    assert reached == []


def test_the_guard_reads_the_packages_it_names():
    """Bug caught: a renamed package leaving the guard above reading nothing, and passing."""
    for package in SQUAD_SIDE:
        assert any((ROOT / "src" / "squadops" / package).rglob("*.py")), package
