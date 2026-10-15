"""A deferred ``squadops`` import says why it is deferred, and every module loads as the first import (#2062).

What bugs would these catch?
- **A deferred import that has outlived its reason.** #1985 found 623 function-local ``squadops``
  imports in ``src/``, and 606 of them no longer guarded anything: they had been added to break a
  cycle that a later change removed, or copied from a neighbour that needed one. #2062 hoisted every
  one whose reason was gone. Each that stays carries ``# deferred (<kind>): <why>`` on the line above
  it, so a new one has to name its reason when it is written, and a reader can check it.
- **A module that cannot be the first import.** Hoisting changes import order process-wide, and a
  load cycle fails only when a process enters it at the wrong module. The suite imports every
  module, but in whatever order its tests run, so it never saw one: ``squadops.ports.sandbox`` failed
  as a first import on main (its models import ran the ``sandbox`` root, which re-exported the no-op
  sandbox, which imports the port back), while every test passed.

Only ``src/squadops`` is held. ``adapters/cycles`` holds the cycle orchestration, which moves into the
domain in 2.3 (#1992) and is measured then.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"

#: Why a ``squadops`` import may stay inside a function. Each kind is a fact a reader can check.
REASONS = {
    "cycle": "the module it imports loads this module at load time",
    "pair": "hoisting it would make two packages import each other at load",
    "optional": "it would load a package the base install lacks",
    "name": "this module defines a name the import would rebind",
    "pure": "it would bring I/O into a pure decision's load (test_pure_decisions_do_no_io)",
    "probe": "the import is itself the check (an ImportError is the answer)",
}


def _deferred_without_reason(source: str) -> list[str]:
    """Each function-local ``from squadops… import`` whose line above is not a known reason."""
    tree = ast.parse(source)
    lines = source.splitlines()
    type_only = {
        id(n)
        for top in ast.walk(tree)
        if isinstance(top, ast.If) and "TYPE_CHECKING" in ast.unparse(top.test)
        for n in ast.walk(top)
    }
    missing = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if not (
                isinstance(node, ast.ImportFrom)
                and not node.level
                and (node.module or "").startswith("squadops")
                and id(node) not in type_only
            ):
                continue
            above = lines[node.lineno - 2].strip() if node.lineno > 1 else ""
            kind = above.removeprefix("# deferred (").split(")", 1)[0]
            if not above.startswith("# deferred (") or kind not in REASONS:
                missing.append(f"{node.lineno}: {ast.unparse(node)}")
    return sorted(set(missing))


def test_every_deferred_squadops_import_says_why():
    missing = {
        str(path.relative_to(_SRC)): hits
        for path in sorted((_SRC / "squadops").rglob("*.py"))
        if (hits := _deferred_without_reason(path.read_text(encoding="utf-8")))
    }

    assert missing == {}, (
        "a function-local squadops import needs `# deferred (<kind>): <why>` on the line above, "
        f"with <kind> one of {sorted(REASONS)}; or hoist it: {missing}"
    )


@pytest.mark.parametrize(
    ("source", "missing"),
    [
        ("def f():\n    from squadops.cycles.models import Run\n", 1),
        (
            "def f():\n    # deferred (cycle): cycles.models loads this module\n"
            "    from squadops.cycles.models import Run\n",
            0,
        ),
        # A kind outside the vocabulary is no reason.
        ("def f():\n    # deferred (convenience): tidier\n    from squadops.cycles import x\n", 1),
        # The reason has to sit on the line above, not further up.
        ("def f():\n    # deferred (cycle): x\n    y = 1\n    from squadops.cycles import x\n", 1),
        # Not held: a module-level import, a type-only one, a third-party one, a relative one.
        ("from squadops.cycles.models import Run\n", 0),
        ("if TYPE_CHECKING:\n    def f():\n        from squadops.cycles import x\n", 0),
        ("def f():\n    from yaml import safe_load\n", 0),
        ("def f():\n    from .models import Run\n", 0),
    ],
)
def test_the_reason_rule_reads_each_form(source, missing):
    """Bugs caught: an unexplained deferral passing, an invented kind passing, a reason far from
    its import passing, and an import the rule does not hold being refused."""
    assert len(_deferred_without_reason(source)) == missing


def _modules() -> list[str]:
    names = []
    for path in sorted((_SRC / "squadops").rglob("*.py")):
        parts = path.relative_to(_SRC).with_suffix("").parts
        names.append(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return names


def _import_first(module: str) -> str | None:
    proc = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(_SRC), str(_SRC.parent)])},
    )
    return None if proc.returncode == 0 else f"{module}: {proc.stderr.strip().splitlines()[-1]}"


def test_every_module_loads_as_the_first_import():
    """One fresh interpreter per module, so each is entered first, as some process will enter it."""
    modules = _modules()
    with ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 2))) as pool:
        failures = [f for f in pool.map(_import_first, modules) if f]

    assert "squadops.ports.sandbox" in modules  # the module this guard was written for is held
    assert failures == []
