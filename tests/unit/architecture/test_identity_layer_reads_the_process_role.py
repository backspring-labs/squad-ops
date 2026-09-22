"""Every system-prompt assembly in the handler tree briefs the process, not the step.

SIP-0108 §10m. The first cut of that rule covered the four ``get_system_prompt`` calls and
missed seven ``assemble(...)`` calls that still passed the handler's step role — a review
finding, not a test's. This guard closes the class syntactically: any call in the handler
tree that assembles an identity-carrying prompt (``assemble`` or ``get_system_prompt``)
must pass ``context.role_id`` as its role, positionally or by keyword. It is sound because
the property is a property of the call's text, and it names the offending file and line.

``assemble_task_only`` is deliberately outside it: it composes the STEP's task-type fragment
alone, with no identity layer, and its role is the override key for that fragment.
"""

from __future__ import annotations

import ast
from pathlib import Path

HANDLERS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "capabilities" / "handlers"
IDENTITY_ASSEMBLIES = {"assemble", "get_system_prompt"}


def _is_context_role_id(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "role_id"
        and isinstance(node.value, ast.Name)
        and node.value.id == "context"
    )


def _role_argument(call: ast.Call) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == "role":
            return kw.value
    return call.args[0] if call.args else None


def _identity_assembly_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in IDENTITY_ASSEMBLIES):
            continue
        # …prompt_service.assemble(...) / …prompt_service.get_system_prompt(...)
        owner = func.value
        if isinstance(owner, ast.Attribute) and owner.attr == "prompt_service":
            yield node


def test_every_identity_assembly_in_the_handler_tree_briefs_the_process():
    offenders = []
    seen = 0
    for path in sorted(HANDLERS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in _identity_assembly_calls(tree):
            seen += 1
            role = _role_argument(call)
            if role is None or not _is_context_role_id(role):
                offenders.append(
                    f"{path.relative_to(HANDLERS)}:{call.lineno} passes "
                    f"{ast.unparse(role) if role is not None else '<nothing>'}"
                )
    assert seen >= 11, f"expected the eleven known identity assemblies, found {seen}"
    assert not offenders, (
        "identity-carrying prompt assemblies that brief the STEP instead of the process "
        "(SIP-0108 §10m — pass context.role_id):\n  " + "\n  ".join(offenders)
    )
