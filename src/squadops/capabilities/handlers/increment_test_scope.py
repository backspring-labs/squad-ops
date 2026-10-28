"""The increment test-scope rule's one rendering (#1884, the owner's rule): every author of an
increment's tests, the ``qa.test`` author and its ``qa.test_repair``, is shown what its tests may
assert through the same managed asset (#448) the plan authors are. One asset, one author of the
rule. The pages a repository-backed change adds, with their views' anchors (SIP-0109 §24cp), are
rendered here too, for the suite's author and the view's."""

from __future__ import annotations

from typing import Any

from squadops.stacks.scaffold import (
    criterion_page_harness_for,
    criterion_route_harness_for,
    page_loader_import_for,
    route_caller_import_for,
)


async def increment_test_scope_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The rule and the increment's criteria as an appendix, or ``""`` outside an increment.

    On a stack whose criterion tests must reach a route through the scaffold's caller (#2577),
    an increment with an endpoint criterion is also told how, through the stack's own asset; and
    one with a page criterion how to load its page through the scaffold's loader (#2602)."""
    scope = inputs.get("increment_test_scope")
    if renderer is None or not isinstance(scope, dict):
        return ""
    # deferred (cycle): campaigns.increment_tree loads this module
    from squadops.campaigns.increment_tree import test_scope_lines

    rendered = await renderer.render(
        "request.increment_test_scope_appendix", {"scope_lines": test_scope_lines(scope)}
    )
    stack = str(scope.get("stack") or "")
    sections = [rendered.content]
    # SIP-0109 §24cp: the pages the change adds, whose tests find each view by its anchor.
    views = await increment_views_section(renderer, scope.get("views"))
    if views:
        sections.append(views)
    harness = criterion_route_harness_for(stack)
    routes = [str(c) for c in scope.get("route_criteria") or ()]
    if harness and routes:
        how = await renderer.render(
            harness,
            {
                "route_criteria": ", ".join(routes),
                "route_caller_import": route_caller_import_for(stack),
            },
        )
        sections.append(how.content)
    page_harness = criterion_page_harness_for(stack)
    pages = [str(c) for c in scope.get("page_criteria") or ()]
    if page_harness and pages:
        how = await renderer.render(
            page_harness,
            {
                "page_criteria": ", ".join(pages),
                "page_loader_import": page_loader_import_for(stack),
                "route_caller_import": route_caller_import_for(stack),
            },
        )
        sections.append(how.content)
    return "\n\n".join(sections)


async def increment_views_section(renderer: Any, views: Any) -> str:
    """The pages a repository-backed change adds, each with the anchor its view renders on its
    root element, through ``request.increment_views_appendix`` (SIP-0109 §24cp), or ``""``. One
    rendering for the suite's author (in its test scope) and the view's author
    (``increment_views``), so both are told the one anchor acceptance reads the page for."""
    if renderer is None or not isinstance(views, list) or not views:
        return ""
    # deferred (cycle): campaigns.increment_tree loads this module
    from squadops.campaigns.increment_tree import view_lines

    rendered = await renderer.render(
        "request.increment_views_appendix", {"view_lines": view_lines(views)}
    )
    return rendered.content
