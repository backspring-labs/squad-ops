"""The packages' import direction is readable, and a leaf import loads a leaf's worth (#1985).

What bugs would these catch?
- **A package root that imports the layer again.** ``squadops/__init__`` re-exported the agents, the
  bootstrap and every handler, so importing ``squadops.cycles.naming`` loaded 144 modules and no
  guard could state a direction while every module imported everything. Re-adding one eager import
  to a package root fails the leaf-import bound below.
- **A new mutual dependency between two packages.** Each pair that imports the other at module level
  today is recorded with why it stands. A new pair fails, and so does a recorded pair that has gone,
  so the record stays the measured graph (the #1969 two-sided pattern).

Only module-level imports count: a function-local import and an ``if TYPE_CHECKING:`` block do not
run when the module loads.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"
_TWO_D = "the 2.3 structural batch"

#: Each pair of packages that import each other at module level, measured at #1985, with why it
#: stands. ``capabilities``/``cycles`` is the one #1985 names: the stacks extraction (#1993) moves
#: the stack registry out of ``capabilities``, which is most of ``cycles``'s side of it.
KNOWN_MUTUAL: dict[tuple[str, str], str] = {
    ("capabilities", "cycles"): f"the stack registry sits in capabilities; {_TWO_D} (#1993)",
    ("campaigns", "capabilities"): f"increment evaluation and the proposal handler; {_TWO_D}",
    ("campaigns", "ports"): "the campaign registry port names campaign models",
    ("capabilities", "ports"): "the capability ports name capability models",
    ("cycles", "events"): "cycle events name cycle models; the bus reads event types",
    ("ports", "prompts"): "the prompt port names prompt models",
    ("ports", "sandbox"): "the sandbox port names sandbox models",
    ("ports", "telemetry"): "the telemetry ports name telemetry models",
}

#: How many ``squadops`` modules a leaf may load (#1985 measured 4 for ``cycles.naming`` and 13 for
#: ``capabilities.scaffold`` once the roots were thinned, against 144 and 143 before).
_LEAF_BOUND = {"squadops.cycles.naming": 10, "squadops.capabilities.scaffold": 30}


def _module_level_package_edges() -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for path in (_SRC / "squadops").rglob("*.py"):
        parts = path.relative_to(_SRC).parts
        if len(parts) < 3:  # the package root and top-level modules belong to no package
            continue
        source = parts[1]
        for node in _module_level_imports(ast.parse(path.read_text())):
            names = (
                [node.module]
                if isinstance(node, ast.ImportFrom) and node.module
                else [a.name for a in getattr(node, "names", [])]
            )
            for name in names:
                if name and name.startswith("squadops.") and name.count(".") >= 1:
                    target = name.split(".")[1]
                    if target != source and (_SRC / "squadops" / target).is_dir():
                        edges.add((source, target))
    return edges


def _module_level_imports(tree: ast.Module) -> list[ast.stmt]:
    """Imports that run when the module loads: the top level and any block in it, but not a
    function body or an ``if TYPE_CHECKING:`` block."""
    found: list[ast.stmt] = []
    pending: list[ast.stmt] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        elif isinstance(node, ast.If) and getattr(node.test, "id", None) == "TYPE_CHECKING":
            pending.extend(node.orelse)
        else:
            for field in ("body", "orelse", "handlers", "finalbody"):
                pending.extend(getattr(node, field, None) or [])
    return found


def test_the_mutual_package_dependencies_are_exactly_the_recorded_ones():
    edges = _module_level_package_edges()
    mutual = {tuple(sorted(e)) for e in edges if (e[1], e[0]) in edges}

    new = sorted(mutual - set(KNOWN_MUTUAL))
    gone = sorted(set(KNOWN_MUTUAL) - mutual)
    assert not new, f"packages that now import each other at module level: {new}"
    assert not gone, f"recorded pairs that no longer import each other; drop them: {gone}"


@pytest.mark.parametrize(("leaf", "bound"), sorted(_LEAF_BOUND.items()))
def test_a_leaf_import_loads_a_leafs_worth_of_modules(leaf, bound):
    """In a fresh interpreter, so nothing the test run already imported counts."""
    code = (
        f"import sys; import {leaf}; "
        "print(sum(1 for m in sys.modules if m == 'squadops' or m.startswith('squadops.')))"
    )
    loaded = int(
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONPATH": str(_SRC)},
        ).stdout.strip()
    )

    assert loaded <= bound, f"importing {leaf} loads {loaded} squadops modules (bound {bound})"
