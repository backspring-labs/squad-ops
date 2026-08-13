"""#663 D5 — the two plan-gate seams stay separate AND both stay wired.

``_reject_invalid_plan_before_workload_gate`` (returns errors → recorded
system REJECTED + free framing re-roll; the inter-workload promotion net) and
``_reject_unsatisfiable_plan_at_gate`` (raises; the in-run dispatch-admission
net) carry deliberately different error-channel semantics (#473). The
#718/#719 scar: a plan-validation fix landed on one seam while the other
silently kept the old behavior. These tests mechanize the ownership
documentation so it cannot rot silently.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_orchestration]

_EXECUTOR_PATH = (
    Path(__file__).resolve().parents[3] / "adapters" / "cycles" / "dispatched_flow_executor.py"
)

_PROMOTION_SEAM = "_reject_invalid_plan_before_workload_gate"
_DISPATCH_SEAM = "_reject_unsatisfiable_plan_at_gate"


def _method_calls(tree: ast.AST, method_name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method_name
    ]


def test_both_plan_gate_seams_are_defined_and_called():
    """Bug caught: a refactor merges the seams (or drops one call site) and a
    whole gate path loses its validation net — the promotion path would admit
    an unvalidatable plan to a full implementation run, or the dispatch path
    would lose its fail-fast."""
    tree = ast.parse(_EXECUTOR_PATH.read_text(encoding="utf-8"))

    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
    }
    assert _PROMOTION_SEAM in defined, f"{_PROMOTION_SEAM} was removed — see its D5 ownership note"
    assert _DISPATCH_SEAM in defined, f"{_DISPATCH_SEAM} was removed — see its D5 ownership note"

    assert _method_calls(tree, _PROMOTION_SEAM), (
        f"no call site for {_PROMOTION_SEAM} — the inter-workload promotion path "
        "(the one multi-workload cycles actually traverse) lost its plan-validation net"
    )
    assert _method_calls(tree, _DISPATCH_SEAM), (
        f"no call site for {_DISPATCH_SEAM} — the in-run dispatch path lost its "
        "fail-fast plan-validation net"
    )


def test_seam_error_channels_stay_distinct():
    """Bug caught: someone 'harmonizes' the seams' error handling — the
    promotion seam starting to raise would kill the orchestrator where a
    recorded system rejection + re-roll was owed (the 3.13 stall class);
    the dispatch seam starting to return would silently drop its errors
    (no caller consumes a return value there)."""
    tree = ast.parse(_EXECUTOR_PATH.read_text(encoding="utf-8"))
    methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        and node.name in (_PROMOTION_SEAM, _DISPATCH_SEAM)
    }

    promotion_returns = [
        node
        for node in ast.walk(methods[_PROMOTION_SEAM])
        if isinstance(node, ast.Return) and node.value is not None
    ]
    assert promotion_returns, (
        f"{_PROMOTION_SEAM} no longer returns its errors — #473 requires the "
        "returned-list channel so the caller records a system REJECTED decision"
    )

    dispatch_raises = [
        node for node in ast.walk(methods[_DISPATCH_SEAM]) if isinstance(node, ast.Raise)
    ]
    assert dispatch_raises, (
        f"{_DISPATCH_SEAM} no longer raises — the in-run net's rejection channel "
        "is the raise; a returned value would be silently discarded at its call site"
    )


def test_builder_floor_rule_is_wired_at_both_seams():
    """#888 (the #718/#719 rule applied): the builder-floor validator must be
    called from BOTH seams — dropping either lets an under-covered plan reach
    the #291 completion gate, which has no repair path (roll 15's dead end)."""
    tree = ast.parse(_EXECUTOR_PATH.read_text(encoding="utf-8"))

    seam_sources = {
        node.name: ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        and node.name in (_PROMOTION_SEAM, _DISPATCH_SEAM)
    }

    for seam in (_PROMOTION_SEAM, _DISPATCH_SEAM):
        assert "validate_builder_floor" in seam_sources[seam], (
            f"{seam} no longer calls validate_builder_floor — an under-covered "
            "builder plan on this path dies at run completion with no repair path"
        )
