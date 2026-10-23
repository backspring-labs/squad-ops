"""The packages' import direction is readable, and a leaf import loads a leaf's worth (#1985).

What bugs would these catch?
- **A package root that imports the layer again.** ``squadops/__init__`` re-exported the agents, the
  bootstrap and every handler, so importing ``squadops.cycles.naming`` loaded 144 modules and no
  guard could state a direction while every module imported everything. Re-adding one eager import
  to a package root fails the leaf-import bound below.
- **A new mutual dependency between two packages.** Each pair that imports the other at module level
  today is recorded with why it stands. A new pair fails, and so does a recorded pair that has gone,
  so the record stays the measured graph (the #1969 two-sided pattern).
- **A stack module reaching up again (#1993).** ``squadops.stacks`` is read by both sides, the cycle
  domain and the capability handlers, so it imports neither. One upward import, deferred or not,
  makes a stack change a change to three packages again, which is what the extraction ended.

The mutual-pair record counts only module-level imports: a function-local import and an
``if TYPE_CHECKING:`` block do not run when the module loads. The stacks rule counts every import
statement, since a deferred import is still a dependency: 22 of the 27 that made the old hub were.
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
#: stands. ``capabilities``/``cycles`` is the one #1985 names. The stacks extraction (#1993) took its
#: hub, the stack registry, out of ``capabilities``: ``cycles``'s module-level imports of
#: ``capabilities`` went from 14 to 8, and the 8 left are task contracts, not stacks.
KNOWN_MUTUAL: dict[tuple[str, str], str] = {
    ("capabilities", "cycles"): (
        "the handlers read the cycle domain; the task plan reads the context-assembly contracts, "
        "build profiles and reasoning policy, and the pulse models the capability models"
    ),
    ("campaigns", "capabilities"): f"increment evaluation and the proposal handler; {_TWO_D}",
    ("campaigns", "ports"): "the campaign registry port names campaign models",
    ("capabilities", "ports"): "the capability ports name capability models",
    ("cycles", "events"): "cycle events name cycle models; the bus reads event types",
    ("outcomes", "ports"): (
        "the outcomes port names outcome models, and the proposal's evidence reader implements it "
        "over the stores' ports (SIP-0113 §10t ruling 1)"
    ),
    ("ports", "prompts"): "the prompt port names prompt models",
    ("ports", "sandbox"): "the sandbox port names sandbox models",
    ("ports", "telemetry"): "the telemetry ports name telemetry models",
}

#: How many ``squadops`` modules a leaf may load (#1985 measured 4 for ``cycles.naming`` and 13 for
#: the scaffold once the roots were thinned, against 144 and 143 before; #1993 moved the scaffold from
#: ``capabilities`` to ``stacks``, and it still loads 13).
_LEAF_BOUND = {"squadops.cycles.naming": 10, "squadops.stacks.scaffold": 30}


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


_UPWARD = ("squadops.capabilities", "squadops.cycles")


def _upward_imports(tree: ast.Module) -> list[str]:
    """Every import statement in ``tree`` naming ``capabilities`` or ``cycles``, wherever it sits."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            continue
        if any(n == up or n.startswith(up + ".") for n in names for up in _UPWARD):
            found.append(f"{node.lineno}: {ast.unparse(node)}")
    return found


def test_the_stacks_import_neither_capabilities_nor_cycles():
    upward = {
        str(path.relative_to(_SRC)): hits
        for path in sorted((_SRC / "squadops" / "stacks").rglob("*.py"))
        if (hits := _upward_imports(ast.parse(path.read_text())))
    }

    assert upward == {}, f"stack modules importing capabilities or cycles: {upward}"


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("def f():\n    from squadops.cycles.models import Run\n", 1),
        ("if TYPE_CHECKING:\n    from squadops.capabilities.models import X\n", 1),
        ("from squadops import cycles\n", 1),
        ("import squadops.capabilities.handlers.base as b\n", 1),
        # A stack-side read of the sandbox's environment contract is allowed, and a module whose
        # name only starts like an upward one is not upward.
        ("from squadops.sandbox.environment import get_environment_contract\n", 0),
        ("from squadops.cyclesx import y\n", 0),
    ],
)
def test_the_stacks_rule_reads_every_form_of_import(source, found):
    """Bugs caught: a deferred, type-only or package-form import slipping past the stacks rule, and
    the rule refusing a sibling package whose name begins like ``cycles``."""
    assert len(_upward_imports(ast.parse(source))) == found


def test_loading_the_stacks_loads_neither_capabilities_nor_cycles():
    """In a fresh interpreter, every stacks module and the one module outside the package a stacks
    module reads (``sandbox.environment``, deferred in ``rendered_packaging``). Bug caught: an upward
    route through a package the stacks may import, which the per-statement rule above cannot see."""
    stacks = sorted(
        p.stem for p in (_SRC / "squadops" / "stacks").glob("*.py") if p.stem != "__init__"
    )
    code = (
        "import importlib, sys\n"
        f"for m in {stacks!r}: importlib.import_module('squadops.stacks.' + m)\n"
        "import squadops.sandbox.environment\n"
        f"print(sorted(m for m in sys.modules if m.startswith({_UPWARD!r})))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": str(_SRC)},
    ).stdout.strip()

    assert "scaffold" in stacks  # the glob found the package
    assert loaded == "[]", f"loading the stacks loads: {loaded}"
