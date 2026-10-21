"""The increment test-scope rule's one rendering (#1884, the owner's rule): every author of an
increment's tests, the ``qa.test`` author and its ``qa.test_repair``, is shown what its tests may
assert through the same managed asset (#448) the plan authors are. One asset, one author of the
rule."""

from __future__ import annotations

from typing import Any

from squadops.stacks.scaffold import criterion_route_harness_for, route_caller_import_for


async def increment_test_scope_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The rule and the increment's criteria as an appendix, or ``""`` outside an increment.

    On a stack whose criterion tests must reach a route through the scaffold's caller (#2577),
    an increment with an endpoint criterion is also told how, through the stack's own asset."""
    scope = inputs.get("increment_test_scope")
    if renderer is None or not isinstance(scope, dict):
        return ""
    # deferred (cycle): campaigns.increment_tree loads this module
    from squadops.campaigns.increment_tree import test_scope_lines

    rendered = await renderer.render(
        "request.increment_test_scope_appendix", {"scope_lines": test_scope_lines(scope)}
    )
    stack = str(scope.get("stack") or "")
    harness = criterion_route_harness_for(stack)
    routes = [str(c) for c in scope.get("route_criteria") or ()]
    if not harness or not routes:
        return rendered.content
    how = await renderer.render(
        harness,
        {
            "route_criteria": ", ".join(routes),
            "route_caller_import": route_caller_import_for(stack),
        },
    )
    return f"{rendered.content}\n\n{how.content}"
