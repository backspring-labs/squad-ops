"""Guard 1a — no execution path branches on authoring mode below framing.

SIP-0103 §3.5's claim is that authored mode is a mode of manifest **provenance, not a
second pipeline**: post-approval an authored manifest enters ``plan_artifact_refs``
exactly as a seeded one does, and expander, contract derivation, bind-mode plan
validation and every 1.4/1.5 enforcement surface operate identically.

The invariant holds today and was unpinned (verified 2026-08-09): the predicate
``authors_interface_manifest`` has exactly one production call site, inside the framing
branch of ``build_task_plan``. **Nothing stopped a second one appearing.** That is the
whole risk — the claim is not defended by a design that makes a fork impossible, it is
defended by there currently being only one place that asks the question. A single
``if authors_manifest:`` added to a handler or the executor would falsify the release's
architectural claim while every functional test stayed green, because both modes would
still work; they would simply no longer be the same pipeline.

Guard 1b (``test_authored_mode_equivalence``) is the other half and is not redundant
with this one: a structural test proves nothing *branches*, not that the transformation
is the same. This file is structure; that one is output.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_cycles]

_REPO = Path(__file__).resolve().parents[3]
_PRODUCTION_ROOTS = (_REPO / "src", _REPO / "adapters")

#: The predicate that answers "is this cycle authoring its own manifest?".
_PREDICATE = "authors_interface_manifest"
#: The one flag it produces, consumed by framing's step builder.
_FLAG = "authors_manifest"
#: The module the single legitimate call site lives in. The *function* is
#: deliberately not pinned — see the framing-branch test.
_CALL_SITE_MODULE = _REPO / "src" / "squadops" / "cycles" / "task_plan.py"


def _production_files() -> list[Path]:
    return sorted(p for root in _PRODUCTION_ROOTS for p in root.rglob("*.py"))


def _calls_to(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
    ]


def test_the_authoring_predicate_has_exactly_one_production_call_site():
    """Bug caught: a second place asks "are we in authored mode?" and acts on it.

    That is how a provenance flag becomes a pipeline fork. Both modes keep working, so
    no functional test fails — the release's claim is simply no longer true. Definitions
    and imports are fine; only *calls* count, because only a call can branch.
    """
    sites: list[str] = []
    for path in _production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in _calls_to(tree, _PREDICATE):
            sites.append(f"{path.relative_to(_REPO)}:{call.lineno}")

    assert len(sites) == 1, (
        f"authoring mode is asked about in {len(sites)} places: {sites}. SIP-0103 §3.5 "
        f"allows exactly one, inside framing — a second call site is a pipeline fork "
        f"however small it looks."
    )
    assert sites[0].startswith("src/squadops/cycles/task_plan.py:")


def test_the_one_call_site_is_inside_the_framing_branch():
    """Bug caught: the predicate stays single-call-site but moves below framing.

    Counting call sites alone would pass if the call were hoisted out of the framing
    branch and the flag threaded into the implementation path — exactly the shape a
    well-meaning refactor produces, and it would falsify the release's claim silently.

    Deliberately keyed on the FRAMING guard rather than on an enclosing function name:
    the plan recorded this call site as ``build_task_plan`` and it has since moved into
    ``_resolve_workload_steps``, so a name-based assertion would already have rotted
    once. What must hold is that the call is guarded by ``WorkloadType.FRAMING``,
    wherever that guard lives.
    """
    tree = ast.parse(_CALL_SITE_MODULE.read_text(encoding="utf-8"))

    framing_body_lines: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if not any(
            isinstance(cmp, ast.Attribute) and cmp.attr == "FRAMING" for cmp in ast.walk(node.test)
        ):
            continue
        for stmt in node.body:
            framing_body_lines.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))

    assert framing_body_lines, "task_plan.py no longer has a recognizable FRAMING branch"

    call_lines = {call.lineno for call in _calls_to(tree, _PREDICATE)}

    assert call_lines and call_lines <= framing_body_lines, (
        f"the authoring predicate is called at {sorted(call_lines)}, outside any "
        f"FRAMING-guarded branch — authoring mode must not be visible to another workload"
    )


def test_the_authoring_flag_never_leaves_the_framing_step_builder():
    """Bug caught: the flag is threaded past framing into a downstream consumer.

    ``authors_manifest`` decides one thing — whether framing gains an authoring stage.
    If it appears in a handler, the executor, or any acceptance surface, authoring mode
    has become an input to work below framing, which is the fork this guard exists to
    prevent. Scoped to the single module that legitimately names it.
    """
    offenders = {
        str(path.relative_to(_REPO))
        for path in _production_files()
        if _FLAG in path.read_text(encoding="utf-8")
    }

    assert offenders == {"src/squadops/cycles/task_plan.py"}, (
        f"the authoring flag reaches {sorted(offenders - {'src/squadops/cycles/task_plan.py'})}; "
        f"it may only decide framing's step list"
    )


def test_the_executor_reads_authoring_only_for_gate_and_artifact_vocabulary():
    """Bug caught: the executor starts branching on authoring mode.

    The executor legitimately imports two constants from the authoring module — the
    machine gate-decision principal and the manifest artifact type — plus two
    function-local imports for the question gate and the revision restart. None of those
    is a mode branch. What must never appear there is the *predicate*, and pinning the
    imported vocabulary keeps this test honest about what it is permitting rather than
    silently allowing anything the executor cares to import later.
    """
    executor = _REPO / "adapters" / "cycles" / "dispatched_flow_executor.py"
    tree = ast.parse(executor.read_text(encoding="utf-8"))

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").endswith("cycles.manifest_authoring")
        for alias in node.names
    }

    assert _PREDICATE not in imported
    assert imported == {
        "GATE_DECIDED_BY_NO_QUESTIONS",
        "MANIFEST_ARTIFACT_TYPE",
        "open_questions",
        "REVISION_RESTART_TASK_TYPE",
    }, (
        f"the executor's authoring-module vocabulary changed to {sorted(imported)} — new "
        f"names need review against SIP-0103 §3.5 before they are permitted here"
    )
