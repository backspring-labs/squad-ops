"""The increment test-scope rule's one rendering (#1884, the owner's rule): every author of an
increment's tests, the ``qa.test`` author and its ``qa.test_repair``, is shown what its tests may
assert through the same managed asset (#448) the plan authors are. One asset, one author of the
rule."""

from __future__ import annotations

from typing import Any


async def increment_test_scope_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The rule and the increment's criteria as an appendix, or ``""`` outside an increment."""
    scope = inputs.get("increment_test_scope")
    if renderer is None or not isinstance(scope, dict):
        return ""
    from squadops.campaigns.increment_tree import test_scope_lines

    rendered = await renderer.render(
        "request.increment_test_scope_appendix", {"scope_lines": test_scope_lines(scope)}
    )
    return rendered.content
