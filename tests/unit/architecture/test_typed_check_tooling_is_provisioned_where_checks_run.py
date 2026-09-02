"""Every tool a typed check's evaluator needs is provisioned in every role image that
evaluates typed checks — or the gap is declared, with its reason (#1229, rule B).

The 1.7.0 line paid for the missing half of this: ``undefined_names`` covered ``.py``
only because no image had a TypeScript analyser, and a repair on the Next.js stack could
never be verified because the environment judging it had no node. #1216 made a missing
LANGUAGE declarable; this makes a missing TOOL, per environment, declarable — and read
from the provisioning data the images are built from, never from a second list that says
what someone believed the images contained.

Roles are derived from the handlers: a module under ``handlers/`` that calls
``_evaluate_typed_acceptance`` evaluates typed checks in its ``_role``. Provisioning is
read from ``agents/instances/<role>/system-packages.txt`` (apt) and
``npm-global-packages.txt`` (npm globals), the files ``agents/Dockerfile`` installs from.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from squadops.cycles.acceptance_check_spec import (
    CHECK_ENV_TOOLS,
    DECLARED_TOOLING_GAPS,
    required_tooling_by_check,
)

pytestmark = [pytest.mark.domain_capabilities]

REPO_ROOT = Path(__file__).resolve().parents[3]
HANDLERS = REPO_ROOT / "src" / "squadops" / "capabilities" / "handlers"
INSTANCES = REPO_ROOT / "agents" / "instances"

#: How a tool name in ``required_tooling`` is recognised in the provisioning data: the
#: apt package that provides it, or the npm global that provides it.
_APT_PROVIDES = {"node": "nodejs", "npm": "npm"}
_NPM_GLOBAL_PROVIDES = {"tsc": "typescript"}


def _packages(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _provisioned(role: str) -> set[str]:
    apt = _packages(INSTANCES / role / "system-packages.txt")
    globals_ = {p.split("@", 1)[0] for p in _packages(INSTANCES / role / "npm-global-packages.txt")}
    tools = {tool for tool, pkg in _APT_PROVIDES.items() if pkg in apt}
    tools |= {tool for tool, pkg in _NPM_GLOBAL_PROVIDES.items() if pkg in globals_}
    return tools


def _roles_that_evaluate_typed_checks() -> set[str]:
    roles: set[str] = set()
    for path in HANDLERS.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "_evaluate_typed_acceptance(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_role" for t in node.targets
            ):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    roles.add(node.value.value)
    return roles


def test_the_roles_are_derived_not_assumed():
    """If this set changes, a handler started or stopped evaluating typed checks in a role
    — the provisioning question below changes with it."""
    assert _roles_that_evaluate_typed_checks() == {"builder", "dev", "qa"}


def test_every_tool_a_check_needs_is_provisioned_or_declared_absent_per_role():
    """Bug caught: a check whose evaluator shells out to a tool no image provides — the
    #939 shape, where the check silently covered less than it claimed for five weeks."""
    missing: list[str] = []
    for role in sorted(_roles_that_evaluate_typed_checks()):
        have = _provisioned(role)
        for check, tools in sorted(required_tooling_by_check().items()):
            for tool in sorted(tools):
                if tool in have or (role, tool) in DECLARED_TOOLING_GAPS:
                    continue
                missing.append(f"{role}: {check} needs {tool}")
    assert missing == [], (
        "a role evaluates typed checks without the tool a check needs, and does not say "
        "so — provision it in agents/instances/<role>/ or declare the gap with its reason "
        "in DECLARED_TOOLING_GAPS:\n" + "\n".join(missing)
    )


def test_no_declared_gap_outlives_the_gap():
    """Two-sided: a gap declared for a role that now provisions the tool, or for a role
    that evaluates no typed checks, is a stale disclosure — remove it."""
    roles = _roles_that_evaluate_typed_checks()
    needed = {t for tools in required_tooling_by_check().values() for t in tools}
    stale = [
        f"{role}: {tool}"
        for (role, tool) in sorted(DECLARED_TOOLING_GAPS)
        if role not in roles or tool not in needed or tool in _provisioned(role)
    ]
    assert stale == [], "declared tooling gaps that no longer hold:\n" + "\n".join(stale)


def test_the_environment_union_carries_every_provisioned_tool():
    """``CHECK_ENV_TOOLS`` is the union the command safelist is checked against at import;
    a tool provisioned in any role and missing there would let the safelist refuse a form
    the images can run."""
    provisioned = set().union(*(_provisioned(r) for r in _roles_that_evaluate_typed_checks()))
    assert provisioned <= CHECK_ENV_TOOLS, sorted(provisioned - CHECK_ENV_TOOLS)
