"""Provisioned-tooling resolver (SIP-0096 §6.3/§8).

The resolver turns the per-role ``system-packages.txt`` declarations into the
set of framework tools a deployment provides. The distinction that matters for
the parity guard: a *read but empty* set is verifiable absence (→ block a
required check), while an *unfindable* tree is unverifiable (→ ``None`` → warn).
"""

from __future__ import annotations

import pytest

from squadops.cycles.check_registry import TOOL_NODE
from squadops.cycles.check_tooling import resolve_provisioned_tooling

pytestmark = [pytest.mark.domain_orchestration]


def _write_role_packages(root, role: str, contents: str) -> None:
    role_dir = root / role
    role_dir.mkdir(parents=True)
    (role_dir / "system-packages.txt").write_text(contents, encoding="utf-8")


def test_node_packages_resolve_to_the_node_tool(tmp_path):
    """nodejs/npm in the qa role → the deployment provisions `node` — the exact
    provisioning the frontend-build check's tooling requirement is matched against."""
    _write_role_packages(tmp_path, "qa", "nodejs\nnpm\n")
    assert resolve_provisioned_tooling(tmp_path) == frozenset({TOOL_NODE})


def test_comments_blanks_and_unknown_packages_are_ignored(tmp_path):
    """Only recognized packages count; a stray comment/blank/unmapped apt package
    must not be miscounted as a framework tool."""
    _write_role_packages(tmp_path, "qa", "# QA packages\n\nnodejs\ncurl\n  \n")
    assert resolve_provisioned_tooling(tmp_path) == frozenset({TOOL_NODE})


def test_tooling_is_unioned_across_roles(tmp_path):
    """A role declaring node and another declaring nothing relevant → node still
    provisioned deployment-wide."""
    _write_role_packages(tmp_path, "qa", "npm\n")
    _write_role_packages(tmp_path, "dev", "build-essential\n")
    assert resolve_provisioned_tooling(tmp_path) == frozenset({TOOL_NODE})


def test_present_but_no_node_is_verifiable_absence_not_none(tmp_path):
    """A readable tree with no node declaration is *verifiable* absence — an empty
    set (which blocks a required node check), NOT None (which would only warn).
    Conflating the two is exactly the false-green this guard prevents."""
    _write_role_packages(tmp_path, "dev", "build-essential\n")
    assert resolve_provisioned_tooling(tmp_path) == frozenset()


def test_missing_tree_is_unverifiable_none(tmp_path):
    """An absent agents/instances tree can't be verified → None → the decision
    warns and allows rather than blocking on missing evidence."""
    assert resolve_provisioned_tooling(tmp_path / "does_not_exist") is None
