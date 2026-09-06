"""#559: task-type identifiers are constants at the core — a literal outside the boundary
fails CI.

The defect class: ``"development.develop"``, ``"qa.test"`` … re-typed at every use site
(216 literals across 30 files when this landed, 97 across 23 at filing). A typo'd
comparison is silently never true; there is no rename point and nothing for tooling to
verify. And identity checks on one instance stand in for a property of the kind — the
overlay guard deleted in #558 said ``!= "qa.validate_repair"`` when it meant "steps that
emit product artifacts", so the next judgment-flavoured step would silently not have been
covered.

The boundary is ``squadops.tasks.task_types`` — the one module that spells the wire
strings — plus the places a string genuinely arrives from outside: the contract and
workload manifests (YAML), the request profiles (YAML), and tests. Everything else in
``src/`` and ``adapters/`` names a task type by its ``TaskType`` member.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from squadops.tasks.task_types import TaskType

_REPO = Path(__file__).resolve().parents[3]
_ROOTS = (_REPO / "src" / "squadops", _REPO / "adapters")

#: The boundary: files that may spell a task type as a string.
_BOUNDARY = {
    "src/squadops/tasks/task_types.py",
}

_VALUES = {member.value for member in TaskType}


def _literal_task_types(path: Path) -> list[tuple[int, str]]:
    """Every string constant in the file that equals a task-type wire value."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _VALUES:
                hits.append((node.lineno, node.value))
    return hits


def _core_files():
    for root in _ROOTS:
        for path in sorted(root.rglob("*.py")):
            rel = str(path.relative_to(_REPO))
            if rel in _BOUNDARY or "__pycache__" in path.parts:
                continue
            yield rel, path


def test_no_task_type_literal_outside_the_boundary():
    """Bug caught: the 217th literal — a new comparison, table key or handler declaration
    typed as a string, which the enum cannot see and a typo in which is silent."""
    violations = [
        f'  {rel}:{line}  "{value}"  → TaskType.{TaskType(value).name}'
        for rel, path in _core_files()
        for line, value in _literal_task_types(path)
    ]
    assert not violations, (
        f"{len(violations)} task-type literal(s) outside squadops.tasks.task_types — "
        "name the member (#559):\n" + "\n".join(violations)
    )


def test_every_handler_declares_a_member_not_a_string():
    """The handler registry is keyed on the declaration; a string there would still
    register (a StrEnum member is its string) and silently escape the enum."""
    from squadops.bootstrap.handlers import create_handler_registry

    registry = create_handler_registry()
    for task_type in registry.list_task_types():
        assert isinstance(task_type, TaskType), f"{task_type!r} is registered as a bare string"


def test_every_manifest_task_type_is_a_member():
    """The on-disk contracts and workloads name task types the enum must know — a
    manifest for a type the enum lacks is the stringly-typed addition this guard exists
    to catch, one layer out."""
    manifests = (_REPO / "src" / "squadops" / "capabilities" / "manifests").rglob("*.yaml")
    unknown = []
    for m in manifests:
        for match in re.finditer(r"^\s*task_type:\s*([\w.]+)\s*$", m.read_text(), re.M):
            if match.group(1) not in _VALUES:
                unknown.append(f"{m.relative_to(_REPO)}: {match.group(1)}")
    assert not unknown, "manifest task types absent from TaskType:\n  " + "\n  ".join(unknown)


@pytest.mark.parametrize("member", list(TaskType))
def test_a_member_is_its_wire_string(member):
    """Rule 1 — no serialization change: the member compares, hashes and formats as the
    string a profile, an envelope or a row carries."""
    assert member == member.value
    assert hash(member) == hash(member.value)
    assert f"{member}" == member.value
    assert TaskType(member.value) is member
