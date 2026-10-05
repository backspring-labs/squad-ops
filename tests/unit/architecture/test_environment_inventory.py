"""Every environment read outside the config loader is in the inventory, and every row is read
(#1991, ``docs/architecture/environment.md``).

What bugs would these catch? A new ``os.getenv`` that opens a configuration path the config
loader, its secrets provider and the deploy record never see (``LLM_MODEL`` was one: a model
selection nothing set and nothing recorded); a ``SQUADOPS__*`` variable read around the loader (the
health checker read Keycloak's admin password from the raw environment, so a ``secret://`` value
would have been sent literally); and a row left behind after its read is removed, so the
inventory claims a path that no longer exists.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_DOC = _REPO / "docs" / "architecture" / "environment.md"
_ROOTS = ("src", "adapters")
_CONFIG = "src/squadops/config/"


def _is_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _string_constants() -> dict[str, set[str]]:
    """Module-level ``NAME = "..."`` constants across the tree, so a read through an imported
    name (``os.environ.get(TEST_DB_PASSWORD_ENV)``) resolves to the variable it names."""
    found: dict[str, set[str]] = defaultdict(set)
    for path in _sources():
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            found[target.id].add(node.value.value)
    return found


def _sources() -> list[Path]:
    return [p for root in _ROOTS for p in sorted((_REPO / root).rglob("*.py"))]


def _reads() -> tuple[dict[str, set[str]], set[str]]:
    """``(variable → the files that read it, files with a computed name)``."""
    constants = _string_constants()
    named: dict[str, set[str]] = defaultdict(set)
    dynamic: set[str] = set()
    for path in _sources():
        rel = str(path.relative_to(_REPO))
        for node in ast.walk(ast.parse(path.read_text())):
            arg = None
            if isinstance(node, ast.Call) and node.args:
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "getenv"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "os"
                ) or (
                    isinstance(func, ast.Attribute)
                    and func.attr in ("get", "setdefault", "pop")
                    and _is_environ(func.value)
                ):
                    arg = node.args[0]
            elif isinstance(node, ast.Subscript) and _is_environ(node.value):
                arg = node.slice
            if arg is None:
                continue
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                named[arg.value].add(rel)
            elif isinstance(arg, ast.Name) and len(constants.get(arg.id, ())) == 1:
                named[next(iter(constants[arg.id]))].add(rel)
            else:
                dynamic.add(rel)
    return named, dynamic


def _inventory() -> tuple[dict[str, set[str]], set[str]]:
    """The doc's two tables: ``(variable → its readers, files with a dynamic read)``."""
    text = _DOC.read_text()
    named_section = text.split("## Named variables", 1)[1].split("## Dynamic reads", 1)[0]
    dynamic_section = text.split("## Dynamic reads", 1)[1].split("## Removed", 1)[0]
    named: dict[str, set[str]] = {}
    for line in named_section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("`"):
            named[cells[0].strip("`")] = set(re.findall(r"`([^`]+\.py)`", cells[1]))
    dynamic = set(re.findall(r"^\| `([^`]+\.py)` \|", dynamic_section, re.MULTILINE))
    return named, dynamic


def test_every_variable_read_outside_the_loader_is_in_the_inventory_with_its_reader():
    read, _ = _reads()
    listed, _ = _inventory()

    unlisted = []
    for variable, files in sorted(read.items()):
        outside = {
            f for f in files if not (variable.startswith("SQUADOPS__") and f.startswith(_CONFIG))
        }
        missing = outside - listed.get(variable, set())
        if missing:
            unlisted.append(f"{variable}: read by {sorted(missing)}")

    assert not unlisted, (
        "environment reads outside the config loader that docs/architecture/environment.md does "
        "not list (route it through config, or list it with why it cannot be):\n  "
        + "\n  ".join(unlisted)
    )


def test_every_inventory_row_is_read_by_the_files_it_names():
    read, dynamic = _reads()
    listed, listed_dynamic = _inventory()

    stale = [
        f"{variable}: {sorted(files - read.get(variable, set()))}"
        for variable, files in sorted(listed.items())
        if files - read.get(variable, set())
    ]
    stale += [f"dynamic read in {f}" for f in sorted(listed_dynamic - dynamic)]

    assert not stale, "inventory rows nothing reads any more:\n  " + "\n  ".join(stale)


def test_a_computed_variable_name_is_read_only_where_the_inventory_says_what_decides_it():
    _, dynamic = _reads()
    _, listed_dynamic = _inventory()

    assert dynamic <= listed_dynamic, sorted(dynamic - listed_dynamic)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('import os\nos.getenv("LLM_MODEL")\n', {"LLM_MODEL"}),
        ('import os\nos.environ["X_Y"]\n', {"X_Y"}),
        ('import os\nos.environ.get("A", "d")\n', {"A"}),
    ],
)
def test_the_survey_sees_each_form_of_read(tmp_path, monkeypatch, source, expected):
    """The guard is only as wide as its survey: each read form must be found."""
    module = tmp_path / "src" / "m.py"
    module.parent.mkdir()
    module.write_text(source)
    monkeypatch.setattr(__import__(__name__, fromlist=["_REPO"]), "_REPO", tmp_path)

    read, dynamic = _reads()

    assert set(read) == expected and dynamic == set()
