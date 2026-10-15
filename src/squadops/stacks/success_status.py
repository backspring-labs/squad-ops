"""The success status an endpoint answers with — the one home of the rule (#772, #1067).

A leaf module on purpose: ``scaffold`` imports the stack modules at import time and the
stack modules need this rule, so it cannot live in either without a cycle. ``scaffold``
re-exports both names.
"""

from __future__ import annotations

from typing import Any


def derived_success_status(method: str, path: str) -> int | None:
    """The success status the contract asserts for an endpoint that declares none.

    Collection POST -> 201, child-action POST -> 200, everything else -> None (no status
    probe is derived; a GET answers with HTTP's own 200). **The one home of this rule
    (#772, #1067).** It had seven: three sites in the contract deriver, the skeleton's
    decorator (which OMITTED the kwarg, so FastAPI's 200 met the deriver's 201 on an
    undeclared collection POST — an unwinnable contract), the framing mirror, the
    scaffold gate's allowed set and the Next.js route stub. Every one now calls here.
    """
    if method.upper() != "POST":
        return None
    return 201 if "{" not in path else 200


def success_status_for(ep: Any, method: str | None = None) -> int:
    """The status an implementer must answer with: declared wins, else derived, else 200.

    ``method`` overrides the endpoint's own for child-action rows, which carry a path and
    a declared status but are POSTs by construction.
    """
    declared = getattr(ep, "success_status", None)
    if declared is not None:
        return int(declared)
    derived = derived_success_status(method or getattr(ep, "method", "GET"), ep.path)
    return derived if derived is not None else 200
